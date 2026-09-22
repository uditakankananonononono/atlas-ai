"""Tenant-scoped append-only storage for verified live acceptance receipts."""
from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import JSON,DateTime,String,UniqueConstraint,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class LiveReceiptRow(Base):
 __tablename__='m14_verified_live_receipts';__table_args__=(UniqueConstraint('tenant_id','receipt_id'),)
 id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);receipt_id:Mapped[str]=mapped_column(String(200),index=True);requirement_id:Mapped[str]=mapped_column(String(300),index=True);deployed_version:Mapped[str]=mapped_column(String(300));environment:Mapped[str]=mapped_column(String(200));acceptance_inputs_sha256:Mapped[str]=mapped_column(String(64));proof_sha256:Mapped[str]=mapped_column(String(64));payload:Mapped[dict]=mapped_column(JSON);persisted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class LiveReceiptStore:
 def __init__(self,tenant_id:str,sessions:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=sessions;Base.metadata.create_all(engine)
 def persist(self,receipt:dict):
  with self.sessions.begin() as db:
   row=LiveReceiptRow(tenant_id=self.tenant_id,receipt_id=receipt['receipt_id'],requirement_id=receipt['requirement_id'],deployed_version=receipt['deployed_version'],environment=receipt['environment'],acceptance_inputs_sha256=receipt['acceptance_inputs_sha256'],proof_sha256=receipt['result_sha256'],payload=receipt,persisted_at=datetime.now(timezone.utc));db.add(row)
   try:db.flush()
   except IntegrityError as exc:raise ValueError('verified live receipt is immutable and already persisted') from exc
   return row
 def get(self,receipt_id:str):
  with self.sessions() as db:return db.scalar(select(LiveReceiptRow).where(LiveReceiptRow.tenant_id==self.tenant_id,LiveReceiptRow.receipt_id==receipt_id))
