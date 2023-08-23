# Generalizing template placeholders

## Related issues and PRs

- Reference Issues: https://github.com/cedar-policy/cedar/issues/81
- Implementation PR(s):

## Timeline

- Started 2023-06-15
- Entered FCP (intent to accept) 2023-06-28
- FCP aborted 2023-07-03
- Closed by RFC author 2023-07-12

See comments on [the PR thread](https://github.com/cedar-policy/rfcs/pull/3) for more on the rationale for these decisions.

# Summary

This RFC proposes to generalize templates in two ways:

1. The `?principal` and `?resource` placeholders may appear in the `when`/`unless` conditions of a policy when they also appear in the policy scope.

2. Placeholder variables are not limited to `?principal` and `?resource`. A general variable binding mechanism permits introducing additional placeholder variables in the policy, which can appear in the `when`/`unless` conditions. Moreover, these additional variables need not be linked to values of entity type only; any Cedar type is acceptable. Including `?principal` and/or `?resource` in this list is optional; restrictions on their use are enforced either way.

Because the types of placeholder variables (other than `?principal` and `?resource`) are not known, any validation of templates cannot occur until _link time_. Currently, templates are mostly validated when created, with only a small check carried out at link time.

# Basic examples

### Example 1:

```
permit(
  principal in ?principal,
  action,
  resource)
when {
       ?principal has currentAccessLevel
    && ?principal.currentAccessLevel >= 2
};
```
This template uses `?principal`, an ancestor of `principal`, to be used in the `when` clause (the condition) of the policy. Notice that `?principal` appears in the scope; this is required in order for it to also appear in the condition.

### Example 2

```
@id("Admin")
template (?bound)
permit(
  principal == ?principal,
  action,
  resource)
when {
    // take any action in the scope that you're admin on
    resource in ?bound

    // allow access up the tree for navigation
    || (action == Action::"Navigate" && ?bound in resource)
};
```
This example introduces a fresh placeholder variable `?bound` which it uses in the condition. It is adapted from @WanderingStar [#81](https://github.com/cedar-policy/cedar/issues/81), in which the placeholder `?resource` is used instead of `?bound`. Using the `?resource` placholder is not allowed since it does not (and cannot) also appear in the scope.

# Motivation

This change expands the space of expressible templates. Applications can build more policies by template linking rather than by constructing the policies directly, e.g., by concatenating strings. There are two benefits of template-based policy construction:

1. It is easier to comprehensively analyze, whether manually or automatically, an application's permissions. If all policies are either static or linked templates, then an auditor or tool need only look at the policy store to explore the state of an application's possible permissions. If policies could be created on the fly, then an auditor or tool would have to _also_ analyze the application code.

2. Template-based policy construction prevents code injection attacks (i.e., in the style of SQL injection). Templates act like prepared statements, where placeholders can only be instantiated with data values; they cannot be instantiated with strings that could be reinterpreted as arbitrary policy code. Using templates whenever possible is an important protection for applications that add policies as a result of user actions.

This RFC was motivated by a particular customer use-case, i.e., [#81](https://github.com/cedar-policy/cedar/issues/81).

# Detailed design

This RFC does not propose any change to what syntax is valid in the policy scope. For instance, the following remains _invalid_:
```
permit(
  principal,
  action,
  ?resource in resource
);
```
The only valid uses of `?resource` in the policy scope are `resource == ?resource` and `resource in ?resource`, and this RFC is not proposing to change that. This RFC also disallows the use of `?principal` and `?resource` in the condition if they don't _also_ appear in the scope.

Both restrictions are in place because these two placeholder variables have special meaning for indexing policies in a policy store. In particular, looking _only_ at the linking information (i.e., to what `?principal` and/or `?resource` are bound) is sufficient to precisely select linked policies for particular requests. If the variables could only be bound in the condition or in other positions in the scope, and used in arbitrary contexts, it would lead to selecting superfluous policies.

## Fresh placeholder variables

To support a policy like the one above, this RFC proposes support for placeholder variables beyond `?resource` and `?principal`. With their support, we can write:
```
template (?lowerbound)
permit(principal, action, resource)
when { ?lowerbound in resource };
```
Here, the `template (?lowerbound)` part _introduces_ a fresh placeholder variable which can be used legally within the policy template that follows. Eliding the `template (?lowerbound)` prefix would be illegal, signaling an unbound variable.

Multiple variables can be introduced together, separated by commas, e.g.,
```
template (?user, ?resourcebound)
permit(principal, action, resource)
when {
     ?resourcebound in resource
  && principal in ?user.delegates
};
```

Policy writers can choose to include `?principal` and/or `?resource` in the list of template variables if they like, but doing so is not required. These two variables retain their special status.

If a variable is included in the list that does not appear in the actual template, we can issue a warning.

While all introduced placeholder variables presented so far are assumed to be entities (just like `?principal` and `?resource`), there is no reason why they cannot have arbitrary type. The particular type of the placeholder need not be given, for simplicity.

## Validation

Eliding the type of a placeholder variable poses a problem for validating templates when they are created, without considering particular linkages. This is because we cannot validate an expression like `?bound.name` without knowing the type of `?bound`.

Instead, validation of templates involving variables beyond `?principal` and `?resource` can be deferred to link time. At that point, we know the exact type of the variable, based on the value it is linked to. This is true whether the variable is an entity or a primitive like `string`, `bool`, etc.

Link-time validation has the benefit that it is lower overhead to write the templates, and potentially more flexible, since the particulars of the types don't need to be spelled out, and could even be different for two linkages of the same template. New entity types created after the template don't necessarily require changing the template to add a type annotation.

Link-time validation has three drawbacks, though.

1. Fundamental errors in a template are not discovered until the template is first linked. E.g., `permit(principal in ?principal,action,resource) when { 1 < "hello" >}` will _always_ be invalid when linked, and it would be nice to know that as early as possible.

2. It may be more difficult to analyze the possible impact of a template by considering all of its possible safe linkages. Providing the types essentially puts useful bounds on how templates can be linked safely in the future.

3. Validation is more expensive at linkage time. If we provided types for placeholders, we could mostly validate the template when it is added to the store, and then just check at link time that the linkages to variables have the correct types.

To avoid link-time validation being a breaking change, we can still do creation-time validation when the only variables are `?principal` and `?resource`.

# Drawbacks

This adds new syntax to the Cedar language.

It relegates (most) validation to link time, which has the drawbacks mentioned in the previous section.

# Alternatives

## Type annotations

One obvious alternative would be to annotate placeholder variables with types so that templates can be validated without knowing particular linkages. For example, we might rewrite the example above to be:
```
template (?user:User, ?resourcebound:DeviceGroup)
permit(principal, action, resource)
when {
     ?resourcebound in resource
  && principal in ?user.delegates
};
```
Here we have added `:User` and `:DeviceGroup` type annotations to the introduced variables. The validator can treat `?user` and `?resourcebound` as respectively having these types when considering this template, e.g., to make sure that `?user` truly does have a `delegates` attribute.

We could also allow the appearance of `?principal` and `?resource` in the list of variables, in order to give them types as well. Doing so is probably not necessary, however, because the types of these placeholder variables can be inferred from the schema (based on entity type given to `principal` and `resource` during "cross product" validation, and respectively the `memberOfTypes` portions of those entity types).

This alternative is more work to implement and more effort for users, but mitigates the drawbacks mentioned above.

## Use type parameter syntax

Rather than write `template (?user, ?resourcebound) permit ( principal, ...)` an alternative would be to write `permit<?user,?resourcebound>( principal, ...)`. Using the `<...>` notation resembles parameterization on types used in other languages, as with C++ templates and Java generics.

The benefit of this syntax is that (1) it does not introduce a new keyword (`template`); (2) a normal policy looks closer to a "template" without parameters; and (3) it follows conventions similar to previous languages. I don't know if the parser would be any harder to write with this alternative syntax.
