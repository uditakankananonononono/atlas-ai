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
