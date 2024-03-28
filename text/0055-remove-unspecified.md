# Explicit Unspecified Entities

## Related issues and PRs

- Related RFCs: [RFC35](https://github.com/cedar-policy/rfcs/pull/35), [RFC47](https://github.com/cedar-policy/rfcs/pull/47)
- Implementation PR(s):

## Timeline

- Started: 2024-02-27

## Summary

Cedar currently supports _unspecified entities_, which are entities of a special, unique type that have no attributes, and are not ancestors or descendants of any other entity in the store. Unspecified entities are intended to act as placeholders for entities that don’t influence authorization (see examples below).

The current implementation of unspecified entities results in several corner cases in our code (especially the validator), which have been difficult to maintain (see discussion on [this recent PR](https://github.com/cedar-policy/cedar/pull/603)). The concept of unspecified entities is (in our opinion) confusing for users, and will only become more confusing once we stabilize the partial evaluation experimental feature, which allows “unknown” entities that are subtly different from “unspecified” entities.

This RFC proposes to change the terminology surrounding unspecified entities, instead calling them "default" entities.
It also proposes to give an explicit name to the unspecified entity type (`__cedar::Default`) and to require this name to be used in requests and schemas that use this type.

## Basic example

Cedar uses a Principal, Action, Resource, Context \<P,A,R,C\> model for requests.
This model can feel awkward in cases where there is not a clear principal and/or resource for an action.
For example, consider a "createFile" action that can be used by any `User`, as encoded in the following policy:

```
permit(principal is User, action == Action::"createFile", resource);
```

When making an authorization request for this action, the principal should be a `User`, and the context can store information about the file to create, but it is unclear what the resource should be.
In fact, given the policy above, the resource _doesn't matter_.
In this case, a Cedar user may want to make the authorization request with a “dummy” resource; as of Cedar version 3.1, this is what unspecified entities are for.

The only way to “construct” an unspecified entity is by passing `None` as a component when building a [`Request`](https://docs.rs/cedar-policy/3.0.1/cedar_policy/struct.Request.html).
So a request for this action might look like \<`Some(User::"alice")`, `Some(Action::"createFile")`, `None`, ...\> (using pseudo-syntax).

In the schema, the only way to say that an action applies to an unspecified entity is by omitting the relevant `appliesTo` field.
For example, the following schemas specify that the "createFile" action applies (only) to an unspecified resource.

Cedar schema syntax ([RFC 24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md)):

```
action createFile
  appliesTo { principal: [User] };
```

Cedar schema JSON syntax:

```json
"createFile": {
    "appliesTo": {
        "principal": ["User"]
    }
}
```

This RFC proposes to instead refer to these special entities as **default entities** since you should use them when you want _some default value_ to pass into an authorization request, but you don't care what the exact value is because it doesn't impact authorization.
This RFC also proposes to introduce a new special type (`__cedar::Default`) that allows users to refer to default entities _explicitly_ instead of _implicitly_, and change the type of the `Request` constructor from:

```rust
pub fn new(
        principal: Option<EntityUid>,
        action: Option<EntityUid>,
        resource: Option<EntityUid>,
        context: Context,
        schema: Option<&Schema>,
    ) -> Result<Self, RequestValidationError>
...
```

to:

```rust
pub enum RequestEntity {
    Default,
    Unknown,
    EntityUid(EntityUid)
}

pub fn new(
        principal: RequestEntity,
        action: RequestEntity,
        resource: RequestEntity,
        context: Context,
        schema: Option<&Schema>,
    ) -> Result<Self, RequestValidationError>
...
```

(Note: the `Unknown` variant may be hidden behind the "partial-eval" experimental flag, depending on when this RFC is implemented.)

Under this proposal, the request above would become \<`EntityUid(User::"alice")`, `EntityUid(Action::"createFile")`, `Default`, ...\>.

Finally, schemas will need to explicitly say that an action applies to the default type, rather than omitting an `appliesTo` field.
For example, the schemas above would need to be modified as follows.

Cedar schema syntax (RFC 24):

```
action createFile
  appliesTo { principal: [User], resource: [__cedar::Default] };
```

Cedar schema JSON syntax:

```json
"createFile": {
    "appliesTo": {
        "principal": ["User"],
        "resource": ["__cedar::Default"]
    }
}
```

Users will not be allowed to include entities of type `__cedar::Default` in the store, which ensures that these entities will never have attributes or ancestors/descendants, which are properties we will rely on during validation.
Users will not be allowed to reference the type `__cedar::Default` in their policies (so neither `principal == __cedar::Default::"principal"` nor `principal is __cedar::Default` are allowed).
Users do not need to add `__cedar::Default` to their schemas (and it will be an error if they do) because `__cedar::Default` is defined automatically.
Finally, users cannot create entity uids with type `__cedar::Default`, which prevents using default entities with the `RequestEntity::EntityUid` constructor.

## Motivation

Unspecified entities are a confusing concept, as evidenced by messy special casing in our own code and multiple RFCs to refine their behavior ([RFC35](https://github.com/cedar-policy/rfcs/pull/35), [RFC47](https://github.com/cedar-policy/rfcs/pull/47)).
We expect that this concept will only become more confusing once we stabilize the partial evaluation experimental feature, which allows “unknown” entities that are subtly different from “unspecified” entities, despite sharing similar names.
Unspecified and unknown entities are both pre-defined "dummy" entities that act like any other entity, as long as they are unused or only used in a trivial way (e.g., `principal == principal`).
If a policy uses an _unknown entity_ in a non-trivial way, then evaluation will produce a residual.
If a policy uses an _unspecified entity_ in a non-trivial way, then evaluation will produce an error.

Unspecified entities also lead to two sharp corners in our public API:

1. Omitting a `appliesTo` field in the schema (or setting it to null) means that an action applies only to unspecified entities, while using an empty list means that it applies to no entities. There is no way to say that an action applies to both unspecified entities and other types of entities. For more discussion, see [RFC35](https://github.com/cedar-policy/rfcs/pull/35). (Note: RFC35 has been closed in favor of the current RFC.)
2. It is unclear how we should create `Request`s that use both unspecified and unknown entities. This has not been an issue so far since partial evaluation and its APIs are experimental, but we are looking to stabilize them soon. Currently the best (although not ideal) proposal is to use a builder pattern for `Request`s (e.g., `request.principal(Some(User::"alice"))` sets the principal field of a request). To set a field to be “unspecified” users should pass in `None` instead of `Some(_)`; to set a field to be unknown users should not call the field constructor at all.

## Detailed design

### Naming specifics

The names `RequestEntity` and `__cedar::Default` are both subject to change.

For the latter, we have agreed that we want to use the `__cedar` prefix (reserved as part of [cedar#557](https://github.com/cedar-policy/cedar/pull/557) in v3.1), but the exact type name is up for debate.
Options we've considered include:

- `None`
- `Null`
- `Ghost`
- `Dummy`
- `Empty`
- `Irrelevant`
- `Generic`

Here are some options we’ve ruled out:

- `Any`: possibility to confuse the scope condition `principal` with `principal is __cedar::Any`. The first applies to any principal, while the latter applies to only the “unspecified” entity.
- `Arbitrary`: same issue as “any”
- `Unspecified`: potential for confusion with partial evaluation “unknown”
- `Mock`: implies that this entity type should be used for debugging/testing

### Upgrade strategy

This RFC proposes a **breaking change** for both the API and the language.
It breaks the API because it requires modifying the `Request` constructor, and it breaks the language because it changes the schema format.
Fortunately, this proposal allows for a straightforward period of deprecation.

To start, we will leave the current APIs and schema format as-is, while also adding the new `__cedar::Default` type and support for using it in schemas and requests.
Passing `None` into the `Request` constructor will become equivalent to passing in `Some(__cedar::Default::"eid")`.
Omitting an `appliesTo` field in the schema will become equivalent to having `[__cedar::Default]`, but we will emit a warning to recommend updating to the new syntax.

Then, in a subsequent major version, we can implement the breaking changes described above.

### Documentation

As pointed out in reviews of this RFC, a key reason why unspecified entities are confusing is that we have almost no documentation for them.
Thus, an important part of this RFC is developing useful documentation.
We expect this to include a blog post with examples of applications where you may want an unspecified entity, and recommendations for best practices.

## Drawbacks

Breaking changes are painful for users.
We need to make sure that we provide enough value in the major version with this change for the upgrade to be worth it.

## Alternatives

### Alternative A - Get rid of the unspecified entity type

The current proposal can be viewed as a re-framing of the current unspecified type.
A more radical option (as originally proposed by this RFC) is to completely drop Cedar support for unspecified entities, instead recommending that users create their own application-specific entity types that act like unspecified entities.

This is (arguably) the approach we used in the [TinyTodo application](https://github.com/cedar-policy/cedar-examples/tree/release/3.0.x/tinytodo): we made a special `Application::“TinyTodo”` entity to act as the resource for the “CreateList” and “GetLists” actions.
This alternative is also in line with [our previous suggestion](https://cedar-policy.slack.com/archives/C0547KH7R19/p1706656288284189) to use an application-specific `Unauthenticated` type to represent "unauthenticated" users, rather than using unspecified entities.

Under this alternative, the type of the `Request` constructor would become:

```rust
pub fn new(
        principal: EntityUid,
        action: EntityUid,
        resource: EntityUid,
        context: Context,
        schema: Option<&Schema>,
    ) -> Result<Self, RequestValidationError>
...
```

(Note the non-optional `EntityUid` types.)

Also, like the main RFC proposal, schemas would no longer support missing `appliesTo` fields.

The upgrade path for this alternative is more difficult than the one for the main proposal because it requires Cedar users to look carefully at their applications, and decide what they should use _instead_ of unspecified entities.
However, services that build on top of Cedar (e.g., [Amazon Verified Permissions](https://aws.amazon.com/verified-permissions/)) can handle this change for their customers invisibly by manually defining a catch-all "unspecified" entity type (akin to `__cedar::Default` in the main proposal).

_Note:_ this alternative would benefit from [RFC53 (Enumerated Entity Types)](https://github.com/cedar-policy/rfcs/pull/53), which will allow users to fix the instances for a particular entity type (e.g., it will allow specifying that only `Application::"TinyTodo"` is valid, and no other `Application::"eid"`).

### Alternative B - Maintain the status quo, but clean up the implementation

Pre-define the `__cedar::Default` entity type as in the main proposal, but do not allow users to reference it directly.
Instead, update the underlying implementation to use the new type while leaving the current API as-is.
We took this approach in the [Lean model](https://github.com/cedar-policy/cedar-spec/tree/main/cedar-lean) to avoid special handling for unspecified entities, and it seems to have worked out well.
Differential testing has given us confidence that it leads to the same behavior as our current implementation.

_Note_: This alternative should result in no changes from the user’s perspective. If it does result in changes (e.g., to validation results) then this was unintentional behavior of our current implementation, and should be treated as a bug fix.
