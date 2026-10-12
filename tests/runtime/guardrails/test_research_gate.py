"""Research-conduction completion gate tests (group 140). Stdlib only,
hermetic.

Pins the enforcement: a 'conducted' claim requires a registered dataset, an
executed run with ordered timestamps, and a recorded result whose digest the
run binds to; missing legs and unbound runs refuse; the completion statement
is hash-bound into the claim record.
"""
import hashlib

import pytest

from app.runtime.guardrails import research_gate as g
from app.runtime.guardrails.errors import GuardrailRefusal

T0 = "2026-10-12T07:00:00Z"
T1 = "2026-10-12T07:30:00Z"
T2 = "2026-10-12T08:00:00Z"
RESULT_BYTES = b"run-output-bytes"
DIGEST = hashlib.sha256(RESULT_BYTES).hexdigest()


def evidenced_ledger():
    ledger = g.register_dataset([], "proj-1", "ds-1", name="WikiText-103",
                                source_ref="salesforce", now=T0)
    ledger = g.record_run(ledger, "proj-1", "run-1", started_at=T0, ended_at=T1,
                          result_sha256=DIGEST, summary="baseline evaluation")
    return g.record_result(ledger, "proj-1", "res-1", finding="perplexity 30.1",
                           result_sha256=DIGEST, now=T1)


def test_no_evidence_no_completion_claim():
    with pytest.raises(GuardrailRefusal) as held:
        g.claim_conducted([], "proj-1", "cl-1", statement="research conducted", now=T2)
    assert held.value.code == "RESGATE:refused:missing_evidence"
    assert held.value.details["missing"] == ["datasets", "runs", "results"]


def test_each_missing_leg_named():
    ledger = g.register_dataset([], "proj-1", "ds-1", name="d", now=T0)
    with pytest.raises(GuardrailRefusal) as held:
        g.claim_conducted(ledger, "proj-1", "cl-1", statement="done", now=T2)
    assert held.value.details["missing"] == ["runs", "results"]
    assert held.value.details["datasets"] == 1


def test_unbound_run_result_refused():
    ledger = g.register_dataset([], "proj-1", "ds-1", name="d", now=T0)
    ledger = g.record_run(ledger, "proj-1", "run-1", started_at=T0, ended_at=T1,
                          result_sha256=DIGEST, summary="s")
    other = hashlib.sha256(b"different").hexdigest()
    ledger = g.record_result(ledger, "proj-1", "res-1", finding="f",
                             result_sha256=other, now=T1)
    with pytest.raises(GuardrailRefusal) as held:
        g.claim_conducted(ledger, "proj-1", "cl-1", statement="done", now=T2)
    assert held.value.code == "RESGATE:refused:unbound_run_result"
    assert "unbound:run-1" in held.value.details["missing"]


def test_complete_evidence_admits_and_binds_statement():
    ledger = evidenced_ledger()
    ledger, rec = g.claim_conducted(ledger, "proj-1", "cl-9",
                                    statement="research conducted: perplexity measured", now=T2)
    assert rec["verdict"] == "admitted"
    assert rec["statement_sha256"] == hashlib.sha256(
        b"research conducted: perplexity measured").hexdigest()
    assert (rec["datasets"], rec["runs"], rec["results"]) == (1, 1, 1)


def test_refusal_is_ledgered():
    with pytest.raises(GuardrailRefusal) as held:
        g.claim_conducted([], "proj-1", "cl-1", statement="done", now=T2)
    ledger = held.value.ledger
    assert ledger[-1]["record"]["verdict"] == "refused:missing_evidence"
    g.check_ledger(ledger)


def test_run_time_order_enforced():
    with pytest.raises(ValueError, match="RESGATE:.*ends before it starts"):
        g.record_run([], "proj-1", "run-1", started_at=T1, ended_at=T0,
                     result_sha256=DIGEST, summary="s")


def test_duplicate_ids_rejected():
    ledger = g.register_dataset([], "proj-1", "ds-1", name="d", now=T0)
    with pytest.raises(ValueError, match="RESGATE:.*already registered"):
        g.register_dataset(ledger, "proj-1", "ds-1", name="d2", now=T0)
    ledger = g.record_run(ledger, "proj-1", "run-1", started_at=T0, ended_at=T1,
                          result_sha256=DIGEST, summary="s")
    with pytest.raises(ValueError, match="RESGATE:.*already recorded"):
        g.record_run(ledger, "proj-1", "run-1", started_at=T0, ended_at=T1,
                     result_sha256=DIGEST, summary="s2")


def test_evidence_state_counts():
    ledger = evidenced_ledger()
    state = g.evidence_state(ledger, "proj-1")
    assert state == {"project_id": "proj-1", "datasets": 1, "runs": 1, "results": 1,
                     "missing": [], "unbound_runs": []}
    assert g.evidence_state(ledger, "proj-2")["missing"] == ["datasets", "runs", "results"]


def test_projects_are_isolated():
    ledger = evidenced_ledger()
    with pytest.raises(GuardrailRefusal) as held:
        g.claim_conducted(ledger, "proj-2", "cl-1", statement="done", now=T2)
    assert held.value.details["missing"] == ["datasets", "runs", "results"]


def test_bad_hash_and_naive_time_rejected():
    with pytest.raises(ValueError, match="RESGATE:bad_hash:result_sha256"):
        g.record_run([], "proj-1", "run-1", started_at=T0, ended_at=T1,
                     result_sha256="zz", summary="s")
    with pytest.raises(ValueError, match="RESGATE:naive_instant:started_at"):
        g.record_run([], "proj-1", "run-1", started_at="2026-10-12 07:00:00", ended_at=T1,
                     result_sha256=DIGEST, summary="s")


def test_roundtrip_and_tamper_detection():
    ledger = evidenced_ledger()
    restored = g.loads(g.dumps(ledger))
    assert restored == ledger
    tampered = [dict(e, record=dict(e["record"])) for e in restored]
    tampered[2]["record"]["result_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="GRLEDGER:.*integrity"):
        g.check_ledger(tampered)
