"""Cross-domain practitioner-grade result quality contract.

The contract does not pretend that deterministic software has measured epistemic
confidence.  It reports input/evidence coverage, unresolved assumptions and the
review gate separately so callers can decide whether a result is usable.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_DOMAIN_GATES = {
    "clinical": "licensed_clinician_review",
    "legal": "licensed_attorney_review",
    "finance": "qualified_financial_professional_review",
    "education": "educator_and_accessibility_review",
}


def _present(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, (Mapping, Sequence)) and not isinstance(value, (str, bytes)):
        return len(value) > 0
    return True


def quality_envelope(
    *, domain: str, method: str, inputs: Mapping[str, Any], result: Mapping[str, Any],
    required_inputs: Sequence[str] = (), evidence: Sequence[Mapping[str, Any]] = (),
    assumptions: Sequence[str] = (), limitations: Sequence[str] = (),
) -> dict[str, Any]:
    """Return an auditable quality/uncertainty report without fake probabilities."""
    if domain not in _DOMAIN_GATES:
        raise ValueError(f"unsupported quality domain: {domain}")
    if not method.strip() or not isinstance(inputs, Mapping) or not isinstance(result, Mapping):
        raise ValueError("method, mapping inputs and mapping result are required")
    required = list(dict.fromkeys(str(x) for x in required_inputs if str(x)))
    supplied = [key for key in required if _present(inputs.get(key))]
    missing = [key for key in required if key not in supplied]
    cited = [x for x in evidence if x.get("source_url") or x.get("citation") or x.get("authority")]
    uncited = len(evidence) - len(cited)
    score = 1.0 if not required else round(len(supplied) / len(required), 4)
    uncertainty = "high" if missing or uncited else ("moderate" if assumptions else "bounded")
    return {
        "method": method,
        "evaluation": {
            "required_inputs": required,
            "supplied_inputs": supplied,
            "missing_inputs": missing,
            "input_completeness": score,
            "evidence_items": len(evidence),
            "cited_evidence_items": len(cited),
            "uncited_evidence_items": uncited,
            "result_fields": sorted(str(k) for k in result),
            "status": "needs_review" if missing or uncited else "ready_for_review",
        },
        "uncertainty": {
            "level": uncertainty,
            "basis": "coverage_and_declared_assumptions_not_outcome_probability",
            "assumptions": list(dict.fromkeys(str(x) for x in assumptions if str(x))),
            "unknowns": [f"missing input: {x}" for x in missing]
            + ([f"{uncited} evidence item(s) lack a citation"] if uncited else []),
        },
        "limitations": list(dict.fromkeys(str(x) for x in limitations if str(x))),
        "review_gate": _DOMAIN_GATES[domain],
        "side_effects": "none",
    }


def attach_quality(result: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Attach the contract without replacing method-specific output."""
    if not isinstance(result, dict):
        raise TypeError("method result must be a dictionary")
    if "quality" in result:
        raise ValueError("method result already defines quality")
    return {**result, "quality": quality_envelope(result=result, **kwargs)}
