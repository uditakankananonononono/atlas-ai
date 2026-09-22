from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import JSON,DateTime,String,UniqueConstraint,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class CheckpointQueueRow(Base):
 __tablename__='m12_checkpoint_queue';__table_args__=(UniqueConstraint('tenant_id','run_id','checkpoint_sha256'),)
 id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);run_id:Mapped[str]=mapped_column(String(300),index=True);checkpoint_sha256:Mapped[str]=mapped_column(String(64));state:Mapped[str]=mapped_column(String(30),index=True);payload:Mapped[dict]=mapped_column(JSON);enqueued_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class CheckpointQueue:
 def __init__(self,tenant_id:str,sessions:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=sessions;Base.metadata.create_all(engine)
 def enqueue(self,result:dict):
  with self.sessions.begin() as db:
   active=db.scalar(select(CheckpointQueueRow).where(CheckpointQueueRow.tenant_id==self.tenant_id,CheckpointQueueRow.run_id==result['run_id'],CheckpointQueueRow.state=='queued'))
   if active and active.checkpoint_sha256!=result['checkpoint_sha256']:raise ValueError('run already has a different queued checkpoint')
   if active:return active
   row=CheckpointQueueRow(tenant_id=self.tenant_id,run_id=result['run_id'],checkpoint_sha256=result['checkpoint_sha256'],state='queued',payload=result,enqueued_at=datetime.now(timezone.utc));db.add(row)
   try:db.flush()
   except IntegrityError as exc:raise ValueError('checkpoint is already queued') from exc
   return row
