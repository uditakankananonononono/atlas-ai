"""Slice 13 audit probes: which traced Claire entry paths can reach a payment/comms effect, and what guards them.

PINNED TO commit 404e01a725a0e9a8d8cf3008af3ef772044d9ca8 (tree 8bc61abc288b7abab81f9f2ef894596dc1c845b9). A later change to any adapter, registry
or entry point does NOT inherit these conclusions: re-audit.
Labels: PROTECTION_* = a traced path must stay denied. CHARACTERIZATION_* = records CURRENT behaviour that is a known gap or limit; passing
does NOT mean safe, and changing it is a separate reviewed decision.
COVERAGE OMISSIONS (untraced, no whole-product claim): tools/adapters an integrator binds to the m20 cognitive service; other modules' own effect
adapters (m13 browser agent, outreach, email assistant, billing, ...); the m00 approval center's decide path; production deployment wiring; any
extension registered at runtime. Mocks only; no external side effects; SQLite is not proof for transport/auth behaviour.
"""
import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth.context import TenantContext, require_tenant
from app.core.models import ApprovalRequest, ApprovalStatus
from app.main import app
from app.modules.m20_general_cognitive_worker.legacy_service import Risk, Service as CogService, Tool
from app.modules.m21_claire import routes as claire_routes
from app.modules.m21_claire.models import Approval, ActionRequest
from app.modules.m21_claire.orchestrator import ExecutionOrchestrator, ReviewMismatch
from app.modules.m21_claire.planner import CrossModulePlanner
from app.modules.m21_claire.policy import COMMS_TOKENS, PAYMENT_TOKENS
from app.modules.m21_claire.service import Service as ClaireService
from app.runtime.approved_execution import ApprovedExecutionDispatcher


def req(module, action, **params):
    return ActionRequest(module, action, params, "test purpose")


def plan_for(*requests):
    return CrossModulePlanner().build("goal", requests)


# ---- plain / durable plan dispatch (ExecutionOrchestrator) ---
# Evidence kinds: BEHAVIOURALLY EXERCISED = the test runs that class. SOURCE-TRACED ONLY = DurableExecutionOrchestrator.execute (durable_execution.py:423-468)
# is read: it calls self.policy.require_allowed (:441) and blocks unless a digest-matching, valid approval exists, but ONLY when decision.requires_approval
# (:442). So gating is exactly as strong as the lexical ActionPolicy; an action the policy does not flag runs with no approval. Below, the plain
# orchestrator tests are exercised on the plain class; the durable class is exercised by test_PROTECTION_durable_* and still inherits the lexical limit.---------------------------------------------------------------------------

@pytest.mark.parametrize("verb", sorted(PAYMENT_TOKENS | COMMS_TOKENS))
def test_PROTECTION_plain_orchestrator_does_not_run_a_payment_or_comms_named_action_without_an_exact_approval(verb):
    ran = []
    o = ExecutionOrchestrator()
    o.register(f"m.{verb}", lambda p: ran.append(p))
    plan = plan_for(req("m", verb, to="x"))
    assert o.prepare(plan)                                              # a review is demanded
    with pytest.raises(ReviewMismatch):
        o.execute(plan)
    assert ran == []


def test_PROTECTION_plain_orchestrator_refuses_an_approval_for_different_parameters():
    ran = []
    o = ExecutionOrchestrator()
    o.register("m.send", lambda p: ran.append(p))
    plan = plan_for(req("m", "send", to="x"))
    o.prepare(plan)
    other = plan_for(req("m", "send", to="y"))
    snap = o.review_snapshot(other, other.steps[0].request.action_id)
    with pytest.raises(ReviewMismatch):
        o.approve(plan, Approval("a1", snap.digest, "ap", datetime.now(timezone.utc)))
    with pytest.raises(ReviewMismatch):
        o.execute(plan)
    assert ran == []


def test_CHARACTERIZATION_legacy_policy_is_lexical_innocuous_or_glued_names_are_not_gated_documented_in_policy_py():
    # KNOWN GAP (policy.py:63-67): the legacy gate is a name heuristic. Passing here records the gap; it is not a guarantee.
    ran = []
    o = ExecutionOrchestrator()
    o.register("payments.run", lambda p: ran.append(p))
    o.register("m.sendemail", lambda p: ran.append(p))
    for module, action in (("payments", "run"), ("m", "sendemail")):
        plan = plan_for(req(module, action))
        assert o.prepare(plan) == ()
        o.execute(plan)
    assert len(ran) == 2                                                  # both ran with no approval


def test_CHARACTERIZATION_plain_plan_approvals_are_not_tenant_actor_or_single_use_bound_and_self_approval_is_not_checked():
    # Approval carries only a free-text approver string; the orchestrator has no actor or tenant concept (orchestrator.py:60-77, models.py:127-136).
    ran = []
    o = ExecutionOrchestrator()
    o.register("m.send", lambda p: ran.append(p))
    plan = plan_for(req("m", "send", to="x"))
    o.prepare(plan)
    snap = o.review_snapshot(plan, plan.steps[0].request.action_id)
    o.approve(plan, Approval("a1", snap.digest, "the-same-agent", datetime.now(timezone.utc)))
    o.execute(plan)
    assert len(ran) == 1


# ---- approval request -> execution (m00 dispatcher, outside the six files) ----------------------------------------------------------

class _Center:
    def __init__(self, action_type):
        self.v = {"id": "ap1", "user_id": "t1", "status": ApprovalStatus.APPROVED.value, "action_type": action_type, "payload": {}}

    def get(self, _id):
        return self.v


class _Runtime:
    def __init__(self):
        self.calls = []

    async def dispatch(self, ctx, handoff):
        self.calls.append(handoff)
        return {}


class _Store:
    def __init__(self):
        self.rows = []

    def latest_for(self, t, a):
        return None

    def record(self, **kw):
        self.rows.append(kw)


@pytest.mark.parametrize("op", ["send_message", "spend_money", "install_package", "run_command", "deploy_preview"])
def test_PROTECTION_an_approved_claire_environment_change_is_not_executable_through_the_dispatcher(op):
    rt, st = _Runtime(), _Store()
    d = ApprovedExecutionDispatcher("t1", center=_Center(f"claire:{op}"), runtime=rt, store=st)
    with pytest.raises(ValueError):
        d.execute("ap1")
    assert rt.calls == [] and st.rows[-1]["state"] == "failed"


def test_PROTECTION_request_environment_change_only_files_an_approval_request_and_never_touches_a_client():
    put = []

    class Appr:
        def put(self, item):
            put.append(item); return item

        def list(self):
            return []

    s = ClaireService(object(), Appr())
    g = s.intake("g", [], {}, tenant_id="t1", actor_id="a1")
    s.request_environment_change(g.id, "send_message", {"preview": 1}, tenant_id="t1")
    assert [p.action_type for p in put] == ["claire:send_message"] and s.local_client is None
    with pytest.raises(ValueError):
        s.request_environment_change(g.id, "send_message_now", {})


# ---- local actions (Service.local_action) ------------------------------------------------------------------------------------------

class _Local:
    def __init__(self):
        self.executed = []

    async def capabilities(self):
        return {"send_message", "spend_money", "read_file"}

    async def preview(self, a):
        return {"p": 1}

    async def execute(self, a, token):
        self.executed.append((a, token)); return {"ok": True}

    async def audit(self, e):
        pass


def _local_service():
    class Appr:
        def put(self, item, **kw): return item
        def list(self): return []
    s = ClaireService(object(), Appr(), local_client=_Local())
    g = s.intake("g", [], {}, tenant_id="t1", actor_id="a1")
    return s, g.id


@pytest.mark.parametrize("kind", ["send_message", "spend_money"])
def test_PROTECTION_local_action_without_a_token_files_a_request_and_does_not_execute(kind):
    s, gid = _local_service()
    out = asyncio.run(s.local_action(gid, {"kind": kind}, tenant_id="t1", actor_id="a1"))
    assert s.local_client.executed == [] and out.action_type == f"claire:{kind}"


def test_CONVERTED_local_action_no_longer_accepts_an_arbitrary_token_slice_15():
    # CONVERTED from a CHARACTERIZATION (audited tip 404e01a7: any non-empty token executed). Slice 15 requires a real Module 0 approval; this store has no
    # full_view/consume_effect, so it fails closed. Full coverage: tests/modules/test_m21_local_action_binding.py.
    s, gid = _local_service()
    with pytest.raises(ValueError, match="local action approval refused"):
        asyncio.run(s.local_action(gid, {"kind": "spend_money"}, approval_token="anything", tenant_id="t1", actor_id="a1"))
    assert s.local_client.executed == []


def test_PROTECTION_production_wiring_builds_the_service_without_a_local_client_so_local_action_is_unreachable_in_tree():
    from app.modules.m21_claire import service as svc
    s = claire_routes.get_service(TenantContext("t1", "a1"), cognitive=object())
    assert s.local_client is None and isinstance(s, svc.Service)
    with pytest.raises(RuntimeError):
        asyncio.run(s.local_action("g", {"kind": "send_message"}, "tok"))


# ---- entry snapshot ------------------------------------------------------------------------------------------------------------------

PINNED_NON_RUNTIME_ROUTES = ['DELETE /claire/devices/{device_id}', 'GET /claire/devices', 'POST /claire/devices/pair',
                             'POST /claire/devices/pairing-challenge', 'POST /claire/devices/{device_id}/verify-receipt', 'POST /claire/goals',
                             'POST /claire/goals/{goal_id}/environment-changes', 'POST /claire/goals/{goal_id}/realize',
                             'POST /claire/owner-workflow-279-329', 'POST /claire/preference-feedback-4-6-9']


def test_PROTECTION_the_traced_entry_snapshot_changes_only_with_a_re_audit():
    got = sorted(f"{m} {r.path}" for r in claire_routes.router.routes for m in (getattr(r, "methods", None) or [])
                 if "runtime" not in r.path and "atomic" not in r.path and "concept" not in r.path)
    assert got == PINNED_NON_RUNTIME_ROUTES, "a /claire route was added or removed: re-audit its dispatch path before updating this list"


def test_PROTECTION_realize_is_unreachable_in_tree_until_an_integrator_binds_a_cognitive_service():
    app.dependency_overrides[require_tenant] = lambda: TenantContext("tzz-unbound", "a1")
    try:
        c = TestClient(app)
        # the Service dependency needs the m20 cognitive service, which nothing in tree binds: intake and realize are both 503
        assert c.post("/api/v1/claire/goals", json={"goal": "do a thing", "acceptance": [], "limits": {}}).status_code == 503
        assert c.post("/api/v1/claire/goals/anything/realize").status_code == 503
    finally:
        app.dependency_overrides.pop(require_tenant, None)


def test_PROTECTION_device_pairing_routes_are_tenant_scoped_after_slice_14_but_still_need_no_role():
    # CONVERTED in slice 14 from a CHARACTERIZATION of the cross-tenant list/revoke finding (audited tip 404e01a7). Full coverage:
    # tests/modules/test_m21_device_tenancy.py. STILL TRUE: no role is required, so any authenticated member of a tenant can pair/revoke
    # within that tenant; no effect adapter is reachable from these routes.
    claire_routes._pairing.devices.clear(); claire_routes._pairing.pending.clear()
    who = {"ctx": TenantContext("t1", "u1")}
    app.dependency_overrides[require_tenant] = lambda: who["ctx"]
    try:
        c = TestClient(app)
        ch = c.post("/api/v1/claire/devices/pairing-challenge").json()
        assert "code" in ch                                                # the pairing code is still returned to the challenge caller by design
        dev = c.post("/api/v1/claire/devices/pair", json={"server_nonce": ch["server_nonce"], "code": ch["code"], "name": "pc",
                                                           "certificate_fingerprint": "fp", "capabilities": ["send_message"]}).json()
        who["ctx"] = TenantContext("t2", "u2")
        assert not any(d["id"] == dev["id"] for d in c.get("/api/v1/claire/devices").json())
        assert c.delete(f"/api/v1/claire/devices/{dev['id']}").status_code == 404
        who["ctx"] = TenantContext("t1", "u-other-member", frozenset())    # same tenant, different actor, no roles: still allowed (retained policy)
        assert c.delete(f"/api/v1/claire/devices/{dev['id']}").status_code == 200
    finally:
        app.dependency_overrides.pop(require_tenant, None)
        claire_routes._pairing.devices.clear(); claire_routes._pairing.pending.clear()


# ---- m20 legacy cognitive loop (reached from /claire/goals/{id}/realize when bound) ---------------------------------------------------

class _Approvals:
    def __init__(self):
        self.items = []

    def put(self, item):
        item = ApprovalRequest(id=f"ap{len(self.items)}", module_id=item.module_id, action_type=item.action_type, payload=item.payload, status=ApprovalStatus.PENDING)
        self.items.append(item); return item

    def list(self):
        return list(self.items)


def _cog(steps, tool_name, tool_risk, handler):
    async def model(kind, data):
        return {"steps": steps}
    a = _Approvals()
    s = CogService(a, model)
    s.tools.register(Tool(tool_name, "d", tool_risk, set(), handler))
    return s, a


def _run(s):
    return asyncio.run(s.start("goal", {}, {"seconds": 5, "tokens": 5, "money": 0}))


def test_PROTECTION_cognitive_loop_does_not_dispatch_an_external_tool_until_its_approval_is_approved():
    calls = []

    async def h(args, key):
        calls.append(key); return {"ok": True}
    s, a = _cog([{"title": "t", "tool": "send_note", "risk": "external"}], "send_note", Risk.EXTERNAL, h)
    _run(s)
    assert calls == [] and a.items and a.items[0].action_type == "cognitive:send_note"


def test_PROTECTION_cognitive_loop_refuses_a_model_declared_risk_that_differs_from_the_registered_tool_risk():
    calls = []

    async def h(args, key):
        calls.append(key); return {}
    s, a = _cog([{"title": "t", "tool": "send_note", "risk": "read"}], "send_note", Risk.EXTERNAL, h)
    _run(s)
    assert calls == []


def test_CHARACTERIZATION_cognitive_gate_trusts_the_registered_risk_annotation_a_send_tool_registered_as_read_or_reversible_runs_ungated():
    # KNOWN LIMIT: effect class is whatever the integrator registered; no name or capability check (legacy_service.py:100-108, 134).
    calls = []

    async def h(args, key):
        calls.append(key); return {}
    for risk, name in ((Risk.READ, "send_email"), (Risk.REVERSIBLE, "pay_invoice")):
        calls.clear()
        s, a = _cog([{"title": "t", "tool": name, "risk": risk.value}], name, risk, h)
        _run(s)
        assert len(calls) == 1 and a.items == []


def test_CHARACTERIZATION_cognitive_approval_is_not_single_use_a_failed_then_retried_external_step_dispatches_twice_under_one_approval():
    calls = []

    async def h(args, key):
        calls.append(key)
        if len(calls) == 1:
            raise OSError("boom")                                          # may have happened: no journal, no unknown state in this path
        return {"ok": True}
    s, a = _cog([{"title": "t", "tool": "send_note", "risk": "external"}], "send_note", Risk.EXTERNAL, h)
    run = _run(s)
    a.items[0] = ApprovalRequest(id=a.items[0].id, module_id=a.items[0].module_id, action_type=a.items[0].action_type,
                                 payload=a.items[0].payload, status=ApprovalStatus.APPROVED)
    asyncio.run(s.loop.execute(run))
    assert len(calls) == 2 and len(set(calls)) == 2                        # same approval, two dispatches, two different keys


# ---- durable orchestrator, exercised directly (previously source-traced only) --------------------------------------------------------------

@pytest.mark.parametrize("verb", sorted(PAYMENT_TOKENS | COMMS_TOKENS))
def test_PROTECTION_durable_orchestrator_does_not_run_a_payment_or_comms_named_action_without_an_exact_approval(verb):
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from app.modules.m21_claire.durable_execution import ClaireExecutionRepository, DurableExecutionOrchestrator
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    repo = ClaireExecutionRepository(eng, tenant_id="default")
    repo.create_schema()
    ran = []
    o = DurableExecutionOrchestrator(repo)
    o.register(f"m.{verb}", lambda p: ran.append(p))
    plan = plan_for(req("m", verb, to="x"))
    o.prepare(plan)
    with pytest.raises(ReviewMismatch):
        o.execute(plan)
    assert ran == []


def test_CHARACTERIZATION_durable_orchestrator_gate_is_the_lexical_policy_an_unflagged_name_runs_without_approval():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from app.modules.m21_claire.durable_execution import ClaireExecutionRepository, DurableExecutionOrchestrator
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    repo = ClaireExecutionRepository(eng, tenant_id="default")
    repo.create_schema()
    ran = []
    o = DurableExecutionOrchestrator(repo)
    o.register("m.sendemail", lambda p: ran.append(p) or "ok")   # glued name: not a policy token (durable_execution.py:442 gate is conditional)
    plan = plan_for(req("m", "sendemail", to="x"))
    o.prepare(plan)
    o.execute(plan)
    assert ran                                                  # KNOWN GAP: passing records ungated dispatch, it does not endorse it


def test_PROTECTION_unauthenticated_calls_to_device_and_goal_routes_are_rejected_at_the_mount(monkeypatch):
    # The handlers in routes.py:57-81 declare no auth dependency themselves; authentication comes from main.py's
    # include_router(module_spec.router, dependencies=[Depends(require_tenant)]) loop. Exercised with NO override: 401.
    # the suite's autouse fixture opts into insecure dev auth; remove it so deployment defaults apply (conftest.py:58-63)
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH", raising=False)
    monkeypatch.delenv("ATLAS_ENV", raising=False)
    app.dependency_overrides.pop(require_tenant, None)
    c = TestClient(app)
    for method, path in [("get", "/api/v1/claire/devices"), ("post", "/api/v1/claire/devices/pairing-challenge"),
                         ("delete", "/api/v1/claire/devices/x"), ("post", "/api/v1/claire/goals")]:
        assert getattr(c, method)(path).status_code == 401
