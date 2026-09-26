"""Protocol unit tests: framing, pacing bounds, pc-session ids, submit tokens."""
import pytest

from app.modules.m13_browser_agent.session_bridge import protocol
from app.modules.m13_browser_agent.session_bridge.protocol import (
    BlockKind, BridgeError, CommandKind, PlatformBlocked)


def test_make_and_parse_command_roundtrip():
    command = protocol.make_command(CommandKind.NAVIGATE, {"url": "https://example.com"})
    command_id, kind, args = protocol.parse_command(command)
    assert command_id == command["id"]
    assert kind is CommandKind.NAVIGATE
    assert args == {"url": "https://example.com"}


def test_parse_command_rejects_bad_version_and_kind():
    with pytest.raises(BridgeError, match="protocol version"):
        protocol.parse_command({"v": 999, "id": "x", "kind": "navigate", "args": {}})
    with pytest.raises(BridgeError, match="unknown command kind"):
        protocol.parse_command({"v": 1, "id": "x", "kind": "exfiltrate", "args": {}})
    with pytest.raises(BridgeError, match="missing an id"):
        protocol.parse_command({"v": 1, "kind": "navigate", "args": {}})


def test_parse_result_blocked_raises_platform_blocked():
    raw = protocol.make_result("c1", ok=False, error="rate limited", blocked=BlockKind.RATE_LIMIT.value)
    with pytest.raises(PlatformBlocked) as caught:
        protocol.parse_result(raw)
    assert caught.value.kind is BlockKind.RATE_LIMIT


def test_parse_result_failure_raises_command_rejected():
    raw = protocol.make_result("c1", ok=False, error="daemon exploded")
    with pytest.raises(protocol.CommandRejected, match="daemon exploded"):
        protocol.parse_result(raw)


def test_parse_result_ok_returns_result_dict():
    raw = protocol.make_result("c1", ok=True, result={"url": "https://example.com"})
    assert protocol.parse_result(raw) == {"url": "https://example.com"}


def test_pc_session_id_roundtrip_and_validation():
    session = protocol.make_pc_session("abc123", "main")
    assert session == "pc.abc123.main"
    assert protocol.is_pc_session(session)
    assert not protocol.is_pc_session("server-session")
    assert protocol.split_pc_session(session) == ("abc123", "main")
    with pytest.raises(ValueError):
        protocol.split_pc_session("pc.noname")
    with pytest.raises(ValueError):
        protocol.make_pc_session("has.dot", "main")


def test_pacing_is_clamped_to_human_speed_bounds():
    assert protocol.clamp_pacing(None) == protocol.DEFAULT_PACING_SECONDS
    assert protocol.clamp_pacing(0.01) == protocol.MIN_PACING_SECONDS
    assert protocol.clamp_pacing(99999) == protocol.MAX_PACING_SECONDS
    assert protocol.clamp_pacing(7) == 7.0


def test_submit_token_verification():
    secret = "s3cret"
    token = protocol.submit_token(secret, approval_id="a1", capture_sha256="c" * 64,
                                  selector="#go", values_digest="d" * 64)
    assert protocol.verify_submit_token(secret, approval_id="a1", capture_sha256="c" * 64,
                                        selector="#go", values_digest="d" * 64, token=token)
    # Any drift in the approved content fails verification.
    assert not protocol.verify_submit_token(secret, approval_id="a1", capture_sha256="c" * 64,
                                            selector="#other", values_digest="d" * 64, token=token)
    assert not protocol.verify_submit_token("wrong-secret", approval_id="a1", capture_sha256="c" * 64,
                                            selector="#go", values_digest="d" * 64, token=token)
