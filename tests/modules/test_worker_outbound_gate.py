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
    action_registry.register_executor(5, "fixture_local", lambda p: {"ok": 1})
    monkeypatch.delenv("ATLAS_OUTBOUND_DECLARATIONS")
    v = service.submit(module_id=5, action_type="fixture_local", payload={}, user_id="udita")
    service.decide(v["id"], ApprovalStatus.APPROVED, decided_by="udita")
    assert execute_approved_action.run(v["id"], "e4")["result"] == {"ok": 1}
