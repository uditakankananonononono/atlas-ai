"""Non-bypassable action policy for Claire."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ActionRequest, RiskLevel


# GUARANTEE (lexical only): the legacy policy gates at least every payment/comms/hard-block NAME or TAG the runtime
# would gate lexically, because both share these token sets and name_words(). Declaration-metadata gating
# (spends_money / sends_to_person on a registered runtime tool) is runtime-only and has no legacy equivalent.
# LIMIT: matching is on word boundaries, so glued names with no boundary ("sendemail", "chargecard") are not
# recognised by either side; the word sets are a name heuristic, not a capability proof.
# Verb tokens that put a request behind an approval, wherever they appear in a name (shared with the runtime gates).
PAYMENT_TOKENS = frozenset({"purchase", "book", "transfer", "pay", "payment", "spend", "buy", "charge", "refund", "subscribe"})
COMMS_TOKENS = frozenset({"send", "publish", "share", "invite", "submit", "post", "email", "message", "sms", "dm", "reply", "tweet", "notify", "call", "book"})


def name_words(text: object) -> set[str]:
    """Split on space, slash, hyphen, dot, underscore and camelCase boundaries."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(text))
    return {w for w in re.split(r"[^a-z0-9]+", spaced.lower()) if w}


def _joined(text: object) -> str:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(text))
    return "_" + "_".join(w for w in re.split(r"[^a-z0-9]+", spaced.lower()) if w) + "_"


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

    def _declared_tags(self, request: ActionRequest) -> list[str]:
        declared = request.parameters.get("policy_tags", ()) if isinstance(request.parameters, dict) else ()
        if isinstance(declared, (list, tuple, set, frozenset)):
            return [str(item) for item in declared]
        return []

    def _blocked(self, request: ActionRequest) -> str | None:
        found = self._tokens(request) & self.HARD_BLOCKED
        if found:
            return sorted(found)[0]
        # Whole-phrase check on word boundaries, per field: "self_bot_poster" must not slip through
        # because the glued module+action tokenizer split it.
        for text in (request.action, request.module, *self._declared_tags(request)):
            joined = _joined(text)
            for item in sorted(self.HARD_BLOCKED):
                if f"_{item}_" in joined:
                    return item
        return None

    def evaluate(self, request: ActionRequest) -> PolicyDecision:
        blocked = self._blocked(request)
        if blocked:
            return PolicyDecision(False, False, f"hard-blocked capability: {blocked}")
        verb = request.action.lower().replace("-", "_")
        words = name_words(request.action)
        for tag in self._declared_tags(request):
            words |= name_words(tag)
        gated_word = bool(words & (self.APPROVAL_ACTIONS | PAYMENT_TOKENS | COMMS_TOKENS))
        approval = request.risk is RiskLevel.HIGH or verb in self.APPROVAL_ACTIONS or gated_word
        return PolicyDecision(True, approval, "explicit review required" if approval else "allowed")

    def require_allowed(self, request: ActionRequest) -> PolicyDecision:
        decision = self.evaluate(request)
        if not decision.allowed:
            raise PolicyViolation(decision.reason)
        return decision
