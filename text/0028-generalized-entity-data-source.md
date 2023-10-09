# Generalized Entity Data Source

## Related issues and PRs

- This is a clean rewrite of [RFC 16](https://github.com/cedar-policy/rfcs/pull/16)

## Timeline

- Started: 2023-10-03 (predecessor [#16](https://github.com/cedar-policy/rfcs/pull/16) started on 2023-07-11)
- Entered FCP:
- Accepted:
- Landed:

## Summary

Add a trait `EntityDataSource` which is the interface for providing entity data
to `is_authorized()`.
`Entities` implements this trait, with all the entity data provided upfront and
stored in-memory, but other implementations are possible, e.g., an
implementation which looks up entities on-demand using DB queries.
`is_authorized` takes an `&impl EntityDataSource` instead of an `Entities`.

## Basic example

```rust
struct MyOwnDatabase {
    // ...
}

impl EntityDataSource for MyOwnDatabase {
    fn entity_attr(&self, uid: &EntityUid, attr: &str) -> Result<Option<Value>> {
        // custom implementation which could e.g. look up the attribute by
        // making a request to a database
    }
    // other methods ...
}
```

This RFC does not propose that we provide any implementations of
`EntityDataSource` other than for `Entities`, but lets Cedar users write their
own.

## Motivation

Today, entity data must all be provided up-front and kept in-memory in an
`Entities` object. It must all be present before calling `is_authorized()`.

**Challenge 1:**
We would like to support users whose entity data is large, or expensive to
compute, by allowing them to provide entity data on-demand rather than up-front.
As an important special case of this, we would like to support users whose
entity data is too large to fit in memory.

**Challenge 2:**
We would like to support users whose entity data is already stored in a
database or other storage method, without requiring them to convert it into
Cedar's `Entities` representation, or at least allowing the conversion to take
place on-demand on a per-entity basis.

**Challenge 3:**
Today, every `is_authorized()` request re-evaluates all of the attributes in the
`Entities`; they are stored as restricted expressions and evaluated to `Value`
on every call to `is_authorized()`. (See
[cedar#227](https://github.com/cedar-policy/cedar/issues/227).)
This is inefficient.
Today, `Entities::evaluate()` is implemented on `main` and provides a way to
mitigate this issue, but it is opt-in and we'd rather have it be the default
behavior.
Notably, as of this writing, `Entities::evaluate()` is not released yet, so we
can make changes in this area without breaking our users.

**Challenge 4:**
An additional motivation is that we would like to support partial evaluation
better than the current `Entities::partial()` does, and the proposed
`EntityDataSource` trait provides additional flexibility that should be helpful
for this down the line.

## Detailed design

This RFC has four components:

### Component 1: `is_authorized()` changes

First, we generalize `is_authorized()` to accept any `EntityDataSource`, not
just `Entities`:

```rust
impl Authorizer {
    // status quo:
    pub fn is_authorized(
        &self,
        q: &Request,
        pset: &PolicySet,
        entities: &Entities,
    ) -> Response

    // proposed change:
    pub fn is_authorized(
        &self,
        q: &Request,
        pset: &PolicySet,
        entities: &impl EntityDataSource,
    ) -> Response
}
```

The trait `EntityDataSource` is defined as follows:
```rust
trait EntityDataSource {
    /// Does an entity with the given UID exist or not
    fn entity_exists(&self, uid: &EntityUid) -> Result<bool>;

    /// Get just the indicated attribute of the specified entity, or `Ok(None)`
    /// if the attribute does not exist.
    ///
    /// Implementations of this method should not assume that the entity exists.
    /// If the entity does not exist, the implementation should return
    /// `Err(UnknownEntity)` and not `Ok(None)`.
    fn entity_attr(&self, uid: &EntityUid, attr: &str) -> Result<Option<Value>>;

    /// Does the given attribute exist on the specified entity?
    ///
    /// Implementations of this method should not assume that the entity exists.
    /// If the entity does not exist, the implementation should return
    /// `Err(UnknownEntity)` and not `Ok(false)`.
    fn entity_has_attr(&self, uid: &EntityUid, attr: &str) -> Result<bool> {
        // default implementation in terms of `entity_attr()`.
        // Note this computes the attribute value itself, and throws it away,
        // which may be inefficient for some implementations.
        Ok(self.entity_attr(uid, attr)?.is_some())
    }

    /// Is `child in parent`?
    ///
    /// Implementations of this method should not assume that either entity exists.
    /// If either entity does not exist, the implementation should return
    /// `Err(UnknownEntity)` and not `Ok(false)`.
    fn entity_in(&self, child: &EntityUid, parent: &EntityUid) -> Result<bool>;
}
```

We will provide the implementation of `EntityDataSource` for `Entities`.
This allows users to continue passing an `Entities` to provide entity data to
`is_authorized()`, and makes the change to `is_authorized()`
backwards-compatible: it still accepts an `Entities`, but now also accepts
additional types, namely any other `EntityDataSource`.

### Component 2: Store attributes as precomputed `Value`s

Second, we redefine `Entities` and `Entity` to hold attributes as `Value`s
instead of as `RestrictedExpression`s.
This particularly addresses Challenge 3.
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

### Component 3: Construct entities using precomputed `Value`s

Third, we add new constructors for `Entities` and `Entity` which take `Value`s
instead of `RestrictedExpression`s.
These constructors would work without throwing evaluation errors, in contrast
to the existing constructors after the changes described above.
This probably requires that we expose `Value` in our public API in some manner
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

This RFC currently proposes we take the third option.

### Component 4: Remove no-longer-necessary interface to precompute `Value`s

Fourth and finally, we remove `Entities::evaluate()`, as all `Entities` are now
stored in their evaluated form by default.
This is not a breaking change because `Entities::evaluate()` has not yet been
released in any Cedar release.

## Drawbacks

- This RFC represents some breaking changes for users upgrading to a new major
version of Cedar. All breaking changes come with some cost in terms of user
experience for existing users. This RFC contends that the benefit outweighs the
cost in this case.

- `EntityDataSource` represents a new contract we're making with users.  We
could be locking ourselves in to some implementation choices that currently we'd
be free to change behind the scenes. Similarly with exposing (even a wrapped
version of) `Value`.

- Some errors will occur at different times, or more lazily. In particular,
today, if any entity attribute is invalid, that error will _always_ be caught
during any call of `is_authorized()`. With this RFC, if an entity is never used
during an evaluation, its attributes may never be evaluated and thus may not
cause an error. Changing the behavior of some `is_authorized()` requests from
"error" to "valid" is not technically a breaking change (otherwise, adding any
new language syntax would be a breaking change), but this still might surprise
some users.

- The current proposed definition of `EntityDataSource` assumes that every
implementation of the trait handles transitive closure properly, and has no way
to check this assumption. If users make mistakes in this area, they may silently
get the wrong authorization results.
(This is also true of implementation errors such as loading the wrong attribute
values, etc; but errors with TC may feel more insidious somehow.)

## Alternatives

There are a lot of branching alternatives to all or parts of this RFC; this is
not a complete discussion of the decision tree.

Some of these alternatives are mutually exclusive with each other, and some are
not.

### Alternative A

We could do only the first component of the RFC, at least for now.
(The second, third, and fourth components are severable and could be their own
RFC.)
This provides the flexibility of alternate `EntityDataSource`s, but not the
efficiency improvements from storing attribute values as `Value` instead of
`RestrictedExpression`.
It also avoids all of the breaking changes, since the first component of the RFC
is completely backwards-compatible.

It does mean that implementations of `EntityDataSource` would have to provide
entity data in unevaluated (that is, `RestrictedExpression`) form.

Taking this alternative doesn't close off the door towards making the other
proposed changes sometime in the future.
However, if we took this alternative and users began writing `EntityDataSource`
implementations without the other components, and then later we wanted to make
the changes proposed in the other components of this RFC, we couldn't
_automatically_ or _by default_ provide existing `EntityDataSource`
implementations with those performance or ergonomic improvements; they would
have to make some code changes.

### Alternative B

We could do only the first, second, and fourth components of the RFC, at least
for now.
(The third component -- adding the new constructors for `Entities` and `Entity` --
is severable and could be its own RFC, or perhaps a change that doesn't rise
to the level of requiring an RFC.)

Users would have to still construct `Entity` and `Entities` via restricted
expressions, using constructors which can throw errors.

With this alternative, we may avoid having to expose `Value` or make changes to
`EvalResult`, at least for now.

Taking this alternative doesn't close off the door towards adding these
constructors sometime in the future.

### Alternative C

Instead of the proposed `EntityDataSource` definition, we could have a definition
something like this:
```rust
pub trait EntityDataSource {
    /// Given a uid, get the corresponding entity if it exists.
    /// The entity should already have `ancestors` data which represents all
    /// transitive closure ancestors, not just the direct parents.
    fn get(&self, uid: &EntityUid) -> Result<Option<Entity>>;
}
```

However, this interface might have significant inefficiencies for some
applications.
It requires the implementation of `get()` to return the entire `Entity` object,
including all of its attributes and the UIDs of all of its (transitive)
ancestors.
But often, Cedar doesn't need the entire `Entity` object, and constructing the
entire `Entity` object may be expensive for some trait implementations.
For instance, determining all ancestors may, in some `EntityDataSource`
implementations, require computing a graph reachability problem; or, some
attributes of an entity may be expensive to compute or slow to fetch.
But the Cedar evaluator would be required to call `get()` every time, even if it
only needed, say a single attribute of the entity.
If `get()` is expensive, the evaluator would be effectively throwing away all of
the entity information it didn't need for that particular query, only to
recompute it the next time it needs an attribute or ancestor check.
The proposed `EntityDataSource` interface provides a way for Cedar to ask for
much more granular information, and this RFC contends that it's worth the
complexity.

Unlike the above alternatives, if we took this alternative we couldn't come back
and add the proposed granular interface in the future in a backwards-compatible
way, at least not completely trivially.

### Alternative D

In addition to everything proposed in the current RFC, we could provide the
status-quo definitions of `Entities`, `Entity`, and `is_authorized()` under new
names: e.g., `UnevaluatedEntities`, `UnevaluatedEntity`, and
`is_authorized_unevaluated()` (naming of course TBD).
This is very unlikely to be of any use to new users, but existing users really
wanting the old error behavior could use these types and functions instead of
`Entities`, `Entity`, and `is_authorized()`.

To me, this provides little benefit, at the expense of more confusion and more
APIs to maintain. It also doesn't make any of the changes more back-compatible;
for users, migrating their code to use these renamed types and functions may be
just as much work as adopting the actual breaking changes proposed in this RFC.

### Alternative E

Instead of changing `Entities`, `Entity`, and `is_authorized()` as suggested in
the current RFC, we could provide new versions of these types and functions --
say, `EvaluatedEntities`, `EvaluatedEntity`, and `is_authorized_generic()` --
which have the behaviors proposed in the current RFC.
This avoids making any breaking changes to existing types and functions.

The downsides of this alternative include:
- Existing users don't get the improved performance by default (Challenge 3 in
[Motivation](#motivation)). They have to opt-in by migrating their code to these
new types and functions.
- Whether or not we officially deprecate the existing `Entities`, `Entity`, and
`is_authorized()`, new users may incorrectly assume that they should default to
using those types, as they have the most-intuitive / least-qualified names, and
types like `EvaluatedEntities` might appear to be for special cases.
- If we do not officially deprecate the existing `Entities`, `Entity`, and
`is_authorized()`, we are stuck maintaining more APIs indefinitely. These APIs
are also somewhat redundant and provide multiple ways to do approximately the
same thing, some more optimally than others.
- If we do officially deprecate the existing `Entities`, `Entity`, and
`is_authorized()`, we end up in a final state where we only have
`EvaluatedEntities` and no other kind of `Entities`, which is a kinda ugly and
nonsensical API from a naming standpoint -- not aesthetically pleasing.

### Alternative F

Much like Alternative C, we could define the `EntityDataSource` trait using a
single `.get()` method; but unlike Alternative C, we could have `get()` return
not an `Entity` object itself, but rather a generic that implements some other
trait.
For lack of a better name let's call it `SingleEntityDataSource` for now.
That would like something like this:
```rust
pub trait EntityDataSource {
    type Entity: SingleEntityDataSource;
    /// Given a uid, get data about the corresponding entity if it exists.
    fn get(&self, uid: &EntityUid) -> Result<Option<Self::Entity>>;
}

pub trait SingleEntityDataSource {
    fn attr(&self, attr: &str) -> Result<Option<Value>>;
    fn has_attr(&self, attr: &str) -> Result<bool> {
        // default implementation in terms of `attr()`
        Ok(self.attr(attr)?.is_some())
    }
    fn in(&self, parent: &EntityUid) -> Result<bool>;
}
```

This would provide some (maybe all?) of the benefits of implementing the full
`EntityDataSource` trait.

I'm not immediately sure if this Alternative F would be equivalent in power and
flexibility to the current proposal; but I do find the current proposal to be
more straightforward and think users would too (although it may be arguable).

Note that this definition of `SingleEntityDataSource` is perhaps oriented
towards a system where entities know about their own ancestors, and not their
descendants.
In some implementations, entities might know about their own descendants, but
not their ancestors.
(See, for instance, [cedar#313](https://github.com/cedar-policy/cedar/issues/313).)
For those implementations, it might make sense for `in()` to be a method on the
_parent_ entity that takes the potential _child_'s uid.
Perhaps there's some way we could support both, at the implementation's choice.

One advantage of the current proposal, as opposed to Alternative F, is that it's
agnostic to whether the system is ancestors-oriented or descendants-oriented;
`entity_in()` works equally well with both.

### Alternative G

As proposed, `EntityDataSource` methods do not generally allow the
implementation to assume that input entities exist.
We could instead allow the implementation to assume that input entities exist,
which might be more convenient for the implementation.
However, this would mean that the Cedar evaluator must in some cases call
`entity_exists()` prior to `entity_attr()` / `entity_in()` / etc, which could
result in duplicated work in some implementations.
E.g., many implementations might be able to combine an existence check and
attribute lookup efficiently, or an existence check and `in` check efficiently.

To complicate this further, for `entity_in()`, the current Cedar evaluator will
always know that `child` exists, but not necessarily `parent`, prior to calling
`entity_in()`; but the current RFC proposes not to allow implementations to
assume this, both for simplicity and to avoid committing to this implementation
detail.

In the future, deciding to commit to stronger preconditions for
`EntityDataSource` methods -- e.g., allowing implementations to make stronger
existence assumptions -- would be a backwards-compatible change, while the
reverse would not, so in that sense, the current proposal is the safest
proposal.

### Alternative H

As proposed, `EntityDataSource::entity_in()` requires the implementation to
consider all the transitive ancestors of the entity, which might be a burden for
some users.  We could allow users instead to implement
`entity_parents(&self, uid)`, which returns all the direct parents of the given
`uid`; and then we could provide a default implementation of `entity_in()` which
iteratively calls `entity_parents()` if necessary, essentially computing the
graph reachability in Cedar rather than requiring each `EntityDataSource`
implementation to compute TC.

## Interactions between this RFC and partial evaluation

Partial evaluation shares some of the motivation of this RFC -- in particular,
Challenges 1 and 2 in [Motivation](#motivation).
However, this RFC does not make partial evaluation redundant or vice versa; some
use-cases will work better by examining Cedar residuals to fetch entity data,
and other use-cases will prefer to provide an `EntityDataSource` implementation
for fetching entity data on-demand.
Some use-cases will even use both in conjunction.

The easiest way to handle the interaction between this RFC and partial
evaluation would be to leave `EntityDataSource` as currently proposed in this
RFC, and simply have the Cedar evaluator return a residual as appropriate when
`EntityDataSource::entity_exists()` returns `false`.
That is, the concrete/partial switch for entity data sources would be handled in
the Cedar evaluator, opaquely to `EntityDataSource` implementations with no
opportunity for customization.

This RFC may present an opportunity to allow more customization of
partial-evaluation behavior, either in this or a future RFC, for instance to
address issues like
[cedar#313](https://github.com/cedar-policy/cedar/issues/313).
One key question is "what information can be partial"?
Today, there are two possible partial evaluation "modes":

- Concrete: the `Entities` contains full information on every entity
- Partial: the `Entities` may not contain information on every entity, but
if the `Entities` does have information on an entity, it knows the exact
list of attributes that entity has, all of those attributes' values, and all
of the (transitive) ancestors of the entity, but not necessarily all of the
(direct or transitive) descendants of the entity.

As we generalize `Entities` to `EntityDataSource`, we may consider other modes.
For instance, we may consider a mode where the `EntityDataSource` may have some
information on an entity but not all; say, whether it exists and all of its
attribute values, but not information on its ancestors or descendants.
In that case, `A in B` may return a residual even if `A` and `B` are both known
to exist.
Conversely, we may consider a mode where the `EntityDataSource` may know an
entity's ancestors but not its attribute values.

This has the potential to get almost fractally complicated.
Essentially, we could choose almost any combination of the below choices (2^N
combinations) to be a supported "partial mode":

| More Concrete | More Partial |
| ------------- | ------------ |
| the `EntityDataSource` knows the full list of entities that exist | Operations that depend on entity existence may return a residual |
| if the `EntityDataSource` knows an entity exists, it knows at least the full list of attribute names that are valid for that entity | `entity has attr` may return a residual even if the entity is known to exist |
| if the `EntityDataSource` knows about the existence of any attributes of an entity, it knows the existence of all attributes of the entity | `entity has attr` may return `true` for some `attr` and a residual for another |
| if the `EntityDataSource` knows an entity has a particular attribute, it knows that attribute's value | `entity.attr` may return a residual even if `entity has attr` is known to be true |
| if the `EntityDataSource` knows an entity exists, it knows at least the full list of (transitive) ancestors of the entity | `A in B` may return a residual even if `A` is known to exist |
| if the `EntityDataSource` knows an entity exists, it knows at least the full list of (transitive) descendants of the entity | `A in B` may return a residual even if `B` is known to exist |
| if the `EntityDataSource` knows two entities exist, it knows at least whether they have a (possibly transitive) parent relationship | `A in B` may return a residual even if both `A` and `B` are known to exist |

Today's partial mode would correspond to choosing Partial, Concrete, Concrete, Concrete, Concrete, Partial, Concrete respectively.

Another way to state the same properties is in terms of "entity data source
extensions" -- i.e., given a partial entity data source, and imagining it being
transformed into the full entity data source (that concretely knows all of the
entity data), what kinds of information might be "added" during that operation?
Each row in the above table would correspond to the following kind of
information being "added" respectively:
- new entities' existence, along with their attributes and parent-edges
- attributes, to entities that had no attribute information
- additional attributes, to entities that already had some attribute information
- attribute values, to entities that already knew those attributes existed but did not know their values
- parent-edges from entities already known to exist, to entities not previously known to exist
- parent-edges from entities not previously known to exist, to entities already known to exist
- parent-edges between entities already known to exist

This RFC seems to represent an opportunity to revisit which "partial modes" we
offer, or maybe even find a way to support all possible partial modes (?), but
this has not yet been fully explored.
Ideally, I'd like to get this RFC through without fully deciding all of these
partial-evaluation-related issues (yet), leaving those for a future RFC; but, it
would be good to make sure that the design choices in this RFC aren't closing
any doors in this area that we want to remain open.
