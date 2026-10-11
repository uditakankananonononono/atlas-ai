"""Hermetic row687 declaration-consistency tests, stdlib only."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/test_driven_development687.py'
spec=importlib.util.spec_from_file_location('row687',P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def receipt(stage,ordinal,tests=None):
    return dict(stage=stage,ordinal=ordinal,revision_ref='revision-'+stage,suite_ref='suite',
                evidence_ref='receipt-'+stage,results=tests or [dict(id='test',outcome='FAIL' if stage=='red' else 'PASS')])


def cycle(i='cycle'):
    return dict(id=i,behavior='declared behavior',receipts=[receipt('red',1),receipt('green',2),receipt('refactor',3)])


def request(cycles=None):return dict(as_of='caller label',cycles=[cycle()] if cycles is None else cycles)


class Contract(unittest.TestCase):
    def refuse(self,x,code):
        with self.assertRaises(ValueError) as e:m.run(x)
        self.assertEqual(str(e.exception),'TESTDR687:'+code)

    def test_real_receipt_counts_and_flags(self):
        r=m.run(request())
        self.assertEqual(r['consistent_cycles'],1)
        self.assertEqual(r['cycles'][0]['result_counts'],{'red':{'PASS':0,'FAIL':1},'green':{'PASS':1,'FAIL':0},'refactor':{'PASS':1,'FAIL':0}})
        self.assertFalse(r['tests_executed']);self.assertFalse(r['evidence_verified'])
        self.assertFalse(r['repository_behavior_verified']);self.assertFalse(r['release_authority'])
        self.assertEqual(r['status'],'supplied_receipt_consistency_only')

    def test_order_not_boolean_claim(self):
        x=request();x['cycles'][0]['receipts'][1]['ordinal']=1
        self.assertEqual(m.run(x)['cycles'][0]['reasons'],['stage_order_not_increasing'])
        x=request();x['cycles'][0]['receipts'][0]['results'][0]['outcome']='PASS'
        self.assertEqual(m.run(x)['cycles'][0]['reasons'],['red_has_no_failure'])

    def test_green_and_refactor_failure_reasons(self):
        x=request();x['cycles'][0]['receipts'][1]['results'][0]['outcome']='FAIL';x['cycles'][0]['receipts'][2]['results'][0]['outcome']='FAIL'
        self.assertEqual(m.run(x)['cycles'][0]['reasons'],['green_has_failure','refactor_has_failure'])

    def test_suite_test_revision_consistency(self):
        x=request();rs=x['cycles'][0]['receipts'];rs[1]['suite_ref']='other';rs[1]['results'][0]['id']='other';rs[1]['revision_ref']=rs[0]['revision_ref']
        self.assertEqual(m.run(x)['cycles'][0]['reasons'],['suite_ref_changed','test_ids_changed','red_green_revision_unchanged'])

    def test_n64_n65_cycles(self):
        self.assertEqual(m.run(request([cycle(str(i)) for i in range(64)]))['consistent_cycles'],64)
        self.refuse(request([cycle(str(i)) for i in range(65)]),'limit:cycles')

    def test_n100_n101_test_rows(self):
        x=request()
        for rs in x['cycles'][0]['receipts']:rs['results']=[dict(id=str(i),outcome='FAIL' if rs['stage']=='red' else 'PASS') for i in range(100)]
        self.assertEqual(m.run(x)['cycles'][0]['result_counts']['red']['FAIL'],100)
        x['cycles'][0]['receipts'][0]['results'].append(dict(id='extra',outcome='FAIL'));self.refuse(x,'limit:results')

    def test_raw_text_cap_and_no_strip_allocation(self):
        self.assertEqual(m.run(dict(as_of='x'*256,cycles=[cycle()]))['as_of'],'x'*256)
        for value in ['x'*257,' '*257,'x'*(10*1024*1024)]:
            self.refuse(dict(as_of=value,cycles=[cycle()]),'text_length:as_of')
        import inspect
        lines,start=inspect.getsourcelines(m._text);blocked={start+i for i,l in enumerate(lines) if '.strip(' in l or 'unicodedata.category' in l};executed=set()
        def trace(frame,event,arg):
            if frame.f_code is m._text.__code__ and event=='line':executed.add(frame.f_lineno)
            return trace
        old=sys.gettrace()
        try:
            sys.settrace(trace)
            with self.assertRaises(ValueError):m._text('x'*(10*1024*1024),'as_of')
        finally:sys.settrace(old)
        self.assertFalse(blocked & executed)

    def test_unicode_text_fields(self):
        for value in [chr(0x85),chr(0x2028),chr(0x2029),chr(0x202e),chr(0x200b),chr(0xfeff),chr(127)]:
            self.refuse(dict(as_of='a'+value,cycles=[cycle()]),'text_control:as_of')
        self.assertEqual(m.run(dict(as_of='café 東京',cycles=[cycle()]))['as_of'],'café 東京')

    def test_unknown_missing_and_shapes(self):
        for x,code in [(None,'type:request'),({},'fields:request'),(dict(as_of='x',cycles=[]),'empty:cycles'),(dict(as_of='x',cycles=()),'type:cycles')]:self.refuse(x,code)
        x=request();x['extra']=1;self.refuse(x,'fields:request')
        x=request();x['cycles'][0]['extra']=1;self.refuse(x,'fields:cycle')
        x=request();x['cycles'][0]['receipts'][0]['extra']=1;self.refuse(x,'fields:receipt')
        x=request();x['cycles'][0]['receipts'][0]['results'][0]['extra']=1;self.refuse(x,'fields:result')

    def test_duplicate_ids(self):
        self.refuse(request([cycle(),cycle()]),'duplicate:cycle_id')
        x=request();x['cycles'][0]['receipts'][0]['results']*=2;self.refuse(x,'duplicate:test_id')

    def test_receipt_stages_and_ordinals(self):
        x=request();x['cycles'][0]['receipts'].pop();self.refuse(x,'count:receipts')
        x=request();x['cycles'][0]['receipts'][0]['stage']='green';self.refuse(x,'stage:receipts')
        for value in [True,0,-1,1.5,10**9+1]:
            x=request();x['cycles'][0]['receipts'][0]['ordinal']=value;self.refuse(x,'integer:ordinal')
        x=request();x['cycles'][0]['receipts'][2]['ordinal']=10**9;self.assertEqual(m.run(x)['consistent_cycles'],1)

    def test_bad_result_and_text(self):
        x=request();x['cycles'][0]['receipts'][0]['results'][0]['outcome']='SKIP';self.refuse(x,'outcome:result')
        x=request();x['cycles'][0]['id']=False;self.refuse(x,'type:cycle_id')
        x=request();x['cycles'][0]['behavior']=' ';self.refuse(x,'empty:behavior')

    def test_input_and_output_isolation(self):
        x=request();before=copy.deepcopy(x);r=m.run(x);self.assertEqual(x,before);self.assertEqual(r,m.run(x))
        r['cycles'][0]['evidence_refs'].append('changed');self.assertEqual(x,before)

    def test_count_first_all_four_shapes(self):
        import inspect
        lines,start=inspect.getsourcelines(m._fields)
        blocked={start+i for i,line in enumerate(lines) if 'set(value)' in line or 'for key in value' in line}
        for name in ('request','cycle','receipt','result'):
            executed=set()
            def trace(frame,event,arg):
                if frame.f_code is m._fields.__code__ and event=='line':executed.add(frame.f_lineno)
                return trace
            old=sys.gettrace()
            try:
                sys.settrace(trace)
                with self.assertRaises(ValueError) as e:m._fields({str(i):i for i in range(65)},(),name)
            finally:sys.settrace(old)
            self.assertEqual(str(e.exception),'TESTDR687:fields:'+name)
            self.assertFalse(blocked & executed)

    def test_exact_string_keys_all_four_shapes(self):
        class SubKey(str):pass
        for name,keys in [('request',('as_of','cycles')),('cycle',('id','behavior','receipts')),
                          ('receipt',('stage','ordinal','revision_ref','suite_ref','evidence_ref','results')),
                          ('result',('id','outcome'))]:
            for key in (SubKey(keys[0]),23):
                value={k:None for k in keys[1:]};value[key]=None
                with self.assertRaises(ValueError) as e:m._fields(value,keys,name)
                self.assertEqual(str(e.exception),'TESTDR687:fields:'+name)

    def test_all_seven_text_fields_full_cf_and_controls(self):
        import unicodedata
        forbidden=[chr(i) for i in range(0x110000) if unicodedata.category(chr(i))=='Cf']
        self.assertIn(chr(0xad),forbidden);self.assertIn(chr(0x2060),forbidden)
        forbidden += [chr(0),chr(0x85),chr(0x2028),chr(0x2029)]
        locations=[('as_of','as_of'),('id','cycle_id'),('behavior','behavior'),
                   ('revision_ref','revision_ref'),('suite_ref','suite_ref'),('evidence_ref','evidence_ref'),('test_id','test_id')]
        for field,code in locations:
            for char in forbidden:
                x=request()
                target=x if field=='as_of' else x['cycles'][0] if field in ('id','behavior') else x['cycles'][0]['receipts'][0]
                key=field
                if field=='test_id':target=target['results'][0];key='id'
                target[key]='a'+char
                self.refuse(x,'text_control:'+code)
            for value in ('x'*257,' '*257):
                x=request();target=x if field=='as_of' else x['cycles'][0] if field in ('id','behavior') else x['cycles'][0]['receipts'][0];key=field
                if field=='test_id':target=target['results'][0];key='id'
                target[key]=value;self.refuse(x,'text_length:'+code)

    def test_zs_accepted_no_new_cs_refusal(self):
        for char in (chr(0xa0),chr(0x2003),chr(0xd800)):
            self.assertEqual(m._text('a'+char,'as_of'),'a'+char)

    def test_enum_type_cap_and_order(self):
        import inspect
        lines,start=inspect.getsourcelines(m.run)
        for field,code,marker in [('stage','stage:receipts',"receipt['stage']!=stage"),
                                  ('outcome','outcome:result','outcome not in stage_counts')]:
            with self.subTest(field=field):
                blocked={start+i for i,line in enumerate(lines) if marker in line}
                for value in [False,23,None,[],{},'x'*257,' '*257,'x'*(10*1024*1024)]:
                    x=request();target=x['cycles'][0]['receipts'][0]
                    if field=='outcome':target=target['results'][0]
                    target[field]=value;executed=set()
                    def trace(frame,event,arg):
                        if frame.f_code is m.run.__code__ and event=='line':executed.add(frame.f_lineno)
                        return trace
                    old=sys.gettrace()
                    try:
                        sys.settrace(trace);self.refuse(x,code)
                    finally:sys.settrace(old)
                    self.assertFalse(blocked & executed)
                x=request();target=x['cycles'][0]['receipts'][0]
                if field=='outcome':target=target['results'][0]
                target[field]='x'*256;executed=set()
                def trace(frame,event,arg):
                    if frame.f_code is m.run.__code__ and event=='line':executed.add(frame.f_lineno)
                    return trace
                old=sys.gettrace()
                try:
                    sys.settrace(trace);self.refuse(x,code)
                finally:sys.settrace(old)
                self.assertTrue(blocked & executed)
                class Sub(str):pass
                target[field]=Sub('red' if field=='stage' else 'FAIL');self.refuse(x,code)

    def test_enum_cf_values_refuse(self):
        for field,code in [('stage','stage:receipts'),('outcome','outcome:result')]:
            for char in (chr(0xad),chr(0x2060),chr(0x200b)):
                x=request();target=x['cycles'][0]['receipts'][0]
                if field=='outcome':target=target['results'][0]
                target[field]=('red' if field=='stage' else 'FAIL')+char;self.refuse(x,code)

if __name__=='__main__':unittest.main()
