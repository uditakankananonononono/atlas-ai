"""S5.1 / c36.blueprint - niche-company blueprint composer.

Source excerpt (verbatim, spec text): "Autonomously build whole digital
companies with autonomous worker ai bots across thousands of niches and lead
the industries".

A deterministic composer over SUPPLIED niche fields. No LLM, no network, no
funnel, no scores. Builds B1 regulated gating, B2 offer, B3 pricing, B4
worker-role graph edges, B6 fixed KPI names with null targets and B7 a fixed
three-file scaffold. Stdlib only.
"""
from __future__ import annotations

import math
import re
import unicodedata

from app.modules.c30 import policy

PREFIX = "VENT"
TOP_KEYS = frozenset({"as_of", "niches"})
NICHE_KEYS = frozenset({"id", "name", "audience", "problem", "price_points", "currency",
                        "regulated_flags", "channels", "worker_roles"})
SEND = frozenset({"send", "approve", "approved", "approval", "approval_token", "smtp", "token",
                  "email_send", "sender", "smtp_host", "smtp_port", "smtp_user"})
SPEND = frozenset({"pay", "purchase", "spend", "buy", "checkout", "card_number"})
NOCREDS = frozenset({"login", "password", "username", "credentials", "otp", "api_key",
                     "access_token", "refresh_token", "bearer", "pass", "passwd"})
EFFECT = frozenset({"register", "register_company", "incorporate", "launch", "deploy"})
_CLASSES = (("SEND", SEND), ("SPEND", SPEND), ("EFFECT", EFFECT), ("NOCREDS", NOCREDS))

MAX_NICHES = 2000
MAX_TEXT = 200
MAX_PRICES = 20
MAX_CHANNELS = 20
MAX_ROLES = 12
MAX_FLAGS = 10
MAX_FLAG_LEN = 50

EDGES = (("researcher", "analyst"), ("analyst", "writer"), ("writer", "critic"),
         ("critic", "auditor"), ("builder", "critic"))
KPI_NAMES = ("visitors", "trial_starts", "purchases", "retention_rate")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")  # used with fullmatch; ASCII digits only
_CUR = re.compile(r"[A-Z]{3}")  # used with fullmatch; ASCII A-Z only


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _norm(key):
    return key.casefold().replace("-", "_")


def _scan(node, hits):
    if type(node) is dict:
        for k, v in node.items():
            if type(k) is str:
                nk = _norm(k)
                for rank, (name, table) in enumerate(_CLASSES):
                    if nk in table:
                        hits.append((rank, nk, name))
            _scan(v, hits)
    elif type(node) in (list, tuple):
        for item in node:
            _scan(item, hits)


def _check_keys(node):
    """Non-str keys anywhere in the dict levels the schema reads."""
    if type(node) is dict:
        for k, v in node.items():
            if not type(k) is str:
                _refuse("BAD_TYPE", "key")
            _check_keys(v)
    elif type(node) in (list, tuple):
        for item in node:
            _check_keys(item)


def _is_num(v):
    if type(v) not in (int, float):
        return False
    try:
        return math.isfinite(v) and v > 0
    except OverflowError:
        return False


def _text(value, field, cap, allow_blank=False):
    if type(value) is not str:
        _refuse("BAD_TYPE", field)
    if len(value) > cap:
        _refuse("OVERSIZE", field)
    if any(unicodedata.category(c) in {"Cc", "Cf", "Zl", "Zp"} for c in value):
        _refuse("CONTROL_CHARS", field)
    return policy.clean_text(value, PREFIX, field, cap, allow_blank=allow_blank)


def _preflight(request):
    """Count known schema lists before traversal, then bounded raw-key scan."""
    niches = request.get("niches")
    if type(niches) is list:
        if len(niches) > MAX_NICHES:
            _refuse("OVERSIZE", "niches")
        for n in niches:
            if type(n) is dict:
                for field, cap in (("price_points",20),("channels",20),("worker_roles",12),("regulated_flags",10)):
                    value=n.get(field)
                    if type(value) is list and len(value)>cap:
                        _refuse("OVERSIZE",field)
    stack=[(request,0,False)]
    active=set()
    nodes=0
    while stack:
        node,depth,leaving=stack.pop()
        if leaving:
            active.remove(id(node));continue
        if type(node) in (dict,list,tuple):
            nodes+=1
        if nodes>10000 or depth>32:
            _refuse("OVERSIZE","request")
        if type(node) not in (dict,list,tuple):
            continue
        if id(node) in active:
            _refuse("BAD_TYPE","request")
        active.add(id(node));stack.append((node,depth,True))
        if type(node) is dict:
            for key,value in reversed(list(node.items())):
                if type(key) is str:
                    if len(key)>200:_refuse("OVERSIZE","key")
                    if any(unicodedata.category(c) in {"Cc","Cf","Zl","Zp"} for c in key):
                        _refuse("CONTROL_CHARS","key")
                stack.append((value,depth+1,False))
        else:
            stack.extend((v,depth+1,False) for v in reversed(node))


def _caps(niches):
    if len(niches) > MAX_NICHES:
        _refuse("OVERSIZE", "niches")
    for n in niches:
        if not type(n) is dict:
            continue
        for f in ("id", "name", "audience", "problem"):
            v = n.get(f)
            if type(v) is str and len(v) > MAX_TEXT:
                _refuse("OVERSIZE", f)
        for f, cap in (("price_points", MAX_PRICES), ("channels", MAX_CHANNELS),
                       ("worker_roles", MAX_ROLES), ("regulated_flags", MAX_FLAGS)):
            v = n.get(f)
            if type(v) is list and len(v) > cap:
                _refuse("OVERSIZE", f)
        for field in ("channels","worker_roles"):
            values=n.get(field)
            if type(values) is list:
                for value in values:
                    if type(value) is str and len(value)>200:
                        _refuse("OVERSIZE",field)
        currency=n.get("currency")
        if type(currency) is str and len(currency)>3:
            _refuse("OVERSIZE","currency")
        flags = n.get("regulated_flags")
        if type(flags) is list:
            for x in flags:
                if type(x) is str and len(x) > MAX_FLAG_LEN:
                    _refuse("OVERSIZE", "regulated_flags")


def _text_list(value, field, limit=MAX_TEXT):
    if type(value) is not list:
        _refuse("BAD_TYPE", field)
    return [_text(x, field, limit) for x in value]


def _validate_niche(n):
    if not type(n) is dict:
        _refuse("BAD_TYPE", "niches")
    out = {f: _text(n.get(f), f, MAX_TEXT)
           for f in ("id", "name", "audience", "problem")}
    prices = n.get("price_points", [])
    if type(prices) is not list or not all(_is_num(p) for p in prices):
        _refuse("BAD_TYPE", "price_points")
    currency = n.get("currency")
    if currency is not None and type(currency) is not str:
        _refuse("BAD_TYPE", "currency")
    if currency is not None:
        currency = _text(currency, "currency", 3, allow_blank=True)
    if prices and currency is not None and not _CUR.fullmatch(currency):
        _refuse("BAD_TYPE", "currency")
    out["price_points"] = [round(p, 6) if type(p) is float else p for p in prices]
    out["currency"] = currency if prices else None
    out["channels"] = _text_list(n.get("channels", []), "channels")
    out["worker_roles"] = _text_list(n.get("worker_roles", []), "worker_roles")
    flags = n.get("regulated_flags", [])
    out["regulated_flags"] = _text_list(flags, "regulated_flags", MAX_FLAG_LEN)
    return out


def _graph(roles):
    nodes = sorted(set(roles))
    edges = [{"from": a, "to": b} for a, b in sorted(EDGES) if a in nodes and b in nodes]
    touched = {e["from"] for e in edges} | {e["to"] for e in edges}
    return {"nodes": nodes, "edges": edges, "isolated": [r for r in nodes if r not in touched]}


def _blueprint(n):
    offer = "%s: %s for %s" % (n["name"], n["problem"], n["audience"])
    if n["price_points"]:
        pricing = {"status": "priced", "price_points": n["price_points"], "currency": n["currency"]}
    else:
        pricing = {"status": "pricing_missing"}
    graph = _graph(n["worker_roles"])
    plan = "# Plan\n\nWorker roles: %s\n\nEdges:\n%s" % (
        ", ".join(graph["nodes"]) or "none supplied",
        "".join("- %s -> %s\n" % (e["from"], e["to"]) for e in graph["edges"]) or "- none\n")
    return {"id": n["id"], "offer": offer, "pricing": pricing, "worker_graph": graph,
            "kpis": [{"name": k, "target": None} for k in KPI_NAMES],
            "scaffold": {"README.md": "# %s\n\n%s\n" % (n["name"], offer),
                         "plan.md": plan, "kpis.csv": "kpi,target\n"}}


def run(request):
    """Compose blueprints over supplied niches; refusals raise ValueError."""
    if type(request) is not dict:
        _refuse("BAD_TYPE", "request")
    _preflight(request)
    raw_niches=request.get("niches")
    if type(raw_niches) is list:
        _caps(raw_niches)
    raw_as_of=request.get("as_of")
    if type(raw_as_of) is str and len(raw_as_of)>10:
        _refuse("OVERSIZE","as_of")
    hits = []
    _scan(request, hits)
    if hits:
        rank, key, name = min(hits, key=lambda h: (h[0], h[1]))
        _refuse(name, key)
    _check_keys(request)
    if set(request) - TOP_KEYS:
        _refuse("UNKNOWN", "request")
    niches = request.get("niches")
    for n in (niches if type(niches) is list else []):
        if type(n) is dict and set(n) - NICHE_KEYS:
            _refuse("UNKNOWN", "niches")
    as_of = request.get("as_of")
    if type(as_of) is str and len(as_of)>10:
        _refuse("OVERSIZE","as_of")
    if type(as_of) is not str or not _DATE.fullmatch(as_of):
        _refuse("BAD_TYPE", "as_of")
    try:
        import datetime
        datetime.date.fromisoformat(as_of)
    except ValueError:
        _refuse("BAD_TYPE", "as_of")
    if not type(niches) is list:
        _refuse("BAD_TYPE", "niches")
    if not niches:
        _refuse("EMPTY", "niches")
    _caps(niches)
    as_of = _text(as_of, "as_of", 10)
    clean = [_validate_niche(n) for n in niches]
    if len({n["id"] for n in clean}) != len(clean):
        _refuse("BAD_TYPE", "niches")
    regulated = sorted((n for n in clean if n["regulated_flags"]), key=lambda n: n["id"])
    built = sorted((n for n in clean if not n["regulated_flags"]), key=lambda n: n["id"])
    if not built:
        _refuse("REGULATED", "niches")
    return {
        "blueprints": [_blueprint(n) for n in built],
        "regulated_review": [{"id": n["id"], "status": "regulated_review_needed"} for n in regulated],
        "coverage": {"niches_supplied": len(clean), "blueprints_built": len(built),
                     "regulated_review_count": len(regulated)},
        "scope": policy.scope(
            ["offer text from supplied fields", "pricing passthrough", "worker-role edge graph",
             "fixed KPI names with null targets", "fixed three-file scaffold", "regulated gating"],
            ["market validation", "registration", "payments", "worker execution",
             "funnel", "scores", "leading any industry"],
            "supplied request only", as_of),
    }
