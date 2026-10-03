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
 - idempotency: the action's idempotency_key maps to one Meemee command; a repeat returns the
   stored result and never issues a second command.
 - audit: every phase is appended to a hash chain (m21 AuditChain).
"""
from __future__ import annotations
import hashlib, json
from typing import Any, Callable
from app.core.models import ApprovalStatus
from .local_client_protocol import AuditChain

HIGH_RISK = {"delete_file", "install_package", "uninstall_package", "run_command", "run_workflow",
             "deploy_preview", "connect_tool", "send_message", "spend_money"}


class AdapterError(PermissionError):
    pass


class MeemeeLocalClient:
    def __init__(self, registry: Any, owner_id: str, device_id: str,
                 transport: Callable[[dict[str, Any]], Any], approvals: Any):
        if not owner_id or not device_id:
            raise ValueError("owner_id and device_id are required")
        self.registry, self.owner_id, self.device_id = registry, owner_id, device_id
        self.transport, self.approvals = transport, approvals
        self.chain = AuditChain(device_id)
        self._by_key: dict[str, str] = {}
        self._used_approvals: set[str] = set()

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
        req = self.approvals.get(token)
        if (req is None or req.status != ApprovalStatus.APPROVED or req.action_type != f"claire:{kind}"
                or req.payload.get("preview") != preview):
            raise AdapterError("approval missing, not approved, or not for this exact action")
        if token in self._used_approvals:
            raise AdapterError("approval already used")

    async def execute(self, action: dict[str, Any], approval_token: str | None = None) -> dict[str, Any]:
        kind = action.get("kind", "")
        key = str(action.get("idempotency_key") or "")
        if not key:
            raise ValueError("idempotency_key is required")
        if key in self._by_key:
            cmd = self.registry.command(self._by_key[key])
            return {"replayed": True, "command_id": cmd["command_id"], "status": cmd["status"], "result": cmd["result"]}
        if kind not in await self.capabilities():
            raise AdapterError("capability not declared by device")
        preview = await self.preview(action)
        self._check_approval(action, preview, approval_token)
        if approval_token:
            self._used_approvals.add(approval_token)
        env = self.registry.issue(self.owner_id, self.device_id, kind, action.get("arguments", {}))
        self._by_key[key] = env["command_id"]
        aid = action.get("id") or env["command_id"]
        self.chain.append(aid, "issued", {"command_id": env["command_id"], "kind": kind, "preview_digest": preview["digest"], "approval": approval_token})
        try:
            out = self.transport(env)
            result = getattr(out, "result", out)
            self.registry.complete(env["command_id"], result=result)
            self.chain.append(aid, "completed", {"command_id": env["command_id"]})
            return {"replayed": False, "command_id": env["command_id"], "status": "completed", "result": result}
        except Exception as e:
            self.registry.complete(env["command_id"], error=str(e))
            self.chain.append(aid, "failed", {"command_id": env["command_id"], "error": str(e)})
            raise

    async def audit(self, event: dict[str, Any]) -> None:
        self.chain.append(str(event.get("action", {}).get("id", "")), "recorded", {"goal_id": event.get("goal_id")})
