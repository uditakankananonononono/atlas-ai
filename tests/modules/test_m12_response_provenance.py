import asyncio
import pytest
from app.core import providers
from app.modules.m12_ai_research_lab import wiring
from app.modules.m12_ai_research_lab.executor import ConfidenceUnavailable,ResearchExecutor,RetryPolicy
from app.modules.m12_ai_research_lab.models import ModelCapability,RouteRequest,TaskType
from app.modules.m12_ai_research_lab.router import ModelRouter

@pytest.mark.parametrize('raw,expected',[({'usage':{'prompt_tokens':12,'completion_tokens':3}},(12,3)),({},(None,None)),({'usage':{'prompt_tokens':True,'completion_tokens':-1}},(None,None)),({'usage':{'prompt_tokens':'12','completion_tokens':0}},(None,0)),({'prompt_eval_count':8,'eval_count':2},(8,2)),({'usageMetadata':{'promptTokenCount':7,'candidatesTokenCount':4}},(7,4))])
def test_response_usage_never_invents_missing_zero(raw,expected):
 u=providers._usage(raw,'fixture','model');assert (u.input_tokens,u.output_tokens)==expected

def test_adapter_preserves_response_usage_without_fabricating_confidence_cost(monkeypatch):
 async def fake(*args):return providers.ProviderResult('model','fixture','ollama',providers.ProviderUsage('ollama','model',12,3))
 monkeypatch.setattr(wiring,'generate_result',fake)
 r=asyncio.run(wiring.AtlasProvider().generate(model_id='ollama:model',prompt='fixture',context={}))
 assert r.confidence is None and r.usage=={'input_tokens':12,'output_tokens':3}
 assert r.metadata['usage_source']=='provider_response' and r.metadata['usage_complete'] is True
 assert r.metadata['actual_cost_cents'] is None and r.metadata['cost_source']=='unavailable'

def test_unknown_confidence_stops_once_and_retains_review_candidate(monkeypatch):
 calls=[]
 async def fake(*args):calls.append(args);return providers.ProviderResult('model','candidate','ollama')
 monkeypatch.setattr(wiring,'generate_result',fake)
 cat=[ModelCapability(x,frozenset({TaskType.RESEARCH}),1000,0,100,.8) for x in ['ollama:model','ollama:backup']]
 executor=ResearchExecutor(ModelRouter(cat),wiring.AtlasProvider(),RetryPolicy(base_delay_seconds=0))
 with pytest.raises(ConfidenceUnavailable) as error:asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert len(calls)==1 and error.value.result.text=='candidate'
 assert error.value.result.confidence is None and error.value.result.usage=={}
 assert error.value.result.metadata['review_required'] is True

def test_http_review_boundary_retains_candidate_without_success(monkeypatch):
 from types import SimpleNamespace
 from fastapi import HTTPException
 from app.modules.m12_ai_research_lab.routes import run
 from app.modules.m12_ai_research_lab.schemas import RunIn
 from app.modules.m12_ai_research_lab.models import ModelResult
 class Service:
  async def execute(self,*args):raise ConfidenceUnavailable(ModelResult('candidate','fixture',None,metadata={'review_required':True}))
 with pytest.raises(HTTPException) as error:asyncio.run(run(RunIn(prompt='fixture',task_type=TaskType.RESEARCH,output_tokens=100,budget_cents=1,latency_tolerance_ms=100),SimpleNamespace(tenant_id='fixture'),Service()))
 assert error.value.status_code==422 and error.value.detail['state']=='review_required'
 assert error.value.detail['result']['text']=='candidate' and error.value.detail['result']['confidence'] is None

@pytest.mark.asyncio
async def test_per_response_usage_not_global_last_entry(monkeypatch):
 async def fake(provider,url,**kwargs):
  tokens=kwargs['payload']['messages'][0]['content'];await asyncio.sleep(0)
  return {'choices':[{'message':{'content':tokens}}],'usage':{'prompt_tokens':int(tokens),'completion_tokens':1}}
 monkeypatch.setattr(providers,'_post',fake)
 results=await asyncio.gather(providers.generate_result('12','openai_compat','fixture'),providers.generate_result('21','openai_compat','fixture'))
 assert [(r.text,r.usage.input_tokens) for r in results]==[('12',12),('21',21)]

@pytest.mark.parametrize('confidence,logprobs',[(float('inf'),[]),(float('nan'),[]),(-.1,[]),(1.1,[]),(True,[]),('0.9',[]),(None,[float('inf')]),(None,[float('nan')]),(None,[.1]),(None,[True]),(None,['0']),(None,[-10**1000]),(2,[-.01])])
def test_invalid_confidence_evidence_holds_without_extra_executor_call(confidence,logprobs):
 from app.modules.m12_ai_research_lab.models import ModelResult
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('candidate','fixture',confidence,logprobs)
 cat=[ModelCapability(x,frozenset({TaskType.RESEARCH}),1000,0,100,.8) for x in ['first','backup']]
 with pytest.raises(ConfidenceUnavailable) as error:asyncio.run(ResearchExecutor(ModelRouter(cat),Provider(),RetryPolicy(base_delay_seconds=0)).execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert len(calls)==1 and error.value.result.metadata['review_required'] is True
 assert error.value.result.confidence is None and error.value.result.logprobs==[]
 from dataclasses import asdict
 import json
 json.dumps(asdict(error.value.result),allow_nan=False)

@pytest.mark.parametrize('confidence,logprobs',[(1,[]),(.9,[]),(None,[0])])
def test_valid_confidence_range_or_logprobs_retains_existing_success(confidence,logprobs):
 from app.modules.m12_ai_research_lab.models import ModelResult
 class Provider:
  async def generate(self,**kwargs):return ModelResult('candidate','fixture',confidence,logprobs)
 cat=[ModelCapability('first',frozenset({TaskType.RESEARCH}),1000,0,100,.8)]
 result=asyncio.run(ResearchExecutor(ModelRouter(cat),Provider()).execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert result.metadata['attempts']==1 and 'review_required' not in result.metadata

@pytest.mark.parametrize('confidence,status',[(None,422),(.9,200)])
def test_mounted_http_mixed_catalog_diagnostics_are_strict_json_and_retain_result(confidence,status):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_service
 from app.modules.m12_ai_research_lab.models import ModelResult
 import json
 class Provider:
  async def generate(self,**kwargs):return ModelResult('retained candidate','first',confidence,usage={'input_tokens':12,'output_tokens':3})
 cat=[ModelCapability('first',frozenset({TaskType.RESEARCH}),1000,0,100,.8),ModelCapability('excluded',frozenset({TaskType.RESEARCH}),1000,0,101,1)]
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_service]=lambda:ResearchExecutor(ModelRouter(cat),Provider())
 response=TestClient(app).post('/ai-research-lab/run',json={'prompt':'fixture','task_type':'research','output_tokens':100,'budget_cents':1,'latency_tolerance_ms':100})
 assert response.status_code==status,response.text
 body=response.json();result=body if status==200 else body['detail']['result']
 assert result['text']=='retained candidate' and result['usage']=={'input_tokens':12,'output_tokens':3}
 assert result['metadata']['route_scores']['excluded'] is None
 assert result['metadata']['route_reasons']['excluded']==['latency estimate exceeds tolerance']
 json.dumps(body,allow_nan=False)

@pytest.mark.parametrize('review',[True,False])
@pytest.mark.parametrize('kind',['cycle','nan','object'])
def test_mounted_single_run_unsafe_candidate_retains_evidence_without_repeat(review,kind):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_service
 from app.modules.m12_ai_research_lab.models import ModelResult
 import json
 metadata={}
 metadata['unsafe']=metadata if kind=='cycle' else float('nan') if kind=='nan' else object()
 calls=[]
 class Service:
  async def execute(self,*args):
   calls.append(args)
   result=ModelResult('retained','fixture',None if review else .9,usage={'input_tokens':12},metadata=metadata)
   if review:raise ConfidenceUnavailable(result)
   return result
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_service]=lambda:Service()
 response=TestClient(app).post('/ai-research-lab/run',json={'prompt':'fixture','task_type':'research','output_tokens':100,'budget_cents':1,'latency_tolerance_ms':100})
 assert response.status_code==422,response.text
 detail=response.json()['detail'];assert detail['state']==('review_required' if review else 'invalid_output') and detail['retry_allowed'] is False
 assert detail['result']['text']=='retained' and detail['result']['usage']=={'input_tokens':12}
 assert detail['result']['metadata']=={'unsafe':None} and detail['invalid_json_paths']
 assert len(calls)==1
 json.dumps(detail,allow_nan=False)

def test_mounted_single_run_provider_unknown_is_hold_without_backup():
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.core.providers import ProviderOutcomeUnknown
 from app.modules.m12_ai_research_lab.routes import router,get_service
 calls=[]
 class Provider:
  async def generate(self,**kwargs):
   calls.append(kwargs['model_id'])
   raise ProviderOutcomeUnknown('fixture dispatch unknown')
 cat=[ModelCapability(x,frozenset({TaskType.RESEARCH}),1000,0,100,.8) for x in ['first','backup']]
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_service]=lambda:ResearchExecutor(ModelRouter(cat),Provider())
 response=TestClient(app,raise_server_exceptions=False).post('/ai-research-lab/run',json={'prompt':'fixture','task_type':'research','output_tokens':100,'budget_cents':1,'latency_tolerance_ms':100})
 assert response.status_code==409,response.text
 detail=response.json()['detail'];assert detail['state']=='unknown' and detail['retry_allowed'] is False
 assert detail['reason']=='fixture dispatch unknown' and calls==['first']

@pytest.mark.parametrize('budget',['NaN','Infinity','-Infinity'])
def test_single_run_nonfinite_budget_rejected_before_service(budget):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_service
 calls=[]
 class Service:
  async def execute(self,*args):calls.append(args);raise AssertionError('must not execute')
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_service]=lambda:Service()
 response=TestClient(app).post('/ai-research-lab/run',json={'prompt':'fixture','task_type':'research','output_tokens':100,'budget_cents':budget,'latency_tolerance_ms':100})
 assert response.status_code==422,response.text
 assert not calls

@pytest.mark.parametrize('workflow',[True,False])
def test_mounted_exhausted_low_confidence_retains_last_candidate_and_usage(workflow):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_service,get_dag_engine
 from app.modules.m12_ai_research_lab.service import Service
 from app.modules.m12_ai_research_lab.wiring import build_dag_engine
 from app.modules.m12_ai_research_lab.models import ModelResult
 calls=[]
 class Provider:
  async def generate(self,**kwargs):
   calls.append(kwargs['model_id']);return ModelResult('candidate '+kwargs['model_id'],kwargs['model_id'],.1,usage={'input_tokens':12})
 cat=[ModelCapability(x,frozenset({TaskType.RESEARCH}),1000,0,100,.8) for x in ['first','backup']]
 service=Service(ModelRouter(cat),Provider(),RetryPolicy(base_delay_seconds=0))
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_service]=lambda:service;app.dependency_overrides[get_dag_engine]=lambda:build_dag_engine(service)
 if workflow:
  response=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':'nodes: [{id: a, task: research, config: {output_tokens: 100}}, {id: b, task: research, depends_on: [a]}]'})
 else:
  response=TestClient(app).post('/ai-research-lab/run',json={'prompt':'fixture','task_type':'research','output_tokens':100,'budget_cents':1,'latency_tolerance_ms':100})
 assert response.status_code==422,response.text
 detail=response.json()['detail'];assert detail['state']=='review_required' and detail['retry_allowed'] is False
 result=detail['result'];assert result['text']=='candidate backup' and result['usage']=={'input_tokens':12}
 assert result['metadata']['review_reason']=='confidence_threshold_not_reached'
 assert result['metadata']['attempts']==2 and len(result['metadata']['history'])==2
 assert calls==['first','backup']

@pytest.mark.parametrize('token',['NaN','Infinity','-Infinity'])
@pytest.mark.parametrize('prefixed',[False,True])
def test_raw_nonfinite_budget_validation_is_safe_without_execution(token,prefixed):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_service
 import json
 calls=[]
 class Service:
  async def execute(self,*args):calls.append(args);raise AssertionError('must not execute')
 app=FastAPI();app.include_router(router,prefix='/api/v1' if prefixed else '');app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_service]=lambda:Service()
 payload='{"prompt":"private fixture","task_type":"research","output_tokens":100,"budget_cents":'+token+',"latency_tolerance_ms":100}'
 response=TestClient(app,raise_server_exceptions=False).post(('/api/v1' if prefixed else '')+'/ai-research-lab/run',content=payload,headers={'content-type':'application/json'})
 assert response.status_code==422,response.text
 assert not calls
 errors=response.json()['detail'];assert errors[0]['loc']==['body','budget_cents']
 assert set(errors[0])=={'type','loc','msg'} and 'private fixture' not in response.text
 json.dumps(response.json(),allow_nan=False)

@pytest.mark.parametrize('endpoint,payload',[('run','{broken'),('workflows/run','{"yaml":NaN}')])
def test_model_validation_boundary_handles_other_invalid_body_shapes(endpoint,payload):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_service,get_dag_engine
 app=FastAPI();app.include_router(router,prefix='/api/v1');app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_service]=lambda:object();app.dependency_overrides[get_dag_engine]=lambda:object()
 response=TestClient(app,raise_server_exceptions=False).post('/api/v1/ai-research-lab/'+endpoint,content=payload,headers={'content-type':'application/json'})
 assert response.status_code==422,response.text
 assert response.json()['detail'] and all(set(x)=={'type','loc','msg'} for x in response.json()['detail'])

def test_model_validation_boundary_does_not_catch_auth_http_failure():
 from fastapi import FastAPI,HTTPException
 from fastapi.testclient import TestClient
 from app.auth.context import require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_service
 calls=[]
 def denied():raise HTTPException(401,'fixture denied')
 class Service:
  async def execute(self,*args):calls.append(args)
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=denied;app.dependency_overrides[get_service]=lambda:Service()
 response=TestClient(app).post('/ai-research-lab/run',json={'prompt':'fixture','task_type':'research','output_tokens':100,'budget_cents':1,'latency_tolerance_ms':100})
 assert response.status_code==401 and response.json()=={'detail':'fixture denied'} and not calls

@pytest.mark.parametrize('field,invalid',[
 *[('output_tokens',x) for x in [True,False,'100',100.0]],
 *[('latency_tolerance_ms',x) for x in [True,False,'100',100.0]],
 *[('budget_cents',x) for x in [True,False,'1']],
])
def test_single_run_limits_not_coerced_before_execution(field,invalid):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_service
 from app.modules.m12_ai_research_lab.models import ModelResult
 calls=[]
 class Service:
  async def execute(self,*args):calls.append(args);return ModelResult('fixture','fixture',.9)
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_service]=lambda:Service()
 body={'prompt':'fixture','task_type':'research','output_tokens':100,'budget_cents':1,'latency_tolerance_ms':100};body[field]=invalid
 response=TestClient(app).post('/ai-research-lab/run',json=body)
 assert response.status_code==422,response.text
 assert not calls

@pytest.mark.parametrize('logprobs,review',[([0,-.2],False),([-3],True)])
def test_effective_logprob_confidence_retained_with_derivation_marker(logprobs,review):
 from app.modules.m12_ai_research_lab.models import ModelResult
 from app.modules.m12_ai_research_lab.executor import ConfidenceThresholdNotReached
 from app.modules.m12_ai_research_lab.router import confidence_from_logprobs
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','first',None,list(logprobs),metadata={'confidence_source':'unavailable'})
 cat=[ModelCapability('first',frozenset({TaskType.RESEARCH}),1000,0,100,.8)]
 executor=ResearchExecutor(ModelRouter(cat),Provider(),RetryPolicy(base_delay_seconds=0))
 if review:
  with pytest.raises(ConfidenceThresholdNotReached) as error:asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
  result=error.value.result
 else:result=asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert result.confidence==confidence_from_logprobs(logprobs)
 assert result.metadata['confidence_source']=='supplied_logprobs_mean_exp'
 assert result.metadata['history'][0]['confidence']==result.confidence and result.logprobs==logprobs
 assert len(calls)==1

@pytest.mark.parametrize('confidence',[None,.9])
def test_requested_route_identity_separate_from_reported_response_model(confidence):
 from app.modules.m12_ai_research_lab.models import ModelResult
 calls=[]
 class Provider:
  async def generate(self,**kwargs):
   calls.append(kwargs['model_id']);return ModelResult('fixture','reported-model-alias',confidence,metadata={'requested_model_id':'untrusted-stale-field'})
 cat=[ModelCapability('ollama:requested-model',frozenset({TaskType.RESEARCH}),1000,0,100,.8)]
 executor=ResearchExecutor(ModelRouter(cat),Provider())
 if confidence is None:
  with pytest.raises(ConfidenceUnavailable) as error:asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
  result=error.value.result
 else:result=asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert calls==['ollama:requested-model']
 assert result.model_id=='reported-model-alias'
 assert result.metadata['requested_model_id']=='ollama:requested-model'

@pytest.mark.parametrize('bad',['envelope','none','list','text'])
@pytest.mark.parametrize('workflow',[True,False])
def test_mounted_invalid_returned_model_envelope_holds_after_one_call(bad,workflow):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_service,get_dag_engine
 from app.modules.m12_ai_research_lab.service import Service
 from app.modules.m12_ai_research_lab.wiring import build_dag_engine
 from app.modules.m12_ai_research_lab.models import ModelResult
 calls=[]
 class Provider:
  async def generate(self,**kwargs):
   calls.append(kwargs['model_id'])
   if bad=='envelope':return {'text':'fixture'}
   return ModelResult('fixture','fixture',.9,metadata={'none':None,'list':[],'text':'bad'}[bad])
 cat=[ModelCapability(x,frozenset({TaskType.RESEARCH}),1000,0,100,.8) for x in ['first','backup']]
 service=Service(ModelRouter(cat),Provider(),RetryPolicy(base_delay_seconds=0))
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_service]=lambda:service;app.dependency_overrides[get_dag_engine]=lambda:build_dag_engine(service)
 if workflow:response=TestClient(app,raise_server_exceptions=False).post('/ai-research-lab/workflows/run',json={'yaml':'nodes: [{id: a, task: research}, {id: b, task: research, depends_on: [a]}]'})
 else:response=TestClient(app,raise_server_exceptions=False).post('/ai-research-lab/run',json={'prompt':'fixture','task_type':'research','output_tokens':100,'budget_cents':1,'latency_tolerance_ms':100})
 assert response.status_code==409,response.text
 detail=response.json()['detail'];assert detail['state']=='unknown' and detail['retry_allowed'] is False
 assert calls==['first']

@pytest.mark.parametrize('field,value',[('text',None),('text',{}),('text',1),('model_id',None),('model_id',''),('model_id',' '),('model_id',1)])
def test_invalid_returned_text_or_model_identity_holds_without_backup(field,value):
 from app.core.providers import ProviderOutcomeUnknown
 from app.modules.m12_ai_research_lab.models import ModelResult
 calls=[]
 class Provider:
  async def generate(self,**kwargs):
   calls.append(kwargs['model_id']);result=ModelResult('fixture','reported',.9);setattr(result,field,value);return result
 cat=[ModelCapability(x,frozenset({TaskType.RESEARCH}),1000,0,100,.8) for x in ['first','backup']]
 with pytest.raises(ProviderOutcomeUnknown,match='text or reported model identity'):asyncio.run(ResearchExecutor(ModelRouter(cat),Provider()).execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert calls==['first']

def test_empty_returned_text_retained_without_inventing_missing_response():
 from app.modules.m12_ai_research_lab.models import ModelResult
 class Provider:
  async def generate(self,**kwargs):return ModelResult('','reported',.9)
 cat=[ModelCapability('first',frozenset({TaskType.RESEARCH}),1000,0,100,.8)]
 result=asyncio.run(ResearchExecutor(ModelRouter(cat),Provider()).execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert result.text=='' and result.model_id=='reported'

@pytest.mark.parametrize('workflow',[True,False])
@pytest.mark.parametrize('review',[True,False])
def test_mounted_unrenderable_integer_evidence_is_loss_marked_not_500(workflow,review):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_service,get_dag_engine
 from app.modules.m12_ai_research_lab.workflow import DagEngine
 from app.modules.m12_ai_research_lab.models import ModelResult
 import sys
 if not sys.get_int_max_str_digits():pytest.skip('integer rendering limit disabled')
 huge=10**(sys.get_int_max_str_digits()+1);calls=[]
 result=ModelResult('retained','fixture',None if review else .9,usage={'input_tokens':huge})
 class Service:
  async def execute(self,*args):
   calls.append(args)
   if review:raise ConfidenceUnavailable(result)
   return result
 async def runner(*args):
  returned=await Service().execute(*args)
  return {'text':returned.text,'usage':returned.usage}
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_service]=lambda:Service();app.dependency_overrides[get_dag_engine]=lambda:DagEngine(runner)
 if workflow:response=TestClient(app,raise_server_exceptions=False).post('/ai-research-lab/workflows/run',json={'yaml':'nodes: [{id: a, task: fixture}]'})
 else:response=TestClient(app,raise_server_exceptions=False).post('/ai-research-lab/run',json={'prompt':'fixture','task_type':'research','output_tokens':100,'budget_cents':1,'latency_tolerance_ms':100})
 assert response.status_code==422,response.text
 detail=response.json()['detail'];assert detail['state']==('review_required' if review else 'invalid_output')
 retained=detail['completed']['a'] if workflow and not review else detail['result']
 assert retained['text']=='retained' and retained['usage']=={'input_tokens':None}
 assert detail['invalid_json_paths'] and len(calls)==1

@pytest.mark.parametrize('review',[True,False])
@pytest.mark.parametrize('kind',['value','key'])
def test_mounted_invalid_utf8_response_text_is_explicitly_loss_marked(review,kind):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_service
 from app.modules.m12_ai_research_lab.models import ModelResult
 calls=[]
 class Service:
  async def execute(self,*args):
   calls.append(args)
   metadata={'normal':'অসমীয়া café 🌿'}
   metadata['bad' if kind=='value' else '\ud800']='\udfff' if kind=='value' else 'kept elsewhere'
   result=ModelResult('retained','fixture',None if review else .9,metadata=metadata)
   if review:raise ConfidenceUnavailable(result)
   return result
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_service]=lambda:Service()
 response=TestClient(app,raise_server_exceptions=False).post('/ai-research-lab/run',json={'prompt':'fixture','task_type':'research','output_tokens':100,'budget_cents':1,'latency_tolerance_ms':100})
 assert response.status_code==422,response.text
 detail=response.json()['detail'];assert detail['state']==('review_required' if review else 'invalid_output')
 metadata=detail['result']['metadata'];assert metadata['normal']=='অসমীয়া café 🌿'
 if kind=='value':assert metadata['bad'] is None
 else:assert set(metadata)=={'normal'}
 assert detail['invalid_json_paths'] and detail['result']['text']=='retained' and len(calls)==1
 response.content.decode('utf-8')
