# General multiplication in Cedar

## Related issues and PRs

- Reference Issues: related to [RFC 50]
- Implementation PR(s): [cedar#702]

## Timeline

- Started: 2024-03-07

## Summary

Allow multiplication of arbitrary expressions (that evaluate to Long), not just
multiplication of an expression by a constant.

## Basic example

```
permit(principal, action, resource) when {
    context.foo * principal.bar >= 100
};
```

## Motivation

Today, Cedar only supports multiplication of two operands if (at least) one
operand is a constant.
In the more general n-ary (chained) multiplication case, Cedar requires that at
most one operand is a non-constant, but allows the constants and non-constant to
appear in any order.

- This creates some confusion for Cedar users. No other popular programming
  language has this restriction on multiplication.
- This leads to bugs and confusing behavior. To enforce this restriction,
  Cedar's internal AST node for multiplication only supports multiplying an
  expression by a constant. But this requires the Cedar parser to re-associates
  (and re-order) operands in a chained multiplication, which leads to confusion
  and problems as described in [RFC 50].
- This limits the power of Cedar by preventing users from writing policies
  involving multiplication where neither operand is known at policy-authoring
  time.

This RFC proposes to relax all of these restrictions and allow multiplication
of arbitrary expressions (that evaluate to Long).
In other words, multiplication will be treated just like addition: `*` will be
valid in all positions and situations where `+` is valid today.

## Detailed design

This will actually simplify the evaluator code, validator code, and internal AST.
Multiplication will become an ordinary `BinaryOp`, and no longer need a special
AST node.
The evaluator and validator can handle multiplication in the same way as
addition and in the same code paths.

With this RFC, the policy parser becomes strictly more permissive:
All policies that currently parse will still parse, plus additional policies
that used to produce parse errors will now parse as well.
There are edge cases where evaluations that do not overflow today could result
in overflows after this RFC -- see Drawbacks below.

## Drawbacks

One motivation for the original restriction on multiplication was to make SMT
analysis of Cedar policies easier.
However, presuming that the SMT analysis uses bitvector theory to analyze
operations on Cedar Longs, multiplication by a general expression is not much
more expensive than multiplication by an arbitrary constant (ignoring special
cases such as 0 or constant powers of 2).
Some multiplication expressions will be expensive to analyze (computationally),
but that is already true for some other kinds of Cedar expressions that don't
involve multiplication.
In general, we'd prefer to use a linter to warn users about (these and other)
expensive expressions, rather than use restrictions on the Cedar language.

This RFC firmly closes the door on changing Cedar's default numeric type to
bignum. However, that door is already basically closed.
Also, we could still introduce bignums as an extension type (with their own
separate multiplication operation) in the future.

This RFC has essentially no interaction with any other currently pending or
active RFC, except for [RFC 50] which it replaces and makes obsolete.

There are edges cases where evaluations that do not overflow today could result
in overflows after this RFC.
One example is an expression `CONST * CONST * context.value` for large `CONST`
when `context.value == 0`.
Today's parser will produce the internal AST `(mul (mul context.value CONST) CONST)`
which will not overflow when `context.value == 0`, while this RFC would produce
the internal AST `(mul (mul CONST CONST) context.value)` which would overflow
even when `context.value == 0`.
This is because, like [RFC 50], this RFC proposes to left-associate
multiplication and not to reorder operands, in contrast to the current Cedar
parser.

This edge case seems very unlikely for users to hit (as it requires a
multiplication by two large constants), and this RFC's proposed behavior is
undoubtedly more intuitive, as multiplication is left-associative in most
programming languages.

## Alternatives

[RFC 50] is one alternative which fixes some issues with chained multiplication
without (significantly) relaxing Cedar's restrictions on multiplication
operations.
This RFC's proposal leads to simpler evaluation and validation code than RFC 50,
and also makes the Cedar language simpler and easier to understand for users.

[RFC 50]: https://github.com/cedar-policy/rfcs/pull/50
[cedar#702]: https://github.com/cedar-policy/cedar/pull/702
