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


@pytest.mark.xfail(strict=True,reason='runtime router latency is soft despite max-tolerance contract')
def test_hard_latency_tolerance_rejects_slow_only_catalog():
 model=ModelCapability('slow',frozenset({TaskType.RESEARCH}),1000,0,2000,.9)
 with pytest.raises(NoEligibleModel):
  ModelRouter([model]).route(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'))
