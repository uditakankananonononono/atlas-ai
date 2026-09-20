from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from statistics import fmean
from typing import Any, Callable, Iterable

from .reproducibility import RunManifest


@dataclass(frozen=True, slots=True)
class ExperimentPlan:
    experiment_id: str
    hypothesis: str
    primary_metric: str
    parameters: dict[str, Any]
    seed: int
    analysis_plan: str
    code_version: str

    def __post_init__(self) -> None:
        required = (self.experiment_id, self.hypothesis, self.primary_metric, self.analysis_plan, self.code_version)
        if any(not item.strip() for item in required):
            raise ValueError("experiment plan text fields cannot be blank")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    experiment_id: str
    primary_metric: str
    metric_value: float
    sample_size: int
    outputs: dict[str, Any]
    manifest: RunManifest
    warnings: tuple[str, ...] = ()


Runner = Callable[[dict[str, Any], int], dict[str, Any]]


def execute_experiment(plan: ExperimentPlan, runner: Runner, inputs: dict[str, Any] | None = None) -> ExperimentResult:
    """Run a preregistered plan through a supplied seam and produce a content-addressed manifest."""
    outputs = runner(dict(plan.parameters), plan.seed)
    if not isinstance(outputs, dict):
        raise TypeError("runner must return a dictionary")
    if plan.primary_metric not in outputs:
        raise ValueError(f"runner did not return primary metric {plan.primary_metric!r}")
    raw_metric = outputs[plan.primary_metric]
    if isinstance(raw_metric, bool) or not isinstance(raw_metric, (int, float)) or not math.isfinite(float(raw_metric)):
        raise ValueError("primary metric must be a finite number")
    sample_size = outputs.get("sample_size", 0)
    if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size < 0:
        raise ValueError("sample_size must be a non-negative integer")
    warnings = () if sample_size else ("sample_size was not reported",)
    manifest = RunManifest.create(plan.code_version, plan.seed, {**plan.parameters, "analysis_plan": plan.analysis_plan},
                                  inputs or {}, outputs)
    return ExperimentResult(plan.experiment_id, plan.primary_metric, float(raw_metric), sample_size, outputs, manifest, warnings)


def monte_carlo(seed: int, iterations: int, sampler: Callable[[Any], float]) -> dict[str, Any]:
    """Minimal deterministic simulation seam using an isolated stdlib RNG."""
    import random
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    rng = random.Random(seed)
    samples = [float(sampler(rng)) for _ in range(iterations)]
    if not all(math.isfinite(value) for value in samples):
        raise ValueError("sampler returned a non-finite value")
    mean = fmean(samples)
    variance = fmean((value - mean) ** 2 for value in samples)
    return {"mean": mean, "standard_deviation": math.sqrt(variance), "sample_size": iterations,
            "minimum": min(samples), "maximum": max(samples)}
