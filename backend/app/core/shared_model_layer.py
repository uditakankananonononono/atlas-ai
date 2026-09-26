"""Atlas wiring for the shared model layer (vendored ``instinct_models``, see
backend/instinct_models/VENDORED.md for the pinned shared-models commit).

- ``atlas_config()`` builds the shared ProductConfig with product fixed to
  "atlas". INSTINCT_* env vars are read first; ATLAS_* equivalents fill gaps so
  existing deployments keep working (ATLAS_HF_MODEL, ATLAS_ORNITH_URL, ...).
- ``atlas_router()`` returns the shared Needle-first router.
- ``run(...)`` routes one task. Private content (contracts, personal data) must
  pass ``private=True`` so it never reaches the hosted HF route; the chain stops
  instead of falling through to anything hosted or paid.
"""
from __future__ import annotations

import os
from functools import lru_cache

from instinct_models import ProductConfig, Router, Task, load_config
from instinct_models.router import RoutedResult

_ATLAS_FALLBACKS = {
    "INKLING_LOCAL_URL": "ATLAS_INKLING_LOCAL_URL",
    "INKLING_LOCAL_MODEL": "ATLAS_INKLING_LOCAL_MODEL",
    "HF_MODEL": "ATLAS_HF_MODEL",
    "ORNITH_URL": "ATLAS_ORNITH_URL",
    "ORNITH_MODEL": "ATLAS_ORNITH_MODEL",
    "NEEDLE_WEIGHTS": "ATLAS_NEEDLE_WEIGHTS",
    "ALLOW_HOSTED": "ATLAS_ALLOW_HOSTED",
    "JEV_API_KEY": "ATLAS_JEV_API_KEY",
}


def atlas_env(env: dict | None = None) -> dict:
    src = dict(os.environ if env is None else env)
    out = {k: v for k, v in src.items() if k.startswith("INSTINCT_")}
    for key, atlas_key in _ATLAS_FALLBACKS.items():
        if not out.get(f"INSTINCT_{key}") and src.get(atlas_key):
            out[f"INSTINCT_{key}"] = src[atlas_key]
    # Jev's own documented env name also counts (load_config falls back to it).
    if src.get("JEV_API_KEY") and not out.get("INSTINCT_JEV_API_KEY"):
        out["JEV_API_KEY"] = src["JEV_API_KEY"]
    product = out.get("INSTINCT_PRODUCT")
    if product and product != "atlas":
        raise ValueError(f"INSTINCT_PRODUCT={product!r} in the Atlas process; Atlas only runs as 'atlas'")
    out["INSTINCT_PRODUCT"] = "atlas"
    return out


def atlas_config(env: dict | None = None, path: str | None = None) -> ProductConfig:
    return load_config(atlas_env(env), path=path or os.getenv("INSTINCT_CONFIG_FILE") or None)


@lru_cache(maxsize=1)
def atlas_router() -> Router:
    return Router.from_config(atlas_config())


def run(messages: list[dict], *, tools: list[dict] | None = None, private: bool = True,
        max_tokens: int = 1024, router: Router | None = None) -> RoutedResult:
    """Route one task. Defaults to private=True: Atlas handles her contracts and
    mail, so callers must opt out explicitly for public-only content."""
    return (router or atlas_router()).run(Task(messages=messages, tools=tools, private=private, max_tokens=max_tokens))


class SharedModelError(RuntimeError):
    """No route in the shared chain answered; ``attempts`` says why for each one."""

    def __init__(self, message: str, attempts: list):
        super().__init__(message)
        self.attempts = attempts


def _describe(res: RoutedResult) -> str:
    return " | ".join(f"{a.provider}: {a.outcome}{(' ' + a.detail) if a.detail else ''}" for a in res.attempts)


async def generate(prompt: str, *, private: bool = True, max_tokens: int = 2048,
                   router: Router | None = None) -> tuple[str, str, str]:
    """Async text generation through the shared router: returns (provider, model, text).
    Runs the blocking router in a worker thread. Raises SharedModelError if nothing answered."""
    import asyncio

    r = router or atlas_router()
    res = await asyncio.to_thread(r.run, Task(messages=[{"role": "user", "content": prompt}], private=private,
                                              max_tokens=max_tokens))
    if not res.ok:
        raise SharedModelError("no shared-model route answered: " + _describe(res), res.attempts)
    return res.result.provider, res.result.model, res.result.text


def jev_eval(env: dict | None = None) -> "JevEval":
    """Atlas Jev evaluation client (TypeSafe AI's System One model).

    Key resolution: INSTINCT_JEV_API_KEY, then ATLAS_JEV_API_KEY, then JEV_API_KEY.
    Without a key the client is unavailable and OFF - nothing is called or billed.
    Jev is hosted and paid (credits); it evaluates typed questions, it does not chat,
    and it must never receive private state.
    """
    from instinct_models import JevEval

    return JevEval(api_key=atlas_config(env).jev_api_key)
