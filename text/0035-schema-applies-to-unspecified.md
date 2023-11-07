# Change the Semantics `appliesTo` Fields in the Schema

## Related issues and PRs

- Reference Issues: [cedar#351](https://github.com/cedar-policy/cedar/issues/351)
- Implementation PR(s):

## Timeline

- Started: 2023-10-25

## Summary

| Scenario | Status Quo | Proposal |
| --------- | -------- | ------- |
| Specified `appliesTo` but omitted `principalTypes`/`resourceTypes` | Authz request with this action can only have unspecified entity as principal/resource | Same as status quo |
| Omitted `appliesTo` | Authz request with this action can only have unspecified entity as principal/resource | Action cannot be used in authz request |
| `appliesTo.principalTypes: []` / `appliesTo.resourceTypes: []` | Action cannot be used in authz request | ❌ Not allowed |
| `appliesTo` is defined but all sub-elements are omitted | Authz request with this action can only have unspecified entity as principal/resource; context is an empty record | ❌ Not allowed |

## Motivation

### Current behavior

In Cedar 2.x, if an action's `appliesTo.principalTypes` or `appliesTo.resourceTypes` is not given (or if the entire `appliesTo` element is not given), then it's interpreted as an action that applies to only unspecified principals and resources.
An _unspecified_ entity has a type that is distinct from any defined type.
It is created by passing the `None` option in the principal and/or resource component of a [`Request`](https://docs.rs/cedar-policy/latest/cedar_policy/struct.Request.html).
If an action's `appliesTo.principalTypes` or `appliesTo.resourceTypes` fields are set to the empty list, then the action is not expected to be used with any request; it should only be used as a way to group other actions.

### Challenges

The difference between using an empty list vs. omitting `appliesTo.principalTypes` or `appliesTo.resourceTypes` vs. omitting `appliesTo` entirely can be unclear.
It also allows for confusing combinations: if `appliesTo.principalTypes` is the empty list, then the validator expects the action to never apply, regardless of whether `appliesTo.resourceTypes` is omitted or set to a list of entity types.

### Feature request

We can mitigate the challenges by making following changes:

1. Change an omitted `appliesTo` to mean that the action cannot be used in a request.
2. Disallow empty arrays for `appliesTo.principalTypes` / `appliesTo.resourceTypes`.
3. Disallow an empty `appliesTo` attribute thus requiring at least one of `principalTypes`, `resourceTypes` or `context` to be specified if `appliesTo` is specified.

This feature request is consistent with the semantics for `appliesTo` proposed in [RFC 24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md) for the alternate Cedar schema syntax.

## Detailed design

This RFC will require updating the schema parser to enforce suggestions 1-3 above.
It requires no changes to the validator itself.

### Notes on Backwards Compatibility

This RFC proposes a **breaking change** that requires a major version bump to Cedar.
For the sake of argument, say that the current version of Cedar X and that this RFC will be implemented in Cedar Y (which has no other breaking changes).
The rest of this section is written for users who are upgrading from X to Y.

The changes proposed in this RFC will _only_ affect you use the following in your schema:

1. You intend for an action to apply to _no_ principals or resources, i.e.,

- `appliesTo.principalTypes: []`
- `appliesTo.resourceTypes: []`

2. You intend for an action to apply to _unspecified_ principals or resources, i.e.,

- omitted `appliesTo` field
- `appliesTo: {}`

In **case 1**, in preparation to upgrade, you will need to update your schema to omit the `appliesTo` field.
Your current schema will result in error when you upgrade to Y.
If you use your modified schema with X, you will be able to validate policies that will not validate in Y.
There is _no way_ to write a schema so that validation behavior will be the same between X and Y.

In **case 2**, you should update your schema to use the following syntax instead.

```json
appliesTo: {
    context: {}
}
```

This will have the same meaning in both X and Y: the action applies to an unspecified principal and resource, and the empty context.

## Drawbacks

This is a breaking change that will alter the meaning of current schemas, see the discussion on backwards compatibility [above](#notes-on-backwards-compatibility).
Although this change may cause developer pain in the near term, we hope that it will make schemas easier to understand in the long term.

## Alternatives

- Keep the semantics as is, and improve documentation to reduce confusion.
