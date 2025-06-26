# isInRangeList Operator for ipaddr Type

## Related issues and PRs

- Reference Issues: N/A
- Implementation PR(s): 

## Timeline

- Started: 2025-06-26
- Accepted: TBD
- Stabilized: TBD

## Summary

This RFC proposes the addition of a new method-style operator, `.isInRangeList`, to Cedar's `ipaddr` extension type. This operator will take a single `ipaddr` value (the receiver) and check for its inclusion within a `$Set<ipaddr>$` (the argument). It evaluates to `true` if the receiver IP address or range is contained within any of the IP address ranges provided in the argument set, and `false` otherwise. This feature is designed to dramatically simplify policies that must verify a request's source IP against an allowlist of allowed CIDR blocks, improving policy readability, scalability, and maintainability.

## Basic example

A primary use case for the `ipaddr` type is to restrict access based on the source IP address of a request, which is often provided in the request context. When an application needs to check against a list of multiple allowed IP ranges (e.g., corporate networks, trusted partner networks), the current approach becomes verbose and difficult to manage. 

```
// Policy to allow access only from corporate IP ranges (current method)
permit (
  principal,
  action == Action::"accessAdminDashboard",
  resource
)
when {
  ip(context.network.source_ip).isInRange(ip("198.51.100.0/24")) ||
  ip(context.network.source_ip).isInRange(ip("203.0.113.0/24")) ||
  ip(context.network.source_ip).isInRange(ip("192.0.2.0/25")) ||
  ip(context.network.source_ip).isInRange(ip("2001:db8:a001::/48"))
};
```

The proposed `.isInRangeList` operator simplifies this logic into a single, intuitive function call, making the policy's intent immediately clear.

```
// Policy to allow access only from corporate IP ranges (proposed method)
permit (
  principal,
  action == Action::"accessAdminDashboard",
  resource
)
when {
  ip(context.network.source_ip).isInRangeList(
    [
      ip("198.51.100.0/24"),
      ip("203.0.113.0/24"),
      ip("192.0.2.0/25"),
      ip("2001:db8:a001::/48")
    ]
  )
};
```

This syntax leverages Cedar's existing `Set` literal notation and method-style function calls , making it a natural extension of the language.

## Motivation
The addition of the `.isInRangeList` operator is motivated by several key factors that align with Cedar's goals of expressiveness and readability.

### Smaller JSON Formatted Policies
The current method of chaining `.isInRange()` calls with `||` operators creates a large and object tree that can quickly exceeded the stack depth and recursion limit of systems. The introduction of an `.isInRangeList` operator would allow for the reduction in not only the policy objet's size, but also it's overall complexity, reducing parsing time and allowing for more IP Address Conditions to be expressed within a single policy without exceeding stack depth limits.

### Improved Policy Readability and Authoring
Cedar policies are designed to be easy to read and understand by both technical and non-technical stakeholders. Chaining `.isInRange()` calls with `||` operators creates syntactically complex expressions that obscure the simple intent of "is this IP in our allowlist?". As the list of IP ranges grows, the policy becomes increasingly unwieldy, increasing cognitive load and the likelihood of authoring errors, such as typos or misplaced logical operators. The proposed operator replaces a complex boolean expression with a single, declarative function call, significantly improving the clarity and conciseness of the policy.

### Enhanced Scalability and Maintainability
The proposed operator is not an entirely new concept but rather a natural extension of existing language patterns. Cedar already provides collection-oriented operators like `.containsAny()` for Sets, which checks for the intersection of two sets. The `.isInRangeList` operator applies a similar "check against a collection" pattern but with the specific semantics of IP range inclusion. This demonstrates that the proposal fits harmoniously within the existing language design, filling a logical gap rather than introducing an unfamiliar paradigm. This consistency makes the feature easier for users to learn and adopt.

### Potential for Performance Optimization
While not the primary motivation, a native operator can be implemented more efficiently within the Cedar evaluation engine than a deeply nested tree of `||` expressions. The evaluator can implement a direct, short-circuiting loop over the argument set. In contrast, evaluating a long chain of || operators involves more overhead in traversing the Abstract Syntax Tree (AST). This aligns with reasoning from previous RFCs, where simplifying the AST was seen as a benefit for the evaluator.   

## Detailed design

This is the bulk of the RFC. Explain the design in enough detail for somebody familiar with Cedar to understand, and for somebody familiar with the implementation to implement. This should get into specifics and corner-cases, and include examples of how the feature is used. Any new terminology should be defined here.

// TODO

## Drawbacks

* __Increased Language Surface Area:__ Any new feature adds to the complexity of the language. However, the proposed operator's logic is a straightforward composition of existing primitives (`.isInRange` and set iteration), making it an intuitive and easily understood addition rather than a complex new concept.

* __Implementation Effort:__ This is a substantial feature that requires coordinated development effort across the cedar core repository (parser, validator, evaluator) and the cedar-spec repository for the formal model. This is a standard and expected cost for any significant language enhancement, similar to the effort required for features like the is operator.   

* __Impact on SMT-based Tooling:__ As noted in the discussion for RFC-0057, language changes can affect automated reasoning tools. The analysis of`.isInRangeList` should be reducible to the analysis of a bounded disjunction over the elements of the set S. For SMT solvers, this is a tractable problem. The impact is expected to be minimal and manageable by tool authors.

## Alternatives

### The Status Quo (Chained `||`)
This is the current method for checking against multiple IP ranges. As detailed extensively in the Motivation section, this approach is not scalable and suffers from poor readability and maintainability, especially as the number of IP ranges grows. It is the problem this RFC aims to solve.

## Unresolved questions
Detailed Design requires input from someone more familiar with developing core Cedar functionality and SMT.
