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
    assert dispatcher.execute(view["id"])["state"] == "succeeded"


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
