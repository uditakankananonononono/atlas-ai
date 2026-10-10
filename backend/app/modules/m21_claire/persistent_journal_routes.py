"""Authenticated persistent journal, separate from legacy process-local atomic routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.context import TenantContext, require_tenant
from app.core.database import SessionLocal
from .persistent_journal import PersistentJournal

router = APIRouter(prefix="/claire/journal", tags=["claire-journal"])

def store(t: TenantContext = Depends(require_tenant)) -> PersistentJournal:
    return PersistentJournal(t.tenant_id, t.actor_id, SessionLocal)

class DecisionIn(BaseModel):
    decision: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=1000)
    context: str = Field(default="", max_length=2000)
    source_reference: str = Field(min_length=1, max_length=240)

class CorrectionIn(BaseModel):
    original: str = Field(min_length=1, max_length=2000)
    corrected: str = Field(min_length=1, max_length=2000)
    context: str = Field(default="", max_length=2000)
    source_reference: str = Field(min_length=1, max_length=240)

@router.post("/decisions", status_code=201)
def capture(body: DecisionIn, s: PersistentJournal = Depends(store)):
    try:
        return s.capture(body.decision, body.reason, body.context, body.source_reference)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@router.post("/corrections", status_code=201)
def correction(body: CorrectionIn, s: PersistentJournal = Depends(store)):
    try:
        return s.correction(body.original, body.corrected, body.context, body.source_reference)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@router.get("/decisions")
def retrieve(query: str, limit: int = 5, s: PersistentJournal = Depends(store)):
    try:
        return {"hits": s.retrieve(query, limit)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@router.delete("/entries/{entry_id}")
def delete(entry_id: int, s: PersistentJournal = Depends(store)):
    if not s.delete(entry_id):
        raise HTTPException(404, "entry not found")
    return {"deleted": True}

@router.delete("/entries")
def delete_all(s: PersistentJournal = Depends(store)):
    return {"deleted": s.delete_all()}

@router.get('/decisions/bounded')
def retrieve_bounded(query:str,limit:int=5,scan_cap:int=500,kind:str='decision',after_id:int|None=None,before_id:int|None=None,s:PersistentJournal=Depends(store)):
    """Recent-ID window only, not global lexical top-k or consent."""
    try:return s.retrieve_bounded(query,limit=limit,scan_cap=scan_cap,kind=kind,after_id=after_id,before_id=before_id)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

from datetime import datetime

@router.get('/decisions/cursor')
def retrieve_cursor(query:str,limit:int=5,scan_cap:int=500,kind:str='decision',since:datetime|None=None,until:datetime|None=None,after_id:int|None=None,before_id:int|None=None,s:PersistentJournal=Depends(store)):
    """Newest-ID window, no full-match count or global lexical top-k."""
    try:return s.retrieve_cursor(query,limit=limit,scan_cap=scan_cap,kind=kind,since=since,until=until,after_id=after_id,before_id=before_id)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
