from __future__ import annotations
from datetime import datetime,timezone
from typing import Any
from sqlalchemy import JSON,DateTime,String,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
from .domain import AuditEvent
class BrowserAuditRow(Base):
    __tablename__="m13_browser_audit_events"
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); run_id:Mapped[str]=mapped_column(String(120),index=True); action:Mapped[str]=mapped_column(String(30)); payload:Mapped[dict[str,Any]]=mapped_column(JSON); occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class ConsumedApprovalRow(Base):
    __tablename__="m13_consumed_approvals"
    approval_id:Mapped[str]=mapped_column(String(36),primary_key=True); tenant_id:Mapped[str]=mapped_column(String(120),index=True); consumed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class SQLStore:
    def __init__(self,sessions:sessionmaker|None=None):
        if sessions is None: Base.metadata.create_all(engine); sessions=SessionLocal
        self.sessions=sessions
    async def append_audit(self,event:AuditEvent):
        with self.sessions.begin() as db: db.add(BrowserAuditRow(tenant_id=event.tenant_id,run_id=event.run_id,action=event.action.value,payload=event.payload,occurred_at=datetime.fromtimestamp(event.occurred_at,timezone.utc)))
    async def was_consumed(self,approval_id):
        with self.sessions() as db:return db.get(ConsumedApprovalRow,approval_id) is not None
    async def consume(self,approval_id,tenant_id):
        with self.sessions.begin() as db:
            if db.get(ConsumedApprovalRow,approval_id): raise PermissionError("approval was already consumed")
            db.add(ConsumedApprovalRow(approval_id=approval_id,tenant_id=tenant_id,consumed_at=datetime.now(timezone.utc)))
