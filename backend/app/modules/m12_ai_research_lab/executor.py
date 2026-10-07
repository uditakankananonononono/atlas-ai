from __future__ import annotations
import asyncio
from math import isfinite
from dataclasses import dataclass
from typing import Any
from .models import ModelProvider, ModelResult, RouteRequest
from .router import ModelRouter, confidence_from_logprobs, valid_confidence

class ConfidenceUnavailable(RuntimeError):
    def __init__(self,result:ModelResult):
        super().__init__("Model confidence unavailable; result requires review, no automatic retry")
        self.result=result

class ConfidenceThresholdNotReached(ConfidenceUnavailable):
    def __init__(self,result:ModelResult):
        super().__init__(result)
        self.args=("Model confidence threshold not reached; last candidate requires review, no automatic retry",)

@dataclass(frozen=True)
class RetryPolicy:
    min_confidence: float=.70
    max_attempts: int=3
    base_delay_seconds: float=.2
    enable_self_critique: bool=True
    def __post_init__(self):
        if not valid_confidence(self.min_confidence):raise ValueError("minimum confidence must be finite numeric 0..1")
        if type(self.max_attempts) is not int or self.max_attempts<=0:raise ValueError("maximum attempts must be positive integer")
        if type(self.base_delay_seconds) not in (int,float) or self.base_delay_seconds<0:raise ValueError("retry delay must be finite nonnegative number")
        try:finite_delay=isfinite(self.base_delay_seconds)
        except OverflowError:finite_delay=False
        if not finite_delay:raise ValueError("retry delay must be finite nonnegative number")
        if type(self.enable_self_critique) is not bool:raise ValueError("self critique must be boolean")

class ResearchExecutor:
    def __init__(self, router:ModelRouter, provider:ModelProvider, policy:RetryPolicy=RetryPolicy()): self.router=router; self.provider=provider; self.policy=policy
    async def execute(self, req:RouteRequest, prompt:str, context:dict[str,Any]|None=None)->ModelResult:
        decision=self.router.route(req); diagnostics={"route_scores":{key:value if isfinite(value) else None for key,value in decision.scores.items()},"route_reasons":decision.reasons}; choices=(decision.primary,)+decision.fallbacks; history=[]; context=dict(context or {})
        for attempt in range(min(self.policy.max_attempts,len(choices))):
            model=choices[attempt]
            result=await self.provider.generate(model_id=model.model_id,prompt=prompt,context={**context,"attempt_history":history})
            result.metadata["requested_model_id"]=model.model_id
            confidence=(result.confidence if valid_confidence(result.confidence) else None) if result.confidence is not None else confidence_from_logprobs(result.logprobs)
            if confidence is None:
                result.confidence=None;result.logprobs=[]
                result.metadata.update({"review_required":True,"confidence_source":"unavailable","attempts":attempt+1,"history":history,**diagnostics})
                raise ConfidenceUnavailable(result)
            if result.confidence is None:
                result.confidence=confidence
                result.metadata["confidence_source"]="supplied_logprobs_mean_exp"
            history.append({"model":model.model_id,"confidence":confidence})
            if confidence >= self.policy.min_confidence:
                result.metadata.update({"attempts":attempt+1,**diagnostics,"history":history}); return result
            if self.policy.enable_self_critique:
                prompt=f"Critique and improve the candidate. Return only the improved answer.\nCandidate:\n{result.text}\nOriginal task:\n{prompt}"
            if attempt+1 < min(self.policy.max_attempts,len(choices)):
                await asyncio.sleep(self.policy.base_delay_seconds*(2**attempt))
        result.metadata.update({"review_required":True,"review_reason":"confidence_threshold_not_reached","attempts":len(history),"history":history,**diagnostics})
        raise ConfidenceThresholdNotReached(result)
