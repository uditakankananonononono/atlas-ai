"""FastAPI routes for Module 19 Idea Incubator."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .lane_models import (
    Decision, DecisionCreate, Evidence, EvidenceCreate, EvidenceSummary,
    Experiment, ExperimentCreate, ExperimentUpdate, FeasibilityTest,
    FeasibilityTestCreate, Idea, IdeaCreate, IdeaDossier, IdeaStage,
)
from .lane_repository import ConflictError, NotFoundError
from .lane_service import IdeaIncubatorService, ValidationError

router = APIRouter(prefix="/api/modules/19/ideas", tags=["module-19-idea-incubator"])
_service = IdeaIncubatorService()


def get_service() -> IdeaIncubatorService:
    return _service


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.post("", response_model=Idea, status_code=status.HTTP_201_CREATED)
def create_idea(payload: IdeaCreate, service: IdeaIncubatorService = Depends(get_service)):
    return service.create_idea(payload)


@router.get("", response_model=list[Idea])
def list_ideas(stage: IdeaStage | None = Query(default=None), service: IdeaIncubatorService = Depends(get_service)):
    return service.list_ideas(stage)


@router.get("/{idea_id}", response_model=IdeaDossier)
def get_dossier(idea_id: UUID, service: IdeaIncubatorService = Depends(get_service)):
    try:
        return service.dossier(idea_id)
    except (NotFoundError, ConflictError, ValidationError) as exc:
        raise translate_error(exc) from exc


@router.post("/{idea_id}/evidence", response_model=Evidence, status_code=201)
def add_evidence(idea_id: UUID, payload: EvidenceCreate, service: IdeaIncubatorService = Depends(get_service)):
    try:
        return service.add_evidence(idea_id, payload)
    except (NotFoundError, ConflictError, ValidationError) as exc:
        raise translate_error(exc) from exc


@router.get("/{idea_id}/evidence/summary", response_model=EvidenceSummary)
def evidence_summary(idea_id: UUID, service: IdeaIncubatorService = Depends(get_service)):
    try:
        return service.summarize_evidence(idea_id)
    except (NotFoundError, ConflictError, ValidationError) as exc:
        raise translate_error(exc) from exc


@router.post("/{idea_id}/feasibility-tests", response_model=FeasibilityTest, status_code=201)
def run_feasibility_test(idea_id: UUID, payload: FeasibilityTestCreate, service: IdeaIncubatorService = Depends(get_service)):
    try:
        return service.run_feasibility_test(idea_id, payload)
    except (NotFoundError, ConflictError, ValidationError) as exc:
        raise translate_error(exc) from exc


@router.post("/{idea_id}/experiments", response_model=Experiment, status_code=201)
def create_experiment(idea_id: UUID, payload: ExperimentCreate, service: IdeaIncubatorService = Depends(get_service)):
    try:
        return service.create_experiment(idea_id, payload)
    except (NotFoundError, ConflictError, ValidationError) as exc:
        raise translate_error(exc) from exc


@router.patch("/{idea_id}/experiments/{experiment_id}", response_model=Experiment)
def update_experiment(idea_id: UUID, experiment_id: UUID, payload: ExperimentUpdate, service: IdeaIncubatorService = Depends(get_service)):
    try:
        return service.update_experiment(idea_id, experiment_id, payload)
    except (NotFoundError, ConflictError, ValidationError) as exc:
        raise translate_error(exc) from exc


@router.post("/{idea_id}/decisions", response_model=Decision, status_code=201)
def record_decision(idea_id: UUID, payload: DecisionCreate, service: IdeaIncubatorService = Depends(get_service)):
    try:
        return service.record_decision(idea_id, payload)
    except (NotFoundError, ConflictError, ValidationError) as exc:
        raise translate_error(exc) from exc
