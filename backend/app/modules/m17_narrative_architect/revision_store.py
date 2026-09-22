from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import JSON,DateTime,String,UniqueConstraint,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class RevisionAcceptanceRow(Base):
 __tablename__='m17_revision_acceptances';__table_args__=(UniqueConstraint('tenant_id','essay_id','to_version'),)
 id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);essay_id:Mapped[str]=mapped_column(String(300),index=True);from_version:Mapped[str]=mapped_column(String(200));to_version:Mapped[str]=mapped_column(String(200));acceptance_sha256:Mapped[str]=mapped_column(String(64));payload:Mapped[dict]=mapped_column(JSON);persisted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class RevisionStore:
 def __init__(self,tenant_id:str,sessions:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=sessions;Base.metadata.create_all(engine)
 def persist(self,result:dict):
  with self.sessions.begin() as db:
   head=db.scalar(select(RevisionAcceptanceRow).where(RevisionAcceptanceRow.tenant_id==self.tenant_id,RevisionAcceptanceRow.essay_id==result['essay_id']).order_by(RevisionAcceptanceRow.id.desc()))
   if head and head.to_version!=result['from_version']:raise ValueError('revision chain break: from_version is not stored head')
   row=RevisionAcceptanceRow(tenant_id=self.tenant_id,essay_id=result['essay_id'],from_version=result['from_version'],to_version=result['to_version'],acceptance_sha256=result['acceptance_sha256'],payload=result,persisted_at=datetime.now(timezone.utc));db.add(row)
   try:db.flush()
   except IntegrityError as exc:raise ValueError('revision target version already persisted') from exc
   return row
