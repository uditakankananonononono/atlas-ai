# M24 write-ahead provider operations and Claire outbox seam

Status: DESIGN ONLY. No implementation, migration, provider call, or production guarantee.
Base: Atlas main `3719c6f8bb7c7b624c8b8e8acdc1287f2f64adc9`.
Read separately: Claire review branch `9a5ba1dac9726de0c3494d3f105aa4ebb5675462`; Meemee main `7cd6c7dca319789668725526f759c7ab9f05db69`.
Memo3 local ledger is not landed on main. Do not assume its table or interfaces exist in production.

## Decision proposed

Use a shared write-ahead operation contract, with domain-owned SQL repositories. Commit a recoverable immutable request BEFORE every model-generation or external transport invocation. Commit the exact generated output BEFORE scheduling transport. For money or person-facing transport, review binds that final output and destination, not the prompt that produced it. Queue publication is a hint, never the durable source of work.

This gives discoverable pending/unknown operations and controlled recovery. It does not make a database transaction atomic with Stripe, a model service, or a recipient. A process dying after dispatch reservation and before the network call cannot generally be distinguished from a process dying after provider acceptance. Never infer absence from silence, elapsed lease, an empty receipt, or a generic HTTP error.

Implement M24 first behind a fail-closed cutover flag, then add the Claire generation/transport seam. Do not create two competing journals for one provider action. Each operation has exactly one authoritative owner repository; adapters project its status into other domains using immutable references.

## Current source findings

| Source | Observed behavior | What it does not prove |
| --- | --- | --- |
| M24 `service.py:24-46`, `repository.py:approval/record_execution` | Reads approved tenant-bound payload, invokes Stripe, then inserts execution result in another transaction. No pre-provider reservation or result replay guard. | Existing request keys do not prove receipt-loss recovery or unique external effect. |
| M24 `stripe_client.py:create_invoice` | Creates invoice item then draft invoice, separate POST keys; accepted item plus later failure is reported as unknown. First item ID is not durably retained before second call. | An idempotency header is not indefinite provider deduplication. |
| M24 `ingest_event` / repository lifecycle writes | Event identity is committed before lifecycle apply; lifecycle updates commit independently. Unsigned `/events` and signed webhook share the same identity table. | Stored event is not successfully applied state. |
| Claire `runtime/goals.py:begin_effect` | SQL-fenced effect reservation and applicable approval consumption share one transaction; commit completes before tool invocation. RETURNING-based insert repair is present. | Goal lease is not external provider fencing. |
| Claire `runtime/tools.py:_execute_effect/reconcile_pending` | Non-read tool intent before dispatch; ambiguous failure remains unknown. Existing `idempotent=True` declaration can allow takeover. | Declaration alone is insufficient for M24 retry policy; generic string `absent` is not authenticated provider evidence. |
| Claire `runtime/engine.py:run`, `worker.py`, `goals.py:settle` | Model decision is awaited without a generation operation row; settlement persists report/verdict, not a transport outbox. | Tool journal tests do not cover generation or outbound publication. |
| Meemee `companion/worker.py`, `companion/store.py` | Check-in queued/running state precedes generation; exact generated body is only saved at completion. External accepted delivery plus storage loss has an unknown marker. Local delivery has an atomic message+completion path. | A running check-in is not an exact request/output outbox. |
| Meemee `webhooks.py:WebhookDispatcher.deliver_one` | Separate webhook outbox exists; documented at-least-once retries with delivery ID and receiver deduplication expectation. | Its resend-on-expired-sending semantics are not safe for arbitrary messages or money. |

The reported "outbox absence" is correct for the inspected Claire goal-runtime publication path, not a claim that all Meemee code lacks outboxes. Existing webhook machinery is a useful queue pattern but its delivery guarantee must not be imported into M24 or person-facing delivery unchanged.

## Records and ownership

Proposed table names are illustrative, not an applied schema:

- `provider_operations`: server-generated operation UUID; tenant/actor; domain and aggregate ID; phase (`generation`, `transport`, `billing_step`); immutable request/schema digest; adapter/version; provider account/environment/API version; approval/grant reference and digest; parent/dependency operation ID; state; attempt fence; lease/deadlines; key; result/error classification; created/updated timestamps.
- `provider_attempts`: append-only attempt identity, fence, request digest, dispatch-start time, provider request/object IDs, received response classification, late-response evidence. No raw secret or unbounded provider body.
- `operation_artifacts`: versioned exact generated body or billing request snapshot, digest, bounded encrypted content or private durable-object reference. Blob upload must complete before the DB references it. A blob with no DB owner is an orphan to reconcile, never a ready job. Content is immutable; amendments create a new version needing review.
- `operation_events`: append-only actor, state transition, reason, evidence reference, old/new version and time.
- `billing_inbox`: verified source/account/environment + event ID + raw digest + verified/applied timestamps + processing state and failure. Unverified submissions go to a separate quarantine namespace, not this unique identity space.

Uniqueness is `(tenant, logical_operation_id, phase, request_version)` and `(provider_account, environment, provider_key)`, with immutable collision validation. Client idempotency strings are tenant-scoped, not global existence oracles. A different digest at an existing key is a conflict, not replay. No key contains an email or other sensitive identifier.

M24 owns billing operations and receipts. Claire goals reference the billing operation ID and expose its real outcome; they do not run a second money journal around it. For ordinary Claire effects, extend the existing authoritative GoalStore transaction to add outbox rows; do not separately commit approval, effect intent, then outbox. Across different stores, use a single owner transaction and an idempotent reference/projection handoff, not an imaginary cross-database atomic transaction.

## State model

`prepared -> dispatching -> succeeded` is the normal operation path.

Other states: `failed_before_dispatch`, `outcome_unknown`, `succeeded_late`, `cancelled_before_dispatch`, `closed_unknown`, and `legacy_unknown`.

- `prepared`: durable exact request and authority binding exist; no dispatch reservation has been committed. It may be claimed after its dependencies succeed and authority is rechecked.
- `dispatching`: attempt/fence committed before invocation. Expiration means uncertain, never automatically prepared again.
- `failed_before_dispatch`: only the still-active caller can attest that it did not enter the adapter; reclaim the same operation/key without a new permit, after revalidation.
- `outcome_unknown`: provider call may have started or succeeded. No blind retry. Expose a stable operation ID, uncertainty, status/readback route and safe next step; do not leak provider errors or encourage retry through a generic 500.
- `succeeded_late`: retain a bounded result even after lease expiry; prevent stale overwrite and redispatch. Reviewed acceptance may convert the recorded result to succeeded without invoking the provider.
- `closed_unknown`: terminal accounting closure retains uncertainty and holds the operation permanently. No renewed effect authorization. This matches the local memo3 terminal-close policy, not a claim it is already available in M24.
- `legacy_unknown`: historical dispatch evidence insufficient. Cannot be interpreted as fresh prepared work.

No `unknown -> prepared` generic HTTP button. A per-adapter adjudication can establish authenticated `committed` or `absent`, with evidence, reviewer, account, query scope and observation time. Reviewed retry is a new recorded decision using the original request/key when safe; new keys never hide an unresolved prior effect. Generation retries require a separate budget/authority decision and cannot mark an earlier uncertain charge absent.

## Write-ahead ordering

### A. Generation

1. Assemble bounded canonical prompt/context snapshot, model/version/options, intended private output, generation budget, privacy rules and operation ID. Store exact inputs or encrypted durable reference. Read cached or succeeded output before any model call.
2. In one transaction, validate generation authority/budget, reserve generation operation and queue reference. Commit and return a commit-confirmed operation. If commit fails or acknowledgment is ambiguous, read operation by server ID; no model call until durable commit is confirmed.
3. Claim using SQL CAS. Commit attempt/fence before model invocation. Request provider idempotency only where a verified adapter contract supports it; otherwise record that no deduplication capability exists.
4. Invoke generation. Persist the full validated output version/digest and mark generation succeeded in one transaction. Persist partial/ambiguous failure explicitly. A generation retry may produce different text or another charge; do not describe it as transport-safe merely because nothing was delivered.
5. Create transport only from durable successful output. Never send a transient response held only in worker memory. Generated decision/tool parameters in Claire must be stored as a resumable step checkpoint before executing the selected tool; another worker must not regenerate the same step and treat a changed decision as the same request.
6. For money/person-facing output, request review of final body/destination/amount and artifact version. A grant covering generation does not authorize disclosure, delivery or spending.

A generation that returned before storage failure remains generation-unknown. With no provider lookup/idempotency, default hold. Explicit owner-authorized regeneration may incur cost/change output, but must not create duplicate transport or silently replace an approved body.

### B. Transport or billing step

1. Read the durable exact request/output, complete audience/account/tenant and approval bindings, amount/currency, commitment/cancellation deadline, resource ownership and adapter capabilities. Fail before reservation if any are unresolved.
2. In one domain transaction, lock/version-check approval, validate unexpired/unrevoked scope and exact payload, consume its one permitted effect if required, create `prepared` operation and audit/queue reference. No provider I/O inside this transaction. Replay/pending/conflict must consume nothing new.
3. Claim `prepared` by CAS; commit attempt with a stable provider key and DB-based UTC lease. On an uncertain COMMIT response, read back the exact attempt/fence before invocation. Storage unavailable means no dispatch.
4. Check cancellation/revocation/deadlines immediately before invocation. This local check is not external conditional enforcement. Lease/authority lost before adapter entry records failed/cancelled-before-dispatch. After entry, uncertainty remains even if cancellation was requested.
5. Invoke exactly the serialized request under the recorded provider account/environment/version/key. A changed endpoint, account, payload or adapter version cannot reuse the operation invisibly.
6. Persist accepted response/object IDs, outcome and audit in one transaction. Local response persistence does not mean customer payment or recipient read. If receipt persistence fails, durable intent still makes the operation discoverable; return unknown with its operation ID.
7. Goal settlement and completion-notification outbox creation share one transaction in the authoritative goal store. Transport delivery has its own operation/key. Completing a goal is not sending its result.

Poll the durable prepared queue as the recovery path. Broker enqueue happens after commit and can be duplicated/lost without losing work. Worker acknowledgment follows durable outcome publication. Database durability requires verified PostgreSQL synchronous commit/WAL or SQLite WAL+synchronous FULL and sound storage; process-crash tests alone do not establish power-loss or failover durability. No Redis/broker-only queue or memory cache is a substitute.

## Crash and replay matrix

| Crash point | Durable truth on restart | Allowed continuation |
| --- | --- | --- |
| Before reservation transaction commits | No committed operation/consumption | Retry preparation; no provider call was authorized from uncommitted state. |
| Commit succeeded but caller did not receive acknowledgment | Operation may exist | Read back by stable ID; never create a new key to bypass uncertainty. |
| Prepared commit, before attempt claim | Prepared, no attempt | Claim after authority/dependency recheck. |
| Attempt commit, before actual provider call | Dispatching; indistinguishable from started call after process death | Adapter reconciliation; M24 requires reviewed provider lookup/absence evidence before retry. No inference from missing response. |
| During generation | Generation unknown; no durable output | Hold/reconcile or explicitly authorize regeneration; no transport allowed. |
| Output persisted, before transport queued | Successful immutable output | Transactional transport creation/replay by parent/version identity, no regeneration. |
| Provider accepted, before receipt commit | Unknown with committed attempt/key | Retrieve exact provider objects/evidence; persist acceptance without re-effect. |
| Receipt committed, before worker acknowledgment | Succeeded | Return persisted result, do not invoke adapter. |
| Lease expires while old caller runs | Unknown or late evidence | No replacement dispatch; retain late result under same attempt. A heartbeat extends only a live fence, with finite total runtime; cannot prove provider fencing. |
| Goal settled, before notification dispatch | Goal report + prepared notification if same transaction | Deliver separately after permission recheck, never rerun goal to notify. |
| After terminal close | Closed uncertain record | Read-only inspection; delayed responses append evidence but cannot reopen/retry without a new explicit adjudication. |

## M24-specific protocol

Persist separate operations for checkout, cancellation, invoice item and draft invoice. Stable keys derive from a server operation UUID and step role, stored BEFORE requests, not from attempt numbers. Bind keys to provider account/environment and exact form parameters. Preserve historical existing keys during migration where request identity is known.

Current invoice sequence must not be replayed as a single opaque pair. Each accepted step's object ID/result commits before the next step is eligible. Prefer a reviewed design that creates the draft invoice first, then attaches the item to that explicit invoice ID; otherwise explicitly control inclusion of pending items and avoid collecting unrelated customer items. Changing request order is a new behavior needing compatibility tests/review, not an incidental outbox repair. No automatic delete/refund/cancel compensation, invoice finalization, email or payment is added by this design.

Provider lookup must verify account/environment/customer/subscription ownership and request metadata/amount/currency, not trust a caller-provided ID or a bare metadata match. Negative evidence needs a documented authoritative query scope and propagation/consistency caveats. If no reliable absence proof exists, keep unknown or terminally close without retry. Multiple matches or uncertain lookup also hold.

Stripe's currently fetched documentation says POST idempotency keys can be pruned after at least24hours, reuse after pruning creates a new request, identical-key replays can return the first500, and GET/DELETE key headers have no effect. Therefore a key is not indefinite deduplication. Preserve first-attempt time, capability/version and an explicit retry-not-after bound. Passing a deadline stops automatic dispatch and requires reconciliation/review; do not refresh a key to get a new response. Cancellation's DELETE operation uses verified object state, not a supposed effective key header. Current client is test-mode-only; this design does not enable live mode.

Generation may be optional for billing descriptions. If a model is used, its durable output must be reviewed as part of the money payload before billing execution; generation approval cannot stand in for amount/destination confirmation.

## Incoming billing events are an inbox, not the transport outbox

Verify provider signature/account/environment BEFORE admission to the verified identity space. Persist pending verified event first; apply lifecycle state and mark applied in one transaction, or a pending inbox row retries apply without treating existence as processed success. Failed apply retains pending/error evidence and allows signed redelivery of the same digest. Same identity with changed digest is a conflict/quarantine. Unsigned diagnostics must not poison signed identities.

Checkout completion must verify the documented payment status and account/tenant mapping before entitlement activation; do not equate checkout created/completed with paid. Keep a monotonic per-resource provider event/version cursor; older events cannot overwrite newer state. Equal timestamps/conflicting events require deterministic policy or authoritative provider refresh, not arrival-order max assumptions. These are adjacent M24 defects, not proof that the outbox alone fixes billing state.

## Claire crash-journal integration

Preserve `begin_effect` atomic reservation+gate-consumption and RETURNING fix. Do not revert to unreliable ORM insert rowcount or split the approval transaction. Add generation operations before `model.decide`, persisted decision checkpoints after responses, and publication operations after durable report evaluation. `settle` plus notification creation must be transactional. Existing effect rows remain authoritative for non-read tools.

The landed review-branch slices prove limited local PG16 process boundaries: before-claim and committed-journal external SIGKILL, uncommitted INSERT rollback, subprocess resume, and scratch key-bound reconciliation. The HMAC is per-test evidence, not a product device/provider authenticity feature. Generation/transport kill points, PG server restart/failover and a complete approval rollback matrix were not established by those slices. The new seam must extend their actual barriers and PID/SQL assertions, not relabel them outbox tests.

M24 must override declaration-only `idempotent=True` takeover with the reviewed reconciliation rule. Any Claire wrapper around M24 returns operation status/reference and waits; it cannot re-enter the Stripe client on goal retry. Cancellation closes unsent work/unused authority, preserves already-started unknown effects. Integrate designated reviewer checks from Claire, not caller-supplied reviewer strings. Late evidence is truth to retain, not license for another effect.

Meemee webhook retries remain explicitly at-least-once and receiver-deduped. Their stable delivery ID is useful, but absent receipt or expired sending cannot justify money/person transport retry. Companion private generation and exact output need their own write-ahead rows; the local message+completion transaction remains a separate no-network case.

## In-flight migration and cutover

1. Inventory exact deployed heads and all worker entry points. Quiesce new dispatch, drain or fence old workers and wait bounded shutdown; a deployment flag alone cannot stop an already-running old process. Leave uncertain old callers quarantined rather than making them ready.
2. Add NEW revision(s) on actual heads, no edits/renames of applied revisions. Schema addition first; fail-closed adapters until compatible workers are deployed. Mixed old/new workers may not share a dispatch queue without a version/cutover barrier.
3. Backfill known persisted billing results as `legacy_recorded`, with source/evidence digest and ownership validation. Do not invent full reviewed request binding or original provider keys from the result alone. Such records block new dispatch and offer only verified readback.
4. Historical approved request without execution row may already have called Stripe. Classify as `legacy_unknown` unless authoritative evidence proves never dispatched. No blanket ready backfill, no minted fresh keys. Legacy queued-before-generation with proven no attempt can become prepared under current authority; legacy running check-ins without exact body are unknown and cannot be silently regenerated-and-sent.
5. Existing Claire committed effect receipts retain keys/state. Existing intent/unknown stays reconciliation-held; do not turn lease expiration into prepared. Link existing rows to new queue references idempotently. Plans/steps and GoalStore use different journals; migration records the source owner instead of duplicating effects.
6. Existing billing event IDs lack verified/applied separation. Mark imported historical rows provenance/apply-unknown where evidence is absent. Signed redelivery may process against a new verified namespace; apply dedup/version guards must protect existing entitlements, not reset them indiscriminately.
7. Enable new ingress before dispatch; then route all old execute endpoints through durable repository APIs. Remove/fail-close bypasses. Inventory shows old methods cannot call provider independently. Capability-version mismatch holds, not an implicit fallback.
8. Validate populated SQLite/PG upgrades, interrupted migration, old-reader compatibility and rollback. Populated downgrade refuses unless data is safely exported/retained; rollback never deletes unknowns or re-enables legacy dispatch. Preserve backups/counts, no bulk writes to a live user's billing data during this design task.

## Acceptance plan before implementation can be called ready

- Red controls on current direct M24 replay/receipt loss; green named controls with count of actual mock requests per step, two processes and one authoritative operation.
- Commit-failure/ambiguous-ack fixtures prove ZERO model/transport calls until committed request readback; intent and applicable approval consumption roll back together.
- Real PID-distinct SIGKILL: before commit, inside transaction, after prepared, after attempt commit before network, during generation, after output durable, during transport, after accepted response before receipt, after receipt before acknowledgment, after goal settlement before notification.
- Real PG restart with persisted WAL/config inspection separately from process kill; SQLite reopen/FULL settings; slow responses, clock skew, heartbeat maximum runtime and stale-fence controls. State what storage failures remain untested.
- Invoice first/second-step partial success, multi-match/negative lookup, pruned-key/expired-preview/customer mismatch/cross-account/cross-tenant refusal, malformed provider response, and late accepted result with no redelivery.
- Incoming invalid signature cannot reserve verified event ID; lifecycle apply failure can resume; unpaid checkout never activates; old event never regresses newer state.
- Generation restart reuses persisted output, does not change reviewed body, never sends without final destination/body approval; cancellation and grant revocation tested at each stage.
- HTTP tenant/auth/designated-reviewer boundaries and stable unknown/status contracts; logs redacted/bounded, encrypted artifacts/private access, retention excludes unresolved operation tombstones until safe archival.
- Changed data/adapter under existing key conflicts; original failure receipts and exact-node manifests retained. CI and full collected-node coverage labeled separately from live-provider acceptance.

## Open decisions and limits

Gate first reviews this design, particularly one-owner transaction integration, invoice order and legacy quarantine. No code until that verdict and parent direction. Provider adapter capability/lookup authenticity is unresolved until implemented and tested; generation providers need their own verified contracts. Authorization still gates money and person-facing disclosure, and the current test-only Stripe limit remains.

Durable-before-provider is achievable locally; exactly-once external effect is not promised. A discoverable unknown with no blind retry is preferable to a plausible receipt or silent duplication.

## Sources read

Repository paths above are pinned to the stated SHAs. Claire review branch is not Atlas main. Meemee was cloned read-only at its current SHA; existing webhook outbox is deliberately distinguished from missing Claire publication seam.

Current public provider references inspected:
- https://docs.stripe.com/api/idempotent_requests
- https://docs.stripe.com/api/invoices/create
- https://docs.stripe.com/api/invoiceitems/create

These describe provider mechanics, not deployment validation, user permission, or successful live integration. No credentials are included in this design.
