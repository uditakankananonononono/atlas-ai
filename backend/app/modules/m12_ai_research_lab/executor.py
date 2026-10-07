from __future__ import annotations
import asyncio
from math import isfinite
from dataclasses import dataclass,replace
from typing import Any
from .models import ModelProvider, ModelResult, RouteRequest
from app.core.providers import ProviderOutcomeUnknown
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
        policy=self.policy
        if type(req.tenant_id) is not str or not req.tenant_id.strip():raise ValueError("research tenant must be nonblank text")
        if type(prompt) is not str or not prompt.strip():raise ValueError("research prompt must be nonblank text")
        try:prompt.encode("utf-8")
        except UnicodeEncodeError as error:raise ValueError("research prompt must encode as UTF-8") from error
        decision=self.router.route(req); diagnostics={"route_scores":{key:value if isfinite(value) else None for key,value in decision.scores.items()},"route_reasons":decision.reasons}; choices=(decision.primary,)+decision.fallbacks; history=[]; context=dict(context or {})
        for attempt in range(min(policy.max_attempts,len(choices))):
            model=choices[attempt]
            result=await self.provider.generate(model_id=model.model_id,prompt=prompt,context={**context,"tenant_id":req.tenant_id,"attempt_history":[dict(item) for item in history]})
            if not isinstance(result,ModelResult) or type(result.metadata) is not dict:
                raise ProviderOutcomeUnknown("Returned model result envelope or metadata is unusable; no automatic retry")
            if type(result.text) is not str or type(result.model_id) is not str or not result.model_id.strip():
                raise ProviderOutcomeUnknown("Returned model text or reported model identity is unusable; no automatic retry")
            try:result.text.encode("utf-8")
            except UnicodeEncodeError as error:raise ProviderOutcomeUnknown("Returned model text is not UTF-8 encodable; no automatic retry") from error
            if type(result.usage) is not dict or any(type(key) is not str or type(value) is not int for key,value in result.usage.items()):
                raise ProviderOutcomeUnknown("Returned model usage is not the declared string-to-integer mapping; no automatic retry")
            try:result=replace(result,metadata=dict(result.metadata),usage=dict(result.usage),logprobs=list(result.logprobs) if type(result.logprobs) is list else result.logprobs)
            except Exception as error:raise ProviderOutcomeUnknown("Returned model result could not be copied safely; no automatic retry") from error
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
            if confidence >= policy.min_confidence:
                result.metadata.update({"attempts":attempt+1,**diagnostics,"history":history}); return result
            if policy.enable_self_critique:
                prompt=f"Critique and improve the candidate. Return only the improved answer.\nCandidate:\n{result.text}\nOriginal task:\n{prompt}"
            if attempt+1 < min(policy.max_attempts,len(choices)):
                await asyncio.sleep(policy.base_delay_seconds*(2**attempt))
        result.metadata.update({"review_required":True,"review_reason":"confidence_threshold_not_reached","attempts":len(history),"history":history,**diagnostics})
        raise ConfidenceThresholdNotReached(result)
