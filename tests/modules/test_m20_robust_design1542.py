import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/robust_design1542.py'
s=importlib.util.spec_from_file_location('unit1542',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet():return {'control_factors':['c'],'noise_factors':['n'],'objective':'maximize','scenarios':[{'id':'a','control':{'c':'1'},'noise':{'n':'0'},'response':'1/3'},{'id':'b','control':{'c':'1'},'noise':{'n':'1'},'response':'2/3'}]}
class Tests(unittest.TestCase):
 def refuse(self,d,code):
  with self.assertRaises(m.UnitError) as cm:m.prepare(d)
  self.assertEqual(str(cm.exception),'ROBUST1542: '+code)
 def test_real_exact_output(self):
  r=m.prepare(packet());self.assertFalse(r['release_authorized']);self.assertFalse(r['physical_validity_verified'])
  self.assertEqual(r['response_mean'],'1/2');self.assertEqual(r['response_range'],'1/3');self.assertEqual(r['worst_case_response'],'1/3')
  self.assertEqual(m.prepare(dict(packet(),objective='minimize'))['worst_case_response'],'2/3')
 def test_n_nplus1(self):
  d=packet();d['scenarios']=[dict(d['scenarios'][0],id='s'+str(i)) for i in range(100)];self.assertEqual(m.prepare(d)['scenario_count'],100)
  d['scenarios'].append(dict(d['scenarios'][0],id='extra'));self.refuse(d,'scenarios must have1..100 entries')
 def test_text100_101_and_types(self):
  for value in ['x'*100,'x'*101,'','x'+chr(31),'x'+chr(127),None]:
   d=packet();d['scenarios'][0]['id']=value
   if value=='x'*100:m.prepare(d)
   else:
    with self.assertRaises(m.UnitError):m.prepare(d)
 def test_rational_bounds_and_strict_schema(self):
  for value in ['1000000','1000001',True,'1.2','1/0','00000001']:
   d=packet();d['scenarios'][0]['response']=value
   if value=='1000000':m.prepare(d)
   else:
    with self.assertRaises(m.UnitError):m.prepare(d)
  self.refuse(dict(packet(),extra=1),'packet schema')
 def test_no_input_mutation(self):
  import copy
  d=packet();before=copy.deepcopy(d);m.prepare(d);self.assertEqual(d,before)
 def test_factor8_9_flags_and_empty(self):
  for key,label in [('control_factors','control'),('noise_factors','noise')]:
   d=packet();d[key]=['z'+str(i) for i in range(8)]
   for row in d['scenarios']:row[label]={x:'0' for x in d[key]}
   self.assertFalse(m.prepare(d)['robustness_guaranteed'])
   d[key].append('extra')
   for row in d['scenarios']:row[label]['extra']='0'
   with self.assertRaises(m.UnitError):m.prepare(d)
  d=packet();d['control_factors']=[]
  with self.assertRaises(m.UnitError):m.prepare(d)
  d=packet();d['scenarios']=[d['scenarios'][0]];self.assertEqual(m.prepare(d)['scenario_count'],1)
  d=packet();d['scenarios']=[]
  with self.assertRaises(m.UnitError):m.prepare(d)
if __name__=='__main__':unittest.main()
