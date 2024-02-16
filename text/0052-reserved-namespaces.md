# Reserve Identifiers for Internal Use

## Related issues and PRs

- Reference Issues: (fill in existing related issues, if any)
- Implementation PR(s): (leave this empty)

## Timeline

- Started: 2024-02-14

## Summary

This RFC extends the reservation of the `__cedar` namespace in schema in [RFC24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md) and
proposes reserving all namespaces that start with two underscores (`__`),
forbidding their use in Cedar policies, schema, and entity data so that they can be used by future Cedar language features.

## Basic example

Under this RFC the names `__cedar::Long`, `__Long`, and `__namespace::User` will all become invalid in all contexts.

These would be rejected in a policy

```cedar
permit(principal == __cedar::User::"alice", actions, resource);
```

in a schema

```
namespace __DocCloud {
  ...
}
```

and in entity data

```json
[
    {
        "uid": { "__entity": { "type": "__cedar::User", "id": "alice"} },
        "attrs": {},
        "parents": []
    }
]
```

## Motivation

In designing [RFC24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md) we found that we needed to disambiguate user defined identifiers from built-in primitive and extension types.
We accomplished this by reserving only the `__cedar` namespace inside of schema,
but we anticipate that we may need more reserved namespaces in more contexts in the future.

## Detailed design

We will update the [namespace](https://docs.cedarpolicy.com/policies/syntax-grammar.html#grammar-path) to the following to exclude namespaces starting with `__`.

```
Path ::= LEADING_NAMESPACE_IDENT {'::' IDENT}
LEADING_NAMESPACE_IDENT ::= IDENT - RESERVED_NAMESPACE_IDENT
RESERVED_NAMSPACE_IDENT ::= ['_']['_'].*
IDENT ::= ['_''a'-'z''A'-'Z']['_''a'-'z''A'-'Z''0'-'9']* - RESERVED
RESERVED ::= 'true' | 'false' | 'if' | 'then' | 'else' | 'in' | 'like' | 'has'
```

This primarily applies to entity types names.
In the case where an entity type isn't qualified with a namespace, the leading identifier is just the entity type, so we would forbid an unqualified type `__User`.
It also applies anywhere else namespaces may appear, including the top-level `namespace` element in a schema file, qualified references to common types in a schema file, and extension function names in policies.

It does not apply where a standalone identifier is expected.
For example, an entity attribute could still start with `__`.

## Drawbacks

This is a significant breaking change.
A user with namespaces starting with `__` will need to update their policies, schema, and entity data to use an unreserved namespace.
The nature of this breaking change fortunately allows for migration away from reserved namespaces before the change is released,
and the break will manifest immediately on attempting to parse an affected policy, schema, or entity.

## Alternatives


### A larger breaking change

We could make a larger breaking change by reserving all _identifiers_ starting with `__` instead of just namespaces.
This would include inner namespace elements and attribute names on entities and records.
For example, we would additional forbid referencing an entity `namespace::__User` or writing a record literal `{__attr: 1}`.
We don't currently see an immediate need for this more aggressive change, but making it now provides even more flexibility in future changes at the cost of the breaking change affecting more users.

## A smaller breaking change

We can make a smaller breaking change by reserving only the `__cedar` namespace.
Only identifiers whose path starts with `__cedar` would become invalid identifiers, leaving users free to use an identifier like `__namespace::User`, but not `__cedar::User` or `__cedar::inner::User`.
This still provides names we can use in future features while only affecting users who specifically use this exact namespace.

## No breaking change

We can avoid a breaking change to Cedar by updating the Grammar to allow for a new identifier that is currently invalid, and then reserve that identifier.
For example, we could reserve `$cedar` or `cedar$` (other options for characters include `%` or `!`).
It would would be an error to use this identifier in any way that isn't explicitly permitted by the Cedar spec.

Taking this option would require an update to the schema grammar in [RFC24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md).
