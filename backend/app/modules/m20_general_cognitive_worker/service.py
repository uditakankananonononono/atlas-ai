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
from .metacognition import (
    AttentionResidueManager, BiasDetector, CalibrationEngine, CounterfactualEngine,
    CuriosityEngine, DecisionFatigueGuard, DevilsAdvocate, EpistemicCalendar,
    FlowStateManager, GoalHierarchyManager, ImprovementLoop, IntuitionEngine,
    KnowledgeDecayModeler, LoadBalancer, MetaLearner, PerspectiveSimulator,
    PlanningHorizonController, PromptRegistry, ReframingEngine, SteelmanEngine,
    TemporalTradeoffs, WorldModelRegistry, AbstractionShifter,
)
from .foresight import (
    AntifragilityAssessor, AsymmetryFinder, BaseRateIntegrator, BayesianUpdater,
    CausalAssessor, ConstraintAnalyzer, EVCalculator, HypothesisTracker,
    InsightCapture, KellySizer, LeverageFinder, OptimismCalibrator, OptionalityAnalyzer, OutsideView,
    PlanningFallacyCorrector, PremortemEngine, RedTeamer, ReferenceClassForecaster,
    ReversibilityAssessor, RiskOfRuinAnalyzer, ScenarioPlanner, SecondOrderTracer,
    SerendipityEngine, SimulationFidelityTracker, SystemsModel,
)
from .strategy import (
    AuctionAdvisor, ConstraintsManager, CriticalPathAnalyzer, DecisionTreeBuilder,
    DisruptionAssessor, ErgodicityAnalyzer, FlywheelFinder, GameAnalyzer,
    JTBDFramer, LittlesLawAdvisor, MechanismDesigner, MoatAssessor,
    MonteCarloProjector, NashFinder, NetworkEffectAnalyzer, NonLinearModeler,
    ParetoAnalyzer, PrincipalAgentDesigner, QueueAnalyzer, RealOptionsValuer,
    SensitivityExplorer, SignalingAssessor, TippingPointDetector, TornadoBuilder,
    ValueChainMapper,
)
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
        # Executive Function & Meta-Cognition engines (features-doc rows 10-34)
        self.prompt_registry = PromptRegistry()
        self.improvement = ImprovementLoop(self.prompt_registry)
        self.meta_learner = MetaLearner()
        self.load_balancer = LoadBalancer()
        self.calibration = CalibrationEngine()
        self.counterfactuals = CounterfactualEngine()
        self.temporal = TemporalTradeoffs()
        self.residue = AttentionResidueManager()
        self.flow = FlowStateManager()
        self.reframing = ReframingEngine()
        self.bias_detector = BiasDetector()
        self.intuition = IntuitionEngine()
        self.world_models = WorldModelRegistry()
        self.goal_hierarchy = GoalHierarchyManager()
        self.decision_guard = DecisionFatigueGuard()
        self.horizon = PlanningHorizonController()
        self.abstraction = AbstractionShifter()
        self.perspectives = PerspectiveSimulator()
        self.devils_advocate = DevilsAdvocate()
        self.steelman = SteelmanEngine()
        self.epistemic_calendar = EpistemicCalendar()
        self.decay_modeler = KnowledgeDecayModeler()
        self.curiosity = CuriosityEngine()
        # Simulation, forecasting and decision-analysis engines (rows 35-59)
        self.serendipity = SerendipityEngine()
        self.insights = InsightCapture()
        self.sim_fidelity = SimulationFidelityTracker()
        self.hypotheses = HypothesisTracker()
        self.bayes = BayesianUpdater()
        self.causal = CausalAssessor()
        self.base_rates = BaseRateIntegrator()
        self.reference_class = ReferenceClassForecaster()
        self.outside_view = OutsideView()
        self.planning_fallacy = PlanningFallacyCorrector()
        self.optimism = OptimismCalibrator()
        self.scenarios = ScenarioPlanner()
        self.premortem = PremortemEngine()
        self.red_team = RedTeamer()
        self.second_order = SecondOrderTracer()
        self.leverage = LeverageFinder()
        self.constraints = ConstraintAnalyzer()
        self.antifragility = AntifragilityAssessor()
        self.optionality = OptionalityAnalyzer()
        self.reversibility = ReversibilityAssessor()
        self.asymmetry = AsymmetryFinder()
        self.ev_calculator = EVCalculator()
        self.risk_of_ruin = RiskOfRuinAnalyzer()
        self.kelly = KellySizer()
        # Strategic and quantitative decision aids (rows 60-84)
        self.ergodicity = ErgodicityAnalyzer()
        self.nonlinear = NonLinearModeler()
        self.tipping_points = TippingPointDetector()
        self.network_effects = NetworkEffectAnalyzer()
        self.flywheels = FlywheelFinder()
        self.moats = MoatAssessor()
        self.disruption = DisruptionAssessor()
        self.jtbd = JTBDFramer()
        self.value_chain = ValueChainMapper()
        self.pareto = ParetoAnalyzer()
        self.toc = ConstraintsManager()
        self.queues = QueueAnalyzer()
        self.littles = LittlesLawAdvisor()
        self.critical_paths = CriticalPathAnalyzer()
        self.monte_carlo = MonteCarloProjector()
        self.sensitivity = SensitivityExplorer()
        self.tornado = TornadoBuilder()
        self.decision_trees = DecisionTreeBuilder()
        self.real_options = RealOptionsValuer()
        self.game_theory = GameAnalyzer()
        self.nash = NashFinder()
        self.mechanisms = MechanismDesigner()
        self.auctions = AuctionAdvisor()
        self.signaling = SignalingAssessor()
        self.principal_agent = PrincipalAgentDesigner()
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
            "metacognition": {
                "prompt_templates": len(self.prompt_registry.active()),
                "improvement_proposals": len(self.improvement.proposals),
                "abstract_patterns": len(self.meta_learner.patterns),
                "claims_tracked": len(self.calibration.claims),
                "calibration_error": self.calibration.calibration_error(),
                "world_models": len(self.world_models.models),
                "beliefs_tracked": len(self.epistemic_calendar.beliefs),
                "known_gaps": len(self.curiosity._gap_counts),
                "decisions_automated": self.decision_guard.automated_total,
            },
            "foresight": {
                "insights_captured": len(self.insights.insights),
                "simulations_tracked": len(self.sim_fidelity.records),
                "simulation_fidelity": self.sim_fidelity.fidelity(),
                "active_hypotheses": len(self.hypotheses.ranking()),
                "reference_cases": len(self.reference_class.cases),
                "planning_history_kinds": len(self.planning_fallacy.history),
            },
            "strategy": {
                "toc_snapshots": len(self.toc.snapshots),
            },
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
