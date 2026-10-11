"""S4.3 / c35.waiver_drafts - fee-waiver draft queue (PREP ONLY).

Supplied requirement excerpt: "if there is fee, emails for fee waivers".

Fills a supplied waiver template for opportunities that carry a fee and
returns DRAFTS with recipient, subject and a content-hash id. There is no
send, register, submit, payment or login path: this module only builds
text. Any key that names such an action, at any depth of the request,
refuses the whole request. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from decimal import Decimal

from app.modules.c30 import policy

PREFIX = "APPLY"
MAX_OPPORTUNITIES = 1000
MAX_TEMPLATE = 20000
MAX_BODY = 20000
MAX_CONTAINERS = 10000  # request scan budget: distinct dict/list/tuple objects
MAX_DICT_KEYS = 32
MAX_LIST_ITEMS = MAX_OPPORTUNITIES + 1  # 1001: the unit's own opportunities cap (1000) must still fire at 1001
MAX_DEPTH = 32
MAX_KEY_LEN = 200  # raw length of a request key, checked before normalization
TOP_KEYS = frozenset({"as_of", "profile", "template", "opportunities", "strict"})
PROFILE_KEYS = frozenset({"name", "school"})
OPPORTUNITY_KEYS = frozenset({"id", "title", "fee", "contact_email", "contact_name", "deadline"})
STATUS = "awaiting_exact_draft_approval"
DEFAULT_CONTACT = "Admissions Team"
PLACEHOLDERS = ("name", "school", "opportunity", "contact", "fee", "deadline")

# Forbidden request keys: casefold, "-" -> "_", exact match, any depth.
# Precedence when several hit: SEND > SPEND > SUBMIT > NOCREDS.
_KEY_RULES = (
    ("SEND", frozenset({"send", "approve", "approved", "approval", "approval_token", "smtp",
                        "token", "email_send", "sender", "smtp_host", "smtp_port", "smtp_user"})),
    ("SPEND", frozenset({"pay", "waive_fee", "fee_action"})),
    ("SUBMIT", frozenset({"register", "submit", "attempt"})),
    ("NOCREDS", frozenset({"login", "password", "username", "credentials", "otp", "api_key",
                           "access_token", "refresh_token", "bearer", "pass", "passwd"})),
)

_FREE = frozenset({"free", "0", "0.0", "0.00", "usd 0", "$0", "no fee", "none"})
_UNKNOWN = frozenset({"", "n/a", "tbd", "unknown", "varies"})
_FEE_RE = re.compile(
    r"(?:(usd|eur|gbp|inr|rs|\$|\u20ac|\u00a3|\u20b9)\s?)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?"
    r"(?:\s?(usd|eur|gbp|inr))?", re.ASCII)
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})", re.ASCII)
_PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")


def _cap(value, token, limit):
    """Unit-level cap, checked BEFORE policy.clean_text: an over-cap str refuses
    as OVERSIZE:<schema field>, so the shared helper's own over-length code can
    never surface in this unit (limits passed to clean_text equal the caps)."""
    if isinstance(value, str) and len(value) > limit:
        raise ValueError("%s_REFUSED_OVERSIZE:%s" % (PREFIX, token))


def _clean(value, field, limit, **kw):
    return policy.clean_text(value, PREFIX, field, limit, **kw)


def _bad(name):
    raise ValueError("%s_REFUSED_BAD_TYPE:%s" % (PREFIX, name))


def _oversize_request():
    raise ValueError("%s_REFUSED_OVERSIZE:request" % PREFIX)


_SCAN_TYPES = (dict, list, tuple)


def _scan_keys(request):
    """Steps 2 and 3. Recursive over dict values and list/tuple items, under a
    budget that is checked BEFORE any container is read or descended into:
    at most MAX_CONTAINERS distinct containers (exact builtin dict/list/tuple only; a
    subclass anywhere refuses BAD_TYPE:request before it is read), MAX_DICT_KEYS keys per dict,
    MAX_LIST_ITEMS items per list/tuple and MAX_DEPTH levels (request = 0).
    Anything over refuses OVERSIZE:request, ahead of every content error.
    Step 2: forbidden keys (class precedence SEND > SPEND > SUBMIT > NOCREDS;
    within the winning class the alphabetically first MATCHED table key is the
    suffix; non-matching key text is never echoed). Step 3: a non-str dict key
    anywhere -> BAD_TYPE:key, only when no forbidden key was found."""
    hits = {}
    non_str = False
    if type(request) not in _SCAN_TYPES:
        _bad("request")
    seen = {id(request)}
    stack = [(request, 0)]  # only containers are pushed; the stack never exceeds MAX_CONTAINERS
    while stack:
        node, depth = stack.pop()
        if type(node) is dict:
            if len(node) > MAX_DICT_KEYS:
                _oversize_request()
            children = []
            for key, value in node.items():
                if type(key) is str:
                    if len(key) > MAX_KEY_LEN:
                        _oversize_request()  # raw cap, before any normalization
                    norm = key.casefold().replace("-", "_")
                    for rule, keys in _KEY_RULES:
                        if norm in keys:
                            hits.setdefault(rule, set()).add(norm)
                elif isinstance(key, str):
                    _bad("request")  # str subclass: its casefold/len may be overridden; refused untouched
                else:
                    non_str = True
                children.append(value)
        else:
            if len(node) > MAX_LIST_ITEMS:
                _oversize_request()
            children = node
        for child in children:
            if isinstance(child, (dict, list, tuple)) and type(child) not in _SCAN_TYPES:
                _bad("request")  # a subclass may lie about its size or iteration: refused unread
            if type(child) in _SCAN_TYPES and id(child) not in seen:
                if depth + 1 > MAX_DEPTH or len(seen) >= MAX_CONTAINERS:
                    _oversize_request()
                seen.add(id(child))
                stack.append((child, depth + 1))
    for rule, _keys in _KEY_RULES:
        if rule in hits:
            raise ValueError("%s_REFUSED_%s:%s" % (PREFIX, rule, sorted(hits[rule])[0]))
    if non_str:
        _bad("key")


def _valid_date(value):
    match = _DATE_RE.fullmatch(value)
    if not match:
        return False
    year, month, day = (int(g) for g in match.groups())
    if year < 1 or not 1 <= month <= 12 or day < 1:
        return False
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]
    return day <= days


def _classify_fee(fee):
    """Returns (kind, raw) with kind in free | unknown | draft."""
    if fee is None:
        return "unknown", None
    if isinstance(fee, bool):
        _bad("fee")
    if isinstance(fee, (int, float)):
        if fee != fee or fee in (float("inf"), float("-inf")) or fee < 0:
            _bad("fee")
        if fee == 0:
            return "free", None
        return "draft", str(fee)
    if not isinstance(fee, str):
        _bad("fee")
    raw = fee.strip()
    norm = raw.casefold()
    if norm in _FREE:
        return "free", None
    if norm in _UNKNOWN:
        return "unknown", None
    match = _FEE_RE.fullmatch(norm)
    if not match:
        _bad("fee")
    prefix, whole, frac, suffix = match.groups()
    if prefix and suffix:  # builder choice: one currency token only
        _bad("fee")
    amount = Decimal(whole.replace(",", "") + (frac or ""))
    if amount == 0:
        return "free", None
    return "draft", raw


def _recipient(value):
    """Returns (recipient, needs_recipient, recipient_invalid)."""
    if value is None:
        return None, True, False
    if not isinstance(value, str):
        _bad("contact_email")
    text = value.strip()
    if not text:
        return None, True, False
    if _EMAIL_RE.fullmatch(text) and not any(unicodedata.category(c) in ('Cc', 'Zl', 'Zp') for c in value):
        return text, False, False
    return None, True, True


def _fill(template, values):
    return _PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], template)


def run(request):
    # 1. request is a dict
    if not isinstance(request, dict):
        _bad("request")
    # 2-3. forbidden-key scan, then non-str keys (both before any other check)
    _scan_keys(request)
    # 4. unknown-key allowlists: top level, then profile, then each opportunity in list order
    if set(request) - TOP_KEYS:
        raise ValueError("%s_REFUSED_UNKNOWN:request" % PREFIX)
    profile = request.get("profile")
    if isinstance(profile, dict) and set(profile) - PROFILE_KEYS:
        raise ValueError("%s_REFUSED_UNKNOWN:profile" % PREFIX)
    opportunities = request.get("opportunities")
    if isinstance(opportunities, list):
        for item in opportunities:
            if isinstance(item, dict) and set(item) - OPPORTUNITY_KEYS:
                raise ValueError("%s_REFUSED_UNKNOWN:opportunities" % PREFIX)
    # 5. top-level types
    as_of = request.get("as_of")
    if not isinstance(as_of, str):
        _bad("as_of")
    if not isinstance(profile, dict):
        _bad("profile")
    template = request.get("template")
    if not isinstance(template, str):
        _bad("template")
    if not isinstance(opportunities, list):
        _bad("opportunities")
    if not opportunities:
        raise ValueError("%s_REFUSED_EMPTY" % PREFIX)
    strict = request.get("strict", False)
    if not isinstance(strict, bool):
        _bad("strict")
    # 6. top-level caps: opportunities, template, as_of, profile values (sorted key order)
    if len(opportunities) > MAX_OPPORTUNITIES:
        raise ValueError("%s_REFUSED_OVERSIZE:opportunities" % PREFIX)
    _cap(template, "template", MAX_TEMPLATE)
    _cap(as_of, "as_of", 64)
    for key in sorted(profile):
        _cap(profile[key], "profile", 200)
    # ISO shape of as_of: after the caps, before clean_text
    if not _valid_date(as_of):
        _bad("as_of")
    # 7. clean_text on as_of, profile name/school, template
    as_of = _clean(as_of, "as_of", 64)
    prof = {}
    for key in ("name", "school"):
        if profile.get(key) is not None:
            prof[key] = _clean(profile[key], key, 200, allow_blank=True)
    template = _clean(template, "template", MAX_TEMPLATE, allow_ws=True)
    # 8. per opportunity in list order: types, caps, clean_text; duplicate ids after the pass
    rows = []
    for item in opportunities:
        if not isinstance(item, dict):
            _bad("opportunities")
        for field in ("id", "title"):
            if not isinstance(item.get(field), str):
                _bad(field)
        for field in ("contact_name", "deadline"):
            if item.get(field) is not None and not isinstance(item.get(field), str):
                _bad(field)
        recipient, needs, invalid = _recipient(item.get("contact_email"))
        _cap(item["id"], "id", 128)
        _cap(item["title"], "title", 200)
        _cap(item.get("contact_name"), "contact_name", 200)
        _cap(item.get("deadline"), "deadline", 100)
        oid = _clean(item["id"], "id", 128)
        title = _clean(item["title"], "title", 200)
        contact_name = item.get("contact_name")
        if contact_name is not None:
            contact_name = _clean(contact_name, "contact_name", 200, allow_blank=True)
        deadline = item.get("deadline")
        if deadline is not None:
            deadline = _clean(deadline, "deadline", 100, allow_blank=True)
        rows.append({"id": oid, "title": title, "fee": item.get("fee"), "contact_name": contact_name,
                     "deadline": deadline, "recipient": recipient, "needs": needs,
                     "invalid": invalid})
    ids = set()
    for row in rows:
        if row["id"] in ids:
            _bad("opportunities")
        ids.add(row["id"])
    # 9. fee classification, in list order
    skipped, unknown, drafting = [], [], []
    for row in rows:
        kind, raw = _classify_fee(row["fee"])
        if kind == "free":
            skipped.append(row["id"])
        elif kind == "unknown":
            unknown.append(row["id"])
        else:
            row["fee_raw"] = raw
            drafting.append(row)
    # 10. placeholders (UNFILLED)
    used = set()
    for found in _PLACEHOLDER_RE.findall(template):
        if found not in PLACEHOLDERS:
            raise ValueError("%s_REFUSED_UNFILLED:template" % PREFIX)  # untrusted text, not echoed
        used.add(found)
    for key in ("name", "school"):
        if key in used and not (prof.get(key) or "").strip():
            raise ValueError("%s_REFUSED_UNFILLED:%s" % (PREFIX, key))
    bodies = {}
    for row in drafting:
        if "deadline" in used and not (row["deadline"] or "").strip():
            raise ValueError("%s_REFUSED_UNFILLED:deadline" % PREFIX)
        values = {"name": prof.get("name", ""), "school": prof.get("school", ""),
                  "opportunity": row["title"], "fee": row["fee_raw"],
                  "deadline": row["deadline"] or "",
                  "contact": (row["contact_name"] or "").strip() or DEFAULT_CONTACT}
        body = _fill(template, values)
        if len(body) > MAX_BODY:
            raise ValueError("%s_REFUSED_OVERSIZE:template" % PREFIX)
        bodies[row["id"]] = body
    # 11. recipient check, only when strict: first drafted opportunity in list order
    if strict:
        for row in drafting:
            if row["needs"]:
                raise ValueError("%s_REFUSED_NORECIPIENT:contact_email" % PREFIX)
    drafts = []
    for row in drafting:
        subject = "Fee waiver request: " + row["title"]
        body = bodies[row["id"]]
        framed = json.dumps([row["recipient"] or "", subject, body], ensure_ascii=False,
                            separators=(",", ":")).encode("utf-8")
        drafts.append({"draft_id": hashlib.sha256(framed).hexdigest()[:16],
                       "opportunity_id": row["id"], "recipient": row["recipient"],
                       "subject": subject, "body": body, "status": STATUS,
                       "needs_recipient": row["needs"], "recipient_invalid": row["invalid"]})
    return {"drafts": drafts, "skipped_no_fee": sorted(skipped), "fee_unknown": sorted(unknown),
            "scope": policy.scope(
                ["fee-waiver draft text with recipient and subject from a supplied template",
                 "fee classification into free, unknown and positive",
                 "content-hash draft ids"],
                ["sending email", "registering", "submitting", "any fee action or payment",
                 "login or credentials", "recording approval",
                 "any claim that a waiver will be granted"],
                "supplied request only (no network)", as_of)}
