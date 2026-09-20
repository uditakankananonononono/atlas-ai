from __future__ import annotations

import re
from datetime import timedelta

from .lane_models import EmailMessage, TriageDecision, TriageLabel

_URGENT = ("urgent", "asap", "immediately", "time-sensitive", "deadline", "overdue")
_ACTION = ("please", "could you", "can you", "need you", "action required", "review", "approve", "confirm")
_NEWS = ("unsubscribe", "view in browser", "mailing list", "newsletter")
_SPAM = ("lottery", "crypto giveaway", "wire transfer", "gift card", "act now")
_WAIT = ("waiting for", "following up", "any update", "checking in")


class RuleBasedTriage:
    """Deterministic and explainable baseline; callers can replace it with an ML policy."""

    def classify(self, message: EmailMessage) -> TriageDecision:
        text = f"{message.subject}\n{message.body_text}".lower()
        reasons: list[str] = []
        label = TriageLabel.FYI
        score = .35
        needs_reply = False
        due_at = None
        if self._has(text, _SPAM):
            label, score = TriageLabel.SPAM, .98
            reasons.append("matched spam-risk language")
        elif self._has(text, _NEWS) or message.headers.get("List-Unsubscribe"):
            label, score = TriageLabel.NEWSLETTER, .94
            reasons.append("mailing-list markers present")
        elif self._has(text, _URGENT):
            label, score, needs_reply = TriageLabel.URGENT, .90, True
            reasons.append("matched urgent or deadline language")
            due_at = message.received_at + timedelta(hours=24)
        elif self._has(text, _ACTION) or "?" in text:
            label, score, needs_reply = TriageLabel.ACTION, .78, True
            reasons.append("contains a request or direct question")
        elif self._has(text, _WAIT):
            label, score, needs_reply = TriageLabel.WAITING, .72, True
            reasons.append("contains follow-up language")
        else:
            reasons.append("no request, urgency, or bulk-mail marker found")
        return TriageDecision(message.id, label, score, tuple(reasons), needs_reply, due_at)

    @staticmethod
    def _has(text: str, terms: tuple[str, ...]) -> bool:
        return any(re.search(r"\b" + re.escape(term) + r"\b", text) for term in terms)
