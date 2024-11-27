# Disallow duplicate keys in Cedar records

## Related issues and PRs

- Reference Issues: related to [cedar#169](https://github.com/cedar-policy/cedar/pull/169)
- Implementation PR(s): [cedar#375](https://github.com/cedar-policy/cedar/pull/375)

## Timeline

- Started: 2023-07-14
- Accepted: 2023-08-04
- Landed: 2023-10-24 on `main`
- Released: 2023-12-15 in `cedar-policy` v3.0.0

Note: These statuses are based on [the first version of the RFC process](./../archive/process-v1/README.md).

## Summary

Today, Cedar allows duplicate keys in record literals (and other record values, including `context`), with last-value-wins semantics.
This RFC proposes to disallow duplicate keys in record values, making that an error.

## Basic example

Today,
```
permit(principal, action, resource)
when {
    resource.data == { foo: 2, foo: 3 }
};
```
is a valid Cedar policy. The `foo: 2` is dropped and `foo` will have the value `3` in the record literal.
In other words, in Cedar,
```
{ foo: 2, foo: 3 } == { foo: 3 }
```
evaluates to `true`.

More precisely, Cedar's semantics does not just drop values prior to the last, but fully evaluates them before throwing them away. This has consequences in the presence of errors. For instance,
```
{ foo: 1 + "hello", foo: 3 }
```
does not evaluate to `{ foo: 3 }` as you might expect based on the previous example, but rather, it results in an evaluation error.

This RFC proposes that all of the above expressions and policies would result in an evaluation error due to duplicate keys in a record.

## Motivation

There are two main motivations for this change.

First, in the status quo, Cedar policy ASTs actually cannot losslessly roundtrip to EST and back.
This is because the AST representation correctly allows duplicate keys in record literals, but the EST representation drops them (due to an oversight during EST design). In this way, the EST is unfaithful to Cedar semantics, and not all valid Cedar policies are expressible in the EST, which violates the EST's design goal of being lossless modulo whitespace/comments/etc.

More precisely, if a JSON EST contains duplicate record keys in a record literal, our JSON parser will take last-value-wins, and the internal EST representation will contain only the last value.
This results in the correct behavior on examples like `{ foo: 2, foo: 3 }`, but the incorrect behavior on examples containing errors, like `{ foo: 1 + "hello", foo: 3 }`.
It also means that roundtripping the AST representation to the EST representation and back necessarily loses information -- specifically, the values associated with all but the last instance of each key.

The second motivation is that the status quo makes things difficult for our Cedar formal specification and accompanying proofs.
The proofs are required to reason about "well-formed" records as a pre- and post-condition, which could be avoided if records were structurally prohibited from having duplicate keys (e.g., by using a map type instead of an association list).
The status quo also requires reasoning about the order keys appear in a record literal, meaning that the keys can't be naively sorted without preserving information about their original order.
If duplicate keys were prohibited, the order of keys wouldn't matter (but see "Unresolved questions" below).

Two secondary, more minor motivations for this proposal are:
- It would bring the Cedar language in line with our desired behavior on duplicate keys in other Cedar API surfaces. See [cedar#159](https://github.com/cedar-policy/cedar/issues/159).
- Cedar records resemble other languages' struct types more than they resemble map types. The current behavior would be unexpected for struct types, and the proposed behavior would be intuitive.

## Detailed design

We'd do something very like [cedar#169](https://github.com/cedar-policy/cedar/pull/169), except that instead of implicitly dropping all but the last value for each key (in `.collect()`), we'd be careful to emit an error when constructing an `Expr` if the record has duplicate keys.

In the case of record literals, the error could be caught in the CST->AST step, resulting in the user seeing a parse error rather than an evaluation error.
In the case of `context`, the error would need to be caught when constructing the `Context` object.
In the case of records in entity attributes, the error could be caught when constructing an `Entity` object.
There are no other cases, because currently, Cedar has no other way to construct a record value:
there are only record literals, and records preexisting in `context` or entity attribute values.

All of these cases would be caught prior to `is_authorized()` in Core, so we would not need a new category of evaluation error. No new evaluation errors would happen due to this proposal.

Another consequence of the above choices is that duplicate-key errors "take precedence" over (other) evaluation errors. The expression `{ one: 1 - "three", one: 1 }` will throw a duplicate key error and not a type error.

I don't believe this change would have a significant effect on validation or width/depth subtyping of records, but please correct me if I'm wrong.

## Drawbacks

This is a breaking change, not just to the Cedar API surface, but to the Cedar language (policy syntax) itself.
That's a significant drawback not to be taken lightly.
In this case, it's mitigated somewhat by the fact that we're turning previously-valid policies into errors, not changing them into a silently different behavior.
It's also mitigated by the fact that most Cedar users are probably (citation needed) not writing policies in the class that will have a behavior change -- i.e., policies with duplicate keys in record literals.
And finally, it's mitigated by the fact that Cedar's current behavior on duplicate keys was not documented in the public docs (e.g., in [this section](https://docs.cedarpolicy.com/syntax-datatypes.html#record)), so if any policies are relying on this behavior, it's probably by accident.

## Alternatives

The main alternative is doing nothing, which of course has the reverse pros/cons of the proposal as explained in "Motivation" and "Drawbacks".

Another alternative, which would address the first motivation and not the second, would be to change the EST format so that it supports record literals with duplicate keys.
I believe this would require a breaking change to the EST format, and record literals would not be expressible as JSON maps, which is unfortunate because I believe that's the most natural/ergonomic.
(Devil's advocate: we could maybe find a way to support JSON maps in the common case with some escape syntax for expressing record literals that have duplicate keys. If we want to take this alternative seriously, I can investigate this.)

## Unresolved questions

### Order-independence for record keys

[Resolved: we won't make any further changes as part of this RFC, but may address some of this in a different RFC]

At first glance, one would hope that this change would be sufficient to ensure that the order of keys in a record literal (or more generally, any record value) does not matter.
However, that's not quite true -- if keys are mapped to expressions with errors, the order does matter, because only the first error encountered will be returned.
While we're making this change, should we also make a change so that we have true order-independence for Cedar record keys?
I could think of at least three ways to do that:
1. Always evaluate all values in a record, and return potentially multiple evaluation errors rather than just the first
2. Provide no guarantee about which error the user will receive when multiple record keys have errors (nondeterministic error behavior) -- I think the formal spec currently guarantees the first error?
3. Guarantee that record values will be evaluated in lexicographic order of their keys, regardless of the order the keys appear in the policy text

This issue is particularly hairy for records contained in attribute values in the entity store -- I believe these records go through a hashmap representation in our current datapath, so we lose ordering information and also duplicate keys (silently). Since the values in these records are restricted expressions, there are very few ways they can produce evaluation errors, but they still can, in the case of calls to extension functions. This is probably a potential source of difference between the errors produced in the Rust implementation and in the formal spec; I wonder why DRT hasn't caught this, particularly in the case where we drop a duplicate key that was mapped to an erroring expression. Maybe the Dafny JSON parser silently takes last-value-wins? or maybe we don't test extension values in attribute values?
