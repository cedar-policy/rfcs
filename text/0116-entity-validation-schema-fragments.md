# Entity Validation with Schema Fragments

## Related issues and PRs

- Reference Issues: (none)
- Implementation PR(s): (leave this empty)

## Timeline

- Started: 2026-07-08
- Accepted: TBD
- Stabilized: TBD

## Summary

This RFC proposes an extension to Cedar schema (in both JSON and human-readable Cedar syntax) to enable _soundly_ validating Cedar entities given a schema fragment (a partial Cedar schema that may reference undefined entity types). The extension introduces an `external` keyword that allows schema authors to declare entity types without providing their full definitions, enabling validation of entities that reference these types without requiring all schema fragments to be loaded.

## Basic example

The following schema declares an entity type `User` without defining its attributes, tags, or ancestor types. It then uses this type to define the `owner` attribute for the `Document` entity.

```
external entity User;
entity Document {
  owner: User
};
```

Even though we know nothing about the `User` entity type, we can use this schema to validate a `Document` entity. To validate the `owner` attribute, we check that the value is the `User` entity type. We do not need the full definition of `User` (i.e., its attributes) to conclude that it is valid. For example, we know the following `Document` entity is valid because the entity type of its `owner` is `User`.

```
{
    "uid": { "__entity": { "type": "Document", "id": "file.txt"} },
    "attrs": {
        "owner": { "__entity": { "type": "User", "id": "alice"} }
    },
    "parents": []
}
```

If the `owner` entity type is not `User`, then we know that the `Document` entity is not valid. For example:

```
{
    "uid": { "__entity": { "type": "Document", "id": "report.pdf"} },
    "attrs": {
        // error: Expected entity type `User`, saw `Account`
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

We will introduce a new keyword which declares an "external" entity type, a type name declared to be an entity type without defining its attribute, tag, or ancestor types. Once declared as external in a schema fragment, we know that the name refers to an entity type (not a common type or builtin type), so the rest of that fragment can use the external entity type in the same way as any other. For example, a schema author can have an entity type where the attributes or tags are defined in terms of external entity types.

When combining multiple fragments, we will attempt to link external entity type declarations with concrete definitions. Entity types are linked when their names match precisely (accounting for any containing namespace), but may never be linked with a builtin or common type definition even if the names are the same. An entity type may be declared as external any number of times, but it may only have one concrete definition across all schema fragments. If there is a definition, then that entity type becomes concrete in the resulting fragment, and is treated exactly the same as any other entity type. When there is no concrete definition the entity type remains external in the resulting fragment, but we do not report an error.

If every external entity type in a fragment has a corresponding definition, then the fragment is fully concrete. We can construct a complete `Schema` from it and use it exactly as if there were no external entity type declarations. In this situation, external declarations act as a helpful tool for schema authors to explicitly specify the dependencies between different schema fragments, but could be omitted entirely.

Otherwise, we have a fragment where some entity type declarations do not have a corresponding definition. We cannot construct a complete `Schema` from such a fragment, which limits what we can do with it.

**We can:**

* Validate instances of any defined entity types, even if these entities contain references to an undefined entity type in their attributes or tags. To validate these attributes we only need to check that the actual attribute value has the expected entity type name.
* Validate authorization requests. Validating the context is the same as validating an entity's attributes. If the context contains an entity reference, we do not need the definition of that entity type. Validating the `principal`, `action`, and `resource` of the request requires the definition of the `action`, which will enumerate the allowed `principal` and `resource` types. We don't necessarily need the definitions for these types, as we only check that the variables have the expected entity type. However, we _do_ need these definitions if we also want to validate the particular entity instance which the variables refer to.

**We cannot:**

* Validate an instance of an undefined external entity type. To validate an entity, we check that its attributes, tags, and ancestors have their expected types. We don't know what these types should be, so we must return a validation error.
* Validate any policies. There may be a path to allow validating some restricted set of policies as a future extension, but it does not have a clear motivation, and the soundness of such validation is not obvious. We would also need to consider the downstream effects on type aware partial evaluation and policy analysis before committing to supporting this extension to policy validation.

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

In a JSON schema the `external` keyword appears as a new attribute inside entity type JSON objects.

```
"B": { "external": true }
```

### Syntax alternatives

Following the same basic design, there are some alternative syntax options to consider.

* We could use a different keyword: `extern`, shorter, also used by C and Rust; `import`, perhaps wrongly gives the impression that we're loading in an entity definition from somewhere; `use`, similar to `import`.
* We could use an annotation (`@external`) instead of adding a keyword. This doesn't require any changes to the schema syntax, reducing implementation effort, but we have not previously used annotations for core language features. A related idea is to leave the language unchanged and rely on an annotation processor (or other preprocessor) supplied when constructing a schema, which would stub out the external entity types or import other fragments based on annotations. I don't like either approach because it lets an annotation change the semantics of the schema: whether a type is external would depend on how the schema was processed instead of on the schema text itself. I would rather reserve annotations for tooling and give `external` a first-class syntax, so that a fragment's meaning is self-contained.

## API

We can reflect the distinction between an incomplete and a complete schema in the type system. `SchemaFragment` is the type for a schema that may contain unresolved external references, and it is the type we can use to validate entities. Even when some external entity types have no definition, a `SchemaFragment` carries enough information to validate instances of its defined entity types and to validate authorization requests, as described above. Combining multiple `SchemaFragment`s links external declarations with their definitions and yields another `SchemaFragment`.

`Schema` represents only a complete schema, meaning every external entity type has a corresponding definition. A `Schema` can be constructed from a `SchemaFragment` only when there are no unresolved external references, and it is the type required for validating policies and for downstream tooling like type aware partial evaluation and policy analysis. Because a `Schema` is always complete, these consumers never have to reason about undefined entity types.

## Drawbacks

As discussed in-depth in the unresolved questions section, there are some situations around external entity types in ancestor entity type lists where a schema fragment may be _less permissive_ than the complete schema with all types defined. This limitation is not immediately a problem: by being more restrictive, entity validation with a schema fragment remains sound. However, this could be confusing to users, or lead users to ignore this feature and explicitly include all type definitions anyways.

## Alternatives

* All undefined type names are assumed to be entity types. This isn't actually an alternative, but it's worth looking at why we can't do this. Schema fragments already have a meaning in which an undefined name may legitimately refer to a common type or action defined in another fragment. Assuming that every unresolved reference is an entity type would silently reinterpret those references and change the meaning of existing fragments, so a fragment could no longer be composed with the definitions it was actually written against. We might also frame this as a soundness issue — an entity that validated against a fragment could fail to validate against the complete schema.
* Add syntax for tagging the kind of type reference when it's used. E.g., `other: B::<entity>`. If `B` is defined as an entity, then it resolves to `B`, otherwise `B` is assumed to be external. This could also be useful for resolving ambiguity when a schema defines `B` as a common type and an entity type. I don't like this option because it doesn't explicitly say that `B` is external, just that it's an entity. We also wouldn't be able to detect simple typos like `Usr` instead of `User` before building the complete schema.
* Allow multiple identical entity type definitions while continuing to require a complete schema defining all entity types for all operations. As a compromise, we could allow re-definition of an entity type in different schemas as long as all definitions are identical. This would allow entity validation without loading all schema fragments by forcing each fragment to define all types relevant to it. This is not an attractive option because it would require a large amount of duplicated type definitions. Users who want this behavior could instead precompute and cache the set of schema fragments containing types relevant to each other fragment to enable more efficient loading without effectively storing multiple copies of each fragment.

## Unresolved questions

Given two schema fragments, first for documents,

```
external entity Folder;
entity Document in Folder;
```

and second for folders,

```
external entity Application;
entity Folder in Application;
```

I have a `Document` entity which I want to validate. The transitive closure of its parents is already computed, so it has a `Folder` and `Application` in its list of parents. But, just by looking at the document schema, we don't know that an `Application` can be an ancestor of a `Document`.

```
{
    "uid": { "__entity": { "type": "Document", "id": "file.txt"} },
    "attrs": { },
    "parents": [
        {"__entity": { "type": "Application", "id": "my_app"}}
    ]
}
```

Validating this entity using only the `Document` schema fragment results in a validation error, even though it validates successfully when using a complete schema formed from both fragments. This limitation is not immediately a problem: by being more restrictive, entity validation with a schema fragment remains sound. It also should not be entirely surprising that validation is less capable when given incomplete information. Nonetheless, this is likely to be a pain point for users.

This case must be a validation error, not a warning. If we only reported a warning, an entity could _validate_ against a schema fragment even though we were unable to check its ancestor hierarchy. Downstream tooling like policy analysis relies on successful validation as a precondition, so weakening entity validation to a warning would break the guarantees these consumers depend on. The unresolved question is not whether to report an error, but how to reduce how often users encounter it.

### Workarounds

There is a reasonable workaround for this issue, so we don't necessarily have to change anything about the current design. The problem goes away if users of Cedar are okay with collecting all relevant schema fragments before validating an entity store. In other words, users can ignore this RFC and continue using Cedar as they currently do. However, this conflicts with the motivation for this RFC: depending on how entity data and schemas are stored, it may be difficult to efficiently gather all relevant fragments for validation.

The Cedar library could make loading relevant fragments easier by providing a method on schema fragments which would list the entity types referenced in a schema, making it easier to know what additional schema fragments need to be retrieved. It may still be necessary to load many different fragments to get all type definitions, but would make it easier to preload the relevant fragments.

If loading multiple fragments is simply not an option, users can still work around this issue by modifying the schema to make transitive relations between entity types explicit. For example, the relation between `Document` and `Application` was previously implicit based on the transitive nature of the entity hierarchy. We can modify the schema to make this explicit:

```
external entity Folder, Application;
entity Document in Folder, Application;
```

Now that `Application` is declared and specified to be a valid parent of `Document`, the entity `Document::"file.txt"` validates as expected. This new fragment is semantically equivalent to the original fragment once it has been composed to form a complete schema. This workaround however makes customers replicate parts of their entity hierarchy in every fragment that needs it. A change to `Application` or `Folder` to allow for more parent entity types would require a corresponding change to the `Document` schema before being reflected in `Document` entity validation.

### External entity parents

Instead of declaring ancestors in-line, we could add syntactic support for (optionally) defining the parent types of external entities.

```
external entity Application;
external entity Folder in Application;
entity Document in Folder;
```

If parent types are defined, then they will be used to compute the transitive closure as if they were complete entity type definitions. When not defined, we keep the original behavior, treating the external entity type as having no parent types.

Even in this variant, an external declaration may specify _only_ its parent types, never its attributes or tags. The attributes and tags are exactly the information we intend to omit from a schema fragment, so allowing them would blur the line between an external declaration and a full definition. Ancestor types are a special case because we need them to soundly compute the transitive closure of the entity hierarchy.

This maintains the original structure of the hierarchy, making updates to this copy easier, but does not change the fact that the hierarchy is copied between the different schema fragments. It gives us a convenient way to check the consistency of the hierarchy when composing the complete schema. By checking that `Folder` actually has `Application` as a parent we can ensure that updates to the entity type hierarchy have been made everywhere consistently. If `Application` is later removed as an ancestor of `Folder` without updating the external declaration, we will report an error when composing the complete schema, which we could not do if users have to work around the issue themselves. However, this error can _only_ be detected when building the complete schema. If a user doesn't update a schema fragment and later validates an entity with that fragment, we would still be unable to detect the inconsistency because we would not have the entity type definition to compare against.

## External actions (possible extension)

This RFC proposes external entity declarations to satisfy the most obvious use cases for validating entity data with a schema fragment, but the same idea could be generalized to external action declaration if it becomes necessary.
I don't currently propose accepting this extension as part of this RFC.

An external action could be declared using the same keyword (`external action edit`).
This declares an action `Action::"edit"` for the rest of the fragment to reference without providing its definition.
It would be a validation error to include this action entity in entities being validated.
The schema doesn't fully define it, so we cannot validate that the definition in the entities matches the schema.

Using this action, we could define group membership of other actions in terms of external actions.

```
external action edit;
action other in [edit];
```

Here `Action::"other"` is a member of the `edit` action group.
In the corresponding entity data, we could validate an instance of `Action::"other"` by checking that it has exactly `Action::"edit"` as its declared ancestors.
This has the same problem as the entity type hierarchy: without the definition of `edit` we do not know its transitive ancestors, so the fragment may be less permissive than the complete schema.

Actions are entities, so we allow references to the action entity type in attributes.

```
external action Shared::Action::"edit";
entity User {
  my_actions: Set<Shared::Action>
};
```

To validate a `User` entity we would check that all elements of `my_actions` are one of the declared instances of `Shared::Action`.

We could not validate a request which applies to an external action.
