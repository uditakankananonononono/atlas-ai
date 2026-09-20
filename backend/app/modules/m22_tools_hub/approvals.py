from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable


class ApprovalError(PermissionError):
    pass


@dataclass(frozen=True)
class ApprovalGrant:
    token: str
    action: str
    subject_digest: str
    approved_by: str
    requested_by: str
    expires_at: datetime


class ApprovalStore:
    """Single-use, action-bound approvals with optional durable consumed-token state."""

    def __init__(self, state_path: Path | None = None, clock: Callable[[], datetime] | None = None):
        self._state_path = state_path
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._grants: dict[str, ApprovalGrant] = {}
        self._consumed: set[str] = set()
        self._load()

    def issue(
        self,
        *,
        action: str,
        subject_digest: str,
        approved_by: str,
        requested_by: str,
        ttl: timedelta = timedelta(minutes=15),
    ) -> ApprovalGrant:
        if approved_by == requested_by:
            raise ApprovalError("approval requires separation of requester and approver")
        if not action or not subject_digest or not approved_by or not requested_by:
            raise ApprovalError("approval fields cannot be empty")
        if ttl <= timedelta(0) or ttl > timedelta(hours=24):
            raise ApprovalError("approval TTL must be in (0, 24h]")
        grant = ApprovalGrant(
            token=secrets.token_urlsafe(32), action=action, subject_digest=subject_digest,
            approved_by=approved_by, requested_by=requested_by, expires_at=self._clock() + ttl,
        )
        with self._lock:
            self._grants[self._token_hash(grant.token)] = grant
            self._persist()
        return grant

    def consume(self, *, token: str, action: str, subject_digest: str, actor: str) -> ApprovalGrant:
        token_hash = self._token_hash(token)
        with self._lock:
            if token_hash in self._consumed:
                raise ApprovalError("approval already consumed")
            grant = self._grants.get(token_hash)
            if grant is None:
                raise ApprovalError("approval not found")
            if self._clock() >= grant.expires_at:
                raise ApprovalError("approval expired")
            if not hmac.compare_digest(grant.action, action):
                raise ApprovalError("approval action mismatch")
            if not hmac.compare_digest(grant.subject_digest, subject_digest):
                raise ApprovalError("approval subject mismatch")
            if grant.requested_by != actor:
                raise ApprovalError("approval actor mismatch")
            self._consumed.add(token_hash)
            del self._grants[token_hash]
            self._persist()
            return grant

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _load(self) -> None:
        if self._state_path is None or not self._state_path.exists():
            return
        value = json.loads(self._state_path.read_text(encoding="utf-8"))
        self._consumed = set(value.get("consumed", []))
        for key, item in value.get("grants", {}).items():
            self._grants[key] = ApprovalGrant(
                token="", action=item["action"], subject_digest=item["subject_digest"],
                approved_by=item["approved_by"], requested_by=item["requested_by"],
                expires_at=datetime.fromisoformat(item["expires_at"]),
            )

    def _persist(self) -> None:
        if self._state_path is None:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "grants": {key: {
                "action": grant.action, "subject_digest": grant.subject_digest,
                "approved_by": grant.approved_by, "requested_by": grant.requested_by,
                "expires_at": grant.expires_at.isoformat(),
            } for key, grant in self._grants.items()},
            "consumed": sorted(self._consumed),
        }
        temp = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temp.replace(self._state_path)
