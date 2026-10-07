"""GCW runtime: the durable, tenant-scoped sense-plan-act-evaluate loop
(rows M20-12..M20-16, M20-23..M20-28, M20-30).

GCWRuntime wires the durable stores, the deliberative loop, the fair
scheduler, the bounded MCTS ruminator, the tool selector and the sandbox
runner into one object the integrator binds per tenant. Every mutation
lands in the repository, so a restarted process rehydrates tasks, plans,
memories, methods, retrospectives and calibration history exactly.

The Evaluate phase can resolve explicit caller predictions against dispatcher
outcomes. It does not create a success prediction automatically or verify output
quality. Claim references in node arguments are caller/model-controlled metadata,
not authenticated prediction provenance. Candidate ranking is hand-written
heuristic scoring, not fitted expected information gain or success probability.
"""
from __future__ import annotations

import time
import hashlib
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .embeddings import EmbeddingProvider
from .executive import DeliberativeLoop, ExecutiveModel, MetaReasoner
from .htn_planner import HTNPlanner, PlannerModel
from .mcts import BoundedMCTS, MCTSResult
from .persistence import (
    DurableCalibrationEngine, DurableEpisodicMemory, DurableHTNPlanner,
    DurableRetrospectiveEngine, DurableSemanticMemory, DurableSkillLibrary,
    DurableWorkingMemory,
)
from .safety import ApprovalGate, InMemoryApprovalGate, SafetyGate, SandboxPolicy
from .sandbox import SandboxRunner
from .scheduler import FairContextScheduler
from .schemas import (
    Budget,
    ChunkType, EpisodeOutcome, MemoryChunk, PlanNode, TaskContext, TaskState, TraceEntry,
)
from .risk_register import DurableRiskRegister
from .sql_repository import GCWRepository
from .tool_selection import ToolSelection, ToolSelector
from .tools import ToolDispatcher, ToolRegistry


@dataclass
class AlternativeEvaluated:
    """One candidate next action with its typed score decomposition."""

    node_id: str
    title: str
    heuristic_information_weight: float
    cost: float
    heuristic_progress_weight: float
    score: float


@dataclass
class DecisionArtifact:
    """Private decision record (row M20-26): alternatives and the decision
    matrix. Deliberately carries no chain-of-thought field."""

    task_id: str
    chosen: AlternativeEvaluated | None
    alternatives: list[AlternativeEvaluated]
    decided_at: str
    basis: str = "hand-written information/progress weights minus supplied cost"

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "chosen": vars(self.chosen) if self.chosen else None,
            "alternatives": [vars(a) for a in self.alternatives],
            "decided_at": self.decided_at,
            "basis": self.basis,
            "status":"hand_written_candidate_ranking", "predictive_model_available":False,
        }


@dataclass
class StepReport:
    """Typed result of one scheduler quantum."""

    task_id: str | None
    state: str
    ticks_run: int
    elapsed_seconds: float
    surprises: list[str] = field(default_factory=list)
    budget_status: str = "cooperative_between_steps_only"
    hard_wall_time_enforced: bool = False
    tokens_money_enforced: bool = False


class GCWRuntime:
    """Durable executive runtime for one tenant."""

    def __init__(
        self,
        repo: GCWRepository,
        *,
        planner_model: PlannerModel | None = None,
        executive_model: ExecutiveModel | None = None,
        embedder: EmbeddingProvider | None = None,
        approval_gate: ApprovalGate | None = None,
        sandbox_policy: SandboxPolicy | None = None,
        require_method_review: bool = True,
        seed: int | None = None,
        _hydrate: bool = True,
    ) -> None:
        self.risk_registers = DurableRiskRegister(repo)
        self.repo = repo
        self.tenant_id = repo.tenant_id
        self.working_memory = (
            DurableWorkingMemory.load(repo) if _hydrate else DurableWorkingMemory(repo)
        )
        self.episodic = DurableEpisodicMemory.load(repo, embedder=embedder) if _hydrate else DurableEpisodicMemory(repo, embedder=embedder)
        self.semantic = DurableSemanticMemory.load(repo, embedder=embedder) if _hydrate else DurableSemanticMemory(repo, embedder=embedder)
        self.skills = DurableSkillLibrary.load(repo) if _hydrate else DurableSkillLibrary(repo)
        self.retrospectives = (
            DurableRetrospectiveEngine.load(repo, embedder=embedder)
            if _hydrate else DurableRetrospectiveEngine(repo, embedder=embedder)
        )
        self.calibration = (
            DurableCalibrationEngine.load(repo) if _hydrate else DurableCalibrationEngine(repo)
        )
        self.planner = DurableHTNPlanner.load(
            repo, model=planner_model, require_review=require_method_review,
        ) if _hydrate else DurableHTNPlanner(
            repo, model=planner_model, require_review=require_method_review,
        )
        self.tools = ToolRegistry()
        self.safety = SafetyGate(
            approvals=approval_gate or InMemoryApprovalGate(), sandbox=sandbox_policy,
        )
        self.dispatcher = ToolDispatcher(self.tools, self.safety)
        if _hydrate:
            self.dispatcher.records = repo.list_actions()
        self._persisted_actions = len(self.dispatcher.records)
        self.loop = DeliberativeLoop(
            planner=self.planner, dispatcher=self.dispatcher,
            working_memory=self.working_memory, episodic=self.episodic,
            semantic=self.semantic, skills=self.skills, model=executive_model,
            max_ticks=25,
        )
        self.scheduler = FairContextScheduler()
        self.selector = ToolSelector(self.tools, embedder=embedder)
        self.mcts = BoundedMCTS(seed=seed)
        owner_volume = hashlib.sha256(self.tenant_id.encode("utf-8")).hexdigest()
        self.sandbox = SandboxRunner(policy=sandbox_policy, workspace_root=os.path.join(
            tempfile.gettempdir(), "atlas-gcw-sandbox", owner_volume))
        self.meta = MetaReasoner()
        self.loop.before_run = self._register_expectations
        self._persisted_traces = 0
        if _hydrate:
            for context in repo.list_tasks():
                if repo.list_retrospectives(task_id=context.id):
                    continue
                if context.state in (TaskState.PENDING, TaskState.PLANNING,
                                     TaskState.RUNNING, TaskState.RUMINATING,
                                     TaskState.WAITING_APPROVAL):
                    self.scheduler.add(context)
            # Cursor indexes this process's new loop.traces, not SQL history.

    # -- lifecycle -----------------------------------------------------------

    def submit_goal(
        self,
        goal: str,
        *,
        importance: int = 3,
        deadline: datetime | None = None,
        run_immediately: bool = True,
    ) -> TaskContext:
        if not goal.strip():
            raise ValueError("goal must be non-empty")
        context = TaskContext(
            goal=goal, importance=max(1, min(5, importance)), deadline=deadline,
            tenant_id=self.tenant_id,
        )
        context.wm_partition = context.id
        self.scheduler.add(context)
        self.repo.save_task(context)
        if run_immediately:
            self._run_and_persist(context)
        else:
            # Plan without executing so decision artifacts and MCTS have a
            # real DAG to work on.
            from .htn_planner import PlanError

            try:
                context.plan = self.planner.decompose(context.goal)
                context.state = TaskState.PLANNING
            except PlanError:
                context.state = TaskState.PENDING
            self.repo.save_task(context)
        return context

    def get_task(self, task_id: str) -> TaskContext | None:
        context = self.scheduler.get(task_id)
        return context or self.repo.load_task(task_id)

    def list_tasks(self) -> list[TaskContext]:
        return self.repo.list_tasks()

    def step(self, *, quantum_seconds: float = 5.0, max_ticks: int = 10) -> StepReport:
        """One fair-scheduled quantum across contexts (rows M20-15, M20-24)."""
        started = time.monotonic()
        context = self.scheduler.next_context()
        if context is None:
            return StepReport(task_id=None, state="idle", ticks_run=0, elapsed_seconds=0.0)
        self.loop.max_ticks = max_ticks
        self.loop.last_ticks_run = 0
        budget = Budget(seconds=quantum_seconds)
        surprises = []
        if context.state in (TaskState.PENDING, TaskState.PLANNING, TaskState.RUNNING, TaskState.RUMINATING):
            surprises = self._run_and_persist(context, budget=budget, yield_on_boundary=True)
        elapsed = time.monotonic() - started
        return StepReport(
            task_id=context.id, state=context.state.value,
            ticks_run=self.loop.last_ticks_run,
            elapsed_seconds=round(elapsed, 4), surprises=surprises,
        )

    def run_task(self, task_id: str, *, max_ticks: int = 25, budget: Budget | None = None, yield_on_boundary: bool = False) -> TaskContext | None:
        context = self.get_task(task_id)
        if context is None:
            return None
        if self.repo.list_retrospectives(task_id=task_id):
            return context
        self.loop.max_ticks = max_ticks
        self._run_and_persist(context, budget=budget, yield_on_boundary=yield_on_boundary)
        return context

    def resume(self, task_id: str, node_id: str, *, approved: bool) -> TaskContext | None:
        context = self.get_task(task_id)
        if context is None:
            return None
        if self.repo.list_retrospectives(task_id=task_id):
            return context
        result = self.loop.resume_after_approval(context, node_id, approved)
        self._persist_context(context)
        self._evaluate_expectations(context)
        return result

    # -- evaluation depth ------------------------------------------------------

    def _run_and_persist(self, context: TaskContext, *, budget: Budget | None = None, yield_on_boundary: bool = False) -> list[str]:
        if context.state in (TaskState.PENDING, TaskState.PLANNING) and not context.plan:
            self.loop.start(context, budget=budget, yield_on_boundary=yield_on_boundary)
        else:
            if context.state == TaskState.PLANNING:
                context.state = TaskState.RUNNING
            self.loop.run(context, budget=budget, yield_on_boundary=yield_on_boundary)
        self._persist_context(context)
        return self._evaluate_expectations(context)

    def _persist_context(self, context: TaskContext) -> None:
        context.updated_at = datetime.now(timezone.utc)
        self.repo.save_task(context)
        for action in self.dispatcher.records[self._persisted_actions:]:
            self.repo.save_action(action)
            self._persisted_actions += 1
        new_traces = self.loop.traces[self._persisted_traces:]
        for trace in new_traces:
            self.repo.save_trace(trace)
            self._persisted_traces += 1

    def _register_expectations(self, context: TaskContext) -> None:
        """No fitted success predictor; heuristic weights are not probabilities."""
        return

    def _evaluate_expectations(self, context: TaskContext) -> list[str]:
        """Resolve expectation claims against observed outcomes; a large miss
        is a surprise that triggers reflection and replanning (row M20-14)."""
        surprises: list[str] = []
        for node in context.plan:
            claim_id = node.arguments.get("_expectation_claim_id")
            if claim_id is None or node.state not in (TaskState.SUCCEEDED, TaskState.FAILED):
                continue
            node.arguments.pop("_expectation_claim_id", None)
            claim = self.calibration.claims.get(claim_id)
            if claim is None or claim.resolved:
                continue
            observed = node.state == TaskState.SUCCEEDED
            self.calibration.resolve(claim_id, observed)
            miss = abs(claim.confidence - (1.0 if observed else 0.0))
            if miss >= 0.5:
                surprises.append(node.title)
                self.working_memory.put(MemoryChunk(
                    type=ChunkType.QUESTION,
                    content=(f"surprise on step {node.title!r}: predicted "
                             f"{claim.confidence:.2f}, observed "
                             f"{'success' if observed else 'failure'}"),
                    confidence=1.0, source="surprise-reflection",
                ), active_goal=context.goal, partition=context.id)
                trace = TraceEntry(
                    task_id=context.id, phase="reflect",
                    detail=f"surprise-triggered reflection on {node.title!r}; replanning advised",
                    policy_basis="spec 4.2.4 surprise reflection",
                )
                self.loop.traces.append(trace)
        self._persist_context(context)
        return surprises

    # -- decision artifact (row M20-26) ----------------------------------------

    def decision_artifact(self, task_id: str) -> DecisionArtifact | None:
        context = self.get_task(task_id)
        if context is None:
            return None
        ready = HTNPlanner.ready_nodes(context.plan)
        wm_context = self.working_memory.context(partition=context.id)
        ltm_hits = len(self.semantic.query(context.goal, limit=3))
        candidates = self.meta.score_candidates(ready, wm_context=wm_context, ltm_hits=ltm_hits)
        alternatives = [
            AlternativeEvaluated(
                node_id=c.node.id, title=c.node.title,
                heuristic_information_weight=round(c.heuristic_information_weight, 4),
                cost=c.cost,
                heuristic_progress_weight=round(c.heuristic_progress_weight, 4),
                score=round(c.score, 4),
            )
            for c in candidates
        ]
        return DecisionArtifact(
            task_id=task_id,
            chosen=alternatives[0] if alternatives else None,
            alternatives=alternatives,
            decided_at=datetime.now(timezone.utc).isoformat(),
        )

    # -- search, selection, sandbox --------------------------------------------

    def run_mcts(self, task_id: str, **kwargs) -> MCTSResult | None:
        context = self.get_task(task_id)
        if context is None:
            return None
        if kwargs:
            self.mcts = BoundedMCTS(**kwargs)
        return self.mcts.search(context.plan)

    def select_tool(self, description: str, *, context: dict[str, Any] | None = None) -> ToolSelection:
        return self.selector.select(description, context=context)

    # -- retrospective and close (row M20-28) -----------------------------------

    def close(self, task_id: str) -> dict[str, Any] | None:
        """Auto-retrospective from the trace record, calibration resolution,
        partition cleanup. Idempotent: closing twice returns the stored retro."""
        context = self.get_task(task_id)
        if context is None:
            return None
        existing = self.repo.list_retrospectives(task_id=task_id)
        if existing:
            return {"retrospective": existing[0].model_dump(mode="json"), "idempotent": True}
        self._persist_context(context)
        traces = self.repo.list_traces(task_id=task_id)
        failures = [t for t in traces if "failed" in t.detail or "error" in t.detail]
        blocked = [t for t in traces if "blocked" in t.detail or "gated" in t.detail]
        succeeded_steps = [n for n in context.plan if n.state == TaskState.SUCCEEDED]
        went_well = [f"completed step: {n.title}" for n in succeeded_steps] or ["goal accepted"]
        went_poorly = [t.detail[:160] for t in failures] or []
        lessons: list[str] = []
        if failures:
            lessons.append("investigate failing tools before re-planning the same step shape")
        if blocked:
            lessons.append("surface approval-gated steps earlier so the human is never the bottleneck")
        if context.state == TaskState.SUCCEEDED:
            lessons.append(f"plan of {len(context.plan)} steps completed; method reusable")
        for node in context.plan:
            claim_id = node.arguments.pop("_expectation_claim_id", None)
            if claim_id and claim_id in self.calibration.claims:
                self.calibration.resolve(claim_id, node.state == TaskState.SUCCEEDED)
        retro = self.retrospectives.write(
            task_id, went_well=went_well, went_poorly=went_poorly, lessons=lessons,
        )
        if context.state in (TaskState.PENDING, TaskState.PLANNING, TaskState.RUNNING,
                              TaskState.RUMINATING, TaskState.WAITING_APPROVAL, TaskState.WAITING_USER):
            context.state = TaskState.CANCELLED
            for node in context.plan:
                if node.state not in (TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED):
                    node.state = TaskState.CANCELLED
                    node.approval_id = None
        self.working_memory.clear_partition(task_id)
        self.scheduler.remove(task_id)
        self._persist_context(context)
        return {"retrospective": retro.model_dump(mode="json"), "idempotent": False}
