"""Row 57: the real stdlib transport, driven against a loopback HTTP server behind a socket guard.
No call to api.clicky.com is made: any non-loopback connection attempt fails the test."""
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from app.modules.c31 import clicky

KEY = "abcDEF123456"
SEEN = []
LOCK = threading.Lock()
LOOPBACK = {"127.0.0.1", "::1"}


@pytest.fixture(autouse=True)
def socket_guard(monkeypatch):
    """Any connect() to a non-loopback address fails the test, whatever validation does."""
    real = socket.socket.connect

    def guarded(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else address
        if host not in LOOPBACK:
            raise AssertionError("non-loopback connect attempted: %r" % (host,))
        return real(self, address, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", guarded)
    monkeypatch.setattr(socket, "create_connection", _guarded_create(socket.create_connection))
    SEEN.clear()


def _guarded_create(real):
    def create(address, *a, **k):
        if address[0] not in LOOPBACK and address[0] != "localhost":
            raise AssertionError("non-loopback connect attempted: %r" % (address[0],))
        return real(address, *a, **k)
    return create


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        u = urlsplit(self.path)
        q = parse_qs(u.query)
        with LOCK:
            SEEN.append((u.path, q, dict(self.headers)))
        if u.path == "/landing":
            return self._send(200, "[]")
        mode = q.get("type", [""])[0]
        if mode == "pages":
            return self._send(200, json.dumps([{"type": "pages", "dates": [{"date": "2026-10-11", "items": [{"title": "Home", "value": "7"}]}]}]))
        if mode == "links":
            return self._send(403, "denied")
        if mode == "searches":
            return self._send(200, "<html>not json</html>")
        if mode == "goals":
            return self._send(302, "", {"Location": "/landing?" + u.query})
        if mode == "downloads":
            return self._send(301, "", {"Location": "/landing"})
        if mode == "campaigns":
            return self._send(307, "", {"Location": "/landing"})
        if mode == "events":
            return self._send(200, "x" * (clicky.MAX_BODY + 10))
        if mode == "cities":
            time.sleep(1.5)
            return self._send(200, "[]")
        if mode == "countries":
            return self._send(204, "")
        if mode == "visitors":      # slow drip: 1 byte every 0.1s, would run ~20s
            self.send_response(200); self.send_header("Content-Length", "200"); self.end_headers()
            try:
                for _ in range(200):
                    self.wfile.write(b"["); self.wfile.flush(); time.sleep(0.1)
            except OSError:
                pass
            return
        self._send(200, "[]")

    def _send(self, code, body, headers=None):
        b = body.encode()
        self.send_response(code)
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


@pytest.fixture(scope="module")
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d/api/stats/4" % srv.server_port
    srv.shutdown()


def run(server, types, **kw):
    plan = clicky.plan_stats_request(123, types, **{k: v for k, v in kw.items() if k in ("date", "limit")})
    extra = {k: v for k, v in kw.items() if k not in ("date", "limit")}
    return clicky.execute_stats_request(plan, KEY, base_url=server, allow_loopback=True, **extra)


def test_success_sends_documented_query_and_parses(server):
    out = run(server, "pages", date="last-7-days", limit=50)
    assert out["status_code"] == 200 and out["data"][0]["type"] == "pages"
    path, q, headers = SEEN[0]
    assert path == "/api/stats/4" and len(SEEN) == 1
    assert q["site_id"] == ["123"] and q["type"] == ["pages"] and q["limit"] == ["50"]
    assert q["date"] == ["last-7-days"] and q["output"] == ["json"] and q["sitekey"] == [KEY]
    assert headers["Accept"] == "application/json"


def test_result_url_is_the_url_actually_hit_and_has_no_key(server):
    out = run(server, "pages")
    assert out["request"]["url"] == server and KEY not in json.dumps(out)


@pytest.mark.parametrize("typ,expect", [("links", "APPLY_REFUSED_HTTP:403"), ("searches", "APPLY_REFUSED_BAD_JSON"),
                                        ("events", "APPLY_REFUSED_BAD_TYPE:body"), ("countries", "APPLY_REFUSED_BAD_JSON")])
def test_errors_refuse_without_leaking_key_or_chaining(server, typ, expect):
    with pytest.raises(ValueError) as e:
        run(server, typ)
    assert str(e.value) == expect and KEY not in str(e.value)
    assert e.value.__cause__ is None and (e.value.__context__ is None or KEY not in repr(e.value.__context__))
    import traceback
    assert KEY not in "".join(traceback.format_exception(e.type, e.value, e.tb))


@pytest.mark.parametrize("typ,code", [("goals", 302), ("downloads", 301), ("campaigns", 307)])
def test_redirects_are_refused_and_never_followed(server, typ, code):
    with pytest.raises(ValueError) as e:
        run(server, typ)
    assert str(e.value) == "APPLY_REFUSED_HTTP:%d" % code and KEY not in str(e.value)
    assert [p for p, _, _ in SEEN] == ["/api/stats/4"]          # the Location target was never requested


def test_total_timeout_bounds_slow_server(server):
    plan = clicky.plan_stats_request(123, "cities")
    t0 = time.monotonic()
    with pytest.raises(ValueError, match="APPLY_REFUSED_TRANSPORT"):
        clicky.execute_stats_request(plan, KEY, timeout=0.3, base_url=server, allow_loopback=True)
    assert time.monotonic() - t0 < 1.0


def test_total_timeout_bounds_slow_drip(server):
    plan = clicky.plan_stats_request(123, "visitors")
    t0 = time.monotonic()
    with pytest.raises(ValueError, match="APPLY_REFUSED_TRANSPORT"):
        clicky.execute_stats_request(plan, KEY, timeout=1.0, base_url=server, allow_loopback=True)
    assert time.monotonic() - t0 < 2.0     # per-op timeout alone would allow ~20s
    time.sleep(0.8)
    assert not [t for t in threading.enumerate() if t.name.startswith("ThreadPoolExecutor")]   # worker stopped reading too


def test_connection_refused_does_not_echo_url_or_key():
    plan = clicky.plan_stats_request(123, "pages")
    with pytest.raises(ValueError) as e:
        clicky.execute_stats_request(plan, KEY, base_url="http://127.0.0.1:1/x", allow_loopback=True)
    assert str(e.value) == "APPLY_REFUSED_TRANSPORT" and e.value.__cause__ is None


def test_proxy_environment_is_ignored(server, monkeypatch):
    for v in ("HTTP_PROXY", "http_proxy", "ALL_PROXY"):
        monkeypatch.setenv(v, "http://127.0.0.1:9")      # dead proxy: used => failure
    monkeypatch.delenv("NO_PROXY", raising=False); monkeypatch.delenv("no_proxy", raising=False)
    assert run(server, "pages")["status_code"] == 200


def test_localhost_spelling_accepted(server):
    plan = clicky.plan_stats_request(123, "pages")
    out = clicky.execute_stats_request(plan, KEY, base_url=server.replace("127.0.0.1", "localhost"), allow_loopback=True)
    assert out["status_code"] == 200


def test_caps_refused_at_plan_and_execute_sends_nothing(server):
    for kw in ({"limit": 101}, {"date": "last-31-days"}, {"date": "2026-10-01"}):
        with pytest.raises(ValueError):
            clicky.plan_stats_request(123, "pages", **kw)
    good = clicky.plan_stats_request(123, "pages")
    for field, val in (("limit", 101), ("date", "last-31-days"), ("date", "2026-10-01"), ("type", "nonsense")):
        bad = dict(good, params=dict(good["params"], **{field: val}))
        with pytest.raises(ValueError, match="APPLY_REFUSED_BAD_TYPE:plan"):
            clicky.execute_stats_request(bad, KEY, base_url=server, allow_loopback=True)
    assert SEEN == []


@pytest.mark.parametrize("key", ["", "a b", "k&site_id=9", "short", None, "x" * 65])
def test_bad_sitekey_refused_before_request(server, key):
    plan = clicky.plan_stats_request(123, "pages")
    with pytest.raises(ValueError):
        clicky.execute_stats_request(plan, key, base_url=server, allow_loopback=True)
    assert SEEN == []


@pytest.mark.parametrize("base", ["https://evil.example/x", "http://example.com/x", "http://127.0.0.1.evil.com/x",
                                  "http://u:p@127.0.0.1:1/x", "http://127.0.0.1:1/x?a=b", "https://127.0.0.1:1/x"])
def test_base_url_override_only_plain_loopback(base):
    plan = clicky.plan_stats_request(123, "pages")
    with pytest.raises(ValueError, match="base_url"):
        clicky.execute_stats_request(plan, KEY, base_url=base, allow_loopback=True)
    with pytest.raises(ValueError, match="base_url"):
        clicky.execute_stats_request(plan, KEY, base_url="http://127.0.0.1:9/x")


def _bad_plans():
    good = clicky.plan_stats_request(123, "pages")
    return [None, "x", [], {}, dict(good, url="https://attacker.example/"), dict(good, method="POST"),
            dict(good, params=dict(good["params"], sitekey="literal")),
            dict(good, params=None), dict(good, params={"site_id": 1}), dict(good, headers=None),
            dict(good, headers={"Authorization": "x"}), dict(good, extra=1),
            {k: v for k, v in good.items() if k != "headers"},
            dict(good, params=dict(good["params"], extra="x")),
            dict(good, params=dict(good["params"], site_id=True)),
            dict(good, params=dict(good["params"], type=["pages"]))]


@pytest.mark.parametrize("i", range(16))
def test_malformed_or_tampered_plans_refused_before_any_request(i, server):
    # base_url is a loopback server so a plan that slipped validation WOULD reach it (SEEN) rather than be masked
    # by the live-host gate; the exact refusal reason is asserted.
    with pytest.raises(ValueError) as e:
        clicky.execute_stats_request(_bad_plans()[i], KEY, base_url=server, allow_loopback=True)
    assert str(e.value) == "APPLY_REFUSED_BAD_TYPE:plan" and SEEN == []


def test_live_host_is_off_by_default(monkeypatch):
    plan = clicky.plan_stats_request(123, "pages")
    monkeypatch.delenv(clicky.LIVE_ENV_FLAG, raising=False)
    for kw in ({}, {"live_approved": True}):
        with pytest.raises(ValueError, match="APPLY_REFUSED_NOT_APPROVED"):
            clicky.execute_stats_request(plan, KEY, **kw)
    monkeypatch.setenv(clicky.LIVE_ENV_FLAG, "1")
    with pytest.raises(ValueError, match="APPLY_REFUSED_NOT_APPROVED"):      # env alone is not enough
        clicky.execute_stats_request(plan, KEY)
    assert SEEN == []
