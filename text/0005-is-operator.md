# `is` Operator

## Related issues and PRs

- Reference Issues: <https://github.com/cedar-policy/cedar/issues/94>
- Implementation PR(s):

## Timeline

- Start Date: 2023-06-16
- Date Entered FCP: 2023-07-21
- Date Accepted: 2023-07-28
- Date Landed:

## Summary

This RFC proposes to add an `is` operator to the Cedar language that allows users to check the type of entities.

## Basic example

Say that a user wants to allow any `User` to view files in the folder `Folder::"public"`.
With an `is` operator, the following policy achieves this goal.

```
permit(
  principal is User,
  action == Action::"viewFile",
  resource is File in Folder::"public"
);
```

At evaluation time, `principal is User` will evaluate to true if the type of `principal` is `User`, and `resource is File in Folder::"public"` will evaluate to true if the type of `resource` is `File` and it is a member of `Folder::"public"`.

## Motivation

The `is` operator allows users to restrict the scope of their policies to particular entity types.

In many cases, this can also be done by adding restrictions to the schema.
For example, the `appliesTo` field for each action in the schema allows users to specify which entity types can be used as principals and resources for that action.
In the example [above](#basic-example), the schema could specify that `viewFile` should only apply to principals of type `User` and resources of type `File`.
However, this doesn't help if the user is not using a schema, the action is unconstrained, or the policy refers to an action that may act on multiple principal/resource types.

For example, here is one case where the action is unconstrained, taken from the Cedar [document cloud example](https://github.com/cedar-policy/cedar-examples/tree/main/cedar-example-use-cases/document_cloud).

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

This policy applies to any principal, action, resource pair, but requires that the resource has `owner` and `isPrivate` attributes.
If the resource does not have these attributes, then the policy is a no-op.

Say that only one entity type (e.g., `File`) has the fields `owner` and `isPrivate`.
Then this policy can be written more succinctly as follows.

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
- Update the grammar to allow expressions like `e is et` and `e1 is et in e2` in the policy scope for principals and resources.
The action part of the scope will only allow expressions like `action == Action::"foo"` and `action in [Action::"foo", Action::"bar"]`, as before.

### Changes required to evaluator

`e is et` will evaluate to true iff `et` is a `Name` (e.g., `Namespace::EntityType`) and `e` is an expression that is an entity of type `et`.
If `e` is an entity-typed expression, but does not have type `et`, then `e is et` will evaluate to false.
If `e` is a non-entity-typed expression, the evaluator will produce a type error.

Note that this design maintain the property that "conditions in the scope never error" because `principal` and `resource` are guaranteed to be entities, so the expression `(principal|resource) is et` will never error.

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

3. The `is` operator may encourage coding practices that go against our recommended "best practices" (more details below).

### Best practice: Using "typed" actions

From the discussion on <https://github.com/cedar-policy/cedar/issues/94>:

> Guidance we have given other customers is that actions should be "typed," in the sense that they include in their name the type of the resource they apply to. So instead of writing
>
> ```
> permit(
>   principal == User::"admin",
>   action == Action::"view",
>   resource is Photo
> );
> ```
>
> you would write
>
> ```
> permit(
>   principal == User::"admin",
>   action == Action::"viewPhoto",
>   resource
> );
> ```
>
> In your schema, you indicate that the "viewPhoto" action should always be accompanied by a `Photo` for the resource, so the policy doesn't need to say that explicitly (and doesn't need to perform a runtime check).

If we support an `is` operator, then customers may be encouraged to use a single "view" action for multiple resource types, rather than a new "viewX" action for each resource type X.

## Alternatives

1. Another way to simulate `is` is to add an `entity_type` attribute to entities, and check the type of an entity using `resource.entity_type == "File"` (for example).
However, this requires users to manually add an entity's type as an attribute, and leads to the possibility that an entity might be created with an attribute that doesn't actually match its type.

2. The behavior of `is` can also be simulated using groups.
For each entity type (e.g., `File`), a user could create a group (e.g., `Type::"File"`) and add all entities of that type to the group.
Then to check whether an entity has a particular type, users could use `in` (e.g., `resource in Type::"File"`).
Like alternative (2), this requires some extra work on the part of the user (setting up the memberOf relation), and does not prevent entities from being added as members of the wrong group.

## Resolved questions

- Should we allow `is` in the policy scope?
Currently we only allow `==` and `in` expressions in the scope, with the intention that these expressions can be used to represent RBAC constraints, whereas more general expressions in the policy condition can be used to express ABAC constraints.
  - _Decision:_ We will allow `is` and `is ... in` in the scope.
  - _Summary of discussion:_
    - We feel that `is` is natural to write in the policy scope since it limits the "scope" of the policy.
    - Most requests we have received for this feature use an example with `is` in the scope, confirming our belief that this is the most natural location for its use.
    - Although `is` is not currently used for policy indexing, it could be in the future, and current indexing strategies can safely ignore `is` constraints in the meantime.
- Should users be able to indicate that an entity may be of multiple types, e.g., `principal is [User, Group]`? Can this be combined with `in` (e.g., `principal is [User, Group] in Group::"orgA"`, or even `principal is [User, Group] in [Group::"orgA", Group::"orgB"]`)?
  - _Decision:_ We will not support this. The syntax is more difficult to read and the same behavior can be achieved by writing multiple policies instead. We may reconsider this position based on user feedback.
