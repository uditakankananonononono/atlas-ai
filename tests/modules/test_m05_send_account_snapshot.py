"""Real SQLite storage/locking tests, no external mail or fake delivery claim."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import sqlite3
import threading

import pytest
from app.modules.m05_outreach_manager.send_account_snapshot import (
    SendState, SnapshotStore, PreflightRefused,
)

NOW = datetime(2026,10,8,10,30,tzinfo=timezone.utc)

def state():
    return SendState('m1','r1','c1','cr1','recipient@example.invalid','Review me',
                     'exact Unicode body ₹42','account-a','ar1','owner@example.invalid',
                     'principal-a','smtp-route-a')

@pytest.fixture
def store(tmp_path):
    return SnapshotStore(tmp_path/'reviews.sqlite', clock=lambda: NOW)


def test_durable_exact_snapshot_and_one_time_claim(store):
    original = state()
    token = store.record_review('tenant-a','reviewer-a',original)
    other = SnapshotStore(store.path,clock=lambda:NOW)
    row = other.read_review('tenant-a',token)
    assert row['reviewer']=='reviewer-a' and row['claimed_at'] is None
    assert row['snapshot']['body'] == 'exact Unicode body ₹42'
    seen=[]
    def inspect(tenant,message):
        seen.append((tenant,message));return original
    claimed = other.claim('tenant-a',token,inspect)
    assert seen == [('tenant-a','m1')] and claimed == original
    with pytest.raises(FrozenInstanceError): claimed.body='edited'
    assert other.read_review('tenant-a',token)['claimed_at']==NOW.isoformat()
    with pytest.raises(PreflightRefused,match='consumed'):
        store.claim('tenant-a',token,inspect)
    with pytest.raises(PreflightRefused,match='immutable'):
        store.record_review('tenant-a','reviewer-b',replace(original,body='retry'))


@pytest.mark.parametrize('field', list(SendState.__dataclass_fields__))
def test_each_reviewed_field_drift_refuses_without_consuming(store,field):
    token=store.record_review('tenant-a','owner',state())
    altered=replace(state(),**{field:getattr(state(),field)+'CHANGED'})
    with pytest.raises(PreflightRefused,match=field):
        store.claim('tenant-a',token,lambda t,m:altered)
    assert store.read_review('tenant-a',token)['claimed_at'] is None
    assert store.claim('tenant-a',token,lambda t,m:state()) == state()


def test_cross_tenant_refusal_and_same_message_id_isolation(store):
    a=store.record_review('a','owner-a',state())
    bstate=replace(state(),account_id='b',body='tenant b')
    b=store.record_review('b','owner-b',bstate)
    with pytest.raises(PreflightRefused,match='not found'):
        store.claim('b',a,lambda t,m:state())
    with pytest.raises(PreflightRefused):store.read_review('b',a)
    assert store.claim('a',a,lambda t,m:state())==state()
    assert store.claim('b',b,lambda t,m:bstate)==bstate


def test_eight_independent_connections_only_one_claims(store):
    token=store.record_review('a','owner',state());barrier=threading.Barrier(8)
    def claim(_):
        independent=SnapshotStore(store.path,clock=lambda:NOW)
        barrier.wait()
        try:independent.claim('a',token,lambda t,m:state());return 'claimed'
        except PreflightRefused:return 'refused'
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(claim,range(8)))
    assert results.count('claimed')==1 and results.count('refused')==7


def test_inspector_error_does_not_consume(store):
    token=store.record_review('a','owner',state())
    def broken(t,m):raise OSError('account source unavailable')
    with pytest.raises(OSError):store.claim('a',token,broken)
    assert store.read_review('a',token)['claimed_at'] is None
    with pytest.raises(PreflightRefused,match='SendState'):
        store.claim('a',token,lambda t,m:None)


def test_expiry_including_time_spent_inspecting(store):
    token=store.record_review('a','owner',state(),valid_for=timedelta(seconds=5))
    clock=[NOW]
    s=SnapshotStore(store.path,clock=lambda:clock[0])
    def inspect(t,m):clock[0]=NOW+timedelta(seconds=5);return state()
    with pytest.raises(PreflightRefused,match='expired'):s.claim('a',token,inspect)
    assert s.read_review('a',token)['claimed_at'] is None


def test_clock_backwards_refused(store):
    token=store.record_review('a','owner',state())
    s=SnapshotStore(store.path,clock=lambda:NOW-timedelta(seconds=1))
    with pytest.raises(PreflightRefused,match='clock'):s.claim('a',token,lambda t,m:state())


def test_snapshot_sql_update_delete_and_claim_reset_refused(store):
    token=store.record_review('a','owner',state())
    with sqlite3.connect(store.path) as db:
        for command in ("UPDATE send_reviews SET snapshot='{}'",'DELETE FROM send_reviews'):
            with pytest.raises(sqlite3.IntegrityError):db.execute(command)
    store.claim('a',token,lambda t,m:state())
    with sqlite3.connect(store.path) as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('UPDATE send_reviews SET claimed_at=NULL')


@pytest.mark.parametrize('field', ['recipient','from_address','subject'])
def test_header_injection_refused(field):
    with pytest.raises(ValueError,match='newline'):replace(state(),**{field:'good\r\nBcc: other'})

@pytest.mark.parametrize('ttl', [timedelta(0),timedelta(seconds=-1),timedelta(hours=2)])
def test_invalid_review_lifetime(store,ttl):
    with pytest.raises(ValueError):store.record_review('a','owner',state(),valid_for=ttl)


def test_unaware_clock_and_empty_identity_refused(tmp_path,store):
    s=SnapshotStore(tmp_path/'naive.sqlite',clock=lambda:NOW.replace(tzinfo=None))
    with pytest.raises(ValueError,match='aware'):s.record_review('a','owner',state())
    for tenant,reviewer in [('', 'owner'),('a','')]:
        with pytest.raises(ValueError):store.record_review(tenant,reviewer,state())
    with pytest.raises(ValueError):replace(state(),account_revision='')
    with pytest.raises(ValueError):SnapshotStore(':memory:')


def _process_claim(path, token, output):
    # Module-level callable so spawn starts fresh interpreters/connections.
    s=SnapshotStore(path,clock=lambda:NOW)
    try:s.claim('a',token,lambda t,m:state());output.put('claimed')
    except PreflightRefused:output.put('refused')


def test_four_processes_only_one_claims(store):
    import multiprocessing
    ctx=multiprocessing.get_context('spawn')
    token=store.record_review('a','owner',state());output=ctx.Queue()
    processes=[ctx.Process(target=_process_claim,args=(store.path,token,output)) for _ in range(4)]
    for p in processes:p.start()
    results=[output.get(timeout=20) for _ in processes]
    for p in processes:p.join(timeout=20);assert p.exitcode==0
    assert results.count('claimed')==1 and results.count('refused')==3
    output.close();output.join_thread()


def test_external_source_not_locked_and_claim_does_not_send(store):
    token=store.record_review('a','owner',state())
    live=[state()]
    claimed=store.claim('a',token,lambda t,m:live[0])
    live[0]=replace(live[0],account_revision='revoked')
    # Document the boundary: a later external edit does not mutate the claim.
    assert claimed.account_revision=='ar1' and live[0].account_revision=='revoked'
    assert store.read_review('a',token)['claimed_at'] is not None
