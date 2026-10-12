"""Row 54: ten added read-only public RSS sources. Offline parse tests plus opt-in live smoke."""
import os
import pytest
from app.modules.m01_opportunity_discovery.student_platforms import BY_ID, PlatformUnavailable, discover
import pathlib
import httpx

FIX = pathlib.Path(__file__).parent / 'fixtures' / 'rss_row54'


def fake_client(url, body, content_type='text/html', status=200):
    """Transport keyed by URL: any request to a different URL gets 404 and fails the discover call."""
    def handler(request):
        if str(request.url) != url:
            return httpx.Response(404, text='wrong url', request=request)
        return httpx.Response(status, text=body, headers={'content-type': content_type}, request=request)
    return httpx.Client(transport=httpx.MockTransport(handler))

NEW = ['opportunitydesk', 'fundsforngos', 'scholarshipsandgrants', 'opportunitiescorners', 'scholarshipamerica',
       'nsffunding', 'petersons', 'collegeconfidential', 'thecollegesolution', 'topuniversities']
RSS = '''<?xml version="1.0"?><rss><channel>
<item><title>STEM fellowship open</title><link>https://example.org/a</link><description>apply now</description></item>
<item><title>Arts award</title><link>http://example.org/insecure</link></item>
<item><title>Leaky</title><link>https://user:pw@example.org/x</link></item>
</channel></rss>'''


@pytest.mark.parametrize('pid', NEW)
def test_new_source_is_rss_https_and_labeled(pid):
    p = BY_ID[pid]
    assert p.mode == 'rss' and p.url.startswith('https://') and p.reason


@pytest.mark.parametrize('pid', NEW)
def test_new_source_parses_and_drops_unsafe_links(pid):
    with fake_client(BY_ID[pid].url, RSS, 'application/rss+xml') as c:
        r = discover(pid, 'STEM fellowship', client=c)
    assert [i['url'] for i in r['items']] == ['https://example.org/a']
    assert r['items'][0]['platform'] == pid and r['items'][0]['score'] > 0


@pytest.mark.parametrize('pid', NEW)
def test_new_source_parses_its_captured_real_feed_shape(pid):
    # Fixture = first 2 items of the real feed as fetched 2026-10-12 (rebuilt only by hand).
    body = (FIX / f'{pid}.xml').read_text()
    with fake_client(BY_ID[pid].url, body, 'application/rss+xml') as c:
        r = discover(pid, 'scholarship', client=c)
    assert len(r['items']) == 2 and all(i['url'].startswith('https://') for i in r['items'])


@pytest.mark.parametrize('pid', NEW)
def test_new_source_fails_closed_on_challenge_and_html(pid):
    with fake_client(BY_ID[pid].url, 'blocked', 'text/html', 403) as c:
        with pytest.raises(PlatformUnavailable): discover(pid, client=c)
    with fake_client(BY_ID[pid].url, '<html>challenge</html>', 'text/html') as c:
        with pytest.raises(PlatformUnavailable): discover(pid, client=c)


@pytest.mark.skipif(os.getenv('ATLAS_M01_LIVE_SMOKE') != '1', reason='opt-in live network')
@pytest.mark.parametrize('pid', NEW)
def test_live_smoke(pid):
    r = discover(pid, 'scholarship', limit=5)
    assert r['items'] and all(i['url'].startswith('https://') for i in r['items'])


def test_fixture_provenance_is_recorded_and_matches_files():
    import hashlib, json
    prov = json.loads((FIX / 'PROVENANCE.json').read_text())
    assert set(prov) == set(NEW)
    for pid, rec in prov.items():
        assert rec['source_url'] == BY_ID[pid].url and rec['fetched_at'] and len(rec['original_sha256']) == 64
        assert hashlib.sha256((FIX / f'{pid}.xml').read_bytes()).hexdigest() == rec['fixture_sha256']
        assert 'NOT the original bytes' in rec['derivation']


def test_transport_is_keyed_to_url():
    with fake_client(BY_ID['petersons'].url, RSS, 'application/rss+xml') as c:
        with pytest.raises(PlatformUnavailable):
            discover('opportunitydesk', client=c)
