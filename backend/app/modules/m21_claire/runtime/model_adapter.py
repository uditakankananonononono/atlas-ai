"""Explicit local shared-model bridge. No router fallback or hosted billing path.

Transport-contract tests are not evidence of learned model behavior. Synchronous
provider calls run in a thread: cancellation stops waiting, not the thread.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from instinct_models.providers import (
    LOCAL, HermesLocal, InklingLocal, OrnithOpenAICompat, Provider,
    ProviderError, require_loopback_url,
)
from .engine import InvalidModelOutput, ModelUnavailable
from .types import AgentDecision


def _invalid(*_: Any) -> Any:
    raise InvalidModelOutput("invalid model decision")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def parse_decision(text: str) -> AgentDecision:
    # Reject before parsing: Python 3.12's JSON parser does not reliably raise
    # RecursionError at the same depth as 3.11. Bound raw input and nesting.
    if not isinstance(text, str) or len(text) > 65536:
        _invalid()
    try:
        if len(text.encode("utf-8")) > 65536:
            _invalid()
    except UnicodeEncodeError:
        _invalid()
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > 32:
                _invalid()
        elif char in "]}":
            depth -= 1
    try:
        data = json.loads(text, object_pairs_hook=_pairs, parse_constant=_invalid)
    except (ValueError, RecursionError):
        _invalid()
    if not isinstance(data, dict) or set(data) - {"thought", "tool_call", "replan", "final"}:
        _invalid()
    call = data.get("tool_call")
    if call is not None and (not isinstance(call, dict) or set(call) - {"name", "arguments"}):
        _invalid()
    replan = data.get("replan")
    if replan is not None and (not isinstance(replan, dict) or set(replan) - {"reason", "steps"}):
        _invalid()
    try:
        return AgentDecision.model_validate(data, strict=True)
    except ValueError:
        _invalid()


class LocalSharedModel:
    """One selected provider. Provider failures contain no URLs/raw text in reports.

    Caller owns the provider instance; no implicit retry or second model is used.
    Construction from a URL is restricted to literal loopback through select().
    """

    def __init__(self, provider: Provider, *, max_tokens: int = 1024):
        if provider.locality != LOCAL:
            raise ValueError("hosted providers are not permitted")
        if type(max_tokens) is not int or not 1 <= max_tokens <= 4096:
            raise ValueError("max_tokens must be between 1 and 4096")
        self.provider, self.max_tokens = provider, max_tokens

    @classmethod
    def select(cls, name: str, url: str, model: str) -> LocalSharedModel:
        providers = {"ornith": OrnithOpenAICompat, "inkling": InklingLocal, "hermes": HermesLocal}
        if name not in providers or not isinstance(model, str) or not model.strip():
            raise ValueError("select an explicit local provider and model")
        endpoint = require_loopback_url(url)
        return cls(providers[name](endpoint, model))

    async def decide(self, messages: list[dict[str, str]]) -> AgentDecision:
        # Snapshot for the thread: later mutation of the loop's transcript must
        # not change a provider request after timeout/cancellation.
        snapshot = [dict(message) for message in messages]
        try:
            if not self.provider.available():
                raise ModelUnavailable("model unavailable")
            result = await asyncio.to_thread(
                self.provider.chat, snapshot, tools=None, max_tokens=self.max_tokens,
            )
        except ProviderError:
            raise ModelUnavailable("model unavailable") from None
        # Engine asks for exactly one JSON action. Native tool-calling replies
        # are not silently interpreted as a different protocol.
        if result.tool_calls:
            _invalid()
        return parse_decision(result.text)
