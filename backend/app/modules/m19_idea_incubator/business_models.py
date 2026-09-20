"""Typed business-analysis inputs and evidence-bearing artifacts for rows 360-399."""
from __future__ import annotations
from datetime import datetime,timezone
from enum import IntEnum
from typing import Any,Literal
from uuid import uuid4
from pydantic import BaseModel,Field,field_validator,model_validator

class BusinessFeature(IntEnum):
 MARKET_SIZING=360;COMPETITOR_MAP=361;INDUSTRY_ATTRACTIVENESS=362;VALUE_PROPOSITION=363;BUSINESS_MODEL_CANVAS=364;RAPID_VALIDATION=365;TARGET_MARKET=366;PERSONA=367;CUSTOMER_JOURNEY=368;UNMET_NEEDS=369;DESIRED_OUTCOMES=370;CUSTOMER_MOTIVATION=371;HYPOTHESIS_TEST=372;MVP=373;FEEDBACK_SYSTEM=374;MARKET_VALIDATION=375;PIVOT_DECISION=376;GROWTH_TACTICS=377;VIRAL_METRICS=378;CAC=379;LTV=380;UNIT_ECONOMICS=381;COHORTS=382;RETENTION=383;CHURN_RISK=384;NPS=385;SATISFACTION=386;VOC=387;PRIORITIZATION=388;ROADMAP=389;AGILE_WORKFLOW=390;BACKLOG=391;VELOCITY=392;PROGRESS=393;WORKFLOW_MANAGEMENT=394;AGILE_MEETINGS=395;RETROSPECTIVE=396;CONTROLLED_EXPERIMENT=397;MULTIVARIATE_TEST=398;STATISTICAL_SIGNIFICANCE=399

class Provenance(BaseModel):
 source_id:str=Field(min_length=1,max_length=500);source_type:Literal["user_input","interview","survey","analytics","financial_record","experiment","public_source","other"];uri:str|None=None;observed_at:datetime;notes:str|None=None
class Assumption(BaseModel): name:str=Field(min_length=1);value:Any;rationale:str=Field(min_length=1);sensitivity:Literal["low","medium","high"]="medium"
class Uncertainty(BaseModel): confidence:float=Field(ge=0,le=1);limitations:list[str]=Field(default_factory=list);sample_size:int|None=Field(default=None,ge=0);interval_low:float|None=None;interval_high:float|None=None
class BusinessAnalysisRequest(BaseModel):
 feature:BusinessFeature;inputs:dict[str,Any]=Field(default_factory=dict);assumptions:list[Assumption]=Field(default_factory=list);provenance:list[Provenance]=Field(min_length=1);confidence:float=Field(ge=0,le=1);notes:str|None=Field(default=None,max_length=5000)
 @field_validator("inputs")
 @classmethod
 def inputs_not_empty(cls,v):
  if not v:raise ValueError("inputs are required; Atlas will not invent market evidence")
  return v
class BusinessArtifact(BaseModel):
 id:str=Field(default_factory=lambda:str(uuid4()));idea_id:str;feature:BusinessFeature;method:str;inputs:dict[str,Any];assumptions:list[Assumption];provenance:list[Provenance];result:dict[str,Any];uncertainty:Uncertainty;decision:dict[str,Any];created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))

class MarketSizingInput(BaseModel): total_entities:float=Field(gt=0);annual_revenue_per_entity:float=Field(ge=0);serviceable_fraction:float=Field(gt=0,le=1);obtainable_fraction:float=Field(gt=0,le=1)
class ViralInput(BaseModel): invitations_per_user:float=Field(ge=0);invite_conversion_rate:float=Field(ge=0,le=1);cycle_days:float=Field(gt=0)
class CACInput(BaseModel): acquisition_spend:float=Field(ge=0);new_customers:int=Field(gt=0)
class LTVInput(BaseModel): average_revenue_per_period:float=Field(ge=0);gross_margin_rate:float=Field(ge=0,le=1);periodic_churn_rate:float=Field(gt=0,le=1)
class UnitEconomicsInput(BaseModel): revenue_per_unit:float;variable_cost_per_unit:float;fixed_costs:float=Field(ge=0);units:int=Field(gt=0);cac:float=Field(default=0,ge=0)
class NPSInput(BaseModel):
 scores:list[int]=Field(min_length=1)
 @field_validator("scores")
 @classmethod
 def valid_scores(cls,v):
  if any(x<0 or x>10 for x in v):raise ValueError("NPS scores must be 0 through 10")
  return v
class RateInput(BaseModel):
 starting:int=Field(gt=0);remaining:int=Field(ge=0)
 @model_validator(mode="after")
 def bounded(self):
  if self.remaining>self.starting:raise ValueError("remaining cannot exceed starting")
  return self
class VelocityInput(BaseModel): completed_points:list[float]=Field(min_length=1);planned_points:list[float]|None=None
class SignificanceInput(BaseModel):
 control_conversions:int=Field(ge=0);control_total:int=Field(gt=0);variant_conversions:int=Field(ge=0);variant_total:int=Field(gt=0);alpha:float=Field(default=.05,gt=0,lt=1);minimum_effect:float=Field(default=0,ge=0)
 @model_validator(mode="after")
 def totals(self):
  if self.control_conversions>self.control_total or self.variant_conversions>self.variant_total:raise ValueError("conversions cannot exceed totals")
  return self
class PriorityItem(BaseModel): id:str;reach:float=Field(ge=0);impact:float=Field(ge=0);confidence:float=Field(ge=0,le=1);effort:float=Field(gt=0)
class CohortInput(BaseModel): cohorts:dict[str,list[int]]
