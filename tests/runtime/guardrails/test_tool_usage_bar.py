"""Per-project verified tool-use bar tests (group 141). Stdlib only, hermetic.

Pins the enforcement: only uses carrying BOTH evidence_ref and verified_by
count; duplicate tools never inflate the distinct count; the default bar is
the strictest doc reading (200+ per project); any other bar (the 40+ later
passage) evaluates with no code change; require_bar refuses with the exact
shortfall and ledgers the unmet evaluation first.
"""
import pytest

from app.runtime.guardrails import tool_usage_bar as g
from app.runtime.guardrails.errors import GuardrailRefusal

T0 = "2026-10-12T07:00:00Z"
T1 = "2026-10-12T08:00:00Z"


def uses(n, project="proj-1"):
    ledger = []
    for i in range(n):
        ledger = g.record_use(ledger, project, f"tool-{i:03d}", used_at=T0,
                              evidence_ref=f"ev-{i}", verified_by="builder-1")
    return ledger


def test_default_bar_is_the_strictest_reading():
    assert g.DEFAULT_BAR == 200
    assert g.ALTERNATIVE_BAR == 40


def test_distinct_verified_count():
    ledger = uses(3)
    ledger = g.record_use(ledger, "proj-1", "tool-000", used_at=T0,
                          evidence_ref="ev-again", verified_by="builder-2")
    assert g.verified_tools(ledger, "proj-1") == ["tool-000", "tool-001", "tool-002"]
    assert g.verified_tools(ledger, "proj-2") == []


def test_use_without_attestation_never_records():
    with pytest.raises(ValueError, match="TOOLBAR:empty_field:evidence_ref"):
        g.record_use([], "proj-1", "blast", used_at=T0, evidence_ref=" ",
                     verified_by="builder-1")
    with pytest.raises(ValueError, match="TOOLBAR:empty_field:verified_by"):
        g.record_use([], "proj-1", "blast", used_at=T0, evidence_ref="ev",
                     verified_by="")


def test_unmet_evaluation_is_truthful_evidence_not_error():
    ledger = uses(3)
    ledger, rec = g.evaluate(ledger, "proj-1", now=T1)
    assert rec["verdict"] == "unmet"
    assert rec["distinct_verified_tools"] == 3
    assert rec["shortfall"] == 197
    # the evaluation itself is on the chain
    assert ledger[-1]["record"]["kind"] == "bar_evaluated"


def test_require_bar_refuses_with_shortfall_and_ledgers():
    ledger = uses(3)
    with pytest.raises(GuardrailRefusal) as held:
        g.require_bar(ledger, "proj-1", now=T1)
    assert held.value.code == "TOOLBAR:bar_unmet"
    assert held.value.details["shortfall"] == 197
    assert held.value.ledger[-1]["record"]["verdict"] == "unmet"


def test_either_ruling_lands_without_rework():
    ledger = uses(45)
    # strictest reading still unmet at 45
    _, rec = g.evaluate(ledger, "proj-1", bar=200, now=T1)
    assert rec["verdict"] == "unmet" and rec["shortfall"] == 155
    # the later-passage reading is met at 45
    ledger, rec = g.evaluate(ledger, "proj-1", bar=40, now=T1)
    assert rec["verdict"] == "met"
    ledger, rec = g.require_bar(ledger, "proj-1", bar=40, now=T1)
    assert rec["verdict"] == "met"


def test_full_bar_met():
    ledger = uses(200)
    ledger, rec = g.require_bar(ledger, "proj-1", now=T1)
    assert rec["verdict"] == "met"
    assert rec["distinct_verified_tools"] == 200
    assert rec["shortfall"] == 0


def test_bars_are_per_project():
    ledger = uses(5, project="proj-1")
    ledger = uses(0, project="proj-2") if False else ledger
    with pytest.raises(GuardrailRefusal) as held:
        g.require_bar(ledger, "proj-2", bar=40, now=T1)
    assert held.value.details["distinct_verified_tools"] == 0


def test_bar_validation():
    with pytest.raises(ValueError, match="TOOLBAR:bad_range:bar"):
        g.evaluate([], "proj-1", bar=0, now=T1)
    with pytest.raises(ValueError, match="TOOLBAR:bad_range:bar"):
        g.evaluate([], "proj-1", bar=True, now=T1)


def test_roundtrip_and_tamper_detection():
    ledger = uses(3)
    ledger, _ = g.evaluate(ledger, "proj-1", now=T1)
    restored = g.loads(g.dumps(ledger))
    assert restored == ledger
    tampered = [dict(e, record=dict(e["record"])) for e in restored]
    tampered[-1]["record"]["verdict"] = "met"
    with pytest.raises(ValueError, match="GRLEDGER:.*integrity"):
        g.check_ledger(tampered)
