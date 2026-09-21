import asyncio
from app.runtime.integration import Handoff,RuntimeContext
from app.runtime.production import build_runtime
def test_runtime_registers_real_production_adapters_and_dispatches_goal():
 r=build_runtime();top={(x['module_id'],x['operation']) for x in r.topology()}
 assert (0,'request_approval') in top and (4,'research') in top and all((i,'prepare_goal_work') in top for i in range(26))
 out=asyncio.run(r.dispatch(RuntimeContext('tenant','actor','corr'),Handoff(source_module=20,target_module=14,operation='prepare_goal_work',payload={'goal':'build app'})))
 assert out['state']=='prepared' and out['tenant_id']=='tenant' and out['external_effects'] is False
