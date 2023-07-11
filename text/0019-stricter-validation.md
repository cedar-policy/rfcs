# RFC Template (Fill in your title here)

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

Consider this policy, given in file [`policy.cedar`](policy.cedar), where `principal` is always of type `User`:
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
If we validate this policy against the schema [`schema.cedarschema.json`](schema.cedarschema.json), then `resource.owner` is always of type `User`. As a result, the policy is rejected by strict-mode validation, with two errors:
1. the `if`/`then`/`else` is trying to return entity type `Admin` in the true branch, and entity type `User` on the false branch, and these two are not equal.
1. since `resource.owner` has type `User`, it will have a type different than that returned by the `if`/`then`/`else`, which can sometimes return `Admin`.

But if we change `"User"` in [`schema.cedarschema.json`](schema.cedarschema.json) on line 13 to `"Org"`, then `resource.owner` is always of type `Org`. As a result, the policy is accepted! The two error conditions given above seem not to have changed -- the conditional returns different types, and those types may not equal the type of `resource.owner` -- so it's puzzling what changed to make the policy acceptable.

The reason is that strict-mode validation is dependent on permissive-mode validation. In particular, strict-mode validation is implemented in three steps: 1/ validate and transform the policy using permissive mode; 2/ annotate the transformed policy AST with types; and 3/ check the types against more restrictive rules.

In the first case, when `resource.owner` is always of type `User`, the expression `(if ...) == resource.owner` has type `Boolean` in permissive mode and as a result no transformation takes place in step 1. As a result, it is rejected in step 3 due to the errors given above.

In the second case (after we change the schema), `resource.owner` is always of type `Org`. Under permissive mode, the `(if ...) == resource.owner` expression has singleton type `False`. That’s because the `(if ...)` expression has type `User|Admin` ("`User` or `Admin`") and `User|Admin` entities can never be equal to `Org` entities. Both the _singleton type_ `False` (which only validates an expression that _always_ evaluates to `false`) and _union types_ like `User|Admin` are features of permissive mode and are not present in strict mode. Because of these features, step 1 will replace the `False`-typed `(if ...) == resource.owner` with value `false`, transforming the policy to be `permit(principal,action,resource) when { false || resource.isPublic }`. Since this policy does not require union types and otherwise meets strict mode restrictions, it is accepted in step 3.

In sum: To see why the second case is acceptable, we have to understand the interaction between permissive mode and strict mode. This is subtle and difficult to explain. Instead, we want to implement strict mode as a standalone feature, which does not depend on features only present in permissive mode.

## Detailed design

We propose to change strict-mode validation so that it has the following features taken from permissive mode:
* singleton boolean `True`/`False` types (which have 1/ special consideration of them with `&&`, `||`, and conditionals, and 2/ subtyping between them and `Boolean`, as is done now for permissive mode).
* depth subtyping, but not width subtyping, to support examples like `{ foo: True } <: { foo: bool }`.
* a requirement that arguments to `==` have the same type _unless_ we know that comparison will always be false, in which case we can give the `==` type `False`. The same goes for `contains`, `containsAll`, and other constructs that use `==` under the covers.
* a requirement that branches of a conditional have the same type _unless_ we can simplify the conditional due to the guard having a `True`/`False` type.
* (no union types)

The current way we implement strict mode will change to accommodate these additions. We propose the following:

1. Change the Rust code to implement strict mode by reusing the logic of permissive mode​ and using a flag to perform more restrictive checks. For example, when given `User` and `Admin` entity types, the code performing the least-upper-bound computation will return union type `User|Admin` in permissive mode, and will fail in strict mode. And, the code for conditionals would force branches' types to match in strict mode, but not in permissive mode. Etc.
2. When checking in strict mode, we construct a new AST that performs the needed transformations, as in step 2 today. 
3. Either way, we can add type annotations. For strict mode, they could be added during the transformation; for permissive mode, no transformation is needed. No checking is done after annotations are added, since the checking is always done, regardless of mode, prior to the transformation.

Permissive mode validation considers different `Action`s to have distinct types, e.g., `Action::"view"` and `Action::"update"` don't have the same type. This is in anticipation supporting distinct actions having distinct attribute sets. Today, the least upper bound of any two actions is the type _AnyEntity_, which is a general supertype of all entities, used internally. Such a type supports expressions that are found in the policy scope such as `action in [Action::"view", Action::"edit"]`. This expression typechecks because the least upper bound of `Action::"view"` and `Action::"edit"` is _AnyEntity_ so the expression is type `Set<`_AnyEntity_`>`. Therefore in our amended strict mode we either need to:
1. Support _AnyEntity_ as part of depth subtyping.
2. Stop giving different `Action` entities different types, and if/when they support `Action` attributes we force them to share the same overall type (using optional attributes where different actions differ).

## Drawbacks

The main drawback of this approach is that strict-mode validation will be more restrictive. This is by design: Policies like the one in the motivating example will be rejected where before they were accepted. Accepting this RFC means we are prioritizing understandability over precision under the assumption that the lost precision will not be missed (e.g., since users wouldn't have expected to get it anyway).

A secondary drawback is that this will result in a non-trivial, and backwards-incompatible code change.

## Alternatives

The proposal is, we believe, the minimal change to make strict mode self-contained, but not too different from what was there before. It also should not result in pervasive changes to the existing code. Alternative designs we considered (e.g., allowing more permissive mode features in strict mode) would be more invasive.

## Unresolved questions

See the discussion above about sets of `Action` entities.