"""One approved immutable ready wave of offline Python sandbox work.

No automatic retry/resume. Claimed operations without saved receipt are unknown.
M00 consume and operation claim share a SQL transaction; idempotent permits never
re-enter execution. Production backend is Bubblewrap only, live probe required.
"""
from __future__ import annotations
import asyncio,base64,hashlib,json,os,re,shutil,stat,tempfile,time,uuid
from dataclasses import asdict
from pathlib import Path
from datetime import datetime,timezone
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import String,JSON,select,update,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service as ApprovalService,ApprovalConflictError
from app.modules.m04_research_scientist.approved_sandbox import BubblewrapBackend,ExecutionLimits,BackendUnavailableError,capture_environment_lock
from .sql_repository import ProjectRow,_view
from .runner import _ready

ACTION='execute_project_sandbox_batch'
PROFILE='bubblewrap-single-process-fixed-output-v1'
class WaveError(ValueError):pass
class WaveConflict(WaveError):pass
class WaveForbidden(WaveError):pass
class WaveUnavailable(WaveError):pass

class TaskCode(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    code:str=Field(min_length=1,max_length=50000)
    outputs:list[str]=Field(default_factory=lambda:['result.txt'],min_length=1,max_length=20)
    inputs:dict[str,str]=Field(default_factory=dict,max_length=20) # strict base64, flat names only

class WaveDraft(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    tasks:dict[str,TaskCode]=Field(min_length=1,max_length=500)
    max_parallel:int=Field(default=2,ge=1,le=8)
    timeout_seconds:int=Field(default=10,ge=1,le=60)
    memory_mb:int=Field(default=256,ge=64,le=512)

class SandboxWaveRow(Base):
    __tablename__='m14_sandbox_waves'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(120),index=True)
    actor_id:Mapped[str]=mapped_column(String(120))
    project_id:Mapped[str]=mapped_column(String(36),index=True)
    payload:Mapped[dict]=mapped_column(JSON)
    digest:Mapped[str]=mapped_column(String(64))
    state:Mapped[str]=mapped_column(String(40))
    approval_id:Mapped[str|None]=mapped_column(String(36),nullable=True,unique=True)
    claim_key:Mapped[str|None]=mapped_column(String(64),nullable=True,unique=True)
    result:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    created_at:Mapped[str]=mapped_column(String(40))

class SandboxWaveTaskRow(Base):
    __tablename__='m14_sandbox_wave_tasks'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    wave_id:Mapped[str]=mapped_column(String(36),index=True)
    task_id:Mapped[str]=mapped_column(String(120))
    receipt:Mapped[dict]=mapped_column(JSON)

class SandboxWaveArtifactRow(Base):
    __tablename__='m14_sandbox_wave_artifacts'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    wave_id:Mapped[str]=mapped_column(String(36),index=True)
    task_id:Mapped[str]=mapped_column(String(120))
    name:Mapped[str]=mapped_column(String(200))
    sha256:Mapped[str]=mapped_column(String(64))
    content_base64:Mapped[str]=mapped_column(String(1400000))

def digest(payload):return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def private_root(value):
    if not value:raise WaveUnavailable('sandbox root unavailable')
    p=Path(value)
    try:
        if not p.is_absolute() or any(x.is_symlink() for x in [p,*p.parents]):raise WaveUnavailable('sandbox root unavailable')
        p=p.resolve(strict=True)
        if not p.is_dir() or p.stat().st_mode & 0o077:raise WaveUnavailable('sandbox root unavailable')
        if any(p==x or x in p.parents for x in map(Path,('/tmp','/var/tmp','/dev/shm'))):raise WaveUnavailable('sandbox root unavailable')
        return p
    except OSError:raise WaveUnavailable('sandbox root unavailable') from None

class SandboxWaveService:
    def __init__(self,sessions,root,*,gate=None):
        self.sessions=sessions;self.root=private_root(root)
        self.gate=gate or ApprovalService(session_factory=sessions)
        from .wave_backend import WaveBubblewrapBackend
        self.backend=WaveBubblewrapBackend()

    def _owned(self,db,wave_id,tenant,actor):
        row=db.get(SandboxWaveRow,wave_id)
        if row is None or row.tenant_id!=tenant or row.actor_id!=actor:raise WaveForbidden('wave not available')
        return row

    def draft(self,tenant,actor,project_id,request:WaveDraft):
        environment=self._probe()
        with self.sessions.begin() as db:
            p=db.scalar(select(ProjectRow).where(ProjectRow.tenant_id==tenant,ProjectRow.id==project_id))
            if p is None:raise WaveForbidden('project not available')
            project=_view(p)
            if project.plan is None:raise WaveError('project requires plan')
            if set(request.tasks)!={t.id for t in project.plan.tasks}:raise WaveError('code required for every plan task')
            total_bytes=0
            for task in request.tasks.values():
                total_bytes+=len(task.code.encode())
                if len(set(task.outputs))!=len(task.outputs) or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',name) or name in ('.','..') for name in task.outputs):raise WaveError('flat unique output names required')
                for name,data in task.inputs.items():
                    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',name) or name in ('.','..','analysis.py'):raise WaveError('flat input name required')
                    if len(data)>133336:raise WaveError('input exceeds100k')
                    try:raw=base64.b64decode(data,validate=True)
                    except (ValueError,TypeError):raise WaveError('invalid input encoding') from None
                    total_bytes+=len(raw)
                    if len(raw)>100000:raise WaveError('input exceeds100k')
            if total_bytes>2000000:raise WaveError('draft bytes exceed2MB')
            # One bounded ready wave only; never dispatch reviewed/failed task or a dependent.
            ready=_ready(project.plan)[:request.max_parallel]
            if not ready:raise WaveError('no ready task in plan')
            if len(ready)>project.budget.max_agent_calls or len(ready)*request.timeout_seconds>project.budget.max_runtime_seconds:raise WaveError('wave reservations exceed project budget')
            payload={'tenant_id':tenant,'actor_id':actor,'project_id':project_id,'project_revision':project.revision,'plan':project.plan.model_dump(mode='json'),'budget':project.budget.model_dump(mode='json'),'config':request.model_dump(mode='json'),'profile':PROFILE,'environment':environment,'ready_task_ids':[t.id for t in ready],'reserved_calls':len(ready),'reserved_runtime_seconds':len(ready)*request.timeout_seconds,'reserved_cost_usd':0}
            if len(json.dumps(payload,ensure_ascii=False).encode())>4000000:raise WaveError('full draft exceeds4MB')
            row=SandboxWaveRow(id=str(uuid.uuid4()),tenant_id=tenant,actor_id=actor,project_id=project_id,payload=payload,digest=digest(payload),state='draft',created_at=datetime.now(timezone.utc).isoformat())
            db.add(row);db.flush();return self._view(row)

    def submit(self,tenant,actor,wave_id):
        with self.sessions() as db:
            row=self._owned(db,wave_id,tenant,actor)
            if row.state!='draft' or row.approval_id:raise WaveConflict('already submitted')
            payload=row.payload
        # Submit always PENDING; never use policy allow/gate.
        approval=self.gate.submit(module_id=14,action_type=ACTION,payload=payload,user_id=tenant,ttl_seconds=3600)
        with self.sessions.begin() as db:
            changed=db.execute(update(SandboxWaveRow).where(SandboxWaveRow.id==wave_id,SandboxWaveRow.state=='draft',SandboxWaveRow.approval_id.is_(None)).values(state='awaiting_approval',approval_id=approval['id']))
            if changed.rowcount!=1:raise WaveConflict('concurrent submit; orphan approval cannot dispatch')
        return self.get(tenant,actor,wave_id)

    @staticmethod
    def _view(row):return {'id':row.id,'project_id':row.project_id,'digest':row.digest,'state':row.state,'approval_id':row.approval_id,'payload':row.payload,'result':row.result,'single_wave_only':True,'unknown_after_claim':row.state=='claimed'}

    def get(self,tenant,actor,wave_id):
        with self.sessions() as db:return self._view(self._owned(db,wave_id,tenant,actor))

    def _probe(self):
        if not self.backend.available('python'):raise WaveUnavailable('sandbox backend unavailable')
        try:
            lock=capture_environment_lock(self.backend,'python',ExecutionLimits(timeout_seconds=5,memory_mb=256,max_log_bytes=32768))
        except Exception:raise WaveUnavailable('sandbox namespace capability unavailable') from None
        return lock

    def claim(self,tenant,actor,wave_id):
        private_root(str(self.root))
        environment=self._probe() # actual namespace/interpreter execution BEFORE consumption
        with self.sessions.begin() as db:
            row=self._owned(db,wave_id,tenant,actor)
            if row.state!='awaiting_approval' or not row.approval_id:raise WaveConflict('wave cannot be claimed')
            if row.digest!=digest(row.payload):raise WaveConflict('draft digest changed')
            p=db.scalar(select(ProjectRow).where(ProjectRow.tenant_id==tenant,ProjectRow.id==row.project_id).with_for_update())
            if p is None or p.revision!=row.payload['project_revision'] or p.plan!=row.payload['plan'] or p.budget!=row.payload['budget']:raise WaveConflict('project changed; fresh draft required')
            if environment!=row.payload['environment']:raise WaveConflict('sandbox environment changed')
            from app.modules.m00_approval_center.service import ApprovalRequestRow,ApprovalEventRow,ApprovalEffectRow,_aware
            approval=db.get(ApprovalRequestRow,row.approval_id)
            now=self.gate._clock()
            if approval is None or approval.status!='approved' or not approval.expires_at or _aware(approval.expires_at)<=now:raise WaveConflict('live approved unexpired request required')
            if not db.scalar(select(ApprovalEventRow.id).where(ApprovalEventRow.approval_id==row.approval_id,ApprovalEventRow.event=='approved')):raise WaveConflict('explicit human approval required')
            if db.scalar(select(ApprovalEffectRow.approval_id).where(ApprovalEffectRow.approval_id==row.approval_id)):raise WaveConflict('approval already consumed')
            claim_key=digest({'tenant':tenant,'project':row.project_id})
            if db.scalar(select(SandboxWaveRow.id).where(SandboxWaveRow.claim_key==claim_key)):raise WaveConflict('project already attempted this wave unit')
            changed=db.execute(update(SandboxWaveRow).where(SandboxWaveRow.id==wave_id,SandboxWaveRow.state=='awaiting_approval').values(state='claimed',claim_key=claim_key))
            if changed.rowcount!=1:raise WaveConflict('already claimed')
            self.gate.consume_effect(row.approval_id,module_id=14,action_type=ACTION,payload=row.payload,user_id=tenant,effect_id=wave_id,actor=actor,_session=db)
            payload=json.loads(json.dumps(row.payload))
        return payload,environment

    async def execute(self,tenant,actor,wave_id):
        payload,environment=self.claim(tenant,actor,wave_id)
        config=payload['config']
        # Cancellation of thread await cannot terminate arbitrary thread work; backend owns
        # sandbox process timeout/group cleanup. Claimed state remains unknown on interruption.
        outcomes=await asyncio.gather(*(asyncio.to_thread(self._task,task_id,config['tasks'][task_id],config) for task_id in payload['ready_task_ids']))
        result={'tasks':[x[0] for x in outcomes],'environment':environment,'state':'awaiting_review','single_wave_only':True,'all_dag_completed':False,'independent_quality_verified':False,'reserved_calls':payload['reserved_calls'],'reserved_runtime_seconds':payload['reserved_runtime_seconds'],'reserved_cost_usd':0}
        with self.sessions.begin() as db:
            row=self._owned(db,wave_id,tenant,actor)
            if row.state!='claimed':raise WaveConflict('operation state changed; do not replay')
            project=db.scalar(select(ProjectRow).where(ProjectRow.tenant_id==tenant,ProjectRow.id==row.project_id))
            result['concurrent_project_drift']=project is None or project.revision!=payload['project_revision'] or project.plan!=payload['plan'] or project.budget!=payload['budget']
            for receipt,artifacts in outcomes:
                db.add(SandboxWaveTaskRow(id=str(uuid.uuid4()),wave_id=wave_id,task_id=receipt['task_id'],receipt=receipt))
                for name,data in artifacts:
                    db.add(SandboxWaveArtifactRow(id=str(uuid.uuid4()),wave_id=wave_id,task_id=receipt['task_id'],name=name,sha256=hashlib.sha256(data).hexdigest(),content_base64=base64.b64encode(data).decode()))
            row.result=result;row.state='awaiting_review'
        return self.get(tenant,actor,wave_id)

    def _task(self,task_id,code,config):
        work=Path(tempfile.mkdtemp(prefix='wave-',dir=self.root))
        try:
            inp=work/'input';out=work/'output';inp.mkdir();out.mkdir()
            (inp/'analysis.py').write_text(code['code'])
            for name,value in code['inputs'].items():(inp/name).write_bytes(base64.b64decode(value,validate=True))
            for name in code['outputs']:(out/name).touch()
            limits=ExecutionLimits(timeout_seconds=config['timeout_seconds'],memory_mb=config['memory_mb'],cpus=1,pids=32,max_file_mb=1,max_log_bytes=16384,max_output_files=20,max_output_bytes=1000000,max_dataset_bytes=100000)
            run=self.backend.run(language='python',input_dir=inp,output_dir=out,limits=limits)
            artifacts=[];total=0
            paths=[]
            for parent,dirs,files in os.walk(out,followlinks=False):
                paths.extend(Path(parent)/name for name in [*dirs,*files])
                if len(paths)>100:raise WaveError('output tree exceeds bound')
            for path in sorted(paths):
                mode=path.lstat().st_mode
                if stat.S_ISDIR(mode):continue
                if not stat.S_ISREG(mode) or path.is_symlink():raise WaveError('output not regular file')
                if len(artifacts)>=20 or path.stat().st_size>1000000:raise WaveError('artifact bound exceeded')
                data=LocalBoundedRead(path,1000000);total+=len(data)
                if total>1000000:raise WaveError('artifact total exceeds bound')
                name=str(path.relative_to(out))
                if len(name)>200:raise WaveError('artifact name exceeds bound')
                artifacts.append((name,data))
            receipt={'task_id':task_id,'execution_state':'sandbox_executed' if run.exit_code==0 and not run.timed_out else 'failed','review_required':True,**asdict(run)}
            receipt['stdout']=run.stdout.decode('utf-8',errors='replace');receipt['stderr']=run.stderr.decode('utf-8',errors='replace')
            receipt['artifact_digests']=[{'name':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)} for name,data in artifacts]
            return receipt,artifacts
        except Exception:
            return {'task_id':task_id,'execution_state':'unknown','review_required':True,'error':'sandbox-or-artifact-receipt-failed'},[]
        finally:shutil.rmtree(work,ignore_errors=True)

    def artifact(self,tenant,actor,wave_id,artifact_id):
        with self.sessions() as db:
            self._owned(db,wave_id,tenant,actor)
            row=db.get(SandboxWaveArtifactRow,artifact_id)
            if row is None or row.wave_id!=wave_id:raise WaveForbidden('artifact not available')
            data=base64.b64decode(row.content_base64,validate=True)
            if hashlib.sha256(data).hexdigest()!=row.sha256:raise WaveConflict('artifact integrity mismatch')
            return data,row.name,row.sha256

    def artifacts(self,tenant,actor,wave_id):
        with self.sessions() as db:
            self._owned(db,wave_id,tenant,actor)
            return [{'id':x.id,'name':x.name,'sha256':x.sha256,'task_id':x.task_id} for x in db.scalars(select(SandboxWaveArtifactRow).where(SandboxWaveArtifactRow.wave_id==wave_id))]

def LocalBoundedRead(path,limit):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):raise WaveError('artifact not regular')
        data=handle.read(limit+1)
        if len(data)>limit:raise WaveError('artifact bound exceeded')
        return data
