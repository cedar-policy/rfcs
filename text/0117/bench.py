#!/usr/bin/env python3
"""
Minimal reproduction of the `uint256` RFC's solver-cost measurement.

It regenerates the exact SMT-LIB2 formulas behind the table in the RFC's
"Symbolic compilation" section and times cvc5 on them, so a reviewer can
re-derive the headline numbers from scratch with only cvc5 and Python 3.

WHAT IT MEASURES
  Cedar's symbolic compiler (cedar-policy-symcc) encodes a fixed-width
  integer as an SMT bitvector. The RFC's claim is that COMPARISON-ONLY
  reasoning stays cheap when the width goes from 64 to 256 bits, while
  ARITHMETIC does not. This script proves an operand bound over k
  structurally identical constraints. Only two things ever change:
      - the operand term:   cmp -> x_i            (no arithmetic)
                            mul -> (bvmul y_i x_i) (forces a multiplier)
      - the width n in (_ BitVec n):  64 vs 256
  The boolean skeleton, the constants, and the clause count are otherwise
  byte-for-byte identical, so a cell-to-cell comparison varies exactly one
  thing.

THE FORMULA ("bound" shape, always UNSAT)
  Each x_i is asserted to be small (below 2^(n/4)); the formula then claims
  that some operand term is large (reaches 2^(n/2)). That claim is false, so
  the solver must prove it unsatisfiable. For `cmp` this is interval
  reasoning. For `mul` the solver cannot establish the bound without reasoning
  THROUGH the multiplier -- which is exactly the overflow-safety work that
  wei-scale arithmetic in a policy would force, and the reason the RFC leaves
  arithmetic out of the type.

  Concretely, `gen("cmp", 64, 2)` produces (2 clauses, 64-bit, small=2^16,
  limit=2^32):

      (set-logic QF_BV)
      (set-info :status unsat)
      (declare-const x0 (_ BitVec 64))
      (declare-const x1 (_ BitVec 64))
      (assert (bvult x0 (_ bv65536 64)))          ; x0 < 2^16
      (assert (bvult x1 (_ bv65536 64)))          ; x1 < 2^16
      (assert (or (bvuge x0 (_ bv4294967296 64))  ; some x_i >= 2^32 ?
                  (bvuge x1 (_ bv4294967296 64)))) ; ...no: UNSAT
      (check-sat)

  and `gen("mul", 64, 2)` is identical except each operand becomes a product
  of two small inputs, so the large-value claim is about (bvmul y_i x_i):

      (declare-const x0 (_ BitVec 64)) (declare-const y0 (_ BitVec 64))
      (declare-const x1 (_ BitVec 64)) (declare-const y1 (_ BitVec 64))
      (assert (bvult x0 (_ bv65536 64))) (assert (bvult y0 (_ bv65536 64)))
      (assert (bvult x1 (_ bv65536 64))) (assert (bvult y1 (_ bv65536 64)))
      (assert (or (bvuge (bvmul y0 x0) (_ bv4294967296 64))
                  (bvuge (bvmul y1 x1) (_ bv4294967296 64))))

HOW TO RUN
  cvc5 must be on PATH (or set the CVC5 env var to its path).
      python3 bench.py                 # the RFC table: cmp+mul, 64 vs 256 bits
      python3 bench.py --emit ./smt2   # just write the .smt2 files, don't run
  Timings are machine- and version-specific; see README.md for the exact
  cvc5 version and host the RFC's numbers were taken on.
"""
import subprocess, time, os, sys, statistics, argparse


def bv(val, n):
    """An n-bit SMT-LIB bitvector literal for `val`, reduced mod 2^n so it
    always fits the width (e.g. bv(65536, 64) -> "(_ bv65536 64)")."""
    return f"(_ bv{val % (2 ** n)} {n})"


def operand(op, i):
    """The i-th operand term whose magnitude the formula bounds.

    This one line is the ONLY difference between the two arms being timed:
      "cmp" -> the bare variable x_i        (the solver does no arithmetic)
      "mul" -> (bvmul y_i x_i)              (the solver must go through a
                                            multiplier to bound the result)
    """
    if op == "cmp":
        return f"x{i}"
    if op == "mul":
        return f"(bvmul y{i} x{i})"
    raise ValueError(op)


def gen(op, n, k):
    """Build one 'bound'-shape SMT-LIB2 formula as a string.

    Args:
      op: "cmp" or "mul" -- selects the operand term (see `operand`).
      n:  bitvector width in bits (64 or 256 here).
      k:  number of clauses; larger k = more independent constraints.

    Shape: declare k inputs x_i (and y_i for mul), assert each input is below
    2^(n/4), then assert that at least one operand term reaches 2^(n/2). The
    small-input bounds make that final disjunction impossible, so the formula
    is UNSAT -- which the runner checks, guarding against a formula that is
    accidentally trivial. Returns the full script ending in (check-sat).
    """
    small = 2 ** (n // 4)   # upper bound asserted on every input
    limit = 2 ** (n // 2)   # the (unreachable) magnitude the formula claims
    L = [
        f"; auto-generated: op={op} width={n} clauses={k} shape=bound",
        "(set-logic QF_BV)",           # quantifier-free bitvectors
        "(set-info :status unsat)",
    ]
    # Declarations: one input per clause for cmp; a pair per clause for mul.
    for i in range(k):
        L.append(f"(declare-const x{i} (_ BitVec {n}))")
        if op != "cmp":
            L.append(f"(declare-const y{i} (_ BitVec {n}))")
    # Hypotheses: every input is small.
    for i in range(k):
        L.append(f"(assert (bvult x{i} {bv(small, n)}))")
        if op != "cmp":
            L.append(f"(assert (bvult y{i} {bv(small, n)}))")
    # Claim to refute: some operand term is large. (bvuge = unsigned >=.)
    cl = [f"(bvuge {operand(op, i)} {bv(limit, n)})" for i in range(k)]
    body = "(or " + " ".join(cl) + ")" if k > 1 else cl[0]
    L.append(f"(assert {body})")
    L += ["(check-sat)", "(exit)"]
    return "\n".join(L) + "\n"


CVC5 = os.environ.get("CVC5", "cvc5")
BASE_ARGS = ["--lang=smt2", "--seed=1"]   # pin the parser; fixed seed = determinism


def run_once(path, timeout):
    """Run cvc5 once on `path`, returning (wall_seconds, first_output_line).
    A timeout returns (elapsed, "TIMEOUT") rather than raising."""
    t0 = time.perf_counter()
    try:
        p = subprocess.run([CVC5] + BASE_ARGS + [path],
                           capture_output=True, text=True, timeout=timeout)
        dt = time.perf_counter() - t0
        return dt, (p.stdout + p.stderr).strip().split("\n")[0].strip()
    except subprocess.TimeoutExpired:
        return time.perf_counter() - t0, "TIMEOUT"


def measure(path, timeout):
    """Time one formula and return (median_seconds, reps, result_string).

    Reps are adaptive so the whole table finishes in minutes: a cell whose
    first run is fast is sampled more (5x under 1s, 3x under 10s), a slow cell
    is run once and reported as a single sample. `result_string` is cvc5's
    verdict ("unsat" / "TIMEOUT"), which the caller asserts against.
    """
    dt, res = run_once(path, timeout)
    if res == "TIMEOUT":
        return None, 1, "TIMEOUT"
    reps = 5 if dt < 1.0 else (3 if dt < 10.0 else 1)
    samples = [dt]
    for _ in range(reps - 1):
        samples.append(run_once(path, timeout)[0])
    return round(statistics.median(samples), 4), reps, res


WIDTHS = [64, 256]
KS = [32, 128, 512]


def main():
    """Generate and time the RFC table, or (with --emit) just write the files.

    The plan is the four rows of the RFC table: comparison-only at k=32/128/512
    and the arithmetic contrast (bvmul) at k=32, each at 64 and 256 bits.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", metavar="DIR",
                    help="write the .smt2 files to DIR and exit (do not run cvc5)")
    ap.add_argument("--timeout", type=float, default=120.0,
                    help="per-query timeout in seconds (default 120)")
    args = ap.parse_args()

    plan = [("comparison only", "cmp", k) for k in KS] + [("with bvmul", "mul", 32)]

    if args.emit:
        os.makedirs(args.emit, exist_ok=True)
        for _, op, k in plan:
            for n in WIDTHS:
                path = os.path.join(args.emit, f"bound_{op}_n{n}_k{k}.smt2")
                with open(path, "w") as fh:
                    fh.write(gen(op, n, k))
        print(f"wrote {len(plan) * len(WIDTHS)} files to {args.emit}")
        return

    print(f"{'operand':<22}{'64-bit':>12}{'256-bit':>12}")
    print("-" * 46)
    tmp = "/tmp/uint256_bench"
    os.makedirs(tmp, exist_ok=True)
    for label, op, k in plan:
        cells = []
        for n in WIDTHS:
            path = os.path.join(tmp, f"bound_{op}_n{n}_k{k}.smt2")
            with open(path, "w") as fh:
                fh.write(gen(op, n, k))
            med, reps, res = measure(path, args.timeout)
            assert res in ("unsat", "TIMEOUT"), f"unexpected result {res!r} for {path}"
            cells.append("timeout" if med is None else f"{med:.3f} s" +
                         ("" if reps > 1 else "*"))
        print(f"{label + f', k={k}':<22}{cells[0]:>12}{cells[1]:>12}")
    print("\n* single sample (cell was too slow for a median); "
          "all others are 3- or 5-sample medians.")


if __name__ == "__main__":
    main()
