"""Run comparison and spend analytics for the M12 AI Research Lab.

Two reproducibility questions researchers ask constantly:
1. What changed between two runs? (diff_manifests)
2. Where did the money go? (spend analytics)

Both are pure functions over stored data - deterministic, no I/O beyond
the injected store.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .lane_runs import read_manifest
from .lane_models import RunManifest, StepRecord, micro_to_usd


@dataclass(frozen=True)
class StepDiff:
    step_id: str
    change: str  # added | removed | changed | unchanged
    before: Optional[StepRecord]
    after: Optional[StepRecord]
    changed_fields: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ManifestDiff:
    run_id_before: str
    run_id_after: str
    config_changed: bool
    input_changed: bool
    seed_changed: bool
    code_version_changed: bool
    status_change: Tuple[str, str]
    cost_delta_micro: int
    step_diffs: Tuple[StepDiff, ...]

    @property
    def identical(self) -> bool:
        return (
            not self.config_changed
            and not self.input_changed
            and not self.seed_changed
            and not self.code_version_changed
            and self.cost_delta_micro == 0
            and all(d.change == "unchanged" for d in self.step_diffs)
        )


_STEP_FIELDS = (
    "kind", "status", "model_id", "input_tokens", "output_tokens",
    "cost_micro", "attempts", "input_hash", "output_hash", "error",
)


def diff_manifests(before: RunManifest, after: RunManifest) -> ManifestDiff:
    """Field-level diff of two run manifests, steps matched by step_id."""
    before_steps = {s.step_id: s for s in before.steps}
    after_steps = {s.step_id: s for s in after.steps}
    diffs: List[StepDiff] = []
    for step_id in sorted(set(before_steps) | set(after_steps)):
        b = before_steps.get(step_id)
        a = after_steps.get(step_id)
        if b is None:
            diffs.append(StepDiff(step_id, "added", None, a))
        elif a is None:
            diffs.append(StepDiff(step_id, "removed", b, None))
        else:
            changed = tuple(
                f for f in _STEP_FIELDS if getattr(b, f) != getattr(a, f)
            )
            diffs.append(
                StepDiff(step_id, "changed" if changed else "unchanged", b, a, changed)
            )
    return ManifestDiff(
        run_id_before=before.run_id,
        run_id_after=after.run_id,
        config_changed=before.config_hash != after.config_hash,
        input_changed=before.input_hash != after.input_hash,
        seed_changed=before.seed != after.seed,
        code_version_changed=before.code_version != after.code_version,
        status_change=(before.status, after.status),
        cost_delta_micro=after.total_cost_micro - before.total_cost_micro,
        step_diffs=tuple(diffs),
    )


def diff_manifest_payloads(before: Dict[str, Any], after: Dict[str, Any]) -> ManifestDiff:
    """Same diff, from stored manifest payloads (as returned by the store)."""
    return diff_manifests(_manifest_from_payload(before), _manifest_from_payload(after))


def _manifest_from_payload(payload: Dict[str, Any]) -> RunManifest:
    m = payload["manifest"]
    return RunManifest(
        run_id=m["run_id"],
        workflow_name=m["workflow_name"],
        created_at_utc=m["created_at_utc"],
        code_version=m["code_version"],
        python_version=m["python_version"],
        platform=m["platform"],
        seed=m.get("seed"),
        config=m["config"],
        config_hash=m["config_hash"],
        input_hash=m["input_hash"],
        steps=tuple(StepRecord(**s) for s in m.get("steps", [])),
        status=m.get("status", "running"),
        total_cost_micro=m.get("total_cost_micro", 0),
    )


@dataclass(frozen=True)
class ModelSpend:
    model_id: str
    runs: int
    steps: int
    cost_micro: int
    input_tokens: int
    output_tokens: int

    @property
    def cost_usd(self) -> float:
        return micro_to_usd(self.cost_micro)


def spend_by_model(manifests: List[RunManifest]) -> Tuple[ModelSpend, ...]:
    """Aggregate per-model usage across manifests. Deterministic order."""
    agg: Dict[str, Dict[str, int]] = {}
    run_sets: Dict[str, set] = {}
    for m in manifests:
        for s in m.steps:
            if s.model_id is None:
                continue
            a = agg.setdefault(
                s.model_id,
                {"steps": 0, "cost_micro": 0, "input_tokens": 0, "output_tokens": 0},
            )
            a["steps"] += 1
            a["cost_micro"] += s.cost_micro
            a["input_tokens"] += s.input_tokens
            a["output_tokens"] += s.output_tokens
            run_sets.setdefault(s.model_id, set()).add(m.run_id)
    return tuple(
        ModelSpend(
            model_id=mid,
            runs=len(run_sets[mid]),
            steps=a["steps"],
            cost_micro=a["cost_micro"],
            input_tokens=a["input_tokens"],
            output_tokens=a["output_tokens"],
        )
        for mid, a in sorted(agg.items(), key=lambda kv: (-kv[1]["cost_micro"], kv[0]))
    )
