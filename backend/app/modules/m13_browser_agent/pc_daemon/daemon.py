"""The daemon loop: pair, connect, execute commands under the owner's rules."""
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

from .receipts import ReceiptChain  # same hash-chain format the server registry verifies
from ..session_bridge import protocol
from ..session_bridge.protocol import BlockKind, CommandKind
from .config import DaemonConfig
from ..session_bridge import form_guard

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


NAV_WAIT_SECONDS = 0.8  # fixed delay before the daemon sends a guarded click's navigation


class BrowserHandle:
    """Playwright lifecycle: attach over CDP or launch a persistent profile."""

    def __init__(self, config: DaemonConfig):
        self.config = config
        self._playwright = None
        self._browser = None
        self._context = None
        self._session_ctx = None
        self._probe_ok = None
        self._launched = False
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
            self._launched = True
            self._context = await self._playwright.chromium.launch_persistent_context(
                str(profile), headless=False, args=self.launch_args())

    @property
    def isolated(self) -> bool:
        return self._session_ctx is not None

    async def _session_context(self):
        """Session pages live in their OWN browser context: no other tab of the site shares their
        storage, BroadcastChannel or workers, and the owner's tabs cannot be reached from them.
        Cookies and localStorage are copied once from the owner's context when the first session
        page is made (so log in first). Not possible for a persistent-profile launch (that context has
        no Browser object); then sessions share the owner's context and `isolated` stays False."""
        if self._session_ctx is None and self.config.isolate_session_context:
            browser = getattr(self._context, "browser", None)
            if browser is not None:
                state = await self._context.storage_state()
                self._session_ctx = await browser.new_context(storage_state=state, service_workers="block")
        return self._session_ctx or self._context

    def launch_args(self) -> list[str]:
        """Chromium flags for a browser this daemon launches itself. Not applied when attaching over
        CDP to the owner's browser. --host-resolver-rules (MAP * ~NOTFOUND, EXCLUDE <site>) needs the site
        host, which is not known at launch, so it is NOT applied here."""
        extra = list(self.config.browser_args)
        if any(arg.startswith("--proxy-server") or arg.startswith("--proxy-pac-url") for arg in extra):
            raise ValueError("a proxy is not allowed for a guarded browser (it would carry the site's traffic and DNS)")
        rules = [arg.split("=", 1)[1] for arg in extra if arg.startswith("--host-resolver-rules=")]
        extra = [arg for arg in extra if not arg.startswith("--host-resolver-rules=")]
        args = ["--disable-quic", "--no-proxy-server",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                "--webrtc-ip-handling-policy=disable_non_proxied_udp", *extra]
        if self.config.site_hosts:
            # Merge with any rules the caller passed (theirs first, so they keep precedence), then deny the rest.
            rules.append("MAP * ~NOTFOUND, EXCLUDE " + ", EXCLUDE ".join(self.config.site_hosts))
        if rules:
            args.append("--host-resolver-rules=" + ", ".join(rules))
        return args

    async def verify_containment(self) -> str | None:
        """None when guarded sessions may run, else the reason they may not. A browser we launched has
        the flags. An attached (CDP) browser is refused unless the owner attested its launch flags AND a
        live probe shows no UDP/ICE packet leaves it. DNS containment over CDP is attested, never probed."""
        if not self.config.cdp_url:
            if self._launched and not self.config.site_hosts and not any(
                    arg.startswith("--host-resolver-rules=") for arg in self.config.browser_args):
                return ("guarded sessions are refused: this daemon launched the browser without site_hosts "
                        "(or a --host-resolver-rules in browser_args), so a secret could leave as a DNS name")
            return None
        if not self.config.cdp_containment_attested:
            return ("guarded sessions are refused on an attached browser: the daemon cannot set network "
                    "containment flags over CDP. Attest (cdp_containment_attested) ONLY a browser you started with "
                    "launch_args() including host-resolver-rules for the site; the daemon's live probe checks the "
                    "page-script WebRTC layer only, not DNS, proxy or your flags")
        if self._probe_ok is None:
            self._probe_ok = await self._udp_probe()
        return None if self._probe_ok else "the attached browser let WebRTC/ICE UDP out in a live probe"

    async def _udp_probe(self) -> bool:
        """Open a page exactly as a session page is opened (same init script) and try to start ICE three
        ways: directly, through an iframe's contentWindow and from a srcdoc iframe. Any packet at a local
        UDP socket means the layer is not holding. This probes the page-script layer on the attached
        browser; it cannot probe DNS, proxy settings or a flag-free browser's other UDP paths."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0)); sock.settimeout(0.2)
        page = await (await self._session_context()).new_page()
        try:
            await page.add_init_script(form_guard.FRAME_DENY_JS)
            await page.goto("about:blank")
            await page.evaluate("""p => {
                const start = (W) => { try { const pc = new W.RTCPeerConnection({iceServers:[{urls:'stun:127.0.0.1:'+p}]});
                  pc.createDataChannel('x'); pc.createOffer().then(o => pc.setLocalDescription(o)); } catch (e) {} };
                start(window);
                const f = document.createElement('iframe'); document.body.appendChild(f); start(f.contentWindow);
                const g = document.createElement('iframe');
                g.srcdoc = '<script>try{const pc=new RTCPeerConnection({iceServers:[{urls:"stun:127.0.0.1:' + p + '"}]});pc.createDataChannel("x");pc.createOffer().then(o=>pc.setLocalDescription(o))}catch(e){}<\\/script>';
                document.body.appendChild(g); }""", sock.getsockname()[1])
            await page.wait_for_timeout(1500)
            try:
                sock.recvfrom(2000)
                return False
            except OSError:
                return True
        finally:
            sock.close(); await page.close()

    async def page(self, name: str) -> Any:
        if self._context is None:
            raise RuntimeError("browser is not started")
        page = self._pages.get(name)
        if page is None or page.is_closed():
            page = await (await self._session_context()).new_page()
            await page.add_init_script(form_guard.FRAME_DENY_JS)  # every frame, before any page script
            page.on("response", lambda response, page=page: asyncio.ensure_future(self._snapshot(page, response)))
            self._pages[name] = page
        return page

    @staticmethod
    async def _snapshot(page, response) -> None:
        """Remember the URLs the server's own HTML for the top document refers to, before the page
        script or the user's draft can change the DOM."""
        try:
            if response.request.is_navigation_request() and response.frame == page.main_frame \
                    and "html" in (response.headers.get("content-type") or ""):
                body = (await response.body()).decode("utf-8", "replace")
                page._atlas_doc_urls = (response.url.split("#")[0], form_guard.markup_urls(body, response.url))
                page._atlas_cookies = {(c["name"], c["domain"], c["path"]): c["value"]
                                       for c in await page.context.cookies() if not c.get("httpOnly")}
        except Exception:  # noqa: BLE001 - no snapshot means nothing is pre-approved
            pass

    async def close_page(self, name: str) -> bool:
        page = self._pages.pop(name, None)
        if page is not None and not page.is_closed():
            await page.close()
            return True
        return False

    async def stop(self) -> None:
        if self._session_ctx is not None:
            try:
                await self._session_ctx.close()
            except Exception:  # noqa: BLE001
                pass
            self._session_ctx = None
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
        # One-shot submit tokens/approvals already used (audit findings 3 and F2). Kept on
        # disk so a restart cannot replay them; the deadline is also signed into the token.
        from .config import DEFAULT_STATE_DIR
        safe_device = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in config.device_id) or "device"
        # Never an in-memory-only store: an unset path means the device's default file.
        self.consumed_path = config.consumed_path or str(DEFAULT_STATE_DIR / f"consumed_{safe_device}.json")
        self._consumed_submit: dict[str, float] = {}
        self._store_epoch: str | None = None
        self._store_seq = 0
        self._store_strict = False
        self._store_created = time.time()
        self._store_error = ""
        self._resting: dict[str, Any] = {}
        self._init_store()

    # -- resting guard -----------------------------------------------------------------
    # After a guarded click the guard is NOT removed: it stays on the session page for the life of
    # that document, so a hostile timer, event source, worker or keepalive cannot fire unguarded
    # after the click window. It is lifted only when the daemon replaces the document itself
    # (NAVIGATE), closes the session, or starts the next guarded click. Pages the owner uses in
    # their own tabs are never touched (the guard ignores requests from other pages).

    async def _require_containment(self) -> None:
        reason = await self.browser.verify_containment()
        if reason:
            raise PermissionError(reason)

    async def _lift_resting(self, session: str) -> None:
        guard = self._resting.pop(session, None)
        if guard is not None:
            await guard.remove()

    async def _rest(self, session: str, guard: Any) -> None:
        await guard.close_popups()
        self._resting[session] = guard

    # -- consumed-submit store -------------------------------------------------------
    # Record: {"v":1,"device","epoch","created_at","seq","consumed":{key:expiry},"strict","mac"},
    # HMAC with the command secret, bound to this device id. Next to it is an ANCHOR, a second
    # signed copy of (device, epoch, seq) kept in a different directory keyed by device id
    # (config.anchor_dir, env ATLAS_PC_ANCHOR_DIR, default ~/.atlas-pc/anchors), shared by every
    # record path of this device. Everything fails closed and is checked under an flock on every
    # CLICK_SUBMIT, not only at start-up:
    #  - record missing/unparseable/wrong shape/bad MAC/other device/other epoch than the anchor,
    #    or record seq below the anchor seq (an older snapshot was restored, even before a restart);
    #  - an error is STICKY: once a daemon saw a bad record it refuses every submit until restart;
    #  - a record re-created while a lock file or anchor still exists is "strict": it refuses any
    #    token armed before it existed (arming time = deadline - ARM_TTL_SECONDS).
    # Start-up never raises. Recovery: move the bad record aside and restart.
    # Out of scope (documented): an attacker who can write the state dir, the anchor dir AND holds
    # the command secret; anyone who deletes record, lock file and anchor together.

    def _mac(self, body: dict[str, Any]) -> str:
        import hashlib
        import hmac
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return hmac.new(self.config.command_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    def anchor_paths(self) -> list[Path]:
        """Two anchors in two directory trees, each keyed by device id, resolved once per call.

        Primary: ATLAS_PC_ANCHOR_DIR or ~/.atlas-pc/anchors. Secondary (a different tree):
        ATLAS_PC_ANCHOR_DIR2 or /var/tmp/atlas-pc-anchors-<uid>. Both are pinned inside the record
        and the anchors, so pointing the daemon at other directories is refused, not accepted."""
        primary = os.environ.get("ATLAS_PC_ANCHOR_DIR") or str(Path.home() / ".atlas-pc" / "anchors")
        secondary = os.environ.get("ATLAS_PC_ANCHOR_DIR2") or f"/var/tmp/atlas-pc-anchors-{os.getuid()}"
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in self.config.device_id) or "device"
        return [Path(os.path.realpath(d)) / f"{safe}.anchor.json" for d in (primary, secondary)]

    @property
    def anchor_path(self) -> Path:  # primary, kept for callers and tests
        return self.anchor_paths()[0]

    def _signed(self, body: dict[str, Any]) -> dict[str, Any]:
        return {**body, "mac": self._mac(body)}

    def _verify(self, raw: Any) -> dict[str, Any]:
        import hmac
        if not isinstance(raw, dict):
            raise ValueError("wrong shape")
        mac = raw.get("mac")
        body = {k: v for k, v in raw.items() if k != "mac"}
        if not isinstance(mac, str) or not hmac.compare_digest(mac, self._mac(body)):
            raise ValueError("integrity check failed")
        return raw

    def _store_lock(self):
        import contextlib
        import fcntl

        @contextlib.contextmanager
        def lock():
            path = Path(self.consumed_path + ".lock")
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
        return lock()

    def _read_store(self) -> dict[str, Any]:
        """Parsed, validated record. Raises FileNotFoundError or ValueError."""
        raw = self._verify(json.loads(Path(self.consumed_path).read_text()))
        consumed = raw.get("consumed")
        if (raw.get("v") != 1 or raw.get("device") != self.config.device_id
                or not isinstance(raw.get("epoch"), str) or not raw["epoch"]
                or not isinstance(raw.get("strict"), bool)
                or not isinstance(raw.get("anchor_dirs"), list)
                or isinstance(raw.get("seq"), bool) or not isinstance(raw.get("seq"), int)
                or isinstance(raw.get("created_at"), bool) or not isinstance(raw.get("created_at"), (int, float))
                or not isinstance(consumed, dict)
                or any(not isinstance(k, str) or isinstance(v, bool) or not isinstance(v, (int, float))
                       for k, v in consumed.items())):
            raise ValueError("wrong shape or another device's record")
        return raw

    def _read_anchor(self, path: Path) -> dict[str, Any] | None:
        try:
            raw = self._verify(json.loads(path.read_text()))
        except FileNotFoundError:
            return None
        if (raw.get("v") != 1 or raw.get("device") != self.config.device_id or not isinstance(raw.get("epoch"), str)
                or isinstance(raw.get("seq"), bool) or not isinstance(raw.get("seq"), int)
                or raw.get("anchor_dirs") != self._pins()):
            raise ValueError("anchor has the wrong shape or pins other anchor directories")
        return raw

    def _pins(self) -> list[str]:
        return [str(path) for path in self.anchor_paths()]

    def _atomic_write(self, path: Path, body: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(json.dumps(body))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)

    def _write_store(self) -> None:
        """Record first, anchors second: a crash between them leaves the record ahead (safe)."""
        self._atomic_write(Path(self.consumed_path), self._signed({
            "v": 1, "device": self.config.device_id, "epoch": self._store_epoch,
            "created_at": self._store_created, "seq": self._store_seq,
            "consumed": self._consumed_submit, "strict": self._store_strict, "anchor_dirs": self._pins()}))
        anchor = self._signed({"v": 1, "device": self.config.device_id, "epoch": self._store_epoch,
                               "seq": self._store_seq, "anchor_dirs": self._pins()})
        for path in self.anchor_paths():
            self._atomic_write(path, anchor)

    def _adopt(self, raw: dict[str, Any]) -> None:
        self._store_epoch = raw["epoch"]
        self._store_created = float(raw["created_at"])
        self._store_seq = int(raw["seq"])
        self._store_strict = raw["strict"]
        self._consumed_submit = {k: float(v) for k, v in raw["consumed"].items()}

    def _check_against_anchor(self, raw: dict[str, Any]) -> None:
        """Raise ValueError unless the record agrees with the device anchors in both trees."""
        if raw["anchor_dirs"] != self._pins():
            raise ValueError("the record pins other anchor directories than the ones configured now")
        loaded = [self._read_anchor(path) for path in self.anchor_paths()]
        if any(a is None for a in loaded):
            raise ValueError("a device anchor is missing (both anchors must exist for a record in use)")
        anchors = loaded
        if any(a["epoch"] != raw["epoch"] for a in anchors):
            raise ValueError("the record is not the one the device anchor points to")
        if raw["seq"] < max(a["seq"] for a in anchors):
            raise ValueError("the record went backwards (an older copy was restored)")

    def _init_store(self) -> None:
        try:
            lost = Path(self.consumed_path + ".lock").exists()
            with self._store_lock():
                try:
                    raw = self._read_store()
                except FileNotFoundError:
                    import secrets
                    # Missing record: strict when anything proves one existed (lock file or anchor).
                    self._store_strict = lost or any(path.exists() for path in self.anchor_paths())
                    self._store_epoch = secrets.token_hex(16)
                    self._store_created = time.time()
                    self._store_seq = 0
                    self._consumed_submit = {}
                    self._write_store()
                else:
                    self._check_against_anchor(raw)
                    self._adopt(raw)
        except (OSError, ValueError) as error:
            self._store_error = f"consumed-submit record {self.consumed_path} is unusable at start-up ({error})"

    def _consume_submit(self, keys: tuple[str, ...], deadline: float) -> str | None:
        """Atomically record one-shot use. Returns an error string (refuse) or None (consumed)."""
        from ..session_bridge.form_guard import ARM_TTL_SECONDS
        hint = "Move the record file aside and restart the daemon to start a new one (older tokens are then refused)."
        if self._store_error:
            return f"{self._store_error}; refusing every submit. {hint}"
        try:
            with self._store_lock():
                try:
                    raw = self._read_store()
                    if raw["epoch"] != self._store_epoch:
                        raise ValueError("the record was replaced by a different one")
                    self._check_against_anchor(raw)
                except FileNotFoundError:
                    self._store_error = f"the consumed-submit record {self.consumed_path} disappeared"
                    return f"{self._store_error}; refusing every submit. {hint}"
                except (OSError, ValueError) as error:
                    self._store_error = f"the consumed-submit record {self.consumed_path} is unusable ({error})"
                    return f"{self._store_error}; refusing every submit. {hint}"
                self._adopt(raw)
                now = time.time()
                for key, expires in list(self._consumed_submit.items()):
                    if expires < now:
                        del self._consumed_submit[key]
                if any(key in self._consumed_submit for key in keys):
                    return "replay"
                if self._store_strict and deadline - ARM_TTL_SECONDS < self._store_created:
                    return ("this submit was armed before the consumed-submit record existed, so it cannot be "
                            "proven unused; approve again")
                for key in keys:
                    self._consumed_submit[key] = deadline + 3600.0
                self._store_seq += 1
                try:
                    self._write_store()
                except OSError:
                    for key in keys:
                        self._consumed_submit.pop(key, None)
                    self._store_seq -= 1
                    raise
        except OSError as error:
            return f"cannot record the one-shot use of this submit ({error}); refusing"
        return None

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
                    preview_sha256=str(args.get("preview_sha256", "")),
                    deadline=args.get("deadline"),
                    token=token):
                event = self._receipt_event(command_id, "blocked", {"reason": "submit token invalid"})
                return protocol.make_result(command_id, ok=False,
                                            error="submit token missing or invalid; the click was not approved",
                                            blocked=BlockKind.POLICY.value, receipt=event)
            deadline = args.get("deadline")
            # Arming TTL enforced on the device too. A deadline is mandatory so a replay
            # after a daemon restart cannot outlive the arming window.
            if (isinstance(deadline, bool) or not isinstance(deadline, (int, float))
                    or time.time() > float(deadline)):
                event = self._receipt_event(command_id, "blocked", {"reason": "arming expired"})
                return protocol.make_result(command_id, ok=False,
                                            error="the approved submit was armed too long ago; approve again",
                                            blocked=BlockKind.POLICY.value, receipt=event)
            keys = (f"token:{token}", f"approval:{args.get('approval_id', '')}")
            # Consume before any browser effect: a failed or ambiguous click never replays.
            problem = self._consume_submit(keys, float(deadline))
            if problem == "replay":
                event = self._receipt_event(command_id, "blocked", {"reason": "submit token replayed"})
                return protocol.make_result(command_id, ok=False,
                                            error="submit token already used (replay refused); approve again",
                                            blocked=BlockKind.POLICY.value, receipt=event)
            if problem:
                event = self._receipt_event(command_id, "blocked", {"reason": "consumed record refused"})
                return protocol.make_result(command_id, ok=False, error=problem,
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
            await self._lift_resting(session)  # the document is about to be replaced by the daemon
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
            from ..session_bridge import form_guard
            from ..session_bridge.form_guard import SUBMIT_CONTROL_JS
            locator = page.locator(str(args["selector"]))
            # Navigation clicks never submit. Submit-type controls go through the armed,
            # previewed CLICK_SUBMIT path only (audit finding F3).
            if await locator.evaluate(SUBMIT_CONTROL_JS):
                raise PermissionError("this control would submit a form; submits need an approved, previewed CLICK_SUBMIT")
            # Baseline guard for every daemon-driven click: nothing is approved here, so any
            # non-GET request or body-carrying navigation (including a JS-driven submit from a
            # button, label, or custom element) is aborted and reported.
            await self._require_containment()
            await self._lift_resting(session)
            taint = await form_guard.NetworkGuard.collect_taint(page)
            allowed_href = await form_guard.NetworkGuard.shipped_href(
                page, await locator.evaluate("el => (el.closest('a') || {}).href || ''"))
            guard = form_guard.NetworkGuard(page, taint=taint, allowed_href=allowed_href,
                                            known_urls=await form_guard.NetworkGuard.collect_known_urls(page))
            guard.isolated = self.browser.isolated
            snap = getattr(page, "_atlas_doc_urls", None)
            guard.shipped_url = snap[0] if snap else None
            guard.cookie_baseline = getattr(page, "_atlas_cookies", None)
            await guard.install()
            page_blocked = []
            try:
                await page.evaluate(form_guard.NAV_GUARD_JS, await guard.expose_reporter())
                await locator.click()
                # Constant wait, then the DAEMON sends the one allowed navigation (if the page asked for it).
                # A script that delays or withholds the click's navigation cannot move its arrival time:
                # only whether it asked within this window can reach the server (1 bit).
                await asyncio.sleep(NAV_WAIT_SECONDS)
                if guard.nav_requested:
                    problem = await guard.pre_nav_problem()
                    if problem:
                        guard.blocked.append(problem)
                    else:
                        guard.daemon_nav_ok = True
                        try:
                            await page.goto(allowed_href, referer=guard.shipped_url, wait_until="domcontentloaded")
                        except Exception:  # noqa: BLE001 - the guard report decides
                            pass
                        guard.daemon_nav_ok = False
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:  # noqa: BLE001 - best effort; the guard report decides
                    pass
                # Context-level guard stays up until the page (and any popup) is idle plus a
                # quiet period, so timer-driven and pagehide requests are still judged.
                await guard.settle()
                try:
                    recalled = await page.evaluate(form_guard.NAV_RECALL_JS) or []
                    guard.page_reports.extend(item for item in recalled if item not in guard.page_reports)
                except Exception:  # noqa: BLE001 - navigation destroyed the old document
                    pass
            finally:
                await self._rest(session, guard)  # stays installed for the life of this document
            report = guard.report()
            if report["blocked"]:
                raise PermissionError("navigation click attempted an unapproved request; blocked: "
                                      + "; ".join(report["blocked"])[:500])
            return {"url": page.url, "guard": report}
        if kind is CommandKind.CLICK_SUBMIT:
            await self._require_containment()
            await self._lift_resting(session)
            result = await self._click_submit(page, args)
            await self._after_submit(page, session)
            return result
        if kind is CommandKind.CLOSE:
            await self._lift_resting(session)
            closed = await self.browser.close_page(session)
            return {"closed": closed}
        raise RuntimeError(f"unsupported command kind: {kind}")

    async def _after_submit(self, page: Any, session: str) -> None:
        """The approved POST is done: leave a baseline guard on the resulting document."""
        from ..session_bridge import form_guard
        guard = form_guard.NetworkGuard(page, taint=(), known_urls=await form_guard.NetworkGuard.collect_known_urls(page))
        guard.nav_seen = True
        guard.isolated = self.browser.isolated
        await guard.install()
        await self._rest(session, guard)

    async def _click_submit(self, page: Any, args: dict[str, Any]) -> dict[str, Any]:
        """The one approved click: verify in the real browser, guard it, then click."""
        from bs4 import BeautifulSoup
        from hashlib import sha256
        from ..security import values_digest
        from ..session_bridge import form_guard
        preview = args.get("preview")
        # Every CLICK_SUBMIT needs the reviewed destination preview (audit finding 1).
        # There is no preview-less plain-click path.
        if not isinstance(preview, dict) or "values" not in args:
            raise PermissionError("approved submit requires the reviewed preview")
        snapshot_hash = sha256(json.dumps(preview, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        # M18 binds the preview digest as the capture digest; M13 capture-bound submits
        # carry it separately, covered by the HMAC token.
        if snapshot_hash != (args.get("preview_sha256") or args.get("capture_sha256")):
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
        field_names = form_guard.field_name_map(preview)
        allowed = preview.get('allowed_fields', list(field_names.values()))
        if (soup.select('[form]')
                or any(name not in allowed for name in names)
                or len(set(names)) != len(names)
                or any(node.get('type', '').lower() == 'password' for node in fields)
                or set(names) != set(field_names.values())
                or set(field_names) != set(preview['values'])):
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
        if actual != preview["values"]:
            raise PermissionError("approved form values differ from the reviewed preview")
        # Mitigation for click-time rewrites (TOCTOU). Not a proof: see M18_LOGIN_EXPERIMENTS.md.
        guard = form_guard.NetworkGuard(page, preview, actual,
                                        taint=await form_guard.NetworkGuard.collect_taint(page))
        await guard.install()
        try:
            await page.evaluate(form_guard.GUARD_JS, {"selector": args["selector"], "expected": reviewed})
            await page.locator(str(args["selector"])).click()
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:  # noqa: BLE001 - load state is best effort; the guard report decides
                pass
            await guard.settle(1.5)
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
