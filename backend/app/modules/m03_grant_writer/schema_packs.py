"""Agency schema packs for science grants (M03 enhancement).

A schema pack is a versioned JSON file captured from one official call
(``data/schema_packs/<agency>/<program>/<version>.json``). Every rule in it -
deadline, page limit, required heading, reference count - carries the exact
``anchor`` sentence it was taken from, plus the source URL and retrieval time.
Nothing is inferred from memory.

- ``check`` runs a submission against the latest (or a named) pack: missing
  documents, page counts over the limit, required headings missing, URLs or
  DOIs in references where the call forbids them, too few reference writers,
  and the deadlines that apply to the applicant's field with time left.
- ``diff`` compares two versions of the same program (amendment tracking):
  moved deadlines, changed limits, added or removed documents.
- ``verify_source`` re-reads the official page and reports every anchor that
  no longer appears verbatim - the signal that the call was amended and the
  pack needs a new version. It never rewrites a pack itself.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

PACK_DIR = Path(__file__).parent / "data" / "schema_packs"
_URL_OR_DOI = re.compile(r"https?://|www\.|\bdoi:\s*10\.|\b10\.\d{4,9}/\S+", re.I)
_REQUIRED = ("agency", "program", "solicitation", "version", "source_url", "retrieved_at", "deadlines", "documents")


class PackNotFound(LookupError):
    pass


class PackInvalid(ValueError):
    pass


def _norm(text: str) -> str:
    return " ".join(text.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"').split()).lower()


def _loose(text: str) -> str:
    """Words only: markup, punctuation and spacing differences between the HTML
    page and a captured sentence must not look like an amendment."""
    return " " + " ".join(re.findall(r"[a-z0-9]+", text.lower())) + " "


def validate(pack: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in _REQUIRED if k not in pack]
    if missing:
        raise PackInvalid(f"pack missing {missing}")
    for group in ("deadlines", "documents", "counts", "criteria"):
        for item in pack.get(group, []):
            if not str(item.get("anchor", "")).strip():
                raise PackInvalid(f"{group} item {item.get('id') or item.get('name')} has no source anchor")
    for d in pack["deadlines"]:
        datetime.fromisoformat(f"{d['date']}T{d.get('time', '23:59')}")
        ZoneInfo(d.get("tz", "UTC"))
    return pack


def load_all(base: Path = PACK_DIR) -> dict[tuple[str, str], list[dict[str, Any]]]:
    packs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for path in sorted(base.glob("*/*/*.json")):
        pack = validate(json.loads(path.read_text()))
        packs.setdefault((pack["agency"].lower(), pack["program"].lower()), []).append(pack)
    for versions in packs.values():
        versions.sort(key=lambda p: p["version"])
    return packs


def get_pack(agency: str, program: str, version: str | None = None, base: Path = PACK_DIR) -> dict[str, Any]:
    versions = load_all(base).get((agency.lower(), program.lower()))
    if not versions:
        raise PackNotFound(f"{agency}/{program}")
    if version is None:
        return versions[-1]
    for p in versions:
        if p["version"] == version:
            return p
    raise PackNotFound(f"{agency}/{program}@{version}")


def catalog(base: Path = PACK_DIR) -> list[dict[str, Any]]:
    return [{"agency": v[-1]["agency"], "program": v[-1]["program"], "solicitation": v[-1]["solicitation"],
             "latest_version": v[-1]["version"], "versions": [p["version"] for p in v],
             "source_url": v[-1]["source_url"], "retrieved_at": v[-1]["retrieved_at"]}
            for v in load_all(base).values()]


def _deadline_at(d: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(f"{d['date']}T{d.get('time', '23:59')}").replace(tzinfo=ZoneInfo(d.get("tz", "UTC")))


def check(pack: dict[str, Any], submission: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    """``submission``: {field?, documents: {doc_id: {pages?, text?, attached?}}, counts: {count_id: n}}."""
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    docs = submission.get("documents", {})
    src = {"source_url": pack["source_url"], "version": pack["version"]}

    def issue(code: str, message: str, anchor: str, *, warn: bool = False) -> None:
        (warnings if warn else issues).append({"code": code, "message": message, "rule_source": anchor, **src})

    for d in pack["documents"]:
        got = docs.get(d["id"])
        if not got or not (got.get("attached", True) and (got.get("pages") or got.get("text") or got.get("attached"))):
            issue("missing_document", f"{d['label']} is required", d["anchor"])
            continue
        if d.get("max_pages") is not None:
            if got.get("pages") is None:
                issue("page_count_unknown", f"{d['label']}: page count not supplied (limit {d['max_pages']})", d["anchor"], warn=True)
            elif int(got["pages"]) > d["max_pages"]:
                issue("over_page_limit", f"{d['label']} has {got['pages']} pages; limit is {d['max_pages']}", d["anchor"])
        text = got.get("text")
        if text is None:
            if d.get("required_headings"):
                issue("text_not_supplied", f"{d['label']}: text not supplied, headings not checked", d["anchor"], warn=True)
            continue
        lines = {_norm(l).strip(" :#*") for l in text.splitlines() if l.strip()}
        for h in d.get("required_headings", []):
            if _norm(h) not in lines:
                issue("missing_heading", f"{d['label']} needs a separate '{h}' heading line", d["anchor"])
        if d.get("no_urls_or_dois_in_references") and _URL_OR_DOI.search(text):
            fmt = (pack.get("formatting") or {}).get("anchor", d["anchor"])
            issue("url_or_doi_in_text", f"{d['label']} contains a URL or DOI; the call allows abbreviated titles only", fmt)

    for c in pack.get("counts", []):
        n = int(submission.get("counts", {}).get(c["id"], 0))
        if n < c["min"]:
            issue("too_few", f"{c['label']}: {n} supplied, at least {c['min']} required", c["anchor"])

    field = submission.get("field")
    applicable = [d for d in pack["deadlines"] if "*" in d.get("fields", ["*"]) or (field and field in d.get("fields", []))]
    if field and not any(field in d.get("fields", []) for d in pack["deadlines"]):
        issue("unknown_field", f"field '{field}' is not listed in this call's deadlines", pack["deadlines"][0]["anchor"], warn=True)
    if not field:
        issue("field_not_supplied", "no field of study given; only all-field deadlines are shown", pack["deadlines"][0]["anchor"], warn=True)
    deadlines = []
    for d in sorted(applicable, key=_deadline_at):
        at = _deadline_at(d)
        left = (at - now).total_seconds() / 86400
        row = {"id": d["id"], "label": d["label"], "at": at.isoformat(), "days_left": round(left, 2),
               "passed": left < 0, "rule_source": d["anchor"]}
        deadlines.append(row)
        if left < 0:
            issue("deadline_passed", f"{d['label']} passed at {at.isoformat()}", d["anchor"])
    return {"pack": {k: pack[k] for k in ("agency", "program", "solicitation", "version", "source_url", "retrieved_at")},
            "ready": not issues, "issues": issues, "warnings": warnings, "deadlines": deadlines,
            "formatting_rules": (pack.get("formatting") or {}).get("rules", []),
            "criteria": [c["name"] for c in pack.get("criteria", [])],
            "boundary": "Checks only the rules captured in this pack; confirm against the official call before submitting."}


def _index(items: list[dict[str, Any]], key: str = "id") -> dict[str, dict[str, Any]]:
    return {i[key]: i for i in items}


def diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    for group in ("deadlines", "documents", "counts"):
        a, b = _index(old.get(group, [])), _index(new.get(group, []))
        for k in sorted(a.keys() - b.keys()):
            changes.append({"group": group, "id": k, "change": "removed", "old": a[k]})
        for k in sorted(b.keys() - a.keys()):
            changes.append({"group": group, "id": k, "change": "added", "new": b[k]})
        for k in sorted(a.keys() & b.keys()):
            fields = {f: {"old": a[k].get(f), "new": b[k].get(f)} for f in set(a[k]) | set(b[k])
                      if f != "anchor" and a[k].get(f) != b[k].get(f)}
            if fields:
                changes.append({"group": group, "id": k, "change": "modified", "fields": fields})
    return {"from": old["version"], "to": new["version"], "solicitation": [old["solicitation"], new["solicitation"]],
            "changes": changes, "amended": bool(changes)}


def anchors(pack: dict[str, Any]) -> list[tuple[str, str]]:
    out = []
    for group in ("deadlines", "documents", "counts", "criteria"):
        for item in pack.get(group, []):
            out.append((f"{group}:{item.get('id') or item.get('name')}", item["anchor"]))
    if pack.get("formatting", {}).get("anchor"):
        out.append(("formatting", pack["formatting"]["anchor"]))
    return out


def verify_source(pack: dict[str, Any], fetch_text: Callable[[str], str]) -> dict[str, Any]:
    """Re-read the official page; every anchor must still appear verbatim."""
    page = _loose(html.unescape(re.sub(r"<[^>]+>", " ", fetch_text(pack["source_url"]))))
    missing = [{"rule": rule, "anchor": a} for rule, a in anchors(pack) if _loose(a) not in page]
    return {"source_url": pack["source_url"], "version": pack["version"], "anchors_checked": len(anchors(pack)),
            "missing": missing, "possibly_amended": bool(missing),
            "action": "capture a new pack version from the official call" if missing else "none"}
