from fastapi import APIRouter,Depends,HTTPException
from app.core.approvals import approvals
from .schemas import DiscoveryIn,InstallIn
from .service import Service
router=APIRouter(prefix="/tools-hub",tags=["tools-hub"]);_service=None
def get_service():
 global _service
 if _service is None:_service=Service(approvals,[])
 return _service
@router.post("/discoveries")
async def discover(req:DiscoveryIn,s:Service=Depends(get_service)):return await s.discover(req.query)
@router.post("/installation-proposals",status_code=201)
def propose(req:InstallIn,s:Service=Depends(get_service)):
 try:return s.propose_install(req.candidate_id,req.adapter_type,req.config,req.requested_scopes)
 except KeyError as e:raise HTTPException(404,str(e))
 except ValueError as e:raise HTTPException(422,str(e))
@router.get("/portfolio")
def portfolio(s:Service=Depends(get_service)):return s.portfolio()
