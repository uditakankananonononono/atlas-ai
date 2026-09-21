from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, Field, HttpUrl, model_validator

class CaptureState(StrEnum): ACTIVE='active'; PAUSED='paused'; STOPPED='stopped'; BLOCKED='blocked'; FAILED='failed'
class SourceKind(StrEnum): SCREEN_OCR='screen_ocr'; MIC='mic'; SYSTEM_AUDIO='system_audio'; KNOWLEDGE='knowledge'
class ActionKind(StrEnum): SEND='send'; SUBMIT='submit'; PURCHASE='purchase'; RECORDING_STATE='recording_state'; EXTERNAL_MUTATION='external_mutation'
class CopilotMode(StrEnum): MEETING='meeting'; STUDY='study'; RESEARCH='research'
class Redaction(BaseModel): pattern:str=Field(min_length=1,max_length=200); replacement:str='[REDACTED]'
class CaptureStart(BaseModel):
 device_id:str=Field(min_length=1,max_length=128); selected_screen_ids:list[str]=Field(min_length=1,max_length=8); redactions:list[Redaction]=Field(default_factory=list,max_length=50)
class AudioStart(BaseModel):
 sources:set[SourceKind]=Field(min_length=1); consent:bool; max_buffer_seconds:int=Field(ge=1,le=300)
 @model_validator(mode='after')
 def audio_only(self):
  if not self.sources <= {SourceKind.MIC,SourceKind.SYSTEM_AUDIO}: raise ValueError('audio sources must be mic/system_audio')
  if not self.consent: raise ValueError('explicit audio consent is required')
  return self
class IngestEvent(BaseModel):
 source:SourceKind; content:str=Field(min_length=1,max_length=20000); source_ref:str=Field(min_length=1,max_length=500); screen_id:str|None=None; observed_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc)); speaker:str|None=Field(default=None,max_length=100); speaker_confidence:float|None=Field(default=None,ge=0,le=1); language:str|None=Field(default=None,max_length=35)
class TimelineItem(BaseModel): id:str; source:SourceKind; content:str; source_ref:str; observed_at:datetime; speaker:str|None=None; speaker_confidence:float|None=Field(default=None,ge=0,le=1); language:str|None=None
class SourceCitation(BaseModel): item_id:str; source_ref:str; quote:str=Field(min_length=1,max_length=500)
class CopilotRequest(BaseModel): mode:CopilotMode; prompt:str=Field(min_length=1,max_length=4000); citation_item_ids:list[str]=Field(min_length=1,max_length=30); output_language:str=Field(default='en',min_length=2,max_length=35); assessment_declared:bool=False; observed_context:list[str]=Field(default_factory=list,max_length=20)
class CopilotDraft(BaseModel): mode:CopilotMode; status:str='draft'; content:str; citations:list[SourceCitation]; learner_work_preserved:bool=False; follow_up_questions:list[str]=Field(default_factory=list); summary:str|None=None; action_items:list[str]=Field(default_factory=list); output_language:str='en'; refused:bool=False; reason:str|None=None
class ClaimInput(BaseModel): claim:str=Field(min_length=1,max_length=2000); evidence_item_ids:list[str]=Field(min_length=1,max_length=30)
class ClaimEvidence(BaseModel): claim:str; evidence:list[SourceCitation]; trace_complete:bool
class ApprovalRequest(BaseModel): action:ActionKind; destination:str=Field(min_length=1,max_length=500); exact_preview:str=Field(min_length=1,max_length=20000)
class ApprovalDecision(BaseModel): approved:bool
class ApprovalRecord(BaseModel): id:str; action:ActionKind; destination:str; exact_preview:str; approved:bool|None=None; executed:bool=False
class FailureReport(BaseModel): component:str=Field(min_length=1,max_length=100); reason:str=Field(min_length=1,max_length=1000); blocked:bool=True
class SessionView(BaseModel): id:str; state:CaptureState; selected_screen_ids:list[str]; indicator_visible:bool; audio_consent_indicator:bool; buffer_seconds:int; timeline:list[TimelineItem]
