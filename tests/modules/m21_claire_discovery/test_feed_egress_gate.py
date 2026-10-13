"""Offline probes of Claire's real outbound gate, including DNS and redirects."""
import pytest
from app.modules.m21_claire import source_connectors as feeds
from app.runtime.guardrails.enforcer import GuardrailEnforcer
from app.runtime.guardrails.errors import GuardrailRefusal


def policy(*hosts, max_reads=5):
    return {"tos": {h: {"allowed_kinds": ["read"], "automation_allowed": True} for h in hosts},
            "rate_limits": {h: {"read": {"max": max_reads, "window_seconds": 3600}} for h in hosts}}


def transport(monkeypatch, gate, responses, *, ip="8.8.8.8"):
    events=[]
    def resolve(host, port, **kwargs):
        assert gate.ledger("outbound")[-1]["record"]["verdict"] == "dispatched"
        events.append(("dns", host))
        return [(2, 1, 6, "", (ip, port))]
    class Response:
        def __init__(self, status, body, location):
            self.status, self.body, self.location = status, body, location
        def getheader(self, key): return self.location
        def read(self, n): return self.body[:n]
    class Connection:
        def __init__(self, host, port, pinned_ip, timeout):
            assert pinned_ip == ip
            events.append(("connect",host))
        def request(self, method, target, headers):
            assert method == "GET"
            events.append(("request", target, headers))
        def getresponse(self): return Response(*responses.pop(0))
        def close(self): events.append(("close",))
    monkeypatch.setattr(feeds.socket,"getaddrinfo",resolve)
    monkeypatch.setattr(feeds,"_PinnedHTTPSConnection",Connection)
    return events


def test_default_and_empty_policy_refuse_before_dns_or_socket(monkeypatch):
    gate=GuardrailEnforcer()
    events=transport(monkeypatch,gate,[])
    for declarations in (None, {}, {"tos": {}}):
        with pytest.raises((GuardrailRefusal,ValueError)):
            feeds.fetch_public_feed("https://example.org/rss",enforcer=gate,declarations=declarations)
    assert events == []
    assert gate.ledger("outbound")[-1]["record"]["verdict"] == "refused:denied"


def test_gate_ledgers_admission_before_dns_and_request(monkeypatch):
    gate=GuardrailEnforcer()
    events=transport(monkeypatch,gate,[(200,b"<rss/>",None)])
    assert feeds.fetch_public_feed("https://example.org/rss?q=1",enforcer=gate,
                                   declarations=policy("example.org")) == (b"<rss/>","https://example.org/rss?q=1")
    assert [e[0] for e in events] == ["dns","connect","request","close"]
    assert events[2][1] == "/rss?q=1"
    assert gate.ledger("outbound")[-1]["record"]["authority_checked"] is False


def test_redirect_to_undeclared_destination_refuses_before_its_dns(monkeypatch):
    gate=GuardrailEnforcer()
    events=transport(monkeypatch,gate,[(302,b"", "https://other.org/feed")])
    with pytest.raises(GuardrailRefusal):
        feeds.fetch_public_feed("https://example.org/rss",enforcer=gate,declarations=policy("example.org"))
    assert [e for e in events if e[0] == "dns"] == [("dns","example.org")]
    assert [e["record"]["verdict"] for e in gate.ledger("outbound")] == ["dispatched","refused:denied"]


def test_declared_redirect_has_separate_admission(monkeypatch):
    gate=GuardrailEnforcer()
    events=transport(monkeypatch,gate,[(302,b"", "https://other.org/feed"),(200,b"ok",None)])
    assert feeds.fetch_public_feed("https://example.org/rss",enforcer=gate,
                                   declarations=policy("example.org","other.org")) == (b"ok","https://other.org/feed")
    assert [e for e in events if e[0] == "dns"] == [("dns","example.org"),("dns","other.org")]
    assert len(gate.ledger("outbound")) == 2


def test_same_host_redirect_consumes_ledger_rate_budget(monkeypatch):
    gate=GuardrailEnforcer()
    events=transport(monkeypatch,gate,[(302,b"", "/next")])
    with pytest.raises(GuardrailRefusal) as held:
        feeds.fetch_public_feed("https://example.org/rss",enforcer=gate,
                                declarations=policy("example.org",max_reads=1))
    assert held.value.details["failed_checks"] == ["rate_limit"]
    assert len([e for e in events if e[0] == "dns"]) == 1


@pytest.mark.parametrize("change", ["automation", "kind", "review"])
def test_policy_refusals_do_not_touch_transport(monkeypatch,change):
    gate=GuardrailEnforcer(); events=transport(monkeypatch,gate,[])
    declarations=policy("example.org")
    if change == "automation": declarations["tos"]["example.org"]["automation_allowed"]=False
    if change == "kind": declarations["tos"]["example.org"]["allowed_kinds"]=["post"]
    if change == "review": declarations["review_kinds"]=["read"]
    with pytest.raises(GuardrailRefusal):
        feeds.fetch_public_feed("https://example.org/rss",enforcer=gate,declarations=declarations)
    assert events == []


def test_private_dns_answer_never_opens_connection(monkeypatch):
    gate=GuardrailEnforcer(); events=transport(monkeypatch,gate,[],ip="127.0.0.1")
    with pytest.raises(ValueError,match="non-public"):
        feeds.fetch_public_feed("https://example.org/rss",enforcer=gate,declarations=policy("example.org"))
    assert events == [("dns","example.org")]


def test_oversized_feed_closes_connection_and_retains_admission(monkeypatch):
    gate=GuardrailEnforcer(); events=transport(monkeypatch,gate,[(200,b"too long",None)])
    with pytest.raises(ValueError,match="byte limit"):
        feeds.fetch_public_feed("https://example.org/rss",max_bytes=2,enforcer=gate,declarations=policy("example.org"))
    assert events[-1] == ("close",)
    assert gate.ledger("outbound")[-1]["record"]["verdict"] == "dispatched"


def test_persist_failure_stops_dns(monkeypatch):
    def fail(*args): raise RuntimeError("storage unavailable")
    gate=GuardrailEnforcer(persist=fail); events=transport(monkeypatch,gate,[])
    with pytest.raises(RuntimeError,match="storage unavailable"):
        feeds.fetch_public_feed("https://example.org/rss",enforcer=gate,declarations=policy("example.org"))
    assert events == []


def test_cycle_without_declarations_is_fail_closed(monkeypatch,tmp_path):
    from app.modules.m21_claire.scheduled_signal_cycle import run_feed_cycle
    gate=GuardrailEnforcer(); events=transport(monkeypatch,gate,[])
    result=run_feed_cycle(tenant_id="tenant",feed_urls=["https://example.org/rss"],
                          workspace_path=str(tmp_path/"workspace.db"),enforcer=gate)
    assert result["feeds_succeeded"] == 0 and result["feeds_failed"] == 1
    assert events == []
