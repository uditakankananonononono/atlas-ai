"""Chunk 3 tests: scratchpad, ideation, retrospectives, emotion, uncertainty."""
from app.modules.m20_general_cognitive_worker.reflection import (
    CreativityMode, EmotionalStateModel, IdeationEngine, RetrospectiveEngine,
    ScratchpadManager, UncertaintyGate,
)


def test_scratchpad_resume_and_render():
    pads = ScratchpadManager()
    pads.add_thought("t1", "first observation")
    pads.add_hypothesis("t1", "users churn because onboarding is slow")
    pads.add_hypothesis("t1", "users churn because onboarding is slow")  # dedupe
    pads.add_hypothesis("t1", "pricing is wrong")
    pads.score_options("t1", [{"option": "A", "score": 3}])
    pad = pads.open("t1")
    assert len(pad.chain_of_thought) == 1
    assert len(pad.hypotheses) == 2
    md = pads.render_markdown("t1")
    assert "## Hypotheses" in md and "pricing is wrong" in md
    assert pads.open("t1") is pad  # resumed, not recreated


def test_ideation_diverge_converge_analogy():
    engine = IdeationEngine(seed=3)
    ideas = engine.diverge("reduce textbook costs", count=12)
    assert len(ideas) == 12
    assert any("invert" in i.text for i in ideas)
    for i, idea in enumerate(ideas):
        if i < 3:
            idea.metadata["feasible"] = True
    ranked = engine.converge(ideas, {"feasible": 1.0})
    assert ranked[0].metadata.get("feasible") is True
    analogies = engine.forced_analogy("reduce textbook costs", ["ant colonies", "libraries"])
    assert len(analogies) == 2 and "ant colonies" in analogies[0].text


def test_retrospective_learning_loop():
    engine = RetrospectiveEngine()
    engine.write("t1", went_well=["early user interviews shaped the pitch"],
                 went_poorly=["skipped competitive pricing check"],
                 lessons=["always price-check competitors before pitching"])
    engine.write("t2", went_well=["deployed on time"], went_poorly=["no monitoring"],
                 lessons=["add monitoring before launch"])
    hits = engine.lessons_for("preparing a sales pitch for a new product")
    assert hits
    assert any("price-check" in " ".join(r.lessons) or "interviews" in " ".join(r.went_well)
               for r, _ in hits[:1])


def test_emotional_state_biases_tone_only_and_overridable():
    model = EmotionalStateModel()
    assert model.tone_bias() == "neutral"
    for _ in range(3):
        model.record_outcome(False)
    assert model.tone_bias() == "more formal and careful"
    model.record_feedback(True)
    model.record_outcome(True)
    model.override("playful")
    assert model.tone_bias() == "playful"
    model.clear_override()
    assert model.tone_bias() != "playful"
    for _ in range(8):
        model.record_outcome(True)
    assert model.tone_bias() == "warm and direct"
    assert -1.0 <= model.state.valence <= 1.0


def test_uncertainty_gate():
    gate = UncertaintyGate()
    confident = gate.assess(0.9, rationale="strong sources")
    assert confident.targeted_questions == []
    low = gate.assess(0.4, gaps=["which semester the course runs"])
    assert low.targeted_questions == ["Can you confirm: which semester the course runs?"]
    assert gate.must_ask(low)
    fallback = gate.assess(0.3)
    assert fallback.targeted_questions  # asks even without named gaps
    high_stakes = gate.assess(0.75, high_stakes=True, gaps=["the exact visa category"])
    assert high_stakes.targeted_questions  # 0.75 < 0.85 high-stakes bar
    safe = gate.assess(0.75, high_stakes=False)
    assert safe.targeted_questions == []  # 0.75 > 0.6 normal bar


def test_creativity_mode_params():
    mode = CreativityMode()
    assert mode.model_params() == {"temperature": 0.7, "noise": 0.0}
    mode.activate()
    assert mode.model_params()["temperature"] > 1.0
    mode.deactivate()
    assert mode.enabled is False
