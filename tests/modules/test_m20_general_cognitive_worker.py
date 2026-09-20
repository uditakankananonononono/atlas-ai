import pytest
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service as ApprovalService
from app.core.approvals import approvals as shared_approvals
from app.modules.m20_general_cognitive_worker.service import *

class Model:
 async def __call__(self,purpose,payload):
  return {"steps":[{"id":"read","title":"research","tool":"reader","risk":"read"},{"id":"send","title":"send","tool":"sender","risk":"external","depends_on":["read"],"max_attempts":2}]} if purpose=="htn_plan" else {"summary":"ok"}
class Adapter:
 def __init__(self,result=None):self.calls=0;self.result=result or {"ok":True}
 async def __call__(self,args,key):self.calls+=1;return self.result

@pytest.mark.asyncio
async def test_full_loop_pauses_for_external_approval():
 approvals=shared_approvals;service=Service(approvals,Model());reader=Adapter();sender=Adapter()
 service.tools.register(Tool("reader","read",Risk.READ,{"read"},reader))
 service.tools.register(Tool("sender","send",Risk.EXTERNAL,{"send"},sender))
 run=await service.start("research then send",{}, {"seconds":10,"tokens":100,"money":0})
 assert run.plan.steps[0].state==State.SUCCEEDED
 assert run.plan.steps[1].state==State.WAITING_APPROVAL
 assert sender.calls==0
 approvals.decide(run.plan.steps[1].approval_id,ApprovalStatus.APPROVED)
 run=await service.loop.execute(run)
 assert run.status==State.SUCCEEDED and sender.calls==1
 assert run.traces[-1].policy_basis

def test_memory_sensory_skill_and_supervision():
 sensory=SensoryIngestion({"api"});event=SensoryEvent("api","item",{"title":"grant"},"x")
 assert sensory.ingest(event) and not sensory.ingest(event)
 wm=WorkingMemory(10);wm.put("a","small",.9);wm.put("b","x"*100,.1);assert "a" in wm.context()
 ltm=LongTermMemory();ltm.remember(Memory("semantic",{"statement":"grant deadline"},{"source":"official"},.9));assert ltm.recall("grant")
 skills=SkillLibrary();skills.register(Skill("research","research",[{"title":"read"}]));assert skills.match("research this")
 run=Run("x",{},Plan("x",[],{}),status=State.BLOCKED);assert AtlasSupervisor().assess([run],1)["action"]=="pause_and_escalate"
