"""Executive / deliberative reasoning (spec 4.2.4).

The executive runs the sense-plan-act loop:
  Observe: gather working memory + long-term memory context.
  Orient: the model analyses state, updates beliefs, finds knowledge gaps,
          and forms sub-goals (working-memory chunks).
  Decide: the meta-reasoner scores candidate next actions by expected
          information gain, estimated cost, and probability of progress.
  Act: ready plan steps dispatch through the tool layer (safety-gated).
  Evaluate: results are compared with expectations; surprise triggers a
          reflection phase that updates the world model and replans.

When idle, the executive ruminates: Monte Carlo tree search over the mental
space of remaining steps, exploring alternative solution paths.

Everything the executive thinks lands in a transparent TraceEntry stream.
"""
from __future__ import annotations

import math
import copy
import random
from time import monotonic
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .episodic_memory import EpisodicMemory
from .htn_planner import HTNPlanner, PlanError
from .schemas import (
    ActionRecord, Budget, ChunkType, EpisodeOutcome, MemoryChunk, PlanNode,
    Risk, TaskContext, TaskState, TraceEntry,
)
from .semantic_memory import SemanticMemory
from .skill_library import SkillLibrary
from .tools import ApprovalPending, ToolBlockedError, ToolDispatcher
from .working_memory import WorkingMemory


@runtime_checkable
class ExecutiveModel(Protocol):
    """LLM behind the loop. `purpose` selects the prompt family; payload
    carries the assembled context. Returns a dict the loop interprets."""

    def complete(self, purpose: str, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class CandidateAction:
    node: PlanNode
    heuristic_information_weight: float
    cost: float
    heuristic_progress_weight: float

    @property
    def score(self) -> float:
        if self.cost <= 0:
            return 0.0
        return (0.5 * self.heuristic_information_weight + 0.5 * self.heuristic_progress_weight) / self.cost


RISK_COST = {Risk.READ: 1.0, Risk.REVERSIBLE: 2.0, Risk.EXTERNAL: 4.0, Risk.IRREVERSIBLE: 8.0}


class MetaReasoner:
    """Decision-tree leaf selection (spec 4.2.4 Decide)."""

    def score_candidates(
        self, ready: list[PlanNode], *, wm_context: str, ltm_hits: int,
    ) -> list[CandidateAction]:
        candidates: list[CandidateAction] = []
        for node in ready:
            info_gain = 0.5
            if node.tool in ("web_search", "reader", "search") or node.kind == "research":
                info_gain = 0.9
            if node.title.lower() in wm_context.lower():
                info_gain *= 0.5
            progress = 0.5 + 0.1 * min(ltm_hits, 3) - 0.1 * node.attempts
            candidates.append(CandidateAction(
                node=node,
                heuristic_information_weight=max(0.0, min(1.0, info_gain)),
                cost=RISK_COST.get(node.risk, 1.0),
                heuristic_progress_weight=max(0.05, min(0.95, progress)),
            ))
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates


class MCTSRuminator:
    """Idle-time Monte Carlo exploration of remaining plan orderings.

    Each simulation orders the pending steps randomly (respecting
    dependencies) and scores the ordering by aggregate risk-adjusted success
    probability, so the executive can surface the most robust next ordering.
    """

    def __init__(self, simulations: int = 32, seed: int | None = None) -> None:
        if type(simulations) is not int or not 1 <= simulations <= 10000:
            raise ValueError("simulations must be integer1..10000")
        self.simulations = simulations
        self.random = random.Random(seed)

    def _orderings(self, plan: list[PlanNode]) -> list[list[PlanNode]]:
        pending = [n for n in plan if n.state == TaskState.PENDING]
        done = {n.id for n in plan if n.state == TaskState.SUCCEEDED}
        ordering: list[PlanNode] = []
        pool = pending[:]
        while pool:
            ready = [n for n in pool if all(d in done or d in {x.id for x in ordering} for d in n.depends_on)]
            if not ready:
                break
            choice = self.random.choice(ready)
            ordering.append(choice)
            pool.remove(choice)
        return ordering

    def ruminate(self, plan: list[PlanNode]) -> dict[str, Any]:
        if not any(n.state == TaskState.PENDING for n in plan):
            return {"simulations": 0, "best_ordering": [], "expected_success": None, "status":"random_ordering_heuristic_only", "predictive_model_available":False}
        best_order: list[str] = []
        best_score = -math.inf
        attempts = 0
        for _ in range(self.simulations):
            attempts += 1
            ordering = self._orderings(plan)
            if not ordering:
                break
            log_prob = 0.0
            risk_penalty = 0.0
            for node in ordering:
                p = max(0.05, 0.9 - 0.1 * node.attempts)
                log_prob += math.log(p)
                risk_penalty += RISK_COST.get(node.risk, 1.0)
            score = log_prob - 0.05 * risk_penalty
            if score > best_score:
                best_score = score
                best_order = [n.title for n in ordering]
        expected = math.exp(best_score) if best_order else None
        return {
            "simulations": attempts,
            "best_ordering": best_order,
            "expected_success": None, "heuristic_order_score": round(expected, 4) if expected is not None else None,
            "status":"random_ordering_heuristic_only", "predictive_model_available":False,
        }


class DeliberativeLoop:
    """The executive's sense-plan-act loop over one task context."""

    def __init__(
        self,
        planner: HTNPlanner,
        dispatcher: ToolDispatcher,
        working_memory: WorkingMemory,
        episodic: EpisodicMemory,
        semantic: SemanticMemory,
        skills: SkillLibrary,
        model: ExecutiveModel | None = None,
        ruminator: MCTSRuminator | None = None,
        max_ticks: int = 50,
    ) -> None:
        self.planner = planner
        self.dispatcher = dispatcher
        self.wm = working_memory
        self.episodic = episodic
        self.semantic = semantic
        self.skills = skills
        self.model = model
        self.ruminator = ruminator or MCTSRuminator(seed=7)
        self.max_ticks = max_ticks
        self.meta = MetaReasoner()
        self.traces: list[TraceEntry] = []
        # Optional hook invoked after planning and before each run, so the
        # durable runtime can register pre-dispatch expectations.
        self.before_run: Any = None
        self.before_plan: Any = None
        self.action_history: Any = None
        self.before_model: Any = None

    def _trace(self, phase: str, detail: str, *, task_id: str | None = None, policy_basis: str = "") -> None:
        self.traces.append(TraceEntry(task_id=task_id, phase=phase, detail=detail, policy_basis=policy_basis))

    @staticmethod
    def has_unknown(context):
        return context.model_outcome_unknown or any(n.outcome_unknown for n in context.plan)

    def _hold_unknown(self, context):
        if not self.has_unknown(context): return False
        context.state = TaskState.BLOCKED
        for node in context.plan:
            if node.outcome_unknown: node.state = TaskState.BLOCKED
        self._trace("act", "unresolved outcome unknown; execution held pending verified reconciliation", task_id=context.id)
        return True

    def start(self, context: TaskContext, *, budget: Budget | None = None, yield_on_boundary: bool = False) -> TaskContext:
        """Plan the goal, seed working memory, and run the loop."""
        self.execution_context = context
        if self._hold_unknown(context): return context
        # start is a fresh execution, not a resume. Incoming states are not
        # execution evidence. Continuations must use run/resume.
        for node in context.plan:
            node.state = TaskState.PENDING
            node.attempts = 0
            node.approval_id = None
            node.result_summary = ""
            node.output = None
        self._trace("observe", f"goal accepted: {context.goal}", task_id=context.id)
        analogies = self.episodic.recall_similar(context.goal, limit=3)
        for episode, score in analogies:
            self.wm.put(MemoryChunk(
                type=ChunkType.HYPOTHESIS,
                content=f"similar past episode: {episode.goal} (outcome={episode.outcome.value})",
                confidence=min(1.0, score), source="episodic_memory",
            ), active_goal=context.goal, partition=context.id)
        related = self.semantic.query(context.goal, limit=5)
        for fact, score in related:
            self.wm.put(MemoryChunk(
                type=ChunkType.FACT, content=fact.content,
                confidence=fact.confidence, source="semantic_memory",
            ), active_goal=context.goal, partition=context.id)
        context.state = TaskState.PLANNING
        if not context.plan:
            if self.before_plan is not None:
                self.before_plan(context)
            try:
                if self.before_model is not None: self.before_model(context)
                context.plan = self.planner.decompose(
                    context.goal, context=self.wm.context(partition=context.id),
                    proposer_actor_id=context.creator_actor_id,
                )
                self._trace("plan", f"plan with {len(context.plan)} steps", task_id=context.id)
            except PlanError as exc:
                context.model_outcome_unknown = getattr(exc, "outcome", None) == "unknown"
                context.state = TaskState.BLOCKED
                self._trace("plan", f"planning failed: {exc}", task_id=context.id)
                return context
        self.wm.put(MemoryChunk(
            type=ChunkType.GOAL, content=context.goal, confidence=1.0, source="executive",
        ), active_goal=context.goal, partition=context.id)
        if self.before_run is not None:
            self.before_run(context)
        return self.run(context, budget=budget, yield_on_boundary=yield_on_boundary)

    def _resolved_arguments(self, context, node):
        predecessors = {n.id: n for n in context.plan if n.id in node.depends_on}
        def resolve(value, depth=0):
            if depth > 32: raise ToolBlockedError(node.tool, ['argument binding depth exceeds32'])
            if isinstance(value, dict):
                if '$step' in value:
                    if set(value) != {'$step', 'path'} or not isinstance(value['$step'], str) or not isinstance(value['path'], list):
                        raise ToolBlockedError(node.tool, ['invalid step output reference'])
                    prior = predecessors.get(value['$step'])
                    if prior is None or prior.state != TaskState.SUCCEEDED or prior.output is None:
                        raise ToolBlockedError(node.tool, ['reference requires successful direct dependency with structured output'])
                    output = prior.output
                    for part in value['path']:
                        if isinstance(output, dict) and isinstance(part, str) and part in output:
                            output = output[part]
                        elif isinstance(output, list) and type(part) is int and 0 <= part < len(output):
                            output = output[part]
                        else: raise ToolBlockedError(node.tool, ['step output reference path not found'])
                    return copy.deepcopy(output)
                return {k: resolve(v, depth+1) for k, v in value.items()}
            if isinstance(value, list): return [resolve(v, depth+1) for v in value]
            return copy.deepcopy(value)
        return resolve(node.arguments)

    def run(self, context: TaskContext, *, budget: Budget | None = None, yield_on_boundary: bool = False) -> TaskContext:
        self.execution_context = context
        if self._hold_unknown(context): return context
        budget = budget or Budget()
        if self.before_run is not None:
            self.before_run(context)
        ticks = 0
        self.last_ticks_run = 0
        started = monotonic()
        context.state = TaskState.RUNNING
        while ticks < self.max_ticks and monotonic() - started < budget.seconds:
            ticks += 1
            self.last_ticks_run = ticks
            if HTNPlanner.is_complete(context.plan):
                if not context.plan or all(n.state == TaskState.CANCELLED for n in context.plan):
                    context.state = TaskState.BLOCKED
                    self._trace("evaluate", "no executed steps; cancelled/empty plan is not success", task_id=context.id)
                    return context
                context.state = TaskState.SUCCEEDED
                self._trace("evaluate", "plan complete", task_id=context.id)
                self._close_episode(context, EpisodeOutcome.SUCCEEDED)
                return context
            if HTNPlanner.is_deadlocked(context.plan):
                context.state = TaskState.FAILED
                self._trace("evaluate", "plan deadlocked", task_id=context.id)
                self._close_episode(context, EpisodeOutcome.FAILED)
                return context
            ready = HTNPlanner.ready_nodes(context.plan)
            if not ready:
                waiting = [n for n in context.plan if n.state == TaskState.WAITING_APPROVAL]
                if waiting:
                    context.state = TaskState.WAITING_APPROVAL
                    self._trace("act", "paused on human approval", task_id=context.id,
                                policy_basis="spec 4.4 approval gating")
                    return context
                break
            wm_context = self.wm.context(partition=context.id)
            ltm_hits = len(self.semantic.query(context.goal, limit=3))
            candidates = self.meta.score_candidates(ready, wm_context=wm_context, ltm_hits=ltm_hits)
            if not candidates:
                break
            chosen = candidates[0]
            self._trace("decide", f"next action: {chosen.node.title} (score={chosen.score:.3f})",
                        task_id=context.id)
            node = chosen.node
            node.attempts += 1
            node.state = TaskState.RUNNING
            if node.tool is None:
                result = None
                if self.model is not None:
                    try:
                        if self.before_model is not None: self.before_model(context)
                        response = self.model.complete("reason", {"goal": context.goal,
                            "step": node.title, "arguments": node.arguments, "context": wm_context})
                        if isinstance(response, dict) and response.get("outcome") == "unknown":
                            context.model_outcome_unknown = True
                            node.state = TaskState.BLOCKED
                            node.result_summary = "reasoning generation outcome unknown; no automatic retry"
                            self._hold_unknown(context)
                            return context
                        if isinstance(response, dict) and response.get("available") is not False:
                            candidate = response.get("result")
                            if isinstance(candidate, str) and candidate.strip():
                                result = candidate
                    except Exception as exc:
                        if getattr(exc, "persistence_checkpoint_failed", False): raise
                        if getattr(exc, "outcome", None) == "unknown":
                            context.model_outcome_unknown = True
                            self._hold_unknown(context)
                            return context
                        self._trace("act", f"reasoning model error: {type(exc).__name__}", task_id=context.id)
                if result is None:
                    node.state = TaskState.BLOCKED
                    node.result_summary = "reasoning executor unavailable or returned no result; step not executed"
                    context.state = TaskState.BLOCKED
                    self._trace("act", node.result_summary, task_id=context.id)
                    return context
                node.state = TaskState.SUCCEEDED
                node.result_summary = result
                self._trace("act", f"model returned reasoning output: {node.title}; correctness unverified", task_id=context.id)
                continue
            try:
                import asyncio
                record = _run_async(self.dispatcher.dispatch(
                    node.tool, self._resolved_arguments(context, node), task_id=context.id,
                    granted_approval_id=node.approval_id, risk_floor=node.risk,
                ))
                if record.outcome_unknown:
                    node.outcome_unknown = True
                    node.output = None
                    node.result_summary = record.result_summary
                    self._hold_unknown(context)
                    return context
                if record.succeeded:
                    node.state = TaskState.SUCCEEDED
                    node.approval_id = None
                    node.result_summary = record.result_summary
                    node.output = copy.deepcopy(record.result)
                    self._trace("act", f"{node.tool} succeeded", task_id=context.id)
                    self._evaluate_expectation(context, node, record)
                else:
                    node.result_summary = record.result_summary
                    node.output = None
                    node.state = TaskState.FAILED if node.attempts >= node.max_attempts else TaskState.PENDING
                    self._trace("evaluate", f"{node.tool} failed: {record.result_summary}",
                                task_id=context.id)
                    self._reflect_on_failure(context, node, record.result_summary)
                    if self._hold_unknown(context): return context
            except ApprovalPending as pending:
                node.state = TaskState.WAITING_APPROVAL
                node.approval_id = pending.approval_id
                context.state = TaskState.WAITING_APPROVAL
                self._trace("act", f"{node.tool} gated: approval {pending.approval_id}",
                            task_id=context.id, policy_basis="spec 4.4 approval gating")
                return context
            except ToolBlockedError as blocked:
                node.result_summary = "blocked: " + "; ".join(blocked.reasons)
                node.output = None
                node.state = TaskState.BLOCKED
                context.state = TaskState.BLOCKED
                self._trace("act", f"{node.tool} blocked: {'; '.join(blocked.reasons)}",
                            task_id=context.id, policy_basis="constitutional rules")
                self._close_episode(context, EpisodeOutcome.ABANDONED)
                return context
            except Exception as exc:
                if getattr(exc, "persistence_checkpoint_failed", False): raise
                node.result_summary = str(exc)[:2000]
                node.output = None
                node.state = TaskState.FAILED if node.attempts >= node.max_attempts else TaskState.PENDING
                self._trace("evaluate", f"{node.tool} error: {exc}", task_id=context.id)
                self._reflect_on_failure(context, node, str(exc))
                if self._hold_unknown(context): return context
        if self._hold_unknown(context): return context
        if yield_on_boundary:
            if context.plan and HTNPlanner.is_complete(context.plan) and any(n.state == TaskState.SUCCEEDED for n in context.plan):
                context.state = TaskState.SUCCEEDED
                self._trace("evaluate", "plan complete at scheduler boundary", task_id=context.id)
                self._close_episode(context, EpisodeOutcome.SUCCEEDED)
            elif HTNPlanner.is_deadlocked(context.plan):
                context.state = TaskState.FAILED
                self._trace("evaluate", "plan deadlocked at scheduler boundary", task_id=context.id)
                self._close_episode(context, EpisodeOutcome.FAILED)
            else:
                context.state = TaskState.RUNNING
                self._trace("evaluate", "cooperative scheduler quantum yielded; work remains", task_id=context.id)
            return context
        context.state = TaskState.FAILED
        self._trace("evaluate", "cooperative time/tick boundary reached; tokens/money not enforced", task_id=context.id)
        self._close_episode(context, EpisodeOutcome.FAILED)
        return context

    def resume_after_approval(self, context: TaskContext, node_id: str, approved: bool) -> TaskContext:
        if type(approved) is not bool:
            raise ValueError("approved must be exact bool")
        if self._hold_unknown(context): return context
        node = next((node for node in context.plan if node.id == node_id), None)
        if node is None:
            raise KeyError(node_id)
        if node.state != TaskState.WAITING_APPROVAL or not node.approval_id:
            raise ValueError("node is not waiting on an approval")
        if approved:
            node.state = TaskState.PENDING  # bound approval consumed at dispatch
        else:
            node.state = TaskState.BLOCKED
            node.approval_id = None
        if approved:
            return self.run(context)
        context.state = TaskState.BLOCKED
        self._trace("act", "approval rejected; task blocked", task_id=context.id,
                    policy_basis="spec 4.4 approval gating")
        return context

    def ruminate(self, context: TaskContext) -> dict[str, Any]:
        """Idle-cycle background thinking (spec 4.2.4 rumination)."""
        previous_state = context.state
        context.state = TaskState.RUMINATING
        try:
            result = self.ruminator.ruminate(context.plan)
            self._trace("ruminate", f"heuristic ordering: {result['best_ordering']}", task_id=context.id)
            return result
        finally:
            context.state = previous_state

    def _evaluate_expectation(self, context: TaskContext, node: PlanNode, record: ActionRecord) -> None:
        """Similarity is a retrieval lead, not verification or contradiction proof."""
        if not record.succeeded:
            return
        candidates = [
            fact for fact, score in self.semantic.query(node.title, limit=3)
            if score > 0.6 and fact.confidence < 0.5
        ]
        for fact in candidates:
            self._trace("reflect", f"related low-confidence fact needs evidence review; "
                        f"no contradiction/confirmation inferred: {fact.content[:80]}",
                        task_id=context.id)

    def _reflect_on_failure(self, context: TaskContext, node: PlanNode, error: str) -> None:
        self.wm.put(MemoryChunk(
            type=ChunkType.QUESTION,
            content=f"why did {node.tool} ({node.title}) fail? error: {error[:200]}",
            confidence=1.0, source="reflection",
        ), active_goal=context.goal, partition=context.id)
        if self.model is not None and node.attempts >= node.max_attempts:
            try:
                if self.before_model is not None: self.before_model(context)
                analysis = self.model.complete("reflect", {
                    "goal": context.goal, "failed_step": node.title, "error": error,
                })
            except Exception as exc:
                if getattr(exc, "persistence_checkpoint_failed", False): raise
                if getattr(exc, "outcome", None) == "unknown":
                    context.model_outcome_unknown = True
                    self._hold_unknown(context)
                    return
                self._trace("reflect", f"reflection model error: {type(exc).__name__}; original tool failure retained", task_id=context.id)
                return
            if isinstance(analysis, dict) and analysis.get("outcome") == "unknown":
                context.model_outcome_unknown = True
                self._hold_unknown(context)
                return
            valid = (isinstance(analysis, dict) and analysis.get("available") is not False
                     and all(isinstance(analysis.get(key), str) and analysis[key].strip() for key in ("cause", "fix"))
                     and type(analysis.get("retry")) is bool)
            if not valid:
                self._trace("reflect", "reflection unavailable or invalid; no causal analysis inferred", task_id=context.id)
                return
            self._trace("reflect", f"model reflection hypothesis: {str(analysis)[:200]}; correctness unverified", task_id=context.id)

    def _close_episode(self, context: TaskContext, outcome: EpisodeOutcome) -> None:
        retained = self.action_history(context.id) if self.action_history is not None else []
        by_id = {record.id: record.model_copy(deep=True) for record in retained}
        for record in self.dispatcher.records:
            if record.task_id == context.id:
                by_id[record.id] = record.model_copy(deep=True)
        actions = sorted(by_id.values(), key=lambda record: (record.started_at, record.id))
        self.episodic.log_execution(
            task_id=context.id, goal=context.goal,
            start_state=context.goal, actions=actions,
            outcome=outcome,
            reflection=f"{outcome.value} after plan of {len(context.plan)} steps",
        )


def _run_async(coro):
    """Run an async dispatch from sync loop code."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)
