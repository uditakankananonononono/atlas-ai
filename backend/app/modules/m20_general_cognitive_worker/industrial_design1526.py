"""Row 1526 Industrial Design: concept/selection bookkeeping over supplied inputs.

Weighted decision matrix over caller-supplied criteria weights (integer 1..100)
and concept scores (integer 0..10): exact integer totals, exact fractions of
the maximum, ranking with shared ranks for ties. It selects nothing, is never
release ready and makes no manufacturing claim.
"""
import unicodedata
from fractions import Fraction

MAX_CRITERIA = 16
MAX_CONCEPTS = 32
MAX_NEEDS = 64
MAX_EVIDENCE = 64
MAX_TEXT = 128

_TOP = frozenset(("criteria", "concepts", "user_needs", "prototype_evidence"))
_CRIT = frozenset(("id", "weight"))
_CONC = frozenset(("id", "name", "scores"))
_NEED = frozenset(("id", "text"))
_EVID = frozenset(("id", "concept_id"))


def _fail(code):
    raise ValueError("INDUST1526:" + code)


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


def _unique(rows, name):
    seen = set()
    for row in rows:
        ident = _text(row.get("id"), "id")
        if ident in seen:
            _fail("duplicate_id:" + name)
        seen.add(ident)
    return seen


def run(request):
    if type(request) is not dict:
        _fail("invalid_request")
    if _extra(request, _TOP):
        _fail("unknown_key")
    criteria = _items(request.get("criteria"), "criteria", 1, MAX_CRITERIA, _CRIT)
    concepts = _items(request.get("concepts"), "concepts", 1, MAX_CONCEPTS, _CONC)
    needs = _items(request.get("user_needs", []), "user_needs", 0, MAX_NEEDS, _NEED)
    evidence = _items(request.get("prototype_evidence", []), "prototype_evidence", 0, MAX_EVIDENCE, _EVID)
    crit_ids = _unique(criteria, "criteria")
    weights = {}
    for c in criteria:
        w = c.get("weight")
        if type(w) is not int or not 1 <= w <= 100:
            _fail("invalid_weight")
        weights[c["id"]] = w
    concept_ids = _unique(concepts, "concepts")
    _unique(needs, "user_needs")
    for n in needs:
        _text(n.get("text"), "text")
    _unique(evidence, "prototype_evidence")
    counts = {cid: 0 for cid in sorted(concept_ids)}
    for e in evidence:
        _text(e.get("concept_id"), "concept_id")
        if e.get("concept_id") not in concept_ids:
            _fail("unknown_concept")
        counts[e["concept_id"]] += 1
    maximum = 10 * sum(weights.values())
    rows = []
    for c in concepts:
        _text(c.get("name"), "name")
        scores = c.get("scores")
        if type(scores) is not dict:
            _fail("invalid_item:scores")
        if _extra(scores, crit_ids):
            _fail("unknown_criterion")
        if crit_ids - set(scores):
            _fail("missing_score")
        total = 0
        for cid, s in scores.items():
            if type(s) is not int or not 0 <= s <= 10:
                _fail("invalid_score")
            total += weights[cid] * s
        frac = Fraction(total, maximum)
        rows.append({"id": c["id"], "name": c["name"], "weighted_total": total,
                     "fraction_of_max": "%d/%d" % (frac.numerator, frac.denominator)})
    rows.sort(key=lambda r: (-r["weighted_total"], r["id"]))
    for i, row in enumerate(rows):
        same = [r["id"] for r in rows if r["weighted_total"] == row["weighted_total"] and r["id"] != row["id"]]
        row["rank"] = 1 + sum(1 for r in rows if r["weighted_total"] > row["weighted_total"])
        row["tied_with"] = same
    return {"ranking": rows, "max_possible_total": maximum, "tie_at_top": bool(rows[0]["tied_with"]),
            "selected_concept": None, "selection_requires_human_decision": True, "release_ready": False,
            "manufacturing_claims": False, "prototype_evidence_counts": counts,
            "user_need_count": len(needs)}
