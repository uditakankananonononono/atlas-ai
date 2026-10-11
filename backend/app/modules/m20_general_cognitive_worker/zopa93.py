"""Row 93 ZOPA Mapping: intersect DECLARED buyer and seller acceptable-price intervals.

Pure exact-rational arithmetic over supplied intervals. It never infers reservation
values, never claims that an overlap is an agreement, and sends nothing.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any

_LIMITS = (
    "Supplied declared intervals only. Overlap is not agreement and no overlap is not proof "
    "that no deal is possible. No inferred reservation values, no bargaining-power claim, "
    "no persuasion, no external message, counterparty facts unverified."
)
_ALLOWED_TOP = {"currency", "unit", "buyer_intervals", "seller_intervals"}
_ALLOWED_IV = {"id", "low", "high", "low_inclusive", "high_inclusive", "currency", "unit", "source"}


class ZopaError(ValueError):
    pass


def _num(v: Any, name: str) -> Fraction:
    if isinstance(v, bool) or v is None:
        raise ZopaError(f"{name} must be a finite number")
    try:
        if isinstance(v, float):
            if v != v or v in (float("inf"), float("-inf")):
                raise ZopaError(f"{name} must be finite")
            return Fraction(repr(v))
        if isinstance(v, (int, Fraction)):
            return Fraction(v)
        if isinstance(v, str):
            return Fraction(v.strip())
    except (ValueError, ZeroDivisionError) as exc:
        raise ZopaError(f"{name} is not a valid number") from exc
    raise ZopaError(f"{name} must be a finite number")


def _fmt(f: Fraction) -> str:
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def _flag(d: dict, key: str) -> bool:
    v = d.get(key, True)
    if not isinstance(v, bool):
        raise ZopaError(f"{key} must be a boolean")
    return v


def _parse_side(items: Any, side: str, currency: str, unit: str, seen: set) -> list:
    if not isinstance(items, list) or not items:
        raise ZopaError(f"{side} must be a non-empty list")
    out = []
    for item in items:
        if not isinstance(item, dict):
            raise ZopaError(f"{side} entries must be objects")
        extra = set(item) - _ALLOWED_IV
        if extra:
            raise ZopaError(f"unsupported interval fields: {sorted(extra)}")
        i = item.get("id")
        if not isinstance(i, str) or not i.strip():
            raise ZopaError("interval id must be a non-empty string")
        if i in seen:
            raise ZopaError(f"duplicate interval id: {i}")
        seen.add(i)
        for key, want in (("currency", currency), ("unit", unit)):
            if key in item and item[key] != want:
                raise ZopaError(f"{key} mismatch on interval {i}")
        lo, hi = _num(item.get("low"), "low"), _num(item.get("high"), "high")
        li, hi_i = _flag(item, "low_inclusive"), _flag(item, "high_inclusive")
        if lo > hi or (lo == hi and not (li and hi_i)):
            raise ZopaError(f"interval {i} is empty or inverted")
        out.append({"id": i, "lo": lo, "hi": hi, "li": li, "hi_i": hi_i, "source": item.get("source")})
    return out


def _contains(iv: dict, x: Fraction) -> bool:
    return (x > iv["lo"] or (x == iv["lo"] and iv["li"])) and (x < iv["hi"] or (x == iv["hi"] and iv["hi_i"]))


def _intersect(a: dict, b: dict):
    if a["lo"] > b["lo"] or (a["lo"] == b["lo"] and not a["li"]):
        lo, li = a["lo"], a["li"] and (a["lo"] != b["lo"] or b["li"])
    else:
        lo, li = b["lo"], b["li"]
    if a["hi"] < b["hi"] or (a["hi"] == b["hi"] and not a["hi_i"]):
        hi, hi_i = a["hi"], a["hi_i"]
    else:
        hi, hi_i = b["hi"], b["hi_i"]
    if lo > hi or (lo == hi and not (li and hi_i)):
        return None
    return {"lo": lo, "hi": hi, "li": li, "hi_i": hi_i}


def _normalize(ivs: list) -> list:
    """Merge overlapping or touching (at least one inclusive meeting endpoint) intervals."""
    ivs = sorted(ivs, key=lambda d: (d["lo"], not d["li"], d["hi"], not d["hi_i"]))
    out: list = []
    for d in ivs:
        d = dict(d)
        if out:
            p = out[-1]
            if d["lo"] < p["hi"] or (d["lo"] == p["hi"] and (d["li"] or p["hi_i"])):
                if d["hi"] > p["hi"] or (d["hi"] == p["hi"] and d["hi_i"]):
                    p["hi"], p["hi_i"] = d["hi"], d["hi_i"]
                continue
        out.append(d)
    return out


def map_zopa(request: Any) -> dict:
    if not isinstance(request, dict):
        raise ZopaError("request must be an object")
    extra = set(request) - _ALLOWED_TOP
    if extra:
        raise ZopaError(f"unsupported fields: {sorted(extra)}")
    currency, unit = request.get("currency"), request.get("unit")
    for name, v in (("currency", currency), ("unit", unit)):
        if not isinstance(v, str) or not v.strip():
            raise ZopaError(f"{name} must be declared explicitly")
    seen: set = set()
    buyers = _parse_side(request.get("buyer_intervals"), "buyer_intervals", currency, unit, seen)
    sellers = _parse_side(request.get("seller_intervals"), "seller_intervals", currency, unit, seen)
    pieces = []
    for b in buyers:
        for s in sellers:
            x = _intersect(b, s)
            if x:
                pieces.append(x)
    zones = _normalize(pieces)
    result = []
    for z in zones:
        def touches(iv: dict) -> bool:
            return _intersect(iv, z) is not None
        result.append({
            "low": _fmt(z["lo"]), "high": _fmt(z["hi"]),
            "low_inclusive": z["li"], "high_inclusive": z["hi_i"],
            "buyer_ids": sorted(b["id"] for b in buyers if touches(b)),
            "seller_ids": sorted(s["id"] for s in sellers if touches(s)),
        })
    return {
        "feature_row": 93,
        "status": "overlap" if result else "no_overlap",
        "currency": currency, "unit": unit,
        "zopa_intervals": result,
        "sources": {d["id"]: d["source"] for d in buyers + sellers if d["source"] is not None},
        "overlap_is_agreement": False,
        "inferred_reservation_values": False,
        "limits": _LIMITS,
    }
