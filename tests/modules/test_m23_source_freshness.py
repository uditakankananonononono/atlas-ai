# Integrator-executed. Pure unit tests; no app client, DB, or network.
from datetime import datetime, timedelta, timezone
import pytest
from app.modules.m23_study_abroad import source_freshness as sf

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
URL = 'https://admissions.example.edu/deadlines'

def rec(**kw):
    d = {'fact_id': 'f1', 'subject': 'Example U', 'field': 'deadline', 'value': 'Jan 5', 'source_url': URL,
         'checked_at': (NOW - timedelta(days=10)).isoformat()}
    d.update(kw); return d

def a(**kw): return sf.assess_fact(rec(**kw), now=NOW)

def test_recent_check_with_url_is_fresh_with_provenance():
    f = a(); assert f.status == 'fresh' and f.age_days == 10.0
    assert f.provenance['official_status_attested'] is False and f.provenance['fetched_by_this_module'] is False

def test_url_alone_is_never_verified():
    for ts in (None, '', 'garbage'):
        assert a(checked_at=ts).status == 'unknown'

def test_timestamp_alone_without_url_is_unknown():
    assert a(source_url=None).reason == 'url_missing'

def test_official_url_alias_accepted():
    r = rec(); r['official_url'] = r.pop('source_url')
    assert sf.assess_fact(r, now=NOW).status == 'fresh'

def test_stale_past_max_age_and_boundary():
    assert a(checked_at=(NOW - timedelta(days=181)).isoformat()).status == 'stale'
    assert a(checked_at=(NOW - timedelta(days=180)).isoformat()).status == 'fresh'

def test_per_fact_max_age_override():
    assert a(max_age_days=5).status == 'stale'

def test_future_timestamp_marked_distinctly():
    f = a(checked_at=(NOW + timedelta(days=1)).isoformat())
    assert f.status == 'unknown' and f.reason == 'timestamp_future' and f.age_days is None

def test_small_clock_skew_tolerated():
    assert a(checked_at=(NOW + timedelta(minutes=2)).isoformat()).status == 'fresh'

def test_naive_date_only_and_non_string_timestamps_refused():
    assert a(checked_at='2026-10-01T00:00:00').reason == 'timestamp_timezone_missing'
    assert a(checked_at='2026-10-01').reason == 'timestamp_invalid'
    assert a(checked_at=1760000000).reason == 'timestamp_invalid'
    assert a(checked_at='1999-01-01T00:00:00+00:00').reason == 'timestamp_invalid'

def test_z_suffix_and_offset_normalized_to_utc():
    f = a(checked_at='2026-10-01T05:30:00+05:30'); assert f.checked_at.startswith('2026-10-01T00:00:00')
    assert a(checked_at='2026-10-01T00:00:00Z').status == 'fresh'

@pytest.mark.parametrize('u,reason', [('http://x.edu/a', 'url_not_https'), ('ftp://x.edu', 'url_not_https'),
    ('https://user:pw@x.edu/', 'url_invalid'), ('https://localhost/', 'url_invalid'), ('https://x.edu/a b', 'url_invalid'),
    ('https://x.edu:99999/', 'url_invalid'), ('https://' + 'a' * 2100 + '.edu', 'url_invalid'), (5, 'url_invalid'), ('', 'url_missing')])
def test_bad_urls_unknown(u, reason):
    f = a(source_url=u); assert f.status == 'unknown' and f.reason == reason and f.source_url is None

def test_allowed_domains_when_given():
    ok = sf.assess_fact(rec(), now=NOW, allowed_domains=['example.edu']); assert ok.status == 'fresh'
    bad = sf.assess_fact(rec(), now=NOW, allowed_domains=['other.edu']); assert bad.reason == 'url_domain_not_allowed'
    assert sf.assess_fact(rec(source_url='https://evilexample.edu/'), now=NOW, allowed_domains=['example.edu']).status == 'unknown'

def test_non_mapping_record_is_unknown_not_crash():
    assert sf.assess_fact('x', now=NOW).reason == 'record_not_object'

def test_long_text_bounded_and_missing_id_defaulted():
    f = sf.assess_fact(rec(fact_id=None, value='v' * 5000), now=NOW, index=7)
    assert f.fact_id == 'fact-7' and len(f.value) == sf.MAX_TEXT

def test_batch_counts_and_limits():
    out = sf.assess_facts([rec(), rec(checked_at=None), rec(checked_at=(NOW - timedelta(days=400)).isoformat())], now=NOW)
    assert out['counts'] == {'fresh': 1, 'stale': 1, 'unknown': 1} and out['total'] == 3
    assert 'eligib' in ' '.join(out['limits']) and 'eligible' not in out

def test_batch_bounds_and_param_errors():
    for bad in ([], None, 'x', [rec()] * (sf.MAX_FACTS + 1)):
        with pytest.raises(sf.FreshnessError): sf.assess_facts(bad, now=NOW)
    with pytest.raises(sf.FreshnessError): sf.assess_facts([rec()], now=datetime(2026, 1, 1))
    for m in (0, -1, True, 'x', 99999):
        with pytest.raises(sf.FreshnessError): sf.assess_facts([rec()], now=NOW, max_age_days=m)
