# Entity Slice Validation

## Related issues and PRs

- Implementation PR(s): [cedar#1446](https://github.com/cedar-policy/cedar/pull/1146)

## Timeline

- Started: 2024-08-01
- Accepted: 2024-10-03
- Landed: 2024-10-03 on `main`
- Released: 2024-10-07 in `cedar-policy` 4.2.0 as an experimental feature

Note: These statuses are based on [the first version of the RFC process](./../archive/process-v1/README.md).

## Summary

This RFC introduces "Entity Slicing Validation" (ESV), which consists of

1. An additional validation check, and
2. A generic entity slicing algorithm

The two are connected by the concept of a "level," which defines the depth from root variables (like `principal` and `resource`) at which entity dereferencing operations may safely take place in policies. The validation check ensures that policies never dereference beyond the given level. The slicing algorithm determines what entities are needed to safely decide an authorization request when evaluating policies valid at a given level.

## Basic example

Consider the following [policies](https://github.com/cedar-policy/cedar-examples/blob/release/3.2.x/tinytodo/policies.cedar), taken from the [TinyTodo example application:](https://github.com/cedar-policy/cedar-examples/tree/release/3.2.x/tinytodo)

```
// Policy 1: A User can perform any action on a List they own
permit (
  principal,
  action,
  resource is List
)
when { resource.owner == principal };

// Policy 2: A User can see a List if they are either a reader or editor
permit (
    principal,
    action == Action::"GetList",
    resource
)
when { principal in resource.readers || principal in resource.editors };

// Policy 4: Admins can perform any action on any resource
permit (
  principal in Team::"Admin",
  action,
  resource
);
```

We suppose (per the [schema](https://github.com/cedar-policy/cedar-examples/blob/release/3.2.x/tinytodo/tinytodo.cedarschema), not shown) that `principal` always has entity type `User`, and `resource` always has entity type `List`. These policies are valid at level 1, meaning that variables `principal`, `action`, `resource` and `context` are only *directly* dereferenced, i.e., any entities they reference are not themselves dereferenced.

For example, in policy 1, the expression `resource.owner == principal` directly dereferences `resource` by accessing the contents of its `owner` attribute. In policy 2, expression `principal in resource.readers` directly dereferences `resource` to retrieve the contents of its `readers` attribute, and also directly dereferences `principal` to retrieve its ancestors, to see whether one might be equal to the contents of `resource.readers`. Policy 4 also directly dereferences `principal` to access its ancestors, to see if one is `Team::"admin"`.

Because these policies are valid at level 1, applications submitting authorization requests only need to provide entity data for entities provided as variables, and nothing else. For example, say we want to evaluate the request (`User::"Aaron"`, `Action::"GetList"`, `List::"Objectives"`, `{}`). Then we would only need to provide entity data (direct attributes and ancestors) for `User::"Aaron"`, `Action::"GetList"`, and `List::"Objectives"`. There is no need to provide data for entities referenced from these entities. For example, suppose the `readers` attribute of `List::"Objectives"` is `Team::"interns"`; there is no need to provide data for `Team::"interns"` because we know it will never, itself, be dereferenced when evaluating these policies. There is also no need to provide entity data for other entities directly mentioned in policies, e.g., `Team::"Admin"`.

Now suppose we wanted to extend our TinyTodo policies with the following:

```
// Policy 6: No access if not high rank and at location DEF, 
// or at resource's owner's location
forbid(
    principal,
    action,
    resource is List
) unless {
   principal.joblevel > 6 && principal.location like "DEF*" ||
   principal.location == resource.owner.location
};
```

This policy does *not* validate at level 1. That is because the expression `resource.owner.location` is only valid at level 2: It requires dereferencing `resource` to retrieve the entity in the `owner` attribute, and then requires dereferencing that entity to obtain the contents of its `location` attribute. As a result, if we only provided the `principal` and `resource` entity data, as described above, evaluating policy 6 could produce an evaluation error since data may not be provided for `resource.owner`.

All of the Cedar example policy sets validate with level-based validation, either at level 1 or 2; see the Appendix for details.

## Motivation

Currently, Cedar provides no support for slicing. Users are required to either be inefficient and produce their entire entity store as a slice, or derive their own ad-hoc slicing algorithm. We'd like to provide an out-of-the-box solution that addresses many user's needs. Entity slicing in general is a problem very tied to the specifics of application/deployment. It's likely impossible to have a fully general solution. This RFC is attempting to provide a solution for entity slicing that works for the 80% case, while acknowledging that it won't work for everyone. 

Additionally, there are some application scenarios where the actors writing the policies and the people performing slicing are not the same people, and thus the slicers need to impose some kind of restrictions on policy authors.

This RFC has a close connection to [RFC 74: Entity Slicing using Data Tries](https://github.com/cedar-policy/rfcs/pull/74), which also seeks to provide a sound foundation for entity slicing. We discuss the relationship between them in the Alternatives below; ultimately, we believe they are complementary and should coexist.

## Detailed design

### Entity dereferences

An "Entity Dereference" is any operation that requires directly accessing an entity’s data. The following is an exhaustive list of entity dereferencing operations

1. `e1 in e2` dereferences `e1` (but not `e2`)
2. `e1.foo` dereferences `e1` iff `e1` is an entity
3. `e1 has foo` dereferences `e1` iff `e1` is an entity

Note that testing equality *is not* a dereferencing operation. Therefore expressions like `e1 == e2`, `e1.contains(e2)` and `e3 in e2` do not dereference `e1` or `e2`.

Also note that by “dereference” above, we are only referring to the given operation, not about any operations that might be executed to evaluate subexpressions. For example, while `e1 in e2` only dereferences `e1` (per rule 1 above), if `e2` is `principal.foo`, then of course evaluating `e2` dereferences `principal` (per rule 2 above).

### Entity roots

The variables `principal`, `action`, and `resource` are *entity roots*. (Entity literals are *not* entity roots, and operations on such literals are limited, as described below. Slots and the `Unknown` entity are treated as entity literals because slots will be replaced by literals and `Unknown` cannot be dereferenced.) They directly name entities from a request that could be dereferenced in a policy. A `context` is not an entity root directly; rather, any attributes it (transitively) contains that have entity type are considered roots. For example, consider the following schema:

```
entity User {
    manager: User,
    age: Long,
};
action getDetails appliesTo {
    principal: User,
    resource: User,
    context: {
        admin: User,
        building: { location: Long, ITDeptHead: User },
        foo: { inner: User },
        bar: { inner: User }
    }
};
```

Here, `principal`, `action`, and `resource` are entity roots (as usual), as are:

* `context.admin` 
* `context.building.ITDeptHead` 
* `context.foo.inner` , and 
* `context.bar.inner`

Note that `context`,  `context.building`, and  `context.building.location` are *not* entity roots because they do not have entity type. Moreover, `context.admin.manager` is not an entity root because `manager` is not an attribute of `context` itself.

### Dereference levels

During validation, we extend entity types with a *level*, which is either `∞` or a natural number. We call these *leveled entity types*. The level expresses how many entity dereferences are permitted starting from an expression having that type. Levels on types are only used internally; policy/schema writers never see them. When the level is `∞`, validation is unchanged from the status quo.

### Specifying the level

The maximum level that policies may validate at is specified as a parameter to the validator. Schemas are unchanged. Just like Cedar currently supports strict (the default) and permissive validation, it would now support those things with the additional parameter of what level at which to validate. As discussed in the alternatives below, a drawback of this approach is that policy writers cannot look in one place (the schema) to know the limits on the policies they can write. But in a sense, due to the dichotomy of strict vs. permissive validation, that's already the case.

### Validation algorithm

Validation works essentially as today (see our [OOPSLA’24 paper](https://dl.acm.org/doi/pdf/10.1145/3649835), page 10), but using leveled types. To validate a policy c at level N, we use a request environment which maps `principal`, `resource`, and `context` to leveled types with level N. For example, for the schema given above, to validate at level 2 our request environment would map `principal` to `User`(2), `resource` to `User`(2), and `context` to the type given in the schema annotated with 2, i.e., `{ admin: User(2), building: { location: Long, ITDeptHead: User(2) },... }`.

The rules for expression `e1 in e2` (line (3) in Fig. 7)(a) in the paper) are extended to require that the entity type of `e1` is `E1(n)` where `n > 0`. This requirement indicates that `e1` must be an entity from which you can dereference at least one level (to access its ancestors).

The rules for expression `e has f` and `e.f` (line (6) in Fig. 7(a) in the paper) are extended so that if `e` has entity type, then its type must be `E(n)` where `n > 0`. The rule for `e.f` is additionally extended so that if `e.f` has entity type `F` (per the schema), then the the final type is leveled as one less than `n`; e.g., if `e` has level `n`, then final expression has type F`(n-1)`. (Rules for `e has f` and `e.f` are unchanged when `e` has record type.)

The rule for entity literals (not shown in the paper) always ascribes them level 0 unless we are validating at level  `∞`. For example, the type of expression `User::"Alice"` is `User(0)`. This is because we do not permit dereferencing literals in policies when using leveled validation. (See the Alternatives below for a relaxation of this restriction.)

We extend the subtyping judgment (Fig 7(b) in the paper) with the following rule: `E(n) <: E(n-1)`. That is, it is always safe to treat a leveled entity type at level `n` as if it had fewer levels. This rule is important when multiple expressions are required to have the same level. For example:

```
if (principal.age < 25) then
  principal.manager
else
  principal
```

Suppose we are validating at level 2, then this expression will have type `User(1)`, where we use subtyping to give expression `principal` (in the else branch) type `User(1)` rather than `User(2)`. Similarly, if we were defining a set of entities, all of them must be given the same level. For example, we could give `[ principal.manager, principal ]` the type `Set<User(1)>`. Note that for records, individual attributes may have entities with different levels. E.g., `{ a: principal, b: principal.manager }` would have type `{ a: User(2), b: User(1) }`.

### Slicing 

Once a schema has been validated against a non- infinite level, we can use the following procedure at runtime to compute the entity slice: 

```
/// Takes:
/// request : The request object
/// level : The level the schema was validated at 
/// get-entity : A function for looking up entity data given an EUID 
function slice(request, level, get-entity) { 
    // This will be our entity slice
   let mut es : Map<EUID, EntityData> = {};

   let mut worklist : Set<EUID> = {principal, action, resource, all root euids in context};
   for euid in worklist {
     es.insert(euid, get-entity(euid));
   }
   
   let current-level = 0;
   
   while current-level <= level || worklist.empty? {
        // `t` will become our new worklist
        let t : Set<EUID> = {};
        // Clear our worklist
        for euid in worklist {
            if !es.contains(euid) {
                es.insert(euid, get-entity(euid));
            }
            // Set of all euids mentioned in this entities data
            let new-euids = filter(not-in-es?, all-euids(es.get(euid)));
            t = t.union(new-euids);
        }
        // set t to be the new worklist
        s = t;
        // increment level
        level = level + 1;
   }

    return es;
}

```

### Soundness

Leveled types permit us to generalize the soundness statement we use today. Currently, soundness assumes that expressions like `principal.manager` will never error, i.e., that the proper entity information is available. Now we assume dereferences are only available up to a certain level. In particular, we define a well-formedness judgment μ ⊢ v : τ where μ is an entity store, v is a value, and τ is a possibly leveled type. This judgment is standard for values having non-entity type, e.g.,

```
mu |- i : Long

mu |- s : String

mu |- v1 : T1 ... mu |- vn : Tn 
-------------------------------------------------------
mu |- { f1: v1, ..., fn: vn } : { f1: T1, ..., fn: Tn }
```

There are two rules for entity literals of type `E::s`. The first says level `0` is always allowed. The second says a literal can have a level `n` only if `n` dereferences are possible starting from `E::s`:

```
mu |- E::s : E(0)

mu(E::s) = (v,h) where v = { f1: v1, ..., fn: vn } and h is an ancestor set
mu |- v1 : T1 ... mu |- vn : Tn
where level(T1) >= n-1 ... level(Tn) >= n-1
------------------------------------------------------------------------------------
mu |- E::s : E(n) where n > 0
```

The auxiliary function `level(T)` identifies the lower-bound of the level of type `T`. It’s defined as follows:

* `level(E(n))` = `n`
* `level({ f1: T1, ..., fn: Tn })`  = `m` where `m` = `min(level(T1),...,level(Tn))`
* `level(Long)` = `level(String)` = `level(Boolean)` = `level(Set(T))` = (etc.) = ∞ for all other types

Thus the soundness statement says that 

1. If policy set `p` is validated against a schema `s` with level `l`, where  `l < ∞` .
2. If entity store μ is validated against schema `s` 
3. If request σ is validated against schema `s` 
4. If μ ⊢ σ(principal): E(l) where E is the expected type of the principal for this particular action, and  similarly check the proper leveling of action, request, and context.
5. Then: 
    1. `isAuthorized(sigma, p, mu)` is either a successful result value or an integer overflow error
        1. All errors except integer overflow + missing entity are prevented by the current validator 
        2. missing entity errors are prevented by the new validator + slicer 

We extend the proof of soundness to leverage premise #4 above: This justifies giving `principal` a type with level l in the initial request context, and it justifies the extensions to the rules that perform dereferencing, as they decrease the leveled result by 1, just as the μ⊢v:τ rule does, which we are given.

We also want to prove the soundness of the `slice(request, level, get-entity)` procedure defined above: If `slice`(σ, `l`, `get-entity`) = μ and request σ is validated against schema `s` and level `l`, then μ validates against schema `s` at level `l`.

## Drawbacks

Level-based slicing is coarse-grained: *all* attributes up to the required level, and *all* ancestors, for each required entity must be included in the slice. Much of this information may be unnecessary, though, depending on the particulars of the request. For example, for the TinyTodo policies in our detailed example, if the action in the request was `Action::"CreateList"`, then only policies 1 and 4 can be satisfied. For these policies, no ancestor data for `principal` and `resource` is needed, and only the contents of `resource.owner`, and not (say) `resource.readers` and `resource.editors`, is required. For some applications, the cost to retrieve all of an entity’s data and then pass it to the Cedar authorizer could be nontrivial, so a finer-grained approach may be preferred. Some ideas are sketched under alternatives.

Implementing levels is a non-trivial effort: We must update the Rust code for the validator of policies and entities, and the Lean code and proofs. We also must provide code to perform level-based slicing.

## Alternatives

### Alternative: Entity Slicing using Data Tries

[RFC 74, Entity Slicing using Data Tries](https://github.com/cedar-policy/rfcs/pull/74) proposes the idea of an _entity manifest_ to ease the task of entity slicing. This manifest is a trie-based data structure that expresses which entity attributes and ancestors are needed for each possible action. This data structure is strictly more precise than the concept of level, meaning that it may require less entity data to be provided. For example, the first part of our Basic Example in this RFC (policies 1, 2, and 4 of TinyTodo), the determined entity manifest would indicate that for the `GetList` action, you would need to provide `resource.owner`, `resource.readers`, `resource.editors` and the ancestors of `principal`. This is less data than would be retrieved by the slicing algorithm proposed here: These are level-1 valid policies, so the generic algorithm would acquire the same data given in the manifest but also more, e.g., the ancestors of `resource` and the attributes of `principal`.

Entity manifests are less effective as a _prescriptive_ mechanism that aims to limit the shape of allowable policies. For example, a Cedar policy and entity storage service might like to disallow uploading policies whose entity data is expensive to retrieve in the worst case. With levels, such a service can upper-bound this work by blocking schemas with a level greater than a threshold, say 3. Validation will then ensure that uploaded policies respect this upper bound. Manifests are unwieldy as a specification mechanism, since they are specialized to particular entity definitions and name particular types and attributes, of which there could be many. They'd also have to be updated as types evolved over time, while a level-based specification is less likely to change.

We believe that ultimately level-based validation and entity manifests should coexist. Level-based validation is used to bound entity retrieval work and prevent pathological policies, while entity manifests are used to more efficiently define the needed entity data. We could imagine a deployment strategy in which we accept this RFC and perform generic entity slicing as described here, and then later implement entity manifests, and start performing slicing using those instead.

### Alternative: Level in the schema, not as a validation parameter

Instead of specifying the validation level as a parameter to the validation algorithm, we could specify it directly in schemas. The benefit of this is that policy writers can see the expected form of policies in one place. For example, we could extend our schema from the initial example as follows:

```
level = 1;
entity User {
    manager: User,
    age: Long,
};
action getDetails appliesTo { ... }
```

Policy writers know, by seeing `level = 1`, that they can write `principal.manager` in policies, but not `principal.manager.manager`.

On the other hand, you could imagine that different applications might like to use the same schema file but have different restrictions on entity retrieval, owing to the efficiency of a chosen storage strategy. For example, in a graph database, retrieving data may be efficient no matter what the level is, whereas in a relational database, each level might necessitate another join query, which could be very inefficient.

Specifying levels in schemas also adds a complication when multiple schema files are used during validation. When a user specifies multiple files, they are effectively concatenated together by validator. What should happen if multiple files specify `level` and the level is different? One approach is that the validator would allow at most one to have a `level` specification, else it's an error. Doing so serves the expected use-case that one of those files will be for the application, specifying the `action` types and the `level`, while any others will be only general `entity` and `type` definitions, which are not application specific and thus need not concern themselves with entity slicing.

### Alternative: Per-entity levels, rather than a global level

We might refine in-schema `level` to not apply to all entities, but rather to particular entity types. For example, for `User` entities (bound to `principal`) we might specify level 2 but for any other entity type we specify `level` as 0, as per the following schema:

```
@level(2)
entity Issue = {
  repo: Repository
};
@level(0)
entity Repository = {
  owner: User,
  readers: Set<User>,
};
@level(0)
entity User = {
  manager: User
};
action ReadIssue appliesTo { principal: User, resource: Issue };
```

Per-entity levels allows you to reduce the entities you provide in the slice — given a request, you get the types of the principal and resource entities, look up what their levels are from the schema, and then provide data up to that level for each. Validation for per-entity levels is also a straightforward generalization of the algorithm sketched above.

Note that per-entity levels adds some complication to understandability, in particular for nested attributes. The question is whether the performance benefits are worth it. Suppose I have a policy

```
permit(principal, action, resource) when {
  resource.repo.owner.manager == principal
};
```

This is allowed because `Issue` is labeled with level 2. That means that we are allowed to write `resource.repo.owner.manager` (two levels of dereference beyond the first, allowed one by level 0). But this is a little confusing because we wrote `@level(0)` on `Repository`, and yet we are accessing one of its attributes. The reason that’s Ok is that `Repository` never actually is bound to `principal` or `resource`, so the level is irrelevant.

### Alternative: Full support for entity literals

Entity literals cannot be dereferenced. That means that, *at all levels*, they can only appear in `==` expressions or on the RHS of `in`. This captures use-cases that we know about. However, if you wanted to use them on the LHS of `in` or access their attributes, one approach to doing this would be to extend [enumerated entity types](https://github.com/cedar-policy/rfcs/blob/main/text/0053-enum-entities.md) to normal entity type definitions. For example, 

```
entity User in [Team] enum { "default" @level } = {
  manager: User,
  organization: Org
}; 
```

This would say that there is a `User` entity whose ID is `default` which should always be present in the entity slice, e.g., along with other entities for the principal, resource, etc. That presence is at the level specified globally, e.g., if level was 1, then just the `User::"default"` and its direct attributes would be included, but not the entities those attributes point to.

### Alternatives: Extensions to reduce ancestor requirements

One drawback of level is that it gets *all* of an entity’s ancestors when it is included in a slice. This could be very expensive in the case that the entity has many such ancestors. For example, in TinyTodo, each `User` has `Team`-typed ancestors that correspond to the `viewers` or `editors` of the `List` entities which they can access. This could be 1000s of lists, which are expensive to acquire and to include in the request (especially if calling AVP). Worse, this work is apparently wasted because the policies can only ever look at *some* of these ancestors, notably those reachable from the `editors` or `viewers` of the resource *also provided in the request*. 

Instead of passing in a principal in a request with all of its ancestors, we could just as well pass in only those that are possibly referenced by policy operations. For TinyTodo, it would be those equal to `resource.viewers` or `resource.editors` (if they match). Since this invariant is not something the application necessarily knows for certain (it might be true of policies today, but those policies could change in the future), we want a way to **reduce the provided ancestor data while being robust to how policy changes in the future**. Here are three possible approaches to addressing this issue.

#### Alternative 1: Leverage partial evaluation

We can use partial evaluation to solve this problem: Specify a concrete request with all of the needed attribute data, after entity selection, but **set the ancestor data as **** *unknown***. Partially evaluating such a request will result in results that have incomplete entity checks. These checks can then be handled by the calling application. This might be a nice feature we can package up and give to customers as a client-side library.

A drawback of this approach is that it could slow down evaluation times. This is because the entity hierarchy is used to perform policy slicing. In the worst case, you’d have to consider all possible policies. It might be possible to provide at least *some*of the hierarchy with the request to reduce the set of policies that are partially evaluated. 

#### Alternative 2: Ancestor allow-lists

When validating static policies, it’s possible to see which ancestors are potentially needed. Could we do something similar to level for policy validation, but for ancestors instead?

For TinyTodo policies above, we see the following expressions in policies:

* `principal in resource.viewers`
* `principal in resource.editors`
* `principal in Team::"admin"`

For the other examples, the situation is similar. We also see multi-level access, e.g., with GitHub policies `principal in resource.repo.readers`, and we see recursive access through sets, e.g., for Hotel Chains we see `resource in principal.viewPermissions.hotelReservations` where `hotelReservations` is a set containing entities, rather than being a single entity.

_Approach_: Add an annotation `@ancestors` to the `in` declarations around entities. When I write `entity User in [Team]`, add an annotation that enumerates the `Team`-typed expressions that can be on the RHS of `in` in policies. Here’s an example of the annotated TinyTodo schema:

```
@ancestors(resource.viewers,resource.editors,Team::"admin",Team::"interns")
entity User in [Team, Application] = {
  "joblevel": Long,
  "location": String,
};
@ancestors()
entity Team in [Team, Application];
@ancestors()
entity List in [Application] = {
  "editors": Team,
  "name": String,
  "owner": User,
  "readers": Team,
  "tasks": Tasks,
};
@ancestors()
entity Application;
...
```

Notice that we annotate `List`, `Team`, or `Application` with `()` since entities of these types never appear on the LHS of `in`. An entity type with no annotation at all is assumed to require every potential ancestor.

_Validation_: The validator will check for syntactic equality against the expressions in the annotation. In particular, when it sees an expression `E in F` in a policy, if `E` has an entity type that is annotated with the set of expressions `S` in the schema, then the validator will check that `F` ∈ `S`, using syntactic equality. With the above schema, all current TinyTodo policies would validate, while the following would not

```
// Fails because a Team-typed entity is on the LHS of `in`,
//   but entity Team has no legal RHS expressions per the schema
permit(principal,action == Action::"GetList",resource)
when { resource.editors in Team::"admin" };

// Fails because Team::"temp" is not a legal RHS expression for User
permit(principal in Team::"temp",action,resource);
```

_Entity selection_: When collecting ancestors during entity selection, the application only gets ancestors per the expressions in the annotation. To do that, it would evaluate these expressions for the current request, and provide the ancestors present in the result, if present. For example, suppose our TinyTodo request was

```
principal = User::"Alice"
action    = Action::"GetList"
resource  = List::"123"
context   = {}
```

Since TinyTodo policies are level 2, we would provide entity data for both `User::"Alice"` and `List::"123"`. Suppose that the latter’s data is

```
{ id = "123", 
  owner = User::"Bob",
  viewers = Team::"123viewers",
  editors = Team::"123editors"
}
```

The `principal` has type `User`, which is annotated in the schema with the following expressions, shown with what they evaluate to:

* `resource.viewers` evaluates to `List::"123".viewers` which evaluates to `Team::"123viewers"`
* `resource.editors` evaluates to `List::"123".editors` which evaluates to `Team::"123editors"`
* `Team::"admin"` (itself)
* `Team::"interns"` (itself)

Thus the application knows we can determine in advance whether `User::"Alice"` (the `principal`) has any of these four ancestors, and include them as such with `User::"Alice"`’s entity data, if so. No other ancestor data needs to be provided.

Note: The above algorithm i not very helpful for templates containing expressions `in ?resource` or `in ?principal` ( (templates with only `== ?principal` and `== ?resource` in them are fine, since they don’t check the ancestors). For these, you are basically forced to not annotate the entity type because `?resource` and `?principal` are not legal expressions. This makes sense inasmuch as a template with constraint `principal in ?principal` tells us nothing about possible values to which `?principal` could be linked — the values could include potentially any entity, so in the worst case we’d need to include all possible ancestors. It may be that you could use further contextual data (like the action) to narrow the ones you provide.

Note: Interestingly, no policy-set example ever has an expression other than `principal` or `resource` on the LHS of `in`. The scheme above is not leveraging this fact.

Note: This approach composes nicely with the per-entity `@level` approach sketched above.

### Alternative: Reduce attribute requirements

The per-entity level approach is one way to reduce attribute requirements, but only across levels — for a particular entity you still must provide *all* of its attributes if you are providing its data. We might like to provide only *some* attributes, similar to the alternative that requires only some, not all, ancestors.

As discussed earlier, partial evaluation can be used to help here. There could also be some sort of allow-list for attributes. Probably it would make sense to associate allow-lists with actions.

## Appendix: Accepted policy sets

All existing policies in published example Cedar applications can be validated using levels. In particular, the following policy sets validate at level 1:

* Tags and roles: https://github.com/cedar-policy/cedar-examples/tree/main/cedar-example-use-cases/tags_n_roles
* Sales orgs: https://github.com/cedar-policy/cedar-examples/tree/main/cedar-example-use-cases/sales_orgs
* Hotel chains: https://github.com/cedar-policy/cedar-examples/tree/main/cedar-example-use-cases/hotel_chains

And the following validate at level 2:

* TinyTodo: https://github.com/cedar-policy/cedar-examples/blob/main/tinytodo/policies.cedar and also https://github.com/cedar-policy/cedar-examples/blob/main/tinytodo/policies-templates.cedar
    * Policy 6 includes expression `resource.owner.location`
* Tax Preparer: https://github.com/cedar-policy/cedar-examples/blob/main/cedar-example-use-cases/tax_preprarer/policies.cedar
    * The access rule involves checking something to the effect of `principal.assigned_orgs.contains(resource.owner.organization)`. 
* Document cloud: https://github.com/cedar-policy/cedar-examples/blob/main/cedar-example-use-cases/document_cloud/policies.cedar
    * This has policy expression `(resource.owner.blocked.contains(principal) || principal.blocked.contains(resource.owner))`. (It would not make sense to duplicated the `blocked` 
* GitHub: https://github.com/cedar-policy/cedar-examples/blob/main/cedar-example-use-cases/github_example/policies.cedar
    * Expressions like `principal in resource.repo.readers` are common: A resource like an issue or pull request inherits the permissions of the repository it is a part of, so the rules chase a pointer to that repository.
