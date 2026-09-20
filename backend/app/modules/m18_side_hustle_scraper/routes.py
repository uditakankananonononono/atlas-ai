from fastapi import APIRouter,Depends,HTTPException
from app.core.providers import generate
from .schemas import *
from .service import Service
router=APIRouter(prefix="/side-hustle-scraper",tags=["side-hustle-scraper"])
def get_service()->Service:return Service(generate=generate,collectors={})
@router.post("/blueprints",response_model=list[BlueprintOut])
async def discover(request:DiscoverIn,service:Service=Depends(get_service)):
 try:return await service.discover(request)
 except (ValueError,RuntimeError) as e:raise HTTPException(422,str(e))
@router.post("/feasibility",response_model=FeasibilityOut)
async def analyze(request:AnalyzeIn,service:Service=Depends(get_service)):return await service.analyze(request)
