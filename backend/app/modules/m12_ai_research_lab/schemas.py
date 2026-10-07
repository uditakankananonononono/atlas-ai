from pydantic import BaseModel,Field,ConfigDict,field_validator
from .models import TaskType
class RunIn(BaseModel):
    model_config=ConfigDict(extra="forbid")
    prompt:str=Field(min_length=1,max_length=100_000); task_type:TaskType; output_tokens:int=Field(ge=1,le=200_000,strict=True); budget_cents:float=Field(gt=0,allow_inf_nan=False,strict=True); latency_tolerance_ms:int=Field(gt=0,strict=True)
    @field_validator('prompt')
    @classmethod
    def nonblank_prompt(cls,value):
        if not value.strip():raise ValueError('prompt must be nonblank text')
        return value
class WorkflowIn(BaseModel):
    model_config=ConfigDict(extra="forbid")
    yaml:str=Field(min_length=1,max_length=200_000)
    inputs:dict=Field(default_factory=dict)
