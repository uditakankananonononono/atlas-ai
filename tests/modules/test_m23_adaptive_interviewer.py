"""Adaptive interviewer: grounding, labeling and fallback behavior (fake provider = unit tests only).

The fake provider proves the guards and labels. Real-model behavior is verified separately by
scripts/verification/esai_interview_real_model.py against a local llama.cpp server.
"""
import pytest
from instinct_models import ChatResult, Provider, ProviderUnavailable, Router
from instinct_models.providers import LOCAL, HOSTED
from app.modules.m23_study_abroad.adaptive_interviewer import (
    ADAPTIVE, FALLBACK, AdaptiveInterviewer, check_question, interviewer_from_env, parse_extraction)
from app.modules.m23_study_abroad.interview import IdentityInterviewRepository, QUESTIONS
from app.modules.m23_study_abroad.story import BrandIdRow
from app.core.database import SessionLocal

ANSWER = "I started a robotics club at my school because nobody else would, and I taught 12 younger kids to solder."


class Fake(Provider):
    name, locality = "fake-local", LOCAL
    def __init__(self, question, extraction, fail=False):
        self.question, self.extraction, self.fail, self.calls = question, extraction, fail, []
    def available(self): return True
    def chat(self, messages, *, tools=None, max_tokens=1024):
        self.calls.append(messages)
        if self.fail:
            raise ProviderUnavailable("down")
        text = self.extraction if "KIND |" in messages[0]["content"] else self.question
        return ChatResult(self.name, "fake-model", text, [], {})


def test_check_question_rejects_non_questions_and_drafts():
    assert check_question("What made you choose to teach the younger kids?", []) == "What made you choose to teach the younger kids?"
    assert check_question("Tell me more.", []) is None
    assert check_question("Dear admissions committee, I am a robotics leader?", []) is None
    assert check_question("What is that? And why?", []) is None
    q = "What made you start it?"
    assert check_question(q, [q]) is None


def test_extraction_keeps_only_verbatim_quotes():
    text = ('strength | initiative | "started a robotics club at my school"\n'
            'value | generosity | "taught 12 younger kids to solder"\n'
            'pattern | invented | "won a national championship"\n'
            'garbage line\n'
            'strength | initiative | "started a robotics club at my school"')
    kept, rejected = parse_extraction(text, ANSWER)
    assert [k["label"] for k in kept] == ["initiative", "generosity"]
    assert {r["reason"] for r in rejected} >= {"quote is not verbatim in the student's answer", "not KIND | label | quote", "duplicate"}


def _repo(tenant, provider):
    return IdentityInterviewRepository(tenant, interviewer=AdaptiveInterviewer(Router([provider])))


def test_model_backed_turn_is_labeled_and_brand_uses_only_grounded_items():
    p = Fake("What made you decide to teach the younger kids?",
             'strength | initiative | "started a robotics club at my school"\nvalue | fame | "became famous at school"')
    repo = _repo("adaptive-a", p)
    s = repo.start("college")
    assert s["next_question"] == QUESTIONS[0] and s["next_question_source"] == "fixed_script_opening"
    out = repo.answer(s["id"], ANSWER)
    assert out["next_question"] == "What made you decide to teach the younger kids?"
    assert out["next_question_source"] == ADAPTIVE
    assert out["interviewer"]["model_backed_turns"] == [1]
    assert out["interviewer"]["turns"][0]["grounded_items"] == 1 and out["interviewer"]["turns"][0]["rejected_items"] == 1
    # the stored turn-2 question is the adaptive one
    out2 = repo.answer(s["id"], "Honestly because I remembered how lost I felt in seventh grade.")
    assert out2["turns"][1]["question"] == "What made you decide to teach the younger kids?"
    with SessionLocal() as db:
        brand = db.get(BrandIdRow, "adaptive-a")
        assert "initiative" in brand.strengths and "fame" not in brand.values
        grounded = [e for e in brand.evidence if e.get("provenance")]
        assert grounded and grounded[0]["quote"] == "started a robotics club at my school"
        assert brand.evidence[0]["student_response"] == ANSWER


def test_bad_model_question_falls_back_and_says_so():
    repo = _repo("adaptive-b", Fake("Tell me about yourself", ""))
    s = repo.start("college")
    out = repo.answer(s["id"], ANSWER)
    assert out["next_question"] == QUESTIONS[1] and out["next_question_source"] == FALLBACK
    assert "failed shape checks" in out["interviewer"]["turns"][0]["detail"]


def test_model_down_is_unmistakably_fallback_and_extracts_nothing():
    repo = _repo("adaptive-c", Fake("", "", fail=True))
    s = repo.start("career")
    out = repo.answer(s["id"], ANSWER, evidence_tags=["strength:leadership"])
    t = out["interviewer"]["turns"][0]
    assert out["next_question_source"] == FALLBACK and t["extraction_mode"] == "none_no_model" and t["grounded_items"] == 0
    assert out["interviewer"]["model_backed_turns"] == []
    with SessionLocal() as db:
        assert "leadership" in db.get(BrandIdRow, "adaptive-c").strengths   # caller tags still honored


def test_no_interviewer_is_labeled_fixed_script_not_adaptive():
    s = IdentityInterviewRepository("adaptive-d").start("college")
    assert s["interviewer"]["adaptive_enabled"] is False and "not adaptive" in s["interviewer"]["label"]


def test_private_task_never_reaches_hosted_route():
    class Hosted(Fake):
        locality = HOSTED
        name = "fake-hosted"
    h = Hosted("What made you start it?", "")
    interviewer = AdaptiveInterviewer(Router([h]))
    step = interviewer.step(track="college", turns=[{"question": QUESTIONS[0], "student_response": ANSWER}],
                            fixed_next=QUESTIONS[1], want_question=True)
    assert h.calls == [] and step.question_source == FALLBACK


def test_interviewer_from_env_requires_loopback():
    assert interviewer_from_env({}) is None
    assert interviewer_from_env({"INSTINCT_ORNITH_URL": "https://api.example.com/v1", "INSTINCT_ORNITH_MODEL": "m"}) is None
    assert interviewer_from_env({"INSTINCT_ORNITH_URL": "http://127.0.0.1:8089/v1", "INSTINCT_ORNITH_MODEL": "m"}) is not None
