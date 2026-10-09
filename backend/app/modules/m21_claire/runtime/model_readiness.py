"""Fixed non-private protocol canary, not a model intelligence certification."""
from __future__ import annotations
import hashlib
import secrets
from dataclasses import dataclass

from . import bounded
from .engine import InvalidModelOutput, ModelUnavailable
from .model_adapter import LocalSharedModel
from .redaction import scrub_text


@dataclass(frozen=True)
class ModelReadiness:
    status: str  # unavailable | invalid_output | protocol_answered
    provider: str
    model: str
    response: str | None = None  # actual model final text, scrubbed/capped
    response_sha256: str | None = None  # full parsed decision JSON, before scrub
    learned_model_verified: bool = False
    acceptance_a_met: bool = False


async def check_local_model(provider: str, url: str, model: str, *, timeout_seconds: float = 5) -> ModelReadiness:
    """No DB/queue/tools/private context. No hosted fallback or inference retry.

    A valid JSON reply establishes only protocol reachability. An echo/mock server
    can pass, so never infer learned-model provenance or acceptance A from it.
    """
    if type(timeout_seconds) not in (int, float) or not .05 <= timeout_seconds <= 60:
        raise ValueError("timeout_seconds must be between 0.05 and 60")
    selected = LocalSharedModel.select(provider, url, model)
    # Canary identifiers are safe application config, not URLs or credentials.
    if len(model) > 200:
        raise ValueError("model name exceeds canary limit")
    nonce = secrets.token_hex(8)
    messages = [{"role":"system", "content":"Reply as JSON with exactly one final string field. Do not call any tool."},
                {"role":"user", "content":f"Local readiness probe {nonce}. Return a short greeting in final. This is synthetic probe input, not private user data."}]
    try:
        decision = await bounded.run_bounded(selected.decide(messages), timeout_seconds)
    except (ModelUnavailable, TimeoutError):
        return ModelReadiness("unavailable", provider, scrub_text(model)[:200])
    except InvalidModelOutput:
        return ModelReadiness("invalid_output", provider, scrub_text(model)[:200])
    if decision.final is None:
        return ModelReadiness("invalid_output", provider, scrub_text(model)[:200])
    digest = hashlib.sha256(decision.model_dump_json().encode()).hexdigest()
    return ModelReadiness("protocol_answered", provider, scrub_text(model)[:200],
                          scrub_text(decision.final)[:1000], digest)
