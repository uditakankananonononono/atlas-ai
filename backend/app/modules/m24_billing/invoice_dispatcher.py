"""Invoice durable substeps. No activation or operational provider readiness."""
from __future__ import annotations
import copy
import asyncio
import httpx
from uuid import uuid4
from datetime import timedelta
import re
from datetime import datetime
from sqlalchemy import JSON,String,DateTime,Integer,ForeignKey,UniqueConstraint,CheckConstraint,select,update,exists
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.modules.m00_approval_center.service import ApprovalRequestRow,_aware
from . import write_ahead as wa
from .checkout_dispatcher import API_VERSION,digest,CheckoutRepository
from .repository import TenantBillingRow

class InvoiceStepRow(Base):
    __tablename__='m24_invoice_steps'
    __table_args__=(UniqueConstraint('operation_id','role'),UniqueConstraint('provider_key'),
        CheckConstraint("role IN ('draft-invoice','invoice-item')"))
    id:Mapped[str]=mapped_column(String(80),primary_key=True)
    operation_id:Mapped[str]=mapped_column(String(36),ForeignKey('m24_provider_operations.id'),index=True)
    role:Mapped[str]=mapped_column(String(40))
    provider_key:Mapped[str]=mapped_column(String(80))
    endpoint:Mapped[str]=mapped_column(String(120))
    form:Mapped[dict]=mapped_column(JSON)
    binding_hash:Mapped[str]=mapped_column(String(64))
    state:Mapped[str]=mapped_column(String(40))
    fence:Mapped[str|None]=mapped_column(String(36),nullable=True)
    lease_until:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    first_attempt_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    dispatch_not_after:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    result:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    failure:Mapped[str|None]=mapped_column(String(80),nullable=True)

class InvoiceStepAttemptRow(Base):
    __tablename__='m24_invoice_step_attempts'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    step_id:Mapped[str]=mapped_column(String(80),ForeignKey('m24_invoice_steps.id'),index=True)
    fence:Mapped[str]=mapped_column(String(36),unique=True)
    binding_hash:Mapped[str]=mapped_column(String(64))
    at:Mapped[datetime]=mapped_column(DateTime(timezone=True))


def step_out(row):
    return {name:copy.deepcopy(getattr(row,name)) for name in ('id','operation_id','role','provider_key','endpoint','form','binding_hash','state','fence','result','failure','first_attempt_at','dispatch_not_after')}


def binding(op,role,form):
    return digest({'parent':op.id,'tenant':op.tenant_id,'approval':op.approval_id,'request':op.request_hash,
        'account':op.provider_account,'environment':op.environment,'version':op.api_version,'role':role,
        'key':op.id+':'+role,'form':form,'adapter':'atlas-invoice-v2'})


def validate_parent(db,op,*,check_cancellation=False):
    p=op.request
    if op.action_type!='issue_invoice' or p.get('effect')!='create_draft_invoice' or p.get('provider')!='stripe' or p.get('tenant_id')!=op.tenant_id:
        raise wa.DispatchRefused('invoice authority binding invalid')
    if op.environment!='test' or op.api_version!=API_VERSION:raise wa.DispatchRefused('invoice TEST version required')
    if not isinstance(p.get('customer_id'),str) or not re.fullmatch(r'cus_[A-Za-z0-9_]{1,196}',p['customer_id']):raise wa.DispatchRefused('invoice customer identifier invalid')
    customer=db.get(TenantBillingRow,op.tenant_id)
    if customer is None or customer.customer_id!=p['customer_id']:raise wa.DispatchRefused('invoice customer tenant mapping required')
    from .cancellation import CancellationSnapshotRow
    cancelled=db.scalar(select(wa.OperationRow.id).join(CancellationSnapshotRow,CancellationSnapshotRow.operation_id==wa.OperationRow.id).where(
        wa.OperationRow.tenant_id==op.tenant_id,CancellationSnapshotRow.customer_id==p['customer_id'],
        wa.OperationRow.state!='cancelled_before_dispatch'))
    if check_cancellation and cancelled is not None:raise wa.DispatchRefused('invoice customer cancellation fence active')
    # A local mapping is only preliminary. Actual adapter account/customer identity
    # must be checked before dispatch; no live account readiness claimed here.
    if type(p.get('amount_cents')) is not int or not 1<=p['amount_cents']<=100000000:raise wa.DispatchRefused('invoice amount invalid')
    if not isinstance(p.get('currency'),str) or not re.fullmatch('[a-z]{3}',p['currency']):raise wa.DispatchRefused('invoice currency invalid')
    if not isinstance(p.get('description'),str) or not 1<=len(p['description'])<=1000:raise wa.DispatchRefused('invoice description invalid')
    return p


def make_form(op,role,invoice_id=None):
    p=op.request
    md={'metadata[atlas_operation_id]':op.id,'metadata[atlas_operation_step]':role,'metadata[atlas_approval_id]':op.approval_id}
    if role=='draft-invoice':return {'customer':p['customer_id'],'currency':p['currency'],'auto_advance':'false','pending_invoice_items_behavior':'exclude',**md}
    if role!='invoice-item' or not isinstance(invoice_id,str) or not re.fullmatch(r'in_[A-Za-z0-9_]{1,196}',invoice_id):raise wa.DispatchRefused('committed invoice identifier required')
    return {'customer':p['customer_id'],'invoice':invoice_id,'amount':str(p['amount_cents']),'currency':p['currency'],
        'description':p['description'],'discountable':'false',**md}


def add_step(db,op,role,invoice_id=None):
    form=make_form(op,role,invoice_id)
    step=InvoiceStepRow(id=op.id+':'+role,operation_id=op.id,role=role,provider_key=op.id+':'+role,
        endpoint='/v1/invoices' if role=='draft-invoice' else '/v1/invoiceitems',form=form,binding_hash=binding(op,role,form),state='prepared')
    db.add(step);return step


def validate_bounded_receipt(op,row,result):
    role=row.role
    prefix='in_' if role=='draft-invoice' else 'ii_'
    if set(result)!={'id','object','customer','currency','livemode','invoice','amount'} or not isinstance(result['id'],str) or not re.fullmatch(prefix+r'[A-Za-z0-9_]{1,196}',result['id']) or result['customer']!=op.request['customer_id'] or result['currency']!=op.request['currency'] or result['livemode'] is not False or result['object']!=('invoice' if role=='draft-invoice' else 'invoiceitem'):
        raise ValueError('invalid bounded invoice receipt')
    if role=='invoice-item' and (result['invoice']!=row.form['invoice'] or type(result['amount']) is not int or result['amount']!=op.request['amount_cents']):raise ValueError('invoice item receipt binding differs')
    if role=='draft-invoice' and (result['invoice'] is not None or type(result['amount']) is not int or result['amount']!=0):raise ValueError('draft receipt differs')


class InvoiceRepository(wa.OperationRepository):
    def _add_snapshot(self,db,op,approval):
        db.execute(update(TenantBillingRow).where(TenantBillingRow.tenant_id==op.tenant_id).values(status=TenantBillingRow.status))
        validate_parent(db,op,check_cancellation=True)
        op.provider_key=op.id+':invoice-parent' # Parent itself never calls a provider.
        add_step(db,op,'draft-invoice')

    def prepare(self,*args,**kwargs):
        if kwargs.get('provider_key') is not None:raise wa.DispatchRefused('invoice keys server assigned')
        result=super().prepare(*args,**kwargs)
        self.steps(result['id'],result['tenant_id'])
        return result

    def steps(self,operation_id,tenant_id):
        with self.sessions() as db:
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            validate_parent(db,op)
            rows=db.scalars(select(InvoiceStepRow).where(InvoiceStepRow.operation_id==operation_id)).all()
            if not any(r.role=='draft-invoice' for r in rows):raise wa.DispatchRefused('legacy invoice has no exact draft snapshot')
            for row in rows:
                if row.provider_key!=op.id+':'+row.role or row.id!=row.provider_key or row.binding_hash!=binding(op,row.role,row.form):raise wa.DispatchRefused('invoice immutable step differs')
                if row.role=='draft-invoice' and row.form!=make_form(op,row.role):raise wa.DispatchRefused('invoice draft form differs')
                if row.role=='invoice-item':
                    draft=next(r for r in rows if r.role=='draft-invoice')
                    if draft.state!='succeeded' or not draft.result or row.form!=make_form(op,row.role,draft.result.get('id')):raise wa.DispatchRefused('invoice item dependency differs')
            return {row.role:step_out(row) for row in rows}

    def prepare_item(self,operation_id,tenant_id):
        with self.sessions.begin() as db:
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==op.approval_id).values(status=ApprovalRequestRow.status))
            db.refresh(op)
            db.execute(update(TenantBillingRow).where(TenantBillingRow.tenant_id==op.tenant_id).values(status=TenantBillingRow.status))
            validate_parent(db,op,check_cancellation=True)
            if op.state!='prepared':raise wa.DispatchRefused('invoice parent cancelled or held')
            # Reuse shared authority validator, not a duplicated approval-consumption path.
            authority=CheckoutRepository(self.approvals)
            authority._authority(db,op,authority._now(db))
            draft=db.get(InvoiceStepRow,operation_id+':draft-invoice')
            if draft is None or draft.state!='succeeded' or not draft.result:raise wa.DispatchRefused('invoice draft outcome not committed')
            if draft.binding_hash!=binding(op,draft.role,draft.form) or draft.provider_key!=op.id+':draft-invoice' or draft.form!=make_form(op,'draft-invoice'):raise wa.DispatchRefused('invoice draft binding differs')
            validate_bounded_receipt(op,draft,draft.result)
            existing=db.get(InvoiceStepRow,operation_id+':invoice-item')
            if existing:
                if existing.form!=make_form(op,'invoice-item',draft.result.get('id')) or existing.binding_hash!=binding(op,existing.role,existing.form):raise wa.DispatchRefused('invoice item binding differs')
                return step_out(existing)
            step=add_step(db,op,'invoice-item',draft.result.get('id'));db.flush();result=step_out(step)
        return result

    def _load(self,db,operation_id,tenant_id,role):
        op=db.get(wa.OperationRow,operation_id)
        if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
        validate_parent(db,op)
        row=db.get(InvoiceStepRow,operation_id+':'+role)
        if row is None or row.binding_hash!=binding(op,role,row.form) or row.provider_key!=operation_id+':'+role or row.endpoint!=('/v1/invoices' if role=='draft-invoice' else '/v1/invoiceitems'):
            raise wa.DispatchRefused('invoice exact step binding required')
        if row.role!=role or row.operation_id!=op.id or op.provider_key!=op.id+':invoice-parent':raise wa.DispatchRefused('invoice parent/role binding differs')
        if role=='invoice-item':
            draft=db.get(InvoiceStepRow,operation_id+':draft-invoice')
            if draft is None or draft.state!='succeeded' or not draft.result:raise wa.DispatchRefused('invoice draft outcome not committed')
            validate_bounded_receipt(op,draft,draft.result)
            if row.form!=make_form(op,role,draft.result.get('id')):raise wa.DispatchRefused('invoice dependency form differs')
        elif row.form!=make_form(op,role):raise wa.DispatchRefused('invoice draft form differs')
        return op,row

    def step(self,operation_id,tenant_id,role):
        with self.sessions() as db:
            op,row=self._load(db,operation_id,tenant_id,role)
            return {'operation':wa._out(op),'step':step_out(row)}

    def claim_step(self,operation_id,tenant_id,role):
        wa.require_dispatch_ready()
        clock=CheckoutRepository(self.approvals);fence=str(uuid4())
        with self.sessions.begin() as db:
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==op.approval_id).values(status=ApprovalRequestRow.status))
            db.refresh(op)
            db.execute(update(TenantBillingRow).where(TenantBillingRow.tenant_id==op.tenant_id).values(status=TenantBillingRow.status))
            op,row=self._load(db,operation_id,tenant_id,role)
            validate_parent(db,op,check_cancellation=True)
            now=clock._now(db);authority_bound=clock._authority(db,op,now)
            if op.state!='prepared':raise wa.DispatchRefused('invoice parent held')
            first=_aware(row.first_attempt_at) if row.first_attempt_at else now
            bound=first+timedelta(hours=12)
            if row.dispatch_not_after:bound=min(bound,_aware(row.dispatch_not_after))
            if authority_bound:bound=min(bound,authority_bound)
            if now>=bound:raise wa.DispatchRefused('invoice step dispatch bound elapsed')
            barrier=exists(select(wa.CutoverRow.id).where(wa.CutoverRow.id==1,wa.CutoverRow.protocol_epoch==2,
                wa.CutoverRow.state=='verified-active',wa.CutoverRow.verification_digest.is_not(None),wa.CutoverRow.verified_at.is_not(None)))
            changed=db.execute(update(InvoiceStepRow).where(InvoiceStepRow.id==row.id,InvoiceStepRow.state=='prepared',InvoiceStepRow.fence.is_(None),barrier).values(
                state='dispatching',fence=fence,lease_until=now+timedelta(seconds=60),first_attempt_at=first,dispatch_not_after=bound))
            if changed.rowcount!=1:raise wa.DispatchRefused('invoice step held or cutover locked')
            db.add(InvoiceStepAttemptRow(id=str(uuid4()),step_id=row.id,fence=fence,binding_hash=row.binding_hash,at=now))
            db.add(wa.OperationEventRow(operation_id=op.id,event=role+':dispatch-reserved',actor='m24-worker',at=now))
        return fence

    def before_step_entry(self,operation_id,tenant_id,role,fence):
        wa.require_dispatch_ready();clock=CheckoutRepository(self.approvals)
        with self.sessions() as db:
            op,row=self._load(db,operation_id,tenant_id,role);validate_parent(db,op,check_cancellation=True);now=clock._now(db);clock._authority(db,op,now)
            barrier=db.get(wa.CutoverRow,1)
            if barrier is None or barrier.protocol_epoch!=2 or barrier.state!='verified-active' or not barrier.verification_digest or not barrier.verified_at:
                raise wa.DispatchRefused('invoice cutover lost')
            if op.state!='prepared' or row.state!='dispatching' or row.fence!=fence or row.lease_until is None or _aware(row.lease_until)<=now or row.dispatch_not_after is None or _aware(row.dispatch_not_after)<=now:
                raise wa.DispatchRefused('invoice step fence/deadline lost')
            return {'operation':wa._out(op),'step':step_out(row)}

    def step_outcome(self,operation_id,tenant_id,role,fence,*,state,result=None,failure=None):
        if state not in {'succeeded','outcome_unknown','failed_before_dispatch'} or (state=='succeeded')!=(result is not None):raise ValueError('invalid invoice outcome')
        clock=CheckoutRepository(self.approvals)
        with self.sessions.begin() as db:
            # Approval lock gives the same order as prepare/claim, including competing completions.
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==op.approval_id).values(status=ApprovalRequestRow.status))
            db.refresh(op)
            db.execute(update(TenantBillingRow).where(TenantBillingRow.tenant_id==op.tenant_id).values(status=TenantBillingRow.status))
            op,row=self._load(db,operation_id,tenant_id,role)
            if row.fence!=fence or row.state not in {'dispatching','outcome_unknown'}:raise wa.DispatchRefused('invoice stale or terminal step')
            if state=='failed_before_dispatch' and row.state!='dispatching':raise wa.DispatchRefused('invoice unknown cannot become pre-entry safe')
            now=clock._now(db)
            if result is not None:
                validate_bounded_receipt(op,row,result)
                row.result=copy.deepcopy(result)
                row.state='succeeded_late' if op.state!='prepared' or row.state=='outcome_unknown' or _aware(row.lease_until)<=now else 'succeeded'
            else:row.state=state
            row.failure=failure
            db.add(wa.OperationEventRow(operation_id=op.id,event=role+':'+row.state,actor='m24-worker',at=now))
        return self.step(operation_id,tenant_id,role)

    def hold_final(self,operation_id,tenant_id,reason):
        with self.sessions.begin() as db:
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            changed=db.execute(update(wa.OperationRow).where(wa.OperationRow.id==op.id,wa.OperationRow.state=='prepared').values(state='outcome_unknown',failure=reason))
            if changed.rowcount:db.add(wa.OperationEventRow(operation_id=op.id,event='invoice-final-held',actor='m24-worker',at=CheckoutRepository(self.approvals)._now(db)))
        return self.get(operation_id,tenant_id)

    def finish(self,operation_id,tenant_id,invoice_id,item_id,verified_invoice):
        with self.sessions.begin() as db:
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==op.approval_id).values(status=ApprovalRequestRow.status))
            db.refresh(op)
            db.execute(update(TenantBillingRow).where(TenantBillingRow.tenant_id==op.tenant_id).values(status=TenantBillingRow.status))
            op,draft=self._load(db,operation_id,tenant_id,'draft-invoice');_,item=self._load(db,operation_id,tenant_id,'invoice-item')
            if op.state!='prepared' or draft.state!='succeeded' or item.state!='succeeded' or draft.result['id']!=invoice_id or item.result['id']!=item_id:raise wa.DispatchRefused('invoice completion dependency differs')
            validate_parent(db,op,check_cancellation=True)
            validate_final(verified_invoice,wa._out(op),step_out(draft),step_out(item))
            op.state='succeeded';op.result={'invoice_id':invoice_id,'invoice_item_id':item_id,'status':'draft','amount_cents':op.request['amount_cents'],'currency':op.request['currency']}
            db.add(wa.OperationEventRow(operation_id=op.id,event='invoice-verified-complete',actor='m24-worker',at=CheckoutRepository(self.approvals)._now(db)))
        return self.get(operation_id,tenant_id)


class InvoiceAdapter:
    def __init__(self,secret_key,provider_account,transport=None):
        if not isinstance(secret_key,str) or not secret_key.startswith('sk_test_'):raise ValueError('invoice TEST key required')
        wa._text(provider_account,'provider_account',200);self.key=secret_key;self.provider_account=provider_account;self.transport=transport

    def validate(self,snapshot):
        op=snapshot['operation'];row=snapshot['step']
        if op['provider_account']!=self.provider_account or op['environment']!='test' or op['api_version']!=API_VERSION:raise wa.DispatchRefused('invoice adapter binding differs')
        return httpx.Request('POST','https://api.stripe.com'+row['endpoint'],data=row['form'],headers={'Authorization':'Bearer '+self.key,'Stripe-Version':API_VERSION,'Idempotency-Key':row['provider_key']})

    async def invoke(self,request):
        async with httpx.AsyncClient(transport=self.transport,timeout=30) as client:r=await client.send(request)
        r.raise_for_status();return r.json()

    async def read_invoice(self,invoice_id):
        if not isinstance(invoice_id,str) or not re.fullmatch(r'in_[A-Za-z0-9_]{1,196}',invoice_id):raise ValueError('invalid invoice handle')
        async with httpx.AsyncClient(transport=self.transport,timeout=30) as client:
            r=await client.get('https://api.stripe.com/v1/invoices/'+invoice_id,headers={'Authorization':'Bearer '+self.key,'Stripe-Version':API_VERSION})
        r.raise_for_status();return r.json()


def validate_receipt(raw,snapshot):
    op=snapshot['operation'];row=snapshot['step'];p=op['request'];role=row['role']
    if not isinstance(raw,dict) or raw.get('livemode') is not False or raw.get('customer')!=p['customer_id'] or raw.get('currency')!=p['currency'] or raw.get('object')!=('invoice' if role=='draft-invoice' else 'invoiceitem'):raise ValueError('invoice response binding differs')
    md=raw.get('metadata')
    expected={'atlas_operation_id':op['id'],'atlas_operation_step':role,'atlas_approval_id':op['approval_id']}
    if not isinstance(md,dict) or any(md.get(k)!=v for k,v in expected.items()):raise ValueError('invoice receipt metadata differs')
    ident=raw.get('id');prefix='in_' if role=='draft-invoice' else 'ii_'
    if not isinstance(ident,str) or not re.fullmatch(prefix+r'[A-Za-z0-9_]{1,196}',ident):raise ValueError('invoice receipt handle invalid')
    if role=='draft-invoice':
        if raw.get('status')!='draft' or raw.get('auto_advance') is not False or type(raw.get('total')) is not int or raw.get('total')!=0:raise ValueError('draft response differs')
        attached=None;amount=0
    else:
        if raw.get('invoice')!=row['form']['invoice'] or type(raw.get('amount')) is not int or raw['amount']!=p['amount_cents'] or raw.get('description')!=p['description']:raise ValueError('invoice item response differs')
        attached=raw['invoice'];amount=raw['amount']
    return {'id':ident,'object':raw['object'],'customer':raw['customer'],'currency':raw['currency'],'livemode':False,'invoice':attached,'amount':amount}


def validate_final(raw,parent,draft,item):
    p=parent['request']
    if not isinstance(raw,dict) or raw.get('id')!=draft['result']['id'] or raw.get('object')!='invoice' or raw.get('status')!='draft' or raw.get('auto_advance') is not False or raw.get('livemode') is not False or raw.get('customer')!=p['customer_id'] or raw.get('currency')!=p['currency'] or type(raw.get('total')) is not int or raw['total']!=p['amount_cents']:raise ValueError('invoice final total or binding differs')
    md=raw.get('metadata',{})
    if not isinstance(md,dict) or md.get('atlas_operation_id')!=parent['id'] or md.get('atlas_operation_step')!='draft-invoice' or md.get('atlas_approval_id')!=parent['approval_id']:raise ValueError('invoice final metadata differs')
    lines=raw.get('lines')
    # Conservative hold on paginated/incomplete data. No invented default-page completeness.
    if not isinstance(lines,dict) or lines.get('has_more') is not False or not isinstance(lines.get('data'),list) or len(lines['data'])!=1:raise ValueError('invoice line set incomplete or not exact')
    line=lines['data'][0]
    # Version-specific parent shape must be confirmed in TEST before readiness.
    parent_ref=line.get('parent',{}).get('invoice_item_details',{}).get('invoice_item') if isinstance(line,dict) and isinstance(line.get('parent'),dict) else None
    if parent_ref!=item['result']['id'] or type(line.get('amount')) is not int or line.get('amount')!=p['amount_cents'] or line.get('currency')!=p['currency'] or line.get('description')!=p['description']:raise ValueError('invoice final item binding differs')


class InvoiceDispatcher:
    def __init__(self,repository,adapter):self.repo=repository;self.adapter=adapter

    async def _step(self,operation_id,tenant_id,role):
        snapshot=self.repo.step(operation_id,tenant_id,role)
        if snapshot['step']['state']!='prepared':return snapshot
        request=self.adapter.validate(snapshot);wa.require_dispatch_ready()
        try:fence=self.repo.claim_step(operation_id,tenant_id,role)
        except wa.DispatchRefused:return self.repo.step(operation_id,tenant_id,role)
        except Exception:return {'step':{'state':'outcome_unknown','failure':'claim-commit-unconfirmed'}}
        try:
            committed=self.repo.step(operation_id,tenant_id,role)
            if committed['step']['fence']!=fence or committed['step']['state']!='dispatching':raise wa.DispatchRefused('invoice claim readback differs')
        except Exception:return {'step':{'state':'outcome_unknown','failure':'claim-readback-unavailable'}}
        entered=False
        try:
            entry=self.repo.before_step_entry(operation_id,tenant_id,role,fence)
            if entry['step']['binding_hash']!=snapshot['step']['binding_hash'] or entry['step']['form']!=snapshot['step']['form']:raise wa.DispatchRefused('invoice request changed before entry')
            entered=True # IN-PROCESS fact, never recoverable from restart.
            raw=await self.adapter.invoke(request);result=validate_receipt(raw,snapshot)
        except (Exception,asyncio.CancelledError):
            try:return self.repo.step_outcome(operation_id,tenant_id,role,fence,state='outcome_unknown' if entered else 'failed_before_dispatch',failure='adapter-unknown' if entered else 'pre-entry-refused')
            except Exception:return {'step':{'state':'outcome_unknown','failure':'outcome-storage-unavailable'}}
        try:return self.repo.step_outcome(operation_id,tenant_id,role,fence,state='succeeded',result=result)
        except Exception:return {'step':{'state':'outcome_unknown','failure':'receipt-storage-unavailable'}}

    async def dispatch(self,operation_id,tenant_id):
        parent=self.repo.get(operation_id,tenant_id)
        if parent['state']!='prepared':return parent
        wa.require_dispatch_ready()
        if self.adapter.provider_account!=parent['provider_account'] or parent['environment']!='test' or parent['api_version']!=API_VERSION:raise wa.DispatchRefused('invoice adapter account differs')
        draft=await self._step(operation_id,tenant_id,'draft-invoice')
        if draft['step']['state']!='succeeded':return {'id':operation_id,'state':'outcome_unknown','step':'draft-invoice','step_state':draft['step']['state']}
        self.repo.prepare_item(operation_id,tenant_id)
        item=await self._step(operation_id,tenant_id,'invoice-item')
        if item['step']['state']!='succeeded':return {'id':operation_id,'state':'outcome_unknown','step':'invoice-item','step_state':item['step']['state']}
        try:
            wa.require_dispatch_ready()
            with self.repo.sessions() as db:
                current=db.get(wa.OperationRow,operation_id)
                if current is None or current.tenant_id!=tenant_id:raise wa.DispatchRefused('invoice final tenant differs')
                clock=CheckoutRepository(self.repo.approvals);clock._authority(db,current,clock._now(db))
                barrier=db.get(wa.CutoverRow,1)
                if barrier is None or barrier.state!='verified-active' or barrier.protocol_epoch!=2 or not barrier.verification_digest or not barrier.verified_at:raise wa.DispatchRefused('invoice final cutover lost')
            raw=await self.adapter.read_invoice(draft['step']['result']['id'])
            validate_final(raw,parent,draft['step'],item['step'])
            return self.repo.finish(operation_id,tenant_id,draft['step']['result']['id'],item['step']['result']['id'],raw)
        except (Exception,asyncio.CancelledError):
            try:return self.repo.hold_final(operation_id,tenant_id,'invoice-final-verification-unknown')
            except Exception:return {'id':operation_id,'state':'outcome_unknown','failure':'final-storage-unavailable'}

# Register the customer-fence snapshot model before standalone invoice fixtures
# call create_all. Deferred until all invoice classes exist to avoid an import cycle.
from . import cancellation as _cancellation_models  # noqa: E402,F401
