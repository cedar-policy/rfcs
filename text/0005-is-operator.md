# `is` Operator

## Related issues and PRs

- Reference Issues: <https://github.com/cedar-policy/cedar/issues/94>
- Implementation PR(s):

## Timeline

- Start Date: 2023-06-16
- Date Entered FCP:
- Date Accepted:
- Date Landed:

## Summary

This RFC proposes to add an `is` operator to the Cedar language to allow checking equality of entity types.

## Basic example

Say that a user wants to allow any `User` to view files in the folder `Folder::"public"`.
With an `is` operator, the following policy achieves this goal.

```
permit(
  principal is User,
  action == Action::"view",
  resource is File in Folder::"public"
);
```

At evaluation time, `principal is User` will evaluate to true or false depending on the type of `principal`, and `resource is File in Folder::"public"` will evaluate to true or false depending on the type of `resource`, and whether the `resource` is a member of `Folder::"public"`.

## Motivation

The `is` operator in useful in (at least) two common scenarios.

### Use case 1: Input validation

Say that a user wants to allow any `User` to view files in the folder `Folder::"public"`.
Currently, to achieve the desired behavior, the user should define a schema with the action entity "view" that can apply to principals of type `User` and resources of type `File`, and then write the following policy.

```
permit(principal, action == Action::"view", resource in Folder::"public");
```

Assuming that they pass in inputs where the principal is of type `User` and the resource is of type `File`, this will work as expected.
However, it could also return "allow" for other principal types like `Folder` or resource types like `User`.
This is a bug on the user's end: they shouldn’t make a query with the action "view" when the principal is not a `User` and the resource is not a `File`.
They are breaking the contract they stated in their schema.
Nevertheless, it might be confusing that such a query does not result in a "deny".

With an `is` operator, users could instead write the following.

```
permit(
  principal is User,
  action == Action::"view",
  resource is File in Folder::"public"
);
```

`is` acts as a dynamic check on the runtime types of `principal` and `resource`.
This puts the important type information into the policy itself, as opposed to a separate schema, making it easy to tell what the policy does.

### Use case 2: Reduce `has` checks

The `is` operator can also be used in some places where `has` is currently required.
For example, consider the following policy taken from the Cedar [document cloud example](https://github.com/cedar-policy/cedar-examples/tree/main/cedar-example-use-cases/document_cloud).

```
forbid (principal, action, resource)
when
{
  resource has owner &&
  principal != resource.owner &&
  resource has isPrivate &&
  resource.isPrivate
};
```

This policy acts on any type of resource, but can only be satisfied when the resource has `owner` and `isPrivate` attributes.
If the resource does not have these attributes, then the policy is a no-op.
Either way, we need to check whether the attributes exist using `has` to avoid runtime errors.

Now say that only one entity type (e.g., `File`) has the fields `owner` and `isPrivate`.
Then this policy could be written more succinctly as follows.

```
forbid (principal, action, resource is File)
when
{
  principal != resource.owner &&
  resource.isPrivate
};
```

## Detailed design

### Changes required to parser/AST

- Update the grammar and AST to support expressions of the form `e is et` where `et` is a `Name` (e.g., `Namespace::EntityType`).
- Update the grammar and AST to support expressions of the form `e1 is et in e2` (but not `e1 in e2 is et`, because this is more difficult to mentally parse).
- Update the grammar to allow expressions like `e is et` and `e1 is et in e2` in the policy scope.

### Changes required to evaluator

`e is et` will evaluate to true iff `et` is a `Name` (e.g., `Namespace::EntityType`) and `e` is an expression that is an entity of type `et`.
Otherwise it will evaluate to false.
To maintain the property that "conditions in the scope never error," `e is et` will never return an error; it will simply return false if any error occurs.

Namespaces are considered "part of" the entity type. So:

- `User::"alice" is User` is true
- `Namespace::User::"alice" is User` is false
- `Namespace::User::"alice" is Namespace::User` is true
- `User::"alice" is Namespace::User` is false

### Changes required to validator

`e is et` will be typed as `True` if the validator can guarantee that expression `e` is an entity of type `et`, or `False` if the validator can guarantee that `e` is a non-entity type or an entity not of type `et`.
Otherwise, the validator gives `e is et` type `Bool`.

To improve typing precision, we can extend the current notion of "effects" to track information about entity types.
Currently, the validator uses effects to know whether an expression is guaranteed to have an attribute.
In particular, the validator knows that if `e has a` evaluates to true, then expression `e` is guaranteed to have attribute `a`.
We can do something similar for `is`: when the expression `e is et` evaluates to true, expression `e` is guaranteed to be an entity of type `et`.

### Other changes

The Dafny formalization of the Cedar language, corresponding proofs, and differential testing framework in [cedar-spec](https://github.com/cedar-policy/cedar-spec) will need to be updated to include the new `is` operator.

## Drawbacks

1. This is a substantial new feature that will require significant development effort.

2. This change will break existing applications that depend on the structure of policies. For example, if we decide to allow `is` in the policy scope (as shown in the examples above), tools that perform basic "policy slicing" based on the scope will need to decide how to handle the new syntax.

3. The `is` operator makes individual policies easier to understand because the type information is in the policy itself. However, it may make it more difficult to get a global view of how different actions and entity types are used. The schema currently fills this role: it provides a centralized place to provide all typing constraints.

4. The `is` operator may encourage coding practices that go against our recommended "best practices" (more details below).

### Best practice: Using "typed" actions

From the discussion on <https://github.com/cedar-policy/cedar/issues/94>:

> Guidance we have given other customers is that actions should be "typed," in the sense that they include in their name the type of the resource they apply to. So instead of writing
>
>     permit(
>       principal == User::"admin",
>       action == Action::"view",
>       resource is Photo
>     );
>
> you would write
>
>     permit(
>       principal == User::"admin",
>       action == Action::"viewPhoto",
>       resource
>     );
>
> In your schema, you indicate that the "viewPhoto" action should always be accompanied by a `Photo` for the resource, so the policy doesn't need to say that explicitly (and doesn't need to perform a runtime check).

If we support an `is` operator, then customers may be encouraged to use a single "view" action for multiple resource types, rather than a new "viewX" actions for each resource type X.

## Alternatives

1. For the most part, users can currently solve the problems that `is` solves by specifying in the schema what types of principals and resources an action applies to, or by using `has` checks, per the examples in the [Motivation](#motivation) above.
However, in some cases, `is` may result in policies that are easier to read.
(Aside: the issue of "input validation" brought up in [Use case 1](#use-case-1-input-validation) could also be addressed by performing validation against the schema for every input query, but that deserves its own RFC.)

2. Another way to simulate `is` is to add an `entity_type` attribute to entities, and check the type of an entity using `resource.entity_type == "File"` (for example).
However, this requires users to manually add an entity's type as an attribute, and leads to the possibility that an entity might be created with an attribute that doesn't actually match its type.

3. The behavior of `is` can also be simulated using groups.
For each entity type (e.g., `File`), a user could create a group (e.g., `Type::"File"`) and add all entities of that type to the group.
Then to check whether an entity has a particular type, users could use `in` (e.g., `resource in Type::"File"`).
Like alternative (2), this requires some extra work on the part of the user (setting up the memberOf relation), and does not prevent entities from being added as members of the wrong group.

## Unresolved questions

1. Should we allow `is` in the policy scope and, more broadly, how do we determine what to allow in the policy scope?
Currently we only allow `==` and `in` expressions in the scope, with the intention that these expressions can be used to represent RBAC constraints, whereas the more general expressions in the policy condition can be used to express ABAC constraints.
Arguably, the `is` operator helps to represent "roles".

2. Should we allow `is` to apply to action entities? Action entities should _always_ have type `Action`, although they may have different namespaces.
So `is` could still be used to distinguish between `Namespace1::Action` and `Namespace2::Action`.

3. Should users be able to indicate that an entity may be of multiple types, e.g., `principal is [User, Group]`? Can this be combined with `in` (e.g., `principal is [User, Group] in Group::"orgA"`, or even `principal is [User, Group] in [Group::"orgA", Group::"orgB"]`)?
