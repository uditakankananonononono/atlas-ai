from __future__ import annotations
import hashlib
from datetime import datetime,timezone
from sqlalchemy import LargeBinary,DateTime,String,UniqueConstraint,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class SourceMessageRow(Base):
 __tablename__='m10_promise_source_messages';__table_args__=(UniqueConstraint('tenant_id','message_id'),)
 id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);message_id:Mapped[str]=mapped_column(String(200),index=True);content_sha256:Mapped[str]=mapped_column(String(64));content_bytes:Mapped[bytes]=mapped_column(LargeBinary);persisted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class SourceMessageStore:
 def __init__(self,tenant_id:str,sessions:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=sessions;Base.metadata.create_all(engine)
 def persist(self,message_id,expected_sha256,data):
  actual=hashlib.sha256(data).hexdigest()
  if actual!=expected_sha256:raise ValueError('source-message byte hash mismatch')
  with self.sessions.begin() as db:
   existing=db.scalar(select(SourceMessageRow).where(SourceMessageRow.tenant_id==self.tenant_id,SourceMessageRow.message_id==message_id))
   if existing:
    if existing.content_sha256!=actual or existing.content_bytes!=data:raise ValueError('immutable source-message conflict')
    return existing
   row=SourceMessageRow(tenant_id=self.tenant_id,message_id=message_id,content_sha256=actual,content_bytes=data,persisted_at=datetime.now(timezone.utc));db.add(row)
   try:db.flush()
   except IntegrityError as exc:raise ValueError('source message already persisted') from exc
   return row
