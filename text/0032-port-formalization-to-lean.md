# Port Cedar formalization to Lean

## Related issues and PRs

- Implementation PR(s): [cedar-spec#138](https://github.com/cedar-policy/cedar-spec/pull/138)

## Timeline

- Started: 2023-10-12
- Accepted: 2023-10-24
- Landed: 2023-10-26 on `main`
- Released: The Dafny formalization was deprecated in `cedar-spec` v3.1.0 (released 2024-03-08)

Note: These statuses are based on [the first version of the RFC process](./../archive/process-v1/README.md).

## Summary

This RFC proposes to port our current Cedar models and proofs (written in [Dafny](https://dafny.org/)) to an alternative verification tool ([Lean](https://lean-lang.org/)) that is better suited for meta-theory proofs, like Cedar’s validation soundness proof.

**Note**: The changes proposed in this RFC do not impact the [`cedar-policy/cedar`](https://github.com/cedar-policy/cedar) repository or any of its associated Rust crates. The proposed changes are restricted to the formalization available in [`cedar-policy/cedar-spec`](https://github.com/cedar-policy/cedar-spec).

## Motivation

Following a [verification-guided development process](https://www.amazon.science/blog/how-we-built-cedar-with-automated-reasoning-and-differential-testing), we use proofs to gate the release of Cedar’s core components. To release a new version, the Rust implementation of each component is differentially tested against its Dafny model, which is formally verified against key security and correctness properties.

We chose Dafny for its balance of usability and ability to automatically prove basic security properties of Cedar's authorizer. But proving Cedar's meta-theoretic properties (such as validator soundness) is less suited for Dafny’s automation (e.g., see [_this issue_](https://github.com/cedar-policy/cedar-spec/issues/35) and associated PRs). For these proofs to be robust in terms of performance and maintenance, they need to be highly detailed, favoring the use of an [_interactive theorem prover_](https://en.wikipedia.org/wiki/Proof_assistant). We propose porting Cedar to Lean, an interactive theorem prover that is well suited for large-scale proofs about meta-theory.

## Detailed design

Cedar consists of three core components: (1) the evaluator, (2) authorizer, and (3) validator. The evaluator interprets Cedar policies, and the authorizer combines the results of evaluating multiple policies into an authorization decision. Cedar’s security theorems prove basic properties of the authorizer (e.g., deny overrides allow). The validator is a tool for working with Cedar policies. It type checks a policy against a schema. To assure correctness, we prove a validator soundness theorem which guarantees that if the validator accepts a policy, evaluating that policy on a valid input can never cause a type error.

All core components of Cedar are modeled in Dafny and have proofs.  There are ~6,000 lines of modeling code.  The proofs for the authorizer and evaluator are small:  the largest is ~200 LOC.  The validation soundness proof is ~2,000 LOC.

For each component, we plan to port the model first and start differentially testing it against the Rust implementation, and then port the proofs. The Dafny and Lean code will co-exist while we work on the port. Once the Lean validator proofs are complete, we will archive the Cedar Dafny folder.

We believe it is best to do the port now while our development is relatively small, and before we begin working on proving other meta-theoretic properties, like soundness of the partial evaluator (which is not yet modeled in Dafny).

## Drawbacks

We will need to support both Dafny and Lean proofs for a period of time, to ensure that Cedar remains sound and there are no gaps.


