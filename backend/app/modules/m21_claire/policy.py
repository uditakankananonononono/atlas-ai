"""Non-bypassable action policy for Claire."""
from __future__ import annotations

from dataclasses import dataclass

from .models import ActionRequest, RiskLevel


class PolicyViolation(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str


class ActionPolicy:
    """Classifies capabilities independently of wording supplied by a caller."""

    HARD_BLOCKED = frozenset({
        "deception", "impersonate", "fabricate_evidence", "piracy", "copyright_bypass",
        "fake_account", "bot_account", "ban_evasion", "credential_stuffing",
        "login_scraping", "self_bot",
    })
    APPROVAL_ACTIONS = frozenset({
        "send", "publish", "share", "delete", "purchase", "book", "install", "execute",
        "submit", "invite", "transfer", "deploy", "change_permissions",
    })

    @staticmethod
    def _tokens(request: ActionRequest) -> set[str]:
        normalized = f"{request.module} {request.action}".lower().replace("-", "_").replace(".", "_")
        tokens = set(normalized.split("_")) | set(normalized.split())
        declared = request.parameters.get("policy_tags", ())
        if isinstance(declared, (list, tuple, set, frozenset)):
            tokens |= {str(item).lower().replace("-", "_") for item in declared}
        return tokens

    def evaluate(self, request: ActionRequest) -> PolicyDecision:
        tokens = self._tokens(request)
        blocked = tokens & self.HARD_BLOCKED
        if blocked:
            return PolicyDecision(False, False, f"hard-blocked capability: {sorted(blocked)[0]}")
        verb = request.action.lower().replace("-", "_")
        approval = request.risk is RiskLevel.HIGH or verb in self.APPROVAL_ACTIONS
        return PolicyDecision(True, approval, "explicit review required" if approval else "allowed")

    def require_allowed(self, request: ActionRequest) -> PolicyDecision:
        decision = self.evaluate(request)
        if not decision.allowed:
            raise PolicyViolation(decision.reason)
        return decision
