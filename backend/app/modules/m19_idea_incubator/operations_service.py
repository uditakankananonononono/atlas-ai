"""Operations analyses and plans. No method performs operational execution."""
from __future__ import annotations
from math import sqrt
from statistics import fmean,pstdev
from .operations_models import *
METHODS={452:"supply-chain network plan",456:"finite-capacity scheduling plan",457:"quality control plan",458:"Six Sigma defect analysis",459:"lean waste audit",460:"just-in-time readiness assessment",461:"total quality management plan",462:"Kaizen improvement backlog",463:"root-cause evidence matrix",464:"Ishikawa fishbone",465:"5 Whys chain",466:"PDCA cycle",467:"DMAIC charter",468:"value-stream map",469:"process-mining discovery specification",470:"workflow simplification plan",471:"RPA suitability assessment",472:"business process reengineering charter",473:"change-management plan",474:"Kotter eight-step plan",475:"ADKAR assessment"}
REQUIRED={452:("nodes","lanes","capacities","service_targets"),456:("orders","resources","capacities","durations","due_dates"),457:("standards","characteristics","sampling_plan","acceptance_criteria"),458:("opportunities","defects","units","target_sigma"),459:("process_steps","observed_waste","customer_value_definition"),460:("demand_signal","lead_times","lot_sizes","supplier_reliability","buffers"),461:("quality_policy","customer_requirements","process_owners","measures"),462:("observations","improvement_ideas","owners","review_cadence"),463:("problem_statement","evidence","candidate_causes","disconfirming_evidence"),464:("problem","people","process","equipment","materials","environment","measurement"),465:("problem","why_chain","evidence_by_step"),466:("plan","baseline","intervention","check_metrics","act_rule"),467:("define","measure","analyze","improve","control"),468:("steps","cycle_times","wait_times","inventory","value_added"),469:("event_log_fields","case_id","activity","timestamp","data_quality"),470:("steps","handoffs","approvals","manual_effort"),471:("tasks","rule_stability","volumes","exceptions","systems","security_constraints"),472:("current_outcomes","target_outcomes","constraints","redesign_principles"),473:("stakeholders","impacts","readiness","communications","training","resistance_risks"),474:("urgency","coalition","vision","communications","barriers","short_term_wins","acceleration","anchoring"),475:("awareness","desire","knowledge","ability","reinforcement")}
class OperationsAnalysisService:
 def analyze(self,idea_id:str,r:OperationsAnalysisRequest)->OperationsArtifact:
  f=int(r.feature);analysis,method=self._compute(f,r.inputs);limits=[]
  if r.confidence<.5:limits.append("Input confidence is low; validate before using this plan.")
  if any(p.source_type=="public_source" and not p.uri for p in r.provenance):limits.append("A public source lacks a URI.")
  limits.append("This artifact is a plan or analysis only; no supplier, inventory, production, workflow, automation, or organizational change was executed.")
  plan={"status":"proposed","requires_human_review":True,"next_steps":self._next(f,analysis),"operational_changes_applied":False}
  return OperationsArtifact(idea_id=idea_id,feature=r.feature,method=method,inputs=r.inputs,provenance=r.provenance,assumptions=r.assumptions,analysis=analysis,uncertainty=Uncertainty(confidence=r.confidence,limitations=limits,sample_size=analysis.get("sample_size")),plan=plan)
 def _compute(self,f,x):
  if f==451:
   vendors=[Vendor.model_validate(v) for v in x.get("vendors",[])];weights=x.get("weights",{"cost":.3,"quality":.3,"delivery":.2,"risk":.2})
   if not vendors:raise ValueError("vendors are required")
   if set(weights)!={"cost","quality","delivery","risk"} or abs(sum(weights.values())-1)>1e-6:raise ValueError("vendor weights must cover four criteria and sum to 1")
   max_cost=max(v.cost for v in vendors) or 1;ranked=sorted(({"id":v.id,"score":weights["cost"]*(100*(1-v.cost/max_cost))+weights["quality"]*v.quality+weights["delivery"]*v.delivery+weights["risk"]*(100-v.risk)} for v in vendors),key=lambda q:q["score"],reverse=True)
   return {"ranked_vendors":ranked,"recommendation":"review highest score with due diligence; no vendor selected"},"weighted vendor scorecard"
  if f==453:
   d=InventoryInput.model_validate(x);eoq=sqrt(2*d.annual_demand*d.order_cost/d.annual_holding_cost_per_unit);return {"economic_order_quantity":eoq,"reorder_point":d.daily_demand*d.lead_time_days+d.safety_stock,"annual_cycle_inventory":eoq/2,"formula_scope":"deterministic EOQ; excludes quantity discounts and variable demand"},"EOQ and reorder-point analysis"
  if f==454:
   d=DemandInput.model_validate(x);w=min(d.window,len(d.history));forecast=fmean(d.history[-w:]);sd=pstdev(d.history[-w:]) if w>1 else 0;return {"forecast":[forecast]*d.horizon,"window":w,"history_points":len(d.history),"interval_low":max(0,forecast-1.96*sd),"interval_high":forecast+1.96*sd,"warning":"naive moving average; no seasonality or causal variables"},"moving-average demand forecast"
  if f==455:
   legs=x.get("legs",[])
   if not legs:raise ValueError("legs are required")
   rows=[];total=0
   for leg in legs:
    missing={"id","distance","rate_per_distance","fixed_cost","units"}-set(leg)
    if missing:raise ValueError("logistics leg missing: "+", ".join(sorted(missing)))
    cost=leg["distance"]*leg["rate_per_distance"]+leg["fixed_cost"];total+=cost;rows.append({"id":leg["id"],"cost":cost,"cost_per_unit":cost/leg["units"] if leg["units"] else None})
   return {"legs":rows,"total_cost":total},"lane-cost model"
  req=REQUIRED.get(f)
  if req:
   missing=[k for k in req if k not in x or x[k] in (None,[],{})]
   if missing:raise ValueError("missing required inputs: "+", ".join(missing))
   result={"sections":{k:x[k] for k in req},"evidence_bound":True,"execution_claim":False}
   if f==458:
    opportunities=x["opportunities"]*x["units"];result["dpmo"]=x["defects"]/opportunities*1_000_000 if opportunities else None
   if f==468:result["total_cycle_time"]=sum(x["cycle_times"]);result["total_wait_time"]=sum(x["wait_times"]);result["process_cycle_efficiency"]=sum(x["value_added"])/(sum(x["cycle_times"])+sum(x["wait_times"])) if sum(x["cycle_times"])+sum(x["wait_times"]) else None
   return result,METHODS[f]
  raise ValueError(f"unsupported operations feature row {f}")
 @staticmethod
 def _next(f,a):return ["validate source data","review constraints and risks","approve a bounded pilot","measure actual outcomes"]
