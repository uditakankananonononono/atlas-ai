"""U37 "All top competitions for high schoolers": curated registry.

A bounded curated list of 16 widely recognized high-school competitions.
Candidate curation is attributed to the original package. Official pages were
re-fetched for this repair on 2026-10-12; source evidence and caveats are in
the contract. Each entry carries dated source text, not a live guarantee.
The existing m01 service normalizes collected feed items generically; this
unit is a bounded curated registry, which no existing surface
provides. It is a list, not an application: no registration, autofill,
submission or outreach happens here.
"""
from datetime import date
import re

PREFIX = 'U37'
CHECKED_AT = '2026-10-11'
MAX_KEY = 128
MAX_ROWS = 256
MAX_TEXT = 2048

CATEGORIES = ('arts_writing', 'biology', 'business', 'chemistry',
              'health_professions', 'humanities', 'informatics', 'mathematics',
              'physics', 'robotics', 'science_research', 'stem_team')
LEVELS = ('international', 'national_us')
DEADLINE_KINDS = ('application_deadline', 'event_dates', 'not_announced',
                  'varies_by_country', 'varies_by_region')

_REQUIRED = ('key', 'name', 'organizer', 'category', 'level', 'eligibility',
             'deadline_kind', 'dates_text', 'source_url', 'checked_at',
             'selection_note')

COMPETITIONS = (
    {'key': 'amc-10-12', 'name': 'AMC 10/12 (American Mathematics Competitions)',
     'organizer': 'Mathematical Association of America',
     'category': 'mathematics', 'level': 'national_us',
     'eligibility': 'AMC 10: grades 10 and below, under 17.5 on competition day; '
                    'AMC 12: grades 12 and below, under 19.5',
     'deadline_kind': 'event_dates',
     'dates_text': '2026-27: AMC 10A/12A November 5, 2026; '
                   'AMC 10B/12B November 13, 2026',
     'source_url': 'https://maa.org/student-programs/amc/',
     'checked_at': CHECKED_AT,
     'selection_note': 'School competition manager registers; path to AIME/USAMO '
                       'and the U.S. IMO team; national_us denotes this U.S. pathway, not exclusive eligibility. MAA also offers AMC International outside the USA and Canada.'},
    {'key': 'imo', 'name': 'International Mathematical Olympiad (IMO)',
     'organizer': 'IMO Board', 'category': 'mathematics', 'level': 'international',
     'eligibility': 'Pre-university students in national teams of up to 6',
     'deadline_kind': 'varies_by_country',
     'dates_text': 'IMO 2027: Budapest, Hungary, July 16-26, 2027 '
                   '(IMO 2026 Shanghai, July 10-21, 2026, completed)',
     'source_url': 'https://www.imo-official.org/', 'checked_at': CHECKED_AT,
     'selection_note': 'National selection contests feed each team'},
    {'key': 'ipho', 'name': 'International Physics Olympiad (IPhO)',
     'organizer': 'IPhO Secretariat', 'category': 'physics', 'level': 'international',
     'eligibility': 'Secondary school students in national teams of up to 5',
     'deadline_kind': 'varies_by_country',
     'dates_text': 'IPhO 2026: Bucaramanga, Colombia, July 4-12, 2026 (completed)',
     'source_url': 'https://www.ipho-new.org/', 'checked_at': CHECKED_AT,
     'selection_note': 'National selection (e.g. USAPhO path) feeds each team'},
    {'key': 'icho', 'name': 'International Chemistry Olympiad (IChO)',
     'organizer': 'IChO Steering Committee', 'category': 'chemistry',
     'level': 'international',
     'eligibility': 'Secondary school students in national teams',
     'deadline_kind': 'varies_by_country',
     'dates_text': 'IChO 2026: Tashkent, Uzbekistan, July 10-19, 2026 (completed)',
     'source_url': 'https://icho2026.uz/', 'checked_at': CHECKED_AT,
     'selection_note': 'National selection feeds each team'},
    {'key': 'ibo', 'name': 'International Biology Olympiad (IBO)',
     'organizer': 'IBO Association', 'category': 'biology', 'level': 'international',
     'eligibility': 'Secondary school students in national teams of up to 4',
     'deadline_kind': 'varies_by_country',
     'dates_text': 'IBO 2027: Warsaw, Poland, July 18-25, 2027',
     'source_url': 'https://www.ibo-info.org/en/competition.html',
     'checked_at': CHECKED_AT,
     'selection_note': 'National selection (e.g. USABO) feeds each team'},
    {'key': 'ioi', 'name': 'International Olympiad in Informatics (IOI)',
     'organizer': 'IOI Committee', 'category': 'informatics', 'level': 'international',
     'eligibility': 'Secondary school students in national teams of up to 4',
     'deadline_kind': 'varies_by_country',
     'dates_text': 'IOI 2027: Germany (dates not stated on site); '
                   'IOI 2026 Uzbekistan, August 9-16, 2026 (completed)',
     'source_url': 'https://ioinformatics.org/', 'checked_at': CHECKED_AT,
     'selection_note': 'National selection (e.g. USACO) feeds each team'},
    {'key': 'isef', 'name': 'Regeneron International Science and Engineering Fair (ISEF)',
     'organizer': 'Society for Science', 'category': 'science_research',
     'level': 'international',
     'eligibility': 'High-school students qualifying via Society-affiliated fairs',
     'deadline_kind': 'event_dates',
     'dates_text': 'ISEF 2027 Los Angeles: grand-award and affiliated-fair pages state May 8-14, 2027; college-fair page states May 9-14, 2027; homepage states no 2027 dates. Official pages conflict; verify the applicable schedule.',
     'source_url': 'https://www.societyforscience.org/isef/',
     'checked_at': CHECKED_AT,
     'selection_note': 'Qualification through affiliated regional fairs'},
    {'key': 'regeneron-sts', 'name': 'Regeneron Science Talent Search (STS)',
     'organizer': 'Society for Science', 'category': 'science_research',
     'level': 'national_us', 'eligibility': 'U.S. high school seniors',
     'deadline_kind': 'application_deadline',
     'dates_text': 'Application deadline November 5, 2026 at 8pm ET; '
                   'finals week March 11-17, 2027',
     'source_url': 'https://www.societyforscience.org/regeneron-sts/',
     'checked_at': CHECKED_AT,
     'selection_note': 'Direct application; about 2,600 entrants per year'},
    {'key': 'usaco', 'name': 'USA Computing Olympiad (USACO)',
     'organizer': 'USACO', 'category': 'informatics', 'level': 'national_us',
     'eligibility': 'Pre-college students; contests open online',
     'deadline_kind': 'event_dates',
     'dates_text': '2025-26 season: contests Jan 9-12, Jan 30-Feb 2, Feb 20-23; '
                   'US Open March 28 (proctored); 2026-27 schedule not posted '
                   'as of 2026-10-11',
     'source_url': 'https://usaco.org/', 'checked_at': CHECKED_AT,
     'selection_note': 'Online contests feed training camp and IOI/EGOI teams'},
    {'key': 'usapho', 'name': 'USA Physics Olympiad (USAPhO, via F=ma)',
     'organizer': 'AAPT and American Institute of Physics',
     'category': 'physics', 'level': 'national_us',
     'eligibility': 'High school students; school registers as test site',
     'deadline_kind': 'not_announced',
     'dates_text': '2027 F=ma/USAPhO dates not announced as of 2026-10-11 '
                   '(2026 U.S. Physics Team program page live)',
     'source_url': 'https://www.aapt.org/physicsteam/', 'checked_at': CHECKED_AT,
     'selection_note': 'F=ma exam feeds USAPhO and the U.S. Physics Team'},
    {'key': 'science-olympiad', 'name': 'Science Olympiad',
     'organizer': 'Science Olympiad, Inc.', 'category': 'stem_team',
     'level': 'national_us',
     'eligibility': 'School teams via state chapters; Division C is grades 9-12',
     'deadline_kind': 'event_dates',
     'dates_text': '2027 National Tournament: Ohio State University, '
                   'May 14-15, 2027',
     'source_url': 'https://www.soinc.org/future-national-tournaments',
     'checked_at': CHECKED_AT,
     'selection_note': 'Teams advance through regional and state tournaments'},
    {'key': 'nhd', 'name': 'National History Day (NHD)',
     'organizer': 'National History Day, Inc.', 'category': 'humanities',
     'level': 'national_us', 'eligibility': 'Students in grades 6-12',
     'deadline_kind': 'varies_by_region',
     'dates_text': '2027 theme: Innovation in History: Impact, Influence, '
                   'Change; contest dates vary by affiliate',
     'source_url': 'https://www.nhd.org/', 'checked_at': CHECKED_AT,
     'selection_note': 'Students advance through local and affiliate contests'},
    {'key': 'scholastic-art-writing', 'name': 'Scholastic Art & Writing Awards',
     'organizer': 'Alliance for Young Artists & Writers',
     'category': 'arts_writing', 'level': 'national_us',
     'eligibility': 'Teens in grades 7-12 in the U.S. and Canada',
     'deadline_kind': 'varies_by_region',
     'dates_text': '2027 Awards open October 1, 2026; regional deadlines from '
                   'December 1, 2026 to as late as January 4, 2027',
     'source_url': 'https://www.artandwriting.org/awards/how-to-enter/calendar/',
     'checked_at': CHECKED_AT,
     'selection_note': 'Regional adjudication feeds national medals'},
    {'key': 'deca', 'name': 'DECA Competitive Events (ICDC)',
     'organizer': 'DECA Inc.', 'category': 'business', 'level': 'international',
     'eligibility': 'High school members of DECA chapters',
     'deadline_kind': 'event_dates',
     'dates_text': 'ICDC: April 17-20, 2027, Anaheim, CA',
     'source_url': 'https://www.deca.org/conferences/icdc',
     'checked_at': CHECKED_AT,
     'selection_note': 'Members qualify through association conferences'},
    {'key': 'hosa', 'name': 'HOSA Competitive Events (ILC)',
     'organizer': 'HOSA-Future Health Professionals', 'category': 'health_professions',
     'level': 'international',
     'eligibility': 'Middle school through postsecondary HOSA members',
     'deadline_kind': 'event_dates',
     'dates_text': 'ILC: June 22-25, 2027, Philadelphia, PA',
     'source_url': 'https://hosa.org/ilc', 'checked_at': CHECKED_AT,
     'selection_note': 'Members qualify through state conferences'},
    {'key': 'first-robotics', 'name': 'FIRST Robotics Competition (FRC)',
     'organizer': 'FIRST', 'category': 'robotics', 'level': 'international',
     'eligibility': 'High school students, grades 9-12',
     'deadline_kind': 'event_dates',
     'dates_text': 'BIOCORE season challenge releases January 9, 2027; '
                   'events via local regionals and districts',
     'source_url': 'https://www.firstinspires.org/programs/frc/',
     'checked_at': CHECKED_AT,
     'selection_note': 'Team registration via FIRST dashboard'},
)


def _fail(message):
    raise ValueError(f'{PREFIX}: {message}')


def _check_category(category):
    if type(category) is not str or len(category) > MAX_KEY:
        _fail('category must be an exact string of at most 128 characters')
    if category not in CATEGORIES:
        _fail(f'category must be one of {", ".join(CATEGORIES)}')
    return category


def _check_level(level):
    if type(level) is not str or len(level) > MAX_KEY:
        _fail('level must be an exact string of at most 128 characters')
    if level not in LEVELS:
        _fail(f'level must be one of {", ".join(LEVELS)}')
    return level


def list_competitions(category=None, level=None):
    """Return entries, optionally filtered, sorted by competition name."""
    if category is not None:
        _check_category(category)
    if level is not None:
        _check_level(level)
    rows = [c for c in COMPETITIONS
            if (category is None or c['category'] == category)
            and (level is None or c['level'] == level)]
    return sorted([dict(c) for c in rows], key=lambda c: c['name'])


def get_competition(key):
    """Return one entry by key; unknown keys refuse."""
    if type(key) is not str or len(key) > MAX_KEY:
        _fail('key must be an exact string of at most 128 characters')
    for c in COMPETITIONS:
        if c['key'] == key:
            return dict(c)
    _fail(f'unknown competition key {key!r}')


def summarize():
    """Count entries by category, level and deadline kind in use."""
    by_category = {}
    for c in COMPETITIONS:
        by_category[c['category']] = by_category.get(c['category'], 0) + 1
    by_level = {}
    for c in COMPETITIONS:
        by_level[c['level']] = by_level.get(c['level'], 0) + 1
    kinds = sorted({c['deadline_kind'] for c in COMPETITIONS})
    return {'total': len(COMPETITIONS), 'by_category': by_category,
            'by_level': by_level, 'deadline_kinds_used': kinds}


def validate_registry(entries=None):
    """Check registry consistency; returns entry count plus issue list."""
    rows = COMPETITIONS if entries is None else entries
    if type(rows) not in (list, tuple):
        _fail('entries must be an exact list or tuple')
    if len(rows) > MAX_ROWS:
        _fail('entries exceed 256 rows')
    issues = []
    seen = set()
    for c in rows:
        if type(c) is not dict:
            _fail('entry must be an exact object')
        if len(c) > 32:
            _fail('entry exceeds 32 fields')
        if any(type(k) is not str or len(k) > MAX_KEY for k in c):
            _fail('entry fields must be exact bounded strings')
        key = c.get('key', '?')
        if type(key) is not str or len(key) > MAX_KEY:
            _fail('entry key must be an exact string of at most 128 characters')
        if 'checked_at' in c and type(c['checked_at']) is not str:
            _fail('checked_at must be an exact string')
        if any(type(v) is not str or len(v) > MAX_TEXT for v in c.values()):
            _fail('entry values must be exact strings of at most 2048 characters')
        if key in seen:
            issues.append(f'duplicate key {key!r}')
            continue
        seen.add(key)
        for field in _REQUIRED:
            if field not in c:
                issues.append(f'entry {key!r} missing field {field!r}')
                break
        else:
            for field in _REQUIRED:
                if not c[field].strip():
                    issues.append(f'entry {key!r} {field} must be nonblank')
            if c['category'] not in CATEGORIES:
                issues.append(f'entry {key!r} category not in CATEGORIES')
            if c['level'] not in LEVELS:
                issues.append(f'entry {key!r} level not in LEVELS')
            if not c['source_url'].startswith('https://') or len(c['source_url']) <= 8:
                issues.append(f'entry {key!r} source_url must be an https URL')
            if c['deadline_kind'] not in DEADLINE_KINDS:
                issues.append(f'entry {key!r} deadline_kind '
                              f'{c["deadline_kind"]!r} not in DEADLINE_KINDS')
            try:
                if len(c['checked_at']) != 10 or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', c['checked_at']):
                    raise ValueError
                date.fromisoformat(c['checked_at'])
            except ValueError:
                issues.append(f'entry {key!r} checked_at must be an ISO date')
    return {'entries': len(rows), 'issues': issues}
