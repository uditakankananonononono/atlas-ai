# M20-DEBT693-SCHEDULE-01: bounded exact technical-debt scheduling

Scoped capability for row 693 Technical Debt Management only. Does NOT close
the full row title: no repository scanning, no debt discovery, no real
engineering-hour measurement, no predicted savings, no learned prioritization
model. The row's broader PARTIAL diagnostics in
`software_practice_685_709.py` (`technical_debt_management`, impact/frequency
scoring) are untouched; this unit adds exact subset scheduling as a separate
module. Wiring into the shared 685-709 method surface ships as a separate
integrator-applied patch, not here.

Input: a finite caller-supplied debt dependency graph (`items`, 1..12 entries,
each `id`, declared `benefit`, declared `cost`, optional `depends_on` id list)
and a declared `budget_hours`. Benefits and costs are caller declarations,
never measured or predicted values; `provenance` states this verbatim.

Computation: bounded exhaustive subset search. All 2^n subsets (state cap
4096 at n = 12) are enumerated; a subset is feasible when it is closed under
prerequisites (every dependency of a selected item is also selected) and its
total cost is within budget. The receipt returns the benefit-maximal feasible
subset, the `unselected` list with per-item reason
(`infeasible_within_budget` when the item's transitive prerequisite closure
alone exceeds budget, else `not_selected_optimal_tradeoff`), and an
optimality certificate: algorithm name, items, `subsets_enumerated` = 2^n,
state cap, optimal benefit/cost, closure requirement, tie-break rule.
Exhaustive enumeration makes the certificate independently reproducible by
re-enumeration; nothing is asserted from heuristics.

Determinism: ties among benefit-maximal feasible subsets resolve to the
lexicographically smallest sorted selected-id tuple, so the selection is
independent of input item order (tests permute every item order). Arithmetic
is exact (`Fraction`), so float inputs cannot flip comparisons. `item_trace`
keeps the original unsorted source order with input indices for provenance
only; selection never reads it. `provenance.input_sha256` hashes the
canonical (sorted-keys) input. Identical inputs give byte-identical receipts.

Refusals (ValueError, 422 at the route): non-object input; item count outside
1..12 (12 accepted, 13 refused); missing/empty/duplicate ids; missing
benefit/cost; boolean, NaN, infinite, string, or negative numerics;
non-list `depends_on`; unknown dependency references; dependency cycles
(including self-dependency); missing or negative budget.

Side effects: none. `provenance` declares `repository_edits: false`,
`learned_prioritization: false`, `benefits_are_predicted_savings: false`,
`external_task_scheduled: false`. No model download, external execution,
persistent state, or other row closure. `human_review_required: true`:
the receipt ranks caller-declared numbers; it does not decide engineering
work.

Tests (`tests/modules/test_m20_debt693_schedule.py`): hand-computed
known-answer fixtures; an independent brute-force combination oracle over a
150-case seeded acyclic corpus; exact 12/13 bounds; zero-budget and
exact-cost boundaries; infeasible costly prerequisite naming; cycle,
self-dependency, unknown-reference and duplicate-id refusal; boolean/NaN/
infinite/string numeric refusal; all-permutation tie-order independence;
receipt determinism and unsorted source-trace checks; provenance flags; a
greedy ratio-baseline floor over a 120-case seeded corpus (exhaustive never
loses, strictly wins at least once). Mounted auth/tenant route checks live
in the separate wiring patch and run only after the integrator applies it.
