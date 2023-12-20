# Null JSON values in context and entity attribute JSON data

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started: 2023-11-02
- Entered FCP (intent to reject): 2023-12-11
- Rejected: 2023-12-20

## Summary

The JSON representation for request contexts and entity attributes currently rejects any data containing a `null` JSON value. 
With the proposal in this RFC, we would accept `null` JSON values appearing as the value of record attributes while continuing to reject `null` everywhere else.

## Basic example

Given a JSON object `{"foo": 1, "bar": null}`, we will ignore the `null` attribute and construct the Cedar record `{foo: 1}` instead of returning an error result.
In the JSON object `{"foo": [null]}`, the `null` is not directly an attribute value, so current behavior will not change (we fail to construct a Cedar record).

## Motivation

A goal when designing entity and context parsing for Cedar was to support users passing generic JSON data as a request context with minimal preprocessing requirements.
We do this by constructing, for example, Cedar records from JSON objects and Cedar strings from JSON strings.
Notably, however, we do not construct any request context if there is a `null` JSON value appearing _anywhere_ in the JSON data, requiring that users who may have `null` in their context preprocess their data to remove it.
This becomes a problem when a users includes `null` in their data, expecting that it will be accepted like most other JSON data, but then encounter an unexpected error.

## Detailed design

This RFC proposes ignoring `null` values _only_ when they occur as the value of a record attribute while continuing to error on `null` elsewhere.
This is based on the observation that, while we can't handle `null` in all situations, a `null` value appearing as a record attribute can reasonably be treated as explicitly marking the attribute _not_ present in the record.

### JSON Parsing Background

To build the attributes for a context or entity, Cedar currently accept a generic [JSON value](https://www.json.org/json-en.html) with a few limitation:

1. If the value is an object, it must not contain the same attribute twice. If it contains the reserved attributes `__expr`, `__entity`, or `__extn`, then it may also be rejected based on specific rules for these escapes.
2. If the value is a number, it must be an integer. A JSON value could be a fractional (e.g, `1.0`) or exponential (e.g., `1e0`) value, but these are not permitted.
3. The `null` value may not occur anywhere.

These limitations ensure that there is an obvious mapping from JSON values to their Cedar equivalents.
Fractional and exponential numbers encode floating point numbers which do not exist in Cedar, so they are not accepted.
In the case of `null`, Cedar does not have any `null` value, so there is no single obvious Cedar value that it should map to in all situations.
The change proposed in this RFC supports `null` where there is an obvious interpretation (record attributes) while continuing to error elsewhere.

### Edge Cases

If an object contains an attribute more than once it will still be an error even if the value of some of the attributes are `null`.
All JSON formats used by Cedar should error when encountering an attribute more than once in any JSON object.
Even though the `null` value is marking the attribute as absent from the Cedar record, the entry is present in the JSON object, so it is still an error.
Moreover, explicitly marking an attribute as absent and later providing a value for that attribute is very likely to be a mistake.

We use JSON objects with the reserved attributes `__expr`, `__entity`, or `__extn` as escapes for writing Cedar values that don't have JSON equivalents.
These are JSON objects, so this RFC as written up to this point implies ignoring `null` on attributes appearing here.
We will instead continue to treat `null` as an error in this context.
If this were not an error and we instead ignored `null` values, `{"__entity": null}` would be treated the same as `{}`, but the `__entity` escape should parse to an entity while `{}` parses to a record.
We could alternatively find a way to parse `null` to an entity, perhaps the unspecified entity.
There is currently no way to specify the unspecified entity in out JSON data format.
If we want to extend the formats to support it, this may be a reasonable approach, but that extension is beyond the scope of this RFC, and can be added later in a backwards compatible manner if `null` remains an error here.

### Schema based parsing

The static type system used by Cedar includes optional attributes. 
When constructing a context based on a context type from a schema we can ensure that any attributes that are not optional are present with a non-`null` value.
Optional attributes may be present, present with a `null` value, or absent.

For the following context type, `{"foo": null, "bar": 1}` and `{"bar": 1}` are accepted because `foo` is not required, but `{"bar": null}` and `{}` are rejected because `bar` is required.

```json
{
    "type": "Record",
    "attributes": {
        "foo": {"type": "Long", "required": false},
        "bar": {"type": "Long", "required": true}
    }
}
```

We can further ensure that any attribute present with a `null` value is an optional attributes in context type.
This would mean rejecting `{"bar": 1, "baz": null}` because `baz` is not an optional attribute in the record type.
This extra check is not necessary to meet the preconditions for validation soundness since the Cedar value constructed would be `{bar: 1}` which does match the type, but this may be useful for detecting errors in input data.

## Drawbacks

### Unexpected behavior

Ignoring `null` may not be the desired behavior for all users.
It seems reasonable that a `null` attribute value can be safely ignored, but a user may expect that `context has foo` evaluates to `true` if `foo` is present in their JSON context data.
It will instead evaluate to `false` if `foo` is present but has a `null` value.

In support of this point, observe how JavaScript treats objects containing `null`:
```js
Object.hasOwn({foo: null}, 'foo') // true
```

### Inconsistent behavior

Handling `null` when it occurs directly as an attribute while continuing to error elsewhere could lead to surprising errors.
If a user first observes that `null` is ignored as an attribute value, they may later assume that it will be ignored as an element of a set.

## Alternatives

### Ignore `null` everywhere

To avoid inconsistent handling of `null`, we could decided that `null` occurring _anywhere_ should be ignored. 
Aside from objects, the only relevant case is arrays.
This entails interpreting the JSON object `{"foo": [null]}` as the Cedar value `{foo: []}`.

This behavior is very surprising.
I cannot think of a programming language with `null` that would not count it as an element of a list.
This would lead to misleading behavior around  the `any` and `all` operators proposed in [RFC 21](https://github.com/cedar-policy/rfcs/pull/21) (and, to a lesser extent, the existing `containsAll` and `containsAny` operators).
The following policy would permit access even if `context.portNumbers` contains a `null` value, but `null` is clearly not within this range.

```cedar
permit(principal, action, resource)
when {
  context.portNumbers.all(it >= 8000 && it <= 8999)
};
```

This behavior is concerning, but, if we accept the misleading behavior around `has` when ignoring `null` attributes, it seems that this could be considered acceptable.

### Add `null` to Cedar

We don't want to add `null` as in Java where any reference may be `null`, but it could be added as the element of a unit type without causing too much trouble.
This could work well for when using Cedar as a dynamic language, but its use would be limited in a statically typed context.

### Error on `null`

This is our current behavior.
It limits what data can be used to construct an entity or context, so users with `null` values in their data see an error and can remove it in their own pre-processing pass if that's the behavior they require.

If different users tend to want different non-error parsing, then this alternative provides a clear error message to users immediately on attempting to parse a `null` value.
At this point, they are forced to make an explicit decision about how to handle `null` data.
As the source of the data, users are likely to be in a better position to make this decision than we are.

This is a good alternative unless believe that the majority of users want the same non-error parsing of `null`.
In that case we would be requiring that many users independently re-implement the same preprocessing pass.
Even in this case, supporting one non-error alternative (e.g., this rfc, or ignore `null` everywhere) would still force users wanting a different option to write their own preprocessing pass while making the behavior when a `null` is included in their data more difficult to diagnose.
Rather than see an error when parsing, an unexpected parsing of `null` values could result in an unexpected authorization decision.


