"""Resolve a wall-clock time in an IANA zone to a UTC instant, DST-safe.

``2026-11-01T01:30`` in America/New_York happens twice and
``2026-03-08T02:30`` never happens. Guessing either would publish an hour off,
so the default policy is to reject both with a controlled error and let the
caller pick an explicit policy. Uses the system/tzdata zone database through
``zoneinfo``; an unknown zone name is an error, never a silent UTC fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

AMBIGUOUS_POLICIES = ("reject", "earlier", "later")
GAP_POLICIES = ("reject", "shift_forward")


class LocalTimeError(ValueError):
    """Base for local-time resolution failures."""


class InvalidTimezoneError(LocalTimeError):
    pass


class NonexistentLocalTimeError(LocalTimeError):
    """The wall-clock time falls in a DST gap and never occurs in that zone."""


class AmbiguousLocalTimeError(LocalTimeError):
    """The wall-clock time occurs twice (DST fold) in that zone."""


@dataclass(frozen=True)
class ResolvedLocalTime:
    instant_utc: datetime
    local_requested: str
    local_resolved: str
    timezone: str
    utc_offset_minutes: int
    ambiguous: bool
    in_gap: bool
    adjustment: str | None


def _zone(name: str) -> ZoneInfo:
    if not name or not name.strip() or name.strip().lower() in {"utc+0", "local"}:
        raise InvalidTimezoneError(f"unknown timezone: {name!r}")
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError, OSError) as error:
        raise InvalidTimezoneError(f"unknown timezone: {name!r}") from error


def resolve_local(
    local: datetime, tz_name: str, *, on_ambiguous: str = "reject", on_gap: str = "reject"
) -> ResolvedLocalTime:
    if local.tzinfo is not None:
        raise LocalTimeError("local time must not carry its own offset; pass it with a timezone name")
    if on_ambiguous not in AMBIGUOUS_POLICIES:
        raise LocalTimeError(f"on_ambiguous must be one of {AMBIGUOUS_POLICIES}")
    if on_gap not in GAP_POLICIES:
        raise LocalTimeError(f"on_gap must be one of {GAP_POLICIES}")
    zone = _zone(tz_name)
    first = local.replace(tzinfo=zone, fold=0)
    second = local.replace(tzinfo=zone, fold=1)
    off_first, off_second = first.utcoffset(), second.utcoffset()
    # Round trip through UTC: a gap time does not survive it.
    survives = first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == local
    ambiguous = survives and off_first != off_second
    adjustment = None
    chosen = first
    in_gap = not survives
    if in_gap:
        if on_gap == "reject":
            raise NonexistentLocalTimeError(f"{local.isoformat()} does not exist in {tz_name} (DST gap)")
        # Clocks jump forward by (offset after - offset before): keep the same elapsed
        # time from the pre-gap offset, which lands on the first valid minute after the gap.
        instant = (local - off_first).replace(tzinfo=timezone.utc)
        chosen = instant.astimezone(zone)
        adjustment = "shifted_forward_over_dst_gap"
    elif ambiguous:
        if on_ambiguous == "reject":
            raise AmbiguousLocalTimeError(f"{local.isoformat()} occurs twice in {tz_name} (DST fold)")
        chosen = first if on_ambiguous == "earlier" else second
        adjustment = f"ambiguous_resolved_{on_ambiguous}"
    instant_utc = chosen.astimezone(timezone.utc)
    return ResolvedLocalTime(
        instant_utc=instant_utc,
        local_requested=local.isoformat(),
        local_resolved=chosen.replace(tzinfo=None).isoformat(),
        timezone=zone.key,
        utc_offset_minutes=int(chosen.utcoffset() / timedelta(minutes=1)),
        ambiguous=ambiguous,
        in_gap=in_gap,
        adjustment=adjustment,
    )
