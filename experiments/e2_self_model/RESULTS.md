# E2: can a self-model predict whether a module's own tests catch a change?

Source pin: atlas-ai commit ef1f6af; collect.py rerun on a checkout of 8a79fc4 plus the E3 landing commit 4203b988 (not a pristine 8a79fc4 run): same 335 generated rows, 212 killed, 0 invalid, and identical rows after sorting by (module, old, new, killed, invalid); original file order differs. The old/new text in mutants.jsonl is truncated and the line number is the first matching line, so the rows verify rerun equality only; they do not identify each mutation site or rule out duplicate generation. Treat 335 as generated rows, not 335 distinct mutants. Metric recomputation with analyze.py on the supplied mutants file reproduced the all-feature Brier 0.1807485, ECE 0.0731921, AUC 0.7627895 and bootstrap CI [-0.116893, -0.078401]. This recomputed metrics from the retained file; it did not re-execute the mutations. Python 3.12.14, pytest 9.1.1, run with `--noconftest`.

Task: before running anything, predict whether a one-line mutant of a `backend/app/self_improve/*.py` module is killed (some test fails) by that module's own test file(s). Ground truth: 335 generated mutant rows from the frozen E5 generator (`experiments/e5_gate_quality/mutants.py`) over 9 modules that have a dedicated test file and a passing unmutated baseline (codegen, detector, engine, improvement_gate, mixin, planner, registry, sandbox, self_eval). Excluded for lack of a dedicated test file: events, gate, plans, safety, testsynth. Predictors use static features only (operator kind, line kind, whether the enclosing function name appears in tests, module test-LOC/module-LOC ratio). Logistic regression, leave-one-module-out cross-validation, so every test module is unseen. Paired bootstrap (2000x over rows) for Brier minus base rate. Deterministic, no seeds.

Invalidated first attempt: an earlier collection run reported every mutant killed because the scratch copy lacked `app.modules` and pytest failed at import. That data was discarded. The collector now requires a passing unmutated baseline per module and excludes any pytest exit code other than 0 or 1 (0 invalid in the final run).

## Results

| Claim | Status |
|---|---|
| 335 generated mutant rows, 0 invalid, 63.3% killed overall; per-module kill rate ranges 0.18 (codegen) to 0.95 (improvement_gate) | VERIFIED |
| Base-rate predictor Brier 0.279 | VERIFIED |
| Mutant-level static features only (operator, line kind, function-in-tests) do not beat the base rate: Brier 0.282 (op), 0.264 (op+line+fn); bootstrap 95% interval for the difference includes zero for both | VERIFIED |
| A single module-level feature (test LOC / module LOC) gives Brier 0.184, interval for difference from base [-0.111, -0.079] | VERIFIED |
| All features together: Brier 0.181, calibration error 0.073 (base rate 0.343), AUC 0.76; no better than the module-level feature alone (0.184) | VERIFIED |
| The predictive signal comes from module-level test density, not from anything about the individual change | VERIFIED |
| The test-density relationship rests on 9 modules; one exception is detector (ratio 0.84, kill rate 0.24) | VERIFIED |
| Two modules with the highest ratios (improvement_gate, self_eval) are the gate code whose tests were written around mutation evidence, which may confound the ratio effect | UNVERIFIED |
| The predictor is usable for routing or for deciding which changes need extra review | UNVERIFIED |
| The result holds for modules outside self_improve or for other generators of mutants | UNVERIFIED |
| AUC for the base-rate predictor (0.148) means anything | UNVERIFIED |

## What failure showed
1. The hypothesis "a predictor beats base rate on unseen probes" holds only through one coarse module-level number. A per-change self-model built from the features tried here adds nothing detectable.
2. The base-rate AUC below 0.5 is an artifact of leave-one-module-out (a held-out high-kill module lowers the training mean); ignore it.
3. Self-report here means predicting this repo's own test outcomes. It is not a claim about awareness or general self-knowledge.

## Follow-ups (not done)
- Real coverage per line (a covered-by-tests flag) as a feature; it is the obvious missing signal and needs coverage tooling in the scratch copy.
- More modules (the other 5 need dedicated tests first) so the 9-point relationship can be checked.
- Abstain analysis: how often declining the low-confidence tail avoids wrong predictions.

Reproduce (Python 3.12 with pytest, numpy, sqlalchemy, fastapi, httpx): `python experiments/e2_self_model/collect.py <out>` (~8 min), then `python experiments/e2_self_model/analyze.py <out>`. Per-mutant data: `mutants.jsonl`; metrics: `results.json`.
