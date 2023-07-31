# Standalone strict validation

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Start Date: 11-07-2023
- Date Entered FCP:
- Date Accepted:
- Date Landed:

## Summary

Internally, strict validation of a policy is implemented as 1/ checking and transforming the policy using a _permissive_ validation mode; 2/ annotating the transformed policy with types, and 3/ checking the types against more restrictive rules. We would like to be able to at least _explain_ strict mode independently of permissive mode, but there is no easy way to do that. This RFC proposes to separate strict mode from permissive mode, making the implementation simpler and more understandable/explainable, though somewhat more strict.

## Motivation

Consider this policy, given in file [`policy.cedar`](./0019/policy.cedar), where `principal` is always of type `User`:
```
permit(
    principal,
    action == Action::"read",
    resource)
when {
  (if context.sudo then Admin::"root" else principal) == resource.owner ||
  resource.isPublic
}
```
If we validate this policy against the schema [`schema.cedarschema.json`](./0019/schema.cedarschema.json), then `resource.owner` is always of type `User`. As a result, the policy is rejected by strict-mode validation, with two errors:
1. the `if`/`then`/`else` is trying to return entity type `Admin` in the true branch, and entity type `User` on the false branch, and these two are not equal.
1. since `resource.owner` has type `User`, it will have a type different than that returned by the `if`/`then`/`else`, which can sometimes return `Admin`.

But if we change `"User"` in [`schema.cedarschema.json`](./0019/schema.cedarschema.json) on line 13 to `"Org"`, then `resource.owner` is always of type `Org`. As a result, the policy is accepted! The two error conditions given above seem not to have changed -- the conditional returns different types, and those types may not equal the type of `resource.owner` -- so it's puzzling what changed to make the policy acceptable.

The reason is that strict-mode validation is dependent on permissive-mode validation. In particular, strict-mode validation is implemented in three steps: 1/ validate and transform the policy using permissive mode; 2/ annotate the transformed policy AST with types; and 3/ check the types against more restrictive rules.

In the first case, when `resource.owner` is always of type `User`, the expression `(if ...) == resource.owner` has type `Boolean` in permissive mode and as a result no transformation takes place in step 1. As a result, it is rejected in step 3 due to the errors given above.

In the second case (after we change the schema), `resource.owner` is always of type `Org`. Under permissive mode, the `(if ...) == resource.owner` expression has singleton type `False`. That’s because the `(if ...)` expression has type `User|Admin` ("`User` or `Admin`") and `User|Admin` entities can never be equal to `Org` entities. Both the _singleton type_ `False` (which only validates an expression that _always_ evaluates to `false`) and _union types_ like `User|Admin` are features of permissive mode and are not present in strict mode. Because of these features, step 1 will replace the `False`-typed `(if ...) == resource.owner` with value `false`, transforming the policy to be `permit(principal,action,resource) when { false || resource.isPublic }`. Since this policy does not require union types and otherwise meets strict mode restrictions, it is accepted in step 3.

In sum: To see why the second case is acceptable, we have to understand the interaction between permissive mode and strict mode. This is subtle and difficult to explain. Instead, we want to implement strict mode as a standalone feature, which does not depend on features only present in permissive mode.

## Detailed design

We propose to change strict-mode validation so that it has the following features taken from permissive mode:
* Singleton boolean `True`/`False` types (which have 1/ special consideration of them with `&&`, `||`, and conditionals, and 2/ subtyping between them and `Boolean`, as is done now for permissive mode).
* Depth subtyping, but not width subtyping, to support examples like `{ foo: True } <: { foo: bool }`.

Strict-mode validation will continue to apply the restriction it currently applies:
* Arguments to `==` must have the compatibles types (i.e., an upper bound exists according to the strict - depth only - definitions of subtyping) _unless_ we know that comparison will always be false, in which case we can give the `==` type `False`. The same goes for `contains`, `containsAll`, and `containsAny`.
* Arguments to an `in` expression must be compatible with the entity type hierarchy, or we must know that the comparison is always false.
* Branches of a conditional must have compatible types _unless_ we can simplify the conditional due to the guard having a `True`/`False` type.
* The elements of a set must have compatible types.
* As a consequence of the two prior restrictions, union types cannot be constructed.
* Empty set literals may not exist in a policy because we do not currently infer the type of the elements of an empty set.
* Extension type constructors may only be applied to literals.

The current way we implement strict mode will change to accommodate these additions. We propose the following:

1. Change the Rust code to implement strict mode by reusing the logic of permissive mode​ and using a flag to perform more restrictive checks. For example, when given `User` and `Admin` entity types, the code performing the least-upper-bound computation will return union type `User|Admin` in permissive mode, and will fail in strict mode. And, the code for conditionals would force branches' types to match in strict mode, but not in permissive mode. Etc.
2. When checking in strict mode, we construct a new AST that performs the needed transformations, as in step 2 today.
3. Either way, we can add type annotations. For strict mode, they could be added during the transformation; for permissive mode, no transformation is needed. No checking is done after annotations are added, since the checking is always done, regardless of mode, prior to the transformation.

### Actions

Permissive mode validation considers different `Action`s to have distinct types, e.g., `Action::"view"` and `Action::"update"` don't have the same type. This is in anticipation of supporting distinct actions having distinct attribute sets. Today, the least upper bound of any two actions is the type _AnyEntity_, which is a general supertype of all entities, used internally. Such a type supports expressions that are found in the policy scope such as `action in [Action::"view", Action::"edit"]`. This expression typechecks because the least upper bound of `Action::"view"` and `Action::"edit"` is _AnyEntity_ so the expression is type `Set<`_AnyEntity_`>`.
However, these are different types which may have different attributes, so we need width subtyping to define an upper bound, but width subtyping is not supported by strict validation.

We will resolve this issue by making all `Action` entities of a particular action entity type have the same type in both strict and permissive validation.
Actions having the same type would need to have the same attributes record type.
If the actions have the same type, then strict mode validation can let different actions occur in the same set.
Since actions do not _currently_ have attributes, this does not effect permissive policy typechecking today.
The restriction is that it would not be possible to declare one action with an attribute `{"foo": 1}` while another action has an attribute `{"foo": false}`

### Template slots

There are no restrictions on what entity type can be used to instantiate a slot in a template, so the permissive typechecker also uses `AnyEntity` here.
The only restriction on the type of a slot is that it must be instantiated with an entity type that exists in the schema.
Based on this, we will modify both permissive and strict validation to precisely typecheck a template by extending the query type environment to include a type environment for template slots.
In the same way that we typecheck a policy once for each possible binding for the types of `principal`, `action`, and `resource`, we will also typecheck a template once for every possible binding for the type of any slots in that template.

Typechecking for every entity type may seem excessive,
but we know that a template slot can only occur in an `==` or `in` expression in the policy scope where the `principal` or `resource` is compared to the slot.
We will infer the type `False` for these expression if the slot is an entity type that cannot be `==` or `in` the principal or resource entity type, short-circuiting the rest of typechecking for that type environment.
Typechecking could be optimized by recognizing and ignoring type environments that will be `False` based only on the policy scope.

For example, using the schema from the motivating example, the following template will typecheck.

```
permit(principal == ?principal, action == Action::"read", resource);
```

Using the usual request type environment construction, there is one environment `(User, Action::"read", Object)`.
Because this is a template containing `?principal`, we extend the environment with each possible type for the slot: `User`, `Org`, `Admin` and `Object`.
When typechecking, the validator sees `principal == ?principal && ...` first in every environment which is always an equality between two entity types.
The `principal` is always a `User` while `?principal` is one of the possible slot types depending on the type environment.
In every environment where `?principal` is not `User`, the equality has type `False`, causing the `&&` to short-circuit to type `False`,
The rest of the policy is typechecked as usual when `?principal` is `User`.

This change to template typechecking does not introduce any new type errors and in fact will enable more precise typechecking if we expand where in a policy template slots may be used.

### Unspecified principal/resource entity types

The validator has a concept of an unspecified principal or resource entity type in an action `appliesTo` specification.
When `principalTypes` or `resourceTypes` is omitted, we interpret the schema as declaring that the action does not apply to any particular principal/resource entity type.
It instead applies to the "unspecified" principal or resource, which allows a users to make authorization requests using that action without providing the principal or resource,
or when providing an entity with any of the defined entity types as the principal or resource.
This is implemented by assigning the `AnyEntity` type to a variable when it is unspecified,
but this depends on width subtyping between entity types which we want to eliminate from strict validation.

It is not possible to extend the set of type environments to handle this case in a way that does not use `AnyEntity`.
Constructing one type environment for each declared entity type does not soundly handle the case where an entity is _not_ provided in the query.
If some attribute exists for every declared entity type, then an access to that attribute would be permitted, but that attribute cannot be safely accessed if an entity is not used in the query.
We would need to further extend set of type environments to include an entity representing this case,
but, other than `AnyEntity`, we do not have a type that can represent the type of an unspecified entity.

Instead, we observe that the existence of `AnyEntity` on it's own is not a problem for strict validation,
so we _can_ in fact use it as the type of an unspecified entity in strict mode validation.
The `AnyEntity` type is only a problem when it allows for construction of a union type representing multiple entity types.
We want to typecheck the policy with a distinct type environment for every entity type and for an unspecified entity.
For each query environment, we can over-approximate by instead using `AnyEntity` as the type of the query variable.
In each query environment, `AnyEntity` represents exactly one entity type,
and will always represent exactly one entity type as long as the least upper bound of `AnyEntity` with every type is not defined.

If we approximate every type environment with `AnyEntity`, the different type environments are now identical, so we only need to typecheck once with this approximate type environment.
Using the `AnyEntity` types will cause the strict-mode validator to reject some expressions which might otherwise be well typed.
For example, `principal == User::"alice"` is well typed when `principal` is `User`, and for any other entity type for `principal`, including the unspecified entity type, the expression could have type `False`, but we will not accept it.
This is an acceptable for unspecified entities because we do not believe policies should in general be doing comparison with unspecified entities.
Of course, these comparisons are still supported by the permissive mode validator.
This same tradeoff is not acceptable for template slots: `principal == ?principal` must be accepted by the strict mode validator.

## Drawbacks

The main drawback of this approach is that strict-mode validation will be more restrictive. This is by design: Policies like the one in the motivating example will be rejected where before they were accepted. Accepting this RFC means we are prioritizing understandability over precision under the assumption that the lost precision will not be missed (e.g., since users wouldn't have expected to get it anyway).

A secondary drawback is that this will result in a non-trivial, and backwards-incompatible code change.

## Alternatives

The proposal is, we believe, the minimal change to make strict mode self-contained, but not too different from what was there before. It also should not result in pervasive changes to the existing code. Alternative designs we considered (e.g., allowing more permissive mode features in strict mode) would be more invasive.
