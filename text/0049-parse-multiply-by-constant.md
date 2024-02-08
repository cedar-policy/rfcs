# Refine the Parsing Rule of Multiply-By-Constant Operation

## Related issues and PRs

- Reference Issues: https://github.com/cedar-policy/cedar/issues/619
- Implementation PR(s): (leave this empty)

## Timeline

- Started: 2024-02-07

## Summary

This PR proposes that the parser checks validity of multiplication operations after left-associativity is explicitly applied on the CST level. And the order of resulting AST should be the same as that of CST.

## Basic example

`2*1*context.value` should be conceptually converted into `((2*1)*context.value)` before determining if it's a valid multiply-by-constant operation. And the resulting AST should be `(mul (mul 2 1) context.value)`.

## Motivation

Let's first revisit the status quo: The parser separates the operands of a CST representing a (possibly chained) multiplication operation into a non-integer-constant and a list of integer constants, preserving the order of the constants, and then *left-fold* the constant list with the non-constant. For instance, `2*1*content.value` is parsed into `(mul (mul content.value 2) 1)`.

Note that the parser changes the order of operands, which does not alter the evaluation result since Cedar's multiplication operation is associative. However, changing the evaluation order can make error message confusing: For instance, evaluating `2*6*context.value` when `context.value` is `i64::MAX/10` produces an error message like ```integer overflow while attempting to multiply `1844674407370955160` by `6```, contradicting the intuitive left-to-right evaluation order.

The parser's rule to determine if multiplication operations are valid is also confusing. For instance, `2*1*context.value` is valid whereas its variant `(2*1)*context.value` is not. The inconsistency further causes ambiguity in EST to AST conversion: ESTs of the aforementioned example are the same but only the former can be parsed to an AST.

## Detailed design

To resolve the issues, this PR proposes a design to explicitly apply Cedar's left-associativity rule on the CST level and determine validity afterwards. The CSTs, if deemed valid, should be converted to ASTs that have the same order. Note that there will be only two operands for the CST representation of a multiplication operation, as opposed to a list of operands per status quo.

The validity checking algorithm is simple: Count the non-constant-integer operands of a CST representing a multiplication operation recursively and error if it's greater than 1. An example algorithm is as follows.

```Rust
fn count_non_constant_operands(lhs, rhs) -> bool {
    match (lhs, rhs) {
        (cst::Mul(ll, lr), cst::Mul(rl, rr)) => count_non_constant_operands(ll, lr) + count_non_constant_operands(rl, rr),
        (cst::Mul(ll, lr), Lit(Int(_))) => count_non_constant_operands(ll, lr),
        (cst::Mul(ll, lr), _) => count_non_constant_operands(ll, lr) + 1,
        (Lit(Int(_)), cst::Mul(rl, rr)) => count_non_constant_operands(rl, rr),
        (_, cst::Mul(rl, rr)) => count_non_constant_operands(rl, rr) + 1,
        (Lit(Int(_)), Lit(Int(_))) => 0,
        (Lit(Int(_)), _) => 1,
        (_, Lit(Int(_))) => 1,
        (_, _) => 2,
    }
}
```

This recursive algorithm validates expressions derived from arbitrary operand associations of a chained multiplication operation. For instance, expressions `1*2*context*3`, `1*(2*context*3)`, and `1*(2*context)*3` are all accepted.

## Drawbacks

The major drawback of this approach is that it induces a breaking change.

## Alternatives

An alternative is to let the ESTs representing multiplication operations to a list of operands, just like what CSTs do.

## Unresolved questions
