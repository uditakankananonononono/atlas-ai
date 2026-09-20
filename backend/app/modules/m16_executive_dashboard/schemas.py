from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel,Field
class ApprovalState(str,Enum):PENDING="pending";APPROVED="approved";REJECTED="rejected";EXPIRED="expired"
class Event(BaseModel):id:str;sequence:int;topic:str;aggregate_type:str;aggregate_id:str;payload:dict[str,Any];occurred_at:datetime
class Snapshot(BaseModel):version:int;last_sequence:int;generated_at:datetime;data:dict[str,Any]
class Approval(BaseModel):id:str;module_id:int;action_type:str;title:str;summary:str;risk:str="medium";evidence:dict[str,Any]=Field(default_factory=dict);proposed_payload:dict[str,Any]=Field(default_factory=dict);state:ApprovalState=ApprovalState.PENDING;created_at:datetime;expires_at:datetime|None=None;reviewed_at:datetime|None=None
class ApprovalDecision(BaseModel):approve:bool;note:str|None=Field(None,max_length=2000)
class CommandRequest(BaseModel):utterance:str=Field(min_length=2,max_length=4000)
class CommandPreview(BaseModel):id:str;utterance:str;intent:str;parameters:dict[str,Any];plan:list[dict[str,Any]];read_only:bool;confidence:float;expires_at:datetime;created_at:datetime
class TimelineItem(BaseModel):id:str;title:str;start:datetime;end:datetime;progress:float=Field(0,ge=0,le=1);dependencies:list[str]=Field(default_factory=list);critical:bool=False;at_risk:bool=False;module_id:int|None=None
# Cross-module status, KPI, blocker and drilldown schemas (additive).
class AgentState(str,Enum):RUNNING="running";IDLE="idle";STALLED="stalled";OFFLINE="offline"
class AgentHeartbeat(BaseModel):module_id:int;agent_id:str=Field(min_length=1,max_length=120);state:AgentState=AgentState.RUNNING;current_task:str|None=Field(None,max_length=500);detail:dict[str,Any]=Field(default_factory=dict)
class AgentStatus(AgentHeartbeat):last_heartbeat:datetime
class EvidenceRef(BaseModel):kind:str;id:str;summary:str;sequence:int|None=None
class ModuleStatus(BaseModel):module_id:int;slug:str;name:str;implemented:bool;agent:AgentStatus|None=None;pending_approvals:int=0;events_24h:int=0;open_blockers:int=0
class KPI(BaseModel):id:str;label:str;unit:str="count";value:float=0;previous_value:float|None=None;window_hours:int=24;definition:str="";evidence:list[EvidenceRef]=Field(default_factory=list);evidence_total:int=0
class BlockerSeverity(str,Enum):CRITICAL="critical";WARNING="warning";INFO="info"
class Blocker(BaseModel):id:str;kind:str;severity:BlockerSeverity;summary:str;module_id:int|None=None;evidence:list[EvidenceRef]=Field(default_factory=list);recommended_action:str="";detected_at:datetime
class DashboardOverview(BaseModel):generated_at:datetime;modules:list[ModuleStatus];kpis:list[KPI];blockers:list[Blocker];pending_approvals:int;critical_path:list[str]
class DrilldownResult(BaseModel):subject:EvidenceRef;detail:dict[str,Any]=Field(default_factory=dict);events:list[Event]=Field(default_factory=list);approvals:list[Approval]=Field(default_factory=list)
class EventIn(BaseModel):id:str|None=None;topic:str=Field(min_length=1,max_length=120);aggregate_type:str=Field(min_length=1,max_length=80);aggregate_id:str=Field(min_length=1,max_length=200);payload:dict[str,Any]=Field(default_factory=dict);occurred_at:datetime|None=None
class KpiDefinitionIn(BaseModel):id:str=Field(min_length=2,max_length=80,pattern=r"^[a-z][a-z0-9_]*$");label:str=Field(min_length=2,max_length=120);unit:str="count";topics:list[str]=Field(min_length=1);window_hours:int|None=Field(None,ge=1,le=24*30)
class KpiDefinitionOut(KpiDefinitionIn):created_at:datetime
class DigestSection(BaseModel):title:str;lines:list[str]
class Digest(BaseModel):generated_at:datetime;pending_approvals:int;open_blockers:int;sections:list[DigestSection]
class AlertComparator(str,Enum):GT="gt";GTE="gte";LT="lt";LTE="lte"
class AlertRuleIn(BaseModel):id:str=Field(min_length=2,max_length=80,pattern=r"^[a-z][a-z0-9_]*$");kpi_id:str=Field(min_length=2,max_length=80);comparator:AlertComparator;threshold:float;severity:BlockerSeverity=BlockerSeverity.WARNING;message:str|None=Field(None,max_length=300);cooldown_hours:int=Field(1,ge=1,le=168)
class AlertRuleOut(AlertRuleIn):created_at:datetime
class BulkApprovalDecision(BaseModel):approval_ids:list[str]=Field(min_length=1,max_length=100);approve:bool;note:str|None=Field(None,max_length=2000)
class BulkDecisionResult(BaseModel):decided:list[Approval];skipped:list[dict[str,str]]
class WidgetKind(str,Enum):KPI_CARD="kpi_card";MODULE_STATUS="module_status";BLOCKERS="blockers";TIMELINE="timeline";APPROVALS="approvals";ALERTS="alerts";DIGEST="digest"
class WidgetConfig(BaseModel):id:str=Field(min_length=1,max_length=80);kind:WidgetKind;kpi_id:str|None=None;visible:bool=True;position:int=Field(0,ge=0)
class DashboardView(BaseModel):widgets:list[WidgetConfig];updated_at:datetime
class DashboardViewIn(BaseModel):widgets:list[WidgetConfig]=Field(max_length=50)
