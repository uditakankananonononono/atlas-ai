"""Explicit owner review and continuation. No implied completion or auto-dispatch."""
import uuid,json
from sqlalchemy import String,JSON,select,update
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.auth.context import TenantContext
from app.modules.m00_approval_center.service import ApprovalRequestRow,ApprovalEventRow,ApprovalEffectRow,_aware
from .sandbox_wave import SandboxWaveRow,SandboxWaveTaskRow,WaveConflict,WaveForbidden,digest
from .wave_supersede import evidence,current
from .sql_repository import ProjectRow
REVIEW='review_project_sandbox_wave'
CONTINUE='continue_project_sandbox_wave'
class DecisionColumns:
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(120))
    actor_id:Mapped[str]=mapped_column(String(120))
    payload:Mapped[dict]=mapped_column(JSON)
    digest:Mapped[str]=mapped_column(String(64))
    approval_id:Mapped[str]=mapped_column(String(36),unique=True)
    state:Mapped[str]=mapped_column(String(30))
    decided_by:Mapped[str|None]=mapped_column(String(120),nullable=True)
    decided_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
class ReviewRow(DecisionColumns,Base):__tablename__='m14_wave_reviews'
class ContinuationRow(DecisionColumns,Base):__tablename__='m14_wave_continuations'

def owner(context,row):
    if not isinstance(context,TenantContext) or context.tenant_id!=row.tenant_id or context.actor_id!=row.actor_id:raise WaveForbidden('original owner required')

class ReviewedContinuationService:
    def __init__(self,waves):self.waves=waves;self.sessions=waves.sessions;self.gate=waves.gate
    def _row(self,db,ctx,id,model):
        row=db.get(model,id)
        if row is None:raise WaveForbidden('operation unavailable')
        owner(ctx,row);return row
    def _project(self,db,wave,lock=False):
        query=select(ProjectRow).where(ProjectRow.tenant_id==wave.tenant_id,ProjectRow.id==wave.project_id)
        if lock:query=query.with_for_update().execution_options(populate_existing=True)
        p=db.scalar(query)
        if p is None:raise WaveConflict('project unavailable')
        return p
    def _review_source(self,db,ctx,wave_id,selection):
        wave=self.waves._owned(db,wave_id,ctx.tenant_id,ctx.actor_id)
        if wave.state!='awaiting_review' or not wave.claim_key or current(db,wave)[1]!=wave.id:raise WaveConflict('current awaiting-review wave required')
        ev=evidence(db,wave)
        if ev['classification']!='verified S6':raise WaveConflict('verified S6 required')
        p=self._project(db,wave)
        if p.revision!=wave.payload['project_revision'] or p.plan!=wave.payload['plan'] or p.budget!=wave.payload['budget']:raise WaveConflict('project drift')
        if not isinstance(selection,dict) or set(selection)!=set(wave.payload['ready_task_ids']):raise WaveConflict('complete ready-task review required')
        receipts={r.task_id:r.receipt for r in db.scalars(select(SandboxWaveTaskRow).where(SandboxWaveTaskRow.wave_id==wave.id))}
        for id,decision in selection.items():
            if not isinstance(decision,dict) or set(decision)!={'accept','reason'} or type(decision['accept'])!=bool or not isinstance(decision['reason'],str) or not 1<=len(decision['reason'].strip())<=1000:raise WaveConflict('explicit task decisions and reasons required')
            r=receipts[id]
            if decision['accept'] and (r.get('execution_state')!='sandbox_executed' or r.get('exit_code')!=0 or r.get('timed_out') is not False):raise WaveConflict('only successful real execution may be accepted')
        return wave,p,ev
    def _submit(self,ctx,model,action,payload):
        approval=self.gate.submit(module_id=14,action_type=action,payload=payload,user_id=ctx.tenant_id,ttl_seconds=3600)
        with self.sessions.begin() as db:
            row=model(id=str(uuid.uuid4()),tenant_id=ctx.tenant_id,actor_id=ctx.actor_id,payload=payload,digest=digest(payload),approval_id=approval['id'],state='awaiting_approval');db.add(row);db.flush();id=row.id
        return self.get(ctx,id,model)
    def get(self,ctx,id,model=ReviewRow):
        with self.sessions() as db:
            row=self._row(db,ctx,id,model)
            return {'id':row.id,'state':row.state,'approval_id':row.approval_id,'digest':row.digest,'payload':row.payload}
    def propose_review(self,ctx,wave_id,selection):
        with self.sessions() as db:
            wave,p,ev=self._review_source(db,ctx,wave_id,selection)
            payload={'prior_wave_id':wave.id,'prior_digest':wave.digest,'evidence':ev,'project_revision':p.revision,'plan':p.plan,'budget':p.budget,'selection':selection,'owner_actor':ctx.actor_id,'tenant_id':ctx.tenant_id}
        return self._submit(ctx,ReviewRow,REVIEW,payload)
    def _decide(self,ctx,id,decision,model,action):
        if decision not in ('approved','denied'):raise WaveConflict('human decision required')
        with self.sessions.begin() as db:
            row=self._row(db,ctx,id,model);now=self.gate._clock();a=db.get(ApprovalRequestRow,row.approval_id)
            if row.state!='awaiting_approval' or a is None or a.status!='pending' or a.action_type!=action or a.module_id!=14 or a.user_id!=ctx.tenant_id or a.payload!=row.payload or row.digest!=digest(row.payload) or not a.expires_at or _aware(a.expires_at)<=now:raise WaveConflict('matching live owner request required')
            if db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==a.id,ApprovalRequestRow.status=='pending').values(status=decision,approved_by=ctx.actor_id,decided_at=now)).rowcount!=1:raise WaveConflict('decision changed')
            if db.execute(update(model).where(model.id==id,model.state=='awaiting_approval').values(state=decision,decided_by=ctx.actor_id,decided_at=now.isoformat())).rowcount!=1:raise WaveConflict('decision changed')
            db.add(ApprovalEventRow(approval_id=a.id,event=decision,actor=ctx.actor_id,at=now))
        return self.get(ctx,id,model)
    def decide_review(self,ctx,id,decision):return self._decide(ctx,id,decision,ReviewRow,REVIEW)
    def decide_continuation(self,ctx,id,decision):return self._decide(ctx,id,decision,ContinuationRow,CONTINUE)
    def _permit(self,db,ctx,row,action):
        now=self.gate._clock();a=db.get(ApprovalRequestRow,row.approval_id)
        if row.state!='approved' or row.decided_by!=ctx.actor_id or not row.decided_at or row.digest!=digest(row.payload) or a is None or a.status!='approved' or a.approved_by!=ctx.actor_id or not a.expires_at or _aware(a.expires_at)<=now or db.scalar(select(ApprovalEffectRow.id).where(ApprovalEffectRow.approval_id==a.id)):raise WaveConflict('unused live module owner decision required')
        if db.execute(update(type(row)).where(type(row).id==row.id,type(row).state=='approved').values(state='applied')).rowcount!=1:raise WaveConflict('already applied')
        self.gate.consume_effect(a.id,module_id=14,action_type=action,payload=row.payload,user_id=ctx.tenant_id,effect_id=row.id,actor=ctx.actor_id,_session=db)
    def apply_review(self,ctx,id):
        with self.sessions.begin() as db:
            row=self._row(db,ctx,id,ReviewRow);source=db.get(SandboxWaveRow,row.payload['prior_wave_id']);p=self._project(db,source,True)
            wave=db.scalar(select(SandboxWaveRow).where(SandboxWaveRow.id==source.id).with_for_update().execution_options(populate_existing=True))
            wave,p,ev=self._review_source(db,ctx,wave.id,row.payload['selection'])
            if wave.digest!=row.payload['prior_digest'] or ev!=row.payload['evidence'] or p.revision!=row.payload['project_revision'] or p.plan!=row.payload['plan'] or p.budget!=row.payload['budget']:raise WaveConflict('review evidence changed')
            plan=json.loads(json.dumps(p.plan))
            for task in plan['tasks']:
                if task['id'] in row.payload['selection']:task['status']='completed' if row.payload['selection'][task['id']]['accept'] else 'blocked'
            if db.execute(update(ProjectRow).where(ProjectRow.pk==p.pk,ProjectRow.revision==row.payload['project_revision']).values(plan=plan,revision=p.revision+1)).rowcount!=1:raise WaveConflict('project changed')
            self._permit(db,ctx,row,REVIEW)
        return self.get(ctx,id)
    def _applied_review(self,db,ctx,id):
        row=self._row(db,ctx,id,ReviewRow)
        if row.state!='applied' or row.digest!=digest(row.payload):raise WaveConflict('applied review required')
        wave=self.waves._owned(db,row.payload['prior_wave_id'],ctx.tenant_id,ctx.actor_id)
        if evidence(db,wave)!=row.payload['evidence']:raise WaveConflict('review evidence changed')
        p=self._project(db,wave)
        plan=json.loads(json.dumps(row.payload['plan']))
        for task in plan['tasks']:
            if task['id'] in row.payload['selection']:task['status']='completed' if row.payload['selection'][task['id']]['accept'] else 'blocked'
        if p.revision!=row.payload['project_revision']+1 or p.plan!=plan or p.budget!=row.payload['budget']:raise WaveConflict('reviewed project changed')
        return row,wave,p
    def draft_next(self,ctx,review_id,request,artifact_inputs=None):
        with self.sessions() as db:
            review,wave,p=self._applied_review(db,ctx,review_id)
            check_ready(db,p)
            verify_artifact_inputs(db,wave,request,artifact_inputs or [])
            lineage={'artifact_inputs':artifact_inputs or [],'review_id':review.id,'review_digest':review.digest,'prior_wave_id':wave.id,'evidence':review.payload['evidence']}
        drafted=self.waves.draft(ctx.tenant_id,ctx.actor_id,p.id,request)
        with self.sessions.begin() as db:
            review,wave,p=self._applied_review(db,ctx,review_id);row=self.waves._owned(db,drafted['id'],ctx.tenant_id,ctx.actor_id)
            if row.state!='draft' or row.payload['project_revision']!=p.revision:raise WaveConflict('draft project changed')
            tasks={t['id']:t for t in p.plan['tasks']}
            if not any(tasks[id]['dependencies'] for id in row.payload['ready_task_ids']):raise WaveConflict('newly-ready dependent required')
            row.payload={**row.payload,'review_lineage':lineage};row.digest=digest(row.payload)
        return self.waves.get(ctx.tenant_id,ctx.actor_id,row.id)
    def _continuation_pair(self,db,ctx,review_id,new_id):
        review,prior,p=self._applied_review(db,ctx,review_id);new=self.waves._owned(db,new_id,ctx.tenant_id,ctx.actor_id)
        check_ready(db,p)
        if new.project_id!=p.id or new.state!='awaiting_approval' or not new.approval_id or new.claim_key or new.digest!=digest(new.payload) or new.payload['project_revision']!=p.revision or new.payload['plan']!=p.plan or new.payload['budget']!=p.budget:raise WaveConflict('new immutable reviewed draft required')
        if new.payload.get('review_lineage')!={'artifact_inputs':new.payload.get('review_lineage',{}).get('artifact_inputs',[]),'review_id':review.id,'review_digest':review.digest,'prior_wave_id':prior.id,'evidence':review.payload['evidence']}:raise WaveConflict('review lineage changed')
        from .sandbox_wave import WaveDraft
        verify_artifact_inputs(db,prior,WaveDraft.model_validate(new.payload['config']),new.payload['review_lineage']['artifact_inputs'])
        version,wid=current(db,prior)
        if wid!=prior.id:raise WaveConflict('prior version changed')
        return review,prior,new,p,version
    def propose_continuation(self,ctx,review_id,new_id):
        with self.sessions() as db:
            review,prior,new,p,version=self._continuation_pair(db,ctx,review_id,new_id)
            payload={'review_id':review.id,'review_digest':review.digest,'prior_wave_id':prior.id,'new_wave_id':new.id,'new_digest':new.digest,'project_revision':p.revision,'current_key_version':version,'evidence':review.payload['evidence'],'owner_actor':ctx.actor_id,'tenant_id':ctx.tenant_id}
        return self._submit(ctx,ContinuationRow,CONTINUE,payload)
    def apply_continuation(self,ctx,id):
        with self.sessions.begin() as db:
            row=self._row(db,ctx,id,ContinuationRow);source=db.get(SandboxWaveRow,row.payload['prior_wave_id']);self._project(db,source,True)
            db.scalar(select(SandboxWaveRow).where(SandboxWaveRow.id==source.id).with_for_update().execution_options(populate_existing=True))
            review,prior,new,p,version=self._continuation_pair(db,ctx,row.payload['review_id'],row.payload['new_wave_id'])
            if review.digest!=row.payload['review_digest'] or new.digest!=row.payload['new_digest'] or version!=row.payload['current_key_version'] or p.revision!=row.payload['project_revision']:raise WaveConflict('continuation changed')
            self._permit(db,ctx,row,CONTINUE)
            db.add(ContinuationKeyRow(id=str(uuid.uuid4()),project_key=digest({'tenant':ctx.tenant_id,'project':p.id}),version=version+1,prior_wave_id=prior.id,new_wave_id=new.id,owner_actor=ctx.actor_id,continuation_id=row.id,review_id=review.id,operation_type='continuation'))
        return self.get(ctx,id,ContinuationRow)

from sqlalchemy import Integer,UniqueConstraint
class ContinuationKeyRow(Base):
    __tablename__='m14_continuation_keys'
    __table_args__=(UniqueConstraint('project_key','version'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    project_key:Mapped[str]=mapped_column(String(64),index=True)
    version:Mapped[int]=mapped_column(Integer)
    prior_wave_id:Mapped[str]=mapped_column(String(36))
    new_wave_id:Mapped[str]=mapped_column(String(36),unique=True)
    owner_actor:Mapped[str]=mapped_column(String(120))
    continuation_id:Mapped[str]=mapped_column(String(36),unique=True)
    review_id:Mapped[str]=mapped_column(String(36),unique=True)
    operation_type:Mapped[str]=mapped_column(String(30))

def check_ready(db,project):
    from .runner import _ready
    from .schemas import ProjectPlan
    reviews=list(db.scalars(select(ReviewRow).where(ReviewRow.tenant_id==project.tenant_id,ReviewRow.state=='applied')))
    rejected={id for r in reviews if r.payload['prior_wave_id'] in set(db.scalars(select(SandboxWaveRow.id).where(SandboxWaveRow.project_id==project.id,SandboxWaveRow.tenant_id==project.tenant_id))) for id,d in r.payload['selection'].items() if not d['accept']}
    ready=_ready(ProjectPlan.model_validate(project.plan))
    if any(t.id in rejected for t in ready):raise WaveConflict('rejected ready task excluded; retry policy required')

def verify_artifact_inputs(db,prior,request,selections):
    import base64,hashlib
    from .sandbox_wave import SandboxWaveArtifactRow
    if not isinstance(selections,list) or len(selections)>100:raise WaveConflict('bounded explicit artifact selections required')
    names=set()
    for selection in selections:
        if not isinstance(selection,dict) or set(selection)!={'task_id','input_name','artifact_id','sha256'}:raise WaveConflict('explicit artifact selection required')
        key=(selection['task_id'],selection['input_name'])
        if key in names:raise WaveConflict('duplicate artifact input')
        names.add(key)
        artifact=db.get(SandboxWaveArtifactRow,selection['artifact_id'])
        if artifact is None or artifact.wave_id!=prior.id or artifact.sha256!=selection['sha256']:raise WaveConflict('artifact selection unavailable')
        raw=base64.b64decode(artifact.content_base64,validate=True)
        if hashlib.sha256(raw).hexdigest()!=artifact.sha256:raise WaveConflict('artifact selection corrupt')
        task=request.tasks.get(selection['task_id'])
        if task is None or task.inputs.get(selection['input_name'])!=base64.b64encode(raw).decode():raise WaveConflict('selected artifact input bytes mismatch')

def validate_continuation_claim(db,row,tenant,actor):
    key=db.scalar(select(ContinuationKeyRow).where(ContinuationKeyRow.new_wave_id==row.id))
    lineage=row.payload.get('review_lineage')
    if lineage is None:
        if key is not None:raise WaveConflict('continuation lineage missing')
        return
    if key is None:raise WaveConflict('separate continuation approval required')
    operation=db.get(ContinuationRow,key.continuation_id);review=db.get(ReviewRow,key.review_id)
    if operation is None or operation.state!='applied' or operation.actor_id!=actor or operation.tenant_id!=tenant or operation.digest!=digest(operation.payload) or operation.payload['new_digest']!=row.digest or review is None or review.state!='applied' or review.digest!=lineage['review_digest']:raise WaveConflict('continuation authority or lineage corrupt')
    prior=db.get(SandboxWaveRow,key.prior_wave_id)
    if evidence(db,prior)!=lineage['evidence']:raise WaveConflict('review evidence changed')
    from .sandbox_wave import WaveDraft
    verify_artifact_inputs(db,prior,WaveDraft.model_validate(row.payload['config']),lineage['artifact_inputs'])
