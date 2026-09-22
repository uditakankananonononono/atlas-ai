from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import JSON,DateTime,String,UniqueConstraint,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class PublicationReceiptRow(Base):
 __tablename__='m15_provider_publication_receipts';__table_args__=(UniqueConstraint('tenant_id','approval_id'),UniqueConstraint('tenant_id','provider','object_key'))
 id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);approval_id:Mapped[str]=mapped_column(String(200));version_id:Mapped[str]=mapped_column(String(200));provider:Mapped[str]=mapped_column(String(200));object_key:Mapped[str]=mapped_column(String(1000));published_sha256:Mapped[str]=mapped_column(String(64));payload:Mapped[dict]=mapped_column(JSON);persisted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class PublicationReceiptStore:
 def __init__(self,tenant_id:str,sessions:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=sessions;Base.metadata.create_all(engine)
 def persist(self,receipt:dict):
  with self.sessions.begin() as db:
   row=PublicationReceiptRow(tenant_id=self.tenant_id,approval_id=receipt['approval_id'],version_id=receipt['version_id'],provider=receipt['provider'],object_key=receipt['object_key'],published_sha256=receipt['published_sha256'],payload=receipt,persisted_at=datetime.now(timezone.utc));db.add(row)
   try:db.flush()
   except IntegrityError as exc:raise ValueError('publication receipt is immutable and already persisted for approval or object') from exc
   return row
 def get(self,approval_id:str):
  with self.sessions() as db:return db.scalar(select(PublicationReceiptRow).where(PublicationReceiptRow.tenant_id==self.tenant_id,PublicationReceiptRow.approval_id==approval_id))
