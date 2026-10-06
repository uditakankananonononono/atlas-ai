"""HTTP boundary for Module 20 specialized-domain executive cognition."""
from __future__ import annotations
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from app.auth.context import TenantContext,require_tenant
from pydantic import BaseModel, ConfigDict, Field

from .specialized_domain import SpecializedDomainError, analyze_specialized_domain

router = APIRouter(prefix="/specialized-domain", tags=["m20-specialized-domain"])


class SpecializedDomainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    row_id: int = Field(ge=1310, le=1559)
    data: dict[str, Any]
    options: dict[str, Any] = Field(default_factory=dict)


class EvaluationResponse(BaseModel):
    status: str
    diagnostic_fields: list[str]
    human_review_required: bool
    externally_verified: bool


class UncertaintyResponse(BaseModel):
    level: str
    drivers: list[str]
    input_evidence_only: bool


class SpecializedDomainResponse(BaseModel):
    row_id: int
    domain: str
    capability: str
    tenant_id: str
    actor_id: str
    result: dict[str, Any]
    evaluation: EvaluationResponse
    uncertainty: UncertaintyResponse
    assumptions: list[str]
    limits: list[str]
    side_effects: list[str]


@router.post("/analyze", response_model=SpecializedDomainResponse)
def analyze(
    body: SpecializedDomainRequest,
    principal: TenantContext = Depends(require_tenant),
):
    try:
        return analyze_specialized_domain(
            row_id=body.row_id,
            data=body.data,
            options=body.options,
            tenant_id=principal.tenant_id,
            actor_id=principal.actor_id,
        ).to_dict()
    except (SpecializedDomainError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
