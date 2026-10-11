"""[Row 105] Pre-Suasion: exact bookkeeping of a disclosed context-setting plan over supplied attention weights.

The caller declares a context label, whether the context-setting is disclosed, and a list of non-negative integer
attention weights. The unit reports the exact shares, the most concentrated share (all ties), a Shannon balance figure
and whether covert influence is blocked. It never decides how to prime anyone, never sends or posts anything,
measures no behaviour, predicts no response and gives no advice. Undisclosed context-setting blocks deployment.
"""
from __future__ import annotations

import math
import unicodedata
from fractions import Fraction

ROW = 105
CODE = "PRESUA105"
MAX_CONTEXT = 200
MIN_WEIGHTS, MAX_WEIGHTS = 2, 20
MAX_WEIGHT = 10**9
LIMITS = (
    "Supplied weights only; nothing here measures where anyone's attention goes.",
    "Context-setting must be disclosed to the people it concerns; an undisclosed plan is never allowed.",
    "Not persuasion, not a measurement and not advice; the balance figure describes the supplied numbers only.",
)
_KEYS = ("context", "disclosed", "attention_weights")
_BAD_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})


class PreSuasionError(ValueError):
    pass


def _fail(msg):
    raise PreSuasionError(f"{CODE}: {msg}")


def _text(value, field, limit):
    if type(value) is not str:
        _fail(f"{field} must be a string")
    if len(value) > limit:  # raw cap before any strip or scan
        _fail(f"{field} is longer than {limit} characters")
    if not value.strip():
        _fail(f"{field} must not be blank")
    for ch in value:
        if unicodedata.category(ch) in _BAD_CATEGORIES:
            _fail(f"{field} contains a control, format or separator character")
    return value


def review(data):
    if type(data) is not dict:
        _fail("input must be a mapping")
    if len(data) > len(_KEYS):  # key count before any key is read
        _fail("too many keys")
    for k in data:
        if type(k) is not str or k not in _KEYS:
            _fail("unknown key")
    for k in _KEYS:
        if k not in data:
            _fail(f"{k} required")
    context = _text(data["context"], "context", MAX_CONTEXT)
    if type(data["disclosed"]) is not bool:
        _fail("disclosed must be true or false")
    disclosed = data["disclosed"]
    weights = data["attention_weights"]
    if type(weights) is not list or not MIN_WEIGHTS <= len(weights) <= MAX_WEIGHTS:
        _fail(f"attention_weights must be a list of {MIN_WEIGHTS} to {MAX_WEIGHTS} items")
    for w in weights:
        if type(w) is not int or not 0 <= w <= MAX_WEIGHT:
            _fail(f"attention_weights items must be integers from 0 to {MAX_WEIGHT}")
    total = sum(weights)
    if total <= 0:
        _fail("attention_weights must have a positive total")
    shares = [Fraction(w, total) for w in weights]
    top = max(shares)
    entropy_sum = 0.0
    for s in shares:
        if s:
            p = float(s)
            entropy_sum += p * math.log(p)
    balance = round(min(1.0, max(0.0, (0.0 - entropy_sum) / math.log(len(shares)))), 6)
    return {
        "row": ROW, "context": context, "disclosed": disclosed,
        "shares": [f"{s.numerator}/{s.denominator}" for s in shares],
        "max_share": f"{top.numerator}/{top.denominator}",
        "max_share_index": [i for i, s in enumerate(shares) if s == top],
        "balance": balance,
        "concentration_check": top <= Fraction(1, 2),
        "covert_influence_blocked": not disclosed, "allowed": disclosed,
        "limits": list(LIMITS),
    }
