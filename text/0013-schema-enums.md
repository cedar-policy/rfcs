# Enums in Schemas

## Related issues and PRs

- Reference Issues: 
- Implementation PR(s): 

## Timeline

- Start Date: 2023-06-30
- Date Entered FCP:
- Date Accepted:
- Date Landed:

## Summary

Add support for enumerations of `bool`, `string`, and `long` types in schemas, and use this information when doing policy validation and schema-based-parsing.

## Basic example

Maintaining backward compatibility with JSON schema as much as possible, we can match its enum feature. For example:

```json
"type": "Record",
  "attributes": {
    "color": {
      "type": "String",
      "enum" : ["red", "blue", "green"]
    }
}
```

The enum part limits the color attribute to one of three possibilities. We would permit enumerations of this flavor for numbers and booleans too.

## Motivation

Enumerations are a common need, and this change supports them in Cedar. It avoids the mistake of expecting a string (say) to match only a few values, but then encountering a different value at runtime.

Enumerations are particularly useful for policy building UIs -- the UI can look at the schema to know what values are valid for a particular attribute.

Enumerations are also useful for schema-based parsing, and reject entities/contexts that don't properly pick a value from the enumeration.


## Detailed design

Schema specification:
* The types `String`, `Bool`, and `Long` MAY have a field `enum` in their specification. 
* If the field `enum` is not present the semantics is unchanged.
* If the field `enum` is present, it's value MUST be a non-empty list. 
* If the field `enum` is present, and it's in a `Long` specification, the values in the list MUST be numbers.
* If the field `enum` is present, and it's in a `String` specification, the values in the list MUST be strings.
* If the field `enum` is present, and it's in a `Boolean` specification, the values in the list MUST be booleans.

The presence of the `enum` field has the validator interpret the specification as a union between singleton types for everything in the `enum` list.

We can extend the validator to support singleton types for strings and numbers, and to allow union types for strings, booleans, and numbers. We have singleton types for booleans already, where bool is equivalent to the union true|false. This feature would generalize the same approach to numbers and strings.

For the future addition of numeric ranges to schemas, you could technically have both enumerations and ranges, but the enumeration can be checked against the range at validation time, and then the range can be ignored.

Like other types, enums are usable in the "common types" mechanism.

## Drawbacks

Why should we *not* do this? Please consider:

- implementation cost, both in term of code size and complexity
- integration of this feature with other existing and planned features
- cost of migrating existing Cedar applications (is it a breaking change?)

There are tradeoffs to choosing any path. Attempt to identify them here.

## Alternatives

### Alternative 1: Don't support it


### Alternative 2: Different syntax

There are many different syntax decisions we could make here. Here's an example that puts the fact the type is an enum for front and center:
```json
{
  "type" : "Record",
  "attributes" : {
    "color" : {
      "type" : "Enum",
      "values" : ["red", "blue", "green"]
    }
  }
}
```
In this case, we don't specify the `Enum` is a subset of `String`, as that's implicit.

## Unresolved questions

* Do we have any mechanism for enums of extensions types?
* Do we want any way to support exhaustive case statements?
* Any reason to support empty enums?
