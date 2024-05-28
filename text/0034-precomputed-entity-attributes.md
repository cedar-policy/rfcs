# Precomputed Entity Attributes

## Related issues and PRs

- This RFC is mostly directly taken from [RFC 28](https://github.com/cedar-policy/rfcs/pull/28);
  it splits out the changes from RFC 28 that relate to precomputed entity
  attributes, without the larger changes in RFC 28 regarding `EntityDataSource`.
- This RFC is also the successor to [RFC 23](https://github.com/cedar-policy/rfcs/pull/23).
- Implementation PR: [cedar#430](https://github.com/cedar-policy/cedar/pull/430)

## Timeline

- Started: 2023-10-24 (predecessor [#28](https://github.com/cedar-policy/rfcs/pull/28) started on 2023-10-03, and predecessor [#23](https://github.com/cedar-policy/rfcs/pull/23) started on 2023-07-18)
- Accepted: 2023-11-14
- Landed: 2023-11-16 on `main`
- Released: 2023-12-15 in `cedar-policy` v3.0.0

## Summary

Internally, Cedar entity objects will store their attribute values as
precomputed `Value`s, rather than in `RestrictedExpression` form.
This entails some minor breaking changes to the Cedar public API, but provides
important efficiency gains.

## Motivation

1. Today, every `is_authorized()` request re-evaluates all of the attributes in the
`Entities`; they are stored as restricted expressions and evaluated to `Value`
on every call to `is_authorized()`. (See
[cedar#227](https://github.com/cedar-policy/cedar/issues/227).)
This is inefficient.

2. Today, `Entities::evaluate()` is implemented on `main` and provides a way to
mitigate this issue, but it is opt-in and we'd rather have it be the default
behavior.
Notably, as of this writing, `Entities::evaluate()` is not released yet, so we
can make changes in this area without breaking our users.

## Detailed design

This RFC has ~three~ two components: (a third component was severed and moved to
Alternative A after discussion)

### Component 1: Store attributes as precomputed `Value`s

We redefine `Entities` and `Entity` to hold attributes as `Value`s instead of as
restricted expressions.
This addresses the first point in [Motivation](#motivation).

This change is breaking for the public API in two (small) ways:
- `Entity::new()`, `Entities::from_json_*()`, and friends can take the same
inputs, but will need to sometimes return an evaluation error due to errors
evaluating the entity attributes (particularly, errors from evaluating extension
functions for attribute values of type `ipaddr` or `decimal`).
Today, `Entity::new()` never returns an error, and the `Entities` functions can
return `EntitiesError` but not an evaluation error.
- Conversely, `Entity::attr()` need not return an error anymore, as all of the
attributes will already be evaluated. (If we are very concerned about backward
compatibility, we could keep the current signature and just never return `Err`.
Currently, this RFC is proposing we change the signature to not contain
`Result`, since we're already making the related breaking change to
`Entity::new()`.)

Accepting these breaking changes allows us to give users the best-performing
behavior by default.
For alternatives that are less breaking, see [Alternatives](#alternatives).

### Component 2: Remove no-longer-necessary interface to precompute `Value`s

We remove `Entities::evaluate()`, as all `Entities` are now stored in their
evaluated form by default.
This addresses the second point in [Motivation](#motivation).

This is not a breaking change because `Entities::evaluate()` has not yet been
released in any Cedar release.

## Drawbacks

- This RFC represents some breaking changes for users upgrading to a new major
version of Cedar. All breaking changes come with some cost in terms of user
experience for existing users. This RFC contends that the benefit outweighs the
cost in this case.

## Alternatives

### Alternative A

In addition to what is currently proposed in this RFC, we could add the
following change, allowing users to construct entities using precomputed
`Value`s.

__Motivation__

Today, `Entity::new()` requires callers to pass in attribute values as
`RestrictedExpression`.
For some callers, evaluating these `RestrictedExpression`s is an unnecessary
source of runtime evaluation errors (and performance overhead).

__Detailed design__

We add new constructors for `Entities` and `Entity` which take `Value`s
instead of `RestrictedExpression`s.
These constructors would work without throwing evaluation errors, in contrast to
the existing constructors after the changes described in the main part of this
RFC.

This change requires that we expose `Value` in our public API in some manner
(probably via a wrapper around the Core implementation, as we do for many other
Core types).
Note that today, `EvalResult` plays the role of `Value` in our public API, but
conversion between `EvalResult` and `Value` is relatively expensive (`O(n)`).
We could either:

- expose `Value` but leave `EvalResult` alone. This provides maximum backwards
compatibility, but might cause confusion, as `Value` and `EvalResult`
would be conceptually similar, but slightly different and not interchangeable.
- consolidate `EvalResult` and `Value` into a single representation, called
`Value` and based on the Core `Value`. This provides maximum API cleanliness
but requires the most breaking changes.
- expose `Value`, but keep `EvalResult` as a type synonym for `Value`. This
is almost the same as the above option, but keeps the `EvalResult` type name
around, even though it makes breaking changes to the structure of
`EvalResult`. This might reduce confusion for users who are migrating, as
they only have to adapt to the changes to `EvalResult` and not rename
`EvalResult` to `Value` in their own code; but, it might increase confusion
for future users, who will see two names for the same thing.
- not expose `Value` and just use `EvalResult`, even in the new constructors.
This provides maximum backwards compatibility, like the first option, and
also avoids the possible confusion generated by the first option, but comes
at a notable performance cost (due to the inefficient
`EvalResult`-to-`Value` conversion required under the hood) and might
generate a different kind of confusion as `EvalResult` is an awkward name in
the context of these constructors.

__Commentary__

The sub-proposal in this alternative is severable and could be its own RFC, or
perhaps a change that doesn't rise to the level of requiring an RFC.
We have the freedom to do it any time in the future (after the rest of the RFC
is accepted and implemented) if we don't want to do it now.

@mwhicks1 opinion, which I tend to agree with, is that this alternative is
probably more trouble than it's worth -- that it provides only marginal benefit
to users at the cost of cluttering our API, both with additional constructors,
and with the public `Value` type.

If we don't take this alternative, users will have to still construct `Entity`
and `Entities` via restricted expressions, using constructors which can throw
errors.
But, we would be able to avoid having to expose `Value` or make changes to
`EvalResult`, at least for now.

### Alternative B

In addition to what is currently proposed in the current RFC, we could provide
the status-quo definitions of `Entities` and `Entity` under new names: e.g.,
`UnevaluatedEntities` and `UnevaluatedEntity` (naming of course TBD).
This is very unlikely to be of any use to new users, but existing users really
wanting the old error behavior could use these types and functions instead of
`Entities` and `Entity`.

To me, this provides little benefit, at the expense of more confusion and more
APIs to maintain. It also doesn't make any of the changes more back-compatible;
for users, migrating their code to use these renamed types and functions may be
just as much work as adopting the actual breaking changes proposed in this RFC.

### Alternative C

Instead of changing `Entities` and `Entity` as suggested in the current RFC, we
could provide new versions of these types -- say, `EvaluatedEntities` and
`EvaluatedEntity` -- which have the behaviors proposed in the current RFC.  This
avoids making any breaking changes to existing types and functions.

The downsides of this alternative include:
- Existing users don't get the improved performance by default (see
[Motivation](#motivation)). They have to opt-in by migrating their code to these
new types and functions.
- Whether or not we officially deprecate the existing `Entities` and `Entity`,
new users may incorrectly assume that they should default to using those types,
as they have the most-intuitive / least-qualified names, and types like
`EvaluatedEntities` might appear to be for special cases.
- If we do not officially deprecate the existing `Entities` and `Entity`, we are
stuck maintaining more APIs indefinitely. These APIs are also somewhat redundant
and provide multiple ways to do approximately the same thing, some more
optimally than others.
- If we do officially deprecate the existing `Entities` and `Entity` we end up
in a final state where we only have `EvaluatedEntities` and no other kind of
`Entities`, which is a kinda ugly and nonsensical API from a naming standpoint
-- not aesthetically pleasing.
