"""Embedding matcher (fake loopback embedding server = unit tests only; real models are in scripts/verification)."""
import http.server, json, threading, time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m23_study_abroad.embedding_matcher import (EMBEDDING, FALLBACK, LocalEmbeddingMatcher, cosine,
                                                           matcher_from_env)
from app.modules.m23_study_abroad.essay_tools import EssayToolService

VOCAB = ["robot", "water", "dog", "music"]


def _vec(text):
    t = text.lower()
    return [float(t.count(w)) + 0.01 for w in VOCAB]


def _server(handler_body):
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers["content-length"]); req = json.loads(self.rfile.read(n))
            handler_body(self, req)
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _ok(h, req):
    data = [{"index": i, "embedding": _vec(t)} for i, t in enumerate(req["input"])]
    out = json.dumps({"data": data}).encode()
    h.send_response(200); h.send_header("content-type", "application/json"); h.end_headers(); h.wfile.write(out)


EVID = [{"label": "Dogs", "description": "I walk shelter dog every weekend", "values": []},
        {"label": "Robots", "description": "I built a robot for the robot club", "values": []}]


def test_embedding_ranking_is_labeled_and_only_orders_student_evidence():
    srv = _server(_ok)
    svc = EssayToolService(matcher=LocalEmbeddingMatcher(f"http://127.0.0.1:{srv.server_port}/v1", "stub"))
    r = svc.topic_finder("Tell us about a robot you made", EVID)
    assert r["match_mode"] == EMBEDDING and r["candidates"][0]["label"] == "Robots"
    assert "embedding_similarity" in r["candidates"][0] and r["generated_essay_prose"] is None
    srv.shutdown()


def test_unreachable_or_garbage_is_labeled_token_fallback_with_original_order():
    for body in (None, lambda h, req: (h.send_response(200), h.end_headers(), h.wfile.write(b"not json"))):
        if body is None:
            m = LocalEmbeddingMatcher("http://127.0.0.1:9/v1", "stub", timeout=1)
        else:
            srv = _server(body); m = LocalEmbeddingMatcher(f"http://127.0.0.1:{srv.server_port}/v1", "stub", timeout=2)
        r = EssayToolService(matcher=m).topic_finder("robot", EVID)
        assert r["match_mode"] == FALLBACK and [c["label"] for c in r["candidates"]] == ["Dogs", "Robots"]
        assert all("embedding_similarity" not in c for c in r["candidates"])


def test_no_matcher_is_token_overlap_labeled():
    assert EssayToolService().topic_finder("robot", EVID)["match_mode"] == FALLBACK


def test_dimension_mismatch_or_missing_vector_rejected():
    def bad(h, req):
        data = [{"index": 0, "embedding": [1.0, 2.0]}, {"index": 1, "embedding": [1.0]}, {"index": 2, "embedding": [1.0, 0.0]}]
        out = json.dumps({"data": data}).encode(); h.send_response(200); h.end_headers(); h.wfile.write(out)
    srv = _server(bad)
    assert LocalEmbeddingMatcher(f"http://127.0.0.1:{srv.server_port}/v1", "stub").rank("q", ["a", "b"]) is None


def test_redirect_refused_and_nonloopback_rejected():
    def redir(h, req):
        h.send_response(307); h.send_header("Location", "http://203.0.113.9/x"); h.end_headers()
    srv = _server(redir)
    assert LocalEmbeddingMatcher(f"http://127.0.0.1:{srv.server_port}/v1", "stub").rank("q", ["a"]) is None
    with pytest.raises(ValueError):
        LocalEmbeddingMatcher("https://api.example.com/v1", "m")
    assert matcher_from_env({"INSTINCT_EMBED_URL": "https://api.example.com/v1", "INSTINCT_EMBED_MODEL": "m"}) is None
    assert matcher_from_env({}) is None


def test_trickling_embedding_response_hits_total_deadline():
    def trickle(h, req):
        h.send_response(200); h.send_header("content-length", "100000"); h.end_headers()
        try:
            for _ in range(60):
                h.wfile.write(b"x" * 10); h.wfile.flush(); time.sleep(0.3)
        except Exception:
            pass
    srv = _server(trickle)
    t0 = time.time()
    assert LocalEmbeddingMatcher(f"http://127.0.0.1:{srv.server_port}/v1", "stub", timeout=1.5).rank("q", ["a"]) is None
    assert time.time() - t0 < 3.5


def test_http_route_tenant_scoped_label(monkeypatch):
    srv = _server(_ok)
    monkeypatch.setenv("INSTINCT_EMBED_URL", f"http://127.0.0.1:{srv.server_port}/v1")
    monkeypatch.setenv("INSTINCT_EMBED_MODEL", "stub")
    c = TestClient(app)
    H = {"x-atlas-tenant": "emb-a", "x-atlas-actor": "student"}
    r = c.post("/api/v1/study-abroad/essay-tools/topics", headers=H, json={"prompt": "robot", "evidence": EVID})
    assert r.status_code == 200 and r.json()["match_mode"] == EMBEDDING and r.json()["candidates"][0]["label"] == "Robots"
    monkeypatch.delenv("INSTINCT_EMBED_URL")
    r2 = c.post("/api/v1/study-abroad/essay-tools/topics", headers=H, json={"prompt": "robot", "evidence": EVID})
    assert r2.json()["match_mode"] == FALLBACK


def test_cosine_basic():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0) and cosine([1, 0], [0, 1]) == 0.0 and cosine([0, 0], [1, 1]) == 0.0


def _resp(data):
    def h(hh, req):
        out = json.dumps({"data": data}).encode(); hh.send_response(200); hh.end_headers(); hh.wfile.write(out)
    return h


@pytest.mark.parametrize("data", [
    [{"index": 0, "embedding": ["1", "2"]}, {"index": 1, "embedding": [1, 2]}],            # numeric strings
    [{"index": 0, "embedding": [1e999, 1]}, {"index": 1, "embedding": [1, 2]}],            # overflow -> inf
    [{"index": 0, "embedding": [1, 2]}, {"index": 0, "embedding": [1, 3]}],                # duplicate index
    [{"index": 0, "embedding": [1, 2]}, {"index": 5, "embedding": [1, 3]}],                # out of range
    [{"index": 0, "embedding": [True, 2]}, {"index": 1, "embedding": [1, 2]}],             # bool
    [{"index": 0, "embedding": []}, {"index": 1, "embedding": []}],                        # empty
    [{"index": 0}, {"index": 1, "embedding": [1, 2]}],                                     # missing vector
    "garbage",
])
def test_malformed_embedding_responses_fall_back_safely(data):
    srv = _server(_resp(data))
    m = LocalEmbeddingMatcher(f"http://127.0.0.1:{srv.server_port}/v1", "stub", timeout=3)
    assert m.rank("q", ["a"]) is None
    r = EssayToolService(matcher=m).topic_finder("robot", EVID[:1])
    assert r["match_mode"] == FALLBACK


def test_nan_json_constant_is_rejected():
    def h(hh, req):
        out = b'{"data":[{"index":0,"embedding":[NaN,1]},{"index":1,"embedding":[1,2]}]}'
        hh.send_response(200); hh.end_headers(); hh.wfile.write(out)
    srv = _server(h)
    assert LocalEmbeddingMatcher(f"http://127.0.0.1:{srv.server_port}/v1", "stub").rank("q", ["a"]) is None


def test_env_http_proxy_is_never_used(monkeypatch):
    seen = []
    def spy(hh, req): seen.append(req); hh.send_response(500); hh.end_headers()
    proxy = _server(spy)
    target = _server(_ok)
    monkeypatch.setenv("HTTP_PROXY", f"http://127.0.0.1:{proxy.server_port}")
    monkeypatch.setenv("http_proxy", f"http://127.0.0.1:{proxy.server_port}")
    monkeypatch.delenv("NO_PROXY", raising=False); monkeypatch.delenv("no_proxy", raising=False)
    assert LocalEmbeddingMatcher(f"http://127.0.0.1:{target.server_port}/v1", "stub").rank("q", ["robot"]) is not None
    assert seen == []


def test_hard_total_cap_with_delayed_headers_then_body():
    def slow(hh, req):
        time.sleep(1.2); hh.send_response(200); hh.send_header("content-length", "100000"); hh.end_headers()
        try:
            for _ in range(40):
                hh.wfile.write(b"x" * 10); hh.wfile.flush(); time.sleep(0.3)
        except Exception:
            pass
    srv = _server(slow)
    t0 = time.time()
    assert LocalEmbeddingMatcher(f"http://127.0.0.1:{srv.server_port}/v1", "stub", timeout=1.5).rank("q", ["a"]) is None
    assert time.time() - t0 < 2.5


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://127.0.0.1/x", "http://user:pw@127.0.0.1:1/v1",
                                 "http://127.0.0.1:99999/v1", "http://127.0.0.1:1/v1?x=1", "http://[::2]/v1", "http://example.com/v1"])
def test_bad_urls_rejected(url):
    with pytest.raises(ValueError):
        LocalEmbeddingMatcher(url, "m")
    assert matcher_from_env({"INSTINCT_EMBED_URL": url, "INSTINCT_EMBED_MODEL": "m"}) is None


def test_all_zero_vectors_are_rejected():
    srv = _server(_resp([{"index": 0, "embedding": [0, 0]}, {"index": 1, "embedding": [0.0, 0.0]}]))
    assert LocalEmbeddingMatcher(f"http://127.0.0.1:{srv.server_port}/v1", "stub").rank("q", ["a"]) is None


def test_abandoned_calls_are_bounded_and_extra_calls_fall_back_immediately():
    import threading as th
    from app.modules.m23_study_abroad import embedding_matcher as em
    release = th.Event()
    def hang(hh, req):  # a header line every 0.2s: each socket read stays under the 0.3s timeout, so the worker lingers
        try:
            hh.wfile.write(b"HTTP/1.1 200 OK\r\n")
            for _ in range(90):
                if release.is_set():
                    break
                hh.wfile.write(b"X-a: b\r\n"); hh.wfile.flush(); time.sleep(0.2)
        except Exception:
            pass
    class TS(http.server.ThreadingHTTPServer):
        daemon_threads = True
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["content-length"])); hang(self, None)
        def log_message(self, *a): pass
    srv = TS(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    m = LocalEmbeddingMatcher(f"http://127.0.0.1:{srv.server_port}/v1", "stub", timeout=0.3)
    before = th.active_count()
    for _ in range(4):
        assert m.rank("q", ["a"]) is None          # each times out and is abandoned, holding its slot
    t0 = time.time()
    for _ in range(20):
        assert m.rank("q", ["a"]) is None          # no slot left -> instant fallback, no new thread
    assert time.time() - t0 < 0.5
    assert th.active_count() - before <= 10        # <= 4 lingering workers (+ server handler threads), not 24
    release.set()


def test_bad_evidence_values_do_not_500_and_are_bounded():
    c = TestClient(app)
    H = {"x-atlas-tenant": "emb-v", "x-atlas-actor": "student"}
    for values in (None, 123, ["x", 3], "bad", [{"a": 1}], [True], ["y" * 5000] * 50):
        ev = [{"label": "A", "description": "robot robot", "values": values}]
        r = c.post("/api/v1/study-abroad/essay-tools/topics", headers=H, json={"prompt": "robot", "evidence": ev})
        assert r.status_code == 200, (values, r.status_code)


def test_oversized_evidence_skips_embedding_with_honest_detail():
    srv = _server(_ok)
    svc = EssayToolService(matcher=LocalEmbeddingMatcher(f"http://127.0.0.1:{srv.server_port}/v1", "stub"))
    r = svc.topic_finder("robot", [{"label": str(i), "description": "robot", "values": []} for i in range(60)])
    assert r["match_mode"] == FALLBACK and "bounded work" in r["match_detail"] and len(r["candidates"]) == 60
    ok = svc.topic_finder("robot", EVID)
    assert ok["match_mode"] == EMBEDDING and ok["match_detail"] == ""
