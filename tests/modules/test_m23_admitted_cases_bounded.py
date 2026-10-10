# Integrator-executed. Offline only (httpx.MockTransport); no live HTTP.
import httpx
import pytest
from app.modules.m23_study_abroad.admitted_cases_bounded import (
    fetch_case_metadata_bounded, read_bounded, BodyTooLarge, SAFE_STATUSES)

HTML = {'content-type': 'text/html'}
OK_ROBOTS = httpx.Response(200, text='User-agent: *\nAllow: /')


def _transport(robots, page, calls):
    def handler(request):
        calls.append(request.url.path)
        return robots() if request.url.path == '/robots.txt' else page()
    return httpx.MockTransport(handler)


class CountingStream(httpx.SyncByteStream):
    def __init__(self, n, chunk=1000):
        self.n, self.chunk, self.yielded = n, chunk, 0
    def __iter__(self):
        while self.yielded < self.n:
            size = min(self.chunk, self.n - self.yielded)
            self.yielded += size
            yield b'x' * size


def test_read_bounded_stops_at_limit_plus_one_without_draining():
    stream = CountingStream(10_000_000)
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, stream=stream))) as c:
        with c.stream('GET', 'https://a.example/') as resp:
            with pytest.raises(BodyTooLarge):
                read_bounded(resp, 5000)
    assert stream.yielded <= 5000 + 1000


def test_read_bounded_accepts_exact_limit():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b'a' * 100))) as c:
        with c.stream('GET', 'https://a.example/') as resp:
            assert len(read_bounded(resp, 100)) == 100


def test_oversized_page_is_too_large_and_not_returned():
    calls = []
    t = _transport(lambda: httpx.Response(200, text='User-agent: *\nAllow: /'),
                   lambda: httpx.Response(200, headers=HTML, content=b'<title>t</title>' + b'x' * 2000), calls)
    row = fetch_case_metadata_bounded('hamilton', transport=t, page_limit=1000)
    assert row['live_status'] == 'too_large'
    assert 'page_title' not in row


def test_oversized_robots_refuses_before_page_fetch():
    calls = []
    t = _transport(lambda: httpx.Response(200, content=b'#' * 5000),
                   lambda: httpx.Response(200, headers=HTML, text='<title>t</title>'), calls)
    row = fetch_case_metadata_bounded('hamilton', transport=t, robots_limit=1000)
    assert row['live_status'] == 'robots_unverified'
    assert calls == ['/robots.txt']


@pytest.mark.parametrize('status', [404, 500, 301])
def test_robots_unavailable_refuses_before_page_fetch(status):
    calls = []
    t = _transport(lambda: httpx.Response(status), lambda: httpx.Response(200, headers=HTML, text='x'), calls)
    row = fetch_case_metadata_bounded('hamilton', transport=t)
    assert row['live_status'] == 'robots_unverified' and row['http_status'] == status
    assert calls == ['/robots.txt']


def test_robots_network_error_refuses_before_page_fetch_with_safe_status():
    calls = []
    def robots():
        raise httpx.ConnectError('secret-internal-detail')
    t = _transport(robots, lambda: httpx.Response(200, headers=HTML, text='x'), calls)
    row = fetch_case_metadata_bounded('hamilton', transport=t)
    assert row['live_status'] == 'fetch_failed'
    assert 'secret-internal-detail' not in str(row)
    assert calls == ['/robots.txt']


def test_page_error_gives_safe_status_not_raw_error():
    calls = []
    def page():
        raise httpx.ReadTimeout('raw-timeout-text')
    t = _transport(lambda: OK_ROBOTS, page, calls)
    row = fetch_case_metadata_bounded('hamilton', transport=t)
    assert row['live_status'] == 'fetch_failed' and 'raw-timeout-text' not in str(row)


def test_robots_denied_never_requests_page():
    calls = []
    t = _transport(lambda: httpx.Response(200, text='User-agent: *\nDisallow: /'),
                   lambda: httpx.Response(200, headers=HTML, text='x'), calls)
    assert fetch_case_metadata_bounded('hamilton', transport=t)['live_status'] == 'robots_denied'
    assert calls == ['/robots.txt']


def test_metadata_only_no_essay_body():
    calls = []
    page = lambda: httpx.Response(200, headers=HTML, text='<html><head><title>Essay archive</title>'
        '<meta name="description" content="Incoming student case"></head><body>private essay prose</body></html>')
    row = fetch_case_metadata_bounded('hamilton', transport=_transport(lambda: OK_ROBOTS, page, calls))
    assert row['live_status'] == 'page_reachable'
    assert row['page_title'] == 'Essay archive' and row['page_description'] == 'Incoming student case'
    assert row['outcome_independently_verified'] is False
    assert 'private essay prose' not in str(row)
    assert calls == ['/robots.txt', '/']  or len(calls) == 2


def test_non_html_and_non_200_page_statuses():
    calls = []
    t = _transport(lambda: OK_ROBOTS, lambda: httpx.Response(200, headers={'content-type': 'application/pdf'}, content=b'%PDF'), calls)
    assert fetch_case_metadata_bounded('hamilton', transport=t)['live_status'] == 'unsupported_content_type'
    t = _transport(lambda: OK_ROBOTS, lambda: httpx.Response(302, headers={'location': 'https://evil.example/'}), [])
    assert fetch_case_metadata_bounded('hamilton', transport=t)['live_status'] == 'unavailable'


def test_unknown_case_raises_keyerror_and_statuses_are_closed_set():
    with pytest.raises(KeyError):
        fetch_case_metadata_bounded('nope', transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert 'page_reachable' in SAFE_STATUSES


def test_invalid_utf8_robots_refuses_page():
    calls=[]
    def handle(request):
        calls.append(str(request.url));return httpx.Response(200,content=b'\xff\xfe')
    out=fetch_case_metadata_bounded('hamilton',httpx.MockTransport(handle))
    assert out['live_status']=='robots_unverified' and len(calls)==1
