"""[1282] "Evidence Analysis": custody completeness and gaps over caller-declared evidence records.

Pure, hermetic and stdlib only: no files, no network, no clock, no randomness.
It takes the items the caller declares (id, type, source, timestamp, optional weight tag, optional chain
of custody transfers) and reports, per item, whether the declared custody chain is complete or which
mechanical gaps it has. Weight tags are passed through untouched; none is ever computed or invented.
It does not judge admissibility, authenticity, relevance or weight. The separate admissibility issue map
for this row lives in legal_support_1260_1309.py and is neither used nor replaced here.
"""
from __future__ import annotations

from datetime import datetime

SCOPE = "EVID1282 custody completeness only"
BOUNDARY = ("Mechanical consistency check of caller-declared custody records. It does not establish authenticity, "
            "admissibility, relevance, probative weight or that any transfer happened; weight tags are the caller's "
            "words, passed through. The admissibility issue map for row 1282 is legal_support_1260_1309.py, "
            "which this module neither calls nor replaces.")

MAX_ITEMS = 1000
MAX_EVENTS = 200
MAX_TEXT = 500
MAX_TAG = 64

_ITEM_REQUIRED = ("evidence_id", "type", "source", "timestamp")
_ITEM_OPTIONAL = ("weight_tag", "custody")
_EVENT_REQUIRED = ("from", "to", "at")
_EVENT_OPTIONAL = ("note",)


class EvidenceError(ValueError):
    pass


def _fail(msg):
    raise EvidenceError("EVID1282: " + msg)


def _text(v, where, limit=MAX_TEXT):
    if not isinstance(v, str) or not v.strip() or len(v) > limit or any(ord(c) < 32 or ord(c) == 127 for c in v):
        _fail(f"{where} must be a non-empty single-line string of at most {limit} characters")
    return v


def _when(v, where):
    if not isinstance(v, str):
        _fail(f"{where} must be an ISO-8601 timestamp with an explicit UTC offset")
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        _fail(f"{where} must be an ISO-8601 timestamp with an explicit UTC offset")
    if d.tzinfo is None or d.utcoffset() is None:
        _fail(f"{where} must be an ISO-8601 timestamp with an explicit UTC offset")
    return d


def _check_keys(d, required, optional, where):
    for k in required:
        if k not in d:
            _fail(f"{where} missing '{k}'")
    for k in d:
        if k not in required and k not in optional:
            _fail(f"{where} has unknown key '{k}'")


def _gap(code, index, detail):
    return {"code": code, "index": index, "detail": detail}


def analyze_evidence(items):
    if not isinstance(items, list):
        _fail("items must be a list")
    if not items:
        _fail("items must not be empty")
    if len(items) > MAX_ITEMS:
        _fail(f"too many items (limit {MAX_ITEMS})")
    seen, out = set(), []
    for n, it in enumerate(items):
        if not isinstance(it, dict):
            _fail(f"item {n} must be an object")
        _check_keys(it, _ITEM_REQUIRED, _ITEM_OPTIONAL, f"item {n}")
        eid = _text(it["evidence_id"], f"item {n} 'evidence_id'")
        if eid in seen:
            _fail(f"duplicate evidence_id {eid!r}")
        seen.add(eid)
        typ = _text(it["type"], f"item {n} 'type'")
        src = _text(it["source"], f"item {n} 'source'")
        t0 = _when(it["timestamp"], f"item {n} 'timestamp'")
        tag = None
        if "weight_tag" in it:
            tag = _text(it["weight_tag"], f"item {n} 'weight_tag'", MAX_TAG)
        custody = it.get("custody", [])
        if not isinstance(custody, list):
            _fail(f"item {n} 'custody' must be a list")
        if len(custody) > MAX_EVENTS:
            _fail(f"item {n} has too many custody events (limit {MAX_EVENTS})")
        events = []
        for j, e in enumerate(custody):
            where = f"item {n} custody event {j}"
            if not isinstance(e, dict):
                _fail(f"{where} must be an object")
            _check_keys(e, _EVENT_REQUIRED, _EVENT_OPTIONAL, where)
            frm = _text(e["from"], f"{where} 'from'")
            to = _text(e["to"], f"{where} 'to'")
            at = _when(e["at"], f"{where} 'at'")
            if "note" in e:
                _text(e["note"], f"{where} 'note'")
            events.append((frm, to, at))
        gaps = []
        if not events:
            gaps.append(_gap("CUSTODY_EMPTY", None, "no custody transfers were declared"))
            status = "NO_CUSTODY"
        else:
            for j, (frm, to, at) in enumerate(events):
                if j == 0:
                    if frm != src:
                        gaps.append(_gap("FIRST_FROM_NOT_SOURCE", 0,
                                         f"first transfer is from {frm!r} but the declared source is {src!r}"))
                else:
                    prev = events[j - 1]
                    if frm != prev[1]:
                        gaps.append(_gap("HOLDER_DISCONTINUITY", j,
                                         f"transfer {j} is from {frm!r} but the previous transfer went to {prev[1]!r}"))
                    if at < prev[2]:
                        gaps.append(_gap("TIME_REVERSED", j, f"transfer {j} is dated before transfer {j - 1}"))
                if at < t0:
                    gaps.append(_gap("BEFORE_ITEM_TIMESTAMP", j, f"transfer {j} is dated before the item timestamp"))
            status = "CUSTODY_GAPS" if gaps else "CUSTODY_COMPLETE"
        out.append({"evidence_id": eid, "type": typ, "source": src, "timestamp": it["timestamp"],
                    "weight_tag": tag, "custody_status": status, "gaps": gaps, "custody_events": len(events)})
    return {
        "scope": SCOPE, "boundary": BOUNDARY, "items": out,
        "summary": {"total": len(out),
                    "complete": sum(1 for x in out if x["custody_status"] == "CUSTODY_COMPLETE"),
                    "with_gaps": sum(1 for x in out if x["custody_status"] == "CUSTODY_GAPS"),
                    "no_custody": sum(1 for x in out if x["custody_status"] == "NO_CUSTODY")},
        "admissibility_judged": False, "weights_invented": False,
    }
