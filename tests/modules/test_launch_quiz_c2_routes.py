"""Mounted-in-isolation adapter checks. Not production mounting clearance."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker import launch_quiz_c2_routes as routes
from app.modules.m20_general_cognitive_worker.launch_quiz_c2 import LaunchQuiz


def client(monkeypatch):
    monkeypatch.setattr(routes, '_engine', LaunchQuiz())
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_authenticated_owner_isolation(monkeypatch, oidc_auth_headers):
    c = client(monkeypatch)
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH')
    a = oidc_auth_headers(tenant='tenant-a', subject='owner')
    b = oidc_auth_headers(tenant='tenant-a', subject='other')
    d = oidc_auth_headers(tenant='tenant-b', subject='owner')
    r = c.post('/api/v1/c31/launch-quiz/run', headers=a, json={'operation': 'start', 'payload': {'consent': True}})
    assert r.status_code == 200
    sid = r.json()['session_id']
    assert c.get('/api/v1/c31/launch-quiz/report', params={'session_id': sid}).status_code == 401
    for headers in (b, d):
        r = c.get('/api/v1/c31/launch-quiz/report', headers=headers, params={'session_id': sid})
        assert r.status_code == 400
        assert r.json()['detail'] == 'FLEET_REFUSED_OWNER'
    assert c.get('/api/v1/c31/launch-quiz/report', headers=a, params={'session_id': sid}).status_code == 200


def test_route_lifecycle_and_refusals(monkeypatch, oidc_auth_headers):
    c = client(monkeypatch)
    h = oidc_auth_headers(tenant='tenant-a', subject='owner')
    def run(operation, payload=None, sid=''):
        return c.post('/api/v1/c31/launch-quiz/run', headers=h, json={'operation': operation, 'session_id': sid, 'payload': payload or {}})
    assert run('start', {'consent': 'true'}).json()['detail'] == 'FLEET_REFUSED_NOCONSENT'
    sid = run('start', {'consent': True, 'as_of': '2026-10-11'}).json()['session_id']
    for key, choice in [('values', 'accuracy'), ('decision', 'evidence'), ('dilemma', 'compare'), ('writing', 'detailed')]:
        assert run('answer', {'question_id': key, 'choice': choice, 'explanation': 'Synthetic example.'}, sid).status_code == 200
    assert run('documents', {'documents': [{'id': 'd', 'text': 'Verify evidence', 'consent': True}]}, sid).status_code == 200
    assert run('edit', {'key': 'writing', 'value': 'concise'}, sid).status_code == 200
    r = run('plan', {'task': 'Design a tool'}, sid)
    assert r.status_code == 200
    assert r.json()['status'] == 'draft'
    assert r.json()['document_count'] == 1
    assert run('plan', {'task': 'Send', 'action': 'outreach'}, sid).json()['detail'] == 'POLICY_REFUSED_OUTREACH'
    assert run('bogus', {}, sid).status_code == 400
    assert run('edit', {'key': [], 'value': 'x'}, sid).status_code == 400
    assert run('revoke', {}, sid).json()['deleted'] is True
    assert c.get('/api/v1/c31/launch-quiz/report', headers=h, params={'session_id': sid}).json()['detail'] == 'FLEET_REFUSED_NOTFOUND'


def test_delete_route_isolated_lifecycle(monkeypatch, oidc_auth_headers):
    c = client(monkeypatch)
    h = oidc_auth_headers(tenant='delete-tenant', subject='owner')
    started = c.post('/api/v1/c31/launch-quiz/run', headers=h, json={
        'operation': 'start', 'payload': {'consent': True},
    })
    assert started.status_code == 200
    sid = started.json()['session_id']
    result = c.post('/api/v1/c31/launch-quiz/run', headers=h, json={
        'operation': 'delete', 'session_id': sid,
    })
    assert result.status_code == 200
    assert result.json() == {'deleted': True, 'session_id': sid}
    report = c.get('/api/v1/c31/launch-quiz/report', headers=h, params={'session_id': sid})
    assert report.status_code == 400
    assert report.json()['detail'] == 'FLEET_REFUSED_NOTFOUND'


def test_both_route_operations_own_lock_during_engine_call(monkeypatch, oidc_auth_headers):
    from threading import RLock
    c = client(monkeypatch)
    lock = RLock()
    monkeypatch.setattr(routes, '_lock', lock)
    calls = []
    original_start = routes._engine.start
    original_profile = routes._engine.profile
    def start(*args, **kwargs):
        assert lock._is_owned(), 'run route must hold lock before engine entry'
        calls.append('start')
        return original_start(*args, **kwargs)
    def profile(*args, **kwargs):
        assert lock._is_owned(), 'report route must hold lock before engine entry'
        calls.append('profile')
        return original_profile(*args, **kwargs)
    monkeypatch.setattr(routes._engine, 'start', start)
    monkeypatch.setattr(routes._engine, 'profile', profile)
    h = oidc_auth_headers(tenant='lock-tenant', subject='owner')
    r = c.post('/api/v1/c31/launch-quiz/run', headers=h, json={
        'operation': 'start', 'payload': {'consent': True},
    })
    assert r.status_code == 200
    sid = r.json()['session_id']
    assert c.get('/api/v1/c31/launch-quiz/report', headers=h, params={'session_id': sid}).status_code == 200
    assert calls == ['start', 'profile']


def test_controlled_concurrent_report_waits_for_run_lock(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, RLock, current_thread
    from app.auth.context import TenantContext
    first_entered = Event()
    release_first = Event()
    second_attempt = Event()
    second_entered = Event()
    real_lock = RLock()
    class ObservedLock:
        def __enter__(self):
            if current_thread().name.endswith('_1'):
                second_attempt.set()
            real_lock.acquire()
            return self
        def __exit__(self, *args):
            real_lock.release()
    monkeypatch.setattr(routes, '_lock', ObservedLock())
    engine = LaunchQuiz()
    monkeypatch.setattr(routes, '_engine', engine)
    tenant = TenantContext('concurrent-tenant', 'owner')
    sid = engine.start(routes.owner(tenant), consent=True)['session_id']
    original_question = engine.question
    original_profile = engine.profile
    def question(*args, **kwargs):
        first_entered.set()
        assert release_first.wait(5), 'test controller did not release first operation'
        return original_question(*args, **kwargs)
    def profile(*args, **kwargs):
        second_entered.set()
        return original_profile(*args, **kwargs)
    monkeypatch.setattr(engine, 'question', question)
    monkeypatch.setattr(engine, 'profile', profile)
    request = routes.RunRequest(operation='answer', session_id=sid, payload={
        'question_id': 'values', 'choice': 'accuracy', 'explanation': 'Synthetic.',
    })
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='c2lock') as pool:
        first = pool.submit(routes.run, request, tenant)
        try:
            assert first_entered.wait(5), 'first operation never entered engine'
            second = pool.submit(routes.report, sid, tenant)
            assert second_attempt.wait(5), 'second operation did not attempt route lock'
            assert not second_entered.is_set(), 'report entered engine while run held lock'
        finally:
            release_first.set()
        assert first.result(timeout=5)['id'] == 'decision'
        assert second.result(timeout=5)['answered_count'] == 1
        assert second_entered.is_set()
