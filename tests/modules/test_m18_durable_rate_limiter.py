from datetime import datetime,timezone,timedelta
import pytest
from app.modules.m18_side_hustle_scraper.durable_rate_limiter import DurableHostRateLimiter
from app.modules.m18_side_hustle_scraper.lane_rate_limit_state import StateRejected


def test_restart_retains_retry_after_success_cannot_clear_it(tmp_path):
    now=datetime(2026,10,10,tzinfo=timezone.utc);clock=lambda:now
    limiter=DurableHostRateLimiter(tmp_path,'t',bootstrap=True,clock=clock)
    limiter.begin_request('h');limiter.honor_retry_after('h',120);limiter.record_success('h')
    other=DurableHostRateLimiter(tmp_path,'t',clock=clock)
    assert other.check('h')==120
    now+=timedelta(seconds=20)
    assert other.begin_request('h')==100
    now+=timedelta(seconds=101)
    assert other.begin_request('h')==0


def test_missing_restore_and_repeat_bootstrap_refused(tmp_path):
    with pytest.raises(StateRejected):DurableHostRateLimiter(tmp_path,'t')
    DurableHostRateLimiter(tmp_path,'t',bootstrap=True)
    with pytest.raises(StateRejected):DurableHostRateLimiter(tmp_path,'t',bootstrap=True)
    with pytest.raises(StateRejected):DurableHostRateLimiter(tmp_path,'other')


def test_persistence_failure_blocks_current_instance_only(tmp_path,monkeypatch):
    from app.modules.m18_side_hustle_scraper import durable_rate_limiter as m
    limiter=DurableHostRateLimiter(tmp_path,'t',bootstrap=True)
    monkeypatch.setattr(m,'write_snapshot',lambda *a,**k:(_ for _ in ()).throw(StateRejected('injected')))
    with pytest.raises(StateRejected):limiter.begin_request('h')
    with pytest.raises(StateRejected):limiter.begin_request('h')


def test_expired_snapshot_not_reset(tmp_path):
    now=datetime(2026,10,10,tzinfo=timezone.utc)
    limiter=DurableHostRateLimiter(tmp_path,'t',bootstrap=True,clock=lambda:now,retention_seconds=1)
    now+=timedelta(seconds=2)
    with pytest.raises(StateRejected):limiter.begin_request('h')


def test_failed_save_fresh_instance_loads_previous_snapshot_residue(tmp_path,monkeypatch):
    from app.modules.m18_side_hustle_scraper import durable_rate_limiter as m
    now=datetime(2026,10,10,tzinfo=timezone.utc)
    first=DurableHostRateLimiter(tmp_path,'t',bootstrap=True,clock=lambda:now)
    original=m.write_snapshot
    monkeypatch.setattr(m,'write_snapshot',lambda *a,**k:(_ for _ in ()).throw(StateRejected('injected')))
    with pytest.raises(StateRejected):first.begin_request('h')
    monkeypatch.setattr(m,'write_snapshot',original)
    fresh=DurableHostRateLimiter(tmp_path,'t',clock=lambda:now)
    assert fresh.begin_request('h')==0 # explicit limitation, not desired crash safety
