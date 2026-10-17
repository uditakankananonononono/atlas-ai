"""Durable claim-first idempotency for intake, following the Module 0 gate pattern.
The claim is recorded BEFORE the side effect (generate + run creation), so a concurrent
retry never starts a second paid effect while one is claimed. A pending claim is never
reclaimed automatically: lease expiry cannot prove the worker or the remote effect died,
and an exception from generate cannot prove no charge happened. Stuck or unknown claims
wait for explicit grounded reconciliation (reconcile_abandon), an operator action that
is never invoked by the request path. Completed receipts qualify against the live run map."""
from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import DateTime,JSON,String,update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine

class IdempotencyConflictError(RuntimeError):pass
class IdempotencyInProgressError(RuntimeError):pass
class IdempotencyUnavailableError(RuntimeError):pass

class IntakeIdempotencyRow(Base):
    __tablename__="m19_intake_idempotency"
    tenant_id:Mapped[str]=mapped_column(String(120),primary_key=True)
    key:Mapped[str]=mapped_column(String(200),primary_key=True)
    request_hash:Mapped[str]=mapped_column(String(64))
    status:Mapped[str]=mapped_column(String(20))
    run_id:Mapped[str|None]=mapped_column(String(36),index=True,nullable=True)
    response_json:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))

class IntakeIdempotencyStore:
    def __init__(self,session_factory:sessionmaker=SessionLocal,clock=lambda:datetime.now(timezone.utc)):
        self.sessions=session_factory;self.clock=clock;Base.metadata.create_all(engine)
    def claim(self,tenant_id:str,key:str,request_hash:str)->tuple[str,IntakeIdempotencyRow|None]:
        """Returns (outcome,row): claimed | replay | in_progress | conflict. Pending claims are never reclaimed here."""
        now=self.clock()
        row=IntakeIdempotencyRow(tenant_id=tenant_id,key=key,request_hash=request_hash,status="pending",run_id=None,response_json=None,created_at=now,updated_at=now)
        try:
            with self.sessions.begin() as db:db.add(row)
            return "claimed",None
        except IntegrityError:pass
        with self.sessions() as db:
            existing=db.get(IntakeIdempotencyRow,(tenant_id,key))
            if existing.request_hash!=request_hash:return "conflict",existing
            if existing.status=="completed":return "replay",existing
            return "in_progress",existing
    def complete(self,tenant_id:str,key:str,run_id:str,response_json:dict)->None:
        with self.sessions.begin() as db:
            db.execute(update(IntakeIdempotencyRow).where(IntakeIdempotencyRow.tenant_id==tenant_id,IntakeIdempotencyRow.key==key).values(status="completed",run_id=run_id,response_json=response_json,updated_at=self.clock()).execution_options(synchronize_session=False))
    def reconcile_abandon(self,tenant_id:str,key:str)->bool:
        """Explicit operator reconciliation for a pending claim whose effect is PROVEN absent.
        Never called by the request path: an unknown-outcome claim must stay pending until
        someone with ground truth clears it. Returns True when a pending claim was removed."""
        with self.sessions.begin() as db:
            row=db.get(IntakeIdempotencyRow,(tenant_id,key))
            if row is not None and row.status=="pending":db.delete(row);return True
            return False
