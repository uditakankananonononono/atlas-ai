# E5: does the improvement gate catch bad patches that tests alone accept?

Source pin: atlas-ai commit ef1f6af (default branch HEAD when cloned for this run); gate file `backend/app/self_improve/improvement_gate.py` unchanged since the clone.

Scope: that gate only. Synthetic corpus authored by the experimenter, 12 small function templates, 73 patches. Deterministic run, so there is no seed noise; the variance this run cannot measure is corpus authorship. Nothing here is a statement about patches outside this corpus.

## Setup (frozen before scoring)
- Mutant generator: `mutants.py`, patch-independent line operators, fixed.
- Three decision rules compared on every patch:
  - T0: tests pass and at least one counted.
  - T1: T0 + test count not below baseline + plan sandbox/branch checks (everything the gate does except mutation).
  - GATE: full `ImprovementGate.authorize` with `run_mutations` evidence, declared equivalents = 0.
- Conditions per template: A correct code + thorough tests; B correct code + weak tests; C buggy code + weak tests (tests pass); D buggy code + thorough tests (control); E correct code but plan touches a file outside the sandbox; F buggy code, tests thinned so count falls below baseline; G (is_leap only) bug of omission with tests that exercise every existing line.

## Results

| Claim | Status |
|---|---|
| A, correct + thorough tests: T0 12/12 accepted, T1 12/12, GATE 10/12 (2 refused as survivors) | VERIFIED |
| B, correct + weak tests: GATE refused 7/12 (T0/T1 accepted 12/12) | VERIFIED |
| C, buggy + weak tests: T0 and T1 accepted 12/12; GATE refused 6/12 and accepted 6/12 | VERIFIED |
| D, buggy + failing thorough tests: all rules refused 12/12 (GATE via baseline-fails refusal) | VERIFIED |
| E, out-of-sandbox file: T0 accepted 12/12; T1 and GATE refused 12/12 (structural rule, not mutation) | VERIFIED |
| F, test count dropped below baseline: T0 accepted 12/12; T1 and GATE refused 12/12 (structural rule, not mutation) | VERIFIED |
| G, omission bug with line-complete tests: GATE accepted 1/1 | VERIFIED |
| Mutation evidence adds catches beyond T1 only in C (6 of 12) on this corpus | VERIFIED |
| Mutation evidence cost: 2 of 12 well-tested correct patches refused (clamp: 2 surviving mutants that I judged equivalent by reading, not proven; window_sum: the thorough tests do not exercise n=1, so the surviving mutant reflects a gap in the authored tests) | VERIFIED |
| In the 6 accepted C patches and the G patch, the supplied tests killed every generated mutant of the buggy code | VERIFIED |
| Those accepted bugs are mostly omissions or changed semantics that line mutants cannot reveal (my reading of the 7 cases, not a tested classification) | UNVERIFIED |
| The gate's catch rates on this corpus apply to patches outside it | UNVERIFIED |
| The 50% catch rate on C applies outside this corpus | UNVERIFIED |
| Hypothesis supported for under-tested changed lines: GATE refused 6 of 12 C patches that T1 accepted | VERIFIED |
| Hypothesis falsified for omission bugs: 6 C patches and G passed the gate | VERIFIED |

## What failure showed
1. The gate misses omission bugs. Accepted bad patches: window_sum, dedupe, parse_amount, chunk, safe_div, top_k (C) and is_leap (G). Mutating code that exists cannot reveal code that is missing.
2. Declared equivalents are a caller claim; with 0 declared, equivalent mutants cause false refusals (clamp, A).
3. Code the generator cannot mutate fails closed as UNGATED. No such case occurred after operators were fixed, but an earlier operator set produced 0 mutants for dedupe and top_k, so coverage of the generator matters.
4. Most of the structural wins (E, F) come from the sandbox and baseline-count rules, not mutation.

## Proposed follow-ups (not done)
- Add a spec-derived property or differential check for omission bugs (compare against a reference implementation on generated inputs) and re-score C and G.
- Second, independently authored corpus to test whether the 6/12 holds.
- Equivalent-mutant triage step before refusing.

Reproduce: `python experiments/e5_gate_quality/run_experiment.py <out_dir>` (needs pytest, ~90 s). Raw per-patch output: `results.json`.
