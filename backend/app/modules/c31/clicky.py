"""A3 / c31.clicky - clicky integration adapter stub (supplied descriptors only).

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

import http.client as _http_client
import json
import math
import os
import re
import time
import urllib.error as _urlerr
import urllib.request as _urlreq
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout
from urllib.parse import urlencode, urlsplit as _urlsplit

from app.modules.c30 import policy

PREFIX = "APPLY"
TARGET = "clicky"
MAX_PARAMS = 64
MAX_BODY = 100000
IDENTIFY_QUESTION = ("What is clicky's current API and pricing? Please send "
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


# --- Documented public API shape (read from https://clicky.com/help/api on 2026-10-12) ---
# This records what the public docs said on that date. It is NOT proof that the
# API still behaves this way; no live call has been made (that needs her site_id
# and sitekey and her approval). Requests are HTTP GET to the base with site_id,
# sitekey and type query parameters, not Bearer auth, so plan_request's header
# shape does not apply. Docs: free accounts get the last 30 days of history and
# 100 results per request.
DOCUMENTED_API_BASE = "https://api.clicky.com/api/stats/4"
DOCUMENTED_DOCS_URL = "https://clicky.com/help/api"
DOCUMENTED_TYPES = frozenset({"visitors", "pages", "pages-entrance", "pages-exit", "links",
                              "links-domains", "searches", "searches-keywords", "countries",
                              "cities", "goals", "campaigns", "events", "downloads"})
FREE_MAX_LIMIT = 100
FREE_MAX_HISTORY_DAYS = 30
_RELATIVE_DATES = {"today", "yesterday"}
_LAST_N_DAYS = re.compile(r"^last-([1-9][0-9]{0,2})-days$")


def _history_days_ok(date):
    """Free-tier history bound, enforced for the date forms we can reason about.
    Absolute dates are refused: they cannot be bounded without a clock."""
    if date in _RELATIVE_DATES:
        return True
    m = _LAST_N_DAYS.match(date)
    return bool(m) and int(m.group(1)) <= FREE_MAX_HISTORY_DAYS


def plan_stats_request(site_id, types, *, date="last-7-days", limit=FREE_MAX_LIMIT):
    """Pure plan for the documented Clicky stats GET. The sitekey is never
    embedded: it is a secret reference resolved by the caller's transport."""
    if isinstance(site_id, bool) or not isinstance(site_id, int) or site_id <= 0:
        raise ValueError("APPLY_REFUSED_BAD_TYPE:site_id")
    if isinstance(types, str):
        types = [types]
    if not isinstance(types, (list, tuple)) or not types or len(types) > 8:
        raise ValueError("APPLY_REFUSED_BAD_TYPE:types")
    for t in types:  # type-check before any set membership: unhashable input must refuse cleanly
        if not isinstance(t, str):
            raise ValueError("APPLY_REFUSED_BAD_TYPE:types")
    for t in types:
        if t not in DOCUMENTED_TYPES:
            raise ValueError("APPLY_REFUSED_UNKNOWN_ENDPOINT:" + t[:64])
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= FREE_MAX_LIMIT:
        raise ValueError("APPLY_REFUSED_BAD_TYPE:limit")
    date = policy.clean_text(date, PREFIX, "date", 64)
    if not _history_days_ok(date):
        raise ValueError("APPLY_REFUSED_BAD_TYPE:date")
    params = {"site_id": site_id, "sitekey": "${CLICKY_SITEKEY}", "type": ",".join(types),
              "date": date, "limit": limit, "output": "json"}
    return {"method": "GET", "url": DOCUMENTED_API_BASE, "params": params,
            "headers": {"Accept": "application/json"}, "live_verified": False,
            "docs_url": DOCUMENTED_DOCS_URL}


# --- Real transport for the documented stats GET ---
# execute_stats_request performs the HTTP GET itself with the stdlib. It is OFF by default for the
# real host: a call without base_url is refused unless the caller passes live_approved=True AND the
# process environment sets ATLAS_CLICKY_LIVE_OWNER_APPROVED=1. This is a default-off guard, not an
# authorization system: it exists so no caller can reach api.clicky.com by accident. The owner's
# approval and sitekey are still required in fact. The sitekey travels in the query string because
# the documented API takes it there; it is never returned, logged or placed in an error.
# Tests drive it only against a loopback server (allow_loopback=True) behind a socket guard.
TRANSPORT_TIMEOUT_S = 10.0
LIVE_ENV_FLAG = "ATLAS_CLICKY_LIVE_OWNER_APPROVED"
_PLAN_KEYS = {"method", "url", "params", "headers", "live_verified", "docs_url"}
_PARAM_KEYS = {"site_id", "sitekey", "type", "date", "limit", "output"}


class _NoRedirect(_urlreq.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # a redirect could carry the sitekey elsewhere
        return None


def _validated_plan(plan):
    """Accept only a plan that plan_stats_request would itself produce. Any malformed input is
    APPLY_REFUSED_BAD_TYPE:plan, never a KeyError/TypeError."""
    try:
        if not isinstance(plan, dict) or set(plan) != _PLAN_KEYS:
            raise ValueError
        params = plan["params"]
        if not isinstance(params, dict) or set(params) != _PARAM_KEYS or not isinstance(params["type"], str):
            raise ValueError
        rebuilt = plan_stats_request(params["site_id"], params["type"].split(","), date=params["date"], limit=params["limit"])
        if rebuilt != plan:
            raise ValueError
    except (ValueError, TypeError, AttributeError, KeyError):
        raise ValueError("APPLY_REFUSED_BAD_TYPE:plan") from None
    return plan


def _fetch(url, headers, per_op_timeout, deadline):
    """One bounded GET; returns (status, bytes) or an error code string. Runs in a worker thread."""
    req = _urlreq.Request(url, headers=headers, method="GET")
    opener = _urlreq.build_opener(_urlreq.ProxyHandler({}), _NoRedirect)  # no proxy env: key never leaves the host
    try:
        with opener.open(req, timeout=per_op_timeout) as resp:
            status, buf = resp.status, bytearray()
            while len(buf) <= MAX_BODY:
                if time.monotonic() > deadline:
                    return "APPLY_REFUSED_TRANSPORT", None
                chunk = resp.read1(4096)  # returns what has arrived, so the deadline is re-checked on a drip
                if not chunk:
                    break
                buf += chunk
            return status, bytes(buf)
    except _urlerr.HTTPError as exc:
        code = exc.code
        try:
            exc.close()
        except Exception:
            pass
        return "APPLY_REFUSED_HTTP:%d" % code, None
    except (_urlerr.URLError, TimeoutError, OSError, _http_client.HTTPException):
        return "APPLY_REFUSED_TRANSPORT", None


def execute_stats_request(plan, sitekey, *, timeout=TRANSPORT_TIMEOUT_S, base_url=None, allow_loopback=False,
                          live_approved=False):
    """Run a plan from plan_stats_request. Returns parse_response output.

    Refusals are ValueError('APPLY_REFUSED_*') with no chained exception, so the sitekey (which is in
    the request URL) is not reachable from __context__/__cause__ or a traceback. `timeout` bounds the
    WHOLE call (connect, headers and body) as seen by the CALLER: the call returns within `timeout`
    (outer future timeout). Residue: urllib cannot cancel the worker, so after a refusal the worker thread may
    outlive the call, for body reads until its next read1 (deadline check) and for connect/header stalls until the
    per-operation timeout (`timeout`) trips or the server finishes. It holds no result and nothing waits on it. base_url overrides the
    host only when allow_loopback is True and the host is 127.0.0.1/localhost over http."""
    plan = _validated_plan(plan)
    if not isinstance(sitekey, str) or not re.fullmatch(r"[A-Za-z0-9]{6,64}", sitekey):
        raise ValueError("APPLY_REFUSED_BAD_TYPE:sitekey")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
        raise ValueError("APPLY_REFUSED_BAD_TYPE:timeout")
    url = plan["url"]
    if base_url is None:
        if live_approved is not True or os.environ.get(LIVE_ENV_FLAG) != "1":
            raise ValueError("APPLY_REFUSED_NOT_APPROVED")
    else:
        parts = _urlsplit(base_url)
        if (not allow_loopback or parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost"}
                or parts.query or parts.fragment or parts.username or parts.password):
            raise ValueError("APPLY_REFUSED_BAD_TYPE:base_url")
        url = base_url
    params = dict(plan["params"])
    params["sitekey"] = sitekey
    deadline = time.monotonic() + timeout
    pool = ThreadPoolExecutor(max_workers=1)
    fut = pool.submit(_fetch, url + "?" + urlencode(params), dict(plan["headers"]), timeout, deadline)
    try:
        status, raw = fut.result(timeout=timeout)
    except _FutTimeout:
        status, raw = "APPLY_REFUSED_TRANSPORT", None
    finally:
        pool.shutdown(wait=False)
    if raw is None:
        raise ValueError(status)
    if len(raw) > MAX_BODY:
        raise ValueError("APPLY_REFUSED_BAD_TYPE:body")
    try:
        body = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("APPLY_REFUSED_BAD_JSON") from None
    out = parse_response(dict(plan, url=url), status, body)  # url carries no query: the key is not in it
    out["request"] = {"method": "GET", "url": url}
    out["scope"] = policy.scope(["one GET to the stats endpoint"], ["spend", "auto-submission", "writes"],
                                "real transport; live use needs the owner's sitekey and approval")
    return out
