# Step 2B design note v2: `Service.local_action` fail-closed approval binding (DESIGN ONLY, no code)

Base: `5e1001dd6a52c10150d810dce3cb5c72ada0bb61` (claire-runtime-m1). v1 was 75c65aa4; v2 folds in the review of v1. Problem statement: audit row 4 of `m21-gate-coverage-audit-404e01a7.md`.
Limits for the whole note: no role/designation check (m00 decide path untraced), no actor binding at m00, no daemon token validation, no attestation of OS execution, no durable local-effect journal,
no whole-product claim. The change closes ONE gap: the Service accepting any non-empty string as an approval. Structural guard only; this is not role closure.

## Today (file:line at base)
- `m21_claire/service.py:43-60` `local_action`. High-risk = fixed kind set, or lexical `ActionPolicy.requires_approval`, or caller-supplied `external_effect` (`:50-54`).
- `:55-56` high-risk without a token files `request_environment_change`; payload = goal_id, tenant_id?, environment, daemon `preview`, rollback. It does NOT bind the action.
- `:57` any truthy token reaches `local_client.execute(action, token)`; nothing checks it. Pinned by `test_m21_legacy_policy_superset.py::test_local_action_gates_comms_verb_and_blocks_standing_no` and the audit CHARACTERIZATION test.
- `:59` the goal is read AFTER execute: an unknown goal id raises KeyError after the effect ran. `local_action` has no tenant/actor check at all (`owned`, `:31-35`, is used only by routes).
- Facade `core/approvals.py:6-13` `ApprovalStore.put` passes no ttl; `list` returns `ApprovalRequest` (id, module, action_type, payload, status) with NO user_id/approved_by/decided_at/expires_at.
- m00: `_expire_if_overdue` (`m00_approval_center/service.py:333-340`) expires only PENDING rows, so a TTL bounds review time, not how long an APPROVED permit stays usable. `consume_effect` (`:565-588`) is atomic and exact-request-bound but has no age check and replays `allowed=True` for an identical effect_id.
- No route or in-tree caller; production wiring has no local_client (`routes.py:12`): no deployed path is affected until an integrator wires one.

## Proposed behaviour
### A. Order of operations in `local_action(goal_id, action, approval_token=None, *, tenant_id=None, actor_id=None)`
1. Snapshot: require `action` to be plain JSON (as `runtime/gates.py:54-58`), then `json.loads(json.dumps(action, sort_keys=True))` into a private immutable snapshot BEFORE any await. Digest, FORBIDDEN scan, policy tags, preview, consume and execute all use that snapshot (the client receives its own deep copy of the snapshot each time, so a mutable caller dict or a client mutation cannot drift what was approved). Non-JSON = refuse.
2. Goal lookup and owner check come FIRST for ALL calls, high-risk or not (before capabilities, preview or any await): unknown goal or mismatch -> the same `KeyError` as `owned`.
   Legacy rule (explicit): a goal with no owner record, or an owner record of (None, None), is LEGACY. A legacy goal accepts only calls with tenant_id=None and actor_id=None and may run NON-high-risk actions as today; a HIGH-RISK action on a legacy goal is refused because the approver-differs rule has no defined actor. Owned goals require matching non-blank tenant_id and actor_id.
   This is a behaviour change for non-high-risk calls too (owner check added): called out, and pinned by tests.
3. Existing checks unchanged: FORBIDDEN, capabilities, preview, lexical policy, high-risk classification.
4. High-risk without token: files the request as today but now with `goal_id` and `action_digest` (sha256 of canonical JSON of {goal_id, kind, action}) in the payload, pending TTL 24h (see B), returns it. Does not execute.
5. High-risk with token: `approval_token` is a Module 0 approval id. Verify via a NEW full-view accessor, then consume, then execute (see C and D).

### B. Full-view accessor and expiry separation (review items 1 and 2)
- New facade method `core/approvals.py::ApprovalStore.full_view(approval_id) -> dict` returning the m00 view (id, module_id, action_type, payload, user_id, status, decided_at, approved_by, expires_at). Existing `put`/`list` behaviour is unchanged, so no existing caller changes. `put` gains an optional keyword `ttl_seconds=None` (default unchanged).
- Verification from the full view, all required: module_id 21; action_type `claire:<kind>`; user_id == goal tenant; payload.goal_id == goal; payload.action_digest == digest of THIS snapshot; status APPROVED; `approved_by` non-blank and != caller actor (structural self-approval guard only); decided_at present.
- The permit is consumed against the STORED reviewed payload from that view (never re-derived from the preview the daemon produced, never from the caller), so the m00 request hash covers the exact reviewed record, and the digest in it binds the action.
- Two separate time controls, both named constants: PENDING review TTL = 24h via `put(ttl_seconds=...)` (existing m00 semantics: only PENDING expires); APPROVED execution validity = 15 MINUTES (900s, inclusive) from `decided_at`, enforced where the race lives: `consume_effect` gains an optional keyword `max_age_seconds=None` (default None keeps every other caller unchanged). Inside the SAME transaction as the effect-row insert it computes `now` from the service's injected clock (aware, via `_aware`), requires `decided_at` not null and `now <= _aware(decided_at) + max_age`, else `ApprovalConflictError("approval is stale")` before any row is written. A get-time precheck is NOT relied on. Boundary: exactly decided_at + max_age is valid, one microsecond later refused. Clock anchor: decided_at is written by the m00 service clock at decide time.
- Touching m00 `consume_effect` is a change to shared Module 0 code: one optional keyword, default off, no change to decide, submit, expiry or policy paths.

### C. Single use, no refund, no auto-retry (items for the effect)
- `consume_effect(approval_id, module_id=21, action_type, payload=<stored payload>, user_id, effect_id=<fresh uuid4 per call>, actor, max_age_seconds=APPROVED_VALIDITY)`. A fresh effect_id per call is deliberate: an identical effect_id replays `allowed=True`, which would allow a double run on retry. Second use of the same approval -> "already consumed" -> refuse.
- Permit must come back as a dict with `allowed is True`, `approval_id` and `effect_id` equal to what we sent; anything else (missing key, falsy, other id) -> refuse. If the store lacks `full_view` or `consume_effect` -> refuse (fail closed). Fixed refusal messages; no `str(exc)`; named exceptions only (`ApprovalNotFoundError`, `ApprovalConflictError`, `ValueError` from our own checks).
- A consumed approval is never refunded. The Service never retries `local_action` (no loop exists; test asserts one client call). Any retry needs a NEW approval.

### D. Execute / audit and unknown outcome
- Immediately after consume and before `local_client.execute`, append `{"local_action": kind, "approval_id": id, "outcome": "unknown"}` to the goal's evidence (intent marker). On success, replace it with the result entry. A `try/finally` flag leaves the marker as "unknown" if `execute` or `audit` raises; the exception then propagates (no blanket `except`), so callers must not render it. Surfaced limit, stated: the marker lives in the in-memory goal state, it is not a durable journal and does not survive a process restart (durable local-effect journal is out of scope). If `execute` succeeded but `audit` fails, the result is kept and the marker records `audit_failed`.
- The daemon still gets `execute(snapshot, approval_id)`; we do not claim the daemon validates the id.

## What stays unchanged
High-risk classification (kind set, lexical policy, `external_effect`), FORBIDDEN list, capability and preview calls, non-high-risk execution (no approval needed), the m00 dispatcher allowlist refusing `claire:*`, routes, schemas, migrations (none), m00 decide/submit/expiry semantics.

## Out of scope (stated, not closed)
Approver role/designation and who may call m00 decide; actor binding at m00; a durable local-effect journal and restart-safe unknown-outcome; lexical classification gaps (an effectful kind with `external_effect` omitted stays ungated); device-to-action binding; production wiring of a local client; daemon-side token validation; m20 loop and orchestrator approval weaknesses (audit rows 2 and 5); whole-product claims.

## Tests (labels). Each NEW test must fail on base 5e1001dd.
- CONVERTED: `test_local_action_gates_comms_verb_and_blocks_standing_no` (token "tok" executes `dm` today; now refused, exact approved approval on an owned goal executes once) and the audit CHARACTERIZATION test.
- NEW local_action: unknown/bogus id; PENDING; DENIED; pending-expired; APPROVED but stale (decided_at older than the window) refused; boundary exactly at window valid, +1us refused; concurrent consume crossing the boundary (one execution at most, zero when stale); different args/goal/kind/tenant; self-approved; blank approved_by; route-filed (no digest); second use refused with one client call; concurrent double use one executes; consume precedes execute; consumed stays consumed after execute failure and marker is "unknown"; audit failure keeps result and marks audit_failed; store lacking `full_view`/`consume_effect` refuses; permit with allowed != True or wrong ids refuses; non-JSON action refused; caller mutation of the action dict after validation and during await does not change what is previewed, consumed or executed; unknown goal refused before preview/execute/await; non-high-risk call on an owned goal with missing/foreign identity refused; legacy goal: high-risk refused, non-high-risk still runs; no `str(exc)` in any refusal; filed request carries goal_id + action_digest + pending TTL.
- NEW m00: `consume_effect(max_age_seconds=None)` behaves exactly as before; stale/boundary/null decided_at; clock injection and aware/naive datetimes.
- PROTECTION: FORBIDDEN refusals, non-high-risk actions unchanged, no-token high-risk still files a request and does not execute, unwired client RuntimeError, existing m21 policy-superset and m00 consume tests green.

## Decisions adopted from review
24h pending TTL and 15-minute approved validity as separate named constants (PENDING_REVIEW_TTL_SECONDS, APPROVED_VALIDITY_SECONDS); `approved_by != actor` as a structural guard, never role closure, legacy/default actor high-risk refused; no refund, no auto-retry.
Open for review: (a) the `try/finally` marker lets the raw client exception propagate; say if you want a named wrapper exception instead (the client is an external Protocol, so I have no closed class list to catch); (b) RESOLVED by the parent: approved validity is 15 minutes.

## v3 implementation notes (slice 15, supersede wording above where different)
- Approved validity: valid iff 0 <= now - decided_at <= 900s, evaluated with a FRESH aware clock read inside the consuming transaction after the approval row lock (`with_for_update` on databases that support it; on SQLite the unique constraint serializes and an IntegrityError is mapped to the fixed "already consumed" conflict). `max_age_seconds` must be a positive finite non-bool int/float, else ValueError.
- Non-high-risk wording: the approval requirement is unchanged; the owner check and plain-JSON check now apply to ALL calls.
- Preview: the fresh preview must equal the reviewed (stored) preview as canonical JSON, else refused and the approval is NOT consumed (fresh review required). Honest gap: a daemon preview with volatile fields (timestamps) will force a re-review every time; semantic comparison of recipient/destination/cost/device is not attempted.
- Unknown outcome: named `LocalActionOutcomeUnknown` with a fixed message and the client exception chained as `__cause__`; `except Exception` only at the client execute boundary; cancellation (BaseException) leaves the unknown marker; audit errors are swallowed at the audit boundary into an `audit_failed` marker (result kept). Unknown must be reconciled before any retry; a new approval is a prerequisite, not permission to repeat.
- Keyword `ttl_seconds` is passed to the store `put` only when set (24h for local-action requests).

## Addendum: SQLite / contention caveat (published code 36f9f3ca)
`consume_effect` takes `with_for_update=True` on the approval row; that is a real row lock only on databases that support it (Postgres). SQLite ignores it, so there the at-most-one guarantee comes from the UNIQUE constraints on `approval_id` and `effect_id` plus commit ordering (the 8-thread test exercises this). Under contention a caller can see a database error (for example "database is locked" or an IntegrityError mapped to the fixed "already consumed" conflict) rather than the fixed "local action approval refused" message; the effect still runs at most once. This is documented behaviour, not a code change. Postgres row-lock behaviour was not exercised by these tests.
Carried bounds: no role/designation authorization; no m00 actor binding, daemon token validation, device attestation or production wiring; the unknown-outcome marker is in-memory, not durable; a new approval is not proof that an uncertain earlier effect is safe to repeat.
