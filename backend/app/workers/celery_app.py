import os
from celery import Celery

redis_url = os.getenv("ATLAS_REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("atlas", broker=redis_url, backend=redis_url, include=["app.workers.tasks"])
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "atlas.collection.*": {"queue": "collection"},
        "atlas.m13.*": {"queue": "browser"},
        "atlas.m12.*": {"queue": "ai"},
        "atlas.m15.*": {"queue": "documents"},
        "atlas.m10.*": {"queue": "default"},
        "atlas.m11.*": {"queue": "default"},
    },
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "dispatch-due-collection-sources": {
            "task": "atlas.collection.dispatch_due",
            "schedule": 60.0,
        },
        "expire-approval-requests": {
            "task": "atlas.approvals.expire",
            "schedule": 60.0,
        },
        "project-and-sweep-executive-dashboards": {
            "task": "atlas.m16.project_and_sweep",
            "schedule": 60.0,
        },
        "sync-and-execute-due-social-posts": {
            "task": "atlas.m06.sync_and_execute_due",
            "schedule": 60.0,
        },
        "drain-m22-install-jobs": {
            "task": "atlas.m22.drain_install_jobs",
            "schedule": 60.0,
        },
        "propose-due-m04-reruns": {
            "task": "atlas.m04.propose_due_reruns",
            "schedule": 900.0,
        },
        "draft-due-outreach-followups": {
            "task": "atlas.m05.draft_due_followups",
            "schedule": 3600.0,
        },
    },
)
