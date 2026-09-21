from uuid import uuid4
from app.core.models import ApprovalRequest, GoalPlan, PlannedStep
from app.runtime.integration import Handoff
from app.modules.catalog import BY_ID
from app.core.approvals import approvals as approval_store

_KEYWORDS = {
    1: ("opportunity", "competition", "grant", "fellowship"),
    3: ("grant", "fellowship", "proposal"),
    4: ("research", "paper", "literature", "experiment"),
    5: ("outreach", "email", "contact", "professor"),
    14: ("build", "project", "prototype", "code"),
    15: ("document", "pdf", "report"),
    19: ("idea", "startup", "business"),
}

def plan_goal(goal: str, allow_external_action: bool = False) -> GoalPlan:
    text = goal.lower()
    selected = [mid for mid, keys in _KEYWORDS.items() if any(k in text for k in keys)] or [20]
    steps, approvals = [], []
    for mid in dict.fromkeys(selected):
        module = BY_ID[mid]
        external = mid in {5}
        handoff = Handoff(source_module=20, target_module=mid, operation="prepare_goal_work", payload={"goal": goal}, requires_approval=external)
        steps.append(PlannedStep(module_id=mid, module_name=module.name, action=f"Prepare work for: {goal}", requires_approval=external, operation=handoff.operation, payload=handoff.payload, evidence=handoff.evidence))
        if external:
            approvals.append(ApprovalRequest(id=str(uuid4()), module_id=mid, action_type="external_communication", payload={"goal": goal, "execution_enabled": allow_external_action}))
    approvals = [approval_store.put(request) for request in approvals]
    return GoalPlan(goal=goal, steps=steps, approval_requests=approvals)
