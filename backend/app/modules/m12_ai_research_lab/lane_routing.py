"""Capability- and budget-aware model routing.

Deterministic: given the same registry and requirements, route() always
picks the same model and explains why. All rejection reasons are kept so
decisions are auditable.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .lane_models import (
    CandidateVerdict,
    ModelProfile,
    RouteDecision,
    TaskRequirements,
)


class NoEligibleModelError(RuntimeError):
    def __init__(self, verdicts: List[CandidateVerdict]):
        self.verdicts = tuple(verdicts)
        summary = "; ".join(
            f"{v.model_id}: {', '.join(v.reasons)}" for v in verdicts if not v.eligible
        )
        super().__init__(f"no eligible model ({summary or 'empty registry'})")


class ModelRouter:
    """Registry + deterministic router."""

    def __init__(self, profiles: Optional[List[ModelProfile]] = None) -> None:
        self._models: Dict[str, ModelProfile] = {}
        for p in profiles or []:
            self.register(p)

    def register(self, profile: ModelProfile) -> None:
        if profile.model_id in self._models:
            raise ValueError(f"duplicate model_id: {profile.model_id}")
        self._models[profile.model_id] = profile

    def get(self, model_id: str) -> ModelProfile:
        try:
            return self._models[model_id]
        except KeyError:
            raise KeyError(f"unknown model_id: {model_id}") from None

    def list_models(self, include_disabled: bool = False) -> List[ModelProfile]:
        models = sorted(self._models.values(), key=lambda m: m.model_id)
        if not include_disabled:
            models = [m for m in models if m.enabled]
        return models

    def _check_eligibility(
        self, m: ModelProfile, req: TaskRequirements
    ) -> Tuple[bool, Tuple[str, ...], int]:
        reasons: List[str] = []
        if not m.enabled:
            reasons.append("model disabled")
        missing = sorted(req.required_capabilities - m.capabilities)
        if missing:
            reasons.append(f"missing capabilities: {', '.join(missing)}")
        if m.quality_tier < req.min_quality_tier:
            reasons.append(
                f"quality tier {m.quality_tier} below required {req.min_quality_tier}"
            )
        needed_ctx = req.estimated_input_tokens + req.estimated_output_tokens
        if needed_ctx > m.max_context_tokens:
            reasons.append(
                f"estimated tokens {needed_ctx} exceed context {m.max_context_tokens}"
            )
        cost = m.estimate_cost_micro(
            req.estimated_input_tokens, req.estimated_output_tokens
        )
        if req.max_cost_micro is not None and cost > req.max_cost_micro:
            reasons.append(
                f"estimated cost {cost} micro exceeds ceiling {req.max_cost_micro}"
            )
        return (not reasons, tuple(reasons), cost)

    @staticmethod
    def _effective_cost_micro(m: ModelProfile, estimated_cost_micro: int,
                              req: TaskRequirements) -> int:
        """Cost used to compare candidates.

        With real token estimates this is the estimated call cost. With no
        estimates (0 tokens, common for preview routing) estimated cost is 0
        for every model and cannot discriminate, so we fall back to the
        blended per-1k unit price. Deterministic either way.
        """
        if req.estimated_input_tokens + req.estimated_output_tokens > 0:
            return estimated_cost_micro
        return (m.cost_per_1k_input_micro + m.cost_per_1k_output_micro) // 2

    @classmethod
    def _sort_key(cls, m: ModelProfile, estimated_cost_micro: int,
                  req: TaskRequirements) -> Tuple:
        """Deterministic lexicographic ranking. Lower tuple wins.

        Default: effective cost, then quality (desc), then latency, then id.
        Latency-first callers get latency ahead of cost. model_id is always
        the final tie-break so identical profiles resolve stably.
        """
        eff = cls._effective_cost_micro(m, estimated_cost_micro, req)
        if req.prefer_low_latency:
            return (m.latency_tier, eff, -m.quality_tier, m.model_id)
        return (eff, -m.quality_tier, m.latency_tier, m.model_id)

    def route(self, req: TaskRequirements) -> RouteDecision:
        verdicts: List[CandidateVerdict] = []
        eligible: List[Tuple[Tuple, ModelProfile, int]] = []
        for m in sorted(self._models.values(), key=lambda x: x.model_id):
            ok, reasons, cost = self._check_eligibility(m, req)
            if ok:
                key = self._sort_key(m, cost, req)
                verdicts.append(
                    CandidateVerdict(
                        model_id=m.model_id,
                        eligible=True,
                        reasons=(),
                        estimated_cost_micro=cost,
                        score=float(key[0]),
                    )
                )
                eligible.append((key, m, cost))
            else:
                verdicts.append(
                    CandidateVerdict(
                        model_id=m.model_id,
                        eligible=False,
                        reasons=reasons,
                        estimated_cost_micro=cost,
                        score=None,
                    )
                )
        if not eligible:
            raise NoEligibleModelError(verdicts)
        eligible.sort(key=lambda t: t[0])
        key, chosen, cost = eligible[0]
        eff = self._effective_cost_micro(chosen, cost, req)
        reasons = (
            f"best deterministic rank among {len(eligible)} eligible model(s)",
            f"effective cost {eff} micro-dollars "
            f"({'estimated call cost' if req.estimated_input_tokens + req.estimated_output_tokens > 0 else 'blended unit price, no token estimate given'})",
            f"quality tier {chosen.quality_tier}, latency tier {chosen.latency_tier}",
        )
        return RouteDecision(
            chosen=chosen,
            estimated_cost_micro=cost,
            reasons=reasons,
            verdicts=tuple(verdicts),
        )
