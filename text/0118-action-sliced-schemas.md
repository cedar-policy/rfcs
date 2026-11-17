# Authorization with Action-Sliced Schemas

## Related issues and PRs

- Reference Issues: (none)
- Related RFCs: [RFC 95 (type-aware partial evaluation)](0095-type-aware-partial-evaluation.md), [RFC 116 (entity validation with schema fragments)](0116-entity-validation-schema-fragments.md), [RFC 53 (enumerated entity types)](0053-enum-entities.md)
- Formal model and proofs:
  - [cedar-spec#1106](https://github.com/cedar-policy/cedar-spec/pull/1106): concrete authorization reads only the request action's closure of action entities
  - [Swolebrain/cedar-spec#1](https://github.com/Swolebrain/cedar-spec/pull/1): partial authorization with a sliced schema refines partial authorization with the full schema
- Implementation PR(s): prototype of `Schema::action_closure_for` on [Swolebrain/cedar:action-slicing](https://github.com/cedar-policy/cedar/compare/main...Swolebrain:cedar:action-slicing)
- Depends on: [cedar#2713](https://github.com/cedar-policy/cedar/pull/2713) (linking schemas with enumerated entity types), already merged

## Timeline

- Started: 2026-11-17
- Accepted: TBD
- Stabilized: TBD

## Summary

This RFC lets an application authorize a request without parsing its whole schema. It adds three things:

1. `Schema::action_closure_for`, which cuts a schema down to one action's *closure*: the action, its ancestor actions, and just enough entity type declarations to validate a request for that action. A closure is a partial schema in the sense of [RFC 116](0116-entity-validation-schema-fragments.md), and is small no matter how large the schema is.
2. Concrete authorization with a closure. The action entities of the request action's closure take the place of the action entities of the full schema. The decision is the same as with the full schema.
3. `PolicySet::tpe_with_sliced_schema`, type-aware partial evaluation ([RFC 95](0095-type-aware-partial-evaluation.md)) with a *sliced schema*: every entity type of the full schema, but only the request action's closure. Before evaluation, it omits policies whose scope cannot match the request, and it removes actions outside the closure from `action in [...]` scopes. The response is the same as with the full schema, except that it omits some policies that evaluate to `false`.

Both guarantees hold when the schema and policies meet three restrictions on how actions are used. This RFC adds a check for them. Building a sliced schema when a closure mentions an enumerated entity type relies on RFC 116 linking accepting identical definitions of that type, which Cedar already supports ([cedar#2713](https://github.com/cedar-policy/cedar/pull/2713)).

The guarantees for (2) and (3) are proved in the Lean model.

## Basic example

Take this schema:

```cedarschema
entity Team;
entity User in [Team];
entity Document { owner: User };

action ReadActions;
action ViewDocument in [ReadActions] appliesTo {
  principal: User,
  resource: Document,
  context: { mfa: Bool }
};
action ListDocuments in [ReadActions] appliesTo { principal: User, resource: Document };
action DeleteDocument appliesTo { principal: User, resource: Document };
```

and these policies:

```cedar
@id("owner-access")
permit (
  principal,
  action in [Action::"ReadActions", Action::"DeleteDocument"],
  resource
) when { resource.owner == principal };

@id("admins-delete")
forbid (principal, action == Action::"DeleteDocument", resource)
unless { principal in Team::"admins" };

@id("view-needs-mfa")
forbid (principal, action == Action::"ViewDocument", resource)
unless { context.mfa };
```

The closure of `Action::"ViewDocument"` is a partial schema. It defines `ViewDocument` and its ancestor `ReadActions`, and declares the entity types they refer to as `external`:

```cedarschema
external entity User;
external entity Document;

action ReadActions;
action ViewDocument in [ReadActions] appliesTo {
  principal: User,
  resource: Document,
  context: { mfa: Bool }
};
```

The *entity type registry* holds every entity type and no actions:

```cedarschema
entity Team;
entity User in [Team];
entity Document { owner: User };
```

An application computes the registry and one closure per action when the schema changes, and stores them as text.

**Concrete authorization.** To authorize `User::"alice"` performing `ViewDocument` on `Document::"d1"`, the application parses only the closure of `ViewDocument` and takes its action entities:

```rust
let (closure, _) = Schema::from_cedarschema_str(&stored_closure_of_view_document)?;
// Optional: validate the request against the closure.
let request = Request::new(alice, view_document, d1, context, Some(&closure))?;
let entities = Entities::from_json_value(entity_json, None)?
    .add_entities(closure.action_entities()?, None)?;
let response = Authorizer::new().is_authorized(&request, &policies, &entities);
```

The decision is the same as if `entities` held the action entities of the full schema.

**Partial authorization.** To ask which documents `User::"alice"` can view, the application links the registry with the closure into a sliced schema and calls `tpe_with_sliced_schema`:

```rust
let (registry, _) = Schema::from_cedarschema_str(&stored_registry)?;
let (closure, _) = Schema::from_cedarschema_str(&stored_closure_of_view_document)?;
let sliced = Schema::schema_link_complete([registry, closure])?;

let request = PartialRequest::new(
    PartialEntityUid::new("User".parse()?, Some("alice".parse()?)),
    view_document,
    PartialEntityUid::new("Document".parse()?, None),
    Some(Context::from_pairs([("mfa".into(), RestrictedExpression::new_bool(true))])?),
    &sliced,
)?;
let entities = PartialEntities::from_json_value(entity_json, &sliced)?;
let response = policies.tpe_with_sliced_schema(&request, &entities, &sliced)?;
```

Calling the existing `PolicySet::tpe` with `sliced` fails: `owner-access` and `admins-delete` name `Action::"DeleteDocument"`, which the sliced schema does not declare, so `tpe` returns a validation error for the unknown action literal. `tpe_with_sliced_schema` first slices the policies for the request:

- `admins-delete` is omitted, because `action == Action::"DeleteDocument"` cannot match `ViewDocument`.
- In `owner-access`, `action in [Action::"ReadActions", Action::"DeleteDocument"]` becomes `action in [Action::"ReadActions"]`, keeping only the ancestors of `ViewDocument`.
- `view-needs-mfa` is kept as written.

The residual is `permit(principal, action, resource) when { resource.owner == User::"alice" };`, the same as `tpe` returns with the full schema. With the full schema, `tpe` also reports `admins-delete` as a policy that evaluates to `false`. The sliced response does not list it.

## Motivation

Cedar's authorization APIs are written as if the whole schema were always in memory. `Authorizer::is_authorized` needs the action entities, and the usual way to get them is `Schema::action_entities` on the full schema. Request validation and type-aware partial evaluation take a complete `Schema`. Parsing a schema costs time proportional to its size, so authorization latency grows with schema size even when a request only touches a small part of it.

Most schemas are small enough that this does not matter. Some are not. Consider an authorization gateway that sits in front of many applications, for example one that authorizes AI agents calling tools across a set of services. Each application brings its own entity types and actions, and the gateway's schema is the union of all of them: thousands of actions and megabytes of schema text. Such a gateway may also see bursty, low-volume traffic, where an agent makes one authorization request and then works for seconds or minutes before making another. A cache of parsed schemas does not help much when most requests miss it.

In the prototype, with a 353 KB schema holding 2,000 leaf actions, parsing the schema and extracting its action entities takes 340 ms. A single request touches one action and its ancestors.

The goal is to put a ceiling on how much schema size adds to authorization latency:

1. Concrete authorization should cost time that depends on the size of the request action's part of the schema, not on the size of the schema.
2. Request validation should be possible with the same bounded input.
3. Type-aware partial evaluation for one concrete action should not require the actions the request does not touch. This covers permission queries such as "which resources can this principal access with this action" and "which of these actions can this principal perform".
4. The answers must be the same as with the full schema. Authorization that gives a different decision when the schema is split is not acceptable, so the conditions under which slicing is safe must be stated exactly and checkable.

Applications can partly do this today by extracting the action hierarchy themselves and building action entities by hand. That gives up request validation and partial evaluation, and leaves each application to work out when the shortcut changes a decision. The rest of this RFC gives Cedar a single, checked way to do it.

## Detailed design

### Terminology

- The **full schema** is the application's complete schema.
- The **closure** of an action `A` is the set holding `A` and every ancestor action of `A` in the full schema. Ancestors are taken transitively.
- The **closure schema** of `A` is the partial schema (RFC 116) returned by `Schema::action_closure_for(A)`. It is described [below](#computing-a-closure-schema).
- The **entity type registry** is the full schema without its actions: every entity type, with its attributes, tags, and parent types.
- The **sliced schema** for `A` is the registry linked with the closure schema of `A`. It is a complete schema whose entity types are those of the full schema and whose actions are the closure of `A`, with the same definitions as in the full schema. The Lean model calls this relation `Schema.IsActionSliceOf`.

### Restrictions

Authorization with a closure gives the same answer as with the full schema only if evaluating a policy cannot read the entity data of an action outside the closure. Scope constraints on the action (`action == A`, `action in A`, `action in [A, B]`) are safe: they read only the request action's ancestors, which the closure contains. The risk is an action UID that reaches evaluation some other way. Three restrictions rule this out. They are checked against the full schema.

1. **No action entity literals in conditions.** No `when` or `unless` clause contains an entity literal whose type is an action type. For example, `when { Action::"x" in Action::"y" }` reads the ancestors of `Action::"x"`, which the closure of the request action may not contain. Action literals in the policy scope are allowed.
2. **No `is` tests on action types in conditions.** No `when` or `unless` clause contains `e is T` where `T` is an action type. A sliced schema may omit every action of some action type, and then the typechecker does not recognize `T` as an action type. This restriction is needed only for partial authorization, but it is checked for both paths.
3. **No action-typed attributes.** No entity attribute, entity tag, or action context attribute has an action type, at any depth, including inside sets and records. Otherwise a condition such as `context.a in context.b` can compare two action UIDs from outside the closure. Cedar already rejects an action type in `appliesTo`. It accepts an action type in attributes, tags, and context today.

Restriction 3 is about the schema alone. Restrictions 1 and 2 are about policies, but need the schema to know which entity types are action types.

The Lean model shows why each restriction is needed. Without restriction 3, it gives a schema, a policy, and a request that all validate, for which the full schema allows and the closure denies. The counterexamples are in the documentation of `Schema.noActionTypedAttrs` in cedar-spec#1106.

### Checking the restrictions

The check is offered as two methods, so an application can check a new policy without rechecking the schema, and recheck its policies when the schema changes:

```rust
impl Schema {
    /// Check restriction 3: no entity attribute, entity tag, or action
    /// context attribute of this schema has an action type, at any depth.
    pub fn check_sliceable(&self) -> Result<(), SliceabilityErrors>;
}

impl PolicySet {
    /// Check restrictions 1 and 2 for every policy and template in this set:
    /// no condition contains an entity literal of an action type of `schema`,
    /// and no condition tests for an action type of `schema` with `is`.
    pub fn check_sliceable(&self, schema: &Schema) -> Result<(), SliceabilityErrors>;
}
```

`SliceabilityErrors` collects every violation, not just the first, so that an application can report them all at once. Each `SliceabilityError` names what broke the restriction:

```rust
pub enum SliceabilityError {
    /// Restriction 1
    ActionLiteralInCondition { policy_id: PolicyId, literal: EntityUid, source_loc: Option<Loc> },
    /// Restriction 2
    ActionTypeTestInCondition { policy_id: PolicyId, entity_type: EntityTypeName, source_loc: Option<Loc> },
    /// Restriction 3. `path` is the attribute path, for example
    /// `User.manager.approvers` or `context of Action::"view".a`.
    ActionTypedAttribute { path: String, entity_type: EntityTypeName, source_loc: Option<Loc> },
}
```

Cedar does not run these checks inside the slicing APIs, because those APIs never see the full schema. The application runs them when it writes a schema or a policy, and rejects the write if they fail. An application that cannot reject a write should not use the slicing APIs for that schema.

The application should also validate its policies against the full schema in strict mode. Neither guarantee below needs this as a separate assumption, but `tpe_with_sliced_schema` does not typecheck the policies it omits, so validation is the only place where an error in such a policy is reported.

### Computing a closure schema

```rust
impl Schema {
    /// The closure schema of `action`, or `Ok(None)` if `action` is not
    /// declared in this schema.
    pub fn action_closure_for(
        &self,
        action: &EntityUid,
    ) -> Result<Option<SchemaFragment>, SchemaError>;
}
```

The result is a `SchemaFragment`, so it can be stored with `SchemaFragment::to_cedarschema` or `SchemaFragment::to_json_string` and parsed back later with `Schema::from_cedarschema_str` or `Schema::from_json_str`. It contains:

- `action` and each of its ancestor actions, defined as in the full schema, with their `appliesTo` and context. Common types used in a context are inlined. Each action's descendants are cut down to those in the closure, so the result holds exactly the hierarchy among the closure's actions.
- Each entity type that one of these actions applies to, or that one of their context types mentions at any depth:
  - An enumerated entity type is defined, with its values. A closure must define it so that request validation can reject an entity ID the type does not list. RFC 116 does not allow an `external` declaration of an enumerated type, for the same reason.
  - Every other entity type is declared `external` with no parents. Request validation accepts any entity ID of such a type, as the full schema does, and does not look at its attributes or ancestors.

Entity types that the closure's actions do not refer to are left out. An action type mentioned in a context is not declared either. Restriction 3 rules this case out, and without it the closure can disagree with the full schema (see property 2 below). If `action` is not declared in the schema, the result is `Ok(None)`.

The cost of `action_closure_for` depends on the size of the closure, not the size of the schema, because a parsed `Schema` already stores each action's transitive ancestors.

Two properties make a closure schema useful on its own. The prototype tests the first for each of the 2,000 leaf actions of the benchmark schema after a round trip through Cedar schema text, and checks the action's own entity for one action after a round trip through JSON. It tests the second on requests with a wrong principal type, a wrong resource type, a missing context attribute, a context attribute of the wrong type, an empty context, and enumerated entity IDs that the type does and does not list.

1. Its action entities are those of the full schema for the actions in the closure: for each action `X` in the closure of `A`, `closure.action_entities()` holds the same entity for `X` as `full.action_entities()`, and it holds no other entities.
2. It validates a request for `A` as the full schema does: `Request::new(p, A, r, c, Some(&closure))` succeeds exactly when `Request::new(p, A, r, c, Some(&full))` succeeds, given restriction 3. Without restriction 3 the closure can reject a context that holds an action from outside the closure.

### Computing the entity type registry

```rust
impl Schema {
    /// Every entity type of this schema, with its attributes, tags, and
    /// parent types, and no actions. Common types are inlined.
    pub fn entity_type_registry(&self) -> Result<SchemaFragment, SchemaError>;
}
```

The registry is a complete schema with no actions. It is used to validate entities, and is linked with a closure schema to make a sliced schema. The prototype builds it with an internal API; this RFC makes that operation public.

### Concrete authorization with a closure schema

Concrete authorization does not need a new function. `Authorizer::is_authorized` takes the action entities as part of its `Entities` argument, and those can come from the closure schema of the request action instead of from the full schema:

1. Parse the closure schema of the request action.
2. Optionally, validate the request with `Request::new(..., Some(&closure))`. RFC 116 already supports request validation with a partial schema for any action it defines.
3. Build the entities. To validate them, parse them with the registry as the schema. The registry holds no actions, so the entity data must not contain action entities.
4. Add `closure.action_entities()` to the entities, and call `Authorizer::is_authorized`.

The registry is only needed for step 3. If the application does not validate entities, authorization parses only the closure schema.

**Guarantee.** Suppose the full schema is well formed and meets restriction 3, and the policies meet restriction 1 with respect to it. Take two entity stores that hold the same non-action entities and the same entities for the actions in the closure of the request action. They may differ on actions outside the closure. Suppose also that the request and the first store conform to the full schema. The second store needs no separate check. Then `is_authorized` gives the same response for both stores: the same decision, the same determining policies, and the same errors. In particular, take the first store to hold the full schema's action entities and the second to hold the closure's action entities instead. Both give the same response.

This is the theorem `Cedar.Validation.isAuthorized_insensitive_to_offclosure_actions` in cedar-spec#1106.

The guarantee assumes that the request and the entities conform to the full schema. An application that does not validate them can still pass, for example, an entity whose attribute holds an action UID, although restriction 3 says no attribute has an action type. Authorization with such input can differ between the full schema's action entities and the closure's. The input then does not conform to the schema, so the full-schema result was not meaningful either.

### Partial authorization with a sliced schema

```rust
impl PolicySet {
    /// Type-aware partial evaluation using a schema sliced for the request
    /// action.
    pub fn tpe_with_sliced_schema<'a>(
        &self,
        request: &'a PartialRequest,
        entities: &'a PartialEntities,
        sliced_schema: &'a Schema,
    ) -> Result<TpeResponse<'a>, tpe_err::TpeError>;
}
```

`sliced_schema` must be the sliced schema for the request action: every entity type of the full schema, and only the closure of the request action. An application builds it with `Schema::schema_link_complete([registry, closure])`. The request and the partial entities are constructed against `sliced_schema`.

`PolicySet::tpe` cannot be used with a sliced schema directly. It validates and typechecks every policy, and a policy that names an action outside the closure fails with an error for the unknown action literal, even when its scope means it cannot apply to the request. `tpe_with_sliced_schema` does the following:

1. It returns an error if `sliced_schema` is not complete. A partial schema cannot typecheck policies (RFC 116).
2. It finds the request environment of `request` in `sliced_schema`: the principal type, action, and resource type. If there is none, it returns what `PolicySet::tpe` returns with the same arguments. That is a `NoMatchingReqEnv` error.
3. It checks that every partial entity conforms to `sliced_schema`, and that `entities` gives the ancestors of the request action. An action entity outside the closure does not conform, because `sliced_schema` does not declare it. If either check fails, it returns `TpeError::SlicedEntities`. Partial entities built against `sliced_schema` include its action entities, so they pass the second check.
4. It slices each policy for the request environment:
   - A policy whose principal scope cannot match an entity of the request's principal type is omitted. So is a policy whose resource scope cannot match an entity of the request's resource type. A scope `== E` can match only an entity of the type of `E`, and `is T` only an entity of type `T`. A scope `in E` can match only an entity whose type is the type of `E` or can be a descendant of it in the schema. A scope `is T in E` needs both.
   - A policy whose action scope cannot match the request action is omitted. `action == A` matches only `A` itself. `action in [A₁, ..., Aₙ]` matches if some `Aᵢ` is the request action or one of its ancestors.
   - In a kept policy with an `action in [A₁, ..., Aₙ]` scope, every `Aᵢ` that is not the request action or one of its ancestors is removed. The list keeps its order. `action in A` is the one-element case.
   - Every other part of a kept policy is unchanged.
5. It runs type-aware partial evaluation on the sliced policies with `sliced_schema`, and returns the response.

Omitted policies are not validated or typechecked. As a result, `tpe_with_sliced_schema` can succeed where `tpe` would report an error for a policy that cannot apply to the request. This is why the application should validate its policies against the full schema when it writes them.

The new error variant is:

```rust
pub enum TpeError {
    // ... existing variants ...
    /// The partial entities cannot be used with the sliced schema.
    SlicedEntities(SlicedEntitiesError),
}

pub enum SlicedEntitiesError {
    /// A partial entity does not conform to the sliced schema. This includes
    /// an action entity that is not in the sliced schema.
    Validation(EntityValidationError),
    /// The partial entities do not give the ancestors of the request action.
    UnknownActionAncestors { action: EntityUid },
}
```

The second check in step 3 is needed for soundness. If the request action's ancestors were unknown, a dropped policy's action scope would have a residual result in the full evaluation, not `false`, and dropping the policy would lose it.

**Guarantee.** Suppose:

- the full schema and the sliced schema are well formed, and the sliced schema is the slice of the full schema for the request action;
- the full schema and the policies meet restrictions 1, 2, and 3;
- the partial request is valid for the sliced schema, and the partial entities pass the checks in step 3; and
- `tpe` with the full schema succeeds.

Then `tpe_with_sliced_schema` succeeds, and its response *refines* the full response:

- the decision is the same;
- the satisfied, errored, and residual policies are the same, for both permits and forbids;
- the policies that evaluate to `false` are a subset of those in the full response, for both permits and forbids;
- the full list of residuals, one per evaluated policy, is the full response's list with some `false` residuals removed; and
- reauthorizing the residuals with any concrete request and entities gives the same result as reauthorizing the full response's residuals.

This is the theorem `Cedar.Thm.isAuthorizedPartialWithSlicedPolicies_refines` in Swolebrain/cedar-spec#1, about the Lean function `Cedar.TPE.isAuthorizedPartialWithSlicedPolicies`. The Lean property `Response.SliceRefines` states the bullet points above.

### Linking with enumerated entity types

A closure schema defines each enumerated entity type it mentions, and the registry defines every entity type, so building a sliced schema with `Schema::schema_link([registry, closure])` links two definitions of the same enumerated type whenever a closure mentions one. RFC 116 linking as first implemented rejected this as a duplicate definition.

[cedar#2713](https://github.com/cedar-policy/cedar/pull/2713), already merged, lifts that limit. When the schemas being linked define the same enumerated entity type more than once, linking succeeds if every definition lists the same set of values, in any order, and the result has one definition of that type. If the value sets differ, linking fails with `LinkError::EnumValuesMismatch`. An `external` declaration still cannot resolve to an enumerated type, and other duplicate definitions are still errors. The same change lets an external entity type have an enumerated type as an ancestor.

This RFC needs no further change to linking. Because `action_closure_for` and the registry copy each enumerated type's values from the same full schema, the two definitions always agree, and the registry links with any closure.

### Several actions at once

A batch of concrete requests, or a permission query over several actions ("which of these actions can this principal perform on this resource?"), needs one closure per action. Each request or query is evaluated against its own action's closure or sliced schema. Closures cannot be linked with each other: two closures whose actions share an ancestor both define that ancestor, and linking rejects the duplicate. The cost is then proportional to the number and size of the closures involved, and to the registry for partial authorization, but not to the size of the rest of the schema.

### Formal model and testing

The Lean model adds:

- `Schema.actionClosure`, `Schema.actionEntities`, and `Schema.IsActionSliceOf`, which define the closure and the slice relation;
- `Schema.noActionLiteralsInConditions`, `Schema.noActionTypeTestsInConditions`, and `Schema.noActionTypedAttrs`, executable versions of restrictions 1, 2, and 3;
- `Cedar.TPE.isAuthorizedPartialWithSlicedPolicies`, the model of `tpe_with_sliced_schema`, with the slicing functions `Scope.mayMatchType`, `ActionScope.sliceForAction`, and `Policy.sliceForRequestEnv`; and
- the two theorems above.

The Lean model accepts action types in more places than the Rust schema parser, including `appliesTo`. `Schema.noActionTypedAttrs` therefore also checks `appliesTo`, so that the Lean theorems do not depend on the Rust parser's checks.

Before stabilization, the following tests are added to cedar-spec:

- Differential testing of `PolicySet::tpe_with_sliced_schema` in Rust against `isAuthorizedPartialWithSlicedPolicies` in Lean, through the Lean FFI. The FFI entry point is prototyped.
- Differential testing of the Rust restriction checks against the Lean ones.
- A property test that, for generated schemas and actions, the parsed result of `action_closure_for` linked with `entity_type_registry` is the slice of the full schema in the sense of `Schema.IsActionSliceOf`, and that the closure alone gives the same action entities and request validation results as the full schema. The theorems take `IsActionSliceOf` as a hypothesis; this test connects them to the Rust functions that produce slices.
- A property test that, for generated inputs that meet the restrictions, concrete authorization with closure action entities gives the same response as with full-schema action entities.

### Feature flag

All new APIs are behind a new experimental feature, `schema-slicing`. `tpe_with_sliced_schema` and the `SlicedEntities` error variant also need the existing `tpe` feature.

### Performance

The prototype benchmark uses a 353 KB schema with 3 entity types and 2,022 actions: 2,000 leaf actions, each with three ancestor actions, and the 22 group actions above them. One closure schema, stored as Cedar schema text, is about 384 bytes.

| Benchmark | Time |
| --- | --- |
| Parse the full schema and extract its action entities | 340 ms |
| Extract the action entities of the full schema, already parsed | 1.55 ms |
| Parse one closure schema and extract its action entities (concrete authorization) | 0.45 ms |
| Parse the registry and one closure schema, link them, and extract the action entities (request and entity validation, partial authorization) | 0.62 ms |
| Parse a one-line schema, for scale | 0.08 ms |

The times are criterion estimates from `cedar-policy/benches/schema_slicing.rs` in the prototype. Concrete authorization with a closure is faster even than taking the action entities from a full schema that is already parsed and cached.

The cost of the closure path depends on the size of the closure and, when it is used, the size of the registry. It does not depend on the number of actions in the schema. The benchmark schema has only 3 entity types with no attributes, so its registry is 46 bytes. An application with many or large entity types pays more for the registry, and only on the paths that use it.

## Drawbacks

- **The restrictions reject valid policies and schemas.** A policy with `Action::"x" in Action::"y"` in a condition, or a schema with an action-typed attribute, cannot use these APIs, and some applications will have such policies or schemas. Applications must opt in by running the checks, and must enforce them on every later write, or the guarantees do not hold.
- **The guarantees depend on checks Cedar cannot run itself.** The slicing APIs never see the full schema, so they cannot check the restrictions, that the policies validate against the full schema, or that the sliced schema really is a slice of it. An application that skips a check can get a different answer from what the full schema gives, with no error.
- **Partial-authorization responses differ in one visible way.** The response from `tpe_with_sliced_schema` does not list omitted policies among the policies that evaluate to `false`. Code that reads the full set of `false` policies sees fewer of them.
- **Storage grows with the action hierarchy.** Each closure schema repeats its action's ancestors and the entity type declarations its actions use. The total size of all closures can be much larger than the schema when hierarchies are deep or when many actions share large contexts.
- **More API and more proofs to maintain.** The feature adds five public methods, three error types, a new `TpeError` variant, and a set of Lean definitions and proofs. Future changes to type-aware partial evaluation must keep `tpe_with_sliced_schema` and its proof working.

## Alternatives

### Do nothing

Applications can extract the action hierarchy from the schema ahead of time, for example as a map from each action to its ancestors, and build action entities from it at authorization time. This is fast, but gives no request validation and no partial evaluation, and each application has to work out by itself when the shortcut changes a decision. The counterexamples behind restriction 3 show that this is easy to get wrong.

### Make schemas faster to parse or cache

A faster parser lowers the cost per byte, but the cost is still proportional to the schema size. Caching parsed schemas helps applications with steady traffic and a few schemas. It helps little when traffic is bursty or when there are many large schemas, which is the case this RFC targets.

### Partition the schema by namespace

An application could store and parse one namespace at a time. This puts no bound on the size of the namespace that holds the request action, and action groups or entity types in other namespaces force loading those namespaces too. In the worst case it loads the whole schema.

### Make `PolicySet::tpe` accept sliced schemas

Instead of a new function, `tpe` could treat unknown action literals as warnings, or slice policies itself whenever the schema lacks some actions. That would change the behavior of an existing API, and `tpe` cannot tell a sliced schema from a schema with a mistake in it. A separate function makes the caller state that the schema is a slice, and takes on the obligations that come with that.

### A `SliceableSchema` type

A new type could guarantee, when it is built, that a schema meets restriction 3. Restrictions 1 and 2 are about policies, so the type would also need to hold or check the policy set, and would have to be rebuilt on every policy change. Two check functions are simpler and fit how applications write schemas and policies separately.

### Allow action literals in conditions

Restriction 1 could be lifted by including in the slice the closure of every action that a condition names, in addition to the request action's closure. The set of such actions can be computed from the policies ahead of time. This needs closures to be combined, which the current linking rules do not allow (see [Several actions at once](#several-actions-at-once)), and needs the proofs to cover a union of closures. It is a possible extension; see the unresolved questions.

## Unresolved questions

- **Combining closures.** Linking could also accept identical action definitions, in the same way as it accepts identical enumerated types since cedar#2713. Closures could then be unioned into one schema for a batch or a multi-action permission query, and restriction 1 could be lifted as described in the alternatives. Should this RFC include that, or leave it to a later one?
- **Where the restriction checks live.** This RFC proposes `Schema::check_sliceable` and `PolicySet::check_sliceable`. The checks could instead be a mode of the `Validator`, which would report them alongside other validation errors with the same source locations. Which is more useful to applications?
- **Reporting omitted policies.** Should `TpeResponse` from `tpe_with_sliced_schema` list the IDs of the policies it omitted, so that callers can tell an omitted policy from one that was never in the set?
- **Proof of request validation with a closure.** That a closure schema validates requests for its action exactly as the full schema does is tested in the prototype but not proved. RFC 116's soundness property gives one direction. Should a proof of the other direction be a stabilization requirement?
