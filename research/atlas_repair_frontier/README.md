# Atlas hard-budget repair frontier
Research candidate, not a first, not a new optimizer, not AGI progress evidence.

When memory artifacts become invalid, which executable repairs should an agent
fund under a HARD cost cap? A scalarized value-minus-lambda-cost policy can miss
cap-optimal discrete points even when lambda is chosen perfectly. This small
Atlas benchmark makes that limitation reproducible.

## Reproduce
From repository root, Python 3.12 (no production dependencies):
```
PYTHONPATH=backend python research/atlas_repair_frontier/run_benchmark.py
python research/atlas_repair_frontier/independent_oracle.py
python -m pytest tests/atlas_repair_frontier -q
```
Pytest uses repository conftest and thus needs Atlas test dependencies.

## Measured run
100 deterministic seeds, 12 nodes each, all integer budgets from 1 through sum
of declared costs: 5,964 graph/budget pairs. Directed acyclic repair prerequisites,
positive integer cost 1..9, utility 0..15, 10% non-executable candidates.

| Policy | Summed declared utility |
|---|---:|
| Exact hard-cap predecessor-closed optimizer | 288,420 |
| Best feasible supported scalarized point across ALL lambda >= 0 | 271,475 |
| Closure-aware marginal utility/cost greedy | 285,668 |

Exact wins on 2,200 pairs vs the scalarized comparator and 909 vs greedy. Summed
utility gains are 6.24% and 0.96%, respectively. These totals weight every integer
cap equally; neighboring caps are correlated, NOT independent trials. No
statistical significance or external generalization is claimed. Full replay
exceeds the budget on 4,622 pairs. At every pair selected outputs match the
independently evaluated memoised recursive full replay projection: 5,964/5,964; zero overspends.
The separate combinations oracle confirms all 5,964 optimal utility values.
Recorded wall time around 1.65 seconds is incidental local runtime, not a
comparative speedup claim. Candidate tests: 55 pass locally. Separate m20 regression: 35 pass locally.
These are separate counts, not 90 candidate tests. The auditor independently
verified the original 10 candidate tests; the v3 counts await independent audit.

## Strong comparator, narrow conclusion
We do not merely sweep a few lambda settings. Exact rational inequalities find
all frontier points optimal for SOME lambda, including ties, then grant the
comparator its BEST feasible point per budget. This is a generous mathematical
scalarization baseline, NOT execution of the MemoRepair code or model pipeline.
The win only establishes that scalarization cannot recover some unsupported
discrete hard-cap optima on these generated instances. Classical result, not
new mathematical discovery. MemoRepair itself recognizes the hard-cap PCKP.

A two-item witness is included: costs (2,3), utility (2,4). Budget 2 permits
utility 2, but that point is never optimal for value minus lambda*cost. The
empty set or cost-3 set beats it for every lambda. This is a regression fixture,
not the entire random benchmark.

## Contract and limits
- Explicit topologically ordered graph, at most 20 nodes; exponential worst case.
- Complete provenance and correct declared utilities/costs assumed, not learned.
- Non-executable prerequisites block downstream repair.
- Pure deterministic artifact replay; no LLM, tool API, real memory or external
  side effect. Each artifact is evidence_version + sum(parent values).
- Withholding happens by selection; no concurrent store, transaction, actual
  revocation listener, persistent publication barrier or permission system.
- A SHA256 receipt binds input/selection/version/outputs. It is an integrity
  receipt, NOT a proof of optimality, authenticity or semantic correctness.
- No savings in real tokens/dollars, model accuracy, reasoning or AGI measured.
- No production endpoint is mounted. Not ready to dispatch actual paid repairs.

Files: core module, explicit tests, standalone independent exhaustive oracle,
seeded benchmark harness, raw results and prior-art notes. Audit before landing.

V2 mutation evidence: shipped tests kill 229/253 unique mutants (90.5%);
headline-only judge kills 177/253 (70.0%), 2 by 60-second timeout. Six duplicate
encodings skipped globally. Full survivor logs and methodology: audit/README.md.
Survivors are limitations, not silently waived. V2 awaits independent audit.

V3 corrects seven real test gaps reported by re-audit. Full shipped-test mutation
sweep at every PYTHONHASHSEED 0..9: 235/253 killed (92.9%), 18 survivors, same
survivor set every seed, 2,530 judgments. Worst-case 235/253 includes timeout
kills under original 20-second rule; reasons retained. Optimizer core unchanged.
See audit/V3.md, which corrects the v2 hash-seed count and invalid redundancy/
tie explanations. Candidate status and all novelty limits remain unchanged.
