# Atlas E9: bounded emergent formalism experiment

Date: 2026-10-13. Python: CPython 3.12.14. Main source pin:
`4f68f54a0d0742982192aa643c2fa92d61437c9b`. No paid services or model calls.

## Outcome and claim boundary

The system induces task-specific executable operators from scalar observations,
not from environment matrices. It finds coefficients and a minimal uniquely
fitted order, constructs composition in a quotient ring, produces independently
testable future predictions, and translates the operator into human algebra.
The hypothesis class, algebra construction and discovery algorithm are authored.
It does **not** discover a new mathematical law, expand its own operator language,
or beat the strongest known algorithm. This is a measured component, not a
stand-in for completion of the requested Emergent Formalism direction.

| Claim | Status | Evidence |
|---|---|---|
| 60 authored environments, 2,640/2,640 held-out predictions correct | VERIFIED | `results.json`, deterministic CPython 3.12.14 replay |
| Task-specific recurrence coefficients/order inferred without matrices or future answers | VERIFIED | `discover(prefix)` receives 24 observations only |
| Executable composition and human-math translation available | VERIFIED | Operator definition, ring-law tests, per-task definitions |
| Strong Berlekamp-Massey control also gets 2,640/2,640 | VERIFIED | Separate discrepancy-based inference implementation |
| Bounded enumerative synthesis gets 88/2,640 | SCOPED | 2 fully solved tasks, 58 budget exhaustion; explicit coefficient DSL and 20,000-candidate budget |
| 2,520/2,640 test indices lie below 10,000 | SCOPED | This is count(index < 10000), not an executed direct-iteration baseline; distant-index predictions are separately verified |
| Shuffled-observation control gets 0/2,640 | VERIFIED | Seeded shuffle, same fitter and test indices |
| Random/corrupted-validation rejection | SCOPED | 5/5 IID random prefixes and 5/5 corrupted validation prefixes rejected |
| Real delayed transition-matrix changes are missed | VERIFIED | 5/5 unchanged prefixes accepted; 0/5 switched-environment answers at index 100 correct; 6/385 suffix predictions correct |
| New mathematics or improvement over strongest recurrence methods | PARTIAL | Not established; prior art directly covers the construction |
| General Emergent Formalism with autonomous grammar invention | PARTIAL | Not implemented; no generalization beyond this authored class established |
| Atlas production integration | PARTIAL | Standalone importable experiment; no service wiring changed |

## Frozen run specification

Five seeds: 17, 29, 43, 71, 101. Three environment families: dense,
diagonal and Jordan transition matrices. Four latent dimensions: 2, 4, 6, 8.
All data are **experimenter-authored synthetic** systems over the fixed prime
field F_1009. The environment emits a scalar linear observation of a latent
state. Discovery receives the first 24 emissions, uses the first 16 for fitting
and the next 8 to refuse unsupported fits. Prediction tests use indices 24..63,
100, 1000, 10^6+seed, 10^12+seed. Test answers come from independent matrix
exponentiation, not the inferred recurrence evaluator. Seeds and specification
were fixed in code before first run, but there is no externally timestamped
preregistration or seal, and the same experimenter authored model and data.

Discovery tries increasing orders, solves exact overdetermined linear equations
and rejects nonunique or inconsistent solutions. For recurrence coefficients c,
its executable definition is:

`a_(t+d) = sum_(j=0..d-1) c_j*a_(t+j) mod 1009`

`q(x) = x^d - sum_j c_j*x^j`

`compose(u,v) = u*v mod q`, `predict(n) = <x^n mod q, initial>`.

Applicability requires a stationary exact homogeneous linear recurrence within
the order cap over F_1009. Prefix agreement is not a universal proof. The minimal
fitted order can theoretically be smaller than the hidden state dimension, but
all 60 reported fits equal that dimension, so this case is not exercised. Ambiguous all-zero
prefixes fail closed instead of being assigned an arbitrary operator.

## Baselines and controls

1. Berlekamp-Massey on the same 16 fit points, independently coded; same eight
   validation points and quotient evaluator. This strong baseline ties discovery.
   Shared evaluator is disclosed; separate matrix oracle tests it independently.
2. Plain enumerative recurrence-program synthesis, coefficients {-2,-1,0,1,2},
   orders 1..8, 20,000 candidates. It does not include arbitrary field constants,
   learned abstractions or linear algebra. Hence the gap is relative to that
   grammar/budget only, not a statement that program synthesis cannot solve it.
   The enumerator receives all 24 prefix points (not just 16 fit points). Inferred
   minimal-order coefficients fall outside its {-2,-1,0,1,2} grammar for all
   60 tasks. This disadvantages its hypothesis class. It still finds a
   higher-order grammar-expressible fit in two cases, so grammar exclusion of
   the inferred minimal recurrence does not prove no equivalent program exists.
3. Index-count proxy for a 10,000-step iteration cap: count(index < 10000).
   Direct iteration was not run as a scoring baseline. No wall-clock or FLOP
   efficiency advantage measured; the count is only a disclosed resource proxy.
4. Shuffled prefixes, IID prefixes, validation corruption, actual delayed
   transition-matrix changes: keep state continuous, switch the matrix advancing
   x_t to x_(t+1) at t=24, then independently emit the following observations.
   The 24-point prefix is unchanged. At index 100, predicted/actual outputs are
   646/789, 842/64, 124/862, 137/846, 421/747 for the five seeds. Of 385
   suffix emissions at indices 24..100, 6 match, including the unchanged
   emission at index 24 in each run. No output is fabricated as truth+1.

Unit tests separately use seeds 887, 991, 1109, orders 1..8, three families,
indices up to 10^15+seed, and independent iterative-vs-matrix oracle comparisons.
Six unit tests pass. Ring laws and composition check reproducibility and
semantics, but are not counted as evidence of intelligence.

## Prior art and novelty

- DreamCoder already learns executable abstractions/programming languages:
  https://arxiv.org/abs/2006.08381
- Berlekamp-Massey and Kitamasa already infer recurrences and compute distant
  terms by characteristic-polynomial reduction:
  https://mtuann.github.io/competitive-programming-cpp/topics/math/berlekamp-massey-kitamasa/
- Polynomial arithmetic and companion matrices are established software tools:
  https://numpy.org/doc/stable/reference/routines.polynomials.polynomial.html

These sources were fetched, not inferred from memory. No novelty claim is made.
No exhaustive prior-art review was performed.

## Replay

From repository root, using Python 3.12:

```sh
python3.12 -m unittest discover -s experiments/e9_formalism -p 'test_*.py' -v
python3.12 experiments/e9_formalism/run_experiment.py --output /tmp/e9-replay.json
diff -u experiments/e9_formalism/results.json /tmp/e9-replay.json
```

Standard library only. For an exact raw-file comparison use CPython 3.12.14,
because the output records the Python version. Other 3.12 versions should have
identical evidence values but a differing `python` metadata field.

## What remains

A next substantive advance needs a learner that proposes new executable grammar
rules, evaluates them on genuinely different problems, and outperforms powerful
existing synthesis/abstraction systems on a sealed benchmark. This patch does
not satisfy that ambition. Delayed changes demonstrate why law discovery needs
active falsification and deployment monitoring, not self-certification.
