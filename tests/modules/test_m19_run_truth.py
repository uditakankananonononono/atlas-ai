"""Local transport tests use controlled HTTP responses, not real model inference."""
import asyncio,json,subprocess,os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
import httpx,pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.providers import ProviderError
from app.modules.m19_idea_incubator import local_provider, routes
from app.modules.m19_idea_incubator.run_repository import RunRepository,RunConflict
from app.modules.m19_idea_incubator.service import Service
from app.modules.m19_idea_incubator.schemas import IntakeIn,PreviewIn,PackageIn
CANVAS={'problem':['x'],'customer_segments':['y'],'unique_value_proposition':'z','solution':['s'],'channels':[],'revenue_streams':[],'cost_structure':[],'key_metrics':[],'riskiest_assumptions':['demand']}
class Approvals:
 def __init__(self):self.items=[]
 def put(self,item):self.items.append(item);return item
@pytest.fixture
def repo(tmp_path):
 path=tmp_path/'runs.sqlite';sf=sessionmaker(bind=create_engine(f'sqlite:///{path}',connect_args={'check_same_thread':False}),expire_on_commit=False)
 return RunRepository('tenant-a',sf)
def service(repo,gen=None,approval=None):
 async def generate(*a):return 'controlled-test',json.dumps(CANVAS)
 return Service(generate=gen or generate,approval_store=approval or Approvals(),repository=repo)
@pytest.mark.asyncio
async def test_truth_restart_and_subprocess(repo):
 s=service(repo);run=await s.intake(IntakeIn(one_liner='new idea'),'same')
 assert run.state=='awaiting_evidence' and run.stage=='intake' and run.execution_status=='not_executed'
 assert not run.gates[0].proceed and 'landscape' in run.unavailable_stages
 r2=RunRepository('tenant-a',repo.sessions);assert r2.get(run.id)==run
 code="from sqlalchemy import create_engine;from sqlalchemy.orm import sessionmaker;from app.modules.m19_idea_incubator.run_repository import RunRepository;print(RunRepository('tenant-a',sessionmaker(bind=create_engine(%r))).get(%r).state)"%(str(repo.sessions.kw['bind'].url),run.id)
 out=subprocess.check_output([__import__('sys').executable,'-c',code],env={**os.environ,'PYTHONPATH':'backend'},text=True)
 assert out.strip()=='awaiting_evidence'
 assert (await s.intake(IntakeIn(one_liner='new idea'),'same')).id==run.id
 with pytest.raises(RunConflict):await s.intake(IntakeIn(one_liner='other idea'),'same')
 with pytest.raises(KeyError):RunRepository('tenant-b',repo.sessions).get(run.id)
 assert [e['kind'] for e in r2.events(run.id)]==['intake_requested','canvas_generated']
@pytest.mark.asyncio
async def test_failure_persisted_no_fake_canvas_or_retry(repo):
 calls=[]
 async def fail(*a):calls.append(1);raise ProviderError('unavailable')
 s=service(repo,fail)
 with pytest.raises(ProviderError):await s.intake(IntakeIn(one_liner='new idea'),'fail')
 with pytest.raises(ProviderError):await s.intake(IntakeIn(one_liner='new idea'),'fail')
 run,_=repo.begin('fail',__import__('app.modules.m19_idea_incubator.service',fromlist=['digest']).digest(IntakeIn(one_liner='new idea').model_dump(mode='json')),25)
 assert run.canvas is None and run.state=='unavailable' and len(calls)==1
@pytest.mark.asyncio
async def test_invalid_output_is_persisted(repo):
 async def invalid(*a):return 'test','not JSON'
 with pytest.raises(ProviderError):await service(repo,invalid).intake(IntakeIn(one_liner='new idea'),'invalid')
def test_parallel_claims_and_compare_swap(repo):
 def claim(_):return RunRepository('tenant-a',repo.sessions).begin('parallel','a'*64,0)
 with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(claim,range(16)))
 assert sum(new for _,new in results)==1 and len({r.id for r,_ in results})==1
 run=results[0][0];first=repo.save(run,1,'updated')
 with pytest.raises(RunConflict):repo.save(run,1,'lost_update')
 assert len(repo.events(run.id))==2
 other=RunRepository('tenant-b',repo.sessions).begin('parallel','b'*64,0)[0]
 assert other.id!=run.id
@pytest.mark.asyncio
async def test_inflight_intake_single_generator(repo):
 calls=[];started=asyncio.Event();release=asyncio.Event()
 async def slow(*a):calls.append(1);started.set();await release.wait();return 'test',json.dumps(CANVAS)
 s=service(repo,slow);task=asyncio.create_task(s.intake(IntakeIn(one_liner='new idea'),'busy'))
 await started.wait();second=await service(repo,slow).intake(IntakeIn(one_liner='new idea'),'busy')
 assert second.state=='intake_generating' and second.canvas is None
 release.set();first=await task;assert first.id==second.id and len(calls)==1
def test_expired_lease_becomes_interrupted(repo):
 run,_=repo.begin('expired','a'*64,0);run.lease_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
 repo.save(run,1,'expiry_fixture');assert repo.get(run.id).state=='interrupted'
 assert repo.get(run.id).canvas is None and repo.events(run.id)[-1]['kind']=='operation_interrupted'
@pytest.mark.asyncio
async def test_preview_review_replay_and_concurrency(repo):
 approvals=Approvals();s=service(repo,approval=approvals);run=await s.intake(IntakeIn(one_liner='new idea'))
 def preview(_):
  try:return s.request_preview(run.id,PreviewIn(artifacts=['caller-ref'],estimated_cost=0))
  except RunConflict:return None
 with ThreadPoolExecutor(max_workers=8) as pool:items=list(pool.map(preview,range(8)))
 assert len(approvals.items)==1
 assert s.request_preview(run.id,PreviewIn(artifacts=['caller-ref'],estimated_cost=0)).id==approvals.items[0].id
 assert s.get(run.id).stage=='intake' and s.get(run.id).execution_status=='not_executed'
 assert approvals.items[0].payload['tenant_id']=='tenant-a' and not approvals.items[0].payload['executor_available']
 with pytest.raises(RunConflict):s.request_preview(run.id,PreviewIn(artifacts=['different'],estimated_cost=0))
@pytest.mark.asyncio
async def test_package_evidence_persistence_and_no_pdf(repo):
 calls=[]
 async def gen(*a):
  calls.append(1)
  if len(calls)==1:return 'test',json.dumps(CANVAS)
  return 'test',json.dumps({'executive_summary':'draft','recommendation':'test','recommendation_confidence':0,'market_claims':[],'technical_feasibility':[],'prototype_artifacts':['ref'],'unresolved_risks':['unknown'],'next_experiments':[],'pdf_rendered':True,'format':'pdf'})
 s=service(repo,gen);run=await s.intake(IntakeIn(one_liner='new idea'));req=PackageIn(run_id=run.id,evidence=[{'source':'caller'}],artifacts=['ref'])
 result=await s.package(req);assert result.format=='json' and not result.pdf_rendered and result.execution_status=='draft_unverified'
 assert await s.package(req)==result and len(calls)==2
 assert repo.events(run.id)[-2]['evidence']['supplied_evidence']==[{'source':'caller'}]
@pytest.mark.asyncio
async def test_transport_no_paid_fallback(monkeypatch):
 monkeypatch.delenv('ATLAS_M19_MODEL',raising=False);monkeypatch.delenv('ATLAS_OLLAMA_MODEL',raising=False)
 with pytest.raises(ProviderError):await local_provider.generate_local('prompt')
 with pytest.raises(ProviderError):await local_provider.generate_local('prompt','openai','model')
 monkeypatch.setenv('ATLAS_M19_MODEL','installed-test');monkeypatch.setenv('ATLAS_M19_OLLAMA_URL','https://evil.example')
 with pytest.raises(ProviderError):await local_provider.generate_local('prompt')
 monkeypatch.setenv('ATLAS_M19_OLLAMA_URL','http://127.0.0.1:11434')
 seen=[];real=httpx.AsyncClient
 def handler(req):seen.append(req);return httpx.Response(200,json={'message':{'content':json.dumps(CANVAS)}})
 monkeypatch.setattr(local_provider.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
 model,text=await local_provider.generate_local('prompt');assert model=='installed-test' and json.loads(text)==CANVAS
 assert seen[0].url.host=='127.0.0.1' and json.loads(seen[0].content)['format']=='json'
@pytest.mark.asyncio
async def test_route_default_missing_model_returns_503_and_is_tenant_scoped(repo,monkeypatch):
 monkeypatch.delenv('ATLAS_M19_MODEL',raising=False);monkeypatch.delenv('ATLAS_OLLAMA_MODEL',raising=False)
 monkeypatch.setattr(routes,'RunRepository',lambda tenant:RunRepository(tenant,repo.sessions))
 app=FastAPI();app.include_router(routes.router);c=TestClient(app)
 r=c.post('/idea-incubator/ideas',json={'one_liner':'new idea'},headers={'X-Atlas-Tenant':'tenant-a','Idempotency-Key':'default'})
 assert r.status_code==503 and 'run_id=' in r.json()['detail']
 rid=r.json()['detail'].split('run_id=')[1]
 assert c.get('/idea-incubator/ideas/'+rid,headers={'X-Atlas-Tenant':'tenant-b'}).status_code==404
 assert c.get('/idea-incubator/ideas/'+rid,headers={'X-Atlas-Tenant':'tenant-a'}).json()['canvas'] is None
@pytest.mark.asyncio
async def test_package_rejects_fabricated_preview(repo):
 n=[]
 async def gen(*a):
  n.append(1)
  if len(n)==1:return 'test',json.dumps(CANVAS)
  return 'test',json.dumps({'executive_summary':'draft','recommendation':'test','recommendation_confidence':0,'market_claims':[],'technical_feasibility':[],'prototype_artifacts':[],'prototype_preview':'https://invented.invalid','unresolved_risks':[],'next_experiments':[]})
 s=service(repo,gen);run=await s.intake(IntakeIn(one_liner='new idea'))
 with pytest.raises(ProviderError):await s.package(PackageIn(run_id=run.id))
 assert repo.get(run.id).state=='package_failed' and repo.get(run.id).package is None
 with pytest.raises(RunConflict):await s.package(PackageIn(run_id=run.id))
 assert len(n)==2
@pytest.mark.asyncio
async def test_uncertain_approval_never_resubmitted(repo):
 class Broken:
  def put(self,item):raise RuntimeError('uncertain store commit')
 s=service(repo,approval=Broken());run=await s.intake(IntakeIn(one_liner='new idea'))
 with pytest.raises(RuntimeError):s.request_preview(run.id,PreviewIn(artifacts=[],estimated_cost=0))
 assert repo.get(run.id).state=='approval_reconciliation_required'
 with pytest.raises(RunConflict):s.request_preview(run.id,PreviewIn(artifacts=[],estimated_cost=0))
def test_migration_roundtrip(tmp_path):
 import importlib.util
 from alembic.migration import MigrationContext
 from alembic.operations import Operations
 from sqlalchemy import inspect
 spec=importlib.util.spec_from_file_location('migration','migrations/versions/20261003_m19_run_truth.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 engine=create_engine('sqlite:///'+str(tmp_path/'migrate.sqlite'))
 with engine.begin() as connection:
  m.op=Operations(MigrationContext.configure(connection));m.upgrade()
  assert set(inspect(connection).get_table_names())=={'m19_runs','m19_run_events'}
  m.downgrade();assert inspect(connection).get_table_names()==[]
@pytest.mark.asyncio
async def test_production_route_uses_verified_tenant(repo,monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.delenv('ATLAS_M19_MODEL',raising=False);monkeypatch.delenv('ATLAS_OLLAMA_MODEL',raising=False)
 monkeypatch.setattr(routes,'RunRepository',lambda tenant:RunRepository(tenant,repo.sessions))
 app=FastAPI();app.include_router(routes.router);c=TestClient(app)
 assert c.post('/idea-incubator/ideas',json={'one_liner':'new idea'},headers={'X-Atlas-Tenant':'tenant-a'}).status_code==401
 h=oidc_auth_headers('tenant-a');h['X-Atlas-Tenant']='tenant-b'
 r=c.post('/idea-incubator/ideas',json={'one_liner':'new idea'},headers=h);assert r.status_code==503
 rid=r.json()['detail'].split('run_id=')[1]
 assert c.get('/idea-incubator/ideas/'+rid,headers=oidc_auth_headers('tenant-a')).status_code==200
 assert c.get('/idea-incubator/ideas/'+rid,headers=oidc_auth_headers('tenant-b')).status_code==404
def test_parallel_processes_single_claim(repo):
 code="from sqlalchemy import create_engine;from sqlalchemy.orm import sessionmaker;from app.modules.m19_idea_incubator.run_repository import RunRepository;r,new=RunRepository('tenant-a',sessionmaker(bind=create_engine(%r))).begin('processes','c'*64,0);print(r.id,int(new))"%str(repo.sessions.kw['bind'].url)
 def claim(_):return subprocess.check_output([__import__('sys').executable,'-c',code],env={**os.environ,'PYTHONPATH':'backend'},text=True).strip().split()
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(claim,range(4)))
 assert len({rid for rid,new in results})==1 and sum(int(new) for rid,new in results)==1
@pytest.mark.asyncio
async def test_real_loopback_unavailable_no_model_inference(monkeypatch):
 import socket
 with socket.socket() as sock:
  sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 monkeypatch.setenv('ATLAS_M19_OLLAMA_URL',f'http://127.0.0.1:{port}')
 monkeypatch.setenv('ATLAS_M19_MODEL','test-not-installed')
 with pytest.raises(ProviderError,match='no fallback used'):await local_provider.generate_local('this is a transport failure test, not inference')
