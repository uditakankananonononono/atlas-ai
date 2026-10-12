"""G114: lenslab - lens operators + measured battery."""
from __future__ import annotations

import pytest

from app.modules.c31 import lenslab

IDEA = ("Build an app that helps students track study habits. "
        "It must never sell user data and can only use free tools.")


def test_operators_transform_differently():
    results = {l: lenslab.transform(IDEA, l)["result"] for l in sorted(lenslab.OPERATORS)}
    assert len({str(r) for r in results.values()}) == len(lenslab.OPERATORS)
    sysr = results["systemizing"]
    assert sysr["inputs"] and sysr["rules"] and sysr["outputs"]
    assert any("track" in r for r in sysr["rules"])


def test_constraint_flip_real_inversion():
    flips = lenslab.transform(IDEA, "constraint-flip")["result"]["flips"]
    assert any("may now sell user data" in f["inverted"] for f in flips)
    assert all(f["constraint"] != f["inverted"] for f in flips)
    assert len(flips) == len({f["inverted"] for f in flips})  # deduped


def test_lateral_jump_imports_real_mechanism():
    art = lenslab.transform(IDEA, "lateral-jump")["result"]
    assert art["domain"] in lenslab.DOMAINS
    assert len(art["imported"]) == 2
    assert all("students" in m or "app" in m for m in art["mapping"])


def test_pattern_first_finds_repeats():
    art = lenslab.transform("data data data and one tool", "pattern-first")["result"]
    assert art["repeated"][0] == {"token": "data", "count": 3}


def test_hyperfocus_picks_rarest_word():
    art = lenslab.transform("the app app app crystallizes", "hyperfocus")["result"]
    assert art["focus"] == "crystallizes"


def test_battery_measures_deltas():
    out = lenslab.battery(IDEA, n=10)
    assert out["baseline"]["fluency"] == 10
    assert len(out["lenses"]) == len(lenslab.OPERATORS)
    for row in out["lenses"]:
        assert set(row["delta"]) == {"fluency", "flexibility", "originality", "elaboration"}
    assert out["best_lens"] in lenslab.OPERATORS
    assert out["formulas"]["originality"]


def test_disclaimer_and_clinical_refusal():
    assert "not diagnoses" in lenslab.transform(IDEA, "hyperfocus")["disclaimer"]
    with pytest.raises(ValueError, match="FLEET_REFUSED_CLINICAL"):
        lenslab.battery(IDEA, diagnose=True)
    with pytest.raises(ValueError, match="FLEET_REFUSED_BAD_LENS"):
        lenslab.transform(IDEA, "telepathy")


def test_determinism():
    assert lenslab.battery(IDEA, n=8) == lenslab.battery(IDEA, n=8)
