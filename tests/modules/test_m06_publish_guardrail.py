"""m06 platform write goes through the guardrail outbound gate (groups 136/139): refusals, not just success."""
from app.runtime.guardrails.enforcer import GuardrailEnforcer

from app.modules.m06_social_media_manager.scheduler import STATUS_FAILED, STATUS_PUBLISHED, Scheduler
from app.modules.m06_social_media_manager.service import MemorySocialRepository

from tests.modules.test_m06_scheduler import (  # noqa: F401
    NOW, FakeAdapter, FakeAdapterFactory, FakeDecisions, create_entry, make_plan, make_scheduler)


def _approved(scheduler, decisions):
    entry = create_entry(scheduler, make_plan())
    decisions.statuses["approval-1"] = "approved"
    scheduler.sync_decisions()
    return entry


def test_publish_dispatched_through_gate_and_ledgered():
    adapter = FakeAdapter()
    scheduler, repo, decisions = make_scheduler(adapter)
    entry = _approved(scheduler, decisions)
    assert len(scheduler.execute_due(NOW)) == 1 and len(adapter.published) == 1
    assert repo.get_schedule(entry.id).status == STATUS_PUBLISHED
    assert scheduler._enforcer.ledger("outbound")[-1]["record"]["verdict"] == "dispatched"


def test_publish_refused_when_authority_rejects_adapter_never_called():
    adapter = FakeAdapter()
    repo, decisions = MemorySocialRepository(), FakeDecisions()
    sch = Scheduler(repository=repo, decisions=decisions, adapter_factory=FakeAdapterFactory(adapter),
                    clock=lambda: NOW, enforcer=GuardrailEnforcer(authority_check=lambda r, d: False))
    entry = _approved(sch, decisions)
    assert sch.execute_due(NOW) == []
    got = repo.get_schedule(entry.id)
    assert got.status == STATUS_FAILED and "authority_rejected" in got.failure
    assert adapter.published == []


def test_publish_refused_when_enforcer_has_no_authority_hook():
    adapter = FakeAdapter()
    repo, decisions = MemorySocialRepository(), FakeDecisions()
    sch = Scheduler(repository=repo, decisions=decisions, adapter_factory=FakeAdapterFactory(adapter),
                    clock=lambda: NOW, enforcer=GuardrailEnforcer())
    entry = _approved(sch, decisions)
    sch.execute_due(NOW)
    assert "authority_hook_required" in repo.get_schedule(entry.id).failure and adapter.published == []


def test_publish_refused_when_platform_terms_undeclared():
    adapter = FakeAdapter()
    repo, decisions = MemorySocialRepository(), FakeDecisions()
    sch = Scheduler(repository=repo, decisions=decisions, adapter_factory=FakeAdapterFactory(adapter),
                    clock=lambda: NOW,
                    outbound_declarations={"tos": {}, "rate_limits": {}, "consent": [], "recent_actions": []})
    entry = _approved(sch, decisions)
    sch.execute_due(NOW)
    assert "refused:denied" in repo.get_schedule(entry.id).failure and adapter.published == []


def test_publish_refused_when_approval_revoked_after_sync():
    adapter = FakeAdapter()
    scheduler, repo, decisions = make_scheduler(adapter)
    entry = _approved(scheduler, decisions)
    decisions.statuses["approval-1"] = "denied"
    assert scheduler.execute_due(NOW) == [] and adapter.published == []


def _mutate_after_bind(scheduler, mutate):
    """Wrap dispatch_outbound so `mutate(action)` runs after the digest is bound, before the gate checks it."""
    real = scheduler._enforcer.dispatch_outbound

    def wrapped(action, *args, **kwargs):
        mutate(action)
        return real(action, *args, **kwargs)

    scheduler._enforcer.dispatch_outbound = wrapped


def test_default_enforcer_refuses_approval_revoked_after_bind():
    adapter = FakeAdapter()
    scheduler, repo, decisions = make_scheduler(adapter)
    entry = _approved(scheduler, decisions)
    _mutate_after_bind(scheduler, lambda a: decisions.statuses.__setitem__("approval-1", "denied"))
    assert scheduler.execute_due(NOW) == []
    assert adapter.published == []
    assert "authority_rejected" in repo.get_schedule(entry.id).failure


def test_default_enforcer_refuses_payload_edited_after_bind():
    adapter = FakeAdapter()
    scheduler, repo, decisions = make_scheduler(adapter)
    entry = _approved(scheduler, decisions)
    _mutate_after_bind(scheduler, lambda a: a.__setitem__("text", a["text"] + " (edited)"))
    assert scheduler.execute_due(NOW) == []
    assert adapter.published == []
    assert "authority_rejected" in repo.get_schedule(entry.id).failure


import pytest

@pytest.mark.parametrize("field", ["text", "format", "alt_texts", "media_urls", "link", "thread_chunks"])
def test_every_publish_field_is_digest_bound(field):
    adapter = FakeAdapter()
    scheduler, repo, decisions = make_scheduler(adapter)
    entry = _approved(scheduler, decisions)
    def mutate(action):
        action[field] = ["edited"] if isinstance(action[field], list) else "edited"
    _mutate_after_bind(scheduler, mutate)
    assert scheduler.execute_due(NOW) == [] and adapter.published == []
    assert "authority_rejected" in repo.get_schedule(entry.id).failure


def test_explicit_empty_declarations_refuse_publish():
    adapter = FakeAdapter()
    repo, decisions = MemorySocialRepository(), FakeDecisions()
    scheduler = Scheduler(repository=repo, decisions=decisions,
                          adapter_factory=FakeAdapterFactory(adapter), clock=lambda: NOW,
                          outbound_declarations={})
    entry = _approved(scheduler, decisions)
    assert scheduler.execute_due(NOW) == [] and adapter.published == []
    assert "refused:denied" in repo.get_schedule(entry.id).failure


def test_published_request_equals_gate_canonical_payload():
    from app.runtime.guardrails._fields import payload_sha256
    adapter = FakeAdapter()
    scheduler, repo, decisions = make_scheduler(adapter)
    _approved(scheduler, decisions)
    admitted = {}
    real = scheduler._enforcer.dispatch_outbound
    def capture(action, *args, **kwargs):
        admitted.update(action)
        return real(action, *args, **kwargs)
    scheduler._enforcer.dispatch_outbound = capture
    assert len(scheduler.execute_due(NOW)) == 1
    request = adapter.published[0]
    for field in ("platform", "text", "format", "link", "media_urls", "alt_texts", "thread_chunks"):
        value = getattr(request, field)
        assert (list(value) if isinstance(value, tuple) else value) == admitted[field]
    assert scheduler._enforcer.ledger("outbound")[-1]["record"]["action_digest"] == payload_sha256(
        {k: v for k, v in admitted.items() if k != "id"})


def test_publish_callback_consumes_gate_action_not_entry_or_detached_request():
    class Gate:
        def dispatch_outbound(self, action, declarations, *, effect, **kwargs):
            # Contract probe, not a production admission.
            action.update(text="canonical", format="post", link="https://example.test",
                          media_urls=["media"], alt_texts=["alt"], thread_chunks=["chunk"])
            return effect(action)
    adapter = FakeAdapter()
    repo, decisions = MemorySocialRepository(), FakeDecisions()
    scheduler = Scheduler(repository=repo, decisions=decisions, adapter_factory=FakeAdapterFactory(adapter),
                          clock=lambda: NOW, enforcer=Gate())
    _approved(scheduler, decisions)
    assert len(scheduler.execute_due(NOW)) == 1
    request = adapter.published[0]
    assert (request.text, request.format, request.link) == ("canonical", "post", "https://example.test")
    assert request.media_urls == ("media",) and request.alt_texts == ("alt",) and request.thread_chunks == ("chunk",)
