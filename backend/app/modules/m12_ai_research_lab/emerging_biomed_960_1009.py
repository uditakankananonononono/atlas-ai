"""Preclinical biomedical/neurotechnology study calculators, ledger rows 960-1009.
No function recommends treatment or controls a device; outputs support study design only.
"""
from __future__ import annotations
import math,statistics
NAMES="""regenerative_medicine stem_cell_therapy gene_therapy crispr_applications base_editing prime_editing epigenome_editing synthetic_biology metabolic_engineering protein_engineering directed_evolution enzyme_design antibody_design vaccine_design drug_discovery drug_repurposing personalized_medicine pharmacogenomics microbiome_engineering probiotic_design phage_therapy immunotherapy car_t_therapy checkpoint_inhibitors mrna_therapeutics nanomedicine targeted_drug_delivery theranostics liquid_biopsy wearable_sensors implantable_devices brain_computer_interfaces neural_prosthetics cochlear_implants retinal_implants deep_brain_stimulation optogenetics chemogenetics neurofeedback brain_mapping connectomics neural_decoding neural_encoding memory_prosthetics cognitive_enhancement nootropics neurostimulation transcranial_magnetic_stimulation focused_ultrasound neural_dust""".split()
ROWS=dict(zip(NAMES,range(960,1010)))
def _n(d,k,default=None):
 v=d.get(k,default)
 if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v):raise ValueError(f"{k} must be finite")
 return float(v)
def _v(d,k,n=1):
 v=d.get(k)
 if not isinstance(v,list) or len(v)<n or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in v):raise ValueError(f"{k} requires {n}+ finite numbers")
 return list(map(float,v))
def _rates(d):
 successes=_n(d,"successes");total=_n(d,"total");control=_n(d,"control_successes",0);ct=_n(d,"control_total",total)
 if min(total,ct)<=0 or not 0<=successes<=total or not 0<=control<=ct:raise ValueError("valid success/total counts required")
 rate=successes/total;cr=control/ct;return {"response_rate":rate,"control_rate":cr,"absolute_effect":rate-cr,"relative_effect":rate/cr if cr else None,"n":int(total)}
def _classification(d):
 tp,fp,tn,fn=[_n(d,k) for k in ("true_positive","false_positive","true_negative","false_negative")]
 if min(tp,fp,tn,fn)<0 or tp+fn==0 or tn+fp==0:raise ValueError("nonnegative confusion counts with both classes required")
 return {"sensitivity":tp/(tp+fn),"specificity":tn/(tn+fp),"precision":tp/(tp+fp) if tp+fp else 0,"false_positive_rate":fp/(fp+tn)}
def _signal(d):
 signal=_v(d,"signal",2);truth=_v(d,"reference",2)
 if len(signal)!=len(truth):raise ValueError("aligned signal/reference required")
 err=[a-b for a,b in zip(signal,truth)];ms=sum(x*x for x in err)/len(err);var=statistics.pvariance(truth)
 return {"rmse":math.sqrt(ms),"correlation":_corr(signal,truth),"explained_variance_proxy":1-ms/var if var else None,"samples":len(signal)}
def _corr(a,b):
 ma,mb=statistics.mean(a),statistics.mean(b);den=math.sqrt(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b));return sum((x-ma)*(y-mb) for x,y in zip(a,b))/den if den else 0
def run(method,data):
 if method not in ROWS:raise ValueError(f"unsupported emerging-biomed method {method}")
 limits=["Research-use-only calculation from caller-supplied data; not medical advice, diagnosis, treatment selection, dosing, device control, or regulatory evidence."]
 # Tissue/cell modalities: quantify viability, engraftment and functional improvement.
 if method in {"regenerative_medicine","stem_cell_therapy"}:
  seeded=_n(data,"cells_seeded");viable=_n(data,"viable_cells");engrafted=_n(data,"engrafted_cells");baseline=_n(data,"baseline_function");follow=_n(data,"followup_function");out={"viability":viable/seeded,"engraftment":engrafted/viable,"functional_change":follow-baseline}
 # Genome/epigenome editing: efficiency plus bystander/off-target burden.
 elif method in {"gene_therapy","crispr_applications","base_editing","prime_editing","epigenome_editing"}:
  edited=_n(data,"edited_reads");total=_n(data,"total_reads");
  if total<=0 or edited<0 or edited>total:raise ValueError("valid read counts required")
  off=_n(data,"off_target_reads",0);byst=_n(data,"bystander_reads",0);out={"edit_efficiency":edited/total,"off_target_rate":off/total,"bystander_rate":byst/total,"precision":max(0,(edited-off-byst)/total)}
 # Engineering/design candidates: rank explicit assay scores, never infer efficacy.
 elif method in {"synthetic_biology","protein_engineering","directed_evolution","enzyme_design","antibody_design","vaccine_design","drug_discovery","drug_repurposing","personalized_medicine","pharmacogenomics","probiotic_design","immunotherapy","checkpoint_inhibitors","mrna_therapeutics","nanomedicine","targeted_drug_delivery","theranostics","cognitive_enhancement","nootropics"}:
  candidates=data.get("candidates");weights=_v(data,"weights")
  if not isinstance(candidates,list) or not candidates:raise ValueError("candidates required")
  scored=[]
  for c in candidates:
   metrics=_v(c,"metrics")
   if len(metrics)!=len(weights):raise ValueError("candidate metrics must align with weights")
   scored.append({"id":c["id"],"score":sum(x*w for x,w in zip(metrics,weights))})
  out={"ranked_candidates":sorted(scored,key=lambda x:x["score"],reverse=True),"criteria_count":len(weights)};limits += ["Ranking reflects supplied assay criteria/weights and does not establish clinical benefit."]
 elif method=="metabolic_engineering":
  product=_n(data,"product_moles");substrate=_n(data,"substrate_moles");theoretical=_n(data,"theoretical_yield");biomass=_n(data,"biomass");time=_n(data,"hours");out={"molar_yield":product/substrate,"percent_theoretical":product/substrate/theoretical,"specific_productivity":product/(biomass*time)}
 elif method=="microbiome_engineering":
  before=_v(data,"abundance_before",2);after=_v(data,"abundance_after",2)
  if len(before)!=len(after) or sum(before)<=0 or sum(after)<=0:raise ValueError("aligned positive-sum abundances required")
  pb=[x/sum(before) for x in before];pa=[x/sum(after) for x in after];out={"shannon_before":-sum(x*math.log(x) for x in pb if x),"shannon_after":-sum(x*math.log(x) for x in pa if x),"bray_curtis_change":sum(abs(a-b) for a,b in zip(before,after))/sum(a+b for a,b in zip(before,after))}
 elif method=="phage_therapy":
  initial=_n(data,"initial_bacteria");final=_n(data,"final_bacteria");moi=_n(data,"phage_particles")/initial;out={"log10_reduction":math.log10(initial/final),"multiplicity_of_infection":moi,"fraction_remaining":final/initial}
 elif method in {"car_t_therapy"}:
  out=_rates(data);out["expansion_fold"]=_n(data,"peak_car_t_cells")/_n(data,"baseline_car_t_cells")
 elif method=="liquid_biopsy":out=_classification(data)|{"limit_of_detection":_n(data,"limit_of_detection")}
 elif method in {"wearable_sensors","implantable_devices"}:
  out=_signal(data);out["uptime"]=_n(data,"valid_samples")/_n(data,"expected_samples");out["drift_per_day"]=_n(data,"end_calibration_error",0)-_n(data,"start_calibration_error",0)
 elif method in {"brain_computer_interfaces","neural_prosthetics","neural_decoding"}:
  out=_classification(data);out["information_transfer_bits_per_minute"]=_n(data,"bits_correct")/_n(data,"minutes")
 elif method in {"cochlear_implants","retinal_implants","memory_prosthetics"}:
  baseline=_v(data,"baseline_scores",2);follow=_v(data,"followup_scores",2)
  if len(baseline)!=len(follow):raise ValueError("aligned scores required")
  diffs=[b-a for a,b in zip(baseline,follow)];out={"mean_change":statistics.mean(diffs),"responder_rate":sum(x>=_n(data,"responder_threshold",0) for x in diffs)/len(diffs),"paired_changes":diffs}
 elif method in {"deep_brain_stimulation","optogenetics","chemogenetics","neurofeedback","neurostimulation","transcranial_magnetic_stimulation","focused_ultrasound"}:
  out=_rates(data);out["adverse_event_rate"]=_n(data,"adverse_events",0)/_n(data,"total");out["protocol"]={k:data.get(k) for k in ("frequency_hz","intensity","duration_minutes")};limits += ["Protocol is recorded for study provenance only and must not be used to operate a device."]
 elif method=="brain_mapping":
  activations=_v(data,"regional_activation",2);labels=data.get("region_labels")
  if not isinstance(labels,list) or len(labels)!=len(activations):raise ValueError("region labels align")
  out={"peak_region":labels[max(range(len(activations)),key=lambda i:activations[i])],"z_scores":[(x-statistics.mean(activations))/(statistics.stdev(activations) or 1) for x in activations]}
 elif method=="connectomics":
  nodes=data.get("nodes");edges=data.get("edges")
  if not isinstance(nodes,list) or not isinstance(edges,list):raise ValueError("nodes/edges required")
  degree={x:0 for x in nodes}
  for a,b in edges:degree[a]+=1;degree[b]+=1
  n=len(nodes);out={"density":2*len(edges)/(n*(n-1)) if n>1 else 0,"degree":degree,"hub":max(degree,key=degree.get) if degree else None}
 elif method=="neural_encoding":
  stimulus=_v(data,"stimulus",2);response=_v(data,"response",2)
  if len(stimulus)!=len(response):raise ValueError("aligned stimulus/response required")
  mx,my=statistics.mean(stimulus),statistics.mean(response);slope=sum((x-mx)*(y-my) for x,y in zip(stimulus,response))/sum((x-mx)**2 for x in stimulus);out={"linear_gain":slope,"intercept":my-slope*mx,"correlation":_corr(stimulus,response)}
 elif method=="neural_dust":
  transmitted=_n(data,"packets_transmitted");received=_n(data,"packets_received");energy=_n(data,"energy_mj");time=_n(data,"hours");out={"packet_delivery_rate":received/transmitted,"energy_per_received_packet":energy/received,"operating_hours":time}
 else:raise AssertionError(method)
 out["method_limits"]=limits
 return {"method":method,"feature_row":ROWS[method],"inputs":data,"output":out,
  "evaluation":{"calculator_executed":True,"metric_fields":sorted(k for k in out if k != "method_limits"),"input_fields":sorted(data),"qualified_review_required":True},
  "uncertainty":{"method_limits":limits,"clinical_effect_established":False,"regulatory_evidence_established":False,"device_or_treatment_executed":False,"caller_supplied_data_not_independently_verified":True}}
