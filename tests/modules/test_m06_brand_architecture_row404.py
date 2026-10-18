"""Row 404 brand architecture: deterministic structure with honesty guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m06_social_media_manager.marketing_computations import compute

SLUG = "brand-architecture"


def build(facts=None):
    return compute(SLUG, {"facts": facts or {}})


def test_infers_branded_house_from_single_root():
    out = build({"entities": [
        {"name": "Acme"},
        {"name": "Acme Tools", "parent": "Acme"},
        {"name": "Acme Cloud", "parent": "Acme"},
    ]})
    assert out["structure"] == "branded-house"
    assert "single root" in out["structure_basis"]


def test_infers_house_of_brands_when_no_parents():
    out = build({"entities": ["Acme", "Beta", "Gamma"]})
    assert out["structure"] == "house-of-brands"
    assert "no provided parent links" in out["structure_basis"]


def test_infers_hybrid_when_mixed():
    out = build({"entities": [
        {"name": "Acme"},
        {"name": "Acme Tools", "parent": "Acme"},
        {"name": "Standalone"},
    ]})
    assert out["structure"] == "hybrid"


def test_caller_structure_wins_and_is_validated():
    out = build({"structure": "hybrid", "entities": ["A", "B"]})
    assert out["structure"] == "hybrid"
    assert out["structure_basis"] == "caller-provided"
    import pytest

    with pytest.raises(ValueError):
        build({"structure": "empire", "entities": ["A"]})


def test_pairwise_relationships_cover_every_pair():
    out = build({"entities": [
        {"name": "Acme"},
        {"name": "Tools", "parent": "Acme"},
        {"name": "Cloud", "parent": "Acme"},
        {"name": "Standalone"},
    ]})
    rels = {(r["a"], r["b"]): r["relationship"] for r in out["relationships"]}
    assert len(rels) == 6  # all pairs of 4 entities
    assert rels[("Acme", "Tools")] == "parent-child"
    assert rels[("Tools", "Cloud")] == "siblings"
    assert rels[("Acme", "Standalone")] == "separate-houses"
    assert rels[("Tools", "Standalone")] == "separate-houses"


def test_dangling_parent_flagged_not_repaired():
    out = build({"entities": [{"name": "Tools", "parent": "Ghost"}]})
    assert any("Ghost" in i for i in out["issues"])
    assert out["entities"][0]["parent"] == "Ghost"  # left as-is


def test_cycle_flagged():
    out = build({"entities": [
        {"name": "A", "parent": "B"},
        {"name": "B", "parent": "A"},
    ]})
    assert any("cycle" in i for i in out["issues"])


def test_no_entities_means_empty_and_noted():
    out = build({})
    assert out["entities"] == []
    assert out["relationships"] == []
    assert any("nothing to organize" in n for n in out["notes"])


def test_never_invents_entities():
    out = build({"entities": ["Solo"]})
    assert [e["name"] for e in out["entities"]] == ["Solo"]
    assert out["relationships"] == []


def test_deterministic_deduped_and_spec_sections():
    facts = {"entities": ["Acme", "acme", {"name": "Tools", "parent": "Acme"}]}
    a = build(facts)
    assert a == build(dict(facts))
    assert [e["name"] for e in a["entities"]] == ["Acme", "Tools"]
    for key in ("structure", "entities", "relationships", "migration_notes"):
        assert key in a


def test_invalid_entities_rejected():
    import pytest

    with pytest.raises(ValueError):
        build({"entities": [42]})
    with pytest.raises(ValueError):
        build({"entities": [{"parent": "X"}]})
