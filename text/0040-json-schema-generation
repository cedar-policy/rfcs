# RFC Template (Fill in your title here)

## Related issues and PRs

- Reference Issues: -
- Implementation PR(s): -

## Timeline

- Started: 2023-11-21

## Summary

This proposal is to export useful interface types from cedar into JsonSchema, under a feature flag. The rationale for this is so that other languages bindings can use these generated json schemas to create data classes for that language.

## Basic example

An example of what this entails is here https://github.com/josema03/cedar/compare/379a2b1330bc5f82bb2bdd9cb39db1ebd41a053b..d501acba0a878dfe898427cdc0645d8b37779562

Of course, we would do all of these trait implementations (as well as the dependency addition) under feature flags so as to not affect current consumers.

## Motivation

Without this functionality, then structs like (AuthorizationCall)[https://github.com/cedar-policy/cedar/blob/main/cedar-policy/src/frontend/is_authorized.rs#L146] and (RecvdSlice)[https://github.com/cedar-policy/cedar/blob/main/cedar-policy/src/frontend/is_authorized.rs#L286] need to be duplicated in the calling code.

This adds surface area for bugs for consumers who use cedar in other languages (eg. wasm), because it causes the potential for drift between the `cedar-policy` structs and their copies in the wasm-wrapper package.


## Detailed design

We will add the schemars dependency under a feature flag named `jsonschema`. 

We will then implement the `JsonSchema` trait in all the necessary structs that will allow us to have Json Schema definitions of the inputs and outputs of all the following operations:

1. Authorize
2. Authorize with schema
3. Format policies
4. Validate entities against schema
5. Validate context against schema
6. Parsing euids
7. Parsing schemas (the whole schema type definition with all its subtypes and recursive type definition around TypeOfAttribute should be exported to JsonSchema)
8. Convert policy to JSON syntax tree
9. Convert JSON syntax tree to policy
11. Convert policy template to JSON syntax tree
12. Convert policy template from JSON to string

As an example, use cases 1, 2, and 7 would be enabled by implementing the trait in all the following structs:
* `cedar-policy-core::ast::PolicyID`
* `cedar-policy-core::authorizer::Decision`
* `cedar-policy-core::entities::json::EntityJson`
* `cedar-policy-core::entities::json::CedarValueJson`
* `cedar-policy-core::entities::json::TypeAndId`
* `cedar-policy-core::entities::json::FnAndArg`
* `cedar-policy-core::entities::json::EntityUidJson`
* `cedar-policy-validator::schema_file_format::SchemaFragment`
* `cedar-policy-validator::schema_file_format::NamespaceDefinition`
* `cedar-policy-validator::schema_file_format::SchemaType`
* `cedar-policy-validator::schema_file_format::EntityType`
* `cedar-policy-validator::schema_file_format::ActionType`
* `cedar-policy-validator::schema_file_format::AttributesOrContext`
* `cedar-policy-validator::schema_file_format::ApplySpec`
* `cedar-policy-validator::schema_file_format::ActionEntityUID`
* `cedar-policy-validator::schema_file_format::TypeOfAttribute`
* `cedar-policy::api::PolicyId`
* `cedar-policy::frontend::InterfaceResponse`
* `cedar-policy::frontend::InterfaceDiagnostics`
* `cedar-policy::frontend::AuthorizationAnswer`
* `cedar-policy::frontend::AuthorizationCall`
* `cedar-policy::frontend::EntityUIDStrings`
* `cedar-policy::frontend::Link`
* `cedar-policy::frontend::TemplateLink`
* `cedar-policy::frontend::Links`
* `cedar-policy::frontend::RecvdSlice`
* `cedar-policy::frontend::utils::PolicySpecification`


## Drawbacks

* We're taking on another dependency that is schemars.
* The way rust works with not being able to implement traits in a crate you dont own means we either need to copy a lot of these types from `cedar-policy-core` or accept that we're indirectly exposing them. One could argue we're already indirectly exposing these types though.

## Alternatives

That example commit I posted above also uses ts-rs to more directly export types from rust to typescript. However, this implementation required extending ts-rs and the PR to do so has not been approved. It also seems strange to couple cedar-policy crates to typescript. JsonSchema is a more generic solution and I think it's more acceptable for JsonSchema implementations to live in cedar-policy crates than typescript-specific things.

The alternative to implement multiple traits for all the structs to export to ts, java, etc, was also explored. We _could_ directly export from rust to java under a `javapojos` feature flag, rust to typescript under a `typescriptinterfaces` flag, etc. This was a lot more work and adds more dependency risk.

## Unresolved questions

I have not yet exhaustively ascertained all the types that I need to export. If this approach is accepted, I will develop a wasm implementation with all the features I need in parallel to implementing this RFC. Tht way, I'll be able to ensure I export the types I need for the wasm implementation.
