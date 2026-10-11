"""Row 1530 Design for Six Sigma: CTQ/DMADV bookkeeping over supplied inputs.

Checks caller-supplied CTQ specifications (lower <= target <= upper where
given), verification-plan references and the declared DMADV phase, and lists
CTQs without a specification (open) or without any verification-plan item.
It computes no sigma level and makes no statistical-validation claim.
"""
import unicodedata
from decimal import Decimal, InvalidOperation

MAX_CTQS = 64
MAX_PLAN = 128
MAX_TEXT = 128
MAX_MAGNITUDE = 10 ** 12
PHASES = ("define", "measure", "analyze", "design", "verify")

_TOP = frozenset(("dmadv_phase", "ctqs", "verification_plan"))
_CTQ = frozenset(("id", "name", "specification"))
_SPEC = frozenset(("unit", "lower", "target", "upper"))
_PLAN = frozenset(("id", "ctq_id", "method"))


def _fail(code):
    raise ValueError("DFSS1530:" + code)


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


def _num(value, field):
    if type(value) not in (int, float) or (type(value) is int and value.bit_length() > 64) or (type(value) is float and value != value) or abs(value) > MAX_MAGNITUDE:
        _fail("invalid_number:" + field)
    try:
        return Decimal(str(value))
    except InvalidOperation:
        _fail("invalid_number:" + field)


def _items(value, name, lo, hi, allowed):
    if type(value) is not list or not lo <= len(value) <= hi:
        _fail("invalid_count:" + name)
    for item in value:
        if type(item) is not dict:
            _fail("invalid_item:" + name)
        if _extra(item, allowed):
            _fail("unknown_key")
    return value


def _check_spec(spec):
    if type(spec) is not dict:
        _fail("invalid_item:specification")
    if _extra(spec, _SPEC):
        _fail("unknown_key")
    if not any(k in spec for k in ("lower", "target", "upper")):
        _fail("specification_needs_bound")
    _text(spec.get("unit"), "unit")
    given = [_num(spec[k], k) for k in ("lower", "target", "upper") if k in spec]
    if any(a > b for a, b in zip(given, given[1:])):
        _fail("invalid_specification")


def run(request):
    if type(request) is not dict:
        _fail("invalid_request")
    if _extra(request, _TOP):
        _fail("unknown_key")
    phase = request.get("dmadv_phase")
    if phase not in PHASES:
        _fail("invalid_phase")
    ctqs = _items(request.get("ctqs"), "ctqs", 1, MAX_CTQS, _CTQ)
    plan = _items(request.get("verification_plan", []), "verification_plan", 0, MAX_PLAN, _PLAN)
    ids, open_ids = [], []
    for c in ctqs:
        cid = _text(c.get("id"), "id")
        if cid in ids:
            _fail("duplicate_id:ctqs")
        ids.append(cid)
        _text(c.get("name"), "name")
        if "specification" in c:
            _check_spec(c["specification"])
        else:
            open_ids.append(cid)
    counts = {cid: 0 for cid in ids}
    plan_seen = set()
    for item in plan:
        pid = _text(item.get("id"), "id")
        if pid in plan_seen:
            _fail("duplicate_id:verification_plan")
        plan_seen.add(pid)
        _text(item.get("method"), "method")
        ref = _text(item.get("ctq_id"), "ctq_id")
        if ref not in counts:
            _fail("unknown_ctq")
        counts[ref] += 1
    unverified = [cid for cid in ids if counts[cid] == 0]
    notes = []
    if PHASES.index(phase) >= 3 and open_ids:
        notes.append("open_ctq_at_design_or_verify")
    if phase == "verify" and unverified:
        notes.append("unverified_ctq_at_verify")
    return {"phase": phase, "phase_index": PHASES.index(phase), "open_ctq_ids": open_ids,
            "unverified_ctq_ids": unverified, "plan_items_by_ctq": counts, "phase_gate_notes": notes,
            "statistical_validation_claimed": False, "sigma_level_computed": False,
            "summary": {"ctq_count": len(ids), "open_count": len(open_ids), "unverified_count": len(unverified),
                        "plan_item_count": len(plan)}}
