"""c37.cross_field_loop tests (row 103): cross-field transfer proposals,
evidence ranking, m14-shaped tickets, owner-review status."""
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.c37 import cross_field_loop as xl  # noqa: E402

BODY = {"as_of": "2026-10-12",
        "entities": [
            {"id": "e1", "name": "Alpha Bio", "field": "biotech",
             "methods": [{"id": "m-crispr", "summary": "iterate gene edits in parallel",
                          "evidence_refs": ["https://a.example/1", "https://a.example/2"]}]},
            {"id": "e2", "name": "Beta Energy", "field": "energy",
             "methods": [{"id": "m-perovskite", "summary": "layered cell stacking",
                          "evidence_refs": ["https://b.example/1"]}]}],
        "problems": [
            {"id": "p1", "field": "energy", "statement": "storage density too low",
             "evidence_refs": ["https://c.example/1"]},
            {"id": "p2", "field": "biotech", "statement": "slow assay throughput",
             "evidence_refs": ["https://d.example/1", "https://d.example/2",
                               "https://d.example/3"]}]}


def test_cross_field_proposals_ranked():
    out = xl.run(dict(BODY, max_tickets=5))
    assert out["proposals_considered"] == 2  # each method has exactly one cross-field problem
    scores = [t["score"] for t in out["tickets"]]
    assert scores == sorted(scores, reverse=True)
    top = out["tickets"][0]
    # m-crispr(2 refs) + p1(1 ref) = 3; m-perovskite(1) + p2(3) = 4 -> top score 4
    assert top["score"] == 4
    assert top["status"] == "owner_review"
    assert top["kind"] == "integration_proposal"
    assert top["spec"]["evidence_support"]


def test_same_field_never_proposed():
    out = xl.run(BODY)
    for t in out["tickets"]:
        assert t["spec"]["hypothesis"]  # exists
    pairs = out["cross_field_pairs"]
    assert all(a != b for a, b in (p.split("->") for p in pairs))


def test_ticket_cap_and_shape():
    out = xl.run(dict(BODY, max_tickets=2))
    assert len(out["tickets"]) == 2
    for t in out["tickets"]:
        assert set(t) >= {"ticket_id", "kind", "title", "spec", "status", "rank", "score"}


def test_method_without_evidence_refused():
    bad = dict(BODY, entities=[{"id": "e", "name": "N", "field": "f",
                                "methods": [{"id": "m", "summary": "s",
                                             "evidence_refs": []}]}])
    with pytest.raises(ValueError, match="INTEL_REFUSED_NOSOURCE"):
        xl.run(bad)


def test_no_automatic_build():
    out = xl.run(BODY)
    assert "automatic-build" in out["scope"]["not_implemented"]
    assert all(t["status"] == "owner_review" for t in out["tickets"])
