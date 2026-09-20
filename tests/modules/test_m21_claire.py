import pytest
from app.core.approvals import ApprovalStore
from app.modules.m20_general_cognitive_worker.service import Service as Cognitive
from app.modules.m21_claire.service import Service
class Model:
 async def __call__(self,purpose,payload):return {"steps":[{"id":"p","title":"prepare safely","risk":"read"}]}
@pytest.mark.asyncio
async def test_claire_is_sandboxed_bounded_and_transparent():
 approvals=ApprovalStore();s=Service(Cognitive(approvals,Model()),approvals,max_retries=999)
 g=s.intake("build a prototype",["tests pass"],{})
 assert g.limits["environment"]=="paired_local_pc" and g.limits["max_retries"]==5
 done=await s.realize(g.id);assert done.status=="succeeded" and done.evidence[0]["policy_basis"]
 req=s.request_environment_change(g.id,"install_package",{"package":"x"});assert req.status.value=="pending"

def test_claire_rejects_standing_nos():
 s=Service(Cognitive(ApprovalStore(),Model()),ApprovalStore())
 with pytest.raises(ValueError):s.intake("use a discord self-bot",[],{})
