"""Bounded exact supplied-input bookkeeping, not physical engineering validation."""
PREFIX='RELTES1543'
from fractions import Fraction
import re
class UnitError(ValueError):pass
def refuse(code):raise UnitError(PREFIX+': '+code)
def shape(d,keys,code):
 if type(d)is not dict or set(d)!=set(keys):refuse(code)
def text(v):
 if type(v)is not str or len(v)>100 or not v.strip() or any(ord(c)<32 or ord(c)==127 for c in v):refuse('text must be nonblank control-free1..100')
 return v
def names(v,label,cap):
 if type(v)is not list or not 1<=len(v)<=cap:refuse(label+' must have1..'+str(cap)+' entries')
 for x in v:text(x)
 if len(v)!=len(set(v)):refuse('duplicate '+label)
 return v
def rational(v):
 if type(v)is not str:refuse('rational string required')
 if len(v)>16:refuse('rational raw length exceeds16')
 if not re.fullmatch(r'-?[0-9]+(?:/[1-9][0-9]*)?',v):refuse('rational string required')
 parts=v.lstrip('-').split('/')
 if any(len(p)>7 or int(p)>1000000 for p in parts):refuse('rational components exceed1000000')
 return Fraction(v)
def bounded_rows(v,label):
 if type(v)is not list or not 1<=len(v)<=100:refuse(label+' must have1..100 entries')
 return v
def boundary():return {'release_authorized':False,'physical_validity_verified':False,'scope':'caller_supplied_bookkeeping_only'}
def prepare(d):
 shape(d,('specimen_count','profiles','measurements','acceptance_criteria'),'packet schema')
 n=d['specimen_count']
 if type(n)is not int or not 1<=n<=10000:refuse('specimen_count must be integer1..10000')
 names(d['measurements'],'measurements',100);names(d['acceptance_criteria'],'acceptance_criteria',100)
 profiles=bounded_rows(d['profiles'],'profiles');seen=set();hours=Fraction(0);cycles=0;retained=[]
 for p in profiles:
  shape(p,('id','duration_hours','cycles'),'profile schema');text(p['id'])
  if p['id'] in seen:refuse('duplicate profile id')
  seen.add(p['id']);duration=rational(p['duration_hours'])
  if duration<=0:refuse('duration_hours must be positive')
  c=p['cycles']
  if type(c)is not int or not 0<=c<=1000000:refuse('cycles must be integer0..1000000')
  hours+=duration;cycles+=c;retained.append({'id':p['id'],'duration_hours':str(duration),'cycles':c})
 return {**boundary(),'specimen_count':n,'profile_count':len(profiles),'profiles':retained,'measurements':list(d['measurements']),'acceptance_criteria':list(d['acceptance_criteria']),
  'planned_hours_per_specimen':str(hours),'planned_specimen_hours':str(hours*n),'planned_cycles_per_specimen':cycles,'planned_specimen_cycles':cycles*n,
  'test_executed':False,'lifetime_estimated':False,'reliability_certified':False}
