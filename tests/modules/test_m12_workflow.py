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
 assert result=={'self':None} and paths==['$["self"]']

def test_mounted_cyclic_review_candidate_survives_conversion_boundary():
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_dag_engine
 from app.modules.m12_ai_research_lab.executor import ConfidenceUnavailable
 from app.modules.m12_ai_research_lab.models import ModelResult
 cyclic={};cyclic['self']=cyclic
 async def runner(*args):raise ConfidenceUnavailable(ModelResult('retained','fixture',usage={'input_tokens':12},metadata=cyclic))
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_dag_engine]=lambda:DagEngine(runner)
 response=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':'nodes: [{id: a, task: review}]'})
 assert response.status_code==422,response.text
 detail=response.json()['detail'];assert detail['state']=='review_required'
 assert detail['result']['text']=='retained' and detail['result']['usage']=={'input_tokens':12}
 assert detail['result']['metadata']=={'self':None} and detail['invalid_json_paths']

@pytest.mark.parametrize('limit',[0,-1,True,False,1.5,'8',None,float('nan'),float('inf')])
def test_invalid_dag_concurrency_rejected_before_node_dispatch(limit):
 calls=[]
 async def runner(*args):calls.append(args);return {}
 with pytest.raises(WorkflowValidationError,match='positive integer'):DagEngine(runner,max_concurrency=limit)
 assert not calls

@pytest.mark.asyncio
async def test_valid_dag_concurrency_serializes_independent_nodes():
 active=0;peak=0;calls=[]
 async def runner(task,*args):
  nonlocal active,peak
  active+=1;peak=max(peak,active);calls.append(task)
  await asyncio.sleep(0)
  active-=1;return {'text':task}
 out=await DagEngine(runner,max_concurrency=1).run(Workflow.from_yaml('nodes: [{id: a, task: a}, {id: b, task: b}]'),{})
 assert peak==1 and calls==['a','b'] and out=={'a':{'text':'a'},'b':{'text':'b'}}

def test_response_loss_paths_distinguish_nested_dotted_and_index_like_keys():
 from app.modules.m12_ai_research_lab.response_json import safe_workflow_json
 from math import nan
 value={'a.b':nan,'a':{'b':nan},'x[0]':nan,'x':[nan],'quote"key':nan}
 result,paths=safe_workflow_json(value)
 assert len(set(paths))==5
 assert '$["a.b"]' in paths and '$["a"]["b"]' in paths
 assert '$["x[0]"]' in paths and '$["x"][0]' in paths
 assert '$["quote\\"key"]' in paths
 assert result=={'a.b':None,'a':{'b':None},'x[0]':None,'x':[None],'quote"key':None}

def test_response_discarded_key_paths_identify_distinct_positions():
 from app.modules.m12_ai_research_lab.response_json import safe_workflow_json
 value={1:'discard',2:'discard','normal':'retained','\ud800':'discard','\udfff':'discard'}
 result,paths=safe_workflow_json(value)
 assert result=={'normal':'retained'} and len(set(paths))==4
 assert paths==['$.<nontext-key:0>','$.<nontext-key:1>','$.<invalid-text-key:3>','$.<invalid-text-key:4>']

@pytest.mark.asyncio
async def test_generic_dag_retains_custom_config_contract():
 calls=[]
 async def runner(task,config,context):calls.append(config);return {'supplied':config}
 config={'temperature':.2,'custom':{'flag':True}}
 result=await DagEngine(runner).run(Workflow.from_yaml('nodes: [{id: a, task: custom, config: {temperature: 0.2, custom: {flag: true}}}]'),{})
 assert calls==[config] and result=={'a':{'supplied':config}}

@pytest.mark.parametrize('extra',[{'budget_cents':1},{'model_id':'unsupported'},{'tenant_id':'other'},{'input':{'prompt':'wrong'}}])
def test_workflow_body_extra_options_not_silently_ignored(extra):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_dag_engine
 calls=[]
 async def runner(*args):calls.append(args);return {'text':'fixture'}
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_dag_engine]=lambda:DagEngine(runner)
 response=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':'nodes: [{id: a, task: fixture}]',**extra})
 assert response.status_code==422,response.text
 assert response.json()['detail'][0]['type']=='extra_forbidden' and not calls

@pytest.mark.parametrize('raw',[
 'budget_cents: 1\nnodes: [{id: a, task: fixture}]',
 'inputs: {prompt: ignored}\nnodes: [{id: a, task: fixture}]',
 'nodes: [{id: a, task: fixture, model_id: ignored}]',
 'nodes: [{id: a, task: fixture, depend_on: [missing]}]',
])
def test_unknown_yaml_options_not_silently_ignored(raw):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_dag_engine
 calls=[]
 async def runner(*args):calls.append(args);return {}
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_dag_engine]=lambda:DagEngine(runner)
 response=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':raw})
 assert response.status_code==422,response.text
 assert 'unsupported workflow' in response.json()['detail'] and not calls

@pytest.mark.asyncio
async def test_node_input_tenant_mutation_cannot_change_siblings_or_descendants():
 seen=[]
 async def runner(task,config,context):
  inputs=context['workflow_inputs'];seen.append((task,inputs['tenant_id']))
  if task=='a':inputs['tenant_id']='forged';inputs['prompt']='changed'
  return {'text':task}
 inputs={'tenant_id':'original','prompt':'fixture'}
 wf=Workflow.from_yaml('nodes: [{id: a, task: a}, {id: b, task: b}, {id: c, task: c, depends_on: [a]}]')
 out=await DagEngine(runner).run(wf,inputs)
 assert seen==[('a','original'),('b','original'),('c','original')]
 assert inputs=={'tenant_id':'original','prompt':'fixture'} and len(out)==3

@pytest.mark.asyncio
async def test_validator_top_level_input_mutation_does_not_rebind_execution():
 seen=[];validated=[]
 def validator(node,inputs):
  validated.append((node.id,inputs['tenant_id']))
  inputs['tenant_id']='changed-by-validator'
 async def runner(task,config,context):seen.append(context['workflow_inputs']['tenant_id']);return {}
 inputs={'tenant_id':'original'}
 wf=Workflow.from_yaml('nodes: [{id: a, task: a}, {id: b, task: b}]')
 await DagEngine(runner,validator=validator).run(wf,inputs)
 assert validated==[('a','original'),('b','original')] and seen==['original','original'] and inputs=={'tenant_id':'original'}

@pytest.mark.asyncio
async def test_running_dag_uses_entry_input_snapshot_despite_caller_rebinding():
 started=asyncio.Event();release=asyncio.Event();seen=[]
 async def runner(task,config,context):
  seen.append((task,context['workflow_inputs']['tenant_id']))
  if task=='a':started.set();await release.wait()
  return {'text':task}
 inputs={'tenant_id':'original'}
 wf=Workflow.from_yaml('nodes: [{id: a, task: a}, {id: b, task: b, depends_on: [a]}]')
 running=asyncio.create_task(DagEngine(runner).run(wf,inputs))
 await started.wait();inputs['tenant_id']='caller-changed';release.set()
 await running
 assert seen==[('a','original'),('b','original')] and inputs['tenant_id']=='caller-changed'

@pytest.mark.asyncio
async def test_descendant_cannot_rewrite_top_level_parent_for_parallel_consumer():
 seen=[]
 async def runner(task,config,context):
  if task=='parent':return {'text':'original','model_id':'fixture'}
  seen.append((task,context['parents']['a']['text']))
  if task=='mutator':context['parents']['a']['text']='forged'
  return {'text':task}
 wf=Workflow.from_yaml('nodes: [{id: a, task: parent}, {id: b, task: mutator, depends_on: [a]}, {id: c, task: consumer, depends_on: [a]}]')
 result=await DagEngine(runner).run(wf,{})
 assert seen==[('mutator','original'),('consumer','original')]
 assert result['a']=={'text':'original','model_id':'fixture'}
