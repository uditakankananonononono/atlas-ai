from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from .security import NavigationBlocked, validate_public_url


_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


@dataclass
class _Session:
    context: BrowserContext
    persistent: bool


class PlaywrightSessions:
    """Lazy, tenant-isolated browser contexts with SSRF protection on every request."""

    def __init__(self, root: str = "/tmp/atlas-browser", allowed_hosts: set[str] | None = None, max_sessions: int = 64):
        self.root = Path(root)
        self.allowed_hosts = allowed_hosts
        self.max_sessions = max_sessions
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._sessions: dict[tuple[str, str], _Session] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _check_id(value: str) -> str:
        if not _SAFE_ID.fullmatch(value):
            raise ValueError("invalid tenant or session id")
        return value

    async def start(self) -> None:
        async with self._lock:
            if self._browser is not None:
                return
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)

    async def close(self) -> None:
        async with self._lock:
            sessions, self._sessions = self._sessions, {}
            for session in sessions.values():
                await session.context.close()
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
            self._browser = None
            self._pw = None

    async def close_session(self, tenant_id: str, session_id: str) -> bool:
        key = (self._check_id(tenant_id), self._check_id(session_id))
        async with self._lock:
            session = self._sessions.pop(key, None)
        if session:
            await session.context.close()
            return True
        return False

    async def _guard_route(self, route: Any) -> None:
        try:
            validate_public_url(route.request.url, self.allowed_hosts)
        except NavigationBlocked:
            await route.abort("blockedbyclient")
        else:
            await route.continue_()

    async def page(self, tenant_id: str, session_id: str, persistent: bool = False):
        key = (self._check_id(tenant_id), self._check_id(session_id))
        await self.start()
        async with self._lock:
            existing = self._sessions.get(key)
            if existing and existing.persistent != persistent:
                raise ValueError("session persistence mode cannot change")
            if existing is None:
                if len(self._sessions) >= self.max_sessions:
                    raise RuntimeError("browser session capacity reached")
                assert self._browser is not None
                path = self.root / tenant_id / session_id
                path.mkdir(parents=True, exist_ok=True)
                context = await self._browser.new_context(record_har_path=str(path / "audit.har"))
                await context.route("**/*", self._guard_route)
                existing = _Session(context=context, persistent=persistent)
                self._sessions[key] = existing
            pages = existing.context.pages
            return pages[0] if pages else await existing.context.new_page()
