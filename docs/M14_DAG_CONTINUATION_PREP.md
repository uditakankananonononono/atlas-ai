# M14 attempted-wave continuation policy (PREP, authored, NOT RUN)

Status: design and test prep, builder-authored. The builder (this task agent) did NOT run anything:
its only checks were py_compile and ast.parse on the test file. Provenance of the later results:
the PEER's independent auditor executed the tests on its own side with a real Bubblewrap environment
present and reported 21 PASS + 1 strict XFAIL; whole M14 969 PASS / 1 XFAIL / 2 pre-existing
environment FAIL, identical to base, plus the 21 new, zero regression (auditor's figures, relayed by
the coordinator, not reproduced by the builder). Auditor mutation results: removing the project
attempted-wave key was caught by 6 tests. Removing the wave-state guard was NOT independently pinned:
all 21 still passed because both guards raise the same exception type (`WaveConflict`) and the
original policy helper compared type only. Both guard messages are statically present in the source
(a static test pins them); the state guard's removal was masked, not shown to be caught. The
follow-up revision of the helper matches messages to pin each guard; that revision is itself
AUTHORED-NOT-RUN by the builder until the auditor runs it.
Nothing here implements continuation, resume, retry or recovery. No product file is changed.
Base: 7d6098ff81b17478d0a975961f40904d5c69cb99
(tree 2d41da684ce15b9c6e871cccd66992da9d06c4a4). Source read statically with `git show` at that
exact commit: `backend/app/modules/m14_project_builder/sandbox_wave.py`,
`docs/M14_SANDBOX_WAVE_20261010.md`, `tests/modules/test_m14_sandbox_wave.py`.
Claims about runtime behavior below were read from code by the builder; the auditor's run is the
only execution evidence.

Question: when a run is interrupted mid-wave and a later process finds the permanent
attempted-wave key, what exact continuation contract applies, and what is NOT resumed?

## Short answer

The contract is: **no continuation.** A project with an attempted-wave key is closed to any
further sandbox dispatch. Only reads are served. The interrupted wave is reported as unknown
and is never completed, retried, resumed or replaced by the code at this base. The landed
document already says "Review/continuation is a future unit, not implemented here"; this
document fixes what "not implemented" means precisely so a later unit cannot weaken it silently.

## Persisted facts per stage (what a second process can see)

Stages are the named boundaries in `SandboxWaveService`. "Key" is `SandboxWaveRow.claim_key`,
`digest({'tenant': tenant, 'project': project_id})`, unique, set only by the claim transaction.

| # | Boundary (interruption lands just after) | wave.state | claim_key | M00 effect row | task rows | artifact rows | result |
|---|---|---|---|---|---|---|---|
| S0 | draft committed | draft | none | none | none | none | none |
| S1 | submit committed (M00 request pending/decided) | awaiting_approval | none | none | none | none | none |
| S2a | claim: environment probe done or failed, claim transaction not committed | awaiting_approval | none | none | none | none | none |
| S2b | claim transaction ran claim update and consume_effect but did not commit (rolled back) | awaiting_approval | none | none | none | none | none |
| S3 | claim transaction committed, dispatch not started | claimed | SET | 1 | none | none | none |
| S4 | dispatch in progress, any subset of tasks finished inside the process | claimed | SET | 1 | none | none | none |
| S5 | all tasks finished in memory, finalize transaction not committed (rolled back) | claimed | SET | 1 | none | none | none |
| S6 | finalize committed | awaiting_review | SET | 1 | one per dispatched task | per output | stored |

Why no state sits between S5 and S6: `execute` builds receipts only after `asyncio.gather` over
every ready task returns, then writes all task rows, all artifact rows, `result` and
`state='awaiting_review'` in one `sessions.begin()` block. Per-task results are never persisted
individually. So a finished task in an interrupted wave leaves no durable trace. A sandbox
process that finished inside an interrupted run is lost, by design, and must not be inferred
from anything else.

S2a and S2b are not attempts: key and effect are absent, the approval is unconsumed, and the
claim may be retried by anyone with the same wave under the existing guards. S3 to S5 are
attempts: the key is permanent and the approval is consumed.

## Second-process contract

A second process is any `SandboxWaveService` constructed later over the same database
(restart, another worker, or an operator). Rules, with the code path each is read from:

1. `get` on a wave in state `claimed` returns `unknown_after_claim=True`, `result=None`
   (`_view`). It is the only truthful answer. The wave is neither failed nor complete.
2. `claim` and `execute` on that wave raise `WaveConflict('wave cannot be claimed')` because the
   state is not `awaiting_approval`. `execute` calls `claim` first, so nothing is dispatched.
3. A fresh draft for the same project may be created, submitted and approved (draft and submit
   do not read the key), but `claim` raises `WaveConflict('project already attempted this wave
   unit')` before any state change or consumption. The new approval stays unconsumed and the new
   wave stays `awaiting_approval`. The key is per project, so this also closes the project to
   its dependent tasks and to a second wave after a completed S6.
4. `artifacts` on a wave that never reached S6 returns an empty list; `artifact` for any id
   raises `WaveForbidden`.
5. Project plan and budget are not changed by a wave at any stage, so no plan field records
   progress. Plan status is not evidence of completion.
6. In state `awaiting_review` (S6) the same rules 2 and 3 apply. The result carries
   `all_dag_completed=False` and `independent_quality_verified=False`; neither is upgraded.

## Explicitly NOT resumed, retried, or inferred

- Tasks of an interrupted wave, including ones that finished inside the dead process.
- The remaining ready tasks, dependents (a task whose dependency is not `completed`) and any
  later wave of the DAG.
- Partial or orphan artifact/task rows, if any exist, as evidence of completion. Under the
  documented atomic finalize they cannot exist; if found, treat as corruption, not progress.
- The reservation (calls, runtime, zero USD cost): consumed at claim, never refunded or released.
- The M00 approval: spent at claim. It does not authorize a rerun; a replay with the same
  effect id never re-enters execution.
- The attempted-wave key: no code path clears or reuses it.
- A `claimed` wave by timeout, heartbeat or age. The code has no lease. A second process cannot
  tell a crashed owner from a slow one; a slow owner may still commit S6 later. Policy for the
  reader is: keep reading, never act on it.

## Constraints on any future continuation unit (design requirements, not implemented)

A later unit that adds review or continuation must not change the rules above implicitly. Minimum
bars, each an owner decision, not an assumption:

- A new, separately approved M00 action type bound to the exact prior wave id and its digest.
- Explicit human authority to supersede an unknown wave; the system must not conclude abandonment
  by itself.
- A new reservation, charged separately. No reuse of the consumed one.
- A rule for lifting or versioning the permanent key that names who may do it.
- Verification of the previous attempt from durable evidence only (S6 rows with verified SHA256),
  never from process memory, plan status, temp directories or logs.
- Metadata such as `claim_key`, `digest`, task or artifact rows is not authentication of who
  wrote it. Anyone with write access to the SQL store can alter it. This document does not
  claim otherwise.

## Unresolved semantics (flag before relying on the contract)

1. No lease or staleness rule: slow versus crashed is undecidable; see above.
2. `artifacts()` does not check wave state. If partial artifact rows ever existed for a `claimed`
   wave, they would be listed and downloadable. Unreachable with atomic finalize, but not
   enforced by the read path. The test file carries a strict xfail documenting this.
3. `claim` runs the environment probe before reading wave state, so on a host without namespace
   capability a second-process `claim` on a spent wave raises `WaveUnavailable`, not
   `WaveConflict`. Either way nothing is consumed or dispatched.
4. A wave interrupted at S3 to S5 permanently closes its project even though no task result was
   saved. That is intended by the landed text ("no automatic retry/resume") but is the harshest
   consequence; confirm it is what the owner wants.
5. "Second process" in the authored tests is a second service instance over the same database,
   the same convention as the existing restart tests, not a separate OS process.
6. The authored interruption injection uses a `BaseException` subclass raised inside a worker
   thread and a SQLAlchemy `before_commit` listener on the sessionmaker. The builder never executed
   either. The peer's auditor run (21 PASS + 1 strict XFAIL, real Bubblewrap present) exercised
   them and they behaved as the tests assume; that confirmation belongs to the auditor.
7. Plan-DAG readiness (`_ready`) treats `blocked` and `ready` tasks whose dependencies are all
   `completed` as ready; a sandbox wave never marks a task completed, so dependents remain
   permanently unready at this base.

## Authored tests (NOT RUN)

`tests/modules/test_m14_continuation_prep.py`. Static tests need no sandbox. Real-execution tests
reuse the existing convention and skip when Bubblewrap namespaces are unavailable. Policy
assertions check the guard by exception message: "wave cannot be claimed" for the state guard and
"project already attempted this wave unit" for the project key. Planned commands for the executing
side are in the delivery manifest.
