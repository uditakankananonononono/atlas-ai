"""Deterministic business analysis without fabricated evidence."""
from __future__ import annotations
from math import erf,sqrt
from statistics import fmean,pstdev
from .business_models import *

QUALITATIVE_METHODS={361:"SWOT competitor matrix",362:"Five Forces",363:"value proposition canvas",364:"business model canvas",365:"assumption validation board",366:"segment attractiveness matrix",367:"evidence-backed persona",368:"customer journey map",369:"jobs-and-pains synthesis",370:"outcome statement mapping",371:"jobs-to-be-done forces",372:"hypothesis test card",373:"MVP scope card",374:"feedback collection plan",375:"market validation scorecard",376:"pivot/persevere review",377:"growth tactic backlog",384:"churn-risk rubric",386:"satisfaction scorecard",387:"voice-of-customer theme analysis",389:"outcome roadmap",390:"agile operating model",391:"ordered backlog",393:"progress/burndown view",394:"workflow policy",395:"agile meeting plan",396:"sprint retrospective",397:"controlled experiment protocol",398:"multivariate experiment protocol"}
REQUIRED={361:("competitors","criteria"),362:("supplier_power","buyer_power","new_entrants","substitutes","rivalry"),363:("customer_jobs","pains","gains","products_services","pain_relievers","gain_creators"),364:("partners","activities","resources","value_propositions","relationships","channels","segments","costs","revenues"),365:("assumptions","tests"),366:("segments","criteria"),367:("observations","behaviors","goals","pain_points"),368:("stages","touchpoints","customer_actions","pain_points"),369:("observations","needs"),370:("situations","outcomes","importance","satisfaction"),371:("push","pull","anxiety","habit"),372:("hypothesis","metric","threshold","method"),373:("core_hypothesis","minimum_capabilities","excluded_scope","success_metric"),374:("channels","questions","sampling","coding_scheme"),375:("signals","thresholds","observations"),376:("original_hypothesis","evidence","pivot_options","decision_rule"),377:("tactics","constraints","expected_mechanisms"),384:("customers","risk_signals","weights"),386:("responses","scale"),387:("feedback","coding_scheme"),389:("outcomes","initiatives","dependencies","time_horizons"),390:("roles","cadence","definition_of_done","work_item_types"),391:("items",),393:("planned","completed","dates"),394:("states","wip_limits","policies"),395:("meetings","participants","cadence","outcomes"),396:("went_well","did_not","actions","owners"),397:("hypothesis","primary_metric","randomization_unit","control","treatment","stopping_rule"),398:("factors","levels","primary_metric","allocation","multiple_testing_method")}
class BusinessAnalysisService:
 def analyze(self,idea_id:str,request:BusinessAnalysisRequest)->BusinessArtifact:
  f=int(request.feature);result,method=self._compute(f,request.inputs);limitations=[]
  if request.confidence<.5:limitations.append("Input confidence is below 0.5; treat the output as directional.")
  if any(p.source_type=="public_source" and not p.uri for p in request.provenance):limitations.append("A public source lacks a URI and cannot be independently checked.")
  decision={"status":"ready_for_review","recommended_action":self._recommend(f,result),"machine_decision":False}
  return BusinessArtifact(idea_id=idea_id,feature=request.feature,method=method,inputs=request.inputs,assumptions=request.assumptions,provenance=request.provenance,result=result,uncertainty=Uncertainty(confidence=request.confidence,limitations=limitations,sample_size=result.get("sample_size"),interval_low=result.get("interval_low"),interval_high=result.get("interval_high")),evaluation={"method":method,"computed_outputs":sorted(result),"evidence_sources":len(request.provenance),"assumptions_tested":[a.name for a in request.assumptions],"human_review_required":True},decision=decision)
 def _compute(self,f:int,x:dict):
  if f==360:
   d=MarketSizingInput.model_validate(x);tam=d.total_entities*d.annual_revenue_per_entity;sam=tam*d.serviceable_fraction;return {"tam":tam,"sam":sam,"som":sam*d.obtainable_fraction,"currency":x.get("currency"),"formula":"entities × annual revenue; then serviceable and obtainable fractions"},"bottom-up TAM/SAM/SOM"
  if f==378:
   d=ViralInput.model_validate(x);k=d.invitations_per_user*d.invite_conversion_rate;return {"viral_coefficient":k,"viral":k>1,"cycle_days":d.cycle_days,"daily_compounding_factor":k**(1/d.cycle_days) if k else 0},"viral coefficient"
  if f==379:
   d=CACInput.model_validate(x);return {"cac":d.acquisition_spend/d.new_customers,"spend":d.acquisition_spend,"new_customers":d.new_customers},"blended CAC"
  if f==380:
   d=LTVInput.model_validate(x);return {"ltv":d.average_revenue_per_period*d.gross_margin_rate/d.periodic_churn_rate,"expected_periods":1/d.periodic_churn_rate},"simple churn-based LTV"
  if f==381:
   d=UnitEconomicsInput.model_validate(x);contribution=d.revenue_per_unit-d.variable_cost_per_unit-d.cac;return {"contribution_margin_per_unit":contribution,"contribution_margin_rate":contribution/d.revenue_per_unit if d.revenue_per_unit else None,"profit_at_volume":contribution*d.units-d.fixed_costs,"break_even_units":d.fixed_costs/contribution if contribution>0 else None},"unit contribution economics"
  if f==382:
   d=CohortInput.model_validate(x);curves={k:[round(n/v[0],4) if v and v[0] else None for n in v] for k,v in d.cohorts.items()};return {"retention_curves":curves,"cohort_count":len(curves)},"cohort retention table"
  if f==383:
   d=RateInput.model_validate(x);return {"retention_rate":d.remaining/d.starting,"churn_rate":1-d.remaining/d.starting,"sample_size":d.starting},"period retention"
  if f==385:
   d=NPSInput.model_validate(x);pro=sum(n>=9 for n in d.scores);det=sum(n<=6 for n in d.scores);n=len(d.scores);return {"nps":round(100*(pro-det)/n,2),"promoters":pro,"passives":n-pro-det,"detractors":det,"sample_size":n},"Net Promoter Score"
  if f==388:
   items=[PriorityItem.model_validate(v) for v in x.get("items",[])];
   if not items:raise ValueError("items are required")
   return {"ranked_items":sorted(({"id":i.id,"rice_score":i.reach*i.impact*i.confidence/i.effort} for i in items),key=lambda z:z["rice_score"],reverse=True)},"RICE prioritization"
  if f==392:
   d=VelocityInput.model_validate(x);return {"average_velocity":fmean(d.completed_points),"velocity_stddev":pstdev(d.completed_points),"sprints":len(d.completed_points),"commitment_reliability":[c/p if p else None for c,p in zip(d.completed_points,d.planned_points)] if d.planned_points else None},"sprint velocity"
  if f==399:return self._significance(SignificanceInput.model_validate(x)),"two-proportion z-test"
  required=REQUIRED.get(f)
  if required:
   missing=[k for k in required if k not in x or x[k] in (None,[],{})]
   if missing:raise ValueError("missing required inputs: "+", ".join(missing))
   return {"sections":{k:x[k] for k in required},"source_bound":True,"fabricated_claims":False},QUALITATIVE_METHODS[f]
  raise ValueError(f"unsupported business feature row {f}")
 def _significance(self,d):
  p1=d.control_conversions/d.control_total;p2=d.variant_conversions/d.variant_total;pooled=(d.control_conversions+d.variant_conversions)/(d.control_total+d.variant_total);se=sqrt(pooled*(1-pooled)*(1/d.control_total+1/d.variant_total));z=(p2-p1)/se if se else 0;pvalue=2*(1-(1+erf(abs(z)/sqrt(2)))/2);diff=p2-p1;se_diff=sqrt(p1*(1-p1)/d.control_total+p2*(1-p2)/d.variant_total);low=diff-1.96*se_diff;high=diff+1.96*se_diff
  return {"control_rate":p1,"variant_rate":p2,"absolute_lift":diff,"relative_lift":diff/p1 if p1 else None,"z_score":z,"p_value":pvalue,"statistically_significant":pvalue<d.alpha,"practically_significant":abs(diff)>=d.minimum_effect,"interval_low":low,"interval_high":high,"sample_size":d.control_total+d.variant_total,"warning":"Fixed-horizon approximation; invalid after unplanned repeated peeking."}
 @staticmethod
 def _recommend(f,r):
  if f==399:return "review effect size and validity before rollout" if r["statistically_significant"] else "collect more data or retain control"
  if f==381 and r["contribution_margin_per_unit"]<=0:return "fix unit economics before scaling"
  if f==378 and not r["viral"]:return "do not assume self-sustaining virality"
  return "review artifact against decision threshold"

# Row-specific business instruments. These deliberately return different schemas so a
# caller cannot mistake a generic section echo for implemented analysis.
def _row_specific_business(f:int,x:dict):
 def need(*ks):
  missing=[k for k in ks if x.get(k) in (None,"",[],{})]
  if missing: raise ValueError("missing required inputs: "+", ".join(missing))
 if f==361:
  need("competitors","criteria"); rows=[]
  for c in x["competitors"]:
   scores=c.get("scores",{}) if isinstance(c,dict) else {};rows.append({"competitor":c.get("id") if isinstance(c,dict) else c,"criterion_scores":scores,"score":sum(float(scores.get(k.get("id",k),0))*float(k.get("weight",1) if isinstance(k,dict) else 1) for k in x["criteria"])})
  return {"competitor_matrix":sorted(rows,key=lambda z:z["score"],reverse=True),"evidence_only":True},"weighted competitor matrix"
 if f==362:
  need("supplier_power","buyer_power","new_entrants","substitutes","rivalry");scale={"low":1,"medium":2,"high":3};vals={k:scale.get(str(x[k]).lower(),float(x[k]) if isinstance(x[k],(int,float)) else 0) for k in ("supplier_power","buyer_power","new_entrants","substitutes","rivalry")};return {"force_scores":vals,"industry_pressure_index":sum(vals.values())/5},"Five Forces pressure index"
 if f==363:
  need("customer_jobs","pains","gains","products_services","pain_relievers","gain_creators");return {"fit_map":{"job_coverage":min(len(x["products_services"])/len(x["customer_jobs"]),1),"pain_coverage":min(len(x["pain_relievers"])/len(x["pains"]),1),"gain_coverage":min(len(x["gain_creators"])/len(x["gains"]),1)},"unverified_offer":True},"value proposition fit map"
 if f==364:
  need("partners","activities","resources","value_propositions","relationships","channels","segments","costs","revenues");return {"canvas":{"infrastructure":{"partners":x["partners"],"activities":x["activities"],"resources":x["resources"]},"offer":x["value_propositions"],"customers":{"relationships":x["relationships"],"channels":x["channels"],"segments":x["segments"]},"finances":{"costs":x["costs"],"revenues":x["revenues"]}}},"business model canvas"
 if f==365:
  need("assumptions","tests");tests={t.get("assumption_id"):t for t in x["tests"] if isinstance(t,dict)};return {"assumption_board":[{"assumption":a.get("id"),"risk":a.get("risk","unknown"),"test":tests.get(a.get("id")),"status":"test_defined" if a.get("id") in tests else "untested"} for a in x["assumptions"]]},"lean assumption board"
 if f==366:
  need("segments","criteria");return {"segment_ranking":sorted([{"segment":s.get("id"),"score":sum(float(s.get("scores",{}).get(c.get("id"),0))*float(c.get("weight",1)) for c in x["criteria"])} for s in x["segments"]],key=lambda z:z["score"],reverse=True)},"segment attractiveness ranking"
 if f==367:
  need("observations","behaviors","goals","pain_points");return {"persona":{"observed_behaviors":x["behaviors"],"goals":x["goals"],"pain_points":x["pain_points"],"observation_count":len(x["observations"]),"fictional_details_added":False}},"evidence-backed persona"
 if f==368:
  need("stages","touchpoints","customer_actions","pain_points");return {"journey":[{"stage":s,"touchpoints":[t for t in x["touchpoints"] if not isinstance(t,dict) or t.get("stage")==s],"actions":[a for a in x["customer_actions"] if not isinstance(a,dict) or a.get("stage")==s],"pain_points":[p for p in x["pain_points"] if not isinstance(p,dict) or p.get("stage")==s]} for s in x["stages"]]},"customer journey"
 if f==369:
  need("observations","needs");return {"unmet_needs":[{"need":n.get("id",n) if isinstance(n,dict) else n,"evidence_count":sum((n.get("id",n) if isinstance(n,dict) else n) in o.get("need_ids",[]) for o in x["observations"] if isinstance(o,dict))} for n in x["needs"]]},"unmet-needs evidence count"
 if f==370:
  need("situations","outcomes","importance","satisfaction");return {"opportunity_scores":[{"situation":s,"outcome":o,"score":float(i)+max(float(i)-float(q),0)} for s,o,i,q in zip(x["situations"],x["outcomes"],x["importance"],x["satisfaction"])]},"outcome opportunity scoring"
 if f==371:
  need("push","pull","anxiety","habit");return {"forces":{"progress":len(x["push"])+len(x["pull"]),"inertia":len(x["anxiety"])+len(x["habit"]),"push":x["push"],"pull":x["pull"],"anxiety":x["anxiety"],"habit":x["habit"]}},"jobs-to-be-done forces"
 if f==372:
  need("hypothesis","metric","threshold","method");return {"test_card":{"hypothesis":x["hypothesis"],"metric":x["metric"],"threshold":x["threshold"],"method":x["method"],"outcome":"not_run"}},"hypothesis test card"
 if f==373:
  need("core_hypothesis","minimum_capabilities","excluded_scope","success_metric");return {"mvp_scope":{"core_hypothesis":x["core_hypothesis"],"included":x["minimum_capabilities"],"excluded":x["excluded_scope"],"success_metric":x["success_metric"],"deployed":False}},"MVP scope boundary"
 if f==374:
  need("channels","questions","sampling","coding_scheme");return {"user_test_protocol":{"channels":x["channels"],"question_count":len(x["questions"]),"sampling":x["sampling"],"coding_scheme":x["coding_scheme"],"responses_collected":0}},"user testing protocol"
 if f==375:
  need("signals","thresholds","observations");pairs=list(zip(x["signals"],x["thresholds"],x["observations"]));return {"pmf_scorecard":[{"signal":s,"threshold":t,"observed":o,"passed":float(o)>=float(t)} for s,t,o in pairs],"validated":bool(pairs) and all(float(o)>=float(t) for s,t,o in pairs)},"product-market-fit scorecard"
 if f==376:
  need("original_hypothesis","evidence","pivot_options","decision_rule");return {"pivot_review":{"hypothesis":x["original_hypothesis"],"evidence":x["evidence"],"options":x["pivot_options"],"decision_rule":x["decision_rule"],"decision":"human_required"}},"pivot/persevere gate"
 if f==377:
  need("tactics","constraints","expected_mechanisms");return {"growth_experiments":[{"tactic":t,"mechanism":m,"constraints":x["constraints"],"status":"proposed"} for t,m in zip(x["tactics"],x["expected_mechanisms"])]},"constraint-bound growth experiments"
 if f==384:
  need("customers","risk_signals","weights");return {"churn_risk":[{"customer":c.get("id"),"score":sum(float(c.get("signals",{}).get(s,0))*float(w) for s,w in zip(x["risk_signals"],x["weights"])),"prediction_only":True} for c in x["customers"]]},"weighted churn-risk rubric"
 if f==386:
  need("responses","scale");vals=[float(v) for v in x["responses"]];return {"csat":{"mean":fmean(vals),"responses":len(vals),"scale":x["scale"]}},"customer satisfaction mean"
 if f==387:
  need("feedback","coding_scheme");codes=x["coding_scheme"] if isinstance(x["coding_scheme"],dict) else {};return {"voice_of_customer":{"themes":{k:sum(any(term.lower() in str(v).lower() for term in terms) for v in x["feedback"]) for k,terms in codes.items()},"uncoded_count":len(x["feedback"]) if not codes else None}},"rule-based voice-of-customer coding"
 if f==389:
  need("outcomes","initiatives","dependencies","time_horizons");return {"roadmap":[{"horizon":h,"outcomes":[o for o in x["outcomes"] if not isinstance(o,dict) or o.get("horizon")==h],"initiatives":[i for i in x["initiatives"] if not isinstance(i,dict) or i.get("horizon")==h]} for h in x["time_horizons"]],"dependencies":x["dependencies"]},"outcome roadmap"
 if f==390:
  need("roles","cadence","definition_of_done","work_item_types");return {"sprint_plan":{"roles":x["roles"],"cadence":x["cadence"],"definition_of_done":x["definition_of_done"],"work_item_types":x["work_item_types"],"commitment":"not_started"}},"sprint operating plan"
 if f==391:
  need("items");return {"backlog":sorted(x["items"],key=lambda i:(i.get("priority",999),-float(i.get("value",0))))},"ordered backlog"
 if f==393:
  need("planned","completed","dates");return {"burndown":[{"date":d,"remaining":max(float(p)-float(c),0)} for p,c,d in zip(x["planned"],x["completed"],x["dates"])]},"burndown series"
 if f==394:
  need("states","wip_limits","policies");return {"kanban":{"columns":[{"state":s,"wip_limit":x["wip_limits"].get(s)} for s in x["states"]],"policies":x["policies"]}},"kanban policy board"
 if f==395:
  need("meetings","participants","cadence","outcomes");return {"ceremonies":[{"meeting":m,"participants":x["participants"],"cadence":x["cadence"],"expected_outcomes":x["outcomes"],"facilitated":False} for m in x["meetings"]]},"scrum ceremony plan"
 if f==396:
  need("went_well","did_not","actions","owners");return {"retrospective":{"went_well":x["went_well"],"did_not":x["did_not"],"action_register":[{"action":a,"owner":o,"status":"open"} for a,o in zip(x["actions"],x["owners"])]}},"retrospective action register"
 if f==397:
  need("hypothesis","primary_metric","randomization_unit","control","treatment","stopping_rule");return {"ab_test":{"hypothesis":x["hypothesis"],"primary_metric":x["primary_metric"],"randomization_unit":x["randomization_unit"],"arms":{"control":x["control"],"treatment":x["treatment"]},"stopping_rule":x["stopping_rule"],"status":"designed_not_run"}},"controlled A/B protocol"
 if f==398:
  need("factors","levels","primary_metric","allocation","multiple_testing_method");cells=1
  for level in x["levels"]: cells*=len(level)
  return {"multivariate_design":{"factors":x["factors"],"levels":x["levels"],"cell_count":cells,"primary_metric":x["primary_metric"],"allocation":x["allocation"],"multiple_testing_method":x["multiple_testing_method"],"status":"designed_not_run"}},"factorial test protocol"
 return None

_original_compute=BusinessAnalysisService._compute
def _compute_distinct(self,f:int,x:dict):
 specific=_row_specific_business(f,x)
 if specific is None: return _original_compute(self,f,x)
 result,method=specific;result["source_bound"]=True;result["fabricated_claims"]=False;return result,method
BusinessAnalysisService._compute=_compute_distinct
