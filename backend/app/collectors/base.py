"""Normalized collector contract for official and licensed data pipes."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol
import httpx

@dataclass(frozen=True)
class CollectedItem:
    canonical_url: str
    external_id: str
    payload: dict[str, Any]

@dataclass
class CollectionBatch:
    items: list[CollectedItem] = field(default_factory=list)
    requests: int = 0
    cursor: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

class Collector(Protocol):
    async def collect(self, config: dict[str, Any]) -> CollectionBatch: ...

class HttpCollector:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or httpx.AsyncClient(timeout=60, follow_redirects=True)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    @staticmethod
    def require(config: dict[str, Any], key: str) -> str:
        value = config.get(key)
        if not value:
            raise ValueError(f"collector config requires {key}")
        return str(value)
