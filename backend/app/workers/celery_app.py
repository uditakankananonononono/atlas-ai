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
    beat_schedule={
        "expire-approval-requests": {
            "task": "atlas.approvals.expire",
            "schedule": 60.0,
        },
    },
)
