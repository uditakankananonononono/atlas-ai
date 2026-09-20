from datetime import datetime,timezone
from sqlalchemy import JSON,DateTime,String,select
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base,SessionLocal,engine
from app.modules.m00_approval_center.service import ApprovalRequestRow
class BillingEventRow(Base):
 __tablename__="m24_billing_events";id:Mapped[str]=mapped_column(String(120),primary_key=True);type:Mapped[str]=mapped_column(String(120));payload:Mapped[dict]=mapped_column(JSON);processed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class BillingExecutionRow(Base):
 __tablename__="m24_billing_executions";approval_id:Mapped[str]=mapped_column(String(36),primary_key=True);result:Mapped[dict]=mapped_column(JSON);executed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
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
 def tenant_billing(self,tenant_id):
  with SessionLocal() as db:return db.get(TenantBillingRow,tenant_id)
 def upsert_tenant_billing(self,tenant_id,**values):
  with SessionLocal.begin() as db:
   row=db.get(TenantBillingRow,tenant_id)
   if row is None:row=TenantBillingRow(tenant_id=tenant_id);db.add(row)
   for key,value in values.items():setattr(row,key,value)
   db.flush();return {c.name:getattr(row,c.name) for c in row.__table__.columns}
 def record_usage(self,tenant_id,event_id,metric,quantity,idempotency_key,occurred_at,metadata):
  with SessionLocal.begin() as db:
   prior=db.scalar(select(UsageRow).where(UsageRow.tenant_id==tenant_id,UsageRow.idempotency_key==idempotency_key))
   if prior:return prior,False
   row=UsageRow(id=event_id,tenant_id=tenant_id,metric=metric,quantity=quantity,idempotency_key=idempotency_key,occurred_at=occurred_at,event_metadata=metadata);db.add(row);db.flush();return row,True
 def usage_totals(self,tenant_id,start,end):
  with SessionLocal() as db:
   rows=db.execute(select(UsageRow.metric,func.sum(UsageRow.quantity)).where(UsageRow.tenant_id==tenant_id,UsageRow.occurred_at>=start,UsageRow.occurred_at<end).group_by(UsageRow.metric)).all();return {metric:int(total) for metric,total in rows}
 def upsert_invoice(self,tenant_id,**values):
  with SessionLocal.begin() as db:
   row=db.get(InvoiceRow,values["id"])
   if row is None:row=InvoiceRow(tenant_id=tenant_id,**values);db.add(row)
   elif row.tenant_id==tenant_id:
    for key,value in values.items():setattr(row,key,value)
   else:raise PermissionError("invoice belongs to another tenant")
 def list_invoices(self,tenant_id,limit=100):
  with SessionLocal() as db:return list(db.scalars(select(InvoiceRow).where(InvoiceRow.tenant_id==tenant_id).order_by(InvoiceRow.period_end.desc()).limit(limit)))


class TenantBillingRow(Base):
 __tablename__="m24_tenant_billing"
 tenant_id:Mapped[str]=mapped_column(String(120),primary_key=True);plan_id:Mapped[str]=mapped_column(String(40),default="free");status:Mapped[str]=mapped_column(String(30),default="active")
 customer_id:Mapped[str|None]=mapped_column(String(200),nullable=True,index=True);subscription_id:Mapped[str|None]=mapped_column(String(200),nullable=True,index=True)
 current_period_start:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);current_period_end:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);cancel_at_period_end:Mapped[bool]=mapped_column(default=False)
class UsageRow(Base):
 __tablename__="m24_usage"
 id:Mapped[str]=mapped_column(String(36),primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);metric:Mapped[str]=mapped_column(String(80),index=True);quantity:Mapped[int];idempotency_key:Mapped[str]=mapped_column(String(160));occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True);event_metadata:Mapped[dict]=mapped_column(JSON,default=dict)
from sqlalchemy import UniqueConstraint,func
UsageRow.__table__.append_constraint(UniqueConstraint("tenant_id","idempotency_key",name="uq_m24_usage_tenant_key"))
class InvoiceRow(Base):
 __tablename__="m24_invoices"
 id:Mapped[str]=mapped_column(String(200),primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);status:Mapped[str]=mapped_column(String(40));currency:Mapped[str]=mapped_column(String(3));amount_due:Mapped[int];amount_paid:Mapped[int];period_start:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);period_end:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);hosted_invoice_url:Mapped[str|None]=mapped_column(String(2000),nullable=True)
