"""Slice 4b: durable steps journal intent BEFORE the executor; a crash never re-runs an approved effect."""
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.modules.m21_claire.durable_execution import (
    ClaireExecutionRepository, DurableExecutionOrchestrator, EffectResolutionError, SqlIdempotencyStore,
)
from app.modules.m21_claire.execution import AttemptsExhausted, BoundedExecutor, EffectUnknown, IdempotencyConflict, IdempotencyStore
from app.modules.m21_claire.models import ActionRequest, Approval, PlanState, RiskLevel, StepState, utcnow
from app.modules.m21_claire.planner import CrossModulePlanner


class Crash(BaseException):
    """Simulates the process dying mid-step: not an Exception, so no FAILED state is saved."""


def engine():
    return create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def repo_on(eng, tenant="default"):
    r = ClaireExecutionRepository(eng, tenant_id=tenant)
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
    repo2.resolve_effect(p.plan_id, "send-1", "committed", {"sent": True})
    done = orch(repo2, effects).resume(p.plan_id)
    assert done.state is PlanState.SUCCEEDED and effects == ["draft", "send"]


def test_owner_resolves_absent_and_resume_runs_once():
    eng = engine()
    p, effects = crashed(eng)
    repo2 = repo_on(eng)
    repo2.resolve_effect(p.plan_id, "send-1", "absent")
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
    r.resolve_effect(p.plan_id, "send-1", "committed")
    with pytest.raises(EffectResolutionError):
        r.resolve_effect(p.plan_id, "send-1", "absent")  # committed effects cannot be erased


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


def test_normal_exception_is_not_landed_and_retry_may_run_with_class_name_only_error():
    eng = engine()
    repo = repo_on(eng)
    effects = []
    p = plan()
    o = orch(repo, effects, send_exc=ConnectionError("smtp://user:secret@host down"))
    approve(o, p)
    with pytest.raises(AttemptsExhausted):
        o.execute(p)
    step = next(s for s in p.steps if s.request.action_id == "send-1")
    assert step.error == "AttemptsExhausted"
    blob = repr(repo.audit_log(p.plan_id)) + repr(repo.load_plan(p.plan_id).steps)
    assert "secret" not in blob and "smtp" not in blob
    assert repo.effect_states(p.plan_id) == {"draft-1": "committed"}  # abandoned row removed


# PROTECTION: in-memory idempotency cannot be re-introduced silently
def test_durable_orchestrator_refuses_a_volatile_store():
    with pytest.raises(ValueError):
        DurableExecutionOrchestrator(repo_on(engine()), executor=BoundedExecutor(IdempotencyStore()))
    DurableExecutionOrchestrator(repo_on(engine()), executor=BoundedExecutor(SqlIdempotencyStore(repo_on(engine()))))
