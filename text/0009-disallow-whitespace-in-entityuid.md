# Disallow embedded whitespace in string representations of the EntityUID

## Related issues and PRs

- Reference Issues: none
- Implementation PR(s): https://github.com/cedar-policy/rfcs/pull/9

## Timeline

- Start Date: 2023-06-19 
- Date Entered FCP: 2023-06-21
- Date Accepted: 2023-06-26
- Date Landed:

## Summary

Disallow embedded whitespace, comments, and control characters in string representations of the EntityUID

## Basic example
Currently, the following syntax is legal:
```
EntityTypeName::from_str("ExampleCo  ::  Photoflash  ::  User  //comment");
```
This change would modify the function so that the string input must be normalized; i.e. all extraneous whitespace, control characters, and comments removed.
```
EntityTypeName::from_str("ExampleCo::Photoflash::User");
```

## Motivation
Similar to other programming languages such as Rust, Cedar is currently whitespace agnostic. This leads to the ability to embed whitespace, control characters like newlines, and comments around the `::` delimiter in an Entity UID.

For example, the following syntax is valid:
```
permit( 
  principal == ExampleCo :: Photoflash  ::  //This is a comment
       :: User::"alice",
  action,
  resource
);

permit( 
  principal == ExampleCo::Photoflash::User:://comment

  "alice",
  action,
  resource
);
```

This capability was little known, even amongst many Cedar team members, and was only identified as a result of a typo in a Cedar demo. While this behavior may be OK inside policy statements, there is a risk when policy contents such as the EntityTypeName are used as strings outside the context of policy statements, such as in the JSON schema representation. For laypersons who are not Cedar experts, these values appear to be normalized strings rather than fragments of Cedar policy syntax, leading to bugs in application code when whitespace and comments can appear in the value.

Examples:
1. The Cedar Schema format models the schema configuration under a JSON key for the namespace. Policy stores which index schemas by namespace are unlikely to recognize the need to normalize the value, leading to the possibility of storing duplicate schema definitions for "ExampleCo::Photoflash" and "ExampleCo  ::  Photoflash" and indeterminate behavior regarding which schema takes effect at runtime.
2. Policy Stores can implement logic that relies on string comparisons against the EntityTypeName. In a real issue, an application using Cedar sought to preclude callers from passing Actions in the inline slice of entity definitions. It did so by checking if an EntityTypeName matched `.*::Action`. It presumed that `:: Action` was invalid syntax and would be rejected by the Cedar evalator, the same as any other syntatically invalid input. This resulted in a bug, as it allowed callers to bypass the extra validation that the application sought to enforce.
3. Customers are anticipated to build meta-permissions layers that restrict callers to manipulating policy store contents for only certain namespaces. This may lead to policies such as `forbid(...) when {context.namespace = "ExampleCo::Photoflash"};`. There is a risk that an unauthorized actor could bypass this restriction by using a namespace with embedded spaces. 

While it is technically possible for applications to mitigate this risk by diligently using Cedar tooling to normalize the values, the little-known nature of this Cedar behavior implies that few will know they *should* normalize the value. As a point of reference, application developers who have worked with Cedar extensively for over a year were bitten by this bug in production. Hence, this is likely to result in bugs in many other Cedar-based implementation with similar logic, risking a perception that Cedar is fragile or unsafe.

## Detailed design
In `EntityTypeName::from_str()`, whitespace would be disallowed throughout -- either before, after, or in the middle of the typename. The analagous change will also be made in functions `EntityNamespace::from_str()` and `EntityUid::from_str()`.

## Drawbacks
This is a breaking change. We do not generally want breaking changes in Cedar. It is being proposed only because it is believed the risk of breakage is low, and any potential short-term impacts to stability will pay long-term dividends in Cedar's perceived reliability.

The parties most at risk are those who accept *ad hoc* values of EntityTypeName from callers in a string format where the values may contain embedded whitespace. At the current time, the only known party who does this in a production setting is Amazon Verified Permissions. Due to the relative newness of Amazon Verified Permissions, this party is accepting of the change as it is not expected to break any production scenarios, and appears to be a valid risk to accept in order to benefit the Cedar community in the long-term.

Other parties at risk are those who use static, programmatically defined values of EntityTypeName where the code contains a typo in the value that accidentally includes additional whitespace. The belief is that this is likely to get caught in a test environment before going to production, and represents a typo that the impacted party may wish to fix, regardless.

The last party at risk are those who allow customers to upload custom schema files where the namespace value may contain whitespaces. The only known party who accepts adhoc schema uploads from customers with namespaces is Amazon Verified Permissions, which is accepting of this change.

To test these assumptions, this change will preceeded by reach-outs to Cedar early adopters to highlight the risks and gain community buy-in on the approach.

## Alternatives
An alternative is to modify the policy syntax to disallow embedded whitespace in Entity UID across all parts of Cedar, including within policy statements. This could be done by treating the UID as a single identifier with special structure (rather than tokenizing it into `::` separated sequence of identifiers).

One additional benefit of this approach is that it can mitigate attempts by pentesters and malicious actors who may seek ways to craft Cedar policy statements that look like they do one thing, but actually do another. The existence of little known parsing behaviors provide an avenue for exploration by this audience, as demonstrated by the following example:

```
permit(
  principal == ExampleCo::Photoflash::User:://"alice"

  "bob", //TODO: Try various tricks to obfuscate this line from readers
  action,
  resource
);
```

Despite the potential benefit, this alternative was rejected due to the high risk of breaking existing Cedar users. In the worst case scenario, a customer may have an existing `forbid` statement that relies on this behavior as illustrated below. By changing the behavior, the `forbid` statement will error at runtime and be skipped, and hence the system could fail open.

```
forbid(
  principal in ExampleCo:: Photoflash::UserGroup::"someGroup", //Accidential typo, but valid syntax
  action == ExampleCo:: Photoflash::Action::"write",
  resource
);
``` 

This risk is too great. Therefore, the suggested approach is a compromise that mitigates the known production bugs with fewer risks. Any concerns about pentesters and malicious actors crafting obfuscated policies will need to be addressed by other non-breaking means, such as linter warnings and syntax highlighting.
