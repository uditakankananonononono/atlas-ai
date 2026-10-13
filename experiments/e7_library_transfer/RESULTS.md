# E7: library learning across four authored domains, and a loop-structure comparison (directions 1, 3, 4, 7)

Label: replication of library learning in the style of DreamCoder (Ellis et al. 2021) and Stitch (Bowers et al. 2023) on a tiny authored suite, plus a negative result for a multi-loop agent. Source pin: atlas-ai main f7ae6fe7 (new files only), Python 3.12.14. Nothing here is a novelty claim.

Setup: 40 tasks, 10 per domain (domains named math, bio, code, physics: integer sequences, base sequences over 0..3, +1/-1 bracket sequences as a stand-in for code, position traces), each a pipeline of 3 or 4 of 14 list primitives; 8 training and 8 held-out input/output examples per task; a program counts as solved only when it matches all 8 held-out examples. Search is enumeration of pipelines, budget = programs evaluated. Library macros are promoted only if they raise the solved count on a validation half of the training tasks (candidates must occur in at least 2 solved programs from at least 2 domains). Held-out environment = a whole domain left out (4 folds). Controls: no library, a random library of the same size, a within-domain library. Files: `dsl.py`, `library.py`, `run.py`, `loops.py`, `rows.jsonl`, `libs.json`, `loops_rows_B1000.jsonl`, `loops_rows_B300.jsonl`, `analysis.txt`, `loops_analysis.txt`. Data statement: tasks and domain input generators are authored synthetic for this experiment. Several tasks have shorter equivalent programs on the generated inputs (for example the bracket domain has only +1/-1 values), so base search solves them early; that dilutes the effect.

## Direction 1 / 4 / 7: transfer of learned macros to a held-out domain
| Claim | Status |
|---|---|
| Budget 1000: base solves 0.525 of held-out tasks, cross-domain library 0.600 (+0.075, bootstrap 95% [-0.025, +0.200]), random library 0.500 (library minus random +0.100, [+0.025, +0.200]) | VERIFIED |
| Budgets 3000 and 10000: library minus base 0.000 on both (base already solves 0.900 and 0.975) | VERIFIED |
| Macros promoted at budget 1000: m_cumsum_max (bio fold and physics fold), m_sort_reverse (code and physics folds), none for math. Physics held-out rose from 0.2 to 0.5 | VERIFIED |
| Within-domain control (5 tasks per domain) at budget 1000: no library 0.550, own-domain library 0.550, cross-domain library 0.600 on the same tasks | VERIFIED |
| The gain over no library is established (interval includes zero at the one budget where it appears) | UNVERIFIED |
| The abstraction transfers between math, biology, software engineering and physical reasoning as such (the domains here are four input generators over one primitive set) | UNVERIFIED |
| A transfer on external data from outside the authored tasks | UNVERIFIED |

## Direction 3 (SCOPED): fast/deliberative/learning/strategic loops vs a single loop, stream of the 40 tasks, 10 orders
Loop rules as coded in `loops.py`: fast loop = library macros as cached skills; deliberative = enumeration at budget B; learning loop = re-learn macros every 8 tasks from verified solutions (cost counted); strategic loop = retry a failed task once at 3B only if total programs evaluated so far < 0.7*3*B*(k+1)*0.5 after k+1 tasks (about 1.05*B per task).
| Claim | Status |
|---|---|
| Budget 1000 per task: single loop solves 21.0/40 using 25,215 programs evaluated; single loop with 3x budget solves 36.0/40 using 41,662; multi-loop solves 22.8/40 using 77,914 (including learning-loop cost) | VERIFIED |
| Budget 300: single 12.0/40 (9,059), single 3x 20.0/40 (23,298), multi 13.0/40 (15,473) | VERIFIED |
| The multi-loop agent beats the single loop at equal per-task budget by 1 to 1.8 tasks (10 of 10 orders) but is worse than the 3x-budget single loop by 7 to 13 tasks and spends more total compute at budget 1000 | VERIFIED |
| Multi-loop structure gives more robust generalization than a single loop with more context | UNVERIFIED |
| A long-horizon task with a cost not measured in enumeration steps | UNVERIFIED |

Missing real test for direction 3: an agent working a long task with a wall-clock or token cost, compared at equal spend. This toy has no such cost.
