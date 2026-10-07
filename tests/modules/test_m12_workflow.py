import pytest
from app.modules.m12_ai_research_lab.workflow import *
def test_yaml_dag_validation():
    wf=Workflow.from_yaml("name: x\nnodes:\n- {id: a, task: model}\n- {id: b, task: model, depends_on: [a]}\n")
    assert wf.nodes[1].depends_on==("a",)
def test_cycle_rejected():
    with pytest.raises(WorkflowValidationError): Workflow.from_yaml("nodes:\n- {id: a, task: x, depends_on: [b]}\n- {id: b, task: x, depends_on: [a]}\n")
@pytest.mark.asyncio
async def test_engine_passes_declared_parent_outputs():
    async def runner(task,config,ctx): return {"parents":list(ctx["parents"])}
    wf=Workflow.from_yaml("nodes:\n- {id: a, task: x}\n- {id: b, task: x, depends_on: [a]}\n")
    out=await DagEngine(runner).run(wf,{})
    assert out["b"]["parents"]==["a"]

@pytest.mark.parametrize('raw',['','[]','name: x','nodes: []','nodes: {}','nodes: [1]','nodes: [{task: x}]','nodes: [{id: 1, task: x}]','nodes: [{id: a, task: null}]','nodes: [{id: a, task: x, depends_on: a}]','nodes: [{id: a, task: x, config: []}]','nodes: [','name: []\nnodes: [{id: a, task: x}]','nodes: [{id: a, task: x, depends_on: [b,b]}, {id: b, task: x}]'])
def test_invalid_yaml_shapes_rejected_with_contract_error(raw):
 with pytest.raises(WorkflowValidationError):Workflow.from_yaml(raw)

@pytest.mark.parametrize('raw',['[]','nodes: []','nodes: [','nodes: [{id: a, task: x, config: []}]'])
def test_mounted_workflow_invalid_input_422_before_runner(raw):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_dag_engine
 calls=[]
 async def runner(*args):calls.append(args);return {}
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_dag_engine]=lambda:DagEngine(runner)
 response=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':raw,'inputs':{}})
 assert response.status_code==422 and not calls

@pytest.mark.parametrize('raw',['nodes: [{id: a, id: b, task: x}]','nodes: [{id: a, task: x, config: {budget: 1, budget: 999}}]','nodes: [{id: a, task: x}]\nnodes: [{id: b, task: x}]'])
def test_duplicate_yaml_keys_not_silently_overwritten(raw):
 with pytest.raises(WorkflowValidationError,match='duplicate YAML'):Workflow.from_yaml(raw)

def test_excessive_nested_yaml_depth_is_contract_error_not_recursion():
 raw='nodes: [{id: a, task: x, config: {nested: '+ '['*600+'0'+']'*600+'}}]'
 with pytest.raises(WorkflowValidationError):Workflow.from_yaml(raw)

def test_mounted_excessive_depth_is_422_without_runner_call():
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_dag_engine
 calls=[]
 async def runner(*args):calls.append(args);return {}
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_dag_engine]=lambda:DagEngine(runner)
 raw='nodes: [{id: a, task: x, config: {nested: '+ '['*600+'0'+']'*600+'}}]'
 response=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':raw})
 assert response.status_code==422 and not calls

@pytest.mark.parametrize('kind,status,state',[('review',422,'review_required'),('unknown',409,'unknown')])
def test_mounted_node_uncertainty_retains_sibling_output_no_dependent_or_retry(kind,status,state):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.core.providers import ProviderOutcomeUnknown
 from app.modules.m12_ai_research_lab.routes import router,get_dag_engine
 from app.modules.m12_ai_research_lab.executor import ConfidenceUnavailable
 from app.modules.m12_ai_research_lab.models import ModelResult
 calls=[]
 async def runner(task,config,ctx):
  calls.append(task)
  if task=='uncertain':
   if kind=='unknown':raise ProviderOutcomeUnknown('fixture dispatched')
   raise ConfidenceUnavailable(ModelResult('review candidate','fixture',usage={'input_tokens':12}))
  return {'text':'sibling complete'}
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_dag_engine]=lambda:DagEngine(runner)
 raw='nodes: [{id: a, task: uncertain}, {id: b, task: sibling}, {id: c, task: dependent, depends_on: [a,b]}]'
 response=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':raw})
 assert response.status_code==status,response.text
 detail=response.json()['detail'];assert detail['state']==state and detail['node_id']=='a' and detail['retry_allowed'] is False
 assert detail['completed']=={'b':{'text':'sibling complete'}} and calls==['uncertain','sibling']
 if kind=='review':assert detail['result']['text']=='review candidate' and detail['result']['usage']=={'input_tokens':12}

@pytest.mark.asyncio
async def test_cancelled_parent_never_becomes_successful_dependency():
 calls=[]
 async def runner(task,config,context):
  calls.append(task)
  if task=='cancel':raise asyncio.CancelledError()
  return {'text':'fixture'}
 wf=Workflow.from_yaml('nodes: [{id: a, task: cancel}, {id: b, task: sibling}, {id: c, task: dependent, depends_on: [a,b]}]')
 with pytest.raises(WorkflowNodeFailure) as error:await DagEngine(runner).run(wf,{})
 assert calls==['cancel','sibling'] and isinstance(error.value.error,asyncio.CancelledError)
 assert error.value.completed=={'b':{'text':'fixture'}} and 'a' not in error.value.completed

def test_mounted_cancelled_node_is_controlled_failure_without_dependent():
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_dag_engine
 calls=[]
 async def runner(task,config,context):calls.append(task);raise asyncio.CancelledError()
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_dag_engine]=lambda:DagEngine(runner)
 response=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':'nodes: [{id: a, task: cancel}, {id: b, task: dependent, depends_on: [a]}]'})
 assert response.status_code==422 and response.json()['detail']['state']=='cancelled' and calls==['cancel']

def test_mounted_multiple_failures_preserve_unknown_and_review_evidence():
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.core.providers import ProviderOutcomeUnknown
 from app.modules.m12_ai_research_lab.routes import router,get_dag_engine
 from app.modules.m12_ai_research_lab.executor import ConfidenceUnavailable
 from app.modules.m12_ai_research_lab.models import ModelResult
 calls=[]
 async def runner(task,config,context):
  calls.append(task)
  if task=='failed':raise RuntimeError('fixture failure')
  if task=='unknown':raise ProviderOutcomeUnknown('fixture dispatched')
  if task=='review':raise ConfidenceUnavailable(ModelResult('candidate','fixture',usage={'input_tokens':12}))
  return {'text':'completed'}
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_dag_engine]=lambda:DagEngine(runner)
 raw='nodes: [{id: a, task: failed}, {id: b, task: unknown}, {id: c, task: review}, {id: d, task: sibling}, {id: e, task: dependent, depends_on: [a,b,c,d]}]'
 response=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':raw})
 assert response.status_code==409 and response.json()['detail']['state']=='unknown'
 detail=response.json()['detail'];assert detail['node_id']=='b' and detail['reason']=='fixture dispatched'
 assert detail['failed_nodes']==['a','b','c'] and detail['completed']=={'d':{'text':'completed'}}
 assert [f['state'] for f in detail['failures']]==['failed','unknown','review_required']
 assert detail['failures'][2]['result']['text']=='candidate' and detail['failures'][2]['result']['usage']=={'input_tokens':12}
 assert calls==['failed','unknown','review','sibling']

@pytest.mark.parametrize('failed',[True,False])
def test_mounted_unsafe_sibling_metadata_reported_without_losing_result(failed):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_dag_engine
 import json
 async def runner(task,config,context):
  if task=='fail':raise RuntimeError('fixture failure')
  return {'text':'retained','metadata':{'bad':float('nan'),'unsupported':object()}}
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_dag_engine]=lambda:DagEngine(runner)
 raw='nodes: [{id: a, task: sibling}'+(', {id: b, task: fail}' if failed else '')+']'
 response=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':raw})
 assert response.status_code==422,response.text
 detail=response.json()['detail'];assert detail['completed']['a']['text']=='retained'
 assert detail['completed']['a']['metadata']=={'bad':None,'unsupported':None}
 assert len(detail['invalid_json_paths'])==2
 json.dumps(detail,allow_nan=False)

def test_response_json_cycle_and_depth_are_explicit_not_silent():
 from app.modules.m12_ai_research_lab.response_json import safe_workflow_json
 cyclic={};cyclic['self']=cyclic
 result,paths=safe_workflow_json(cyclic)
 assert result=={'self':None} and paths==['$.self']
