"""Bounded exact supplied-input bookkeeping, not physical engineering validation."""
PREFIX='ROBUST1542'
from fractions import Fraction
import re
class UnitError(ValueError):pass
def refuse(code):raise UnitError(PREFIX+': '+code)
def shape(d,keys,code):
 if type(d)is not dict or set(d)!=set(keys):refuse(code)
def text(v):
 if type(v)is not str or not v.strip() or len(v)>100 or any(ord(c)<32 or ord(c)==127 for c in v):refuse('text must be nonblank control-free1..100')
 return v
def names(v,label,cap):
 if type(v)is not list or not 1<=len(v)<=cap:refuse(label+' must have1..'+str(cap)+' entries')
 for x in v:text(x)
 if len(v)!=len(set(v)):refuse('duplicate '+label)
 return v
def rational(v):
 if type(v)is not str or not re.fullmatch(r'-?[0-9]+(?:/[1-9][0-9]*)?',v):refuse('rational string required')
 parts=v.lstrip('-').split('/')
 if any(len(p)>7 or int(p)>1000000 for p in parts):refuse('rational components exceed1000000')
 return Fraction(v)
def bounded_rows(v,label):
 if type(v)is not list or not 1<=len(v)<=100:refuse(label+' must have1..100 entries')
 return v
def boundary():return {'release_authorized':False,'physical_validity_verified':False,'scope':'caller_supplied_bookkeeping_only'}
def prepare(d):
 shape(d,('control_factors','noise_factors','objective','scenarios'),'packet schema')
 controls=names(d['control_factors'],'control_factors',8);noise=names(d['noise_factors'],'noise_factors',8)
 if set(controls)&set(noise):refuse('control and noise names overlap')
 if d['objective'] not in ('maximize','minimize'):refuse('objective must be maximize or minimize')
 rows=bounded_rows(d['scenarios'],'scenarios');seen=set();vals=[];retained=[]
 for row in rows:
  shape(row,('id','control','noise','response'),'scenario schema');text(row['id'])
  if row['id'] in seen:refuse('duplicate scenario id')
  seen.add(row['id']);shape(row['control'],controls,'control schema');shape(row['noise'],noise,'noise schema')
  c={k:str(rational(row['control'][k])) for k in controls};n={k:str(rational(row['noise'][k])) for k in noise};v=rational(row['response']);vals.append(v)
  retained.append({'id':row['id'],'control':c,'noise':n,'response':str(v)})
 mean=sum(vals,Fraction(0))/len(vals)
 return {**boundary(),'scenarios':retained,'scenario_count':len(vals),'response_mean':str(mean),'response_range':str(max(vals)-min(vals)),
  'population_variance':str(sum((x-mean)**2 for x in vals)/len(vals)),'worst_case_response':str(min(vals) if d['objective']=='maximize' else max(vals)),
  'objective':d['objective'],'robustness_guaranteed':False}
