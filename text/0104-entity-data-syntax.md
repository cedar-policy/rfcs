# Cedar syntax for entity data

## Related issues and PRs

- Reference Issues: [#102](https://github.com/cedar-policy/rfcs/issues/102), [RFC24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md)
- Implementation PR(s): (leave this empty)

## Timeline

- Started: 2025-08-20
- Accepted: TBD
- Stabilized: TBD

## Summary

This document proposes a custom syntax for entity literals. This follows RFC24, which did the same for schemas. The summary, motivation, drawbacks and alternatives are largely copied from RFC24 as this RFC is very similar in these respects.

The syntax was developed with the following goals in mind:

* Use the same concepts in both the JSON-based and custom syntax, allowing them to be naturally inter-converted
* Reuse Cedar policy/schema syntax as much as possible, to help with intuition
* When no Cedar policy/schema syntax analogue exists, leverage ideas from other programming languages that favor readability
* Use as few syntactic concepts as possible; similar ideas in the schema should look similar syntactically
* Support converting back and forth between the JSON-based schema without losing information

This is _not_ a proposal to _replace_ the JSON-based syntax; the aim is to provide an additional syntax that better satisfies the goals above. The JSON syntax is appropriate in many circumstances, such as when constructing entities programmatically (the usual case for a runtime system). Adopting this approach would allow for development-time ease of use, especially during exploration and iteration on schemas.

## Basic example

The default list of entities that's populated in the Cedar playground for the photo sharing app is 57 lines of JSON:

```json
[
    {
        "uid": {
            "type": "PhotoApp::User",
            "id": "alice"
        },
        "attrs": {
            "userId": "897345789237492878",
            "personInformation": {
                "age": 25,
                "name": "alice"
            }
        },
        "parents": [
            {
                "type": "PhotoApp::UserGroup",
                "id": "alice_friends"
            },
            {
                "type": "PhotoApp::UserGroup",
                "id": "AVTeam"
            }
        ]
    },
    {
        "uid": {
            "type": "PhotoApp::Photo",
            "id": "vacationPhoto.jpg"
        },
        "attrs": {
            "private": false,
            "account": {
                "__entity": {
                    "type": "PhotoApp::Account",
                    "id": "ahmad"
                }
            }
        },
        "parents": []
    },
    {
        "uid": {
            "type": "PhotoApp::UserGroup",
            "id": "alice_friends"
        },
        "attrs": {},
        "parents": []
    },
    {
        "uid": {
            "type": "PhotoApp::UserGroup",
            "id": "AVTeam"
        },
        "attrs": {},
        "parents": []
    }
]
```

with this proposal, it could be represented compactly as follows:

```
namespace PhotoApp {
  entity User instance "alice" in [UserGroup::"alice_friends", UserGroup::"AVTeam"] {
      userId: "897345789237492878",
      personInformation: {
          age: 25,
          name: "alice"
      }
  };

  entity Photo instance "vacationPhoto.jpg" {
      private: false,
      account: Account::"ahmad"
  };

  entity UserGroup instances [
    "alice_friends",
    "AVTeam"
  ];
}
```

## Motivation

Developing and iterating on schemas and policies involves creating and modifying lists of entities in order to test policies, which is very cumbersome with the existing entity syntax in JSON:

* JSON has low information density. Cedar schema was able to provide significant increases in density and readability relative to the JSON syntax.
* JSON does not support comments, which can be useful when defining a collection of entities and their relationships.

This stands as an obstacle to Cedar adoption. New users want to experiment with Cedar before they use it, and a critical step before a successful test of an authorization request is defining the entities for the request. Doing this in JSON is cumbersome and imposing. Smoothing this process will create better first impressions of Cedar.

The JSON syntax for entities also creates friction during the development of a Cedar schema. To test a schema, entities that conform to the schema must be defined. JSON is inconvenient enough for doing this once by hand, but when iterating on the schema, the entities often need to be updated, and the JSON syntax again makes this cumbersome.

The JSON syntax is _not_ an impediment for the final implementation of a system using Cedar, but the provision of a more human-readable format can still be of use when debugging such systems.

We believe that a custom syntax for entities can help. It can be more information-dense, support comments, and leverage familiar syntactic constructs. The success of Cedar syntax for schemas points to the value of this change could have.

## Detailed design

To be precise, we are defining a syntax that would allow for `Entities::from_cedar_str()` to parallel `Entities::from_json_str()` and so on. Some design goals are:

* Easy to write
* Consistency with policy and especially schema syntax
* Easy for parsers to differentiate from policy and schema

The schema syntax already defines a syntax for entity types where the values of parents and attributes are types, and actions are already sort of entity literals; replacing these with values provides the basis for this option.

### Comments

Instance declarations can use line-ending comments in the same style as Cedar schemas and policies, e.g., `// this is a comment`.

### Namespace format

Namespaces are identical to schemas. Nested namespaces should be allowed if and when they are allowed in schemas in the future.

```
namespace My::Namespace {
  ...
}
```

### Instance declarations

Instance declarations use the `instance` keyword (or `instances`, see below) after an entity type written as `entity {entityType}`. This allows for a potential future where instances could be declared after a full entity type declaration.

Instance declarations look largely like entity type declarations, but use literals rather than types as the values.

```
entity SomeType1 instance "entity_id_1" = {
  attribute: "value"
};
```

Like entity type declarations, the `=` is optional, and instances without attributes can be declared without a record.

```
entity SomeType1 instance "entity_id_2" {
  attribute: "value"
};

entity SomeType1 instance "entity_id_3";
```

Parents are defined like in entity type declarations, but use entity identifiers rather than types. Tags are similar.

```
entity SomeType1 instance "entity_id_4" in [OtherType::"parent_entity_id"] {
  attribute: "value"
} tags {
  tagName: "tagValue"
};
```

### Multiple instances in one declaration

For convenience, multiple instances can be defined without repeating the entity type using the `instances` keyword followed by a list of instances. These instances follow the same syntax except that `=` is not permissible.

```
entity SomeType1 instances [
  "entity_id_5" {
    attribute: "value"
  },
  "entity_id_6" in [OtherType::"parent_entity_id"] {
    attribute: "value"
  } tags {
    tagName: "tagValue"
  },
  "entity_id_7" {},
  "entity_id_8"
];
```

```
// syntax error
entity SomeType2 instances [
  "entity_id_9" = {
    attribute: "value"
  }
];
```

### Grammar

```
Entities := {NamespaceOrEntityDeclaration}
NamespaceOrEntityDeclaration := Namespace | EntityDeclaration
Namespace := 'namespace' Path '{' {EntityDeclaration} '}'
EntityDeclaration := EntityInstanceDeclaration | EntityInstancesDeclaration

EntityInstanceDeclaration := 'entity' Path 'instance' EntityInstance ';'
EntityInstance := Name ['in' EntityRefOrRefs] [['='] Record] ['tags' Tags]

EntityInstancesDeclaration := 'entity' Path 'instances' '[' EntityInstanceNoEqualsList ']' ';'
EntityInstanceNoEqualsList := EntityInstanceNoEquals {',' EntityInstanceNoEquals}
EntityInstanceNoEquals := Name ['in' EntityRefOrRefs] [Record] ['tags' Tags]

Path := IDENT {'::' IDENT}
Name := STR
EntityRefOrRefs := EntityRef | '[' [EntityRefOrRefs] ']'
EntityRef := Path '::' STR

Record := '{' [KeyValues] '}'
KeyValues := Key ':' Value [',' | ',' KeyValues]
Key := IDENT | STR
Value := // TODO: scoped down from policy grammar, also need some bits from schema grammar

Tags := Record

IDENT     := ['_''a'-'z''A'-'Z']['_''a'-'z''A'-'Z''0'-'9']*
STR       := Fully-escaped Unicode surrounded by '"'s
```

## Potential future additions

Not addressed in this proposal but open for future improvement:

* Deduplication of values, e.g. similar to common types in schemas, the ability to define a record once and use it in multiple instances
* Annotations
* Intermixing of policies, instances, and/or schema in a single file
  * Note the syntax leaves open the possibility for instances to be declared inline with a full entity type declaration

## Drawbacks

There are several reasons not to develop a custom syntax:

### Multiple formats can raise cognitive burden

Adding another custom format raises the bar for what customers need to know. They may ignore one format at first, but eventually they may need to learn both. For example, if one team uses the JSON format and another uses the custom format, but then the teams merge, they will each end up having to read/update the other's format. They may also fight about which format to move to.

Mitigating this problem is that it's easy and predictable to convert between the two formats, since the syntactic concepts line up very closely. The features you lose when converting from the new format to the JSON one would be 1/ any comments, and 2/ any use of intermingling of `action`, `entity`, and `type` declarations, since they must all be in their own sections in the JSON. Otherwise the features line up very closely and the only difference is syntax. We would expect to write conversion tools as part of implementing the new syntax (which are easily achieved by parsing in the new format and pretty-printing in JSON).

### Requirement of good tooling

As a practical matter, having a custom entity literal syntax will require that we develop high-quality tools to help authors write in the syntax.

Parse error messages need to be of good quality, and report common issues such as missing curly braces, missing semi-colons, incorrect keywords, etc. A formatting tool can help ensure standardized presentation. An IDE plugin can put these things together to provide interactive feedback. For the JSON syntax, IDE plugins already exist to flag parse errors and to format documents uniformly.

### Greater implementation cost

Supporting a new syntax is an extra implementation cost, including the new tools mentioned above, now and going forward. More code/tools means more potential for bugs.

## Appendix A: Alternatives

### Replacing the JSON syntax

One alternative would be to _replace_ the current JSON-based syntax with the one in this proposal. This proposal would avoid the "cognitive burden" drawback mentioned above, but would be a disruptive, backward-incompatible change, and would lose the JSON format's benefits of existing tooling and easier programmatic entity instance construction.

Another alternative would be to adopt a [Yaml](https://en.wikipedia.org/wiki/YAML)-based syntax. This approach would meet our goals of greater information density and support for comments, and it would come with some existing tooling (such as IDE extensions). A downside of Yaml is that it provides _more_ than we need, with a lack of conciseness leading to confusing. We could make our own parser for a subset of Yaml we wish to support for schemas, but that may lead to a confusing user experience. Yaml's indentation-sensitive parsing also means that an indentation mistake will be silently accepted, leading to a confusing user experience. Our custom syntax is whitespace-insensitive, and having total control over the grammar means better context for error messages.

### Instance expressions

Instances could be defined using expressions. It's a little less familiar/similar to schema syntax than the selected design, and might be harder to do useful syntax highlighting, but it is relatively close to how extension types like `datetime` are written. It opens up the possibility of composition within policies and schemas, but that is only relevant if that would ever be needed. This syntax doesn't allow for reusable records.

The syntax could be a file containing a simple list of instances. This would be more explicit that the content of the file is a set of entities and only a set of entities (like with JSON).

```
[
  Namespace::SomeType::"entity_id"([Namespace::OtherType::"parent_entity_id"], {
      attribute: "value"
    }, {
      tagName: "value"
    }),
  //subsequent entities
]
```

The syntax could alternatively use a keyword to make it a declaration, which would allow for reusable records.

```
entities [
  Namespace::SomeType::"entity_id"([Namespace::OtherType::"parent_entity_id"], {
      attribute: "value",
    }, {
      tagName: "value"
    }),
  //subsequent entities
]
```

This could allow for namespace blocks, but a complication is whether there could be multiple `entities` declarations in a file or only one.
