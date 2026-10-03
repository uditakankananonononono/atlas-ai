"""Essay critique: coaching only, exact-quote anchored (fake loopback model = unit tests; real runs in scripts/verification)."""
import http.server, json, threading
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m23_study_abroad import essay_critique as ec

DRAFT = ("I have always been a hard worker and I am passionate about engineering. Last spring I rebuilt the drive train of "
         "our robot overnight because the first one snapped before regionals, and we still placed fourth. Engineering "
         "matters to me. Engineering shapes how I see problems, and engineering gives me energy, and engineering is what "
         "I want to study because engineering helps people.")


def _srv(text, hits=None):
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["content-length"]))
            if hits is not None: hits.append(1)
            out = json.dumps({"choices": [{"message": {"content": text}}], "model": "stub"}).encode()
            self.send_response(200); self.send_header("content-type", "application/json"); self.end_headers(); self.wfile.write(out)
        def log_message(self, *a): pass
    s = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def _router(srv):
    return ec.router_from_env({"INSTINCT_ORNITH_URL": f"http://127.0.0.1:{srv.server_port}/v1", "INSTINCT_ORNITH_MODEL": "stub"})


def test_verified_measures_are_exact_and_checkable():
    m = ec.verified_measures(DRAFT)
    kinds = {x["type"] for x in m}
    assert {"abstract_claim", "repeated_word"} <= kinds
    assert all(x["quote"] in DRAFT for x in m) and all(x["source"] == ec.VERIFIED for x in m)
    rep = next(x for x in m if x["type"] == "repeated_word")
    assert DRAFT.lower().count("engineering") >= 4 and "engineering" in rep["observation"]


def test_model_spans_must_be_exact_copies_and_questions_are_our_templates():
    text = ('evidence | I have always been a hard worker\n'
            'scene | rebuilt the drive train of our robot overnight\n'
            'reason | built a rocket to Mars\n'                       # fabricated
            'rewrite | I am a tireless engineer\n'                    # type not allowed
            'scene | I have always been a hard worker')               # duplicate-ish handled below
    kept, rej = ec.parse_spans(text, DRAFT)
    assert [k["quote"] for k in kept] == ["I have always been a hard worker", "rebuilt the drive train of our robot overnight"]
    assert all(k["quote"] in DRAFT and k["question"] in {t.format(q=k["quote"]) for t in ec.TEMPLATES.values()} for k in kept)
    assert len(rej) >= 2


def test_critique_with_model_is_labeled_and_never_returns_essay_prose():
    s = _srv("evidence | I have always been a hard worker\nscene | rebuilt the drive train of our robot overnight")
    out = ec.critique(DRAFT, _router(s))
    assert out["mode"] == "model_selected_spans_plus_verified_measures" and out["generated_essay_prose"] is None
    assert out["revised_draft"] is None and out["student_authored_final"] is True
    assert any(i["source"] == ec.MODEL_SPAN and i["span_quality"] == "unverified" for i in out["items"])
    for i in out["items"]:
        assert i["quote"] in DRAFT
    s.shutdown()


def test_model_prose_instead_of_spans_is_rejected_not_passed_through():
    s = _srv("Here is a better version: I rebuilt my team's robot with grit and determination, a true leader.")
    out = ec.critique(DRAFT, _router(s))
    assert out["mode"] == "verified_measures_only_model_spans_rejected"
    assert not any(i["source"] == ec.MODEL_SPAN for i in out["items"])
    assert "better version" not in json.dumps(out["items"])
    s.shutdown()


def test_no_model_is_labeled_measures_only():
    out = ec.critique(DRAFT, None)
    assert out["mode"] == "verified_measures_only_no_model" and "no local model" in out["detail"]
    dead = ec.router_from_env({"INSTINCT_ORNITH_URL": "http://127.0.0.1:9/v1", "INSTINCT_ORNITH_MODEL": "x"})
    out2 = ec.critique(DRAFT, dead)
    assert out2["mode"].startswith("verified_measures_only") and out2["model"] is None


def test_non_loopback_env_disables_model():
    assert ec.router_from_env({"INSTINCT_ORNITH_URL": "https://api.example.com/v1", "INSTINCT_ORNITH_MODEL": "x"}) is None
    assert ec.router_from_env({"INSTINCT_ORNITH_URL": "http://127.0.0.1:1/v1", "INSTINCT_ORNITH_MODEL": "x",
                               "INSTINCT_HERMES_URL": "https://r.example.com/v1", "INSTINCT_HERMES_MODEL": "h"}) is None


def test_draft_is_capped_and_http_route_works(monkeypatch):
    s = _srv("scene | rebuilt the drive train of our robot overnight")
    monkeypatch.setenv("INSTINCT_ORNITH_URL", f"http://127.0.0.1:{s.server_port}/v1")
    monkeypatch.setenv("INSTINCT_ORNITH_MODEL", "stub")
    c = TestClient(app)
    H = {"x-atlas-tenant": "crit-a", "x-atlas-actor": "student"}
    r = c.post("/api/v1/study-abroad/essay-tools/critique", headers=H, json={"draft": DRAFT})
    assert r.status_code == 200 and r.json()["mode"] == "model_selected_spans_plus_verified_measures"
    assert r.json()["generated_essay_prose"] is None
    assert c.post("/api/v1/study-abroad/essay-tools/critique", headers=H, json={"draft": "short"}).status_code == 422
    big = ec.critique("word " * 5000, None)
    assert all(len(i["quote"]) <= ec.MAX_DRAFT for i in big["items"])
    s.shutdown()


def test_proxy_never_used(monkeypatch):
    seen = []
    px = _srv("x", seen); tgt = _srv("scene | rebuilt the drive train of our robot overnight")
    for k in ("HTTP_PROXY", "http_proxy"):
        monkeypatch.setenv(k, f"http://127.0.0.1:{px.server_port}")
    monkeypatch.delenv("NO_PROXY", raising=False); monkeypatch.delenv("no_proxy", raising=False)
    out = ec.critique(DRAFT, _router(tgt))
    assert seen == [] and out["mode"] == "model_selected_spans_plus_verified_measures"


def test_busy_slots_return_labeled_measures_only(monkeypatch):
    import threading as th
    for _ in range(2): ec._SLOTS.acquire()
    try:
        out = ec.critique(DRAFT, ec.router_from_env({"INSTINCT_ORNITH_URL": "http://127.0.0.1:9/v1", "INSTINCT_ORNITH_MODEL": "x"}))
        assert "busy" in out["detail"] and out["mode"].startswith("verified_measures_only")
    finally:
        for _ in range(2): ec._SLOTS.release()
