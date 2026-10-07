"""Chunk 2 tests: deliberative loop end-to-end (spec 4.2.4)."""
import pytest

from app.modules.m20_general_cognitive_worker.episodic_memory import EpisodicMemory
from app.modules.m20_general_cognitive_worker.executive import DeliberativeLoop
from app.modules.m20_general_cognitive_worker.htn_planner import HTNPlanner
from app.modules.m20_general_cognitive_worker.safety import (
    ApprovalGateDecision, InMemoryApprovalGate, SafetyGate,
)
from app.modules.m20_general_cognitive_worker.schemas import (
    Budget, HTNMethod, PlanNode, Risk, TaskContext, TaskState, ToolSpec,
)
from app.modules.m20_general_cognitive_worker.semantic_memory import SemanticMemory
from app.modules.m20_general_cognitive_worker.skill_library import SkillLibrary
from app.modules.m20_general_cognitive_worker.tools import ToolDispatcher, ToolRegistry
from app.modules.m20_general_cognitive_worker.working_memory import WorkingMemory


def build_loop(approvals=None, planner_model=None):
    registry = ToolRegistry()
    calls = {"research": 0, "send": 0}

    async def research(args):
        calls["research"] += 1
        return {"findings": ["competitor A", "competitor B"]}

    async def send(args):
        calls["send"] += 1
        return {"sent": True}

    registry.register(ToolSpec(name="web_search", description="search", risk=Risk.READ), research)
    registry.register(ToolSpec(name="send_email", description="send", risk=Risk.EXTERNAL), send)
    gate = approvals or InMemoryApprovalGate()
    dispatcher = ToolDispatcher(registry, SafetyGate(approvals=gate))
    planner = HTNPlanner(model=planner_model)
    planner.register_method(HTNMethod(
        name="research-and-report",
        goal_pattern="research competitors and email the findings",
        subtasks=[
            PlanNode(title="research competitors", tool="web_search", risk=Risk.READ),
            PlanNode(title="email findings", tool="send_email", risk=Risk.EXTERNAL,
                     depends_on=["research competitors"]),
        ],
    ))
    loop = DeliberativeLoop(
        planner=planner, dispatcher=dispatcher,
        working_memory=WorkingMemory(), episodic=EpisodicMemory(),
        semantic=SemanticMemory(), skills=SkillLibrary(),
    )
    return loop, gate, calls


def test_full_loop_pauses_for_approval_then_resumes():
    loop, gate, calls = build_loop()
    ctx = TaskContext(goal="research competitors and email the findings", importance=4)
    ctx = loop.start(ctx)
    assert ctx.state == TaskState.WAITING_APPROVAL
    assert calls["research"] == 1 and calls["send"] == 0
    waiting = [n for n in ctx.plan if n.state == TaskState.WAITING_APPROVAL]
    assert len(waiting) == 1 and waiting[0].approval_id
    gate.decide(waiting[0].approval_id, ApprovalGateDecision.APPROVED)
    ctx = loop.resume_after_approval(ctx, waiting[0].id, approved=True)
    assert ctx.state == TaskState.SUCCEEDED
    assert calls["send"] == 1
    episodes = loop.episodic.for_task(ctx.id)
    assert episodes and episodes[0].outcome.value == "succeeded"
    phases = {t.phase for t in loop.traces}
    assert {"observe", "plan", "decide", "act", "evaluate"} <= phases
    approval_traces = [t for t in loop.traces if t.policy_basis]
    assert approval_traces, "approval gating must be visible in the trace"


def test_rejected_approval_blocks_task():
    loop, gate, calls = build_loop()
    ctx = loop.start(TaskContext(goal="research competitors and email the findings"))
    waiting = [n for n in ctx.plan if n.state == TaskState.WAITING_APPROVAL][0]
    gate.decide(waiting.approval_id, ApprovalGateDecision.REJECTED)
    ctx = loop.resume_after_approval(ctx, waiting.id, approved=False)
    assert ctx.state == TaskState.BLOCKED
    assert calls["send"] == 0


def test_constitutional_block_stops_execution():
    loop, gate, calls = build_loop()

    async def evil(args):
        return {}

    loop.dispatcher.registry.register(ToolSpec(
        name="engage", description="engage", risk=Risk.READ,
    ), evil)
    loop.planner.register_method(HTNMethod(
        name="astroturf", goal_pattern="boost our reviews",
        subtasks=[PlanNode(title="boost", tool="engage", risk=Risk.READ,
                           arguments={"plan": "create fake accounts to post fake reviews"})],
    ))
    ctx = loop.start(TaskContext(goal="boost our reviews please"))
    assert ctx.state == TaskState.BLOCKED
    assert any("blocked" in t.detail for t in loop.traces if t.phase == "act")


def test_budget_bound_and_episode_closure():
    loop, _, _ = build_loop()
    loop.planner.register_method(HTNMethod(
        name="infinite", goal_pattern="loop forever task",
        subtasks=[PlanNode(title=f"step{i}", tool="web_search", risk=Risk.READ) for i in range(20)],
    ))
    ctx = TaskContext(goal="loop forever task")
    ctx = loop.start(ctx)
    # Separate wall-time and tick bounds; completion is not output correctness.
    ctx2 = loop.run(ctx, budget=Budget(seconds=3))
    assert ctx2.state in (TaskState.FAILED, TaskState.SUCCEEDED)
    assert loop.episodic.for_task(ctx.id), "episode must be logged even on budget exhaustion"


def test_rumination_trace():
    loop, _, _ = build_loop()
    ctx = TaskContext(goal="research competitors and email the findings")
    ctx.plan = loop.planner.decompose(ctx.goal)
    result = loop.ruminate(ctx)  # all nodes still pending
    assert result["simulations"] > 0
    assert result["best_ordering"]
    assert any(t.phase == "ruminate" for t in loop.traces)


def test_untooled_plan_node_never_succeeds_without_actual_reasoning_model():
 loop,_,_=build_loop()
 ctx=TaskContext(goal='prove unsolved claim',plan=[PlanNode(title='derive a proof')])
 out=loop.start(ctx)
 assert out.state==TaskState.BLOCKED
 assert out.plan[0].state==TaskState.BLOCKED
 assert 'unavailable' in out.plan[0].result_summary
 assert not any(e.outcome.value=='succeeded' for e in loop.episodic.for_task(ctx.id))


def test_model_reasoning_requires_nonempty_result_and_retains_actual_output():
 class Model:
  def complete(self,purpose,payload):
   assert purpose=='reason' and payload['step']=='compute a simple answer'
   return {'available':True,'result':'The requested arithmetic result is 4.'}
 loop,_,_=build_loop();loop.model=Model()
 ctx=TaskContext(goal='arithmetic',plan=[PlanNode(title='compute a simple answer')])
 out=loop.start(ctx)
 assert out.state==TaskState.SUCCEEDED
 assert out.plan[0].result_summary=='The requested arithmetic result is 4.'


@pytest.mark.parametrize('response',[{'available':False,'result':'text'}, {'available':True}, {'result':''}, {'result':None}, 'plausible prose'])
def test_invalid_or_unavailable_reasoning_response_never_marks_success(response):
 class Model:
  def complete(self,*args,**kwargs):return response
 loop,_,_=build_loop();loop.model=Model()
 out=loop.start(TaskContext(goal='x',plan=[PlanNode(title='think')]))
 assert out.state==TaskState.BLOCKED and out.plan[0].state==TaskState.BLOCKED


@pytest.mark.parametrize('state',[TaskState.SUCCEEDED,TaskState.CANCELLED])
def test_start_does_not_trust_incoming_terminal_state_without_execution(state):
 loop,_,_=build_loop()
 out=loop.start(TaskContext(goal='x',plan=[PlanNode(title='think',state=state)]))
 assert out.state==TaskState.BLOCKED and out.plan[0].state==TaskState.BLOCKED


def test_run_all_cancelled_plan_never_reports_success():
 loop,_,_=build_loop()
 out=loop.run(TaskContext(goal='x',plan=[PlanNode(title='cancelled',state=TaskState.CANCELLED)]))
 assert out.state==TaskState.BLOCKED


def test_successful_unrelated_tool_never_confirms_title_similar_fact():
 from app.modules.m20_general_cognitive_worker.schemas import ActionRecord
 loop,_,_=build_loop()
 fact=loop.semantic.remember('research competitors',confidence=.1)
 before=fact.last_confirmed_at
 node=PlanNode(title='research competitors',tool='web_search')
 context=TaskContext(goal='research competitors')
 record=ActionRecord(tool='web_search',succeeded=True)
 loop._evaluate_expectation(context,node,record)
 assert loop.semantic.get(fact.id).last_confirmed_at==before
 assert any('no contradiction/confirmation inferred' in t.detail for t in loop.traces)
 assert not any('fact contradicted' in t.detail for t in loop.traces)


def test_shared_dispatcher_episodes_are_task_scoped_and_detached():
 loop,_,_=build_loop()
 a=loop.start(TaskContext(goal='a',plan=[PlanNode(title='a',tool='web_search',arguments={'fixture':'a'})]))
 b=loop.start(TaskContext(goal='b',plan=[PlanNode(title='b',tool='web_search',arguments={'fixture':'b'})]))
 assert a.state==b.state==TaskState.SUCCEEDED
 a_episode=loop.episodic.for_task(a.id)[0];b_episode=loop.episodic.for_task(b.id)[0]
 assert [x.arguments for x in a_episode.actions]==[{'fixture':'a'}]
 assert [x.arguments for x in b_episode.actions]==[{'fixture':'b'}]
 assert {x.task_id for x in b_episode.actions}=={b.id}
 loop.dispatcher.records[-1].arguments['fixture']='changed'
 assert b_episode.actions[0].arguments=={'fixture':'b'}


def test_wall_time_boundary_is_not_a_tick_count_and_stops_between_steps(monkeypatch):
 from app.modules.m20_general_cognitive_worker import executive
 loop,_,calls=build_loop();clock=iter([0,0,.2]);monkeypatch.setattr(executive,'monotonic',lambda:next(clock))
 context=TaskContext(goal='fixture',plan=[PlanNode(title='a',tool='web_search'),PlanNode(title='b',tool='web_search')])
 loop.run(context,budget=Budget(seconds=.1))
 assert calls['research']==1 and loop.last_ticks_run==1
 assert context.state==TaskState.FAILED


def test_scheduler_wall_quantum_yields_instead_of_false_failure(monkeypatch):
 from app.modules.m20_general_cognitive_worker import executive
 loop,_,calls=build_loop();clock=iter([0,0,.2]);monkeypatch.setattr(executive,'monotonic',lambda:next(clock))
 context=TaskContext(goal='fixture',plan=[PlanNode(title='a',tool='web_search'),PlanNode(title='b',tool='web_search')])
 loop.run(context,budget=Budget(seconds=.1),yield_on_boundary=True)
 assert calls['research']==1 and context.state==TaskState.RUNNING and loop.last_ticks_run==1
 assert not loop.episodic.for_task(context.id)


def test_optional_reflection_error_never_overwrites_tool_failure_or_escapes():
 loop,_,_=build_loop();calls=[]
 class BrokenReflection:
  def complete(self,purpose,payload):
   calls.append(purpose);raise RuntimeError('synthetic model failure')
 loop.model=BrokenReflection()
 async def fail(args):raise RuntimeError('synthetic tool failure')
 loop.dispatcher.registry.register(ToolSpec(name='fixture_fail',description='fixture',max_retries=1),fail)
 context=TaskContext(goal='fixture',plan=[PlanNode(title='fail',tool='fixture_fail',max_attempts=1)])
 result=loop.start(context)
 assert result.state==TaskState.FAILED and calls==['reflect']
 assert len(loop.dispatcher.records)==1 and 'synthetic tool failure' in loop.dispatcher.records[0].result_summary
 assert any('reflection model error' in t.detail for t in loop.traces)
 assert loop.episodic.for_task(context.id)[0].outcome.value=='failed'


@pytest.mark.parametrize('response',[{'available':False,'cause':'x','fix':'y','retry':True}, {'cause':'','fix':'y','retry':True}, {'cause':'x','fix':'y','retry':'true'}, 'causal prose', None])
def test_invalid_reflection_is_labeled_unavailable_not_causal_analysis(response):
 loop,_,_=build_loop()
 class Model:
  def complete(self,*args,**kwargs):return response
 loop.model=Model()
 node=PlanNode(title='failure',tool='fixture',attempts=1,max_attempts=1)
 loop._reflect_on_failure(TaskContext(goal='fixture'),node,'fixture error')
 assert any('reflection unavailable or invalid' in t.detail for t in loop.traces)
 assert not any('model reflection hypothesis:' in t.detail for t in loop.traces)


def test_valid_reflection_remains_unverified_hypothesis_not_retry_execution():
 loop,_,_=build_loop()
 class Model:
  def complete(self,purpose,payload):return {'cause':'synthetic hypothesis','fix':'synthetic suggestion','retry':True}
 loop.model=Model();node=PlanNode(title='failure',tool='fixture',state=TaskState.FAILED,attempts=1,max_attempts=1)
 loop._reflect_on_failure(TaskContext(goal='fixture'),node,'fixture error')
 assert node.state==TaskState.FAILED and not loop.dispatcher.records
 assert any('model reflection hypothesis:' in t.detail and 'correctness unverified' in t.detail for t in loop.traces)


def test_plan_risk_escalation_requires_review_even_for_registered_read_tool():
 loop,gate,calls=build_loop()
 context=TaskContext(goal='fixture',plan=[PlanNode(title='elevated read',tool='web_search',risk=Risk.EXTERNAL)])
 out=loop.start(context)
 assert out.state==TaskState.WAITING_APPROVAL and calls['research']==0
 waiting=out.plan[0];gate.decide(waiting.approval_id,ApprovalGateDecision.APPROVED)
 assert loop.resume_after_approval(out,waiting.id,True).state==TaskState.SUCCEEDED
 assert calls['research']==1


@pytest.mark.parametrize("state", [TaskState.SUCCEEDED, TaskState.BLOCKED, TaskState.WAITING_APPROVAL])
def test_rumination_does_not_reactivate_terminal_or_waiting_context(state):
    loop, _, _ = build_loop()
    context = TaskContext(goal="inspect", state=state)
    loop.ruminate(context)
    assert context.state == state


def test_rumination_exception_restores_context_state():
    loop, _, _ = build_loop()
    context = TaskContext(goal="inspect", state=TaskState.RUNNING)
    def fail(plan):
        raise RuntimeError("rumination failed")
    loop.ruminator.ruminate = fail
    with pytest.raises(RuntimeError):
        loop.ruminate(context)
    assert context.state == TaskState.RUNNING
