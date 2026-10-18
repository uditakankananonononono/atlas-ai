"""Row 403 positioning: deterministic statement with honesty guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m06_social_media_manager.marketing_computations import compute

SLUG = "positioning"


def build(facts=None):
    return compute(SLUG, {"facts": facts or {}})


def test_caller_statement_wins():
    out = build({"statement": "  The calm payroll company  "})
    assert out["statement"] == "The calm payroll company"
    assert out["statement_basis"] == "caller-provided"


def test_statement_derived_from_disclosed_template():
    out = build({"audience": "school districts", "brand": "PayFlow",
                 "category": "payroll tool", "benefit": "runs itself",
                 "reason": "it reconciles automatically"})
    assert out["statement"] == (
        "For school districts, PayFlow is the payroll tool that runs "
        "itself because it reconciles automatically"
    )
    assert out["statement_basis"] == "derived from disclosed spec template"


def test_missing_fields_become_explicit_slots():
    out = build({"brand": "PayFlow", "category": "payroll tool"})
    assert "[TO BE PROVIDED: audience]" in out["statement"]
    assert "[TO BE PROVIDED: benefit]" in out["statement"]
    assert "[TO BE PROVIDED: reason]" in out["statement"]


def test_no_inputs_means_placeholder():
    out = build({})
    assert out["statement"] == "TO BE PROVIDED"
    assert out["category"] == "TO BE PROVIDED"


def test_only_grounded_claims_become_differentiators():
    out = build({"claims": [
        {"claim": "Fastest onboarding", "evidence": "3-day median in pilot"},
        {"claim": "Most accurate"},
        "Just a bare claim",
    ]})
    assert out["differentiators"] == [
        {"claim": "Fastest onboarding", "evidence": "3-day median in pilot"}
    ]
    assert out["reasons_to_believe"] == ["3-day median in pilot"]
    assert out["ungrounded_claims"] == ["Most accurate", "Just a bare claim"]
    assert any("lacked provided evidence" in n for n in out["notes"])


def test_no_fabricated_differentiators():
    out = build({"claims": [{"claim": "A"}, {"claim": "B"}]})
    assert out["differentiators"] == []
    assert out["reasons_to_believe"] == []
    assert out["ungrounded_claims"] == ["A", "B"]


def test_deterministic_and_spec_sections():
    facts = {"brand": "PayFlow", "claims": [{"claim": "A", "evidence": "E"}]}
    assert build(facts) == build(dict(facts))
    out = build(facts)
    for key in ("statement", "category", "differentiators", "reasons_to_believe"):
        assert key in out


def test_invalid_claims_rejected():
    import pytest

    with pytest.raises(ValueError):
        build({"claims": [42]})
    with pytest.raises(ValueError):
        build({"claims": [{"evidence": "no claim"}]})
