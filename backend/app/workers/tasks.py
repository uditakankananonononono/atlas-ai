from app.workers.celery_app import celery_app

@celery_app.task(name="atlas.approvals.expire")
def expire_approval_requests() -> list[str]:
    from app.modules.m00_approval_center.service import default_service
    return default_service().expire_overdue()

@celery_app.task(name="atlas.modules.execute_approved")
def execute_approved_action(approval_id: str) -> dict[str, str]:
    """Worker seam. Dispatchers must verify approved state and a registered action handler."""
    from app.modules.m00_approval_center.service import default_service
    view = default_service().get(approval_id)
    if view["status"].value != "approved":
        raise ValueError("approval is not approved")
    return {"approval_id": approval_id, "status": "ready_for_registered_handler"}
