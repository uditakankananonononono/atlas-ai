import pytest
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService
from app.modules.m20_general_cognitive_worker.schemas import TaskContext,PlanNode,TaskState

@pytest.mark.parametrize('state',[TaskState.SUCCEEDED,TaskState.FAILED,TaskState.BLOCKED,TaskState.PENDING,TaskState.RUNNING])
def test_resume_cannot_reexecute_nonwaiting_node(state):
 calls=[]
 class Model:
  def complete(self,*args):calls.append(args);return {'result':'fixture'}
 svc=CognitiveWorkerService(executive_model=Model());node=PlanNode(title='fixture',state=state,result_summary='existing');ctx=TaskContext(goal='fixture',state=TaskState.BLOCKED,plan=[node])
 with pytest.raises(ValueError,match='not waiting on approval'):svc.loop.resume_after_approval(ctx,node.id,True)
 assert calls==[] and node.state==state and node.result_summary=='existing' and ctx.state==TaskState.BLOCKED

def test_unknown_node_id_does_not_run_other_pending_nodes():
 svc=CognitiveWorkerService();ctx=TaskContext(goal='fixture',plan=[PlanNode(title='fixture')]);before=ctx.model_dump()
 with pytest.raises(ValueError,match='node not found'):svc.loop.resume_after_approval(ctx,'missing',True)
 assert ctx.model_dump()==before

def test_waiting_without_token_cannot_resume():
 svc=CognitiveWorkerService();node=PlanNode(title='fixture',state=TaskState.WAITING_APPROVAL);ctx=TaskContext(goal='fixture',plan=[node])
 with pytest.raises(ValueError,match='not waiting on approval'):svc.loop.resume_after_approval(ctx,node.id,True)
 assert node.state==TaskState.WAITING_APPROVAL
