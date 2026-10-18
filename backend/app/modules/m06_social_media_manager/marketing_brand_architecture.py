"""Row 404 brand architecture: deterministic organization of caller-provided
brands/products into a disclosed structure, with honesty guards.

Honesty rules enforced in code, not by prompt:

1. Entities and parent links come only from the caller. The engine never
   invents brands, products, or parents, and never silently repairs bad
   input: a parent reference that names no provided entity, or a parent
   cycle, is flagged in ``issues`` and left as-is.
2. Structure is caller-provided (validated against the disclosed set) or
   inferred from the provided parent links via a disclosed rule; the basis
   is marked either way.
3. Pairwise relationships are derived mechanically from the provided parent
   links (parent-child, siblings, same-house, separate-houses), disclosed as
   derivation, not brand research.
4. No external effects: pure function over the input mapping.
"""

from __future__ import annotations

import re
from typing import Any

_ALLOWED_STRUCTURES = ("branded-house", "house-of-brands", "hybrid")
_MAX_ENTITIES = 20  # pairwise relationships grow quadratically; disclose the cap

_WHITESPACE = re.compile(r"\s+")


def _norm_str(value: Any, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{what} must be strings, got {type(value).__name__}")
    out = _WHITESPACE.sub(" ", value.strip())
    if not out:
        raise ValueError(f"{what} must be non-empty")
    return out


def _normalize_entities(raw: list[Any]) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            name, parent = _norm_str(item, "entities"), None
        elif isinstance(item, dict):
            name = _norm_str(item.get("name"), "entities")
            parent_raw = item.get("parent")
            parent = (
                _norm_str(parent_raw, "entity parents") if parent_raw else None
            )
        else:
            raise ValueError(
                f"entities must be strings or mappings, got {type(item).__name__}"
            )
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        entities.append({"name": name, "parent": parent})
    return entities


def _roots(entities: list[dict[str, Any]], parent_of: dict[str, str]) -> dict[str, str]:
    """Root of each entity by walking provided parent links; cycles stop at
    the repeated node and are reported by the caller."""
    out: dict[str, str] = {}
    for e in entities:
        node, visited = e["name"], {e["name"].lower()}
        while parent_of.get(node.lower()):
            node = parent_of[node.lower()]
            if node.lower() in visited:
                break  # cycle; flagged separately
            visited.add(node.lower())
        out[e["name"]] = node
    return out


def build_brand_architecture(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deterministic brand-architecture artifact.

    Identical input produces identical output, including ordering.
    """
    facts = inputs.get("facts") or {}
    notes: list[str] = []
    issues: list[str] = []

    raw_entities = facts.get("entities") or []
    entities = _normalize_entities(raw_entities)
    capped = False
    if len(entities) > _MAX_ENTITIES:
        entities = entities[:_MAX_ENTITIES]
        capped = True
        notes.append(
            f"capped at {_MAX_ENTITIES} entities (pairwise relationships "
            "grow quadratically)"
        )

    names = {e["name"].lower() for e in entities}
    parent_of = {
        e["name"].lower(): e["parent"] for e in entities if e["parent"]
    }
    for e in entities:
        if e["parent"] and e["parent"].lower() not in names:
            issues.append(
                f"{e['name']!r} references parent {e['parent']!r}, which is "
                "not in the provided entity list"
            )

    # Cycle detection over provided links.
    for e in entities:
        node, visited = e["name"], set()
        while parent_of.get(node.lower()):
            node = parent_of[node.lower()]
            if node.lower() in visited:
                issues.append(
                    f"parent cycle detected through {node!r}; relationships "
                    "for the cycle are computed up to the repeat"
                )
                break
            visited.add(node.lower())

    roots = _roots(entities, parent_of)
    distinct_roots = {r.lower() for r in roots.values()}

    provided_structure = facts.get("structure")
    if provided_structure:
        structure = _norm_str(provided_structure, "structure")
        if structure not in _ALLOWED_STRUCTURES:
            raise ValueError(
                f"structure must be one of {_ALLOWED_STRUCTURES}, got {structure!r}"
            )
        basis = "caller-provided"
    elif not entities:
        structure = "branded-house"
        basis = "default: no entities provided"
    elif len(distinct_roots) == 1 and any(parent_of.values()):
        structure = "branded-house"
        basis = "inferred: single root with provided parent links"
    elif not parent_of:
        structure = "house-of-brands"
        basis = "inferred: no provided parent links"
    else:
        structure = "hybrid"
        basis = "inferred: multiple roots with some provided parent links"

    relationships: list[dict[str, str]] = []
    for i, a in enumerate(entities):
        for b in entities[i + 1:]:
            if a["parent"] and a["parent"].lower() == b["name"].lower():
                rel = "parent-child"
            elif b["parent"] and b["parent"].lower() == a["name"].lower():
                rel = "parent-child"
            elif a["parent"] and b["parent"] and a["parent"].lower() == b["parent"].lower():
                rel = "siblings"
            elif roots[a["name"]].lower() == roots[b["name"]].lower():
                rel = "same-house"
            else:
                rel = "separate-houses"
            relationships.append({"a": a["name"], "b": b["name"], "relationship": rel})

    migration_notes = [str(n) for n in (facts.get("migration_notes") or [])]
    if not entities:
        notes.append("no entities provided; nothing to organize")
    notes.append(
        "entities and parent links come only from the caller; dangling "
        "parents and cycles are flagged in issues, never silently repaired"
    )

    return {
        "structure": structure,
        "structure_basis": basis,
        "entities": entities,
        "relationships": relationships,
        "migration_notes": migration_notes,
        "roots": sorted({e["name"] for e in entities if roots[e["name"]].lower() == e["name"].lower() or e["name"].lower() not in parent_of}),
        "orphan_count": sum(1 for e in entities[1:] if not e["parent"]),
        "issues": issues,
        "notes": notes,
    }
