# Standalone strict validation

## Related issues and PRs

- Reference Issues:
- Implementation PR(s): https://github.com/cedar-policy/cedar/pull/282 and https://github.com/cedar-policy/cedar-spec/pull/111

## Timeline

- Start Date: 2023-07-11
- Date Entered FCP: 2023-08-18
- Date Accepted: 2023-08-18
- Date Landed: 2023-09-08 on `main`

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
* Depth subtyping, but not width subtyping, to support examples like `{ foo: True } <: { foo: Boolean }`.

Strict-mode validation will continue to apply the restriction it currently applies:
* Arguments to `==` must have the compatibles types (i.e., an upper bound exists according to the strict - depth only - definitions of subtyping) _unless_ we know that comparison will always be false, in which case we can give the `==` type `False`. The same goes for `contains`, `containsAll`, and `containsAny`.
* Arguments to an `in` expression must be compatible with the entity type hierarchy, or we must know that the comparison is always false.
* Branches of a conditional must have compatible types _unless_ we can simplify the conditional due to the guard having a `True`/`False` type.
* The elements of a set must have compatible types.
* As a consequence of the two prior restrictions, union types cannot be constructed.
* Empty set literals may not exist in a policy because we do not currently infer the type of the elements of an empty set.
* Extension type constructors may only be applied to literals.

Validating `Action` entities and template slots `?principal` and `?resource` must be done differently so as not to rely on the "top" entity type _AnyEntity_, which is essentially an infinite-width union type, used internally.
Next, we describe how we propose to handle these situations, in both permissive and strict validation.
Importantly, these changes all retain or even _improve_ precision compared to the status quo -- they will _not_ be the reason that policies that typechecked under the old strict mode no longer do.

### Actions

Permissive mode validation considers different `Action`s to have distinct types, e.g., `Action::"view"` and `Action::"update"` don't have the same type.
This is in anticipation of supporting distinct actions having distinct attribute sets.
The least upper bound of any two actions is the type _AnyEntity_.
Such a type supports expressions that are found in the policy scope such as `action in [Action::"view", Action::"edit"]`.
This expression typechecks because the least upper bound of `Action::"view"` and `Action::"edit"` is _AnyEntity_ so the expression is type `Set<`_AnyEntity_`>`.
Since _AnyEntity_ cannot be used in strict validation, the current code special-cases the above expression, treating it as equivalent to `action in Action::"view" || action in Action::"edit"`.
However, this approach is unsatisfying as it only supports literal sets of `Action` entities.

It turns out we can resolve this issue by making all `Action` entities have one type -- `Action` -- in both strict and permissive validation.
This change strictly _adds_ precision to validation, compared to the status quo.
Expressions like `[Action::"view", Action::"edit"]` have type `Set<Action>` and thus do not need _AnyEntity_ to be well-typed.
Expressions like `if principal.isAdmin then Action::"edit" else Action::"editLimited"` will typecheck in strict validation, since both branches have the same type (`Action`).

A possible drawback of this change is that it will not allow distinct actions to have distinct attribute sets (if indeed we add attributes to actions in the future).
Rather, all actions must be typeable with the same record type.
As a mitigation, for action entities that have an attribute that others do not, the attribute can be made optional.
However, two entities would not be able to have the same attribute at _different_ types, e.g., `{ foo: String }` vs. `{ foo: Long }`.
Arguably, this restriction is clearer and more intuitive than what would have been allowed before.

### Template slots

There are no restrictions on what entity type can be used to instantiate a slot in a template, so the permissive typechecker also uses _AnyEntity_ here.
The only restriction on the type of a slot is that it must be instantiated with an entity type that exists in the schema.
The strict validator today does not properly support validating templates, which is something we want to allow.

Because _AnyEntity_ cannot be used in strict validation, we will modify both permissive and strict validation to precisely typecheck a template by extending the query type environment to include a type environment for template slots.
Doing so will strictly _improve_ precision for permissive validation; all templates that validated before will still do so after this change.

Here is how the change will work.
In the same way that we typecheck a policy once for each possible binding for the types of `principal` and `resource` for a given action, we will also typecheck a template once for every possible binding for the type of any slots in that template.

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
In every environment where `?principal` is not `User`, the equality has type `False`, causing the `&&` to short-circuit to type `False`.
The rest of the policy is typechecked as usual when `?principal` is `User`.

This change will match the precision of the validator today, and will enable more precise typechecking if we expand where in a policy template slots may be used.
In particular, if we allowed expressions like `?principal.foo == 2` in the condition of a policy, the above approach would allow us to know precisely that `?principal` will always have a `foo` attribute, whereas the current approach using _AnyEntity_ would not be able to.

### Implementation details

The current way we implement strict mode will change to accommodate these additions. We propose the following:

1. Change the Rust code to implement strict mode by reusing the logic of permissive mode​ and using a flag to perform more restrictive checks. For example, when given `User` and `Admin` entity types, the code performing the least-upper-bound computation will return union type `User|Admin` in permissive mode, and will fail in strict mode. And, the code for conditionals would force branches' types to match in strict mode, but not in permissive mode. Etc.
2. When checking in strict mode, we construct a new AST that performs the needed transformations, as in step 2 today.
3. Either way, we can add type annotations. For strict mode, they could be added during the transformation; for permissive mode, no transformation is needed. No checking is done after annotations are added, since the checking is always done, regardless of mode, prior to the transformation.

## Drawbacks

The main drawback of this approach is that strict-mode validation will be more restrictive. This is by design: Policies like the one in the motivating example will be rejected where before they were accepted. Accepting this RFC means we are prioritizing understandability over precision under the assumption that the lost precision will not be missed.

Policies that validated before but will not validate now are quite odd -- they would rely on the use of width subtyping, unions, etc. to determine that an expression will always evaluate to `true` (or `false`) and thus can be transformed away. But policies like these will be like those in the motivating example at the start of this RFC, and are probably not what the user intended in the first place. Ultimately, flagging them as erroneous is safer.

A secondary drawback is that this change will result in a non-trivial, and backwards-incompatible code change.
Mitigating this issue is that the backward incompatibility will be minimal in practice (per the above), and we will use verification-guided development to prove that the change is sound (i.e., will not introduce design or implementation mistakes).

## Alternatives

The proposal is, we believe, the minimal change to make strict mode self-contained, but not too different from what was there before. It also should not result in pervasive changes to the existing code. Alternative designs we considered (e.g., allowing more permissive mode features in strict mode) would be more invasive.

## Updates

* 2023-11-07: The original text said that `AnyEntity` was used to type unspecified entities. This is not the case in any released version of Cedar -- instead unspecified entities are given a special `Unspecified` type. Updated text to reflect this.
