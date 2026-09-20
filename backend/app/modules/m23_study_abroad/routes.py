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
