"""Named-model catalog and free-first routing.

Udita names models by short names ("Fugu", "Ultron", "Inkling"). This module
records what each name really is (verified 2026-09-24), how Atlas can reach it,
and whether that costs money. Routing is free-first: local servers on her PC,
then free-tier hosted inference, and paid providers only when
ATLAS_ALLOW_PAID is explicitly true. If every free route fails, Atlas stops
with an error instead of sliding into a paid provider.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.core import providers
from app.core.providers import ProviderError

FREE = "free"            # runs on her own hardware, no account needed
FREE_TIER = "free_tier"  # hosted, needs a free account/token, capped credits
PAID = "paid"            # bills per token; never used unless ATLAS_ALLOW_PAID


@dataclass(frozen=True)
class Route:
    provider: str
    model: str
    cost: str
    note: str = ""


@dataclass(frozen=True)
class CatalogEntry:
    name: str
    what_it_is: str
    open_weights: bool
    routes: tuple[Route, ...] = field(default_factory=tuple)
    wired: bool = True
    reason_not_wired: str = ""
    sources: tuple[str, ...] = field(default_factory=tuple)


CATALOG: dict[str, CatalogEntry] = {
    "inkling": CatalogEntry(
        name="Inkling",
        what_it_is="Thinking Machines Lab open-weights multimodal MoE (975B total / 41B active, text+image+audio in, text out), released 2026-07-15.",
        open_weights=True,
        routes=(
            Route("openai_compat", "inkling", FREE, "Serve unsloth/inkling-GGUF with llama.cpp `llama-server`; even the 1-bit quant needs a very large-memory machine."),
            Route("huggingface", "thinkingmachines/Inkling", FREE_TIER, "HF Inference Providers router (together, fireworks-ai, baseten, deepinfra live)."),
        ),
        sources=("https://huggingface.co/blog/thinkingmachines-inkling", "https://huggingface.co/thinkingmachines/Inkling"),
    ),
    "inkling-small": CatalogEntry(
        name="Inkling-Small",
        what_it_is="Smaller Inkling variant, Apache-2.0, same multimodal family.",
        open_weights=True,
        routes=(
            Route("openai_compat", "inkling-small", FREE, "Self-host with vLLM/SGLang; BF16 needs ~600 GB VRAM, NVFP4 ~180 GB."),
            Route("huggingface", "thinkingmachines/Inkling-Small", FREE_TIER, "HF router (baseten, deepinfra live)."),
        ),
        sources=("https://huggingface.co/thinkingmachines/Inkling-Small",),
    ),
    "fugu": CatalogEntry(
        name="Sakana Fugu",
        what_it_is="Sakana AI multi-agent orchestrator delivered as one hosted model (fugu, fugu-ultra). NOT open weights: access is through the paid Sakana API.",
        open_weights=False,
        routes=(Route("fugu", "fugu", PAID, "Needs FUGU_API_KEY + FUGU_BASE_URL and ATLAS_ALLOW_PAID=true."),),
        sources=("https://github.com/SakanaAI/Fugu", "https://console.sakana.ai/pricing"),
    ),
    "ultron": CatalogEntry(
        name="Ultron",
        what_it_is="No single model. The name covers several unrelated community checkpoints (e.g. trojan0x/ultron recurrent-depth research models, jaipkapoor99/ultron-124m, 1bitLabs/ultron-0.3b, passing2961/Ultron-7B/11B from the Stark social-conversation paper).",
        open_weights=True,
        wired=False,
        reason_not_wired="Ambiguous name; none of these is a general assistant model. Tell Atlas which exact Hub repo you mean and it can be served through openai_compat.",
        sources=("https://huggingface.co/trojan0x/ultron", "https://huggingface.co/passing2961/Ultron-11B"),
    ),
}


def resolve(name: str) -> CatalogEntry:
    key = name.strip().lower().replace(" ", "-").removeprefix("sakana-")
    entry = CATALOG.get(key)
    if entry is None:
        raise ProviderError(f"unknown model name: {name!r}; known: {', '.join(sorted(CATALOG))}")
    if not entry.wired:
        raise ProviderError(f"{entry.name} is not wired: {entry.reason_not_wired}")
    return entry


def paid_allowed() -> bool:
    return os.getenv("ATLAS_ALLOW_PAID", "").strip().lower() in {"1", "true", "yes"}


def default_chain() -> list[Route]:
    """Free routes first, in order: Ollama, local OpenAI-compatible server, HF free tier."""
    chain = [
        Route("ollama", os.getenv("ATLAS_OLLAMA_MODEL", "llama3.1:8b"), FREE),
        Route("openai_compat", os.getenv("ATLAS_LOCAL_OPENAI_MODEL", "local"), FREE),
    ]
    if os.getenv("HF_TOKEN"):
        chain.append(Route("huggingface", os.getenv("ATLAS_HF_MODEL", "thinkingmachines/Inkling-Small"), FREE_TIER))
    return chain


async def generate_free_first(prompt: str, model_name: str | None = None) -> tuple[str, str, str]:
    """Return (provider, model, text). Tries free routes; paid only when explicitly allowed."""
    routes = list(resolve(model_name).routes) if model_name else default_chain()
    errors: list[str] = []
    for route in routes:
        if route.cost == PAID and not paid_allowed():
            errors.append(f"{route.provider}: skipped (paid, ATLAS_ALLOW_PAID not set)")
            continue
        try:
            chosen, text = await providers.generate(prompt, route.provider, route.model)
            return route.provider, chosen, text
        except ProviderError as exc:
            errors.append(f"{route.provider}: {exc}")
    raise ProviderError("no free model route succeeded; Atlas stopped instead of using a paid provider. " + " | ".join(errors))


def catalog_view() -> list[dict]:
    return [
        {
            "key": key, "name": e.name, "what_it_is": e.what_it_is, "open_weights": e.open_weights,
            "wired": e.wired, "reason_not_wired": e.reason_not_wired,
            "routes": [{"provider": r.provider, "model": r.model, "cost": r.cost, "note": r.note} for r in e.routes],
            "sources": list(e.sources),
        }
        for key, e in CATALOG.items()
    ]
