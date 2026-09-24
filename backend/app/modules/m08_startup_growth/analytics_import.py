"""Import experiment observations from free analytics exports (M08 enhancement).

Two paths, both offline parsing of files she downloaded herself:

- ``plausible``: Plausible's CSV export (same schema as its CSV importer,
  ``lib/plausible/imported/csv_importer.ex``):
  ``imported_visitors`` = ``date, visitors, pageviews, bounces, visits, visit_duration``
  ``imported_custom_events`` = ``date, name, link_url, path, visitors, events``.
  Exposures = sum of ``visitors`` over the window; conversions = sum of
  ``visitors`` on rows of the named goal event. Daily unique visitors summed
  over days are visitor-days, not people - reported as such.
- ``mapped``: any CSV (Umami, a sheet, a form tool) with the owner naming the
  exposures column, the conversions column, and optionally a date column and a
  row filter.

Each import is fingerprinted (file hashes + window + goal); the same import
cannot be recorded twice, so re-uploading a file never double counts.
"""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import date
from typing import Any


class ImportError_(ValueError):
    pass


def _rows(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise ImportError_("CSV has no header row")
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in reader]


def _in_window(value: str, start: date | None, end: date | None) -> bool:
    if start is None and end is None:
        return True
    try:
        d = date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ImportError_(f"unreadable date '{value}'") from exc
    return (start is None or d >= start) and (end is None or d <= end)


def _int(value: str, col: str) -> int:
    try:
        return int(float(value.replace(",", "") or 0))
    except ValueError as exc:
        raise ImportError_(f"column {col}: '{value}' is not a number") from exc


def _need(rows: list[dict[str, str]], cols: list[str], label: str) -> None:
    if rows and any(c not in rows[0] for c in cols):
        raise ImportError_(f"{label} is missing columns {[c for c in cols if c not in rows[0]]}; has {sorted(rows[0])}")


def fingerprint(parts: list[str]) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def from_plausible(*, visitors_csv: str, custom_events_csv: str, goal: str,
                   start: date | None = None, end: date | None = None) -> dict[str, Any]:
    v, e = _rows(visitors_csv), _rows(custom_events_csv)
    _need(v, ["date", "visitors"], "imported_visitors")
    _need(e, ["date", "name", "visitors"], "imported_custom_events")
    days = [r for r in v if _in_window(r["date"], start, end)]
    exposures = sum(_int(r["visitors"], "visitors") for r in days)
    goal_rows = [r for r in e if r["name"] == goal and _in_window(r["date"], start, end)]
    if not goal_rows and not any(r["name"] == goal for r in e):
        names = sorted({r["name"] for r in e})[:20]
        raise ImportError_(f"goal '{goal}' not found in custom events; present: {names}")
    conversions = sum(_int(r["visitors"], "visitors") for r in goal_rows)
    if conversions > exposures:
        raise ImportError_(f"goal visitors ({conversions}) exceed site visitors ({exposures}) for this window")
    return {"exposures": exposures, "conversions": conversions, "days": len(days),
            "unit": "daily unique visitors summed over days (visitor-days)",
            "window": [start.isoformat() if start else None, end.isoformat() if end else None],
            "fingerprint": fingerprint(["plausible", hashlib.sha256(visitors_csv.encode()).hexdigest(),
                                        hashlib.sha256(custom_events_csv.encode()).hexdigest(), goal,
                                        str(start), str(end)]),
            "source": f"plausible export, goal '{goal}'"}


def from_mapped(*, csv_text: str, exposures_col: str, conversions_col: str, date_col: str | None = None,
                filter_col: str | None = None, filter_value: str | None = None,
                start: date | None = None, end: date | None = None, label: str = "csv") -> dict[str, Any]:
    rows = _rows(csv_text)
    cols = [exposures_col, conversions_col] + [c for c in (date_col, filter_col) if c]
    _need(rows, cols, label)
    if (start or end) and not date_col:
        raise ImportError_("a date window needs date_col")
    picked = [r for r in rows if (not filter_col or r[filter_col] == filter_value)
              and (not date_col or _in_window(r[date_col], start, end))]
    exposures = sum(_int(r[exposures_col], exposures_col) for r in picked)
    conversions = sum(_int(r[conversions_col], conversions_col) for r in picked)
    if conversions > exposures:
        raise ImportError_(f"conversions ({conversions}) exceed exposures ({exposures})")
    return {"exposures": exposures, "conversions": conversions, "rows": len(picked),
            "unit": f"sum of {exposures_col} / {conversions_col}",
            "window": [start.isoformat() if start else None, end.isoformat() if end else None],
            "fingerprint": fingerprint(["mapped", hashlib.sha256(csv_text.encode()).hexdigest(), exposures_col,
                                        conversions_col, str(date_col), str(filter_col), str(filter_value),
                                        str(start), str(end)]),
            "source": f"{label}: {conversions_col}/{exposures_col}"}
