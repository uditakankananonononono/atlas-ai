"""Chunk 4 tests: GCW service facade, standup, supervision."""
from datetime import datetime, timedelta, timezone

from app.modules.m20_general_cognitive_worker.safety import (
    ApprovalGateDecision, InMemoryApprovalGate,
)
from app.modules.m20_general_cognitive_worker.schemas import Risk, TaskState, ToolSpec
from app.modules.m20_general_cognitive_worker.service import (
    CognitiveWorkerService, JUDGMENT_SKILLS,
)


def build_service():
    gate = InMemoryApprovalGate()
    service = CognitiveWorkerService(approval_gate=gate)

    async def search(args):
        return {"results": ["r1", "r2"]}

    async def send(args):
        return {"sent": True}

    service.tools.register(
        ToolSpec(name="web_search", description="search", risk=Risk.READ), search)
    service.tools.register(
        ToolSpec(name="send_email", description="send", risk=Risk.EXTERNAL), send)
    from app.modules.m20_general_cognitive_worker.schemas import HTNMethod, PlanNode
    service.planner.register_method(HTNMethod(
        name="research-report", goal_pattern="research topic and send summary",
        subtasks=[
            PlanNode(title="research", tool="web_search", risk=Risk.READ),
            PlanNode(title="send summary", tool="send_email", risk=Risk.EXTERNAL,
                     depends_on=["research"]),
        ],
    ))
    return service, gate


def test_judgment_skills_seeded_and_matched():
    service = CognitiveWorkerService()
    names = [s.name for s in service.skills.list()]
    for entry in JUDGMENT_SKILLS:
        assert entry["name"] in names
    matches = service.skills.match("please stress test my conclusion")
    assert matches and matches[0].name == "devils-advocate"


def test_goal_flow_pause_approve_and_standup():
    service, gate = build_service()
    ctx = service.submit_goal("research topic and send summary", importance=4)
    assert ctx.state == TaskState.WAITING_APPROVAL
    waiting = [n for n in ctx.plan if n.state == TaskState.WAITING_APPROVAL][0]
    gate.decide(waiting.approval_id, ApprovalGateDecision.APPROVED)
    resumed = service.resume(ctx.id, waiting.id, approved=True)
    assert resumed.state == TaskState.SUCCEEDED
    standup = service.standup()
    assert "research topic and send summary" in standup
    assert "[succeeded]" in standup
    health = service.supervise()
    assert health["healthy"] is True
    assert health["tool_calls"] >= 2 and health["tool_failures"] == 0
    assert health["episodes"] >= 1


def test_ingest_routes_into_working_memory_partition():
    service, _ = build_service()
    ctx = service.submit_goal("research topic and send summary", run_immediately=False)
    event = service.sensory.ingest_text("competitor raised prices", source="api")
    service.ingest(event, context_id=ctx.id)
    chunks = service.working_memory.focused(partition=ctx.id)
    assert any("competitor raised prices" in c.content for c in chunks)


def test_scheduler_tick_and_rumination():
    service, _ = build_service()
    deadline = datetime.now(timezone.utc) + timedelta(hours=1)
    ctx = service.submit_goal("research topic and send summary",
                              deadline=deadline, run_immediately=False)
    service.submit_goal("research topic and send summary", importance=1, run_immediately=False)
    nxt = service.scheduler.next_context()
    assert nxt.id == ctx.id  # deadline proximity wins
    ctx.plan = service.planner.decompose(ctx.goal)  # rumination needs a plan
    result = service.ruminate(ctx.id)
    assert result is not None and result["simulations"] > 0


def test_close_task_clears_partition_and_stores_lessons():
    service, _ = build_service()
    ctx = service.submit_goal("research topic and send summary", run_immediately=False)
    service.close_task(ctx.id, went_well=["fast research"],
                       went_poorly=["late send"], lessons=["send earlier"])
    assert service.working_memory.focused(partition=ctx.id) == []
    hits = service.retrospectives.lessons_for("sending research summaries")
    assert hits and "send earlier" in " ".join(hits[0][0].lessons)
