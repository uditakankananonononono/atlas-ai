"""Exact checkout write-ahead dispatcher. Production activation remains unavailable.

Tests may replace require_dispatch_ready; that is not operational cutover evidence.
Adapter entry is an IN-PROCESS marker only. A restarted dispatching row is unknown.
"""
from __future__ import annotations
import asyncio
import copy
import hashlib
import json
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from uuid import uuid4
from urllib.parse import urlparse
import httpx
from sqlalchemy import JSON,String,ForeignKey,select,update,func,exists
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.modules.m00_approval_center.service import ApprovalRequestRow,ApprovalEffectRow,_aware
from app.modules.m00_approval_center.impact import ApprovalReviewStateRow,validate_bound_snapshot
from . import write_ahead as wa

API_VERSION='2026-09-30.endive'
ADAPTER_VERSION='atlas-checkout-v2'
ENDPOINT='https://api.stripe.com/v1/checkout/sessions'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class CheckoutSnapshotRow(Base):
    __tablename__='m24_checkout_snapshots'
    operation_id:Mapped[str]=mapped_column(String(36),ForeignKey('m24_provider_operations.id'),primary_key=True)
    form:Mapped[dict]=mapped_column(JSON)
    form_hash:Mapped[str]=mapped_column(String(64))
    binding_hash:Mapped[str]=mapped_column(String(64))
    adapter_version:Mapped[str]=mapped_column(String(80))


def form_for(op):
    from .service import PLANS
    from .precommit import verify_commitment_preview
    p=op.request
    if op.action_type!='create_subscription_checkout' or p.get('tenant_id')!=op.tenant_id or p.get('provider')!='stripe' or p.get('mode')!='subscription':
        raise wa.DispatchRefused('checkout authority binding invalid')
    plan=PLANS.get(p.get('plan',{}).get('id'))
    if plan is None or p.get('plan')!=plan.model_dump() or plan.monthly_price_usd<=0:
        raise wa.DispatchRefused('checkout catalog differs from approval')
    for name in ('success_url','cancel_url'):
        u=p.get(name)
        if not isinstance(u,str) or len(u)>2048 or urlparse(u).scheme!='https' or not urlparse(u).netloc or urlparse(u).username:
            raise wa.DispatchRefused('checkout requires bounded HTTPS return URLs')
    if p.get('commitment_preview'):
        preview=verify_commitment_preview(p['commitment_preview'],plan.model_dump(),checkout_supported=True)
        if preview['preview_sha256']!=p.get('commitment_preview_sha256') or int(Decimal(preview['exact_charge'])*100)!=p.get('expected_charge_cents'):
            raise wa.DispatchRefused('checkout reviewed charge differs')
    return {'mode':'subscription','success_url':p['success_url'],'cancel_url':p['cancel_url'],
        'client_reference_id':op.tenant_id,'metadata[atlas_approval_id]':op.approval_id,
        'metadata[atlas_operation_id]':op.id,'metadata[atlas_operation_step]':'checkout',
        'metadata[tenant_id]':op.tenant_id,'metadata[plan_id]':plan.id,
        'subscription_data[metadata][atlas_tenant_id]':op.tenant_id,'subscription_data[metadata][plan_id]':plan.id,
        'line_items[0][price_data][currency]':'usd','line_items[0][price_data][product_data][name]':f'Atlas {plan.name}',
        'line_items[0][price_data][unit_amount]':str(int(Decimal(str(plan.monthly_price_usd))*100)),
        'line_items[0][price_data][recurring][interval]':'month','line_items[0][quantity]':'1'}


def binding_for(op,form):
    return digest({'operation':op.id,'tenant':op.tenant_id,'approval':op.approval_id,'request':op.request_hash,
        'account':op.provider_account,'environment':op.environment,'api_version':op.api_version,
        'key':op.provider_key,'adapter':ADAPTER_VERSION,'endpoint':ENDPOINT,'form':form})


class CheckoutRepository(wa.OperationRepository):
    def _add_snapshot(self,db,op,approval):
        if op.api_version!=API_VERSION:raise wa.DispatchRefused('checkout API version not pinned')
        form=form_for(op)
        # Server-operation step key, never approval_id or attempt-derived. Committed with intent.
        op.provider_key=op.id+':checkout'
        db.add(CheckoutSnapshotRow(operation_id=op.id,form=form,form_hash=digest(form),
            binding_hash=binding_for(op,form),adapter_version=ADAPTER_VERSION))

    def prepare(self,*args,**kwargs):
        if kwargs.get('provider_key') is not None:raise wa.DispatchRefused('checkout step key is server assigned')
        result=super().prepare(*args,**kwargs)
        # Plain slice1 intents do not have exact forms and cannot be silently upgraded.
        self.snapshot(result['id'],result['tenant_id'])
        return result

    def _validated(self,db,op):
        snap=db.get(CheckoutSnapshotRow,op.id)
        if snap is None:raise wa.DispatchRefused('checkout immutable snapshot required')
        if op.environment!='test' or op.api_version!=API_VERSION or op.provider_key!=op.id+':checkout' or op.protocol_epoch!=2:
            raise wa.DispatchRefused('checkout immutable adapter binding differs')
        if snap.adapter_version!=ADAPTER_VERSION or snap.form_hash!=digest(snap.form) or snap.binding_hash!=binding_for(op,snap.form) or snap.form!=form_for(op):
            raise wa.DispatchRefused('checkout immutable form differs')
        return snap

    def snapshot(self,operation_id,tenant_id):
        with self.sessions() as db:
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            snap=self._validated(db,op)
            return {'operation':wa._out(op),'form':copy.deepcopy(snap.form),'form_hash':snap.form_hash,
                'binding_hash':snap.binding_hash,'adapter_version':snap.adapter_version}

    def _now(self,db):
        # DB UTC clock for claims/leases, not a caller's wall-clock assertion.
        value=db.scalar(select(func.current_timestamp()))
        if isinstance(value,str):value=datetime.fromisoformat(value)
        return _aware(value)

    def _authority(self,db,op,now):
        a=db.get(ApprovalRequestRow,op.approval_id)
        if a is None or a.status!='approved' or a.module_id!=24 or a.user_id!=op.tenant_id or wa._digest(a)!=op.request_hash or a.payload!=op.request:
            raise wa.DispatchRefused('checkout authority changed')
        if a.expires_at and _aware(a.expires_at)<=now:raise wa.DispatchRefused('checkout approval elapsed')
        validate_bound_snapshot(wa._view(a),db.get(ApprovalReviewStateRow,a.id))
        permit=db.scalar(select(ApprovalEffectRow).where(ApprovalEffectRow.approval_id==a.id))
        if permit is None or permit.effect_id!=wa._permit_key(op.tenant_id,a.id) or permit.request_hash!=op.request_hash:
            raise wa.DispatchRefused('checkout permit differs')
        cutoff=_aware(a.expires_at) if a.expires_at else None
        preview=op.request.get('commitment_preview',{})
        if preview.get('cancellation_deadline'):
            deadline=datetime.fromisoformat(preview['cancellation_deadline'])
            if deadline.tzinfo is None or deadline<=now:raise wa.DispatchRefused('checkout commitment elapsed')
            cutoff=min(cutoff,deadline) if cutoff else deadline
        return cutoff

    def claim(self,operation_id,tenant_id,*,protocol_epoch,lease_seconds=60):
        if type(protocol_epoch) is not int or protocol_epoch!=2:raise wa.DispatchRefused('old protocol refused')
        if type(lease_seconds) is not int or not 1<=lease_seconds<=60:raise ValueError('checkout lease must be 1-60 seconds')
        wa.require_dispatch_ready() # No activation implementation, even forged rows refuse in production.
        fence=str(uuid4())
        with self.sessions.begin() as db:
            # Lock approval then operation, matching preparation lock order.
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==op.approval_id).values(status=ApprovalRequestRow.status))
            db.refresh(op)
            self._validated(db,op);now=self._now(db);cutoff=self._authority(db,op,now)
            barrier=db.get(wa.CutoverRow,1)
            if barrier is None or barrier.protocol_epoch!=2 or barrier.state!='verified-active' or not barrier.verification_digest or not barrier.verified_at:
                raise wa.DispatchRefused('checkout cutover locked')
            # Never refresh first-attempt age. No unknown/dispatching takeover, even a young key.
            first=_aware(op.first_attempt_at) if op.first_attempt_at else now
            bound=first+timedelta(hours=12)
            if cutoff:bound=min(bound,cutoff)
            if op.dispatch_not_after:bound=min(bound,_aware(op.dispatch_not_after))
            if now>=bound:raise wa.DispatchRefused('checkout dispatch bound elapsed')
            changed=db.execute(update(wa.OperationRow).where(wa.OperationRow.id==op.id,wa.OperationRow.tenant_id==tenant_id,
                wa.OperationRow.state=='prepared',wa.OperationRow.fence.is_(None),
                exists(select(wa.CutoverRow.id).where(wa.CutoverRow.id==1,wa.CutoverRow.protocol_epoch==2,
                    wa.CutoverRow.state=='verified-active',wa.CutoverRow.verification_digest.is_not(None),wa.CutoverRow.verified_at.is_not(None)))).values(state='dispatching',fence=fence,
                    lease_until=now+timedelta(seconds=lease_seconds),first_attempt_at=first,dispatch_not_after=bound))
            if changed.rowcount!=1:raise wa.DispatchRefused('checkout not claimable; reconcile existing attempt')
            db.add(wa.AttemptRow(id=str(uuid4()),operation_id=op.id,fence=fence,request_hash=op.request_hash,started_at=now))
            db.add(wa.OperationEventRow(operation_id=op.id,event='dispatch-reserved',actor='m24-worker',at=now))
        return fence

    def before_entry(self,operation_id,tenant_id,fence):
        wa.require_dispatch_ready()
        with self.sessions() as db:
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            now=self._now(db);self._validated(db,op);self._authority(db,op,now)
            b=db.get(wa.CutoverRow,1)
            if b is None or b.state!='verified-active' or b.protocol_epoch!=2 or not b.verification_digest or not b.verified_at:
                raise wa.DispatchRefused('checkout cutover lost')
            if op.state!='dispatching' or op.fence!=fence or _aware(op.lease_until)<=now or _aware(op.dispatch_not_after)<=now:
                raise wa.DispatchRefused('checkout dispatch fence or deadline lost')
            return self.snapshot(operation_id,tenant_id)

    def outcome(self,operation_id,tenant_id,fence,*,state,result=None,failure=None):
        if state not in {'succeeded','outcome_unknown','failed_before_dispatch'} or (state=='succeeded')!=(result is not None):raise ValueError('invalid outcome')
        with self.sessions.begin() as db:
            db.execute(update(wa.OperationRow).where(wa.OperationRow.id==operation_id,wa.OperationRow.tenant_id==tenant_id).values(state=wa.OperationRow.state))
            op=db.get(wa.OperationRow,operation_id)
            if op is None or op.tenant_id!=tenant_id:raise KeyError(operation_id)
            if op.fence!=fence:raise wa.DispatchRefused('checkout stale fence')
            if op.state not in {'dispatching','outcome_unknown'}:raise wa.DispatchRefused('checkout outcome already held or recorded')
            now=self._now(db)
            if result is not None:
                self._validated(db,op)
                # Only bounded validated identifiers, never raw Stripe errors/URLs/secrets.
                if set(result)!={'id','object','livemode','mode','amount_total','currency','status','payment_status'} or not isinstance(result.get('id'),str) or not result['id'].startswith('cs_test_') or len(result['id'])>255 or result['object']!='checkout.session' or result['livemode'] is not False or result['mode']!='subscription' or type(result['amount_total']) is not int or result['amount_total']!=int(self._validated(db,op).form['line_items[0][price_data][unit_amount]']) or result['currency']!='usd' or result['status'] not in {'open','complete','expired'} or result['payment_status'] not in {'paid','unpaid','no_payment_required'}:
                    raise ValueError('bounded checkout receipt invalid')
                op.result=copy.deepcopy(result)
                op.state='succeeded_late' if op.state=='outcome_unknown' or _aware(op.lease_until)<=now else 'succeeded'
            else:op.state=state
            op.failure=failure
            db.add(wa.OperationEventRow(operation_id=op.id,event=op.state,actor='m24-worker',at=now))
        return self.get(operation_id,tenant_id)

    def expire_uncertain(self,operation_id,tenant_id):
        """Restart/lease expiry is uncertainty, NOT durable proof of no adapter entry."""
        with self.sessions.begin() as db:
            now=self._now(db)
            db.execute(update(wa.OperationRow).where(wa.OperationRow.id==operation_id,wa.OperationRow.tenant_id==tenant_id,
                wa.OperationRow.state=='dispatching',wa.OperationRow.lease_until<=now).values(state='outcome_unknown',failure='lease-expired'))
        return self.get(operation_id,tenant_id)


class CheckoutAdapter:
    """TEST-only pinned request adapter. No readiness check or activation claim."""
    def __init__(self,secret_key,provider_account,transport=None):
        if not isinstance(secret_key,str) or not secret_key.startswith('sk_test_'):raise ValueError('TEST key required')
        wa._text(provider_account,'provider_account',200)
        self.secret_key=secret_key;self.provider_account=provider_account;self.transport=transport

    def validate(self,snapshot):
        op=snapshot['operation']
        if op['environment']!='test' or op['provider_account']!=self.provider_account or op['api_version']!=API_VERSION or snapshot['adapter_version']!=ADAPTER_VERSION:
            raise wa.DispatchRefused('checkout adapter binding differs')
        if digest(snapshot['form'])!=snapshot['form_hash']:raise wa.DispatchRefused('checkout form serialization differs')
        # Serialization completed outside adapter entry; only exact stored form will be sent.
        return httpx.Request('POST',ENDPOINT,headers={'Authorization':'Bearer '+self.secret_key,
            'Idempotency-Key':op['provider_key'],'Stripe-Version':API_VERSION},data=snapshot['form'])

    async def invoke(self,request):
        async with httpx.AsyncClient(timeout=30,transport=self.transport) as client:
            response=await client.send(request)
        response.raise_for_status()
        return response.json()


def validated_result(raw,snapshot):
    op=snapshot['operation'];form=snapshot['form']
    if not isinstance(raw,dict) or raw.get('object')!='checkout.session' or raw.get('livemode') is not False or raw.get('mode')!='subscription' or raw.get('client_reference_id')!=op['tenant_id']:
        raise ValueError('checkout response binding invalid')
    md=raw.get('metadata',{})
    if not isinstance(md,dict) or any(md.get(k)!=v for k,v in {'atlas_operation_id':op['id'],'atlas_operation_step':'checkout','atlas_approval_id':op['approval_id'],'tenant_id':op['tenant_id'],'plan_id':op['request']['plan']['id']}.items()):
        raise ValueError('checkout response metadata invalid')
    ident=raw.get('id')
    if not isinstance(ident,str) or not ident.startswith('cs_test_') or len(ident)>255:raise ValueError('checkout response identifier invalid')
    if type(raw.get('amount_total')) is not int or raw['amount_total']!=int(form['line_items[0][price_data][unit_amount]']) or raw.get('currency')!='usd':
        raise ValueError('checkout response charge differs')
    if raw.get('status') not in {'open','complete','expired'} or raw.get('payment_status') not in {'paid','unpaid','no_payment_required'}:raise ValueError('checkout response status invalid')
    return {k:raw[k] for k in ('id','object','livemode','mode','amount_total','currency','status','payment_status')}


class CheckoutDispatcher:
    def __init__(self,repository,adapter):self.repo=repository;self.adapter=adapter

    async def dispatch(self,operation_id,tenant_id):
        initial=self.repo.get(operation_id,tenant_id)
        if initial['state']!='prepared':return initial # persisted result/uncertainty, never network retry
        wa.require_dispatch_ready()
        snapshot=self.repo.snapshot(operation_id,tenant_id)
        request=self.adapter.validate(snapshot) # structural serialization outside adapter invocation
        try:fence=self.repo.claim(operation_id,tenant_id,protocol_epoch=2)
        except wa.DispatchRefused:return self.repo.get(operation_id,tenant_id)
        except Exception:
            return {'id':operation_id,'tenant_id':tenant_id,'state':'outcome_unknown','result':None,'failure':'claim-commit-unconfirmed'}
        # Confirm committed exact attempt. Ambiguous claim acknowledgment never reaches adapter.
        try:committed=self.repo.get(operation_id,tenant_id)
        except Exception:
            return {'id':operation_id,'tenant_id':tenant_id,'state':'outcome_unknown','result':None,'failure':'claim-readback-unavailable'}
        if committed['fence']!=fence or committed['state']!='dispatching':raise wa.DispatchRefused('checkout claim readback differs')
        entered=False
        try:
            entry_snapshot=self.repo.before_entry(operation_id,tenant_id,fence)
            if entry_snapshot['binding_hash']!=snapshot['binding_hash'] or entry_snapshot['form']!=snapshot['form']:
                raise wa.DispatchRefused('checkout form changed before entry')
            # This fact is in-process only; a restart cannot trust it.
            entered=True
            raw=await self.adapter.invoke(request)
            result=validated_result(raw,snapshot)
        except (Exception,asyncio.CancelledError):
            state='outcome_unknown' if entered else 'failed_before_dispatch'
            try:return self.repo.outcome(operation_id,tenant_id,fence,state=state,failure='adapter-outcome-unknown' if entered else 'pre-entry-refused')
            except Exception:return {'id':operation_id,'tenant_id':tenant_id,'state':'outcome_unknown','result':None,'failure':'outcome-storage-unavailable'}
        try:return self.repo.outcome(operation_id,tenant_id,fence,state='succeeded',result=result)
        except Exception:
            return {'id':operation_id,'tenant_id':tenant_id,'state':'outcome_unknown','result':None,'failure':'receipt-storage-unavailable'}
