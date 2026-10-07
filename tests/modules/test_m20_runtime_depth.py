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
    SemanticFact, Skill, SkillStatus, TaskContext, TaskState, ToolSpec, TraceEntry,
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
    assert reloaded.freshness(fact.id) is None
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
    planner.activate_method(learned[0].name,expected_hash=planner.method_review_hash(planner.methods[learned[0].name]))
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
    # Fixture output proves model invocation/wiring, not real model quality.
    class FixtureExecutiveModel:
        def complete(self, purpose, payload):
            if purpose == "reason":
                return {"available": True, "result": "fixture reasoning output for " + payload["step"]}
            return {"retry": False}
    runtime.loop.model = FixtureExecutiveModel()

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
    assert {"heuristic_information_weight", "cost", "heuristic_progress_weight", "score"} <= set(top)
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
    assert 0.0 <= body["heuristic_root_value"] <= 1.0
    again = client.get(f"/api/modules/20/runtime/tasks/{task_id}/mcts?simulations=0")
    assert again.status_code == 422


def test_m20_16_mcts_terminal_plan_returns_no_action():
    plan = [PlanNode(title="done", state=TaskState.SUCCEEDED)]
    result = BoundedMCTS(max_simulations=8, seed=1).search(plan)
    assert result.best_action_id is None and result.simulations_run == 0
    assert result.heuristic_root_value == 1.0


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
    # CPU rlimit can stop the process before the wall timeout fires.
    # Nonzero kill is not automatically a confirmed wall-timeout cause.
    assert result.returncode != 0
    assert result.duration_seconds < 5


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
    assert resolved==[], "no fitted success predictor; no invented expectation claims"
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
    assert runtime.calibration.adjusted_confidence(0.9) is None


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
                          json={"goal": "run the flaky step", "run_immediately": False})
    ctx=runtime.get_task(created.json()["task_id"])
    claim=runtime.calibration.assess_claim("caller prediction: flaky step succeeds", .9)
    ctx.plan[0].arguments["_expectation_claim_id"]=claim.id
    client.post(f"/api/modules/20/runtime/tasks/{ctx.id}/step",json={})
    assert runtime.get_task(ctx.id).state==TaskState.FAILED
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


def test_durable_working_memory_eviction_and_rejected_weak_chunk_never_resurrect():
 repo=fresh_repo();wm=DurableWorkingMemory(repo,capacity=1)
 strong=MemoryChunk(type=ChunkType.GOAL,content='fixture high',salience=1,confidence=1)
 weak=MemoryChunk(type=ChunkType.FACT,content='noise',salience=0,confidence=0)
 wm.put(strong,active_goal='fixture high',partition='p')
 wm.put(weak,active_goal='fixture high',partition='p')
 assert wm.get(weak.id) is None
 assert {x.id for x in repo.list_chunks()}=={strong.id}
 loaded=DurableWorkingMemory.load(repo,capacity=1)
 assert loaded.get(weak.id) is None and loaded.get(strong.id) is not None
 newer=MemoryChunk(type=ChunkType.GOAL,content='new fixture',salience=1,confidence=1)
 loaded.put(newer,active_goal='new fixture',partition='p')
 assert {x.id for x in repo.list_chunks()}=={newer.id}
 assert DurableWorkingMemory.load(repo,capacity=1).get(strong.id) is None


def test_scheduler_step_reports_actual_ticks_and_cooperative_time_scope():
 runtime,_=make_runtime()
 context=runtime.submit_goal('no model no method',run_immediately=False)
 report=runtime.step(quantum_seconds=.1,max_ticks=17)
 assert report.task_id==context.id and report.ticks_run==0
 assert report.budget_status=='cooperative_between_steps_only'
 assert report.hard_wall_time_enforced is report.tokens_money_enforced is False


def test_replanning_same_generated_cache_key_never_self_activates_review_required_method():
 model=StubPlannerModel([{'title':'fixture'}]);runtime,repo=make_runtime(model=model,require_review=True)
 for _ in range(3):runtime.planner.decompose('novel exact fixture',context='same')
 assert model.calls==3
 methods=[m for m in runtime.planner.methods.values() if m.name.startswith('learned:')]
 assert len(methods)==1
 assert runtime.planner.method_status(methods[0].name)=='proposed'
 assert all(status=='proposed' for method,status in repo.list_methods() if method.name.startswith('learned:'))


def test_method_activation_requires_exact_reviewed_revision_hash():
 model=StubPlannerModel([{'title':'old fixture'}]);runtime,repo=make_runtime(model=model)
 runtime.planner.decompose('fixture exact',context='same')
 method=next(iter(runtime.planner.methods.values()));reviewed=runtime.planner.method_review_hash(method)
 model.steps=[{'title':'replacement fixture'}];runtime.planner.decompose('fixture exact',context='same')
 with pytest.raises(PermissionError,match='revision'):runtime.planner.activate_method(method.name,expected_hash=reviewed)
 assert runtime.planner.method_status(method.name)=='proposed'
 current=runtime.planner.methods[method.name]
 assert runtime.planner.activate_method(method.name,expected_hash=runtime.planner.method_review_hash(current))


def test_method_http_review_hash_rejects_missing_and_stale_revision(mounted):
 client,runtime,repo,_=mounted
 model=StubPlannerModel([{'title':'old'}]);runtime.planner.model=model
 runtime.planner.decompose('novel review fixture',context='same')
 item=next(row for row in client.get('/api/modules/20/runtime/methods').json() if row['name'].startswith('learned:'))
 path='/api/modules/20/runtime/methods/'+item['name']+'/activate'
 assert client.post(path).status_code==422
 model.steps=[{'title':'new'}];runtime.planner.decompose('novel review fixture',context='same')
 assert client.post(path,json={'expected_hash':item['review_hash']}).status_code==409
 current=next(row for row in client.get('/api/modules/20/runtime/methods').json() if row['name']==item['name'])
 assert current['review_status']=='proposed'
 assert client.post(path,json={'expected_hash':current['review_hash']}).status_code==200
 assert dict((m.name,status) for m,status in repo.list_methods())[item['name']]=='active'


def test_method_same_name_replacements_update_one_durable_revision_and_restart():
 model=StubPlannerModel([{'title':'old'}]);runtime,repo=make_runtime(model=model)
 runtime.planner.decompose('restart review fixture',context='same')
 original=next(iter(runtime.planner.methods.values()))
 old_hash=runtime.planner.method_review_hash(original)
 model.steps=[{'title':'new'}];runtime.planner.decompose('restart review fixture',context='same')
 rows=repo.list_methods()
 assert len(rows)==1 and rows[0][0].id==original.id
 restarted=make_runtime(hydrate_repo=repo)
 current=restarted.planner.methods[original.name]
 assert current.subtasks[0].title=='new' and restarted.planner.method_status(current.name)=='proposed'
 with pytest.raises(PermissionError,match='revision'):
  restarted.planner.activate_method(current.name,expected_hash=old_hash)
 assert restarted.planner.activate_method(current.name,expected_hash=restarted.planner.method_review_hash(current))
 assert make_runtime(hydrate_repo=repo).planner.method_status(current.name)=='active'


def test_runtime_restart_persists_first_new_traces_without_skipping_history_count():
 runtime,repo=make_runtime()
 old=runtime.submit_goal('old fixture unavailable')
 old_ids={t.id for t in repo.list_traces()}
 assert old_ids
 restarted=make_runtime(hydrate_repo=repo)
 new=restarted.submit_goal('new fixture unavailable')
 new_traces=repo.list_traces(task_id=new.id)
 assert new_traces and {t.id for t in new_traces}=={t.id for t in restarted.loop.traces}
 assert old_ids<={t.id for t in repo.list_traces()}


def test_surprise_persistence_flushes_pending_trace_before_new_reflection():
 runtime,repo=make_runtime()
 context=runtime.submit_goal('surprise fixture',run_immediately=False)
 claim=runtime.calibration.assess_claim('supplied prediction',.9)
 context.plan=[PlanNode(title='synthetic failed',state=TaskState.FAILED,arguments={'_expectation_claim_id':claim.id})]
 runtime.loop._trace('fixture','pending trace before evaluation',task_id=context.id)
 runtime._evaluate_expectations(context)
 traces=repo.list_traces(task_id=context.id)
 assert len(traces)==2 and {t.id for t in traces}=={t.id for t in runtime.loop.traces}
 runtime._persist_context(context)
 assert len(repo.list_traces(task_id=context.id))==2


def test_trace_flush_retry_does_not_duplicate_already_committed_trace(monkeypatch):
 runtime,repo=make_runtime()
 context=runtime.submit_goal('fixture',run_immediately=False)
 for i in range(3):runtime.loop._trace('fixture',str(i),task_id=context.id)
 original=repo.save_trace;calls=0
 def flaky(trace):
  nonlocal calls
  calls+=1
  if calls==2:raise RuntimeError('synthetic write failure before commit')
  return original(trace)
 monkeypatch.setattr(repo,'save_trace',flaky)
 with pytest.raises(RuntimeError,match='synthetic'):runtime._persist_context(context)
 assert len(repo.list_traces(task_id=context.id))==1
 runtime._persist_context(context)
 assert len(repo.list_traces(task_id=context.id))==3


def test_retrospective_after_restart_uses_durable_failure_trace_history():
 runtime,repo=make_runtime()
 async def fail(arguments):raise RuntimeError('synthetic retained failure evidence')
 runtime.tools.register(ToolSpec(name='fixture_failure',description='fixture',max_retries=1),fail)
 runtime.planner.register_method(HTNMethod(name='fixture',goal_pattern='fixture failure',subtasks=[PlanNode(title='fixture failure',tool='fixture_failure',max_attempts=1)]))
 context=runtime.submit_goal('fixture failure')
 assert context.state==TaskState.FAILED
 restarted=make_runtime(hydrate_repo=repo)
 assert not restarted.loop.traces
 result=restarted.close(context.id)
 retro=result['retrospective']
 assert any('synthetic retained failure evidence' in text for text in retro['went_poorly'])
 assert any('investigate failing tools' in text for text in retro['lessons'])
 assert restarted.close(context.id)['idempotent'] is True


def test_scheduler_quantum_yields_unfinished_work_and_completes_across_restart():
 runtime,repo=make_runtime();calls=[]
 async def compute(arguments):
  result=arguments['n']*arguments['n'];calls.append(result);return {'square':result}
 spec=ToolSpec(name='fixture_square',description='fixture')
 runtime.tools.register(spec,compute)
 nodes=[PlanNode(title=f'square {n}',tool=spec.name,arguments={'n':n}) for n in (2,3,4)]
 for i in range(1,len(nodes)):nodes[i].depends_on=[nodes[i-1].id]
 runtime.planner.register_method(HTNMethod(name='square fixture',goal_pattern='square fixture',subtasks=nodes))
 context=runtime.submit_goal('square fixture',run_immediately=False)
 first=runtime.step(max_ticks=1)
 assert first.state=='running' and first.ticks_run==1 and calls==[4]
 assert not runtime.episodic.for_task(context.id)
 restarted=make_runtime(hydrate_repo=repo);restarted.tools.register(spec,compute)
 second=restarted.step(max_ticks=1)
 assert second.state=='running' and calls==[4,9]
 third=restarted.step(max_ticks=1)
 assert third.state=='succeeded' and calls==[4,9,16]
 assert restarted.step().state=='idle'
 assert repo.load_task(context.id).state==TaskState.SUCCEEDED
 assert [a.arguments['n'] for a in restarted.episodic.for_task(context.id)[0].actions]==[2,3,4]


def test_action_journal_detaches_immutable_same_id_and_scopes_tenant():
 repo=fresh_repo();other=GCWRepository(repo.engine,tenant_id='other')
 action=ActionRecord(tool='fixture',task_id='fixture',arguments={'n':[2]},succeeded=False)
 repo.save_action(action);repo.save_action(action)
 assert len(repo.list_actions())==1 and not other.list_actions()
 view=repo.list_actions()[0];view.arguments['n'].append(3)
 assert repo.list_actions()[0].arguments=={'n':[2]}
 with pytest.raises(PermissionError,match='differs'):repo.save_action(view)
 with pytest.raises(PermissionError,match='another tenant'):other.save_action(action)


def test_action_journal_additive_migration_on_local_sqlite():
 import importlib.util
 from alembic.migration import MigrationContext
 from alembic.operations import Operations
 from sqlalchemy import inspect
 spec=importlib.util.spec_from_file_location('action_migration','migrations/versions/20261007_m20_action_records.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 engine=make_engine()
 with engine.begin() as connection:
  with Operations.context(MigrationContext.configure(connection)):
   module.upgrade()
   assert 'm20_action_records' in inspect(connection).get_table_names()
   assert {idx['name'] for idx in inspect(connection).get_indexes('m20_action_records')}=={'ix_m20_action_records_task_id','ix_m20_action_records_tenant_id'}
   module.downgrade()
   assert 'm20_action_records' not in inspect(connection).get_table_names()


def test_task_restart_preserves_owner_partition_and_scheduler_service_history():
 from datetime import datetime,timezone
 repo=GCWRepository(make_engine(),tenant_id='fixture-owner');repo.create_schema()
 context=TaskContext(goal='fixture',tenant_id='fixture-owner',wm_partition='fixture-partition',ticks_served=7,last_run_at=datetime(2026,10,7,tzinfo=timezone.utc))
 repo.save_task(context);loaded=repo.load_task(context.id)
 assert loaded.tenant_id=='fixture-owner' and loaded.wm_partition=='fixture-partition'
 assert loaded.ticks_served==7 and loaded.last_run_at==context.last_run_at


def test_task_runtime_metadata_migration_preserves_legacy_rows():
 import importlib.util
 import sqlalchemy as sa
 from alembic.migration import MigrationContext
 from alembic.operations import Operations
 spec=importlib.util.spec_from_file_location('task_migration','migrations/versions/20261007_m20_task_runtime_metadata.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 engine=make_engine()
 with engine.begin() as connection:
  connection.execute(sa.text('CREATE TABLE m20_tasks (id TEXT PRIMARY KEY)'))
  connection.execute(sa.text("INSERT INTO m20_tasks(id) VALUES ('legacy')"))
  with Operations.context(MigrationContext.configure(connection)):
   module.upgrade()
   assert connection.execute(sa.text('SELECT runtime_metadata_json FROM m20_tasks')).scalar()=='{}'
   module.downgrade()
   assert connection.execute(sa.text('SELECT id FROM m20_tasks')).scalar()=='legacy'


def test_http_task_step_honors_cooperative_quantum_and_keeps_work_active(mounted,monkeypatch):
 from app.modules.m20_general_cognitive_worker import executive
 client,runtime,repo,_=mounted;calls=[]
 async def square(arguments):calls.append(arguments['n']**2);return {'square':calls[-1]}
 runtime.tools.register(ToolSpec(name='fixture_square_http',description='fixture'),square)
 context=runtime.submit_goal('fixture',run_immediately=False)
 context.plan=[PlanNode(title='first',tool='fixture_square_http',arguments={'n':2}),PlanNode(title='second',tool='fixture_square_http',arguments={'n':3})]
 runtime.repo.save_task(context)
 original_clock=executive.monotonic
 clock=iter([0,0,.2]);monkeypatch.setattr(executive,'monotonic',lambda:next(clock))
 first=client.post(f'/api/modules/20/runtime/tasks/{context.id}/step',json={'quantum_seconds':.1,'max_ticks':10})
 assert first.status_code==200 and first.json()['state']=='running' and calls==[4]
 monkeypatch.setattr(executive,'monotonic',original_clock)
 final=client.post(f'/api/modules/20/runtime/tasks/{context.id}/step',json={'quantum_seconds':1,'max_ticks':1})
 assert final.status_code==200 and final.json()['state']=='succeeded' and calls==[4,9]


def test_closed_active_task_cannot_rehydrate_or_run_again():
 runtime,repo=make_runtime();calls=[]
 async def handler(args):calls.append(args);return {'n':len(calls)}
 spec=ToolSpec(name='fixture_closed',description='fixture')
 runtime.tools.register(spec,handler)
 context=runtime.submit_goal('fixture',run_immediately=False)
 context.plan=[PlanNode(title='must not run',tool=spec.name)];repo.save_task(context)
 runtime.close(context.id)
 assert repo.load_task(context.id).state==TaskState.CANCELLED
 assert repo.load_task(context.id).plan[0].state==TaskState.CANCELLED
 restarted=make_runtime(hydrate_repo=repo);restarted.tools.register(spec,handler)
 assert restarted.step().state=='idle'
 assert restarted.run_task(context.id).state==TaskState.CANCELLED and not calls
 assert restarted.close(context.id)['idempotent'] is True


def test_closed_success_task_run_does_not_create_duplicate_execution_episode():
 runtime,repo=make_runtime()
 async def handler(args):return {'n':2+2}
 runtime.tools.register(ToolSpec(name='fixture_once',description='fixture'),handler)
 context=runtime.submit_goal('fixture',run_immediately=False);context.plan=[PlanNode(title='compute',tool='fixture_once')]
 runtime.run_task(context.id);runtime.close(context.id)
 count=len(repo.list_episodes(task_id=context.id))
 restarted=make_runtime(hydrate_repo=repo)
 assert restarted.run_task(context.id).state==TaskState.SUCCEEDED
 assert len(repo.list_episodes(task_id=context.id))==count==1


def test_legacy_closed_active_row_excluded_from_scheduler_and_approval_resume():
 runtime,repo=make_runtime()
 context=runtime.submit_goal('fixture',run_immediately=False)
 context.plan=[PlanNode(title='waiting',tool='fixture',state=TaskState.WAITING_APPROVAL,approval_id='old')]
 context.state=TaskState.WAITING_APPROVAL;repo.save_task(context)
 runtime.retrospectives.write(context.id,went_well=[],went_poorly=[],lessons=[])
 restarted=make_runtime(hydrate_repo=repo)
 assert restarted.step().state=='idle'
 assert restarted.resume(context.id,context.plan[0].id,approved=True).state==TaskState.WAITING_APPROVAL
 assert not restarted.dispatcher.records


def test_retrospective_restart_preserves_identity_time_and_detached_views():
 runtime,repo=make_runtime()
 retro=runtime.retrospectives.write('fixture',went_well=['fixture'],went_poorly=[],lessons=['fixture lesson'])
 original=repo.list_retrospectives()[0]
 retro.lessons.append('caller mutation')
 hit=runtime.retrospectives.lessons_for('fixture')[0][0]
 assert hit.lessons==['fixture lesson']
 hit.lessons.append('read mutation')
 assert runtime.retrospectives.lessons_for('fixture')[0][0].lessons==['fixture lesson']
 restored=make_runtime(hydrate_repo=repo).retrospectives.lessons_for('fixture')[0][0]
 assert restored.id==original.id and restored.created_at==original.created_at and restored.lessons==original.lessons


def test_skill_snapshots_cannot_mutate_internal_steps_status_or_evidence():
 library=DurableSkillLibrary(fresh_repo())
 original=Skill(name='fixture',goal_pattern='fixture',steps=[ActionRecord(tool='fixture',arguments={'n':[2]})],evidence={'ids':['a']})
 view=library.register(original)
 original.steps[0].arguments['n'].append(9);view.status=SkillStatus.RETIRED
 for read in (library.find_by_name('fixture'),library.match('fixture')[0],library.list()[0],library.activate(view.id)):
  read.steps[0].arguments['n'].append(8);read.evidence['ids'].append('bad')
 stored=library.find_by_name('fixture')
 assert stored.steps[0].arguments=={'n':[2]} and stored.evidence=={'ids':['a']}
 assert stored.status==SkillStatus.ACTIVE


def test_skill_retirement_persists_across_restart():
 repo=fresh_repo();library=DurableSkillLibrary(repo)
 library.register(Skill(name='fixture',goal_pattern='fixture'))
 assert library.retire('fixture')
 restarted=DurableSkillLibrary.load(repo)
 assert restarted.find_by_name('fixture') is None and restarted.list()[0].status==SkillStatus.RETIRED


def test_htn_reviewed_method_views_cannot_mutate_active_snapshot():
 runtime,repo=make_runtime()
 original=HTNMethod(name='fixture',goal_pattern='fixture',subtasks=[PlanNode(title='original',arguments={'n':[2]})])
 view=runtime.planner.register_method(original)
 original.subtasks[0].title='input mutation';view.subtasks[0].title='return mutation'
 current=runtime.planner.methods['fixture'];current.subtasks[0].title='read mutation'
 current.subtasks[0].arguments['n'].append(9)
 assert runtime.planner.decompose('fixture')[0].title=='original'
 assert runtime.planner.methods['fixture'].subtasks[0].arguments=={'n':[2]}
 assert repo.list_methods()[0][0].subtasks[0].title=='original'
 with pytest.raises(TypeError):runtime.planner.methods['fixture']=current


def test_invalid_library_dag_never_persists_and_preset_success_does_execute():
 from app.modules.m20_general_cognitive_worker.htn_planner import PlanError
 runtime,repo=make_runtime();calls=[]
 with pytest.raises(PlanError):runtime.planner.register_method(HTNMethod(name='bad',goal_pattern='fixture',subtasks=[PlanNode(title='bad',depends_on=['missing'])]))
 assert not repo.list_methods()
 async def compute(args):calls.append(3*3);return {'square':calls[-1]}
 runtime.tools.register(ToolSpec(name='fixture_reset',description='fixture'),compute)
 runtime.planner.register_method(HTNMethod(name='good',goal_pattern='fixture',subtasks=[PlanNode(title='compute',tool='fixture_reset',state=TaskState.SUCCEEDED,result_summary='fake')]))
 result=runtime.submit_goal('fixture')
 assert result.state==TaskState.SUCCEEDED and calls==[9] and result.plan[0].result_summary=="{'square': 9}"


def test_mcts_rollout_failure_is_not_retried_and_sibling_remains_ready():
    parent = PlanNode(id="p", title="parent", risk=Risk.READ)
    child = PlanNode(id="c", title="child", depends_on=["p"], risk=Risk.READ)
    sibling = PlanNode(id="s", title="sibling", risk=Risk.READ)
    search = BoundedMCTS(max_depth=5)
    class FailRng:
        choices = []
        def choice(self, ready):
            node = ready[0]
            self.choices.append(node.id)
            return node
        def random(self):
            return 1.0
    rng = FailRng()
    search.random = rng
    search._rollout([parent, child, sibling], set(), 0)
    assert rng.choices == ["p", "s"]


@pytest.mark.parametrize("state", [TaskState.FAILED, TaskState.BLOCKED, TaskState.WAITING_APPROVAL])
def test_mcts_no_ready_does_not_label_unsucceeded_plan_complete(state):
    result = BoundedMCTS().search([PlanNode(title="not completed", state=state)])
    assert result.best_action_id is None
    assert result.simulations_run == 0
    assert result.heuristic_root_value == 0
    assert result.stopped_by == "no_ready_action"


def test_mcts_partial_no_ready_reports_supplied_progress():
    result = BoundedMCTS().search([PlanNode(title="done", state=TaskState.SUCCEEDED), PlanNode(title="failed", state=TaskState.FAILED)])
    assert result.heuristic_root_value == 0.5
    assert result.stopped_by == "no_ready_action"


@pytest.mark.parametrize("kwargs", [{"max_seconds":float("nan")}, {"max_seconds":float("inf")}, {"max_simulations":True}, {"max_depth":1.5}, {"exploration":float("nan")}, {"exploration":-1}])
def test_mcts_budget_configuration_requires_finite_bounded_values(kwargs):
    with pytest.raises(ValueError):
        BoundedMCTS(**kwargs)


def test_scheduler_step_reports_surprise_consumed_during_run():
    runtime, _ = make_runtime()
    async def work(args):
        return {"value": 1}
    runtime.tools.register(ToolSpec(name="fixture", description="synthetic fixture", risk=Risk.READ), work)
    claim = runtime.calibration.assess_claim("unlikely success", 0.1)
    context = TaskContext(goal="surprise", state=TaskState.RUNNING,
        plan=[PlanNode(title="fixture step", tool="fixture", arguments={"_expectation_claim_id":claim.id})])
    runtime.scheduler.add(context)
    report = runtime.step(max_ticks=2)
    assert report.surprises == ["fixture step"]
    assert runtime.calibration.claims[claim.id].resolved is True


def test_skill_version_history_and_exclusive_activation_survive_restart():
    repo = fresh_repo()
    library = DurableSkillLibrary(repo)
    first = library.register(Skill(name='fixture', goal_pattern='fixture'))
    library.retire('fixture')
    library = DurableSkillLibrary.load(repo)
    second = library.register(Skill(name='fixture', goal_pattern='fixture'))
    assert second.version == first.version + 1
    library.activate(first.id)
    restarted = DurableSkillLibrary.load(repo)
    assert [s.id for s in restarted.list(status=SkillStatus.ACTIVE)] == [first.id]
    third = restarted.register(Skill(name='fixture', goal_pattern='fixture'))
    assert third.version == second.version + 1
    assert [s.id for s in DurableSkillLibrary.load(repo).list(status=SkillStatus.ACTIVE)] == [third.id]


@pytest.mark.parametrize('rate', [float('nan'), float('inf'), -1, True, '1'])
def test_fair_scheduler_rejects_invalid_supplied_aging_rate(rate):
    from app.modules.m20_general_cognitive_worker.scheduler import FairContextScheduler
    with pytest.raises(ValueError):
        FairContextScheduler(aging_bonus_per_minute=rate)


def test_fair_scheduler_aging_overflow_is_reported_before_selection_mutation():
    from datetime import datetime, timedelta, timezone
    from app.modules.m20_general_cognitive_worker.scheduler import FairContextScheduler
    now = datetime.now(timezone.utc)
    scheduler = FairContextScheduler(aging_bonus_per_minute=1e308)
    context = TaskContext(goal='fixture', created_at=now - timedelta(minutes=10))
    scheduler.add(context)
    with pytest.raises(ValueError):
        scheduler.next_context(now=now)
    assert context.last_run_at is None and context.ticks_served == 0


def test_durable_risk_register_restart_revision_and_tenant_isolation():
    from app.modules.m20_general_cognitive_worker.risk_register import DurableRiskRegister
    engine = make_engine()
    a = GCWRepository(engine, tenant_id='a'); a.create_schema()
    b = GCWRepository(engine, tenant_id='b')
    risk = {'id': 'cutoff', 'cause': 'Miss payroll cutoff', 'severity': 8, 'occurrence': 3, 'detection': 4,
            'owner': '', 'mitigation': 'Queue alert', 'test': '', 'evidence': []}
    first = DurableRiskRegister(a).create(goal='Payroll export', risks=[risk])
    assert DurableRiskRegister(b).get(first['id']) is None
    loaded = DurableRiskRegister(a).get(first['id'])
    assert loaded['revision'] == 1 and loaded['report']['risks'][0]['risk_priority_number'] == 96
    risk.update(owner='ops', test='Replay cutoff', evidence=['supplied-test'])
    updated = DurableRiskRegister(a).revise(first['id'], expected_revision=1, risks=[risk])
    assert updated['revision'] == 2 and updated['report']['ready_for_owner_review']
    with pytest.raises(ValueError, match='revision conflict'):
        DurableRiskRegister(a).revise(first['id'], expected_revision=1, risks=[risk])
    history = DurableRiskRegister(a).history(first['id'])
    assert [row['revision'] for row in history] == [1, 2]
    assert history[0]['report']['risks'][0]['owner'] == ''
    with pytest.raises(KeyError):
        DurableRiskRegister(b).revise(first['id'], expected_revision=2, risks=[risk])


def test_durable_risk_http_revision_conflict_and_history(mounted):
    client, runtime, repo, _ = mounted
    risk = {'id': 'fixture', 'cause': 'Miss cutoff', 'severity': 5, 'occurrence': 3, 'detection': 2,
            'owner': '', 'mitigation': '', 'test': '', 'evidence': []}
    created = client.post('/api/modules/20/runtime/risk-registers', json={'goal': 'fixture', 'risks': [risk]})
    assert created.status_code == 201
    identifier = created.json()['id']
    risk['owner'] = 'ops lead'
    updated = client.post(f'/api/modules/20/runtime/risk-registers/{identifier}/revise', json={'expected_revision': 1, 'risks': [risk]})
    assert updated.status_code == 200 and updated.json()['revision'] == 2
    stale = client.post(f'/api/modules/20/runtime/risk-registers/{identifier}/revise', json={'expected_revision': 1, 'risks': [risk]})
    assert stale.status_code == 409
    assert len(client.get(f'/api/modules/20/runtime/risk-registers/{identifier}/history').json()) == 2
    assert client.get('/api/modules/20/runtime/risk-registers/missing').status_code == 404


def test_risk_register_file_restart_lists_open_control_gaps(tmp_path):
    from app.modules.m20_general_cognitive_worker.risk_register import DurableRiskRegister
    path = tmp_path / 'risk.sqlite'
    engine = create_engine(f'sqlite:///{path}')
    repo = GCWRepository(engine, tenant_id='a'); repo.create_schema()
    risk = {'id': 'fixture', 'cause': 'Miss cutoff', 'severity': 5, 'occurrence': 3, 'detection': 2,
            'owner': '', 'mitigation': '', 'test': '', 'evidence': []}
    first = DurableRiskRegister(repo).create(goal='fixture', risks=[risk])
    engine.dispose()
    restarted = create_engine(f'sqlite:///{path}')
    register = DurableRiskRegister(GCWRepository(restarted, tenant_id='a'))
    summaries = register.list()
    assert summaries[0]['id'] == first['id'] and summaries[0]['open_control_gaps'] == 4
    assert summaries[0]['highest_priority'] == 30
    assert DurableRiskRegister(GCWRepository(restarted, tenant_id='b')).list() == []
    assert register.get(first['id'])['revision'] == 1
    restarted.dispose()


def test_risk_revision_history_insert_failure_rolls_back_current_revision():
    from app.modules.m20_general_cognitive_worker.risk_register import DurableRiskRegister, RiskRevisionRow
    from sqlalchemy import event
    repo = fresh_repo(); register = DurableRiskRegister(repo)
    risk = {'id': 'fixture', 'cause': 'Miss cutoff', 'severity': 5, 'occurrence': 3, 'detection': 2,
            'owner': '', 'mitigation': '', 'test': '', 'evidence': []}
    first = register.create(goal='fixture', risks=[risk])
    def fail_insert(mapper, connection, target):
        if target.revision == 2: raise RuntimeError('fixture insert failure')
    event.listen(RiskRevisionRow, 'before_insert', fail_insert)
    try:
        with pytest.raises(RuntimeError, match='fixture insert failure'):
            register.revise(first['id'], expected_revision=1, risks=[risk])
    finally:
        event.remove(RiskRevisionRow, 'before_insert', fail_insert)
    assert register.get(first['id'])['revision'] == 1
    assert len(register.history(first['id'])) == 1


def test_risk_revision_file_sqlite_simultaneous_writers_only_one_commits(tmp_path):
    from app.modules.m20_general_cognitive_worker.risk_register import DurableRiskRegister
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    path = tmp_path / 'writers.sqlite'
    engine = create_engine(f'sqlite:///{path}', connect_args={'timeout': 10})
    repo = GCWRepository(engine, tenant_id='a'); repo.create_schema()
    risk = {'id': 'fixture', 'cause': 'Miss cutoff', 'severity': 5, 'occurrence': 3, 'detection': 2,
            'owner': '', 'mitigation': '', 'test': '', 'evidence': []}
    first = DurableRiskRegister(repo).create(goal='fixture', risks=[risk])
    barrier = Barrier(2)
    def write(owner):
        separate = create_engine(f'sqlite:///{path}', connect_args={'timeout': 10})
        register = DurableRiskRegister(GCWRepository(separate, tenant_id='a'))
        try:
            barrier.wait(timeout=5)
            try:
                result = register.revise(first['id'], expected_revision=1, risks=[{**risk, 'owner': owner}])
                return ('committed', result['report']['risks'][0]['owner'])
            except ValueError as exc:
                assert 'revision conflict' in str(exc)
                return ('conflict', owner)
        finally:
            separate.dispose()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ['one', 'two']))
    assert sorted(result[0] for result in results) == ['committed', 'conflict']
    register = DurableRiskRegister(repo)
    assert [row['revision'] for row in register.history(first['id'])] == [1, 2]
    winner = next(owner for status, owner in results if status == 'committed')
    assert register.get(first['id'])['report']['risks'][0]['owner'] == winner
    engine.dispose()


def test_risk_register_revision_diff_exposes_control_and_rating_changes():
    from app.modules.m20_general_cognitive_worker.risk_register import DurableRiskRegister
    repo = fresh_repo(); register = DurableRiskRegister(repo)
    risk = {'id': 'cutoff', 'cause': 'Miss payroll cutoff', 'severity': 5, 'occurrence': 3, 'detection': 2,
            'owner': '', 'mitigation': '', 'test': '', 'evidence': []}
    first = register.create(goal='fixture', risks=[risk])
    register.revise(first['id'], expected_revision=1, risks=[{**risk, 'owner': 'ops', 'severity': 8},
        {**risk, 'id': 'vendor', 'cause': 'Vendor offline'}])
    diff = register.compare(first['id'], from_revision=1, to_revision=2)
    assert diff['added'] == ['vendor'] and diff['removed'] == []
    assert diff['changed'][0]['id'] == 'cutoff'
    assert diff['changed'][0]['fields']['owner'] == {'before': '', 'after': 'ops'}
    assert diff['changed'][0]['priority'] == {'before': 30, 'after': 48}
    assert diff['evidence_verified'] is False
    with pytest.raises(KeyError):
        register.compare(first['id'], from_revision=1, to_revision=99)


def test_runtime_tool_history_uses_dispatch_journal_and_survives_restart():
    runtime, repo = make_runtime()
    async def noop(args): return {}
    spec = ToolSpec(name='fixture', description='fixture read', capabilities=['fixture'], risk=Risk.READ)
    runtime.tools.register(spec, noop)
    context = TaskContext(goal='fixture')
    runtime.dispatcher.records.append(ActionRecord(tool='fixture', task_id=context.id, succeeded=False))
    runtime._persist_context(context)
    choice = runtime.select_tool('fixture read').as_dict()
    assert choice['candidates'][0]['historical_success'] == pytest.approx(1 / 3, abs=1e-4)
    assert choice['runtime_dispatch_history_connected'] is True
    assert choice['history_status'] == 'reported_local_dispatch_journal_with_beta_1_1_prior'
    restarted = make_runtime(hydrate_repo=repo)
    restarted.tools.register(spec, noop)
    for _ in range(2):
        assert restarted.select_tool('fixture read').as_dict()['candidates'][0]['historical_success'] == pytest.approx(1 / 3, abs=1e-4)


def test_tool_history_actual_local_handlers_persisted_across_engine_reopen(tmp_path):
    import asyncio
    path = tmp_path / 'tool-history.sqlite'
    engine = create_engine(f'sqlite:///{path}')
    repo = GCWRepository(engine)
    repo.create_schema()
    runtime = GCWRuntime(repo)
    calls = []
    async def handler(args):
        calls.append(args['fail'])
        if args['fail']:
            raise RuntimeError('fixture local failure')
        return {'value': 42}
    spec = ToolSpec(name='local_fixture', description='local fixture',
                    capabilities=['fixture'], risk=Risk.READ, max_retries=1)
    runtime.tools.register(spec, handler)
    task = TaskContext(goal='local fixture')
    for failed in (False, False, True):
        action = asyncio.run(runtime.dispatcher.dispatch(
            'local_fixture', {'fail': failed}, task_id=task.id))
        assert action.succeeded is not failed
        runtime._persist_context(task)
    assert calls == [False, False, True]
    assert len(repo.list_actions()) == 3
    engine.dispose()
    reopened_engine = create_engine(f'sqlite:///{path}')
    reopened = GCWRuntime(GCWRepository(reopened_engine))
    reopened.tools.register(spec, handler)
    for _ in range(2):
        candidate = reopened.select_tool('local fixture').as_dict()['candidates'][0]
        assert candidate['supplied_successes'] == 2
        assert candidate['supplied_failures'] == 1
        assert candidate['historical_success'] == 0.6
    assert calls == [False, False, True]
    reopened_engine.dispose()


def test_retrospective_reports_actual_action_evidence_not_trace_keywords():
    import asyncio
    runtime, repo = make_runtime()
    async def handler(args):
        if args['fail']:
            raise RuntimeError('retained diagnostic')
        return {'value': 'error is a valid data label'}
    runtime.tools.register(ToolSpec(name='fixture_report', description='fixture',
                                   max_retries=1, risk=Risk.READ), handler)
    task = TaskContext(goal='fixture')
    for failed in (False, True):
        asyncio.run(runtime.dispatcher.dispatch('fixture_report', {'fail': failed}, task_id=task.id))
    runtime._persist_context(task)
    report = runtime.close(task.id)['retrospective']['execution_report']
    assert report['final_task_state'] == 'cancelled'
    assert report['local_action_count'] == 2
    assert report['local_success_count'] == 1
    assert report['local_failure_count'] == 1
    assert report['external_outcomes_verified'] is False
    assert report['tools']['fixture_report']['failed_action_ids'] == [repo.list_actions(task_id=task.id)[1].id]
    assert report['tools']['fixture_report']['last_failure'] == 'failed after 1 attempt(s): retained diagnostic'
    assert runtime.close(task.id)['retrospective']['execution_report'] == report
    assert make_runtime(hydrate_repo=repo).close(task.id)['retrospective']['execution_report'] == report


def test_retrospective_empty_cancelled_task_does_not_claim_goal_went_well():
    runtime, _ = make_runtime()
    task = TaskContext(goal='not executed')
    runtime._persist_context(task)
    retro = runtime.close(task.id)['retrospective']
    assert retro['went_well'] == []
    assert retro['execution_report']['local_action_count'] == 0


def test_risk_control_patch_preserves_other_risks_and_rejects_stale_review(mounted):
    client, runtime, _, _ = mounted
    risk = {'id': 'one', 'cause': 'cutoff', 'severity': 5, 'occurrence': 3, 'detection': 2,
            'owner': '', 'mitigation': '', 'test': '', 'evidence': []}
    other = dict(risk, id='two', cause='supplier')
    created = runtime.risk_registers.create(goal='fixture', risks=[risk, other])
    path = f"/api/modules/20/runtime/risk-registers/{created['id']}/risks/one"
    response = client.patch(path, json={'expected_revision': 1, 'changes': {'owner': 'supplied ops label', 'test': 'Replay'}})
    assert response.status_code == 200
    result = response.json()
    assert result['revision'] == 2
    rows = {r['id']: r for r in result['report']['risks']}
    assert rows['one']['owner'] == 'supplied ops label'
    assert rows['two']['owner'] == ''
    assert client.patch(path, json={'expected_revision': 1, 'changes': {'mitigation': 'stale'}}).status_code == 409
    assert client.patch(path, json={'expected_revision': 2, 'changes': {'id': 'renamed'}}).status_code == 422
    assert client.patch(path, json={'expected_revision': 2, 'changes': {}}).status_code == 422
    assert client.patch(path + 'missing', json={'expected_revision': 2, 'changes': {'owner': 'x'}}).status_code == 404
    assert runtime.risk_registers.get(created['id'])['revision'] == 2
    assert len(runtime.risk_registers.history(created['id'])) == 2


def test_planning_retrieves_prior_retrospective_lessons_after_restart():
    runtime, repo = make_runtime()
    prior = runtime.retrospectives.write('past', went_well=[], went_poorly=['fixture failure'],
        lessons=['check fixture input before retry'], execution_report={'external_outcomes_verified': False})
    class CapturePlanner:
        def __init__(self): self.context = None
        def decompose(self, goal, *, context=''):
            self.context = context
            return [{'title': 'review fixture', 'tool': None}]
    model = CapturePlanner()
    restored = make_runtime(hydrate_repo=repo, model=model)
    task = restored.submit_goal('fixture retry', run_immediately=True)
    assert model.context and 'check fixture input before retry' in model.context
    chunks = restored.working_memory.focused(partition=task.id)
    lesson_chunks = [c for c in chunks if c.source == 'retrospective_retrieval']
    assert len(lesson_chunks) == 1
    assert lesson_chunks[0].type == ChunkType.HYPOTHESIS
    assert prior.id in lesson_chunks[0].content
    assert 'unverified review suggestion' in lesson_chunks[0].content


def test_review_lessons_prepared_plan_deduplicates_and_stays_task_partitioned():
    class CapturePlanner:
        def __init__(self): self.context = ''
        def decompose(self, goal, *, context=''):
            self.context = context
            return [{'title': 'review fixture', 'tool': None}]
    model = CapturePlanner()
    runtime, _ = make_runtime(model=model)
    runtime.retrospectives.write('past', went_well=[], went_poorly=[], lessons=['fixture check'])
    task = runtime.submit_goal('fixture', run_immediately=False)
    assert 'fixture check' in model.context
    runtime._retrieve_review_lessons(task)
    runtime._retrieve_review_lessons(task)
    chunks = [c for c in runtime.working_memory.focused(partition=task.id) if c.source == 'retrospective_retrieval']
    assert len(chunks) == 1 and chunks[0].confidence == 0
    assert runtime.working_memory.focused(partition='other') == []


def test_runtime_task_context_input_is_durable_replay_safe_and_reaches_planner(mounted):
    client, runtime, repo, _ = mounted
    task = runtime.submit_goal('fixture input', run_immediately=False)
    path = f'/api/modules/20/runtime/tasks/{task.id}/context'
    payload = {'text': 'Supplier cutoff is 16:00 in supplied note', 'source': 'supplied-note', 'reference': 'note-1'}
    response = client.post(path, json=payload)
    assert response.status_code == 201
    first = response.json()
    assert first['source_verified'] is False
    assert first['inserted'] is True
    assert client.post(path, json=payload).json()['inserted'] is False
    assert client.post(path, json=dict(payload, text='changed')).status_code == 409
    class CapturePlanner:
        def decompose(self, goal, *, context=''):
            self.context = context
            return [{'title': 'review input', 'tool': None}]
    model = CapturePlanner()
    restored = make_runtime(hydrate_repo=repo, model=model)
    restored.run_task(task.id)
    assert 'Supplier cutoff is 16:00' in model.context
    assert 'unverified supplied context' in model.context
    assert 'note-1' in model.context
    assert restored.working_memory.focused(partition='other') == []
    runtime.close(task.id)
    assert client.post(path, json=dict(payload, reference='note-2')).status_code == 409
    assert client.post('/api/modules/20/runtime/tasks/missing/context', json=payload).status_code == 404


def test_task_context_reference_replay_after_runtime_restart_and_tenant_isolation():
    engine = make_engine()
    a = GCWRepository(engine, tenant_id='a'); a.create_schema()
    b = GCWRepository(engine, tenant_id='b')
    runtime = GCWRuntime(a)
    task = runtime.submit_goal('fixture', run_immediately=False)
    payload = dict(text='fixture retained note', source='caller', reference='r1')
    first = runtime.add_task_context(task.id, **payload)
    restarted = GCWRuntime(a)
    assert restarted.add_task_context(task.id, **payload)['inserted'] is False
    assert restarted.working_memory.get(first['chunk_id']).confidence == 0
    with pytest.raises(KeyError): GCWRuntime(b).add_task_context(task.id, **payload)
    with pytest.raises(ValueError): restarted.add_task_context(task.id, text=' ', source='caller', reference='r2')


def test_runtime_task_schedule_update_changes_service_order_and_survives_restart(mounted):
    from datetime import datetime, timezone
    client, runtime, repo, _ = mounted
    first = runtime.submit_goal('first fixture', importance=4, run_immediately=False)
    second = runtime.submit_goal('second fixture', importance=1, run_immediately=False)
    path = f'/api/modules/20/runtime/tasks/{second.id}/schedule'
    response = client.patch(path, json={'importance': 5, 'deadline': '2026-10-08T10:00:00+05:30'})
    assert response.status_code == 200
    assert response.json()['importance'] == 5
    assert runtime.scheduler.order()[0].id == second.id
    reopened = make_runtime(hydrate_repo=repo)
    assert reopened.get_task(second.id).importance == 5
    assert reopened.get_task(second.id).deadline == datetime(2026, 10, 8, 4, 30, tzinfo=timezone.utc)
    assert reopened.scheduler.order()[0].id == second.id
    assert client.patch(path, json={'deadline': None}).json()['deadline'] is None
    assert client.patch(path, json={'importance': True}).status_code == 422
    assert client.patch(path, json={'deadline': '2026-10-08T10:00:00'}).status_code == 422
    assert client.patch(path, json={}).status_code == 422
    runtime.close(second.id)
    assert client.patch(path, json={'importance': 3}).status_code == 409
    assert client.patch('/api/modules/20/runtime/tasks/missing/schedule', json={'importance': 3}).status_code == 404
    assert runtime.get_task(first.id).importance == 4


def test_task_schedule_failed_save_does_not_change_active_scheduler():
    runtime, repo = make_runtime()
    task = runtime.submit_goal('fixture', importance=2, run_immediately=False)
    original = repo.save_task
    def fail(context): raise RuntimeError('fixture persistence unavailable')
    repo.save_task = fail
    with pytest.raises(RuntimeError): runtime.update_task_schedule(task.id, changes={'importance': 5})
    assert runtime.get_task(task.id).importance == 2
    repo.save_task = original
    assert repo.load_task(task.id).importance == 2


def test_task_execution_evidence_readback_exposes_retained_records_after_restart(mounted):
    import asyncio
    client, runtime, repo, _ = mounted
    async def handler(args): return {'value': 42}
    runtime.tools.register(ToolSpec(name='fixture', description='fixture', risk=Risk.READ), handler)
    task = runtime.submit_goal('fixture', run_immediately=False)
    action = asyncio.run(runtime.dispatcher.dispatch('fixture', {}, task_id=task.id))
    runtime.loop._trace('act', 'retained fixture diagnostic', task_id=task.id)
    runtime._persist_context(task)
    path = f'/api/modules/20/runtime/tasks/{task.id}/evidence'
    response = client.get(path, params={'limit': 1})
    assert response.status_code == 200
    data = response.json()
    assert data['actions'][0]['id'] == action.id
    assert data['traces'][0]['detail'] == 'retained fixture diagnostic'
    assert data['external_outcomes_verified'] is False
    assert data['action_count'] == 1 and data['trace_count'] == 1
    restarted = make_runtime(hydrate_repo=repo)
    assert restarted.task_evidence(task.id, limit=1)['actions'] == data['actions']
    assert client.get(path, params={'limit': 101}).status_code == 422
    assert client.get('/api/modules/20/runtime/tasks/missing/evidence').status_code == 404


def test_task_evidence_db_bounded_latest_first_and_tenant_hidden():
    from datetime import datetime, timedelta, timezone
    engine = make_engine()
    a = GCWRepository(engine, tenant_id='a'); a.create_schema()
    b = GCWRepository(engine, tenant_id='b')
    runtime = GCWRuntime(a)
    task = runtime.submit_goal('fixture', run_immediately=False)
    now = datetime.now(timezone.utc)
    for i in range(3):
        a.save_action(ActionRecord(tool='fixture', task_id=task.id, started_at=now + timedelta(seconds=i)))
        a.save_trace(TraceEntry(task_id=task.id, phase='act', detail=str(i), created_at=now + timedelta(seconds=i)))
    evidence = runtime.task_evidence(task.id, limit=2)
    assert len(evidence['actions']) == len(evidence['traces']) == 2
    assert evidence['action_count'] == evidence['trace_count'] == 3
    assert evidence['actions_truncated'] and evidence['traces_truncated']
    assert [t['detail'] for t in evidence['traces']] == ['2', '1']
    with pytest.raises(KeyError): GCWRuntime(b).task_evidence(task.id)


def test_runtime_supplied_plan_preparation_without_model_executes_only_on_step(mounted):
    client, runtime, repo, _ = mounted
    calls = []
    async def handler(args):
        calls.append(args['value']); return {'value': args['value'] * 2}
    runtime.tools.register(ToolSpec(name='fixture_compute', description='fixture', risk=Risk.READ), handler)
    task = runtime.submit_goal('fixture needs plan', run_immediately=False)
    path = f'/api/modules/20/runtime/tasks/{task.id}/plan'
    response = client.put(path, json={'steps': [{'id': 'a', 'title': 'compute fixture', 'tool': 'fixture_compute', 'arguments': {'value': 21}}]})
    assert response.status_code == 200
    assert response.json()['state'] == 'planning'
    assert calls == []
    assert repo.load_task(task.id).plan[0].tool == 'fixture_compute'
    assert client.put(path, json={'steps': [{'title': 'replace'}]}).status_code == 409
    result = client.post(f'/api/modules/20/runtime/tasks/{task.id}/step', json={'max_ticks': 2, 'quantum_seconds': 5})
    assert result.status_code == 200 and calls == [21]
    assert result.json()['state'] == 'succeeded'
    assert len(repo.list_actions(task_id=task.id)) == 1
    bad = runtime.submit_goal('invalid fixture plan', run_immediately=False)
    badpath = f'/api/modules/20/runtime/tasks/{bad.id}/plan'
    assert client.put(badpath, json={'steps': [{'id': 'a', 'title': 'cycle', 'depends_on': ['a']}]}).status_code == 422
    assert repo.load_task(bad.id).plan == []
    assert client.put('/api/modules/20/runtime/tasks/missing/plan', json={'steps': [{'title': 'fixture'}]}).status_code == 404


def test_supplied_plan_cannot_bypass_external_step_approval_or_import_success():
    runtime, repo = make_runtime()
    calls = []
    async def handler(args): calls.append('effect'); return {}
    runtime.tools.register(ToolSpec(name='fixture_external', description='fixture', risk=Risk.EXTERNAL), handler)
    task = runtime.submit_goal('fixture effect', run_immediately=False)
    runtime.prepare_supplied_plan(task.id, steps=[{'title': 'fixture effect', 'tool': 'fixture_external',
        'state': 'succeeded', 'approval_id': 'invented', 'attempts': 99}])
    restored = make_runtime(hydrate_repo=repo)
    restored.tools.register(ToolSpec(name='fixture_external', description='fixture', risk=Risk.EXTERNAL), handler)
    result = restored.run_task(task.id)
    assert calls == []
    assert result.state == TaskState.WAITING_APPROVAL
    assert result.plan[0].approval_id != 'invented'
    assert result.plan[0].attempts == 1


def test_runtime_plan_structured_dataflow_survives_between_step_restart():
    runtime, repo = make_runtime()
    task = runtime.submit_goal('fixture data flow', run_immediately=False)
    runtime.prepare_supplied_plan(task.id, steps=[
        {'id': 'fetch', 'title': 'fetch fixture', 'tool': 'fixture_fetch'},
        {'id': 'sum', 'title': 'sum fixture', 'tool': 'fixture_sum', 'depends_on': ['fetch'],
         'arguments': {'values': {'$step': 'fetch', 'path': ['values']}}},
    ])
    async def fetch(args): return {'values': [20, 22], 'metadata': {'source': 'fixture'}}
    runtime.tools.register(ToolSpec(name='fixture_fetch', description='fixture', risk=Risk.READ), fetch)
    runtime.run_task(task.id, max_ticks=1, yield_on_boundary=True)
    assert repo.load_task(task.id).plan[0].output == {'values': [20, 22], 'metadata': {'source': 'fixture'}}
    restored = make_runtime(hydrate_repo=repo)
    calls = []
    async def total(args):
        calls.append(args['values']); return {'total': sum(args['values'])}
    restored.tools.register(ToolSpec(name='fixture_sum', description='fixture', risk=Risk.READ,
        parameters={'type': 'object', 'properties': {'values': {'type': 'array', 'items': {'type': 'number'}}}, 'required': ['values']}), total)
    result = restored.run_task(task.id, max_ticks=2)
    assert result.state == TaskState.SUCCEEDED
    assert calls == [[20, 22]]
    assert result.plan[1].output == {'total': 42}
    assert repo.list_actions(task_id=task.id)[-1].result == {'total': 42}


def test_bound_arguments_review_uses_actual_output_and_invalid_path_blocks():
    runtime, repo = make_runtime()
    task = runtime.submit_goal('fixture bindings', run_immediately=False)
    runtime.prepare_supplied_plan(task.id, steps=[
        {'id':'a','title':'fetch','tool':'fetch'},
        {'id':'b','title':'send','tool':'fixture_external','depends_on':['a'],
         'arguments':{'recipient':{'$step':'a','path':['address']}}}])
    async def fetch(args): return {'address':'fixture@example.invalid'}
    calls=[]
    async def send(args): calls.append(args); return {}
    runtime.tools.register(ToolSpec(name='fetch',description='fixture',risk=Risk.READ),fetch)
    runtime.tools.register(ToolSpec(name='fixture_external',description='fixture',risk=Risk.EXTERNAL),send)
    context=runtime.run_task(task.id)
    assert context.state == TaskState.WAITING_APPROVAL and calls == []
    approval = runtime.safety.approvals.requests[context.plan[1].approval_id]
    assert approval.payload == {'recipient':'fixture@example.invalid'}
    context.plan[1].state=TaskState.PENDING
    context.plan[1].approval_id=None
    context.plan[1].arguments['recipient']['path']=['absent']
    context=runtime.run_task(task.id)
    assert context.state == TaskState.BLOCKED and calls == []


def test_method_instantiation_remaps_dataflow_and_clears_imported_output():
    from app.modules.m20_general_cognitive_worker.htn_planner import HTNPlanner
    method=HTNMethod(name='fixture',goal_pattern='fixture',subtasks=[
        PlanNode(id='a',title='fetch',tool='fetch',output={'imported':True}),
        PlanNode(id='b',title='sum',tool='sum',depends_on=['a'],arguments={'data':{'$step':'a','path':[]}})])
    planner=HTNPlanner();planner.register_method(method)
    plan=planner.decompose('fixture')
    assert plan[0].output is None
    assert plan[1].arguments['data']['$step']==plan[0].id


@pytest.mark.parametrize('value',[{'x':float('nan')},{'x':'x'*64001},['wrong type']])
def test_dispatch_invalid_structured_result_not_promoted_to_success(value):
    import asyncio
    runtime,_=make_runtime()
    async def handler(args): return value
    runtime.tools.register(ToolSpec(name='fixture',description='fixture',risk=Risk.READ,max_retries=1),handler)
    record=asyncio.run(runtime.dispatcher.dispatch('fixture',{}))
    assert not record.succeeded and record.result is None


def test_supplied_plan_preflight_reports_all_known_tool_gaps_without_execution(mounted):
    client, runtime, _, _ = mounted
    calls=[]
    async def handler(args): calls.append(args); return {'value': 42}
    runtime.tools.register(ToolSpec(name='fixture',description='fixture',risk=Risk.READ,
        parameters={'type':'object','properties':{'value':{'type':'integer'}},'required':['value']},
        preconditions=['fixture_enabled']),handler)
    task=runtime.submit_goal('fixture preflight',run_immediately=False)
    runtime.prepare_supplied_plan(task.id,steps=[
        {'id':'a','title':'bad static input','tool':'fixture','arguments':{'value':'wrong'}},
        {'id':'b','title':'unknown tool','tool':'missing_fixture','depends_on':['a']},
        {'id':'c','title':'bound input','tool':'fixture','depends_on':['a'],
         'arguments':{'value':{'$step':'a','path':['value']}}}])
    response=client.post(f'/api/modules/20/runtime/tasks/{task.id}/preflight',json={'context':{}})
    assert response.status_code==200
    data=response.json()
    assert data['ready_for_dispatch'] is False
    byid={row['step_id']:row for row in data['steps']}
    assert 'arguments_schema' in byid['a']['issues']
    assert 'missing_preconditions' in byid['a']['issues']
    assert 'unknown_tool' in byid['b']['issues']
    assert byid['c']['argument_check']=='deferred_until_dependency_output'
    assert data['external_actions_executed'] is False and data['approval_granted'] is False
    assert calls==[] and len(runtime.safety.approvals.requests)==0
    assert client.post('/api/modules/20/runtime/tasks/missing/preflight',json={}).status_code==404


def test_preflight_clean_static_inputs_never_grant_dispatch_permission():
    runtime,_=make_runtime()
    async def handler(args): return {}
    runtime.tools.register(ToolSpec(name='fixture',description='fixture',risk=Risk.EXTERNAL),handler)
    task=runtime.submit_goal('fixture',run_immediately=False)
    runtime.prepare_supplied_plan(task.id,steps=[{'title':'fixture','tool':'fixture'}])
    report=runtime.preflight_task(task.id)
    assert report['static_checks_passed'] is True
    assert report['ready_for_dispatch'] is False
    assert report['steps'][0]['effective_risk']=='external'
    assert not runtime.safety.approvals.requests


def test_runtime_builtin_csv_summary_executes_real_data_without_model():
    runtime, repo = make_runtime()
    task = runtime.submit_goal('summarize supplied expenses', run_immediately=False)
    runtime.prepare_supplied_plan(task.id, steps=[{'title':'summarize expenses','tool':'csv_summary',
        'arguments':{'csv_text':'team,amount\nops,10\nops,20\nsales,5\n', 'value_column':'amount','group_column':'team'}}])
    report = runtime.preflight_task(task.id)
    assert report['static_checks_passed'] is True
    result = runtime.run_task(task.id)
    assert result.state == TaskState.SUCCEEDED
    output = result.plan[0].output
    assert output['rows'] == 3
    assert output['groups'] == [{'group':'ops','count':2,'sum':30.0,'mean':15.0,'min':10.0,'max':20.0},
                                {'group':'sales','count':1,'sum':5.0,'mean':5.0,'min':5.0,'max':5.0}]
    assert output['source_verified'] is False
    assert repo.list_actions(task_id=task.id)[0].result == output


@pytest.mark.parametrize('csv_text', ['amount,amount\n1,2\n','amount\nnan\n','amount\nnot numeric\n','amount,x\n1\n','amount\n','amount\n1e308\n1e308\n'])
def test_csv_summary_rejects_bad_data_without_success(csv_text):
    import asyncio
    runtime,_=make_runtime()
    result=asyncio.run(runtime.dispatcher.dispatch('csv_summary',{'csv_text':csv_text,'value_column':'amount'}))
    assert not result.succeeded and result.result is None


def test_csv_summary_bounds_rows_groups_and_preserves_zero_negative_values():
    from app.modules.m20_general_cognitive_worker.local_tools import summarize_csv
    with pytest.raises(ValueError):summarize_csv({'csv_text':'amount\n'+'1\n'*1001,'value_column':'amount'})
    with pytest.raises(ValueError):summarize_csv({'csv_text':'team,amount\n'+''.join(f'{i},1\n' for i in range(101)),
                                               'value_column':'amount','group_column':'team'})
    result=summarize_csv({'csv_text':'amount\n0\n-4\n6\n','value_column':'amount'})
    assert result['groups'][0]['sum']==2 and result['groups'][0]['min']==-4


def test_default_csv_reconciliation_reports_missing_and_changed_records():
    runtime,repo=make_runtime()
    task=runtime.submit_goal('reconcile supplied invoice exports',run_immediately=False)
    runtime.prepare_supplied_plan(task.id,steps=[{'title':'compare exports','tool':'csv_reconcile',
        'arguments':{'left_csv':'id,amount,status\nA,10,open\nB,20,paid\nC,30,open\n',
            'right_csv':'id,amount,status\nA,10,open\nB,21,paid\nD,40,open\n',
            'key_column':'id','compare_columns':['amount','status']}}])
    result=runtime.run_task(task.id)
    assert result.state==TaskState.SUCCEEDED
    output=result.plan[0].output
    assert output['left_only']==['C'] and output['right_only']==['D']
    assert output['unchanged']==['A']
    assert output['changed']==[{'key':'B','fields':{'amount':{'left':'20','right':'21'}}}]
    assert output['source_verified'] is False
    assert repo.list_actions(task_id=task.id)[0].result==output


@pytest.mark.parametrize('left',['id,x\nA,1\nA,2\n','id,x\n,1\n','id,id\nA,1\n','id,x\nA\n'])
def test_reconcile_csv_rejects_ambiguous_keys_and_malformed_exports(left):
    from app.modules.m20_general_cognitive_worker.local_tools import reconcile_csv
    with pytest.raises(ValueError):reconcile_csv({'left_csv':left,'right_csv':'id,x\nA,1\n','key_column':'id','compare_columns':['x']})


def test_reconcile_csv_uses_exact_strings_and_allows_empty_export():
    from app.modules.m20_general_cognitive_worker.local_tools import reconcile_csv
    result=reconcile_csv({'left_csv':'id,x\nA,1.0\n','right_csv':'id,x\nA,1\n','key_column':'id','compare_columns':['x']})
    assert result['changed'][0]['fields']['x']=={'left':'1.0','right':'1'}
    result=reconcile_csv({'left_csv':'id,x\n','right_csv':'id,x\nA,1\n','key_column':'id','compare_columns':['x']})
    assert result['right_only']==['A'] and result['left_count']==0


def test_real_default_csv_filter_to_summary_pipeline_across_restart():
    runtime,repo=make_runtime()
    task=runtime.submit_goal('summarize open supplied invoices',run_immediately=False)
    runtime.prepare_supplied_plan(task.id,steps=[
        {'id':'filter','title':'select open records','tool':'csv_filter',
         'arguments':{'csv_text':'id,status,amount\nA,open,10\nB,paid,20\nC,open,5\n',
                      'where':{'status':'open'},'columns':['id','amount']}},
        {'id':'summary','title':'sum selected records','tool':'csv_summary','depends_on':['filter'],
         'arguments':{'csv_text':{'$step':'filter','path':['csv_text']},'value_column':'amount'}}])
    runtime.run_task(task.id,max_ticks=1,yield_on_boundary=True)
    restored=make_runtime(hydrate_repo=repo)
    result=restored.run_task(task.id,max_ticks=2)
    assert result.state==TaskState.SUCCEEDED
    assert result.plan[0].output['matched_rows']==2
    assert result.plan[1].output['groups'][0]['sum']==15
    assert len(repo.list_actions(task_id=task.id))==2


def test_csv_filter_exact_predicates_quoted_fields_and_empty_matches():
    from app.modules.m20_general_cognitive_worker.local_tools import filter_csv
    result=filter_csv({'csv_text':'id,status,note\nA,open,"a,b"\nB,Open,c\n','where':{'status':'open'},'columns':['note','id']})
    assert result['csv_text']=='note,id\n"a,b",A\n'
    assert result['matched_rows']==1
    result=filter_csv({'csv_text':'id,status\nA,open\n','where':{'status':'paid'}})
    assert result['csv_text']=='id,status\n' and result['matched_rows']==0
    with pytest.raises(ValueError):filter_csv({'csv_text':'id\nA\n','where':{'missing':'x'}})
    with pytest.raises(ValueError):filter_csv({'csv_text':'id\nA\n','columns':['id','id']})


def test_runtime_supervision_reports_actual_durable_blockers_after_restart(mounted):
    client,runtime,repo,_=mounted
    a=runtime.submit_goal('fixture invoice review',run_immediately=False)
    runtime.prepare_supplied_plan(a.id,steps=[{'title':'missing handler','tool':'missing_fixture'}])
    runtime.run_task(a.id,max_ticks=1)
    b=runtime.submit_goal('fixture queued',run_immediately=False)
    response=client.get('/api/modules/20/runtime/supervision')
    assert response.status_code==200
    report=response.json()
    assert report['healthy'] is None
    assert report['tasks_by_state']['failed']==1
    assert report['tasks_by_state']['pending']==1
    assert report['local_action_count']==0
    assert report['task_count']==2
    blocked={r['task_id']:r for r in report['attention_required']}
    assert a.id in blocked
    assert blocked[a.id]['steps'][0]['tool']=='missing_fixture'
    restored=make_runtime(hydrate_repo=repo)
    assert restored.supervision()['tasks_by_state']==report['tasks_by_state']
    assert 'production' in report['boundary']


def test_tool_ranking_and_supervision_use_sql_aggregates_not_full_action_payloads():
    runtime, repo = make_runtime()
    for i, success in enumerate([True, True, False]):
        repo.save_action(ActionRecord(tool='csv_summary', succeeded=success, result={'large': 'x'*10000}))
    def forbidden(*args, **kwargs): raise AssertionError('full journal read forbidden')
    repo.list_actions = forbidden
    selection = runtime.select_tool('summarize csv numeric').as_dict()
    candidate = next(c for c in selection['candidates'] if c['tool_name'] == 'csv_summary')
    assert candidate['historical_success'] == 0.6
    assert candidate['supplied_successes'] == 2 and candidate['supplied_failures'] == 1
    summary = repo.action_summary()
    assert summary == {'local_action_count': 3, 'local_failure_count': 1}


def test_dispatch_aggregate_counts_are_tenant_scoped():
    engine = make_engine()
    a = GCWRepository(engine, tenant_id='a'); a.create_schema()
    b = GCWRepository(engine, tenant_id='b')
    a.save_action(ActionRecord(tool='csv_summary', succeeded=False))
    b.save_action(ActionRecord(tool='csv_summary', succeeded=True))
    assert a.dispatch_outcome_counts() == {'csv_summary': {'successes': 0, 'failures': 1}}
    assert b.dispatch_outcome_counts() == {'csv_summary': {'successes': 1, 'failures': 0}}


def test_runtime_startup_avoids_all_tenant_action_payloads_but_episode_keeps_history():
    runtime,repo=make_runtime()
    task=runtime.submit_goal('fixture pipeline',run_immediately=False)
    runtime.prepare_supplied_plan(task.id,steps=[
        {'id':'a','title':'filter','tool':'csv_filter','arguments':{'csv_text':'amount\n42\n'}},
        {'id':'b','title':'summary','tool':'csv_summary','depends_on':['a'],
         'arguments':{'csv_text':{'$step':'a','path':['csv_text']},'value_column':'amount'}}])
    runtime.run_task(task.id,max_ticks=1,yield_on_boundary=True)
    original=repo.list_actions
    def scoped_only(*,task_id=None):
        if task_id is None:raise AssertionError('unbounded startup journal read')
        return original(task_id=task_id)
    repo.list_actions=scoped_only
    restored=make_runtime(hydrate_repo=repo)
    assert restored.dispatcher.records==[]
    result=restored.run_task(task.id,max_ticks=2)
    assert result.state==TaskState.SUCCEEDED
    episode=repo.list_episodes()[-1]
    assert [a.tool for a in episode.actions]==['csv_filter','csv_summary']


def test_persisted_action_buffer_is_drained_without_losing_sql_episode_history():
    runtime,repo=make_runtime()
    for i in range(10):
        task=runtime.submit_goal(f'fixture summary {i}',run_immediately=False)
        runtime.prepare_supplied_plan(task.id,steps=[{'title':'sum','tool':'csv_summary',
            'arguments':{'csv_text':'amount\n42\n','value_column':'amount'}}])
        runtime.run_task(task.id)
        assert runtime.dispatcher.records==[]
        assert repo.list_actions(task_id=task.id)[0].result['groups'][0]['sum']==42
    assert len(repo.list_episodes())==10
    assert all(len(e.actions)==1 for e in repo.list_episodes())


def test_partial_action_flush_retry_keeps_pending_only_and_never_duplicates(monkeypatch):
    runtime,repo=make_runtime()
    task=runtime.submit_goal('fixture',run_immediately=False)
    runtime.dispatcher.records.extend([ActionRecord(tool='fixture',task_id=task.id) for _ in range(3)])
    original=repo.save_action;calls=0
    def flaky(action):
        nonlocal calls
        calls+=1
        if calls==2:raise RuntimeError('fixture save unavailable')
        return original(action)
    monkeypatch.setattr(repo,'save_action',flaky)
    with pytest.raises(RuntimeError):runtime._persist_context(task)
    assert len(repo.list_actions(task_id=task.id))==1
    runtime._persist_context(task)
    assert len(repo.list_actions(task_id=task.id))==3
    assert runtime.dispatcher.records==[]


def test_runtime_tool_catalog_exposes_actual_local_capabilities_and_schemas(mounted):
    client,runtime,_,_=mounted
    response=client.get('/api/modules/20/runtime/tools')
    assert response.status_code==200
    result=response.json()
    assert result['status']=='registered_handlers_only'
    tools={t['name']:t for t in result['tools']}
    assert {'csv_filter','csv_summary','csv_reconcile'} <= set(tools)
    assert tools['csv_summary']['parameters']['required']==['csv_text','value_column']
    assert tools['csv_filter']['risk']=='read'
    assert result['external_availability_verified'] is False
    assert result['approval_granted'] is False


def test_default_temporal_check_executes_actual_constraint_reasoning_in_plan():
    runtime,repo=make_runtime()
    task=runtime.submit_goal('check supplied approval delivery timing',run_immediately=False)
    runtime.prepare_supplied_plan(task.id,steps=[{'title':'check timing','tool':'temporal_check',
        'arguments':{'temporal_events':['draft','approval','delivery'],'time_unit':'hours',
        'time_constraints':[{'from':'draft','to':'approval','minimum_gap':3},
                            {'from':'approval','to':'delivery','minimum_gap':4},
                            {'from':'draft','to':'delivery','maximum_gap':5}]}}])
    result=runtime.run_task(task.id)
    assert result.state==TaskState.SUCCEEDED
    output=result.plan[0].output
    assert output['status']=='inconsistent'
    assert output['conflict_witness']['total_upper_bound']==-2
    assert repo.list_actions(task_id=task.id)[0].result==output
    # Successful execution of the checker never means the schedule is feasible.
    assert output['witness_relative_times'] is None


def test_actual_dependency_output_check_stops_downstream_when_condition_fails():
    runtime,repo=make_runtime()
    task=runtime.submit_goal('check supplied timing before next work',run_immediately=False)
    runtime.prepare_supplied_plan(task.id,steps=[
        {'id':'check','title':'check timing','tool':'temporal_check','arguments':{
            'temporal_events':['a','b'],'time_unit':'hours','time_constraints':[
                {'from':'a','to':'b','minimum_gap':3,'maximum_gap':4},
                {'from':'b','to':'a','minimum_gap':1}]}},
        {'id':'require','title':'require consistent timing','tool':'require_value','max_attempts':1,'depends_on':['check'],
         'arguments':{'actual':{'$step':'check','path':['status']},'expected':'consistent'}},
        {'id':'later','title':'later work','tool':'csv_summary','depends_on':['require'],
         'arguments':{'csv_text':'amount\n42\n','value_column':'amount'}}])
    result=runtime.run_task(task.id)
    assert result.state==TaskState.FAILED
    assert result.plan[0].state==TaskState.SUCCEEDED
    assert result.plan[1].state==TaskState.FAILED
    assert result.plan[2].state==TaskState.PENDING
    assert [a.tool for a in repo.list_actions(task_id=task.id)]==['temporal_check','require_value']


def test_require_value_exact_json_is_not_truthiness_or_approval():
    from app.modules.m20_general_cognitive_worker.local_tools import require_value
    assert require_value({'actual':{'x':0},'expected':{'x':0}})['matched']
    for actual,expected in [(True,1),(None,False),('Open','open'),(1,1.0)]:
        with pytest.raises(ValueError):require_value({'actual':actual,'expected':expected})
    with pytest.raises(ValueError):require_value({'actual':float('nan'),'expected':float('nan')})


def test_supplied_plan_validates_and_resolves_output_reference_titles_before_execution():
    runtime,repo=make_runtime()
    task=runtime.submit_goal('fixture binding review',run_immediately=False)
    prepared=runtime.prepare_supplied_plan(task.id,steps=[
        {'id':'a','title':'select records','tool':'csv_filter','arguments':{'csv_text':'amount\n42\n'}},
        {'title':'sum','tool':'csv_summary','depends_on':['select records'],
         'arguments':{'csv_text':{'$step':'select records','path':['csv_text']},'value_column':'amount'}}])
    assert prepared.plan[1].arguments['csv_text']['$step']=='a'
    assert runtime.run_task(task.id).state==TaskState.SUCCEEDED
    from app.modules.m20_general_cognitive_worker.htn_planner import PlanError
    for reference in [{'\u0024step':'unknown','path':[]},{'\u0024step':'a','path':[-1]}, {'\u0024step':'a','path':[],'extra':True}]:
        bad=runtime.submit_goal('invalid binding',run_immediately=False)
        with pytest.raises(PlanError):runtime.prepare_supplied_plan(bad.id,steps=[
            {'id':'a','title':'source','tool':'csv_filter','arguments':{'csv_text':'amount\n42\n'}},
            {'title':'target','tool':'csv_summary','depends_on':['a'],'arguments':{'csv_text':reference,'value_column':'amount'}}])
        assert repo.load_task(bad.id).plan==[]


def test_failed_read_step_can_be_corrected_without_rerunning_successful_predecessor(mounted):
    client,runtime,repo,_=mounted
    task=runtime.submit_goal('fixture correction',run_immediately=False)
    runtime.prepare_supplied_plan(task.id,steps=[
        {'id':'a','title':'filter','tool':'csv_filter','arguments':{'csv_text':'amount\n42\n'}},
        {'id':'b','title':'sum','tool':'csv_summary','max_attempts':1,'depends_on':['a'],
         'arguments':{'csv_text':{'$step':'a','path':['csv_text']},'value_column':'missing'}}])
    assert runtime.run_task(task.id).state==TaskState.FAILED
    path=f'/api/modules/20/runtime/tasks/{task.id}/steps/b/retry'
    response=client.post(path,json={'arguments':{'csv_text':{'$step':'a','path':['csv_text']},'value_column':'amount'}})
    assert response.status_code==200
    assert response.json()['state']=='planning'
    assert len(repo.list_actions(task_id=task.id))==2
    completed=client.post(f'/api/modules/20/runtime/tasks/{task.id}/step',json={'max_ticks':2,'quantum_seconds':5})
    assert completed.json()['state']=='succeeded'
    assert [a.tool for a in repo.list_actions(task_id=task.id)]==['csv_filter','csv_summary','csv_summary']
    assert runtime.get_task(task.id).plan[1].output['groups'][0]['sum']==42
    assert client.post(path,json={'arguments':{}}).status_code==409


def test_read_retry_refuses_effectful_failed_step_and_preserves_evidence():
    runtime,repo=make_runtime()
    task=runtime.submit_goal('fixture external',run_immediately=False)
    runtime.prepare_supplied_plan(task.id,steps=[{'id':'a','title':'effect','tool':'fixture_external','risk':'external'}])
    async def handler(args):return {}
    runtime.tools.register(ToolSpec(name='fixture_external',description='fixture',risk=Risk.EXTERNAL),handler)
    task=runtime.get_task(task.id);task.plan[0].state=TaskState.FAILED;task.state=TaskState.FAILED
    runtime._persist_context(task)
    with pytest.raises(ValueError,match='effectful'):runtime.prepare_read_step_retry(task.id,'a',arguments={})
    assert repo.load_task(task.id).plan[0].state==TaskState.FAILED


def test_default_rule_check_derives_review_prerequisites_with_full_proof():
    runtime,repo=make_runtime()
    task=runtime.submit_goal('check supplied release prerequisites',run_immediately=False)
    runtime.prepare_supplied_plan(task.id,steps=[{'title':'check release rules','tool':'rule_check',
        'arguments':{'facts':['tests_passed','owner_reviewed'], 'rules':[
            {'id':'r1','if':['tests_passed'],'then':'technically_ready'},
            {'id':'r2','if':['technically_ready','owner_reviewed'],'then':'release_ready'}],
            'query_atoms':['release_ready','approved_payment']}}])
    result=runtime.run_task(task.id)
    assert result.state==TaskState.SUCCEEDED
    output=result.plan[0].output
    query=next(q for q in output['queries'] if q['atom']=='release_ready')
    assert query['entailed'] is True
    assert query['proof_tree']['rule_id']=='r2'
    assert next(q for q in output['queries'] if q['atom']=='approved_payment')['entailed'] is False
    assert output['source_verified'] is False and output['approval_granted'] is False
    assert repo.list_actions(task_id=task.id)[0].result==output


def test_handler_toolerror_is_retained_failed_execution_not_missing_journal():
    import asyncio
    from app.modules.m20_general_cognitive_worker.tools import ToolError
    runtime,repo=make_runtime()
    calls=[]
    async def handler(args):calls.append(1);raise ToolError('actual local handler diagnostic')
    runtime.tools.register(ToolSpec(name='fixture_toolerror',description='fixture',risk=Risk.READ,max_retries=1),handler)
    task=runtime.submit_goal('fixture diagnostic',run_immediately=False)
    runtime.prepare_supplied_plan(task.id,steps=[{'title':'diagnostic','tool':'fixture_toolerror','max_attempts':1}])
    result=runtime.run_task(task.id)
    assert result.state==TaskState.FAILED
    actions=repo.list_actions(task_id=task.id)
    assert len(actions)==1
    assert not actions[0].succeeded
    assert 'actual local handler diagnostic' in actions[0].result_summary
    assert calls==[1]


def test_handler_gate_shaped_exception_cannot_create_fabricated_pending_approval():
    import asyncio
    from app.modules.m20_general_cognitive_worker.tools import ApprovalPending
    runtime,_=make_runtime()
    async def handler(args):raise ApprovalPending('fixture','fabricated-approval')
    runtime.tools.register(ToolSpec(name='fixture_gate_error',description='fixture',risk=Risk.READ,max_retries=1),handler)
    record=asyncio.run(runtime.dispatcher.dispatch('fixture_gate_error',{}))
    assert not record.succeeded
    assert 'fabricated-approval' in record.result_summary
    assert not runtime.safety.approvals.requests


def test_mcts_scores_selected_prefix_risk_and_failure_at_depth_limit():
    low = PlanNode(title='read', risk=Risk.READ)
    high = PlanNode(title='effect', risk=Risk.IRREVERSIBLE)
    def value(node):
        return BoundedMCTS(max_simulations=5000, max_depth=1, seed=19).search([node]).heuristic_root_value
    # One attempted action: expected progress .9, minus declared attempt cost.
    assert value(low) == pytest.approx(.9 - .1 * .05, abs=.025)
    assert value(high) == pytest.approx(.9 - .1 * .6, abs=.025)
    assert value(high) < value(low)


def test_mcts_never_recommends_started_or_exhausted_step():
    for node in [PlanNode(title='already running', state=TaskState.RUNNING),
                 PlanNode(title='attempts exhausted', attempts=1, max_attempts=1)]:
        result = BoundedMCTS(max_simulations=20, seed=1).search([node])
        assert result.best_action_id is None
        assert result.stopped_by == 'no_ready_action'


def test_mcts_selected_prefix_failure_blocks_dependent_but_runs_sibling():
    parent = PlanNode(id='p',title='parent')
    child = PlanNode(id='c',title='child',depends_on=['p'])
    sibling = PlanNode(id='s',title='sibling')
    search = BoundedMCTS(max_depth=3)
    class FailParent:
        chosen = []
        def choice(self, nodes):
            assert all(n.id != 'c' for n in nodes)
            self.chosen.append(nodes[0].id)
            return nodes[0]
        def random(self):
            return 1.0
    search.random = FailParent()
    reward = search._rollout([parent,child,sibling], set(), 2, prefix=['p','c'])
    assert reward == 0
    assert search.random.chosen == ['s']


def test_method_outcomes_count_observations_not_unfinished_plans_and_survive_reload():
    runtime, repo = make_runtime()
    planner = runtime.planner
    planner.register_method(HTNMethod(name='fixture',goal_pattern='fixture',subtasks=[PlanNode(title='read')]))
    reviewed = planner.method_review_hash(planner.methods['fixture'])
    for _ in range(3): planner.decompose('fixture')
    planner.record_outcome('fixture', True)
    planner.record_outcome('fixture', False)
    current = planner.methods['fixture']
    assert current.success_rate == .5
    assert current.outcomes_recorded == 2 and current.successes_recorded == 1
    assert current.times_used == 3
    assert planner.method_review_hash(current) == reviewed
    from app.modules.m20_general_cognitive_worker.persistence import DurableHTNPlanner
    restarted = DurableHTNPlanner.load(repo, require_review=True)
    assert restarted.methods['fixture'].model_dump() == current.model_dump()
    assert restarted.method_status('fixture') == 'active'
    restarted.record_outcome('fixture', True)
    assert restarted.methods['fixture'].success_rate == pytest.approx(2/3)


def test_method_outcome_requires_boolean_and_does_not_use_legacy_unbacked_rate():
    from app.modules.m20_general_cognitive_worker.htn_planner import HTNPlanner
    planner = HTNPlanner()
    planner.register_method(HTNMethod(name='fixture',goal_pattern='fixture',times_used=100,success_rate=.99,subtasks=[PlanNode(title='read')]))
    with pytest.raises(ValueError): planner.record_outcome('fixture', 'false')
    planner.record_outcome('fixture', False)
    assert planner.methods['fixture'].success_rate == 0
    assert planner.methods['fixture'].outcomes_recorded == 1


def test_method_reported_counts_reopen_file_sql_and_keep_proposed_review_gate(tmp_path):
    from app.modules.m20_general_cognitive_worker.persistence import DurableHTNPlanner
    from app.modules.m20_general_cognitive_worker.schemas import MethodSource
    path = tmp_path / 'methods.sqlite'
    engine = create_engine('sqlite:///' + str(path))
    repo = GCWRepository(engine); repo.create_schema()
    planner = DurableHTNPlanner(repo, require_review=True)
    planner.register_method(HTNMethod(name='proposed',goal_pattern='fixture',source=MethodSource.LEARNED,subtasks=[PlanNode(title='read')]))
    reviewed = planner.method_review_hash(planner.methods['proposed'])
    planner.record_outcome('proposed', True)
    engine.dispose()
    engine2 = create_engine('sqlite:///' + str(path))
    loaded = DurableHTNPlanner.load(GCWRepository(engine2), require_review=True)
    assert loaded.methods['proposed'].success_rate == 1
    assert loaded.methods['proposed'].outcomes_recorded == 1
    assert loaded.method_status('proposed') == 'proposed'
    assert loaded.method_review_hash(loaded.methods['proposed']) == reviewed
    assert loaded._match_method('fixture') is None
    engine2.dispose()


def test_method_inconsistent_reported_counts_reject_and_ratio_is_derived():
    from app.modules.m20_general_cognitive_worker.htn_planner import HTNPlanner, PlanError
    planner = HTNPlanner()
    with pytest.raises(PlanError):
        planner.register_method(HTNMethod(name='bad',goal_pattern='fixture',outcomes_recorded=1,successes_recorded=2,subtasks=[PlanNode(title='read')]))
    planner.register_method(HTNMethod(name='good',goal_pattern='fixture',outcomes_recorded=2,successes_recorded=1,success_rate=.99,subtasks=[PlanNode(title='read')]))
    assert planner.methods['good'].success_rate == .5


def test_failed_actual_read_step_keeps_node_diagnostic_in_supervision_after_reload():
 runtime,repo=make_runtime()
 task=runtime.submit_goal('fixture numeric failure',run_immediately=False)
 runtime.prepare_supplied_plan(task.id,steps=[{'id':'bad','title':'bad summary','tool':'csv_summary','max_attempts':1,
  'arguments':{'csv_text':'value\nnot-numeric\n','value_column':'value'}}])
 result=runtime.run_task(task.id,max_ticks=4,yield_on_boundary=True)
 assert result.plan[0].state==TaskState.FAILED
 assert 'not numeric' in result.plan[0].result_summary
 assert result.plan[0].output is None
 reopened=GCWRuntime(repo)
 report=reopened.supervision()
 step=next(t for t in report['attention_required'] if t['task_id']==task.id)['steps'][0]
 assert 'not numeric' in step['result_summary']
 assert reopened.get_task(task.id).plan[0].result_summary==result.plan[0].result_summary


def test_schema_blocked_step_persists_named_diagnostic_without_fake_action():
 runtime,repo=make_runtime()
 task=runtime.submit_goal('fixture schema failure',run_immediately=False)
 runtime.prepare_supplied_plan(task.id,steps=[{'id':'bad','title':'bad summary','tool':'csv_summary','arguments':{}}])
 result=runtime.run_task(task.id,max_ticks=3,yield_on_boundary=True)
 assert result.plan[0].state==TaskState.BLOCKED
 assert result.plan[0].result_summary.startswith('blocked: ')
 assert result.plan[0].output is None and repo.list_actions(task_id=task.id)==[]
 assert GCWRuntime(repo).get_task(task.id).plan[0].result_summary==result.plan[0].result_summary
