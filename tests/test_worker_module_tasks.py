from app.workers import tasks
from app.workers.celery_app import celery_app


def test_module_periodic_tasks_are_registered_with_beat():
    celery_app.loader.import_default_modules()
    assert "atlas.m16.project_and_sweep" in celery_app.tasks
    assert "atlas.m06.sync_and_execute_due" in celery_app.tasks
    configured = celery_app.conf.beat_schedule
    assert configured["project-and-sweep-executive-dashboards"]["schedule"] == 60.0
    assert configured["sync-and-execute-due-social-posts"]["schedule"] == 60.0


def test_dashboard_task_runs_every_discovered_tenant(monkeypatch):
    monkeypatch.setattr(tasks, "_tenant_ids_for", lambda *models: ["a", "b"])
    seen = []

    class Repo:
        def __init__(self, tenant, actor):
            seen.append((tenant, actor))

    class Service:
        def __init__(self, repo): pass
        def project(self): return {"projected_events": 2}
        def sweep_expired(self): return ["x"]

    monkeypatch.setattr("app.modules.m16_executive_dashboard.repository.SqlDashboardRepository", Repo)
    monkeypatch.setattr("app.modules.m16_executive_dashboard.service.Service", Service)
    assert tasks.project_and_sweep_dashboards.run() == {
        "tenants": 2, "projected_events": 4, "expired_approvals": 2,
    }
    assert seen == [("a", "celery-beat"), ("b", "celery-beat")]


def test_social_task_syncs_before_approved_effect_execution(monkeypatch):
    monkeypatch.setattr(tasks, "_tenant_ids_for", lambda *models: ["a"])
    calls = []

    class Repo:
        def __init__(self, tenant): calls.append(("repo", tenant))
    class Decisions: pass
    class Adapters: pass
    class Scheduler:
        def __init__(self, **kwargs): pass
        def sync_decisions(self): calls.append(("sync",)); return [1, 2]
        def execute_due(self): calls.append(("execute",)); return [1]

    monkeypatch.setattr("app.modules.m06_social_media_manager.sql_repository.SqlSocialRepository", Repo)
    monkeypatch.setattr("app.modules.m06_social_media_manager.routes._ApprovalCenterLookup", Decisions)
    monkeypatch.setattr("app.modules.m06_social_media_manager.routes._EnvAdapterFactory", Adapters)
    monkeypatch.setattr("app.modules.m06_social_media_manager.scheduler.Scheduler", Scheduler)
    assert tasks.sync_and_execute_due_social.run() == {"tenants": 1, "synced": 2, "published": 1}
    assert calls == [("repo", "a"), ("sync",), ("execute",)]


def test_followup_task_drafts_and_submits_each_message(monkeypatch):
    monkeypatch.setattr(tasks, "_tenant_ids_for", lambda *models: ["a"])
    calls = []

    class Repo:
        def __init__(self, tenant): calls.append(("repo", tenant))
    class Message:
        id = "original"
    class Followup:
        id = "followup"
    class Service:
        def __init__(self, *args): pass
        def due_follow_ups(self): return [Message()]
        async def draft_follow_up(self, message_id, generate):
            calls.append(("draft", message_id))
            return Followup()
        def submit_for_approval(self, message_id): calls.append(("review", message_id))

    monkeypatch.setattr("app.modules.m05_outreach_manager.sql_repository.SqlCampaignRepository", Repo)
    monkeypatch.setattr("app.modules.m05_outreach_manager.sql_repository.SqlContactRepository", Repo)
    monkeypatch.setattr("app.modules.m05_outreach_manager.campaigns.CampaignService", Service)
    assert tasks.draft_due_followups.run() == {
        "tenants": 1, "drafted": 1, "submitted_for_approval": 1,
    }
    assert calls == [("repo", "a"), ("repo", "a"), ("draft", "original"), ("review", "followup")]


def test_followup_beat_is_hourly_and_never_a_send_task():
    entry = celery_app.conf.beat_schedule["draft-due-outreach-followups"]
    assert entry == {"task": "atlas.m05.draft_due_followups", "schedule": 3600.0}
