"""Authenticated owner interview API; no route can execute an external action."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from app.core.database import SessionLocal
from .owner_interview import InterviewStore

router = APIRouter(prefix="/claire/interview", tags=["claire-interview"])


def store(t: TenantContext = Depends(require_tenant)) -> InterviewStore:
    return InterviewStore(t.tenant_id, t.actor_id, SessionLocal)


class ConsentIn(BaseModel):
    enabled: bool


class AnswerIn(BaseModel):
    question_id: str
    choice: str
    reason: str = Field(min_length=1, max_length=2000)
    source_reference: str = Field(min_length=1, max_length=240)


@router.put("/consent")
def consent(body: ConsentIn, s: InterviewStore = Depends(store)):
    return s.consent(body.enabled)


@router.get("/next")
def next_question(s: InterviewStore = Depends(store)):
    return s.next_question()


@router.post("/answers", status_code=201)
def answer(body: AnswerIn, s: InterviewStore = Depends(store)):
    try:
        return s.answer(body.question_id, body.choice, body.reason, body.source_reference)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/answers/{answer_id}")
def revoke(answer_id: int, s: InterviewStore = Depends(store)):
    if not s.revoke(answer_id):
        raise HTTPException(404, "answer not found")
    return {"revoked": True}


@router.get("/context")
def context(s: InterviewStore = Depends(store)):
    return s.context()


@router.delete("/answers")
def delete_all(s: InterviewStore = Depends(store)):
    return {"deleted": s.delete_all()}
