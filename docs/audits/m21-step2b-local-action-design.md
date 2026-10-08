# Step 2B design note: `Service.local_action` fail-closed approval binding (DESIGN ONLY, no code)

Base: `5e1001dd6a52c10150d810dce3cb5c72ada0bb61` (claire-runtime-m1). Audit row 4 of `m21-gate-coverage-audit-404e01a7.md` is the problem statement.
Limits that apply to this whole note: no role/designation check (m00 decide path is untraced), no actor binding at m00, no daemon token validation, no attestation of OS execution,
no whole-product claim. The change closes ONE gap: the Service accepting any non-empty string as approval.

## Today (file:line at base)
- `m21_claire/service.py:43-60` `local_action`. High-risk = kind in a fixed set, or lexical `ActionPolicy.requires_approval`, or caller-supplied `external_effect` (`:50-54`).
- `:55-56` high-risk without a token files `request_environment_change` (action_type `claire:<kind>`, payload = goal_id, tenant_id?, environment, daemon `preview`, rollback). The payload does NOT bind the action itself.
- `:57` any truthy token reaches `local_client.execute(action, token)`. Nothing checks it against Module 0. Pinned today by
  `tests/modules/test_m21_legacy_policy_superset.py::test_local_action_gates_comms_verb_and_blocks_standing_no` (token "tok" executes `dm`) and the audit CHARACTERIZATION test.
- `:59` the goal is looked up AFTER execute (`self.goals[goal_id]`): an unknown goal id raises KeyError after the effect already ran. `local_action` has no tenant/actor check at all (`owned` is used only by the routes).
- No route or in-tree caller; production wiring has no local_client (`routes.py:12`). This change cannot affect a deployed path until an integrator wires one.

## Proposed behaviour (what CHANGES)
For a high-risk action (same classification as today, unchanged), `approval_token` is interpreted as a Module 0 approval id and is accepted only if ALL hold, checked in this order and BEFORE any execution:
1. Goal resolution first: the goal exists, and if the goal has an owner record the caller's tenant_id+actor_id (new keyword-only params) match it; owned goal + missing/blank caller identity = refuse (same indistinguishable KeyError as `owned`). Goals with no owner record stay in the legacy None namespace (existing tests construct goals directly).
2. The approval exists in Module 0 (`get`), module_id 21, action_type `claire:<kind>`, `user_id` equal to the goal's tenant (or "default" when legacy, matching `put`), payload.goal_id equal to this goal, status APPROVED.
3. The approval payload carries `action_digest` = sha256 of canonical JSON of {goal_id, kind, action}, and it equals the digest of THIS call. Actions must be plain JSON (as `runtime/gates.py:54-58`), else refused. So an approval for one action cannot authorize another, and the reviewed preview is no longer the only thing bound.
4. `approved_by` is present and differs from the goal's actor (no self-approval, as the runtime). This is the only approver rule here; role and designation are NOT checked (decide path untraced).
5. Single use: `consume_effect` (`m00_approval_center/service.py:565-588`) with a fresh uuid effect_id per call. That call is atomic and exact-request-bound; a second call with the same approval is refused ("already consumed"). A fresh effect_id per call is deliberate: consume_effect replays `allowed` for an identical effect_id, which would permit a double run on retry.
Order: consume, then `local_client.execute`, then audit. A consumed approval is never refunded: a crash or error after consume needs a NEW approval (fail safe; also no automatic retry).
Evidence/audit append is resolved before execute (goal already held), removing the post-effect KeyError.
`local_action` filing path: when it files the request (`:56`), it now adds `action_digest` and `goal_id` to the payload so the approval it files can actually authorize that call. Requests filed by the HTTP route `request_environment_change` carry no digest, so they CANNOT authorize local_action (intended: the route files route-reviewed environment changes, not exact-action grants).
Fail closed: if the injected approval store lacks `get`/`consume_effect` (e.g. the in-memory fakes), or any named error occurs (`ApprovalNotFoundError`, `ApprovalConflictError`, expired, non-approved, mismatch), refuse with a fixed message; no `str(exc)` in text. No blanket except.
`core/approvals.py` facade gains thin `get` and `consume_effect` delegations to `default_service()`; no change to `put`/`list`.

## What stays unchanged
- High-risk classification (kind set, lexical policy, `external_effect` flag), FORBIDDEN list, capabilities check, preview call, non-high-risk actions (executed without approval, token passed through as today).
- The daemon contract `execute(action, approval_token)`: the Service now passes the approval id as the token and still does NOT claim the daemon validates it.
- The `claire:*` refusal in the m00 ApprovedExecutionDispatcher allowlist (those approvals are not executed by the dispatcher).
- Routes, schemas, migrations: none. No persistence added (m00 persists approvals and effect rows already).

## Out of scope (stated, not closed)
Approver role/designation and who may call m00 decide; approval TTL (the facade `put` passes no ttl, so these approvals do not expire unless the m00 caller sets one: open decision below); keyed effect journal / unknown-outcome handling for local effects (an error after consume is an unrecorded outcome); lexical classification gaps (`external_effect` omitted = ungated); device-to-action binding (which paired device runs it); wiring a local client in production; the m20 loop and orchestrator approval weaknesses (audit rows 2 and 5).

## Tests (labels)
- CONVERTED: `test_local_action_gates_comms_verb_and_blocks_standing_no` and the audit CHARACTERIZATION: arbitrary token refused; exact-digest approved approval executes once.
- NEW (each must fail on base): bogus/unknown id; PENDING, DENIED and expired approval; approval for a different action (same kind, different args); different goal; different kind; foreign tenant approval; self-approved (approved_by == actor); route-filed approval (no digest); second use of the same approval (refused, one execution); concurrent double use (one executes); consume happens before execute (execute failure leaves approval consumed); store lacking `get`/`consume_effect` refuses; non-JSON action refused; unknown goal refused BEFORE execute; owned goal with missing/foreign caller refused; no str(exc) in any refusal text; the filed request now carries action_digest.
- PROTECTION: forbidden strings still refuse, non-high-risk actions unchanged, no token on high-risk still files a request and does not execute, unwired client still RuntimeError, existing m21 policy-superset tests green.

## Decisions requested
1. Approval TTL: add an optional ttl to the facade `put` and file local-action approvals with a bounded TTL (proposal: 24h), or leave unbounded as today (limit stated).
2. Rule 4 (approved_by != actor): keep as proposed, or defer until the m00 decide-path audit.
3. Keep the effect-failure policy (approval stays consumed, new approval needed), yes/no.
