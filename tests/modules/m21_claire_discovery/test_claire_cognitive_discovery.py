from datetime import datetime, timezone

import pytest

from app.modules.m21_claire.cognitive_discovery import (
    DiscoveryStore, Evidence, cross_domain_transfer_report,
    information_value, propose_counterfactuals,
)


def ev(ref="https://example.org/paper"):
    return Evidence("test", ref, "Observed result", datetime.now(timezone.utc).isoformat(), 0.9)


def test_hypothesis_evidence_and_optimistic_version(tmp_path):
    store = DiscoveryStore(tmp_path / "discovery.db")
    h = store.create_hypothesis("tenant-a", "Transfer", "A method transfers",
                                ["biology", "software"])
    updated = store.add_evidence("tenant-a", h["id"], ev(), expected_version=1)
    assert updated["version"] == 2
    assert updated["evidence"][0]["reference"].startswith("https:")
    with pytest.raises(RuntimeError):
        store.add_evidence("tenant-a", h["id"], ev(), expected_version=1)


def test_tenant_isolation(tmp_path):
    store = DiscoveryStore(tmp_path / "discovery.db")
    h = store.create_hypothesis("a", "Private", "claim", ["biology"])
    assert store.get_hypothesis("b", h["id"]) is None
    assert store.list_hypotheses("b") == []


def test_no_support_without_evidence(tmp_path):
    store = DiscoveryStore(tmp_path / "discovery.db")
    h = store.create_hypothesis("a", "Claim", "claim", ["biology"])
    with pytest.raises(ValueError):
        store.set_hypothesis_status("a", h["id"], "supported", 1)


def test_experiment_lifecycle_and_audit(tmp_path):
    store = DiscoveryStore(tmp_path / "discovery.db")
    h = store.create_hypothesis("a", "Claim", "claim", ["biology"])
    exp = store.create_experiment("a", h["id"], "Does it transfer?",
                                  {"baseline": "simple"}, "held-out gain")
    result = store.record_experiment_outcome("a", exp["id"], {"observed": "no gain"})
    assert result["status"] == "completed"
    assert store.audit_chain("a")["valid"] is True


def test_skill_is_not_verified_until_tests_run(tmp_path):
    store = DiscoveryStore(tmp_path / "discovery.db")
    skill = store.register_skill("a", "sum", "sum values", {"op": "sum_values"},
                                 [], [], [{"input": {"values": [1, 2]}, "expected": 3}])
    assert skill["status"] == "unverified"
    result = store.evaluate_skill("a", skill["id"],
                                  lambda procedure, data: sum(data["values"]))
    assert result["skill"]["status"] == "verified"
    assert result["skill"]["score"] == 1.0


def test_counterfactuals_are_marked_unvalidated():
    items = propose_counterfactuals([{
        "domain": "biology", "factor": "temperature", "outcome": "growth",
        "context": "condition A", "possible_confounders": ["pH"]
    }])
    assert len(items) == 1
    assert items[0]["status"] == "unvalidated_hypothesis"
    assert items[0]["requires_human_or_domain_validation"] is True


def test_information_value_rejects_bad_inputs():
    with pytest.raises(ValueError):
        information_value(decision_impact=2, uncertainty=.5, expected_reduction=.5,
                          generality=.5, cost=.2)
    assert information_value(decision_impact=1, uncertainty=1, expected_reduction=1,
                             generality=1, cost=0, risk=0) > 0


def test_transfer_reports_worst_domain():
    cases = [
        {"id": "1", "domain": "math", "input": {"values": [1, 2]}, "expected": 3},
        {"id": "2", "domain": "biology", "input": {"values": [2, 3]}, "expected": 5},
        {"id": "3", "domain": "software", "input": {"values": [2]}, "expected": 99},
    ]
    report = cross_domain_transfer_report(cases, lambda x: sum(x["values"]))
    assert report["domain_count"] == 3
    assert report["worst_domain_accuracy"] == 0.0
    assert report["case_count"] == 3


def test_reregistered_skill_keeps_one_consistent_id(tmp_path):
    store = DiscoveryStore(tmp_path / "discovery.db")
    tests_ = [{"input": {"values": [1, 2]}, "expected": 3}]
    first = store.register_skill("a", "sum", "v1", {"op": "sum_values"}, [], [], tests_)
    second = store.register_skill("a", "sum", "v2 body", {"op": "sum_values"}, [], [], tests_)
    assert second["id"] == first["id"] and second["version"] == 2
    res = store.evaluate_skill("a", second["id"], lambda p, d: sum(d["values"]))
    assert res["skill"]["description"] == "v2 body" and res["skill"]["id"] == second["id"]
    res_old = store.evaluate_skill("a", first["id"], lambda p, d: sum(d["values"]))
    assert res_old["skill"]["description"] == "v2 body"
