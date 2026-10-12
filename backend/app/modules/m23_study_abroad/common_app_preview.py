"""m23.common_app_preview (doc row 101): ready a Common App PREVIEW from a
prior portfolio ZIP.

Closes the audit gap ("actual prior ZIP and complete personal preview not
verified"): a real ZIP reader that parses a portfolio archive (profile.json,
activities/*.json, honors/*.json, essays/*.txt|*.md), validates every field
against Common App's published constraints, and renders the complete
application preview in section order with per-section status.

Enforced boundaries: path-traversal and oversize archives refuse; unknown
members are reported, never executed; nothing is submitted, signed, attested
or uploaded anywhere. Essays are rendered as the student's own supplied text;
this unit writes no prose. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import io
import json
import re
import zipfile

from app.modules.c30 import policy

PREFIX = "COMMONAPP"
MAX_ZIP_BYTES = 20 * 1024 * 1024
MAX_MEMBER_BYTES = 2 * 1024 * 1024
MAX_MEMBERS = 500
ACTIVITIES_MAX = 10
ACTIVITY_DESC_CHARS = 150
POSITION_CHARS = 50
ORG_CHARS = 100
HONORS_MAX = 5
HONORS_TITLE_CHARS = 100
ESSAY_WORDS_MAX = 650
REQUIRED_PROFILE = ("legal_name", "birth_date", "email", "school", "graduation_year")

_WORD = re.compile(r"[A-Za-z0-9'-]+")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

LIMITS = (
    "Preview only: nothing is submitted, signed, attested or uploaded.",
    "Validation checks Common App's published field constraints; it is not an "
    "admission judgement.",
    "Essays render as supplied student text; no prose is generated or edited.",
)


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


def _safe_member(name):
    if not isinstance(name, str) or not name or name.startswith("/") or ".." in name.split("/") \
            or "\\" in name or name.endswith("/"):
        return None
    return name


def read_portfolio(data):
    """Parse portfolio ZIP bytes into a structured portfolio dict."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("%s_REFUSED_BAD_TYPE:zip" % PREFIX)
    if len(data) > MAX_ZIP_BYTES:
        _err("OVERSIZE", "zip")
    try:
        zf = zipfile.ZipFile(io.BytesIO(bytes(data)))
    except zipfile.BadZipFile:
        _err("BAD_ZIP")
    names = zf.namelist()
    if len(names) > MAX_MEMBERS:
        _err("OVERSIZE", "members")
    portfolio = {"profile": None, "activities": [], "honors": [], "essays": [],
                 "unknown_members": []}
    for raw in names:
        name = _safe_member(raw)
        if name is None:
            if not raw.endswith("/"):
                _err("PATH", "member")  # traversal attempt: refuse the whole archive
            continue
        info = zf.getinfo(raw)
        if info.file_size > MAX_MEMBER_BYTES:
            _err("OVERSIZE", "member")
        top, _, rest = name.partition("/")
        blob = zf.read(raw)
        if top == "profile.json" and not rest:
            try:
                portfolio["profile"] = json.loads(blob.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                _err("PARSE", "profile.json")
        elif top == "activities" and rest.endswith(".json"):
            try:
                row = json.loads(blob.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                _err("PARSE", name)
            row["_member"] = name
            portfolio["activities"].append(row)
        elif top == "honors" and rest.endswith(".json"):
            try:
                row = json.loads(blob.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                _err("PARSE", name)
            row["_member"] = name
            portfolio["honors"].append(row)
        elif top == "essays" and (rest.endswith(".txt") or rest.endswith(".md")):
            try:
                text = blob.decode("utf-8")
            except UnicodeDecodeError:
                _err("PARSE", name)
            portfolio["essays"].append({"_member": name, "text": text})
        else:
            portfolio["unknown_members"].append(name)
    if portfolio["profile"] is None:
        _err("MISSING", "profile.json")
    if not isinstance(portfolio["profile"], dict):
        _err("PARSE", "profile.json")
    return portfolio


def validate(portfolio):
    """Field-level validation against Common App published constraints."""
    if not isinstance(portfolio, dict) or "profile" not in portfolio:
        raise ValueError("%s_REFUSED_BAD_TYPE:portfolio" % PREFIX)
    v = []
    prof = portfolio["profile"]
    for field in REQUIRED_PROFILE:
        if not prof.get(field):
            v.append({"section": "profile", "field": field, "issue": "missing"})
    email = prof.get("email")
    if email and not _EMAIL.fullmatch(str(email)):
        v.append({"section": "profile", "field": "email", "issue": "not-an-email"})
    bd = prof.get("birth_date")
    if bd and not _DATE.fullmatch(str(bd)):
        v.append({"section": "profile", "field": "birth_date", "issue": "not-YYYY-MM-DD"})
    acts = portfolio.get("activities", [])
    if len(acts) > ACTIVITIES_MAX:
        v.append({"section": "activities", "field": "count",
                  "issue": "exceeds-%d" % ACTIVITIES_MAX})
    for i, a in enumerate(acts):
        desc = str(a.get("description", ""))
        pos = str(a.get("position", ""))
        org = str(a.get("organization", ""))
        if len(desc) > ACTIVITY_DESC_CHARS:
            v.append({"section": "activities", "field": "description", "index": i,
                      "issue": "over-%d-chars" % ACTIVITY_DESC_CHARS, "have": len(desc)})
        if len(pos) > POSITION_CHARS:
            v.append({"section": "activities", "field": "position", "index": i,
                      "issue": "over-%d-chars" % POSITION_CHARS, "have": len(pos)})
        if len(org) > ORG_CHARS:
            v.append({"section": "activities", "field": "organization", "index": i,
                      "issue": "over-%d-chars" % ORG_CHARS, "have": len(org)})
        if not desc.strip():
            v.append({"section": "activities", "field": "description", "index": i,
                      "issue": "missing"})
    honors = portfolio.get("honors", [])
    if len(honors) > HONORS_MAX:
        v.append({"section": "honors", "field": "count", "issue": "exceeds-%d" % HONORS_MAX})
    for i, h in enumerate(honors):
        if len(str(h.get("title", ""))) > HONORS_TITLE_CHARS:
            v.append({"section": "honors", "field": "title", "index": i,
                      "issue": "over-%d-chars" % HONORS_TITLE_CHARS})
    for i, e in enumerate(portfolio.get("essays", [])):
        words = len(_WORD.findall(e.get("text", "")))
        if words > ESSAY_WORDS_MAX:
            v.append({"section": "essays", "field": "words", "index": i,
                      "issue": "over-%d-words" % ESSAY_WORDS_MAX, "have": words})
        if words == 0:
            v.append({"section": "essays", "field": "words", "index": i, "issue": "empty"})
    return v


def render_preview(portfolio):
    """Render the complete application preview (markdown) in Common App
    section order, with per-section status and the full violation list."""
    violations = validate(portfolio)
    prof = portfolio["profile"]
    lines = ["# Common App Preview", "",
             "> Preview only. Nothing here is submitted, signed or attested.", ""]
    lines.append("## Profile")
    for field in REQUIRED_PROFILE + tuple(k for k in prof if k not in REQUIRED_PROFILE):
        lines.append("- **%s:** %s" % (field, prof.get(field, "(missing)")))
    lines.append("")
    lines.append("## Activities (%d/%d)" % (len(portfolio["activities"]), ACTIVITIES_MAX))
    for i, a in enumerate(portfolio["activities"]):
        lines.append("%d. **%s** - %s" % (i + 1, a.get("position", "(no position)"),
                                          a.get("organization", "(no organization)")))
        lines.append("   %s" % a.get("description", "(no description)"))
        lines.append("   Hours/week: %s | Weeks/year: %s | Grades: %s"
                     % (a.get("hours_per_week", "?"), a.get("weeks_per_year", "?"),
                        a.get("grades", "?")))
    lines.append("")
    lines.append("## Honors (%d/%d)" % (len(portfolio["honors"]), HONORS_MAX))
    for i, h in enumerate(portfolio["honors"]):
        lines.append("%d. %s (%s, grade %s)"
                     % (i + 1, h.get("title", "(no title)"), h.get("level", "?"),
                        h.get("grade", "?")))
    lines.append("")
    lines.append("## Essays")
    for i, e in enumerate(portfolio["essays"]):
        words = len(_WORD.findall(e["text"]))
        lines.append("### %s (%d/%d words)" % (e["_member"], words, ESSAY_WORDS_MAX))
        lines.append("")
        lines.append(e["text"].strip())
        lines.append("")
    sections = {
        "profile": not any(x["section"] == "profile" for x in violations),
        "activities": bool(portfolio["activities"]) and
                      not any(x["section"] == "activities" for x in violations),
        "honors": not any(x["section"] == "honors" for x in violations),
        "essays": bool(portfolio["essays"]) and
                  not any(x["section"] == "essays" for x in violations),
    }
    lines.append("## Validation")
    if violations:
        for x in violations:
            loc = "%s.%s" % (x["section"], x["field"])
            if "index" in x:
                loc += "[%d]" % x["index"]
            lines.append("- ❌ %s: %s%s" % (loc, x["issue"],
                                            (" (have %s)" % x["have"]) if "have" in x else ""))
    else:
        lines.append("- ✅ no constraint violations")
    return {
        "markdown": "\n".join(lines),
        "complete": all(sections.values()) and not violations,
        "sections": sections,
        "violations": violations,
        "unknown_members": portfolio.get("unknown_members", []),
        "submitted": False,
        "limits": list(LIMITS),
    }
