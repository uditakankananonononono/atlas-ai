from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field
from .types import RunReport


class ToolReceiptCriterion(BaseModel):
    """Declared at intake, frozen with the goal: needs >= min_count successful receipts from `tool`."""
    kind: Literal["tool_receipt"] = "tool_receipt"
    tool: str = Field(min_length=1, max_length=100)
    min_count: int = Field(default=1, ge=1, le=100)


class Verdict(BaseModel):
    accepted: bool
    results: list[dict[str, Any]]


def evaluate(criteria: list[dict[str, Any]], report: RunReport) -> Verdict:
    """Acceptance is decided from tool receipts only. The model's final text never counts."""
    results = []
    if report.stop_reason != "final":
        return Verdict(accepted=False, results=[{"criterion": c, "met": False, "why": f"run ended: {report.stop_reason}"} for c in criteria])
    for raw in criteria:
        c = ToolReceiptCriterion.model_validate(raw)
        n = sum(1 for r in report.receipts if r.ok and r.tool == c.tool)
        results.append({"criterion": c.model_dump(), "met": n >= c.min_count, "observed": n})
    return Verdict(accepted=bool(results) and all(r["met"] for r in results), results=results)
