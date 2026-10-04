# M20 contract changes (baseline 313309be -> honest-estimates change f1bf05d6 and follow-up)

Status: these are NOT equivalent renames. Seven existing assertions were rewritten because the old behaviour returned
numbers that were not measurements. Nothing here is accepted. Provenance of the original requirement wording was not
recovered from the intake record; the "old" column is what the baseline tests asserted.

| Test (file) | Old assertion | New assertion | Reason | Capability status |
|---|---|---|---|---|
| test_meta_reasoner_* (test_m20_planner_scheduler) | `scored[0].score > scored[1].score` (research outranks email by a numeric gain/cost score) | order by risk tier only; with no recorded episodes `score`, `progress_probability`, `information_gain` are None; `ranking_basis` says "no success estimate" | old score came from fixed constants | Ranking = risk tier, then observed tool success rate when >= min samples. **Information gain is not computed anywhere (always None).** |
| test_mcts_rumination_* (same) | `0 < expected_success <= 1` | `mode == "simulated_search"`, `expected_success is None` with status "too little recorded evidence" | old value was hard-coded `0.9 - 0.1*attempts` | Real UCT search over the plan; probability only when every step has an evidence estimate (product of per-tool rates, independence ASSUMED) |
| same test, final line | all steps SUCCEEDED => `expected_success == 1.0` | None, `remaining_steps == 0`, status "no steps remain" | a finished plan is a past fact, not a forecast (WIP21 change, not in f1bf05d6) | Retrospective completion is not reported as a future probability |
| test_row14_counterfactual_simulation (test_m20_metacognition) | best alternative = "read-only dry run" (risk-tier prior) | all estimates None, `best_alternative is None`, `unestimated_alternatives == 2` | no evidence for either alternative | Counterfactuals need recorded episodes per tool |
| test_row14_route (test_m20_metacognition_routes) | best alternative "dry run" | alternatives listed, estimate None, best None | same | same |
| test_m20_13_26_decision_artifact... (test_m20_runtime_depth) | keys information_gain/cost/progress_probability/score present | keys plus risk/ranking_basis/evidence; fresh runtime has gain/probability/score None, `evidence.available False` | no history | `cost` is now the risk rank, not a cost estimate |
| test_m20_30 / test_m20_14 (same file) | expectations registered from a prior | tasks must first build >= 3 recorded successes; surprise = 4th failure contradicting a 3/3 history | predictions only from evidence | Calibration and surprise reflection need history |

## Inputs dropped from scoring (kept in the API signature for compatibility)
- `wm_context` (working-memory text) and `ltm_hits` (semantic hits): neither measures this step's success. They no longer affect ranking.
- The old gain/cost divisor and the risk-tier success priors (.9/.75/.55/.4): removed (see `test_fixed_prior_symbols_are_removed`).

## Gaps retained (not implemented, not claimed)
1. Information gain / value-of-information: no real estimator exists. A grounded version would need recorded outcomes of
   information-seeking steps; until then it stays None.
2. Cost: only the discrete risk rank. No money/time/latency cost model from recorded episodes.
3. Use of long-term-memory relevance to rank steps: removed, not replaced.
4. Independence assumption in the rumination product is unverified.
Replacement coverage: tests/modules/test_m20_honest_estimates.py (evidence-driven ranking, Wilson intervals, minimum samples).

## Original requirement wording (raw source, WIP22)
Source: /downloads/m20-planner-gain-cost-ltm-wording-f2e1793b.json (user-pasted spec text in M00604; spec author unverified; archive is research material, not authority).
Exact wording: "A meta-reasoner selects the next action. It uses a decision tree where each leaf is an executable skill (web_search, write_code, ask_user_clarification). The choice is based on expected information gain, estimated cost, and probability of progress toward the goal."
The spec also asks for reusable HTN methods, episodic plus semantic/procedural long-term memory, a working memory of about 50 chunks, idle MCTS rumination, and a module/model budget downgrade.
The spec gives NO formulas or metrics. So information gain, cost, LTM/WM use, rumination quality and budget downgrade are genuinely requested. They are NOT closed by removing bad tests. No authoritative formula is invented here; the current behaviour is evidence-based and honest, and the parts below stay requested-but-unimplemented gaps.

## Wording of observed rates (WIP22)
An observed success rate (including 1.0) is an observed frequency with a sample-size confidence interval. It is not a calibrated future probability and not proof of independence between steps. No arbitrary rate cap is applied.

## Rumination with no PENDING step (WIP22 fix)
Previously "no PENDING" was reported as "no steps remain" even for PLANNING/RUNNING/WAITING_*/RUMINATING/FAILED/BLOCKED/CANCELLED. Now ruminate returns state_counts, remaining_steps = every non-SUCCEEDED step, plan_complete True only when every step SUCCEEDED (and the plan is non-empty), expected_success always None, and a status naming the unfinished states. DeliberativeLoop.ruminate also restores the real prior task state (it used to force RUNNING, hiding WAITING_APPROVAL etc.) and traces expected_success=None. Tests: every TaskState case in test_m20_planner_scheduler.py plus a loop test in test_m20_executive.py.
