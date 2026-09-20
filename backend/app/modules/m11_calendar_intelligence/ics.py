"""Minimal iCalendar (RFC 5545) VEVENT parsing, stdlib only.

Covers what CalDAV/ICS feeds actually carry for events: UID, SUMMARY,
DTSTART/DTEND (UTC, floating, or all-day), LOCATION, STATUS. TZID-local
times are treated as floating and surfaced as UTC; recurring RRULE
expansion is integrator work (documented in INTEGRATION.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class IcsEvent:
    uid: str
    summary: str = ""
    start: datetime | None = None
    end: datetime | None = None
    location: str | None = None
    status: str = "confirmed"
    raw: dict[str, str] = field(default_factory=dict)


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line)
    return lines


def parse_datetime(value: str, params: dict[str, str]) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    if params.get("VALUE", "").upper() == "DATE" or (len(value) == 8 and value.isdigit()):
        return datetime(
            int(value[0:4]), int(value[4:6]), int(value[6:8]), tzinfo=timezone.utc
        )
    if value.endswith("Z"):
        value = value[:-1]
        try:
            return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    try:
        # Floating / TZID-local time: surfaced as UTC (documented limitation).
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_ics_events(text: str) -> list[IcsEvent]:
    events: list[IcsEvent] = []
    current: dict[str, str] | None = None
    params: dict[str, dict[str, str]] = {}
    for line in _unfold(text):
        upper = line.upper()
        if upper == "BEGIN:VEVENT":
            current, params = {}, {}
            continue
        if upper == "END:VEVENT" and current is not None:
            events.append(
                IcsEvent(
                    uid=current.get("UID", ""),
                    summary=current.get("SUMMARY", ""),
                    start=parse_datetime(current.get("DTSTART", ""), params.get("DTSTART", {})),
                    end=parse_datetime(current.get("DTEND", ""), params.get("DTEND", {})),
                    location=current.get("LOCATION") or None,
                    status=current.get("STATUS", "confirmed").lower(),
                    raw=current,
                )
            )
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key_part, _, value = line.partition(":")
        key, _, param_part = key_part.partition(";")
        key = key.upper()
        current[key] = value
        props: dict[str, str] = {}
        for pair in param_part.split(";"):
            if "=" in pair:
                k, _, v = pair.partition("=")
                props[k.strip().upper()] = v.strip()
        params[key] = props
    return events


def format_ics_dt(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
