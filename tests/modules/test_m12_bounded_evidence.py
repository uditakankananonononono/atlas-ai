"""Local boundary tests. Scripted providers are test doubles, not real inference."""
import asyncio
import math
import pytest

from app.core.providers import ProviderOutcomeUnknown, ProviderError
from app.modules.m12_ai_research_lab.bounded_evidence import (
    BoundedProvider, EvidenceLimits, EvidenceRejected,
    detached_plain_data, detached_result,
)
from app.modules.m12_ai_research_lab.models import (
    ModelResult, ModelCapability, RouteRequest, TaskType,
)
from app.modules.m12_ai_research_lab.router import ModelRouter
from app.modules.m12_ai_research_lab.executor import ResearchExecutor, RetryPolicy


class ScriptedProvider:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def good():
    return ModelResult("answer", "reported", .9, [-.1], {"tokens": 2},
                       {"nested": [{"evidence": "λ"}]})


def test_deep_detachment_and_alias_copy():
    shared = {"a": [1, True, None, 1.5, "hello"]}
    original = {"left": shared, "right": shared}
    copy = detached_plain_data(original)
    assert copy == original
    assert copy["left"] is not copy["right"]
    copy["left"]["a"].append(2)
    assert len(original["left"]["a"]) == 5


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, b"bytes", (1,), {1: "a"}, {"x": object()}, "\ud800", 2**257])
def test_reject_non_plain(value):
    with pytest.raises(EvidenceRejected):
        detached_plain_data(value)


@pytest.mark.parametrize("kind", ["list", "dict", "mixed"])
def test_cycle_rejected(kind):
    data = [] if kind == "list" else {}
    if kind == "list":
        data.append(data)
    elif kind == "dict":
        data["self"] = data
    else:
        data["self"] = [data]
    with pytest.raises(EvidenceRejected, match="cycle"):
        detached_plain_data(data)


def test_ten_thousand_depth_controlled_not_recursion_error():
    data = None
    for _ in range(10000):
        data = [data]
    with pytest.raises(EvidenceRejected, match="depth"):
        detached_plain_data(data)


def test_exact_depth_boundary():
    assert detached_plain_data([[1]], EvidenceLimits(max_depth=2)) == [[1]]
    with pytest.raises(EvidenceRejected, match="depth"):
        detached_plain_data([[[1]]], EvidenceLimits(max_depth=2))


def test_item_counts_include_mapping_keys():
    assert detached_plain_data({"a": 1}, EvidenceLimits(max_items=3)) == {"a": 1}
    with pytest.raises(EvidenceRejected, match="item"):
        detached_plain_data({"a": 1}, EvidenceLimits(max_items=2))
    with pytest.raises(EvidenceRejected, match="item"):
        detached_plain_data([None] * 100000)


def test_aggregate_utf8_keys_and_values():
    assert detached_plain_data({"λ": "😀"}, EvidenceLimits(max_utf8_bytes=6)) == {"λ": "😀"}
    with pytest.raises(EvidenceRejected, match="byte"):
        detached_plain_data({"λ": "😀"}, EvidenceLimits(max_utf8_bytes=5))
    with pytest.raises(EvidenceRejected, match="byte"):
        detached_plain_data(["abc", "def"], EvidenceLimits(max_utf8_bytes=5))


@pytest.mark.parametrize("field", ["max_depth", "max_items", "max_utf8_bytes", "max_integer_bits"])
@pytest.mark.parametrize("value", [0, -1, True, 1.2])
def test_limits_validated(field, value):
    with pytest.raises(ValueError):
        EvidenceLimits(**{field: value})


def test_custom_conversion_never_invoked():
    class Hostile(dict):
        def items(self):
            raise AssertionError("must not invoke custom iteration")
        def __repr__(self):
            raise AssertionError("must not invoke representation")
    with pytest.raises(EvidenceRejected):
        detached_plain_data({"nested": Hostile()})


@pytest.mark.parametrize("field,value", [
    ("usage", {"tokens": -1}), ("usage", {"tokens": True}),
    ("logprobs", [True]), ("logprobs", [math.nan]),
    ("confidence", math.nan), ("confidence", True),
    ("metadata", {"x": object()}), ("text", "\ud800"),
    ("model_id", "\ud800"), ("metadata", []),
])
def test_bad_result(field, value):
    result = good()
    setattr(result, field, value)
    with pytest.raises(EvidenceRejected):
        detached_result(result)


def test_result_detached():
    result = good()
    copy = detached_result(result)
    copy.metadata["nested"][0]["evidence"] = "changed"
    copy.usage["tokens"] = 99
    copy.logprobs.append(-2)
    assert result == good()


def test_result_subclass_rejected():
    class Extended(ModelResult):
        pass
    with pytest.raises(EvidenceRejected):
        detached_result(Extended("x", "m"))


@pytest.mark.asyncio
async def test_input_refused_before_dispatch():
    provider = ScriptedProvider(good())
    with pytest.raises(EvidenceRejected):
        await BoundedProvider(provider).generate(model_id="m", prompt="p", context={"bad": object()})
    assert provider.calls == []


@pytest.mark.asyncio
async def test_inputs_detached_and_valid_output():
    provider = ScriptedProvider(good())
    context = {"list": [1]}
    output = await BoundedProvider(provider).generate(model_id="m", prompt="p", context=context)
    provider.calls[0]["context"]["list"].append(2)
    assert context == {"list": [1]}
    assert output == good() and output is not provider.result


@pytest.mark.asyncio
async def test_executor_invalid_return_no_fallback():
    result = good()
    result.metadata["bad"] = object()
    provider = ScriptedProvider(result)
    catalog = [ModelCapability(m, frozenset({TaskType.RESEARCH}), 1000, 0, 1, .9)
               for m in ("first", "second")]
    executor = ResearchExecutor(ModelRouter(catalog), BoundedProvider(provider),
                                RetryPolicy(base_delay_seconds=0))
    with pytest.raises(ProviderOutcomeUnknown):
        await executor.execute(RouteRequest(TaskType.RESEARCH, 1, 1, 100, "t"), "task")
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_budget_invalid_return_unknown():
    provider = ScriptedProvider(good())
    with pytest.raises(ProviderOutcomeUnknown) as error:
        await BoundedProvider(provider, EvidenceLimits(max_utf8_bytes=40)).generate(
            model_id="m", prompt="p", context={})
    assert isinstance(error.value.__cause__, EvidenceRejected)
    assert len(provider.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("exception", [ProviderError("preflight"), ProviderOutcomeUnknown("transport"), asyncio.CancelledError()])
async def test_provider_exception_preserved(exception):
    class Failing:
        async def generate(self, **kwargs):
            raise exception
    with pytest.raises(type(exception)) as error:
        await BoundedProvider(Failing()).generate(model_id="m", prompt="p", context={})
    assert error.value is exception


@pytest.mark.asyncio
async def test_executor_good_result_succeeds_without_mutating_provider_metadata():
    provider = ScriptedProvider(good())
    catalog = [ModelCapability("requested", frozenset({TaskType.RESEARCH}), 1000, 0, 1, .9)]
    executor = ResearchExecutor(ModelRouter(catalog), BoundedProvider(provider),
                                RetryPolicy(base_delay_seconds=0))
    result = await executor.execute(RouteRequest(TaskType.RESEARCH, 1, 1, 100, "t"), "task")
    assert result.text == "answer"
    assert result.metadata["attempts"] == 1
    assert result.metadata["requested_model_id"] == "requested"
    assert "attempts" not in provider.result.metadata
    # Different reported/requested IDs are NOT proof of authenticity.
    assert result.model_id == "reported"


@pytest.mark.asyncio
async def test_executor_missing_confidence_still_requires_review():
    from app.modules.m12_ai_research_lab.executor import ConfidenceUnavailable
    result = good()
    result.confidence = None
    result.logprobs = []
    provider = ScriptedProvider(result)
    catalog = [ModelCapability("requested", frozenset({TaskType.RESEARCH}), 1000, 0, 1, .9)]
    executor = ResearchExecutor(ModelRouter(catalog), BoundedProvider(provider))
    with pytest.raises(ConfidenceUnavailable) as error:
        await executor.execute(RouteRequest(TaskType.RESEARCH, 1, 1, 100, "t"), "task")
    assert error.value.result.metadata["review_required"] is True
    assert len(provider.calls) == 1


def test_increased_depth_limit_is_iterative():
    data = None
    for _ in range(1200):
        data = [data]
    result = detached_plain_data(data, EvidenceLimits(max_depth=1200, max_items=1201))
    for _ in range(1200):
        result = result[0]
    assert result is None


def test_exact_integer_bit_boundary():
    assert detached_plain_data(255, EvidenceLimits(max_integer_bits=8)) == 255
    assert detached_plain_data(-255, EvidenceLimits(max_integer_bits=8)) == -255
    with pytest.raises(EvidenceRejected):
        detached_plain_data(256, EvidenceLimits(max_integer_bits=8))
