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
  return BusinessArtifact(idea_id=idea_id,feature=request.feature,method=method,inputs=request.inputs,assumptions=request.assumptions,provenance=request.provenance,result=result,uncertainty=Uncertainty(confidence=request.confidence,limitations=limitations,sample_size=result.get("sample_size"),interval_low=result.get("interval_low"),interval_high=result.get("interval_high")),decision=decision)
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
