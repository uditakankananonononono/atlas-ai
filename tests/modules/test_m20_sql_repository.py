"""Chunk 4 tests: durable SQL persistence (sql_repository pattern)."""
import pytest
from sqlalchemy import create_engine

from app.modules.m20_general_cognitive_worker.schemas import (
    ActionRecord, Episode, EpisodeOutcome, PlanNode, Risk, SemanticFact, Skill,
    SkillStatus, TaskContext, TaskState, TraceEntry,
)
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository


@pytest.fixture()
def repo():
    engine = create_engine("sqlite:///:memory:")
    repository = GCWRepository(engine)
    repository.create_schema()
    return repository


def test_task_roundtrip_with_plan(repo):
    ctx = TaskContext(goal="persist me", importance=5,
                      plan=[PlanNode(title="step one", tool="web_search", risk=Risk.READ),
                            PlanNode(title="step two")])
    ctx.plan[1].depends_on = [ctx.plan[0].id]
    ctx.state = TaskState.RUNNING
    ctx.standup_notes = ["made progress"]
    repo.save_task(ctx)
    loaded = repo.load_task(ctx.id)
    assert loaded is not None
    assert loaded.goal == "persist me" and loaded.state == TaskState.RUNNING
    assert loaded.plan[1].depends_on == [loaded.plan[0].id]
    assert loaded.standup_notes == ["made progress"]
    # update path
    ctx.state = TaskState.SUCCEEDED
    repo.save_task(ctx)
    assert repo.load_task(ctx.id).state == TaskState.SUCCEEDED
    assert repo.load_task("missing") is None
    running = repo.list_tasks(state="succeeded")
    assert len(running) == 1


def test_episode_fact_skill_trace_roundtrips(repo):
    ctx = TaskContext(goal="parent task")
    repo.save_task(ctx)
    repo.save_episode(Episode(
        task_id=ctx.id, goal="did things",
        actions=[ActionRecord(tool="web_search", result_summary="ok")],
        outcome=EpisodeOutcome.SUCCEEDED, reflection="went fine",
    ))
    episodes = repo.list_episodes(task_id=ctx.id)
    assert len(episodes) == 1 and episodes[0].actions[0].tool == "web_search"

    repo.save_fact(SemanticFact(
        content="durable fact", decay_rate=1.0, provenance={"source": "test"},
    ))
    facts = repo.list_facts()
    assert facts[0].content == "durable fact" and facts[0].decay_rate == 1.0

    skill = Skill(name="s", goal_pattern="g", steps=[ActionRecord(tool="t")],
                  status=SkillStatus.ACTIVE)
    repo.save_skill(skill)
    skill.version = 2
    repo.save_skill(skill)
    skills = repo.list_skills()
    assert len(skills) == 1 and skills[0].version == 2
    assert repo.list_skills(status="active") and repo.list_skills(status="retired") == []

    trace = TraceEntry(task_id=ctx.id, phase="decide", detail="chose step one",
                       policy_basis="spec 4.4")
    repo.save_trace(trace)
    traces = repo.list_traces(task_id=ctx.id)
    assert traces[0].detail == "chose step one"
    assert traces[0].policy_basis == "spec 4.4"
