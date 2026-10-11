import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/reliability_testing1543.py'
s=importlib.util.spec_from_file_location('unit1543',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet():return {'specimen_count':2,'profiles':[{'id':'hot','duration_hours':'3/2','cycles':4}],'measurements':['voltage'],'acceptance_criteria':['no visible damage']}
class Tests(unittest.TestCase):
 def refuse(self,d,code):
  with self.assertRaises(m.UnitError) as cm:m.prepare(d)
  self.assertEqual(str(cm.exception),'RELTES1543: '+code)
 def test_real_exact_output(self):
  r=m.prepare(packet());self.assertFalse(r['release_authorized']);self.assertFalse(r['physical_validity_verified'])
  self.assertEqual(r['planned_hours_per_specimen'],'3/2');self.assertEqual(r['planned_specimen_hours'],'3');self.assertEqual(r['planned_cycles_per_specimen'],4)
  self.assertFalse(r['test_executed'])
 def test_n_nplus1(self):
  self.assertEqual(m.prepare(dict(packet(),specimen_count=10000))['specimen_count'],10000)
  self.refuse(dict(packet(),specimen_count=10001),'specimen_count must be integer1..10000')
  d=packet();d['profiles']=[dict(d['profiles'][0],id='p'+str(i)) for i in range(100)];self.assertEqual(m.prepare(d)['profile_count'],100)
  d['profiles'].append(dict(d['profiles'][0],id='extra'));self.refuse(d,'profiles must have1..100 entries')
  d=packet();d['profiles'][0]['cycles']=1000000;self.assertEqual(m.prepare(d)['planned_cycles_per_specimen'],1000000)
  d['profiles'][0]['cycles']=1000001;self.refuse(d,'cycles must be integer0..1000000')
 def test_text100_101_and_types(self):
  for value in ['x'*100,'x'*101,'','x'+chr(31),'x'+chr(127),None]:
   d=packet();d['measurements'][0]=value
   if value=='x'*100:m.prepare(d)
   else:
    with self.assertRaises(m.UnitError):m.prepare(d)
 def test_rational_bounds_and_strict_schema(self):
  for value in ['1000000','1000001',True,'1.2','1/0','00000001']:
   d=packet();d['profiles'][0]['duration_hours']=value
   if value=='1000000':m.prepare(d)
   else:
    with self.assertRaises(m.UnitError):m.prepare(d)
  self.refuse(dict(packet(),extra=1),'packet schema')
 def test_no_input_mutation(self):
  import copy
  d=packet();before=copy.deepcopy(d);m.prepare(d);self.assertEqual(d,before)
 def test_plan_boundaries_and_flags(self):
  d=packet();d['specimen_count']=1;d['profiles'][0]['cycles']=0
  r=m.prepare(d);self.assertEqual(r['planned_cycles_per_specimen'],0);self.assertFalse(r['lifetime_estimated']);self.assertFalse(r['reliability_certified'])
  d['profiles'][0]['duration_hours']='0'
  with self.assertRaises(m.UnitError):m.prepare(d)
  for key in ['measurements','acceptance_criteria']:
   d=packet();d[key]=['x'+str(i) for i in range(100)];self.assertEqual(len(m.prepare(d)[key]),100)
   d[key].append('extra')
   with self.assertRaises(m.UnitError):m.prepare(d)
   d[key]=[]
   with self.assertRaises(m.UnitError):m.prepare(d)
  d=packet();d['profiles']=[]
  with self.assertRaises(m.UnitError):m.prepare(d)
if __name__=='__main__':unittest.main()
