# E3: goal formation (SYNTHETIC LABELS, every result UNVERIFIED)

Source pin: atlas-ai commit ef1f6af, Python 3.12.14. No real owner decision, journal entry or preference was read or used. The accept/reject labels come from a hidden preference function I wrote (accept probability = sigmoid(3 * (value - 0.6 * cost + 0.5 * novelty - 0.5))), so every number below describes a simulation, not the owner. Real labels are consent-pending with the owner; until they exist, all rows stay UNVERIFIED.

Setup: 20 seeds; each world has 60 candidate goals plus 12 near-duplicates under different signatures; 20% of goals need a gated action (payment or person-facing communication). Observable context is a noisy copy of value, cost, novelty (sd 0.3). Urgency (event count and recency) is correlated with value only weakly (30% weight). Top-10 proposals scored. Rankers: R0 order from the shipped `GapDetector` (real code, fed synthetic gap events); R1 random; R2 value-minus-cost-plus-novelty heuristic; R3 R2 plus duplicate removal; R4 logistic model trained on 40 synthetic labelled goals plus duplicate removal; R5 oracle (knows the hidden probability).

## Results (mean accepted fraction in top 10; seed sd in parentheses)

| Claim | Status |
|---|---|
| R0 detector 0.575 (0.12), R1 random 0.445 (0.13), R2 0.730 (0.17), R3 0.740 (0.18), R4 0.610 (0.18), R5 oracle 0.775 (0.13) | UNVERIFIED |
| R3 beats R0 by 0.165, paired bootstrap 95% interval [0.055, 0.265] | UNVERIFIED |
| R4 (learned from 40 labels) beats R0 by 0.035, interval [-0.080, 0.145], so no detectable gain over the detector | UNVERIFIED |
| R4 beats random by 0.165, interval [0.075, 0.255]; hand heuristic R3 beats R4 by 0.130, interval [0.070, 0.190] | UNVERIFIED |
| R0 beats random by 0.130 only because the simulation ties urgency to value at 30%; this is built in, not discovered | UNVERIFIED |
| Duplicates in top 10: R0 0.45, R2 0.60, all dedupe variants 0 | UNVERIFIED |
| Gated goals make up about 1.85 of the top 10 for every ranker (about 19%); no ranker here executes anything or tags approval, so this run says nothing about leak safety | UNVERIFIED |
| R3's heuristic uses the same functional form and weights as the hidden preference, so its score is circular and an upper-ish bound, not evidence it would match a real owner | UNVERIFIED |
| Any of this predicts what the real owner would accept | UNVERIFIED |

## What this does and does not show
- It shows the harness works end to end on the shipped detector, and that with 40 noisy labels a learned ranker is not distinguishable from the detector, while dedupe removes near-duplicates. Those are properties of the simulation.
- The hypothesis (candidate goals ranked by expected value and cost are accepted more often than detector order) is untested against real preferences. A negative or null result on real labels remains fully possible.
- Gated-action handling (every payment or communication goal must carry an approval flag and never be auto-executed) needs its own test against the real approval path in `core/approvals.py`; not done.

## Follow-ups (not done)
- With the owner's consent, replace synthetic labels with her past accept/reject decisions, split train/test by time, and rerun. Until then do not cite these numbers.
- Test the approval flag on gated goals against `core/approvals.py`.

Reproduce: `python experiments/e3_goal_formation/run_experiment.py <out_dir>` (Python 3.12, about 1 s). Output: `results.json` (`synthetic_labels: true`).
