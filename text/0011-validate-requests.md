# Validate input requests

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Start Date: 2021-06-23
- Date Entered FCP:
- Date Accepted:
- Date Landed:

## Summary

Given a schema, _validation_ checks that policies conform to the schema, and _schema-based parsing_ checks that entities conform to the schema.
This RFC proposes to add support for checking that a query conforms to a schema.

## Basic example

Say the schema specifies that an action `readFile` should only be used with principals of type `User` and resources of type `File`.
This RFC proposes to change the signature of the `Request` constructor to add an optional schema argument that can be used to check  argument types when constructing a `Request`.

Examples (w/ invalid syntax for EUIDs):

```rust
Request::new(Some(principal), Some(action), Some(resource), context, None); // no schema; works like before
Request::new(Some(User::"alice"), Some(Action::"readFile"), Some(File::"secret_file.txt"), context, Some(schema)); // ok
Request::new(Some(User::"alice"), Some(Action::"readFile"), Some(User::"bob"), context, Some(schema)); // error, invalid resource
```

## Motivation

(Example migrated from #5)

Say that a user wants to allow any `User` to view files in the folder `Folder::"public"`.
Currently, to achieve the desired behavior, the user should define a schema with the action entity `readFile` that can apply to principals of type `User` and resources of type `File`, and then write the following policy.

```
permit(principal, action == Action::"readFile", resource in Folder::"public");
```

Assuming that they pass in inputs where the principal is of type `User` and the resource is of type `File`, this will work as expected.
However, it could also return "allow" for other principal types like `Folder` or resource types like `User`.
This is a bug on the user's end: they shouldn’t make a query with the action `readFile` when the principal is not a `User` and the resource is not a `File`.
They are breaking the contract they stated in their schema.
Nevertheless, it might be confusing that such a query does not result in a "deny".

This RFC proposes to add a check, when constructing the `Request` type, that the query is valid according to the schema.

## Detailed design

Validation and schema-based parsing are both "opt-in" in the sense that they are not required, so we'll the same for query validation.
Validation is done by a separate API (`Validator::validate`), while schema-based parsing is done by passing a (optional) schema argument into various parsing APIs, e.g., `Entities::from_json_str` and `Context::from_json_str`.
If the schema argument is `None`, then parsing does no validation.

This RFC proposes to modify the constructor for the `Request` type to add an optional schema type, similar to schema-based parsing.

## Drawbacks

- This is a breaking change that will affect any users that are manually constructing `Request`s (which is likely all users).

## Alternatives

- Maintain the status quo. Users should enforce that queries conform to their schema prior to authorization.
- Add support for authorization-time checks of entity types, per #5.
This would allow users to manually encode typing restrictions on `principal`s and `resource`s within their policies.

## Unresolved questions

None, at the moment.
