# Row 107 Nudge Design - contract

## Ledger source pin
audits/additional-2000-features.json, id 107: requirement "Nudge Design"; description "Structures choices to guide behavior"; status PARTIAL (read from main).

## Delta against the existing mechanism
Existing: `_nudge`, backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py:565. It computes an `autonomy_score` as max(0, 1 - 0.2*(friction-1)) times 1 or 0.4, a float `supplied_uptake_difference`, a +/-0.1 band, and `deployment_allowed` when easy opt-out, transparency, visibility and friction <= 2 all hold.
This module (new file nudge_design107.py, nothing existing edited) keeps the same four conditions but reports them as named failures in fixed order (opt_out_not_easy, not_transparent, alternatives_hidden, opt_out_steps_over_2), a count `checks_passed` out of 4 and `allowed` only if all four pass. No autonomy score, no band. Optional uptake figures are integer pairs [successes, total] for baseline and default, and the difference is an exact reduced fraction (default minus baseline), reported only when both are given.

## Interface
`review({"options", "default", "easy_opt_out", "transparent", "alternatives_visible", "opt_out_steps", optional "baseline_uptake", "default_uptake"})`; 2 to 20 unique options of 1 to 100 characters; default must be one of them; opt_out_steps an integer 0 to 20 (more than 2 fails the check, more than 20 is refused); uptake totals 1 to 10^9.

## Refusals (prefix `NUDGED107:`, exception NudgeError)
Non-mapping input; unknown keys; missing required key; non-boolean flags; bad opt_out_steps (bool and float refused); options not a list of 2 to 20; blank or over-long option; duplicate option; default not in options; only one of the two uptake pairs; malformed uptake pair.

## Limits
Supplied declarations only; nothing measures what people will choose. A default must not hide costs, obstruct exit or remove alternatives. Not a prediction of behaviour change and not advice; the uptake difference is the caller's figures. Boundaries pinned at N and N+1: 20/21 options, 2/1 options, steps 2/3 and 20/21, option length 100/101, uptake totals 1/0 and 10^9/10^9+1.

## Status
Prep only. Independent mutant-battery audit required before landing. Full test suite not run: only this row's tests were run.
