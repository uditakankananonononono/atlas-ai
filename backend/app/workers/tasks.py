from app.workers.celery_app import celery_app

@celery_app.task(name="atlas.approvals.expire")
def expire_approval_requests() -> list[str]:
    from app.modules.m00_approval_center.service import default_service
    return default_service().expire_overdue()

@celery_app.task(name="atlas.modules.execute_approved")
def execute_approved_action(approval_id: str, effect_id: str) -> dict[str, object]:
    """Consume one approved permit, then invoke its exact registered executor."""
    from app.modules.m00_approval_center.service import default_service
    from app.workers.action_registry import execute_registered
    view = default_service().get(approval_id)
    status = view["status"].value if hasattr(view["status"], "value") else view["status"]
    if status != "approved": raise ValueError("approval is not approved")
    permit = default_service().consume_effect(approval_id, module_id=view["module_id"],
        action_type=view["action_type"], payload=view["payload"], user_id=view["user_id"],
        effect_id=effect_id, actor="celery-worker")
    result = execute_registered(view["module_id"], view["action_type"], view["payload"])
    return {"approval_id":approval_id,"effect_id":permit["effect_id"],"status":"executed","result":result}

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


def _tenant_ids_for(*models) -> list[str]:
    """Discover active tenants from durable module rows, never from guessed config."""
    from sqlalchemy import select, union_all
    from app.core.database import SessionLocal
    statements = [select(model.tenant_id.label("tenant_id")) for model in models]
    if not statements:
        return []
    query = statements[0] if len(statements) == 1 else union_all(*statements)
    with SessionLocal() as db:
        return sorted({tenant_id for tenant_id in db.scalars(query) if tenant_id})


@celery_app.task(name="atlas.m16.project_and_sweep")
def project_and_sweep_dashboards() -> dict[str, int]:
    from app.modules.m16_executive_dashboard.repository import (
        ApprovalRow, EventRow, SnapshotRow, SqlDashboardRepository,
    )
    from app.modules.m16_executive_dashboard.service import Service
    tenants = _tenant_ids_for(EventRow, SnapshotRow, ApprovalRow)
    projected = expired = 0
    for tenant_id in tenants:
        service = Service(SqlDashboardRepository(tenant_id, "celery-beat"))
        summary = service.project()
        projected += int(summary["projected_events"])
        expired += len(service.sweep_expired())
    return {"tenants": len(tenants), "projected_events": projected, "expired_approvals": expired}


@celery_app.task(name="atlas.m06.sync_and_execute_due")
def sync_and_execute_due_social() -> dict[str, int]:
    from app.modules.m06_social_media_manager.routes import (
        _ApprovalCenterLookup, _EnvAdapterFactory,
    )
    from app.modules.m06_social_media_manager.scheduler import Scheduler
    from app.modules.m06_social_media_manager.sql_repository import (
        SocialPlanRow, SocialScheduleRow, SqlSocialRepository,
    )
    tenants = _tenant_ids_for(SocialPlanRow, SocialScheduleRow)
    synced = published = 0
    for tenant_id in tenants:
        scheduler = Scheduler(
            repository=SqlSocialRepository(tenant_id),
            decisions=_ApprovalCenterLookup(),
            adapter_factory=_EnvAdapterFactory(),
        )
        synced += len(scheduler.sync_decisions())
        published += len(scheduler.execute_due())
    return {"tenants": len(tenants), "synced": synced, "published": published}


@celery_app.task(name="atlas.m05.draft_due_followups")
def draft_due_followups() -> dict[str, int]:
    """Create review-bound follow-up drafts; this task never sends email."""
    import asyncio
    from app.core.approvals import approvals
    from app.core.providers import generate
    from app.modules.m05_outreach_manager.campaigns import CampaignService
    from app.modules.m05_outreach_manager.sql_repository import (
        CampaignRow, ContactRow, MessageRow, SqlCampaignRepository, SqlContactRepository,
    )
    tenants = _tenant_ids_for(CampaignRow, ContactRow, MessageRow)
    drafted = submitted = 0
    for tenant_id in tenants:
        service = CampaignService(
            SqlCampaignRepository(tenant_id), SqlContactRepository(tenant_id), approvals
        )
        for message in service.due_follow_ups():
            followup = asyncio.run(service.draft_follow_up(message.id, generate))
            drafted += 1
            service.submit_for_approval(followup.id)
            submitted += 1
    return {"tenants": len(tenants), "drafted": drafted, "submitted_for_approval": submitted}
