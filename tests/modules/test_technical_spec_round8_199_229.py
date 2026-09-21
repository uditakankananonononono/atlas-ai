"""Exact substantive coverage for technical-spec ledger rows 199-229."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.technical_spec_round8_199_229 import (
 ROWS,PRODUCTION_ROWS,semantic_behavior,safety_replacement,verify_production,mapping
)
from app.modules.m20_general_cognitive_worker.technical_spec_routes_round8_199_229 import router

def test_row_199_m20_27_semantic_behavior():
 result=semantic_behavior(199,{'ideas': ['cheap solar sensor', 'solar sensor with offline sync'], 'constraints': ['solar', 'offline']})
 assert result.mapping.requirement_id=='M20-27' and result.status=="implemented"
 assert result.output

def test_row_200_m20_28_semantic_behavior():
 result=semantic_behavior(200,{'task_id': 't1', 'went_well': ['tests'], 'improve': ['latency'], 'lessons': ['cache deterministic results']})
 assert result.mapping.requirement_id=='M20-28' and result.status=="implemented"
 assert result.output

def test_row_201_m20_29_semantic_behavior():
 result=semantic_behavior(201,{'tone': 'formal'})
 assert result.mapping.requirement_id=='M20-29' and result.status=="implemented"
 assert result.output

def test_row_202_m20_30_semantic_behavior():
 result=semantic_behavior(202,{'confidence': 0.4, 'high_stakes': True, 'missing_question': 'Which account?'})
 assert result.mapping.requirement_id=='M20-30' and result.status=="implemented"
 assert result.output

def test_row_203_m20_31_semantic_behavior():
 result=semantic_behavior(203,{'mode': 'creative', 'domains': ['biology', 'art']})
 assert result.mapping.requirement_id=='M20-31' and result.status=="implemented"
 assert result.output

def test_row_204_m20_32_semantic_behavior():
 result=semantic_behavior(204,{'streams': ['market_analysis', 'pitch_deck', 'mvp']})
 assert result.mapping.requirement_id=='M20-32' and result.status=="implemented"
 assert result.output

def test_row_205_m20_33_semantic_behavior():
 result=semantic_behavior(205,{'cadence': '0 9 * * *', 'timezone': 'Asia/Kolkata'})
 assert result.mapping.requirement_id=='M20-33' and result.status=="implemented"
 assert result.output

def test_row_206_m20_34_semantic_behavior():
 result=semantic_behavior(206,{'action': 'financial_transaction', 'approved': True})
 assert result.mapping.requirement_id=='M20-34' and result.status=="implemented"
 assert result.output
 assert result.output["allowed"] is False

def test_row_207_m20_35_semantic_behavior():
 result=semantic_behavior(207,{'project_id': 'atlas', 'api_allowlist': ['https://api.example.test']})
 assert result.mapping.requirement_id=='M20-35' and result.status=="implemented"
 assert result.output

def test_row_208_x01_requires_literal_external_attestation():
 result=verify_production(208,{"config":"present"})
 assert result.mapping.requirement_id=='X01'
 assert result.status=="missing_evidence" and result.output["verified"] is False

def test_row_209_x02_requires_literal_external_attestation():
 result=verify_production(209,{"config":"present"})
 assert result.mapping.requirement_id=='X02'
 assert result.status=="missing_evidence" and result.output["verified"] is False

def test_row_210_x03_requires_literal_external_attestation():
 result=verify_production(210,{"config":"present"})
 assert result.mapping.requirement_id=='X03'
 assert result.status=="missing_evidence" and result.output["verified"] is False

def test_row_211_x04_requires_literal_external_attestation():
 result=verify_production(211,{"config":"present"})
 assert result.mapping.requirement_id=='X04'
 assert result.status=="missing_evidence" and result.output["verified"] is False

def test_row_212_x05_requires_literal_external_attestation():
 result=verify_production(212,{"config":"present"})
 assert result.mapping.requirement_id=='X05'
 assert result.status=="missing_evidence" and result.output["verified"] is False

def test_row_213_x06_semantic_behavior():
 result=semantic_behavior(213,{'tenant_id': 't1', 'module': '20', 'model': 'model-a', 'input_ref': 'sha256:input', 'output_ref': 'sha256:output', 'latency_ms': 42})
 assert result.mapping.requirement_id=='X06' and result.status=="implemented"
 assert result.output

def test_row_214_x07_semantic_behavior():
 result=semantic_behavior(214,{'thresholds': {'20': 1}, 'module': '20', 'model': 'large', 'cost': 0.25})
 assert result.mapping.requirement_id=='X07' and result.status=="implemented"
 assert result.output

def test_row_215_x08_semantic_behavior():
 result=semantic_behavior(215,{'thresholds': {'20': 0.1}, 'module': '20', 'model': 'large', 'cost': 0.25})
 assert result.mapping.requirement_id=='X08' and result.status=="implemented"
 assert result.output

def test_row_216_x09_semantic_behavior():
 result=semantic_behavior(216,{'thresholds': {'20': 0.1}, 'module': '20', 'model': 'large', 'cost': 0.25, 'critical': False})
 assert result.mapping.requirement_id=='X09' and result.status=="implemented"
 assert result.output

def test_row_217_x10_semantic_behavior():
 result=semantic_behavior(217,{'tenant_id': 'a', 'resource_tenant_id': 'b'})
 assert result.mapping.requirement_id=='X10' and result.status=="implemented"
 assert result.output
 assert result.output["allowed"] is False

def test_row_218_x11_requires_literal_external_attestation():
 result=verify_production(218,{"config":"present"})
 assert result.mapping.requirement_id=='X11'
 assert result.status=="missing_evidence" and result.output["verified"] is False

def test_row_219_x12_requires_literal_external_attestation():
 result=verify_production(219,{"config":"present"})
 assert result.mapping.requirement_id=='X12'
 assert result.status=="missing_evidence" and result.output["verified"] is False

def test_row_220_x13_requires_literal_external_attestation():
 result=verify_production(220,{"config":"present"})
 assert result.mapping.requirement_id=='X13'
 assert result.status=="missing_evidence" and result.output["verified"] is False

def test_row_221_x14_requires_literal_external_attestation():
 result=verify_production(221,{"config":"present"})
 assert result.mapping.requirement_id=='X14'
 assert result.status=="missing_evidence" and result.output["verified"] is False

def test_row_222_s01_rejects_and_replaces_prohibited_behavior():
 result=safety_replacement(222,'stealth fingerprint spoof')
 assert result.mapping.requirement_id=='S01'
 assert result.status=="rejected" and result.output["blocked"] is True
 assert result.output["executed"] is False and result.output["replacement"]

def test_row_223_s02_rejects_and_replaces_prohibited_behavior():
 result=safety_replacement(223,'Discord self-bot using user token')
 assert result.mapping.requirement_id=='S02'
 assert result.status=="rejected" and result.output["blocked"] is True
 assert result.output["executed"] is False and result.output["replacement"]

def test_row_224_s03_rejects_and_replaces_prohibited_behavior():
 result=safety_replacement(224,'Sales Navigator scraping')
 assert result.mapping.requirement_id=='S03'
 assert result.status=="rejected" and result.output["blocked"] is True
 assert result.output["executed"] is False and result.output["replacement"]

def test_row_225_s04_rejects_and_replaces_prohibited_behavior():
 result=safety_replacement(225,'unofficial TikTok rotating residential proxy')
 assert result.mapping.requirement_id=='S04'
 assert result.status=="rejected" and result.output["blocked"] is True
 assert result.output["executed"] is False and result.output["replacement"]

def test_row_226_s05_rejects_and_replaces_prohibited_behavior():
 result=safety_replacement(226,'store hidden chain-of-thought')
 assert result.mapping.requirement_id=='S05'
 assert result.status=="rejected" and result.output["blocked"] is True
 assert result.output["executed"] is False and result.output["replacement"]

def test_row_227_s06_rejects_and_replaces_prohibited_behavior():
 result=safety_replacement(227,'real emotion emotional state vector')
 assert result.mapping.requirement_id=='S06'
 assert result.status=="rejected" and result.output["blocked"] is True
 assert result.output["executed"] is False and result.output["replacement"]

def test_row_228_s07_rejects_and_replaces_prohibited_behavior():
 result=safety_replacement(228,'AGI-class human-level any non-physical job')
 assert result.mapping.requirement_id=='S07'
 assert result.status=="rejected" and result.output["blocked"] is True
 assert result.output["executed"] is False and result.output["replacement"]

def test_row_229_s08_rejects_and_replaces_prohibited_behavior():
 result=safety_replacement(229,'auto-execute email without approval')
 assert result.mapping.requirement_id=='S08'
 assert result.status=="rejected" and result.output["blocked"] is True
 assert result.output["executed"] is False and result.output["replacement"]

def test_route_is_mounted_and_preserves_source_mapping():
 app=FastAPI();app.include_router(router)
 client=TestClient(app)
 listing=client.get("/technical-spec/199-229/requirements")
 assert listing.status_code==200 and len(listing.json())==31
 assert listing.json()[0]["source_line_start"]==162
 response=client.post("/technical-spec/199-229/222",json={"payload":{"mechanism":"stealth evasion patch"}})
 assert response.status_code==200 and response.json()["status"]=="rejected"

def test_unknown_row_and_wrong_execution_mode_fail_closed():
 with pytest.raises(ValueError,match="unknown technical-spec row"): mapping(999)
 with pytest.raises(ValueError,match="production attestation or safety replacement"):
  semantic_behavior(208,{})

def test_production_attestation_rejects_empty_references_and_accepts_literal_evidence():
 rejected=verify_production(208,{},lambda rid,evidence:(True,()))
 assert rejected.status=="missing_evidence"
 accepted=verify_production(208,{"probe":"ok"},lambda rid,evidence:(True,("attestation://mtls/probe-1",)))
 assert accepted.status=="verified" and accepted.evidence==( "attestation://mtls/probe-1",)

def test_safety_replacement_never_executes_even_for_unrecognized_wording():
 result=safety_replacement(229,"publish report")
 assert result.status=="replacement_required" and result.output["executed"] is False
