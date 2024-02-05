# Make `==` and `in` on `Unspecified` to be errors

## Related issues and PRs

- Reference Issues: [cedar#217](https://github.com/cedar-policy/cedar/issues/217)
- Implementation PR(s):

## Timeline

- Started: 2024-02-05

## Summary

The `==` and `in` operations will always produce errors when applied to
`Unspecified` entities. This replaces the current behavior, which produces
errors in some cases, `true` in other cases, and `false` in other cases.

## Basic example

Cedar's API allows you to leave the principal, action, or resource of a request
unspecified, indicating that the principal, action, or resource "shouldn't
matter" for any policy evaluation.
Suppose `principal` is left unspecified in a request.

1. If some policy contains the expression `principal == User::"alice"` or
`User::"alice" == principal`, those expressions currently (Cedar 2.x and 3.x)
evaluate to `false` -- unspecified entities are defined to not be equal to any
entity in the hierarchy.
2. If some policy contains the expression `principal in Group::"foo"` or
`User::"alice" in principal`, those expressions currently (Cedar 2.x and 3.x)
evaluate to `false` -- unspecified entities are defined to not be `in` any
entity in the hierarchy.
3. If some policy contains the expression `principal == principal` or
`principal in principal`, those expressions currently (Cedar 2.x and 3.x)
evaluate to `true` (even when `principal` is unspecified in the request).
Unspecified entities are defined to be equal to themselves.
4. If some policy contains the expression `principal has foo` or
`principal is Foo`, that expression currently (Cedar 2.x and 3.x) evaluates to
`false` -- unspecified entities are defined to have no attributes, and their
entity type cannot be written in a policy.
5. If some policy contains the expression `principal.foo`, that expression
currently throws an error.

With this RFC, we change the behavior to be consistent: _All_ of the above
examples will throw an error.

## Motivation

The behavior of unspecified entities is complicated, unintuitive, and has to
be special-cased frequently in the validator.  Even we, as Cedar developers, are
often confused or tripped up by the semantics of `Unspecified`.
The distinction between unspecified entities and partial-evaluation unknowns is
also subtle and confusing and has caused bugs.

The proposed semantics is more consistent for Cedar users, as outlined above in
"Basic example", and hopefully also more intuitive for users (reduce surprises).
The original intended use-case for `Unspecified` was that a caller who leaves a
variable (say `principal`) unspecified, is implicitly guaranteeing that
`principal` does not matter to the authorization outcome (e.g., because no
policies check `principal`).
This RFC's proposed semantics is more true to this intended use-case than the
current semantics.

Additionally, the proposed semantics will allow us to simplify Cedar's
implementation by unifying the behavior of `Unspecified` and `Unknown` in many
ways, allowing us to share code for these two features.

## Detailed design

### Semantics

The detailed semantics is clear and simple: if `principal` (resp. `action` or
`resource`) is Unspecified in the request, it is an evaluation error for
`principal` (resp. `action` or `resource`) to appear in any (evaluated)
expression in the policy.
(The scope constraints `principal,` `action,` and `resource,` are always still
allowed of course.)

From the evaluator perspective, we must still allow unspecified variables to
appear in unevaluated/dead code, because the evaluator simply does not evaluate
those expressions due to short-circuiting; but despite this, validator can still
soundly prohibit these variables in all expressions in the policy.

### Implementation

Under the hood, we can implement this cleanly and simply in the evaluator by
simply setting unspecified variables to `Unknown`, evaluating the policies using
the partial evaluator, and then returning an error if any evaluation resulted in
a residual.

This means that `Unspecified` and `Unknown` are handled the same way and have
the same semantics (except that for `Unspecified`, residuals are converted to
errors before being returned to the user).
Many parts of the implementation would no longer need to distinguish between
`Unspecified` and `Unknown`, and in fact, the evaluator code would be fully
shared.

In the validator, this change will allow us to remove many existing special-cases
for handling `Unspecified`.
For instance, typechecking `<unspecified> in [A, B, C]` today requires reasoning
about A, B, and C -- if any of them are or could be `Unspecified` themselves,
then the expression has type `Bool` (because two `Unspecified` entities may or
may not be equal: `principal == principal` is true, but `principal == resource`
is not), but if A, B, and C must all be specified entities, then the expression
has type `False`.
With this RFC's change, this expression is simply an error regardless of what A,
B, and C are.

### Interaction with partial evaluation

TBD; see "Unresolved questions" below

## Drawbacks

Why should we *not* do this?

- This is a breaking change.
  Breaking changes are inconvenient for our users and make it difficult for
  them to stay on the latest version of Cedar.
  We don't want to make breaking changes lightly, and arguably, this change
  might not be important enough to justify a breaking change.
  However, this change can probably be ignored by most Cedar users.
  We assume that most users who actually use `Unspecified` (which is probably a
  small minority already?) use it for its originally intended use-case (see
  Motivation), and thus do not rely on `==`, `in`, or `has` operations on those
  unspecified entities. This means that changing the behavior of `==`, `in`, and
  `has` on unspecified entities has no effect on these users. However, see the
  next bullet.
- Some users might be currently using unspecified-principal to mean something
  like "unauthenticated user" rather than for its originally intended meaning,
  which is that `principal` doesn't matter to the policy evaluation.
  This RFC's semantics change would prohibit this use case, and require those
  Cedar users to instead create a special entity like `Unauthenticated::""` to
  represent the unauthenticated user.
  Arguably, an explicit `Unauthenticated` principal is a best-practice anyway,
  but this RFC would still represent an annoying breaking change for any users
  currently using `Unspecified` this way.
- If we go through with [cedar#590](https://github.com/cedar-policy/cedar/pull/590)
  and fully separate concrete from partial evaluation, that reduces the benefit
  of this RFC from an implementation standpoint.
  If we still wanted to share the code for processing `Unspecified` and
  `Unknown` in the evaluator, we would have any requests containing
  `Unspecified` go though the partial-evaluation path, and all other non-partial
  requests go through the concrete-evaluation path.
  This is somewhat undesirable as it might be a footgun to have those categories
  of requests handled differently.

## Alternatives

### Alternative A: Just remove `Unspecified`

`Unspecified` is arguably an anti-pattern with few use cases.
Cedar users can always make things more explicit by creating "dummy" entities
like `Unauthenticated::""` or `DontCare::""` instead of using unspecified
principal, and likewise for action and resource.
Arguably, this is a best practice, and makes the resulting Cedar policies and
schemas easier to read and reason about.
We could remove `Unspecified` entirely in a future Cedar major version, instead
of making breaking changes to its behavior (as currently proposed in this RFC).

This alternative would be a breaking change for a larger class of users than
the main proposal.
Specifically, this alternative would additionally break users who are currently
genuinely using `Unspecified` to mean "shouldn't matter", as originally intended.
Those users will have to create dummy entities as described above.

## Unresolved questions

- How should `Unspecified` interact with partial evaluation? If the user leaves
  `principal` unknown for partial evaluation, should `Unspecified` be an implicit
  possibility for the value of `principal`, or not? Do we even allow users to use
  these features simultaneously? For the same variable? For different variables?
- If we go through with [cedar#590](https://github.com/cedar-policy/cedar/pull/590)
  and fully separate concrete from partial evaluation, that reduces the benefit
  of this RFC from an implementation standpoint, as discussed under Drawbacks above.
  This is currently unresolved.
  (Perhaps this RFC provides an argument for rejecting cedar#590; or, perhaps
  cedar#590 provides an argument in favor of this RFC's Alternative A rather
  than its main proposal.)
