from fastapi import APIRouter
from .schemas import *
from .service import Service
router=APIRouter(prefix='/study-abroad',tags=['study-abroad']);service=Service()
@router.post('/identity-vector')
def identity(x:StudentProfileIn):return service.identity_vector(x)
@router.post('/essay-coaching',response_model=EssayCoachingOut)
def essay(x:EssayCoachingIn):return service.coach_essay(x)
class FitIn(BaseModel):profile:StudentProfileIn;universities:list[UniversityIn]
@router.post('/fit')
def fit(x:FitIn):return service.fit(x.profile,x.universities)

from fastapi import Depends,HTTPException
from app.auth.context import TenantContext,require_tenant
from .interview import IdentityInterviewRepository

def interview_repository(tenant:TenantContext=Depends(require_tenant)):
 return IdentityInterviewRepository(tenant.tenant_id)

@router.post('/identity-interviews',status_code=201)
def start_identity_interview(x:IdentityInterviewStartIn,repo:IdentityInterviewRepository=Depends(interview_repository)):
 return repo.start(x.track)

@router.get('/identity-interviews/{session_id}')
def get_identity_interview(session_id:str,repo:IdentityInterviewRepository=Depends(interview_repository)):
 try:return repo.get(session_id)
 except LookupError:raise HTTPException(404,'identity interview not found')

@router.post('/identity-interviews/{session_id}/turns')
def answer_identity_interview(session_id:str,x:IdentityInterviewTurnIn,repo:IdentityInterviewRepository=Depends(interview_repository)):
 try:return repo.answer(session_id,x.student_response,x.modality,x.evidence_tags)
 except LookupError:raise HTTPException(404,'identity interview not found')
 except ValueError as e:raise HTTPException(409,str(e))
