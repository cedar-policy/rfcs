- Start Date: 2023-06-14
- Target Major Version: X.x
- Reference Issues: <https://github.com/cedar-policy/cedar/issues/94>
- Implementation PR:

# Summary

This RFC proposes to add an `is` operator to the Cedar language to allow checking equality of entity types.

# Basic example

Say that a user wants to allow any `User` to view files in the folder `Folder::"public"`.
With an `is` operator, the following policy achieves this goal.

```
permit(
  principal is User,
  action == Action::"view",
  resource is File in Folder::"public"
);
```

At evaluation time, `principal is User` and `resource is File` will evaluate to true or false depending on the type of principal.

# Motivation

Say that a user wants to allow any `User` to view files in the folder `Folder::"public"`.
To achieve the desired behavior, the user could define a schema with the action entity "view" that can apply to principals of type `User` and resources of type `File`, and then write the following policy.

```
permit(principal, action == Action::"view", resource in Folder::"public");
```

Assuming that they pass in inputs where the principal is of type `User` this will work as expected.
However, it could also returns "allow" for other principal types like `Folder`s.
This is a bug on the user's end: they shouldn’t make a query with the action "view" when the principal is not a `User`.
They are breaking the contract they stated in their schema.
Nevertheless, it might be confusing that this query is not disallowed.

With an `is` operator, users could instead write the following.

```
permit(
  principal is User,
  action == Action::"view",
  resource is File in Folder::"public"
);
```

At evaluation time, `principal is User` will evaluate to true or false depending on the type of principal.
This puts the important type information into the policy itself, making it (presumably) simpler to understand and easier to audit.

# Detailed design

## Changes required to parser/AST

- Extend the grammar's definition of `RELOP` to include `is`.
- Update the `Relation` production to allow chained operations (to support `.. is .. in ..`). Not
- Extend the grammar's `Principal`, `Action`, and `Resource` rules to allow `is`.
- Add a new `BinaryOp` (`Is`) to the AST.

Additional changes required if we decide to allow `is` in the policy scope:


- Extend the `PrincipalOrResourceConstraint` and `ActionConstraint` enums to allow `is`.

## Changes required to evaluator

`e is et` will evaluate to true iff `e` is an entity-typed expression and `et` is an identifier.
Otherwise it will evaluate to false.
To maintain the property that "conditions in the scope never error", `e is et` will never return an error.
It will simply return false if any error occurs.

### Namespaces

Namespaces are considered "part of" the entity type. So:

- `User::"alice" is User"` is true
- `Namespace::User::"alice" is User` is false
- `Namespace::User::"alice" is Namespace::User` is true
- `User::"alice" is Namespace::User` is false

## Changes required to validator

The validator currently track "effects" to know whether a 

An expression like `e is et` may have type `True` or `False` depending on whether additional information is known 

## Other changes

Note: the Dafny formalization of the Cedar language and corresponding proofs in cedar-spec will also need to be updated with the new `is` operator.

# Drawbacks

- This is a substantial new feature, which will require significant development effort and will modify much of the codebase. This allows for the possibility of bugs creeping in. We will mitigate this through thorough code reviews and testing, as well as differential testing against the Dafny implementation (which we expect will be done first).
- This change will break existing applications that depend on the syntactic structure of policies. In particular, if we decide to allow `is` in the policy scope (as shown in the examples above), tools that perform basic "policy slicing" based on the scope will need to decide how to handle the new syntax.
- One concern raised so far: does this feature encourage bad coding practices?

# Alternatives

For the most part, users can do this currently by specifying what types of principals and resources an action applies to in the schema.

For example, consider the example [above](#basic-example). To achieve the desired behavior, the user could define a schema with the action entity "view" that can apply to principals of type `User` and resources of type `File`, and then write the following policy:

```
permit(principal, action == Action::"view", resource in Folder::"public");
```

Assuming that they pass in inputs that match the schema type, this will work as expected. However, it would also returns "allow" for other principal types like `Folder`s. This is a bug on the user's end: they shouldn’t make a query with the action "view" when the principal is not a `User`. They are breaking the contract they stated in their schema. Nevertheless, it might be confusing that this query is not disallowed.

# Adoption strategy

This PR proposes to add a new language feature to Cedar, so consumers of the current `cedar-policy` package from crates.io should, for the most part, experience no breakage. The only exception is if they were relying on the EST to do custom policy parsing. In this case, they will need to update their custom parsing to account for the new `is` syntax.

# Unresolved questions

1. Should we allow `is` operators to be chained with `in`, e.g., `principal is User in Group::"foo"`? If so, is `principal in Group::"foo" is User` also allowed (and equivalent)?
2. Do we allow expressions with `is` in the policy scope, or only in the condition?
3. Assuming we allow `is` in the policy scope, Do we allow `is` to 
4. Should users be able to indicate that a variable may be of multiple types, e.g., `principal is [User, Group]`?
5. Given that the `is` operator encodes which entity types should be used with each policy, should we remove the "appliesTo”" components of the schema? Assuming we support specifying multiple types with `is` (see Q2 above), the "appliesTo" information is potentially redundant.

(Additional questions TBD)

My current tentative answer to the questions are:

1. Allow `principal is User in Group::"foo"`, but disallow `principal in Group::"foo" is User` because that is harder to read.
2. Yes, allow in scope.
3. Yes, allow with actions.
4. Yes, allow list syntax.
5. Keep both `is` and the "appliesTo" lists.