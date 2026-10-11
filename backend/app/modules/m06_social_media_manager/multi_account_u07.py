"""U07 multi-account manager (oneofficial variant).

Manages a fleet of its owner's own social accounts only: exactly one
official account per platform, hard enforced. No automation-labeled
accounts exist in this variant - any ownership other than 'owner'
refuses. Per-account persona, content calendar, per-account analytics,
and a free sign-up step plan. Every publish intent becomes an m00-style
approval-request payload; nothing here executes a sign-up, send, submit,
or post. Fake identities and altered reposts of other people's content
refuse. All refusals are ValueError prefixed 'ACCTU07:'.
"""
from __future__ import annotations

import re
from datetime import date
from fractions import Fraction

MAX_HANDLE = 30
MAX_TEXT = 5000
MAX_CALENDAR_ENTRIES = 92
MAX_BIO = 500
MAX_CREDIT = 200

PLATFORMS = ("instagram", "tiktok", "twitter", "linkedin")
OWNERSHIP_KINDS = ("owner",)
CONTENT_ORIGINS = ("original", "credited")
STOP_REASONS = ("captcha", "phone", "id", "payment")

_HANDLE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,29}")
_ACCOUNT_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_METRIC_KEYS = ("followers", "impressions", "engagements")

INTERPRETATION = "one official account per platform, owned by the owner; every publish is an approval request, never an execution"

LIMITS = [
    "This unit plans and records only: it never creates accounts, signs up, autofills portals, sends, submits, or posts; every publish intent is an m00 approval request that stays awaiting human approval.",
    "Accounts must be the owner's own: one official account per platform, and any other ownership kind refuses.",
    "Content must be original or carry a credit source; altered reposts of other people's content refuse.",
    "The sign-up plan lists free steps and stops at CAPTCHA, phone, ID, and payment gates; it executes nothing and a human completes any real sign-up themselves.",
    "Analytics summarize only metrics supplied to this unit; nothing is scraped or fetched.",
]


def _fail(msg: str):
    raise ValueError(f"ACCTU07: {msg}")


def _keys(d, allowed, label):
    if not isinstance(d, dict):
        _fail(f"{label} must be an object")
    for k in d:
        if k not in allowed:
            _fail(f"unknown key {k!r} in {label}")


def _date(v, label):
    if not isinstance(v, str) or not _DATE.fullmatch(v):
        _fail(f"{label} date must be ISO YYYY-MM-DD")
    try:
        date.fromisoformat(v)
    except ValueError:
        _fail(f"{label} date {v!r} is not a real calendar day")
    return v


def _check_account_id(v):
    if not isinstance(v, str) or not _ACCOUNT_ID.fullmatch(v):
        _fail("account_id must be 1-40 chars of [A-Za-z0-9_-]")
    return v


def _metric_values(entry, label):
    out = {}
    for k in _METRIC_KEYS:
        v = entry.get(k)
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            _fail(f"{label} {k} must be a non-negative integer")
        out[k] = v
    return out


def create_account(data: dict) -> dict:
    """Validate and normalize one owner account record."""
    _keys(data, {"account_id", "platform", "handle", "ownership", "persona", "source_ref"}, "account")
    account_id = data.get("account_id")
    _check_account_id(account_id)
    if data.get("platform") not in PLATFORMS:
        _fail(f"platform must be one of {list(PLATFORMS)}")
    handle = data.get("handle")
    if not isinstance(handle, str) or not _HANDLE.fullmatch(handle) or len(handle) > MAX_HANDLE:
        _fail(f"handle must match {_HANDLE.pattern} and be at most {MAX_HANDLE} chars")
    if data.get("ownership") not in OWNERSHIP_KINDS:
        _fail("ownership must be 'owner'; only the owner's own official accounts are managed")
    persona = data.get("persona")
    _keys(persona, {"display_name", "bio", "voice", "claims_real_person"}, "persona")
    if persona.get("claims_real_person"):
        _fail("persona must not claim to be a real person")
    if not isinstance(persona.get("display_name"), str) or not persona["display_name"].strip():
        _fail("persona display_name must be non-blank")
    for k in ("display_name", "bio", "voice"):
        v = persona.get(k, "")
        if not isinstance(v, str) or len(v) > MAX_BIO:
            _fail(f"persona {k} must be a string of at most {MAX_BIO} chars")
    src = data.get("source_ref")
    if not isinstance(src, str) or not src.strip() or len(src) > 200:
        _fail("source_ref must be a non-blank string of at most 200 chars")
    return {"account_id": account_id, "platform": data["platform"], "handle": handle,
            "ownership": "owner",
            "persona": {"display_name": persona["display_name"],
                        "bio": persona.get("bio", ""), "voice": persona.get("voice", "")},
            "source_ref": src, "limits": list(LIMITS)}


def new_fleet() -> dict:
    return {"accounts": []}


def add_account(fleet: dict, data: dict) -> dict:
    """Add an owner account to a fleet dict. Exactly one official account
    per platform; a second account on the same platform refuses."""
    _keys(fleet, {"accounts"}, "fleet")
    if not isinstance(fleet.get("accounts"), list):
        _fail("fleet accounts must be a list")
    acc = create_account(data)
    for existing in fleet["accounts"]:
        if (not isinstance(existing, dict) or not isinstance(existing.get("account_id"), str)
                or existing.get("platform") not in PLATFORMS):
            _fail("fleet accounts must be account records with an account_id and a known platform")
        if existing["account_id"] == acc["account_id"]:
            _fail(f"duplicate account_id {acc['account_id']!r}")
        if existing["platform"] == acc["platform"]:
            _fail(f"platform {acc['platform']!r} already has its one official account")
    return {"accounts": fleet["accounts"] + [acc]}


def plan_calendar(account: dict, entries: list) -> dict:
    """Per-account draft calendar. Entries are drafts; nothing is scheduled
    or published."""
    acc = create_account(account)
    if not isinstance(entries, list) or not entries:
        _fail("calendar entries must be a non-empty list")
    if len(entries) > MAX_CALENDAR_ENTRIES:
        _fail(f"calendar entries exceed {MAX_CALENDAR_ENTRIES}")
    out = []
    for i, e in enumerate(entries):
        _keys(e, {"date", "title", "theme", "format"}, f"entries[{i}]")
        _date(e.get("date"), f"entries[{i}]")
        for k in ("title", "theme", "format"):
            if not isinstance(e.get(k), str) or not e[k].strip() or len(e[k]) > 200:
                _fail(f"entries[{i}] {k} must be a non-blank string of at most 200 chars")
        out.append({"date": e["date"], "title": e["title"], "theme": e["theme"],
                    "format": e["format"], "status": "draft"})
    return {"account_id": acc["account_id"], "entries": out}


def record_metrics(account: dict, entry: dict) -> dict:
    """One day of supplied metrics for an account. Nothing is fetched."""
    acc = create_account(account)
    _keys(entry, {"date", "followers", "impressions", "engagements"}, "metrics")
    _date(entry.get("date"), "metrics")
    rec = {"account_id": acc["account_id"], "date": entry["date"]}
    rec.update(_metric_values(entry, "metrics"))
    return rec


def summarize_metrics(account_id: str, records: list) -> dict:
    """Totals plus an exact engagement rate over supplied records."""
    _check_account_id(account_id)
    if not isinstance(records, list) or not records:
        _fail("records must be a non-empty list")
    for r in records:
        _keys(r, {"account_id", "date", "followers", "impressions", "engagements"}, "record")
        if r.get("account_id") != account_id:
            _fail("record account_id does not belong to this account")
        _date(r.get("date"), "record")
        _metric_values(r, "record")
    impressions = sum(r["impressions"] for r in records)
    engagements = sum(r["engagements"] for r in records)
    rate = Fraction(engagements, impressions) if impressions else None
    rate_str = None if rate is None else (str(rate.numerator) if rate.denominator == 1
                                           else f"{rate.numerator}/{rate.denominator}")
    latest = max(r["date"] for r in records)
    return {"account_id": account_id, "records": len(records),
            "impressions_total": impressions, "engagements_total": engagements,
            "engagement_rate": rate_str,
            "followers_latest": next(r["followers"] for r in records if r["date"] == latest)}


def signup_plan(platform: str) -> dict:
    """Free sign-up step plan with hard stops. Executes nothing."""
    if platform not in PLATFORMS:
        _fail(f"platform must be one of {list(PLATFORMS)}")
    steps = [
        {"kind": "open_site", "detail": f"open the official {platform} sign-up page", "cost": "free"},
        {"kind": "fill_profile", "detail": "enter the persona display name, handle and bio", "cost": "free"},
        {"kind": "stop", "reason": "captcha", "detail": "CAPTCHA challenge: a human completes it", "cost": "free"},
        {"kind": "stop", "reason": "phone", "detail": "phone verification: ask the owner", "cost": "free"},
        {"kind": "stop", "reason": "id", "detail": "ID verification: ask the owner", "cost": "free"},
        {"kind": "stop", "reason": "payment", "detail": "any payment step: stop, free sign-ups only", "cost": "free"},
    ]
    return {"platform": platform, "steps": steps, "executes": False}


def propose_post(account: dict, content: dict) -> dict:
    """Turn a publish intent into an m00-style approval request. Never
    publishes. Content must be original or carry a credit source."""
    acc = create_account(account)
    _keys(content, {"text", "origin", "credit_source"}, "content")
    text = content.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        _fail(f"content text must be non-blank and at most {MAX_TEXT} chars")
    origin = content.get("origin")
    if origin == "altered_repost":
        _fail("altered reposts of other people's content refuse; content must be original or credited")
    if origin not in CONTENT_ORIGINS:
        _fail(f"content origin must be one of {list(CONTENT_ORIGINS)}")
    credit = content.get("credit_source")
    if origin == "original" and credit is not None:
        _fail("original content must not carry a credit_source")
    if origin == "credited" and (not isinstance(credit, str) or not credit.strip() or len(credit) > MAX_CREDIT):
        _fail(f"credited content must name its credit_source as a non-blank string of at most {MAX_CREDIT} chars")
    return {"action": "publish", "status": "awaiting_human_approval", "executes": False,
            "account_id": acc["account_id"], "platform": acc["platform"],
            "text": text, "origin": origin, "credit_source": credit,
            "interpretation": INTERPRETATION}
