"""Focused evidence for finance feature rows 1310-1359."""
import math
import pytest
from app.modules.m16_executive_dashboard import analysis, finance

CASES={
'financial_statement_analysis':({'revenue':100,'cogs':60,'operating_expenses':20,'assets':200,'liabilities':80,'current_assets':70,'current_liabilities':35,'inventory':20,'net_income':12},{}),
'ratio_analysis':({'revenue':100,'cogs':60,'operating_expenses':20,'assets':200,'liabilities':80,'current_assets':70,'current_liabilities':35,'inventory':20,'net_income':12},{}),
'cash_flow_analysis':({'operating':30,'investing':-12,'financing':-5,'capex':10,'opening_cash':7,'net_income':20},{}),
'working_capital_management':({'receivables':20,'inventory':15,'payables':10,'sales':100,'cogs':60},{}),
'capital_budgeting':({'cash_flows':[-100,60,60]},{'discount_rate':.1}),'npv_calculation':({'cash_flows':[-100,60,60]},{'discount_rate':.1}),
'irr_analysis':({'cash_flows':[-100,60,60]},{}),'payback_period':({'cash_flows':[-100,30,50,40]},{}),
'real_options_analysis':({'base_npv':5,'up_value':80,'down_value':20,'exercise_cost':40},{'up_probability':.5,'discount_rate':.1}),
'cost_of_capital':({'equity':60,'debt':40,'cost_of_equity':.12,'cost_of_debt':.06,'tax_rate':.25},{}),'wacc_calculation':({'equity':60,'debt':40,'cost_of_equity':.12,'cost_of_debt':.06,'tax_rate':.25},{}),
'capm':({'risk_free_rate':.03,'beta':1.2,'market_return':.09},{}),'beta_estimation':({'market_returns':[.01,.02,-.01,.03],'asset_returns':[.012,.026,-.014,.038]},{}),
'risk_adjusted_returns':({'returns':[.01,.02,-.01,.03]},{'annualization':12}),'sharpe_ratio':({'returns':[.01,.02,-.01,.03]},{'annualization':12}),'sortino_ratio':({'returns':[.01,.02,-.01,.03]},{'annualization':12}),
'portfolio_optimization':({'expected_returns':[.05,.1],'covariance':[[.04,.01],[.01,.09]]},{'target_return':.08}),'markowitz_model':({'expected_returns':[.05,.1],'covariance':[[.04,.01],[.01,.09]]},{'target_return':.08}),
'black_litterman':({'prior_returns':[.05,.07],'views':[.08,.04],'confidences':[.75,.25]},{}),
'factor_models':({'asset_returns':[.01,.02,.015,.03],'factors':[[.01,.0],[.02,.01],[.0,.02],[.03,.01]]},{}),'fama_french':({'asset_returns':[.01,.02,.015,.03],'factors':[[.01,.0],[.02,.01],[.0,.02],[.03,.01]]},{}),
'risk_parity':({'volatilities':[.1,.2,.4]},{}),'asset_allocation':({'scores':[1,2,3],'minimums':[.1,.1,.1]},{}),'rebalancing_strategy':({'current_weights':[.3,.7],'target_weights':[.5,.5],'portfolio_value':1000},{'threshold':.05}),
'performance_attribution':({'portfolio_weights':[.6,.4],'benchmark_weights':[.5,.5],'portfolio_returns':[.1,.04],'benchmark_returns':[.08,.05]},{}),
'information_ratio':({'returns':[.03,.01,.02,.04],'benchmark_returns':[.02,.015,.01,.03]},{'annualization':12}),
'alpha_generation':({'beta':1.1,'actual_return':.12,'risk_free_rate':.03,'market_return':.1},{}),'beta_management':({'beta':1.1,'actual_return':.12,'risk_free_rate':.03,'market_return':.1},{'target_beta':.8}),
'hedging_strategies':({'exposure':1000000,'beta':1.2,'contract_notional':50000},{}),
'derivatives_pricing':({'spot':100,'strike':100,'time':1,'rate':.05,'volatility':.2},{}),'black_scholes':({'spot':100,'strike':100,'time':1,'rate':.05,'volatility':.2},{}),
'binomial_trees':({'spot':100,'strike':100,'time':1,'rate':.05,'volatility':.2},{'steps':100}),'monte_carlo_pricing':({'spot':100,'strike':100,'time':1,'rate':.05,'volatility':.2},{'simulations':20000}),'greeks_calculation':({'spot':100,'strike':100,'time':1,'rate':.05,'volatility':.2},{}),
'volatility_modeling':({'returns':[.01,-.02,.015,-.01]},{'omega':.00001,'alpha':.1,'beta':.8}),'garch_models':({'returns':[.01,-.02,.015,-.01]},{'omega':.00001,'alpha':.1,'beta':.8}),'stochastic_volatility':({'returns':[.01,-.02,.015,-.01]},{}),'jump_diffusion':({'spot':100,'time':1,'rate':.03,'volatility':.2},{'jump_intensity':.2,'jump_mean':-.05,'jump_volatility':.1}),
'fixed_income_analysis':({'cash_flows':[5,5,105],'yield':.05},{}),'duration':({'cash_flows':[5,5,105],'yield':.05},{}),'convexity':({'cash_flows':[5,5,105],'yield':.05},{}),
'yield_curve_construction':({'instruments':[{'price':95,'face':100},{'price':92,'face':100}]},{}),
'credit_analysis':({'ebitda':30,'interest_expense':5,'debt':80,'assets':200,'working_capital':20,'retained_earnings':30,'sales':180,'market_equity':120},{}),'default_prediction':({'ebitda':30,'interest_expense':5,'debt':80,'assets':200,'working_capital':20,'retained_earnings':30,'sales':180,'market_equity':120},{}),
'recovery_rates':({'recovered_amount':50,'exposure_at_default':100,'workout_cost':5},{}),'credit_derivatives':({'spread':.02,'notional':1000000,'maturity':5,'recovery_rate':.4},{}),'cds_pricing':({'spread':.02,'notional':1000000,'maturity':5,'recovery_rate':.4},{}),
'securitization':({'pool_balances':[100,200],'coupon_rates':[.05,.06],'default_rates':[.01,.02],'recovery_rates':[.5,.4],'prepayment_rates':[.05,.1],'credit_enhancement':5},{}),'mbs_analysis':({'pool_balances':[100,200],'coupon_rates':[.05,.06],'default_rates':[.01,.02],'recovery_rates':[.5,.4],'prepayment_rates':[.05,.1],'credit_enhancement':5},{}),'abs_analysis':({'pool_balances':[100,200],'coupon_rates':[.05,.06],'default_rates':[.01,.02],'recovery_rates':[.5,.4],'prepayment_rates':[.05,.1],'credit_enhancement':5},{})}

@pytest.mark.parametrize('method,row',finance.ROWS.items())
def test_rows_1310_1359_are_real_mounted_calculations(method,row):
 data,params=CASES[method];result=analysis.run(method,data,params,seed=17)
 assert result['feature_row']==row and result['method']==method
 assert isinstance(result['output'],dict) and result['output']
 assert result['inputs']['data']==data

def test_black_scholes_binomial_and_seeded_monte_carlo_agree():
 bs=analysis.run('black_scholes',*CASES['black_scholes'])['output']['price']
 tree=analysis.run('binomial_trees',*CASES['binomial_trees'])['output']['price']
 mc=analysis.run('monte_carlo_pricing',*CASES['monte_carlo_pricing'],seed=9)['output']
 assert bs==pytest.approx(10.4506,rel=1e-3) and tree==pytest.approx(bs,rel=.01)
 assert abs(mc['price']-bs)<3*mc['standard_error']
 assert mc==analysis.run('monte_carlo_pricing',*CASES['monte_carlo_pricing'],seed=9)['output']

def test_capital_budgeting_root_and_bond_risk_are_numerically_consistent():
 npv=analysis.run('npv_calculation',*CASES['npv_calculation'])['output']['npv'];irr=analysis.run('irr_analysis',*CASES['irr_analysis'])['output']
 assert npv>0 and abs(irr['npv_at_irr'])<1e-8
 bond=analysis.run('fixed_income_analysis',*CASES['fixed_income_analysis'])['output']
 assert bond['price']==pytest.approx(100) and bond['macaulay_duration']>bond['modified_duration']>0 and bond['convexity']>0

def test_portfolio_attribution_and_credit_outputs_reconcile():
 w=analysis.run('markowitz_model',*CASES['markowitz_model'])['output'];assert sum(w['weights'])==pytest.approx(1) and w['expected_return']==pytest.approx(.08)
 p=analysis.run('performance_attribution',*CASES['performance_attribution'])['output'];assert p['active_return_explained']==pytest.approx(.011)
 rec=analysis.run('recovery_rates',*CASES['recovery_rates'])['output'];assert rec['net_recovery_rate']+rec['loss_given_default']==pytest.approx(1)

def test_invalid_finance_inputs_fail_loudly():
 with pytest.raises(ValueError):analysis.run('irr_analysis',{'cash_flows':[1,2,3]})
 with pytest.raises(ValueError):analysis.run('garch_models',{'returns':[.1,.2,.3]},{'omega':.1,'alpha':.7,'beta':.4})
 with pytest.raises(ValueError):analysis.run('portfolio_optimization',{'expected_returns':[.1,.2],'covariance':[[1],[2]]})
