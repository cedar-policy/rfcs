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
* If the field `enum` is present, its value MUST be a non-empty list. 
* If the field `enum` is present, and it's in a `Long` specification, the values in the list MUST be numbers.
* If the field `enum` is present, and it's in a `String` specification, the values in the list MUST be strings.
* If the field `enum` is present, and it's in a `Boolean` specification, the values in the list MUST be booleans.

The presence of the `enum` field has the validator interpret the specification as a union between singleton types for everything in the `enum` list.

We can extend the validator to support singleton types for strings and numbers, and to allow union types for strings, booleans, and numbers. We have singleton types for booleans already, where bool is equivalent to the union true|false. This feature would generalize the same approach to numbers and strings.

For the future addition of numeric ranges to schemas, you could technically have both enumerations and ranges, but the enumeration can be checked against the range at validation time, and then the range can be ignored.

Like other types, enums are usable in the "common types" mechanism.

This would let us detect more policy error's statically. For example, using the Colors example above:

```
permit(principal, action, resource) when {
  principal.color == "gree"
};
```

The validator could flag the above policy as an error, as the equality will always be false, and will be typed thusly.

### Detailed Use Cases

#### Strings 
A use-case for strings was given above, but here's another one:
```json
"type": "Record",
  "attributes": {
    "department": {
      "type": "String",
      "enum" : ["engineering", "sales", "support"]
    }
}
```

#### Numbers
Enums on numbers could be used for enforcing that a number is in a small set. 
```json
"type": "Record",
  "attributes": {
    "TrustLevel": {
      "type": "Long",
      "enum" : [1, 2, 3, 4, 5]
    }
}
```

A non-consecutive example (That wouldn't be served the ranges RFC):
```json
"type": "Record",
  "attributes": {
    "KeyBits": {
      "type": "Long",
      "enum" : [512 , 1024 , 2048 , 4096] 
    }
}
```

#### Booleans
Enums on booleans are perhaps the strangest. 
Booleans are already essentially an enum in the type system, a union between the `True` type and the `False` type.
Enums on boolean values could be used as follows:
```json
"type": "Record",
  "attributes": {
    "authenticated": {
      "type": "Boolean",
      "enum" : ["true"],
      "required" : false
    }
}
```
This allows you to have a value who's meaning is only conveyed by it's presence or absence.

## Drawbacks

The main drawback is increasing the complexity of the schema & typechecking.

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
* Do we want any way to support exhaustive case statements? (No, potential future RFC)
* Any reason to support empty enums? (No)
