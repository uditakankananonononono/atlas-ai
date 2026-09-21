"""Deterministic, decision-support finance analytics for owner rows 1360-1409.

The functions calculate prices, exposures and empirical diagnostics from caller supplied
market data. They never trade, fetch restricted data, or present calculations as advice.
Every result preserves assumptions and limitations for auditability.
"""
from __future__ import annotations
import math, random, statistics
from typing import Any

NAMES = [
"structured_products","exotic_options","barrier_options","asian_options","lookback_options",
"forward_starting_options","compound_options","chooser_options","rainbow_options","basket_options",
"quanto_options","commodity_trading","energy_markets","carbon_trading","weather_derivatives",
"fx_trading","currency_hedging","carry_trade","purchasing_power_parity","interest_rate_parity",
"international_finance","sovereign_risk","country_risk","political_risk","emerging_markets",
"frontier_markets","microfinance","development_finance","impact_investing","esg_investing",
"sustainable_finance","green_bonds","climate_finance","carbon_markets","behavioral_finance",
"prospect_theory","mental_accounting","loss_aversion","overconfidence","anchoring","herding",
"market_efficiency","emh_testing","anomalies","momentum","value","size","quality","low_volatility","profitability"]
ROWS = dict(zip(NAMES, range(1360, 1410)))

def _num(d:dict,k:str, default:float|None=None)->float:
    v=d.get(k,default)
    if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v): raise ValueError(f"{k} must be finite")
    return float(v)
def _vec(d:dict,k:str,n:int=1)->list[float]:
    v=d.get(k)
    if not isinstance(v,list) or len(v)<n or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in v): raise ValueError(f"{k} needs at least {n} finite numbers")
    return [float(x) for x in v]
def _mean(x): return sum(x)/len(x)
def _sd(x): return statistics.stdev(x) if len(x)>1 else 0.0
def _corr(x,y):
    if len(x)!=len(y) or len(x)<2: raise ValueError("aligned series of length >=2 required")
    mx,my=_mean(x),_mean(y); den=math.sqrt(sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/den if den else 0.0
def _returns(prices):
    if len(prices)<2 or any(x<=0 for x in prices): raise ValueError("positive price series length >=2 required")
    return [prices[i]/prices[i-1]-1 for i in range(1,len(prices))]
def _norm(z): return .5*(1+math.erf(z/math.sqrt(2)))
def _bs(s,k,t,r,v,call=True,q=0):
    if min(s,k,t,v)<=0: raise ValueError("spot, strike, maturity and volatility must be positive")
    d1=(math.log(s/k)+(r-q+.5*v*v)*t)/(v*math.sqrt(t)); d2=d1-v*math.sqrt(t)
    return s*math.exp(-q*t)*(_norm(d1) if call else _norm(d1)-1)-k*math.exp(-r*t)*(_norm(d2) if call else _norm(d2)-1)
def _pv(cfs,rate): return sum(float(cf)/(1+rate)**(i+1) for i,cf in enumerate(cfs))
def _common(method,data): return {"method":method,"feature_row":ROWS[method],"inputs":data,"assumptions":[],"limits":["Decision support only; no order is placed and no investment recommendation is made."]}

def run(method:str,data:dict[str,Any],seed:int=0)->dict[str,Any]:
    if method not in ROWS: raise ValueError(f"unsupported finance method {method}")
    o=_common(method,data); a=o["assumptions"]; lim=o["limits"]; rng=random.Random(seed)
    s=_num(data,"spot",100) if method in NAMES[:11] else None
    if method=="structured_products":
        principal=_num(data,"principal"); floor=_num(data,"capital_floor",.9); participation=_num(data,"participation",1); ret=_num(data,"underlying_return")
        payoff=principal*max(floor,1+participation*ret); o["output"]={"redemption":payoff,"principal_at_risk":max(0,principal-payoff),"embedded_option_payoff":principal*max(0,participation*ret-(floor-1))}; a+=["Issuer pays the stated terminal payoff and remains solvent."]
    elif method=="exotic_options":
        paths=data.get("paths"); strike=_num(data,"strike"); kind=data.get("payoff","digital")
        if not isinstance(paths,list) or not paths or any(not isinstance(p,list) or not p for p in paths): raise ValueError("non-empty simulated paths required")
        if kind=="digital": vals=[1.0 if p[-1]>strike else 0.0 for p in paths]
        elif kind=="range": vals=[max(p)-min(p) for p in paths]
        else: raise ValueError("payoff must be digital or range")
        o["output"]={"payoff_type":kind,"expected_payoff":_mean(vals),"standard_error":_sd(vals)/math.sqrt(len(vals)),"path_count":len(vals)}; lim+=["Values supplied paths; no model calibration."]
    elif method=="barrier_options":
        path=_vec(data,"path",2); k=_num(data,"strike"); barrier=_num(data,"barrier"); direction=data.get("direction","up"); knock=data.get("knock","out"); hit=max(path)>=barrier if direction=="up" else min(path)<=barrier; vanilla=max(path[-1]-k,0); active=hit if knock=="in" else not hit
        o["output"]={"barrier_hit":hit,"active":active,"payoff":vanilla if active else 0.0,"monitoring_points":len(path)}; a+=["Barrier is monitored only at supplied observations."]
    elif method=="asian_options":
        path=_vec(data,"path",2); k=_num(data,"strike"); avg=statistics.geometric_mean(path) if data.get("average") == "geometric" else _mean(path); o["output"]={"average":avg,"payoff":max(avg-k,0),"observations":len(path)}; a+=["Equal-weight observation schedule."]
    elif method=="lookback_options":
        path=_vec(data,"path",2); typ=data.get("type","floating_call"); payoff=path[-1]-min(path) if typ=="floating_call" else max(path)-path[-1]
        o["output"]={"path_min":min(path),"path_max":max(path),"payoff":max(payoff,0),"type":typ}; a+=["Discrete supplied path, without continuous-monitoring correction."]
    elif method=="forward_starting_options":
        start=_num(data,"start_spot"); end=_num(data,"end_spot"); m=_num(data,"strike_multiplier",1); o["output"]={"strike_fixed_at_start":m*start,"payoff":max(end-m*start,0),"forward_return":end/start-1}
    elif method=="compound_options":
        inner=_bs(s,_num(data,"inner_strike"),_num(data,"inner_maturity"),_num(data,"rate",.02),_num(data,"volatility",.2)); outer_k=_num(data,"outer_strike"); o["output"]={"inner_option_value":inner,"outer_intrinsic_proxy":max(inner-outer_k,0)}; lim+=["Outer value is intrinsic-at-decision proxy, not Geske closed form."]
    elif method=="chooser_options":
        k=_num(data,"strike"); t=_num(data,"maturity",1); r=_num(data,"rate",.02); v=_num(data,"volatility",.2); call=_bs(s,k,t,r,v); put=_bs(s,k,t,r,v,False); o["output"]={"call_value":call,"put_value":put,"chosen":"call" if call>=put else "put","chooser_value_at_choice":max(call,put)}; lim+=["Choice is evaluated now rather than before final maturity."]
    elif method in {"rainbow_options","basket_options"}:
        spots=_vec(data,"spots",2); weights=_vec(data,"weights",2); strikes=_num(data,"strike");
        if len(spots)!=len(weights): raise ValueError("spots and weights must align")
        under=max(spots) if method=="rainbow_options" else sum(x*w for x,w in zip(spots,weights))/sum(weights); o["output"]={"reference_level":under,"payoff":max(under-strikes,0),"asset_count":len(spots),"construction":"best_of" if method=="rainbow_options" else "weighted_basket"}; lim+=["Terminal payoff only; no correlation-sensitive present value."]
    elif method=="quanto_options":
        k=_num(data,"strike"); fixed_fx=_num(data,"fixed_fx"); foreign_payoff=max(s-k,0); o["output"]={"foreign_payoff":foreign_payoff,"domestic_payoff":foreign_payoff*fixed_fx,"fixed_fx":fixed_fx}; a+=["Contractual fixed conversion rate applies."]
    elif method=="commodity_trading":
        spot=_num(data,"spot"); futures=_num(data,"futures"); t=_num(data,"maturity_years"); carry=math.log(futures/spot)/t; o["output"]={"basis":futures-spot,"annualized_implied_carry":carry,"curve":"contango" if futures>spot else "backwardation"}
    elif method=="energy_markets":
        prices=_vec(data,"hourly_prices",2); load=_vec(data,"load",2)
        if len(prices)!=len(load): raise ValueError("prices/load align")
        o["output"]={"time_weighted_price":_mean(prices),"load_weighted_price":sum(p*l for p,l in zip(prices,load))/sum(load),"peak_offpeak_spread":max(prices)-min(prices),"total_energy":sum(load)}
    elif method in {"carbon_trading","carbon_markets"}:
        emissions=_num(data,"emissions"); allowances=_num(data,"allowances"); price=_num(data,"allowance_price"); gap=emissions-allowances; o["output"]={"net_allowance_position":-gap,"compliance_cost":max(gap,0)*price,"surplus_value":max(-gap,0)*price,"market_kind":"compliance" if method=="carbon_trading" else data.get("market_kind","compliance")}
    elif method=="weather_derivatives":
        temps=_vec(data,"daily_temperatures"); base=_num(data,"base_temperature",18); strike=_num(data,"degree_day_strike"); rate=_num(data,"currency_per_degree_day"); kind=data.get("index","HDD"); idx=sum(max(base-t,0) for t in temps) if kind=="HDD" else sum(max(t-base,0) for t in temps); o["output"]={"weather_index":idx,"index":kind,"payoff":max(idx-strike,0)*rate,"days":len(temps)}
    elif method=="fx_trading":
        prices=_vec(data,"fx_rates",2); r=_returns(prices); o["output"]={"total_return":prices[-1]/prices[0]-1,"annualized_volatility":_sd(r)*math.sqrt(_num(data,"periods_per_year",252)),"max_rate":max(prices),"min_rate":min(prices)}
    elif method=="currency_hedging":
        exposure=_num(data,"foreign_exposure"); forward=_num(data,"forward_rate"); hedge=_num(data,"hedge_ratio",1); future=_num(data,"future_spot"); unhedged=exposure*future; hedged=exposure*(hedge*forward+(1-hedge)*future); o["output"]={"hedged_domestic_value":hedged,"unhedged_domestic_value":unhedged,"hedge_pnl":hedged-unhedged,"forward_notional":exposure*hedge}
    elif method=="carry_trade":
        high=_num(data,"high_rate"); low=_num(data,"low_rate"); fxchg=_num(data,"funding_currency_change",0); o["output"]={"rate_differential":high-low,"unlevered_return":high-low+fxchg,"break_even_fx_change":low-high}; a+=["Simple one-period rates and no funding/transaction costs."]
    elif method=="purchasing_power_parity":
        home=_num(data,"home_price_index"); foreign=_num(data,"foreign_price_index"); spot=_num(data,"spot_rate"); implied=home/foreign; o["output"]={"ppp_rate":implied,"currency_misalignment":spot/implied-1,"interpretation":"home_currency_overvalued" if spot<implied else "home_currency_undervalued"}
    elif method=="interest_rate_parity":
        spot=_num(data,"spot_rate"); home=_num(data,"home_rate"); foreign=_num(data,"foreign_rate"); t=_num(data,"years",1); implied=spot*(1+home*t)/(1+foreign*t); observed=_num(data,"forward_rate",implied); o["output"]={"implied_forward":implied,"observed_forward":observed,"parity_gap":observed-implied}
    elif method=="international_finance":
        assets=_num(data,"foreign_assets"); liabilities=_num(data,"foreign_liabilities"); gdp=_num(data,"gdp"); current=_num(data,"current_account",0); o["output"]={"net_international_investment_position":assets-liabilities,"niip_to_gdp":(assets-liabilities)/gdp,"current_account_to_gdp":current/gdp}
    elif method in {"sovereign_risk","country_risk","political_risk","emerging_markets","frontier_markets"}:
        if method=="sovereign_risk":
            debt=_num(data,"debt_to_gdp"); deficit=_num(data,"deficit_to_gdp"); reserves=_num(data,"reserves_to_short_debt"); spread=_num(data,"bond_spread_bps"); score=.3*min(debt/150,1)+.2*min(max(deficit,0)/15,1)+.2*(1-min(reserves,1))+.3*min(spread/1500,1)
            out={"risk_score":score,"components":{"debt":debt,"deficit":deficit,"reserves":reserves,"spread_bps":spread}}
        elif method=="country_risk":
            vals=[_num(data,k) for k in ("economic_risk","financial_risk","political_risk")]; w=data.get("weights",[.4,.3,.3]); out={"composite_risk":sum(x*y for x,y in zip(vals,w))/sum(w),"components":vals}
        elif method=="political_risk":
            probs=_vec(data,"scenario_probabilities"); losses=_vec(data,"scenario_losses");
            if len(probs)!=len(losses) or abs(sum(probs)-1)>1e-6: raise ValueError("aligned probabilities summing to one")
            out={"expected_loss":sum(p*l for p,l in zip(probs,losses)),"worst_case_loss":max(losses),"scenarios":len(probs)}
        else:
            returns=_vec(data,"returns",2); benchmark=_vec(data,"benchmark_returns",2); out={"annualized_return":_mean(returns)*12,"annualized_volatility":_sd(returns)*math.sqrt(12),"benchmark_correlation":_corr(returns,benchmark),"liquidity_score":_num(data,"liquidity_score"),"classification":method.replace("_markets","")}
        o["output"]=out; lim+=["Composite/scenario score is transparent and caller-defined, not a credit rating."]
    elif method=="microfinance":
        disbursed=_num(data,"amount_disbursed"); outstanding=_num(data,"portfolio_outstanding"); overdue=_num(data,"overdue_over_30"); writeoffs=_num(data,"writeoffs"); borrowers=_num(data,"active_borrowers"); o["output"]={"portfolio_at_risk_30":overdue/outstanding,"writeoff_ratio":writeoffs/_num(data,"average_portfolio",outstanding),"average_loan_balance":outstanding/borrowers,"capital_deployment":outstanding/disbursed}
    elif method=="development_finance":
        private=_num(data,"private_capital_mobilized"); public=_num(data,"public_capital"); beneficiaries=_num(data,"beneficiaries"); cost=_num(data,"program_cost"); o["output"]={"mobilization_ratio":private/public,"cost_per_beneficiary":cost/beneficiaries,"total_capital":private+public}
    elif method in {"impact_investing","esg_investing","sustainable_finance","climate_finance"}:
        metrics=data.get("metrics"); weights=data.get("weights")
        if not isinstance(metrics,dict) or not metrics: raise ValueError("named normalized metrics required")
        if weights is None: weights={k:1 for k in metrics}
        if set(weights)!=set(metrics) or any(not 0<=float(v)<=1 for v in metrics.values()): raise ValueError("metrics must align and be normalized [0,1]")
        score=sum(float(metrics[k])*float(weights[k]) for k in metrics)/sum(float(v) for v in weights.values()); o["output"]={"weighted_score":score,"metric_contributions":{k:float(metrics[k])*float(weights[k])/sum(float(v) for v in weights.values()) for k in metrics},"framework":method}; lim+=["Score depends on supplied measurements and weights; no claim of taxonomy alignment or impact causality."]
    elif method=="green_bonds":
        cfs=_vec(data,"cashflows"); y=_num(data,"yield_rate"); eligible=_num(data,"eligible_green_allocations"); proceeds=_num(data,"net_proceeds"); o["output"]={"dirty_price":_pv(cfs,y),"green_allocation_ratio":eligible/proceeds,"unallocated_proceeds":max(0,proceeds-eligible)}; lim+=["Eligibility is caller attested; external-review status is not inferred."]
    elif method=="behavioral_finance":
        actual=_vec(data,"actual_allocations"); target=_vec(data,"target_allocations");
        if len(actual)!=len(target): raise ValueError("allocations align")
        o["output"]={"allocation_drift_l1":sum(abs(a-b) for a,b in zip(actual,target)),"turnover_to_rebalance":sum(abs(a-b) for a,b in zip(actual,target))/2,"largest_bias_bucket":max(range(len(actual)),key=lambda i:abs(actual[i]-target[i]))}
    elif method=="prospect_theory":
        outcomes=_vec(data,"outcomes"); probs=_vec(data,"probabilities"); alpha=_num(data,"alpha",.88); lam=_num(data,"loss_aversion",2.25); ref=_num(data,"reference",0)
        if len(outcomes)!=len(probs) or abs(sum(probs)-1)>1e-6: raise ValueError("probabilities align and sum one")
        vals=[(x-ref)**alpha if x>=ref else -lam*(ref-x)**alpha for x in outcomes]; o["output"]={"subjective_value":sum(p*v for p,v in zip(probs,vals)),"outcome_values":vals,"reference":ref}
    elif method=="mental_accounting":
        accounts=data.get("accounts");
        if not isinstance(accounts,list) or not accounts: raise ValueError("accounts required")
        total=sum(_num(x,"balance") for x in accounts); weighted=sum(_num(x,"balance")*_num(x,"return",0) for x in accounts)/total; fungible=sum(_num(x,"balance")*(1+_num(x,"return",0)) for x in accounts); o["output"]={"total_balance":total,"portfolio_return":weighted,"fungible_terminal_value":fungible,"account_count":len(accounts)}
    elif method=="loss_aversion":
        gains=_vec(data,"gains"); losses=_vec(data,"losses"); o["output"]={"revealed_loss_aversion_ratio":abs(_mean(losses))/_mean(gains),"mean_gain":_mean(gains),"mean_absolute_loss":abs(_mean(losses))}
    elif method=="overconfidence":
        forecasts=_vec(data,"forecasts",2); actual=_vec(data,"actual",2); widths=_vec(data,"interval_widths",2)
        if not len(forecasts)==len(actual)==len(widths): raise ValueError("aligned observations")
        err=[abs(a-b) for a,b in zip(forecasts,actual)]; o["output"]={"mean_absolute_error":_mean(err),"mean_stated_half_width":_mean(widths)/2,"overconfidence_ratio":_mean(err)/(_mean(widths)/2),"overconfident":_mean(err)>_mean(widths)/2}
    elif method=="anchoring":
        estimates=_vec(data,"estimates",2); anchors=_vec(data,"anchors",2); truths=_vec(data,"truths",2)
        if not len(estimates)==len(anchors)==len(truths): raise ValueError("aligned observations")
        o["output"]={"anchor_estimate_correlation":_corr(estimates,anchors),"truth_estimate_correlation":_corr(estimates,truths),"mean_anchor_pull":_mean([abs(e-t)-abs(e-a) for e,a,t in zip(estimates,anchors,truths)])}
    elif method=="herding":
        individual=_vec(data,"individual_returns",2); market=_vec(data,"market_returns",2)
        if len(individual)!=len(market): raise ValueError("aligned returns")
        dispersions=[abs(i-m) for i,m in zip(individual,market)]; o["output"]={"cross_sectional_absolute_deviation":_mean(dispersions),"co_movement":_corr(individual,market),"same_direction_fraction":sum((i>=0)==(m>=0) for i,m in zip(individual,market))/len(market)}
    elif method in {"market_efficiency","emh_testing"}:
        returns=_vec(data,"returns",4); lag=returns[:-1]; lead=returns[1:]; rho=_corr(lag,lead); n=len(lag); z=rho*math.sqrt(n); o["output"]={"lag1_autocorrelation":rho,"runs":1+sum((returns[i]>=0)!=(returns[i-1]>=0) for i in range(1,len(returns))),"normal_approx_p_value":2*(1-_norm(abs(z))),"reject_random_walk":2*(1-_norm(abs(z)))<_num(data,"alpha",.05)}; lim+=["Simple weak-form diagnostic; rejection/non-rejection does not establish all forms of EMH."]
    elif method=="anomalies":
        returns=_vec(data,"returns",3); labels=data.get("period_labels")
        if not isinstance(labels,list) or len(labels)!=len(returns): raise ValueError("period_labels align")
        groups={};
        for label,r in zip(labels,returns): groups.setdefault(str(label),[]).append(r)
        means={k:_mean(v) for k,v in groups.items()}; o["output"]={"group_mean_returns":means,"spread":max(means.values())-min(means.values()),"strongest_group":max(means,key=means.get)}
    elif method in {"momentum","value","size","quality","low_volatility","profitability"}:
        signal=_vec(data,"signal",4); future=_vec(data,"future_returns",4)
        if len(signal)!=len(future): raise ValueError("signal and future returns align")
        order=sorted(range(len(signal)),key=lambda i:signal[i]); q=max(1,len(order)//4); low=order[:q]; high=order[-q:]
        # value/quality/profitability: high-minus-low; size and low vol convention favors low signal
        direction=-1 if method in {"size","low_volatility"} else 1; spread=direction*(_mean([future[i] for i in high])-_mean([future[i] for i in low])); o["output"]={"factor":method,"high_bucket_return":_mean([future[i] for i in high]),"low_bucket_return":_mean([future[i] for i in low]),"factor_return":spread,"rank_correlation":_corr([float(i) for i in range(len(order))],[future[j] for j in order]),"bucket_size":q}; a+=["Signal is measured before future returns; equal-weight quartile proxy."]
    else: raise AssertionError(method)
    o["output"]["assumptions"]=a; o["output"]["method_limits"]=lim
    return o
