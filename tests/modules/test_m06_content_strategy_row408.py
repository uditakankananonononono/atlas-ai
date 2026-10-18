"""Row 408 content strategy: deterministic structure with honesty guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m06_social_media_manager.marketing_computations import compute

SLUG = "content-strategy"


def build(facts=None):
    return compute(SLUG, {"facts": facts or {}})


def test_pillars_capped_and_basis_marked():
    out = build({"pillars": [f"p{i}" for i in range(8)]})
    assert len(out["pillars"]) == 5
    assert all(p["basis"] == "caller-provided" for p in out["pillars"])
    out2 = build({"topics": ["a", "b", "c"]})
    assert all(p["basis"] == "derived from provided topics" for p in out2["pillars"])


def test_formats_per_pillar_only_from_provided_pieces():
    out = build({
        "pillars": ["security", "pricing"],
        "content": [
            {"topic": "security", "format": "guide"},
            {"topic": "security", "format": "webinar"},
            {"topic": "security", "format": "guide"},
            {"topic": "other", "format": "meme"},
        ],
    })
    by = {p["pillar"]: p for p in out["pillars"]}
    assert by["security"]["formats"] == ["guide", "webinar"]
    assert "format_gap" not in by["security"]
    assert by["pricing"]["formats"] == []
    assert by["pricing"]["format_gap"] is True
    assert by["pricing"]["format_slot"].startswith("TO BE PROVIDED")
    assert "meme" not in by["security"]["formats"]


def test_measurement_lists_only_available_metrics():
    out = build({
        "pillars": ["security"],
        "analytics": {"mau": 400},
        "content": [{"topic": "security", "impressions": 100, "engagements": 5}],
    })
    m = out["measurement"]
    assert m["available_metrics"] == ["mau", "impressions", "engagements"]
    assert m["observed"]["impressions"] == 100.0
    assert m["observed"]["engagement_rate"] == 0.05
    assert m["measurement_gaps"] == []


def test_no_metrics_means_honest_gap():
    out = build({"pillars": ["security"]})
    m = out["measurement"]
    assert m["available_metrics"] == []
    assert m["observed"]["impressions"] is None
    assert m["observed"]["engagement_rate"] is None
    assert m["measurement_gaps"]


def test_cadence_provided_wins_else_disclosed_default():
    out = build({"pillars": ["a"], "cadence": {"per_week": 5}})
    assert out["cadence"]["plan"] == {"per_week": 5}
    assert out["cadence"]["basis"] == "caller-provided"
    out2 = build({"pillars": ["a"]})
    assert out2["cadence"]["basis"] == "engine default, not audience data"
    out3 = build({})
    assert out3["cadence"]["plan"] is None


def test_empty_when_nothing_provided():
    out = build({})
    assert out["pillars"] == []
    assert any("nothing to structure" in n for n in out["notes"])


def test_fewer_than_three_pillars_noted():
    out = build({"pillars": ["only one"]})
    assert any("fewer than 3 pillars" in n for n in out["notes"])


def test_deterministic_deduped_and_spec_sections():
    facts = {"pillars": ["Security", "security ", "Pricing"]}
    a = build(facts)
    assert a == build(dict(facts))
    assert [p["pillar"] for p in a["pillars"]] == ["Security", "Pricing"]
    for key in ("pillars", "formats", "cadence", "measurement"):
        assert key in a


def test_invalid_inputs_rejected():
    import pytest

    with pytest.raises(ValueError):
        build({"pillars": [42]})
    with pytest.raises(ValueError):
        build({"content": ["not-a-mapping"]})
    with pytest.raises(ValueError):
        build({"analytics": ["not-a-mapping"]})
