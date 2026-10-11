"""Independent exact supplied-rule boundary tests; no release/integration claim."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest

CORE=Path(os.environ.get('FLAG697_CORE',str(Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/flag_evaluator697.py')))
spec=importlib.util.spec_from_file_location('boundary_flag697',CORE)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
evaluate=module.evaluate_flags697
MAX=2**53-1

def cmp(value=1):return {'op':'eq','field':'x','value':value}
def data(condition=None):
 return {'context_schema':{'x':'int'},'evaluation_context':{'x':1},'flags':[{'name':'f','source_id':'s','default':False,'rules':[{'id':'r','source_id':'s','priority':0,'value':True,'condition':cmp() if condition is None else condition}]}]}
def trace(d):return evaluate(d)['flags'][0]['trace'][0]['matched']
def bucket(seed,key,percent):
 d=data({'op':'bucket','field':'x','seed':seed,'percent':percent});d['context_schema']['x']='string';d['evaluation_context']['x']=key;return d

class BoundaryPins(unittest.TestCase):
 def refuse(self,d,message):
  with self.assertRaises(ValueError) as e:evaluate(d)
  self.assertEqual(str(e.exception),message)

 def test_percent_bucket_exact_equality_is_excluded(self):
  # Assumption: strict < score boundary, not <=, with integral percent.
  seed,key='s','key-1'
  score=int.from_bytes(hashlib.sha256(json.dumps([seed,key],ensure_ascii=False,separators=(',',':')).encode('utf-8')).digest()[:8],'big')%10000
  self.assertEqual(score,7100)
  self.assertIs(trace(bucket(seed,key,71)),False)
  self.assertIs(trace(bucket(seed,key,72)),True)

 def test_unicode_seed_hash_is_unescaped_utf8(self):
  # Assumption: ensure_ascii=False applies to seed as well as user key.
  seed,key='é','key-88'
  unescaped=int.from_bytes(hashlib.sha256(json.dumps([seed,key],ensure_ascii=False,separators=(',',':')).encode('utf-8')).digest()[:8],'big')%10000
  escaped=int.from_bytes(hashlib.sha256(json.dumps([seed,key],ensure_ascii=True,separators=(',',':')).encode('utf-8')).digest()[:8],'big')%10000
  self.assertEqual((unescaped,escaped),(1800,8066))
  self.assertIs(trace(bucket(seed,key,19)),True)
  self.assertIs(trace(bucket(seed,key,18)),False)

 def test_name_exact_type_and_blank_refusal(self):
  for value in ['', '   ', None, 7, True, [], {}]:
   d=data();d['flags'][0]['name']=value
   self.refuse(d,'FLAG697_ID: flag.name')
  for value in ['a','n'*64]:
   d=data();d['flags'][0]['name']=value;evaluate(d)
  d=data();d['flags'][0]['name']='n'*65;self.refuse(d,'FLAG697_ID: flag.name')

 def test_identifier_surrogate_both_endpoints(self):
  for value in ['\ud800','\udfff']:
   d=data();d['flags'][0]['name']=value;self.refuse(d,'FLAG697_ID: flag.name')
  for value in ['\ud7ff','\ue000']:
   d=data();d['flags'][0]['name']=value;evaluate(d)

 def test_number_magnitude_exact_both_signs(self):
  for v in [-MAX,MAX]:
   d=data(cmp(v));d['context_schema']['x']='number';d['evaluation_context']['x']=v;self.assertIs(trace(d),True)
  for v in [-MAX-1,MAX+1]:
   d=data();d['context_schema']['x']='number';d['evaluation_context']['x']=v;self.refuse(d,'FLAG697_TYPE: context.x')
   d=data(cmp(v));d['context_schema']['x']='number';self.refuse(d,'FLAG697_TYPE: rule.r.value')

 def test_int_magnitude_negative_arm(self):
  d=data(cmp(-MAX));d['evaluation_context']['x']=-MAX;self.assertIs(trace(d),True)
  d=data();d['evaluation_context']['x']=-MAX-1;self.refuse(d,'FLAG697_TYPE: context.x')

 def test_string_empty_and_max_exact(self):
  for v in ['','x'*256]:
   d=data(cmp(v));d['context_schema']['x']='string';d['evaluation_context']['x']=v;self.assertIs(trace(d),True)
  d=data(cmp('x'*257));d['context_schema']['x']='string';d['evaluation_context']['x']='x';self.refuse(d,'FLAG697_TYPE: rule.r.value')

 def test_string_surrogate_endpoints_and_neighbors(self):
  for v in ['\ud800','\udfff']:
   d=data(cmp(v));d['context_schema']['x']='string';d['evaluation_context']['x']='x';self.refuse(d,'FLAG697_TYPE: rule.r.value')
  for v in ['\ud7ff','\ue000']:
   d=data(cmp(v));d['context_schema']['x']='string';d['evaluation_context']['x']=v;self.assertIs(trace(d),True)

 def test_condition_node_and_op_exact_schema_errors(self):
  for node in [None,[],7,'eq',{}, {'op':None},{'op':7},{'op':[]}]:
   self.refuse(data(node if node is not None else {'op':None}), 'FLAG697_SCHEMA: rule.r')
  d=data();d['flags'][0]['rules'][0]['condition']=None;self.refuse(d,'FLAG697_SCHEMA: rule.r')

 def test_args_type_and_both_arity_edges(self):
  for args in [(),None,{},[],[cmp() for _ in range(128)]]:
   self.refuse(data({'op':'all','args':args}),'FLAG697_BOUND: rule.r.args')
  self.assertIs(trace(data({'op':'all','args':[cmp()]})),True)
  self.assertIs(trace(data({'op':'all','args':[cmp() for _ in range(127)]})),True)

 def test_nested_error_path_preserves_child_index(self):
  node={'op':'any','args':[cmp(),{'op':'all','args':[cmp(),{'op':'bad'}]}]}
  self.refuse(data(node),'FLAG697_OPERATOR: rule.r.args.1.args.1.op')

 def test_seed_and_rule_source_id_128_edges(self):
  evaluate(bucket('s'*128,'u',50))
  self.refuse(bucket('s'*129,'u',50),'FLAG697_ID: rule.r.seed')
  for seed in ['', ' ', True]:self.refuse(bucket(seed,'u',50),'FLAG697_ID: rule.r.seed')
  d=data();d['flags'][0]['rules'][0]['source_id']='s'*128;evaluate(d)
  d['flags'][0]['rules'][0]['source_id']='s'*129;self.refuse(d,'FLAG697_ID: rule.source_id')

 def test_schema64_edge_exact_error(self):
  d=data();d['context_schema']={'x':'int',**{'f'+str(i):'int' for i in range(63)}};evaluate(d)
  d['context_schema']['f63']='int';self.refuse(d,'FLAG697_BOUND: context')
  for schema in [None,[],True]:
   d=data();d['context_schema']=schema;self.refuse(d,'FLAG697_SCHEMA: context')

 def test_percent_scale_100_not_99_or_101(self):
  self.assertIs(trace(bucket('s','key-1',71)),False)
  self.assertIs(trace(bucket('s','key-607',72)),True)

 def test_boolean_child_depth_exact_eight(self):
  node=cmp()
  for _ in range(7):node={'op':'all','args':[node]}
  self.assertIs(trace(data(node)),True)
  self.refuse(data({'op':'all','args':[node]}),'FLAG697_BOUND: rule.r'+'.args.0'*8)

 def test_valid_schema_size_invalid_context_is_schema_error(self):
  for size in [63,64]:
   d=data();d['context_schema']={'f'+str(i):'int' for i in range(size)};d['evaluation_context']=[]
   self.refuse(d,'FLAG697_SCHEMA: context')
