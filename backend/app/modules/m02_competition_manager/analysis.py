"""Cross-source grounding checks for competition application facts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from .models import ExtractedFact


@dataclass(frozen=True)
class GroundingConflict:
    kind: str
    values: tuple[Any, ...]
    source_ids: tuple[str, ...]
    message: str


def grounding_conflicts(facts: Iterable[ExtractedFact]) -> list[GroundingConflict]:
    """Return action-blocking disagreements without attempting to guess a winner."""
    grouped: dict[str, list[ExtractedFact]] = {}
    for fact in facts:
        if fact.kind in {"deadline", "rubric"}:
            grouped.setdefault(fact.kind, []).append(fact)
    conflicts: list[GroundingConflict] = []
    deadlines = grouped.get("deadline", [])
    unique_deadlines: dict[str, list[ExtractedFact]] = {}
    for fact in deadlines: unique_deadlines.setdefault(str(fact.value), []).append(fact)
    if len(unique_deadlines) > 1:
        ordered = sorted(unique_deadlines)
        sources = tuple(sorted({f.evidence.source_id for f in deadlines}))
        conflicts.append(GroundingConflict("deadline", tuple(ordered), sources, "Sources disagree on the application deadline"))

    criteria: dict[str, dict[int, set[str]]] = {}
    for fact in grouped.get("rubric", []):
        label = str(fact.value["criterion"]).strip().casefold()
        criteria.setdefault(label, {}).setdefault(int(fact.value["weight_percent"]), set()).add(fact.evidence.source_id)
    for criterion, weights in sorted(criteria.items()):
        if len(weights) > 1:
            sources = tuple(sorted({source for source_set in weights.values() for source in source_set}))
            conflicts.append(GroundingConflict("rubric", tuple(sorted(weights)), sources, f"Sources disagree on rubric weight for {criterion}"))
    return conflicts


def checklist_dependency_order(items) -> list[str]:
    """Topologically order checklist items, rejecting missing edges and cycles."""
    by_id = {item.id: item for item in items}
    incoming = {item.id: set(item.dependency_ids) for item in items}
    missing = {dep for deps in incoming.values() for dep in deps if dep not in by_id}
    if missing: raise ValueError(f"unknown dependencies: {sorted(missing)}")
    ready = sorted(item_id for item_id, deps in incoming.items() if not deps)
    result: list[str] = []
    while ready:
        item_id = ready.pop(0); result.append(item_id)
        for other_id in sorted(incoming):
            if item_id in incoming[other_id]:
                incoming[other_id].remove(item_id)
                if not incoming[other_id] and other_id not in result and other_id not in ready:
                    ready.append(other_id); ready.sort()
    if len(result) != len(items):
        cyclic = sorted(item_id for item_id, deps in incoming.items() if deps)
        raise ValueError(f"checklist dependency cycle: {cyclic}")
    return result
