import builtins
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base, SessionLocal, engine
from app.core.models import ApprovalRequest, ApprovalStatus

class ApprovalRow(Base):
    __tablename__ = "approval_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    module_id: Mapped[int]
    action_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class ApprovalAuditRow(Base):
    __tablename__ = "approval_audit"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    approval_id: Mapped[str] = mapped_column(String(36), index=True)
    event: Mapped[str] = mapped_column(String(40))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class ApprovalStore:
    """Durable approval state and append-only audit events."""
    def __init__(self) -> None:
        Base.metadata.create_all(engine)

    @staticmethod
    def _model(row: ApprovalRow) -> ApprovalRequest:
        return ApprovalRequest(id=row.id, module_id=row.module_id, action_type=row.action_type, payload=row.payload, status=ApprovalStatus(row.status))

    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        now = datetime.now(timezone.utc)
        with SessionLocal.begin() as db:
            existing = db.get(ApprovalRow, item.id)
            if existing is None:
                db.add(ApprovalRow(id=item.id, module_id=item.module_id, action_type=item.action_type, payload=item.payload, status=item.status.value, created_at=now))
                db.add(ApprovalAuditRow(approval_id=item.id, event="created", at=now))
        return item

    def list(self) -> builtins.list[ApprovalRequest]:
        with SessionLocal() as db:
            return [self._model(row) for row in db.scalars(select(ApprovalRow).order_by(ApprovalRow.created_at.desc()))]

    def decide(self, item_id: str, decision: ApprovalStatus) -> ApprovalRequest | None:
        if decision not in {ApprovalStatus.APPROVED, ApprovalStatus.DENIED}:
            raise ValueError("decision must be approved or denied")
        now = datetime.now(timezone.utc)
        with SessionLocal.begin() as db:
            row = db.get(ApprovalRow, item_id)
            if row is None:
                return None
            if row.status != ApprovalStatus.PENDING.value:
                raise ValueError("approval has already been decided")
            row.status = decision.value
            row.decided_at = now
            db.add(ApprovalAuditRow(approval_id=item_id, event=decision.value, at=now))
            db.flush()
            return self._model(row)

    def audit(self, item_id: str) -> builtins.list[dict[str, str]]:
        with SessionLocal() as db:
            rows = db.scalars(select(ApprovalAuditRow).where(ApprovalAuditRow.approval_id == item_id).order_by(ApprovalAuditRow.id))
            return [{"event": row.event, "at": row.at.isoformat()} for row in rows]

approvals = ApprovalStore()
