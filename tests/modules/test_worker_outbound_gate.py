"""Worker choke point: person-facing approved actions are admitted by the outbound gate BEFORE the permit is spent."""
import json

import pytest

from app.core.models import ApprovalStatus
from app.runtime.guardrails.errors import GuardrailRefusal
from tests.modules.test_m00_impact_preview import service  # noqa: F401

DECL = {"tos": {"social": {"allowed_kinds": ["post"], "automation_allowed": True}},
        "rate_limits": {"social": {"post": {"max": 100, "window_seconds": 60}}},
        "consent": [], "recent_actions": []}


@pytest.fixture
def world(service, monkeypatch, tmp_path):  # noqa: F811
    from app.workers import action_registry, tasks
    monkeypatch.setattr(action_registry, "_EXECUTORS", {})
    monkeypatch.setattr(tasks, "_OUTBOUND", {})
    monkeypatch.setattr("app.modules.m00_approval_center.service.default_service", lambda: service)
    calls = []
    action_registry.register_executor(6, "publish_social_post", lambda p: calls.append(dict(p)) or {"posted": True})
    path = tmp_path / "decl.json"
    path.write_text(json.dumps(DECL))
    monkeypatch.setenv("ATLAS_OUTBOUND_DECLARATIONS", str(path))
    return service, calls, path


def _approved(service):
    v = service.submit(module_id=6, action_type="publish_social_post", payload={"text": "hi"}, user_id="udita")
    service.decide(v["id"], ApprovalStatus.APPROVED, decided_by="udita")
    return v["id"]


def _events(service, aid):
    return [e["event"] for e in service.audit(aid)]


def test_declared_and_approved_post_executes(world):
    from app.workers.tasks import execute_approved_action
    service, calls, _ = world
    aid = _approved(service)
    out = execute_approved_action.run(aid, "e1")
    assert out["status"] == "executed" and calls == [{"text": "hi"}]


def test_undeclared_platform_terms_refuse_before_permit_is_spent(world, monkeypatch):
    from app.workers.tasks import execute_approved_action
    service, calls, path = world
    monkeypatch.delenv("ATLAS_OUTBOUND_DECLARATIONS")
    aid = _approved(service)
    with pytest.raises(GuardrailRefusal) as held:
        execute_approved_action.run(aid, "e2")
    assert held.value.code == "OUTGATE:refused:denied"
    assert calls == [] and "effect_consumed" not in _events(service, aid)


def test_authority_rejected_when_approval_revoked_before_gate_hook(world, monkeypatch):
    from app.workers import tasks
    service, calls, _ = world
    aid = _approved(service)
    orig = service.get
    state = {"n": 0}

    def flaky(a):
        v = dict(orig(a))
        state["n"] += 1
        if state["n"] >= 2:  # task's own status read passed; the hook's read sees it denied
            v["status"] = "denied"
        return v
    monkeypatch.setattr(service, "get", flaky)
    with pytest.raises(GuardrailRefusal) as held:
        tasks.execute_approved_action.run(aid, "e3")
    assert held.value.code == "OUTGATE:refused:authority_rejected"
    assert calls == [] and "effect_consumed" not in _events(service, aid)


def test_non_person_facing_action_is_not_gated(world, monkeypatch):
    from app.workers import action_registry
    from app.workers.tasks import execute_approved_action
    service, _, _ = world
    action_registry.register_executor(0, "prepare_goal_work", lambda p: {"ok": 1})
    monkeypatch.delenv("ATLAS_OUTBOUND_DECLARATIONS")
    v = service.submit(module_id=0, action_type="prepare_goal_work", payload={}, user_id="udita")
    service.decide(v["id"], ApprovalStatus.APPROVED, decided_by="udita")
    assert execute_approved_action.run(v["id"], "e4")["result"] == {"ok": 1}


def test_unknown_worker_action_refused_before_permit(world):
    from app.workers import tasks, action_registry
    service, calls, _ = world
    action_registry.register_executor(5, "unknown_send", lambda p: calls.append(p) or {})
    v = service.submit(module_id=5, action_type="unknown_send", payload={}, user_id="udita")
    service.decide(v["id"], ApprovalStatus.APPROVED, decided_by="udita")
    with pytest.raises(PermissionError, match="unclassified"):
        tasks.execute_approved_action.run(v["id"], "unknown")
    assert calls == [] and "effect_consumed" not in _events(service, v["id"])


def test_worker_rate_history_is_retained_across_tasks(world):
    from app.workers import tasks
    service, calls, path = world
    decl = json.loads(path.read_text())
    decl["rate_limits"]["social"]["post"]["max"] = 1
    path.write_text(json.dumps(decl))
    first, second = _approved(service), _approved(service)
    tasks.execute_approved_action.run(first, "first")
    with pytest.raises(GuardrailRefusal, match="refused:denied"):
        tasks.execute_approved_action.run(second, "second")
    assert calls == [{"text": "hi"}]
    assert "effect_consumed" not in _events(service, second)
    assert len(tasks._outbound_enforcer(service, "udita")[0].ledger("outbound")) == 2


def test_worker_long_effect_id_refused_without_truncation(world):
    from app.workers.tasks import execute_approved_action
    service, calls, _ = world
    aid = _approved(service)
    with pytest.raises(ValueError, match="bad_id:effect_id"):
        execute_approved_action.run(aid, "a" * 65)
    assert calls == [] and "effect_consumed" not in _events(service, aid)


def test_worker_callback_consumes_canonical_action(world, monkeypatch):
    from app.workers import tasks
    service, calls, _ = world
    aid = _approved(service)
    enforcer, _ = tasks._outbound_enforcer(service, "udita")
    def gate(action, declarations, *, effect, **kwargs):
        # Contract probe, not a real admission.
        action["payload"] = {"nested": {"to": ["canonical"]}}
        action["module_id"] = 99
        action["user_id"] = "canonical-tenant"
        action["action_type"] = "canonical-operation"
        action["effect_id"] = "canonical-effect"
        return effect(action)
    monkeypatch.setattr(enforcer, "dispatch_outbound", gate)
    def permitted(approval_id, effect_id, view):
        assert approval_id == aid and effect_id == "canonical-effect"
        assert view == {"id": aid, "module_id": 99, "user_id": "canonical-tenant",
                        "action_type": "canonical-operation", "payload": {"nested": {"to": ["canonical"]}}}
        return {"canonical": True}
    monkeypatch.setattr(tasks, "_execute_permitted", permitted)
    assert tasks.execute_approved_action.run(aid, "canonical-test") == {"canonical": True}


def test_worker_local_name_cannot_be_reused_on_effect_module(world):
    from app.workers import tasks, action_registry
    service, calls, _ = world
    action_registry.register_executor(10, "prepare_goal_work", lambda p: calls.append(p) or {})
    v = service.submit(module_id=10, action_type="prepare_goal_work", payload={}, user_id="udita")
    service.decide(v["id"], ApprovalStatus.APPROVED, decided_by="udita")
    with pytest.raises(PermissionError, match="unclassified"):
        tasks.execute_approved_action.run(v["id"], "wrong-module")
    assert calls == [] and "effect_consumed" not in _events(service, v["id"])
