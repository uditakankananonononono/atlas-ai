"""Secure visual browser actions with immutable, single-use submit approvals."""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from .domain import ActionType, AuditEvent, RunStatus
from .forms import FieldDescriptor, match_fields
from .security import file_digest, validate_public_url, values_digest


class Service:
    def __init__(self, sessions: Any, approval_service: Any, store: Any, artifact_root: str = "/tmp/atlas-browser", allowed_hosts: set[str] | None = None):
        self.sessions = sessions
        self.approvals = approval_service
        self.store = store
        self.root = Path(artifact_root)
        self.allowed_hosts = allowed_hosts

    async def navigate(self, tenant_id: str, session_id: str, url: str, persistent: bool = False) -> dict[str, Any]:
        safe_url = validate_public_url(url, self.allowed_hosts)
        page = await self.sessions.page(tenant_id, session_id, persistent)
        response = await page.goto(safe_url, wait_until="domcontentloaded")
        final_url = validate_public_url(page.url, self.allowed_hosts)
        await self.store.append_audit(AuditEvent(tenant_id, session_id, ActionType.NAVIGATE, {"requested_url": safe_url, "final_url": final_url, "persistent": persistent}))
        return {"status": "ok", "url": final_url, "http_status": getattr(response, "status", None)}

    async def fill(self, tenant_id: str, session_id: str, fields: list[FieldDescriptor], data: dict[str, str]) -> dict[str, str]:
        page = await self.sessions.page(tenant_id, session_id, False)
        mapping = match_fields(fields, data)
        for selector, value in mapping.items():
            await page.locator(selector).fill(value)
        await self.store.append_audit(AuditEvent(tenant_id, session_id, ActionType.FILL, {"selectors": sorted(mapping), "count": len(mapping)}))
        return mapping

    async def click(self, tenant_id: str, session_id: str, selector: str) -> dict[str, str]:
        page = await self.sessions.page(tenant_id, session_id, False)
        await page.locator(selector).click()
        await self.store.append_audit(AuditEvent(tenant_id, session_id, ActionType.CLICK, {"selector": selector}))
        return {"status": "ok"}

    async def screenshot(self, tenant_id: str, session_id: str, mask_selectors: list[str] | None = None) -> str:
        """Full-page screenshot; masked selectors are covered so field values never land in the image."""
        directory = self.root / tenant_id / session_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{secrets.token_hex(12)}.png"
        page = await self.sessions.page(tenant_id, session_id, False)
        mask = [page.locator(selector) for selector in (mask_selectors or [])]
        await page.screenshot(path=str(path), full_page=True, mask=mask)
        await self.store.append_audit(AuditEvent(tenant_id, session_id, ActionType.SCREENSHOT, {"path": str(path), "sha256": file_digest(str(path)), "masked_count": len(mask)}))
        return str(path)

    async def read_values(self, tenant_id: str, session_id: str, selectors: list[str]) -> dict[str, str]:
        """Read back the exact on-page value of each selector; missing selectors raise."""
        page = await self.sessions.page(tenant_id, session_id, False)
        values: dict[str, str] = {}
        for selector in selectors:
            values[selector] = await page.locator(selector).input_value()
        await self.store.append_audit(AuditEvent(tenant_id, session_id, ActionType.READBACK, {"selectors": sorted(selectors), "count": len(values)}))
        return values

    async def extract(self, tenant_id: str, session_id: str) -> str:
        page = await self.sessions.page(tenant_id, session_id, False)
        html = await page.content()
        await self.store.append_audit(AuditEvent(tenant_id, session_id, ActionType.EXTRACT, {"bytes": len(html.encode("utf-8"))}))
        return html

    async def request_submit(self, tenant_id: str, actor_id: str, session_id: str, selector: str, values: dict[str, str]) -> dict[str, Any]:
        page = await self.sessions.page(tenant_id, session_id, False)
        page_url = validate_public_url(page.url, self.allowed_hosts)
        snapshot = await self.screenshot(tenant_id, session_id)
        digest = values_digest(values)
        payload = {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "session_id": session_id,
            "selector": selector,
            "form_values": dict(values),
            "values_digest": digest,
            "page_url": page_url,
            "snapshot_path": snapshot,
            "snapshot_digest": file_digest(snapshot),
        }
        view = self.approvals.submit(module_id=13, action_type="browser_submit", user_id=tenant_id, payload=payload, ttl_seconds=3600)
        await self.store.append_audit(AuditEvent(tenant_id, session_id, ActionType.SUBMIT, {"phase": "staged", "approval_id": view["id"], "selector": selector, "digest": digest, "page_url": page_url}))
        return {"status": RunStatus.AWAITING_APPROVAL, "approval_id": view["id"], "snapshot_path": snapshot, "values_digest": digest, "page_url": page_url}

    async def submit(self, tenant_id: str, session_id: str, selector: str, values: dict[str, str], approval_id: str) -> dict[str, str]:
        view = self.approvals.get(approval_id)
        payload = view.get("payload", {})
        status = view.get("status")
        status = status.value if hasattr(status, "value") else status
        page = await self.sessions.page(tenant_id, session_id, False)
        current_url = validate_public_url(page.url, self.allowed_hosts)
        expected = {"tenant_id": tenant_id, "session_id": session_id, "selector": selector, "values_digest": values_digest(values), "page_url": current_url}
        if status != "approved" or any(payload.get(key) != value for key, value in expected.items()):
            raise PermissionError("approval is missing, stale, denied, or for different content")
        if payload.get("form_values") != values:
            raise PermissionError("approved form values do not match")
        if await self.store.was_consumed(approval_id):
            raise PermissionError("approval was already consumed")
        # Consume before the external effect. A failed click requires a fresh approval and cannot replay.
        await self.store.consume(approval_id, tenant_id)
        authorize = getattr(self.sessions, "authorize_submit", None)
        if authorize is not None:
            await authorize(tenant_id, session_id, approval_id=approval_id,
                            capture_sha256=str(payload.get("capture_sha256", "")),
                            selector=selector, values=values)
        await page.locator(selector).click()
        await self.store.append_audit(AuditEvent(tenant_id, session_id, ActionType.SUBMIT, {"phase": "executed", "selector": selector, "approval_id": approval_id, "digest": expected["values_digest"], "page_url": current_url}))
        return {"status": "submitted"}
