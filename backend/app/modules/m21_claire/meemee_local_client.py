"""Reversible adapter: Claire (Atlas m21) -> Meemee device runtime.

Implements the m21 ``LocalClient`` protocol (capabilities/preview/execute/audit) on top of a
Meemee ``DeviceRegistry`` (signed, replay-guarded commands). Nothing here imports Meemee: the
registry and the device transport are injected, so Atlas keeps no hard dependency and nothing is
merged or removed. The device transport is a callable ``(envelope) -> result`` (a real device peer
or Meemee's DeviceSimulator).

Semantics kept at this boundary:
 - tenant: one adapter instance is bound to one owner/tenant id; Meemee rows are owner-scoped.
 - approval: high-risk kinds need an APPROVED m00 approval whose action_type is claire:<kind>,
   whose stored preview equals this action's preview, and which has not been used before.
 - idempotency: (owner, device, idempotency_key) is claimed atomically in a SQLite table (primary
   key, BEGIN IMMEDIATE) and bound to the action digest and the Meemee command_id. Survives restart and
   concurrent processes. Same key + different action is refused. A claim with no recorded command
   (crash between claim and issue) fails closed as "indeterminate": it is never re-issued.
 - approval use: the approval id is consumed in the same transaction as the claim, so a restart or a
   second process cannot replay it.
 - audit: every phase is appended to the m21 hash chain and persisted; the chain is reloaded on start.
State lives in adapter-owned tables (claire_adapter_*) in a SQLite file the caller names (may be the
Meemee registry file). Meemee tables are only touched through DeviceRegistry methods.
"""
from __future__ import annotations
import contextlib, hashlib, json, sqlite3
from datetime import datetime, timezone
from typing import Any, Callable
from app.core.models import ApprovalStatus
from .local_client_protocol import AuditChain, AuditEvent

HIGH_RISK = {"delete_file", "install_package", "uninstall_package", "run_command", "run_workflow",
             "deploy_preview", "connect_tool", "send_message", "spend_money"}


class AdapterError(PermissionError):
    pass


class MeemeeLocalClient:
    def __init__(self, registry: Any, owner_id: str, device_id: str,
                 transport: Callable[[dict[str, Any]], Any], approvals: Any, state_path: str,
                 fault_hook: Callable[[str], None] | None = None):
        if not owner_id or not device_id:
            raise ValueError("owner_id and device_id are required")
        self.registry, self.owner_id, self.device_id = registry, owner_id, device_id
        self.transport, self.approvals, self.state_path = transport, approvals, str(state_path)
        self._fault = fault_hook or (lambda point: None)  # test-only crash injection
        with contextlib.closing(self._db()) as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS claire_adapter_claims(owner_id TEXT NOT NULL,device_id TEXT NOT NULL,idem_key TEXT NOT NULL,
                action_digest TEXT NOT NULL,approval_id TEXT,command_id TEXT,state TEXT NOT NULL,created_at TEXT NOT NULL,
                PRIMARY KEY(owner_id,device_id,idem_key));
              CREATE TABLE IF NOT EXISTS claire_adapter_approval_uses(approval_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,
                device_id TEXT NOT NULL,idem_key TEXT NOT NULL,action_digest TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS claire_adapter_audit(owner_id TEXT NOT NULL,device_id TEXT NOT NULL,sequence INTEGER NOT NULL,
                action_id TEXT,phase TEXT,payload TEXT,previous_hash TEXT,event_hash TEXT,PRIMARY KEY(owner_id,device_id,sequence));
            """)
            rows = db.execute("SELECT * FROM claire_adapter_audit WHERE owner_id=? AND device_id=? ORDER BY sequence", (owner_id, device_id)).fetchall()
        self.chain = AuditChain(device_id)
        self.chain.events = [AuditEvent(r["sequence"], device_id, r["action_id"], r["phase"], json.loads(r["payload"]), r["previous_hash"], r["event_hash"]) for r in rows]

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.state_path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def _audit(self, action_id: str, phase: str, payload: dict[str, Any]) -> None:
        # Sequence comes from the persisted table so concurrent writers cannot fork the chain.
        with contextlib.closing(self._db()) as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT * FROM claire_adapter_audit WHERE owner_id=? AND device_id=? ORDER BY sequence", (self.owner_id, self.device_id)).fetchall()
            self.chain.events = [AuditEvent(r["sequence"], self.device_id, r["action_id"], r["phase"], json.loads(r["payload"]), r["previous_hash"], r["event_hash"]) for r in rows]
            e = self.chain.append(action_id, phase, payload)
            db.execute("INSERT INTO claire_adapter_audit VALUES(?,?,?,?,?,?,?,?)", (self.owner_id, self.device_id, e.sequence, e.action_id, e.phase, json.dumps(e.payload, sort_keys=True, default=str), e.previous_hash, e.event_hash))
            self._fault("mid_audit")
            db.execute("COMMIT")

    def _device(self) -> dict[str, Any]:
        d = self.registry.get(self.owner_id, self.device_id)
        if not d or d.get("revoked_at"):
            raise AdapterError("device is not paired to this owner or is revoked")
        return d

    async def capabilities(self) -> set[str]:
        return set(self._device()["manifest"])

    async def preview(self, action: dict[str, Any]) -> dict[str, Any]:
        args = action.get("arguments", {})
        digest = hashlib.sha256(json.dumps([action.get("kind"), args], sort_keys=True, default=str).encode()).hexdigest()
        return {"device_id": self.device_id, "kind": action.get("kind"), "arguments": args, "digest": digest, "effects": "none until executed"}

    def _check_approval(self, action: dict[str, Any], preview: dict[str, Any], token: str | None) -> None:
        kind = action["kind"]
        if not (kind in HIGH_RISK or action.get("external_effect")):
            return
        if not token:
            raise AdapterError("approval required")
        req = self.approvals.get(token, user_id=self.owner_id)  # owner-scoped lookup
        if (req is None or req.status != ApprovalStatus.APPROVED or req.action_type != f"claire:{kind}"
                or req.payload.get("tenant_id") != self.owner_id
                or req.payload.get("preview") != preview):
            raise AdapterError("approval missing, not approved, not this owner's, or not for this exact action")

    def _report(self, claim: sqlite3.Row) -> dict[str, Any]:
        if not claim["command_id"]:
            return {"replayed": True, "command_id": None, "status": "indeterminate", "result": None,
                    "note": "claimed but no command recorded (in flight or crashed); not re-issued"}
        cmd = self.registry.command(claim["command_id"])
        return {"replayed": True, "command_id": claim["command_id"], "status": cmd["status"] if cmd else "missing", "result": cmd["result"] if cmd else None}

    async def execute(self, action: dict[str, Any], approval_token: str | None = None) -> dict[str, Any]:
        kind = action.get("kind", "")
        key = str(action.get("idempotency_key") or "")
        if not key:
            raise ValueError("idempotency_key is required")
        if kind not in await self.capabilities():
            raise AdapterError("capability not declared by device")
        preview = await self.preview(action)
        digest = preview["digest"]
        with contextlib.closing(self._db()) as db:
            db.execute("BEGIN IMMEDIATE")
            claim = db.execute("SELECT * FROM claire_adapter_claims WHERE owner_id=? AND device_id=? AND idem_key=?", (self.owner_id, self.device_id, key)).fetchone()
            if claim:
                db.execute("COMMIT")
                if claim["action_digest"] != digest:
                    raise AdapterError("idempotency key already used for a different action")
                if claim["approval_id"] and approval_token != claim["approval_id"]:
                    raise AdapterError("reading this result requires the approval it was authorized with")
                return self._report(claim)
            try:
                self._check_approval(action, preview, approval_token)
                if approval_token:
                    db.execute("INSERT INTO claire_adapter_approval_uses VALUES(?,?,?,?,?)", (approval_token, self.owner_id, self.device_id, key, digest))
            except sqlite3.IntegrityError:
                db.execute("ROLLBACK")
                raise AdapterError("approval already used")
            except Exception:
                db.execute("ROLLBACK")
                raise
            db.execute("INSERT INTO claire_adapter_claims VALUES(?,?,?,?,?,NULL,'claimed',?)", (self.owner_id, self.device_id, key, digest, approval_token, datetime.now(timezone.utc).isoformat()))
            db.execute("COMMIT")
        self._fault("after_claim")
        env = self.registry.issue(self.owner_id, self.device_id, kind, action.get("arguments", {}))
        self._fault("after_issue")
        with contextlib.closing(self._db()) as db:
            db.execute("UPDATE claire_adapter_claims SET command_id=?,state='issued' WHERE owner_id=? AND device_id=? AND idem_key=?", (env["command_id"], self.owner_id, self.device_id, key))
        self._fault("after_update")
        aid = action.get("id") or env["command_id"]
        self._audit(aid, "issued", {"command_id": env["command_id"], "kind": kind, "preview_digest": digest, "approval": approval_token})
        try:
            out = self.transport(env)
            self._fault("after_transport")
            result = getattr(out, "result", out)
            self.registry.complete(env["command_id"], result=result)
            self._audit(aid, "completed", {"command_id": env["command_id"]})
            return {"replayed": False, "command_id": env["command_id"], "status": "completed", "result": result}
        except Exception as e:
            self.registry.complete(env["command_id"], error=str(e))
            self._audit(aid, "failed", {"command_id": env["command_id"], "error": str(e)})
            raise

    async def audit(self, event: dict[str, Any]) -> None:
        self._audit(str(event.get("action", {}).get("id", "")), "recorded", {"goal_id": event.get("goal_id")})
