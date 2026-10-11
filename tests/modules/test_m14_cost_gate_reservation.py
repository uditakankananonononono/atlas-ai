"""M14 TaskRunner cost-gate reservation pins.

Audit defect: run() pre-flighted can_afford_call() with ZERO estimate and the
executor ran before actuals were recorded - a $1-cap ledger accepted
pre-flight, the executor spent $2, and the post-hoc record raised with the
ledger cost still 0. The gate must bind via hold/reserve (the sandbox-wave
model): conservative pre-charge before execution, settle with actuals at
completion, release when the call never happened.
"""
import pytest

from app.modules.m14_project_builder.budgets import (
    BudgetError, BudgetExceeded, BudgetLedger, BudgetLimits)
from app.modules.m14_project_builder.runner import RunnerError, TaskOutput, TaskRunner
from app.modules.m14_project_builder.schemas import ProjectPlan, ProjectTask


def task(tid, deps=()):
    return ProjectTask(id=tid, title=f"Task {tid}", objective=f"Do {tid}",
                       agent_kind="coder", dependencies=list(deps),
                       acceptance_criteria=["tests pass"])


def plan(*tasks):
    return ProjectPlan(goal="g", tasks=list(tasks), quality_gates=["review"])


def make_runner(executor, cost=25.0, calls=50, estimator=None):
    ledger = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=calls,
        max_runtime_seconds=3600, max_cost_usd=cost))
    return TaskRunner(ledger, executor, cost_estimator=estimator,
                      auto_approve=True), ledger


def test_reservation_blocks_overspend_pre_execution():
    ran = []

    def executor(t):
        ran.append(t.id)
        return TaskOutput(success=True, summary="done", cost_usd=2.0)

    # honest estimate $2 against a $1 cap: the call must never start
    runner, ledger = make_runner(executor, cost=1.0, estimator=lambda t: 2.0)
    report = runner.run(plan(task("a")))
    assert report.stopped_reason == "budget_exhausted"
    assert ran == []                      # executor never invoked
    assert ledger.status().cost_usd_used == 0.0   # nothing charged
    assert ledger.status().agent_calls_used == 0


def test_actual_cost_recorded_and_above_estimate_overage_truthful():
    def executor(t):
        return TaskOutput(success=True, summary="done", cost_usd=2.0)

    # default conservative estimate (full remaining headroom = $1 reserved);
    # executor reports $2 actual: the ledger must record the real $2 spend,
    # not be left at 0 like the old post-hoc path
    runner, ledger = make_runner(executor, cost=1.0)
    report = runner.run(plan(task("a"), task("b", ("a",))))
    assert report.stopped_reason == "budget_exhausted"
    assert ledger.status().cost_usd_used == pytest.approx(2.0)
    assert ledger.status().agent_calls_used == 1
    assert "cost_usd" in ledger.status().exhausted_dimensions


def test_settle_reconciles_refund_to_actuals():
    def executor(t):
        return TaskOutput(success=True, summary="done", cost_usd=0.25)

    runner, ledger = make_runner(executor, cost=1.0)
    report = runner.run(plan(task("a"), task("b", ("a",)), task("c", ("b",))))
    assert report.stopped_reason == "completed"
    status = ledger.status()
    assert status.cost_usd_used == pytest.approx(0.75)
    assert status.agent_calls_used == 3
    # reserve/settle event stream reconciles to the final recorded cost
    cost_events = [e.amount for e in ledger.events() if e.dimension == "cost_usd"]
    assert sum(cost_events) == pytest.approx(0.75)
    assert any(a > 0 for a in cost_events) and any(a < 0 for a in cost_events)


def test_executor_exception_retains_hold_as_unknown_spend():
    def executor(t):
        raise RuntimeError("provider down")

    # the runner cannot know whether the provider was charged, so the hold is
    # RETAINED conservatively - never a free-budget refund on the unknown path
    runner, ledger = make_runner(executor, cost=1.0)
    with pytest.raises(RuntimeError):
        runner.run(plan(task("a")))
    status = ledger.status()
    assert status.agent_calls_used == 1
    assert status.cost_usd_used == pytest.approx(1.0)  # full headroom was held
    notes = [e.note for e in ledger.events()]
    assert any("unknown" in n for n in notes)
    # the spent-unknown hold consumes budget: no headroom remains
    assert ledger.status().cost_usd_remaining == pytest.approx(0.0)


def test_estimator_must_return_positive_finite():
    ok = TaskOutput(success=True, summary="done", cost_usd=0.1)
    for bad in (0.0, -0.5, float("nan"), float("inf"), True):
        runner, _ = make_runner(lambda t: ok, cost=1.0, estimator=lambda t: bad)
        with pytest.raises(RunnerError):
            runner.run(plan(task("a")))


def test_reserve_rejects_dishonest_estimate_at_ledger_level():
    ledger = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=1.0))
    for bad in (-0.1, float("nan"), float("inf"), True):
        with pytest.raises(BudgetError):
            ledger.reserve_call(bad)


def test_zero_cost_budget_still_allows_free_calls():
    def executor(t):
        return TaskOutput(success=True, summary="done", cost_usd=0.0)

    runner, ledger = make_runner(executor, cost=0.0)
    report = runner.run(plan(task("a")))
    assert report.stopped_reason == "completed"
    assert ledger.status().cost_usd_used == 0.0


def test_over_cap_actual_on_final_task_not_reported_completed():
    def executor(t):
        return TaskOutput(success=True, summary="done", cost_usd=2.0)

    # the over-cap spend is the LAST task: with no next reserve to trip, only
    # the settle-time raise stops the run from claiming "completed"
    runner, ledger = make_runner(executor, cost=1.0)
    report = runner.run(plan(task("a")))
    assert report.stopped_reason == "budget_exhausted"
    assert ledger.status().cost_usd_used == pytest.approx(2.0)


# -- reservation integrity pins (auditor-4 core findings) ----------------------


def _reserve(ledger, amount=0.4):
    return ledger.reserve_call(amount, note="pin")


def test_double_release_rejected_with_no_ledger_change():
    ledger = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=1.0))
    reservation = _reserve(ledger)
    ledger.release_call(reservation)
    snapshot = (ledger.status().cost_usd_used, ledger.status().agent_calls_used)
    with pytest.raises(BudgetError):
        ledger.release_call(reservation)
    with pytest.raises(BudgetError):
        ledger.settle_call(reservation, 0.1)
    after = (ledger.status().cost_usd_used, ledger.status().agent_calls_used)
    assert after == snapshot == (0.0, 0)  # no -1 calls / negative cost


def test_double_settle_rejected():
    ledger = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=1.0))
    reservation = _reserve(ledger)
    ledger.settle_call(reservation, 0.4)
    snapshot = ledger.status().cost_usd_used
    with pytest.raises(BudgetError):
        ledger.settle_call(reservation, 0.1)
    assert ledger.status().cost_usd_used == snapshot


def test_forged_reservation_rejected():
    from app.modules.m14_project_builder.budgets import CallReservation
    ledger = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=1.0))
    _reserve(ledger)  # registry holds one active token; the forgery is not it
    snapshot = (ledger.status().cost_usd_used, ledger.status().agent_calls_used)
    for forged in (CallReservation(ledger, 999999), CallReservation(None, 1),
                   object(), "reservation"):
        with pytest.raises(BudgetError):
            ledger.settle_call(forged, 0.0)
        with pytest.raises(BudgetError):
            ledger.release_call(forged)
    after = (ledger.status().cost_usd_used, ledger.status().agent_calls_used)
    assert after == snapshot  # no negative cost / phantom headroom


def test_cross_ledger_reservation_rejected():
    one = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=1.0))
    two = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=1.0))
    reservation = _reserve(one)
    with pytest.raises(BudgetError):
        two.release_call(reservation)
    with pytest.raises(BudgetError):
        two.settle_call(reservation, 0.1)
    # target ledger untouched; source reservation still active and usable once
    assert two.status().cost_usd_used == 0.0 and two.status().agent_calls_used == 0
    one.settle_call(reservation, 0.4)
    assert one.status().cost_usd_used == pytest.approx(0.4)


def test_reservation_amount_not_mutable_or_public():
    ledger = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=1.0))
    reservation = _reserve(ledger)
    assert not hasattr(reservation, "amount_usd")
    with pytest.raises(AttributeError):
        reservation.amount_usd = 100.0
    with pytest.raises(AttributeError):
        reservation._amount = 100.0
    ledger.release_call(reservation)
    assert ledger.status().cost_usd_used == 0.0


# --- Auditor-4 re-audit pins: issued-token identity binding ---
# The registry matched integer id only: CallReservation(ledger, active_id)
# was a working clone. Identity must bind to the issued object itself.

def test_clone_with_genuine_active_id_rejected_on_all_actions():
    from app.modules.m14_project_builder.budgets import CallReservation
    for method in ("release_call", "settle_call", "abandon_call"):
        ledger = BudgetLedger(BudgetLimits(
            max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=10.0))
        real = _reserve(ledger, 3.0)
        clone = CallReservation(ledger, real._token_id)
        before = ledger.status()
        args = (0.0,) if method == "settle_call" else ()
        with pytest.raises(BudgetError):
            getattr(ledger, method)(clone, *args)
        after = ledger.status()
        # zero ledger change: no refund, no consumed state, no phantom headroom
        assert (after.cost_usd_used, after.agent_calls_used) == \
               (before.cost_usd_used, before.agent_calls_used)
        # the original is still active and usable exactly once
        ledger.settle_call(real, 3.0)
        assert ledger.status().cost_usd_used == pytest.approx(3.0)


def test_subclass_forgery_with_genuine_id_rejected():
    from app.modules.m14_project_builder.budgets import CallReservation

    class Forged(CallReservation):
        pass

    ledger = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=10.0))
    real = _reserve(ledger, 3.0)
    forged = Forged(ledger, real._token_id)
    before = ledger.status()
    with pytest.raises(BudgetError):
        ledger.release_call(forged)
    with pytest.raises(BudgetError):
        ledger.settle_call(forged, 0.0)
    after = ledger.status()
    assert (after.cost_usd_used, after.agent_calls_used) == \
           (before.cost_usd_used, before.agent_calls_used)
    ledger.settle_call(real, 3.0)  # original unaffected


def test_cross_ledger_existing_id_clone_rejected():
    from app.modules.m14_project_builder.budgets import CallReservation
    one = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=10.0))
    two = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=10.0))
    _reserve(one, 3.0)   # one: active id 1
    _reserve(two, 4.0)   # two: active id 1 - same integer, different issuance
    clone = CallReservation(two, 1)  # constructed against two's EXISTING active id
    before = two.status()
    with pytest.raises(BudgetError):
        two.release_call(clone)
    with pytest.raises(BudgetError):
        two.settle_call(clone, 0.0)
    after = two.status()
    assert (after.cost_usd_used, after.agent_calls_used) == \
           (before.cost_usd_used, before.agent_calls_used)


def test_existing_slot_mutation_blocked():
    from app.modules.m14_project_builder.budgets import CallReservation
    ledger = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=10.0))
    real = _reserve(ledger, 3.0)
    other = _reserve(ledger, 1.0)
    # __slots__ blocks NEW names only; existing slots must be frozen by the
    # immutable override - retargeting _token_id/_ledger must raise
    with pytest.raises(AttributeError):
        real._token_id = other._token_id
    with pytest.raises(AttributeError):
        real._ledger = None
    # both holds pre-charged (3.0 + 1.0); real settles at actual 3.0, other still held
    ledger.settle_call(real, 3.0)
    assert ledger.status().cost_usd_used == pytest.approx(4.0)


def test_retargeted_token_rejected_even_without_immutability_override(monkeypatch):
    # Defense in depth at the ledger surface: if the __setattr__ override is
    # deleted (the auditor's CORE-M4 mutant), __slots__ still permits writes
    # to the EXISTING _ledger/_token_id slots - so identity binding alone
    # must reject the retargeted token with zero ledger change.
    from app.modules.m14_project_builder.budgets import CallReservation
    one = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=10.0))
    two = BudgetLedger(BudgetLimits(
        max_iterations=10, max_agent_calls=5, max_runtime_seconds=60, max_cost_usd=10.0))
    real = _reserve(one, 3.0)
    _reserve(two, 4.0)  # two's active id collides with real's id
    monkeypatch.delattr(CallReservation, "__setattr__")
    real._ledger = two
    real._token_id = 1  # retarget two's genuine active id
    before = two.status()
    with pytest.raises(BudgetError):
        two.release_call(real)
    with pytest.raises(BudgetError):
        two.settle_call(real, 0.0)
    after = two.status()
    assert (after.cost_usd_used, after.agent_calls_used) == \
           (before.cost_usd_used, before.agent_calls_used)
    # two's genuine token is untouched and still settles
    two.settle_call(two._reservations[1]["token"], 4.0)
    assert two.status().cost_usd_used == pytest.approx(4.0)
