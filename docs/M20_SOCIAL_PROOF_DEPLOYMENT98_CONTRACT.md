# SOCIAL98: exact social-proof count check (row 98)

Ledger source pin: `audits/additional-2000-features.json` row 98, requirement "Social Proof Deployment", description "Leverages herd behavior", status PARTIAL. Ledger file SHA256 `285cc16c474215b241383fb922c8a2f2abfa9f7cda3592b04dc61141317d83ff` at main 48357da0. PREP only: nothing here is wired, landed or closed.

## Delta against the existing mechanism
Existing: `backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py:404` `_social_proof` (read). It takes a claim, an `evidence` string (truthy check only), an optional float `claimed_proportion` and optional `sample_size` (cast through float), computes a float Wilson interval with a fixed z of 1.96 rounded to four places, uses a fixed minimum sample of 30, returns a fixed confidence of 0.85 or 0.5, and has no source, date or age check and no comparison between a claimed figure and counts.
This unit (`social_proof_deployment98.py`, `evaluate_social_proof`, new file, not imported by and not importing the existing one) differs in these checkable ways:
- Inputs are integer counts (observed_count of sample_size), not a float proportion; the proportion is an exact reduced fraction string and the percent is rounded half-up with integer arithmetic.
- The Wilson interval uses a caller-declared rational z (1 to 5), computed with Fractions and integer square root, and is rounded outward to six decimals so it encloses the exact interval. It is not rounded to the nearest value.
- The minimum sample and the maximum evidence age are caller rules, not constants. A required source string and ISO date (ASCII, calendar-checked) are part of the evidence; an evidence date after the packet date is refused.
- An optional claimed whole percent is compared with the rounded observed percent; a mismatch blocks.
- Blocking reasons are listed by name, sorted: `claim_mismatch`, `evidence_stale`, `min_sample_not_met`. No confidence number is produced.
- When nothing blocks, the output carries a plain disclosure of only the supplied numbers ("K of N responses from SOURCE as of DATE."); when blocked it is null. Nothing in the output claims an effect.
- Refusals are `Social98Error` (a ValueError) with the exact prefix `SOCIAL98: ` and fixed message texts that never echo input.

## Input
Exactly `claim`, `evidence`, `as_of`, `min_sample`, `max_age_days`, `z`, plus optional `claimed_percent` (may be null). `evidence` is exactly `source`, `as_of`, `observed_count`, `sample_size`.
Limits: claim 500 characters; source 200; sample_size 1..1000000000; observed_count 0..sample_size; min_sample 1..1000000000; max_age_days 0..3650; claimed_percent 0..100; z a string p or p/q with at most 7 digits per component and 1 <= z <= 5. Text is nonblank with no control characters. Integers must be real integers (not bool, float or string). Unknown or missing keys refuse. Input is not mutated; output holds no aliases.

## Output
claim, evidence (with age_days), proportion, percent_rounded, z, wilson_interval [low, high], rules {min_sample_met, claim_consistent (null when no claim figure), evidence_fresh}, blocked_reasons, deployment_allowed, disclosure, scope `caller_declared_counts_only`, real_world_effect_verified false, limits, boundary.

## Ethical-use framing
The unit checks that a social-proof statement matches counts the caller declares and shows exactly those counts. It does not target individuals, does not choose or fabricate evidence, and does not say whether the statement will change anyone's behavior.

## Tests and gaps
`tests/modules/test_m20_social_proof_deployment98.py`: hermetic, standard library, N and N+1 pins on every limit and rule. Raw RED, GREEN, mutation and scan outputs are supplied separately.
FULL-SUITE UNVERIFIED: only this unit's tests (and neighbor tests named in the package logs) were run, not the full repository suite.

## Limits
Counts, source and dates are declared by the caller and are not fetched or verified. Freshness is checked against the supplied packet date, not a clock. The Wilson interval assumes independent sampling that this unit cannot check. No real-world effect, advice, prediction or permission to act is claimed. Not an acceptance or closure claim.
