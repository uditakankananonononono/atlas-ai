"""Hermetic stdlib tests: caller-declared bookkeeping, not legal validity."""
import copy
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/agency_proceedings1269.py'
spec = importlib.util.spec_from_file_location('agency1269', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    return dict(jurisdiction='declared-region', as_of='2026-10-11',
        sources=[dict(key='source-a', citation='Declared authority excerpt', jurisdiction='declared-region',
                      checked_on='2026-10-11', url='https://example.org/authority')],
        tribunal=dict(label='declared-tribunal', source_keys=['source-a']),
        records=[dict(key='record-a', text='Supplied record excerpt', source_keys=['source-a'])],
        pleadings=[dict(key='pleading-a', text='Declared pleading', record_keys=['record-a'], source_keys=['source-a'])],
        hearings=[dict(key='hearing-a', on='2026-10-10', text='Declared hearing step', record_keys=['record-a'], source_keys=['source-a'])],
        exhaustion=[dict(key='step-a', state='unknown', text='Caller cannot confirm step', source_keys=['source-a'])],
        assertions=['Caller assertion, not a sourced fact'],
        analysis=[dict(text='Counsel review question', source_keys=['source-a'])])


class AgencyTests(unittest.TestCase):
    def call(self, p):
        return module.organize(p)
    def refuses(self, p, code):
        try:
            self.call(p)
        except module.AgencyProceedingsError as error:
            self.assertEqual(code, str(error))
        except Exception as error:
            self.fail('Expected exact refusal '+code+', got unexpected '+type(error).__name__)
        else:
            self.fail('Expected exact refusal '+code+', got success')
    def test_real_bookkeeping_and_separation(self):
        p=fixture();before=copy.deepcopy(p);o=self.call(p)
        self.assertEqual(before,p)
        self.assertEqual(1269,o['row_id'])
        self.assertEqual({'sources':1,'records':1,'pleadings':1,'hearings':1,'exhaustion_steps':1},o['counts'])
        self.assertEqual(['pleading-a','hearing-a'],o['record_usage']['record-a'])
        self.assertEqual(['step-a'],o['unknown_exhaustion_steps'])
        self.assertIsNone(o['exhaustion_decision'])
        self.assertFalse(o['authority_verified']);self.assertFalse(o['external_effect'])
        o['supplied']['records'][0]['text']='changed'
        self.assertEqual(before,p)
    def test_exact_top_schema(self):
        p=fixture();p['legal_outcome']=True;self.refuses(p,'AGENCY1269:SCHEMA')
    def test_missing_source(self):
        p=fixture();p['records'][0]['source_keys']=['absent'];self.refuses(p,'AGENCY1269:SOURCE_REF')
    def test_missing_record(self):
        p=fixture();p['hearings'][0]['record_keys']=['absent'];self.refuses(p,'AGENCY1269:RECORD_REF')
    def test_duplicate_key(self):
        p=fixture();p['records']*=2;self.refuses(p,'AGENCY1269:DUPLICATE')
    def test_duplicate_ref(self):
        p=fixture();p['tribunal']['source_keys']*=2;self.refuses(p,'AGENCY1269:REFS')
    def test_wrong_state(self):
        p=fixture();p['exhaustion'][0]['state']='legally_exhausted';self.refuses(p,'AGENCY1269:STATE')
    def test_bad_date(self):
        p=fixture();p['as_of']='2026-02-30';self.refuses(p,'AGENCY1269:DATE')
    def test_noncanonical_date(self):
        p=fixture();p['as_of']='20261011';self.refuses(p,'AGENCY1269:DATE')
    def test_url_credentials(self):
        p=fixture();p['sources'][0]['url']='https://user:secret@example.org/';self.refuses(p,'AGENCY1269:URL')
    def test_control_and_padding(self):
        for text in [' padded','bad\x1ftext','']:
            with self.subTest(text=repr(text)):
                p=fixture();p['jurisdiction']=text;self.refuses(p,'AGENCY1269:TEXT')
    def test_text_bound_both_sides(self):
        p=fixture();p['records'][0]['text']='x'*2048;self.assertEqual(1269,self.call(p)['row_id'])
        p['records'][0]['text']+='x';self.refuses(p,'AGENCY1269:TEXT')
    def test_list_bounds_literal(self):
        for count in [128,129]:
            p=fixture();p['records']=[dict(key=f'record-{n}',text='Declared record',source_keys=['source-a']) for n in range(count)]
            p['pleadings']=[];p['hearings']=[]
            if count==128:self.assertEqual(128,self.call(p)['counts']['records'])
            else:self.refuses(p,'AGENCY1269:BOUND')
    def test_empty_sources_refuse(self):
        p=fixture();p['sources']=[];self.refuses(p,'AGENCY1269:BOUND')
    def test_empty_record_lists_allowed(self):
        p=fixture();p['records']=[];p['pleadings']=[];p['hearings']=[];p['exhaustion']=[]
        o=self.call(p);self.assertEqual({},o['record_usage']);self.assertEqual('review_required',o['status'])
    def test_mismatch_stale_and_future_are_flags_not_legal_decisions(self):
        p=fixture();p['sources'][0]['jurisdiction']='other';p['sources'][0]['checked_on']='2026-10-09';p['hearings'][0]['on']='2026-10-12'
        o=self.call(p);self.assertEqual('needs_review',o['status'])
        self.assertEqual(['source-a'],o['jurisdiction_mismatches']);self.assertEqual(['source-a'],o['stale_source_keys'])
        self.assertEqual(['hearing-a'],o['future_hearing_keys']);self.assertIsNone(o['exhaustion_decision'])
    def test_future_source_check_refuses(self):
        p=fixture();p['sources'][0]['checked_on']='2026-10-12';self.refuses(p,'AGENCY1269:FUTURE_SOURCE')
    def test_assertions_not_promoted(self):
        o=self.call(fixture());self.assertEqual(['Caller assertion, not a sourced fact'],o['supplied']['assertions'])
        self.assertEqual('caller_supplied_unverified',o['evidence_status'])

    def test_forbidden_unicode_categories_and_explicit_cf_pins(self):
        import unicodedata
        values = ['\u00ad','\u2060','\u200d','\u0085','\u2028','\u2029']
        values += [chr(n) for n in range(0x110000) if unicodedata.category(chr(n)) == 'Cf']
        for value in values:
            with self.subTest(codepoint=hex(ord(value))):
                p=fixture();p['records'][0]['text']='left'+value+'right'
                self.refuses(p,'AGENCY1269:TEXT')
    def test_zs_accepted_and_cs_residual_not_new_refusal(self):
        for value in ['\u00a0','\u2007','\ud800']:
            p=fixture();p['records'][0]['text']='left'+value+'right'
            self.assertEqual(1269,self.call(p)['row_id'])
    def test_dict_count_precedes_key_iteration(self):
        class Oversized(dict):
            def __iter__(self):raise AssertionError('key iteration before count')
        # Strict schema rejects subclasses before count or iteration too.
        self.refuses(Oversized({str(n):None for n in range(129)}),'AGENCY1269:SCHEMA')
        p=fixture();p.update({str(n):None for n in range(129)})
        self.refuses(p,'AGENCY1269:SCHEMA')


    def test_root_text_dates_types_and_renamed_schema(self):
        for field in ['jurisdiction','as_of']:
            for value in [None,1,True,[],{}]:
                p=fixture();p[field]=value
                self.refuses(p,'AGENCY1269:'+('TEXT' if field=='jurisdiction' else 'DATE'))
        for field in fixture():
            p=fixture();p['renamed_'+field]=p.pop(field)
            self.refuses(p,'AGENCY1269:SCHEMA')
    def test_source_and_every_item_exact_shapes(self):
        for collection in ['sources','records','pleadings','hearings','exhaustion','analysis']:
            for value in [None,1,'x',[],{}]:
                p=fixture();p[collection][0]=value;self.refuses(p,'AGENCY1269:SCHEMA')
            for field in fixture()[collection][0]:
                p=fixture();item=p[collection][0];item['renamed_'+field]=item.pop(field)
                self.refuses(p,'AGENCY1269:SCHEMA')
        for value in [None,[],{},dict(label='tribunal',source_keys=['source-a'],extra=True)]:
            p=fixture();p['tribunal']=value;self.refuses(p,'AGENCY1269:SCHEMA')
    def test_every_echoed_text_validation(self):
        paths=[('jurisdiction',),('tribunal','label'),('sources',0,'key'),('sources',0,'citation'),
               ('sources',0,'jurisdiction'),('sources',0,'url'),('assertions',0)]
        for kind in ['records','pleadings','hearings','exhaustion']:
            paths += [(kind,0,'key'),(kind,0,'text')]
        paths += [('analysis',0,'text')]
        for path in paths:
            for value in ['', ' padded','padded ',None,1,True,[],{},'left\u00adright','left\u2060right']:
                with self.subTest(path=path,value=repr(value)):
                    p=fixture();node=p
                    for key in path[:-1]:node=node[key]
                    node[path[-1]]=value;self.refuses(p,'AGENCY1269:TEXT')
    def test_every_reference_bound_text_and_unknown_code(self):
        paths=[('tribunal','source_keys')]+[(kind,0,'source_keys') for kind in ['records','pleadings','hearings','exhaustion','analysis']]
        for path in paths:
            for value,code in [(None,'BOUND'),({},'BOUND'),('source-a','BOUND'),([], 'BOUND'),(['source-a']*129,'BOUND'),([None],'TEXT'),([1],'TEXT'),([''],'TEXT'),([' padded'],'TEXT'),(['source-a']*2,'REFS'),(['missing'],'SOURCE_REF')]:
                with self.subTest(path=path,value=repr(value)):
                    p=fixture();node=p
                    for key in path[:-1]:node=node[key]
                    node[path[-1]]=value;self.refuses(p,'AGENCY1269:'+code)
        for kind in ['pleadings','hearings']:
            p=fixture();p[kind][0]['record_keys']=['missing'];self.refuses(p,'AGENCY1269:RECORD_REF')
    def test_every_container_bound_before_iteration(self):
        for field in ['sources','records','pleadings','hearings','exhaustion','assertions','analysis']:
            for value in [None,{},'',1,True]:
                p=fixture();p[field]=value;self.refuses(p,'AGENCY1269:BOUND')
            p=fixture();p[field]=p[field]*129;self.refuses(p,'AGENCY1269:BOUND')
    def test_source_keys_and_typed_item_duplicates(self):
        for kind in ['sources','records','pleadings','hearings','exhaustion']:
            p=fixture();p[kind]*=2;self.refuses(p,'AGENCY1269:DUPLICATE')
    def test_all_url_cases_exact(self):
        for url in ['http://example.org/a','ftp://example.org/a','https:example.org','https://',
                    'https://u:p@example.org','https://u@example.org','https://@example.org',
                    'https://:p@example.org','https://[x/a']:
            p=fixture();p['sources'][0]['url']=url;self.refuses(p,'AGENCY1269:URL')
        for url in ['https://example.org','HTTPS://example.org']:
            p=fixture();p['sources'][0]['url']=url;self.assertEqual(1269,self.call(p)['row_id'])
    def test_all_date_slots_exact_weekdate_and_lengths(self):
        for path in [('as_of',),('sources',0,'checked_on'),('hearings',0,'on')]:
            for value in ['2026-W41-1','20261011','2026-10-1','2026-10-110',None,1,True,[],{},'2026-02-30']:
                p=fixture();node=p
                for key in path[:-1]:node=node[key]
                node[path[-1]]=value;self.refuses(p,'AGENCY1269:DATE')
    def test_exhaustion_states_exact_and_no_decision(self):
        for value in [None,1,True,[],{},'', 'done','declared_done ']:
            p=fixture();p['exhaustion'][0]['state']=value;self.refuses(p,'AGENCY1269:STATE')
        for state in ['declared_done','declared_pending','unknown']:
            p=fixture();p['exhaustion'][0]['state']=state;o=self.call(p)
            self.assertEqual(['step-a'] if state=='unknown' else [],o['unknown_exhaustion_steps'])
            self.assertIsNone(o['exhaustion_decision'])
    def test_every_output_flag_exact_and_clean_boundary(self):
        p=fixture();p['hearings'][0]['on']=p['as_of'];o=self.call(p)
        self.assertEqual('review_required',o['status']);self.assertEqual([],o['future_hearing_keys'])
        self.assertIs(o['authority_verified'],False);self.assertIs(o['external_effect'],False)
        self.assertIs(o['requires_counsel_review'],True);self.assertIsNone(o['exhaustion_decision'])
        self.assertEqual('caller_supplied_unverified',o['evidence_status'])
        self.assertEqual(module.BOUNDARY,o['boundary'])
        self.assertEqual([],o['jurisdiction_mismatches']);self.assertEqual([],o['stale_source_keys'])
        self.assertEqual([],o['unreferenced_record_keys'])
        for field,value in [('jurisdiction','other'),('checked_on','2026-10-09')]:
            p=fixture();p['hearings']=[];p['sources'][0][field]=value;o=self.call(p)
            self.assertEqual('needs_review',o['status'])
        p=fixture();p['hearings'][0]['on']='2026-10-12';o=self.call(p)
        self.assertEqual('needs_review',o['status']);self.assertEqual(['hearing-a'],o['future_hearing_keys'])
        p=fixture();p['records'].append(dict(key='unused',text='Declared unused record',source_keys=['source-a']))
        self.assertEqual(['unused'],self.call(p)['unreferenced_record_keys'])

    def test_shape_refuses_str_subclass_keys(self):
        class Key(str):pass
        for path in [(),('tribunal',),('sources',0),('records',0),('pleadings',0),('hearings',0),('exhaustion',0),('analysis',0)]:
            p=fixture();node=p
            for key in path:node=node[key]
            key=next(iter(node));value=node.pop(key);node[Key(key)]=value
            self.refuses(p,'AGENCY1269:SCHEMA')
    def test_state_raw_cap_precedes_hash(self):
        p=fixture();p['exhaustion'][0]['state']='x'*2049
        self.refuses(p,'AGENCY1269:STATE')
        class State(str):
            def __hash__(self):raise AssertionError('subclass state hashed')
        p=fixture();p['exhaustion'][0]['state']=State('declared_done')
        self.refuses(p,'AGENCY1269:STATE')

class Key(str):
    pass

class RecordReferencePins(unittest.TestCase):
    def refuses(self, p, code):
        with self.assertRaises(module.AgencyProceedingsError) as c:
            module.organize(p)
        self.assertEqual('AGENCY1269:' + code, str(c.exception))

    def test_record_keys_family_exact_refusals(self):
        for kind in ('pleadings', 'hearings'):
            cases = [(None, 'BOUND'), ('record-a', 'BOUND'), (('record-a',), 'BOUND'), ({'record-a'}, 'BOUND'), ([], 'BOUND'),
                     (['record-a'] * 129, 'BOUND'),
                     ([''], 'TEXT'), ([' record-a'], 'TEXT'), (['record-a '], 'TEXT'), ([None], 'TEXT'), ([1], 'TEXT'),
                     (['r\u00ad1'], 'TEXT'), (['r\u20601'], 'TEXT'), (['r\n1'], 'TEXT'), (['r\u20281'], 'TEXT'),
                     ([Key('record-a')], 'TEXT'), (['x' * 2049], 'TEXT'),
                     (['record-a', 'record-a'], 'REFS'), (['record-a', 'zz'], 'RECORD_REF'), (['zz'], 'RECORD_REF')]
            for value, code in cases:
                with self.subTest(kind=kind, value=repr(value)[:40]):
                    p = fixture(); p[kind][0]['record_keys'] = value
                    self.refuses(p, code)
            p = fixture(); p[kind][0]['record_keys'] = ['record-a'] * 1
            module.organize(p)

    def test_schema_key_type_checked_before_any_key_hashing(self):
        calls = []
        class Spy(str):
            def __hash__(self):
                calls.append(1); return str.__hash__(self)
        for path in ((), ('tribunal',), ('sources', 0), ('records', 0), ('pleadings', 0), ('hearings', 0), ('exhaustion', 0), ('analysis', 0)):
            with self.subTest(path=path):
                p = fixture(); t = p
                for k in path: t = t[k]
                name = next(iter(t)); val = t.pop(name); t[Spy(name)] = val
                del calls[:]
                self.refuses(p, 'SCHEMA')
                self.assertEqual([], calls)

if __name__=='__main__':unittest.main()

