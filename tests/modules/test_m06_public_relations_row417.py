"""Row 417 public relations: deterministic drafts with honesty guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m06_social_media_manager.marketing_computations import compute

SLUG = "public-relations"


def build(facts=None):
    return compute(SLUG, {"facts": facts or {}})


def test_caller_narrative_wins():
    out = build({"narrative": "  Our story  "})
    assert out["narrative"] == "Our story"
    assert out["narrative_basis"] == "caller-provided"


def test_narrative_derived_or_placeholder():
    out = build({"headline": "Funding round", "why_it_matters": "jobs"})
    assert out["narrative"] == "Funding round - jobs"
    assert out["narrative_basis"].startswith("derived")
    assert build({})["narrative"] == "TO BE PROVIDED"


def test_press_release_is_always_unpublished_draft():
    out = build({"headline": "H", "body": "B", "quote": "Q",
                 "quote_source": "CEO", "contact": "pr@example.com"})
    pr = out["press_release_draft"]
    assert pr["status"] == "draft"
    assert pr["review_required"] is True
    assert pr["published"] is False
    assert pr["body"].startswith("DRAFT - FOR REVIEW ONLY")
    assert "pr@example.com" in pr["body"]
    assert pr["requires"] == ["sender/legal review"]


def test_missing_facts_become_explicit_slots():
    out = build({"headline": "Only headline"})
    pr = out["press_release_draft"]
    assert "[TO BE PROVIDED: quote]" in pr["body"]
    assert "[TO BE PROVIDED: contact]" in pr["body"]
    for key in ("quote", "quote_source", "contact", "body"):
        assert key in pr["requires"]


def test_no_invented_milestone_dates_or_channels():
    out = build({"milestones": [{"name": "Launch"}, "Teaser"]})
    for m in out["announcement_plan"]:
        assert m["date"] == "TO BE PROVIDED: date"
        assert m["channel"] == "TO BE PROVIDED: channel"
        assert m["status"] == "planned"


def test_milestones_sorted_by_provided_date_then_input_order():
    out = build({"milestones": [
        {"name": "B", "date": "2026-03-01"},
        {"name": "A"},
        {"name": "C", "date": "2026-01-15"},
    ]})
    assert [m["name"] for m in out["announcement_plan"]] == ["C", "B", "A"]


def test_risk_notes_combine_provided_and_disclosed_checklist():
    out = build({"risks": ["unconfirmed partner quote"]})
    rn = out["risk_notes"]
    assert rn["caller_provided"] == ["unconfirmed partner quote"]
    assert len(rn["review_checklist"]) == 3
    assert "not an assertion" in rn["checklist_basis"]


def test_readiness_from_provided_inputs_only():
    assert build({})["readiness"] == 0.0
    assert build({"headline": "H", "quote": "Q", "body": "B",
                  "contact": "C"})["readiness"] == 1.0


def test_deterministic_and_spec_sections():
    facts = {"headline": "H", "milestones": [{"name": "M", "date": "2026-01-01"}]}
    assert build(facts) == build(dict(facts))
    out = build(facts)
    for key in ("narrative", "announcement_plan", "press_release_draft", "risk_notes"):
        assert key in out


def test_invalid_milestones_rejected():
    import pytest

    with pytest.raises(ValueError):
        build({"milestones": [42]})
    with pytest.raises(ValueError):
        build({"milestones": [{"date": "no name"}]})
