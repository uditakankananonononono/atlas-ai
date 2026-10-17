import pytest
from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger, BudgetExceeded
from app.modules.m12_ai_research_lab.lane_models import BudgetPolicy
BAD=[float("nan"),float("inf"),True,False,1.5,-1,"5",None]
@pytest.mark.parametrize("a",BAD)
def test_reserve_rejects_nonint_amounts_and_stays_clean(a):
    L=BudgetLedger(BudgetPolicy(daily_limit_micro=100))
    with pytest.raises((ValueError,TypeError)): L.reserve("r",a)
    assert L.status().reserved_micro==0
@pytest.mark.parametrize("a",BAD)
def test_commit_rejects_nonint_amounts_and_records_nothing(a):
    L=BudgetLedger(BudgetPolicy(daily_limit_micro=100))
    L.reserve("c",10)
    with pytest.raises((ValueError,TypeError)): L.commit("c",a)
    s=L.status(); assert s.spent_today_micro==0 and s.reserved_micro==10
def test_nan_reservation_cannot_disable_limits():
    L=BudgetLedger(BudgetPolicy(daily_limit_micro=100))
    try: L.reserve("p",float("nan"))
    except (ValueError,TypeError): pass
    with pytest.raises(BudgetExceeded): L.reserve("q",1000)
@pytest.mark.parametrize("kw",[dict(daily_limit_micro=float("nan")),dict(monthly_limit_micro=float("nan")),dict(per_run_limit_micro=float("nan")),
    dict(daily_limit_micro=float("inf")),dict(daily_limit_micro=True),dict(daily_limit_micro=1.5),dict(daily_limit_micro="9")])
def test_policy_limits_must_be_positive_ints(kw):
    with pytest.raises((ValueError,TypeError)): BudgetPolicy(**kw)
def test_valid_unchanged():
    L=BudgetLedger(BudgetPolicy(daily_limit_micro=100,monthly_limit_micro=1000,per_run_limit_micro=50))
    L.reserve("a",0); L.commit("a",0); L.reserve("b",40); L.commit("b",40)
    assert L.status().spent_today_micro==40
    with pytest.raises(BudgetExceeded): L.reserve("c",51)
