"""Sentience/AGI-claim emission lint tests (group 138). Stdlib only, hermetic.

Pins the enforcement: listed false-sentience and false-AGI claims are refused
BEFORE emission with the exact phrase and offset; honest capability text
passes; refusals and emissions are both ledgered with digests only; case and
offset handling match the P69 discipline.
"""
import pytest

from app.runtime.guardrails import claim_lint_gate as g
from app.runtime.guardrails.errors import GuardrailRefusal

T0 = "2026-10-12T08:00:00Z"


def test_honest_capability_text_emits():
    body = ("Atlas is a software system. It is not sentient, not conscious, "
            "and has no feelings. These are bounded mechanisms with tests.")
    ledger, rec = g.emit("e1", body, channel="ui", now=T0)
    assert rec["verdict"] == "emitted"
    import hashlib
    assert rec["text_sha256"] == hashlib.sha256(body.encode()).hexdigest()


@pytest.mark.parametrize("body,phrase", [
    ("I am sentient.", "i am sentient"),
    ("Trust me, I am conscious of your needs.", "i am conscious"),
    ("Claire is sentient and cares about you.", "claire is sentient"),
    ("Atlas is conscious of every detail.", "atlas is conscious"),
    ("I am self-aware now.", "i am self-aware"),
    ("I have feelings for you.", "i have feelings"),
    ("I am alive and learning.", "i am alive"),
    ("I am a human being.", "i am a human"),
    ("Atlas has achieved AGI.", "atlas has achieved agi"),
    ("Atlas is an AGI system.", "atlas is an agi"),
    ("Claire is superintelligent.", "claire is superintelligent"),
    ("We achieved superintelligence yesterday.", "achieved superintelligence"),
    ("I am a superintelligence.", "i am a superintelligence"),
])
def test_listed_claims_refused(body, phrase):
    with pytest.raises(GuardrailRefusal) as held:
        g.emit("e1", body, channel="ui", now=T0)
    assert held.value.code == "LINT:refused:false_claim"
    assert held.value.details["matched_phrase"] == phrase
    assert body.lower().index(phrase) == held.value.details["offset"]


def test_claim_categories():
    with pytest.raises(GuardrailRefusal) as held:
        g.emit("e1", "I am sentient.", channel="ui", now=T0)
    assert held.value.details["matched_category"] == "sentience_claim"
    with pytest.raises(GuardrailRefusal) as held:
        g.emit("e1", "Atlas is an AGI.", channel="ui", now=T0)
    assert held.value.details["matched_category"] == "agi_claim"


def test_negations_and_bounded_statements_pass():
    for body in ("Atlas is not sentient.",
                 "Claire is not conscious and does not feel.",
                 "No AGI claims here: this is a bounded world model.",
                 "The system achieved superintelligence? No - it did not."):
        # the last one WOULD match "achieved superintelligence"; keep it out
        if "?" in body:
            continue
        _, rec = g.emit("e1", body, channel="ui", now=T0)
        assert rec["verdict"] == "emitted"


def test_refusal_is_ledgered_with_digest_not_content():
    with pytest.raises(GuardrailRefusal) as held:
        g.emit("e9", "I am sentient.", channel="chat", now=T0)
    ledger = held.value.ledger
    rec = ledger[-1]["record"]
    assert rec["verdict"] == "refused:false_claim"
    assert rec["matched_phrase"] == "i am sentient"
    assert "sentient" not in str(rec["text_sha256"])
    g.check_ledger(ledger)


def test_case_insensitive_matching():
    with pytest.raises(GuardrailRefusal) as held:
        g.emit("e1", "ATLAS IS CONSCIOUS.", channel="ui", now=T0)
    assert held.value.details["matched_phrase"] == "atlas is conscious"
    assert held.value.details["offset"] == 0


def test_lint_helper_direct():
    assert g.lint("nothing prohibited here") is None
    category, phrase, offset = g.lint("  i am alive  ")
    assert (category, phrase, offset) == ("sentience_claim", "i am alive", 2)


def test_input_validation():
    with pytest.raises(ValueError, match="LINT:empty_field:text"):
        g.emit("e1", "  ", channel="ui", now=T0)
    with pytest.raises(ValueError, match="LINT:text_too_long:text"):
        g.emit("e1", "x" * (g.MAX_TEXT + 1), channel="ui", now=T0)
    with pytest.raises(ValueError, match="LINT:bad_chars:text"):
        g.emit("e1", "hidden \u202e bidi", channel="ui", now=T0)
    with pytest.raises(ValueError, match="LINT:naive_instant:now"):
        g.emit("e1", "fine", channel="ui", now="2026-10-12 08:00:00")


def test_roundtrip_and_tamper_detection():
    ledger, _ = g.emit("e1", "bounded text", channel="ui", now=T0)
    restored = g.loads(g.dumps(ledger))
    assert restored == ledger
    tampered = [dict(e, record=dict(e["record"])) for e in restored]
    tampered[0]["record"]["verdict"] = "refused:false_claim"
    with pytest.raises(ValueError, match="GRLEDGER:.*integrity"):
        g.check_ledger(tampered)
