"""P70 platform conduct preflight (outbound action gate).

Checks ONE proposed outbound action against rules the CALLER declares:
platform rules, rate limits plus a caller-supplied action history, consent
records, and purpose-limited data categories. Pure, deterministic, stdlib
only, no clock, no network, no storage. It performs no action.

It does not read any real terms of service, does not know any platform's real
rules, and is not proof of legal compliance. Missing declarations are denied
(fail closed). Malformed input raises ValueError.
"""
from __future__ import annotations

import math

SCOPE = "declared-input-only"


def _num(name, v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"{name} must be a finite number")
    return v


def _pint(name, v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        raise ValueError(f"{name} must be a positive integer")
    return v


def _str(name, v):
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return v


def _strs(name, v):
    if not isinstance(v, (list, tuple)):
        raise ValueError(f"{name} must be a list")
    return [_str(name, x) for x in v]


def _norm_action(a):
    if not isinstance(a, dict):
        raise ValueError("action must be a dict")
    purpose = a.get("purpose")
    if purpose is not None:
        _str("purpose", purpose)
    automated = a.get("automated", False)
    if not isinstance(automated, bool):
        raise ValueError("automated must be a bool")
    return {"platform": _str("platform", a.get("platform")), "kind": _str("kind", a.get("kind")),
            "at": _num("at", a.get("at")), "count": _pint("count", a.get("count", 1)),
            "subjects": _strs("subjects", a.get("subjects", [])),
            "data_categories": _strs("data_categories", a.get("data_categories", [])),
            "purpose": purpose, "automated": automated}


def _norm_decl(d):
    if not isinstance(d, dict):
        raise ValueError("declarations must be a dict")
    tos = d.get("tos")
    if not isinstance(tos, dict):
        raise ValueError("tos must be a dict")
    for plat, entry in tos.items():
        if not isinstance(entry, dict):
            raise ValueError(f"tos entry for {plat!r} must be a dict")
        if "allowed_kinds" in entry:
            if not isinstance(entry["allowed_kinds"], (list, tuple)):
                raise ValueError("tos allowed_kinds must be a list")
            _strs("tos allowed_kinds", entry["allowed_kinds"])
        if "automation_allowed" in entry and not isinstance(entry["automation_allowed"], bool):
            raise ValueError("tos automation_allowed must be a bool")
    rl = d.get("rate_limits", {})
    if not isinstance(rl, dict):
        raise ValueError("rate_limits must be a dict")
    for plat, kinds in rl.items():
        if not isinstance(kinds, dict):
            raise ValueError("rate_limits entry must be a dict")
        for k, rule in kinds.items():
            if not isinstance(rule, dict):
                raise ValueError("rate limit rule must be a dict")
            _pint("rate limit max", rule.get("max"))
            _pint("rate limit window_seconds", rule.get("window_seconds"))
    recent = d.get("recent_actions", [])
    if not isinstance(recent, list):
        raise ValueError("recent_actions must be a list")
    for e in recent:
        if not isinstance(e, dict):
            raise ValueError("recent action must be a dict")
        _str("recent platform", e.get("platform"))
        _str("recent kind", e.get("kind"))
        _num("recent at", e.get("at"))
        _pint("recent count", e.get("count", 1))
    consent = d.get("consent", [])
    if not isinstance(consent, list):
        raise ValueError("consent must be a list")
    for c in consent:
        if not isinstance(c, dict):
            raise ValueError("consent record must be a dict")
        _str("consent subject", c.get("subject"))
        _str("consent purpose", c.get("purpose"))
        _num("consent granted_at", c.get("granted_at"))
        if c.get("expires_at") is not None:
            _num("consent expires_at", c["expires_at"])
        if not isinstance(c.get("revoked", False), bool):
            raise ValueError("consent revoked must be a bool")
    privacy = d.get("privacy")
    if privacy is not None:
        if not isinstance(privacy, dict):
            raise ValueError("privacy must be a dict")
        if "personal_categories" in privacy:
            _strs("privacy personal_categories", privacy["personal_categories"])
        if "purpose_allowed" in privacy:
            pa = privacy["purpose_allowed"]
            if not isinstance(pa, dict):
                raise ValueError("privacy purpose_allowed must be a dict")
            for purpose, cats in pa.items():
                _str("privacy purpose", purpose)
                _strs("privacy purpose_allowed categories", cats)
    review = d.get("review_kinds", [])
    if not isinstance(review, (list, tuple)):
        raise ValueError("review_kinds must be a list")
    _strs("review_kinds", review)
    return tos, rl, recent, consent, privacy, list(review)


def _chk(name, passed, reason):
    return {"check": name, "passed": bool(passed), "reason": reason}


def preflight(action, declarations):
    a = _norm_action(action)
    tos, rl, recent, consent, privacy, review = _norm_decl(declarations)
    checks = []

    rules = tos.get(a["platform"])
    checks.append(_chk("tos_declared", isinstance(rules, dict),
                       "platform rules declared" if isinstance(rules, dict)
                       else f"no declared rules for platform {a['platform']!r}"))
    ok_rules = isinstance(rules, dict)
    kind_ok = ok_rules and a["kind"] in rules.get("allowed_kinds", [])
    checks.append(_chk("tos_kind_allowed", kind_ok,
                       f"kind {a['kind']!r} declared allowed" if kind_ok
                       else f"kind {a['kind']!r} not declared allowed"))
    auto_ok = ok_rules and (not a["automated"] or rules.get("automation_allowed") is True)
    checks.append(_chk("tos_automation", auto_ok,
                       "automation not used or declared allowed" if auto_ok
                       else "automated action but automation not declared allowed"))

    by_plat = rl.get(a["platform"], {})
    rule = by_plat.get(a["kind"])
    wildcard = False
    if rule is None:
        rule, wildcard = by_plat.get("*"), True
    if rule is None:
        checks.append(_chk("rate_limit", False, "no rate limit declared for this platform and kind"))
    else:
        lo = a["at"] - rule["window_seconds"]
        used = sum(e.get("count", 1) for e in recent
                   if e["platform"] == a["platform"] and (wildcard or e["kind"] == a["kind"])
                   and lo < e["at"] <= a["at"])
        total = used + a["count"]
        checks.append(_chk("rate_limit", total <= rule["max"],
                           f"{total} in window (limit {rule['max']} per {rule['window_seconds']}s)"))

    if a["subjects"]:
        missing = []
        for s in a["subjects"]:
            good = any(c["subject"] == s and a["purpose"] is not None and c["purpose"] == a["purpose"]
                       and not c.get("revoked", False) and c["granted_at"] <= a["at"]
                       and (c.get("expires_at") is None or c["expires_at"] > a["at"])
                       for c in consent)
            if not good:
                missing.append(s)
        checks.append(_chk("consent", not missing,
                           "valid declared consent for all subjects" if not missing
                           else "no valid consent for: " + ", ".join(missing)))
    else:
        checks.append(_chk("consent", True, "no subjects declared"))

    cats = a["data_categories"]
    if cats and privacy is None:
        checks.append(_chk("privacy_purpose", False, "data categories given but no privacy declaration"))
    elif cats:
        personal = [c for c in cats if c in privacy.get("personal_categories", [])]
        if not personal:
            checks.append(_chk("privacy_purpose", True, "no declared personal categories"))
        else:
            allowed = privacy.get("purpose_allowed", {}).get(a["purpose"]) if a["purpose"] else None
            bad = [c for c in personal if allowed is None or c not in allowed]
            checks.append(_chk("privacy_purpose", not bad,
                               "personal categories within declared purpose" if not bad
                               else "categories not allowed for declared purpose: " + ", ".join(bad)))
    else:
        checks.append(_chk("privacy_purpose", True, "no data categories declared"))

    if any(not c["passed"] for c in checks):
        verdict = "deny"
    elif a["kind"] in review:
        verdict = "needs_review"
    else:
        verdict = "allow"
    return {"verdict": verdict, "checks": checks, "scope": SCOPE,
            "performs_no_action": True, "not_legal_compliance": True}
