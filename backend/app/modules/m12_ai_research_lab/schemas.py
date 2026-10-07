from pydantic import BaseModel,Field,ConfigDict
from .models import TaskType
class RunIn(BaseModel):
    model_config=ConfigDict(extra="forbid")
    prompt:str=Field(min_length=1,max_length=100_000); task_type:TaskType; output_tokens:int=Field(ge=1,le=200_000,strict=True); budget_cents:float=Field(gt=0,allow_inf_nan=False,strict=True); latency_tolerance_ms:int=Field(gt=0,strict=True)
class WorkflowIn(BaseModel):
    model_config=ConfigDict(extra="forbid")
    yaml:str=Field(min_length=1,max_length=200_000)
    inputs:dict=Field(default_factory=dict)
