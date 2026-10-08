"""Tenant ownership guard for per-idea analysis routes."""
from fastapi import Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .repository import SqlIdeaRepository

def get_idea_repository(t:TenantContext=Depends(require_tenant))->SqlIdeaRepository:return SqlIdeaRepository(t.tenant_id)

def require_owned_idea(idea_id:str,repo:SqlIdeaRepository=Depends(get_idea_repository))->str:
 """404 unless the idea exists in the caller's tenant (same answer for missing and foreign ids)."""
 if repo.get_idea(idea_id) is None:raise HTTPException(404,"idea or experiment not found")
 return idea_id
