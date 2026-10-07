import pytest
from sqlalchemy import create_engine
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService
from app.modules.m20_general_cognitive_worker.schemas import TaskContext,PlanNode,TaskState,ToolSpec,Risk,ApprovalGateDecision
from app.modules.m20_general_cognitive_worker.safety import InMemoryApprovalGate
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository

def wire(svc,calls):
 async def effect_then_timeout(args):calls.append(args);raise TimeoutError('fixture effect happened, response lost')
 svc.tools.register(ToolSpec(name='fixture_effect',description='local fake effect',risk=Risk.EXTERNAL,max_retries=3),effect_then_timeout)

def execute(svc):
 ctx=TaskContext(goal='fixture',plan=[PlanNode(title='fixture effect',tool='fixture_effect',max_attempts=3)])
 svc.loop.start(ctx);assert ctx.state==TaskState.WAITING_APPROVAL
 token=ctx.plan[0].approval_id;svc.safety.approvals.decide(token,ApprovalGateDecision.APPROVED)
 svc.loop.resume_after_approval(ctx,ctx.plan[0].id,True)
 return ctx

def test_effect_unknown_blocks_before_reflection_or_fresh_approval():
 calls=[];gate=InMemoryApprovalGate();svc=CognitiveWorkerService(approval_gate=gate);wire(svc,calls)
 ctx=execute(svc)
 assert calls==[{}] and ctx.state==TaskState.BLOCKED and ctx.plan[0].outcome_unknown
 assert svc.dispatcher.records[-1].outcome_unknown and not svc.dispatcher.records[-1].succeeded
 attempts=ctx.plan[0].attempts
 for action in [lambda:svc.loop.run(ctx),lambda:svc.loop.start(ctx),lambda:svc.loop.resume_after_approval(ctx,ctx.plan[0].id,True)]:
  action();assert ctx.state==TaskState.BLOCKED and len(calls)==1 and ctx.plan[0].attempts==attempts
 assert not any(t.phase=='reflect' for t in svc.loop.traces)

def test_persisted_unknown_survives_actual_sqlite_restart_and_manual_run(tmp_path):
 engine=create_engine(f'sqlite:///{tmp_path / "unknown.db"}');repo=GCWRepository(engine);repo.create_schema()
 calls=[];runtime=GCWRuntime(repo,approval_gate=InMemoryApprovalGate());wire(runtime,calls);ctx=execute(runtime);repo.save_task(ctx)
 engine.dispose();fresh_engine=create_engine(f'sqlite:///{tmp_path / "unknown.db"}');fresh=GCWRuntime(GCWRepository(fresh_engine),approval_gate=InMemoryApprovalGate());wire(fresh,calls)
 loaded=fresh.run_task(ctx.id)
 assert loaded.state==TaskState.BLOCKED and loaded.plan[0].outcome_unknown and len(calls)==1
 fresh.resume(ctx.id,loaded.plan[0].id,approved=True)
 assert len(calls)==1 and fresh.repo.load_task(ctx.id).plan[0].outcome_unknown
 fresh_engine.dispose()
