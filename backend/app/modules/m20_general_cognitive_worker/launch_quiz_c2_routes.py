"""Unmounted C2 authenticated HTTP adapter. Integrator must mount router.

Uses verified tenant+actor as owner, never a caller-supplied owner field.
Single-process memory only. RLock serializes route operations. No cross-worker
persistence or UI is claimed. Core has no FastAPI dependency.
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
    identity = owner(tenant)
    p = request.payload
    try:
        with _lock:
            if request.operation == 'start':
                return _engine.start(identity, consent=p.get('consent'), as_of=p.get('as_of', 'unspecified'))
            if request.operation == 'answer':
                return _engine.answer(identity, request.session_id, p.get('question_id'), p.get('choice'), p.get('explanation'))
            if request.operation == 'documents':
                return _engine.documents(identity, request.session_id, p.get('documents'))
            if request.operation == 'edit':
                return _engine.edit(identity, request.session_id, p.get('key'), p.get('value'))
            if request.operation == 'plan':
                return _engine.plan(identity, request.session_id, p.get('task'), action=p.get('action', 'draft'))
            if request.operation == 'delete':
                return _engine.delete(identity, request.session_id)
            if request.operation == 'revoke':
                return _engine.revoke(identity, request.session_id)
            raise QuizError('FLEET_REFUSED_OPERATION')
    except QuizError as exc:
        raise HTTPException(400, str(exc)) from exc
    except (TypeError, KeyError) as exc:
        raise HTTPException(400, 'FLEET_REFUSED_INPUT') from exc


@router.get('/report')
def report(session_id: str, tenant: TenantContext = Depends(require_tenant)):
    try:
        with _lock:
            return _engine.profile(owner(tenant), session_id)
    except QuizError as exc:
        raise HTTPException(400, str(exc)) from exc
