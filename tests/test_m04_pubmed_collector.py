import json, os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m04_research_scientist import pubmed_collector as pc, routes
from app.modules.m04_research_scientist.source_throttle import SourceThrottle

XML = b"""<?xml version="1.0"?><!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD" "x.dtd"><PubmedArticleSet>
<PubmedArticle><MedlineCitation><PMID>111</PMID><Article><Journal><JournalIssue><PubDate><Year>2026</Year></PubDate></JournalIssue></Journal>
<ArticleTitle>Spatial niches in <i>tumors</i></ArticleTitle><Abstract><AbstractText Label="A">First part of the abstract.</AbstractText><AbstractText>Second part here.</AbstractText></Abstract></Article>
<MeshHeadingList><MeshHeading><DescriptorName>Humans</DescriptorName></MeshHeading></MeshHeadingList></MedlineCitation></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>222</PMID><Article><ArticleTitle>No abstract record</ArticleTitle></Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""

def test_parse_skips_missing_abstract_and_joins_parts():
    ps = pc.parse_pubmed_xml(XML)
    assert [p.paper_id for p in ps] == ["pubmed:111"]
    assert ps[0].title == "Spatial niches in tumors" and ps[0].abstract == "First part of the abstract. Second part here."
    assert ps[0].keywords == ["Humans"] and str(ps[0].url) == "https://pubmed.ncbi.nlm.nih.gov/111/"

def test_entities_and_malformed_rejected():
    for bad in (b'<!DOCTYPE a [<!ENTITY x "y">]><a/>', b"<a"):
        with pytest.raises(pc.PubmedCollectorError):
            pc.parse_pubmed_xml(bad)

def test_two_step_fetch_filters_non_numeric_ids_and_uses_fixed_host():
    urls = []
    def fetch(u):
        urls.append(u)
        return json.dumps({"esearchresult": {"idlist": ["111", "x&db=evil", "../9"]}}).encode() if "esearch" in u else XML
    ps = pc.collect_pubmed("tumor niches", 5, fetch=fetch)
    assert len(ps) == 1 and all(u.startswith("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/") for u in urls)
    assert "id=111&" in urls[1] + "&" or urls[1].endswith("id=111") or "id=111" in urls[1]
    assert "evil" not in urls[1] and "tool=atlas-m04" in urls[0]

def test_empty_search_makes_no_efetch():
    urls = []
    assert pc.collect_pubmed("tumor niches", 5, fetch=lambda u: urls.append(u) or b'{"esearchresult":{"idlist":[]}}') == []
    assert len(urls) == 1

@pytest.mark.parametrize("q,n", [("ab", 5), ("a;b rm", 5), ("fine query", 0), ("fine query", 51)])
def test_bad_inputs(q, n):
    with pytest.raises(ValueError):
        pc.collect_pubmed(q, n, fetch=lambda u: pytest.fail("fetched"))

def test_bad_esearch_shape():
    with pytest.raises(pc.PubmedCollectorError):
        pc.collect_pubmed("tumor niches", 5, fetch=lambda u: b"{}")

def test_throttle_spaces_calls_per_source(tmp_path):
    now = [100.0]; slept = []
    t = SourceThrottle(clock=lambda: now[0], sleep=lambda s: (slept.append(s), now.__setitem__(0, now[0] + s)), state_dir=tmp_path)
    t.run("arxiv", lambda: 1); t.run("arxiv", lambda: 1)
    now[0] += 1.0; t.run("arxiv", lambda: 1)
    t.run("pubmed", lambda: 1)
    assert slept == [3.0, 2.0]

def test_throttle_records_time_even_when_call_fails(tmp_path):
    now = [100.0]; slept = []
    t = SourceThrottle(clock=lambda: now[0], sleep=lambda s: slept.append(s), state_dir=tmp_path)
    with pytest.raises(RuntimeError):
        t.run("pubmed", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    t.run("pubmed", lambda: 1)
    assert slept == [0.4]

def test_throttle_ignores_future_stamp(tmp_path):
    (tmp_path / "atlas-collector-arxiv.stamp").write_text("99999999999")
    slept = []
    SourceThrottle(clock=lambda: 100.0, sleep=slept.append, state_dir=tmp_path).run("arxiv", lambda: 1)
    assert slept == []

def test_throttle_spaces_across_processes(tmp_path):
    import subprocess, sys, textwrap
    code = textwrap.dedent(f"""
        import time, sys
        from app.modules.m04_research_scientist.source_throttle import SourceThrottle
        t = SourceThrottle(state_dir={str(tmp_path)!r})
        stamps = [t.run("pubmed", time.time) for _ in range(3)]
        print(*stamps)
    """)
    ps = [subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, cwd=os.getcwd() + "/backend") for _ in range(3)]
    stamps = sorted(float(x) for p in ps for x in p.communicate()[0].split())
    assert len(stamps) == 9
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    assert min(gaps) >= 0.35, gaps  # 0.4s spacing across 3 processes, small timing slack

def test_arxiv_collect_goes_through_throttle(monkeypatch):
    from app.modules.m04_research_scientist import arxiv_collector as ac
    calls = []
    monkeypatch.setattr(ac.THROTTLE, "run", lambda s, fn: (calls.append(s), fn())[1])
    ac.collect_arxiv("tumor niches", 2, fetch=lambda u: b"<feed xmlns='http://www.w3.org/2005/Atom'/>")
    assert calls == ["arxiv"]

def _client(monkeypatch, fn):
    from app.auth.context import TenantContext, require_tenant
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t-pm", actor_id="u")
    monkeypatch.setattr(pc, "collect_pubmed", fn)
    return TestClient(app)

def test_route_ingest_and_fixed_errors(monkeypatch):
    r = _client(monkeypatch, lambda q, n: pc.parse_pubmed_xml(XML)).post(
        "/research-scientist/surveillance/collect/pubmed", json={"query": "tumor niches"})
    assert r.status_code == 200 and r.json()["source"] == "pubmed" and r.json()["fetched"] == 1
    def boom(q, n): raise pc.PubmedCollectorError("secret-url")
    r = _client(monkeypatch, boom).post("/research-scientist/surveillance/collect/pubmed", json={"query": "tumor niches"})
    assert r.status_code == 502 and "secret" not in r.text

@pytest.mark.skipif(os.getenv("ATLAS_LIVE_NET") != "1", reason="live network opt-in")
def test_live_pubmed():
    ps = pc.collect_pubmed("spatial transcriptomics", 2)
    assert ps and all(p.source == "pubmed" for p in ps)

def test_cross_tenant_isolation(monkeypatch):
    from app.auth.context import TenantContext, require_tenant
    from app.modules.m04_research_scientist.surveillance import SurveillanceRepository
    monkeypatch.setattr(pc, "collect_pubmed", lambda q, n: pc.parse_pubmed_xml(XML))
    app = FastAPI(); app.include_router(routes.router)
    who = {"t": "tenant-A"}
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id=who["t"], actor_id="u")
    c = TestClient(app)
    assert c.post("/research-scientist/surveillance/collect/pubmed", json={"query": "tumor niches"}).json()["created"] in (0, 1)
    assert len(SurveillanceRepository("tenant-A").rows()) >= 1
    assert SurveillanceRepository("tenant-B-never-ingested").rows() == []

def test_utf16_declared_dtd_cannot_bypass():
    from app.modules.m04_research_scientist import arxiv_collector as ac
    doc = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE feed [<!ENTITY a "b">]><feed xmlns="http://www.w3.org/2005/Atom"/>'.encode("utf-16")
    with pytest.raises(ac.ArxivCollectorError):
        ac.parse_arxiv_atom(doc)
    with pytest.raises(pc.PubmedCollectorError):
        pc.parse_pubmed_xml(b'<!DOCTYPE a [<!ENTITY x "y">]><a>&x;</a>')

def test_response_streamed_with_cap(monkeypatch):
    import httpx
    from app.modules.m04_research_scientist import arxiv_collector as ac
    monkeypatch.setattr(ac, "MAX_BYTES", 1000)
    chunks = []
    def gen():
        for _ in range(100):
            chunks.append(1); yield b"x" * 100
    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=gen())), **kw))
    with pytest.raises(ac.ArxivCollectorError):
        ac.capped_get("https://export.arxiv.org/x", 1000, ac.ArxivCollectorError)
    assert len(chunks) < 100  # stopped reading early

def test_remote_ids_must_be_valid_format():
    from app.modules.m04_research_scientist import arxiv_collector as ac
    bad = ATOM_BAD = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/../../etc/x</id><title>Bad id title</title><summary>long enough summary text for the abstract</summary></entry>
    <entry><id>http://arxiv.org/abs/2610.00009v2</id><title>Good id title</title><summary>long enough summary text for the abstract</summary></entry>
    <entry><id>http://arxiv.org/abs/cs.LG/0701001v1</id><title>Old id title</title><summary>long enough summary text for the abstract</summary></entry></feed>"""
    assert [p.paper_id for p in ac.parse_arxiv_atom(bad)] == ["arxiv:2610.00009v2", "arxiv:cs.LG/0701001v1"]

def test_non_numeric_pmid_skipped():
    x = XML.replace(b"<PMID>111</PMID>", b"<PMID>1/../x</PMID>")
    assert pc.parse_pubmed_xml(x) == []

def test_programming_errors_are_not_masked_as_502(monkeypatch):
    def bug(q, n): raise KeyError("programming bug")
    c = _client(monkeypatch, bug)
    with pytest.raises(KeyError):  # propagates (server would return 500), not a masked 502
        c.post("/research-scientist/surveillance/collect/pubmed", json={"query": "tumor niches"})
