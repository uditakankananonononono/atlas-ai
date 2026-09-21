from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .native_capabilities import *
router=APIRouter(prefix='/native-capabilities',tags=['native-capabilities'])
_builder=SpecAppBuilder(); _research=ResearchAgent(); _live=LiveAssistant(); _pipeline=DiscoveryPipeline(); _apps={}; _workspaces={}
class DataIn(BaseModel): data:dict[str,Any]=Field(default_factory=dict)
class WorkspaceIn(BaseModel): files:dict[str,str]; manifest:dict[str,str]=Field(default_factory=dict); entrypoint:str; test_path:str|None=None
class ResearchIn(BaseModel): question:str; sources:list[dict[str,Any]]; tool_calls:list[dict[str,Any]]=Field(default_factory=list)
class ActionIn(BaseModel): event:dict[str,Any]; action:str; arguments:dict[str,Any]=Field(default_factory=dict); risk:str='low'
class DiscoveryIn(BaseModel): name:str; sources:list[dict[str,Any]]; capabilities:list[str]; license:str; permissions:list[str]=Field(default_factory=list); approved:bool=False
@router.get('')
def listing(): return native_capabilities()
@router.post('/apps/build')
def build(body:DataIn):
 try:
  out=_builder.build(body.data); _apps[out['app_id']]=out; return {k:v for k,v in out.items() if k!='workspace'}
 except CapabilityError as e: raise HTTPException(422,str(e)) from e
@router.post('/apps/{app_id}/revise')
def revise(app_id:str,body:DataIn):
 try:
  out=_builder.revise(_apps[app_id],body.data.get('changes',[])); return {k:v for k,v in out.items() if k!='workspace'}
 except KeyError as e: raise HTTPException(404,'app not found') from e
 except CapabilityError as e: raise HTTPException(422,str(e)) from e
@router.post('/workspaces/run')
def workspace(body:WorkspaceIn):
 try:
  ws=CodeWorkspace(); [ws.write(p,c) for p,c in body.files.items()]; ws.set_manifest(body.manifest); snap=ws.snapshot('uploaded'); run=ws.run(body.entrypoint); test=ws.test(body.test_path) if body.test_path else None; _workspaces[ws.id]=ws
  return {'workspace_id':ws.id,'snapshot_id':snap.id,'run':run,'test':test,'logs':ws.logs,'manifest':ws.manifest}
 except CapabilityError as e: raise HTTPException(422,str(e)) from e
@router.post('/research')
def research(body:ResearchIn):
 try:return _research.answer(body.question,body.sources,body.tool_calls)
 except CapabilityError as e:raise HTTPException(422,str(e)) from e
@router.post('/live/actions')
def live(body:ActionIn):
 try:
  event=_live.normalize(body.event); return {'event':event,'proposal':_live.propose_action(event,body.action,body.arguments,body.risk)}
 except CapabilityError as e:raise HTTPException(422,str(e)) from e
@router.post('/discovery/install')
def discover(body:DiscoveryIn):
 try:
  manifest=_pipeline.manifest(body.name,body.sources,body.capabilities,body.license,body.permissions); adapter=_pipeline.generate_adapter(manifest); test=_pipeline.sandbox_test(adapter,body.capabilities[0]); plan=_pipeline.install_plan(manifest,adapter,test,body.approved)
  return {'manifest':manifest,'adapter':adapter,'sandbox_test':test,'install':plan}
 except (CapabilityError,IndexError,ValueError) as e:raise HTTPException(422,str(e)) from e
