# Input Version Annotation

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started: 2013-10-13

## Summary

Reserve a way to indicate the Cedar version of an input format, so that future versions of Cedar can recognize and gracefully handle earlier input formats.

## Basic example

Cedar policies:
```
__cedar::version("3.0");
permit(principal,action,resource) when {
    principal is User && resource.owner == principal
};
```
JSON Cedar entities:
```
{
    "__cedar::version": "2.4",
    "contents": [
        {
            "uid": { "__entity": { "type": "User", "id": "alice"} },
            "attrs": {},
            "parents": [{ "__entity": { "type": "UserGroup", "id": "jane_friends"} }]
        }, ... 
    ]
}
```
JSON Cedar schema:
```
{
    "__cedar::version": "2.4",
    "PhotoApp": {
        "entityTypes": {
            "User": {
                "memberOfTypes": [
                    "UserGroup"
                ]
            }, ...
        },
        "actions": ...
    }
}
```
[Custom Cedar schema](0024-schema-syntax.md):
```
@__cedar::version("3.0");
entity UserGroup;
entity User in [UserGroup];
entity List {
    owner: User
};
```

## Motivation

Cedar will occasionally make breaking changes which invalidate prior Cedar input formats. For example [RFC 20](0020-unique-record-keys.md) requires that keys in records be unique, both in policies and in entities, whereas pre-RFC 20 they did not have to be. 

This RFC proposes to define annotations that signal the associated version of a particular input format, so that future versions of Cedar (or tools/services that use Cedar) can handle the situation gracefully. 

For example, by annotating a policy or JSON input file with version 2.4, the parser for Cedar version 3.0 can flag an input with a 2.4-only feature as no longer supported, rather than just failing to parse. Or, a service that uses Cedar can run multiple versions of the Cedar tools, selecting the version that matches the input version they are given.

## Detailed design

This RFC proposes a version annotation on Cedar's main input types: policies, entities (JSON), schema (JSON and custom). 

The design has two main goals:

- **Optional**: No version annotation is required. If none is given, the Cedar parser will assume the most recent version.

- **Uniform**: The way of specifying the version should be similar across all input formats, but also adhere to their particular style.

### Version string

Each input file will be associated with a version string. This is the version the input was written for, e.g., `"2.4.1"` or `"3.0"`. It could be that newer Cedar versions are compatible with older formats, but it is up to newer parsers to know that. For example, a new version of Cedar will add the [`is` operator](0005-is-operator.md) to policies, but an earlier version without that operator may still parse properly. The newer parser can account for this when parsing.

If an input file is annotated with an ill-formed version string, the parser should treat it as a version it does not know about, e.g., as if for a future version of Cedar. It can issue a warning and proceed. If an input file is version-annotated more than once, then the parser should signal an error.

### Policies and Custom Schema

For Cedar policies and custom schema syntax, we propose adding a new top-level declaration:
```
__cedar::version(XXX);
```
where `XXX` is a string with the version in it.

This declaration applies to all policies or schema elements that are parsed in the same file. It doesn't matter where the declaration is, in the file. If the declaration appears more than once, it is an error.

Here is the amended grammar for a policies file:
```
File    := {Policy | Version}
Version := '__cedar::version' '(' STRING ')' ';'
Policy  := {Annotation} Effect '(' Scope ')' {Conditions} ';'
...
```
Here is the amended grammar for a custom schema:
```
Schema    := {Namespace | Version}
Version   := '__cedar::version' '(' STRING ')' ';'
Namespace := ('namespace' Path '{' {Decl} '}') | {Decl}
...
```
In both cases there is the semantic constraint that `VERSION` appears at most once.

### Entities JSON

The Cedar entities JSON is now defined as an array of entity records. We propose to update it to be a record containing a version declaration followed by that array. In particular:
```
{
    "__cedar::version": XXX,
    "contents": [
        ...
    ]
}
```
That is, the `[ ... ]` part above is the same format the parser expects today.

Because version information is optional, the Cedar parser should still accept inputs of the form `[ ... ]`, i.e., a list of entities, assuming they are formatted in accord with the most recent version.

### Schema JSON

The Cedar schema JSON is now defined as a record whose elements are individual namespaces, i.e., 
```
{
    "Name::space::one": {
        ...
    },
    "Name::space::two": {
        ...
    }
}
```
We propose to extend this format so that one of the "namespace" elements can be `"__cedar::version"`, and it will be associated with the version string XXX, i.e.,
```
{
    "__cedar::version": XXX, 
    "Name::space::one": {
        ...
    },
    "Name::space::two": {
        ...
    }
}
```
This approach is unambiguous, and optional, because the namespace element `__cedar` is reserved, so no legal schema could define its own namespace containing `__cedar`. (This change was made as part of the [RFC 24](0024-schema-syntax.md).)

## Drawbacks

Implementing this RFC will add some complexity to the various Cedar parsers. They will now have to accept inputs that have a version annotation, and those that do not. They should also use that annotation to improve functionality and/or error messages, but such improvements do not have to come right away.

On the other hand, this RFC is essentially backward compatible -- the old, version-free format will still be accepted (assuming inputs do not rely on changes to format such as [RFC 20](0020-unique-record-keys.md)).

## Alternatives

We could consider versioning individual input elements, rather than whole input files. For example, we could have proposed to use metadata annotations like `@version("2.4.1")` as annotations on individual policies. However, this seems like overkill -- most likely all policies in one batch have the same version; if they do not, you can separate them into multiple batches.

The use of `__cedar::version` as the keyword to identify a version may look a little strange; we might prefer to just write `version` or `cedar_version`. The use of the version key with `__cedar` is crucial for supporting versioning in JSON-based schemas, and for uniformity we thought it best to use the same key everywhere. Also, the presence of `__cedar` in the keyword makes clear that it indicates the _Cedar language_ version, not a version associated with the application using Cedar.