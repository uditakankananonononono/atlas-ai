"""Duplicate-send guard: actual state/storage, local sender boundary only."""
import asyncio
from datetime import datetime,timezone
import pytest
from test_m05_delivery import make_world,gate_for,FakeSender
from app.modules.m05_outreach_manager.delivery import DeliveryService,DeliveryReceipt,DeliveryApprovalError


def test_concurrent_same_message_crosses_sender_only_once():
    service,_,_,_,draft,approval=make_world(datetime.now(timezone.utc))
    class PausingSender:
        name='boundary'
        def __init__(self):self.calls=[]
        async def send(self,**kwargs):
            self.calls.append(kwargs);await asyncio.sleep(.05)
            return DeliveryReceipt(provider_message_id='local')
    async def run():
        sender=PausingSender();d=DeliveryService(service,gate_for(approval),sender)
        outcomes=await asyncio.gather(d.send_approved(draft.id),d.send_approved(draft.id),return_exceptions=True)
        assert len(sender.calls)==1
        assert sum(isinstance(o,DeliveryApprovalError) for o in outcomes)==1
    asyncio.run(run())


def sql_repo(tmp_path,tenant='a'):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.modules.m05_outreach_manager.sql_repository import SqlCampaignRepository
    engine=create_engine('sqlite:///'+str(tmp_path/'claims.sqlite'),connect_args={'timeout':10})
    Base.metadata.create_all(engine)
    return SqlCampaignRepository(tenant,sessionmaker(bind=engine)),engine


def approved_message():
    service,_,_,_,draft,_=make_world(datetime(2026,10,8,tzinfo=timezone.utc))
    return service.get_message(draft.id)


def persist(repo,message):
    from app.modules.m05_outreach_manager.campaigns import MessageEvent
    return repo.save_message(message,MessageEvent(message_id=message.id,event='fixture',at=message.updated_at))


def test_sql_exact_snapshot_and_reopen_does_not_retry(tmp_path):
    from dataclasses import dataclass
    repo,engine=sql_repo(tmp_path);message=approved_message();persist(repo,message)
    assert not repo.claim_delivery(message.model_copy(update={'body':'changed'}))
    assert repo.claim_delivery(message)
    other,_=sql_repo(tmp_path)
    assert not other.claim_delivery(message)
    persist(other,message.model_copy(update={'version':message.version+1}))
    assert not other.claim_delivery(other.get_message(message.id))
    engine.dispose()


def test_sql_cross_tenant_same_message_id_isolated(tmp_path):
    a,e=sql_repo(tmp_path,'a');b,e2=sql_repo(tmp_path,'b');m=approved_message()
    persist(a,m)
    assert not b.claim_delivery(m)
    persist(b,m)
    assert a.claim_delivery(m) and b.claim_delivery(m)
    assert not a.claim_delivery(m) and not b.claim_delivery(m)
    e.dispose();e2.dispose()


def test_sql_eight_independent_sessions_claim_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    repo,engine=sql_repo(tmp_path);m=approved_message();persist(repo,m)
    barrier=threading.Barrier(8)
    def claim(_):barrier.wait();return repo.claim_delivery(m)
    with ThreadPoolExecutor(max_workers=8) as pool:out=list(pool.map(claim,range(8)))
    assert out.count(True)==1 and out.count(False)==7
    engine.dispose()


def test_unknown_repository_fails_closed():
    service,_,_,_,draft,approval=make_world(datetime.now(timezone.utc))
    class NoClaim:
        def __getattr__(self,name):
            if name=='claim_delivery':raise AttributeError(name)
            return getattr(original,name)
    original=service.campaigns;service.campaigns=NoClaim();sender=FakeSender()
    with pytest.raises(DeliveryApprovalError,match='claim'):
        asyncio.run(DeliveryService(service,gate_for(approval),sender).send_approved(draft.id))
    assert sender.calls==[]


def test_cancellation_consumes_claim_without_retry():
    service,_,_,_,draft,approval=make_world(datetime.now(timezone.utc))
    class CancelSender:
        name='cancel'
        async def send(self,**kw):raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(DeliveryService(service,gate_for(approval),CancelSender()).send_approved(draft.id))
    sender=FakeSender()
    with pytest.raises(DeliveryApprovalError,match='claim'):
        asyncio.run(DeliveryService(service,gate_for(approval),sender).send_approved(draft.id))
    assert sender.calls==[]


def reviewed_delivery(service,draft,approval,sender,tmp_path,*,alter=None):
    from app.modules.m05_outreach_manager.send_account_snapshot import SnapshotStore,SendState
    m=service.get_message(draft.id);c=service._contact(m.contact_id)
    snapshot=SendState(m.id,str(m.version),c.id,str(c.version),str(c.email),m.subject,m.body,
                       'account-a','rev1','owner@example.invalid','principal-a','transport-a')
    store=SnapshotStore(tmp_path/'review.sqlite')
    token=store.record_review(service.tenant_id,'owner',snapshot)
    live=snapshot if alter is None else alter(snapshot)
    return DeliveryService(service,gate_for(approval),sender,review_store=store,
                           review_token=token,inspect_account=lambda t,m:live)


def test_reviewed_snapshot_path_passes_frozen_from_address(tmp_path):
    service,_,_,_,draft,approval=make_world(datetime.now(timezone.utc))
    class InspectSender:
        name='boundary'
        def __init__(self):self.kw=None
        async def send(self,**kw):self.kw=kw;return DeliveryReceipt()
    sender=InspectSender();d=reviewed_delivery(service,draft,approval,sender,tmp_path)
    asyncio.run(d.send_approved(draft.id))
    assert sender.kw['from_account']=='owner@example.invalid'
    assert sender.kw['body']=='Body text'


def test_live_account_drift_on_reviewed_route_blocks_send(tmp_path):
    from dataclasses import replace
    service,_,_,_,draft,approval=make_world(datetime.now(timezone.utc));sender=FakeSender()
    d=reviewed_delivery(service,draft,approval,sender,tmp_path,
                        alter=lambda s:replace(s,auth_principal='changed-principal'))
    with pytest.raises(DeliveryApprovalError,match='auth_principal'):asyncio.run(d.send_approved(draft.id))
    assert sender.calls==[]


def test_partial_review_configuration_refused(tmp_path):
    from app.modules.m05_outreach_manager.send_account_snapshot import SnapshotStore
    service,_,_,_,draft,approval=make_world(datetime.now(timezone.utc))
    with pytest.raises(ValueError,match='together'):
        DeliveryService(service,gate_for(approval),FakeSender(),review_store=SnapshotStore(tmp_path/'r'))


def _sql_process_claim(path,tenant,message_data,output):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.modules.m05_outreach_manager.sql_repository import SqlCampaignRepository
    from app.modules.m05_outreach_manager.campaigns import OutreachMessage
    engine=create_engine('sqlite:///'+path,connect_args={'timeout':10})
    repo=SqlCampaignRepository(tenant,sessionmaker(bind=engine))
    output.put(repo.claim_delivery(OutreachMessage.model_validate(message_data)))
    engine.dispose()


def test_sql_fresh_process_claim_persists_across_restart(tmp_path):
    import multiprocessing
    repo,e=sql_repo(tmp_path);m=approved_message();persist(repo,m)
    ctx=multiprocessing.get_context('spawn');q=ctx.Queue()
    ps=[ctx.Process(target=_sql_process_claim,args=(str(tmp_path/'claims.sqlite'),'a',m.model_dump(mode='json'),q)) for _ in range(4)]
    for p in ps:p.start()
    outcomes=[q.get(timeout=20) for _ in ps]
    for p in ps:p.join(timeout=20);assert p.exitcode==0
    assert outcomes.count(True)==1 and outcomes.count(False)==3
    assert not repo.claim_delivery(m)
    q.close();q.join_thread();e.dispose()


def test_sql_claim_refuses_live_content_drift(tmp_path):
    repo,e=sql_repo(tmp_path);m=approved_message();persist(repo,m)
    edited=m.model_copy(update={'body':'edited','version':m.version+1});persist(repo,edited)
    assert not repo.claim_delivery(m)
    assert repo.claim_delivery(edited)
    e.dispose()


def test_sql_replace_update_delete_cannot_reset_claim(tmp_path):
    import sqlite3
    repo,e=sql_repo(tmp_path);m=approved_message();persist(repo,m);assert repo.claim_delivery(m)
    with sqlite3.connect(tmp_path/'claims.sqlite') as db:
        assert db.execute('PRAGMA recursive_triggers').fetchone()[0]==0
        row=list(db.execute('SELECT * FROM m05_delivery_claims').fetchone())
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('INSERT OR REPLACE INTO m05_delivery_claims VALUES (?,?,?,?)',row)
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM m05_delivery_claims')
        with pytest.raises(sqlite3.IntegrityError):db.execute("UPDATE m05_delivery_claims SET message_id='reset'")
    assert not repo.claim_delivery(m)
    e.dispose()
