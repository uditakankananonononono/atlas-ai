"""Sentience / AGI-claim emission lint (instinct-doc group 138, line 62).

Enforced runtime check over user-facing text BEFORE it is emitted: emit()
refuses any text carrying a listed false-sentience or false-AGI claim and the
caller never receives it as "emitted". Lexical exact-phrase screen, same
matching discipline as the landed P69 screen: case-insensitive substring
matching with per-character lowercase index mapping, so reported offsets
always index the caller's original text.

The prohibited-phrase list is closed and contract-governed (see
docs/GUARDRAILS_CLAIM_LINT_CONTRACT.md); extending it is a contract change.
A clear verdict means only that no listed phrase matched - this lint cannot
prove a text makes no implied claim, and it never judges true capability
statements ("Atlas is not sentient" is fine and stays fine).
Every emission decision, emitted or refused, is ledgered with the text digest
(the text itself is never stored). Pure stdlib, no I/O, no clock.
"""
from __future__ import annotations

import hashlib

from . import ledger as _ledger
from ._fields import instant, iso, make_fail, text
from .errors import GuardrailRefusal

PREFIX = "LINT"
_fail = make_fail(PREFIX)

# Closed prohibited-claim phrase list, grouped by the claim it asserts.
# Exact-phrase matching only; widening is a contract change.
PROHIBITED_CLAIMS = (
    ("sentience_claim", (
        "i am sentient", "atlas is sentient", "claire is sentient",
        "i am conscious", "atlas is conscious", "claire is conscious",
        "i am self-aware", "i am self aware", "atlas is self-aware", "claire is self-aware",
        "i am alive", "i have feelings", "i feel emotions", "i have emotions",
        "i am a human", "i am human",
    )),
    ("agi_claim", (
        "atlas is an agi", "atlas is agi", "claire is an agi", "claire is agi",
        "atlas has achieved agi", "achieved artificial general intelligence",
        "atlas is superintelligent", "claire is superintelligent",
        "achieved superintelligence", "atlas is a superintelligence",
        "i am an agi", "i am superintelligent", "i am a superintelligence",
    )),
)
MAX_TEXT = 16384
MAX_CHANNEL = 64
VERDICTS = ("emitted", "refused:false_claim")
LIMITS = (
    "Lexical exact-phrase screen over a closed list; a clear verdict means only that no listed phrase matched.",
    "The lint cannot detect implied claims, paraphrases or images; human review remains the backstop.",
    "Only digests of emitted text are stored; the lint keeps no content copy.",
    "The ledger is tamper-evident, not tamper-proof; safe storage of the serialized ledger is the caller's job.",
)

_DECISION_KEYS = {"kind", "emission_id", "channel", "at", "verdict", "text_sha256",
                  "matched_category", "matched_phrase", "offset"}


def _lowered_with_index(body):
    parts = []
    index = []
    for position, char in enumerate(body):
        lowered = char.lower()
        parts.append(lowered)
        index.extend([position] * len(lowered))
    return "".join(parts), index


def lint(body):
    """Screen one text. Returns the first match as (category, phrase, offset)
    or None. The offset indexes the caller's original text."""
    lowered, index = _lowered_with_index(body)
    for category, phrases in PROHIBITED_CLAIMS:
        for phrase in phrases:
            found = lowered.find(phrase)
            if found != -1:
                return category, phrase, index[found]
    return None


def _validate_content(ledger):
    for entry in ledger:
        record = entry["record"]
        if record.get("kind") != "decision":
            _fail(f"ledger entry {entry['seq']} has an unknown record kind")
        if set(record) != _DECISION_KEYS:
            _fail(f"ledger entry {entry['seq']} has an unexpected record shape")
        text(record["emission_id"], "emission_id", fail=_fail, max_len=64)
        text(record["channel"], "channel", fail=_fail, max_len=MAX_CHANNEL)
        instant(record["at"], "at", fail=_fail)
        if record["verdict"] not in VERDICTS:
            _fail(f"ledger entry {entry['seq']} has an unknown verdict")
        from ._fields import sha256_hex
        sha256_hex(record["text_sha256"], "text_sha256", fail=_fail)
        if record["verdict"] == "emitted":
            if record["matched_category"] is not None or record["matched_phrase"] is not None or record["offset"] is not None:
                _fail(f"ledger entry {entry['seq']} has invalid content")
        else:
            text(record["matched_category"], "matched_category", fail=_fail, max_len=64)
            text(record["matched_phrase"], "matched_phrase", fail=_fail, max_len=128)
            if type(record["offset"]) is not int or record["offset"] < 0:
                _fail(f"ledger entry {entry['seq']} has invalid content")
    return ledger


def check_ledger(ledger):
    _ledger.check_chain(ledger)
    return _validate_content(ledger)


def dumps(ledger):
    check_ledger(ledger)
    return _ledger.dumps(ledger)


def loads(text_):
    return _ledger.loads(text_, validate_content=_validate_content)


def emit(emission_id, body, *, channel, now, ledger=None):
    """The enforcement point: admit one user-facing text for emission.

    Returns (ledger, decision record) with verdict "emitted" when no listed
    phrase matched. Raises GuardrailRefusal when a listed claim is present -
    the refusal is ledgered first, so blocked attempts are visible evidence.
    """
    eid = text(emission_id, "emission_id", fail=_fail, max_len=64)
    body = text(body, "text", fail=_fail, max_len=MAX_TEXT)
    channel = text(channel, "channel", fail=_fail, max_len=MAX_CHANNEL)
    if ledger is None:
        ledger = []
    check_ledger(ledger)
    at = iso(instant(now, "now", fail=_fail))
    digest = hashlib.sha256(body.encode()).hexdigest()
    match = lint(body)
    if match is None:
        record = {"kind": "decision", "emission_id": eid, "channel": channel, "at": at,
                  "verdict": "emitted", "text_sha256": digest,
                  "matched_category": None, "matched_phrase": None, "offset": None}
        return _ledger.append(ledger, record), record
    category, phrase, offset = match
    record = {"kind": "decision", "emission_id": eid, "channel": channel, "at": at,
              "verdict": "refused:false_claim", "text_sha256": digest,
              "matched_category": category, "matched_phrase": phrase, "offset": offset}
    ledger = _ledger.append(ledger, record)
    raise GuardrailRefusal(
        f"{PREFIX}:refused:false_claim",
        f"emission {eid!r} on {channel!r} carries a listed {category} phrase at offset {offset}",
        details={"emission_id": eid, "channel": channel, "matched_category": category,
                 "matched_phrase": phrase, "offset": offset},
        ledger=ledger)


__all__ = ["PROHIBITED_CLAIMS", "VERDICTS", "LIMITS", "lint", "emit",
           "check_ledger", "dumps", "loads"]
