"""P246|L194 line coverage over a supplied instinct-doc line map (V3 shape).

Source line, verbatim: "5. Verify every line, every word, every module, every tool,
every benchmark, every test, and every discovery claim."

This is a bounded declared-input check, not verification. It reads a line map and
a list of evidence declarations and reports which distinct requirement lines have a
declared COVERED_BY_DECLARATION record and which do not. It does not read the doc,
judge whether any evidence is adequate or true, or claim that any line is fulfilled.
Offline, standard library only, no I/O. Namespace package: no __init__.py here.
"""
from __future__ import annotations

import re
from datetime import datetime

COVERED = "COVERED_BY_DECLARATION"
UNCOVERED = "UNCOVERED"
HEADER_MARK = "SECTION HEADER"
MAX_ROWS = 2000
MAX_EVIDENCE = 20000
MAX_TEXT = 2000
MAX_REF = 2048
_ID = re.compile(r"P([1-9][0-9]*)\|L([1-9][0-9]*)")
_ROW_FIELDS = {"P", "L", "class", "mission", "summary", "dup_of"}
_EV_FIELDS = {"line_id", "status", "evidence_ref", "declared_at", "source"}
_REQ_FIELDS = {"line_map", "evidence", "include_classes"}


class LineCoverageError(ValueError):
    """Exact refusal of a malformed request."""


def _posint(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v if v > 0 else None
    if isinstance(v, str) and re.fullmatch(r"[1-9][0-9]*", v):
        return int(v)
    return None


def _check_time(v):
    if not isinstance(v, str) or not v:
        return False
    try:
        dt = datetime.fromisoformat(v[:-1] + "+00:00" if v.endswith("Z") else v)
    except ValueError:
        return False
    return dt.tzinfo is not None and dt.utcoffset() is not None


def _rows(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ROWS:
        raise LineCoverageError(f"line_map must be a list of 1..{MAX_ROWS} rows")
    rows, seen = {}, set()
    for i, r in enumerate(raw):
        w = f"line_map row {i}"
        if not isinstance(r, dict):
            raise LineCoverageError(f"{w} must be an object")
        for k in sorted(r):
            if k not in _ROW_FIELDS:
                raise LineCoverageError(f"{w} unknown field: {k}")
        p, l = _posint(r.get("P")), _posint(r.get("L"))
        if p is None:
            raise LineCoverageError(f"{w} P must be a positive integer")
        if l is None:
            raise LineCoverageError(f"{w} L must be a positive integer")
        cls = r.get("class")
        if not isinstance(cls, str) or not cls:
            raise LineCoverageError(f"{w} class must be a non-empty string")
        summary = r.get("summary", "")
        if not isinstance(summary, str) or len(summary) > MAX_TEXT:
            raise LineCoverageError(f"{w} summary must be a string up to {MAX_TEXT} chars")
        mission = r.get("mission", "")
        if not isinstance(mission, str) or len(mission) > MAX_TEXT:
            raise LineCoverageError(f"{w} mission must be a string up to {MAX_TEXT} chars")
        dup = r.get("dup_of", "")
        if not isinstance(dup, str) or not (dup == "" or dup == HEADER_MARK or _ID.fullmatch(dup)):
            raise LineCoverageError(f"{w} dup_of must be empty, SECTION HEADER or P<n>|L<n>")
        lid = f"P{p}|L{l}"
        if lid in seen:
            raise LineCoverageError(f"duplicate line id in line_map: {lid}")
        seen.add(lid)
        kind = "decorative" if cls == "DECORATIVE" else "header" if dup == HEADER_MARK else "duplicate" if dup else "distinct"
        rows[lid] = {"id": lid, "P": p, "L": l, "class": cls, "mission": mission, "summary": summary,
                     "dup_of": dup if kind == "duplicate" else "", "kind": kind, "_row": i}
    for lid, r in rows.items():
        if r["kind"] != "duplicate":
            continue
        if r["dup_of"] == lid:
            raise LineCoverageError(f"line_map row {r['_row']} dup_of points at itself")
        if r["dup_of"] not in rows:
            raise LineCoverageError(f"line_map row {r['_row']} dup_of {r['dup_of']} not found")
    return rows


def _canonical(rows):
    """Follow dup_of chains to the final line; refuse cycles."""
    out = {}
    for lid in sorted(rows, key=lambda k: (rows[k]["L"], rows[k]["P"])):
        cur, trail = lid, [lid]
        while rows[cur]["kind"] == "duplicate":
            cur = rows[cur]["dup_of"]
            if cur in trail:
                raise LineCoverageError(f"duplicate cycle at {min(trail, key=lambda k: (rows[k]['L'], rows[k]['P']))}")
            trail.append(cur)
        out[lid] = cur
    return out


def _evidence(raw):
    if not isinstance(raw, list) or len(raw) > MAX_EVIDENCE:
        raise LineCoverageError(f"evidence must be a list of 0..{MAX_EVIDENCE} records")
    out = []
    for i, e in enumerate(raw):
        w = f"evidence {i}"
        if not isinstance(e, dict):
            raise LineCoverageError(f"{w} must be an object")
        for k in sorted(e):
            if k not in _EV_FIELDS:
                raise LineCoverageError(f"{w} unknown field: {k}")
        lid = e.get("line_id")
        if not isinstance(lid, str) or not _ID.fullmatch(lid):
            raise LineCoverageError(f"{w} line_id must match P<n>|L<n> exactly")
        status = e.get("status")
        if status not in (COVERED, UNCOVERED):
            raise LineCoverageError(f"{w} status must be COVERED_BY_DECLARATION or UNCOVERED")
        ref = e.get("evidence_ref", "")
        if not isinstance(ref, str) or len(ref) > MAX_REF or (status == COVERED and not ref):
            raise LineCoverageError(f"{w} evidence_ref must be a non-empty string up to {MAX_REF} chars when COVERED_BY_DECLARATION")
        if not _check_time(e.get("declared_at")):
            raise LineCoverageError(f"{w} declared_at must be an ISO-8601 timestamp with timezone")
        if e.get("source") not in ("self", "audit"):
            raise LineCoverageError(f"{w} source must be self or audit")
        out.append({"index": i, "line_id": lid, "status": status, "evidence_ref": ref,
                    "declared_at": e["declared_at"], "source": e["source"]})
    return out


def _order(rows):
    return lambda lid: (rows[lid]["L"], rows[lid]["P"])


def _item(r):
    return {"line_id": r["id"], "class": r["class"], "mission": r["mission"], "summary": r["summary"],
            "words": r["summary"].split()}  # display only, never a match key


def compute_line_coverage(request):
    if not isinstance(request, dict):
        raise LineCoverageError("request must be an object")
    for k in sorted(request):
        if k not in _REQ_FIELDS:
            raise LineCoverageError(f"unknown request field: {k}")
    rows = _rows(request.get("line_map"))
    evid = _evidence(request.get("evidence", []))
    classes = request.get("include_classes", ["NON-SCIENCE"])
    if (not isinstance(classes, list) or not classes or not all(isinstance(c, str) and c for c in classes)):
        raise LineCoverageError("include_classes must be a non-empty list of strings")
    classes = sorted(set(classes))
    canon = _canonical(rows)
    key = _order(rows)

    by_kind = {k: [r for r in rows.values() if r["kind"] == k] for k in ("decorative", "header", "duplicate", "distinct")}
    distinct_by_class, dup_by_class = {}, {}
    for r in by_kind["distinct"]:
        distinct_by_class[r["class"]] = distinct_by_class.get(r["class"], 0) + 1
    for r in by_kind["duplicate"]:
        dup_by_class[r["class"]] = dup_by_class.get(r["class"], 0) + 1
    buckets = {
        "source_rows": len(rows),
        "decorative_rows": len(by_kind["decorative"]),
        "non_decorative_source_rows": len(rows) - len(by_kind["decorative"]),
        "section_header_rows": len(by_kind["header"]),
        "duplicate_rows": len(by_kind["duplicate"]),
        "distinct_requirements": len(by_kind["distinct"]),
        "distinct_by_class": dict(sorted(distinct_by_class.items())),
        "duplicate_rows_by_class": dict(sorted(dup_by_class.items())),
    }

    cross = []
    for r in sorted(by_kind["duplicate"], key=lambda r: key(r["id"])):
        c = rows[canon[r["id"]]]
        if c["class"] != r["class"]:
            cross.append({"line_id": r["id"], "own_class": r["class"], "canonical": c["id"], "canonical_class": c["class"]})

    unknown, non_req, rolled = [], [], []
    per = {}  # canonical id -> list of evidence
    for e in evid:
        lid = e["line_id"]
        if lid not in rows:
            unknown.append({"line_id": lid, "evidence_index": e["index"]})
            continue
        if rows[lid]["kind"] in ("header", "decorative"):
            non_req.append({"line_id": lid, "kind": rows[lid]["kind"], "evidence_index": e["index"]})
            continue
        target = canon[lid]
        if target != lid:
            rolled.append({"from": lid, "to": target, "evidence_index": e["index"]})
        per.setdefault(target, []).append(e)

    def state(target):
        recs = per.get(target, [])
        has_c = any(x["status"] == COVERED for x in recs)
        has_u = any(x["status"] == UNCOVERED for x in recs)
        return recs, has_c, has_u

    covered, uncovered, other_covered = [], [], []
    declared_uncovered, conflicts, self_only = [], [], []
    other_class = {}
    in_scope = 0
    for r in sorted(by_kind["distinct"], key=lambda r: key(r["id"])):
        recs, has_c, has_u = state(r["id"])
        if r["class"] not in classes:
            other_class.setdefault(r["class"], []).append(r["id"])
            if has_c and not has_u:
                other_covered.append({**_item(r), "evidence": _ev_list(recs)})
            continue
        in_scope += 1
        if has_u:
            declared_uncovered.append(r["id"])
        if has_c and has_u:
            conflicts.append(r["id"])
        if has_c and not has_u:
            covered.append({**_item(r), "evidence": _ev_list(recs)})
            if all(x["source"] == "self" for x in recs if x["status"] == COVERED):
                self_only.append(r["id"])
        else:
            uncovered.append(_item(r))

    return {
        "buckets": buckets,
        "denominator": {"classes": classes, "distinct_requirements": in_scope},
        "counts": {"covered": len(covered), "uncovered": len(uncovered)},
        "covered": covered,
        "uncovered": uncovered,
        "other_class_requirements": {c: ids for c, ids in sorted(other_class.items())},
        "other_class_covered": other_covered,
        "declared_uncovered": declared_uncovered,
        "conflicting_declarations": conflicts,
        "self_declared_only": self_only,
        "evidence_rolled_up": rolled,
        "unknown_line_evidence": unknown,
        "evidence_on_non_requirement_rows": non_req,
        "cross_class_duplicates": cross,
        "claims": {
            "basis": "declared evidence records matched by exact line id after duplicate roll-up; nothing was read or checked",
            "line_fulfilled": False,
            "evidence_adequacy_assessed": False,
            "universal_closure": False,
            "unit11_non_duplication": "UNVERIFIED",
        },
    }


def _ev_list(recs):
    return [{"status": x["status"], "evidence_ref": x["evidence_ref"], "declared_at": x["declared_at"],
             "source": x["source"], "evidence_index": x["index"]}
            for x in sorted(recs, key=lambda x: (x["source"], x["evidence_ref"], x["declared_at"], x["status"]))]
