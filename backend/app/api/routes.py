from fastapi import APIRouter, HTTPException
from app.core.approvals import approvals
from app.core.models import ApprovalDecision, ApprovalRequest, GenerateRequest, GenerateResponse, GoalPlan, GoalRequest
from app.core.planner import plan_goal
from app.core.providers import ProviderError, generate
from app.modules.catalog import MODULES

router = APIRouter()

@router.get("/modules")
def list_modules() -> list[dict[str, object]]:
    return [module.__dict__ for module in MODULES]

@router.post("/goals/plan", response_model=GoalPlan)
def create_plan(request: GoalRequest) -> GoalPlan:
    return plan_goal(request.goal)

@router.get("/approvals", response_model=list[ApprovalRequest])
def list_approvals() -> list[ApprovalRequest]:
    return approvals.list()

@router.get("/approvals/{approval_id}/audit")
def approval_audit(approval_id: str) -> list[dict[str, str]]:
    events = approvals.audit(approval_id)
    if not events:
        raise HTTPException(status_code=404, detail="approval not found")
    return events

@router.post("/approvals/{approval_id}/decision", response_model=ApprovalRequest)
def decide_approval(approval_id: str, decision: ApprovalDecision) -> ApprovalRequest:
    try:
        updated = approvals.decide(approval_id, decision.decision)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if updated is None:
        raise HTTPException(status_code=404, detail="approval not found")
    return updated

@router.post("/ai/generate", response_model=GenerateResponse)
async def generate_text(request: GenerateRequest) -> GenerateResponse:
    try:
        model, text = await generate(request.prompt, request.provider, request.model)
    except ProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return GenerateResponse(provider=request.provider, model=model, text=text)
