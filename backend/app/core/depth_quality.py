"""Cross-domain practitioner-grade result quality contract.

The contract does not pretend that deterministic software has measured epistemic
confidence.  It reports input/evidence coverage, unresolved assumptions and the
review gate separately so callers can decide whether a result is usable.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence, Sized
from typing import Any

_DOMAIN_GATES = {
    "clinical": "licensed_clinician_review",
    "legal": "licensed_attorney_review",
    "finance": "qualified_financial_professional_review",
    "education": "educator_and_accessibility_review",
}


def _present(value: Any) -> bool:
    # Equivalent to ``value is None or value == ""`` / container-length checks,
    # but never invokes caller-controlled __eq__ (hostile objects raising
    # arbitrary exceptions must not escape as raw errors).
    if value is None:
        return False
    if isinstance(value, str) and value == "":
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
    try:
        known_domain = domain in _DOMAIN_GATES
    except TypeError:  # unhashable domain (e.g. a list) was a raw escape
        known_domain = False
    if not known_domain:
        raise ValueError(f"unsupported quality domain: {domain}")
    try:
        blank_method = not method.strip()
    except (AttributeError, TypeError, RuntimeError):  # e.g. method=None was a raw escape
        raise ValueError("method, mapping inputs and mapping result are required") from None
    if blank_method or not isinstance(inputs, Mapping) or not isinstance(result, Mapping):
        raise ValueError("method, mapping inputs and mapping result are required")

    def _materialize(name: str, value: Any, *, need_len: bool) -> tuple[list[Any], bool]:
        # Accept exactly what the pre-gate contract accepted: any iterable,
        # including empty mappings/sets and iterators.  Refuse (coded) only
        # what previously crashed: non-iterables and, where len() is needed,
        # unsized iterables.
        if need_len:
            try:
                len(value)
            except (TypeError, RuntimeError):
                raise ValueError(f"{name} must be a sequence of items") from None
        if isinstance(value, Sized):
            try:
                truthy = bool(value)
            except RuntimeError:
                raise ValueError(f"{name} must be a sequence of items") from None
        else:
            truthy = True  # iterators/generators are always truthy, as before
        try:
            items = list(value)
        except (TypeError, RuntimeError):
            raise ValueError(f"{name} must be a sequence of items") from None
        return items, truthy

    ri_items, _ = _materialize("required_inputs", required_inputs, need_len=False)
    ev_items, _ = _materialize("evidence", evidence, need_len=True)
    as_items, as_truthy = _materialize("assumptions", assumptions, need_len=False)
    li_items, _ = _materialize("limitations", limitations, need_len=False)
    try:
        required = list(dict.fromkeys(str(x) for x in ri_items if str(x)))
    except (ValueError, TypeError, RuntimeError):
        raise ValueError("required_inputs must be a sequence of items") from None
    supplied = [key for key in required if _present(inputs.get(key))]
    missing = [key for key in required if key not in supplied]
    cited = []
    for x in ev_items:
        try:
            if x.get("source_url") or x.get("citation") or x.get("authority"):
                cited.append(x)
        except (AttributeError, TypeError, RuntimeError):  # non-mapping entries crashed before
            raise ValueError("evidence entries must be mappings") from None
    uncited = len(ev_items) - len(cited)
    score = 1.0 if not required else round(len(supplied) / len(required), 4)
    uncertainty = "high" if missing or uncited else ("moderate" if as_truthy else "bounded")
    try:
        assumptions_out = list(dict.fromkeys(str(x) for x in as_items if str(x)))
        limitations_out = list(dict.fromkeys(str(x) for x in li_items if str(x)))
    except (ValueError, TypeError, RuntimeError):
        raise ValueError("assumptions and limitations must be sequences of items") from None
    return {
        "method": method,
        "evaluation": {
            "required_inputs": required,
            "supplied_inputs": supplied,
            "missing_inputs": missing,
            "input_completeness": score,
            "evidence_items": len(ev_items),
            "cited_evidence_items": len(cited),
            "uncited_evidence_items": uncited,
            "result_fields": sorted(str(k) for k in result),
            "status": "needs_review" if missing or uncited else "ready_for_review",
        },
        "uncertainty": {
            "level": uncertainty,
            "basis": "coverage_and_declared_assumptions_not_outcome_probability",
            "assumptions": assumptions_out,
            "unknowns": [f"missing input: {x}" for x in missing]
            + ([f"{uncited} evidence item(s) lack a citation"] if uncited else []),
        },
        "limitations": limitations_out,
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
