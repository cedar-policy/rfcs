- Start Date: 2023-06-16
- Target Major Version: 2.x
- Reference Issues: https://github.com/cedar-policy/cedar/issues/106
- Implementation PR: 

# Summary

Allow template policies to be grouped together, so they can be linked all at once. Doing so ensures that the application writer cannot mistakenly link one policy in the group separately from all the policies.

# Basic example

Consider this pair of template policies:
```
@id("policy1")
permit(
  principal == ?principal,
  action, 
  resource in ?resource);

@id("policy2")
permit(
  principal == ?principal,
  action == Action::"viewDoc",
  resource in Directory::"DivisionDocs");
```
This pair represents a _role_: the linked principal can access any resource in the linked group (policy1), or it can view any document in a particular collection. A grouping mechanism would help connect them. For example:
```
@templategroup("role1")
@id("policy1")
permit(
  principal == ?principal,
  action, 
  resource in ?resource);

@templategroup("role1")
@id("policy2")
permit(
  principal == ?principal,
  action == Action::"viewDoc",
  resource in Directory::"DivisionDocs");
```
Here we have labeled both policies with the same `@templategroup`; we link them at the same time using an API that references the group (`role1`), rather than individual policy (`policy1` and `policy2`).

# Motivation

We want to make sure that related template policies are always linked, together. Doing so ensures that permissions-level invariants are properly maintained.

Grouping is also useful when reading and analyzing policies, since it makes evident that template groups represent a uniform whole that should be reasoned about together. A UX for policy management could display grouped policies together, in a different color, etc. Automated analysis must consider all possible linkages for templates, and the grouping adds useful constraints, e.g., that a linkage principal _p_ for `policy1` implies a linkage of the same _p_ for `policy2` in the same template group.

# Detailed design

The updated APIs are for the CLI and core Cedar.

In the presentation above in the [Basic example](#basic-example), I have shown the syntax that would be available to user using the CLI. While the CLI interprets `@id` to be the policy ID, the Cedar libraries do not treat it specially. The same should be true for `@templategroup`. 

The change to APIs to implement this CLI syntax change would be to allow linking not just by policy ID, but also (or instead) by group ID. You would have to change APIs so that templates can be coupled either with _just_ a group ID, or with both a group ID and policy ID. In the former case, the linking API would not have to change -- all of the templates in the group identified by the ID are linked. As a practical matter, I have a feeling this won't work because `PolicySet`s seem to store templates in a map indexed by `PolicyID`, which has to be unique. Whichever approach we take, a linkage for group `role1` should link any template having that group. A linkage for ID `policy1` should _fail_ if `policy1` also has a `@templategroup` annotation -- this is important for forbidding linkages to individual group policies.

# Drawbacks

The main reason not to do this is that it adds extra code that customers _could_ implement themselves, using the existing annotation mechanism. 

However, doing so would lose the benefits of making the mechanism known to UIs, analysis tools, etc. and it would impose extra work on customers. The code for handling linking in the CLI should be a basis for customers that want to identify templates and template groups in some way other than by annotation metadata.

# Alternatives

We could add new syntax to Cedar that supports policy groups. For example
```
@id("role1")
{ 
    @id("policy1")
    permit(
      principal == ?principal,
      action, 
      resource in ?resource);

    @id("policy2")
    permit(
      principal == ?principal,
      action == Action::"viewDoc",
      resource in Directory::"DivisionDocs");
}
```
Here we allow any statements to by syntactically grouped within braces, and add an annotation on the group. This is potentially more visually clear to readers, and evokes [AWS IAM policies, which can consist of multiple statements grouped together](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_statement.html). But it would require extending the Cedar grammar.

We could opt to do nothing at the level of the language, and rely on users of Cedar (such as Amazon Verified Permissions) to implement grouping using metadata of their choice, even as suggested here. We could also add the grouping syntax above, but not more than that, again relying on users to interpret the metadata annotations themselves. However, if grouping policies is likely to be generally useful, it seems useful to provide support for it.

Users can also achieve the desired grouping effect by combining both templates into a single one:
```
@id("bothpolicies")
permit(
  principal == ?principal,
  action, 
  resource)
when {
   resource in ?resource ||
   (action == Action::"viewDoc" && resource in Directory::"DivisionDocs")
};
```
This has the drawback that the combined policy is more difficult to understand. (It also requires the template slot `?resource` to appear in the `when` condition, rather than the scope, which [RFC-0003](https://github.com/cedar-policy/rfcs/pull/3) aims to address.) Finally, this policy will not index very well in Verified Permissions because constraints on the `action` and `resource` do not appear in the policy scope (and could not, since there is more than one).

# Unresolved questions

API design is not carefully fleshed out. Open to particular proposals here from people who know more.
