"""Action-item extraction per the spec output schema [{action, deadline,
related_entity}]. Primary path is an injected LLM (app.core.providers.generate
style); output is JSON-validated against the ActionItem schema with one
retry, then a deterministic heuristic fallback so ingestion never hard-fails
on model noise.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Awaitable, Callable

from .schemas import ActionItem

GenerateFn = Callable[[str, str, str | None], Awaitable[tuple[str, str]]]

_PROMPT = (
    "Extract action items from this email. Return ONLY a JSON array with the "
    'shape [{{"action": str, "deadline": ISO-8601 datetime or null, '
    '"related_entity": str or null}}]. Extract at most 5 items. If there are no '
    "action items, return [].\n"
    "Subject: {subject}\nBody: {body}\nToday: {today}"
)

_RETRY_PROMPT = (
    "Your previous output was not valid JSON matching "
    '[{{"action": str, "deadline": ISO-8601 or null, "related_entity": str or null}}]. '
    "Return ONLY the corrected JSON array, no prose.\nPrevious output: {bad}"
)

_VERB_RE = re.compile(
    r"\b(submit|send|complete|sign|register|review|confirm|pay|upload|fill|return|"
    r"schedule|book|respond|reply|verify|upload|attach|provide|finish)\b",
    re.IGNORECASE,
)
_DEADLINE_RE = re.compile(
    r"\b(?:by|before|due(?: date)?(?: is)?|deadline(?: is)?|no later than)\s+"
    r"([A-Z][a-z]+ \d{1,2}(?:, \d{4})?|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:next |this )?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|"
    r"tomorrow|end of (?:day|week|month)|EOD|EOW)\b",
    re.IGNORECASE,
)


def _parse_deadline(text: str) -> datetime | None:
    try:
        import dateparser
    except ImportError:
        return None
    parsed = dateparser.parse(
        text, settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": True}
    )
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_action_json(text: str) -> list[ActionItem]:
    """Validate model output against the spec schema; raise ValueError if not."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned.strip())
    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("action extraction output must be a JSON array")
    return [ActionItem.model_validate(item) for item in data][:5]


async def extract_actions(
    llm_generate: GenerateFn,
    *,
    provider: str,
    model: str | None,
    subject: str,
    body: str,
) -> list[ActionItem]:
    """LLM extraction with schema validation, one retry, heuristic fallback."""
    prompt = _PROMPT.format(subject=subject, body=body[:6000], today=datetime.now(timezone.utc).date())
    _, first = await llm_generate(prompt, provider, model)
    try:
        return parse_action_json(first)
    except (ValueError, KeyError):
        pass
    _, second = await llm_generate(_RETRY_PROMPT.format(bad=first[:2000]), provider, model)
    try:
        return parse_action_json(second)
    except (ValueError, KeyError):
        return heuristic_extract(subject, body)


def heuristic_extract(subject: str, body: str) -> list[ActionItem]:
    """Deterministic fallback: imperative sentences plus deadline phrases."""
    items: list[ActionItem] = []
    text = f"{subject}. {body}"
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        sentence = sentence.strip()
        if not sentence or len(sentence) < 8 or len(items) >= 5:
            continue
        if not _VERB_RE.search(sentence):
            continue
        deadline = None
        match = _DEADLINE_RE.search(sentence)
        if match:
            deadline = _parse_deadline(match.group(1))
        items.append(ActionItem(action=sentence[:400], deadline=deadline, related_entity=None))
    return items
