"""Row 420 social strategy: deterministic roles/KPIs with honesty guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m06_social_media_manager.marketing_computations import compute

SLUG = "social-media-strategy"


def build(facts=None):
    return compute(SLUG, {"facts": facts or {}})


def test_archetype_roles_with_disclosed_basis():
    out = build({"channels": ["LinkedIn", "TikTok"]})
    roles = {r["platform"]: r for r in out["platform_roles"]}
    assert "B2B authority" in roles["LinkedIn"]["role"]
    assert "short-form discovery" in roles["TikTok"]["role"]
    assert all(r["basis"].startswith("disclosed archetype")
               for r in roles.values())


def test_caller_role_wins():
    out = build({"channels": [{"name": "LinkedIn", "role": " recruiting only "}]})
    role = out["platform_roles"][0]
    assert role["role"] == "recruiting only"
    assert role["basis"] == "caller-provided"


def test_unknown_platform_gets_honest_slot():
    out = build({"channels": ["QxyzzNet"]})
    role = out["platform_roles"][0]
    assert role["role"].startswith("TO BE PROVIDED")
    assert role["role_gap"] is True
    assert role["basis"].startswith("no archetype")


def test_kpi_measurable_lists_and_observed_from_provided_only():
    out = build({"channels": ["LinkedIn", "QxyzzNet"],
                 "impressions": 1000, "engagements": 40})
    kpis = out["kpis"]
    assert kpis["measurable_per_platform"]["LinkedIn"]
    assert kpis["measurable_per_platform"]["QxyzzNet"] == []
    assert kpis["observed"]["engagement_rate"] == 0.04
    assert kpis["observed"]["conversion_rate"] is None  # not provided


def test_no_observed_numbers_when_nothing_provided():
    out = build({"channels": ["LinkedIn"]})
    assert out["kpis"]["observed"]["engagement_rate"] is None
    assert out["kpis"]["observed"]["conversion_rate"] is None


def test_mix_and_cadence_precedence():
    out = build({"channels": ["LinkedIn"],
                 "content_mix": {"promote": 1.0}, "cadence": {"posts_per_week": 7}})
    assert out["content_mix"]["basis"] == "caller-provided"
    assert out["cadence"]["basis"] == "caller-provided"
    out2 = build({"channels": ["LinkedIn"]})
    assert out2["content_mix"]["basis"] == "engine default, not audience data"
    assert out2["cadence"]["basis"] == "engine default, not audience data"
    out3 = build({})
    assert out3["content_mix"]["mix"] is None
    assert out3["cadence"]["plan"] is None


def test_no_platforms_noted():
    out = build({})
    assert out["platform_roles"] == []
    assert any("no platforms provided" in n for n in out["notes"])


def test_deterministic_deduped_and_spec_sections():
    facts = {"channels": ["LinkedIn", "linkedin ", "TikTok"]}
    a = build(facts)
    assert a == build(dict(facts))
    assert [r["platform"] for r in a["platform_roles"]] == ["LinkedIn", "TikTok"]
    for key in ("platform_roles", "content_mix", "cadence", "kpis"):
        assert key in a


def test_invalid_platforms_rejected():
    import pytest

    with pytest.raises(ValueError):
        build({"channels": [42]})
    with pytest.raises(ValueError):
        build({"channels": [{"role": "no name"}]})
