"""Evidence-bound operations planning schemas for feature rows 451-475."""
from __future__ import annotations
from datetime import datetime,timezone
from enum import IntEnum
from typing import Any,Literal
from uuid import uuid4
from pydantic import BaseModel,Field,field_validator
from .business_models import Provenance,Assumption,Uncertainty
class OperationsFeature(IntEnum):
 VENDOR_SELECTION=451;SUPPLY_CHAIN=452;INVENTORY_OPTIMIZATION=453;DEMAND_FORECAST=454;LOGISTICS_COST=455;PRODUCTION_SCHEDULING=456;QUALITY_STANDARDS=457;SIX_SIGMA=458;LEAN=459;JIT=460;TQM=461;CONTINUOUS_IMPROVEMENT=462;ROOT_CAUSE=463;FISHBONE=464;FIVE_WHYS=465;PDCA=466;DMAIC=467;VALUE_STREAM=468;PROCESS_MINING=469;WORKFLOW=470;RPA=471;REENGINEERING=472;CHANGE_MANAGEMENT=473;KOTTER=474;ADKAR=475
class OperationsAnalysisRequest(BaseModel):
 feature:OperationsFeature;inputs:dict[str,Any];provenance:list[Provenance]=Field(min_length=1);assumptions:list[Assumption]=Field(default_factory=list);confidence:float=Field(ge=0,le=1)
 @field_validator("inputs")
 @classmethod
 def nonempty(cls,v):
  if not v:raise ValueError("inputs are required; no operational facts will be invented")
  return v
class OperationsArtifact(BaseModel):
 id:str=Field(default_factory=lambda:str(uuid4()));idea_id:str;feature:OperationsFeature;method:str;inputs:dict[str,Any];provenance:list[Provenance];assumptions:list[Assumption];analysis:dict[str,Any];uncertainty:Uncertainty;evaluation:dict[str,Any];plan:dict[str,Any];execution_status:Literal["not_executed"]="not_executed";created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))
class Vendor(BaseModel): id:str;cost:float=Field(ge=0);quality:float=Field(ge=0,le=100);delivery:float=Field(ge=0,le=100);risk:float=Field(ge=0,le=100)
class DemandInput(BaseModel): history:list[float]=Field(min_length=2);horizon:int=Field(default=1,ge=1,le=52);window:int=Field(default=3,ge=1)
class InventoryInput(BaseModel): annual_demand:float=Field(gt=0);order_cost:float=Field(gt=0);annual_holding_cost_per_unit:float=Field(gt=0);lead_time_days:float=Field(ge=0);daily_demand:float=Field(ge=0);safety_stock:float=Field(default=0,ge=0)

class ProductionSchedulingInput(BaseModel):
 orders:list[str]=Field(min_length=1);resources:list[str]=Field(min_length=1);capacities:list[float]=Field(min_length=1);durations:list[float]=Field(min_length=1);due_dates:list[str]=Field(min_length=1)
class QualityControlInput(BaseModel):
 standards:list[str]=Field(min_length=1);characteristics:list[str]=Field(min_length=1);sampling_plan:str=Field(min_length=1);acceptance_criteria:str=Field(min_length=1)
class SixSigmaInput(BaseModel):
 opportunities:float=Field(gt=0);defects:float=Field(ge=0);units:float=Field(gt=0);target_sigma:float=Field(gt=0,le=6)
class LeanInput(BaseModel):
 process_steps:list[str]=Field(min_length=1);observed_waste:list[str]=Field(min_length=1);customer_value_definition:str=Field(min_length=1)
class JITInput(BaseModel):
 demand_signal:list[float]=Field(min_length=1);lead_times:list[float]=Field(min_length=1);lot_sizes:list[float]=Field(min_length=1);supplier_reliability:list[float]=Field(min_length=1);buffers:list[float]=Field(min_length=1)
class TQMInput(BaseModel):
 quality_policy:str=Field(min_length=1);customer_requirements:list[str]=Field(min_length=1);process_owners:list[str]=Field(min_length=1);measures:list[str]=Field(min_length=1)
class KaizenInput(BaseModel):
 observations:list[str]=Field(min_length=1);improvement_ideas:list[str]=Field(min_length=1);owners:list[str]=Field(min_length=1);review_cadence:str=Field(min_length=1)
class RootCauseInput(BaseModel):
 problem_statement:str=Field(min_length=1);evidence:list[str]=Field(min_length=1);candidate_causes:list[str]=Field(min_length=1);disconfirming_evidence:list[str]=Field(min_length=1)
class FishboneInput(BaseModel):
 problem:str=Field(min_length=1);people:list[str]=Field(min_length=1);process:list[str]=Field(min_length=1);equipment:list[str]=Field(min_length=1);materials:list[str]=Field(min_length=1);environment:list[str]=Field(min_length=1);measurement:list[str]=Field(min_length=1)
class FiveWhysInput(BaseModel):
 problem:str=Field(min_length=1);why_chain:list[str]=Field(min_length=2);evidence_by_step:list[str]=Field(min_length=2)
class PDCAInput(BaseModel):
 plan:str=Field(min_length=1);baseline:float;intervention:str=Field(min_length=1);check_metrics:list[str]=Field(min_length=1);act_rule:str=Field(min_length=1)
class DMAICInput(BaseModel):
 define:str=Field(min_length=1);measure:str=Field(min_length=1);analyze:str=Field(min_length=1);improve:str=Field(min_length=1);control:str=Field(min_length=1)
class ValueStreamInput(BaseModel):
 steps:list[str]=Field(min_length=1);cycle_times:list[float]=Field(min_length=1);wait_times:list[float]=Field(min_length=1);inventory:list[float]=Field(min_length=1);value_added:list[float]=Field(min_length=1)
class ProcessMiningInput(BaseModel):
 event_log_fields:list[str]=Field(min_length=1);case_id:str=Field(min_length=1);activity:str=Field(min_length=1);timestamp:str=Field(min_length=1);data_quality:str=Field(min_length=1)
class WorkflowInput(BaseModel):
 steps:list[str]=Field(min_length=1);handoffs:list[str]=Field(min_length=1);approvals:list[str]=Field(min_length=1);manual_effort:list[float]=Field(min_length=1)
class RPAInput(BaseModel):
 tasks:list[str]=Field(min_length=1);rule_stability:str=Field(min_length=1);volumes:list[float]=Field(min_length=1);exceptions:list[str]=Field(min_length=1);systems:list[str]=Field(min_length=1);security_constraints:list[str]=Field(min_length=1)
class ReengineeringInput(BaseModel):
 current_outcomes:list[str]=Field(min_length=1);target_outcomes:list[str]=Field(min_length=1);constraints:list[str]=Field(min_length=1);redesign_principles:list[str]=Field(min_length=1)
class ChangeManagementInput(BaseModel):
 stakeholders:list[str]=Field(min_length=1);impacts:list[str]=Field(min_length=1);readiness:list[str]=Field(min_length=1);communications:list[str]=Field(min_length=1);training:list[str]=Field(min_length=1);resistance_risks:list[str]=Field(min_length=1)
class KotterInput(BaseModel):
 urgency:str=Field(min_length=1);coalition:list[str]=Field(min_length=1);vision:str=Field(min_length=1);communications:list[str]=Field(min_length=1);barriers:list[str]=Field(min_length=1);short_term_wins:list[str]=Field(min_length=1);acceleration:list[str]=Field(min_length=1);anchoring:list[str]=Field(min_length=1)
class ADKARInput(BaseModel):
 awareness:float=Field(ge=0,le=5);desire:float=Field(ge=0,le=5);knowledge:float=Field(ge=0,le=5);ability:float=Field(ge=0,le=5);reinforcement:float=Field(ge=0,le=5)
