"""Exact declared stock snapshot checks; PREP only, no urgency manufacture."""
from datetime import datetime, timedelta, timezone
import re
import unicodedata
from fractions import Fraction

class Scarcity99Error(ValueError):pass

def _refuse(code):raise Scarcity99Error('SCARCI99: '+code)
def prepare_scarcity(packet):
 keys={'claim','source_ref','total','allocated','claimed_remaining','observed_at','as_of','max_age_seconds'}
 if type(packet)is not dict or set(packet)!=keys:_refuse('packet schema')
 for key in ('claim','source_ref'):
  value=packet[key]
  if type(value)is not str or len(value)>2000 or not value.strip() or any(unicodedata.category(c) in ('Cc','Cf','Zl','Zp') for c in value):_refuse('invalid '+key)
 for key in ('total','allocated','claimed_remaining'):
  if type(packet[key])is not int or not 0<=packet[key]<=1000000:_refuse('counts must be integer0..1000000')
 if packet['allocated']>packet['total']:_refuse('allocated exceeds total')
 cap=packet['max_age_seconds']
 if type(cap)is not int or not 0<=cap<=86400:_refuse('max_age_seconds must be integer0..86400')
 times=[]
 for key in ('observed_at','as_of'):
  value=packet[key]
  if not isinstance(value,str):_refuse('invalid '+key)
  if len(value)>40:_refuse('invalid '+key)
  match=re.fullmatch(r'([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(\.[0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})',value)
  if match is None:_refuse('invalid '+key)
  year,month,day,hour,minute,second=(int(x) for x in match.groups()[:6])
  fraction,zone=match.groups()[6:]
  micro=int((fraction[1:] if fraction else '').ljust(6,'0'))
  if zone=='Z':offset=timedelta(0)
  else:
   oh=int(zone[1:3]);om=int(zone[4:6])
   if oh>23 or om>59:_refuse('invalid '+key)
   offset=timedelta(hours=oh,minutes=om)*(1 if zone[0]=='+' else -1)
  try:stamp=datetime(year,month,day,hour,minute,second,micro,tzinfo=timezone(offset))
  except (ValueError,OverflowError):_refuse('invalid '+key)
  times.append(stamp)
 # Integer microseconds preserve exact caller chronology, no live clock inference.
 delta=times[1]-times[0]
 micros=(delta.days*86400+delta.seconds)*1000000+delta.microseconds
 if micros<0:_refuse('observation is in future')
 age=Fraction(micros,1000000);remaining=packet['total']-packet['allocated']
 return {**packet,'remaining':remaining,'age_seconds':str(age),'arithmetic_consistent':packet['claimed_remaining']==remaining,
  'within_caller_age_limit':age<=cap,'deployment_authorized':False,'real_world_verified':False,
  'scope':'caller_declared_snapshot_checks_only','ethical_boundary':'Disclose source and snapshot age. No fabricated stock, manufactured urgency, targeting or efficacy claim.'}
