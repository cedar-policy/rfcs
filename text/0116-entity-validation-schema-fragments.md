# Entity Validation with Schema Fragments

## Related issues and PRs

- Reference Issues: (none)
- Implementation PR(s): [#2615](https://github.com/cedar-policy/cedar/pull/2615)

## Timeline

- Started: 2026-07-08
- Accepted: TBD
- Stabilized: TBD

## Summary

This RFC proposes an extension to Cedar schemas (in both JSON and human-readable Cedar syntax) to enable _sound_ validation of Cedar entities given a schema fragment (a partial Cedar schema that may reference undefined entity types and actions). The extension introduces an `external` keyword that allows schema authors to declare entity types or actions without providing their full definitions, enabling validation of entities that reference them without requiring all schema fragments to be loaded.
The extension also introduces linking of schema.

## Basic example

The following schema declares an entity type `User` without defining its attributes, tags, or ancestor types. It then uses this type to define the `owner` attribute for the `Document` entity.

```
external entity User;
entity Document {
  owner: User
};
```

Even though we know nothing about the `User` entity type, we can use this schema to validate a `Document` entity. To validate the `owner` attribute, we check that the value has entity type `User`. We do not need the full definition of `User` to conclude that it is valid. For example, we know the following `Document` entity is valid because the entity type of its `owner` is `User`.

```
{
    "uid": { "type": "Document", "id": "file.txt" },
    "attrs": {
        "owner": { "__entity": { "type": "User", "id": "alice"} }
    },
    "parents": []
}
```

If the `owner` entity type is not `User`, then we know that the `Document` entity is not valid. For example:

```
{
    "uid": { "type": "Document", "id": "report.pdf" },
    "attrs": {
        "owner": { "__entity": { "type": "Account", "id": "123"} }
    },
    "parents": []
}
```

## Motivation

We have found that we want to store and manage different types of Cedar entities separately.

Say we have an application managing documents for users. Documents and users are stored and managed separately, so we also want to validate their corresponding Cedar entities independently. In this model, each schema fragment typically defines a single entity type and its relationships. We can create a schema defining the document entity, but, for each document, there is a user who owns that document, so our document schema must reference the user entity type.

While the current Cedar schema specification allows us to define the `Document` and `User` entities in separate documents (schema fragments), it does not allow us to validate either type of entity until we have composed a complete schema, even when much of the information in the schema is irrelevant. In fact, we may need to retrieve and load a schema fragment when we don't need any information from that fragment just to satisfy the requirement that all entity types referenced in the complete schema are also defined. In a distributed system, loading this information can lead to unnecessary latency when validating entity data.

We would like to use a schema fragment with undefined entity types in situations where the actual definition of those types is not relevant for a particular validation task. Unconditionally allowing undefined entity types is too error prone (a simple typo in a type would not be caught until a schema is used), so this RFC proposes that entity types can be _declared_ as `external` entity types without providing a definition.

## Detailed design

We will introduce a new keyword which declares an "external" entity type: a non-enumerated entity type without defining its attributes or tags. An external entity may optionally declare its parent types, as described below. Once declared as external in a schema fragment, we know that the name refers to an entity type (not a common or built-in type), so the rest of that fragment can use it in entity references.

When combining multiple fragments, we attempt to link external declarations with concrete definitions. Declarations are linked when their names precisely match a definition of the same kind, accounting for any containing namespace. An external entity may link only with a non-enumerated entity type definition, and an external action may link only with an action definition. Neither may link with a common or built-in type. An external declaration may appear in any number of input fragments, but it may have only one concrete definition. Repeated external declarations are combined according to the ancestor rules below. If there is a concrete definition, it replaces the external declarations in the combined result. Otherwise, the declaration remains unresolved, but we do not report an error.

External entities cannot resolve to enumerated entity types because validation against the fragment cannot check whether an entity identifier is one of the allowed values. Allowing this would make validation against the fragment unsound.

If every external declaration has a corresponding concrete definition, then we have a complete `Schema` which we can use exactly as if there were no external declarations. In this situation, external declarations explicitly specify dependencies between schema fragments, but could be omitted entirely.

Otherwise, we have a partial schema with unresolved external declarations. We cannot construct a complete `Schema`, which limits what we can do with it.

Linking schema should not cause any declared entity's ancestor set to grow. Linking schema should not introduce an entity type whose name shadows a primitive, and in general the linked result is held to Cedar's existing name shadowing rules. Linking happens after the common types are resolved, so common type name shadowing and duplication are permitted, and behave as if the type definitions are inlined in each individual schema being linked.

**We can:**

* Validate instances of any defined entity types, even if their attributes, tags, or ancestors contain references to an unresolved external entity type. For attributes and tags, we only need to check that an entity reference has the expected entity type name. Ancestors also require enough hierarchy information to determine that their types are allowed, as described below.
* Validate authorization requests for defined actions. Validating the context is the same as validating an entity's attributes. The action definition enumerates the allowed `principal` and `resource` types, so we only need to check that those request components have the expected entity types. We need the entity type definitions only if we also want to validate the entity instances to which those components refer.

**We cannot:**

* Validate an instance of an unresolved external entity type. To validate an entity, we check that its attributes, tags, and ancestors have their expected types. We don't know what these types should be, so we must return a validation error.
* Validate an unresolved external action entity or a request which applies to one. The fragment does not have the action's `appliesTo` definition.
* Validate any policies. There may be a path to allow validating some restricted set of policies as a future extension, but it does not have a clear motivation, and the soundness of such validation is not obvious. We would also need to consider the downstream effects on type-aware partial evaluation and policy analysis before committing to supporting this extension to policy validation.

### External ancestor types

An external entity appearing as an ancestor type is not as straightforward as using it in an attribute. For an attribute, the type definition is irrelevant. When used as an ancestor type, however, its parent types transitively determine the other valid ancestor types.

For example, given

```
external entity Folder;
entity Document in Folder;
```

and a separate definition of `Folder`,

```
entity Application;
entity Folder in Application;
```

we cannot tell from the document fragment that `Application` can be an ancestor of `Document`. Validating a `Document` with an `Application` ancestor using only this fragment must result in an error, not a warning, because we were unable to check its ancestor hierarchy.

For the same reason, linking the two schemas above also result in an error, because the linking enlarges the ancestor set of `Document`.

To reduce how often users encounter this error, we allow external entities to specify their parent types:

```
external entity Application;
external entity Folder in Application;
entity Document in Folder;
```

If parent types are declared, they are used to compute the transitive closure as if they were part of a complete entity type definition. Parent types from repeated external declarations are combined. When the concrete definition is linked, every declared parent type must also be a direct parent type in that definition; the concrete definition may have additional parent types, but not additional ancestors. If no parent types are declared, we conservatively treat the external entity type as having no known parent types.

A mismatch can only be detected when building the complete schema. Until then, an out-of-date fragment may be less permissive than the complete schema, but validation remains sound.

### External actions

We also support declaring external actions in the same way as entities. Action declarations have the same issue with ancestors, made more complicated because every action declaration in the schema defines a specific action entity, and validating an action entity requires its ancestors to exactly match the schema. If an external action has ancestors, every external declaration for that action must declare all of them. When schemas are combined, the declarations must agree and must exactly match the concrete action definition.

An external action can be referenced by other actions as an action group. We can validate those actions by checking that their ancestors exactly match the schema using the transitive closure, including the ancestors declared for the external action. We cannot validate the unresolved external action itself or a request which applies to it because its `appliesTo` definition is unknown.

## Syntax

I propose adding `external` as a new Cedar schema keyword. The keyword appears before the `entity` keyword, avoiding any ambiguity between the keyword and entity type names. In this example, we declare that `B` and `C` are entities, so we can resolve the entity type references in the definition of `A`. Note that the external entity declarations can be combined in the same way as regular entity declarations.

```
external entity B, C;
entity A in C {
  other: B
};
```

We can declare a namespaced external entity type just as we would define a namespaced type. The standard rules apply for qualifying the name in references.

```
namespace MyApp {
  external entity B;
  entity A {
    other: B
  };
}
entity C {
  other: MyApp::B
};
```

In a JSON schema the `external` keyword appears as a new attribute inside entity type or action JSON objects. An external entity may also include `memberOfTypes`.

```
"B": {
  "external": true,
  "memberOfTypes": ["C"]
}
```

An external action with ancestors must include them in `memberOf` and omits `appliesTo`.

```
"DeleteActions": {
  "external": true,
  "memberOf": [{ "id": "WriteActions" }]
}
```

We can declare an external action using the same syntax.

```
external action WriteActions;
external action DeleteActions in WriteActions;
action DeleteFile in DeleteActions;
```

Here we have defined two external action groups (`WriteActions` and `DeleteActions`) and defined our own action `DeleteFile` in these groups. This also demonstrates hierarchy membership for external declarations. An external action declaration must list all of its ancestors, while ancestor information is optional for an external entity declaration.

### Syntax alternatives

Following the same basic design, there are some alternative syntax options to consider.

* We could use a different keyword: `extern`, shorter, also used by C and Rust; `import`, perhaps wrongly gives the impression that we're loading in an entity definition from somewhere; `use`, similar to `import`.
* We could use an annotation (`@external`) instead of adding a keyword. This doesn't require any changes to the schema syntax, reducing implementation effort, but we have not previously used annotations for core language features. A related idea is to leave the language unchanged and rely on an annotation processor (or other preprocessor) supplied when constructing a schema, which would stub out the external entity types or import other fragments based on annotations. I don't like either approach because it lets an annotation change the semantics of the schema: whether a type is external would depend on how the schema was processed instead of on the schema text itself. I would rather reserve annotations for tooling and give `external` a first-class syntax, so that a fragment's meaning is self-contained.

## API

After the update, `SchemaFragment` remains the parsed input type and may contain arbitrary unresolved references, so it is not sufficient for validation.
Combining one or more `SchemaFragment`s and checking that every unresolved reference has a corresponding external declaration produces a `Schema`.
`Schema`s can be then used for linking, and the result of linking remains `Schema` that may contain external references.
Linking `schema` resolves external declarations with concrete definitions and checks the consistency rules described above.

The API also provides an `is_complete` function to check if a `Schema` has any remaining `external` declaration.
For any complete schema, validation behavior remains unaffected.
Sound entity validation and request validation are supported for incomplete schema.

## Formal Properties
The linker enjoys three major properties
- Order agnostic: Linking order does not affect the result of linking, but may produce different error messages. Type alias are resolved per-schema; so name shadowing caused by 
- Soundness: If a schema validates a request or an entity, it keeps doing so after any successful linking with any other schema.
- Completeness: If a schema does not validates a request or an entity, then there exists another schema that completes this schema when linked, and there exists a completion that causes the validation to fail.
In other words, request validation and entity validation cannot be more permissive without breaking soundness.

## Drawbacks

As discussed in [External ancestor types](#external-ancestor-types), a schema fragment may be _less permissive_ than the complete schema when an external entity declaration omits ancestor information or has not yet been updated. This limitation is not immediately a problem: by being more restrictive, entity validation with a schema fragment remains sound. However, this could be confusing to users or lead them to ignore this feature and explicitly include all type definitions anyway.

## Alternatives

* All undefined type names are assumed to be entity types. This isn't actually an alternative, but it's worth looking at why we can't do this. Schema fragments already have a meaning in which an undefined name may legitimately refer to a common type or action defined in another fragment. Assuming that every unresolved reference is an entity type would silently reinterpret those references and change the meaning of existing fragments, so a fragment could no longer be composed with the definitions it was actually written against. We might also frame this as a soundness issue — an entity that validated against a fragment could fail to validate against the complete schema.
* Add syntax for tagging the kind of type reference when it's used. E.g., `other: B::<entity>`. If `B` is defined as an entity, then it resolves to `B`, otherwise `B` is assumed to be external. This could also be useful for resolving ambiguity when a schema defines `B` as a common type and an entity type. I don't like this option because it doesn't explicitly say that `B` is external, just that it's an entity. We also wouldn't be able to detect simple typos like `Usr` instead of `User` before building the complete schema.
* Allow multiple identical entity type definitions while continuing to require a complete schema defining all entity types for all operations. As a compromise, we could allow re-definition of an entity type in different schemas as long as all definitions are identical. This would allow entity validation without loading all schema fragments by forcing each fragment to define all types relevant to it. This is not an attractive option because it would require a large amount of duplicated type definitions. Users who want this behavior could instead precompute and cache the set of schema fragments containing types relevant to each other fragment to enable more efficient loading without effectively storing multiple copies of each fragment.
