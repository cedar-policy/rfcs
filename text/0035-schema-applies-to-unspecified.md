# Change the Semantics of Unspecified `appliesTo` Fields in the Schema

## Related issues and PRs

- Reference Issues: [cedar#351](https://github.com/cedar-policy/cedar/issues/351)
- Implementation PR(s):

## Timeline

- Started: 2023-10-25

## Summary

This RFC proposes to change the semantics of the `appliesTo` field in the schema, as summarized by the following table.
| Scenario | Status Quo | Proposal |
| --------- | -------- | ------- |
| (1) Specified `appliesTo` but omitted `principalTypes`/`resourceTypes` | Authz request can have a principal/resource entity of any type, or the unspecified entity | Authz request with this action can only have unspecified entity as principal/resource |
| (2) Omitted `appliesTo` | Authz request can have a principal/resource entity of any type, or the unspecified entity | Action cannot be used in authz request |
| (3) `appliesTo.principalTypes: []` / `appliesTo.resourceTypes: []` | Action cannot be used in authz request | ❌ Not allowed |
| (4) `appliesTo` is defined but all sub-elements are omitted | Authz request can have a principal/resource entity of any type, or the unspecified entity; context is an empty record | ❌ Not allowed |

## Motivation

### Current behavior

In Cedar 2.x, if an action's `appliesTo.principalTypes` or `appliesTo.resourceTypes` is not given (or if the entire `appliesTo` element is not given), then it's interpreted as an action that applies to all principal types and resource types.

### Challenges

Discussion on [RFC 24](https://github.com/cedar-policy/rfcs/pull/24) highlighted challenges this introduces, primarily the risk of unintentionally specifying that an action applies to all principal types / resource types and related complications it causes for analysis and the experience of policy validation as error messages become more confusing.

### Feature request

We can mitigate the challenges listed above by making following changes:

1. Specified `appliesTo` but omitted `appliesTo.principalTypes` / `appliesTo.resourceTypes` means that the request component is unspecified, i.e., corresponding to the `None` option in the principal and/or resource component of a [`Request`](https://docs.rs/cedar-policy/X.0/cedar_policy/struct.Request.html). Omitted `appliesTo.context` means that the context is an empty record (same as the status quo).
2. Omitted `appliesTo` means that the action cannot be used in a request. It is used exclusively as an action group.
3. Disallow empty arrays for `appliesTo.principalTypes` / `appliesTo.resourceTypes`.
4. Disallow an empty `appliesTo` attribute thus requiring at least one of `principalTypes`, `resourceTypes` or `context` to be specified if `appliesTo` is specified.

This feature request is consistent with the semantics for `appliesTo` proposed in [RFC 24](https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md) for the alternate Cedar schema syntax.

## Detailed design

This RFC will require the following changes:

1. The permissive validator must be updated to treat an omitted `appliesTo.principalTypes` / `appliesTo.resourceTypes` as the _unspecified_ entity type, rather than _any_ entity type. The difference is that the _unspecified_ entity type is a particular type that is different from any defined type, whereas _any_ entity type could be the unspecified type or any other type defined in the schema. Note that this change is only required in the _permissive_ validator, because the corresponding change was already made to strict validation as part of [RFC 19](https://github.com/cedar-policy/rfcs/blob/main/text/0019-stricter-validation.md).
2. The validator must be updated to treat an omitted `appliesTo` attribute as indication that an action does not apply to any principal or resource types.
3. The schema parser must be updated to reject empty arrays for `appliesTo.principalTypes` / `appliesTo.resourceTypes`.
4. The schema parser must be updated to reject empty `appliesTo` attributes.

### Notes on Backwards Compatibility

This RFC proposes a **breaking change** that requires a major version bump to Cedar.
For the sake of argument, say that the current version of Cedar X and that this RFC will be implemented in Cedar Y (which has no other breaking changes).
The rest of this section is written for users who are upgrading from X to Y.

The changes proposed in this RFC will _only_ affect you if you have one or more of the following in your schema:

1. You intend for an action to apply to _no_ principals or resources, i.e.,

- `appliesTo.principalTypes: []`
- `appliesTo.resourceTypes: []`

2. You intend for an action to apply to _any_ principal and/or resource types, i.e.,

- omitted `appliesTo` field
- omitted `appliesTo.principalTypes` field
- omitted `appliesTo.resourceTypes` field

In **case 1**, in preparation to upgrade, you will need to update your schema to omit the `appliesTo` field.
Your current schema will result in error when you upgrade to Y.
If you use your modified schema with X, you will be able to validate policies that will not validate in Y.
There is _no way_ to write a schema so that validation behavior will be the same between X and Y.

In **case 2**, you will need to decide: did you intend for the action to apply to any entity type defined in the schema, or did you intend for the action to apply only to an unspecified entity?
(It is no longer possible to choose both options.)
In the former case, you can update the relevant `appliesTo` list(s) to include all entity types in the schema.
For example, say that your schema contains entity types for `User`, `Group`, and `Photo` and you want an action to apply to a resource of any of these types.
Then instead of omitting the `appliesTo.resourceTypes` field, you will need to set the field to `[User, Group, Photo]`.
The modified schema will produce the same validation behavior between X and Y.

In the latter case, you can leave your schema unchanged.
However, the interpretation of the schema is slightly different between X and Y: In X omitting a field means that you want an action to apply to _any_ entity type, while in in Y it means that you require the action to be applied to an _unspecified_ entity.
In many cases, this difference in interpretation will make no different for validation.
If a policy validates with any entity type, then it must also validate for the unspecified entity type.
However the inverse is not true: using the unspecified entity type is more precise, so it may be the case that a policy will fail to validate in Y (with an [`ImpossiblePolicy`](https://docs.rs/cedar-policy/latest/cedar_policy/enum.TypeErrorKind.html#variant.ImpossiblePolicy) error) where it previously succeeded.
This was observed in [RFC 19](https://github.com/cedar-policy/rfcs/blob/main/text/0019-stricter-validation.md):

> In particular, for an expression like `principal == User::"Alice"` in a policy, using _AnyEntity_ for the type of `principal` would give this expression the type `Boolean`. But we know better: This expression will always evaluate to `false` when `principal` is unspecified in the request. Giving `principal` an entity type not equal to any other type would allow us to type the expression as `False`, and therefore uncover that the policy containing this expression might never properly apply.

## Drawbacks

This is a breaking change that will alter the meaning of current schemas, see the discussion on backwards compatibility [above](#notes-on-backwards-compatibility).
Although this change may cause developer pain in the near term, we hope that it will make schemas easier to understand in the long term.

## Alternatives

- Keep the semantics as is, and improve documentation to reduce confusion.
- Introduce an explicit way of specifying that an action applies to all principal types / all resource types  ([cedar#320](https://github.com/cedar-policy/cedar/issues/320)).
