"""[Row 101] Authority Positioning: exact, deterministic check of which supplied credential declarations may be cited.

Transparent, ethical-use framing. The caller declares a claim and credential records. This function counts only records
that are verified (by a named check the caller supplies), attributable, in date, and relevant to the claim, and says
plainly what is not counted. It verifies nothing itself, predicts no persuasion effect and gives no advice.
"""
from __future__ import annotations

from datetime import date
import re

ROW = 101
CODE = "AUTHOR101"
MAX_CREDENTIALS = 100
MAX_CLAIM = 500
KINDS = ("degree", "license", "publication", "experience", "affiliation")
POINTS = {"direct": 2, "adjacent": 1, "none": 0}
SUPPORTED_MIN_POINTS = 4
SUPPORTED_MIN_ISSUERS = 2
LIMITS = (
    "Supplied declarations only; this function checks consistency and dates, not the truth of any declaration.",
    "No credential is verified by this function; 'verified_by' is the caller's own statement of a check.",
    "Not a prediction of persuasion or any outcome; cite only counted credentials, and disclose the uncounted ones.",
)
_TOP = {"claim", "credentials", "as_of", "disclosed"}
_CRED = {"id", "kind", "issuer", "relevance", "verified_by", "issued_on", "attributable", "expires_on"}


class AuthorityError(ValueError):
    pass


def _fail(msg):
    raise AuthorityError(f"{CODE}: {msg}")


def _day(v, name):
    if not isinstance(v, str):
        _fail(f"{name} must be an ISO date string YYYY-MM-DD")
    try:
        if len(v) != 10 or re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', v) is None:
            raise ValueError
        return date.fromisoformat(v)
    except ValueError:
        _fail(f"{name} must be an ISO date string YYYY-MM-DD")


def _text(v, name):
    if not isinstance(v, str) or not v.strip():
        _fail(f"{name} must be a non-empty string")
    return v


def assess(data):
    if not isinstance(data, dict):
        _fail("input must be a mapping")
    for k in data:
        if k not in _TOP:
            _fail(f"unknown key {k!r}")
    claim = data.get("claim")
    if not isinstance(claim, str) or not claim.strip() or len(claim) > MAX_CLAIM:
        _fail(f"claim must be a non-empty string of at most {MAX_CLAIM} characters")
    creds = data.get("credentials")
    if not isinstance(creds, list) or len(creds) > MAX_CREDENTIALS:
        _fail(f"credentials must be a list of at most {MAX_CREDENTIALS} records")
    if "as_of" not in data:
        _fail("as_of required")
    as_of = _day(data["as_of"], "as_of")
    disclosed = data.get("disclosed")
    if type(disclosed) is not bool:
        _fail("disclosed must be true or false")
    seen = set()
    counted, uncounted, issuers, points = [], [], set(), 0
    for n, c in enumerate(creds):
        if not isinstance(c, dict):
            _fail(f"credential {n} must be a mapping")
        for k in c:
            if k not in _CRED:
                _fail(f"credential {n} has unknown key {k!r}")
        cid = _text(c.get("id"), f"credential {n} id")
        if cid in seen:
            _fail(f"duplicate credential id {cid!r}")
        seen.add(cid)
        if c.get("kind") not in KINDS:
            _fail(f"credential {n} kind must be one of {', '.join(KINDS)}")
        issuer = _text(c.get("issuer"), f"credential {n} issuer")
        rel = c.get("relevance")
        if rel not in POINTS:
            _fail(f"credential {n} relevance must be one of direct, adjacent, none")
        attributable = c.get("attributable")
        if type(attributable) is not bool:
            _fail(f"credential {n} attributable must be true or false")
        issued = _day(c.get("issued_on"), f"credential {n} issued_on")
        if issued > as_of:
            _fail(f"credential {n} issued_on is after as_of")
        expires = None
        if "expires_on" in c:
            expires = _day(c["expires_on"], f"credential {n} expires_on")
            if expires < issued:
                _fail(f"credential {n} expires_on is before issued_on")
        vb = c.get("verified_by")
        reasons = []
        if not (isinstance(vb, str) and vb.strip()):
            reasons.append("unverified")
        if not attributable:
            reasons.append("unattributable")
        if expires is not None and expires < as_of:
            reasons.append("expired")
        if rel == "none":
            reasons.append("not_relevant")
        if reasons:
            uncounted.append({"id": cid, "reasons": reasons})
        else:
            counted.append(cid)
            points += POINTS[rel]
            issuers.add(issuer)
    if points >= SUPPORTED_MIN_POINTS and len(issuers) >= SUPPORTED_MIN_ISSUERS:
        level = "supported"
    elif points >= 1:
        level = "limited"
    else:
        level = "none"
    return {
        "row": ROW, "claim": claim, "as_of": data["as_of"], "counted": counted, "uncounted": uncounted,
        "points": points, "distinct_issuers": len(issuers), "assertion_level": level,
        "release_allowed": disclosed and level != "none", "disclosure_required": [u["id"] for u in uncounted],
        "limits": list(LIMITS),
    }
