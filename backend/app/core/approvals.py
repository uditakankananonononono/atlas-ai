import builtins
"""Compatibility facade over Module 0, the single Atlas approval path."""
from app.core.models import ApprovalRequest, ApprovalStatus
from app.modules.m00_approval_center.service import ApprovalConflictError, ApprovalNotFoundError, default_service

class ApprovalStore:
    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        view = default_service().submit(module_id=item.module_id, action_type=item.action_type, payload=item.payload)
        return ApprovalRequest(id=view["id"], module_id=view["module_id"], action_type=view["action_type"], payload=view["payload"], status=view["status"])

    def list(self) -> builtins.list[ApprovalRequest]:
        return [ApprovalRequest(id=v["id"], module_id=v["module_id"], action_type=v["action_type"], payload=v["payload"], status=v["status"]) for v in default_service().list()]

    def get(self, item_id: str) -> ApprovalRequest | None:
        """Fetch one approval without scanning the tenant-wide queue."""
        try:
            view = default_service().get(item_id)
        except ApprovalNotFoundError:
            return None
        return ApprovalRequest(id=view["id"], module_id=view["module_id"], action_type=view["action_type"], payload=view["payload"], status=view["status"])

    def register_callback(self, item_id: str, callback) -> None:
        """Run callback after Module 0 records a terminal decision."""
        default_service().register_callback(item_id, callback)

    def decide(self, item_id: str, decision: ApprovalStatus) -> ApprovalRequest | None:
        try:
            view = default_service().decide(item_id, decision, decided_by="legacy-api")
        except ApprovalNotFoundError:
            return None
        except ApprovalConflictError as error:
            raise ValueError(str(error)) from error
        return ApprovalRequest(id=view["id"], module_id=view["module_id"], action_type=view["action_type"], payload=view["payload"], status=view["status"])

    def audit(self, item_id: str) -> builtins.list[dict[str, str]]:
        try:
            events = default_service().audit(item_id)
        except ApprovalNotFoundError:
            return []
        return [{"event": e["event"], "at": e["at"].isoformat()} for e in events]

approvals = ApprovalStore()
