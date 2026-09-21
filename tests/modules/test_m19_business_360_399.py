from datetime import datetime,timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m19_idea_incubator.business_models import *
from app.modules.m19_idea_incubator.business_service import BusinessAnalysisService
from app.modules.m19_idea_incubator.business_router import router

P=Provenance(source_id="analytics-1",source_type="analytics",observed_at=datetime.now(timezone.utc))
def req(feature,inputs,confidence=.8):return BusinessAnalysisRequest(feature=feature,inputs=inputs,provenance=[P],confidence=confidence)
def service():return BusinessAnalysisService()

def test_360_market_sizing_is_input_bound():
 a=service().analyze("i",req(360,{"total_entities":1000,"annual_revenue_per_entity":100,"serviceable_fraction":.5,"obtainable_fraction":.1,"currency":"USD"}));assert (a.result["tam"],a.result["sam"],a.result["som"])==(100000,50000,5000);assert a.provenance[0].source_id=="analytics-1"

@pytest.mark.parametrize("row,inputs,key",[
 (378,{"invitations_per_user":3,"invite_conversion_rate":.4,"cycle_days":7},"viral_coefficient"),(379,{"acquisition_spend":1000,"new_customers":20},"cac"),(380,{"average_revenue_per_period":20,"gross_margin_rate":.8,"periodic_churn_rate":.1},"ltv"),(381,{"revenue_per_unit":100,"variable_cost_per_unit":40,"fixed_costs":1000,"units":100,"cac":20},"contribution_margin_per_unit"),(383,{"starting":100,"remaining":80},"retention_rate"),(385,{"scores":[10,9,8,6]},"nps"),(388,{"items":[{"id":"a","reach":100,"impact":2,"confidence":.8,"effort":4},{"id":"b","reach":20,"impact":1,"confidence":1,"effort":2}]},"ranked_items"),(392,{"completed_points":[10,20,30],"planned_points":[20,20,30]},"average_velocity")])
def test_metric_rows(row,inputs,key):assert key in service().analyze("i",req(row,inputs)).result

def test_382_cohorts():assert service().analyze("i",req(382,{"cohorts":{"jan":[100,80,60]}})).result["retention_curves"]["jan"]==[1,0.8,0.6]

def test_399_significance_reports_uncertainty_and_warning():
 a=service().analyze("i",req(399,{"control_conversions":100,"control_total":1000,"variant_conversions":140,"variant_total":1000,"alpha":.05,"minimum_effect":.02}));assert a.result["statistically_significant"] is True;assert a.result["practically_significant"] is True;assert a.uncertainty.interval_low is not None;assert "peeking" in a.result["warning"]

def test_no_provenance_and_empty_inputs_rejected():
 with pytest.raises(Exception):BusinessAnalysisRequest(feature=360,inputs={},provenance=[],confidence=.5)

def test_public_source_without_uri_is_flagged():
 p=Provenance(source_id="report",source_type="public_source",observed_at=datetime.now(timezone.utc));a=service().analyze("i",BusinessAnalysisRequest(feature=379,inputs={"acquisition_spend":10,"new_customers":1},provenance=[p],confidence=.8));assert "lacks a URI" in a.uncertainty.limitations[0]

QUAL={361:{"competitors":[{"id":"A","scores":{"price":4}}],"criteria":[{"id":"price","weight":1}]},362:{"supplier_power":"low","buyer_power":"high","new_entrants":"medium","substitutes":"medium","rivalry":"high"},363:{"customer_jobs":["x"],"pains":["p"],"gains":["g"],"products_services":["s"],"pain_relievers":["r"],"gain_creators":["c"]},364:{"partners":["p"],"activities":["a"],"resources":["r"],"value_propositions":["v"],"relationships":["r"],"channels":["c"],"segments":["s"],"costs":[1],"revenues":[2]},365:{"assumptions":[{"id":"a","risk":"high"}],"tests":[{"assumption_id":"a","method":"interview"}]},366:{"segments":[{"id":"s","scores":{"c":3}}],"criteria":[{"id":"c","weight":1}]},367:{"observations":["o"],"behaviors":["b"],"goals":["g"],"pain_points":["p"]},368:{"stages":["s"],"touchpoints":["t"],"customer_actions":["a"],"pain_points":["p"]},369:{"observations":["o"],"needs":["n"]},370:{"situations":["s"],"outcomes":["o"],"importance":[5],"satisfaction":[2]},371:{"push":["p"],"pull":["p"],"anxiety":["a"],"habit":["h"]},372:{"hypothesis":"h","metric":"m","threshold":1,"method":"test"},373:{"core_hypothesis":"h","minimum_capabilities":["m"],"excluded_scope":["e"],"success_metric":"s"},374:{"channels":["c"],"questions":["q"],"sampling":"s","coding_scheme":"c"},375:{"signals":["s"],"thresholds":[1],"observations":[1]},376:{"original_hypothesis":"h","evidence":["e"],"pivot_options":["p"],"decision_rule":"r"},377:{"tactics":["t"],"constraints":["c"],"expected_mechanisms":["m"]},384:{"customers":[{"id":"c","signals":{"r":1}}],"risk_signals":["r"],"weights":[1]},386:{"responses":[5],"scale":"1-5"},387:{"feedback":["fast and clear"],"coding_scheme":{"speed":["fast"]}},389:{"outcomes":["o"],"initiatives":["i"],"dependencies":["d"],"time_horizons":["now"]},390:{"roles":["r"],"cadence":"weekly","definition_of_done":"done","work_item_types":["story"]},391:{"items":[{"id":"1"}]},393:{"planned":[1],"completed":[1],"dates":["2026-01-01"]},394:{"states":["todo"],"wip_limits":{"todo":2},"policies":["p"]},395:{"meetings":["standup"],"participants":["team"],"cadence":"daily","outcomes":["blockers"]},396:{"went_well":["x"],"did_not":["y"],"actions":["z"],"owners":["u"]},397:{"hypothesis":"h","primary_metric":"m","randomization_unit":"user","control":"a","treatment":"b","stopping_rule":"n=100"},398:{"factors":["color"],"levels":[["red","blue"]],"primary_metric":"m","allocation":"equal","multiple_testing_method":"bonferroni"}}
@pytest.mark.parametrize("row,inputs",sorted(QUAL.items()))
def test_qualitative_rows_are_typed_source_bound_artifacts(row,inputs):
 a=service().analyze("i",req(row,inputs));assert a.result["source_bound"] is True and a.result["fabricated_claims"] is False and a.inputs==inputs

def test_qualitative_missing_fields_fail_instead_of_fabricating():
 with pytest.raises(ValueError,match="missing required inputs"):service().analyze("i",req(361,{"competitors":["A"]}))

def test_mounted_business_api():
 app=FastAPI();app.include_router(router);c=TestClient(app);payload=req(379,{"acquisition_spend":100,"new_customers":5}).model_dump(mode="json");r=c.post("/portfolio/ideas/x/business-analyses",json=payload);assert r.status_code==201 and r.json()["result"]["cac"]==20

def test_row_361_competitor_matrix_calculates_weighted_scores():
 a=service().analyze("i",req(361,{"competitors":[{"id":"A","scores":{"price":4}}],"criteria":[{"id":"price","weight":2}]}));assert a.result["competitor_matrix"][0]["score"]==8

def test_row_370_outcome_opportunity_uses_importance_and_satisfaction():
 a=service().analyze("i",req(370,{"situations":["s"],"outcomes":["o"],"importance":[9],"satisfaction":[3]}));assert a.result["opportunity_scores"][0]["score"]==15

def test_row_375_product_market_fit_does_not_claim_passing_thresholds():
 a=service().analyze("i",req(375,{"signals":["retention"],"thresholds":[.5],"observations":[.4]}));assert a.result["validated"] is False

def test_row_384_churn_prediction_is_explicitly_prediction_only():
 a=service().analyze("i",req(384,{"customers":[{"id":"c","signals":{"late":1}}],"risk_signals":["late"],"weights":[2]}));assert a.result["churn_risk"]==[{"customer":"c","score":2.0,"prediction_only":True}]

def test_row_398_multivariate_cell_count_is_factorial_not_a_shared_envelope():
 a=service().analyze("i",req(398,{"factors":["color","copy"],"levels":[["r","b"],["a","z"]],"primary_metric":"ctr","allocation":"equal","multiple_testing_method":"holm"}));assert a.result["multivariate_design"]["cell_count"]==4

def test_business_qualitative_rows_have_distinct_result_keys_and_methods():
 artifacts=[service().analyze("i",req(row,inputs)) for row,inputs in sorted(QUAL.items())]
 assert len({next(iter(a.result)) for a in artifacts})==len(artifacts)
 assert len({a.method for a in artifacts})==len(artifacts)
