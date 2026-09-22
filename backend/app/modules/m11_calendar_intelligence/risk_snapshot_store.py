from __future__ import annotations
import hashlib
from datetime import datetime,timezone
from sqlalchemy import LargeBinary,DateTime,String,UniqueConstraint,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class RiskSnapshotRow(Base):
 __tablename__='m11_risk_source_snapshots';__table_args__=(UniqueConstraint('tenant_id','content_sha256'),)
 id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);content_sha256:Mapped[str]=mapped_column(String(64));source_uri:Mapped[str]=mapped_column(String(2000));source_bytes:Mapped[bytes]=mapped_column(LargeBinary);persisted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class RiskSnapshotStore:
 def __init__(self,tenant_id:str,sessions:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=sessions;Base.metadata.create_all(engine)
 def persist(self,source_uri:str,expected_sha256:str,data:bytes):
  actual=hashlib.sha256(data).hexdigest()
  if actual!=expected_sha256:raise ValueError('source snapshot byte hash mismatch')
  with self.sessions.begin() as db:
   existing=db.scalar(select(RiskSnapshotRow).where(RiskSnapshotRow.tenant_id==self.tenant_id,RiskSnapshotRow.content_sha256==actual))
   if existing:
    if existing.source_bytes!=data or existing.source_uri!=source_uri:raise ValueError('immutable source snapshot conflict')
    return existing
   row=RiskSnapshotRow(tenant_id=self.tenant_id,content_sha256=actual,source_uri=source_uri,source_bytes=data,persisted_at=datetime.now(timezone.utc));db.add(row)
   try:db.flush()
   except IntegrityError as exc:raise ValueError('immutable source snapshot already persisted') from exc
   return row
