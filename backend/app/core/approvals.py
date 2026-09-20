from threading import RLock
from app.core.models import ApprovalRequest, ApprovalStatus

class ApprovalStore:
    """Thread-safe in-memory MVP store. Replace with PostgreSQL before multi-instance deploy."""
    def __init__(self) -> None:
        self._items: dict[str, ApprovalRequest] = {}
        self._lock = RLock()

    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        with self._lock:
            self._items[item.id] = item
            return item

    def list(self) -> list[ApprovalRequest]:
        with self._lock:
            return list(self._items.values())

    def get(self, item_id: str) -> ApprovalRequest | None:
        with self._lock:
            return self._items.get(item_id)

    def decide(self, item_id: str, decision: ApprovalStatus) -> ApprovalRequest | None:
        if decision not in {ApprovalStatus.APPROVED, ApprovalStatus.DENIED}:
            raise ValueError("decision must be approved or denied")
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                return None
            if item.status is not ApprovalStatus.PENDING:
                raise ValueError("approval has already been decided")
            updated = item.model_copy(update={"status": decision})
            self._items[item_id] = updated
            return updated

approvals = ApprovalStore()
