"""c35.practice_engine tests (row 100): simulation sessions, scoring,
weakness analytics, study plan, award tracker, live-exam guard."""
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.c35 import practice_engine as pe  # noqa: E402

BANK = [{"id": "q%d" % i, "prompt": "practice %d" % i, "answer": "AB"[i % 2],
         "tags": [["algebra", "geometry"][i % 2]]} for i in range(10)]


def test_session_hides_answers():
    s = pe.new_session(BANK, {"time_limit_s": 600})
    assert s["answers_included"] is False and s["live_exam"] is False
    assert all("answer" not in q for q in s["questions"])


def test_scoring_and_tag_analytics():
    s = pe.new_session(BANK)
    answers = {q["id"]: q["answer"] for q in BANK}
    answers["q0"] = "WRONG"
    r = pe.score_session(BANK, s["session_id"], answers, 500)
    assert r["correct"] == 9 and r["score"] == 0.9
    assert r["per_tag_accuracy"]["geometry"] == 1.0
    assert r["per_tag_accuracy"]["algebra"] == 0.8


def test_history_plan_award_loop():
    s = pe.new_session(BANK)
    answers = {q["id"]: q["answer"] for q in BANK}
    history = {}
    for _ in range(3):
        r = pe.score_session(BANK, s["session_id"], answers, 400)
        pe.update_history(history, r)
    assert history["practice_sessions"] == 3 and history["best_score"] == 1.0
    plan = pe.study_plan(history, "2026-10-12", days=7)
    assert len(plan["plan"]) == 7
    assert plan["basis"] == "practice history only"
    awards = pe.award_tracker(
        [{"id": "a1", "name": "Synthetic Award", "min_practice_score": 0.9,
          "min_sessions": 3, "official_url": "https://example.org/award"},
         {"id": "a2", "name": "Hard Award", "min_practice_score": 1.0,
          "min_sessions": 10, "official_url": "https://example.org/hard"}],
        history)
    ready = {a["id"]: a["practice_ready"] for a in awards["awards"]}
    assert ready == {"a1": True, "a2": False}
    gaps = [a for a in awards["awards"] if a["id"] == "a2"][0]["gaps"]
    assert gaps[0]["metric"] == "practice_sessions"
    assert awards["not_an_award_claim"] is True


def test_live_exam_keys_refused():
    with pytest.raises(ValueError, match="PRACTICE_REFUSED_LIVE_EXAM"):
        pe.new_session(BANK, {"time_limit_s": 600, "live_exam": True})
    with pytest.raises(ValueError, match="PRACTICE_REFUSED_LIVE_EXAM"):
        pe.score_session(BANK, "s", {"q0": "A", "proctor": "x"}, 100)


def test_live_sourced_question_refused():
    bad = BANK + [{"id": "qx", "prompt": "leaked", "answer": "A", "source": "live"}]
    with pytest.raises(ValueError, match="PRACTICE_REFUSED_LIVE_EXAM"):
        pe.new_session(bad)


def test_no_real_exam_claim():
    s = pe.new_session(BANK)
    r = pe.score_session(BANK, s["session_id"], {q["id"]: q["answer"] for q in BANK}, 100)
    assert r["live_exam"] is False
    assert any("never assistance during a live" in l for l in r["limits"])

def test_weakest_first_orders_distinct_accuracies():
    from app.modules.c35 import practice_engine as engine
    out=engine.study_plan({'tags':{'strong':{'accuracy_sum':.9,'sessions':1},'weak':{'accuracy_sum':.2,'sessions':1}}},'2026-10-12',days=2)
    assert out['weakest_first']==['weak','strong']
