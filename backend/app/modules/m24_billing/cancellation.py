"""Reviewed immediate cancellation. DELETE key is not provider deduplication."""
from __future__ import annotations
import copy,re,asyncio
from datetime import datetime
from sqlalchemy import JSON,String,ForeignKey,select,update
from sqlalchemy.orm import Mapped,mapped_column
import httpx
from app.core.database import Base
from app.modules.m00_approval_center.service import _aware
from . import write_ahead as wa
from .checkout_dispatcher import CheckoutRepository,API_VERSION,digest
from .repository import TenantBillingRow
from .invoice_dispatcher import InvoiceStepRow

TERMS={'timing':'immediate','invoice_now':False,'prorate':False,
    'pending_invoice_items':'not deleted; may still be charged later',
    'pending_prorations':'removed under immediate cancellation with both flags false',
    'finalized_invoices':'automatic collection stops for this customer',
    'atlas_pending_drafts':'unsent invoice work held; existing draft not deleted; no stale item attachment',
    'compensation':'no deletion/refund/automatic compensation'}

class CancellationSnapshotRow(Base):
    __tablename__='m24_cancellation_snapshots'
    operation_id:Mapped[str]=mapped_column(String(36),ForeignKey('m24_provider_operations.id'),primary_key=True)
    customer_id:Mapped[str]=mapped_column(String(200))
    subscription_id:Mapped[str]=mapped_column(String(200))
    before_state:Mapped[dict]=mapped_column(JSON)
    form:Mapped[dict]=mapped_column(JSON)
    binding_hash:Mapped[str]=mapped_column(String(64))


def cancellation_snapshot(db,op):
    p=op.request
    if op.action_type!='cancel_subscription' or p.get('tenant_id')!=op.tenant_id or p.get('effect')!='cancel_subscription' or p.get('provider')!='stripe' or p.get('cancellation_terms')!=TERMS:
        raise wa.DispatchRefused('reviewed cancellation terms required; sparse legacy request refused')
    if op.environment!='test' or op.api_version!=API_VERSION:raise wa.DispatchRefused('cancellation TEST version required')
    customer=p.get('customer_id');sub=p.get('subscription_id');before=p.get('before_state')
    if not isinstance(customer,str) or not re.fullmatch(r'cus_[A-Za-z0-9_]{1,180}',customer) or not isinstance(sub,str) or not re.fullmatch(r'sub_[A-Za-z0-9_]{1,180}',sub):raise wa.DispatchRefused('cancellation ownership identifiers invalid')
    if not isinstance(before,dict) or set(before)!={'customer_id','subscription_id','status','cancel_at_period_end'} or before['customer_id']!=customer or before['subscription_id']!=sub or before['status'] not in {'active','trialing','past_due','unpaid','paused'} or type(before['cancel_at_period_end']) is not bool:raise wa.DispatchRefused('cancellation before state required')
    local=db.get(TenantBillingRow,op.tenant_id)
    if local is None or local.customer_id!=customer or local.subscription_id!=sub:raise wa.DispatchRefused('cancellation tenant ownership differs')
    # Local observed before-state drift holds; provider read immediately before entry also required.
    if local.status!=before['status'] or local.cancel_at_period_end!=before['cancel_at_period_end']:raise wa.DispatchRefused('cancellation before state drift')
    form={'invoice_now':'false','prorate':'false'}
    bound=digest({'operation':op.id,'tenant':op.tenant_id,'approval':op.approval_id,'request':op.request_hash,
        'account':op.provider_account,'environment':op.environment,'version':op.api_version,'endpoint':'/v1/subscriptions/'+sub,
        'method':'DELETE','form':form,'before':before,'terms':TERMS})
    return customer,sub,before,form,bound


class CancellationRepository(CheckoutRepository):
    def _add_snapshot(self,db,op,approval):
        db.execute(update(TenantBillingRow).where(TenantBillingRow.tenant_id==op.tenant_id).values(status=TenantBillingRow.status))
        customer,sub,before,form,bound=cancellation_snapshot(db,op)
        op.provider_key=op.id+':cancel-subscription' # local identity only, not DELETE idempotency.
        db.add(CancellationSnapshotRow(operation_id=op.id,customer_id=customer,subscription_id=sub,before_state=before,form=form,binding_hash=bound))
        # Fence all existing pending invoice parents immediately on preparation.
        # No deletion/compensation; already-entered calls may finish late and stay held.
        parents=db.scalars(select(wa.OperationRow).where(wa.OperationRow.tenant_id==op.tenant_id,
            wa.OperationRow.action_type=='issue_invoice',wa.OperationRow.state=='prepared')).all()
        for invoice in parents:
            if invoice.request.get('customer_id')!=customer:continue
            invoice.state='outcome_unknown';invoice.failure='customer-cancellation-fence'
            db.execute(update(InvoiceStepRow).where(InvoiceStepRow.operation_id==invoice.id,InvoiceStepRow.state=='prepared').values(state='cancelled_before_dispatch',failure='customer-cancellation-fence'))
            db.add(wa.OperationEventRow(operation_id=invoice.id,event='invoice-cancellation-held',actor='m24-worker',at=self.clock()))

    def _validated(self,db,op):
        row=db.get(CancellationSnapshotRow,op.id)
        if row is None:raise wa.DispatchRefused('exact cancellation snapshot required')
        customer,sub,before,form,bound=cancellation_snapshot(db,op)
        if row.customer_id!=customer or row.subscription_id!=sub or row.before_state!=before or row.form!=form or row.binding_hash!=bound or op.provider_key!=op.id+':cancel-subscription':raise wa.DispatchRefused('cancellation immutable binding differs')
        return row

    def snapshot(self,operation_id,tenant_id):
        with self.sessions() as db:
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            row=self._validated(db,op)
            return {'operation':wa._out(op),'subscription_id':row.subscription_id,'customer_id':row.customer_id,
                'before_state':copy.deepcopy(row.before_state),'form':copy.deepcopy(row.form),'binding_hash':row.binding_hash}

    def outcome(self,operation_id,tenant_id,fence,*,state,result=None,failure=None):
        if state not in {'succeeded','outcome_unknown','failed_before_dispatch'} or (state=='succeeded')!=(result is not None):raise ValueError('invalid cancellation outcome')
        with self.sessions.begin() as db:
            from app.modules.m00_approval_center.service import ApprovalRequestRow
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==op.approval_id).values(status=ApprovalRequestRow.status));db.refresh(op)
            if op.fence!=fence or op.state not in {'dispatching','outcome_unknown'}:raise wa.DispatchRefused('cancellation stale or terminal')
            if state=='failed_before_dispatch' and op.state!='dispatching':raise wa.DispatchRefused('cancellation unknown cannot become safe')
            now=self._now(db)
            if result is not None:
                # Receipt retention must not depend on current subscription status
                # after the cancellation itself or a webhook changed it.
                row=db.get(CancellationSnapshotRow,op.id)
                if row is None or row.subscription_id!=op.request.get('subscription_id') or row.customer_id!=op.request.get('customer_id'):raise wa.DispatchRefused('cancellation recorded binding unavailable')
                if set(result)!={'id','customer','status','livemode','canceled_at'} or result['id']!=row.subscription_id or result['customer']!=row.customer_id or result['status']!='canceled' or result['livemode'] is not False or type(result['canceled_at']) is not int:raise ValueError('bounded cancellation receipt differs')
                op.result=copy.deepcopy(result);op.state='succeeded_late' if op.state=='outcome_unknown' or _aware(op.lease_until)<=now else 'succeeded'
            else:op.state=state
            op.failure=failure;db.add(wa.OperationEventRow(operation_id=op.id,event='cancel:'+op.state,actor='m24-worker',at=now))
        return self.get(operation_id,tenant_id)


class CancellationAdapter:
    def __init__(self,secret_key,provider_account,transport=None):
        if not isinstance(secret_key,str) or not secret_key.startswith('sk_test_'):raise ValueError('TEST key required')
        wa._text(provider_account,'provider_account',200);self.key=secret_key;self.provider_account=provider_account;self.transport=transport
    def validate(self,snap):
        op=snap['operation']
        if op['provider_account']!=self.provider_account or op['environment']!='test' or op['api_version']!=API_VERSION:raise wa.DispatchRefused('cancellation adapter binding differs')
        return httpx.Request('DELETE','https://api.stripe.com/v1/subscriptions/'+snap['subscription_id'],data=snap['form'],
            headers={'Authorization':'Bearer '+self.key,'Stripe-Version':API_VERSION}) # Deliberately NO ineffective DELETE key header.
    async def retrieve(self,snap):
        async with httpx.AsyncClient(transport=self.transport,timeout=30) as client:r=await client.get('https://api.stripe.com/v1/subscriptions/'+snap['subscription_id'],headers={'Authorization':'Bearer '+self.key,'Stripe-Version':API_VERSION})
        r.raise_for_status();return r.json()
    async def invoke(self,request):
        async with httpx.AsyncClient(transport=self.transport,timeout=30) as client:r=await client.send(request)
        r.raise_for_status();return r.json()


def validate_before(raw,snap):
    before=snap['before_state']
    if not isinstance(raw,dict) or raw.get('object')!='subscription' or raw.get('id')!=snap['subscription_id'] or raw.get('customer')!=snap['customer_id'] or raw.get('livemode') is not False or raw.get('status')!=before['status'] or raw.get('cancel_at_period_end') is not before['cancel_at_period_end']:raise wa.DispatchRefused('provider subscription before state differs')
    if raw.get('metadata',{}).get('atlas_tenant_id')!=snap['operation']['tenant_id']:raise wa.DispatchRefused('provider subscription tenant binding differs')


class CancellationDispatcher:
    def __init__(self,repo,adapter):self.repo=repo;self.adapter=adapter
    async def dispatch(self,operation_id,tenant_id):
        initial=self.repo.get(operation_id,tenant_id)
        if initial['state']!='prepared':return initial
        wa.require_dispatch_ready();snap=self.repo.snapshot(operation_id,tenant_id);request=self.adapter.validate(snap)
        # Read-only ownership snapshot before mutation reservation; GET is not effect absence evidence.
        validate_before(await self.adapter.retrieve(snap),snap)
        try:fence=self.repo.claim(operation_id,tenant_id,protocol_epoch=2)
        except wa.DispatchRefused:return self.repo.get(operation_id,tenant_id)
        except Exception:return {'id':operation_id,'state':'outcome_unknown','failure':'cancel-claim-unconfirmed'}
        try:
            committed=self.repo.get(operation_id,tenant_id)
            if committed['fence']!=fence or committed['state']!='dispatching':raise wa.DispatchRefused('cancellation claim readback differs')
        except Exception:return {'id':operation_id,'state':'outcome_unknown','failure':'cancel-readback-unavailable'}
        entered=False
        try:
            entry=self.repo.before_entry(operation_id,tenant_id,fence)
            if entry['binding_hash']!=snap['binding_hash']:raise wa.DispatchRefused('cancellation changed before entry')
            # Second GET can fail/timeout but never mutates; in-process structural safe path only.
            validate_before(await self.adapter.retrieve(snap),snap)
            self.repo.before_entry(operation_id,tenant_id,fence)
            entered=True # in-process only; restart after attempt commit cannot trust it
            raw=await self.adapter.invoke(request)
            if not isinstance(raw,dict) or raw.get('object')!='subscription' or raw.get('id')!=snap['subscription_id'] or raw.get('customer')!=snap['customer_id'] or raw.get('status')!='canceled' or raw.get('livemode') is not False or type(raw.get('canceled_at')) is not int:raise ValueError('cancellation response differs')
            result={k:raw[k] for k in ('id','customer','status','livemode','canceled_at')}
        except (Exception,asyncio.CancelledError):
            try:return self.repo.outcome(operation_id,tenant_id,fence,state='outcome_unknown' if entered else 'failed_before_dispatch',failure='cancel-unknown' if entered else 'cancel-pre-entry-refused')
            except Exception:return {'id':operation_id,'state':'outcome_unknown','failure':'cancel-outcome-storage-unavailable'}
        try:return self.repo.outcome(operation_id,tenant_id,fence,state='succeeded',result=result)
        except Exception:return {'id':operation_id,'state':'outcome_unknown','failure':'cancel-receipt-unavailable'}
