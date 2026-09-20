from fastapi import APIRouter,Depends,HTTPException
from app.core.approvals import approvals
from app.core.providers import generate
from app.core.models import ApprovalRequest
from .schemas import *
from .service import Service
router=APIRouter(prefix="/idea-incubator",tags=["idea-incubator"]);_service=None
def get_service()->Service:
 global _service
 if _service is None:_service=Service(generate=generate,approval_store=approvals)
 return _service
@router.post("/ideas",response_model=RunOut,status_code=201)
async def intake(request:IntakeIn,service:Service=Depends(get_service)):return await service.intake(request)
@router.get("/ideas/{run_id}",response_model=RunOut)
def get(run_id:str,service:Service=Depends(get_service)):
 try:return service.get(run_id)
 except KeyError as e:raise HTTPException(404,"idea not found") from e
@router.post("/ideas/{run_id}/preview",response_model=ApprovalRequest,status_code=201)
def preview(run_id:str,request:PreviewIn,service:Service=Depends(get_service)):
 try:return service.request_preview(run_id,request)
 except KeyError as e:raise HTTPException(404,"idea not found") from e
 except ValueError as e:raise HTTPException(409,str(e)) from e
@router.post("/packages",response_model=PackageOut)
async def package(request:PackageIn,service:Service=Depends(get_service)):
 try:return await service.package(request)
 except KeyError as e:raise HTTPException(404,"idea not found") from e
