"""Read-only student sources: parsing, capability boundaries and live opt-in smoke."""
import os

import httpx
import pytest

from app.modules.m01_opportunity_discovery.student_platforms import (
    BY_ID, PLATFORMS, PlatformUnavailable, _safe_target, discover,
)


def fake_client(url, body, content_type='text/html', status=200):
    return httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, text=body, headers={'content-type': content_type}, request=request)
    ))


def test_seventeen_named_platforms_are_unique_and_capability_labeled():
    assert len(PLATFORMS) == len(BY_ID) == 17
    assert {'ripplematch', 'simplify', 'raiseme', 'bold', 'fastweb', 'devpost', 'challengerocket'} <= BY_ID.keys()
    assert {p.mode for p in PLATFORMS} == {'rss', 'html', 'launch_only'}
    for p in PLATFORMS:
        assert p.url.startswith('https://')
        assert p.mode != 'launch_only' or p.reason


@pytest.mark.parametrize('platform', [p.id for p in PLATFORMS if p.mode == 'launch_only'])
def test_launch_only_never_calls_network(platform):
    class Exploding:
        def get(self, url): raise AssertionError('should not fetch')
    result = discover(platform, client=Exploding())
    assert result['mode'] == 'launch_only' and result['launch_url'] == BY_ID[platform].url
    assert result['items'] == [] and result['scanned_at'] is None


@pytest.mark.parametrize('platform,href', [
    ('fastweb', '/college-scholarships/scholarships/1234-stem-award'),
    ('challengerocket', '/hackathon-future-smart-city-26'),
    ('mlh', 'https://events.mlh.io/events/14418-hack-coms-2026?utm_source=mlh'),
    ('internshala', '/internship/detail/data-analyst-123'),
])
def test_html_sources_parse_actual_item_paths(platform, href):
    p = BY_ID[platform]
    html = (f'<html><div class="challenge-card__title"><h3><a href="{href}">STEM Hackathon Opportunity</a></h3></div>'
            f'<a href="https://evil.example/apply">Evil Listing</a></html>') if platform == 'challengerocket' else (
            f'<html><h3><a href="{href}">STEM Hackathon Opportunity</a></h3>'
            f'<a href="https://evil.example/apply">Evil Listing</a></html>')
    with fake_client(p.url, html) as client:
        result = discover(platform, 'STEM hackathon', client=client)
    assert len(result['items']) == 1
    item = result['items'][0]
    assert item['title'] == 'STEM Hackathon Opportunity' and item['score'] > 0
    assert item['source_url'] == p.url and 'utm_' not in item['url']


def test_rss_parser_ranks_and_rejects_unsafe_links():
    p = BY_ID['scholarshiproar']
    rss = '''<?xml version="1.0"?><rss><channel>
    <item><title>History scholarship</title><link>https://scholarshiproar.com/a</link></item>
    <item><title>STEM scholarship</title><link>https://scholarshiproar.com/b</link></item>
    <item><title>Bad</title><link>http://unsafe.example/</link></item>
    </channel></rss>'''
    with fake_client(p.url, rss, 'application/rss+xml') as client:
        items = discover(p.id, 'STEM', client=client)['items']
    assert len(items) == 2 and items[0]['title'] == 'STEM scholarship'


def test_block_challenge_and_malformed_payload_are_not_silent_success():
    p = BY_ID['fastweb']
    with fake_client(p.url, '<h1>Rate limited</h1>', status=429) as client:
        with pytest.raises(PlatformUnavailable, match='429'): discover(p.id, client=client)
    with fake_client(p.url, '<html>No listings</html>') as client:
        with pytest.raises(PlatformUnavailable, match='no listing'): discover(p.id, client=client)


def test_external_redirects_and_non_https_targets_rejected():
    p = BY_ID['fastweb']
    assert _safe_target(p, 'http://www.fastweb.com/college-scholarships/scholarships/123-x') is None
    assert _safe_target(p, 'https://bad.example/college-scholarships/scholarships/123-x') is None
    assert _safe_target(p, 'https://user:pass@www.fastweb.com/college-scholarships/scholarships/123-x') is None
    assert _safe_target(p, 'https://www.fastweb.com/member/123') is None


@pytest.mark.skipif(os.getenv('ATLAS_M01_LIVE_SMOKE') != '1', reason='opt-in live source check')
@pytest.mark.parametrize('platform', [p.id for p in PLATFORMS if p.mode != 'launch_only'])
def test_live_public_discovery(platform):
    # A live failure stays a failure, never replaced with canned records.
    result = discover(platform, limit=1)
    assert result['items'] and result['items'][0]['url'].startswith('https://')
