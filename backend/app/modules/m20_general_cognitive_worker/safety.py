"""Safety and alignment for the GCW (spec 4.4).

Three layers:
1. Constitutional rules: hard-coded checks every action must pass. These
   encode the four permanent nos (no deception/authorship faking, no piracy
   or credential theft, no bots/fake engagement, no login scraping or
   ToS-violating extraction) plus the spec's examples (never initiate
   financial transactions, never share private data without approval).
2. Approval gating: externally visible and irreversible actions pause for
   the Human Approval Center (Module 0) through the ApprovalGate protocol.
3. Sandbox policy: code execution is constrained to allowed hosts and a
   per-project filesystem scope; the executor itself is injected.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol, runtime_checkable

from .schemas import ApprovalGateDecision, ApprovalGateRequest, Risk


@dataclass
class RuleViolation:
    rule_id: str
    reason: str


# A constitutional rule returns a violation reason string, or None when the
# action is clean under that rule.
ConstitutionalRule = tuple[str, Callable[[str, dict[str, Any]], str | None]]


def _payload_text(payload: dict[str, Any]) -> str:
    return " ".join(str(v).lower() for v in payload.values())


def _check_deception(action_type: str, payload: dict[str, Any]) -> str | None:
    text = f"{action_type} {_payload_text(payload)}"
    markers = (
        "impersonate", "fake identity", "forge signature", "ghostwrite as",
        "pretend to be", "lie to", "deceive", "evade ai detection",
        "ai-detector evasion", "fake authorship",
    )
    for marker in markers:
        if marker in text:
            return f"deception/authorship faking marker: {marker!r}"
    return None


def _check_piracy(action_type: str, payload: dict[str, Any]) -> str | None:
    text = f"{action_type} {_payload_text(payload)}"
    markers = (
        "pirate", "crack", "keygen", "bypass paywall", "steal credential",
        "credential theft", "stolen password", "leaked database",
    )
    for marker in markers:
        if marker in text:
            return f"piracy/credential-theft marker: {marker!r}"
    return None


def _check_inauthentic(action_type: str, payload: dict[str, Any]) -> str | None:
    text = f"{action_type} {_payload_text(payload)}"
    markers = (
        "fake account", "bot account", "astroturf", "fake review",
        "fake followers", "engagement bot", "vote brigade", "sockpuppet",
    )
    for marker in markers:
        if marker in text:
            return f"inauthentic-behavior marker: {marker!r}"
    return None


def _check_scraping(action_type: str, payload: dict[str, Any]) -> str | None:
    text = f"{action_type} {_payload_text(payload)}"
    markers = (
        "login scraping", "logged-in scraping", "behind login", "rotate proxy",
        "rotating residential", "evade rate limit", "captcha bypass",
        "scrape private",
    )
    for marker in markers:
        if marker in text:
            return f"ToS-violating-extraction marker: {marker!r}"
    return None


FINANCIAL_ACTION_TYPES = {"payment", "purchase", "transfer", "book_paid", "subscribe_paid"}
PRIVATE_DATA_ACTION_TYPES = {"share_private_data", "export_contacts", "send_private_document"}


class ConstitutionalRules:
    """Hard-coded rule set checked before every dispatched action."""

    def __init__(self, extra_rules: list[ConstitutionalRule] | None = None) -> None:
        self.rules: list[ConstitutionalRule] = [
            ("no-deception", _check_deception),
            ("no-piracy", _check_piracy),
            ("no-inauthentic-engagement", _check_inauthentic),
            ("no-tos-violating-extraction", _check_scraping),
        ]
        self.rules.extend(extra_rules or [])

    def check(self, action_type: str, payload: dict[str, Any]) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for rule_id, predicate in self.rules:
            reason = predicate(action_type, payload)
            if reason:
                violations.append(RuleViolation(rule_id=rule_id, reason=reason))
        return violations


def requires_approval(action_type: str, risk: Risk, payload: dict[str, Any]) -> bool:
    """Spec 4.4: externally visible actions always gate; money and private
    data gate even when a caller mislabels their risk tier."""
    if risk in (Risk.EXTERNAL, Risk.IRREVERSIBLE):
        return True
    if action_type in FINANCIAL_ACTION_TYPES or action_type in PRIVATE_DATA_ACTION_TYPES:
        return True
    if payload.get("externally_visible"):
        return True
    return False


@runtime_checkable
class ApprovalGate(Protocol):
    """Module 0 (Human Approval Center) as seen by the GCW."""

    def request(self, request: ApprovalGateRequest) -> str: ...

    def decision(self, approval_id: str) -> ApprovalGateDecision: ...


class InMemoryApprovalGate:
    """Dev/test gate. Production binds Module 0's durable center."""

    def __init__(self, auto_decision: ApprovalGateDecision | None = None) -> None:
        self.requests: dict[str, ApprovalGateRequest] = {}
        self.decisions: dict[str, ApprovalGateDecision] = {}
        self.auto_decision = auto_decision

    def request(self, request: ApprovalGateRequest) -> str:
        self.requests[request.id] = request
        self.decisions[request.id] = self.auto_decision or ApprovalGateDecision.PENDING
        return request.id

    def decide(self, approval_id: str, decision: ApprovalGateDecision) -> None:
        if approval_id not in self.requests:
            raise KeyError(approval_id)
        self.decisions[approval_id] = decision

    def decision(self, approval_id: str) -> ApprovalGateDecision:
        return self.decisions.get(approval_id, ApprovalGateDecision.PENDING)


@dataclass
class SandboxPolicy:
    """Execution sandbox boundaries (spec 4.4)."""

    allowed_hosts: frozenset[str] = frozenset()
    filesystem_root: str = ""
    network_enabled: bool = False
    max_runtime_seconds: int = 120

    def allows_host(self, host: str) -> bool:
        if not self.network_enabled:
            return False
        return host in self.allowed_hosts

    def allows_path(self, path: str) -> bool:
        if not self.filesystem_root:
            return False
        normalized = path.rstrip("/")
        root = self.filesystem_root.rstrip("/")
        return normalized == root or normalized.startswith(root + "/")


class SafetyGate:
    """Single entry point the dispatcher consults before any action runs."""

    def __init__(
        self,
        rules: ConstitutionalRules | None = None,
        approvals: ApprovalGate | None = None,
        sandbox: SandboxPolicy | None = None,
    ) -> None:
        self.rules = rules or ConstitutionalRules()
        self.approvals = approvals or InMemoryApprovalGate()
        self.sandbox = sandbox or SandboxPolicy()

    def preflight(
        self,
        action_type: str,
        risk: Risk,
        payload: dict[str, Any],
        *,
        task_id: str | None = None,
        summary: str = "",
        granted_approval_id: str | None = None,
    ) -> tuple[bool, str | None, list[RuleViolation]]:
        """Returns (may_proceed, approval_id_or_none, violations).

        Constitutional violations block outright. Approval-required actions
        file a request and do not proceed until the gate approves. A granted
        approval id (Module 0's exact-effect token) satisfies the gate once
        for the reviewed action.
        """
        violations = self.rules.check(action_type, payload)
        if violations:
            return False, None, violations
        if granted_approval_id is not None:
            decision = self.approvals.decision(granted_approval_id)
            if decision == ApprovalGateDecision.APPROVED:
                return True, granted_approval_id, []
            return False, granted_approval_id, []
        if requires_approval(action_type, risk, payload):
            request = ApprovalGateRequest(
                task_id=task_id, action_type=action_type,
                summary=summary or action_type, payload=payload, risk=risk,
            )
            approval_id = self.approvals.request(request)
            decision = self.approvals.decision(approval_id)
            return decision == ApprovalGateDecision.APPROVED, approval_id, []
        return True, None, []
