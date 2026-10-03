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

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .episodic_memory import EpisodicMemory
from .evidence import OutcomeEstimate, ToolEvidence
from .htn_planner import HTNPlanner, PlanError
from .mcts import BoundedMCTS
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


# Safety ordering of risk tiers. A policy rank used only to order candidates
# (safer first). It is not a probability and not a cost estimate.
RISK_RANK = {Risk.READ: 0, Risk.REVERSIBLE: 1, Risk.EXTERNAL: 2, Risk.IRREVERSIBLE: 3}


@dataclass
class CandidateAction:
    """A ready step plus the evidence behind its ranking.

    ``progress_probability`` is the observed success rate of the step's tool in
    recorded episodes, or None when there is not enough evidence. There is no
    information-gain number: nothing in the recorded data measures it, so it
    is reported as not estimated.
    """

    node: PlanNode
    estimate: OutcomeEstimate
    risk_rank: int

    @property
    def progress_probability(self) -> float | None:
        return self.estimate.value

    @property
    def information_gain(self) -> None:
        return None

    @property
    def score(self) -> float | None:
        """Observed success rate when evidence exists; otherwise None."""
        return self.estimate.value

    @property
    def ranking_basis(self) -> str:
        if self.estimate.available:
            return (f"risk tier first, then observed success rate "
                    f"{self.estimate.successes}/{self.estimate.samples}")
        return f"risk tier only; no success estimate ({self.estimate.basis})"


class MetaReasoner:
    """Next-action selection (spec 4.2.4 Decide), evidence-based.

    Candidates are ordered safest risk tier first, then by the observed
    success rate of the step's tool (higher first), then by plan order. Steps
    without enough recorded evidence are not scored; they are ordered by risk
    tier and plan order only and say so.
    """

    def __init__(self, evidence: ToolEvidence | None = None) -> None:
        self.evidence = evidence or ToolEvidence(())

    def score_candidates(
        self, ready: list[PlanNode], *, wm_context: str = "", ltm_hits: int = 0,
    ) -> list[CandidateAction]:
        # wm_context / ltm_hits are accepted for API compatibility; neither is a
        # measurement of this step's success, so neither is turned into a score.
        candidates = [
            CandidateAction(
                node=node, estimate=self.evidence.for_tool(node.tool),
                risk_rank=RISK_RANK.get(node.risk, len(RISK_RANK)),
            )
            for node in ready
        ]
        order = {id(c): i for i, c in enumerate(candidates)}
        candidates.sort(key=lambda c: (
            c.risk_rank,
            0 if c.estimate.available else 1,
            -(c.estimate.value or 0.0),
            order[id(c)],
        ))
        return candidates


class MCTSRuminator:
    """Idle-time rumination: real UCT tree search (BoundedMCTS) over the
    remaining plan, driven by recorded tool evidence.

    Output distinguishes SIMULATED search from real execution, reports which
    steps were assumed to succeed for lack of evidence, and gives
    ``expected_success`` only when every step in the ordering has an evidence
    estimate (product of per-tool observed rates, independence assumed).
    Otherwise it is None, never a made-up number.
    """

    def __init__(
        self, simulations: int = 32, seed: int | None = None,
        evidence: ToolEvidence | None = None, max_seconds: float = 1.0,
    ) -> None:
        self.simulations = simulations
        self.evidence = evidence or ToolEvidence(())
        self._seed = seed
        self._max_seconds = max_seconds

    def ruminate(self, plan: list[PlanNode]) -> dict[str, Any]:
        pending = [n for n in plan if n.state == TaskState.PENDING]
        if not pending:
            return {"simulations": 0, "best_ordering": [], "expected_success": 1.0,
                    "expected_success_status": "nothing pending",
                    "mode": "simulated_search"}
        search = BoundedMCTS(
            max_simulations=self.simulations, max_seconds=self._max_seconds,
            seed=self._seed, evidence=self.evidence,
        ).search(plan)
        by_id = {n.id: n for n in plan}
        ordering_ids = list(search.principal_variation_ids)
        searched = len(ordering_ids)
        # Complete the ordering deterministically (dependency-safe, safer risk
        # first) for steps the search did not reach; flagged as unsearched.
        done = {n.id for n in plan if n.state == TaskState.SUCCEEDED} | set(ordering_ids)
        remaining = [n for n in pending if n.id not in done]
        while remaining:
            ready = [n for n in remaining if all(d in done for d in n.depends_on)]
            if not ready:
                break
            ready.sort(key=lambda n: RISK_RANK.get(n.risk, 9))
            ordering_ids.append(ready[0].id)
            done.add(ready[0].id)
            remaining.remove(ready[0])
        estimates = [self.evidence.for_tool(by_id[i].tool) for i in ordering_ids if i in by_id]
        if ordering_ids and all(e.available for e in estimates) and not remaining:
            expected = 1.0
            for e in estimates:
                expected *= e.value
            expected_status = "product of observed per-tool success rates; steps assumed independent"
        else:
            expected = None
            expected_status = (
                "not estimated: " + (
                    "plan has steps that cannot be ordered (blocked dependencies)"
                    if remaining else "some steps have too little recorded evidence"
                )
            )
        return {
            "simulations": search.simulations_run,
            "mode": search.mode,
            "best_ordering": [by_id[i].title for i in ordering_ids if i in by_id],
            "ordering_source": {"searched_steps": searched,
                                "unsearched_tail_steps": len(ordering_ids) - searched},
            "expected_success": round(expected, 4) if expected is not None else None,
            "expected_success_status": expected_status,
            "search_value": search.root_value,
            "search_value_standard_error": search.root_standard_error,
            "value_semantics": search.value_semantics,
            "assumed_success_steps": [by_id[i].title for i in search.assumed_success_steps if i in by_id],
            "evidence": search.evidence,
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
        self.evidence = ToolEvidence(self.episodic.episodes)
        self.ruminator = ruminator or MCTSRuminator(seed=7, evidence=self.evidence)
        self.max_ticks = max_ticks
        self.meta = MetaReasoner(self.evidence)
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
            self._trace("decide", f"next action: {chosen.node.title} ({chosen.ranking_basis})",
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
