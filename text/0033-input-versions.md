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
@cedar_version("3.0");
permit(principal,action,resource) when {
    principal is User && resource.owner == principal
};
```
JSON Cedar entities:
```
{
    "@cedar_version": "2.4",
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
    "@cedar_version": "2.4",
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
@cedar_version("3.0");
entity UserGroup;
entity User in [UserGroup];
entity List {
    owner: User
};
```

## Motivation

Cedar will occasionally make breaking changes which invalidate prior Cedar input formats. For example [RFC 20](0020-unique-record-keys.md) requires that keys in records be unique, both in policies and in entities, whereas pre-RFC 20 they did not have to be. 

This RFC proposes to define annotations that signal the associated version of a particular input format, so that future versions of Cedar (or tools/services that use Cedar) can handle the situation gracefully.

This RFC makes no specification about what "gracefully" means, but minimally it can be used to indicate that parse errors might be due to version format incompatibilities. For example, by annotating a policy or JSON input file with version 2.4, the parser for Cedar version 3.0 can flag an input with a 2.4-only feature as no longer supported, rather than just failing to parse. Or, a service that uses Cedar can run multiple versions of the Cedar tools, selecting the version that matches the input version they are given.

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
@cedar_version(XXX);
```
where `XXX` is a string with the version in it.

This declaration applies to all policies or schema elements that are parsed in the same file. It doesn't matter where the declaration is, in the file. If the declaration appears more than once, it is an error.

Here is the amended grammar for a policies file:
```
File    := {Policy | Version}
Version := '@cedar_version' '(' STRING ')' ';'
Policy  := {Annotation} Effect '(' Scope ')' {Conditions} ';'
...
```
Here is the amended grammar for a custom schema:
```
Schema    := {Namespace | Version}
Version   := '@cedar_version' '(' STRING ')' ';'
Namespace := ('namespace' Path '{' {Decl} '}') | {Decl}
...
```
In both cases there is the semantic constraint that `Version` appears at most once.

### Entities JSON

The Cedar entities JSON is now defined as an array of entity records. We propose to update it to be a record containing a version declaration followed by that array. In particular:
```
{
    "@cedar_version": XXX,
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
We propose to extend this format so that one of the "namespace" elements can be `"@cedar_version"`, and it will be associated with the version string XXX, i.e.,
```
{
    "@cedar_version": XXX,
    "Name::space::one": {
        ...
    },
    "Name::space::two": {
        ...
    }
}
```
This approach is unambiguous, and optional, because the element `@cedar_version` cannot be misinterpreted as a namespace, since `@` is not allowed to appear in a namespace identifier.

### Compatibility

The old, version-free format will still be accepted assuming inputs do not rely on changes to format such as [RFC 20](0020-unique-record-keys.md).

## Drawbacks

Implementing this RFC will add some complexity to the various Cedar parsers. They will now have to accept inputs that have a version annotation, and those that do not. They will have to minimally use that annotation to improve functionality and/or error messages. Doing this requires thinking carefully about the meaning of an annotation (e.g., what span of versions use the same format).

The presence of a version annotation may imply more than this RFC is actually offering, leading to customer confusion or disappointment. For example, customers may expect that the current parser can parse and properly interpret all formats up to the present one, rather than reject those earlier formats (gracefully).

Adding an annotation adds some maintenance burden on customers. When a version annotation is present in a policy file, if the policies are changed to use a newer version of Cedar, the version annotation needs to be changed; it is not hard to forget to do so.

If an input format changes in a way that older syntax is interpreted differently, such as the `appliesTo` in the JSON schema as per the request in [issue 351](https://github.com/cedar-policy/cedar/issues/351), the fact that a version annotation is optional presents a problem: A newer and older parser could both accept the same input, but interpret it differently. If a version annotation was required, such an ambiguous interpretation would not be possible.

## Alternatives

### Do nothing to Cedar; version info can appear in application metadata

Rather than add a version annotation in the Cedar input syntax directly, version information can just be stored in metadata. For example, an application could store Cedar schemas in a document database and use a format like
```
{
    "cedar_verson": "3.1.0",
    "schema" : {
        "foo::bar" {
            "entityTypes" : { ... },
            "actions": { ... }
        }
    }
}
```
Such annotations could then trigger different application actions, e.g., calling different versions of the Cedar evaluator.

Versioning is especially useful when the same syntax is interpreted differently in later versions. This situation should be (very) rare, though. When it happens, the newer parser can warn about the change in syntax, especially in the case of errors that would trigger due to the change.

### Change, or drop, the policy annotation format

The use of `;` to distinguish per-policy annotations from file-wide policy annotations may be too subtle. Users could mistakenly write the following:
```
@cedar_version("2.4.0")
permit(
    principal == User::"Alice",
    action == Action::"viewPhoto",
    resource == Photo::"vacation97.jpg"
);
```
They might think that the version applies to the whole file, but the lack of a semi-colon means the annotation just applies to the given policy.

To avoid this problem, we could require a distinct syntax for file-wide annotations, e.g., `#foo("...")` rather than `@foo("...");` For `cedar_version` in particular, we could make a warning whenever this id is used as an annotation on an individual policy, rather than the whole file.

We could also avoid versioning policies (and custom schemas) entirely, with the intention that policy syntax will always be backward compatible. We could limit version annotations on JSON-based formats instead.

#### Make new-version parsers accept old formats

Rather than reject inputs for older formats, newer parsers could accept those formats. For example, a new schema parser could interpret JSON schemas per [issue 351](https://github.com/cedar-policy/cedar/issues/351) by default, but if the schema is labeled as version "2.4" or earlier then the older intepretation could be used. This is both customer friendly and avoids errors. The cost is a significant maintenance burden for development, which creates a greater chance of errors.