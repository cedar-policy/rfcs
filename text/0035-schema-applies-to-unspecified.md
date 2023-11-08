# Change the Semantics `appliesTo` Fields in the Schema

## Related issues and PRs

- Reference Issues: [cedar#351](https://github.com/cedar-policy/cedar/issues/351)
- Implementation PR(s):

## Timeline

- Started: 2023-10-25

## Summary

| Scenario | Status Quo | Proposal |
| --------- | -------- | ------- |
| Specified `appliesTo` but omitted `principalTypes`/`resourceTypes` | Authz request with this action can only have an unspecified entity as the principal/resource | Same as status quo |
| Omitted `appliesTo` | Authz request with this action can only have unspecified entities as the principal and resource | Action cannot be used in authz request |
| `appliesTo.principalTypes: []` / `appliesTo.resourceTypes: []` | Action cannot be used in authz request | ❌ Not allowed |
| `appliesTo` is defined but all sub-elements are omitted | Authz request with this action can only have unspecified entities as the principal and resource; context is an empty record | ❌ Not allowed |

## Motivation

In Cedar 2.x, if an action's `appliesTo.principalTypes` (or `appliesTo.resourceTypes`) is not given, then it's interpreted as an action that applies to only unspecified principals (or resources).
If an action's `appliesTo` is not given, then it's interpreted as an action that applies only to unspecified principals _and_ resources.
An _unspecified_ entity has a type that is distinct from any defined type.
It is created by passing the `None` option in the principal and/or resource component of a [`Request`](https://docs.rs/cedar-policy/latest/cedar_policy/struct.Request.html).

If an action's `appliesTo.principalTypes` or `appliesTo.resourceTypes` are the empty list, then the action is not expected to be used with any request; it should only be used to group other actions.
This takes precedent over any other information in the `appliesTo`.
For example: if `appliesTo.principalTypes` is the empty list, then the validator expects the action to never apply, regardless of whether `appliesTo.resourceTypes` is omitted or set to a particular list of entity types.

The difference between omitting a field vs. setting it to the empty list has caused confusion for users.
This RFC proposes to:

1. Change an omitted `appliesTo` to mean that the action cannot be used in a request.
2. Disallow empty arrays for `appliesTo.principalTypes` / `appliesTo.resourceTypes`.
3. Disallow an empty `appliesTo` attribute thus requiring at least one of `principalTypes`, `resourceTypes` or `context` to be specified if `appliesTo` is specified.

This feature request is consistent with the semantics for `appliesTo` proposed in [RFC 24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md) for the alternate Cedar schema syntax.

## Detailed design

This RFC will require updating the schema parser to enforce proposals 1-3 above.
It requires no changes to the validator itself.

### Notes on Backwards Compatibility

This RFC proposes a **breaking change** that requires a major version bump to Cedar.
For the sake of argument, say that the current version of Cedar is X and that this RFC will be implemented in Y (which has no other breaking changes).
The rest of this section is written for users who are upgrading from X to Y.

The changes proposed in this RFC will _only_ affect you if you use the following in your schema:

1. You intend for an action to apply to _no_ principals or resources, i.e.,

- `appliesTo.principalTypes: []`
- `appliesTo.resourceTypes: []`

2. You intend for an action to apply to _unspecified_ principals and resources, i.e.,

- omitted `appliesTo` field
- `appliesTo: {}`

In **case 1**, in preparation to upgrade, you will need to update your schema to omit the `appliesTo` field.
Your current schema will result in error when you upgrade to Y.
If you use your modified schema with X, you will be able to validate policies that will not validate in Y.
There is _no way_ to write a schema so that validation behavior will be the same between X and Y.

In **case 2**, you should update your schema to use the following syntax instead.

```json
"appliesTo": {
    "context": {}
}
```

This will have the same meaning in both X and Y: the action applies to an unspecified principal and resource, and the empty context.

## Drawbacks

This is a breaking change that will alter the meaning of current schemas.
See the discussion on backwards compatibility [above](#notes-on-backwards-compatibility) and discussion on backwards-compatible alternatives [below](#alternatives).

## Alternatives

### Alternative A

The main downside of the current proposal is that, in some cases (see **case 1** [above](#notes-on-backwards-compatibility)), there will be no way to update your schema before you upgrade to Cedar Y -- you will have to update your schema simultaneously with the upgrade.
This will be a problem for large applications where updating policies, schemas, and the Cedar SDK cannot be done atomically.

We could mitigate this by instead implementing the following changes.

| Scenario | Status Quo | Proposal |
| --------- | -------- | ------- |
| Specified `appliesTo` but omitted `principalTypes`/`resourceTypes` | Authz request with this action can only have an unspecified entity as the principal/resource | Same as status quo |
| `appliesTo.principalTypes: []` AND `appliesTo.resourceTypes: []` | Action cannot be used in authz request | Same as status quo |
| `appliesTo.principalTypes: []` OR `appliesTo.resourceTypes: []` | Action cannot be used in authz request | ❌ Not allowed |
| Omitted `appliesTo` | Authz request with this action can only have unspecified entities as the principal and resource | ❌ Not allowed |

These changes remove some of the confusing behavior of the current implementation (e.g., setting only one of `appliesTo.principalTypes`/`appliesTo.resourceTypes` to be the empty list), while maintaining backwards compatibility.
Under this alternative, some schemas will produce parse errors after upgrading to Y, but users can fix these error proactively.
For every valid schema in Y, there is some schema in X that has identical behavior.

The downside of this alternative is that it still allows the empty list to mean that an action applies to no entities, which may be confusing for users.
Specifying that an action applies to no entities also requires more characters with this alternative, possibly making it more annoying to type out.

This alternative will require updates to [RFC 24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md) in order to maintain consistency between the two schema formats.

### Alternative B

Another way to address backwards compatibility concerns is to combine this change with an implementation of schema versioning (see [RFC 33](https://github.com/cedar-policy/rfcs/pull/33)), supporting both the old and new behavior for schema parsing (for some period of time), allowing users to choose which behavior they want by setting a flag.

There are at least two reasonable options here:

- Force Cedar Y schemas to include an explicit version marker saying version Y. Schemas with no version marker will be interpreted using the Cedar X behavior, even if you're using Cedar Y. This gives full backwards-compatibility: no one's schema changes behavior when upgrading from Cedar X to Cedar Y, unless/until you add a version marker saying version Y. However, this means the behavior proposed in this RFC won't be default, which seems undesirable.
- Same thing, but interpret schemas with no version marker using the Cedar Y behavior. This is still a breaking change, because unmarked schemas will change behavior when upgrading from Cedar X to Cedar Y. But it solves the problem of "no way to write a schema so that validation behavior will be the same between X and Y." Users just add a "version X" marker to their schema, and then they can upgrade from Cedar X to Cedar Y without that schema changing behavior.

The primary arguments against this alternative are that (1) it blocks this RFC on the acceptance of RFC 33, and (2) it commits us to maintaining multiple versions of the schema parser and sets a precedent for supporting deprecated data formats going forward.

## Unresolved questions

- Should we provide an automated transformation for people using the existing schemas? How should we provide this transformation: as a new API in `cedar-policy`, or a standalone executable? How long should we maintain the transformation code? How can we ensure that users run the transformation at upgrade time?
