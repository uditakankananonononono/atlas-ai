"""Durable effect ledger: reserve-before-invoke for non-idempotent actions.

Contract (deliberately narrow - this is NOT general exactly-once):

* Before a non-idempotent tool handler is invoked, the dispatcher reserves
  the effect in transactional state (``reserve``) and then marks it
  ``invoking`` (``mark_invoking``). Both are committed before the handler
  runs. If either commit fails, the handler is never called.
* The effect identity is ``sha256(json([tenant, task, node, tool,
  args_hash]))`` - a JSON-array encoding, so components containing "|" (or
  any other separator) cannot collide with a different component split. It
  is immutable: the same key with different arguments is refused. Rows
  written before this encoding fix keep their old "|"-joined identity; the
  ledger reads them back through the legacy key so a recorded effect is
  never silently re-invoked after the upgrade (see docs/EFFECT_LEDGER.md).
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
what this process saw. Owner liveness: on the same host a verifiably live
owner process (PID plus boot id, PID namespace and /proc start-time identity,
so PID reuse, including after a reboot, does not resurrect a dead owner) is NEVER treated as dead - even past its lease. A
handler that blocks the event loop outlives its lease while running, and
retaking it would double the external effect. Cross-host owners cannot be
PID-checked; only the lease bounds them. Rows written before the liveness
fix carry no start-time token and fall back to plain PID liveness.

Handlers must not block the event loop with synchronous I/O or sleeps:
asyncio.wait_for cannot cancel a loop-blocking handler, so it runs past its
timeout and lease. The ledger refuses to retake or reconcile such a live
invocation, but the dispatch call itself still returns only after the
handler yields. Use async I/O or an executor for blocking work.
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
from sqlalchemy.exc import DBAPIError, IntegrityError

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
    # Process start-time token (/proc/<pid>/stat field 22) identifying the
    # owning process instance; "" where /proc is unavailable or on rows
    # written before this column existed. Guards against PID reuse.
    sa.Column("owner_pid_start", sa.String(64), nullable=False, default=""),
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
    # JSON-array encoding is unambiguous: components containing "|" (or any
    # other separator) cannot collide with a different split of the same
    # joined string, which the previous "|".join(...) encoding allowed
    # ((task='T|N', node='X') collided with (task='T', node='N|X')).
    key = json.dumps([tenant_id, task_id, node_id, tool, args_hash], separators=(",", ":"))
    return hashlib.sha256(key.encode()).hexdigest(), args_hash


def _legacy_effect_id(tenant_id: str, task_id: str, node_id: str, tool: str, args_hash: str) -> str:
    # Pre-fix identity encoding ("|"-joined). Ambiguous when components
    # contain "|"; kept read-only so rows written before the encoding fix
    # remain authoritative for their effect.
    return hashlib.sha256("|".join([tenant_id, task_id, node_id, tool, args_hash]).encode()).hexdigest()


def legacy_effect_identity(tenant_id: str, task_id: str, node_id: str, tool: str, args: dict[str, Any]) -> str:
    """The pre-fix effect id for these components, for reconciling rows that
    were reserved before the identity encoding changed."""
    _, args_hash = effect_identity(tenant_id, task_id, node_id, tool, args)
    return _legacy_effect_id(tenant_id, task_id, node_id, tool, args_hash)


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


def _environment_token() -> str:
    """Identify this boot and PID namespace: "<boot6>.<pidns>".

    PIDs and start times are only comparable within one boot and one PID
    namespace. start-time ticks restart at boot, so after a reboot a recycled
    PID can carry a start time equal to a dead owner's. "" where unavailable.
    """
    try:
        with open("/proc/sys/kernel/random/boot_id") as fh:
            boot = hashlib.sha256(fh.read().strip().encode()).hexdigest()[:6]
    except OSError:
        return ""
    try:
        ns = os.readlink("/proc/self/ns/pid").strip("pid:[]") or "0"
    except OSError:
        ns = "0"
    return f"{boot}.{ns}"


def _proc_state_and_start(pid: int) -> tuple[str, str]:
    """(state, start-time ticks) for a Linux process via /proc, else ("", "").

    ("", "") means the check is unavailable on this platform; callers then
    fall back to PID liveness only.
    """
    try:
        with open(f"/proc/{pid}/stat", "rb") as fh:
            raw = fh.read().decode()
        rest = raw.rsplit(")", 1)[1].split()  # comm may contain spaces/parens
        return rest[0], rest[19]              # state (field 3), starttime (field 22)
    except (OSError, IndexError):
        return "", ""


def current_owner_token(pid: int | None = None) -> str:
    """Start-time token stored with a reservation: "<boot6>.<pidns>:<start>"
    (just "<start>" where the environment id is unavailable, "" without /proc)."""
    start = _proc_state_and_start(pid if pid is not None else os.getpid())[1]
    if not start:
        return ""
    env = _environment_token()
    return f"{env}:{start}" if env else start


def _split_token(token: str) -> tuple[str, str]:
    env, sep, start = token.rpartition(":")
    return (env, start) if sep else ("", token)  # legacy rows: bare start ticks


def _has_live_threads(pid: int) -> bool:
    """True if a zombie thread-group leader still has running threads.

    After the main thread calls pthread_exit, /proc/PID/stat shows state Z
    while the other threads keep running; the process is alive.
    """
    try:
        tids = os.listdir(f"/proc/{pid}/task")
    except OSError:
        return False
    for tid in tids:
        if tid == str(pid):
            continue
        try:
            with open(f"/proc/{pid}/task/{tid}/stat", "rb") as fh:
                state = fh.read().decode().rsplit(")", 1)[1].split()[0]
        except (OSError, IndexError):
            continue
        if state not in ("Z", "X"):
            return True
    return False


def _owner_process_alive(pid: int, recorded_token: str) -> bool | None:
    """Same-host owner liveness with PID-reuse, reboot and zombie handling.

    True = alive, False = dead, None = cannot be verified from this PID
    namespace (the caller must fall back to the lease). Assumes owner_host
    (hostname) uniquely identifies the machine; containers sharing a hostname
    but not a PID namespace are detected through the namespace id in the token
    for rows written after this fix.
    """
    if pid <= 0:
        return False
    rec_env, rec_start = _split_token(recorded_token or "")
    if rec_env:
        cur_env = _environment_token()
        if cur_env and cur_env != rec_env:
            rec_boot, cur_boot = rec_env.split(".")[0], cur_env.split(".")[0]
            # Different boot: no process survives a reboot. Same boot but a
            # different PID namespace: PIDs are not comparable - unverifiable.
            return False if rec_boot != cur_boot else None
    if not _pid_alive(pid):
        return False
    state, start = _proc_state_and_start(pid)
    if rec_start and start and start != rec_start:
        return False                          # PID reused by a newer process
    if state == "Z":
        return _has_live_threads(pid)         # reaped-pending, unless threads still run
    return True


def worker_identity(hostname: str, pid: int) -> str:
    """Compact owner fence; hostname itself is kept separately for liveness."""
    host_id = hashlib.sha256(hostname.encode()).hexdigest()[:32]
    return f"{host_id}:{pid}:{uuid.uuid4().hex[:8]}"


class EffectLedger:
    """Tenant-scoped durable ledger over any SQLAlchemy engine."""

    def __init__(self, engine: sa.engine.Engine, tenant_id: str, *, lease_seconds: float = 120.0) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self.engine = engine
        self.tenant_id = tenant_id
        self.lease_seconds = lease_seconds
        # Keep the owner fence within the original VARCHAR(64), even for a
        # long hostname. owner_host retains the full name for liveness checks.
        self.worker_id = worker_identity(socket.gethostname(), os.getpid())
        self._create_schema()
        self._ensure_owner_pid_start_column()

    def _create_schema(self) -> None:
        """checkfirst is not atomic: another first-boot worker can win DDL.

        Retry only duplicate-table/type races, in a fresh transaction. Other
        database failures still abort initialization, before any invocation.
        """
        for attempt in range(3):
            try:
                metadata.create_all(self.engine, checkfirst=True)
                return
            except DBAPIError as exc:
                code = getattr(exc.orig, "sqlstate", None)
                constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", "")
                duplicate = (code == "42P07" or
                             (code == "23505" and constraint == "pg_type_typname_nsp_index") or
                             (self.engine.dialect.name == "sqlite" and
                              "table m20_effect_ledger already exists" in str(exc.orig)))
                if not duplicate or attempt == 2:
                    raise

    def _ensure_owner_pid_start_column(self) -> None:
        """Add owner_pid_start to tables created before the liveness fix.

        Rows that predate the column get the default "" and are liveness-
        checked by PID only (no PID-reuse guard), which is the same
        conservative direction as before: a live PID means a live owner.
        """
        if "owner_pid_start" in {c["name"] for c in sa.inspect(self.engine).get_columns(effects.name)}:
            return
        try:
            with self.engine.begin() as conn:
                conn.execute(sa.text(
                    f"ALTER TABLE {effects.name} ADD COLUMN owner_pid_start VARCHAR(40) NOT NULL DEFAULT ''"))
        except Exception:
            # A concurrent ledger may have added it first; verify once more.
            cols = {c["name"] for c in sa.inspect(self.engine).get_columns(effects.name)}
            if "owner_pid_start" not in cols:
                raise

    # -- helpers -------------------------------------------------------------
    def _where(self, effect_id: str):
        return sa.and_(effects.c.tenant_id == self.tenant_id, effects.c.effect_id == effect_id)

    def get(self, effect_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(effects).where(self._where(effect_id))).mappings().first()
        return dict(row) if row else None

    def get_legacy(self, task_id: str, node_id: str, tool: str, args_hash: str) -> dict[str, Any] | None:
        """The pre-fix "|"-joined row for this effect, only if it really is this effect.

        The legacy id is ambiguous: (task='T|N', node='X') and (task='T',
        node='N|X') hash alike. A row found under the legacy id is accepted
        only when its stored task/node/tool/args_hash equal the request
        (tenant is already scoped); otherwise it belongs to a different
        effect and is ignored.
        """
        row = self.get(_legacy_effect_id(self.tenant_id, task_id, node_id, tool, args_hash))
        if row is None:
            return None
        if (row["task_id"], row["node_id"], row["tool"], row["args_hash"]) != (task_id, node_id, tool, args_hash):
            return None
        return row

    def resolve_effect_id(self, task_id: str, node_id: str, tool: str, args: dict[str, Any]) -> str:
        """Effect id to act on: the new-encoding id, or a matching legacy row's id."""
        effect_id, args_hash = effect_identity(self.tenant_id, task_id, node_id, tool, args)
        if self.get(effect_id) is None:
            legacy = self.get_legacy(task_id, node_id, tool, args_hash)
            if legacy is not None:
                return legacy["effect_id"]
        return effect_id

    def list(self, state: str | None = None) -> list[dict[str, Any]]:
        stmt = sa.select(effects).where(effects.c.tenant_id == self.tenant_id)
        if state:
            stmt = stmt.where(effects.c.state == state)
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt.order_by(effects.c.created_at)).mappings()]

    def _cas(self, effect_id: str, *, expect_state: str, expect_owner: str | None, expect_attempt: int, **values) -> bool:
        cond = [self._where(effect_id), effects.c.state == expect_state,
                effects.c.attempt == expect_attempt]
        if expect_owner is not None:
            cond.append(effects.c.owner == expect_owner)
        values["updated_at"] = _iso(_now())
        with self.engine.begin() as conn:
            return conn.execute(sa.update(effects).where(sa.and_(*cond)).values(**values)).rowcount == 1

    def _owner_dead(self, row: dict[str, Any]) -> bool:
        # A verifiably live owner on this host is never dead - even past its
        # lease. A loop-blocking handler outlives its lease while running;
        # retaking it would double the external effect. Cross-host owners
        # cannot be PID-checked, so only the lease bounds them.
        if row["owner_host"] == socket.gethostname():
            alive = _owner_process_alive(row["owner_pid"], row.get("owner_pid_start") or "")
            if alive is not None:
                return not alive
            # Unverifiable (different PID namespace, same hostname): lease only.
        return datetime.fromisoformat(row["lease_expires_at"]) <= _now()

    # -- reserve -------------------------------------------------------------
    def reserve(self, *, task_id: str, node_id: str, tool: str, args: dict[str, Any],
                lease_seconds: float | None = None, provider_idempotent: bool = False) -> Reservation:
        effect_id, args_hash = effect_identity(self.tenant_id, task_id, node_id, tool, args)
        lease = _iso(_now() + timedelta(seconds=lease_seconds or self.lease_seconds))
        now = _iso(_now())
        # Rows reserved before the identity-encoding fix keep their old
        # "|"-joined id; they stay authoritative for their effect, so the
        # same effect is never silently re-invoked after the upgrade.
        legacy_row = self.get_legacy(task_id, node_id, tool, args_hash)
        if legacy_row is not None:
            return self._classify_existing(legacy_row, legacy_row["effect_id"],
                                           args_hash, provider_idempotent, lease)
        values = dict(tenant_id=self.tenant_id, effect_id=effect_id, task_id=task_id, node_id=node_id,
                      tool=tool, args_hash=args_hash, state=RESERVED, attempt=1, owner=self.worker_id,
                      owner_host=socket.gethostname(), owner_pid=os.getpid(),
                      owner_pid_start=current_owner_token(), lease_expires_at=lease,
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
            if self._owner_dead(row) and self._take(effect_id, RESERVED, row, lease, bump=True):
                return Reservation(effect_id, row["attempt"] + 1, self.worker_id)
            raise EffectInProgress(effect_id)
        if state == INVOKING:
            if self._owner_dead(row):
                self._cas(effect_id, expect_state=INVOKING, expect_owner=row["owner"], expect_attempt=row["attempt"], state=INDETERMINATE,
                          error="worker died after invocation began and before the final receipt")
                row = self.get(effect_id) or row
                if row["state"] == INDETERMINATE:
                    if provider_idempotent and self._take(effect_id, INDETERMINATE, row, lease, bump=True):
                        return Reservation(effect_id, row["attempt"] + 1, self.worker_id)
                    raise EffectIndeterminate(effect_id, row["error"])
            raise EffectInProgress(effect_id)
        raise EffectError(f"unknown ledger state {state!r}")

    def _take(self, effect_id: str, expect_state: str, row: dict[str, Any], lease: str, *, bump: bool) -> bool:
        return self._cas(effect_id, expect_state=expect_state, expect_owner=row["owner"], expect_attempt=row["attempt"],
                         state=RESERVED, owner=self.worker_id, owner_host=socket.gethostname(),
                         owner_pid=os.getpid(), owner_pid_start=current_owner_token(),
                         lease_expires_at=lease,
                         attempt=row["attempt"] + (1 if bump else 0), error="")

    # -- transitions ---------------------------------------------------------
    def mark_invoking(self, res: Reservation) -> None:
        if not self._cas(res.effect_id, expect_state=RESERVED, expect_owner=res.owner, expect_attempt=res.attempt, state=INVOKING):
            raise EffectInProgress(res.effect_id)

    def complete(self, res: Reservation, result_summary: str) -> None:
        if not self._cas(res.effect_id, expect_state=INVOKING, expect_owner=res.owner, expect_attempt=res.attempt,
                         state=SUCCEEDED, result_summary=result_summary[:2000]):
            raise EffectIndeterminate(res.effect_id, "lost ownership before final receipt")

    def fail_safe(self, res: Reservation, error: str) -> None:
        self._cas(res.effect_id, expect_state=INVOKING, expect_owner=res.owner, expect_attempt=res.attempt, state=FAILED, error=error[:2000])

    def release(self, res: Reservation, error: str) -> bool:
        """Give up a reservation whose handler was provably never called.

        Used by the dispatcher when mark_invoking fails. RESERVED -> FAILED, or
        INVOKING -> FAILED when the mark_invoking commit landed but its
        acknowledgement was lost. Both are safe only because the handler never
        ran. Owner/attempt-scoped CAS: a newer reservation is untouched, even
        when the same worker retook it.
        FAILED rows are retakeable, so the effect is not stuck EffectInProgress.
        """
        err = f"not executed: {error}"[:2000]
        for st in (RESERVED, INVOKING):
            if self._cas(res.effect_id, expect_state=st, expect_owner=res.owner, expect_attempt=res.attempt, state=FAILED, error=err):
                return True
        return False

    def mark_indeterminate(self, res: Reservation, error: str) -> None:
        self._cas(res.effect_id, expect_state=INVOKING, expect_owner=res.owner, expect_attempt=res.attempt, state=INDETERMINATE, error=error[:2000])

    def reconcile(self, effect_id: str, *, outcome: str, actor: str, note: str,
                  result_summary: str = "") -> dict[str, Any]:
        """Human decision on an indeterminate effect: 'applied' or 'not_applied'."""
        if outcome not in ("applied", "not_applied"):
            raise ValueError("outcome must be 'applied' or 'not_applied'")
        if not actor or not note:
            raise ValueError("actor and note are required")
        # A killed worker may have left INVOKING without any restart dispatch
        # to classify it. Use the same liveness rule and owner/attempt-scoped CAS as
        # reserve; never convert a live invocation or a safe reservation.
        row = self.get(effect_id)
        if row is not None and row["state"] == INVOKING:
            if not self._owner_dead(row):
                raise EffectInProgress(effect_id)
            self._cas(effect_id, expect_state=INVOKING, expect_owner=row["owner"], expect_attempt=row["attempt"],
                      state=INDETERMINATE,
                      error="worker died after invocation began and before the final receipt")
        # Reload after a dead-owner transition; fence the human decision to
        # this observed indeterminate attempt, not a later retry's row.
        row = self.get(effect_id)
        if row is None or row["state"] != INDETERMINATE:
            raise EffectError("effect is not indeterminate (or does not belong to this tenant)")
        state = RECONCILED_APPLIED if outcome == "applied" else RECONCILED_NOT_APPLIED
        ok = self._cas(effect_id, expect_state=INDETERMINATE, expect_owner=row["owner"], expect_attempt=row["attempt"], state=state,
                       note=f"{actor}: {note}", result_summary=result_summary or f"reconciled by {actor}: {outcome}")
        if not ok:
            raise EffectError("effect is not indeterminate (or does not belong to this tenant)")
        return self.get(effect_id)  # type: ignore[return-value]
