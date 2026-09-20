import json,pytest
from app.modules.m19_idea_incubator.schemas import IntakeIn,PreviewIn
from app.modules.m19_idea_incubator.service import Service
async def gen(prompt,*args):return "mock",json.dumps({"problem":["x"],"customer_segments":["students"],"unique_value_proposition":"u","solution":["s"],"channels":["c"],"revenue_streams":["r"],"cost_structure":["c"],"key_metrics":["k"],"riskiest_assumptions":["demand"]})
class A:
 def put(self,item):return item
@pytest.mark.asyncio
async def test_preview_is_approval_gated():
 s=Service(generate=gen,approval_store=A());run=await s.intake(IntakeIn(one_liner="help students",budget_cap=10));a=s.request_preview(run.id,PreviewIn(artifacts=["build.zip"],estimated_cost=3));assert a.action_type=="deploy_sandbox_preview";assert s.get(run.id).state=="pending_approval"
@pytest.mark.asyncio
async def test_budget_cap_blocks_preview():
 s=Service(generate=gen,approval_store=A());run=await s.intake(IntakeIn(one_liner="help students",budget_cap=1));
 with pytest.raises(ValueError):s.request_preview(run.id,PreviewIn(artifacts=[],estimated_cost=2))
