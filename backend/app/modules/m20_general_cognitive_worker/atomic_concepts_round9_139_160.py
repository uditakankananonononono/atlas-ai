"""Atomic concepts 139-160: auditable business, data, social and corpus tools.

Outputs are calculations, decision records, plans, or retrieval candidates. They never
claim market capture, culture change, employee action, pipeline execution, emotional
truth, or external-source connection without evidence.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass,field
from hashlib import sha256
from math import log
import re
from typing import Any

CONCEPTS={
"360.1":"TAM calculation","360.2":"SAM calculation","360.3":"SOM calculation",
"361.1":"Competitor-strength mapping","361.2":"Competitor-weakness mapping",
"483.1":"Culture-value design","483.2":"Culture-norm design",
"492.1":"Objective definition","492.2":"Key-result definition",
"495.1":"Performance evaluation","495.2":"Performance improvement plan",
"535.1":"Data movement pipeline","535.2":"Data transformation pipeline",
"716.1":"Emotion-signal recognition","716.2":"Context-appropriate response selection",
"1106.1":"AIC computation and interpretation","1106.2":"BIC computation and interpretation",
"2010.1":"Owner writing-source connection/selection","2010.2":"Owner essay-source connection/selection",
"2010.3":"Owner activity-description connection/selection","2010.4":"Source-corpus indexing",
"2010.5":"Grounded application-drafting retrieval from source corpus",
}
RESEARCH={
"market":"https://www.sba.gov/business-guide/plan-your-business/market-research-competitive-analysis",
"teams":"https://rework.withgoogle.com/intl/en/guides/understand-team-effectiveness",
"etl":"https://www.ibm.com/think/insights/etl-best-practices",
"aic":"https://stat.ethz.ch/R-manual/R-devel/library/stats/html/AIC.html",
"emotion":"https://pmc.ncbi.nlm.nih.gov/articles/PMC8969204/",
}
class ConceptError(ValueError):pass
def need(p:dict,*keys:str):
 missing=[k for k in keys if p.get(k) in (None,[],{})]
 if missing:raise ConceptError("missing required inputs: "+", ".join(missing))
def number(p,key,nonnegative=True):
 need(p,key)
 try:v=float(p[key])
 except (TypeError,ValueError):raise ConceptError(f"{key} must be numeric")
 if nonnegative and v<0:raise ConceptError(f"{key} cannot be negative")
 return v

def _market(cid,p):
 need(p,"segments","currency"); rows=[]
 for i,s in enumerate(p["segments"]):
  if not isinstance(s,dict):raise ConceptError(f"segments[{i}] must be an object")
  need(s,"name","customers","annual_revenue_per_customer")
  customers=number(s,"customers"); arpc=number(s,"annual_revenue_per_customer")
  serviceable=float(s.get("serviceable_fraction",1)); obtainable=float(s.get("obtainable_fraction",0))
  if not 0<=serviceable<=1 or not 0<=obtainable<=1:raise ConceptError("fractions must be in [0,1]")
  tam=customers*arpc;sam=tam*serviceable;som=sam*obtainable
  rows.append({"name":s["name"],"tam":tam,"sam":sam,"som":som,"assumptions":s.get("assumptions",[])})
 totals={k:sum(r[k] for r in rows) for k in ("tam","sam","som")}
 target={"360.1":"tam","360.2":"sam","360.3":"som"}[cid]
 return {"method":"bottom_up","currency":p["currency"],"segments":rows,"totals":totals,"selected_metric":target,"selected_value":totals[target],"sanity_check_source":p.get("top_down_reference"),"captured_revenue_claimed":False,"research":RESEARCH["market"]}

def _competitive(cid,p):
 need(p,"criteria","competitors");criteria=p["criteria"];out=[]
 for c in p["competitors"]:
  need(c,"name","evidence","scores");missing=[x["id"] for x in criteria if x["id"] not in c["scores"]]
  if missing:raise ConceptError(f"competitor {c['name']} missing scores: {missing}")
  if not c["evidence"]:raise ConceptError("each competitor requires evidence")
  weighted=sum(float(x.get("weight",1))*float(c["scores"][x["id"]]) for x in criteria)
  maximum=sum(float(x.get("weight",1))*float(x.get("max_score",5)) for x in criteria)
  normalized=weighted/maximum if maximum else 0
  out.append({"name":c["name"],"normalized_strength":normalized,"normalized_weakness":1-normalized,"evidence":c["evidence"],"unknowns":c.get("unknowns",[])})
 metric="normalized_strength" if cid=="361.1" else "normalized_weakness"
 return {"metric":metric,"ranking":sorted(out,key=lambda x:(-x[metric],x["name"])),"evidence_date":p.get("evidence_date"),"unknown_is_not_weakness":True,"research":RESEARCH["market"]}

def _culture(cid,p):
 if cid=="483.1":
  need(p,"purpose","values");values=[]
  for v in p["values"]:
   need(v,"name","behavioral_examples","counterexamples");values.append({**v,"observable":True,"tradeoff_prompt":v.get("tradeoff_prompt",f"When should {v['name']} yield to another value?")})
  return {"purpose":p["purpose"],"values":values,"employee_input_required":True,"adoption_claimed":False,"research":RESEARCH["teams"]}
 need(p,"values","norms");known={v["name"] if isinstance(v,dict) else v for v in p["values"]};norms=[]
 for n in p["norms"]:
  need(n,"trigger","behavior","linked_value","repair")
  if n["linked_value"] not in known:raise ConceptError("norm references unknown value")
  norms.append({**n,"enforcement":"fair, documented, non-retaliatory","measured_by":n.get("measured_by")})
 return {"norms":norms,"voice_and_revision_cycle":p.get("revision_cycle","quarterly team review"),"imposed_without_review":False,"research":RESEARCH["teams"]}

def _okr(cid,p):
 if cid=="492.1":
  need(p,"objective","strategic_context","owner","horizon");obj=str(p["objective"]).strip()
  if any(ch.isdigit() for ch in obj):raise ConceptError("objective should be qualitative; put metrics in key results")
  return {"objective":obj,"strategic_context":p["strategic_context"],"owner":p["owner"],"horizon":p["horizon"],"qualities":{"directional":True,"outcome_oriented":True,"memorable":len(obj)<=120},"approved":False}
 need(p,"objective","key_results");out=[]
 for kr in p["key_results"]:
  need(kr,"metric","baseline","target","deadline","owner");base=float(kr["baseline"]);target=float(kr["target"])
  if base==target:raise ConceptError("key-result target must differ from baseline")
  out.append({**kr,"direction":"increase" if target>base else "decrease","progress_formula":"(current-baseline)/(target-baseline)","activity_metric":bool(kr.get("activity_metric",False))})
 return {"objective":p["objective"],"key_results":out,"count":len(out),"outcome_review_required":any(x["activity_metric"] for x in out),"achievement_claimed":False}

def _performance(cid,p):
 if cid=="495.1":
  need(p,"criteria","observations");ev=[]
  for c in p["criteria"]:
   matched=[o for o in p["observations"] if o.get("criterion_id")==c["id"]]
   ev.append({"criterion_id":c["id"],"weight":float(c.get("weight",1)),"evidence":matched,"rating":None if not matched else sum(float(x["rating"]) for x in matched)/len(matched),"insufficient_evidence":not matched})
  return {"criteria_evaluation":ev,"protected_trait_inference":False,"employee_response_window":True,"employment_decision_made":False}
 need(p,"gap","target_outcome","supports","checkpoints","owner");
 if not p.get("employee_input"):raise ConceptError("performance improvement plan requires employee input")
 return {"gap":p["gap"],"target_outcome":p["target_outcome"],"supports":p["supports"],"checkpoints":p["checkpoints"],"owner":p["owner"],"employee_input":p["employee_input"],"success_evidence":p.get("success_evidence",[]),"punitive_action_automated":False,"hr_review_required":True}

def _pipeline(cid,p):
 if cid=="535.1":
  need(p,"source","destination","schema","checkpoint");
  if p["source"]==p["destination"]:raise ConceptError("source and destination must differ")
  return {"source":p["source"],"destination":p["destination"],"mode":p.get("mode","incremental"),"checkpoint":p["checkpoint"],"schema":p["schema"],"idempotency_key":p.get("idempotency_key"),"dead_letter_destination":p.get("dead_letter_destination"),"lineage_recorded":True,"executed":False,"research":RESEARCH["etl"]}
 need(p,"input_schema","output_schema","steps","quality_checks");seen=set(p["input_schema"]);plan=[]
 for step in p["steps"]:
  need(step,"operation","inputs","outputs");missing=set(step["inputs"])-seen
  if missing:raise ConceptError(f"transform uses unavailable fields: {sorted(missing)}")
  seen.update(step["outputs"]);plan.append({**step,"deterministic":bool(step.get("deterministic",True))})
 missing_out=set(p["output_schema"])-seen
 if missing_out:raise ConceptError(f"output schema fields are not produced: {sorted(missing_out)}")
 return {"transform_plan":plan,"quality_checks":p["quality_checks"],"schema_contract":{"input":p["input_schema"],"output":p["output_schema"]},"test_before_promote":True,"executed":False,"research":RESEARCH["etl"]}

def _emotion(cid,p):
 if cid=="716.1":
  need(p,"signals");allowed={"explicit_self_report","message_wording","interaction_context"};out=[]
  for s in p["signals"]:
   if s.get("type") not in allowed:continue
   confidence=float(s.get("confidence",0));
   if not 0<=confidence<=1:raise ConceptError("confidence must be in [0,1]")
   out.append({"type":s["type"],"value":s.get("value"),"confidence":confidence,"interpretation":"tentative"})
  return {"recognized_signals":out,"emotion_claimed_as_fact":False,"diagnosis":None,"clarifying_question_required":not any(x["type"]=="explicit_self_report" for x in out),"research":RESEARCH["emotion"]}
 need(p,"context","candidate_responses");constraints=p.get("constraints",{});ranked=[]
 for r in p["candidate_responses"]:
  score=int(bool(r.get("acknowledges")))+int(bool(r.get("asks_preference")))+int(bool(r.get("respects_boundary")))-2*int(bool(r.get("diagnoses")))
  ranked.append({**r,"context_score":score})
 ranked.sort(key=lambda x:(-x["context_score"],str(x.get("text",""))))
 return {"selected":ranked[0] if ranked else None,"ranked":ranked,"context":p["context"],"constraints":constraints,"send_executed":False,"user_choice_preserved":True}

def _ic(cid,p):
 need(p,"log_likelihood","parameter_count","sample_size");ll=float(p["log_likelihood"]);k=int(p["parameter_count"]);n=int(p["sample_size"])
 if k<1 or n<=k+1:raise ConceptError("sample_size must exceed parameter_count + 1")
 aic=2*k-2*ll;bic=k*log(n)-2*ll;aicc=aic+(2*k*(k+1))/(n-k-1)
 metric="aic" if cid=="1106.1" else "bic";value=aic if metric=="aic" else bic
 return {"criterion":metric.upper(),"value":value,"aic":aic,"aicc":aicc,"bic":bic,"lower_is_preferred_only_among_same_data_and_likelihood":True,"not_absolute_fit":True,"research":RESEARCH["aic"]}

@dataclass
class Corpus:
 documents:dict[str,dict[str,Any]]=field(default_factory=dict)
 def select(self,kind:str,p:dict)->dict:
  need(p,"owner_id","sources");allowed={"writing","essay","activity"}
  if kind not in allowed:raise ConceptError("unsupported source kind")
  selected=[]
  for s in p["sources"]:
   need(s,"source_id","title","owner_confirmed");
   if not s["owner_confirmed"]:raise ConceptError("every selected source requires owner confirmation")
   selected.append({"source_id":s["source_id"],"title":s["title"],"kind":kind,"connected":bool(s.get("connected",False)),"indexed":False})
  return {"owner_id":p["owner_id"],"selected_sources":selected,"connection_claimed":all(x["connected"] for x in selected),"selection_persisted":False}
 def index(self,p:dict)->dict:
  need(p,"owner_id","documents");indexed=[]
  for d in p["documents"]:
   need(d,"source_id","kind","text");text=str(d["text"]).strip()
   if len(text)<20:raise ConceptError("document text is too short to index")
   chunks=[text[i:i+500] for i in range(0,len(text),450)];digest=sha256(text.encode()).hexdigest();self.documents[digest]={**d,"owner_id":p["owner_id"],"chunks":chunks}
   indexed.append({"document_id":digest,"source_id":d["source_id"],"kind":d["kind"],"chunk_count":len(chunks),"content_sha256":digest})
  return {"indexed":indexed,"owner_id":p["owner_id"],"source_of_truth":True,"embedding_claimed":False}
 def retrieve(self,p:dict)->dict:
  need(p,"owner_id","query");terms=set(re.findall(r"[a-z0-9]+",p["query"].lower()));hits=[]
  for doc_id,d in self.documents.items():
   if d["owner_id"]!=p["owner_id"]:continue
   for i,c in enumerate(d["chunks"]):
    overlap=len(terms&set(re.findall(r"[a-z0-9]+",c.lower())))
    if overlap:hits.append({"document_id":doc_id,"chunk_index":i,"source_id":d["source_id"],"kind":d["kind"],"text":c,"term_overlap":overlap})
  hits.sort(key=lambda x:(-x["term_overlap"],x["document_id"],x["chunk_index"]))
  return {"query":p["query"],"citations":hits[:int(p.get("limit",5))],"drafting_grounded_only_in_returned_citations":True,"draft_generated":False}

_default_corpus=Corpus()
def execute(cid:str,p:dict[str,Any],corpus:Corpus|None=None)->dict[str,Any]:
 if cid not in CONCEPTS:raise ConceptError("unknown atomic concept")
 if cid.startswith("360."):result=_market(cid,p)
 elif cid.startswith("361."):result=_competitive(cid,p)
 elif cid.startswith("483."):result=_culture(cid,p)
 elif cid.startswith("492."):result=_okr(cid,p)
 elif cid.startswith("495."):result=_performance(cid,p)
 elif cid.startswith("535."):result=_pipeline(cid,p)
 elif cid.startswith("716."):result=_emotion(cid,p)
 elif cid.startswith("1106."):result=_ic(cid,p)
 elif cid in {"2010.1","2010.2","2010.3"}:result=(corpus or _default_corpus).select({"2010.1":"writing","2010.2":"essay","2010.3":"activity"}[cid],p)
 elif cid=="2010.4":result=(corpus or _default_corpus).index(p)
 else:result=(corpus or _default_corpus).retrieve(p)
 return {"atomic_row_id":cid,"concept":CONCEPTS[cid],"result":result,"status":"computed_or_planned_not_externally_executed"}
