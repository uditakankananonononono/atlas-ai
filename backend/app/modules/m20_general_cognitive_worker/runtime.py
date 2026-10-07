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
    ChunkType, EpisodeOutcome, MemoryChunk, PlanNode, Risk, TaskContext, TaskState, TraceEntry,
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
        from .local_tools import register_local_tools
        register_local_tools(self.tools)
        self.safety = SafetyGate(
            approvals=approval_gate or InMemoryApprovalGate(), sandbox=sandbox_policy,
        )
        self.dispatcher = ToolDispatcher(self.tools, self.safety)
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
        self.loop.action_history = lambda task_id: self.repo.list_actions(task_id=task_id)
        self.loop.before_run = self._register_expectations
        self.loop.before_plan = self._retrieve_review_lessons
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
                self._retrieve_review_lessons(context)
                context.plan = self.planner.decompose(context.goal, context=self.working_memory.context(partition=context.id))
                context.state = TaskState.PLANNING
            except PlanError:
                context.state = TaskState.PENDING
            self.repo.save_task(context)
        return context

    def get_task(self, task_id: str) -> TaskContext | None:
        context = self.scheduler.get(task_id)
        return context or self.repo.load_task(task_id)

    def supervision(self):
        tasks = self.repo.list_tasks()
        states = {}; attention = []
        for task in tasks:
            states[task.state.value] = states.get(task.state.value, 0) + 1
            if task.state in (TaskState.FAILED, TaskState.BLOCKED, TaskState.WAITING_APPROVAL, TaskState.WAITING_USER):
                attention.append({'task_id': task.id, 'goal': task.goal, 'state': task.state.value,
                    'steps': [{'step_id': node.id, 'title': node.title, 'tool': node.tool,
                               'state': node.state.value, 'attempts': node.attempts,
                               'approval_id': node.approval_id, 'result_summary': node.result_summary}
                              for node in task.plan if node.state != TaskState.SUCCEEDED]})
        return {'healthy': None, 'task_count': len(tasks), 'tasks_by_state': states,
                'attention_required': attention, **self.repo.action_summary(),
                'external_outcomes_verified': False, 'status': 'durable_local_work_state_review',
                'boundary': 'Persisted local work-state review only; no production health, liveness or externally verified outcome inference.'}

    def preflight_task(self, task_id, *, context=None):
        from .tools import ToolError, ToolBlockedError
        task = self.get_task(task_id)
        if task is None: raise KeyError(task_id)
        context = context or {}
        rows = []
        def bindings(value):
            if isinstance(value, dict):
                return '$step' in value or any(bindings(item) for item in value.values())
            return isinstance(value, list) and any(bindings(item) for item in value)
        for node in task.plan:
            row = {'step_id': node.id, 'tool': node.tool, 'issues': [], 'missing_preconditions': [],
                   'argument_check': 'not_applicable', 'effective_risk': node.risk.value}
            if node.tool is None:
                if self.loop.model is None: row['issues'].append('reasoning_model_unavailable')
            else:
                try: tool = self.tools.get(node.tool)
                except ToolError:
                    row['issues'].append('unknown_tool'); rows.append(row); continue
                tiers = [Risk.READ, Risk.REVERSIBLE, Risk.EXTERNAL, Risk.IRREVERSIBLE]
                row['effective_risk'] = tiers[max(tiers.index(tool.spec.risk), tiers.index(node.risk))].value
                row['missing_preconditions'] = tool.check_preconditions(context)
                if row['missing_preconditions']: row['issues'].append('missing_preconditions')
                if bindings(node.arguments):
                    row['argument_check'] = 'deferred_until_dependency_output'
                    row['issues'].append('argument_binding_unresolved')
                else:
                    try:
                        tool.validate_arguments(node.arguments)
                        row['argument_check'] = 'static_schema_valid'
                    except ToolBlockedError:
                        row['argument_check'] = 'static_schema_invalid'
                        row['issues'].append('arguments_schema')
            rows.append(row)
        return {'task_id': task_id, 'steps': rows,
                'ready_for_dispatch': False,
                'static_checks_passed': bool(rows) and not any(row['issues'] for row in rows),
                'status': 'registered_capability_and_static_input_diagnostics_only',
                'approval_granted': False, 'external_actions_executed': False,
                'context_is_supplied_not_verified': True,
                'dispatch_rechecks_required': True}

    def prepare_supplied_plan(self, task_id, *, steps):
        from .htn_planner import HTNPlanner
        context = self.get_task(task_id)
        if context is None: raise KeyError(task_id)
        if (self.repo.list_retrospectives(task_id=task_id) or context.plan
                or self.repo.list_actions(task_id=task_id)
                or context.state not in (TaskState.PENDING, TaskState.PLANNING, TaskState.BLOCKED)):
            raise ValueError('plan conflict; only empty unexecuted tasks accept supplied plans')
        nodes = HTNPlanner()._validate(steps)
        for node in nodes:
            node.state = TaskState.PENDING
            node.attempts = 0
            node.approval_id = None
            node.result_summary = ''
            node.output = None
        updated = context.model_copy(deep=True)
        updated.plan = nodes
        updated.state = TaskState.PLANNING
        self.repo.save_task(updated)
        self.scheduler.add(updated)
        self.loop._trace('plan', 'supplied DAG prepared only; not executed or approved', task_id=task_id)
        self._persist_context(updated)
        return updated

    def update_task_schedule(self, task_id, *, changes):
        if not isinstance(changes, dict) or not changes or not set(changes) <= {'importance', 'deadline'}:
            raise ValueError('nonempty importance/deadline changes required')
        context = self.get_task(task_id)
        if context is None: raise KeyError(task_id)
        if self.repo.list_retrospectives(task_id=task_id):
            raise ValueError('schedule conflict; task is closed')
        updated = context.model_copy(deep=True)
        if 'importance' in changes:
            importance = changes['importance']
            if type(importance) is not int or not 1 <= importance <= 5:
                raise ValueError('importance must be exact integer1..5')
            updated.importance = importance
        if 'deadline' in changes:
            deadline = changes['deadline']
            if deadline is not None and (not isinstance(deadline, datetime) or deadline.tzinfo is None or deadline.utcoffset() is None):
                raise ValueError('deadline must be timezone-aware or null')
            updated.deadline = deadline.astimezone(timezone.utc) if deadline is not None else None
        updated.updated_at = datetime.now(timezone.utc)
        self.repo.save_task(updated)
        if self.scheduler.get(task_id) is not None:
            self.scheduler.add(updated)
        return updated

    def add_task_context(self, task_id, *, text, source, reference):
        context = self.get_task(task_id)
        if context is None: raise KeyError(task_id)
        if self.repo.list_retrospectives(task_id=task_id):
            raise ValueError('context conflict; task is closed')
        for value, limit in ((text, 4000), (source, 200), (reference, 200)):
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError('bounded nonempty text/source/reference required')
        import json
        identity = hashlib.sha256(json.dumps([self.tenant_id, task_id, source, reference]).encode()).hexdigest()
        content = f"unverified supplied context [source {source}; reference {reference}]: {text}"
        previous = self.working_memory.get(identity)
        if previous is not None:
            if previous.content != content:
                raise ValueError('context conflict; reference already has different content')
            return {'chunk_id': identity, 'inserted': False, 'source_verified': False}
        self.working_memory.put(MemoryChunk(id=identity, type=ChunkType.HYPOTHESIS,
            content=content, confidence=0.0, source='supplied_task_context'),
            active_goal=context.goal, partition=task_id)
        return {'chunk_id': identity, 'inserted': self.working_memory.get(identity) is not None,
                'source_verified': False, 'replay_scope': 'retained_working_memory_only'}

    def task_evidence(self, task_id, *, limit=50):
        if self.repo.load_task(task_id) is None: raise KeyError(task_id)
        return self.repo.task_evidence(task_id, limit=limit)

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
        try:
            for action in self.dispatcher.records[self._persisted_actions:]:
                self.repo.save_action(action)
                self._persisted_actions += 1
        finally:
            if self._persisted_actions:
                del self.dispatcher.records[:self._persisted_actions]
                self._persisted_actions = 0
        new_traces = self.loop.traces[self._persisted_traces:]
        for trace in new_traces:
            self.repo.save_trace(trace)
            self._persisted_traces += 1

    def _retrieve_review_lessons(self, context: TaskContext) -> None:
        """Bounded review suggestions, never facts or authorization for effects."""
        existing = {chunk.content for chunk in self.working_memory.focused(partition=context.id)
                    if chunk.source == 'retrospective_retrieval'}
        for retro, similarity in self.retrospectives.lessons_for(context.goal, limit=3):
            if retro.task_id == context.id or similarity <= 0:
                continue
            for lesson in retro.lessons[:3]:
                content = f"unverified review suggestion [retrospective {retro.id}]: {lesson[:1000]}"
                if content in existing: continue
                self.working_memory.put(MemoryChunk(
                    type=ChunkType.HYPOTHESIS, content=content, confidence=0.0,
                    source='retrospective_retrieval'), active_goal=context.goal, partition=context.id)
                existing.add(content)

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
        self.selector.use_dispatch_counts(self.repo.dispatch_outcome_counts())
        selection = self.selector.select(description, context=context)
        selection.history_status = "reported_local_dispatch_journal_with_beta_1_1_prior"
        selection.runtime_dispatch_history_connected = True
        return selection

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
        went_well = [f"completed step: {n.title}" for n in succeeded_steps]
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
        if context.state in (TaskState.PENDING, TaskState.PLANNING, TaskState.RUNNING,
                              TaskState.RUMINATING, TaskState.WAITING_APPROVAL, TaskState.WAITING_USER):
            context.state = TaskState.CANCELLED
            for node in context.plan:
                if node.state not in (TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED):
                    node.state = TaskState.CANCELLED
                    node.approval_id = None
        actions = self.repo.list_actions(task_id=task_id)
        tools = {}
        for action in actions:
            entry = tools.setdefault(action.tool, {
                "success_count": 0, "failure_count": 0,
                "succeeded_action_ids": [], "failed_action_ids": [], "last_failure": None,
            })
            if action.succeeded:
                entry["success_count"] += 1
                entry["succeeded_action_ids"].append(action.id)
            else:
                entry["failure_count"] += 1
                entry["failed_action_ids"].append(action.id)
                entry["last_failure"] = action.result_summary
                diagnostic = f"local tool {action.tool} failed ({action.id}): {action.result_summary}"
                if diagnostic not in went_poorly:
                    went_poorly.append(diagnostic)
        if any(not action.succeeded for action in actions) and not failures:
            lessons.append("investigate failing tools before re-planning the same step shape")
        report = {
            "status": "persisted_reported_local_execution_summary",
            "external_outcomes_verified": False,
            "final_task_state": context.state.value,
            "local_action_count": len(actions),
            "local_success_count": sum(action.succeeded for action in actions),
            "local_failure_count": sum(not action.succeeded for action in actions),
            "tools": tools,
            "step_states": {state.value: sum(node.state == state for node in context.plan)
                            for state in TaskState if any(node.state == state for node in context.plan)},
        }
        retro = self.retrospectives.write(
            task_id, went_well=went_well, went_poorly=went_poorly, lessons=lessons,
            execution_report=report,
        )
        self.working_memory.clear_partition(task_id)
        self.scheduler.remove(task_id)
        self._persist_context(context)
        return {"retrospective": retro.model_dump(mode="json"), "idempotent": False}
