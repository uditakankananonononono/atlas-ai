"""A3 / c31.okara - okara integration adapter stub (supplied descriptors only).

Source excerpt (verbatim): "improve atlas so, it can integrate clicky, okara
ai tool".

The tool's current public API/pricing is NOT verified live (offline unit):
identification accepts only a SUPPLIED descriptor (her docs/links) naming the
tool with pricing evidence. The adapter is pure: it plans requests and parses
supplied responses; it never performs network calls itself (transport is
caller-supplied and only ever a mock in tests). Live smoke on a free tier is
explicitly out of scope until she approves account use. Stdlib only,
deterministic.

Identified descriptors carry endpoints as DETACHED DEEP COPIES - mutable, not
frozen; identify and plan_request share descriptor validation through the
shared _validate_descriptor, so post-identify mutation is rejected at the next
call; parse_response validates the supplied plan shape and the response
status/body instead. parse_response refuses literal NaN/Infinity constants, but
valid JSON like 1e999 parses as float inf under Python; response fields carry
NO finite-output promise (only request params are validated finite).
"""
from __future__ import annotations

import json
import math
from urllib.parse import urlencode

from app.modules.c30 import policy

PREFIX = "APPLY"
TARGET = "okara"
MAX_PARAMS = 64
MAX_BODY = 100000
IDENTIFY_QUESTION = ("What is okara's current API and pricing? Please send "
                     "the docs/pricing link you mean, so the adapter matches "
                     "the right tool.")
REQUIRED = ("name", "docs_url", "api_base", "pricing_evidence", "key_ref",
            "endpoints")


def _validate_descriptor(descriptor):
    """The single descriptor validation path. Returns a FRESH clean descriptor
    (deep-copied endpoints): later caller mutation of the supplied dict never
    alters what was validated."""
    if isinstance(descriptor, bool) or not isinstance(descriptor, dict):
        raise ValueError("APPLY_REFUSED_NOSOURCE")
    for field in REQUIRED:
        if field not in descriptor:
            raise ValueError("APPLY_REFUSED_BAD_TYPE:" + field)
    name = policy.clean_text(descriptor["name"], PREFIX, "name", 64)
    docs_url = policy.clean_text(descriptor["docs_url"], PREFIX, "docs_url", 512)
    api_base = policy.clean_text(descriptor["api_base"], PREFIX, "api_base", 512)
    evidence = policy.clean_text(descriptor["pricing_evidence"], PREFIX,
                                 "pricing_evidence", 2000)
    key_ref = policy.clean_text(descriptor["key_ref"], PREFIX, "key_ref", 64)
    if "free_tier" not in descriptor:  # omitted field refuses cleanly, never KeyError
        raise ValueError("APPLY_REFUSED_BAD_TYPE:free_tier")
    free_tier = descriptor["free_tier"]
    if free_tier is not None and not isinstance(free_tier, bool):
        raise ValueError("APPLY_REFUSED_BAD_TYPE:free_tier")
    endpoints = descriptor["endpoints"]
    if isinstance(endpoints, bool) or not isinstance(endpoints, dict) or not endpoints:
        raise ValueError("APPLY_REFUSED_BAD_TYPE:endpoints")
    clean_endpoints = {}
    for ep, spec in endpoints.items():
        policy.clean_text(ep, PREFIX, "endpoints", 64)
        if not isinstance(spec, dict):
            raise ValueError("APPLY_REFUSED_BAD_TYPE:endpoints")
        path = policy.clean_text(spec.get("path"), PREFIX, "path", 256)
        method = policy.clean_text(spec.get("method"), PREFIX, "method", 8)
        if method not in ("GET", "POST"):
            raise ValueError("APPLY_REFUSED_BAD_TYPE:method")
        clean_endpoints[ep] = {"path": path, "method": method}  # detached deep copy
    return {"name": name, "docs_url": docs_url, "api_base": api_base,
            "pricing_evidence": evidence, "key_ref": key_ref,
            "free_tier": free_tier, "endpoints": clean_endpoints}


def identify(descriptor):
    """Validate a supplied tool descriptor; returns the identification ledger."""
    clean = _validate_descriptor(descriptor)
    if clean["name"].strip().lower() != TARGET:
        return {"status": "unidentified", "descriptor": None,
                "question": IDENTIFY_QUESTION,
                "scope": policy.scope(
                    ["supplied-descriptor identification"],
                    ["guessing the tool", "live lookup", "spend"],
                    "supplied descriptor (her docs/links)")}
    if clean["free_tier"] is not True:
        policy.check("spend", PREFIX)  # pricing not evidenced free: refuse
    clean["free_tier"] = True
    return {"status": "identified", "descriptor": clean, "question": None,
            "scope": policy.scope(
                ["supplied-descriptor identification", "free tier evidenced"],
                ["live verification of pricing", "account use without approval"],
                "supplied descriptor (her docs/links)")}


def plan_request(descriptor, endpoint_key, params):
    """Build a pure request plan; performs NO call. The full descriptor is
    re-validated at this public entry: no post-identification mutation or
    direct-call bypass reaches a plan."""
    clean = _validate_descriptor(descriptor)  # shared validation, no bypass
    if clean["name"].strip().lower() != TARGET or clean["free_tier"] is not True:
        raise ValueError("APPLY_REFUSED_UNIDENTIFIED")
    if endpoint_key not in clean["endpoints"]:
        raise ValueError("APPLY_REFUSED_UNKNOWN_ENDPOINT:" + str(endpoint_key))
    if isinstance(params, bool) or not isinstance(params, dict):
        raise ValueError("APPLY_REFUSED_BAD_TYPE:params")
    if len(params) > MAX_PARAMS:
        raise ValueError("APPLY_REFUSED_OVERSIZE")
    # every key is validated BEFORE any sort: mixed-type keys refuse cleanly
    keyed = []
    for k in params:
        keyed.append(policy.clean_text(k, PREFIX, "params", 64))
    # clean_text returns validated strings unchanged, so keyed == original keys
    clean_params = {}
    for k in sorted(keyed):
        v = params[k]
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            raise ValueError("APPLY_REFUSED_BAD_TYPE:params")
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError("APPLY_REFUSED_BAD_TYPE:params")
        if isinstance(v, str):
            v = policy.clean_text(v, PREFIX, "params", 256)
        clean_params[k] = v
    spec = clean["endpoints"][endpoint_key]
    return {"method": spec["method"],
            "url": clean["api_base"].rstrip("/") + spec["path"],
            "headers": {"Authorization": "Bearer ${%s}" % clean["key_ref"],
                        "Accept": "application/json"},
            "params": clean_params,
            "encoded": urlencode(clean_params)}


def _strict_constant(name):
    raise ValueError("APPLY_REFUSED_BAD_JSON")


def parse_response(plan, status, body):
    """Parse a SUPPLIED response for a planned request (never fetched here)."""
    if not isinstance(plan, dict):
        raise ValueError("APPLY_REFUSED_BAD_TYPE:plan")
    method = plan.get("method")
    if not isinstance(method, str) or method not in ("GET", "POST"):
        raise ValueError("APPLY_REFUSED_BAD_TYPE:plan:method")
    if not isinstance(plan.get("url"), str) or not plan["url"].strip():
        raise ValueError("APPLY_REFUSED_BAD_TYPE:plan:url")
    if isinstance(status, bool) or not isinstance(status, int):
        raise ValueError("APPLY_REFUSED_BAD_TYPE:status")
    if status < 200 or status >= 300:
        raise ValueError("APPLY_REFUSED_HTTP:%d" % status)
    if not isinstance(body, str) or len(body) > MAX_BODY:
        raise ValueError("APPLY_REFUSED_BAD_TYPE:body")
    try:
        data = json.loads(body, parse_constant=_strict_constant)
    except ValueError:
        raise ValueError("APPLY_REFUSED_BAD_JSON")
    return {"status_code": status, "data": data,
            "request": {"method": method, "url": plan["url"]},
            "scope": policy.scope(
                ["parsed supplied response"],
                ["live calls", "spend", "auto-submission"],
                "caller-supplied mock transport response")}
