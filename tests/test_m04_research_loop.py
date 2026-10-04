import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m04_research_scientist import research_loop as rl, routes
from app.modules.m04_research_scientist.schemas import PaperInput

def P(i, title, abs_): return PaperInput(paper_id=i, title=title, abstract=abs_ + " padding text for length requirement", source="arxiv")

CORPUS = {
 "p1": P("p1", "Spatial immune niches", "tumor microenvironment spatial transcriptomics immune niches"),
 "p2": P("p2", "Tumor niche mapping", "tumor microenvironment spatial transcriptomics fibroblast mapping"),
 "p3": P("p3", "Fibroblast signalling", "fibroblast signalling tumor microenvironment crosstalk"),
}

def fake_collector(log):
    def c(q, n):
        log.append(q)
        terms = set(q.split())
        hits = [p for p in CORPUS.values() if terms & set(rl.key_terms(p.title + " " + p.abstract))]
        return hits[:n]
    return c

def test_loop_expands_query_from_retrieved_terms_and_records_trail():
    log = []
    res = rl.run_loop("How do immune niches shape tumor spatial transcriptomics?", {"arxiv": fake_collector(log)}, max_steps=3)
    assert log[0] == "immune niches shape tumor spatial transcriptomics"
    assert len(log) >= 2 and log[1].startswith(log[0]) and len(log[1]) > len(log[0])  # expanded by real retrieved terms
    assert set(res.papers) == {"p1", "p2", "p3"}
    assert res.steps[0].new_paper_ids and res.stop_reason in {"no_new_papers", "no_new_terms", "max_steps"}

def test_stops_when_no_new_papers():
    res = rl.run_loop("quantum gravity condensates entangled", {"arxiv": lambda q, n: []}, max_steps=3)
    assert res.stop_reason == "no_new_papers" and len(res.steps) == 1

def test_max_steps_bound_and_validation():
    for kw in ({"max_steps": 0}, {"max_steps": 4}, {"per_step": 0}, {"per_step": 21}):
        with pytest.raises(ValueError):
            rl.run_loop("immune niches tumor", {"arxiv": lambda q, n: []}, **kw)
    with pytest.raises(ValueError):
        rl.run_loop("the and for are", {"arxiv": lambda q, n: []})

def test_papers_deduplicated_across_steps_and_sources():
    c = fake_collector([])
    res = rl.run_loop("immune niches tumor microenvironment", {"arxiv": c, "pubmed": c}, max_steps=2)
    assert len(res.papers) == 3
    assert sum(len(s.new_paper_ids) for s in res.steps) == 3  # second source adds nothing new

def _client(monkeypatch, fn):
    from app.auth.context import TenantContext, require_tenant
    from app.modules.m04_research_scientist import arxiv_collector as ac
    monkeypatch.setattr(ac, "collect_arxiv", fn)
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t", actor_id="u")
    return TestClient(app)

def test_route_labels_method_and_returns_trail(monkeypatch):
    r = _client(monkeypatch, fake_collector([])).post("/research-scientist/research-loop",
        json={"question": "How do immune niches shape tumor spatial transcriptomics?", "max_steps": 2})
    j = r.json()
    assert r.status_code == 200 and "no language model" in j["method"] and j["steps"] and len(j["papers"]) == 3

def test_route_error_mapping_fixed_messages(monkeypatch):
    from app.modules.m04_research_scientist import arxiv_collector as ac
    def boom(q, n): raise ac.ArxivCollectorError("secret")
    r = _client(monkeypatch, boom).post("/research-scientist/research-loop", json={"question": "immune niches tumor spatial"})
    assert r.status_code == 502 and "secret" not in r.text
    assert _client(monkeypatch, boom).post("/research-scientist/research-loop", json={"question": "short"}).status_code == 422

def test_expansion_skips_stopwords_and_plural_of_used_terms():
    mk = lambda i, ti, ab: PaperInput(paper_id=i, title=ti, abstract=ab, source="arxiv")
    docs = [mk("a", "Graph networks", "but network graph networks messaging passing molecule"),
            mk("b", "More graphs", "but network graph networks messaging passing molecule")]
    q = []
    rl.run_loop("graph networks molecules properties", {"arxiv": lambda s, n: (q.append(s), docs)[1]}, max_steps=2)
    assert len(q) == 2 and q[1].split()[-1] in {"messaging", "passing", "molecule"}
    assert "but" not in q[1].split() and "network" not in q[1].split()[4:]

def test_deadline_stops_with_partial_trail_before_next_call():
    now = [0.0]
    vals = list(CORPUS.values()); k = []
    def c(q, n):
        now[0] += 40; k.append(1); return vals[:len(k) + 1]
    res = rl.run_loop("immune niches tumor microenvironment", {"arxiv": c}, max_steps=3, deadline_s=60, clock=lambda: now[0])
    assert res.stop_reason == "deadline" and res.status == "partial" and len(res.steps) == 2 and len(res.papers) == 3

def test_mid_step_error_keeps_prior_papers_and_is_not_success():
    calls = []
    def c(q, n):
        calls.append(q)
        if len(calls) == 2: raise RuntimeError("secret upstream text")
        return list(CORPUS.values())
    res = rl.run_loop("immune niches tumor microenvironment", {"arxiv": c}, max_steps=3)
    assert res.status == "partial" and res.stop_reason == "collector_error" and res.error == "RuntimeError"
    assert len(res.papers) == 3 and len(res.steps) == 1 and "secret" not in repr(res.error)

def test_first_step_error_is_failed_and_route_502(monkeypatch):
    from app.modules.m04_research_scientist import arxiv_collector as ac
    def boom(q, n): raise ac.ArxivCollectorError("secret")
    r = _client(monkeypatch, boom).post("/research-scientist/research-loop", json={"question": "immune niches tumor spatial"})
    assert r.status_code == 502 and "secret" not in r.text

def test_route_partial_failure_is_200_with_status_partial(monkeypatch):
    from app.modules.m04_research_scientist import arxiv_collector as ac
    n = []
    def c(q, k):
        n.append(1)
        if len(n) > 1: raise ac.ArxivCollectorError("x")
        return list(CORPUS.values())
    j = _client(monkeypatch, c).post("/research-scientist/research-loop", json={"question": "immune niches tumor spatial", "max_steps": 3}).json()
    assert j["status"] == "partial" and j["error"] == "ArxivCollectorError" and len(j["papers"]) == 3

def test_remote_record_validation_error_is_collector_error_not_422(monkeypatch):
    from app.modules.m04_research_scientist import pubmed_collector as pc
    x = b"<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>" + b"9" * 300 + b"</PMID><Article><ArticleTitle>A title</ArticleTitle><Abstract><AbstractText>An abstract that is long enough.</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
    with pytest.raises(pc.PubmedCollectorError):
        pc.parse_pubmed_xml(x)
    from app.auth.context import TenantContext, require_tenant
    monkeypatch.setattr(pc, "collect_pubmed", lambda q, n: pc.parse_pubmed_xml(x))
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t", actor_id="u")
    r = TestClient(app).post("/research-scientist/surveillance/collect/pubmed", json={"query": "tumor niches"})
    assert r.status_code == 502
