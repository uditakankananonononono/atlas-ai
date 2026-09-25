"""Tools Hub: compliant discovery and approval-gated integrations."""
from __future__ import annotations
import asyncio,hashlib,re,uuid
from dataclasses import dataclass,field
from datetime import datetime,timezone
from typing import Any,AsyncIterator,Protocol
from urllib.parse import urlparse
from app.core.models import ApprovalRequest
MODULE_ID=22

def now():return datetime.now(timezone.utc)
class Collector(Protocol):
    name:str
    async def collect(self,query:str)->AsyncIterator[dict[str,Any]]:...
class ApprovalStore(Protocol):
    def put(self,item:ApprovalRequest)->ApprovalRequest:...
@dataclass
class Candidate:
    name:str;url:str;summary:str;source:str;version:str|None=None;license:str|None=None;permissions:list[str]=field(default_factory=list);maintenance:float=0.;security:float=0.;fit:float=0.;novelty:float=0.;evidence:list[dict[str,Any]]=field(default_factory=list);id:str=field(default_factory=lambda:str(uuid.uuid4()));kind:str="tool"
    @property
    def score(self):return round(.30*self.fit+.25*self.security+.20*self.maintenance+.15*self.novelty+.10*min(1,len(self.evidence)/3),4)
@dataclass
class InstallationProposal:
    candidate_id:str;adapter_type:str;config:dict[str,Any];requested_scopes:list[str];rollback_plan:dict[str,Any];approval_id:str;id:str=field(default_factory=lambda:str(uuid.uuid4()))
class Service:
    BLOCKED_DOMAINS={"oceanofpdf.com"};BLOCKED_PATTERNS=("self-bot","rotating proxy","credential stuffing","bypass paywall","stealth scraping")
    def __init__(self,approval_store:ApprovalStore,collectors:list[Collector]=[]):self.approvals=approval_store;self.collectors=collectors;self.candidates={};self.proposals={};self.installed={};self.last_errors:dict[str,str]={}
    async def _drain(self,collector:Collector,query:str)->list[Candidate]:
        found=[]
        async for raw in collector.collect(query):
            candidate=self._normalize(raw,collector.name)
            if candidate:found.append(candidate)
        return found
    async def discover(self,query:str)->list[Candidate]:
        results=await asyncio.gather(*(self._drain(c,query) for c in self.collectors),return_exceptions=True)
        found=[];self.last_errors={}
        for collector,result in zip(self.collectors,results):
            if isinstance(result,Exception):self.last_errors[collector.name]=str(result);continue
            found.extend(result)
        dedup={self._key(x):x for x in found};ranked=sorted(dedup.values(),key=lambda x:x.score,reverse=True)
        self.candidates.update({x.id:x for x in ranked});return ranked
    def _normalize(self,x,source):
        url=x.get("url","");text=f"{x.get('name','')} {x.get('summary','')}".lower()
        if urlparse(url).hostname in self.BLOCKED_DOMAINS or any(p in text for p in self.BLOCKED_PATTERNS):return None
        return Candidate(x["name"],url,x.get("summary",""),source,x.get("version"),x.get("license"),x.get("permissions",[]),float(x.get("maintenance",.5)),float(x.get("security",.5)),float(x.get("fit",.5)),float(x.get("novelty",.5)),x.get("evidence",[]),kind=x.get("kind","tool"))
    @staticmethod
    def _key(c):return hashlib.sha256(f"{c.name.lower()}|{urlparse(c.url).netloc}".encode()).hexdigest()
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
        return [{"name":c.name,"kind":getattr(c,"kind","tool"),"last_error":self.last_errors.get(c.name)} for c in self.collectors]
    def portfolio(self):return [{"candidate":self.candidates[k],**v} for k,v in self.installed.items()]
