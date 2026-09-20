"""Orchestration, failure isolation, and stateful monitoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Callable, Iterable

from .adapters import OpportunityAdapter
from .models import Opportunity, RankedOpportunity, SearchQuery
from .normalization import deduplicate
from .ranking import rank_all


@dataclass(frozen=True, slots=True)
class AdapterFailure:
    adapter: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    items: tuple[RankedOpportunity, ...]
    failures: tuple[AdapterFailure, ...]
    searched_at: datetime


class OpportunityDiscoveryService:
    def __init__(self, adapters: Iterable[OpportunityAdapter], *, dedupe_threshold: float = 0.84) -> None:
        self.adapters = tuple(adapters)
        if not self.adapters:
            raise ValueError("at least one adapter is required")
        self.dedupe_threshold = dedupe_threshold

    def search(self, query: SearchQuery) -> SearchResult:
        opportunities: list[Opportunity] = []
        failures: list[AdapterFailure] = []
        for adapter in self.adapters:
            try:
                opportunities.extend(adapter.search(query))
            except Exception as exc:  # isolate a legal/public source outage
                failures.append(AdapterFailure(adapter.name, type(exc).__name__, str(exc)[:500]))
        unique = deduplicate(opportunities, self.dedupe_threshold)
        return SearchResult(tuple(rank_all(unique, query)), tuple(failures), datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class OpportunityChange:
    kind: str
    opportunity_id: str
    previous: Opportunity | None
    current: Opportunity | None


class OpportunityMonitor:
    """Thread-safe diff engine; persistence can be supplied by serializing snapshot()."""
    def __init__(self) -> None:
        self._state: dict[str, Opportunity] = {}
        self._lock = Lock()

    def update(self, opportunities: Iterable[Opportunity]) -> tuple[OpportunityChange, ...]:
        incoming = {item.id: item for item in opportunities}
        changes: list[OpportunityChange] = []
        with self._lock:
            for key, item in incoming.items():
                old = self._state.get(key)
                if old is None:
                    changes.append(OpportunityChange("new", key, None, item))
                elif _fingerprint(old) != _fingerprint(item):
                    changes.append(OpportunityChange("updated", key, old, item))
            for key, old in self._state.items():
                if key not in incoming:
                    changes.append(OpportunityChange("removed", key, old, None))
            self._state = incoming
        return tuple(sorted(changes, key=lambda x: (x.kind, x.opportunity_id)))

    def snapshot(self) -> tuple[Opportunity, ...]:
        with self._lock:
            return tuple(self._state[key] for key in sorted(self._state))


def _fingerprint(item: Opportunity) -> tuple[object, ...]:
    return (item.title, item.description, item.source_status, item.open_date, item.close_date, item.amount_min, item.amount_max, item.currency, item.countries, item.eligibility, item.tags, item.canonical_url)


@dataclass(frozen=True, slots=True)
class MonitorRun:
    result: SearchResult
    changes: tuple[OpportunityChange, ...]


def run_persistent_monitor(service: OpportunityDiscoveryService, store: object, monitor_key: str, query: SearchQuery) -> MonitorRun:
    """Search sources and atomically compare them with a persisted monitor snapshot.

    `store` is structurally typed to avoid coupling deployments to SQLite; it must
    expose replace_and_diff(monitor_key, iterable).
    """
    result = service.search(query)
    items = [ranked.opportunity for ranked in result.items]
    changes = store.replace_and_diff(monitor_key, items)  # type: ignore[attr-defined]
    return MonitorRun(result, changes)
