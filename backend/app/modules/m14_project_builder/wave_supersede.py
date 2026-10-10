"""Human admin-controlled blocked-project unblock, never inferred abandonment."""
import base64,json,uuid
from datetime import datetime,timezone
from sqlalchemy import String,Integer,JSON,UniqueConstraint,select,update
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.auth.context import TenantContext
from .sandbox_wave import SandboxWaveRow,SandboxWaveTaskRow,SandboxWaveArtifactRow,WaveConflict,WaveForbidden,digest
from app.modules.m00_approval_center.service import ApprovalRequestRow,ApprovalEventRow,ApprovalEffectRow,_aware
ACTION='wave_supersede'

class WaveKeyVersionRow(Base):
    __tablename__='m14_wave_key_versions'
    __table_args__=(UniqueConstraint('project_key','version'),UniqueConstraint('new_wave_id'))
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    project_key:Mapped[str]=mapped_column(String(64),index=True)
    version:Mapped[int]=mapped_column(Integer)
    prior_wave_id:Mapped[str]=mapped_column(String(36))
    new_wave_id:Mapped[str]=mapped_column(String(36))
    admin_actor:Mapped[str]=mapped_column(String(120))
    supersede_id:Mapped[str]=mapped_column(String(36),unique=True)
    evidence:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[str]=mapped_column(String(40))

class WaveSupersedeRow(Base):
    __tablename__='m14_wave_supersedes'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(120))
    requester_actor:Mapped[str]=mapped_column(String(120))
    payload:Mapped[dict]=mapped_column(JSON)
    digest:Mapped[str]=mapped_column(String(64))
    approval_id:Mapped[str]=mapped_column(String(36),unique=True)
    state:Mapped[str]=mapped_column(String(40))
    approver_actor:Mapped[str|None]=mapped_column(String(120),nullable=True)
    approver_role:Mapped[str|None]=mapped_column(String(40),nullable=True)
    decided_at:Mapped[str|None]=mapped_column(String(40),nullable=True)


def admin(context):
    if not isinstance(context,TenantContext) or not context.has_role('atlas-admin'):raise WaveForbidden('authenticated tenant admin required')

def project_key(wave):return digest({'tenant':wave.tenant_id,'project':wave.project_id})

def current(db,wave):
    key=project_key(wave)
    row=db.scalar(select(WaveKeyVersionRow).where(WaveKeyVersionRow.project_key==key).order_by(WaveKeyVersionRow.version.desc()).limit(1))
    return (row.version,row.new_wave_id) if row else (0,wave.id)

def evidence(db,wave):
    if wave.digest!=digest(wave.payload):raise WaveConflict('prior digest corrupt')
    tasks=list(db.scalars(select(SandboxWaveTaskRow).where(SandboxWaveTaskRow.wave_id==wave.id)))
    artifacts=list(db.scalars(select(SandboxWaveArtifactRow).where(SandboxWaveArtifactRow.wave_id==wave.id)))
    if wave.state=='claimed':
        if wave.result is not None or tasks or artifacts:raise WaveConflict('partial durable evidence refused')
        return {'classification':'unknown / no S6 evidence','sha256':None}
    if wave.state!='awaiting_review' or not isinstance(wave.result,dict):raise WaveConflict('prior wave not attempted or verifiable')
    expected=wave.payload['ready_task_ids']
    if sorted(t.task_id for t in tasks)!=sorted(expected):raise WaveConflict('task evidence mismatch')
    receipts={t.task_id:t.receipt for t in tasks}
    if sorted(wave.result.get('tasks',[]),key=lambda x:x['task_id'])!=sorted(receipts.values(),key=lambda x:x['task_id']):raise WaveConflict('result/task evidence mismatch')
    seen=[]
    for a in artifacts:
        try:raw=base64.b64decode(a.content_base64,validate=True)
        except Exception:raise WaveConflict('artifact encoding corrupt') from None
        if digest_bytes(raw)!=a.sha256:raise WaveConflict('artifact digest corrupt')
        if a.task_id not in receipts:raise WaveConflict('orphan artifact refused')
        seen.append((a.task_id,a.name,a.sha256,len(raw)))
    expected_artifacts=[(task_id,a['name'],a['sha256'],a['bytes']) for task_id,r in receipts.items() for a in r.get('artifact_digests',[])]
    if sorted(seen)!=sorted(expected_artifacts):raise WaveConflict('artifact evidence mismatch')
    return {'classification':'verified S6','sha256':digest({'payload_digest':wave.digest,'result':wave.result,'tasks':receipts,'artifacts':sorted(seen)})}

def digest_bytes(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()

class WaveSupersedeService:
    def __init__(self,waves):self.waves=waves;self.sessions=waves.sessions;self.gate=waves.gate
    def _row(self,db,context,sid):
        admin(context);r=db.get(WaveSupersedeRow,sid)
        if r is None or r.tenant_id!=context.tenant_id:raise WaveForbidden('supersede not available')
        return r
    def _pair(self,db,context,prior_id,new_id):
        prior=db.get(SandboxWaveRow,prior_id);new=db.get(SandboxWaveRow,new_id)
        if prior is None or new is None or prior.id==new.id or prior.tenant_id!=context.tenant_id or new.tenant_id!=context.tenant_id or prior.project_id!=new.project_id or prior.actor_id!=new.actor_id:raise WaveForbidden('wave pair not available')
        if not prior.claim_key or prior.state not in ('claimed','awaiting_review'):raise WaveConflict('prior wave not attempted')
        if new.state!='awaiting_approval' or not new.approval_id or new.claim_key:raise WaveConflict('new immutable submitted wave required')
        if new.digest!=digest(new.payload):raise WaveConflict('new draft corrupt')
        if prior.payload['ready_task_ids']!=new.payload['ready_task_ids']:raise WaveConflict('only initially-ready task retry allowed')
        version,wid=current(db,prior)
        if wid!=prior.id:raise WaveConflict('prior wave is not current key version')
        return prior,new,version
    def propose(self,context,prior_id,new_id):
        admin(context)
        with self.sessions() as db:
            prior,new,version=self._pair(db,context,prior_id,new_id)
            payload={'tenant_id':context.tenant_id,'requester_admin':context.actor_id,'prior_wave_id':prior.id,'prior_digest':prior.digest,'current_key_version':version,'new_wave_id':new.id,'new_digest':new.digest,'new_reservation':{k:new.payload[k] for k in ('reserved_calls','reserved_runtime_seconds','reserved_cost_usd')},'evidence':evidence(db,prior),'no_completion_inference':True}
        approval=self.gate.submit(module_id=14,action_type=ACTION,payload=payload,user_id=context.tenant_id,ttl_seconds=3600)
        with self.sessions.begin() as db:
            r=WaveSupersedeRow(id=str(uuid.uuid4()),tenant_id=context.tenant_id,requester_actor=context.actor_id,payload=payload,digest=digest(payload),approval_id=approval['id'],state='awaiting_approval');db.add(r);db.flush();sid=r.id
        return self.get(context,sid)
    def get(self,context,sid):
        with self.sessions() as db:
            r=self._row(db,context,sid)
            return {'id':r.id,'state':r.state,'approval_id':r.approval_id,'digest':r.digest,'payload':r.payload,'approver_actor':r.approver_actor,'approver_role':r.approver_role}
    def decide(self,context,sid,decision):
        admin(context)
        if decision not in ('approved','denied'):raise WaveConflict('human approved or denied decision required')
        with self.sessions.begin() as db:
            r=self._row(db,context,sid);now=self.gate._clock()
            approval=db.get(ApprovalRequestRow,r.approval_id)
            if r.state!='awaiting_approval' or approval is None or approval.action_type!=ACTION or approval.status!='pending' or approval.payload!=r.payload or not approval.expires_at or _aware(approval.expires_at)<=now:raise WaveConflict('pending matching unexpired supersede required')
            changed=db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==approval.id,ApprovalRequestRow.status=='pending').values(status=decision,approved_by=context.actor_id,decided_at=now))
            if changed.rowcount!=1:raise WaveConflict('decision changed')
            changed=db.execute(update(WaveSupersedeRow).where(WaveSupersedeRow.id==r.id,WaveSupersedeRow.state=='awaiting_approval').values(state=decision,approver_actor=context.actor_id,approver_role='atlas-admin',decided_at=now.isoformat()))
            if changed.rowcount!=1:raise WaveConflict('supersede decision changed')
            db.add(ApprovalEventRow(approval_id=approval.id,event=decision,actor=context.actor_id,at=now))
        return self.get(context,sid)
    def apply(self,context,sid):
        admin(context)
        with self.sessions.begin() as db:
            r=self._row(db,context,sid)
            if r.state!='approved' or r.approver_role!='atlas-admin' or not r.approver_actor or r.digest!=digest(r.payload):raise WaveConflict('role-bound approved supersede required')
            prior=db.scalar(select(SandboxWaveRow).where(SandboxWaveRow.id==r.payload['prior_wave_id']).with_for_update())
            prior,new,version=self._pair(db,context,r.payload['prior_wave_id'],r.payload['new_wave_id'])
            if prior.digest!=r.payload['prior_digest'] or new.digest!=r.payload['new_digest'] or version!=r.payload['current_key_version'] or evidence(db,prior)!=r.payload['evidence']:raise WaveConflict('supersede evidence or version changed')
            approval=db.get(ApprovalRequestRow,r.approval_id);now=self.gate._clock()
            if approval is None or approval.status!='approved' or approval.approved_by!=r.approver_actor or not approval.expires_at or _aware(approval.expires_at)<=now or db.scalar(select(ApprovalEffectRow.approval_id).where(ApprovalEffectRow.approval_id==approval.id)):raise WaveConflict('live unused supersede approval required')
            changed=db.execute(update(SandboxWaveRow).where(SandboxWaveRow.id==prior.id,SandboxWaveRow.state==prior.state).values(state='superseded'))
            if changed.rowcount!=1:raise WaveConflict('prior finalization changed')
            changed=db.execute(update(WaveSupersedeRow).where(WaveSupersedeRow.id==r.id,WaveSupersedeRow.state=='approved').values(state='applied'))
            if changed.rowcount!=1:raise WaveConflict('supersede already applied')
            self.gate.consume_effect(approval.id,module_id=14,action_type=ACTION,payload=r.payload,user_id=context.tenant_id,effect_id=sid,actor=context.actor_id,_session=db)
            db.add(WaveKeyVersionRow(id=str(uuid.uuid4()),project_key=project_key(prior),version=version+1,prior_wave_id=prior.id,new_wave_id=new.id,admin_actor=r.approver_actor,supersede_id=sid,evidence=r.payload['evidence'],created_at=now.isoformat()))
        return self.get(context,sid)
    def history(self,context,project_id):
        admin(context);key=digest({'tenant':context.tenant_id,'project':project_id})
        with self.sessions() as db:
            return [{'version':r.version,'prior_wave_id':r.prior_wave_id,'new_wave_id':r.new_wave_id,'admin_actor':r.admin_actor,'evidence':r.evidence,'supersede_id':r.supersede_id} for r in db.scalars(select(WaveKeyVersionRow).where(WaveKeyVersionRow.project_key==key).order_by(WaveKeyVersionRow.version))]
