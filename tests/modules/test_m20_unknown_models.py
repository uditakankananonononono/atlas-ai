import pytest
from app.core.providers import ProviderOutcomeUnknown
from app.modules.m20_general_cognitive_worker import model_adapters as ma
from app.modules.m20_general_cognitive_worker.htn_planner import HTNPlanner
from app.modules.m20_general_cognitive_worker.schemas import TaskContext,PlanNode,TaskState
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService as Service

def bind(monkeypatch):
 calls=[]
 async def unknown(*args,**kwargs):calls.append(args);raise ProviderOutcomeUnknown('fixture dispatched')
 monkeypatch.setattr(ma.model_catalog,'generate_free_first',unknown);return calls

def test_unknown_planning_is_classified_no_learned_method(monkeypatch):
 calls=bind(monkeypatch);planner=HTNPlanner(model=ma.FreeFirstPlannerModel())
 with pytest.raises(ma.PlannerOutcomeUnknown) as error:planner.decompose('fixture novel goal')
 assert error.value.outcome=='unknown' and error.value.retry_allowed is False
 assert len(calls)==1 and not planner.methods

@pytest.mark.parametrize('purpose',['reason','reflect'])
def test_unknown_adapter_never_becomes_ordinary_unavailable(monkeypatch,purpose):
 calls=bind(monkeypatch);out=ma.FreeFirstExecutiveModel().complete(purpose,{})
 assert out=={'available':False,'outcome':'unknown','retry_allowed':False,'error':'fixture dispatched'}
 assert len(calls)==1

def test_reasoning_unknown_blocks_step_and_scheduler_does_not_repeat(monkeypatch):
 calls=bind(monkeypatch);svc=Service(executive_model=ma.FreeFirstExecutiveModel())
 ctx=TaskContext(goal='fixture',plan=[PlanNode(title='fixture reason')]);svc.loop.start(ctx)
 assert ctx.state==TaskState.BLOCKED and ctx.plan[0].state==TaskState.BLOCKED
 assert 'outcome unknown' in ctx.plan[0].result_summary and len(calls)==1
 svc.scheduler.add(ctx)
 svc.tick();assert len(calls)==1 and ctx.state==TaskState.BLOCKED

def test_reflection_unknown_is_not_recorded_as_model_analysis(monkeypatch):
 calls=bind(monkeypatch);svc=Service(executive_model=ma.FreeFirstExecutiveModel());ctx=TaskContext(goal='fixture')
 node=PlanNode(title='fixture tool',tool='fixture',attempts=1,max_attempts=1)
 svc.loop._reflect_on_failure(ctx,node,'fixture error')
 assert len(calls)==1
 assert svc.loop.traces[-1].detail=='reflection generation outcome unknown; no automatic retry'

@pytest.mark.parametrize('phase',['planning','deferred_planning','reasoning'])
def test_runtime_api_persists_model_unknown_and_restart_manualrun_holds(tmp_path,monkeypatch,phase):
 from sqlalchemy import create_engine
 from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
 from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
 calls=bind(monkeypatch);url=f'sqlite:///{tmp_path / "model-unknown.db"}'
 engine=create_engine(url);repo=GCWRepository(engine);repo.create_schema()
 runtime=GCWRuntime(repo,planner_model=ma.FreeFirstPlannerModel(),executive_model=ma.FreeFirstExecutiveModel())
 if phase=='reasoning':
  ctx=TaskContext(goal='fixture',plan=[PlanNode(title='fixture reason')]);repo.save_task(ctx);ctx=runtime.run_task(ctx.id)
 else:ctx=runtime.submit_goal('fixture novel goal',run_immediately=phase!='deferred_planning')
 assert ctx.state==TaskState.BLOCKED and repo.load_task(ctx.id).model_outcome_unknown and len(calls)==1
 engine.dispose();fresh_engine=create_engine(url);fresh=GCWRuntime(GCWRepository(fresh_engine),planner_model=ma.FreeFirstPlannerModel(),executive_model=ma.FreeFirstExecutiveModel())
 result=fresh.run_task(ctx.id);assert result.state==TaskState.BLOCKED and result.model_outcome_unknown and len(calls)==1
 fresh_engine.dispose()
