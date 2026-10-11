"""Row 1268 Regulatory Practice: bounded declared obligation bookkeeping.

Maps caller-declared regulated activities to caller-declared rules (regulator,
rule-text reference, effective/end dates) and caller-declared control-evidence
references, and reports as-of effectiveness plus gaps. Everything computed comes
from the supplied declarations. No rule text is fetched or verified, no control
evidence is inspected, no compliance is certified, nothing is filed or sent.
Standard library only.

Validation order: exact container type before len(); count cap before any
iteration; strings are exact str with length cap, then a Unicode check (no
control, line/paragraph separator or bidi/format characters). Refusals are
generic and never contain caller keys, values or ids.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from typing import Any

PREFIX = "REGULA1268:"
CODE = "REGULA1268"
MAX_ITEMS = 64
MAX_TEXT = 500
BOUNDARY = ("Legal work product for review, not legal advice. Licensed counsel must verify "
            "jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.")

_ID = re.compile(r"[A-Za-z0-9_.-]{1,64}")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_TOP = {"jurisdiction", "as_of", "activities", "rules", "controls"}
_TOP_REQ = {"jurisdiction", "as_of", "activities", "rules"}
_ACT = {"id", "text", "rule_ids"}
_RULE = {"id", "regulator", "rule_text_ref", "effective_date", "end_date"}
_RULE_REQ = _RULE - {"end_date"}
_CTL = {"id", "rule_id", "evidence_ref"}
_TEXT_MSG = "text fields must be 1..500 characters without control, bidi or format characters"


class RegulatoryPracticeRefusal(ValueError):
    """Refused; .code is machine readable, str() is the exact reason."""

    def __init__(self, message: str):
        super().__init__(PREFIX + " " + message)
        self.code = CODE


def _refuse(message: str):
    raise RegulatoryPracticeRefusal(message)


def _text(v: Any) -> str:
    if type(v) is not str or len(v) > MAX_TEXT:   # raw length cap first
        _refuse(_TEXT_MSG)
    if not v.strip():
        _refuse(_TEXT_MSG)
    for ch in v:
        if unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp"):
            _refuse(_TEXT_MSG)
    return v


def _id(v: Any) -> str:
    if type(v) is not str or len(v) > 64 or _ID.fullmatch(v) is None:
        _refuse("ids must match [A-Za-z0-9_.-]{1,64}")
    return v


def _date(v: Any, msg: str) -> date:
    if type(v) is not str or len(v) != 10 or _DATE.fullmatch(v) is None:
        _refuse(msg)
    try:
        return date.fromisoformat(v)
    except ValueError:
        _refuse(msg)


def _keys(d: dict, allowed: set, required: set, label: str) -> None:
    if len(d) > len(allowed):   # key-count cap before any key scan
        _refuse("unknown %s field present" % label)
    if any(type(k) is not str for k in d):
        _refuse("field names must be strings")
    if set(d) - allowed:
        _refuse("unknown %s field present" % label)
    if required - set(d):
        _refuse("missing required %s field" % label)


def _items(v: Any, name: str, minimum: int) -> list:
    msg = "%s must be a list of %d..%d objects" % (name, minimum, MAX_ITEMS)
    if type(v) is not list or not minimum <= len(v) <= MAX_ITEMS:
        _refuse(msg)
    if any(type(x) is not dict for x in v):
        _refuse(msg)
    return v


def map_regulatory_obligations(data: Any) -> dict:
    if type(data) is not dict:
        _refuse("input must be an object")
    if len(data) > len(_TOP):   # key-count cap before any key scan
        _refuse("unknown top-level field present")
    if any(type(k) is not str for k in data):
        _refuse("field names must be strings")
    if set(data) - _TOP:
        _refuse("unknown top-level field present")
    if _TOP_REQ - set(data):
        _refuse("missing required top-level field")

    as_of_text = data["as_of"]
    as_of = _date(as_of_text, "as_of must be an ISO date YYYY-MM-DD")
    jurisdiction = _text(data["jurisdiction"])
    raw_acts = _items(data["activities"], "activities", 1)
    raw_rules = _items(data["rules"], "rules", 1)
    raw_ctls = _items(data.get("controls", []), "controls", 0)

    rules = []
    for r in raw_rules:
        _keys(r, _RULE, _RULE_REQ, "rule")
        eff_t = r["effective_date"]
        end_t = r.get("end_date")
        msg = "rule dates must be ISO dates YYYY-MM-DD"
        eff = _date(eff_t, msg)
        end = _date(end_t, msg) if "end_date" in r else None
        if end is not None and end <= eff:
            _refuse("rule end_date must be after effective_date")
        rules.append({"id": _id(r["id"]), "regulator": _text(r["regulator"]),
                      "rule_text_ref": _text(r["rule_text_ref"]),
                      "effective_date": eff_t, "end_date": end_t if end is not None else None,
                      "_eff": eff, "_end": end})

    acts = []
    for a in raw_acts:
        _keys(a, _ACT, _ACT, "activity")
        ids = a["rule_ids"]
        if type(ids) is not list or len(ids) > MAX_ITEMS:
            _refuse("activity rule_ids must be a list of unique rule ids")
        clean = []
        for x in ids:
            if type(x) is not str or len(x) > 64 or _ID.fullmatch(x) is None:
                _refuse("activity rule_ids must be a list of unique rule ids")
            clean.append(x)
        if len(set(clean)) != len(clean):
            _refuse("activity rule_ids must be a list of unique rule ids")
        acts.append({"id": _id(a["id"]), "text": _text(a["text"]), "rule_ids": sorted(clean)})

    ctls = []
    for c in raw_ctls:
        _keys(c, _CTL, _CTL, "control")
        ctls.append({"id": _id(c["id"]), "rule_id": _id(c["rule_id"]),
                     "evidence_ref": _text(c["evidence_ref"])})

    for coll, label in ((rules, "rule"), (acts, "activity"), (ctls, "control")):
        if len({x["id"] for x in coll}) != len(coll):
            _refuse("duplicate %s id" % label)
    rule_ids = {r["id"] for r in rules}
    if any(x not in rule_ids for a in acts for x in a["rule_ids"]):
        _refuse("activity rule_ids reference an unknown rule")
    if any(c["rule_id"] not in rule_ids for c in ctls):
        _refuse("control rule_id references an unknown rule")

    rules.sort(key=lambda x: x["id"]); acts.sort(key=lambda x: x["id"]); ctls.sort(key=lambda x: x["id"])

    out_rules = []
    for r in rules:
        if as_of < r["_eff"]:
            eff_state = "not_yet_effective"
        elif r["_end"] is not None and as_of >= r["_end"]:
            eff_state = "ended"
        else:
            eff_state = "in_effect"
        mine = [c for c in ctls if c["rule_id"] == r["id"]]
        out_rules.append({"id": r["id"], "regulator": r["regulator"], "rule_text_ref": r["rule_text_ref"],
                          "effective_date": r["effective_date"], "end_date": r["end_date"],
                          "effectiveness": eff_state,
                          "control_ids": [c["id"] for c in mine],
                          "control_evidence_refs": [c["evidence_ref"] for c in mine]})
    state = {r["id"]: r["effectiveness"] for r in out_rules}
    used = {x for a in acts for x in a["rule_ids"]}
    findings = {
        "activities_without_rules": [a["id"] for a in acts if not a["rule_ids"]],
        "rules_without_control_evidence": [r["id"] for r in out_rules if not r["control_ids"]],
        "rules_without_activities": [r["id"] for r in out_rules if r["id"] not in used],
        "rules_not_in_effect_at_as_of": [r["id"] for r in out_rules if r["effectiveness"] != "in_effect"],
        "activities_touching_rules_not_in_effect": [a["id"] for a in acts
                                                     if any(state[x] != "in_effect" for x in a["rule_ids"])],
    }
    canon = {"jurisdiction": jurisdiction, "as_of": as_of_text,
             "activities": acts, "rules": out_rules_for_hash(rules), "controls": ctls}
    digest = hashlib.sha256(json.dumps(canon, sort_keys=True, ensure_ascii=True,
                                       separators=(",", ":")).encode("ascii")).hexdigest()
    return {
        "status": "declared_input_bookkeeping_only",
        "jurisdiction": jurisdiction, "as_of": as_of_text,
        "rules": out_rules,
        "activities": [{"id": a["id"], "text": a["text"], "rule_ids": list(a["rule_ids"])} for a in acts],
        "findings": findings,
        "provenance_sha256": digest,
        "compliance_certified": False, "rule_text_verified": False,
        "control_evidence_verified": False, "legal_conclusion": None,
        "counsel_review_required": True, "boundary": BOUNDARY,
    }


def out_rules_for_hash(rules: list) -> list:
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rules]
