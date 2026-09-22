"""Tenant-scoped, evidence-based acceptance for external adapters.

Configuration is inventory, never proof.  An adapter becomes live-accepted only
when a real probe succeeds.  Write probes are additionally constrained to an
adapter-declared sandbox resource and an approval for the exact action.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Mapping

Probe = Callable[[str], Any | Awaitable[Any]]
WriteProbe = Callable[[str, str, Mapping[str, Any]], Any | Awaitable[Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AdapterSpec:
    adapter_id: str
    label: str
    required_env: tuple[str, ...]
    scopes: tuple[str, ...]
    reconnect_action: str
    read_probe: Probe | None = None
    write_probe: WriteProbe | None = None
    sandbox_resources: tuple[str, ...] = ()

    def configured(self, env: Mapping[str, str] = os.environ) -> bool:
        return all(bool(env.get(name, "").strip()) for name in self.required_env)


@dataclass(frozen=True)
class ExactWriteApproval:
    approved: bool
    adapter_id: str
    action: str
    resource: str


class AcceptanceError(RuntimeError):
    pass


class UnknownAdapter(AcceptanceError):
    pass


class UnsafeWriteProbe(AcceptanceError):
    pass


class AcceptanceStore:
    """SQLite-backed probe evidence, isolated by tenant and adapter."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._db:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS integration_acceptance (
                tenant_id TEXT NOT NULL, adapter_id TEXT NOT NULL,
                last_read_at TEXT, last_read_ok INTEGER, last_read_failure TEXT,
                last_write_at TEXT, last_write_ok INTEGER, last_write_failure TEXT,
                PRIMARY KEY (tenant_id, adapter_id))"""
            )

    def record(self, tenant_id: str, adapter_id: str, kind: str, ok: bool, failure: str | None) -> None:
        if kind not in {"read", "write"}:
            raise ValueError("probe kind must be read or write")
        if not tenant_id.strip() or not adapter_id.strip():
            raise ValueError("tenant and adapter are required")
        at, ok_col, failure_col = f"last_{kind}_at", f"last_{kind}_ok", f"last_{kind}_failure"
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO integration_acceptance(tenant_id,adapter_id) VALUES(?,?) "
                "ON CONFLICT(tenant_id,adapter_id) DO NOTHING", (tenant_id, adapter_id),
            )
            self._db.execute(
                f"UPDATE integration_acceptance SET {at}=?, {ok_col}=?, {failure_col}=? "
                "WHERE tenant_id=? AND adapter_id=?",
                (_now(), int(ok), failure, tenant_id, adapter_id),
            )

    def get(self, tenant_id: str, adapter_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM integration_acceptance WHERE tenant_id=? AND adapter_id=?",
                (tenant_id, adapter_id),
            ).fetchone()
        return dict(row) if row else {}


class AcceptanceCatalog:
    def __init__(self, specs: Iterable[AdapterSpec], store: AcceptanceStore | None = None) -> None:
        items = list(specs)
        self.specs = {item.adapter_id: item for item in items}
        if len(self.specs) != len(items):
            raise ValueError("adapter ids must be unique")
        self.store = store or AcceptanceStore()

    def _spec(self, adapter_id: str) -> AdapterSpec:
        try:
            return self.specs[adapter_id]
        except KeyError as exc:
            raise UnknownAdapter(adapter_id) from exc

    def status(self, tenant_id: str, adapter_id: str) -> dict[str, Any]:
        spec = self._spec(adapter_id); evidence = self.store.get(tenant_id, adapter_id)
        read_ok = evidence.get("last_read_ok") == 1
        write_ok = evidence.get("last_write_ok") == 1
        configured = spec.configured()
        failure = evidence.get("last_read_failure") or evidence.get("last_write_failure")
        if not configured:
            failure = "Missing configuration: " + ", ".join(x for x in spec.required_env if not os.getenv(x, "").strip())
        return {
            "adapter_id": spec.adapter_id, "label": spec.label,
            "configured": configured,
            "live_accepted": configured and read_ok,
            "write_accepted": configured and write_ok,
            "last_successful_read": evidence.get("last_read_at") if read_ok else None,
            "last_successful_write": evidence.get("last_write_at") if write_ok else None,
            "scopes": list(spec.scopes), "failure_reason": failure,
            "reconnect_action": spec.reconnect_action,
            "write_probe_available": spec.write_probe is not None,
            "sandbox_resources": list(spec.sandbox_resources),
        }

    def list(self, tenant_id: str) -> list[dict[str, Any]]:
        return [self.status(tenant_id, key) for key in sorted(self.specs)]

    async def probe_read(self, tenant_id: str, adapter_id: str) -> dict[str, Any]:
        spec = self._spec(adapter_id)
        if not spec.configured():
            raise AcceptanceError("adapter is not configured")
        if spec.read_probe is None:
            raise AcceptanceError("adapter has no safe read probe")
        try:
            result = spec.read_probe(tenant_id)
            if inspect.isawaitable(result): await result
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            self.store.record(tenant_id, adapter_id, "read", False, message)
            raise AcceptanceError(message) from exc
        self.store.record(tenant_id, adapter_id, "read", True, None)
        return self.status(tenant_id, adapter_id)

    async def probe_write(self, tenant_id: str, adapter_id: str, action: str, resource: str,
                          approval: ExactWriteApproval, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        spec = self._spec(adapter_id)
        if not spec.configured(): raise AcceptanceError("adapter is not configured")
        if spec.write_probe is None: raise UnsafeWriteProbe("adapter has no safe write probe")
        if resource not in spec.sandbox_resources:
            raise UnsafeWriteProbe("write probes may target only a declared sandbox resource")
        expected = ExactWriteApproval(True, adapter_id, action, resource)
        if approval != expected:
            raise UnsafeWriteProbe("approved exact adapter, action, and sandbox resource are required")
        try:
            result = spec.write_probe(tenant_id, resource, dict(payload or {}))
            if inspect.isawaitable(result): await result
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            self.store.record(tenant_id, adapter_id, "write", False, message)
            raise AcceptanceError(message) from exc
        self.store.record(tenant_id, adapter_id, "write", True, None)
        return self.status(tenant_id, adapter_id)


async def _google_read(_: str) -> None:
    import httpx
    token = os.environ["GOOGLE_OAUTH_ACCESS_TOKEN"]
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()


def _redis_read(_: str) -> None:
    from redis import Redis
    client = Redis.from_url(os.environ["ATLAS_REDIS_URL"])
    try:
        if client.ping() is not True: raise RuntimeError("Redis PING was not acknowledged")
    finally: client.close()


def _redis_write(_: str, resource: str, payload: Mapping[str, Any]) -> None:
    from redis import Redis
    client = Redis.from_url(os.environ["ATLAS_REDIS_URL"])
    try:
        key = f"{resource}:acceptance"
        client.set(key, json.dumps(dict(payload)), ex=60)
        if client.get(key) is None: raise RuntimeError("sandbox value was not readable")
        client.delete(key)
    finally: client.close()


def default_catalog(path: str | Path | None = None) -> AcceptanceCatalog:
    sandbox_stream = os.getenv("ATLAS_REDIS_ACCEPTANCE_SANDBOX", "atlas:sandbox")
    specs = [
        AdapterSpec("google-workspace", "Google Workspace", ("GOOGLE_OAUTH_ACCESS_TOKEN",),
                    ("openid", "email", "docs.readonly", "spreadsheets.readonly"),
                    "/settings/integrations/google-workspace/reconnect", _google_read),
        AdapterSpec("redis", "Redis Streams", ("ATLAS_REDIS_URL",), ("ping", "stream.read", "stream.write"),
                    "/settings/integrations/redis", _redis_read, _redis_write, (sandbox_stream,)),
    ]
    return AcceptanceCatalog(specs, AcceptanceStore(path or os.getenv("ATLAS_ACCEPTANCE_DB", ":memory:")))
