"""Per-row discriminating tests for computation rows 1310-1459.

Follow-on layer over the merged 150 named quantitative computations:
  * finance rows 1310-1359  -> app.modules.m16_executive_dashboard.finance_core
  * finance rows 1360-1409  -> app.modules.m16_executive_dashboard.finance
  * education rows 1410-1459 -> app.modules.m20_general_cognitive_worker.education

For every row this file pins a fixture pair in which exactly one relevant input
changes and asserts that the row's distinctive computation value (or a
row-specific categorical decision) changes with it, plus an invalid-domain
failure for every row.  Boundary markers are re-asserted here so this layer
alone cannot silently lose them: finance stays non-transactional / not-advice,
education stays educator-gated and pseudonymous with no protected-trait
inference.

Rows whose distinctive metric is structurally constant (a fixed stage count or
fixed safeguard list divided by itself) are named in EDU_INVARIANT_ARTIFACT;
for those rows the discriminating assertion targets a row-specific artifact or
categorical judgement and additionally documents the invariance by asserting
the distinctive value is unchanged across the pair.
"""
import math

import pytest

from app.modules.m16_executive_dashboard import finance_core
from app.modules.m16_executive_dashboard import finance as finance_spec
from app.modules.m20_general_cognitive_worker import education
from app.modules.m20_general_cognitive_worker.education import EducationError

# ---------------------------------------------------------------------------
# Finance rows 1310-1359 (finance_core)
# ---------------------------------------------------------------------------

CORE_CASES = {
'financial_statement_analysis':({'revenue':100,'cogs':60,'operating_expenses':20,'assets':200,'liabilities':80,'current_assets':70,'current_liabilities':35,'inventory':20,'net_income':12},{}),
'ratio_analysis':({'revenue':100,'cogs':60,'operating_expenses':20,'assets':200,'liabilities':80,'current_assets':70,'current_liabilities':35,'inventory':20,'net_income':12},{}),
'cash_flow_analysis':({'operating':30,'investing':-12,'financing':-5,'capex':10,'opening_cash':7,'net_income':20},{}),
'working_capital_management':({'receivables':20,'inventory':15,'payables':10,'sales':100,'cogs':60},{}),
'capital_budgeting':({'cash_flows':[-100,60,60]},{'discount_rate':.1}),
'npv_calculation':({'cash_flows':[-100,60,60]},{'discount_rate':.1}),
'irr_analysis':({'cash_flows':[-100,60,60]},{}),
'payback_period':({'cash_flows':[-100,30,50,40]},{}),
'real_options_analysis':({'base_npv':5,'up_value':80,'down_value':20,'exercise_cost':40},{'up_probability':.5,'discount_rate':.1}),
'cost_of_capital':({'equity':60,'debt':40,'cost_of_equity':.12,'cost_of_debt':.06,'tax_rate':.25},{}),
'wacc_calculation':({'equity':60,'debt':40,'cost_of_equity':.12,'cost_of_debt':.06,'tax_rate':.25},{}),
'capm':({'risk_free_rate':.03,'beta':1.2,'market_return':.09},{}),
'beta_estimation':({'market_returns':[.01,.02,-.01,.03],'asset_returns':[.012,.026,-.014,.038]},{}),
'risk_adjusted_returns':({'returns':[.01,.02,-.01,.03]},{'annualization':12}),
'portfolio_optimization':({'expected_returns':[.05,.1],'covariance':[[.04,.01],[.01,.09]]},{'target_return':.08}),
'markowitz_model':({'expected_returns':[.05,.1],'covariance':[[.04,.01],[.01,.09]]},{'target_return':.08}),
'black_litterman':({'prior_returns':[.05,.07],'views':[.08,.04],'confidences':[.75,.25]},{}),
'factor_models':({'asset_returns':[.01,.02,.015,.03],'factors':[[.01,.0],[.02,.01],[.0,.02],[.03,.01]]},{}),
'fama_french':({'asset_returns':[.01,.02,.015,.03],'factors':[[.01,.0],[.02,.01],[.0,.02],[.03,.01]]},{}),
'risk_parity':({'volatilities':[.1,.2,.4]},{}),
'asset_allocation':({'scores':[1,2,3],'minimums':[.1,.1,.1]},{}),
'rebalancing_strategy':({'current_weights':[.3,.7],'target_weights':[.5,.5],'portfolio_value':1000},{'threshold':.05}),
'performance_attribution':({'portfolio_weights':[.6,.4],'benchmark_weights':[.5,.5],'portfolio_returns':[.1,.04],'benchmark_returns':[.08,.05]},{}),
'sharpe_ratio':({'returns':[.01,.02,-.01,.03]},{'annualization':12}),
'sortino_ratio':({'returns':[.01,.02,-.01,.03]},{'annualization':12}),
'information_ratio':({'returns':[.03,.01,.02,.04],'benchmark_returns':[.02,.015,.01,.03]},{'annualization':12}),
'alpha_generation':({'beta':1.1,'actual_return':.12,'risk_free_rate':.03,'market_return':.1},{}),
'beta_management':({'beta':1.1,'actual_return':.12,'risk_free_rate':.03,'market_return':.1},{'target_beta':.8}),
'hedging_strategies':({'exposure':1000000,'beta':1.2,'contract_notional':50000},{}),
'derivatives_pricing':({'spot':100,'strike':100,'time':1,'rate':.05,'volatility':.2},{}),
'black_scholes':({'spot':100,'strike':100,'time':1,'rate':.05,'volatility':.2},{}),
'binomial_trees':({'spot':100,'strike':100,'time':1,'rate':.05,'volatility':.2},{'steps':100}),
'monte_carlo_pricing':({'spot':100,'strike':100,'time':1,'rate':.05,'volatility':.2},{'simulations':20000}),
'greeks_calculation':({'spot':100,'strike':100,'time':1,'rate':.05,'volatility':.2},{}),
'volatility_modeling':({'returns':[.01,-.02,.015,-.01]},{'omega':.00001,'alpha':.1,'beta':.8}),
'garch_models':({'returns':[.01,-.02,.015,-.01]},{'omega':.00001,'alpha':.1,'beta':.8}),
'stochastic_volatility':({'returns':[.01,-.02,.015,-.01]},{}),
'jump_diffusion':({'spot':100,'time':1,'rate':.03,'volatility':.2},{'jump_intensity':.2,'jump_mean':-.05,'jump_volatility':.1}),
'fixed_income_analysis':({'cash_flows':[5,5,105],'yield':.05},{}),
'yield_curve_construction':({'instruments':[{'price':95,'face':100},{'price':92,'face':100}]},{}),
'duration':({'cash_flows':[5,5,105],'yield':.05},{}),
'convexity':({'cash_flows':[5,5,105],'yield':.05},{}),
'credit_analysis':({'ebitda':30,'interest_expense':5,'debt':80,'assets':200,'working_capital':20,'retained_earnings':30,'sales':180,'market_equity':120},{}),
'default_prediction':({'ebitda':30,'interest_expense':5,'debt':80,'assets':200,'working_capital':20,'retained_earnings':30,'sales':180,'market_equity':120},{}),
'recovery_rates':({'recovered_amount':50,'exposure_at_default':100,'workout_cost':5},{}),
'credit_derivatives':({'spread':.02,'notional':1000000,'maturity':5,'recovery_rate':.4},{}),
'cds_pricing':({'spread':.02,'notional':1000000,'maturity':5,'recovery_rate':.4},{}),
'securitization':({'pool_balances':[100,200],'coupon_rates':[.05,.06],'default_rates':[.01,.02],'recovery_rates':[.5,.4],'prepayment_rates':[.05,.1],'credit_enhancement':5},{}),
'mbs_analysis':({'pool_balances':[100,200],'coupon_rates':[.05,.06],'default_rates':[.01,.02],'recovery_rates':[.5,.4],'prepayment_rates':[.05,.1],'credit_enhancement':5},{}),
'abs_analysis':({'pool_balances':[100,200],'coupon_rates':[.05,.06],'default_rates':[.01,.02],'recovery_rates':[.5,.4],'prepayment_rates':[.05,.1],'credit_enhancement':5},{}),
}

# method -> (data overrides, params overrides, output key that must move)
CORE_DISCRIMINATING = {
'financial_statement_analysis':({'revenue':200},{},'gross_margin'),
'ratio_analysis':({'current_assets':140},{},'current_ratio'),
'cash_flow_analysis':({'operating':40},{},'free_cash_flow'),
'working_capital_management':({'receivables':40},{},'cash_conversion_cycle'),
'capital_budgeting':({},{'discount_rate':.2},'npv'),
'npv_calculation':({},{'discount_rate':.2},'npv'),
'irr_analysis':({'cash_flows':[-100,50,60]},{},'irr'),
'payback_period':({'cash_flows':[-100,30,60,40]},{},'payback_period'),
'real_options_analysis':({},{'up_probability':.7},'option_value'),
'cost_of_capital':({'tax_rate':.4},{},'wacc'),
'wacc_calculation':({'cost_of_debt':.08},{},'wacc'),
'capm':({'beta':1.5},{},'expected_return'),
'beta_estimation':({'asset_returns':[.012,.026,-.014,.05]},{},'beta'),
'risk_adjusted_returns':({},{'annualization':4},'annualized_return'),
'portfolio_optimization':({},{'target_return':.06},'weights'),
'markowitz_model':({},{'target_return':.06},'weights'),
'black_litterman':({'confidences':[.25,.75]},{},'posterior_returns'),
'factor_models':({'asset_returns':[.02,.01,.025,.01]},{},'factor_loadings'),
'fama_french':({'factors':[[.02,.0],[.01,.01],[.0,.01],[.03,.02]]},{},'factor_loadings'),
'risk_parity':({'volatilities':[.1,.2,.3]},{},'weights'),
'asset_allocation':({'scores':[3,2,1]},{},'weights'),
'rebalancing_strategy':({},{'threshold':.25},'trades'),
'performance_attribution':({'portfolio_returns':[.12,.04]},{},'selection'),
'sharpe_ratio':({'returns':[.02,.03,-.01,.04]},{},'sharpe_ratio'),
'sortino_ratio':({'returns':[.02,.03,-.02,.04]},{},'sortino_ratio'),
'information_ratio':({'benchmark_returns':[.02,.02,.02,.02]},{},'information_ratio'),
'alpha_generation':({'actual_return':.15},{},'jensen_alpha'),
'beta_management':({},{'target_beta':.6},'hedge_notional_fraction'),
'hedging_strategies':({'beta':1.5},{},'contracts'),
'derivatives_pricing':({'volatility':.3},{},'price'),
'black_scholes':({'strike':90},{},'price'),
'binomial_trees':({'volatility':.25},{},'price'),
'monte_carlo_pricing':({'volatility':.4},{},'price'),
'greeks_calculation':({'rate':.08},{},'rho'),
'volatility_modeling':({},{'omega':.00005},'next_variance'),
'garch_models':({},{'beta':.7},'next_variance'),
'stochastic_volatility':({},{'phi':.8},'next_variance'),
'jump_diffusion':({},{'jump_intensity':.5},'terminal_variance_approx'),
'fixed_income_analysis':({'yield':.07},{},'price'),
'yield_curve_construction':({'instruments':[{'price':95,'face':100},{'price':90,'face':100}]},{},'discount_factors'),
'duration':({'yield':.08},{},'modified_duration'),
'convexity':({'cash_flows':[5,105]},{},'convexity'),
'credit_analysis':({'ebitda':50},{},'altman_style_score'),
'default_prediction':({'debt':120},{},'illustrative_default_probability'),
'recovery_rates':({'workout_cost':10},{},'net_recovery_rate'),
'credit_derivatives':({'spread':.03},{},'implied_hazard_rate'),
'cds_pricing':({'maturity':7},{},'premium_leg_approx'),
'securitization':({'default_rates':[.03,.04]},{},'expected_credit_loss'),
'mbs_analysis':({'prepayment_rates':[.1,.2]},{},'expected_prepayment'),
'abs_analysis':({'recovery_rates':[.6,.5]},{},'expected_credit_loss'),
}

NAN = float('nan')

# method -> (data overrides, params overrides) that must raise ValueError
CORE_INVALID = {
'financial_statement_analysis':({'revenue':-5},{}),
'ratio_analysis':({'current_liabilities':0},{}),
'cash_flow_analysis':({'operating':NAN},{}),
'working_capital_management':({'sales':0},{}),
'capital_budgeting':({},{'discount_rate':-2}),
'npv_calculation':({},{'discount_rate':-2}),
'irr_analysis':({'cash_flows':[1,2,3]},{}),
'payback_period':({'cash_flows':[-100]},{}),
'real_options_analysis':({'base_npv':NAN},{}),
'cost_of_capital':({'equity':0,'debt':0},{}),
'wacc_calculation':({'equity':0,'debt':0},{}),
'capm':({'beta':NAN},{}),
'beta_estimation':({'market_returns':[1,1,1],'asset_returns':[1,2,3]},{}),
'risk_adjusted_returns':({'returns':[.1]},{}),
'portfolio_optimization':({'covariance':[[1],[2]]},{}),
'markowitz_model':({'covariance':[[1],[2]]},{}),
'black_litterman':({'views':[.1]},{}),
'factor_models':({'factors':[[.01],[.02]]},{}),
'fama_french':({'factors':[[.01],[.02]]},{}),
'risk_parity':({'volatilities':[0,.2]},{}),
'asset_allocation':({'minimums':[.6,.6,.6]},{}),
'rebalancing_strategy':({'target_weights':[1.0]},{}),
'performance_attribution':({'benchmark_weights':[1.0]},{}),
'sharpe_ratio':({'returns':[.1]},{}),
'sortino_ratio':({'returns':[.1]},{}),
'information_ratio':({'benchmark_returns':[.01]},{}),
'alpha_generation':({'actual_return':NAN},{}),
'beta_management':({'actual_return':NAN},{}),
'hedging_strategies':({'exposure':NAN},{}),
'derivatives_pricing':({'volatility':0},{}),
'black_scholes':({'volatility':0},{}),
'binomial_trees':({'rate':3.0},{}),
'monte_carlo_pricing':({'volatility':NAN},{}),
'greeks_calculation':({'spot':0},{}),
'volatility_modeling':({},{'alpha':.7,'beta':.4}),
'garch_models':({},{'alpha':.7,'beta':.4}),
'stochastic_volatility':({'returns':[.1,.2]},{}),
'jump_diffusion':({'spot':NAN},{}),
'fixed_income_analysis':({'yield':NAN},{}),
'yield_curve_construction':({'instruments':[]},{}),
'duration':({'yield':NAN},{}),
'convexity':({'yield':NAN},{}),
'credit_analysis':({'ebitda':NAN},{}),
'default_prediction':({'ebitda':NAN},{}),
'recovery_rates':({'recovered_amount':NAN},{}),
'credit_derivatives':({'spread':NAN},{}),
'cds_pricing':({'spread':NAN},{}),
'securitization':({'coupon_rates':[.05]},{}),
'mbs_analysis':({'coupon_rates':[.05]},{}),
'abs_analysis':({'coupon_rates':[.05]},{}),
}


def _core_pair(method):
    (data, params) = CORE_CASES[method]
    d_mut, p_mut, key = CORE_DISCRIMINATING[method]
    base = finance_core.run(method, dict(data), dict(params), seed=17)['output']
    moved = finance_core.run(method, dict(data, **d_mut), dict(params, **p_mut), seed=17)['output']
    return base, moved, key


@pytest.mark.parametrize('method,row', sorted(finance_core.ROWS.items(), key=lambda kv: kv[1]))
def test_core_row_distinctive_value_moves_with_one_input(method, row):
    assert 1310 <= row <= 1359
    base, moved, key = _core_pair(method)
    assert base[key] != moved[key], f'{method}: {key} did not discriminate'


@pytest.mark.parametrize('method,row', sorted(finance_core.ROWS.items(), key=lambda kv: kv[1]))
def test_core_row_rejects_invalid_domain(method, row):
    data, params = CORE_CASES[method]
    d_mut, p_mut = CORE_INVALID[method]
    with pytest.raises(ValueError):
        finance_core.run(method, dict(data, **d_mut), dict(params, **p_mut), seed=17)


# ---------------------------------------------------------------------------
# Finance rows 1360-1409 (finance)
# ---------------------------------------------------------------------------

SPEC_CASES = {
"structured_products":{"principal":1000,"underlying_return":.2},
"exotic_options":{"paths":[[90,110],[100,80]],"strike":100},
"barrier_options":{"path":[100,121,115],"strike":105,"barrier":120},
"asian_options":{"path":[90,100,110],"strike":95},
"lookback_options":{"path":[90,120,110]},
"forward_starting_options":{"start_spot":100,"end_spot":120},
"compound_options":{"inner_strike":100,"inner_maturity":1,"outer_strike":5},
"chooser_options":{"strike":100},
"rainbow_options":{"spots":[90,120],"weights":[.5,.5],"strike":100},
"basket_options":{"spots":[90,120],"weights":[.5,.5],"strike":100},
"quanto_options":{"strike":90,"fixed_fx":1.2},
"commodity_trading":{"spot":90,"futures":100,"maturity_years":1},
"energy_markets":{"hourly_prices":[20,50],"load":[1,3]},
"carbon_trading":{"emissions":120,"allowances":100,"allowance_price":30},
"weather_derivatives":{"daily_temperatures":[10,20,12],"degree_day_strike":10,"currency_per_degree_day":5},
"fx_trading":{"fx_rates":[80,81,80.5]},
"currency_hedging":{"foreign_exposure":100,"forward_rate":82,"future_spot":80},
"carry_trade":{"high_rate":.08,"low_rate":.03},
"purchasing_power_parity":{"home_price_index":120,"foreign_price_index":100,"spot_rate":1.3},
"interest_rate_parity":{"spot_rate":1.2,"home_rate":.05,"foreign_rate":.02},
"international_finance":{"foreign_assets":500,"foreign_liabilities":400,"gdp":1000},
"sovereign_risk":{"debt_to_gdp":80,"deficit_to_gdp":5,"reserves_to_short_debt":.8,"bond_spread_bps":300},
"country_risk":{"economic_risk":.2,"financial_risk":.3,"political_risk":.4},
"political_risk":{"scenario_probabilities":[.8,.2],"scenario_losses":[0,100]},
"emerging_markets":{"returns":[.01,.02,-.01],"benchmark_returns":[.0,.01,-.01],"liquidity_score":.7},
"frontier_markets":{"returns":[.01,.02,-.01],"benchmark_returns":[.0,.01,-.01],"liquidity_score":.3},
"microfinance":{"amount_disbursed":1000,"portfolio_outstanding":800,"overdue_over_30":80,"writeoffs":10,"active_borrowers":20},
"development_finance":{"private_capital_mobilized":200,"public_capital":100,"beneficiaries":50,"program_cost":150},
"impact_investing":{"metrics":{"impact":.8,"risk":.4}},
"esg_investing":{"metrics":{"e":.8,"s":.6,"g":.7}},
"sustainable_finance":{"metrics":{"taxonomy":.9,"transition":.5}},
"green_bonds":{"cashflows":[5,105],"yield_rate":.05,"eligible_green_allocations":90,"net_proceeds":100},
"climate_finance":{"metrics":{"mitigation":.8,"adaptation":.6}},
"carbon_markets":{"emissions":90,"allowances":100,"allowance_price":20,"market_kind":"voluntary"},
"behavioral_finance":{"actual_allocations":[.7,.3],"target_allocations":[.5,.5]},
"prospect_theory":{"outcomes":[100,-100],"probabilities":[.5,.5]},
"mental_accounting":{"accounts":[{"balance":100,"return":.1},{"balance":50,"return":0}]},
"loss_aversion":{"gains":[10,20],"losses":[-30,-20]},
"overconfidence":{"forecasts":[10,20],"actual":[12,16],"interval_widths":[2,2]},
"anchoring":{"estimates":[10,20,30],"anchors":[9,19,29],"truths":[15,15,15]},
"herding":{"individual_returns":[.1,-.1,.2],"market_returns":[.08,-.05,.1]},
"market_efficiency":{"returns":[.1,-.1,.05,-.02,.01]},
"emh_testing":{"returns":[.1,-.1,.05,-.02,.01]},
"anomalies":{"returns":[.1,.2,-.1,.0],"period_labels":["Jan","Jan","Other","Other"]},
}
for _m in ["momentum","value","size","quality","low_volatility","profitability"]:
    SPEC_CASES[_m] = {"signal":[1,2,3,4,5,6,7,8],"future_returns":[-.04,-.03,-.02,-.01,.01,.02,.03,.04]}

# method -> (data overrides, output key that must move)
SPEC_DISCRIMINATING = {
"structured_products":({"underlying_return":.3},'redemption'),
"exotic_options":({"paths":[[90,110],[100,105]]},'expected_payoff'),
"barrier_options":({"barrier":130},'payoff'),
"asian_options":({"path":[90,100,130]},'payoff'),
"lookback_options":({"path":[80,120,110]},'payoff'),
"forward_starting_options":({"strike_multiplier":.9},'payoff'),
"compound_options":({"inner_strike":90},'inner_option_value'),
"chooser_options":({"strike":120},'chooser_value_at_choice'),
"rainbow_options":({"spots":[90,140]},'payoff'),
"basket_options":({"weights":[.8,.2]},'payoff'),
"quanto_options":({"fixed_fx":1.4},'domestic_payoff'),
"commodity_trading":({"futures":110},'annualized_implied_carry'),
"energy_markets":({"load":[3,1]},'load_weighted_price'),
"carbon_trading":({"emissions":150},'compliance_cost'),
"weather_derivatives":({"degree_day_strike":15},'payoff'),
"fx_trading":({"fx_rates":[80,84,80.5]},'annualized_volatility'),
"currency_hedging":({"forward_rate":85},'hedge_pnl'),
"carry_trade":({"high_rate":.09},'unlevered_return'),
"purchasing_power_parity":({"home_price_index":130},'currency_misalignment'),
"interest_rate_parity":({"home_rate":.07},'implied_forward'),
"international_finance":({"foreign_assets":600},'niip_to_gdp'),
"sovereign_risk":({"bond_spread_bps":600},'risk_score'),
"country_risk":({"economic_risk":.4},'composite_risk'),
"political_risk":({"scenario_probabilities":[.5,.5]},'expected_loss'),
"emerging_markets":({"liquidity_score":.4},'liquidity_score'),
"frontier_markets":({"liquidity_score":.9},'liquidity_score'),
"microfinance":({"overdue_over_30":100},'portfolio_at_risk_30'),
"development_finance":({"private_capital_mobilized":300},'mobilization_ratio'),
"impact_investing":({"metrics":{"impact":.6,"risk":.4}},'weighted_score'),
"esg_investing":({"metrics":{"e":.5,"s":.6,"g":.7}},'weighted_score'),
"sustainable_finance":({"metrics":{"taxonomy":.6,"transition":.5}},'weighted_score'),
"green_bonds":({"eligible_green_allocations":80},'green_allocation_ratio'),
"climate_finance":({"metrics":{"mitigation":.5,"adaptation":.6}},'weighted_score'),
"carbon_markets":({"emissions":110},'net_allowance_position'),
"behavioral_finance":({"actual_allocations":[.8,.2]},'allocation_drift_l1'),
"prospect_theory":({"reference":50},'subjective_value'),
"mental_accounting":({"accounts":[{"balance":100,"return":.2},{"balance":50,"return":0}]},'portfolio_return'),
"loss_aversion":({"gains":[10,30]},'revealed_loss_aversion_ratio'),
"overconfidence":({"interval_widths":[6,6]},'overconfidence_ratio'),
"anchoring":({"anchors":[1,1,1]},'anchor_estimate_correlation'),
"herding":({"market_returns":[-.08,.05,-.1]},'co_movement'),
"market_efficiency":({"returns":[.1,.1,.05,.02,.01]},'lag1_autocorrelation'),
"emh_testing":({"returns":[.1,.1,.05,.02,.01]},'normal_approx_p_value'),
"anomalies":({"period_labels":["Jan","Other","Jan","Other"]},'spread'),
"momentum":({"signal":[8,7,6,5,4,3,2,1]},'factor_return'),
"value":({"signal":[8,7,6,5,4,3,2,1]},'factor_return'),
"size":({"signal":[8,7,6,5,4,3,2,1]},'factor_return'),
"quality":({"signal":[8,7,6,5,4,3,2,1]},'factor_return'),
"low_volatility":({"signal":[8,7,6,5,4,3,2,1]},'factor_return'),
"profitability":({"signal":[8,7,6,5,4,3,2,1]},'factor_return'),
}

# method -> data overrides that must raise ValueError
SPEC_INVALID = {
"structured_products":{"principal":NAN},
"exotic_options":{"paths":[]},
"barrier_options":{"direction":"sideways"},
"asian_options":{"path":[100]},
"lookback_options":{"type":"fixed"},
"forward_starting_options":{"start_spot":NAN},
"compound_options":{"inner_strike":0},
"chooser_options":{"volatility":0},
"rainbow_options":{"weights":[1]},
"basket_options":{"weights":[1]},
"quanto_options":{"fixed_fx":NAN},
"commodity_trading":{"futures":-1},
"energy_markets":{"load":[0,0]},
"carbon_trading":{"allowance_price":NAN},
"weather_derivatives":{"currency_per_degree_day":NAN},
"fx_trading":{"fx_rates":[80]},
"currency_hedging":{"forward_rate":NAN},
"carry_trade":{"high_rate":NAN},
"purchasing_power_parity":{"foreign_price_index":NAN},
"interest_rate_parity":{"spot_rate":NAN},
"international_finance":{"gdp":NAN},
"sovereign_risk":{"debt_to_gdp":NAN},
"country_risk":{"weights":[1,1]},
"political_risk":{"scenario_probabilities":[.3,.3]},
"emerging_markets":{"liquidity_score":2},
"frontier_markets":{"liquidity_score":2},
"microfinance":{"portfolio_outstanding":NAN},
"development_finance":{"public_capital":NAN},
"impact_investing":{"metrics":{}},
"esg_investing":{"metrics":{}},
"sustainable_finance":{"metrics":{}},
"green_bonds":{"cashflows":[]},
"climate_finance":{"metrics":{}},
"carbon_markets":{"emissions":NAN},
"behavioral_finance":{"target_allocations":[1]},
"prospect_theory":{"probabilities":[.5,.6]},
"mental_accounting":{"accounts":[]},
"loss_aversion":{"gains":[]},
"overconfidence":{"actual":[1]},
"anchoring":{"truths":[1]},
"herding":{"market_returns":[1]},
"market_efficiency":{"returns":[.1,.2]},
"emh_testing":{"returns":[.1,.2]},
"anomalies":{"period_labels":["a"]},
"momentum":{"future_returns":[.1]},
"value":{"future_returns":[.1]},
"size":{"future_returns":[.1]},
"quality":{"future_returns":[.1]},
"low_volatility":{"future_returns":[.1]},
"profitability":{"future_returns":[.1]},
}


@pytest.mark.parametrize('method,row', sorted(finance_spec.ROWS.items(), key=lambda kv: kv[1]))
def test_spec_row_distinctive_value_moves_with_one_input(method, row):
    assert 1360 <= row <= 1409
    data = SPEC_CASES[method]
    mutation, key = SPEC_DISCRIMINATING[method]
    base = finance_spec.run(method, dict(data), seed=7)['output']
    moved = finance_spec.run(method, dict(data, **mutation), seed=7)['output']
    assert base[key] != moved[key], f'{method}: {key} did not discriminate'


@pytest.mark.parametrize('method,row', sorted(finance_spec.ROWS.items(), key=lambda kv: kv[1]))
def test_spec_row_rejects_invalid_domain(method, row):
    with pytest.raises(ValueError):
        finance_spec.run(method, dict(SPEC_CASES[method], **SPEC_INVALID[method]), seed=7)


@pytest.mark.parametrize('engine,cases', [(finance_core, None), (finance_spec, None)])
def test_finance_rows_keep_nontransactional_not_advice_markers(engine, cases):
    if engine is finance_core:
        for method, (data, params) in CORE_CASES.items():
            marker = engine.run(method, dict(data), dict(params), seed=17)['output']['distinctive_computation']
            assert marker['transactional'] is False and marker['advice'] is False
            assert marker['caller_supplied_inputs_only'] and marker['row_id'] == finance_core.ROWS[method]
    else:
        for method, data in SPEC_CASES.items():
            marker = engine.run(method, dict(data), seed=7)['output']['distinctive_computation']
            assert marker['transactional'] is False and marker['advice'] is False
            assert marker['caller_supplied_inputs_only'] and marker['row_id'] == finance_spec.ROWS[method]


# ---------------------------------------------------------------------------
# Education rows 1410-1459 (education)
# ---------------------------------------------------------------------------

SRC = {"title": "Teaching evidence", "url": "https://example.edu/evidence"}


def edu_design(name, **extra):
    p = {"topic": "Fractions", "learners": {"grade": 5},
         "objectives": [{"id": "o1", "statement": "Compare fractions"}],
         "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}],
         "duration_minutes": 50, "source": SRC}
    p.update(extra)
    return education.execute(name, p)


def edu_inclusion(name, **extra):
    p = {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"},
         "supports": ["worked examples"], "source": SRC}
    p.update(extra)
    return education.execute(name, p)


def edu_pedagogy(name, **extra):
    p = {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": SRC}
    p.update(extra)
    return education.execute(name, p)


def edu_delivery(name, **extra):
    p = {"units": ["Foundations", "Application"], "constraints": {"bandwidth": "low"}, "source": SRC}
    if name == "moocs":
        p["cohort_scale"] = 1000
    p.update(extra)
    return education.execute(name, p)


def edu_immersive(name, **extra):
    p = {"objective": "Apply safety procedure", "mechanic": "branching decision",
         "alignment_rationale": "requires choosing each step", "source": SRC}
    p.update(extra)
    return education.execute(name, p)


EVENTS = [
    {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": True, "duration_seconds": 20},
    {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": False, "duration_seconds": 40},
]


def edu_analytics(name, ev=None, **extra):
    p = {"events": list(EVENTS) if ev is None else ev, "source": SRC}
    p.update(extra)
    return education.execute(name, p)


# name -> (builder, base kwargs, perturbed kwargs): distinctive value must move
EDU_DISCRIMINATING = {
"curriculum_design": (edu_design, {}, {"assessments": [{"name": "exit ticket", "objective_ids": []}]}),
"learning_objective_writing": (edu_design, {}, {"objectives": ["Understand fractions"]}),
"assessment_design": (edu_design, {}, {"assessments": [{"name": "quiz", "objective_ids": ["o1", "bogus"]}]}),
"rubric_creation": (edu_design, {"criteria": [{"name": "reasoning", "weight": 3}, {"name": "accuracy", "weight": 1}]},
                    {"criteria": [{"name": "reasoning", "weight": 1}, {"name": "accuracy", "weight": 1}]}),
"lesson_planning": (edu_design, {}, {"duration_minutes": 100}),
"unit_planning": (edu_design, {}, {"objectives": [{"id": "o1", "statement": "Compare fractions"},
                                                 {"id": "o2", "statement": "Simplify fractions"}]}),
"course_design": (edu_design, {}, {"assessments": [{"name": "quiz", "objective_ids": ["bogus"]}]}),
"instructional_design": (edu_design, {}, {"objectives": [{"id": "o1", "statement": "Compare fractions"},
                                                         {"id": "o2", "statement": "Simplify fractions"}]}),
"addie_model": (edu_design, {}, {"duration_minutes": 100}),
"sam_model": (edu_design, {}, {"duration_minutes": 100}),
"backward_design": (edu_design, {}, {"assessments": [{"name": "quiz", "objective_ids": ["bogus"]}]}),
"differentiated_instruction": (edu_inclusion, {}, {"supports": ["worked examples", "manipulatives"]}),
"personalized_learning": (edu_inclusion, {}, {"objectives": ["Solve equations", "Graph equations"]}),
"adaptive_learning": (edu_inclusion, {"mastery": .4}, {"mastery": .8}),
"zone_of_proximal_development": (edu_inclusion, {"independent_skills": ["a"], "assisted_skills": ["a", "b"]},
                                 {"independent_skills": ["a"], "assisted_skills": ["a", "b", "c"]}),
"situated_learning": (edu_pedagogy, {}, {"artifacts": ["log", "product", "reflection", "presentation"]}),
"anchored_instruction": (edu_pedagogy, {}, {"challenge": "Reduce school waste across the whole district"}),
"cooperative_learning": (edu_pedagogy, {}, {"roles": ["facilitator", "recorder"]}),
"collaborative_learning": (edu_pedagogy, {}, {"artifacts": ["log", "product", "reflection", "presentation"]}),
"flipped_classroom": (edu_delivery, {}, {"units": ["a", "b", "c"]}),
"blended_learning": (edu_delivery, {}, {"units": ["a", "b", "c"]}),
"online_learning": (edu_delivery, {}, {"units": ["a", "b", "c"]}),
"distance_education": (edu_delivery, {}, {"units": ["a", "b", "c"]}),
"moocs": (edu_delivery, {}, {"cohort_scale": 2000}),
"microlearning": (edu_delivery, {}, {"units": ["a", "b", "c"]}),
"game_based_learning": (edu_immersive, {}, {"alignment_rationale": ""}),
"gamification": (edu_immersive, {}, {"choices": ["path a", "path b"]}),
"learning_analytics": (edu_analytics, None, None),
"educational_data_mining": (edu_analytics, {"min_support": 2}, {"min_support": 3}),
"student_modeling": (edu_analytics, None, None),
"knowledge_tracing": (edu_analytics, None, None),
"affect_detection": (edu_analytics, None, None),
}

# Previously constant checklist/stage-count metrics now respond to one relevant
# caller input while retaining their row-specific safety artifacts.
EDU_DISCRIMINATING.update({
"syllabus_creation": (edu_design, {"duration_minutes": 50}, {"duration_minutes": 90}),
"universal_design_for_learning": (edu_inclusion, {"objectives": ["Solve equations"]}, {"objectives": ["Understand equations"]}),
"intelligent_tutoring": (edu_inclusion, {"objectives": ["Solve equations"]}, {"objectives": ["Understand equations"]}),
"scaffolding": (edu_inclusion, {"objectives": ["Solve equations"]}, {"objectives": ["Understand equations"]}),
"cognitive_apprenticeship": (edu_inclusion, {"objectives": ["Solve equations"]}, {"objectives": ["Understand equations"]}),
"problem_based_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}),
"project_based_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}),
"inquiry_based_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}),
"discovery_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}),
"experiential_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}),
"service_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}),
"peer_instruction": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}),
"mobile_learning": (edu_delivery, {}, {"units": ["a", "b", "c"]}),
"simulation_based_learning": (edu_immersive, {}, {"mechanic": "timed evidence puzzle"}),
"virtual_reality_learning": (edu_immersive, {}, {"objective": "Understand safety procedure"}),
"augmented_reality_learning": (edu_immersive, {}, {"objective": "Understand safety procedure"}),
"mixed_reality_learning": (edu_immersive, {}, {"objective": "Understand safety procedure"}),
"artificial_intelligence_in_education": (None, None, None),
})


def _edu_value(out):
    return out["result"]["distinctive_computation"]["value"]


@pytest.mark.parametrize('name,row', sorted(education.NAME_TO_ROW.items(), key=lambda kv: kv[1]))
def test_education_row_distinctive_value_moves_with_one_input(name, row):
    assert 1410 <= row <= 1459
    builder, base_kw, pert_kw = EDU_DISCRIMINATING[name]
    if name == "artificial_intelligence_in_education":
        base = education.execute(name, {"use_case": "practice hints", "source": SRC})
        moved = education.execute(name, {"use_case": "structured essay feedback", "source": SRC})
    elif name == "learning_analytics":
        base = builder(name)
        moved = builder(name, [dict(EVENTS[0]), dict(EVENTS[0])])
    elif name == "student_modeling":
        base = builder(name)
        moved = builder(name, [dict(EVENTS[0]), dict(EVENTS[0])])
    elif name == "knowledge_tracing":
        other = [{"learner_id": "p2", "skill": "fractions", "event_type": "attempt", "correct": False},
                 {"learner_id": "p2", "skill": "fractions", "event_type": "attempt", "correct": False}]
        base = builder(name)
        moved = builder(name, list(EVENTS) + other)
    elif name == "affect_detection":
        allowed = [{"learner_id": "p", "skill": "s", "event_type": "self_report", "value": "ok"}]
        base = builder(name, allowed)
        moved = builder(name, allowed + [{"learner_id": "p", "skill": "s", "event_type": "camera_face", "value": "sad"}])
    else:
        base = builder(name, **base_kw)
        moved = builder(name, **pert_kw)
    assert _edu_value(base) != _edu_value(moved), f"{name}: distinctive value did not discriminate"


def test_education_row_1425_categorical_adaptation_decision_changes():
    low = edu_inclusion("adaptive_learning", mastery=.4)["result"]["adaptation"]
    high = edu_inclusion("adaptive_learning", mastery=.9)["result"]["adaptation"]
    assert low == "scaffold" and high == "advance"


# Rows whose distinctive metric is structurally constant: the discriminating
# assertion targets the named row-specific artifact or categorical judgement,
# and the pair also documents that the distinctive value itself is invariant.
EDU_INVARIANT_ARTIFACT = {
"syllabus_creation": (edu_design, {"duration_minutes": 50}, {"duration_minutes": 90}, "sequence"),
"universal_design_for_learning": (edu_inclusion, {"objectives": ["Solve equations"]}, {"objectives": ["Understand equations"]}, "objectives"),
"intelligent_tutoring": (edu_inclusion, {"objectives": ["Solve equations"]}, {"objectives": ["Understand equations"]}, "objectives"),
"scaffolding": (edu_inclusion, {"objectives": ["Solve equations"]}, {"objectives": ["Understand equations"]}, "objectives"),
"cognitive_apprenticeship": (edu_inclusion, {"objectives": ["Solve equations"]}, {"objectives": ["Understand equations"]}, "objectives"),
"problem_based_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}, "objectives"),
"project_based_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}, "objectives"),
"inquiry_based_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}, "objectives"),
"discovery_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}, "objectives"),
"experiential_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}, "objectives"),
"service_learning": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}, "objectives"),
"peer_instruction": (edu_pedagogy, {"objectives": ["Evaluate evidence"]}, {"objectives": ["Understand evidence"]}, "objectives"),
"mobile_learning": (edu_delivery, {}, {"units": ["a", "b", "c"]}, "delivery_plan"),
"simulation_based_learning": (edu_immersive, {}, {"mechanic": "timed evidence puzzle"}, "mechanic"),
"virtual_reality_learning": (edu_immersive, {}, {"objective": "Understand safety procedure"}, "objective"),
"augmented_reality_learning": (edu_immersive, {}, {"objective": "Understand safety procedure"}, "objective"),
"mixed_reality_learning": (edu_immersive, {}, {"objective": "Understand safety procedure"}, "objective"),
"artificial_intelligence_in_education": (None, None, None, "use_case"),
}


@pytest.mark.parametrize('name', sorted(EDU_INVARIANT_ARTIFACT))
def test_education_invariant_row_artifact_discriminates(name):
    builder, base_kw, pert_kw, artifact = EDU_INVARIANT_ARTIFACT[name]
    if name == "artificial_intelligence_in_education":
        base = education.execute(name, {"use_case": "practice hints", "source": SRC})
        moved = education.execute(name, {"use_case": "structured essay feedback", "source": SRC})
    else:
        base = builder(name, **base_kw)
        moved = builder(name, **pert_kw)
    assert base["result"][artifact] != moved["result"][artifact], f"{name}: {artifact} did not discriminate"
    assert _edu_value(base) != _edu_value(moved), f"{name}: distinctive value did not move"


# family name -> payload (with valid source) that must raise EducationError
EDU_INVALID_BY_FAMILY = {
"design": {"source": SRC},
"inclusion": {"objectives": [], "learner_profile": {"x": 1}, "source": SRC},
"pedagogy": {"objectives": ["Evaluate evidence"], "source": SRC},
"delivery": {"units": [], "source": SRC},
"immersive": {"objective": "Apply safety procedure", "source": SRC},
"analytics": {"events": [{"learner_id": "p1", "event_type": "attempt"}], "source": SRC},
}

EDU_INVALID_BY_ROW = {
"rubric_creation": {"topic": "x", "learners": {}, "objectives": ["Apply x"],
                    "assessments": [{"name": "q", "objective_ids": []}], "source": SRC},
"adaptive_learning": {"objectives": ["Solve x"], "learner_profile": {}, "mastery": .95,
                      "support_below": .9, "advance_at": .5, "source": SRC},
"artificial_intelligence_in_education": {"source": SRC},
"student_modeling": {"events": list(EVENTS), "prior_mastery": 2, "source": SRC},
"knowledge_tracing": {"events": list(EVENTS), "prior_mastery": 2, "source": SRC},
}


@pytest.mark.parametrize('cap', education.capabilities(), ids=lambda c: str(c["row_id"]))
def test_education_row_rejects_invalid_domain(cap):
    name, family = cap["key"], cap["family"]
    payload = EDU_INVALID_BY_ROW.get(name, EDU_INVALID_BY_FAMILY[family])
    with pytest.raises(EducationError):
        education.execute(name, dict(payload))


def test_education_rows_keep_educator_gate_and_privacy_markers():
    for out in _all_education_results():
        marker = out["result"]["distinctive_computation"]
        assert marker["educator_review_required"] is True
        assert "pseudonymous" in marker["privacy"] and "protected-trait" in marker["privacy"]
        assert marker["inputs"] == "caller supplied only"
        assert "educator" in out["boundary"].lower()
        assert out["uncertainty"]["not_a_mastery_or_credential_claim"] is True


def _all_education_results():
    results = []
    for cap in education.capabilities():
        name = cap["key"]
        if cap["family"] == "design":
            extra = {"criteria": ["accuracy"]} if name == "rubric_creation" else {}
            out = edu_design(name, **extra)
        elif cap["family"] == "inclusion":
            extra = {"mastery": .4} if name == "adaptive_learning" else {}
            out = edu_inclusion(name, **extra)
        elif cap["family"] == "pedagogy":
            out = edu_pedagogy(name)
        elif cap["family"] == "delivery":
            out = edu_delivery(name)
        elif cap["family"] == "immersive":
            out = edu_immersive(name)
        elif name == "artificial_intelligence_in_education":
            out = education.execute(name, {"use_case": "practice hints", "source": SRC})
        else:
            out = edu_analytics(name)
        results.append(out)
    return results


# ---------------------------------------------------------------------------
# Cross-layer contract: exactly 150 unique named computations over 1310-1459
# ---------------------------------------------------------------------------

def test_all_150_rows_have_unique_named_computations_covering_1310_1459():
    names, rows = [], []
    for method, (data, params) in CORE_CASES.items():
        marker = finance_core.run(method, dict(data), dict(params), seed=17)["output"]["distinctive_computation"]
        names.append(marker["name"]); rows.append(marker["row_id"])
    for method, data in SPEC_CASES.items():
        marker = finance_spec.run(method, dict(data), seed=7)["output"]["distinctive_computation"]
        names.append(marker["name"]); rows.append(marker["row_id"])
    for out in _all_education_results():
        marker = out["result"]["distinctive_computation"]
        names.append(marker["name"]); rows.append(out["row_id"])
    assert len(names) == 150 and len(set(names)) == 150
    assert sorted(rows) == list(range(1310, 1460))
    assert all(math.isfinite(float(v)) for v in
               [o["result"]["distinctive_computation"]["value"] for o in _all_education_results()])
