"""Exact edge pins for the frozen 1541 design bookkeeping module."""
import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/response_surface_methodology1541.py'
s=importlib.util.spec_from_file_location('pins1541',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet(factors=None):
 f=['a','b'] if factors is None else factors
 return {'factors':f,'points':[{x:str(i+2) for i,x in enumerate(f)}],'responses':['7/3']}
class Pins(unittest.TestCase):
 def refuse(self,d,code):
  try:m.prepare(d)
  except Exception as e:
   self.assertIsInstance(e,m.UnitError);self.assertEqual(str(e),'RESPSU1541: '+code)
  else:self.fail('Expected exact refusal '+code)
 def test_two_factor_full_matrix(self):
  r=m.prepare(packet())
  self.assertEqual(r['term_names'],['1','a','b','a^2','b^2','a*b'])
  self.assertEqual(r['design_matrix'],[['1','2','3','4','9','6']])
  self.assertEqual(r['design_rank'],1)
 def test_three_factor_full_matrix(self):
  r=m.prepare(packet(['a','b','c']))
  self.assertEqual(r['term_names'],['1','a','b','c','a^2','b^2','c^2','a*b','a*c','b*c'])
  self.assertEqual(r['design_matrix'],[['1','2','3','4','4','9','16','6','8','12']])
 def test_nonzero_response_mean_sum(self):
  d=packet();d['points']*=3;d['responses']=['7/3','-2/3','5/2']
  r=m.prepare(d);self.assertEqual(r['response_sum'],'25/6');self.assertEqual(r['response_mean'],'25/18')
 def test_empty_factors_points_exact_refusal(self):
  self.refuse(packet([]),'factors must have1..8 entries')
  d=packet();d['points']=[];self.refuse(d,'points must have1..100 entries')
 def test_response_count_and_type_exact_refusal(self):
  for responses in [[],['1','2'],None,('1',),'1',{}]:
   d=packet();d['responses']=responses;self.refuse(d,'response count mismatch')
 def test_duplicate_factor_name(self):
  self.refuse(packet(['a','a']),'duplicate factors')
 def test_controls_and_text100_101(self):
  for name in ['a'+chr(31),'a'+chr(127),'x'*101]:
   self.refuse(packet([name]),'text must be nonblank control-free1..100')
  for name in ['a'+chr(32),'x'*100]:
   self.assertEqual(m.prepare(packet([name]))['term_names'][1],name)
 def test_structure_failures_are_exact_module_refusals(self):
  for d in [None,[],1,'packet']:self.refuse(d,'packet schema')
  for f in [None,(),{},'a',1]:
   d=packet();d['factors']=f;self.refuse(d,'factors must have1..8 entries')
  for p in [None,(),{},'point',1]:
   d=packet();d['points']=p;self.refuse(d,'points must have1..100 entries')
  for p in [None,[],1,'point']:
   d=packet();d['points']=[p];self.refuse(d,'point schema')
if __name__=='__main__':unittest.main()
