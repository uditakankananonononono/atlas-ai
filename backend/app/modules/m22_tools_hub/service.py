"""Tools Hub: compliant discovery and approval-gated integrations."""
from __future__ import annotations
import asyncio,csv,hashlib,io,json,os,re,time,uuid
from dataclasses import asdict,dataclass,field
from datetime import datetime,timezone
from typing import Any,AsyncIterator,Protocol
from urllib.parse import parse_qsl,urlencode,urlparse,urlunparse
from app.core.models import ApprovalRequest
MODULE_ID=22

def now():return datetime.now(timezone.utc)
now_dt=now
class Collector(Protocol):
    name:str
    async def collect(self,query:str)->AsyncIterator[dict[str,Any]]:...
class ApprovalStore(Protocol):
    def put(self,item:ApprovalRequest)->ApprovalRequest:...
@dataclass
class Candidate:
    name:str;url:str;summary:str;source:str;version:str|None=None;license:str|None=None;permissions:list[str]=field(default_factory=list);maintenance:float=0.;security:float=0.;fit:float=0.;novelty:float=0.;evidence:list[dict[str,Any]]=field(default_factory=list);id:str=field(default_factory=lambda:str(uuid.uuid4()));kind:str="tool";weights:dict[str,float]|None=None
    DEFAULT_WEIGHTS={"fit":.30,"security":.25,"maintenance":.20,"novelty":.15,"evidence":.10}
    def _signal_values(self):
        return {"fit":self.fit,"security":self.security,"maintenance":self.maintenance,"novelty":self.novelty,"evidence":min(1.,len(self.evidence)/3)}
    @property
    def score(self):
        values=self._signal_values()
        if self.weights:
            total=sum(float(self.weights.get(k,0.)) for k in values)
            if total<=0:return 0.
            return round(sum(float(self.weights.get(k,0.))*v for k,v in values.items())/total,4)
        return round(sum(w*values[k] for k,w in self.DEFAULT_WEIGHTS.items()),4)
    def explain(self)->dict[str,Any]:
        """Why this candidate ranked where it did: per-signal value x weight = contribution."""
        values=self._signal_values();weights=self.weights or self.DEFAULT_WEIGHTS
        total=sum(float(weights.get(k,0.)) for k in values) if self.weights else 1.
        contributions={k:{"value":round(v,4),"weight":weights.get(k,0.),"contribution":round(float(weights.get(k,0.))*v/(total or 1.),4)} for k,v in values.items()}
        return {"score":self.score,"kind":self.kind,"source":self.source,"weighted":bool(self.weights),"contributions":contributions}
@dataclass
class InstallationProposal:
    candidate_id:str;adapter_type:str;config:dict[str,Any];requested_scopes:list[str];rollback_plan:dict[str,Any];approval_id:str;id:str=field(default_factory=lambda:str(uuid.uuid4()))
class Service:
    BLOCKED_DOMAINS={"oceanofpdf.com"};BLOCKED_PATTERNS=("self-bot","rotating proxy","credential stuffing","bypass paywall","stealth scraping")
    def __init__(self,approval_store:ApprovalStore,collectors:list[Collector]=[],state_path:str|None=None,source_cooldown_seconds:float|None=None,require_https:bool|None=None):
        self.approvals=approval_store;self.collectors=collectors;self.candidates={};self.proposals={};self.installed={};self.last_errors:dict[str,str]={}
        self.state_path=state_path
        self.source_cooldown_seconds=float(source_cooldown_seconds if source_cooldown_seconds is not None else os.environ.get("ATLAS_M22_SOURCE_COOLDOWN_SECONDS",300))
        self.require_https=(os.environ.get("ATLAS_M22_ALLOW_INSECURE","")!="1") if require_https is None else require_https
        self.blocked_domains=set(self.BLOCKED_DOMAINS);self.blocked_patterns=set(self.BLOCKED_PATTERNS)
        self._cooldown_until:dict[str,float]={};self.source_stats:dict[str,dict[str,Any]]={}
        self.query_history:list[dict[str,Any]]=[];self._query_snapshots:dict[str,dict[str,str]]={};self.last_diffs:dict[str,dict[str,Any]]={}
        self._load_blocks()
    @staticmethod
    def _validate_weights(weights:dict[str,float])->None:
        allowed={"fit","security","maintenance","novelty","evidence"}
        unknown=set(weights)-allowed
        if unknown:raise ValueError(f"unknown scoring signals: {sorted(unknown)}")
        if any(float(v)<0 for v in weights.values()):raise ValueError("scoring weights must be non-negative")
        if sum(float(v) for v in weights.values())<=0:raise ValueError("at least one scoring weight must be positive")
    async def _drain(self,collector:Collector,query:str,weights=None)->list[Candidate]:
        found=[]
        async for raw in collector.collect(query):
            candidate=self._normalize(raw,collector.name,weights=weights)
            if candidate:found.append(candidate)
        return found
    async def _drain_timed(self,collector:Collector,query:str,weights=None)->list[Candidate]:
        started=time.monotonic()
        try:
            found=await self._drain(collector,query,weights=weights)
        except Exception:
            stats=self.source_stats.setdefault(collector.name,{"runs":0,"failures":0,"candidates":0,"last_latency_ms":0.,"last_status":"never run"})
            stats["runs"]+=1;stats["failures"]+=1;stats["last_latency_ms"]=round((time.monotonic()-started)*1000,1);stats["last_status"]="error"
            if self.source_cooldown_seconds>0:self._cooldown_until[collector.name]=time.time()+self.source_cooldown_seconds
            raise
        stats=self.source_stats.setdefault(collector.name,{"runs":0,"failures":0,"candidates":0,"last_latency_ms":0.,"last_status":"never run"})
        stats["runs"]+=1;stats["candidates"]+=len(found);stats["last_latency_ms"]=round((time.monotonic()-started)*1000,1);stats["last_status"]="ok"
        return found
    async def discover(self,query:str,kinds:list[str]|None=None,weights:dict[str,float]|None=None)->list[Candidate]:
        if weights is not None:self._validate_weights(weights)
        selected=[c for c in self.collectors if not kinds or getattr(c,"kind","tool") in kinds]
        now=time.time();active=[];self.last_errors={}
        for c in selected:
            until=self._cooldown_until.get(c.name,0.)
            if until>now:self.last_errors[c.name]=f"in cooldown after a failure until {datetime.fromtimestamp(until,timezone.utc).isoformat()}"
            else:active.append(c)
        results=await asyncio.gather(*(self._drain_timed(c,query,weights) for c in active),return_exceptions=True)
        found=[]
        for collector,result in zip(active,results):
            if isinstance(result,Exception):self.last_errors[collector.name]=str(result);continue
            found.extend(result)
        dedup={self._key(x):x for x in found};ranked=sorted(dedup.values(),key=lambda x:x.score,reverse=True)
        self.candidates.update({x.id:x for x in ranked})
        snapshot={self._key(x):x.name for x in ranked}
        previous=self._query_snapshots.get(query)
        self.last_diffs[query]={"first_run":previous is None,"added":[name for k,name in snapshot.items() if previous is not None and k not in previous],"removed":[name for k,name in (previous or {}).items() if k not in snapshot]}
        self._query_snapshots[query]=snapshot
        self.query_history=[*self.query_history[-199:],{"query":query,"kinds":kinds,"at":now_dt().isoformat(),"count":len(ranked)}]
        return ranked
    async def discover_many(self,queries:list[str],kinds:list[str]|None=None,weights:dict[str,float]|None=None)->dict[str,Any]:
        """Batch discovery: one call, one deduped+ranked merge across queries."""
        if len(queries)>20:raise ValueError("at most 20 queries per batch")
        per_query={}
        for q in queries:per_query[q]=await self.discover(q,kinds=kinds,weights=weights)
        merged={}
        for items in per_query.values():
            for x in items:merged.setdefault(self._key(x),x)
        return {"per_query":per_query,"merged":sorted(merged.values(),key=lambda x:x.score,reverse=True)}
    def discovery_report(self,query:str)->dict[str,Any]:
        ranked=sorted((c for c in self.candidates.values()),key=lambda x:x.score,reverse=True)
        return {"query":query,"candidates":[asdict(x)|{"score":x.score} for x in ranked],"diff":self.last_diffs.get(query),"errors":dict(self.last_errors),"sources":self.sources()}
    def export_candidates(self,fmt:str="json")->str:
        """Export the current candidate store as json, csv or markdown."""
        items=sorted(self.candidates.values(),key=lambda x:x.score,reverse=True)
        if fmt=="json":return json.dumps([asdict(x)|{"score":x.score} for x in items],indent=1)
        if fmt=="csv":
            out=io.StringIO();writer=csv.writer(out)
            writer.writerow(["name","kind","source","score","url","summary"])
            for x in items:writer.writerow([x.name,x.kind,x.source,x.score,x.url,x.summary.replace("\n"," ")])
            return out.getvalue()
        if fmt in ("markdown","md"):
            lines=["# Tools Hub candidate digest","",f"{len(items)} candidates, ranked by score.",""]
            for x in items:lines.append(f"- **{x.name}** ({x.kind} via {x.source}, score {x.score}) - {x.url}")
            return "\n".join(lines)+"\n"
        raise ValueError(f"unknown export format {fmt!r}; use json, csv or markdown")
    # -- runtime blocklist (persisted under state_path) ---------------------
    def _blocks_file(self)->str|None:
        return os.path.join(self.state_path,"m22_blocks.json") if self.state_path else None
    def _load_blocks(self)->None:
        path=self._blocks_file()
        if not path:return
        try:
            with open(path,encoding="utf-8") as fh:saved=json.load(fh)
            self.blocked_domains|={str(d).lower() for d in saved.get("domains",[])}
            self.blocked_patterns|={str(p) for p in saved.get("patterns",[])}
        except (OSError,json.JSONDecodeError):pass
    def _save_blocks(self)->None:
        path=self._blocks_file()
        if not path:return
        os.makedirs(os.path.dirname(path) or ".",exist_ok=True)
        tmp=f"{path}.{os.getpid()}.tmp"
        with open(tmp,"w",encoding="utf-8") as fh:json.dump({"domains":sorted(self.blocked_domains),"patterns":sorted(self.blocked_patterns)},fh,indent=1)
        os.replace(tmp,path)
    def blocks(self)->dict[str,list[str]]:
        return {"domains":sorted(self.blocked_domains),"patterns":sorted(self.blocked_patterns)}
    def add_block(self,kind:str,value:str)->dict[str,list[str]]:
        value=value.strip()
        if not value:raise ValueError("block value is required")
        if kind=="domains":self.blocked_domains.add(value.lower())
        elif kind=="patterns":self.blocked_patterns.add(value.lower())
        else:raise ValueError("kind must be 'domains' or 'patterns'")
        self._save_blocks();return self.blocks()
    def remove_block(self,kind:str,value:str)->dict[str,list[str]]:
        if kind=="domains":self.blocked_domains.discard(value.strip().lower())
        elif kind=="patterns":self.blocked_patterns.discard(value.strip().lower())
        else:raise ValueError("kind must be 'domains' or 'patterns'")
        self._save_blocks();return self.blocks()
    def _normalize(self,x,source,weights=None):
        url=x.get("url","");text=f"{x.get('name','')} {x.get('summary','')}".lower()
        host=urlparse(url).hostname or ""
        if self.require_https and url and urlparse(url).scheme!="https":return None
        if host.lower() in self.blocked_domains or any(p in text for p in self.blocked_patterns):return None
        return Candidate(x["name"],url,x.get("summary",""),source,x.get("version"),x.get("license"),x.get("permissions",[]),float(x.get("maintenance",.5)),float(x.get("security",.5)),float(x.get("fit",.5)),float(x.get("novelty",.5)),x.get("evidence",[]),kind=x.get("kind","tool"),weights=weights)
    @staticmethod
    def _canonical_url(url:str)->str:
        """Canonical form for dedup: lowercase host, no default ports, no
        tracking parameters, sorted query, no fragment, no trailing slash."""
        try:p=urlparse(url)
        except Exception:return url or ""
        host=(p.netloc or "").lower()
        if p.scheme=="https" and host.endswith(":443"):host=host[:-4]
        if p.scheme=="http" and host.endswith(":80"):host=host[:-3]
        pairs=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith("utm_") and k.lower() not in ("fbclid","gclid","mc_cid","mc_eid")]
        pairs.sort()
        path=p.path.rstrip("/") or "/"
        return urlunparse(((p.scheme or "https").lower(),host,path,"",urlencode(pairs),""))
    @staticmethod
    def _key(c):return hashlib.sha256(f"{c.name.lower()}|{Service._canonical_url(c.url)}".encode()).hexdigest()
    def propose_install(self,candidate_id:str,adapter_type:str,config:dict[str,Any],scopes:list[str]):
        c=self.candidates.get(candidate_id)
        if not c:raise KeyError("candidate not found")
        if c.security<.5:raise ValueError("security review failed")
        rollback={"strategy":"snapshot_then_restore","remove_credentials":True,"disable_adapter":True,"candidate":c.name}
        req=self.approvals.put(ApprovalRequest(id=str(uuid.uuid4()),module_id=MODULE_ID,action_type="integrate_tool",payload={"candidate_id":c.id,"name":c.name,"url":c.url,"adapter_type":adapter_type,"config_preview":{k:v for k,v in config.items() if "secret" not in k.lower() and "token" not in k.lower()},"requested_scopes":scopes,"rollback_plan":rollback,"score":c.score}))
        p=InstallationProposal(c.id,adapter_type,config,scopes,rollback,req.id);self.proposals[p.id]=p;return p
    def mark_integrated(self,proposal_id:str,evidence:dict[str,Any]):
        p=self.proposals[proposal_id]
        required=("operation_id","artifact_sha256","manifest_digest","installed_at","receipt_path")
        missing=[x for x in required if not evidence.get(x)]
        if missing:raise ValueError("integration evidence missing: "+", ".join(missing))
        digest=lambda x:isinstance(x,str) and bool(re.fullmatch(r"[0-9a-f]{64}",x))
        if not digest(evidence["artifact_sha256"]) or not digest(evidence["manifest_digest"]):raise ValueError("integration evidence digests must be lowercase SHA-256")
        if evidence.get("approval_id")!=p.approval_id:raise ValueError("integration receipt approval does not match proposal")
        if evidence.get("candidate_id")!=p.candidate_id:raise ValueError("integration receipt candidate does not match proposal")
        receipt={**evidence,"verified_binding":True,"rollback_available":bool(evidence.get("backup_id")),"execution_claim":"installer receipt supplied and proposal binding verified; runtime behavior not independently verified"}
        self.installed[p.candidate_id]={"proposal":p,"evidence":receipt,"installed_at":now()};return self.installed[p.candidate_id]
    def sources(self)->list[dict[str,Any]]:
        return [{"name":c.name,"kind":getattr(c,"kind","tool"),"last_error":self.last_errors.get(c.name),**self.source_stats.get(c.name,{"runs":0,"failures":0,"candidates":0,"last_latency_ms":0.,"last_status":"never run"})} for c in self.collectors]
    def portfolio(self):return [{"candidate":self.candidates[k],**v} for k,v in self.installed.items()]
