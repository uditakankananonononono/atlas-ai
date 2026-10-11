"""Row 1303 Legal Operations (ledger: requirement title only - "Legal Operations", no description).

Bounded declared legal-support bookkeeping over caller-supplied data only. Delta against
the existing mechanism SPECS row 1303 at legal_support_1260_1309.py line 60 and
analyze_legal_feature at line 96 (read on live main 4da7f8e5): the existing engine accepts
free-form analysis items and checks no row-specific vocabulary; this unit checks which
named elements of the row the caller supplied a reference for. "referenced" means a
reference string was supplied; nothing is verified, no deadline is computed or advised,
and no legal conclusion is reached.
"""

import datetime
import re
import unicodedata

ROW = 1303
_P = "LEGALO1303: "
_VOCAB = ("matter_owner", "phase", "milestones", "budget_inputs", "controls", "approvals")
_REQUEST_KEYS = ("row", "as_of", "entries")
_ENTRY_KEYS = ("element", "status", "source_ref", "entry_date")
_STATUSES = ("supplied", "missing", "disputed")
_MAX_ENTRIES = 200
_MAX_REF = 200
_BAD_CATS = ("Cc", "Cf", "Zl", "Zp")  # Zs accepted; Cs surrogates stay a disclosed residual
_DATE_SHAPE = re.compile(r"\d{4}-\d{2}-\d{2}")
_BOUNDARY = ("Legal work product for review, not legal advice. Licensed counsel must verify "
             "jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.")
_SCOPE = ("bounded declared legal-support bookkeeping over caller-supplied data only "
          "(jurisdiction/as-of/provenance-bound; separates sourced facts from assertions and "
          "from analysis); never reaches a legal conclusion, never files, serves or contacts "
          "anyone, never verifies supplied assertions or authority references; never changes a matter or approves a budget.")
# SEND/SPEND/NOCREDS: canonical table sets from backend/app/modules/c30/worldclass.py lines 34-43.
# EFFECT: package-specified set for this legal package. Scan order SEND, SPEND, NOCREDS, EFFECT.
_SEND = frozenset({"send", "approve", "approved", "approval", "approval_token", "smtp",
                   "token", "email_send", "sender", "smtp_host", "smtp_port", "smtp_user"})
_SPEND = frozenset({"pay", "purchase", "spend", "buy", "checkout", "card_number"})
_NOCREDS = frozenset({"login", "password", "username", "credentials", "otp", "api_key",
                      "access_token", "refresh_token", "bearer", "pass", "passwd"})
_EFFECT = frozenset({"file", "serve", "send", "contact", "submit", "execute", "advise", "settle"})
_FORBIDDEN = (("SEND", _SEND), ("SPEND", _SPEND), ("NOCREDS", _NOCREDS), ("EFFECT", _EFFECT))
_LIMITS = [
    "Bookkeeping over supplied declarations only; no legal conclusion is reached or implied.",
    "Nothing is filed, served, sent or contacted; no supplied reference or authority is verified.",
    "No deadline is computed or advised; days_since_latest is bare arithmetic with no threshold.",
]


class LegalOperationsError(ValueError):
    pass


def _fail(code):
    raise LegalOperationsError(_P + code)


def _scan_forbidden(node):
    if type(node) is dict:
        for key, value in node.items():
            if type(key) is str:
                for table_name, table in _FORBIDDEN:
                    if key in table:
                        _fail(table_name + ":" + key)
            _scan_forbidden(value)
    elif type(node) is list:
        for item in node:
            _scan_forbidden(item)


def _unicode_clean(text, code):
    for ch in text:
        if unicodedata.category(ch) in _BAD_CATS:
            _fail(code)
    return text


def _date(value, code):
    if type(value) is not str or not value.isascii() or _DATE_SHAPE.fullmatch(value) is None:
        _fail(code)
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        _fail(code)


def _check_source_ref(entry, status):
    present = "source_ref" in entry
    if status in ("supplied", "disputed"):
        if not present or type(entry["source_ref"]) is not str:
            _fail("BAD_TYPE:source_ref")
        ref = entry["source_ref"]
        if not 1 <= len(ref) <= _MAX_REF:  # length capped before any strip
            _fail("BAD_TYPE:source_ref")
        _unicode_clean(ref, "BAD_TYPE:source_ref")
    elif present and entry["source_ref"] is not None:
        _fail("BAD_TYPE:source_ref")


def _check_entry(entry, as_of):
    if type(entry) is not dict or any(type(k) is not str for k in entry):
        _fail("BAD_TYPE:entry")
    keys = set(entry)
    if "element" not in keys or "status" not in keys or not keys <= set(_ENTRY_KEYS):
        _fail("BAD_TYPE:entry")
    element = entry["element"]
    if type(element) is not str or element not in _VOCAB:
        _fail("UNKNOWN:element")
    status = entry["status"]
    if type(status) is not str or status not in _STATUSES:
        _fail("UNKNOWN:status")
    _check_source_ref(entry, status)
    if "entry_date" in entry:
        if _date(entry["entry_date"], "BAD_TYPE:entry_date") > as_of:
            _fail("BAD_TYPE:entry_date")


def run(request):
    _scan_forbidden(request)
    if type(request) is not dict or any(type(k) is not str for k in request):
        _fail("BAD_TYPE:request")
    if len(request) != len(_REQUEST_KEYS) or set(request) != set(_REQUEST_KEYS):
        _fail("BAD_TYPE:request")
    row = request["row"]
    if type(row) is not int or row != ROW:
        _fail("UNKNOWN:row")
    as_of = _date(request["as_of"], "BAD_TYPE:as_of")
    entries = request["entries"]
    if type(entries) is not list:
        _fail("BAD_TYPE:entries")
    if len(entries) < 1:
        _fail("EMPTY:entries")
    if len(entries) > _MAX_ENTRIES:
        _fail("OVERSIZE:entries")
    for entry in entries:
        _check_entry(entry, as_of)
    seen = set()
    for entry in entries:
        marker = (entry["element"], entry["status"], entry.get("source_ref"))
        if marker in seen:
            _fail("BAD_TYPE:entries")
        seen.add(marker)
    by_element = {}
    for entry in entries:
        by_element.setdefault(entry["element"], []).append(entry)
    elements = []
    counts = {"referenced": 0, "disputed": 0, "declared_missing": 0, "unaddressed": 0}
    for name in _VOCAB:
        group = by_element.get(name, [])
        supplied = [e for e in group if e["status"] == "supplied"]
        disputed = [e for e in group if e["status"] == "disputed"]
        missing = [e for e in group if e["status"] == "missing"]
        if disputed:
            state = "disputed"
        elif supplied:
            state = "referenced"
        elif missing:
            state = "declared_missing"
        else:
            state = "unaddressed"
        dates = [datetime.date.fromisoformat(e["entry_date"]) for e in supplied if "entry_date" in e]
        latest = max(dates) if dates else None
        elements.append({
            "element": name,
            "status": state,
            "also_declared_missing": state == "referenced" and bool(missing),
            "latest_entry_date": latest.isoformat() if latest is not None else None,
            "days_since_latest": (as_of - latest).days if latest is not None else None,
        })
        counts[state] += 1
    return {
        "row": ROW,
        "elements": elements,
        "coverage": {
            "elements_total": len(_VOCAB),
            "referenced": counts["referenced"],
            "disputed": counts["disputed"],
            "declared_missing": counts["declared_missing"],
            "unaddressed": counts["unaddressed"],
        },
        "counsel_review_required": True,
        "legal_conclusion": False,
        "references_verified": False,
        "boundary": _BOUNDARY,
        "scope": _SCOPE,
    }
