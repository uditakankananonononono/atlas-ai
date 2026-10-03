"""Daemon tests: block detection, capability gating, submit-token enforcement."""
import pytest

from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.pc_daemon.daemon import (
    Daemon, DeviceIdentity, detect_block)
from app.modules.m13_browser_agent.session_bridge import protocol
from app.modules.m13_browser_agent.session_bridge.protocol import BlockKind, CommandKind


def test_detect_block_classification():
    assert detect_block("https://x.com/feed", 429) is BlockKind.RATE_LIMIT
    assert detect_block("https://www.instagram.com/accounts/login/?next=/", 200) is BlockKind.LOGIN_WALL
    assert detect_block("https://www.linkedin.com/checkpoint/challenge/123", 200) is BlockKind.CHALLENGE
    assert detect_block("https://example.com/page", 200, "please complete the CAPTCHA") is BlockKind.CHALLENGE
    assert detect_block("https://example.com/page", 200, "totally normal page") is None


class FakeLocator:
    def __init__(self, page, selector):
        self.page, self.selector = page, selector

    async def count(self):
        return 1 if self.selector in self.page.values else 0

    @property
    def first(self):
        return self

    async def input_value(self):
        return self.page.values[self.selector]

    async def fill(self, value):
        self.page.values[self.selector] = value
        self.page.filled.append((self.selector, value))

    async def evaluate(self, script):
        return {"type": "text", "ac": ""}

    async def click(self):
        self.page.clicked.append(self.selector)


class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.values = {"#name": "Ada"}
        self.filled = []
        self.clicked = []

    def locator(self, selector):
        return FakeLocator(self, selector)

    main_frame = object()

    def on(self, event, handler):
        pass

    def remove_listener(self, event, handler):
        pass

    async def wait_for_load_state(self, state, timeout=None):
        pass

    async def goto(self, url, wait_until="domcontentloaded"):
        self.url = url

        class Response:
            status = 200
        return Response()

    async def content(self):
        return "<html>normal page</html>"

    def is_closed(self):
        return False


class FakeBrowser:
    def __init__(self):
        self._page = FakePage()

    isolated = False

    async def verify_containment(self):
        return None  # a fake browser has no network to contain

    async def page(self, name):
        return self._page

    async def close_page(self, name):
        return True


@pytest.fixture
def daemon(tmp_path):
    config = DaemonConfig(server_url="https://atlas.test", device_id="dev1",
                          command_secret="topsecret", key_path=str(tmp_path / "key.pem"), pacing_seconds=0, click_settle_seconds=0,
                          consumed_path=str(tmp_path / "consumed.json"),
                          capabilities=["navigate", "extract", "read_values", "fill",
                                        "click_nav", "click_submit"])
    identity = DeviceIdentity.load_or_create(tmp_path / "key.pem")
    instance = Daemon(config, identity)
    instance.browser = FakeBrowser()
    return instance


def _command(kind, args, command_id="cmd-1"):
    return protocol.make_command(kind, args, command_id=command_id)


@pytest.mark.asyncio
async def test_capability_not_granted_is_blocked(tmp_path):
    config = DaemonConfig(server_url="https://atlas.test", device_id="dev1",
                          command_secret="topsecret", key_path=str(tmp_path / "key.pem"), pacing_seconds=0, click_settle_seconds=0,
                          consumed_path=str(tmp_path / "consumed.json"), capabilities=["extract"])
    daemon = Daemon(config, DeviceIdentity.load_or_create(tmp_path / "key.pem"))
    daemon.browser = FakeBrowser()
    answer = await daemon.execute(_command(CommandKind.FILL, {"session": "s", "selector": "#a", "value": "x"}))
    assert answer["ok"] is False
    assert answer["blocked"] == BlockKind.POLICY.value
    assert "not granted" in answer["error"]


@pytest.mark.asyncio
async def test_submit_click_requires_valid_token(daemon):
    args = {"session": "s", "selector": "#go", "approval_id": "a1",
            "capture_sha256": "c" * 64, "values_digest": "d" * 64, "token": "wrong"}
    answer = await daemon.execute(_command(CommandKind.CLICK_SUBMIT, args))
    assert answer["ok"] is False
    assert answer["blocked"] == BlockKind.POLICY.value
    assert "not approved" in answer["error"]
    assert daemon.browser._page.clicked == []  # nothing was clicked


@pytest.mark.asyncio
async def test_submit_click_without_preview_is_refused_even_with_valid_token(daemon):
    import time
    deadline = time.time() + 60
    token = protocol.submit_token("topsecret", approval_id="a1", capture_sha256="c" * 64,
                                  selector="#go", values_digest="d" * 64, deadline=deadline)
    args = {"session": "s", "selector": "#go", "approval_id": "a1", "capture_sha256": "c" * 64,
            "values_digest": "d" * 64, "token": token, "values": {"#name": "Ada"},
            "deadline": deadline}
    answer = await daemon.execute(_command(CommandKind.CLICK_SUBMIT, args))
    assert answer["ok"] is False and "preview" in answer["error"]
    assert daemon.browser._page.clicked == []  # no preview-less plain click path exists


@pytest.mark.asyncio
async def test_submit_click_without_deadline_is_refused_and_token_is_one_shot(daemon):
    import time
    token = protocol.submit_token("topsecret", approval_id="a1", capture_sha256="c" * 64,
                                  selector="#go", values_digest="d" * 64, device_id="dev1", session="s",
                                  expires_at=2000000000)
    args = {"session": "s", "selector": "#go", "approval_id": "a1", "capture_sha256": "c" * 64,
            "values_digest": "d" * 64, "token": token, "expires_at": 2000000000}
    # No reviewed preview on the device: the click is refused before it happens, and the approval is spent.
    first = await daemon.execute(_command(CommandKind.CLICK_SUBMIT, args, command_id="c1"))
    assert first["ok"] is False and "replay" not in first["error"] and "already reserved" not in first["error"]
    assert first["effect_uncertain"] is True and "do not retry" in first["error"]
    again = await daemon.execute(_command(CommandKind.CLICK_SUBMIT, args, command_id="c2"))
    assert again["ok"] is False and again["effect_uncertain"] is True and "already reserved" in again["error"]
    assert daemon.browser._page.clicked == []


@pytest.mark.asyncio
async def test_navigate_reports_platform_block(daemon):
    class LoginWallBrowser(FakeBrowser):
        async def page(self, name):
            page = FakePage()

            async def goto(url, wait_until="domcontentloaded"):
                page.url = "https://www.instagram.com/accounts/login/?next=/"

                class Response:
                    status = 200
                return Response()
            page.goto = goto
            return page
    daemon.browser = LoginWallBrowser()
    answer = await daemon.execute(_command(CommandKind.NAVIGATE,
                                           {"session": "s", "url": "https://www.instagram.com/"}))
    assert answer["ok"] is False
    assert answer["blocked"] == BlockKind.LOGIN_WALL.value
    assert answer["receipt"]["phase"] == "blocked"


@pytest.mark.asyncio
async def test_receipt_chain_matches_m21_format(daemon):
    await daemon.execute(_command(CommandKind.NAVIGATE, {"session": "s", "url": "https://example.com"},
                                  command_id="cmd-a"))
    await daemon.execute(_command(CommandKind.EXTRACT, {"session": "s"}, command_id="cmd-b"))
    events = daemon.receipts.events
    assert [e["sequence"] for e in events] == [1, 2]
    assert events[1]["previous_hash"] == events[0]["event_hash"]
    # Verified by the same logic the server registry uses.
    import hashlib
    import hmac as hmac_mod
    import json
    previous = "0" * 64
    for position, raw in enumerate(events, 1):
        body = json.dumps({"sequence": position, "device_id": "dev1",
                           "action_id": raw["action_id"], "phase": raw["phase"],
                           "payload": raw["payload"], "previous_hash": previous},
                          sort_keys=True, default=str)
        computed = hashlib.sha256(body.encode()).hexdigest()
        assert hmac_mod.compare_digest(computed, raw["event_hash"])
        previous = computed
