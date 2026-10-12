"""Shared append-only, hash-chained ledger machinery for guardrail gates.

Same construction as m02 reviewed_execution: every gate decision is a record;
each ledger entry chains seq + record + prev_hash into record_hash. The chain
is tamper-evident, not tamper-proof: it detects unrehashed edits only, and
safe storage of a serialized ledger is the caller's job. Pure stdlib, no I/O,
no clock - callers inject timestamps inside the records themselves.
"""
from __future__ import annotations

import hashlib
import json

GENESIS_HASH = "0" * 64
MAX_RECORDS = 4096
MAX_SERIALIZED = 4_000_000


def _fail(message):
    raise ValueError("GRLEDGER: " + message)


def record_hash(seq, record, prev_hash):
    payload = json.dumps({"seq": seq, "record": record, "prev_hash": prev_hash},
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def append(ledger, record):
    """Append one record to a chain-verified ledger; returns a new list."""
    check_chain(ledger)
    if len(ledger) >= MAX_RECORDS:
        _fail(f"ledger exceeds {MAX_RECORDS} records")
    if type(record) is not dict or not record:
        _fail("record must be a non-empty dict")
    try:
        json.dumps(record, allow_nan=False)
    except (TypeError, ValueError):
        _fail("record must contain finite JSON values")
    seq = len(ledger)
    prev_hash = ledger[-1]["record_hash"] if ledger else GENESIS_HASH
    return ledger + [{"seq": seq, "record": record, "prev_hash": prev_hash,
                      "record_hash": record_hash(seq, record, prev_hash)}]


def check_chain(ledger):
    """Verify entry shape, sequence and hash chain. Returns the ledger.

    Record *content* validation (per-kind fields, cross-record order rules)
    belongs to the owning gate module, which calls this first and then its
    own content pass.
    """
    if type(ledger) is not list or len(ledger) > MAX_RECORDS:
        _fail(f"ledger must be a list of at most {MAX_RECORDS} entries")
    prev_hash = GENESIS_HASH
    for seq, entry in enumerate(ledger):
        if type(entry) is not dict or set(entry) != {"seq", "record", "prev_hash", "record_hash"}:
            _fail(f"ledger entry {seq} has an unexpected shape")
        if type(entry["record"]) is not dict or not entry["record"]:
            _fail(f"ledger entry {seq} has an invalid record")
        if entry["seq"] != seq or entry["prev_hash"] != prev_hash:
            _fail(f"ledger entry {seq} breaks the sequence chain")
        if entry["record_hash"] != record_hash(seq, entry["record"], prev_hash):
            _fail(f"ledger entry {seq} fails the integrity check")
        prev_hash = entry["record_hash"]
    return ledger


def dumps(ledger):
    """Serialize for caller-side persistence (canonical JSON)."""
    check_chain(ledger)
    return json.dumps(ledger, sort_keys=True, separators=(",", ":"))


def loads(text, *, validate_content=None):
    """Parse a serialized ledger, verifying the chain. validate_content, when
    given, is the owning gate's per-record content checker and runs after the
    structural chain pass."""
    if type(text) is not str or len(text) > MAX_SERIALIZED:
        _fail(f"serialized ledger must be text at most {MAX_SERIALIZED} characters")
    try:
        ledger = json.loads(text)
    except ValueError:
        _fail("serialized ledger is not valid JSON")
    check_chain(ledger)
    if validate_content is not None:
        validate_content(ledger)
    return [dict(entry, record=dict(entry["record"])) for entry in ledger]


__all__ = ["GENESIS_HASH", "MAX_RECORDS", "MAX_SERIALIZED",
           "record_hash", "append", "check_chain", "dumps", "loads"]
