# ATLAS-1000-LOCAL-DISPATCH-02

## Scope

Real bounded local dispatch consumer, NOT operational 1000 deployment,
throughput, horizontal nodes, delegated worker credentials, or proof that
reconciliation terminates external work. Those requirements remain OPEN.
No provider/network/cloud/spend. Existing Bubblewrap namespace/readonly-file
and seccomp process limits stay intact; no sandbox security downgrade.

The owner creates actual M14 waves, approves logical admission and reserves
slots, separately approves M14 execution, then explicitly enqueues selected
waves. Enqueue and claim both require unused exact live owner execution
approval. Admission alone cannot enqueue or execute. Selected wave snapshots,
whole batch digest and all exact wave slots bind the job. Jobs have permanent
unique wave IDs, with no retry/requeue API. Owner OIDC enqueue/status routes
are the only HTTP additions; there is deliberately no HTTP worker-run route.

Finite operator invocation `run_local_pool` requires explicit
ATLAS_M14_LOCAL_DISPATCH=1 and starts at most two independent Python workers.
The separate spawn-safe entrypoint reads its private stdin specification.
Workers inherit operator-owned database access; this is not a delegated
identity/credential issuance protocol. Root must be an existing private,
nonvolatile M14 sandbox root. HTTP setup requires the same opt-in and migration.
Migration provisions a fixed policy: two claimed jobs, at most four admitted
sandbox tasks, at most two tasks per wave. This counts admitted task executions,
not ancillary Python/Bubblewrap/probe processes or measured CPU utilization.
No long-running daemon/beat/autostart/Celery broker is added.

## Atomic execution

Every local claim/finalize uses the existing global admission singleton UPDATE
mutex, then project/wave ordering through the shared M14 claim helper. Claim
atomically consumes the separate execution approval, sets the M14 wave claim,
claims ALL logical slots, and stores job token/fence/worker label. PostgreSQL
and SQLite actual rollback/contention are tested. No partial-slot claim then
separate transaction wave claim window remains. The original M14 claim/execute
HTTP path retains its behavior through extracted in-session helpers.

The job runs the actual existing sandbox task backend. Receipt publication,
artifact storage, matching durable S6 validation, slot/quota release, and job
terminal state commit together. A failure with real backend receipt is failed,
not reviewed success. Unknown/incomplete execution cannot free capacity.
Human quality review remains required. Job completion is not project completion.
The local worker receives owner context from the trusted operator, not from an
unverified message or a claimed arbitrary worker role.

## Unknown and cancellation

Worker interruption after committed claim leaves job claimed/outcome_unknown,
wave claimed and slots charged. No replacement worker automatically resumes.
Slot cancellation after claim invalidates admission fence and makes publication
refuse. Claimed jobs have no reconciliation/requeue endpoint in this unit;
they conservatively retain the local pool slot, even if individual admission
slots are later reconciled. Operator repair/recovery is a later reviewed unit.
The supervisor timeout kills its Python worker, NOT proven child sandbox
termination; backend-owned task timeout/process-group cleanup still applies.
No capacity release follows supervisor termination. This is not a promise
that killing a worker kills all work. Physical resource cleanup remains OPEN.

## Verification record

Initial missing-module red test is retained. First20-node run:8 FAIL/12 PASS
(extracted publication helper referenced missing payload). Fixed local variable.
Next4 FAIL/16 PASS: subprocess -m double-registered package ORM, and real failed
backend receipts were incorrectly refused. Fixed spawn-safe separate entrypoint
and explicit failed receipt handling. Fresh20 PASS; expanded40 PASS; latest
48 PASS (79.95s), actual PostgreSQL and SQLite.

Product tests start two actual OS workers, four actual Bubblewrap sandbox tasks,
read real S6 task/artifact records and leave a third admission untouched.
Separate OS contenders synchronize before claiming one job, one winner only.
Crash child exits27 immediately after claim; restart cannot redispatch and quota
stays charged. Rollback tests cover permit/slots and finish receipt/quota commit.
OIDC owner/foreign tenant, source/policy/resources/expiry drift, slot cancellation,
forged job/slot fences, partial outputs, real failed execution and populated
migration downgrade refusal are tested. Two selected waves from one batch can
both run after the first becomes claimed/completed.

Named mutations, restored source after each: separate execution approval,
job owner, two-worker/four-task cap, live slot selection, job fence, job token,
slot fence, real receipt state each yield2 FAIL, one per database backend.
The early receipt-selection guard mutant survives its partial-receipt scenario
(2 PASS); appears masked by downstream complete durable S6 task selection.
This is unpinned defence-in-depth, not proven redundancy; no kill claimed.
Initial owner and job-token survivors were closed by isolated status and corrupt
job-token canaries, not relabeled as prior kills. Full old M14/M00 and admission
regression XML receipts will accompany the candidate. Operational1000 stays OPEN.

Latest new48 PASS83.83s with XML. Receipt start/finish intervals prove actual
sandbox task overlap peak>=2 and<=4, not merely two spawned worker labels.
Full PostgreSQL empty->migrationhead->downone->reup PASS. Current M14 collection
1143 nodes =1095 prior nodes +48 new nodes. No operational deployment claim.

Complete candidate regression splits: old M14 fast914 PASS16.27s,
slow104 PASS/1strictXFAIL117.51s, existing admission76 PASS56.32s,
new local dispatcher48 PASS83.83s. Disjoint union1143 =1142 PASS/1XFAIL,
matching full collection1143. M00 separately250 PASS17.76s. Base3ec2aa11
fresh public receipts from prior landing: same oldM14/admission counts,
M00250 PASS. Previous unit's failed whole-run and disk-full retry are not
reclassified by these later serial checks. Fresh independent audit is required.

## Independent audit named test-only repairs

FIX-1 adds 24 paired SQLite/PostgreSQL nodes, product bytes unchanged. R1
corrupts job worker label while retaining matching slot label. R2 separately
pins claim payload, job-bound wave digest and current-version source checks.
R3 isolates early complete-receipt selection by explicitly stubbing downstream
S6 classification; R4 returns an explicit nonverified classification to isolate
its refusal. Those two are guard-unit tests, not claims that stubbed S6 proves
execution. Real execution/evidence tests remain separate and unchanged. R5
uses a nonqueued job with an otherwise unclaimed approved wave. R6 corrupts
runtime reservation and cost separately. R7 separately pins reserved batch,
self-consistent execution source drift after admission, and duplicate task
slots (set equality alone cannot detect the wrong count).

Restored-source mutant receipts: R1/R3/R4/R5 each2 FAIL; combined R2 guard6
FAIL; R6 runtime/cost each2 FAIL with2 unaffected PASS; R7 state/source/count
each2 FAIL with4 unaffected PASS. No product changes made to kill these.

FIX-2 permitted unpinned defence-in-depth, no kill claimed. R8 checks unused
effect, event actor, expiry and approval payload in _execution_approval appear
masked at claim by _claim_in_session and M00 exact-payload effect consumption;
removing these early checks can still defer refusal until claim. Slot actor
in _slots appears masked by batch/wave owner checks under ordinary uncorrupted
slot creation. Exact slot-ID list equality appears masked by complete task set
and slot state checks; a corrupt replacement row is not proved safe. Individual
worker-count and task-count guards overlap for ordinary two-task waves under
fixed2x2 policy, though one-task jobs can distinguish job count. These are
code-reading hypotheses, not behaviorally proven redundancy. The auditor's
original survivor observations remain distinct from this explanation.

The local finish current-version fence and _publish_in_session current-version
fence overlap; the existing M14 supersede suite pins the older publication
path. No local-file kill of the latter standalone guard is claimed.

Auditor's NOT-RUN list remains UNVERIFIED by that audit, not a survivor list:
slot-count limit, CPU resource, enqueue slot expiry, claim slot expiry, wave
approval recheck at claim, claim-source drift removal, finish slot token and
expiry, receipt backend, pool job-count, publish-state check. Ordinary tests
may cover related behavior but are not their named mutation receipts. The
revised candidate returns for the independent auditor's complete split replay,
all survivors and that unrun list. Operational1000 deployment remains OPEN.

Revised 72-node complete local-file verification uses disjoint selector splits:
46 PASS existing selector (80.57s) and26 PASS guard selector, with XML union72
unique nodes. One unsplit revised run hit the workspace execution timeout after
61 progress dots, no final summary/XML; it is NOT a successful whole-file run.
Prior whole M14/M00 receipts remain pre-fix. Independent auditor will re-run
those on the revised commit. Product bytes are identical to fce2097.
