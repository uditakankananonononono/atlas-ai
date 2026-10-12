"""Row 107 / registry freshness audit for the U37 high-school competition list.

Source excerpt (supplied text): "discover all top high school competitions".
Offline, stdlib only. Given registry rows and a date, report rows whose
source check is stale, whose source URL is not https, duplicate keys or
URLs, and categories with fewer than MIN_PER_CATEGORY rows. It does not fetch
pages and cannot show the list is exhaustive: coverage is only ever
reported as "N curated rows", never "all competitions".
"""
from __future__ import annotations

from datetime import date
from urllib.parse import urlparse

STALE_DAYS = 45
MIN_PER_CATEGORY = 2


def _day(value):
    if not isinstance(value, str):
        raise ValueError("REGISTRY_AUDIT_REFUSED_BAD_TYPE:date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("REGISTRY_AUDIT_REFUSED_BAD_DATE")


def audit(rows, today, stale_days=STALE_DAYS):
    if isinstance(rows, bool) or not isinstance(rows, (list, tuple)):
        raise ValueError("REGISTRY_AUDIT_REFUSED_BAD_TYPE:rows")
    now = _day(today)
    findings, keys, urls, cats = [], {}, {}, {}
    for r in rows:
        if not isinstance(r, dict):
            raise ValueError("REGISTRY_AUDIT_REFUSED_BAD_TYPE:row")
        k = r.get("key")
        keys[k] = keys.get(k, 0) + 1
        u = r.get("source_url")
        urls.setdefault(u, []).append(k)
        cats[r.get("category")] = cats.get(r.get("category"), 0) + 1
        if urlparse(u or "").scheme != "https":
            findings.append({"key": k, "issue": "SOURCE_NOT_HTTPS"})
        try:
            age = (now - _day(r.get("checked_at"))).days
        except ValueError:
            findings.append({"key": k, "issue": "BAD_CHECKED_AT"})
            continue
        if age < 0:
            findings.append({"key": k, "issue": "CHECKED_IN_FUTURE"})
        elif age > stale_days:
            findings.append({"key": k, "issue": "STALE_SOURCE_CHECK", "age_days": age})
    findings += [{"key": k, "issue": "DUPLICATE_KEY"} for k, n in keys.items() if n > 1]
    findings += [{"key": ks[0], "issue": "DUPLICATE_SOURCE_URL", "keys": ks}
                 for u, ks in urls.items() if len(ks) > 1]
    thin = sorted(c for c, n in cats.items() if n < MIN_PER_CATEGORY)
    return {"rows": len(rows), "as_of": today, "findings": findings,
            "thin_categories": thin, "clean": not findings,
            "coverage_statement": "%d curated rows; exhaustiveness not established" % len(rows),
            "scope": {"implemented": ["freshness, https, duplicate and category-depth checks"],
                      "not_implemented": ["page fetching", "discovery of new competitions",
                                          "proof of exhaustive coverage"],
                      "data_source": "supplied registry rows"}}
