# Make isInRange Operator Variadic for ipaddr Type

## Related issues and PRs

- Reference Issues: N/A
- Implementation PR(s): 

## Timeline

- Started: 2025-06-26
- Accepted: TBD
- Stabilized: TBD

## Summary

This RFC proposes modifying the existing `.isInRange` operator to Cedar's `ipaddr` extension type. The operator currently is unary, taking a single IP Address; but expanding it to be variadic will enable simplification of policies which check for containment in more than one IP Address block. This maintains backwards compatibility, while simplifying policies that must verify a request's source IP against an allowlist of allowed CIDR blocks, improving policy readability, scalability, and maintainability.

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
  context.network.source_ip.isInRange(ip("198.51.100.0/24")) ||
  context.network.source_ip.isInRange(ip("203.0.113.0/24")) ||
  context.network.source_ip.isInRange(ip("192.0.2.0/25")) ||
  context.network.source_ip.isInRange(ip("2001:db8:a001::/48"))
};
```

The proposed change simplifies this logic into a single function call making the policy's intent clearer.

```
// Policy to allow access only from corporate IP ranges (proposed method)
permit (
  principal,
  action == Action::"accessAdminDashboard",
  resource
)
when {
  context.source_ip.isInRange(
    ip("198.51.100.0/24"),
    ip("203.0.113.0/24"),
    ip("192.0.2.0/25"),
    ip("2001:db8:a001::/48")
  )
};
```

And we can represent the variadic expression as follows 
```json
"conditions": [
    {
        "kind": "when",
        "body": {
            "isInRange": [
                {
                    ".": {
                        "left": {
                            "Var": "context"
                        },
                        "attr": "source_ip"
                    }
                },
                {
                    "ip": [
                        {
                            "Value": "198.51.100.0/24"
                        }
                    ]
                },
                {
                    "ip": [
                        {
                            "Value": "203.0.113.0/24"
                        }
                    ]
                },
                 {
                    "ip": [
                        {
                            "Value": "192.0.2.0/25"
                        }
                    ]
                },
                {
                    "ip": [
                        {
                            "Value": "2001:db8:a001::/48"
                        }
                    ]
                }
            ]
        }
    }
]
```

## Motivation
Making the `.isInRange` operator variadic is motivated by several key factors that align with Cedar's goals of expressiveness and readability.

### Smaller JSON Formatted Policies
The current method of chaining `.isInRange()` calls with `||` operators creates a large and object tree that can quickly exceeded the stack depth and recursion limit of systems. The use of a variadic operator would allow for the reduction in not only the policy objet's size, but also the overall tree depth (the origin of this RFC).

### Improved Policy Readability and Authoring
Cedar policies are designed to be easy to read and understand by both technical and non-technical stakeholders. Chaining `.isInRange()` calls with `||` operators creates syntactically complex expressions that obscure the simple intent of "is this IP in our allowlist?". As the list of IP ranges grows, the policy becomes increasingly unwieldy. The proposed operator replaces a complex boolean expression with a single, declarative function call, significantly improving the clarity and conciseness of the policy.

It should be explicitly documented that this operator performs an OR operation among the ranges provided, such that the provided IP address is in at least one of the listed ranges, not all of them.

## Detailed design

Implementing this RFC requires extending the parser, evaluator, typechecker, and symbolic compiler to allow `.isInRange` to take one or more arguments. Since `.isInRange` is an extension function, there is no need to change the AST, since the AST nodes for extension functions already take as input a list of arguments.

The evaluator should be modified so that it no longer forces `.isInRange` to have exactly one argument. Instead, the evaluator checks that at least one argument is provided and that all provided arguments are of type ipaddr. If not, the evaluation errors. Otherwise, the evaluator checks if the receiver IP address is in the range of any argument IP addresses.

The typechecker and symbolic compiler should be modified similarly to the evaluator.

Similar to other functions, the arguments should be eagerly evaluated. In the event that an error occurs, or one of the arguments passed to the function is not an IP address, the function call should produce an error.

## Drawbacks

* __Increased Language Surface Area:__ Any new feature adds to the complexity of the language. However, the proposed operator's logic is a minimal change, making it an intuitive and easily understood addition rather than a complex new concept.

* __Implementation Effort:__ This is a substantial feature that requires coordinated development effort across the cedar core repository (parser, validator, evaluator) and the cedar-spec repository for the formal model. This is a standard and expected cost for any significant language enhancement, similar to the effort required for features like the isEmpty operator.

## Alternatives

### The Status Quo (Chained `||`)
This is the current method for checking against multiple IP ranges. As detailed extensively in the Motivation section, this approach is not scalable and suffers from poor readability and maintainability, especially as the number of IP ranges grows. It is the problem this RFC aims to solve.

## Unresolved questions
Detailed Design requires input from someone more familiar with developing core Cedar functionality and SMT.
