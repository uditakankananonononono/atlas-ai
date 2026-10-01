"""Real native services and durable SQLite, without model or network stubs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
import inspect
import pytest
from sqlalchemy import select, text
from app.core import discovery as d
from app.core.collection import CollectionSourceRow
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import ApprovalRequestRow, ApprovalEventRow, ApprovalConflictError
from test_discovery_promotion_approval_native import native, snapshot, request, approve


def test_public_fake_authority_rejected(native):
    sessions, service, _, cid = native
    request(native)
    class Yes:
        def verify(self, db, approval_id, tenant_id, scope, now):
            return d.VerifiedPromotionDecision(approval_id, tenant_id, scope, now+timedelta(hours=1))
    before = snapshot(sessions)
    assert list(inspect.signature(d.promote_candidate).parameters) == ['tenant_id', 'candidate_id']
    with pytest.raises(TypeError): d.promote_candidate('a', cid, approval_authority=Yes())
    with pytest.raises(PermissionError): d.promote_candidate('a', cid)
    assert snapshot(sessions) == before


@pytest.mark.parametrize('terminal', ['denied', 'expired', 'revoked'])
def test_new_attempt_after_terminal(native, terminal):
    sessions, service, _, cid = native
    aid = request(native)
    if terminal == 'denied': service.decide(aid, ApprovalStatus.DENIED, 'owner-a')
    elif terminal == 'revoked':
        approve(native, aid); service.revoke(aid, tenant_id='a', revoked_by='owner-a')
    else:
        with sessions.begin() as db:
            db.get(ApprovalRequestRow, aid).expires_at = datetime.now(timezone.utc)-timedelta(seconds=1)
    with pytest.raises(PermissionError): d.promote_candidate('a', cid)
    bid = request(native)
    assert bid != aid
    with sessions() as db:
        bindings = list(db.scalars(select(d.CandidateApprovalBindingRow).order_by(d.CandidateApprovalBindingRow.version)))
        assert [(b.approval_id, b.version) for b in bindings] == [(aid, 1), (bid, 2)]
    # Even a forged old approved decision does not authorize the new attempt.
    with sessions.begin() as db:
        old = db.get(ApprovalRequestRow, aid)
        old.status='approved'; old.approved_by='owner-a'; old.decided_at=datetime.now(timezone.utc)
        old.expires_at=datetime.now(timezone.utc)+timedelta(hours=1)
        db.add(ApprovalEventRow(approval_id=aid,event='approved',actor='owner-a',at=datetime.now(timezone.utc)))
    with pytest.raises(PermissionError): d.promote_candidate('a', cid)
    approve(native, bid)
    sid = d.promote_candidate('a', cid)
    with sessions() as db:
        assert db.get(d.CandidateApprovalUseRow, aid) is None
        assert db.get(d.CandidateApprovalUseRow, bid).source_id == sid
    with pytest.raises(PermissionError): d.promote_candidate('a', cid)
    assert request(native) == bid


def test_distinct_same_platform_accounts(native):
    sessions, service, _, cid = native
    with sessions.begin() as db:
        other = d.DiscoveryCandidateRow(tenant_id='a',platform='instagram',account_key='account-two',
            profile_url='https://example.test/second',evidence=[])
        db.add(other); db.flush(); second=other.id
    aid=request(native); approve(native,aid)
    bid=d.request_candidate_promotion('a',second,approval_service=service); approve(native,bid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids=list(pool.map(lambda c:d.promote_candidate('a',c), [cid,second]))
    assert len(set(ids)) == 2
    with sessions() as db:
        sources=list(db.scalars(select(CollectionSourceRow)))
        assert len({s.source_key for s in sources}) == 2
        assert sorted(s.config['accounts'] for s in sources)==[['account-two'],['fixture-only']]


def test_concurrent_retry_one_attempt_no_orphans(native):
    sessions,service,_,cid=native
    aid=request(native); service.decide(aid,ApprovalStatus.DENIED,'owner-a')
    gate=Barrier(12)
    def retry(_):
        gate.wait()
        return request(native)
    with ThreadPoolExecutor(max_workers=12) as pool: ids=list(pool.map(retry,range(12)))
    assert len(set(ids))==1 and ids[0]!=aid
    assert request(native)==ids[0]
    with sessions() as db:
        approvals=list(db.scalars(select(ApprovalRequestRow)))
        bindings=list(db.scalars(select(d.CandidateApprovalBindingRow)))
        assert len(approvals)==len(bindings)==2
        assert {a.id for a in approvals}=={b.approval_id for b in bindings}


def test_revocation_writer_before_consume(native):
    sessions,service,_,cid=native
    aid=request(native);approve(native,aid)
    with pytest.raises(PermissionError): service.revoke(aid,tenant_id='a',revoked_by='intruder')
    service.revoke(aid,tenant_id='a',revoked_by='owner-a')
    service.revoke(aid,tenant_id='a',revoked_by='owner-a')
    with pytest.raises(PermissionError): d.promote_candidate('a',cid)
    assert snapshot(sessions)['sources']==[]
    assert len([e for e in service.audit(aid) if e['event']=='revoked'])==1
    bid=request(native);approve(native,bid);d.promote_candidate('a',cid)
    with pytest.raises(ApprovalConflictError): service.revoke(bid,tenant_id='a',revoked_by='owner-a')


def test_atomic_request_rollback_no_orphan(native, monkeypatch):
    sessions,service,_,cid=native
    submit=service._submit_in_transaction
    def fail(db,**kw):
        submit(db,**kw)
        raise RuntimeError('after request insertion')
    monkeypatch.setattr(service,'_submit_in_transaction',fail)
    with pytest.raises(RuntimeError):request(native)
    with sessions() as db:
        assert list(db.scalars(select(ApprovalRequestRow)))==[]
        assert list(db.scalars(select(d.CandidateApprovalBindingRow)))==[]


def test_absent_server_owner_fails_closed(native, monkeypatch):
    sessions,_,_,cid=native
    aid=request(native);approve(native,aid)
    monkeypatch.delenv('ATLAS_PROMOTION_OWNERS_JSON')
    with pytest.raises(PermissionError):d.promote_candidate('a',cid)
    assert snapshot(sessions)['sources']==[]


def test_retry_migration_preserves_history_and_guards(tmp_path):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError
    engine=create_engine(f"sqlite:///{tmp_path/'upgrade.db'}")
    def load(name):
        path=Path(__file__).parents[1]/'migrations/versions'/name
        spec=importlib.util.spec_from_file_location(name,path)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        return mod
    with engine.begin() as conn:
        operations=Operations(MigrationContext.configure(conn))
        legacy=load('20261001_discovery_approval_binding.py');legacy.op=operations;legacy.upgrade()
        conn.execute(text('CREATE TABLE discovery_candidates (id INTEGER PRIMARY KEY, platform TEXT)'))
        conn.execute(text("INSERT INTO discovery_candidates VALUES(1,'instagram')"))
        conn.execute(text("INSERT INTO discovery_approval_bindings VALUES(1,'old','a','hash')"))
        conn.execute(text("INSERT INTO discovery_approval_uses VALUES('old',1,1,'2026-01-01')"))
        current=load('20261001_discovery_retry_attempts.py');current.op=operations;current.upgrade()
        assert tuple(conn.execute(text('SELECT approval_id,candidate_id,version,source_key FROM discovery_approval_bindings')).one())==('old',1,1,'tracked:instagram')
        assert conn.scalar(text('SELECT count(*) FROM discovery_approval_uses'))==1
        for table in ['discovery_approval_bindings','discovery_approval_uses']:
            with pytest.raises(IntegrityError):conn.execute(text(f'DELETE FROM {table}'))
        conn.execute(text("INSERT INTO discovery_approval_bindings VALUES('fresh',1,2,'tracked:account',NULL,'a','newhash')"))
        with pytest.raises(RuntimeError,match='audited rollback'):current.downgrade()
    engine.dispose()


def test_revocation_route_uses_authenticated_actor(native, monkeypatch):
    from app.auth.context import TenantContext
    from app.modules.m00_approval_center.routes import revoke_request
    from fastapi import HTTPException
    sessions,service,_,cid=native
    aid=request(native);approve(native,aid)
    with pytest.raises(HTTPException) as denied:
        revoke_request(aid,service,TenantContext('a','intruder'))
    assert denied.value.status_code==403
    with pytest.raises(HTTPException) as wrong_tenant:
        revoke_request(aid,service,TenantContext('b','owner-b'))
    assert wrong_tenant.value.status_code==404
    revoke_request(aid,service,TenantContext('a','owner-a'))
    with pytest.raises(PermissionError):d.promote_candidate('a',cid)


def test_postgres_retry_migration_preserves_history_and_guards():
    import os
    import importlib.util
    from pathlib import Path
    from uuid import uuid4
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError
    url=os.getenv('ATLAS_TEST_DATABASE_URL', '')
    if not url.startswith('postgresql:') and not url.startswith('postgresql+'):
        pytest.skip('requires a real PostgreSQL test database')
    engine=create_engine(url)
    schema='migration_'+uuid4().hex
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA {schema}'))
            conn.execute(text(f'SET search_path TO {schema}'))
            operations=Operations(MigrationContext.configure(conn))
            for name in ['20261001_discovery_approval_binding.py','20261001_discovery_retry_attempts.py']:
                spec=importlib.util.spec_from_file_location(name,Path(__file__).parents[1]/'migrations/versions'/name)
                mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.op=operations
                if name.endswith('retry_attempts.py'):
                    conn.execute(text('CREATE TABLE discovery_candidates (id INTEGER PRIMARY KEY, platform TEXT)'))
                    conn.execute(text("INSERT INTO discovery_candidates VALUES(1,'instagram')"))
                    conn.execute(text("INSERT INTO discovery_approval_bindings VALUES(1,'old','a','hash')"))
                    conn.execute(text("INSERT INTO discovery_approval_uses VALUES('old',1,1,'2026-01-01')"))
                mod.upgrade()
            assert conn.scalar(text('SELECT count(*) FROM discovery_approval_bindings'))==1
            assert conn.scalar(text('SELECT count(*) FROM discovery_approval_uses'))==1
            conn.execute(text("INSERT INTO discovery_approval_bindings VALUES('fresh',1,2,'tracked:new',NULL,'a','newhash')"))
            for table in ['discovery_approval_bindings','discovery_approval_uses']:
                for statement in [f'DELETE FROM {table}',f"UPDATE {table} SET candidate_id=999"]:
                    with pytest.raises(IntegrityError), conn.begin_nested():conn.execute(text(statement))
    finally:
        with engine.begin() as conn:conn.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        engine.dispose()
