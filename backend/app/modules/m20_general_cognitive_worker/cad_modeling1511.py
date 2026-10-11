r"""Row 1511 CAD Modeling: bounded exact supplied feature-tree evaluation.

Evaluates a caller-declared CAD feature tree: order-based reference checking
(a reference must name a feature declared earlier in the tree; self-references
and forward references are findings), an exact deterministic regeneration order
when the tree is clean, and declared-parameter usage. Everything computed comes
from caller-supplied declarations; no geometry kernel runs, no model is rebuilt,
no drawing is released. Standard library only.

Validation (v3 order): every collection requires the exact container type
(type(x) is list/dict) BEFORE len(); then the count cap BEFORE any iteration,
dedup or allocation. For every string: length cap first, then a Unicode check
(no Unicode control, line/paragraph separator or bidi/format characters), then
aggregate accounting. Strict nested key allowlists with key-count caps before
the allowlist scan. The incoming object is never copied: the receipt and the
provenance hash are built only from validated values in fresh containers, so no
receipt structure aliases a caller-owned object. Refusal reasons are generic
and name schema fields only; they never contain a caller key, value, id,
reference, parameter name, or any repr of caller content.

Parameter caps (FINAL author table): MAX_PARAMETERS = 32 is ONE shared number
with two checks - the global parameters object holds at most 32 keys and each
feature's parameters list holds at most 32 entries. Global parameter keys are
strings with a raw cap of 32 checked first; values keep the existing 32-char
cap. Cross-cite: Mechanical Design 1510 keeps its own MAX_UNITS_KEYS=32 /
MAX_UNITS_KEY_LEN=32 / MAX_UNITS_VALUE_LEN=32 and MAX_INTERFACES=64; 1510 has
no parameters field.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

MAX_FEATURES = 64
MAX_REFERENCES = 64
MAX_PARAMETERS = 32  # shared: global parameters keys AND per-feature parameters entries
MAX_ID_LEN = 128
MAX_PARAM_KEY_LEN = 32
MAX_PARAM_VALUE_LEN = 32
MAX_AGGREGATE_STRING_LEAVES = 200000

_PREFIX = "CADMOD1511:"
_TOP_KEYS = ("features", "parameters")
_FEAT_KEYS = ("id", "references", "parameters")

_LISTED_CF = (set(range(0x200B, 0x2010)) | set(range(0x202A, 0x202F))
              | set(range(0x2066, 0x206A)) | {0xFEFF})
_UNICODE_MSG = ("contains a disallowed character: no Unicode control, "
                "line/paragraph separator or bidi/format characters")


class CadModelingRefusal(ValueError):
    """The request was refused; .code is machine readable, str() is the exact reason."""

    def __init__(self, code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def _refuse(kind: str, message: str) -> None:
    code = _PREFIX + kind
    raise CadModelingRefusal(code, code + ": " + message)


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


def _validate(data: Any) -> tuple[list[dict], dict[str, str]]:
    if type(data) is not dict:  # exact type: subclasses refused before len
        _invalid("input must be an object")
    if len(data) > len(_TOP_KEYS):  # count cap before the allowlist scan
        _unknown_key("input")
    for key in data:
        if key not in _TOP_KEYS:
            _unknown_key("input")
    agg = _Aggregate()
    feats_raw = data.get("features")
    if type(feats_raw) is not list:  # exact type
        _invalid(f"features must be a list of 1..{MAX_FEATURES} feature objects")
    if len(feats_raw) > MAX_FEATURES:
        _limit(f"features count {len(feats_raw)} exceeds limit {MAX_FEATURES}")
    if len(feats_raw) < 1:
        _invalid(f"features must be a list of 1..{MAX_FEATURES} feature objects")
    seen: set[str] = set()
    feats: list[dict] = []
    for index, raw in enumerate(feats_raw):
        owner = f"features[{index}]"
        if type(raw) is not dict:  # exact type
            _invalid(f"{owner} must be an object")
        if len(raw) > len(_FEAT_KEYS):  # count cap before the allowlist scan
            _unknown_key(owner)
        for key in raw:
            if key not in _FEAT_KEYS:
                _unknown_key(owner)
        fid = raw.get("id")
        if not isinstance(fid, str) or not fid:
            _invalid(f"{owner}.id requires a non-empty string")
        _text(fid, f"{owner}.id", MAX_ID_LEN, agg, "features")
        if fid in seen:
            _invalid("duplicate id in features")
        seen.add(fid)
        refs = raw.get("references", [])
        if type(refs) is not list:  # exact type
            _invalid(f"{owner}.references must be a list of feature ids")
        if len(refs) > MAX_REFERENCES:  # count cap before any iteration or allocation
            _limit(f"{owner}.references count {len(refs)} exceeds limit {MAX_REFERENCES}")
        if any(not isinstance(x, str) for x in refs):
            _invalid(f"{owner}.references must be a list of feature ids")
        checked_refs = []
        for ref in refs:
            checked_refs.append(_text(ref, f"{owner}.references ref", MAX_ID_LEN, agg, "features"))
        fparams = raw.get("parameters", [])
        if type(fparams) is not list:  # exact type (FINAL author table)
            _invalid(f"{owner}.parameters must be a list of parameter names")
        if len(fparams) > MAX_PARAMETERS:  # shared 32, count cap before any iteration
            _limit(f"{owner}.parameters count {len(fparams)} exceeds limit {MAX_PARAMETERS}")
        if any(not isinstance(x, str) for x in fparams):
            _invalid(f"{owner}.parameters must be a list of parameter names")
        checked_names = []
        for name in fparams:
            checked_names.append(_text(name, f"{owner}.parameters name", MAX_PARAM_KEY_LEN, agg, "features"))
        feats.append({"id": fid, "input_index": index,
                      "references": list(dict.fromkeys(checked_refs)),
                      "parameters": list(dict.fromkeys(checked_names))})
    declared = {f["id"] for f in feats}
    for f in feats:
        for ref in f["references"]:
            if ref not in declared:
                _refuse("unknown_reference",
                        f"unknown feature reference at features[{f['input_index']}].references")
    params_raw = data.get("parameters", {})
    if type(params_raw) is not dict:  # exact type (FINAL author table)
        _invalid("parameters must be an object of string values")
    if len(params_raw) > MAX_PARAMETERS:  # shared 32, count cap before any iteration
        _limit(f"parameters count {len(params_raw)} exceeds limit {MAX_PARAMETERS}")
    params: dict[str, str] = {}
    for key, value in params_raw.items():
        if not isinstance(key, str):
            _invalid("parameters must be an object of string values")
        _text(key, "parameters key", MAX_PARAM_KEY_LEN, agg, "parameters")
        if not isinstance(value, str):
            _invalid("parameters must be an object of string values")
        params[key] = _text(value, "parameters value", MAX_PARAM_VALUE_LEN, agg, "parameters")
    for f in feats:
        for name in f["parameters"]:
            if name not in params:
                _refuse("unknown_parameter",
                        f"unknown parameter reference at features[{f['input_index']}].parameters")
    return feats, params


def _regeneration_order(feats: list[dict]) -> list[str]:
    """Exact deterministic topological order over backward references, lexicographic tie-break."""
    deps = {f["id"]: set(f["references"]) for f in feats}  # all backward, so acyclic
    order: list[str] = []
    ready = sorted(fid for fid, ds in deps.items() if not ds)
    while ready:
        fid = ready.pop(0)
        order.append(fid)
        newly = []
        for other, ds in deps.items():
            if fid in ds:
                ds.discard(fid)
                if not ds:
                    newly.append(other)
        ready = sorted(ready + newly)
    return order


def evaluate_feature_tree(data: Any) -> dict[str, Any]:
    """Return the exact order-based reference evaluation of the supplied feature tree.

    The incoming object is validated read-only: exact container types first,
    then count caps, and only then per-item iteration. Nothing copies the
    caller's object. The receipt and the provenance hash are built only from
    validated values in fresh containers (the alias fix is a bounded
    post-validation field copy), so mutating the caller's data after the call
    cannot change the receipt, mutating the receipt cannot reach the caller's
    data, and two calls over the same input return byte-identical receipts.
    """
    feats, params = _validate(data)
    seen: set[str] = set()
    errors: list[dict] = []
    for f in feats:
        for ref in f["references"]:
            if ref == f["id"]:
                errors.append({"feature": f["id"], "kind": "self_reference", "reference": ref})
            elif ref not in seen:
                errors.append({"feature": f["id"], "kind": "forward_reference", "reference": ref})
        seen.add(f["id"])
    ready = not errors
    used = sorted({name for f in feats for name in f["parameters"]})
    canonical_obj: dict[str, Any] = {}
    if "features" in data:
        canon_feats = []
        for f, raw in zip(feats, data["features"]):
            entry: dict[str, Any] = {"id": f["id"]}
            if "references" in raw:
                entry["references"] = list(f["references"])
            if "parameters" in raw:
                entry["parameters"] = list(f["parameters"])
            canon_feats.append(entry)
        canonical_obj["features"] = canon_feats
    if "parameters" in data:
        canonical_obj["parameters"] = dict(params)
    canonical = json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"))
    return {
        "row": 1511,
        "capability": "CAD Modeling",
        "scope": "supplied_feature_tree_evaluation",
        "status": "evaluation_complete",
        "feature_rows": [{"id": f["id"], "references": list(f["references"]),
                          "parameters": list(f["parameters"])}
                         for f in feats],
        "reference_errors": errors,
        "regeneration_order": _regeneration_order(feats) if ready else None,
        "regeneration_ready": ready,
        "summary": {
            "feature_count": len(feats),
            "error_count": len(errors),
            "parameters_declared": sorted(params),
            "parameters_used": used,
            "parameters_unreferenced": sorted(set(params) - set(used)),
        },
        "input_trace": [{"feature_id": f["id"], "input_index": f["input_index"]} for f in feats],
        "parameters": dict(params),
        "provenance": {
            "input_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "hash_scope": "validated_fields",
            "declarations_not_geometry": True,
            "geometry_kernel_executed": False,
            "regeneration_performed": False,
        },
        "boundary": {
            "requires_engineer_review": True,
            "not_a_released_model": True,
            "no_machinery_control": True,
            "text": ("An order and reference evaluation over a caller-supplied feature tree is "
                     "not a regenerated model, a released drawing, a simulation run, or a "
                     "manufacturing approval. Qualified engineers validate geometry, "
                     "tolerances and certification."),
        },
        "human_review_required": True,
    }
