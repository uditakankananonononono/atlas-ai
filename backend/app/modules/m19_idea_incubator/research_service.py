"""Deterministic and evidence-bound research methods; no invented papers or outcomes."""
from __future__ import annotations
from math import log,sqrt
from statistics import fmean,NormalDist
from .research_models import *
METHODS={110:"structured literature synthesis",111:"citation-network map",112:"evidence-gap map",113:"falsifiable hypothesis card",114:"experimental-design protocol",116:"confounder DAG checklist",117:"randomization protocol",118:"blinding protocol",119:"replication protocol",122:"publication-bias diagnostics plan",123:"researcher-degrees-of-freedom audit",124:"preregistration record",125:"open-science checklist",126:"reproducibility audit",127:"pre-submission peer-review rubric",128:"journal scope-and-policy match",129:"citation-scenario estimate",130:"structured abstract",131:"accurate title candidates",132:"figure specification",133:"statistical test decision tree"}
REQ={110:("studies","research_question","inclusion_criteria","exclusion_criteria"),111:("papers","citations"),112:("included_studies","dimensions","observed_coverage"),113:("observed_pattern","theory","population","outcome","falsifier"),114:("hypothesis","outcome","factors","constraints","analysis_plan"),116:("exposure","outcome","candidate_variables","temporal_order","causal_assumptions"),117:("units","arms","allocation_ratio","strata","seed_policy"),118:("roles","assignments","blinded_roles","unblinding_rule"),119:("original_protocol","target_effect","deviations","materials","analysis_plan"),122:("studies","effect_sizes","standard_errors","search_scope"),123:("outcomes","predictors","subgroups","transformations","stopping_rules"),124:("hypotheses","outcomes","exclusions","sample_size_rule","analysis_plan","timestamp_policy"),125:("data_plan","code_plan","materials_plan","license","repository","privacy_constraints"),126:("artifacts","environment","steps","expected_outputs","checksums"),127:("manuscript_sections","claims","methods","limitations","target_audience"),128:("manuscript_scope","methods","audience","candidate_venues","venue_policies"),129:("historical_comparables","field","publication_year","documented_features"),130:("background","objective","methods","results","limitations","conclusion"),131:("study_design","population","intervention_or_exposure","outcome","main_finding"),132:("data","variables","figure_purpose","uncertainty_encoding","accessibility"),133:("outcome_type","design","groups","paired","distribution_assumptions","estimand")}
class ResearchAnalysisService:
 def analyze(self,idea_id,r):
  f=int(r.feature);analysis,method=self._compute(f,r.inputs);limits=[]
  if r.confidence<.5:limits.append("Input confidence is low.")
  if any(p.source_type=="public_source" and not p.uri for p in r.provenance):limits.append("A public source lacks a URI and cannot be checked.")
  limits.extend(analysis.pop("method_caveats",[]));claims={"invented_studies":False,"impact_prediction":False,"evidence_bound":True}
  if f==129:claims["impact_prediction"]="scenario_only"
  return ResearchArtifact(idea_id=idea_id,feature=r.feature,method=method,inputs=r.inputs,provenance=r.provenance,assumptions=r.assumptions,analysis=analysis,uncertainty=Uncertainty(confidence=r.confidence,limitations=limits,sample_size=analysis.get("sample_size"),interval_low=analysis.get("interval_low"),interval_high=analysis.get("interval_high")),claims=claims)
 def _compute(self,f,x):
  if f==115:
   d=PowerInput.model_validate(x);zalpha=NormalDist().inv_cdf(1-d.alpha/2);zpower=NormalDist().inv_cdf(d.power);per_group=2*((zalpha+zpower)/d.effect_size)**2
   return {"sample_size_per_group":int(per_group)+1,"total_sample_size":d.groups*(int(per_group)+1),"effect_size":d.effect_size,"method_caveats":["Normal approximation for a balanced two-sided comparison; simulation or specialized formulas may be required."]},"approximate power analysis"
  if f==120:
   studies=[MetaStudy.model_validate(v) for v in x.get("studies",[])]
   if not studies:raise ValueError("studies are required")
   weights=[1/s.standard_error**2 for s in studies];fixed=sum(w*s.effect for w,s in zip(weights,studies))/sum(weights);se=sqrt(1/sum(weights));q=sum(w*(s.effect-fixed)**2 for w,s in zip(weights,studies));df=len(studies)-1;i2=max(0,(q-df)/q)*100 if q else 0
   return {"fixed_effect":fixed,"standard_error":se,"interval_low":fixed-1.96*se,"interval_high":fixed+1.96*se,"q":q,"i_squared_percent":i2,"sample_size":len(studies),"method_caveats":["Fixed-effect model assumes one common true effect; heterogeneity and dependence need review."]},"inverse-variance fixed-effect meta-analysis"
  if f==121:
   d=EffectSizeInput.model_validate(x);pooled=sqrt(((d.treatment_n-1)*d.treatment_sd**2+(d.control_n-1)*d.control_sd**2)/(d.treatment_n+d.control_n-2));cohen=(d.treatment_mean-d.control_mean)/pooled;j=1-3/(4*(d.treatment_n+d.control_n)-9);return {"cohens_d":cohen,"hedges_g":j*cohen,"mean_difference":d.treatment_mean-d.control_mean,"sample_size":d.treatment_n+d.control_n,"method_caveats":["Standardized effects depend on scale reliability and pooled-SD assumptions."]},"standardized mean difference"
  if f==134:
   d=BayesianInput.model_validate(x);a=d.prior_alpha+d.successes;b=d.prior_beta+d.trials-d.successes;mean=a/(a+b);sd=sqrt(a*b/((a+b)**2*(a+b+1)));return {"posterior_alpha":a,"posterior_beta":b,"posterior_mean":mean,"interval_low":max(0,mean-1.96*sd),"interval_high":min(1,mean+1.96*sd),"sample_size":d.trials,"method_caveats":["Interval uses a normal approximation to the beta posterior; report prior sensitivity."]},"beta-binomial Bayesian update"
  required=REQ.get(f)
  if required:
   missing=[k for k in required if k not in x or x[k] in (None,[],{})]
   if missing:raise ValueError("missing required inputs: "+", ".join(missing))
   result={"sections":{k:x[k] for k in required},"source_bound":True,"study_count":len(x.get("studies",x.get("included_studies",[]))) if isinstance(x.get("studies",x.get("included_studies",[])),list) else None}
   caveats=[]
   if f==110:caveats.append("Synthesis covers only supplied studies and screening criteria; it is not automatically exhaustive.")
   if f==111:caveats.append("Citation edges show references, not endorsement or causal influence.")
   if f==112:caveats.append("A coverage gap is not proof that a question is valuable or unexplored outside the supplied corpus.")
   if f==129:caveats.append("Citation counts are not predicted; only documented comparables and scenario assumptions are returned.")
   if f==132:caveats.append("This produces a figure specification, not rendered publication artwork.")
   result["method_caveats"]=caveats;return result,METHODS[f]
  raise ValueError(f"unsupported research feature row {f}")
