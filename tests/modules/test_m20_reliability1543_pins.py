import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/reliability_testing1543.py'
s=importlib.util.spec_from_file_location('pins1543',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet():return {'specimen_count':1,'profiles':[{'id':'p','duration_hours':'1','cycles':0}],'measurements':['m'],'acceptance_criteria':['c']}
class Pins(unittest.TestCase):
 def refuse(self,d,code):
  try:m.prepare(d)
  except Exception as e:self.assertIsInstance(e,m.UnitError);self.assertEqual(str(e),'RELTES1543: '+code)
  else:self.fail('Expected '+code)
 def test_duration_edges_exact_profiles(self):
  for duration in ['1','1000000','3/2']:
   d=packet();d['profiles'][0]['duration_hours']=duration;r=m.prepare(d)
   self.assertEqual(r['profiles'],[{'id':'p','duration_hours':str(m.Fraction(duration)),'cycles':0}]);self.assertEqual(r['planned_hours_per_specimen'],str(m.Fraction(duration)))
  d=packet();d['profiles'][0]['duration_hours']='0';self.refuse(d,'duration_hours must be positive')
 def test_specimen_edges_and_bool(self):
  for n in [1,10000]:self.assertEqual(m.prepare(dict(packet(),specimen_count=n))['specimen_count'],n)
  for n in [0,10001,True]:self.refuse(dict(packet(),specimen_count=n),'specimen_count must be integer1..10000')
 def test_cycle_edges_and_bool(self):
  for n in [0,1000000]:
   d=packet();d['profiles'][0]['cycles']=n;self.assertEqual(m.prepare(d)['planned_cycles_per_specimen'],n)
  for n in [-1,1000001,True]:
   d=packet();d['profiles'][0]['cycles']=n;self.refuse(d,'cycles must be integer0..1000000')
 def test_duplicates(self):
  d=packet();d['profiles']*=2;self.refuse(d,'duplicate profile id')
  for key in ['measurements','acceptance_criteria']:
   d=packet();d[key]*=2;self.refuse(d,'duplicate '+key)
 def test_profile_schema_missing_extra_nondict(self):
  for profile in [{'id':'p','duration_hours':'1'},dict(packet()['profiles'][0],extra=1),None,[],1]:
   d=packet();d['profiles']=[profile];self.refuse(d,'profile schema')
 def test_empty_and_nonlist_inputs(self):
  for key in ['profiles','measurements','acceptance_criteria']:
   for value in [[],None,(),{'p':1},'p']:
    d=packet();d[key]=value;self.refuse(d,key+' must have1..100 entries')
  for value in [None,[],1]:self.refuse(value,'packet schema')
 def test_profile_id_controls_and_rational_parse(self):
  for value in ['',None,'a'+chr(31)]:
   d=packet();d['profiles'][0]['id']=value;self.refuse(d,'text must be nonblank control-free1..100')
  for value in ['1.5','1/0',True]:
   d=packet();d['profiles'][0]['duration_hours']=value;self.refuse(d,'rational string required')
if __name__=='__main__':unittest.main()
