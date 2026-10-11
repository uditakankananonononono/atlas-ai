"""c37.news_create (V8): rank SUPPLIED items by SUPPLIED interests, emit templated briefs and tickets.

Stdlib plus the real c30 policy helpers. Offline, deterministic, no effects: nothing is fetched,
sent, built or published here. Tickets are data that propose work for review; the score is a toy
keyword-and-recency formula, not interestingness or novelty detection.
"""
import datetime
import re
import unicodedata
from urllib.parse import urlsplit

from app.modules.c30 import policy

PREFIX = "INTEL"
TOP_KEYS = ("as_of", "interests", "top_n", "items")
ITEM_KEYS = ("id", "kind", "title", "summary", "url", "published", "tags")
KINDS = ("news", "paper", "tech")

SEND = frozenset({"send", "approve", "approved", "approval", "approval_token", "smtp", "token",
                  "email_send", "sender", "smtp_host", "smtp_port", "smtp_user"})
SPEND = frozenset({"pay", "purchase", "spend", "buy", "checkout", "card_number"})
EFFECT = frozenset({"fetch", "crawl", "scrape", "download", "publish", "post", "build", "deploy"})
NOCREDS = frozenset({"login", "password", "username", "credentials", "otp", "api_key", "access_token",
                     "refresh_token", "bearer", "pass", "passwd"})
CLASSES = (("SEND", SEND), ("SPEND", SPEND), ("EFFECT", EFFECT), ("NOCREDS", NOCREDS))

MAX_ITEMS = 5000
MAX_INTERESTS = 50
MAX_TAGS = 20
MAX_ID = 128
MAX_TITLE = 300
MAX_SUMMARY = 4000
MAX_URL = 2000
MAX_WORD = 64
MAX_DATE = 10                       # length of YYYY-MM-DD
MAX_KIND = max(len(k) for k in KINDS)   # longest enum literal (paper)
MAX_TOP_N = 20
# blanket fences, applied before any per-character work
MAX_CONTAINERS = 10010   # 1 top + items + interests + 5000 items + 5000 tag lists + 7 spare
MAX_KEYS = 32
MAX_OTHER_LIST = 64
MAX_KEY_CHARS = 64
MAX_RAW_STR = 10000
MAX_DEPTH = 8

QUESTIONS = (
    "What is new in this item, going only by the supplied summary?",
    "What would it enable if it holds up?",
    "What are the risks or reasons it may not hold up?",
    "What would a first prototype test?",
    "What is unknown from the supplied summary?",
)
_LIST_CAPS = {"items": MAX_ITEMS, "interests": MAX_INTERESTS, "tags": MAX_TAGS}
_URL_ASCII_BAD = re.compile(r"[\x00-\x20\x7f]")
# Zl, Zp and Zs are whitespace, so str.isspace covers them; Cc and Cf are named here
_URL_BAD_CATS = frozenset({"Cc", "Cf"})
_WORDS = re.compile(r"[^\W_]+")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, (":" + field) if field else ""))


def _admit(value, field, role, depth, stack, count):
    t = type(value)
    if t is str:
        if len(value) > MAX_RAW_STR:
            _refuse("OVERSIZE", field)
    elif t is dict or t is list:
        count[0] += 1
        if depth > MAX_DEPTH or count[0] > MAX_CONTAINERS:
            _refuse("OVERSIZE", field)
        stack.append((value, field, role, depth))
    elif isinstance(value, (dict, list)):
        _refuse("BAD_TYPE", field)


def _preflight(request):
    """Cardinality first: containers only, no per-character work, children admitted by count."""
    stack = [(request, "request", "top", 0)]
    count = [1]
    while stack:
        node, field, role, depth = stack.pop()
        if type(node) is dict:
            if len(node) > MAX_KEYS:
                _refuse("OVERSIZE", field)
            for k, v in node.items():
                if type(k) is str and len(k) > MAX_KEY_CHARS:
                    _refuse("OVERSIZE", field)
                if role == "top" and k == "items":
                    _admit(v, "items", "items", depth + 1, stack, count)
                elif role == "top" and k == "interests":
                    _admit(v, "interests", "interests", depth + 1, stack, count)
                elif role == "item" and k == "tags":
                    _admit(v, "tags", "tags", depth + 1, stack, count)
                else:
                    _admit(v, field, "other", depth + 1, stack, count)
        else:
            if len(node) > _LIST_CAPS.get(role, MAX_OTHER_LIST):
                _refuse("OVERSIZE", field)
            for v in node:
                if role == "items":
                    if type(v) is dict:
                        count[0] += 1
                        if depth + 1 > MAX_DEPTH or count[0] > MAX_CONTAINERS:
                            _refuse("OVERSIZE", field)
                        stack.append((v, "items", "item", depth + 1))
                    else:
                        _admit(v, "items", "other", depth + 1, stack, count)
                else:
                    _admit(v, field, "other", depth + 1, stack, count)


def _norm(key):
    return key.casefold().replace("-", "_")


def _walk(node, fn):
    stack = [node]
    while stack:
        n = stack.pop()
        if type(n) is dict:
            for k, v in n.items():
                fn(k)
                stack.append(v)
        elif type(n) is list:
            stack.extend(n)


def _scan_forbidden(request):
    found = set()

    def grab(k):
        if type(k) is str:
            found.add(_norm(k))
    _walk(request, grab)
    for reason, table in CLASSES:
        hits = sorted(found & table)
        if hits:
            _refuse(reason, hits[0])


def _check_key_types(request):
    def chk(k):
        if type(k) is not str:
            _refuse("BAD_TYPE", "key")
    _walk(request, chk)


def _check_unknown(request):
    if any(k not in TOP_KEYS for k in request):
        _refuse("UNKNOWN", "request")
    items = request.get("items")
    if type(items) is list:
        for it in items:
            if type(it) is dict and any(k not in ITEM_KEYS for k in it):
                _refuse("UNKNOWN", "items")


def _valid_date(value):
    if type(value) is not str or len(value) != 10 or not _DATE.fullmatch(value):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _top_types(request):
    raw = request.get("as_of")
    if type(raw) is str and len(raw) > MAX_DATE:
        _refuse("OVERSIZE", "as_of")
    as_of = _valid_date(raw)
    if as_of is None:
        _refuse("BAD_TYPE", "as_of")
    n = request.get("top_n")
    if type(n) is not int or n < 1:
        _refuse("BAD_TYPE", "top_n")
    if n > MAX_TOP_N:
        _refuse("OVERSIZE", "top_n")
    for f in ("interests", "items"):
        if type(request.get(f)) is not list:
            _refuse("BAD_TYPE", f)
        if not request[f]:
            _refuse("EMPTY", f)
    return as_of, n


def _check_caps(request):
    for s in request["interests"]:
        if type(s) is str and len(s) > MAX_WORD:
            _refuse("OVERSIZE", "interests")
    for it in request["items"]:
        if type(it) is not dict:
            continue
        for f, cap in (("id", MAX_ID), ("kind", MAX_KIND), ("title", MAX_TITLE), ("summary", MAX_SUMMARY),
                       ("url", MAX_URL), ("published", MAX_DATE)):
            v = it.get(f)
            if type(v) is str and len(v) > cap:
                _refuse("OVERSIZE", f)
        tags = it.get("tags")
        if type(tags) is list:   # the 20-tag count cap is enforced by the preflight
            for s in tags:
                if type(s) is str and len(s) > MAX_WORD:
                    _refuse("OVERSIZE", "tags")


def _text(value, name, limit, allow_ws=False):
    return policy.clean_text(value, PREFIX, name, limit, allow_ws=allow_ws)


def _validate_item(it, seen):
    if type(it) is not dict:
        _refuse("BAD_TYPE", "items")
    iid = _text(it.get("id"), "id", MAX_ID)
    kind = it.get("kind")
    if type(kind) is not str:
        _refuse("BAD_TYPE", "kind")
    if kind not in KINDS:
        _refuse("UNKNOWN", "kind")
    title = _text(it.get("title"), "title", MAX_TITLE)
    summary = _text(it.get("summary"), "summary", MAX_SUMMARY, allow_ws=True)
    url = it.get("url")
    if type(url) is not str:
        _refuse("BAD_TYPE", "url")
    published = _valid_date(it.get("published"))
    if published is None:
        _refuse("BAD_TYPE", "published")
    tags = it.get("tags")
    if type(tags) is not list:
        _refuse("BAD_TYPE", "tags")
    tags = [_text(t, "tags", MAX_WORD) for t in tags]
    if iid in seen:
        _refuse("BAD_TYPE", "items")
    seen.add(iid)
    return {"id": iid, "kind": kind, "title": title, "summary": summary, "url": url,
            "published": published, "published_text": it["published"], "tags": tags}


def _url_ok(url):
    if not url[:8].isascii() or url[:8].lower() != "https://":
        return False
    if url.isascii():
        if _URL_ASCII_BAD.search(url):
            return False
    elif any(c.isspace() or unicodedata.category(c) in _URL_BAD_CATS for c in url):
        return False
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    return bool(host) and "@" not in parts.netloc


def _interest_keys(interests):
    keys = {}
    for s in interests:
        k = s.strip().casefold()
        keys[k] = tuple(_WORDS.findall(k))
    return keys


def _overlap(it, keys):
    hay = " " + " ".join(_WORDS.findall((it["title"] + " " + it["summary"]).casefold())) + " "
    tags = {t.strip().casefold() for t in it["tags"]}
    matched = []
    for k, words in keys.items():
        if k in tags or (words and " " + " ".join(words) + " " in hay):
            matched.append(k)
    return sorted(matched)


def run(request):
    if type(request) is not dict:
        _refuse("BAD_TYPE", "request")
    _preflight(request)
    _scan_forbidden(request)
    _check_key_types(request)
    _check_unknown(request)
    as_of, top_n = _top_types(request)
    _check_caps(request)
    interests = [_text(s, "interests", MAX_WORD) for s in request["interests"]]
    seen = set()
    items = [_validate_item(it, seen) for it in request["items"]]
    keys = _interest_keys(interests)

    url_invalid = future = 0
    scored = []
    for it in items:
        if not _url_ok(it["url"]):
            url_invalid += 1
            continue
        if it["published"] > as_of:
            future += 1
            continue
        matched = _overlap(it, keys)
        age = (as_of - it["published"]).days
        recency = max(0, 30 - age)
        scored.append((-(10 * len(matched) + recency), it["id"], it, matched, age, recency))
    scored.sort(key=lambda r: (r[0], r[1]))
    ranked, briefs, tickets = [], [], []
    for neg, iid, it, matched, age, recency in scored:
        ranked.append({"id": iid, "kind": it["kind"], "title": it["title"], "source_url": it["url"],
                       "published": it["published_text"], "overlap": len(matched),
                       "matched_interests": matched, "age_days": age, "recency": recency, "score": -neg})
        if matched and len(briefs) < top_n:
            briefs.append({"item_id": iid, "title": it["title"], "kind": it["kind"], "source_url": it["url"],
                           "supplied_summary": it["summary"], "questions": list(QUESTIONS),
                           "status": "TO_RESEARCH"})
            tickets.append({"ticket_id": "V8-" + iid, "title": "Explore: " + it["title"],
                            "source_item_id": iid, "source_url": it["url"], "status": "proposed",
                            "needs_her_review": True})
    return {
        "ranked": ranked, "briefs": briefs, "tickets": tickets,
        "counts": {"supplied": len(items), "ranked": len(ranked), "dropped_url_invalid": url_invalid,
                   "dropped_future_date": future},
        "scope": policy.scope(
            ["integer keyword-overlap plus recency ranking of supplied items",
             "templated research briefs and proposed tickets for the top supplied matches"],
            ["interestingness or novelty detection", "fetching any feed, site or stream",
             "verification of supplied summaries", "creating or building anything"],
            "caller-supplied items and interest terms, unfetched and unverified", request["as_of"]),
    }
