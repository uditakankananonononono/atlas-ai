"""Canonical data models for the M12 AI Research Lab.

Stdlib-only dataclasses. Money is always integer micro-dollars
(1 USD = 1_000_000 micro-dollars) so cost math is exact and deterministic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

MICRO_PER_USD = 1_000_000


def usd_to_micro(usd: float) -> int:
    """Convert a USD float to integer micro-dollars, rounding to nearest."""
    return int(round(usd * MICRO_PER_USD))


def micro_to_usd(micro: int) -> float:
    return micro / MICRO_PER_USD


def canonical_json(obj: Any) -> str:
    """Deterministic JSON encoding used for all hashing and manifests."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


# Capabilities a model can advertise. Kept as plain strings so new
# providers can add their own without a code change.
CAP_CHAT = "chat"
CAP_CODE = "code"
CAP_VISION = "vision"
CAP_JSON_MODE = "json_mode"
CAP_EMBEDDING = "embedding"
CAP_LONG_CONTEXT = "long_context"
CAP_TOOL_USE = "tool_use"


@dataclass(frozen=True)
class ModelProfile:
    """A routable model with its cost and capability profile."""

    model_id: str
    provider: str
    display_name: str
    cost_per_1k_input_micro: int  # micro-dollars per 1k input tokens
    cost_per_1k_output_micro: int  # micro-dollars per 1k output tokens
    capabilities: FrozenSet[str] = frozenset({CAP_CHAT})
    max_context_tokens: int = 8192
    quality_tier: int = 3  # 1 (weakest) .. 5 (strongest)
    latency_tier: int = 2  # 1 (fastest) .. 3 (slowest)
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("model_id must be non-empty")
        if self.cost_per_1k_input_micro < 0 or self.cost_per_1k_output_micro < 0:
            raise ValueError("costs must be non-negative")
        if not 1 <= self.quality_tier <= 5:
            raise ValueError("quality_tier must be in 1..5")
        if not 1 <= self.latency_tier <= 3:
            raise ValueError("latency_tier must be in 1..3")
        if self.max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be positive")

    def estimate_cost_micro(self, input_tokens: int, output_tokens: int) -> int:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts must be non-negative")
        return (
            self.cost_per_1k_input_micro * input_tokens
            + self.cost_per_1k_output_micro * output_tokens
        ) // 1000


@dataclass(frozen=True)
class TaskRequirements:
    """What a task needs from a model."""

    required_capabilities: FrozenSet[str] = frozenset({CAP_CHAT})
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    min_quality_tier: int = 1
    max_cost_micro: Optional[int] = None  # per-call ceiling; None = no ceiling
    prefer_low_latency: bool = False
    prefer_low_cost: bool = True


@dataclass(frozen=True)
class CandidateVerdict:
    """Per-model eligibility verdict, kept for explainability."""

    model_id: str
    eligible: bool
    reasons: Tuple[str, ...] = ()
    estimated_cost_micro: Optional[int] = None
    score: Optional[float] = None


@dataclass(frozen=True)
class RouteDecision:
    """Outcome of routing: the chosen model plus the full audit trail."""

    chosen: ModelProfile
    estimated_cost_micro: int
    reasons: Tuple[str, ...]
    verdicts: Tuple[CandidateVerdict, ...]


@dataclass(frozen=True)
class BudgetPolicy:
    """Spending limits. All amounts in micro-dollars. None = unlimited."""

    daily_limit_micro: Optional[int] = None
    monthly_limit_micro: Optional[int] = None
    per_run_limit_micro: Optional[int] = None
    warn_fraction: float = 0.8  # warn once spend reaches this fraction of a limit

    def __post_init__(self) -> None:
        for name in ("daily_limit_micro", "monthly_limit_micro", "per_run_limit_micro"):
            v = getattr(self, name)
            if v is not None and v <= 0:
                raise ValueError(f"{name} must be positive or None")
        if not 0.0 < self.warn_fraction <= 1.0:
            raise ValueError("warn_fraction must be in (0, 1]")


@dataclass(frozen=True)
class BudgetStatus:
    """Snapshot of spend against policy, all amounts in micro-dollars."""

    spent_today_micro: int
    spent_month_micro: int
    reserved_micro: int
    daily_limit_micro: Optional[int]
    monthly_limit_micro: Optional[int]
    per_run_limit_micro: Optional[int]
    daily_remaining_micro: Optional[int]
    monthly_remaining_micro: Optional[int]
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StepRecord:
    """One executed step inside a reproducible run."""

    step_id: str
    kind: str
    status: str  # completed | failed | skipped
    model_id: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_micro: int = 0
    attempts: int = 1
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class RunManifest:
    """Everything needed to audit and reproduce a run."""

    run_id: str
    workflow_name: str
    created_at_utc: str
    code_version: str
    python_version: str
    platform: str
    seed: Optional[int]
    config: Dict[str, Any]
    config_hash: str
    input_hash: str
    steps: Tuple[StepRecord, ...] = ()
    status: str = "running"  # running | completed | failed
    total_cost_micro: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def digest(self) -> str:
        """Stable digest over the manifest content."""
        return sha256_hex(canonical_json(self.to_dict()))


@dataclass(frozen=True)
class EvalCase:
    """One evaluation case with declarative checks."""

    case_id: str
    input: Any
    checks: Tuple[Dict[str, Any], ...]

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("case_id must be non-empty")
        if not self.checks:
            raise ValueError("an eval case needs at least one check")


@dataclass(frozen=True)
class CheckResult:
    check: Dict[str, Any]
    passed: bool
    detail: str


@dataclass(frozen=True)
class EvalCaseResult:
    case_id: str
    passed: bool
    output_hash: str
    checks: Tuple[CheckResult, ...]


@dataclass(frozen=True)
class EvalReport:
    """Aggregate result of an evaluation run, deterministically ordered."""

    eval_id: str
    created_at_utc: str
    case_results: Tuple[EvalCaseResult, ...]
    total: int
    passed: int
    failed: int

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eval_id": self.eval_id,
            "created_at_utc": self.created_at_utc,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "case_results": [
                {
                    "case_id": c.case_id,
                    "passed": c.passed,
                    "output_hash": c.output_hash,
                    "checks": [
                        {"check": r.check, "passed": r.passed, "detail": r.detail}
                        for r in c.checks
                    ],
                }
                for c in self.case_results
            ],
        }

    def digest(self) -> str:
        return sha256_hex(canonical_json(self.to_dict()))
