from fastapi import APIRouter,Depends,HTTPException,Query,status
from app.auth.context import TenantContext,require_tenant
from app.core.approvals import approvals
from app.core.providers import generate
from app.core.models import ApprovalRequest
from .schemas import *
from .repository import SqlIdeaRepository
from .ledger import ConflictError,LedgerService,ValidationError
from .service import Service
router=APIRouter(prefix="/idea-incubator",tags=["idea-incubator"]);_service=None
def get_service()->Service:
 global _service
 if _service is None:_service=Service(generate=generate,approval_store=approvals)
 return _service
def get_ledger(t:TenantContext=Depends(require_tenant)):return LedgerService(SqlIdeaRepository(t.tenant_id),t.actor_id)
@router.post("/ideas",response_model=RunOut,status_code=201)
async def intake(request:IntakeIn,service:Service=Depends(get_service)):return await service.intake(request)
@router.get("/ideas/{run_id}",response_model=RunOut)
def get(run_id:str,service:Service=Depends(get_service)):
 try:return service.get(run_id)
 except KeyError as e:raise HTTPException(404,"idea not found") from e
@router.post("/ideas/{run_id}/preview",response_model=ApprovalRequest,status_code=201)
def preview(run_id:str,request:PreviewIn,service:Service=Depends(get_service)):
 try:return service.request_preview(run_id,request)
 except KeyError as e:raise HTTPException(404,"idea not found") from e
 except ValueError as e:raise HTTPException(409,str(e)) from e
@router.post("/packages",response_model=PackageOut)
async def package(request:PackageIn,service:Service=Depends(get_service)):
 try:return await service.package(request)
 except KeyError as e:raise HTTPException(404,"idea not found") from e

def _error(e):
 if isinstance(e,LookupError):return HTTPException(404,"idea or experiment not found")
 if isinstance(e,ConflictError):return HTTPException(409,str(e))
 return HTTPException(422,str(e))
@router.post("/portfolio/ideas",response_model=Idea,status_code=status.HTTP_201_CREATED)
def create_idea(data:IdeaCreate,service:LedgerService=Depends(get_ledger)):return service.create_idea(data)
@router.get("/portfolio/ideas",response_model=list[Idea])
def list_ideas(stage:IdeaStage|None=Query(None),service:LedgerService=Depends(get_ledger)):return service.list_ideas(stage)
@router.get("/portfolio/ideas/{idea_id}",response_model=IdeaDossier)
def dossier(idea_id:str,service:LedgerService=Depends(get_ledger)):
 try:return service.dossier(idea_id)
 except (LookupError,ConflictError,ValidationError) as e:raise _error(e) from e
@router.post("/portfolio/ideas/{idea_id}/evidence",response_model=Evidence,status_code=201)
def add_evidence(idea_id:str,data:EvidenceCreate,service:LedgerService=Depends(get_ledger)):
 try:return service.add_evidence(idea_id,data)
 except (LookupError,ConflictError,ValidationError) as e:raise _error(e) from e
@router.post("/portfolio/ideas/{idea_id}/feasibility-tests",response_model=FeasibilityTest,status_code=201)
def feasibility(idea_id:str,data:FeasibilityTestCreate,service:LedgerService=Depends(get_ledger)):
 try:return service.test_feasibility(idea_id,data)
 except (LookupError,ConflictError,ValidationError) as e:raise _error(e) from e
@router.post("/portfolio/ideas/{idea_id}/experiments",response_model=Experiment,status_code=201)
def create_experiment(idea_id:str,data:ExperimentCreate,service:LedgerService=Depends(get_ledger)):
 try:return service.create_experiment(idea_id,data)
 except (LookupError,ConflictError,ValidationError) as e:raise _error(e) from e
@router.patch("/portfolio/ideas/{idea_id}/experiments/{experiment_id}",response_model=Experiment)
def update_experiment(idea_id:str,experiment_id:str,data:ExperimentUpdate,service:LedgerService=Depends(get_ledger)):
 try:return service.update_experiment(idea_id,experiment_id,data)
 except (LookupError,ConflictError,ValidationError) as e:raise _error(e) from e
@router.post("/portfolio/ideas/{idea_id}/decisions",response_model=Decision,status_code=201)
def decision(idea_id:str,data:DecisionCreate,service:LedgerService=Depends(get_ledger)):
 try:return service.decide(idea_id,data)
 except (LookupError,ConflictError,ValidationError) as e:raise _error(e) from e

# Feature rows 360-399 are mounted as a sub-router so the global module prefix stays stable.
from .business_router import router as business_router
router.include_router(business_router)

from .operations_router import router as operations_router
router.include_router(operations_router)

from .research_router import router as research_router
router.include_router(research_router)

class AssumptionBurnDownIn(BaseModel):
 assumptions:list[dict]=Field(min_length=1,max_length=500);tests:list[dict]=Field(min_length=1,max_length=1000);budget:float=Field(default=0,ge=0)
@router.post('/assumption-burn-down')
def assumption_burn_down(data:AssumptionBurnDownIn):
 from .assumption_tests import rank_assumption_tests
 try:return rank_assumption_tests(data.assumptions,data.tests,data.budget)
 except ValueError as error:raise HTTPException(422,str(error)) from error

from .luxury_venture import VentureBrief,build_luxury_venture
@router.post('/luxury-venture-studio')
def luxury_venture_studio(data:VentureBrief):
 try:return build_luxury_venture(data)
 except ValueError as error:raise HTTPException(422,str(error)) from error

from .luxury_venture import PitchPackageRequest,build_pitch_package
@router.post('/luxury-venture-studio/pitch-package')
def luxury_venture_pitch_package(data:PitchPackageRequest):
 try:return build_pitch_package(data)
 except ValueError as error:raise HTTPException(422,str(error)) from error

class LuxuryPortfolioIn(BaseModel):
 brief:VentureBrief
 owner_id:str=Field(min_length=1,max_length=200)
@router.post('/luxury-venture-studio/portfolio',response_model=Idea,status_code=201)
def persist_luxury_venture(data:LuxuryPortfolioIn,service:LedgerService=Depends(get_ledger)):
 studio=build_luxury_venture(data.brief);winner=next(x for x in studio['concepts'] if x['concept_id']==studio['recommended_concept_id'])
 return service.create_idea(IdeaCreate(title=winner['name'],problem=data.brief.customer_job,proposed_solution=winner['promise'],tags=['luxury-venture',data.brief.sector],metadata={'brand_or_segment':data.brief.brand_or_segment,'evidence_refs':winner['evidence_refs'],'scorecard':winner['scores'],'review_status':'pending'}))

from .luxury_venture import OutreachPreview,validate_outreach_preview
class LuxuryOutreachRequest(BaseModel):
 package:PitchPackageRequest
 outreach:OutreachPreview
@router.post('/luxury-venture-studio/outreach-preview',response_model=ApprovalRequest,status_code=201)
def luxury_outreach_preview(data:LuxuryOutreachRequest,t:TenantContext=Depends(require_tenant)):

 try:
  package=build_pitch_package(data.package);preview=validate_outreach_preview(data.outreach,package)
 except ValueError as error:raise HTTPException(422,str(error)) from error
 item=ApprovalRequest(id=str(__import__('uuid').uuid4()),module_id=19,action_type='luxury_venture_outreach',payload={**preview,'tenant_id':t.tenant_id})
 return approvals.put(item,user_id=t.tenant_id)

from .luxury_venture import VentureOutcome,summarize_outcome
class LuxuryOutcomeRequest(BaseModel):
 outcome:VentureOutcome
 evidence_kind:EvidenceKind=EvidenceKind.EXPERIMENT
@router.post('/luxury-venture-studio/portfolio/{idea_id}/experiments/{experiment_id}/outcome')
def luxury_venture_outcome(idea_id:str,experiment_id:str,data:LuxuryOutcomeRequest,service:LedgerService=Depends(get_ledger)):
 try:
  summary=summarize_outcome(data.outcome)
  updated=service.update_experiment(idea_id,experiment_id,ExperimentUpdate(status=ExperimentStatus(data.outcome.status),observed_value=data.outcome.observed_value,learnings=data.outcome.learnings))
  polarity=EvidencePolarity.SUPPORTS if data.outcome.status=='succeeded' else EvidencePolarity.CONTRADICTS if data.outcome.status=='failed' else EvidencePolarity.NEUTRAL
  evidence=service.add_evidence(idea_id,EvidenceCreate(kind=data.evidence_kind,claim=data.outcome.learnings,source=', '.join(data.outcome.source_refs),polarity=polarity,strength=.9,confidence=.8,observed_at=updated.updated_at,metadata={'experiment_id':experiment_id,'target_met':summary['target_met']}))
  return {'experiment':updated,'evidence':evidence,'learning_summary':summary,'idea_stage_changed':False}
 except (LookupError,ConflictError,ValidationError,ValueError) as error:raise _error(error) from error
