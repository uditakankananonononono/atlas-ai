from datetime import datetime,timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m19_idea_incubator.operations_models import *
from app.modules.m19_idea_incubator.operations_service import OperationsAnalysisService
from app.modules.m19_idea_incubator.operations_router import router
P=Provenance(source_id="ops-1",source_type="analytics",observed_at=datetime.now(timezone.utc))
def req(row,inputs,confidence=.8):return OperationsAnalysisRequest(feature=row,inputs=inputs,provenance=[P],confidence=confidence)
def svc():return OperationsAnalysisService()

def assert_plan(a):
 assert a.execution_status=="not_executed";assert a.plan["operational_changes_applied"] is False;assert a.plan["requires_human_review"] is True;assert "no supplier" in a.uncertainty.limitations[-1]

def test_row_451_vendor_selection_is_ranked_not_executed():
 a=svc().analyze("i",req(451,{"vendors":[{"id":"a","cost":10,"quality":90,"delivery":80,"risk":10},{"id":"b","cost":8,"quality":70,"delivery":90,"risk":20}],"weights":{"cost":.25,"quality":.25,"delivery":.25,"risk":.25}}));assert len(a.analysis["ranked_vendors"])==2;assert "no vendor selected" in a.analysis["recommendation"];assert_plan(a)
def test_row_453_inventory_eoq_and_reorder_point():
 a=svc().analyze("i",req(453,{"annual_demand":10000,"order_cost":50,"annual_holding_cost_per_unit":2,"lead_time_days":5,"daily_demand":30,"safety_stock":20}));assert round(a.analysis["economic_order_quantity"],2)==707.11;assert a.analysis["reorder_point"]==170;assert_plan(a)
def test_row_454_forecast_declares_naive_scope_and_uncertainty():
 a=svc().analyze("i",req(454,{"history":[10,20,30,40],"horizon":2,"window":3}));assert a.analysis["forecast"]==[30,30];assert "naive" in a.analysis["warning"];assert_plan(a)
def test_row_455_logistics_cost_model():
 a=svc().analyze("i",req(455,{"legs":[{"id":"L1","distance":100,"rate_per_distance":2,"fixed_cost":50,"units":10}]}));assert a.analysis["total_cost"]==250;assert a.analysis["legs"][0]["cost_per_unit"]==25;assert_plan(a)

ROWS={452:{"nodes":["a"],"lanes":["l"],"capacities":[1],"service_targets":[1]},456:{"orders":["o"],"resources":["r"],"capacities":[1],"durations":[1],"due_dates":["d"]},457:{"standards":["s"],"characteristics":["c"],"sampling_plan":"p","acceptance_criteria":"a"},458:{"opportunities":10,"defects":2,"units":100,"target_sigma":4},459:{"process_steps":["p"],"observed_waste":["w"],"customer_value_definition":"v"},460:{"demand_signal":[1],"lead_times":[1],"lot_sizes":[1],"supplier_reliability":[.9],"buffers":[1]},461:{"quality_policy":"p","customer_requirements":["r"],"process_owners":["o"],"measures":["m"]},462:{"observations":["o"],"improvement_ideas":["i"],"owners":["u"],"review_cadence":"weekly"},463:{"problem_statement":"p","evidence":["e"],"candidate_causes":["c"],"disconfirming_evidence":["d"]},464:{"problem":"p","people":["x"],"process":["x"],"equipment":["x"],"materials":["x"],"environment":["x"],"measurement":["x"]},465:{"problem":"p","why_chain":["w1","w2"],"evidence_by_step":["e1","e2"]},466:{"plan":"p","baseline":1,"intervention":"i","check_metrics":["m"],"act_rule":"a"},467:{"define":"d","measure":"m","analyze":"a","improve":"i","control":"c"},468:{"steps":["a","b"],"cycle_times":[2,3],"wait_times":[5,0],"inventory":[1,2],"value_added":[1,2]},469:{"event_log_fields":["case","activity","time"],"case_id":"case","activity":"activity","timestamp":"time","data_quality":"checked"},470:{"steps":["s"],"handoffs":["h"],"approvals":["a"],"manual_effort":[1]},471:{"tasks":["t"],"rule_stability":"high","volumes":[100],"exceptions":["x"],"systems":["s"],"security_constraints":["c"]},472:{"current_outcomes":["c"],"target_outcomes":["t"],"constraints":["x"],"redesign_principles":["p"]},473:{"stakeholders":["s"],"impacts":["i"],"readiness":["r"],"communications":["c"],"training":["t"],"resistance_risks":["x"]},474:{"urgency":"u","coalition":["c"],"vision":"v","communications":["c"],"barriers":["b"],"short_term_wins":["w"],"acceleration":["a"],"anchoring":["a"]},475:{"awareness":1,"desire":2,"knowledge":3,"ability":4,"reinforcement":5}}
@pytest.mark.parametrize("row,inputs",sorted(ROWS.items()))
def test_row_named_evidence_bound_plans(row,inputs):
 a=svc().analyze("i",req(row,inputs));assert a.analysis["evidence_bound"] is True;assert a.analysis["execution_claim"] is False;assert a.inputs==inputs;assert_plan(a)

def test_row_458_dpmo_calculation():assert svc().analyze("i",req(458,ROWS[458])).analysis["dpmo"]==2000
def test_row_468_value_stream_metrics():
 a=svc().analyze("i",req(468,ROWS[468]));assert a.analysis["total_cycle_time"]==5 and a.analysis["total_wait_time"]==5 and a.analysis["process_cycle_efficiency"]==.3
def test_missing_inputs_fail_instead_of_inventing():
 with pytest.raises(ValueError,match="missing required inputs"):svc().analyze("i",req(475,{"awareness":1}))
def test_no_provenance_rejected():
 with pytest.raises(Exception):OperationsAnalysisRequest(feature=451,inputs={"vendors":[1]},provenance=[],confidence=.5)
def test_low_confidence_is_flagged():assert "low" in svc().analyze("i",req(453,{"annual_demand":1,"order_cost":1,"annual_holding_cost_per_unit":1,"lead_time_days":1,"daily_demand":1},.2)).uncertainty.limitations[0]
def test_mounted_operations_api():
 app=FastAPI();app.include_router(router);c=TestClient(app);payload=req(454,{"history":[1,2,3]}).model_dump(mode="json");r=c.post("/portfolio/ideas/x/operations-analyses",json=payload);assert r.status_code==201 and r.json()["execution_status"]=="not_executed"
