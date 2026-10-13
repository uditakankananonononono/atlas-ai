# Group 80 math engine contract (v4, auditor-revised)

Source request (instinct doc, group 80): crack maths problems and dilemmas in any field.

## What is built (real runtime behavior)

`backend/app/modules/m20_general_cognitive_worker/math_engine.py` - a bounded,
stdlib-only exact math engine with a `solve(task)` dispatcher. Problem families:

- linear systems up to 8 unknowns, exact rational Gaussian elimination
  (unique / no-solution / infinite-solutions with independently recomputed ranks)
- quadratics with exact roots, including exact quadratic-surd form a + b*sqrt(r);
  the surd kernel is computed by bounded full factorization, so exact form
  requires discriminant numerator*denominator <= 10**18 (larger is refused,
  never approximated)
- polynomial arithmetic: exact derivative and integral (rational coefficients), evaluation
- linear Diophantine equations ax + by = c (particular + general solution, or a
  proven no-solution verdict from the gcd)
- primality: deterministic Miller-Rabin for n <= 10**18
- factorization: trial division + Pollard rho with a hard iteration budget
  (500,000 iterations across one call; exhaustion is a refusal, never a hang),
  n <= 10**18
- Chinese remainder systems, up to 8 pairwise-coprime congruences, combined
  modulus capped at 10**160
- combinatorics: choose, permute, derangements, Catalan, Fibonacci (exact,
  results capped at 10**60, n/k must be exact integers, Catalan n <= 500)
- arithmetic and geometric sequences: nth term and sum of first n terms, with
  pre-computed size refusals instead of materializing giant powers
- descriptive statistics: exact mean, median, population variance, min, max
- arithmetic expression evaluation: a safe AST whitelist (no names, calls,
  attributes, or imports), with an independent shunting-yard/RPN evaluator as
  the cross-check. Intermediate arithmetic results inside the two evaluators
  are capped at 200 bits (~10**60), so nested-power bombs are refused, not
  allocated; other families carry their own named bounds (CRT combined
  modulus, egcd inputs, sequence powers, combinatorics results) rather than
  one global cap.

## Verification (task-bound, full-field, re-verifiable)

Every `solve()` result carries a `verification` receipt from `verify()`.
verify() trusts NOTHING in the result: it recomputes every reported field
from the original task inputs - status, ranks, discriminant and displayed
root strings (exact roots recomputed via the shared `_quadratic_exact`
helper; `roots` must be empty when the discriminant is negative), gcd and
general-solution strings, CRT modulus/residues/normalized congruences,
combinatorics op/n/k as given in the task (choose/permute keep the original
k; internal normalization never leaks into the result) and the expected
value via independent formulas (math.comb/perm, exact inclusion-exclusion
for derangements, fast-doubling for Fibonacci), the task's own
sequence_kind and closed forms in a distinct arrangement, all six
statistics fields, the expression value via the independent evaluator, and
polynomial calculus via the inverse operation. Delivered results are
re-verifiable: nothing verify() needs is stripped, and a malformed
`_roots_exact` (when present) yields a false receipt, never a crash.

verify() also enforces the exact result envelope per family: required keys
must be present and unknown keys are rejected (a delivered result's own
'verification' receipt is the one allowed extra, never trusted). Shape
binding matches the solver's admissible-input boundary: linear systems
must be square with a matching vector (caps applied before any element
iteration), the polynomial integral's constant term is bound to zero, and
primality answers must be real booleans.

verify() re-applies every solve bound before recomputing - combinatorics
n/k ranges and the 10**60 result cap (a derangements feasibility pass runs
before any inclusion-exclusion), Catalan n <= 500, sequence n and the
geometric power pre-checks, expression source length, matrix sizes,
statistics list size, CRT pair count, and factor-list shape - so a direct
verify() call on an out-of-bounds task fails fast instead of computing.

A result whose verification fails is never reported as solved: `solve()`
flips its status to `verification_failed`. Tamper tests (both auditor probe
rounds) prove altered answers are rejected for every family.

## What is NOT achieved (named missing scope)

- "Any field" is not achieved. No geometry, trigonometry, limits, non-polynomial
  calculus, differential equations, proofs, or open-ended dilemmas.
- The engine is a library, not a mounted product surface: no HTTP route, no UI,
  no natural-language word-problem parsing in this patch.
- Verification is an independent in-process re-check, not the program's
  external auditor gate.

Verdict for group 80 remains PARTIAL.
