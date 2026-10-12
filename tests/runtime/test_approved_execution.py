"""Approved-execution dispatcher: guard rails, receipts, readback, routes."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.m00_approval_center.service import ApprovalNotFoundError
from app.runtime.approved_execution import (
    ACTION_ALLOWLIST,
    ApprovedExecutionDispatcher,
    ExecutionConflictError,
    ReceiptStore,
)
from app.runtime.approved_execution_routes import get_dispatcher
from app.runtime.integration import AtlasRuntime


class FakeCenter:
    """Minimal Module 0 stand-in with the service's dict-view contract."""

    def __init__(self, user_id="tenant-a"):
        self.views = {}
        self.user_id = user_id

    def submit(self, *, module_id, action_type, payload, user_id=None, ttl_seconds=None):
        approval_id = str(uuid.uuid4())
        self.views[approval_id] = {
            "id": approval_id, "user_id": user_id or self.user_id,
            "module_id": module_id, "action_type": action_type,
            "payload": payload, "status": "pending"}
        return self.views[approval_id]

    def get(self, approval_id):
        if approval_id not in self.views:
            raise ApprovalNotFoundError(approval_id)
        return self.views[approval_id]

    def set_status(self, approval_id, status):
        self.views[approval_id]["status"] = status


def make_dispatcher(tmp_path, center=None, runtime=None, allowlist=None, tenant="tenant-a"):
    return ApprovedExecutionDispatcher(
        tenant, center=center or FakeCenter(tenant), runtime=runtime,
        store=ReceiptStore(str(tmp_path / "receipts.sqlite")), allowlist=allowlist)


def approved_goal(center, action_type="execute_product_plan"):
    view = center.submit(module_id=20, action_type=action_type,
                         payload={"goal": "launch", "goal_id": "g-1"})
    center.set_status(view["id"], "approved")
    return view["id"]


def test_pending_denied_and_expired_approvals_are_refused(tmp_path):
    dispatcher = make_dispatcher(tmp_path)
    for status in ("pending", "denied", "expired"):
        view = dispatcher.center.submit(module_id=20, action_type="execute_product_plan",
                                        payload={"goal": "x"})
        dispatcher.center.set_status(view["id"], status)
        with pytest.raises(PermissionError, match=status):
            dispatcher.execute(view["id"])
        assert dispatcher.store.latest_for("tenant-a", view["id"]) is None


def test_unknown_and_cross_tenant_approvals_are_not_found(tmp_path):
    dispatcher = make_dispatcher(tmp_path)
    with pytest.raises(ApprovalNotFoundError):
        dispatcher.execute("no-such-approval")
    other = dispatcher.center.submit(module_id=20, action_type="execute_product_plan",
                                     payload={"goal": "x"}, user_id="tenant-b")
    dispatcher.center.set_status(other["id"], "approved")
    with pytest.raises(ApprovalNotFoundError):
        dispatcher.execute(other["id"])


def test_approved_item_executes_and_persists_started_and_succeeded_receipts(tmp_path):
    dispatcher = make_dispatcher(tmp_path)
    approval_id = approved_goal(dispatcher.center)
    receipt = dispatcher.execute(approval_id)
    assert receipt["state"] == "succeeded"
    assert receipt["readback"]["result"]["state"] == "prepared"
    assert receipt["readback"]["result"]["external_effects"] is False
    states = [r["state"] for r in dispatcher.list_receipts()]
    assert states == ["succeeded", "started"]


def test_replay_is_blocked_but_failures_may_retry(tmp_path):
    async def boom(context, handoff):
        raise RuntimeError("adapter exploded")

    runtime = AtlasRuntime()
    runtime.register(20, "prepare_goal_work", boom)
    dispatcher = make_dispatcher(tmp_path, runtime=runtime)
    approval_id = approved_goal(dispatcher.center)
    with pytest.raises(RuntimeError):
        dispatcher.execute(approval_id)
    assert dispatcher.readback(approval_id)["state"] == "failed"
    assert "adapter exploded" in dispatcher.readback(approval_id)["readback"]["error"]

    from app.runtime.production import build_runtime
    dispatcher.runtime = build_runtime()
    receipt = dispatcher.execute(approval_id)  # failed receipts are retryable
    assert receipt["state"] == "succeeded"
    with pytest.raises(ExecutionConflictError, match="succeeded"):
        dispatcher.execute(approval_id)


def test_non_allowlisted_action_is_refused_and_audited(tmp_path):
    dispatcher = make_dispatcher(tmp_path)
    view = dispatcher.center.submit(module_id=13, action_type="browse_the_web",
                                    payload={"goal": "browse task", "url": "https://example.test"})
    dispatcher.center.set_status(view["id"], "approved")
    with pytest.raises(ValueError, match="not allowlisted"):
        dispatcher.execute(view["id"])
    receipt = dispatcher.readback(view["id"])
    assert receipt["state"] == "failed" and "not allowlisted" in receipt["readback"]["error"]
    dispatcher.allowlist["browse_the_web"] = (20, "prepare_goal_work")
    with pytest.raises(PermissionError, match="unclassified"):
        dispatcher.execute(view["id"])
    assert dispatcher.readback(view["id"])["state"] == "failed"


def test_allowlist_maps_only_to_registered_adapters():
    from app.runtime.production import build_runtime
    runtime = build_runtime()
    for action_type, target in ACTION_ALLOWLIST.items():
        assert target in runtime.handlers, f"{action_type} maps to unregistered {target}"


def test_routes_cover_guards_receipts_and_readback(tmp_path):
    dispatcher = make_dispatcher(tmp_path, tenant="tenant")
    app.dependency_overrides[get_dispatcher] = lambda: dispatcher
    client = TestClient(app)
    try:
        pending = dispatcher.center.submit(module_id=20, action_type="execute_product_plan",
                                           payload={"goal": "launch", "goal_id": "g-1"},
                                           user_id="tenant")
        assert client.post("/api/v1/approved-executions",
                           json={"approval_id": pending["id"]}).status_code == 403
        assert client.post("/api/v1/approved-executions",
                           json={"approval_id": "missing"}).status_code == 404

        dispatcher.center.set_status(pending["id"], "approved")
        executed = client.post("/api/v1/approved-executions",
                               json={"approval_id": pending["id"]})
        assert executed.status_code == 201
        assert executed.json()["state"] == "succeeded"
        assert client.post("/api/v1/approved-executions",
                           json={"approval_id": pending["id"]}).status_code == 409

        readback = client.get(f"/api/v1/approved-executions/{pending['id']}")
        assert readback.status_code == 200
        assert readback.json()["readback"]["result"]["goal"] == "launch"
        assert client.get("/api/v1/approved-executions/no-receipt").status_code == 404
        receipts = client.get("/api/v1/approved-executions").json()
        assert [r["state"] for r in receipts] == ["succeeded", "started"]

        refused = dispatcher.center.submit(module_id=13, action_type="browse_the_web",
                                           payload={}, user_id="tenant")
        dispatcher.center.set_status(refused["id"], "approved")
        assert client.post("/api/v1/approved-executions",
                           json={"approval_id": refused["id"]}).status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---- guardrail enforcer wiring for person-facing action types (groups 136/137/139) ----
from app.runtime.guardrails.enforcer import GuardrailEnforcer  # noqa: E402
from app.runtime.guardrails.errors import GuardrailRefusal  # noqa: E402

_EFF_ALLOW = {"send_email_reply": (10, "send"), "publish_social_post": (6, "post")}
_DECL = {
    "tos": {p: {"allowed_kinds": ["send", "post"], "automation_allowed": True}
            for p in ("gmail", "social")},
    "rate_limits": {p: {k: {"max": 100, "window_seconds": 60} for k in ("send", "post")}
                    for p in ("gmail", "social")},
    "consent": [], "recent_actions": [],
}


class _SpyRuntime:
    def __init__(self):
        self.calls = []

    async def dispatch(self, context, handoff):
        self.calls.append(handoff.operation)
        return {"ok": True}


def _effect_dispatcher(tmp_path, enforcer, runtime):
    return ApprovedExecutionDispatcher(
        "tenant-a", center=FakeCenter("tenant-a"), runtime=runtime,
        store=ReceiptStore(str(tmp_path / "r.sqlite")), allowlist=_EFF_ALLOW,
        enforcer=enforcer, outbound_declarations=_DECL)


def _approved(d, action_type):
    v = d.center.submit(module_id=10, action_type=action_type, payload={"to": "x"})
    d.center.set_status(v["id"], "approved")
    return v["id"]


@pytest.mark.parametrize("action_type", sorted(_EFF_ALLOW))
def test_person_facing_action_refused_without_enforcer(tmp_path, action_type):
    rt = _SpyRuntime()
    d = _effect_dispatcher(tmp_path, None, rt)
    aid = _approved(d, action_type)
    with pytest.raises(PermissionError, match="requires a guardrail enforcer"):
        d.execute(aid)
    assert rt.calls == []
    assert d.store.latest_for("tenant-a", aid)["state"] == "failed"


def test_person_facing_action_refused_without_authority_hook(tmp_path):
    rt = _SpyRuntime()
    enf = GuardrailEnforcer()  # no authority_check: fail closed
    d = _effect_dispatcher(tmp_path, enf, rt)
    aid = _approved(d, "send_email_reply")
    with pytest.raises(GuardrailRefusal) as held:
        d.execute(aid)
    assert held.value.code == "OUTGATE:refused:authority_hook_required"
    assert rt.calls == []
    assert enf.ledger("outbound")[-1]["record"]["verdict"] == "refused:authority_hook_required"


def test_person_facing_action_refused_when_authority_rejects(tmp_path):
    rt = _SpyRuntime()
    d = _effect_dispatcher(tmp_path, GuardrailEnforcer(authority_check=lambda ref, dig: False), rt)
    aid = _approved(d, "publish_social_post")
    with pytest.raises(GuardrailRefusal) as held:
        d.execute(aid)
    assert held.value.code == "OUTGATE:refused:authority_rejected"
    assert rt.calls == []


def test_person_facing_action_runs_with_validated_authority_and_ledgers(tmp_path):
    rt = _SpyRuntime()
    seen = []
    from app.runtime.guardrails._fields import payload_sha256
    expected = {}
    def check(ref, dig):
        seen.append(ref)
        return dig == payload_sha256(expected)
    enf = GuardrailEnforcer(authority_check=check)
    d = _effect_dispatcher(tmp_path, enf, rt)
    aid = _approved(d, "send_email_reply")
    real = enf.dispatch_outbound
    def dispatch(action, *args, **kwargs):
        expected.update({k: v for k, v in action.items() if k != "id"})
        return real(action, *args, **kwargs)
    enf.dispatch_outbound = dispatch
    receipt = d.execute(aid)
    assert receipt["state"] == "succeeded" and rt.calls == ["send"]
    assert seen == [aid]
    assert enf.ledger("outbound")[-1]["record"]["verdict"] == "dispatched"


# ---- production wiring: M00 authority hook bound to the action digest ----
from app.runtime.approved_execution import M00AuthorityCheck  # noqa: E402


def _prod_like(tmp_path, rt, decl=None):
    center = FakeCenter("tenant-a")
    chk = M00AuthorityCheck(center, "tenant-a")
    return ApprovedExecutionDispatcher(
        "tenant-a", center=center, runtime=rt,
        store=ReceiptStore(str(tmp_path / "r.sqlite")), allowlist=_EFF_ALLOW,
        enforcer=GuardrailEnforcer(authority_check=chk), authority_binder=chk,
        outbound_declarations=_DECL if decl is None else decl)


def test_prod_path_dispatches_approved_unmodified_send(tmp_path):
    rt = _SpyRuntime()
    d = _prod_like(tmp_path, rt)
    aid = _approved(d, "send_email_reply")
    assert d.execute(aid)["state"] == "succeeded" and rt.calls == ["send"]


def test_prod_path_refuses_when_payload_edited_after_execution_bind(tmp_path):
    rt = _SpyRuntime()
    d = _prod_like(tmp_path, rt)
    aid = _approved(d, "send_email_reply")
    orig = d.center.get

    def edited(a):
        v = dict(orig(a))
        if d.authority_binder._bound.get(a):  # hook call happens after bind
            v["payload"] = {"to": "attacker"}
        return v
    d.center.get = edited
    # first get() (status check) happens before bind -> unmodified; hook's get() is edited
    with pytest.raises(GuardrailRefusal) as held:
        d.execute(aid)
    assert held.value.code == "OUTGATE:refused:authority_rejected" and rt.calls == []


def test_prod_path_refuses_when_approval_revoked_before_dispatch(tmp_path):
    rt = _SpyRuntime()
    d = _prod_like(tmp_path, rt)
    aid = _approved(d, "send_email_reply")
    orig = d.center.get

    def revoked(a):
        v = dict(orig(a))
        if d.authority_binder._bound.get(a):
            v["status"] = "denied"
        return v
    d.center.get = revoked
    with pytest.raises(GuardrailRefusal) as held:
        d.execute(aid)
    assert held.value.code == "OUTGATE:refused:authority_rejected" and rt.calls == []


def test_prod_path_refuses_when_platform_terms_undeclared(tmp_path):
    rt = _SpyRuntime()
    d = _prod_like(tmp_path, rt, decl={"tos": {}, "rate_limits": {}, "consent": [], "recent_actions": []})
    aid = _approved(d, "send_email_reply")
    with pytest.raises(GuardrailRefusal) as held:
        d.execute(aid)
    assert held.value.code == "OUTGATE:refused:denied" and rt.calls == []


def test_build_dispatcher_carries_enforcer_and_default_declares_only_gmail(tmp_path, monkeypatch):
    from app.runtime import approved_execution_routes as r
    monkeypatch.delenv("ATLAS_OUTBOUND_DECLARATIONS", raising=False)
    d = r.build_dispatcher("tenant-a")
    assert d.enforcer is not None and isinstance(d.authority_binder, M00AuthorityCheck)
    assert set(d.outbound_declarations["tos"]) == {"gmail"}
    assert "social" not in d.outbound_declarations["tos"]


@pytest.mark.parametrize("override", [{}, {"send_email_reply": ("github", "read")}])
def test_effect_classification_cannot_be_overridden(tmp_path, override):
    with pytest.raises(ValueError, match="classification is fixed"):
        ApprovedExecutionDispatcher("tenant-a", center=FakeCenter(), runtime=_SpyRuntime(),
                                    store=ReceiptStore(str(tmp_path / "fixed.sqlite")), effect_kinds=override)


def test_fixed_effect_inventory_is_immutable():
    from app.runtime.approved_execution import EFFECT_ACTION_KINDS
    with pytest.raises(TypeError):
        EFFECT_ACTION_KINDS["send_email_reply"] = ("github", "read")


@pytest.mark.parametrize("field", ["payload", "module_id", "action_type", "user_id"])
def test_prod_hook_rejects_nested_and_identity_drift_after_bind(tmp_path, field):
    rt = _SpyRuntime()
    d = _prod_like(tmp_path, rt)
    aid = _approved(d, "send_email_reply")
    d.center.views[aid]["payload"] = {"nested": {"to": ["owner"]}}
    orig = d.enforcer.dispatch_outbound
    def drift(action, *args, **kwargs):
        if field == "payload":
            d.center.views[aid]["payload"]["nested"]["to"].append("attacker")
        else:
            d.center.views[aid][field] = {"module_id": 99, "action_type": "publish_social_post",
                                           "user_id": "other"}[field]
        return orig(action, *args, **kwargs)
    d.enforcer.dispatch_outbound = drift
    with pytest.raises(GuardrailRefusal, match="authority_rejected"):
        d.execute(aid)
    assert rt.calls == []


def test_dispatcher_effect_uses_only_canonical_gate_action(tmp_path):
    class Runtime:
        async def dispatch(self, context, handoff):
            assert context.tenant_id == "canonical-tenant"
            assert context.actor_id == "canonical-actor"
            assert context.correlation_id == "canonical-receipt"
            assert handoff.target_module == 99 and handoff.operation == "canonical-operation"
            assert handoff.payload == {"nested": {"to": ["canonical"]}}
            return {"canonical": True}
    class Gate:
        def dispatch_outbound(self, action, declarations, *, effect, **kwargs):
            # Contract probe, not a real admission: detects a detached closure.
            action["context"] = {"tenant_id": "canonical-tenant", "actor_id": "canonical-actor",
                                 "correlation_id": "canonical-receipt"}
            action["handoff"]["target_module"] = 99
            action["handoff"]["operation"] = "canonical-operation"
            action["payload"] = {"nested": {"to": ["canonical"]}}
            return effect(action)
    d = _effect_dispatcher(tmp_path, Gate(), Runtime())
    assert d.execute(_approved(d, "send_email_reply"))["readback"]["result"] == {"canonical": True}


def test_authority_binder_deep_copies_execution_fields():
    from app.runtime.guardrails._fields import payload_sha256
    center = FakeCenter()
    v = center.submit(module_id=10, action_type="send_email_reply", payload={"nested": {"to": ["owner"]}})
    center.set_status(v["id"], "approved")
    check = M00AuthorityCheck(center, "tenant-a")
    fields = {"action_type": "send_email_reply", "approval_module_id": 10, "payload": v["payload"]}
    check.bind(v["id"], fields)
    digest = payload_sha256(fields)
    fields["payload"]["nested"]["to"].append("attacker")
    assert check._bound[v["id"]]["payload"] == {"nested": {"to": ["owner"]}}
    assert check(v["id"], digest) is False
    assert check(v["id"], payload_sha256(fields)) is False


@pytest.mark.parametrize("section", ["context", "handoff", "payload"])
def test_execution_context_target_and_nested_payload_are_digest_bound(tmp_path, section):
    rt = _SpyRuntime()
    d = _prod_like(tmp_path, rt)
    aid = _approved(d, "send_email_reply")
    real = d.enforcer.dispatch_outbound
    def tamper(action, *args, **kwargs):
        if section == "context":
            action[section]["tenant_id"] = "attacker"
        elif section == "handoff":
            action[section]["operation"] = "attacker"
        else:
            action[section]["to"] = {"nested": ["attacker"]}
        return real(action, *args, **kwargs)
    d.enforcer.dispatch_outbound = tamper
    with pytest.raises(GuardrailRefusal, match="authority_rejected"):
        d.execute(aid)
    assert rt.calls == []


def test_local_action_cannot_be_redirected_to_an_effect_target(tmp_path):
    rt = _SpyRuntime()
    d = make_dispatcher(tmp_path, runtime=rt, allowlist={"prepare_goal_work": (10, "send")})
    aid = approved_goal(d.center, "prepare_goal_work")
    with pytest.raises(PermissionError, match="unclassified"):
        d.execute(aid)
    assert rt.calls == []
