"""U37: curated high-school competition registry from live official pages."""
import pytest
from app.modules.m01_opportunity_discovery.high_school_competitions_u37 import (
    COMPETITIONS, CATEGORIES, DEADLINE_KINDS, LEVELS,
    get_competition, list_competitions, summarize, validate_registry)

def refuse(fn, message):
    with pytest.raises(ValueError) as ei:
        fn()
    assert str(ei.value) == message

def test_registry_size_and_kinds():
    assert len(COMPETITIONS) == 16
    assert validate_registry() == {'entries': 16, 'issues': []}

def test_exact_entry_envelope():
    assert get_competition('regeneron-sts') == {
        'key': 'regeneron-sts',
        'name': 'Regeneron Science Talent Search (STS)',
        'organizer': 'Society for Science',
        'category': 'science_research',
        'level': 'national_us',
        'eligibility': 'U.S. high school seniors',
        'deadline_kind': 'application_deadline',
        'dates_text': 'Application deadline November 5, 2026 at 8pm ET; '
                      'finals week March 11-17, 2027',
        'source_url': 'https://www.societyforscience.org/regeneron-sts/',
        'checked_at': '2026-10-11',
        'selection_note': 'Direct application; about 2,600 entrants per year'}

def test_unknown_key_refused():
    refuse(lambda: get_competition('nope'),
           "U37: unknown competition key 'nope'")

def test_category_filter_exact():
    assert [c['key'] for c in list_competitions(category='mathematics')] == [
        'amc-10-12', 'imo']

def test_bad_category_refused():
    refuse(lambda: list_competitions(category='underwater'),
           "U37: category must be one of arts_writing, biology, business, "
           "chemistry, health_professions, humanities, informatics, "
           "mathematics, physics, robotics, science_research, stem_team")

def test_level_filter_counts():
    assert len(list_competitions(level='international')) == 9
    assert len(list_competitions(level='national_us')) == 7

def test_bad_level_refused():
    refuse(lambda: list_competitions(level='global'),
           'U37: level must be one of international, national_us')

def test_combined_filter():
    assert [c['key'] for c in list_competitions(
        category='informatics', level='international')] == ['ioi']

def test_list_sorted_by_name():
    names = [c['name'] for c in list_competitions()]
    assert names == sorted(names)
    assert len(names) == 16

def test_summarize_exact():
    assert summarize() == {
        'total': 16,
        'by_category': {'arts_writing': 1, 'biology': 1, 'business': 1,
                        'chemistry': 1, 'health_professions': 1, 'humanities': 1,
                        'informatics': 2, 'mathematics': 2, 'physics': 2,
                        'robotics': 1, 'science_research': 2, 'stem_team': 1},
        'by_level': {'international': 9, 'national_us': 7},
        'deadline_kinds_used': ['application_deadline', 'event_dates',
                                'not_announced', 'varies_by_country',
                                'varies_by_region']}

def test_all_entries_checked_today_and_https():
    for c in COMPETITIONS:
        assert c['checked_at'] == '2026-10-11'
        assert c['source_url'].startswith('https://')

def test_validate_registry_detects_duplicate_key():
    tampered = list(COMPETITIONS) + [dict(COMPETITIONS[0])]
    report = validate_registry(tampered)
    assert report['entries'] == 17
    assert report['issues'] == ["duplicate key 'amc-10-12'"]

def test_validate_registry_detects_missing_field():
    tampered = [dict(c) for c in COMPETITIONS]
    del tampered[3]['source_url']
    report = validate_registry(tampered)
    assert report['issues'] == ["entry 'icho' missing field 'source_url'"]

def test_validate_registry_detects_bad_deadline_kind():
    tampered = [dict(c) for c in COMPETITIONS]
    tampered[0]['deadline_kind'] = 'whenever'
    report = validate_registry(tampered)
    assert report['issues'] == [
        "entry 'amc-10-12' deadline_kind 'whenever' not in DEADLINE_KINDS"]

def test_validate_registry_detects_bad_checked_at():
    tampered = [dict(c) for c in COMPETITIONS]
    tampered[0]['checked_at'] = '11/10/2026'
    report = validate_registry(tampered)
    assert report['issues'] == [
        "entry 'amc-10-12' checked_at must be an ISO date"]

def test_sts_application_deadline_pinned():
    sts = get_competition('regeneron-sts')
    assert 'November 5, 2026' in sts['dates_text']
    assert sts['deadline_kind'] == 'application_deadline'

def test_declared_taxonomies_match_registry():
    assert {c['category'] for c in COMPETITIONS} <= set(CATEGORIES)
    assert {c['level'] for c in COMPETITIONS} <= set(LEVELS)
    assert {c['deadline_kind'] for c in COMPETITIONS} <= set(DEADLINE_KINDS)


class U37Str(str):
    pass


@pytest.mark.parametrize('value', [[], 1, U37Str('imo'), 'x'*129])
def test_repair_key_clean_refusals(value):
    with pytest.raises(ValueError, match='^U37:'):
        get_competition(value)


@pytest.mark.parametrize('value', [U37Str('biology'), [], 1])
def test_repair_category_exact(value):
    with pytest.raises(ValueError, match='^U37:'):
        list_competitions(category=value)


def test_repair_copy_isolation():
    result = list_competitions()
    before = get_competition(result[0]['key'])
    result[0]['name'] = 'caller change'
    assert get_competition(before['key']) == before


@pytest.mark.parametrize('rows', [[None], 7, [{'key': []}], [{'key':'imo','checked_at':None}]])
def test_repair_malformed_rows(rows):
    with pytest.raises(ValueError, match='^U37:'):
        validate_registry(rows)


@pytest.mark.parametrize('field,value', [('category','bad'), ('level','bad'),
    ('source_url','javascript:alert(1)'), ('name',' '), ('checked_at','20261011')])
def test_repair_consistency_issues(field,value):
    entry=get_competition('imo');entry[field]=value
    assert validate_registry([entry])['issues']


def test_repair_cardinality_cap():
    with pytest.raises(ValueError, match='^U37:'):
        validate_registry([{}]*257)


def test_repair_missing_key_marker():
    assert validate_registry([{}]) == {'entries':1,'issues':["entry '?' missing field 'key'"]}


# Canonical independent envelopes reviewed against official sources and candidate.
EXPECTED_REGISTRY = ({'key': 'amc-10-12',
  'name': 'AMC 10/12 (American Mathematics Competitions)',
  'organizer': 'Mathematical Association of America',
  'category': 'mathematics',
  'level': 'national_us',
  'eligibility': 'AMC 10: grades 10 and below, under 17.5 on competition day; AMC 12: grades 12 '
                 'and below, under 19.5',
  'deadline_kind': 'event_dates',
  'dates_text': '2026-27: AMC 10A/12A November 5, 2026; AMC 10B/12B November 13, 2026',
  'source_url': 'https://maa.org/student-programs/amc/',
  'checked_at': '2026-10-11',
  'selection_note': 'School competition manager registers; path to AIME/USAMO and the U.S. IMO '
                    'team; national_us denotes this U.S. pathway, not exclusive eligibility. MAA '
                    'also offers AMC International outside the USA and Canada.'},
 {'key': 'imo',
  'name': 'International Mathematical Olympiad (IMO)',
  'organizer': 'IMO Board',
  'category': 'mathematics',
  'level': 'international',
  'eligibility': 'Pre-university students in national teams of up to 6',
  'deadline_kind': 'varies_by_country',
  'dates_text': 'IMO 2027: Budapest, Hungary, July 16-26, 2027 (IMO 2026 Shanghai, July 10-21, '
                '2026, completed)',
  'source_url': 'https://www.imo-official.org/',
  'checked_at': '2026-10-11',
  'selection_note': 'National selection contests feed each team'},
 {'key': 'ipho',
  'name': 'International Physics Olympiad (IPhO)',
  'organizer': 'IPhO Secretariat',
  'category': 'physics',
  'level': 'international',
  'eligibility': 'Secondary school students in national teams of up to 5',
  'deadline_kind': 'varies_by_country',
  'dates_text': 'IPhO 2026: Bucaramanga, Colombia, July 4-12, 2026 (completed)',
  'source_url': 'https://www.ipho-new.org/',
  'checked_at': '2026-10-11',
  'selection_note': 'National selection (e.g. USAPhO path) feeds each team'},
 {'key': 'icho',
  'name': 'International Chemistry Olympiad (IChO)',
  'organizer': 'IChO Steering Committee',
  'category': 'chemistry',
  'level': 'international',
  'eligibility': 'Secondary school students in national teams',
  'deadline_kind': 'varies_by_country',
  'dates_text': 'IChO 2026: Tashkent, Uzbekistan, July 10-19, 2026 (completed)',
  'source_url': 'https://icho2026.uz/',
  'checked_at': '2026-10-11',
  'selection_note': 'National selection feeds each team'},
 {'key': 'ibo',
  'name': 'International Biology Olympiad (IBO)',
  'organizer': 'IBO Association',
  'category': 'biology',
  'level': 'international',
  'eligibility': 'Secondary school students in national teams of up to 4',
  'deadline_kind': 'varies_by_country',
  'dates_text': 'IBO 2027: Warsaw, Poland, July 18-25, 2027',
  'source_url': 'https://www.ibo-info.org/en/competition.html',
  'checked_at': '2026-10-11',
  'selection_note': 'National selection (e.g. USABO) feeds each team'},
 {'key': 'ioi',
  'name': 'International Olympiad in Informatics (IOI)',
  'organizer': 'IOI Committee',
  'category': 'informatics',
  'level': 'international',
  'eligibility': 'Secondary school students in national teams of up to 4',
  'deadline_kind': 'varies_by_country',
  'dates_text': 'IOI 2027: Germany (dates not stated on site); IOI 2026 Uzbekistan, August 9-16, '
                '2026 (completed)',
  'source_url': 'https://ioinformatics.org/',
  'checked_at': '2026-10-11',
  'selection_note': 'National selection (e.g. USACO) feeds each team'},
 {'key': 'isef',
  'name': 'Regeneron International Science and Engineering Fair (ISEF)',
  'organizer': 'Society for Science',
  'category': 'science_research',
  'level': 'international',
  'eligibility': 'High-school students qualifying via Society-affiliated fairs',
  'deadline_kind': 'event_dates',
  'dates_text': 'ISEF 2027 Los Angeles: grand-award and affiliated-fair pages state May 8-14, '
                '2027; college-fair page states May 9-14, 2027; homepage states no 2027 dates. '
                'Official pages conflict; verify the applicable schedule.',
  'source_url': 'https://www.societyforscience.org/isef/',
  'checked_at': '2026-10-11',
  'selection_note': 'Qualification through affiliated regional fairs'},
 {'key': 'regeneron-sts',
  'name': 'Regeneron Science Talent Search (STS)',
  'organizer': 'Society for Science',
  'category': 'science_research',
  'level': 'national_us',
  'eligibility': 'U.S. high school seniors',
  'deadline_kind': 'application_deadline',
  'dates_text': 'Application deadline November 5, 2026 at 8pm ET; finals week March 11-17, 2027',
  'source_url': 'https://www.societyforscience.org/regeneron-sts/',
  'checked_at': '2026-10-11',
  'selection_note': 'Direct application; about 2,600 entrants per year'},
 {'key': 'usaco',
  'name': 'USA Computing Olympiad (USACO)',
  'organizer': 'USACO',
  'category': 'informatics',
  'level': 'national_us',
  'eligibility': 'Pre-college students; contests open online',
  'deadline_kind': 'event_dates',
  'dates_text': '2025-26 season: contests Jan 9-12, Jan 30-Feb 2, Feb 20-23; US Open March 28 '
                '(proctored); 2026-27 schedule not posted as of 2026-10-11',
  'source_url': 'https://usaco.org/',
  'checked_at': '2026-10-11',
  'selection_note': 'Online contests feed training camp and IOI/EGOI teams'},
 {'key': 'usapho',
  'name': 'USA Physics Olympiad (USAPhO, via F=ma)',
  'organizer': 'AAPT and American Institute of Physics',
  'category': 'physics',
  'level': 'national_us',
  'eligibility': 'High school students; school registers as test site',
  'deadline_kind': 'not_announced',
  'dates_text': '2027 F=ma/USAPhO dates not announced as of 2026-10-11 (2026 U.S. Physics Team '
                'program page live)',
  'source_url': 'https://www.aapt.org/physicsteam/',
  'checked_at': '2026-10-11',
  'selection_note': 'F=ma exam feeds USAPhO and the U.S. Physics Team'},
 {'key': 'science-olympiad',
  'name': 'Science Olympiad',
  'organizer': 'Science Olympiad, Inc.',
  'category': 'stem_team',
  'level': 'national_us',
  'eligibility': 'School teams via state chapters; Division C is grades 9-12',
  'deadline_kind': 'event_dates',
  'dates_text': '2027 National Tournament: Ohio State University, May 14-15, 2027',
  'source_url': 'https://www.soinc.org/future-national-tournaments',
  'checked_at': '2026-10-11',
  'selection_note': 'Teams advance through regional and state tournaments'},
 {'key': 'nhd',
  'name': 'National History Day (NHD)',
  'organizer': 'National History Day, Inc.',
  'category': 'humanities',
  'level': 'national_us',
  'eligibility': 'Students in grades 6-12',
  'deadline_kind': 'varies_by_region',
  'dates_text': '2027 theme: Innovation in History: Impact, Influence, Change; contest dates vary '
                'by affiliate',
  'source_url': 'https://www.nhd.org/',
  'checked_at': '2026-10-11',
  'selection_note': 'Students advance through local and affiliate contests'},
 {'key': 'scholastic-art-writing',
  'name': 'Scholastic Art & Writing Awards',
  'organizer': 'Alliance for Young Artists & Writers',
  'category': 'arts_writing',
  'level': 'national_us',
  'eligibility': 'Teens in grades 7-12 in the U.S. and Canada',
  'deadline_kind': 'varies_by_region',
  'dates_text': '2027 Awards open October 1, 2026; regional deadlines from December 1, 2026 to as '
                'late as January 4, 2027',
  'source_url': 'https://www.artandwriting.org/awards/how-to-enter/calendar/',
  'checked_at': '2026-10-11',
  'selection_note': 'Regional adjudication feeds national medals'},
 {'key': 'deca',
  'name': 'DECA Competitive Events (ICDC)',
  'organizer': 'DECA Inc.',
  'category': 'business',
  'level': 'international',
  'eligibility': 'High school members of DECA chapters',
  'deadline_kind': 'event_dates',
  'dates_text': 'ICDC: April 17-20, 2027, Anaheim, CA',
  'source_url': 'https://www.deca.org/conferences/icdc',
  'checked_at': '2026-10-11',
  'selection_note': 'Members qualify through association conferences'},
 {'key': 'hosa',
  'name': 'HOSA Competitive Events (ILC)',
  'organizer': 'HOSA-Future Health Professionals',
  'category': 'health_professions',
  'level': 'international',
  'eligibility': 'Middle school through postsecondary HOSA members',
  'deadline_kind': 'event_dates',
  'dates_text': 'ILC: June 22-25, 2027, Philadelphia, PA',
  'source_url': 'https://hosa.org/ilc',
  'checked_at': '2026-10-11',
  'selection_note': 'Members qualify through state conferences'},
 {'key': 'first-robotics',
  'name': 'FIRST Robotics Competition (FRC)',
  'organizer': 'FIRST',
  'category': 'robotics',
  'level': 'international',
  'eligibility': 'High school students, grades 9-12',
  'deadline_kind': 'event_dates',
  'dates_text': 'BIOCORE season challenge releases January 9, 2027; events via local regionals and '
                'districts',
  'source_url': 'https://www.firstinspires.org/programs/frc/',
  'checked_at': '2026-10-11',
  'selection_note': 'Team registration via FIRST dashboard'})

def test_repair_all_sixteen_canonical_envelopes():
    assert [get_competition(row["key"]) for row in EXPECTED_REGISTRY] == list(EXPECTED_REGISTRY)
    assert list_competitions() == sorted(EXPECTED_REGISTRY, key=lambda row: row["name"])


@pytest.mark.parametrize('value',[U37Str('international'),[],1])
def test_repair_level_exact(value):
    with pytest.raises(ValueError,match='^U37:'):
        list_competitions(level=value)


def test_repair_key_cap_pair():
    refuse(lambda:get_competition('x'*128),"U37: unknown competition key '"+'x'*128+"'")
    refuse(lambda:get_competition('x'*129),'U37: key must be an exact string of at most 128 characters')


def test_repair_rows_cap_pair():
    assert validate_registry([{}]*256)['entries']==256
    refuse(lambda:validate_registry([{}]*257),'U37: entries exceed 256 rows')


@pytest.mark.parametrize('field,value', [('name','x'*2049),('key',U37Str('imo')),
    ('checked_at',U37Str('2026-10-11')),('category',U37Str('mathematics'))])
def test_repair_row_scalar_exact_bounds(field,value):
    row=get_competition('imo');row[field]=value
    with pytest.raises(ValueError,match='^U37:'):
        validate_registry([row])


def test_closing_field_count_32_33():
    row = get_competition('imo')
    row.update({'extra%d' % i: 'value' for i in range(21)})
    assert len(row) == 32
    assert validate_registry([row]) == {'entries': 1, 'issues': []}
    row['extra21'] = 'value'
    refuse(lambda: validate_registry([row]), 'U37: entry exceeds 32 fields')


@pytest.mark.parametrize('field', [U37Str('extra'), 1, 'x'*129])
def test_closing_field_name_guard(field):
    row = get_competition('imo')
    row[field] = 'value'
    refuse(lambda: validate_registry([row]), 'U37: entry fields must be exact bounded strings')


def test_closing_field_name_128_accepted():
    row = get_competition('imo')
    row['x'*128] = 'value'
    assert validate_registry([row]) == {'entries': 1, 'issues': []}


@pytest.mark.parametrize('key', [U37Str('imo'), [], 'x'*129])
def test_closing_row_key_guard(key):
    row = get_competition('imo')
    row['key'] = key
    refuse(lambda: validate_registry([row]),
           'U37: entry key must be an exact string of at most 128 characters')


def test_closing_row_key_128_accepted():
    row = get_competition('imo')
    row['key'] = 'x'*128
    assert validate_registry([row]) == {'entries': 1, 'issues': []}


@pytest.mark.parametrize('value', [None, U37Str('2026-10-11')])
def test_closing_checked_at_dedicated_refusal(value):
    row = get_competition('imo')
    row['checked_at'] = value
    refuse(lambda: validate_registry([row]), 'U37: checked_at must be an exact string')


@pytest.mark.parametrize('value', ['2026-W01-1', '20261011'])
def test_closing_checked_at_grammar(value):
    row = get_competition('imo')
    row['checked_at'] = value
    assert validate_registry([row]) == {
        'entries': 1, 'issues': ["entry 'imo' checked_at must be an ISO date"],
    }


def test_closing_value_2048_2049():
    row = get_competition('imo')
    row['name'] = 'x'*2048
    assert validate_registry([row]) == {'entries': 1, 'issues': []}
    row['name'] += 'x'
    refuse(lambda: validate_registry([row]),
           'U37: entry values must be exact strings of at most 2048 characters')


def test_closing_short_url_9_8():
    row = get_competition('imo')
    row['source_url'] = 'https://x'
    assert validate_registry([row]) == {'entries': 1, 'issues': []}
    row['source_url'] = 'https://'
    assert validate_registry([row]) == {
        'entries': 1, 'issues': ["entry 'imo' source_url must be an https URL"],
    }
