"""Integrated workflows composed from real module services by dependency injection."""
from __future__ import annotations
from .integration import AtlasRuntime,Handoff,RuntimeContext

class OpportunityToApplicationWorkflow:
    """M1 opportunity -> M2 rules/checklist -> M13 staged form -> M0 approval."""
    def __init__(self,runtime:AtlasRuntime):self.runtime=runtime
    async def prepare(self,context:RuntimeContext,opportunity:dict,profile_sources:list[dict]):
        evidence=[{"type":"opportunity","id":opportunity.get("id"),"url":opportunity.get("url")},*profile_sources]
        rules=await self.runtime.dispatch(context,Handoff(source_module=1,target_module=2,operation="analyze_opportunity",payload={"opportunity":opportunity},evidence=evidence))
        draft=await self.runtime.dispatch(context,Handoff(source_module=2,target_module=2,operation="draft_application",payload={"competition":rules,"profile_sources":profile_sources},evidence=evidence))
        staged=await self.runtime.dispatch(context,Handoff(source_module=2,target_module=13,operation="stage_form",payload={"draft":draft,"target_url":opportunity.get("url")},evidence=evidence,requires_approval=True))
        approval=await self.runtime.dispatch(context,Handoff(source_module=13,target_module=0,operation="request_approval",payload=staged,evidence=evidence,requires_approval=True))
        return {"opportunity":opportunity.get("id"),"rules":rules,"draft":draft,"staged":staged,"approval":approval,"correlation_id":context.correlation_id}

class ResearchToDocumentWorkflow:
    """M4 research evidence -> M3 draft -> M15 artifact -> M0 sharing approval."""
    def __init__(self,runtime:AtlasRuntime):self.runtime=runtime
    async def prepare(self,context:RuntimeContext,question:str,papers:list[dict]):
        evidence=[{"type":"paper","paper_id":p.get("paper_id"),"url":p.get("url")} for p in papers]
        analysis=await self.runtime.dispatch(context,Handoff(source_module=4,target_module=4,operation="research",payload={"question":question,"papers":papers},evidence=evidence))
        draft=await self.runtime.dispatch(context,Handoff(source_module=4,target_module=3,operation="draft_grounded",payload={"analysis":analysis},evidence=evidence))
        artifact=await self.runtime.dispatch(context,Handoff(source_module=3,target_module=15,operation="render_document",payload={"draft":draft},evidence=evidence))
        approval=await self.runtime.dispatch(context,Handoff(source_module=15,target_module=0,operation="request_approval",payload={"action":"share_document","artifact":artifact},evidence=evidence,requires_approval=True))
        return {"analysis":analysis,"draft":draft,"artifact":artifact,"approval":approval,"correlation_id":context.correlation_id}
