"""Integrator-executed helper contracts; route imports covered separately."""
from copy import deepcopy
from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "backend/app/modules/m23_study_abroad/cost_estimate.py"
_SPEC = importlib.util.spec_from_file_location("m23_cost_estimate_validation_02", _PATH)
_HELPER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_HELPER)
estimate_net_cost = _HELPER.estimate_net_cost
summarize_awards = _HELPER.summarize_awards


def money(amount, currency="USD", **extra):
    return {"amount": amount, "currency": currency, **extra}


def scenario():
    return {"currency": "USD", "years": "2",
            "annual_costs": {"tuition": money("10000"), "fees": money("1000"),
                             "living": money("4000")}, "aid": []}


def awards():
    return {"currency": "USD", "awards": [
        money("5000", timing="annual", accepted=True),
        money("2000", timing="annual", accepted=False)]}


def test_explicit_annual_and_program_total_aid_are_scaled_differently():
    data = scenario()
    data["aid"] = [money("3000", timing="annual"), money("1000", timing="program_total")]
    result = estimate_net_cost(data)
    assert result["gross_cost"] == "30000"
    assert result["aid_scenario_total"] == "7000"
    assert result["net_cost"] == "23000"


def test_fractional_years_prorate_annual_cost_and_aid():
    data = scenario()
    data["years"] = "0.5"
    data["aid"] = [money("1000", timing="annual")]
    assert estimate_net_cost(data)["net_cost"] == "7000"


def test_zero_years_is_explicit_nonnegative_not_defaulted_to_one():
    data = scenario()
    data["years"] = 0
    assert estimate_net_cost(data)["gross_cost"] == "0"


def test_excess_aid_is_unapplied_not_negative_cost_or_cash_payment():
    data = scenario()
    data["aid"] = [money("40000", timing="program_total")]
    result = estimate_net_cost(data)
    assert result["net_cost"] == "0" and result["unapplied_aid"] == "10000"
    assert result["estimate_only"] is True and "No payment" in result["boundary"]


@pytest.mark.parametrize("bad", [-1, "-0.01", float("nan"), float("inf"),
                                     float("-inf"), "NaN", "Infinity", True, [], {},
                                     "", " 1 ", "1_000", "1e31", "1e-29"])
@pytest.mark.parametrize("target", ["years", "tuition", "aid"])
def test_invalid_numbers_rejected_everywhere(bad, target):
    data = scenario()
    if target == "years":
        data["years"] = bad
    elif target == "tuition":
        data["annual_costs"]["tuition"]["amount"] = bad
    else:
        data["aid"] = [money(bad, timing="annual")]
    with pytest.raises(ValueError):
        estimate_net_cost(data)


def test_decimal_arithmetic_and_rendering_are_exact():
    data = scenario()
    data["years"] = 1
    data["annual_costs"] = {"tuition": money(0.1), "fees": money(Decimal("0.20")),
                            "living": money(0)}
    assert estimate_net_cost(data)["net_cost"] == "0.3"


def test_missing_data_is_deterministic_unknown_not_a_zero_estimate():
    expected = ["aid", "annual_costs.fees.amount", "annual_costs.fees.currency",
                "annual_costs.living.amount", "annual_costs.living.currency",
                "annual_costs.tuition.amount", "annual_costs.tuition.currency", "currency", "years"]
    result = estimate_net_cost({})
    assert result["unknown_inputs"] == expected
    assert result["gross_cost"] is None and result["net_cost"] is None
    assert result == estimate_net_cost({})


def test_unknown_aid_retains_known_gross_but_not_net():
    data = scenario()
    del data["aid"]
    result = estimate_net_cost(data)
    assert result["gross_cost"] == "30000" and result["net_cost"] is None
    assert result["unknown_inputs"] == ["aid"]


def test_missing_aid_timing_does_not_silently_deduct():
    data = scenario()
    data["aid"] = [money("1000")]
    result = estimate_net_cost(data)
    assert result["net_cost"] is None and result["unknown_inputs"] == ["aid[0].timing"]


@pytest.mark.parametrize("timing", ["monthly", "", False, 1, {}, []])
def test_invalid_aid_timing_rejected(timing):
    data = scenario()
    data["aid"] = [money("1000", timing=timing)]
    with pytest.raises(ValueError):
        estimate_net_cost(data)


@pytest.mark.parametrize("currency", ["EUR", "INR"])
def test_mixed_cost_and_aid_currencies_rejected(currency):
    data = scenario()
    data["aid"] = [money("1000", currency, timing="program_total")]
    with pytest.raises(ValueError, match="Mixed currencies"):
        estimate_net_cost(data)


def test_unknown_amount_does_not_hide_incompatible_currency():
    data = scenario()
    data["annual_costs"]["fees"] = money(None, "EUR")
    with pytest.raises(ValueError, match="Mixed currencies"):
        estimate_net_cost(data)


@pytest.mark.parametrize("currency", ["usd", "US", " USD", "USD ", 3, "US$"])
def test_currency_labels_are_not_defaulted_or_coerced(currency):
    data = scenario()
    data["currency"] = currency
    with pytest.raises(ValueError):
        estimate_net_cost(data)


def test_unknown_currency_prevents_net_estimate():
    data = scenario()
    data["annual_costs"]["fees"]["currency"] = None
    assert estimate_net_cost(data)["net_cost"] is None


def test_awards_same_currency_and_timing_offered_and_accepted_totals():
    result = summarize_awards(awards())
    assert result["total_offered"] == "7000" and result["accepted_total"] == "5000"
    assert result["timing"] == "annual" and result["estimate_only"] is True


def test_mixed_award_currencies_never_summed():
    data = awards()
    data["awards"][1]["currency"] = "EUR"
    with pytest.raises(ValueError, match="Mixed currencies"):
        summarize_awards(data)


def test_mixed_award_timings_never_summed():
    data = awards()
    data["awards"][1]["timing"] = "program_total"
    with pytest.raises(ValueError, match="Mixed award timings"):
        summarize_awards(data)


def test_unknown_award_acceptance_preserves_offered_only():
    data = awards()
    del data["awards"][1]["accepted"]
    result = summarize_awards(data)
    assert result["total_offered"] == "7000" and result["accepted_total"] is None
    assert result["unknown_inputs"] == ["awards[1].accepted"]


@pytest.mark.parametrize("bad", ["true", "false", 0, 1, [], {}])
def test_award_acceptance_requires_literal_boolean(bad):
    data = awards()
    data["awards"][0]["accepted"] = bad
    with pytest.raises(ValueError):
        summarize_awards(data)


def test_unknown_award_amount_never_becomes_zero():
    data = awards()
    data["awards"][0]["amount"] = None
    result = summarize_awards(data)
    assert result["total_offered"] is None and result["accepted_total"] is None


def test_missing_awards_differs_from_explicit_empty_awards():
    assert summarize_awards({"currency": "USD"})["total_offered"] is None
    result = summarize_awards({"currency": "USD", "awards": []})
    assert result["total_offered"] == "0" and result["accepted_total"] == "0"
    assert result["timing"] is None


@pytest.mark.parametrize("field", ["aid", "awards"])
@pytest.mark.parametrize("bad", [{}, "none", [1], [None], [{}] * 501])
def test_malformed_or_oversized_collections_rejected(field, bad):
    data = scenario() if field == "aid" else awards()
    data[field] = bad
    with pytest.raises(ValueError):
        (estimate_net_cost if field == "aid" else summarize_awards)(data)


def test_helpers_do_not_mutate_inputs():
    for data, function in [(scenario(), estimate_net_cost), (awards(), summarize_awards)]:
        before = deepcopy(data)
        function(data)
        assert data == before


def test_unknown_results_are_json_serializable_without_nan():
    import json
    for result in (estimate_net_cost({}), summarize_awards({})):
        assert json.loads(json.dumps(result, allow_nan=False)) == result


@pytest.mark.parametrize("bad", [-1, "NaN", "Infinity", True, "1e31", "1e-29"])
def test_invalid_award_amounts_rejected(bad):
    data = awards()
    data["awards"][0]["amount"] = bad
    with pytest.raises(ValueError):
        summarize_awards(data)


def test_missing_award_timing_suppresses_both_totals():
    data = awards()
    del data["awards"][0]["timing"]
    result = summarize_awards(data)
    assert result["total_offered"] is None and result["accepted_total"] is None
    assert result["unknown_inputs"] == ["awards[0].timing"]


def test_finite_upper_bound_products_have_no_float_overflow():
    data = scenario()
    data["years"] = "1e30"
    data["annual_costs"] = {key: money("1e30") for key in ("tuition", "fees", "living")}
    assert estimate_net_cost(data)["gross_cost"] == "3" + "0" * 60


def test_unknown_years_never_returns_program_total():
    data = scenario()
    data["years"] = None
    result = estimate_net_cost(data)
    assert result["gross_cost"] is None and result["net_cost"] is None


@pytest.mark.parametrize("bad", [[], "USD", 1, None])
def test_root_requires_mapping(bad):
    for function in (estimate_net_cost, summarize_awards):
        with pytest.raises(ValueError):
            function(bad)
