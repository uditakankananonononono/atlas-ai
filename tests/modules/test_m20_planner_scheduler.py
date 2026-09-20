"""Chunk 2 tests: HTN planner, MCTS ruminator, context scheduler."""
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m20_general_cognitive_worker.executive import MCTSRuminator, MetaReasoner
from app.modules.m20_general_cognitive_worker.htn_planner import HTNPlanner, PlanError
from app.modules.m20_general_cognitive_worker.scheduler import ContextScheduler
from app.modules.m20_general_cognitive_worker.schemas import (
    HTNMethod, MethodSource, PlanNode, Risk, TaskContext, TaskState,
)


class FakePlannerModel:
    def __init__(self, steps):
        self.steps = steps
        self.calls = 0

    def decompose(self, goal, *, context=""):
        self.calls += 1
        return self.steps


def library_method():
    return HTNMethod(
        name="market-entry", goal_pattern="prepare market entry strategy analysis",
        subtasks=[
            PlanNode(title="research market", tool="web_search", risk=Risk.READ),
            PlanNode(title="draft report", tool="write_document", risk=Risk.REVERSIBLE,
                     depends_on=["research market"]),
        ],
    )


def test_library_method_match_and_reuse():
    planner = HTNPlanner()
    planner.register_method(library_method())
    plan = planner.decompose("prepare a market entry strategy for product X")
    assert len(plan) == 2
    assert plan[1].depends_on == [plan[0].id]
    assert planner.methods["market-entry"].times_used == 1


def test_de_novo_decomposition_learned_and_validated():
    model = FakePlannerModel([
        {"id": "a", "title": "gather data", "tool": "web_search", "risk": "read"},
        {"id": "b", "title": "analyze", "tool": "python_sandbox", "risk": "reversible", "depends_on": ["a"]},
    ])
    planner = HTNPlanner(model=model)
    plan = planner.decompose("analyze competitor pricing for textbooks")
    assert model.calls == 1
    assert plan[1].depends_on == ["a"]
    learned = [m for m in planner.methods.values() if m.source == MethodSource.LEARNED]
    assert len(learned) == 1
    plan2 = planner.decompose("analyze competitor pricing for textbooks")
    assert model.calls == 1  # second time hits the learned method
    assert len(plan2) == 2


def test_decompose_rejects_bad_models():
    planner = HTNPlanner(model=FakePlannerModel([]))
    with pytest.raises(PlanError):
        planner.decompose("goal")
    planner = HTNPlanner(model=FakePlannerModel([{"title": "x", "depends_on": ["ghost"]}]))
    with pytest.raises(PlanError):
        planner.decompose("goal")
    planner = HTNPlanner(model=FakePlannerModel([
        {"id": "a", "title": "a", "depends_on": ["b"]},
        {"id": "b", "title": "b", "depends_on": ["a"]},
    ]))
    with pytest.raises(PlanError):
        planner.decompose("goal")
    planner = HTNPlanner()
    with pytest.raises(PlanError):
        planner.decompose("goal with no method and no model")


def test_ready_nodes_and_deadlock():
    a = PlanNode(title="a")
    b = PlanNode(title="b", depends_on=[a.id])
    c = PlanNode(title="c", depends_on=[b.id], max_attempts=1)
    plan = [a, b, c]
    assert [n.title for n in HTNPlanner.ready_nodes(plan)] == ["a"]
    a.state = TaskState.SUCCEEDED
    assert [n.title for n in HTNPlanner.ready_nodes(plan)] == ["b"]
    b.state = TaskState.FAILED
    assert HTNPlanner.ready_nodes(plan) == []
    assert HTNPlanner.is_deadlocked(plan) is True
    c.state = TaskState.CANCELLED
    b.state = TaskState.SUCCEEDED
    assert HTNPlanner.is_complete(plan) is True


def test_meta_reasoner_prefers_high_gain_low_cost():
    meta = MetaReasoner()
    research = PlanNode(title="research competitors", tool="web_search", risk=Risk.READ)
    send = PlanNode(title="email results", tool="send_email", risk=Risk.EXTERNAL)
    scored = meta.score_candidates([send, research], wm_context="", ltm_hits=2)
    assert scored[0].node.title == "research competitors"
    assert scored[0].score > scored[1].score


def test_mcts_rumination_returns_ordering():
    a = PlanNode(title="research", risk=Risk.READ)
    b = PlanNode(title="draft", risk=Risk.REVERSIBLE, depends_on=[a.id])
    c = PlanNode(title="publish", risk=Risk.EXTERNAL, depends_on=[b.id])
    ruminator = MCTSRuminator(simulations=16, seed=1)
    result = ruminator.ruminate([a, b, c])
    assert result["simulations"] == 16
    assert result["best_ordering"] == ["research", "draft", "publish"]
    assert 0 < result["expected_success"] <= 1.0
    a.state = b.state = c.state = TaskState.SUCCEEDED
    assert ruminator.ruminate([a, b, c])["expected_success"] == 1.0


def test_scheduler_priority_and_round_robin():
    scheduler = ContextScheduler()
    now = datetime.now(timezone.utc)
    urgent = TaskContext(goal="urgent", importance=3, deadline=now + timedelta(minutes=10))
    important = TaskContext(goal="important", importance=5)
    background = TaskContext(goal="background", importance=1)
    for ctx in (urgent, important, background):
        scheduler.add(ctx)
    order = scheduler.order(now=now)
    assert order[0].goal == "urgent"  # deadline proximity beats importance delta
    assert order[-1].goal == "background"
    first = scheduler.next_context(now=now)
    assert first.goal == "urgent"
    urgent.state = TaskState.SUCCEEDED
    nxt = scheduler.next_context(now=now)
    assert nxt.goal == "important"
    load = scheduler.cognitive_load()
    assert abs(sum(load.values()) - 1.0) < 1e-6
    assert load[important.id] > load[background.id]
    done = TaskContext(goal="done", state=TaskState.SUCCEEDED)
    scheduler.add(done)
    assert done not in scheduler.active()
