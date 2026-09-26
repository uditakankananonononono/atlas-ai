"""Pairing, device management, and the daemon websocket for the session bridge.

Tenant-facing routes run under the module's normal require_tenant guard. The
pair-confirm and websocket endpoints are daemon-facing: the daemon
authenticates with the one-time pairing code (confirm) and afterwards with an
ed25519 proof-of-possession signature against its stored public key (connect).
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.auth.context import TenantContext, require_tenant

from . import protocol
from .dispatch import HUB, DaemonConnection
from .registry import BridgeRegistry, PairingError

router = APIRouter(prefix="/browser-agent/bridge", tags=["browser-agent-bridge"])
_registry: BridgeRegistry | None = None


def get_registry() -> BridgeRegistry:
    global _registry
    if _registry is None:
        _registry = BridgeRegistry()
    return _registry


class PairConfirmIn(BaseModel):
    server_nonce: str = Field(min_length=8, max_length=120)
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")
    name: str = Field(min_length=1, max_length=200)
    public_key: str = Field(min_length=32, max_length=4000)
    capabilities: list[str] = Field(min_length=1, max_length=20)
    pacing_seconds: float | None = Field(default=None, ge=protocol.MIN_PACING_SECONDS,
                                         le=protocol.MAX_PACING_SECONDS)


@router.post("/pairing-challenge", status_code=201)
def pairing_challenge(ttl_seconds: int = 300, tenant: TenantContext = Depends(require_tenant),
                      registry: BridgeRegistry = Depends(get_registry)):
    """Start pairing. The owner copies the code into the daemon on her PC."""
    return registry.create_challenge(tenant.tenant_id, ttl_seconds)


@router.post("/pair", status_code=201)
def pair(body: PairConfirmIn, registry: BridgeRegistry = Depends(get_registry)):
    """Daemon-facing: prove the one-time code, receive device credentials."""
    try:
        return registry.confirm_pairing(body.server_nonce, body.code, name=body.name,
                                        public_key=body.public_key, capabilities=body.capabilities,
                                        pacing_seconds=body.pacing_seconds)
    except PairingError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/devices")
def devices(tenant: TenantContext = Depends(require_tenant),
            registry: BridgeRegistry = Depends(get_registry)):
    return registry.list_devices(tenant.tenant_id)


@router.delete("/devices/{device_id}")
def revoke_device(device_id: str, tenant: TenantContext = Depends(require_tenant),
                  registry: BridgeRegistry = Depends(get_registry)):
    if not registry.revoke(tenant.tenant_id, device_id):
        raise HTTPException(404, "device not found")
    return {"device_id": device_id, "revoked": True}


class ReceiptIn(BaseModel):
    events: list[dict] = Field(min_length=1, max_length=10000)


@router.post("/devices/{device_id}/verify-receipt")
def verify_receipt(device_id: str, body: ReceiptIn, tenant: TenantContext = Depends(require_tenant),
                   registry: BridgeRegistry = Depends(get_registry)):
    device = registry.get_device(device_id)
    if device is None or device.tenant_id != tenant.tenant_id:
        raise HTTPException(404, "device not found")
    try:
        return registry.verify_receipt(device_id, body.events)
    except PairingError as error:
        raise HTTPException(422, str(error)) from error


@router.websocket("/ws")
async def daemon_socket(websocket: WebSocket, device_id: str, ts: str, sig: str):
    """Daemon-facing command channel, authenticated by device signature."""
    registry = get_registry()
    try:
        device = registry.verify_connect_signature(device_id, ts, sig)
    except PairingError:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    registry.touch_seen(device_id)
    connection = DaemonConnection(websocket, device_id, device.pacing_seconds)
    await HUB.register(connection)
    try:
        while True:
            raw = await websocket.receive_json()
            if isinstance(raw, dict) and raw.get("v") == protocol.PROTOCOL_VERSION:
                await connection.handle_message(raw)
    except WebSocketDisconnect:
        pass
    finally:
        await HUB.unregister(device_id, connection)
