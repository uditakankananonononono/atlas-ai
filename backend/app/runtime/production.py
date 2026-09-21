"""Production runtime registry: explicit service adapters, no magic module calls."""
from __future__ import annotations
from typing import Any
from app.runtime.integration import AtlasRuntime, Handoff, RuntimeContext

async def _approval(context:RuntimeContext,handoff:Handoff)->dict[str,Any]:
 from app.modules.m00_approval_center.service import default_service
 action=str(handoff.payload.get('action') or handoff.operation)
 view=default_service().submit(module_id=handoff.source_module,action_type=action,payload=handoff.payload,user_id=context.tenant_id)
 return {'approval_id':view['id'],'status':view['status'],'requires_human_review':True}

async def _research(context:RuntimeContext,handoff:Handoff)->dict[str,Any]:
 from app.modules.m04_research_scientist.service import Service
 # The production adapter exposes the typed payload and evidence boundary; the
 # module service remains the owner of actual research execution.
 return {'question':handoff.payload.get('question'),'papers':handoff.payload.get('papers',[]),'evidence':handoff.evidence,'tenant_id':context.tenant_id,'requires_research_service':True}

async def _prepare_goal(context:RuntimeContext,handoff:Handoff)->dict[str,Any]:
 return {'module_id':handoff.target_module,'goal':handoff.payload['goal'],'tenant_id':context.tenant_id,'actor_id':context.actor_id,'state':'prepared','external_effects':False}

def build_runtime()->AtlasRuntime:
 runtime=AtlasRuntime()
 runtime.register(0,'request_approval',_approval)
 runtime.register(4,'research',_research)
 for module_id in range(26): runtime.register(module_id,'prepare_goal_work',_prepare_goal)
 return runtime

runtime=build_runtime()
