"""Durable run snapshots and append-only observations. No stage executor exists here."""
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy import JSON, String, Integer, UniqueConstraint, select, update
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError
from app.core.database import Base, SessionLocal
from .schemas import RunOut, Stage

class RunConflict(ValueError): pass
class RunRow(Base):
    __tablename__ = 'm19_runs'
    __table_args__ = (UniqueConstraint('tenant_id', 'request_key'),)
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)

class RunEventRow(Base):
    __tablename__ = 'm19_run_events'
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    event: Mapped[dict] = mapped_column(JSON)

class RunRepository:
    def __init__(self, tenant_id='local', sessions=SessionLocal):
        if not tenant_id or len(tenant_id)>120: raise ValueError('invalid tenant')
        self.tenant_id, self.sessions = tenant_id, sessions
        # Local SQLite convenience. Production schema uses the shipped migration.
        bind = sessions.kw['bind']
        if bind.dialect.name == 'sqlite':
            Base.metadata.create_all(bind, tables=[RunRow.__table__, RunEventRow.__table__])

    def begin(self, key, digest, budget):
        now = datetime.now(timezone.utc)
        run = RunOut(id=str(uuid4()), state='intake_generating', stage=Stage.INTAKE,
                     canvas=None, gates=[], budget_cap=budget, version=1,
                     lease_expires_at=now+timedelta(minutes=3))
        try:
            with self.sessions.begin() as db:
                db.add(RunRow(tenant_id=self.tenant_id, id=run.id, request_key=key,
                              request_hash=digest, version=1, snapshot=run.model_dump(mode='json')))
                db.add(RunEventRow(tenant_id=self.tenant_id, run_id=run.id, version=1,
                                  event={'kind':'intake_requested','at':now.isoformat()}))
            return run, True
        except IntegrityError:
            with self.sessions() as db:
                row=db.scalar(select(RunRow).where(RunRow.tenant_id==self.tenant_id,RunRow.request_key==key))
                if row is None: raise
                if row.request_hash != digest: raise RunConflict('idempotency key reused with different intake')
                return self.get(row.id), False

    def get(self, rid):
        with self.sessions() as db:
            row=db.get(RunRow, (self.tenant_id,rid))
            if row is None: raise KeyError(rid)
            run=RunOut.model_validate(row.snapshot)
        if run.lease_expires_at and run.lease_expires_at < datetime.now(timezone.utc):
            run.state='approval_reconciliation_required' if run.state=='preview_requesting' else 'interrupted'; run.error='operation interrupted or lease expired; no automatic retry'
            run.lease_expires_at=None
            try: return self.save(run,run.version,'operation_interrupted')
            except RunConflict: return self.get(rid)
        return run

    def save(self, run, expected, kind, evidence=None):
        new=run.model_copy(deep=True); new.version=expected+1
        with self.sessions.begin() as db:
            result=db.execute(update(RunRow).where(RunRow.tenant_id==self.tenant_id,
                RunRow.id==run.id,RunRow.version==expected).values(version=new.version,snapshot=new.model_dump(mode='json')))
            if result.rowcount != 1: raise RunConflict('run changed; refresh before retrying')
            db.add(RunEventRow(tenant_id=self.tenant_id,run_id=run.id,version=new.version,
                event={'kind':kind,'at':datetime.now(timezone.utc).isoformat(),'evidence':evidence or {}}))
        return new

    def events(self,rid):
        self.get(rid)
        with self.sessions() as db:
            return [{'version':r.version,**r.event} for r in db.scalars(select(RunEventRow).where(
                RunEventRow.tenant_id==self.tenant_id,RunEventRow.run_id==rid).order_by(RunEventRow.version))]
