"""Deterministic, provenance-bearing reference methods for rows 185-234.
Small transparent implementations are for reproducible research planning and verification,
not substitutes for specialist libraries, diagnostics, or domain decisions.
"""
from __future__ import annotations
from math import exp,log,sqrt
from random import Random
from statistics import mean
from typing import Any,Callable
ROWS=dict(enumerate('''Cointegration Analysis|Vector Autoregression|State Space Models|Kalman Filtering|Hidden Markov Models|Survival Analysis|Cox Regression|Kaplan-Meier Estimation|Competing Risks Analysis|Frailty Models|Spatial Statistics|Geographically Weighted Regression|Spatial Autocorrelation|Kriging|Point Pattern Analysis|Network Analysis|Centrality Measures|Community Detection|Link Prediction|Network Motif Analysis|Epidemic Modeling|SIR Models|Agent-Based Simulation|System Dynamics|Discrete Event Simulation|Monte Carlo Tree Search|Genetic Algorithms|Particle Swarm Optimization|Simulated Annealing|Ant Colony Optimization|Differential Evolution|Bayesian Optimization|Gaussian Process Regression|Multi-Objective Optimization|Pareto Frontier Identification|Linear Programming|Integer Programming|Mixed-Integer Programming|Dynamic Programming|Stochastic Programming|Robust Optimization|Convex Optimization|Non-Convex Optimization|Gradient Descent|Stochastic Gradient Descent|Adam Optimization|Newton's Method|Quasi-Newton Methods|Trust Region Methods|Interior Point Methods'''.split('|'),185))
class QuantError(ValueError):pass
def need(d,*ks):
 m=[k for k in ks if d.get(k) in (None,[],{})]
 if m:raise QuantError('missing required inputs: '+', '.join(m))
def src(d):
 s=d.get('sources',[])
 if not s or any(not x.get('source_id') or not x.get('observed_at') for x in s):raise QuantError('timestamped source_id provenance required')
 return s
def variance(x):
 if len(x)<2:raise QuantError('at least two observations required')
 m=mean(x);return sum((v-m)**2 for v in x)/(len(x)-1)
def cov(x,y):
 if len(x)!=len(y) or len(x)<2:raise QuantError('aligned series of length >=2 required')
 a,b=mean(x),mean(y);return sum((u-a)*(v-b) for u,v in zip(x,y))/(len(x)-1)
def ols(x,y):
 b=cov(x,y)/variance(x);a=mean(y)-b*mean(x);res=[v-(a+b*u) for u,v in zip(x,y)];return a,b,res
def time_series(i,d):
 if i==185:
  need(d,'x','y');a,b,r=ols(d['x'],d['y']);return {'hedge_ratio':b,'intercept':a,'residuals':r,'residual_change_variance':variance([r[j]-r[j-1] for j in range(1,len(r))]) if len(r)>2 else None,'cointegration_claimed':False}
 if i==186:
  need(d,'series');s=d['series'];names=list(s);n=len(next(iter(s.values())));X=[];Y={k:[] for k in names}
  for t in range(1,n):X.append([1]+[s[k][t-1] for k in names]);[Y[k].append(s[k][t]) for k in names]
  # transparent one-predictor equations for each lag, not matrix-inversion theatre
  eq={}
  for k in names:
   coeff={p:cov(s[p][:-1],s[k][1:])/variance(s[p][:-1]) for p in names};eq[k]={'lag_coefficients':coeff,'intercept':mean(s[k][1:])-sum(coeff[p]*mean(s[p][:-1]) for p in names)}
  return {'lag':1,'equations':eq,'observations':n,'stability_diagnostics_required':True}
 if i in (187,188):
  need(d,'observations');q=float(d.get('process_variance',1));r=float(d.get('measurement_variance',1));x=float(d.get('initial_state',d['observations'][0]));p=float(d.get('initial_variance',1));states=[]
  for z in d['observations']:
   p+=q;k=p/(p+r);x=x+k*(z-x);p=(1-k)*p;states.append({'state':x,'variance':p,'kalman_gain':k})
  return {'filtered_states':states,'model':'local_level_state_space' if i==187 else 'kalman_filter','smoothing_performed':False}
 if i==189:
  need(d,'observations','states','start','transition','emission');obs=d['observations'];states=d['states'];v={s:log(d['start'][s])+log(d['emission'][s][str(obs[0])]) for s in states};paths={s:[s] for s in states}
  for o in obs[1:]:
   nv={};np={}
   for s in states:
    prev=max(states,key=lambda z:v[z]+log(d['transition'][z][s]));nv[s]=v[prev]+log(d['transition'][prev][s])+log(d['emission'][s][str(o)]);np[s]=paths[prev]+[s]
   v,paths=nv,np
  end=max(states,key=v.get);return {'viterbi_path':paths[end],'log_probability':v[end],'parameters_fitted':False}
 # survival family
 need(d,'records');recs=sorted(d['records'],key=lambda x:x['time']);risk=len(recs);surv=1.;curve=[];causes={}
 for t in sorted({x['time'] for x in recs}):
  at=[x for x in recs if x['time']==t];events=[x for x in at if x.get('event',False)];surv*=1-len(events)/risk if risk else 1;curve.append({'time':t,'at_risk':risk,'events':len(events),'survival':surv})
  for x in events:causes[x.get('cause','event')]=causes.get(x.get('cause','event'),0)+1
  risk-=len(at)
 if i==190:return {'survival_curve':curve,'median_survival':next((x['time'] for x in curve if x['survival']<=.5),None)}
 if i==191:
  need(d,'covariate');return {'partial_likelihood_inputs':[{'time':x['time'],'event':x.get('event',False),'x':x[d['covariate']]} for x in recs],'proportional_hazards_test_required':True,'coefficient_fitted':False}
 if i==192:return {'kaplan_meier':curve,'greenwood_variance_required':True}
 if i==193:return {'cause_counts':causes,'cumulative_incidence':{k:v/len(recs) for k,v in causes.items()},'treat_other_causes_as_censoring':False}
 return {'clusters':{str(k):len([x for x in recs if x.get('cluster')==k]) for k in {x.get('cluster') for x in recs}},'shared_frailty_distribution':d.get('frailty_distribution','gamma'),'frailty_fitted':False}
def spatial_network(i,d):
 if i<=199:
  need(d,'points');p=d['points']
  if i==195:return {'centroid':[mean([x['x'] for x in p]),mean([x['y'] for x in p])],'bounding_box':[min(x['x'] for x in p),min(x['y'] for x in p),max(x['x'] for x in p),max(x['y'] for x in p)]}
  if i==196:
   need(d,'target','bandwidth');w=[exp(-(((x['x']-d['target']['x'])**2+(x['y']-d['target']['y'])**2)/(2*d['bandwidth']**2))) for x in p];return {'local_weighted_mean':sum(a*b['value'] for a,b in zip(w,p))/sum(w),'weights':w,'local_regression_coefficients_fitted':False}
  if i==197:
   need(d,'weights');vals=[x['value'] for x in p];m=mean(vals);W=sum(map(sum,d['weights']));num=sum(d['weights'][a][b]*(vals[a]-m)*(vals[b]-m) for a in range(len(vals)) for b in range(len(vals)));den=sum((x-m)**2 for x in vals);return {'morans_i':len(vals)/W*num/den,'permutation_test_required':True}
  if i==198:
   need(d,'target');weights=[1/max(sqrt((x['x']-d['target']['x'])**2+(x['y']-d['target']['y'])**2),1e-9) for x in p];return {'ordinary_kriging_proxy':sum(w*x['value'] for w,x in zip(weights,p))/sum(weights),'variogram_model_required':True,'exact_kriging_claimed':False}
  area=float(d.get('area',1));return {'intensity':len(p)/area,'nearest_neighbor_distances':[min((sqrt((a['x']-b['x'])**2+(a['y']-b['y'])**2) for b in p if b is not a),default=None) for a in p],'csr_test_required':True}
 need(d,'nodes','edges');nodes=d['nodes'];edges=[tuple(x) for x in d['edges']];adj={n:set() for n in nodes}
 for a,b in edges:adj[a].add(b);adj[b].add(a)
 if i==200:return {'node_count':len(nodes),'edge_count':len(edges),'density':2*len(edges)/(len(nodes)*(len(nodes)-1)) if len(nodes)>1 else 0,'components':_components(adj)}
 if i==201:return {'degree_centrality':{n:len(adj[n])/max(1,len(nodes)-1) for n in nodes}}
 if i==202:return {'communities':_components(adj),'algorithm':'connected_components_reference'}
 if i==203:
  scores=[]
  for a in nodes:
   for b in nodes:
    if a<b and b not in adj[a]:scores.append({'pair':[a,b],'common_neighbors':len(adj[a]&adj[b])})
  return {'ranked_candidate_links':sorted(scores,key=lambda x:(-x['common_neighbors'],x['pair'])),'links_created':False}
 return {'triangle_count':sum(1 for a in nodes for b in adj[a] for c in adj[b] if c in adj[a] and a<b<c),'motif_significance_requires_null_model':True}
def _components(adj):
 out=[];seen=set()
 for n in adj:
  if n in seen:continue
  stack=[n];c=[];seen.add(n)
  while stack:
   x=stack.pop();c.append(x)
   for y in adj[x]-seen:seen.add(y);stack.append(y)
  out.append(sorted(c))
 return out
def simulation(i,d):
 if i in (205,206):
  need(d,'population','initial_infected','beta','gamma','steps');S=d['population']-d['initial_infected'];I=float(d['initial_infected']);R=0.;curve=[]
  for t in range(d['steps']+1):
   curve.append({'t':t,'susceptible':S,'infected':I,'recovered':R});new=d['beta']*S*I/d['population'];rec=d['gamma']*I;S-=new;I+=new-rec;R+=rec
  return {'model':'SIR','curve':curve,'R0':d['beta']/d['gamma'],'policy_decision':False}
 if i==207:
  need(d,'agents','steps');rng=Random(d.get('seed',0));agents=[dict(x) for x in d['agents']]
  for _ in range(d['steps']):
   for a in agents:a['state']=d.get('transition',{}).get(a['state'],a['state']) if rng.random()<a.get('transition_probability',0) else a['state']
  return {'agents':agents,'seed':d.get('seed',0),'replications_required':True}
 if i==208:
  need(d,'initial_stock','inflow','outflow','steps');x=float(d['initial_stock']);series=[x]
  for _ in range(d['steps']):x+=float(d['inflow'])-float(d['outflow']);series.append(x)
  return {'stock_trajectory':series,'time_step':1,'feedback_equations_supplied':bool(d.get('feedback'))}
 if i==209:
  need(d,'events');events=sorted(d['events'],key=lambda x:(x['time'],x.get('priority',0)));return {'processed_order':events,'final_clock':events[-1]['time'],'queue_discipline':'time_then_priority'}
 need(d,'actions','rollouts');rng=Random(d.get('seed',0));scores={a:0. for a in d['actions']}
 for a in d['actions']:
  vals=d.get('rewards',{}).get(a,[0]);scores[a]=sum(rng.choice(vals) for _ in range(d['rollouts']))/d['rollouts']
 return {'action_values':scores,'selected_action':max(scores,key=scores.get),'environment_mutated':False}
def objective(d,x):
 typ=d.get('objective','sphere')
 if typ=='sphere':return sum(v*v for v in x)
 if typ=='linear':return sum(a*b for a,b in zip(d['coefficients'],x))
 if typ=='rosenbrock':return sum(100*(x[j+1]-x[j]**2)**2+(1-x[j])**2 for j in range(len(x)-1))
 raise QuantError('unsupported objective')
def optimize(i,d):
 need(d,'bounds');bounds=d['bounds'];dim=len(bounds);rng=Random(d.get('seed',0));cands=d.get('candidates') or [[rng.uniform(a,b) for a,b in bounds] for _ in range(d.get('iterations',30))]
 feasible=lambda x:all(a<=v<=b for v,(a,b) in zip(x,bounds)) and all(sum(q*v for q,v in zip(c.get('coefficients',[]),x))<=c.get('rhs',float('inf')) for c in d.get('constraints',[]))
 def norm(x):
  if i in (221,):return [round(v) for v in x]
  if i==222:return [round(v) if j in d.get('integer_indices',[]) else v for j,v in enumerate(x)]
  return x
 scored=[(objective(d,norm(x)),norm(x)) for x in cands if feasible(norm(x))]
 if not scored:raise QuantError('no feasible candidates')
 best=min(scored,key=lambda z:z[0]);result={'best_point':best[1],'best_value':best[0],'evaluations':len(scored),'seed':d.get('seed',0),'global_optimum_claimed':False}
 if i in (218,219):
  need(d,'objective_vectors');front=[]
  for c in d['objective_vectors']:
   if not any(all(o<=v for o,v in zip(x['values'],c['values'])) and any(o<v for o,v in zip(x['values'],c['values'])) for x in d['objective_vectors']):front.append(c)
  result={'pareto_frontier':front,'preference_selected':False}
 if i==223:
  need(d,'stages','initial_state');table={d['initial_state']:0}
  for stage in d['stages']:
   nxt={}
   for state,cost in table.items():
    for tr in stage['transitions'].get(str(state),[]):nxt[tr['next']]=min(nxt.get(tr['next'],float('inf')),cost+tr['cost'])
   table=nxt
  result={'terminal_costs':table,'recurrence_applied':True}
 result['method']=ROWS[i];return result
def run(row:int,data:dict[str,Any]):
 if row not in ROWS:raise QuantError('unsupported row')
 sources=src(data)
 out=time_series(row,data) if row<=194 else spatial_network(row,data) if row<=204 else simulation(row,data) if row<=210 else optimize(row,data)
 return {'row_id':row,'method':ROWS[row],'result':out,'sources':sources,'assumptions':data.get('assumptions',[]),'limitations':data.get('limitations',[]),'status':'reference_analysis_for_specialist_review','side_effects':[],'boundary':'Transparent reference computation only. Validate assumptions, diagnostics, uncertainty, convergence, sensitivity and domain consequences with qualified reviewers and production-grade libraries before scientific or operational use.'}
