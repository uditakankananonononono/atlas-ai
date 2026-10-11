"""[1265] "Due Process": completeness and sequence bookkeeping over caller-declared elements.

Pure, hermetic and stdlib only: no files, no network, no clock, no entropy source.
The caller declares a protected interest, a deprivation, notice, a hearing and balancing-factor statements,
each optionally tied to caller-supplied source ids. The module reports which elements are declared, which
are sourced, which source ids are unknown, and how the declared dates order against each other. It never
decides whether process was adequate, never verifies a source or a declared fact, and never files or
contacts anyone. The generic template engine for this row lives in legal_support_1260_1309.py and is
neither used nor replaced here.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

PREFIX = "DUEPRO1265:"
SCOPE = "DUEPRO1265 declared-element completeness and date ordering only"
STANDING_BOUNDARY = ("Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, "
                     "currency, citations, facts, duties, deadlines and strategy before use.")
BOUNDARY = (STANDING_BOUNDARY + " Mechanical bookkeeping over caller-declared statements: it does not decide "
            "whether notice or a hearing was adequate, timely or required, does not weigh any factor, and does "
            "not verify any declared fact, date or source.")

MAX_TEXT = 500
MAX_SOURCES = 64
MAX_KEYS = 64
MAX_FACTORS = 50
MAX_IDS = 20

REFUSAL_CODES = ("BAD_TYPE", "MISSING", "UNKNOWN_KEY", "BAD_TEXT", "BAD_DATE", "TOO_MANY", "DUPLICATE_SOURCE",
                 "INCONSISTENT")
GAP_CODES = ("ELEMENT_NOT_DECLARED", "UNSOURCED", "UNKNOWN_SOURCE_ID", "DATE_AFTER_AS_OF", "DATE_UNDECLARED",
             "NOTICE_DECLARED_NOT_GIVEN", "HEARING_DECLARED_NOT_HELD")

_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_TOP_REQUIRED = ("jurisdiction", "as_of", "sources")
_TOP_OPTIONAL = ("protected_interest", "deprivation", "notice", "hearing", "balancing_factors")
_ELEMENTS = ("protected_interest", "deprivation", "notice", "hearing", "balancing_factors")


class DueProcessError(ValueError):
    def __init__(self, code, where):
        self.code = code
        super().__init__("%s%s:%s" % (PREFIX, code, where))


def _fail(code, where):
    raise DueProcessError(code, where)


def _text(v, where):
    # exact str only; raw length cap first, then blank check, then the category scan
    if type(v) is not str or len(v) > MAX_TEXT:
        _fail("BAD_TEXT", where)
    if not v.strip():
        _fail("BAD_TEXT", where)
    if any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") for c in v):
        _fail("BAD_TEXT", where)
    return v


def _date(v, where):
    if type(v) is not str or len(v) != 10 or not _DATE_RE.fullmatch(v):
        _fail("BAD_DATE", where)
    try:
        return date.fromisoformat(v)
    except ValueError:
        _fail("BAD_DATE", where)


def _obj(v, where, required, optional):
    if type(v) is not dict:
        _fail("BAD_TYPE", where)
    if len(v) > MAX_KEYS:                       # count before any iteration
        _fail("TOO_MANY", where)
    for k in v:
        # exact str key first, so a str subclass never reaches the allowlist comparison
        if type(k) is not str or (k not in required and k not in optional):
            _fail("UNKNOWN_KEY", where)         # fixed reason: the caller's key is not echoed
    for k in required:
        if k not in v:
            _fail("MISSING", "%s.%s" % (where, k))
    return v


def _ids(v, where):
    if type(v) is not list:
        _fail("BAD_TYPE", where)
    if len(v) > MAX_IDS:
        _fail("TOO_MANY", where)
    return [_text(x, "%s[%d]" % (where, i)) for i, x in enumerate(v)]


def _source_state(ids, known, element, gaps, index=None):
    """Status of one declared item, appending UNSOURCED / UNKNOWN_SOURCE_ID gaps."""
    def gap(code, detail, **extra):
        g = {"code": code, "element": element, "detail": detail}
        if index is not None:
            g["index"] = index
        g.update(extra)
        gaps.append(g)
    if not ids:
        gap("UNSOURCED", "no source ids declared")
        return "DECLARED_UNSOURCED"
    bad = [x for x in ids if x not in known]
    for x in bad:
        gap("UNKNOWN_SOURCE_ID", "source id is not in the supplied sources", source_id=x)
    return "DECLARED_UNSOURCED" if bad else "DECLARED_SOURCED"


def _order(a, b):
    if a is None or b is None:
        return "not_comparable"
    return "before" if a < b else "after" if a > b else "same_day"


def analyze_due_process(request):
    if type(request) is not dict:
        _fail("BAD_TYPE", "request")
    if len(request) > MAX_KEYS:                 # count before any iteration
        _fail("TOO_MANY", "request")
    for k in request:
        if type(k) is not str or (k not in _TOP_REQUIRED and k not in _TOP_OPTIONAL):
            _fail("UNKNOWN_KEY", "request")     # fixed reason: the caller's key is not echoed
    for k in _TOP_REQUIRED:
        if k not in request:
            _fail("MISSING", k)
    jurisdiction = _text(request["jurisdiction"], "jurisdiction")
    as_of = _date(request["as_of"], "as_of")
    srcs = request["sources"]
    if type(srcs) is not list:
        _fail("BAD_TYPE", "sources")
    if len(srcs) > MAX_SOURCES:
        _fail("TOO_MANY", "sources")
    known = set()
    for i, s in enumerate(srcs):
        w = "sources[%d]" % i
        _obj(s, w, ("source_id", "label"), ())
        sid = _text(s["source_id"], w + ".source_id")
        _text(s["label"], w + ".label")
        if sid in known:
            _fail("DUPLICATE_SOURCE", w + ".source_id")
        known.add(sid)

    gaps, elements, dates = [], {}, {}

    def missing(name):
        elements[name] = {"status": "NOT_DECLARED"}
        gaps.append({"code": "ELEMENT_NOT_DECLARED", "element": name, "detail": "element was not declared"})

    def dated(name, raw, where):
        d = _date(raw, where)
        if d > as_of:
            gaps.append({"code": "DATE_AFTER_AS_OF", "element": name, "detail": "declared date is after as_of"})
        return d

    def undated(name):
        gaps.append({"code": "DATE_UNDECLARED", "element": name, "detail": "no date declared; ordering not comparable"})

    # protected_interest
    if "protected_interest" not in request:
        missing("protected_interest")
    else:
        e = _obj(request["protected_interest"], "protected_interest", ("description",), ("source_ids",))
        desc = _text(e["description"], "protected_interest.description")
        ids = _ids(e.get("source_ids", []), "protected_interest.source_ids")
        st = _source_state(ids, known, "protected_interest", gaps)
        elements["protected_interest"] = {"status": st, "description": desc, "source_ids": list(ids)}

    # deprivation
    if "deprivation" not in request:
        missing("deprivation")
    else:
        e = _obj(request["deprivation"], "deprivation", ("description",), ("date", "source_ids"))
        desc = _text(e["description"], "deprivation.description")
        d = dated("deprivation", e["date"], "deprivation.date") if "date" in e else None
        ids = _ids(e.get("source_ids", []), "deprivation.source_ids")
        st = _source_state(ids, known, "deprivation", gaps)
        if d is None:
            undated("deprivation")
        dates["deprivation"] = d
        elements["deprivation"] = {"status": st, "description": desc,
                                   "date": e.get("date"), "source_ids": list(ids)}

    # notice
    if "notice" not in request:
        missing("notice")
    else:
        e = _obj(request["notice"], "notice", ("given",), ("date", "content_summary", "source_ids"))
        if type(e["given"]) is not bool:
            _fail("BAD_TYPE", "notice.given")
        if not e["given"] and "date" in e:
            _fail("INCONSISTENT", "notice.date")
        d = dated("notice", e["date"], "notice.date") if "date" in e else None
        summ = _text(e["content_summary"], "notice.content_summary") if "content_summary" in e else None
        ids = _ids(e.get("source_ids", []), "notice.source_ids")
        st = _source_state(ids, known, "notice", gaps)
        if not e["given"]:
            gaps.append({"code": "NOTICE_DECLARED_NOT_GIVEN", "element": "notice",
                         "detail": "caller declared that notice was not given"})
        elif d is None:
            undated("notice")
        dates["notice"] = d
        elements["notice"] = {"status": st, "given": e["given"], "date": e.get("date"),
                              "content_summary": summ, "source_ids": list(ids)}

    # hearing
    if "hearing" not in request:
        missing("hearing")
    else:
        e = _obj(request["hearing"], "hearing", ("held",), ("date", "decision_maker", "source_ids"))
        if type(e["held"]) is not bool:
            _fail("BAD_TYPE", "hearing.held")
        if not e["held"] and "date" in e:
            _fail("INCONSISTENT", "hearing.date")
        d = dated("hearing", e["date"], "hearing.date") if "date" in e else None
        who = _text(e["decision_maker"], "hearing.decision_maker") if "decision_maker" in e else None
        ids = _ids(e.get("source_ids", []), "hearing.source_ids")
        st = _source_state(ids, known, "hearing", gaps)
        if not e["held"]:
            gaps.append({"code": "HEARING_DECLARED_NOT_HELD", "element": "hearing",
                         "detail": "caller declared that no hearing was held"})
        elif d is None:
            undated("hearing")
        dates["hearing"] = d
        elements["hearing"] = {"status": st, "held": e["held"], "date": e.get("date"),
                               "decision_maker": who, "source_ids": list(ids)}

    # balancing_factors
    if "balancing_factors" not in request:
        missing("balancing_factors")
    else:
        fl = request["balancing_factors"]
        if type(fl) is not list:
            _fail("BAD_TYPE", "balancing_factors")
        if len(fl) > MAX_FACTORS:
            _fail("TOO_MANY", "balancing_factors")
        if not fl:
            missing("balancing_factors")
            elements["balancing_factors"] = {"status": "NOT_DECLARED", "count": 0, "items": []}
        else:
            items = []
            for i, f in enumerate(fl):
                w = "balancing_factors[%d]" % i
                _obj(f, w, ("label", "statement"), ("source_ids",))
                label = _text(f["label"], w + ".label")
                stmt = _text(f["statement"], w + ".statement")
                ids = _ids(f.get("source_ids", []), w + ".source_ids")
                st = _source_state(ids, known, "balancing_factors", gaps, i)
                items.append({"label": label, "statement": stmt, "status": st, "source_ids": list(ids)})
            allok = all(x["status"] == "DECLARED_SOURCED" for x in items)
            elements["balancing_factors"] = {"status": "DECLARED_SOURCED" if allok else "DECLARED_UNSOURCED",
                                             "count": len(items), "items": items}

    sequence = {
        "notice_vs_deprivation": _order(dates.get("notice"), dates.get("deprivation")),
        "hearing_vs_deprivation": _order(dates.get("hearing"), dates.get("deprivation")),
        "notice_vs_hearing": _order(dates.get("notice"), dates.get("hearing")),
    }
    gaps.sort(key=lambda g: _ELEMENTS.index(g["element"]))   # stable: keeps per-element discovery order
    return {
        "scope": SCOPE, "boundary": BOUNDARY, "jurisdiction": jurisdiction, "as_of": request["as_of"],
        "elements": elements, "sequence": sequence, "gaps": gaps,
        "summary": {"elements_declared": sum(1 for v in elements.values() if v["status"] != "NOT_DECLARED"),
                    "gap_count": len(gaps)},
        "adequacy_judged": False, "legal_conclusion": None, "requires_licensed_counsel": True,
        "filing_or_external_effect": False, "authority_independently_verified": False,
        "disclaimer": STANDING_BOUNDARY,
    }
