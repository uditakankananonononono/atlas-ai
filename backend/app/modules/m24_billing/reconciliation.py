"""M24 reviewed positive lookup and unsent cancellation. No absence/retry authority."""
from __future__ import annotations
import copy
import re
from datetime import datetime,timezone
from uuid import uuid4
import httpx
from sqlalchemy import JSON,String,DateTime,ForeignKey,select,update
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.auth.context import TenantContext
from app.modules.m00_approval_center.service import ApprovalRequestRow,_aware
from . import write_ahead as wa
from .checkout_dispatcher import CheckoutRepository,CheckoutAdapter,validated_result,digest,API_VERSION
from .invoice_dispatcher import InvoiceRepository,InvoiceStepRow,validate_receipt,validate_bounded_receipt

class LookupEvidenceRow(Base):
    __tablename__='m24_lookup_evidence'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    operation_id:Mapped[str]=mapped_column(String(36),ForeignKey('m24_provider_operations.id'),index=True)
    tenant_id:Mapped[str]=mapped_column(String(120))
    role:Mapped[str]=mapped_column(String(40))
    binding_hash:Mapped[str]=mapped_column(String(64))
    provider_account:Mapped[str]=mapped_column(String(200))
    environment:Mapped[str]=mapped_column(String(20))
    api_version:Mapped[str]=mapped_column(String(80))
    object_id:Mapped[str]=mapped_column(String(200))
    receipt:Mapped[dict]=mapped_column(JSON)
    evidence_digest:Mapped[str]=mapped_column(String(64))
    observed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    accepted_by:Mapped[str|None]=mapped_column(String(120),nullable=True)
    accepted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


def require_reviewer(db,op,principal):
    """HTTP authenticates principal; original M00 approved_by is designation."""
    if not isinstance(principal,TenantContext) or principal.tenant_id!=op.tenant_id or not principal.has_role('atlas-approver','atlas-admin'):raise PermissionError('M24 approver principal required')
    a=db.get(ApprovalRequestRow,op.approval_id)
    if a is None or a.user_id!=op.tenant_id or a.module_id!=24 or a.status!='approved' or wa._digest(a)!=op.request_hash:raise wa.DispatchRefused('M24 original approval binding unavailable')
    reviewer=a.approved_by
    if type(reviewer) is not str or not reviewer.strip() or reviewer!=reviewer.strip() or len(reviewer)>120 or reviewer!=principal.actor_id:
        raise PermissionError('M24 original designated approver required')
    # Expired original authority does not authorize a new effect, but accepting
    # verified already-committed evidence creates no new provider effect.
    return a


class PositiveLookupAdapter(CheckoutAdapter):
    async def retrieve(self,kind,object_id):
        prefix,path={'checkout':('cs_test_','checkout/sessions'),'draft-invoice':('in_','invoices'),'invoice-item':('ii_','invoiceitems')}[kind]
        if not isinstance(object_id,str) or not re.fullmatch(re.escape(prefix)+r'[A-Za-z0-9_]{1,180}',object_id):raise ValueError('bounded provider handle required')
        async with httpx.AsyncClient(timeout=30,transport=self.transport) as client:
            response=await client.get('https://api.stripe.com/v1/'+path+'/'+object_id,headers={'Authorization':'Bearer '+self.secret_key,'Stripe-Version':API_VERSION})
        response.raise_for_status();return response.json()


class ReconciliationRepository:
    def __init__(self,approvals):self.approvals=approvals;self.sessions=approvals._sessions;self.clock=CheckoutRepository(approvals)

    def binding(self,operation_id,tenant_id,role):
        if role=='checkout':
            snap=CheckoutRepository(self.approvals).snapshot(operation_id,tenant_id)
            return snap,snap['binding_hash']
        if role in {'draft-invoice','invoice-item'}:
            snap=InvoiceRepository(self.approvals).step(operation_id,tenant_id,role)
            return snap,snap['step']['binding_hash']
        raise ValueError('unsupported lookup role')

    async def lookup_positive(self,operation_id,tenant_id,role,object_id,adapter):
        wa.require_dispatch_ready() # Active provider access never authorized by fixture/caller metadata.
        snap,bound=self.binding(operation_id,tenant_id,role);op=snap['operation']
        if op['provider_account']!=adapter.provider_account or op['environment']!='test' or op['api_version']!=API_VERSION:raise wa.DispatchRefused('lookup adapter binding differs')
        if role=='checkout':state=op['state']
        else:state=snap['step']['state']
        if state not in {'dispatching','outcome_unknown','succeeded_late'}:raise wa.DispatchRefused('lookup requires uncertain or late operation')
        raw=await adapter.retrieve(role,object_id)
        receipt=validated_result(raw,snap) if role=='checkout' else validate_receipt(raw,snap)
        if receipt['id']!=object_id:raise wa.DispatchRefused('lookup object handle differs')
        with self.sessions.begin() as db:
            current=db.get(wa.OperationRow,operation_id)
            if current is None or current.tenant_id!=tenant_id:raise KeyError(operation_id)
            now=self.clock._now(db);ident=str(uuid4())
            evidence=digest({'operation':operation_id,'role':role,'binding':bound,'account':op['provider_account'],'environment':'test','version':API_VERSION,'object':object_id,'receipt':receipt,'observed':now.astimezone(timezone.utc).isoformat()})
            db.add(LookupEvidenceRow(id=ident,operation_id=operation_id,tenant_id=tenant_id,role=role,binding_hash=bound,
                provider_account=op['provider_account'],environment='test',api_version=API_VERSION,object_id=object_id,receipt=receipt,evidence_digest=evidence,observed_at=now))
            db.add(wa.OperationEventRow(operation_id=operation_id,event='positive-lookup-recorded',actor='m24-lookup',at=now))
        return {'evidence_id':ident,'operation_id':operation_id,'role':role,'object_id':object_id,'evidence_digest':evidence,'limitations':'positive retrieve only; no absence or retry evidence'}

    def accept_positive(self,operation_id,evidence_id,principal):
        # No provider call, no replay/retry, no new permit. Original principal checked from DB.
        with self.sessions.begin() as db:
            op=db.get(wa.OperationRow,operation_id)
            if op is None or not isinstance(principal,TenantContext) or op.tenant_id!=principal.tenant_id:raise KeyError(operation_id)
            db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==op.approval_id).values(status=ApprovalRequestRow.status));db.refresh(op)
            require_reviewer(db,op,principal)
            e=db.get(LookupEvidenceRow,evidence_id)
            if e is None or e.operation_id!=op.id or e.tenant_id!=op.tenant_id:raise KeyError(evidence_id)
            snap,bound=self.binding(op.id,op.tenant_id,e.role)
            expected=digest({'operation':op.id,'role':e.role,'binding':e.binding_hash,'account':e.provider_account,'environment':e.environment,'version':e.api_version,'object':e.object_id,'receipt':e.receipt,'observed':_aware(e.observed_at).astimezone(timezone.utc).isoformat()})
            if e.evidence_digest!=expected or e.binding_hash!=bound or e.provider_account!=op.provider_account or e.environment!=op.environment or e.api_version!=op.api_version or e.receipt.get('id')!=e.object_id:raise wa.DispatchRefused('lookup evidence binding differs')
            if e.accepted_at is not None:return {'id':op.id,'evidence_id':e.id,'state':'already-accepted'}
            if e.role=='checkout':
                if op.state not in {'dispatching','outcome_unknown','succeeded_late'}:raise wa.DispatchRefused('checkout evidence target not uncertain')
                # Receipt was validated on retrieve; bounded shape revalidated for tamper resistance.
                if set(e.receipt)!={'id','object','livemode','mode','amount_total','currency','status','payment_status'}:raise wa.DispatchRefused('checkout evidence receipt differs')
                r=e.receipt
                if r['object']!='checkout.session' or r['livemode'] is not False or r['mode']!='subscription' or type(r['amount_total']) is not int or r['amount_total']!=int(snap['form']['line_items[0][price_data][unit_amount]']) or r['currency']!='usd' or r['status'] not in {'open','complete','expired'} or r['payment_status'] not in {'paid','unpaid','no_payment_required'} or not isinstance(r['id'],str) or not r['id'].startswith('cs_test_') or len(r['id'])>200:raise wa.DispatchRefused('checkout evidence receipt binding differs')
                op.result=copy.deepcopy(e.receipt);op.state='succeeded';op.failure=None
            else:
                _,row=InvoiceRepository(self.approvals)._load(db,op.id,op.tenant_id,e.role)
                if op.state in {'closed_unknown','cancelled_before_dispatch'} or row.state not in {'dispatching','outcome_unknown','succeeded_late'}:raise wa.DispatchRefused('invoice evidence target not uncertain')
                validate_bounded_receipt(op,row,e.receipt);row.result=copy.deepcopy(e.receipt);row.state='succeeded';row.failure=None
            now=self.clock._now(db);e.accepted_by=principal.actor_id;e.accepted_at=now
            db.add(wa.OperationEventRow(operation_id=op.id,event='positive-evidence-accepted',actor=principal.actor_id,at=now))
        return {'id':operation_id,'evidence_id':evidence_id,'state':'accepted-no-provider-effect'}

    def cancel_unsent_or_close_unknown(self,operation_id,principal):
        with self.sessions.begin() as db:
            op=db.get(wa.OperationRow,operation_id)
            if op is None or not isinstance(principal,TenantContext) or op.tenant_id!=principal.tenant_id:raise KeyError(operation_id)
            db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==op.approval_id).values(status=ApprovalRequestRow.status));db.refresh(op)
            require_reviewer(db,op,principal)
            if op.state in {'succeeded','closed_unknown','cancelled_before_dispatch'}:raise wa.DispatchRefused('operation already terminal')
            steps=db.scalars(select(InvoiceStepRow).where(InvoiceStepRow.operation_id==op.id)).all()
            uncertain=op.first_attempt_at is not None or any(s.first_attempt_at is not None for s in steps)
            state='closed_unknown' if uncertain else 'cancelled_before_dispatch'
            op.state=state;op.failure='reviewed-uncertain-closure' if uncertain else 'cancelled-unsent'
            for step in steps:
                if step.state=='prepared':step.state='cancelled_before_dispatch'
            db.add(wa.OperationEventRow(operation_id=op.id,event=state,actor=principal.actor_id,at=self.clock._now(db)))
        return {'id':operation_id,'state':state,'provider_effect':'not-undone','retry_allowed':False}
