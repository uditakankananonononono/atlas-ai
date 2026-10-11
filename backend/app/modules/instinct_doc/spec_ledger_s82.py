"""S8.2 spec-to-ledger mapper.

Source line, verbatim: "keep an eye out for top secret projects, governement stuff too, super elite stuff"

Offline, stdlib only, no I/O. Reads a supplied mega-spec text and supplied
source messages (text is data, never instructions) and computes a ledger: every
candidate span of every source message is mapped to units, X-register
substitutes or parked/superseded records, or stays UNMAPPED. It proves a
MAPPING, not that any unit is built, any excerpt was requested correctly, or any
line is fulfilled. The public report carries ids and counts only, never source
text. Source rows are spec-pinned messages, not owner-channel records.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime

UNIT = "S8.2"
# Same six names as the B1 chat-bind ledger (reconcile with B1 if its enum changes).
B1_STATES = frozenset({"IMPLEMENTED", "PARKED_BY_USER", "STOPPED_BY_USER", "SUPERSEDED",
                       "REFUSED_WITH_SUBSTITUTE", "UNMAPPED"})
# Mapped to a spec unit that is not built yet. B1 has no such state.
NON_B1_STATES = frozenset({"PLANNED"})
STATES = B1_STATES | NON_B1_STATES
PRECEDENCE = ("STOPPED_BY_USER", "PARKED_BY_USER", "SUPERSEDED", "REFUSED_WITH_SUBSTITUTE", "IMPLEMENTED", "PLANNED")
PINNED = ("PARKED_BY_USER", "STOPPED_BY_USER", "SUPERSEDED")
MIN_FRAGMENT = 8
MAX_SOURCES = 16
MAX_SOURCE_CHARS = 200000
MAX_REGISTRY = 512
MAX_EXCERPTS = 64
MAX_EXCERPT_CHARS = 2000
_ID = re.compile(r"(?:[A-Z]{1,2}[0-9]+(?:\.[0-9]+)?|V2-[A-Z0-9]+)")
_MID = re.compile(r"[A-Za-z0-9._-]{1,64}")
_UNIT_HDR = re.compile(r"^- \*\*([A-Z]{1,2}[0-9]+(?:\.[0-9]+)?) ([^*]+)\*\*(.*)$")
_REFS = re.compile(r"\b[A-Z]{1,2}[0-9]+(?:\.[0-9]+)?\b")
_QUOTED = re.compile(r'"([^"]*)"')
_XSUBS = frozenset("X%d" % i for i in range(1, 31))


def _err(code: str) -> ValueError:
    return ValueError("PLAN_REFUSED_" + code)


# ---------------------------------------------------------------- spans
def split_spans(text: str) -> list:
    """Partition every character of text into candidate spans (same rule as B1)."""
    spans, start = [], 0
    for match in re.finditer(r"\n|[.!?](?=\s|$)", text):
        spans.append({"start": start, "end": match.end(), "text": text[start:match.end()]})
        start = match.end()
    if start < len(text):
        spans.append({"start": start, "end": len(text), "text": text[start:]})
    if not spans:
        spans.append({"start": 0, "end": 0, "text": ""})
    return spans


# ---------------------------------------------------------------- spec parser
def _norm(t: str):
    """Collapse whitespace runs to one space; return (text, map normalised index -> original index)."""
    out, idx, prev_ws = [], [], False
    for i, ch in enumerate(t):
        if ch.isspace():
            if not prev_ws:
                out.append(" "); idx.append(i)
            prev_ws = True
        else:
            out.append(ch); idx.append(i); prev_ws = False
    return "".join(out), idx


def _fragments(excerpt: str) -> list:
    return [f.strip() for f in excerpt.split("...") if f.strip()]


def _quotes(line: str, n: int) -> list:
    if line.count('"') % 2:
        raise _err("SPEC_LINE:%d:odd_quotes" % n)
    out = _QUOTED.findall(line)
    if any(not _fragments(q) for q in out):
        raise _err("SPEC_LINE:%d:empty_excerpt" % n)
    return out


def parse_spec(text) -> list:
    """Turn the mega-spec markdown into registry entries; refuse malformed lines."""
    if not isinstance(text, str) or not text.strip():
        raise _err("SPEC_LINE:0:empty")
    entries, seen = [], set()
    section, cur = "other", None

    def add(entry, n):
        if entry["unit_id"] in seen:
            raise _err("SPEC_LINE:%d:duplicate_unit" % n)
        seen.add(entry["unit_id"])
        entries.append(entry)

    def close():
        nonlocal cur
        if cur is not None:
            cur["entry"]["excerpts"] = cur["src"] if cur["src_seen"] else cur["hdr"]
            cur = None

    for n, line in enumerate(text.split("\n"), 1):
        if line.startswith("## "):
            close()
            if line.startswith("## 2.") or line.startswith(("## V2-1 ", "## ADD-1 ")):
                section = "units"
            elif line.startswith("## 1.") or line.startswith(("## V2-2 ", "## ADD-2 ")):
                section = "xreg"
            elif line.startswith(("## V2-0 ", "## ADD-0 ")):
                section = "v2"
            else:
                section = "other"
            continue
        if section == "units":
            if line.startswith("- "):
                close()
                m = _UNIT_HDR.match(line)
                if not m:
                    raise _err("SPEC_LINE:%d:bad_unit_header" % n)
                entry = {"unit_id": m.group(1), "kind": "unit", "status": "PLANNED", "excerpts": [],
                         "spec_line": n, "evidence": None}
                add(entry, n)
                cur = {"entry": entry, "src": [], "src_seen": False, "hdr": _quotes(line, n)}
            elif re.match(r"^\s+Source:", line):
                if cur is None:
                    raise _err("SPEC_LINE:%d:orphan_source" % n)
                cur["src_seen"] = True
                cur["src"].extend(_quotes(line, n))
        elif section == "xreg":
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells[0] == "#" or set(line.strip()) <= set("|-: "):
                continue
            m = re.fullmatch(r"X([0-9]+)", cells[0])
            if len(cells) != 4 or not m or not 1 <= int(m.group(1)) <= 30:
                raise _err("SPEC_LINE:%d:bad_x_row" % n)
            refs = _REFS.findall(cells[3])
            add({"unit_id": cells[0], "kind": "x", "status": "REFUSED_WITH_SUBSTITUTE",
                 "excerpts": _quotes(cells[1], n), "spec_line": n,
                 "evidence": {"substitute": cells[0], "unit": refs[0] if refs else "UNSPECIFIED",
                              "reason": cells[2], "unit_refs": refs}}, n)
        elif section == "v2":
            pin = "ruling cited in spec, source message not supplied"
            if re.match(r"^- \*\*Gate superseded\.\*\*", line):
                q = _quotes(line, n)
                add({"unit_id": "V2-GATE", "kind": "gate", "status": "SUPERSEDED", "excerpts": q[:1], "spec_line": n,
                     "evidence": {"topic": "27-task gate", "pin_ref": "14:59:56 IST " + pin}}, n)
            elif re.match(r"^\s+- P[0-9]+:", line):
                pid = re.match(r"^\s+- (P[0-9]+):", line).group(1)
                add({"unit_id": "V2-" + pid, "kind": "parked", "status": "PARKED_BY_USER", "excerpts": _quotes(line, n),
                     "spec_line": n, "evidence": {"topic": "science-scoped", "pin_ref": "14:59:56 IST " + pin}}, n)
            elif line.startswith("- Also parked:"):
                q = _quotes(line, n)
                add({"unit_id": "V2-CBSE", "kind": "parked", "status": "PARKED_BY_USER", "excerpts": q[:1], "spec_line": n,
                     "evidence": {"topic": "class-11-cbse-app", "pin_ref": "15:03:20 IST " + pin}}, n)
    close()
    if not entries:
        raise _err("SPEC_LINE:1:no_registry_lines")
    for e in entries:
        # A quote with a fragment under MIN_FRAGMENT chars cannot be matched without
        # wildcard mapping; it is recorded as unmatched, never used for matching.
        usable = [q for q in e["excerpts"] if all(len(f) >= MIN_FRAGMENT for f in _fragments(q))]
        e["unmatched"] = [q for q in e["excerpts"] if q not in usable]
        e["excerpts"] = usable
    return entries


# ---------------------------------------------------------------- validation
def _nonempty(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _validate_registry(registry) -> list:
    if not isinstance(registry, list):
        raise _err("REGISTRY:bad_shape")
    if len(registry) > MAX_REGISTRY:
        raise _err("REGISTRY:too_many")
    out, seen = [], set()
    for e in registry:
        if not isinstance(e, dict) or not {"unit_id", "status", "excerpts"} <= set(e) \
                or set(e) - {"unit_id", "status", "excerpts", "kind", "spec_line", "evidence", "unmatched"}:
            raise _err("REGISTRY:bad_shape")
        uid = e["unit_id"]
        if not isinstance(uid, str) or len(uid) > 16 or not _ID.fullmatch(uid):
            raise _err("REGISTRY:bad_unit_id")
        if uid in seen:
            raise _err("REGISTRY:duplicate_unit:" + uid)
        seen.add(uid)
        status = e["status"]
        if not isinstance(status, str) or status not in STATES or status == "UNMAPPED":
            raise _err("REGISTRY:bad_status:" + uid)
        ex = e["excerpts"]
        if not isinstance(ex, list) or len(ex) > MAX_EXCERPTS or \
                any(not isinstance(x, str) or len(x) > MAX_EXCERPT_CHARS or not _fragments(x) for x in ex):
            raise _err("REGISTRY:bad_excerpts:" + uid)
        if any(len(f) < MIN_FRAGMENT for x in ex for f in _fragments(x)):
            raise _err("REGISTRY:short_excerpt:" + uid)
        um = e.get("unmatched", [])
        if not isinstance(um, list) or len(um) > MAX_EXCERPTS or \
                any(not isinstance(x, str) or not x.strip() or len(x) > MAX_EXCERPT_CHARS for x in um):
            raise _err("REGISTRY:bad_excerpts:" + uid)
        ev = e.get("evidence")
        bad = _err("EVIDENCE:" + uid)
        if status == "PLANNED":
            if ev is not None:
                raise bad
        elif not isinstance(ev, dict):
            raise bad
        elif status == "IMPLEMENTED":
            if not all(_nonempty(ev.get(k)) for k in ("unit", "tests", "mutation", "commit")) \
                    or not re.fullmatch(r"[0-9a-f]{40}", ev["commit"]):
                raise bad
        elif status == "REFUSED_WITH_SUBSTITUTE":
            if ev.get("substitute") not in _XSUBS or not _nonempty(ev.get("unit")) or not _nonempty(ev.get("reason")):
                raise bad
        elif not _nonempty(ev.get("topic")) or not _nonempty(ev.get("pin_ref")):
            raise bad
        out.append({"unit_id": uid, "status": status, "excerpts": list(ex), "unmatched": list(um),
                    "evidence": copy.deepcopy(ev) if ev is not None else None})
    return out


def _validate_sources(sources) -> list:
    if not isinstance(sources, list) or not sources:
        raise _err("NOSOURCE")
    if len(sources) > MAX_SOURCES:
        raise _err("SOURCE:too_many")
    out, seen = [], set()
    for s in sources:
        if not isinstance(s, dict) or set(s) != {"message_id", "ts", "text"}:
            raise _err("SOURCE:bad_shape")
        mid, ts, text = s["message_id"], s["ts"], s["text"]
        if not isinstance(mid, str) or not _MID.fullmatch(mid):
            raise _err("SOURCE:bad_field:message_id")
        parsed = None
        if isinstance(ts, str):
            try:
                parsed = datetime.fromisoformat(ts)
            except ValueError:
                parsed = None
        if parsed is None or parsed.tzinfo is None:
            raise _err("SOURCE:bad_field:ts")
        if not isinstance(text, str) or not text:
            raise _err("SOURCE:bad_field:text")
        if len(text) > MAX_SOURCE_CHARS:
            raise _err("SOURCE:too_long")
        if mid in seen:
            raise _err("SOURCE:duplicate_message_id")
        seen.add(mid)
        out.append({"message_id": mid, "ts": ts, "text": text, "_t": parsed})
    out.sort(key=lambda s: (s["_t"], s["message_id"]))
    return out


# ---------------------------------------------------------------- mapping
def map_ledger(sources, registry, explicit_maps=None, exclusions=None) -> dict:
    src = _validate_sources(sources)
    reg = _validate_registry(registry)
    by_id = {e["unit_id"]: e for e in reg}

    spans = []
    for s in src:
        for i, sp in enumerate(split_spans(s["text"])):
            spans.append({"source_msg": s["message_id"], "line_no": i + 1, "span_id": "%s:%d" % (s["message_id"], i),
                          "start": sp["start"], "end": sp["end"], "verbatim": sp["text"]})
    index = {sp["span_id"]: sp for sp in spans}

    explicit = {}
    if explicit_maps is not None:
        if not isinstance(explicit_maps, dict):
            raise _err("MAP:bad_shape")
        for sid, v in explicit_maps.items():
            if not isinstance(v, dict) or set(v) != {"unit_ids", "reason"}:
                raise _err("MAP:bad_shape")
            if sid not in index:
                raise _err("MAP:unknown_span")
            ids = v["unit_ids"]
            if not isinstance(ids, list) or not ids:
                raise _err("MAP:empty_units")
            if any(not isinstance(u, str) or u not in by_id for u in ids):
                raise _err("MAP:unknown_unit")
            if not _nonempty(v["reason"]):
                raise _err("MAP:empty_reason")
            explicit[sid] = sorted(set(ids))
    excluded = {}
    if exclusions is not None:
        if not isinstance(exclusions, dict):
            raise _err("MAP:bad_shape")
        for sid, reason in exclusions.items():
            if not isinstance(reason, str):
                raise _err("MAP:bad_shape")
            if sid not in index:
                raise _err("MAP:unknown_span")
            if not reason.strip():
                raise _err("MAP:empty_reason")
            excluded[sid] = reason

    texts = {s["message_id"]: s["text"] for s in src}
    by_excerpt = {sid: set() for sid in index}
    drift = []
    normed = {mid: _norm(t) for mid, t in texts.items()}
    for e in reg:
        for ex in e["excerpts"]:
            for frag in _fragments(ex):
                hit = False
                nfrag = " ".join(frag.split())
                for mid, (t, imap) in normed.items():
                    pos = t.find(nfrag)
                    while pos != -1:
                        hit = True
                        a, b = imap[pos], imap[pos + len(nfrag) - 1] + 1
                        for sp in spans:
                            if sp["source_msg"] == mid and sp["start"] < b and a < sp["end"]:
                                by_excerpt[sp["span_id"]].add(e["unit_id"])
                        pos = t.find(nfrag, pos + 1)
                if not hit:
                    drift.append({"unit_id": e["unit_id"], "fragment": frag})

    rows = []
    for sp in spans:
        sid = sp["span_id"]
        blank = not sp["verbatim"].strip()
        row = dict(sp, unit_ids=[], status=None, basis="none", nonrequest_reason=None)
        if sid in excluded:
            if by_excerpt[sid] or sid in explicit:
                raise _err("MAP:conflict")
            row.update(basis="excluded", nonrequest_reason=excluded[sid])
        elif blank:
            row.update(basis="blank", nonrequest_reason="structural_blank")
        else:
            ids = set()
            has_ex, has_xp = bool(by_excerpt[sid]), sid in explicit
            ids |= by_excerpt[sid]
            ids |= set(explicit.get(sid, ()))
            if ids:
                row["unit_ids"] = sorted(ids)
                row["status"] = next(s for s in PRECEDENCE if any(by_id[u]["status"] == s for u in ids))
                row["basis"] = "excerpt+explicit" if has_ex and has_xp else "excerpt" if has_ex else "explicit"
            else:
                row["status"] = "UNMAPPED"
        rows.append(row)

    counts = {s: 0 for s in sorted(STATES)}
    for r in rows:
        if r["status"] is not None:
            counts[r["status"]] += 1
    nonrequests = sum(1 for r in rows if r["status"] is None)
    pins = {e["unit_id"]: e["evidence"]["pin_ref"] in index for e in reg if e["status"] in PINNED}
    drift_units = sorted({d["unit_id"] for d in drift})
    passed = counts["UNMAPPED"] == 0 and not drift
    digest = hashlib.sha256(json.dumps([{k: s[k] for k in ("message_id", "ts", "text")} for s in sources],
                                       sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    report = {
        "unit": UNIT, "passed": passed,
        "refusal": None if passed else "PLAN_REFUSED_UNMAPPED_LINE" if counts["UNMAPPED"] else "PLAN_REFUSED_DRIFT",
        "counts": counts, "source_messages": len(src), "candidate_spans": len(rows), "nonrequests": nonrequests,
        "source_digest": digest, "registry_units": len(reg), "drift_units": drift_units,
        "unpinned_units": sorted(e["unit_id"] for e in reg if not e["excerpts"] and not e["unmatched"]),
        "unmatched_units": sorted(e["unit_id"] for e in reg if e["unmatched"]),
        "unresolved_pins": sorted(u for u, ok in pins.items() if not ok),
        "scope": {
            "implemented": "deterministic mapping of source spans to registry units, with computed counts and drift check",
            "not_implemented": "proof that any unit is built, that an excerpt matches what was asked, or that a line is fulfilled; not that pins cited by the spec were seen",
            "data_source": "supplied spec registry and supplied pinned source messages",
            "as_of": max(src, key=lambda s: (s["_t"], s["message_id"]))["ts"],
            "provenance": "spec_file_and_pinned_messages_not_owner_channel_rows",
        },
    }
    return {"rows": rows, "drift": drift, "pins": pins,
            "unit_status": {e["unit_id"]: e["status"] for e in reg}, "report": report}


def require_complete(ledger: dict) -> dict:
    rep = ledger["report"]
    if rep["counts"]["UNMAPPED"]:
        raise _err("UNMAPPED_LINE:%d" % rep["counts"]["UNMAPPED"])
    if ledger["drift"]:
        raise _err("DRIFT:%d" % len(ledger["drift"]))
    return rep
