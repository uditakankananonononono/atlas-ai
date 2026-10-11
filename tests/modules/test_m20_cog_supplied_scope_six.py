"""Rows 1975/1976/1977/1992/1993/2009: non-substitute partials carry an explicit supplied-operator scope.

These six methods are not reference substitutes (truth01 pins exactly 26 of those and is untouched).
They are supplied-data operators: Brier calibration, a valence/arousal rubric, finite knapsack enumeration.
"""
import json
from collections import Counter
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker import cognitive_1960_2009 as mod
from app.modules.m20_general_cognitive_worker.cognitive_routes_1960_2009 import router

ROOT = Path(__file__).resolve().parents[2]
BOUNDARY = ("Supplied-data operator only; not verification or execution of the original named capability, "
            "no cognition, emotion recognition or general optimization demonstrated.")
SIX = {
    "cognitive_computing": (1975, "supplied_scored_attempt_brier_calibration", "PARTIAL"),
    "affective_computing": (1976, "supplied_valence_arousal_quadrant_rubric", "PARTIAL"),
    "emotion_recognition": (1977, "supplied_valence_arousal_quadrant_rubric", "PARTIAL"),
    "optimization": (1992, "finite_binary_knapsack_enumeration_max_20_items", "SCOPED"),
    "operations_research": (1993, "finite_binary_knapsack_enumeration_max_20_items", "SCOPED"),
    "metacognition": (2009, "supplied_scored_attempt_brier_calibration", "PARTIAL"),
}
DATA = {
    "cognitive_computing": {"tasks": [{"task": "a", "confidence": .8, "correct": True}]},
    "metacognition": {"tasks": [{"task": "a", "confidence": .8, "correct": True}]},
    "affective_computing": {"signals": {"arousal": .8, "valence": .7}},
    "emotion_recognition": {"signals": {"arousal": .2, "valence": -.7}},
    "optimization": {"values": [10, 4], "costs": [5, 6], "budget": 5},
    "operations_research": {"values": [10, 4], "costs": [5, 6], "budget": 5},
}


def scope(op):
    return {"supplied_operator": op, "named_capability_executed": False, "scope_status": "supplied_operator_only",
            "original_capability_status": "unverified", "verification_boundary": BOUNDARY}


def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_exact_methods_and_rows():
    assert {m: mod.ROWS[m] for m in SIX} == {m: v[0] for m, v in SIX.items()}
    assert mod.SUPPLIED_OPERATORS == {m: v[1] for m, v in SIX.items()}
    assert len(mod.SUPPLIED_OPERATORS) == 6


def test_disjoint_from_reference_substitutes_and_truth01_counts_untouched():
    assert len(mod.REFERENCE_SUBSTITUTES) == 26
    assert not set(SIX) & set(mod.REFERENCE_SUBSTITUTES)
    for m in SIX:
        assert mod.capability_scope(m) == {}


@pytest.mark.parametrize("method", sorted(SIX))
def test_supplied_scope_exact(method):
    assert mod.supplied_scope(method) == scope(SIX[method][1])


@pytest.mark.parametrize("method", sorted(set(mod.ROWS) - set(SIX)))
def test_supplied_scope_empty_for_every_other_method(method):
    assert mod.supplied_scope(method) == {}


def test_supplied_scope_unsupported_method_exact_message():
    with pytest.raises(ValueError) as e:
        mod.supplied_scope("not_a_method")
    assert str(e.value) == "unsupported cognitive method not_a_method"


@pytest.mark.parametrize("method", sorted(SIX))
def test_run_output_and_routes_carry_scope(method):
    want = scope(SIX[method][1])
    out = mod.run(method, DATA[method])["output"]
    for k, v in want.items():
        assert out[k] == v
    cat = {x["method"]: x for x in client().get("/cognitive-1960-2009/methods").json()}[method]
    for k, v in want.items():
        assert cat[k] == v
    assert cat["feature_row"] == SIX[method][0]
    r = client().post("/cognitive-1960-2009/analyze", json={"method": method, "data": DATA[method]})
    assert r.status_code == 200
    for k, v in want.items():
        assert r.json()["output"][k] == v


def test_existing_outputs_unchanged_by_scope_merge():
    o = mod.run("cognitive_computing", DATA["cognitive_computing"])["output"]
    assert o["calibration_brier"] == pytest.approx(.04) and o["cognition_executed"] is False
    assert o["status"] == "supplied_scored_attempt_calibration_only" and o["outcome_truth_verified"] is False
    a = mod.run("affective_computing", DATA["affective_computing"])["output"]
    assert a["status"] == "supplied_signal_quadrant_rubric_only" and a["heuristic_quadrant_label"] == "excited" and a["emotion_recognized"] is False and a["confidence"] is None
    p = mod.run("optimization", DATA["optimization"])["output"]
    assert p["chosen_indices"] == [0] and p["objective_value"] == 10 and p["used_budget"] == 5


def test_other_methods_output_has_no_supplied_scope_keys():
    out = mod.run("decision_science", {"options": [{"name": "a", "criteria": [1]}], "weights": [1]})["output"]
    assert "supplied_operator" not in out


def _ledger_rows():
    d = json.loads((ROOT / "audits/additional-2000-features.json").read_text())
    return d, {r["id"]: r for r in d["rows"]}


@pytest.mark.parametrize("method", sorted(SIX))
def test_ledger_row_states_supplied_scope_without_promotion(method):
    d, rows = _ledger_rows()
    rid, op, status = SIX[method]
    r = rows[rid]
    assert r["status"] == status
    assert r["supplied_scope"] == {"method": method, "supplied_operator": op, "original_capability_status": "unverified",
                                   "named_capability_executed": False}
    assert op in r["boundary"] and "remains unverified" in r["boundary"]
    assert r["boundary"].startswith("Supplied-data operator only: " + op + ".")
    assert r["historical_claim"]["status"] == "verified-pushed"
    assert r["description"] == ""
    assert d["counts"] == dict(Counter(x["status"] for x in d["rows"]))


@pytest.mark.parametrize("method", sorted(SIX))
def test_implementation_audit_line_no_longer_claims_practitioner_depth(method):
    rid, op, status = SIX[method]
    line = next(x for x in (ROOT / "docs/IMPLEMENTATION_AUDIT.md").read_text().splitlines() if x.startswith(f"| {rid} |"))
    assert "verified-practitioner-depth" not in line
    assert f"| {status}-supplied-operator |" in line and op in line and "remains unverified" in line


def test_other_audit_lines_untouched():
    n = sum(1 for x in (ROOT / "docs/IMPLEMENTATION_AUDIT.md").read_text().splitlines()
            if x.startswith("| ") and "-supplied-operator |" in x)
    assert n == 6
