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

from .foresight import SystemsModel
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


# ----------------------------------------------------------- rows 35-59 --
# Simulation, forecasting and decision-analysis surface (/meta/...).

class SerendipityRequest(BaseModel):
    text: str = Field(min_length=1)
    available_slots: int = Field(default=5, ge=0)
    epsilon: float | None = Field(default=None, ge=0.0, le=1.0)
    seed: int | None = None


class InsightRequest(BaseModel):
    text: str = Field(min_length=1)
    context: str = ""


class InsightDevelopRequest(BaseModel):
    note: str = Field(min_length=1)


class SimulationPredictRequest(BaseModel):
    domain: str = Field(min_length=1)
    predicted: float
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class SimulationResolveRequest(BaseModel):
    actual: float


class HypothesisRequest(BaseModel):
    statement: str = Field(min_length=1)
    prior: float = Field(gt=0.0, lt=1.0)


class HypothesisEvidenceRequest(BaseModel):
    likelihood_ratios: dict[str, float]


class BayesianRequest(BaseModel):
    prior: float = Field(ge=0.0, le=1.0)
    likelihood_ratio: float = Field(gt=0.0)


class CausalRequest(BaseModel):
    cause: str = Field(min_length=1)
    effect: str = Field(min_length=1)
    evidence: dict[str, bool] = Field(default_factory=dict)


class BaseRateRequest(BaseModel):
    base_rate: float = Field(ge=0.0, le=1.0)
    case_estimate: float = Field(ge=0.0, le=1.0)
    evidence_reliability: float = Field(default=0.5, ge=0.0, le=1.0)
    sample_size: int = Field(default=0, ge=0)


class ReferenceCaseRequest(BaseModel):
    features: str = Field(min_length=1)
    outcome: float
    label: str | None = None


class ReferenceForecastRequest(BaseModel):
    features: str = Field(min_length=1)


class OutsideViewRequest(BaseModel):
    inside_estimate: float
    outside_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    subject: str = "this project"


class OverrunRecordRequest(BaseModel):
    kind: str = Field(min_length=1)
    estimated: float = Field(gt=0.0)
    actual: float = Field(ge=0.0)


class OverrunCorrectRequest(BaseModel):
    kind: str = Field(min_length=1)
    estimate: float = Field(gt=0.0)


class OptimismRecordRequest(BaseModel):
    domain: str = Field(min_length=1)
    predicted_confidence: float = Field(ge=0.0, le=1.0)
    succeeded: bool


class OptimismAdjustRequest(BaseModel):
    domain: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class ScenarioRequest(BaseModel):
    objective: str = Field(min_length=1)
    drivers: list[str] = Field(min_length=1)
    probabilities: dict[str, float] | None = None


class PremortemRequest(BaseModel):
    goal: str = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    failure_date: datetime | None = None


class RedTeamRequest(BaseModel):
    plan: str = Field(min_length=1)
    assets: list[str] = Field(default_factory=list)


class SecondOrderRequest(BaseModel):
    action: str = Field(min_length=1)
    first_order: list[str] = Field(min_length=1)
    depth: int = Field(default=2, ge=1, le=4)


class SystemsLinkRequest(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    sign: str = Field(pattern=r"^[+-]$")
    delay: str = ""


class SystemsModelRequest(BaseModel):
    links: list[SystemsLinkRequest] = Field(default_factory=list)


class ConstraintRequest(BaseModel):
    stages: list[dict[str, Any]] = Field(min_length=1)


class AntifragilityRequest(BaseModel):
    components: list[dict[str, Any]] = Field(min_length=1)


class OptionalityRequest(BaseModel):
    decision: str = Field(min_length=1)
    options_kept: list[str] = Field(default_factory=list)
    options_closed: list[str] = Field(default_factory=list)
    reversible: bool = False


class ReversibilityRequest(BaseModel):
    decision: str = Field(min_length=1)
    undo_cost: float = Field(ge=0.0, le=10.0)
    undo_days: float = Field(ge=0.0)
    blast_radius: float = Field(ge=0.0, le=10.0)


class AsymmetryRequest(BaseModel):
    options: list[dict[str, Any]] = Field(min_length=1)


class EVRequest(BaseModel):
    options: list[dict[str, Any]] = Field(min_length=1)


class RiskOfRuinRequest(BaseModel):
    capital: float = Field(gt=0.0)
    bet_size: float = Field(gt=0.0)
    win_prob: float = Field(ge=0.0, le=1.0)
    payoff_ratio: float = Field(default=1.0, gt=0.0)
    trials: int = Field(default=100, ge=1)


class KellyRequest(BaseModel):
    win_prob: float = Field(ge=0.0, le=1.0)
    payoff_ratio: float = Field(gt=0.0)


@router.post("/meta/serendipity/plan")
def row35_serendipity(request: SerendipityRequest) -> dict[str, Any]:
    service = get_service()
    gaps = service.curiosity.detect_gaps(request.text, service.semantic)
    engine = service.serendipity if request.epsilon is None else type(service.serendipity)(epsilon=request.epsilon)
    topics = [f.content for f, _ in service.semantic.query(request.text, limit=6, min_score=0.05)]
    slots = engine.plan(gaps, available_slots=request.available_slots,
                        known_topics=topics, seed=request.seed)
    return {"epsilon": engine.epsilon, "gaps": gaps, "slots": [s.__dict__ for s in slots],
            "note": "Suggestions only - any external action still requires the normal approval path"}


@router.post("/meta/insights", status_code=201)
def row36_capture_insight(request: InsightRequest) -> dict[str, Any]:
    service = get_service()
    insight = service.insights.capture(request.text, context=request.context,
                                       semantic_memory=service.semantic)
    return {"insight_id": insight.insight_id, "links": insight.links,
            "development_prompts": service.insights.development_prompts(insight.insight_id)}


@router.post("/meta/insights/{insight_id}/develop")
def row36_develop_insight(insight_id: str, request: InsightDevelopRequest) -> dict[str, Any]:
    service = get_service()
    try:
        insight = service.insights.develop(insight_id, request.note)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown insight_id")
    return {"insight_id": insight.insight_id, "status": insight.status,
            "developments": insight.developments}


@router.get("/meta/insights/stale")
def row36_stale_insights(older_than_days: float = 7.0) -> dict[str, Any]:
    stale = get_service().insights.stale(older_than_days=older_than_days)
    return {"stale": [{"insight_id": i.insight_id, "text": i.text,
                       "captured_at": i.captured_at.isoformat()} for i in stale]}


@router.post("/meta/simulations", status_code=201)
def row37_record_simulation(request: SimulationPredictRequest) -> dict[str, Any]:
    rec = get_service().sim_fidelity.record_prediction(
        request.domain, request.predicted, confidence=request.confidence)
    return {"record_id": rec.record_id}


@router.post("/meta/simulations/{record_id}/resolve")
def row37_resolve_simulation(record_id: str, request: SimulationResolveRequest) -> dict[str, Any]:
    service = get_service()
    try:
        rec = service.sim_fidelity.resolve(record_id, request.actual)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown record_id")
    return {"record_id": rec.record_id, "fidelity": rec.fidelity,
            "domain_fidelity": service.sim_fidelity.fidelity(domain=rec.domain),
            "confidence_adjustment": service.sim_fidelity.confidence_adjustment(domain=rec.domain)}


@router.post("/meta/hypotheses", status_code=201)
def row38_add_hypothesis(request: HypothesisRequest) -> dict[str, Any]:
    h = get_service().hypotheses.add(request.statement, prior=request.prior)
    return {"hypothesis_id": h.hypothesis_id}


@router.post("/meta/hypotheses/evidence")
def row38_update_hypotheses(request: HypothesisEvidenceRequest) -> dict[str, Any]:
    service = get_service()
    try:
        ranking = service.hypotheses.update(request.likelihood_ratios)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown hypothesis_id: {exc}")
    return {"ranking": [{"hypothesis_id": h.hypothesis_id, "statement": h.statement,
                         "probability": h.probability, "evidence_count": h.evidence_count}
                        for h in ranking]}


@router.post("/meta/bayes/update")
def row39_bayesian_update(request: BayesianRequest) -> dict[str, Any]:
    service = get_service()
    posterior = service.bayes.update(request.prior, request.likelihood_ratio)
    return {"prior": request.prior, "likelihood_ratio": request.likelihood_ratio,
            "posterior": posterior}


@router.post("/meta/causal/assess")
def row40_causal_assess(request: CausalRequest) -> dict[str, Any]:
    report = get_service().causal.assess(cause=request.cause, effect=request.effect,
                                         evidence=request.evidence)
    return report.__dict__


@router.post("/meta/base-rate/integrate")
def row41_base_rate(request: BaseRateRequest) -> dict[str, Any]:
    estimate = get_service().base_rates.integrate(
        base_rate=request.base_rate, case_estimate=request.case_estimate,
        evidence_reliability=request.evidence_reliability, sample_size=request.sample_size)
    return estimate.__dict__


@router.post("/meta/reference-class/cases", status_code=201)
def row42_add_case(request: ReferenceCaseRequest) -> dict[str, Any]:
    service = get_service()
    service.reference_class.add_case(request.features, request.outcome, label=request.label)
    return {"cases": len(service.reference_class.cases)}


@router.post("/meta/reference-class/forecast")
def row42_forecast(request: ReferenceForecastRequest) -> dict[str, Any]:
    forecast = get_service().reference_class.forecast(request.features)
    if forecast is None:
        return {"forecast": None, "reason": "no reference cases recorded yet"}
    return {"forecast": forecast.__dict__}


@router.post("/meta/outside-view")
def row43_outside_view(request: OutsideViewRequest) -> dict[str, Any]:
    service = get_service()
    forecast = service.reference_class.forecast(request.subject)
    report = service.outside_view.adopt(inside_estimate=request.inside_estimate,
                                        reference_forecast=forecast,
                                        outside_weight=request.outside_weight,
                                        subject=request.subject)
    return report.__dict__


@router.post("/meta/planning-fallacy/records", status_code=201)
def row44_record_overrun(request: OverrunRecordRequest) -> dict[str, Any]:
    service = get_service()
    service.planning_fallacy.record(kind=request.kind, estimated=request.estimated,
                                    actual=request.actual)
    mult, n = service.planning_fallacy.multiplier(request.kind)
    return {"kind": request.kind, "multiplier": mult, "samples": n}


@router.post("/meta/planning-fallacy/correct")
def row44_correct_estimate(request: OverrunCorrectRequest) -> dict[str, Any]:
    return get_service().planning_fallacy.correct(kind=request.kind, estimate=request.estimate)


@router.post("/meta/optimism/records", status_code=201)
def row45_record_outcome(request: OptimismRecordRequest) -> dict[str, Any]:
    service = get_service()
    service.optimism.record(domain=request.domain,
                            predicted_confidence=request.predicted_confidence,
                            succeeded=request.succeeded)
    bias, n = service.optimism.bias(request.domain)
    return {"domain": request.domain, "bias": bias, "samples": n}


@router.post("/meta/optimism/adjust")
def row45_adjust_confidence(request: OptimismAdjustRequest) -> dict[str, Any]:
    return get_service().optimism.adjust(domain=request.domain, confidence=request.confidence)


@router.post("/meta/scenarios")
def row46_scenarios(request: ScenarioRequest) -> dict[str, Any]:
    return get_service().scenarios.plan(objective=request.objective, drivers=request.drivers,
                                        probabilities=request.probabilities)


@router.post("/meta/premortem")
def row47_premortem(request: PremortemRequest) -> dict[str, Any]:
    return get_service().premortem.analyze(goal=request.goal, risks=request.risks,
                                           failure_date=request.failure_date)


@router.post("/meta/red-team")
def row48_red_team(request: RedTeamRequest) -> dict[str, Any]:
    return get_service().red_team.probe(plan=request.plan, assets=request.assets)


@router.post("/meta/second-order")
def row49_second_order(request: SecondOrderRequest) -> dict[str, Any]:
    return get_service().second_order.trace(action=request.action,
                                            first_order=request.first_order,
                                            depth=request.depth)


@router.post("/meta/systems/loops")
def row50_systems_loops(request: SystemsModelRequest) -> dict[str, Any]:
    model = SystemsModel()
    for link in request.links:
        model.add_link(link.source, link.target, sign=link.sign, delay=link.delay)
    return {"loops": [loop.__dict__ for loop in model.loops()],
            "emergence_notes": model.emergence_notes()}


@router.post("/meta/systems/leverage")
def row51_leverage(request: SystemsModelRequest) -> dict[str, Any]:
    model = SystemsModel()
    for link in request.links:
        model.add_link(link.source, link.target, sign=link.sign, delay=link.delay)
    points = get_service().leverage.rank(model)
    return {"leverage_points": [p.__dict__ for p in points]}


@router.post("/meta/constraints/analyze")
def row52_constraints(request: ConstraintRequest) -> dict[str, Any]:
    return get_service().constraints.analyze(stages=request.stages)


@router.post("/meta/antifragility/assess")
def row53_antifragility(request: AntifragilityRequest) -> dict[str, Any]:
    return get_service().antifragility.assess(components=request.components)


@router.post("/meta/optionality/assess")
def row54_optionality(request: OptionalityRequest) -> dict[str, Any]:
    return get_service().optionality.assess(
        decision=request.decision, options_kept=request.options_kept,
        options_closed=request.options_closed, reversible=request.reversible)


@router.post("/meta/reversibility/assess")
def row55_reversibility(request: ReversibilityRequest) -> dict[str, Any]:
    return get_service().reversibility.assess(
        decision=request.decision, undo_cost=request.undo_cost,
        undo_days=request.undo_days, blast_radius=request.blast_radius)


@router.post("/meta/asymmetry/evaluate")
def row56_asymmetry(request: AsymmetryRequest) -> dict[str, Any]:
    return get_service().asymmetry.evaluate(options=request.options)


@router.post("/meta/ev/compute")
def row57_expected_value(request: EVRequest) -> dict[str, Any]:
    return get_service().ev_calculator.compute(options=request.options)


@router.post("/meta/risk-of-ruin")
def row58_risk_of_ruin(request: RiskOfRuinRequest) -> dict[str, Any]:
    return get_service().risk_of_ruin.analyze(
        capital=request.capital, bet_size=request.bet_size, win_prob=request.win_prob,
        payoff_ratio=request.payoff_ratio, trials=request.trials)


@router.post("/meta/kelly/size")
def row59_kelly(request: KellyRequest) -> dict[str, Any]:
    return get_service().kelly.size(win_prob=request.win_prob, payoff_ratio=request.payoff_ratio)


# ----------------------------------------------------------- rows 60-84 --
# Strategic and quantitative decision aids (/meta/...).

class ErgodicityRequest(BaseModel):
    outcomes: list[list[float]] = Field(min_length=1)


class NonLinearRequest(BaseModel):
    xs: list[float] = Field(min_length=3)
    ys: list[float] = Field(min_length=3)


class NonLinearExtrapolateRequest(BaseModel):
    model: str
    slope: float
    intercept: float
    x: float = Field(gt=0.0)


class TippingPointRequest(BaseModel):
    series: list[float] = Field(min_length=8)
    threshold: float | None = None


class NetworkEffectRequest(BaseModel):
    n_users: int = Field(ge=0)
    two_sided: bool = False
    same_side: bool = True


class MoatRequest(BaseModel):
    ratings: dict[str, dict[str, Any]]


class DisruptionRequest(BaseModel):
    entrant_improvement_rate: float = Field(ge=0.0)
    incumbent_improvement_rate: float = Field(ge=0.0)
    entrant_targets_underserved: bool
    entrant_cheaper: bool
    incumbent_overserving: bool = False


class JTBDRequest(BaseModel):
    product: str = Field(min_length=1)
    statements: list[str] = Field(min_length=1)


class ValueChainRequest(BaseModel):
    stages: list[dict[str, Any]] = Field(min_length=1)


class ParetoRequest(BaseModel):
    items: dict[str, float]
    target_share: float = Field(default=0.8, gt=0.0, le=1.0)


class TOCRequest(BaseModel):
    stages: list[dict[str, Any]] = Field(min_length=1)


class QueueRequest(BaseModel):
    arrival_rate: float = Field(ge=0.0)
    service_rate: float = Field(gt=0.0)
    servers: int = Field(default=1, ge=1)


class LittlesLawRequest(BaseModel):
    wip: float | None = None
    throughput: float | None = None
    cycle_time: float | None = None


class CriticalPathRequest(BaseModel):
    tasks: list[dict[str, Any]] = Field(min_length=1)


class MonteCarloRequest(BaseModel):
    tasks: list[dict[str, float]] = Field(min_length=1)
    trials: int = Field(default=1000, ge=10)
    seed: int | None = 42


class SensitivityRequest(BaseModel):
    expression: str = Field(min_length=1)
    params: dict[str, float] = Field(min_length=1)
    swing: float = Field(default=0.2, gt=0.0, lt=1.0)


class DecisionTreeRequest(BaseModel):
    spec: dict[str, Any]


class RealOptionsRequest(BaseModel):
    underlying: float = Field(gt=0.0)
    up: float = Field(ge=1.0)
    down: float = Field(gt=0.0, lt=1.0)
    exercise_cost: float = Field(ge=0.0)
    kind: str = "expand"
    steps: int = Field(default=10, ge=1, le=50)
    risk_free: float = 0.0


class GameRequest(BaseModel):
    row_payoffs: list[list[float]]
    col_payoffs: list[list[float]]


class VCGRequest(BaseModel):
    agents: dict[str, dict[str, float]]


class ICCheckRequest(BaseModel):
    agent: str
    true_values: dict[str, float]
    others: dict[str, dict[str, float]] = Field(default_factory=dict)
    deviations: list[dict[str, float]] = Field(default_factory=list)


class AuctionRequest(BaseModel):
    auction_type: str
    value: float = Field(ge=0.0)
    n_bidders: int = Field(default=2, ge=2)
    common_value: bool = False


class SignalingRequest(BaseModel):
    benefit: float = Field(ge=0.0)
    cost_high_type: float = Field(ge=0.0)
    cost_low_type: float = Field(ge=0.0)


class PrincipalAgentRequest(BaseModel):
    efforts: list[dict[str, Any]] = Field(min_length=1)
    target_effort: str
    shares: list[float] | None = None


@router.post("/meta/ergodicity")
def row60_ergodicity(request: ErgodicityRequest) -> dict[str, Any]:
    try:
        return get_service().ergodicity.analyze(
            outcomes=[(float(p), float(m)) for p, m in request.outcomes])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/nonlinear/classify")
def row61_nonlinear_classify(request: NonLinearRequest) -> dict[str, Any]:
    try:
        return get_service().nonlinear.classify(xs=request.xs, ys=request.ys)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/nonlinear/extrapolate")
def row61_nonlinear_extrapolate(request: NonLinearExtrapolateRequest) -> dict[str, Any]:
    try:
        value = get_service().nonlinear.extrapolate(
            model=request.model, slope=request.slope, intercept=request.intercept, x=request.x)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"model": request.model, "x": request.x, "extrapolated": value,
            "note": "The fitted form was used - no silent linear projection"}


@router.post("/meta/tipping-point")
def row62_tipping_point(request: TippingPointRequest) -> dict[str, Any]:
    try:
        return get_service().tipping_points.analyze(series=request.series,
                                                    threshold=request.threshold)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/network-effects")
def row63_network_effects(request: NetworkEffectRequest) -> dict[str, Any]:
    return get_service().network_effects.analyze(
        n_users=request.n_users, two_sided=request.two_sided, same_side=request.same_side)


@router.post("/meta/flywheels")
def row64_flywheels(request: SystemsModelRequest) -> dict[str, Any]:
    model = SystemsModel()
    for link in request.links:
        model.add_link(link.source, link.target, sign=link.sign, delay=link.delay)
    return get_service().flywheels.find(model)


@router.post("/meta/moats")
def row65_moats(request: MoatRequest) -> dict[str, Any]:
    try:
        return get_service().moats.assess(ratings=request.ratings)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/disruption")
def row66_disruption(request: DisruptionRequest) -> dict[str, Any]:
    return get_service().disruption.assess(
        entrant_improvement_rate=request.entrant_improvement_rate,
        incumbent_improvement_rate=request.incumbent_improvement_rate,
        entrant_targets_underserved=request.entrant_targets_underserved,
        entrant_cheaper=request.entrant_cheaper,
        incumbent_overserving=request.incumbent_overserving)


@router.post("/meta/jtbd")
def row67_jtbd(request: JTBDRequest) -> dict[str, Any]:
    return get_service().jtbd.frame(product=request.product, statements=request.statements)


@router.post("/meta/value-chain")
def row68_value_chain(request: ValueChainRequest) -> dict[str, Any]:
    try:
        return get_service().value_chain.map(stages=request.stages)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/pareto")
def row69_pareto(request: ParetoRequest) -> dict[str, Any]:
    try:
        return get_service().pareto.analyze(items=request.items,
                                            target_share=request.target_share)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/toc/observe")
def row70_toc(request: TOCRequest) -> dict[str, Any]:
    try:
        return get_service().toc.observe(stages=request.stages)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/queue")
def row71_queue(request: QueueRequest) -> dict[str, Any]:
    service = get_service()
    try:
        if request.servers == 1:
            return service.queues.mm1(arrival_rate=request.arrival_rate,
                                      service_rate=request.service_rate)
        return service.queues.mmc(arrival_rate=request.arrival_rate,
                                  service_rate=request.service_rate,
                                  servers=request.servers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/littles-law")
def row72_littles_law(request: LittlesLawRequest) -> dict[str, Any]:
    try:
        return get_service().littles.relate(wip=request.wip, throughput=request.throughput,
                                            cycle_time=request.cycle_time)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/critical-path")
def row73_critical_path(request: CriticalPathRequest) -> dict[str, Any]:
    try:
        return get_service().critical_paths.analyze(tasks=request.tasks)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/monte-carlo")
def row74_monte_carlo(request: MonteCarloRequest) -> dict[str, Any]:
    try:
        return get_service().monte_carlo.simulate(tasks=request.tasks,
                                                  trials=request.trials, seed=request.seed)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/sensitivity")
def row75_sensitivity(request: SensitivityRequest) -> dict[str, Any]:
    try:
        return get_service().sensitivity.analyze(expression=request.expression,
                                                 params=request.params, swing=request.swing)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/tornado")
def row76_tornado(request: SensitivityRequest) -> dict[str, Any]:
    try:
        return get_service().tornado.build(expression=request.expression,
                                           params=request.params, swing=request.swing)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/decision-tree")
def row77_decision_tree(request: DecisionTreeRequest) -> dict[str, Any]:
    try:
        return get_service().decision_trees.build(spec=request.spec)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/real-options")
def row78_real_options(request: RealOptionsRequest) -> dict[str, Any]:
    try:
        return get_service().real_options.value(
            underlying=request.underlying, up=request.up, down=request.down,
            exercise_cost=request.exercise_cost, kind=request.kind,
            steps=request.steps, risk_free=request.risk_free)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/game")
def row79_game(request: GameRequest) -> dict[str, Any]:
    try:
        return get_service().game_theory.analyze(row_payoffs=request.row_payoffs,
                                                 col_payoffs=request.col_payoffs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/nash")
def row80_nash(request: GameRequest) -> dict[str, Any]:
    try:
        return get_service().nash.find(row_payoffs=request.row_payoffs,
                                       col_payoffs=request.col_payoffs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/mechanism/vcg")
def row81_vcg(request: VCGRequest) -> dict[str, Any]:
    try:
        return get_service().mechanisms.vcg(agents=request.agents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/mechanism/check-incentives")
def row81_check_incentives(request: ICCheckRequest) -> dict[str, Any]:
    try:
        return get_service().mechanisms.check_incentives(
            agent=request.agent, true_values=request.true_values,
            others=request.others, deviations=request.deviations)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/auction")
def row82_auction(request: AuctionRequest) -> dict[str, Any]:
    try:
        return get_service().auctions.recommend(
            auction_type=request.auction_type, value=request.value,
            n_bidders=request.n_bidders, common_value=request.common_value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/signaling")
def row83_signaling(request: SignalingRequest) -> dict[str, Any]:
    try:
        return get_service().signaling.assess(benefit=request.benefit,
                                              cost_high_type=request.cost_high_type,
                                              cost_low_type=request.cost_low_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/meta/principal-agent")
def row84_principal_agent(request: PrincipalAgentRequest) -> dict[str, Any]:
    try:
        return get_service().principal_agent.design(efforts=request.efforts,
                                                    target_effort=request.target_effort,
                                                    shares=request.shares)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

# ------------------------------------------------ rows 1210-1259: legal workbench
from typing import Literal as _Literal
from .legal_support import PROFILES as _LEGAL_PROFILES, legal_support as _legal_support

class LegalSupportRequest(BaseModel):
    method: _Literal[
        'contract_drafting','contract_review','contract_negotiation','legal_research','case_law_analysis','statutory_interpretation','regulatory_compliance','legal_risk_assessment','due_diligence','mergers_acquisitions','corporate_governance','securities_law','intellectual_property','patent_drafting','patent_prosecution','trademark_registration','copyright_analysis','trade_secret_protection','licensing_agreements','technology_transfer','employment_law','labor_relations','discrimination_analysis','harassment_investigation','wrongful_termination','employment_contracts','non_compete_agreements','immigration_law','visa_applications','asylum_cases','refugee_law','family_law','divorce_proceedings','child_custody','adoption','estate_planning','wills_and_trusts','probate','real_estate_law','property_transactions','landlord_tenant','zoning_and_land_use','environmental_law','climate_regulation','pollution_control','natural_resources','energy_law','criminal_law','criminal_defense','prosecution_strategy'
    ]
    data: dict[str, Any] = Field(default_factory=dict)

@router.post('/legal/support')
def legal_support_route(request: LegalSupportRequest) -> dict[str, Any]:
    return {"module_id":20,"method":request.method,"result":_legal_support(request.method, request.data),
            "human_review_required":True}

# Specialized-domain education surface, rows 1410-1459.
from .education_routes import router as education_router
router.include_router(education_router)

# Specialized social-research surface, ledger rows 1710-1759.
from .social_research_routes_1710_1759 import router as social_research_router_1710_1759
router.include_router(social_research_router_1710_1759)

from .political_social_routes_1760_1809 import router as political_social_router_1760_1809
router.include_router(political_social_router_1760_1809)

# Mechanical engineering analysis rows 1510-1559.
from .engineering_routes_1510_1559 import router as engineering_router_1510_1559
router.include_router(engineering_router_1510_1559)

# Learning and reasoning workbench, owner-ledger rows 810-859.
from .learning_reasoning_routes_810_859 import router as learning_reasoning_router_810_859
router.include_router(learning_reasoning_router_810_859)

# Cognitive and reasoning methods rows 1960-2009.
from .cognitive_routes_1960_2009 import router as cognitive_router_1960_2009
router.include_router(cognitive_router_1960_2009)

# Humanities analysis rows 1810-1859.
from .humanities_routes_1810_1859 import router as humanities_router_1810_1859
router.include_router(humanities_router_1810_1859)

from .cognitive_learning_routes_860_909 import router as cognitive_learning_router_860_909
router.include_router(cognitive_learning_router_860_909)

# Distributed/platform engineering workbench, rows 585-634.
from .platform_engineering_routes_585_634 import router as platform_engineering_router_585_634
router.include_router(platform_engineering_router_585_634)

# Optimization and original-story workbench, owner-ledger rows 235-280.
from .optimization_story_routes_235_280 import router as optimization_story_router_235_280
router.include_router(optimization_story_router_235_280)
