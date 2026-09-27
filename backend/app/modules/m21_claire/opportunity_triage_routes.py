"""Authenticated read-only opportunity triage."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .opportunity_triage import triage

router = APIRouter(prefix="/claire/opportunities", tags=["claire-opportunities"])

class TriageIn(BaseModel):
    platform_ids: list[str] = Field(min_length=1, max_length=5)
    query: str = Field(min_length=1, max_length=200)
    per_platform: int = Field(default=10, ge=1, le=25)

@router.post("/triage")
def run(body: TriageIn, tenant: TenantContext = Depends(require_tenant)):
    try:
        return triage(body.platform_ids, body.query, per_platform=body.per_platform)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
