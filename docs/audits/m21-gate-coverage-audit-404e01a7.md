# Claire gate-coverage audit (slice 13)

Audited tip: `404e01a725a0e9a8d8cf3008af3ef772044d9ca8`, tree `8bc61abc288b7abab81f9f2ef894596dc1c845b9` (branch claire-runtime-m1).
Paths below are relative to `backend/app/`; `m21` = `modules/m21_claire`, `m20` = `modules/m20_general_cognitive_worker`.
Probes: `tests/modules/test_m21_gate_coverage_audit.py` (PROTECTION_* must stay denied; CHARACTERIZATION_* record current gaps, passing is NOT approval).
A later change to any path does not inherit these conclusions.

## Scope statement
Every "no bypass" below is limited to the currently-wired, traced paths named in the row. It is NOT a whole-product claim. Where a row shows a
characterized gap, risky-class dispatch is reachable without a gate under the stated registration/token assumption even though no in-tree integrator
does that today. A registered tool's risk annotation is a declaration, not effect validation.

Mount authentication: `main.py:27-48` includes each module router with `dependencies=[Depends(require_tenant)]`; unauthenticated calls return 401
(probed, no override). Handlers themselves may declare no dependency (e.g. `m21/routes.py:57-81`).

## Path table
Evidence kind: E = behaviourally exercised by a test; S = source-traced only.

| # | Entry | Normalization / dispatch / adapter | Guard | Tenant / actor / role | Verdict at this tip | Evidence |
|---|---|---|---|---|---|---|
| 1 | `/claire/runtime/*` (slices 1-12) | runtime engine -> ReadOnlyToolRegistry.execute -> GateEnforcer.classify (`m21/runtime/gates.py:77,107`, `tools.py:111`) | single-use exact-payload approval + effect journal | tenant+actor bound; approver role + distinct + designation | guarded; tool flags are integrator-declared | E (runtime tests) |
| 2 | `POST /claire/goals`, `/goals/{id}/realize` (`m21/routes.py:14-21`) | -> `m21/service.py` realize -> m20 `legacy_service.py` Service.start -> DeliberativeLoop._step (`:136-150`) -> ToolRegistry.dispatch (`:103-108`) | step.risk EXTERNAL/IRREVERSIBLE files `cognitive:<tool>` approval (`:137-143`); tool.risk must equal step.risk (`:107`) | `routes.py:19-20` owned() check; approval looked up by id only (`:141`), no payload/tenant/actor binding, not single-use | unreachable in tree: `m20/routes.py:46-54` returns 503 until an integrator calls bind_service, which nothing in tree does. If bound: risk is the registered annotation only (send tool registered READ runs ungated); failed-then-retried approved step dispatches twice (`:144-149`), no journal | E (503 pinned; loop characterizations) |
| 3 | `POST /claire/goals/{id}/environment-changes` (`m21/routes.py:22-27`) | `m21/service.py:39-42` files approval `claire:<op>` only | `runtime/approved_execution.py:35-39` allowlist (execute_product_plan, prepare_goal_work, research_request), refusal `:146-151`; production construction `approved_execution_routes.py:20-24` uses the default | tenant via owned() | claire:send_message/spend_money/... never executed; guarded | E (5 ops) |
| 4 | `Service.local_action` (`m21/service.py:43-60`) | no route, no in-tree caller; production Service built without local_client (`m21/routes.py:12`) so `:44` raises RuntimeError | high-risk kind/lexical policy/caller-declared `external_effect` (`:50-54`) without token files a request (`:55-56`); ANY non-empty token string executes (`:57`); Service never validates the token | none in Service | unreachable in tree; weak guard if a client is wired. Daemon-side token validation is not present in `local_client_protocol.py` (promise vs enforcement: that file describes reference handshake state, `:22`) and is unverified | E |
| 5 | ExecutionOrchestrator / DurableExecutionOrchestrator / CrossModulePlanner (`m21/orchestrator.py:60-124`, `durable_execution.py:365-468`, `planner.py:19-49`) | no route, no in-tree caller (exports `m21/__init__.py:12-14`, tests) | `policy.require_allowed` (`durable_execution.py:441`) then approval digest check ONLY `if decision.requires_approval` (`:442-452`); `orchestrator.py:103-109` same on plain class | `models.py:127-136` approver is a free-text string: no tenant/actor, no single-use, no self-approval check | payment/comms token verbs refused without exact approval on BOTH classes (E on plain and on durable); policy is lexical (`policy.py:63-67`), so glued/innocuous names (`m.sendemail`) run with no approval (E, characterized, both classes). Durable adds a journal; plain does not (a missing journal is not by itself a bypass) | E plain; E durable; S for retry/resume branches not otherwise tested |
| 6 | `/claire/devices/*` (`m21/routes.py:57-81`; `local_client_protocol.py:21-46`) | module-global PairingService, reference state only; no effect adapter reachable | mount auth only | NOT tenant-scoped, no role: pairing code returned to caller, GET lists all tenants' devices, any tenant can DELETE any device | genuine tenant-isolation finding (reviewer-confirmed), not a payment/comms bypass. AT THE AUDITED TIP. Closed at the route layer by slice 14 (see addendum); the table row is kept as the audited state | E |
| 7 | Rest of the m21 package | grep finds no network/subprocess/file/socket call (only urlparse); other m21 routers read as data/workflow | n/a | n/a | grep absence is NOT tracing of all routers/adapters; hidden dispatch via dynamic registration is not excluded | S (grep only) |
| 8 | `core/approvals.py:7-10` (facade) | put() with no tenant in payload files under user "default" | m00 service | the m20 loop lists approvals with no user filter (`legacy_service.py:141`) | LEAD only: Module 0 tenancy behaviour was not probed | S |

## Coverage omissions (untraced; no whole-product claim)
- tools/adapters an integrator binds to the m20 cognitive service
- other modules' own effect adapters (m13 browser agent, outreach, email assistant, billing, ...)
- the m00 approval-center decide path and who may approve
- m20 agi_routes and other m20 routers; m21 owner-workflow / atomic-concept / preference routes beyond the grep in row 7
- production deployment wiring and any runtime-registered or dynamic extension

## Step 2 (not started; each needs its own design and approval before code)
- 2A tenant-scope and role-gate `/claire/devices/*`
- 2B fail closed in `local_action` unless an exact, single-use approval is verified

## Addendum: slice 14 (Step 2A), after 8a13da2e
Device routes are now tenant-scoped (pending challenges and devices bound to the caller's tenant; foreign and unknown ids/nonces share one 404/422 body; foreign denial precedes any flag, consumption or fingerprint return). Retained limits: no role gate (any authenticated member of a tenant can pair/revoke that tenant's devices), no actor binding, in-memory per-process state, receipts authenticate neither OS execution nor payload truth, local_action token enforcement (2B) untouched. Row 6 above is the audited-tip state.
