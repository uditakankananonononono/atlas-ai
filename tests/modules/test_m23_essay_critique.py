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
    assert {"trait_word", "repeated_word"} <= kinds
    assert all(x["quote"] in DRAFT for x in m)
    assert all(x["source"] == (ec.HEURISTIC if x["type"] == "trait_word" else ec.VERIFIED) for x in m)
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
    assert big["processed"]["model_truncated"] is True and all(i["quote"] in "word " * 5000 for i in big["items"])
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


def test_trait_word_is_a_labeled_heuristic_and_whole_word_only():
    ravi = ("I consider myself dedicated, but what matters is that my grandfather Ravi has run the shop on Park Street for "
            "forty years and I opened it every morning at six during the monsoon. I was driven to the hospital by a neighbor.")
    m = ec.verified_measures(ravi)
    t = [x for x in m if x["type"] == "trait_word"]
    assert t and all(x["source"] == ec.HEURISTIC and "Keyword heuristic only" in x["observation"] for x in t)
    assert "without a specific example" not in json.dumps(m)
    assert not any("driven" in x["observation"] for x in t)           # 'driven to the hospital' no longer flagged
    assert ec.verified_measures("My hardworking friends and a hard-working team.") == [] or all(
        x["source"] == ec.HEURISTIC for x in ec.verified_measures("My hardworking friends"))


def test_repeated_word_counts_whole_words_only_and_attributes_to_a_real_sentence():
    d = "Engineering is fun. Reengineering plans bore me. I like engineering and engineering teams, so engineering wins."
    m = [x for x in ec.verified_measures(d) if x["type"] == "repeated_word"]
    assert m and "4 times" in m[0]["observation"] and m[0]["quote"] == "Engineering is fun."
    assert "Reengineering" not in m[0]["observation"]


def test_midword_and_whitespace_changed_spans_are_rejected():
    d = "Last spring I rebuilt the drive train of our robot overnight, and we  still placed."
    assert ec.parse_spans("scene | ebuilt the drive train of our robot", d)[0] == []                 # mid-word start
    assert ec.parse_spans("scene | rebuilt the drive train of our rob", d)[0] == []                  # mid-word end
    assert ec.parse_spans("scene | and we still placed", d)[0] == []                                  # whitespace collapsed
    assert ec.parse_spans("scene | I rebuilt the drive train", d)[0][0]["quote"] == "I rebuilt the drive train"
    assert ec.parse_spans("scene | the drive train", d)[0] == []                                      # 3 words < 4


def test_long_draft_reports_what_was_processed_instead_of_silently_truncating():
    long = DRAFT + (" Filler sentence about nothing in particular." * 400) + " Engineering Engineering. The late sentence is " + "word " * 45 + "."
    out = ec.critique(long, None)
    assert out["processed"]["model_truncated"] is True and out["processed"]["draft_chars"] == len(long.strip())
    assert out["processed"]["measures_chars"] == len(long.strip())
    assert any(i["type"] == "long_sentence" and "late sentence" in i["quote"] for i in out["items"])  # measures see the tail
    short = ec.critique(DRAFT, None)
    assert short["processed"]["model_truncated"] is False


def test_two_slot_adversarial_load_is_bounded(monkeypatch):
    import time, threading as th
    class TS(http.server.ThreadingHTTPServer):
        daemon_threads = True
    release = th.Event()
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["content-length"]))
            try:
                self.wfile.write(b"HTTP/1.1 200 OK\r\n")
                for _ in range(60):
                    if release.is_set(): break
                    self.wfile.write(b"X-a: b\r\n"); self.wfile.flush(); time.sleep(0.2)
            except Exception: pass
        def log_message(self, *a): pass
    srv = TS(("127.0.0.1", 0), H); th.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(ec, "STEP_BUDGET_S", 0.4)
    r = _router(srv)
    before = th.active_count()
    for _ in range(2):
        assert ec.critique(DRAFT, r)["mode"].startswith("verified_measures_only")   # times out, abandons, keeps its slot
    t0 = time.time()
    outs = [ec.critique(DRAFT, r) for _ in range(30)]
    assert time.time() - t0 < 2.0 and all("busy" in o["detail"] for o in outs)
    assert th.active_count() - before <= 6
    release.set()
