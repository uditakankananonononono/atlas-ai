r"""Row 1513 Computational Fluid Dynamics: bounded exact supplied mass-flow balance.

Evaluates caller-declared flow ports: exact direction totals, mass imbalance
percentage against the cluster-parity denominator floor, closure against a
declared tolerance, and per-port shares. All arithmetic is exact rational
(Fraction) over the declared values. No solver runs, no mesh is generated, no
flow field is computed; declarations only. Standard library only.

Numeric rule (uniform, author-final): int, float and str accepted, bool refused.
Strings: raw length cap first (80), then a strip of ONLY ASCII U+0020 at both
ends, then a full match against the ASCII grammar
^-?(0|[1-9][0-9]*)(\.[0-9]+)?(/[1-9][0-9]*)?$ with at most 64 digits per part;
Fraction conversion happens only after the grammar passes. Integers: bit_length
<= 213 as a cheap pre-convert check. Floats: finite and within range first,
then Fraction(repr(x)) - the shortest decimal round trip, so 0.1 is exactly
1/10; the string grammar is not applied to repr output. Magnitude range 1e12
applies to all three by exact Fraction compare.

Validation (v3 order): for every field the type/shape check comes first, then
the count cap (a len() call, no iteration), and only then any per-item
iteration or allocation. For every string: length cap first, then the Unicode
check (no Unicode control, line/paragraph separator or bidi/format characters),
then aggregate accounting. Strict key allowlists with count caps before the
allowlist scan. The incoming object is never copied: the receipt and the
provenance hash are built only from validated values in fresh containers, so no
receipt structure aliases a caller-owned object. Refusal reasons are generic
and name schema fields only; they never contain a caller key, value, id, or any
repr of caller content.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from fractions import Fraction
from typing import Any

MAX_PORTS = 64
MAX_BOUNDARY_CONDITIONS = 64
MAX_BC_ITEM_LEN = 256
MAX_ID_LEN = 128
MAX_TEXT_LEN = 256
MAX_RAW_NUMERIC_LEN = 80
MAX_DIGITS_PER_PART = 64
MAX_INT_BIT_LENGTH = 213
MAX_MAGNITUDE = Fraction(10 ** 12)
MAX_AGGREGATE_STRING_LEAVES = 100000
DENOM_FLOOR = Fraction(1, 10 ** 12)  # cluster parity: max(abs(total_in), 1e-12)

_PREFIX = "COMPUT1513:"
_TOP_KEYS = ("domain", "turbulence_model", "boundary_conditions", "ports",
             "closure_tolerance_percent")
_PORT_KEYS = ("id", "direction", "mass_flow_kg_per_s")
_NUM_RE = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?(/[1-9][0-9]*)?$")

_LISTED_CF = (set(range(0x200B, 0x2010)) | set(range(0x202A, 0x202F))
              | set(range(0x2066, 0x206A)) | {0xFEFF})
_UNICODE_MSG = ("contains a disallowed character: no Unicode control, "
                "line/paragraph separator or bidi/format characters")


class CfdBalanceRefusal(ValueError):
    """The request was refused; .code is machine readable, str() is the exact reason."""

    def __init__(self, code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def _refuse(kind: str, message: str) -> None:
    code = _PREFIX + kind
    raise CfdBalanceRefusal(code, code + ": " + message)


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
            _limit(f"aggregate string leaves exceed limit {MAX_AGGREGATE_STRING_LEAVES} "
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


def _number(value: Any, owner: str, agg: _Aggregate, field_class: str) -> Fraction:
    """Parse a declared number under the uniform numeric rule (see module docstring)."""
    if value is None:
        _invalid(f"{owner} is required")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        _invalid(f"{owner} must be a finite number or numeric string")
    if isinstance(value, int):
        if value.bit_length() > MAX_INT_BIT_LENGTH:
            _limit(f"{owner} integer bit length exceeds limit {MAX_INT_BIT_LENGTH}")
        fr = Fraction(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            _invalid(f"{owner} must be a finite number or numeric string")
        if abs(value) > float(10 ** 12):
            _limit(f"{owner} magnitude exceeds limit 1000000000000")
        fr = Fraction(repr(value))  # shortest decimal round trip: 0.1 is exactly 1/10
    else:
        if len(value) > MAX_RAW_NUMERIC_LEN:  # raw length cap first, before any strip
            _limit(f"{owner} is {len(value)} characters, limit is {MAX_RAW_NUMERIC_LEN}")
        agg.add(value, field_class)
        stripped = value.strip(" ")  # ASCII U+0020 only
        match = _NUM_RE.fullmatch(stripped)
        if not match:
            _invalid(f"{owner} must be a finite number or numeric string")
        body = stripped.lstrip("-")
        core, _, dpart = body.partition("/")
        ipart, _, fpart = core.partition(".")
        tokens = [(ipart, fpart)]
        if dpart:
            tokens.append((dpart, ""))
        for tw, tf in tokens:  # each token: whole part + fractional part
            if len(tf) > MAX_DIGITS_PER_PART:
                _limit(f"{owner} has more than {MAX_DIGITS_PER_PART} fractional digits")
            if len((tw + tf).lstrip("0")) > MAX_DIGITS_PER_PART:
                _limit(f"{owner} has more than {MAX_DIGITS_PER_PART} significant digits")
        fr = Fraction(int(ipart + fpart), 10 ** len(fpart))
        if dpart:
            fr /= int(dpart)
        if stripped.startswith("-"):
            fr = -fr
    if abs(fr) > MAX_MAGNITUDE:
        _limit(f"{owner} magnitude exceeds limit 1000000000000")
    return fr


def _validate(data: Any) -> tuple[list[dict], Fraction, Any, Any, list]:
    if type(data) is not dict:  # exact type: subclasses refused before len
        _invalid("input must be an object")
    if len(data) > len(_TOP_KEYS):  # count cap before the allowlist scan
        _invalid("unknown key at input")
    for key in data:
        if key not in _TOP_KEYS:
            _invalid("unknown key at input")
    agg = _Aggregate()
    ports_raw = data.get("ports")
    if type(ports_raw) is not list:  # exact type: subclasses refused before len
        _invalid(f"ports must be a list of 1..{MAX_PORTS} port objects")
    if len(ports_raw) > MAX_PORTS:
        _limit(f"ports count {len(ports_raw)} exceeds limit {MAX_PORTS}")
    if len(ports_raw) < 1:
        _invalid(f"ports must be a list of 1..{MAX_PORTS} port objects")
    seen: set[str] = set()
    ports: list[dict] = []
    for index, raw in enumerate(ports_raw):
        owner = f"ports[{index}]"
        if type(raw) is not dict:  # exact type
            _invalid(f"{owner} must be an object")
        if len(raw) > len(_PORT_KEYS):  # count cap before the allowlist scan
            _invalid("unknown key at ports")
        for key in raw:
            if key not in _PORT_KEYS:
                _invalid("unknown key at ports")
        pid = raw.get("id")
        if not isinstance(pid, str) or not pid:
            _invalid(f"{owner}.id requires a non-empty string")
        _text(pid, f"{owner}.id", MAX_ID_LEN, agg, "ports")
        if pid in seen:
            _invalid("duplicate id in ports")
        seen.add(pid)
        direction = raw.get("direction")
        if direction not in ("in", "out"):
            _invalid(f"{owner}.direction must be 'in' or 'out'")
        rate = _number(raw.get("mass_flow_kg_per_s"), f"{owner}.mass_flow_kg_per_s", agg, "ports")
        if rate < 0:
            _invalid(f"{owner}.mass_flow_kg_per_s must be nonnegative")
        ports.append({"id": pid, "direction": direction, "rate": rate, "input_index": index})
    tol = Fraction(5)
    if "closure_tolerance_percent" in data:
        tol = _number(data["closure_tolerance_percent"], "closure_tolerance_percent", agg, "closure_tolerance_percent")
        if tol < 0 or tol > 100:
            _invalid("closure_tolerance_percent must be within 0..100")
    bcs_raw = data.get("boundary_conditions", [])
    if type(bcs_raw) is not list:  # exact type: tuples/dicts/subclasses refused before len
        _invalid("boundary_conditions must be a list of strings")
    if len(bcs_raw) > MAX_BOUNDARY_CONDITIONS:  # count cap before any iteration
        _limit(f"boundary_conditions count {len(bcs_raw)} exceeds limit {MAX_BOUNDARY_CONDITIONS}")
    if any(not isinstance(x, str) for x in bcs_raw):
        _invalid("boundary_conditions must be a list of strings")
    bcs = []
    for index, bc in enumerate(bcs_raw):
        bcs.append(_text(bc, f"boundary_conditions[{index}]", MAX_BC_ITEM_LEN, agg, "boundary_conditions"))
    for name in ("domain", "turbulence_model"):
        v = data.get(name)
        if v is not None:
            if not isinstance(v, str):
                _invalid(f"{name} must be a string when provided")
            _text(v, name, MAX_TEXT_LEN, agg, name)
    return ports, tol, data.get("domain"), data.get("turbulence_model"), bcs


def _exact(fr: Fraction) -> str:
    """Exact rendering: terminating decimals as decimal strings, else 'num/den'."""
    if fr.denominator == 1:
        return str(fr.numerator)
    den = fr.denominator
    for p in (2, 5):
        while den % p == 0:
            den //= p
    if den != 1:
        return f"{fr.numerator}/{fr.denominator}"
    num, d, scale = fr.numerator, fr.denominator, 0
    while d != 1:
        if d % 10 == 0:
            d //= 10
            scale += 1
        elif d % 2 == 0:
            d //= 2
            scale += 1
            num *= 5
        else:
            d //= 5
            scale += 1
            num *= 2
    s = str(abs(num)).rjust(scale + 1, "0")
    s = s[:-scale] + "." + s[-scale:]
    s = s.rstrip("0").rstrip(".")
    return ("-" if num < 0 else "") + s


def evaluate_flow_balance(data: Any) -> dict[str, Any]:
    """Return the exact mass-flow balance evaluation of the supplied port declarations.

    The incoming object is validated read-only: type and shape checks first,
    then count caps, and only then per-item iteration. Nothing copies the
    caller's object. The receipt and the provenance hash are built only from
    validated values in fresh containers (the alias fix is a bounded
    post-validation field copy), so no receipt structure (the
    boundary_conditions list included) aliases a caller-owned object, and two
    calls over the same input return byte-identical receipts.
    """
    ports, tol, domain, turb, bcs = _validate(data)
    tin = sum((p["rate"] for p in ports if p["direction"] == "in"), Fraction(0))
    tout = sum((p["rate"] for p in ports if p["direction"] == "out"), Fraction(0))
    denom = max(abs(tin), DENOM_FLOOR)
    imbalance = abs(tin - tout) / denom * 100
    rows = []
    for p in ports:
        total = tin if p["direction"] == "in" else tout
        share = None if total == 0 else _exact(p["rate"] / total * 100)
        rows.append({"id": p["id"], "direction": p["direction"],
                     "mass_flow_kg_per_s": _exact(p["rate"]),
                     "share_of_direction_percent": share})

    def largest(direction: str, total: Fraction) -> dict | None:
        best = None
        for p in ports:
            if p["direction"] != direction or total == 0:
                continue
            share = p["rate"] / total * 100
            if best is None or share > best[0]:
                best = (share, p["id"])
        return None if best is None else {"id": best[1], "share_percent": _exact(best[0])}

    canonical_obj: dict[str, Any] = {}
    if "ports" in data:
        canon_ports = []
        for p, raw in zip(ports, data["ports"]):
            entry: dict[str, Any] = {"id": p["id"], "direction": p["direction"]}
            if "mass_flow_kg_per_s" in raw:
                entry["mass_flow_kg_per_s"] = raw["mass_flow_kg_per_s"]
            canon_ports.append(entry)
        canonical_obj["ports"] = canon_ports
    if "closure_tolerance_percent" in data:
        canonical_obj["closure_tolerance_percent"] = data["closure_tolerance_percent"]
    if "boundary_conditions" in data:
        canonical_obj["boundary_conditions"] = list(bcs)
    if "domain" in data:
        canonical_obj["domain"] = domain
    if "turbulence_model" in data:
        canonical_obj["turbulence_model"] = turb
    canonical = json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"))
    return {
        "row": 1513,
        "capability": "Computational Fluid Dynamics",
        "scope": "supplied_mass_flow_balance",
        "status": "evaluation_complete",
        "domain": domain,
        "turbulence_model": turb,
        "boundary_conditions": list(bcs),
        "port_rows": rows,
        "totals": {"mass_in_kg_per_s": _exact(tin), "mass_out_kg_per_s": _exact(tout)},
        "mass_imbalance_percent": _exact(imbalance),
        "closure_tolerance_percent": _exact(tol),
        "balanced_to_tolerance": imbalance <= tol,
        "largest_inflow": largest("in", tin),
        "largest_outflow": largest("out", tout),
        "summary": {
            "port_count": len(ports),
            "inflow_count": sum(1 for p in ports if p["direction"] == "in"),
            "outflow_count": sum(1 for p in ports if p["direction"] == "out"),
        },
        "input_trace": [{"port_id": p["id"], "input_index": p["input_index"]} for p in ports],
        "provenance": {
            "input_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "hash_scope": "validated_fields",
            "declarations_not_simulation": True,
            "solver_run_claimed": False,
        },
        "boundary": {
            "requires_engineer_review": True,
            "not_a_simulation_run": True,
            "no_machinery_control": True,
            "text": ("A mass-flow balance over caller-supplied declarations is not a CFD "
                     "simulation run, a mesh convergence study, a validated flow field, or a "
                     "certification. Qualified engineers validate models, boundary conditions "
                     "and results; Atlas never controls machinery or certifies a design."),
        },
        "human_review_required": True,
    }
