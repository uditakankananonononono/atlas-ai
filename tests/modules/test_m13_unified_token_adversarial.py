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
@pytest.mark.parametrize("what", ["wrong_device", "wrong_session_in_args", "wrong_preview_digest", "one_char_tampered_token"])
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
        t = c["args"]["token"]
        c["args"]["token"] = ("0" if t[0] != "0" else "1") + t[1:]  # always a real one-character change
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


@pytest.mark.parametrize("raw,leaks", [
    ("blocked ws://h/socket?token=SECRETQ&x=1", ["SECRETQ"]),
    ("blocked wss://h/s?sid=SECRETQ#f", ["SECRETQ"]),
    ("GET https://h.example/reset/SECRETPATHTOKEN123/confirm failed", ["SECRETPATHTOKEN123"]),
    ("GET https://h.example/app;jsessionid=ABCSECRET99/page failed", ["ABCSECRET99"]),
    ("GET https://h.example/verify/aGVsbG8 failed", ["aGVsbG8"]),
    ("failed token%3Dabc123 here", ["abc123"]),
    ("GET https://h.example/x/0123456789abcdef0123456789abcdef/y", ["0123456789abcdef0123456789abcdef"]),
])
def test_redaction_review_findings(raw, leaks):
    out = redact_urls(raw)
    for leak in leaks:
        assert leak not in out, out


def test_redaction_keeps_operational_non_secret_links():
    assert redact_urls("blocked at https://example.com/apply/form?x=1") == "blocked at https://example.com/apply/form"


@pytest.mark.xfail(strict=True, reason="DOCUMENTED BOUND: a secret in an ordinary-looking path segment cannot be recognised")
def test_redaction_bound_secret_in_plain_looking_path_segment_survives():
    assert "hunter" not in redact_urls("GET https://h.example/profile/hunter/page")


def _legacy_v1_token(secret, c):  # real M18 pre-unification format: pipe-delimited + deadline, no device/session
    import hashlib, hmac
    body = "|".join([c["approval_id"], c["capture_sha256"], c["selector"], c["values_digest"], f"deadline={c['expires_at']}"])
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def _legacy_v2_token(secret, c, device):  # real postclick format: canonical JSON, device/session, token_version 2, no preview
    import hashlib, hmac
    claims = dict(approval_id=c["approval_id"], capture_sha256=c["capture_sha256"], selector=c["selector"],
                  values_digest=c["values_digest"], device_id=device, session=c["session"],
                  expires_at=c["expires_at"], action="click_submit", token_version=2)
    return hmac.new(secret.encode(), p.canonical_json(claims).encode(), hashlib.sha256).hexdigest()


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", ["v1_m18_pipe_format", "v2_postclick_json_format"])
async def test_real_legacy_token_formats_are_refused(env, legacy):
    make, browser, config = env
    c = cmd(config)
    a = c["args"]
    a["token"] = (_legacy_v1_token(config.command_secret, a) if legacy.startswith("v1")
                  else _legacy_v2_token(config.command_secret, a, config.device_id))
    d = make()
    answer = await d.execute(c)
    assert answer["ok"] is False and answer["effect_uncertain"] is False
    assert browser.clicks == 0 and reservations(d) == 0


_KILL_SCRIPT = r'''
import asyncio, os, signal, sys, time
sys.path.insert(0, "backend")
from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon, DeviceIdentity
from app.modules.m13_browser_agent.session_bridge import protocol as p
mode, tmp = sys.argv[1], sys.argv[2]
cfg = DaemonConfig(device_id="dev", command_secret="secret", key_path=tmp + "/key.pem", pacing_seconds=0,
                   click_settle_seconds=0, consumed_path=tmp + "/consumed.json", capabilities=["click_submit"])
d = Daemon(cfg, DeviceIdentity.load_or_create(__import__("pathlib").Path(tmp) / "key.pem"))
class B:
    clicks = 0
d.browser = B()
from app.modules.m13_browser_agent.session_bridge.form_guard import ARM_TTL_SECONDS
args = dict(session="main", approval_id="ap", selector="#go", capture_sha256="c" * 64, values_digest="d" * 64,
            expires_at=int(time.time()) + int(ARM_TTL_SECONDS) + 10)  # armed after the strict store was created
args["token"] = p.submit_token("secret", device_id="dev", **args)
kill = lambda *a, **k: os.kill(os.getpid(), signal.SIGKILL)
if mode == "after_reserve":
    d._consume_submit = kill            # SIGKILL after the durable reservation, before the consumed record
elif mode == "mid_store_write":
    os.replace = kill                   # SIGKILL after the temp file is written, before the atomic rename
print(asyncio.run(d.execute(p.make_command(p.CommandKind.CLICK_SUBMIT, args, command_id="k1"))))
print("SURVIVED")
'''


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["after_reserve", "mid_store_write"])
async def test_real_sigkill_subprocess_then_restart_fails_closed(env, tmp_path, mode):
    """REAL SIGKILL of a separate process (not an exception). Proven: no click in the child (it has no
    click path), the reservation survives on disk, and a restarted daemon on the same stores refuses.
    NOT proven: power loss / fsync behaviour of the filesystem."""
    import subprocess, sys, signal
    make, browser, config = env
    child_dir = tmp_path / "child"
    child_dir.mkdir()
    proc = subprocess.run([sys.executable, "-c", _KILL_SCRIPT, mode, str(child_dir)], capture_output=True, text=True,
                          cwd=str(Path(__file__).resolve().parents[2]), env={"PYTHONPATH": "backend", "PATH": "/usr/bin"})
    assert proc.returncode == -signal.SIGKILL, (proc.returncode, proc.stdout, proc.stderr[-500:])
    cfg2 = replace(config, key_path=str(child_dir / "key.pem"), consumed_path=str(child_dir / "consumed.json"))
    restarted = Daemon(cfg2, DeviceIdentity.load_or_create(child_dir / "key.pem"))
    restarted.browser = browser
    from app.modules.m13_browser_agent.session_bridge.form_guard import ARM_TTL_SECONDS
    args = dict(session="main", approval_id="ap", selector="#go", capture_sha256="c" * 64, values_digest="d" * 64,
                expires_at=int(time.time()) + int(ARM_TTL_SECONDS) + 10)
    args["token"] = p.submit_token(cfg2.command_secret, device_id="dev", **args)
    assert reservations(restarted) == 1
    answer = await restarted.execute(p.make_command(p.CommandKind.CLICK_SUBMIT, args, command_id="k2"))
    assert answer["ok"] is False and "already reserved" in answer["error"] and answer["effect_uncertain"] is True
    assert browser.clicks == 0
