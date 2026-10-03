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
    text = ('strength | robotics club | "started a robotics club at my school"\n'
            'value | younger kids | "taught 12 younger kids to solder"\n'
            'pattern | invented | "won a national championship"\n'
            'garbage line\n'
            'strength | robotics club | "started a robotics club at my school"')
    kept, rejected = parse_extraction(text, ANSWER)
    assert [k["label"] for k in kept] == ["robotics club", "younger kids"]
    assert {r["reason"] for r in rejected} >= {"quote is not an exact copy from the student's answer", "not KIND | label | quote", "duplicate"}
    assert all(k["status"] == "proposed_unverified" and k["student_confirmed"] is False for k in kept)


def test_quote_must_be_exact_not_case_or_punctuation_normalized_and_label_words_must_be_said():
    kept, rej = parse_extraction('strength | robotics club | "STARTED a robotics club at my school"\n'
                                 'strength | leadership skills | "started a robotics club at my school"\n'
                                 'value | younger kids | "taught 12 younger kids to solder"', ANSWER)
    assert [k["label"] for k in kept] == ["younger kids"]  # case change and unsaid-word label both rejected
    assert len(rej) == 2


def test_question_introducing_unsaid_facts_or_leading_is_rejected():
    conv = ANSWER + " What experience shaped you?"
    assert check_question("What was it like when you taught the younger kids to solder?", [], conv)
    assert check_question("How did the radio project inspire you to pursue a career in technology?", [], conv) is None
    assert check_question("What was hardest about teaching the kids chemistry?", [], conv) is None


def _repo(tenant, provider):
    return IdentityInterviewRepository(tenant, interviewer=AdaptiveInterviewer(Router([provider])))


def test_model_backed_turn_is_labeled_and_brand_uses_only_grounded_items():
    p = Fake("What was it like when you taught the younger kids?",
             'strength | robotics club | "started a robotics club at my school"\nvalue | famous school | "became famous at school"')
    repo = _repo("adaptive-a", p)
    s = repo.start("college")
    assert s["next_question"] == QUESTIONS[0] and s["next_question_source"] == "fixed_script_opening"
    out = repo.answer(s["id"], ANSWER)
    assert out["next_question"] == "What was it like when you taught the younger kids?"
    assert out["next_question_source"] == ADAPTIVE
    assert out["interviewer"]["model_backed_turns"] == [1]
    assert out["interviewer"]["turns"][0]["proposed_items"] == 1 and out["interviewer"]["turns"][0]["rejected_items"] == 1
    # the stored turn-2 question is the adaptive one
    out2 = repo.answer(s["id"], "Honestly because I remembered how lost I felt in seventh grade.")
    assert out2["turns"][1]["question"] == "What was it like when you taught the younger kids?"
    with SessionLocal() as db:
        brand = db.get(BrandIdRow, "adaptive-a")
        assert "robotics club" not in brand.strengths and "famous school" not in brand.values  # unconfirmed proposals are evidence only
        grounded = [e for e in brand.evidence if e.get("provenance")]
        assert grounded and grounded[0]["quote"] == "started a robotics club at my school"
        assert brand.evidence[0]["student_response"] == ANSWER
        assert "NOT yet confirmed" in grounded[0]["provenance"]
    repo.confirm_insight(s["id"], 1, 0, True)
    with SessionLocal() as db:
        assert "robotics club" in db.get(BrandIdRow, "adaptive-a").strengths


def test_bad_model_question_falls_back_and_says_so():
    repo = _repo("adaptive-b", Fake("Tell me about yourself", ""))
    s = repo.start("college")
    out = repo.answer(s["id"], ANSWER)
    assert out["next_question"] == QUESTIONS[1] and out["next_question_source"] == FALLBACK
    assert "failed lexical grounding checks" in out["interviewer"]["turns"][0]["detail"]


def test_model_down_is_unmistakably_fallback_and_extracts_nothing():
    repo = _repo("adaptive-c", Fake("", "", fail=True))
    s = repo.start("career")
    out = repo.answer(s["id"], ANSWER, evidence_tags=["strength:leadership"])
    t = out["interviewer"]["turns"][0]
    assert out["next_question_source"] == FALLBACK and t["extraction_mode"] == "none_no_model" and t["proposed_items"] == 0
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


def test_provider_exception_is_labeled_fallback_not_a_500_and_turn_is_kept():
    class Boom(Fake):
        def chat(self, messages, *, tools=None, max_tokens=1024):
            raise KeyError("malformed json shape")
    repo = _repo("adaptive-e", Boom("", ""))
    s = repo.start("college")
    out = repo.answer(s["id"], ANSWER)
    assert out["turns"][0]["student_response"] == ANSWER and out["next_question_source"] == FALLBACK
    assert "KeyError" in out["interviewer"]["turns"][0]["detail"]


def test_second_answer_to_same_question_is_rejected():
    from app.modules.m23_study_abroad.interview import ConcurrentAnswerError
    from sqlalchemy import update
    from app.modules.m23_study_abroad.interview import IdentityInterviewRow
    repo = _repo("adaptive-f", Fake("", ""))
    s = repo.start("college")
    repo.answer(s["id"], ANSWER)
    # simulate a racer that read question_index=0: rewind then both CAS against stale index via direct call
    with repo.sessions.begin() as db:
        db.execute(update(IdentityInterviewRow).where(IdentityInterviewRow.id == s["id"]).values(question_index=0))
    # a stale writer is modelled by an unmatched expectation: status complete blocks, index mismatch raises
    with repo.sessions.begin() as db:
        db.execute(update(IdentityInterviewRow).where(IdentityInterviewRow.id == s["id"]).values(question_index=1))
    out = repo.answer(s["id"], "A second distinct answer for question two.")
    assert [t["ordinal"] for t in out["turns"]] == [1, 2]
    assert ConcurrentAnswerError  # exported for the route's 409 mapping


def test_threaded_answers_one_wins_ordinals_unique():
    import threading
    repo = _repo("adaptive-g", Fake("", ""))
    s = repo.start("college")
    results = []
    def go(i):
        try:
            repo.answer(s["id"], f"Distinct answer number {i} about my robotics work.")
            results.append("ok")
        except ValueError:
            results.append("conflict")
    ts = [threading.Thread(target=go, args=(i,)) for i in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    out = repo.get(s["id"])
    ords = [t["ordinal"] for t in out["turns"]]
    assert ords == sorted(set(ords)) and len(ords) == results.count("ok") >= 1


def test_loopback_transport_refuses_redirects_and_nonloopback():
    import http.server, threading
    from instinct_models import ProviderError, ProviderUnavailable
    from app.modules.m23_study_abroad.adaptive_interviewer import _post_loopback
    hits = []
    class R(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            hits.append(self.path); self.send_response(307)
            self.send_header("Location", "http://203.0.113.9/steal"); self.end_headers()
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), R)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with pytest.raises(ProviderError):
        _post_loopback(f"http://127.0.0.1:{srv.server_port}/v1/chat/completions", {"a": 1}, {}, 2)
    srv.shutdown()
    with pytest.raises(ProviderUnavailable):
        _post_loopback("http://example.com/v1", {}, {}, 2)


def test_hermes_non_loopback_disables_interviewer():
    env = {"INSTINCT_ORNITH_URL": "http://127.0.0.1:8089/v1", "INSTINCT_ORNITH_MODEL": "m",
           "INSTINCT_HERMES_URL": "https://remote.example.com/v1", "INSTINCT_HERMES_MODEL": "h"}
    assert interviewer_from_env(env) is None


def test_http_tenant_isolation_and_labels_through_real_routes(monkeypatch):
    import http.server, json, threading
    from fastapi.testclient import TestClient
    from app.main import app
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            b = json.loads(self.rfile.read(int(self.headers["content-length"])))
            ext = "KIND |" in b["messages"][0]["content"]
            txt = ('strength | robotics club | "started a robotics club at my school"' if ext
                   else "What was it like when you taught the younger kids to solder?")
            o = json.dumps({"choices": [{"message": {"content": txt}}], "model": "stub"}).encode()
            self.send_response(200); self.send_header("content-type", "application/json"); self.end_headers(); self.wfile.write(o)
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("INSTINCT_ORNITH_URL", f"http://127.0.0.1:{srv.server_port}/v1")
    monkeypatch.setenv("INSTINCT_ORNITH_MODEL", "stub")
    c = TestClient(app)
    A = {"x-atlas-tenant": "http-a", "x-atlas-actor": "student"}
    B = {"x-atlas-tenant": "http-b", "x-atlas-actor": "student"}
    sid = c.post("/api/v1/study-abroad/identity-interviews", headers=A, json={"track": "college"}).json()["id"]
    r = c.post(f"/api/v1/study-abroad/identity-interviews/{sid}/turns", headers=A,
               json={"modality": "chat", "student_response": ANSWER, "evidence_tags": []})
    assert r.status_code == 200 and r.json()["next_question_source"] == ADAPTIVE
    assert c.get(f"/api/v1/study-abroad/identity-interviews/{sid}", headers=B).status_code == 404
    assert c.post(f"/api/v1/study-abroad/identity-interviews/{sid}/turns", headers=B,
                  json={"modality": "chat", "student_response": ANSWER, "evidence_tags": []}).status_code == 404
    assert c.post(f"/api/v1/study-abroad/identity-interviews/{sid}/insights/1/0/confirm", headers=B,
                  json={"confirmed": True}).status_code == 404
    ok = c.post(f"/api/v1/study-abroad/identity-interviews/{sid}/insights/1/0/confirm", headers=A, json={"confirmed": True})
    assert ok.status_code == 200
    srv.shutdown()
