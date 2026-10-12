"""c35.practice_engine (doc row 100): olympiad/quiz PRACTICE AND SIMULATION
engine - practice/simulation only, never live-exam assistance.

Builds the legitimate version of "attempt olympiads and win": adaptive timed
mock sessions over SUPPLIED practice banks, per-topic weakness analytics
across sessions, a spaced study plan, and an award-eligibility tracker that
compares PRACTICE metrics against supplied PUBLIC award criteria.

Hard boundaries (enforced in code):
- LIVE_EXAM guard: any request key or question marker indicating a live,
  real, ongoing or proctored exam refuses the whole request.
- Sessions never echo answers back before scoring; question payloads to the
  solver carry no answer field.
- The award tracker reports practice-metric eligibility gaps only. It never
  claims a win, an award, a scholarship or a real exam result.
Stdlib only, offline, deterministic (session ids are content hashes).
"""
from __future__ import annotations

import hashlib
import json
import re

from app.modules.c30 import policy

PREFIX = "PRACTICE"
MAX_BANK = 1000
MAX_SESSIONS = 500
MAX_TAGS = 64
MAX_PLAN_DAYS = 90

_LIVE_KEYS = frozenset({
    "live", "live_exam", "real_exam", "proctor", "proctored", "exam_day",
    "ongoing_exam", "contest_live", "during_exam", "exam_window", "actual_exam",
    "competition_live", "official_attempt", "exam_login"})
_LIVE_SOURCES = frozenset({"live", "real", "real_exam", "live_exam", "ongoing",
                           "current_exam", "proctored", "official_exam"})
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

LIMITS = (
    "Practice and simulation only: never assistance during a live or real exam.",
    "Practice metrics are not olympiad scores and predict no award outcome.",
    "Award eligibility is computed against supplied public criteria only.",
)


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


def _live_guard(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and k.casefold().replace("-", "_") in _LIVE_KEYS:
                _err("LIVE_EXAM", k.casefold())
            _live_guard(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _live_guard(v)


def _check_bank(bank):
    if isinstance(bank, bool) or not isinstance(bank, (list, tuple)) or not bank:
        raise ValueError("%s_REFUSED_BAD_TYPE:bank" % PREFIX)
    if len(bank) > MAX_BANK:
        _err("OVERSIZE")
    out = []
    for q in bank:
        if not isinstance(q, dict):
            raise ValueError("%s_REFUSED_BAD_TYPE:question" % PREFIX)
        src = str(q.get("source", "practice")).strip().lower()
        if src in _LIVE_SOURCES:
            _err("LIVE_EXAM", "question.source")
        qid = policy.clean_text(q.get("id"), PREFIX, "question.id", 64)
        policy.clean_text(q.get("prompt"), PREFIX, "question.prompt", 4000, allow_ws=True)
        ans = q.get("answer")
        if not isinstance(ans, str) or not ans:
            raise ValueError("%s_REFUSED_BAD_TYPE:answer" % PREFIX)
        tags = q.get("tags", [])
        if isinstance(tags, bool) or not isinstance(tags, (list, tuple)) or len(tags) > MAX_TAGS:
            raise ValueError("%s_REFUSED_BAD_TYPE:tags" % PREFIX)
        out.append({"id": qid, "prompt": q["prompt"], "answer": ans,
                    "tags": [policy.clean_text(t, PREFIX, "tag", 64) for t in tags],
                    "difficulty": q.get("difficulty", 1)})
    return out


def new_session(bank, config=None):
    """Start a practice session: returns the question payload WITHOUT answers
    plus a deterministic session id."""
    config = config or {}
    _live_guard(config)
    qs = _check_bank(bank)
    limit = config.get("time_limit_s", 1800)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 60 <= limit <= 86400:
        raise ValueError("%s_REFUSED_BAD_TYPE:time_limit_s" % PREFIX)
    tags_filter = config.get("tags")
    if tags_filter:
        wanted = set(tags_filter)
        qs = [q for q in qs if wanted & set(q["tags"])]
        if not qs:
            _err("EMPTY", "filtered-bank")
    sid = "sess-" + hashlib.sha256(
        json.dumps([q["id"] for q in qs]).encode("utf-8")).hexdigest()[:12]
    return {"session_id": sid, "kind": "practice_simulation",
            "time_limit_s": limit,
            "questions": [{"id": q["id"], "prompt": q["prompt"], "tags": q["tags"],
                           "difficulty": q["difficulty"]} for q in qs],
            "answers_included": False, "live_exam": False, "limits": list(LIMITS)}


def score_session(bank, session_id, answers, elapsed_s):
    """Score a finished practice session; per-tag accuracy included."""
    _live_guard(answers)
    qs = _check_bank(bank)
    if isinstance(answers, bool) or not isinstance(answers, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:answers" % PREFIX)
    if isinstance(elapsed_s, bool) or not isinstance(elapsed_s, (int, float)) or elapsed_s < 0:
        raise ValueError("%s_REFUSED_BAD_TYPE:elapsed_s" % PREFIX)
    by_id = {q["id"]: q for q in qs}
    correct, wrong, unanswered = 0, 0, 0
    per_tag = {}
    for q in qs:
        given = answers.get(q["id"])
        tag_stats = per_tag.setdefault  # noqa: F841 (clarity below)
        for t in q["tags"] or ("untagged",):
            st = per_tag.setdefault(t, {"asked": 0, "correct": 0})
            st["asked"] += 1
            if isinstance(given, str) and given.strip() == q["answer"].strip():
                st["correct"] += 1
        if given is None:
            unanswered += 1
        elif isinstance(given, str) and given.strip() == q["answer"].strip():
            correct += 1
        else:
            wrong += 1
    total = len(qs)
    acc = {t: round(st["correct"] / st["asked"], 4) for t, st in per_tag.items()}
    return {"session_id": session_id, "kind": "practice_simulation",
            "total": total, "correct": correct, "wrong": wrong, "unanswered": unanswered,
            "score": round(correct / total, 4) if total else 0.0,
            "per_tag_accuracy": acc, "elapsed_s": elapsed_s,
            "seconds_per_question": round(elapsed_s / total, 2) if total else None,
            "live_exam": False, "limits": list(LIMITS)}


def update_history(history, result):
    """Fold a scored session into the caller's history dict (rolling per-tag
    accuracy and session count)."""
    if not isinstance(history, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:history" % PREFIX)
    if not isinstance(result, dict) or "per_tag_accuracy" not in result:
        raise ValueError("%s_REFUSED_BAD_TYPE:result" % PREFIX)
    sessions = history.get("sessions", [])
    if len(sessions) >= MAX_SESSIONS:
        _err("OVERSIZE")
    sessions.append({"session_id": result["session_id"], "score": result["score"],
                     "total": result["total"], "correct": result["correct"]})
    tags = history.get("tags", {})
    for tag, acc in result["per_tag_accuracy"].items():
        rec = tags.setdefault(tag, {"sessions": 0, "accuracy_sum": 0.0})
        rec["sessions"] += 1
        rec["accuracy_sum"] += acc
    history["sessions"] = sessions
    history["tags"] = tags
    history["best_score"] = max(s["score"] for s in sessions)
    history["practice_sessions"] = len(sessions)
    return history


def study_plan(history, as_of, days=14):
    """Weakest-tags-first spaced plan over the next `days` days."""
    if not isinstance(history, dict) or "tags" not in history:
        raise ValueError("%s_REFUSED_BAD_TYPE:history" % PREFIX)
    if not isinstance(as_of, str) or not _DATE.fullmatch(as_of):
        raise ValueError("%s_REFUSED_BAD_TYPE:as_of" % PREFIX)
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_PLAN_DAYS:
        raise ValueError("%s_REFUSED_BAD_TYPE:days" % PREFIX)
    ranked = sorted(
        ((rec["accuracy_sum"] / rec["sessions"], tag) for tag, rec in history["tags"].items()
         if rec["sessions"]),
        key=lambda x: (x[0], x[1]))
    if not ranked:
        _err("EMPTY", "history")
    plan = []
    for i in range(days):
        acc, tag = ranked[i % len(ranked)]
        plan.append({"day": i + 1, "focus_tag": tag, "current_practice_accuracy": round(acc, 4),
                     "work": "timed practice set + error review"})
    return {"as_of": as_of, "days": days, "plan": plan,
            "weakest_first": [t for _, t in ranked],
            "basis": "practice history only", "limits": list(LIMITS)}


def award_tracker(criteria, history):
    """Compare PRACTICE metrics against supplied public award criteria.
    criteria = [{"id","name","min_practice_score","min_sessions","official_url"}]."""
    if isinstance(criteria, bool) or not isinstance(criteria, (list, tuple)):
        raise ValueError("%s_REFUSED_BAD_TYPE:criteria" % PREFIX)
    if not isinstance(history, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:history" % PREFIX)
    best = history.get("best_score", 0.0)
    sessions = history.get("practice_sessions", 0)
    rows = []
    for c in criteria:
        if not isinstance(c, dict):
            raise ValueError("%s_REFUSED_BAD_TYPE:criterion" % PREFIX)
        cid = policy.clean_text(c.get("id"), PREFIX, "criterion.id", 64)
        name = policy.clean_text(c.get("name"), PREFIX, "criterion.name", 200)
        url = c.get("official_url")
        if not isinstance(url, str) or not url.startswith("https://"):
            _err("NOSOURCE", cid)
        need_score = c.get("min_practice_score", 0.0)
        need_sessions = c.get("min_sessions", 0)
        gaps = []
        if best < need_score:
            gaps.append({"metric": "best_practice_score", "have": best, "need": need_score})
        if sessions < need_sessions:
            gaps.append({"metric": "practice_sessions", "have": sessions, "need": need_sessions})
        rows.append({"id": cid, "name": name, "official_url": url,
                     "practice_ready": not gaps, "gaps": gaps})
    return {"awards": rows, "basis": "practice metrics vs supplied public criteria",
            "not_an_award_claim": True, "live_exam": False, "limits": list(LIMITS)}
