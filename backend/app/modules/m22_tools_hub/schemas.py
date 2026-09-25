from typing import Any
from pydantic import BaseModel,Field
class DiscoveryIn(BaseModel):
 query:str=Field(min_length=2,max_length=500)
 kinds:list[str]|None=None
 weights:dict[str,float]|None=None
class BatchDiscoveryIn(BaseModel):
 queries:list[str]=Field(min_length=1,max_length=20)
 kinds:list[str]|None=None
 weights:dict[str,float]|None=None
class FeedDiscoverIn(BaseModel):url:str=Field(min_length=10,max_length=2000)
class FeedPollIn(BaseModel):url:str=Field(min_length=10,max_length=2000);max_items:int=Field(default=20,ge=1,le=100)
class OpmlParseIn(BaseModel):opml:str=Field(min_length=20,max_length=2_000_000)
class OpmlBuildIn(BaseModel):feeds:list[dict[str,str]]=Field(min_length=1,max_length=500)
class BlockValueIn(BaseModel):value:str=Field(min_length=1,max_length=300)
class InstallIn(BaseModel):candidate_id:str;adapter_type:str;config:dict[str,Any]={};requested_scopes:list[str]=[]
