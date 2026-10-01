"""Authenticated finite-run surface. No client-selectable adapters or receipts."""
import json
import os
from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.auth.context import TenantContext, require_tenant
from app.modules.m00_approval_center.service import default_service
from app.modules.m13_browser_agent.session_bridge.dispatch import BridgedSessions
from app.modules.m13_browser_agent.session_bridge.routes import get_registry
from app.modules.m13_browser_agent.session_bridge.protocol import split_pc_session
from .login_runner import BrowserRecipe, LoginHustleRunner, LoginRunStore

router = APIRouter(prefix='/side-hustle-scraper/login-runs', tags=['side-hustle-login'])


def build_login_runner(*, store, sessions, approvals, recipes, receipt_key):
    """Shared production/test composition root. Dependencies are server-owned."""
    return LoginHustleRunner(store, sessions, approvals, recipes, receipt_key)


@lru_cache
def get_login_runner():
    key = os.environ.get('ATLAS_M18_RECEIPT_KEY', '').encode()
    if len(key) < 32:
        raise HTTPException(503, 'Login execution not configured: server receipt key required')
    try:
        installed = json.loads(os.environ.get('ATLAS_M18_BROWSER_RECIPES', '[]'))
        recipes = {r['platform']: BrowserRecipe(**r) for r in installed}
        if any(r.local_test for r in recipes.values()):
            raise ValueError('local fixture adapters may not be installed by environment')
        return build_login_runner(store=LoginRunStore(os.environ.get('ATLAS_M18_LOGIN_DB', 'atlas-m18-login.sqlite3')),
            sessions=BridgedSessions(get_registry()), approvals=default_service(), recipes=recipes, receipt_key=key)
    except (ValueError, TypeError) as error:
        raise HTTPException(503, 'Installed browser adapter configuration invalid') from error


class CreateIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    platform: str
    account: str
    session_id: str

    @field_validator('session_id')
    @classmethod
    def safe_session(cls, value):
        split_pc_session(value)
        return value


class PreviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    hypothesis: str = Field(min_length=1, max_length=2000)
    draft: str = Field(min_length=1, max_length=5000)
    max_minutes: int = Field(ge=1, le=120)


async def call(operation):
    try:
        return await operation
    except KeyError as error:
        raise HTTPException(404, 'Run not found') from error
    except (ValueError, PermissionError, RuntimeError) as error:
        raise HTTPException(409, str(error)) from error


@router.post('', status_code=201)
def create(body: CreateIn, t: TenantContext = Depends(require_tenant), runner=Depends(get_login_runner)):
    try:
        return runner.create(t.tenant_id, t.actor_id, **body.model_dump())
    except (ValueError, PermissionError) as error:
        raise HTTPException(409, str(error)) from error


@router.get('/{rid}')
def get(rid: str, t: TenantContext = Depends(require_tenant), runner=Depends(get_login_runner)):
    try:
        run = runner.store.get(t.tenant_id, rid)
        if run.get('receipt'):
            runner.verify_receipt(t.tenant_id, run)
        return run
    except KeyError as error:
        raise HTTPException(404, 'Run not found') from error
    except PermissionError as error:
        raise HTTPException(409, str(error)) from error


@router.post('/{rid}/discover')
async def discover(rid: str, t: TenantContext = Depends(require_tenant), runner=Depends(get_login_runner)):
    return await call(runner.discover(t.tenant_id, rid))


@router.post('/{rid}/preview')
async def preview(rid: str, body: PreviewIn, t: TenantContext = Depends(require_tenant), runner=Depends(get_login_runner)):
    return await call(runner.preview(t.tenant_id, rid, t.actor_id, **body.model_dump()))


@router.post('/{rid}/execute')
async def execute(rid: str, t: TenantContext = Depends(require_tenant), runner=Depends(get_login_runner)):
    return await call(runner.execute(t.tenant_id, rid, t.actor_id))


@router.post('/{rid}/reconcile')
async def reconcile(rid: str, t: TenantContext = Depends(require_tenant), runner=Depends(get_login_runner)):
    return await call(runner.reconcile(t.tenant_id, rid))


@router.post('/{rid}/receipts')
def reject_receipt(rid: str, t: TenantContext = Depends(require_tenant)):
    raise HTTPException(409, 'Client receipts cannot establish execution; use adapter readback')


@router.post('/{rid}/stop')
def stop(rid: str, t: TenantContext = Depends(require_tenant), runner=Depends(get_login_runner)):
    try:
        return runner.stop(t.tenant_id, rid, t.actor_id)
    except KeyError as error:
        raise HTTPException(404, 'Run not found') from error
    except PermissionError as error:
        raise HTTPException(409, str(error)) from error
