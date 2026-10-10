"""OPT-IN, UNWIRED parallel Redis Streams submission + synchronous REST status.

Existing defaults/routes/broadcaster/callbacks remain unchanged. This is NOT a
whole-system exclusively-Streams claim. Peer must mount the returned status
router and operate a consumer/recovery loop. No route or worker is auto-mounted.
No decision, approval permit, external effect or account action is performed.

TrustedStreamBinding is deployment configuration, NEVER message-body authority.
Each stream is tenant-specific with Redis Cluster hash tags. Provision separate
Redis credentials/ACLs: each producer may XADD ONLY its assigned input stream;
consumer may read/group/ack those streams and write their DLQs. Principal names
passed to submit must already come from a trusted authenticated caller, NOT a
request body. This module does not authenticate a Redis writer, create users,
configure ACLs/TLS or establish protection on a shared writable stream. Without
that deployment binding/ACL, do not activate this path.

Consumer validates the finite-JSON envelope and commits request + created event
+ tenant-namespaced content-bound idempotency row in ONE database transaction
BEFORE XACK. No in-process broadcast or policy auto-allow shortcut. At-least-once
Redis delivery is NOT an exactly-once cross-store transaction: after DB commit
and before ACK, replay checks the stored content hash, emits no second request
or event, then ACKs. Database/Redis failures propagate, remain pending and are
not treated as poison. Poison envelopes/conflicting replays retry up to three
PEL deliveries, then a Lua operation writes only fixed reason/Redis message ID
to DLQ before XACK, atomically on Redis (same hash slot). No raw errors/payloads
are copied into DLQ. Missing/deleted PEL records are reported, never success.

Input retention: never automatically trimmed; pending-safe reclamation/backup
and disk alarms are deployment-owned. This prioritizes pending work over bounded
storage. DLQ keeps at most 1000 metadata entries, so old DLQ evidence can expire.
An operator must run recover every 60 seconds or more and follow its next_id;
entries idle at least 60 seconds may be claimed. Concurrent long handlers can
be claimed by another worker; DB replay handles duplicates. Redis >=6.2 required
for XAUTOCLAIM; its deleted-id result is exposed. Input group creation is explicit
setup, not a silent fallback/reset. No real Redis/ACL/restart acceptance claimed.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.context import TenantContext, require_tenant
from app.modules.catalog import BY_ID
from .schemas import ApprovalView
from .service import (ApprovalRequestRow, ApprovalEventRow, ApprovalIdempotencyRow,
                      ApprovalNotFoundError, Service, _view)

MAX_ATTEMPTS = 3
MAX_STREAM_ENTRIES = None
MAX_DLQ_ENTRIES = 1000
MAX_ENVELOPE_BYTES = 65536
RECOVERY_IDLE_MS = 60000
POLL_BLOCK_MS = 1000
MAX_BATCH = 100
RETENTION_POLICY = "Input is never automatically trimmed; DLQ metadata retains at most 1000 entries."

_DEADLETTER = """
local pending = redis.call('XPENDING', KEYS[1], ARGV[1], ARGV[2], ARGV[2], 1)
if #pending == 0 then return 0 end
redis.call('XADD', KEYS[2], 'MAXLEN', '=', ARGV[4], '*',
           'message_id', ARGV[2], 'reason', ARGV[3])
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
return 1
"""


class EnvelopeError(ValueError):
    def __init__(self):
        super().__init__("invalid_envelope")


class ReplayConflict(ValueError):
    def __init__(self):
        super().__init__("replay_conflict")


def _text(value, maximum):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise EnvelopeError()
    return value


def _json_value(value, depth=0):
    if depth > 32:
        raise EnvelopeError()
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise EnvelopeError()
            _json_value(child, depth+1)
    elif type(value) is list:
        for child in value:
            _json_value(child, depth+1)
    elif type(value) not in (str, int, float, bool, type(None)):
        raise EnvelopeError()


def _encode(value):
    try:
        _json_value(value)
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         allow_nan=False, ensure_ascii=False)
        if len(raw.encode("utf-8")) > MAX_ENVELOPE_BYTES:
            raise EnvelopeError()
        return raw
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise EnvelopeError() from None


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EnvelopeError()
        result[key] = value
    return result


@dataclass(frozen=True)
class Submission:
    request_id: str
    module_id: int
    action_type: str
    payload: dict
    ttl_seconds: int | None = None

    def as_envelope(self):
        _text(self.request_id, 120)
        _text(self.action_type, 100)
        if type(self.module_id) is not int or self.module_id not in BY_ID:
            raise EnvelopeError()
        if type(self.payload) is not dict:
            raise EnvelopeError()
        if self.ttl_seconds is not None and (type(self.ttl_seconds) is not int or not 1 <= self.ttl_seconds <= 31536000):
            raise EnvelopeError()
        value = {"version": 1, "request_id": self.request_id, "module_id": self.module_id,
                 "action_type": self.action_type, "payload": self.payload,
                 "ttl_seconds": self.ttl_seconds}
        # Canonical round trip validates and isolates mutable input references.
        return json.loads(_encode(value))

    @classmethod
    def decode(cls, fields):
        try:
            normalized = {_decode(k): _decode(v) for k, v in fields.items()}
            if set(normalized) != {"envelope"}:
                raise EnvelopeError()
            raw = normalized["envelope"]
            if len(raw.encode("utf-8")) > MAX_ENVELOPE_BYTES:
                raise EnvelopeError()
            envelope = json.loads(raw, object_pairs_hook=_unique)
            expected = {"version", "request_id", "module_id", "action_type", "payload", "ttl_seconds"}
            if type(envelope) is not dict or set(envelope) != expected:
                raise EnvelopeError()
            if type(envelope["version"]) is not int or envelope["version"] != 1:
                raise EnvelopeError()
            return cls(**{key: value for key, value in envelope.items() if key != "version"}).as_envelope()
        except (TypeError, ValueError, UnicodeError, RecursionError, AttributeError):
            raise EnvelopeError() from None


def _decode(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if type(value) is not str:
        raise EnvelopeError()
    return value


@dataclass(frozen=True)
class TrustedStreamBinding:
    tenant_id: str
    principal: str

    def __post_init__(self):
        _text(self.tenant_id, 120)
        _text(self.principal, 120)

    @property
    def slot(self):
        return hashlib.sha256(self.tenant_id.encode()).hexdigest()

    @property
    def stream(self):
        return "atlas:m00:{" + self.slot + "}:submissions"

    @property
    def dlq(self):
        return "atlas:m00:{" + self.slot + "}:deadletters"


class AsyncStreams(Protocol):
    """Injected redis.asyncio-compatible client, never created/connected here."""
    async def xadd(self, name, fields, **kwargs): ...
    async def xgroup_create(self, **kwargs): ...
    async def xreadgroup(self, **kwargs): ...
    async def xpending_range(self, **kwargs): ...
    async def xautoclaim(self, **kwargs): ...
    async def xack(self, name, groupname, *ids): ...
    async def eval(self, script, numkeys, *args): ...


class StreamsSubmissions:
    GROUP = "atlas-m00-submissions-v1"

    def __init__(self, redis: AsyncStreams, service: Service, bindings: list[TrustedStreamBinding]):
        if not bindings or len({b.tenant_id for b in bindings}) != len(bindings) or len({b.principal for b in bindings}) != len(bindings):
            raise ValueError("unique trusted bindings required")
        self.redis, self.service = redis, service
        self._tenants = {b.tenant_id: b for b in bindings}
        self._principals = {b.principal: b for b in bindings}

    def binding(self, tenant):
        if tenant not in self._tenants:
            raise ValueError("unbound trusted tenant")
        return self._tenants[tenant]

    async def create_group(self, tenant: str):
        """Explicit deployment setup: start at 0-0, errors (including BUSYGROUP) propagate."""
        binding = self.binding(tenant)
        return await self.redis.xgroup_create(name=binding.stream, groupname=self.GROUP,
                                             id="0-0", mkstream=True)

    async def submit(self, principal: str, submission: Submission):
        binding = self._principals.get(principal)
        if binding is None:
            raise ValueError("unbound trusted principal")
        encoded = _encode(submission.as_envelope())
        # NO MAXLEN: XADD trimming could delete unprocessed/pending work.
        return _decode(await self.redis.xadd(binding.stream, {"envelope": encoded}))

    def _persist(self, tenant: str, envelope: dict):
        canonical = _encode({"tenant_id": tenant, "submission": envelope})
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        key = "m00streams:v1:" + hashlib.sha256(_encode([tenant, envelope["request_id"]]).encode()).hexdigest()

        def existing(db):
            idem = db.get(ApprovalIdempotencyRow, key)
            if idem is None:
                return None
            row = db.get(ApprovalRequestRow, idem.approval_id)
            if idem.request_hash != digest or row is None or row.user_id != tenant:
                raise ReplayConflict()
            # Replay only ACKs if authoritative request + creation evidence exist.
            events = db.scalars(select(ApprovalEventRow).where(
                ApprovalEventRow.approval_id == row.id, ApprovalEventRow.event == "created")).all()
            if len(events) != 1:
                raise RuntimeError("creation evidence unavailable")
            return row.id

        try:
            with self.service._sessions.begin() as db:
                prior = existing(db)
                if prior is not None:
                    return prior
                now = self.service._clock()
                expiry = now + timedelta(seconds=envelope["ttl_seconds"]) if envelope["ttl_seconds"] else None
                row = ApprovalRequestRow(id=str(uuid4()), user_id=tenant,
                    module_id=envelope["module_id"], action_type=envelope["action_type"],
                    payload=envelope["payload"], status="pending", created_at=now, expires_at=expiry)
                db.add(row)
                db.add(ApprovalEventRow(approval_id=row.id, event="created", actor=None, at=now))
                db.add(ApprovalIdempotencyRow(key=key, request_hash=digest, approval_id=row.id, created_at=now))
                db.flush()
                # Verify creation evidence inside the transaction before committing.
                if existing(db) != row.id:
                    raise RuntimeError("creation evidence unavailable")
                approval_id = row.id
            return approval_id
        except IntegrityError:
            # Concurrent replay winner must be visible, otherwise real DB failure.
            with self.service._sessions() as db:
                prior = existing(db)
                if prior is None:
                    raise
                return prior

    async def _handle(self, binding, message_id, fields):
        message_id = _decode(message_id)
        if not re.fullmatch(r"\d+-\d+", message_id):
            raise ValueError("invalid Redis entry id")
        pending = await self.redis.xpending_range(name=binding.stream, groupname=self.GROUP,
                                                 min=message_id, max=message_id, count=1)
        if len(pending) != 1:
            return {"message_id": message_id, "outcome": "pending_unavailable"}
        attempts = pending[0].get("times_delivered", pending[0].get(b"times_delivered"))
        if type(attempts) is not int or attempts < 1:
            raise RuntimeError("pending delivery count unavailable")
        try:
            envelope = Submission.decode(fields)
            approval_id = await asyncio.to_thread(self._persist, binding.tenant_id, envelope)
        except (EnvelopeError, ReplayConflict) as error:
            reason = "invalid_envelope" if isinstance(error, EnvelopeError) else "replay_conflict"
            if attempts < MAX_ATTEMPTS:
                return {"message_id": message_id, "outcome": "retry", "reason": reason}
            result = await self.redis.eval(_DEADLETTER, 2, binding.stream, binding.dlq,
                                          self.GROUP, message_id, reason, MAX_DLQ_ENTRIES)
            return {"message_id": message_id, "outcome": "deadlettered" if result == 1 else "pending_unavailable", "reason": reason}
        acked = await self.redis.xack(binding.stream, self.GROUP, message_id)
        if acked != 1:
            return {"message_id": message_id, "outcome": "committed_ack_unverified", "approval_id": approval_id}
        return {"message_id": message_id, "outcome": "persisted", "approval_id": approval_id}

    async def poll(self, tenant: str, consumer: str, *, count: int = MAX_BATCH):
        binding = self.binding(tenant)
        _text(consumer, 120)
        if type(count) is not int or not 1 <= count <= MAX_BATCH:
            raise ValueError("invalid batch count")
        batches = await self.redis.xreadgroup(groupname=self.GROUP, consumername=consumer,
                         streams={binding.stream: ">"}, count=count, block=POLL_BLOCK_MS)
        results = []
        for name, messages in batches:
            if _decode(name) != binding.stream:
                raise RuntimeError("unexpected stream")
            for mid, fields in messages:
                results.append(await self._handle(binding, mid, fields))
        return results

    async def recover(self, tenant: str, consumer: str, *, start_id: str = "0-0"):
        binding = self.binding(tenant)
        _text(consumer, 120)
        if not re.fullmatch(r"\d+-\d+", start_id):
            raise ValueError("invalid recovery cursor")
        result = await self.redis.xautoclaim(name=binding.stream, groupname=self.GROUP,
                    consumername=consumer, min_idle_time=RECOVERY_IDLE_MS,
                    start_id=start_id, count=MAX_BATCH)
        cursor, messages = result[0], result[1]
        deleted = result[2] if len(result) > 2 else []
        return {"next_id": _decode(cursor), "deleted_ids": [_decode(mid) for mid in deleted],
                "results": [await self._handle(binding, mid, fields) for mid, fields in messages]}


def create_status_router(service: Service) -> APIRouter:
    """Return UNMOUNTED sync GET router; existing require_tenant is mandatory.

    Filter tenant in DB before reading payload or invoking lazy expiration. No
    tenant fallback/input, and foreign ID matches missing ID's generic 404.
    """
    router = APIRouter(prefix="/approval-stream-status", tags=["approval-stream-status"])

    @router.get("/requests/{approval_id}", response_model=ApprovalView)
    def status(approval_id: str, tenant: TenantContext = Depends(require_tenant)):
        with service._sessions() as db:
            owned = db.scalar(select(ApprovalRequestRow.id).where(
                ApprovalRequestRow.id == approval_id, ApprovalRequestRow.user_id == tenant.tenant_id))
        if owned is None:
            raise HTTPException(status_code=404, detail="approval not found")
        try:
            view = service.get(approval_id)
        except ApprovalNotFoundError:
            raise HTTPException(status_code=404, detail="approval not found") from None
        if view["user_id"] != tenant.tenant_id:
            raise HTTPException(status_code=404, detail="approval not found")
        return view

    return router
