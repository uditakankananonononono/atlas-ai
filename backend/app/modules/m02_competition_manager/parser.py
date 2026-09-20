"""Deterministic, evidence-preserving competition document parser."""
from __future__ import annotations

import re
from datetime import datetime, time, timezone
from typing import Iterable, Optional

from .models import ExtractedFact, SourceEvidence

_MONTHS = {
    name.lower(): number
    for number, name in enumerate(
        ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    ) if name
}
_MONTHS.update({name[:3]: number for name, number in list(_MONTHS.items())})

_MATERIAL_TERMS = (
    "essay", "resume", "cv", "transcript", "recommendation", "portfolio",
    "video", "abstract", "proposal", "proof of enrollment", "identity document",
)
_RULE_MARKERS = re.compile(r"\b(?:must|shall|required|eligible|ineligible|may not|cannot|at least|no more than)\b", re.I)
_RUBRIC = re.compile(r"(?P<label>[A-Za-z][A-Za-z /&-]{2,60})\s*[:\-]\s*(?P<weight>\d{1,3})\s*%")
_DATE_PATTERNS = (
    re.compile(r"\b(?P<month>January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[.]?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?[,]?\s+(?P<year>20\d{2})(?:\s+(?:at\s+)?(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)?)?\b", re.I),
    re.compile(r"\b(?P<year>20\d{2})[-/](?P<month_num>\d{1,2})[-/](?P<day>\d{1,2})(?:[ T](?P<hour>\d{1,2}):(?P<minute>\d{2}))?\b"),
)


def _evidence(source_id: str, text: str, start: int, end: int, url: Optional[str]) -> SourceEvidence:
    return SourceEvidence(source_id=source_id, quote=text[start:end].strip(), start=start, end=end, url=url)


def _lines(text: str) -> Iterable[tuple[str, int, int]]:
    pos = 0
    for raw in text.splitlines(keepends=True):
        line = raw.strip()
        if line:
            left = len(raw) - len(raw.lstrip())
            start = pos + left
            yield line, start, start + len(line)
        pos += len(raw)


def parse_competition_document(text: str, source_id: str, *, url: Optional[str] = None, default_timezone=timezone.utc) -> list[ExtractedFact]:
    if not text.strip():
        raise ValueError("source text cannot be empty")
    if not source_id.strip():
        raise ValueError("source_id cannot be empty")
    facts: list[ExtractedFact] = []
    seen: set[tuple[str, str, int]] = set()

    def add(kind: str, value, start: int, end: int, confidence: float = 1.0) -> None:
        key = (kind, repr(value), start)
        if key not in seen:
            seen.add(key)
            facts.append(ExtractedFact(kind, value, _evidence(source_id, text, start, end, url), confidence))

    for line, start, end in _lines(text):
        lowered = line.lower()
        if _RULE_MARKERS.search(line):
            add("rule", line.lstrip("-*• \t"), start, end, 0.9)
        for material in _MATERIAL_TERMS:
            if re.search(rf"\b{re.escape(material)}s?\b", lowered):
                required = bool(re.search(r"\b(required|must|submit|upload|include|provide)\b", lowered))
                add("material", {"name": material, "required": required}, start, end, 0.92 if required else 0.78)
        for match in _RUBRIC.finditer(line):
            weight = int(match.group("weight"))
            if weight <= 100:
                add("rubric", {"criterion": match.group("label").strip(), "weight_percent": weight}, start + match.start(), start + match.end(), 0.98)

    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            before = text[max(0, match.start() - 80):match.start()].lower()
            after = text[match.end():min(len(text), match.end() + 40)].lower()
            if not re.search(r"deadline|due|close|submit|application", before + after):
                continue
            gd = match.groupdict()
            month = int(gd.get("month_num") or _MONTHS[gd["month"].lower().rstrip(".")[:3]])
            hour = int(gd.get("hour") or 23)
            minute = int(gd.get("minute") or 59)
            ampm = (gd.get("ampm") or "").lower()
            if ampm == "pm" and hour != 12: hour += 12
            if ampm == "am" and hour == 12: hour = 0
            try:
                parsed = datetime(int(gd["year"]), month, int(gd["day"]), hour, minute, tzinfo=default_timezone)
            except ValueError:
                continue
            add("deadline", parsed.isoformat(), match.start(), match.end(), 0.96)
    return facts


def validate_rubric(facts: list[ExtractedFact]) -> dict[str, object]:
    rubric = [f for f in facts if f.kind == "rubric"]
    total = sum(int(f.value["weight_percent"]) for f in rubric)
    return {"total_weight_percent": total, "complete": total == 100, "criteria_count": len(rubric)}
