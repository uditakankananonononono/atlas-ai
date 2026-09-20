from uuid import uuid4

import pytest

from app.modules.m17_advice_essay.communication_coaching import ROW_BY_SKILL, CommunicationCoach
from app.modules.m17_advice_essay.schemas import CommunicationCoachingRequest, CommunicationSkill


EXPECTED_ROWS = {
    710: "persuasive_writing", 711: "negotiation_tactics", 712: "conflict_resolution",
    713: "mediation", 714: "active_listening", 715: "empathetic_response",
    716: "emotional_intelligence", 717: "social_calibration", 718: "cultural_sensitivity",
    719: "cross_cultural_communication", 720: "diplomatic_language", 721: "assertiveness",
    722: "boundary_setting", 723: "difficult_conversations", 724: "feedback_delivery",
    725: "feedback_reception", 726: "public_speaking", 727: "presentation_design",
    728: "storytelling", 729: "rapport_building", 730: "networking", 731: "mentorship",
    732: "coaching", 733: "teaching", 734: "explaining_complex_ideas", 735: "analogies",
    736: "metaphors", 737: "examples", 738: "scaffolding", 739: "questioning",
    740: "socratic_method",
}


@pytest.mark.parametrize(("row", "skill_name"), EXPECTED_ROWS.items(), ids=lambda value: f"row-{value}" if isinstance(value, int) else value)
def test_rows_710_740_have_typed_ethics_bounded_coaching(row, skill_name):
    skill = CommunicationSkill(skill_name)
    assert ROW_BY_SKILL[skill] == row
    result = CommunicationCoach().coach(CommunicationCoachingRequest(
        owner_id=uuid4(), skill=skill, context="Prepare for a real conversation.",
        goal="Communicate clearly without pressure", audience="A colleague",
        known_facts=["A deadline was missed once"], cultural_context=["Ask preferences; do not infer"],
    ))
    assert result.skill is skill
    assert result.review_required is True
    assert result.external_action_proposed is False
    assert result.questions and result.rehearsal_steps and result.observations
    assert any("not a sent message" in caveat for caveat in result.caveats)


def test_row_710_persuasion_rejects_manipulative_frame_in_guidance():
    result = CommunicationCoach().coach(CommunicationCoachingRequest(
        owner_id=uuid4(), skill=CommunicationSkill.PERSUASIVE_WRITING,
        context="Convince someone", goal="Gain agreement", audience="A reader",
        draft="Obviously, you must agree. Everyone knows this.",
    ))
    joined = " ".join(result.caveats + result.draft_feedback).lower()
    assert "false urgency" in joined
    assert "pressure" in joined


def test_rows_713_718_do_not_diagnose_emotion_culture_or_consent():
    for skill in (CommunicationSkill.MEDIATION, CommunicationSkill.EMPATHETIC_RESPONSE,
                  CommunicationSkill.EMOTIONAL_INTELLIGENCE, CommunicationSkill.CULTURAL_SENSITIVITY):
        result = CommunicationCoach().coach(CommunicationCoachingRequest(
            owner_id=uuid4(), skill=skill, context="Ambiguous interaction",
            goal="Understand", audience="Another person",
        ))
        assert any("hypotheses" in caveat for caveat in result.caveats)


def test_student_authored_boundary_survives_story_and_teaching_workflows():
    for skill in (CommunicationSkill.STORYTELLING, CommunicationSkill.SOCRATIC_METHOD):
        result = CommunicationCoach().coach(CommunicationCoachingRequest(
            owner_id=uuid4(), skill=skill, context="College essay revision",
            goal="Improve reasoning", audience="Admissions reader", student_authored_work=True,
        ))
        assert "revise your own words" in result.authorship_notice
        assert "No submission-ready response" in result.authorship_notice


def test_boundary_setting_feedback_is_assertive_without_assigning_motive():
    result = CommunicationCoach().coach(CommunicationCoachingRequest(
        owner_id=uuid4(), skill=CommunicationSkill.BOUNDARY_SETTING,
        context="Repeated requests", goal="Protect study time", audience="Peer",
        draft="You never care about my work.",
    ))
    assert any("absolute wording" in item for item in result.draft_feedback)
    assert any("I-statement" in item for item in result.draft_feedback)
