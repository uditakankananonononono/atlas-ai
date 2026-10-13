"""Authenticated endpoints for Claire's bounded research laboratory."""
from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .research_lab import ClosedLoopResearchEngine, generate_concept_lattice, ExperimentalOntologyDiscovery
from .source_connectors import analyze_signals
from .research_workspace import ResearchWorkspaceStore

router=APIRouter(prefix="/claire/research",tags=["claire-research-lab"])

@lru_cache(maxsize=1)
def _workspace():
    path=os.getenv("CLAIRE_RESEARCH_DB",os.getenv("CLAIRE_DISCOVERY_DB","./data/claire_research.sqlite3"))
    return ResearchWorkspaceStore(Path(path))

def _ctx(tenant: TenantContext=Depends(require_tenant)):
    return tenant.tenant_id,_workspace()

class Case(BaseModel):
    id: str|None=None
    input: dict[str,Any]
    expected: Any
class RunIn(BaseModel):
    domain: str=Field(min_length=1,max_length=160)
    train: list[Case]=Field(min_length=2,max_length=2000)
    validation: list[Case]=Field(min_length=1,max_length=1000)
    test: list[Case]=Field(min_length=1,max_length=1000,description="Untouched confirmation split; used only after candidate selection")
    target_name: str=Field(default="target",min_length=1,max_length=100)
    task_type: Literal["auto","classification","regression"]="auto"
class ConceptsIn(BaseModel):
    domains: list[str]=Field(min_length=1,max_length=100)
    bottlenecks: list[str]=Field(min_length=1,max_length=100)
    methods: list[str]=Field(min_length=1,max_length=100)
    constraints: list[str]=Field(default_factory=lambda:["low compute","public data","reproducible"],max_length=50)
    limit: int=Field(default=1000,ge=1,le=5000)
class OutcomeIn(BaseModel):
    domain: str=Field(min_length=1,max_length=160)
    task_type: str=Field(min_length=1,max_length=160)
    complexity: float=Field(ge=0,le=1)
    passed: bool
    predicted_confidence: float|None=Field(default=None,ge=0,le=1)
    model_id: str=Field(default="default",min_length=1,max_length=160)
class SignalsIn(BaseModel): signals: list[dict[str,Any]]=Field(min_length=1,max_length=500)
class OperatorIn(BaseModel): rows: list[dict[str,Any]]=Field(min_length=1,max_length=1000); max_operators: int=Field(default=40,ge=1,le=200)
class ProposalIn(BaseModel):
    action_type: str
    payload: dict[str,Any]
    ttl_minutes: int=Field(default=30,ge=1,le=1440)
    note: str=Field(default="",max_length=2000)
class ApproveIn(BaseModel): expected_payload_hash: str=Field(min_length=64,max_length=64); note: str=Field(default="",max_length=2000)
class ConsumeIn(BaseModel): action_type: str; payload: dict[str,Any]

@router.post("/runs",status_code=201)
def research_run(body: RunIn,ctx=Depends(_ctx)):
    tenant,store=ctx
    try:
        report=ClosedLoopResearchEngine().run(train=[c.model_dump() for c in body.train],validation=[c.model_dump() for c in body.validation],test=[c.model_dump() for c in body.test],domain=body.domain,target_name=body.target_name,task_type=body.task_type)
        saved=store.save_run(tenant,report)
        return {"report":report,"persistence":saved}
    except (ValueError,TypeError) as e: raise HTTPException(422,str(e)) from e

@router.get("/runs")
def list_runs(limit:int=Query(50,ge=1,le=200),ctx=Depends(_ctx)):
    tenant,store=ctx; return {"items":store.list_runs(tenant,limit)}

@router.post("/concept-lattice")
def concept_lattice(body: ConceptsIn,ctx=Depends(_ctx)):
    try: return {"items":generate_concept_lattice(**body.model_dump()),"status":"unreviewed_ideas","warning":"Generated idea count is not novelty or scientific evidence."}
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.post("/intervention-proposals")
def interventions(body: OperatorIn,ctx=Depends(_ctx)):
    try: return {"items":ExperimentalOntologyDiscovery().propose(body.rows,max_operators=body.max_operators),"execution":"proposal-only; generated operators are not applied to real-world systems"}
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.post("/signals")
def ingest_signals(body: SignalsIn,ctx=Depends(_ctx)):
    tenant,store=ctx
    try:
        saved=store.add_signals(tenant,body.signals)
        signals=store.list_signals(tenant,limit=5000)
        return {"stored":saved,"analysis":analyze_signals(signals)}
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.get("/signals")
def list_signals(limit:int=Query(500,ge=1,le=5000),ctx=Depends(_ctx)):
    tenant,store=ctx; return {"items":store.list_signals(tenant,limit)}

@router.post("/outcomes")
def record_outcome(body: OutcomeIn,ctx=Depends(_ctx)):
    tenant,store=ctx
    try: return store.record_outcome(tenant,**body.model_dump())
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.get("/epistemic-map")
def epistemic_map(limit:int=Query(5000,ge=1,le=50000),ctx=Depends(_ctx)):
    tenant,store=ctx; return store.epistemic_report(tenant,limit)

@router.post("/approvals",status_code=201)
def propose_action(body: ProposalIn,ctx=Depends(_ctx)):
    tenant,store=ctx
    try: return store.approvals.propose(tenant,body.action_type,body.payload,ttl_minutes=body.ttl_minutes,note=body.note)
    except ValueError as e: raise HTTPException(422,str(e)) from e

def _trusted_approver(tenant: TenantContext) -> str:
    """Fail closed unless identity and approval authority come from auth context, not JSON."""
    actor = (getattr(tenant, "actor_id", None) or getattr(tenant, "user_id", None)
             or getattr(tenant, "subject", None))
    raw_roles = getattr(tenant, "roles", None) or []
    raw_scopes = getattr(tenant, "scopes", None) or []
    roles = {raw_roles} if isinstance(raw_roles, str) else set(raw_roles)
    scopes = {raw_scopes} if isinstance(raw_scopes, str) else set(raw_scopes)
    permitted = bool(getattr(tenant, "can_approve_actions", False)) or "actions:approve" in scopes or bool(roles.intersection({"owner", "admin", "approver"}))
    if not actor or not permitted:
        raise HTTPException(403, "authenticated actor lacks the configured action-approval permission")
    return str(actor)

@router.post("/approvals/{approval_id}/approve")
def approve_action(approval_id:str,body:ApproveIn,ctx=Depends(_ctx),tenant:TenantContext=Depends(require_tenant)):
    tenant_id,store=ctx
    actor_id=_trusted_approver(tenant)
    try: return store.approvals.approve(tenant_id,approval_id,actor_id=actor_id,expected_payload_hash=body.expected_payload_hash,note=body.note)
    except KeyError as e: raise HTTPException(404,str(e)) from e
    except (ValueError,RuntimeError) as e: raise HTTPException(409,str(e)) from e

def _trusted_executor(tenant: TenantContext) -> str:
    actor=(getattr(tenant,"actor_id",None) or getattr(tenant,"user_id",None) or getattr(tenant,"subject",None))
    raw_roles=getattr(tenant,"roles",None) or []; raw_scopes=getattr(tenant,"scopes",None) or []
    roles={raw_roles} if isinstance(raw_roles,str) else set(raw_roles)
    scopes={raw_scopes} if isinstance(raw_scopes,str) else set(raw_scopes)
    permitted=bool(getattr(tenant,"can_execute_approved_actions",False)) or "actions:execute" in scopes or bool(roles.intersection({"owner","admin","executor","worker"}))
    if not actor or not permitted: raise HTTPException(403,"authenticated actor lacks the configured action-execution permission")
    return str(actor)

@router.get("/approvals/{approval_id}")
def get_approval(approval_id:str,ctx=Depends(_ctx),tenant:TenantContext=Depends(require_tenant)):
    tenant_id,store=ctx
    _trusted_approver(tenant)
    try: return store.approvals.get(tenant_id,approval_id)
    except KeyError as e: raise HTTPException(404,str(e)) from e

@router.post("/approvals/{approval_id}/consume")
def consume_action(approval_id:str,body:ConsumeIn,ctx=Depends(_ctx),tenant:TenantContext=Depends(require_tenant)):
    tenant_id,store=ctx
    _trusted_executor(tenant)
    try: return store.approvals.consume(tenant_id,approval_id,action_type=body.action_type,payload=body.payload)
    except KeyError as e: raise HTTPException(404,str(e)) from e
    except (ValueError,RuntimeError) as e: raise HTTPException(409,str(e)) from e

@router.get("/approvals")
def list_approvals(limit:int=Query(100,ge=1,le=500),ctx=Depends(_ctx)):
    tenant,store=ctx; return {"items":store.approvals.list(tenant,limit)}

# Optional, explicit user-preference learning. This stores only choices the user makes.
from .learning_interview import PreferenceInterviewStore
from .opportunity_engine import rank_opportunities, research_dossier, draft_evidence_post

@lru_cache(maxsize=1)
def _preferences():
    path=os.getenv("CLAIRE_RESEARCH_DB",os.getenv("CLAIRE_DISCOVERY_DB","./data/claire_research.sqlite3"))
    return PreferenceInterviewStore(Path(path))

class OpportunityRankIn(BaseModel):
    opportunities: list[dict[str,Any]]=Field(min_length=1,max_length=1000)
    profile: dict[str,Any]=Field(default_factory=dict)
    limit:int=Field(default=50,ge=1,le=200)
class DossierIn(BaseModel):
    topic:str=Field(min_length=1,max_length=500)
    sources:list[dict[str,Any]]=Field(default_factory=list,max_length=500)
    max_sources:int=Field(default=30,ge=1,le=100)
class ContentDraftIn(BaseModel):
    topic:str=Field(min_length=1,max_length=500)
    audience:str=Field(min_length=1,max_length=500)
    evidence:list[dict[str,Any]]=Field(default_factory=list,max_length=100)
    voice:str=Field(default="clear, curious, evidence-led",max_length=500)
    call_to_action:str=Field(default="What evidence would change your mind?",max_length=1000)
    max_sources:int=Field(default=5,ge=1,le=20)
class QuestionIn(BaseModel):
    domain:str=Field(min_length=1,max_length=160)
    criterion:str=Field(min_length=1,max_length=160)
    options:list[str]=Field(min_length=2,max_length=100)
    context:str=Field(default="",max_length=2000)
class PreferenceAnswerIn(BaseModel):
    domain:str=Field(min_length=1,max_length=160)
    criterion:str=Field(min_length=1,max_length=160)
    left_option:str=Field(min_length=1,max_length=500)
    right_option:str=Field(min_length=1,max_length=500)
    chosen_option:str=Field(min_length=1,max_length=500)
    importance:float=Field(default=1,ge=0,le=1)
    context:str=Field(default="",max_length=2000)

@router.post("/opportunities/rank")
def opportunity_rank(body:OpportunityRankIn,ctx=Depends(_ctx)):
    try: return rank_opportunities(body.opportunities,body.profile,limit=body.limit)
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.post("/dossier")
def dossier(body:DossierIn,ctx=Depends(_ctx)):
    try: return research_dossier(body.topic,body.sources,max_sources=body.max_sources)
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.post("/content-draft")
def content_draft(body:ContentDraftIn,ctx=Depends(_ctx)):
    try: return draft_evidence_post(topic=body.topic,audience=body.audience,evidence=body.evidence,voice=body.voice,call_to_action=body.call_to_action,max_sources=body.max_sources)
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.post("/learning/next-question")
def next_preference_question(body:QuestionIn,ctx=Depends(_ctx)):
    tenant,_=ctx
    try: return _preferences().next_question(tenant,body.domain,body.criterion,body.options,context=body.context)
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.post("/learning/answer",status_code=201)
def preference_answer(body:PreferenceAnswerIn,ctx=Depends(_ctx)):
    tenant,_=ctx
    try: return _preferences().answer(tenant,**body.model_dump())
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.get("/learning/profile")
def preference_profile(domain:str|None=None,ctx=Depends(_ctx)):
    tenant,_=ctx; return _preferences().profile(tenant,domain)

@router.delete("/learning/profile")
def erase_preference_profile(domain:str|None=None,ctx=Depends(_ctx)):
    tenant,_=ctx; return _preferences().erase(tenant,domain)

# Tenant-scoped application and competition portfolio. These routes prepare and track
# application packets; they do not submit forms or contact third parties.
from .application_portfolio import ApplicationPortfolioStore
from .venture_studio import generate_venture_hypotheses, build_content_calendar

@lru_cache(maxsize=1)
def _portfolio():
    path=os.getenv("CLAIRE_APPLICATION_DB",os.getenv("CLAIRE_RESEARCH_DB",os.getenv("CLAIRE_DISCOVERY_DB","./data/claire_applications.sqlite3")))
    return ApplicationPortfolioStore(Path(path))

class PortfolioProfileIn(BaseModel):
    profile: dict[str,Any]

class ApplicationListingIn(BaseModel):
    listing: dict[str,Any]
    notes: str=Field(default="",max_length=5000)

class ApplicationPrepareIn(BaseModel):
    notes: str=Field(default="",max_length=5000)

class ApplicationStatusIn(BaseModel):
    status: Literal["discovered","researching","preparing","needs_user_review","user_approved_to_submit","submitted_confirmed","decision_received","archived"]
    note: str=Field(default="",max_length=2000)
    submission_receipt_url: str|None=None
    manual_confirmation: bool=False

class VentureHypothesesIn(BaseModel):
    signals: list[dict[str,Any]]=Field(min_length=1,max_length=2000)
    profile: dict[str,Any]=Field(default_factory=dict)
    limit: int=Field(default=30,ge=1,le=200)

class ContentCalendarIn(BaseModel):
    signals: list[dict[str,Any]]=Field(min_length=1,max_length=2000)
    audience: str=Field(min_length=1,max_length=500)
    voice: str=Field(default="curious, specific, evidence-led",max_length=500)
    items: int=Field(default=14,ge=1,le=60)

@router.post("/portfolio/profile",status_code=200)
def save_portfolio_profile(body:PortfolioProfileIn,ctx=Depends(_ctx)):
    tenant,_=ctx
    try: return _portfolio().save_profile(tenant,body.profile)
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.get("/portfolio/profile")
def get_portfolio_profile(ctx=Depends(_ctx)):
    tenant,_=ctx; result=_portfolio().get_profile(tenant)
    if result is None: raise HTTPException(404,"No profile saved for this tenant")
    return result

@router.delete("/portfolio/profile")
def erase_portfolio_profile(ctx=Depends(_ctx)):
    tenant,_=ctx; return {"deleted":_portfolio().erase_profile(tenant)}

@router.post("/applications",status_code=201)
def add_application_listing(body:ApplicationListingIn,ctx=Depends(_ctx)):
    tenant,_=ctx
    try: return _portfolio().add_listing(tenant,body.listing,notes=body.notes)
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.get("/applications")
def list_application_listings(limit:int=Query(100,ge=1,le=500),ctx=Depends(_ctx)):
    tenant,_=ctx; return {"items":_portfolio().list_applications(tenant,limit)}

@router.get("/applications/{application_id}")
def get_application_listing(application_id:str,ctx=Depends(_ctx)):
    tenant,_=ctx
    try: return _portfolio().get_application(tenant,application_id)
    except KeyError as e: raise HTTPException(404,"Application not found") from e

@router.post("/applications/{application_id}/prepare")
def prepare_application_packet(application_id:str,body:ApplicationPrepareIn,ctx=Depends(_ctx)):
    tenant,_=ctx
    try: return _portfolio().prepare(tenant,application_id,notes=body.notes)
    except KeyError as e: raise HTTPException(404,"Application not found") from e
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.post("/applications/{application_id}/status")
def update_application_status(application_id:str,body:ApplicationStatusIn,ctx=Depends(_ctx),tenant:TenantContext=Depends(require_tenant)):
    tenant_id,_=ctx
    if body.status == "user_approved_to_submit":
        _trusted_approver(tenant)
    try: return _portfolio().update_status(tenant_id,application_id,body.status,note=body.note,
                                           submission_receipt_url=body.submission_receipt_url,
                                           manual_confirmation=body.manual_confirmation)
    except KeyError as e: raise HTTPException(404,"Application not found") from e
    except ValueError as e: raise HTTPException(409,str(e)) from e
    except RuntimeError as e: raise HTTPException(409,str(e)) from e

@router.post("/venture/hypotheses")
def venture_hypotheses(body:VentureHypothesesIn,ctx=Depends(_ctx)):
    try: return generate_venture_hypotheses(body.signals,body.profile,limit=body.limit)
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.post("/brand/content-calendar")
def brand_content_calendar(body:ContentCalendarIn,ctx=Depends(_ctx)):
    try: return build_content_calendar(body.signals,audience=body.audience,voice=body.voice,items=body.items)
    except ValueError as e: raise HTTPException(422,str(e)) from e

# Four-timescale proposal coordinator (fast, deliberative, learning, strategic).
from .cognitive_loops import CognitiveLoopCoordinator

@lru_cache(maxsize=1)
def _cognitive_loops():
    path=os.getenv("CLAIRE_COGNITION_DB",os.getenv("CLAIRE_RESEARCH_DB",os.getenv("CLAIRE_DISCOVERY_DB","./data/claire_cognition.sqlite3")))
    return CognitiveLoopCoordinator(Path(path))

class CognitiveCycleIn(BaseModel):
    signals: list[dict[str,Any]]=Field(default_factory=list,max_length=1000)
    outcomes: list[dict[str,Any]]=Field(default_factory=list,max_length=1000)
    goals: list[dict[str,Any]]=Field(default_factory=list,max_length=200)
    max_proposals: int=Field(default=40,ge=1,le=100)

class CognitiveReviewIn(BaseModel):
    accepted: bool
    note: str=Field(default="",max_length=1000)

@router.post("/cognition/cycle",status_code=201)
def run_cognitive_cycle(body:CognitiveCycleIn,ctx=Depends(_ctx)):
    tenant,workspace=ctx
    stored=workspace.list_signals(tenant,limit=5000)
    # The explicitly supplied entries extend the tenant's already stored records.
    signal_rows=[*stored,*body.signals]
    try:
        return _cognitive_loops().run_cycle(tenant_id=tenant,signals=signal_rows,outcomes=body.outcomes,
                                             goals=body.goals,max_proposals=body.max_proposals)
    except ValueError as e: raise HTTPException(422,str(e)) from e

@router.get("/cognition/proposals")
def list_cognitive_proposals(limit:int=Query(100,ge=1,le=1000),ctx=Depends(_ctx)):
    tenant,_=ctx; return {"items":_cognitive_loops().list_proposals(tenant,limit)}

@router.post("/cognition/proposals/{proposal_id}/review")
def review_cognitive_proposal(proposal_id:str,body:CognitiveReviewIn,ctx=Depends(_ctx)):
    tenant,_=ctx
    try: return _cognitive_loops().review_proposal(tenant,proposal_id,accepted=body.accepted,note=body.note)
    except KeyError as e: raise HTTPException(404,"Proposal not found or already reviewed") from e
