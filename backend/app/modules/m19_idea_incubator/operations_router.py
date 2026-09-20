from fastapi import APIRouter,Depends,HTTPException,status
from .operations_models import OperationsAnalysisRequest,OperationsArtifact
from .operations_service import OperationsAnalysisService
router=APIRouter(prefix="/portfolio",tags=["idea-incubator-operations-analysis"]);_service=OperationsAnalysisService()
def get_operations_service():return _service
@router.post("/ideas/{idea_id}/operations-analyses",response_model=OperationsArtifact,status_code=status.HTTP_201_CREATED)
def analyze_operations(idea_id:str,data:OperationsAnalysisRequest,service:OperationsAnalysisService=Depends(get_operations_service)):
 try:return service.analyze(idea_id,data)
 except ValueError as e:raise HTTPException(422,str(e)) from e
