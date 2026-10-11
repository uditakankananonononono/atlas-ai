"""c37.patents (V2): claim DRAFTS from a caller-supplied invention record.

Stdlib plus the real c30 policy helpers. Offline, deterministic, no effects.
No filing path. `invention.owner == "self"` is a caller assertion, never
verified. Prior-art records are unverified caller data, passed through
untouched. No overlap, novelty or patentability computation here.
"""
import math
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit

from app.modules.c30 import policy

PREFIX = "INTEL"
DRAFT = "DRAFT NOT FOR FILING"
UNVERIFIED = "caller_supplied, unverified"

TOP_KEYS = ("as_of", "invention", "prior_art", "novelty_input")
INV_KEYS = ("id", "owner", "title", "summary", "components", "novel_features")
PA_KEYS = ("id", "title", "url")
NOV_KEYS = ("source", "value")

SEND = frozenset({"send", "approve", "approved", "approval", "approval_token", "smtp", "token",
                  "email_send", "sender", "smtp_host", "smtp_port", "smtp_user"})
SPEND = frozenset({"pay", "purchase", "spend", "buy", "checkout", "card_number"})
EFFECT = frozenset({"file", "submit", "uspto_submit", "epo_submit", "grant"})
NOCREDS = frozenset({"login", "password", "username", "credentials", "otp", "api_key",
                     "access_token", "refresh_token", "bearer", "pass", "passwd"})
CLASSES = (("SEND", SEND), ("SPEND", SPEND), ("FILE", EFFECT), ("NOCREDS", NOCREDS))

TEXT_CAP = 500
LIST_CAP = 30
PA_CAP = 200
URL_CAP = 2000


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, (":" + field) if field else ""))


def _norm(key):
    return key.casefold().replace("-", "_")


def _preflight(request):
    # Iterative count-first shape admission. No global key set or recursion.
    stack = [(request, "request", 0, False)]
    active = []
    nodes = 0
    key_cap = 200
    list_caps = {"components": LIST_CAP, "novel_features": LIST_CAP, "prior_art": PA_CAP}
    while stack:
        node, field, depth, exiting = stack.pop()
        if exiting:
            active.remove(id(node))
            continue
        nodes += 1 + (len(node) if type(node) is dict else 0)
        if nodes > 10000 or depth > 32:
            _refuse("OVERSIZE", field)
        if type(node) not in (dict, list):
            if isinstance(node, (dict, list)):
                _refuse("BAD_TYPE", field)
            continue
        identity = id(node)
        if identity in active:
            _refuse("BAD_TYPE", "request")
        # Raw container count before child tuple/list comprehension allocation.
        if nodes + len(node) > 10000:
            _refuse("OVERSIZE", field)
        if type(node) is dict:
            if field not in ("request", "invention", "prior_art", "novelty_input") and len(node) > 200:
                _refuse("OVERSIZE", field)
            for key in node:
                if type(key) is not str:
                    _refuse("BAD_TYPE", "key")
                if len(key) > key_cap:
                    _refuse("OVERSIZE", "key")
            children = [(value, key if key in ("invention", "prior_art", "novelty_input", "components", "novel_features") else field)
                        for key, value in node.items()]
        else:
            if len(node) > list_caps.get(field, 200):
                _refuse("OVERSIZE", field)
            children = [(value, field) for value in node]
        active.append(identity)
        stack.append((node, field, depth, True))
        for value, child_field in reversed(children):
            stack.append((value, child_field, depth + 1, False))


def _collect_keys(node, found):
    if type(node) is dict:
        for k, v in node.items():
            if type(k) is str:
                found.add(_norm(k))
            _collect_keys(v, found)
    elif type(node) is list:
        for v in node:
            _collect_keys(v, found)


def _scan_forbidden(request):
    found = set()
    _collect_keys(request, found)
    for reason, table in CLASSES:
        hits = sorted(found & table)
        if hits:
            _refuse(reason, hits[0])


def _check_key_types(node):
    if type(node) is dict:
        for k, v in node.items():
            if not type(k) is str:
                _refuse("BAD_TYPE", "key")
            _check_key_types(v)
    elif type(node) is list:
        for v in node:
            _check_key_types(v)


def _check_unknown(request):
    if any(k not in TOP_KEYS for k in request):
        _refuse("UNKNOWN", "request")
    inv = request.get("invention")
    if type(inv) is dict and any(k not in INV_KEYS for k in inv):
        _refuse("UNKNOWN", "invention")
    pa = request.get("prior_art")
    if type(pa) is list:
        for e in pa:
            if type(e) is dict and any(k not in PA_KEYS for k in e):
                _refuse("UNKNOWN", "prior_art")
    nov = request.get("novelty_input")
    if type(nov) is dict and any(k not in NOV_KEYS for k in nov):
        _refuse("UNKNOWN", "novelty_input")


def _valid_date(value):
    if not type(value) is str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _check_types_and_empties(request, inv):
    if not _valid_date(request.get("as_of")):
        _refuse("BAD_TYPE", "as_of")
    if not type(inv) is dict:
        _refuse("BAD_TYPE", "invention")
    for f in ("components", "novel_features"):
        if not type(inv.get(f)) is list:
            _refuse("BAD_TYPE", f)
    pa = request.get("prior_art")
    if pa is not None and not type(pa) is list:
        _refuse("BAD_TYPE", "prior_art")
    for f in ("components", "novel_features"):
        if not inv[f]:
            _refuse("EMPTY", f)
    if not pa:
        _refuse("PRIORART_MISSING", "prior_art")


def _is_str(v):
    return type(v) is str


def _check_caps(request, inv):
    for f in ("id", "title", "summary"):
        if _is_str(inv.get(f)) and len(inv[f]) > TEXT_CAP:
            _refuse("OVERSIZE", f)
    for f in ("components", "novel_features"):
        items = inv[f]
        if len(items) > LIST_CAP or any(_is_str(i) and len(i) > TEXT_CAP for i in items):
            _refuse("OVERSIZE", f)
    pa = request["prior_art"]
    if len(pa) > PA_CAP:
        _refuse("OVERSIZE", "prior_art")
    for e in pa:
        if not type(e) is dict:
            continue
        for leaf, cap in (("id", TEXT_CAP), ("title", TEXT_CAP), ("url", URL_CAP)):
            if _is_str(e.get(leaf)) and len(e[leaf]) > cap:
                _refuse("OVERSIZE", leaf)


def _unicode_text(value, field):
    if not type(value) is str:
        _refuse("BAD_TYPE", field)
    if not value.strip() or any(unicodedata.category(c) in {"Cc", "Cf", "Zl", "Zp"} for c in value):
        _refuse("BAD_TYPE", field)
    return value


def _clean_item(value, field):
    _unicode_text(value, field)
    try:
        return policy.clean_text(value, PREFIX, field, TEXT_CAP)
    except ValueError:
        _refuse("BAD_TYPE", field)


def _clean_url(value):
    if not _is_str(value) or not value.startswith("https://"):
        _refuse("BAD_TYPE", "prior_art")
    if any(c.isspace() or unicodedata.category(c) in {"Cc", "Cf", "Zl", "Zp", "Zs"} for c in value):
        _refuse("BAD_TYPE", "prior_art")
    try:
        host = urlsplit(value).hostname
    except ValueError:
        host = None
    if not host:
        _refuse("BAD_TYPE", "prior_art")
    return value


def _clean_prior_art(entries):
    seen = set()
    out = []
    for e in entries:
        if not type(e) is dict:
            _refuse("BAD_TYPE", "prior_art")
        pid = _clean_item(e.get("id"), "prior_art")
        title = _clean_item(e.get("title"), "prior_art")
        url = _clean_url(e.get("url"))
        if pid in seen:
            _refuse("BAD_TYPE", "prior_art")
        seen.add(pid)
        out.append({"id": pid, "title": title, "url": url})
    return out


def _clean_novelty(nov):
    if nov is None:
        return None
    if not type(nov) is dict or type(nov.get("source")) is not str or nov.get("source") != "c32.ideate":
        _refuse("BAD_TYPE", "novelty_input")
    v = nov.get("value")
    if type(v) not in (int, float) or not 0 <= v <= 1 or not math.isfinite(v):
        _refuse("BAD_TYPE", "novelty_input")
    return {"source": "c32.ideate", "value": round(v, 6), "label": UNVERIFIED}


def _claims(title, components, features):
    if len(components) == 1:
        body = components[0]
    else:
        body = "; ".join(components[:-1]) + "; and " + components[-1]
    texts = ["1. A %s comprising: %s." % (title, body)]
    for k, feat in enumerate(features, start=2):
        texts.append("%d. The %s of claim 1, wherein %s." % (k, title, feat))
    return [{"number": n, "text": t, "label": DRAFT} for n, t in enumerate(texts, start=1)]


def run(request):
    if not type(request) is dict:
        _refuse("BAD_TYPE", "request")
    _preflight(request)
    _scan_forbidden(request)
    _check_key_types(request)
    _check_unknown(request)
    inv = request.get("invention")
    _check_types_and_empties(request, inv)
    _check_caps(request, inv)
    _clean_item(inv.get("id"), "id")
    if inv.get("owner") != "self" or not _is_str(inv.get("owner")):
        _refuse("NOT_OWNER", "owner")
    title = _clean_item(inv.get("title"), "title")
    _clean_item(inv.get("summary"), "summary")
    components = [_clean_item(c, "components") for c in inv["components"]]
    features = [_clean_item(f, "novel_features") for f in inv["novel_features"]]
    prior = _clean_prior_art(request["prior_art"])
    echo = _clean_novelty(request.get("novelty_input"))
    claims = _claims(title, components, features)
    return {
        "claims": claims,
        "claim_count": len(claims),
        "draft_label": DRAFT,
        "prior_art_passthrough": prior,
        "novelty_input_echo": echo,
        "owner_assertion": UNVERIFIED,
        "scope": policy.scope(
            ["claim text drafts from supplied components and features",
             "pass-through of supplied prior-art records"],
            ["prior-art comparison or novelty scoring", "ownership or inventorship verification",
             "legal advice", "prior-art search", "filing"],
            "caller-supplied invention and prior-art records, unverified", request["as_of"]),
    }
