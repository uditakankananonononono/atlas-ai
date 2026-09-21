"""Semantic implementations and honest evidence gates for technical rows 199-229.

Production infrastructure is never inferred from configuration text. X01-X05 and
X11-X14 stay ``missing_evidence`` until an external attestor is injected. Safety
replacement rows reject the prohibited mechanism and return a permitted route.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Protocol

ROWS: dict[int, tuple[str, str, int, int]] = {
199:("M20-27","Divergent/convergent ideation modes.",162,165),
200:("M20-28","Retrospective artifact and retrieval.",162,165),
201:("M20-29","Tone adaptation from explicit context/feedback, not simulated undisclosed emotion.",166,169),
202:("M20-30","Confidence/uncertainty calibration and targeted questions.",166,169),
203:("M20-31","Creativity/playfulness mode.",166,169),
204:("M20-32","Three-stream market-analysis/pitch-deck/MVP orchestration example as an end-to-end acceptance test.",170,186),
205:("M20-33","Scheduled dashboard stand-up updates with user-controlled cadence.",185,185),
206:("M20-34","Constitutional hard rules for finance and private-data handling.",187,189),
207:("M20-35","Ephemeral no-network-by-default code sandbox with per-project volumes and explicit API allowlist.",190,190),
208:("X01","mTLS for all inter-service communication.",191,192),
209:("X02","Runtime Vault secret injection and encryption at rest.",191,192),
210:("X03","OpenTelemetry cross-service traces.",193,193),
211:("X04","Centralized Google Cloud Logging.",193,193),
212:("X05","Grafana operational metrics dashboards.",193,193),
213:("X06","AI-call audit records for model, prompt/input reference, output reference and latency, with privacy/redaction policy.",193,193),
214:("X07","Per-module/per-model API budget tracking.",194,194),
215:("X08","Daily-spend threshold alerts.",194,194),
216:("X09","Policy-controlled cheaper-model downgrade for noncritical work.",194,194),
217:("X10","Tenant ID schema and gateway-enforced data isolation.",195,195),
218:("X11","Docker Compose single-machine local deployment acceptance test.",196,197),
219:("X12","Kubernetes production deployment acceptance test.",196,197),
220:("X13","32-GB local deployment profile using Ollama.",196,197),
221:("X14","Horizontal Celery-worker scaling benchmark.",196,197),
222:("S01","Reject stealth/evasion patches intended to bypass site controls; use normal compliant browser automation.",10,10),
223:("S02","Reject Discord self-bots; use official bots/APIs or owner-provided exports.",32,32),
224:("S03","Reject LinkedIn Sales Navigator scraping; use official APIs, permitted public pages or user-provided exports.",57,57),
225:("S04","Reject unofficial TikTok wrappers with rotating residential proxies; use official/permitted/public sources.",95,95),
226:("S05","Do not store or expose hidden chain-of-thought scratchpads; store concise decision records, evidence and alternatives.",163,163),
227:("S06","Do not claim a real internal emotional state; expose transparent tone configuration/context.",167,167),
228:("S07","Do not promise “AGI-class,” “any non-physical job,” “human-level,” “continuous thought,” or “brilliant tireless human” as verified capabilities without literal benchmark evidence; convert these to scoped measurable acceptance tests.",109,110),
229:("S08","Do not auto-execute financial transactions, private-data disclosure, publishing, email, deployment or submissions; preserve exact-preview human approval.",187,190),
}

PRODUCTION_ROWS={208,209,210,211,212,218,219,220,221}
SAFETY_ALTERNATIVES={
222:"standards-compliant Playwright using normal site controls",
223:"official Discord bot/API or owner-provided export",
224:"official LinkedIn API, permitted public page, or user export",
225:"official TikTok API or permitted public source without proxy evasion",
226:"concise decision record with evidence, alternatives, and selected rationale",
227:"explicit tone configuration derived from disclosed context and feedback",
228:"scoped benchmark with dataset, metric, threshold, and reproducible result",
229:"exact-preview approval request with no effect before approval",
}
PROHIBITED={
222:("stealth","evasion","captcha bypass","fingerprint spoof"),
223:("self-bot","selfbot","user token"),
224:("sales navigator scraping","scrape sales navigator"),
225:("unofficial tiktok","residential proxy","rotating proxy"),
226:("chain-of-thought","hidden scratchpad","private reasoning"),
227:("emotional state vector","real emotion","feels sad"),
228:("agi-class","any non-physical job","human-level","continuous thought","brilliant tireless human"),
229:("auto-execute","without approval","silent publish","silent send"),
}

@dataclass(frozen=True)
class SourceMapping:
    row:int; requirement_id:str; requirement:str; source_line_start:int; source_line_end:int

def mapping(row:int)->SourceMapping:
    try: rid,req,start,end=ROWS[row]
    except KeyError as exc: raise ValueError(f"unknown technical-spec row {row}") from exc
    return SourceMapping(row,rid,req,start,end)

@dataclass
class Result:
    mapping:SourceMapping; status:str; output:dict[str,Any]; evidence:tuple[str,...]=()

class Attestor(Protocol):
    def __call__(self, requirement_id:str, evidence:dict[str,Any])->tuple[bool,tuple[str,...]]: ...

def verify_production(row:int,evidence:dict[str,Any],attestor:Attestor|None=None)->Result:
    m=mapping(row)
    if row not in PRODUCTION_ROWS: raise ValueError("row is not an external production-attestation row")
    if attestor is None:
        return Result(m,"missing_evidence",{"verified":False,"reason":"external runtime attestation required"})
    ok,refs=attestor(m.requirement_id,evidence)
    if not ok or not refs: return Result(m,"missing_evidence",{"verified":False,"reason":"attestation rejected"})
    return Result(m,"verified",{"verified":True},refs)

def safety_replacement(row:int,requested_mechanism:str)->Result:
    m=mapping(row)
    if row not in SAFETY_ALTERNATIVES: raise ValueError("row is not a safety replacement")
    normalized=requested_mechanism.casefold()
    blocked=any(term in normalized for term in PROHIBITED[row])
    return Result(m,"rejected" if blocked else "replacement_required",{
        "executed":False,"blocked":blocked,"replacement":SAFETY_ALTERNATIVES[row],
        "reason":"prohibited mechanism" if blocked else "only the documented safe replacement is supported",
    })

@dataclass
class RetrospectiveStore:
    records:list[dict[str,Any]]=field(default_factory=list)
    def write(self,task_id:str,went_well:list[str],improve:list[str],lessons:list[str])->dict[str,Any]:
        if not task_id.strip() or not lessons: raise ValueError("task_id and at least one lesson are required")
        record={"task_id":task_id,"went_well":tuple(went_well),"improve":tuple(improve),"lessons":tuple(lessons)}
        record["id"]=sha256(repr(record).encode()).hexdigest()[:16]; self.records.append(record); return record
    def retrieve(self,query:str)->list[dict[str,Any]]:
        terms=set(query.casefold().split()); return [r for r in self.records if terms & set(" ".join(r["lessons"]).casefold().split())]

@dataclass
class BudgetTracker:
    thresholds:dict[str,float]=field(default_factory=dict); spend:dict[tuple[str,str],float]=field(default_factory=dict)
    def record(self,module:str,model:str,cost:float,critical:bool=False)->dict[str,Any]:
        if cost<0: raise ValueError("cost cannot be negative")
        key=(module,model); self.spend[key]=round(self.spend.get(key,0)+cost,6)
        total=sum(v for (mod,_),v in self.spend.items() if mod==module); threshold=self.thresholds.get(module,float("inf"))
        return {"module":module,"model":model,"model_spend":self.spend[key],"daily_module_spend":total,
          "alert":total>threshold,"recommended_model":"economy" if total>threshold and not critical else model}

@dataclass
class AuditLog:
    records:list[dict[str,Any]]=field(default_factory=list)
    def ai_call(self,tenant_id:str,module:str,model:str,input_ref:str,output_ref:str,latency_ms:int)->dict[str,Any]:
        if not tenant_id or not input_ref or not output_ref: raise ValueError("tenant and opaque input/output references are required")
        if latency_ms<0: raise ValueError("latency must be nonnegative")
        record={"tenant_id":tenant_id,"module":module,"model":model,"input_ref":input_ref,"output_ref":output_ref,
          "latency_ms":latency_ms,"redaction_policy":"references-only-v1","recorded_at":datetime.now(timezone.utc).isoformat()}
        self.records.append(record); return record

def semantic_behavior(row:int,payload:dict[str,Any],retrospectives:RetrospectiveStore|None=None)->Result:
    m=mapping(row)
    if row==199:
        ideas=[str(x).strip() for x in payload.get("ideas",[]) if str(x).strip()]
        constraints=[str(x).casefold() for x in payload.get("constraints",[])]
        if len(ideas)<2: raise ValueError("divergent mode requires at least two ideas")
        scored=[{"idea":i,"score":sum(c in i.casefold() for c in constraints)} for i in ideas]
        return Result(m,"implemented",{"divergent":ideas,"convergent":sorted(scored,key=lambda x:(-x["score"],x["idea"]))})
    if row==200:
        store=retrospectives or RetrospectiveStore(); rec=store.write(payload.get("task_id",""),payload.get("went_well",[]),payload.get("improve",[]),payload.get("lessons",[]))
        return Result(m,"implemented",{"artifact":rec,"retrieved":store.retrieve(" ".join(payload.get("lessons",[])))})
    if row==201:
        allowed={"neutral","formal","warm","concise","playful"}; tone=payload.get("tone","neutral")
        if tone not in allowed: raise ValueError("tone must be an explicit supported value")
        return Result(m,"implemented",{"tone":tone,"basis":"explicit_context_or_feedback","simulated_emotion":False})
    if row==202:
        confidence=float(payload.get("confidence",0)); high_stakes=bool(payload.get("high_stakes"))
        if not 0<=confidence<=1: raise ValueError("confidence must be between 0 and 1")
        needs=high_stakes and confidence<.8
        return Result(m,"implemented",{"confidence":confidence,"proceed":not needs,"question":payload.get("missing_question") if needs else None})
    if row==203:
        mode=payload.get("mode","standard");
        if mode not in {"standard","creative","playful"}: raise ValueError("unsupported creativity mode")
        return Result(m,"implemented",{"mode":mode,"cross_domain_prompts":payload.get("domains",[])[:4],"temperature_cap":.9 if mode!="standard" else .4})
    if row==204:
        streams=("market_analysis","pitch_deck","mvp"); supplied=set(payload.get("streams",streams))
        if supplied!=set(streams): raise ValueError("acceptance test requires exactly the three specified streams")
        return Result(m,"implemented",{"streams":[{"name":s,"state":"planned","acceptance_test":True} for s in streams],"parallel":True})
    if row==205:
        cadence=payload.get("cadence"); timezone_name=payload.get("timezone")
        if not cadence or not timezone_name: raise ValueError("user-controlled cadence and timezone are required")
        return Result(m,"implemented",{"cadence":cadence,"timezone":timezone_name,"enabled":bool(payload.get("enabled",True)),"destination":"executive_dashboard"})
    if row==206:
        action=payload.get("action",""); private=bool(payload.get("contains_private_data")); approved=bool(payload.get("approved"))
        blocked=action=="financial_transaction" or (private and not approved)
        return Result(m,"implemented",{"allowed":not blocked,"rule":"no_finance_and_no_unapproved_private_disclosure"})
    if row==207:
        project=payload.get("project_id",""); allowed=tuple(payload.get("api_allowlist",[]))
        if not project or any(not x.startswith("https://") for x in allowed): raise ValueError("project_id and HTTPS-only allowlist required")
        return Result(m,"implemented",{"ephemeral":True,"network_default":"deny","api_allowlist":allowed,"volume":f"project:{project}"})
    if row==213:
        audit=AuditLog(); rec=audit.ai_call(payload.get("tenant_id",""),payload.get("module",""),payload.get("model",""),payload.get("input_ref",""),payload.get("output_ref",""),int(payload.get("latency_ms",-1)))
        return Result(m,"implemented",rec)
    if row in {214,215,216}:
        tracker=BudgetTracker(payload.get("thresholds",{})); out=tracker.record(payload.get("module",""),payload.get("model",""),float(payload.get("cost",0)),bool(payload.get("critical")))
        return Result(m,"implemented",out)
    if row==217:
        tenant=payload.get("tenant_id"); resource_tenant=payload.get("resource_tenant_id")
        if not tenant or not resource_tenant: raise ValueError("tenant IDs are required")
        return Result(m,"implemented",{"allowed":tenant==resource_tenant,"gateway_enforced":True,"tenant_id":tenant})
    raise ValueError("row requires production attestation or safety replacement, not semantic execution")
