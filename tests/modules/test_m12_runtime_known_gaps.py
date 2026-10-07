"""Hermetic runtime contract gaps. No provider/network calls."""
import asyncio
import pytest
from app.modules.m12_ai_research_lab.models import ModelCapability,ModelResult,RouteRequest,TaskType
from app.modules.m12_ai_research_lab.router import ModelRouter,NoEligibleModel
from app.modules.m12_ai_research_lab.executor import ResearchExecutor,RetryPolicy


def models():
 return [ModelCapability('first',frozenset({TaskType.RESEARCH}),1000,0,100,.9),ModelCapability('backup',frozenset({TaskType.RESEARCH}),1000,0,100,.8)]


def test_provider_exception_currently_escapes_without_backup_invocation():
 calls=[]
 class Provider:
  async def generate(self,*,model_id,prompt,context):
   calls.append(model_id)
   raise TimeoutError('hermetic timeout, no request made')
 executor=ResearchExecutor(ModelRouter(models()),Provider(),RetryPolicy(base_delay_seconds=0))
 with pytest.raises(TimeoutError):
  asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,500,'fixture'),'fixture'))
 assert calls==['first']
 # Characterization, not safe-retry advice: a real timeout may hide a billable effect.


def test_hard_latency_tolerance_rejects_slow_only_catalog():
 model=ModelCapability('slow',frozenset({TaskType.RESEARCH}),1000,0,2000,.9)
 with pytest.raises(NoEligibleModel):
  ModelRouter([model]).route(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'))

@pytest.mark.parametrize('estimate',[101,2000])
def test_over_tolerance_models_excluded_from_primary_and_fallbacks(estimate):
 slow=ModelCapability('slow',frozenset({TaskType.RESEARCH}),1000,0,estimate,1)
 boundary=ModelCapability('boundary',frozenset({TaskType.RESEARCH}),1000,0,100,.8)
 fast=ModelCapability('fast',frozenset({TaskType.RESEARCH}),1000,0,99,.7)
 decision=ModelRouter([slow,boundary,fast]).route(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'))
 assert decision.primary.model_id=='boundary'
 assert [m.model_id for m in decision.fallbacks]==['fast']
 assert decision.scores['slow']==float('-inf')
 assert decision.reasons['slow']==['latency estimate exceeds tolerance']

@pytest.mark.parametrize('estimate,tolerance',[(0,100),(-1,100),(100,0),(100,-1)])
def test_nonpositive_latency_is_not_eligible(estimate,tolerance):
 model=ModelCapability('invalid',frozenset({TaskType.RESEARCH}),1000,0,estimate,.9)
 with pytest.raises(NoEligibleModel):ModelRouter([model]).route(RouteRequest(TaskType.RESEARCH,100,0,tolerance,'fixture'))

def test_ineligible_catalog_does_not_call_provider():
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','slow',1)
 executor=ResearchExecutor(ModelRouter([ModelCapability('slow',frozenset({TaskType.RESEARCH}),1000,0,2000,.9)]),Provider())
 with pytest.raises(NoEligibleModel):asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert not calls

def test_low_confidence_fallback_cannot_invoke_over_tolerance_model():
 calls=[]
 class Provider:
  async def generate(self,*,model_id,**kwargs):
   calls.append(model_id);return ModelResult('fixture',model_id, .1 if model_id=='first' else .9)
 slow=ModelCapability('slow',frozenset({TaskType.RESEARCH}),1000,0,101,1)
 executor=ResearchExecutor(ModelRouter([*models(),slow]),Provider(),RetryPolicy(base_delay_seconds=0))
 result=asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert result.model_id=='backup' and calls==['first','backup']
