"""Focused evidence for finance feature rows 1310-1359."""
import math
import pytest
from app.modules.m16_executive_dashboard import analysis, finance_core as finance

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

def test_rows_1310_1359_have_unique_named_non_transactional_computations():
 names=[]
 for method,(data,params) in CASES.items():
  marker=analysis.run(method,data,params)["output"]["distinctive_computation"]
  assert marker["row_id"]==finance.ROWS[method] and marker["caller_supplied_inputs_only"]
  assert marker["transactional"] is False and marker["advice"] is False
  names.append(marker["name"])
 assert len(set(names))==50

def test_row_1315_npv_changes_with_discount_rate():
 data,params=CASES['npv_calculation']; higher=dict(params,discount_rate=.2)
 assert analysis.run('npv_calculation',data,params)['output']['npv'] != analysis.run('npv_calculation',data,higher)['output']['npv']

def test_row_1342_seeded_monte_carlo_changes_with_volatility():
 data,params=CASES['monte_carlo_pricing']; volatile=dict(data,volatility=.4)
 assert analysis.run('monte_carlo_pricing',data,params,seed=1)['output']['price'] != analysis.run('monte_carlo_pricing',volatile,params,seed=1)['output']['price']

# Exact expanded-ledger nodes delegate to the substantive input-discrimination fixture.
import importlib.util as _ilu
_ds=_ilu.spec_from_file_location("_atlas_discriminating",__file__.replace("test_m16_finance_1310_1359.py","test_discriminating_1310_1459.py"));_dm=_ilu.module_from_spec(_ds);_ds.loader.exec_module(_dm)
_assert_core_moves=_dm.test_core_row_distinctive_value_moves_with_one_input
def test_1310_financial_statement_analysis_distinctive_value_moves():
 _assert_core_moves("financial_statement_analysis",1310)
def test_1311_ratio_analysis_distinctive_value_moves():
 _assert_core_moves("ratio_analysis",1311)
def test_1312_cash_flow_analysis_distinctive_value_moves():
 _assert_core_moves("cash_flow_analysis",1312)
def test_1313_working_capital_management_distinctive_value_moves():
 _assert_core_moves("working_capital_management",1313)
def test_1314_capital_budgeting_distinctive_value_moves():
 _assert_core_moves("capital_budgeting",1314)
def test_1315_npv_calculation_distinctive_value_moves():
 _assert_core_moves("npv_calculation",1315)
def test_1316_irr_analysis_distinctive_value_moves():
 _assert_core_moves("irr_analysis",1316)
def test_1317_payback_period_distinctive_value_moves():
 _assert_core_moves("payback_period",1317)
def test_1318_real_options_analysis_distinctive_value_moves():
 _assert_core_moves("real_options_analysis",1318)
def test_1319_cost_of_capital_distinctive_value_moves():
 _assert_core_moves("cost_of_capital",1319)
def test_1320_wacc_calculation_distinctive_value_moves():
 _assert_core_moves("wacc_calculation",1320)
def test_1321_capm_distinctive_value_moves():
 _assert_core_moves("capm",1321)
def test_1322_beta_estimation_distinctive_value_moves():
 _assert_core_moves("beta_estimation",1322)
def test_1323_risk_adjusted_returns_distinctive_value_moves():
 _assert_core_moves("risk_adjusted_returns",1323)
def test_1324_portfolio_optimization_distinctive_value_moves():
 _assert_core_moves("portfolio_optimization",1324)
def test_1325_markowitz_model_distinctive_value_moves():
 _assert_core_moves("markowitz_model",1325)
def test_1326_black_litterman_distinctive_value_moves():
 _assert_core_moves("black_litterman",1326)
def test_1327_factor_models_distinctive_value_moves():
 _assert_core_moves("factor_models",1327)
def test_1328_fama_french_distinctive_value_moves():
 _assert_core_moves("fama_french",1328)
def test_1329_risk_parity_distinctive_value_moves():
 _assert_core_moves("risk_parity",1329)
def test_1330_asset_allocation_distinctive_value_moves():
 _assert_core_moves("asset_allocation",1330)
def test_1331_rebalancing_strategy_distinctive_value_moves():
 _assert_core_moves("rebalancing_strategy",1331)
def test_1332_performance_attribution_distinctive_value_moves():
 _assert_core_moves("performance_attribution",1332)
def test_1333_sharpe_ratio_distinctive_value_moves():
 _assert_core_moves("sharpe_ratio",1333)
def test_1334_sortino_ratio_distinctive_value_moves():
 _assert_core_moves("sortino_ratio",1334)
def test_1335_information_ratio_distinctive_value_moves():
 _assert_core_moves("information_ratio",1335)
def test_1336_alpha_generation_distinctive_value_moves():
 _assert_core_moves("alpha_generation",1336)
def test_1337_beta_management_distinctive_value_moves():
 _assert_core_moves("beta_management",1337)
def test_1338_hedging_strategies_distinctive_value_moves():
 _assert_core_moves("hedging_strategies",1338)
def test_1339_derivatives_pricing_distinctive_value_moves():
 _assert_core_moves("derivatives_pricing",1339)
def test_1340_black_scholes_distinctive_value_moves():
 _assert_core_moves("black_scholes",1340)
def test_1341_binomial_trees_distinctive_value_moves():
 _assert_core_moves("binomial_trees",1341)
def test_1342_monte_carlo_pricing_distinctive_value_moves():
 _assert_core_moves("monte_carlo_pricing",1342)
def test_1343_greeks_calculation_distinctive_value_moves():
 _assert_core_moves("greeks_calculation",1343)
def test_1344_volatility_modeling_distinctive_value_moves():
 _assert_core_moves("volatility_modeling",1344)
def test_1345_garch_models_distinctive_value_moves():
 _assert_core_moves("garch_models",1345)
def test_1346_stochastic_volatility_distinctive_value_moves():
 _assert_core_moves("stochastic_volatility",1346)
def test_1347_jump_diffusion_distinctive_value_moves():
 _assert_core_moves("jump_diffusion",1347)
def test_1348_fixed_income_analysis_distinctive_value_moves():
 _assert_core_moves("fixed_income_analysis",1348)
def test_1349_yield_curve_construction_distinctive_value_moves():
 _assert_core_moves("yield_curve_construction",1349)
def test_1350_duration_distinctive_value_moves():
 _assert_core_moves("duration",1350)
def test_1351_convexity_distinctive_value_moves():
 _assert_core_moves("convexity",1351)
def test_1352_credit_analysis_distinctive_value_moves():
 _assert_core_moves("credit_analysis",1352)
def test_1353_default_prediction_distinctive_value_moves():
 _assert_core_moves("default_prediction",1353)
def test_1354_recovery_rates_distinctive_value_moves():
 _assert_core_moves("recovery_rates",1354)
def test_1355_credit_derivatives_distinctive_value_moves():
 _assert_core_moves("credit_derivatives",1355)
def test_1356_cds_pricing_distinctive_value_moves():
 _assert_core_moves("cds_pricing",1356)
def test_1357_securitization_distinctive_value_moves():
 _assert_core_moves("securitization",1357)
def test_1358_mbs_analysis_distinctive_value_moves():
 _assert_core_moves("mbs_analysis",1358)
def test_1359_abs_analysis_distinctive_value_moves():
 _assert_core_moves("abs_analysis",1359)
