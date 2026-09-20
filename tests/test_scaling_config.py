from pathlib import Path

def test_prod_compose_partitions_queues_and_requires_secrets():
 text=Path("docker-compose.prod.yml").read_text()
 for queue in ("collection,default","ai,documents","browser"):assert f"-Q {queue}" in text
 for secret in ("ATLAS_TOKEN_KEY:?","POSTGRES_PASSWORD:?","REDIS_PASSWORD:?"):assert secret in text

def test_celery_has_late_ack_and_queue_routes():
 text=Path("backend/app/workers/celery_app.py").read_text();assert "task_acks_late=True" in text and '"queue": "browser"' in text
