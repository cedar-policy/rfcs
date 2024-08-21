# Trailing Commas

## Related issues and PRs

- Reference Issues: https://github.com/cedar-policy/cedar/issues/1024
- Implementation PR(s):

## Timeline

- Started: 2024-06-26 

## Summary

The Cedar grammar (both policies and schemas) should accept trailing
commas whenever possible.

## Basic example

Currently, this is a parse error:
```
permit(principal, action, resource) when {
    { foo : 3, bar : 2, } == context  
};
```
This RFC would make it not a parse error. 
It would also change this is several places beyond records.

## Motivation

In general, allowing trailing commas makes editing easier.
Re-arranging, deleting, and copy-pasting code into/from a comma
separated grammar element will no longer require adjusting commas.

Example:
```
{
    "managers": ["Dave", "Shelly", "Chris"],
    "projects" : {
        "Alpha" : {
            "zones" : ["A", "B"]
        },
        "Beta" : {
            "zones" : ["D", "F"]
        }
    }
}
```
The `Beta` project cannot simply be deleted from this record, and
likewise, new fields cannot be simply pasted into any level of the
objects, without adjusting commas.

Many languages allow for trailing commas, including:
* Rust
* Python
* Java,
* Go
* JavaScript
* OCaml

(Frustratingly: not JSON!)

In addition, it will make our schema grammar and policy grammar more
consistent, as the schema grammar allows trailing commas in many places.

## Detailed design

### Cedar Policy Grammar

We want to allow trailing commas in the following expressions:
1. scopes: `permit(principal, action, resource, )` 
2. sets: `[1,2,3,]`
3. records: `{ foo : 1, bar : 3, }`
4. all method/function calls: `.contains(3,)`, `ip("10.10.10.10",)`

In the grammar:

The following grammar rules change:
```
Scope ::= Principal ',' Action ',' Resource
```
becomes:
```
Scope ::= Principal ',' Action ',' Resource ','?
```

```
EntList ::= Entity {',' Entity}
```
becomes:
```
EntList ::= Entity {',' | ',' Entity} ','?
```

```
ExprList ::= Expr {',' Expr}
```
becomes:
```
ExprList ::= Expr {',' | ',' Expr} ','?
```

```
RecInits ::= (IDENT | STR) ':' Expr {',' (IDENT | STR) ':' Expr}
```
becomes:
```
RecInits ::= (IDENT | STR) ':' Expr {',' | ',' (IDENT | STR) ':' Expr}
```

### Cedar Schema Grammar
The schema grammar already allows trailing commas in several places
(such as record types and entity lists), but not everywhere:

We want to allow trailing commas in the following expressions:
1. membership lists: `entity Photo in [Account, Album,];`
2. Multi-entity declarations: `entity Photo,Video;`
3. Record types: `{ foo : Long, bar : String, }` (currently allowed)
4. Multi-action declarations: `action foo,bar,;`
5. Apply specs: `appliesTo { principal : ["A"], resource: ["B"],"`
   (currently allowed)


```
EntTypes  := Path {',' Path}
```
becomes:

```
EntTypes  := Path {',' | ',' Path}
```

```
Names     := Name {',' Name}
```
becomes:
```
Names     := Name {',' | ',' Name} ','?
```

```
Idents    := IDENT {',' IDENT}
```
becomes:
```
Idents    := IDENT {',' | ',' IDENT}
```


### Backwards Compatibility 
This change is fully backwards compatible. 

## Drawbacks

* Trailing commas are potentially confusing.

## Alternatives

* Keep status quo: this is a non critical change

## Unresolved questions
