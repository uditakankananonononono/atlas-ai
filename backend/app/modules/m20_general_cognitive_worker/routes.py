"""FastAPI routes for the GCW (spec 4.3 dashboard surface).

Mounted by the integrator at /api/modules/20. The service instance is
injected with bind_service() (or FastAPI dependency override in tests).
All externally visible effects still flow through Module 0 inside the
service - these endpoints only expose control and inspection.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .safety import ApprovalGateDecision
from .schemas import Risk, ToolSpec

router = APIRouter(prefix="/api/modules/20", tags=["m20_general_cognitive_worker"])

_service = None


def bind_service(service) -> None:
    global _service
    _service = service


def get_service():
    if _service is None:
        raise HTTPException(status_code=503, detail="GCW service not bound yet")
    return _service


class GoalRequest(BaseModel):
    goal: str = Field(min_length=1)
    importance: int = Field(default=3, ge=1, le=5)
    deadline: datetime | None = None
    run_immediately: bool = True


class TextIngestRequest(BaseModel):
    text: str = Field(min_length=1)
    source: str = "api"
    external_id: str | None = None
    context_id: str | None = None


class EmailIngestRequest(BaseModel):
    subject: str
    body: str
    sender: str
    external_id: str | None = None
    context_id: str | None = None


class ResumeRequest(BaseModel):
    node_id: str
    approved: bool


class RememberRequest(BaseModel):
    content: str = Field(min_length=1)
    kind: str = "fact"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    decay_rate: float = Field(default=0.0, ge=0.0)


class RetrospectiveRequest(BaseModel):
    went_well: list[str] = []
    went_poorly: list[str] = []
    lessons: list[str] = []


@router.post("/goals", status_code=201)
def submit_goal(request: GoalRequest) -> dict[str, Any]:
    service = get_service()
    context = service.submit_goal(
        request.goal, importance=request.importance,
        deadline=request.deadline, run_immediately=request.run_immediately,
    )
    return {"task_id": context.id, "state": context.state.value,
            "steps": len(context.plan)}


@router.get("/tasks")
def list_tasks() -> list[dict[str, Any]]:
    service = get_service()
    return [
        {"id": c.id, "goal": c.goal, "state": c.state.value,
         "importance": c.importance, "deadline": c.deadline,
         "steps_total": len(c.plan),
         "steps_done": sum(1 for n in c.plan if n.state.value == "succeeded")}
        for c in service.scheduler._contexts.values()
    ]


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    service = get_service()
    context = service.scheduler.get(task_id)
    if context is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {
        "id": context.id, "goal": context.goal, "state": context.state.value,
        "plan": [n.model_dump(mode="json") for n in context.plan],
        "working_memory": service.working_memory.context(partition=context.id),
    }


@router.post("/tasks/{task_id}/resume")
def resume_task(task_id: str, request: ResumeRequest) -> dict[str, Any]:
    service = get_service()
    context = service.resume(task_id, request.node_id, approved=request.approved)
    if context is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task_id": context.id, "state": context.state.value}


@router.post("/tasks/{task_id}/ruminate")
def ruminate_task(task_id: str) -> dict[str, Any]:
    service = get_service()
    result = service.ruminate(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="task not found")
    return result


@router.post("/tasks/{task_id}/retrospective")
def close_task(task_id: str, request: RetrospectiveRequest) -> dict[str, str]:
    service = get_service()
    if service.scheduler.get(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    service.close_task(
        task_id, went_well=request.went_well,
        went_poorly=request.went_poorly, lessons=request.lessons,
    )
    return {"status": "closed"}


@router.post("/ingest/text", status_code=201)
def ingest_text(request: TextIngestRequest) -> dict[str, Any]:
    service = get_service()
    event = service.sensory.ingest_text(
        request.text, source=request.source, external_id=request.external_id,
    )
    if event is None:
        return {"ingested": False, "reason": "duplicate"}
    service.ingest(event, context_id=request.context_id)
    return {"ingested": True, "event_id": event.id}


@router.post("/ingest/email", status_code=201)
def ingest_email(request: EmailIngestRequest) -> dict[str, Any]:
    service = get_service()
    event = service.sensory.ingest_email(
        subject=request.subject, body=request.body, sender=request.sender,
        external_id=request.external_id,
    )
    if event is None:
        return {"ingested": False, "reason": "duplicate"}
    service.ingest(event, context_id=request.context_id)
    return {"ingested": True, "event_id": event.id}


@router.post("/memory/facts", status_code=201)
def remember_fact(request: RememberRequest) -> dict[str, str]:
    service = get_service()
    fact = service.semantic.remember(
        request.content, kind=request.kind,
        confidence=request.confidence, decay_rate=request.decay_rate,
    )
    return {"fact_id": fact.id}


@router.get("/memory/facts")
def query_facts(query: str = "", limit: int = 5) -> list[dict[str, Any]]:
    service = get_service()
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    return [
        {"content": f.content, "kind": f.kind, "confidence": f.confidence, "score": s}
        for f, s in service.semantic.query(query, limit=limit)
    ]


@router.get("/memory/episodes")
def recall_episodes(query: str = "", limit: int = 5) -> list[dict[str, Any]]:
    service = get_service()
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    return [
        {"goal": e.goal, "outcome": e.outcome.value, "reflection": e.reflection, "score": s}
        for e, s in service.episodic.recall_similar(query, limit=limit)
    ]


@router.get("/skills")
def list_skills() -> list[dict[str, Any]]:
    service = get_service()
    return [
        {"id": s.id, "name": s.name, "version": s.version, "status": s.status.value}
        for s in service.skills.list()
    ]


@router.get("/tools")
def list_tools() -> list[dict[str, Any]]:
    return get_service().tools.describe()


@router.get("/standup")
def standup() -> dict[str, str]:
    return {"standup": get_service().standup()}


@router.get("/traces")
def traces(task_id: str | None = None) -> list[dict[str, Any]]:
    return [t.model_dump(mode="json") for t in get_service().traces(task_id=task_id)]


@router.get("/health")
def health() -> dict[str, Any]:
    return get_service().supervise()


# ------------------------------------------------- rows 10-34: meta-cognition
# One mounted route per audit row; thin adapters over the typed engines.

class ImprovementProposalRequest(BaseModel):
    target_name: str
    proposed_content: str = Field(min_length=1)
    expected_gain: float = 0.0


class ImprovementApplyRequest(BaseModel):
    approved: bool
    approval_id: str | None = None


class TransferRequest(BaseModel):
    goal: str = Field(min_length=1)


class ClaimRequest(BaseModel):
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_count: int = Field(default=0, ge=0)


class ClaimResolveRequest(BaseModel):
    correct: bool


class CounterfactualRequest(BaseModel):
    episode_id: str
    alternatives: list[dict[str, Any]]


class TemporalCompareRequest(BaseModel):
    immediate_value: float
    delayed_value: float
    delay_days: float = Field(ge=0.0)
    k: float | None = None


class ContextSwitchRequest(BaseModel):
    from_partition: str
    to_partition: str
    active_goal: str = ""


class FlowAssessRequest(BaseModel):
    challenge: float = Field(ge=0.0, le=1.0)
    skill: float = Field(ge=0.0, le=1.0)


class FlowStructureRequest(BaseModel):
    tasks: list[dict[str, Any]]
    skill: float = Field(ge=0.0, le=1.0)


class ReframeRequest(BaseModel):
    setback: str = Field(min_length=1)


class BiasScanRequest(BaseModel):
    text: str = Field(min_length=1)


class IntuitionRequest(BaseModel):
    question: str = Field(min_length=1)


class WorldModelRequest(BaseModel):
    name: str = Field(min_length=1)
    assumptions: dict[str, str]


class WorldModelEvidenceRequest(BaseModel):
    supported: bool
    weight: float = 1.0


class WorldModelReviseRequest(BaseModel):
    assumptions: dict[str, str]


class GoalConflictRequest(BaseModel):
    plan: list[dict[str, Any]]
    terminal_values: list[str] | None = None


class RoutineDecisionRequest(BaseModel):
    decision_type: str
    options: list[str]
    routine: bool = True
    stakes: str = "low"


class RegretRequest(BaseModel):
    options: dict[str, dict[str, float]]


class SacrificeRequest(BaseModel):
    chosen: dict[str, Any]
    alternatives: list[dict[str, Any]]


class SunkCostRequest(BaseModel):
    options: list[dict[str, Any]]


class HorizonRequest(BaseModel):
    uncertainty: float = Field(ge=0.0, le=1.0)
    time_available_minutes: float = Field(gt=0.0)


class RollupRequest(BaseModel):
    goal: str
    plan: list[dict[str, Any]]
    level: str


class PerspectivesRequest(BaseModel):
    proposal: dict[str, Any]


class StressTestRequest(BaseModel):
    claim: str
    assumptions: list[str] = []
    evidence: list[str] = []


class SteelmanRequest(BaseModel):
    opposing_position: str
    known_facts: list[str] = []


class BeliefRequest(BaseModel):
    content: str = Field(min_length=1)
    review_interval_days: int = Field(default=90, gt=0)


class CuriosityGapsRequest(BaseModel):
    text: str = Field(min_length=1)


class CuriosityExploreRequest(BaseModel):
    idle_budget: float = Field(gt=0.0)


@router.post("/meta/improvement/proposals", status_code=201)
def row10_propose_improvement(request: ImprovementProposalRequest) -> dict[str, Any]:
    service = get_service()
    metrics = service.improvement.analyze(
        tool_records=service.dispatcher.records,
        episodes=list(service.episodic._episodes.values()),
        calibration_error=service.calibration.calibration_error(),
    )
    try:
        proposal = service.improvement.propose(
            request.target_name, request.proposed_content,
            evidence=metrics, expected_gain=request.expected_gain,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown prompt template")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"proposal_id": proposal.id, "status": proposal.status.value,
            "evidence": proposal.evidence}


@router.post("/meta/improvement/proposals/{proposal_id}/apply")
def row10_apply_improvement(proposal_id: str, request: ImprovementApplyRequest) -> dict[str, Any]:
    service = get_service()
    if proposal_id not in service.improvement.proposals:
        raise HTTPException(status_code=404, detail="proposal not found")
    try:
        template = service.improvement.apply(
            proposal_id, approved=request.approved, approval_id=request.approval_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"target": template.name, "version": template.version, "applied": True}


@router.post("/meta/meta-learning/transfer")
def row11_meta_learning_transfer(request: TransferRequest) -> dict[str, Any]:
    service = get_service()
    for episode in service.episodic._episodes.values():
        service.meta_learner.abstract(episode)
    return {"transfers": service.meta_learner.transfer(request.goal)}


@router.post("/meta/load-allocation")
def row12_load_balancing(total_ticks: float = 100.0) -> dict[str, Any]:
    service = get_service()
    allocation = service.load_balancer.allocate(
        list(service.scheduler._contexts.values()), total_ticks=total_ticks,
    )
    return {"allocation": allocation}


@router.post("/meta/calibration/claims", status_code=201)
def row13_assess_claim(request: ClaimRequest) -> dict[str, Any]:
    claim = get_service().calibration.assess_claim(
        request.text, request.confidence, evidence_count=request.evidence_count,
    )
    return {"claim_id": claim.id, "flagged": claim.flagged, "flag_reason": claim.flag_reason}


@router.post("/meta/calibration/claims/{claim_id}/resolve")
def row13_resolve_claim(claim_id: str, request: ClaimResolveRequest) -> dict[str, Any]:
    service = get_service()
    if claim_id not in service.calibration.claims:
        raise HTTPException(status_code=404, detail="claim not found")
    claim = service.calibration.resolve(claim_id, request.correct)
    return {"claim_id": claim.id, "resolved": claim.resolved}


@router.get("/meta/calibration/curve")
def row13_calibration_curve() -> dict[str, Any]:
    service = get_service()
    return {"curve": service.calibration.calibration_curve(),
            "calibration_error": service.calibration.calibration_error()}


@router.post("/meta/counterfactuals")
def row14_counterfactual(request: CounterfactualRequest) -> dict[str, Any]:
    service = get_service()
    episode = service.episodic.get(request.episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="episode not found")
    return service.counterfactuals.simulate(episode, request.alternatives)


@router.post("/meta/temporal/compare")
def row15_temporal_compare(request: TemporalCompareRequest) -> dict[str, Any]:
    return get_service().temporal.compare(
        immediate_value=request.immediate_value, delayed_value=request.delayed_value,
        delay_days=request.delay_days, k=request.k,
    )


@router.post("/meta/context-switch")
def row16_context_switch(request: ContextSwitchRequest) -> dict[str, Any]:
    service = get_service()
    report = service.residue.switch(
        service.working_memory, from_partition=request.from_partition,
        to_partition=request.to_partition, active_goal=request.active_goal,
    )
    return report.__dict__


@router.post("/meta/flow/assess")
def row17_flow_assess(request: FlowAssessRequest) -> dict[str, Any]:
    return get_service().flow.assess(challenge=request.challenge, skill=request.skill)


@router.post("/meta/flow/structure")
def row17_flow_structure(request: FlowStructureRequest) -> dict[str, Any]:
    return {"structured": get_service().flow.structure_work(request.tasks, skill=request.skill)}


@router.post("/meta/reframe")
def row18_reframe(request: ReframeRequest) -> dict[str, Any]:
    reframe = get_service().reframing.reframe(request.setback)
    return reframe.__dict__


@router.post("/meta/bias-scan")
def row19_bias_scan(request: BiasScanRequest) -> dict[str, Any]:
    return get_service().bias_detector.scan_with_correction(request.text)


@router.post("/meta/intuition")
def row20_intuition(request: IntuitionRequest) -> dict[str, Any]:
    service = get_service()
    gut = service.intuition.gut(
        request.question,
        skill_matches=service.skills.match(request.question),
        fact_hits=service.semantic.query(request.question, limit=1),
    )
    return {"answer": gut.answer, "confidence": gut.confidence, "basis": gut.basis,
            "latency_class": gut.latency_class}


@router.post("/meta/world-models", status_code=201)
def row21_register_world_model(request: WorldModelRequest) -> dict[str, Any]:
    model = get_service().world_models.register(request.name, request.assumptions)
    return {"name": model.name, "version": model.version, "posterior": model.posterior}


@router.post("/meta/world-models/{name}/evidence")
def row21_world_model_evidence(name: str, request: WorldModelEvidenceRequest) -> dict[str, Any]:
    service = get_service()
    if name not in service.world_models.models:
        raise HTTPException(status_code=404, detail="model not found")
    model = service.world_models.apply_evidence(name, supported=request.supported, weight=request.weight)
    return {"name": model.name, "posterior": model.posterior}


@router.post("/meta/world-models/{name}/revise")
def row21_revise_world_model(name: str, request: WorldModelReviseRequest) -> dict[str, Any]:
    service = get_service()
    if name not in service.world_models.models:
        raise HTTPException(status_code=404, detail="model not found")
    model = service.world_models.revise(name, request.assumptions)
    return {"name": model.name, "version": model.version}


@router.get("/meta/world-models")
def row21_list_world_models() -> dict[str, Any]:
    service = get_service()
    best = service.world_models.current_best()
    return {
        "models": [{"name": m.name, "version": m.version, "posterior": m.posterior}
                   for m in service.world_models.models.values()],
        "current_best": best.name if best else None,
    }


@router.post("/meta/goals/check-conflicts")
def row22_goal_conflicts(request: GoalConflictRequest) -> dict[str, Any]:
    from .schemas import PlanNode as _PlanNode
    service = get_service()
    if request.terminal_values is not None:
        service.goal_hierarchy.terminal_values = [v.lower() for v in request.terminal_values]
    plan = [_PlanNode(**n) for n in request.plan]
    return service.goal_hierarchy.restructure(plan)


@router.post("/meta/decisions/routine")
def row23_routine_decision(request: RoutineDecisionRequest) -> dict[str, Any]:
    from .metacognition import RoutinePolicy as _RoutinePolicy
    service = get_service()
    if request.decision_type not in service.decision_guard.policies and request.options:
        service.decision_guard.add_policy(_RoutinePolicy(
            decision_type=request.decision_type, default_choice=request.options[0],
        ))
    return service.decision_guard.decide(
        request.decision_type, options=request.options,
        routine=request.routine, stakes=request.stakes,
    )


@router.post("/meta/decisions/regret")
def row24_regret(request: RegretRequest) -> dict[str, Any]:
    from .metacognition import project_regret as _project_regret
    try:
        return _project_regret(request.options)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/decisions/opportunity-cost")
def row25_opportunity_cost(request: SacrificeRequest) -> dict[str, Any]:
    from .metacognition import quantify_sacrifice as _quantify
    return _quantify(request.chosen, request.alternatives)


@router.post("/meta/decisions/sunk-cost")
def row26_sunk_cost(request: SunkCostRequest) -> dict[str, Any]:
    from .metacognition import sunk_cost_choice as _sunk
    try:
        return _sunk(request.options)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/planning-horizon")
def row27_horizon(request: HorizonRequest) -> dict[str, Any]:
    try:
        return get_service().horizon.horizon(
            uncertainty=request.uncertainty,
            time_available_minutes=request.time_available_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/abstraction/rollup")
def row28_rollup(request: RollupRequest) -> dict[str, Any]:
    from .schemas import PlanNode as _PlanNode
    plan = [_PlanNode(**n) for n in request.plan]
    try:
        return get_service().abstraction.rollup(request.goal, plan, level=request.level)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/perspectives")
def row29_perspectives(request: PerspectivesRequest) -> dict[str, Any]:
    views = get_service().perspectives.evaluate(request.proposal)
    return {"perspectives": [v.__dict__ for v in views]}


@router.post("/meta/devils-advocate")
def row30_devils_advocate(request: StressTestRequest) -> dict[str, Any]:
    report = get_service().devils_advocate.stress_test(
        claim=request.claim, assumptions=request.assumptions, evidence=request.evidence,
    )
    return report.__dict__


@router.post("/meta/steelman")
def row31_steelman(request: SteelmanRequest) -> dict[str, Any]:
    report = get_service().steelman.strengthen(
        opposing_position=request.opposing_position, known_facts=request.known_facts,
    )
    return report.__dict__


@router.post("/meta/epistemic-calendar/beliefs", status_code=201)
def row32_register_belief(request: BeliefRequest) -> dict[str, Any]:
    entry = get_service().epistemic_calendar.register(
        request.content, review_interval_days=request.review_interval_days,
    )
    return {"belief_id": entry.belief_id, "next_review": entry.next_review().isoformat()}


@router.get("/meta/epistemic-calendar/due")
def row32_due_beliefs() -> dict[str, Any]:
    return {"due": get_service().epistemic_calendar.due()}


@router.get("/meta/knowledge-decay/forecast")
def row33_decay_forecast(days_ahead: float = 30.0, threshold: float = 0.5) -> dict[str, Any]:
    service = get_service()
    return {"forecast": service.decay_modeler.forecast(
        service.semantic, days_ahead=days_ahead, threshold=threshold,
    )}


@router.post("/meta/curiosity/gaps")
def row34_detect_gaps(request: CuriosityGapsRequest) -> dict[str, Any]:
    service = get_service()
    return {"gaps": service.curiosity.detect_gaps(request.text, service.semantic)}


@router.post("/meta/curiosity/explore")
def row34_explore(request: CuriosityExploreRequest) -> dict[str, Any]:
    service = get_service()
    items = service.curiosity.allocate(idle_budget=request.idle_budget)
    return {"exploration": [i.__dict__ for i in items]}
