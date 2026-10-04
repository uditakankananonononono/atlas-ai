import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m04_research_scientist import routes
from app.modules.m04_research_scientist.extractive_summary import split_sentences, summarize

ABS = ("Tumor niches shape immune response in solid cancers. We map tumor niches with spatial transcriptomics across 40 samples. "
       "The weather was pleasant during sample collection. Tumor niches with fibroblast signalling predicted immune exclusion. "
       "Funding came from a public grant.")

def test_selected_sentences_are_verbatim_in_original_order_and_title_weighted():
    r = summarize("Tumor niches and immune exclusion", ABS, 3)
    sents = split_sentences(ABS)
    assert [s["text"] for s in r["selected"]] == [sents[s["index"]] for s in r["selected"]]
    assert [s["index"] for s in r["selected"]] == sorted(s["index"] for s in r["selected"])
    picked = {s["index"] for s in r["selected"]}
    assert 2 not in picked and 4 not in picked             # off-topic sentences are not chosen
    assert r["coverage"] == "3 of 5 abstract sentences" and "not abstractive" in r["method"]

def test_title_terms_change_the_ranking():
    doc = "Alpha beta gamma delta. Epsilon zeta eta theta. Alpha beta again here. Epsilon zeta again there."
    a = summarize("alpha beta", doc, 1)["selected"][0]["index"]
    b = summarize("epsilon zeta", doc, 1)["selected"][0]["index"]
    assert a in (0, 2) and b in (1, 3)

def test_max_sentences_and_bounds():
    assert len(summarize("Title", ABS, 1)["selected"]) == 1
    assert len(summarize("Title", ABS, 10)["selected"]) == 5
    for kw in ({"max_sentences": 0}, {"max_sentences": 11}):
        with pytest.raises(ValueError):
            summarize("Title", ABS, **kw)
    with pytest.raises(ValueError):
        summarize("Title", "x" * 50_001)

def test_deterministic_and_known_abbreviations_do_not_split():
    assert summarize("Title", ABS, 2) == summarize("Title", ABS, 2)
    assert split_sentences("See Fig. 2 for details. Next Sentence here.") == ["See Fig. 2 for details.", "Next Sentence here."]
    assert split_sentences("Smith et al. Showed it works. Done now.") == ["Smith et al. Showed it works.", "Done now."]

def test_unknown_abbreviation_still_splits_documented_limit():
    assert len(split_sentences("Measured at Mt. Everest base. Next Sentence here.")) == 3

def test_route_422_and_result(monkeypatch):
    from app.auth.context import TenantContext, require_tenant
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t", actor_id="u")
    c = TestClient(app)
    ok = c.post("/research-scientist/papers/summarize", json={"title": "Tumor niches", "abstract": ABS, "max_sentences": 2})
    assert ok.status_code == 200 and len(ok.json()["selected"]) == 2
    assert c.post("/research-scientist/papers/summarize", json={"title": "Tumor niches", "abstract": "short"}).status_code == 422


# ---- abstractive (model-generated) mode: real local llama.cpp server, no fake generator ----
import os, socket, urllib.parse

def _server_up():
    u = urllib.parse.urlparse(os.getenv("ATLAS_LOCAL_OPENAI_URL", "http://localhost:8080/v1"))
    try:
        socket.create_connection((u.hostname, u.port or 80), 1).close(); return True
    except OSError:
        return False

def test_abstractive_unreachable_server_is_503_not_fake_text(monkeypatch):
    monkeypatch.setenv("ATLAS_LOCAL_OPENAI_URL", "http://127.0.0.1:1/v1")
    from app.core import providers
    providers._BREAKERS["openai_compat"].__init__(3, 30)
    from app.modules.m04_research_scientist.abstractive_summary import summarize_abstractive
    try:
        with pytest.raises(providers.ProviderError):
            summarize_abstractive("Tumor niches", ABS)
    finally:
        providers._BREAKERS["openai_compat"].__init__(3, 30)

def test_abstractive_rejects_non_loopback_endpoint(monkeypatch):
    monkeypatch.setenv("ATLAS_LOCAL_OPENAI_URL", "http://169.254.169.254/v1")
    from app.core import providers
    from app.modules.m04_research_scientist.abstractive_summary import summarize_abstractive
    with pytest.raises(providers.ProviderError, match="not loopback"):
        summarize_abstractive("Tumor niches", ABS)

def test_abstractive_route_503_when_model_down_and_default_stays_extractive(monkeypatch):
    monkeypatch.setenv("ATLAS_LOCAL_OPENAI_URL", "http://127.0.0.1:1/v1")
    from app.core import providers
    app = FastAPI(); app.include_router(routes.router)
    from app.auth.context import TenantContext, require_tenant
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t", actor_id="u")
    c = TestClient(app)
    try:
        r = c.post("/research-scientist/papers/summarize", json={"title": "Tumor niches", "abstract": ABS, "mode": "abstractive"})
        assert r.status_code == 503 and "nothing was generated" in r.text
    finally:
        providers._BREAKERS["openai_compat"].__init__(3, 30)
    assert c.post("/research-scientist/papers/summarize", json={"title": "Tumor niches", "abstract": ABS}).status_code == 200

@pytest.mark.skipif(not _server_up(), reason="needs a running local llama.cpp server (ATLAS_LOCAL_OPENAI_URL)")
def test_abstractive_real_local_model_output_is_labeled():
    from app.modules.m04_research_scientist.abstractive_summary import summarize_abstractive
    r = summarize_abstractive("Tumor niches and immune exclusion", ABS)
    assert r["summary"].strip() and "MODEL-GENERATED" in r["method"] and "not verified" in r["method"]
