"""Owner review, separate continuation and execute permits, durable DAG progress."""
import asyncio
import pytest
from sqlalchemy import select
from app.auth.context import TenantContext
from app.core.models import ApprovalStatus
from app.modules.m14_project_builder.reviewed_continuation import ReviewedContinuationService,ReviewRow,ContinuationRow,ContinuationKeyRow
from app.modules.m14_project_builder.sandbox_wave import SandboxWaveRow,WaveConflict,WaveForbidden
from app.modules.m14_project_builder.sql_repository import ProjectRow
from app.modules.m14_project_builder.wave_supersede import WaveKeyVersionRow
from app.modules.m00_approval_center.service import ApprovalEffectRow
from test_m14_sandbox_wave import env,approved,request
OWNER=TenantContext('t','owner',frozenset())
OTHER=TenantContext('t','other',frozenset({'atlas-admin'}))


def completed(svc):
    prior,_=approved(svc);asyncio.run(svc.execute('t','owner',prior));return prior


def test_review_next_wave_three_separate_approvals_actual_dependency(env):
    waves,sessions,_=env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    review=svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'output reviewed'}})
    with pytest.raises(WaveForbidden):svc.decide_review(OTHER,review['id'],'approved')
    with pytest.raises(WaveConflict):svc.apply_review(OWNER,review['id'])
    svc.decide_review(OWNER,review['id'],'approved');svc.apply_review(OWNER,review['id'])
    with sessions() as db:
        project=db.scalar(select(ProjectRow));assert project.revision==2
        assert project.plan['tasks'][0]['status']=='completed'
        assert project.plan['tasks'][1]['status']=='blocked'
    config=request();config.tasks['b'].code="open('/output/result.txt','w').write('dependent executed')"
    new=svc.draft_next(OWNER,review['id'],config)
    assert new['payload']['ready_task_ids']==['b'] and new['payload']['review_lineage']['review_id']==review['id']
    waves.submit('t','owner',new['id'])
    continuation=svc.propose_continuation(OWNER,review['id'],new['id'])
    with pytest.raises(WaveConflict):waves.claim('t','owner',new['id'])
    svc.decide_continuation(OWNER,continuation['id'],'approved');svc.apply_continuation(OWNER,continuation['id'])
    with pytest.raises(WaveConflict):waves.claim('t','owner',new['id'])
    waves.gate.decide(waves.get('t','owner',new['id'])['approval_id'],ApprovalStatus.APPROVED,decided_by='owner')
    result=asyncio.run(waves.execute('t','owner',new['id']))
    assert [t['task_id'] for t in result['result']['tasks']]==['b']
    assert not result['result']['independent_quality_verified'] and not result['result']['all_dag_completed']
    with sessions() as db:
        key=db.scalar(select(ContinuationKeyRow));assert key.operation_type=='continuation' and key.owner_actor=='owner'
        assert len(list(db.scalars(select(ApprovalEffectRow))))==4
        assert db.get(SandboxWaveRow,prior).claim_key is not None
    with pytest.raises(WaveConflict):svc.apply_review(OWNER,review['id'])
    with pytest.raises(WaveConflict):svc.apply_continuation(OWNER,continuation['id'])


def test_review_unknown_failed_and_incomplete_selection_refused(env):
    waves,_,_=env;prior,_=approved(waves);waves.claim('t','owner',prior);svc=ReviewedContinuationService(waves)
    with pytest.raises(WaveConflict):svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'guess'}})


def test_rejection_stays_blocked_and_excluded_at_draft_and_claim(env):
    waves,sessions,_=env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    review=svc.propose_review(OWNER,prior,{'a':{'accept':False,'reason':'not accepted'}});svc.decide_review(OWNER,review['id'],'approved');svc.apply_review(OWNER,review['id'])
    with sessions() as db:assert db.scalar(select(ProjectRow)).plan['tasks'][0]['status']=='blocked'
    with pytest.raises(WaveConflict,match='rejected'):svc.draft_next(OWNER,review['id'],request())
    with pytest.raises(WaveConflict,match='rejected'):waves.draft('t','owner','p',request())


def test_review_selection_complete_and_raw_decide_cannot_apply(env):
    waves,_,_=env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    with pytest.raises(WaveConflict,match='complete'):svc.propose_review(OWNER,prior,{})
    review=svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'checked'}})
    waves.gate.decide(review['approval_id'],ApprovalStatus.APPROVED,decided_by='owner')
    with pytest.raises(WaveConflict,match='module owner'):svc.apply_review(OWNER,review['id'])

from test_m14_wave_supersede import pg_env

def test_pg_review_apply_rollback_and_concurrent_once(pg_env,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy.exc import IntegrityError
    waves,sessions,_=pg_env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    r=svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'reviewed'}});svc.decide_review(OWNER,r['id'],'approved')
    original=waves.gate.consume_effect
    def fault(*a,**kw):original(*a,**kw);kw['_session'].flush();raise RuntimeError('fault')
    monkeypatch.setattr(waves.gate,'consume_effect',fault)
    with pytest.raises(RuntimeError):svc.apply_review(OWNER,r['id'])
    with sessions() as db:assert db.scalar(select(ProjectRow)).revision==1 and db.get(ReviewRow,r['id']).state=='approved'
    monkeypatch.setattr(waves.gate,'consume_effect',original)
    def apply():
        try:svc.apply_review(OWNER,r['id']);return 'applied'
        except (WaveConflict,IntegrityError):return 'refused'
    with ThreadPoolExecutor(2) as pool:assert sorted(pool.map(lambda _:apply(),range(2)))==['applied','refused']
    with sessions() as db:assert db.scalar(select(ProjectRow)).revision==2


def test_explicit_prior_artifact_selection_bytes_and_hash(env):
    import base64
    waves,_,_=env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    r=svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'reviewed'}});svc.decide_review(OWNER,r['id'],'approved');svc.apply_review(OWNER,r['id'])
    a=waves.artifacts('t','owner',prior)[0];config=request();config.tasks['b'].inputs={'prior.txt':base64.b64encode(b'hello').decode()}
    sel=[{'task_id':'b','input_name':'prior.txt','artifact_id':a['id'],'sha256':a['sha256']}]
    new=svc.draft_next(OWNER,r['id'],config,sel);assert new['payload']['review_lineage']['artifact_inputs']==sel
    config.tasks['b'].inputs['prior.txt']=base64.b64encode(b'changed').decode()
    with pytest.raises(WaveConflict,match='bytes mismatch'):svc.draft_next(OWNER,r['id'],config,sel)


def test_actual_second_os_process_executes_approved_dependent(env):
    import subprocess,os,json,sys
    waves,sessions,root=env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    r=svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'reviewed'}});svc.decide_review(OWNER,r['id'],'approved');svc.apply_review(OWNER,r['id'])
    config=request();config.tasks['b'].code="open('/output/result.txt','w').write('second process')"
    new=svc.draft_next(OWNER,r['id'],config);waves.submit('t','owner',new['id']);c=svc.propose_continuation(OWNER,r['id'],new['id']);svc.decide_continuation(OWNER,c['id'],'approved');svc.apply_continuation(OWNER,c['id'])
    waves.gate.decide(waves.get('t','owner',new['id'])['approval_id'],ApprovalStatus.APPROVED,decided_by='owner')
    code="""import sys,asyncio,json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m14_project_builder.sandbox_wave import SandboxWaveService
from app.modules.m14_project_builder.reviewed_continuation import ReviewedContinuationService
engine=create_engine(sys.argv[1]);sessions=sessionmaker(engine,expire_on_commit=False)
svc=SandboxWaveService(sessions,sys.argv[2]);result=asyncio.run(svc.execute('t','owner',sys.argv[3]));print(json.dumps(result));engine.dispose()
"""
    run=subprocess.run([sys.executable,'-c',code,str(sessions.kw['bind'].url),str(root),new['id']],capture_output=True,text=True,timeout=30,env={**os.environ,'PYTHONPATH':os.environ['PYTHONPATH']})
    assert run.returncode==0,run.stderr
    result=json.loads(run.stdout);assert result['result']['tasks'][0]['task_id']=='b'
    assert waves.get('t','owner',new['id'])['state']=='awaiting_review'
    data,_,_=waves.artifact('t','owner',new['id'],waves.artifacts('t','owner',new['id'])[0]['id']);assert data==b'second process'


def test_oidc_owner_review_http_and_generic_decision_denial(env,oidc_auth_headers,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m14_project_builder import routes
    from app.modules.m00_approval_center import routes as m00
    waves,_,_=env;prior=completed(waves);app=FastAPI();app.include_router(routes.router);app.include_router(m00.router)
    app.dependency_overrides[routes.get_wave_service]=lambda:waves;app.dependency_overrides[m00.get_service]=lambda:waves.gate
    monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0')
    with TestClient(app) as client:
        base='/project-builder';headers=oidc_auth_headers('t','owner');other=oidc_auth_headers('t','other',roles=['atlas-admin'])
        body={'selection':{'a':{'accept':True,'reason':'read output'}}}
        assert client.post(base+'/sandbox-waves/'+prior+'/reviews',json=body).status_code==401
        assert client.post(base+'/sandbox-waves/'+prior+'/reviews',headers=other,json=body).status_code==403
        r=client.post(base+'/sandbox-waves/'+prior+'/reviews',headers=headers,json=body);assert r.status_code==202
        row=r.json();id=row['id']
        assert client.post('/approval-center/requests/'+row['approval_id']+'/decision',headers=headers,json={'decision':'approved','decided_by':'owner'}).status_code==403
        assert client.post(base+'/wave-reviews/'+id+'/decision',headers=other,json={'decision':'approved'}).status_code==403
        assert client.post(base+'/wave-reviews/'+id+'/decision',headers=headers,json={'decision':'approved'}).status_code==200
        assert client.post(base+'/wave-reviews/'+id+'/apply',headers=headers).status_code==200
        config=request();config.tasks['b'].code="open('/output/result.txt','w').write('http')"
        new=client.post(base+'/wave-reviews/'+id+'/next-wave',headers=headers,json={'config':config.model_dump(mode='json')});assert new.status_code==201,new.text
        nid=new.json()['id'];assert client.post(base+'/sandbox-waves/'+nid+'/submit',headers=headers).status_code==202
        c=client.post(base+'/wave-reviews/'+id+'/continuations',headers=headers,json={'new_wave_id':nid});assert c.status_code==202
        cid=c.json()['id']
        assert client.post('/approval-center/requests/'+c.json()['approval_id']+'/decision',headers=headers,json={'decision':'approved','decided_by':'owner'}).status_code==403
        assert client.post(base+'/wave-continuations/'+cid+'/decision',headers=headers,json={'decision':'approved'}).status_code==200
        assert client.post(base+'/wave-continuations/'+cid+'/apply',headers=headers).status_code==200
        assert client.post(base+'/sandbox-waves/'+nid+'/execute',headers=headers).status_code==409
        waves.gate.decide(new.json().get('approval_id') or waves.get('t','owner',nid)['approval_id'],ApprovalStatus.APPROVED,decided_by='owner')
        assert client.post(base+'/sandbox-waves/'+nid+'/execute',headers=headers).status_code==200

@pytest.mark.parametrize('fault',['project','artifact','expiry','denial','failed','timeout','exit','raw'])
def test_review_fail_closed_drift_and_success_fields(env,fault):
    from datetime import timedelta
    from app.modules.m14_project_builder.sandbox_wave import SandboxWaveTaskRow,SandboxWaveArtifactRow
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    waves,sessions,_=env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    if fault in ('failed','timeout','exit'):
        with sessions.begin() as db:
            task=db.scalar(select(SandboxWaveTaskRow));receipt={**task.receipt}
            if fault=='failed':receipt['execution_state']='failed'
            if fault=='timeout':receipt['timed_out']=True
            if fault=='exit':receipt['exit_code']=1
            task.receipt=receipt;wave=db.get(SandboxWaveRow,prior);wave.result={**wave.result,'tasks':[receipt]}
        with pytest.raises(WaveConflict,match='successful'):svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'guess'}})
        return
    r=svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'reviewed'}})
    if fault=='raw':waves.gate.decide(r['approval_id'],ApprovalStatus.APPROVED,decided_by='owner')
    else:svc.decide_review(OWNER,r['id'],'denied' if fault=='denial' else 'approved')
    with sessions.begin() as db:
        if fault=='project':db.scalar(select(ProjectRow)).revision+=1
        if fault=='artifact':db.scalar(select(SandboxWaveArtifactRow)).content_base64='Yg=='
        if fault=='expiry':db.get(ApprovalRequestRow,r['approval_id']).expires_at=waves.gate._clock()-timedelta(seconds=1)
    with pytest.raises(WaveConflict):svc.apply_review(OWNER,r['id'])
    with sessions() as db:assert db.scalar(select(ProjectRow)).plan['tasks'][0]['status']!='completed'


def test_continuation_pg_concurrent_apply_rollback_and_sibling(pg_env,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy.exc import IntegrityError
    waves,sessions,_=pg_env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    r=svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'read'}});svc.decide_review(OWNER,r['id'],'approved');svc.apply_review(OWNER,r['id'])
    config=request();config.tasks['b'].code="open('/output/result.txt','w').write('next')"
    new=svc.draft_next(OWNER,r['id'],config);sibling=svc.draft_next(OWNER,r['id'],config)
    for n in (new,sibling):
        wave=waves.submit('t','owner',n['id']);waves.gate.decide(wave['approval_id'],ApprovalStatus.APPROVED,decided_by='owner')
    c=svc.propose_continuation(OWNER,r['id'],new['id']);svc.decide_continuation(OWNER,c['id'],'approved')
    original=waves.gate.consume_effect
    def fault(*a,**kw):original(*a,**kw);kw['_session'].flush();raise RuntimeError('fault')
    monkeypatch.setattr(waves.gate,'consume_effect',fault)
    with pytest.raises(RuntimeError):svc.apply_continuation(OWNER,c['id'])
    with sessions() as db:assert not db.scalar(select(ContinuationKeyRow)) and db.get(ContinuationRow,c['id']).state=='approved'
    monkeypatch.setattr(waves.gate,'consume_effect',original)
    def apply():
        try:svc.apply_continuation(OWNER,c['id']);return 'applied'
        except (WaveConflict,IntegrityError):return 'refused'
    with ThreadPoolExecutor(2) as pool:assert sorted(pool.map(lambda _:apply(),range(2)))==['applied','refused']
    with pytest.raises(WaveConflict):waves.claim('t','owner',sibling['id'])
    assert asyncio.run(waves.execute('t','owner',new['id']))['result']['tasks'][0]['task_id']=='b'


def test_rejected_task_claim_guard_even_if_draft_guard_bypassed(env,monkeypatch):
    import app.modules.m14_project_builder.reviewed_continuation as module
    waves,_,_=env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    r=svc.propose_review(OWNER,prior,{'a':{'accept':False,'reason':'reject'}});svc.decide_review(OWNER,r['id'],'approved');svc.apply_review(OWNER,r['id'])
    original=module.check_ready;monkeypatch.setattr(module,'check_ready',lambda *a:None)
    new=waves.draft('t','owner','p',request());s=waves.submit('t','owner',new['id']);waves.gate.decide(s['approval_id'],ApprovalStatus.APPROVED,decided_by='owner')
    monkeypatch.setattr(module,'check_ready',original)
    with pytest.raises(WaveConflict,match='rejected'):waves.claim('t','owner',new['id'])


def test_review_sqlite_transaction_rollback(env,monkeypatch):
    waves,sessions,_=env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    r=svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'reviewed'}});svc.decide_review(OWNER,r['id'],'approved')
    original=waves.gate.consume_effect
    def fault(*a,**kw):original(*a,**kw);kw['_session'].flush();raise RuntimeError('rollback')
    monkeypatch.setattr(waves.gate,'consume_effect',fault)
    with pytest.raises(RuntimeError):svc.apply_review(OWNER,r['id'])
    with sessions() as db:
        assert db.scalar(select(ProjectRow)).revision==1
        assert db.get(ReviewRow,r['id']).state=='approved'
        assert not db.scalar(select(ApprovalEffectRow).where(ApprovalEffectRow.approval_id==r['approval_id']))


def test_next_wave_requires_newly_ready_dependent(env):
    from app.modules.m14_project_builder.sandbox_wave import digest
    waves,sessions,_=env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    r=svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'checked'}});svc.decide_review(OWNER,r['id'],'approved');svc.apply_review(OWNER,r['id'])
    # Seed a consistent reviewed plan with a new independent root rather than a dependent.
    with sessions.begin() as db:
        review=db.get(ReviewRow,r['id']);plan={**review.payload['plan'],'tasks':[dict(t) for t in review.payload['plan']['tasks']]}
        plan['tasks'][1]['dependencies']=[]
        review.payload={**review.payload,'plan':plan};review.digest=digest(review.payload)
        reviewed={**plan,'tasks':[dict(t) for t in plan['tasks']]};reviewed['tasks'][0]['status']='completed';db.scalar(select(ProjectRow)).plan=reviewed
    with pytest.raises(WaveConflict,match='newly-ready dependent'):svc.draft_next(OWNER,r['id'],request())


def test_apply_review_payload_evidence_and_digest_guard_independently(env):
    from app.modules.m14_project_builder.sandbox_wave import digest
    waves,sessions,_=env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    r=svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'read'}});svc.decide_review(OWNER,r['id'],'approved')
    with sessions.begin() as db:
        review=db.get(ReviewRow,r['id']);review.payload={**review.payload,'prior_digest':'0'*64,'evidence':{'classification':'verified S6','sha256':'1'*64}};review.digest=digest(review.payload)
        from app.modules.m00_approval_center.service import ApprovalRequestRow
        db.get(ApprovalRequestRow,review.approval_id).payload=review.payload
    with pytest.raises(WaveConflict,match='review evidence changed'):svc.apply_review(OWNER,r['id'])


def test_owner_decision_expired_while_all_other_pending_guards_match(env):
    from datetime import timedelta
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    waves,sessions,_=env;prior=completed(waves);svc=ReviewedContinuationService(waves)
    r=svc.propose_review(OWNER,prior,{'a':{'accept':True,'reason':'checked'}})
    with sessions.begin() as db:db.get(ApprovalRequestRow,r['approval_id']).expires_at=waves.gate._clock()-timedelta(seconds=1)
    with pytest.raises(WaveConflict,match='matching live owner request'):svc.decide_review(OWNER,r['id'],'approved')
    with sessions() as db:assert db.get(ReviewRow,r['id']).state=='awaiting_approval'
