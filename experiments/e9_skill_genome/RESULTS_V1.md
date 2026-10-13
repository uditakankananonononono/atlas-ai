# E9 v1 (superseded by RESULTS.md; kept for the audited numbers, with audit corrections applied)
# E9: skill genome (Direction 4). Do rewritten/combined/tested skills, trusted only on unseen-task gain, help without retraining?

Python: stdlib only. Developed and run on Python 3.10.12 (3.12 was not available in the build sandbox; no 3.11+ features used, but 3.12 replay is UNVERIFIED). pytest was not installable, tests use `unittest` (pytest also collects them).

## Run commands
```
cd experiments/e9_skill_genome
python -m unittest discover -s tests -v        # 10 tests, <1 s
python run_experiment.py 20 1500                # 20 seeds, search budget 1500; ~6 min on 2 cores; writes results.json
python analyze.py                               # writes analysis.txt
```
Replay check: seed 1 re-run under a different PYTHONHASHSEED gave identical curves and libraries to results.json.

## Setup (frozen before the 20-seed run, except where marked post-hoc)
- Domain (SYNTHETIC, authored by me): tasks map int tuples to int tuples. 29 base ops (`ops.py`). 10 authored "themes" (3-op pipelines, `tasks.py`); a task is a theme, theme + 1 random op, or first 2 theme ops + 1 random op (3-4 ops). Themes 0-6 appear in acquisition; themes 7-9 are novel and appear only in validation/test. Each task: 3 train examples, 12 hidden inputs. Half the tasks have "poor" train examples (distinct, non-negative: cannot reveal dedupe/abs behaviour), half "rich". Solved = the first pipeline that fits the 3 train examples also passes all 12 hidden inputs.
- Agent (`agent.py`): breadth-first pipeline search, observational-equivalence pruning, max 4 units, budget = unit executions (1500). Library skills are tried first. NOT the e7 DSL: e7's harness has no preconditions, contracts or failure cases, so it cannot host a genome. I kept its conventions where they carried over (budget in evaluations, solved = all held-out examples, no-library and same-size-random-library controls, held-out environment = novel themes, library promotion only on validation gain). This is a deviation from "reuse the harness", flagged.
- Skill genome (`genome.py`): `precondition` (flags nonneg/distinct/nonempty inferred from the inputs of its tests; checked on the actual input a skill receives), `procedure` (exec'd source text, restricted builtins), `expected` outputs (flags len_le/subset/sorted inferred from test outputs; checked at run time), `failure_cases` (counterexamples recorded when a pipeline using the skill fails), `tests` (verification I/O pairs).
- Operators: induce (flattened solved program with length >= 2), rewrite (single delete/insert/substitute edit fitting train examples plus the counterexample, after a failed task), combine (every 20 tasks, top-2 adjacent unit pairs, length 3-5; its tests are snapshots of its own procedure, so they are tautological).
- Acquisition: 120 tasks, environment returns pass/fail and one counterexample. No parameters are trained; the library is the only thing that changes (continual acquisition without retraining).
- Conditions: `nolib`; `admit_all` (admit anything that passes its own tests); `gated` (own tests pass AND net validation gain >= 2 tasks on 40 unseen validation tasks, themes 0-9); `gated_induced_only` (no rewrite/combine); `random_lib_same_size` (control: random 2-3 op skills, same size as the gated library, no preconditions); `gated_margin1_posthoc` (margin 1, added AFTER seeing a 2-seed pilot where margin 2 looked too strict; post-hoc, not the primary result).
- Test (a narrow split: signature-disjoint on target + train inputs only; hidden inputs share four fixed probe tuples across tasks; same theme families as acquisition except themes 7-9): 60 tasks per seed (themes sampled, not stratified: 37-47 seen-theme tasks and 13-23 novel-theme tasks per seed), generated from separate RNG streams; asserted signature-disjoint (target + train inputs) from acquisition and validation. Themes recur across sets by design, so "unseen" means unseen task instances, not unseen skill families, except the novel themes.
- 20 seeds; CIs are bootstrap over seeds (5000 resamples). Full output: `analysis.txt`, raw: `results.json`. v1 code (tasks.py, run_experiment.py, analyze.py) is frozen and unchanged; v2 lives in tasks2.py, agent2.py, run_v2.py, analyze_v2.py.

## Results (test solved-rate, mean [95% CI over 20 seeds], budget 1500)

| Condition | All | Seen themes | Novel themes | Library size (theme-aligned) |
|---|---|---|---|---|
| nolib | 0.059 [0.049,0.070] | 0.074 | 0.030 | 0 |
| admit_all | 0.271 [0.241,0.302] | 0.396 | 0.013 [0.000,0.031] | 59.8 (7.7, 13%) |
| gated (margin 2) | 0.209 [0.172,0.247] | 0.298 | 0.020 | 3.9 (2.2, 58%) |
| gated_induced_only | 0.141 [0.119,0.165] | 0.199 | 0.021 | 2.3 (1.6, 67%) |
| random_lib_same_size | 0.031 [0.016,0.047] | 0.032 | 0.027 | 3.9 |
| gated margin 1 (post-hoc) | 0.286 [0.256,0.315] | 0.416 | 0.021 | 7.8 (3.9, 49%) |

"Theme-aligned" = program is a contiguous >=2-op segment of a seen theme (label from my authored themes, used for evaluation only). Non-aligned skills are mostly task-specific full pipelines or overfit programs.

Paired differences, all test tasks (mean [CI], wins/ties/losses over seeds): gated - nolib +0.150 [+0.113,+0.190] 19/1/0; admit_all - nolib +0.212 [+0.181,+0.244] 20/0/0; **gated - admit_all -0.062 [-0.089,-0.030] 3/0/17**; gated - random_lib +0.178 [+0.138,+0.219] 19/1/0; gated - induced_only +0.068 [+0.041,+0.100] 16/4/0; margin1 - admit_all +0.015 [-0.016,+0.047] 11/1/8.

Learning curve (all test tasks, after 0/60/120 acquisition tasks): nolib 0.059/0.059/0.059; admit_all 0.059/0.252/0.271; gated 0.059/0.177/0.209.

Gate decisions pooled over 20 seeds (gated): 78 admitted (38 induced, 40 rewritten); 1561 rejected for no unseen gain (815 induced, 579 rewritten, 167 combined); 202 duplicates. Zero candidates failed own tests, so the own-test check never filtered anything.

## Claims
| Claim | Status |
|---|---|
| Skill libraries acquired without retraining raise test solved-rate over no library (gated +0.150, admit_all +0.212, 19-20 of 20 seeds) | VERIFIED (this synthetic domain, this budget) |
| Gain is specific to learned skills: same-size random library does not help (0.031 vs nolib 0.059; gated beats it by +0.178) | VERIFIED |
| Rewrite+combine together add value over induction alone under the gate (+0.068 [+0.041,+0.100]); the ablation disables both, so the effect is not attributed to rewrite alone | SCOPED (v2 ablation separates them). Combine contributed 0 admissions at margin 2 (167 rejected) and 0.3 skills/seed at margin 1: NOT shown useful |
| The gate keeps libraries small (4 vs 60 skills); theme-aligned share (58% vs 13%) is a proxy label from my authored themes, not a measure of genuine skill quality | VERIFIED as size; proxy for quality |
| The unseen-gain gate improves performance over admitting everything | FALSIFIED. admit_all beat gated margin 2 on 17/20 seeds (-0.062). The gate is too conservative: skills are judged one at a time and most useful skills add < 2 net validation tasks alone |
| Margin 1 recovers it (0.286 vs 0.271, CI of the difference includes 0) | PARTIAL: post-hoc margin chosen after a pilot, and still not better than admit_all |
| Junk skills in admit_all hurt on novel themes (0.013 vs nolib 0.030) | UNVERIFIED: CIs overlap and the novel-theme sample is tiny (18 tasks x 20 seeds, ~1-3% solved). No harm from bloat shown, no robustness benefit of the gate shown |
| Failure-case regression: a skill that passes its own tests but fails unseen tasks is not trusted | VERIFIED at unit level (`tests/test_e9.py::FailureRegression`: overfit `[sort_desc,take3]` from poor examples passes own tests, fails 6/6 unseen rich theme-2 tasks, gate rejects it, admit_all accepts it, correct `[dedupe,sort_desc,take3]` is admitted, tampered tests rejected). At scale, 33 of 78 gated-admitted skills are not theme-aligned, so the gate does not guarantee genuine skills |
| Skill-level failure cases are recorded but only used as a regression input to rewrite; they do not retire an admitted skill | SCOPED: no retirement/audit pass was implemented |
| Preconditions inferred from poor examples under-generalise: a correct skill acquired from distinct/non-negative examples never fires on rich-example tasks (found while writing the regression test) | VERIFIED as a design property; not quantified at scale |
| Result transfers beyond this authored domain | UNVERIFIED. Themes recur by construction, so reuse is the whole mechanism here; no prior-art check was done, no novelty claim is made (library learning, DreamCoder-style, is established prior art) |

## Honest read
The skill library works and rewrite helps. The "trust only if it improves unseen tasks" rule, as I implemented it, makes libraries small and clean but costs accuracy against admit-everything in this domain. The test set shares themes with acquisition, so admit_all's many task-specific skills (theme + same extra op) get reuse credit that would not exist with fresher tasks. I did not run a variant with test tasks whose extra op is never seen in acquisition. The gate's margin was tuned once, post-hoc, on a 2-seed pilot; margin 1 results are labelled as such.

## Known limits
Python 3.12 not run. Single domain, authored. The gate reuses the same 40 validation tasks adaptively for every decision (validation overfit possible, unmeasured; test tasks are never used for decisions). random_lib_same_size used max(gated size,1) skills. Search budget fixed at 1500; other budgets not run (e7 saw gains vanish at larger budgets; unchecked here). Combined-skill tests are tautological snapshots.
