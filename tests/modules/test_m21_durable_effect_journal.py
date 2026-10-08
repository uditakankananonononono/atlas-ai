"""Slice 4b: durable steps journal intent BEFORE the executor; a crash never re-runs an approved effect."""
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.modules.m21_claire.durable_execution import (
    ClaireExecutionRepository, DurableExecutionOrchestrator, EffectResolutionError, SqlIdempotencyStore,
)
from app.modules.m21_claire.execution import AttemptsExhausted, BoundedExecutor, EffectUnknown, NotExecuted, IdempotencyConflict, IdempotencyStore
from app.modules.m21_claire.models import ActionRequest, Approval, PlanState, RiskLevel, StepState, utcnow
from app.modules.m21_claire.planner import CrossModulePlanner


class Crash(BaseException):
    """Simulates the process dying mid-step: not an Exception, so no FAILED state is saved."""


def engine():
    return create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def repo_on(eng, tenant="default", min_age=0.0):
    r = ClaireExecutionRepository(eng, tenant_id=tenant, intent_min_age_seconds=min_age)
    r.create_schema()
    return r


def plan():
    return CrossModulePlanner().build("ship", [
        ActionRequest("docs", "draft", {"t": "q3"}, "r", RiskLevel.LOW, action_id="draft-1"),
        ActionRequest("mail", "send", {"to": "team"}, "r", RiskLevel.HIGH, ("draft-1",), "send-1"),
    ])


def orch(repo, effects, crash=False, send_exc=None):
    o = DurableExecutionOrchestrator(repo)
    o.register("docs.draft", lambda p: effects.append("draft") or "d")

    def send(p):
        effects.append("send")
        if crash:
            raise Crash()
        if send_exc:
            raise send_exc
        return {"sent": True}
    o.register("mail.send", send)
    return o


def approve(o, p):
    for r in o.prepare(p):
        if r.action_id == "send-1":
            o.approve(p, Approval("ap", r.digest, "user", utcnow(), utcnow() + timedelta(hours=1)))


def crashed(eng):
    effects = []
    repo = repo_on(eng)
    p = plan()
    o = orch(repo, effects, crash=True)
    approve(o, p)
    with pytest.raises(Crash):
        o.execute(p)
    return p, effects


# PROTECTION (base repro: effects == ['draft','send','send'])
def test_crash_mid_step_never_reruns_the_approved_effect():
    eng = engine()
    p, effects = crashed(eng)
    repo2 = repo_on(eng)  # "new process": new repository and orchestrator, same database
    with pytest.raises(EffectUnknown):
        orch(repo2, effects).resume(p.plan_id)
    assert effects == ["draft", "send"]
    after = repo2.load_plan(p.plan_id)
    assert after.state is PlanState.FAILED
    assert [s.state for s in after.steps if s.request.action_id == "send-1"] != [StepState.SUCCEEDED]
    events = [e["event"] for e in repo2.audit_log(p.plan_id)]
    assert "effect_unknown" in events
    assert repo2.effect_states(p.plan_id) == {"draft-1": "committed", "send-1": "intent"}


# NEW: owner resolution
def test_owner_resolves_committed_and_resume_replays_without_rerun():
    eng = engine()
    p, effects = crashed(eng)
    repo2 = repo_on(eng)
    repo2.resolve_effect(p.plan_id, "send-1", "committed", {"sent": True}, confirm_executor_stopped=True)
    done = orch(repo2, effects).resume(p.plan_id)
    assert done.state is PlanState.SUCCEEDED and effects == ["draft", "send"]


def test_owner_resolves_absent_and_resume_runs_once():
    eng = engine()
    p, effects = crashed(eng)
    repo2 = repo_on(eng)
    repo2.resolve_effect(p.plan_id, "send-1", "absent", confirm_executor_stopped=True)
    done = orch(repo2, effects).resume(p.plan_id)
    assert done.state is PlanState.SUCCEEDED and effects == ["draft", "send", "send"]


def test_resolve_is_tenant_scoped_and_only_for_unresolved_effects():
    eng = engine()
    p, _ = crashed(eng)
    with pytest.raises(EffectResolutionError):
        repo_on(eng, "other").resolve_effect(p.plan_id, "send-1", "absent")
    with pytest.raises(EffectResolutionError):
        repo_on(eng).resolve_effect(p.plan_id, "send-1", "maybe")
    r = repo_on(eng)
    r.resolve_effect(p.plan_id, "send-1", "committed", confirm_executor_stopped=True)
    with pytest.raises(EffectResolutionError):
        r.resolve_effect(p.plan_id, "send-1", "absent")  # committed effects cannot be erased


# PROTECTION (reviewer finding): resolving a possibly-live intent row would let a second executor run the step
def test_live_intent_cannot_be_resolved_without_confirmation_and_age():
    eng = engine()
    p, _ = crashed(eng)
    fenced = repo_on(eng, min_age=3600.0)
    for outcome in ("absent", "committed"):
        with pytest.raises(EffectResolutionError):
            fenced.resolve_effect(p.plan_id, "send-1", outcome)  # no confirmation
        with pytest.raises(EffectResolutionError):
            fenced.resolve_effect(p.plan_id, "send-1", outcome, confirm_executor_stopped=True)  # too young
    assert fenced.effect_states(p.plan_id)["send-1"] == "intent"
    with pytest.raises(EffectUnknown):  # the row still blocks any other orchestrator
        orch(repo_on(eng), []).resume(p.plan_id)


def test_unknown_after_reported_failure_resolves_without_the_live_fence():
    eng = engine()
    repo = repo_on(eng, min_age=3600.0)
    p = plan()
    o = orch(repo, [], send_exc=ConnectionError("x"))
    approve(o, p)
    with pytest.raises(AttemptsExhausted):
        o.execute(p)
    repo.resolve_effect(p.plan_id, "send-1", "absent")
    assert repo.effect_states(p.plan_id) == {"draft-1": "committed"}


# PROTECTION
def test_fingerprint_change_on_a_journaled_key_conflicts():
    store = SqlIdempotencyStore(repo_on(engine()))
    store.claim("k", "fp1")
    store.complete("k", "r")
    assert store.claim("k", "fp1") == (False, "r")
    with pytest.raises(IdempotencyConflict):
        store.claim("k", "fp2")


def test_journal_row_is_tenant_scoped_and_stores_no_parameters():
    eng = engine()
    a, b = repo_on(eng, "a"), repo_on(eng, "b")
    assert a.effect_claim("k", "fp") == (True, None)
    assert b.effect_claim("k", "fp") == (True, None)  # same key, different tenant: independent
    with pytest.raises(EffectUnknown):
        a.effect_claim("k", "fp")
    from app.modules.m21_claire.durable_execution import StepEffectRow
    assert {c.name for c in StepEffectRow.__table__.columns}.isdisjoint({"parameters", "request_json", "arguments"})


# PROTECTION (reviewer repro): ConnectionError AFTER the send landed must not allow a second send.
def test_failure_after_body_begins_is_unknown_and_never_reruns():
    eng = engine()
    repo = repo_on(eng)
    effects = []
    p = plan()
    o = orch(repo, effects, send_exc=ConnectionError("smtp://user:secret@host reset after send"))
    approve(o, p)
    with pytest.raises(AttemptsExhausted):
        o.execute(p)
    step = next(s for s in p.steps if s.request.action_id == "send-1")
    assert step.error == "AttemptsExhausted"
    blob = repr(repo.audit_log(p.plan_id)) + repr(repo.load_plan(p.plan_id).steps)
    assert "secret" not in blob and "smtp" not in blob
    assert repo.effect_states(p.plan_id) == {"draft-1": "committed", "send-1": "unknown"}
    # fresh process, same approval: refused, not re-sent
    with pytest.raises(EffectUnknown):
        orch(repo_on(eng), effects).resume(p.plan_id)
    assert effects == ["draft", "send"]
    # a retryable predicate does not turn an unproven failure into a retry
    o2 = DurableExecutionOrchestrator(repo_on(engine()), max_attempts=3, retryable=lambda e: True)
    calls = []
    o2.register("docs.draft", lambda q: "d")
    o2.register("mail.send", lambda q: calls.append(1) or (_ for _ in ()).throw(ConnectionError("x")))
    p2 = plan()
    approve(o2, p2)
    with pytest.raises(AttemptsExhausted):
        o2.execute(p2)
    assert calls == [1]


# NEW: explicit never-ran classification is the only retryable/abandonable failure
def test_not_executed_is_abandoned_and_retry_may_run():
    eng = engine()
    repo = repo_on(eng)
    effects = []
    p = plan()
    o = orch(repo, effects, send_exc=NotExecuted("bad input, nothing written"))
    approve(o, p)
    with pytest.raises(AttemptsExhausted):
        o.execute(p)
    assert repo.effect_states(p.plan_id) == {"draft-1": "committed"}
    done = orch(repo_on(eng), effects).resume(p.plan_id)
    assert done.state is PlanState.SUCCEEDED and effects == ["draft", "send", "send"]


# PROTECTION: in-memory idempotency cannot be re-introduced silently
def test_durable_orchestrator_refuses_a_volatile_store():
    with pytest.raises(ValueError):
        DurableExecutionOrchestrator(repo_on(engine()), executor=BoundedExecutor(IdempotencyStore()))
    DurableExecutionOrchestrator(repo_on(engine()), executor=BoundedExecutor(SqlIdempotencyStore(repo_on(engine()))))
