"""Tests-only exact edge pins for frozen BARGAIN91; no BATNA92 interoperability."""
import importlib.util
from pathlib import Path
import unittest
CORE=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/bargaining_power91.py'
s=importlib.util.spec_from_file_location('bargain91_edges',CORE)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def packet():
 return {'model':{f:{'weight':'1','scale':1,'direction':'benefit' if f in ('alternatives','resources') else 'penalty'} for f in m.FACTORS},'parties':[{'id':'a','position':'p','factors':{'alternatives':1,'resources':1,'time_pressure':False,'dependency':False}}]}
def record(n=1,utility='1'):
 names=['n'+str(i) for i in range(n)]
 return {'version':'1','options_count':n,'best_names':names,'best_utility':utility,'is_tie':n>1,'ranking':[{'name':name,'utility':utility,'rank':1} for name in names],'margin_to_next':None,'limits':['declared']*5}

class EdgeTests(unittest.TestCase):
 def refusal(self,fn,arg,message):
  try:fn(arg)
  except Exception as exc:
   self.assertIsInstance(exc,m.Bargain91Error)
   self.assertEqual(str(exc),'BARGAIN91: '+message)
  else:self.fail('Expected exact refusal: '+message)
 def accepted(self,fn,arg):
  try:return fn(arg)
  except Exception as exc:self.fail('Expected accepted input, got '+type(exc).__name__+': '+str(exc))
 def test_exact_limits_and_copy(self):
  expected={'parties':64,'text':2000,'id':100,'scale':1000000,'rational_component':1000000}
  self.assertEqual(m.LIMITS,expected)
  result=self.accepted(m.evaluate_bargaining_power,packet());self.assertEqual(result['limits'],expected)
  result['limits']['text']=0;self.assertEqual(m.LIMITS,expected)
 def test_party_text_exact_length_controls_and_types(self):
  for key,limit,label in [('id',100,'party id'),('position',2000,'position')]:
   for length in [limit-1,limit]:
    d=packet();d['parties'][0][key]='x'*length
    self.assertEqual(self.accepted(m.evaluate_bargaining_power,d)['ranking'][0][key],'x'*length)
   for value in ['x'*(limit+1),'', '   ',None,12,[], 'x'+chr(31), 'x'+chr(127)]:
    with self.subTest(key=key,value_type=type(value).__name__):
     d=packet();d['parties'][0][key]=value
     self.refusal(m.evaluate_bargaining_power,d,label+' must be nonempty bounded text without controls')
   for code in [32,126,128]:
    d=packet();d['parties'][0][key]='x'+chr(code)
    self.assertEqual(self.accepted(m.evaluate_bargaining_power,d)['ranking'][0][key],'x'+chr(code))
 def test_weight_component_numeric_and_digit_edges(self):
  for weight in ['1000000','1000000/1000000','1/1000000','0000001']:
   d=packet();d['model']['alternatives']['weight']=weight
   self.assertEqual(self.accepted(m.evaluate_bargaining_power,d)['ranking'][0]['components']['alternatives'],str(m.Fraction(weight)))
  for weight in ['1000001','1/1000001','00000001','000000001','10000000']:
   d=packet();d['model']['alternatives']['weight']=weight
   self.refusal(m.evaluate_bargaining_power,d,'weight numerator and denominator exceed limit')
 def test_scale_integer_exact_edges(self):
  for scale in [1,999999,1000000]:
   d=packet();d['model']['alternatives']['scale']=scale
   self.assertEqual(self.accepted(m.evaluate_bargaining_power,d)['ranking'][0]['components']['alternatives'],str(m.Fraction(1,scale)))
  for scale in [0,-1,1000001,True,False,1.0,'1',None,[]]:
   d=packet();d['model']['alternatives']['scale']=scale
   self.refusal(m.evaluate_bargaining_power,d,'scale must be integer within 1..1000000')
 def test_flag_scale_exact_refusal_concatenation(self):
  for factor in ['time_pressure','dependency']:
   d=packet();d['model'][factor]['scale']=2
   self.refusal(m.evaluate_bargaining_power,d,factor+' flag scale must be 1')
 def test_empty_parties_exact_refusal(self):
  d=packet();d['parties']=[]
  self.refusal(m.evaluate_bargaining_power,d,'parties must be a list with 1..64 entries')
 def test_party_key_set_and_type_refusal(self):
  d=packet();d['parties'][0]['extra']=1
  self.refusal(m.evaluate_bargaining_power,d,'party schema invalid')
  d=packet();d['parties'][0]=[]
  self.refusal(m.evaluate_bargaining_power,d,'party schema invalid')
 def test_batna_utility_length_and_grammar_edges(self):
  for length in [127,128]:
   utility='1'*length;d=record(utility=utility)
   self.assertEqual(self.accepted(m.validate_batna_record,d),d)
  for utility in ['1'*129,'not-rational','',None,1,[], '1/0']:
   d=record(utility=utility)
   self.refusal(m.validate_batna_record,d,'BATNA utility must be bounded rational string')
 def test_batna_options_count_edges(self):
  for n in [1,999,1000]:
   d=record(n);self.assertEqual(self.accepted(m.validate_batna_record,d),d)
  for n in [0,-1,1001,True,False,1.0,'1',None,[]]:
   d=record();d['options_count']=n
   self.refusal(m.validate_batna_record,d,'BATNA options_count must be integer within 1..1000')
 def test_batna_ranking_type_and_count(self):
  for ranking in [[],record(2)['ranking'],tuple(record()['ranking']),None,{}]:
   d=record();d['ranking']=ranking
   self.refusal(m.validate_batna_record,d,'BATNA ranking count mismatch')
 def test_batna_name_and_limit_exact_edges(self):
  for target,label in [('name','BATNA name'),('limit','BATNA limit')]:
   def put(d,v):
    if target=='name':d['ranking'][0]['name']=v;d['best_names']=[v]
    else:d['limits'][0]=v
   for length in [1999,2000]:
    d=record();put(d,'x'*length);self.assertEqual(self.accepted(m.validate_batna_record,d),d)
   for value in ['x'*2001,'', ' ',None,12,[], 'x'+chr(31),'x'+chr(127)]:
    d=record();put(d,value)
    self.refusal(m.validate_batna_record,d,label+' must be nonempty bounded text without controls')
   for code in [32,126,128]:
    d=record();put(d,'x'+chr(code));self.assertEqual(self.accepted(m.validate_batna_record,d),d)
if __name__=='__main__':unittest.main()
