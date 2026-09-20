from fastapi import APIRouter,Depends,HTTPException
from app.core.providers import generate
from .schemas import *
from .service import Service
router=APIRouter(prefix="/narrative-architect",tags=["narrative-architect"])
def get_service()->Service: return Service(generate=generate,collectors={})
@router.post("/advice",response_model=list[AdviceOut])
async def advice(request:CollectIn,service:Service=Depends(get_service)):
 try:return await service.collect(request)
 except (ValueError,RuntimeError) as e: raise HTTPException(422,str(e))
@router.post("/concepts",response_model=list[ConceptOut])
async def concepts(request:ConceptIn,service:Service=Depends(get_service)): return await service.concepts(request)
@router.post("/critique",response_model=CritiqueOut)
async def critique(request:CritiqueIn,service:Service=Depends(get_service)): return await service.critique(request)
