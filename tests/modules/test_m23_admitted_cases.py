import httpx
import pytest
from app.modules.m23_study_abroad.admitted_cases import cases, search_cases, fetch_case_metadata


def test_twenty_distinct_public_case_sites_with_provenance():
    entries = cases()
    assert len(entries) == 20
    assert len({e['publisher'] for e in entries}) == 20
    assert all(e['checked_on'] == '2026-09-25' and e['scope_note'] for e in entries)
    assert all(e['access'] == 'public_metadata_only' for e in entries)
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
