from fastapi import APIRouter,Depends,HTTPException,status
from .research_models import ResearchAnalysisRequest,ResearchArtifact
from .research_service import ResearchAnalysisService
router=APIRouter(prefix="/portfolio",tags=["idea-incubator-research-analysis"]);_service=ResearchAnalysisService()
def get_research_service():return _service
@router.post("/ideas/{idea_id}/research-analyses",response_model=ResearchArtifact,status_code=status.HTTP_201_CREATED)
def analyze_research(idea_id:str,data:ResearchAnalysisRequest,service:ResearchAnalysisService=Depends(get_research_service)):
 try:return service.analyze(idea_id,data)
 except ValueError as e:raise HTTPException(422,str(e)) from e
