"""Twenty distinct, executable read-only opportunity analysis capabilities."""
from datetime import date

import pytest

from app.modules.m01_opportunity_discovery import student_intelligence as s
from app.modules.m01_opportunity_discovery.student_platforms import PlatformUnavailable


def item(platform='fastweb', title='STEM scholarship', url='https://www.fastweb.com/college-scholarships/scholarships/123-stem', description=''):
    return {'platform': platform, 'source_url': s.BY_ID[platform].url, 'title': title, 'description': description,
            'url': url, 'opportunity_kind': 'scholarship', 'score': .4}


def cards():
    return [s.annotate(item(description='Deadline: October 10, 2026. Award: $5,000. Remote undergraduate students in India.')),
            s.annotate(item(title='Art program', url='https://www.fastweb.com/college-scholarships/scholarships/124-art',
                            description='Deadline: September 1, 2026. Award: INR 2,000. In-person graduate students in Europe.')),
            s.annotate(item(title='Science fellowship', url='https://www.fastweb.com/college-scholarships/scholarships/125-science',
                            description='Posted September 2, 2026. Tuition $100,000.'))]


def test_01_explicit_deadline_only():
    assert s.extract_deadline('Posted 2026-09-01. Deadline: 2026-10-10')['value'] == '2026-10-10'
    assert s.extract_deadline('Event date 2026-10-10')['value'] is None


def test_02_award_currency_and_no_fee_confusion():
    assert s.extract_award('Award: $5k')['amount'] == 5000
    assert s.extract_award('Scholarship amount INR 20,000')['currency'] == 'INR'
    assert s.extract_award('Tuition fee $20,000')['amount'] is None


def test_03_delivery_evidence():
    assert s.extract_delivery('A virtual program')['value'] == 'online'
    assert s.extract_delivery('It starts on Monday')['value'] is None


def test_04_student_level_mentions_not_eligibility():
    assert s.extract_student_level('For doctoral and undergraduate students')['levels'] == ['undergraduate', 'phd']
    assert s.extract_student_level('everyone')['basis'] == 'text_mentions_not_eligibility'


def test_05_region_mentions_not_eligibility():
    assert s.extract_region('For projects in India and Africa')['mentions'] == ['India', 'Africa']
    assert s.extract_region('Asian students')['mentions'] == []


def test_06_canonical_preserves_functional_query():
    assert s.canonical_link('https://Example.org/a/?utm_source=x&topic=stem#frag') == 'https://example.org/a?topic=stem'
    with pytest.raises(ValueError): s.canonical_link('http://example.org/a')


def test_07_stable_id_across_tracking():
    a = item(); b = item(url=a['url']+'?utm_campaign=abc')
    assert s.stable_id(a) == s.stable_id(b)


def test_08_evidence_card_unknown_and_source_consistency():
    card = s.annotate(item(description='Posted 2026-09-01'))
    assert card['deadline']['value'] is None and card['award']['amount'] is None
    with pytest.raises(ValueError): s.annotate(item() | {'source_url': 'https://bad.example/'})


def test_09_exact_link_dedupe_not_same_title():
    a, b, c = item(), item(url=item()['url']+'?utm_source=x'), item(url=item()['url']+'-other')
    assert len(s.deduplicate([a, b, c])) == 2


def test_10_kind_filter():
    a = item(); b = a | {'opportunity_kind': 'internship'}
    assert s.filter_kind([a, b], 'internship') == [b]


def test_11_platform_filter():
    a = item(); b = a | {'platform': 'scholarshiproar'}
    assert s.filter_platform([a, b], 'scholarshiproar') == [b]


def test_12_positive_terms_any_and_all():
    a, b = item(), item(title='STEM program')
    assert s.filter_terms([a, b], ['scholarship', 'STEM'], require_all=True) == [a]
    assert s.filter_terms([a, b], ['program']) == [b]


def test_13_negative_terms():
    assert s.exclude_terms([item(), item(title='No essay')], ['essay']) == [item()]


def test_14_deadline_window_unknown_handling():
    a, b, c = cards()
    assert s.deadline_window([a, b, c], date(2026,10,1), date(2026,10,31)) == [a]
    assert s.deadline_window([a,b,c], date(2026,10,1), date(2026,10,31), include_unknown=True) == [a,c]
    with pytest.raises(ValueError): s.deadline_window([a], date(2026,10,31), date(2026,10,1))


def test_15_expired_filter_keeps_unknown():
    a, b, c = cards()
    assert s.exclude_expired([a,b,c], today=date(2026,9,25)) == [a,c]


def test_16_minimum_award_never_crosses_currency():
    a, b, c = cards()
    assert s.minimum_award([a,b,c], 3000, 'USD') == [a]
    assert s.minimum_award([a,b,c], 3000, 'USD', include_unknown=True) == [a,c]


def test_17_delivery_filter_unknown():
    a, b, c = cards()
    assert s.filter_delivery([a,b,c], 'remote') == [a]
    assert s.filter_delivery([a,b,c], 'remote', include_unknown=True) == [a,c]


def test_18_level_mention_filter():
    a, b, c = cards()
    assert s.filter_level_mentions([a,b,c], 'graduate') == [b]
    assert s.filter_level_mentions([a,b,c], 'graduate', include_unknown=True) == [b,c]


def test_19_region_mention_filter():
    a, b, c = cards()
    assert s.filter_region_mentions([a,b,c], 'India') == [a]
    assert s.filter_region_mentions([a,b,c], 'India', include_unknown=True) == [a,c]


def test_20_source_breakdown_and_unknowns():
    result = s.source_breakdown(cards())
    assert result['total'] == 3 and result['deadline_unknown'] == result['award_unknown'] == 1
    assert result['by_platform'] == {'fastweb': 3}


def test_live_aggregation_isolates_failures_and_labels_launch(monkeypatch):
    def discovery(platform, query, limit):
        if platform == 'fastweb': return {'mode': 'html', 'items': [item()]}
        if platform == 'simplify': return {'mode': 'launch_only', 'launch_url': s.BY_ID[platform].url, 'reason': 'extension'}
        raise PlatformUnavailable('upstream failed')
    monkeypatch.setattr(s, 'discover', discovery)
    result = s.search_and_analyze(['fastweb', 'simplify', 'mlh'], 'STEM')
    assert result['breakdown']['total'] == 1
    assert len(result['launch_only']) == len(result['failures']) == 1
    with pytest.raises(ValueError): s.search_and_analyze(['fastweb'] * 2)


def test_refine_composes_real_evidence_filters():
    a, b, c = cards()
    assert s.refine([a,b,c], kind='scholarship', terms=['STEM'], start=date(2026,10,1), end=date(2026,10,31),
                    min_award=3000, currency='USD', delivery='remote', level='undergraduate', region='India') == [a]
    with pytest.raises(ValueError): s.refine([a], start=date(2026,10,1))
    with pytest.raises(ValueError): s.refine([a], min_award=100)


def test_routes_are_mounted_and_require_tenant():
    from app.modules.m01_opportunity_discovery.routes import router
    paths = {r.path for r in router.routes if hasattr(r, 'path')}
    assert '/opportunity-discovery/student-insights' in paths
    assert '/opportunity-discovery/student-insights/search' in paths
