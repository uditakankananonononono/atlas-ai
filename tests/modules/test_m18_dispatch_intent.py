from datetime import datetime,timezone,timedelta
import pytest
from app.modules.m18_side_hustle_scraper.dispatch_intent import DispatchIntentWAL,IntentBoundHostRateLimiter
from app.modules.m18_side_hustle_scraper.durable_rate_limiter import DurableHostRateLimiter
from app.modules.m18_side_hustle_scraper.lane_rate_limit_state import StateRejected
NOW=datetime(2026,10,10,tzinfo=timezone.utc)

def prepare(root):
    wal=DispatchIntentWAL(root,'t');wal.provision()
    DurableHostRateLimiter(root,'t',bootstrap=True,clock=lambda:NOW)
    return wal,IntentBoundHostRateLimiter(root,'t',clock=lambda:NOW)


def test_success_order_and_restart_pacing(tmp_path,monkeypatch):
    wal,limiter=prepare(tmp_path);events=[]
    save=limiter._save;complete=limiter.intent_wal._complete
    def saving():
        assert limiter.intent_wal.read()['pending']['host']=='h'
        events.append('snapshot');save()
    def completing(intent):events.append('complete');complete(intent)
    monkeypatch.setattr(limiter,'_save',saving);monkeypatch.setattr(limiter.intent_wal,'_complete',completing)
    assert limiter.begin_request('h')==0
    assert events==['snapshot','complete'] and wal.read()['pending'] is None
    fresh=IntentBoundHostRateLimiter(tmp_path,'t',clock=lambda:NOW)
    assert fresh.begin_request('h')>0


def test_snapshot_failure_pending_survives_new_instance(tmp_path,monkeypatch):
    wal,limiter=prepare(tmp_path)
    def fail():raise StateRejected('save failure')
    monkeypatch.setattr(limiter,'_save',fail)
    with pytest.raises(StateRejected):limiter.begin_request('h')
    pending=wal.read()['pending'];assert pending['host']=='h'
    fresh=IntentBoundHostRateLimiter(tmp_path,'t',clock=lambda:NOW)
    with pytest.raises(StateRejected,match='pending'):fresh.begin_request('other')
    with pytest.raises(StateRejected):wal.acknowledge_inspected(pending)
    with pytest.raises(StateRejected):wal.acknowledge_inspected({**pending,'id':'a'*32},operator_inspected=True)
    wal.acknowledge_inspected(pending,operator_inspected=True)
    assert wal.read()['pending'] is None


def test_intent_write_failure_no_request_permission(tmp_path,monkeypatch):
    wal,limiter=prepare(tmp_path)
    def fail(state):raise StateRejected('write failure')
    monkeypatch.setattr(limiter.intent_wal,'_write',fail)
    with pytest.raises(StateRejected):limiter.begin_request('h')
    assert limiter._states['h'].total_requests==0
    with pytest.raises(StateRejected):limiter.begin_request('h')


def test_crash_shape_pending_without_snapshot_refuses_all(tmp_path):
    wal,limiter=prepare(tmp_path)
    wal.begin('h',NOW)
    fresh=IntentBoundHostRateLimiter(tmp_path,'t',clock=lambda:NOW)
    with pytest.raises(StateRejected):fresh.check('x')
    with pytest.raises(StateRejected):fresh.record_request('h')
    with pytest.raises(StateRejected):fresh.honor_retry_after('h',600)


def test_completion_failure_after_snapshot_retains_safe_pacing(tmp_path,monkeypatch):
    wal,limiter=prepare(tmp_path)
    def fail(intent):raise StateRejected('complete failure')
    monkeypatch.setattr(limiter.intent_wal,'_complete',fail)
    with pytest.raises(StateRejected):limiter.begin_request('h')
    assert wal.read()['pending']
    restarted=IntentBoundHostRateLimiter(tmp_path,'t',clock=lambda:NOW)
    with pytest.raises(StateRejected):restarted.begin_request('h')


def test_missing_corrupt_cross_tenant_and_existing_bootstrap(tmp_path):
    wal=DispatchIntentWAL(tmp_path,'t')
    with pytest.raises(StateRejected):wal.read()
    wal.provision()
    with pytest.raises(StateRejected):wal.provision()
    other=DispatchIntentWAL(tmp_path,'other');other.path.write_bytes(wal.path.read_bytes())
    with pytest.raises(StateRejected):other.read()
    wal.path.write_bytes(b'{')
    with pytest.raises(StateRejected):wal.read()


def test_symlink_read_and_naive_timestamp_refused(tmp_path):
    wal,limiter=prepare(tmp_path)
    with pytest.raises(StateRejected):wal.begin('h',datetime(2026,10,10))
    original=wal.path.read_bytes();wal.path.unlink();target=tmp_path/'target';target.write_bytes(original);wal.path.symlink_to(target)
    with pytest.raises(StateRejected):wal.read()
    assert target.read_bytes()==original


def test_expired_snapshot_pending_not_auto_cleared(tmp_path):
    wal,limiter=prepare(tmp_path);wal.begin('h',NOW)
    with pytest.raises(StateRejected):IntentBoundHostRateLimiter(tmp_path,'t',clock=lambda:NOW+timedelta(days=2))
    assert wal.read()['pending'] is not None


@pytest.mark.parametrize('bootstrap',[True,False])
def test_binding_rejects_bootstrap_kwarg_before_snapshot_creation(tmp_path,bootstrap):
    wal=DispatchIntentWAL(tmp_path,'t');wal.provision()
    with pytest.raises(StateRejected,match='bootstrap kwarg'):IntentBoundHostRateLimiter(tmp_path,'t',bootstrap=bootstrap,clock=lambda:NOW)
    assert not list(tmp_path.glob('m18-pacing-*'))
