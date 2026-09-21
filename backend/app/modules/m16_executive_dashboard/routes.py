import asyncio,json
from fastapi import Header, APIRouter,Depends,HTTPException,Request
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
# --- planning & measurement (feature rows 388-399) ---
planning_router=APIRouter(prefix="/planning",tags=["executive-dashboard-planning"])
@planning_router.post("/items",response_model=WorkItemOut,status_code=201)
def create_item(data:WorkItemIn,service:Service=Depends(get_service)):return service.create_work_item(data)
@planning_router.get("/items",response_model=list[WorkItemOut])
def list_items(sprint_id:str|None=None,roadmap_id:str|None=None,status:str|None=None,service:Service=Depends(get_service)):return service.list_work_items(sprint_id,roadmap_id,status)
@planning_router.patch("/items/{item_id}",response_model=WorkItemOut)
def patch_item(item_id:str,data:WorkItemPatch,service:Service=Depends(get_service)):
    try:return service.patch_work_item(item_id,data)
    except LookupError:raise HTTPException(404,"work item not found")
    except ValueError as e:raise HTTPException(422,str(e))
@planning_router.delete("/items/{item_id}",status_code=204)
def delete_item(item_id:str,service:Service=Depends(get_service)):
    try:service.delete_work_item(item_id)
    except LookupError:raise HTTPException(404,"work item not found")
@planning_router.get("/prioritization",response_model=list[PrioritizedItem])
def prioritization(method:str="rice",service:Service=Depends(get_service)):
    try:return service.prioritization(method)
    except ValueError as e:raise HTTPException(422,str(e))
@planning_router.post("/sprints",response_model=SprintOut,status_code=201)
def create_sprint(data:SprintIn,service:Service=Depends(get_service)):
    try:return service.create_sprint(data)
    except ValueError as e:raise HTTPException(422,str(e))
@planning_router.get("/sprints",response_model=list[SprintOut])
def list_sprints(service:Service=Depends(get_service)):return service.list_sprints()
@planning_router.post("/sprints/{sprint_id}/start",response_model=SprintOut)
def start_sprint(sprint_id:str,service:Service=Depends(get_service)):
    try:return service.start_sprint(sprint_id)
    except LookupError:raise HTTPException(404,"sprint not found")
    except ValueError as e:raise HTTPException(409,str(e))
@planning_router.post("/sprints/{sprint_id}/close",response_model=SprintOut)
def close_sprint(sprint_id:str,service:Service=Depends(get_service)):
    try:return service.close_sprint(sprint_id)
    except LookupError:raise HTTPException(404,"sprint not found")
    except ValueError as e:raise HTTPException(409,str(e))
@planning_router.get("/sprints/{sprint_id}/burndown",response_model=BurndownReport)
def sprint_burndown(sprint_id:str,service:Service=Depends(get_service)):
    try:return service.burndown(sprint_id)
    except LookupError:raise HTTPException(404,"sprint not found")
@planning_router.get("/velocity",response_model=VelocityReport)
def velocity(service:Service=Depends(get_service)):return service.velocity_report()
@planning_router.get("/board",response_model=KanbanBoard)
def board(service:Service=Depends(get_service)):return service.board()
@planning_router.post("/items/{item_id}/move",response_model=WorkItemOut)
def move_item(item_id:str,column:str,service:Service=Depends(get_service)):
    from .planning import WipLimitExceeded
    try:return service.move_item(item_id,column)
    except LookupError:raise HTTPException(404,"work item not found")
    except WipLimitExceeded as e:raise HTTPException(409,str(e))
    except ValueError as e:raise HTTPException(422,str(e))
@planning_router.post("/roadmaps",response_model=RoadmapOut,status_code=201)
def create_roadmap(data:RoadmapIn,service:Service=Depends(get_service)):
    try:return service.create_roadmap(data)
    except ValueError as e:raise HTTPException(422,str(e))
@planning_router.get("/roadmaps",response_model=list[RoadmapOut])
def list_roadmaps(service:Service=Depends(get_service)):return service.list_roadmaps()
@planning_router.get("/roadmaps/{roadmap_id}/view",response_model=RoadmapView)
def roadmap_view(roadmap_id:str,service:Service=Depends(get_service)):
    try:return service.roadmap_view(roadmap_id)
    except LookupError:raise HTTPException(404,"roadmap not found")
@planning_router.post("/ceremonies",response_model=CeremonyOut,status_code=201)
def create_ceremony(data:CeremonyIn,service:Service=Depends(get_service)):
    try:return service.create_ceremony(data)
    except LookupError:raise HTTPException(404,"sprint not found")
@planning_router.get("/ceremonies",response_model=list[CeremonyOut])
def list_ceremonies(sprint_id:str|None=None,service:Service=Depends(get_service)):return service.list_ceremonies(sprint_id)
@planning_router.post("/retrospectives",response_model=RetrospectiveOut,status_code=201)
def create_retro(data:RetrospectiveIn,service:Service=Depends(get_service)):
    try:return service.create_retrospective(data)
    except LookupError:raise HTTPException(404,"sprint not found")
@planning_router.get("/retrospectives",response_model=list[RetrospectiveOut])
def list_retros(service:Service=Depends(get_service)):return service.list_retrospectives()
@planning_router.get("/retrospectives/rollup")
def retro_rollup(service:Service=Depends(get_service)):return service.retro_rollup()
@planning_router.post("/experiments",response_model=ExperimentOut,status_code=201)
def create_experiment(data:ExperimentIn,service:Service=Depends(get_service)):
    try:return service.create_experiment(data)
    except ValueError as e:raise HTTPException(422,str(e))
@planning_router.get("/experiments",response_model=list[ExperimentOut])
def list_experiments(service:Service=Depends(get_service)):return service.list_experiments()
@planning_router.get("/experiments/{experiment_id}",response_model=ExperimentOut)
def get_experiment(experiment_id:str,service:Service=Depends(get_service)):
    try:return service.get_experiment(experiment_id)
    except LookupError:raise HTTPException(404,"experiment not found")
@planning_router.post("/experiments/{experiment_id}/measurements",response_model=ExperimentOut)
def record_measurement(experiment_id:str,data:MeasurementIn,service:Service=Depends(get_service)):
    try:return service.record_measurement(experiment_id,data)
    except LookupError as e:raise HTTPException(404,str(e))
    except ValueError as e:raise HTTPException(409,str(e))
@planning_router.post("/experiments/{experiment_id}/status",response_model=ExperimentOut)
def set_experiment_status(experiment_id:str,status:str,service:Service=Depends(get_service)):
    try:return service.set_experiment_status(experiment_id,status)
    except LookupError:raise HTTPException(404,"experiment not found")
    except ValueError as e:raise HTTPException(409,str(e))
@planning_router.get("/experiments/{experiment_id}/significance",response_model=SignificanceReport)
def experiment_significance(experiment_id:str,alpha:float=0.05,service:Service=Depends(get_service)):
    try:return service.experiment_significance(experiment_id,alpha)
    except LookupError:raise HTTPException(404,"experiment not found")
router.include_router(planning_router)
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
# --- tenant-bound analysis jobs (feature rows 1010-1034) ---
@router.get("/analysis/methods",response_model=list[AnalysisMethodInfo])
def analysis_methods(service:Service=Depends(get_service)):return service.analysis_methods()
@router.post("/analysis/jobs",response_model=AnalysisJobOut,status_code=201)
def run_analysis(data:AnalysisJobIn,service:Service=Depends(get_service)):
    try:return service.run_analysis(data)
    except ValueError as e:raise HTTPException(422,str(e))
@router.get("/analysis/jobs",response_model=list[AnalysisJobOut])
def list_analysis_jobs(method:str|None=None,service:Service=Depends(get_service)):return service.list_analysis_jobs(method)
@router.get("/analysis/jobs/{job_id}",response_model=AnalysisJobOut)
def get_analysis_job(job_id:str,service:Service=Depends(get_service)):
    try:return service.get_analysis_job(job_id)
    except LookupError:raise HTTPException(404,"analysis job not found")

# Specialized finance analytics (owner feature rows 1360-1409).
@router.get("/finance/methods",response_model=list[FinanceMethodInfo])
def finance_methods():
    from .finance import ROWS
    return [FinanceMethodInfo(method=m,feature_row=row) for m,row in ROWS.items()]

@router.post("/finance/analyze")
def finance_analyze(data:FinanceAnalysisIn,x_tenant_id:str=Header(min_length=1,alias="X-Tenant-ID"),x_actor_id:str=Header(min_length=1,alias="X-Actor-ID")):
    from .finance import run
    try:
        result=run(data.method,data.data,data.seed)
        result["scope"]={"tenant_id":x_tenant_id,"actor_id":x_actor_id}
        return result
    except ValueError as e:raise HTTPException(422,str(e))

# Direct, mounted semantic surface for emerging capability rows 910-959.
class EmergingAnalysisIn(BaseModel):
    method:str=Field(min_length=1)
    data:dict=Field(default_factory=dict)
    params:dict=Field(default_factory=dict)
    seed:int=0
@router.get('/emerging-910-959/methods')
def emerging_methods_910_959():
    from .emerging_capabilities_0910_0959 import ROWS,SUMMARIES,INPUTS
    return [{'method':m,'feature_row':r,'summary':SUMMARIES[m],'required_evidence':INPUTS[m]} for m,r in ROWS.items()]
@router.post('/emerging-910-959/analyze')
def emerging_analyze_910_959(body:EmergingAnalysisIn):
    from .emerging_capabilities_0910_0959 import ROWS,run
    if body.method not in ROWS:raise HTTPException(422,'unsupported emerging method')
    try:return run(body.method,body.data,body.params,body.seed)
    except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc:raise HTTPException(422,str(exc)) from exc

# Direct semantic evidence surface for owner-feature rows 1910-1959.
from .semantic_ai_routes_1910_1959 import router as semantic_ai_router_1910_1959
router.include_router(semantic_ai_router_1910_1959)
