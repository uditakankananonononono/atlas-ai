from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from app.core.approvals import approvals
from .schemas import *
from .service import Service,NotFoundError
from .sql_repository import Repository
router=APIRouter(prefix="/startup-growth",tags=["startup-growth"])
def get_service(tenant:TenantContext=Depends(require_tenant)):return Service(Repository(tenant.tenant_id),approvals)
@router.post("/landing-pages",response_model=BuildOut,status_code=201)
def landing(data:LandingPageIn,service:Service=Depends(get_service)):return service.landing_page(data)
@router.post("/pitch-decks",response_model=BuildOut,status_code=201)
def deck(data:PitchDeckIn,service:Service=Depends(get_service)):return service.pitch_deck(data)
@router.post("/documentation",response_model=BuildOut,status_code=201)
def docs(data:DocumentationIn,service:Service=Depends(get_service)):return service.documentation(data)
@router.post("/builds/{build_id}/propose/{action}",response_model=PublishProposal,status_code=201)
def propose(build_id:str,action:Literal["push_startup_site","deploy_startup_site","share_pitch_deck","publish_documentation"],service:Service=Depends(get_service)):
    try:return service.propose(build_id,action)
    except NotFoundError as e:raise HTTPException(404,"build not found") from e
@router.post('/technical-85-94/{row_id}')
def technical_85_94(row_id:int,payload:dict):
 from .technical_85_94 import run
 try:return run(row_id,payload)
 except (ValueError,TypeError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


# -- free-first experiment board ---------------------------------------------------
from pydantic import BaseModel as _BM, Field as _F
from .experiments import ExperimentBoard, ExperimentNotFound, ExperimentRefused


class _Tool(_BM):
    name: str = _F(min_length=1, max_length=200); cost_minor: int = _F(default=0, ge=0); note: str = _F(default="", max_length=500)
class ExperimentIn(_BM):
    title: str = _F(min_length=1, max_length=300); hypothesis: str = _F(min_length=10, max_length=4000)
    metric: str = _F(min_length=1, max_length=200); success_rate: float = _F(gt=0, le=1); baseline_rate: float | None = _F(default=None, ge=0, le=1)
    max_days: int = _F(ge=1, le=365); max_effort_hours: float = _F(gt=0, le=2000); tools: list[_Tool] = _F(min_length=1, max_length=20)
class ObservationIn(_BM):
    exposures: int = _F(ge=0); conversions: int = _F(ge=0); effort_hours: float = _F(default=0, ge=0); source: str = _F(default="", max_length=500); note: str = _F(default="", max_length=2000)
class DecisionIn(_BM):
    decision: str; reason: str = _F(min_length=3, max_length=4000)
class CapIn(_BM):
    add_days: int = _F(default=0, ge=0, le=365); add_effort_hours: float = _F(default=0, ge=0, le=2000); reason: str = _F(min_length=3, max_length=4000)
class PaidProposalIn(_BM):
    description: str = _F(min_length=3, max_length=4000); estimated_cost_minor: int = _F(gt=0); currency: str = _F(default="USD", pattern=r"^[A-Z]{3}$"); rationale: str = _F(min_length=3, max_length=4000)


def get_board(tenant: TenantContext = Depends(require_tenant)) -> ExperimentBoard:
    return ExperimentBoard(tenant.tenant_id, approvals=approvals)


def _ex(call):
    try: return call()
    except ExperimentNotFound as e: raise HTTPException(404, "experiment not found") from e
    except ExperimentRefused as e: raise HTTPException(422, str(e)) from e


@router.post("/experiments", status_code=201)
def create_experiment(data: ExperimentIn, b: ExperimentBoard = Depends(get_board)): return _ex(lambda: b.create(**data.model_dump(exclude={"tools"}), tools=[t.model_dump() for t in data.tools]))
@router.get("/experiments")
def experiment_board(b: ExperimentBoard = Depends(get_board)): return b.board()
@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str, b: ExperimentBoard = Depends(get_board)): return _ex(lambda: b.get(experiment_id))
@router.post("/experiments/{experiment_id}/observations")
def observe_experiment(experiment_id: str, data: ObservationIn, b: ExperimentBoard = Depends(get_board)): return _ex(lambda: b.observe(experiment_id, **data.model_dump()))
@router.post("/experiments/{experiment_id}/decisions")
def decide_experiment(experiment_id: str, data: DecisionIn, b: ExperimentBoard = Depends(get_board)): return _ex(lambda: b.decide(experiment_id, **data.model_dump()))
@router.post("/experiments/{experiment_id}/cap")
def extend_experiment_cap(experiment_id: str, data: CapIn, b: ExperimentBoard = Depends(get_board)): return _ex(lambda: b.extend_cap(experiment_id, **data.model_dump()))
@router.post("/experiments/{experiment_id}/paid-proposals", status_code=201)
def paid_proposal(experiment_id: str, data: PaidProposalIn, b: ExperimentBoard = Depends(get_board)): return _ex(lambda: b.propose_paid(experiment_id, **data.model_dump()))


# -- analytics export import ------------------------------------------------------
from datetime import date as _date
from .analytics_import import ImportError_, from_mapped, from_plausible


class PlausibleImportIn(_BM):
    visitors_csv: str = _F(min_length=1, max_length=5_000_000); custom_events_csv: str = _F(min_length=1, max_length=5_000_000)
    goal: str = _F(min_length=1, max_length=200); start: _date | None = None; end: _date | None = None; effort_hours: float = _F(default=0, ge=0)
class MappedImportIn(_BM):
    csv_text: str = _F(min_length=1, max_length=5_000_000); exposures_col: str; conversions_col: str
    date_col: str | None = None; filter_col: str | None = None; filter_value: str | None = None
    start: _date | None = None; end: _date | None = None; label: str = _F(default="csv", max_length=100); effort_hours: float = _F(default=0, ge=0)


def _imp(b, experiment_id, parse, effort):
    try: parsed = parse()
    except ImportError_ as e: raise HTTPException(422, str(e)) from e
    return _ex(lambda: b.import_observation(experiment_id, parsed, effort_hours=effort)) | {"import": parsed}


@router.post("/experiments/{experiment_id}/import/plausible")
def import_plausible(experiment_id: str, data: PlausibleImportIn, b: ExperimentBoard = Depends(get_board)):
    return _imp(b, experiment_id, lambda: from_plausible(**data.model_dump(exclude={"effort_hours"})), data.effort_hours)
@router.post("/experiments/{experiment_id}/import/csv")
def import_mapped(experiment_id: str, data: MappedImportIn, b: ExperimentBoard = Depends(get_board)):
    return _imp(b, experiment_id, lambda: from_mapped(**data.model_dump(exclude={"effort_hours"})), data.effort_hours)
