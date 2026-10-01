"""The daemon loop: pair, connect, execute commands under the owner's rules."""
from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any

from .receipts import ReceiptChain  # same hash-chain format the server registry verifies
from ..session_bridge import protocol
from ..session_bridge.protocol import BlockKind, CommandKind
from .config import DaemonConfig

# Heuristics for "the site stopped us". Each is a reason to report blocked,
# never to retry or evade.
_LOGIN_URL_MARKERS = ("/accounts/login", "/login", "/signin", "/authwall")
_CHALLENGE_MARKERS = ("challenge", "captcha", "checkpoint")


def detect_block(url: str, http_status: int | None, html_excerpt: str = "") -> BlockKind | None:
    """Classify a page state as a platform block, or None when the read is clean."""
    lowered_url = (url or "").lower()
    if http_status == 429:
        return BlockKind.RATE_LIMIT
    if any(marker in lowered_url for marker in _CHALLENGE_MARKERS):
        return BlockKind.CHALLENGE
    if any(marker in lowered_url for marker in _LOGIN_URL_MARKERS):
        return BlockKind.LOGIN_WALL
    excerpt = (html_excerpt or "")[:4000].lower()
    if "captcha" in excerpt or "unusual activity" in excerpt:
        return BlockKind.CHALLENGE
    return None


class DeviceIdentity:
    """The daemon's ed25519 keypair, generated once and stored locally."""

    def __init__(self, private_key: Any):
        self._private = private_key

    @classmethod
    def load_or_create(cls, path: Path) -> "DeviceIdentity":
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        if path.exists():
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
            return cls(key)
        key = Ed25519PrivateKey.generate()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        path.chmod(0o600)
        return cls(key)

    def public_key_pem(self) -> str:
        from cryptography.hazmat.primitives import serialization
        return self._private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo).decode("utf-8")

    def sign(self, message: bytes) -> bytes:
        return self._private.sign(message)


class BrowserHandle:
    """Playwright lifecycle: attach over CDP or launch a persistent profile."""

    def __init__(self, config: DaemonConfig):
        self.config = config
        self._playwright = None
        self._browser = None
        self._context = None
        self._pages: dict[str, Any] = {}

    async def start(self) -> None:
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        if self.config.cdp_url:
            # Attach to the browser she already has running; her logins stay hers.
            self._browser = await self._playwright.chromium.connect_over_cdp(self.config.cdp_url)
            contexts = self._browser.contexts
            self._context = contexts[0] if contexts else await self._browser.new_context()
        else:
            profile = Path(self.config.profile_dir)
            profile.mkdir(parents=True, exist_ok=True)
            self._context = await self._playwright.chromium.launch_persistent_context(
                str(profile), headless=False)

    async def page(self, name: str) -> Any:
        if self._context is None:
            raise RuntimeError("browser is not started")
        page = self._pages.get(name)
        if page is None or page.is_closed():
            page = await self._context.new_page()
            self._pages[name] = page
        return page

    async def close_page(self, name: str) -> bool:
        page = self._pages.pop(name, None)
        if page is not None and not page.is_closed():
            await page.close()
            return True
        return False

    async def stop(self) -> None:
        if self._context is not None and not self.config.cdp_url:
            await self._context.close()
        if self._browser is not None and self.config.cdp_url:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._context = self._browser = self._playwright = None
        self._pages.clear()


class Daemon:
    def __init__(self, config: DaemonConfig, identity: DeviceIdentity):
        self.config = config
        self.identity = identity
        self.browser = BrowserHandle(config)
        self.receipts = ReceiptChain(config.device_id)
        self._last_action_at = 0.0
        self._capabilities = set(config.capabilities)

    async def _pace(self) -> None:
        wait = self.config.pacing_seconds - (time.monotonic() - self._last_action_at)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_action_at = time.monotonic()

    def _receipt_event(self, action_id: str, phase: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.receipts.append(action_id, phase, payload)

    async def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        command_id, kind, args = protocol.parse_command(command)
        session = str(args.get("session", "default"))[:120]
        capability = protocol.capability_for(kind)
        if capability not in self._capabilities:
            event = self._receipt_event(command_id, "blocked", {"reason": "capability not granted",
                                                              "capability": capability})
            return protocol.make_result(command_id, ok=False,
                                        error=f"capability '{capability}' was not granted at pairing",
                                        blocked=BlockKind.POLICY.value, receipt=event)
        if kind is CommandKind.CLICK_SUBMIT:
            token = str(args.get("token", ""))
            if not protocol.verify_submit_token(
                    self.config.command_secret,
                    approval_id=str(args.get("approval_id", "")),
                    capture_sha256=str(args.get("capture_sha256", "")),
                    selector=str(args.get("selector", "")),
                    values_digest=str(args.get("values_digest", "")),
                    token=token):
                event = self._receipt_event(command_id, "blocked", {"reason": "submit token invalid"})
                return protocol.make_result(command_id, ok=False,
                                            error="submit token missing or invalid; the click was not approved",
                                            blocked=BlockKind.POLICY.value, receipt=event)
            deadline = args.get("deadline")
            # Arming TTL enforced on the device too. Servers that predate the TTL send none.
            if deadline is not None and (not isinstance(deadline, (int, float)) or time.time() > float(deadline)):
                event = self._receipt_event(command_id, "blocked", {"reason": "arming expired"})
                return protocol.make_result(command_id, ok=False,
                                            error="the approved submit was armed too long ago; approve again",
                                            blocked=BlockKind.POLICY.value, receipt=event)
        await self._pace()
        try:
            result = await self._run(kind, session, args)
        except Exception as error:  # noqa: BLE001 - report, never retry blindly
            event = self._receipt_event(command_id, "failed", {"error": str(error)[:1000]})
            return protocol.make_result(command_id, ok=False, error=str(error)[:2000], receipt=event)
        block = detect_block(result.get("url", ""), result.get("http_status"),
                             result.get("html_excerpt", ""))
        if block is not None:
            event = self._receipt_event(command_id, "blocked", {"block": block.value, "url": result.get("url")})
            return protocol.make_result(command_id, ok=False,
                                        error=f"site stopped the read at {result.get('url', 'unknown page')}",
                                        blocked=block.value, receipt=event)
        event = self._receipt_event(command_id, "completed", {"kind": kind.value, "url": result.get("url")})
        return protocol.make_result(command_id, ok=True, result=result, receipt=event)

    async def _run(self, kind: CommandKind, session: str, args: dict[str, Any]) -> dict[str, Any]:
        if kind is CommandKind.SOCIAL_READ:
            from .social_read import run_social_read
            return await run_social_read(args)
        page = await self.browser.page(session)
        if kind is CommandKind.NAVIGATE:
            response = await page.goto(str(args["url"]), wait_until=str(args.get("wait_until", "domcontentloaded")))
            html_excerpt = (await page.content())[:4000]
            return {"url": page.url, "http_status": getattr(response, "status", None),
                    "html_excerpt": html_excerpt}
        if kind is CommandKind.EXTRACT:
            html = await page.content()
            return {"html": html, "url": page.url, "html_excerpt": html[:4000]}
        if kind is CommandKind.SCREENSHOT:
            mask = [page.locator(selector) for selector in args.get("mask", [])]
            data = await page.screenshot(full_page=bool(args.get("full_page")), mask=mask)
            return {"png_base64": base64.b64encode(data).decode("ascii"), "url": page.url}
        if kind is CommandKind.READ_VALUES:
            values = {}
            for selector in args.get("selectors", [])[:200]:
                locator = page.locator(str(selector))
                if await locator.count():
                    values[str(selector)] = await locator.first.input_value()
            return {"values": values, "url": page.url}
        if kind is CommandKind.FORM_FACTS:
            from ..session_bridge.form_guard import FORM_FACTS_JS
            return {"facts": await page.evaluate(FORM_FACTS_JS, str(args["selector"])), "url": page.url}
        if kind is CommandKind.FILL:
            await page.locator(str(args["selector"])).fill(str(args["value"]))
            return {"url": page.url}
        if kind is CommandKind.CLICK_NAV:
            await page.locator(str(args["selector"])).click()
            return {"url": page.url}
        if kind is CommandKind.CLICK_SUBMIT:
            return await self._click_submit(page, args)
        if kind is CommandKind.CLOSE:
            closed = await self.browser.close_page(session)
            return {"closed": closed}
        raise RuntimeError(f"unsupported command kind: {kind}")

    async def _click_submit(self, page: Any, args: dict[str, Any]) -> dict[str, Any]:
        """The one approved click: verify in the real browser, guard it, then click."""
        from bs4 import BeautifulSoup
        from hashlib import sha256
        from ..security import values_digest
        from ..session_bridge import form_guard
        preview = args.get("preview")
        if preview is None:
            # Generic M13 capture-bound submit (no reviewed form preview): the original
            # values check and plain click. The M18 login runner always sends a preview.
            if "values" in args:
                from ..security import values_digest as _vd
                actual = {}
                for selector in args["values"]:
                    locator = page.locator(selector)
                    if await locator.count() != 1:
                        raise PermissionError("approved form selector changed")
                    actual[selector] = await locator.input_value()
                if _vd(actual) != args.get("values_digest"):
                    raise PermissionError("approved form values changed on paired device")
            await page.locator(str(args["selector"])).click()
            return {"url": page.url, "approval_id": args.get("approval_id"),
                    "capture_sha256": args.get("capture_sha256")}
        if not isinstance(preview, dict) or "values" not in args:
            raise PermissionError("approved submit requires the reviewed preview")
        snapshot_hash = sha256(json.dumps(preview, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        if snapshot_hash != args.get("capture_sha256"):
            raise PermissionError("submit preview does not match approved digest")
        soup = BeautifulSoup(await page.content(), "html.parser")
        button = soup.select(args["selector"])
        if len(button) != 1 or str(button[0]) != preview["submit"]:
            raise PermissionError("approved submit target changed on device")
        form = button[0].find_parent("form")
        if form is None:
            raise PermissionError("approved destination or form changed on device")
        if any(attr in node.attrs for node in [button[0], *form.select("input,button")]
               for attr in form_guard.SUBMIT_OVERRIDES):
            raise PermissionError("submit control overrides the reviewed form destination on device")
        reviewed = preview.get("form_facts")
        if not isinstance(reviewed, dict):
            raise PermissionError("approved preview has no browser-resolved form facts")
        form_guard.static_form_checks(soup, form, button[0], reviewed.get("enctype", form_guard.DEFAULT_ENCTYPE))
        # The browser, not urljoin, decides where the form posts (<base>, clobbering, scripts).
        live = form_guard.validate_facts(await page.evaluate(form_guard.FORM_FACTS_JS, args["selector"]),
                                         reviewed["enctype"])
        if (live != reviewed or live["url"] != preview["url"] or page.url != preview["url"]
                or live["action"] != preview["form_action"]
                or form.get("method", "get") != preview["method"]
                or form.get_text(" ", strip=True) != preview["form_text"]):
            raise PermissionError("approved destination or form changed on device")
        fields = form.select('input,textarea,select,button[name]')
        names = [node.get('name') for node in fields]
        if (soup.select('[form]')
                or any(name not in preview['allowed_fields'] for name in names)
                or len(set(names)) != len(names)
                or any(node.get('type', '').lower() == 'password' for node in fields)
                or {f'[name="{name}"]' for name in names} != set(preview['values'])):
            raise PermissionError("reviewed form field allowlist changed on device")
        for field, selector in args.get("readback_selectors", {}).items():
            nodes = soup.select(selector)
            if len(nodes) != 1 or nodes[0].get_text(" ", strip=True) != preview[field]:
                raise PermissionError("approved account or terms changed on device")
        actual = {}
        for selector in args["values"]:
            locator = page.locator(selector)
            if await locator.count() != 1:
                raise PermissionError("approved form selector changed")
            actual[selector] = await locator.input_value()
        if values_digest(actual) != args.get("values_digest"):
            raise PermissionError("approved form values changed on paired device")
        # Mitigation for click-time rewrites (TOCTOU). Not a proof: see M18_LOGIN_EXPERIMENTS.md.
        guard = form_guard.NetworkGuard(page, preview, actual)
        await guard.install()
        try:
            await page.evaluate(form_guard.GUARD_JS, {"selector": args["selector"], "expected": reviewed})
            await page.locator(str(args["selector"])).click()
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:  # noqa: BLE001 - load state is best effort; the guard report decides
                pass
            page_blocked = []
            try:
                page_blocked = await page.evaluate(form_guard.GUARD_STATE_JS) or []
                await page.evaluate(form_guard.GUARD_REMOVE_JS)
            except Exception:  # noqa: BLE001 - navigation destroyed the old document
                pass
        finally:
            await guard.remove()
        report = guard.report()
        report["blocked"] = [*report["blocked"], *[f"page-guard: {item}" for item in page_blocked]]
        return {"url": page.url, "approval_id": args.get("approval_id"),
                "capture_sha256": args.get("capture_sha256"), "guard": report}

    def connect_url(self) -> str:
        timestamp = str(int(time.time()))
        signature = self.identity.sign(f"{self.config.device_id}.{timestamp}".encode("utf-8")).hex()
        base = self.config.server_url.rstrip("/").replace("http", "ws", 1)
        return (f"{base}/api/v1/browser-agent/bridge/ws"
                f"?device_id={self.config.device_id}&ts={timestamp}&sig={signature}")

    async def run(self) -> None:
        import websockets
        await self.browser.start()
        try:
            async with websockets.connect(self.connect_url(), max_size=protocol.MAX_COMMAND_BYTES * 4) as ws:
                async for raw in ws:
                    command = json.loads(raw)
                    answer = await self.execute(command)
                    await ws.send(json.dumps(answer))
        finally:
            await self.browser.stop()


def pair_with_server(server_url: str, nonce: str, code: str, *, name: str,
                     capabilities: list[str], pacing_seconds: float | None,
                     key_path: Path, config_path: Path) -> DaemonConfig:
    """One-time pairing: create the device key, prove the code, store credentials."""
    import httpx
    identity = DeviceIdentity.load_or_create(key_path)
    response = httpx.post(
        f"{server_url.rstrip('/')}/api/v1/browser-agent/bridge/pair",
        json={"server_nonce": nonce, "code": code, "name": name,
              "public_key": identity.public_key_pem(), "capabilities": capabilities,
              "pacing_seconds": pacing_seconds},
        timeout=30.0)
    response.raise_for_status()
    data = response.json()
    config = DaemonConfig(server_url=server_url, device_id=data["device_id"],
                          command_secret=data["command_secret"], key_path=str(key_path),
                          pacing_seconds=pacing_seconds or 5.0, capabilities=data["capabilities"])
    config.save(config_path)
    return config
