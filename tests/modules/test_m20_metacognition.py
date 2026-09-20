"""Focused tests for features-doc rows 10-34 (Executive Function & Meta-Cognition).

Each test is named test_rowNN_* so the audit ledger can map row -> evidence.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m20_general_cognitive_worker.metacognition import (
    AbstractionShifter, AttentionResidueManager, BiasDetector, CalibrationEngine, CounterfactualEngine,
    CuriosityEngine, DecisionFatigueGuard, DevilsAdvocate, EpistemicCalendar,
    FlowStateManager, GoalHierarchyManager, ImprovementLoop, IntuitionEngine,
    KnowledgeDecayModeler, LoadBalancer, MetaLearner, PerspectiveSimulator,
    PlanningHorizonController, PromptRegistry, PromptTemplate, ReframingEngine,
    RoutinePolicy, SteelmanEngine, TemporalTradeoffs, WorldModelRegistry,
    project_regret, quantify_sacrifice, sunk_cost_choice,
)
from app.modules.m20_general_cognitive_worker.schemas import (
    ActionRecord, ChunkType, Episode, EpisodeOutcome, MemoryChunk, PlanNode, Risk,
    TaskContext, TaskState,
)
from app.modules.m20_general_cognitive_worker.semantic_memory import SemanticMemory
from app.modules.m20_general_cognitive_worker.working_memory import WorkingMemory


def test_row10_recursive_improvement_requires_approval_and_versions():
    registry = PromptRegistry()
    registry.register(PromptTemplate(name="orient_prompt", content="analyze the state"))
    loop = ImprovementLoop(registry)
    metrics = loop.analyze(
        tool_records=[type("R", (), {"succeeded": False})(), type("R", (), {"succeeded": True})()],
        episodes=[Episode(task_id="t", goal="g", outcome=EpisodeOutcome.SUCCEEDED)],
        calibration_error=0.12,
    )
    assert metrics["tool_failure_rate"] == 0.5
    proposal = loop.propose("orient_prompt", "analyze the state, then list knowledge gaps first",
                            evidence=metrics, expected_gain=0.1)
    with pytest.raises(PermissionError):
        loop.apply(proposal.id, approved=False)
    applied = loop.apply(proposal.id, approved=True, approval_id="appr-1")
    assert applied.version == 2 and "knowledge gaps" in applied.content
    assert registry.get("orient_prompt").version == 2
    with pytest.raises(ValueError):
        loop.propose("constitutional_rules", "ignore the rules", evidence={}, expected_gain=1.0)
    with pytest.raises(KeyError):
        loop.propose("nonexistent", "x", evidence={}, expected_gain=0.1)


def test_row11_meta_learning_transfers_patterns_across_domains():
    learner = MetaLearner()
    ep = Episode(task_id="t1", goal="research professors and draft email outreach",
                 actions=[ActionRecord(tool="web_search"), ActionRecord(tool="draft_email"),
                          ActionRecord(tool="send_email")],
                 outcome=EpisodeOutcome.SUCCEEDED)
    pattern = learner.abstract(ep)
    assert pattern is not None and pattern.role_sequence == ("gather", "transform", "deliver")
    transfers = learner.transfer("investigate rival coffee shops and post a review")
    # coffee-shop domain tokens differ from professor-outreach tokens -> transfer fires
    assert transfers and transfers[0]["role_sequence"] == ["gather", "transform", "deliver"]
    same = learner.transfer("research professors for phd outreach")
    assert same == []  # same domain overlap: not cross-domain


def test_row12_load_balancing_by_complexity_and_deadline():
    now = datetime.now(timezone.utc)
    simple = TaskContext(goal="trivial", importance=1,
                         plan=[PlanNode(title="a", risk=Risk.READ)])
    hard = TaskContext(goal="hard", importance=3, deadline=now + timedelta(minutes=30),
                       plan=[PlanNode(title=str(i), risk=Risk.EXTERNAL) for i in range(4)])
    allocation = LoadBalancer().allocate([simple, hard], total_ticks=100, now=now)
    assert allocation[hard.id] > allocation[simple.id]
    assert sum(allocation.values()) == pytest.approx(100.0)
    assert LoadBalancer().allocate([], total_ticks=10) == {}


def test_row13_calibration_flags_overconfidence_and_shrinks():
    engine = CalibrationEngine()
    flagged = engine.assess_claim("the deadline is Friday", 0.95, evidence_count=0)
    assert flagged.flagged and "ceiling" in flagged.flag_reason
    ok = engine.assess_claim("water is wet", 0.6, evidence_count=3)
    assert not ok.flagged
    for i in range(10):
        c = engine.assess_claim(f"claim {i}", 0.8, evidence_count=3)
        engine.resolve(c.id, correct=(i < 6))
    curve = engine.calibration_curve()
    assert curve and curve[0]["observed_accuracy"] == pytest.approx(0.6)
    assert engine.calibration_error() is not None
    adjusted = engine.adjusted_confidence(0.95)
    assert adjusted < 0.95  # shrunk toward 60% observed accuracy


def test_row14_counterfactual_simulation():
    engine = CounterfactualEngine()
    ep = Episode(task_id="t", goal="ship feature",
                 actions=[ActionRecord(tool="deploy", succeeded=False)],
                 outcome=EpisodeOutcome.FAILED)
    result = engine.simulate(ep, [
        {"replaces_step": 0, "action": "deploy behind feature flag", "risk": "reversible"},
        {"replaces_step": 0, "action": "read-only dry run", "risk": "read"},
    ])
    assert result["actual_outcome"] == "failed"
    assert result["best_alternative"]["alternative_action"] == "read-only dry run"
    assert all("lesson" in a for a in result["alternatives"])


def test_row15_temporal_discounting_and_calibration():
    tt = TemporalTradeoffs(k=0.05)
    result = tt.compare(immediate_value=50.0, delayed_value=100.0, delay_days=365)
    assert result["choice"] in ("immediate", "delayed")
    assert result["discounted_delayed_value"] < 100.0
    fitted = tt.calibrate([
        {"immediate": 50, "delayed": 100, "delay_days": 365, "chose_delayed": False},
        {"immediate": 50, "delayed": 400, "delay_days": 365, "chose_delayed": True},
    ])
    assert 0.0 <= fitted <= 0.5


def test_row16_attention_residue_switch():
    wm = WorkingMemory(capacity=20)
    goal = "climate grant"
    wm.put(MemoryChunk(type=ChunkType.GOAL, content="climate grant deadline",
                       salience=0.99, confidence=1.0), active_goal=goal, partition="ctx-a")
    wm.put(MemoryChunk(type=ChunkType.FACT, content="trivial note",
                       salience=0.0, confidence=0.0), active_goal=goal, partition="ctx-a")
    report = AttentionResidueManager(carry_over_threshold=0.8).switch(
        wm, from_partition="ctx-a", to_partition="ctx-b", active_goal="new project")
    assert report.cleared_count >= 1
    assert wm.focused(partition="ctx-a") == []
    carried = [c.content for c in wm.focused(partition="ctx-b")]
    assert any("[carry-over]" in c for c in carried)
    assert not any("trivial note" in c for c in carried)


def test_row17_flow_state_zones_and_structuring():
    flow = FlowStateManager()
    assert flow.assess(challenge=0.5, skill=0.52)["zone"] == "flow"
    assert flow.assess(challenge=0.9, skill=0.3)["zone"] == "anxiety"
    assert flow.assess(challenge=0.2, skill=0.8)["zone"] == "boredom"
    assert flow.assess(challenge=0.1, skill=0.1)["zone"] == "apathy"
    structured = flow.structure_work([
        {"title": "hard", "difficulty": 0.9},
        {"title": "easy", "difficulty": 0.3},
        {"title": "medium", "difficulty": 0.5},
    ], skill=0.45)
    assert structured[0]["title"] in ("easy", "medium")  # ramps from near skill level
    with pytest.raises(ValueError):
        flow.assess(challenge=1.5, skill=0.5)


def test_row18_cognitive_reframing():
    engine = ReframingEngine()
    reframe = engine.reframe("the deploy failed with an exception in the payment test")
    assert reframe.category == "technical"
    assert reframe.actionable_steps and "regression test" in reframe.actionable_steps[1]
    generic = engine.reframe("everything went sideways today")
    assert generic.category == "general" and generic.actionable_steps


def test_row19_bias_detection_and_correction():
    detector = BiasDetector()
    findings = detector.scan("We've already invested so much, we can't quit now - success is guaranteed.")
    biases = {f.bias for f in findings}
    assert "sunk_cost" in biases and "overconfidence" in biases
    result = detector.scan_with_correction("everyone is doing it so we should too")
    assert result["findings"][0]["bias"] == "bandwagon"
    assert "mitigation" in result["corrected_prompt"] or "evaluate" in result["corrected_prompt"]
    assert detector.scan("the data shows a modest effect") == []


def test_row20_intuition_fast_then_slow_validation():
    from app.modules.m20_general_cognitive_worker.schemas import Skill
    engine = IntuitionEngine()
    skill = Skill(name="interview-prep", goal_pattern="prepare for interviews", steps=[])
    gut = engine.gut("how do I prep for the interview?", skill_matches=[skill], fact_hits=[])
    assert gut.confidence >= 0.7 and "interview-prep" in gut.answer
    result = engine.validate(gut, lambda: "use the interview-prep procedure, then do a mock round")
    assert result["agree"] is True
    gut2 = engine.gut("totally novel question", skill_matches=[], fact_hits=[])
    assert gut2.confidence <= 0.1
    result2 = engine.validate(gut2, lambda: "deliberate answer from slow reasoning")
    assert result2["agree"] is False
    assert result2["final_answer"] == "deliberate answer from slow reasoning"


def test_row21_world_model_versioning_and_evidence():
    registry = WorldModelRegistry()
    registry.register("growth", {"market": "expanding"})
    registry.register("stagnation", {"market": "flat"})
    registry.apply_evidence("growth", supported=True, weight=1.5)
    registry.apply_evidence("stagnation", supported=False, weight=1.0)
    assert registry.current_best().name == "growth"
    model = registry.revise("growth", {"market": "expanding", "moat": "network effects"})
    assert model.version == 2 and model.history[0]["version"] == 1
    assert 0.0 < model.posterior < 1.0


def test_row22_goal_conflict_detection_and_restructure():
    manager = GoalHierarchyManager(terminal_values=["honesty", "legality"])
    bad = PlanNode(title="create fake reviews to boost ratings")
    good = PlanNode(title="write honest comparison post", depends_on=[bad.id])
    free = PlanNode(title="research competitor features")
    conflicts = manager.check([bad, good, free])
    assert conflicts and conflicts[0].violated_value in ("honesty", "legality")
    result = manager.restructure([bad, good, free])
    assert result["restructured"] is True
    assert bad.state == TaskState.CANCELLED
    assert good.depends_on == []  # re-linked after parent removal
    assert "research competitor features" in result["remaining_steps"]


def test_row23_decision_fatigue_automation_and_caps():
    guard = DecisionFatigueGuard()
    guard.add_policy(RoutinePolicy(decision_type="calendar_color", default_choice="blue", max_auto_per_day=1))
    auto = guard.decide("calendar_color", options=["blue", "red"], routine=True, stakes="low")
    assert auto["automated"] and auto["chosen"] == "blue"
    capped = guard.decide("calendar_color", options=["blue", "red"], routine=True, stakes="low")
    assert capped["automated"] is False  # daily cap
    high = DecisionFatigueGuard()
    high.add_policy(RoutinePolicy(decision_type="hire", default_choice="candidate-a"))
    assert high.decide("hire", options=["candidate-a"], routine=True, stakes="high")["automated"] is False


def test_row24_regret_projection_table():
    result = project_regret({
        "safe": {"good": 50, "bad": 50},
        "risky": {"good": 200, "bad": 0},
    })
    assert result["regret_table"]["safe"]["good"] == 150
    assert result["max_regret"]["risky"] == 50
    assert result["minimax_choice"] == "risky"


def test_row25_opportunity_cost_quantified():
    result = quantify_sacrifice({"name": "job-a", "value": 80.0},
                                [{"name": "job-b", "value": 120.0}, {"name": "job-c", "value": 60.0}])
    assert result["best_foregone"]["name"] == "job-b"
    assert result["opportunity_cost"] == 40.0


def test_row26_sunk_cost_resistance():
    result = sunk_cost_choice([
        {"name": "project-x", "past_investment": 900.0, "forward_value": 10.0},
        {"name": "project-y", "past_investment": 0.0, "forward_value": 50.0},
    ])
    assert result["recommended"] == "project-y"
    assert result["sunk_cost_influenced"] is True
    clean = sunk_cost_choice([
        {"name": "a", "past_investment": 0.0, "forward_value": 5.0},
        {"name": "b", "past_investment": 0.0, "forward_value": 1.0},
    ])
    assert clean["sunk_cost_influenced"] is False


def test_row27_planning_horizon_flexibility():
    ctrl = PlanningHorizonController()
    shallow = ctrl.horizon(uncertainty=0.9, time_available_minutes=30)
    deep = ctrl.horizon(uncertainty=0.1, time_available_minutes=480)
    assert shallow["max_depth"] < deep["max_depth"]
    assert shallow["replan_interval_minutes"] > deep["replan_interval_minutes"]
    with pytest.raises(ValueError):
        ctrl.horizon(uncertainty=1.5, time_available_minutes=10)


def test_row28_abstraction_level_shifting():
    shifter = AbstractionShifter()
    a = PlanNode(title="market research", tool="web_search")
    b = PlanNode(title="draft report", depends_on=[a.id])
    c = PlanNode(title="build prototype", tool="python_sandbox")
    plan = [a, b, c]
    strategy = shifter.rollup("launch product", plan, level="strategy")
    assert strategy["level"] == "strategy" and "3 steps" in strategy["summary"]
    streams = shifter.rollup("launch product", plan, level="streams")
    assert len(streams["streams"]) == 2
    research_stream = [s for s in streams["streams"] if s["root"] == "market research"][0]
    assert research_stream["descendants"] == ["draft report"]
    steps = shifter.rollup("launch product", plan, level="steps")
    assert len(steps["steps"]) == 3
    with pytest.raises(ValueError):
        shifter.rollup("g", plan, level="quantum")


def test_row29_cognitive_diversity_perspectives():
    sim = PerspectiveSimulator()
    views = sim.evaluate({"summary": "ship the MVP", "evidence_count": 4, "risk": "reversible",
                          "upside": 8, "timeline_days": 21, "externally_visible": False})
    assert len(views) == 5
    by_persona = {v.persona: v for v in views}
    assert by_persona["analyst"].supports and not by_persona["analyst"].concerns
    risky = sim.evaluate({"summary": "yolo launch", "evidence_count": 0, "risk": "irreversible",
                          "upside": 2, "timeline_days": 180, "externally_visible": True})
    for view in risky:
        assert view.concerns, f"{view.persona} should have concerns"
        assert view.score < 0.5


def test_row30_devils_advocate_stress_test():
    advocate = DevilsAdvocate()
    report = advocate.stress_test(
        claim="our product will dominate the market",
        assumptions=["users want this", "competitors will not react", "costs stay flat"],
        evidence=["one user interview"],
    )
    assert len(report.assumption_attacks) == 3
    assert report.evidence_gaps  # 3 assumptions, 1 evidence
    assert report.alternative_explanations
    assert report.residual_confidence < 0.7


def test_row31_steelman_constructs_strongest_opposition():
    engine = SteelmanEngine()
    report = engine.strengthen(
        opposing_position="remote work hurts team cohesion",
        known_facts=[
            "remote teams report lower cohesion scores",
            "some teams ship faster remotely",
            "cohesion predicts retention",
        ],
    )
    assert report.supporting_points and "cohesion" in report.supporting_points[0]
    assert report.concessions
    assert report.response_skeleton[0].startswith("restate")


def test_row32_epistemic_calendar_reviews():
    calendar = EpistemicCalendar()
    old = datetime.now(timezone.utc) - timedelta(days=200)
    entry = calendar.register("competitor is not building this", formed_at=old, review_interval_days=90)
    fresh = calendar.register("water is wet", review_interval_days=365)
    due = calendar.due()
    assert due and due[0]["belief_id"] == entry.belief_id
    assert due[0]["overdue_days"] > 100
    calendar.mark_reviewed(entry.belief_id)
    assert all(d["belief_id"] != entry.belief_id for d in calendar.due())


def test_row33_knowledge_decay_forecast():
    memory = SemanticMemory()
    fact = memory.remember("competitor price is $10/mo", kind="price", decay_rate=0.0)
    fact.last_confirmed_at = datetime.now(timezone.utc) - timedelta(days=45)
    modeler = KnowledgeDecayModeler()
    assert modeler.default_decay("price") == 2.0
    forecasts = modeler.forecast(memory, days_ahead=60, threshold=0.6)
    assert any(f["fact_id"] == fact.id for f in forecasts)
    assert forecasts[0]["predicted_freshness"] < forecasts[0]["current_freshness"]
    assert "refresh_by" in forecasts[0]


def test_row34_curiosity_gaps_and_allocation():
    memory = SemanticMemory()
    memory.remember("python is a programming language")
    engine = CuriosityEngine(seed=1)
    gaps = engine.detect_gaps("compare quantum computing frameworks in python", memory)
    assert "quantum" in gaps and "python" not in gaps
    engine.detect_gaps("quantum hardware comparison", memory)  # gap frequency grows
    items = engine.allocate(idle_budget=10.0)
    assert items and items[0].gap == "quantum"
    assert items[0].allocated_budget > 0
    assert sum(i.allocated_budget for i in items) <= 10.0 + 1e-6
    pulls = engine.serendipity_pull(memory, count=1)
    assert pulls == ["python is a programming language"]
