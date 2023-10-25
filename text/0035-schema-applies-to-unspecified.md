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

**Current behavior**  
In Cedar 2.x, if an action's `appliesTo.principalTypes` or `appliesTo.resourceTypes` is not given (or if the entire `appliesTo` element is not given), then it's interpreted as an action that applies to all principal types and resource types.

**Challenges**  
Discussion on [RFC 24](https://github.com/cedar-policy/rfcs/pull/24) highlighted challenges this introduces, primarily the risk of unintentionally specifying that an action applies to all principal types / resource types and related complications it causes for analysis and the experience of policy validation as error messages become more confusing.

**Feature request**  
We can mitigate the challenges listed above by making following changes:

1. Specified `appliesTo` but omitted `appliesTo.principalTypes` / `appliesTo.resourceTypes` means that the request component is unspecified, i.e., corresponding to the `None` option in the principal and/or resource component of a [`Request`](https://docs.rs/cedar-policy/2.4.0/cedar_policy/struct.Request.html). Omitted `appliesTo.context` means that the context is an empty record (same as the status quo).
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

## Drawbacks

This is a breaking change that will alter the meaning of current schemas.
Given a policy set and schema that successfully validate with version 2.x, after this change, the schema may fail to parse (due to cases 3 or 4) or validation may return an error where it previously succeeded (due to cases 1 or 2).
Although this change may cause developer pain in the near term, we hope that it will make schemas easier to understand in the long term.

## Alternatives

- Keep the semantics as is, and improve documentation to reduce confusion.
- Introduce an explicit way of specifying that an action applies to all principal types / all resource types  ([cedar#320](https://github.com/cedar-policy/cedar/issues/320)).

## Unresolved questions

None, yet.
