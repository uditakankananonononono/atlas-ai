from __future__ import annotations
import asyncio
from dataclasses import dataclass
from math import isfinite
from typing import Any
from .models import ModelProvider, ModelResult, RouteRequest
from .bounded_evidence import BoundedProvider, detached_plain_data
from .router import ModelRouter, confidence_from_logprobs


class ConfidenceUnavailable(RuntimeError):
    def __init__(self, result: ModelResult):
        super().__init__("Model confidence unavailable; review required, no automatic retry")
        self.result = result


class ConfidenceThresholdNotReached(ConfidenceUnavailable):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    min_confidence: float = .70
    max_attempts: int = 3
    base_delay_seconds: float = .2
    enable_self_critique: bool = True

    def __post_init__(self):
        if type(self.min_confidence) not in (int, float) or not 0 <= self.min_confidence <= 1:
            raise ValueError("minimum confidence must be finite numeric 0..1")
        if type(self.max_attempts) is not int or self.max_attempts <= 0:
            raise ValueError("maximum attempts must be positive integer")
        if type(self.base_delay_seconds) not in (int, float) or self.base_delay_seconds < 0:
            raise ValueError("retry delay must be finite nonnegative number")
        try:
            valid_delay = isfinite(self.base_delay_seconds)
        except OverflowError:
            valid_delay = False
        if not valid_delay or type(self.enable_self_critique) is not bool:
            raise ValueError("invalid retry delay or self critique flag")


class ResearchExecutor:
    def __init__(self, router: ModelRouter, provider: ModelProvider, policy: RetryPolicy = RetryPolicy()):
        self.router = router
        self.provider = provider
        self.policy = policy

    async def execute(self, req: RouteRequest, prompt: str, context: dict[str, Any] | None = None) -> ModelResult:
        if type(req.tenant_id) is not str or not req.tenant_id.strip():
            raise ValueError("research tenant must be nonblank text")
        if type(context) is not dict and context is not None:
            raise ValueError("research context must be a plain mapping")
        context = detached_plain_data({} if context is None else context)
        decision = self.router.route(req)
        choices = (decision.primary,) + decision.fallbacks
        history = []
        provider = BoundedProvider(self.provider)
        for attempt in range(min(self.policy.max_attempts, len(choices))):
            model = choices[attempt]
            result = await provider.generate(model_id=model.model_id, prompt=prompt, context={
                **context, "tenant_id": req.tenant_id,
                "attempt_history": [dict(item) for item in history],
            })
            result.metadata["requested_model_id"] = model.model_id
            confidence = result.confidence if result.confidence is not None else confidence_from_logprobs(result.logprobs)
            diagnostics = {"attempts": attempt + 1, "history": history,
                           "route_scores": {key: value if isfinite(value) else None for key, value in decision.scores.items()}}
            if confidence is None:
                result.metadata.update({**diagnostics, "review_required": True, "confidence_source": "unavailable"})
                raise ConfidenceUnavailable(result)
            if result.confidence is None:
                result.confidence = confidence
                result.metadata["confidence_source"] = "supplied_logprobs_mean_exp"
            history.append({"model": model.model_id, "confidence": confidence})
            if confidence >= self.policy.min_confidence:
                result.metadata.update(diagnostics)
                return result
            if self.policy.enable_self_critique:
                prompt = f"Critique and improve the candidate. Return only the improved answer.\nCandidate:\n{result.text}\nOriginal task:\n{prompt}"
            if attempt + 1 < min(self.policy.max_attempts, len(choices)):
                await asyncio.sleep(self.policy.base_delay_seconds * (2 ** attempt))
        result.metadata.update({"review_required": True, "review_reason": "confidence_threshold_not_reached", "history": history})
        raise ConfidenceThresholdNotReached(result)
