import pytest
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service as ApprovalService
from app.core.approvals import approvals as shared_approvals
from app.modules.m20_general_cognitive_worker.legacy_service import *

class Model:
 async def __call__(self,purpose,payload):
  return {"steps":[{"id":"read","title":"research","tool":"reader","risk":"read"},{"id":"send","title":"send","tool":"sender","risk":"external","depends_on":["read"],"max_attempts":2}]} if purpose=="htn_plan" else {"summary":"ok"}
class Adapter:
 def __init__(self,result=None):self.calls=0;self.result=result or {"ok":True}
 async def __call__(self,args,key):self.calls+=1;return self.result

@pytest.fixture
def initialized_approvals(tmp_path,monkeypatch):
 from sqlalchemy import create_engine
 from sqlalchemy.orm import sessionmaker
 from app.core.database import Base
 import app.modules.m00_approval_center.service as module
 engine=create_engine(f"sqlite:///{tmp_path}/approvals.db")
 Base.metadata.create_all(engine)
 monkeypatch.setattr(module,'_default_service',ApprovalService(session_factory=sessionmaker(bind=engine,expire_on_commit=False)))
 return shared_approvals

@pytest.mark.asyncio
async def test_full_loop_pauses_for_external_approval(initialized_approvals):
 approvals=initialized_approvals;service=Service(approvals,Model());reader=Adapter();sender=Adapter()
 service.tools.register(Tool("reader","read",Risk.READ,{"read"},reader))
 service.tools.register(Tool("sender","send",Risk.EXTERNAL,{"send"},sender))
 run=await service.start("research then send",{}, {"seconds":10,"tokens":100,"money":0},tenant_id="t1",actor_id="u1")   # CONVERTED (slice 16): identity is required for approval-gated steps
 assert run.plan.steps[0].state==State.SUCCEEDED
 assert run.plan.steps[1].state==State.WAITING_APPROVAL
 assert sender.calls==0
 approvals.decide(run.plan.steps[1].approval_id,ApprovalStatus.APPROVED,decided_by='approver-1')
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

@pytest.mark.asyncio
async def test_approval_infrastructure_failure_blocks_instead_of_silent_pending():
 # CONVERTED (slice 16): a complete store (so binding is available) whose put fails; the step still BLOCKS, and now no raw error text is kept
 class BrokenStore:
  def put(self,item,**kw):raise RuntimeError('approval database unavailable')
  def list(self):return []
  def full_view(self,i):raise RuntimeError('x')
  def consume_effect(self,i,**kw):raise RuntimeError('x')
 service=Service(BrokenStore(),Model());reader=Adapter();sender=Adapter()
 service.tools.register(Tool('reader','read',Risk.READ,{'read'},reader))
 service.tools.register(Tool('sender','send',Risk.EXTERNAL,{'send'},sender))
 run=await service.start('research then send',{}, {'seconds':10,'tokens':100,'money':0},tenant_id='t1',actor_id='u1')
 assert run.status==State.BLOCKED and run.plan.steps[1].state==State.BLOCKED
 assert run.plan.steps[1].error=='RuntimeError' and 'approval database' not in run.plan.steps[1].error
 assert sender.calls==0
 assert run.traces[-1].decision=='escalate'
