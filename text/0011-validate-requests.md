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

Given a schema, _validation_ checks that policies conform to the schema, and _schema-based parsing_ checks that entities and context conform to the schema.
This RFC proposes to add support for checking that a request conforms to a schema.

## Basic example

Say the schema specifies that an action `readFile` should only be used with principals of type `User` and resources of type `File`.
This RFC proposes to change the signature of the `Request` constructor to add an optional schema argument that can be used to check  argument types when constructing a `Request`.

Examples (using informal syntax for EUIDs):

```rust
Request::new(Some(principal), Some(action), Some(resource), context, None); // no schema; works like before

Request::new(Some(User::"alice"), Some(Action::"readFile"), Some(File::"secret_file.txt"), context, Some(schema)); // ok

Request::new(Some(User::"alice"), Some(Action::"readFile"), Some(Folder::"some_folder"), context, Some(schema)); // error, invalid resource
```

## Motivation

### Example 1: Unexpected authorization decisions

Say that a user wants to allow any `User` to view files in the folder `Folder::"public"`.
Currently, to achieve the desired behavior, the user should define a schema with the action entity `readFile` that can apply to principals of type `User` and resources of type `File`, and then write the following policy.

```
permit(principal, action == Action::"readFile", resource in Folder::"public");
```

Assuming that they pass in inputs where the principal is of type `User` and the resource is of type `File`, this will work as expected.
However, it could also return "allow" for other principal and resource types.
For example, say that the user constructs a request with a `User` principal and `Folder` resource.
If that folder happens to be nested inside `Folder::"public"`, then this request may return an "allow" decision even though (as its name suggests) `readFile` should not be applied to folders.
This is a bug on the user's end: they are breaking the contract they stated in their schema.
Nevertheless, it might be confusing that this request does not result in "deny".

### Example 2: Unexpected authorization-time errors

Validation assures users that their policies are free from certain types of errors.
But it only does so under certain assumptions, one of which being that the input request conforms to the schema.
We currently do not provide utilities to check that this assumption holds.

Consider the setup from [Example 1](#example-1-unexpected-authorization-decisions), where the action `readFile` can only apply to principals of type `User` and resources of type `File`.
In addition, say that entities of type `File` have a Boolean field `isPrivate` that restricts which users can view the file, and entities of type `Folder` do not have this field.
Now consider the following variation of the policy from [Example 1](#example-1-unexpected-authorization-decisions).

```
permit(principal, action == Action::"readFile", resource in Folder::"public")
unless { resource.isPrivate };
```

The validator will find no faults with this policy, guaranteeing that there will be no type errors at authorization time, modulo some restrictions.
But say that the user unintentionally violates these restrictions by passing a request with a `Folder` as the resource.
This request will result in a "deny" (which is presumably what the user intended), but the diagnostics will report a type error (which is unexpected, given that validation succeeded) due to the invalid access of the field `isPrivate`.

### Proposed solution

This RFC proposes to add a check, when constructing the `Request` type, that the request is valid according to the schema.

## Detailed design

Validation and schema-based parsing are both "opt-in" in the sense that they are not required, so we'll want the same for request validation.
Validation is done by a separate API (`Validator::validate`), while schema-based parsing is done by passing a (optional) schema argument into various parsing APIs, e.g., `Entities::from_json_str` and `Context::from_json_str`.
If the schema argument is `None`, then parsing does no validation.

This RFC proposes to modify the constructor for the `Request` type to add an optional schema type, similar to schema-based parsing.

## Drawbacks

- This is a breaking change that will affect any users that are manually constructing `Request`s (which is likely all users).

## Alternatives

- Maintain the status quo. Users should enforce that queries conform to their schema prior to authorization.
- Add support for authorization-time checks of entity types, per [#5](https://github.com/cedar-policy/rfcs/pull/5).
This would allow users to manually encode typing restrictions on principals and resources within their policies.
So, in the example [above](#motivation), the user could include `principal is User` and `resource is File` in the policy text to force a "deny" decision when the principal and resource are not of the appropriate types.

## Unresolved questions

- The text above proposes to modify the current `Request::new` interface. A less invasive alternative would be to provide a new constructor `Request::new_with_validation` that performs the validation check. The downside of the first approach is that it will break existing users. The downside of the second is that it is easy to ignore: Users may not realize they have the option to perform validation on input requests, and may not realize the importance.
