from fastapi import APIRouter,Depends,HTTPException
from typing import Any
from pydantic import BaseModel
from app.core.approvals import approvals
from .schemas import BatchDiscoveryIn,BlockValueIn,DiscoveryIn,FeedDiscoverIn,FeedPollIn,InstallIn,OpmlBuildIn,OpmlParseIn
from .service import Service
from .collectors import default_collectors
import threading
from app.auth.context import TenantContext,require_tenant
router=APIRouter(prefix="/tools-hub",tags=["tools-hub"])
# Per-tenant discovery Service (candidate cache, query snapshots/history/diffs, cooldowns, source stats, blocklist are
# tenant state and must not be shared). The collectors are shared on purpose: they only hold PUBLIC registry data
# (e.g. the PyPI name index cache) and one 100MB-class index per tenant would be wasteful. In-memory, per process,
# lost on restart; hard cap on tenants, fail closed (no eviction = no silent deletion of another tenant's state).
MAX_TENANT_SERVICES=64
_services:dict[str,Service]={};_shared_collectors:list|None=None;_services_lock=threading.Lock()
def service_for_tenant(tenant_id:str)->Service:
 global _shared_collectors
 with _services_lock:
  svc=_services.get(tenant_id)
  if svc is None:
   if len(_services)>=MAX_TENANT_SERVICES:raise HTTPException(503,"tools-hub in-memory tenant capacity reached; restart or configure persistent per-tenant services")
   if _shared_collectors is None:_shared_collectors=default_collectors()
   svc=_services[tenant_id]=Service(approvals,list(_shared_collectors))
  return svc
def get_service(tenant:TenantContext=Depends(require_tenant)):
 return service_for_tenant(tenant.tenant_id)
@router.post("/discoveries")
async def discover(req:DiscoveryIn,s:Service=Depends(get_service)):
 try:return await s.discover(req.query,kinds=req.kinds,weights=req.weights)
 except ValueError as e:raise HTTPException(422,str(e))

@router.post("/discoveries/batch")
async def discover_batch(req:BatchDiscoveryIn,s:Service=Depends(get_service)):
 try:
  result=await s.discover_many(req.queries,kinds=req.kinds,weights=req.weights)
 except ValueError as e:raise HTTPException(422,str(e))
 from dataclasses import asdict
 return {"per_query":{q:[asdict(x)|{"score":x.score,"score_complete":x.score_complete,"score_state":x.score_state} for x in items] for q,items in result["per_query"].items()},"merged":[asdict(x)|{"score":x.score,"score_complete":x.score_complete,"score_state":x.score_state} for x in result["merged"]]}

@router.get("/discoveries/{query}/report")
def discovery_report(query:str,s:Service=Depends(get_service)):return s.discovery_report(query)

@router.get("/queries")
def query_history(s:Service=Depends(get_service)):return {"queries":s.query_history}

@router.get("/candidates/export")
def export_candidates(format:str="json",s:Service=Depends(get_service)):
 try:body=s.export_candidates(format)
 except ValueError as e:raise HTTPException(422,str(e))
 media={"json":"application/json","csv":"text/csv","markdown":"text/markdown","md":"text/markdown"}[format]
 from fastapi import Response
 return Response(content=body,media_type=media)

@router.get("/candidates/{candidate_id}/explain")
def explain_candidate(candidate_id:str,s:Service=Depends(get_service)):
 c=s.candidates.get(candidate_id)
 if not c:raise HTTPException(404,"candidate not found")
 return c.explain()

@router.post("/candidates/{candidate_id}/refresh")
def refresh_candidate(candidate_id:str,s:Service=Depends(get_service)):
 from .sources import SourceError,refresh_repository_candidate
 c=s.candidates.get(candidate_id)
 if not c:raise HTTPException(404,"candidate not found")
 if c.kind!="repository":raise HTTPException(422,"evidence refresh is only supported for repository candidates")
 try:update=refresh_repository_candidate(c.name,c.source)
 except SourceError as e:raise HTTPException(422,str(e))
 c.maintenance=update["maintenance"];c.evidence=[update["evidence"],*[e for e in c.evidence if e.get("source")!=c.source]]
 return {"id":c.id,"name":c.name,"source":c.source,"maintenance":c.maintenance,"evidence":c.evidence,"refreshed":True}

@router.get("/blocks")
def list_blocks(s:Service=Depends(get_service)):return s.blocks()

@router.post("/blocks/{kind}/add")
def add_block(kind:str,body:BlockValueIn,s:Service=Depends(get_service)):
 try:return s.add_block(kind,body.value)
 except ValueError as e:raise HTTPException(422,str(e))

@router.post("/blocks/{kind}/remove")
def remove_block(kind:str,body:BlockValueIn,s:Service=Depends(get_service)):
 try:return s.remove_block(kind,body.value)
 except ValueError as e:raise HTTPException(422,str(e))

@router.post("/feeds/discover")
def discover_feeds_endpoint(req:FeedDiscoverIn):
 from .sources import SourceError,discover_feeds
 try:return {"site":req.url,"feeds":discover_feeds(req.url)}
 except SourceError as e:raise HTTPException(422,str(e))

@router.post("/feeds/opml/parse")
def opml_parse(req:OpmlParseIn):
 from .sources import SourceError,parse_opml
 try:return {"feeds":parse_opml(req.opml)}
 except SourceError as e:raise HTTPException(422,str(e))

@router.post("/feeds/opml/build")
def opml_build(req:OpmlBuildIn):
 from .sources import feeds_to_opml
 for feed in req.feeds:
  if "feed_url" not in feed:raise HTTPException(422,"each feed needs a feed_url")
 from fastapi import Response
 return Response(content=feeds_to_opml(req.feeds),media_type="text/x-opml")

_watcher=None
def get_watcher():
 global _watcher
 if _watcher is None:
  import os
  from .sources import FeedWatcher
  root=os.environ.get("ATLAS_TOOLS_ROOT","/tmp/atlas-tools")
  _watcher=FeedWatcher(os.path.join(root,"m22_feed_watches.json"))
 return _watcher

@router.post("/feeds/poll")
async def poll_feed(req:FeedPollIn):
 from .sources import SourceError
 try:return {"feed":req.url,"new_entries":await get_watcher().poll(req.url,max_items=req.max_items)}
 except SourceError as e:raise HTTPException(422,str(e))
@router.post("/installation-proposals",status_code=201)
def propose(req:InstallIn,s:Service=Depends(get_service)):
 try:return s.propose_install(req.candidate_id,req.adapter_type,req.config,req.requested_scopes)
 except KeyError as e:raise HTTPException(404,str(e))
 except ValueError as e:raise HTTPException(422,str(e))
@router.get("/portfolio")
def portfolio(s:Service=Depends(get_service)):return s.portfolio()

@router.get("/sources")
def sources(s:Service=Depends(get_service)):
 return {"sources":s.sources()}

@router.post('/expanded-259-278/{row_id}')
def expanded_259_278(row_id:int,payload:dict):
 from .expanded_259_278 import run
 try:return run(row_id,payload)
 except (ValueError,TypeError,KeyError) as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc

from .native_capability_routes import router as native_capability_router
router.include_router(native_capability_router)

class IntegrationReceiptIn(BaseModel):evidence:dict[str,Any]
@router.post('/installation-proposals/{proposal_id}/receipts',status_code=201)
def integration_receipt(proposal_id:str,body:IntegrationReceiptIn,s:Service=Depends(get_service)):
 try:return s.mark_integrated(proposal_id,body.evidence)
 except KeyError:raise HTTPException(404,'installation proposal not found')
 except ValueError as error:raise HTTPException(422,str(error)) from error

from .pipeline_routes import router as pipeline_router
router.include_router(pipeline_router)
