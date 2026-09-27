"""Read-only Claire cards from M06's already-stored social observations."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth.context import TenantContext, require_tenant
from app.modules.m06_social_media_manager.social_reading.routes import get_store
from app.modules.m06_social_media_manager.social_reading.knowledge import KnowledgeStore
from .social_signal_review import review_signals

router = APIRouter(prefix="/claire/social-signals", tags=["claire-social-signals"])

@router.get("/review")
def review(min_score: float = Query(default=0.25, ge=0, le=1),
           limit: int = Query(default=25, ge=1, le=100), since: datetime | None = None,
           tenant: TenantContext = Depends(require_tenant), store: KnowledgeStore = Depends(get_store)):
    try:
        return review_signals(store, tenant.tenant_id, min_score=min_score, limit=limit, since=since)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
