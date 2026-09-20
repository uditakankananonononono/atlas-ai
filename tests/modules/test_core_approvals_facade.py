from app.core.approvals import ApprovalStore
from app.core.models import ApprovalRequest, ApprovalStatus


class FakeService:
    def __init__(self):
        self.callback = None

    def get(self, item_id):
        if item_id == "missing":
            from app.modules.m00_approval_center.service import ApprovalNotFoundError
            raise ApprovalNotFoundError(item_id)
        return {"id": item_id, "module_id": 5, "action_type": "send_outreach_email",
                "payload": {"message_id": "m1"}, "status": ApprovalStatus.APPROVED}

    def register_callback(self, item_id, callback):
        self.callback = (item_id, callback)


def test_direct_get_and_callback_facade(monkeypatch):
    fake = FakeService()
    monkeypatch.setattr("app.core.approvals.default_service", lambda: fake)
    store = ApprovalStore()
    assert store.get("a1") == ApprovalRequest(id="a1", module_id=5,
        action_type="send_outreach_email", payload={"message_id": "m1"},
        status=ApprovalStatus.APPROVED)
    assert store.get("missing") is None
    callback = lambda view: None
    store.register_callback("a1", callback)
    assert fake.callback == ("a1", callback)
