"""M13 pairing CLI auth pins.

Audit defect: pair_with_server POSTed the bridge pair endpoint with JSON +
timeout only - no Authorization header or bearer option - while every module
router is mounted behind require_tenant, which rejects a missing Bearer with
401 outside insecure dev mode. The documented pairing CLI could not pair
against the production mount.
"""
import pytest

from app.modules.m13_browser_agent.pc_daemon import __main__ as cli


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        return self._payload


PAIR_PAYLOAD = {"device_id": "dev1", "command_secret": "s3cret",
                "capabilities": ["navigate"]}


def _fake_post(captured, status_code=200):
    def post(url, *, json, timeout, headers=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers or {}
        return _FakeResponse(status_code, PAIR_PAYLOAD)
    return post


def test_pair_sends_bearer_token(monkeypatch, tmp_path, capsys):
    captured = {}
    monkeypatch.setattr("httpx.post", _fake_post(captured))
    rc = cli.main(["pair", "--server", "https://atlas.test", "--nonce", "n",
                   "--code", "123456", "--token", "tok-abc"])
    assert rc == 0
    assert captured["headers"].get("Authorization") == "Bearer tok-abc"


def test_pair_token_from_env_when_flag_absent(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr("httpx.post", _fake_post(captured))
    monkeypatch.setenv("ATLAS_PAIR_TOKEN", "tok-env")
    rc = cli.main(["pair", "--server", "https://atlas.test", "--nonce", "n",
                   "--code", "123456"])
    assert rc == 0
    assert captured["headers"].get("Authorization") == "Bearer tok-env"


def test_pair_flag_overrides_env(monkeypatch):
    captured = {}
    monkeypatch.setattr("httpx.post", _fake_post(captured))
    monkeypatch.setenv("ATLAS_PAIR_TOKEN", "tok-env")
    rc = cli.main(["pair", "--server", "https://atlas.test", "--nonce", "n",
                   "--code", "123456", "--token", "tok-flag"])
    assert rc == 0
    assert captured["headers"].get("Authorization") == "Bearer tok-flag"


def test_pair_without_token_401_is_clean_refusal(monkeypatch, capsys):
    captured = {}
    monkeypatch.setattr("httpx.post", _fake_post(captured, status_code=401))
    monkeypatch.delenv("ATLAS_PAIR_TOKEN", raising=False)
    rc = cli.main(["pair", "--server", "https://atlas.test", "--nonce", "n",
                   "--code", "123456"])
    out = capsys.readouterr()
    assert rc == 2
    assert "401" in out.err
    assert "ATLAS_PAIR_TOKEN" in out.err or "--token" in out.err
    assert "Traceback" not in out.err and "Traceback" not in out.out
    assert captured["headers"].get("Authorization") is None


def test_pair_with_server_raises_refused_on_401(monkeypatch, tmp_path):
    from app.modules.m13_browser_agent.pc_daemon.daemon import (
        PairingRefusedError, pair_with_server)
    monkeypatch.setattr("httpx.post", _fake_post({}, status_code=401))
    with pytest.raises(PairingRefusedError, match="401"):
        pair_with_server("https://atlas.test", "n", "123456", name="pc",
                         capabilities=["navigate"], pacing_seconds=None,
                         key_path=tmp_path / "k.pem", config_path=tmp_path / "c.json")


# --- Auditor-4 403 pins (test-only child) ---
# The 401/403 -> PairingRefusedError branch covered only 401; deleting 403
# from the status check survived the suite. These pins close that, isolate
# HOME (the CLI writes ~/.atlas-pc, never tmp_path on its own), and pin the
# explicit blank-flag behavior of the `args.token or env` fallback.

import json as _json

import app.modules.m13_browser_agent.pc_daemon.config as _pc_config


@pytest.fixture
def isolated_state_dir(monkeypatch, tmp_path):
    """Point the CLI's imported DEFAULT_STATE_DIR at tmp_path (the module
    constant is Path.home()/.atlas-pc at import time - without this, pair
    runs write the device key and config into the real HOME)."""
    monkeypatch.setattr(cli, "DEFAULT_STATE_DIR", tmp_path)
    return tmp_path


def test_pair_with_server_raises_refused_on_403(monkeypatch, tmp_path):
    from app.modules.m13_browser_agent.pc_daemon.daemon import (
        PairingRefusedError, pair_with_server)
    monkeypatch.setattr("httpx.post", _fake_post({}, status_code=403))
    with pytest.raises(PairingRefusedError, match="403"):
        pair_with_server("https://atlas.test", "n", "123456", name="pc",
                         capabilities=["navigate"], pacing_seconds=None,
                         key_path=tmp_path / "k.pem", config_path=tmp_path / "c.json")


def test_pair_cli_403_clean_refusal_no_config_overwrite(monkeypatch, capsys, isolated_state_dir):
    state = isolated_state_dir
    sentinel = state / "config.json"
    original = {"server_url": "https://old.test", "device_id": "keep-me"}
    sentinel.write_text(_json.dumps(original))
    monkeypatch.setattr("httpx.post", _fake_post({}, status_code=403))
    monkeypatch.setenv("ATLAS_PAIR_TOKEN", "tok-env")
    rc = cli.main(["pair", "--server", "https://atlas.test", "--nonce", "n",
                   "--code", "123456"])
    out = capsys.readouterr()
    assert rc == 2
    assert "403" in out.err
    assert "ATLAS_PAIR_TOKEN" in out.err or "--token" in out.err
    assert "Traceback" not in out.err and "Traceback" not in out.out
    # refused pairing must not clobber an existing config or leave a key behind
    assert _json.loads(sentinel.read_text()) == original


def test_pair_cli_403_with_flag_token_sends_it_then_refuses(monkeypatch, capsys, isolated_state_dir):
    captured = {}
    monkeypatch.setattr("httpx.post", _fake_post(captured, status_code=403))
    rc = cli.main(["pair", "--server", "https://atlas.test", "--nonce", "n",
                   "--code", "123456", "--token", "tok-flag"])
    out = capsys.readouterr()
    assert rc == 2
    assert captured["headers"].get("Authorization") == "Bearer tok-flag"
    assert "403" in out.err


def test_pair_blank_flag_falls_back_to_env(monkeypatch, isolated_state_dir):
    # Explicit blank --token "" is falsy, so `args.token or env` uses the env
    # token: the flag wins only when non-empty. Pinned as the intended contract.
    captured = {}
    monkeypatch.setattr("httpx.post", _fake_post(captured))
    monkeypatch.setenv("ATLAS_PAIR_TOKEN", "tok-env")
    rc = cli.main(["pair", "--server", "https://atlas.test", "--nonce", "n",
                   "--code", "123456", "--token", ""])
    assert rc == 0
    assert captured["headers"].get("Authorization") == "Bearer tok-env"


def test_pair_blank_flag_without_env_sends_no_authorization(monkeypatch, isolated_state_dir):
    captured = {}
    monkeypatch.setattr("httpx.post", _fake_post(captured))
    monkeypatch.delenv("ATLAS_PAIR_TOKEN", raising=False)
    rc = cli.main(["pair", "--server", "https://atlas.test", "--nonce", "n",
                   "--code", "123456", "--token", ""])
    assert rc == 0
    assert captured["headers"].get("Authorization") is None
