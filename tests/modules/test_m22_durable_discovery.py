import pytest
from app.modules.m22_tools_hub.discovery_state_store import DiscoveryStateStore,StateError
from app.modules.m22_tools_hub.durable_discovery import DurableDiscoveryService

class Collector:
    name='fake';kind='tool'
    def __init__(self,fail=False):self.calls=0;self.fail=fail
    async def collect(self,q):
        self.calls+=1
        if self.fail:raise RuntimeError('private-error')
        yield {'name':'Public Tool','url':'https://example.org','summary':'ok'}

@pytest.mark.asyncio
async def test_restart_cooldown_and_digest_diff(tmp_path):
    store=DiscoveryStateStore(tmp_path,'a');store.provision()
    c=Collector(True)
    first=DurableDiscoveryService(None,[c],discovery_store=store,source_cooldown_seconds=300)
    await first.discover('q');assert c.calls==1
    second=DurableDiscoveryService(None,[c],discovery_store=DiscoveryStateStore(tmp_path,'a'))
    await second.discover('q');assert c.calls==1
    assert second.last_diffs['q']['first_run'] is False
    assert b'private-error' not in store.path.read_bytes()

@pytest.mark.asyncio
async def test_persist_failure_latches_and_missing_refuses(tmp_path,monkeypatch):
    store=DiscoveryStateStore(tmp_path,'a')
    with pytest.raises(StateError):DurableDiscoveryService(None,[],discovery_store=store)
    store.provision();c=Collector();s=DurableDiscoveryService(None,[c],discovery_store=store)
    def fail(*a,**kw):raise StateError('commit_unverified')
    monkeypatch.setattr(store,'record_query',fail)
    with pytest.raises(StateError):await s.discover('q')
    with pytest.raises(StateError,match='persistence_failed'):await s.discover('q')
    assert c.calls==1 and not s.candidates

@pytest.mark.asyncio
async def test_restart_nonempty_snapshot_not_new_and_tenant_isolation(tmp_path):
    a=DiscoveryStateStore(tmp_path,'a');a.provision()
    c=Collector();one=DurableDiscoveryService(None,[c],discovery_store=a)
    found=await one.discover('q');assert len(found)==1
    two=DurableDiscoveryService(None,[c],discovery_store=DiscoveryStateStore(tmp_path,'a'))
    await two.discover('q')
    assert two.last_diffs['q']['first_run'] is False and two.last_diffs['q']['added']==[]
    b=DiscoveryStateStore(tmp_path,'b');b.provision()
    other=DurableDiscoveryService(None,[c],discovery_store=b)
    await other.discover('q');assert other.last_diffs['q']['first_run'] is True

@pytest.mark.asyncio
async def test_capacity_refuses_before_collector(tmp_path,monkeypatch):
    from app.modules.m22_tools_hub import durable_discovery as d
    store=DiscoveryStateStore(tmp_path,'a');store.provision();store.record_query('old',[],at=1)
    monkeypatch.setattr(d,'MAX_QUERIES',1)
    c=Collector();s=d.DurableDiscoveryService(None,[c],discovery_store=store)
    with pytest.raises(StateError,match='query_capacity'):await s.discover('new')
    assert c.calls==0
    assert not s._persistence_failed
    await s.discover('old')
    assert c.calls==1


@pytest.mark.asyncio
async def test_invalid_kind_does_not_latch(tmp_path):
    store=DiscoveryStateStore(tmp_path,'a');store.provision()
    c=Collector();s=DurableDiscoveryService(None,[c],discovery_store=store)
    with pytest.raises(StateError,match='invalid_kind'):await s.discover('q',kinds=['bad'])
    assert not s._persistence_failed and c.calls==0
    await s.discover('q');assert c.calls==1
