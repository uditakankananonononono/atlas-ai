"""Real collector/paired WAL path, fake HTTP only, no network."""
from datetime import timedelta
import pytest
from test_m18_dispatch_intent import NOW
from app.modules.m18_side_hustle_scraper.dispatch_intent import DispatchIntentWAL,IntentBoundHostRateLimiter
from app.modules.m18_side_hustle_scraper.durable_rate_limiter import DurableHostRateLimiter
from app.modules.m18_side_hustle_scraper.lane_rate_limit_state import StateRejected,read_snapshot
from app.modules.m18_side_hustle_scraper.lane_sources import BaseCollector
from app.modules.m18_side_hustle_scraper.lane_http import HttpError
from app.modules.m18_side_hustle_scraper.lane_models import FetchPolicy
URL='https://example.org/data'
HOST='example.org'

class Clock:
    now=NOW
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=timedelta(seconds=seconds)

class Http:
    def __init__(self,check):self.calls=0;self.check=check
    def fetch(self,*a,**kw):
        self.calls+=1;self.check(self.calls);return 'real fake response'

def setup(root,*,sleeper=None,retries=0):
    clock=Clock();policy=FetchPolicy(min_request_interval_seconds=2,max_retries=retries)
    wal=DispatchIntentWAL(root,'t');wal.provision()
    DurableHostRateLimiter(root,'t',bootstrap=True,clock=clock,policy=policy)
    limiter=IntentBoundHostRateLimiter(root,'t',clock=clock,policy=policy)
    def check(calls):
        assert wal.read()['pending'] is None
        state=read_snapshot(limiter._path,tenant_id='t',now=clock())
        assert state.states[HOST].total_requests==calls
        assert state.states[HOST].last_request_at==clock()
    http=Http(check)
    collector=BaseCollector(http,limiter=limiter,clock=clock,policy=policy,sleeper=sleeper or clock.sleep)
    return collector,limiter,wal,http,clock

def test_permission_and_snapshot_readback_before_fetch(tmp_path,monkeypatch):
    c,l,wal,http,clock=setup(tmp_path)
    def forbidden(*a):raise AssertionError('bound record_request must never be used')
    monkeypatch.setattr(l,'record_request',forbidden)
    assert c._get(URL)==('real fake response',None)
    assert http.calls==1
    assert c._get(URL)==('real fake response',None)
    assert http.calls==2 and clock.now>=NOW+timedelta(seconds=2)


def test_pending_fresh_limiter_blocks_fetch(tmp_path):
    c,l,wal,http,clock=setup(tmp_path);wal.begin('other',clock())
    fresh=IntentBoundHostRateLimiter(tmp_path,'t',clock=clock,policy=c.policy)
    c.limiter=fresh
    response,error=c._get(URL)
    assert response is None and error and http.calls==0
    assert wal.read()['pending']['host']=='other'

@pytest.mark.parametrize('phase',['intent','snapshot','completion','success','failure','retry_after'])
def test_persistence_failure_denies_current_operation(tmp_path,monkeypatch,phase):
    c,l,wal,http,clock=setup(tmp_path,retries=1)
    def fail(*a,**kw):raise StateRejected('private sentinel')
    if phase=='intent':monkeypatch.setattr(l.intent_wal,'begin',fail)
    if phase=='snapshot':monkeypatch.setattr(l,'_save',fail)
    if phase=='completion':monkeypatch.setattr(l.intent_wal,'_complete',fail)
    if phase=='success':monkeypatch.setattr(l,'record_success',fail)
    if phase in ('failure','retry_after'):
        def fetching(*a,**kw):http.calls+=1;raise HttpError(URL,429,'slow down',retry_after=10)
        http.fetch=fetching
        monkeypatch.setattr(l,'record_failure' if phase=='failure' else 'honor_retry_after',fail)
    response,error=c._get(URL)
    assert response is None and error
    assert http.calls==(1 if phase in ('success','failure','retry_after') else 0)
    assert 'private sentinel' not in str(error)


def test_noop_sleeper_cannot_grant_permission(tmp_path):
    waits=[];c,l,wal,http,clock=setup(tmp_path,sleeper=waits.append)
    assert c._get(URL)[0]=='real fake response'
    response,error=c._get(URL)
    assert response is None and error and http.calls==1
    assert len(waits)==3
    assert l._states[HOST].total_requests==1


def test_retry_charges_each_dispatch_and_rechecks_wait(tmp_path):
    c,l,wal,http,clock=setup(tmp_path,retries=1);check=http.check
    def fetching(*a,**kw):
        http.calls+=1;check(http.calls)
        if http.calls==1:raise HttpError(URL,429,'slow down',retry_after=3)
        return 'retried'
    http.fetch=fetching
    assert c._get(URL)==('retried',None)
    assert http.calls==2 and clock.now>=NOW+timedelta(seconds=3)


def test_declaration_required_legacy_path_unchanged(tmp_path):
    from app.modules.m18_side_hustle_scraper.lane_rate_limit import HostRateLimiter
    clock=Clock();policy=FetchPolicy(max_retries=0)
    legacy=HostRateLimiter(policy,clock=clock);http=Http(lambda n:None)
    c=BaseCollector(http,limiter=legacy,clock=clock,policy=policy)
    assert not hasattr(legacy,'dispatch_intent_bound')
    assert c._get(URL)==('real fake response',None)
    assert http.calls==1


def test_declared_protocol_missing_fails_closed(tmp_path):
    c,l,_,http,_=setup(tmp_path)
    l.begin_request=None
    assert c._get(URL)[0] is None and http.calls==0


def test_excessive_wait_fails_without_sleep_or_fetch(tmp_path,monkeypatch):
    waits=[];c,l,_,http,_=setup(tmp_path,sleeper=waits.append)
    monkeypatch.setattr(l,'begin_request',lambda host:3601)
    assert c._get(URL)[0] is None and http.calls==0 and not waits


def test_circuit_blocks_fetch(tmp_path,monkeypatch):
    c,l,_,http,_=setup(tmp_path)
    monkeypatch.setattr(l,'circuit_open',lambda host:True)
    assert c._get(URL)[0] is None and http.calls==0
