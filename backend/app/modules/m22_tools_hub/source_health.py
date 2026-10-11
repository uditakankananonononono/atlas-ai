"""Freshness and health report across M22 discovery sources.

``health_report`` runs one query against every collector concurrently and
reports, per source: status (ok | empty | error), candidate count (capped at
20), latency, the newest dated item and whether that is stale. It reads only
what the collectors return; sources that expose no date report ``stale: None``
(unknown) rather than being called fresh. One request per source per report.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import aclosing
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from .sources_extra import parse_ts

MAX_COUNT = 20
DATE_KEYS = ("updated_at", "last_activity_at", "pushed_at", "published_at", "published", "lastpub",
             "last_eventful_visit_date", "last_visit_date", "date", "updated", "created_at")


def freshness_of(evidence: Iterable[dict[str, Any]]) -> datetime | None:
    newest = None
    for ev in evidence or []:
        for key in DATE_KEYS:
            parsed = parse_ts(ev.get(key)) if isinstance(ev, dict) else None
            if parsed and (newest is None or parsed > newest):
                newest = parsed
    return newest


async def probe_source(collector: Any, query: str, *, clock: Callable[[], float] = time.monotonic,
                       now: datetime | None = None, max_age_days: int = 365, timeout: float = 20.0) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    result: dict[str, Any] = {"source": collector.name, "kind": getattr(collector, "kind", None),
                              "status": "ok", "count": 0, "latency_ms": 0.0, "newest": None,
                              "stale": None, "error": None}

    async def gather() -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        async with aclosing(collector.collect(query)) as stream:
            async for item in stream:
                items.append(item)
                if len(items) >= MAX_COUNT:
                    break
        return items

    started = clock()
    items: list[dict[str, Any]] = []
    try:
        items = await asyncio.wait_for(gather(), timeout)
    except asyncio.TimeoutError:
        result.update(status="error", error=f"timed out after {timeout}s")
    except Exception as exc:  # noqa: BLE001 - a failing source must not break the report
        result.update(status="error", error=str(exc) or type(exc).__name__)
    result["latency_ms"] = round((clock() - started) * 1000, 1)
    if result["status"] == "error":
        return result
    result["count"] = len(items)
    if not items:
        result["status"] = "empty"
        return result
    newest = None
    for item in items:
        got = freshness_of(item.get("evidence") or [])
        if got and (newest is None or got > newest):
            newest = got
    if newest:
        result["newest"] = newest.isoformat()
        result["stale"] = (now - newest) > timedelta(days=max_age_days)
    return result


async def health_report(collectors: list[Any], query: str, *, now: datetime | None = None,
                        max_age_days: int = 365, timeout: float = 20.0) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    rows = await asyncio.gather(*(probe_source(c, query, now=now, max_age_days=max_age_days, timeout=timeout)
                                  for c in collectors))
    summary = {"ok": 0, "empty": 0, "error": 0}
    for row in rows:
        summary[row["status"]] += 1
    summary["total"] = len(rows)
    return {"generated_at": now.isoformat(), "query": query, "max_age_days": max_age_days,
            "sources": list(rows), "summary": summary}


def all_collectors() -> list[Any]:
    """Every no-key collector Atlas can run today: the defaults plus the delta sources."""
    from .sources import default_source_collectors
    from .sources_extra import extra_source_collectors
    seen: set[str] = set()
    merged = []
    for collector in default_source_collectors() + extra_source_collectors():
        if collector.name not in seen:  # safe if the wiring patch already added the delta sources
            seen.add(collector.name)
            merged.append(collector)
    return merged


def main(argv: list[str] | None = None) -> int:
    import json
    import sys
    args = sys.argv[1:] if argv is None else argv
    query = args[0] if args else "python"
    print(json.dumps(asyncio.run(health_report(all_collectors(), query)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
