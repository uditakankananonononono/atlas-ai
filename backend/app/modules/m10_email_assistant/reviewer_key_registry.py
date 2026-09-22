from __future__ import annotations
import base64,hashlib
from datetime import datetime,timezone
from sqlalchemy import LargeBinary,Boolean,DateTime,String,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from pydantic import BaseModel,Field
from app.core.database import Base,SessionLocal,engine
class ReviewerKeyRow(Base):
 __tablename__='m10_reviewer_public_keys';__table_args__=(UniqueConstraint('tenant_id','reviewer_id','key_id'),)
 id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);reviewer_id:Mapped[str]=mapped_column(String(200));key_id:Mapped[str]=mapped_column(String(200));public_key:Mapped[bytes]=mapped_column(LargeBinary);fingerprint_sha256:Mapped[str]=mapped_column(String(64));active:Mapped[bool]=mapped_column(Boolean);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));retired_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class RegisterReviewerKey(BaseModel):reviewer_id:str=Field(min_length=1);key_id:str=Field(min_length=1);public_key_base64:str=Field(min_length=1)
class ReviewerKeyRegistry:
 def __init__(self,tenant_id:str,sessions:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=sessions;Base.metadata.create_all(engine)
 def register(self,b:RegisterReviewerKey):
  try:raw=base64.b64decode(b.public_key_base64,validate=True)
  except Exception as exc:raise ValueError('invalid public key encoding') from exc
  if len(raw)!=32:raise ValueError('Ed25519 public key must be 32 bytes')
  with self.sessions.begin() as db:
   row=db.scalar(select(ReviewerKeyRow).where(ReviewerKeyRow.tenant_id==self.tenant_id,ReviewerKeyRow.reviewer_id==b.reviewer_id,ReviewerKeyRow.key_id==b.key_id))
   if row:
    if row.public_key!=raw:raise ValueError('key_id is already bound to different public key bytes')
    return row
   row=ReviewerKeyRow(tenant_id=self.tenant_id,reviewer_id=b.reviewer_id,key_id=b.key_id,public_key=raw,fingerprint_sha256=hashlib.sha256(raw).hexdigest(),active=True,created_at=datetime.now(timezone.utc),retired_at=None);db.add(row);db.flush();return row
 def retire(self,reviewer_id,key_id):
  with self.sessions.begin() as db:
   row=db.scalar(select(ReviewerKeyRow).where(ReviewerKeyRow.tenant_id==self.tenant_id,ReviewerKeyRow.reviewer_id==reviewer_id,ReviewerKeyRow.key_id==key_id))
   if not row:raise ValueError('reviewer key not found')
   row.active=False;row.retired_at=datetime.now(timezone.utc);db.flush();return row
