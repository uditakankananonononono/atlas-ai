from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .hn_research import HNResearch, ResearchUnavailable

router = APIRouter(prefix='/research/hn', tags=['bounded-live-research'])
class HNQuery(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    as_of: str = Field(min_length=1, max_length=64)
    limit: int = Field(default=100, ge=1, le=100)

def researcher():
    return HNResearch()

@router.post('/trends')
def trends(body: HNQuery, tenant: TenantContext = Depends(require_tenant),
           service: HNResearch = Depends(researcher)):
    try:
        return service.trends(body.query, as_of=body.as_of, limit=body.limit)
    except ValueError as exc:
        raise HTTPException(422, 'invalid research parameters') from exc
    except ResearchUnavailable as exc:
        raise HTTPException(502, str(exc)) from exc

from .preference_ranker import RankingTrial, run_trial

@router.post('/preference-trial')
def preference_trial(body: RankingTrial, tenant: TenantContext = Depends(require_tenant)):
    return run_trial(body)
