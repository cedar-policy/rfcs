# Reserve Identifiers for Internal Use

## Related issues and PRs

- Reference Issues: https://github.com/cedar-policy/cedar/issues/920
- Implementation PR(s): https://github.com/cedar-policy/cedar/pull/969

## Timeline

- Started: 2024-02-14
- Accepted: 2024-06-10
- Landed: 2024-07-15 on `main` ([#969](https://github.com/cedar-policy/cedar/pull/969))
- Released: TBD

## Summary

This RFC extends the reservation of the `__cedar` namespace in schema in [RFC24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md) and
proposes reserving all namespaces and identifiers where the first element is `__cedar`,
forbidding their use in Cedar policies, schema, and entity data so that they can be used by future Cedar language features.

## Basic example

Under this RFC the names `__cedar`, `__cedar::Long`, and `__cedar::namespace::User` will all become invalid in all contexts.

These would be rejected in a policy

```cedar
permit(principal == __cedar::User::"alice", actions, resource);
```

in a schema

```
namespace __cedar {
    entity User;
}
```

and in entity data

```json
[
    {
        "uid": { "__entity": {
            "type": "__cedar::User",
            "id": "alice"
        }},
        "attrs": {},
        "parents": []
    }
]
```

In this entity data example, the `__entity` JSON key does not demonstrate the new reserved namespace mechanism.
It is a place were we already assign special significance to some identifiers starting with `__` in entity data.

## Motivation

In designing [RFC24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md) we found that we needed to disambiguate user defined identifiers from built-in primitive and extension types.
We accomplished this by reserving only the `__cedar` namespace inside of schema,
but we anticipate that we may need more reserved namespaces in more contexts in the future.

## Detailed design

We will update the [namespace grammar](https://docs.cedarpolicy.com/policies/syntax-grammar.html#grammar-path) to the following to exclude namespaces and identifiers starting with `__cedar`.


```
Path ::= IDENT {'::' TRAILING_NAMESPACE_IDENT}
IDENT ::= INNER_IDENT - '__cedar'
TRAILING_NAMESPACE_IDENT ::= ['_''a'-'z''A'-'Z']['_''a'-'z''A'-'Z''0'-'9']* - RESERVED
RESERVED ::= 'true' | 'false' | 'if' | 'then' | 'else' | 'in' | 'like' | 'has'
```

This primarily applies to entity types names.
In the case where an entity type isn't qualified with a namespace, the leading identifier is just the entity type, so we would forbid an unqualified type `__cedar`.
It also applies anywhere else namespaces may appear, including the top-level `namespace` element in a schema file, qualified references to common types in a schema file, and extension function names in policies.

It also applies where a standalone identifier is expected.
For example, an entity attribute could not be `__cedar`.
Reserving this single attribute is not own it's own particularly useful, but we may later extend the attribute grammar to accept namespace paths.

## Drawbacks

This is a significant breaking change.
Anyone using the `__cedar` namespace will need to update their policies, schema, and entity data to use an unreserved namespace.
The nature of this breaking change fortunately allows for migration away from reserved namespaces before the change is released,
and the break will manifest immediately on attempting to parse an affected policy, schema, or entity.

## Alternatives

### A larger breaking change

We could make a larger breaking change by reserving identifiers starting with `__` instead of just `__cedar`.
For example, we would additional forbid referencing an entity `__tiny_todo::User`.

We don't currently see an immediate need for this more aggressive change, and it increases the likelihood a current user will be affected.
We may also find that consumers of Cedar who expose the policy language to their users want to reserve namespaces for their own use.
They could of course choose a namespace with any leading characters, but they may prefer the uniformity between `__cedar::Long` and, for example, `__tiny_todo`.

### No breaking change

We can avoid a breaking change to Cedar by updating the Grammar to allow for a new identifier that is currently invalid, and then reserve that identifier.
For example, we could reserve `$cedar` or `cedar$` (other options for characters include `%` or `!`).
It would would be an error to use this identifier in any way that isn't explicitly permitted by the Cedar spec.

Taking this option would require an update to the schema grammar proposed in [RFC24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md).
