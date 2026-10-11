# Row 106 Priming Effects - contract

## Ledger source pin
audits/additional-2000-features.json, id 106: requirement "Priming Effects"; description "Activates related concepts unconsciously"; status PARTIAL (read from main).

## Delta against the existing mechanism
Existing (delta base): `_priming`, backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py:555, reached through `run()` in that file. This module is a new file; the existing file, routes and tests are not edited.
Behavior differences, each a deliberate refusal or change here and not a defect finding:
- `float()` coercion of counts (numeric strings accepted): here counts must be exact integers 0 to 1,000,000,000 (bool, float and string refused).
- A partial count set was accepted when either total was nonzero: here all four counts or none; a partial set is refused.
- The Wald interval was reported with no disclosure of when it is unreliable: here it is reported only when both rates are strictly between 0 and 1, with `degenerate_rate`, `small_sample` and `interval_unreliable` flags.
- `bool(disclosed)` coercion: here `disclosed` must be exactly true or false.
- Effect values were rounded floats: here the effect is an exact reduced fraction plus a decimal string rounded to 6 places half-even from the exact fraction.

## Interface
`review({"context", "disclosed"[, "exposed_successes", "exposed_total", "control_successes", "control_total"]})`. Returns `row`, `context`, `disclosed`, `effect` ("p/q" or null), `effect_decimal` (string or null), `interval_95` (two floats rounded to 6 places, or null), `degenerate_rate`, `small_sample`, `interval_unreliable`, `causal_estimate_available` (always false), `descriptive_difference_available`, `covert_influence_blocked`, `allowed`, `limits` (three strings).
Effect is exposed proportion minus control proportion, exact. The 95% interval is effect plus/minus 1.96 times sqrt(p1(1-p1)/n1 + p2(1-p2)/n2), a float pinned with a tolerance. `small_sample` is true when any of the four cells (successes and failures in each group) is below 5. `allowed` is true only when `disclosed` is true and counts are present.

## Refusals (prefix `PRIME106:`, exception PrimingError)
Messages name the schema field and never include a supplied value: non-mapping input; too many keys (before any key is read); unknown key; missing key; `context` wrong type, over 200 characters (cap before strip and scan), blank, or with a forbidden character; `disclosed` not an exact bool; a partial count set (`counts`: all four or none); a count that is not an exact integer from 0 to 10^9; a total below 1; successes above their total. Type and range of every count is checked before the relations between counts.

## Limits
Supplied counts only; assignment, confounding and measurement are not verified. An unadjusted difference of proportions: no causal claim and no claim that anything is unconscious or effective. Context-setting must be disclosed. The unit never decides how to prime anyone, never sends or posts anything, measures no behavior and gives no advice. Boundaries pinned at N and N+1: counts 0/-1 and 10^9/10^9+1, totals 1/0, cell 5/4 for each of the four cells, context 200/201.

## Status
Independent gate: separate record. Full test suite not run: only this row's tests were run.
