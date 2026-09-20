from app.workers.celery_app import celery_app

def test_real_worker_tasks_registered():
    celery_app.loader.import_default_modules()
    assert "atlas.approvals.expire" in celery_app.tasks
    assert "atlas.modules.execute_approved" in celery_app.tasks
    assert celery_app.conf.beat_schedule["expire-approval-requests"]["schedule"] == 60.0
