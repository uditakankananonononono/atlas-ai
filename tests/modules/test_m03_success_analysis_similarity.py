"""Success analysis: real sparse-vector (TF-IDF) cosine similarity + heading-structure gaps. Local, deterministic, labelled."""
import math, pytest
from app.modules.m03_grant_writer.service import Service
from app.modules.m03_grant_writer.schemas import SuccessAnalysisRequest

class _A:  # approvals sink unused here
    def put(self,i): return i
S=Service(_A(),None,"t")
P="""# Specific Aims
We propose protein folding prediction using transformer models and molecular dynamics simulation for drug discovery.
# Significance
Protein misfolding drives disease."""
NEAR="""# Specific Aims
Protein folding prediction with transformer models and molecular dynamics for drug discovery targets.
# Significance
Misfolded protein drives disease.
# Approach
Run simulations.
# Broader Impacts
Training students."""
FAR="""# Abstract
Coastal fisheries management in estuaries relies on seasonal catch surveys and community outreach.
# Approach
Survey boats weekly.
# Broader Impacts
Fishing cooperatives."""
def run(ex): return S.analyze_success(SuccessAnalysisRequest(proposal=P,funded_examples=ex))

def test_near_example_ranks_above_far_and_cosine_is_bounded():
    r=run([FAR,NEAR])
    assert r.similarity_method=="tfidf-cosine" and r.nearest_examples[0]["example_index"]==1
    assert r.nearest_examples[0]["cosine"]>r.nearest_examples[1]["cosine"]>=0 and all(0<=n["cosine"]<=1.0000001 for n in r.nearest_examples)

def test_identical_text_is_cosine_one_and_disjoint_is_zero():
    assert math.isclose(run([P]).nearest_examples[0]["cosine"],1.0,abs_tol=1e-3)
    assert run(["zzzz qqqq xxxx wwww yyyy vvvv uuuu tttt ssss rrrr"]).nearest_examples[0]["cosine"]==0.0

def test_synonyms_do_not_match_and_the_method_note_says_so():
    r=run([FAR]); assert "NOT neural embeddings" in r.method_note

def test_structure_gaps_need_two_examples_and_flag_missing_headings():
    assert run([NEAR]).structure_gaps==[]
    g=run([NEAR,FAR]).structure_gaps
    assert "approach" in g and "broader impacts" in g and "specific aims" not in g

def test_no_examples_performs_no_comparison():
    r=run([]); assert r.similarity_method=="none" and r.nearest_examples==[] and "no success comparison" in r.caveat

def test_route_returns_the_new_fields():
    from fastapi import FastAPI; from fastapi.testclient import TestClient
    from app.modules.m03_grant_writer.routes import router, get_service
    app=FastAPI(); app.include_router(router,prefix="/api"); app.dependency_overrides[get_service]=lambda:S
    r=TestClient(app).post("/api/grant-writer/success-analysis",json={"proposal":P,"funded_examples":[NEAR,FAR]})
    assert r.status_code==200 and r.json()["similarity_method"]=="tfidf-cosine" and r.json()["nearest_examples"][0]["example_index"]==0

def test_a_heading_used_by_only_one_of_three_examples_is_not_a_gap():
    ONE="# Abstract\nx\n# Unique Section\ny"
    assert "unique section" not in run([NEAR,FAR,ONE]).structure_gaps
    assert "approach" in run([NEAR,FAR,ONE]).structure_gaps
