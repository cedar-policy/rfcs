# RFC Template Disallow embedded whitespace in EntityUID

## Related issues and PRs

- Reference Issues:
- Implementation PR(s): 

## Timeline

- Start Date: 2023-06-19 
- Date Entered FCP:
- Date Accepted:
- Date Landed:

## Summary

Disallow embedded whitespace, comments, and control characters in EntityUID

## Basic example

Currently, the following syntax is legal:
```
permit( 
  principal == ExampleCo :: Photoflash  ::  //This is a comment
       :: User::"alice",
  action,
  resource
);

permit( 
  principal == ExampleCo::Photoflash::User:://"alice"

  "bob",
  action,
  resource
);
```

This change would modify the parser so that the same policies must be expressed as follows:
```
permit( 
  principal == ExampleCo::Photoflash::User::"alice",
  action,
  resource
);

permit( 
  principal == ExampleCo::Photoflash::User::"bob",
  action,
  resource
);
```
## Motivation
Similar to other programming languages such as Rust, Cedar is currently whitespace agnostic. This leads to the ability to embed whitespace, control characters like newlines, and comments around the `::` delimiter in an Entity UID.

This capability was little known, even amongst Cedar team members, and was only identified as a result of a typo in a Cedar demo. This behavior presents a risk along a few dimensions. First, much of the tooling around Cedar presumes these values are strings.

Examples:
1. The Cedar Schema format models the schema configuration under a JSON key for the namespace. By all appearances, this is a JSON string rather than a fragment of Cedar syntax. Policy stores which index schemas by namespace are unlikely to recognize the need to normalize the value, leading to the possibility of storing duplicate schema definitions for "ExampleCo::Photoflash" and "ExampleCo  ::  Photoflash" and indeterminate behavior regarding which schema takes effect at runtime.
2. Policy Stores can implement logic that relies on string comparisons against the EntityType. In a real issue, an application using Cedar sought to preclude callers from passing Actions in the inline slice of entity definitions. It did so by checking if an EntityType matched `.*::Action`. It presumed that `:: Action` was invalid syntax and would be rejected by the Cedar evalator, the same as any other syntatically invalid input. This resulted in a bug, as it allowed callers to avoid the extra validation that the application sought to enforce. While it is technically possible for the application to resolve this by using Cedar tooling to normalize the value, the little-known nature of this Cedar behavior implies that few will know they should normalize the value. Hence, this is likely to result in bugs in other Cedar-based implementation with similar logic.
3. Customers are anticipated to build meta-permissions layers that restrict callers to manipulating policy store contents for only certain namespaces. This may lead to policies such as `forbid(...) when {context.namespace = "ExampleCo::Photoflash"};`. There is a risk that an unauthorized actor could bypass this restriction by using a namespace with embedded spaces. 

In addition to the above, pentesters and malicious actors will explore ways to craft Cedar policy statements that look like they do one thing, but actually do another. The existence of little known parsing behaviors provide an avenue for exploration by this audience, as demonstrated by the second example in the opening of this RFC:

```
permit( 
  principal == ExampleCo::Photoflash::User:://"alice"

  "bob", //TODO: Try various tricks to obfuscate this line from readers
  action,
  resource
);
```

## Detailed design
The UID will be treated as a single identifier with special structure (rather than tokenizing it into `::` separated sequence of identifiers).

## Drawbacks
This is a breaking change. We do not generally want breaking changes in Cedar. In the worst case scenario, a customer may have an existing `forbid` statement that relies on this behavior as illustrated below. By changing the behavior, the `forbid` statement will error at runtime and be skipped, and hence the system could fail open.

```
forbid(
  principal in ExampleCo:: Photoflash::UserGroup::"someGroup", //Accidential typo, but valid syntax
  action == ExampleCo:: Photoflash::Action::"write",
  resource
);
```

This breaking change is only being considered due to the relative newness of Cedar and the probability of breaking a real production scenario being low, and it can only be done if the community agrees that altering this behavior will pay long term dividends that outweight the risk of near-term impacts.

## Alternatives

We could change the behavior of `EntityTypeName::from_str()` without changing the syntax used in Cedar policies themselves. In `EntityTypeName::from_str()`, whitespace would be disallowed throughout -- either before, after, or in the middle of the typename. In Cedar policies, whitespace would still be allowed in every position it’s allowed today.  This would avoid a breaking change to the Cedar language and avoid diverging from the behavior of most mainstream programming languages, which do allow whitespace around namespaces and namespace separators.  This alternative would fully address the Examples 1, 2, and 3 in this PDF, and while it would not address the malicious policy example given, that should be weighed against the impact of a breaking change to the Cedar language and diverging from other commonly-used languages.

