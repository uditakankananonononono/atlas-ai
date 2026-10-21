"""Row 20 pin: IntuitionEngine.validate reports text comparison only, never verification."""
from __future__ import annotations

from app.modules.m20_general_cognitive_worker.metacognition import IntuitionEngine


def test_row20_intuition_never_claims_verified_validation():
    from app.modules.m20_general_cognitive_worker.schemas import Skill
    engine = IntuitionEngine()
    skill = Skill(name="interview-prep", goal_pattern="prepare for interviews", steps=[])
    gut = engine.gut("how do I prep?", skill_matches=[skill], fact_hits=[])
    agree_result = engine.validate(gut, lambda: "use the interview-prep procedure")
    assert agree_result["validated"] is False
    assert agree_result["status"] == "text_comparison_only"
    gut2 = engine.gut("novel question", skill_matches=[], fact_hits=[])
    disagree_result = engine.validate(gut2, lambda: "deliberate answer")
    assert disagree_result["validated"] is False
    assert disagree_result["status"] == "text_comparison_only"
