"""Email categorisation into the spec's seven labels.

Spec reference: "A fine-tuned BERT model classifies emails into:
opportunity, professor reply, collaboration, newsletter, personal, spam,
action-required."

BertEmailClassifier loads that fine-tuned model lazily (transformers is an
optional heavyweight dep). RuleBasedClassifier is the deterministic fallback
used until a trained checkpoint ships, and in tests.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Protocol

from .schemas import EmailCategory


@dataclass
class ClassifierInput:
    subject: str
    sender: str
    snippet: str
    labels: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Classification:
    category: EmailCategory
    confidence: float
    reasons: list[str] = field(default_factory=list)


class EmailClassifier(Protocol):
    def classify(self, item: ClassifierInput) -> Classification: ...


class ClassifierUnavailableError(RuntimeError):
    pass


_OPPORTUNITY_RE = re.compile(
    r"\b(scholarship|fellowship|internship|hackathon|competition|grant|award|"
    r"application (now )?open|apply (now|by)|deadline to apply|summer program|"
    r"research opportunity|funding opportunity)\b",
    re.IGNORECASE,
)
_COLLABORATION_RE = re.compile(
    r"\b(collaborat\w*|partner(ship| with)?|co-author|coauthor|sponsor(ship)?|"
    r"work together|joint (project|venture|paper)|guest post)\b",
    re.IGNORECASE,
)
_ACTION_RE = re.compile(
    r"\b(action required|please (respond|reply|confirm|review|sign|complete|submit)|"
    r"rsvp|response (required|needed)|due (by|on|date)|overdue|verify your|"
    r"final notice|payment due|signature required|confirm your)\b",
    re.IGNORECASE,
)
_NEWSLETTER_RE = re.compile(
    r"\b(unsubscribe|newsletter|digest|weekly round(?:-| )?up|mailing list)\b",
    re.IGNORECASE,
)
_ACADEMIC_SENDER_RE = re.compile(
    r"(\.edu\b|\.ac\.|prof\.?|dr\.?|university|college|institute)", re.IGNORECASE
)


class RuleBasedClassifier:
    """Deterministic keyword/header classifier. Precedence: spam first,
    then action-required, then the substantive categories, then newsletter,
    then personal as the default."""

    def classify(self, item: ClassifierInput) -> Classification:
        labels = {label.upper() for label in item.labels}
        text = f"{item.subject}\n{item.snippet}"
        reasons: list[str] = []

        if "SPAM" in labels:
            return Classification(EmailCategory.SPAM, 0.99, ["gmail-label:SPAM"])

        scores: dict[EmailCategory, int] = {}

        if _ACTION_RE.search(text):
            scores[EmailCategory.ACTION_REQUIRED] = 2
            reasons.append("action-required keywords")
        if "IMPORTANT" in labels and _ACTION_RE.search(text):
            scores[EmailCategory.ACTION_REQUIRED] = scores.get(EmailCategory.ACTION_REQUIRED, 0) + 1

        if _ACADEMIC_SENDER_RE.search(item.sender) and item.subject.lower().startswith("re:"):
            scores[EmailCategory.PROFESSOR_REPLY] = 3
            reasons.append("academic sender + reply subject")
        elif _ACADEMIC_SENDER_RE.search(item.sender):
            scores[EmailCategory.PROFESSOR_REPLY] = 1
            reasons.append("academic sender")

        if _OPPORTUNITY_RE.search(text):
            scores[EmailCategory.OPPORTUNITY] = 2
            reasons.append("opportunity keywords")

        if _COLLABORATION_RE.search(text):
            scores[EmailCategory.COLLABORATION] = 2
            reasons.append("collaboration keywords")

        newsletter_score = 0
        if "list-unsubscribe" in {k.lower() for k in item.headers}:
            newsletter_score += 2
            reasons.append("List-Unsubscribe header")
        if {"CATEGORY_PROMOTIONS", "CATEGORY_UPDATES"} & labels:
            newsletter_score += 2
            reasons.append("gmail promotions/updates label")
        if _NEWSLETTER_RE.search(text):
            newsletter_score += 1
        if newsletter_score:
            scores[EmailCategory.NEWSLETTER] = newsletter_score

        if not scores:
            return Classification(EmailCategory.PERSONAL, 0.6, ["no signals; default personal"])

        best = max(scores.items(), key=lambda kv: kv[1])
        confidence = min(0.5 + 0.15 * best[1], 0.95)
        return Classification(best[0], round(confidence, 2), reasons)


class BertEmailClassifier:
    """Fine-tuned BERT classifier per spec. The model path must point at a
    checkpoint whose label set is the seven EmailCategory values. transformers
    is imported lazily so the rest of the module needs no heavyweight deps."""

    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        self._pipeline = None

    def _load(self) -> None:
        if self._pipeline is not None:
            return
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise ClassifierUnavailableError(
                "transformers is not installed; use RuleBasedClassifier or install the ML extras"
            ) from exc
        self._pipeline = pipeline("text-classification", model=self.model_path)

    def classify(self, item: ClassifierInput) -> Classification:
        self._load()
        text = f"{item.subject}\n{item.snippet}"[:2000]
        result = self._pipeline(text, truncation=True)[0]
        label = result["label"].lower().replace("-", "_").replace(" ", "_")
        try:
            category = EmailCategory(label)
        except ValueError as exc:
            raise ClassifierUnavailableError(
                f"model returned unknown label {result['label']!r}; checkpoint must emit the seven spec labels"
            ) from exc
        return Classification(category, float(result["score"]), ["bert:" + result["label"]])


def configured_classifier() -> EmailClassifier:
    """Select the production classifier explicitly and fail closed on bad config.

    ATLAS_EMAIL_CLASSIFIER=bert requires ATLAS_EMAIL_BERT_MODEL to identify a
    verified local or Hugging Face checkpoint. No model is downloaded merely
    by importing the service, and no unverified training labels are fabricated.
    """
    selected=os.getenv("ATLAS_EMAIL_CLASSIFIER", "rules").strip().lower()
    if selected in {"rules","rule","deterministic"}:
        return RuleBasedClassifier()
    if selected in {"bert","transformers"}:
        model=os.getenv("ATLAS_EMAIL_BERT_MODEL", "").strip()
        if not model:
            raise ClassifierUnavailableError("ATLAS_EMAIL_BERT_MODEL is required when ATLAS_EMAIL_CLASSIFIER=bert")
        return BertEmailClassifier(model)
    raise ClassifierUnavailableError(f"unsupported email classifier: {selected}")
