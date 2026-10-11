"""S3.1 trend-to-product prototyper (c34, prefix PROTO).

From a supplied trend brief this emits a product spec, a static mockup site (plain
HTML, no scripts or external references), a CAD-free gadget spec with a bill of
materials, and a free-tool build plan. Paid tools are not bought or used: each
tool kind maps to an in-repo generator at zero cost. Hermetic, stdlib only, no
network, clock or RNG; the output depends only on the payload.

Not implemented (see scope): trend discovery, any novelty or creativity judgement,
physical prototyping or CAD, part ordering, and any spend.
"""

import html
import re
import unicodedata

from app.modules.c30 import policy

UNIT = "S3.1"
_SPEND_KEYS = ("purchase", "spend", "order_parts", "live_api", "buy_paid_tools")
_PAYLOAD_FIELDS = {"as_of", "brief"} | set(_SPEND_KEYS)
_BRIEF_FIELDS = {"name", "trend", "audience", "features", "components", "tools", "currency"}
_COMPONENT_FIELDS = {"name", "qty", "unit_cost_cents"}
_TOOL_FIELDS = {"name", "kind", "paid"}
_TOOL_KINDS = ("site", "bom", "spec")
_SUBSTITUTE = {"site": "in-repo:site_html_generator", "bom": "in-repo:bom_generator",
               "spec": "in-repo:spec_generator"}
_MAX_AS_OF, _MAX_NAME, _MAX_TREND, _MAX_AUDIENCE, _MAX_FEATURE = 64, 80, 200, 120, 120
_MAX_FEATURES, _MAX_COMPONENTS, _MAX_TOOLS = 8, 30, 10
_MAX_QTY, _MAX_COST = 10000, 10000000
_UNSAFE = re.compile(r"(?:weapons?|firearms?|explosives?|bombs?|poisons?|malware|ransomware|"
                     r"spyware|stalkerware)\b", re.I)
_SCOPE_IMPLEMENTED = ("product spec, static mockup site, CAD-free gadget spec with a computed bill of "
                      "materials, and a free-tool build plan, from the supplied brief only")
_SCOPE_NOT_IMPLEMENTED = [
    "trend discovery: the trend is supplied by the caller, not fetched or verified",
    "novelty or creativity: nothing here assesses whether the product is new",
    "physical prototype, CAD, or part ordering: output is a spec, a BOM and a static mockup",
    "spend: no purchase, paid tool or live API call is made",
]


def _refuse(detail):
    raise ValueError("PROTO_REFUSED_" + detail)


def _strict_int(value):
    return type(value) is int


def _text(value, name, limit):
    if type(value) is not str:
        _refuse("BAD_TYPE:" + name)
    if not value or value != value.strip():
        _refuse("EMPTY_FIELD:" + name)
    if len(value) > limit:
        _refuse("TEXT_TOO_LONG:" + name)
    if any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in value):
        _refuse("UNSAFE_CHARS:" + name)
    return policy.clean_text(value, "PROTO", name, limit)


def _required(d, key, path):
    if key not in d:
        _refuse("EMPTY_FIELD:" + path)
    return d[key]


def _bounded(value, name, lo, hi):
    if not _strict_int(value):
        _refuse("BAD_TYPE:" + name)
    if value < lo or value > hi:
        _refuse("OUT_OF_RANGE:" + name)
    return value


def _validate(payload):
    if type(payload) is not dict:
        _refuse("BAD_TYPE:payload")
    if set(payload) - _PAYLOAD_FIELDS:
        _refuse("UNKNOWN_FIELDS:payload")
    if any(payload.get(k) for k in _SPEND_KEYS):
        _refuse("SPEND:no_purchase_paid_tool_or_live_api")
    as_of = _text(_required(payload, "as_of", "as_of"), "as_of", _MAX_AS_OF)
    brief = _required(payload, "brief", "brief")
    if type(brief) is not dict:
        _refuse("BAD_TYPE:brief")
    if set(brief) - _BRIEF_FIELDS:
        _refuse("UNKNOWN_FIELDS:brief")
    name = _text(_required(brief, "name", "name"), "name", _MAX_NAME)
    trend = _text(_required(brief, "trend", "trend"), "trend", _MAX_TREND)
    audience = _text(_required(brief, "audience", "audience"), "audience", _MAX_AUDIENCE)

    features = _required(brief, "features", "features")
    if type(features) is not list:
        _refuse("BAD_TYPE:features")
    if not 1 <= len(features) <= _MAX_FEATURES:
        _refuse("OUT_OF_RANGE:features")
    seen = set()
    for i, f in enumerate(features):
        _text(f, "features[%d]" % i, _MAX_FEATURE)
        if f in seen:
            _refuse("DUPLICATE:features[%d]" % i)
        seen.add(f)

    components = brief.get("components", [])
    if type(components) is not list:
        _refuse("BAD_TYPE:components")
    if len(components) > _MAX_COMPONENTS:
        _refuse("OUT_OF_RANGE:components")
    seen = set()
    for i, c in enumerate(components):
        p = "components[%d]" % i
        if type(c) is not dict:
            _refuse("BAD_TYPE:" + p)
        if set(c) - _COMPONENT_FIELDS:
            _refuse("UNKNOWN_FIELDS:" + p)
        _text(_required(c, "name", p + ".name"), p + ".name", _MAX_NAME)
        if c["name"] in seen:
            _refuse("DUPLICATE:" + p + ".name")
        seen.add(c["name"])
        _bounded(_required(c, "qty", p + ".qty"), p + ".qty", 1, _MAX_QTY)
        _bounded(_required(c, "unit_cost_cents", p + ".unit_cost_cents"), p + ".unit_cost_cents", 0, _MAX_COST)

    tools = brief.get("tools", [])
    if type(tools) is not list:
        _refuse("BAD_TYPE:tools")
    if len(tools) > _MAX_TOOLS:
        _refuse("OUT_OF_RANGE:tools")
    seen = set()
    for i, t in enumerate(tools):
        p = "tools[%d]" % i
        if type(t) is not dict:
            _refuse("BAD_TYPE:" + p)
        if set(t) - _TOOL_FIELDS:
            _refuse("UNKNOWN_FIELDS:" + p)
        _text(_required(t, "name", p + ".name"), p + ".name", _MAX_NAME)
        if t["name"] in seen:
            _refuse("DUPLICATE:" + p + ".name")
        seen.add(t["name"])
        kind = _required(t, "kind", p + ".kind")
        if type(kind) is not str:
            _refuse("BAD_TYPE:" + p + ".kind")
        if kind not in _TOOL_KINDS:
            _refuse("BAD_KIND:" + (kind if re.fullmatch(r"[a-z]{1,16}", kind) else "invalid"))
        if type(_required(t, "paid", p + ".paid")) is not bool:
            _refuse("BAD_TYPE:" + p + ".paid")

    currency = brief.get("currency", "USD")
    if type(currency) is not str:
        _refuse("BAD_TYPE:currency")
    if not re.fullmatch(r"[A-Z]{3}", currency):
        _refuse("BAD_VALUE:currency")

    checks = [("name", name), ("trend", trend), ("audience", audience)]
    checks += [("features[%d]" % i, f) for i, f in enumerate(features)]
    checks += [("components[%d].name" % i, c["name"]) for i, c in enumerate(components)]
    checks += [("tools[%d].name" % i, t["name"]) for i, t in enumerate(tools)]
    for path, value in checks:
        if _UNSAFE.search(value):
            _refuse("UNSAFE:" + path)
    return as_of, name, trend, audience, features, components, tools, currency


def _site(name, trend, audience, features):
    e = html.escape
    lines = ["<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
             "<title>%s</title>" % e(name), "</head>", "<body>", "<h1>%s</h1>" % e(name),
             "<p>%s</p>" % e(trend), "<p>Audience: %s</p>" % e(audience), "<ul>"]
    lines += ["<li>%s</li>" % e(f) for f in features]
    lines += ["</ul>", "</body>", "</html>"]
    return "\n".join(lines) + "\n"


def run_prototype(payload):
    as_of, name, trend, audience, features, components, tools, currency = _validate(payload)
    spec_lines = ["Name: " + name, "Trend: " + trend, "Audience: " + audience]
    spec_lines += ["Feature %d: %s" % (i + 1, f) for i, f in enumerate(features)]
    bom = [{"name": c["name"], "qty": c["qty"], "unit_cost_cents": c["unit_cost_cents"],
            "line_total_cents": c["qty"] * c["unit_cost_cents"]} for c in components]
    plan_tools = [{"name": t["name"], "kind": t["kind"], "paid": t["paid"],
                   "used": _SUBSTITUTE[t["kind"]], "cost_cents": 0} for t in tools]
    steps = ["write product spec", "generate static mockup site", "compute bill of materials",
             "review with owner before any build or purchase"]
    return {
        "unit": UNIT,
        "spec": "# Product spec\n\n" + "\n".join(spec_lines) + "\n",
        "site_html": _site(name, trend, audience, features),
        "gadget": {"spec": spec_lines, "bom": bom,
                   "total_cents": sum(r["line_total_cents"] for r in bom), "currency": currency},
        "build_plan": {"tools": plan_tools,
                       "steps": [{"step": i + 1, "action": a} for i, a in enumerate(steps)]},
        "scope": {"implemented": _SCOPE_IMPLEMENTED, "not_implemented": list(_SCOPE_NOT_IMPLEMENTED),
                  "data_source": "supplied", "as_of": as_of},
    }
