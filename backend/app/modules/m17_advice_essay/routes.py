"""FastAPI routes for Module 17.

Authentication middleware must provide the owner UUID. The route dependency never
accepts owner identity from a request body or query string.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .schemas import (
    AdviceSource, AdviceTip, CommunicationCoachingRequest, CommunicationCoachingResponse,
    CollaborationCoachingRequest, CollaborationCoachingResponse,
    TrustWellbeingCoachingRequest, TrustWellbeingCoachingResponse,
    EssayBrief, EssayConcept, EssayCritique, IdentityMaterial,
)
from .service import AdviceEssayService


class CritiqueRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)
    draft: str = Field(min_length=1, max_length=50_000)


def build_router(
    service_provider: Callable[[], AdviceEssayService],
    owner_provider: Callable[[], UUID],
) -> APIRouter:
    router = APIRouter(prefix="/v1/modules/17", tags=["module-17"])
    @router.post("/trust-wellbeing/coaching", response_model=TrustWellbeingCoachingResponse)
    def coach_trust_wellbeing(request: TrustWellbeingCoachingRequest, service: AdviceEssayService = Depends(service_provider), owner_id: UUID = Depends(owner_provider)) -> TrustWellbeingCoachingResponse:
        _require_owner(owner_id, request.owner_id)
        return service.coach_trust_wellbeing(request)

    @router.post("/collaboration/coaching", response_model=CollaborationCoachingResponse)
    def coach_collaboration(request: CollaborationCoachingRequest, service: AdviceEssayService = Depends(service_provider), owner_id: UUID = Depends(owner_provider)) -> CollaborationCoachingResponse:
        _require_owner(owner_id, request.owner_id)
        return service.coach_collaboration(request)

    @router.post("/communication/coaching", response_model=CommunicationCoachingResponse)
    def coach_communication(request: CommunicationCoachingRequest, service: AdviceEssayService = Depends(service_provider), owner_id: UUID = Depends(owner_provider)) -> CommunicationCoachingResponse:
        _require_owner(owner_id, request.owner_id)
        return service.coach_communication(request)

    @router.post("/sources", response_model=AdviceSource, status_code=status.HTTP_201_CREATED)
    def add_source(source: AdviceSource, service: AdviceEssayService = Depends(service_provider), owner_id: UUID = Depends(owner_provider)) -> AdviceSource:
        _require_owner(owner_id, source.owner_id)
        return service.ingest_source(source)

    @router.post("/advice/compile", response_model=list[AdviceTip])
    def compile_advice(service: AdviceEssayService = Depends(service_provider), owner_id: UUID = Depends(owner_provider)) -> list[AdviceTip]:
        return service.compile_advice(owner_id)

    @router.post("/identity-materials", response_model=IdentityMaterial, status_code=status.HTTP_201_CREATED)
    def add_material(material: IdentityMaterial, service: AdviceEssayService = Depends(service_provider), owner_id: UUID = Depends(owner_provider)) -> IdentityMaterial:
        _require_owner(owner_id, material.owner_id)
        return service.add_identity_material(material)

    @router.post("/essay/concepts", response_model=list[EssayConcept])
    def create_concepts(brief: EssayBrief, service: AdviceEssayService = Depends(service_provider), owner_id: UUID = Depends(owner_provider)) -> list[EssayConcept]:
        _require_owner(owner_id, brief.owner_id)
        return service.create_concepts(brief)

    @router.post("/essay/critique", response_model=EssayCritique)
    def critique(request: CritiqueRequest, service: AdviceEssayService = Depends(service_provider), owner_id: UUID = Depends(owner_provider)) -> EssayCritique:
        return service.critique(owner_id, request.prompt, request.draft)

    return router


def _require_owner(authenticated_owner: UUID, resource_owner: UUID) -> None:
    if authenticated_owner != resource_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner mismatch")
