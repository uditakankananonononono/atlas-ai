# E6: candidate causal models and information-value experiment choice (directions 2 and 5)

Label: replication of Bayesian optimal experimental design on an authored synthetic world. Not novel (Lindley 1956 expected-information-gain design; cost-weighted variants are standard). Source pin: atlas-ai main f7ae6fe7 (new files only), Python 3.12.14, numpy.

Setup: hidden world y = gate(x_i, x_j) over 5 binary inputs, 6 gates, 120 candidate causal models collapsing to 70 behavioral classes. Agent keeps a posterior, picks an intervention among 32 settings (costs 1 to 5, drawn per world), sees y with 10% flip noise, stops at posterior 0.9 on one class. Policies: random, eig (expected entropy reduction), eig_cost (EIG divided by cost). Every class is the hidden world, 3 seeds each: 210 runs per policy, 630 rows (`rows.jsonl`, `analysis.txt`, `run.py`). Data statement: every world, cost and noise level is authored for this experiment. The bootstrap treats the 210 runs per policy as independent although the 3 seeds of a world share one cost vector, so the intervals are slightly optimistic.

| Claim | Status |
|---|---|
| Mean total experiment cost to reach posterior 0.9: random 62.03, eig 34.45, eig_cost 20.91 | VERIFIED |
| Cost difference vs random: eig -27.58 (bootstrap 95% [-31.31, -23.85]); eig_cost -41.12 ([-45.00, -37.48]); eig_cost vs eig -13.54 ([-14.82, -12.28]) | VERIFIED |
| Mean experiments run: random 20.87, eig 11.34, eig_cost 12.93 | VERIFIED |
| Identification accuracy at the stop rule: random 0.962, eig 0.943, eig_cost 0.952; the differences are within run-to-run noise at 210 runs and no accuracy gain is claimed (all runs converge; the 0.9 stop rule allows about 5% wrong) | VERIFIED |
| Choosing the discriminating experiment and discarding models on evidence cuts cost on this synthetic family | VERIFIED |
| The engine learns how to investigate a new scientific domain, or helps on a domain whose model family is not enumerable | UNVERIFIED |
| The result holds when the hidden mechanism is outside the candidate set, or for continuous or larger models | UNVERIFIED |
| Any part of this is a new method | UNVERIFIED |

Failure notes: accuracy is not improved by the information-based policies, only cost. The candidate set contains the truth by construction, so the hardest part of the direction (proposing the right model family) is not tested.
