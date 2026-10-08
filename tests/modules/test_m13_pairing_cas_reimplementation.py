"""Pairing challenge single-claim pins; scoped repository evidence."""
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from app.core.database import Base
from app.modules.m13_browser_agent.session_bridge.registry import (
    BridgeRegistry, PairingChallengeRow, PairedDeviceRow, PairingError,
)

@pytest.fixture
def registry(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'pair.db'}")
    Base.metadata.create_all(engine, tables=[PairingChallengeRow.__table__, PairedDeviceRow.__table__])
    factory=sessionmaker(engine, expire_on_commit=False)
    yield BridgeRegistry(factory),factory
    engine.dispose()

def test_competitor_consumes_after_read_loser_creates_no_device(registry,monkeypatch):
    reg,factory=registry; challenge=reg.create_challenge('tenant-a')
    get=Session.get; injected=[]
    def competitor(session, entity, ident, *a, **kw):
        result=get(session,entity,ident,*a,**kw)
        if entity is PairingChallengeRow and not injected:
            injected.append(True)
            with factory.begin() as other:
                winner=get(other,PairingChallengeRow,ident);winner.consumed=True
        return result
    monkeypatch.setattr(Session,'get',competitor)
    with pytest.raises(PairingError,match='already-used'):
        reg.confirm_pairing(challenge['server_nonce'],challenge['code'],name='PC',public_key='test-only',capabilities=['navigate'])
    with factory() as session: assert not list(session.scalars(select(PairedDeviceRow)))

@pytest.mark.parametrize('invalid',['wrong_code','expired'])
def test_invalid_challenge_not_consumed(registry,invalid):
    reg,factory=registry;c=reg.create_challenge('tenant-a')
    if invalid=='expired':
        with factory.begin() as session:
            session.get(PairingChallengeRow,c['server_nonce']).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    code=('000000' if c['code']!='000000' else '000001') if invalid=='wrong_code' else c['code']
    with pytest.raises(PairingError): reg.confirm_pairing(c['server_nonce'],code,name='PC',public_key='test-only',capabilities=['navigate'])
    with factory() as session: assert not session.get(PairingChallengeRow,c['server_nonce']).consumed

def test_device_write_failure_rolls_back_consumption(registry,monkeypatch):
    reg,factory=registry;c=reg.create_challenge('tenant-a');flush=Session.flush
    def fail(session,*a,**kw):
        if any(isinstance(x,PairedDeviceRow) for x in session.new): raise RuntimeError('device persist failed')
        return flush(session,*a,**kw)
    monkeypatch.setattr(Session,'flush',fail)
    with pytest.raises(RuntimeError): reg.confirm_pairing(c['server_nonce'],c['code'],name='PC',public_key='test-only',capabilities=['navigate'])
    with factory() as session: assert not session.get(PairingChallengeRow,c['server_nonce']).consumed

def test_real_postgres_eight_consumers_one_device(tmp_path):
    import threading
    import pgserver
    server=pgserver.get_server(str(tmp_path/'pg'))
    engine=create_engine(server.get_uri())
    try:
        Base.metadata.create_all(engine, tables=[PairingChallengeRow.__table__, PairedDeviceRow.__table__])
        factory=sessionmaker(engine,expire_on_commit=False)
        reg=BridgeRegistry(factory)
        for turn in range(5):
            c=reg.create_challenge('tenant-a');barrier=threading.Barrier(8)
            winners=[];losers=[];errors=[]
            def worker(i):
                try:
                    barrier.wait()
                    winners.append(reg.confirm_pairing(c['server_nonce'],c['code'],name=f'PC-{i}',public_key='test-only',capabilities=['navigate']))
                except PairingError as e: losers.append(e)
                except Exception as e: errors.append(e)
            threads=[threading.Thread(target=worker,args=(i,)) for i in range(8)]
            for t in threads:t.start()
            for t in threads:t.join(timeout=30)
            assert not any(t.is_alive() for t in threads)
            assert not errors
            assert len(winners)==1 and len(losers)==7
            with factory() as session:
                devices=list(session.scalars(select(PairedDeviceRow)))
                assert len(devices)==turn+1
                assert session.get(PairingChallengeRow,c['server_nonce']).consumed
    finally:
        engine.dispose();server.cleanup()
