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
# --- planning & measurement entities (feature rows 388-399) ---
WORK_ITEM_STATUSES=("backlog","ready","in_progress","review","done")
class WorkItemIn(BaseModel):title:str=Field(min_length=1,max_length=300);item_type:str=Field("feature",max_length=40);estimate:float|None=Field(None,ge=0);reach:float|None=None;impact:float|None=None;confidence:float|None=Field(None,ge=0,le=1);effort:float|None=Field(None,ge=0);value:float|None=Field(None,ge=0);sprint_id:str|None=None;roadmap_id:str|None=None;planned_start:datetime|None=None;planned_end:datetime|None=None
class WorkItemPatch(BaseModel):title:str|None=None;status:str|None=None;estimate:float|None=Field(None,ge=0);reach:float|None=None;impact:float|None=None;confidence:float|None=Field(None,ge=0,le=1);effort:float|None=Field(None,ge=0);value:float|None=Field(None,ge=0);rank:int|None=None;sprint_id:str|None=None;roadmap_id:str|None=None;planned_start:datetime|None=None;planned_end:datetime|None=None
class WorkItemOut(WorkItemIn):id:str;status:str="backlog";rank:int=0;created_at:datetime;updated_at:datetime;completed_at:datetime|None=None
class PrioritizedItem(BaseModel):item:WorkItemOut;method:str;score:float|None;inputs:dict[str,float|None];formula:str;missing_inputs:list[str]
class SprintIn(BaseModel):name:str=Field(min_length=1,max_length=200);goal:str="";start:datetime;end:datetime;capacity_points:float|None=Field(None,ge=0)
class SprintOut(SprintIn):id:str;status:str="planned";closed_at:datetime|None=None
class VelocityPoint(BaseModel):sprint_id:str;sprint_name:str;committed_points:float;completed_points:float
class VelocityReport(BaseModel):sprints:list[VelocityPoint];average_completed:float|None;inputs:dict[str,Any]
class BurndownPoint(BaseModel):day:datetime;ideal_remaining:float;actual_remaining:float;total_committed:float
class BurndownReport(BaseModel):sprint_id:str;series:list[BurndownPoint];assumptions:list[str]
class KanbanBoard(BaseModel):columns:dict[str,list[WorkItemOut]];wip_limits:dict[str,int|None]
class CeremonyIn(BaseModel):sprint_id:str;kind:str=Field(pattern="^(planning|daily|review|retro|other)$");scheduled_at:datetime;notes:str="";action_items:list[dict[str,Any]]=Field(default_factory=list)
class CeremonyOut(CeremonyIn):id:str;created_at:datetime
class RetrospectiveIn(BaseModel):sprint_id:str;went_well:list[str]=Field(default_factory=list);didnt_go_well:list[str]=Field(default_factory=list);action_items:list[dict[str,Any]]=Field(default_factory=list)
class RetrospectiveOut(RetrospectiveIn):id:str;created_at:datetime
class RoadmapIn(BaseModel):name:str=Field(min_length=1,max_length=200);horizon_start:datetime;horizon_end:datetime
class RoadmapOut(RoadmapIn):id:str;created_at:datetime
class RoadmapView(BaseModel):roadmap:RoadmapOut;lanes:dict[str,list[WorkItemOut]]
class VariantIn(BaseModel):key:str=Field(min_length=1,max_length=60);name:str="";allocation:float=Field(gt=0,le=1);factors:dict[str,str]=Field(default_factory=dict)
class VariantOut(VariantIn):trials:int=0;successes:int=0
class ExperimentIn(BaseModel):name:str=Field(min_length=1,max_length=200);hypothesis:str="";metric:str=Field(min_length=1,max_length=120);kind:str=Field("ab",pattern="^(ab|multivariate)$");variants:list[VariantIn]=Field(min_length=2)
class ExperimentOut(BaseModel):id:str;name:str;hypothesis:str;metric:str;kind:str;variants:list[VariantOut];status:str="draft";created_at:datetime;updated_at:datetime
class MeasurementIn(BaseModel):variant_key:str;trials:int=Field(ge=0);successes:int=Field(ge=0)
class SignificanceReport(BaseModel):test:str;p_value:float|None;significant:bool;alpha:float;uplift:float|None;confidence_interval:tuple[float,float]|None;inputs:dict[str,Any];assumptions:list[str]
class VariantResult(BaseModel):key:str;trials:int;successes:int;rate:float|None
# --- tenant-bound analysis jobs (feature rows 1010-1034) ---
class AnalysisJobIn(BaseModel):
    method:str=Field(min_length=1,max_length=60);data:dict[str,Any]=Field(default_factory=dict);params:dict[str,Any]=Field(default_factory=dict);seed:int=Field(0,ge=0)
class AnalysisJobOut(BaseModel):
    id:str;method:str;feature_row:int;data:dict[str,Any];params:dict[str,Any];seed:int;status:str;output:dict[str,Any]|None;error:str|None;created_at:datetime;completed_at:datetime|None
class AnalysisMethodInfo(BaseModel):
    method:str;feature_row:int;summary:str;required_inputs:list[str];limits:list[str]
