"""Adversarial proof for the unified v3 submit token (M18 preview/selector/values binding + device/session binding
+ durable reservation + consumed-submit store).

FIXTURE LABEL: the click body is a counted fake (same labeled fixture as test_m13_daemon_replay.py). What is proven
here is the ordering and the fail-closed behaviour of the token / ledger / consumed store; the real M18 click is
proven on real Chromium in test_m13_daemon_postclick_status.py and test_m13_paired_websocket_e2e.py."""
import asyncio
import json
import time
from dataclasses import replace
from pathlib import Path

import pytest

from app.modules.m13_browser_agent.pc_daemon import daemon as dmod
from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon, DeviceIdentity, redact_urls
from app.modules.m13_browser_agent.session_bridge import protocol as p

from tests.modules.test_m13_daemon_replay import Browser, _labeled_fake_click_fixture  # noqa: F401


@pytest.fixture
def env(tmp_path):
    config = DaemonConfig(device_id="dev", command_secret="secret", key_path=str(tmp_path / "key.pem"),
                          pacing_seconds=0, click_settle_seconds=0, consumed_path=str(tmp_path / "consumed.json"),
                          capabilities=["click_submit", "click_nav"])
    identity = DeviceIdentity.load_or_create(tmp_path / "key.pem")
    browser = Browser()

    def make(cfg=config):
        d = Daemon(cfg, identity)
        d.browser = browser
        return d
    return make, browser, config


def cmd(config, *, approval="ap", expires=None, session="main", device=None, preview_sha="", cid="c1", **over):
    args = dict(session=session, approval_id=approval, selector="#go", capture_sha256="c" * 64,
                values_digest="d" * 64, expires_at=expires or int(time.time()) + 120)
    if preview_sha:
        args["preview_sha256"] = preview_sha
    args["token"] = p.submit_token(config.command_secret, device_id=device or config.device_id, **args)
    args.update(over)
    return p.make_command(p.CommandKind.CLICK_SUBMIT, args, command_id=cid)


def reservations(daemon):
    import sqlite3
    db = sqlite3.connect(daemon.effects.path)
    try:
        return db.execute("SELECT count(*) FROM submit_effects").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


@pytest.mark.asyncio
@pytest.mark.parametrize("what", ["wrong_device", "wrong_session_in_args", "wrong_preview_digest", "v2_style_token_without_binding"])
async def test_wrong_binding_refused_before_any_reservation_or_click(env, what):
    make, browser, config = env
    if what == "wrong_device":
        c = cmd(config, device="other-device")
    elif what == "wrong_session_in_args":
        c = cmd(config, session="main")
        c["args"]["session"] = "elsewhere"
    elif what == "wrong_preview_digest":
        c = cmd(config, preview_sha="a" * 64)
        c["args"]["preview_sha256"] = "b" * 64
    else:
        c = cmd(config)
        c["args"]["token"] = c["args"]["token"].replace("3", "2", 1)
    d = make()
    answer = await d.execute(c)
    assert answer["ok"] is False and answer["effect_uncertain"] is False
    assert browser.clicks == 0 and reservations(d) == 0


@pytest.mark.asyncio
async def test_expiry_between_reserve_and_click_never_clicks_and_keeps_reservation(env, monkeypatch):
    make, browser, config = env
    d = make()
    c = cmd(config, expires=int(time.time()) + 5)

    async def slow_pace():  # time passes after the reservation, before the click
        real = time.time()
        monkeypatch.setattr(p.time, "time", lambda: real + 3600)
    d._pace = slow_pace
    answer = await d.execute(c)
    assert answer["ok"] is False and "expired before effect" in answer["error"]
    assert browser.clicks == 0 and reservations(d) == 1
    monkeypatch.undo()
    # a fresh armed token for the same approval cannot reuse the retained reservation
    retry = await make().execute(cmd(config, expires=int(time.time()) + 120, cid="c2"))
    assert retry["ok"] is False and "already reserved" in retry["error"] and browser.clicks == 0


@pytest.mark.asyncio
async def test_crash_between_reserve_and_consume_fails_closed_on_restart(env, monkeypatch):
    make, browser, config = env
    d = make()

    def crash(self, keys, deadline):  # process dies after the durable reservation, before the consumed record
        raise KeyboardInterrupt("simulated crash")
    monkeypatch.setattr(Daemon, "_consume_submit", crash)
    with pytest.raises(KeyboardInterrupt):
        await d.execute(cmd(config))
    monkeypatch.undo()
    assert reservations(d) == 1 and browser.clicks == 0
    restarted = make()  # new process, same stores
    answer = await restarted.execute(cmd(config, cid="after-restart"))
    assert answer["ok"] is False and "already reserved" in answer["error"] and answer["effect_uncertain"] is True
    assert browser.clicks == 0


@pytest.mark.asyncio
async def test_consumed_record_without_reservation_is_still_refused(env):
    """The reverse gap (ledger lost, consumed record kept): the second independent store refuses."""
    make, browser, config = env
    d = make()
    first = await d.execute(cmd(config))
    assert first["ok"] is True and browser.clicks == 1
    Path(d.effects.path).unlink()  # ledger lost
    answer = await make().execute(cmd(config, cid="c3"))
    assert answer["ok"] is False and answer["effect_uncertain"] is True and browser.clicks == 1


@pytest.mark.asyncio
async def test_unusable_consumed_record_refuses_every_submit_but_keeps_reservation(env):
    make, browser, config = env
    Path(config.consumed_path).write_text("{not json")
    d = make()
    answer = await d.execute(cmd(config))
    assert answer["ok"] is False and answer["effect_uncertain"] is True and browser.clicks == 0
    assert reservations(d) == 1  # never silently retried later


@pytest.mark.parametrize("raw", [
    "blocked: GET http://h/p?token=SECRETQ&x=1#frag not part of the click",
    "see https://user:pw@h.example/path/to?next=%2Flogin&challenge=1",
    "HTTP://H/Path?TOKEN=SECRETQ",
    "navigated to http://127.0.0.1:9/cb?code=abc123#access_token=SECRETQ done",
])
def test_redaction_strips_query_fragment_and_userinfo_in_plain_urls(raw):
    out = redact_urls(raw)
    for leak in ("SECRETQ", "token=", "abc123", "next=", "challenge=", "pw@", "frag"):
        assert leak.lower() not in out.lower(), (leak, out)


@pytest.mark.parametrize("raw", [
    "blocked: GET http%3A%2F%2Fh%2Fp%3Ftoken%3DSECRETQ not part of the click",
    "blocked: GET http:\\/\\/h\\/p?token=SECRETQ",
    "request failed (token=SECRETQ)",
    "Authorization: Bearer SECRETQ rejected",
])
def test_redaction_of_encoded_and_bare_token_forms(raw):
    out = redact_urls(raw)
    assert "SECRETQ" not in out, out
