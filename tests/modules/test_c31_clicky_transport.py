"""Row 57: the real stdlib transport, driven end to end against a loopback HTTP server.
No call to api.clicky.com is ever made here."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from app.modules.c31 import clicky

KEY = "abcDEF123456"
SEEN = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        q = parse_qs(urlsplit(self.path).query)
        SEEN.append((urlsplit(self.path).path, q, dict(self.headers)))
        mode = q.get("type", [""])[0]
        if mode == "pages":
            return self._send(200, json.dumps([{"type": "pages", "dates": [{"date": "2026-10-11", "items": [{"title": "Home", "value": "7"}]}]}]))
        if mode == "links":
            return self._send(403, "denied")
        if mode == "searches":
            return self._send(200, "<html>not json</html>")
        if mode == "goals":
            return self._send(302, "", {"Location": "http://example.invalid/steal?" + self.path})
        if mode == "events":
            return self._send(200, "x" * (clicky.MAX_BODY + 10))
        if mode == "cities":
            import time; time.sleep(1.5)
            return self._send(200, "[]")
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
    srv = HTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    yield "http://127.0.0.1:%d/api/stats/4" % srv.server_port
    srv.shutdown()


def run(server, types, **kw):
    SEEN.clear()
    plan = clicky.plan_stats_request(123, types, **kw)
    return clicky.execute_stats_request(plan, KEY, base_url=server, allow_loopback=True)


def test_success_sends_documented_query_and_parses(server):
    out = run(server, "pages", date="last-7-days", limit=50)
    assert out["status_code"] == 200 and out["data"][0]["type"] == "pages"
    path, q, headers = SEEN[0]
    assert path == "/api/stats/4"
    assert q["site_id"] == ["123"] and q["type"] == ["pages"] and q["limit"] == ["50"]
    assert q["date"] == ["last-7-days"] and q["output"] == ["json"] and q["sitekey"] == [KEY]
    assert headers["Accept"] == "application/json"


def test_sitekey_never_in_result_or_request(server):
    out = run(server, "pages")
    assert KEY not in json.dumps(out) and out["request"]["url"] == clicky.DOCUMENTED_API_BASE


@pytest.mark.parametrize("typ,expect", [("links", "APPLY_REFUSED_HTTP:403"), ("searches", "APPLY_REFUSED_BAD_JSON"),
                                        ("events", "APPLY_REFUSED_BAD_TYPE:body")])
def test_errors_refuse_without_leaking_key(server, typ, expect):
    with pytest.raises(ValueError) as e:
        run(server, typ)
    assert str(e.value) == expect and KEY not in str(e.value)


def test_redirect_is_refused_and_not_followed(server):
    with pytest.raises(ValueError) as e:
        run(server, "goals")
    assert str(e.value).startswith("APPLY_REFUSED_HTTP:302") and KEY not in str(e.value)


def test_timeout_refuses(server):
    plan = clicky.plan_stats_request(123, "cities")
    with pytest.raises(ValueError, match="APPLY_REFUSED_TRANSPORT"):
        clicky.execute_stats_request(plan, KEY, timeout=0.3, base_url=server, allow_loopback=True)


def test_connection_refused_does_not_echo_url_or_key():
    plan = clicky.plan_stats_request(123, "pages")
    with pytest.raises(ValueError) as e:
        clicky.execute_stats_request(plan, KEY, base_url="http://127.0.0.1:1/x", allow_loopback=True)
    assert str(e.value) == "APPLY_REFUSED_TRANSPORT"


def test_caps_enforced_before_any_request(server):
    SEEN.clear()
    for kw in ({"limit": 101}, {"date": "last-31-days"}, {"date": "2026-10-01"}):
        with pytest.raises(ValueError):
            clicky.plan_stats_request(123, "pages", **kw)
    assert SEEN == []


@pytest.mark.parametrize("key", ["", "a b", "k&site_id=9", "short", None, "x" * 65])
def test_bad_sitekey_refused_before_request(server, key):
    SEEN.clear()
    plan = clicky.plan_stats_request(123, "pages")
    with pytest.raises(ValueError):
        clicky.execute_stats_request(plan, key, base_url=server, allow_loopback=True)
    assert SEEN == []


@pytest.mark.parametrize("base", ["https://evil.example/x", "http://example.com/x", "http://127.0.0.1.evil.com/x"])
def test_base_url_override_only_loopback(base):
    plan = clicky.plan_stats_request(123, "pages")
    with pytest.raises(ValueError, match="base_url"):
        clicky.execute_stats_request(plan, KEY, base_url=base, allow_loopback=True)
    with pytest.raises(ValueError, match="base_url"):
        clicky.execute_stats_request(plan, KEY, base_url="http://127.0.0.1:9/x")


def test_tampered_plan_refused():
    plan = clicky.plan_stats_request(123, "pages")
    for bad in (dict(plan, url="https://attacker.example/"), dict(plan, method="POST"),
                dict(plan, params=dict(plan["params"], sitekey="literal"))):
        with pytest.raises(ValueError):
            clicky.execute_stats_request(bad, KEY)
