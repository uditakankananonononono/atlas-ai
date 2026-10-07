import asyncio
import pytest
from app.modules.m12_ai_research_lab.wiring import build_dag_engine
from app.modules.m12_ai_research_lab.workflow import Workflow,WorkflowValidationError
from app.modules.m12_ai_research_lab.models import ModelResult

@pytest.mark.parametrize('config',['output_tokens: -1','output_tokens: true','output_tokens: "100"','latency_tolerance_ms: 0','latency_tolerance_ms: false','budget_cents: -.1','budget_cents: .nan','budget_cents: "1"','prompt: [x]','prompt: ""','task_type: invalid'])
def test_all_model_nodes_prevalidate_before_any_service_call(config):
 calls=[]
 class Service:
  async def execute(self,*args):calls.append(args);return ModelResult('fixture','fixture',.9)
 wf=Workflow.from_yaml('nodes: [{id: a, task: research}, {id: b, task: research, config: {'+config+'}}]')
 with pytest.raises(WorkflowValidationError):asyncio.run(build_dag_engine(Service()).run(wf,{'tenant_id':'fixture'}))
 assert calls==[]

def test_valid_model_node_preserves_exact_request_not_coerced():
 calls=[]
 class Service:
  async def execute(self,req,prompt,context):calls.append((req,prompt,context));return ModelResult('fixture','fixture',.9)
 wf=Workflow.from_yaml('nodes: [{id: a, task: research, config: {output_tokens: 100, budget_cents: 0.5, latency_tolerance_ms: 100, prompt: fixture}}]')
 out=asyncio.run(build_dag_engine(Service()).run(wf,{'tenant_id':'fixture'}))
 assert out['a']['text']=='fixture' and calls[0][0].output_tokens==100 and calls[0][0].budget_cents==.5 and calls[0][1]=='fixture'

def test_mounted_shipped_invalid_node_stops_valid_sibling_before_call():
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.auth.context import TenantContext,require_tenant
 from app.modules.m12_ai_research_lab.routes import router,get_dag_engine
 calls=[]
 class Service:
  async def execute(self,*args):calls.append(args);return ModelResult('fixture','fixture',.9)
 app=FastAPI();app.include_router(router);app.dependency_overrides[require_tenant]=lambda:TenantContext('fixture','fixture');app.dependency_overrides[get_dag_engine]=lambda:build_dag_engine(Service())
 response=TestClient(app).post('/ai-research-lab/workflows/run',json={'yaml':'nodes: [{id: a, task: research}, {id: b, task: research, config: {output_tokens: -1}}]'})
 assert response.status_code==422 and calls==[]
