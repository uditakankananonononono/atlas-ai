"""HTTP surface for the named-model catalog and free-first generation."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import model_catalog
from app.core.providers import ProviderError

router = APIRouter(prefix="/models", tags=["models"])


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    model_name: str | None = Field(default=None, max_length=80)


@router.get("/catalog")
def catalog() -> dict:
    return {"paid_allowed": model_catalog.paid_allowed(), "models": model_catalog.catalog_view()}


@router.post("/generate")
async def generate(body: GenerateRequest) -> dict:
    try:
        provider, model, text = await model_catalog.generate_free_first(body.prompt, body.model_name)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"provider": provider, "model": model, "text": text}


@router.get("/health")
async def health() -> dict:
    return {"paid_allowed": model_catalog.paid_allowed(), "providers": await model_catalog.health()}
