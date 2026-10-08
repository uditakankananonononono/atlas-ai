import pytest
from sqlalchemy import create_engine
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.auth.context import TenantContext,require_tenant
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.runtime_routes import router,get_runtime
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.persistence import DurableHTNPlanner
from app.modules.m20_general_cognitive_worker.schemas import HTNMethod,PlanNode,MethodSource

@pytest.fixture
def wired(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "review.db"}')
    repo=GCWRepository(engine,tenant_id='fixture');repo.create_schema();runtime=GCWRuntime(repo)
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_runtime]=lambda:runtime
    yield app,runtime,repo
    engine.dispose()


def proposal(runtime,proposer='author'):
    # JSON input establishes the desired new schema field before implementation.
    method=HTNMethod.model_validate({'name':'fixture','goal_pattern':'fixture','source':'learned','subtasks':[{'title':'fixture'}],'proposer_actor_id':proposer})
    runtime.planner.register_method(method)
    return runtime.planner.methods['fixture']

@pytest.mark.parametrize('actor,roles',[('member',[]),('author',['atlas-reviewer']),('author',['atlas-admin'])])
def test_unqualified_or_self_reviewer_cannot_activate(wired,actor,roles):
    app,runtime,repo=wired;method=proposal(runtime)
    app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture',actor,frozenset(roles))
    response=TestClient(app).post('/api/modules/20/runtime/methods/fixture/activate',json={'expected_hash':runtime.planner.method_review_hash(method)})
    assert response.status_code==403
    assert repo.list_methods()[0][1]=='proposed'


def test_independent_reviewer_receipt_survives_restart(wired):
    app,runtime,repo=wired;method=proposal(runtime)
    app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','reviewer',frozenset({'atlas-reviewer'}))
    reviewed=runtime.planner.method_review_hash(method)
    response=TestClient(app).post('/api/modules/20/runtime/methods/fixture/activate',json={'expected_hash':reviewed})
    assert response.status_code==200
    restored=DurableHTNPlanner.load(repo,require_review=True)
    receipt=restored.methods['fixture'].model_dump()['activation_review']
    assert receipt['actor_id']=='reviewer' and receipt['proposer_actor_id']=='author'
    assert receipt['reviewed_hash']==reviewed and receipt['reviewed_at']


def test_unknown_legacy_proposer_cannot_be_assumed_independent(wired):
    app,runtime,repo=wired;method=proposal(runtime,None)
    app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','reviewer',frozenset({'atlas-admin'}))
    response=TestClient(app).post('/api/modules/20/runtime/methods/fixture/activate',json={'expected_hash':runtime.planner.method_review_hash(method)})
    assert response.status_code==403 and repo.list_methods()[0][1]=='proposed'


def test_authenticated_task_creator_bound_before_planning_and_retained_after_restart(wired):
    app,runtime,repo=wired
    class Model:
        def decompose(self,goal,*,context=''):
            return [{'title':'fixture'}]
    runtime.planner.model=Model()
    app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','authenticated-author')
    response=TestClient(app).post('/api/modules/20/runtime/tasks',json={'goal':'novel fixture','run_immediately':False,'creator_actor_id':'spoofed'})
    assert response.status_code==201
    task=repo.load_task(response.json()['id'])
    assert task.creator_actor_id=='authenticated-author'
    restored=DurableHTNPlanner.load(repo,require_review=True)
    method=next(iter(restored.methods.values()))
    assert method.proposer_actor_id=='authenticated-author'
    with pytest.raises(PermissionError,match='own payload'):
        restored.activate_method(method.name,expected_hash=restored.method_review_hash(method),actor_id='authenticated-author',roles={'atlas-admin'})


def test_direct_activation_cannot_skip_identity_role_or_reviewed_hash(wired):
    _,runtime,repo=wired;method=proposal(runtime)
    reviewed=runtime.planner.method_review_hash(method)
    with pytest.raises(PermissionError,match='role'):
        runtime.activate_method(method.name,expected_hash=reviewed)
    with pytest.raises(PermissionError,match='role'):
        runtime.activate_method(method.name,expected_hash=reviewed,actor_id='reviewer',roles={'atlas-worker'})
    with pytest.raises(PermissionError,match='hash'):
        repo.set_method_status(method.id,'active',actor_id='reviewer',roles={'atlas-admin'})
    assert repo.list_methods()[0][1]=='proposed'


def test_review_receipt_excluded_from_content_hash_and_cleared_for_replacement(wired):
    app,runtime,repo=wired;method=proposal(runtime)
    reviewed=runtime.planner.method_review_hash(method)
    assert runtime.activate_method('fixture',expected_hash=reviewed,actor_id='reviewer',roles={'atlas-admin'})
    activated=runtime.planner.methods['fixture']
    assert runtime.planner.method_review_hash(activated)==reviewed
    replacement=activated.model_copy(deep=True)
    replacement.subtasks[0].title='replacement'
    replacement.proposer_actor_id='other-author'
    runtime.planner.register_method(replacement)
    restored=DurableHTNPlanner.load(repo,require_review=True)
    assert restored.method_status('fixture')=='proposed'
    assert restored.methods['fixture'].activation_review is None


def test_activation_publishes_committed_snapshot_without_racy_postcommit_read(wired,monkeypatch):
    _,runtime,repo=wired;method=proposal(runtime)
    reviewed=runtime.planner.method_review_hash(method)
    original=repo.set_method_status
    def commit_then_replace(*args,**kwargs):
        activated=original(*args,**kwargs)
        other=DurableHTNPlanner.load(repo,require_review=True)
        replacement=other.methods['fixture'].model_copy(deep=True)
        replacement.subtasks[0].title='unreviewed concurrent replacement'
        other.register_method(replacement)
        return activated
    monkeypatch.setattr(repo,'set_method_status',commit_then_replace)
    assert runtime.activate_method('fixture',expected_hash=reviewed,actor_id='reviewer',roles={'atlas-reviewer'})
    assert runtime.planner.methods['fixture'].subtasks[0].title=='fixture'
    assert repo.list_methods()[0][0].subtasks[0].title=='unreviewed concurrent replacement'
    assert repo.list_methods()[0][1]=='proposed'


def test_signed_production_roles_not_body_or_headers_establish_reviewer(wired,oidc_auth_headers,monkeypatch):
    from app.modules.m20_general_cognitive_worker import runtime_routes
    app,runtime,repo=wired
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    # Bind actual tenant resolver, not a dependency override of authorization.
    app.dependency_overrides.clear()
    monkeypatch.setattr(runtime_routes,'_runtimes',{'fixture':runtime})
    method=proposal(runtime)
    client=TestClient(app)
    path='/api/modules/20/runtime/methods/fixture/activate'
    body={'expected_hash':runtime.planner.method_review_hash(method),'actor_id':'reviewer','roles':['atlas-admin']}
    member=oidc_auth_headers('fixture','member')
    member.update({'X-Atlas-Actor':'reviewer','X-Atlas-Roles':'atlas-admin'})
    assert client.post(path,json=body,headers=member).status_code==403
    assert client.post(path,json=body,headers=oidc_auth_headers('fixture','author',['atlas-admin'])).status_code==403
    assert client.post(path,json=body,headers=oidc_auth_headers('fixture','independent',['atlas-reviewer'])).status_code==200
    assert repo.list_methods()[0][0].activation_review['actor_id']=='independent'
