# Guard Arithmetic Expressions within Policies

## Related issues and PRs

- Reference Issues: No existing issue, but supersedes https://github.com/cedar-policy/rfcs/pull/36
- Implementation PR(s): (Existing PR for range analysis based on schema: https://github.com/cedar-policy/cedar/pull/56)

## Timeline

- Started: 2023-11-07

## Summary

We will use a range analysis (as in https://github.com/cedar-policy/cedar/pull/56) but with the bounds given in the policy rather than in the schema.

## Motivation

Arithmetic with bounded integers is a common source of bugs [https://blog.research.google/2006/06/extra-extra-read-all-about-it-nearly.html]. Consider the following policy:

```
forbid(principal, action, resource) when {
   principal.elevated_privileges_end_time_s * 1000 > context.current_time_ms ||
   !principal.is_mfa
};
```

A casual reader of this policy may conclude that all actions are forbiden when `principal.mfa` is `false`. This is wrong. The lhs (`principal.elevated_privileges_end_time_s * 1000 > context.current_time_ms`) is evaluated first and if it errors the entire policy is skipped.

To avoid this class of mistakes, we want to change Cedar's validator to error on arithmetic expressions that could overflow. To pass validation, arithmetic should be guarded. For example, the above policy should be written:

```
forbid(principal, action, resource) when {
   (principal.elevated_privileges_end_time_s < i64::MAX / 1000 &&
    principal.elevated_privileges_end_time_s > i64::MIN / 1000 &&
    principal.elevated_privileges_end_time_s * 1000 > context.current_time_ms) ||
   !principal.is_mfa
};
```

## Detailed design

Every non-identity preserving arithmetic operation should be guarded by comparisons that prevent over/underflow.

- We add intervals to represent the ranges of each integer.
- Integers without explicit intervals are assumed to lie in `[i64::MIN, i64::MAX]` so almost any arithmetic operation on them will be a validation error.
- We use interval arithmetic, which is imprecise, but because the bounds are written in the policy, the intervals can be precisely given at the point of each operation.


## Drawbacks

The policies that use arithmetic and will pass validation are ugly.

We assume almost no one uses arithmetic, so we think this is an acceptable tradeoff. If there are significant uses of arithmetic, a better approach is likely desirable.

## Alternatives

### Unbounded Integers
Unclear how these will affect our FFI. We can take this proposal now and switch to unbounded ints later more easily than we can switch now and reverse that decision later.

### Bounds in the schema.
It is not clear how to analyze a set with members of an EntityType that has an integer attribute with bounds while keeping analysis sound, complete and decidable. Consider

```
MyEntityType1: [{i: Long [-10,10]}]
MyEntityType2: [{set_of_my_entities: Set<MyEntityType1>}]
```
and the policy:
```
permit(principal is MyEntityType2, action, resource) when {
    principal.set_of_my_entities.contains(resource.foo) && resource.foo.i > 1000
};
```
Analysis should encode that no entity in `MyEntityType2.set_of_my_entities` has an attribute `i` outside the range `[-10,10]`.


### Status quo
See the downside in the motivation.

### Less general range analysis
Unlike https://github.com/cedar-policy/cedar/pull/56, because we're putting bounds in the policies, we could require explicit bounds for each arithmetic operation.

So
```
(if principal.a < 9,223,372,036,854,774 && principal.a > -9,223,372,036,854,774 then principal.a * 1000 else 0) * 500 > foo
```
would require new bounds:

```
principal.a * 1000 + 500 < i64::MAX && (if principal.a < 9,223,372,036,854,774 && principal.a > -9,223,372,036,854,774 then principal.a * 1000 else 0) + 500 > foo
```
Requiring bounds for each operation would be easier to implement, but much more annoying to use if anyone uses chained arithmetic operations.

## Unresolved questions

What should the validation error messages look like? Can we suggest bounds that will look more reasonable in policies than `principal.a < 9,223,372,036,854,774 && principal.a > -9,223,372,036,854,774 && ...`?