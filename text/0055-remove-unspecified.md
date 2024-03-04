# Explicit Unspecified Entities

## Related issues and PRs

- Related RFCs: [RFC35](https://github.com/cedar-policy/rfcs/pull/35), [RFC47](https://github.com/cedar-policy/rfcs/pull/47)
- Implementation PR(s):

## Timeline

- Started: 2024-02-27

## Summary

Cedar currently supports _unspecified entities_, which are entities of a special, unique type that have no attributes, and are not ancestors or descendants of any other entity in the store. Unspecified entities are intended to act as placeholders for entities that don’t influence authorization (see examples below).

The current implementation of unspecified entities results in several corner cases in our code (especially the validator), which have been difficult to maintain (see discussion on [this recent PR](https://github.com/cedar-policy/cedar/pull/603)). The concept of unspecified entities is (in our opinion) confusing for users, and will only become more confusing once we stabilize the partial evaluation experimental feature, which allows “unknown” entities that are subtly different from “unspecified” entities.

This RFC proposes to drop Cedar support for unspecified entities, instead recommending that users create their own application-specific entity types that act like unspecified entities.

## Basic example

Cedar uses a Principal, Action, Resource, Context \<P,A,R,C\> model for requests.
This model can feel awkward in cases where there is not a clear principal and/or resource for an action.
For example, consider a "createFile" action that can be used by any `User`, as encoded in the following policy:

```
permit(principal is User, action == Action::"createFile", resource);
```

When making an authorization request for this action, the principal should be a `User`, and the context can store information about the file to create, but it is unclear what the resource should be.
In fact, given the policy above, the resource _doesn't matter_.
In this case, a Cedar user may want to make the authorization request with a “dummy” resource; this is what Cedar’s unspecified entities are for.

As of Cedar v3.1, the only way to “construct” an unspecified entity is by passing `None` as a component when building a [`Request`](https://docs.rs/cedar-policy/3.0.1/cedar_policy/struct.Request.html).
So a request for this action might look like \<`Some(User::"alice")`, `Some(Action::"createFile")`, `None`, ...\> (using pseudo-syntax).

In the schema, omitting the relevant `appliesTo` field says that an action applies to an unspecified entity.
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

Now consider a "createAccount" action.
It's unclear what principal _or_ resource should be used with this action.
The approach above can be extended to this case too: make the action apply to an unspecified principal _and_ resource.
But now "unspecified" entities are being used to represent multiple distinct concepts: a file store, (unidentified) users creating an account, and a system that manages accounts.

This RFC proposes that users should instead explicitly create these "dummy" entities in an application-specific manner.
For this example, the user should create entities of three types: `FileSystem`, `UnauthenticatedUser`, and `AccountManager`.
The first will act as the principal for a "createFile" request, and the second and third will act as the principal and resource for a "createAccount" request.

This is exactly the approach we used in the [TinyTodo application](https://github.com/cedar-policy/cedar-examples/tree/release/3.0.x/tinytodo): we made a special `Application::“TinyTodo”` entity to act as the resource for the “CreateList” and “GetLists” actions.
This proposal is also in line with [our previous suggestion](https://cedar-policy.slack.com/archives/C0547KH7R19/p1706656288284189) to use an application-specific `Unauthenticated` type to represent "unauthenticated" users, rather than using unspecified entities.

## Motivation

Unspecified entities are a confusing concept, as evidenced by messy special casing in our own code and multiple RFCs to refine the behavior ([RFC35](https://github.com/cedar-policy/rfcs/pull/35), [RFC47](https://github.com/cedar-policy/rfcs/pull/47)).
We expect that this concept will only become more confusing once we stabilize the partial evaluation experimental feature, which allows “unknown” entities that are subtly different from “unspecified” entities.
Unspecified and unknown entities are both pre-defined "dummy" entities that act like any other entity, as long as they are unused or only used in a trivial way (e.g., `principal == principal`).
If a policy uses an _unknown entity_ in a non-trivial way, then evaluation will produce a residual.
If a policy uses an _unspecified entity_ in a non-trivial way, then evaluation will produce an error.

Unspecified entities also lead to two sharp corners in our public API:

1. Omitting a `appliesTo` field in the schema (or setting it to null) means that an action applies only to unspecified entities, while using an empty list means that it applies to no entities. There is no way to say that an action applies to both unspecified entities and other types of entities. For more discussion, see [RFC35](https://github.com/cedar-policy/rfcs/pull/35). (Note: RFC35 will be closed in favor of the current RFC, if accepted.)
2. It is unclear how we should create `Request`s that use both unspecified and unknown entities. This has not been an issue so far since partial evaluation and its APIs are experimental, but we are looking to stabilize them soon. Currently the best (although not ideal) proposal is to use a builder pattern for `Request`s (e.g., `request.principal(Some(User::"alice"))` sets the principal field of a request). To set a field to be “unspecified” users should pass in `None` instead of `Some(_)`; to set a field to be unknown users should not call the field constructor at all.

## Detailed design

This RFC proposes to drop unspecified entities from the Cedar language.
This means that the type of the `Request` constructor will change from:

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
pub fn new(
        principal: EntityUid,
        action: EntityUid,
        resource: EntityUid,
        context: Context,
        schema: Option<&Schema>,
    ) -> Result<Self, RequestValidationError>
...
```

And schemas will no longer support missing `appliesTo` fields.
Omitting a field will result in a parse error.

This will force users to create their own “unspecified” entity type(s) per application, like how we do for the [TinyTodo application](https://github.com/cedar-policy/cedar-examples/tree/release/3.0.x/tinytodo).
Services that build on top of Cedar (e.g., [Amazon Verified Permissions](https://aws.amazon.com/verified-permissions/)) can still maintain their current API (supporting optional fields in the request) by manually adding a catch-all "unspecified" entity type, as described in Alternative A.

_Note:_ this approach will benefit from [RFC53 (Enumerated Entity Types)](https://github.com/cedar-policy/rfcs/pull/53), if accepted.
That RFC would allow users to fix the instances for a particular entity type (e.g., it would allow specifying that only `Application::"TinyTodo"` is valid, and no other `Application::"eid"`).

### Upgrade strategy

This RFC proposes a **breaking change** for both the API and the language.
It breaks the API because it requires modifying the `Request` constructor, and it breaks the language because it changes the schema format and space of valid requests.
We will make this change more palatable by using a period of deprecation.
In particular, we will:

1. Publish a blog post based on this RFC with examples of applications where you may want an "unspecified" entity, and what we think you should use instead. (Suggestions welcome!)
2. In the next minor version (v3.2), we will produce a warning during validation if an unspecified entity is allowed for any action in the schema, along with a pointer to this blog post. (Unfortunately, we cannot produce warnings at authorization time because our APIs do not currently support this.)
3. Starting in the next major version (v4.0), we will make the breaking changes described above. This will **break** users, rather than silently changing behavior. If a user passes in optional fields when building a `Request`, they will get a Rust compile-time error. If they try to specify an action in the schema that applies to an unspecified entity, then they will get a schema parse error.

## Drawbacks

Breaking changes are painful for users.
This breaking change in particular will force users to take a second look at their application and reassess _why_ they are using unspecified entities.
We need to make sure that we provide enough value in v4.0 for the upgrade to be worth it.

## Alternatives

### Alternative A - Pre-define a special "unspecified" entity type

This alternative proposes to introduce a new special type (for now, called `__cedar::Ghost`) that allows users to refer to “unspecified” entities directly, instead of implicitly referring to them by passing `None` to the Request constructor, or omitting a field in the schema.
Like the main RFC proposal, users will be required to provide `EntityUid`s for each field of a `Request`, but they may now set some of these fields to be `__cedar::Ghost::"eid"` (for any `eid`).
Schemas will need to explicitly say that an action applies to this special type.
For example, the schemas from the example above would need to be modified as follows.

Cedar schema syntax (RFC 24):

```
action createFile
  appliesTo { principal: [User], resource: [__cedar::Ghost] };
```

Cedar schema JSON syntax:

```json
"createFile": {
    "appliesTo": {
        "principal": ["User"],
        "resource": ["__cedar::Ghost"]
    }
}
```

Users will not be allowed to include entities of type `__cedar::Ghost` in the store
This ensures that these entities will never have attributes or ancestors/descendants in the store, which is a property we will rely on during validation.
Users will not be allowed to write entity literals of type `__cedar::Ghost` in their policies, although they may reference `__cedar::Ghost` itself (e.g., `principal is __cedar::Ghost` is ok).
They do not need to add `__cedar::Ghost` to their schemas (and it will be an error if they do) because `__cedar::Ghost` is defined automatically.
We will provide a constructor to build an entity of type `__cedar::Ghost` so users can pass it as an argument to the `Request` constructor.

[cedar#557](https://github.com/cedar-policy/cedar/pull/557) (to be released in v3.1) reserves the `__cedar` namespace in schemas, so we should use this to prefix the new entity type, but the exact type name is up for debate.
Some other names we've considered (aside from "Ghost") include:

- `Null`
- `Dummy`

Here are some options we’ve ruled out:

- `Any`: possibility to confuse the scope condition `principal` with `principal is __cedar::Any`. The first applies to any principal, while the latter applies to only the “unspecified” entity.
- `Arbitrary`: same issue as “any”
- `Unspecified`: potential for confusion with partial evaluation “unknown”
- `Mock`: implies that this entity type should be used for debugging/testing

This alternative allows for a straightforward period of deprecation.
For example, in the next minor version (v3.2) we could leave the current APIs and schema format as-is, while also adding the new `__cedar::Ghost` type and support for using it in schemas and requests.
Both the old and new approaches will have the same behavior — under the hood, we will switch our current implementation to use the new entity type, which will allow us to remove some awkward special casing in our code.
Then, starting with the next major version (v4.0), we could break the current APIs as described in the main proposal above.

### Alternative B - Maintain the status quo, but clean up the implementation

Pre-define the `__cedar::Ghost` entity type as in Alternative A, but do not allow users to reference it directly.
Instead, update the underlying implementation to use the new type while leaving the current API as-is.
We took this approach in the [Lean model](https://github.com/cedar-policy/cedar-spec/tree/main/cedar-lean) to avoid special handling for unspecified entities, and it seems to have worked out well.
Differential testing has given us confidence that it leads to the same behavior as our current implementation.

_Note_: This alternative should result in no changes from the user’s perspective. If it does result in changes (e.g., to validation results) then this was unintentional behavior of our current implementation, and should be treated as a bug fix.

## Unresolved questions

None, yet.
