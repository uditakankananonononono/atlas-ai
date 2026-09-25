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

# Luxury venture studio: real free data sources (M19, expanded 2026-09-25).
from .luxury_sources import LISTED_LUXURY_WATCHLIST,SOURCE_REGISTRY,LuxuryDataService
from .luxury_service import GroundedStudioRequest,LuxuryVentureService
def get_luxury_data_service()->LuxuryDataService:return LuxuryDataService()
def get_luxury_venture_service()->LuxuryVentureService:return LuxuryVentureService()
@router.get('/luxury-venture-studio/sources')
def luxury_free_sources()->dict:return SOURCE_REGISTRY
@router.get('/luxury-venture-studio/news')
async def luxury_news(query:str=Query(min_length=2,max_length=200),limit:int=Query(15,ge=1,le=40),data:LuxuryDataService=Depends(get_luxury_data_service)):
 try:items,report=await data.news(query,limit)
 except Exception as e:raise HTTPException(502,'upstream source failed: '+str(e)[:200]) from e
 return {'query':query,'items':items,'fetch_report':report,'all_sources_free':True}
@router.get('/luxury-venture-studio/brand')
async def luxury_brand_profile(name:str=Query(min_length=2,max_length=200),data:LuxuryDataService=Depends(get_luxury_data_service)):
 try:profile,report=await data.brand_profile(name)
 except Exception as e:raise HTTPException(502,'upstream source failed: '+str(e)[:200]) from e
 return {'profile':profile,'fetch_report':report}
@router.get('/luxury-venture-studio/company/{ticker}')
async def luxury_company_facts(ticker:str,data:LuxuryDataService=Depends(get_luxury_data_service)):
 try:company,report=await data.company_facts(ticker)
 except ValueError as e:raise HTTPException(422,str(e)) from e
 except Exception as e:raise HTTPException(502,'upstream source failed: '+str(e)[:200]) from e
 return {'company':company,'fetch_report':report}
class LuxuryEvidenceIn(BaseModel):
 brand_or_segment:str=Field(min_length=2,max_length=200)
 sector:str=Field(default='other',pattern=r'^(automotive|character_ip|hotel|luxury_hospitality|fashion|jewelry|other)$')
 ticker:str|None=Field(default=None,pattern=r'^[A-Za-z]{1,6}$')
 limit:int=Field(default=12,ge=1,le=30)
@router.post('/luxury-venture-studio/evidence')
async def luxury_evidence(data:LuxuryEvidenceIn,service:LuxuryVentureService=Depends(get_luxury_venture_service)):
 try:return await service.collect(data.brand_or_segment,data.sector,data.ticker,data.limit)
 except ValueError as e:raise HTTPException(422,str(e)) from e
@router.post('/luxury-venture-studio/grounded')
async def luxury_grounded_studio(data:GroundedStudioRequest,service:LuxuryVentureService=Depends(get_luxury_venture_service)):
 try:return await service.grounded_studio(data)
 except ValueError as e:raise HTTPException(422,str(e)) from e

# Luxury venture studio phase 2: twenty real tools and data capabilities.
from .luxury_tools import (MarketSizingIn,PriceSensitivityIn,SECTOR_PRESETS,digest,explain_scorecard,follow_up_plan,interview_script,kpi_sheet,market_sizing,objection_sheet,pitch_outline,positioning_map,price_sensitivity,sector_presets,select_validation_methods)
@router.get('/luxury-venture-studio/company-compare')
async def luxury_company_compare(tickers:str=Query(min_length=1,max_length=60),data:LuxuryDataService=Depends(get_luxury_data_service)):
 chosen=[t.strip().upper() for t in tickers.split(',') if t.strip()]
 if not 2<=len(chosen)<=6:raise HTTPException(422,'supply 2-6 comma-separated tickers')
 try:return await data.company_compare(chosen)
 except Exception as e:raise HTTPException(502,'upstream source failed: '+str(e)[:200]) from e
@router.get('/luxury-venture-studio/filings')
async def luxury_filing_search(query:str=Query(min_length=2,max_length=120),limit:int=Query(10,ge=1,le=40),data:LuxuryDataService=Depends(get_luxury_data_service)):
 try:hits,report=await data.filing_search(query,limit)
 except Exception as e:raise HTTPException(502,'upstream source failed: '+str(e)[:200]) from e
 return {'query':query,'filings':hits,'fetch_report':report,'note':'Real SEC EDGAR full-text filing search, free.'}
@router.get('/luxury-venture-studio/company/{ticker}/contact')
async def luxury_company_contact(ticker:str,data:LuxuryDataService=Depends(get_luxury_data_service)):
 try:return await data.company_contact(ticker)
 except ValueError as e:raise HTTPException(422,str(e)) from e
 except Exception as e:raise HTTPException(502,'upstream source failed: '+str(e)[:200]) from e
@router.get('/luxury-venture-studio/mentions')
async def luxury_mentions(query:str=Query(min_length=2,max_length=120),limit:int=Query(25,ge=1,le=40),data:LuxuryDataService=Depends(get_luxury_data_service)):
 try:return await data.mentions(query,limit)
 except Exception as e:raise HTTPException(502,'upstream source failed: '+str(e)[:200]) from e
@router.get('/luxury-venture-studio/sources/health')
async def luxury_sources_health(data:LuxuryDataService=Depends(get_luxury_data_service)):
 try:return await data.sources_health()
 except Exception as e:raise HTTPException(502,'upstream source failed: '+str(e)[:200]) from e
class EvidenceRefreshIn(BaseModel):
 brand_or_segment:str=Field(min_length=2,max_length=200);sector:str=Field(default='other',max_length=40);ticker:str|None=Field(default=None,pattern=r'^[A-Za-z]{1,6}$');prior_source_ids:list[str]=Field(default_factory=list,max_length=100);limit:int=Field(default=12,ge=1,le=30)
@router.post('/luxury-venture-studio/evidence/refresh')
async def luxury_evidence_refresh(data:EvidenceRefreshIn,service:LuxuryVentureService=Depends(get_luxury_venture_service)):
 fresh=await service.collect(data.brand_or_segment,data.sector,data.ticker,data.limit)
 current={s['source_id'] for s in fresh['sources']};prior=set(data.prior_source_ids)
 fresh['refresh']={'added':sorted(current-prior),'persisted':sorted(current&prior),'no_longer_returned':sorted(prior-current),'note':'IDs are positional for news items; treat added/no_longer_returned as title-level changes for news sources.'}
 return fresh
@router.post('/luxury-venture-studio/tools/price-sensitivity')
def luxury_price_sensitivity(data:PriceSensitivityIn):
 try:return price_sensitivity(data)
 except ValueError as e:raise HTTPException(422,str(e)) from e
@router.post('/luxury-venture-studio/tools/market-sizing')
def luxury_market_sizing(data:MarketSizingIn):return market_sizing(data)
class InterviewScriptIn(BaseModel):
 customer_job:str=Field(min_length=10,max_length=1000);constraints:list[str]=Field(default_factory=list,max_length=30)
@router.post('/luxury-venture-studio/tools/interview-script')
def luxury_interview_script(data:InterviewScriptIn):return interview_script(data.customer_job,data.constraints)
class ValidationMethodsIn(BaseModel):
 constraints:list[str]=Field(default_factory=list,max_length=30)
@router.post('/luxury-venture-studio/tools/validation-methods')
def luxury_validation_methods(data:ValidationMethodsIn):return select_validation_methods(data.constraints)
class ConceptToolIn(BaseModel):
 concept:dict;sector:str=Field(default='other',max_length=40)
@router.post('/luxury-venture-studio/tools/pitch-outline')
def luxury_pitch_outline(data:ConceptToolIn):
 try:return pitch_outline(data.concept,data.sector)
 except (KeyError,ValueError) as e:raise HTTPException(422,'concept lacks required fields: '+str(e)) from e
class FollowUpIn(BaseModel):
 subject:str=Field(min_length=3,max_length=200);days:list[int]|None=None
@router.post('/luxury-venture-studio/tools/follow-up-plan')
def luxury_follow_up(data:FollowUpIn):return follow_up_plan(data.subject,data.days)
@router.post('/luxury-venture-studio/tools/objection-sheet')
def luxury_objections(data:ConceptToolIn):
 try:return objection_sheet(data.concept)
 except (KeyError,ValueError) as e:raise HTTPException(422,'concept lacks required fields: '+str(e)) from e
@router.post('/luxury-venture-studio/tools/kpi-sheet')
def luxury_kpis(data:ConceptToolIn):
 try:return kpi_sheet(data.concept)
 except (KeyError,ValueError) as e:raise HTTPException(422,'concept lacks required fields: '+str(e)) from e
class PositioningIn(BaseModel):
 price_band:float=Field(ge=1,le=5);heritage:float=Field(ge=1,le=5);peers:list[dict]=Field(default_factory=list,max_length=20)
@router.post('/luxury-venture-studio/tools/positioning-map')
def luxury_positioning(data:PositioningIn):
 try:return positioning_map(data.price_band,data.heritage,data.peers)
 except ValueError as e:raise HTTPException(422,str(e)) from e
class ScorecardIn(BaseModel):
 scores:dict
@router.post('/luxury-venture-studio/tools/explain-scorecard')
def luxury_explain_scorecard(data:ScorecardIn):return explain_scorecard(data.scores)
@router.get('/luxury-venture-studio/tools/sector-presets')
def luxury_sector_presets():return sector_presets()
@router.get('/luxury-venture-studio/tools/comparable-set')
def luxury_comparable_set(sector:str=Query(default='other')):
 listed=[{'ticker':t,'name':n} for t,(n,s,_c) in LISTED_LUXURY_WATCHLIST.items() if s==sector]
 return {'sector':sector,'listed_comparables':listed,'non_listed_note':'Private or European-listed houses (Chanel, LVMH, Hermes, Kering, Richemont, Moncler, Burberry, Sanrio) are covered through news and reference sources only.'}
class DigestIn(BaseModel):
 pack:dict
@router.post('/luxury-venture-studio/tools/digest')
def luxury_digest(data:DigestIn):return digest(data.pack)
