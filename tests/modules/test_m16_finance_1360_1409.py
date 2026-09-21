import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m16_executive_dashboard.finance import ROWS, run

CASES={
"structured_products":{"principal":1000,"underlying_return":.2},"exotic_options":{"paths":[[90,110],[100,80]],"strike":100},"barrier_options":{"path":[100,121,115],"strike":105,"barrier":120},"asian_options":{"path":[90,100,110],"strike":95},"lookback_options":{"path":[90,120,110]},"forward_starting_options":{"start_spot":100,"end_spot":120},"compound_options":{"inner_strike":100,"inner_maturity":1,"outer_strike":5},"chooser_options":{"strike":100},"rainbow_options":{"spots":[90,120],"weights":[.5,.5],"strike":100},"basket_options":{"spots":[90,120],"weights":[.5,.5],"strike":100},"quanto_options":{"strike":90,"fixed_fx":1.2},
"commodity_trading":{"spot":90,"futures":100,"maturity_years":1},"energy_markets":{"hourly_prices":[20,50],"load":[1,3]},"carbon_trading":{"emissions":120,"allowances":100,"allowance_price":30},"weather_derivatives":{"daily_temperatures":[10,20,12],"degree_day_strike":10,"currency_per_degree_day":5},"fx_trading":{"fx_rates":[80,81,80.5]},"currency_hedging":{"foreign_exposure":100,"forward_rate":82,"future_spot":80},"carry_trade":{"high_rate":.08,"low_rate":.03},"purchasing_power_parity":{"home_price_index":120,"foreign_price_index":100,"spot_rate":1.3},"interest_rate_parity":{"spot_rate":1.2,"home_rate":.05,"foreign_rate":.02},"international_finance":{"foreign_assets":500,"foreign_liabilities":400,"gdp":1000},
"sovereign_risk":{"debt_to_gdp":80,"deficit_to_gdp":5,"reserves_to_short_debt":.8,"bond_spread_bps":300},"country_risk":{"economic_risk":.2,"financial_risk":.3,"political_risk":.4},"political_risk":{"scenario_probabilities":[.8,.2],"scenario_losses":[0,100]},"emerging_markets":{"returns":[.01,.02,-.01],"benchmark_returns":[.0,.01,-.01],"liquidity_score":.7},"frontier_markets":{"returns":[.01,.02,-.01],"benchmark_returns":[.0,.01,-.01],"liquidity_score":.3},"microfinance":{"amount_disbursed":1000,"portfolio_outstanding":800,"overdue_over_30":80,"writeoffs":10,"active_borrowers":20},"development_finance":{"private_capital_mobilized":200,"public_capital":100,"beneficiaries":50,"program_cost":150},
"impact_investing":{"metrics":{"impact":.8,"risk":.4}},"esg_investing":{"metrics":{"e":.8,"s":.6,"g":.7}},"sustainable_finance":{"metrics":{"taxonomy":.9,"transition":.5}},"green_bonds":{"cashflows":[5,105],"yield_rate":.05,"eligible_green_allocations":90,"net_proceeds":100},"climate_finance":{"metrics":{"mitigation":.8,"adaptation":.6}},"carbon_markets":{"emissions":90,"allowances":100,"allowance_price":20,"market_kind":"voluntary"},
"behavioral_finance":{"actual_allocations":[.7,.3],"target_allocations":[.5,.5]},"prospect_theory":{"outcomes":[100,-100],"probabilities":[.5,.5]},"mental_accounting":{"accounts":[{"balance":100,"return":.1},{"balance":50,"return":0}]},"loss_aversion":{"gains":[10,20],"losses":[-30,-20]},"overconfidence":{"forecasts":[10,20],"actual":[12,16],"interval_widths":[2,2]},"anchoring":{"estimates":[10,20,30],"anchors":[9,19,29],"truths":[15,15,15]},"herding":{"individual_returns":[.1,-.1,.2],"market_returns":[.08,-.05,.1]},"market_efficiency":{"returns":[.1,-.1,.05,-.02,.01]},"emh_testing":{"returns":[.1,-.1,.05,-.02,.01]},"anomalies":{"returns":[.1,.2,-.1,.0],"period_labels":["Jan","Jan","Other","Other"]},
}
for m in ["momentum","value","size","quality","low_volatility","profitability"]: CASES[m]={"signal":[1,2,3,4,5,6,7,8],"future_returns":[-.04,-.03,-.02,-.01,.01,.02,.03,.04]}

def test_every_owner_row_has_real_deterministic_output_and_provenance():
    assert set(CASES)==set(ROWS) and sorted(ROWS.values())==list(range(1360,1410))
    for method,data in CASES.items():
        result=run(method,data,7)
        assert result["feature_row"]==ROWS[method]
        assert result["output"]["method_limits"] and "inputs" in result
        assert run(method,data,7)==result

def test_domain_specific_payoffs_risk_and_factor_semantics():
    assert run("barrier_options",CASES["barrier_options"])["output"]["payoff"]==0
    assert run("asian_options",CASES["asian_options"])["output"]["payoff"]==5
    assert run("carbon_trading",CASES["carbon_trading"])["output"]["compliance_cost"]==600
    assert run("microfinance",CASES["microfinance"])["output"]["portfolio_at_risk_30"]==pytest.approx(.1)
    assert run("prospect_theory",CASES["prospect_theory"])["output"]["subjective_value"]<0
    assert run("momentum",CASES["momentum"])["output"]["factor_return"]>0
    assert run("size",CASES["size"])["output"]["factor_return"]<0

def test_validation_rejects_bad_probability_and_alignment():
    with pytest.raises(ValueError): run("political_risk",{"scenario_probabilities":[.3,.3],"scenario_losses":[1,2]})
    with pytest.raises(ValueError): run("basket_options",{"spots":[1,2],"weights":[1],"strike":1})

def test_routes_are_mounted_under_executive_dashboard_boundary():
    c=TestClient(app); headers={"X-Tenant-ID":"t-finance","X-Actor-ID":"u-finance"}
    methods=c.get("/api/v1/executive-dashboard/finance/methods",headers=headers)
    assert methods.status_code==200 and len(methods.json())==50
    r=c.post("/api/v1/executive-dashboard/finance/analyze",headers=headers,json={"method":"profitability","data":CASES["profitability"]})
    assert r.status_code==200 and r.json()["feature_row"]==1409
    bad=c.post("/api/v1/executive-dashboard/finance/analyze",headers=headers,json={"method":"unknown","data":{}})
    assert bad.status_code==422

def test_rows_1360_1409_have_unique_named_non_transactional_computations():
    names=[]
    for method,data in CASES.items():
        marker=run(method,data)["output"]["distinctive_computation"]
        assert marker["row_id"]==ROWS[method] and marker["caller_supplied_inputs_only"]
        assert marker["transactional"] is False and marker["advice"] is False
        names.append(marker["name"])
    assert len(set(names))==50

def test_row_1385_frontier_liquidity_changes_with_relevant_input():
    low=dict(CASES["frontier_markets"]); high=dict(low); high["liquidity_score"]=.9
    assert run("frontier_markets",low)["output"]["liquidity_score"] != run("frontier_markets",high)["output"]["liquidity_score"]

def test_row_1395_prospect_reference_changes_subjective_value():
    base=dict(CASES["prospect_theory"]); shifted=dict(base,reference=50)
    assert run("prospect_theory",base)["output"]["subjective_value"] != run("prospect_theory",shifted)["output"]["subjective_value"]

def test_row_1404_momentum_signal_changes_factor_output():
    base=dict(CASES["momentum"]); reversed_signal=dict(base,signal=list(reversed(base["signal"])))
    assert run("momentum",base)["output"]["factor_return"] != run("momentum",reversed_signal)["output"]["factor_return"]
