"""Typed uncertainty: failures after a command was sent are EffectUncertain, failures before are not."""
import asyncio

import pytest

from app.modules.m13_browser_agent.session_bridge import protocol
from app.modules.m13_browser_agent.session_bridge.dispatch import DaemonConnection
from app.modules.m13_browser_agent.session_bridge.protocol import (
    CommandKind, DeviceOffline, EffectUncertain, PlatformBlocked)


class WS:
    def __init__(self, fail_send=False):
        self.sent, self.fail_send = [], fail_send

    async def send_json(self, payload):
        if self.fail_send:
            raise RuntimeError("socket closed before send")
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_timeout_after_send_is_effect_uncertain():
    conn = DaemonConnection(WS(), "dev", 0.0)
    with pytest.raises(EffectUncertain):
        await conn.execute(CommandKind.CLICK_SUBMIT, {"session": "s"}, timeout=0.05)


@pytest.mark.asyncio
async def test_disconnect_after_send_is_effect_uncertain_not_plain_offline():
    conn = DaemonConnection(WS(), "dev", 0.0)
    task = asyncio.create_task(conn.execute(CommandKind.CLICK_SUBMIT, {"session": "s"}, timeout=5))
    await asyncio.sleep(0.05)
    conn.fail_all("daemon disconnected")
    with pytest.raises(EffectUncertain):
        await task


@pytest.mark.asyncio
async def test_send_json_failure_is_uncertain_because_a_partial_send_cannot_be_ruled_out():
    conn = DaemonConnection(WS(fail_send=True), "dev", 0.0)
    with pytest.raises(EffectUncertain):
        await conn.execute(CommandKind.CLICK_SUBMIT, {"session": "s"}, timeout=1)


@pytest.mark.asyncio
async def test_failure_before_anything_was_written_is_not_effect_uncertain():
    conn = DaemonConnection(WS(), "dev", 0.0)

    async def broken_pace():
        raise RuntimeError("pacing failed")
    conn._pace = broken_pace
    with pytest.raises(Exception) as caught:
        await conn.execute(CommandKind.CLICK_SUBMIT, {"session": "s"}, timeout=1)
    assert not isinstance(caught.value, EffectUncertain)
    assert conn.websocket.sent == []


def test_parse_result_types_come_from_a_flag_not_from_message_text():
    flagged = {"v": protocol.PROTOCOL_VERSION, "id": "1", "ok": False, "blocked": "policy",
               "error": "anything at all", "effect_uncertain": True}
    with pytest.raises(PlatformBlocked) as caught:
        protocol.parse_result(flagged)
    assert isinstance(caught.value, EffectUncertain)
    text_only = {"v": protocol.PROTOCOL_VERSION, "id": "1", "ok": False, "blocked": "policy",
                 "error": "effect may have occurred; do not retry"}
    with pytest.raises(PlatformBlocked) as caught:
        protocol.parse_result(text_only)
    assert not isinstance(caught.value, EffectUncertain)
    rejected = {"v": protocol.PROTOCOL_VERSION, "id": "1", "ok": False, "error": "x", "effect_uncertain": True}
    with pytest.raises(EffectUncertain):
        protocol.parse_result(rejected)


def test_pre_dispatch_needs_positive_assurance_not_just_a_plain_bridge_error():
    from app.modules.m13_browser_agent.session_bridge.protocol import (
        BridgeError, CommandRejected, PreDispatchError, is_provably_pre_dispatch)
    assert is_provably_pre_dispatch(PreDispatchError("device offline")) is True
    assert is_provably_pre_dispatch(DeviceOffline("not connected")) is True
    assert is_provably_pre_dispatch(BridgeError("unknown origin")) is False
    assert is_provably_pre_dispatch(CommandRejected("old daemon said no")) is False
    assert is_provably_pre_dispatch(PlatformBlocked("policy", "x")) is False
    assert is_provably_pre_dispatch(RuntimeError("x")) is False


def _answer(conn_ws, **extra):
    return {"v": protocol.PROTOCOL_VERSION, "id": conn_ws.sent[0]["id"], "ok": False, **extra}


@pytest.mark.asyncio
@pytest.mark.parametrize("extra,expect_uncertain", [
    ({"blocked": "policy", "error": "older daemon, no flag"}, True),    # absent flag: conservative
    ({"error": "older daemon rejected, no flag"}, True),
    ({"blocked": "policy", "error": "refused", "effect_uncertain": False}, False),  # positive assurance
    ({"error": "refused", "effect_uncertain": False}, False),
    ({"blocked": "policy", "error": "x", "effect_uncertain": True}, True),
])
async def test_version_skew_absent_flag_on_click_submit_is_uncertain(extra, expect_uncertain):
    from app.modules.m13_browser_agent.session_bridge.protocol import is_provably_pre_dispatch
    ws = WS()
    conn = DaemonConnection(ws, "dev", 0.0)
    task = asyncio.create_task(conn.execute(CommandKind.CLICK_SUBMIT, {"session": "s"}, timeout=5))
    await asyncio.sleep(0.05)
    await conn.handle_message(_answer(ws, **extra))
    with pytest.raises(Exception) as caught:
        await task
    assert isinstance(caught.value, EffectUncertain) is expect_uncertain
    assert is_provably_pre_dispatch(caught.value) is (not expect_uncertain)


@pytest.mark.asyncio
async def test_absent_flag_on_other_commands_stays_plain():
    ws = WS()
    conn = DaemonConnection(ws, "dev", 0.0)
    task = asyncio.create_task(conn.execute(CommandKind.NAVIGATE, {"session": "s"}, timeout=5))
    await asyncio.sleep(0.05)
    await conn.handle_message(_answer(ws, blocked="rate_limit", error="slow down"))
    with pytest.raises(PlatformBlocked) as caught:
        await task
    assert not isinstance(caught.value, EffectUncertain)
