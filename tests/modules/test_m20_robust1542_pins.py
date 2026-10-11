import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/robust_design1542.py'
s=importlib.util.spec_from_file_location('pins1542',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet():return {'control_factors':['c'],'noise_factors':['n'],'objective':'maximize','scenarios':[{'id':'s','control':{'c':'2/4'},'noise':{'n':'-1/2'},'response':'3/2'}]}
class Pins(unittest.TestCase):
 def refuse(self,d,code):
  try:m.prepare(d)
  except Exception as e:self.assertIsInstance(e,m.UnitError);self.assertEqual(str(e),'ROBUST1542: '+code)
  else:self.fail('Expected '+code)
 def test_nonconstant_exact_population_variance(self):
  d=packet();d['scenarios']=[dict(d['scenarios'][0],id=str(i),response=v) for i,v in enumerate(['1','2','4'])]
  r=m.prepare(d);self.assertEqual(r['population_variance'],'14/9');self.assertEqual(r['response_mean'],'7/3')
 def test_empty_and_nonlist_and_packet_types(self):
  for key,cap in [('control_factors',8),('noise_factors',8),('scenarios',100)]:
   for v in [[],None,(),{},'a']:
    d=packet();d[key]=v;self.refuse(d,key+' must have1..'+str(cap)+' entries')
  for d in [None,[],1]:self.refuse(d,'packet schema')
 def test_overlap_objective_and_duplicates(self):
  d=packet();d['noise_factors']=['c'];self.refuse(d,'control and noise names overlap')
  for v in ['other',[],None]:self.refuse(dict(packet(),objective=v),'objective must be maximize or minimize')
  for key in ['control_factors','noise_factors']:
   d=packet();d[key]*=2;self.refuse(d,'duplicate '+key)
  d=packet();d['scenarios']*=2;self.refuse(d,'duplicate scenario id')
 def test_scenario_and_mapping_schema(self):
  for row in [None,[],dict(packet()['scenarios'][0],extra=1),{'id':'s'}]:
   d=packet();d['scenarios']=[row];self.refuse(d,'scenario schema')
  for key in ['control','noise']:
   for value in [None,[],{},dict(packet()['scenarios'][0][key],extra='1')]:
    d=packet();d['scenarios'][0][key]=value;self.refuse(d,key+' schema')
 def test_retained_scenario_exact(self):
  self.assertEqual(m.prepare(packet())['scenarios'],[{'id':'s','control':{'c':'1/2'},'noise':{'n':'-1/2'},'response':'3/2'}])
 def test_factor_blank_nonstr_controls_text_edges(self):
  for value in ['',None,1,'a'+chr(31),'x'*101]:
   d=packet();d['control_factors']=[value];self.refuse(d,'text must be nonblank control-free1..100')
  for value in ['a b','x'*100]:
   d=packet();d['control_factors']=[value];d['scenarios'][0]['control']={value:'0'};self.assertEqual(m.prepare(d)['scenarios'][0]['control'],{value:'0'})
if __name__=='__main__':unittest.main()
