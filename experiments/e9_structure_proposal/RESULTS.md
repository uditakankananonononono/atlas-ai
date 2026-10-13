# Atlas E9: observation-conditioned program proposals plus E6 information gain

Date: 2026-10-13. Overall direction-2 status: PARTIAL. This implements structural
program proposals rather than taking a supplied list of candidate worlds. It does
not discover an unknown modeling language, latent graph, or arbitrary scientific
mechanism. No novelty or AGI claim. All data, worlds, costs and noise are authored
synthetic data, not external scientific observations.

## What changed from E6

E6 receives a complete enumerated family of 70 behavioral classes. E9 receives
only observation pairs and an explicit Boolean language: five binary inputs,
constants, negated input literals, AND/OR/XOR, at most two binary nodes. It builds
syntax bottom-up, uses history to select a 48-element per-size intermediate beam,
then forms an observation likelihood over the generated behavioral classes. It
rebuilds this proposal set after every measurement, not from an oracle registry.
The unmodified `experiments/e6_world_model_info_value/engine.py:eig` computes EIG.
Hidden truth outputs reach `learn` only as the initial observation values and
subsequent measurement callback replies. Randomization seeds, costs and initial
input settings are generated before reading any world, by a separate run-count-
only schedule. They are not functions of the table or its hash. A truth-label
permutation test captures all non-observation learner inputs and verifies they
remain identical; with observation values/callback replies held fixed, the learner
returns identical queries and outputs under those permutations. This proves the
tested interface invariance, not statistical independence from finite samples.
 The benchmark
scores predictions against truth after learning finishes.

The full grammar contains 1,252 distinct truth tables, requiring 4,044 generated
expression evaluations per synthesis pass. The empty-history beam generates 809
classes with 2,172 evaluations. These are tiny, fully enumerable spaces. The
grammar is still a known hypothesis-family assumption. This moves one step beyond
E6's list lookup, but does not solve open-ended family invention.

## Protocol

Fixed protocol: beam=48, depth bound=two binary nodes, four
initial unbiased input observations, 12-query budget, uniform behavioral-class
prior. No model trained or hyperparameter selected on development or heldout rows.
Clean suite: 100 unique three-input composed mechanisms, generator seed 73; hash
of the behavioral table separates 21 development from 79 heldout worlds. Three
seeds per world. Development and heldout do share the grammar and generator:
this is world-level holdout, not out-of-distribution generalization.

Four paired controls: beam+random, beam+EIG/cost, exhaustive+random,
exhaustive+EIG/cost. Exhaustive regenerates the finite grammar with no intermediate
pruning. All have the same query cap and initial observations. Costs are [1,5),
shared per world. E6's costs, selector and binary flip-noise model are retained.
Unlike E6's confidence stop, E9 has a fixed query budget: conditional confidence
from an incomplete beam cannot justify global certainty. Clean random selects
unmeasured settings without replacement; noisy random permits repeats. Initial
observation cost is excluded equally. Unused queries are not charged when the
proposal set rejects the world. Thus cost savings alone are not success.

Intervals below resample whole worlds, averaging seeds within each world, with
2,000 paired bootstrap samples. They address shared-world dependence rather than
E6's independent-seed bootstrap. They are descriptive intervals for this small
synthetic generator, not proof of broad generalization.

## Clean heldout results: 79 worlds, 237 rows per policy

| Policy | Exact identification | All-32-input accuracy* | Query cost | Queries | Search evaluations | Rejected |
|---|---:|---:|---:|---:|---:|---:|
| beam+random | 74.26% | 91.93% | 35.10 | 11.82 | 27,851 | 5.06% |
| beam+EIG/cost | 94.09% | 94.46% | 28.69 | 11.76 | 27,704 | 5.49% |
| exhaustive+random | 79.32% | 96.94% | 35.57 | 12.00 | 52,572 | 0% |
| exhaustive+EIG/cost | 100% | 100% | 29.43 | 12.00 | 52,572 | 0% |

*Rejections count as zero accuracy, not 50% or missing rows. These 32 inputs
include the measured settings: this is full-domain prediction, not input holdout.

| Claim | Status | Evidence / restriction |
|---|---|---|
| Structures are generated from observations without passing the hidden model list to the learner | VERIFIED, SCOPED | inspect engine.py, no-world-import/interface tests, changing-observations test; language is supplied |
| Reuses exact E6 EIG | VERIFIED | import and known-discriminating-setting test |
| Beam+EIG improves exact identification over beam+random by 19.83 percentage points | VERIFIED, SCOPED | paired world-cluster 95% CI [14.35,25.74] points; clean authored heldout worlds only |
| Full-domain predictive accuracy improves over beam+random | PARTIAL | +2.53 points, CI [-0.95,5.86]; interval includes zero |
| Beam+EIG uses 6.41 less query cost than beam+random | VERIFIED, SCOPED | CI [-7.23,-5.70]; rejection can shorten runs, so not a same-success-threshold cost claim |
| Beam matches exhaustive+EIG | PARTIAL, negative | beam loses 5.91 identification points, CI [-10.55,-2.11] |
| Beam reduces generated-expression evaluations relative to exhaustive+EIG | VERIFIED, SCOPED | -24,868, CI [-25,353,-24,483]; no wall-time claim or common total-compute budget |
| Finite grammar can be invented, unknown families recovered, or latent DAGs identified | PARTIAL, not demonstrated | known bounded program grammar and direct input-output interventions only |
| Novel method or AGI | PARTIAL, not demonstrated | related active synthesis/causal design literature predates this experiment |

## Noise and misspecification stress tests

At 10% independently sampled output-flip noise: 40 worlds, two seeds, 33 heldout
worlds (66 rows/policy). Beam+random identifies 18.18%, beam+EIG 54.55%,
exhaustive+random 22.73%, exhaustive+EIG 51.52%. Beam+EIG minus beam+random is
+36.36 points, CI [22.73,50.00], but absolute identification remains poor at this
short budget. Its predictive accuracy is 90.15% vs random 80.49%. No robust-noise
claim: the noise rate is known, and posterior calibration is untested.

Out-of-grammar signed three-input majority circuits: 20 worlds, two seeds,
19 heldout worlds. Every policy identifies 0%. Beam+EIG rejects 57.89% of heldout
runs, exhaustive+EIG 52.63%. The remainder return wrong in-grammar predictions.
A zero surviving set detects some misspecification; a nonempty set does not
certify that the mechanism is in the language. Rejection also does not distinguish
misspecification from beam pruning. Full 32-setting evidence rejects the tested
majority example even under exhaustive search. No query-cost gain in this suite
is interpreted as successful discovery.

## Failures and next work

- Beam ranking judges intermediate expressions as if they were final outputs.
  This can discard a useful subexpression and later exclude a realizable truth.
- Rebuilding the beam changes the candidate universe. Reported confidence is
  conditional on current proposals, not a coherent global Bayesian posterior.
- The entire 32-input behavior of each *hypothesis* is evaluated to deduplicate
  programs. It never queries unobserved *truth* values, but does rely on a fully
  executable, tiny hypothesis language.
- No structural equivalence or hidden circuit topology claim: equivalent
  programs collapse by truth table; this measures behavior, not original syntax.
- No free-form grammar invention, continuous variables, confounding, latent
  causes, real-data validation, larger circuits or external model proposer.
- Expression counts exclude EIG, sorting and likelihood costs. No claim that
  beam wins at equal end-to-end compute or wall time.
- Next real step: reserve diverse structural proposals independent of output-fit
  and track alternative grammars; evaluate unknown operators and new variables.
  This remains future work, not a delivered capability.

## Replay

Base: atlas-ai main 4f68f54a0d0742982192aa643c2fa92d61437c9b. Requires
`experiments/e6_world_model_info_value`, already on main, because its EIG selector
is imported unchanged. E9 adds only its own directory; no application runtime wiring.
Python 3.12.14; numpy 2.5.4; pytest 9.1.1. Commands from repository root:

```sh
python3.12 -m venv .venv-e9
.venv-e9/bin/python -m pip install -r experiments/e9_structure_proposal/requirements.txt
.venv-e9/bin/python -m pytest -q experiments/e9_structure_proposal/test_structure_engine.py
.venv-e9/bin/python experiments/e9_structure_proposal/run.py --output /tmp/e9-clean
.venv-e9/bin/python experiments/e9_structure_proposal/run.py --output /tmp/e9-noisy --worlds 40 --seeds 2 --noise .1
.venv-e9/bin/python experiments/e9_structure_proposal/run.py --output /tmp/e9-outside --worlds 20 --seeds 2 --outside
.venv-e9/bin/python experiments/e9_structure_proposal/audit.py --suite clean
.venv-e9/bin/python experiments/e9_structure_proposal/audit.py --suite noisy
.venv-e9/bin/python experiments/e9_structure_proposal/audit.py --suite outside
```

19 tests pass, including exact-reuse, observation-conditioning, deterministic
replay, full evidence, metric/cost recomputation, split separation and invalid
inputs, plus truth-label permutation/interface invariance. All 1,680 result rows were rebuilt byte-identically by audit.py. Result-file SHA256:

- clean: 65b68d56548fa1f64a27f5f79556f630b608312068f9707dff6a49c82a391a9d
- noisy: 3189327de29922f2103136a5d62416c3b78c129b22b0995e6f07f7274ea4f7bb
- outside: 18d56c622a4a7557176b04e630d32b1d3d1bc1aa5bf9a9ef86756ff568473085

Prior-art sources and their relation are in PRIOR_ART.md. VERIFIED denotes implementation/result verification in this bounded synthetic
suite, not general-science verification.
