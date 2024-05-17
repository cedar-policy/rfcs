# Referring to types in the empty namespace

## Related issues and PRs

- Reference Issues: [cedar#579](https://github.com/cedar-policy/cedar/issues/579)
- Implementation PR(s):

## Timeline

- Started: 2024-05-07

## Summary

Cedar users need a way to explicitly refer to types in the empty namespace,
particularly in schemas, where the currently active namespace is implicitly
prepended to any unqualified typenames.
This RFC proposes a tweak to typename resolution, and also proposes the syntax
`::id` to explicitly refer to the name `id` in the empty namespace.

## Basic example

```
entity User {
    email: String,
};
type id = String;

namespace Demo {
    entity User {
        id: id,
    };

    entity Account {
        owner: User,
    };
}
```

Currently, the `Demo::User` declaration is an error, because in its `id`
attribute, the `id` type implicitly refers to `Demo::id`, which doesn't exist.
With this RFC, this example would implicitly work correctly, because when
`Demo::id` is not found, the resolver would fall back to looking for `id` in the
empty namespace, and find the appropriate declaration.

As a separate issue, in the `owner` attribute of `Demo::Account`, the `User`
type implicitly refers to `Demo::User` and not the `User` in the empty
namespace.
This is correct behavior which we want to preserve.
However, currently, the schema author has no way to adjust this attribute
declaration so that it refers to the `User` type declared in the empty
namespace.
With this RFC, the schema author can use the syntax `owner: ::User` to
explicitly refer to the `User` type declared in the empty namespace.

## Motivation

Users justifiably expect that they can refer to any declared typename (in any
namespace) from any position in the schema, by writing a fully qualified name.
The fact that RFC 24 did not provide a way to refer to typenames in the empty
namespace by using some kind of fully qualified name seems like an oversight,
and should be corrected for consistency.

The other change proposed in this RFC, implicitly falling back to the empty
namespace (so that the `Demo::User` declaration is legal in the example above),
is an ergonomic change to avoid having to use the new syntax in the common case
where there is actually no typename collision (i.e., where the typename is not
actually defined in both the active and the empty namespace).

The two changes are theoretically separable and/or severable, but make sense to
address together, as they both relate to how we reference typenames in the empty
namespace.
The implicit-fallback change deals with referencing a typename in the empty
namespace where there is no collision with a typename in the active namespace.
The explicit-`::` change deals with referencing a typename in the empty
namespace where there _is_ a collision with a typename in the active namespace.

This issue has been encountered "in the wild" by multiple people, according to
a [comment on cedar#579](https://github.com/cedar-policy/cedar/issues/579#issuecomment-2077482637).

## Detailed design

### Change 1: Fully qualified syntax for referring to typenames in the empty namespace

The syntax `::id`, where `id` is an unqualified typename, now explicitly refers
to the `id` in the empty namespace.

This applies:
* regardless of if there is an `id` defined in the active namespace or not
* regardless of if there is an `id` defined in the empty namespace or not (if not, this is an error)
* regardless of whether `id` is the name of a common type or an entity type, in
either the empty and/or active namespace
* in both the human (RFC 24) and JSON schema syntaxes

This does not apply:
* to primitive and extension types. From the user's perspective, those live in
the `__cedar` namespace and not in the empty namespace. `::String` refers to an
entity or common type `String` defined in the empty namespace, while
`__cedar::String` refers to the builtin primitive type `String`.
* to "names" like `::A::B` -- that syntax remains an error. `A::B` is already an
unambiguous, fully-qualified name, and will never have any namespace implicitly
prepended.

### Change 2: Implicitly falling back on the empty namespace

When the schema refers to an unqualified typename (e.g, `id`) which doesn't
exist in the active namespace, we should fall back to looking for it in the
empty namespace.
Only if it exists in neither the active nor empty namespace should this be an
error.

E.g., in the example at the top of this RFC, consider the type of the `id`
attribute of `Demo::User`.
Since there is no `id` type defined in namespace `Demo`, this is an error today.
With this change, when we see there is no `Demo::id`, we implicitly look for
`id` in the empty namespace, and resolving `id` to be the common type `::id`
defined to be `String` in the empty namespace.
The user could, of course, write `::id` directly, but with this change, they
do not have to, in the common case where there is no collision (where `id` is
not actually defined in both the `Demo` and empty namespaces).

This applies to both entity and common types defined in the empty namespace.

This applies to both the human (RFC 24) and JSON schema syntaxes.

This is reminiscent of, but not dependent on, the existing similar behavior for
primtiive and extension types, where we first check for an entity or common type
`String` in the active namespace before falling back on resolving to
`__cedar::String`.

### Change 3: Warn when defining a typename that shadows an existing definition

This is a small change (adding a validation warning) that wouldn't require an
RFC by itself, but since it is related, and came up in comments on this RFC
thread, it is listed here.

If the user defines an entity/common type that shadows an existing definition
(i.e., a definition in the empty namespace, or the name of a primitive/extension
type), we will produce a validation warning for that definition.
(However, this is not a validation error, and this RFC's Change 1 will still
allow you to refer to the shadowed name.)

## Drawbacks

* The schema implementation becomes more complex, as we need more complex
methods for typename resolution, and also slightly more complexity in the
schema parser, as `::id` wasn't previously legal syntax (`::` previously was
only legal between two identifiers).

This is not a breaking change; all existing schemas remain valid with the same
semantics as they had before this RFC.

## Alternatives

Instead of `::id`, we could use many other syntaxes.
One proposal in the original
[cedar#579](https://github.com/cedar-policy/cedar/issues/579) thread was to use
something in the `__cedar` namespace, e.g., `__cedar::schema::top_level::id`.
Other possibilities include other special characters, like `^id` or `#id`, or even
a special keyword, like `root id`, which should be unambiguous in both the human
and JSON schema grammars.

## Unresolved questions

* Should we also support the `::id` syntax in policies?
    [2024-05-17: Based on discussion in the RFC thread, the proposed resolution is "no"]
    * Arguments for:
        * Consistency: Users will write `::User` in schemas and might expect to
        be able to write `::User` in policies as well
    * Arguments against:
        * It's unnecessary from an expressiveness perspective, as policies do not
        have a notion of active namespace, so the unqualified name `id` always refers to
        the `id` in the empty namespace and is never implicitly prefixed with any other
        namespace.
        * We can catch `::User` in the policy parser and provide a specific, informative
        error message, which makes this less of a sharp edge
        * We can always go back and add support for `::id` in policies later, if needed
