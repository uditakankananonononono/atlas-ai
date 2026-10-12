"""Authenticated compatibility surface over the canonical durable idea ledger.

No separate global repository is used. Request owner/actor fields are retained for
wire compatibility but never choose identity or storage scope.
"""
from fastapi import APIRouter,Depends,HTTPException,Query
from app.auth.context import TenantContext,require_tenant
from . import lane_models as old
from . import schemas as canonical
from .ledger import LedgerService,ConflictError,ValidationError
from .repository import SqlIdeaRepository
def get_service(t:TenantContext=Depends(require_tenant)):
    return LedgerService(SqlIdeaRepository(t.tenant_id),t.actor_id)

router=APIRouter(prefix='/api/modules/19/ideas',tags=['module-19-idea-incubator'],dependencies=[Depends(require_tenant)])

def convert(model,value):return model.model_validate(value.model_dump(mode='json'))
def idea_view(value):
    # Existing canonical rows may predate owner attribution. Do not invent it.
    return old.Idea.model_validate({**value.model_dump(mode='json'),'owner_id':value.metadata.get('captured_by','unattributed')})
def invoke(call):
    try:return call()
    except (LookupError,ValueError,RuntimeError) as exc:
        code=404 if isinstance(exc,LookupError) else 409 if isinstance(exc,RuntimeError) else 422
        raise HTTPException(code,str(exc)) from exc

@router.post('',response_model=old.Idea,status_code=201)
def create(payload:old.IdeaCreate,service:LedgerService=Depends(get_service),t:TenantContext=Depends(require_tenant)):
    data=payload.model_dump(exclude={'owner_id'});data['metadata']={**data['metadata'],'captured_by':t.actor_id}
    return idea_view(service.create_idea(canonical.IdeaCreate.model_validate(data)))
@router.get('',response_model=list[old.Idea])
def listing(stage:old.IdeaStage|None=Query(None),service:LedgerService=Depends(get_service)):
    return [idea_view(x) for x in service.list_ideas(canonical.IdeaStage(stage.value) if stage else None)]
@router.get('/{idea_id}',response_model=old.IdeaDossier)
def dossier(idea_id:str,service:LedgerService=Depends(get_service)):
    value=invoke(lambda:service.dossier(idea_id));return old.IdeaDossier.model_validate({**value.model_dump(mode='json'),'idea':idea_view(value.idea).model_dump(mode='json')})
@router.post('/{idea_id}/evidence',response_model=old.Evidence,status_code=201)
def evidence(idea_id:str,payload:old.EvidenceCreate,service:LedgerService=Depends(get_service)):
    return convert(old.Evidence,invoke(lambda:service.add_evidence(idea_id,convert(canonical.EvidenceCreate,payload))))
@router.get('/{idea_id}/evidence/summary',response_model=old.EvidenceSummary)
def summary(idea_id:str,service:LedgerService=Depends(get_service)):
    return convert(old.EvidenceSummary,invoke(lambda:service.evidence_summary(idea_id)))
@router.post('/{idea_id}/feasibility-tests',response_model=old.FeasibilityTest,status_code=201)
def feasibility(idea_id:str,payload:old.FeasibilityTestCreate,service:LedgerService=Depends(get_service)):
    return convert(old.FeasibilityTest,invoke(lambda:service.test_feasibility(idea_id,convert(canonical.FeasibilityTestCreate,payload))))
@router.post('/{idea_id}/experiments',response_model=old.Experiment,status_code=201)
def experiment(idea_id:str,payload:old.ExperimentCreate,service:LedgerService=Depends(get_service)):
    return convert(old.Experiment,invoke(lambda:service.create_experiment(idea_id,convert(canonical.ExperimentCreate,payload))))
@router.patch('/{idea_id}/experiments/{experiment_id}',response_model=old.Experiment)
def update(idea_id:str,experiment_id:str,payload:old.ExperimentUpdate,service:LedgerService=Depends(get_service)):
    return convert(old.Experiment,invoke(lambda:service.update_experiment(idea_id,experiment_id,convert(canonical.ExperimentUpdate,payload))))
@router.post('/{idea_id}/decisions',response_model=old.Decision,status_code=201)
def decision(idea_id:str,payload:old.DecisionCreate,service:LedgerService=Depends(get_service)):
    data=canonical.DecisionCreate.model_validate(payload.model_dump(exclude={'actor_id'}))
    return convert(old.Decision,invoke(lambda:service.decide(idea_id,data)))
