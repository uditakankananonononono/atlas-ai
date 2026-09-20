from fastapi import APIRouter,Depends,HTTPException
from app.core.approvals import approvals
from app.modules.m20_general_cognitive_worker.routes import get_service as cognitive_service
from .schemas import GoalIn,EnvironmentChangeIn
from .service import Service
router=APIRouter(prefix="/claire",tags=["claire"]);_service=None
def get_service():
 global _service
 if _service is None:_service=Service(cognitive_service(),approvals)
 return _service
@router.post("/goals",status_code=201)
def intake(req:GoalIn,s:Service=Depends(get_service)):
 try:return s.intake(req.goal,req.acceptance,req.limits)
 except ValueError as e:raise HTTPException(422,str(e))
@router.post("/goals/{goal_id}/realize")
async def realize(goal_id:str,s:Service=Depends(get_service)):
 try:return await s.realize(goal_id)
 except KeyError:raise HTTPException(404,"goal not found")
@router.post("/goals/{goal_id}/environment-changes",status_code=201)
def environment_change(goal_id:str,req:EnvironmentChangeIn,s:Service=Depends(get_service)):
 if goal_id not in s.goals:raise HTTPException(404,"goal not found")
 try:return s.request_environment_change(goal_id,req.operation,req.preview)
 except ValueError as e:raise HTTPException(422,str(e))
