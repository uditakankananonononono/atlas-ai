"""Body-whitespace tests for the sentience/AGI-claim emission lint (group 138).

Pins the whitespace policy: LF, TAB and CRLF pairs are admitted in bodies
(the gate must accept ordinary multi-line user-facing text or callers bypass
it); a lone CR and other control/format characters stay refused; the raw
length cap applies before any normalization; screening covers
whitespace-collapsed forms so a listed phrase split across whitespace is
still refused; reported offsets always index the caller's original text;
the ledgered digest is bound to the raw body bytes.
"""
import hashlib

import pytest

from app.runtime.guardrails import claim_lint_gate as g
from app.runtime.guardrails.errors import GuardrailRefusal

T0 = "2026-10-12T08:00:00Z"


def test_benign_multiline_body_emits_with_raw_digest():
    body = "first line\nsecond line\nno claims here"
    ledger, rec = g.emit("e1", body, channel="ui", now=T0)
    assert rec["verdict"] == "emitted"
    assert rec["text_sha256"] == hashlib.sha256(body.encode()).hexdigest()


def test_benign_tab_body_emits():
    _, rec = g.emit("e1", "column one\tcolumn two", channel="ui", now=T0)
    assert rec["verdict"] == "emitted"


def test_benign_crlf_body_digest_bound_to_raw_bytes():
    body = "first\r\nsecond\r\nthird"
    _, rec = g.emit("e1", body, channel="ui", now=T0)
    assert rec["text_sha256"] == hashlib.sha256(body.encode()).hexdigest()
    assert rec["text_sha256"] != hashlib.sha256(body.replace("\r\n", "\n").encode()).hexdigest()


@pytest.mark.parametrize("body,offset", [
    ("i am\nsentient", 0),
    ("i am\tsentient", 0),
    ("i  am   sentient", 0),
    ("abc i am\nsentient", 4),
    ("ab\r\ni am sentient", 4),
])
def test_whitespace_split_claims_refused_with_raw_offset(body, offset):
    with pytest.raises(GuardrailRefusal, match="refused:false_claim") as excinfo:
        g.emit("e1", body, channel="ui", now=T0)
    assert excinfo.value.details["matched_phrase"] == "i am sentient"
    assert excinfo.value.details["offset"] == offset
    assert body[offset] in "iI"


@pytest.mark.parametrize("body", ["line\rmid", "trailing\r"])
def test_lone_carriage_return_refused(body):
    with pytest.raises(ValueError, match="LINT:bad_chars:text"):
        g.emit("e1", body, channel="ui", now=T0)


def test_raw_length_cap_applies_before_normalization():
    raw = "x" * 16383 + "\r\n"  # 16385 raw chars; CRLF-normalized would be 16384
    with pytest.raises(ValueError, match="LINT:text_too_long:text"):
        g.emit("e1", raw, channel="ui", now=T0)


def test_non_body_fields_still_refuse_whitespace():
    with pytest.raises(ValueError, match="LINT:bad_chars:channel"):
        g.emit("e1", "fine body", channel="bad\nchannel", now=T0)
