# `uint256` extension

## Related issues and PRs

- Reference Issues: [cedar#494](https://github.com/cedar-policy/cedar/issues/494), [cedar#495](https://github.com/cedar-policy/cedar/pull/495), [cedar#63](https://github.com/cedar-policy/cedar/issues/63), [rfcs#36](https://github.com/cedar-policy/rfcs/pull/36), [rfcs#39](https://github.com/cedar-policy/rfcs/pull/39), [RFC 0021](https://github.com/cedar-policy/rfcs/blob/main/archive/rfc/0021-any-and-all-operators.md), [RFC 0057](https://github.com/cedar-policy/rfcs/blob/main/text/0057-general-multiplication.md), [RFC 0076](https://github.com/cedar-policy/rfcs/blob/main/text/0076-entity-slice-validation.md), [RFC 0080](https://github.com/cedar-policy/rfcs/blob/main/text/0080-datetime-extension.md)
- Implementation PR(s):

## Timeline

- Started: 2026-08-25
- Accepted: TBD
- Stabilized: TBD

## Summary

Cedar currently supports extension functions for IP addresses, decimal values, and dates and times.
This RFC proposes one more: `uint256`, an **unsigned 256-bit integer** — the width and signedness of the Ethereum Virtual Machine (EVM) word, and of every amount field in the ERC-20, ERC-721, ERC-1155 and ERC-4626 token standards.

The type is deliberately minimal. It has a single string constructor and exactly six operators: `==`, `!=`, `<`, `<=`, `>`, `>=`. **It has no arithmetic** — no addition, subtraction, multiplication, division or remainder — which matches the *capability* surface Cedar's existing `decimal` extension already ships: a constructor plus four comparisons and nothing else. (`decimal` spells its comparisons as methods rather than operators; `Detailed design` explains why `uint256` follows RFC 0080 and uses operators instead.) Cedar's `long` type is not changed in any way, and no existing policy, schema, or entity file needs to change: like `ipaddr`, `decimal`, and `datetime`, `uint256` would live behind a feature flag.

We want anything added to Cedar to be modelable in Lean and to preserve Cedar's decidable SMT-based analysis. Comparison-only reasoning over a fixed-width bitvector is the cheapest wide-integer shape we could find on both counts, and the `Detailed design` section gives measured numbers, with their limits stated, rather than an assurance.

## Basic example

An application authorizing blockchain transactions wants to require a second approver for any transfer of 10 ether or more. Ethereum denominates transaction values in wei, where 1 ether is 10<sup>18</sup> wei, so the threshold is 10<sup>19</sup> — larger than `long` can hold. With `uint256`:

```cedar
forbid (
  principal,
  action == Action::"signTransaction",
  resource
)
unless {
  context.value < uint256("10000000000000000000") ||   // 10 ETH in wei
  (context has approvals && context.approvals >= 2)
};
```

## Motivation

### Cedar cannot express a 10 ETH transfer

Cedar's `long` is a signed 64-bit integer (`cedar-policy-core/src/ast/integer.rs`: `pub type Integer = i64;`), and Ethereum counts value in wei, at 10<sup>18</sup> wei to the ether. So the largest amount a policy can name is `i64::MAX` wei, which is 9.223372036854775807 ETH. A policy about a 10 ETH transfer cannot be written: both the threshold literal and the context value it would compare against are unrepresentable.

The same ceiling hits every token with 18 decimal places, the de facto ERC-20 default — DAI, WETH, SHIB, UNI, and LINK all declare 18. Any balance above ~9.22 whole tokens overflows `long` in base units, and real supplies run far past that: on mainnet DAI holds ~4.6×10<sup>27</sup> base units and SHIB ~1.0×10<sup>33</sup>.

The gap is not Ethereum's alone. 256 bits is the width of the EVM machine word, so every EVM-compatible chain, and every 18-decimal token deployed on one, carries the same `uint256` amount fields and hits the same ceiling.

It is not even EVM-only. Canton's token standard, CIP-0056, types every token amount as Daml's `Decimal`: "38-digit fixed-point decimals with 28 digits before and 10 digits after the decimal point," one uniform scale for all tokens. So a Canton amount reaches 10<sup>28</sup> whole units — past `long`'s 9.2×10<sup>18</sup>, and about thirteen orders of magnitude past what Cedar's `decimal` can hold, which cannot carry the 10 fractional digits either. In base units at the standard's fixed scale it is an integer below 10<sup>38</sup>, well inside 2<sup>256</sup> — for the non-negative holdings and transfer amounts this type is for; `Decimal` is signed, and a Canton value that can go negative wants the `int256` named under *Forward compatibility*. Two unrelated ecosystems, the same conclusion: the amounts are integers, and 64 bits is not enough.

(Chains whose amounts are natively 64-bit — Bitcoin's `typedef int64_t CAmount`, Cardano's lovelace, Solana's `u64` lamports — fit in `long` today and are not part of this ask.)

### `decimal` does not help

The obvious first answer is Cedar's `decimal` extension. It does not work. `decimal` is a signed 64-bit integer scaled by 10<sup>4</sup> (`cedar-policy-core/src/extensions/decimal.rs`: `const NUM_DIGITS: u32 = 4;` over `value: i64`), documented as ranging from -922337203685477.5808 to 922337203685477.5807. It buys **no additional magnitude** over `long` — it is backed by the same i64 — and spends four digits on a fraction, dropping the whole-number ceiling to about 9.2×10<sup>14</sup>. Its smallest non-zero value, 0.0001, is 10<sup>14</sup> wei. It cannot represent one wei, or one gwei.

That is why this RFC asks for an integer. On-chain amounts are exact integers in base units; a fixed-point re-encoding is a lossy rewrite of something already integral.

### The same request has already been made publicly, by someone else

We are not the first to ask. [cedar#494](https://github.com/cedar-policy/cedar/issues/494), filed 2023-12-12, quotes a request made in the public Cedar community Slack on 2023-12-07 by a third party working in the same domain:

> I’m working on an authorization system around blockchain transactions; I believe current data types can’t support bigint operations, any idea how that could be supported easily? Any reason we couldn’t add an extension type like decimal to add Big Integer type/operations?

Independently, and 2.7 years before this RFC, that person proposed the same mechanism this RFC proposes: an extension type modelled on `decimal`. Two people met the same wall and arrived at the same design, which is the best signal we have that the shape is right.

### Why the workarounds are not good enough

Three workarounds exist today; each fails, and the third fails in the way Cedar exists to prevent.

1. **Split the value across several `long`s.** A 256-bit value becomes four 64-bit limbs, and `a < b` becomes a hand-written lexicographic chain over four attribute pairs, with signedness traps in every limb (a limb with its top bit set is negative as a `long`). Reviewers cannot audit this, and a single mis-ordered clause changes the decision.
2. **Carry the value as a `String`.** Equality works; `<` is not defined for strings, so the ordering every motivating policy needs cannot be written at all.
3. **Precompute the comparison in the application and pass a boolean in `context`.** This works, but it moves the authorization decision out of the policy and into the calling application. RFC 0080 made the same argument about precomputed time comparisons — it "makes authorization logic difficult to audit because it moves this logic outside of Cedar policies and into the calling application." A threshold that lives in application code is a threshold that cannot be reviewed, versioned, or varied per tenant as a policy.

## Detailed design

### Constructing `uint256` values

The `uint256(string)` function constructs a value from a string. Strict validation requires the argument to be a string literal, although evaluation and authorization accept any appropriately-typed expression — the same rule Cedar applies to every existing extension constructor.

Two input forms are accepted:

- **Decimal**: one or more ASCII digits, `^[0-9]+$`. No sign, no separators, no leading `+`, no decimal point, no exponent.
- **Hexadecimal**: `0x` (lowercase `x`) followed by one or more hex digits, `^0x[0-9a-fA-F]+$`. Hex is accepted because EVM tooling and JSON-RPC quote `uint256` fields as `0x`-prefixed hex, and requiring integrators to re-encode them invites exactly the transcription errors this type exists to prevent.

The value must lie in `[0, 2<sup>256</sup>−1]`. Examples:

| Expression | Result |
|---|---|
| `uint256("0")` | 0 |
| `uint256("10000000000000000000")` | 10<sup>19</sup> (10 ETH in wei) |
| `uint256("115792089237316195423570985008687907853269984665640564039457584007913129639935")` | 2<sup>256</sup>−1 |
| `uint256("0x8ac7230489e80000")` | 10<sup>19</sup> |
| `uint256("0x")` | error — no digits |
| `uint256("115792089237316195423570985008687907853269984665640564039457584007913129639936")` | error — out of range (2<sup>256</sup>) |
| `uint256("-1")` | error — negative, see *Invalid input* below |
| `uint256("1.0")`, `uint256("1e18")`, `uint256("1_000")`, `uint256(" 1")` | error — malformed |

Leading zeros are accepted on input, in both forms (`uint256("007")` is 7, and `uint256("0x000...0a")` is 10), because JSON-RPC frequently zero-pads hex values to 32 bytes.

#### Canonical representation

`uint256` is represented internally as a 256-bit unsigned integer, and the constructor normalizes: the internal value depends only on the mathematical number, not on which of the accepted spellings produced it. So `uint256("10") == uint256("0x0a")` and `uint256("007") == uint256("7")` are both `true`, and equality needs no discipline from whoever produces the context. This matches `decimal`, which canonicalizes `decimal("1.0")` to the same value as `decimal("1.0000")`, and RFC 0080's `datetime`, whose "Equality is based on the underlying representation."

`toString()`-style formatting is not proposed; there is no operator or method that produces a `String` from a `uint256`.

#### Invalid input is rejected, never reinterpreted

Negative and out-of-range inputs are **errors**: no wrapping, saturating, truncating, or reinterpreting two's-complement bits as unsigned. This holds in the constructor and in the JSON forms alike. A string literal fails at validation time, because Cedar's validator evaluates single-argument extension constructors on their literals (`cedar-policy-core/src/validator/extensions/decimal.rs`, `validate_decimal_string`); a context or entity value fails when that JSON is parsed.

### Operators

`uint256` participates in Cedar's existing per-type operator overloading rather than registering named comparison methods. Concretely, its extension value answers `true` to `supports_operator_overloading()` (`cedar-policy-core/src/ast/extension.rs`), which is how `datetime` and `duration` already get their comparisons through the generic dispatch in `cedar-policy-core/src/evaluator.rs`. Both operands must be `uint256`; nothing else compares against one, as *No mixed comparisons* below spells out. For `U1`, `U2` of type `uint256`:

- `U1 == U2` is `true` when the two values are the same number
- `U1 != U2` is `true` when they are not
- `U1 < U2` is `true` when `U1` is strictly less than `U2`
- `U1 <= U2` is `true` when `U1` is less than or equal to `U2`
- `U1 > U2` is `true` when `U1` is strictly greater than `U2`
- `U1 >= U2` is `true` when `U1` is greater than or equal to `U2`

Only three of those six need new dispatch. Cedar's AST carries just `Eq`, `Less` and `LessEq` (`cedar-policy-core/src/ast/ops.rs`), and the other three are existing sugar: `e1 != e2` is built as `!(e1 == e2)`, `e1 > e2` as `!(e1 <= e2)`, and `e1 >= e2` as `!(e1 < e2)`. That is why the encoder below emits only three SMT operators, and why `int256` would need only `bvslt` and `bvsle`.

Note this is deliberately *not* `decimal`'s design. `decimal` answers `false` to the same hook and instead registers `lessThan`, `lessThanOrEqual`, `greaterThan`, `greaterThanOrEqual` as methods. RFC 0080 deliberately reversed that convention for `datetime` and `duration`, accepting "some implementation complexity" because "it will make policies that use these operations easier to read and easier to write." We follow 0080, not `decimal`. The `decimal` precedent we do claim is its **operator surface** — constructor plus four comparisons and no arithmetic at all — not its syntax.

**No arithmetic, and no division.** `+`, `-`, `*`, `/`, `%` and unary negation are not defined for `uint256`, at any width, in this RFC. The analysis measurements below are the reason, and `Alternatives` explains why arithmetic is not simply deferred paperwork.

Two things make that less of a compromise than it sounds. Cedar's own `decimal` extension has **zero** arithmetic — its registered function set is the constructor plus exactly four comparisons — so this is a second instance of an accepted pattern rather than a novelty. And it is also the mainstream design outside Cedar. We surveyed nine production policy systems that authorize over blockchain transaction context, and **not one of them gives the policy author arithmetic on token amounts**; where arithmetic exists it is either general-purpose contract code or engine-internal accumulation against an author-supplied literal. One of them, Turnkey, documents its policy-language `uint` as a 256-bit unsigned type and ships a grammar with exactly four operation categories — logical, comparison, access, function — and no arithmetic operators at all. A 256-bit unsigned integer with comparison-only semantics is deployed and in production use today; it is not a hypothetical shape.

The related design question — how to bound a transfer's *fiat* value, which is the one requirement that would force wide multiplication — has the same industry answer: every surveyed system that supports fiat limits has the platform convert before evaluation and exposes a pre-converted field for the policy to compare. None exposes a rate to the policy. We recommend that pattern for Cedar too, and it is why arithmetic is not needed to make this type useful.

**No mixed comparisons: `uint256` orders against `uint256` and nothing else.** Not `long`, not `decimal`, not `datetime` or `duration`, not `String`. Where `context.value` is a `uint256`, both `context.value < 10` and `context.value < decimal("1.0")` are errors, and strict validation rejects them outright.

Nothing new is being proposed to get that; it falls out of the evaluator as it stands. An overloaded comparison requires *both* operands to be extension values that opt into operator overloading and carry the **same** typename (`cedar-policy-core/src/evaluator.rs`), so no two different extension types are ever ordered against each other — and `decimal` does not opt in at all, returning `false` from `supports_operator_overloading()` (`cedar-policy-core/src/extensions/decimal.rs`), so its values have no `<` even among themselves. A `Long` compared against a non-`Long` is already a type error.

**Strict validation rejects a mixed `==` too.** This is the case that matters in practice, and it is worth stating plainly because Cedar's evaluator alone would not stop it: `Eq` is total, so at evaluation time `context.value == 10` returns `false` rather than erroring. Strict validation does not let such a policy through. A `uint256` and a `long` have no least upper bound, so the validator reports the two operands as incompatible types (`cedar-policy-core/src/validator/typecheck.rs`, `enforce_strict_equality`). A validated policy therefore cannot mix the two types under `==` any more than under `<`; the silent-`false` behavior is reachable only in a policy that was never strictly validated.

We do not propose implicit widening of `long` to `uint256`, and no explicit conversion function is part of this RFC (see `Unresolved questions`).

### JSON encoding

The argument is always a **string**, in all three positions, following the precedents set by the IP address and decimal extensions.

In entity and context JSON, using the `__extn` escape:

```json
{
  "value": { "__extn": { "fn": "uint256", "arg": "10000000000000000000" } }
}
```

In a schema:

```json
{ "type": "Extension", "name": "uint256" }
```

In the JSON (EST) representation of a policy:

```json
{ "uint256": [ { "Value": "10000000000000000000" } ] }
```

Because `uint256` has exactly one single-argument constructor, Cedar's existing implicit-constructor path applies: where a schema declares the attribute as the `uint256` extension type, the `__extn` escape may be omitted and `"value": "10000000000000000000"` parses. Every representable value round-trips.

**Why a string and not a JSON number.** Two independent reasons, both concrete. First, Cedar maps bare JSON integers straight to `Long`: `cedar-policy-core/src/entities/json/value.rs` carries the comment "JSON int => Cedar long (64-bit signed integer)" over a `Long(i64)` variant, with no big-number path, so a JSON number is not a place a 256-bit value can be put. Second, JSON numbers are unsafe for this range in the wider ecosystem: many JSON clients — JavaScript and `jq` among them — parse numbers into IEEE-754 doubles, which represent integers exactly only up to 2<sup>53</sup>. CosmWasm hit the same problem and reached the same conclusion; its [`Uint256`](https://github.com/CosmWasm/cosmwasm/blob/160f8c533bed8bbc0749e7ff84d19f8ac87553b7/packages/std/src/math/uint256.rs#L27-L29) type is documented as "An implementation of u256 that is using strings for JSON encoding/decoding, such that the full u256 range can be used for clients that convert JSON numbers to floats, like JavaScript and jq." A string-constructed extension type also never crosses Cedar's own JSON-number boundary — see the measurement in `Alternatives`.

### Symbolic compilation

We take this to be the section that decides the RFC. Being *encodable* in Cedar's SMT-based analysis is a hard requirement: [RFC 0021](https://github.com/cedar-policy/rfcs/blob/main/archive/rfc/0021-any-and-all-operators.md) was accepted in 2023 and then rejected in 2024 because "even the revised version is not analyzable as described below, and further restrictions would be needed to make it analyzable." Analysis *cost* is a different matter, and [RFC 0057](https://github.com/cedar-policy/rfcs/blob/main/text/0057-general-multiplication.md) has already set the project's position on it: "Some multiplication expressions will be expensive to analyze (computationally), but that is already true for some other kinds of Cedar expressions that don't involve multiplication. In general, we'd prefer to use a linter to warn users about (these and other) expensive expressions, rather than use restrictions on the Cedar language." We are not asking for an exception to that; we are noting that a comparison-only type stays cheap without needing a linter to protect it. So rather than assert that this design is cheap to analyze, we measured it, and we state the bounds of what we measured.

`uint256` compiles to a fixed-width SMT bitvector, in the same way Cedar's existing extension types do. `cedar-policy-symcc` already emits SMT-LIB datatype declarations such as `(Decimal (decimalVal (_ BitVec 64)))` and, for IPv6, `(V6 (addrV6 (_ BitVec 128)) (prefixV6 (Option (_ BitVec 7))))`; `uint256` adds `(Uint256 (uint256Val (_ BitVec 256)))`. The bitvector width is already a parameter (`TermType::Bitvec { n }`), and a 128-bit `Width` constant already exists in `symcc/type_abbrevs.rs`, so 256 is one doubling past a width the encoder already ships — but see `Drawbacks`, because it is emphatically not a free change.

Because the type has no arithmetic, the only operators the encoder must emit are `bvult`, `bvule` and `=` (the unsigned counterparts of the `bvslt`/`bvsle`/`=` that Cedar already emits for comparison-only `long` policies — we captured its emitted SMT-LIB to confirm that is all a threshold policy produces).

**What we measured.** cvc5 1.3.4, single core, on structurally identical formulas differing only in the operand term, proving an operand bound over *k* independent constraints:

| operand | 64-bit | 256-bit |
|---|---|---|
| comparison only, *k*=32 | 0.028 s | 0.124 s |
| comparison only, *k*=128 | 0.130 s | 0.680 s |
| comparison only, *k*=512 | 1.18 s | 4.83 s |
| with `bvmul`, *k*=32 | 2.58 s | 49.2 s |

At *k*=32 the multiplying formula costs **395× the comparison-only formula at 256 bits**, versus 92× at 64 bits: the arithmetic penalty gets *worse* as the integer widens. At *k*=32, widening 64→256 bits costs comparison-only 4.5× and multiplication 19.1× (across the three clause counts the comparison-only ratio ranges 4.1×–5.2×). Ratios are computed from the unrounded medians, so they differ slightly from dividing the table's rounded cells. End to end, a real comparison-only wei-threshold policy compiled by `cedar-policy-symcc` and checked for equivalence cost 1.89 ms at 128 bits against 1.78 ms at 64 bits, with no query in that load-matched experiment exceeding 8.6 ms.

**Three honest bounds on those numbers**, because each of them is a claim a reviewer could otherwise falsify:

1. *Comparison-only wide integers are cheap* is **not** true without a width bound. Pushing comparison-only formulas further, cvc5 took 100.7 s at 2048 bits × 512 clauses and **timed out past 120 s at 4096 bits × 512 clauses**. The defensible claim is the bounded one: at 256 bits, comparison-only stayed under 5 s at every clause count we tested, and under 1.1 s at 128 clauses across every formula shape we tested (0.68 s on the operand-bound shape the table above reports). That is a property of 256 bits at realistic policy sizes, not of wide integers in general — which is a reason to fix the width at 256 rather than parameterize it.
2. *Arithmetic on wide integers is always expensive* is also false. On a policy-equivalence shape that cvc5's preprocessor closes by rewriting, multiplication finished in ~0.005 s at every width we ran it at — 64, 128 and 256 bits — never reaching the bit-blaster; comparison on that same shape stays at ~0.005–0.02 s out to 4096 bits. The claim we make is the asymmetric one: arithmetic on wide integers *can* be very expensive and comparison, at this width, is not.
3. *The analysis can ignore the arithmetic when the property only depends on ordering* is false too, and we checked. On a transitivity refutation — unsatisfiable without ever looking inside the operand terms — `bvmul` operands still cost 43.3 s at 256 bits. This is the strongest argument for excluding arithmetic from the type rather than adding it and expecting the solver to skip it.

Cells above 10 s are single samples; the *k*=512 cells are 3-sample medians rather than 5, and the 2048-bit and 4096-bit results we cite are single samples. All measurements are cvc5 1.3.4 specific; we did not run z3. The end-to-end figure above is a **128-bit** measurement of a widened `long`, not of the type this RFC proposes: we got it by locally patching symcc's `long` encoding to 128 bits, including fixing the two `From<i128>` trait-bound errors noted in `Alternatives`. It is offered only as a shape check on realistic policy sizes, not as a measurement of the design; we did not build a 256-bit end-to-end case, so the solver microbenchmark is the only 256-bit evidence here. A minimal harness that regenerates the formulas behind this table and times cvc5 on them is included alongside this RFC ([`0117/bench.py`](./0117/bench.py), with [`0117/README.md`](./0117/README.md)); the full corpus — all four formula shapes, the 2048/4096-bit sweep, the raw `.smt2` inputs, command lines and machine details — is available on request.

### Out of scope

Each exclusion below is a case we looked at and are deliberately not proposing, so that the type this RFC asks for is one we can defend rather than one that nearly covers everything.

- **Signed values.** `uint256` cannot hold them, and they are real: Uniswap V3 and V4 use `int256` swap deltas (in a 60-block sample of one major pool, 48 of 48 swaps had exactly one side negative) and `int24` ticks (negative in 4 of 8 major pools we read, because the sign follows token ordering rather than market conditions); PancakeSwap V3 is a verbatim fork and inherits both; Compound V3 stores an `int104` principal whose negative case *is* the borrow balance; Cardano encodes a burn as a negative `mint` quantity; Chainlink's `AggregatorV3Interface` returns an `int256 answer`, and Chainlink's own registry declares thousands of stream value fields as `int192`. A Cedar `int256` is named as future work below.
- **Signed 256 instead of unsigned 256.** Ruled out by evidence rather than taste. A signed 256-bit integer misses the entire top half of `uint256` — exactly 2<sup>255</sup> values — including 2<sup>256</sup>−1, which OpenZeppelin's `ERC20` special-cases as the infinite-allowance sentinel in `_spendAllowance` and which wallets and dapps commonly set. A Cedar policy over `int256` could not name the most common allowance value on Ethereum. Unsigned 256 is not a compromise here; for the token standards it is strictly better.
- **Fractional types.** `uint256` holds whole numbers only, so it cannot represent Borsh/Anchor `f32`/`f64`. A fractional value *can* be carried as an integer, but only if the producer and the policy agree on one scale: at scale 10<sup>2</sup>, 1.25 is the integer 125. Canton is the case where that agreement already exists — CIP-0056 fixes the scale at 10 digits for every token, so a Canton amount simply *is* an integer count of base units — which is why Canton appears in `Motivation` rather than here.
- **Arbitrary precision.** Cardano's Plutus Core `integer` denotes ℤ — its only bounds are economic, not type-level — so no fixed width covers a Cardano contract call. That is a different RFC with a different analysis story, and `Alternatives` gives our verdict on it.

### Forward compatibility

`uint256` is proposed as the first of a possible family, not as a claim that one width and one signedness are all Cedar will ever want. If it is accepted, the natural next request is **`int256`**, a signed 256-bit integer for the swap deltas, ticks, principals, and oracle answers listed above; together the two cover the Solidity ABI's integer union. We would expect `int256` to reuse this design verbatim — string constructor, canonical representation, six operators, no arithmetic — differing only in the accepted sign and the encoder's choice of `bvslt`/`bvsle`. Nothing in this RFC should be read as foreclosing that, and the naming (`uint256`, not `bigint` or `wide`) is chosen so the second type has an obvious name.

### Feature flag

`uint256` ships behind a **non-default** `uint256` feature flag, in the same one-feature-per-extension style `ipaddr`, `decimal`, and `datetime` use, so it is opt-in while it is unstable. Stabilization means joining those three in the `default` feature set — they are all in `default` today — which is the path `datetime` followed: experimental under its own flag in 4.3.0, then stabilized into `default`.

## Drawbacks

**Implementation cost is real and we should not undersell it.** Cedar's symbolic compiler dispatches extension types by basename — an unrecognized name returns "unsupported extension {name}" from `symcc/term_type.rs` — so a new extension type is *invisible to symbolic analysis* until symcc is taught about it. Teaching it means threading a new `ExtType` through roughly a dozen files across **two** compilers — `symcc/term_type.rs`, `symcc/term.rs`, `symcc/op.rs`, `symcc/ext.rs`, `symcc/extfun.rs`, `symcc/encoder.rs`, `symcc/decoder.rs`, `symcc/factory.rs`, `symcc/interpretation.rs`, `symcc/compiler.rs`, a new `symcc/extension_types/uint256.rs`, and the duplicated `symccopt/compiler.rs` — because `decimal`'s comparisons are registered once per compiler. Seventeen files under `cedar-policy-symcc/src` mention `decimal` or `Decimal` today, which is the honest scale of the precedent. That work is mechanical and fully precedented, but it is not small.

The Lean model is the harder half. `decimal` is a type-def over `Int64` in the Lean formalization, and `datetime`/`duration` are 64-bit too; there is no off-the-shelf 256-bit primitive to alias, so the model, its proofs, and the differential test generators all need real work rather than a rename. This RFC would also touch the validator, schema parsing, JSON entity parsing, the formatter, and every non-Rust implementation of Cedar — and a 256-bit type obliges those implementations to acquire a wide-integer dependency, which is free in some languages (Java `BigInteger`, JavaScript `BigInt`, Python `int`, Rust via a crate) and not in others. **We are offering to do this work**, including the symcc encoding and the Lean model, and to attach the benchmark artifacts behind the measurements above.

**Analysis cost.** Comparison-only 256-bit bitvectors are cheap at realistic policy sizes and measurably not cheap at absurd ones; the numbers and their bounds are in `Detailed design`, and the shape of the risk is that cost grows *superlinearly* in clause count (16× the clauses cost 39× the time at 256 bits) and superlinearly in width past 256 bits (8× the width cost 21× the time at 512 clauses), with no plateau. Fixing the width at 256 rather than making it configurable is a deliberate response to that.

**Integration with existing and planned features.** The interaction surface is small by construction. Because `uint256` has no arithmetic, it does not interact with RFC 0057's general multiplication, and it does not touch the overflow-error class that RFC 0076's soundness statement carves out — `long` arithmetic behaves exactly as it does today. The one interaction to note is that `uint256` values cannot be compared with `long` values, which is inherited existing semantics rather than a new restriction, but does mean an application migrating a field from `long` to `uint256` must update policies that compare it.

**Migration cost: none.** This is not a breaking change. No existing policy, schema, entity file, or API changes behavior; the type is additive and behind a flag. Existing policies keep parsing, and `long` keeps its range, its overflow errors, and its arithmetic.

**The honest case against.** Every extension type is a permanent tax on the whole toolchain — Rust, Lean, symcc, validator, formatter, every port. This one buys a narrow capability: comparison of wide unsigned integers. It does not serve anyone who needs arithmetic on those integers, does not serve signed fields, and does not serve fractional ones. The public demand we can point to is one third-party request from 2023 plus this RFC. If the community's answer is that the capability is not worth the tax, that is a reasonable answer, and the `Motivation` section is written so it can be reused to evaluate other solutions.

## Alternatives

**1. Do nothing; precompute the comparison in the application.** *Verdict: rejected, but it is the strongest alternative.* It works today and costs Cedar nothing. It also moves the threshold out of the policy and into application code, which is precisely the auditability loss RFC 0080 rejected for time comparisons. We concede that an application *can* bucket a threshold into a small `long` when the set of thresholds is known and fixed at deploy time; the case this RFC is about is parameterized, policy-authored thresholds that differ per principal or per resource, which that trick does not cover.

**2. Split the value across multiple `long`s.** *Verdict: rejected.* Ordering becomes a hand-written lexicographic chain over four limb pairs, each limb signed, and the invariant that makes it correct is invisible to the reader and unchecked by the validator. It is also not obviously more analyzable than a single 256-bit bitvector: four 64-bit comparisons plus the boolean structure to chain them is not free either.

**3. Carry the value as a `String`.** *Verdict: rejected.* Equality already works this way, which is exactly why ordering is the ask — and `<` is not defined for strings, so the workaround stops at equality.

**4. Carry a unit or scale alongside the value, so it fits in `long`.** *Verdict: rejected.* Express amounts in whole tokens, or gwei, or "tenths of an ether," and pass the scale as another context key. Three problems. Comparisons become unreliable across scales, since two values with different scales compare as their unscaled integers rather than their values. A bound at the wrong scale is not an error but a silently wrong policy: "1 ETH" is `1` in whole ether, 10<sup>9</sup> in gwei, and 10<sup>18</sup> in wei, and getting that wrong yields a predicate that is vacuously true (allow everything) or unsatisfiable (deny everything) rather than one that fails loudly. 

**5. Widen Cedar's `long`.** *Verdict: rejected, on three independent grounds.* First, accepted RFC 0057 says in its own text: "This RFC firmly closes the door on changing Cedar's default numeric type to bignum. However, that door is already basically closed. Also, we could still introduce bignums as an extension type (with their own separate multiplication operation) in the future." That is both a closed door and a named alternative, and this RFC takes the named alternative. Second, the maintainers stated the same preference twice in the 2023 exchange: cedar#494 says plainly "We don't want to change the default behavior of Cedar, but we can generalize our code and make it easy for people to play with different Integer types," and the resolution, cedar#495, was a compile-time alias titled "Generalize Integer type (so it can be changed to e.g., i128)". Third — and this is the measurement — widening the alias is not the cheap change it looks like. Flipping `pub type Integer` to `i128` and widening the JSON `Long` variant with it produced **72 distinct test failures, of which 67 land at the JSON-number boundary**, including outright breakage of serde's `#[serde(untagged)]` deserialization for entity and EST parsing. A string-constructed extension type never crosses that boundary. (Those counts measure *widening `long`*, which this RFC does not propose; we cite them only as evidence against this alternative, not as a cost of this RFC.)

The predictable counter-offer is that the alias already exists, so a user who needs wide integers can recompile Cedar with a different `Integer` type. That does not solve the problem this RFC is about. The alias is a compile-time property of a Cedar build, not a language feature: policies written against it are not portable, the width is invisible in the schema, and — decisively — an application platform cannot require its policy authors to run a recompiled Cedar in order to write a policy. Flipping the alias also breaks `cedar-policy-symcc` outright (two `From<i128>` trait-bound errors), and fixing them requires *choosing* a bitvector width, which is a semantic decision about the analysis rather than a mechanical repair.

**6. A wider or higher-precision `decimal`.** *Verdict: deferred, not rejected.* A `decimal256`-style type would be a reasonable future RFC and could layer on the same representation. It is the wrong primitive for this use case: on-chain amounts are integral, so fixed point is a lossy re-encoding; and Cedar "does not currently support arithmetic division (`/`) or remainder (`%`)" (RFC 0080), so a policy cannot rescale base units internally. Authors would hand-write scale factors instead, and under RFC 0057's left-association a chained rescale `CONST * CONST * context.value` overflows for large `CONST` even when `context.value == 0` — 0057 documents exactly this case, and with base-unit scale factors `CONST` is large: `10000000000 * 10000000000 * context.value` overflows on the constants alone. The absence of division makes fixed point *more* hazardous here, not cheaper.

**7. Arbitrary precision (a bignum extension type).** *Verdict: rejected for now, with the case for it stated fairly.* It is the only option that covers Cardano's Plutus `integer`, and RFC 0057 explicitly leaves the extension-type door open for bignums. But it cannot use bitvector theory at all, moving the encoding to SMT-LIB `Int`; the previous unbounded-integer proposal, [rfcs#36](https://github.com/cedar-policy/rfcs/pull/36), is closed and labelled `rejected`, as is the guarded-arithmetic proposal [rfcs#39](https://github.com/cedar-policy/rfcs/pull/39) that replaced it a week later; and while the space-complexity objections raised in that discussion were about addition and multiplication rather than comparison, discharging that argument for a comparison-only bignum would require evidence we do not have. We would rather ship the fixed-width type we can measure. A fixed 256-bit type also does not foreclose a bignum type later.

For the record, and against the temptation to cite it as support: the 2023 branch `andrewmwells/unbounded_ints` is **not** evidence for this design. It is an abandoned, incomplete `ibig` bignum attempt — stub serializers that emit `0`, an infinitely recursive conversion — not a fixed-width experiment, and it should not be read as precedent for either direction.

**8. `int256` instead of `uint256`.** *Verdict: rejected as the first type; proposed as future work.* Covered under *Out of scope*: a signed 256-bit integer misses exactly half the `uint256` space, including the infinite-allowance sentinel that OpenZeppelin's `ERC20` treats specially. If Cedar would rather add one signed type that covers most of the ABI than one unsigned type that covers the token standards exactly, that is a legitimate design preference and we would rather have the discussion than guess — but note that `int257` is the smallest *signed* width that covers the whole Solidity integer union, and a 257-bit bitvector is a stranger thing to ask a Lean model and an SMT encoder for than a 256-bit one.

**Impact of not doing this.** Applications that authorize over blockchain transaction context keep precomputing amount comparisons outside Cedar and passing booleans in, which is a working design with the authorization logic in the wrong place. Cedar keeps a type system in which wide values can be compared for equality but never ordered.

## Unresolved questions

- **The name.** `uint256` is precise and matches the Solidity/EVM spelling, which is what integrators will recognize. If maintainers prefer a Cedar-idiomatic name that generalizes better across a family, we are happy to be told what it should be.
- **Whether a follow-on RFC for `int256` should be filed immediately after this one**, or wait until `uint256` has proven the shape in practice. `int256` is not part of this ask either way.
- **Whether an explicit `long` → `uint256` conversion is wanted.** Two constraints if so: it cannot reuse the name `uint256`, since extension function names must be unique; and it must error on a negative input rather than reinterpret its bit pattern, per *Invalid input* above. Adding one would not disturb the `__extn`-free JSON shorthand described above: that shorthand looks specifically for a constructor taking a single `String`, so a function taking a `long` is never a candidate for it and cannot make the lookup ambiguous.
