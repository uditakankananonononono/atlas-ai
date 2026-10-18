"""Row 406 messaging framework: deterministic structure with honesty guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m06_social_media_manager.marketing_computations import compute

SLUG = "messaging-framework"


def build(facts=None):
    return compute(SLUG, {"facts": facts or {}})


def test_caller_core_message_wins():
    out = build({"core_message": "We make payroll boring",
                 "pillars": ["fast", "accurate", "cheap"]})
    assert out["core_message"] == "We make payroll boring"
    assert out["core_message_basis"] == "caller-provided"


def test_core_message_derived_with_slots_for_missing_facts():
    out = build({"product": "PayFlow", "pillars": ["a", "b", "c"]})
    assert out["core_message_basis"] == "derived from disclosed template"
    assert "PayFlow" in out["core_message"]
    assert "[TO BE PROVIDED: audience]" in out["core_message"]
    assert "[TO BE PROVIDED: primary benefit]" in out["core_message"]
    out2 = build({"pillars": ["a", "b", "c"]})
    assert out2["core_message"] == "TO BE PROVIDED"


def test_pillars_derived_from_benefits_and_capped():
    out = build({"benefits": [f"benefit {i}" for i in range(7)]})
    assert len(out["pillars"]) == 4
    assert all(p["basis"] == "derived from provided benefits" for p in out["pillars"])


def test_caller_pillars_preserved_with_proof():
    out = build({"pillars": [
        {"name": "Fast onboarding",
         "proof_points": ["live in 3 days in pilot"]},
        "Accurate filings",
    ]})
    assert out["pillars"][0]["proof_points"] == ["live in 3 days in pilot"]
    assert "proof_gap" not in out["pillars"][0]
    assert out["pillars"][1]["proof_gap"] is True
    assert out["pillars"][1]["proof_slot"].startswith("TO BE PROVIDED")


def test_no_fabricated_proof_anywhere():
    out = build({"pillars": ["a", "b", "c"]})
    assert out["proof_points"] == []
    assert all(p["proof_gap"] for p in out["pillars"])
    assert out["proof_coverage"] == 0.0


def test_unassigned_proof_points_are_not_misattributed():
    out = build({"pillars": ["a", "b"],
                 "proof_points": ["some provided proof"]})
    assert out["proof_points"] == ["some provided proof"]
    for p in out["pillars"]:
        assert p["proof_points"] == []
        assert p["proof_gap"] is True
        assert "unassigned" in p["proof_slot"]


def test_audience_variants_only_for_provided_segments():
    out = build({"core_message": "We make payroll boring",
                 "pillars": ["a"],
                 "audience_segments": ["Schools", "schools", "Clinics"]})
    variants = out["audience_variants"]
    assert [v["segment"] for v in variants] == ["Schools", "Clinics"]
    assert variants[0]["variant"] == "We make payroll boring - for Schools"
    assert variants[0]["basis"] == "derived from disclosed template"


def test_caller_provided_variant_wins():
    out = build({"pillars": ["a"],
                 "audience_segments": ["Schools"],
                 "audience_variants": [{"segment": "Schools",
                                        "variant": "Boring payroll for schools"}]})
    assert out["audience_variants"][0]["variant"] == "Boring payroll for schools"
    assert out["audience_variants"][0]["basis"] == "caller-provided"


def test_no_pillars_or_benefits_is_noted():
    out = build({})
    assert out["pillars"] == []
    assert any("no pillars or benefits" in n for n in out["notes"])


def test_deterministic_and_spec_sections():
    facts = {"pillars": ["a", "b", "c"], "audience_segments": ["Schools"]}
    assert build(facts) == build(dict(facts))
    out = build(facts)
    for key in ("core_message", "pillars", "proof_points", "audience_variants"):
        assert key in out


def test_invalid_inputs_rejected():
    import pytest

    with pytest.raises(ValueError):
        build({"pillars": [42]})
    with pytest.raises(ValueError):
        build({"benefits": ["  "]})
