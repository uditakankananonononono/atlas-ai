import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/response_surface_methodology1541.py'
s=importlib.util.spec_from_file_location('unit1541',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet():return {'factors':['x'],'points':[{'x':'0'},{'x':'1'},{'x':'2'}],'responses':['1','2','5']}
class Tests(unittest.TestCase):
 def refuse(self,d,code):
  with self.assertRaises(m.UnitError) as cm:m.prepare(d)
  self.assertEqual(str(cm.exception),'RESPSU1541: '+code)
 def test_real_exact_output(self):
  r=m.prepare(packet());self.assertFalse(r['release_authorized']);self.assertFalse(r['physical_validity_verified'])
  self.assertEqual(r['term_names'],['1','x','x^2']);self.assertEqual(r['design_rank'],3);self.assertEqual(r['residual_degrees_of_freedom'],0);self.assertEqual(r['response_sum'],'8')
  d=packet();d['points']=[{'x':'1'}]*3;self.assertEqual(m.prepare(d)['design_rank'],1)
 def test_n_nplus1(self):
  d=packet();d['points']=[{'x':'0'}]*100;d['responses']=['1']*100;self.assertEqual(m.prepare(d)['point_count'],100)
  d['points'].append({'x':'0'});d['responses'].append('1');self.refuse(d,'points must have1..100 entries')
  for count in [1,8]:
   d={'factors':['x'+str(i) for i in range(count)],'points':[{ 'x'+str(i):'0' for i in range(count)}],'responses':['0']};self.assertEqual(m.prepare(d)['factor_count'],count)
  d['factors'].append('extra');self.refuse(d,'factors must have1..8 entries')
 def test_text100_101_and_types(self):
  for value in ['x'*100,'x'*101,'','x'+chr(31),'x'+chr(127),None]:
   d=packet();d['factors'][0]=value;d['points']=[{value:'0'}];d['responses']=['0']
   if value=='x'*100:m.prepare(d)
   else:
    with self.assertRaises(m.UnitError):m.prepare(d)
 def test_rational_bounds_and_strict_schema(self):
  for value in ['1000000','1000001',True,'1.2','1/0','00000001']:
   d=packet();d['responses'][0]=value
   if value=='1000000':m.prepare(d)
   else:
    with self.assertRaises(m.UnitError):m.prepare(d)
  self.refuse(dict(packet(),extra=1),'packet schema')
 def test_no_input_mutation(self):
  import copy
  d=packet();before=copy.deepcopy(d);m.prepare(d);self.assertEqual(d,before)
 def test_flags_and_column_rank(self):
  r=m.prepare(packet());self.assertTrue(r['full_column_rank']);self.assertFalse(r['fit_executed']);self.assertFalse(r['prediction_validated'])
  d=packet();d['points']=[{'x':'0'}];d['responses']=['0'];self.assertFalse(m.prepare(d)['full_column_rank'])
if __name__=='__main__':unittest.main()
