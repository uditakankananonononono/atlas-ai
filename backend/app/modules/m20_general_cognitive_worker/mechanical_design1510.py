"""Row 1510 Mechanical Design: bounded exact design-review matrix over supplied declarations.

Evaluates the verification coverage of a caller-declared mechanical design
requirements set: which requirements carry both a declared verification method and
a declared acceptance criterion, which declared load cases are referenced, and
which are not. Everything computed comes from caller-supplied declarations; nothing
is measured, simulated or predicted. No CAD/FEA/solver execution, no physical test,
no design certification, no machinery control. Standard library only.

Validation (v3 order): for every field the type/shape check comes first, then the
count cap (a len() call, no iteration), and only then any per-item iteration,
dedup or allocation. For every string the length cap comes first, then a Unicode
check (no Unicode control, line/paragraph separator or bidi/format characters),
then aggregate accounting. The incoming object is never copied: validation reads
it without iterating past the count caps, and the receipt and the provenance hash
are built only from validated values, in fresh containers, so nothing in the
receipt aliases a caller-owned object. Refusal reasons are generic and name only
schema fields; they never contain a caller key, value, id, reference, unit label
or any repr of caller content.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

MAX_REQUIREMENTS = 64
MAX_LOAD_CASES = 64
MAX_INTERFACES = 64
MAX_ID_LEN = 128
MAX_TEXT_LEN = 1024
MAX_UNITS_KEYS = 32
MAX_UNITS_KEY_LEN = 32
MAX_UNITS_VALUE_LEN = 32
MAX_LIST_ITEM_LEN = 500
MAX_REFS_PER_REQUIREMENT = 64
MAX_AGGREGATE_STRING_LEAVES = 200000

_PREFIX = "MECHAN1510:"
_TOP_KEYS = ("requirements", "load_cases", "interfaces", "units", "assumptions", "source_refs")
_REQ_KEYS = ("id", "verification_method", "acceptance", "load_cases")
_LC_KEYS = ("id", "description")

_LISTED_CF = (set(range(0x200B, 0x2010)) | set(range(0x202A, 0x202F))
              | set(range(0x2066, 0x206A)) | {0xFEFF})
_UNICODE_MSG = ("contains a disallowed character: no Unicode control, "
                "line/paragraph separator or bidi/format characters")


class MechanicalDesignRefusal(ValueError):
    """The request was refused; .code is machine readable, str() is the exact reason."""

    def __init__(self, code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def _refuse(kind: str, message: str) -> None:
    code = _PREFIX + kind
    raise MechanicalDesignRefusal(code, code + ": " + message)


def _invalid(message: str) -> None:
    _refuse("invalid_input", message)


def _limit(message: str) -> None:
    _refuse("resource_limit", message)


class _Aggregate:
    """Running budget over every validated string leaf of the input."""

    def __init__(self) -> None:
        self.total = 0

    def add(self, text: str, field_class: str) -> None:
        self.total += len(text)
        if self.total > MAX_AGGREGATE_STRING_LEAVES:
            _refuse("oversize",
                    f"aggregate string leaves exceed limit {MAX_AGGREGATE_STRING_LEAVES} "
                    f"(field class: {field_class})")


def _unicode_check(value: str, owner: str) -> None:
    for ch in value:
        if ord(ch) == 127 or unicodedata.category(ch) in ("Cc", "Zl", "Zp") or ord(ch) in _LISTED_CF:
            _invalid(f"{owner} {_UNICODE_MSG}")


def _text(value: str, owner: str, limit: int, agg: _Aggregate, field_class: str) -> str:
    """Length cap first, then Unicode check, then aggregate accounting."""
    if len(value) > limit:
        _limit(f"{owner} is {len(value)} characters, limit is {limit}")
    _unicode_check(value, owner)
    agg.add(value, field_class)
    return value


def _unknown_key(parent: str) -> None:
    # The reason names the parent schema field only; a key is unbounded caller
    # input and must never reach the refusal text.
    _refuse("unknown_key", f"unknown key at {parent}")


def _id(value: Any, owner: str, agg: _Aggregate, field_class: str) -> str:
    if not isinstance(value, str) or not value:
        _invalid(f"{owner}.id requires a non-empty string")
    return _text(value, f"{owner}.id", MAX_ID_LEN, agg, field_class)


def _optional_text(item: dict, key: str, owner: str, agg: _Aggregate, field_class: str) -> str | None:
    if key not in item:
        return None
    value = item[key]
    if not isinstance(value, str):
        _invalid(f"{owner}.{key} must be a string when present")
    _text(value, f"{owner}.{key}", MAX_TEXT_LEN, agg, field_class)
    return value or None  # empty string counts as not provided (cluster parity)


def _str_list(data: dict, key: str, limit: int, agg: _Aggregate) -> list[str]:
    if key not in data:
        return []
    value = data[key]
    if type(value) is not list:  # exact type
        _invalid(f"{key} must be a list of strings")
    if len(value) > limit:  # count cap before any iteration
        _limit(f"{key} count {len(value)} exceeds limit {limit}")
    if any(not isinstance(x, str) for x in value):
        _invalid(f"{key} must be a list of strings")
    out = []
    for index, item in enumerate(value):
        out.append(_text(item, f"{key}[{index}]", MAX_LIST_ITEM_LEN, agg, key))
    return out


def _validate(data: Any) -> tuple[list[dict], list[dict], list[str], dict, list[str], list[str]]:
    if type(data) is not dict:  # exact type: subclasses refused before len
        _invalid("input must be an object")
    if len(data) > len(_TOP_KEYS):  # count cap before the allowlist scan
        _unknown_key("input")
    for key in data:
        if key not in _TOP_KEYS:
            _unknown_key("input")
    agg = _Aggregate()
    reqs_raw = data.get("requirements")
    if type(reqs_raw) is not list:  # exact type
        _invalid(f"requirements must be a list of 1..{MAX_REQUIREMENTS} requirement objects")
    if len(reqs_raw) > MAX_REQUIREMENTS:
        _limit(f"requirements count {len(reqs_raw)} exceeds limit {MAX_REQUIREMENTS}")
    if len(reqs_raw) < 1:
        _invalid(f"requirements must be a list of 1..{MAX_REQUIREMENTS} requirement objects")
    seen: set[str] = set()
    reqs: list[dict] = []
    for index, raw in enumerate(reqs_raw):
        owner = f"requirements[{index}]"
        if type(raw) is not dict:  # exact type
            _invalid(f"{owner} must be an object")
        if len(raw) > len(_REQ_KEYS):  # count cap before the allowlist scan
            _unknown_key(owner)
        for key in raw:
            if key not in _REQ_KEYS:
                _unknown_key(owner)
        rid = _id(raw.get("id"), owner, agg, "requirements")
        if rid in seen:
            _invalid("duplicate id in requirements")
        seen.add(rid)
        refs = raw.get("load_cases", [])
        if type(refs) is not list:  # exact type
            _invalid(f"{owner}.load_cases must be a list of load case ids")
        if len(refs) > MAX_REFS_PER_REQUIREMENT:  # count cap before any iteration or allocation
            _limit(f"{owner}.load_cases count {len(refs)} exceeds limit {MAX_REFS_PER_REQUIREMENT}")
        if any(not isinstance(x, str) for x in refs):
            _invalid(f"{owner}.load_cases must be a list of load case ids")
        checked_refs = []
        for ref in refs:
            checked_refs.append(_text(ref, f"{owner}.load_cases ref", MAX_ID_LEN, agg, "requirements"))
        reqs.append({"id": rid, "input_index": index,
                     "verification_method": _optional_text(raw, "verification_method", owner, agg, "requirements"),
                     "acceptance": _optional_text(raw, "acceptance", owner, agg, "requirements"),
                     "load_cases": list(dict.fromkeys(checked_refs))})
    lcs_raw = data.get("load_cases", [])
    if type(lcs_raw) is not list:  # exact type
        _invalid("load_cases must be a list of load case objects")
    if len(lcs_raw) > MAX_LOAD_CASES:
        _limit(f"load_cases count {len(lcs_raw)} exceeds limit {MAX_LOAD_CASES}")
    seen_lc: set[str] = set()
    load_cases: list[dict] = []
    for index, raw in enumerate(lcs_raw):
        owner = f"load_cases[{index}]"
        if type(raw) is not dict:  # exact type
            _invalid(f"{owner} must be an object")
        if len(raw) > len(_LC_KEYS):
            _unknown_key(owner)
        for key in raw:
            if key not in _LC_KEYS:
                _unknown_key(owner)
        lid = _id(raw.get("id"), owner, agg, "load_cases")
        if lid in seen_lc:
            _invalid("duplicate id in load_cases")
        seen_lc.add(lid)
        load_cases.append({"id": lid, "description": _optional_text(raw, "description", owner, agg, "load_cases")})
    declared = {lc["id"] for lc in load_cases}
    for r in reqs:
        for ref in r["load_cases"]:
            if ref not in declared:
                _refuse("unknown_reference",
                        f"unknown load case reference at requirements[{r['input_index']}].load_cases")
    interfaces_raw = data.get("interfaces", [])
    if type(interfaces_raw) is not list:  # exact type: subclasses refused before len
        _invalid("interfaces must be a list of non-empty interface ids")
    if len(interfaces_raw) > MAX_INTERFACES:
        _limit(f"interfaces count {len(interfaces_raw)} exceeds limit {MAX_INTERFACES}")
    if any(not isinstance(x, str) or not x for x in interfaces_raw):
        _invalid("interfaces must be a list of non-empty interface ids")
    interfaces: list[str] = []
    seen_if: set[str] = set()
    for index, iid in enumerate(interfaces_raw):
        interfaces.append(_text(iid, f"interfaces[{index}] id", MAX_ID_LEN, agg, "interfaces"))
        if iid in seen_if:
            _invalid("duplicate id in interfaces")
        seen_if.add(iid)
    units_raw = data.get("units", {})
    if type(units_raw) is not dict:  # exact type: subclasses refused before len
        _invalid("units must be an object of string unit labels")
    if len(units_raw) > MAX_UNITS_KEYS:  # count cap before any iteration
        _limit(f"units count {len(units_raw)} exceeds limit {MAX_UNITS_KEYS}")
    units: dict[str, str] = {}
    for key, value in units_raw.items():
        if not isinstance(key, str):
            _invalid("units must be an object of string unit labels")
        _text(key, "units key", MAX_UNITS_KEY_LEN, agg, "units")
        if not isinstance(value, str):
            _invalid("units must be an object of string unit labels")
        units[key] = _text(value, "units value", MAX_UNITS_VALUE_LEN, agg, "units")
    return (reqs, load_cases, interfaces, units,
            _str_list(data, "assumptions", MAX_LOAD_CASES, agg),
            _str_list(data, "source_refs", MAX_LOAD_CASES, agg))


def evaluate_design_review(data: Any) -> dict[str, Any]:
    """Return the exact verification-coverage evaluation of the supplied declaration.

    The incoming object is validated read-only: type and shape checks first, then
    count caps, and only then per-item iteration. Nothing copies the caller's
    object. The receipt and the provenance hash are built only from validated
    values in fresh containers (the alias fix is a bounded post-validation field
    copy), so mutating the caller's data after the call cannot change the receipt,
    mutating the receipt cannot reach the caller's data, and two calls over the
    same input return byte-identical receipts.
    """
    reqs, load_cases, interfaces, units, assumptions, source_refs = _validate(data)
    referenced: set[str] = set()
    matrix = []
    for r in sorted(reqs, key=lambda x: x["id"]):
        covered = bool(r["verification_method"]) and bool(r["acceptance"])
        referenced.update(r["load_cases"])
        matrix.append({"requirement_id": r["id"],
                       "verification_method": r["verification_method"],
                       "acceptance": r["acceptance"],
                       "load_cases": list(r["load_cases"]),
                       "covered": covered})
    uncovered = sorted(r["id"] for r in reqs if not (r["verification_method"] and r["acceptance"]))
    declared = {lc["id"] for lc in load_cases}
    canonical_obj: dict[str, Any] = {}
    if "requirements" in data:
        canon_reqs = []
        for r, raw in zip(sorted(reqs, key=lambda x: x["input_index"]),
                          (data["requirements"][r["input_index"]] for r in sorted(reqs, key=lambda x: x["input_index"]))):
            entry: dict[str, Any] = {"id": r["id"]}
            if "verification_method" in raw:
                entry["verification_method"] = r["verification_method"]
            if "acceptance" in raw:
                entry["acceptance"] = r["acceptance"]
            if "load_cases" in raw:
                entry["load_cases"] = list(r["load_cases"])
            canon_reqs.append(entry)
        canonical_obj["requirements"] = canon_reqs
    if "load_cases" in data:
        canonical_obj["load_cases"] = [
            {k: v for k, v in lc.items() if k in data["load_cases"][i] or k == "id"}
            for i, lc in enumerate(load_cases)]
    if "interfaces" in data:
        canonical_obj["interfaces"] = list(interfaces)
    if "units" in data:
        canonical_obj["units"] = dict(units)
    if "assumptions" in data:
        canonical_obj["assumptions"] = list(assumptions)
    if "source_refs" in data:
        canonical_obj["source_refs"] = list(source_refs)
    canonical = json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"))
    return {
        "row": 1510,
        "capability": "Mechanical Design",
        "scope": "supplied_design_review_matrix",
        "status": "evaluation_complete",
        "verification_matrix": matrix,
        "summary": {
            "requirement_count": len(reqs),
            "covered_count": len(reqs) - len(uncovered),
            "uncovered_count": len(uncovered),
            "uncovered_requirement_ids": uncovered,
            "declared_load_case_count": len(load_cases),
            "referenced_load_case_ids": sorted(referenced),
            "unreferenced_load_case_ids": sorted(declared - referenced),
            "requirements_complete": not uncovered,
        },
        "interfaces": list(interfaces),
        "input_trace": [{"requirement_id": r["id"], "input_index": r["input_index"]} for r in reqs],
        "units": dict(units),
        "assumptions": list(assumptions),
        "source_refs": list(source_refs),
        "provenance": {
            "input_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "hash_scope": "validated_normalized_fields",
            "declarations_not_measurements": True,
            "computed_not_physically_verified": True,
            "solver_or_cad_executed": False,
            "physical_test_performed": False,
        },
        "boundary": {
            "requires_engineer_review": True,
            "not_a_certified_design": True,
            "no_machinery_control": True,
            "text": ("A coverage matrix over caller-supplied declarations is not a certified "
                     "design, released drawing, simulation run, laboratory result, or safety "
                     "approval. Qualified engineers validate materials, loads, tests, "
                     "tolerances and certification."),
        },
        "human_review_required": True,
    }
