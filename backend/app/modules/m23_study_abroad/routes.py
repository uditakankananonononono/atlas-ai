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

from .advising import AdvisingService
def advising_service(tenant:TenantContext=Depends(require_tenant)):return AdvisingService(tenant.tenant_id)
@router.post('/major-mentor')
def major_mentor(x:MajorMentorIn,s:AdvisingService=Depends(advising_service)):return s.major_mentor(x.profile,x.majors)
@router.post('/school-match')
def school_match(x:SchoolMatchIn,s:AdvisingService=Depends(advising_service)):return s.school_match(x.profile,x.schools)
@router.post('/activity-plan')
def activity_plan(x:ActivityPlannerIn,s:AdvisingService=Depends(advising_service)):return s.activity_plan(x.profile,x.activities,x.weekly_hours)
@router.post('/passion-projects')
def passion_projects(x:PassionProjectIn,s:AdvisingService=Depends(advising_service)):return s.passion_projects(x.profile,x.constraints,x.ideas)
@router.get('/advising-history')
def advising_history(kind:str|None=None,s:AdvisingService=Depends(advising_service)):return s.history(kind)

from .essay_tools import EssayToolService
essay_tools=EssayToolService()
@router.post('/essay-tools/topics')
def essay_topics(x:TopicFinderIn):return essay_tools.topic_finder(x.prompt,x.evidence)
@router.post('/essay-tools/outline')
def essay_outline(x:OutlineCoachIn):return essay_tools.outline(x.prompt,x.student_thesis,x.evidence)
@router.post('/essay-tools/hook')
def essay_hook(x:HookCoachIn):return essay_tools.hook_coach(x.student_hook,x.evidence)
@router.post('/essay-tools/conclusion')
def essay_conclusion(x:ConclusionCoachIn):return essay_tools.conclusion_coach(x.student_conclusion,x.thesis)
@router.post('/essay-tools/clarity')
def essay_clarity(x:ClarityReviewIn):return essay_tools.clarity_review(x.draft)
