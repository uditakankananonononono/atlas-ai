"""Row 411 keyword research: deterministic expansion + honesty guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m06_social_media_manager.marketing_computations import compute

SLUG = "keyword-research"


def research(facts=None, metrics=None):
    payload = {"facts": facts or {}}
    if metrics is not None:
        payload["provided_metrics"] = metrics
    return compute(SLUG, payload)


def test_expands_single_seed_into_bounds():
    out = research(facts={"seed_keywords": ["crm software"]})
    kws = out["keywords"]
    assert 15 <= len(kws) <= 30
    assert kws[0]["term"] == "crm software"  # seeds first
    assert any(k["origin"] == "derived" for k in kws)


def test_caps_at_thirty_terms():
    out = research(facts={"seed_keywords": ["crm", "erp", "helpdesk", "billing"]})
    assert len(out["keywords"]) == 30


def test_derived_intent_comes_from_modifier_template():
    out = research(facts={"seed_keywords": ["crm software"]})
    by_term = {k["term"]: k for k in out["keywords"]}
    assert by_term["how to crm software"]["intent"] == "informational"
    assert by_term["best crm software"]["intent"] == "commercial"
    assert by_term["buy crm software"]["intent"] == "transactional"
    assert by_term["crm software login"]["intent"] == "navigational"
    assert out["intent_map"]["buy crm software"] == "transactional"
    for k in out["keywords"]:
        if k["origin"] == "derived":
            assert "template" in k["intent_basis"]


def test_seed_intent_rules():
    out = research(
        facts={"seed_keywords": ["best crm", "crm login", "how to reset password",
                                 "crm discount code", "qxyzz"]},
        metrics={"qxyzz": {"intent": "commercial"}},
    )
    by_term = {k["term"]: k for k in out["keywords"]}
    assert by_term["best crm"]["intent"] == "commercial"
    assert by_term["crm login"]["intent"] == "navigational"
    assert by_term["how to reset password"]["intent"] == "informational"
    assert by_term["crm discount code"]["intent"] == "transactional"
    assert by_term["qxyzz"]["intent"] == "commercial"  # caller-provided wins
    assert by_term["qxyzz"]["intent_basis"] == "caller-provided"


def test_unmatched_seed_is_honestly_unclassified():
    out = research(facts={"seed_keywords": ["qxyzz"]})
    seed = out["keywords"][0]
    assert seed["intent"] == "unclassified"
    assert seed["intent_basis"] == "no rule matched"


def test_no_fabricated_metrics_on_any_term():
    out = research(facts={"seed_keywords": ["crm software"]})
    for k in out["keywords"]:
        assert k["volume"] is None
        assert k["difficulty"] is None
        assert k["cpc"] is None


def test_provided_metrics_attach_to_exact_terms_only():
    metrics = {
        "crm software": {"volume": 1200, "difficulty": 35, "cpc": 4.5},
        "buy crm software": {"volume": 90, "difficulty": 50},
    }
    out = research(facts={"seed_keywords": ["crm software"]}, metrics=metrics)
    by_term = {k["term"]: k for k in out["keywords"]}
    assert by_term["crm software"]["volume"] == 1200
    assert by_term["crm software"]["cpc"] == 4.5
    # a derived term the caller happened to measure keeps its provided metrics
    assert by_term["buy crm software"]["volume"] == 90
    # unmeasured derived terms stay null
    assert by_term["how to crm software"]["volume"] is None


def test_quick_wins_require_provided_volume_and_low_provided_difficulty():
    metrics = {
        "crm software": {"volume": 1200, "difficulty": 20},
        "erp software": {"volume": 800, "difficulty": 75},
        "helpdesk tool": {"difficulty": 10},
        "billing app": {"volume": 500},
    }
    out = research(facts={"seed_keywords": list(metrics)}, metrics=metrics)
    assert out["quick_wins"] == ["crm software"]
    assert "engine default" in out["quick_win_rule"]


def test_deterministic_and_deduped():
    facts = {"seed_keywords": ["crm  software", "CRM Software", "crm software"]}
    a = research(facts=facts)
    b = research(facts=facts)
    assert a == b
    seeds = [k["term"] for k in a["keywords"] if k["origin"] == "seed"]
    assert seeds == ["crm software"]
    assert len({k["term"].lower() for k in a["keywords"]}) == len(a["keywords"])


def test_placeholder_when_no_seeds_and_no_expansion():
    out = research(facts={"users": "400 schools"})
    assert len(out["keywords"]) == 1
    assert out["keywords"][0]["term"] == "TO BE PROVIDED"
    assert out["keywords"][0]["volume"] is None
    assert out["quick_wins"] == []
    terms = [k["term"] for k in out["keywords"]]
    assert not any("TO BE PROVIDED" in t and t != "TO BE PROVIDED" for t in terms)


def test_metrics_keys_serve_as_seed_fallback():
    out = research(metrics={"beta testing tools": {"volume": 1200}})
    assert out["keywords"][0]["term"] == "beta testing tools"
    assert out["keywords"][0]["volume"] == 1200


def test_non_string_seed_rejected():
    import pytest

    with pytest.raises(ValueError):
        research(facts={"seed_keywords": [42]})
