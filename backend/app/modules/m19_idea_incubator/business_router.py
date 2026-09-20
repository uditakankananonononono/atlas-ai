"""Mounted API boundary for evidence-bound business analyses (feature rows 360-399)."""
from fastapi import APIRouter,Depends,HTTPException,status
from .business_models import BusinessAnalysisRequest,BusinessArtifact
from .business_service import BusinessAnalysisService
router=APIRouter(prefix="/portfolio",tags=["idea-incubator-business-analysis"])
_service=BusinessAnalysisService()
def get_business_service():return _service
@router.post("/ideas/{idea_id}/business-analyses",response_model=BusinessArtifact,status_code=status.HTTP_201_CREATED)
def analyze_business(idea_id:str,data:BusinessAnalysisRequest,service:BusinessAnalysisService=Depends(get_business_service)):
 try:return service.analyze(idea_id,data)
 except ValueError as e:raise HTTPException(status_code=422,detail=str(e)) from e
