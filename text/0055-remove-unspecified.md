# Explicit Unspecified Entities

## Related issues and PRs

- Related RFCs: [RFC35](https://github.com/cedar-policy/rfcs/pull/35), [RFC47](https://github.com/cedar-policy/rfcs/pull/47)
- Implementation PR(s):

## Timeline

- Started: 2024-02-27
- Accepted: 2024-05-28
- Landed: 2024-06-19 on `main` ([#983](https://github.com/cedar-policy/cedar/pull/983))
- Released: TBD

## Summary

Cedar currently supports _unspecified entities_, which are entities of a special, unique type that have no attributes, and are not ancestors or descendants of any other entity in the store. Unspecified entities are intended to act as placeholders for entities that don’t influence authorization (see examples below).

The current implementation of unspecified entities results in several corner cases in our code (especially the validator), which have been difficult to maintain (see discussion on [this recent PR](https://github.com/cedar-policy/cedar/pull/603)). The concept of unspecified entities is (in our opinion) confusing for users, and will only become more confusing once we stabilize the partial evaluation experimental feature, which allows “unknown” entities that are subtly different from “unspecified” entities.

This RFC proposes to drop Cedar support for unspecified entities, instead recommending that users create their own application-specific entity types that act like unspecified entities.

## Basic example

Consider a "createFile" action that can be used by any `User`, as encoded in the following policy:

```
permit(principal is User, action == Action::"createFile", resource);
```

When making an authorization request for this action, the principal should be a `User`, and the context can store information about the file to create, but it is unclear what the resource should be.
In fact, given the policy above, the resource _doesn't matter_.
In this case, a Cedar user may want to make the authorization request with a “dummy” resource; as of Cedar version 3.x, this is what **unspecified entities** are for.

Now consider a "createAccount" action. It's unclear what principal _or_ resource should be used with this action. The approach above can be extended to this case too: make the action apply to an unspecified principal and resource. But now "unspecified" entities are being used to represent multiple distinct concepts: a file store, (unidentified) users creating an account, and a system that manages accounts.

This RFC proposes that users should instead explicitly create these "dummy" entities in an application-specific manner. For this example, the user should create entities of three types: `FileSystem`, `UnauthenticatedUser`, and `AccountManager`. The first will act as the principal for a "createFile" request, and the second and third will act as the principal and resource for a "createAccount" request.

This is (arguably) the approach we used in the [TinyTodo application](https://github.com/cedar-policy/cedar-examples/tree/release/3.0.x/tinytodo): we made a special `Application::“TinyTodo”` entity to act as the resource for the “CreateList” and “GetLists” actions.
This alternative is also in line with [our previous suggestion](https://cedar-policy.slack.com/archives/C0547KH7R19/p1706656288284189) to use an application-specific `Unauthenticated` type to represent "unauthenticated" users, rather than using unspecified entities.

## Motivation

Unspecified entities are a confusing concept, as evidenced by messy special casing in our own code and multiple RFCs to refine their behavior ([RFC35](https://github.com/cedar-policy/rfcs/pull/35), [RFC47](https://github.com/cedar-policy/rfcs/pull/47)).
We expect that this concept will only become more confusing once we stabilize the partial evaluation experimental feature, which allows “unknown” entities that are subtly different from "unspecified" entities, despite sharing similar names.

Unspecified entities also lead to two sharp corners in our public API:

1. Omitting a `appliesTo` field in the schema (or setting it to null) means that an action applies only to unspecified entities, while using an empty list means that it applies to no entities. There is no way to say that an action applies to both unspecified entities and other types of entities. For more discussion, see [RFC35](https://github.com/cedar-policy/rfcs/pull/35). (Note: RFC35 has been closed in favor of the current RFC.)
2. It is unclear how we should create `Request`s that use both unspecified and unknown entities. This has not been an issue so far since partial evaluation and its APIs are experimental, but we are looking to stabilize them soon. Currently the best (although not ideal) proposal is to use a builder pattern for `Request`s (e.g., `request.principal(Some(User::"alice"))` sets the principal field of a request). To set a field to be “unspecified” users could pass in `None` instead of `Some(_)`; to set a field to be unknown users would not call the field constructor at all.

### Aside: Unspecified vs. unknown

Unspecified and unknown entities are both pre-defined "dummy" entities that act like any other entity, as long as they are unused or only used in a trivial way (e.g., `principal == principal`).
If a policy uses an _unknown entity_ in a non-trivial way, then evaluation will produce a residual.
If a policy uses an _unspecified entity_ in a non-trivial way, then evaluation will produce an error.

## Detailed design

### Status quo

As of Cedar v3.x, the only way to construct an unspecified entity is by passing `None` as a component when building a [`Request`](https://docs.rs/cedar-policy/latest/cedar_policy/struct.Request.html).
So a request for the "createFile" action above might look like:

```rust
{
    principal: Some(User::"alice"),
    action: Some(Action::"createFile"),
    resource: None,
    ...
}
```

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

### Proposal

The proposal is simple: stop allowing the syntax above. The `Request` constructor will no longer accept optional arguments and schemas will no longer support missing `appliesTo` fields. The `Request` constructor API will be changed to require an `EntityUid` (instead of `Option<EntityUid>`) for the principal/action/resource, requiring code changes in programs using Cedar's Rust APIs. The schema APIs will not change, but omitting an `appliesTo` field will result in a parse error.

### Relation to RFC35

This RFC combines nicely with the (accepted) [RFC53 (Enumerated Entity Types)](https://github.com/cedar-policy/rfcs/pull/53), which allows users to fix the instances for a particular entity type. This means that custom "unspecified" entities can be easily restricted to a small set of possible entities. For example, RFC53 allows specifying that only `Application::"TinyTodo"` is valid, and no other `Application::"eid"`.

### Upgrade strategy

We appreciate that this RFC proposes a breaking change for Cedar's users, and the upgrade path is non-trivial  because it requires users to look carefully at their applications, and decide what they should use _instead_ of unspecified entities.
To help, while implementing this RFC, we plan to develop a **blog post** with examples of applications where you may have used an "unspecified" entity, and what we think you should use instead (suggestions for examples are welcome!).

We also plan to provide APIs (hidden behind a flag, like our experimental features) for the following operations, with the same API and behavior that was available in 3.x.

- Parsing a schema in the Cedar schema format
- Parsing a schema in the Cedar JSON schema format
- Constructing a request

This will allow services that build on top of Cedar (e.g., [Amazon Verified Permissions](https://aws.amazon.com/verified-permissions/)) to handle this upgrade for their customers invisibly.
The implementation will follow the approach outlined in [Alternative B](#alternative-b---maintain-the-status-quo-but-clean-up-the-implementation).
However, _we will not maintain these APIs indefinitely_ so you will need to support the new changes eventually. Please reach out to us if there's a way that we can help.

## Alternatives

### Alternative A - Predefine a special "unspecified" entity type

Continue to support unspecified entities, but re-brand them as "default" entities, with the intuition that you should use them when you want _some default value_ to pass into an authorization request.
This alternative proposes to give an explicit name to the unspecified entity type (`__cedar::Default`) and to require this name to be used in requests and schemas that use this type.

Under this proposal, the schema definition for the "createFile" action from above would look like:

```
action createFile
  appliesTo { principal: [User], resource: [__cedar::Default] };
```

and a (pseudo-syntax) request for this action might be:

```rust
{
    principal: EntityUid(User::"alice"),
    action: EntityUid(Action::"createFile"),
    resource: Default,
    ...
}
```

where the type of the `Request` constructor is:

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

(_Note_: the `Unknown` variant may be hidden behind the "partial-eval" experimental flag, depending on when this RFC is implemented.)

Users will not be allowed to include entities of type `__cedar::Default` in the store, which ensures that these entities will never have attributes or ancestors/descendants, which are properties we will rely on during validation.
Users will not be allowed to reference the type `__cedar::Default` in their policies (so neither `principal == __cedar::Default::"principal"` nor `principal is __cedar::Default` are allowed).
Users do not need to add `__cedar::Default` to their schemas (and it will be an error if they do) because `__cedar::Default` is defined automatically.
Finally, users cannot create entity uids with type `__cedar::Default`, which prevents using default entities with the `RequestEntity::EntityUid` constructor.

#### Naming specifics

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

- `Any`: possibility to confuse the scope condition `principal` with `principal is __cedar::Any`. The first applies to any principal, while the latter applies to only the default entity.
- `Arbitrary`: same issue as "any"
- `Unspecified`: potential for confusion with partial evaluation "unknown"
- `Mock`: implies that this entity type should be used for debugging/testing

#### Discussion notes

We considered this alternative seriously, and it even became the main proposal for a period of time.
But ultimately we decided that this alternative feels like a temporary solution, and we would eventually want to get rid of unspecified/default entities anyways.

Here's a nice (lightly edited) summary from @max2me:
> Both the main proposal and Alternative A are breaking changes, so I'd rather go a step forward and require customers to update schema, code, and policies once for the benefit of a brighter future (Alternative A would require customers to update just schema and code, yet all the same testing will have to occur).
>
> My concerns with Alternative A:
>
> - Lack of symmetry -- you omit something in the policy and yet explicitly mention it in the authorization code and schema. This leads to a fragmented experience of working with Cedar as a technology.
> - Surprise factor -- I suspect that most customers who leave principal/resource unscoped in policies will not realize that in addition to all the entities they reference in their code, there is a hidden default type.
>
> In my opinion, occasional duplication of policies and the need to define your own default type is a small cost to pay for the overall simplicity and cohesiveness of the system.

### Alternative B - Maintain the status quo, but clean up the implementation

Pre-define the `__cedar::Default` entity type as in Alternative A, but do not allow users to reference it directly.
Instead, update the underlying implementation to use the new type while leaving the current API as-is.
We took this approach in the [Lean model](https://github.com/cedar-policy/cedar-spec/tree/main/cedar-lean) to avoid special handling for unspecified entities, and it seems to have worked out well.
Differential testing has given us confidence that it leads to the same behavior as our current implementation.

_Note_: This alternative should result in no changes from the user’s perspective. If it does result in changes (e.g., to validation results) then this was unintentional behavior of our current implementation, and should be treated as a bug fix.
