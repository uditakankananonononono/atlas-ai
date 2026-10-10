"""Durable logical builder admission. No worker launch or provider dispatch.

A single database mutex serializes every capacity-changing transaction on both
PostgreSQL and SQLite. Claimed work never expires into free capacity: expiry
means outcome-unknown, retained until explicit owner reconciliation.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import JSON, Integer, String, UniqueConstraint, select, update
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated
from app.core.database import Base
from app.auth.context import TenantContext
from app.modules.m00_approval_center.service import Service as ApprovalService, ApprovalRequestRow, ApprovalEventRow, ApprovalEffectRow, _aware
from .sandbox_wave import SandboxWaveRow, WaveConflict, WaveForbidden, digest
from .sql_repository import ProjectRow
from .schemas import ProjectPlan
from .runner import _ready

ACTION = 'admit_logical_builders'
RESOURCE_KEYS = ('slots', 'cpu_units', 'memory_mb', 'runtime_seconds', 'cost_cents')
GLOBAL_LIMITS = dict(slots=1000, cpu_units=1000, memory_mb=256000, runtime_seconds=1000000, cost_cents=0)
TENANT_LIMITS = dict(slots=600, cpu_units=600, memory_mb=153600, runtime_seconds=600000, cost_cents=0)

class AdmissionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    wave_ids: list[Annotated[str, StringConstraints(min_length=1, max_length=36)]] = Field(min_length=1, max_length=1000)
    cpu_units: int = Field(default=1, ge=1, le=8)
    memory_mb: int = Field(default=256, ge=1, le=4096)
    runtime_seconds: int = Field(default=600, ge=1, le=86400)
    cost_cents: int = Field(default=0, ge=0, le=0)
    ttl_seconds: int = Field(default=3600, ge=1, le=86400)

class BuilderPoolRow(Base):
    __tablename__ = 'm14_builder_pool'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    epoch: Mapped[int] = mapped_column(Integer)
    limits: Mapped[dict] = mapped_column(JSON)
    used: Mapped[dict] = mapped_column(JSON)

class BuilderTenantRow(Base):
    __tablename__ = 'm14_builder_tenants'
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    limits: Mapped[dict] = mapped_column(JSON)
    used: Mapped[dict] = mapped_column(JSON)

class BuilderBatchRow(Base):
    __tablename__ = 'm14_builder_batches'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    actor_id: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(30))
    approval_id: Mapped[str] = mapped_column(String(36), unique=True)
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decided_at: Mapped[str | None] = mapped_column(String(40), nullable=True)

class BuilderSlotRow(Base):
    __tablename__ = 'm14_builder_slots'
    __table_args__ = (UniqueConstraint('work_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    actor_id: Mapped[str] = mapped_column(String(120))
    work_key: Mapped[str] = mapped_column(String(64))
    wave_id: Mapped[str] = mapped_column(String(36))
    project_id: Mapped[str] = mapped_column(String(36))
    task_id: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(30))
    resources: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[str] = mapped_column(String(40))
    fence: Mapped[int] = mapped_column(Integer)
    token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reconciliation: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class BuilderAdmissionEventRow(Base):
    __tablename__ = 'm14_builder_admission_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(36))
    slot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_id: Mapped[str] = mapped_column(String(120))
    event: Mapped[str] = mapped_column(String(40))
    at: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON)

MODELS = (BuilderPoolRow, BuilderTenantRow, BuilderBatchRow, BuilderSlotRow, BuilderAdmissionEventRow)
def zeros(): return dict.fromkeys(RESOURCE_KEYS, 0)
def _now(): return datetime.now(timezone.utc)

def _ctx(ctx):
    if not isinstance(ctx, TenantContext) or any(not isinstance(v,str) or not v.strip() or len(v)>120 for v in (ctx.tenant_id,ctx.actor_id)):
        raise WaveForbidden('authenticated owner required')

def _view(row):
    return dict(id=row.id, state=row.state, digest=row.digest, payload=row.payload, approval_id=row.approval_id)

def _slot(row):
    return {k:getattr(row,k) for k in ('id','batch_id','wave_id','project_id','task_id','state','resources','expires_at','fence','worker_id','reconciliation')}

class BuilderAdmissionService:
    CAPACITY = 1000
    def __init__(self, sessions, clock=_now):
        self.sessions, self.clock = sessions, clock
        self.gate = ApprovalService(sessions, clock=clock)

    def _lock(self, db):
        if db.execute(update(BuilderPoolRow).where(BuilderPoolRow.id==1).values(epoch=BuilderPoolRow.epoch+1)).rowcount != 1:
            raise WaveConflict('admission pool not provisioned; migrate explicitly')
        pool = db.get(BuilderPoolRow, 1, populate_existing=True)
        if pool.limits != GLOBAL_LIMITS:
            raise WaveConflict('pool policy drift')
        return pool

    def _batch(self,db,ctx,id):
        _ctx(ctx)
        row = db.get(BuilderBatchRow,id)
        if row is None or row.tenant_id != ctx.tenant_id or row.actor_id != ctx.actor_id:
            raise WaveForbidden('owner batch unavailable')
        if row.digest != digest(row.payload): raise WaveConflict('batch digest corrupt')
        return row

    def _sources(self,db,ctx,wave_ids):
        if len(set(wave_ids))!=len(wave_ids) or any(not isinstance(w,str) or not 1<=len(w)<=36 for w in wave_ids):
            raise WaveConflict('distinct bounded wave identifiers required')
        sources=[]; seen=set()
        for wid in sorted(wave_ids):
            wave=db.get(SandboxWaveRow,wid)
            if wave is None or wave.tenant_id!=ctx.tenant_id or wave.actor_id!=ctx.actor_id:
                raise WaveForbidden('owner wave unavailable')
            if wave.state not in ('draft','awaiting_approval') or wave.claim_key or wave.digest!=digest(wave.payload):
                raise WaveConflict('unattempted immutable owner wave required')
            project=db.scalar(select(ProjectRow).where(ProjectRow.tenant_id==ctx.tenant_id,ProjectRow.id==wave.project_id))
            if project is None or project.revision!=wave.payload.get('project_revision') or project.plan!=wave.payload.get('plan') or project.budget!=wave.payload.get('budget'):
                raise WaveConflict('project snapshot drift')
            from .reviewed_continuation import check_ready
            check_ready(db,project)
            ready={t.id for t in _ready(ProjectPlan.model_validate(project.plan))}
            ids=wave.payload.get('ready_task_ids')
            if not isinstance(ids,list) or not 1<=len(ids)<=8 or len(set(ids))!=len(ids) or not set(ids)<=ready:
                raise WaveConflict('bounded ready wave required')
            for tid in ids:
                key=(wave.project_id,tid)
                if key in seen:raise WaveConflict('duplicate project task')
                seen.add(key)
            sources.append(dict(wave_id=wid,wave_digest=wave.digest,project_id=project.id,revision=project.revision,task_ids=ids))
        if len(seen)>1000:raise WaveConflict('batch exceeds 1000')
        return sources

    def propose(self,ctx,request):
        _ctx(ctx)
        if not isinstance(request,AdmissionRequest):raise WaveConflict('typed admission request required')
        with self.sessions() as db:sources=self._sources(db,ctx,request.wave_ids)
        now=self.clock(); expires=(now+timedelta(seconds=request.ttl_seconds)).isoformat()
        resources=dict(slots=1,cpu_units=request.cpu_units,memory_mb=request.memory_mb,runtime_seconds=request.runtime_seconds,cost_cents=request.cost_cents)
        payload=dict(tenant_id=ctx.tenant_id,owner_actor=ctx.actor_id,sources=sources,resources=resources,expires_at=expires,logical_only=True,dispatch_authorized=False)
        approval=self.gate.submit(module_id=14,action_type=ACTION,payload=payload,user_id=ctx.tenant_id,ttl_seconds=request.ttl_seconds)
        with self.sessions.begin() as db:
            row=BuilderBatchRow(id=str(uuid.uuid4()),tenant_id=ctx.tenant_id,actor_id=ctx.actor_id,payload=payload,digest=digest(payload),state='awaiting_approval',approval_id=approval['id'])
            db.add(row);db.flush();result=_view(row)
        return result

    def get(self,ctx,id):
        with self.sessions() as db:
            row=self._batch(db,ctx,id);result=_view(row)
            slots=list(db.scalars(select(BuilderSlotRow).where(BuilderSlotRow.batch_id==id)))
            result['slots']=[_slot(s) for s in slots]
            result['outcome_unknown_ids']=[s.id for s in slots if s.state=='unknown' or s.state=='claimed' and datetime.fromisoformat(s.expires_at)<=self.clock()]
            result['dispatch_authorized']=False
            return result

    def decide(self,ctx,id,decision):
        if decision not in ('approved','denied'):raise WaveConflict('explicit human decision required')
        with self.sessions.begin() as db:
            self._lock(db);row=self._batch(db,ctx,id);a=db.get(ApprovalRequestRow,row.approval_id);now=self.clock()
            if row.state!='awaiting_approval' or a is None or a.status!='pending' or a.payload!=row.payload or a.user_id!=ctx.tenant_id or a.module_id!=14 or a.action_type!=ACTION or not a.expires_at or _aware(a.expires_at)<=now:
                raise WaveConflict('matching live owner approval required')
            a.status=decision;a.approved_by=ctx.actor_id;a.decided_at=now
            row.state=decision;row.decided_by=ctx.actor_id;row.decided_at=now.isoformat()
            db.add(ApprovalEventRow(approval_id=a.id,event=decision,actor=ctx.actor_id,at=now))
        return self.get(ctx,id)

    def reserve(self,ctx,id):
        with self.sessions.begin() as db:
            pool=self._lock(db);row=self._batch(db,ctx,id);now=self.clock();a=db.get(ApprovalRequestRow,row.approval_id)
            if row.state!='approved' or row.decided_by!=ctx.actor_id or not row.decided_at or datetime.fromisoformat(row.payload['expires_at'])<=now or a is None or a.status!='approved' or not a.expires_at or _aware(a.expires_at)<=now or a.approved_by!=ctx.actor_id or a.payload!=row.payload or a.action_type!=ACTION or a.module_id!=14 or a.user_id!=ctx.tenant_id or db.scalar(select(ApprovalEffectRow.id).where(ApprovalEffectRow.approval_id==a.id)):
                raise WaveConflict('unused live module owner approval required')
            if self._sources(db,ctx,[s['wave_id'] for s in row.payload['sources']])!=row.payload['sources']:
                raise WaveConflict('source changed')
            tenant=db.get(BuilderTenantRow,ctx.tenant_id)
            if tenant is None:
                tenant=BuilderTenantRow(tenant_id=ctx.tenant_id,limits=dict(TENANT_LIMITS),used=zeros());db.add(tenant)
            if tenant.limits!=TENANT_LIMITS:raise WaveConflict('tenant policy drift')
            count=sum(len(s['task_ids']) for s in row.payload['sources']); total={k:v*count for k,v in row.payload['resources'].items()}
            for quota in (pool,tenant):
                if any(quota.used[k]+total[k]>quota.limits[k] for k in RESOURCE_KEYS):raise WaveConflict('admission quota exhausted')
                quota.used={k:quota.used[k]+total[k] for k in RESOURCE_KEYS}
            # The permanent logical-task key prevents replay through fresh approvals.
            for source in row.payload['sources']:
                for tid in source['task_ids']:
                    work_key=digest(dict(tenant=ctx.tenant_id,project=source['project_id'],task=tid))
                    if db.scalar(select(BuilderSlotRow.id).where(BuilderSlotRow.work_key==work_key)):
                        raise WaveConflict('task already admitted; explicit next-generation policy required')
                    db.add(BuilderSlotRow(id=str(uuid.uuid4()),batch_id=id,tenant_id=ctx.tenant_id,actor_id=ctx.actor_id,work_key=work_key,wave_id=source['wave_id'],project_id=source['project_id'],task_id=tid,state='reserved',resources=dict(row.payload['resources']),expires_at=row.payload['expires_at'],fence=0))
            self.gate.consume_effect(a.id,module_id=14,action_type=ACTION,payload=row.payload,user_id=ctx.tenant_id,effect_id=id,actor=ctx.actor_id,_session=db)
            row.state='reserved';self._event(db,row,None,ctx,'reserved',dict(count=count))
        return self.get(ctx,id)

    def _event(self,db,batch,slot,ctx,event,details):
        db.add(BuilderAdmissionEventRow(batch_id=batch.id,slot_id=slot.id if slot else None,actor_id=ctx.actor_id,event=event,at=self.clock().isoformat(),details=details))

    def _owned_slot(self,db,ctx,id):
        _ctx(ctx);slot=db.get(BuilderSlotRow,id)
        if slot is None or slot.tenant_id!=ctx.tenant_id or slot.actor_id!=ctx.actor_id:raise WaveForbidden('owner slot unavailable')
        batch=self._batch(db,ctx,slot.batch_id)
        return slot,batch

    def claim(self,ctx,id,worker_id):
        if not isinstance(worker_id,str) or not worker_id.strip() or len(worker_id)>120:raise WaveConflict('bounded worker id required')
        with self.sessions.begin() as db:
            self._lock(db);slot,batch=self._owned_slot(db,ctx,id)
            if slot.state!='reserved' or datetime.fromisoformat(slot.expires_at)<=self.clock():raise WaveConflict('unexpired reserved slot required')
            if self._sources(db,ctx,[s['wave_id'] for s in batch.payload['sources']])!=batch.payload['sources']:raise WaveConflict('source drift before claim')
            slot.state='claimed';slot.fence+=1;slot.token=str(uuid.uuid4());slot.worker_id=worker_id
            self._event(db,batch,slot,ctx,'claimed',dict(fence=slot.fence,worker_id=worker_id))
            result={**_slot(slot),'token':slot.token,'dispatch_authorized':False}
        return result

    def _release(self,db,pool,slot):
        tenant=db.get(BuilderTenantRow,slot.tenant_id)
        for quota in (pool,tenant):
            if quota is None or any(quota.used[k]<slot.resources[k] for k in RESOURCE_KEYS):raise WaveConflict('quota integrity refusal')
            quota.used={k:quota.used[k]-slot.resources[k] for k in RESOURCE_KEYS}
        slot.fence+=1;slot.token=None

    def complete(self,ctx,id,token,fence,worker_id,outcome):
        if outcome not in ('completed','failed'):raise WaveConflict('explicit terminal outcome required')
        with self.sessions.begin() as db:
            pool=self._lock(db);slot,batch=self._owned_slot(db,ctx,id)
            if type(fence)!=int or slot.state!='claimed' or slot.token!=token or not token or slot.fence!=fence or slot.worker_id!=worker_id or datetime.fromisoformat(slot.expires_at)<=self.clock():raise WaveConflict('live matching fenced claim required; reconcile unknown explicitly')
            self._release(db,pool,slot);slot.state=outcome
            self._event(db,batch,slot,ctx,outcome,dict(worker_id=worker_id))
        return self.get(ctx,batch.id)

    def cancel(self,ctx,id):
        with self.sessions.begin() as db:
            pool=self._lock(db);slot,batch=self._owned_slot(db,ctx,id)
            if slot.state=='reserved':self._release(db,pool,slot);slot.state='cancelled'
            elif slot.state=='claimed':slot.state='unknown';slot.fence+=1;slot.token=None
            else:raise WaveConflict('reserved or claimed slot required')
            self._event(db,batch,slot,ctx,'cancel_requested',dict(state=slot.state))
        return self.get(ctx,batch.id)

    def reconcile(self,ctx,id,reason):
        if not isinstance(reason,str) or not 3<=len(reason.strip())<=1000:raise WaveConflict('explicit reconciliation reason required')
        with self.sessions.begin() as db:
            pool=self._lock(db);slot,batch=self._owned_slot(db,ctx,id)
            if slot.state!='unknown' and not (slot.state=='claimed' and datetime.fromisoformat(slot.expires_at)<=self.clock()):raise WaveConflict('outcome-unknown claim required')
            slot.reconciliation=dict(owner_actor=ctx.actor_id,reason=reason,at=self.clock().isoformat(),outcome='unknown_closed_no_retry')
            self._release(db,pool,slot);slot.state='reconciled_unknown'
            self._event(db,batch,slot,ctx,'owner_reconciled_unknown',slot.reconciliation)
        return self.get(ctx,batch.id)

    def status(self,ctx):
        _ctx(ctx)
        with self.sessions() as db:
            tenant=db.get(BuilderTenantRow,ctx.tenant_id)
            return dict(tenant_limits=TENANT_LIMITS,tenant_used=tenant.used if tenant else zeros(),global_capacity=1000,logical_only=True,operational_1000_deployment_verified=False)
