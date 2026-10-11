"""Row 1528 Design for Assembly: part-reduction bookkeeping over supplied parts.

A part is counted essential when the caller flags that it moves relative to
others, must be a different material, or must be removable for service. The
unit reports the theoretical minimum part count, combination candidates and
exact reduction/efficiency fractions. No assembly time, line or cost claim.
"""
import unicodedata
from fractions import Fraction

MAX_PARTS = 128
MAX_STEPS = 128
MAX_STEP_PARTS = 32
MAX_TEXT = 128

_TOP = frozenset(("parts", "assembly_steps"))
_FLAGS = ("moves_relative", "different_material_required", "service_removal_required")
_PART = frozenset(("id",) + _FLAGS)
_STEP = frozenset(("id", "part_ids"))


def _fail(code):
    raise ValueError("DESASS1528:" + code)


_BAD_CHARS = frozenset("\x7f\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff")


def _has_forbidden(value):
    return any(c in _BAD_CHARS or unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in value)


MAX_KEYS = 64


def _extra(d, allowed):
    # key count is checked before any set construction or iteration
    if len(d) > MAX_KEYS:
        _fail("invalid_count:keys")
    return set(d) - allowed


def _text(value, field):
    if type(value) is not str or not 1 <= len(value) <= MAX_TEXT or not value.strip() or _has_forbidden(value):
        _fail("invalid_text:" + field)
    return value


def _items(value, name, lo, hi, allowed):
    if type(value) is not list or not lo <= len(value) <= hi:
        _fail("invalid_count:" + name)
    for item in value:
        if type(item) is not dict:
            _fail("invalid_item:" + name)
        if _extra(item, allowed):
            _fail("unknown_key")
    return value


def _frac(f):
    return str(f.numerator) if f.denominator == 1 else "%d/%d" % (f.numerator, f.denominator)


def run(request):
    if type(request) is not dict:
        _fail("invalid_request")
    if _extra(request, _TOP):
        _fail("unknown_key")
    parts = _items(request.get("parts"), "parts", 1, MAX_PARTS, _PART)
    steps = _items(request.get("assembly_steps", []), "assembly_steps", 0, MAX_STEPS, _STEP)
    ids, essential, candidates = set(), [], []
    for p in parts:
        pid = _text(p.get("id"), "id")
        if pid in ids:
            _fail("duplicate_id:parts")
        ids.add(pid)
        for flag in _FLAGS:
            if type(p.get(flag)) is not bool:
                _fail("invalid_bool:" + flag)
        if any(p[flag] for flag in _FLAGS):
            essential.append(pid)
        else:
            candidates.append(pid)
    step_ids, used = set(), set()
    for s in steps:
        sid = _text(s.get("id"), "id")
        if sid in step_ids:
            _fail("duplicate_id:assembly_steps")
        step_ids.add(sid)
        refs = s.get("part_ids")
        if type(refs) is not list or not 1 <= len(refs) <= MAX_STEP_PARTS:
            _fail("invalid_count:part_ids")
        for ref in refs:
            _text(ref, "part_ids")
            if ref not in ids:
                _fail("unknown_part")
            used.add(ref)
    total, minimum = len(parts), len(essential)
    return {"part_count": total, "theoretical_minimum_parts": minimum, "essential_part_ids": essential,
            "combination_candidates": candidates, "reduction_fraction": _frac(Fraction(total - minimum, total)),
            "efficiency_ratio": _frac(Fraction(minimum, total)), "step_count": len(steps),
            "parts_without_step": sorted(ids - used), "assembly_time_or_cost_claimed": False}
