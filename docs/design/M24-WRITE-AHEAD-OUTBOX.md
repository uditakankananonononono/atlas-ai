# M24 write-ahead provider operations and Claire outbox seam

Status: DESIGN ONLY. No implementation, migration, provider call, or production guarantee.
Base: Atlas main `3719c6f8bb7c7b624c8b8e8acdc1287f2f64adc9`.
Read separately: Claire review branch `9a5ba1dac9726de0c3494d3f105aa4ebb5675462`; Meemee main `7cd6c7dca319789668725526f759c7ab9f05db69`.
Memo3 local ledger is not landed on main. Do not assume its table or interfaces exist in production.

Revision2 addresses gate critique of f47a183f. Still design only; required provider-account version verification and compatibility gates remain outstanding.

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
- `failed_before_dispatch`: a structural pre-network path only: request validation/serialization/claim verification happens outside the adapter invocation block; set an irreversible adapter-entered marker immediately before entering ANY adapter that can perform network I/O. Only exceptions before that marker may set this state. Never infer it from an exception after adapter return, rejected HTTP status, timeout or cancellation. A kill before adapter entry proves zero mock requests but a restart after an attempt commit still treats the dead caller as unknown, not as attested safe. Reclaim the same operation/key only after this durable, tested pre-entry classification and revalidation.
- `outcome_unknown`: provider call may have started or succeeded. No blind retry. Expose a stable operation ID, uncertainty, status/readback route and safe next step; do not leak provider errors or encourage retry through a generic 500.
- `succeeded_late`: retain a bounded result even after lease expiry; prevent stale overwrite and redispatch. Reviewed acceptance may convert the recorded result to succeeded without invoking the provider.
- `closed_unknown`: terminal accounting closure retains uncertainty and holds the operation permanently. No renewed effect authorization. This matches the local memo3 terminal-close policy, not a claim it is already available in M24.
- `legacy_unknown`: historical dispatch evidence insufficient. Cannot be interpreted as fresh prepared work.

No `unknown -> prepared` generic HTTP button. A per-adapter adjudication can establish authenticated `committed` or `absent`, with evidence, reviewer, account, query scope and observation time. Reviewed retry is a new recorded decision using the original request/key when safe; new keys never hide an unresolved prior effect. Generation retries require a separate budget/authority decision and cannot mark an earlier uncertain charge absent.

## Write-ahead ordering

### A. Generation

1. Assemble bounded canonical prompt/context snapshot, model/version/options, intended private output, generation budget, privacy rules and operation ID. Budget accounting has TWO explicit units: integer input/output tokens and integer micro-USD (one millionth of a dollar), with a pinned price schedule, currency conversion policy if needed, and maximum input/output limits. Local unmetered generation has zero monetary reservation but still reserves a token/compute-attempt allowance. Refuse a paid provider when a trustworthy maximum charge cannot be bounded. Store exact inputs or encrypted durable reference. Read cached or succeeded output before any model call.
2. In one transaction, validate generation authority/budget, reserve generation operation, unique budget-attempt entry and queue reference. Move maximum token allowance and priced cost from available to reserved now, before invocation. At the A3 attempt commit, mark the entry charged-pending (counts against the budget, never refunded automatically after a crash). Verified usage later settles actual spend and releases only proven unused reserve. Every regeneration attempt debits a NEW budget entry before invocation, including after a crash or timeout; prior ambiguous provider charge remains charged-pending. Generation retries therefore can consume the budget twice and are blocked if remaining budget or owner spending scope is insufficient. Commit and return a commit-confirmed operation. If commit fails or acknowledgment is ambiguous, read operation by server ID; no model call until durable commit is confirmed.
3. Claim using SQL CAS. Commit attempt/fence before model invocation. Request provider idempotency only where a verified adapter contract supports it; otherwise record that no deduplication capability exists.
4. Invoke generation. Persist the full validated output version/digest and mark generation succeeded in one transaction. Persist partial/ambiguous failure explicitly. A generation retry may produce different text or another charge; do not describe it as transport-safe merely because nothing was delivered.
5. Create transport only from durable successful output. Never send a transient response held only in worker memory. Generated decision/tool parameters in Claire must be stored as a resumable step checkpoint before executing the selected tool; another worker must not regenerate the same step and treat a changed decision as the same request.
6. For money/person-facing output, request review of final body/destination/amount and artifact version. A grant covering generation does not authorize disclosure, delivery or spending.

A generation that returned before storage failure remains generation-unknown. With no provider lookup/idempotency, default hold. Explicit owner-authorized regeneration may incur cost/change output, but must not create duplicate transport or silently replace an approved body.

### B. Transport or billing step

1. Read the durable exact request/output, complete audience/account/tenant and approval bindings, amount/currency, commitment/cancellation deadline, resource ownership and adapter capabilities. Fail before reservation if any are unresolved.
2. In one domain transaction, lock/version-check approval, validate unexpired/unrevoked scope and exact payload, consume its one permitted effect if required, create `prepared` operation and audit/queue reference. No provider I/O inside this transaction. Replay/pending/conflict must consume nothing new.
3. Claim `prepared` by CAS; commit attempt with a stable provider key and DB-based UTC lease. On an uncertain COMMIT response, read back the exact attempt/fence before invocation. Storage unavailable means no dispatch.
4. Check cancellation/revocation/deadlines immediately before invocation. Acceptance covers cancellation BEFORE adapter entry only; cancellation requested after dispatch does not promise stopping, retracting or undoing an external effect. This local check is not external conditional enforcement. Lease/authority lost before adapter entry records failed/cancelled-before-dispatch. After entry, uncertainty remains even if cancellation was requested.
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

### Version pin and exact new invoice request sequence

New docs-based risk, NOT a proven live defect: current code creates an invoice item then a draft with no `pending_invoice_items_behavior`. The fetched current invoice-create docs say omitted behavior defaults to `exclude`. Current code sends no `Stripe-Version`; the account's default API version determines actual current behavior, which has not been read from a live Stripe account. The approved item may therefore be missing from the draft. Do not claim this happened to a customer.

For NEW operations propose `Stripe-Version: 2026-09-30.endive` on every request, pinned in adapter configuration and immutable operation snapshot; this is the version named by the currently fetched versioning docs. Verify availability/compatibility in the account's TEST environment before implementation readiness; an unsupported version fails closed, never silently falls back. Webhook endpoint version is separately pinned/verified. Legacy in-flight requests keep their recorded/original version; an unknown original version cannot be upgraded during same-key replay.

One authoritative request snapshot includes the exact following parameters (plus authentication and the bound account/environment headers). Let O be the server-generated parent operation UUID, C the verified customer, A the approved integer amount in minor units, and U the approved lower-case currency. No tax/discount change is silently added.

1. Commit draft-step operation/key `O:draft-invoice` before `POST /v1/invoices` with `customer=C`, `currency=U`, `auto_advance=false`, `pending_invoice_items_behavior=exclude`, `metadata[atlas_operation_id]=O`, `metadata[atlas_operation_step]=draft-invoice`, `metadata[atlas_approval_id]=approval_id`. No finalization/send/pay call. Persist returned invoice ID I before step2 becomes eligible.
2. Commit item-step operation/key `O:invoice-item` before `POST /v1/invoiceitems` with `customer=C`, `invoice=I`, `amount=A`, `currency=U`, `description=approved_description`, `discountable=false`, `metadata[atlas_operation_id]=O`, `metadata[atlas_operation_step]=invoice-item`, `metadata[atlas_approval_id]=approval_id`. Explicit `invoice=I` prevents loose customer pending-item association. Persist item ID and result before marking the parent complete. Metadata additions and reversed order change bodies and require compatibility review.
3. `GET /v1/invoices/I` (read operation, not a mutation retry), paginate all line items if required, assert `status=draft`, correct customer/currency/environment, exactly the intended item binding and final `total=A`. If existing customer defaults/tax/discounts produce another total, hold as mismatch: no claim of approved success and no automatic deletion/compensation. Contract test MUST expose the old omitted-item default and enforce the new final approved total under the pinned version.

Current invoice-item-first in-flight operations MUST NOT be converted to draft-first or receive new metadata under their old keys. Preserve `{approval_id}:invoice-item` and `{approval_id}:draft-invoice`, original parameter snapshots/version if known, and partial step evidence. Missing original parameter/version/accepted item ID requires legacy-unknown reconciliation, not fabricated reconstruction. No automatic delete/refund/cancel compensation, finalization, email or payment is added.

### Exact lookup handles and reviewer evidence

Every NEW create call gets opaque `metadata[atlas_operation_id]` and step metadata before first dispatch. Checkout also keeps existing `metadata[atlas_approval_id]` and `client_reference_id=tenant_id`; current checkout code ALREADY has the approval metadata, contrary to any blanket claim that it has none. Current invoice item lacks it. Do not add metadata when replaying a legacy same-key request: that changes parameters.

| Step | Exact handle/read path | Search/consistency limit and reviewer view |
| --- | --- | --- |
| Checkout create | If persisted: `GET /v1/checkout/sessions/{cs_id}`. Lost ID: paginate `GET /v1/checkout/sessions?limit=100&starting_after={cursor}` under the same account/environment; locally filter metadata operation UUID/step or legacy approval ID, client reference, mode, created time and approved price fields. If subscription ID was independently persisted, the documented list `subscription={sub_id}` filter can narrow it. | No generic Checkout metadata SEARCH or customer filter is assumed from the inspected session-list docs. Account-wide scan may be incomplete/expensive; any page failure/cap/uncertain observation yields unknown. Reviewer sees account/version, time bounds, complete page count, matching session IDs/status/payment_status and exact binding checks. No guarantee that an empty list proves absence. Without a complete trustworthy handle/query, stay unknown. |
| Draft invoice create | If persisted: `GET /v1/invoices/{I}`. Lost ID: paginate `GET /v1/invoices?customer=C&limit=100&starting_after={cursor}`, filter exact operation UUID+step or legacy approval metadata, currency, draft state and request binding. Discovery-only alternative: `GET /v1/invoices/search?query=metadata['atlas_operation_id']:'O'` with properly encoded query. | Invoice SEARCH is indexed, not read-after-write: docs say normally <1minute, up to1hour in outages, unavailable to merchants in India. Never establish absence from search; use list/retrieve to validate positive candidates. List consistency has no reviewed absence guarantee here. Reviewer sees candidate IDs, account/customer, query/pages/time, metadata and line/total checks. No reliable absence proof means unknown. |
| Invoice item create | Persisted ID: `GET /v1/invoiceitems/{ii_id}`. Lost ID: paginate `GET /v1/invoiceitems?customer=C&limit=100&starting_after={cursor}`, locally filter operation UUID/step and `invoice=I`, amount/currency/description. For legacy no-metadata item, require independent item ID or other authoritative exact binding; amount/time alone is not unique. | No invoice-item metadata SEARCH endpoint assumed. No empty-page absence guarantee established. Reviewer sees all candidate IDs/bindings, query coverage and whether the item is attached to I. Duplicate/missing/legacy-no-handle stays unknown; never rerun item to find out. |
| Subscription cancel DELETE | Reviewed subscription ID is already the handle: `GET /v1/subscriptions/{sub_id}`, same account/environment, verify customer and tenant mapping plus cancellation fields/status. | Header key offers no DELETE dedupe benefit. Current state may show cancellation but does not attribute who caused it. Reviewer sees before snapshot, current status/canceled_at and ownership evidence. A missing object/403/stale read is not proof of this operation's success or safe retry. If uncertain, stay unknown. |
| Model generation | Stored provider response/request ID, if that specific adapter exposes a documented authenticated retrieve API; otherwise no lookup handle. | No universal model-query protocol assumed. Reviewer sees request/model/version/budget attempt, any returned output digest and charge status. No handle means generation-unknown; explicit regeneration uses a new budget entry/approval and never creates transport from lost output. |

Positive matches validate object identity/request binding before being accepted; bare metadata is not proof of authorization. Reviewer approval is recorded with evidence digest, authenticated designated actor, observation UTC, provider account/environment and limitations. This design supplies no automatically authoritative NEGATIVE provider lookup: until an adapter proves sufficient absence semantics, ambiguous M24 remains unknown regardless of whether the key is young.

Provider lookup must verify account/environment/customer/subscription ownership and request metadata/amount/currency, not trust a caller-provided ID or a bare metadata match. Negative evidence needs a documented authoritative query scope and propagation/consistency caveats. If no reliable absence proof exists, keep unknown or terminally close without retry. Multiple matches or uncertain lookup also hold.

Stripe's currently fetched documentation says POST idempotency keys can be pruned after at least24hours, reuse after pruning creates a new request, identical-key replays can return the first500, and GET/DELETE key headers have no effect. Therefore a key is not indefinite deduplication. Persist `first_attempt_at_utc` once per key in the claim transaction and never reset it. Set `automatic_dispatch_not_after = first_attempt_at_utc + 12 hours`, further shortened by the approved cancellation/commitment deadline and authority expiry. Stop at or after the bound and require review;12hours is a conservative local policy, not a provider retention promise. The bound is necessary but NOT sufficient for retries: ambiguous M24 still requires reviewed lookup/absence proof even within12hours. With unknown first-attempt time, automatic dispatch is disabled. Passing a deadline stops automatic dispatch and requires reconciliation/review; do not refresh a key to get a new response. Cancellation's DELETE operation uses verified object state, not a supposed effective key header. Current client is test-mode-only; this design does not enable live mode.

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

1. Inventory exact deployed heads and all worker entry points. Set concrete cutover `dispatch_protocol_epoch=2` with DB-CAS claims requiring both operation epoch2 and adapter protocol2. The DB rejects mismatches/old claim writes through the reservation API (test epoch1 claims refused). Quiesce new dispatch and allow60seconds for cooperative worker shutdown; then terminate/fence remaining old workers and quarantine unresolved operations. Existing legacy workers can bypass the new DB API and call Stripe directly, so a DB barrier alone cannot stop them: revoke/rotate old provider credentials or enforce egress isolation, verify no old worker holds usable credentials before enabling epoch2. Rotation/termination is a separately approved cutover operation, not executed by this design. Drain or fence old workers and wait bounded shutdown; a deployment flag alone cannot stop an already-running old process. Leave uncertain old callers quarantined rather than making them ready.
2. Add NEW revision(s) on actual heads, no edits/renames of applied revisions. Schema addition first; fail-closed adapters until compatible workers are deployed. Mixed old/new workers may not share a dispatch queue without a version/cutover barrier.
3. Backfill known persisted billing results as `legacy_recorded`, with source/evidence digest and ownership validation. Do not invent full reviewed request binding or original provider keys from the result alone. Such records block new dispatch and offer only verified readback.
4. Historical approved request without execution row may already have called Stripe. Report counts by class before enabling dispatch: approved-no-result approval-age<24h, age>=24h, timestamp-unknown; recorded result; proven unattempted; partial item/draft; Claire pending/committed; unsigned legacy inbox; verified unapplied. Approval age is an UPPER bound on elapsed time since a call made after approval, not the actual key age; actual dispatch may be later. An approval younger than24hours bounds a post-approval call age, but still does not prove dispatch timing, key retention, account/version binding or absence. An older approval does not prove its key is old, so classify it conservatively rather than inventing first-attempt time. Inside24h remains legacy_unknown until reconciliation, not ready. Outside24h or unknown time disables same-key automatic dispatch because the pruning window may have passed; still reconcile/hold, never create a fresh key to avoid it. Count/source-ID export and unresolved inventory signoff are cutover prerequisites. Classify as `legacy_unknown` unless authoritative evidence proves never dispatched. No blanket ready backfill, no minted fresh keys. Legacy queued-before-generation with proven no attempt can become prepared under current authority; legacy running check-ins without exact body are unknown and cannot be silently regenerated-and-sent.
5. Existing Claire committed effect receipts retain keys/state. Existing intent/unknown stays reconciliation-held; do not turn lease expiration into prepared. Link existing rows to new queue references idempotently. Plans/steps and GoalStore use different journals; migration records the source owner instead of duplicating effects.
6. Inbox migration ORDER: create the new verified namespace keyed by(provider account,environment,event ID) FIRST and deploy signed admission/apply code against it, with legacy IDs isolated and never satisfying verified dedupe. Next import only independently verifiable signed legacy entries with distinct verified/applied markers; leave uncertain provenance quarantined. Disable or reroute unsigned `/events` away from verified namespace before enabling processing; unsigned diagnostics are moved LAST to a separate table with no unique-key collision access. Test a pre-existing unsigned legacy ID followed by a valid signed same-ID event: signature verified, new verified pending row created, lifecycle applied once, later signed duplicate dedupes; the unsigned row cannot mark it processed. Existing billing event IDs lack verified/applied separation. Mark imported historical rows provenance/apply-unknown where evidence is absent. Signed redelivery may process against a new verified namespace; apply dedup/version guards must protect existing entitlements, not reset them indiscriminately.
7. Enable new ingress before dispatch; then route all old execute endpoints through durable repository APIs. Remove/fail-close bypasses. Inventory shows old methods cannot call provider independently. Capability-version mismatch holds, not an implicit fallback.
8. Validate populated SQLite/PG upgrades, interrupted migration, old-reader compatibility and rollback. Populated downgrade refuses unless data is safely exported/retained; rollback never deletes unknowns or re-enables legacy dispatch. Preserve backups/counts, no bulk writes to a live user's billing data during this design task.

## Acceptance plan before implementation can be called ready

- Red controls on current direct M24 replay/receipt loss; green named controls with count of actual mock requests per step, two processes and one authoritative operation.
- Mock Stripe readiness gate enforces stable keys, parameter comparison, first-result500replay and24hour pruning; it must reproduce the old omitted-pending-item risk and the pinned draft-first explicit-item attachment/total=A contract. Count provider CALLS and distinct EFFECTS separately per step across crashes; not just parent success count.
- Commit-failure/ambiguous-ack fixtures prove ZERO model/transport calls until committed request readback; intent and applicable approval consumption roll back together.
- Real PID-distinct SIGKILL: before commit, inside transaction, after prepared, after attempt commit before network, during generation, after output durable, during transport, after accepted response before receipt, after receipt before acknowledgment, after goal settlement before notification.
- Real PG restart with persisted WAL/config inspection separately from process kill; SQLite reopen/FULL settings; slow responses, clock skew, heartbeat maximum runtime and stale-fence controls. WAL/power-loss/failover durability remain explicitly UNTESTED until separate evidenced tests; no mock/process kill upgrades that claim. State what storage failures remain untested.
- Kill immediately after invoice-item acceptance BEFORE committed item ID: pending intent stays unknown, reconciles the exact item rather than re-creating it. Expired lease+late response appends evidence but never redispatches/reopens terminal work. Changed payload/account/version under an existing operation/key errors. Generation crash/retry produces a NEW charged-pending budget entry and cannot release ambiguous prior spend.
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
- https://docs.stripe.com/api/versioning
- https://docs.stripe.com/api/checkout/sessions/list
- https://docs.stripe.com/api/checkout/sessions/retrieve
- https://docs.stripe.com/api/invoiceitems/list
- https://docs.stripe.com/api/invoices/list
- https://docs.stripe.com/api/invoices/search
- https://docs.stripe.com/api/invoices/retrieve
- https://docs.stripe.com/api/subscriptions/retrieve

These describe provider mechanics, not deployment validation, user permission, or successful live integration. No credentials are included in this design.
