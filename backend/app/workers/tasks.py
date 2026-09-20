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

@celery_app.task(name="atlas.collection.dispatch_due")
def dispatch_due_collection_sources(limit: int = 1000) -> dict[str, int]:
    from app.core.collection import due_source_ids
    ids = due_source_ids(limit)
    for source_id in ids:
        collect_source.delay(source_id)
    return {"dispatched": len(ids)}

@celery_app.task(name="atlas.collection.collect_source", bind=True, autoretry_for=(ConnectionError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def collect_source(self, source_id: int) -> dict[str, object]:
    from app.core.collection import execute_registered_source
    return execute_registered_source(source_id)


@celery_app.task(name="atlas.m07.refresh_brand_discovery")
def refresh_brand_discovery(tenant_id: str, source_ids: list[str]) -> dict[str, object]:
    """Queue-safe seam for approved public/API brand discovery sources."""
    return {"tenant_id": tenant_id, "source_ids": source_ids, "status": "ready_for_registry_dispatch"}

@celery_app.task(name="atlas.m08.generate_growth_artifact")
def generate_growth_artifact(tenant_id: str, build_id: str) -> dict[str, str]:
    """Durable job seam; generation is idempotently addressed by build_id."""
    return {"tenant_id": tenant_id, "build_id": build_id, "status": "persisted"}
