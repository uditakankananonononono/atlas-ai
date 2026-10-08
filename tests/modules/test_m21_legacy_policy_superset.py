"""Slice 4a: the legacy ActionPolicy / orchestrator / Service.local_action only ever ADD gates relative to the runtime."""
import asyncio
from datetime import datetime, timezone

import pytest

from app.modules.m21_claire import (
    ActionPolicy, ActionRequest, CrossModulePlanner, ExecutionOrchestrator, PolicyViolation, ReviewMismatch,
)
from app.modules.m21_claire.runtime import gates
from app.modules.m21_claire.service import Service

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def req(action, module="m05", tags=None):
    return ActionRequest(module, action, {"policy_tags": tags} if tags else {}, "t")


# PROTECTION: these ran with no approval on base (reproduced before the fix).
@pytest.mark.parametrize("action", ["notify_customer", "tweet", "dm", "reply", "email", "sendEmail", "charge_card",
                                    "refund", "pay", "subscribe", "post_update", "message_user"])
def test_comms_and_payment_verbs_need_approval_on_legacy_path(action):
    d = ActionPolicy().evaluate(req(action))
    assert d.allowed and d.requires_approval


@pytest.mark.parametrize("action,tags", [("research", ["notify"]), ("draft", ["charge"])])
def test_declared_tags_raise_the_gate(action, tags):
    assert ActionPolicy().evaluate(req(action, tags=tags)).requires_approval


# PROTECTION: split / camelCase hard-blocked names slipped through the glued tokenizer on base.
@pytest.mark.parametrize("action,module,tags", [
    ("self_bot_poster", "claire", None), ("fake_account_creator", "m05", None), ("impersonateUser", "m05", None),
    ("research", "m05", ["self_bot"]), ("research", "m05", ["fakeAccount"]), ("research", "self_bot", None)])
def test_hard_blocked_names_cannot_slip_through(action, module, tags):
    assert not ActionPolicy().evaluate(req(action, module, tags)).allowed


def test_orchestrator_refuses_unapproved_comms_verb_and_blocked_names():
    orch = ExecutionOrchestrator(clock=lambda: NOW)
    ran = []
    orch.register("m05.notify_customer", lambda p: ran.append(1))
    plan = CrossModulePlanner().build("g", [req("notify_customer")])
    orch.prepare(plan)
    with pytest.raises(ReviewMismatch):
        orch.execute(plan)
    assert not ran
    with pytest.raises(PolicyViolation):
        CrossModulePlanner().build("g", [req("self_bot_poster", "claire")])


# PROTECTION: the runtime and the legacy policy share one vocabulary, so legacy can never be looser than the runtime.
def test_lexical_only_runtime_vocabulary_and_splitter_are_the_legacy_ones():
    # Lexical guarantee only: declaration metadata (spends_money etc.) is runtime-only. Glued names (sendemail) are unrecognised by both.
    from app.modules.m21_claire import policy
    assert gates._PAYMENT_TOKENS is policy.PAYMENT_TOKENS and gates._COMMS_TOKENS is policy.COMMS_TOKENS
    assert gates._words is policy.name_words


# REGRESSION: legacy remains stricter than the runtime owner ruling for destructive verbs, and benign names stay free.
@pytest.mark.parametrize("action", ["delete", "install", "execute", "deploy", "change_permissions"])
def test_legacy_destructive_verbs_still_need_approval(action):
    assert ActionPolicy().evaluate(req(action)).requires_approval


@pytest.mark.parametrize("action", ["research", "draft", "summarize", "notebook_search", "compose_report"])
def test_benign_names_are_not_gated(action):
    assert not ActionPolicy().evaluate(req(action)).requires_approval


class _Client:
    def __init__(self): self.executed = []
    async def capabilities(self): return {"dm", "self_bot_post", "read_file"}
    async def preview(self, action): return {}
    async def execute(self, action, token): self.executed.append(action); return {"ok": True}
    async def audit(self, event): pass


class _Approvals:
    def __init__(self): self.items = []
    def put(self, item): self.items.append(item); return item
    def list(self): return self.items


def _service(client):
    class _Cog: pass
    svc = Service(_Cog(), _Approvals(), client)
    svc.goals["g"] = type("G", (), {"evidence": []})()
    return svc


# PROTECTION: local_action("dm") executed with no approval on base.
def test_local_action_gates_comms_verb_and_blocks_standing_no():
    client = _Client()
    svc = _service(client)
    with pytest.raises(ValueError):  # gated, and no approval route exists for it: fails closed, never executes
        asyncio.run(svc.local_action("g", {"kind": "dm"}))
    assert client.executed == []
    with pytest.raises(ValueError):
        asyncio.run(svc.local_action("g", {"kind": "self_bot_post"}))
    assert client.executed == []
    # CONVERTED (slice 15): an arbitrary token no longer lets the gated verb proceed (dm is blocked by the legacy policy before any approval check);
    # a plain read on a legacy goal is still never gated
    with pytest.raises(ValueError):
        asyncio.run(svc.local_action("g", {"kind": "dm"}, "tok"))
    asyncio.run(svc.local_action("g", {"kind": "read_file"}))
    assert [a["kind"] for a in client.executed] == ["read_file"]
