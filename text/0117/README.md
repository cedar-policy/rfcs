# `uint256` RFC — benchmark appendix

`bench.py` is a minimal, self-contained reproduction of the solver-cost
measurement in the RFC's *Symbolic compilation* section. It regenerates the
exact SMT-LIB2 formulas the table is built from and times cvc5 on them, so the
headline claim — that comparison-only reasoning stays cheap from 64 to 256
bits while arithmetic does not — can be re-derived from scratch.

## Requirements

- Python 3 (standard library only)
- [cvc5](https://cvc5.github.io/) on `PATH`, or its path in the `CVC5` env var

## Running

```
python3 bench.py                 # run the table: comparison-only + bvmul, 64 vs 256 bits
python3 bench.py --emit ./smt2   # only write the .smt2 files, run nothing
python3 bench.py --timeout 60    # per-query timeout in seconds (default 120)
```

Each cell writes one `.smt2` file and times cvc5 on it with `--lang=smt2
--seed=1`. Fast cells report a 3- or 5-sample median; a cell too slow for that
reports a single sample, marked `*`.

## What it generates

The `bound` shape: over *k* structurally identical constraints, inputs are
bounded by 2^(N/4) and the formula claims some operand term reaches 2^(N/2)
(unsatisfiable). Two arms differ only in the operand term —

- `cmp`: `x_i` — no arithmetic
- `mul`: `(bvmul y_i x_i)` — forces the solver through a multiplier

— and the two widths differ only in `n` of `(_ BitVec n)`. The boolean
skeleton, constants, and clause count are otherwise identical, so a
cell-to-cell comparison varies exactly one thing. This is the full benchmark's
arithmetic-isolating shape; the `mul` bound cannot be established without
reasoning through the multiplier, which is why it stands in for the
overflow-safety obligation wei-scale arithmetic would impose.

## Reference numbers

The medians in the RFC were taken with:

- **cvc5 1.3.4** (`git f3b21c4`)
- **AMD EPYC 9R14**, single core (one cvc5 process at a time)
- Linux, kernel 6.12.x

Timings are machine- and version-specific, so absolute numbers will differ on
other hardware; the 64-bit-vs-256-bit *ratio* is the portable result. On the
reference host `bench.py` reproduces the table's comparison-only k=32 cells
(~0.028 s at 64 bits, ~0.124 s at 256) and the `bvmul` k=32 64-bit cell
(~2.58 s).
