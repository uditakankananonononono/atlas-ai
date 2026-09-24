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

_BREAKERS={name:CircuitBreaker(3,30) for name in ("openai","anthropic","gemini","deepseek","ollama","openai_compat","huggingface","fugu")}
_USAGE:list[ProviderUsage]=[]

def usage_snapshot()->list[ProviderUsage]: return list(_USAGE)
def _model(name:str)->str:
    value=name.strip()
    if not value or len(value)>200 or any(x in value for x in "\r\n/?#"):
        raise ProviderError("invalid model identifier")
    return value

def _hf_model(name:str)->str:
    """Hub ids are `org/name`, optionally with a `:provider` suffix; one slash is allowed here."""
    value=name.strip()
    if not value or len(value)>200 or value.count("/")>1 or any(x in value for x in "\r\n?#") or value.startswith("/") or value.endswith("/"):
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
    elif provider=="deepseek":
        key=os.getenv("DEEPSEEK_API_KEY")
        if not key: raise ProviderError("DEEPSEEK_API_KEY is not configured")
        chosen=_model(model or os.getenv("ATLAS_DEEPSEEK_MODEL","deepseek-chat"))
        data=await _post(provider,"https://api.deepseek.com/chat/completions",headers={"Authorization":f"Bearer {key}"},payload={"model":chosen,"messages":[{"role":"user","content":prompt}]})
        try:text=data["choices"][0]["message"]["content"]
        except (KeyError,IndexError,TypeError) as exc:raise ProviderError("DeepSeek response schema rejected") from exc
    elif provider in {"ollama","local"}:
        provider="ollama";chosen=_model(model or os.getenv("ATLAS_OLLAMA_MODEL","llama3.1:70b"));base=os.getenv("ATLAS_OLLAMA_URL","http://ollama:11434").rstrip("/")
        data=await _post(provider,f"{base}/api/chat",payload={"model":chosen,"stream":False,"messages":[{"role":"user","content":prompt}]})
        try:text=data["message"]["content"]
        except (KeyError,TypeError) as exc:raise ProviderError("Ollama response schema rejected") from exc
    elif provider in {"openai_compat","llamacpp","vllm","lmstudio","sglang"}:
        # Any OpenAI-compatible server on her own PC (llama.cpp `llama-server`, vLLM, LM Studio, SGLang). Free: no key.
        provider="openai_compat";base=os.getenv("ATLAS_LOCAL_OPENAI_URL","http://localhost:8080/v1").rstrip("/")
        chosen=_model(model or os.getenv("ATLAS_LOCAL_OPENAI_MODEL","local"))
        headers={"Authorization":f"Bearer {os.getenv('ATLAS_LOCAL_OPENAI_KEY')}"} if os.getenv("ATLAS_LOCAL_OPENAI_KEY") else None
        data=await _post(provider,f"{base}/chat/completions",headers=headers,payload={"model":chosen,"messages":[{"role":"user","content":prompt}]})
        try:text=data["choices"][0]["message"]["content"]
        except (KeyError,IndexError,TypeError) as exc:raise ProviderError("Local OpenAI-compatible response schema rejected") from exc
    elif provider in {"huggingface","hf"}:
        # Hugging Face Inference Providers router; a free HF account includes monthly credits. Optional config.
        provider="huggingface";key=os.getenv("HF_TOKEN")
        if not key: raise ProviderError("HF_TOKEN is not configured")
        chosen=_hf_model(model or os.getenv("ATLAS_HF_MODEL","thinkingmachines/Inkling-Small"))
        data=await _post(provider,"https://router.huggingface.co/v1/chat/completions",headers={"Authorization":f"Bearer {key}"},payload={"model":chosen,"messages":[{"role":"user","content":prompt}]})
        try:text=data["choices"][0]["message"]["content"]
        except (KeyError,IndexError,TypeError) as exc:raise ProviderError("Hugging Face response schema rejected") from exc
    elif provider in {"fugu","sakana"}:
        # Sakana Fugu is a PAID hosted API (not open weights). Never used unless paid use is explicitly enabled.
        provider="fugu"
        if os.getenv("ATLAS_ALLOW_PAID","").lower() not in {"1","true","yes"}: raise ProviderError("Fugu is a paid API; set ATLAS_ALLOW_PAID=true to enable it")
        key=os.getenv("FUGU_API_KEY");base=os.getenv("FUGU_BASE_URL","").rstrip("/")
        if not key or not base: raise ProviderError("FUGU_API_KEY and FUGU_BASE_URL are not configured")
        if not base.endswith("/v1"): base=f"{base}/v1"
        chosen=_model(model or os.getenv("ATLAS_FUGU_MODEL","fugu"))
        data=await _post(provider,f"{base}/chat/completions",headers={"Authorization":f"Bearer {key}"},payload={"model":chosen,"messages":[{"role":"user","content":prompt}]})
        try:text=data["choices"][0]["message"]["content"]
        except (KeyError,IndexError,TypeError) as exc:raise ProviderError("Fugu response schema rejected") from exc
    else:raise ProviderError(f"Unsupported provider: {provider}")
    if not isinstance(text,str) or not text.strip():raise ProviderError(f"{provider.title()} returned no text")
    _usage(data,provider,chosen);return chosen,text
