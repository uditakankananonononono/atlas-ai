import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m04_research_scientist import arxiv_collector as ac
from app.modules.m04_research_scientist import routes

ATOM = b"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
<entry><id>http://arxiv.org/abs/2610.00001v1</id><published>2026-10-01T10:00:00Z</published>
<title>Spatial   immune niches
 in tumors</title><summary>We map spatial immune niches across tumor sections with a long enough abstract.</summary>
<category term="q-bio.QM"/><category term="cs.LG"/></entry>
<entry><id>http://arxiv.org/api/errors#x</id><title>Error</title><summary>bad request</summary></entry>
<entry><id>http://arxiv.org/abs/2610.00002v1</id><title>Short</title><summary>tiny</summary></entry>
</feed>"""

def test_parse_real_shaped_atom_skips_errors_and_stubs():
    ps = ac.parse_arxiv_atom(ATOM)
    assert [p.paper_id for p in ps] == ["arxiv:2610.00001v1"]
    assert ps[0].title == "Spatial immune niches in tumors" and ps[0].keywords == ["q-bio.QM", "cs.LG"]

def test_rejects_dtd_oversize_and_malformed():
    for bad in (b'<!DOCTYPE x [<!ENTITY a "b">]><feed/>', b"<feed", b"x" * (ac.MAX_BYTES + 1)):
        with pytest.raises(ac.ArxivCollectorError):
            ac.parse_arxiv_atom(bad)

def test_url_is_fixed_host_and_terms_are_anded():
    seen = []
    ac.collect_arxiv("graph neural network", 5, fetch=lambda u: seen.append(u) or ATOM)
    assert seen[0].startswith("https://export.arxiv.org/api/query?")
    assert "all%3Agraph+AND+all%3Aneural+AND+all%3Anetwork" in seen[0] and "max_results=5" in seen[0]

@pytest.mark.parametrize("q,n", [("ab", 5), ("x&y=http://evil", 5), ("fine query", 0), ("fine query", 51), ("...", 5)])
def test_bad_inputs_rejected_before_fetch(q, n):
    with pytest.raises(ValueError):
        ac.collect_arxiv(q, n, fetch=lambda u: pytest.fail("fetched"))

def _client(monkeypatch, fn):
    from app.auth.context import TenantContext, require_tenant
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t-arx", actor_id="u")
    monkeypatch.setattr(ac, "collect_arxiv", fn)
    return TestClient(app)

def test_route_error_categories_do_not_echo(monkeypatch):
    def boom(q, n): raise ac.ArxivCollectorError("secret-internal http://x")
    r = _client(monkeypatch, boom).post("/research-scientist/surveillance/collect/arxiv", json={"query": "tumor niches"})
    assert r.status_code == 502 and "secret" not in r.text
    def bad(q, n): raise ValueError("secret-q")
    r = _client(monkeypatch, bad).post("/research-scientist/surveillance/collect/arxiv", json={"query": "tumor niches"})
    assert r.status_code == 422 and "secret" not in r.text

def test_route_ingests_with_local_embedder(monkeypatch):
    c = _client(monkeypatch, lambda q, n: ac.parse_arxiv_atom(ATOM))
    r = c.post("/research-scientist/surveillance/collect/arxiv", json={"query": "tumor niches", "embedding_provider": "lexical"})
    assert r.status_code == 200, r.text
    assert r.json()["fetched"] == 1 and r.json()["source"] == "arxiv"

@pytest.mark.skipif(os.getenv("ATLAS_LIVE_NET") != "1", reason="live network opt-in")
def test_live_arxiv():
    ps = ac.collect_arxiv("transformer", 3)
    assert ps and all(p.source == "arxiv" and p.abstract for p in ps)

def test_route_embedding_failure_is_503_without_echo(monkeypatch):
    c = _client(monkeypatch, lambda q, n: ac.parse_arxiv_atom(ATOM))
    r = c.post("/research-scientist/surveillance/collect/arxiv", json={"query": "tumor niches", "embedding_provider": "ollama"})
    assert r.status_code == 503 and "Errno" not in r.text and "ollama" not in r.text.lower().replace("embedding provider", "")

def test_doctype_alone_rejected():
    with pytest.raises(ac.ArxivCollectorError):
        ac.parse_arxiv_atom(b'<!DOCTYPE feed><feed xmlns="http://www.w3.org/2005/Atom"/>')

def test_default_fetch_refuses_redirect_and_non_200(monkeypatch):
    import httpx
    hits = []
    def handler(req):
        hits.append(str(req.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})
    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(ac.ArxivCollectorError):
        ac.collect_arxiv("tumor niches", 2)
    assert len(hits) == 1 and hits[0].startswith("https://export.arxiv.org/")
