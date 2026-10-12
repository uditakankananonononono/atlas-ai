from datetime import date,datetime,timezone
import pytest
from app.modules.m10_email_assistant.classifier import RuleBasedClassifier,ClassifierInput
from app.modules.m11_calendar_intelligence.solver import BuiltInSolver,TaskSpec,SchedulingPrefs,Window
from app.modules.m12_ai_research_lab.router import ModelRouter,NoEligibleModel
from app.modules.m12_ai_research_lab.models import ModelCapability,RouteRequest,TaskType
D=date(2026,10,12)
def dt(h,m=0):return datetime(2026,10,12,h,m,tzinfo=timezone.utc)
def prefs():return SchedulingPrefs(working_hours={0:[Window(540,600)]},energy_curve={9:3})
def test_m10_action_precedes_academic_reply_and_newsletter():
 c=RuleBasedClassifier()
 assert c.classify(ClassifierInput('Re: question','prof@uni.edu','please reply')).category.value=='action_required'
 assert c.classify(ClassifierInput('Please review','a@b.com','',labels=['CATEGORY_UPDATES'],headers={'List-Unsubscribe':'x'})).category.value=='action_required'
def test_m11_recovers_feasible_order():
 p=BuiltInSolver().solve([TaskSpec('long','long',45,dt(10),priority=5),TaskSpec('early','early',15,dt(9,15),priority=1)],[],prefs(),D,days=1)
 assert {x.task_id:(x.start,x.end) for x in p}=={'early':(dt(9),dt(9,15)),'long':(dt(9,15),dt(10))}
def test_m11_split_prep_stays_inside_working_hours():
 p=BuiltInSolver().solve([TaskSpec('split','split',30,dt(10),prep_minutes=30,splittable=True,min_block_minutes=15)],[],prefs(),D,days=1)
 assert all(x.start>=dt(9) and x.end<=dt(10) for x in p)
 assert next(x for x in p if x.kind=='prep').end==min(x.start for x in p if x.kind=='task')
def test_m12_hard_latency_rejects_slow_only_model():
 m=ModelCapability('slow',frozenset({TaskType.RESEARCH}),4000,0,90000,.9)
 with pytest.raises(NoEligibleModel):ModelRouter([m]).route(RouteRequest(TaskType.RESEARCH,100,1,100,'t'))
def test_m09_route_wires_real_adapters_without_fake_vectors(monkeypatch):
 from types import SimpleNamespace
 from app.modules.m09_knowledge_workspace import routes,inference
 class Backend:
  def embed(self, texts):return [[1.,0.] for t in texts]
 nlp=lambda text:SimpleNamespace(ents=[SimpleNamespace(text='Atlas',label_='ORG')])
 engine=inference.GraphInference(Backend(),nlp)
 monkeypatch.setattr(inference,'configured_inference',lambda:engine)
 monkeypatch.setattr(routes,'SqlGraphRepository',lambda *a:object())
 svc=routes.get_service(SimpleNamespace(tenant_id='t',actor_id='u'))
 assert svc.embed('Atlas')==[1.,0.]
 assert svc.extract_entities('Atlas')[0]['text']=='Atlas'
 assert inference.GraphInference().embed('Atlas') is None

def test_m09_technical_helpers_do_not_claim_primary_inference():
 from app.modules.m09_knowledge_workspace.technical_95_99 import run
 r=run(97,{'tenant_id':'t','nodes':[],'edges':[]})
 assert r['persistence_performed'] is False and r['ner_inference_performed'] is False

def test_m12_gan_explicitly_declares_planning_not_training():
 from app.modules.m12_ai_research_lab.research_methods_135_184 import execute,capabilities
 r=execute('GAN Training',{'source':{'title':'Example','url':'https://example.org'},'task':'train'})
 assert r['primary_model_training_performed'] is False
 assert all(x['primary_algorithm_execution_claimed'] is False for x in capabilities())

@pytest.mark.asyncio
async def test_m12_dag_preserves_review_result_without_running_child():
 from app.modules.m12_ai_research_lab.wiring import build_dag_engine,WorkflowReviewRequired
 from app.modules.m12_ai_research_lab.workflow import Workflow
 from app.modules.m12_ai_research_lab.executor import ConfidenceUnavailable
 from app.modules.m12_ai_research_lab.models import ModelResult
 calls=[]
 class Service:
  async def execute(self,*a):
   calls.append(a)
   raise ConfidenceUnavailable(ModelResult('answer','model',metadata={'review_required':True}))
 wf=Workflow.from_yaml('nodes:\n- {id: a, task: research}\n- {id: b, task: research, depends_on: [a]}')
 with pytest.raises(WorkflowReviewRequired) as exc:
  await build_dag_engine(Service()).run(wf,{'tenant_id':'t'})
 assert exc.value.result.text=='answer' and len(calls)==1
def test_m11_split_prep_cannot_cross_protected_focus():
 from app.modules.m11_calendar_intelligence.solver import InfeasibleScheduleError
 p=prefs();p.focus_blocks={0:[Window(540,555)]}
 with pytest.raises(InfeasibleScheduleError):
  BuiltInSolver().solve([TaskSpec('split','split',30,dt(10),prep_minutes=30,splittable=True,min_block_minutes=15)],[],p,D,days=1)

def test_m11_failed_trial_does_not_leak_reservations():
 tasks=[TaskSpec('long','long',45,dt(10),priority=5),TaskSpec('early','early',15,dt(9,15),priority=1)]
 s=BuiltInSolver()
 first=s.solve(tasks,[],prefs(),D,days=1);second=s.solve(tasks,[],prefs(),D,days=1)
 assert first==second

def test_m12_latency_limit_boundary():
 m=ModelCapability('equal',frozenset({TaskType.RESEARCH}),4000,0,100,.9)
 assert ModelRouter([m]).route(RouteRequest(TaskType.RESEARCH,100,1,100,'t')).primary.model_id=='equal'

@pytest.mark.asyncio
async def test_m12_workflow_http_reports_review_not_generic_error():
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab import routes
 from app.modules.m12_ai_research_lab.wiring import build_dag_engine
 from app.modules.m12_ai_research_lab.executor import ConfidenceUnavailable
 from app.modules.m12_ai_research_lab.models import ModelResult
 class Service:
  async def execute(self,*args):raise ConfidenceUnavailable(ModelResult('review me','model',metadata={'review_required':True}))
 app=FastAPI();app.include_router(routes.router)
 app.dependency_overrides[require_tenant]=lambda:TenantContext('t','u')
 app.dependency_overrides[routes.get_dag_engine]=lambda:build_dag_engine(Service())
 r=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':'nodes:\n- {id: a, task: research}','inputs':{}})
 assert r.status_code==422
 assert r.json()['detail']['state']=='review_required'
 assert r.json()['detail']['result']['text']=='review me'
 assert r.json()['detail']['downstream_executed'] is False
