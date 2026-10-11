"""Targeted row697 boundary repair tests, no deployment authority."""
import ast
import importlib.util
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
P=ROOT/'backend/app/modules/m20_general_cognitive_worker/flag_evaluator697.py'
s=importlib.util.spec_from_file_location('flag697_repair',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def req():
    return {'context_schema':{'key':'string'},'evaluation_context':{'key':'ok'},'flags':[{'name':'f','source_id':'src','default':False,'rules':[{'id':'r','source_id':'src','priority':0,'value':True,'condition':{'op':'eq','field':'key','value':'ok'}}]}]}
class String(str):pass
class Repair(unittest.TestCase):
    def refusal(self,fn,code,*args):
        with self.assertRaises(ValueError) as cm:fn(*args)
        self.assertEqual(str(cm.exception),'FLAG697_'+code)
    def test_shape_count_and_exact_keys(self):
        self.refusal(m._shape,'SCHEMA: x',dict.fromkeys(range(4)),{'a'},set(),'x')
        self.refusal(m._shape,'SCHEMA: x',{String('a'):1},{'a'},set(),'x')
        m._shape({'a':1,'b':2},{'a'},{'b'},'x')
        self.refusal(m._shape,'SCHEMA: x',{'a':1,'b':2,'c':3},{'a'},{'b'},'x')
    def test_context_count_first(self):
        d=req();d['evaluation_context']=dict.fromkeys(range(65));self.refusal(m.evaluate_flags697,'BOUND: context',d)
        d=req();d['context_schema']={str(i):'bool' for i in range(64)};d['evaluation_context']={str(i):True for i in range(64)};d['flags']=[];m.evaluate_flags697(d)
    def test_unicode_categories_and_cap(self):
        for char in ('\x00','\n','\u200b','\u2028','\u2029','\ud800','\udfff'):
            self.refusal(m._id,'ID: x','a'+char,'x')
            self.refusal(m._typed,'TYPE: x','a'+char,'string','x')
        for char in ('\u00a0','\u2000','\u3000'):
            m._id('a'+char+'b','x');m._typed(char,'string','x')
        m._id('a'*64,'x');self.refusal(m._id,'ID: x','a'*65,'x')
        m._typed('a'*256,'string','x');self.refusal(m._typed,'TYPE: x','a'*257,'string','x')
    def test_hashed_and_echoed_text(self):
        for field in ('name','source_id'):
            d=req();d['flags'][0][field]='a\u200b';self.refusal(m.evaluate_flags697,'ID: flag.'+field,d)
        d=req();d['evaluation_context']['key']='a\u200b';self.refusal(m.evaluate_flags697,'TYPE: context.key',d)
        d=req();d['flags'][0]['rules'][0]['condition']={'op':'bucket','field':'key','percent':50,'seed':'a\u200b'};self.refusal(m.evaluate_flags697,'ID: rule.r.seed',d)
    def test_enum_caps(self):
        d=req();d['flags'][0]['rules'][0]['condition']['op']='x'*7;self.refusal(m.evaluate_flags697,'OPERATOR: rule.r.op',d)
        d=req();d['context_schema']['key']='x'*7;self.refusal(m.evaluate_flags697,'TYPE: schema.key',d)
        d=req();d['flags'][0]['rules'][0]['condition']={String('op'):'eq','field':'key','value':'ok'};self.refusal(m.evaluate_flags697,'SCHEMA: rule.r',d)
    def test_lookup_caps_before_membership(self):
        d=req();d['flags'][0]['rules'][0]['condition']['field']='x'*65
        self.refusal(m.evaluate_flags697,'FIELD: rule.r.field',d)
        d=req();d['evaluation_context']={'x'*65:'ok'}
        self.refusal(m.evaluate_flags697,'FIELD: context.field',d)
        d=req();d['evaluation_context']={String('key'):'ok'}
        self.refusal(m.evaluate_flags697,'FIELD: context.field',d)
        d=req();d['flags'][0]['rules'][0]['condition']['field']=String('key')
        self.refusal(m.evaluate_flags697,'FIELD: rule.r.field',d)
        funcs={n.name:n for n in ast.parse(P.read_text()).body if isinstance(n,ast.FunctionDef)}
        text=ast.unparse(funcs['_condition'])
        self.assertLess(text.index('type(field)'),text.index('len(field)'))
        self.assertLess(text.index('len(field)'),text.index('field not in schema'))
        text=ast.unparse(funcs['evaluate_flags697'])
        self.assertLess(text.index('len(field)'),text.index('field not in schema'))
        d=req();d['context_schema']={'x'*64:'string'};d['evaluation_context']={'x'*64:'ok'}
        d['flags'][0]['rules'][0]['condition']['field']='x'*64;m.evaluate_flags697(d)

    def test_large_integer_guard(self):
        for kind in ('int','number'):
            m._typed(2**53-1,kind,'x');m._typed(-(2**53-1),kind,'x')
            for v in (2**53,-2**53,1<<100000):self.refusal(m._typed,'TYPE: x',v,kind,'x')
    def test_source_guard_order(self):
        tree=ast.parse(P.read_text());func={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        text=ast.unparse(func['_shape']);self.assertLess(text.index('len(value)'),text.index('set(value)'));self.assertLess(text.index('type(k)'),text.index('set(value)'))
        text=ast.unparse(func['_id']);self.assertLess(text.index('len(value)'),text.index('strip()'));self.assertLess(text.index('len(value)'),text.index('_unsafe_text'))
        text=ast.unparse(func['_typed']);self.assertLess(text.index('bit_length()'),text.index('abs('))
        text=ast.unparse(func['_condition']);self.assertLess(text.index('len(op)'),text.index("op in ('all', 'any')"))
        text=ast.unparse(func['evaluate_flags697']);self.assertLess(text.index('len(context)'),text.index('context.items()'));self.assertLess(text.index('len(kind)'),text.index('kind not in KINDS'))
    def test_condition_four_five_keys_and_key_gate(self):
        node={'op':'bucket','field':'key','seed':'s','percent':50}
        d=req();d['flags'][0]['rules'][0]['condition']=node;m.evaluate_flags697(d)
        d=req();d['flags'][0]['rules'][0]['condition']={**node,'extra':1}
        self.refusal(m.evaluate_flags697,'BOUND: rule.r',d)
        d=req();d['flags'][0]['rules'][0]['condition']={String('op'):'invalid','field':'key','value':'ok'}
        self.refusal(m.evaluate_flags697,'SCHEMA: rule.r',d)

    def test_non_dict_shapes_and_children(self):
        for bad in (None,[],1,'bad'):
            d=req();d['flags']=[bad];self.refusal(m.evaluate_flags697,'SCHEMA: flag',d)
            d=req();d['flags'][0]['rules']=[bad];self.refusal(m.evaluate_flags697,'SCHEMA: rule',d)
            for op in ('all','any','not','bucket'):
                d=req()
                node={'op':op,'args':[bad]} if op in ('all','any') else {'op':'not','arg':bad} if op=='not' else bad
                d['flags'][0]['rules'][0]['condition']=node
                path='rule.r.args.0' if op in ('all','any') else 'rule.r.arg' if op=='not' else 'rule.r'
                self.refusal(m.evaluate_flags697,'SCHEMA: '+path,d)
        for bad in (None,{},1,'bad'):
            d=req();d['flags']=bad;self.refusal(m.evaluate_flags697,'BOUND: flags',d)
            d=req();d['flags'][0]['rules']=bad;self.refusal(m.evaluate_flags697,'BOUND: flag.rules',d)

    def test_unknown_keys_all_levels(self):
        d=req();d['extra']=True;self.refusal(m.evaluate_flags697,'SCHEMA: request',d)
        d=req();d['flags'][0]['extra']=1;self.refusal(m.evaluate_flags697,'SCHEMA: flag',d)
        d=req();d['flags'][0]['rules'][0]['extra']=1;self.refusal(m.evaluate_flags697,'SCHEMA: rule',d)
        for op in ('all','any','not','bucket','eq'):
            node={'op':op,'args':[{'op':'eq','field':'key','value':'ok'}]} if op in ('all','any') else {'op':'not','arg':{'op':'eq','field':'key','value':'ok'}} if op=='not' else {'op':'bucket','field':'key','seed':'s','percent':50} if op=='bucket' else {'op':'eq','field':'key','value':'ok'}
            node['extra']=1;d=req();d['flags'][0]['rules'][0]['condition']=node
            self.refusal(m.evaluate_flags697,('BOUND' if op=='bucket' else 'SCHEMA')+': rule.r',d)

    def test_schema_ids_kinds_and_context_numbers(self):
        for field in ('','a\u200b','x'*65,String('key')):
            d=req();d['context_schema']={field:'string'};d['evaluation_context']={};d['flags']=[]
            self.refusal(m.evaluate_flags697,'ID: schema.field',d)
        for kind in ('foo','',5,None,b'int'):
            d=req();d['context_schema']['key']=kind;self.refusal(m.evaluate_flags697,'TYPE: schema.key',d)
        for kind in ('number','int'):
            for val in ('bad',None,{},[],True):
                d=req();d['context_schema']['key']=kind;d['evaluation_context']['key']=val
                self.refusal(m.evaluate_flags697,'TYPE: context.key',d)
        for val,ok in ((float(2**53-1),True),(float(2**53),False)):
            d=req();d['context_schema']['key']='number';d['evaluation_context']['key']=val;d['flags']=[]
            if ok:m.evaluate_flags697(d)
            else:self.refusal(m.evaluate_flags697,'TYPE: context.key',d)

    def test_string_context_exact_type_and_rule_ids(self):
        for value in (1,None,1.0,True,[],b'ok'):
            d=req();d['evaluation_context']['key']=value
            self.refusal(m.evaluate_flags697,'TYPE: context.key',d)
        for value in ('','a\u200b','x'*65,String('r')):
            d=req();d['flags'][0]['rules'][0]['id']=value
            self.refusal(m.evaluate_flags697,'ID: rule.id',d)

    def test_priority_endpoint(self):
        d=req();d['flags'][0]['rules'][0]['priority']=1000000;m.evaluate_flags697(d)
        d['flags'][0]['rules'][0]['priority']=1000001;self.refusal(m.evaluate_flags697,'PRIORITY: r',d)
        d['flags'][0]['rules'][0]['priority']=-1;self.refusal(m.evaluate_flags697,'PRIORITY: r',d)

    def test_behavior_unchanged(self):
        o=m.evaluate_flags697(req());self.assertTrue(o['flags'][0]['value']);self.assertFalse(o['release_authorized']);self.assertFalse(o['evidence_verified'])
if __name__=='__main__':unittest.main(verbosity=2)
