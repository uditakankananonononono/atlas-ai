# ATLAS-1000-DURABLE-ADMISSION-01

## Contract

This unit implements architecture and admission acceptance for 1000 logical
builders. The operational requirement "deploy 1000 builders at once" remains
OPEN. No worker launch, provider request, model throughput, cloud provisioning,
1000 operating-system processes, distributed sandbox containment, or full DAG
completion is proved. Existing ProjectPlan <=500 and sandbox-wave <=8 limits
remain unchanged. Logical admission does not authorize sandbox execution and
does not automatically integrate with any worker dispatch path.

The product workflow is owner wave draft -> immutable admission proposal ->
owner decision through the module endpoint -> durable reservation -> logical
worker claim -> fenced completion. Existing M14 execution approvals remain
separate. The authenticated original wave owner supplies no caller approval
boolean and cannot substitute a foreign tenant or owner. M00 remains the stored
approval/effect record; its generic decision endpoint refuses this action.
Admission uses unattempted draft/awaiting-approval waves, exact project revision,
plan and budget snapshots, and ready-task validation including rejected-task
exclusion. It deliberately does not allocate provider credentials.

## Fixed policy in this unit

Global concurrent admission limits: 1000 slots, 1000 declared CPU units,
256000 MB declared memory, 1000000 declared runtime seconds, zero cost cents.
Per-tenant limits: 600 slots, 600 CPU units, 153600 MB, 600000 seconds, zero
cost cents. These are logical reservations, not enforced execution limits or
memory/cgroup measurements. All resources are positive bounded strict integers;
cost is exactly zero. Migration explicitly provisions the singleton global
policy. First allocation provisions a tenant under the fixed policy inside the
same transaction. Policy drift refuses. There is no runtime policy-edit API.
The policy constants are admission quotas, not proof of hardware availability.

The singleton database UPDATE obtains the write mutex before every decision,
reservation, claim, release and reconciliation. PostgreSQL serializes on its
row; SQLite serializes writers. Quota checks and charges, permanent task key,
1000-capacity check, slot insertion and M00 effect consumption commit together.
The service performs no startup create_all or automatic pool provisioning.
The gate proposal may leave a harmless unused M00 request if local batch
creation fails; it cannot reserve slots without the matching module record.

A task key is permanent per tenant/project/task. Completion frees concurrent
capacity but never permits fresh-batch redispatch of that same logical task.
A future generation/retry policy requires a new reviewed unit. The DB mutex is
a serialization bottleneck; no throughput or availability guarantee is claimed.

## Fencing and unknown outcomes

Claims return a random token, monotonically advancing fence, and worker label.
The authenticated owner is the caller; this unit adds no delegated worker
identity/credential issuance. A token is not execution authority. An active,
unexpired exact token+fence+worker match is required to release through
completion. Cancellation before claim frees the slot. Cancellation after claim
invalidates the fence and marks unknown WITHOUT freeing capacity. Expired
claimed work appears as unknown on status and remains charged. No timeout,
restart or replacement worker silently retries or releases it.

The owner can explicitly reconcile unknown work with a bounded reason. This
is recorded as unknown_closed_no_retry, not as successful execution or proof
that external work stopped. It frees logical capacity but does not kill work;
operators must ensure external work is stopped before treating physical
resources as reusable. There is no external work in the acceptance fixtures.
Claims that crash before expiry remain visibly claimed, not falsely completed;
they may be explicitly cancelled into unknown or age into the unknown report.

## HTTP

Mounted under the existing /project-builder router:
- POST /builder-admission/batches: immutable wave specification proposal.
- GET /builder-admission/status: own tenant quota usage, truthful scope flags.
- GET /builder-admission/batches/{id}: owner-only batch, logical slots, unknowns.
- POST /builder-admission/batches/{id}/decision: approved or denied by owner.
- POST /builder-admission/batches/{id}/reserve: atomic permit and reservation.
- POST /builder-admission/slots/{id}/claim: bounded worker_id.
- POST /builder-admission/slots/{id}/complete: token/fence/worker_id/outcome.
- POST /builder-admission/slots/{id}/cancel: before/after-claim semantics above.
- POST /builder-admission/slots/{id}/reconcile: explicit reason, no retry.

Status deliberately does not disclose other tenants' global occupancy. Every
response says dispatch_authorized=false where relevant. HTTP auth is the
existing production OIDC verifier; tests use locally signed RS256 identities.

## Migration and evidence

Revision 20261010_m14_builder_admission follows 20261010_m14_review_continue.
It creates five new tables and one fixed pool row, no legacy backfill. Populated
SQLite and PostgreSQL roundtrips preserve existing project rows. Downgrade
refuses reserved/claimed/unknown slots; settled history is removed only by an
explicit downgrade. No production migration or deployment was run.

Tests prove 1000 distinct logical slots across 125 eight-task project batches,
two tenants, exact SQL inventory/counters, and 1001st refusal without a consumed
permit. Separate OS contenders allocate only one of two 400-slot batches when
600 are already reserved. Actual PostgreSQL and SQLite, not mocked storage.
Another process reads the durable 1000 count. Separate claim contenders issue
only one fence. A child commits claim then exits 27; restart cannot re-claim,
unknown remains charged, explicit reconciliation invalidates stale completion.

Initial missing-module red collection is recorded, not a base 1000 load test.
First complete controls: 32 PASS. Added binding negatives found an expiry gap:
46 PASS / 2 FAIL; module-side live M00 expiry check fixed it, then 48 PASS.
Five named mutants (global capacity, tenant binding, claim fence, module owner
decision, aggregate quota) each produced one focused FAIL and were restored.
Exact-base/candidate existing-module and M00 results are recorded in the audit
packet. One unsplit candidate whole-M14 invocation was killed at the 120-second
execution limit; it is NOT a successful whole-suite receipt. Disjoint complete
splits, not that interrupted run, establish regression results.

Latest complete candidate receipts: 48 new admission PASS (44.29s), existing
M14 disjoint 914 PASS (13.45s) + 104 PASS / 1 strict XFAIL (122.26s),
M00 250 PASS (19.27s). Ordered legacy collection equality: 1019 exact nodes.
Full PostgreSQL empty -> migration head -> down one -> re-up PASS.
Final named mutant rerun: five separate 1 FAIL receipts, then restored source
and fresh 48 PASS. The strict XFAIL is retained baseline behavior, not a skip
and not repaired by this unit. The acceptance fixtures model project/wave rows
for the 1000 inventory, while a separate actual product drafting consumer uses
M14 SandboxWaveService and its real Bubblewrap environment probe.

Exact base 6906ebdb regression receipts: 914 PASS (17.51s) + 104 PASS /
1 strict XFAIL (124.50s), M00 250 PASS (20.80s). Candidate matches these
counts exactly, adds 48 new PASS. After bounded wave-ID transport hardening,
fresh exact candidate admission tests: 48 PASS (42.38s). No skipped tests.

## Independent audit named fixes

The first independent audit reported no product defect and killed 14 mutant
classes. FIX-1 and FIX-2 add paired SQLite/PostgreSQL guard tests, with product
bytes unchanged. New scenarios pin P1 premature live-claim reconciliation,
P2 expired reserved-slot claim, P3 wrong completion token with correct fence
and worker, P5 same-tenant foreign wave actor, P6 rejected task and nonready
subset, plus P4 self-consistent source-digest drift at reserve and claim,
P7 decision expiry/payload match, P8 fixed pool/tenant policy drift, P9 release
quota-integrity rollback. Each corresponding isolated mutant was run and killed:
P1/P2/P3/P5/P6 guards produced 2 FAIL each (one per SQL backend);
P4 reserve/claim, P7 expiry/payload, P8 pool/tenant produced 2 FAIL each with
2 unaffected scenario PASS; P9 produced 4 FAIL. Source restored afterward.

Remaining accepted unpinned defence in depth, no mutation kill claimed:
- P10a duplicate project/task at proposal: appears masked at reservation by
  permanent work-key lookup and its UNIQUE constraint. The pinned fresh-batch
  deduplication scenario is not an in-batch duplicate-path proof.
- P10b proposal over-1000 early refusal: appears masked later by global1000
  and tenant600 quota checks. This does not prove the early proposal guard.
- P11 unused approval-effect precheck: appears masked by approved-state refusal
  after reserve sets reserved, and M00 consume_effect in the same transaction.
  The latter masking path was not behaviorally probed by this admission audit.
- P12 slot actor check: appears masked by the following owner batch check.
  Slot actor is copied from batch owner; directly corrupted slot rows are not
  covered by that masking hypothesis.

These explanations are code-reading hypotheses, not proven redundancy. The
original auditor removed each of these guards separately and observed the old
48-test file still PASS; that is a survivor receipt, not a guarantee that the
removed defence is unnecessary. Operational deployment remains OPEN.

Named-fix fresh complete admission receipt: 76 PASS (56.28s), zero skips.
Product/backend/migration bytes exactly unchanged from af19cf9. The earlier
whole M14/M00 receipts above are pre-fix receipts, not relabeled as new runs.
The revised candidate returns for the independent auditor's whole M14/M00 and
survivor-list replay before any landing decision.
