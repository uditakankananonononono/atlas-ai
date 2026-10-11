import copy
import importlib.util
from pathlib import Path
import unittest
CORE=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/bargaining_power91.py'
s=importlib.util.spec_from_file_location('bargain91',CORE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def party(id='a',**factors):
 d={'alternatives':10,'resources':5,'time_pressure':False,'dependency':False};d.update(factors)
 return {'id':id,'position':'Caller position','factors':d}
def packet(parties=None):
 return {'model':{'alternatives':{'weight':'1/2','scale':10,'direction':'benefit'},'resources':{'weight':'1/2','scale':10,'direction':'benefit'},'time_pressure':{'weight':'1/4','scale':1,'direction':'penalty'},'dependency':{'weight':'1/4','scale':1,'direction':'penalty'}},'parties':parties or [party()]}
class BargainTests(unittest.TestCase):
 def test_exact_components_ranks_and_ties(self):
  d=packet([party('b'),party('a'),party('c',alternatives=0,resources=0,time_pressure=True,dependency=True)])
  r=m.evaluate_bargaining_power(d)
  self.assertEqual([x['id'] for x in r['ranking']],['a','b','c'])
  self.assertEqual([x['rank'] for x in r['ranking']],[1,1,3])
  self.assertEqual(r['ranking'][0]['score'],'3/4');self.assertEqual(r['ranking'][2]['score'],'-1/2')
  self.assertEqual(r['ranking'][0]['components'],{'alternatives':'1/2','resources':'1/4','time_pressure':'0','dependency':'0'})
  self.assertEqual(r['tie_groups'],[['a','b']]);self.assertFalse(r['real_world_power_verified'])
  self.assertEqual(r['scope'],'caller_declared_factor_model_only')
 def test_missing_factors_exact_refusal(self):
  for key in packet()['model']:
   d=packet();del d['parties'][0]['factors'][key]
   with self.assertRaises(m.Bargain91Error) as cm:m.evaluate_bargaining_power(d)
   self.assertEqual(str(cm.exception),'BARGAIN91: factors must contain exactly alternatives, resources, time_pressure, dependency')
 def test_strict_type_bounds_and_model(self):
  for key,value in [('alternatives',True),('resources',-1),('alternatives',11),('time_pressure',1),('dependency','false')]:
   d=packet();d['parties'][0]['factors'][key]=value
   with self.assertRaises(m.Bargain91Error):m.evaluate_bargaining_power(d)
  for weight in ['1/0','-1','nan','1.5',True,'1000001']:
   d=packet();d['model']['alternatives']['weight']=weight
   with self.assertRaises(m.Bargain91Error):m.evaluate_bargaining_power(d)
  d=packet();d['model']['dependency']['direction']='benefit'
  with self.assertRaises(m.Bargain91Error):m.evaluate_bargaining_power(d)
 def test_exact_tie_without_float_and_caller_weight_delta(self):
  d=packet([party('a',alternatives=3,resources=1),party('b',alternatives=1,resources=3)])
  r=m.evaluate_bargaining_power(d);self.assertEqual(r['tie_groups'],[['a','b']])
  d['model']['alternatives']['weight']='2/3';r=m.evaluate_bargaining_power(d)
  self.assertEqual(r['ranking'][0]['id'],'a');self.assertEqual(r['ranking'][0]['score'],'1/4')
 def test_determinism_and_no_alias(self):
  d=packet([party('b'),party('a')]);old=copy.deepcopy(d);r=m.evaluate_bargaining_power(d)
  d2=copy.deepcopy(d);d2['parties'].reverse();self.assertEqual(r,m.evaluate_bargaining_power(d2))
  r['ranking'][0]['position']='changed';r['model']['alternatives']['weight']='0';self.assertEqual(d,old)
 def test_bad_schema_duplicates_limits(self):
  for d in [[],{},packet([party(),party()])]:
   with self.assertRaises(m.Bargain91Error):m.evaluate_bargaining_power(d)
  d=packet();d['parties'][0]['id']='bad\n'
  with self.assertRaises(m.Bargain91Error):m.evaluate_bargaining_power(d)
  d=packet();d['parties'][0]['position']='x'*2001
  with self.assertRaises(m.Bargain91Error):m.evaluate_bargaining_power(d)
  d=packet([party(str(i)) for i in range(64)]);self.assertEqual(len(m.evaluate_bargaining_power(d)['ranking']),64)
  d['parties'].append(party('65'))
  with self.assertRaises(m.Bargain91Error):m.evaluate_bargaining_power(d)

class BatnaAdapterTests(unittest.TestCase):
 def record(self):
  return {'version':'1','options_count':3,'best_names':['x','y'],'best_utility':'3/2','is_tie':True,'ranking':[{'name':'x','utility':'3/2','rank':1},{'name':'y','utility':'3/2','rank':1},{'name':'z','utility':'1','rank':3}],'margin_to_next':'1/2','limits':['caller-declared']*5}
 def test_valid_tie_margin_no_power_conversion(self):
  d=packet();d['parties'][0]['batna_record']=self.record();r=m.evaluate_bargaining_power(d)
  self.assertEqual(r['ranking'][0]['score'],'3/4');self.assertEqual(r['ranking'][0]['batna_record'],self.record())
  r['ranking'][0]['batna_record']['limits'].append('changed');self.assertEqual(d['parties'][0]['batna_record'],self.record())
 def test_bad_consistency_rejected(self):
  for key,value in [('version',1),('options_count',True),('best_names',['y','x']),('best_utility','2'),('is_tie',False),('margin_to_next','0'),('limits',[])]:
   d=self.record();d[key]=value
   with self.subTest(key=key),self.assertRaises(m.Bargain91Error):m.validate_batna_record(d)
  d=self.record();d['ranking'][2]['rank']=2
  with self.assertRaises(m.Bargain91Error):m.validate_batna_record(d)
 def test_single_and_all_tied_margin_none(self):
  d=self.record();d['ranking']=d['ranking'][:2];d['options_count']=2;d['margin_to_next']=None;m.validate_batna_record(d)
  d['ranking']=d['ranking'][:1];d['options_count']=1;d['best_names']=['x'];d['is_tie']=False;m.validate_batna_record(d)
if __name__=='__main__':unittest.main()
