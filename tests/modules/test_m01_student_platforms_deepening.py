"""Rows 47-54 deepening: exact registry pins and listing-parser behavior for student_platforms. Offline only: every
request goes to an httpx.MockTransport; launch_only rows are asserted to make NO request at all."""
import httpx
import pytest

from app.modules.m01_opportunity_discovery import student_platforms as sp
from app.modules.m01_opportunity_discovery.student_platforms import BY_ID, PlatformUnavailable, discover

PINS = {  # id: (name, url, mode, kind)
    'ripplematch': ('RippleMatch', 'https://ripplematch.com/', 'launch_only', 'job'),
    'simplify': ('Simplify', 'https://simplify.jobs/copilot', 'launch_only', 'job'),
    'raiseme': ('RaiseMe', 'https://www.raiseme.com/', 'launch_only', 'scholarship'),
    'bold': ('Bold.org', 'https://bold.org/scholarships/', 'launch_only', 'scholarship'),
    'fastweb': ('Fastweb', 'https://www.fastweb.com/college-scholarships', 'html', 'scholarship'),
    'devpost': ('Devpost', 'https://devpost.com/hackathons', 'launch_only', 'hackathon'),
    'challengerocket': ('ChallengeRocket', 'https://challengerocket.com/hackathons-and-challenges.html', 'html', 'competition'),
}


def no_request_client():
    def handler(request):
        raise AssertionError('launch_only must not make a request: %s' % request.url)
    return httpx.Client(transport=httpx.MockTransport(handler))


def client_for(url, body, ctype='text/html', status=200):
    def handler(request):
        assert str(request.url) == url
        return httpx.Response(status, content=body if isinstance(body, bytes) else body.encode(),
                              headers={'content-type': ctype}, request=request)
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize('pid', sorted(PINS))
def test_registry_entry_is_pinned_exactly(pid):
    p = BY_ID[pid]
    assert (p.name, p.url, p.mode, p.kind) == PINS[pid]


@pytest.mark.parametrize('pid', ['ripplematch', 'simplify', 'raiseme', 'bold', 'devpost'])
def test_launch_only_rows_return_launch_url_and_no_items_without_any_request(pid):
    p = BY_ID[pid]
    with no_request_client() as c:
        out = discover(pid, 'anything', client=c)
    assert out == {'platform': pid, 'mode': 'launch_only', 'launch_url': p.url, 'reason': p.reason,
                   'items': [], 'scanned_at': None}
    assert p.reason


def test_bold_reason_says_the_rate_limit_challenge_is_not_to_be_evaded():
    assert 'rate-limit challenge' in BY_ID['bold'].reason and 'do not evade' in BY_ID['bold'].reason


FASTWEB_URL = PINS['fastweb'][1]
FASTWEB = '''<html><body>
<h3><a href="/college-scholarships/scholarships/123-big-award?utm=x#top">Big Award Scholarship</a></h3>
<a href="/college-scholarships/scholarships/456-banner-ad">Promoted banner scholarship</a>
<h3><a href="/college-scholarships/scholarships/789-see">See Details</a></h3>
<h3><a href="/college-scholarships/scholarships/1-x">Tiny</a></h3>
<h3><a href="/college-scholarships/other/999-not-a-listing">Not a listing page</a></h3>
<h3><a href="https://evil.example/college-scholarships/scholarships/5-offsite">Offsite listing title</a></h3>
<h3><a href="http://www.fastweb.com/college-scholarships/scholarships/6-plain">Insecure listing title</a></h3>
<h3><a href="https://user:pw@www.fastweb.com/college-scholarships/scholarships/7-cred">Credential link title</a></h3>
</body></html>'''


def test_fastweb_keeps_only_h3_listing_links_on_host_with_clean_urls():
    with client_for(FASTWEB_URL, FASTWEB) as c:
        out = discover('fastweb', client=c)
    assert [i['url'] for i in out['items']] == ['https://www.fastweb.com/college-scholarships/scholarships/123-big-award']
    assert out['items'][0]['title'] == 'Big Award Scholarship'
    assert out['items'][0]['opportunity_kind'] == 'scholarship' and out['items'][0]['platform'] == 'fastweb'


CR_URL = PINS['challengerocket'][1]
CR = '''<html><body>
<nav><a href="/hackathon-nav-link">Navigation hackathon link</a></nav>
<div class="challenge-card__title"><a href="/hackathon-real-one">Real Hackathon One</a></div>
<div class="challenge-card__title"><a href="/hackathon-short">Go</a></div>
<div class="challenge-card__title"><a href="/hackathon-read">Read More</a></div>
<div class="challenge-card__title"><a href="/hackathon-apply">apply now</a></div>
<div class="challenge-card__title"><a href="/about-us">About us page title</a></div>
</body></html>'''


def test_challengerocket_keeps_only_real_cards_with_real_titles():
    with client_for(CR_URL, CR) as c:
        out = discover('challengerocket', client=c)
    assert [(i['title'], i['url']) for i in out['items']] == [('Real Hackathon One', 'https://challengerocket.com/hackathon-real-one')]


def rss(n):
    items = ''.join('<item><title>Item %d</title><link>https://example.org/%d</link><description>d</description></item>' % (i, i)
                    for i in range(n))
    return '<?xml version="1.0"?><rss><channel>%s</channel></rss>' % items


U = BY_ID['petersons'].url


def test_rss_dedupes_urls_and_applies_the_limit():
    dup = ('<?xml version="1.0"?><rss><channel><item><title>A one</title><link>https://example.org/a</link></item>'
           '<item><title>A again</title><link>https://example.org/a</link></item></channel></rss>')
    with client_for(U, dup, 'application/rss+xml') as c:
        assert len(discover('petersons', client=c)['items']) == 1
    with client_for(U, rss(10), 'application/rss+xml') as c:
        assert len(discover('petersons', limit=3, client=c)['items']) == 3


def test_rss_refuses_html_content_type_oversize_and_bad_status():
    with client_for(U, rss(2), 'text/html') as c:
        with pytest.raises(PlatformUnavailable):
            discover('petersons', client=c)
    with client_for(U, b'<rss>' + b'x' * 2_000_001, 'application/rss+xml') as c:
        with pytest.raises(PlatformUnavailable) as e:
            discover('petersons', client=c)
    assert '2 MB' in str(e.value)
    with client_for(U, 'no', 'application/rss+xml', 404) as c:
        with pytest.raises(PlatformUnavailable):
            discover('petersons', client=c)


def test_atom_entries_are_read():
    atom = ('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom entry one</title>'
            '<link rel="alternate" href="https://example.org/atom-1"/><summary>s</summary></entry></feed>')
    with client_for(U, atom, 'application/atom+xml; xml') as c:
        out = discover('petersons', client=c)
    assert [i['url'] for i in out['items']] == ['https://example.org/atom-1']


def test_input_bounds_and_unknown_platform():
    with pytest.raises(KeyError):
        discover('no-such-platform')
    for bad in (0, 101):
        with pytest.raises(ValueError):
            discover('petersons', limit=bad)
    with pytest.raises(ValueError):
        discover('petersons', 'q' * 201)


def test_default_client_does_not_follow_redirects(monkeypatch):
    seen = {}
    real = httpx.Client

    def spy(*a, **k):
        seen.update(k)
        return real(transport=httpx.MockTransport(lambda r: httpx.Response(
            200, content=rss(1).encode(), headers={'content-type': 'application/rss+xml'}, request=r)))
    monkeypatch.setattr(sp.httpx, 'Client', spy)
    discover('petersons')
    assert seen['follow_redirects'] is False and seen['timeout'] == 15


ROW54 = {  # id: (url, kind) for the ten rows-54 sources
    'opportunitydesk': ('https://opportunitydesk.org/feed/', 'program'),
    'fundsforngos': ('https://www.fundsforngos.org/feed/', 'grant'),
    'scholarshipsandgrants': ('https://scholarshipsandgrants.us/feed/', 'scholarship'),
    'opportunitiescorners': ('https://opportunitiescorners.com/feed/', 'program'),
    'scholarshipamerica': ('https://scholarshipamerica.org/feed/', 'scholarship'),
    'nsffunding': ('https://www.nsf.gov/rss/rss_www_funding_pgm_annc_inf.xml', 'grant'),
    'petersons': ('https://www.petersons.com/blog/feed/', 'program'),
    'collegeconfidential': ('https://collegeconfidential.com/feed/', 'program'),
    'thecollegesolution': ('https://thecollegesolution.com/feed/', 'program'),
    'topuniversities': ('https://www.topuniversities.com/rss.xml', 'program'),
}


@pytest.mark.parametrize('pid', sorted(ROW54))
def test_row54_sources_have_exact_url_mode_and_kind(pid):
    p = BY_ID[pid]
    assert (p.url, p.mode, p.kind) == (ROW54[pid][0], 'rss', ROW54[pid][1])
