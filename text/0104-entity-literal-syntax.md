# Entity literal syntax 

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

https://github.com/cedar-policy/cedar-examples/blob/85df878b68b0986d97433be14728858ae2a545ab/tinytodo/entities.json

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

a more compact syntax could be

```
namespace PhotoApp {
  instance User::"alice" in [UserGroup::"alice_friends", UserGroup::"AVTeam"] = {
      userId: "897345789237492878",
      personInformation: {
          age: 25,
          name: "alice"
      }
  };
  
  instance Photo::"vacationPhoto.jpg" = {
      private: false,
      account: Account::"ahmad"
  };
  
  instance UserGroup::"alice_friends" = {};
  instance UserGroup::"AVTeam" = {};
}
```

## Motivation

Developing and iterating on schemas and policies involves creating and modifying lists of entities in order to test policies, which is very cumbersome with the existing entity syntax in JSON:

* JSON has low information density. Cedar schema was able to provide significant increases in density and readability relative to the JSON syntax.
* JSON does not support comments. This means that any design intent for a schema cannot be expressed inline.

We believe that a custom syntax for entities can help. It can be more information-dense, support comments, and leverage familiar syntactic constructs. The success of Cedar syntax for schemas points to the value of this change could have.

## Detailed design

To be precise, we are defining a syntax that would allow for `Entities::from_cedar_str()` to parallel `Entities::from_json_str()` and so on. Some design goals are:

* Easy to write
* Consistency with policy and especially schema syntax
* Easy for parsers to differentiate from policy and schema
* Optionally, allow for reusable record (and maybe primitive) literals
* Optionally, if use cases exist for it, reusability of the syntax for inline literals in schemas and policies

Two potential options for syntax are listed below.

### Option 1: instance declarations

The schema syntax already defines a syntax for entity types where the values of parents and attributes are types, and actions are already sort of entity literals; replacing these with values provides the basis for this option. We would select a new keyword, using `instance` as an example (`entity` would be nice, but it's taken). This should make it easy to reuse the parsing for schema syntax (and make syntax highlighting straightforward), and the parser could identify when they were incorrectly used in schemas and vice versa.

```
namespace Namespace {
  instance SomeType::"entity_id" in [OtherNamespace::OtherType::"parent_entity_id"] = {
    attribute: "value"
  } tags {
    tagName: "tagValue"
  };
}

// subsequent declarations
```

The declaration style would make it possible to define and reference reusable records (which would need another keyword). The primary drawback is that the thing that is being defined, which is a set of entities, is only implicitly defined through the file itself. This makes sense for schema, but here it's maybe a bit weirder. On the other hand, while there is not currently a need for other information in the file, but this option would allow for that. This option also doesn't allow composition, if that's desirable.

### Option 2: instance expressions

The main alternative would be an inline syntax. As a separate syntax, it could look like this:

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

This would be more explicit that the content of the file is a set of entities and only a set of entities (like with JSON). It's a little less familiar/similar to schema syntax than Option 1, and might be harder to do useful syntax highlighting, but it is relatively close to how extension types like `datetime` are written. It opens up the possibility of composition within policies and schemas, but that is only relevant if that would ever be needed. This syntax doesn't allow for reusable records.

### Option 3: instance set declaration

A third alternative that would allow for inline literals _and_ reusable records would be to define a keyword for the set, say `entities`:

```
entities [
  Namespace::SomeType::"entity_id"([Namespace::OtherType::"parent_entity_id"], {
      attribute: "value",
      recordAttr: myRecord
    }, {
      tagName: "value"
    }),
  //subsequent entities
]

record myRecord = {
  foo: "bar"
};
```

This could allow for namespace blocks, but a complication is whether there can be multiple `entities` declarations in a file or only one.

## Drawbacks

There are several reasons not to develop a custom syntax:

### Multiple formats can raise cognitive burden

Adding another custom format raises the bar for what customers need to know. They may ignore one format at first, but eventually they may need to learn both. For example, if one team uses the JSON format and another uses the custom format, but then the teams merge, they will each end up having to read/update the other's format. They may also fight about which format to move to.

Mitigating this problem is that it's easy and predictable to convert between the two formats, since the syntactic concepts line up very closely. The features you lose when converting from the new format to the JSON one would be 1/ any comments, and 2/ any use of intermingling of `action`, `entity`, and `type` declarations, since they must all be in their own sections in the JSON. Otherwise the features line up very closely and the only difference is syntax. We would expect to write conversion tools as part of implementing the new syntax (which are easily achieved by parsing in the new format and pretty-printing in JSON).

### Requirement of good tooling

As a practical matter, having a custom entity literal syntax will require that we develop high-quality tools to help authors write in the syntax. 

Parse error messages need to be of good quality, and report common issues such as missing curly braces, missing semi-colons, incorrect keywords, etc. A formatting tool can help ensure standardized presentation. An IDE plugin can put these things together to provide interactive feedback. For the JSON syntax, IDE plugins already exist to flag parse errors and to format documents uniformly. 

TODO Note that the problem of matching up curly braces in JSON-formatted schemas is more acute than in the custom syntax, since it's common to have deep nesting levels where matching is hard to eyeball. For example, in the `TinyTodo` JSON example, we have up to seven levels of direct nesting of curly braces, whereas the custom syntax has only three, and these levels are more visually isolated because of the other syntax in between them.

### Greater implementation cost

Supporting a new syntax is an extra implementation cost, including the new tools mentioned above, now and going forward. More code/tools means more potential for bugs. 

## Alternatives

One alternative would be to _replace_ the current JSON-based sytnax with the one in this proposal. This proposal would avoid the "cognitive burden" drawback mentioned above, but would be a disruptive, backward-incompatible change, and would lose the JSON format's benefits of existing tooling and easier programmatic schema construction.

Another alternative would be to adopt a [Yaml](https://en.wikipedia.org/wiki/YAML)-based syntax. This approach would meet our goals of greater information density and support for comments, and it would come with some existing tooling (such as IDE extensions). A downside of Yaml is that it provides _more_ than we need, with a lack of conciseness leading to confusing. We could make our own parser for a subset of Yaml we wish to support for schemas, but that may lead to a confusing user experience. Yaml's indentation-sensitive parsing also means that an indentation mistake will be silently accepted, leading to a confusing user experience. Our custom syntax is whitespace-insensitive, and having total control over the grammar means better context for error messages.

## Unresolved questions

The syntax design needs feedback and iteration.
