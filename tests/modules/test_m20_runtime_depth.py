"""Runtime-depth tests for the GCW (technical-spec rows 173-207 / M20-01..35).

Covers the durable sense-plan-act-evaluate runtime: persistent memory
systems, reviewed HTN method learning, bounded MCTS, tool selection,
sandbox policy and execution, fair concurrent scheduling, auto
retrospectives, and confidence calibration - mounted over HTTP and at the
store level, with failure paths.
"""
from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.modules.m20_general_cognitive_worker.mcts import BoundedMCTS
from app.modules.m20_general_cognitive_worker.persistence import (
    DurableSemanticMemory, DurableSkillLibrary, DurableWorkingMemory,
)
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.runtime_routes import bind_runtime, router
from app.modules.m20_general_cognitive_worker.safety import (
    ApprovalGateDecision, InMemoryApprovalGate, SandboxPolicy,
)
from app.modules.m20_general_cognitive_worker.sandbox import (
    ApiAllowRule, SandboxRunner, SandboxViolation, host_matches,
)
from app.modules.m20_general_cognitive_worker.schemas import (
    ActionRecord, ChunkType, EpisodeOutcome, HTNMethod, MemoryChunk, PlanNode, Risk,
    SemanticFact, Skill, SkillStatus, TaskState, ToolSpec,
)
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.tools import (
    ToolBlockedError, ToolRegistry,
)
from app.modules.m20_general_cognitive_worker.tool_selection import ToolSelector


class StubPlannerModel:
    def __init__(self, steps):
        self.steps = steps
        self.calls = 0

    def decompose(self, goal, *, context=""):
        self.calls += 1
        return list(self.steps)


def make_engine():
    # StaticPool: one shared in-memory connection, so a "restarted" runtime
    # on a second repository sees the first runtime's committed rows.
    return create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def make_runtime(*, model=None, gate=None, require_review=True, hydrate_repo=None):
    if hydrate_repo is not None:
        return GCWRuntime(hydrate_repo, planner_model=model, approval_gate=gate,
                          require_method_review=require_review)
    engine = make_engine()
    repo = GCWRepository(engine)
    repo.create_schema()
    return GCWRuntime(repo, planner_model=model, approval_gate=gate,
                      require_method_review=require_review), repo


def fresh_repo():
    engine = make_engine()
    repo = GCWRepository(engine)
    repo.create_schema()
    return repo


# -- M20-04 / M20-05: working memory depth + persistence ---------------------

def test_m20_04_working_memory_survives_restart_with_attention_order():
    repo = fresh_repo()
    wm = DurableWorkingMemory(repo, capacity=3)
    wm.put(MemoryChunk(type=ChunkType.FACT, content="quarterly revenue grew 12 percent",
                       salience=0.9), active_goal="revenue analysis", partition="p1")
    wm.put(MemoryChunk(type=ChunkType.QUESTION, content="which segment grew fastest",
                       salience=0.4), active_goal="revenue analysis", partition="p1")
    reloaded = DurableWorkingMemory.load(repo, capacity=3)
    assert len(reloaded) == 2
    focused = reloaded.focused(partition="p1")
    assert focused[0].content == "quarterly revenue grew 12 percent"
    assert all(c.context_id == "p1" for c in focused)


def test_m20_04_capacity_pruning_persists_and_partitions_isolate():
    repo = fresh_repo()
    wm = DurableWorkingMemory(repo, capacity=2)
    for i in range(3):
        wm.put(MemoryChunk(type=ChunkType.FACT, content=f"stale fact {i}", salience=0.1),
               active_goal="other", partition="a")
    wm.put(MemoryChunk(type=ChunkType.GOAL, content="goal of b", salience=1.0),
           active_goal="goal of b", partition="b")
    assert len(wm.focused(partition="a")) <= 2
    assert len(wm.focused(partition="b")) == 1  # M20-25: partition isolation
    reloaded = DurableWorkingMemory.load(repo, capacity=2)
    assert len(reloaded.focused(partition="a")) <= 2
    assert len(reloaded.focused(partition="b")) == 1
    wm.clear_partition("a")
    assert repo.list_chunks(partition="a") == []
    assert len(repo.list_chunks(partition="b")) == 1


# -- M20-06: episodic memory persistence and analogical recall ---------------

def test_m20_06_episodes_recall_after_reload():
    runtime, repo = make_runtime()
    runtime.episodic.log_execution(
        task_id="t1", goal="analyse competitor pricing",
        actions=[ActionRecord(tool="web_search", result_summary="ok")],
        outcome=EpisodeOutcome.SUCCEEDED, reflection="pricing grid worked",
    )
    restored = GCWRuntime(repo)
    hits = restored.episodic.recall_similar("competitor pricing analysis", limit=1)
    assert hits and hits[0][0].goal == "analyse competitor pricing"
    assert hits[0][0].outcome == EpisodeOutcome.SUCCEEDED


# -- M20-07: semantic memory facts, edges, decay ------------------------------

def test_m20_07_facts_edges_and_decay_survive_reload():
    repo = fresh_repo()
    memory = DurableSemanticMemory(repo)
    fact = memory.remember("Acme raised prices in June", confidence=0.9, decay_rate=2.0)
    concept = memory.remember("Acme pricing strategy", kind="concept")
    memory.link(fact.id, "about", concept.id)
    reloaded = DurableSemanticMemory.load(repo)
    neighbours = reloaded.neighbors(fact.id, relation="about")
    assert len(neighbours) == 1 and neighbours[0].to_id == concept.id
    assert reloaded.freshness(fact.id) < 0.9
    reloaded.confirm(fact.id)
    assert repo.list_facts()


# -- M20-08 / M20-09: procedural memory, reviewed skill proposals -------------

def test_m20_08_09_skills_persist_and_proposals_need_activation():
    repo = fresh_repo()
    library = DurableSkillLibrary(repo)
    library.compile("pricing-report", "analyse competitor pricing",
                    [ActionRecord(tool="web_search"), ActionRecord(tool="python_sandbox")])
    runtime, _ = make_runtime()
    episode = runtime.episodic.log_execution(
        task_id="t2", goal="analyse competitor pricing",
        actions=[ActionRecord(tool="web_search"), ActionRecord(tool="python_sandbox")],
        outcome=EpisodeOutcome.SUCCEEDED,
    )
    episode2 = runtime.episodic.log_execution(
        task_id="t3", goal="analyse competitor pricing again",
        actions=[ActionRecord(tool="web_search"), ActionRecord(tool="python_sandbox")],
        outcome=EpisodeOutcome.SUCCEEDED,
    )
    proposals = library.propose_from_episodes(
        [episode, episode2], min_occurrences=2,
    )
    # repeated successful pattern proposed, never silently activated (M20-09)
    assert len(proposals) == 1
    assert proposals[0].status == SkillStatus.PROPOSED
    assert repo.list_skills(status="proposed")
    reloaded = DurableSkillLibrary.load(repo)
    match = reloaded.match("analyse competitor pricing")
    assert match and match[0].name == "pricing-report"
    assert match[0].status == SkillStatus.ACTIVE
    # human review activates the proposal
    reloaded.activate(proposals[0].id)
    assert repo.list_skills(status="proposed") == []
    assert repo.list_skills(status="active")


# -- M20-10 / M20-11: HTN reuse and reviewed learned-method persistence -------

def test_m20_10_11_learned_methods_require_review_before_reuse():
    model = StubPlannerModel([{"title": "step one"}, {"title": "step two"}])
    runtime, repo = make_runtime(model=model)
    planner = runtime.planner
    planner.decompose("draft a launch announcement")
    learned = [m for m in planner.methods.values() if m.name.startswith("learned:")]
    assert len(learned) == 1
    assert planner.method_status(learned[0].name) == "proposed"
    planner.decompose("draft a launch announcement")
    assert model.calls == 2  # proposed method cannot match yet
    planner.activate_method(learned[0].name)
    planner.decompose("draft a launch announcement")
    assert model.calls == 2  # reviewed method now matches
    restored = GCWRuntime(repo, planner_model=model, require_method_review=True)
    assert restored.planner.method_status(learned[0].name) == "active"


def test_m20_10_invalid_decomposition_rejected():
    runtime, _ = make_runtime(model=StubPlannerModel([{"title": "x", "risk": "bogus"}]))
    from app.modules.m20_general_cognitive_worker.htn_planner import PlanError

    with pytest.raises(PlanError):
        runtime.planner.decompose("anything novel")


# -- M20-12..15: mounted loop, bounded cadence, persistence -------------------

@pytest.fixture()
def mounted():
    gate = InMemoryApprovalGate()
    runtime, repo = make_runtime(gate=gate)

    async def search(args):
        return {"results": ["competitor A raised prices"]}

    runtime.tools.register(ToolSpec(
        name="web_search", description="search the public web",
        risk=Risk.READ, capabilities=["search", "research"],
    ), search)
    runtime.planner.register_method(HTNMethod(
        name="market-scan", goal_pattern="scan competitor market and summarise",
        subtasks=[
            PlanNode(title="research competitors", tool="web_search", risk=Risk.READ),
            PlanNode(title="summarise findings", depends_on=["research competitors"]),
        ],
    ))
    app = FastAPI()
    app.include_router(router)
    bind_runtime(runtime)
    return TestClient(app), runtime, repo, gate


def test_m20_12_goal_lifecycle_over_mounted_http(mounted):
    client, runtime, repo, _ = mounted
    created = client.post("/api/modules/20/runtime/tasks",
                          json={"goal": "scan competitor market and summarise"})
    assert created.status_code == 201
    body = created.json()
    assert body["state"] == "succeeded"
    task = client.get(f"/api/modules/20/runtime/tasks/{body['task_id']}")
    assert task.status_code == 200
    assert [n["state"] for n in task.json()["plan"]] == ["succeeded", "succeeded"]
    # durable: episodes and traces landed in the repository
    assert repo.list_episodes(task_id=body["task_id"])
    assert repo.list_traces(task_id=body["task_id"])


def test_m20_15_bounded_cadence_ticks(mounted):
    client, runtime, repo, _ = mounted
    model = StubPlannerModel([{"title": f"reasoning step {i}"} for i in range(6)])
    runtime.planner.model = model
    created = client.post("/api/modules/20/runtime/tasks",
                          json={"goal": "novel unplanned goal", "run_immediately": False})
    task_id = created.json()["task_id"]
    first = client.post(f"/api/modules/20/runtime/tasks/{task_id}/step",
                        json={"max_ticks": 2})
    done_after_first = sum(1 for n in first.json()["plan"] if n["state"] == "succeeded")
    assert done_after_first <= 2
    for _ in range(3):
        client.post(f"/api/modules/20/runtime/tasks/{task_id}/step", json={"max_ticks": 2})
    final = client.get(f"/api/modules/20/runtime/tasks/{task_id}")
    assert final.json()["state"] == "succeeded"


def test_m20_15_unknown_task_404(mounted):
    client, *_ = mounted
    assert client.get("/api/modules/20/runtime/tasks/nope").status_code == 404
    assert client.post("/api/modules/20/runtime/tasks/nope/close").status_code == 404
    assert client.get("/api/modules/20/runtime/tasks/nope/mcts").status_code == 404


# -- M20-13 / M20-26: decision artifact without hidden chain-of-thought -------

def test_m20_13_26_decision_artifact_lists_alternatives_no_cot(mounted):
    client, runtime, *_ = mounted
    created = client.post("/api/modules/20/runtime/tasks",
                          json={"goal": "scan competitor market and summarise",
                                "run_immediately": False})
    task_id = created.json()["task_id"]
    artifact = client.get(f"/api/modules/20/runtime/tasks/{task_id}/decision")
    assert artifact.status_code == 200
    body = artifact.json()
    assert body["alternatives"], "expected evaluated alternatives"
    top = body["chosen"]
    assert {"information_gain", "cost", "progress_probability", "score"} <= set(top)
    assert "chain_of_thought" not in body and "chain" not in body["basis"]


# -- M20-16: bounded MCTS -------------------------------------------------------

def test_m20_16_mcts_bounded_typed_and_deterministic(mounted):
    client, runtime, *_ = mounted
    created = client.post("/api/modules/20/runtime/tasks",
                          json={"goal": "scan competitor market and summarise",
                                "run_immediately": False})
    task_id = created.json()["task_id"]
    result = client.get(f"/api/modules/20/runtime/tasks/{task_id}/mcts?simulations=24")
    assert result.status_code == 200
    body = result.json()
    assert body["simulations_run"] <= 24
    assert body["stopped_by"] in {"simulation_budget", "time_budget"}
    assert body["best_action_title"] == "research competitors"  # only ready step
    assert body["action_stats"][0]["visits"] > 0
    assert 0.0 <= body["root_value"] <= 1.0
    again = client.get(f"/api/modules/20/runtime/tasks/{task_id}/mcts?simulations=0")
    assert again.status_code == 422


def test_m20_16_mcts_terminal_plan_returns_no_action():
    plan = [PlanNode(title="done", state=TaskState.SUCCEEDED)]
    result = BoundedMCTS(max_simulations=8, seed=1).search(plan)
    assert result.best_action_id is None and result.simulations_run == 0
    assert result.root_value == 1.0


# -- M20-17: tool selection with uncertainty -------------------------------------

def test_m20_17_tool_selection_scores_and_ambiguity():
    registry = ToolRegistry()

    async def noop(args):
        return {}

    registry.register(ToolSpec(
        name="web_search", description="search the public web for information",
        risk=Risk.READ, capabilities=["search", "research"],
    ), noop)
    registry.register(ToolSpec(
        name="send_email", description="send an email to a person",
        risk=Risk.EXTERNAL, capabilities=["email", "send"],
    ), noop)
    selector = ToolSelector(registry)
    choice = selector.select("research public information")
    assert choice.chosen is not None and choice.chosen.tool_name == "web_search"
    assert choice.chosen.capability_match > 0
    selector.record_outcome("web_search", False)
    selector.record_outcome("web_search", False)
    assert selector.historical_success("web_search") < 0.5


def test_m20_17_precondition_failure_and_ambiguity_paths():
    registry = ToolRegistry()

    async def noop(args):
        return {}

    registry.register(ToolSpec(
        name="api_a", description="query the external api", risk=Risk.READ,
        capabilities=["api"], preconditions=["network"],
    ), noop)
    selector = ToolSelector(registry)
    blocked = selector.select("query the api", context={})
    assert blocked.chosen is None and blocked.needs_clarification
    assert "network" in blocked.clarifying_question
    allowed = selector.select("query the api", context={"network": True})
    assert allowed.chosen is not None and allowed.chosen.tool_name == "api_a"

    registry2 = ToolRegistry()
    for name in ("search_alpha", "search_beta"):
        registry2.register(ToolSpec(
            name=name, description="search the public web",
            risk=Risk.READ, capabilities=["search"],
        ), noop)
    ambiguous = ToolSelector(registry2).select("search the web")
    assert ambiguous.needs_clarification and ambiguous.chosen is None
    assert "search_alpha" in ambiguous.clarifying_question or "search_beta" in ambiguous.clarifying_question


# -- M20-18 / M20-21 / M20-35: sandbox policy and execution ----------------------

def test_m20_18_sandbox_executes_real_python(tmp_path):
    runner = SandboxRunner(SandboxPolicy(), workspace_root=str(tmp_path))
    result = runner.run_python("proj-1", "print(2 + 2)")
    assert result.returncode == 0 and result.stdout.strip() == "4"


def test_m20_35_network_denied_by_default(tmp_path):
    runner = SandboxRunner(SandboxPolicy(), workspace_root=str(tmp_path))
    result = runner.run_python(
        "proj-1", "import socket; socket.create_connection(('example.com', 80))",
    )
    assert result.returncode != 0
    assert "sandbox" in result.stderr and "network" in result.stderr


def test_m20_35_timeout_kills_runaway_code(tmp_path):
    runner = SandboxRunner(SandboxPolicy(), workspace_root=str(tmp_path))
    result = runner.run_python("proj-1", "while True: pass", timeout_seconds=1)
    assert result.timed_out


def test_m20_21_path_containment_blocks_escapes(tmp_path):
    runner = SandboxRunner(SandboxPolicy(), workspace_root=str(tmp_path))
    with pytest.raises(SandboxViolation):
        runner.resolve_path("proj-1", "../../etc/passwd")
    volume = runner.project_volume("proj-1")
    os.symlink("/etc", os.path.join(volume, "escape"))
    with pytest.raises(SandboxViolation):
        runner.resolve_path("proj-1", "escape/passwd")
    ok = runner.resolve_path("proj-1", "data/results.csv")
    assert ok.startswith(runner.project_volume("proj-1"))


def test_m20_22_api_allowlist_and_host_rules(tmp_path):
    runner = SandboxRunner(
        SandboxPolicy(network_enabled=True, allowed_hosts=frozenset({"api.example.com"})),
        workspace_root=str(tmp_path),
        api_allowlist=[ApiAllowRule("GET", "api.example.com", "/v1/")],
    )
    assert runner.check_api("GET", "api.example.com", "/v1/prices") == []
    assert runner.check_api("POST", "api.example.com", "/v1/prices")
    assert runner.check_api("GET", "api.example.com", "/admin")
    assert runner.check_host("evil.example.org")
    assert host_matches("sub.example.com", "*.example.com")
    assert not host_matches("example.com", "*.example.com")


def test_m20_35_mounted_sandbox_violation_is_403(mounted):
    client, runtime, *_ = mounted
    blocked = client.post("/api/modules/20/runtime/sandbox/run",
                          json={"project_id": "p", "code": "pass",
                                "allowed_hosts": ["unlisted.example"]})
    assert blocked.status_code == 403
    ok = client.post("/api/modules/20/runtime/sandbox/run",
                     json={"project_id": "p", "code": "print('hi')"})
    assert ok.status_code == 200 and ok.json()["stdout"].strip() == "hi"


# -- M20-23 / M20-24: fair concurrent scheduling --------------------------------

def test_m20_23_24_fair_scheduler_round_robin_and_starvation():
    from datetime import datetime, timedelta, timezone

    from app.modules.m20_general_cognitive_worker.scheduler import FairContextScheduler
    from app.modules.m20_general_cognitive_worker.schemas import TaskContext

    scheduler = FairContextScheduler()
    contexts = [TaskContext(goal=f"goal {i}", importance=3) for i in range(3)]
    for ctx in contexts:
        scheduler.add(ctx)
    served = [scheduler.next_context().id for _ in range(3)]
    assert set(served) == {c.id for c in contexts}
    assert all(c.ticks_served == 1 for c in contexts)
    stale = TaskContext(goal="old goal", importance=1,
                        created_at=datetime.now(timezone.utc) - timedelta(hours=2))
    scheduler.add(stale)
    report = scheduler.starvation_report(threshold_minutes=30)
    assert any(r["context_id"] == stale.id for r in report)


def test_m20_24_deadline_urgency_wins():
    from datetime import datetime, timedelta, timezone

    from app.modules.m20_general_cognitive_worker.scheduler import FairContextScheduler
    from app.modules.m20_general_cognitive_worker.schemas import TaskContext

    scheduler = FairContextScheduler()
    urgent = TaskContext(goal="urgent", importance=3,
                         deadline=datetime.now(timezone.utc) + timedelta(minutes=5))
    relaxed = TaskContext(goal="relaxed", importance=3)
    scheduler.add(relaxed)
    scheduler.add(urgent)
    assert scheduler.next_context().id == urgent.id


# -- M20-28: retrospectives -----------------------------------------------------

def test_m20_28_close_generates_persisted_idempotent_retrospective(mounted):
    client, runtime, repo, _ = mounted
    created = client.post("/api/modules/20/runtime/tasks",
                          json={"goal": "scan competitor market and summarise"})
    task_id = created.json()["task_id"]
    closed = client.post(f"/api/modules/20/runtime/tasks/{task_id}/close")
    assert closed.status_code == 200
    retro = closed.json()["retrospective"]
    assert retro["went_well"] and retro["lessons"]
    again = client.post(f"/api/modules/20/runtime/tasks/{task_id}/close")
    assert again.json()["idempotent"] is True
    # durable: a fresh runtime over the same repo retrieves it by similarity
    restored = GCWRuntime(repo)
    lessons = restored.retrospectives.lessons_for("competitor market scan", limit=1)
    assert lessons and lessons[0][0].task_id == task_id
    listed = client.get("/api/modules/20/runtime/retrospectives")
    assert any(r["task_id"] == task_id for r in listed.json())


# -- M20-30: confidence calibration ---------------------------------------------

def test_m20_30_expectations_resolve_and_calibration_persists(mounted):
    client, runtime, repo, _ = mounted
    created = client.post("/api/modules/20/runtime/tasks",
                          json={"goal": "scan competitor market and summarise"})
    task_id = created.json()["task_id"]
    runtime.close(task_id)
    resolved = [c for c in runtime.calibration.claims.values() if c.resolved]
    assert resolved, "expectations should resolve at close"
    report = client.get("/api/modules/20/runtime/calibration").json()
    assert report["resolved"] == len(resolved)
    restored = GCWRuntime(repo)
    assert len(restored.calibration.claims) == len(runtime.calibration.claims)


def test_m20_30_calibration_curve_and_shrinkage():
    runtime, _ = make_runtime()
    for i in range(6):
        claim = runtime.calibration.assess_claim(f"claim {i}", 0.9, evidence_count=3)
        runtime.calibration.resolve(claim.id, i % 2 == 0)
    curve = runtime.calibration.calibration_curve()
    assert curve and abs(curve[0]["observed_accuracy"] - 0.5) < 1e-9
    assert runtime.calibration.calibration_error() is not None
    assert runtime.calibration.adjusted_confidence(0.9) < 0.9


def test_m20_14_surprise_triggers_reflection(mounted):
    client, runtime, repo, _ = mounted

    async def failing(args):
        raise RuntimeError("tool exploded")

    runtime.tools.register(ToolSpec(
        name="flaky", description="flaky tool", risk=Risk.READ,
    ), failing)
    runtime.planner.register_method(HTNMethod(
        name="flaky-method", goal_pattern="run the flaky step",
        subtasks=[PlanNode(title="flaky step", tool="flaky", risk=Risk.READ,
                           max_attempts=1)],
    ))
    created = client.post("/api/modules/20/runtime/tasks",
                          json={"goal": "run the flaky step"})
    assert created.json()["state"] == "failed"
    traces = [t for t in repo.list_traces(task_id=created.json()["task_id"])
              if t.phase == "reflect"]
    assert any("surprise" in t.detail for t in traces)
    questions = [c for c in runtime.working_memory.focused(partition=created.json()["task_id"])
                 if c.type == ChunkType.QUESTION]
    assert any("surprise" in c.content for c in questions)


# -- M20-34: constitutional rules ------------------------------------------------

def test_m20_34_constitutional_block_and_financial_gating():
    import asyncio

    from app.modules.m20_general_cognitive_worker.safety import requires_approval

    runtime, _ = make_runtime()

    async def evil(args):
        return {}

    runtime.tools.register(ToolSpec(
        name="post", description="post publicly", risk=Risk.EXTERNAL,
    ), evil)
    with pytest.raises(ToolBlockedError):
        asyncio.run(runtime.dispatcher.dispatch(
            "post", {"text": "impersonate the CEO"}, task_id="t",
        ))
    # money gates even when the caller mislabels the risk tier
    assert requires_approval("payment", Risk.READ, {}) is True


# -- tenant boundaries -------------------------------------------------------------

def test_tenant_isolation_across_repositories():
    engine = make_engine()
    repo_a = GCWRepository(engine, tenant_id="tenant-a")
    repo_b = GCWRepository(engine, tenant_id="tenant-b")
    repo_a.create_schema()
    from app.modules.m20_general_cognitive_worker.schemas import TaskContext

    ctx = TaskContext(goal="tenant a work", tenant_id="tenant-a")
    repo_a.save_task(ctx)
    repo_a.save_fact(SemanticFact(content="tenant a fact"))
    assert repo_b.load_task(ctx.id) is None
    assert repo_b.list_tasks() == []
    assert repo_b.list_facts() == []
    assert repo_a.load_task(ctx.id) is not None
    with pytest.raises(PermissionError):
        repo_b.save_task(ctx)
