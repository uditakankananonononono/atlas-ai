# Row 102 Consistency Commitment - contract

## Ledger source pin
audits/additional-2000-features.json, id 102: requirement "Consistency Commitment"; description "Uses small yeses to build to large yeses"; status PARTIAL (read from main).

## Delta against the existing mechanism
Existing: `_consistency_commitment`, backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py:530. It takes one prior commitment and one current choice, computes escalation = requested_step / commitment_scale, a pressure score min(1, max(0, escalation-1)) when not freely chosen, and a +/-0.1 band around it. Those are single-step heuristics.
This module (new file consistency_commitment102.py, nothing existing edited) reviews a whole declared ladder of requests with integer arithmetic. Per step: the exact reduced ratio to the most recent accepted step; violation `escalation_over_2x` when size is more than twice that step (size*1 > 2*prior); `not_freely_chosen`; `no_exit_available`; and `continued_after_decline` for any step after a declined one. Violations are listed in that fixed order (continued_after_decline, escalation_over_2x, not_freely_chosen, no_exit_available). The ladder is `allowed` only if no step has a violation and the caller states the whole ladder was disclosed first; `first_violation` names the earliest step and its first code, or `ladder_not_disclosed`.

## Interface
`review({"steps": [...], "ladder_disclosed": bool})`. Step keys: id (non-empty, max 100 characters, unique), size (int 1 to 1,000,000), freely_chosen, accepted, exit_available (booleans).

## Refusals (prefix `CONSIS102:`, exception ConsistencyError)
Non-mapping input; unknown keys; steps not a list of 1 to 50; missing or non-boolean ladder_disclosed; non-mapping step; unknown step key; bad id; duplicate id; size not an int in range (bool and float refused); non-boolean flags.

## Limits
Supplied declarations only. Nothing here measures what a person feels or will do; no prediction of compliance, no advice. A declined step ends the ladder. Boundaries pinned at N and N+1: 50/51 steps, size 1/0 and 1,000,000/1,000,001, id 100/101, ratio exactly 2 versus just over 2.

## Status
Prep only. Independent mutant-battery audit required before landing. Full test suite not run: only this row's tests were run.
