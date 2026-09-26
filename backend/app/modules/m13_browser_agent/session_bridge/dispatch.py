"""Command dispatch from Atlas to paired-PC daemons.

``BridgedSessions`` mirrors the ``PlaywrightSessions`` duck type (page /
close_session / start / close) plus the read-adapter surface that
``pre_submit_capture`` expects, so the existing capture-bound approval flow
runs unchanged - the page simply lives on the owner's PC, in her logged-in
browser.

Writes stay gated: a click only leaves as CLICK_SUBMIT when the session was
armed by ``authorize_submit`` (called from the approval-consumption path);
every other click is CLICK_NAV, which the daemon may refuse unless the owner
granted that capability at pairing.
"""
from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path
from typing import Any

from . import protocol
from .protocol import (BlockKind, BridgeError, CommandKind, DeviceOffline,
                       PlatformBlocked, clamp_pacing, is_pc_session, split_pc_session)
from .registry import BridgeRegistry


class DaemonConnection:
    """One live daemon websocket: correlates commands to results by id."""

    def __init__(self, websocket: Any, device_id: str, pacing_seconds: float):
        self.websocket = websocket
        self.device_id = device_id
        self.pacing_seconds = clamp_pacing(pacing_seconds)
        self._pending: dict[str, asyncio.Future] = {}
        self._send_lock = asyncio.Lock()
        self._pace_lock = asyncio.Lock()
        self._last_action_at = 0.0

    async def _pace(self) -> None:
        async with self._pace_lock:
            wait = self.pacing_seconds - (time.monotonic() - self._last_action_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_action_at = time.monotonic()

    async def execute(self, kind: CommandKind, args: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
        command = protocol.make_command(kind, args)
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[command["id"]] = future
        try:
            await self._pace()
            async with self._send_lock:
                await self.websocket.send_json(command)
            raw = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as error:
            raise BridgeError(f"daemon did not answer within {timeout:.0f}s") from error
        finally:
            self._pending.pop(command["id"], None)
        return protocol.parse_result(raw)

    async def handle_message(self, raw: dict[str, Any]) -> None:
        command_id = str(raw.get("id", ""))
        future = self._pending.get(command_id)
        if future is not None and not future.done():
            future.set_result(raw)

    def fail_all(self, reason: str) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(DeviceOffline(reason))
        self._pending.clear()


class ConnectionHub:
    """Registry of live daemon connections, keyed by device id."""

    def __init__(self) -> None:
        self._connections: dict[str, DaemonConnection] = {}
        self._lock = asyncio.Lock()

    async def register(self, connection: DaemonConnection) -> None:
        async with self._lock:
            old = self._connections.get(connection.device_id)
            self._connections[connection.device_id] = connection
        if old is not None:
            old.fail_all("device reconnected")

    async def unregister(self, device_id: str, connection: DaemonConnection) -> None:
        async with self._lock:
            if self._connections.get(device_id) is connection:
                del self._connections[device_id]
        connection.fail_all("device disconnected")

    def get(self, device_id: str) -> DaemonConnection | None:
        return self._connections.get(device_id)

    def online(self, device_id: str) -> bool:
        return device_id in self._connections


HUB = ConnectionHub()


class BridgedLocator:
    """Selector handle whose operations round-trip to the daemon's page."""

    def __init__(self, page: "BridgedPage", selector: str):
        self.page = page
        self.selector = selector

    async def fill(self, value: str) -> None:
        await self.page._execute(CommandKind.FILL, {"selector": self.selector, "value": value})

    async def click(self) -> None:
        await self.page._click(self.selector)

    async def input_value(self) -> str:
        result = await self.page._execute(CommandKind.READ_VALUES, {"selectors": [self.selector]})
        values = result.get("values", {})
        if self.selector not in values:
            raise BridgeError(f"selector not present on the paired page: {self.selector}")
        return values[self.selector]


class BridgedPage:
    """A page on the owner's PC, driven through her paired daemon."""

    def __init__(self, sessions: "BridgedSessions", tenant_id: str, device_id: str, local_name: str):
        self._sessions = sessions
        self.tenant_id = tenant_id
        self.device_id = device_id
        self.local_name = local_name
        self.url = sessions._urls.get((tenant_id, self.session_id), "about:blank")

    @property
    def session_id(self) -> str:
        return f"{protocol.PC_SESSION_PREFIX}{self.device_id}.{self.local_name}"

    async def _execute(self, kind: CommandKind, args: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
        result = await self._sessions._execute(self.tenant_id, self.device_id, self.local_name,
                                               kind, args, timeout=timeout)
        if isinstance(result, dict) and result.get("url"):
            self.url = result["url"]
            self._sessions._urls[(self.tenant_id, self.session_id)] = self.url
        return result

    async def _click(self, selector: str) -> None:
        kind, extra = self._sessions._click_class(self.tenant_id, self.device_id, self.local_name, selector)
        await self._execute(kind, {"selector": selector, **extra})

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> Any:
        result = await self._execute(CommandKind.NAVIGATE, {"url": url, "wait_until": wait_until}, timeout=90.0)
        self.url = result.get("url", self.url)

        class _Response:
            def __init__(self, status: int | None):
                self.status = status
        return _Response(result.get("http_status"))

    def locator(self, selector: str) -> BridgedLocator:
        return BridgedLocator(self, selector)

    async def content(self) -> str:
        result = await self._execute(CommandKind.EXTRACT, {})
        return str(result.get("html", ""))

    async def screenshot(self, *, path: str, full_page: bool = False, mask: list | None = None) -> None:
        mask_selectors = [item.selector for item in (mask or []) if isinstance(item, BridgedLocator)]
        result = await self._execute(CommandKind.SCREENSHOT,
                                     {"full_page": bool(full_page), "mask": mask_selectors},
                                     timeout=120.0)
        encoded = result.get("png_base64")
        if not encoded:
            raise BridgeError("daemon returned no screenshot bytes")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(base64.b64decode(encoded))


class BridgedSessions:
    """Session factory whose pages run on the owner's paired devices."""

    def __init__(self, registry: BridgeRegistry, hub: ConnectionHub | None = None):
        self.registry = registry
        self.hub = hub or HUB
        # One armed submit per (tenant, session); consumed by the next click.
        self._armed: dict[tuple[str, str], dict[str, str]] = {}
        # Last URL reported by the daemon per (tenant, session); lets a fresh
        # page handle know where the paired browser currently is.
        self._urls: dict[tuple[str, str], str] = {}

    # -- PlaywrightSessions-compatible surface -----------------------------

    async def start(self) -> None:
        return None  # daemons connect on their own; nothing to launch

    async def close(self) -> None:
        return None

    async def page(self, tenant_id: str, session_id: str, persistent: bool = False) -> BridgedPage:
        device_id, local_name = split_pc_session(session_id)
        device = self.registry.get_device(device_id)
        if device is None or device.tenant_id != tenant_id:
            raise DeviceOffline("no paired device for this session")
        if device.revoked:
            raise DeviceOffline("paired device is revoked")
        if not self.hub.online(device_id):
            raise DeviceOffline("paired device is not connected")
        return BridgedPage(self, tenant_id, device_id, local_name)

    async def close_session(self, tenant_id: str, session_id: str) -> bool:
        device_id, local_name = split_pc_session(session_id)
        if not self.hub.online(device_id):
            return False
        await self._execute(tenant_id, device_id, local_name, CommandKind.CLOSE, {})
        self._armed.pop((tenant_id, session_id), None)
        return True

    # -- read-adapter surface for pre_submit_capture ------------------------

    async def read_values(self, tenant_id: str, session_id: str, selectors: list[str]) -> dict[str, str]:
        device_id, local_name = split_pc_session(session_id)
        result = await self._execute(tenant_id, device_id, local_name,
                                     CommandKind.READ_VALUES, {"selectors": selectors})
        values = result.get("values", {})
        missing = [selector for selector in selectors if selector not in values]
        if missing:
            raise BridgeError(f"selectors not present on the paired page: {missing}")
        return {selector: values[selector] for selector in selectors}

    async def extract(self, tenant_id: str, session_id: str) -> str:
        device_id, local_name = split_pc_session(session_id)
        result = await self._execute(tenant_id, device_id, local_name, CommandKind.EXTRACT, {})
        return str(result.get("html", ""))

    async def screenshot(self, tenant_id: str, session_id: str, mask_selectors: list[str] | None = None) -> str:
        page = await self.page(tenant_id, session_id, True)
        import secrets as _secrets
        path = f"/tmp/atlas-browser/{tenant_id}/{session_id}/{_secrets.token_hex(12)}.png"
        mask = [BridgedLocator(page, selector) for selector in (mask_selectors or [])]
        await page.screenshot(path=path, full_page=True, mask=mask)
        return path

    # -- approval arming ----------------------------------------------------

    async def authorize_submit(self, tenant_id: str, session_id: str, *, approval_id: str,
                               capture_sha256: str, selector: str, values: dict[str, str]) -> None:
        """Arm the next click on this session as the approved submit.

        Called by the M13 submit path only after the approval was consumed.
        The token is HMACed with the per-device command secret so the daemon
        can verify it independently. Arming is one-shot: the next click on
        this session consumes it, whether it succeeds or fails.
        """
        from ..security import values_digest
        device_id, _ = split_pc_session(session_id)
        device = self.registry.get_device(device_id)
        if device is None or device.tenant_id != tenant_id:
            raise DeviceOffline("no paired device for this session")
        token = protocol.submit_token(device.command_secret, approval_id=approval_id,
                                      capture_sha256=capture_sha256, selector=selector,
                                      values_digest=values_digest(values))
        self._armed[(tenant_id, session_id)] = {
            "approval_id": approval_id, "capture_sha256": capture_sha256, "token": token}

    def _click_class(self, tenant_id: str, device_id: str, local_name: str,
                     selector: str) -> tuple[CommandKind, dict[str, str]]:
        key = (tenant_id, f"{protocol.PC_SESSION_PREFIX}{device_id}.{local_name}")
        armed = self._armed.pop(key, None)
        if armed is None:
            return CommandKind.CLICK_NAV, {}
        return CommandKind.CLICK_SUBMIT, armed

    # -- transport ----------------------------------------------------------

    async def _execute(self, tenant_id: str, device_id: str, local_name: str,
                       kind: CommandKind, args: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
        device = self.registry.get_device(device_id)
        if device is None or device.tenant_id != tenant_id:
            raise DeviceOffline("no paired device for this tenant")
        if device.revoked:
            raise DeviceOffline("paired device is revoked")
        connection = self.hub.get(device_id)
        if connection is None:
            raise DeviceOffline("paired device is not connected")
        capability = "click_submit" if kind is CommandKind.CLICK_SUBMIT else kind.value
        if capability not in set(device.capabilities):
            raise BridgeError(f"paired device was not granted the '{capability}' capability")
        return await connection.execute(kind, {"session": local_name, **args}, timeout=timeout)


class HybridSessions:
    """Routes session ids to the paired-PC bridge or the server-side browser.

    ``pc.``-prefixed sessions run on the owner's device through the bridge;
    everything else uses the existing headless Playwright backend. The
    read-adapter surface (read_values/extract/screenshot) is provided for
    both backends so ``pre_submit_capture`` works uniformly.
    """

    def __init__(self, server_sessions: Any, bridged: BridgedSessions):
        self.server = server_sessions
        self.bridged = bridged

    def _backend(self, session_id: str) -> Any:
        return self.bridged if is_pc_session(session_id) else self.server

    async def start(self) -> None:
        await self.server.start()

    async def close(self) -> None:
        await self.server.close()

    async def page(self, tenant_id: str, session_id: str, persistent: bool = False) -> Any:
        return await self._backend(session_id).page(tenant_id, session_id, persistent)

    async def close_session(self, tenant_id: str, session_id: str) -> bool:
        return await self._backend(session_id).close_session(tenant_id, session_id)

    async def authorize_submit(self, tenant_id: str, session_id: str, **kwargs) -> None:
        """Arm an approved submit; only meaningful for paired-PC sessions."""
        if is_pc_session(session_id):
            await self.bridged.authorize_submit(tenant_id, session_id, **kwargs)

    async def read_values(self, tenant_id: str, session_id: str, selectors: list[str]) -> dict[str, str]:
        if is_pc_session(session_id):
            return await self.bridged.read_values(tenant_id, session_id, selectors)
        page = await self.server.page(tenant_id, session_id, False)
        return {selector: await page.locator(selector).input_value() for selector in selectors}

    async def extract(self, tenant_id: str, session_id: str) -> str:
        if is_pc_session(session_id):
            return await self.bridged.extract(tenant_id, session_id)
        page = await self.server.page(tenant_id, session_id, False)
        return await page.content()

    async def screenshot(self, tenant_id: str, session_id: str, mask_selectors: list[str] | None = None) -> str:
        if is_pc_session(session_id):
            return await self.bridged.screenshot(tenant_id, session_id, mask_selectors)
        import secrets as _secrets
        path = f"/tmp/atlas-browser/{tenant_id}/{session_id}/{_secrets.token_hex(12)}.png"
        page = await self.server.page(tenant_id, session_id, False)
        mask = [page.locator(selector) for selector in (mask_selectors or [])]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=path, full_page=True, mask=mask)
        return path
