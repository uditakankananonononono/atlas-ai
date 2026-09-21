from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from re import IGNORECASE, sub
from threading import RLock
from types import MappingProxyType
from uuid import uuid4
from .schemas import *

@dataclass
class _Session:
 id:str; tenant_id:str; actor_id:str; device_id:str; screens:list[str]; redactions:list[Redaction]
 state:CaptureState=CaptureState.ACTIVE; indicator:bool=True; audio_indicator:bool=False; max_buffer:int=0
 timeline:list[TimelineItem]=field(default_factory=list); audio:deque[TimelineItem]=field(default_factory=deque)

class Repository:
 def __init__(self): self.sessions={}; self.approvals={}; self.audit=defaultdict(list); self.lock=RLock()
 def own(self,tenant,actor,sid):
  s=self.sessions.get(sid)
  if not s or (s.tenant_id,s.actor_id)!=(tenant,actor): raise KeyError('session not found')
  return s
 def append_audit(self,tenant,actor,event,detail):
  key=(tenant,actor); prior=self.audit[key][-1]['hash'] if self.audit[key] else 'GENESIS'; at=datetime.now(timezone.utc).isoformat()
  digest=sha256(f'{prior}|{at}|{event}|{detail}'.encode()).hexdigest()
  row={'at':at,'event':event,'detail':detail,'prior_hash':prior,'hash':digest}; self.audit[key].append(row); return row

class Service:
 EXAM_MARKERS=('exam','quiz','test in progress','proctored','assessment','question paper','lockdown browser')
 def __init__(self,repo=None): self.repo=repo or Repository()
 def _audit(self,t,a,e,d): return self.repo.append_audit(t,a,e,d)
 def start_capture(self,t,a,data:CaptureStart):
  sid=str(uuid4()); s=_Session(sid,t,a,data.device_id,list(dict.fromkeys(data.selected_screen_ids)),data.redactions); self.repo.sessions[sid]=s
  self._audit(t,a,'capture_started',{'session':sid,'screens':s.screens}); return self.view(t,a,sid)
 def view(self,t,a,sid):
  s=self.repo.own(t,a,sid); return SessionView(id=s.id,state=s.state,selected_screen_ids=s.screens,indicator_visible=s.indicator,audio_consent_indicator=s.audio_indicator,buffer_seconds=s.max_buffer,timeline=s.timeline)
 def recording_state(self,t,a,sid,state:CaptureState):
  if state not in (CaptureState.PAUSED,CaptureState.ACTIVE,CaptureState.STOPPED): raise ValueError('unsupported recording transition')
  s=self.repo.own(t,a,sid)
  if s.state==CaptureState.STOPPED: raise RuntimeError('stopped session cannot restart')
  s.state=state
  if state==CaptureState.STOPPED: s.indicator=False;s.audio_indicator=False;s.audio.clear()
  self._audit(t,a,f'capture_{state.value}',{'session':sid}); return self.view(t,a,sid)
 def start_audio(self,t,a,sid,data:AudioStart):
  s=self.repo.own(t,a,sid)
  if s.state!=CaptureState.ACTIVE: raise RuntimeError('capture is not active')
  s.audio_indicator=True;s.max_buffer=data.max_buffer_seconds;self._audit(t,a,'audio_consent',{'session':sid,'sources':sorted(x.value for x in data.sources),'max_seconds':s.max_buffer});return self.view(t,a,sid)
 def ingest(self,t,a,sid,data:IngestEvent):
  s=self.repo.own(t,a,sid)
  if s.state!=CaptureState.ACTIVE: raise RuntimeError(f'capture is {s.state.value}')
  if data.source==SourceKind.SCREEN_OCR and data.screen_id not in s.screens: raise PermissionError('screen is outside owner selection')
  if data.source in (SourceKind.MIC,SourceKind.SYSTEM_AUDIO) and not s.audio_indicator: raise PermissionError('audio consent indicator is not active')
  text=data.content
  for r in s.redactions: text=sub(r.pattern,r.replacement,text,flags=IGNORECASE)
  item=TimelineItem(id=str(uuid4()),source=data.source,content=text,source_ref=data.source_ref,observed_at=data.observed_at,speaker=data.speaker,speaker_confidence=data.speaker_confidence,language=data.language);s.timeline.append(item)
  if data.source in (SourceKind.MIC,SourceKind.SYSTEM_AUDIO):
   s.audio.append(item); cutoff=item.observed_at.timestamp()-s.max_buffer
   while s.audio and s.audio[0].observed_at.timestamp()<cutoff:
    expired=s.audio.popleft();s.timeline=[x for x in s.timeline if x.id!=expired.id]
  self._audit(t,a,'timeline_ingest',{'session':sid,'item':item.id,'source':item.source.value});return item
 def _cites(self,s,ids):
  by={x.id:x for x in s.timeline}; missing=[x for x in ids if x not in by]
  if missing: raise ValueError(f'unknown source items: {missing}')
  return [SourceCitation(item_id=by[x].id,source_ref=by[x].source_ref,quote=by[x].content[:500]) for x in ids]
 def copilot(self,t,a,sid,data:CopilotRequest):
  s=self.repo.own(t,a,sid); context=' '.join([data.prompt,*data.observed_context]).lower()
  if data.assessment_declared or any(x in context for x in self.EXAM_MARKERS):
   self._audit(t,a,'exam_assistance_refused',{'session':sid});return CopilotDraft(mode=data.mode,content='I cannot provide real-time answers during an assessment.',citations=[],refused=True,reason='live_assessment_context')
  cites=self._cites(s,data.citation_item_ids)
  if data.mode==CopilotMode.MEETING: content='Draft meeting note: '+data.prompt
  elif data.mode==CopilotMode.STUDY: content='Hint: break the problem into steps and compare your current work with the cited source.'
  else: content='Research draft: validate each claim against the cited evidence.'
  self._audit(t,a,'copilot_draft_created',{'session':sid,'mode':data.mode.value});return CopilotDraft(mode=data.mode,content=content,citations=cites,learner_work_preserved=data.mode==CopilotMode.STUDY,follow_up_questions=['What evidence would change this conclusion?','What should happen next?'],summary='; '.join(c.quote for c in cites),action_items=['Review and approve the draft before any external action.'] if data.mode==CopilotMode.MEETING else [],output_language=data.output_language)
 def claim_table(self,t,a,sid,claims:list[ClaimInput]):
  s=self.repo.own(t,a,sid); out=[ClaimEvidence(claim=c.claim,evidence=self._cites(s,c.evidence_item_ids),trace_complete=True) for c in claims];self._audit(t,a,'claim_table_created',{'session':sid,'claims':len(out)});return out
 def propose(self,t,a,data:ApprovalRequest):
  rid=str(uuid4());r=ApprovalRecord(id=rid,**data.model_dump());self.repo.approvals[rid]=(t,a,r);self._audit(t,a,'action_proposed',{'approval':rid,'action':data.action.value,'destination':data.destination,'exact_preview':data.exact_preview});return r
 def decide(self,t,a,rid,data:ApprovalDecision):
  owner=self.repo.approvals.get(rid)
  if not owner or owner[:2]!=(t,a):raise KeyError('approval not found')
  r=owner[2]
  if r.approved is not None:raise RuntimeError('approval already decided')
  r.approved=data.approved;self._audit(t,a,'action_approved' if data.approved else 'action_rejected',{'approval':rid});return r
 def execute(self,t,a,rid,executor):
  owner=self.repo.approvals.get(rid)
  if not owner or owner[:2]!=(t,a):raise KeyError('approval not found')
  r=owner[2]
  if r.approved is not True:raise PermissionError('exact preview approval required')
  if r.executed:raise RuntimeError('action already executed')
  try: executor(r.action,r.destination,r.exact_preview)
  except Exception as exc:
   self._audit(t,a,'action_failed',{'approval':rid,'reason':str(exc)});raise RuntimeError(f'external action failed: {exc}') from exc
  r.executed=True;self._audit(t,a,'action_executed',{'approval':rid});return r
 def failure(self,t,a,sid,data:FailureReport):
  s=self.repo.own(t,a,sid);s.state=CaptureState.BLOCKED if data.blocked else CaptureState.FAILED;self._audit(t,a,'component_blocked' if data.blocked else 'component_failed',data.model_dump());return self.view(t,a,sid)
 def audit_log(self,t,a): return tuple(MappingProxyType(dict(x)) for x in self.repo.audit[(t,a)])
