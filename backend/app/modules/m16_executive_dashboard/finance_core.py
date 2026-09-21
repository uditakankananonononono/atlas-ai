"""Pure, auditable finance analytics for owner feature rows 1310-1359.

Inputs are caller supplied, calculations are deterministic, and outputs expose
assumptions and limits. No market data is silently fetched and no trade is made.
Rates are decimals and periods must be consistent unless explicitly stated.
"""
from __future__ import annotations
import math, random, statistics
ROWS={
'financial_statement_analysis':1310,'ratio_analysis':1311,'cash_flow_analysis':1312,'working_capital_management':1313,'capital_budgeting':1314,'npv_calculation':1315,'irr_analysis':1316,'payback_period':1317,'real_options_analysis':1318,'cost_of_capital':1319,'wacc_calculation':1320,'capm':1321,'beta_estimation':1322,'risk_adjusted_returns':1323,'portfolio_optimization':1324,'markowitz_model':1325,'black_litterman':1326,'factor_models':1327,'fama_french':1328,'risk_parity':1329,'asset_allocation':1330,'rebalancing_strategy':1331,'performance_attribution':1332,'sharpe_ratio':1333,'sortino_ratio':1334,'information_ratio':1335,'alpha_generation':1336,'beta_management':1337,'hedging_strategies':1338,'derivatives_pricing':1339,'black_scholes':1340,'binomial_trees':1341,'monte_carlo_pricing':1342,'greeks_calculation':1343,'volatility_modeling':1344,'garch_models':1345,'stochastic_volatility':1346,'jump_diffusion':1347,'fixed_income_analysis':1348,'yield_curve_construction':1349,'duration':1350,'convexity':1351,'credit_analysis':1352,'default_prediction':1353,'recovery_rates':1354,'credit_derivatives':1355,'cds_pricing':1356,'securitization':1357,'mbs_analysis':1358,'abs_analysis':1359}
SUMMARIES={m:m.replace('_',' ').title() for m in ROWS}
INPUTS={m:['documented caller-supplied finance inputs'] for m in ROWS}

def _f(x,name):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError(f'{name} must be finite')
 return float(x)
def _v(d,k,n=1):
 x=d.get(k)
 if not isinstance(x,list) or len(x)<n:return (_ for _ in ()).throw(ValueError(f'{k} needs at least {n} values'))
 return [_f(a,k) for a in x]
def _same(*xs):
 if len({len(x) for x in xs})!=1:raise ValueError('aligned arrays required')
def _mean(x):return sum(x)/len(x)
def _cov(x,y):
 _same(x,y);mx,my=_mean(x),_mean(y);return sum((a-mx)*(b-my) for a,b in zip(x,y))/(len(x)-1) if len(x)>1 else 0
def _var(x):return _cov(x,x)
def _sd(x):return math.sqrt(max(0,_var(x)))
def _norm(z):return .5*(1+math.erf(z/math.sqrt(2)))
def _disc(c,r):return sum(v/(1+r)**i for i,v in enumerate(c))
def _irr(c):
 lo,hi=-.999999,10.0
 flo,fhi=_disc(c,lo),_disc(c,hi)
 if flo*fhi>0:raise ValueError('cash flows do not bracket a unique IRR in (-1, 10]')
 for _ in range(200):
  mid=(lo+hi)/2;f=_disc(c,mid)
  if flo*f<=0:hi=mid;fhi=f
  else:lo=mid;flo=f
 return (lo+hi)/2
def _bs(s,k,t,r,sigma,q=0,kind='call'):
 if min(s,k,sigma)<=0 or t<=0:raise ValueError('spot, strike, volatility and time must be positive')
 d1=(math.log(s/k)+(r-q+.5*sigma*sigma)*t)/(sigma*math.sqrt(t));d2=d1-sigma*math.sqrt(t)
 call=s*math.exp(-q*t)*_norm(d1)-k*math.exp(-r*t)*_norm(d2)
 put=call-s*math.exp(-q*t)+k*math.exp(-r*t)
 return (call if kind=='call' else put),d1,d2
def _solve(a,b):
 n=len(b);m=[list(map(float,a[i]))+[float(b[i])] for i in range(n)]
 for i in range(n):
  p=max(range(i,n),key=lambda j:abs(m[j][i]))
  if abs(m[p][i])<1e-12:raise ValueError('singular covariance/design matrix')
  m[i],m[p]=m[p],m[i];q=m[i][i];m[i]=[v/q for v in m[i]]
  for j in range(n):
   if j!=i:q=m[j][i];m[j]=[x-q*y for x,y in zip(m[j],m[i])]
 return [m[i][-1] for i in range(n)]
def _base(method,data,params):return {'method':method,'feature_row':ROWS[method],'inputs':{'data':data,'params':params},'assumptions':[],'method_limits':[]}
def run(method,data,params=None,seed=0):
 if method not in ROWS:raise ValueError(f'unsupported finance method {method}')
 p=params or {};o=_base(method,data,p);a=o['assumptions'];lim=o['method_limits'];out={}
 if method in {'financial_statement_analysis','ratio_analysis'}:
  revenue=_f(data['revenue'],'revenue');cogs=_f(data['cogs'],'cogs');op=_f(data['operating_expenses'],'operating_expenses');assets=_f(data['assets'],'assets');liab=_f(data['liabilities'],'liabilities');cash=_f(data.get('cash',0),'cash');ca=_f(data.get('current_assets',assets),'current_assets');cl=_f(data.get('current_liabilities',liab),'current_liabilities');ni=_f(data.get('net_income',revenue-cogs-op),'net_income')
  if min(revenue,assets,ca)<=0 or cl<=0:raise ValueError('positive revenue/assets/current balances required')
  out={'gross_profit':revenue-cogs,'operating_income':revenue-cogs-op,'gross_margin':(revenue-cogs)/revenue,'operating_margin':(revenue-cogs-op)/revenue,'net_margin':ni/revenue,'current_ratio':ca/cl,'quick_ratio':(ca-cash if data.get('inventory') is None else ca-_f(data['inventory'],'inventory'))/cl,'debt_to_assets':liab/assets,'return_on_assets':ni/assets,'equity':assets-liab}
  a+=['Statements use one currency and aligned accounting periods.'];lim+=['Accounting-policy, quality-of-earnings and footnote review remain external.']
 elif method=='cash_flow_analysis':
  cfo=_f(data['operating'],'operating');cfi=_f(data['investing'],'investing');cff=_f(data['financing'],'financing');capex=_f(data.get('capex',0),'capex');opening=_f(data.get('opening_cash',0),'opening_cash');out={'net_change_in_cash':cfo+cfi+cff,'ending_cash':opening+cfo+cfi+cff,'free_cash_flow':cfo-capex,'cash_conversion':cfo/_f(data['net_income'],'net_income') if data.get('net_income') else None}
 elif method=='working_capital_management':
  ar=_f(data['receivables'],'receivables');inv=_f(data['inventory'],'inventory');ap=_f(data['payables'],'payables');sales=_f(data['sales'],'sales');cogs=_f(data['cogs'],'cogs');days=_f(p.get('days',365),'days');
  if sales<=0 or cogs<=0:raise ValueError('sales and cogs must be positive')
  dso=ar/sales*days;dio=inv/cogs*days;dpo=ap/cogs*days;out={'net_working_capital':ar+inv-ap,'dso':dso,'dio':dio,'dpo':dpo,'cash_conversion_cycle':dso+dio-dpo}
 elif method in {'capital_budgeting','npv_calculation'}:
  c=_v(data,'cash_flows');r=_f(p.get('discount_rate',data.get('discount_rate')),'discount_rate');
  if r<=-1:raise ValueError('discount rate must exceed -1')
  npv=_disc(c,r);out={'npv':npv,'discount_rate':r,'present_values':[v/(1+r)**i for i,v in enumerate(c)],'accept':npv>=0}
 elif method=='irr_analysis':
  c=_v(data,'cash_flows',2);rate=_irr(c);out={'irr':rate,'npv_at_irr':_disc(c,rate),'iterations':200};lim+=['Multiple sign changes can create multiple IRRs; this returns the bracketed root.']
 elif method=='payback_period':
  c=_v(data,'cash_flows',2);cum=c[0];pb=None
  for i,v in enumerate(c[1:],1):
   prev=cum;cum+=v
   if cum>=0 and pb is None:pb=i-1+((-prev/v) if v else 0)
  out={'payback_period':pb,'recovered':pb is not None,'ending_cumulative_cash':cum};lim+=['Undiscounted payback ignores cash flows after recovery.']
 elif method=='real_options_analysis':
  base=_f(data['base_npv'],'base_npv');up=_f(data['up_value'],'up_value');down=_f(data['down_value'],'down_value');prob=_f(p.get('up_probability',.5),'up_probability');cost=_f(data.get('exercise_cost',0),'exercise_cost');disc=_f(p.get('discount_rate',0),'discount_rate');opt=(prob*max(up-cost,0)+(1-prob)*max(down-cost,0))/(1+disc);out={'base_npv':base,'option_value':opt,'expanded_project_value':base+opt};a+=['One-period decision tree; risk-adjusted probability is caller supplied.']
 elif method in {'cost_of_capital','wacc_calculation'}:
  e=_f(data['equity'],'equity');d=_f(data['debt'],'debt');re=_f(data['cost_of_equity'],'cost_of_equity');rd=_f(data['cost_of_debt'],'cost_of_debt');tax=_f(data.get('tax_rate',0),'tax_rate');v=e+d
  if v<=0:raise ValueError('positive total capital required')
  out={'wacc':e/v*re+d/v*rd*(1-tax),'equity_weight':e/v,'debt_weight':d/v,'after_tax_debt_cost':rd*(1-tax)}
 elif method=='capm':
  rf=_f(data['risk_free_rate'],'risk_free_rate');beta=_f(data['beta'],'beta');rm=_f(data['market_return'],'market_return');out={'expected_return':rf+beta*(rm-rf),'market_risk_premium':rm-rf}
 elif method=='beta_estimation':
  x=_v(data,'market_returns',2);y=_v(data,'asset_returns',2);_same(x,y);v=_var(x)
  if v==0:raise ValueError('market returns have zero variance')
  beta=_cov(y,x)/v;out={'beta':beta,'alpha_periodic':_mean(y)-beta*_mean(x),'r_squared':(_cov(x,y)/(_sd(x)*_sd(y)))**2 if _sd(y) else 0,'observations':len(x)}
 elif method in {'risk_adjusted_returns','sharpe_ratio','sortino_ratio','information_ratio'}:
  r=_v(data,'returns',2);annual=_f(p.get('annualization',1),'annualization')
  if method=='information_ratio':
   b=_v(data,'benchmark_returns',2);_same(r,b);active=[x-y for x,y in zip(r,b)];te=_sd(active);out={'information_ratio':_mean(active)/te*math.sqrt(annual) if te else None,'tracking_error':te*math.sqrt(annual),'active_return':_mean(active)*annual}
  else:
   rf=_f(p.get('risk_free_rate',0),'risk_free_rate')/annual;ex=[x-rf for x in r];sd=_sd(ex);down=math.sqrt(sum(min(0,x)**2 for x in ex)/len(ex));out={'annualized_return':_mean(r)*annual,'volatility':sd*math.sqrt(annual),'sharpe_ratio':_mean(ex)/sd*math.sqrt(annual) if sd else None,'sortino_ratio':_mean(ex)/down*math.sqrt(annual) if down else None,'max_drawdown':_max_drawdown(r)}
 elif method in {'portfolio_optimization','markowitz_model'}:
  mu=_v(data,'expected_returns',2);cov=data.get('covariance');n=len(mu)
  if not isinstance(cov,list) or len(cov)!=n or any(not isinstance(row,list) or len(row)!=n for row in cov):raise ValueError('square covariance matrix required')
  target=_f(p.get('target_return',min(mu)),'target_return');inv1=_solve(cov,[1]*n);invm=_solve(cov,mu);A=sum(inv1);B=sum(invm);C=sum(x*y for x,y in zip(mu,invm));den=A*C-B*B
  if abs(den)<1e-12:raise ValueError('degenerate efficient frontier')
  w=[((C-B*target)*x+(A*target-B)*y)/den for x,y in zip(inv1,invm)];var=sum(w[i]*float(cov[i][j])*w[j] for i in range(n) for j in range(n));out={'weights':w,'expected_return':sum(x*y for x,y in zip(w,mu)),'volatility':math.sqrt(max(0,var)),'fully_invested':sum(w)};lim+=['Unconstrained mean-variance solution permits shorting and is input-sensitive.']
 elif method=='black_litterman':
  prior=_v(data,'prior_returns');views=_v(data,'views');conf=_v(data,'confidences');_same(prior,views,conf);out={'posterior_returns':[(1-c)*q+c*v for q,v,c in zip(prior,views,conf)],'prior_returns':prior};a+=['Views map one-to-one to assets; confidence is a 0-1 scalar blend.'];lim+=['Reference diagonal-confidence blend, not full pick-matrix Bayesian BL.']
 elif method in {'factor_models','fama_french'}:
  y=_v(data,'asset_returns',3);f=data.get('factors')
  if not isinstance(f,list) or len(f)!=len(y) or not f or any(not isinstance(row,list) or len(row)!=len(f[0]) for row in f):raise ValueError('aligned rectangular factors required')
  X=[[1.0]+list(map(float,row)) for row in f];k=len(X[0]);xtx=[[sum(row[i]*row[j] for row in X) for j in range(k)] for i in range(k)];xty=[sum(row[i]*v for row,v in zip(X,y)) for i in range(k)];coef=_solve(xtx,xty);pred=[sum(c*x for c,x in zip(coef,row)) for row in X];res=[a-b for a,b in zip(y,pred)];out={'alpha':coef[0],'factor_loadings':coef[1:],'residual_volatility':_sd(res),'r_squared':1-sum(x*x for x in res)/sum((x-_mean(y))**2 for x in y)}
 elif method=='risk_parity':
  vol=_v(data,'volatilities');
  if any(x<=0 for x in vol):raise ValueError('volatilities must be positive')
  inv=[1/x for x in vol];z=sum(inv);out={'weights':[x/z for x in inv],'target':'equal volatility contribution under zero-correlation approximation'};lim+=['Uses inverse-volatility approximation; full correlated ERC needs iterative covariance optimization.']
 elif method=='asset_allocation':
  scores=_v(data,'scores');mins=[float(x) for x in data.get('minimums',[0]*len(scores))];_same(scores,mins)
  if sum(mins)>1 or any(x<0 for x in mins):raise ValueError('valid minimum weights required')
  pos=[max(0,x) for x in scores];z=sum(pos);rem=1-sum(mins);w=[m+rem*(x/z if z else 1/len(scores)) for m,x in zip(mins,pos)];out={'weights':w,'minimums':mins}
 elif method=='rebalancing_strategy':
  current=_v(data,'current_weights');target=_v(data,'target_weights');_same(current,target);threshold=_f(p.get('threshold',.05),'threshold');value=_f(data.get('portfolio_value',1),'portfolio_value');trades=[(t-c)*value if abs(t-c)>=threshold else 0 for c,t in zip(current,target)];out={'trades':trades,'turnover':sum(abs(x) for x in trades)/(2*value),'triggered':[i for i,x in enumerate(trades) if x]}
 elif method=='performance_attribution':
  pw=_v(data,'portfolio_weights');bw=_v(data,'benchmark_weights');pr=_v(data,'portfolio_returns');br=_v(data,'benchmark_returns');_same(pw,bw,pr,br);alloc=[(p-b)*r for p,b,r in zip(pw,bw,br)];select=[b*(p-r) for b,p,r in zip(bw,pr,br)];inter=[(p-b)*(x-r) for p,b,x,r in zip(pw,bw,pr,br)];out={'allocation':sum(alloc),'selection':sum(select),'interaction':sum(inter),'active_return_explained':sum(alloc+select+inter),'by_asset':[{'allocation':x,'selection':y,'interaction':z} for x,y,z in zip(alloc,select,inter)]}
 elif method in {'alpha_generation','beta_management'}:
  beta=_f(data['beta'],'beta');actual=_f(data['actual_return'],'actual_return');rf=_f(data.get('risk_free_rate',0),'risk_free_rate');market=_f(data['market_return'],'market_return');alpha=actual-(rf+beta*(market-rf));target=_f(p.get('target_beta',beta),'target_beta');out={'jensen_alpha':alpha,'current_beta':beta,'target_beta':target,'hedge_notional_fraction':target-beta}
 elif method=='hedging_strategies':
  exposure=_f(data['exposure'],'exposure');beta=_f(data.get('beta',1),'beta');contract=_f(data['contract_notional'],'contract_notional');hedge_ratio=_f(p.get('hedge_ratio',1),'hedge_ratio');contracts=-exposure*beta*hedge_ratio/contract;out={'contracts':contracts,'rounded_contracts':round(contracts),'residual_notional':exposure*beta+round(contracts)*contract}
 elif method in {'derivatives_pricing','black_scholes'}:
  price,d1,d2=_bs(_f(data['spot'],'spot'),_f(data['strike'],'strike'),_f(data['time'],'time'),_f(data['rate'],'rate'),_f(data['volatility'],'volatility'),_f(data.get('dividend_yield',0),'dividend_yield'),p.get('option_type','call'));out={'price':price,'d1':d1,'d2':d2,'model':'Black-Scholes-Merton'}
 elif method=='binomial_trees':
  s=_f(data['spot'],'spot');k=_f(data['strike'],'strike');t=_f(data['time'],'time');r=_f(data['rate'],'rate');sigma=_f(data['volatility'],'volatility');steps=int(p.get('steps',100));kind=p.get('option_type','call');american=bool(p.get('american',False));dt=t/steps;u=math.exp(sigma*math.sqrt(dt));dn=1/u;q=(math.exp(r*dt)-dn)/(u-dn)
  if not 0<=q<=1:raise ValueError('invalid risk-neutral probability')
  vals=[max((s*u**j*dn**(steps-j)-k)*(1 if kind=='call' else -1),0) for j in range(steps+1)]
  for i in range(steps-1,-1,-1):
   vals=[math.exp(-r*dt)*(q*vals[j+1]+(1-q)*vals[j]) for j in range(i+1)]
   if american:vals=[max(v,max((s*u**j*dn**(i-j)-k)*(1 if kind=='call' else -1),0)) for j,v in enumerate(vals)]
  out={'price':vals[0],'steps':steps,'up':u,'down':dn,'risk_neutral_probability':q,'american':american}
 elif method=='monte_carlo_pricing':
  s=_f(data['spot'],'spot');k=_f(data['strike'],'strike');t=_f(data['time'],'time');r=_f(data['rate'],'rate');vol=_f(data['volatility'],'volatility');n=max(100,min(int(p.get('simulations',10000)),200000));kind=p.get('option_type','call');rng=random.Random(seed);pay=[]
  for _ in range(n):
   st=s*math.exp((r-.5*vol*vol)*t+vol*math.sqrt(t)*rng.gauss(0,1));pay.append(max((st-k)*(1 if kind=='call' else -1),0)*math.exp(-r*t))
  out={'price':_mean(pay),'standard_error':_sd(pay)/math.sqrt(n),'simulations':n,'seed':seed}
 elif method=='greeks_calculation':
  s=_f(data['spot'],'spot');k=_f(data['strike'],'strike');t=_f(data['time'],'time');r=_f(data['rate'],'rate');vol=_f(data['volatility'],'volatility');q=_f(data.get('dividend_yield',0),'dividend_yield');kind=p.get('option_type','call');price,d1,d2=_bs(s,k,t,r,vol,q,kind);pdf=math.exp(-d1*d1/2)/math.sqrt(2*math.pi);delta=math.exp(-q*t)*(_norm(d1) if kind=='call' else _norm(d1)-1);gamma=math.exp(-q*t)*pdf/(s*vol*math.sqrt(t));vega=s*math.exp(-q*t)*pdf*math.sqrt(t);theta=-(s*math.exp(-q*t)*pdf*vol)/(2*math.sqrt(t))+(q*s*math.exp(-q*t)*(_norm(d1) if kind=='call' else _norm(d1)-1))-r*k*math.exp(-r*t)*(_norm(d2) if kind=='call' else _norm(d2)-1);rho=(k*t*math.exp(-r*t)*_norm(d2)) if kind=='call' else (-k*t*math.exp(-r*t)*_norm(-d2));out={'price':price,'delta':delta,'gamma':gamma,'vega':vega,'theta_per_year':theta,'rho':rho}
 elif method in {'volatility_modeling','garch_models'}:
  r=_v(data,'returns',3);omega=_f(p.get('omega',1e-6),'omega');alpha=_f(p.get('alpha',.1),'alpha');beta=_f(p.get('beta',.85),'beta')
  if omega<0 or alpha<0 or beta<0 or alpha+beta>=1:raise ValueError('stationary GARCH(1,1) requires nonnegative parameters and alpha+beta<1')
  h=[_var(r)]
  for x in r[:-1]:h.append(omega+alpha*x*x+beta*h[-1])
  forecast=omega+alpha*r[-1]**2+beta*h[-1];out={'conditional_variances':h,'next_variance':forecast,'next_volatility':math.sqrt(forecast),'unconditional_variance':omega/(1-alpha-beta)}
 elif method=='stochastic_volatility':
  r=_v(data,'returns',3);phi=_f(p.get('phi',.95),'phi');mu=_f(p.get('mu',math.log(max(_var(r),1e-12))),'mu');h=mu
  filtered=[]
  for x in r:h=mu+phi*(h-mu)+(1-phi)*(math.log(x*x+1e-12)-h);filtered.append(math.exp(h))
  out={'filtered_variances':filtered,'next_variance':math.exp(mu+phi*(h-mu))};lim+=['Deterministic log-variance filter, not latent-state Bayesian estimation.']
 elif method=='jump_diffusion':
  s=_f(data['spot'],'spot');t=_f(data['time'],'time');r=_f(data['rate'],'rate');vol=_f(data['volatility'],'volatility');lam=_f(p.get('jump_intensity',0),'jump_intensity');jm=_f(p.get('jump_mean',0),'jump_mean');js=_f(p.get('jump_volatility',0),'jump_volatility');expected=s*math.exp(r*t);variance=s*s*math.exp(2*r*t)*(math.exp(vol*vol*t+lam*t*((math.exp(jm+js*js/2)-1)**2))-1);out={'expected_terminal_price':expected,'terminal_variance_approx':variance,'expected_jump_count':lam*t};a+=['Merton compound-Poisson lognormal jumps under caller-supplied risk-neutral parameters.']
 elif method in {'fixed_income_analysis','duration','convexity'}:
  c=_v(data,'cash_flows');y=_f(data['yield'],'yield');freq=int(p.get('frequency',1));times=[(i+1)/freq for i in range(len(c))];pv=[x/(1+y/freq)**(i+1) for i,x in enumerate(c)];price=sum(pv);mac=sum(t*x for t,x in zip(times,pv))/price;modified=mac/(1+y/freq);conv=sum(x*t*(t+1/freq)/(1+y/freq)**2 for x,t in zip(pv,times))/price;out={'price':price,'macaulay_duration':mac,'modified_duration':modified,'convexity':conv,'dv01':modified*price*.0001}
 elif method=='yield_curve_construction':
  instruments=data.get('instruments')
  if not isinstance(instruments,list) or not instruments:raise ValueError('instruments required')
  discounts=[]
  for i,inst in enumerate(instruments,1):
   coupon=_f(inst.get('coupon',0),'coupon');price=_f(inst['price'],'price');face=_f(inst.get('face',100),'face');known=sum(coupon*d for d in discounts);df=(price-known)/(face+coupon)
   if not 0<df<=1.5:raise ValueError('invalid bootstrapped discount factor')
   discounts.append(df)
  out={'discount_factors':discounts,'spot_rates':[df**(-1/(i+1))-1 for i,df in enumerate(discounts)]}
 elif method in {'credit_analysis','default_prediction'}:
  ebitda=_f(data['ebitda'],'ebitda');interest=_f(data['interest_expense'],'interest_expense');debt=_f(data['debt'],'debt');assets=_f(data['assets'],'assets');wc=_f(data.get('working_capital',0),'working_capital');re=_f(data.get('retained_earnings',0),'retained_earnings');sales=_f(data.get('sales',0),'sales');equity=_f(data.get('market_equity',0),'market_equity');z=1.2*wc/assets+1.4*re/assets+3.3*ebitda/assets+.6*equity/debt+sales/assets;pd=1/(1+math.exp(max(-50,min(50,z-3))));out={'interest_coverage':ebitda/interest if interest else None,'debt_to_ebitda':debt/ebitda if ebitda else None,'altman_style_score':z,'illustrative_default_probability':pd};lim+=['Illustrative score is not a calibrated rating or lending decision.']
 elif method=='recovery_rates':
  recovered=_f(data['recovered_amount'],'recovered_amount');exposure=_f(data['exposure_at_default'],'exposure_at_default');cost=_f(data.get('workout_cost',0),'workout_cost');out={'gross_recovery_rate':recovered/exposure,'net_recovery_rate':(recovered-cost)/exposure,'loss_given_default':1-(recovered-cost)/exposure}
 elif method in {'credit_derivatives','cds_pricing'}:
  spread=_f(data['spread'],'spread');notional=_f(data['notional'],'notional');maturity=_f(data['maturity'],'maturity');recovery=_f(data.get('recovery_rate',.4),'recovery_rate');discount=_f(p.get('discount_rate',0),'discount_rate');hazard=spread/max(1-recovery,1e-12);survival=math.exp(-hazard*maturity);premium=notional*spread*sum(math.exp(-(discount+hazard)*t) for t in range(1,math.ceil(maturity)+1));protection=notional*(1-recovery)*(1-survival)*math.exp(-discount*maturity/2);out={'implied_hazard_rate':hazard,'survival_probability':survival,'premium_leg_approx':premium,'protection_leg_approx':protection,'mark_to_model':protection-premium};lim+=['Flat hazard/spread, annual premium and midpoint default approximation.']
 elif method in {'securitization','mbs_analysis','abs_analysis'}:
  bal=_v(data,'pool_balances');rates=_v(data,'coupon_rates');pd=_v(data,'default_rates');rec=_v(data,'recovery_rates');_same(bal,rates,pd,rec);prep=[float(x) for x in data.get('prepayment_rates',[0]*len(bal))];_same(bal,prep);gross=sum(b*r for b,r in zip(bal,rates))/sum(bal);loss=sum(b*q*(1-z) for b,q,z in zip(bal,pd,rec));pre=sum(b*q for b,q in zip(bal,prep));enh=_f(data.get('credit_enhancement',0),'credit_enhancement');out={'pool_balance':sum(bal),'weighted_average_coupon':gross,'expected_credit_loss':loss,'expected_prepayment':pre,'credit_enhancement':enh,'enhancement_coverage':enh/loss if loss else None,'net_loss_after_enhancement':max(loss-enh,0)};a+=['Static pool, deterministic default/recovery/prepayment assumptions.'];lim+=['No waterfall timing, correlation, seasoning, delinquency transition or option-adjusted spread engine.']
 else:raise AssertionError(method)
 o['output']=out;return o

def _max_drawdown(r):
 wealth=peak=1.;m=0.
 for x in r:wealth*=1+x;peak=max(peak,wealth);m=min(m,wealth/peak-1)
 return m

# Quantitative rows retain their named outputs and gain an explicit model-risk
# report. Completeness is never represented as investment confidence.
_original_run = run
from app.core.depth_quality import attach_quality as _attach_quality

def run(method:str,data:dict,params:dict|None=None,seed:int=0)->dict:
    out=_original_run(method,data,params,seed)
    required=[k for k in data if k not in {'assumptions','sources','evidence'}]
    evidence=[x for key in ('sources','evidence') for x in data.get(key,[]) if isinstance(x,dict)]
    return _attach_quality(out,domain='finance',method=method,inputs=data,
        required_inputs=required,evidence=evidence,assumptions=data.get('assumptions',[]),
        limitations=['Model output is scenario analysis, not accounting, tax, valuation, trading, or investment advice.',
                     'Market data, conventions, calibration, liquidity, costs, policy, and model risk require independent review.'])
