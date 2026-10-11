"""Row 1266 Equal Protection: bounded five-element bookkeeping over caller data.

The caller supplies a jurisdiction, an as-of date, a list of authority
references (id, citation, jurisdiction, effective date, last-checked date) and
up to five elements of an equal-protection review: classification,
comparator, intent evidence, the scrutiny tier supplied by counsel, and
interest/means fit. Each element cites authority ids. This unit validates the
shape, checks that every cited id resolves to a supplied authority, flags
authority jurisdiction mismatch, staleness (last_checked_at before as_of) and
not-yet-effective dates, and lists open items in a fixed order.

It selects no scrutiny tier, assesses no merits, decides no discrimination
claim, verifies no authority or fact, and files or sends nothing.

Delta vs the existing surface (legal_support_1260_1309.py at main a294723b):
row 1266 there is a SPECS entry (L23) run through the shared analyze_legal_feature
engine (L96), whose row-specific input is passed through unvalidated
(`"inputs": data.get("row_inputs", {})`, L131) and whose output reports
named_capability_executed False. This unit adds a validated, element-by-element
structure with per-element source resolution and fixed-order open items, which
that template does not perform.
"""
import re
import unicodedata

PREFIX = "EQUALP1266"
STANDING_BOUNDARY = ("Legal work product for review, not legal advice. Licensed counsel must verify "
                     "jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.")
BOUNDARY = (STANDING_BOUNDARY + " This unit organizes caller-supplied equal-protection elements "
            "(classification, comparator, intent, scrutiny tier, fit) and the authority references cited "
            "for each. It selects no scrutiny tier, assesses no merits, decides no discrimination claim, "
            "verifies no authority or fact, and files or sends nothing.")

MAX_TEXT = 2000
MAX_AUTHORITIES = 64
MAX_SOURCE_IDS = 8
MAX_INTENT_ITEMS = 32
MAX_EXTRA_KEYS = 8
REFUSED_CATEGORIES = ("Cc", "Cf", "Zl", "Zp")
ELEMENTS = ("classification", "comparator", "intent", "scrutiny", "fit")
CONCLUSION_FIELDS = ("verdict", "conclusion", "outcome", "likely_outcome", "prediction",
                     "merits", "ruling", "advice")
KINDS = ("facial", "applied", "unspecified")
TIERS = ("strict", "intermediate", "rational_basis")
INTENT_KINDS = ("facial_text", "stated_purpose", "disparate_impact_data",
                "historical_background", "procedural_departure")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _fail(message):
    raise ValueError(f"{PREFIX}: {message}")


def _has_refused_char(value):
    return any(unicodedata.category(ch) in REFUSED_CATEGORIES for ch in value)


def _text(value, field):
    # raw length first, then character categories, then emptiness (Zs spaces are allowed)
    if type(value) is not str or len(value) > MAX_TEXT:
        _fail(f"{field} requires non-empty text of at most {MAX_TEXT} characters")
    if _has_refused_char(value):
        _fail(f"{field} contains a control, format or line/paragraph-separator character")
    if not value.strip():
        _fail(f"{field} requires non-empty text of at most {MAX_TEXT} characters")
    return value


def _date(value, field):
    from datetime import date
    if type(value) is not str or len(value) != 10 or not _DATE.fullmatch(value):
        _fail(f"{field} requires an ISO date YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(f"{field} requires an ISO date YYYY-MM-DD")


def _enum(value, field, allowed):
    if type(value) is not str or len(value) > MAX_TEXT or value not in allowed:  # raw cap before membership
        _fail(f"{field} must be one of {', '.join(allowed)}")
    return value


def _object(value, field, allowed):
    if type(value) is not dict:
        _fail(f"{field} requires an object")
    limit = len(allowed) + MAX_EXTRA_KEYS  # count before any iteration
    if len(value) > limit:
        _fail(f"{field} has too many fields (at most {limit})")
    for key in value:
        if type(key) is not str or key not in allowed:
            _fail(f"unknown field in {field}")  # fixed reason: the caller's key is never echoed
    return value


def _source_ids(value, field):
    ok = (type(value) is list and len(value) <= MAX_SOURCE_IDS
          and all(type(x) is str and len(x) <= MAX_TEXT and not _has_refused_char(x) and x.strip()
                  for x in value)
          and len(set(value)) == len(value))
    if not ok:
        _fail(f"{field}.source_ids requires a list of at most {MAX_SOURCE_IDS} unique non-empty text ids")
    return list(value)


def _authority(raw, index):
    where = f"authorities[{index}]"
    _object(raw, where, ("id", "citation", "jurisdiction", "effective_date", "last_checked_at"))
    return {"id": _text(raw.get("id"), f"{where}.id"),
            "citation": _text(raw.get("citation"), f"{where}.citation"),
            "jurisdiction": _text(raw.get("jurisdiction"), f"{where}.jurisdiction"),
            "effective_date": raw.get("effective_date"), "last_checked_at": raw.get("last_checked_at"),
            "_effective": _date(raw.get("effective_date"), f"{where}.effective_date"),
            "_checked": _date(raw.get("last_checked_at"), f"{where}.last_checked_at")}


def _element(supplied, source_ids, known, jurisdiction_of, jurisdiction):
    unresolved = [s for s in source_ids if s not in known]
    if unresolved:
        status = "unresolved_sources"
    elif not source_ids:
        status = "unsourced"
    else:
        status = "supplied"
    mismatch = [s for s in source_ids if s in known and jurisdiction_of[s] != jurisdiction]
    return {"status": status, "supplied": supplied, "source_ids": source_ids,
            "unresolved_source_ids": unresolved}, mismatch


def map_equal_protection(payload):
    if type(payload) is not dict:
        _fail("payload requires an object")
    allowed = ("jurisdiction", "as_of", "authorities") + ELEMENTS
    if len(payload) > len(allowed) + MAX_EXTRA_KEYS:  # count before any iteration
        _fail(f"payload has too many fields (at most {len(allowed) + MAX_EXTRA_KEYS})")
    for key in payload:
        if type(key) is str and key in CONCLUSION_FIELDS:
            _fail(f"field {key!r} asks for a conclusion; this unit decides no claim")
    _object(payload, "payload", allowed)
    jurisdiction = _text(payload.get("jurisdiction"), "jurisdiction")
    as_of_text = payload.get("as_of")
    as_of = _date(as_of_text, "as_of")
    raw_auth = payload.get("authorities")
    if type(raw_auth) is not list or not 1 <= len(raw_auth) <= MAX_AUTHORITIES:
        _fail(f"authorities requires a list of 1..{MAX_AUTHORITIES} records")
    authorities, seen = [], set()
    for i, raw in enumerate(raw_auth):
        a = _authority(raw, i)
        if a["id"] in seen:
            _fail("duplicate authority id")
        seen.add(a["id"])
        authorities.append(a)
    jurisdiction_of = {a["id"]: a["jurisdiction"] for a in authorities}

    elements, mismatches = {}, {}

    def missing(name):
        elements[name] = {"status": "missing", "supplied": None, "source_ids": [], "unresolved_source_ids": []}
        mismatches[name] = []

    def present(name):
        value = payload.get(name)
        if value is None:
            missing(name)
            return None
        return value

    v = present("classification")
    if v is not None:
        _object(v, "classification", ("basis", "kind", "source_ids"))
        supplied = {"basis": _text(v.get("basis"), "classification.basis"),
                    "kind": _enum(v.get("kind"), "classification.kind", KINDS)}
        elements["classification"], mismatches["classification"] = _element(
            supplied, _source_ids(v.get("source_ids"), "classification"), seen, jurisdiction_of, jurisdiction)

    v = present("comparator")
    sim_missing = False
    if v is not None:
        _object(v, "comparator", ("treated_group", "treated_treatment", "comparator_group",
                                  "comparator_treatment", "similarly_situated_assertion", "source_ids"))
        supplied = {k: _text(v.get(k), f"comparator.{k}") for k in
                    ("treated_group", "treated_treatment", "comparator_group", "comparator_treatment")}
        sim = v.get("similarly_situated_assertion")
        supplied["similarly_situated_assertion"] = None if sim is None else _text(sim, "comparator.similarly_situated_assertion")
        sim_missing = sim is None
        elements["comparator"], mismatches["comparator"] = _element(
            supplied, _source_ids(v.get("source_ids"), "comparator"), seen, jurisdiction_of, jurisdiction)

    v = present("intent")
    if v is not None:
        _object(v, "intent", ("items",))
        raw_items = v.get("items")
        if type(raw_items) is not list or not 1 <= len(raw_items) <= MAX_INTENT_ITEMS:
            _fail(f"intent.items requires a list of 1..{MAX_INTENT_ITEMS} records")
        items, kinds, all_ids, unresolved, mism = [], set(), [], [], []
        for i, raw in enumerate(raw_items):
            where = f"intent.items[{i}]"
            _object(raw, where, ("kind", "text", "source_ids"))
            kind = _enum(raw.get("kind"), f"{where}.kind", INTENT_KINDS)
            text = _text(raw.get("text"), f"{where}.text")
            ids = _source_ids(raw.get("source_ids"), where)
            item, m = _element({"kind": kind, "text": text}, ids, seen, jurisdiction_of, jurisdiction)
            items.append(item)
            kinds.add(kind)
            for s in ids:
                if s not in all_ids:
                    all_ids.append(s)
            unresolved += [s for s in item["unresolved_source_ids"] if s not in unresolved]
            mism += [s for s in m if s not in mism]
        statuses = [x["status"] for x in items]
        status = ("unresolved_sources" if "unresolved_sources" in statuses
                  else "unsourced" if "unsourced" in statuses else "supplied")
        elements["intent"] = {"status": status, "supplied": {"item_count": len(items)},
                              "kinds_present": sorted(kinds), "items": items,
                              "source_ids": sorted(all_ids), "unresolved_source_ids": sorted(unresolved)}
        mismatches["intent"] = sorted(mism)

    v = present("scrutiny")
    if v is not None:
        _object(v, "scrutiny", ("tier_supplied_by_counsel", "source_ids"))
        supplied = {"tier_supplied_by_counsel": _enum(v.get("tier_supplied_by_counsel"),
                                                      "scrutiny.tier_supplied_by_counsel", TIERS)}
        elements["scrutiny"], mismatches["scrutiny"] = _element(
            supplied, _source_ids(v.get("source_ids"), "scrutiny"), seen, jurisdiction_of, jurisdiction)

    v = present("fit")
    if v is not None:
        _object(v, "fit", ("interest", "means", "source_ids"))
        supplied = {"interest": _text(v.get("interest"), "fit.interest"),
                    "means": _text(v.get("means"), "fit.means")}
        elements["fit"], mismatches["fit"] = _element(
            supplied, _source_ids(v.get("source_ids"), "fit"), seen, jurisdiction_of, jurisdiction)

    open_items = []
    for name in ELEMENTS:
        e = elements[name]
        if e["status"] == "missing":
            open_items.append(f"{name}:missing")
            continue
        if e["status"] == "unsourced":
            open_items.append(f"{name}:unsourced")
        for s in e["unresolved_source_ids"]:
            open_items.append(f"{name}:unresolved_source:{s}")
        for s in mismatches[name]:
            open_items.append(f"{name}:jurisdiction_mismatch:{s}")
        if name == "comparator" and sim_missing:
            open_items.append("comparator:similarly_situated_assertion_missing")
    out_auth = []
    for a in authorities:
        stale = a["_checked"] < as_of
        early = a["_effective"] > as_of
        if stale:
            open_items.append(f"authority:{a['id']}:stale")
        if early:
            open_items.append(f"authority:{a['id']}:not_yet_effective")
        out_auth.append({"id": a["id"], "citation": a["citation"], "jurisdiction": a["jurisdiction"],
                         "jurisdiction_match": a["jurisdiction"] == jurisdiction,
                         "effective_date": a["effective_date"], "last_checked_at": a["last_checked_at"],
                         "stale": stale, "not_yet_effective": early})
    return {"row": 1266, "unit": "equal_protection_element_map", "jurisdiction": jurisdiction,
            "as_of": as_of_text, "elements": elements, "authorities": out_auth,
            "open_items": open_items, "ready_for_counsel_review": not open_items,
            "claim_decided": False, "scrutiny_selected_by_unit": False, "merits_assessed": False,
            "authorities_verified": False, "filed_or_sent": False,
            "requires_licensed_counsel": True, "boundary": BOUNDARY}
