"""Validated LLM providers with retries, circuit breaking, trace and usage accounting."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any
import httpx
from app.platform.observability import inject_trace
from app.platform.reliability import CircuitBreaker, CircuitOpen

class ProviderError(RuntimeError): pass
@dataclass(frozen=True)
class ProviderUsage:
    provider:str; model:str; input_tokens:int; output_tokens:int

_BREAKERS={name:CircuitBreaker(3,30) for name in ("openai","anthropic","gemini")}
_USAGE:list[ProviderUsage]=[]

def usage_snapshot()->list[ProviderUsage]: return list(_USAGE)
def _model(name:str)->str:
    value=name.strip()
    if not value or len(value)>200 or any(x in value for x in "\r\n/?#"):
        raise ProviderError("invalid model identifier")
    return value

def _usage(data:dict[str,Any],provider:str,model:str)->None:
    raw=data.get("usage") or data.get("usageMetadata") or {}
    incoming=raw.get("prompt_tokens",raw.get("input_tokens",raw.get("promptTokenCount",0)))
    outgoing=raw.get("completion_tokens",raw.get("output_tokens",raw.get("candidatesTokenCount",0)))
    _USAGE.append(ProviderUsage(provider,model,int(incoming or 0),int(outgoing or 0)))

async def _post(provider:str,url:str,*,headers:dict[str,str]|None=None,params:dict[str,str]|None=None,payload:dict[str,Any])->dict[str,Any]:
    async def operation():
        async with httpx.AsyncClient(timeout=60) as client:
            response=await client.post(url,headers=inject_trace(headers or {}),params=params,json=payload)
        if response.status_code in {408,425,429,500,502,503,504}: raise httpx.HTTPStatusError("retryable provider response",request=response.request,response=response)
        if response.is_error: raise ProviderError(f"{provider.title()} request failed ({response.status_code})")
        try: return response.json()
        except ValueError as exc: raise ProviderError(f"{provider.title()} returned invalid JSON") from exc
    try:return await _BREAKERS[provider].call(operation,60,retries=2)
    except CircuitOpen as exc:raise ProviderError(f"{provider.title()} circuit is open") from exc
    except httpx.HTTPError as exc:raise ProviderError(f"{provider.title()} request failed after retries") from exc

async def generate(prompt: str, provider: str, model: str | None = None) -> tuple[str, str]:
    provider=provider.lower().strip()
    if not prompt.strip(): raise ProviderError("prompt is empty")
    if provider=="openai":
        key=os.getenv("OPENAI_API_KEY")
        if not key: raise ProviderError("OPENAI_API_KEY is not configured")
        chosen=_model(model or os.getenv("ATLAS_OPENAI_MODEL","gpt-4o-mini"))
        data=await _post(provider,"https://api.openai.com/v1/chat/completions",headers={"Authorization":f"Bearer {key}"},payload={"model":chosen,"messages":[{"role":"user","content":prompt}]})
        try:text=data["choices"][0]["message"]["content"]
        except (KeyError,IndexError,TypeError) as exc:raise ProviderError("OpenAI response schema rejected") from exc
    elif provider=="anthropic":
        key=os.getenv("ANTHROPIC_API_KEY")
        if not key: raise ProviderError("ANTHROPIC_API_KEY is not configured")
        chosen=_model(model or os.getenv("ATLAS_ANTHROPIC_MODEL","claude-3-5-haiku-latest"))
        data=await _post(provider,"https://api.anthropic.com/v1/messages",headers={"x-api-key":key,"anthropic-version":"2023-06-01"},payload={"model":chosen,"max_tokens":2048,"messages":[{"role":"user","content":prompt}]})
        try:text="".join(x["text"] for x in data["content"] if x.get("type")=="text")
        except (KeyError,TypeError) as exc:raise ProviderError("Anthropic response schema rejected") from exc
    elif provider in {"gemini","google"}:
        provider="gemini";key=os.getenv("GEMINI_API_KEY")
        if not key: raise ProviderError("GEMINI_API_KEY is not configured")
        chosen=_model(model or os.getenv("ATLAS_GEMINI_MODEL","gemini-2.5-flash"))
        data=await _post(provider,f"https://generativelanguage.googleapis.com/v1beta/models/{chosen}:generateContent",params={"key":key},payload={"contents":[{"parts":[{"text":prompt}]}]})
        try:text="".join(x.get("text","") for x in data["candidates"][0]["content"]["parts"])
        except (KeyError,IndexError,TypeError) as exc:raise ProviderError("Gemini response schema rejected") from exc
    else:raise ProviderError(f"Unsupported provider: {provider}")
    if not isinstance(text,str) or not text.strip():raise ProviderError(f"{provider.title()} returned no text")
    _usage(data,provider,chosen);return chosen,text
