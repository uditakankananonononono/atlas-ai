"""Row695 Strangler Fig Pattern: finite declared route dispatch and recorded-fixture parity.

Pure evaluator. It never routes network traffic, never executes a handler and never
reads production traffic. "Handlers" are labels; "old/new outputs" are supplied
recorded fixtures. See docs/M20_STRANGLER695_CONTRACT.md for scope and limits.
"""
from __future__ import annotations

import math
import re
from typing import Any

ALGORITHM = "finite_strangler_route_dispatch_v1"
METHODS = ("DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT")
ROLES = ("legacy", "replacement")
MAX_RULES = MAX_REQUESTS = MAX_FIXTURES = 64
MAX_PATH = 256
MAX_SEGMENTS = 16
MAX_DEPTH = 8
MAX_NODES = 256
MAX_STRING = 4096
MAX_KEY = 64
MAX_INT_BITS = 256
FIELDS = ("body", "status")
DEFAULT_RULE = "@default"
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
_CHARS = re.compile(r"[A-Za-z0-9._~!$&'()*+,;=:@%/-]+")
_PCT = re.compile(r"%([0-9A-F]{2})")
_UNRESERVED = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def _id(value: Any, what: str) -> str:
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError(f"{what} must be a 1..64 character id of letters, digits and _.:-")
    return value


def _keys(obj: Any, required: set, optional: set, what: str) -> dict:
    if not isinstance(obj, dict) or any(type(k) is not str for k in obj):
        raise ValueError(f"{what} must be an object")
    missing, extra = required - set(obj), set(obj) - required - optional
    if missing or extra:
        raise ValueError(f"{what} keys invalid: missing {sorted(missing)} unknown {sorted(extra)}")
    return obj


def path_problem(path: Any) -> str | None:
    """Return a refusal code for a path that is not already normalized, else None."""
    if type(path) is not str:
        return "path_not_string"
    if not 1 <= len(path) <= MAX_PATH:
        return "path_length"
    if not path.isascii() or not _CHARS.fullmatch(path):
        return "forbidden_character"
    if path[0] != "/":
        return "path_must_start_with_slash"
    if path == "/":
        return None
    if path.endswith("/"):
        return "trailing_slash_ambiguous"
    segments = path[1:].split("/")
    if len(segments) > MAX_SEGMENTS:
        return "too_many_segments"
    for seg in segments:
        if seg == "":
            return "empty_segment"
        if seg in (".", ".."):
            return "dot_segment"
    stripped = path
    for m in _PCT.finditer(path):
        octet = int(m.group(1), 16)
        if octet in _UNRESERVED or octet < 0x20 or octet == 0x7F or chr(octet) in "/\\%?#.":
            return "ambiguous_percent_encoding"
    stripped = _PCT.sub("", path)
    if "%" in stripped:
        return "bad_percent_encoding"
    return None


def _json(value: Any, depth: int, budget: list) -> None:
    budget[0] += 1
    if depth > MAX_DEPTH or budget[0] > MAX_NODES:
        raise ValueError("body exceeds depth 8 or 256 nodes")
    t = type(value)
    if value is None or t is bool:
        return
    if t is int:
        if value.bit_length() > MAX_INT_BITS:
            raise ValueError("body integer too large")
    elif t is float:
        if not math.isfinite(value):
            raise ValueError("body numbers must be finite")
    elif t is str:
        if len(value) > MAX_STRING:
            raise ValueError("body string exceeds 4096 characters")
    elif t is list:
        for item in value:
            _json(item, depth + 1, budget)
    elif t is dict:
        for k, v in value.items():
            if type(k) is not str or len(k) > MAX_KEY:
                raise ValueError("body object keys must be strings of at most 64 characters")
            _json(v, depth + 1, budget)
    else:
        raise ValueError("body must be JSON data")


def _same(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if type(a) is list:
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if type(a) is dict:
        return set(a) == set(b) and all(_same(a[k], b[k]) for k in a)
    return a == b


def _output(obj: Any, what: str) -> dict:
    _keys(obj, {"status", "body"}, set(), what)
    status = obj["status"]
    if type(status) is not int or not 100 <= status <= 599:
        raise ValueError(f"{what}.status must be an integer 100..599 (not boolean)")
    _json(obj["body"], 1, [0])
    return obj


def _rule(raw: Any) -> dict:
    _keys(raw, {"id", "method", "match", "path", "target"}, set(), "rule")
    rid = _id(raw["id"], "rule id")
    if raw["method"] != "*" and raw["method"] not in METHODS or type(raw["method"]) is not str:
        raise ValueError("rule method must be '*' or an uppercase HTTP method")
    if raw["match"] not in ("exact", "prefix") or type(raw["match"]) is not str:
        raise ValueError("rule match must be exact or prefix")
    problem = path_problem(raw["path"])
    if problem:
        raise ValueError(f"rule {rid} path refused: {problem}")
    if raw["target"] not in ROLES or type(raw["target"]) is not str:
        raise ValueError("rule target must be legacy or replacement")
    segs = 0 if raw["path"] == "/" else raw["path"].count("/")
    kind = 1 if raw["match"] == "exact" else 0
    return {"id": rid, "method": raw["method"], "match": raw["match"], "path": raw["path"], "target": raw["target"],
            "key": (kind, 0 if kind else segs, 0 if raw["method"] == "*" else 1)}


def _covers(prefix: str, path: str) -> bool:
    return prefix == "/" or path == prefix or path.startswith(prefix + "/")


def _matches(rule: dict, method: str, path: str) -> bool:
    if rule["method"] not in ("*", method):
        return False
    return path == rule["path"] if rule["match"] == "exact" else _covers(rule["path"], path)


def _overlap(a: dict, b: dict) -> bool:
    if "*" not in (a["method"], b["method"]) and a["method"] != b["method"]:
        return False
    if a["match"] == "exact" and b["match"] == "exact":
        return a["path"] == b["path"]
    if a["match"] == "exact":
        return _covers(b["path"], a["path"])
    if b["match"] == "exact":
        return _covers(a["path"], b["path"])
    return _covers(a["path"], b["path"]) or _covers(b["path"], a["path"])


def _dominates(a: dict, b: dict) -> bool:
    return a["key"][:2] >= b["key"][:2] and a["key"][2] >= b["key"][2]


def _check_rules(rules: list) -> list:
    ids, selectors = set(), set()
    for r in rules:
        if r["id"] in ids:
            raise ValueError(f"duplicate rule id {r['id']}")
        ids.add(r["id"])
        sel = (r["match"], r["method"], r["path"])
        if sel in selectors:
            raise ValueError(f"duplicate_rule_selector {sel}")
        selectors.add(sel)
    overlaps = []
    ordered = sorted(rules, key=lambda r: r["id"])
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            if not _overlap(a, b):
                continue
            differ = a["target"] != b["target"]
            if differ and not (_dominates(a, b) or _dominates(b, a)):
                raise ValueError(f"ambiguous_precedence between rules {a['id']} and {b['id']}: path and method specificity disagree")
            win, lose = (a, b) if a["key"] > b["key"] else (b, a)
            kinds = {a["match"], b["match"]}
            kind = "exact_vs_prefix" if kinds == {"exact", "prefix"} else "prefix_vs_prefix" if kinds == {"prefix"} else "method_specific_vs_wildcard"
            overlaps.append({"kind": kind, "winner": win["id"], "shadowed": lose["id"], "targets_differ": differ})
    return sorted(overlaps, key=lambda o: (o["winner"], o["shadowed"]))


def _dispatch(req: dict, rules: list, targets: dict, default: str | None, override: set) -> dict:
    rec = {"request_id": req["id"], "method": req["method"] if req["method_ok"] else None, "path": req["path"] if req["path_ok"] else None,
           "decision": "refused", "target": None, "handler": None, "rule_id": None, "trace": [], "reasons": list(req["reasons"])}
    if req["reasons"]:
        return rec
    hits = sorted((r for r in rules if _matches(r, req["method"], req["path"])), key=lambda r: (tuple(-k for k in r["key"]), r["id"]))
    rec["trace"] = [{"rule_id": r["id"], "match": r["match"], "method": r["method"], "path": r["path"], "specificity": list(r["key"]), "selected": i == 0}
                    for i, r in enumerate(hits)]
    if hits:
        win = hits[0]
        target = "legacy" if win["id"] in override else win["target"]
        rec.update(decision="routed", target=target, rule_id=win["id"])
    elif default is not None:
        target = "legacy" if DEFAULT_RULE in override else default
        rec.update(decision="default", target=target)
    else:
        rec["decision"] = "no_route"
        return rec
    rec["handler"] = targets[rec["target"]]["handler"]
    return rec


def _request(raw: Any) -> dict:
    _keys(raw, {"id", "method", "path"}, set(), "request")
    reasons = []
    method_ok = type(raw["method"]) is str and raw["method"] in METHODS
    if not method_ok:
        reasons.append("method_not_normalized_uppercase_http_method")
    problem = path_problem(raw["path"])
    if problem:
        reasons.append(problem)
    return {"id": _id(raw["id"], "request id"), "method": raw["method"], "path": raw["path"], "method_ok": method_ok, "path_ok": problem is None,
            "reasons": reasons}


def _golden(raw: Any) -> dict:
    _keys(raw, {"parity", "mismatched_fields"}, set(), "golden")
    fields = raw["mismatched_fields"]
    if type(raw["parity"]) is not bool or type(fields) is not list or any(f not in FIELDS or type(f) is not str for f in fields) or len(set(fields)) != len(fields):
        raise ValueError("golden requires boolean parity and unique mismatched_fields from body,status")
    if raw["parity"] != (not fields):
        raise ValueError("golden parity contradicts mismatched_fields")
    return {"parity": raw["parity"], "mismatched_fields": sorted(fields)}


def evaluate(data: Any) -> dict:
    """Evaluate route dispatch and recorded-fixture parity. Raises ValueError on malformed input."""
    _keys(data, {"targets", "rules", "requests"}, {"fixtures", "default_target"}, "input")
    targets = _keys(data["targets"], set(ROLES), set(), "targets")
    for role in ROLES:
        _keys(targets[role], {"handler"}, set(), f"targets.{role}")
        _id(targets[role]["handler"], f"targets.{role}.handler")
    default = data.get("default_target")
    if default is not None and (type(default) is not str or default not in ROLES):
        raise ValueError(f"unknown default_target {default!r}")
    raw_rules, raw_reqs, raw_fix = data["rules"], data["requests"], data.get("fixtures", [])
    for seq, lo, hi, what in ((raw_rules, 1, MAX_RULES, "rules"), (raw_reqs, 1, MAX_REQUESTS, "requests"), (raw_fix, 0, MAX_FIXTURES, "fixtures")):
        if type(seq) is not list or not lo <= len(seq) <= hi:
            raise ValueError(f"{what} must be a list of {lo}..{hi} items")
    rules = [_rule(r) for r in raw_rules]
    overlaps = _check_rules(rules)
    reqs = [_request(r) for r in raw_reqs]
    seen = set()
    for r in reqs:
        if r["id"] in seen:
            raise ValueError(f"duplicate request id {r['id']}")
        seen.add(r["id"])
    fixtures, fids, freqs = [], set(), set()
    for raw in raw_fix:
        _keys(raw, {"id", "request_id", "legacy", "replacement"}, {"golden"}, "fixture")
        fid, rid = _id(raw["id"], "fixture id"), _id(raw["request_id"], "fixture request_id")
        if fid in fids:
            raise ValueError(f"duplicate fixture id {fid}")
        if rid not in seen:
            raise ValueError(f"unknown request_id {rid} in fixture {fid}")
        if rid in freqs:
            raise ValueError(f"duplicate fixture for request {rid}")
        fids.add(fid)
        freqs.add(rid)
        fixtures.append({"id": fid, "request_id": rid, "legacy": _output(raw["legacy"], "fixture.legacy"),
                         "replacement": _output(raw["replacement"], "fixture.replacement"),
                         "golden": _golden(raw["golden"]) if "golden" in raw else None})

    reqs.sort(key=lambda r: r["id"])
    fixtures.sort(key=lambda f: f["id"])
    base = [_dispatch(r, rules, targets, default, set()) for r in reqs]
    by_req = {r["request_id"]: r for r in base}

    parity, candidates, violations, fixture_reqs = [], set(), [], set()
    for f in fixtures:
        route = by_req[f["request_id"]]
        fixture_reqs.add(f["request_id"])
        fields = sorted(name for name in FIELDS if not _same(f["legacy"][name], f["replacement"][name]))
        golden_ok = None if f["golden"] is None else (f["golden"]["mismatched_fields"] == fields and f["golden"]["parity"] == (not fields))
        if golden_ok is False:
            violations.append(f["id"])
        target = route["target"]
        parity.append({"fixture_id": f["id"], "request_id": f["request_id"], "effective_target": target, "parity": not fields,
                       "mismatched_fields": fields, "golden_ok": golden_ok, "served_output": f[target] if target else None})
        if target == "replacement" and (fields or golden_ok is False):
            candidates.add(route["rule_id"] or DEFAULT_RULE)
    unverified = sorted({r["rule_id"] or DEFAULT_RULE for r in base if r["target"] == "replacement" and r["request_id"] not in fixture_reqs})

    cand = sorted(candidates)
    after = [_dispatch(r, rules, targets, default, candidates) for r in reqs]
    effect = [{"request_id": b["request_id"], "rule_id": b["rule_id"], "before": b["target"], "after": a["target"]}
              for b, a in zip(base, after) if b["target"] != a["target"]]
    blockers = ["fixture_parity_compares_recorded_outputs_only", "no_production_traffic_or_handler_execution_observed"]
    if any(r["decision"] == "refused" for r in base):
        blockers.append("refused_requests_present")
    if any(r["decision"] == "no_route" for r in base):
        blockers.append("unrouted_requests_present")
    if unverified:
        blockers.append("replacement_routes_without_fixture")
    if any(not p["parity"] for p in parity):
        blockers.append("parity_mismatch_present")
    if violations:
        blockers.append("golden_violation_present")
    return {
        "algorithm": ALGORITHM, "status": "evaluated", "routes": base, "overlaps": overlaps, "parity": parity,
        "golden_violations": sorted(violations), "rollback_candidates": cand, "unverified_replacement_rules": unverified,
        "rollback_effect": effect, "after_rollback_routes": after,
        "legacy_removal_safe": False, "legacy_removal_blockers": sorted(blockers),
        "handler_executed": False, "network_routing_performed": False, "production_traffic_verified": False,
    }
