from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .lane_models import Draft


@dataclass(frozen=True)
class PolicyFinding:
    code: str
    severity: str
    detail: str


class OutboundPolicy:
    """Pre-send safety checks. Blockers must be cleared before approval."""
    _secret = re.compile(r"(?i)\b(password|api[_ -]?key|secret|recovery code)\s*[:=]\s*\S+")
    _card = re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)")

    def inspect(self, draft: Draft, allowed_domains: Iterable[str] = ()) -> tuple[PolicyFinding, ...]:
        findings: list[PolicyFinding] = []
        if not draft.to:
            findings.append(PolicyFinding("missing_recipient", "block", "Draft has no recipient"))
        allowed = {d.lower().lstrip("@") for d in allowed_domains}
        for address in (*draft.to, *draft.cc):
            if "@" not in address:
                findings.append(PolicyFinding("invalid_recipient", "block", f"Invalid address: {address}"))
            elif allowed and address.rsplit("@", 1)[1].lower() not in allowed:
                findings.append(PolicyFinding("external_recipient", "warn", f"External recipient: {address}"))
        if self._secret.search(draft.body_text):
            findings.append(PolicyFinding("possible_secret", "block", "Body may contain a credential"))
        if self._card.search(draft.body_text):
            findings.append(PolicyFinding("possible_card_number", "block", "Body may contain a payment-card number"))
        if not draft.subject.strip():
            findings.append(PolicyFinding("missing_subject", "warn", "Draft subject is empty"))
        return tuple(findings)

    def assert_sendable(self, draft: Draft, allowed_domains: Iterable[str] = ()) -> tuple[PolicyFinding, ...]:
        findings = self.inspect(draft, allowed_domains)
        blockers = [f.code for f in findings if f.severity == "block"]
        if blockers:
            raise PermissionError("outbound policy blocked draft: " + ", ".join(blockers))
        return findings
