"""Verified TEST billing inbox. No default admission config or provider calls."""
from __future__ import annotations
import copy,hashlib,json,re
from dataclasses import dataclass
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import JSON,String,Integer,DateTime,ForeignKey,select,update
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.exc import IntegrityError
from app.core.database import Base
from app.modules.m00_approval_center.service import _aware
from . import write_ahead as wa
from .checkout_dispatcher import API_VERSION,CheckoutRepository
from .repository import TenantBillingRow,InvoiceRow
from .webhooks import verify_stripe_signature

class InboxRefused(wa.DispatchRefused):pass

class InboxRow(Base):
    __tablename__='m24_verified_inbox'
    identity:Mapped[str]=mapped_column(String(400),primary_key=True)
    provider_account:Mapped[str]=mapped_column(String(200))
    environment:Mapped[str]=mapped_column(String(20))
    event_id:Mapped[str]=mapped_column(String(120))
    event_type:Mapped[str]=mapped_column(String(120))
    created:Mapped[int]=mapped_column(Integer)
    digest:Mapped[str]=mapped_column(String(64))
    payload_digest:Mapped[str]=mapped_column(String(64))
    payload:Mapped[dict]=mapped_column(JSON)
    state:Mapped[str]=mapped_column(String(30),default='pending')
    failure:Mapped[str|None]=mapped_column(String(120),nullable=True)
    verified_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    applied_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class QuarantineRow(Base):
    __tablename__='m24_inbox_quarantine'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    event_id:Mapped[str]=mapped_column(String(120))
    digest:Mapped[str]=mapped_column(String(64))
    reason:Mapped[str]=mapped_column(String(120))
    observed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))

class ResourceBindingRow(Base):
    """Provisioned account/resource ownership; metadata alone cannot create it."""
    __tablename__='m24_inbox_resource_bindings'
    identity:Mapped[str]=mapped_column(String(400),primary_key=True)
    provider_account:Mapped[str]=mapped_column(String(200))
    environment:Mapped[str]=mapped_column(String(20))
    resource_id:Mapped[str]=mapped_column(String(200))
    tenant_id:Mapped[str]=mapped_column(String(120))
    customer_id:Mapped[str]=mapped_column(String(200))
    version:Mapped[int]=mapped_column(Integer,default=0)
    event_digest:Mapped[str|None]=mapped_column(String(64),nullable=True)

@dataclass(frozen=True)
class VerifiedEvent:
    account:str
    payload:dict
    raw_digest:str

class WebhookAdmission:
    def __init__(self,secret,provider_account,*,connected_account=None):
        if not isinstance(secret,str) or not secret:raise ValueError('webhook secret required')
        if not isinstance(provider_account,str) or not re.fullmatch(r'acct_[A-Za-z0-9_]{1,180}',provider_account):raise ValueError('endpoint account binding required')
        if connected_account is not None and connected_account!=provider_account:raise ValueError('connected account binding differs')
        self.secret=secret;self.account=provider_account;self.connected_account=connected_account
    def verify(self,payload,signature,*,now=None):
        wa.require_dispatch_ready() # No checked account/egress readiness => no operational admission.
        if not isinstance(payload,bytes) or len(payload)>262144:raise InboxRefused('bounded webhook payload required')
        data=verify_stripe_signature(payload,signature,self.secret,now=now)
        if not isinstance(data,dict) or data.get('object')!='event' or not isinstance(data.get('id'),str) or not re.fullmatch(r'evt_[A-Za-z0-9_]{1,110}',data['id']):raise InboxRefused('bounded event identity required')
        if data.get('livemode') is not False or data.get('api_version')!=API_VERSION:raise InboxRefused('event TEST version differs')
        if data.get('account')!=self.connected_account:raise InboxRefused('event endpoint account differs')
        if type(data.get('created')) is not int or not 0<data['created']<=int(datetime.now(timezone.utc).timestamp())+300:raise InboxRefused('event created time invalid')
        if not isinstance(data.get('type'),str) or len(data['type'])>120 or not isinstance(data.get('data'),dict) or not isinstance(data['data'].get('object'),dict):raise InboxRefused('event shape differs')
        return VerifiedEvent(self.account,copy.deepcopy(data),hashlib.sha256(payload).hexdigest())

def identity(account,resource):return account+':test:'+resource

class InboxRepository:
    def __init__(self,sessions):self.sessions=sessions
    def quarantine(self,event_id,digest,reason):
        with self.sessions.begin() as db:
            db.add(QuarantineRow(id=str(uuid4()),event_id=str(event_id)[:120],digest=digest,reason=reason,observed_at=datetime.now(timezone.utc)))
    def unsigned(self,event):
        raw=json.dumps(event.model_dump(),sort_keys=True,separators=(',',':')).encode()
        self.quarantine(event.id,hashlib.sha256(raw).hexdigest(),'unsigned-diagnostic')
        return {'id':event.id,'type':event.type,'processed':False,'processed_at':datetime.now(timezone.utc)}
    def admit(self,event):
        if not isinstance(event,VerifiedEvent):raise InboxRefused('signature verified event required')
        p=event.payload;ident=identity(event.account,p['id'])
        try:
            with self.sessions.begin() as db:
                row=db.get(InboxRow,ident)
                if row is None:
                    db.add(InboxRow(identity=ident,provider_account=event.account,environment='test',event_id=p['id'],event_type=p['type'],created=p['created'],digest=event.raw_digest,payload_digest=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest(),payload=copy.deepcopy(p),state='pending',verified_at=datetime.now(timezone.utc)))
                elif row.digest!=event.raw_digest:raise InboxRefused('same event identity changed digest')
        except IntegrityError:
            with self.sessions() as db:
                winner=db.get(InboxRow,ident)
                if winner is None or winner.digest!=event.raw_digest:raise InboxRefused('event admission race conflict')
        except InboxRefused:
            self.quarantine(p['id'],event.raw_digest,'verified-digest-conflict');raise
        return ident
    def get(self,ident):
        with self.sessions() as db:
            row=db.get(InboxRow,ident)
            if row is None:raise KeyError(ident)
            return {'id':row.event_id,'type':row.event_type,'state':row.state,'failure':row.failure,'processed':row.state=='applied','processed_at':row.applied_at or row.verified_at}
    def _binding(self,db,row,obj):
        resource=obj.get('subscription') if row.event_type.startswith('checkout.') else obj.get('id')
        if not isinstance(resource,str) or len(resource)>200:raise InboxRefused('resource identity unavailable')
        key=identity(row.provider_account,resource)
        # Bind and serialize by existing resource row, including SQLite writers.
        changed=db.execute(update(ResourceBindingRow).where(ResourceBindingRow.identity==key).values(version=ResourceBindingRow.version))
        if changed.rowcount!=1:raise InboxRefused('provisioned resource ownership unavailable')
        binding=db.get(ResourceBindingRow,key);db.refresh(binding)
        md=obj.get('metadata',{})
        if not isinstance(md,dict) or not any(field in md for field in ('atlas_tenant_id','tenant_id')):raise InboxRefused('tenant metadata unavailable')
        if binding.provider_account!=row.provider_account or binding.environment!=row.environment or binding.resource_id!=resource or binding.customer_id!=obj.get('customer'):raise InboxRefused('resource account customer tenant differs')
        for field in ('atlas_tenant_id','tenant_id'):
            if field in md and md[field]!=binding.tenant_id:raise InboxRefused('conflicting tenant metadata')
        if obj.get('client_reference_id') is not None and obj['client_reference_id']!=binding.tenant_id:raise InboxRefused('client reference tenant differs')
        db.execute(update(TenantBillingRow).where(TenantBillingRow.tenant_id==binding.tenant_id).values(status=TenantBillingRow.status))
        local=db.get(TenantBillingRow,binding.tenant_id)
        if local is None or local.customer_id!=binding.customer_id:raise InboxRefused('local customer mapping differs')
        if not row.event_type.startswith('invoice.') and local.subscription_id!=resource:raise InboxRefused('local subscription mapping differs')
        return binding,local
    def _apply(self,db,row,obj,binding,local):
        kind=row.event_type
        if obj.get('livemode') is not False:raise InboxRefused('resource TEST identity differs')
        if kind=='checkout.session.completed':
            if obj.get('object')!='checkout.session' or obj.get('status')!='complete' or obj.get('payment_status')!='paid' or obj.get('mode')!='subscription':raise InboxRefused('checkout not confirmed paid complete')
            md=obj['metadata'];op=db.get(wa.OperationRow,md.get('atlas_operation_id'))
            if op is None or op.action_type!='create_subscription_checkout' or op.state!='succeeded' or op.tenant_id!=binding.tenant_id or op.provider_account!=row.provider_account or op.environment!='test' or op.api_version!=API_VERSION or op.approval_id!=md.get('atlas_approval_id') or not op.result or op.result.get('id')!=obj.get('id'):raise InboxRefused('checkout durable operation differs')
            if md.get('plan_id')!=op.request['plan']['id'] or md.get('atlas_operation_step')!='checkout':raise InboxRefused('checkout plan binding differs')
            if obj.get('currency')!='usd' or type(obj.get('amount_total')) is not int or obj['amount_total']!=int(op.result['amount_total']):raise InboxRefused('checkout amount differs')
            if op.dispatch_not_after and row.created>int(_aware(op.dispatch_not_after).timestamp()):raise InboxRefused('checkout commitment deadline differs')
            local.plan_id=md['plan_id'];local.status='active'
        elif kind in {'customer.subscription.updated','customer.subscription.deleted'}:
            statuses={'trialing','active','past_due','canceled','incomplete','incomplete_expired','unpaid','paused'}
            if obj.get('object')!='subscription' or obj.get('status') not in statuses or type(obj.get('cancel_at_period_end')) is not bool:raise InboxRefused('subscription lifecycle shape differs')
            if kind.endswith('deleted') and obj['status']!='canceled':raise InboxRefused('deleted subscription not canceled')
            local.status=obj['status'];local.cancel_at_period_end=obj['cancel_at_period_end']
            for field in ('current_period_start','current_period_end'):
                value=obj.get(field)
                if value is not None and (type(value) is not int or not 0<value<253402300800):raise InboxRefused('subscription period differs')
                setattr(local,field,datetime.fromtimestamp(value,timezone.utc) if value is not None else None)
        elif kind in {'invoice.paid','invoice.payment_failed','invoice.updated'}:
            if obj.get('object')!='invoice' or obj.get('currency')!='usd' or obj.get('status') not in {'draft','open','paid','uncollectible','void'} or any(type(obj.get(k)) is not int or not 0<=obj[k]<=100000000 for k in ('amount_due','amount_paid')):raise InboxRefused('invoice lifecycle shape differs')
            if kind=='invoice.paid' and (obj['status']!='paid' or obj['amount_paid']<obj['amount_due']):raise InboxRefused('invoice not confirmed paid')
            current=db.get(InvoiceRow,obj['id'])
            if current is not None and current.tenant_id!=binding.tenant_id:raise InboxRefused('invoice tenant differs')
            if current is None:
                current=InvoiceRow(id=obj['id'],tenant_id=binding.tenant_id);db.add(current)
            for field in ('status','currency','amount_due','amount_paid'):setattr(current,field,obj[field])
            # Provider-hosted URLs are not admitted as trusted navigation targets.
        else:raise InboxRefused('unsupported lifecycle event')
    def apply(self,ident,*,hook=None):
        hook=hook or (lambda point:None)
        try:
            with self.sessions.begin() as db:
                db.execute(update(InboxRow).where(InboxRow.identity==ident).values(state=InboxRow.state))
                row=db.get(InboxRow,ident)
                if row is None:raise KeyError(ident)
                if row.state in {'applied','ignored_stale','held'}:return {'id':row.event_id,'type':row.event_type,'state':row.state,'failure':row.failure,'processed':row.state=='applied','processed_at':row.applied_at or row.verified_at}
                if row.payload_digest!=hashlib.sha256(json.dumps(row.payload,sort_keys=True,separators=(',',':')).encode()).hexdigest():raise InboxRefused('stored event payload digest differs')
                obj=row.payload['data']['object'];binding,local=self._binding(db,row,obj)
                if row.created<binding.version:row.state='ignored_stale';row.failure='older-resource-event'
                elif row.created==binding.version and binding.event_digest!=row.digest:row.state='held';row.failure='equal-time-resource-conflict'
                else:
                    self._apply(db,row,obj,binding,local);db.flush();hook('inside-apply')
                    binding.version=row.created;binding.event_digest=row.digest;row.state='applied';row.failure=None
                    row.applied_at=datetime.now(timezone.utc);hook('before-apply-commit')
            hook('after-apply-commit')
        except Exception:
            # Rollback lifecycle+cursor+marker, retain admitted pending event.
            with self.sessions.begin() as db:
                row=db.get(InboxRow,ident)
                if row is not None and row.state=='pending':row.failure='lifecycle-apply-refused'
            raise
        return self.get(ident)
