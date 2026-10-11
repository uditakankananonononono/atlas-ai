"""S3.4 bounded supplied-taxonomy coverage; no source URLs fetched."""
import copy
import importlib.util
import os
import itertools
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
PATH = pathlib.Path(os.environ.get('S34_MODULE_PATH', ROOT / 'backend/app/modules/c34/industry.py'))
spec = importlib.util.spec_from_file_location('s34_test_target', PATH)
industry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(industry)


def request():
    return {'taxonomy': [
        {'code': 'R', 'name': 'Primary sector', 'parent': None},
        {'code': 'A', 'name': 'Agriculture', 'parent': 'R'},
        {'code': 'B', 'name': 'Construction', 'parent': 'R'},
        {'code': 'A1', 'name': 'Soil sensors', 'parent': 'A'},
        {'code': 'A2', 'name': 'Seed handling', 'parent': 'A'},
        {'code': 'B1', 'name': 'Building repair', 'parent': 'B'}],
        'touched': [{'code': 'A1', 'unit_id': 'U1', 'evidence': 'supplied blueprint'}],
        'needs': [{'id': 'n1', 'text': 'soil repair', 'codes': ['A1', 'B1'],
                   'severity': .8, 'evidence_url': 'https://example.invalid/n1'},
                  {'id': 'n2', 'text': 'seed repair', 'codes': ['A2'],
                   'severity': .5, 'evidence_url': ''}],
        'capabilities': [{'id': 'c1', 'text': 'soil sensor design'}],
        'min_gap_severity': .5}


class CoverageTests(unittest.TestCase):
    def refusal(self, data, code):
        with self.assertRaises(ValueError) as cm:
            industry.run(data)
        self.assertEqual(str(cm.exception), code)

    def test_ancestor_rollup_leaf_direct(self):
        out = industry.run(request())
        self.assertEqual(out['direct_touched_codes'], ['A1'])
        self.assertEqual(out['rolled_touched_codes'], ['A', 'A1', 'R'])
        self.assertEqual(out['levels'], [
            {'depth': 0, 'touched': 1, 'total': 1, 'coverage_percent': 100.0},
            {'depth': 1, 'touched': 1, 'total': 2, 'coverage_percent': 50.0},
            {'depth': 2, 'touched': 1, 'total': 3, 'coverage_percent': 33.3}])
        self.assertEqual(out['leaf_coverage'], {'touched': 1, 'total': 3, 'coverage_percent': 33.3})
        self.assertEqual(out['ancestor_coverage'][0],
                         {'code': 'A', 'touched': 2, 'total': 3, 'coverage_percent': 66.7})

    def test_direct_ancestor_does_not_touch_descendants(self):
        data = request(); data['touched'] = [{'code': 'R', 'unit_id': 'x', 'evidence': 'e'}]
        out = industry.run(data)
        self.assertEqual(out['rolled_touched_codes'], ['R'])
        self.assertEqual(out['leaf_coverage']['touched'], 0)

    def test_partial_gap_fraction_and_missing_evidence(self):
        out = industry.run(request())
        gaps = out['gaps']
        self.assertEqual([g['id'] for g in gaps], ['n2', 'n1'])
        self.assertEqual(gaps[0]['gap_score'], .5)
        self.assertEqual(gaps[1]['gap_score'], .4)
        self.assertEqual(gaps[1]['status'], 'partial_gap')
        self.assertEqual(gaps[1]['touched_codes'], ['A1'])
        self.assertEqual(gaps[1]['untouched_codes'], ['B1'])
        self.assertEqual(out['excluded_candidate_needs'], [{'id': 'n2', 'code': 'PROTO_REFUSED_NOSOURCE'}])
        self.assertIn('supplied taxonomy only', out['coverage_basis'])
        self.assertFalse(out['source_evidence_verified'])

    def test_inclusive_threshold_fully_touched_not_gap(self):
        data = request();data['needs'][0]['codes']=['A1'];data['min_gap_severity']=.5
        self.assertEqual([g['id'] for g in industry.run(data)['gaps']], ['n2'])
        data['min_gap_severity']=.500001
        self.assertEqual(industry.run(data)['gaps'], [])

    def test_multiple_touch_evidence_not_double_counted(self):
        data = request();data['touched'] *= 2
        self.assertEqual(industry.run(data)['levels'][2]['touched'], 1)

    def test_untouched_order_need_count_then_code(self):
        data=request();data['needs'].append({'id':'n3','text':'another seed need','codes':['A2'],'severity':1})
        rows=industry.run(data)['untouched']
        self.assertEqual([(r['code'],r['need_count']) for r in rows], [('A2',2),('B1',1),('B',0)])

    def test_permutations_determinism_and_no_mutation(self):
        original=request();before=copy.deepcopy(original);want=industry.run(original)
        self.assertEqual(original,before)
        for tax in (original['taxonomy'],list(reversed(original['taxonomy']))):
            for needs in itertools.permutations(original['needs']):
                d=copy.deepcopy(original);d['taxonomy']=tax;d['needs']=list(needs)
                self.assertEqual(json.dumps(industry.run(d),sort_keys=True),json.dumps(want,sort_keys=True))
        self.assertEqual(want['scope']['data_source'],'supplied taxonomy, touched references, needs and capabilities')
        self.assertEqual(want['scope']['as_of'],'supplied-input')
        original['as_of']='2026-10-11';self.assertEqual(industry.run(original)['scope']['as_of'],'2026-10-11')

    def test_fixture_60_codes_15_touched_20_needs(self):
        taxonomy=[{'code':f'r{i}','name':f'Root {i}','parent':None} for i in range(5)]
        taxonomy += [{'code':f'g{i}','name':f'Group {i}','parent':f'r{i//3}'} for i in range(15)]
        taxonomy += [{'code':f'l{i}','name':f'Leaf {i}','parent':f'g{i%15}'} for i in range(40)]
        d={'taxonomy':taxonomy,'touched':[{'code':f'l{i}','unit_id':f'U{i}','evidence':'e'} for i in range(15)],
           'needs':[{'id':f'n{i}','text':f'Need {i}','codes':[f'l{i}',f'l{i+20}'],'severity':.8,'evidence_url':'https://example.invalid'} for i in range(20)],
           'capabilities':[],'min_gap_severity':.5}
        out=industry.run(d)
        self.assertEqual(out['levels'],[{'depth':0,'touched':5,'total':5,'coverage_percent':100.0},
            {'depth':1,'touched':15,'total':15,'coverage_percent':100.0},
            {'depth':2,'touched':15,'total':40,'coverage_percent':37.5}])
        self.assertEqual(len(out['gaps']),20)
        self.assertEqual(sum(g['status']=='partial_gap' for g in out['gaps']),15)

    def test_independent_subset_oracle(self):
        base=request()
        for bits in itertools.product((False,True),repeat=6):
            direct={row['code'] for row,b in zip(base['taxonomy'],bits) if b}
            d=copy.deepcopy(base);d['touched']=[{'code':c,'unit_id':'u','evidence':'e'} for c in direct]
            out=industry.run(d)
            parent={row['code']:row['parent'] for row in d['taxonomy']}
            expected=set(direct)
            for c in direct:
                while parent[c] is not None:
                    c=parent[c];expected.add(c)
            self.assertEqual(out['rolled_touched_codes'],sorted(expected))
            self.assertEqual(out['leaf_coverage']['touched'],len(direct & {'A1','A2','B1'}))

    def test_taxonomy_refusals(self):
        for val in (None,[],{},True):
            d=request();d['taxonomy']=val;self.refusal(d,'PROTO_REFUSED_NOTAXONOMY')
        d=request();d['taxonomy'][0]['parent']='A';self.refusal(d,'PROTO_REFUSED_NOTAXONOMY:cycle')
        d=request();d['taxonomy'][1]['parent']='unknown';self.refusal(d,'PROTO_REFUSED_NOTAXONOMY:parent')
        d=request();d['taxonomy'].append(d['taxonomy'][0]);self.refusal(d,'PROTO_REFUSED_NOTAXONOMY:duplicate')
        d=request();d['taxonomy'][0]['unknown']='x';self.refusal(d,'PROTO_REFUSED_BAD_TYPE:taxonomy_row')

    def test_input_refusals(self):
        self.refusal(None,'PROTO_REFUSED_BAD_TYPE:request')
        d=request();d['submit']=True;self.refusal(d,'PROTO_REFUSED_BAD_TYPE:request_fields')
        for field in ('touched','needs','capabilities'):
            d=request();d[field]={};self.refusal(d,'PROTO_REFUSED_BAD_TYPE:'+field)
        for value in (True,float('nan'),float('inf'),-.1,1.1):
            d=request();d['min_gap_severity']=value;self.refusal(d,'PROTO_REFUSED_BAD_TYPE:min_gap_severity')
            d=request();d['needs'][0]['severity']=value;self.refusal(d,'PROTO_REFUSED_BAD_TYPE:severity')
        d=request();d['touched'][0]['code']='unknown';self.refusal(d,'PROTO_REFUSED_NOTAXONOMY:touched_code')
        d=request();d['needs'][0]['codes']=['unknown'];self.refusal(d,'PROTO_REFUSED_NOTAXONOMY:need_code')
        d=request();d['needs'][0]['codes']=[];self.refusal(d,'PROTO_REFUSED_EMPTY:need_codes')
        d=request();d['needs'][0]['codes']=['A1','A1'];self.refusal(d,'PROTO_REFUSED_BAD_TYPE:need_codes')
        d=request();d['needs'][1]['id']='n1';self.refusal(d,'PROTO_REFUSED_BAD_TYPE:need_id')
        d=request();d['capabilities']*=2;self.refusal(d,'PROTO_REFUSED_BAD_TYPE:capability_id')

    def test_real_policy_hygiene_no_effect_surface(self):
        d=request();d['taxonomy'][0]['name']='bad\x00name';self.refusal(d,'PROTO_REFUSED_CONTROL_CHARS:name')
        d=request();d['taxonomy'][0]['name']=' ';self.refusal(d,'PROTO_REFUSED_EMPTY:name')
        public=[k for k,v in vars(industry).items() if callable(v) and not k.startswith('_')]
        self.assertEqual(public,['run'])
        self.assertEqual((ROOT/'backend/app/modules/c34/__init__.py').read_bytes(),b'')
        self.assertIs(industry.policy,sys.modules['app.modules.c30.policy'])
        self.assertIn('market validation or real new industries',industry.run(request())['scope']['not_implemented'])

    def test_full_set_containment_omit_not_refuse(self):
        d=request();d['needs']=[{'id':'n','text':'soil sensors repair','codes':['B1'],'severity':1,'evidence_url':'https://example.invalid'}]
        d['capabilities']=[{'id':'c','text':'soil sensor sensors design'}]
        out=industry.run(d)
        self.assertEqual(out['candidates'],[])
        self.assertEqual(out['omitted_candidates'][0]['code'],'OVERCLAIM')
        self.assertEqual(out['omitted_candidates'][0]['matched_taxonomy_codes'],['A1'])
        # One common word is not full containment in either direction.
        d['taxonomy'][3]['name']='soil chemistry'
        out=industry.run(d)
        self.assertEqual(len(out['candidates']),1)
        self.assertEqual(out['omitted_candidates'],[])
        self.assertFalse(out['candidates'][0]['novelty_verified'])
        self.assertFalse(out['candidates'][0]['industry_created'])
        self.assertEqual(out['candidates'][0]['shared_terms'],['sensors','soil'])

    def test_reverse_containment_and_no_empty_match(self):
        d=request();d['taxonomy'][0]['name']='soil sensor repair design agriculture'
        d['taxonomy'][3]['name']='the and of'
        d['needs']=[{'id':'n','text':'soil repair','codes':['B1'],'severity':1,'evidence_url':'https://example.invalid'}]
        d['capabilities']=[{'id':'c','text':'soil sensor design'}]
        out=industry.run(d)
        self.assertEqual(out['omitted_candidates'][0]['matched_taxonomy_codes'],['R'])
        d['taxonomy'][0]['name']='primary sector'
        self.assertEqual(len(industry.run(d)['candidates']),1)

    def test_missing_source_no_shared_terms_and_closed_gaps_no_candidates(self):
        d=request();d['taxonomy'][3]['name']='soil chemistry'
        d['needs'][0]['evidence_url']=' '
        self.assertEqual(industry.run(d)['candidates'],[])
        d['needs'][0]['evidence_url']='https://example.invalid'
        d['capabilities'][0]['text']='virtual games'
        self.assertEqual(industry.run(d)['candidates'],[])
        d['capabilities'][0]['text']='soil device'
        self.assertEqual(len(industry.run(d)['candidates']),1)
        d['needs'][0]['codes']=['A1']
        self.assertEqual(industry.run(d)['candidates'],[])

    def test_coverage_assertions_computed_only(self):
        for word in ('all','every','covered'):
            d=request();d['coverage_assertion']={'word':word,'coverage_percent':100}
            self.refusal(d,'PROTO_REFUSED_OVERCLAIM')
            d['coverage_assertion']['coverage_percent']=50.0
            self.assertEqual(industry.run(d)['coverage']['touched'],3)
        d=request();d['coverage_assertion']={'word':'best','coverage_percent':50}
        self.refusal(d,'PROTO_REFUSED_BAD_TYPE:coverage_assertion')
        d=request();d['coverage_assertion']={'word':'all','coverage_percent':True}
        self.refusal(d,'PROTO_REFUSED_BAD_TYPE:coverage_assertion')
        d=request();d['coverage_assertion']={'word':'all','coverage_percent':50,'extra':1}
        self.refusal(d,'PROTO_REFUSED_BAD_TYPE:coverage_assertion')

    def test_fraction_precision_and_large_numeric_refusal(self):
        d=request();d['needs'][0]['codes']=['A1','A2','B1']
        d['needs'][0]['severity']=.8
        self.assertEqual(industry.run(d)['gaps'][0]['gap_score'],.533333)
        d['needs'][0]['severity']=.800000001
        self.assertEqual(industry.run(d)['gaps'][0]['severity'],.8)
        for field in ('min_gap_severity','severity'):
            d=request()
            if field=='severity':d['needs'][0][field]=10**400
            else:d[field]=10**400
            self.refusal(d,'PROTO_REFUSED_BAD_TYPE:'+field)
        d=request();d['coverage_assertion']={'word':'all','coverage_percent':10**400}
        self.refusal(d,'PROTO_REFUSED_BAD_TYPE:coverage_assertion')

    def test_candidate_terms_are_name_terms(self):
        d=request();d['taxonomy'][3]['name']='soil chemistry'
        out=industry.run(d)['candidates'][0]
        self.assertEqual(out['key_terms'],sorted(industry._terms(out['name'])))

    def test_caps_and_canonical_json(self):
        d=request();d['taxonomy']=[{'code':str(i),'name':'node '+str(i),'parent':None} for i in range(1024)]
        d['touched']=[];d['needs']=[];d['capabilities']=[]
        self.assertEqual(industry.run(d)['coverage']['total'],1024)
        d['taxonomy'].append({'code':'x','name':'node x','parent':None})
        self.refusal(d,'PROTO_REFUSED_BAD_TYPE:taxonomy_size')
        for field,cap in [('needs',1024),('capabilities',256),('touched',4096)]:
            d=request();d[field]=[{}]*(cap+1)
            self.refusal(d,'PROTO_REFUSED_BAD_TYPE:'+field+'_size')
        d=request();d['taxonomy'][0]['name']='x'*256
        industry.run(d)
        d['taxonomy'][0]['name']='x'*257
        self.refusal(d,'PROTO_REFUSED_TEXT_TOO_LONG:name')
        out=industry.run(request())
        self.assertEqual(list(out),sorted(out))
        json.dumps(out,allow_nan=False,sort_keys=True)


class PinTests(CoverageTests):
    """S3.4 test-only repair: pins for the 42-survivor battery. Module frozen."""

    def tax(self, n):
        return [{'code': f'c{i}', 'name': f'node {i}', 'parent': None} for i in range(n)]

    def test_caps_exact_boundary_accepted(self):
        d = request()
        d['needs'] = [{'id': f'n{i}', 'text': 'soil', 'codes': ['A1'], 'severity': 0}
                      for i in range(1024)]
        d['capabilities'] = [{'id': f'c{i}', 'text': 'soil'} for i in range(256)]
        d['touched'] = [{'code': 'A1', 'unit_id': f'u{i}', 'evidence': 'e'}
                        for i in range(4096)]
        d['min_gap_severity'] = 0
        industry.run(d)
        for field, cap in (('needs', 1024), ('capabilities', 256), ('touched', 4096)):
            d = request(); d[field] = d.get(field, []) + [{}] * (cap + 1 - len(d.get(field, [])))
            self.refusal(d, 'PROTO_REFUSED_BAD_TYPE:' + field + '_size')

    def test_text_limits_exact_boundary(self):
        long128 = 'x' * 128
        d = request(); d['taxonomy'].append({'code': long128, 'name': 'extra', 'parent': None})
        industry.run(d)
        d = request(); d['taxonomy'].append({'code': 'x' * 129, 'name': 'extra', 'parent': None})
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:code')
        d = request(); d['taxonomy'][1]['parent'] = long128
        self.refusal(d, 'PROTO_REFUSED_NOTAXONOMY:parent')
        d = request(); d['taxonomy'][1]['parent'] = 'x' * 129
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:parent')
        d = request(); d['taxonomy'].append({'code': long128, 'name': 'n', 'parent': None})
        d['touched'] = [{'code': long128, 'unit_id': 'u', 'evidence': 'e'}]; industry.run(d)
        d['touched'] = [{'code': 'x' * 129, 'unit_id': 'u', 'evidence': 'e'}]
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:code')
        d = request(); d['touched'][0]['unit_id'] = long128; industry.run(d)
        d['touched'][0]['unit_id'] = 'x' * 129
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:unit_id')
        d = request(); d['touched'][0]['evidence'] = 'x' * 2048; industry.run(d)
        d['touched'][0]['evidence'] = 'x' * 2049
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:evidence')
        d = request(); d['needs'][0]['id'] = long128; industry.run(d)
        d['needs'][0]['id'] = 'x' * 129
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:need_id')
        d = request(); d['needs'][0]['text'] = 'x' * 2048; industry.run(d)
        d['needs'][0]['text'] = 'x' * 2049
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:need_text')
        d = request(); d['needs'][0]['codes'] = ['A1', long128]
        self.refusal(d, 'PROTO_REFUSED_NOTAXONOMY:need_code')
        d = request(); d['needs'][0]['codes'] = ['A1', 'x' * 129]
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:need_code')
        d = request(); d['needs'][0]['evidence_url'] = 'x' * 2048; industry.run(d)
        d['needs'][0]['evidence_url'] = 'x' * 2049
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:evidence_url')
        d = request(); d['capabilities'][0]['id'] = long128; industry.run(d)
        d['capabilities'][0]['id'] = 'x' * 129
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:capability_id')
        d = request(); d['capabilities'][0]['text'] = 'x' * 2048; industry.run(d)
        d['capabilities'][0]['text'] = 'x' * 2049
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:capability_text')
        d = request(); d['as_of'] = long128; industry.run(d)
        d['as_of'] = 'x' * 129
        self.refusal(d, 'PROTO_REFUSED_TEXT_TOO_LONG:as_of')

    def test_severity_and_threshold_zero_and_one_accepted(self):
        for sev in (0, 1):
            d = request(); d['needs'][0]['severity'] = sev; d['min_gap_severity'] = 0
            industry.run(d)
        d = request(); d['min_gap_severity'] = 1
        self.assertEqual(industry.run(d)['gaps'], [])
        d = request(); d['needs'][0]['severity'] = 0; d['min_gap_severity'] = 0
        by_id = {g['id']: g for g in industry.run(d)['gaps']}
        self.assertEqual(by_id['n1']['gap_score'], 0.0)
        d = request(); d['needs'][0]['severity'] = 1
        by_id = {g['id']: g for g in industry.run(d)['gaps']}
        self.assertEqual(by_id['n1']['gap_score'], 0.5)

    def test_row_keysets_and_non_dict(self):
        for bad in ('x', {'code': 'A1', 'unit_id': 'u'},
                    {'code': 'A1', 'unit_id': 'u', 'evidence': 'e', 'extra': 1}):
            d = request(); d['touched'] = [bad]
            self.refusal(d, 'PROTO_REFUSED_BAD_TYPE:touched_row')
        for bad in ('x', {'id': 'n', 'text': 't', 'codes': ['A1']},
                    {'id': 'n', 'text': 't', 'codes': ['A1'], 'severity': 1, 'extra': 1}):
            d = request(); d['needs'] = [bad]
            self.refusal(d, 'PROTO_REFUSED_BAD_TYPE:need_row')
        for bad in ('x', {'id': 'c'}, {'id': 'c', 'text': 't', 'extra': 1}):
            d = request(); d['capabilities'] = [bad]
            self.refusal(d, 'PROTO_REFUSED_BAD_TYPE:capability_row')

    def test_equal_term_sets_match_and_omit(self):
        d = request()
        d['taxonomy'][0]['name'] = 'soil repair soil sensor design'
        d['needs'] = [{'id': 'n', 'text': 'soil repair', 'codes': ['B1'], 'severity': 1,
                       'evidence_url': 'https://example.invalid'}]
        d['capabilities'] = [{'id': 'c', 'text': 'soil sensor design'}]
        out = industry.run(d)
        self.assertEqual(out['candidates'], [])
        self.assertEqual(out['omitted_candidates'][0]['code'], 'OVERCLAIM')
        self.assertEqual(out['omitted_candidates'][0]['matched_taxonomy_codes'], ['R'])

    def test_candidate_physical_execution_false(self):
        d = request(); d['taxonomy'][3]['name'] = 'soil chemistry'
        cand = industry.run(d)['candidates'][0]
        self.assertIs(cand['physical_execution'], False)
        self.assertEqual(cand['kind'], 'keyword_recombination_draft')

    def test_canonical_round6_real_pin(self):
        d = request(); d['needs'][0]['severity'] = 0.12345674
        d['min_gap_severity'] = 0
        by_id = {g['id']: g for g in industry.run(d)['gaps']}
        self.assertEqual(by_id['n1']['severity'], 0.123457)

    def test_gap_score_round6_double_round_tiebreak(self):
        tax = [{'code': f'c{i}', 'name': f'node {i}', 'parent': None} for i in range(11)]
        d = {'taxonomy': tax,
             'touched': [{'code': 'c0', 'unit_id': 'u', 'evidence': 'e'},
                         {'code': 'c1', 'unit_id': 'u', 'evidence': 'e'}],
             'needs': [{'id': 'n', 'text': 'soil', 'codes': [f'c{i}' for i in range(11)],
                        'severity': 0.3}],
             'capabilities': [], 'min_gap_severity': 0}
        # 0.3*9/11 = 0.2454545...; round6 = 0.245455 (round7 path gives 0.245454)
        self.assertEqual(industry.run(d)['gaps'][0]['gap_score'], 0.245455)

    def test_coverage_zero_and_hundred_with_assertion(self):
        d = request(); d['touched'] = []
        out = industry.run(d)
        self.assertEqual(out['coverage']['coverage_percent'], 0.0)
        d['coverage_assertion'] = {'word': 'all', 'coverage_percent': 0}
        industry.run(d)
        d = request()
        d['touched'] = [{'code': c, 'unit_id': 'u', 'evidence': 'e'}
                        for c in ('R', 'A', 'B', 'A1', 'A2', 'B1')]
        out = industry.run(d)
        self.assertEqual(out['coverage']['coverage_percent'], 100.0)
        d['coverage_assertion'] = {'word': 'every', 'coverage_percent': 100}
        industry.run(d)
        d = request(); d['coverage_assertion'] = {'word': 'all', 'coverage_percent': 100.5}
        self.refusal(d, 'PROTO_REFUSED_BAD_TYPE:coverage_assertion')
        d = request(); d['coverage_assertion'] = {'word': 'all', 'coverage_percent': 101}
        self.refusal(d, 'PROTO_REFUSED_BAD_TYPE:coverage_assertion')


if __name__=='__main__':
    unittest.main(verbosity=2)
