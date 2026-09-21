"""Compliant route planning for GCW tool-integration requirements.

The planner prefers reviewed free APIs, then normal browser or paired-PC UI
operation. It never treats a blocked UI as success. If the only discovered
capability is paid, it proposes a GitHub-backed implementation pipeline rather
than silently buying access. Final submits remain approval gated.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class Route(str, Enum):
    API = "api"
    BROWSER = "browser"
    PAIRED_PC = "paired_pc"


class RouteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route: Route
    name: str = Field(min_length=1)
    available: bool = True
    free: bool = True
    compliant: bool = True
    reviewed: bool = True


class IntegrationRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    tenant_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    routes: list[RouteCandidate] = Field(default_factory=list)
    final_submit: bool = False
    approval_granted: bool = False
    automation_blocked: bool = False
    block_reason: str | None = None
    github_repository: str | None = None
    native_build_allowed: bool = False

    @field_validator("tenant_id", "actor_id")
    @classmethod
    def no_blank_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identity must not be blank")
        return value


ROUTE_ORDER = {Route.API: 0, Route.BROWSER: 1, Route.PAIRED_PC: 2}


def plan_tool_route(row: int, raw: dict[str, Any]) -> dict[str, Any]:
    """Return an auditable plan, not fabricated execution evidence."""
    try:
        request = IntegrationRequest.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"invalid tool-integration request: {exc}") from exc

    audit = {
        "event": "gcw_tool_route_planned",
        "technical_spec_row": row,
        "tenant_id": request.tenant_id,
        "actor_id": request.actor_id,
    }
    isolation_key = f"{request.tenant_id}:{request.actor_id}"
    candidates = [
        item for item in request.routes
        if item.available and item.compliant and item.reviewed
    ]
    candidates.sort(key=lambda item: (not item.free, ROUTE_ORDER[item.route], item.name))
    free = [item for item in candidates if item.free]

    if free:
        selected = free[0]
        if request.automation_blocked and selected.route in {Route.BROWSER, Route.PAIRED_PC}:
            reason = request.block_reason or "site blocked compliant UI automation"
            audit.update(route=selected.route.value, status="blocked", reason=reason)
            return {
                "status": "blocked",
                "selected_route": selected.route.value,
                "selected_adapter": selected.name,
                "failure": reason,
                "honest_completion": False,
                "evidence": [],
                "approval_required": request.final_submit,
                "audit_log": audit,
                "isolation_key": isolation_key,
                "free_first_order": [item.name for item in candidates],
            }
        status = "waiting_approval" if request.final_submit and not request.approval_granted else "ready"
        audit.update(route=selected.route.value, status=status)
        return {
            "status": status,
            "selected_route": selected.route.value,
            "selected_adapter": selected.name,
            "honest_completion": False,
            "evidence": [],
            "approval_required": request.final_submit,
            "approval_granted": request.approval_granted,
            "audit_log": audit,
            "isolation_key": isolation_key,
            "free_first_order": [item.name for item in candidates],
        }

    if candidates and request.native_build_allowed and request.github_repository:
        audit.update(route="native_build_pipeline", status="proposal")
        return {
            "status": "proposal",
            "selected_route": "native_build_pipeline",
            "selected_adapter": None,
            "pipeline": ["discover", "implement", "test", "review", "deploy_after_approval"],
            "github_repository": request.github_repository,
            "paid_route_declined": True,
            "honest_completion": False,
            "evidence": [],
            "approval_required": True,
            "audit_log": audit,
            "isolation_key": isolation_key,
            "free_first_order": [item.name for item in candidates],
        }

    reason = "no reviewed compliant free route is available"
    audit.update(route=None, status="blocked", reason=reason)
    return {
        "status": "blocked",
        "selected_route": None,
        "failure": reason,
        "honest_completion": False,
        "evidence": [],
        "approval_required": request.final_submit,
        "audit_log": audit,
        "isolation_key": isolation_key,
        "free_first_order": [item.name for item in candidates],
    }
