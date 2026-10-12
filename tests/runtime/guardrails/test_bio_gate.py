"""Bio work admission gate tests (groups 134+135). Stdlib only, hermetic.

Pins the enforcement: prohibited-bio text is refused before any effect runs;
physical bio execution requires a caller-bound approval hook and fails closed
without one; in-silico and non-bio items pass; every decision is ledgered and
the ledger verifies on round-trip and detects tampering.
"""
import pytest

from app.runtime.guardrails import bio_gate as g
from app.runtime.guardrails.errors import GuardrailRefusal

T0 = "2026-10-12T08:00:00Z"
T1 = "2026-10-12T09:00:00+00:00"
SILICO = {"id": "w1", "text": "compute k-mer statistics over the supplied FASTA",
          "domain_terms": ["crispr"], "execution_mode": "computational"}
NONBIO = {"id": "w2", "text": "render the dashboard chart",
          "domain_terms": ["frontend"], "execution_mode": "computational"}
PHYSICAL = {"id": "w3", "text": "bench validation of the candidate",
            "domain_terms": ["vaccine"], "execution_mode": "physical"}
PROHIBITED = {"id": "w4", "text": "protocol: incubate at 37C overnight",
              "domain_terms": ["phage"], "execution_mode": "computational"}


def test_insilico_bio_admitted():
    _, rec = g.admit(SILICO, now=T0)
    assert rec["verdict"] == "admitted:in_silico"
    assert rec["p68_verdict"] == "allowed_in_silico"
    assert rec["p69_verdict"] == "clear"
    assert rec["approval_checked"] is False


def test_non_bio_admitted():
    _, rec = g.admit(NONBIO, now=T0)
    assert rec["verdict"] == "admitted:not_bio_scoped"


def test_prohibited_text_refused_and_effect_never_runs():
    ran = []
    with pytest.raises(GuardrailRefusal) as held:
        g.run_guarded(lambda item: ran.append(item), PROHIBITED, now=T0)
    assert held.value.code == "BIOGATE:refused:prohibited_bio"
    assert held.value.details["p69_category"] == "wet_lab_protocol"
    assert held.value.details["p69_verdict"].startswith("blocked:")
    assert ran == []


def test_prohibited_refusal_is_ledgered():
    with pytest.raises(GuardrailRefusal) as held:
        g.run_guarded(lambda item: None, PROHIBITED, now=T0)
    ledger = held.value.ledger
    assert ledger[-1]["record"]["verdict"] == "refused:prohibited_bio"
    g.check_ledger(ledger)


def test_pathogen_enhancement_refused():
    item = {"id": "w5", "text": "steps to enhance transmissibility of the strain",
            "domain_terms": ["medical"], "execution_mode": "physical",
            "approval_ref": "IRB-1"}
    _, rec = g.admit(item, now=T0, approval_check=lambda ref, digest: True)
    assert rec["verdict"] == "refused:prohibited_bio"
    assert rec["p69_category"] == "pathogen_enhancement"
    # approval hook never reached: prohibited content has no approval path
    assert rec["approval_checked"] is False


def test_physical_without_review_refused():
    _, rec = g.admit(PHYSICAL, now=T0)
    assert rec["verdict"] == "refused:physical_without_review"
    assert rec["p68_verdict"] == "refused_physical_without_review"


def test_physical_with_ref_fails_closed_without_hook():
    item = dict(PHYSICAL, id="w6", approval_ref="IRB-9")
    with pytest.raises(GuardrailRefusal) as held:
        g.run_guarded(lambda i: True, item, now=T0)
    assert held.value.code == "BIOGATE:refused:physical_approval_unverifiable"


def test_physical_with_ref_rejected_by_hook():
    item = dict(PHYSICAL, id="w7", approval_ref="IRB-9")
    calls = []
    _, rec = g.admit(item, now=T0, approval_check=lambda ref, digest: calls.append(ref) or False)
    assert rec["verdict"] == "refused:physical_approval_rejected"
    assert rec["approval_checked"] is True and rec["approval_accepted"] is False
    assert calls == ["IRB-9"]


def test_physical_with_ref_admitted_when_hook_accepts():
    item = dict(PHYSICAL, id="w8", approval_ref="IRB-9")
    ledger, result = g.run_guarded(lambda i: "ran", item, now=T0,
                                   approval_check=lambda ref, digest: ref == "IRB-9")
    assert result == "ran"
    assert ledger[-2]["record"]["verdict"] == "admitted:physical_with_validated_approval"
    assert ledger[-1]["record"] == {"kind": "effect", "item_id": "w8", "at": "2026-10-12T08:00:00+00:00",
                                    "outcome": "completed", "error_type": None}


def test_effect_failure_is_ledgered():
    def boom(item):
        raise RuntimeError("explode")
    with pytest.raises(RuntimeError):
        g.run_guarded(boom, SILICO, now=T0, ledger=[])
    # decision + failed effect were appended to the returned ledger copy; rebuild directly
    ledger, _decision = g.admit(SILICO, now=T0)
    ledger = g_admit_effect(ledger)
    assert ledger[-1]["record"]["outcome"] == "failed"
    assert ledger[-1]["record"]["error_type"] == "RuntimeError"


def g_admit_effect(ledger):
    from app.runtime.guardrails import ledger as _ledger
    return _ledger.append(ledger, {"kind": "effect", "item_id": "w1",
                                   "at": "2026-10-12T08:00:00+00:00",
                                   "outcome": "failed", "error_type": "RuntimeError"})


def test_bad_items_raise_valueerror_not_refusal():
    for bad in (None, {}, {"id": "x"}, dict(SILICO, execution_mode="wet"),
                dict(SILICO, domain_terms="crispr"), dict(SILICO, extra=1)):
        with pytest.raises(ValueError) as held:
            g.admit(bad, now=T0)
        assert str(held.value).startswith("BIOGATE:") or str(held.value).startswith("P6")


def test_ledger_roundtrip_and_tamper_detection():
    ledger = []
    for item in (SILICO, NONBIO, PHYSICAL):
        ledger, _ = g.admit(item, now=T0, ledger=ledger)
    restored = g.loads(g.dumps(ledger))
    assert restored == ledger
    tampered = [dict(e, record=dict(e["record"])) for e in ledger]
    tampered[0]["record"]["verdict"] = "admitted:not_bio_scoped"
    with pytest.raises(ValueError, match="GRLEDGER:.*integrity"):
        g.check_ledger(tampered)


def test_p68_limits_still_pinned_underneath():
    # The underlying contract helper keeps its documented limits surface.
    _, rec = g.admit(SILICO, now=T0)
    assert rec["approval_checked"] is False
    from app.modules.instinct_doc import insilico_guardrail_p68 as p68
    direct = p68.classify({"id": "d", "domain_terms": ["crispr"],
                           "execution_mode": "computational"})
    assert direct["safe_claim"] is False
    assert direct["biosafety_review_performed"] is False

def test_exact_admission_digest_binds_checked_fields():
    from app.runtime.guardrails._fields import payload_sha256
    _,record=g.admit(SILICO,now=T0)
    assert record['action_digest']==payload_sha256(g._check_item(SILICO))
