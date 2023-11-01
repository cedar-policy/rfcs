# Unbounded Integers

## Related issues and PRs

- Reference Issues: (fill in existing related issues, if any)
- Implementation PR(s): Not implemented, but an implementation was started for benchmarking: https://github.com/cedar-policy/cedar/pull/376

## Timeline

- Started: 2023-11-01

## Summary

Currently, Cedar represents integers using Rust's `i64`. This RFC proposes changing the internal representation to unbounded integers using the `IBig` crate.

## Basic example

Currently, `1,000,000,000,000,000,000 * ({"a" : 1,000,000,000,000,000,000}.a)` will overflow and result in an error. If this RFC is accepted, it would instead evaluate to `1,000,000,000,000,000,000,000,000,000,000,000,000`.

## Motivation

Bounded integer semantics (either wrapping or erroring on overflow) are unintuitive [https://blog.research.google/2006/06/extra-extra-read-all-about-it-nearly.html]. Consider the following policy:

```
forbid(principal, action, resource) when {
   principal.elevated_privileges_end_time_s * 1000 > context.current_time_ms ||
   !principal.is_mfa
};
```

A casual reader of this policy may conclude that all actions are forbiden when `principal.mfa` is `false`. This is wrong. The lhs (`principal.elevated_privileges_end_time_s * 1000 > context.current_time_ms`) is evaluated first and if it errors the entire policy is skipped.

To avoid this class of mistakes, we want to change Cedar so that arithmetic never errors.

## Detailed design

We replace the internal representation of integers as `i64`s with an unbounded representation (see draft https://github.com/cedar-policy/cedar/pull/376 which is incomplete but was used for benchmarking). Cedar would also remove the limitation on integers recieved as inputs (both integer literals in policies and attributes recieved from JSON or directly constructed).

With these limits removed, Cedar could represent the result of e.g., `i64::MAX * i64::MAX` in the residual policies returned by partial evaluation.

## Drawbacks

### Performance:
Using `i64`s is obviously faster than using unbounded integers. We benchmarked several crates, and the fastest we tested (under our licensing restrictions which forbids (L)GPL) was `IBig`. We evaluated policies that should represent the worst-case runtime increase from the switch.

*Summary: In the worst case, we seem to be looking at 340μs vs 530μs for purely evaluation. This is a 56% increase, but negligible in an end-to-end system.*

For the worst-case effect on policy evaluation, we assume a 10k character limit and do addition / multiplication of the literal `i64::MAX` repeated up to this limit +/* `principal.a` where `principal.a == i64::MAX`. All benchmarks are run for 100 iterations:

```
IBig_addition
mean: 368.41585148514855μs
std_dev: 37.14383484933371μs
IBig_multiplication
mean: 528.5201386138613μs
std_dev: 27.376510998230426μs
i128_addition
mean: 341.99384158415853μs
std_dev: 28.056390901018368μs
i64_mult_by_1
mean: 327.4614752475248μs
std_dev: 28.18572847410058μs
```

Again, this is just evaluation. These differences are in the noise for end-to-end tests:

```
i128_10kchar_addition: 2.164s for 100 runs
IBig_10kchar_addition: 2.165s for 100 runs
```

So an avarage run takes `~21ms` and the runtime increases by `~200μs`.

### Applications Using Cedar Must Limit Input:
In this RFC, we propose lifting Cedar's limits on integers. This means applications using Cedar would have to enforce their own limits. We expect applications to sanitize any user inputs and this probably includes limiting the lengths of string inputs. We think reasonable length limits (e.g., AVP limits policies to 10k chars) will give acceptable performance, but we should test this more (see unresolved question 2).

### Taking new dependency:
If this RFC is accepted, Cedar would take a new dependency on `IBig`, increasing the attack surface.

## Alternatives

### Unbounded internal integers, bounded inputs
Applications will need to limit the integers input as attributes. Cedar could choose some default limit (e.g., `i64`). The current RFC doesn't impose a specific limit and relies on applications to sanitize any user inputs as appropriate.

The downside of choosing a default limit is that analysis could return counter examples that don't respect this limit. It is not clear how to fix this while keeping analysis complete and decidable.

It is probably sufficient to limit the length of the string passed as input, but this should be tested (see unresolved question 2).

### Wrapping integers
Arithmetic on integers that wrap on overflow is total, but it has caused bugs in the past and so is probably not ideal for an authorization language.

## Unresolved questions

- How efficient is (de)serializing `IBig`s?
- Benchmarking was done assuming inputs bounded by `[i64::MIN, i64::MAX]` and 10k character policies. How does relaxing these assumptions affect performance?