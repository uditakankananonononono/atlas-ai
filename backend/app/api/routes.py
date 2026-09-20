from fastapi import APIRouter
from app.core.models import GoalPlan, GoalRequest
from app.core.planner import plan_goal
from app.modules.catalog import MODULES

router = APIRouter()

@router.get("/modules")
def list_modules() -> list[dict[str, object]]:
    return [module.__dict__ for module in MODULES]

@router.post("/goals/plan", response_model=GoalPlan)
def create_plan(request: GoalRequest) -> GoalPlan:
    """Plan only. External effects remain blocked behind explicit approval."""
    return plan_goal(request.goal, request.allow_external_action)
