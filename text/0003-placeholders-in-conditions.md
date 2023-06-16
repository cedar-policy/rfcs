- Start Date: 2023-06-15
- Target Major Version: 2.x
- Reference Issues: https://github.com/cedar-policy/cedar/issues/81
- Implementation PR:

# Summary

__Support template placeholders in conditions__

This RFC proposes to allow the `?principal` and `?resource` placeholders to appear in the `when`/`unless` conditions of a policy, not just in the policy scope.

NB: This RFC was migrated from https://github.com/cedar-policy/cedar/issues/81 as our RFC process was introduced and formalized.

# Basic example

Example 1, from @WanderingStar

```
@id("Admin")
permit(
  principal == ?principal,
  action,
  resource)
when {
    // take any action in the scope that you're admin on
    resource in ?resource

    // allow access up the tree for navigation
    || (action == Action::"Navigate" && ?resource in resource)
};
```

Example 2

```
permit(principal, action, resource)
when {
    ?principal has currentAccessLevel
        && ?principal.currentAccessLevel >= 2
};
```

# Motivation

With this change, we can write policies like the above that perform multiple checks on `?principal` or `?resource`.
We can also write policies that perform checks other than `in` or `==` on `?principal` or `?resource`, such as checking attributes of `?principal` or `?resource`.
In Example 1 above, this feature allows us to write this as a single template, rather than as two separate templates that we'd have to make sure are always instantiated together (which is an additional maintenance burden).
In Example 2, this feature allows us to write this as a template, where without this feature we'd be unable to use a template for this purpose.

# Non-proposals

This RFC is _not_ proposing any change to what syntax is valid in the policy scope. For instance, the following remains _invalid_:
```
permit(
  principal,
  action,
  ?resource in resource
);
```
The only valid uses of `?resource` in the policy scope are `resource == ?resource` and `resource in ?resource`, and this RFC is not proposing to change that.

Of course, the above policy could be legally written as the following, in this RFC's proposal:
```
permit(principal, action, resource)
when { ?resource in resource };
```

# Drawbacks

- It becomes possible to write more complex Cedar policies, that may be harder for humans to read and reason about.

## Non-drawbacks

- Implementation cost in Cedar should be low.
- This is not a breaking change, either for Cedar syntax (all existing Cedar policies remain valid) or for Cedar APIs.

# Alternatives

In https://github.com/cedar-policy/cedar/issues/81, @mwhicks1 suggested that Example 1 could be accomplished with "template groups" instead.
With that solution, we would have two separate templates, but Cedar would provide a mechanism ensuring that they are always instantiated together, with the same arguments.
Unfortunately (as @mwhicks1 also pointed out, in a comment on this RFC), "template groups" would not alone be sufficient for Example 1, if the current restrictions on placeholders and the policy scope remain, because there would be no way to express the `?resource in resource` part.
Likewise, it's difficult to see how template groups would solve the use-case in Example 2.
