"""Explicit finite local dispatcher. No daemon, broker, provider or network.

Operator-owned subprocesses execute approved immutable offline sandbox waves.
The logical admission gate and the wave execution gate remain separate.
"""
from __future__ import annotations
import asyncio,json,uuid,os,sys,subprocess
from datetime import datetime,timezone
from sqlalchemy import String,Integer,JSON,select,update
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.auth.context import TenantContext
from app.modules.m00_approval_center.service import ApprovalRequestRow,ApprovalEventRow,ApprovalEffectRow,_aware
from .builder_admission import BuilderAdmissionService,BuilderSlotRow
from .sandbox_wave import SandboxWaveService,WaveConflict,WaveForbidden,digest,ACTION
from .wave_supersede import current,evidence

class LocalDispatchPoolRow(Base):
    __tablename__='m14_local_dispatch_pool'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    policy:Mapped[dict]=mapped_column(JSON)

class LocalDispatchJobRow(Base):
    __tablename__='m14_local_dispatch_jobs'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(120),index=True)
    actor_id:Mapped[str]=mapped_column(String(120))
    wave_id:Mapped[str]=mapped_column(String(36),unique=True)
    batch_id:Mapped[str]=mapped_column(String(36))
    payload:Mapped[dict]=mapped_column(JSON)
    digest:Mapped[str]=mapped_column(String(64))
    state:Mapped[str]=mapped_column(String(30))
    fence:Mapped[int]=mapped_column(Integer)
    token:Mapped[str|None]=mapped_column(String(36),nullable=True)
    worker_id:Mapped[str|None]=mapped_column(String(120),nullable=True)
    result:Mapped[dict|None]=mapped_column(JSON,nullable=True)

POLICY={'workers':2,'sandbox_tasks':4,'max_wave_tasks':2}
class LocalDispatchService:
    MAX_WORKERS=2
    def __init__(self,sessions,root):
        self.sessions=sessions;self.admission=BuilderAdmissionService(sessions);self.waves=SandboxWaveService(sessions,root)
    def _job(self,db,ctx,id):
        row=db.get(LocalDispatchJobRow,id)
        if row is None or row.tenant_id!=ctx.tenant_id or row.actor_id!=ctx.actor_id:raise WaveForbidden('owner local job unavailable')
        if row.digest!=digest(row.payload):raise WaveConflict('job digest changed')
        return row
    def _policy(self,db):
        p=db.get(LocalDispatchPoolRow,1)
        if p is None or p.policy!=POLICY:raise WaveConflict('explicit local pool migration/policy required')
    def _slots(self,db,ctx,batch,wave):
        self.admission._batch(db,ctx,batch.id)
        slots=list(db.scalars(select(BuilderSlotRow).where(BuilderSlotRow.batch_id==batch.id,BuilderSlotRow.wave_id==wave.id).order_by(BuilderSlotRow.task_id)))
        if len(slots)!=len(wave.payload['ready_task_ids']) or {s.task_id for s in slots}!=set(wave.payload['ready_task_ids']):raise WaveConflict('complete wave admission required')
        if not 1<=len(slots)<=POLICY['max_wave_tasks']:raise WaveConflict('local wave limit2')
        for s in slots:
            if s.actor_id!=ctx.actor_id or s.tenant_id!=ctx.tenant_id or s.project_id!=wave.project_id or s.resources['cpu_units']<1 or s.resources['memory_mb']<wave.payload['config']['memory_mb'] or s.resources['runtime_seconds']<wave.payload['config']['timeout_seconds'] or s.resources['cost_cents']!=0:raise WaveConflict('owner admission resources insufficient')
        return slots
    def _execution_approval(self,db,ctx,wave):
        a=db.get(ApprovalRequestRow,wave.approval_id) if wave.approval_id else None
        if wave.state!='awaiting_approval' or a is None or a.user_id!=ctx.tenant_id or a.module_id!=14 or a.action_type!=ACTION or a.payload!=wave.payload or a.status!='approved' or a.approved_by!=ctx.actor_id or not a.expires_at or _aware(a.expires_at)<=self.admission.clock():raise WaveConflict('separate live owner wave execution approval required')
        if not db.scalar(select(ApprovalEventRow.id).where(ApprovalEventRow.approval_id==a.id,ApprovalEventRow.event=='approved',ApprovalEventRow.actor==ctx.actor_id)) or db.scalar(select(ApprovalEffectRow.id).where(ApprovalEffectRow.approval_id==a.id)):raise WaveConflict('unused explicit owner execution approval required')
    def enqueue(self,ctx,batch_id,wave_id):
        with self.sessions.begin() as db:
            self.admission._lock(db);self._policy(db);batch=self.admission._batch(db,ctx,batch_id)
            if batch.state!='reserved':raise WaveConflict('reserved admission required')
            wave=self.waves._owned(db,wave_id,ctx.tenant_id,ctx.actor_id)
            self._execution_approval(db,ctx,wave)
            if self.admission._sources(db,ctx,[wave.id])!=[s for s in batch.payload['sources'] if s['wave_id']==wave.id]:raise WaveConflict('admission source changed')
            slots=self._slots(db,ctx,batch,wave)
            if any(s.state!='reserved' or datetime.fromisoformat(s.expires_at)<=self.admission.clock() for s in slots):raise WaveConflict('unexpired complete reservation required')
            if db.scalar(select(LocalDispatchJobRow.id).where(LocalDispatchJobRow.wave_id==wave_id)):raise WaveConflict('wave already enqueued')
            payload=dict(batch_id=batch_id,batch_digest=batch.digest,wave_id=wave_id,wave_digest=wave.digest,slot_ids=[s.id for s in slots],policy=POLICY)
            row=LocalDispatchJobRow(id=str(uuid.uuid4()),tenant_id=ctx.tenant_id,actor_id=ctx.actor_id,wave_id=wave_id,batch_id=batch_id,payload=payload,digest=digest(payload),state='queued',fence=0)
            db.add(row);db.flush();id=row.id
        return self.get(ctx,id)
    def get(self,ctx,id):
        with self.sessions() as db:
            r=self._job(db,ctx,id)
            return dict(id=r.id,state=r.state,payload=r.payload,fence=r.fence,worker_id=r.worker_id,result=r.result,outcome_unknown=r.state=='claimed',logical_only=False,operational_1000_deployment_verified=False)
    def claim(self,ctx,id,worker_id):
        if not isinstance(worker_id,str) or not worker_id.strip() or len(worker_id)>120:raise WaveConflict('bounded worker label required')
        environment=self.waves._probe()
        with self.sessions.begin() as db:
            self.admission._lock(db);self._policy(db);job=self._job(db,ctx,id)
            if job.state!='queued':raise WaveConflict('queued one-shot job required')
            active=list(db.scalars(select(LocalDispatchJobRow).where(LocalDispatchJobRow.state=='claimed')))
            if len(active)>=POLICY['workers'] or sum(len(r.payload['slot_ids']) for r in active)+len(job.payload['slot_ids'])>POLICY['sandbox_tasks']:raise WaveConflict('local worker pool exhausted')
            batch=self.admission._batch(db,ctx,job.batch_id);wave=self.waves._owned(db,job.wave_id,ctx.tenant_id,ctx.actor_id)
            if batch.state!='reserved' or batch.digest!=job.payload['batch_digest'] or wave.digest!=job.payload['wave_digest']:raise WaveConflict('immutable enqueue source changed')
            self._execution_approval(db,ctx,wave)
            if self.admission._sources(db,ctx,[wave.id])!=[s for s in batch.payload['sources'] if s['wave_id']==wave.id]:raise WaveConflict('admission source drift')
            slots=self._slots(db,ctx,batch,wave)
            if [s.id for s in slots]!=job.payload['slot_ids'] or any(s.state!='reserved' or datetime.fromisoformat(s.expires_at)<=self.admission.clock() for s in slots):raise WaveConflict('whole live wave reservation required')
            payload=self.waves._claim_in_session(db,ctx.tenant_id,ctx.actor_id,wave.id,environment)
            token=str(uuid.uuid4());job.fence+=1;job.token=token;job.worker_id=worker_id;job.state='claimed'
            claims=[]
            for s in slots:
                s.state='claimed';s.fence+=1;s.token=token;s.worker_id=worker_id
                claims.append(dict(id=s.id,fence=s.fence))
                self.admission._event(db,batch,s,ctx,'local_dispatch_claimed',dict(job_id=id,worker_id=worker_id))
            result=dict(payload=payload,environment=environment,token=token,fence=job.fence,slots=claims,worker_id=worker_id)
        return result
    def finish(self,ctx,id,claim,outcomes):
        with self.sessions.begin() as db:
            pool=self.admission._lock(db);self._policy(db);job=self._job(db,ctx,id)
            if job.state!='claimed' or job.token!=claim['token'] or job.fence!=claim['fence'] or job.worker_id!=claim['worker_id']:raise WaveConflict('local job fence changed')
            wave=self.waves._owned(db,job.wave_id,ctx.tenant_id,ctx.actor_id);batch=self.admission._batch(db,ctx,job.batch_id)
            if wave.digest!=job.payload['wave_digest'] or claim['payload']!=wave.payload or current(db,wave)[1]!=wave.id:raise WaveConflict('wave publication source changed')
            slots=self._slots(db,ctx,batch,wave);fences={s['id']:s['fence'] for s in claim['slots']}
            if any(s.state!='claimed' or s.token!=claim['token'] or s.fence!=fences.get(s.id) or s.worker_id!=claim['worker_id'] or datetime.fromisoformat(s.expires_at)<=self.admission.clock() for s in slots):raise WaveConflict('admission publication fence/expiry changed')
            ids=wave.payload['ready_task_ids']
            if len(outcomes)!=len(ids) or {x[0]['task_id'] for x in outcomes}!=set(ids):raise WaveConflict('complete task receipt selection required')
            if any(x[0].get('execution_state') not in ('sandbox_executed','failed') or x[0].get('backend')!=self.waves.backend.name for x in outcomes):raise WaveConflict('actual sandbox execution receipt required')
            result=dict(tasks=[x[0] for x in outcomes],environment=claim['environment'],state='awaiting_review',single_wave_only=True,all_dag_completed=False,independent_quality_verified=False,reserved_calls=wave.payload['reserved_calls'],reserved_runtime_seconds=wave.payload['reserved_runtime_seconds'],reserved_cost_usd=0)
            self.waves._publish_in_session(db,ctx.tenant_id,ctx.actor_id,wave.id,result,outcomes);db.flush()
            if evidence(db,wave)['classification']!='verified S6':raise WaveConflict('complete durable S6 required')
            failed=any(x[0].get('exit_code')!=0 or x[0].get('timed_out') is not False for x in outcomes)
            for s in slots:
                self.admission._release(db,pool,s);s.state='failed' if failed else 'completed'
                self.admission._event(db,batch,s,ctx,'local_dispatch_settled',dict(job_id=id,outcome=s.state))
            job.state='failed' if failed else 'completed';job.token=None;job.result=dict(wave_id=wave.id,evidence=evidence(db,wave),review_required=True,independent_quality_verified=False)
        return self.get(ctx,id)
    def run(self,ctx,id,worker_id):
        claim=self.claim(ctx,id,worker_id);config=claim['payload']['config']
        async def execute():return await asyncio.gather(*(asyncio.to_thread(self.waves._task,t,config['tasks'][t],config) for t in claim['payload']['ready_task_ids']))
        outcomes=asyncio.run(execute())
        return self.finish(ctx,id,claim,outcomes)

def run_local_pool(uri,root,ctx,job_ids):
    """Finite operator invocation, at most two processes. No arbitrary code transport."""
    if os.getenv('ATLAS_M14_LOCAL_DISPATCH')!='1':raise WaveConflict('explicit local dispatch opt-in required')
    if not isinstance(ctx,TenantContext) or not isinstance(job_ids,list) or not 1<=len(job_ids)<=2 or len(set(job_ids))!=len(job_ids):raise WaveConflict('finite pool requires1..2distinctjobs')
    children=[]
    try:
        for id in job_ids:
            body=json.dumps(dict(uri=uri,root=root,tenant=ctx.tenant_id,actor=ctx.actor_id,job_id=id,worker_id='local-'+str(uuid.uuid4())))
            p=subprocess.Popen([sys.executable,'-m','app.modules.m14_project_builder.local_dispatch_worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            p.stdin.write(body);p.stdin.close();p.stdin=None;children.append(p)
        results=[]
        for p in children:
            out,err=p.communicate(timeout=180)
            if p.returncode!=0:
                raise WaveConflict('local worker refused or interrupted; inspect durable unknown state')
            results.append(json.loads(out))
        return results
    finally:
        # Supervisor does not free claims when killing a stuck worker.
        for p in children:
            if p.poll() is None:p.kill();p.wait()

def main():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    if os.getenv('ATLAS_M14_LOCAL_DISPATCH')!='1':raise WaveConflict('explicit local dispatch opt-in required')
    body=json.load(sys.stdin)
    engine=create_engine(body['uri']);sessions=sessionmaker(engine,expire_on_commit=False)
    try:print(json.dumps(LocalDispatchService(sessions,body['root']).run(TenantContext(body['tenant'],body['actor']),body['job_id'],body['worker_id'])))
    finally:engine.dispose()

