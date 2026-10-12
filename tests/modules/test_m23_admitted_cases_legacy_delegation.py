# Offline only (httpx.MockTransport); sleep is injected, so no real waiting and no live HTTP.
import inspect
import httpx
import pytest
from app.modules.m23_study_abroad import admitted_cases, admitted_cases_bounded, routes

HTML = {'content-type': 'text/html'}


def run(robots_text, **kw):
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text=robots_text)
        return httpx.Response(200, headers=HTML, text='<title>t</title>')
    row = admitted_cases.fetch_case_metadata('hamilton', httpx.MockTransport(handler),
                                             sleep=lambda s: calls.append('sleep:%g' % s), **kw)
    return row, calls


def test_legacy_helper_waits_the_robots_crawl_delay():
    row, calls = run('User-agent: *\nCrawl-delay: 5\nAllow: /')
    assert row['live_status'] == 'page_reachable'
    assert calls[0] == '/robots.txt' and calls[1] == 'sleep:5' and len(calls) == 3


def test_legacy_helper_skips_delay_above_cap_without_requesting_page():
    row, calls = run('User-agent: *\nCrawl-delay: 31\nAllow: /')
    assert row['live_status'] == 'crawl_delay_too_long' and row['crawl_delay_seconds'] == 31
    assert calls == ['/robots.txt']


def test_legacy_helper_honors_boundary_30():
    row, calls = run('User-agent: *\nCrawl-delay: 30\nAllow: /')
    assert row['live_status'] == 'page_reachable' and 'sleep:30' in calls


def test_legacy_helper_passes_cap_through():
    row, calls = run('User-agent: *\nCrawl-delay: 31\nAllow: /', max_crawl_delay=60)
    assert row['live_status'] == 'page_reachable' and 'sleep:31' in calls
    with pytest.raises(ValueError):
        run('User-agent: *\nAllow: /', max_crawl_delay=121)


def test_legacy_helper_uses_the_given_transport_and_case():
    seen = []
    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(404)
    row = admitted_cases.fetch_case_metadata('hamilton', httpx.MockTransport(handler))
    assert row['live_status'] == 'robots_unverified' and row['id'] == 'hamilton'
    assert len(seen) == 1 and seen[0].endswith('/robots.txt')


def test_legacy_helper_is_a_pure_delegate_to_the_bounded_helper(monkeypatch):
    got = {}
    def fake(case_id, transport=None, **kw):
        got.update(case_id=case_id, transport=transport, kw=kw)
        return {'live_status': 'sentinel'}
    monkeypatch.setattr(admitted_cases_bounded, 'fetch_case_metadata_bounded', fake)
    t = httpx.MockTransport(lambda r: httpx.Response(500))
    assert admitted_cases.fetch_case_metadata('mit', t, page_limit=7)['live_status'] == 'sentinel'
    assert got == {'case_id': 'mit', 'transport': t, 'kw': {'page_limit': 7}}


def test_legacy_unknown_case_still_raises_keyerror():
    with pytest.raises(KeyError):
        admitted_cases.fetch_case_metadata('not-in-the-index', httpx.MockTransport(lambda r: httpx.Response(500)))


def test_legacy_module_has_no_own_http_client():
    assert 'httpx.Client' not in inspect.getsource(admitted_cases.fetch_case_metadata)
    assert 'RobotFileParser' not in inspect.getsource(admitted_cases.fetch_case_metadata)


def test_routes_bind_the_bounded_helper():
    assert routes.fetch_case_metadata is admitted_cases_bounded.fetch_case_metadata_bounded
