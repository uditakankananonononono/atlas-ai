"""Row 412 link building: deterministic outreach with honesty guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m06_social_media_manager.marketing_computations import compute

SLUG = "link-building"


def build(contacts=None, facts=None):
    payload = {"facts": facts or {}}
    if contacts is not None:
        payload["contacts"] = contacts
    return compute(SLUG, payload)


def test_no_prospects_means_empty_everything_and_honest_note():
    out = build()
    assert out["targets"] == []
    assert out["angles"] == []
    assert out["outreach_drafts"] == []
    assert out["prospect_count"] == 0
    assert "never invents" in out["targets_note"]


def test_bare_string_prospect_gets_generic_angle_honestly():
    out = build(["Jane at Qxyzz"])
    angle = out["angles"][0]
    assert angle["angle_type"] == "value-first introduction"
    assert angle["basis"] == "no rule matched"
    assert angle["value_exchange"] == "TO BE PROVIDED"


def test_keyword_rule_table_picks_angle_from_provided_text():
    contacts = [
        {"name": "Sam", "site": "devblog.io", "topic": "guest post guidelines"},
        {"name": "Pat", "site": "resources.example", "topic": "resource links page"},
        {"name": "Kim", "notes": "runs a data study"},
        {"name": "Lee", "topic": "broken link on their tools page"},
        {"name": "Jo", "topic": "podcast interviews"},
        {"name": "Rey", "topic": "product reviews and comparisons"},
    ]
    out = build(contacts)
    types = {a["target"]: a["angle_type"] for a in out["angles"]}
    assert types["Sam"] == "guest post"
    assert types["Pat"] == "resource inclusion"
    assert types["Kim"] == "data citation"
    assert types["Lee"] == "broken-link replacement"
    assert types["Jo"] == "podcast guest pitch"
    assert types["Rey"] == "expert review contribution"
    for a in out["angles"]:
        assert a["basis"].startswith("matched keyword")


def test_provided_fields_carried_and_missing_fields_null():
    out = build([{"name": "Jane", "site": "devblog.io", "authority": 51,
                  "email": "jane@devblog.io"}])
    target = out["targets"][0]
    assert target["authority"] == 51
    assert target["site"] == "devblog.io"
    draft = out["outreach_drafts"][0]
    assert draft["email"] == "jane@devblog.io"  # caller-provided only

    out2 = build(["Jane"])
    assert out2["targets"][0]["authority"] is None
    assert out2["targets"][0]["site"] is None
    assert out2["outreach_drafts"][0]["email"] is None


def test_drafts_are_unsent_templates_with_explicit_slots():
    out = build([{"name": "Jane", "topic": "guest posts"}])
    draft = out["outreach_drafts"][0]
    assert draft["status"] == "draft"
    assert draft["sent"] is False
    assert "[TO BE PROVIDED:" in draft["body"]
    assert "sender name" in draft["requires"]
    assert "link or asset to share" in draft["requires"]
    assert "their site/page" in draft["requires"]  # not provided


def test_draft_uses_only_provided_facts():
    out = build([{"name": "Jane", "site": "devblog.io", "topic": "guest posts"}])
    body = out["outreach_drafts"][0]["body"]
    assert "devblog.io" in body
    assert "their site/page" not in out["outreach_drafts"][0]["requires"]


def test_follow_up_plan_disclosed_as_engine_default():
    plan = build(["Jane"])["follow_up_plan"]
    assert plan["stop_on_decline"] is True
    assert "engine defaults" in plan["basis"]


def test_deterministic_and_deduped():
    contacts = ["Jane at Qxyzz", "jane at qxyzz", "Jane  at  Qxyzz"]
    a = build(contacts)
    b = build(list(contacts))
    assert a == b
    assert a["prospect_count"] == 1


def test_output_covers_spec_sections():
    out = build(["Jane"])
    for key in ("targets", "angles", "outreach_drafts"):
        assert key in out


def test_invalid_prospect_rejected():
    import pytest

    with pytest.raises(ValueError):
        build([42])
    with pytest.raises(ValueError):
        build([{"site": "no-name.example"}])
    with pytest.raises(ValueError):
        build([""])


def test_empty_site_slot_is_listed_in_requires():
    for site in (None, "", False, 0):
        draft = build([{"name": "Jane", "site": site}])["outreach_drafts"][0]
        assert "[TO BE PROVIDED: their site/page]" in draft["body"]
        assert "their site/page" in draft["requires"]
