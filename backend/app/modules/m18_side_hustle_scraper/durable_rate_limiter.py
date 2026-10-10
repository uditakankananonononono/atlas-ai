"""Opt-in, single-process serialized persistence binding for HostRateLimiter.

Caller provisions a private directory and trusted tenant; bootstrap is explicit.
Persistence failure latch is per-instance only. Restart can load previous valid
state and lose the failed-save request timestamp; no restart-safe reconciliation.
No default collector wiring. No replay/hostile-directory or distributed guarantees.
Each record is persisted before returning to the caller. Use begin_request before
external fetch: a crash after it preserves the request timestamp. A crash before
record_failure can still lose an unseen Retry-After; this is not a remote lease.
"""
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from threading import RLock
import hashlib

from .lane_rate_limit import HostRateLimiter, HostState
from .lane_rate_limit_state import read_snapshot, write_snapshot, StateRejected


class DurableHostRateLimiter(HostRateLimiter):
    def __init__(self, private_root: Path, tenant_id: str, *, bootstrap: bool = False,
                 retention_seconds: int = 86400, **kwargs):
        if not isinstance(tenant_id,str) or not tenant_id.strip():raise StateRejected('trusted tenant required')
        if type(bootstrap) is not bool:raise StateRejected('explicit bootstrap bool required')
        if type(retention_seconds) is not int or not 1<=retention_seconds<=2592000:raise StateRejected('invalid retention')
        self._lock=RLock();self._blocked=False;self.retention_seconds=retention_seconds
        root=Path(private_root).absolute()
        if any(p.is_symlink() for p in [root,*root.parents]) or not root.is_dir():raise StateRejected('trusted existing directory required')
        self._path=root/('m18-pacing-'+hashlib.sha256(tenant_id.encode()).hexdigest()+'.json');self._tenant=tenant_id
        super().__init__(**kwargs)
        with self._lock:
            if bootstrap:
                if self._path.exists() or self._path.is_symlink():raise StateRejected('bootstrap existing state refused')
                self._save()
            else:self._load()

    def _load(self):
        record=read_snapshot(self._path,tenant_id=self._tenant,now=self._clock())
        self._states={key:HostState(**asdict(value)) for key,value in record.states.items()}

    def _save(self):
        now=self._clock()
        try:write_snapshot(self._path,self._tenant,self._states,now=now,expires_at=now+timedelta(seconds=self.retention_seconds))
        except Exception:
            self._blocked=True
            raise

    def _guard(self):
        if self._blocked:raise StateRejected('prior persistence failure; explicit reconciliation required')
        # Recheck disk TTL/corruption before permitting another effect.
        self._load()

    def check(self,host):
        with self._lock:
            self._guard();return super().check(host)

    def begin_request(self,host):
        with self._lock:
            self._guard();wait=super().check(host)
            if wait>0:return wait
            super().record_request(host);self._save();return 0.0

    def record_request(self,host):
        with self._lock:
            self._guard();super().record_request(host);self._save()

    def record_failure(self,host,failure):
        with self._lock:
            self._guard();super().record_failure(host,failure);self._save()

    def honor_retry_after(self,host,retry_after_seconds):
        with self._lock:
            self._guard();super().honor_retry_after(host,retry_after_seconds);self._save()

    def record_success(self,host):
        with self._lock:
            self._guard();until=self._state(host).circuit_open_until
            super().record_success(host)
            if until is not None and until>self._clock():self._state(host).circuit_open_until=until
            self._save()
