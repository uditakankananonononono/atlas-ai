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
    # 20 read steps at 0.9 info gain each: budget 5 seconds caps ticks
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
