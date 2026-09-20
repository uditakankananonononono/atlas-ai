"""GCW service facade: one object wiring every subsystem together.

This is the entry point the integrator binds: inject the LLM clients
(ExecutiveModel/PlannerModel/Transcriber/VisionModel/DocumentParser), the
Module 0 approval gate, and production stores; everything else composes
here. Also owns stand-up reporting for the Executive Dashboard (spec 4.3)
and Atlas supervision (health + budget signals).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .embeddings import EmbeddingProvider
from .episodic_memory import EpisodicMemory
from .executive import DeliberativeLoop, ExecutiveModel, MCTSRuminator
from .htn_planner import HTNPlanner, PlannerModel
from .reflection import (
    CreativityMode, EmotionalStateModel, IdeationEngine, RetrospectiveEngine,
    ScratchpadManager, UncertaintyGate,
)
from .safety import ApprovalGate, ConstitutionalRules, InMemoryApprovalGate, SafetyGate, SandboxPolicy
from .scheduler import ContextScheduler
from .schemas import (
    ActionRecord, Budget, CognitiveEvent, Episode, Risk, SemanticFact, Skill,
    TaskContext, TaskState, TraceEntry,
)
from .semantic_memory import SemanticMemory
from .sensory import DocumentParser, SensoryLayer, Transcriber, VisionModel
from .skill_library import SkillLibrary
from .tools import ToolDispatcher, ToolRegistry
from .working_memory import AttentionController, WorkingMemory

# Judgment-style Category 1 rows ship as prompt-chain skills (spec 4.2.3
# procedural memory): the executive matches goals to them and runs the chain
# through the model. They are reasoning scaffolds, not autonomous actions.
JUDGMENT_SKILLS: list[dict[str, Any]] = [
    {
        "name": "devils-advocate",
        "goal_pattern": "stress test challenge my conclusion argument",
        "chain": ["state the conclusion", "argue the strongest case against it",
                  "list what would change the conclusion"],
    },
    {
        "name": "steelman",
        "goal_pattern": "steelman strongest version opposing argument",
        "chain": ["restate the opposing position at its strongest",
                  "list its best evidence", "only then respond"],
    },
    {
        "name": "premortem",
        "goal_pattern": "premortem imagine project failure prevent",
        "chain": ["imagine the project failed completely", "list the most likely causes",
                  "turn each cause into a preventive action"],
    },
    {
        "name": "cognitive-reframing",
        "goal_pattern": "reframe setback learning opportunity",
        "chain": ["state the setback plainly", "extract the actionable lesson",
                  "name the next smallest step"],
    },
    {
        "name": "second-order-check",
        "goal_pattern": "second order effects consequences",
        "chain": ["list first-order effects", "for each, list its consequences",
                  "flag delayed and feedback effects"],
    },
    {
        "name": "bias-scan",
        "goal_pattern": "detect cognitive biases in reasoning",
        "chain": ["check sunk cost, anchoring, confirmation, availability biases",
                  "state which apply and why", "re-derive the conclusion without them"],
    },
]


class CognitiveWorkerService:
    """The General Cognitive Worker (spec section 4)."""

    def __init__(
        self,
        *,
        executive_model: ExecutiveModel | None = None,
        planner_model: PlannerModel | None = None,
        approval_gate: ApprovalGate | None = None,
        embedder: EmbeddingProvider | None = None,
        attention: AttentionController | None = None,
        transcriber: Transcriber | None = None,
        vision: VisionModel | None = None,
        document_parser: DocumentParser | None = None,
        sandbox: SandboxPolicy | None = None,
        rules: ConstitutionalRules | None = None,
        working_memory_capacity: int = 50,
        seed_judgment_skills: bool = True,
    ) -> None:
        self.embedder = embedder
        self.sensory = SensoryLayer(
            transcriber=transcriber, vision=vision, document_parser=document_parser,
        )
        self.working_memory = WorkingMemory(
            capacity=working_memory_capacity, attention=attention,
        )
        self.episodic = EpisodicMemory(embedder=embedder)
        self.semantic = SemanticMemory(embedder=embedder)
        self.skills = SkillLibrary()
        self.tools = ToolRegistry()
        self.safety = SafetyGate(
            rules=rules, approvals=approval_gate or InMemoryApprovalGate(), sandbox=sandbox,
        )
        self.dispatcher = ToolDispatcher(self.tools, self.safety)
        self.planner = HTNPlanner(model=planner_model)
        self.scheduler = ContextScheduler()
        self.scratchpads = ScratchpadManager()
        self.ideation = IdeationEngine()
        self.retrospectives = RetrospectiveEngine(embedder=embedder)
        self.emotions = EmotionalStateModel()
        self.uncertainty = UncertaintyGate()
        self.creativity = CreativityMode()
        self.executive_model = executive_model
        self.loop = DeliberativeLoop(
            planner=self.planner, dispatcher=self.dispatcher,
            working_memory=self.working_memory, episodic=self.episodic,
            semantic=self.semantic, skills=self.skills, model=executive_model,
        )
        if seed_judgment_skills:
            self._seed_judgment_skills()

    def _seed_judgment_skills(self) -> None:
        for entry in JUDGMENT_SKILLS:
            steps = [ActionRecord(tool="prompt_chain", arguments={"step": s}) for s in entry["chain"]]
            self.skills.register(Skill(
                name=entry["name"], goal_pattern=entry["goal_pattern"], steps=steps,
            ))

    # -- perception ------------------------------------------------------

    def ingest(self, event: CognitiveEvent, *, context_id: str | None = None) -> CognitiveEvent | None:
        """Push a normalized sensory event into working memory."""
        if event is None:
            return None
        from .schemas import ChunkType, MemoryChunk
        goal = ""
        if context_id and (ctx := self.scheduler.get(context_id)):
            goal = ctx.goal
        self.working_memory.put(MemoryChunk(
            type=ChunkType.FACT, content=event.text, confidence=event.confidence,
            source=f"sensory:{event.modality.value}",
        ), active_goal=goal, partition=context_id or "")
        return event

    # -- goals and execution --------------------------------------------

    def submit_goal(
        self,
        goal: str,
        *,
        importance: int = 3,
        deadline: datetime | None = None,
        budget: Budget | None = None,
        run_immediately: bool = True,
    ) -> TaskContext:
        context = TaskContext(
            goal=goal, importance=max(1, min(5, importance)), deadline=deadline,
        )
        context.wm_partition = context.id
        self.scheduler.add(context)
        if run_immediately:
            self.loop.start(context)
            self.emotions.record_outcome(context.state == TaskState.SUCCEEDED)
        context.updated_at = datetime.now(timezone.utc)
        return context

    def tick(self, *, budget: Budget | None = None) -> TaskContext | None:
        """One scheduler step: time-slice the highest-priority context."""
        context = self.scheduler.next_context()
        if context is None:
            return None
        if context.state in (TaskState.PENDING, TaskState.PLANNING):
            self.loop.start(context)
        elif context.state in (TaskState.RUNNING, TaskState.RUMINATING):
            self.loop.run(context, budget=budget)
        context.updated_at = datetime.now(timezone.utc)
        return context

    def resume(self, task_id: str, node_id: str, *, approved: bool) -> TaskContext | None:
        context = self.scheduler.get(task_id)
        if context is None:
            return None
        return self.loop.resume_after_approval(context, node_id, approved)

    def ruminate(self, task_id: str) -> dict[str, Any] | None:
        context = self.scheduler.get(task_id)
        if context is None:
            return None
        return self.loop.ruminate(context)

    # -- reporting and supervision ---------------------------------------

    def standup(self) -> str:
        """Daily stand-up for the Executive Dashboard (spec 4.3)."""
        lines = [f"GCW stand-up {datetime.now(timezone.utc).date().isoformat()}"]
        contexts = list(self.scheduler._contexts.values())
        if not contexts:
            lines.append("- no active work")
        for ctx in sorted(contexts, key=lambda c: c.created_at):
            total = len(ctx.plan)
            done = sum(1 for n in ctx.plan if n.state == TaskState.SUCCEEDED)
            blocked = [n.title for n in ctx.plan if n.state in (TaskState.BLOCKED, TaskState.WAITING_APPROVAL)]
            lines.append(
                f"- [{ctx.state.value}] {ctx.goal} ({done}/{total} steps)"
                + (f" | blocked on: {', '.join(blocked)}" if blocked else "")
            )
            for note in ctx.standup_notes[-3:]:
                lines.append(f"    note: {note}")
        return "\n".join(lines)

    def supervise(self) -> dict[str, Any]:
        """Atlas supervision: module health and budget signals."""
        contexts = list(self.scheduler._contexts.values())
        by_state: dict[str, int] = {}
        for ctx in contexts:
            by_state[ctx.state.value] = by_state.get(ctx.state.value, 0) + 1
        tool_failures = sum(1 for r in self.dispatcher.records if not r.succeeded)
        return {
            "module": "m20_general_cognitive_worker",
            "healthy": True,
            "tasks": by_state,
            "working_memory_chunks": len(self.working_memory),
            "episodes": len(self.episodic),
            "semantic_facts": len(self.semantic),
            "skills": len(self.skills),
            "tools": len(self.tools),
            "tool_calls": len(self.dispatcher.records),
            "tool_failures": tool_failures,
            "traces": len(self.loop.traces),
            "emotional_tone_bias": self.emotions.tone_bias(),
            "cognitive_load": self.scheduler.cognitive_load(),
        }

    def traces(self, *, task_id: str | None = None) -> list[TraceEntry]:
        return [
            t for t in self.loop.traces if task_id is None or t.task_id == task_id
        ]

    def close_task(self, task_id: str, *, went_well: list[str], went_poorly: list[str],
                   lessons: list[str]) -> None:
        """Write the retrospective and clear the WM partition."""
        self.retrospectives.write(
            task_id, went_well=went_well, went_poorly=went_poorly, lessons=lessons,
        )
        self.working_memory.clear_partition(task_id)


# Legacy runtime exports used by Claire and the original Module 20 surface.
from .legacy_service import Service, Run, State
