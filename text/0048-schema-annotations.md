# Annotations for Cedar Schemas

## Related issues and PRs

- Reference Issues:
- Implementation PR(s): https://github.com/cedar-policy/cedar/tree/feature/shaobo/rfc48

## Timeline

- Started: 2024-02-05

## Summary

Like Cedar policies, users may want to associate arbitrary, machine readable metadata with Schema objects.
We solved this problem in Cedar policies by allowing for *annotations*: arbitrary key/value pairs that are attachable to policies.
This could be extended to Cedar schemas, allowing users to attach attributes an entity type/common type/action declaration and attribute declaration.


## Basic example

Here is a basic example for doc comments.
```
@doc("this is the namespace")
namespace TinyTodo {
    @doc("a common type representing a task")
    type Task = {
        @doc("task id")
        "id": Long,
        "name": String,
        "state": String,
    };
    @doc("a common type representing a set of tasks")
    type Tasks = Set<Task>;

    @doc("an entity type representing a list")
    @docComment("any entity type is a child of type `Application`")
    entity List in [Application] = {
        @doc("editors of a list")
        "editors": Team,
        "name": String,
        "owner": User,
        @doc("readers of a list")
        "readers": Team,
        "tasks": Tasks,
    };

    @doc("actions that a user can operate on a list")
    action DeleteList, GetList, UpdateList appliesTo {
        principal: [User],
        resource: [List]
    };
}
```
The `@id("...")` notation is similar to the notation used for policy annotations.

## Motivation

Users should be allowed to associate machine readable metadata with objects in a Schema.
While we could create special syntax for associating particular kinds of metadata, we cannot
predict all of the metadata uses that users will have.
Thus providing a flexible system that users can adapt to their needs is preferable.
This proposal re-uses the same syntax from Cedar Policies, creating a unified syntax.


## Detailed design

### Semantics
Attributes have **no** impact on validation decisions.
Attributes are arbitrary key/value pairs where:
* 'key' is a valid Cedar identifier
* 'value' is a Cedar string


The Cedar spec takes no opinion or stance on the interpretation of annotations.
The interpretation is entirely up to users of Cedar.

### Cedar Schema Syntax
Attributes in Cedar Schemas will mirror the syntax used for attributes in a policy: informally that's `@<key>("value")`.
Formally the following rule is added to the Cedar grammar:
```
Annotation := '@' IDENT '(' STR ')'
Annotations := {Annotations}
```
With an arbitrary number of them being able to prepend to a namespace declaration, entity type declaration, common type declaration, action declaration, and an attribute declaration.

Thus the full schema syntax becomes:
```
Schema      := {Namespace}
Namespace   := (Annotations 'namespace' Path '{' {Decl} '}') | {Decl}
Decl        := Entity | Action | TypeDecl
Entity      := Annotations 'entity' Idents ['in' EntOrTyps] [['='] RecType] ';'
Action      := Annotations 'action' Names ['in' (Name | '[' [Names] ']')] [AppliesTo] [ActAttrs]';'
TypeDecl    := Annotations 'type' IDENT '=' Type ';'
Type        := PRIMTYPE | IDENT | SetType | RecType
EntType     := Path
SetType     := 'Set' '<' Type '>'
RecType     := '{' [AttrDecls] '}'
AttrDecls   := Annotations Name ['?'] ':' Type [',' | ',' AttrDecls]
AppliesTo   := 'appliesTo' '{' AppDecls '}'
ActAttrs    := 'attributes' '{' AttrDecls '}'
AppDecls    := ('principal' | 'resource') ':' EntOrTyps [',' | ',' AppDecls]
             | 'context' ':' RecType [',' | ',' AppDecls]
Path        := IDENT {'::' IDENT}
EntTypes    := Path {',' Path}
EntOrTyps   := EntType | '[' [EntTypes] ']'
Name        := IDENT | STR
Names       := Name {',' Name}
Idents      := IDENT {',' IDENT}
Annotation  := '@' IDENT '(' STR ')
Annotations := Annotation {Annotations}

IDENT       := ['_''a'-'z''A'-'Z']['_''a'-'z''A'-'Z''0'-'9']* - PRIMTYPE
STR         := Fully-escaped Unicode surrounded by '"'s
PRIMTYPE    := 'Long' | 'String' | 'Bool'
WHITESPC    := Unicode whitespace
COMMENT     := '//' ~NEWLINE* NEWLINE
```

### JSON Syntax
None of the three top-level constructs (EntityTypes, Actions, CommonTypes) in JSON schemas allow for arbitrary key/value pairs.
This means a new key can be safely added while preserving backwards compatibility.
The same fact also applies to entity attribute declarations.
This proposal reserves the `annotations` key at the top level of each of those constructs, which contains an Object, containing each annotation key as an Object key, associated with the annotation string.
The only oddness here is Common Types, whose toplevel is a regular type. While this should still be backwards compatible, it will look a little odd to have annotations in some types and not in others.

A corresponding JSON schema for the above example is as follows.
```JSON
{
    "": {
    "annotations": {
        "doc": "this is the namespace"
    },
    "commonTypes": {
        "Task": {
        "annotations": {
            "doc": "a common type representing a task"
        },
        "type": "Record",
        "attributes": {
            "id": {
            "type": "Long",
            "annotations": {
                "doc": "task id"
            },
            },
            "name": {
            "type": "String"
            },
            "state": {
            "type": "String"
            }
        }
        },
        "Tasks": {
        "type": "Set",
        "element": {
            "type": "Task"
        }
        }
    },
    "entityTypes": {
        "Application": {},
        "List": {
        "annotations": {
            "doc": "an entity type representing a list",
            "docComment": "any entity type is a child of type `Application`"
        },
        "memberOfTypes": [
            "Application"
        ],
        "shape": {
            "type": "Record",
            "attributes": {
            "editors": {
                "type": "Team"
            },
            "name": {
                "type": "String"
            },
            "owner": {
                "type": "User"
            },
            "readers": {
                "type": "Team"
            },
            "tasks": {
                "type": "Tasks"
            }
            }
        }
        }
    },
    "actions": {
        "CreateList": {
         "annotations": {
            "doc": "actions that a user can operate on a list"
        },
        "appliesTo": {
            "resourceTypes": [
            "Application"
            ],
            "principalTypes": [
            "User"
            ]
        }
       }
    }
  }
}
```

## Drawbacks

1. Complexity: adds more complexity to schema
2. Oddness around syntax for Common Types in JSON form
3. By not taking a stance on annotation meanings, it makes it harder for a standard to form around them (ex: for doc strings)
4. Multi-line docstrings are technically valid but awkward.

## Alternatives

### Take a stance
Reverse our decision around annotations and start taking stances on what annotations mean.
This lets us standardize certain annotations, like `doc`.
This probably can't happen unless we also do this for policies, which we've said we don't want to do.
### Doc Strings as comments
Instead of annotations, we could add "doc-strings" as a first class feature.
Could look like this:
```
/# Stop users from accessing a high security document unless:
/#  A) The principal and user are at the same location
/#  B) The principal has a job level greater than  4
forbid(principal, action, resource) when {
    resource.security_level == "HIGH"
unless {
    (resource.location == principal.location) || (principal.job_level > 4 )
};
```
This has nice and easy multi-line syntax, but is special cased and not as general.
