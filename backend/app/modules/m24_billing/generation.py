"""Inactive optional billing generation. No model implementation/default wiring."""
from __future__ import annotations
import asyncio,copy
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from sqlalchemy import JSON,String,Integer,DateTime,ForeignKey,CheckConstraint,UniqueConstraint,select,update,exists
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.modules.m00_approval_center.service import ApprovalRequestRow,ApprovalEffectRow,_aware
from . import write_ahead as wa
from .checkout_dispatcher import CheckoutRepository,digest

ACTION='generate_billing_description'

class BudgetRow(Base):
    __tablename__='m24_generation_budgets'
    __table_args__=(CheckConstraint('available_input >= 0 AND available_output >= 0 AND available_micro_usd >= 0 AND available_attempts >= 0'),)
    id:Mapped[str]=mapped_column(String(120),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(120))
    account:Mapped[str]=mapped_column(String(200))
    price_schedule:Mapped[dict]=mapped_column(JSON)
    available_input:Mapped[int]=mapped_column(Integer)
    available_output:Mapped[int]=mapped_column(Integer)
    available_micro_usd:Mapped[int]=mapped_column(Integer)
    available_attempts:Mapped[int]=mapped_column(Integer)

class GenerationRow(Base):
    __tablename__='m24_generations'
    __table_args__=(UniqueConstraint('approval_id'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    approval_id:Mapped[str]=mapped_column(String(36))
    tenant_id:Mapped[str]=mapped_column(String(120))
    budget_id:Mapped[str]=mapped_column(String(120),ForeignKey('m24_generation_budgets.id'))
    request_hash:Mapped[str]=mapped_column(String(64))
    request:Mapped[dict]=mapped_column(JSON)
    binding_hash:Mapped[str]=mapped_column(String(64))
    state:Mapped[str]=mapped_column(String(40))
    fence:Mapped[str|None]=mapped_column(String(36),nullable=True)
    lease_until:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    output:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    failure:Mapped[str|None]=mapped_column(String(80),nullable=True)

class BudgetAttemptRow(Base):
    __tablename__='m24_generation_budget_attempts'
    __table_args__=(CheckConstraint('reserved_input >= 0 AND reserved_output >= 0 AND reserved_micro_usd >= 0'),)
    generation_id:Mapped[str]=mapped_column(String(36),ForeignKey('m24_generations.id'),primary_key=True)
    state:Mapped[str]=mapped_column(String(30))
    reserved_input:Mapped[int]=mapped_column(Integer)
    reserved_output:Mapped[int]=mapped_column(Integer)
    reserved_micro_usd:Mapped[int]=mapped_column(Integer)
    actual_input:Mapped[int|None]=mapped_column(Integer,nullable=True)
    actual_output:Mapped[int|None]=mapped_column(Integer,nullable=True)
    actual_micro_usd:Mapped[int|None]=mapped_column(Integer,nullable=True)

class GenerationEventRow(Base):
    __tablename__='m24_generation_events'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    generation_id:Mapped[str]=mapped_column(String(36))
    event:Mapped[str]=mapped_column(String(80))
    at:Mapped[datetime]=mapped_column(DateTime(timezone=True))

def integer(value,name,ceiling=1000000000):
    if type(value) is not int or not 0<=value<=ceiling:raise wa.DispatchRefused(name+' must be bounded nonnegative integer')
    return value

def validate_request(payload,tenant,budget):
    keys={'tenant_id','budget_id','account','model','model_version','inputs','options','price_schedule','max_input_tokens','max_output_tokens','max_micro_usd','privacy','regenerates'}
    if set(payload)!=keys or payload['tenant_id']!=tenant or payload['budget_id']!=budget.id or payload['account']!=budget.account or payload['privacy']!='private-no-delivery':raise wa.DispatchRefused('generation authority binding differs')
    for field in ('account','model','model_version'):wa._text(payload[field],field,200)
    if not isinstance(payload['inputs'],str) or not 1<=len(payload['inputs'])<=32000 or not isinstance(payload['options'],dict) or len(str(payload['options']))>8000:raise wa.DispatchRefused('bounded immutable generation inputs required')
    price=payload['price_schedule']
    if not isinstance(price,dict) or set(price)!={'id','currency','input_micro_usd_per_token','output_micro_usd_per_token'} or price!=budget.price_schedule or price['currency']!='USD':raise wa.DispatchRefused('pinned USD price schedule required')
    wa._text(price['id'],'price_schedule_id',120)
    input_rate=integer(price['input_micro_usd_per_token'],'input price');output_rate=integer(price['output_micro_usd_per_token'],'output price')
    inp=integer(payload['max_input_tokens'],'input tokens');out=integer(payload['max_output_tokens'],'output tokens');cost=integer(payload['max_micro_usd'],'maximum charge')
    if inp<1 or out<1 or inp*input_rate+out*output_rate!=cost:raise wa.DispatchRefused('trustworthy exact maximum charge required')
    if payload['regenerates'] is not None:wa._text(payload['regenerates'],'regenerates',36)
    return inp,out,cost

def view(row):return {key:copy.deepcopy(getattr(row,key)) for key in ('id','approval_id','tenant_id','budget_id','request_hash','request','binding_hash','state','fence','output','failure')}

class GenerationRepository:
    def __init__(self,approvals):self.approvals=approvals;self.sessions=approvals._sessions;self.clock=CheckoutRepository(approvals)
    def _validate(self,db,row,*,authority=True):
        budget=db.get(BudgetRow,row.budget_id)
        if budget is None or budget.tenant_id!=row.tenant_id:raise wa.DispatchRefused('generation budget ownership differs')
        inp,out,cost=validate_request(row.request,row.tenant_id,budget)
        attempt=db.get(BudgetAttemptRow,row.id)
        if attempt is None or (attempt.reserved_input,attempt.reserved_output,attempt.reserved_micro_usd)!=(inp,out,cost):raise wa.DispatchRefused('immutable generation reservation differs')
        if row.binding_hash!=digest({'id':row.id,'approval':row.approval_id,'request_hash':row.request_hash,'request':row.request}):raise wa.DispatchRefused('generation immutable binding differs')
        a=db.get(ApprovalRequestRow,row.approval_id)
        if a is None or a.module_id!=24 or a.user_id!=row.tenant_id or a.action_type!=ACTION or wa._digest(a)!=row.request_hash or a.payload!=row.request:raise wa.DispatchRefused('generation original approval differs')
        if authority:
            from app.modules.m00_approval_center.impact import ApprovalReviewStateRow,validate_bound_snapshot
            now=self.clock._now(db)
            if a.status!='approved' or a.expires_at and _aware(a.expires_at)<=now:raise wa.DispatchRefused('generation authority elapsed or revoked')
            validate_bound_snapshot(wa._view(a),db.get(ApprovalReviewStateRow,a.id))
        permit=db.scalar(select(ApprovalEffectRow).where(ApprovalEffectRow.approval_id==a.id))
        if permit is None or permit.effect_id!='m24-generation:'+row.id or permit.request_hash!=row.request_hash:raise wa.DispatchRefused('generation permit differs')
        return budget
    def prepare(self,approval_id,tenant_id,*,actor='m24-generator',hook=None):
        hook=hook or (lambda point:None)
        with self.sessions.begin() as db:
            locked=db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==approval_id,ApprovalRequestRow.user_id==tenant_id,ApprovalRequestRow.module_id==24).values(status=ApprovalRequestRow.status))
            if locked.rowcount!=1:raise KeyError(approval_id)
            approval=db.get(ApprovalRequestRow,approval_id)
            prior=db.scalar(select(GenerationRow).where(GenerationRow.approval_id==approval_id))
            if prior:self._validate(db,prior,authority=False);return view(prior)
            if approval.action_type!=ACTION:raise wa.DispatchRefused('generation-specific authority required')
            p=copy.deepcopy(approval.payload);budget=db.get(BudgetRow,p.get('budget_id'))
            if budget is None or budget.tenant_id!=tenant_id:raise wa.DispatchRefused('generation budget ownership unavailable')
            inp,out,cost=validate_request(p,tenant_id,budget)
            if p['regenerates'] is not None:
                old=db.get(GenerationRow,p['regenerates'])
                if old is None or old.tenant_id!=tenant_id or old.budget_id!=budget.id or old.state not in {'dispatching','outcome_unknown','succeeded_late'}:raise wa.DispatchRefused('explicit regeneration target unavailable')
            ident=str(uuid4());self.approvals.consume_effect(approval_id,module_id=24,action_type=ACTION,payload=p,user_id=tenant_id,effect_id='m24-generation:'+ident,actor=actor,_session=db)
            changed=db.execute(update(BudgetRow).where(BudgetRow.id==budget.id,BudgetRow.tenant_id==tenant_id,BudgetRow.account==p['account'],
                BudgetRow.available_input>=inp,BudgetRow.available_output>=out,BudgetRow.available_micro_usd>=cost,BudgetRow.available_attempts>=1).values(
                available_input=BudgetRow.available_input-inp,available_output=BudgetRow.available_output-out,
                available_micro_usd=BudgetRow.available_micro_usd-cost,available_attempts=BudgetRow.available_attempts-1))
            if changed.rowcount!=1:raise wa.DispatchRefused('generation budget exhausted')
            hook('after-balance-update')
            row=GenerationRow(id=ident,approval_id=approval_id,tenant_id=tenant_id,budget_id=budget.id,request_hash=wa._digest(approval),request=p,
                binding_hash=digest({'id':ident,'approval':approval_id,'request_hash':wa._digest(approval),'request':p}),state='prepared',created_at=self.clock._now(db))
            db.add(row);db.flush();db.add(BudgetAttemptRow(generation_id=ident,state='reserved',reserved_input=inp,reserved_output=out,reserved_micro_usd=cost))
            db.add(GenerationEventRow(generation_id=ident,event='prepared-reserved',at=self.clock._now(db)));db.flush();hook('before-reservation-commit');result=view(row)
        hook('after-reservation-commit');return result
    def get(self,ident,tenant):
        with self.sessions() as db:
            row=db.get(GenerationRow,ident)
            if row is None or row.tenant_id!=tenant:raise KeyError(ident)
            return view(row)
    def claim(self,ident,tenant):
        wa.require_dispatch_ready();fence=str(uuid4())
        with self.sessions.begin() as db:
            row=db.get(GenerationRow,ident)
            if row is None or row.tenant_id!=tenant:raise KeyError(ident)
            db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==row.approval_id).values(status=ApprovalRequestRow.status));db.refresh(row)
            self._validate(db,row);now=self.clock._now(db)
            barrier=exists(select(wa.CutoverRow.id).where(wa.CutoverRow.id==1,wa.CutoverRow.protocol_epoch==2,wa.CutoverRow.state=='verified-active',wa.CutoverRow.verification_digest.is_not(None),wa.CutoverRow.verified_at.is_not(None)))
            changed=db.execute(update(GenerationRow).where(GenerationRow.id==ident,GenerationRow.state=='prepared',GenerationRow.fence.is_(None),barrier).values(state='dispatching',fence=fence,lease_until=now+timedelta(seconds=60)))
            if changed.rowcount!=1:raise wa.DispatchRefused('generation held or cutover locked')
            attempt=db.get(BudgetAttemptRow,ident)
            if attempt is None or attempt.state!='reserved':raise wa.DispatchRefused('generation reservation unavailable')
            attempt.state='charged-pending';db.add(GenerationEventRow(generation_id=ident,event='attempt-committed',at=now))
        return fence
    def before_entry(self,ident,tenant,fence):
        wa.require_dispatch_ready()
        with self.sessions() as db:
            row=db.get(GenerationRow,ident)
            if row is None or row.tenant_id!=tenant:raise KeyError(ident)
            self._validate(db,row)
            barrier=db.get(wa.CutoverRow,1)
            if barrier is None or barrier.protocol_epoch!=2 or barrier.state!='verified-active' or not barrier.verification_digest or not barrier.verified_at:raise wa.DispatchRefused('generation cutover lost')
            if row.state!='dispatching' or row.fence!=fence or _aware(row.lease_until)<=self.clock._now(db):raise wa.DispatchRefused('generation fence or lease lost')
            attempt=db.get(BudgetAttemptRow,ident)
            if attempt is None or attempt.state!='charged-pending':raise wa.DispatchRefused('generation pending charge missing')
            return view(row)
    def unknown(self,ident,tenant,fence):
        with self.sessions.begin() as db:
            row=db.get(GenerationRow,ident)
            if row is None or row.tenant_id!=tenant:raise KeyError(ident)
            if row.fence!=fence or row.state!='dispatching':raise wa.DispatchRefused('generation stale outcome')
            row.state='outcome_unknown';row.failure='generation-unknown';db.add(GenerationEventRow(generation_id=ident,event='unknown-no-refund',at=self.clock._now(db)))
        return self.get(ident,tenant)
    def settle(self,ident,tenant,fence,raw,*,hook=None):
        hook=hook or (lambda point:None)
        with self.sessions.begin() as db:
            row=db.get(GenerationRow,ident)
            if row is None or row.tenant_id!=tenant:raise KeyError(ident)
            db.execute(update(GenerationRow).where(GenerationRow.id==ident).values(state=GenerationRow.state));db.refresh(row)
            if row.fence!=fence or row.state not in {'dispatching','outcome_unknown'} or row.output is not None:raise wa.DispatchRefused('generation stale or terminal settlement')
            budget=self._validate(db,row,authority=False);p=row.request
            if not isinstance(raw,dict) or set(raw)!={'text','input_tokens','output_tokens','micro_usd','account','model','model_version','price_schedule_id','usage_verified'}:raise wa.DispatchRefused('bounded verified model response required')
            if raw['account']!=p['account'] or raw['model']!=p['model'] or raw['model_version']!=p['model_version'] or raw['price_schedule_id']!=p['price_schedule']['id'] or raw['usage_verified'] is not True:raise wa.DispatchRefused('model response authority differs')
            if not isinstance(raw['text'],str) or not raw['text'].strip() or len(raw['text'])>1000:raise wa.DispatchRefused('bounded billing description required')
            inp=integer(raw['input_tokens'],'actual input');out=integer(raw['output_tokens'],'actual output');cost=integer(raw['micro_usd'],'actual charge')
            if inp>p['max_input_tokens'] or out>p['max_output_tokens'] or cost>p['max_micro_usd'] or cost!=inp*p['price_schedule']['input_micro_usd_per_token']+out*p['price_schedule']['output_micro_usd_per_token']:raise wa.DispatchRefused('model usage exceeds or differs from reserve')
            attempt=db.get(BudgetAttemptRow,ident)
            if attempt is None or attempt.state!='charged-pending':raise wa.DispatchRefused('generation charge not pending')
            db.execute(update(BudgetRow).where(BudgetRow.id==budget.id).values(available_input=BudgetRow.available_input+attempt.reserved_input-inp,
                available_output=BudgetRow.available_output+attempt.reserved_output-out,available_micro_usd=BudgetRow.available_micro_usd+attempt.reserved_micro_usd-cost))
            # Attempt allowance is always consumed, including zero-charge models.
            attempt.actual_input=inp;attempt.actual_output=out;attempt.actual_micro_usd=cost;attempt.state='settled'
            output={'version':1,'text':raw['text'],'digest':digest(raw),'usage':copy.deepcopy(raw)}
            row.output=output;row.state='succeeded_late' if row.state=='outcome_unknown' or _aware(row.lease_until)<=self.clock._now(db) else 'succeeded';row.failure=None
            db.add(GenerationEventRow(generation_id=ident,event='output-settled',at=self.clock._now(db)));db.flush();hook('before-output-commit')
        hook('after-output-commit');return self.get(ident,tenant)
    def description_for_proposal(self,ident,tenant,version,output_digest):
        with self.sessions() as db:
            row=db.get(GenerationRow,ident)
            if row is None or row.tenant_id!=tenant:raise KeyError(ident)
            self._validate(db,row,authority=False)
            if row.state!='succeeded' or not row.output or row.output['version']!=version or row.output['digest']!=output_digest or digest(row.output['usage'])!=output_digest or row.output['text']!=row.output['usage']['text']:raise wa.DispatchRefused('committed successful output version required')
            return row.output['text'] # No proposal send, transport, or money authority.

class GenerationDispatcher:
    def __init__(self,repo,adapter):self.repo=repo;self.adapter=adapter
    async def dispatch(self,ident,tenant):
        initial=self.repo.get(ident,tenant)
        if initial['state']!='prepared':return initial
        wa.require_dispatch_ready()
        p=initial['request']
        if any(getattr(self.adapter,field,None)!=p[field] for field in ('account','model','model_version')):raise wa.DispatchRefused('generation adapter binding differs')
        try:fence=self.repo.claim(ident,tenant)
        except wa.DispatchRefused:return self.repo.get(ident,tenant)
        except Exception:return {'id':ident,'state':'outcome_unknown','failure':'generation-claim-unconfirmed'}
        try:
            committed=self.repo.get(ident,tenant)
            if committed['fence']!=fence or committed['state']!='dispatching':raise wa.DispatchRefused('generation readback differs')
            request=self.repo.before_entry(ident,tenant,fence)
            raw=await self.adapter.generate(copy.deepcopy(request['request']))
        except (Exception,asyncio.CancelledError):
            try:return self.repo.unknown(ident,tenant,fence)
            except Exception:return {'id':ident,'state':'outcome_unknown','failure':'generation-outcome-unconfirmed'}
        try:return self.repo.settle(ident,tenant,fence,raw)
        except Exception:return {'id':ident,'state':'outcome_unknown','failure':'generation-output-unconfirmed'}
