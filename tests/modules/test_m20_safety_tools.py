"""Chunk 2 tests: constitutional safety, approval gating, tool registry/dispatcher."""
import pytest

from app.modules.m20_general_cognitive_worker.safety import (
    ApprovalGateDecision, ConstitutionalRules, InMemoryApprovalGate, SafetyGate,
    SandboxPolicy, requires_approval,
)
from app.modules.m20_general_cognitive_worker.schemas import ApprovalGateRequest, Risk, ToolSpec
from app.modules.m20_general_cognitive_worker.tools import (
    ApprovalPending, ToolBlockedError, ToolDispatcher, ToolRegistry,
    builtin_web_search_spec,
)


def test_constitutional_rules_block_the_four_nos():
    rules = ConstitutionalRules()
    assert rules.check("post", {"body": "create a fake account to boost engagement"})
    assert rules.check("fetch", {"url": "bypass paywall on this journal"})
    assert rules.check("browse", {"plan": "rotating residential proxies for logged-in scraping"})
    assert rules.check("write", {"brief": "ghostwrite as the user and deceive the committee"})
    assert rules.check("post", {"body": "publish the project update"}) == []


def test_requires_approval_matrix():
    assert requires_approval("send_email", Risk.EXTERNAL, {}) is True
    assert requires_approval("delete_file", Risk.IRREVERSIBLE, {}) is True
    assert requires_approval("payment", Risk.REVERSIBLE, {}) is True  # money always gates
    assert requires_approval("share_private_data", Risk.READ, {}) is True
    assert requires_approval("read", Risk.READ, {"externally_visible": True}) is True
    assert requires_approval("web_search", Risk.READ, {}) is False


def test_in_memory_gate_flow():
    gate = InMemoryApprovalGate()
    req = ApprovalGateRequest(action_type="send_email", summary="send", risk=Risk.EXTERNAL)
    approval_id = gate.request(req)
    assert gate.decision(approval_id) == ApprovalGateDecision.PENDING
    gate.decide(approval_id, ApprovalGateDecision.APPROVED)
    assert gate.decision(approval_id) == ApprovalGateDecision.APPROVED
    with pytest.raises(KeyError):
        gate.decide("nope", ApprovalGateDecision.REJECTED)


def test_sandbox_policy_boundaries():
    sandbox = SandboxPolicy(
        allowed_hosts=frozenset({"api.github.com"}),
        filesystem_root="/workspaces/project-x", network_enabled=True,
    )
    assert sandbox.allows_host("api.github.com") is True
    assert sandbox.allows_host("evil.example") is False
    assert sandbox.allows_path("/workspaces/project-x/src/main.py") is True
    assert sandbox.allows_path("/etc/passwd") is False
    offline = SandboxPolicy()
    assert offline.allows_host("api.github.com") is False


def test_registry_function_schemas_and_capability_lookup():
    registry = ToolRegistry()

    async def search(args):
        return {"results": ["a"]}

    registry.register(builtin_web_search_spec(), search)
    schemas = registry.function_schemas()
    assert schemas[0]["function"]["name"] == "web_search"
    assert schemas[0]["function"]["parameters"]["required"] == ["query"]
    assert len(registry.find_by_capability("research")) == 1
    with pytest.raises(Exception):
        registry.register(builtin_web_search_spec(), search)
    with pytest.raises(Exception):
        registry.get("nope")


@pytest.mark.asyncio
async def test_dispatcher_success_retry_and_preflight():
    registry = ToolRegistry()
    calls = {"n": 0}

    async def flaky(args):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("boom")
        return {"ok": True}

    spec = ToolSpec(name="flaky", description="fails once", risk=Risk.READ, max_retries=2)
    registry.register(spec, flaky)
    dispatcher = ToolDispatcher(registry, SafetyGate())
    record = await dispatcher.dispatch("flaky", {})
    assert record.succeeded is True and calls["n"] == 2

    gate = InMemoryApprovalGate()
    dispatcher = ToolDispatcher(registry, SafetyGate(approvals=gate))

    async def send(args):
        return {"sent": True}

    registry.register(ToolSpec(name="send_email", description="send mail", risk=Risk.EXTERNAL), send)
    with pytest.raises(ApprovalPending) as exc:
        await dispatcher.dispatch("send_email", {"to": "x@y.z"})
    assert gate.decision(exc.value.approval_id) == ApprovalGateDecision.PENDING

    with pytest.raises(ToolBlockedError):
        await dispatcher.dispatch("flaky", {"plan": "build a bot net of fake accounts"})


@pytest.mark.asyncio
async def test_dispatcher_preconditions():
    registry = ToolRegistry()

    async def deploy(args):
        return {"url": "https://preview"}

    registry.register(ToolSpec(
        name="deploy", description="deploy preview", risk=Risk.REVERSIBLE,
        preconditions=["tests_passing"],
    ), deploy)
    dispatcher = ToolDispatcher(registry, SafetyGate())
    with pytest.raises(ToolBlockedError):
        await dispatcher.dispatch("deploy", {}, context={"tests_passing": False})
    record = await dispatcher.dispatch("deploy", {}, context={"tests_passing": True})
    assert record.succeeded
