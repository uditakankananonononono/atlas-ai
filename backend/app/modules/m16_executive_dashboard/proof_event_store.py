from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import JSON,DateTime,String,UniqueConstraint,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class ProofEventRow(Base):
 __tablename__='m16_verified_proof_events';__table_args__=(UniqueConstraint('tenant_id','event_id'),)
 id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);event_id:Mapped[str]=mapped_column(String(200),index=True);producer:Mapped[str]=mapped_column(String(200));module_id:Mapped[str]=mapped_column(String(100));requirement_id:Mapped[str]=mapped_column(String(300),index=True);event_type:Mapped[str]=mapped_column(String(50));proof_sha256:Mapped[str]=mapped_column(String(64));payload:Mapped[dict]=mapped_column(JSON);persisted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class ProofEventStore:
 def __init__(self,tenant_id:str,sessions:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=sessions;Base.metadata.create_all(engine)
 def persist(self,event:dict):
  with self.sessions.begin() as db:
   row=ProofEventRow(tenant_id=self.tenant_id,event_id=event['event_id'],producer=event['producer'],module_id=event['module_id'],requirement_id=event['requirement_id'],event_type=event['event_type'],proof_sha256=event['proof_sha256'],payload=event,persisted_at=datetime.now(timezone.utc));db.add(row)
   try:db.flush()
   except IntegrityError as exc:raise ValueError('verified producer event is immutable and already persisted') from exc
   return row
 def get(self,event_id:str):
  with self.sessions() as db:return db.scalar(select(ProofEventRow).where(ProofEventRow.tenant_id==self.tenant_id,ProofEventRow.event_id==event_id))
