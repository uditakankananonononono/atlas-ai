from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
class NodeType(str,Enum):
    PROJECT="project";RESEARCH="research";COMPETITION="competition";APPLICATION="application";EMAIL="email";CONTACT="contact";FILE="file";DEADLINE="deadline";TASK="task";NOTE="note"
class Relationship(str,Enum):
    CHILD_OF="child_of";REFERENCES="references";SUPPORTS="supports";BLOCKS="blocks";MENTIONS="mentions";RELATED_TO="related_to";DEPENDS_ON="depends_on"
class SuggestionStatus(str,Enum): PENDING="pending";ACCEPTED="accepted";REJECTED="rejected"
class NodeCreate(BaseModel):
    node_type:NodeType;title:str=Field(min_length=1,max_length=500);body:str|None=None;source_uri:str|None=None;source_module:str|None=None;external_id:str|None=None;metadata:dict[str,Any]=Field(default_factory=dict)
class Node(NodeCreate):
    id:str;version:int=1;embedding:list[float]|None=None;created_at:datetime;updated_at:datetime
class NodeUpdate(BaseModel):
    title:str|None=Field(None,min_length=1,max_length=500);body:str|None=None;metadata:dict[str,Any]|None=None;expected_version:int=Field(ge=1)
class EdgeCreate(BaseModel):
    source_id:str;target_id:str;relationship:Relationship;rationale:str|None=None;evidence:dict[str,Any]=Field(default_factory=dict)
class Edge(EdgeCreate):
    id:str;confidence:float=1;created_at:datetime
class LinkSuggestion(BaseModel):
    id:str;source_id:str;target_id:str;relationship:Relationship;score:float;reasons:list[dict[str,Any]];status:SuggestionStatus=SuggestionStatus.PENDING;created_at:datetime;reviewed_at:datetime|None=None
class Neighborhood(BaseModel): nodes:list[Node];edges:list[Edge];truncated:bool=False
class ReviewRequest(BaseModel): accept:bool
class PlannerContextRequest(BaseModel): node_ids:list[str]=Field(min_length=1,max_length=100)
