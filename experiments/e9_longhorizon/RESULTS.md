# E9: multi-timescale loops vs a single loop on a long-horizon multi-file repair task (direction 3, replaces the toy in e7 loops.py)

Label: SCOPED. A measured-cost agent task, but the agents are programmatic search agents (mutation-based repair with fault localization), not LLM agents; no LLM was used, so there is no token cost. Not a novelty claim. The names GenProg (Le Goues et al. 2012) and Ochiai/spectrum-based fault localization (Abreu et al. 2007) are cited from recall as the closest prior art; no prior-art search was run for this experiment and the citations were not checked against sources, so treat them as UNVERIFIED pointers, not a prior-art check. Python 3.12 target (developed on 3.10; an independent replay of selected rows on 3.12 matched on the semantic fields compared (evals, visible and hidden outcome), not the whole file; stdlib + numpy only). New files only, intended for atlas-ai main 4f68f54a (e7 landed); only the directory experiments/e9_longhorizon is touched, but I could only check the apply against f7ae6fe7 plus the e6/e7/e8 v2 patch, not 4f68f54a itself; no code from e6/e7/e8 is imported.

Task (authored synthetic data, generated from templates and seeded constants): a Python project of 6 modules with 18 or 19 functions in total (18 in 28 of the 48 first-suite projects, 19 in 20): each module has 2 primitive functions (each a list-to-list or list-to-int template) and one composite that returns `R(L(xs)) + c`, and a module gets one extra list-to-int helper when it would otherwise have none. `L` and `R` are drawn from the list-to-list and list-to-int functions defined so far, which may include the same module's own primitives, so a composite does not necessarily call only earlier modules. k = 1, 2 or 3 single-AST-mutation bugs are injected into k different modules. 8 visible tests per function drive the agent; 20 hidden tests per function score the final program. Hidden tests and bug locations are not shown to the agents by convention in the code (the agents receive the `Project` object and the code does not read `hid` or `bugs` except to score and to build the starting buggy state); these are use-by-code boundaries, not enforced interfaces. A bug counts only if it fails at least one visible test. The edit space (about 400 to 450 single-site edits: comparison, arithmetic, and/or, constant +-1, scalar variable swap, plus a revert of the original value at every site so bug locations are not leaked by the candidate list) contains the inverse of every injected bug. That is the same family as the bug injector, so this measures search efficiency, not discovery of unseen fix types.

Cost unit: program evaluations (one run of the visible suite on one candidate; cache hits free; each fault-localization coverage run charged as 1 evaluation). Test executions are also logged (`tests` in rows). Wall time is logged; coverage runs are slower than plain evaluations, so wall time favours agents that localize less. No tokens: not measured.

Agents (all anytime, so success at budget B = first visible pass at evals <= B and zero hidden failures): `S_uniform` single loop, greedy (accept only strictly fewer failing visible tests), uniform proposals; `S_fl` same with Ochiai weights computed once; `M` three timescales: fast edit proposals, medium recompute of fault localization after each strict improvement, slow per-episode operator-kind credit weights plus a stuck rule (revert to best, flatten weights); `M_noslow` ablation without the slow loop. Hyperparameters (STUCK=120, EPS0=0.05, growth 2) were set by hand and never tuned by search, but no dev split was run, and task size, visible-test count and the acceptor were changed after a pilot on this same family (see Caveats), so the final configuration is not independent of that pilot and the test numbers carry that selection. Evaluation: 48 test tasks (seeds 1000-1047, k cycling 1,2,3), 2 agent seeds each, paired bootstrap over tasks (5000 resamples). Files (module names carry an `lh_` prefix so they do not collide with other experiments in a shared pytest run): `lh_tasks.py`, `lh_agents.py`, `lh_run.py`, `lh_analyze.py`, `test_e9_longhorizon.py`, `rows_test.jsonl`, `analysis.txt`.

Run: `cd experiments/e9_longhorizon && python3 test_e9_longhorizon.py` (or pytest), then `python3 lh_run.py test S_uniform,S_fl,M,M_noslow 0,1 /tmp/rows_rerun.jsonl` (about 2 minutes on 2 cores; the fourth argument is the output path, the file is replaced, never appended, and with no fourth argument it replaces the shipped `rows_test.jsonl`) and `python3 lh_analyze.py test '' /tmp/rows_rerun.jsonl`; the analyzer refuses files with repeated (seed, kind, agent seed) rows. Runs are deterministic given seeds; the analyze output is in `analysis.txt`.

## Results (hidden-verified success rate, 48 tasks x 2 seeds)
| agent | B=100 | B=333 | B=1000 |
|---|---|---|---|
| S_uniform | 0.250 | 0.667 | 0.708 |
| S_fl | 0.573 | 0.646 | 0.646 |
| M | 0.562 | 0.615 | 0.615 |
| M_noslow | 0.604 | 0.646 | 0.646 |

| Claim | Status |
|---|---|
| M beats uniform single loop at equal budget 100 (+0.312, 95% [+0.188,+0.438]); it does not at 333 (-0.052 [-0.156,+0.052]) | VERIFIED |
| M versus the single loop that also uses fault localization (S_fl): no gain at equal budget (100: -0.010 [-0.073,+0.052]; 333: -0.031 [-0.083,+0.010]) | VERIFIED (negative) |
| The three-timescale structure helps beyond fault localization | UNVERIFIED, evidence points against: M is at or below S_fl and M_noslow everywhere; the slow loop did nothing measurable |
| M at budget B versus a single loop at 3x budget: S_fl at 3x ties or beats M (M@100 minus S_fl@300: -0.083 [-0.156,-0.021]); S_uniform at 3x is above M (M@333 minus S_uniform@999: -0.094 [-0.198,+0.010]) | VERIFIED (negative, interval for the S_uniform comparison includes zero) |
| The 3x-budget comparison is informative at B >= 333 | PARTIAL, effectively no: all 115 unsolved runs (of 384) stopped before budget ran out because the greedy agent exhausted every single edit from its current state (a local minimum). Success is flat past about 400 evaluations for every agent, so extra budget cannot help any of them |
| Success falls with horizon. Hidden-verified solves out of 32 runs per k, k=1/2/3: M 29/18/12 (visible passes 29/22/13), S_fl 30/19/13, M_noslow 30/19/13, S_uniform 32/19/17 (visible 32/21/18) | VERIFIED |
| Overfitting: 3 to 5% of runs pass all visible tests but fail hidden ones (S_uniform 0.031, others 0.052) | VERIFIED |
| Real LLM or token-cost agent, equal-spend comparison | UNVERIFIED, not done |
| Generalization beyond this authored task family | UNVERIFIED |

## Second result, labelled separately: all agents with a local-minimum escape (suffix _esc), fresh seeds
Added after the first result, in response to its main defect. When a greedy agent has tried every edit from its current state, it takes the stored best state (`best`), applies one uniformly random edit to it, and continues the greedy loop from that kicked state, resetting the tried set and, for agents other than S_fl, recomputing fault localization. `best` is overwritten on any strict improvement relative to the current (kicked) state, even if the result is worse than the previously stored best, so later kicks start from the latest improved state and not necessarily the best ever seen; the same rule is applied to all four agents, M additionally recomputes fault localization after the kick. Fresh tasks: seeds 2000-2047 (k cycling 1,2,3), 2 agent seeds, same budgets. This is not independent of the first result (same code and family, design changed after seeing it). Run: `python3 lh_run.py test2 S_uniform_esc,S_fl_esc,M_esc,M_noslow_esc 0,1 /tmp/rows_rerun2.jsonl`, `python3 lh_analyze.py test2 _esc /tmp/rows_rerun2.jsonl`; output in `analysis_test2_esc.txt`, rows in `rows_test2.jsonl`.
| agent | B=100 | B=333 | B=1000 |
|---|---|---|---|
| S_uniform_esc | 0.198 | 0.510 | 0.521 |
| S_fl_esc | 0.479 | 0.542 | 0.552 |
| M_esc | 0.531 | 0.562 | 0.594 |
| M_noslow_esc | 0.510 | 0.531 | 0.531 |
| Claim | Status |
|---|---|
| M_esc minus S_fl_esc at equal budget: +0.052 at 100 [-0.031,+0.146], +0.021 at 333 [-0.073,+0.104]; M_esc at B minus S_fl_esc at 3x: -0.010 [-0.094,+0.073] (B=100), +0.010 [-0.073,+0.094] (B=333) | VERIFIED as measured; no difference established |
| M_esc beats uniform single loop at budget 100 (+0.333 [+0.219,+0.448]); at 333 and at 3x budget the intervals include zero | VERIFIED |
| Slow loop effect: M_esc minus M_noslow_esc +0.021 [-0.052,+0.094] at 100, +0.031 [-0.042,+0.104] at 333 | UNVERIFIED (interval includes zero) |
| The escape makes budget bind (0 of 154 unsolved runs stopped early) but a random single-edit kick adds little: success at 1000 is 0.52 to 0.59, below the first result on different tasks, so the two tables are not comparable | VERIFIED; cross-table comparison not supported |
| Hidden-verified solves out of 32 at 1000 evaluations, k=1/2/3 (visible passes in `analysis_test2_esc.txt`): M_esc 29/14/14, M_noslow_esc 26/12/13, S_fl_esc 26/19/8, S_uniform_esc 26/15/9 | VERIFIED |
| Multi-timescale structure beats a single loop on this task | UNVERIFIED: point estimates favour M_esc at B=100 to 1000 over the single loops, but no interval excludes zero against S_fl_esc |

## Caveats found along the way
- An earlier pilot (not shipped, its rows cannot be replayed with this code) used a 10-module project with up to 6 bugs and accepted equal-fitness moves; almost no agent solved anything (M 3% hidden-verified at 30 tasks, all baselines 0%) and tie-accepting drifted edits inside buggy functions. I changed the task size, the number of visible tests, and the acceptor after seeing those numbers, so the final configuration is not independent of that pilot. Treat the pilot numbers as UNVERIFIED.
- The first result has no escape from local minima in any agent, so the slow loop's stuck rule cannot fire after the neighbourhood is exhausted; the second result adds a simple kick. Both are defects of the design, not evidence that a slow loop is useless. Compound edits and restarts from the original were not tried.
- Only 2 agent seeds per task and 48 tasks; intervals are wide.
- Fault-localization coverage runs cost wall time not reflected in the evaluation count.
