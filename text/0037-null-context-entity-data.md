# Null JSON values in context and entity attribute JSON data

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started: 2023-11-02

## Summary

The JSON representation for request contexts and entity attributes currently rejects any data containing a `null` JSON value. 
With the proposal in this RFC, we would accept `null` JSON values appearing as the value of record attributes while continuing to reject `null` everywhere else.

## Basic example

Given a JSON object `{"foo": 1, "bar": null}`, we will ignore the `null` attribute and construct the Cedar record `{foo: 1}` instead of returning an error result.
In the JSON object `{"foo": [null]}`, the `null` is not directly an attribute value, so current behavior will not change (we fail to construct a Cedar record).

## Motivation

We want to support users passing generic JSON data as a request context with minimal preprocessing requirements.
We do this by constructing, for example, Cedar records from JSON objects and Cedar strings from JSON strings.
Notably, however, we will not construct any request context if there is a `null` JSON value appearing _anywhere_ in the JSON data, requiring that users who may have `null` in their context preprocess their data to remove it.

## Detailed design

To build the attributes for a context or entity, we accept a generic [JSON value](https://www.json.org/json-en.html) with a few limitation:

1. If the value is an object, it must not contain the same attribute twice. If it contains the reserved attributes `__expr`, `__entity`, or `__extn`, then it may also be rejected based on specific rules for these escapes.
2. If the value is a number, it must be an integer. A JSON value could be a fractional (e.g, `1.0`) or exponential (e.g., `1e0`) value, but these are not permitted.
3. The `null` value may not occur anywhere.

These limitations ensure that there is an obvious mapping from JSON values to their Cedar equivalents.
Fractional and exponential numbers encode floating point numbers which do not exist in Cedar, so they are not accepted.
In the case of `null`, Cedar does not have any `null` value, so there is no single obvious Cedar value that it should map to in all situations.

In this RFC we observe that when `null` occurs as the value of a record attribute there is a natural interpretation.
We can treat the `null` value as explicitly marking the attribute as _not_ present in the record, so we can ignore the attribute while continuing to error on `null` anywhere else.

If an object contains an attribute more than once it will still be an error even if the value of some of the attributes are `null`.

We use JSON objects with the reserved attributes `__expr`, `__entity`, or `__extn` as escapes for writing Cedar values that don't have JSON equivalents.
These are JSON objects, so this RFC as written up to this point implies ignoring `null` on attributes appearing here.
We will instead continue to treat `null` as an error in this context.

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
This entails interpreting `{"foo": [null]}` as `{foo: []}`.

This would lead to misleading behavior around  the `any` and `all` operators proposed in [RFC 21](https://github.com/cedar-policy/rfcs/pull/21) (and, to a lesser extent, the existing `containsAll` and `containsAny` operators).
The following policy would permit access even if `context.portNumbers` contains a `null` value, but `null` is clearly not within this range.

```cedar
permit(principal, action, resource)
when {
  context.portNumbers.all(it >= 8000 && it <= 8999)
};
```

This behavior is concerning, but, if we accept the misleading behavior around `has` when ignore `null` attributes, I don't think it should be considered unacceptable.

### Add `null` to Cedar

We don't want to add `null` as in Java where any reference may be `null`, but it could be added as the element of a unit type without causing too much trouble.
This could work well for when using Cedar as a dynamic language, but its use would be limited in a statically typed context.

### Error on `null`

This is our current behavior.
As stated above, it limits what data can be used to construct a context, forcing users to remove it in their own preprocessing passes. 
Cedar should be easy and ergonomic to use, so we should hesitate to offload work users without good reason, but, if the correct interpretation of `null` is not always the same, it may be the correct choice here.

If we take this alternative, we should keep in mind that many users are likely to find themselves writing the same filter to remove `null` from their data, so we should consider providing this filter ourselves, even if it is not an integral part of the Cedar data format.

## Unresolved questions

* Unexpected attribute with `null` value in schema based parsing.
