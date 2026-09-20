from uuid import uuid4
import pytest
from app.modules.m17_advice_essay.schemas import TrustWellbeingCoachingRequest, TrustWellbeingSkill
from app.modules.m17_advice_essay.trust_wellbeing_coaching import ROW_BY_SKILL, TrustWellbeingCoach

EXPECTED={771:"trust_building",772:"psychological_safety",773:"inclusion",774:"diversity",775:"equity",776:"justice",777:"ethics",778:"integrity",779:"honesty",780:"transparency",781:"accountability",782:"reliability",783:"dependability",784:"consistency",785:"patience",786:"tolerance",787:"forgiveness",788:"gratitude",789:"humility",790:"curiosity",791:"open_mindedness",792:"intellectual_humility",793:"wisdom",794:"prudence",795:"temperance",796:"courage",797:"resilience",798:"grit",799:"self_control",800:"delayed_gratification",801:"impulse_control",802:"emotional_regulation",803:"stress_management",804:"coping_strategies",805:"mindfulness",806:"meditation",807:"relaxation",808:"sleep_hygiene",809:"exercise"}

@pytest.mark.parametrize(("row","name"),EXPECTED.items(),ids=[f"row-{r}" for r in EXPECTED])
def test_rows_771_809_are_review_only_nonclinical_coaching(row,name):
 skill=TrustWellbeingSkill(name); assert ROW_BY_SKILL[skill]==row
 result=TrustWellbeingCoach().coach(TrustWellbeingCoachingRequest(owner_id=uuid4(),skill=skill,context="Personal reflection",goal="Choose one safe step"))
 assert result.review_required is True and result.external_action_proposed is False
 assert result.reflection_questions and result.low_risk_steps
 joined=" ".join(result.safeguards).lower()
 assert "does not diagnose" in joined and "no identity, emotion" in joined
 assert "not emergency or crisis support" in result.escalation_boundary.lower()
 assert "immediate danger" in result.escalation_boundary.lower()
 assert "persistent or worsening" in result.escalation_boundary.lower()

@pytest.mark.parametrize("skill",list(TrustWellbeingSkill)[26:])
def test_rows_797_809_include_stop_and_professional_support_boundary(skill):
 result=TrustWellbeingCoach().coach(TrustWellbeingCoachingRequest(owner_id=uuid4(),skill=skill,context="Wellbeing",goal="Low-risk support"))
 assert any("stop any practice" in x.lower() for x in result.safeguards)
 assert "licensed clinician" in result.escalation_boundary

def test_forgiveness_and_tolerance_never_require_reconciliation_or_harm():
 for skill in (TrustWellbeingSkill.FORGIVENESS,TrustWellbeingSkill.TOLERANCE):
  result=TrustWellbeingCoach().coach(TrustWellbeingCoachingRequest(owner_id=uuid4(),skill=skill,context="Conflict",goal="Reflect safely"))
  assert any("not required" in x.lower() and "harm" in x.lower() for x in result.safeguards)

def test_student_authorship_is_preserved():
 result=TrustWellbeingCoach().coach(TrustWellbeingCoachingRequest(owner_id=uuid4(),skill=TrustWellbeingSkill.ETHICS,context="Essay",goal="Reflect",student_authored_work=True))
 assert "your own work" in result.authorship_notice and "no submission-ready text" in result.authorship_notice
