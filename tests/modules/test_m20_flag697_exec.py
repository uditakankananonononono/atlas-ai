"""Stdlib, source-loaded tests for the finite supplied flag evaluator."""
import copy
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import unittest

CORE = Path(os.environ.get('FLAG697_CORE', str(Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/flag_evaluator697.py')))
spec = importlib.util.spec_from_file_location('flag697', CORE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
evaluate = module.evaluate_flags697

def cmp(op='eq', value=1, field='x'):
    return {'op': op, 'field': field, 'value': value}

def payload(condition=None):
    return {'context_schema': {'x': 'int'}, 'evaluation_context': {'x': 1},
            'flags': [{'name': 'beta', 'source_id': 'flag-src', 'default': False,
                       'rules': [{'id': 'r1', 'source_id': 'rule-src', 'priority': 1,
                                  'value': True, 'condition': condition or cmp()}]}]}

def flag(data):
    return evaluate(data)['flags'][0]

class Flag697Tests(unittest.TestCase):
    def refusal(self, data, code):
        with self.assertRaises(ValueError) as caught:
            evaluate(data)
        self.assertEqual(str(caught.exception).split(':', 1)[0], code)

    def test_actual_evaluation_ignores_caller_safe(self):
        d = payload(); d['flags'][0]['safe'] = True
        d['evaluation_context']['x'] = 0
        out = evaluate(d)
        self.assertFalse(out['flags'][0]['value'])
        self.assertTrue(out['flags'][0]['caller_diagnostic_safe'])
        self.assertFalse(out['repository_behavior_verified'])
        self.assertFalse(out['release_authorized'])
        self.assertFalse(out['evidence_verified'])
        self.assertTrue(out['capability_executed'])

    def test_exhaustive_integer_comparators(self):
        oracle = {'eq': lambda a,b:a==b, 'ne':lambda a,b:a!=b,
                  'lt':lambda a,b:a<b, 'le':lambda a,b:a<=b,
                  'gt':lambda a,b:a>b, 'ge':lambda a,b:a>=b}
        for op, a, b in itertools.product(oracle, range(-2,3), range(-2,3)):
            d=payload(cmp(op,b)); d['evaluation_context']['x']=a
            with self.subTest(op=op,a=a,b=b):
                self.assertEqual(flag(d)['value'], oracle[op](a,b))

    def test_boolean_truth_tables_all_any_not(self):
        for a,b in itertools.product((False,True),repeat=2):
            for op,want in [('all',a and b),('any',a or b)]:
                d=payload({'op':op,'args':[cmp('eq',True,'a'),cmp('eq',True,'b')]})
                d.update(context_schema={'a':'bool','b':'bool'},evaluation_context={'a':a,'b':b})
                self.assertEqual(flag(d)['value'],want)
            d=payload({'op':'not','arg':cmp('eq',True,'a')})
            d.update(context_schema={'a':'bool'},evaluation_context={'a':a})
            self.assertEqual(flag(d)['value'],not a)

    def test_string_and_number_equalities(self):
        for kind,values in [('string',['','a','é']),('number',[-1,0,0.5,1.0]),('bool',[False,True])]:
            for a,b in itertools.product(values,repeat=2):
                for op in ['eq','ne']:
                    d=payload(cmp(op,b));d['context_schema']={'x':kind};d['evaluation_context']={'x':a}
                    self.assertEqual(flag(d)['value'],(a==b) if op=='eq' else (a!=b))

    def test_missing_context_propagates_unknown_not_false(self):
        for condition in [cmp('ne'), {'op':'not','arg':cmp()},
                          {'op':'any','args':[cmp(),cmp('ne')]}]:
            d=payload(condition);d['evaluation_context']={}
            f=flag(d)
            self.assertFalse(f['value']);self.assertEqual(f['reason'],'default_no_match')
            self.assertIsNone(f['trace'][0]['matched'])
            self.assertEqual(f['trace'][0]['missing_fields'],['x'])

    def test_three_valued_boolean_missing(self):
        missing=cmp('eq',1,'x');yes=cmp('eq',True,'b');no=cmp('eq',False,'b')
        for op,args,want in [('all',[missing,no],False),('all',[missing,yes],None),
                             ('any',[missing,yes],True),('any',[missing,no],None)]:
            d=payload({'op':op,'args':args});d.update(context_schema={'x':'int','b':'bool'},evaluation_context={'b':True})
            self.assertEqual(flag(d)['trace'][0]['matched'],want)

    def test_priority_trace_and_unsorted_order(self):
        d=payload();r=d['flags'][0]['rules'][0]
        d['flags'][0]['rules']=[dict(r,id='low',priority=9,value=True),dict(r,id='high',priority=0,value=False)]
        f=flag(d);self.assertFalse(f['value']);self.assertEqual(f['matched_rule_id'],'high')
        self.assertEqual(f['priority'],0);self.assertEqual([x['rule_id'] for x in f['trace']],['high','low'])
        self.assertEqual(f['source_id'],'flag-src');self.assertEqual(f['trace'][0]['source_id'],'rule-src')
        alt=copy.deepcopy(d);alt['flags'][0]['rules'].reverse();self.assertEqual(evaluate(d),evaluate(alt))

    def test_default_both_values_and_no_rules(self):
        for default in (True,False):
            d=payload();d['flags'][0].update(default=default,rules=[])
            f=flag(d);self.assertEqual(f['value'],default);self.assertIsNone(f['priority'])
            self.assertIsNone(f['matched_rule_id']);self.assertEqual(f['trace'],[])

    def test_duplicate_names_rule_ids_priorities(self):
        d=payload();d['flags'].append(copy.deepcopy(d['flags'][0]));self.refusal(d,'FLAG697_DUPLICATE_FLAG')
        for key,code in [('id','FLAG697_DUPLICATE_RULE'),('priority','FLAG697_DUPLICATE_PRIORITY')]:
            d=payload();r=copy.deepcopy(d['flags'][0]['rules'][0]);r['id']='r2';r['priority']=2
            r[key]=d['flags'][0]['rules'][0][key];d['flags'][0]['rules'].append(r);self.refusal(d,code)

    def test_unknown_operator_and_field(self):
        self.refusal(payload(cmp('exec')),'FLAG697_OPERATOR')
        self.refusal(payload(cmp(field='other')),'FLAG697_FIELD')
        d=payload();d['evaluation_context']['other']=1;self.refusal(d,'FLAG697_FIELD')

    def test_type_mismatches_and_nonfinite(self):
        for value in [True,1.0,'1',None,[],{}]:
            d=payload();d['evaluation_context']['x']=value;self.refusal(d,'FLAG697_TYPE')
            self.refusal(payload(cmp(value=value)),'FLAG697_TYPE')
        for value in [float('nan'),float('inf'),-float('inf')]:
            d=payload();d['context_schema']['x']='number';d['evaluation_context']['x']=value
            self.refusal(d,'FLAG697_TYPE')
        for kind,val in [('bool',True),('string','a')]:
            d=payload(cmp('lt',val));d['context_schema']['x']=kind;d['evaluation_context']['x']=val
            self.refusal(d,'FLAG697_OPERATOR_TYPE')

    def test_strict_schema_and_source_ids(self):
        for d in [{},[],dict(payload(),extra=True)]:self.refusal(d,'FLAG697_SCHEMA')
        d=payload();d['flags'][0]['source_id']='';self.refusal(d,'FLAG697_ID')
        d=payload();d['flags'][0]['rules'][0]['source_id']='';self.refusal(d,'FLAG697_ID')
        d=payload();d['flags'][0]['rules'][0]['priority']=True;self.refusal(d,'FLAG697_PRIORITY')
        d=payload();d['flags'][0]['default']=1;self.refusal(d,'FLAG697_TYPE')
        d=payload();d['flags'][0]['safe']='yes';self.refusal(d,'FLAG697_TYPE')
        self.refusal(payload({'op':'all','args':[]}),'FLAG697_BOUND')

    def test_flag_rule_field_and_string_exact_limits(self):
        d=payload();d['flags']=[dict(d['flags'][0],name='f'+str(i)) for i in range(32)]
        self.assertEqual(len(evaluate(d)['flags']),32)
        d['flags'].append(dict(d['flags'][0],name='f32'));self.refusal(d,'FLAG697_BOUND')
        d=payload();d['flags'][0]['rules']=[dict(d['flags'][0]['rules'][0],id='r'+str(i),priority=i) for i in range(32)]
        self.assertEqual(len(flag(d)['trace']),32)
        d['flags'][0]['rules'].append(dict(d['flags'][0]['rules'][0],id='r32',priority=32));self.refusal(d,'FLAG697_BOUND')
        d=payload();d['context_schema']={'f'+str(i):'int' for i in range(64)};d['evaluation_context']={};d['flags'][0]['rules']=[]
        evaluate(d);d['context_schema']['f64']='int';self.refusal(d,'FLAG697_BOUND')
        d=payload(cmp(value='s'*256));d['context_schema']['x']='string';d['evaluation_context']['x']='s'*256;self.assertTrue(flag(d)['value'])
        d['evaluation_context']['x']='s'*257;self.refusal(d,'FLAG697_TYPE')
        d=payload();d['flags'][0]['name']='n'*64;evaluate(d);d['flags'][0]['name']='n'*65;self.refusal(d,'FLAG697_ID')
        d=payload();d['flags'][0]['source_id']='s'*128;evaluate(d);d['flags'][0]['source_id']='s'*129;self.refusal(d,'FLAG697_ID')
        d=payload(cmp(value=2**53-1));d['evaluation_context']['x']=2**53-1;evaluate(d)
        d['evaluation_context']['x']=2**53;self.refusal(d,'FLAG697_TYPE')

    def test_node_and_depth_exact_limits(self):
        # One all root + 127 comparator leaves =128; depth remains2.
        d=payload({'op':'all','args':[cmp() for _ in range(127)]});self.assertTrue(flag(d)['value'])
        d['flags'][0]['rules'][0]['condition']['args'].append(cmp());self.refusal(d,'FLAG697_BOUND')
        node=cmp()
        for _ in range(7):node={'op':'not','arg':node}
        d=payload(node);evaluate(d)
        d['flags'][0]['rules'][0]['condition']={'op':'not','arg':node};self.refusal(d,'FLAG697_BOUND')

    def test_bucket_boundaries_and_independent_hash_oracle(self):
        for key in ['u1','u2','é', 'z'*256]:
            score=int.from_bytes(hashlib.sha256(json.dumps(['seed',key],ensure_ascii=False,separators=(',',':')).encode('utf-8')).digest()[:8],'big')%10000
            for percent in [0,1,25,50,99,100]:
                d=payload({'op':'bucket','field':'u','seed':'seed','percent':percent});d.update(context_schema={'u':'string'},evaluation_context={'u':key})
                self.assertEqual(flag(d)['value'],score<percent*100)
                self.assertEqual(evaluate(d),evaluate(copy.deepcopy(d)))
        for value in [-1,101,True,0.5]:
            self.refusal(payload({'op':'bucket','field':'x','seed':'seed','percent':value}),'FLAG697_BUCKET')
        self.refusal(payload({'op':'bucket','field':'x','seed':'seed','percent':50}),'FLAG697_OPERATOR_TYPE')

    def test_input_immutable_and_all_rules_validated(self):
        d=payload();before=copy.deepcopy(d);evaluate(d);self.assertEqual(d,before)
        d['flags'][0]['rules'].append({'id':'r2','source_id':'s','priority':2,'value':True,'condition':cmp('bad')})
        self.refusal(d,'FLAG697_OPERATOR')

    def test_flag_output_sorted_not_input_order(self):
        d=payload();d['flags'].append(dict(d['flags'][0],name='alpha'))
        self.assertEqual([x['name'] for x in evaluate(d)['flags']],['alpha','beta'])
        e=copy.deepcopy(d);e['flags'].reverse();self.assertEqual(evaluate(d),evaluate(e))


# Additional exact-bound and malformed-input cases (collected when imported).
class Flag697AdditionalTests(unittest.TestCase):
    refusal = Flag697Tests.refusal
    def test_priority_and_percent_and_args_bounds(self):
        d=payload();d['flags'][0]['rules'][0]['priority']=1000000;evaluate(d)
        d['flags'][0]['rules'][0]['priority']=1000001;self.refusal(d,'FLAG697_PRIORITY')
        for p in [0,100]:
            d=payload({'op':'bucket','field':'x','seed':'s','percent':p});d['context_schema']['x']='string';d['evaluation_context']['x']='u';evaluate(d)
        for kind in ['unknown',True,[]]:
            d=payload();d['context_schema']['x']=kind;self.refusal(d,'FLAG697_TYPE')
        d=payload();d['flags'][0]['rules'][0]['value']=1;self.refusal(d,'FLAG697_TYPE')
        d=payload(cmp(value='\ud800'));d['context_schema']['x']='string';d['evaluation_context']['x']='\ud800'
        self.refusal(d,'FLAG697_TYPE')

    def test_independent_node_bound_not_masked_by_arity(self):
        d=payload({'op':'all','args':[{'op':'not','arg':cmp()}]+[cmp() for _ in range(125)]})
        evaluate(d) # root1 + not2 +125 leaves =128
        d['flags'][0]['rules'][0]['condition']['args'].append(cmp())
        self.refusal(d,'FLAG697_BOUND') # arity127 legal; nodes129 illegal

if __name__ == '__main__': unittest.main(verbosity=2)
