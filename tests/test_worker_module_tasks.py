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
        def __init__(self, *args, **kwargs): pass
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


def test_followup_worker_passes_actual_tenant_to_campaign_service(monkeypatch):
    from app.modules.m05_outreach_manager import campaigns,sql_repository
    from app.workers import tasks
    created=[]
    monkeypatch.setattr(tasks,"_tenant_ids_for",lambda *models:["owner-a","owner-b"])
    monkeypatch.setattr(sql_repository,"SqlCampaignRepository",lambda tenant:("campaigns",tenant))
    monkeypatch.setattr(sql_repository,"SqlContactRepository",lambda tenant:("contacts",tenant))
    class OwnerBoundService:
        def __init__(self,repo,contacts,approvals,tenant_id="local"):
            assert tenant_id==repo[1]==contacts[1], (tenant_id,repo,contacts)
            created.append(tenant_id)
        def due_follow_ups(self):return []
    monkeypatch.setattr(campaigns,"CampaignService",OwnerBoundService)
    assert tasks.draft_due_followups.run()=={"tenants":2,"drafted":0,"submitted_for_approval":0}
    assert created==["owner-a","owner-b"]


def test_followup_worker_real_campaign_service_binds_review_payload_to_tenant(monkeypatch):
    from datetime import datetime,timedelta,timezone
    from app.core import approvals as approval_module,providers
    from app.modules.m05_outreach_manager import campaigns,sql_repository
    from app.modules.m05_outreach_manager.service import InMemoryContactRepository,Service
    from app.modules.m05_outreach_manager.schemas import ContactCreate
    now=datetime.now(timezone.utc)
    class Sink:
        def __init__(self):self.calls=[]
        def put(self,item,**kwargs):self.calls.append((item,kwargs));return item
    sink=Sink();contacts=InMemoryContactRepository();repo=campaigns.InMemoryCampaignRepository()
    contact=Service(contacts,sink,None,tenant_id="owner-a").create_contact(ContactCreate(project_id="p",name="Fixture",email="fixture@example.test"))
    earlier=campaigns.CampaignService(repo,contacts,sink,tenant_id="owner-a",clock=lambda:now-timedelta(days=10))
    campaign=earlier.create_campaign(project_id="p",name="fixture",goal="fixture goal")
    draft=earlier.add_draft(campaign.id,contact.id,subject="Fixture",body="fixture text")
    earlier.submit_for_approval(draft.id);earlier.record_decision(draft.id,True);earlier.mark_sent(draft.id)
    sink.calls.clear()
    monkeypatch.setattr(tasks,"_tenant_ids_for",lambda *models:["owner-a"])
    monkeypatch.setattr(sql_repository,"SqlCampaignRepository",lambda tenant:repo)
    monkeypatch.setattr(sql_repository,"SqlContactRepository",lambda tenant:contacts)
    monkeypatch.setattr(approval_module,"approvals",sink)
    async def generate(*args):return "fixture","Subject: Following up\nFixture follow-up only."
    monkeypatch.setattr(providers,"generate",generate)
    assert tasks.draft_due_followups.run()=={"tenants":1,"drafted":1,"submitted_for_approval":1}
    item,kwargs=sink.calls[0]
    assert item.payload["tenant_id"]=="owner-a" and kwargs["user_id"]=="owner-a"
