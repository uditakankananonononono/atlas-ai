import asyncio, pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m04_research_scientist import routes
from app.modules.m04_research_scientist.surveillance import SurveillancePipeline, SurveillanceRepository, term_cooccurrence_gaps
from app.modules.m04_research_scientist.schemas import PaperInput

class R:
    def __init__(self, title, kw): self.title, self.keywords = title, kw

ROWS = [R("Tumor immune niches", ["spatial", "cancer"]), R("Tumor fibroblast study", ["spatial", "cancer"]),
        R("Quantum control pulses", ["quantum", "optics"]), R("Quantum optics devices", ["quantum", "optics"])]

def test_pairs_each_frequent_but_never_together_are_found_and_cooccurring_are_not():
    g = term_cooccurrence_gaps(ROWS, min_df=2)
    pairs = {(x["term_a"], x["term_b"]) for x in g}
    assert ("cancer", "quantum") in pairs or ("quantum", "cancer") in pairs
    assert not any({a, b} == {"spatial", "cancer"} for a, b in pairs)       # co-occur in 2 papers
    assert not any({a, b} == {"quantum", "optics"} for a, b in pairs)
    one = next(x for x in g if {x["term_a"], x["term_b"]} == {"cancer", "quantum"})
    assert one["papers_with_both"] == 0 and one["corpus_size"] == 4 and "never together" in one["statement"] and "not evidence of global novelty" in one["statement"]

def test_min_df_filters_rare_terms_and_bounds_validated():
    assert term_cooccurrence_gaps([R("Alpha", ["x"]), R("Beta", ["y"])], min_df=2) == []
    for kw in ({"min_df": 0}, {"top_terms": 1}, {"limit": 0}, {"limit": 101}):
        with pytest.raises(ValueError):
            term_cooccurrence_gaps(ROWS, **kw)

def test_limit_and_ranking_deterministic():
    g1 = term_cooccurrence_gaps(ROWS, min_df=2, limit=2); g2 = term_cooccurrence_gaps(ROWS, min_df=2, limit=2)
    assert g1 == g2 and len(g1) == 2

def test_route_is_tenant_scoped_and_labelled(tmp_path):
    from app.auth.context import TenantContext, require_tenant
    class E:
        async def embed(self, texts): return [[1.0, 0.0]] * len(texts)
    mk = lambda i, t, kw: PaperInput(paper_id=i, title=t, abstract="A sufficiently long abstract for this paper.", source="arxiv", keywords=kw)
    papers = [mk("g1", "Tumor immune niches", ["spatial"]), mk("g2", "Tumor fibroblast", ["spatial"]),
              mk("g3", "Quantum control", ["optics"]), mk("g4", "Quantum devices", ["optics"])]
    asyncio.run(SurveillancePipeline(SurveillanceRepository("tg-A"), E()).ingest(papers))
    app = FastAPI(); app.include_router(routes.router); who = {"t": "tg-A"}
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id=who["t"], actor_id="u")
    c = TestClient(app)
    j = c.get("/research-scientist/surveillance/term-gaps").json()
    assert "not global novelty" in j["method"] and j["gaps"]
    who["t"] = "tg-B-empty"
    assert c.get("/research-scientist/surveillance/term-gaps").json()["gaps"] == []
    assert c.get("/research-scientist/surveillance/term-gaps?min_df=0").status_code == 422
