"""University-fit filter over a caller-supplied table (pure, stdlib only).

Takes a table the caller typed or exported, plus a small profile, and says per
row: fits, does_not_fit, or unverified. It never fetches anything, holds no
admissions or aid data of its own, and makes no claim about admission odds.

"fits" means only: the row is well formed, carries an https source and a
timezone-aware check date that is not in the future and is within
max_age_days, and the row's own values satisfy the profile's declared
criteria. It does NOT mean the source is official or correct, or that the
applicant would be admitted or funded. Rows with a bad or stale source, a bad
date, a missing or unknown field or an unsupported field are "unverified" and
are never judged for fit.

Enums, field names and limits come from university_fit_schema.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_SCHEMA_FILE = Path(__file__).with_name('university_fit_schema.json')
_S = json.loads(_SCHEMA_FILE.read_text(encoding='utf-8'))
MAX_ROWS = _S['limits']['max_rows']
DEFAULT_MAX_AGE_DAYS = _S['limits']['default_max_age_days']
MAX_AGE_DAYS_CEILING = _S['limits']['max_age_days_ceiling']
MAX_URL = 2048
MAX_DATE_TEXT = 40
ROW_ENUMS = _S['row']['enums']
PROFILE_BOOLS = _S['profile']['bools']
PROFILE_ENUMS = _S['profile']['enums']

METHOD_LIMITS = (
    'Filters a caller-supplied table against declared criteria only; the data is supplied, not '
    'verified or fetched here. fits means the row satisfies the criteria and is fresh; it makes no '
    'admission or funding claim, no admission-odds estimate and no use of marks or scores beyond '
    'the has_sat and ielts flags.'
)
PROVENANCE = 'caller-supplied table; not verified by this module'


def _parse_checked_at(raw: Any) -> tuple[datetime | None, str | None]:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, 'checked_at_missing'
    if not isinstance(raw, str):
        return None, 'checked_at_invalid'
    s = raw.strip()
    if len(s) > MAX_DATE_TEXT:
        return None, 'checked_at_invalid'
    if s[-1] in 'zZ':
        s = s[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None, 'checked_at_invalid'
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None, 'checked_at_naive'
    return dt.astimezone(timezone.utc), None


def _source_problem(raw: Any) -> str | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return 'source_url_missing'
    if not isinstance(raw, str) or len(raw) > MAX_URL or any(c.isspace() for c in raw):
        return 'source_url_invalid'
    try:
        parts = urlsplit(raw)
    except ValueError:
        return 'source_url_invalid'
    if parts.scheme != 'https' or not parts.netloc or not parts.hostname:
        return 'source_url_invalid'
    if '@' in parts.netloc:
        return 'source_url_invalid'
    try:
        port = parts.port
    except ValueError:
        return 'source_url_invalid'
    if port is not None and not 1 <= port <= 65535:
        return 'source_url_invalid'
    return None


def _check_profile(profile: Any) -> dict:
    if not isinstance(profile, dict):
        raise ValueError('profile must be an object')
    allowed = set(PROFILE_BOOLS) | set(PROFILE_ENUMS)
    for k in sorted(profile, key=str):
        if k not in allowed:
            raise ValueError(f'profile has unsupported field {k}')
    if 'has_sat' not in profile:
        raise ValueError('profile needs has_sat')
    out = {'require_full_aid': True, 'forbid_additional_written_test': True, 'ielts': 'maybe'}
    for k in PROFILE_BOOLS:
        if k in profile:
            if not isinstance(profile[k], bool):
                raise ValueError(f'profile.{k} must be true or false')
            out[k] = profile[k]
    for k, choices in PROFILE_ENUMS.items():
        if k in profile:
            if profile[k] not in choices:
                raise ValueError(f"profile.{k} must be one of {', '.join(choices)}")
            out[k] = profile[k]
    return out


def _field_problems(r: dict) -> list[str]:
    allowed = set(_S['row']['text']) | set(ROW_ENUMS)
    problems: list[str] = []
    for k in sorted(r, key=str):
        if k not in allowed:
            problems.append(f'unsupported_field:{k}')
    for k, choices in ROW_ENUMS.items():
        if k not in r:
            problems.append(f'missing_field:{k}')
        elif not isinstance(r[k], str) or r[k] not in choices:
            problems.append(f'invalid_value:{k}')
    return problems


def evaluate(rows: list, profile: dict, now: datetime, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> dict:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now must be a timezone-aware datetime')
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, int) \
            or not 1 <= max_age_days <= MAX_AGE_DAYS_CEILING:
        raise ValueError(f'max_age_days must be an integer from 1 to {MAX_AGE_DAYS_CEILING}')
    prof = _check_profile(profile)
    if not isinstance(rows, list):
        raise ValueError('rows must be a list')
    if len(rows) > MAX_ROWS:
        raise ValueError(f'at most {MAX_ROWS} rows are allowed, got {len(rows)}')
    now = now.astimezone(timezone.utc)

    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            raise ValueError(f'row {i} must be an object')
        name, country = r.get('university'), r.get('country')
        if not isinstance(name, str) or not name.strip() or not isinstance(country, str) or not country.strip():
            raise ValueError(f'row {i} needs a non-empty university and country')
        name, country = name.strip(), country.strip()
        key = (name, country)
        if key in seen:
            raise ValueError(f'duplicate row {name} ({country})')
        seen.add(key)

        problems = _field_problems(r)
        sp = _source_problem(r.get('source_url'))
        if sp:
            problems.append(sp)
        checked, dp = _parse_checked_at(r.get('checked_at'))
        age = None
        if dp:
            problems.append(dp)
        else:
            age = now - checked
            if checked > now:
                problems.append('checked_at_future')
            elif age > timedelta(days=max_age_days):
                problems.append('stale')

        reasons: list[str] = []
        if problems:
            verdict, reasons = 'unverified', problems
        else:
            aid, written, sat, ielts_acc = r['intl_ug_aid'], r['additional_written_test'], r['sat'], r['ielts_accepted']
            if prof['require_full_aid'] and aid != 'full':
                reasons.append('aid_not_full')
            if prof['forbid_additional_written_test'] and written == 'yes':
                reasons.append('additional_written_test_required')
            if sat == 'required' and not prof['has_sat']:
                reasons.append('sat_required_profile_has_none')
            if ielts_acc == 'no' and prof['ielts'] != 'no':
                reasons.append('ielts_not_accepted')
            verdict = 'fits' if not reasons else 'does_not_fit'
        src = r.get('source_url')
        out.append({
            'university': name, 'country': country, 'verdict': verdict, 'reasons': reasons,
            'source_url': src if isinstance(src, str) else None,
            'checked_at': checked.isoformat() if checked is not None else None,
            'age_days': round(age.total_seconds() / 86400, 6) if age is not None else None,
        })
    out.sort(key=lambda x: (x['university'], x['country']))
    counts = {'rows': len(out)}
    for v in ('fits', 'does_not_fit', 'unverified'):
        counts[v] = sum(1 for x in out if x['verdict'] == v)
    return {'feature': 'university_fit', 'rows': out, 'counts': counts,
            'profile': prof, 'max_age_days': max_age_days, 'as_of': now.isoformat(),
            'data_provenance': PROVENANCE, 'method_limits': METHOD_LIMITS}
