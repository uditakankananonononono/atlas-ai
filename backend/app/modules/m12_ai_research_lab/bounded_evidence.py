"""Opt-in plain-data boundary. No model authenticity, billing or quality claim.

Compose BoundedProvider with ResearchExecutor. This does not replace the shipped
service wiring. Limits bound retained data, not provider CPU, transport or money.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from app.core.providers import ProviderOutcomeUnknown
from .models import ModelProvider, ModelResult


class EvidenceRejected(ValueError):
    """Data cannot be represented under the declared local limits."""


@dataclass(frozen=True)
class EvidenceLimits:
    max_depth: int = 32
    max_items: int = 10000
    max_utf8_bytes: int = 1048576
    max_integer_bits: int = 256

    def __post_init__(self):
        for value in (self.max_depth, self.max_items, self.max_utf8_bytes,
                      self.max_integer_bits):
            if type(value) is not int or value <= 0:
                raise ValueError("evidence limits must be positive exact integers")


def detached_plain_data(value: Any, limits: EvidenceLimits = EvidenceLimits()) -> Any:
    """Iteratively copy exact JSON-like types with shared aggregate budgets.

    Depth counts edges from the root. Items count values and mapping keys.
    Bytes count UTF-8 strings and keys, not JSON syntax or scalar encodings.
    Repeated aliases are copied separately; ancestor cycles are rejected.
    No arbitrary conversion, iterator, property or representation is invoked.
    """
    if type(limits) is not EvidenceLimits:
        raise ValueError("limits must be EvidenceLimits")
    root = [None]
    active: set[int] = set()
    items = 0
    size = 0
    stack = [(False, value, root, 0, 0)]

    def charge_text(text: str):
        nonlocal size
        # UTF-8 has at least one byte per Python character. Avoid encoding an
        # already oversized string, and encode in chunks for bounded scratch.
        if len(text) > limits.max_utf8_bytes - size:
            raise EvidenceRejected("UTF-8 byte budget exceeded")
        try:
            for start in range(0, len(text), 4096):
                size += len(text[start:start + 4096].encode("utf-8"))
                if size > limits.max_utf8_bytes:
                    raise EvidenceRejected("UTF-8 byte budget exceeded")
        except UnicodeEncodeError as error:
            raise EvidenceRejected("text is not UTF-8 encodable") from error

    while stack:
        leaving, source, destination, key, depth = stack.pop()
        if leaving:
            active.remove(id(source))
            continue
        items += 1
        if items > limits.max_items:
            raise EvidenceRejected("item budget exceeded")
        if depth > limits.max_depth:
            raise EvidenceRejected("depth budget exceeded")
        kind = type(source)
        if source is None or kind is bool:
            destination[key] = source
        elif kind is str:
            charge_text(source)
            destination[key] = source
        elif kind is int:
            if source.bit_length() > limits.max_integer_bits:
                raise EvidenceRejected("integer bit budget exceeded")
            destination[key] = source
        elif kind is float:
            if not isfinite(source):
                raise EvidenceRejected("nonfinite number")
            destination[key] = source
        elif kind in (list, dict):
            if id(source) in active:
                raise EvidenceRejected("ancestor cycle")
            # Reject wide inputs before allocating a duplicate or task stack.
            required = len(source) * (2 if kind is dict else 1)
            if items + required > limits.max_items:
                raise EvidenceRejected("item budget exceeded")
            active.add(id(source))
            copy = [None] * len(source) if kind is list else {}
            destination[key] = copy
            stack.append((True, source, None, None, 0))
            if kind is list:
                for index in range(len(source) - 1, -1, -1):
                    stack.append((False, source[index], copy, index, depth + 1))
            else:
                for child_key, child in source.items():
                    if type(child_key) is not str:
                        raise EvidenceRejected("mapping keys must be exact text")
                    items += 1
                    if items > limits.max_items:
                        raise EvidenceRejected("item budget exceeded")
                    charge_text(child_key)
                    stack.append((False, child, copy, child_key, depth + 1))
        else:
            raise EvidenceRejected("unsupported plain-data type")
    return root[0]


def detached_result(result: ModelResult,
                    limits: EvidenceLimits = EvidenceLimits()) -> ModelResult:
    """Copy and validate the envelope, without authenticating its assertions."""
    if type(result) is not ModelResult:
        raise EvidenceRejected("result must be exact ModelResult")
    if type(result.text) is not str or type(result.model_id) is not str or not result.model_id.strip():
        raise EvidenceRejected("text and nonblank model identity are required")
    if type(result.metadata) is not dict or type(result.usage) is not dict or type(result.logprobs) is not list:
        raise EvidenceRejected("invalid result container shape")
    # Apply resource budgets before scanning each evidence sequence.
    copied = detached_plain_data({
        "text": result.text, "model_id": result.model_id,
        "confidence": result.confidence, "logprobs": result.logprobs,
        "usage": result.usage, "metadata": result.metadata,
    }, limits)
    confidence = copied["confidence"]
    if confidence is not None and (type(confidence) not in (int, float) or not 0 <= confidence <= 1):
        raise EvidenceRejected("invalid confidence")
    if any(type(count) is not int or count < 0 for count in copied["usage"].values()):
        raise EvidenceRejected("invalid usage counts")
    if any(type(logprob) not in (int, float) or not -1e308 <= logprob <= 0 for logprob in copied["logprobs"]):
        raise EvidenceRejected("invalid logprob evidence")
    return ModelResult(**copied)


class BoundedProvider:
    """Guard local inputs before dispatch and quarantine unusable returns.

    Exceptions raised by the underlying provider retain their original type.
    A rejected return follows a dispatched call, so it is always unknown and
    must not trigger fallback. Cancellation remains cancellation.
    """
    def __init__(self, provider: ModelProvider, limits: EvidenceLimits = EvidenceLimits()):
        if type(limits) is not EvidenceLimits:
            raise ValueError("limits must be EvidenceLimits")
        self.provider = provider
        self.limits = limits

    async def generate(self, *, model_id: str, prompt: str,
                       context: dict[str, Any]) -> ModelResult:
        if type(context) is not dict or type(prompt) is not str or not prompt.strip() or type(model_id) is not str or not model_id.strip():
            raise EvidenceRejected("invalid provider inputs")
        inputs = detached_plain_data({"model_id": model_id, "prompt": prompt,
                                      "context": context}, self.limits)
        result = await self.provider.generate(**inputs)
        try:
            return detached_result(result, self.limits)
        except EvidenceRejected as error:
            raise ProviderOutcomeUnknown(
                "Returned evidence rejected by bounded plain-data boundary; no automatic retry"
            ) from error
