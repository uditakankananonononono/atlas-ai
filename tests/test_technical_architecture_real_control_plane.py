import asyncio
import json
import logging
from datetime import datetime,timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import context as auth
from app.modules.m09_knowledge_workspace.lane_models import SourceRef
from app.modules.m09_knowledge_workspace.lane_service import KnowledgeWorkspace
from app.platform.integrations import APSchedulerService
from app.platform.middleware import ProductionBoundaryMiddleware


def test_a21_oidc_verifier_rejects_malformed_unsigned_and_missing_subject_tokens():
    verifier=auth.OIDCVerifier('https://issuer','atlas')
    for token in ('not-a-jwt','e30.e30.','eyJhbGciOiJub25lIiwia2lkIjoieCJ9.e30.'):
        with pytest.raises(Exception) as error:
            asyncio.run(verifier.verify(token))
        assert getattr(error.value,'status_code',401)==401


def test_a24_real_knowledge_audit_is_hash_chained_and_tamper_evident():
    from dataclasses import replace
    kb=KnowledgeWorkspace(clock=lambda:datetime(2026,9,22,tzinfo=timezone.utc),id_factory=iter(['d','e1','e2']).__next__)
    kb.create_document(document_id='doc',title='Atlas',content='one',actor_id='owner',source_refs=[SourceRef('https://source.test')])
    kb.update_document('doc',actor_id='owner',expected_version=1,content='two')
    events=kb.audit_history()
    assert kb.verify_audit_integrity() and events[1].previous_hash==events[0].event_hash
    kb.store._audit[0]=replace(events[0],action='tampered')
    assert not kb.verify_audit_integrity()


def test_a25_real_apscheduler_executes_registered_date_job():
    from apscheduler.schedulers.background import BackgroundScheduler
    ran=[];scheduler=BackgroundScheduler(timezone='UTC');service=APSchedulerService(scheduler)
    service.add('once',lambda:ran.append('done'),'date',run_date=datetime.now(timezone.utc))
    scheduler.start()
    import time
    deadline=time.time()+2
    while not ran and time.time()<deadline: time.sleep(.02)
    scheduler.shutdown(wait=True)
    assert ran==['done'] and scheduler.get_job('once') is None


def test_a30_real_gateway_rate_limits_and_returns_trace_header():
    app=FastAPI();app.add_middleware(ProductionBoundaryMiddleware,limit_per_minute=1)
    @app.get('/private')
    def private(): return {'ok':True}
    client=TestClient(app)
    headers={'x-atlas-tenant':'t','x-atlas-actor':'a'}
    first=client.get('/private',headers=headers);second=client.get('/private',headers=headers)
    assert first.status_code==200 and first.headers['traceparent']
    assert second.status_code==429 and second.json()=={'detail':'rate limit exceeded'}
    assert second.headers['traceparent']


def test_a32_real_approval_sse_route_has_streaming_media_and_proxy_headers():
    source=__import__('pathlib').Path('backend/app/modules/m00_approval_center/routes.py').read_text()
    assert 'StreamingResponse' in source and 'media_type="text/event-stream"' in source
    assert 'Cache-Control": "no-cache"' in source and 'X-Accel-Buffering": "no"' in source
    assert ': heartbeat\\n\\n' in source and 'data: {json.dumps(event)}\\n\\n' in source
