"""Real native imports, Module 0 service, and file SQLite. No collector/network calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
import os

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core import discovery as d
from app.core.collection import CollectionSourceRow
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service, ApprovalRequestRow, ApprovalEventRow


@pytest.fixture
def native(tmp_path, monkeypatch):
    database_url = os.getenv('ATLAS_TEST_DATABASE_URL', f"sqlite:///{tmp_path / 'promotion.db'}")
    engine = create_engine(database_url, **({'connect_args': {'timeout': 20}} if database_url.startswith('sqlite:') else {}))
    if not database_url.startswith('sqlite:'):
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(d, 'SessionLocal', sessions)
    monkeypatch.setenv('ATLAS_PROMOTION_OWNERS_JSON', '{"a":"owner-a","b":"owner-b"}')
    service = Service(sessions)
    authority = d.NativePromotionApprovalAuthority(lambda tenant: 'owner-a' if tenant == 'a' else 'owner-b')
    with sessions.begin() as db:
        candidate = d.DiscoveryCandidateRow(tenant_id='a', platform='instagram',
            account_key='fixture-only', profile_url='https://example.test/fixture', evidence=[])
        db.add(candidate); db.flush(); cid = candidate.id
    yield sessions, service, authority, cid
    engine.dispose()


def snapshot(sessions):
    with sessions() as db:
        return {
            'candidates': [(x.id, x.status, x.reviewed_at) for x in db.scalars(select(d.DiscoveryCandidateRow))],
            'sources': [(x.id, x.enabled, x.config) for x in db.scalars(select(CollectionSourceRow))],
            'source_settings': [(x.id, x.collector_type, x.priority, x.cadence_seconds, x.cost_per_1000_requests_usd, x.daily_request_cap, x.next_run_at) for x in db.scalars(select(CollectionSourceRow))],
            'uses': [(x.approval_id, x.candidate_id, x.source_id) for x in db.scalars(select(d.CandidateApprovalUseRow))],
        }


def request(native):
    sessions, service, authority, cid = native
    return d.request_candidate_promotion('a', cid, approval_service=service)


def approve(native, aid, actor='owner-a'):
    native[1].decide(aid, ApprovalStatus.APPROVED, actor)


def test_no_record_and_no_authority_fail_closed(native):
    sessions, _, authority, cid = native
    before = snapshot(sessions)
    with pytest.raises(PermissionError): d.promote_candidate('a', cid)
    with pytest.raises(TypeError): d.promote_candidate('a', cid, approval_authority=authority)
    with pytest.raises(TypeError): d.promote_candidate('a', cid, approved=True)
    assert snapshot(sessions) == before


@pytest.mark.parametrize('mode', ['pending', 'denied', 'expired', 'revoked', 'wrong_tenant', 'wrong_owner',
                                 'wrong_action', 'wrong_hash', 'no_decision_event', 'no_expiry', 'missing_record'])
def test_invalid_decisions_leave_state_unchanged(native, mode):
    sessions, service, authority, cid = native
    aid = request(native)
    if mode == 'denied': service.decide(aid, ApprovalStatus.DENIED, 'owner-a')
    elif mode != 'pending': approve(native, aid, 'intruder' if mode == 'wrong_owner' else 'owner-a')
    with sessions.begin() as db:
        row = db.get(ApprovalRequestRow, aid)
        if mode == 'expired': row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        if mode == 'revoked': db.add(ApprovalEventRow(approval_id=aid, event='revoked', actor='owner-a', at=datetime.now(timezone.utc)))
        if mode == 'wrong_tenant': row.user_id = 'b'
        if mode == 'wrong_action': row.action_type = 'unrelated'
        if mode == 'wrong_hash': row.payload = {'scope_sha256': '0' * 64, 'approved': True}
        if mode == 'no_expiry': row.expires_at = None
        if mode == 'missing_record': db.delete(row)
        if mode == 'no_decision_event':
            db.execute(text("DELETE FROM m00_approval_events WHERE approval_id=:id AND event='approved'"), {'id': aid})
    before = snapshot(sessions)
    with pytest.raises(PermissionError): d.promote_candidate('a', cid)
    assert snapshot(sessions) == before


def test_valid_approval_enabled_once_and_tenant_isolation(native):
    sessions, _, authority, cid = native
    aid = request(native); approve(native, aid)
    before = snapshot(sessions)
    with pytest.raises(LookupError): d.promote_candidate('b', cid)
    assert snapshot(sessions) == before
    sid = d.promote_candidate('a', cid)
    after = snapshot(sessions)
    assert after['sources'] == [(sid, True, {'adapter': 'public_instagram', 'accounts': ['fixture-only']})]
    assert after['candidates'][0][1] == 'approved' and after['candidates'][0][2] is not None
    assert after['uses'] == [(aid, cid, sid)]
    with pytest.raises(PermissionError): d.promote_candidate('a', cid)
    assert snapshot(sessions) == after


def test_same_approval_race_has_one_winner(native):
    sessions, _, authority, cid = native
    aid = request(native); approve(native, aid)
    gate = Barrier(8)
    def promote():
        gate.wait()
        try: return ('ok', d.promote_candidate('a', cid))
        except PermissionError: return ('denied', None)
    with ThreadPoolExecutor(max_workers=8) as pool: results = list(pool.map(lambda _: promote(), range(8)))
    assert sum(r[0] == 'ok' for r in results) == 1
    state = snapshot(sessions)
    assert len(state['sources']) == len(state['uses']) == 1
    assert state['sources'][0][1] is True


def test_denied_race_leaves_state_unchanged(native):
    sessions, _, authority, cid = native
    request(native); before = snapshot(sessions)
    def promote(_):
        with pytest.raises(PermissionError): d.promote_candidate('a', cid)
    with ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(promote, range(8)))
    assert snapshot(sessions) == before


def test_binding_immutable_and_cannot_reuse_for_another_candidate(native):
    sessions, _, _, cid = native
    aid = request(native)
    for sql in ['UPDATE discovery_approval_bindings SET scope_sha256=:value WHERE candidate_id=:id',
                'DELETE FROM discovery_approval_bindings WHERE candidate_id=:id']:
        with pytest.raises(IntegrityError), sessions.begin() as db:
            db.execute(text(sql), {'value': 'f' * 64, 'id': cid})
    assert request(native) == aid  # identical pending request is idempotent
    with pytest.raises(IntegrityError), sessions.begin() as db:
        db.add(d.CandidateApprovalBindingRow(candidate_id=999, approval_id=aid, tenant_id='a', scope_sha256='f'*64, version=1, source_key='unused'))


def test_candidate_change_is_stale(native):
    sessions, _, authority, cid = native
    aid = request(native); approve(native, aid)
    with sessions.begin() as db: db.get(d.DiscoveryCandidateRow, cid).account_key = 'changed'
    before = snapshot(sessions)
    with pytest.raises(PermissionError, match='configuration changed'): d.promote_candidate('a', cid)
    assert snapshot(sessions) == before


@pytest.mark.parametrize('field', ['config', 'cadence_seconds', 'daily_request_cap', 'enabled'])
def test_existing_disabled_source_enabled_only_for_exact_reviewed_config(native, field):
    sessions, _, authority, cid = native
    with sessions.begin() as db:
        src = CollectionSourceRow(tenant_id='a', source_key='tracked:instagram', collector_type='public_page',
            priority=60, cadence_seconds=28800, enabled=False, daily_request_cap=3,
            cost_per_1000_requests_usd=0, config={'adapter': 'public_instagram', 'accounts': ['previous']},
            next_run_at=datetime.now(timezone.utc))
        db.add(src); db.flush(); sid=src.id
    aid = d.request_candidate_promotion('a', cid, approval_service=native[1], target_source_id=sid); approve(native, aid)
    with sessions.begin() as db:
        src = db.get(CollectionSourceRow, sid)
        setattr(src, field, {'adapter': 'public_instagram', 'accounts': ['changed']} if field == 'config' else
                True if field == 'enabled' else 99)
    before = snapshot(sessions)
    with pytest.raises(PermissionError): d.promote_candidate('a', cid)
    assert snapshot(sessions) == before


def test_existing_source_valid_approval(native):
    sessions, _, authority, cid = native
    with sessions.begin() as db:
        src = CollectionSourceRow(tenant_id='a', source_key='tracked:instagram', collector_type='public_page',
            priority=60, cadence_seconds=28800, enabled=False, daily_request_cap=3,
            cost_per_1000_requests_usd=0, config={'adapter': 'public_instagram', 'accounts': ['previous']},
            next_run_at=datetime.now(timezone.utc))
        db.add(src); db.flush(); sid=src.id
    aid = d.request_candidate_promotion('a', cid, approval_service=native[1], target_source_id=sid); approve(native, aid)
    assert d.promote_candidate('a', cid) == sid
    assert snapshot(sessions)['sources'] == [(sid, True, {'adapter':'public_instagram', 'accounts':['previous','fixture-only']})]


def test_rollback_when_authority_raises(native):
    sessions, _, _, cid = native
    request(native); before = snapshot(sessions)
    class FailingServerAuthority:
        def verify(self, db, *args):
            db.get(d.DiscoveryCandidateRow, cid).status = 'should-rollback'
            db.flush()
            raise RuntimeError('verification backend unavailable')
    with pytest.raises(RuntimeError): d._PromotionService(sessions, FailingServerAuthority()).promote('a', cid)
    assert snapshot(sessions) == before


def test_review_payload_drift_denied(native):
    sessions, _, authority, cid = native
    aid=request(native); approve(native, aid)
    with sessions.begin() as db:
        row=db.get(ApprovalRequestRow, aid)
        row.payload={**row.payload, 'scope': {'enabled': True, 'arbitrary':'changed'}}
    before=snapshot(sessions)
    with pytest.raises(PermissionError):d.promote_candidate('a',cid)
    assert snapshot(sessions)==before


def test_consumption_receipt_cannot_be_deleted_or_updated(native):
    sessions, _, authority, cid = native
    aid=request(native);approve(native,aid);d.promote_candidate('a',cid)
    for sql in ["DELETE FROM discovery_approval_uses", "UPDATE discovery_approval_uses SET source_id=999"]:
        with pytest.raises(IntegrityError), sessions.begin() as db:db.execute(text(sql))


def test_migration_sqlite_upgrade_immutability_and_downgrade(tmp_path):
    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('discovery_migration',
        Path(__file__).parents[1]/'migrations/versions/20261001_discovery_approval_binding.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine(f"sqlite:///{tmp_path/'migration.db'}")
    with engine.begin() as conn:
        migration.op=Operations(MigrationContext.configure(conn));migration.upgrade()
        conn.execute(text("INSERT INTO discovery_approval_bindings VALUES(1,'approval','tenant','hash')"))
        conn.execute(text("INSERT INTO discovery_approval_uses VALUES('approval',1,1,'2026-01-01')"))
        for table in ['discovery_approval_bindings','discovery_approval_uses']:
            with pytest.raises(IntegrityError):conn.execute(text(f'DELETE FROM {table}'))
        migration.downgrade()
        assert conn.scalar(text("SELECT count(*) FROM sqlite_master WHERE name='discovery_approval_bindings'"))==0
    engine.dispose()


def test_trusted_owner_directory_change_denies_old_actor(native, monkeypatch):
    sessions, _, _, cid = native
    aid=request(native);approve(native,aid)
    monkeypatch.setenv('ATLAS_PROMOTION_OWNERS_JSON', '{"a":"new-owner"}')
    before=snapshot(sessions)
    with pytest.raises(PermissionError):d.promote_candidate('a',cid)
    assert snapshot(sessions)==before


def test_different_candidate_race_cannot_overwrite_reviewed_source(native):
    sessions, service, authority, cid=native
    with sessions.begin() as db:
        other=d.DiscoveryCandidateRow(tenant_id='a',platform='instagram',account_key='second-fixture',
            profile_url='https://example.test/second',evidence=[])
        db.add(other);db.flush();other_id=other.id
    with sessions.begin() as db:
        source=CollectionSourceRow(tenant_id='a',source_key='explicit-shared-source',collector_type='public_page',
            priority=60,cadence_seconds=28800,enabled=False,daily_request_cap=3,
            cost_per_1000_requests_usd=0,config={'adapter':'public_instagram','accounts':[]},
            next_run_at=datetime.now(timezone.utc))
        db.add(source);db.flush();sid=source.id
    aid=d.request_candidate_promotion('a',cid,approval_service=service,target_source_id=sid);approve(native,aid)
    bid=d.request_candidate_promotion('a',other_id,approval_service=service,target_source_id=sid);approve(native,bid)
    barrier=Barrier(2)
    def promote(candidate_id):
        barrier.wait()
        try:return ('ok',d.promote_candidate('a',candidate_id))
        except PermissionError:return ('denied',None)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(promote,[cid,other_id]))
    assert sorted(r[0] for r in results)==['denied','ok']
    state=snapshot(sessions)
    assert len(state['sources'])==len(state['uses'])==1
    assert len(state['sources'][0][2]['accounts'])==1
    assert sorted(c[1] for c in state['candidates'])==['approved','pending_review']


def test_false_caller_payload_cannot_override_server_decision(native):
    sessions, _, authority, cid=native
    aid=request(native)
    with sessions.begin() as db:
        row=db.get(ApprovalRequestRow,aid);row.payload={**row.payload,'approved':True}
    before=snapshot(sessions)
    with pytest.raises(PermissionError):d.promote_candidate('a',cid)
    assert snapshot(sessions)==before
