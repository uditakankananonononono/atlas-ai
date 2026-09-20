from datetime import datetime,timezone
from sqlalchemy import JSON,DateTime,String,select
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base,SessionLocal,engine
from app.modules.m00_approval_center.service import ApprovalRequestRow
class BillingEventRow(Base):
 __tablename__="m23_billing_events";id:Mapped[str]=mapped_column(String(120),primary_key=True);type:Mapped[str]=mapped_column(String(120));payload:Mapped[dict]=mapped_column(JSON);processed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class BillingExecutionRow(Base):
 __tablename__="m23_billing_executions";approval_id:Mapped[str]=mapped_column(String(36),primary_key=True);result:Mapped[dict]=mapped_column(JSON);executed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class Repository:
 def __init__(self):Base.metadata.create_all(engine)
 def approval(self,aid):
  with SessionLocal() as db:r=db.get(ApprovalRequestRow,aid);return {"status":r.status,"payload":r.payload} if r else None
 def record_execution(self,aid,result):
  with SessionLocal.begin() as db:
   if db.get(BillingExecutionRow,aid):raise RuntimeError("billing approval already executed")
   db.add(BillingExecutionRow(approval_id=aid,result=result,executed_at=datetime.now(timezone.utc)))
 def save_event(self,event):
  with SessionLocal.begin() as db:
   if db.get(BillingEventRow,event.id):return False
   db.add(BillingEventRow(id=event.id,type=event.type,payload=event.data,processed_at=datetime.now(timezone.utc)));return True
