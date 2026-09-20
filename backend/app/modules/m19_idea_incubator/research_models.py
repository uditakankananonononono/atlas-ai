"""Evidence-bound research-method artifacts for rows 110-134."""
from __future__ import annotations
from datetime import datetime,timezone
from enum import IntEnum
from typing import Any,Literal
from uuid import uuid4
from pydantic import BaseModel,Field,field_validator,model_validator
from .business_models import Provenance,Assumption,Uncertainty
class ResearchFeature(IntEnum):
 LITERATURE_SYNTHESIS=110;CITATION_NETWORK=111;RESEARCH_GAPS=112;HYPOTHESIS=113;EXPERIMENTAL_DESIGN=114;POWER=115;CONFOUNDS=116;RANDOMIZATION=117;BLINDING=118;REPLICATION=119;META_ANALYSIS=120;EFFECT_SIZE=121;PUBLICATION_BIAS=122;P_HACKING=123;PREREGISTRATION=124;OPEN_SCIENCE=125;REPRODUCIBILITY=126;PEER_REVIEW=127;JOURNAL_MATCH=128;CITATION_ESTIMATE=129;ABSTRACT=130;TITLE=131;FIGURES=132;TEST_SELECTION=133;BAYESIAN_ANALYSIS=134
class ResearchAnalysisRequest(BaseModel):
 feature:ResearchFeature;inputs:dict[str,Any];provenance:list[Provenance]=Field(min_length=1);assumptions:list[Assumption]=Field(default_factory=list);confidence:float=Field(ge=0,le=1)
 @field_validator("inputs")
 @classmethod
 def nonempty(cls,v):
  if not v:raise ValueError("inputs are required; studies and results will not be invented")
  return v
class ResearchArtifact(BaseModel):
 id:str=Field(default_factory=lambda:str(uuid4()));idea_id:str;feature:ResearchFeature;method:str;inputs:dict[str,Any];provenance:list[Provenance];assumptions:list[Assumption];analysis:dict[str,Any];uncertainty:Uncertainty;claims:dict[str,Any];created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))
class PowerInput(BaseModel): effect_size:float=Field(gt=0);alpha:float=Field(default=.05,gt=0,lt=1);power:float=Field(default=.8,gt=.5,lt=1);groups:int=Field(default=2,ge=1,le=20)
class MetaStudy(BaseModel): id:str;effect:float;standard_error:float=Field(gt=0)
class EffectSizeInput(BaseModel): treatment_mean:float;control_mean:float;treatment_sd:float=Field(gt=0);control_sd:float=Field(gt=0);treatment_n:int=Field(gt=1);control_n:int=Field(gt=1)
class BayesianInput(BaseModel):
 successes:int=Field(ge=0);trials:int=Field(gt=0);prior_alpha:float=Field(default=1,gt=0);prior_beta:float=Field(default=1,gt=0)
 @model_validator(mode="after")
 def bounded(self):
  if self.successes>self.trials:raise ValueError("successes cannot exceed trials")
  return self
