"""Bounded signed qualitative transitions and exact synchronous stock flows."""
from itertools import product
from .calibration_predictor import text
from .anchored_assessment import rows
from .arithmetic_work import rational

def integer(value,label,low,high):
 if type(value)is not int or not low<=value<=high:raise ValueError(label+' requires integer['+str(low)+','+str(high)+']')
 return value

def qualitative(p):
 variables={}
 for row in rows(p.get('qualitative_variables'),'qualitative_variables',minimum=1,maximum=6):
  key=text(row.get('id'),'variable id');landmarks=[];signs=[]
  for mark in rows(row.get('landmarks'),'landmarks',minimum=2,maximum=5):
   ident=text(mark.get('id'),'landmark id');sign=integer(mark.get('sign'),'landmark sign',-1,1)
   if ident in landmarks:raise ValueError('unique landmark ids required')
   landmarks.append(ident);signs.append(sign)
  initial=text(row.get('initial'),'initial landmark')
  if key in variables or initial not in landmarks or signs!=sorted(signs):raise ValueError('unique variables, known initial and ordered landmark signs required')
  variables[key]={'landmarks':landmarks,'signs':signs,'initial':initial}
 influences={}
 for row in rows(p.get('qualitative_influences'),'qualitative_influences',maximum=64):
  key=text(row.get('id'),'influence id');a=text(row.get('from'),'influence from');b=text(row.get('to'),'influence to');sign=integer(row.get('sign'),'influence sign',-1,1);source=text(row.get('source'),'influence source')
  if key in influences or a not in variables or b not in variables or sign==0:raise ValueError('unique influences, known variables and nonzero signs required')
  influences[key]={'id':key,'from':a,'to':b,'sign':sign,'source':source}
 steps=integer(p.get('qualitative_steps'),'qualitative_steps',0,8);names=sorted(variables);current={tuple(variables[k]['landmarks'].index(variables[k]['initial'])for k in names)};history=[];expanded=0
 def exported(states):return [{k:variables[k]['landmarks'][state[i]]for i,k in enumerate(names)}for state in sorted(states)]
 history.append(exported(current))
 for step in range(steps):
  successors=set()
  for state in sorted(current):
   signs={k:variables[k]['signs'][state[i]]for i,k in enumerate(names)};options=[]
   for i,k in enumerate(names):
    effects={r['sign']*signs[r['from']]for r in influences.values()if r['to']==k}-{0}
    directions=(-1,0,1)if len(effects)==2 else tuple(effects)if effects else (0,)
    options.append(sorted({min(len(variables[k]['landmarks'])-1,max(0,state[i]+d))for d in directions}))
   for candidate in product(*options):
    expanded+=1
    if expanded>4096 or candidate not in successors and len(successors)>=256:
     return {'status':'state_budget_exhausted','states_by_step':history,'completed_steps':step,'ambiguous_successors_preserved':True,'source_truth_verified':False,'influences':[influences[k]for k in sorted(influences)],'boundary':'Explicit ordered signed landmarks and influences only; opposing effects retain decrease/stay/increase. Adjacent synchronous transitions, no physical validity or numeric prediction. Budget truncation returns only completed steps.'}
    successors.add(candidate)
  current=successors;history.append(exported(current))
 return {'status':'simulated','states_by_step':history,'completed_steps':steps,'ambiguous_successors_preserved':True,'source_truth_verified':False,'influences':[influences[k]for k in sorted(influences)],'boundary':'Explicit ordered signed landmarks and influences only; opposing effects retain decrease/stay/increase. Adjacent synchronous transitions, no physical validity or numeric prediction. Budget truncation returns only completed steps.'}

def stock_flow(p):
 stocks={}
 for row in rows(p.get('system_stocks'),'system_stocks',minimum=1,maximum=16):
  key=text(row.get('id'),'stock id');unit=text(row.get('unit'),'stock unit');initial=rational(row.get('initial'),'stock initial');source=text(row.get('source'),'stock source')
  if key in stocks or initial<0:raise ValueError('unique stock IDs and nonnegative initial required')
  stocks[key]={'unit':unit,'initial':initial,'source':source}
 time=text(p.get('system_time_unit'),'system_time_unit');dt=rational(p.get('system_dt'),'system_dt');steps=integer(p.get('system_steps'),'system_steps',0,64)
 if not 0<dt<=1000:raise ValueError('system_dt in(0,1000] required')
 flows={};edges=[]
 for row in rows(p.get('system_flows'),'system_flows',maximum=32):
  key=text(row.get('id'),'flow id');a=row.get('from');b=row.get('to');kind=row.get('rate_kind');driver=row.get('driver');rate=rational(row.get('rate'),'flow rate');delay=integer(row.get('delay_steps'),'delay_steps',0,8);unit=text(row.get('stock_unit'),'flow stock unit');tu=text(row.get('time_unit'),'flow time unit');source=text(row.get('source'),'flow source')
  if key in flows or a==b or a is not None and a not in stocks or b is not None and b not in stocks:raise ValueError('unique flows with distinct known endpoints or one external endpoint required')
  if kind not in ('constant','proportional')or rate<0 or rate>1000 or tu!=time or any(stocks[k]['unit']!=unit for k in [a,b]if k is not None):raise ValueError('supported nonnegative rates and matching endpoint/time units required')
  if kind=='constant'and(driver is not None or delay!=0)or kind=='proportional'and(driver not in stocks or stocks[driver]['unit']!=unit):raise ValueError('constant has no driver/delay; proportional has matching known driver required')
  flows[key]={'id':key,'from':a,'to':b,'kind':kind,'driver':driver,'rate':rate,'delay':delay,'source':source}
  if kind=='proportional'and rate:
   for endpoint,sign in [(a,-1),(b,1)]:
    if endpoint is not None:edges.append((driver,endpoint,sign))
 cycles=set();visited=0
 def walk(start,node,path,sign):
  nonlocal visited
  for a,b,s in sorted(set(edges)):
   if a!=node:continue
   visited+=1
   if visited>4096:raise ValueError('feedback cycle search exceeds4096 edges')
   if b==start:cycles.add((tuple(path),sign*s))
   elif b not in path and b>=start:walk(start,b,path+[b],sign*s)
 for key in sorted(stocks):walk(key,key,[key],1)
 units=sorted({r['unit']for r in stocks.values()});history=[{k:r['initial']for k,r in stocks.items()}];external={u:rational(0,'zero')for u in units};records=[];status='simulated';blocked_step=None;blocked=[]
 def bounded(value):
  if abs(value.numerator)>10**12 or value.denominator>10**12:raise ValueError('simulation rational components exceed10**12')
 for step in range(1,steps+1):
  pre=history[-1];post=dict(pre);pending=[];net={u:rational(0,'zero')for u in units}
  for key,r in sorted(flows.items()):
   driver_step=max(0,step-1-r['delay'])if r['kind']=='proportional' else None
   amount=r['rate']*dt*(history[driver_step][r['driver']]if r['kind']=='proportional'else 1);bounded(amount)
   a,b=r['from'],r['to'];unit=stocks[a if a is not None else b]['unit']
   if a is not None:post[a]-=amount
   else:net[unit]+=amount
   if b is not None:post[b]+=amount
   else:net[unit]-=amount
   pending.append({'step':step,'flow_id':key,'amount':str(amount),'driver_step':driver_step,'source':r['source']})
  for v in post.values():bounded(v)
  blocked=sorted(k for k,v in post.items()if v<0)
  if blocked:status='negative_stock_blocked';blocked_step=step;break
  history.append(post);records.extend(pending)
  for u in units:external[u]+=net[u];bounded(external[u])
 def totals(state):return {u:sum(v for k,v in state.items()if stocks[k]['unit']==u)for u in units}
 conserved=all(totals(history[-1])[u]-totals(history[0])[u]==external[u]for u in units)
 return {'status':status,'trajectory':[{'step':i,'stocks':{k:str(state[k])for k in sorted(stocks)},'totals_by_unit':{u:str(v)for u,v in totals(state).items()}}for i,state in enumerate(history)],'flow_records':records,'closed_system':all(r['from']is not None and r['to']is not None for r in flows.values()),'external_net_by_unit':{u:str(external[u])for u in units},'conservation_verified':conserved,'feedback_cycles':[{'stock_ids':list(path),'sign':sign}for path,sign in sorted(cycles)],'blocked_step':blocked_step,'blocked_stocks':blocked,'source_truth_verified':False,'real_world_prediction':None,'stock_sources':{k:stocks[k]['source']for k in sorted(stocks)},'boundary':'Exact finite synchronous constant/proportional stock flows with declared compatible stock/time units, constant initial prehistory and discrete delays. Negative steps are atomic refusals. Graph feedback signs are structural only; no real-world validity, stability or prediction.'}
