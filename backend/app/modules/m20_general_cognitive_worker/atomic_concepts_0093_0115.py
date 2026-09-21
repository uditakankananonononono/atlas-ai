"""Strong, transparent atomic concept engines for ledger rows 93-115.
Research basis: Little's Law L=λW under stable flow; TOC focusing steps;
private-value auction expected-utility strategies; graph centrality/path tracing.
"""
from __future__ import annotations
import math
META={93:('50.2','system_delay'),94:('50.3','emergent_behavior'),95:('52.1','constraint_identification'),96:('52.2','constraint_improvement'),97:('61.1','exponential_model'),98:('61.2','logarithmic_model'),99:('61.3','power_law_model'),100:('68.1','value_creation'),101:('68.2','value_capture'),102:('72.1','wip_measurement'),103:('72.2','throughput_measurement'),104:('72.3','cycle_time_measurement'),105:('72.4','littles_law_check'),106:('82.1','bidding_optimization'),107:('82.2','selling_optimization'),108:('101.1','expertise_positioning'),109:('101.2','credibility_evidence'),110:('103.1','rapport_plan'),111:('103.2','similarity_grounding'),112:('104.1','shared_identity'),113:('104.2','shared_purpose'),114:('111.1','citation_influence'),115:('111.2','academic_idea_flow')};BY={x[1]:r for r,x in META.items()}
def _f(x,n):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError(f'{n} must be finite')
 return float(x)
def _v(d,k,n=1):
 x=d.get(k)
 if not isinstance(x,list) or len(x)<n:raise ValueError(f'{k} requires {n}+ values')
 return [_f(y,k) for y in x]
def _same(*x):
 if len({len(a) for a in x})!=1:raise ValueError('aligned arrays required')
def _ols(x,y):
 _same(x,y);mx=sum(x)/len(x);my=sum(y)/len(y);den=sum((z-mx)**2 for z in x)
 if den<=0:raise ValueError('predictor has zero variance')
 b=sum((a-mx)*(c-my) for a,c in zip(x,y))/den;a=my-b*mx;pred=[a+b*z for z in x];sst=sum((z-my)**2 for z in y);return a,b,1-sum((u-v)**2 for u,v in zip(y,pred))/sst if sst else 1

def run(method,d):
 if method not in BY:raise ValueError('unsupported atomic concept')
 r=BY[method];aid=META[r][0];limits=['Decision support on supplied evidence; no external effect or scale claim.'];o={}
 if r==93:
  impulse=_v(d,'input');response=_v(d,'response');_same(impulse,response);maxlag=int(d.get('max_lag',len(impulse)-1));scores=[]
  for lag in range(maxlag+1):
   pairs=list(zip(impulse[:len(impulse)-lag or None],response[lag:]));scores.append(sum(a*b for a,b in pairs)/len(pairs))
  best=max(range(len(scores)),key=lambda i:scores[i]);o={'estimated_delay_periods':best,'lag_scores':scores,'direct_effect_at_zero':scores[0]}
 elif r==94:
  individual=_v(d,'individual_predictions');observed=_v(d,'observed_system');_same(individual,observed);res=[y-x for x,y in zip(individual,observed)];threshold=_f(d.get('threshold',0),'threshold');o={'interaction_residuals':res,'emergent_indices':[i for i,x in enumerate(res) if abs(x)>threshold],'emergent_fraction':sum(abs(x)>threshold for x in res)/len(res)}
 elif r==95:
  names=d.get('stages');cap=_v(d,'capacities');demand=_f(d['demand_rate'],'demand_rate');_same(names,cap);util=[demand/x if x>0 else math.inf for x in cap];m=max(util);o={'constraint':names[util.index(m)],'utilizations':dict(zip(names,util)),'system_capacity':min(cap),'throughput_gap':max(0,demand-min(cap))}
 elif r==96:
  names=d.get('stages');cap=_v(d,'capacities');_same(names,cap);i=min(range(len(cap)),key=cap.__getitem__);uplift=_f(d['proposed_uplift'],'proposed_uplift');new=cap[:];new[i]+=uplift;o={'constraint':names[i],'exploit':['protect constraint from idle time','feed only quality work','buffer constraint'],'subordinate':'pace upstream release to constraint','before_capacity':min(cap),'after_capacity':min(new),'verified_gain':min(new)-min(cap),'next_constraint':names[min(range(len(new)),key=new.__getitem__)]}
 elif r in {97,98,99}:
  x=_v(d,'x',3);y=_v(d,'y',3);_same(x,y)
  if r==97:
   if any(z<=0 for z in y):raise ValueError('exponential y must be positive')
   la,b,r2=_ols(x,[math.log(z) for z in y]);o={'a':math.exp(la),'growth_rate':b,'equation':'y=a*exp(b*x)','r_squared_log_space':r2,'doubling_time':math.log(2)/b if b>0 else None}
  elif r==98:
   if any(z<=0 for z in x):raise ValueError('logarithmic x must be positive')
   a,b,r2=_ols([math.log(z) for z in x],y);o={'intercept':a,'coefficient':b,'equation':'y=a+b*ln(x)','r_squared':r2}
  else:
   if any(z<=0 for z in x+y):raise ValueError('power law requires positive x,y')
   la,b,r2=_ols([math.log(z) for z in x],[math.log(z) for z in y]);o={'scale':math.exp(la),'exponent':b,'equation':'y=a*x^b','r_squared_log_log':r2}
 elif r in {100,101}:
  stages=d.get('stages');_need=isinstance(stages,list) and stages
  if not _need:raise ValueError('stages required')
  rows=[]
  for s in stages:
   cost=_f(s.get('cost',0),'cost');willing=_f(s.get('customer_value',0),'customer_value');revenue=_f(s.get('revenue',0),'revenue');rows.append({'stage':s['name'],'value_created':willing-cost,'value_captured':revenue-cost,'cost':cost,'customer_value':willing,'revenue':revenue})
  key='value_created' if r==100 else 'value_captured';o={'stages':rows,'highest_point':max(rows,key=lambda x:x[key])['stage'],'total':sum(x[key] for x in rows),'metric':key}
 elif r in {102,103,104,105}:
  arrivals=d.get('arrivals',[]);departures=d.get('departures',[]);window=_f(d['window'],'window')
  if window<=0:raise ValueError('window positive required')
  wip=_f(d.get('ending_wip',len(arrivals)-len(departures)),'ending_wip');through=len(departures)/window;cts=[]
  for x in departures:
   if 'entered_at' in x and 'exited_at' in x:cts.append(_f(x['exited_at'],'exit')-_f(x['entered_at'],'enter'))
  measured_ct=sum(cts)/len(cts) if cts else d.get('cycle_time');pred=wip/through if through>0 else None
  o={'wip':wip,'throughput_per_time':through,'measured_cycle_time':measured_ct,'little_predicted_cycle_time':pred,'stable_window_assumed':True}
  if r==105:
   if measured_ct is None or pred is None:raise ValueError('throughput and cycle observations required')
   err=abs(float(measured_ct)-pred)/max(abs(float(measured_ct)),1e-12);o.update({'relative_error':err,'consistent':err<=_f(d.get('tolerance',.1),'tolerance')})
 elif r==106:
  value=_f(d['private_value'],'private_value');n=int(d['bidder_count']);kind=d.get('auction_type','first_price');_ = _f(d.get('entry_cost',0),'entry_cost')
  if value<0 or n<2:raise ValueError('nonnegative value and bidder_count>=2 required')
  bid=value*(n-1)/n if kind=='first_price' else value if kind in {'second_price','english'} else None
  if bid is None:raise ValueError('supported auction_type required')
  o={'recommended_bid':bid,'max_willingness_to_pay':value,'auction_type':kind,'strategy':'symmetric risk-neutral uniform-private-value benchmark' if kind=='first_price' else 'truthful private-value benchmark'};limits+=['Requires independent private values and benchmark distribution; never bids automatically.']
 elif r==107:
  values=sorted(_v(d,'buyer_values'));reserve_candidates=sorted(set([0]+values));best=max((r0,sum(v>=r0 for v in values)*r0) for r0 in reserve_candidates);o={'recommended_reserve':best[0],'empirical_revenue_bound':best[1],'buyer_count':len(values),'mechanism':d.get('mechanism','second_price_with_reserve')};limits+=['Empirical reserve can overfit; validate out of sample and follow auction law.']
 elif r in {108,109}:
  claims=d.get('claims');
  if not isinstance(claims,list) or not claims:raise ValueError('claims required')
  verified=[x for x in claims if x.get('evidence_uri') and x.get('issuer') and x.get('checked_at')];o={'verified_claims':verified,'unsupported_claims':[x for x in claims if x not in verified],'positioning_allowed':bool(verified),'evidence_plan':[{'claim':x.get('claim'),'needed':['issuer','evidence_uri','checked_at']} for x in claims if x not in verified]};limits+=['No fabricated credentials or implied authority.']
 elif r in {110,111}:
  mine=set(d.get('my_facts',[]));theirs=set(d.get('their_verified_facts',[]));shared=sorted(mine&theirs);o={'genuine_commonalities':shared,'open_questions':d.get('open_questions',[]),'rapport_steps':['listen','reflect accurately','ask permission','share only genuine common ground'],'fabricated_similarity_blocked':True,'usable_shared_count':len(shared)}
 elif r in {112,113}:
  mine=set(d.get('my_groups' if r==112 else 'my_goals',[]));theirs=set(d.get('their_verified_groups' if r==112 else 'their_verified_goals',[]));shared=sorted(mine&theirs);o={'shared':shared,'frame':('We share '+', '.join(shared)) if shared else None,'frame_allowed':bool(shared),'difference_preserved':True,'fabricated_unity_blocked':True}
 elif r in {114,115}:
  papers=d.get('papers');edges=d.get('citations');
  if not isinstance(papers,list) or not isinstance(edges,list):raise ValueError('papers and citations required')
  ids={x['id'] for x in papers};valid=[(e['citing'],e['cited']) for e in edges if e.get('citing') in ids and e.get('cited') in ids];incoming={i:0 for i in ids}
  for a,b in valid:incoming[b]+=1
  if r==114:o={'in_degree':incoming,'most_influential':max(incoming,key=incoming.get) if incoming else None,'valid_edge_count':len(valid),'invalid_edge_count':len(edges)-len(valid)}
  else:
   years={x['id']:x.get('year') for x in papers};viol=[{'citing':a,'cited':b} for a,b in valid if years.get(a) and years.get(b) and years[a]<years[b]];roots=[i for i in ids if incoming[i]==0];o={'idea_flow_edges':[{'from':b,'to':a} for a,b in valid],'chronology_violations':viol,'uncited_roots':sorted(roots),'valid':not viol}
 o['method_limits']=limits;return {'atomic_row':r,'atomic_row_id':aid,'method':method,'inputs':d,'output':o}
