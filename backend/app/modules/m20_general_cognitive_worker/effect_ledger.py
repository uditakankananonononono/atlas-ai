"""Durable effect ledger: reserve-before-invoke for non-idempotent actions.

Contract (deliberately narrow - this is NOT general exactly-once):

* Before a non-idempotent tool handler is invoked, the dispatcher reserves
  the effect in transactional state (``reserve``) and then marks it
  ``invoking`` (``mark_invoking``). Both are committed before the handler
  runs. If either commit fails, the handler is never called.
* The effect identity is ``sha256(tenant | task | node | tool | canonical
  args)``. It is immutable: the same key with different arguments is refused.
* Duplicate or concurrent workers race on a primary key + compare-and-swap
  updates. Exactly one wins the reservation; the others see
  ``EffectInProgress``.
* A succeeded effect is replayed from the recorded receipt, never invoked
  again.
* If a worker dies (or any exception escapes) after ``invoking`` and before
  the final receipt, the effect is ``indeterminate``. It is never retried
  automatically; a human must reconcile it (``reconcile``) unless the tool
  declares provider-side idempotency (``ToolSpec.provider_idempotent``), in
  which case the same effect id is reused as the provider idempotency key.
* A crash after ``reserve`` but before ``mark_invoking`` provably had no
  effect, so the reservation can be re-taken once its lease/owner is dead.

Limits: remote systems are not made exactly-once. The ledger can only record
what this process saw. Owner liveness uses the lease and, on the same host, a
PID check (PID reuse is possible; the lease bounds it for other hosts).
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

RESERVED = "reserved"
INVOKING = "invoking"
SUCCEEDED = "succeeded"
FAILED = "failed"            # provably did not run / provider rejected; retry allowed
INDETERMINATE = "indeterminate"
RECONCILED_APPLIED = "reconciled_applied"
RECONCILED_NOT_APPLIED = "reconciled_not_applied"

# Provider idempotency key for the effect currently being invoked.
CURRENT_EFFECT_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_effect_id", default=None)

metadata = sa.MetaData()
effects = sa.Table(
    "m20_effect_ledger", metadata,
    sa.Column("tenant_id", sa.String(128), primary_key=True),
    sa.Column("effect_id", sa.String(64), primary_key=True),
    sa.Column("task_id", sa.String(128), nullable=False),
    sa.Column("node_id", sa.String(128), nullable=False),
    sa.Column("tool", sa.String(256), nullable=False),
    sa.Column("args_hash", sa.String(64), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("attempt", sa.Integer, nullable=False, default=1),
    sa.Column("owner", sa.String(64), nullable=False),
    sa.Column("owner_host", sa.String(255), nullable=False),
    sa.Column("owner_pid", sa.Integer, nullable=False),
    sa.Column("lease_expires_at", sa.String(40), nullable=False),
    sa.Column("result_summary", sa.Text, nullable=False, default=""),
    sa.Column("error", sa.Text, nullable=False, default=""),
    sa.Column("note", sa.Text, nullable=False, default=""),
    sa.Column("created_at", sa.String(40), nullable=False),
    sa.Column("updated_at", sa.String(40), nullable=False),
)


class EffectError(RuntimeError):
    pass


class EffectInProgress(EffectError):
    """Another live worker holds this effect."""


class EffectIndeterminate(EffectError):
    """The effect may or may not have happened; manual reconciliation required."""

    def __init__(self, effect_id: str, detail: str = "") -> None:
        super().__init__(f"effect {effect_id} is INDETERMINATE (manual reconciliation required){': ' + detail if detail else ''}")
        self.effect_id = effect_id


class EffectIdentityConflict(EffectError):
    """Same effect identity presented with different arguments."""


class ToolNotExecuted(Exception):
    """Raise from a handler only when it can prove the effect did not occur."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def canonical_args(args: dict[str, Any]) -> str:
    return json.dumps(args, sort_keys=True, separators=(",", ":"), default=repr)


def effect_identity(tenant_id: str, task_id: str, node_id: str, tool: str, args: dict[str, Any]) -> tuple[str, str]:
    # The claim id changes between runs. Other underscore-prefixed arguments
    # can be real tool inputs and MUST remain part of the effect identity.
    identity_args = {k: v for k, v in args.items() if k != "_expectation_claim_id"}
    args_hash = hashlib.sha256(canonical_args(identity_args).encode()).hexdigest()
    key = "|".join([tenant_id, task_id, node_id, tool, args_hash])
    return hashlib.sha256(key.encode()).hexdigest(), args_hash


@dataclass(frozen=True)
class Reservation:
    effect_id: str
    attempt: int
    owner: str
    replayed: bool = False
    result_summary: str = ""


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class EffectLedger:
    """Tenant-scoped durable ledger over any SQLAlchemy engine."""

    def __init__(self, engine: sa.engine.Engine, tenant_id: str, *, lease_seconds: float = 120.0) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self.engine = engine
        self.tenant_id = tenant_id
        self.lease_seconds = lease_seconds
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        metadata.create_all(engine)

    # -- helpers -------------------------------------------------------------
    def _where(self, effect_id: str):
        return sa.and_(effects.c.tenant_id == self.tenant_id, effects.c.effect_id == effect_id)

    def get(self, effect_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(effects).where(self._where(effect_id))).mappings().first()
        return dict(row) if row else None

    def list(self, state: str | None = None) -> list[dict[str, Any]]:
        stmt = sa.select(effects).where(effects.c.tenant_id == self.tenant_id)
        if state:
            stmt = stmt.where(effects.c.state == state)
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt.order_by(effects.c.created_at)).mappings()]

    def _cas(self, effect_id: str, *, expect_state: str, expect_owner: str | None, **values) -> bool:
        cond = [self._where(effect_id), effects.c.state == expect_state]
        if expect_owner is not None:
            cond.append(effects.c.owner == expect_owner)
        values["updated_at"] = _iso(_now())
        with self.engine.begin() as conn:
            return conn.execute(sa.update(effects).where(sa.and_(*cond)).values(**values)).rowcount == 1

    def _owner_dead(self, row: dict[str, Any]) -> bool:
        if datetime.fromisoformat(row["lease_expires_at"]) <= _now():
            return True
        return row["owner_host"] == socket.gethostname() and not _pid_alive(row["owner_pid"])

    # -- reserve -------------------------------------------------------------
    def reserve(self, *, task_id: str, node_id: str, tool: str, args: dict[str, Any],
                lease_seconds: float | None = None, provider_idempotent: bool = False) -> Reservation:
        effect_id, args_hash = effect_identity(self.tenant_id, task_id, node_id, tool, args)
        lease = _iso(_now() + timedelta(seconds=lease_seconds or self.lease_seconds))
        now = _iso(_now())
        values = dict(tenant_id=self.tenant_id, effect_id=effect_id, task_id=task_id, node_id=node_id,
                      tool=tool, args_hash=args_hash, state=RESERVED, attempt=1, owner=self.worker_id,
                      owner_host=socket.gethostname(), owner_pid=os.getpid(), lease_expires_at=lease,
                      result_summary="", error="", note="", created_at=now, updated_at=now)
        try:
            with self.engine.begin() as conn:      # one transaction; rollback leaves no row
                conn.execute(sa.insert(effects).values(**values))
            return Reservation(effect_id, 1, self.worker_id)
        except IntegrityError as exc:
            row = self.get(effect_id)
            if row is None:  # not a duplicate key: a real storage failure; handler must not run
                raise
            return self._classify_existing(row, effect_id, args_hash, provider_idempotent, lease)
        raise AssertionError("unreachable")

    def _classify_existing(self, row: dict[str, Any], effect_id: str, args_hash: str,
                           provider_idempotent: bool, lease: str) -> Reservation:
        if row["args_hash"] != args_hash:
            raise EffectIdentityConflict(effect_id)
        state = row["state"]
        if state in (SUCCEEDED, RECONCILED_APPLIED):
            return Reservation(effect_id, row["attempt"], row["owner"], True, row["result_summary"])
        if state == INDETERMINATE:
            if provider_idempotent and self._take(effect_id, INDETERMINATE, row, lease, bump=True):
                return Reservation(effect_id, row["attempt"] + 1, self.worker_id)
            raise EffectIndeterminate(effect_id, row["error"])
        if state in (FAILED, RECONCILED_NOT_APPLIED):
            if self._take(effect_id, state, row, lease, bump=True):
                return Reservation(effect_id, row["attempt"] + 1, self.worker_id)
            raise EffectInProgress(effect_id)
        if state == RESERVED:
            if self._owner_dead(row) and self._take(effect_id, RESERVED, row, lease, bump=False):
                return Reservation(effect_id, row["attempt"], self.worker_id)
            raise EffectInProgress(effect_id)
        if state == INVOKING:
            if self._owner_dead(row):
                self._cas(effect_id, expect_state=INVOKING, expect_owner=row["owner"], state=INDETERMINATE,
                          error="worker died after invocation began and before the final receipt")
                row = self.get(effect_id) or row
                if row["state"] == INDETERMINATE:
                    if provider_idempotent and self._take(effect_id, INDETERMINATE, row, lease, bump=True):
                        return Reservation(effect_id, row["attempt"] + 1, self.worker_id)
                    raise EffectIndeterminate(effect_id, row["error"])
            raise EffectInProgress(effect_id)
        raise EffectError(f"unknown ledger state {state!r}")

    def _take(self, effect_id: str, expect_state: str, row: dict[str, Any], lease: str, *, bump: bool) -> bool:
        return self._cas(effect_id, expect_state=expect_state, expect_owner=row["owner"],
                         state=RESERVED, owner=self.worker_id, owner_host=socket.gethostname(),
                         owner_pid=os.getpid(), lease_expires_at=lease,
                         attempt=row["attempt"] + (1 if bump else 0), error="")

    # -- transitions ---------------------------------------------------------
    def mark_invoking(self, res: Reservation) -> None:
        if not self._cas(res.effect_id, expect_state=RESERVED, expect_owner=res.owner, state=INVOKING):
            raise EffectInProgress(res.effect_id)

    def complete(self, res: Reservation, result_summary: str) -> None:
        if not self._cas(res.effect_id, expect_state=INVOKING, expect_owner=res.owner,
                         state=SUCCEEDED, result_summary=result_summary[:2000]):
            raise EffectIndeterminate(res.effect_id, "lost ownership before final receipt")

    def fail_safe(self, res: Reservation, error: str) -> None:
        self._cas(res.effect_id, expect_state=INVOKING, expect_owner=res.owner, state=FAILED, error=error[:2000])

    def mark_indeterminate(self, res: Reservation, error: str) -> None:
        self._cas(res.effect_id, expect_state=INVOKING, expect_owner=res.owner, state=INDETERMINATE, error=error[:2000])

    def reconcile(self, effect_id: str, *, outcome: str, actor: str, note: str,
                  result_summary: str = "") -> dict[str, Any]:
        """Human decision on an indeterminate effect: 'applied' or 'not_applied'."""
        if outcome not in ("applied", "not_applied"):
            raise ValueError("outcome must be 'applied' or 'not_applied'")
        if not actor or not note:
            raise ValueError("actor and note are required")
        # A killed worker may have left INVOKING without any restart dispatch
        # to classify it. Use the same liveness rule and owner-scoped CAS as
        # reserve; never convert a live invocation or a safe reservation.
        row = self.get(effect_id)
        if row is not None and row["state"] == INVOKING:
            if not self._owner_dead(row):
                raise EffectInProgress(effect_id)
            self._cas(effect_id, expect_state=INVOKING, expect_owner=row["owner"],
                      state=INDETERMINATE,
                      error="worker died after invocation began and before the final receipt")
        state = RECONCILED_APPLIED if outcome == "applied" else RECONCILED_NOT_APPLIED
        ok = self._cas(effect_id, expect_state=INDETERMINATE, expect_owner=None, state=state,
                       note=f"{actor}: {note}", result_summary=result_summary or f"reconciled by {actor}: {outcome}")
        if not ok:
            raise EffectError("effect is not indeterminate (or does not belong to this tenant)")
        return self.get(effect_id)  # type: ignore[return-value]
