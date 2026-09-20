from pydantic import BaseModel,Field
from .models import TaskType
class RunIn(BaseModel):
    prompt:str=Field(min_length=1,max_length=100_000); task_type:TaskType; output_tokens:int=Field(ge=1,le=200_000); budget_cents:float=Field(gt=0); latency_tolerance_ms:int=Field(gt=0)
class WorkflowIn(BaseModel): yaml:str=Field(min_length=1,max_length=200_000); inputs:dict=Field(default_factory=dict)
