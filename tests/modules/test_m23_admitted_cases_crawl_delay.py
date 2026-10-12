# Offline only (httpx.MockTransport); sleep is injected, so no real waiting and no live HTTP.
from urllib.parse import urlparse
import httpx
import pytest
from app.modules.m23_study_abroad.admitted_cases import USER_AGENT, cases
from app.modules.m23_study_abroad.admitted_cases_bounded import (MAX_CRAWL_DELAY_SECONDS, SAFE_STATUSES,
                                                                 fetch_case_metadata_bounded, HostPacer)

HTML = {'content-type': 'text/html'}
PAGE = lambda: httpx.Response(200, headers=HTML, text='<title>t</title>')
PAGE_PATH = urlparse(next(r for r in cases() if r['id'] == 'hamilton')['url']).path
TOKEN = USER_AGENT.split('/')[0]          # the product token robots.txt groups match on


def run(robots_text, **kw):
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, text=robots_text) if request.url.path == '/robots.txt' else PAGE()
    kw.setdefault('pacer', HostPacer())   # these tests exercise per-call behavior only
    row = fetch_case_metadata_bounded('hamilton', httpx.MockTransport(handler), sleep=lambda s: calls.append('sleep:%g' % s), **kw)
    return row, calls


def test_default_cap_is_30_and_status_is_in_closed_set():
    assert MAX_CRAWL_DELAY_SECONDS == 30 and 'crawl_delay_too_long' in SAFE_STATUSES


def test_crawl_delay_is_waited_between_robots_and_page():
    row, calls = run('User-agent: *\nCrawl-delay: 5\nAllow: /')
    assert row['live_status'] == 'page_reachable'
    assert calls == ['/robots.txt', 'sleep:5', PAGE_PATH]


def test_no_crawl_delay_means_no_sleep_default_unchanged():
    row, calls = run('User-agent: *\nAllow: /')
    assert row['live_status'] == 'page_reachable' and calls == ['/robots.txt', PAGE_PATH]


def test_boundary_30_is_honored_31_is_skipped():
    row, calls = run('User-agent: *\nCrawl-delay: 30')
    assert row['live_status'] == 'page_reachable' and 'sleep:30' in calls
    row, calls = run('User-agent: *\nCrawl-delay: 31')
    assert row['live_status'] == 'crawl_delay_too_long' and row['crawl_delay_seconds'] == 31
    assert calls == ['/robots.txt']                          # page never requested, nothing slept


def test_specific_agent_group_overrides_star_group():
    robots = 'User-agent: %s\nCrawl-delay: 7\n\nUser-agent: *\nCrawl-delay: 2\n' % TOKEN
    row, calls = run(robots)
    assert 'sleep:7' in calls and 'sleep:2' not in calls


def test_star_group_applies_when_no_specific_group():
    row, calls = run('User-agent: *\nCrawl-delay: 2')
    assert calls == ['/robots.txt', 'sleep:2', PAGE_PATH]


def test_custom_cap_is_respected_and_validated():
    row, calls = run('User-agent: *\nCrawl-delay: 5', max_crawl_delay=3)
    assert row['live_status'] == 'crawl_delay_too_long' and calls == ['/robots.txt']
    row, calls = run('User-agent: *\nCrawl-delay: 5', max_crawl_delay=5)
    assert row['live_status'] == 'page_reachable' and 'sleep:5' in calls
    for bad in (-1, 121, True, 'x', None):
        with pytest.raises(ValueError):
            run('User-agent: *', max_crawl_delay=bad)


def test_disallow_takes_precedence_over_crawl_delay_cap():
    row, calls = run('User-agent: *\nCrawl-delay: 99\nDisallow: /')
    assert row['live_status'] == 'robots_denied' and calls == ['/robots.txt']


@pytest.mark.parametrize('line', ['Crawl-delay: abc', 'Crawl-delay: -4', 'Crawl-delay: 2.5', 'Crawl-delay:'])
def test_unparseable_delay_values_are_not_treated_as_a_delay(line):
    row, calls = run('User-agent: *\n%s\nAllow: /' % line)
    assert row['live_status'] == 'page_reachable' and calls == ['/robots.txt', PAGE_PATH]


def test_crawl_delay_zero_does_not_sleep():
    row, calls = run('User-agent: *\nCrawl-delay: 0')
    assert calls == ['/robots.txt', PAGE_PATH]


def test_result_contains_no_robots_text_or_error_detail():
    row, _ = run('User-agent: *\nCrawl-delay: 99')
    assert 'User-agent' not in str(row) and set(row) >= {'id', 'live_status', 'crawl_delay_seconds'}
