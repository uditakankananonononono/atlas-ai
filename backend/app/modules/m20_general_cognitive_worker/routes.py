from fastapi import APIRouter,Depends,HTTPException
from app.core.approvals import approvals
from .schemas import GoalIn
from .service import Service
router=APIRouter(prefix="/general-cognitive-worker",tags=["general-cognitive-worker"])
_service=None
async def default_model(purpose,payload):
    if purpose=="htn_plan":return {"steps":[{"id":"understand","title":"Understand goal","risk":"read"}]}
    return {"summary":"reviewed","next":"none"}
def get_service():
    global _service
    if _service is None:_service=Service(approvals,default_model)
    return _service
@router.post("/runs",status_code=201)
async def create_run(request:GoalIn,service:Service=Depends(get_service)):
    run=await service.start(request.goal,request.constraints,request.budget)
    return {"id":run.id,"status":run.status,"plan_id":run.plan.id,"steps":[{"id":s.id,"title":s.title,"state":s.state,"approval_id":s.approval_id,"error":s.error} for s in run.plan.steps],"trace":[t.__dict__ for t in run.traces]}
@router.get("/runs/{run_id}")
def get_run(run_id:str,service:Service=Depends(get_service)):
    run=service.runs.get(run_id)
    if not run:raise HTTPException(404,"run not found")
    return {"id":run.id,"status":run.status,"steps":[s.__dict__ for s in run.plan.steps],"trace":[t.__dict__ for t in run.traces]}
