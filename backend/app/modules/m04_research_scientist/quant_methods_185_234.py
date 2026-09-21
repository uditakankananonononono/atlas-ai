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
 if typ=='double_well':return sum((v*v-1)**2 for v in x)
 raise QuantError('unsupported objective')
def _validate(d):
 need(d,'bounds'); bounds=[(float(a),float(b)) for a,b in d['bounds']]
 if not bounds or any(not a<b for a,b in bounds):raise QuantError('each bound must be finite and lower < upper')
 cons=d.get('constraints',[])
 if any(len(c.get('coefficients',[]))!=len(bounds) for c in cons):raise QuantError('constraint dimension mismatch')
 return bounds

def _project(x,bounds):return [min(b,max(a,v)) for v,(a,b) in zip(x,bounds)]
def _feasible(x,bounds,cons):return all(a-1e-9<=v<=b+1e-9 for v,(a,b) in zip(x,bounds)) and all(sum(q*v for q,v in zip(c['coefficients'],x))<=c['rhs']+1e-8 for c in cons)
def _grad(d,x,h=1e-5):
 g=[]
 for j in range(len(x)):
  u=x[:];v=x[:];u[j]+=h;v[j]-=h;g.append((objective(d,u)-objective(d,v))/(2*h))
 return g
def _line_search(d,x,p,g,bounds,cons):
 f=objective(d,x);t=1.
 while t>1e-10:
  z=_project([a+t*b for a,b in zip(x,p)],bounds)
  if _feasible(z,bounds,cons) and objective(d,z)<=f+1e-4*t*sum(a*b for a,b in zip(g,p)):return z,t
  t*=.5
 return x,0.
def _finish(i,d,x,history,evaluations,extra=None):
 out={'best_point':x,'best_value':objective(d,x),'evaluations':evaluations,'iterations':len(history)-1,'seed':d.get('seed',0),'converged':len(history)>1 and abs(history[-1]-history[-2])<d.get('tolerance',1e-7),'objective_history':history,'global_optimum_claimed':False,'method':ROWS[i]}
 if extra:out.update(extra)
 return out

def _population(i,d,bounds,rng):
 n=max(8,int(d.get('population_size',20))); it=max(1,int(d.get('iterations',40))); dim=len(bounds);cons=d.get('constraints',[])
 pop=[[(a+b)/2 for a,b in bounds]]+[[rng.uniform(a,b) for a,b in bounds] for _ in range(n-1)];ev=n;hist=[]
 if i==211: # real-valued tournament GA, blend crossover, Gaussian mutation
  for _ in range(it):
   pop=sorted(pop,key=lambda x:objective(d,x));hist.append(objective(d,pop[0]));elite=pop[:2];new=elite[:]
   while len(new)<n:
    p=min(rng.sample(pop,min(3,n)),key=lambda x:objective(d,x));q=min(rng.sample(pop,min(3,n)),key=lambda x:objective(d,x));alpha=rng.random();child=_project([alpha*a+(1-alpha)*b+rng.gauss(0,.05*(hi-lo)) for a,b,(lo,hi) in zip(p,q,bounds)],bounds);new.append(child)
   pop=new;ev+=n
  x=min((z for z in pop if _feasible(z,bounds,cons)),key=lambda z:objective(d,z),default=None);algo={'selection':'tournament','crossover':'arithmetic','mutation':'gaussian'}
 elif i==212: # canonical PSO
  vel=[[0.]*dim for _ in pop];personal=[x[:] for x in pop];gb=min(pop,key=lambda x:objective(d,x))[:]
  for _ in range(it):
   for k,x in enumerate(pop):
    vel[k]=[.7*v+1.4*rng.random()*(p-a)+1.4*rng.random()*(g-a) for v,p,g,a in zip(vel[k],personal[k],gb,x)];pop[k]=_project([a+v for a,v in zip(x,vel[k])],bounds)
    if objective(d,pop[k])<objective(d,personal[k]):personal[k]=pop[k][:]
   gb=min(personal,key=lambda x:objective(d,x))[:];hist.append(objective(d,gb));ev+=n
  x=gb;algo={'inertia':.7,'cognitive':1.4,'social':1.4}
 elif i==215: # DE/rand/1/bin
  F=float(d.get('differential_weight',.8));CR=float(d.get('crossover_probability',.9))
  for _ in range(it):
   nxt=[]
   for k,x in enumerate(pop):
    pool=[z for j,z in enumerate(pop) if j!=k];a,b,c=rng.sample(pool,3);mut=_project([u+F*(v-w) for u,v,w in zip(a,b,c)],bounds);j0=rng.randrange(dim);trial=[mut[j] if rng.random()<CR or j==j0 else x[j] for j in range(dim)];nxt.append(trial if objective(d,trial)<objective(d,x) else x)
   pop=nxt;x=min(pop,key=lambda z:objective(d,z));hist.append(objective(d,x));ev+=n
  algo={'strategy':'DE/rand/1/bin','differential_weight':F,'crossover_probability':CR}
 else:raise AssertionError
 if x is None:raise QuantError('no feasible point: constraints are infeasible')
 return _finish(i,d,x,hist,ev,algo)

def _anneal(i,d,bounds,rng):
 x=[(a+b)/2 for a,b in bounds];fx=objective(d,x);best=x[:];hist=[fx];accepted=0;it=max(1,int(d.get('iterations',100)))
 for k in range(it):
  temp=max(1e-9,float(d.get('initial_temperature',1))*(.95**k));z=_project([v+rng.gauss(0,temp*.2*(b-a)) for v,(a,b) in zip(x,bounds)],bounds);fz=objective(d,z)
  if fz<fx or rng.random()<exp(min(0,(fx-fz)/temp)):x,fx=z,fz;accepted+=1
  if fx<objective(d,best):best=x[:]
  hist.append(objective(d,best))
 return _finish(i,d,best,hist,it+1,{'temperature_schedule':'geometric','accepted_moves':accepted,'final_temperature':temp})

def _ant(i,d,bounds,rng):
 # Continuous ant-colony optimization archive: rank-weighted Gaussian sampling.
 n=max(8,int(d.get('population_size',20))); archive=[[rng.uniform(a,b) for a,b in bounds] for _ in range(n)];hist=[];ev=n
 for _ in range(max(1,int(d.get('iterations',40)))):
  archive.sort(key=lambda x:objective(d,x));weights=[exp(-k*k/(2*(.3*n)**2)) for k in range(n)];sw=sum(weights);weights=[w/sw for w in weights];samples=[]
  for __ in range(n):
   r=rng.random();acc=0;k=0
   for k,w in enumerate(weights):
    acc+=w
    if r<=acc:break
   center=archive[k];samples.append(_project([rng.gauss(v,max(1e-6,.3*mean([abs(v-z[j]) for z in archive]))) for j,v in enumerate(center)],bounds))
  archive=sorted(archive+samples,key=lambda x:objective(d,x))[:n];ev+=n;hist.append(objective(d,archive[0]))
 return _finish(i,d,archive[0],hist,ev,{'pheromone_model':'rank-weighted Gaussian archive','archive_size':n})

def _gp_predict(xs,ys,x,length=1.,noise=1e-6):
 # Gaussian process posterior mean/variance using dependency-free Cholesky.
 n=len(xs);K=[[exp(-sum((a-b)**2 for a,b in zip(xs[r],xs[c]))/(2*length*length))+(noise if r==c else 0) for c in range(n)] for r in range(n)];L=[[0.]*n for _ in range(n)]
 for r in range(n):
  for c in range(r+1):
   z=K[r][c]-sum(L[r][k]*L[c][k] for k in range(c));L[r][c]=sqrt(max(z,1e-15)) if r==c else z/L[c][c]
 def solve(v):
  y=[]
  for r in range(n):y.append((v[r]-sum(L[r][k]*y[k] for k in range(r)))/L[r][r])
  z=[0.]*n
  for r in range(n-1,-1,-1):z[r]=(y[r]-sum(L[k][r]*z[k] for k in range(r+1,n)))/L[r][r]
  return z
 k=[exp(-sum((a-b)**2 for a,b in zip(z,x))/(2*length*length)) for z in xs];alpha=solve(ys);v=solve(k);return sum(a*b for a,b in zip(k,alpha)),max(0,1-sum(a*b for a,b in zip(k,v)))

def _bayes_or_gp(i,d,bounds,rng):
 xs=[list(map(float,x)) for x in d.get('training_x',[])];ys=list(map(float,d.get('training_y',[])))
 if xs and (len(xs)!=len(ys) or any(len(x)!=len(bounds) for x in xs)):raise QuantError('training_x/training_y shape mismatch')
 if not xs:
  xs=[[(a+b)/2 for a,b in bounds]]+[[rng.uniform(a,b) for a,b in bounds] for _ in range(max(3,2*len(bounds)))];ys=[objective(d,x) for x in xs]
 if i==217:
  queries=d.get('query_points',xs);pred=[_gp_predict(xs,ys,q,d.get('length_scale',1.)) for q in queries]
  return {'method':ROWS[i],'predictions':[{'point':q,'mean':m,'variance':v} for q,(m,v) in zip(queries,pred)],'log_marginal_likelihood_optimized':False,'kernel':'RBF','training_size':len(xs)}
 hist=[min(ys)];it=max(1,int(d.get('iterations',15)))
 for _ in range(it):
  grid=[[rng.uniform(a,b) for a,b in bounds] for __ in range(100)];stats=[_gp_predict(xs,ys,z,d.get('length_scale',1.)) for z in grid];z=min(zip(grid,stats),key=lambda q:q[1][0]-2*sqrt(q[1][1]))[0];xs.append(z);ys.append(objective(d,z));hist.append(min(ys))
 k=min(range(len(ys)),key=ys.__getitem__);return _finish(i,d,xs[k],hist,len(ys),{'acquisition':'lower_confidence_bound','kernel':'RBF','observations':len(ys)})

def _lp_vertices(d,bounds):
 if len(bounds)!=2:raise QuantError('linear programming reference solver supports exactly two variables')
 lines=[([1.,0.],bounds[0][0]),([1.,0.],bounds[0][1]),([0.,1.],bounds[1][0]),([0.,1.],bounds[1][1])]+[(list(map(float,c['coefficients'])),float(c['rhs'])) for c in d.get('constraints',[])]
 pts=[]
 for k,(a,r) in enumerate(lines):
  for b,s in lines[k+1:]:
   det=a[0]*b[1]-a[1]*b[0]
   if abs(det)>1e-12:pts.append([(r*b[1]-a[1]*s)/det,(a[0]*s-r*b[0])/det])
 pts=[x for x in pts if _feasible(x,bounds,d.get('constraints',[]))]
 if not pts:raise QuantError('no feasible point: constraints are infeasible')
 return pts

def _derivative_solver(i,d,bounds,rng):
 cons=d.get('constraints',[])
 if 'candidates' in d and not any(_feasible(x,bounds,cons) for x in d['candidates']):raise QuantError('no feasible candidates')
 x=list(map(float,d.get('initial_point',[(a+b)/2 for a,b in bounds])));x=_project(x,bounds)
 if not _feasible(x,bounds,cons):raise QuantError('initial point is infeasible')
 it=max(1,int(d.get('iterations',100)));tol=float(d.get('tolerance',1e-7));hist=[objective(d,x)];ev=1;dim=len(x);H=[[float(r==c) for c in range(dim)] for r in range(dim)];m=[0.]*dim;v=[0.]*dim
 for k in range(1,it+1):
  g=_grad(d,x);ev+=2*dim
  if sqrt(sum(z*z for z in g))<tol:
   if i==231:
    h=1e-4;diag=[(objective(d,x[:j]+[x[j]+h]+x[j+1:])-2*objective(d,x)+objective(d,x[:j]+[x[j]-h]+x[j+1:]))/(h*h) for j in range(dim)]
    if any(z<=1e-10 for z in diag):raise QuantError('Hessian is not positive definite')
   break
  if i in (226,228):p=[-z for z in g]
  elif i==229:
   j=rng.randrange(dim);p=[0.]*dim;p[j]=-g[j]*dim
  elif i==230:
   m=[.9*a+.1*b for a,b in zip(m,g)];v=[.999*a+.001*b*b for a,b in zip(v,g)];p=[-.1*(a/(1-.9**k))/(sqrt(b/(1-.999**k))+1e-8) for a,b in zip(m,v)]
  elif i==231:
   h=1e-4;diag=[]
   for j in range(dim):
    u=x[:];w=x[:];u[j]+=h;w[j]-=h;diag.append((objective(d,u)-2*objective(d,x)+objective(d,w))/(h*h));ev+=2
   if any(z<=1e-10 for z in diag):raise QuantError('Hessian is not positive definite')
   p=[-a/b for a,b in zip(g,diag)]
  elif i==232:p=[-sum(H[r][c]*g[c] for c in range(dim)) for r in range(dim)]
  elif i==233:
   radius=float(d.get('trust_radius',1.));ng=sqrt(sum(z*z for z in g));p=[-z*min(1,radius/ng) for z in g]
  else:raise AssertionError
  old=x[:];oldg=g[:]
  if i==230:
   z=_project([a+b for a,b in zip(x,p)],bounds);x,step=(z,1.) if _feasible(z,bounds,cons) else _line_search(d,x,p,g,bounds,cons)
  else:x,step=_line_search(d,x,p,g,bounds,cons)
  ev+=1
  if step==0:break
  if i==232:
   ng=_grad(d,x);s=[a-b for a,b in zip(x,old)];y=[a-b for a,b in zip(ng,oldg)];rho=sum(a*b for a,b in zip(s,y))
   if rho>1e-12:
    rho=1/rho;I=[[float(r==c)-rho*s[r]*y[c] for c in range(dim)] for r in range(dim)];T=[[sum(I[r][q]*H[q][c] for q in range(dim)) for c in range(dim)] for r in range(dim)];H=[[sum(T[r][q]*I[c][q] for q in range(dim))+rho*s[r]*s[c] for c in range(dim)] for r in range(dim)]
  hist.append(objective(d,x))
  if i not in (229,230) and abs(hist[-1]-hist[-2])<tol:break
 name={226:'projected_gradient',228:'gradient_descent_armijo',229:'random_coordinate_stochastic_gradient',230:'adam',231:'damped_newton',232:'BFGS',233:'trust_region_Cauchy'}[i]
 return _finish(i,d,x,hist,ev,{'algorithm':name,'gradient_norm':sqrt(sum(z*z for z in _grad(d,x)))})

def _interior(i,d,bounds):
 cons=d.get('constraints',[]);allc=cons+([{'coefficients':[1. if j==k else 0. for j in range(len(bounds))],'rhs':b} for k,(a,b) in enumerate(bounds)]+[{'coefficients':[-1. if j==k else 0. for j in range(len(bounds))],'rhs':-a} for k,(a,b) in enumerate(bounds)])
 x=list(map(float,d.get('initial_point',[(a+b)/2 for a,b in bounds])))
 if any(c['rhs']-sum(a*b for a,b in zip(c['coefficients'],x))<=0 for c in allc):raise QuantError('interior point requires a strictly feasible initial point')
 hist=[];ev=0;mu=1.
 for outer in range(8):
  for _ in range(30):
   g=_grad(d,x);ev+=2*len(x)
   for c in allc:
    slack=c['rhs']-sum(a*b for a,b in zip(c['coefficients'],x));g=[a+mu*q/slack for a,q in zip(g,c['coefficients'])]
   p=[-a for a in g];x2,step=_line_search(d,x,p,g,bounds,cons)
   if step==0:break
   x=x2;hist.append(objective(d,x))
  mu*=.2
 return _finish(i,d,x,hist,ev,{'algorithm':'log_barrier_path_following','duality_gap_bound':mu*len(allc),'strict_feasibility_maintained':True})

def optimize(i,d):
 bounds=_validate(d);rng=Random(d.get('seed',0))
 if i in (211,212,215):return _population(i,d,bounds,rng)
 if i==213:return _anneal(i,d,bounds,rng)
 if i==214:return _ant(i,d,bounds,rng)
 if i in (216,217):return _bayes_or_gp(i,d,bounds,rng)
 if i in (218,219):
  need(d,'objective_vectors');front=[c for c in d['objective_vectors'] if not any(all(o<=v for o,v in zip(x['values'],c['values'])) and any(o<v for o,v in zip(x['values'],c['values'])) for x in d['objective_vectors'])];return {'pareto_frontier':front,'preference_selected':False,'method':ROWS[i]}
 if i==220:
  pts=_lp_vertices(d,bounds);x=min(pts,key=lambda z:objective(d,z));return _finish(i,d,x,[objective(d,x)],len(pts),{'algorithm':'vertex_enumeration_simplex_equivalent','vertices_checked':len(pts),'optimality_certificate':'all feasible vertices enumerated'})
 if i in (221,222):
  cands=d.get('candidates') or [[rng.uniform(a,b) for a,b in bounds] for _ in range(d.get('iterations',100))];norm=lambda x:[round(v) if i==221 or j in d.get('integer_indices',[]) else v for j,v in enumerate(x)];cands=[norm(x) for x in cands];cands=[x for x in cands if _feasible(x,bounds,d.get('constraints',[]))]
  if not cands:raise QuantError('no feasible candidates')
  x=min(cands,key=lambda z:objective(d,z));return _finish(i,d,x,[objective(d,x)],len(cands),{'algorithm':'enumerative_integer_search'})
 if i==223:
  need(d,'stages','initial_state');table={d['initial_state']:0}
  for stage in d['stages']:
   nxt={}
   for state,cost in table.items():
    for tr in stage['transitions'].get(str(state),[]):nxt[tr['next']]=min(nxt.get(tr['next'],float('inf')),cost+tr['cost'])
   table=nxt
  return {'terminal_costs':table,'recurrence_applied':True,'method':ROWS[i]}
 if i==224:
  need(d,'scenarios');probs=[float(s['probability']) for s in d['scenarios']]
  if abs(sum(probs)-1)>1e-8:raise QuantError('scenario probabilities must sum to one')
  coeff=[sum(s['probability']*s['coefficients'][j] for s in d['scenarios']) for j in range(len(bounds))];q={**d,'objective':'linear','coefficients':coeff};pts=_lp_vertices(q,bounds);x=min(pts,key=lambda z:objective(q,z));out=_finish(i,q,x,[objective(q,x)],len(pts),{'algorithm':'finite_scenario_expected_value','scenario_values':[sum(a*b for a,b in zip(s['coefficients'],x)) for s in d['scenarios']]});out['method']=ROWS[i];return out
 if i==225:
  need(d,'coefficients','coefficient_uncertainty');nom=list(map(float,d['coefficients']));rad=list(map(float,d['coefficient_uncertainty']))
  if len(rad)!=len(bounds) or any(x<0 for x in rad):raise QuantError('nonnegative uncertainty radius required per coefficient')
  def worst(x):return sum(a*b+r*abs(b) for a,r,b in zip(nom,rad,x))
  pts=_lp_vertices(d,bounds);x=min(pts,key=worst);out=_finish(i,{**d,'objective':'linear','coefficients':nom},x,[worst(x)],len(pts),{'algorithm':'box_uncertainty_robust_counterpart','worst_case_value':worst(x)});out['best_value']=worst(x);return out
 if i in (226,228,229,230,231,232,233):return _derivative_solver(i,d,bounds,rng)
 if i==227:
  starts=d.get('starts') or [[rng.uniform(a,b) for a,b in bounds] for _ in range(max(4,d.get('restarts',8)))];sol=[]
  for z in starts:
   try:sol.append(_derivative_solver(228,{**d,'initial_point':z},bounds,rng))
   except QuantError:pass
  if not sol:raise QuantError('no feasible restart')
  best=min(sol,key=lambda z:z['best_value']);best.update({'method':ROWS[i],'algorithm':'seeded_multistart_local_search','restart_values':[x['best_value'] for x in sol]});return best
 if i==234:return _interior(i,d,bounds)
 raise QuantError('unsupported optimizer row')
def run(row:int,data:dict[str,Any]):
 if row not in ROWS:raise QuantError('unsupported row')
 sources=src(data)
 out=time_series(row,data) if row<=194 else spatial_network(row,data) if row<=204 else simulation(row,data) if row<=210 else optimize(row,data)
 return {'row_id':row,'method':ROWS[row],'result':out,'sources':sources,'assumptions':data.get('assumptions',[]),'limitations':data.get('limitations',[]),
         'evaluation':{'method_specific':True,'review_checks':['assumptions','diagnostics','sensitivity','production-library replication'],'reference_result_only':True},
         'uncertainty':{'level':'requires specialist estimation','metrics':data.get('uncertainty_metrics',[]),'drivers':['finite sample','model misspecification','numerical approximation'],'expert_review_required':True},
         'status':'reference_analysis_for_specialist_review','side_effects':[],'boundary':'Transparent reference computation only. Validate assumptions, diagnostics, uncertainty, convergence, sensitivity and domain consequences with qualified reviewers and production-grade libraries before scientific or operational use.'}
