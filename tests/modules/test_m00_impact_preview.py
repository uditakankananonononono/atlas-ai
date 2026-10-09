"""M00 approval impact preview: live-state drift blocks consumption."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center import impact, routes
from app.modules.m00_approval_center.service import ApprovalBroadcaster, ApprovalConflictError, Service

T0 = datetime(2026, 9, 24, 6, 0, tzinfo=timezone.utc)
PAYLOAD = {"thread_id": "t-1", "to": "prof@example.edu", "body": "Following up on the RA role"}


class Clock:
    now = T0
    def __call__(self):
        return self.now


@pytest.fixture
def world():
    """Stand-in external system the probe reads: a mail thread's live state."""
    return {"t-1": {"last_message_id": "m-3", "reply_count": 2, "subject": "RA role"}}


@pytest.fixture
def registry(world):
    reg = impact.ProbeRegistry()
    reg.register("send_*", lambda payload: dict(world[payload["thread_id"]]), module_id=5)
    return reg


@pytest.fixture
def service(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m00.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return Service(session_factory=sessionmaker(bind=engine, expire_on_commit=False),
                   broadcaster=ApprovalBroadcaster(), clock=Clock())


def _approved(service, registry, capture=True):
    view = service.submit(module_id=5, action_type="send_email", payload=PAYLOAD, user_id="udita")
    if capture:
        impact.capture_review_state(service, view["id"], registry=registry)
    service.decide(view["id"], ApprovalStatus.APPROVED, decided_by="udita")
    return view["id"]


def _consume(service, registry, aid, effect="mail-1"):
    return impact.consume_effect_checked(service, aid, module_id=5, action_type="send_email",
        payload=PAYLOAD, user_id="udita", effect_id=effect, actor="worker", registry=registry)


def test_unchanged_state_consumes_and_reports_hash(service, registry):
    aid = _approved(service, registry)
    preview = impact.impact_preview(service, aid, registry=registry)
    assert preview["verdict"] == "unchanged" and preview["safe_to_consume"] is True
    assert preview["effect"] == PAYLOAD
    permit = _consume(service, registry, aid)
    assert permit["allowed"] and permit["state_verdict"] == "unchanged"
    assert permit["state_hash"] == preview["reviewed"]["state_hash"]


def test_new_reply_after_review_blocks_the_send(service, registry, world):
    aid = _approved(service, registry)
    world["t-1"].update(last_message_id="m-4", reply_count=3)
    preview = impact.impact_preview(service, aid, registry=registry)
    assert preview["verdict"] == "drifted" and preview["safe_to_consume"] is False
    assert {d["path"] for d in preview["drift"]} == {"last_message_id", "reply_count"}
    with pytest.raises(impact.StateDriftError, match="re-review required"):
        _consume(service, registry, aid)
    events = [e["event"] for e in service.audit(aid)]
    assert events[-1] == "effect_blocked_drift" and "effect_consumed" not in events


def test_review_state_is_frozen_once_decided(service, registry):
    aid = _approved(service, registry)
    with pytest.raises(ApprovalConflictError, match="frozen"):
        impact.capture_review_state(service, aid, registry=registry)


def test_missing_probe_after_review_fails_closed(service, registry):
    aid = _approved(service, registry)
    with pytest.raises(ApprovalConflictError, match="cannot verify state"):
        _consume(service, impact.ProbeRegistry(), aid)


def test_no_snapshot_keeps_existing_behaviour(service, registry):
    aid = _approved(service, registry, capture=False)
    assert impact.impact_preview(service, aid, registry=registry)["verdict"] == "no_review_snapshot"
    assert _consume(service, registry, aid)["state_verdict"] == "no_review_snapshot"


def test_payload_tampering_still_rejected_by_hash(service, registry):
    aid = _approved(service, registry)
    with pytest.raises(ApprovalConflictError, match="does not match"):
        impact.consume_effect_checked(service, aid, module_id=5, action_type="send_email",
            payload={**PAYLOAD, "to": "attacker@example.test"}, user_id="udita",
            effect_id="mail-1", actor="worker", registry=registry)


def test_diff_handles_nested_lists_and_removals():
    changes = impact.diff({"a": {"b": [1, 2]}, "gone": 1}, {"a": {"b": [1, 3]}, "new": True})
    assert changes == [
        {"path": "a.b[1]", "change": "changed", "before": 2, "after": 3},
        {"path": "gone", "change": "removed", "before": 1},
        {"path": "new", "change": "added", "after": True},
    ]


def test_most_specific_probe_wins():
    reg = impact.ProbeRegistry()
    reg.register("*", lambda p: {"generic": True})
    reg.register("send_email", lambda p: {"specific": True}, module_id=5)
    assert reg.find(5, "send_email")[1]({}) == {"specific": True}
    assert reg.find(6, "send_email")[1]({}) == {"generic": True}


def test_http_preview_and_drift_409(service, registry, world, monkeypatch):
    monkeypatch.setattr(impact, "PROBES", registry)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_service] = lambda: service
    client = TestClient(app, headers={"x-atlas-tenant": "udita"})
    view = service.submit(module_id=5, action_type="send_email", payload=PAYLOAD, user_id="udita")
    captured = client.post(f"/approval-center/requests/{view['id']}/review-state",
                           json={"state": dict(world["t-1"])})
    assert captured.status_code == 200 and captured.json()["probe"] == "explicit"
    service.decide(view["id"], ApprovalStatus.APPROVED, decided_by="udita")
    world["t-1"]["reply_count"] = 5
    monkeypatch.setattr(routes, "impact_preview", lambda svc, aid: impact.impact_preview(svc, aid, registry=registry))
    monkeypatch.setattr(routes, "consume_effect_checked", lambda svc, aid, **k: impact.consume_effect_checked(svc, aid, registry=registry, **k))
    preview = client.get(f"/approval-center/requests/{view['id']}/impact-preview").json()
    assert preview["verdict"] == "drifted" and preview["drift"][0]["path"] == "reply_count"
    blocked = client.post(f"/approval-center/requests/{view['id']}/consume",
        json={"module_id": 5, "action_type": "send_email", "payload": PAYLOAD, "effect_id": "mail-9"})
    assert blocked.status_code == 409 and blocked.json()["detail"]["drift"][0]["after"] == 5
    other = TestClient(app, headers={"x-atlas-tenant": "someone-else"})
    assert other.get(f"/approval-center/requests/{view['id']}/impact-preview").status_code == 404


def test_structural_state_change_cannot_hide_behind_flattened_path_collision(service):
    world = {'state': {'a.b': 1}}
    registry = impact.ProbeRegistry()
    registry.register('send_email', lambda payload: world['state'], module_id=5)
    aid = _approved(service, registry)
    world['state'] = {'a': {'b': 1}}
    preview = impact.impact_preview(service, aid, registry=registry)
    assert preview['verdict'] == 'drifted'
    assert not preview['safe_to_consume']
    with pytest.raises(impact.StateDriftError):
        _consume(service, registry, aid)


def test_review_capture_probe_cannot_freeze_new_state_after_decision(service):
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    registry = impact.ProbeRegistry()
    def decide_during_probe(payload):
        service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
        return {'state': 'not shown at decision'}
    registry.register('send_email', decide_during_probe, module_id=5)
    with pytest.raises(ApprovalConflictError, match='frozen'):
        impact.capture_review_state(service, view['id'], registry=registry)
    with service._sessions() as db:
        assert db.get(impact.ApprovalReviewStateRow, view['id']) is None


def test_unreadable_live_probe_never_creates_permit(service, registry):
    aid = _approved(service, registry)
    broken = impact.ProbeRegistry()
    def fail(payload):
        raise RuntimeError('fixture unavailable')
    broken.register('send_email', fail, module_id=5)
    with pytest.raises(RuntimeError, match='unavailable'):
        _consume(service, broken, aid)
    assert 'effect_consumed' not in [e['event'] for e in service.audit(aid)]


@pytest.mark.parametrize('state', [[], 'invalid', 1])
def test_explicit_review_state_must_be_object(service, state):
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    with pytest.raises(ValueError, match='state'):
        impact.capture_review_state(service, view['id'], state=state)


def test_changed_probe_identity_cannot_reuse_review_snapshot(service):
    original = impact.ProbeRegistry()
    original.register('send_*', lambda payload: {'version': 1}, module_id=5)
    aid = _approved(service, original)
    replacement = impact.ProbeRegistry()
    replacement.register('send_email', lambda payload: {'version': 1}, module_id=5)
    with pytest.raises(impact.StateDriftError):
        _consume(service, replacement, aid)


@pytest.mark.parametrize('state', [{'value': float('nan')}, {'value': object()}])
def test_capture_refuses_nonjson_review_state(service, state):
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    with pytest.raises(ValueError, match='state'):
        impact.capture_review_state(service, view['id'], state=state)


def test_invalid_live_probe_state_cannot_be_reported_safe_without_snapshot(service):
    registry = impact.ProbeRegistry()
    registry.register('send_email', lambda payload: {'value': float('nan')}, module_id=5)
    aid = _approved(service, registry, capture=False)
    with pytest.raises(ValueError, match='state'):
        _consume(service, registry, aid)


def test_review_capture_http_nonfinite_state_maps_to_422(service):
    from app.auth.context import TenantContext, require_tenant
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_service] = lambda: service
    app.dependency_overrides[require_tenant] = lambda: TenantContext('udita', 'udita')
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    with TestClient(app) as client:
        response = client.post(f"/approval-center/requests/{view['id']}/review-state",
                               content='{"state":{"value":NaN}}', headers={'Content-Type': 'application/json'})
        assert response.status_code == 422


def test_capture_refuses_nonstring_state_keys(service):
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    with pytest.raises(ValueError, match='state'):
        impact.capture_review_state(service, view['id'], state={1: 'value'})


def test_corrupted_snapshot_state_cannot_use_unchanged_stored_hash(service, registry):
    aid = _approved(service, registry)
    with service._sessions.begin() as db:
        row = db.get(impact.ApprovalReviewStateRow, aid)
        row.state = {'corrupted': 'different'}
    with pytest.raises(impact.StateDriftError):
        _consume(service, registry, aid)


def test_bool_to_integer_review_state_is_structural_drift(service):
    world = {'value': True}
    registry = impact.ProbeRegistry()
    registry.register('send_email', lambda payload: dict(world), module_id=5)
    aid = _approved(service, registry)
    world['value'] = 1
    with pytest.raises(impact.StateDriftError):
        _consume(service, registry, aid)


def test_probe_cannot_mutate_nested_effect_payload_in_preview(service):
    payload = {'nested': {'recipient': 'reviewed@test'}}
    view = service.submit(module_id=5, action_type='send_email', payload=payload, user_id='udita')
    registry = impact.ProbeRegistry()
    def mutate(argument):
        argument['nested']['recipient'] = 'changed@test'
        return {'version': 1}
    registry.register('send_email', mutate, module_id=5)
    preview = impact.impact_preview(service, view['id'], registry=registry)
    assert preview['effect'] == payload


def test_literal_list_index_key_to_list_structure_blocks_consumption(service):
    world = {'state': {'a[0]': 1}}
    registry = impact.ProbeRegistry()
    registry.register('send_email', lambda payload: world['state'], module_id=5)
    aid = _approved(service, registry)
    world['state'] = {'a': [1]}
    with pytest.raises(impact.StateDriftError):
        _consume(service, registry, aid)


def test_capture_state_hash_matches_persisted_canonical_state(service):
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    impact.capture_review_state(service, view['id'], state={'list': [1, 2], 'nested': {'key': 'value'}})
    with service._sessions() as db:
        row = db.get(impact.ApprovalReviewStateRow, view['id'])
        assert row.state_hash == impact.state_hash(row.state)


def test_tuple_state_is_normalized_to_persisted_json_before_comparison(service):
    registry = impact.ProbeRegistry()
    registry.register('send_email', lambda payload: {'sequence': (1, 2)}, module_id=5)
    aid = _approved(service, registry)
    assert impact.impact_preview(service, aid, registry=registry)['verdict'] == 'unchanged'


def test_explicit_review_snapshot_can_match_registered_probe(service):
    registry = impact.ProbeRegistry()
    registry.register('send_email', lambda payload: {'value': 1}, module_id=5)
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    impact.capture_review_state(service, view['id'], state={'value': 1})
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    assert _consume(service, registry, view['id'])['state_verdict'] == 'unchanged'


def test_repeated_pending_snapshot_capture_retains_latest_review_state(service):
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    impact.capture_review_state(service, view['id'], state={'value': 1})
    impact.capture_review_state(service, view['id'], state={'value': 2})
    with service._sessions() as db:
        assert db.get(impact.ApprovalReviewStateRow, view['id']).state == {'value': 2}
    assert [e['event'] for e in service.audit(view['id'])] == ['created', 'review_state_captured', 'review_state_captured']


def test_capture_probe_that_crosses_deadline_cannot_persist_snapshot(service):
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita', ttl_seconds=1)
    registry = impact.ProbeRegistry()
    def slow(payload):
        service._clock.now = T0 + timedelta(seconds=2)
        return {'value': 1}
    registry.register('send_email', slow, module_id=5)
    with pytest.raises(ApprovalConflictError, match='expired'):
        impact.capture_review_state(service, view['id'], registry=registry)
    with service._sessions() as db:
        assert db.get(impact.ApprovalReviewStateRow, view['id']) is None


def test_malformed_probe_root_never_creates_permit(service):
    registry = impact.ProbeRegistry()
    registry.register('send_email', lambda payload: [], module_id=5)
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    with pytest.raises(TypeError, match='dict'):
        _consume(service, registry, view['id'])
    assert 'effect_consumed' not in [e['event'] for e in service.audit(view['id'])]


def test_probe_registry_refuses_empty_pattern():
    registry = impact.ProbeRegistry()
    with pytest.raises(ValueError, match='action_pattern'):
        registry.register('', lambda payload: {})


def test_probe_registry_refuses_noncallable_probe():
    registry = impact.ProbeRegistry()
    with pytest.raises(ValueError, match='probe'):
        registry.register('send_email', None)


def test_probe_registration_refuses_name_exceeding_snapshot_column():
    registry = impact.ProbeRegistry()
    with pytest.raises(ValueError, match='name'):
        registry.register('a'*201, lambda payload: {}, module_id=5)


def test_explicit_snapshot_input_mutation_does_not_change_stored_state(service):
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    state = {'nested': {'value': 1}}
    impact.capture_review_state(service, view['id'], state=state)
    state['nested']['value'] = 2
    with service._sessions() as db:
        assert db.get(impact.ApprovalReviewStateRow, view['id']).state == {'nested': {'value': 1}}


def test_probe_generated_name_valid_width_remains_supported():
    registry = impact.ProbeRegistry()
    registry.register('a'*198, lambda payload: {}, module_id=5)
    assert len(registry.find(5, 'a'*198)[0]) == 200


@pytest.mark.parametrize('module', [True, 5.0, 999999])
def test_probe_registry_requires_known_actual_module_identity(module):
    registry = impact.ProbeRegistry()
    with pytest.raises(ValueError, match='module_id'):
        registry.register('send_email', lambda payload: {}, module_id=module)


def test_concurrent_pending_captures_serialize_snapshot_and_audit(service):
    import concurrent.futures
    import threading
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    barrier = threading.Barrier(4)
    def capture(value):
        registry = impact.ProbeRegistry()
        def read(payload):
            barrier.wait(timeout=5)
            return {'value': value}
        registry.register('send_email', read, module_id=5)
        return impact.capture_review_state(service, view['id'], registry=registry)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(capture, range(4)))
    assert len(results) == 4
    with service._sessions() as db:
        row = db.get(impact.ApprovalReviewStateRow, view['id'])
        assert row.state in [{'value': value} for value in range(4)]
        assert row.state_hash == impact.state_hash(row.state)
        assert row.probe == '5:send_email'
    assert [e['event'] for e in service.audit(view['id'])].count('review_state_captured') == 4
    assert service.get(view['id'])['status'] == ApprovalStatus.PENDING


def test_preview_probe_output_is_detached_from_live_mapping(service):
    world = {'nested': {'value': 1}, 'sequence': (1, 2)}
    registry = impact.ProbeRegistry()
    registry.register('send_email', lambda payload: world, module_id=5)
    aid = _approved(service, registry)
    preview = impact.impact_preview(service, aid, registry=registry)
    assert preview['verdict'] == 'unchanged'
    assert preview['current']['state']['sequence'] == [1, 2]
    preview['current']['state']['nested']['value'] = 2
    assert world == {'nested': {'value': 1}, 'sequence': (1, 2)}
    world['nested']['value'] = 3
    assert preview['current']['state']['nested']['value'] == 2
    assert impact.impact_preview(service, aid, registry=registry)['verdict'] == 'drifted'


def test_preview_nested_probe_output_does_not_alias_external_mapping(service):
    world = {'nested': {'value': 1}}
    registry = impact.ProbeRegistry()
    registry.register('send_email', lambda payload: world, module_id=5)
    aid = _approved(service, registry)
    preview = impact.impact_preview(service, aid, registry=registry)
    preview['current']['state']['nested']['value'] = 2
    assert world == {'nested': {'value': 1}}


@pytest.mark.parametrize('failure', ['malformed', 'unavailable'])
def test_http_probe_failure_is_500_and_never_records_effect(service, monkeypatch, failure):
    from app.auth.context import TenantContext, require_tenant
    registry = impact.ProbeRegistry()
    def probe(payload):
        if failure == 'unavailable':
            raise RuntimeError('fixture unavailable')
        return []
    registry.register('send_email', probe, module_id=5)
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    monkeypatch.setattr(routes, 'impact_preview', lambda svc, aid: impact.impact_preview(svc, aid, registry=registry))
    monkeypatch.setattr(routes, 'consume_effect_checked', lambda svc, aid, **kw: impact.consume_effect_checked(svc, aid, registry=registry, **kw))
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_service] = lambda: service
    app.dependency_overrides[require_tenant] = lambda: TenantContext('udita', 'worker', frozenset({'owner'}))
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get(f"/approval-center/requests/{view['id']}/impact-preview").status_code == 500
        response = client.post(f"/approval-center/requests/{view['id']}/consume", json={
            'module_id': 5, 'action_type': 'send_email', 'payload': PAYLOAD, 'effect_id': 'failure-effect'})
        assert response.status_code == 500
    assert 'effect_consumed' not in [event['event'] for event in service.audit(view['id'])]


@pytest.mark.parametrize('iteration', range(3))
def test_concurrent_decision_capture_rejects_post_decision_overwrite(service, iteration):
    import concurrent.futures
    import threading
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    barrier = threading.Barrier(2)
    registry = impact.ProbeRegistry()
    def probe(payload):
        barrier.wait(timeout=5)
        return {'iteration': iteration}
    registry.register('send_email', probe, module_id=5)
    def capture():
        try:
            impact.capture_review_state(service, view['id'], registry=registry)
            return 'captured'
        except ApprovalConflictError:
            return 'frozen'
    def decide():
        barrier.wait(timeout=5)
        return service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        captured = pool.submit(capture)
        decided = pool.submit(decide)
        outcome = captured.result(timeout=10)
        assert decided.result(timeout=10)['status'] == ApprovalStatus.APPROVED
    events = [event['event'] for event in service.audit(view['id'])]
    assert events[-1] == 'approved'
    assert events.count('review_state_captured') == (1 if outcome == 'captured' else 0)
    with pytest.raises(ApprovalConflictError):
        impact.capture_review_state(service, view['id'], state={'overwrite': True})
    with service._sessions() as db:
        row = db.get(impact.ApprovalReviewStateRow, view['id'])
        assert (row is None) == (outcome == 'frozen')
        if row is not None:
            assert row.state == {'iteration': iteration}


def test_own_forced_decision_during_capture_probe(service):
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    registry = impact.ProbeRegistry()
    def probe(payload):
        service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
        return {'forced': True}
    registry.register('send_email', probe, module_id=5)
    with pytest.raises(ApprovalConflictError):
        impact.capture_review_state(service, view['id'], registry=registry)
    assert [e['event'] for e in service.audit(view['id'])] == ['created', 'approved']


def test_http_explicit_snapshot_missing_probe_refuses_consume_with_409(service, monkeypatch):
    from app.auth.context import TenantContext, require_tenant
    registry = impact.ProbeRegistry()
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD, user_id='udita')
    impact.capture_review_state(service, view['id'], state={'value': 1})
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    monkeypatch.setattr(routes, 'consume_effect_checked', lambda svc, aid, **kw: impact.consume_effect_checked(svc, aid, registry=registry, **kw))
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_service] = lambda: service
    app.dependency_overrides[require_tenant] = lambda: TenantContext('udita', 'worker', frozenset({'owner'}))
    with TestClient(app) as client:
        response = client.post(f"/approval-center/requests/{view['id']}/consume", json={
            'module_id': 5, 'action_type': 'send_email', 'payload': PAYLOAD, 'effect_id': 'missing-probe'})
    assert response.status_code == 409
    assert 'cannot verify state' in response.json()['detail']
    assert 'effect_consumed' not in [event['event'] for event in service.audit(view['id'])]


def test_preview_reviewed_mapping_mutation_does_not_alter_snapshot(service, registry):
    aid = _approved(service, registry)
    preview = impact.impact_preview(service, aid, registry=registry)
    preview['reviewed']['state']['reply_count'] = 99
    preview['effect']['thread_id'] = 'changed'
    again = impact.impact_preview(service, aid, registry=registry)
    assert again['verdict'] == 'unchanged'
    assert again['reviewed']['state']['reply_count'] == 2
    assert again['effect']['thread_id'] == 't-1'


def test_capture_exact_expiration_boundary_refuses_snapshot(service):
    view = service.submit(module_id=5, action_type='send_email', payload=PAYLOAD,
                          user_id='udita', ttl_seconds=1)
    service._clock.now = T0 + timedelta(seconds=1)
    with pytest.raises(ApprovalConflictError):
        impact.capture_review_state(service, view['id'], state={'value': 1})
    with service._sessions() as db:
        assert db.get(impact.ApprovalReviewStateRow, view['id']) is None
    assert [event['event'] for event in service.audit(view['id'])] == ['created', 'expired']


def test_cross_request_effect_id_conflict_leaves_loser_unconsumed(service, registry):
    first = _approved(service, registry)
    second = _approved(service, registry)
    assert _consume(service, registry, first, effect='global-effect')['allowed']
    with pytest.raises(ApprovalConflictError, match='effect id'):
        _consume(service, registry, second, effect='global-effect')
    assert [event['event'] for event in service.audit(second)] == ['created', 'review_state_captured', 'approved']
    assert _consume(service, registry, second, effect='separate-effect')['allowed']


def test_http_explicit_capture_missing_request_returns_404(service):
    from app.auth.context import TenantContext, require_tenant
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_service] = lambda: service
    app.dependency_overrides[require_tenant] = lambda: TenantContext('udita', 'udita')
    with TestClient(app) as client:
        assert client.post('/approval-center/requests/missing/review-state',
                           json={'state': {'value': 1}}).status_code == 404


def test_worker_same_effect_retry_returns_persisted_outcome_once(service, monkeypatch):
    from app.workers import action_registry
    from app.workers.tasks import execute_approved_action
    monkeypatch.setattr(action_registry, '_EXECUTORS', {})
    monkeypatch.setattr('app.modules.m00_approval_center.service.default_service', lambda: service)
    view = service.submit(module_id=5, action_type='fixture_repeat', payload={'value': 1}, user_id='udita')
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    calls = []
    def local_executor(payload):
        calls.append(dict(payload))
        return {'call': len(calls)}
    action_registry.register_executor(5, 'fixture_repeat', local_executor)
    first = execute_approved_action.run(view['id'], 'repeat-effect')
    second = execute_approved_action.run(view['id'], 'repeat-effect')
    assert first['result']['call'] == 1 and second['result']['call'] == 1
    assert calls == [{'value': 1}]
    assert [event['event'] for event in service.audit(view['id'])].count('effect_consumed') == 1


def test_worker_missing_executor_refuses_before_permit(service, monkeypatch):
    from app.workers import action_registry
    from app.workers.tasks import execute_approved_action
    monkeypatch.setattr(action_registry, '_EXECUTORS', {})
    monkeypatch.setattr('app.modules.m00_approval_center.service.default_service', lambda: service)
    view = service.submit(module_id=5, action_type='fixture_missing_executor', payload={}, user_id='udita')
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    with pytest.raises(LookupError, match='no approved-action executor'):
        execute_approved_action.run(view['id'], 'missing-executor-effect')
    assert [event['event'] for event in service.audit(view['id'])] == ['created', 'approved']


def test_worker_failed_executor_is_unknown_and_retry_held(service, monkeypatch):
    from app.workers import action_registry
    from app.workers.tasks import execute_approved_action
    monkeypatch.setattr(action_registry, '_EXECUTORS', {})
    monkeypatch.setattr('app.modules.m00_approval_center.service.default_service', lambda: service)
    view = service.submit(module_id=5, action_type='fixture_failing_executor', payload={}, user_id='udita')
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    calls = []
    def local_executor(payload):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError('fixture after local effect')
        return {'call': len(calls)}
    action_registry.register_executor(5, 'fixture_failing_executor', local_executor)
    with pytest.raises(RuntimeError, match='fixture'):
        execute_approved_action.run(view['id'], 'failed-effect')
    with pytest.raises(ApprovalConflictError, match='unknown'):
        execute_approved_action.run(view['id'], 'failed-effect')
    assert len(calls) == 1
    assert [event['event'] for event in service.audit(view['id'])].count('effect_consumed') == 1


def test_drift_block_audit_actor_is_not_validated_before_write(service, registry, world):
    aid = _approved(service, registry)
    world['t-1']['reply_count'] += 1
    with pytest.raises(impact.StateDriftError):
        impact.consume_effect_checked(service, aid, module_id=5, action_type='send_email',
                                      payload=PAYLOAD, user_id='udita', effect_id='fixture',
                                      actor='a'*121, registry=registry)
    event = service.audit(aid)[-1]
    assert event['event'] == 'effect_blocked_drift' and len(event['actor']) == 121


def test_worker_malformed_result_is_unknown_and_retry_held(service, monkeypatch):
    from app.workers import action_registry
    from app.workers.tasks import execute_approved_action
    monkeypatch.setattr(action_registry, '_EXECUTORS', {})
    monkeypatch.setattr('app.modules.m00_approval_center.service.default_service', lambda: service)
    view = service.submit(module_id=5, action_type='fixture_bad_result', payload={}, user_id='udita')
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    calls = []
    def local_executor(payload):
        calls.append(1)
        return None if len(calls) == 1 else {'call': len(calls)}
    action_registry.register_executor(5, 'fixture_bad_result', local_executor)
    with pytest.raises(TypeError, match='mapping'):
        execute_approved_action.run(view['id'], 'malformed-effect')
    with pytest.raises(ApprovalConflictError, match='unknown'):
        execute_approved_action.run(view['id'], 'malformed-effect')
    assert len(calls) == 1
    assert [event['event'] for event in service.audit(view['id'])].count('effect_consumed') == 1
