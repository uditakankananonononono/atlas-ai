"""Mount this router at /api/v1. Durable store path must be configured explicitly."""
import os
from functools import lru_cache
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth.context import require_tenant, TenantContext
from .venture_v2.engines import UNITS, run
from .venture_v2.policy import Refusal
from .venture_v2.store import ReportStore

router=APIRouter(tags=['venture-v2'])

@lru_cache(maxsize=8)
def _open_store(path): return ReportStore(path)

def get_store():
    path=os.environ.get('ATLAS_VENTURE_REPORT_DB')
    if not path or path==':memory:': raise HTTPException(503,'ATLAS_VENTURE_REPORT_DB durable path required')
    try: return _open_store(path)
    except Exception as exc: raise HTTPException(503,'venture report store unavailable') from exc


def register(name,module):
    def execute(body: dict[str,Any],tenant:TenantContext=Depends(require_tenant),store:ReportStore=Depends(get_store)):
        try: return store.save(tenant.tenant_id,name,run(name,body))
        except Refusal as exc: raise HTTPException(422,{'code':exc.code,'message':str(exc)}) from exc
    def report(run_id:str|None=Query(None),tenant:TenantContext=Depends(require_tenant),store:ReportStore=Depends(get_store)):
        try: return store.get(tenant.tenant_id,name,run_id)
        except KeyError as exc: raise HTTPException(404,'report not found') from exc
    execute.__name__='venture_'+name.replace('-','_')+'_run'
    report.__name__='venture_'+name.replace('-','_')+'_report'
    router.add_api_route(f'/{module}/{name}/run',execute,methods=['POST'])
    router.add_api_route(f'/{module}/{name}/report',report,methods=['GET'])

for name,(_,module,_) in UNITS.items(): register(name,module)
