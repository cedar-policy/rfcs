# Entity Type with PartialValue attributes 

## Related issues and PRs

- Implementation: [https://github.com/prakol16/cedar/tree/uncached_entity_db_trait](https://github.com/prakol16/cedar/tree/uncached_entity_db_trait)

## Timeline

- Start Date: 2023-07-18
- Date Entered FCP:
- Date Accepted:
- Date Landed:

## Summary

This RFC proposes to add an entity type, which we tentatively call `ParsedEntity` (because the attributes are fully evaluated/parsed rather than simply parsed into
expressions; I don't like this name so let's find a better one) which is the same as `Entity` but the attribute types are internally represented as `PartialValue`. This allows
us to skip re-evaluating the attributes.

## Basic example

Converting an `Entities` to `ParsedEntities` (which evaluates all the attributes):

```rust
let e: Entities = // load from a JSON file
let f: ParsedEntities = e.eval_attrs();
auth.is_authorized(request, pset, f)
```

On the other hand, `f` could be loaded from any other format:

```rust
let f: ParsedEntities = // load from SQL database which may have native representations for some attribute types
auth.is_authorized(request, pset, f)
```

Finally, `f` does not even have to load all of the entities up front:

```rust
let f: EntityDatabase = // an SQL database which dynamically gets entities when they are needed
auth.is_authorized(request, pset, f)
```

## Motivation

Currently, our entities have an attribute set of type `HashMap<SmolStr, RestrictedExpression>`. This is in some sense an artefact of the entity storage format; the entities
are stored as JSON data, so it is easiest to parse entity attributes into `RestrictedExpression`'s, rather than launching an evaluator at parse time. However, with a 
more generalized storage format, it is likely that this will become a stumbling block. For example, attribute values might best be stored in some native format (e.g.
integers stored as 64-bit integers, decimals stored as native floats rather than a call to the extension function `decimal`), and it is silly to try to convert these first to
a `RestrictedExpression` that is reevaluated, rather than just converting it directly to a `PartialValue`.

Worse, if we do not want to load all of the entities into memory at once (as in [RFC 16](https://github.com/cedar-policy/rfcs/pull/16)), we currently have no way to support this because our evaluator goes through and evaluates all the
entity attributes up front. We could solve this through lazy attribute caching, as the other RFC suggests, but that has several drawbacks, which the other RFC details.
With this RFC, lazy caching becomes unnecessary because the user could parse the attributes up front themselves (or load them from some native format).

## Detailed design

The easiest way to make this change internally is to make `Entity` and `Entities` generic for some `Entity<T>`, where `T` is the attribute type, and similarly, we change
`Entities` to `Entities<T>`.

Externally, to leave the API unchanged, we can make separate wrappers `Entity` and `ParsedEntity` around `Entity<RestrictedExpression>` and `Entity<PartialValue>` respectively.

In order to leave the existing API unchanged, we can leave the current methods `is_authorized` which simply call `eval_attrs()` themselves, adding a new method,
`is_authorized_parsed` (TODO: figure out name) which accepts `ParsedEntities` instead of `Entities`.

## Drawbacks

- It's a relatively large refactor because it touches fundamental Cedar types (`Entity` and `Entities`). It's actually harder than simply adding a lazy attribute cacher while offering
fewer features (but in some sense allowing more flexibility, since the user can do the caching themselves using `RefCell<T>`/`unsafe` if they really want, or choose not
to do caching at all).
- It adds new API very similar to existing API, which could be confusing.
- It may require us to expose/create `PartialValue` (hence `Expr`) API which is more stuff to maintain

## Alternatives

- Get rid of attribute caching entirely and re-evaluate the attribute every time the attribute is needed. Honestly, this isn't even that bad, since restricted expression evaluation
is linear time, essentially doing a `clone()` operation, right? We routinely do `clone`'s on `PartialValue`'s in the code.
- Use lazy attribute caching as described in the [other RFC](https://github.com/cedar-policy/rfcs/pull/16)
- Add an `iter()` method to `EntityDatabase` and keep the existing behavior of parsing all the entity attributes on evaluator creation; do not allow users to pass entities
with already-evaluated attributes.

## Unresolved questions
How should the new API be exposed? In a perfect world, the `is_authorized` calls would only accept `ParsedEntities`. In fact, I would ideally make parsed entities the "default" `Entities` type
and rename the existing `Entities` with unevaluated attributes `UnparsedEntities`. The only time `UnparsedEntities` should show up in user code is possibly right after the JSON
parsing is done, at which point they would typically immediately call `eval_attrs`, unless they want to do some entity slicing before evaluating (we could provide
a utility function which combines JSON loading and `eval_attrs`).

But in this very much imperfect world, I'm not sure if we can do this without breaking any existing API. For example, the current API has a `new` method for `Entity` built from
`RestrictedExpression`s, essentially locking in the underlying attribute type (the return type is just `Self` rather than `Result<Self>`). Therefore, we have to
add new types and make things more confusing.

Maybe we could make this a breaking change and release it in Cedar 3.0?
