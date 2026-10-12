"""Approved execution dispatcher.

Consumes a decided Module 0 (Human Approval Center) item and runs it through
the production runtime - but only when every guard passes:

- the approval exists and belongs to the calling tenant;
- its status is approved (pending, denied and expired are refused);
- it has not already been executed (started or succeeded receipts block
  replay; failed receipts may be retried);
- its action_type is on the explicit allowlist mapping to a registered
  production adapter.

Every attempt persists a receipt - started, succeeded or failed - with a
readback payload, so what ran is reconstructable without trusting logs.
"""
from __future__ import annotations

import json
import copy
from types import MappingProxyType
import os
import sqlite3
import threading
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.models import ApprovalStatus

from .integration import AtlasRuntime, Handoff, RuntimeContext
from .production import build_runtime

# The only approval action types this dispatcher may execute, mapped to the
# production adapter (module_id, operation) that runs them. Anything not
# listed here is refused, however approved it is.
ACTION_ALLOWLIST = MappingProxyType({
    "execute_product_plan": (20, "prepare_goal_work"),
    "prepare_goal_work": (0, "prepare_goal_work"),
    "research_request": (4, "research"),
})

TERMINAL_RECEIPT_STATES = ("started", "succeeded")


class ExecutionConflictError(RuntimeError):
    """Raised when an approved item already has a live or finished receipt."""


class ReceiptStore:
    """SQLite-backed, tenant-scoped receipt log for execution attempts."""

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS execution_receipts ("
                "seq INTEGER PRIMARY KEY AUTOINCREMENT, "
                "receipt_id TEXT NOT NULL, tenant_id TEXT NOT NULL, "
                "approval_id TEXT NOT NULL, action_type TEXT NOT NULL, "
                "state TEXT NOT NULL, readback TEXT NOT NULL, created_at TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def record(self, *, receipt_id: str, tenant_id: str, approval_id: str,
               action_type: str, state: str, readback: dict[str, Any]) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO execution_receipts "
                "(receipt_id, tenant_id, approval_id, action_type, state, readback, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (receipt_id, tenant_id, approval_id, action_type, state,
                 json.dumps(readback, sort_keys=True),
                 datetime.now(timezone.utc).isoformat()))

    def latest_for(self, tenant_id: str, approval_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT receipt_id, action_type, state, readback, created_at "
                "FROM execution_receipts WHERE tenant_id=? AND approval_id=? "
                "ORDER BY seq DESC LIMIT 1",
                (tenant_id, approval_id)).fetchone()
        if not row:
            return None
        return {"receipt_id": row[0], "approval_id": approval_id, "tenant_id": tenant_id,
                "action_type": row[1], "state": row[2], "readback": json.loads(row[3]),
                "created_at": row[4]}

    def list_for(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT receipt_id, approval_id, action_type, state, readback, created_at "
                "FROM execution_receipts WHERE tenant_id=? "
                "ORDER BY seq DESC LIMIT ?",
                (tenant_id, limit)).fetchall()
        return [{"receipt_id": r[0], "approval_id": r[1], "tenant_id": tenant_id,
                 "action_type": r[2], "state": r[3], "readback": json.loads(r[4]),
                 "created_at": r[5]} for r in rows]


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return repr(value)


# Person-facing action types: approval_type -> (platform, outbound kind). These
# NEVER run on an approved M00 item alone: they must go through a
# GuardrailEnforcer (platform terms, rate limits, consent, owner effect
# authority bound to the action digest, one ledger). No enforcer configured ->
# refused, fail closed. Only the fixed local ACTION_ALLOWLIST bypasses egress admission;
# unknown types fail closed even when added to a dispatcher target allowlist.
EFFECT_ACTION_KINDS = MappingProxyType({
    "send_email_reply": ("gmail", "send"),
    "publish_social_post": ("social", "post"),
    "submit_application": ("applications", "submit"),
    "send_outreach_message": ("outreach", "send"),
    "create_subscription_checkout": ("stripe", "payment"),
    "create_invoice": ("stripe", "payment"),
})
LOCAL_ACTION_TYPES = frozenset(ACTION_ALLOWLIST)


class M00AuthorityCheck:
    """authority_check hook for the outbound gate, backed by Module 0.

    Accepts (authority_ref, action_digest) only when authority_ref is an M00
    approval that is CURRENTLY approved, belongs to this tenant, has the bound
    action_type, and whose current payload reproduces the exact digest of the
    action the dispatcher bound at execution time. Edits between the initial
    execution read and the hook read reject; this does NOT bind the payload
    the owner reviewed or detect edits before execution. Module, tenant and
    action_type drift, unbound refs and lookup errors reject (fail closed).
    Not authentication of the approver: it trusts the M00 center.
    """

    def __init__(self, center: Any, tenant_id: str) -> None:
        self.center = center
        self.tenant_id = tenant_id
        self._bound: dict[str, dict[str, Any]] = {}

    def bind(self, approval_id: str, fields: dict[str, Any]) -> None:
        self._bound[approval_id] = copy.deepcopy(fields)

    def __call__(self, authority_ref: Any, action_digest: Any) -> bool:
        from app.runtime.guardrails._fields import payload_sha256
        try:
            fields = self._bound.get(authority_ref)
            if fields is None:
                return False
            view = self.center.get(authority_ref)
            if (view.get("user_id") != self.tenant_id
                    or str(getattr(view.get("status"), "value", view.get("status"))) != ApprovalStatus.APPROVED.value
                    or str(view.get("action_type")) != fields["action_type"]
                    or view.get("module_id") != fields["approval_module_id"]):
                return False
            current = copy.deepcopy(fields)
            current["payload"] = copy.deepcopy(view.get("payload") or {})
            return payload_sha256(fields) == action_digest == payload_sha256(current)
        except Exception:
            return False


class ApprovedExecutionDispatcher:
    """Runs approved Module 0 items through allowlisted production adapters."""

    def __init__(self, tenant_id: str, *, actor_id: str = "dispatcher",
                 center: Any = None, runtime: AtlasRuntime | None = None,
                 store: ReceiptStore | None = None,
                 allowlist: dict[str, tuple[int, str]] | None = None,
                 enforcer: Any = None, authority_binder: Any = None, outbound_declarations: dict | None = None,
                 effect_kinds: dict[str, tuple[str, str]] | None = None) -> None:
        if center is None:
            from app.modules.m00_approval_center.service import default_service
            center = default_service()
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.center = center
        self.runtime = runtime or build_runtime()
        self.allowlist = dict(allowlist or ACTION_ALLOWLIST)
        self.enforcer = enforcer
        self.authority_binder = authority_binder
        self.outbound_declarations = outbound_declarations or {}
        if effect_kinds is not None:
            raise ValueError("effect classification is fixed; effect_kinds overrides are forbidden")
        if store is None:
            root = Path(os.getenv("ATLAS_RUNTIME_DATA_DIR", "/tmp/atlas-runtime"))
            store = ReceiptStore(str(root / f"receipts-{tenant_id}.sqlite"))
        self.store = store

    def execute(self, approval_id: str) -> dict[str, Any]:
        view = copy.deepcopy(self.center.get(approval_id))  # snapshot, no nested aliases
        if view.get("user_id") != self.tenant_id:
            from app.modules.m00_approval_center.service import ApprovalNotFoundError
            raise ApprovalNotFoundError(approval_id)
        status = str(view.get("status"))
        if status != ApprovalStatus.APPROVED.value:
            raise PermissionError(f"approval is {status}, not approved")
        prior = self.store.latest_for(self.tenant_id, approval_id)
        if prior and prior["state"] in TERMINAL_RECEIPT_STATES:
            raise ExecutionConflictError(
                f"approval already has a {prior['state']} receipt ({prior['receipt_id']})")
        action_type = str(view.get("action_type"))
        target = self.allowlist.get(action_type)
        receipt_id = str(uuid4())
        if target is None:
            self.store.record(receipt_id=receipt_id, tenant_id=self.tenant_id,
                              approval_id=approval_id, action_type=action_type,
                              state="failed",
                              readback={"error": f"action_type {action_type!r} is not allowlisted"})
            raise ValueError(f"action_type {action_type!r} is not allowlisted for execution")
        module_id, operation = target
        effect_kind = EFFECT_ACTION_KINDS.get(action_type)
        if effect_kind is None and (action_type not in LOCAL_ACTION_TYPES
                                    or target != ACTION_ALLOWLIST[action_type]):
            self.store.record(receipt_id=receipt_id, tenant_id=self.tenant_id,
                              approval_id=approval_id, action_type=action_type,
                              state="failed", readback={"error": "unclassified action (fail closed)"})
            raise PermissionError(f"unclassified action_type {action_type!r}")
        if effect_kind is not None and self.enforcer is None:
            self.store.record(receipt_id=receipt_id, tenant_id=self.tenant_id,
                              approval_id=approval_id, action_type=action_type,
                              state="failed",
                              readback={"error": "person-facing action requires a guardrail enforcer (fail closed)"})
            raise PermissionError(
                f"action_type {action_type!r} is person-facing and requires a guardrail enforcer")
        handoff = Handoff(
            source_module=0, target_module=module_id, operation=operation,
            payload=dict(view.get("payload") or {}),
            evidence=[{"kind": "approval", "id": approval_id}])
        context = RuntimeContext(tenant_id=self.tenant_id, actor_id=self.actor_id,
                                 correlation_id=receipt_id)
        self.store.record(receipt_id=receipt_id, tenant_id=self.tenant_id,
                          approval_id=approval_id, action_type=action_type,
                          state="started", readback={"target": [module_id, operation]})
        import asyncio
        try:
            if effect_kind is None:
                result = asyncio.run(self.runtime.dispatch(context, handoff))
            else:
                platform, kind = effect_kind
                now = datetime.now(timezone.utc)
                action = {"id": receipt_id, "platform": platform, "kind": kind,
                          "at": int(now.timestamp()), "count": 1,
                          "approval_id": approval_id, "action_type": action_type,
                          "approval_module_id": view["module_id"],
                          "context": {"tenant_id": self.tenant_id, "actor_id": self.actor_id,
                                      "correlation_id": receipt_id},
                          "handoff": {"source_module": 0, "target_module": module_id,
                                      "operation": operation, "evidence": handoff.evidence},
                          "payload": copy.deepcopy(view.get("payload") or {})}
                if self.authority_binder is not None:
                    self.authority_binder.bind(
                        approval_id, {k: v for k, v in action.items() if k != "id"})
                # Admission is ledgered write-ahead by the gate; the runtime
                # runs only if the gate admits (authority_ref = M00 approval id,
                # validated by the enforcer's authority_check hook).
                result = self.enforcer.dispatch_outbound(
                    action, self.outbound_declarations,
                    effect=lambda a: asyncio.run(self.runtime.dispatch(
                        RuntimeContext(**a["context"]),
                        Handoff(**a["handoff"], payload=a["payload"]))),
                    now=now.strftime("%Y-%m-%dT%H:%M:%SZ"), authority_ref=approval_id)
        except Exception as exc:
            self.store.record(receipt_id=receipt_id, tenant_id=self.tenant_id,
                              approval_id=approval_id, action_type=action_type,
                              state="failed",
                              readback={"error": f"{type(exc).__name__}: {exc}"})
            raise
        self.store.record(receipt_id=receipt_id, tenant_id=self.tenant_id,
                          approval_id=approval_id, action_type=action_type,
                          state="succeeded",
                          readback={"result": _jsonable(result),
                                    "target": [module_id, operation]})
        receipt = self.store.latest_for(self.tenant_id, approval_id)
        assert receipt is not None
        return receipt

    def readback(self, approval_id: str) -> dict[str, Any]:
        receipt = self.store.latest_for(self.tenant_id, approval_id)
        if receipt is None:
            raise KeyError(f"no execution receipt for approval {approval_id}")
        return receipt

    def list_receipts(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.store.list_for(self.tenant_id, limit)


__all__ = ["ACTION_ALLOWLIST", "EFFECT_ACTION_KINDS", "M00AuthorityCheck", "ApprovedExecutionDispatcher",
           "ExecutionConflictError", "ReceiptStore"]
