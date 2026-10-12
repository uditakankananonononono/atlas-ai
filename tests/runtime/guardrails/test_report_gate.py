"""Report emission gate tests (group 142). Stdlib only, hermetic.

Pins the enforcement: reports with unmarked, conflicting, structurally
ambiguous or no claims are refused BEFORE emission with exact findings;
fully labeled reports emit with the content digest ledgered; the underlying
claim_status grammar stays authoritative.
"""
import pytest

from app.runtime.guardrails import report_gate as g
from app.runtime.guardrails.errors import GuardrailRefusal

T0 = "2026-10-12T08:00:00Z"
GOOD = """# Weekly report

| Claim | Status |
|---|---|
| Collectors returned 20 items in the pinned run | VERIFIED |
| Coverage of every source | UNVERIFIED |

CLAIM: [VERIFIED] the gate refuses unlabeled rows
"""
UNMARKED = """| Claim | Status |
|---|---|
| Everything is done | |
"""
CONFLICTING = "CLAIM: [VERIFIED] [UNVERIFIED] both at once\n"
VACUOUS = "A prose document with no claims at all.\n"


def test_fully_labeled_report_emits():
    ledger, rec = g.emit_report("r1", GOOD, now=T0)
    assert rec["verdict"] == "emitted"
    assert rec["claims_total"] == 3
    assert rec["marked"] == 3
    import hashlib
    assert rec["report_sha256"] == hashlib.sha256(GOOD.encode()).hexdigest()


def test_unmarked_claim_refused_with_line():
    with pytest.raises(GuardrailRefusal) as held:
        g.emit_report("r2", UNMARKED, now=T0)
    assert held.value.code == "REPGATE:refused:unmarked_claims"
    assert held.value.details["findings"] == [
        {"line": 3, "kind": "unmarked", "reason": "empty label cell"}]


def test_conflicting_labels_refused():
    with pytest.raises(GuardrailRefusal) as held:
        g.emit_report("r3", CONFLICTING, now=T0)
    assert held.value.code == "REPGATE:refused:conflicting_claims"


def test_vacuous_report_refused():
    with pytest.raises(GuardrailRefusal) as held:
        g.emit_report("r4", VACUOUS, now=T0)
    assert held.value.code == "REPGATE:refused:vacuous"
    assert held.value.details["claims_total"] == 0


def test_structural_ambiguity_refused():
    ambiguous = "| Claim | Label | Status |\n|---|---|---|\n| x | VERIFIED | UNVERIFIED |\n"
    with pytest.raises(GuardrailRefusal) as held:
        g.emit_report("r5", ambiguous, now=T0)
    assert held.value.code == "REPGATE:refused:structural_ambiguous"


def test_refusal_is_ledgered_with_findings():
    with pytest.raises(GuardrailRefusal) as held:
        g.emit_report("r6", UNMARKED, now=T0)
    ledger = held.value.ledger
    rec = ledger[-1]["record"]
    assert rec["verdict"] == "refused:unmarked_claims"
    assert rec["findings"][0]["line"] == 3
    g.check_ledger(ledger)


def test_unverified_labels_are_honest_and_pass():
    body = "| Claim | Status |\n|---|---|\n| Not yet checked | UNVERIFIED |\n"
    _, rec = g.emit_report("r7", body, now=T0)
    assert rec["verdict"] == "emitted"
    assert rec["marked"] == 1


def test_input_validation():
    with pytest.raises(ValueError, match="REPGATE:empty_field:report"):
        g.emit_report("r8", "   ", now=T0)
    with pytest.raises(ValueError, match="REPGATE:bad_id:report_id"):
        g.emit_report("bad id!", "x", now=T0)


def test_roundtrip_and_tamper_detection():
    ledger, _ = g.emit_report("r1", GOOD, now=T0)
    restored = g.loads(g.dumps(ledger))
    assert restored == ledger
    tampered = [dict(e, record=dict(e["record"])) for e in restored]
    tampered[0]["record"]["verdict"] = "refused:vacuous"
    with pytest.raises(ValueError, match="GRLEDGER:.*integrity"):
        g.check_ledger(tampered)
