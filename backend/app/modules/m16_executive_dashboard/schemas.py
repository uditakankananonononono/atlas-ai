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
