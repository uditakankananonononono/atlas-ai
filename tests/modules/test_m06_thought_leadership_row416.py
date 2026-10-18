"""Row 416 thought leadership: deterministic themes with honesty guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m06_social_media_manager.marketing_computations import compute

SLUG = "thought-leadership"


def build(facts=None):
    return compute(SLUG, {"facts": facts or {}})


def test_derives_themes_from_expertise_areas():
    out = build({"expertise": ["payroll automation", "compliance audits",
                               "vendor selection"]})
    assert out["theme_count"] == 3
    for theme in out["themes"]:
        assert theme["basis"] == "derived from disclosed angle template"
        assert theme["source_area"] in ("payroll automation", "compliance audits",
                                        "vendor selection")


def test_caps_at_five_themes():
    out = build({"expertise": [f"area {i}" for i in range(9)]})
    assert out["theme_count"] == 5


def test_fewer_than_three_areas_is_noted_honestly():
    out = build({"expertise": ["payroll automation"]})
    assert out["theme_count"] == 1
    assert any("fewer than 3 themes" in n for n in out["notes"])


def test_no_areas_means_empty_and_noted():
    out = build({})
    assert out["themes"] == []
    assert out["outlines"] == []
    assert any("nothing to outline" in n for n in out["notes"])


def test_caller_provided_themes_win_and_are_marked():
    out = build({"themes": ["My exact theme"],
                 "expertise": ["ignored area"]})
    assert out["theme_count"] == 1
    assert out["themes"][0]["title"] == "My exact theme"
    assert out["themes"][0]["basis"] == "caller-provided"
    outline = out["outlines"][0]
    assert outline["hook"].startswith("TO BE PROVIDED")
    assert outline["argument"].startswith("TO BE PROVIDED")


def test_evidence_attaches_only_where_provided():
    out = build({
        "expertise": ["payroll automation", "compliance audits"],
        "evidence": {"payroll automation": ["cut processing time 60% in pilot"]},
    })
    by_area = {o["theme"]: o for o in out["outlines"]}
    with_ev = [o for o in out["outlines"] if not o["evidence_gap"]]
    assert len(with_ev) == 1
    assert with_ev[0]["evidence_slots"] == ["cut processing time 60% in pilot"]
    gaps = [o for o in out["outlines"] if o["evidence_gap"]]
    assert len(gaps) == 1
    assert gaps[0]["evidence_slots"][0].startswith("TO BE PROVIDED")


def test_no_fabricated_evidence_anywhere():
    out = build({"expertise": ["a", "b", "c"]})
    for outline in out["outlines"]:
        assert outline["evidence_gap"] is True
        assert all(s.startswith("TO BE PROVIDED") for s in outline["evidence_slots"])


def test_hooks_and_arguments_are_area_bound_scaffolds():
    out = build({"expertise": ["payroll automation"]})
    outline = out["outlines"][0]
    assert "payroll automation" in outline["hook"]
    assert "payroll automation" in outline["argument"]


def test_channels_echo_only_provided_and_deduped():
    out = build({"expertise": ["a"],
                 "channels": ["LinkedIn", "linkedin", " Blog "]})
    assert out["channels"] == ["LinkedIn", "Blog"]


def test_deterministic():
    facts = {"expertise": ["a", "b"], "evidence": {"a": ["ev1"]}}
    assert build(facts) == build(dict(facts))


def test_output_covers_spec_sections():
    out = build({"expertise": ["a"]})
    for key in ("themes", "outlines", "channels"):
        assert key in out


def test_invalid_inputs_rejected():
    import pytest

    with pytest.raises(ValueError):
        build({"expertise": [42]})
    with pytest.raises(ValueError):
        build({"themes": ["  "]})
    with pytest.raises(ValueError):
        build({"evidence": ["not-a-mapping"]})
