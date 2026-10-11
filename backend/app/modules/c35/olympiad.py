"""c35.olympiad (S4.8): olympiad practice and registration PREP, offline.

Two parts over SUPPLIED data only: a registration checklist with form-prefill,
and timed mock scoring of a supplied question bank. There is no code path that
registers, logs in, attempts a real exam, pays, sends or creates accounts.
Stdlib plus the c30 policy guard. No wall clock: the only date is `as_of`.
"""
from __future__ import annotations

import datetime as _dt
import math
import re

from app.modules.c30 import policy

PREFIX = "APPLY"
MODES = ("checklist", "mock")
REASONS = ("ATTEMPT", "BAD_TYPE", "EMPTY", "NOCREDS", "OVERSIZE", "REGISTER", "SEND", "SPEND")

MAX_BANK = 256
MAX_REQUIREMENTS = 64
MAX_PROMPT = 2000
MAX_TIME_LIMIT_S = 86400
MAX_ELAPSED_S = 604800

# Forbidden dict KEYS (any depth). Highest class first = precedence.
_FORBIDDEN = (
    ("SEND", frozenset(["send", "approve", "approved", "approval", "approval_token", "smtp",
                        "token", "email_send", "sender", "smtp_host", "smtp_port", "smtp_user"])),
    ("SPEND", frozenset(["pay", "waive_fee", "fee_action"])),
    ("REGISTER", frozenset(["register", "submit"])),
    ("ATTEMPT", frozenset(["attempt", "take_exam"])),
    ("NOCREDS", frozenset(["login", "password", "username", "credentials", "otp", "api_key",
                           "access_token", "refresh_token", "bearer", "pass", "passwd"])),
)
_NO_PREFILL = frozenset(["password", "login", "username", "otp", "ssn", "passport", "aadhaar",
                         "pan", "national_id", "card_number"])
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", re.ASCII)

_LIMITS_CHECKLIST = ("Checklist and form-prefill from supplied data only. Does not register, "
                     "log in or submit anything. Does not claim readiness.")
_LIMITS_MOCK = ("A mock score is not an olympiad score. The unit supplies no question content "
                "and does not attempt any real exam. Does not claim readiness.")


def _norm_key(k):
    return k.casefold().replace("-", "_")


def _scan_keys(node, path, hits, nonstr):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str):
                nk = _norm_key(k)
                p = path + [nk]
                for reason, keys in _FORBIDDEN:
                    if nk in keys:
                        hits.append((reason, nk))  # nk equals a table constant
                        break
                _scan_keys(v, p, hits, nonstr)
            else:
                nonstr.append(".".join(path + [str(k)]))
                _scan_keys(v, path + [str(k)], hits, nonstr)
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            _scan_keys(v, path + [str(i)], hits, nonstr)


def _refuse_forbidden(req):
    hits, nonstr = [], []
    _scan_keys(req, [], hits, nonstr)
    for reason, _keys in _FORBIDDEN:
        matched = sorted(set(k for r, k in hits if r == reason))
        if matched:  # suffix is the first matched TABLE key in sorted order, never request text
            raise ValueError("%s_REFUSED_%s:%s" % (PREFIX, reason, matched[0]))
    if nonstr:  # after the str-key scan, so a forbidden key still wins
        raise _bad("key")


def _bad(name):
    return ValueError("%s_REFUSED_BAD_TYPE:%s" % (PREFIX, name))


def _date(value, name):
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise _bad(name)
    try:
        return _dt.date(int(value[0:4]), int(value[5:7]), int(value[8:10]))
    except ValueError:
        raise _bad(name)


def _num(value, name, low, high, low_open):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _bad(name)
    if isinstance(value, float) and not math.isfinite(value):
        raise _bad(name)
    if (value <= low if low_open else value < low) or value > high:
        raise _bad(name)
    return round(value, 6)


def _scope(as_of):
    return policy.scope(
        ["checklist from supplied requirements and profile", "form-prefill dict",
         "mock scoring of a supplied bank"],
        ["real registration", "login", "real exam attempt", "payment", "sending anything",
         "question content", "readiness claim"],
        "supplied request fields only", as_of)


def _checklist(req, as_of_s, as_of):
    # stage: top types
    ol = req.get("olympiad")
    if not isinstance(ol, dict):
        raise _bad("olympiad")
    reqs = ol.get("requirements")
    if not isinstance(reqs, list):
        raise _bad("requirements")
    profile = req.get("profile")
    if not isinstance(profile, dict):
        raise _bad("profile")
    # stage: caps
    if not reqs:
        raise ValueError("%s_REFUSED_EMPTY:requirements" % PREFIX)
    if len(reqs) > MAX_REQUIREMENTS:
        raise ValueError("%s_REFUSED_OVERSIZE:requirements" % PREFIX)
    # stage: per-field
    name = policy.clean_text(ol.get("name"), PREFIX, "name", 256)
    deadline = _date(ol.get("deadline"), "deadline")
    texts = []
    for r in reqs:
        if not isinstance(r, str):
            raise _bad("requirement")
        texts.append(policy.clean_text(r, PREFIX, "requirement", 256))
    for k, v in profile.items():
        if v is None or isinstance(v, bool) or isinstance(v, int):
            continue
        if isinstance(v, str):
            policy.clean_text(v, PREFIX, "profile", 2000, allow_blank=True)
        elif isinstance(v, float) and math.isfinite(v):
            continue
        else:
            raise _bad("profile")
    # stage: compute
    rows, prefill, excluded = [], {}, set()
    for text in texts:
        key = re.sub(r"\s+", "_", text.strip().casefold())
        if key in _NO_PREFILL:  # credential or government-ID: never done, missing or filled
            excluded.add(key)
            rows.append({"key": key, "requirement": text, "status": "prefill_excluded"})
            continue
        val = profile.get(key)
        have = key in profile and val is not None and not (isinstance(val, str) and not val.strip())
        rows.append({"key": key, "requirement": text, "status": "done" if have else "missing"})
        if have:
            prefill[key] = round(val, 6) if isinstance(val, float) else val
    days = (deadline - as_of).days
    done = sum(1 for r in rows if r["status"] == "done")
    missing = sum(1 for r in rows if r["status"] == "missing")
    return dict(sorted({
        "as_of": as_of_s, "coverage": {"done": done, "missing": missing,
                                        "prefill_excluded": len(rows) - done - missing},
        "days_left": days, "done_count": done,
        "limits": _LIMITS_CHECKLIST, "mode": "checklist",
        "missing_count": missing,
        "olympiad": {"deadline": ol["deadline"], "name": name},
        "prefill": dict(sorted(prefill.items())), "prefill_excluded": sorted(excluded),
        "requirements": rows, "scope": _scope(as_of_s),
        "status": "expired" if days < 0 else "open",
    }.items()))


def _same(given, expected):
    g, e = given.strip(), expected.strip()
    if g == e:
        return True
    return len(g) == 1 and len(e) == 1 and g.isalpha() and e.isalpha() and g.casefold() == e.casefold()


def _mock(req, as_of_s):
    # stage: top types
    bank = req.get("bank")
    if not isinstance(bank, list):
        raise _bad("bank")
    answers = req.get("answers")
    if not isinstance(answers, dict):
        raise _bad("answers")
    # stage: caps
    if not bank:
        raise ValueError("%s_REFUSED_EMPTY:bank" % PREFIX)
    if len(bank) > MAX_BANK:
        raise ValueError("%s_REFUSED_OVERSIZE:bank" % PREFIX)
    for q in bank:
        if isinstance(q, dict) and isinstance(q.get("prompt"), str) and len(q["prompt"]) > MAX_PROMPT:
            raise ValueError("%s_REFUSED_OVERSIZE:prompt" % PREFIX)
    # stage: per-field
    items, seen = [], set()
    for q in bank:
        if not isinstance(q, dict):
            raise _bad("bank")
        qid = policy.clean_text(q.get("id"), PREFIX, "id", 64)
        policy.clean_text(q.get("prompt"), PREFIX, "prompt", MAX_PROMPT)
        ans = policy.clean_text(q.get("answer"), PREFIX, "answer", 256)
        tags = q.get("tags")
        if tags is None:
            tags = []
        if not isinstance(tags, list):
            raise _bad("tags")
        clean = []
        for t in tags:
            t = policy.clean_text(t, PREFIX, "tag", 64)
            if t not in clean:
                clean.append(t)
        if qid in seen:
            raise _bad("bank")
        seen.add(qid)
        items.append((qid, ans, clean or ["untagged"]))
    for k, v in answers.items():
        if not isinstance(k, str):
            raise _bad("answers")
        if not isinstance(v, str):
            raise _bad("answer")
        policy.clean_text(v, PREFIX, "answer", 256, allow_blank=True)
    limit = _num(req.get("time_limit_s"), "time_limit_s", 0, MAX_TIME_LIMIT_S, True)
    elapsed = _num(req.get("elapsed_s"), "elapsed_s", 0, MAX_ELAPSED_S, False)
    results, per, correct, unanswered = [], {}, 0, 0
    for qid, expected, tags in items:
        given = answers.get(qid)
        answered = given is not None and bool(given.strip())
        ok = answered and _same(given, expected)
        results.append({"answered": answered, "correct": ok, "id": qid})
        correct += ok
        unanswered += not answered
        for t in tags:
            row = per.setdefault(t, [0, 0])
            row[1] += 1
            row[0] += ok
    total = len(items)
    return dict(sorted({
        "as_of": as_of_s, "correct": correct, "elapsed_s": elapsed, "limits": _LIMITS_MOCK,
        "mode": "mock", "over_time": elapsed > limit,
        "per_tag": {t: {"correct": c, "score": round(c / n, 6), "total": n}
                    for t, (c, n) in sorted(per.items())},
        "results": results, "score": round(correct / total, 6), "scope": _scope(as_of_s),
        "tag_note": "Multi-tag questions count under each tag, so tag totals can exceed the question total.",
        "time_limit_s": limit, "total": total, "unanswered": unanswered,
        "unknown_answer_ids": sorted(k for k in answers if k not in seen),
    }.items()))


def run(request):
    """Offline prep entry point. Raises ValueError('APPLY_REFUSED_<REASON>[:field]')."""
    if not isinstance(request, dict):
        raise _bad("request")
    _refuse_forbidden(request)
    as_of_s = request.get("as_of")
    as_of = _date(as_of_s, "as_of")
    mode = request.get("mode")
    if not isinstance(mode, str):  # no clean_text, trim, casefold or length cap on mode
        raise _bad("mode")
    if mode not in MODES:
        if mode in policy.RULES:
            policy.check(mode, PREFIX)  # a standing-rule name refuses with its rule code
        raise ValueError("%s_REFUSED_UNKNOWN:mode" % PREFIX)  # field name, never the value
    if mode == "checklist":
        return _checklist(request, as_of_s, as_of)
    return _mock(request, as_of_s)
