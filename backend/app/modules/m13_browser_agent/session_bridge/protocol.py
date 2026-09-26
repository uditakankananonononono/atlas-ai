"""Wire protocol between Atlas and a paired-PC browser daemon.

One command, one result, one receipt. Commands are JSON dicts; daemons answer
with a result dict plus receipt events (hash-chained per M21's audit format).
Submit-class clicks carry an HMAC token minted by the server only after the
matching approval was consumed, so the daemon can independently verify that
this exact click was approved - the daemon never takes the network's word.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from enum import Enum
from typing import Any

PROTOCOL_VERSION = 1

# Bridged session ids are namespaced so the server can route them to the
# bridge instead of the server-side headless browser.
PC_SESSION_PREFIX = "pc."

# Human-speed pacing bounds, seconds between browser actions on one device.
MIN_PACING_SECONDS = 2.0
MAX_PACING_SECONDS = 120.0
DEFAULT_PACING_SECONDS = 5.0

MAX_COMMAND_BYTES = 256 * 1024
MAX_RESULT_BYTES = 8 * 1024 * 1024  # screenshots travel as base64


class CommandKind(str, Enum):
    NAVIGATE = "navigate"
    EXTRACT = "extract"
    SCREENSHOT = "screenshot"
    READ_VALUES = "read_values"
    FILL = "fill"
    CLICK_NAV = "click_nav"        # reversible in-page navigation (open a dialog, a tab)
    CLICK_SUBMIT = "click_submit"  # irreversible external effect; requires an approval token
    SOCIAL_READ = "social_read"    # daemon-side read-only collection (e.g. instaloader)
    CLOSE = "close"


class BlockKind(str, Enum):
    LOGIN_WALL = "login_wall"
    CHALLENGE = "challenge"
    RATE_LIMIT = "rate_limit"
    POLICY = "policy"


class BridgeError(RuntimeError):
    """Base error for bridge transport and protocol failures."""


class DeviceOffline(BridgeError):
    """The paired device has no live connection."""


class CommandRejected(BridgeError):
    """The daemon refused the command (capability, pacing, or token)."""


class PlatformBlocked(BridgeError):
    """The site itself stopped the read: login wall, challenge, or rate limit.

    This is a limit to surface to the owner, never a condition to evade.
    """

    def __init__(self, kind: BlockKind | str, detail: str) -> None:
        kind = BlockKind(kind)
        super().__init__(f"platform blocked the read ({kind.value}): {detail}")
        self.kind = kind
        self.detail = detail


def is_pc_session(session_id: str) -> bool:
    return session_id.startswith(PC_SESSION_PREFIX)


def split_pc_session(session_id: str) -> tuple[str, str]:
    """Return (device_id, local session name) for a pc.<device>.<name> id."""
    if not is_pc_session(session_id):
        raise ValueError("not a paired-PC session id")
    rest = session_id[len(PC_SESSION_PREFIX):]
    device_id, _, name = rest.partition(".")
    if not device_id or not name:
        raise ValueError("paired-PC session id must be pc.<device_id>.<name>")
    return device_id, name


def make_pc_session(device_id: str, name: str) -> str:
    if not device_id or not name or "." in device_id:
        raise ValueError("invalid device id or session name")
    return f"{PC_SESSION_PREFIX}{device_id}.{name}"


def make_command(kind: CommandKind, args: dict[str, Any], *, command_id: str | None = None) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "id": command_id or secrets.token_hex(16),
        "kind": kind.value,
        "args": args,
    }


def parse_command(raw: dict[str, Any]) -> tuple[str, CommandKind, dict[str, Any]]:
    if raw.get("v") != PROTOCOL_VERSION:
        raise BridgeError(f"unsupported protocol version: {raw.get('v')!r}")
    command_id = raw.get("id")
    if not isinstance(command_id, str) or not command_id:
        raise BridgeError("command is missing an id")
    try:
        kind = CommandKind(raw.get("kind"))
    except ValueError as error:
        raise BridgeError(f"unknown command kind: {raw.get('kind')!r}") from error
    args = raw.get("args")
    if not isinstance(args, dict):
        raise BridgeError("command args must be an object")
    return command_id, kind, args


def make_result(command_id: str, *, ok: bool, result: dict[str, Any] | None = None,
                error: str | None = None, blocked: str | None = None,
                receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"v": PROTOCOL_VERSION, "id": command_id, "ok": bool(ok)}
    if result is not None:
        body["result"] = result
    if error is not None:
        body["error"] = error[:2000]
    if blocked is not None:
        body["blocked"] = BlockKind(blocked).value
    if receipt is not None:
        body["receipt"] = receipt
    return body


def parse_result(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("v") != PROTOCOL_VERSION:
        raise BridgeError(f"unsupported protocol version: {raw.get('v')!r}")
    if raw.get("blocked"):
        raise PlatformBlocked(raw["blocked"], str(raw.get("error", "no detail")))
    if not raw.get("ok"):
        raise CommandRejected(str(raw.get("error", "command failed"))[:2000])
    result = raw.get("result")
    return result if isinstance(result, dict) else {}


def clamp_pacing(value: float | int | None) -> float:
    if value is None:
        return DEFAULT_PACING_SECONDS
    return max(MIN_PACING_SECONDS, min(MAX_PACING_SECONDS, float(value)))


def submit_token(command_secret: str, *, approval_id: str, capture_sha256: str,
                 selector: str, values_digest: str) -> str:
    """One-shot proof that this exact approved click may run on the device."""
    body = "|".join([approval_id, capture_sha256, selector, values_digest])
    return hmac.new(command_secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_submit_token(command_secret: str, *, approval_id: str, capture_sha256: str,
                        selector: str, values_digest: str, token: str) -> bool:
    expected = submit_token(command_secret, approval_id=approval_id, capture_sha256=capture_sha256,
                            selector=selector, values_digest=values_digest)
    return hmac.compare_digest(expected, token)


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
