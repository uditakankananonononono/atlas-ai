# Design note: m20 legacy DeliberativeLoop approval binding (DESIGN ONLY, no code)

Base: `36f9f3ca42646a5c6dc59a44115721d07ed87c8b` (claire-runtime-m1). Follows audit row 2 and the open lead in row 8 of `m21-gate-coverage-audit-404e01a7.md`.
Limits for the whole note: no role/designation authorization (m00 decide path untraced), no whole-product claim, in-memory run state, no daemon/device claims. Paths relative to `backend/app/`.

## Which runtime this is
Module 20 has two runtimes. The newer `m20/service.py` CognitiveWorkerService (SafetyGate + ToolDispatcher, `tests/modules/test_m20_dispatcher_effect_boundary.py` already pins "external partial failure is not retried under one approval" and an outcome-unknown summary) is NOT touched here and is not audited here. This note covers only the legacy `m20/legacy_service.py` Service / DeliberativeLoop, which is what `m21_claire/service.py:61` (`self.cognitive.start(...)`, reached from `/claire/goals/{id}/realize`) and `m20/routes.py` `bind_service` expect. It is still unreachable in tree until an integrator binds a service (`m20/routes.py:46-54` 503), so nothing below changes a deployed path today.

## Gaps, with file:line at base
G1 tenant-less filing. `legacy_service.py:139` files `cognitive:<tool>` with payload {run_id, step_id, title, arguments, risk} and no tenant. `core/approvals.py:8` then files it under user "default". Any approver of "default" can decide any tenant's step, and a tenant's own approver queue does not contain it.
G2 unfiltered, capped lookup. `:141` `next(x for x in self.approvals.list() if x.id==step.approval_id)`. The facade `list()` with no user_id returns the newest 100 rows across ALL tenants and modules (`m00_approval_center/service.py:205-227`). The id is system-generated (not model-controllable: the planner builds Step positionally, `:85`, and never sets `approval_id`), so this is not an injection path, but a decided approval older than 100 newer rows disappears and the step waits forever (`:142` `not req` returns), and the check is not tenant-scoped.
G3 not payload-bound. The approval stores `step.arguments` at filing time but dispatch (`:146`, `ToolRegistry.dispatch :103-108`) runs the CURRENT `step.arguments`/`tool`/`risk`; nothing compares them to what was approved. Run/step objects are mutable in memory between approval and dispatch.
G4 not single-use, double dispatch. A failed approved EXTERNAL/IRREVERSIBLE step goes back to PENDING and retries up to `max_attempts` (`:148-149`) under the same approval with a new key `run:step:attempt`; an uncertain effect can run again. Pinned today by the audit CHARACTERIZATION test.
G5 no actor. `Service.start(goal, constraints, budget)` (`:166`) has no actor, so "approver differs from the requester" cannot be expressed. m21 `realize` knows (tenant, actor) from `_owners` but does not pass it.
G6 no age bound on an APPROVED decision.

## What Step 2B (slice 15) already closed, and what it did NOT
Closed (m21 `Service.local_action` only): exact-action digest binding, Module 0 `consume_effect` single use, 15-minute approved validity (`max_age_seconds`), `approved_by != actor`, owner-first, unknown-outcome marker. Not touched: the m20 legacy loop above, `ExecutionOrchestrator`, the m00 decide path. Reusable pieces already published: facade `full_view`, `consume_effect`, `put(ttl_seconds)`, m00 `consume_effect(max_age_seconds=...)`. So this slice adds NO new m00 or facade primitive; it applies those to the m20 loop.
Remaining m20-side after 2B: G1-G6.

## Proposed behaviour (what CHANGES), EXTERNAL and IRREVERSIBLE steps only
1. Run identity: `Service.start(goal, constraints, budget, *, tenant_id=None, actor_id=None)`; `Run` records them. m21 `realize` passes the goal owner's tenant and actor. A step that needs approval on a run with no tenant or no actor is BLOCKED fail-closed ("approval binding unavailable"), never filed under "default". (Legacy runs with no identity can still run READ/REVERSIBLE steps as today.)
2. Filing: payload adds `tenant_id`, `run_id`, `step_id`, `tool`, `risk`, and `step_digest` = sha256 of canonical JSON {run_id, step_id, tool, risk, arguments}; filed with pending TTL 24h; the approval is read back by id through `full_view` (never `list()`), fixing G1 and G2.
3. Dispatch gate (immediately before the tool handler, after the cheap pre-checks `tool unavailable` and `tool risk differs`, which keep the approval unconsumed): `full_view` must show module 20, `cognitive:<tool>`, user_id == run tenant, matching run_id/step_id/step_digest of the CURRENT step, status APPROVED, decided_at present, nonblank `approved_by` != run actor; then `consume_effect` with a fresh uuid effect_id and `max_age_seconds=900`; permit must be `allowed is True` with matching ids. Fixes G3, G5 (structural guard only), G6. Strict snapshot: `step.arguments` is deep-copied from validated plain JSON before the digest and passed to the handler as that copy.
4. After consume, any handler error, timeout or cancellation on an EXTERNAL/IRREVERSIBLE step leaves the step BLOCKED with `error="outcome unknown"` and NO retry (no PENDING, `attempts` not reused); the approval stays consumed and a new approval does not prove the earlier effect is safe to repeat. READ and REVERSIBLE retry behaviour is unchanged. Fixes G4.
5. Fail closed: a store without `full_view`/`consume_effect`, any named m00 error, or a malformed view = the step stays BLOCKED with a fixed message; no `str(exc)` in text (the current `:149` stores `f"{type(e).__name__}: {e}"` in `step.error`; for EXTERNAL/IRREVERSIBLE steps this becomes the class name only).

## What stays unchanged
READ/REVERSIBLE steps; the risk-annotation check (`tool.risk != step.risk`) and its limit that effect class is whatever the integrator registered (not validated; stays an unsafe assumption, not closed); the scheduler, planner and trace shapes; the newer CognitiveWorkerService; m21 routes and schemas; no migration.

## Out of scope (stated)
Approver role/designation and the m00 decide path; effect-class validation of integrator tools; a durable journal (outcome-unknown is in-memory run state); other m20 routers and agi routes; tools an integrator binds; production wiring; whole-product claim.

## Compatibility and test impact
In-tree tests use the legacy loop with fake approval stores: every test that drives an EXTERNAL/IRREVERSIBLE step to dispatch (list to be enumerated by grep in the implementation step; `tests/modules/test_m20_*.py`, the audit file's `_cog` probes, `test_m20_combined_merge_canaries`, `tests/integration/test_m17_m20_cross_module_proofs.py` are candidates) will be CONVERTED to a real Module 0 store with identity, or documented as legacy. Decision requested: strict by default (recommended, because nothing in tree binds this service) versus an explicit opt-in flag that leaves today's weak behaviour as the default; I recommend strict, with a named exception only for READ/REVERSIBLE.

## Tests (labels, each NEW must fail on base)
CONVERTED: audit CHARACTERIZATION "approval is not single-use, retry dispatches twice", "trusts registered risk annotation" stays a CHARACTERIZATION. NEW (real Module 0 on file SQLite + injected clock, real thread concurrency): approval filed with tenant/run/step/digest and TTL; decision by the wrong tenant's user not accepted; list-cap case (approval older than 100 newer rows) still resolves by id; changed arguments/tool/risk after approval refused without consuming; self-approved and blank approver refused; stale, boundary, future decided_at; concurrent double-dispatch yields one effect; handler failure/timeout/cancellation => BLOCKED outcome unknown, no retry, approval stays consumed; READ/REVERSIBLE retry unchanged; missing identity => BLOCKED; store lacking methods fails closed; fixed messages. PROTECTION: pre-dispatch refusals (tool unavailable, risk differs) leave the approval unconsumed; risk annotation limit documented.

## Implementation addendum (slice 16)
Milestone label unchanged: partial read-only runtime seam with plan acceptance A NOT met.

What landed (`m20_general_cognitive_worker/legacy_service.py`, `m21_claire/service.py`):
- `start(..., tenant_id=None, actor_id=None)`; Claire's realize path passes the goal owner identity (`_run_identity`, `m21_claire/service.py:59`, used at the `cognitive.start` call at `:64`). Legacy goals with no owner pass nothing and every gated step is blocked `binding_unavailable`.
- A step filed approval-required stays gated for life, even if its tool risk is later mutated to READ/REVERSIBLE (reviewer condition 1).
- Filing: payload {tenant_id, run_id, step_id, title, tool, arguments, risk, step_digest}, action `cognitive:<tool>`, pending TTL 24h. Approved validity 900s (inclusive), checked in m00 `consume_effect(max_age_seconds=900)` with its own clock.
- Dispatch gate: tool/risk/arguments are snapshotted once before consume and that snapshot's handler is called with no relookup. Pre-dispatch refusals (tool unavailable, risk differs) leave the approval unconsumed.
- Tool name, handler and timeout are snapshotted with the arguments BEFORE consume; the dispatch uses only that snapshot (a post-consume handler swap or `step.tool=None` cannot change what runs or fake a synthetic success; regression tests added after review).
- Unknown-outcome marker is set after committed consumption and BEFORE the handler. Timeout, cancellation, handler error and scheduler exceptions keep the fixed state; the outer execute never overwrites it. No retry.
- Fixed error codes only (class name or code, never exception text): binding_unavailable, arguments_invalid, approval_denied, approval_expired, approval_mismatch, approval_stale, approval_consumed, approval_refused, approval_store_unavailable, outcome_unknown. Pending approvals WAIT; terminal invalid ones block with a distinct code.
- Fail closed on blank identities, null/future timestamps, non-plain-JSON arguments, module/action/user/run/step/digest mismatch, wrong permit ids, missing facade methods. No list/default fallback.

Cancellation note: a cancelled run propagates CancelledError out of execute, so the step state stays RUNNING (not BLOCKED) with outcome_unknown=True and error=outcome_unknown. A rerun never picks RUNNING steps up (only PENDING/WAITING are ready), so it blocks the run and dispatches nothing. Handler errors/timeouts/scheduler exceptions (non-cancel) end BLOCKED.

Honest limits:
- No role/designation authorization. `approved_by != actor` is a structural string check; it cannot prove the approver's tenant or role. m00 actor binding / decide-role stay open.
- No m00 actor binding, daemon token validation, device attestation or production wiring.
- The unknown-outcome marker is in-memory run state, not durable.
- A new approval is not proof that an uncertain earlier effect is safe to repeat.
- SQLite row-lock caveat: unique constraint plus commit ordering gives at-most-one; under contention a DB error may surface instead of the fixed refusal (such steps are blocked, nothing dispatched).
- Covers only the legacy `DeliberativeLoop` that Claire realize uses, not `CognitiveWorkerService`. Effect class is whatever the integrator registered.
- No whole-product claim.
