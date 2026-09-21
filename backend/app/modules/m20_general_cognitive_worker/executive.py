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
import random
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
    information_gain: float
    cost: float
    progress_probability: float

    @property
    def score(self) -> float:
        if self.cost <= 0:
            return 0.0
        return (0.5 * self.information_gain + 0.5 * self.progress_probability) / self.cost


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
                information_gain=max(0.0, min(1.0, info_gain)),
                cost=RISK_COST.get(node.risk, 1.0),
                progress_probability=max(0.05, min(0.95, progress)),
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
            return {"simulations": 0, "best_ordering": [], "expected_success": 1.0}
        best_order: list[str] = []
        best_score = -1.0
        for _ in range(self.simulations):
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
        expected = math.exp(best_score) if best_score < 0 else 1.0
        return {
            "simulations": self.simulations,
            "best_ordering": best_order,
            "expected_success": round(expected, 4),
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

    def _trace(self, phase: str, detail: str, *, task_id: str | None = None, policy_basis: str = "") -> None:
        self.traces.append(TraceEntry(task_id=task_id, phase=phase, detail=detail, policy_basis=policy_basis))

    def start(self, context: TaskContext) -> TaskContext:
        """Plan the goal, seed working memory, and run the loop."""
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
            try:
                context.plan = self.planner.decompose(
                    context.goal, context=self.wm.context(partition=context.id),
                )
                self._trace("plan", f"plan with {len(context.plan)} steps", task_id=context.id)
            except PlanError as exc:
                context.state = TaskState.BLOCKED
                self._trace("plan", f"planning failed: {exc}", task_id=context.id)
                return context
        self.wm.put(MemoryChunk(
            type=ChunkType.GOAL, content=context.goal, confidence=1.0, source="executive",
        ), active_goal=context.goal, partition=context.id)
        if self.before_run is not None:
            self.before_run(context)
        return self.run(context)

    def run(self, context: TaskContext, *, budget: Budget | None = None) -> TaskContext:
        budget = budget or Budget()
        if self.before_run is not None:
            self.before_run(context)
        ticks = 0
        context.state = TaskState.RUNNING
        while ticks < self.max_ticks and ticks < budget.seconds:
            ticks += 1
            if HTNPlanner.is_complete(context.plan):
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
                node.state = TaskState.SUCCEEDED
                node.result_summary = "reasoning step (no tool)"
                self._trace("act", f"reasoned step: {node.title}", task_id=context.id)
                continue
            try:
                import asyncio
                record = _run_async(self.dispatcher.dispatch(
                    node.tool, node.arguments, task_id=context.id,
                    granted_approval_id=node.approval_id,
                ))
                if record.succeeded:
                    node.state = TaskState.SUCCEEDED
                    node.approval_id = None
                    node.result_summary = record.result_summary
                    self._trace("act", f"{node.tool} succeeded", task_id=context.id)
                    self._evaluate_expectation(context, node, record)
                else:
                    node.state = TaskState.FAILED if node.attempts >= node.max_attempts else TaskState.PENDING
                    self._trace("evaluate", f"{node.tool} failed: {record.result_summary}",
                                task_id=context.id)
                    self._reflect_on_failure(context, node, record.result_summary)
            except ApprovalPending as pending:
                node.state = TaskState.WAITING_APPROVAL
                node.approval_id = pending.approval_id
                context.state = TaskState.WAITING_APPROVAL
                self._trace("act", f"{node.tool} gated: approval {pending.approval_id}",
                            task_id=context.id, policy_basis="spec 4.4 approval gating")
                return context
            except ToolBlockedError as blocked:
                node.state = TaskState.BLOCKED
                context.state = TaskState.BLOCKED
                self._trace("act", f"{node.tool} blocked: {'; '.join(blocked.reasons)}",
                            task_id=context.id, policy_basis="constitutional rules")
                self._close_episode(context, EpisodeOutcome.ABANDONED)
                return context
            except Exception as exc:
                node.state = TaskState.FAILED if node.attempts >= node.max_attempts else TaskState.PENDING
                self._trace("evaluate", f"{node.tool} error: {exc}", task_id=context.id)
                self._reflect_on_failure(context, node, str(exc))
        context.state = TaskState.FAILED
        self._trace("evaluate", "budget exhausted", task_id=context.id)
        self._close_episode(context, EpisodeOutcome.FAILED)
        return context

    def resume_after_approval(self, context: TaskContext, node_id: str, approved: bool) -> TaskContext:
        for node in context.plan:
            if node.id == node_id:
                if approved:
                    node.state = TaskState.PENDING  # approval_id kept: consumed at dispatch
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
        context.state = TaskState.RUMINATING
        result = self.ruminator.ruminate(context.plan)
        self._trace("ruminate", f"mcts ordering: {result['best_ordering']}", task_id=context.id)
        context.state = TaskState.RUNNING
        return result

    def _evaluate_expectation(self, context: TaskContext, node: PlanNode, record: ActionRecord) -> None:
        """Surprise detection: results that contradict stored facts trigger
        a world-model update (spec 4.2.4 Evaluate)."""
        if not record.succeeded:
            return
        contradictions = [
            fact for fact, score in self.semantic.query(node.title, limit=3)
            if score > 0.6 and fact.confidence < 0.5
        ]
        for fact in contradictions:
            self._trace("reflect", f"world-model update: low-confidence fact contradicted: {fact.content[:80]}",
                        task_id=context.id)
            self.semantic.confirm(fact.id)

    def _reflect_on_failure(self, context: TaskContext, node: PlanNode, error: str) -> None:
        self.wm.put(MemoryChunk(
            type=ChunkType.QUESTION,
            content=f"why did {node.tool} ({node.title}) fail? error: {error[:200]}",
            confidence=1.0, source="reflection",
        ), active_goal=context.goal, partition=context.id)
        if self.model is not None and node.attempts >= node.max_attempts:
            analysis = self.model.complete("reflect", {
                "goal": context.goal, "failed_step": node.title, "error": error,
            })
            self._trace("reflect", f"model reflection: {str(analysis)[:200]}", task_id=context.id)

    def _close_episode(self, context: TaskContext, outcome: EpisodeOutcome) -> None:
        actions = [r for r in self.dispatcher.records]
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
