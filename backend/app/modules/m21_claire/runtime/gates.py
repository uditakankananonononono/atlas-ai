from __future__ import annotations
import hashlib, json, re
from dataclasses import dataclass
from typing import Any
from app.modules.m21_claire.models import ActionRequest
from app.modules.m21_claire.policy import ActionPolicy, COMMS_TOKENS as _COMMS_TOKENS, name_words, PAYMENT_TOKENS as _PAYMENT_TOKENS
from .risk import claire_risk
from .types import ToolRisk

PAYMENT, COMMS = "payment", "comms"
# Verb tokens that can only RAISE a tool's gates, whatever the tool declared.


class GateRefused(PermissionError):
    def __init__(self, reason: str, gates: tuple[str, ...], digest: str):
        super().__init__(reason)
        self.reason, self.gates, self.digest = reason, gates, digest


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    actor_id: str
    goal_id: str
    lease_token: str | None = None  # set by the worker from its claim; required to journal non-read effects


@dataclass(frozen=True)
class Classification:
    blocked: bool
    gates: tuple[str, ...]  # sorted; empty = autonomous
    reason: str


def payload_digest(goal_id: str, capability: str, arguments: dict[str, Any]) -> str:
    enc = json.dumps({"goal_id": goal_id, "capability": capability, "arguments": arguments}, sort_keys=True,
                     separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(enc.encode()).hexdigest()


_words = name_words  # one shared implementation (policy.name_words); identity-tested


def _tokens(name: str, arguments: dict[str, Any]) -> set[str]:
    toks = _words(name)
    tags = arguments.get("policy_tags", ()) if isinstance(arguments, dict) else ()
    if isinstance(tags, (list, tuple, set, frozenset)):
        for tag in tags:
            toks |= _words(tag)
    return toks


def require_plain_json(value: Any, _depth: int = 0) -> None:
    """Gated-call arguments must be plain JSON so a digest cannot collide across types (tuple vs list, bytes, etc.)."""
    if _depth > 50:
        raise ValueError("arguments nested too deeply")
    t = type(value)
    if value is None or t in (bool, str, int):
        return
    if t is float:
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("non-finite number")
        return
    if t is list:
        for v in value:
            require_plain_json(v, _depth + 1)
        return
    if t is dict:
        for k, v in value.items():
            if type(k) is not str:
                raise ValueError("non-string key")
            require_plain_json(v, _depth + 1)
        return
    raise ValueError("not plain JSON")


def classify(tool: Any, arguments: dict[str, Any], policy: ActionPolicy | None = None) -> Classification:
    """Classify from the REGISTERED tool. Anything undeclared on a non-read tool takes both gates.
    Names, tags and model labels can only add gates, never remove them."""
    policy = policy or ActionPolicy()
    request = ActionRequest(module="runtime", action=tool.name, parameters=arguments if isinstance(arguments, dict) else {},
                            purpose="runtime tool call", risk=claire_risk(tool.risk))
    decision = policy.evaluate(request)
    if not decision.allowed:
        return Classification(True, (), decision.reason)
    # ActionPolicy._tokens glues module and action ("runtime impersonate") and splits multiword names
    # ("self_bot" -> self, bot), so some standing-no names slip through it. Check on boundaries here.
    normalized = "_" + "_".join(re.split(r"[^a-z0-9]+", tool.name.lower())).strip("_") + "_"
    for item in sorted(policy.HARD_BLOCKED):
        if f"_{item}_" in normalized:
            return Classification(True, (), f"hard-blocked capability: {item}")
    gates: set[str] = set()
    read_only = tool.risk is ToolRisk.READ
    for declared, gate in ((tool.spends_money, PAYMENT), (tool.sends_to_person, COMMS)):
        if declared is True or (declared is None and not read_only):
            gates.add(gate)
    toks = _tokens(tool.name, arguments)
    if toks & _PAYMENT_TOKENS:
        gates.add(PAYMENT)
    if toks & _COMMS_TOKENS:
        gates.add(COMMS)
    # Owner ruling: delete/install/execute/deploy/change_permissions are AUTONOMOUS in this runtime.
    # decision.requires_approval (Claire's older verb gate) is deliberately NOT consulted here.
    return Classification(False, tuple(sorted(gates)), "classified")


class GateEnforcer:
    def __init__(self, ledger: Any, policy: ActionPolicy | None = None):
        self.ledger, self.policy = ledger, policy or ActionPolicy()

    def evaluate(self, tool: Any, arguments: dict[str, Any], principal: Principal | None) -> tuple[tuple[str, ...], str]:
        """Classify without consuming anything. Returns (gates, digest) or raises GateRefused (invalid, blocked, or gated
        with no principal). Consumption is a separate step so a caller can make it atomic with its own reservation."""
        try:
            require_plain_json(arguments)
        except (ValueError, RecursionError):
            raise GateRefused("invalid_arguments", (), "") from None
        c = classify(tool, arguments, self.policy)
        digest = payload_digest(principal.goal_id if principal else "", tool.name, arguments)
        if c.blocked:
            raise GateRefused("blocked", (), digest)
        if c.gates and principal is None:
            raise GateRefused("approval_required", c.gates, digest)
        return c.gates, digest

    def authorize(self, tool: Any, arguments: dict[str, Any], principal: Principal | None) -> None:
        gates, digest = self.evaluate(tool, arguments, principal)
        if gates and not self.ledger.consume_all(principal, tool.name, digest, gates):
            raise GateRefused("approval_required", gates, digest)
