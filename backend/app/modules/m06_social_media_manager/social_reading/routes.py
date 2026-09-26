"""Routes for the social reading layer, mounted inside M06."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.context import TenantContext, require_tenant
from app.modules.m13_browser_agent.session_bridge.dispatch import BridgedSessions
from app.modules.m13_browser_agent.session_bridge.protocol import PlatformBlocked
from app.modules.m13_browser_agent.session_bridge.routes import get_registry
from app.modules.m19_idea_incubator.ledger import LedgerService
from app.modules.m19_idea_incubator.repository import SqlIdeaRepository

from .idea_feed import harvest_signals
from .knowledge import KnowledgeStore
from .reader import SocialReader

router = APIRouter(prefix="/social-media-manager/social-reading", tags=["social-reading"])
_store: KnowledgeStore | None = None


def get_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store


def get_reader() -> SocialReader:
    return SocialReader(BridgedSessions(get_registry()), get_store())


class ReadRunIn(BaseModel):
    platform: str = Field(pattern=r"^(instagram|linkedin)$")
    operation: str = Field(pattern=r"^(followers|following|connections|feed)$")
    session_id: str = Field(min_length=1, max_length=300, pattern=r"^pc\.[A-Za-z0-9_-]+\.[A-Za-z0-9_.-]+$")
    instagram_username: str = Field(default="", max_length=120)
    limit: int = Field(default=200, ge=1, le=500)


class HarvestIn(BaseModel):
    min_score: float = Field(default=0.25, ge=0.0, le=1.0)
    limit: int = Field(default=25, ge=1, le=100)


@router.post("/run", status_code=201)
async def run_read(body: ReadRunIn, tenant: TenantContext = Depends(require_tenant),
                   reader: SocialReader = Depends(get_reader)):
    try:
        return await reader.run(tenant.tenant_id, platform=body.platform,
                                operation=body.operation, session_id=body.session_id,
                                instagram_username=body.instagram_username, limit=body.limit)
    except PlatformBlocked as error:
        raise HTTPException(502, f"the platform stopped the read ({error.kind.value}): {error.detail}") from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/people")
def people(platform: str | None = None, limit: int = 200,
           tenant: TenantContext = Depends(require_tenant), store: KnowledgeStore = Depends(get_store)):
    return store.list_people(tenant.tenant_id, platform=platform, limit=limit)


@router.get("/people/{platform}/{handle}")
def person(platform: str, handle: str, tenant: TenantContext = Depends(require_tenant),
           store: KnowledgeStore = Depends(get_store)):
    view = store.get_person(tenant.tenant_id, platform, handle)
    if view is None:
        raise HTTPException(404, "person not found")
    return view


@router.get("/signals")
def signals(unharvested: bool = False, limit: int = 200,
            tenant: TenantContext = Depends(require_tenant), store: KnowledgeStore = Depends(get_store)):
    return store.list_signals(tenant.tenant_id, unharvested=unharvested, limit=limit)


@router.get("/runs")
def runs(limit: int = 50, tenant: TenantContext = Depends(require_tenant),
         store: KnowledgeStore = Depends(get_store)):
    return store.list_runs(tenant.tenant_id, limit=limit)


@router.post("/ideas/harvest", status_code=201)
def harvest(body: HarvestIn, tenant: TenantContext = Depends(require_tenant),
            store: KnowledgeStore = Depends(get_store)):
    ledger = LedgerService(SqlIdeaRepository(tenant.tenant_id), tenant.actor_id)
    return harvest_signals(store, ledger, tenant.tenant_id,
                           min_score=body.min_score, limit=body.limit)
