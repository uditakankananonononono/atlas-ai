# E9 v2: skill genome (Direction 4)

Supersedes v1 (`RESULTS_V1.md`, independently audited: numbers byte-identical on Python 3.12; audit corrections applied there). v1 code is frozen; v2 adds `tasks2.py`, `agent2.py`, `run_v2.py`, `analyze_v2.py`, `tests/test_e9_v2.py`. Prior art and the no-novelty statement: `PRIOR_ART.md`. SYNTHETIC authored domain throughout (29 base ops, 10 authored themes). No novelty claim.

## Run commands (Python 3.12 verified via uv; stdlib only)
```
cd experiments/e9_skill_genome
uv run --python 3.12 python -m unittest discover -s tests     # 16 tests (v1 + v2), ~1 s, passes on 3.10 and 3.12
python run_v2.py 20 1500 results_v2_B1500.json                # ~6 min, 2 cores
python run_v2.py 20 500 results_v2_B500.json ; python run_v2.py 8 5000 results_v2_B5000.json
python run_v2.py 3 20000 results_v2_B20000.json nolib,admit_all,joint_audit
python run_v2.py 20 1500 results_v2_abl_B1500.json gated,gated_no_rewrite,gated_no_combine
python analyze_v2.py                                          # -> analysis_v2.txt ; ablation: analysis_v2_ablation.txt
```
CI note: RESULTS CIs were copied from analysis runs whose bootstrap draws depended on call order and can differ from `analysis_v2.txt` by about 0.001-0.002; analyze_v2.py now reseeds per call, and analysis_v2.txt is authoritative. `python analyze_v2.py` also writes the ablation report (analysis_v2_ablation.txt).

Replay: seed 0 at budget 1500 re-run on Python 3.12 gave identical curves and libraries to the 3.10-produced results file.

## What changed vs v1 (fixes for audit findings, plus the requested gaps)
- Test and validation are exactly stratified: 20 test tasks per category x 4 categories = 80 per seed; 10 per category = 40 validation. Categories: `seen_full` (theme as in acquisition), `seen_extraA` (theme + extra op from pool A, the only extras acquisition uses), `seen_extraB_heldout_sampling` (the extra op is drawn from pool B, which acquisition tasks never sample as their extra op; the primitives themselves are NOT unseen: six pool-B ops (drop1, halve, mod5, mul2, sq, take3) occur inside acquisition themes, so only the extra-op sampling is held out and exact-pipeline reuse is not by construction), `novel_theme` (themes 7-9).
- Per-task random hidden inputs (two random edge cases per task, no fixed shared probes). Disjointness now on full signature (target, train inputs, hidden inputs) and no train-example input shared between test and acquisition/validation (asserted in tests). This is still a narrow split: same theme families except `novel_theme`; it is not an unseen-skill-family benchmark.
- Random-library control has exactly the matched condition's size (empty when that library is empty).
- Batch/joint admission (`joint_audit`): candidates pool for 20 tasks, the pool (cap 20) is gated as a SET (admit only if the whole set gains >= 2 validation tasks), then backward elimination drops members whose removal does not lower validation solved count. Retirement audit every 40 tasks: leave-one-out on validation, retire skills whose removal does not hurt.
- Ablations separate rewrite from combine. Budgets 500, 1500, 5000, 20000.
- Validation tasks are REUSED adaptively for every gate/elimination/audit decision (possible validation overfit, unmeasured). Validation now has the same category mix as test, which favours gating relative to v1. Test tasks are never used for decisions.

## Results (test solved-rate, mean over seeds, 95% bootstrap CI over seeds; full tables in analysis_v2.txt)

| Budget (seeds) | nolib | admit_all | gated (1-at-a-time, margin 2) | joint_audit | random same-size |
|---|---|---|---|---|---|
| 500 (20) | 0.021 | 0.169 [0.139,0.199] | 0.294 [0.270,0.319] | 0.299 [0.274,0.325] | 0.016 |
| 1500 (20) | 0.069 | 0.304 [0.275,0.334] | 0.298 [0.258,0.336] | 0.329 [0.289,0.369] | 0.029 |
| 5000 (8) | 0.183 | 0.398 [0.366,0.436] | 0.350 [0.305,0.392] | 0.353 [0.334,0.370] | 0.044 |
| 20000 (3; nolib/admit_all/joint only) | 0.421 | 0.413 | not run | 0.525 | 0.392 |

Per category at 1500: nolib 0.170/0.062/0.015/0.030 (seen_full / extraA / extraB heldout-sampling / novel); joint_audit 0.547/0.357/0.367/0.043; admit_all 0.472/0.388/0.350/0.005.

Paired differences, all test tasks (mean [CI], seed wins/ties/losses):
- Libraries vs nolib: at 500, 1500, 5000 every learned condition is above nolib on all or nearly all seeds (e.g. 1500 joint_audit +0.259 [+0.216,+0.299] 20/0/0; 5000 gated +0.167 [+0.123,+0.202] 8/0/0).
- Learned vs same-size random library (random is itself below nolib): joint_audit +0.299 [+0.258,+0.339] at 1500 (20/0/0); +0.309 [+0.286,+0.333] at 5000.
- gated - admit_all: 500 +0.126 [+0.097,+0.156] 20/0/0 (admit_all collapses at low budget: 40 skills eat the search budget); 1500 -0.006 [-0.043,+0.029] 10/1/9; 5000 -0.048 [-0.094,-0.003] 3/0/5.
- joint_audit - gated: 500 +0.004 [-0.022,+0.031]; 1500 +0.031 [-0.009,+0.073] 12/1/7; 5000 +0.003 [-0.036,+0.039]. Joint admission does NOT reliably beat one-at-a-time. (This comparison also adds the retirement audit to the joint arm; `gated_audit - gated` is about 0, so the joint effect is not confounded in a way that matters, but it is not a pure joint-only comparison.)
- joint_audit - admit_all: 500 +0.130 (19/0/1); 1500 +0.025 [-0.013,+0.062]; 5000 -0.045 [-0.084,-0.014] 1/0/7; 20000 (3 seeds) +0.112 [+0.037,+0.162] 3/0/0.
- Audit alone: gated_audit - gated -0.001 [-0.009,+0.006] at 1500 (15 of 20 seeds tied); retired 0.4 skills/seed. Retirement is a near no-op here.
- Ablation (1500, 20 seeds): removing rewrite costs -0.076: gated - gated_no_rewrite +0.076 [+0.038,+0.112] 17/1/2. Removing combine changes nothing at 1500: 0/20/0 (no combined skill admitted at 1500 or 5000; one combined admission across 20 seeds at 500, not ablated there). So the v1 "rewrite+combine" effect is attributable to rewrite in this domain.
- Harm outside the library's themes (novel_theme, paired vs nolib): 5000: admit_all -0.150 [-0.200,-0.094] 0/1/7, gated -0.106 [-0.144,-0.069] 0/1/7, joint_audit -0.100 [-0.144,-0.044] 1/0/7. 20000 (3 seeds): admit_all -0.383 [-0.450,-0.300] 0/0/3, joint_audit -0.017 [-0.050,0.000]. At 1500 and 500 the gated libraries are neutral to slightly positive (+0.005..+0.013), admit_all -0.025.

## Claims
| Claim | Status |
|---|---|
| Libraries acquired with no retraining raise solved-rate over no library, including on tasks whose extra-op sampling was not seen in acquisition (primitives themselves were seen; seen_extraB_heldout_sampling: 0.015 -> 0.367 joint_audit at 1500) | VERIFIED (this domain, budgets 500-5000; 20000 has 3 seeds) |
| Gain comes from the learned skills, not from library size: same-size random libraries do no better than nolib and are WORSE at every budget (1500: 0.029 vs 0.069; 5000: 0.044 vs 0.183; 20000, 3 seeds: 0.392 vs 0.421), so junk skills cost search budget | VERIFIED |
| Rewrite (counterexample repair) causally adds +0.076 under the gate; combine adds nothing | VERIFIED (ablation, 20 seeds) for this domain; combine's null may be domain-specific |
| One-at-a-time unseen-gain gate beats admit_all | PARTIAL / budget-dependent: wins at 500 (+0.126), ties at 1500, loses at 5000 (-0.048). v1's loss at 1500 did not replicate under v2's stratified validation (which mirrors test categories) |
| Joint (set-level) admission fixes the one-at-a-time gate's conservatism | FALSIFIED / not shown: +0.031 [-0.009,+0.073] at 1500, +0.003 at 500 and 5000 vs one-at-a-time |
| Retirement audit helps | NOT SHOWN: -0.001 [-0.009,+0.006]; mechanism works (retires 0.4-1.5 skills/seed) but changes accuracy by ~0 |
| Libraries are not free: at budget 5000, every library (admit_all, gated, joint) lowers novel-theme solve rate vs no library (-0.10 to -0.15, 7 of 8 seeds worse) I attribute this to library skills being tried first (budget use) but did not isolate it from changed first-fit and pruning behaviour (skills can also fit examples first, or be contract-pruned); the gate reduces but does not remove it | VERIFIED at 5000 (8 seeds); the gate does not protect out-of-theme tasks |
| At budget 20000 admit_all gains nothing overall (-0.008) and wrecks novel themes (-0.383); joint_audit +0.104 over nolib | SCOPED: only 3 seeds, CIs are descriptive, treat as indicative |
| Gains persist at larger budgets (e7's gains vanished) | PARTIAL: libraries still help at 5000 (+0.17..+0.22) but the gap over nolib shrinks (0.234 at 1500 -> 0.167-0.216 at 5000) and at 20000 only joint_audit is ahead (3 seeds) |
| Failure-case regression: a skill passing its own tests but failing unseen tasks is rejected by the gate | VERIFIED (unit tests: overfit [sort_desc,take3] passes own tests, fails 6/6 unseen; gate rejects; admit_all accepts; failure case recorded on use, deterministic task) |
| Rewrite fits train examples but can still fail hidden inputs | VERIFIED (test: 6 of 8 fixed rich tasks pass hidden, 2 do not) |
| Skills trusted "only if they improve unseen tasks" yields genuine skills | PROXY only: theme-aligned share is a label from my authored themes (e.g. joint_audit 3.7 of 6.4 skills at 1500); no direct measure of skill correctness |
| Generalises beyond this authored domain | UNVERIFIED |

## Limits
Authored synthetic domain; same theme families across acquisition/test except `novel_theme`; one hidden-input distribution; validation reused adaptively (not fresh per decision); 8 seeds at 5000 and 3 at 20000; `gated`, `gated_audit`, margin-1 not run at 20000 (cost); combined-skill tests are tautological snapshots; no admit_all+audit variant (cost); margin 2 fixed from v1 (margin 1 in v1 was post hoc and not repeated).
