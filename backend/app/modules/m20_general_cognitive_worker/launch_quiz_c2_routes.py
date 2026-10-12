"""C2 authenticated adapter; optional main-app mounting uses private SQLite.

The standalone router remains an in-memory adapter for explicit host binding.
Identity is always authenticated tenant plus actor, never payload identity.
"""
import json
from threading import RLock
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from .launch_quiz_c2 import LaunchQuiz, QuizError, shared_policy_hook

router = APIRouter(prefix='/api/v1/c31/launch-quiz', tags=['C2'])
_engine = LaunchQuiz(policy_hook=shared_policy_hook)
_lock = RLock()


class RunRequest(BaseModel):
    operation: str = Field(max_length=20)
    session_id: str = Field(default='', max_length=100)
    payload: dict = Field(default_factory=dict)


def owner(tenant):
    return json.dumps([tenant.tenant_id, tenant.actor_id], separators=(',', ':'))


@router.post('/run')
def run(request: RunRequest, tenant: TenantContext = Depends(require_tenant)):
    return _run(request, tenant, _engine, _lock)


def _run(request, tenant, engine, lock):
    identity = owner(tenant)
    p = request.payload
    try:
        with lock:
            if request.operation == 'start':
                return engine.start(identity, consent=p.get('consent'), as_of=p.get('as_of', 'unspecified'))
            if request.operation == 'answer':
                return engine.answer(identity, request.session_id, p.get('question_id'), p.get('choice'), p.get('explanation'))
            if request.operation == 'documents':
                return engine.documents(identity, request.session_id, p.get('documents'))
            if request.operation == 'edit':
                return engine.edit(identity, request.session_id, p.get('key'), p.get('value'))
            if request.operation == 'plan':
                return engine.plan(identity, request.session_id, p.get('task'), action=p.get('action', 'draft'))
            if request.operation == 'delete':
                return engine.delete(identity, request.session_id)
            if request.operation == 'revoke':
                return engine.revoke(identity, request.session_id)
            raise QuizError('FLEET_REFUSED_OPERATION')
    except QuizError as exc:
        raise HTTPException(400, str(exc)) from exc
    except (TypeError, KeyError) as exc:
        raise HTTPException(400, 'FLEET_REFUSED_INPUT') from exc


@router.get('/report')
def report(session_id: str, tenant: TenantContext = Depends(require_tenant)):
    return _report(session_id, tenant, _engine, _lock)


def _report(session_id, tenant, engine, lock):
    try:
        with lock:
            return engine.profile(owner(tenant), session_id)
    except QuizError as exc:
        raise HTTPException(400, str(exc)) from exc


def mount_launch_quiz(app, env=None):
    """Explicit opt-in. Enabled without valid private storage fails startup."""
    import os
    from .launch_quiz_c2_store import DurableLaunchQuiz
    env = os.environ if env is None else env
    if env.get('ATLAS_C2_ENABLED') != '1':
        return
    filename = env.get('ATLAS_C2_DB')
    if not filename:
        raise QuizError('FLEET_REFUSED_STORAGE')
    engine = DurableLaunchQuiz(filename)
    lock = RLock()
    mounted = APIRouter(prefix='/api/v1/c31/launch-quiz', tags=['C2'])
    @mounted.post('/run')
    def durable_run(request: RunRequest, tenant: TenantContext = Depends(require_tenant)):
        return _run(request, tenant, engine, lock)
    @mounted.get('/report')
    def durable_report(session_id: str, tenant: TenantContext = Depends(require_tenant)):
        return _report(session_id, tenant, engine, lock)
    app.include_router(mounted)
