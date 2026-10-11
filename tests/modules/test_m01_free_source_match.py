"""M01 free-source match: real Fastweb detail parsing and profile matching.

Fixtures below are trimmed excerpts of REAL public, logged-out Fastweb pages
(fetched 2026-10-11 about 18:04 IST):
  listing: https://www.fastweb.com/college-scholarships
  detail:  https://www.fastweb.com/college-scholarships/scholarships/195174-regent-s-scholarship-university-of-saint-francis-in
No personal data, no tokens. Negative-case HTML is synthetic and labelled so.
RippleMatch, Simplify, RaiseMe and Bold.org have no public listing Atlas may
parse (account, extension or rate-limit challenge); tests assert that no
items are invented for them.
"""
import os

import httpx
import pytest

from app.modules.m01_opportunity_discovery import free_source_match as fsm
from app.modules.m01_opportunity_discovery.student_platforms import PlatformUnavailable

DETAIL_URL = ('https://www.fastweb.com/college-scholarships/scholarships/'
              '195174-regent-s-scholarship-university-of-saint-francis-in')
LISTING_URL = 'https://www.fastweb.com/college-scholarships'

DETAIL_HTML = """<html><head>
<link rel="canonical" href="https://www.fastweb.com/college-scholarships/scholarships/195174-regent-s-scholarship-university-of-saint-francis-in" />
<title>Regent&#39;s Scholarship - University of Saint Francis, IN | Fastweb</title>
<script type="application/ld+json">
{"@context":"http://schema.org","@type":"MonetaryGrant","name":"Regent's Scholarship - University of Saint Francis, IN ","description":"The Regent\u2019s Scholarship is available to incoming freshman students at the University of Saint Francis who have a minimum GPA of 3.5.","url":"https://www.fastweb.com/college-scholarships/scholarships/195174-regent-s-scholarship-university-of-saint-francis-in","amount":{"@type":"MonetaryAmount","amount":"20000"},"funder":{"@type":"Organization","name":"University of Saint Francis, Indiana","url":"https://www.sf.edu/cost-and-aid/scholarships/"},"datePublished":"2026-09-21"}
</script></head><body>
<div class='cell'>
<h1 class='award-name'>Regent&#39;s Scholarship - University of Saint Francis, IN </h1>
<p class='award-provider'>University of Saint Francis, Indiana</p>
</div>
<div class='award-details-wrapper'>
<div class='award-amount-wrapper'>
<p class='award-label'>amount</p>
<p class='award-info'>
$20,000
</p>
</div>
<div class='awards-count-wrapper'>
<p class='award-label'>awards available</p>
<p class='award-info'>
Unspecified
</p>
</div>
<div class='award-deadline-wrapper'>
<p class='award-label'>deadline</p>
<p class='award-info'>
Varies
</p>
</div>
</div>
<div class='apply-now-button-wrapper'>
<a class="button secondary logged-out-apply " href="#login_widget">LOGIN OR SIGN UP TO APPLY</a>
</div>
</body></html>"""

LISTING_HTML = """<html><body>
<div class='grid-x featured-award-row'><div class='cell large-10 scholarship-name'><h3>
<a href="/college-scholarships/scholarships/195176-dean-s-scholarship-university-of-saint-francis-in">Dean\u2019s Scholarship - University of Saint Francis, IN</a>
</h3></div><div class='cell large-2 medium-4'>
<a class="button secondary ghost" href="/college-scholarships/scholarships/195176-dean-s-scholarship-university-of-saint-francis-in">See Details
</a></div></div>
<div class='grid-x featured-award-row'><div class='cell large-10 scholarship-name'><h3>
<a href="/college-scholarships/scholarships/195175-founder-s-scholarship-university-of-saint-francis-in">Founder\u2019s Scholarship - University of Saint Francis, IN</a>
</h3></div></div>
<div class='grid-x featured-award-row'><div class='cell large-10 scholarship-name'><h3>
<a href="/college-scholarships/scholarships/195174-regent-s-scholarship-university-of-saint-francis-in">Regent&#39;s Scholarship - University of Saint Francis, IN </a>
</h3></div></div>
<!-- synthetic negatives below -->
<h3><a href="https://evil.example/college-scholarships/scholarships/1-x-award">Evil Offsite Scholarship</a></h3>
<h3><a href="/login">Log in now please</a></h3>
</body></html>"""

PROFILE = {'full_name': 'Test Student', 'email': 'student@example.com', 'gpa': 3.7,
           'student_level': 'undergraduate', 'intended_major': 'physics',
           'interests': ['physics', 'robotics'], 'state': 'Indiana', 'min_award_usd': 5000}


def client_for(body, status=200, ctype='text/html; charset=utf-8'):
    return httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, text=body, headers={'content-type': ctype}, request=request)))


# ---- source capability honesty -------------------------------------------------
def test_five_named_sources_with_honest_capability():
    caps = fsm.source_capabilities()
    assert [c['platform'] for c in caps] == ['ripplematch', 'simplify', 'raiseme', 'bold', 'fastweb']
    by = {c['platform']: c for c in caps}
    assert by['fastweb']['public_parse'] is True and by['fastweb']['items_parsed_from'] == 'public listing and detail pages'
    for p in ('ripplematch', 'simplify', 'raiseme', 'bold'):
        assert by[p]['public_parse'] is False and by[p]['items'] == []
        assert by[p]['reason'] and by[p]['launch_url'].startswith('https://')
    assert all(c['paid_tier_used'] is False and c['submits'] is False for c in caps)


# ---- detail parser ---------------------------------------------------------------
def test_detail_parser_extracts_real_page_fields():
    row = fsm.parse_fastweb_detail(DETAIL_HTML, DETAIL_URL)
    assert row['platform'] == 'fastweb' and row['opportunity_kind'] == 'scholarship'
    assert row['title'] == "Regent's Scholarship - University of Saint Francis, IN"
    assert row['provider'] == 'University of Saint Francis, Indiana'
    assert row['amount'] == {'amount': 20000, 'currency': 'USD'}
    assert row['awards_available'] is None
    assert row['deadline'] == {'value': None, 'raw': 'Varies'}
    assert row['min_gpa'] == 3.5
    assert 'incoming freshman' in row['description']
    assert row['requires_account_to_apply'] is True
    assert row['url'] == DETAIL_URL and row['source_url'] == 'https://www.fastweb.com/college-scholarships'
    assert row['evidence_status'] == 'parsed_from_public_page'


def test_detail_parser_falls_back_to_visible_block_without_jsonld():
    # synthetic negative: JSON-LD removed, visible block kept
    html = DETAIL_HTML.split('<script type="application/ld+json">')[0] + '</head>' + DETAIL_HTML.split('</head>')[1]
    row = fsm.parse_fastweb_detail(html, DETAIL_URL)
    assert row['amount'] == {'amount': 20000, 'currency': 'USD'}
    assert row['title'].startswith("Regent's Scholarship") and row['min_gpa'] is None


def test_detail_parser_parses_dated_deadline_and_award_count():
    html = DETAIL_HTML.replace('Varies', 'March 15, 2027').replace('Unspecified', '12')  # synthetic variant
    row = fsm.parse_fastweb_detail(html, DETAIL_URL)
    assert row['deadline'] == {'value': '2027-03-15', 'raw': 'March 15, 2027'}
    assert row['awards_available'] == 12


@pytest.mark.parametrize('bad', ['', '<html><body>nothing here</body></html>', 'x' * 50])
def test_detail_parser_refuses_pages_without_a_scholarship(bad):
    with pytest.raises(ValueError, match='FREE_SOURCE_PARSE'):
        fsm.parse_fastweb_detail(bad, DETAIL_URL)


@pytest.mark.parametrize('url', ['https://evil.example/college-scholarships/scholarships/1-x',
                                 'http://www.fastweb.com/college-scholarships/scholarships/1-x',
                                 'https://www.fastweb.com/login', 'https://u:p@www.fastweb.com/college-scholarships/scholarships/1-x'])
def test_detail_parser_refuses_foreign_or_non_detail_urls(url):
    with pytest.raises(ValueError, match='FREE_SOURCE_URL'):
        fsm.parse_fastweb_detail(DETAIL_HTML, url)


# ---- listing parser (reuses m01 discover) ----------------------------------------
def test_listing_rows_come_from_m01_discover_and_are_structured():
    with client_for(LISTING_HTML) as c:
        rows = fsm.read_fastweb_listing(client=c)
    assert [r['url'].rsplit('/', 1)[1][:6] for r in rows] == ['195176', '195175', '195174']
    assert all(r['platform'] == 'fastweb' and r['id'] and r['provider'] == 'University of Saint Francis, IN' for r in rows)
    assert all(r['amount'] is None and r['deadline'] == {'value': None, 'raw': None} for r in rows)
    assert all(r['evidence_status'] == 'listing_title_only' for r in rows)


def test_listing_unavailable_is_raised_not_faked():
    with client_for('blocked', status=429) as c, pytest.raises(PlatformUnavailable):
        fsm.read_fastweb_listing(client=c)


def test_fetch_detail_uses_safe_target_and_status_check():
    with client_for(DETAIL_HTML) as c:
        assert fsm.fetch_fastweb_detail(DETAIL_URL, client=c)['amount']['amount'] == 20000
    with client_for(DETAIL_HTML) as c, pytest.raises(ValueError, match='FREE_SOURCE_URL'):
        fsm.fetch_fastweb_detail('https://evil.example/x', client=c)
    with client_for('challenge', status=429) as c, pytest.raises(PlatformUnavailable):
        fsm.fetch_fastweb_detail(DETAIL_URL, client=c)
    with client_for('<html/>', ctype='application/json') as c, pytest.raises(PlatformUnavailable):
        fsm.fetch_fastweb_detail(DETAIL_URL, client=c)


# ---- matching ----------------------------------------------------------------------
def row(**kw):
    base = fsm.parse_fastweb_detail(DETAIL_HTML, DETAIL_URL)
    base.update(kw)
    return base


def crit(result, name):
    return next(c for c in result['criteria'] if c['criterion'] == name)


def test_match_explains_each_criterion_with_evidence():
    r = fsm.match(PROFILE, [row()], as_of='2026-10-11')[0]
    assert crit(r, 'gpa')['status'] == 'met' and '3.5' in crit(r, 'gpa')['explanation'] and '3.7' in crit(r, 'gpa')['explanation']
    assert crit(r, 'award')['status'] == 'met'
    assert crit(r, 'deadline')['status'] == 'unknown' and 'Varies' in crit(r, 'deadline')['explanation']
    assert crit(r, 'level')['status'] == 'unknown'
    assert crit(r, 'interests')['status'] == 'unmet'
    assert r['eligible'] is True and r['unmet_hard'] == []


def test_gpa_below_minimum_is_hard_unmet_and_ranks_last():
    p = dict(PROFILE, gpa=3.2)
    good = row(url=DETAIL_URL + '-b', min_gpa=3.0, title='Other', id='x2')
    out = fsm.match(p, [row(), good], as_of='2026-10-11')
    assert [o['title'] for o in out] == ['Other', "Regent's Scholarship - University of Saint Francis, IN"]
    assert out[1]['eligible'] is False and out[1]['unmet_hard'] == ['gpa']


def test_expired_deadline_is_hard_unmet_and_future_is_met():
    past = row(deadline={'value': '2026-01-01', 'raw': 'January 1, 2026'})
    future = row(deadline={'value': '2026-12-01', 'raw': 'December 1, 2026'}, id='f')
    out = {o['id']: o for o in fsm.match(PROFILE, [past, future], as_of='2026-10-11')}
    assert crit(out[past['id']], 'deadline')['status'] == 'unmet' and out[past['id']]['eligible'] is False
    assert crit(out['f'], 'deadline')['status'] == 'met' and 'days' in crit(out['f'], 'deadline')['explanation']


def test_deadline_today_is_still_open():
    r = row(deadline={'value': '2026-10-11', 'raw': 'October 11, 2026'})
    assert crit(fsm.match(PROFILE, [r], as_of='2026-10-11')[0], 'deadline')['status'] == 'met'


def test_interest_overlap_and_level_and_award_thresholds():
    r = row(description='Physics and robotics awards for undergraduate students.',
            student_level={'levels': ['undergraduate'], 'basis': 'text_mentions_not_eligibility'},
            amount={'amount': 1000, 'currency': 'USD'})
    out = fsm.match(PROFILE, [r], as_of='2026-10-11')[0]
    assert crit(out, 'interests')['status'] == 'met' and 'physics' in crit(out, 'interests')['explanation']
    assert crit(out, 'level')['status'] == 'met'
    assert crit(out, 'award')['status'] == 'unmet' and out['eligible'] is True  # award floor is a preference, not hard


def test_unknown_profile_fields_are_skipped_not_guessed():
    out = fsm.match({'full_name': 'T'}, [row()], as_of='2026-10-11')[0]
    assert {c['status'] for c in out['criteria']} == {'unknown'} and out['score'] == 0.0


def test_score_is_met_fraction_and_ties_break_by_amount_then_title():
    a = row(id='a', title='A', amount={'amount': 100, 'currency': 'USD'}, min_gpa=None)
    b = row(id='b', title='B', amount={'amount': 900, 'currency': 'USD'}, min_gpa=None)
    out = fsm.match({'gpa': 3.0}, [a, b], as_of='2026-10-11')
    assert out[0]['score'] == out[1]['score']
    assert [o['id'] for o in out] == ['b', 'a']


def test_boundaries_gpa_and_award_equal_values_are_met():
    r = row(min_gpa=3.7, amount={'amount': 5000, 'currency': 'USD'})
    out = fsm.match(PROFILE, [r], as_of='2026-10-11')[0]
    assert crit(out, 'gpa')['status'] == 'met' and crit(out, 'award')['status'] == 'met'


def test_score_is_exact_met_fraction():
    r = row(min_gpa=3.0, amount={'amount': 9000, 'currency': 'USD'},
            description='Physics prize.', deadline={'value': '2026-12-01', 'raw': 'December 1, 2026'})
    out = fsm.match(PROFILE, [r], as_of='2026-10-11')[0]
    assert [c['status'] for c in out['criteria']] == ['met', 'unknown', 'met', 'met', 'met']
    assert out['score'] == 1.0
    r2 = dict(r, min_gpa=4.0)
    assert fsm.match(PROFILE, [r2], as_of='2026-10-11')[0]['score'] == 0.75


def test_min_gpa_extraction_is_range_checked():
    for text, want in [('minimum GPA of 3.5.', 3.5), ('a minimum cumulative GPA of 3', 3.0),
                       ('minimum GPA of 9.5', None), ('minimum GPA of 0', None), ('no gpa words', None)]:
        assert fsm._min_gpa(text) == want, text


def test_interest_match_ignores_case_in_profile_terms():
    r = row(description='Robotics award.')
    out = fsm.match(dict(PROFILE, interests=['Robotics']), [r], as_of='2026-10-11')[0]
    assert crit(out, 'interests')['status'] == 'met'


def test_own_client_never_follows_redirects_and_redirect_is_unavailable():
    client = fsm._new_client()
    try:
        assert client.follow_redirects is False
    finally:
        client.close()
    with client_for('moved', status=302) as c, pytest.raises(PlatformUnavailable):
        fsm.fetch_fastweb_detail(DETAIL_URL, client=c)


@pytest.mark.parametrize('bad', [{'gpa': 'high'}, {'gpa': True}, {'gpa': 5.5}, {'gpa': float('nan')}, {'interests': 'physics'}, {}])
def test_match_refuses_bad_profiles(bad):
    with pytest.raises(ValueError, match='FREE_SOURCE_PROFILE'):
        fsm.match(bad, [row()], as_of='2026-10-11')


def test_match_refuses_bad_as_of_and_rows():
    for as_of in ('11/10/2026', None, '2026-13-01'):
        with pytest.raises(ValueError, match='FREE_SOURCE_AS_OF'):
            fsm.match(PROFILE, [row()], as_of=as_of)
    with pytest.raises(ValueError, match='FREE_SOURCE_ROWS'):
        fsm.match(PROFILE, [], as_of='2026-10-11')
    with pytest.raises(ValueError, match='FREE_SOURCE_ROWS'):
        fsm.match(PROFILE, ['not a row'], as_of='2026-10-11')


# ---- scope trim (peer ruling): parser + matcher only; prefill belongs to m02 --------
def test_module_has_no_prefill_or_form_surface():
    for name in ('prefill_packet', 'FORM_FIELDS', 'NEXT_STEP', 'c35_prefill'):
        assert not hasattr(fsm, name), name
    src = open(fsm.__file__).read()
    assert 'c35' not in src and 'password' not in src.lower()


def test_search_and_match_end_to_end_with_mock_network():
    def handler(request):
        body = DETAIL_HTML if '195174' in request.url.path else LISTING_HTML
        return httpx.Response(200, text=body, headers={'content-type': 'text/html'}, request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        out = fsm.search_and_match(PROFILE, as_of='2026-10-11', detail_limit=3, client=c)
    assert out['sources'][-1]['platform'] == 'fastweb'
    assert len(out['matches']) == 3 and out['details_fetched'] == 1
    assert any(m['evidence_status'] == 'parsed_from_public_page' for m in out['matches'])
    assert out['not_covered']['ripplematch'] and out['submitted'] is False


@pytest.mark.skipif(not os.environ.get('ATLAS_LIVE_SMOKE'), reason='opt-in live network smoke')
def test_live_fastweb_listing_and_one_detail_smoke():
    rows = fsm.read_fastweb_listing()
    assert rows
    d = fsm.fetch_fastweb_detail(rows[0]['url'])
    assert d['title'] and d['platform'] == 'fastweb' and d['evidence_status'] == 'parsed_from_public_page'
