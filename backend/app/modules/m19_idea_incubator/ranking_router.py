from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException,Query
from app.auth.context import TenantContext,require_tenant
from .ranking import PortfolioRanking,rank_portfolio
from .repository import SqlIdeaRepository
router=APIRouter(prefix="/portfolio",tags=["idea-incubator-ranking"])
def get_ranking_repository(t:TenantContext=Depends(require_tenant)):return SqlIdeaRepository(t.tenant_id)
@router.get("/ranking",response_model=PortfolioRanking)
def ranking(as_of:datetime|None=Query(None),half_life_days:float=Query(90.0,gt=0,le=3650),include_terminal:bool=Query(False),limit:int|None=Query(None,ge=1,le=500),repo=Depends(get_ranking_repository)):
    try:return rank_portfolio(repo,as_of,half_life_days,include_terminal,limit)
    except ValueError as e:raise HTTPException(422,str(e)) from e

from .historical_ranking import HistoricalRanking, rank_portfolio_as_of

@router.get('/ranking/as-of',response_model=HistoricalRanking)
def historical_ranking(as_of:datetime=Query(...),half_life_days:float=Query(90.0,gt=0,le=3650),include_terminal:bool=Query(False),limit:int|None=Query(None,ge=1,le=500),repo=Depends(get_ranking_repository)):
    """Timestamp filter, not reconstructed historical state; safe exclusion policy."""
    try:return rank_portfolio_as_of(repo,as_of,half_life_days,include_terminal,limit,stale_experiment_policy='exclude')
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
