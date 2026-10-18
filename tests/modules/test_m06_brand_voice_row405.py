"""Row 405 brand voice: deterministic attributes with honesty guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m06_social_media_manager.marketing_computations import compute

SLUG = "brand-voice"


def build(facts=None):
    return compute(SLUG, {"facts": facts or {}})


def test_caller_attributes_win_and_carry_examples():
    out = build({"voice_attributes": [
        {"name": "Plain-spoken", "do": "Say 'you owe $12'", "dont": "Say 'a balance is outstanding'"},
        {"name": "Warm", "do": "Acknowledge the feeling first", "dont": "Open with policy"},
    ]})
    assert [a["name"] for a in out["voice_attributes"]] == ["Plain-spoken", "Warm"]
    assert out["do_examples"] == ["Say 'you owe $12'", "Acknowledge the feeling first"]
    assert out["dont_examples"] == ["Say 'a balance is outstanding'", "Open with policy"]
    assert out["example_coverage"] == 1.0


def test_derives_attributes_from_brand_values_and_caps():
    out = build({"values": ["honest", "direct", "calm", "curious", "patient", "extra"]})
    assert len(out["voice_attributes"]) == 5
    assert all(a["basis"] == "derived from provided brand values"
               for a in out["voice_attributes"])


def test_no_values_means_empty_and_noted():
    out = build({})
    assert out["voice_attributes"] == []
    assert any("no voice attributes or brand values" in n for n in out["notes"])


def test_no_fabricated_examples():
    out = build({"values": ["honest", "direct", "calm"]})
    assert out["do_examples"] == []
    assert out["dont_examples"] == []
    for a in out["voice_attributes"]:
        assert a["example_gap"] is True
        assert a["example_slot"].startswith("TO BE PROVIDED")
    assert out["example_coverage"] == 0.0


def test_partial_examples_flag_gap():
    out = build({"voice_attributes": [{"name": "Warm", "do": "Only a do"}]})
    a = out["voice_attributes"][0]
    assert a["example_gap"] is True
    assert out["do_examples"] == ["Only a do"]
    assert out["dont_examples"] == []


def test_tone_flex_uses_disclosed_templates_per_context():
    out = build({"values": ["calm"]})
    tone = out["tone_by_context"]
    assert set(tone) == {"launch", "support", "crisis", "social"}
    for context, entry in tone.items():
        assert entry["basis"] == "derived from disclosed flex template"
        assert any("calm" in g for g in entry["guidance"])
    assert "more direct and factual" in tone["crisis"]["guidance"][0]


def test_caller_tone_override_wins_per_context():
    out = build({"values": ["calm"],
                 "tone_by_context": {"crisis": "Silence until facts verified"}})
    assert out["tone_by_context"]["crisis"]["guidance"] == "Silence until facts verified"
    assert out["tone_by_context"]["crisis"]["basis"] == "caller-provided"
    assert out["tone_by_context"]["launch"]["basis"] == "derived from disclosed flex template"


def test_fewer_than_three_attributes_noted():
    out = build({"values": ["honest"]})
    assert any("fewer than 3 attributes" in n for n in out["notes"])


def test_deterministic_deduped_and_spec_sections():
    facts = {"values": ["honest", "Honest ", "direct"]}
    a = build(facts)
    assert a == build(dict(facts))
    assert [x["name"] for x in a["voice_attributes"]] == ["honest", "direct"]
    for key in ("voice_attributes", "tone_by_context", "do_examples", "dont_examples"):
        assert key in a


def test_invalid_inputs_rejected():
    import pytest

    with pytest.raises(ValueError):
        build({"voice_attributes": [42]})
    with pytest.raises(ValueError):
        build({"values": ["  "]})
    with pytest.raises(ValueError):
        build({"tone_by_context": ["not-a-mapping"]})
