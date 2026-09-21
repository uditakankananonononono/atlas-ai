"""Operations analyses and plans. No method performs operational execution."""
from __future__ import annotations
from math import sqrt
from statistics import fmean,pstdev
from .operations_models import *
METHODS={452:"supply-chain network plan",456:"finite-capacity scheduling plan",457:"quality control plan",458:"Six Sigma defect analysis",459:"lean waste audit",460:"just-in-time readiness assessment",461:"total quality management plan",462:"Kaizen improvement backlog",463:"root-cause evidence matrix",464:"Ishikawa fishbone",465:"5 Whys chain",466:"PDCA cycle",467:"DMAIC charter",468:"value-stream map",469:"process-mining discovery specification",470:"workflow simplification plan",471:"RPA suitability assessment",472:"business process reengineering charter",473:"change-management plan",474:"Kotter eight-step plan",475:"ADKAR assessment"}
REQUIRED={452:("nodes","lanes","capacities","service_targets"),456:("orders","resources","capacities","durations","due_dates"),457:("standards","characteristics","sampling_plan","acceptance_criteria"),458:("opportunities","defects","units","target_sigma"),459:("process_steps","observed_waste","customer_value_definition"),460:("demand_signal","lead_times","lot_sizes","supplier_reliability","buffers"),461:("quality_policy","customer_requirements","process_owners","measures"),462:("observations","improvement_ideas","owners","review_cadence"),463:("problem_statement","evidence","candidate_causes","disconfirming_evidence"),464:("problem","people","process","equipment","materials","environment","measurement"),465:("problem","why_chain","evidence_by_step"),466:("plan","baseline","intervention","check_metrics","act_rule"),467:("define","measure","analyze","improve","control"),468:("steps","cycle_times","wait_times","inventory","value_added"),469:("event_log_fields","case_id","activity","timestamp","data_quality"),470:("steps","handoffs","approvals","manual_effort"),471:("tasks","rule_stability","volumes","exceptions","systems","security_constraints"),472:("current_outcomes","target_outcomes","constraints","redesign_principles"),473:("stakeholders","impacts","readiness","communications","training","resistance_risks"),474:("urgency","coalition","vision","communications","barriers","short_term_wins","acceleration","anchoring"),475:("awareness","desire","knowledge","ability","reinforcement")}
class OperationsAnalysisService:
 def analyze(self,idea_id:str,r:OperationsAnalysisRequest)->OperationsArtifact:
  f=int(r.feature);analysis,method=self._compute(f,r.inputs)
  if 452 <= f <= 475:
   analysis={"evidence_bound":True,"execution_claim":False,**analysis}
  limits=[]
  if r.confidence<.5:limits.append("Input confidence is low; validate before using this plan.")
  if any(p.source_type=="public_source" and not p.uri for p in r.provenance):limits.append("A public source lacks a URI.")
  limits.append("This artifact is a plan or analysis only; no supplier, inventory, production, workflow, automation, or organizational change was executed.")
  plan={"status":"proposed","requires_human_review":True,"next_steps":self._next(f,analysis),"operational_changes_applied":False}
  return OperationsArtifact(idea_id=idea_id,feature=r.feature,method=method,inputs=r.inputs,provenance=r.provenance,assumptions=r.assumptions,analysis=analysis,uncertainty=Uncertainty(confidence=r.confidence,limitations=limits,sample_size=analysis.get("sample_size")),evaluation={"method":method,"computed_outputs":sorted(analysis),"evidence_sources":len(r.provenance),"acceptance_or_control_review_required":True,"pilot_measurement_required":True},plan=plan)
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
  if f==452:
   required=("nodes","lanes","capacities","service_targets");missing=[k for k in required if not x.get(k)]
   if missing:raise ValueError("missing required inputs: "+", ".join(missing))
   return {"network":{"nodes":x["nodes"],"lanes":x["lanes"]},"capacity_total":sum(x["capacities"]),"service_targets":x["service_targets"],"network_changed":False},METHODS[f]
  if f in REQUIRED:
   missing=[k for k in REQUIRED[f] if k not in x or x[k] in (None,[],{})]
   if missing:raise ValueError("missing required inputs: "+", ".join(missing))
  if f==456:
   d=ProductionSchedulingInput.model_validate(x)
   if not (len(d.orders)==len(d.durations)==len(d.due_dates)):raise ValueError("orders, durations, and due_dates must align")
   if len(d.resources)!=len(d.capacities):raise ValueError("resources and capacities must align")
   return {"order_load":dict(zip(d.orders,d.durations)),"resource_capacity":dict(zip(d.resources,d.capacities)),"total_required_hours":sum(d.durations),"total_available_capacity":sum(d.capacities),"capacity_gap":sum(d.capacities)-sum(d.durations)},METHODS[f]
  if f==457:
   d=QualityControlInput.model_validate(x);return {"control_characteristics":d.characteristics,"standards_trace":{c:d.standards for c in d.characteristics},"sampling_plan":d.sampling_plan,"acceptance_gate":d.acceptance_criteria},METHODS[f]
  if f==458:
   d=SixSigmaInput.model_validate(x);op=d.opportunities*d.units;dpmo=d.defects/op*1_000_000
   return {"total_opportunities":op,"dpmo":dpmo,"yield_rate":1-d.defects/op,"target_sigma":d.target_sigma,"control_required":dpmo>0},METHODS[f]
  if f==459:
   d=LeanInput.model_validate(x);return {"value_definition":d.customer_value_definition,"waste_register":[{"waste":w,"disposition":"review for remove/reduce"} for w in d.observed_waste],"flow_steps":d.process_steps,"waste_per_step":len(d.observed_waste)/len(d.process_steps)},METHODS[f]
  if f==460:
   d=JITInput.model_validate(x);reliability=min(d.supplier_reliability)
   return {"demand_mean":fmean(d.demand_signal),"lead_time_max":max(d.lead_times),"lot_size_total":sum(d.lot_sizes),"buffer_total":sum(d.buffers),"supplier_reliability_floor":reliability,"jit_ready":reliability>=.95 and sum(d.buffers)>0},METHODS[f]
  if f==461:
   d=TQMInput.model_validate(x);return {"policy":d.quality_policy,"customer_to_measure":dict(zip(d.customer_requirements,d.measures,strict=False)),"accountable_owners":d.process_owners,"unowned_measure_count":max(0,len(d.measures)-len(d.process_owners))},METHODS[f]
  if f==462:
   d=KaizenInput.model_validate(x);return {"backlog":[{"observation":o,"idea":d.improvement_ideas[i%len(d.improvement_ideas)],"owner":d.owners[i%len(d.owners)]} for i,o in enumerate(d.observations)],"review_cadence":d.review_cadence,"batch_size":len(d.observations)},METHODS[f]
  if f==463:
   d=RootCauseInput.model_validate(x);return {"problem":d.problem_statement,"cause_matrix":[{"cause":c,"support":d.evidence,"challenges":d.disconfirming_evidence,"status":"hypothesis"} for c in d.candidate_causes],"confirmed_root_cause":None},METHODS[f]
  if f==464:
   d=FishboneInput.model_validate(x);return {"effect":d.problem,"bones":{"people":d.people,"process":d.process,"equipment":d.equipment,"materials":d.materials,"environment":d.environment,"measurement":d.measurement},"cause_count":sum(len(v) for v in (d.people,d.process,d.equipment,d.materials,d.environment,d.measurement))},METHODS[f]
  if f==465:
   d=FiveWhysInput.model_validate(x)
   if len(d.why_chain)!=len(d.evidence_by_step):raise ValueError("why_chain and evidence_by_step must align")
   return {"problem":d.problem,"chain":[{"depth":i+1,"why":w,"evidence":d.evidence_by_step[i]} for i,w in enumerate(d.why_chain)],"candidate_root_cause":d.why_chain[-1],"verified":False},METHODS[f]
  if f==466:
   d=PDCAInput.model_validate(x);return {"plan":d.plan,"do":{"intervention":d.intervention,"status":"not_started"},"check":{"baseline":d.baseline,"metrics":d.check_metrics},"act":{"decision_rule":d.act_rule,"status":"pending_measurement"}},METHODS[f]
  if f==467:
   d=DMAICInput.model_validate(x);return {"charter":{"define":d.define},"measurement_plan":d.measure,"analysis_hypothesis":d.analyze,"improvement_proposal":d.improve,"control_plan":d.control,"phase_gate":"define_review"},METHODS[f]
  if f==468:
   d=ValueStreamInput.model_validate(x);n=len(d.steps)
   if any(len(v)!=n for v in (d.cycle_times,d.wait_times,d.inventory,d.value_added)):raise ValueError("value-stream vectors must align with steps")
   elapsed=sum(d.cycle_times)+sum(d.wait_times)
   return {"map":[{"step":d.steps[i],"cycle":d.cycle_times[i],"wait":d.wait_times[i],"inventory":d.inventory[i],"value_added":d.value_added[i]} for i in range(n)],"total_cycle_time":sum(d.cycle_times),"total_wait_time":sum(d.wait_times),"process_cycle_efficiency":sum(d.value_added)/elapsed if elapsed else None},METHODS[f]
  if f==469:
   d=ProcessMiningInput.model_validate(x);required={d.case_id,d.activity,d.timestamp};missing=required-set(d.event_log_fields)
   if missing:raise ValueError("event log lacks mapped fields: "+", ".join(sorted(missing)))
   return {"schema_mapping":{"case":d.case_id,"activity":d.activity,"timestamp":d.timestamp},"data_quality":d.data_quality,"discovery_status":"specified_not_run","event_count":None,"process_model":None},METHODS[f]
  if f==470:
   d=WorkflowInput.model_validate(x);return {"step_count":len(d.steps),"handoff_count":len(d.handoffs),"approval_count":len(d.approvals),"manual_effort_total":sum(d.manual_effort),"simplification_candidates":d.handoffs,"workflow_changed":False},METHODS[f]
  if f==471:
   d=RPAInput.model_validate(x);return {"task_assessments":[{"task":t,"volume":d.volumes[i%len(d.volumes)],"suitable":d.rule_stability.lower()=="high" and not d.exceptions} for i,t in enumerate(d.tasks)],"systems":d.systems,"security_constraints":d.security_constraints,"bot_deployed":False},METHODS[f]
  if f==472:
   d=ReengineeringInput.model_validate(x);return {"from":d.current_outcomes,"to":d.target_outcomes,"design_constraints":d.constraints,"principles":d.redesign_principles,"redesign_status":"charter_only","cutover_authorized":False},METHODS[f]
  if f==473:
   d=ChangeManagementInput.model_validate(x);return {"impact_map":dict(zip(d.stakeholders,d.impacts,strict=False)),"readiness_evidence":d.readiness,"communication_drafts":d.communications,"training_plan":d.training,"resistance_register":d.resistance_risks,"messages_sent":0},METHODS[f]
  if f==474:
   d=KotterInput.model_validate(x);return {"steps":[{"step":1,"input":d.urgency},{"step":2,"input":d.coalition},{"step":3,"input":d.vision},{"step":4,"input":d.communications},{"step":5,"input":d.barriers},{"step":6,"input":d.short_term_wins},{"step":7,"input":d.acceleration},{"step":8,"input":d.anchoring}],"current_gate":1,"change_executed":False},METHODS[f]
  if f==475:
   d=ADKARInput.model_validate(x);scores=d.model_dump();bottleneck=min(scores,key=scores.get)
   return {"scores":scores,"average":fmean(scores.values()),"bottleneck":bottleneck,"bottleneck_score":scores[bottleneck],"intervention_priority":bottleneck},METHODS[f]
  raise ValueError(f"unsupported operations feature row {f}")
 @staticmethod
 def _next(f,a):return ["validate source data","review constraints and risks","approve a bounded pilot","measure actual outcomes"]
