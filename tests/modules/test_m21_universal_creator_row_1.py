import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m21_claire.universal_creator_row_1 import plan

def test_row_1_structures_cross_domain_creation_and_source_grounded_applications():
 result=plan("Apply to genomics summer lab","summer_program_application",[
  {"name":"Lab A","url":"https://lab.example/apply","requirements":["age","transcript"],"preferences":["biology"]},
  {"name":"Lab B","url":"https://b.example/apply","requirements":["age"],"preferences":["coding"]}],
  {"age":17,"biology":"research"})
 assert result["feature_row"]==1 and result["artifact_blueprint"]["sections"][0]=="program_fit"
 assert result["ranked_candidates"][0]["name"]=="Lab B" and result["ranked_candidates"][1]["missing_requirements"]==["transcript"]
 assert result["tool_discovery"]["official_sources_only"] and not result["execution_performed"]

def test_row_1_sign_up_requires_exact_preview_and_prohibits_deceptive_humanization():
 result=plan("Enter debate","competition_application",[],{},["sign_up"])
 assert result["status"]=="exact_preview_required" and result["requires_exact_preview_review"]
 assert "evade detection" in result["humanization"]["forbidden"]
 assert result["result_seeking"]["never_claim_success_without_receipt"]

def test_row_1_negative_paths_reject_unknown_kind_and_unverifiable_source():
 with pytest.raises(ValueError):plan("x","anything",[],{})
 with pytest.raises(ValueError):plan("x","tool_discovery",[{"name":"X","url":"http://unsafe.example","requirements":[]}],{})

def test_row_1_mounted_authenticated_boundary_and_validation():
 c=TestClient(app);url='/api/v1/claire/personalization/universal-creator-row-1/plan'
 h={"X-Tenant-ID":"u","X-Actor-ID":"u"};r=c.post(url,headers=h,json={"goal":"find research tools","kind":"tool_discovery","candidates":[],"owner_facts":{}})
 assert r.status_code==200 and r.json()["feature_row"]==1
 bad=c.post(url,headers=h,json={"goal":"x","kind":"bad","candidates":[],"owner_facts":{}});assert bad.status_code==422

def test_row_1_fit_confidence_tracks_supplied_owner_facts():
 result=plan("Apply","summer_program_application",[{"name":"Lab A","url":"https://a.example","requirements":["age","transcript"],"preferences":["biology"]},{"name":"Lab B","url":"https://b.example","requirements":["age"],"preferences":[]}],{"age":17})
 a,b=result["ranked_candidates"]
 assert a["name"]=="Lab B" and a["fit_confidence"]==1.0
 assert b["fit_confidence"]==pytest.approx(1/3,abs=1e-4) and "unreported facts" in b["fit_uncertainty"]
