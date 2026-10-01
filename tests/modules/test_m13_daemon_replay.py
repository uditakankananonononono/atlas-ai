"""No real browser submits: adversarial replay checks use a counted fake locator."""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon, DeviceIdentity
from app.modules.m13_browser_agent.pc_daemon.effects import EffectLedger
from app.modules.m13_browser_agent.session_bridge import protocol as p


class Browser:
    url = "about:blank"

    def __init__(self):
        self.clicks = 0
        self.delay = False
        self.fail = False

    async def page(self, name):
        if self.delay:
            await asyncio.sleep(0.01)
        return self

    def locator(self, selector):
        return self

    async def click(self):
        self.clicks += 1
        await asyncio.sleep(0)
        if self.fail:
            raise RuntimeError("connection lost after effect")


@pytest.fixture
def setup(tmp_path):
    config = DaemonConfig(device_id="test-device", command_secret="test-only-secret",
                          key_path=str(tmp_path / "key.pem"), pacing_seconds=0,
                          capabilities=["click_submit", "click_nav"])
    identity = DeviceIdentity.load_or_create(tmp_path / "key.pem")
    browser = Browser()

    def make(config=config):
        daemon = Daemon(config, identity)
        daemon.browser = browser
        return daemon
    return make, browser, config


def command(config, *, approval="approval", expires=None, command_id="command"):
    args = dict(session="main", approval_id=approval, selector="#submit",
                capture_sha256="c" * 64, values_digest="d" * 64,
                expires_at=expires if expires is not None else int(time.time()) + 120)
    args["token"] = p.submit_token(config.command_secret, device_id=config.device_id, **args)
    return p.make_command(p.CommandKind.CLICK_SUBMIT, args, command_id=command_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["serial", "concurrent", "restart", "different-command-id"])
async def test_duplicate_at_most_once(setup, mode):
    make, browser, config = setup
    daemon = make()
    cmd = command(config)
    if mode == "concurrent":
        browser.delay = True
        answers = await asyncio.gather(daemon.execute(cmd), make().execute(cmd))
    else:
        first = await daemon.execute(cmd)
        if mode == "restart":
            daemon = make()
        if mode == "different-command-id":
            cmd = {**cmd, "id": "other"}
        answers = [first, await daemon.execute(cmd)]
    assert sum(a["ok"] for a in answers) == 1
    assert browser.clicks == 1
    print(f"{mode}: ok={[a['ok'] for a in answers]}, fake clicks={browser.clicks}")


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("session", "other"), ("selector", "#other"), ("approval_id", "other"),
    ("capture_sha256", "e" * 64), ("values_digest", "e" * 64),
    ("expires_at", 2100000000), ("expires_at", "2100000000"), ("token", "wrong")])
async def test_tampering_denied(setup, field, value):
    make, browser, config = setup
    cmd = command(config)
    cmd["args"][field] = value
    answer = await make().execute(cmd)
    assert not answer["ok"] and browser.clicks == 0


@pytest.mark.asyncio
async def test_device_binding_and_expiry(setup):
    make, browser, config = setup
    assert not (await make(replace(config, device_id="other")).execute(command(config)))["ok"]
    assert not (await make().execute(command(config, expires=int(time.time())-1)))["ok"]
    assert browser.clicks == 0


@pytest.mark.asyncio
async def test_expiry_during_page_lookup_denied(setup, monkeypatch):
    make, browser, config = setup
    cmd = command(config, expires=2000000000)
    monkeypatch.setattr(p.time, "time", lambda: 1900000000)
    original = browser.page

    async def lookup(name):
        page = await original(name)
        monkeypatch.setattr(p.time, "time", lambda: 2100000000)
        return page
    browser.page = lookup
    assert not (await make().execute(cmd))["ok"]
    assert browser.clicks == 0


@pytest.mark.asyncio
async def test_uncertain_after_click_never_retried(setup):
    make, browser, config = setup
    browser.fail = True
    cmd = command(config)
    assert not (await make().execute(cmd))["ok"]
    browser.fail = False
    assert not (await make().execute({**cmd, "id": "retry"}))["ok"]
    assert browser.clicks == 1


@pytest.mark.asyncio
async def test_cancelled_before_effect_stays_reserved(setup):
    make, browser, config = setup
    daemon = make()
    ready = asyncio.Event()

    async def pace():
        ready.set()
        await asyncio.Future()
    daemon._pace = pace
    cmd = command(config)
    task = asyncio.create_task(daemon.execute(cmd))
    await ready.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not (await make().execute(cmd))["ok"]
    assert browser.clicks == 0


@pytest.mark.asyncio
async def test_preexisting_crash_reservation_denied(setup):
    make, browser, config = setup
    cmd = command(config)
    assert make().effects.reserve(config.device_id, "approval", "crashed", "main")
    assert not (await make().execute(cmd))["ok"]
    assert browser.clicks == 0


@pytest.mark.asyncio
async def test_ledger_unavailable_fails_closed(setup, tmp_path):
    make, browser, config = setup
    assert not (await make(replace(config, effect_ledger_path=str(tmp_path))).execute(command(config)))["ok"]
    assert browser.clicks == 0


@pytest.mark.asyncio
async def test_navigation_not_deduplicated_and_new_approval_works(setup):
    make, browser, config = setup
    daemon = make()
    nav = p.make_command(p.CommandKind.CLICK_NAV, dict(session="main", selector="#nav"))
    assert (await daemon.execute(nav))["ok"]
    assert (await daemon.execute(nav))["ok"]
    assert (await daemon.execute(command(config)))["ok"]
    assert (await daemon.execute(command(config, approval="new")))["ok"]
    assert browser.clicks == 4


def test_atomic_reservations_across_connections(tmp_path):
    path = tmp_path / "effects.sqlite3"
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda i: EffectLedger(path).reserve("d", "a", str(i), "s"), range(20)))
    assert sum(results) == 1


def test_token_json_prevents_delimiter_collision():
    common = dict(device_id="d", session="s", expires_at=2000000000, values_digest="v", selector="#go")
    a = p.submit_token("test", approval_id="a|b", capture_sha256="c", **common)
    b = p.submit_token("test", approval_id="a", capture_sha256="b|c", **common)
    assert a != b
    with pytest.raises(ValueError):
        p.submit_token("test", approval_id="a", capture_sha256="c", action="navigate", **common)


def _process_reserve(path, index):
    return EffectLedger(path).reserve("device", "approval", str(index), "s")


def test_atomic_reservations_across_processes(tmp_path):
    from concurrent.futures import ProcessPoolExecutor
    from itertools import repeat
    path = tmp_path / "process-effects.sqlite3"
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_process_reserve, repeat(path, 16), range(16)))
    assert sum(results) == 1
