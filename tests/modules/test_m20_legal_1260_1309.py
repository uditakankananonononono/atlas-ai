import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.legal_support_1260_1309 import SPECS,analyze_legal_feature
from app.modules.m20_general_cognitive_worker.routes import router

AUTH={"id":"A1","title":"Current primary authority","citation":"J 1","source_url":"https://law.example/j1","jurisdiction":"J","effective_date":"2026-01-01","last_checked_at":"2026-09-21","valid_through":"2027-01-01","authority_type":"primary"}
BASE={"jurisdiction":"J","as_of":"2026-09-21","authorities":[AUTH],"sourced_facts":[{"text":"The supplied record says X","source_ids":["A1"]}],"user_assertions":["Client says Y"],"analysis":[{"proposition":"Counsel should compare X and Y","authority_ids":["A1"]}],"row_inputs":{"record_id":"r1"}}

def run(fid,data=None,tenant="t1",actor="u1"):
 return analyze_legal_feature(fid,BASE if data is None else data,tenant_id=tenant,actor_id=actor)

def test_every_row_1260_1309_has_distinct_keyed_behavior_and_provenance():
 assert list(SPECS)==list(range(1260,1310))
 keys=set(); mechanisms=set()
 for fid,spec in SPECS.items():
  out=run(fid); key=spec["output_key"]; artifact=out[key]
  keys.add(key); mechanisms.add(artifact["mechanism"])
  assert out["feature_id"]==fid and out["method"]==spec["method"]
  assert out["jurisdiction"]=="J" and out["as_of"]=="2026-09-21"
  assert out["provenance"]["authorities"][0]["source_url"]==AUTH["source_url"]
  assert artifact["review_state"]=="counsel_review_required"
  assert out["legal_conclusion"] is None and out["filing_or_external_effect"] is False
 assert len(keys)==50 and len(mechanisms)==50

def test_1260_sentencing_guidelines_keeps_assertions_separate_from_sourced_facts():
 o=run(1260); a=o["guideline_calculation_map"]
 assert a["sourced_facts"][0]["status"]=="sourced"
 assert a["user_assertions"]==["Client says Y"] and "sentence" in a["mechanism"]

def test_1275_arbitration_surfaces_contrary_and_foreign_authority_conflicts():
 adverse={**AUTH,"id":"A2","citation":"Other 2","jurisdiction":"K","contrary":True}
 d={**BASE,"authorities":[AUTH,adverse]}; a=run(1275,d)["arbitration_clause_map"]
 assert {x["reason"] for x in a["conflicts"]}=={"contrary authority supplied","jurisdiction mismatch"}
 assert a["review_state"]=="blocked"

def test_1290_legal_ethics_blocks_missing_authority_and_never_clears_duty():
 d={**BASE,"analysis":[{"proposition":"A consent may be needed","authority_ids":["MISSING"]}]}
 a=run(1290,d)["ethics_duty_map"]
 assert a["missing_authority"]==["A consent may be needed"] and a["review_state"]=="blocked"

def test_1298_legal_technology_flags_stale_source():
 stale={**AUTH,"last_checked_at":"2025-01-01","valid_through":"2025-02-01"}
 d={**BASE,"authorities":[stale]}; a=run(1298,d)["legal_technology_control_map"]
 assert a["stale_source_ids"]==["A1"] and a["review_state"]=="blocked"

def test_1303_legal_operations_is_actor_and_tenant_scoped():
 o=run(1303,tenant="tenant-a",actor="lawyer-7")
 assert o["isolation"]=={"tenant_id":"tenant-a","actor_id":"lawyer-7","cross_tenant_data":False}
 with pytest.raises(ValueError,match="cross-tenant"): run(1303,{**BASE,"tenant_id":"tenant-b"},tenant="tenant-a")

def test_1309_legal_education_requires_complete_authority_provenance():
 bad={k:v for k,v in AUTH.items() if k!="effective_date"}
 with pytest.raises(ValueError,match="effective_date"): run(1309,{**BASE,"authorities":[bad]})

def test_typed_validation_rejects_bad_date_url_empty_actor_and_unsupported_row():
 with pytest.raises(ValueError,match="ISO"): run(1262,{**BASE,"as_of":"soon"})
 with pytest.raises(ValueError,match="http"): run(1262,{**BASE,"authorities":[{**AUTH,"source_url":"file:///tmp/x"}]})
 with pytest.raises(ValueError,match="actor_id"): analyze_legal_feature(1262,BASE,tenant_id="t",actor_id="")
 with pytest.raises(ValueError,match="between"): analyze_legal_feature(1310,BASE,tenant_id="t",actor_id="a")

def test_exact_route_mount_returns_row_specific_artifact_and_rejects_cross_tenant():
 app=FastAPI(); app.include_router(router); client=TestClient(app)
 body={"feature_id":1301,"tenant_id":"tenant-a","actor_id":"reviewer-1","data":BASE}
 r=client.post("/api/modules/20/legal-1260-1309/support",json=body)
 assert r.status_code==200 and r.json()["result"]["coding_validation_map"]["mechanism"]==SPECS[1301]["mechanism"]
 body["data"]={**BASE,"tenant_id":"tenant-b"}
 assert client.post("/api/modules/20/legal-1260-1309/support",json=body).status_code==422

# Explicit row-level collection names make each ledger stamp independently auditable.
def _row_case(fid):
 def case():
  spec=SPECS[fid]; out=run(fid); artifact=out[spec["output_key"]]
  assert artifact["mechanism"]==spec["mechanism"]
  assert out["provenance"]["authority_count"]==1
  assert out["legal_conclusion"] is None and not out["filing_or_external_effect"]
 case.__name__=f"test_row_{fid}_{SPECS[fid]['method']}"
 return case
for _fid in range(1260,1310): globals()[f"test_row_{_fid}_{SPECS[_fid]['method']}"]=_row_case(_fid)
del _fid
