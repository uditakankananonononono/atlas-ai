"""Polymath career-and-college roadmap builder (pure, stdlib only).

Input is data the student supplies: her own dated evidence per domain, a curriculum graph of steps
with hours, optional cross-domain bridges, and a table of colleges with interdisciplinary flags.
Output is a breadth/depth map, a prerequisite-ordered schedule fitted to her weekly hours, bridge
readiness, and a view of the college table. Nothing is fetched, sent or decided: the module does not
verify the tables, does not predict admission, and makes no claim about her ability.
"""
from __future__ import annotations

import datetime as _dt
import math
import re
from typing import Any

LEVELS = ("beginner", "intermediate", "advanced")
EVIDENCE_KINDS = ("project", "course", "publication", "competition", "other")
FLAG_NAMES = ("open_curriculum", "double_major", "interdisciplinary_major", "research_for_undergrads")
BREADTH_MIN = 3
DEEP_MIN_DATED_EVIDENCE = 2
STALE_DAYS = 365
MAX_WEEKLY_HOURS = 100
MAX_HORIZON_WEEKS = 520
MAX_TEXT = 512
MAX_URL = 2048
MAX_OBJECT_KEYS = 64
MAX_STEP_HOURS = 1_000_000
MIN_WEEKLY_HOURS = 0.000001
LIST_CAPS = {
    'curriculum.domains': 64, 'curriculum.steps': 2048, 'step.after': 256,
    'wanted_domains': 64, 'goals': 64, 'profile.domains': 64, 'evidence': 256,
    'bridges': 256, 'colleges': 256, 'programs': 64,
}
PROVENANCE = "caller-supplied table; not verified by this module"
THRESHOLDS_NOTE = "breadth and depth thresholds are heuristics named in this module, not standards"
BOUNDARY = (
    "This roadmap is computed only from caller-supplied data. It is not a prediction of admission, "
    "it does not verify any college row, source or evidence item, and it makes no claim about ability. "
    "No message was sent and nothing was submitted; any external action needs separate approval."
)


class RoadmapInputError(ValueError):
    def __init__(self, message):
        super().__init__(str(message)[:512])


def _echo(value):
    return repr(value[:128]) if type(value) is str else '<invalid value>'


def _num(v) -> bool:
    return type(v) in (int, float) and -MAX_STEP_HOURS <= v <= MAX_STEP_HOURS and math.isfinite(v)


def _str(v) -> bool:
    return type(v) is str and len(v) <= MAX_TEXT and v.strip() != ""


def _date(v, what) -> _dt.date:
    if type(v) is not str or len(v) != 10 or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", v):
        raise RoadmapInputError(f"{what} must be an ISO date string")
    try:
        return _dt.date.fromisoformat(v)
    except ValueError as e:
        raise RoadmapInputError(f"{what} is not a valid date: {_echo(v)}") from e


def _list(v, what) -> list:
    if type(v) is not list:
        raise RoadmapInputError(f"{what} must be a list")
    if len(v) > LIST_CAPS[what]:
        raise RoadmapInputError(f"{what} exceeds {LIST_CAPS[what]} items")
    return v


def _dict(v, what) -> dict:
    if type(v) is not dict:
        raise RoadmapInputError(f"{what} must be an object")
    if len(v) > MAX_OBJECT_KEYS:
        raise RoadmapInputError(f"{what} exceeds {MAX_OBJECT_KEYS} keys")
    if any(type(k) is not str or len(k) > MAX_TEXT for k in v):
        raise RoadmapInputError(f"{what} has an invalid key")
    return v


def _check_curriculum(cur):
    cur = _dict(cur, "curriculum")
    domains, steps = [], []
    seen = set()
    for d in _list(cur.get("domains"), "curriculum.domains"):
        d = _dict(d, "domain")
        if not (_str(d.get("id")) and _str(d.get("name"))):
            raise RoadmapInputError("each domain needs a non-empty id and name")
        if d["id"] in seen:
            raise RoadmapInputError(f"duplicate domain id {_echo(d['id'])}")
        seen.add(d["id"])
        domains.append({"id": d["id"], "name": d["name"]})
    ids = set()
    for s in _list(cur.get("steps"), "curriculum.steps"):
        s = _dict(s, "step")
        if not (_str(s.get("id")) and _str(s.get("title"))):
            raise RoadmapInputError("each step needs a non-empty id and title")
        if s["id"] in ids:
            raise RoadmapInputError(f"duplicate step id {_echo(s['id'])}")
        ids.add(s["id"])
        if not _str(s.get("domain")) or s["domain"] not in seen:
            raise RoadmapInputError(f"step {_echo(s['id'])} has an unknown domain")
        if not (_num(s.get("hours")) and s["hours"] > 0):
            raise RoadmapInputError(f"step {_echo(s['id'])} hours must be a positive number")
        after = _list(s.get("after", []), "step.after")
        if not all(_str(a) for a in after):
            raise RoadmapInputError("step.after must list step ids")
        steps.append({"id": s["id"], "domain": s["domain"], "title": s["title"], "hours": s["hours"],
                      "after": list(after)})
    for s in steps:
        for a in s["after"]:
            if a not in ids:
                raise RoadmapInputError(f"step {_echo(s['id'])} depends on unknown step {_echo(a)}")
            if a == s["id"]:
                raise RoadmapInputError(f"step {_echo(s['id'])} depends on itself (cycle)")
    _no_cycle(steps)
    return domains, steps


def _no_cycle(steps):
    after = {s["id"]: s["after"] for s in steps}
    state = {}

    for root in after:
        if state.get(root) == 2:
            continue
        stack = [(root, False)]
        while stack:
            n, exiting = stack.pop()
            if exiting:
                state[n] = 2
                continue
            if state.get(n) == 1:
                raise RoadmapInputError("curriculum steps contain a cycle")
            if state.get(n) == 2:
                continue
            state[n] = 1
            stack.append((n, True))
            for dependency in reversed(after[n]):
                stack.append((dependency, False))


def _check_profile(p, domain_ids, today):
    p = _dict(p, "profile")
    wh = p.get("weekly_hours")
    if not (_num(wh) and MIN_WEEKLY_HOURS <= wh <= MAX_WEEKLY_HOURS):
        raise RoadmapInputError(f"weekly_hours must be a number from {MIN_WEEKLY_HOURS} to {MAX_WEEKLY_HOURS}")
    wanted = _list(p.get("wanted_domains"), "wanted_domains")
    if not all(_str(w) for w in wanted) or len(set(wanted)) != len(wanted):
        raise RoadmapInputError("wanted_domains must be unique domain ids")
    for w in wanted:
        if w not in domain_ids:
            raise RoadmapInputError(f"wanted domain {_echo(w)} is not in the curriculum")
    goals = _list(p.get("goals", []), "goals")
    if not all(_str(g) for g in goals):
        raise RoadmapInputError("goals must be a list of non-empty strings")
    rows = {}
    for row in _list(p.get("domains"), "profile.domains"):
        row = _dict(row, "profile domain")
        did = row.get("domain")
        if not _str(did) or did not in domain_ids:
            raise RoadmapInputError(f"profile domain {_echo(did)} is not in the curriculum")
        if did in rows:
            raise RoadmapInputError(f"profile domain {_echo(did)} listed twice")
        if not _str(row.get("level")) or row["level"] not in LEVELS:
            raise RoadmapInputError(f"level for {_echo(did)} must be one of {LEVELS}")
        evs = []
        for e in _list(row.get("evidence"), "evidence"):
            e = _dict(e, "evidence item")
            if not _str(e.get("title")):
                raise RoadmapInputError("evidence needs a non-empty title")
            if not _str(e.get("kind")) or e["kind"] not in EVIDENCE_KINDS:
                raise RoadmapInputError(f"evidence kind must be one of {EVIDENCE_KINDS}")
            evs.append(_date(e.get("date"), "evidence date"))
        rows[did] = (row["level"], evs)
    return wh, list(wanted), list(goals), rows


def _tier(level, n):
    if n == 0:
        return "none"
    if level == "advanced" and n >= DEEP_MIN_DATED_EVIDENCE:
        return "deep"
    if level in ("intermediate", "advanced"):
        return "developing"
    return "started"


def _pattern(evidenced, deep):
    if evidenced == 0:
        return "no_evidence"
    if evidenced == 1:
        return "single_domain"
    if deep >= 2:
        return "multi_deep"
    if deep == 1:
        return "t_shaped" if evidenced >= BREADTH_MIN else "one_deep_few_others"
    return "broad_shallow"


def _schedule(steps, wanted, domain_order, weekly_hours, horizon):
    by_id = {s["id"]: s for s in steps}
    need = set()

    direct = {s["id"] for s in steps if s["domain"] in wanted}
    stack = list(direct)
    while stack:
        sid = stack.pop()
        if sid in need:
            continue
        need.add(sid)
        stack.extend(by_id[sid]["after"])
    rank = {d: i for i, d in enumerate(list(wanted) + [d for d in domain_order if d not in wanted])}
    pool = [s for s in steps if s["id"] in need]
    pool_domains = sorted({s["domain"] for s in pool}, key=lambda d: rank[d])
    done, order = set(), []
    while len(done) < len(pool):
        progressed = False
        for d in pool_domains:
            for s in pool:
                if s["domain"] == d and s["id"] not in done and all(a in done for a in s["after"]):
                    done.add(s["id"])
                    order.append(s)
                    progressed = True
                    break
        if not progressed:
            raise RoadmapInputError("curriculum steps contain a cycle")
    out, unscheduled, cum, total = [], [], 0.0, 0.0
    for s in order:
        start = int(math.floor(cum / weekly_hours + 1e-9)) + 1
        cum += s["hours"]
        end = max(start, int(math.ceil(cum / weekly_hours - 1e-9)))
        total += s["hours"]
        if end > horizon:
            unscheduled.append({"id": s["id"], "reason": "beyond_horizon"})
            continue
        out.append({"id": s["id"], "domain": s["domain"], "title": s["title"], "hours": s["hours"],
                    "start_week": start, "end_week": end,
                    "pulled_in_as_prerequisite": s["id"] not in direct})
    return {"weekly_hours": weekly_hours, "horizon_weeks": horizon, "steps": out,
            "unscheduled": unscheduled, "total_hours": _clean(total)}


def _clean(x):
    return int(x) if float(x).is_integer() else x


def _check_bridges(bridges, domain_ids):
    out = []
    for b in _list(bridges, "bridges"):
        b = _dict(b, "bridge")
        if not _str(b.get("a")) or not _str(b.get("b")) or b["a"] not in domain_ids or b["b"] not in domain_ids or b["a"] == b["b"]:
            raise RoadmapInputError("a bridge needs two different known domains")
        if not _str(b.get("theme")):
            raise RoadmapInputError("a bridge needs a non-empty theme")
        out.append((b["a"], b["b"], b["theme"]))
    return out


def _check_colleges(colleges, domain_ids, today):
    out, seen = [], set()
    for c in _list(colleges, "colleges"):
        c = _dict(c, "college")
        if not (_str(c.get("id")) and _str(c.get("name")) and _str(c.get("country"))):
            raise RoadmapInputError("each college needs a non-empty id, name and country")
        if c["id"] in seen:
            raise RoadmapInputError(f"duplicate college id {_echo(c['id'])}")
        seen.add(c["id"])
        url = c.get("source_url")
        if not (type(url) is str and len(url) <= MAX_URL and url.startswith("https://") and len(url) > len("https://")):
            raise RoadmapInputError("source_url must be an https URL")
        checked = _date(c.get("checked_at"), "checked_at")
        if checked > today:
            raise RoadmapInputError("checked_at is in the future")
        f = _dict(c.get("flags"), "flags")
        if set(f) != set(FLAG_NAMES) or not all(type(v) is bool for v in f.values()):
            raise RoadmapInputError(f"flags must be exactly {FLAG_NAMES} with boolean values")
        progs = _list(c.get("programs"), "programs")
        if not all(_str(p) and p in domain_ids for p in progs):
            raise RoadmapInputError("programs must be known domain ids")
        out.append((c, checked, f, list(progs)))
    return out


def build_roadmap(profile, curriculum, bridges, colleges, today, horizon_weeks: int = 104) -> dict:
    if type(today) is not _dt.date:
        raise RoadmapInputError("today must be a datetime.date")
    if type(horizon_weeks) is not int or not 0 < horizon_weeks <= MAX_HORIZON_WEEKS:
        raise RoadmapInputError(f"horizon_weeks must be an int from 1 to {MAX_HORIZON_WEEKS}")
    domains, steps = _check_curriculum(curriculum)
    domain_ids = [d["id"] for d in domains]
    weekly, wanted, goals, rows = _check_profile(profile, set(domain_ids), today)
    bridge_rows = _check_bridges(bridges, set(domain_ids))
    college_rows = _check_colleges(colleges, set(domain_ids), today)

    dom_out, dated = [], {}
    for d in domains:
        level, evs = rows.get(d["id"], (None, []))
        n = sum(1 for e in evs if e <= today)
        dated[d["id"]] = n
        dom_out.append({"id": d["id"], "name": d["name"], "level": level, "evidence_count": len(evs),
                        "dated_evidence_count": n, "future_dated_evidence_count": len(evs) - n,
                        "depth_tier": _tier(level, n)})
    evidenced = sum(1 for d in dom_out if d["dated_evidence_count"] >= 1)
    deep = sum(1 for d in dom_out if d["depth_tier"] == "deep")

    bridge_out = []
    for a, b, theme in bridge_rows:
        missing = [x for x in (a, b) if dated[x] == 0]
        bridge_out.append({"a": a, "b": b, "theme": theme, "status": "ready" if not missing else "needs",
                           "missing": missing})

    col_out = []
    for c, checked, f, progs in college_rows:
        true_flags = [k for k in FLAG_NAMES if f[k]]
        age = (today - checked).days
        col_out.append({"id": c["id"], "name": c["name"], "country": c["country"], "source_url": c["source_url"],
                        "checked_at": c["checked_at"], "age_days": age, "stale": age > STALE_DAYS,
                        "flag_count": len(true_flags), "flags_true": true_flags,
                        "covered_wanted": [w for w in wanted if w in progs],
                        "missing_wanted": [w for w in wanted if w not in progs],
                        "provenance": PROVENANCE})
    col_out.sort(key=lambda r: (-len(r["covered_wanted"]), -r["flag_count"], r["id"]))

    return {
        "boundary": BOUNDARY,
        "requires_approval_before_any_external_action": True,
        "makes_ability_claim": False,
        "goals": goals,
        "domains": dom_out,
        "shape": {"evidenced_domains": evidenced, "deep_domains": deep, "pattern": _pattern(evidenced, deep),
                  "thresholds": {"breadth_min": BREADTH_MIN, "deep_min_dated_evidence": DEEP_MIN_DATED_EVIDENCE},
                  "thresholds_note": THRESHOLDS_NOTE},
        "gaps": {"wanted_without_evidence": [w for w in wanted if dated[w] == 0]},
        "schedule": _schedule(steps, wanted, domain_ids, weekly, horizon_weeks),
        "bridges": bridge_out,
        "colleges": col_out,
    }
