"""Row 418 media relations: deterministic pitches with honesty guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m06_social_media_manager.marketing_computations import compute

SLUG = "media-relations"

STORY = {
    "headline": "Schools cut admin time 40% with open-source tooling",
    "summary": "A district-wide rollout of open-source admin tooling.",
    "key_points": ["400 schools live", "40% admin time reduction"],
    "why_now": "New funding round for district digitization closes next month",
    "assets": ["interview with the district CTO", "rollout dataset"],
}


def build(contacts=None, facts=None):
    payload = {"facts": STORY if facts is None else facts}
    if contacts is not None:
        payload["contacts"] = contacts
    return compute(SLUG, payload)


def test_no_contacts_means_empty_and_honest_note():
    out = build([], facts={})
    assert out["targets"] == []
    assert out["pitches"] == []
    assert out["target_count"] == 0
    assert "never invents" in out["targets_note"]


def test_targets_carry_only_provided_fields():
    out = build([{"name": "Asha Rao", "outlet": "EdTech Weekly",
                  "beat": "schools technology", "email": "asha@example.com"}])
    t = out["targets"][0]
    assert t == {"name": "Asha Rao", "outlet": "EdTech Weekly",
                 "beat": "schools technology"}
    assert out["pitches"][0]["email"] == "asha@example.com"

    out2 = build(["Asha Rao"])
    assert out2["targets"][0]["outlet"] is None
    assert out2["targets"][0]["beat"] is None
    assert out2["pitches"][0]["email"] is None


def test_fit_basis_is_disclosed_keyword_overlap():
    out = build([{"name": "Asha Rao", "beat": "schools admin technology"}])
    fit = out["pitches"][0]["fit_basis"]
    assert fit.startswith("keyword overlap with provided beat:")
    assert "schools" in fit


def test_no_overlap_is_stated_honestly():
    out = build([{"name": "Asha Rao", "beat": "celebrity gossip"}])
    assert "no token overlap" in out["pitches"][0]["fit_basis"]
    out2 = build(["Asha Rao"])
    assert "no story-beat overlap" in out2["pitches"][0]["fit_basis"]


def test_pitches_are_unsent_drafts_with_explicit_slots():
    out = build(["Asha Rao"], facts={"headline": "Only a headline"})
    pitch = out["pitches"][0]
    assert pitch["status"] == "draft"
    assert pitch["sent"] is False
    assert "[TO BE PROVIDED:" in pitch["body"]
    for slot in ("summary", "why_now", "key_points", "sender name"):
        assert slot in pitch["requires"]


def test_full_story_leaves_no_story_slots():
    out = build([{"name": "Asha Rao", "outlet": "EdTech Weekly"}])
    pitch = out["pitches"][0]
    assert "[TO BE PROVIDED: story headline]" not in pitch["body"]
    assert "summary" not in pitch["requires"]
    assert "sender name" in pitch["requires"]


def test_follow_up_plan_is_disclosed_default():
    plan = build(["Asha Rao"])["follow_up_plan"]
    assert plan["stop_on_decline"] is True
    assert plan["stop_on_response"] is True
    assert "engine defaults" in plan["basis"]


def test_deterministic_and_deduped():
    contacts = ["Asha Rao", "asha rao", "Asha  Rao"]
    a = build(contacts)
    b = build(list(reversed(contacts)))
    assert a == b  # dedupe keeps first occurrence's surface form
    assert a["target_count"] == 1


def test_output_covers_spec_sections():
    out = build(["Asha Rao"])
    for key in ("targets", "pitches", "follow_up_plan"):
        assert key in out


def test_invalid_contact_rejected():
    import pytest

    with pytest.raises(ValueError):
        build([42])
    with pytest.raises(ValueError):
        build([{"outlet": "no-name Weekly"}])
    with pytest.raises(ValueError):
        build(["  "])
