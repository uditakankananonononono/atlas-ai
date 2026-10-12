"""Authenticated, bounded private-build computations. No external effects."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .exact_math import analyze
from .robust_strategy import optimize
from .enclosure import generate
from .patent_preparation import prepare
from .admissions_training import fit

router=APIRouter(prefix='/mission-build',tags=['mission-build'])


class BuildRequest(BaseModel):
    data:dict=Field(default_factory=dict)


@router.post('/{task}')
def run_private(task:str,body:BuildRequest,tenant:TenantContext=Depends(require_tenant)):
    handlers={'polynomial':analyze,'strategy':optimize,'enclosure':generate,'patent-prepare':prepare}
    if task not in handlers:raise HTTPException(404,'unknown private-build task')
    try:
        return {'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id,'result':handlers[task](body.data),'external_effects':[]}
    except (ValueError,KeyError,TypeError,AttributeError) as exc:
        raise HTTPException(422,str(exc)) from exc


class TrainRequest(BaseModel):
    corpus:list[dict]=Field(min_length=4,max_length=10000)
    sources:list[dict]=Field(min_length=10,max_length=100)
    owner_consented:bool=False


@router.post('/admissions/train')
def train(body:TrainRequest,tenant:TenantContext=Depends(require_tenant)):
    if not body.owner_consented:raise HTTPException(403,'explicit owner training consent required')
    try:
        return {'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id,'model':fit(body.corpus,body.sources),'publishing':False}
    except PermissionError as exc:raise HTTPException(403,str(exc)) from exc
    except (ValueError,KeyError,TypeError,AttributeError) as exc:raise HTTPException(422,str(exc)) from exc

def owner_repository(tenant:TenantContext=Depends(require_tenant)):
    from app.modules.m21_claire.personalization import ScopedPersonalizationRepository
    return ScopedPersonalizationRepository(tenant.tenant_id,tenant.actor_id)


@router.get('/owner/growth')
def growth(repository=Depends(owner_repository)):
    return repository.growth_report()


@router.get('/owner/decisions/{decision_id}')
def owner_decision_history(decision_id:int,repository=Depends(owner_repository)):
    try:return repository.decision_history(decision_id)
    except KeyError as exc:raise HTTPException(404,'decision not found') from exc


class OwnerOutcome(BaseModel):
    outcome:str=Field(min_length=1,max_length=50000)
    lesson:str=Field(min_length=1,max_length=50000)
    rating:str
    evidence:dict=Field(default_factory=dict)


@router.post('/owner/decisions/{decision_id}/outcomes',status_code=201)
def owner_outcome(decision_id:int,body:OwnerOutcome,repository=Depends(owner_repository)):
    try:return {'id':repository.add_decision_outcome(decision_id,body.model_dump())}
    except KeyError as exc:raise HTTPException(404,'decision not found') from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
