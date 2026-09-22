import builtins
"""Compatibility facade over Module 0, the single Atlas approval path."""
from app.core.models import ApprovalRequest, ApprovalStatus
from app.modules.m00_approval_center.service import ApprovalConflictError, ApprovalNotFoundError, default_service

class ApprovalStore:
    def put(self, item: ApprovalRequest, *, user_id: str | None = None) -> ApprovalRequest:
        tenant_id = user_id or str(item.payload.get("tenant_id") or "default")
        view = default_service().submit(module_id=item.module_id, action_type=item.action_type, payload=item.payload, user_id=tenant_id)
        return ApprovalRequest(id=view["id"], module_id=view["module_id"], action_type=view["action_type"], payload=view["payload"], status=view["status"])

    def list(self, *, user_id: str | None = None) -> builtins.list[ApprovalRequest]:
        return [ApprovalRequest(id=v["id"], module_id=v["module_id"], action_type=v["action_type"], payload=v["payload"], status=v["status"]) for v in default_service().list(user_id=user_id)]

    def get(self, item_id: str, *, user_id: str | None = None) -> ApprovalRequest | None:
        """Fetch one approval without scanning the tenant-wide queue."""
        try:
            view = default_service().get(item_id)
            if user_id is not None and view["user_id"] != user_id:
                return None
        except ApprovalNotFoundError:
            return None
        return ApprovalRequest(id=view["id"], module_id=view["module_id"], action_type=view["action_type"], payload=view["payload"], status=view["status"])

    def register_callback(self, item_id: str, callback) -> None:
        """Run callback after Module 0 records a terminal decision."""
        default_service().register_callback(item_id, callback)

    def decide(self, item_id: str, decision: ApprovalStatus, *, user_id: str | None = None, decided_by: str = "legacy-api") -> ApprovalRequest | None:
        try:
            if user_id is not None and default_service().get(item_id)["user_id"] != user_id:
                return None
            view = default_service().decide(item_id, decision, decided_by=decided_by)
        except ApprovalNotFoundError:
            return None
        except ApprovalConflictError as error:
            raise ValueError(str(error)) from error
        return ApprovalRequest(id=view["id"], module_id=view["module_id"], action_type=view["action_type"], payload=view["payload"], status=view["status"])

    def audit(self, item_id: str, *, user_id: str | None = None) -> builtins.list[dict[str, str]]:
        try:
            if user_id is not None and default_service().get(item_id)["user_id"] != user_id:
                return []
            events = default_service().audit(item_id)
        except ApprovalNotFoundError:
            return []
        return [{"event": e["event"], "at": e["at"].isoformat()} for e in events]

approvals = ApprovalStore()
