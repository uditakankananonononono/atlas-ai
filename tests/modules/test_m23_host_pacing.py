# Offline only: httpx.MockTransport, an injected fake clock and an injected sleep that advances it. No live HTTP.
# Concurrency tests use real threads but only MockTransport, gates (Events) and sub-second real timeouts.
import threading
import time
import httpx
import pytest
from app.modules.m23_study_abroad.admitted_cases_bounded import HostPacer, SAFE_STATUSES, fetch_case_metadata_bounded

HTML = {'content-type': 'text/html'}
HOST = 'www.hamilton.edu'


class Clock:
    def __init__(self):
        self.t = 1000.0
        self.slept = []
    def now(self):
        return self.t
    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def prime(p, host, delay):
    ok, _ = p.acquire(host, 0)
    assert ok
    p.release(host, delay)


def call(clock, pacer, robots='User-agent: *\nCrawl-delay: 10\nAllow: /', case='hamilton', **kw):
    def handler(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text=robots)
        return httpx.Response(200, headers=HTML, text='<title>t</title>')
    return fetch_case_metadata_bounded(case, httpx.MockTransport(handler), sleep=clock.sleep, pacer=pacer, **kw)


def test_first_call_to_a_host_is_not_delayed_by_the_ledger():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    assert call(c, p)['live_status'] == 'page_reachable'
    assert c.slept == [10]                     # only the in-call robots->page delay


def test_second_call_waits_out_the_host_delay_since_the_first_finished():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    call(c, p)
    c.slept.clear()
    assert call(c, p)['live_status'] == 'page_reachable'
    assert c.slept == [10, 10]                 # ledger wait, then the in-call delay


def test_wait_shrinks_by_elapsed_time_and_vanishes_when_elapsed():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    call(c, p)
    c.t += 4; c.slept.clear()
    call(c, p)
    assert c.slept[0] == pytest.approx(6)
    c.t += 10; c.slept.clear()
    call(c, p)
    assert c.slept == [10]


def test_host_without_crawl_delay_is_never_spaced():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    for _ in range(3):
        assert call(c, p, robots='User-agent: *\nAllow: /')['live_status'] == 'page_reachable'
    assert c.slept == []


def test_different_hosts_do_not_pace_each_other():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    call(c, p, case='hamilton'); c.slept.clear()
    call(c, p, case='dartmouth')
    assert c.slept == [10]


def test_ledger_records_long_delay_when_page_skipped_and_refuses_over_cap():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    assert call(c, p, robots='User-agent: *\nCrawl-delay: 31')['live_status'] == 'crawl_delay_too_long'
    ok, wait = p.acquire(HOST, 1000)
    assert ok and wait == pytest.approx(31)
    p.release(HOST, None)
    row = call(c, p, robots='User-agent: *\nAllow: /', max_pace_wait=30)
    assert row['live_status'] == 'host_pacing_busy' and row['retry_after_seconds'] == 31


def test_robots_denied_host_is_released_and_keeps_no_new_delay():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    assert call(c, p, robots='User-agent: *\nCrawl-delay: 5\nDisallow: /')['live_status'] == 'robots_denied'
    assert HOST not in p._delay and HOST not in p._busy and HOST in p._last_end


def test_failed_fetch_releases_the_host_and_keeps_last_delay():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    prime(p, HOST, 7)
    c.t += 100
    def boom(request):
        raise httpx.ConnectError('x')
    row = fetch_case_metadata_bounded('hamilton', httpx.MockTransport(boom), sleep=c.sleep, pacer=p)
    assert row['live_status'] == 'fetch_failed' and HOST not in p._busy
    ok, wait = p.acquire(HOST, 1000)
    assert ok and wait == pytest.approx(7)


def test_exception_in_call_still_releases_the_host():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    def raiser(s):
        raise RuntimeError('boom')
    with pytest.raises(RuntimeError):
        fetch_case_metadata_bounded('hamilton', httpx.MockTransport(lambda r: httpx.Response(200, text='User-agent: *\nCrawl-delay: 3')),
                                    sleep=raiser, pacer=p)
    assert HOST not in p._busy


def test_spacing_over_cap_is_refused_without_a_request_or_sleep():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    prime(p, HOST, 100)
    seen = []
    row = fetch_case_metadata_bounded('hamilton', httpx.MockTransport(lambda r: seen.append(r) or httpx.Response(200)),
                                      sleep=c.sleep, pacer=p, max_pace_wait=60)
    assert row['live_status'] == 'host_pacing_busy' and row['retry_after_seconds'] == 100
    assert seen == [] and c.slept == [] and 'host_pacing_busy' in SAFE_STATUSES
    assert HOST not in p._busy                      # a refusal does not hold the host


def test_spacing_exactly_at_cap_is_admitted():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    prime(p, HOST, 60)
    row = call(c, p, robots='User-agent: *\nAllow: /', max_pace_wait=60)
    assert row['live_status'] == 'page_reachable' and c.slept == [60]


def test_max_pace_wait_is_validated():
    c = Clock()
    for bad in (-1, 601, True, 'x', None):
        with pytest.raises(ValueError):
            call(c, HostPacer(c.now), max_pace_wait=bad)


def test_acquire_busy_host_times_out_and_does_not_steal_it():
    p = HostPacer()
    ok, _ = p.acquire('h', 1)
    assert ok
    start = time.monotonic()
    ok2, retry = p.acquire('h', 0.2)
    assert not ok2 and 0.15 <= time.monotonic() - start < 2 and retry >= 1
    assert 'h' in p._busy
    p.release('h', None)
    assert 'h' not in p._busy
    assert p.acquire('h', 0)[0]


def test_release_wakes_a_waiter():
    p = HostPacer()
    assert p.acquire('h', 1)[0]
    got = []
    t = threading.Thread(target=lambda: got.append(p.acquire('h', 5)))
    t.start()
    time.sleep(0.1)
    assert got == []
    p.release('h', None)
    t.join(3)
    assert got and got[0][0] is True


def test_default_shared_pacer_spaces_consecutive_calls_without_an_explicit_pacer(monkeypatch):
    from app.modules.m23_study_abroad.admitted_cases_bounded import DEFAULT_PACER
    monkeypatch.setattr(DEFAULT_PACER, '_max_queue', .3)    # a leaked in-flight mark must fail fast, not park for 60s
    DEFAULT_PACER.reset()
    slept = []
    def handler(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nCrawl-delay: 10')
        return httpx.Response(200, headers=HTML, text='<title>t</title>')
    for _ in range(2):
        fetch_case_metadata_bounded('hamilton', httpx.MockTransport(handler), sleep=slept.append)
    assert slept[0] == 10 and 9 < slept[1] <= 10 and slept[2] == 10
    DEFAULT_PACER.reset()


def test_default_pacer_reset_clears_everything(monkeypatch):
    from app.modules.m23_study_abroad.admitted_cases_bounded import DEFAULT_PACER
    monkeypatch.setattr(DEFAULT_PACER, '_max_queue', .3)
    prime(DEFAULT_PACER, 'zz.example', 3)
    assert DEFAULT_PACER.acquire('zz.example', 100)[1] > 0
    DEFAULT_PACER.release('zz.example', None)
    DEFAULT_PACER.reset()
    ok, wait = DEFAULT_PACER.acquire('zz.example', 0)
    assert ok and wait == 0
    DEFAULT_PACER.release('zz.example', None)


# ---- A/B overlap regression and single-flight first robots fetch ------------------------------------------------
def test_ab_overlap_regression_b_never_starts_before_a_finishes_and_waits_the_delay_after():
    """Delay 10 learned at t=1000. A is admitted at 1010 and finishes at 1025; B must start >= A_end + 10."""
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    c.t = 1000.0; prime(p, HOST, 10)
    events = []
    a_in = threading.Event(); a_go = threading.Event()
    def a_handler(request):
        if request.url.path == '/robots.txt':
            events.append(('A', 'robots', c.t)); a_in.set(); assert a_go.wait(5)
            return httpx.Response(200, text='User-agent: *\nCrawl-delay: 10\nAllow: /')
        return httpx.Response(200, headers=HTML, text='<title>t</title>')
    def b_handler(request):
        events.append(('B', request.url.path, c.t))
        return httpx.Response(200, headers=HTML, text='<title>t</title>') if request.url.path != '/robots.txt' else httpx.Response(200, text='User-agent: *\nAllow: /')
    c.t = 1010.0
    ta = threading.Thread(target=lambda: fetch_case_metadata_bounded('hamilton', httpx.MockTransport(a_handler), sleep=lambda s: None, pacer=p))
    ta.start(); assert a_in.wait(5)
    resB = []
    tb = threading.Thread(target=lambda: resB.append(fetch_case_metadata_bounded('hamilton', httpx.MockTransport(b_handler), sleep=c.sleep, pacer=p)))
    tb.start(); time.sleep(0.15)
    assert [e for e in events if e[0] == 'B'] == []          # B is parked while A is in flight
    c.t = 1025.0; a_go.set(); ta.join(5); tb.join(5)
    b_first = next(e for e in events if e[0] == 'B')
    assert b_first[2] >= 1025.0 + 10                            # B started a full delay after A finished
    assert resB and resB[0]['live_status'] == 'page_reachable' and c.slept[0] == pytest.approx(10)


def test_concurrent_first_calls_to_a_fresh_host_are_single_flight():
    p = HostPacer(max_queue=5)
    lock = threading.Lock(); state = {'now': 0, 'max': 0, 'robots': 0}
    def handler(request):
        with lock:
            state['now'] += 1; state['max'] = max(state['max'], state['now'])
            if request.url.path == '/robots.txt':
                state['robots'] += 1
        time.sleep(0.03)
        with lock:
            state['now'] -= 1
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nAllow: /')
        return httpx.Response(200, headers=HTML, text='<title>t</title>')
    out = []
    start = threading.Barrier(5)
    def work():
        start.wait()
        out.append(fetch_case_metadata_bounded('hamilton', httpx.MockTransport(handler), sleep=lambda s: None, pacer=p)['live_status'])
    ts = [threading.Thread(target=work) for _ in range(5)]
    [t.start() for t in ts]; [t.join(10) for t in ts]
    assert out == ['page_reachable'] * 5
    assert state['max'] == 1 and state['robots'] == 5      # never two requests to the host at once


def test_waiting_callers_use_the_delay_learned_by_the_first_caller():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    results = []
    def handler(request):
        time.sleep(0.02)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nCrawl-delay: 4')
        return httpx.Response(200, headers=HTML, text='<title>t</title>')
    barrier = threading.Barrier(3)
    def work():
        barrier.wait()
        results.append(fetch_case_metadata_bounded('hamilton', httpx.MockTransport(handler), sleep=c.sleep, pacer=p)['live_status'])
    ts = [threading.Thread(target=work) for _ in range(3)]
    [t.start() for t in ts]; [t.join(10) for t in ts]
    assert results == ['page_reachable'] * 3
    # first caller: in-call 4; the two followers each wait 4 (ledger) then 4 (in-call)
    assert sorted(c.slept) == [4, 4, 4, 4, 4]


def test_queue_wait_over_cap_is_refused_busy_with_no_request():
    p = HostPacer()
    assert p.acquire(HOST, 1)[0]            # another call holds the host
    seen = []
    row = fetch_case_metadata_bounded('hamilton', httpx.MockTransport(lambda r: seen.append(r) or httpx.Response(200)),
                                      sleep=lambda s: None, pacer=p, max_pace_wait=0.2)
    assert row['live_status'] == 'host_pacing_busy' and row['retry_after_seconds'] >= 1 and seen == []
    p.release(HOST, None)


def test_exception_in_the_ledger_spacing_sleep_still_releases_the_host():
    c = Clock(); p = HostPacer(c.now, max_queue=.3)
    prime(p, HOST, 5)
    def raiser(s):
        raise RuntimeError('boom')
    with pytest.raises(RuntimeError):
        fetch_case_metadata_bounded('hamilton', httpx.MockTransport(lambda r: httpx.Response(200, text='Allow: /')), sleep=raiser, pacer=p)
    assert HOST not in p._busy


def test_reset_is_refused_while_a_host_is_in_flight_and_changes_nothing():
    c = Clock(); p = HostPacer(c.now)
    prime(p, 'idle.example', 5)
    assert p.acquire('busy.example', 0)[0]
    with pytest.raises(RuntimeError, match='busy.example'):
        p.reset()
    assert 'busy.example' in p._busy and p._delay == {'idle.example': 5.0} and 'idle.example' in p._last_end
    # a second caller is still excluded after the refused reset
    assert p.acquire('busy.example', 0.1)[0] is False
    p.release('busy.example', None)


def test_reset_when_idle_clears_everything_and_force_clears_in_flight():
    c = Clock(); p = HostPacer(c.now)
    prime(p, 'a.example', 5)
    p.reset()
    assert p._delay == {} and p._last_end == {} and p._busy == set()
    assert p.acquire('b.example', 0)[0]
    p.reset(force=True)
    assert p._busy == set()


def test_fresh_pacer_instances_do_not_share_the_ledger():
    c = Clock(); p1 = HostPacer(c.now); p2 = HostPacer(c.now)
    call(c, p1); c.slept.clear()
    call(c, p2)
    assert c.slept == [10]          # p2 knows nothing about p1: only the in-call delay, no ledger wait
