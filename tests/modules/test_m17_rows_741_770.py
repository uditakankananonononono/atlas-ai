from uuid import uuid4

import pytest

from app.modules.m17_advice_essay.collaboration_coaching import ROW_BY_SKILL, CollaborationCoach
from app.modules.m17_advice_essay.schemas import CollaborationCoachingRequest, CollaborationSkill

EXPECTED = {
 741:"facilitation",742:"brainstorming",743:"consensus_building",744:"voting_design",745:"deliberation",
 746:"debate",747:"rhetoric",748:"logic",749:"fallacy_detection",750:"steelmanning",
 751:"charitable_interpretation",752:"principle_of_charity",753:"steel_manning",754:"devils_advocacy",
 755:"red_teaming",756:"war_gaming",757:"tabletop_exercises",758:"simulation",759:"role_playing",
 760:"perspective_taking",761:"theory_of_mind",762:"mentalizing",763:"empathy",764:"compassion",
 765:"altruism",766:"prosocial_behavior",767:"cooperation",768:"collaboration",769:"teamwork",770:"team_building",
}

@pytest.mark.parametrize(("row","name"), EXPECTED.items(), ids=[f"row-{row}" for row in EXPECTED])
def test_rows_741_770_have_review_only_typed_coaching(row, name):
    skill=CollaborationSkill(name); assert ROW_BY_SKILL[skill]==row
    result=CollaborationCoach().coach(CollaborationCoachingRequest(
        owner_id=uuid4(), skill=skill, context="Group planning", objective="Reach a fair, reasoned next step",
        participants=["Participant A", "Participant B"], known_facts=["Decision is reversible"],
    ))
    assert result.skill is skill
    assert result.review_required is True and result.external_action_proposed is False
    assert result.agenda and result.questions and result.critique and result.safeguards
    assert any("no group message" in item.lower() for item in result.safeguards)

@pytest.mark.parametrize("skill", [CollaborationSkill.THEORY_OF_MIND, CollaborationSkill.MENTALIZING,
 CollaborationSkill.PERSPECTIVE_TAKING, CollaborationSkill.EMPATHY])
def test_rows_760_763_forbid_mind_reading(skill):
    result=CollaborationCoach().coach(CollaborationCoachingRequest(
        owner_id=uuid4(), skill=skill, context="Ambiguous behavior", objective="Prepare a question"))
    joined=" ".join(result.safeguards).lower()
    assert "hypothesis" in joined and "diagnosis" in joined

@pytest.mark.parametrize("skill", [CollaborationSkill.RED_TEAMING, CollaborationSkill.WAR_GAMING,
 CollaborationSkill.TABLETOP_EXERCISES, CollaborationSkill.SIMULATION])
def test_rows_755_758_are_bounded_to_fictional_or_authorized_systems(skill):
    result=CollaborationCoach().coach(CollaborationCoachingRequest(
        owner_id=uuid4(), skill=skill, context="Resilience practice", objective="Identify safe improvements"))
    assert any("explicitly authorized" in item and "real-world effects" in item for item in result.safeguards)

@pytest.mark.parametrize("skill", [CollaborationSkill.RHETORIC, CollaborationSkill.DEBATE])
def test_rows_746_747_forbid_deceptive_or_humiliating_persuasion(skill):
    result=CollaborationCoach().coach(CollaborationCoachingRequest(
        owner_id=uuid4(), skill=skill, context="Discuss proposal", objective="Test claim",
        proposal_or_argument="Obviously everyone knows you must agree."))
    joined=" ".join(result.safeguards+result.critique).lower()
    assert "deception" in joined and "dismissive" in joined

def test_student_authorship_boundary_is_preserved():
    result=CollaborationCoach().coach(CollaborationCoachingRequest(
        owner_id=uuid4(), skill=CollaborationSkill.DEBATE, context="Class assignment",
        objective="Review my reasoning", student_authored_work=True))
    assert "revise your own work" in result.authorship_notice
    assert "no submission-ready argument" in result.authorship_notice
