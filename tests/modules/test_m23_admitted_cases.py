import httpx
import pytest
from app.modules.m23_study_abroad.admitted_cases import cases, search_cases, fetch_case_metadata, reading_route


def test_twenty_distinct_public_case_sites_with_provenance():
    entries = cases()
    assert len(entries) == 20
    assert len({e['publisher'] for e in entries}) == 20
    assert all(e['checked_on'] == '2026-09-25' and e['scope_note'] for e in entries)
    assert all(e['access'] == 'public_link_only' and e['reading_mode'] == 'publisher_page' for e in entries)
    assert search_cases('Cornell')[0]['id'] in {'cornell', 'collegetransitions'}
    assert search_cases(evidence_type='institution_published_essay')
    assert search_cases('no match') == []


def test_live_metadata_respects_robots_and_never_returns_essay():
    calls = []
    def handler(request):
        calls.append(str(request.url))
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nAllow: /')
        return httpx.Response(200, headers={'content-type': 'text/html'},
                              text='<html><head><title>Essay archive</title><meta name="description" content="Incoming student case"></head><body>private essay prose</body></html>')
    row = fetch_case_metadata('hamilton', transport=httpx.MockTransport(handler))
    assert row['live_status'] == 'page_reachable'
    assert row['page_title'] == 'Essay archive'
    assert row['page_description'] == 'Incoming student case'
    assert 'private essay prose' not in str(row)
    assert len(calls) == 2
    assert not row['outcome_independently_verified']


def test_missing_robots_denied_or_redirects_do_not_fetch_page():
    for status, expected in [(404, 'robots_unverified'), (200, 'robots_denied')]:
        calls = []
        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(status, text='User-agent: *\nDisallow: /' if status == 200 else '')
        row = fetch_case_metadata('hamilton', transport=httpx.MockTransport(handler))
        assert row['live_status'] == expected
        assert len(calls) == 1
    def redirect(request):
        return httpx.Response(302, headers={'location': 'https://another.example/path'})
    assert fetch_case_metadata('hamilton', transport=httpx.MockTransport(redirect))['live_status'] == 'robots_unverified'
    with pytest.raises(KeyError):
        fetch_case_metadata('not-in-the-index', transport=httpx.MockTransport(redirect))


def test_reader_returns_source_without_touching_site():
    row = reading_route('hamilton')
    assert row['live_status'] == 'source_only'
    assert row['url'].startswith('https://www.hamilton.edu/')
    assert 'essay_text' not in row
    with pytest.raises(KeyError): reading_route('not-in-index')


def _tracking_transport(pulled, page_bytes):
    import httpx as _h
    def handler(request):
        if request.url.path == '/robots.txt':
            return _h.Response(200, text='User-agent: *\nAllow: /\n')
        def stream():
            sent = 0
            while sent < page_bytes:
                chunk = b'x' * min(65536, page_bytes - sent)
                sent += len(chunk)
                pulled[0] = sent
                yield chunk
        return _h.Response(200, headers={'content-type': 'text/html'}, content=stream())
    return _h.MockTransport(handler)

def test_page_transfer_capped_mid_stream():
    # KILL: the size gate was post-download - 1.5MB was consumed before
    # too_large. Now the read aborts just past the cap.
    import httpx, app.modules.m23_study_abroad.admitted_cases as ac
    pulled = [0]
    row = ac.fetch_case_metadata('hamilton', transport=_tracking_transport(pulled, 3_000_000))
    assert row['live_status'] == 'too_large'
    assert pulled[0] <= 1_000_000 + 65536

def test_robots_over_cap_is_unverified_not_allowed():
    # KILL: robots.txt previously had no size gate at all.
    import httpx, app.modules.m23_study_abroad.admitted_cases as ac
    def handler(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(200, content=b'x' * (300 * 1024))
        return httpx.Response(200, text='<html><title>t</title></html>',
                              headers={'content-type': 'text/html'})
    row = ac.fetch_case_metadata('hamilton', transport=httpx.MockTransport(handler))
    assert row['live_status'] == 'robots_unverified'

def test_aggregate_deadline_status(monkeypatch):
    # KILL: 8s was a per-phase HTTP timeout, not an aggregate deadline.
    import httpx, app.modules.m23_study_abroad.admitted_cases as ac
    clock = iter([0.0] + [100.0] * 1000)
    monkeypatch.setattr(ac.time, 'monotonic', lambda: next(clock))
    def handler(request):
        return httpx.Response(200, content=b'x' * 100)
    row = ac.fetch_case_metadata('hamilton', transport=httpx.MockTransport(handler))
    assert row['live_status'] in {'robots_unverified', 'too_large', 'deadline_exceeded'}

def test_catalog_returns_fresh_copies_mutation_cannot_retarget():
    # KILL: the cached catalog list was shared and mutable in-process.
    import app.modules.m23_study_abroad.admitted_cases as ac
    original_len = len(ac.cases())
    mutated = ac.cases()
    mutated.append({'id': 'evil', 'url': 'https://evil.example/x', 'evidence_type': 'x'})
    mutated[0]['url'] = 'https://evil.example/retarget'
    fresh = ac.cases()
    assert len(fresh) == original_len
    assert all(row['url'] != 'https://evil.example/retarget' for row in fresh)


def test_empty_page_past_deadline_is_not_reachable(monkeypatch):
    # KILL: an EOF-time deadline breach used to return page_reachable.
    import httpx, app.modules.m23_study_abroad.admitted_cases as ac
    calls = iter([0.0] * 4 + [100.0] * 1000)
    monkeypatch.setattr(ac.time, 'monotonic', lambda: next(calls))
    def handler(request):
        return httpx.Response(200, text='<html><title>t</title></html>',
                              headers={'content-type': 'text/html'})
    row = ac.fetch_case_metadata('hamilton', transport=httpx.MockTransport(handler))
    assert row['live_status'] == 'deadline_exceeded'

def test_late_chunk_is_deadline_not_too_large(monkeypatch):
    # KILL: a chunk arriving past the deadline was mislabeled too_large.
    import httpx, app.modules.m23_study_abroad.admitted_cases as ac
    calls = iter([0.0] * 6 + [100.0] * 1000)
    monkeypatch.setattr(ac.time, 'monotonic', lambda: next(calls))
    def handler(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nAllow: /\n')
        return httpx.Response(200, content=b'x' * 10,
                              headers={'content-type': 'text/html'})
    row = ac.fetch_case_metadata('hamilton', transport=httpx.MockTransport(handler))
    assert row['live_status'] == 'deadline_exceeded'

def test_spent_deadline_blocks_page_request(monkeypatch):
    # KILL: no pre-request deadline guard existed; the page fetch always ran.
    import httpx, app.modules.m23_study_abroad.admitted_cases as ac
    requested = []
    calls = iter([0.0, 0.0, 0.0, 0.0] + [100.0] * 1000)
    monkeypatch.setattr(ac.time, 'monotonic', lambda: next(calls))
    def handler(request):
        requested.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nAllow: /\n')
        return httpx.Response(200, text='<html/>', headers={'content-type': 'text/html'})
    row = ac.fetch_case_metadata('hamilton', transport=httpx.MockTransport(handler))
    assert row['live_status'] == 'deadline_exceeded'
    assert requested == ['/robots.txt']
