# Change the Semantics `appliesTo` Fields in the Schema

## Related issues and PRs

- Reference Issues: [cedar#351](https://github.com/cedar-policy/cedar/issues/351)
- Implementation PR(s):

## Timeline

- Started: 2023-10-25

## Summary

| Scenario | Status Quo | Proposal |
| --------- | -------- | ------- |
| Specified `appliesTo` but omitted `principalTypes` and/or `resourceTypes` | Authz request with this action can only have an unspecified entity as the principal and/or resource | Same as status quo |
| `appliesTo.principalTypes: []` AND `appliesTo.resourceTypes: []` | Action cannot be used in authz request | Same as status quo |
| `appliesTo.principalTypes: []` OR `appliesTo.resourceTypes: []` | Action cannot be used in authz request | ❌ Not allowed |
| Omitted `appliesTo` | Authz request with this action can only have unspecified entities as the principal and resource | ❌ Not allowed |

## Motivation

In Cedar 2.x and 3.0, if an action's `appliesTo.principalTypes` (or `appliesTo.resourceTypes`) is not given, then it's interpreted as an action that applies to only unspecified principals (or resources).
If an action's `appliesTo` is not given, then it's interpreted as an action that applies only to unspecified principals _and_ resources.
An _unspecified_ entity has a type that is distinct from any defined type.
It is created by passing the `None` option in the principal and/or resource component of a [`Request`](https://docs.rs/cedar-policy/latest/cedar_policy/struct.Request.html).

If an action's `appliesTo.principalTypes` or `appliesTo.resourceTypes` are the empty list, then the action is not expected to be used with any request; it should only be used to group other actions.
This takes precedent over any other information in the `appliesTo`.
For example: if `appliesTo.principalTypes` is the empty list, then the validator expects the action to never apply, regardless of whether `appliesTo.resourceTypes` is omitted or set to a particular list of entity types.

The difference between omitting a field vs. setting it to the empty list, and the relationship between the two, has caused confusion for users.
This RFC proposes to:

1. Require that either both `appliesTo.principalTypes` and `appliesTo.resourceTypes` are empty lists, or neither are.
2. Disallow a missing `appliesTo` field.

These changes remove some of the confusing behavior of the current implementation while maintaining backwards compatibility.
In particular, with this change there is only _one way_ to define an action group (both `appliesTo.principalTypes` and `appliesTo.resourceTypes` must be empty), and _one way_ to define an action where both the principal and resource are unspecified (omit the `appliesTo.principalTypes` and `appliesTo.resourceTypes` fields).
Under this proposal, some schemas will produce parse errors when users upgrade to a new version of Cedar, but users can fix these errors proactively because for every valid schema under the new proposal, there is some schema in the current implementation that has identical behavior.

## Detailed design

This RFC requires updating the schema parser.
It requires no changes to the validator itself.

## Drawbacks

### This proposal is a compromise

This RFC originally proposed Alternative A [below](#alternative-a).
That alternative completely disallows empty lists in the `appliesTo` field, which have been a source of confusion.
The current proposal still allows empty lists, but at least removes some cases where the behavior is confusing (e.g., when one of the `appliesTo` fields is an empty list, but not the other).
Unfortunately, that alternative causes problems for users upgrading between versions of Cedar -- see discussion in the section on Alternative A.

### This proposal is inconsistent with RFC24

This proposal is inconsistent with [RFC 24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md), where an omitted `appliesTo` field is used to define an action group, and empty `appliesTo.principalTypes` or `appliesTo.resourceTypes` lists are forbidden.
In particular, this proposal is inconsistent with RFC24 in two cases:

1. Declaring an action group `"actionGroup"`.

JSON:

```json
"actionGroup": {
    "appliesTo": {
        "principalTypes": [],
        "resourceTypes": []
    }
},
```

Natural syntax:

```
action actionGroup;
```

2. Declaring an action `"action"` that applies to an unspecified principal _and_ resource.

JSON:

```json
"action": {
    "appliesTo": {}
},
```

Natural syntax:

```
action action
  appliesTo { context: {} };
```

(Note that in the natural syntax, `context: {}` is required.)

## Alternatives

### Alternative A

**NOTE:** this alternative was the original proposal

| Scenario | Status Quo | Proposal |
| --------- | -------- | ------- |
| Specified `appliesTo` but omitted `principalTypes` and/or `resourceTypes` | Authz request with this action can only have an unspecified entity as the principal and/or resource | Same as status quo |
| Omitted `appliesTo` | Authz request with this action can only have unspecified entities as the principal and resource | Action cannot be used in authz request |
| `appliesTo.principalTypes: []` / `appliesTo.resourceTypes: []` | Action cannot be used in authz request | ❌ Not allowed |
| `appliesTo` is defined but all sub-elements are omitted | Authz request with this action can only have unspecified entities as the principal and resource; context is an empty record | ❌ Not allowed |

This alternative proposes to:

1. Change an omitted `appliesTo` to mean that the action cannot be used in a request.
2. Disallow empty arrays for `appliesTo.principalTypes` / `appliesTo.resourceTypes`.
3. Disallow an empty `appliesTo` attribute thus requiring at least one of `principalTypes`, `resourceTypes` or `context` to be specified if `appliesTo` is specified.

This semantics is consistent with the semantics for `appliesTo` proposed in [RFC 24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md) for the alternate Cedar schema syntax.

The main downside of this alternative is that, in some cases (see **case 1** [below](#notes-on-backwards-compatibility)), there will be no way to update your schema before you upgrade Cedar versions -- you will have to update your schema simultaneously with the upgrade.
This is a no-go for large applications where updating policies, schemas, and the Cedar SDK cannot be done atomically.

#### Notes on Backwards Compatibility

Say that the current version of Cedar is X and that this alternative is implemented in Y (which has no other breaking changes).
When upgrading from X to Y, the changes proposed in this alternative will _only_ affect you if you use the following in your schema:

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

### Alternative B

Another way to address backwards compatibility concerns is to combine this change with an implementation of schema versioning (see [RFC 33](https://github.com/cedar-policy/rfcs/pull/33)), supporting both the old and new behavior for schema parsing (for some period of time), allowing users to choose which behavior they want by setting a flag.

There are at least two reasonable options here:

- Force Cedar Y schemas to include an explicit version marker saying version Y. Schemas with no version marker will be interpreted using the Cedar X behavior, even if you're using Cedar Y. This gives full backwards-compatibility: no one's schema changes behavior when upgrading from Cedar X to Cedar Y, unless/until you add a version marker saying version Y. However, this means the behavior proposed in this RFC won't be default, which seems undesirable.
- Same thing, but interpret schemas with no version marker using the Cedar Y behavior. This is still a breaking change, because unmarked schemas will change behavior when upgrading from Cedar X to Cedar Y. But it solves the problem of "no way to write a schema so that validation behavior will be the same between X and Y." Users just add a "version X" marker to their schema, and then they can upgrade from Cedar X to Cedar Y without that schema changing behavior.

The primary arguments against this alternative are that (1) it blocks this RFC on the acceptance of RFC 33, and (2) it commits us to maintaining multiple versions of the schema parser and sets a precedent for supporting deprecated data formats going forward.

## Outcomes of Discussion

- _Alternative A_ was rejected because of backwards-compatibility concerns.
- _Alternative B_ was rejected because [RFC 33](https://github.com/cedar-policy/rfcs/pull/33) was rejected. See the discussion on the associated PR.
