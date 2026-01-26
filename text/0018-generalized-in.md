# Generalized `in` operator

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started: 2023-07-11
- Archived: 2023-12-14
- Entered FCP:
- Accepted:
- Landed:

## Summary

Allow `in` to be used for set membership, not just hierarchy membership. In particular, allow it to be used with non-entity-typed values on the LHS. The detailed design of this proposal (see below) ensures that back-compatibility is maintained for all existing valid Cedar policies.

Note (2023-12-14): This RFC has been "archived" in the sense that it doesn't currently have much support, but also we're open to resuming the discussion on it at any time. Feel free to leave a comment and resume the discussion. But in absence of any activity or popular demand, the Cedar team does not plan to take any action on this RFC in the near future.

## Basic examples

### Example 1
Today's Cedar:
```
permit(principal, action == Action::"view", resource == Document::"mine.doc")
when {
    ["sales", "legal"].contains(principal.department)
};
```

Proposed:
```
permit(principal, action == Action::"view", resource == Document::"mine.doc")
when {
    principal.department in ["sales", "legal"]
};
```

### Example 2
Today's Cedar:
```
permit(
    principal == Principal::"long-uuid-here",
    action == Action::"view",
    resource in Database::"prod"
) when {
    resource has tags
        && resource.tags has tagA
        && ["value1", "value2"].contains(resource.tags.tagA)
};
```

Proposed:
```
permit(
    principal == Principal::"long-uuid-here",
    action == Action::"view",
    resource in Database::"prod"
) when {
    resource has tags
        && resource.tags has tagA
        && resource.tags.tagA in ["value1", "value2"]
};
```

## Motivation

In today's Cedar, `.contains()` is the only way to check set membership. There are two problems with this:
1. This is simply awkward in some use cases, such as the two examples above. Subjectively, the `.contains()` syntax is hard to read in these cases, because the set is required to be on the LHS and the value you're actually interested in is required to be on the RHS. In these examples, having the set on the RHS instead of the LHS reads more intuitively.
2. Anecdotally, many users intuitively expect that `in` can be used for set membership and not just hierarchy membership, and are confused when this results in Cedar type errors. See, for example, [this thread](https://cedar-policy.slack.com/archives/C0547KH7R19/p1689253188448809) on the Cedar Slack.

## Detailed design

Cedar's existing `in` keyword is extended to also work for set membership, in a way that is back-compatible with the current semantics. Recall the current semantics of `in`:

* `principal.manager in Group::"A"`

This is true if `principal.manager` is a member of `Group::"A"`.

* `principal.manager in [Group::"A", Group::"B"]`

This is true if `principal.manager` is a member of either group. Equivalent to `principal.manager in Group::"A" || principal.manager in Group::"B"`.

This has been referred to as the "deep" semantics of `in` -- the `x in [A, B]` form doesn't just check if `x` is equal to `A` or `B`, but (recursively) if `x` is a member of `A` or `B` in the hierarchy.

In contrast, set membership is inherently shallow. If `in` was naively adapted to support set membership, the above example would be ambiguous: did the policy author mean set membership (in which case they're intending `principal.manager == Group::"A" || principal.manager == Group::"B"`), or today's Cedar's deep hierarchy membership (with the semantics above)?

This RFC proposes to combine these two semantics in a back-compatible way.
Informally, `in` is "deep" for entity elements, and shallow for non-entity elements.
More formally, the semantics of `a in B` is:
* if `a` and `B` are both entity references, then `true` if `a` is either equal to `B`, or a descendant of `B` in the hierarchy, else `false`
    * this is not changed from today's Cedar
* if `B` is a Cedar set and `a` is not an entity reference, then it's ordinary shallow set membership, i.e., equivalent to `B.contains(a)`
    * this case is a type error in today's Cedar
* if `B` is a Cedar set and `a` is an entity reference, then WLOG let `B` be `[B1, B2, B3]`. The semantics of `a in [B1, B2, B3]` is `a op B1 || a op B2 || a op B3` where for each `Bx`, if `Bx` is an entity reference then `op` is `in`, otherwise `op` is `==`
    * in the case where `B` only contains entity references, this behavior matches today's Cedar
    * in the case where `B` contains other values, this would be a type error in today's Cedar
* in all other cases, type error
    * this is not changed from today's Cedar

Here's one additional example (we'll call it Example 3):
```
resource.owner in ["foo", "bar", User::"Group"]
```
Under this proposal, this expression is `true` if `resource.owner` is the string `"foo"`, the string `"bar"`, the entity reference `User::"Group"`, or any entity reference which is `in` `User::"Group"`.

Arguably, this is the "intuitive" semantics that users want for `in` -- it blends "deep" `in` for entity references while also providing shallow set-membership for sets.

One final note -- this RFC does not propose any changes to what syntax is legal in the policy scope. And of course, it doesn't change the behavior of any syntax that's currently legal in the policy scope.

## Drawbacks

- The new semantics is more complicated than Cedar's current semantics for `in`. This could lead to additional confusion. The current semantics may lead to some confusion as well, but that has been significantly ameliorated with better error messages (see [cedar#177](https://github.com/cedar-policy/cedar/issues/177)).
- As currently proposed (i.e., unless we take alternative 5) `foo in ["Bar", "Baz"]` will have different semantics than `foo in [User::"Bar", User::"Baz"]`. If a user gets used to writing `in` for shallow set membership, they will likely be confused by our current semantics of `in` on sets of entities. For example, `"Foo" in ["Bar", "Baz"]` is trivially false, but `User::"Foo" in [User::"Bar", User::"Baz"]` could be true or false depending on the entity hierarchy.
- The new semantics doesn't provide a way to do shallow set membership with entity references; you will still need `.contains()` for that.
    - Response: Is there a real-world use case that needs shallow set membership with entity references?
- The new `in` is nearly redundant with `.contains()`. For ordinary set-membership with non-entities (as in both of the basic examples at the top), users would now have two different ways to do the same thing -- something we have previously said we want to generally avoid if possible.
    - Response: It seems valuable to have two ways to do set-membership, one with the set on the LHS and the other with the set on the RHS. Cedar already supports "flipped" versions of some operators, which are redundant except for switching their operands -- consider `<` and `>`.
- A final objection is simply that one of the Alternatives below might be better. See discussion below.

## Alternatives

Several alternatives are listed here, in some cases just to explain why we aren't considering them.
The only alternatives from this list that have received any support (as of this writing) are Alternative 1 and Alternative 5.

### Alternative 1: Do nothing (status quo)

The Motivation section above explains why this is undesirable.
However, point (2) in the motivation section has been partially addressed with better error messages (see [cedar#177](https://github.com/cedar-policy/cedar/issues/177)).

### Alternative 2: remove `.contains()`

In addition to everything else proposed in this RFC, we could _also_ remove `.contains()` from the Cedar language.

This would be a breaking change, whereas the RFC as-is is not a breaking change.

I hypothesize that just as our examples above read better with the set on the RHS, some other examples read better with the set on the LHS, so it makes sense to keep both operators.

Also, `.contains()` isn't fully redundant with the new `in`, and there are some things that could not be expressed if we removed it -- namely, shallow set membership with entity references.

Finally, `.contains()` has nice symmetry with `.containsAny()` and `.containsAll()`, and users might expect it given that Cedar has the latter two operators.

### Alternative 3: Use a different dedicated keyword instead of `in`

There are many possibilities for this keyword:
* `isElementOf`
* `elementOf`
* `element`
* `isInSet`
* `isIn`
* `inSet`
* `isOneOf`
* `oneOf`

but we'll use `inSet` in the following.

In this alternative, the first example would read `principal.department inSet ["sales", "legal"]`. The semantics of `a inSet B` would be identical to `B.contains(a)`. The semantics of `in` wouldn't change from today's Cedar.

Reasons not to take this alternative:
* The distinction between `in` and `inSet` could cause confusion
* Users may still reach for `in` for set-membership, as discussed in Motivation above

### Alternative 4: Method call instead of keyword

This is basically a variant of Alternative 3 where instead of `a inSet B` we write `a.inSet(B)`. It doesn't have fundamentally different pros/cons than Alternative 3 does, and it may cause additional confusion for users used to dynamic dispatch, e.g. because `.inSet()` would be a method implicitly defined on all possible types including all present and future extension types. It could also interact unfavorably with dynamic dispatch in Cedar if Cedar ever chooses to add dynamic dispatch itself. Alternative 3 seems better to me for those reasons.

### Alternative 5: `in` always means set-membership when RHS is a set

This would be a breaking change that changes the current meaning of `principal.manager in [Group::"A", Group::"B"]`. The resulting semantics would be simpler as a result, and Examples 1 and 2 would still look the same as in the main proposal.

In this alternative, `in` cannot be used for the current "deep" semantics.
Users would have a few alternatives if they did want the "deep" semantics:
* We could add a new keyword that has the current "deep" semantics -- say, `inAny`
* With [RFC 21], users can get the "deep" semantics with `.any(_ in it)` (although this has the set on the LHS, like `.contains()`)
* If the RHS is a literal, users could just write out `a in G1 || a in G2 || ...`. This doesn't help for the case where the RHS is not a literal, e.g. today's `User::"Henry" in resource.allowedGroups`

Reasons not to take this alternative:
* It would be a breaking change for some existing Cedar policies. In fact, it's a particularly insidious kind of breaking change: It's not that previously-valid policies would now produce parse errors, evaluation errors, or even validation errors (like in [RFC 20]), but rather that the behavior simply silently changes out from under you when you upgrade. Still perfectly valid, but a different meaning and behavior.
* If we add a new keyword like `inAny`, the distinction between `in` and `inAny` could cause confusion
* At least one user has opined that it's unintuitive that `John in [SalesTeam::"California", SalesTeam::"Oregon"]` would have different semantics than `John in SalesTeam::"WestCoast"` (assuming the natural group memberships there)

### Alternative 6: "Deep" set membership as well

Instead of shallow set-membership, `in` could have "deep" set membership semantics, automatically looking inside nested sets. For example, `"a" in ["foo", ["a", "b"]]` is `false` in the main proposal, but would be `true` in this alternative. For a more complicated example, in this alternative, if we write `User::"Alice" in [[Group::"A", Group::"B"],Group::"C"]` then this would be equivalent to `User::"Alice" in [Group::"A", Group::"B", Group::"C"]` with the RHS flattened.

The appeal here is that `in` is already "deep" for group membership and would now be "deep" for set membership as well, which has symmetry and might reduce confusion.

Reasons not to take this alternative:
* Runs against Cedar's tenet about analyzability
* Might be surprising behavior for users, particularly experienced programmers
* Might have undesirable runtime performance compared to the other alternatives


[RFC 20]: https://github.com/cedar-policy/rfcs/blob/main/text/0020-unique-record-keys.md
[RFC 21]: https://github.com/cedar-policy/rfcs/blob/main/text/0021-any-and-all-operators.md
