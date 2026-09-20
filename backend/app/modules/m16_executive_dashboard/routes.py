import asyncio,json
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import StreamingResponse
from app.auth.context import TenantContext,require_tenant
from .repository import SqlDashboardRepository
from .schemas import *
from .service import Service
router=APIRouter(prefix="/executive-dashboard",tags=["executive-dashboard"])
def get_service(t:TenantContext=Depends(require_tenant)):return Service(SqlDashboardRepository(t.tenant_id,t.actor_id))
@router.get("/snapshot",response_model=Snapshot)
def snapshot(service:Service=Depends(get_service)):return service.snapshot()
@router.get("/events",response_model=list[Event])
def events(cursor:int=0,service:Service=Depends(get_service)):return service.events_after(cursor)
@router.get("/approvals",response_model=list[Approval])
def approvals(service:Service=Depends(get_service)):return service.pending_approvals()
@router.post("/approvals/{approval_id}/decision",response_model=Approval)
def decide(approval_id:str,data:ApprovalDecision,service:Service=Depends(get_service)):
    try:return service.decide(approval_id,data)
    except LookupError:raise HTTPException(409,"approval is not pending")
    except RuntimeError as e:raise HTTPException(410,str(e))
@router.post("/commands/preview",response_model=CommandPreview)
def preview(data:CommandRequest,service:Service=Depends(get_service)):return service.preview(data.utterance)
@router.post("/commands/{preview_id}/execute")
def execute(preview_id:str,service:Service=Depends(get_service)):
    try:return service.execute(preview_id)
    except LookupError:raise HTTPException(404,"preview not found")
    except RuntimeError as e:raise HTTPException(409,str(e))
@router.get("/overview",response_model=DashboardOverview)
def overview(service:Service=Depends(get_service)):return service.overview()
@router.get("/modules",response_model=list[ModuleStatus])
def modules(service:Service=Depends(get_service)):return service.module_statuses()
@router.get("/kpis",response_model=list[KPI])
def kpis(service:Service=Depends(get_service)):return service.kpis()
@router.get("/kpis/{kpi_id}/evidence",response_model=DrilldownResult)
def kpi_evidence(kpi_id:str,service:Service=Depends(get_service)):
    try:return service.kpi_evidence(kpi_id)
    except LookupError:raise HTTPException(404,"unknown kpi")
@router.get("/blockers",response_model=list[Blocker])
def blockers(service:Service=Depends(get_service)):return service.blockers()
@router.get("/drilldown/{kind}/{ref_id}",response_model=DrilldownResult)
def drilldown(kind:str,ref_id:str,service:Service=Depends(get_service)):
    if kind not in ("event","approval","module","timeline_item"):raise HTTPException(404,"unknown drilldown kind")
    try:return service.drilldown(kind,ref_id)
    except LookupError:raise HTTPException(404,"not found")
@router.post("/agents/heartbeat",response_model=AgentStatus)
def heartbeat(data:AgentHeartbeat,service:Service=Depends(get_service)):
    try:return service.heartbeat(data)
    except RuntimeError as e:raise HTTPException(501,str(e))
@router.post("/events",response_model=Event,status_code=201)
def intake(data:EventIn,service:Service=Depends(get_service)):return service.intake(data)
@router.post("/events/batch",response_model=list[Event],status_code=201)
def intake_batch(items:list[EventIn],service:Service=Depends(get_service)):
    if len(items)>500:raise HTTPException(413,"batch too large (max 500)")
    return service.intake_batch(items)
@router.get("/kpi-definitions",response_model=list[KpiDefinitionOut])
def list_kpi_definitions(service:Service=Depends(get_service)):return service.list_kpi_definitions()
@router.put("/kpi-definitions",response_model=KpiDefinitionOut)
def save_kpi_definition(data:KpiDefinitionIn,service:Service=Depends(get_service)):
    try:return service.save_kpi_definition(data)
    except ValueError as e:raise HTTPException(409,str(e))
    except RuntimeError as e:raise HTTPException(501,str(e))
@router.delete("/kpi-definitions/{kpi_id}",status_code=204)
def delete_kpi_definition(kpi_id:str,service:Service=Depends(get_service)):
    try:service.delete_kpi_definition(kpi_id)
    except LookupError:raise HTTPException(404,"unknown kpi definition")
@router.get("/view",response_model=DashboardView)
def get_view(service:Service=Depends(get_service)):return service.get_view()
@router.put("/view",response_model=DashboardView)
def save_view(data:DashboardViewIn,service:Service=Depends(get_service)):
    try:return service.save_view(data)
    except ValueError as e:raise HTTPException(422,str(e))
    except RuntimeError as e:raise HTTPException(501,str(e))
@router.post("/approvals/sweep",response_model=list[Approval])
def sweep(service:Service=Depends(get_service)):
    try:return service.sweep_expired()
    except RuntimeError as e:raise HTTPException(501,str(e))
@router.get("/export/events.csv")
def export_events(since_hours:int=24,topic:str|None=None,after_sequence:int=0,service:Service=Depends(get_service)):
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(service.export_events_csv(since_hours,topic,after_sequence),media_type="text/csv")
@router.get("/export/kpis.csv")
def export_kpis(service:Service=Depends(get_service)):
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(service.export_kpis_csv(),media_type="text/csv")
@router.get("/alert-rules",response_model=list[AlertRuleOut])
def list_alert_rules(service:Service=Depends(get_service)):return service.list_alert_rules()
@router.put("/alert-rules",response_model=AlertRuleOut)
def save_alert_rule(data:AlertRuleIn,service:Service=Depends(get_service)):
    try:return service.save_alert_rule(data)
    except RuntimeError as e:raise HTTPException(501,str(e))
@router.delete("/alert-rules/{rule_id}",status_code=204)
def delete_alert_rule(rule_id:str,service:Service=Depends(get_service)):
    try:service.delete_alert_rule(rule_id)
    except LookupError:raise HTTPException(404,"unknown alert rule")
@router.post("/approvals/bulk-decision",response_model=BulkDecisionResult)
def bulk_decide(data:BulkApprovalDecision,service:Service=Depends(get_service)):return service.decide_many(data)
@router.get("/digest",response_model=Digest)
def digest(service:Service=Depends(get_service)):return service.digest()
@router.post("/project")
def project(service:Service=Depends(get_service)):return service.project()
@router.get("/live")
async def live(request:Request,cursor:int=0,service:Service=Depends(get_service)):
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            events=service.events_after(cursor)
            for event in events:cursor=event.sequence;yield f"id: {event.sequence}\nevent: {event.topic}\ndata: {event.model_dump_json()}\n\n"
            if not events:yield ": heartbeat\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
