"""Row 403 positioning: deterministic positioning statement and grounded
differentiators from caller-provided facts, with honesty guards.

Honesty rules enforced in code, not by prompt:

1. The positioning statement is caller-provided or assembled from
   caller-provided audience/brand/category/benefit/reason facts via the
   disclosed spec template; missing inputs are explicit
   [TO BE PROVIDED: ...] slots, never invented positioning.
2. Every differentiator is grounded in a caller-provided fact: only claims
   the caller backed with evidence are listed, each carrying its evidence.
   Claims without evidence are named in ``ungrounded_claims`` instead of
   being silently dropped or silently promoted.
3. Reasons to believe are exactly the caller-provided evidence behind the
   grounded differentiators - nothing else.
4. No external effects: pure function over the input mapping.
"""

from __future__ import annotations

import re
from typing import Any

_WHITESPACE = re.compile(r"\s+")


def _norm_str(value: Any, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{what} must be strings, got {type(value).__name__}")
    out = _WHITESPACE.sub(" ", value.strip())
    if not out:
        raise ValueError(f"{what} must be non-empty")
    return out


def build_positioning(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deterministic positioning artifact.

    Identical input produces identical output, including ordering.
    """
    facts = inputs.get("facts") or {}
    notes: list[str] = []

    provided_statement = facts.get("statement")
    if isinstance(provided_statement, str) and provided_statement.strip():
        statement = _WHITESPACE.sub(" ", provided_statement.strip())
        statement_basis = "caller-provided"
    else:
        fields = {
            "audience": facts.get("audience"),
            "brand": facts.get("brand"),
            "category": facts.get("category"),
            "benefit": facts.get("benefit"),
            "reason": facts.get("reason"),
        }
        if any(fields.values()):
            bound = {
                k: (str(v).strip() if v else f"[TO BE PROVIDED: {k}]")
                for k, v in fields.items()
            }
            statement = (
                f"For {bound['audience']}, {bound['brand']} is the "
                f"{bound['category']} that {bound['benefit']} because "
                f"{bound['reason']}"
            )
            statement_basis = "derived from disclosed spec template"
        else:
            statement = "TO BE PROVIDED"
            statement_basis = "no inputs to derive from"

    category = facts.get("category")
    category_out = (
        _norm_str(category, "category") if category else "TO BE PROVIDED"
    )

    grounded: list[dict[str, Any]] = []
    ungrounded: list[str] = []
    for raw in facts.get("claims") or []:
        if isinstance(raw, str):
            ungrounded.append(_norm_str(raw, "claims"))
        elif isinstance(raw, dict):
            claim = _norm_str(raw.get("claim") or raw.get("name"), "claims")
            evidence = raw.get("evidence")
            if evidence:
                grounded.append({"claim": claim, "evidence": str(evidence)})
            else:
                ungrounded.append(claim)
        else:
            raise ValueError(
                f"claims must be strings or mappings, got {type(raw).__name__}"
            )

    if ungrounded:
        notes.append(
            f"{len(ungrounded)} claim(s) lacked provided evidence and are "
            "listed under ungrounded_claims, not promoted to differentiators"
        )
    notes.append(
        "every differentiator is grounded in a caller-provided fact; the "
        "engine never invents differentiators or evidence"
    )

    return {
        "statement": statement,
        "statement_basis": statement_basis,
        "category": category_out,
        "differentiators": grounded,
        "reasons_to_believe": [g["evidence"] for g in grounded],
        "ungrounded_claims": ungrounded,
        "notes": notes,
    }
