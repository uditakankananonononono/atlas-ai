"""Per-fact source freshness for study-abroad records (pure, no I/O).

Additive lifecycle-workbench/source-freshness route uses this helper.
Never fetches anything and never makes an eligibility claim. It only says how
old a recorded check is. A URL alone is never "verified".

Statuses: fresh | stale | unknown. Every unknown carries a reason code, so
missing, malformed, naive, future and URL problems stay distinguishable.
"fresh" means only: a well-formed https URL plus a timezone-aware check time
that is not in the future and is within max_age_days. It does NOT mean the
URL is official, reachable, or that the fact is correct.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

FRESH, STALE, UNKNOWN = 'fresh', 'stale', 'unknown'
MAX_FACTS = 500
MAX_TEXT = 500
MAX_URL = 2048
DEFAULT_MAX_AGE_DAYS = 180
MAX_AGE_DAYS_CEILING = 3650
FUTURE_SKEW = timedelta(minutes=5)
EARLIEST = datetime(2000, 1, 1, tzinfo=timezone.utc)


class FreshnessError(ValueError):
    """Raised for caller errors (bad batch shape, bad now/max_age), not bad facts."""


@dataclass(frozen=True)
class FactFreshness:
    fact_id: str
    subject: str
    field: str
    value: str
    status: str
    reason: str
    source_url: str | None
    checked_at: str | None  # normalized UTC ISO-8601, or None if not usable
    age_days: float | None
    max_age_days: int
    provenance: Mapping[str, Any]

    def as_dict(self) -> dict:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        d['provenance'] = dict(self.provenance)
        return d


def _text(v: Any) -> str:
    if v is None:
        return ''
    if not isinstance(v, (str, int, float)) or isinstance(v, bool):
        return ''
    return str(v).strip()[:MAX_TEXT]


def parse_checked_at(raw: Any) -> tuple[datetime | None, str]:
    """Return (utc datetime, 'ok') or (None, reason). Strict: ISO-8601 str with offset."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, 'timestamp_missing'
    if not isinstance(raw, str):
        return None, 'timestamp_invalid'
    s = raw.strip()
    if len(s) > 40:
        return None, 'timestamp_invalid'
    if s[-1] in 'zZ':
        s = s[:-1] + '+00:00'
    if 'T' not in s and ' ' not in s:
        return None, 'timestamp_invalid'  # date-only has no time or zone
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None, 'timestamp_invalid'
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None, 'timestamp_timezone_missing'
    try:dt = dt.astimezone(timezone.utc)
    except (OverflowError, ValueError):return None,'timestamp_invalid'
    if dt < EARLIEST:
        return None, 'timestamp_invalid'
    return dt, 'ok'


def check_url(raw: Any, allowed_domains: Iterable[str] | None = None) -> tuple[str | None, str]:
    """Return (normalized url, 'ok') or (None, reason). Syntax only, no network."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, 'url_missing'
    if not isinstance(raw, str):
        return None, 'url_invalid'
    u = raw.strip()
    if len(u) > MAX_URL or any(c.isspace() or ord(c) < 32 for c in u):
        return None, 'url_invalid'
    try:
        p = urlsplit(u)
        host = (p.hostname or '').lower()
        p.port  # raises on a bad port
    except ValueError:
        return None, 'url_invalid'
    if p.scheme.lower() != 'https':
        return None, 'url_not_https'
    if not host or '.' not in host or p.username or p.password:
        return None, 'url_invalid'
    if allowed_domains is not None:
        allowed = [d.lower().lstrip('.') for d in allowed_domains if isinstance(d, str) and d.strip()]
        if not any(host == d or host.endswith('.' + d) for d in allowed):
            return None, 'url_domain_not_allowed'
    return u, 'ok'


def _validate_params(now: datetime, max_age_days: int) -> None:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise FreshnessError('now must be a timezone-aware datetime supplied by the caller')
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, int) or not 1 <= max_age_days <= MAX_AGE_DAYS_CEILING:
        raise FreshnessError(f'max_age_days must be an int in 1..{MAX_AGE_DAYS_CEILING}')


def assess_fact(raw: Any, *, now: datetime, max_age_days: int = DEFAULT_MAX_AGE_DAYS,
                allowed_domains: Iterable[str] | None = None, index: int = 0) -> FactFreshness:
    """Assess one fact record: keys fact_id, subject, field, value, source_url
    (alias official_url), checked_at. A per-fact max_age_days int may override."""
    _validate_params(now, max_age_days)
    r = raw if isinstance(raw, Mapping) else {}
    per = r.get('max_age_days')
    if isinstance(per, int) and not isinstance(per, bool) and 1 <= per <= MAX_AGE_DAYS_CEILING:
        max_age_days = per
    fid = _text(r.get('fact_id')) or f'fact-{index}'
    url_raw = r.get('source_url', r.get('official_url'))
    url, url_state = check_url(url_raw, allowed_domains)
    dt, ts_state = parse_checked_at(r.get('checked_at'))
    now_utc = now.astimezone(timezone.utc)
    age = None
    if not isinstance(raw, Mapping):
        status, reason = UNKNOWN, 'record_not_object'
    elif url is None:
        # URL problem dominates; a timestamp without a usable source is still unknown.
        status, reason = UNKNOWN, url_state
    elif dt is None:
        # A URL alone is never verified.
        status, reason = UNKNOWN, ts_state
    elif dt - now_utc > FUTURE_SKEW:
        status, reason = UNKNOWN, 'timestamp_future'
    else:
        age = max(0.0, (now_utc - dt).total_seconds() / 86400)
        if age > max_age_days:
            status, reason = STALE, 'older_than_max_age'
        else:
            status, reason = FRESH, 'checked_within_max_age'
    return FactFreshness(
        fact_id=fid, subject=_text(r.get('subject')), field=_text(r.get('field')), value=_text(r.get('value')),
        status=status, reason=reason, source_url=url,
        checked_at=dt.isoformat() if dt else None,
        age_days=round(age, 2) if age is not None else None, max_age_days=max_age_days,
        provenance={'source_url': url, 'source_url_state': url_state, 'checked_at_state': ts_state,
                    'assessed_at': now_utc.isoformat(), 'origin': 'caller_supplied_record',
                    'official_status_attested': False, 'fetched_by_this_module': False})


def assess_facts(records: Any, *, now: datetime, max_age_days: int = DEFAULT_MAX_AGE_DAYS,
                 allowed_domains: Iterable[str] | None = None) -> dict:
    """Bounded batch assessment. Raises FreshnessError if records is not a
    non-empty list of at most MAX_FACTS; bad individual facts become unknown."""
    _validate_params(now, max_age_days)
    if not isinstance(records, list) or not records:
        raise FreshnessError('records must be a non-empty list')
    if len(records) > MAX_FACTS:
        raise FreshnessError(f'too many records (max {MAX_FACTS})')
    allowed = list(allowed_domains) if allowed_domains is not None else None
    facts = [assess_fact(r, now=now, max_age_days=max_age_days, allowed_domains=allowed, index=i)
             for i, r in enumerate(records)]
    counts = {s: sum(f.status == s for f in facts) for s in (FRESH, STALE, UNKNOWN)}
    return {'facts': [f.as_dict() for f in facts], 'counts': counts, 'total': len(facts),
            'max_age_days': max_age_days,
            'limits': ['Freshness of a recorded check only; not official-source, reachability, correctness, or eligibility verification.',
                       'No network access was performed.']}
