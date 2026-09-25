import pytest

from app.self_improve.engine import SelfImprovementEngine
from app.self_improve.gate import APPROVED, PENDING, ManualApprovalGate


def make_engine(tmp_path, auto_approve=False, min_occurrences=2):
    gate = ManualApprovalGate(tmp_path / "approvals.json", auto_approve=auto_approve)
    return SelfImprovementEngine(module_id=1, module_slug="opportunity-discovery",
                                 state_dir=tmp_path / "state", gate=gate,
                                 min_occurrences=min_occurrences), gate


def seed(engine, signature="filter only biology grants", n=3):
    for _ in range(n):
        engine.record_gap(signature, detail="user keeps asking to filter grants",
                          exemplar="a biology grant for phd students")


def test_full_cycle_proposes_but_does_not_activate(tmp_path):
    engine, gate = make_engine(tmp_path)
    seed(engine)
    report = engine.run_cycle()
    assert report["candidates"][0]["tests_passed"] is True
    assert len(report["proposals"]) == 1
    proposal = report["proposals"][0]
    assert gate.decision(proposal["approval_id"]) == PENDING
    # Without a human decision, activation is refused.
    with pytest.raises(PermissionError):
        engine.activate(proposal["key"], approval_id=proposal["approval_id"])


def test_activation_after_human_approval(tmp_path):
    engine, gate = make_engine(tmp_path)
    seed(engine)
    report = engine.run_cycle()
    proposal = report["proposals"][0]
    gate.decide(proposal["approval_id"], APPROVED, decided_by="udita")
    entry = engine.activate(proposal["key"], approval_id=proposal["approval_id"])
    assert entry["version"] == 1
    out = engine.dispatch(proposal["name"], ["a biology grant", "a cooking class"])
    assert out["count"] >= 1
    events = [e["event"] for e in engine.ledger()]
    assert "feature_activated" in events and "feature_dispatched" in events


def test_wrong_approval_id_refused(tmp_path):
    engine, gate = make_engine(tmp_path)
    seed(engine)
    proposal = engine.run_cycle()["proposals"][0]
    gate.decide(proposal["approval_id"], APPROVED)
    with pytest.raises(PermissionError):
        engine.activate(proposal["key"], approval_id="si-forged")


def test_gap_not_rebuilt_once_covered(tmp_path):
    engine, gate = make_engine(tmp_path)
    seed(engine)
    engine.run_cycle()
    assert engine.detect_gaps() == []  # proposal already covers the gap


def test_below_threshold_no_candidates(tmp_path):
    engine, _ = make_engine(tmp_path)
    engine.record_gap("one-off miss")
    report = engine.run_cycle()
    assert report["candidates"] == [] and report["proposals"] == []


def test_rollback_flow(tmp_path):
    engine, gate = make_engine(tmp_path)
    seed(engine)
    proposal = engine.run_cycle()["proposals"][0]
    gate.decide(proposal["approval_id"], APPROVED)
    engine.activate(proposal["key"], approval_id=proposal["approval_id"])
    rb_approval = engine.request_rollback(proposal["name"])
    with pytest.raises(PermissionError):
        engine.rollback(proposal["name"], approval_id=rb_approval)
    gate.decide(rb_approval, APPROVED)
    outcome = engine.rollback(proposal["name"], approval_id=rb_approval)
    assert outcome["active_version"] is None
    with pytest.raises(KeyError):
        engine.dispatch(proposal["name"], ["x"])


def test_status_shape(tmp_path):
    engine, _ = make_engine(tmp_path)
    seed(engine, n=2)
    status = engine.status()
    assert status["module"] == "opportunity-discovery"
    assert status["gap_events"] == 2
    assert "filter only biology grants" in status["open_gaps"]
