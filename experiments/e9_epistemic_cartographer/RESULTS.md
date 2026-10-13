# E9: Epistemic Cartographer (competence-boundary map)

Label: implementation plus a measured test on real data. The result is mostly negative. Source pin: atlas-ai main 05b16994 / 4f68f54 (new files only, apply-checked). Python 3.12.14, scikit-learn and numpy current as of 2026-10-13; tests and every number below come from this 3.12 run (earlier 3.10 numbers were superseded because one estimator was unseeded).

Idea tested: an explicit map over input regions recording where an ensemble is reliable, where members disagree, where confident consensus contradicts the label, which regions fail together, and how little the map knows about each region (`cartographer.py`; `Cartographer.describe()` prints the map). Question: does it predict failures on unfamiliar tasks better than ordinary confidence/calibration baselines, and does using it improve label allocation.

## Setup
- Data: 20 Newsgroups, headers/footers/quotes removed; the train/test split is chronological, so test docs are time-shifted. Real models: LR, ComplementNB, LinearSVC (tf-idf), kNN and ExtraTrees (SVD), trained per task on 30/60/100/150 labelled docs.
- 20 categories split by a seeded permutation into 14 familiar and 6 novel. 60 familiar tasks (3-5 categories) build the map. Unfamiliar: A = 30 new combinations of familiar categories, B = 30 tasks with 1-3 novel categories. Map-building and scoring test docs are disjoint halves. Map embedding and 60 regions are fit on familiar-category train docs only. Map statistics used to train predictors are out-of-fold by document.
- Predictors, same GBM settings, no tuning on unfamiliar tasks: calibrated confidence (isotonic), logistic and GBM on item features (confidence, margin, entropy, member disagreement, kNN distance to labelled docs, length, budget, k), map-only GBM, Cartographer = item GBM + map features, shuffled-region control, three ablations.
- Metric: AUROC per task, mean over tasks, bootstrap over tasks (2000 resamples), paired differences. Target: the ensemble prediction disagrees with the given label.
- Everything was fixed before scoring except one rule: the "confident consensus contradicts the label" threshold. First run used max-prob over 0.9, which fired on 0.003% of items; it was changed to 0.5 (about 2%) after that, and everything was rerun. This was a post hoc change; it was made because the feature was empty, not tuned on outcomes. Run-1 failure-prediction numbers were close (cartographer minus item GBM +0.005 on A, -0.002 on B).
- Reproducibility: `LinearSVC` had no seed in the first version; fixed (`random_state=seed`). `check_repro.py` re-ran 18 (task, budget) collections and compared to the stored records: errors, member agreement and per-model errors identical, float features within 2.6e-15 (max over the 18 runs, `repro_check.txt`; the script's pass bar is 1e-12 and it exits nonzero otherwise). The stored records it compares against are the builder's and are not shipped (about 15 MB), so an independent reader can regenerate them with `collect` and run the check only against their own records, not against mine. So collection is reproducible for all discrete outcomes; scoring numbers can move in the last decimal with BLAS/library versions (an independent 3.12 replay agreed to about 0.001: A all +.0059, B all -.0030).

## Results (failure prediction, `results_failure_prediction.json`)
AUROC, task-macro, A = new combinations of familiar categories, B = tasks with novel categories, "all" = pooled over the four budgets.

| Predictor | A 30 | A 100 | A all | B 30 | B 100 | B all |
|---|---|---|---|---|---|---|
| calibrated confidence | .771 | .820 | .807 | .792 | .851 | .832 |
| item GBM | .803 | .826 | .822 | .831 | .856 | .852 |
| map only | .708 | .755 | .752 | .668 | .722 | .723 |
| Cartographer (item + map) | .807 | .830 | .827 | .826 | .853 | .849 |
| shuffled-map control | .805 | .828 | .824 | .832 | .854 | .852 |

| Claim | Status |
|---|---|
| Cartographer beats calibrated confidence: A +0.036 / +0.011 / +0.020 (30 / 100 / all), CIs exclude 0; B +0.034 / +0.002 / +0.017 (100-label CI includes 0) | VERIFIED |
| Most of that gain is item-level features, not the map: the item GBM alone is +0.033 / +0.006 / +0.015 over calibrated confidence on A | VERIFIED |
| Map adds over the item GBM on A: +0.0055 all budgets (CI +0.0027 to +0.0080); +0.0044 at 100 labels; +0.0036 at 30 labels (CI includes 0). Over the shuffled-map control: +0.0030 all (CI +0.0012 to +0.0048), +0.0016 at 100 (CI includes 0). Real but very small | VERIFIED, scoped to this corpus and these 5 models |
| Map does not help on tasks with novel categories (B): point estimates -0.005 / -0.003 / -0.004 vs item GBM (CIs include 0 at 30 and 100 labels; pooled interval -0.0066 to -0.0003, so worse than the item GBM on B pooled in this run; an independent replay gave -0.0030 [-0.0064, +0.0005], which crosses zero). No gain on B in either run. Calibration is worse on B (ECE 0.032 vs 0.015 pooled) | VERIFIED (no gain; slightly worse pooled in this run, borderline across replays) |
| Map alone (no item features) is much weaker than plain confidence: .75 / .72 vs .81 / .83 | VERIFIED |
| Which map components matter: removing co-failure smoothing, per-region model routing, or the label-contradiction features moves AUROC by at most about 0.003 either way, inside the noise | NOT SHOWN: no component is demonstrated necessary |
| Task difficulty (60 unfamiliar tasks, 100 labels, Spearman with true task error): Cartographer 0.79 (CI 0.64 to 0.88), item GBM 0.83, member disagreement 0.84, max-prob 0.63. The map is not better than the baselines | VERIFIED |
| Map coverage score (distance to region centroid) predicts task difficulty | NOT SUPPORTED: Spearman -0.14, CI -0.39 to 0.13 |
| Label-contradiction rate of a region identifies unreliable evaluation: among failing items, against near-duplicate text carrying another category label (89 of 8346 failures), AUC 0.40, below chance | NOT SUPPORTED (weak external ground truth; the feature is a proxy, not a validated label-error detector) |
| The map predicts failures on unfamiliar tasks better than ordinary confidence baselines | PARTIAL: yes versus calibrated confidence; versus a feature-rich item GBM only a +0.005 gain on recombined familiar categories and none on novel categories |
| Learning allocation: map-guided labelling vs random, uncertainty, committee, item-GBM, shuffled-map control | PARTIAL, see below |
| Generalises to other corpora, neural models, or non-text data | UNVERIFIED (one corpus, one split seed, one model zoo) |

## Allocation test
Code is in `ec_run_experiment.py alloc` (8 strategies, 60 unfamiliar tasks, pool of 1200 train docs, 30 random labels then +30 per round to 150, accuracy on the held-out eval docs, paired bootstrap over tasks). A full run finished once earlier under Python 3.10 before the SVC seeding fix; it showed every failure-targeted strategy, map-guided included, ending below random selection (map-guided about -0.04 accuracy at 150 labels vs random, CI excluding 0), and the map-guided batch strategy with regional quotas above item-GBM by about +0.010 and above the shuffled-map control by about +0.006 (area under the learning curve). That run is not shipped as evidence: it predates the fix and was not replayed. A regenerated 3.12 run was started at 13:12 IST (about 45 min); `results_allocation.json` appears only if it finishes. Until then the allocation claim is UNVERIFIED.

## Prior art and novelty
No novelty claim. Error-slice discovery, selective prediction, uncertainty meta-models and active learning all exist. The only candidate novel parts here, co-failure smoothing and per-region model routing, showed no measurable effect.

## Run
```
pip install scikit-learn pytest scipy joblib pandas numpy
python -m pytest -q experiments/e9_epistemic_cartographer/test_cartographer.py      # 13 passed, Python 3.12.14
python experiments/e9_epistemic_cartographer/ec_run_experiment.py collect              # ~2 min on 2 cpus
python experiments/e9_epistemic_cartographer/ec_run_experiment.py fail                 # ~2 min
python experiments/e9_epistemic_cartographer/check_repro.py ~/e9_work               # reproducibility check
python experiments/e9_epistemic_cartographer/ec_run_experiment.py alloc                # ~45 min
```
Needs ~1.5 GB free RAM; run stages one at a time (the fail stage was OOM-killed once when run beside another job in 2 GB). Files: `data.py`, `zoo.py`, `collect.py`, `cartographer.py`, `ec_run_experiment.py`, `check_repro.py`, `test_cartographer.py`, `tasks.json`, `results_failure_prediction.json`, `repro_check.txt`.
