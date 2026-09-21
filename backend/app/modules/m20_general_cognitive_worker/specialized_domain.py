"""Tenant-scoped executive cognition facade for specialized-domain rows 1310-1559.

This module does not replace the domain engines. It gives Module 20 one uniform,
reviewable contract over their deterministic algorithms while preserving each engine's
validation and evidence requirements. Calls are pure: no trade, grade, enrollment,
physical test, or other external action is performed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

from app.modules.m12_ai_research_lab.education_support import (
    FEATURES as EDUCATION_ADVANCED_ROWS,
    education_support,
)
from app.modules.m16_executive_dashboard import analysis as executive_analysis
from app.modules.m16_executive_dashboard.finance_core import ROWS as FINANCE_ROWS

from .education import NAME_TO_ROW as EDUCATION_FOUNDATION_ROWS, execute as education_execute
from .engineering_1510_1559 import METHODS as ENGINEERING_METHODS, engineering_support_1510_1559

Domain = Literal["finance", "education", "engineering"]

ROW_TO_FINANCE = {row: method for method, row in FINANCE_ROWS.items()}
ROW_TO_FOUNDATION_EDUCATION = {row: method for method, row in EDUCATION_FOUNDATION_ROWS.items()}
ROW_TO_ENGINEERING = {1510 + index: method for index, method in enumerate(ENGINEERING_METHODS)}
SUPPORTED_ROWS = frozenset(
    (*ROW_TO_FINANCE, *ROW_TO_FOUNDATION_EDUCATION, *EDUCATION_ADVANCED_ROWS, *ROW_TO_ENGINEERING)
)
EXPECTED_ROWS = frozenset((*range(1310, 1360), *range(1410, 1560)))
if SUPPORTED_ROWS != EXPECTED_ROWS:  # import-time guard against silent ownership gaps
    raise RuntimeError(f"specialized-domain registry mismatch: {sorted(EXPECTED_ROWS ^ SUPPORTED_ROWS)}")


class SpecializedDomainError(ValueError):
    """Invalid row, tenant scope, or domain input."""


@dataclass(frozen=True)
class TenantScope:
    tenant_id: str
    actor_id: str

    @classmethod
    def checked(cls, tenant_id: str, actor_id: str) -> "TenantScope":
        tenant, actor = tenant_id.strip(), actor_id.strip()
        if not tenant or not actor:
            raise SpecializedDomainError("tenant_id and actor_id are required")
        if len(tenant) > 128 or len(actor) > 128:
            raise SpecializedDomainError("tenant_id and actor_id must be at most 128 characters")
        return cls(tenant, actor)


@dataclass(frozen=True)
class Evaluation:
    status: Literal["computed", "draft_for_review"]
    checks: tuple[str, ...]
    human_review_required: bool
    externally_verified: bool


@dataclass(frozen=True)
class Uncertainty:
    level: Literal["not_quantified", "model_reported"]
    drivers: tuple[str, ...]
    input_evidence_only: bool


@dataclass(frozen=True)
class SpecializedDomainResult:
    row_id: int
    domain: Domain
    capability: str
    tenant_id: str
    actor_id: str
    result: Mapping[str, Any]
    evaluation: Evaluation
    uncertainty: Uncertainty
    assumptions: tuple[str, ...]
    limits: tuple[str, ...]
    side_effects: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SpecializedDomainError(f"{name} must be an object")
    return value


def _finance(row_id: int, data: dict[str, Any], options: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    method = ROW_TO_FINANCE[row_id]
    seed = options.get("seed", 0)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise SpecializedDomainError("options.seed must be an integer")
    params = _mapping(options.get("params", {}), "options.params")
    return method, executive_analysis.run(method, data, params, seed=seed)


def _education(row_id: int, data: dict[str, Any], _options: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if row_id in ROW_TO_FOUNDATION_EDUCATION:
        method = ROW_TO_FOUNDATION_EDUCATION[row_id]
        return method, education_execute(method, data)
    return EDUCATION_ADVANCED_ROWS[row_id], education_support(row_id, data)


def _engineering(row_id: int, data: dict[str, Any], _options: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    method = ROW_TO_ENGINEERING[row_id]
    return method, engineering_support_1510_1559(method, data)


def analyze_specialized_domain(
    *, row_id: int, data: dict[str, Any], tenant_id: str, actor_id: str,
    options: dict[str, Any] | None = None,
) -> SpecializedDomainResult:
    """Run one registered algorithm inside an explicit tenant and actor scope."""
    scope = TenantScope.checked(tenant_id, actor_id)
    if isinstance(row_id, bool) or not isinstance(row_id, int) or row_id not in SUPPORTED_ROWS:
        raise SpecializedDomainError(f"unsupported specialized-domain row: {row_id}")
    payload = _mapping(data, "data")
    opts = _mapping(options or {}, "options")

    if row_id in ROW_TO_FINANCE:
        domain: Domain = "finance"
        capability, raw = _finance(row_id, payload, opts)
        result = _mapping(raw.get("output"), "finance output")
        checks = tuple(sorted(result))
        assumptions = tuple(raw.get("assumptions", ()))
        limits = tuple(raw.get("method_limits", raw.get("limits", ())))
        drivers = ("caller-supplied financial inputs", "model assumptions", "market and accounting regime")
    elif row_id < 1510:
        domain = "education"
        capability, raw = _education(row_id, payload, opts)
        result = _mapping(raw.get("result"), "education result")
        source_evaluation = raw.get("evaluation", {})
        checks = tuple(source_evaluation.get("criteria", source_evaluation.get("review_checks", sorted(result))))
        assumptions = ()
        limits = ("No autonomous grading, credential, enrollment, diagnosis, or learner-record change.",)
        drivers = tuple(raw.get("uncertainty", {}).get("drivers", ("learner context", "instrument validity")))
    else:
        domain = "engineering"
        capability, raw = _engineering(row_id, payload, opts)
        result = _mapping(raw.get("result"), "engineering result")
        checks = tuple(raw.get("evaluation", {}).get("checks_performed", sorted(result)))
        assumptions = tuple(raw.get("assumptions", ()))
        limits = tuple(raw.get("limits", ()))
        drivers = tuple(raw.get("uncertainty", {}).get("drivers", ("model form", "measurement variation")))

    return SpecializedDomainResult(
        row_id=row_id,
        domain=domain,
        capability=capability,
        tenant_id=scope.tenant_id,
        actor_id=scope.actor_id,
        result=result,
        evaluation=Evaluation(
            status="computed" if domain == "finance" else "draft_for_review",
            checks=checks,
            human_review_required=True,
            externally_verified=False,
        ),
        uncertainty=Uncertainty(
            level="model_reported" if any(k in result for k in ("standard_error", "confidence_interval")) else "not_quantified",
            drivers=drivers,
            input_evidence_only=True,
        ),
        assumptions=assumptions,
        limits=limits,
    )
