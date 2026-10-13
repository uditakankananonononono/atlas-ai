# Atlas E10: Solve / Critique / Redefine with independent metric admission

Date: 2026-10-13. CPython 3.12.14, standard library only, no paid tools.
Main source pin: `4f68f54a0d0742982192aa643c2fa92d61437c9b`.

## Main result

The previous evaluation gave all 13 candidate policies perfect scores on
nominal unit-weight chain graphs. It missed weighted shortest-path failures.
The critic proposes independently justified invariance dimensions, a separate
validator admits a dimension only if it predicts independent correctness risk,
and selection uses it without changing the externally specified objective.

| Seed | Old selection error | Redefined selection error | Oracle-baseline error | Admitted dimension | Corrected p | Deployment AUC |
|---|---:|---:|---:|---|---:|---:|
| 11 | 29.5% | 1.0% | 1.0% | relabel | 0.0016 | 0.975 |
| 23 | 22.5% | 1.0% | 0.0% | relabel | 0.0026 | 1.0 |
| 47 | 33.0% | 0.0% | 0.0% | relabel | 0.0010 | 1.0 |
| 83 | 21.5% | 0.0% | 0.5% | relabel | 0.0082 | 0.9375 |
| 131 | 30.0% | 0.0% | 0.0% | relabel | 0.0024 | 1.0 |
| Mean | 27.3% | 0.4% | 0.3% | | | |

This beats only the authored inadequate nominal evaluation. It does not beat the
strong external-oracle baseline, invent the metric catalogue, or demonstrate
general open-ended intelligence. The expected result is meaningful evaluation
repair plus a measured warning about metric transfer, not a novelty claim.

| Claim | Status | Evidence |
|---|---|---|
| Previous nominal metric missed real weighted-graph weakness | VERIFIED | All candidate nominal errors 0; held-out BFS errors 21.5%-33% |
| Independent semantic justification | VERIFIED | Relabel preserves the graph up to isomorphism; subdividing an edge preserves every path's cost; positive scaling preserves optimum; disconnected component cannot affect reachability |
| Metric predicts separately measured risk in this catalogue | SCOPED | Independent Bellman-Ford validation, deployment AUC 0.9375..1.0, five seeds |
| No points awarded for proposing a metric | VERIFIED | Gate uses external oracle errors; metric is not deployment reward |
| Uninformative constant metric refused | VERIFIED | Five controls, AUC 0.5 and p 1 |
| Independent-policy-family transfer is reliable | PARTIAL | Transfer AUC 0.75, 1, 1, 0.5, 0.75; one chance result |
| Invariance implies correctness | PARTIAL | Falsified: always-zero policy has 0 invariant violations, 100% external errors |
| Outperforms strong oracle evaluation | PARTIAL | Not supported: mean error 0.4% vs 0.3% oracle baseline |
| Autonomous metric invention / open-ended intelligence | PARTIAL | Authored four-dimension catalogue and finite policies; no new metric language learned |
| Atlas production integration | PARTIAL | Standalone callable code only, no service changes |

## Separation of roles and information

All graphs and solver variants are **experimenter-authored synthetic**. No
LLM-generated authenticity or human benchmark claim. Catalogue: two BFS edge-order
variants, six inadmissible label-distance heuristics (parameters 1,2,4,8,16,32),
four quantized priority solvers (2,4,8,16), exact Dijkstra.

For each of five seeds, task identifiers are disjoint:
- Solve: 60 nominal tasks. The old selection chooses first highest-accuracy
  policy, a fixed tie-break set before scoring.
- Critique: 60 weighted tasks, without correctness answers given to critic.
  Four authored transformations produce violation-rate metrics.
- Independent validator: 120 different weighted tasks. Bellman-Ford measures
  errors, labels risk as error >10%, and checks predictive AUC. Metric must have
  AUC >=0.75 and max-statistic familywise permutation p <=0.05 (4,999 shuffles).
- Redefine: among nominally tied candidates, choose lowest violation rate of
  admitted metric. If none admitted, retain old selection. No threshold tuning.
- Deployment: 200 unseen weighted tasks. Only external Bellman-Ford error counts.
- Strong baseline: choose lowest error on independent validator tasks.

Transformation seeds are `900000+index` and repeat across every experiment
seed and candidate policy. Graphs differ, but transformation randomization is
not independent across experiment seeds; the repeated schedules are a caveat.

The critic never reads deployment outcomes or writes an external correctness
rule. These are software boundaries inside one process, not an adversarial
security boundary. Validation labels from multiple variants of the same
algorithm are correlated; policy-level permutation p-values are **descriptive
for this authored catalogue, not population significance**. Seeds do not remove
corpus-authorship bias. Protocol was written before first run but not externally
preregistered. Metric and graph authorship share one experimenter.

## Important failures and transfer control

`family_holdout.py` admits a metric on 12 heuristic/quantized policies, then
predicts errors on unseen BFS and Dijkstra families. All seeds select subdivision
on the proposal catalogue (tie-breaking is fixed lexicographically), but transfer
AUCs are 0.75, 1.0, 1.0, 0.5, 0.75 across just three transfer policies
(two risky BFS policies, one correct Dijkstra policy), so possible AUC values
are only 0.5/0.75/1.0 here. The holdout admits subdivision while the main run
admits relabel; it is not a direct transfer test of the main admitted metric. At seed 83 both wrong BFS policies have zero
violations and 25%-29.5% errors. This is a real failure, not excluded.

An adversarial always-zero policy has **zero** relabel/subdivision violations
and **100%** external errors. It passes the semantic consistency metric while
being useless. New dimensions remain diagnostics, never substitutes for the
independent success objective. Even a metric admitted for one population can be
blind to a new policy family. This also means the positive main result is scoped
to that policy catalogue.

## Prior art

- POET already coevolves challenges and solutions:
  https://arxiv.org/abs/1901.01753
- Metamorphic testing already uses transformations to expose test weaknesses:
  https://vuir.vu.edu.au/36919/ (2018 review metadata; full text unavailable there)
- Hidden incentives under distributional shift:
  https://arxiv.org/abs/2009.09153

This is an executable combination/control study, not a claim of originality.
Full general-purpose open-ended processes with autonomously proposed dimensions,
independent justification, new policy families and external evaluator custody
remain unfinished. No improvement over POET or existing metamorphic-testing
systems has been measured.

## Replay

```sh
python3.12 -m unittest discover -s experiments/e10_metric_critique -p 'test_*.py' -v
python3.12 experiments/e10_metric_critique/run_experiment.py --output /tmp/e10-replay.json
diff -u experiments/e10_metric_critique/results.json /tmp/e10-replay.json
python3.12 experiments/e10_metric_critique/family_holdout.py
```

Six unit tests pass. They include independent solver/oracle agreement,
transformation correctness, missing weighted weakness, fail-closed admission,
unreachable paths, and the invariant-but-wrong adversary. Outputs include every
policy score, gate decisions, corrected p-values, external errors and controls.
Exact bytes for `results.json` require CPython 3.12.14 because version is recorded.
`family_holdout.py` writes its committed evidence path; run in an isolated
checkout if you need to preserve an untouched tree. `experiments/e9_formalism/replay.sh` instead
checks all three evidence artifacts without overwriting them.
