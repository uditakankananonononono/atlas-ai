"""Row698 scoped trunk-based-development analysis over supplied commit records.

Pure stdlib. Computes reachability, merge bases, divergence, branch age and
required-check coverage bound to exact tip SHAs from caller-supplied commit,
branch and check records. It never talks to git or GitHub, mutates nothing, and
cannot show that branch protection exists (see LIMITS).
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any

MAX_COMMITS = 2000
MAX_BRANCHES = 64
MAX_CHECKS = 512
MAX_REQUIRED = 16
MAX_PARENTS = 8
MAX_NAME = 100
MAX_SOURCE_REF = 200
MAX_AGE_HOURS = 8760

LIMITS = [
    "Analyzes only the supplied commit, branch and check records; nothing is read from git or GitHub, so record accuracy is the caller's claim.",
    "Does not verify, enable or change GitHub branch protection or any protected-branch rule; branch_protection_verified is always false and trunk is never mutated.",
    "Branch age is reference_time minus the oldest commit unique to the branch (not branch creation time); commit timestamps are caller-supplied author/committer claims.",
    "Check coverage is exact-SHA only: a pass on an ancestor, descendant or sibling never covers a tip. Check provenance and runner trust are not verified.",
    "Not a merge-readiness or release decision; human review is still required.",
]

_SHA = re.compile(r"^[0-9a-f]{40}$")
_BRANCH = re.compile(rf"^[A-Za-z0-9._/-]{{1,{MAX_NAME}}}$")
_CHECK = re.compile(rf"^[A-Za-z0-9._/ -]{{1,{MAX_NAME}}}$")
_TS = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$", re.ASCII)
_CONCLUSIONS = {"success": "passed", "failure": "failed", "cancelled": "failed", "timed_out": "failed",
                "skipped": "not_success", "neutral": "not_success", "pending": "pending"}


def _fail(msg: str):
    raise ValueError(msg)


def _ts(v, label):
    err = f"timestamp {label} must be ISO-8601 with explicit UTC offset"
    m = _TS.fullmatch(v) if isinstance(v, str) else None
    if not m:
        _fail(err)
    y, mo, d, h, mi, s, frac, tz = m.groups()
    try:
        if tz == "Z":
            off = timedelta(0)
        else:
            oh, om = int(tz[1:3]), int(tz[4:6])
            if oh > 23 or om > 59:
                raise ValueError
            off = timedelta(hours=oh, minutes=om) * (1 if tz[0] == "+" else -1)
        micro = int((frac or "0").ljust(6, "0"))
        dt = datetime(int(y), int(mo), int(d), int(h), int(mi), int(s), micro, tzinfo=timezone(off))
    except ValueError:
        _fail(err)
    return dt.astimezone(timezone.utc)


def _fmt(dt):
    s = dt.strftime("%Y-%m-%dT%H:%M:%S")
    if dt.microsecond:
        s += f".{dt.microsecond:06d}"
    return s + "Z"


def _us(delta):
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def _text(v, label):
    if not isinstance(v, str) or not v.strip():
        _fail(f"{label} must be a non-blank string")
    if len(v) > MAX_SOURCE_REF:
        _fail(f"{label} exceeds {MAX_SOURCE_REF} characters")
    return v


def _keys(d, allowed, label):
    for k in d:
        if k not in allowed:
            _fail(f"unknown key {k!r} in {label}")


def _list(v, label, nonempty):
    if not isinstance(v, list) or (nonempty and not v):
        _fail(f"{label} must be a{' non-empty' if nonempty else ''} list")
    return v


def _sha(v):
    if not isinstance(v, str) or not _SHA.fullmatch(v):
        _fail(f"invalid sha {v!r}")
    return v


def _bits(x):
    return x.bit_count()


def analyze_trunk(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        _fail("request must be an object")
    _keys(data, {"source_ref", "trunk", "reference_time", "max_branch_age_hours", "required_checks",
                 "commits", "branches", "checks"}, "request")
    top_ref = _text(data.get("source_ref"), "source_ref")
    trunk = data.get("trunk")
    if not isinstance(trunk, str) or not _BRANCH.fullmatch(trunk):
        _fail(f"invalid trunk name {trunk!r}")
    ref = _ts(data.get("reference_time"), "reference_time")
    thr = data.get("max_branch_age_hours")
    if (type(thr) not in (int, float) or not math.isfinite(thr) or not 0 < thr <= MAX_AGE_HOURS):
        _fail(f"max_branch_age_hours must be a finite number in (0, {MAX_AGE_HOURS}]")
    thr_us = Fraction(thr) * 3_600_000_000

    req = _list(data.get("required_checks"), "required_checks", True)
    if len(req) > MAX_REQUIRED:
        _fail(f"required_checks exceed {MAX_REQUIRED}")
    for n in req:
        if not isinstance(n, str) or not _CHECK.fullmatch(n):
            _fail(f"invalid check name {n!r}")
    if len(set(req)) != len(req):
        dup = next(n for n in req if req.count(n) > 1)
        _fail(f"required_checks has duplicate name {dup!r}")
    req = sorted(req)

    raw_commits = _list(data.get("commits"), "commits", True)
    if len(raw_commits) > MAX_COMMITS:
        _fail(f"commits exceed {MAX_COMMITS}")
    raw_branches = _list(data.get("branches"), "branches", True)
    if len(raw_branches) > MAX_BRANCHES:
        _fail(f"branches exceed {MAX_BRANCHES}")
    raw_checks = _list(data.get("checks"), "checks", False)
    if len(raw_checks) > MAX_CHECKS:
        _fail(f"checks exceed {MAX_CHECKS}")

    # ---- commits: parse ----
    commits: dict[str, dict] = {}
    trace = []
    for i, c in enumerate(raw_commits):
        if not isinstance(c, dict):
            _fail(f"commit {i} must be an object")
        label = f"commit {c['sha'] if isinstance(c.get('sha'), str) else i}"
        _keys(c, {"sha", "parents", "committed_at", "source_ref"}, label)
        sha = _sha(c.get("sha"))
        parents = c.get("parents")
        if not isinstance(parents, list):
            _fail(f"parents of commit {sha} must be a list")
        if len(parents) > MAX_PARENTS:
            _fail(f"commit {sha} parents exceed {MAX_PARENTS}")
        for p in parents:
            _sha(p)
        if len(set(parents)) != len(parents):
            dup = next(p for p in parents if parents.count(p) > 1)
            _fail(f"duplicate parent {dup} in commit {sha}")
        when = _ts(c.get("committed_at"), f"commit {sha} committed_at")
        rec = {"parents": sorted(parents), "at": when}
        if sha in commits:
            _fail(f"{'duplicate' if commits[sha] == rec else 'conflicting duplicate'} commit {sha}")
        commits[sha] = rec
        src = _text(c["source_ref"], f"commit {sha} source_ref") if "source_ref" in c else top_ref
        trace.append({"kind": "commit", "id": sha, "source_ref": src})

    shas = sorted(commits)
    idx = {s: i for i, s in enumerate(shas)}
    for s in shas:
        for p in commits[s]["parents"]:
            if p not in commits:
                _fail(f"unknown parent {p} of commit {s}")

    # ---- topological order (Kahn) + cycle refusal ----
    indeg = {s: len(commits[s]["parents"]) for s in shas}
    children: dict[str, list] = {s: [] for s in shas}
    for s in shas:
        for p in commits[s]["parents"]:
            children[p].append(s)
    ready = [s for s in shas if indeg[s] == 0]
    order = []
    while ready:
        s = ready.pop()
        order.append(s)
        for ch in children[s]:
            indeg[ch] -= 1
            if indeg[ch] == 0:
                ready.append(ch)
    if len(order) != len(shas):
        _fail("cycle detected in commit graph")

    # ---- clocks ----
    for s in shas:
        if commits[s]["at"] > ref:
            _fail(f"commit {s} is after reference_time")
    for s in shas:
        for p in commits[s]["parents"]:
            if commits[s]["at"] < commits[p]["at"]:
                _fail(f"commit {s} is older than its parent {p} (ambiguous clock)")

    anc: dict[str, int] = {}
    for s in order:
        a = 1 << idx[s]
        for p in commits[s]["parents"]:
            a |= anc[p]
        anc[s] = a

    # ---- branches ----
    branches: dict[str, str] = {}
    for b in raw_branches:
        if not isinstance(b, dict):
            _fail("branch must be an object")
        name = b.get("name")
        _keys(b, {"name", "tip", "source_ref"}, f"branch {name}")
        if not isinstance(name, str) or not _BRANCH.fullmatch(name):
            _fail(f"invalid branch name {name!r}")
        if name in branches:
            _fail(f"duplicate branch {name}")
        tip = _sha(b.get("tip"))
        if tip not in commits:
            _fail(f"unknown tip {tip} for branch {name}")
        branches[name] = tip
        src = _text(b["source_ref"], f"branch {name} source_ref") if "source_ref" in b else top_ref
        trace.append({"kind": "branch", "id": name, "source_ref": src})
    if trunk not in branches:
        _fail(f"trunk branch {trunk} not in branches")

    # ---- checks ----
    checks: dict[tuple, str] = {}
    full: dict[tuple, dict] = {}
    for c in raw_checks:
        if not isinstance(c, dict):
            _fail("check must be an object")
        name, sha = c.get("name"), c.get("sha")
        label = f"check {name}@{sha}"
        _keys(c, {"name", "sha", "conclusion", "completed_at", "source_ref"}, label)
        if not isinstance(name, str) or not _CHECK.fullmatch(name):
            _fail(f"invalid check name {name!r}")
        _sha(sha)
        if sha not in commits:
            _fail(f"unknown sha {sha} in check {name}")
        concl = c.get("conclusion")
        if not isinstance(concl, str) or concl not in _CONCLUSIONS:
            _fail(f"{label} has unsupported conclusion {concl!r}")
        done = None
        if "completed_at" in c:
            done = _ts(c["completed_at"], f"{label} completed_at")
            if done > ref:
                _fail(f"{label} completed_at is after reference_time")
            if done < commits[sha]["at"]:
                _fail(f"{label} completed_at precedes its commit")
        rec = {"conclusion": concl, "done": done}
        if (name, sha) in full:
            _fail(f"{'duplicate' if full[(name, sha)] == rec else 'conflicting duplicate'} check record {name}@{sha}")
        full[(name, sha)] = rec
        checks[(name, sha)] = _CONCLUSIONS[concl]
        src = _text(c["source_ref"], f"{label} source_ref") if "source_ref" in c else top_ref
        trace.append({"kind": "check", "id": f"{name}@{sha}", "source_ref": src})

    def coverage(tip):
        out, ok = {}, True
        for n in req:
            status = checks.get((n, tip), "missing")
            stale = sorted(s for (cn, s) in checks if cn == n and s != tip and anc[tip] >> idx[s] & 1)
            out[n] = {"status": status, "stale_ancestor_shas": stale}
            ok &= status == "passed"
        return out, ok

    ttip = branches[trunk]
    out_branches = []
    for name in sorted(branches):
        tip = branches[name]
        cov, ok = coverage(tip)
        ahead_bits = anc[tip] & ~anc[ttip]
        behind_bits = anc[ttip] & ~anc[tip]
        common = anc[tip] & anc[ttip]
        covered_by_other = 0
        for s in shas:
            if common >> idx[s] & 1:
                covered_by_other |= anc[s] & ~(1 << idx[s])
        bases = [s for s in shas if (common & ~covered_by_other) >> idx[s] & 1]
        unmerged = [s for s in shas if ahead_bits >> idx[s] & 1]
        ahead, behind = len(unmerged), _bits(behind_bits)
        if name == trunk:
            state = "trunk"
        elif ahead == 0:
            state = "merged"
        elif not bases:
            state = "unrelated"
        else:
            state = "diverged" if behind else "ahead"
        oldest = min((commits[s]["at"] for s in unmerged), default=None)
        age_us = _us(ref - oldest) if oldest else 0
        stale = bool(oldest) and name != trunk and Fraction(age_us) > thr_us
        out_branches.append({
            "name": name, "tip": tip, "state": state, "ahead": ahead, "behind": behind,
            "merge_bases": bases, "unmerged_commits": unmerged,
            "merge_commits_in_unmerged": [s for s in unmerged if len(commits[s]["parents"]) > 1],
            "oldest_unmerged_commit_at": _fmt(oldest) if oldest else None,
            "age_seconds": age_us // 1_000_000 if age_us % 1_000_000 == 0 else age_us / 1_000_000,
            "stale": stale,
            "required_checks": cov, "required_checks_covered": ok,
        })
    tb = next(b for b in out_branches if b["name"] == trunk)
    reach = 0
    for t in branches.values():
        reach |= anc[t]
    trace.sort(key=lambda t: (t["kind"], t["id"]))
    return {
        "reference_time": _fmt(ref),
        "trunk": {"name": trunk, "tip": ttip, "commit_count": _bits(anc[ttip]),
                  "required_checks": tb["required_checks"], "required_checks_covered": tb["required_checks_covered"]},
        "branches": out_branches,
        "stale_branches": [b["name"] for b in out_branches if b["stale"]],
        "unreachable_commits": [s for s in shas if not reach >> idx[s] & 1],
        "source_trace": trace,
        "branch_protection_verified": False,
        "main_mutated": False,
        "limits": list(LIMITS),
    }
