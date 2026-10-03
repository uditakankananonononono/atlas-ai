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
from .effects import EffectLedger

# Heuristics for "the site stopped us". Each is a reason to report blocked,
# never to retry or evade.
_LOGIN_URL_MARKERS = ("/accounts/login", "/login", "/signin", "/authwall")
_CHALLENGE_MARKERS = ("challenge", "captcha", "checkpoint")


def detect_block(url: str, http_status: int | None, html_excerpt: str = "") -> BlockKind | None:
    """Classify a page state as a platform block, or None when the read is clean."""
    lowered_url = (url or "").lower()
    if http_status == 429:
        return BlockKind.RATE_LIMIT
    if http_status in (401, 403, 503):
        return BlockKind.POLICY
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


def safe_url(url: str | None) -> str:
    """scheme://host/path only: queries and fragments often carry tokens and never leave the PC."""
    from urllib.parse import urlsplit
    try:
        parts = urlsplit(url or "")
    except ValueError:
        return "unknown page"
    if not parts.scheme:
        return (url or "")[:200]
    return f"{parts.scheme}://{parts.netloc.rsplit('@', 1)[-1]}{parts.path}"[:500]


_SENSITIVE_NAME = ("password", "passwd", "passcode", "otp", "2fa", "mfa", "token", "secret",
                   "cvv", "cvc", "card", "ssn", "pin")
_SENSITIVE_AUTOCOMPLETE = ("password", "one-time-code", "cc-number", "cc-csc", "cc-exp")


async def _is_credential_field(locator: Any) -> bool:
    """True for password, one-time-code and card fields; their values are never read out."""
    info = await locator.evaluate(
        "e => ({type: (e.type || '').toLowerCase(), ac: (e.autocomplete || '').toLowerCase(),"
        " names: [e.name, e.id, e.placeholder, e.getAttribute('aria-label'), e.getAttribute('data-testid')]"
        ".filter(Boolean).join(' ').toLowerCase(),"
        " masked: (getComputedStyle(e).webkitTextSecurity || 'none') !== 'none'})")
    if info.get("type") == "password" or info.get("masked"):
        return True
    if any(m in info.get("ac", "") for m in _SENSITIVE_AUTOCOMPLETE):
        return True
    import re
    return any(re.search(rf"(?<![a-z]){re.escape(m)}(?![a-z])|{re.escape(m)}", info.get("names", ""))
               for m in _SENSITIVE_NAME if len(m) > 3) or any(
        re.search(rf"(?<![a-z0-9]){re.escape(m)}(?![a-z0-9])", info.get("names", ""))
        for m in _SENSITIVE_NAME if len(m) <= 3)


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
        self.effects = EffectLedger(Path(config.effect_ledger_path) if config.effect_ledger_path
                                    else Path(config.key_path).parent / "submit-effects.sqlite3")
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
        args = dict(args)  # freeze wire fields before any await
        session = str(args.get("session", "default"))[:120]
        capability = "click_submit" if kind is CommandKind.CLICK_SUBMIT else kind.value
        if capability not in self._capabilities:
            event = self._receipt_event(command_id, "blocked", {"reason": "capability not granted",
                                                              "capability": capability})
            return protocol.make_result(command_id, ok=False,
                                        error=f"capability '{capability}' was not granted at pairing",
                                        blocked=BlockKind.POLICY.value, receipt=event,
                                        effect_uncertain=False if kind is CommandKind.CLICK_SUBMIT else None)
        submit_claims = None
        if kind is CommandKind.CLICK_SUBMIT:
            # Do not coerce/truncate signed claims. A token for another device,
            # session, action or expired approval must never reach the browser.
            submit_claims = dict(
                approval_id=args.get("approval_id"), capture_sha256=args.get("capture_sha256"),
                selector=args.get("selector"), values_digest=args.get("values_digest"),
                device_id=self.config.device_id, session=args.get("session"),
                expires_at=args.get("expires_at"), token=args.get("token"), action=kind.value)
            if not protocol.verify_submit_token(self.config.command_secret, **submit_claims):
                event = self._receipt_event(command_id, "blocked", {"reason": "submit token invalid"})
                return protocol.make_result(command_id, ok=False,
                                            error="submit token missing, expired or invalid; the click was not approved",
                                            blocked=BlockKind.POLICY.value, receipt=event, effect_uncertain=False)
            session = args["session"]
            try:
                reserved = self.effects.reserve(self.config.device_id, args["approval_id"],
                                                command_id, session)
            except Exception as error:
                return protocol.make_result(command_id, ok=False,
                                            error=f"effect reservation unavailable; no click: {error}",
                                            blocked=BlockKind.POLICY.value, effect_uncertain=False)
            if not reserved:
                event = self._receipt_event(command_id, "blocked", {"reason": "effect already reserved"})
                return protocol.make_result(command_id, ok=False,
                                            error="effect already reserved; outcome may be uncertain; do not retry",
                                            blocked=BlockKind.POLICY.value, receipt=event, effect_uncertain=True)
        try:
            await self._pace()
            if submit_claims is not None and not protocol.verify_submit_token(
                    self.config.command_secret, **submit_claims):
                return protocol.make_result(command_id, ok=False,
                                            error="submit token expired before effect; reservation retained",
                                            blocked=BlockKind.POLICY.value, effect_uncertain=False)
            result = await self._run(kind, session, args)
        except Exception as error:  # noqa: BLE001 - report, never retry blindly
            detail = str(error)
            if submit_claims is not None:
                detail = f"effect outcome uncertain; reservation retained; do not retry: {error}"
            event = self._receipt_event(command_id, "failed", {"error": detail[:1000]})
            return protocol.make_result(command_id, ok=False, error=detail[:2000], receipt=event,
                                        effect_uncertain=True if submit_claims is not None else None)
        block = detect_block(result.get("url", ""), result.get("http_status"),
                             result.get("html_excerpt", ""))
        is_click = kind in (CommandKind.CLICK_NAV, CommandKind.CLICK_SUBMIT)
        if is_click:
            result.pop("html_excerpt", None)  # used for classification only; never returned
            result["url"] = safe_url(result.get("url"))  # classified on the raw URL above
        if block is not None:
            if submit_claims is not None:
                # The click happened; the site then stopped us. Keep the reservation so
                # the submit is never retried, and say the outcome is unknown.
                error = (f"platform blocked after click ({block.value}); "
                         "effect may have occurred; do not retry")
            elif kind in (CommandKind.CLICK_NAV, CommandKind.CLICK_SUBMIT):
                error = f"platform blocked after click ({block.value}) at {safe_url(result.get('url'))}"
            else:
                error = f"site stopped the read at {safe_url(result.get('url'))}"
            event = self._receipt_event(command_id, "blocked", {"block": block.value, "url": safe_url(result.get("url")),
                                                              "http_status": result.get("http_status")})
            return protocol.make_result(command_id, ok=False, error=error,
                                        blocked=block.value, receipt=event,
                                        effect_uncertain=True if submit_claims is not None else None)
        if submit_claims is not None:
            try:
                self.effects.click_observed(self.config.device_id, args["approval_id"])
            except Exception as error:
                return protocol.make_result(command_id, ok=False, effect_uncertain=True,
                                            error=f"effect outcome uncertain; do not retry: {error}")
        payload = {"kind": kind.value, "url": safe_url(result.get("url"))}
        if is_click:
            # ok means "click dispatched, no block seen in the bounded window". Never "site accepted".
            result["site_acceptance"] = "unconfirmed"
            payload["site_acceptance"] = "unconfirmed"
        # A click is never "completed": the click was dispatched, the site's answer is unconfirmed.
        event = self._receipt_event(command_id, "dispatched_unconfirmed" if is_click else "completed", payload)
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
                    if await _is_credential_field(locator.first):
                        raise PermissionError("read refused: credential field values never leave the PC")
                    values[str(selector)] = await locator.first.input_value()
            return {"values": values, "url": page.url}
        if kind is CommandKind.FILL:
            await page.locator(str(args["selector"])).fill(str(args["value"]))
            return {"url": page.url}
        if kind in (CommandKind.CLICK_NAV, CommandKind.CLICK_SUBMIT):
            extra = {}
            if kind is CommandKind.CLICK_SUBMIT:
                if not protocol.verify_submit_token(
                        self.config.command_secret, approval_id=args.get("approval_id"),
                        capture_sha256=args.get("capture_sha256"), selector=args.get("selector"),
                        values_digest=args.get("values_digest"), device_id=self.config.device_id,
                        session=session, expires_at=args.get("expires_at"), token=args.get("token"),
                        action=kind.value):
                    raise RuntimeError("submit token expired before click; reservation retained")
                extra = {"approval_id": args.get("approval_id"), "capture_sha256": args.get("capture_sha256")}
            # Capture the main-frame document response a click causes (if any) so the
            # landing page's HTTP status is classified exactly like NAVIGATE's.
            statuses: list[int] = []
            last_event = [time.monotonic()]

            def _on_response(response: Any) -> None:
                try:
                    if (response.request.is_navigation_request()
                            and response.request.frame == page.main_frame):
                        statuses.append(int(response.status))
                        last_event[0] = time.monotonic()
                except Exception:  # noqa: BLE001 - observation only, never alter the click
                    pass

            def _on_navigated(frame: Any) -> None:
                if frame == page.main_frame:
                    last_event[0] = time.monotonic()

            page.on("response", _on_response)
            page.on("framenavigated", _on_navigated)
            started = time.monotonic()
            try:
                await page.locator(str(args["selector"])).click()
                last_event[0] = time.monotonic()
                # Watch until no main-frame navigation has happened for the settle time
                # (each navigation restarts it), capped. This catches redirects and short
                # JS-timer navigations; it cannot see anything that starts later.
                settle = float(self.config.click_settle_seconds)
                cap = float(self.config.click_observe_max_seconds)
                while True:
                    now = time.monotonic()
                    if now - last_event[0] >= settle or now - started >= cap:
                        break
                    await asyncio.sleep(min(0.05, settle))
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:  # noqa: BLE001
                    pass
                html_excerpt = (await page.content())[:4000]
            finally:
                page.remove_listener("response", _on_response)
                page.remove_listener("framenavigated", _on_navigated)
            return {"url": page.url, "http_status": statuses[-1] if statuses else None,  # raw: classified, then sanitized in execute()
                    "html_excerpt": html_excerpt,
                    "post_click_observation": {
                        "bounded": True, "window_seconds": round(time.monotonic() - started, 2),
                        "main_frame_navigations_seen": len(statuses),
                        "note": ("later navigations after this window are not observed; "
                                 "ok means no block was seen in the window, not that the site accepted it")},
                    **extra}
        if kind is CommandKind.CLOSE:
            closed = await self.browser.close_page(session)
            return {"closed": closed}
        raise RuntimeError(f"unsupported command kind: {kind}")

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
