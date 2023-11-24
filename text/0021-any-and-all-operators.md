# Add `all` and `any` operators

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started: 2023-07-14
- Entered FCP (intent to accept): 2023-10-27
- Accepted: 2023-11-08
- Landed:

## Summary

This RFC proposes extending the language with `all` and `any` operators that allow checking if all elements or any element in a set satisfies a given predicate. The `all` operator returns `true` if the provided predicate is true for all elements in the set. The `any` operator returns true if the predicate is true for any element in the set.

## Basic example

Consider writing a policy that allows access when all port numbers in the `context` are between 8000 and 8999.  This can't be expressed in Cedar today.

With the `all` operator, we can write this policy as follows:

```
permit(principal, action, resource)
when {
  context.portNumbers.all(it >= 8000 && it <= 8999)
};
```

The same policy can be written using the `any` operator instead:

```
permit(principal, action, resource)
unless {
  context.portNumbers.any(it < 8000 || it > 8999)
};
```

The two operators behave analogously (though [not equivalently](#extending-the-semantics)) to `&&` and `||`. Given negation, each can be written in terms of the other. We include both for ergonomics.

## Motivation

The `all` and `any` operators support a common use case: iterating over a set and checking if a predicate holds for any or all members of the set.

Cedar currently lacks a general way to express this use case. The only alternative is to expand the `all` or `any` checks into conjunctions or disjunctions. For example:

```
// Using all
["a", "ab", "abc"].all(it like "a*")

// Using &&
("a" like "a*") &&
("ab" like "a*") &&
("abc" like "a*")
```

This manual expansion works for literal sets but cannot be applied to non-literal sets like `context.portNumbers`.

The new operators provide a built-in way to concisely express these universal and existential quantifications over a set.

## Detailed design

The Cedar syntax, semantics, and type system are all extended to support the new operators. These extensions are backward compatible, and existing policies won't be affected. In particular, we will keep the `.containsAny` and `.containsAll` operators on sets, even though they can be expressed in terms of `any` and `all`.

### Extending the syntax

This RFC proposes extending the Cedar grammar as follows:

```
Access    :=
  '.' QUANTIFIER '(' Predicate ')'
  | '.' IDENT ['(' [ExprList] ')']
  | '[' STR ']'
QUANTIFIER := 'all' | 'any'
Predicate  := ...
```

The `Predicate` expression differs from `Expr` in two ways:

1. Predicates can use the keyword `it`. A `Predicate` defines the body of function with a single parameter, and we use `it` as the parameter name. This is similar to [Kotlin's `it` keyword](https://kotlinlang.org/docs/lambdas.html#it-implicit-name-of-a-single-parameter).

2. Predicates cannot contain nested `any` or `all` expressions. We disallow nested quantifiers for both performance and analyzability reasons. Nested quantifiers allow writing expressions that run in $O(2^n)$ time, where $n$ is the number of nested quantifiers. For example:

```
[0,1].all(
  [0,1].all(
    ...
      [0,1].all(true)...))
```

Because nested quantifiers are prohibited, there is no need to support predicates with arbitrary parameter names. The `it` keyword sufficiently extends the grammar.

### Extending the semantics

The semantics of `all` and `any` are straightforward when there are no errors:
- `E.all(P)` evaluates to true when `P[e/it]` is true for every element `e` in `E`.
- `E.any(P)` evaluates to true when `P[e/it]` is true for some element `e` in `E`.

But what happens if evaluating `P` errors on some element `e`? In this case, the evaluation of `all` or `any` terminates abruptly with a distinguished `QuantifierError`.

The `QuantifierError` error may include additional diagnostic information, as long as this information is bounded in size and computed deterministically. For example, the `QuantifierError` error could specify the source location, or a fixed-length description of the smallest erroring value in the underlying set, according to some fixed total order on Cedar values. This error handling approach ensures that evaluating  `all` and `any` _deterministic_: the result is the same regardless of iteration order. It also ensures that evaluation is _space efficient_: the size of the evaluator output remains constant in policy and input size.

For example, consider the expression `[1, true].all(it like "foo")`. Regardless of the order in which the predicate is applied, the expression returns the same `QuantifierError`.

Compare this to the [alternative semantics](#non-deterministic-error-behavior) that just propagates the error discovered, when it is discovered. Then evaluating this expression could lead to the error that "a Long was found where a String was expected" or it could lead to the error "A Boolean was found where a String was expected." Which one depends on evaluation order, but no clear order exists because set elements are specifically unordered.

The proposed semantics lets us think about `all` and `any` in terms of their expansion to conjunctions and disjunctions. The quantified expression errors if _any_ expansion would error.

For example:
```
// Throws QuantifierError
[1, true].all(it like "foo")

// Throws a TypeError: "like" can't be applied to an integer
1 like "foo" && true like "foo"

// Throws a TypeError: "like" can't be applied to an boolean
true like "foo" && 1 like "foo"
```

The only difference is the error being thrown: `QuantifierError` for the quantified expression versus an element-specific error for the explicit expansion.

### Extending the type system

The type system needs to be extended with rules for type checking quantified expressions `E.all(P)` and `E.any(P)`. This should be fairly standard: we know the type of `it` from the type of the set `E`, and we can use this to typecheck the predicate `P`. We also need to propagate effects through predicates.

For example, the following should typecheck when `context.limit` is an optional integer attribute, and `resource.things` is a set of entities with an optional integer attribute `.size`:

```
context has limit &&
resource.things.all(
  it has size && it.size < context.limit
)
```

While the effect prior to a `any` or `all` is clear, what about the effect after one? The recommended solution is the simplest one: ignore the effects of `any` and `all` . But we could be more precise if needed.

For example, consider the following expression:

```
resource.things.all(context has limit && it.has size && it.size < context.limit) &&
context.limit > 5
```

Here, the redundant use of `context.limit` in the `all` could carry an effect outside to the `>` expression.

This extra precision isn't necessary in the sense that we can always rewrite expressions to avoid relying on it. For example, we can rewrite the above expression as follows:

```
context has limit &&
resource.things.all(it has size && it.size < context.limit) &&
context.limit > 5
```



## Drawbacks

- This proposal requires significant development effort. We'll need to modify the parser, the CST to AST conversion, CST/AST/EST, evaluator, validator, models, proofs, and DRT.
- The `any` and `all` operators may encourage writing complex expressions with poor performance. For example, `context.portNumbers.any(it == 8010)` is $O(n)$ versus $O(1)$ for `context.portNumbers.contains(8010)`.
- Supporting these operators will likely have a negative impact on analysis performance, especially for complex predicates.

## Alternatives

We considered two alternative semantics for these operators.

### Non-deterministic error behavior

Given `E.any(P)` or `E.all(P)`, we apply `P` to elements of `E` in arbitrary order, terminating on the first error and returning that error as the result. This alternative provides more precise error messages than the proposed approach.

But the downside is that the same policy could produce different errors depending on iteration order. For example, `[1, true].all(it like "foo")` may result in a type error that says `like` cannot be applied to an integer or a boolean. In other words, Cedar semantics would become non-determinstic.

We decided against this semantics for three reasons:
* Violates Cedar's design as a deterministic language. Error non-determinism would be visible to `is_authorized` callers.
* Applications may also become non-deterministic if they examine errors and act on them.
* Non-determinism complicates models and proofs.

Keeping deterministic semantics is important for Cedar as an authorization language.

### Treating errors as `false`

Given `E.any(P)` or `E.all(P)`, we apply `P` to elements of `E` in any order, treating errors as false and continuing evaluation on the remaining elements. Note that this is how `is_authorized` handles policy evaluation errors: they are turned into false and ignored.

With this approach, `any` and `all` become total functions: they never error. For example, `["one", 1].any(it < 2)` evaluates to true because there is one element for which the predicate holds. And `["one", 1].all(it < 2)` is simply false, because `"one" < 2` is treated as false.

The key advantage of this semantics is that it is more amenable to SMT-based analysis than either of the above alternatives.  Both  error-propagating alternatives need more complex and larger encodings.

We decided against this semantics because it breaks the interpretation of `all` and `any` as shorthands for conjunctions and disjunctions. If we expand `["one", true].all(it < 2)` to a conjunction, the result always errors rather than evaluating to false. This discrepancy between the quantified and expanded forms might be confusing and undesirable.
