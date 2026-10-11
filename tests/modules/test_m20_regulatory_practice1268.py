"""Row 1268 Regulatory Practice: bounded declared obligation mapping, hermetic stdlib tests."""
import copy
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/regulatory_practice1268.py'
s = importlib.util.spec_from_file_location('regpractice1268', PATH)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)

BASE = {
    'jurisdiction': 'Example Jurisdiction',
    'as_of': '2026-06-01',
    'activities': [
        {'id': 'A1', 'text': 'Store sample records', 'rule_ids': ['R1', 'R2']},
        {'id': 'A2', 'text': 'Ship sample goods', 'rule_ids': ['R3']},
        {'id': 'A3', 'text': 'Unmapped sample activity', 'rule_ids': []},
    ],
    'rules': [
        {'id': 'R1', 'regulator': 'Example Agency', 'rule_text_ref': 'Example Code 1.1', 'effective_date': '2025-01-01'},
        {'id': 'R2', 'regulator': 'Example Agency', 'rule_text_ref': 'Example Code 1.2', 'effective_date': '2027-01-01'},
        {'id': 'R3', 'regulator': 'Example Board', 'rule_text_ref': 'Example Rule 9', 'effective_date': '2020-01-01', 'end_date': '2026-01-01'},
        {'id': 'R4', 'regulator': 'Example Board', 'rule_text_ref': 'Example Rule 10', 'effective_date': '2020-01-01'},
    ],
    'controls': [
        {'id': 'C1', 'rule_id': 'R1', 'evidence_ref': 'evidence-001'},
        {'id': 'C2', 'rule_id': 'R1', 'evidence_ref': 'evidence-002'},
        {'id': 'C3', 'rule_id': 'R3', 'evidence_ref': 'evidence-003'},
    ],
}


def run(d=None, **kw):
    d = copy.deepcopy(BASE if d is None else d)
    d.update(kw)
    return m.map_regulatory_obligations(d)


class Mapping(unittest.TestCase):
    def test_effectiveness_exact(self):
        out = run()
        eff = {r['id']: r['effectiveness'] for r in out['rules']}
        self.assertEqual(eff, {'R1': 'in_effect', 'R2': 'not_yet_effective', 'R3': 'ended', 'R4': 'in_effect'})

    def test_effective_boundaries(self):
        d = copy.deepcopy(BASE)
        d['as_of'] = '2025-01-01'   # effective_date is inclusive
        self.assertEqual({r['id']: r['effectiveness'] for r in run(d)['rules']}['R1'], 'in_effect')
        d['as_of'] = '2024-12-31'
        self.assertEqual({r['id']: r['effectiveness'] for r in run(d)['rules']}['R1'], 'not_yet_effective')
        d['as_of'] = '2026-01-01'   # end_date is exclusive
        self.assertEqual({r['id']: r['effectiveness'] for r in run(d)['rules']}['R3'], 'ended')
        d['as_of'] = '2025-12-31'
        self.assertEqual({r['id']: r['effectiveness'] for r in run(d)['rules']}['R3'], 'in_effect')

    def test_controls_linked_sorted(self):
        out = run()
        r1 = [r for r in out['rules'] if r['id'] == 'R1'][0]
        self.assertEqual(r1['control_ids'], ['C1', 'C2'])
        self.assertEqual(r1['control_evidence_refs'], ['evidence-001', 'evidence-002'])

    def test_findings_exact(self):
        f = run()['findings']
        self.assertEqual(f['activities_without_rules'], ['A3'])
        self.assertEqual(f['rules_without_control_evidence'], ['R2', 'R4'])
        self.assertEqual(f['rules_without_activities'], ['R4'])
        self.assertEqual(f['rules_not_in_effect_at_as_of'], ['R2', 'R3'])
        self.assertEqual(f['activities_touching_rules_not_in_effect'], ['A1', 'A2'])

    def test_order_independent(self):
        d = copy.deepcopy(BASE)
        d['rules'].reverse(); d['activities'].reverse(); d['controls'].reverse()
        self.assertEqual(run(d)['findings'], run()['findings'])
        self.assertEqual(run(d)['provenance_sha256'], run()['provenance_sha256'])

    def test_provenance_hash_changes_with_input(self):
        d = copy.deepcopy(BASE); d['rules'][0]['rule_text_ref'] = 'Example Code 1.9'
        self.assertNotEqual(run(d)['provenance_sha256'], run()['provenance_sha256'])
        self.assertRegex(run()['provenance_sha256'], r'^[0-9a-f]{64}$')

    def test_provenance_hash_covers_controls(self):
        d = copy.deepcopy(BASE); d['controls'][0]['evidence_ref'] = 'evidence-999'
        self.assertNotEqual(run(d)['provenance_sha256'], run()['provenance_sha256'])

    def test_controls_optional(self):
        d = copy.deepcopy(BASE); del d['controls']
        self.assertEqual(run(d)['findings']['rules_without_control_evidence'], ['R1', 'R2', 'R3', 'R4'])

    def test_never_certifies(self):
        out = run()
        self.assertIs(out['compliance_certified'], False)
        self.assertIs(out['rule_text_verified'], False)
        self.assertIs(out['control_evidence_verified'], False)
        self.assertIs(out['legal_conclusion'], None)
        self.assertIs(out['counsel_review_required'], True)
        self.assertEqual(out['status'], 'declared_input_bookkeeping_only')
        self.assertEqual(out['boundary'], m.BOUNDARY)
        self.assertIn('not legal advice', m.BOUNDARY)

    def test_clean_input_still_not_certified(self):
        d = {'jurisdiction': 'J', 'as_of': '2026-06-01',
             'activities': [{'id': 'A', 'text': 't', 'rule_ids': ['R']}],
             'rules': [{'id': 'R', 'regulator': 'g', 'rule_text_ref': 'x', 'effective_date': '2020-01-01'}],
             'controls': [{'id': 'C', 'rule_id': 'R', 'evidence_ref': 'e'}]}
        out = run(d)
        self.assertEqual(out['findings'], {k: [] for k in out['findings']})
        self.assertIs(out['compliance_certified'], False)

    def test_input_not_mutated_or_aliased(self):
        d = copy.deepcopy(BASE); snap = copy.deepcopy(d)
        out = m.map_regulatory_obligations(d)
        self.assertEqual(d, snap)
        out['rules'][0]['id'] = 'ZZ'
        self.assertEqual(d, snap)


def refuses(t, data, msg):
    with t.assertRaisesRegex(ValueError, '^REGULA1268: ' + msg + '$') as cm:
        m.map_regulatory_obligations(data)
    t.assertEqual(cm.exception.code, 'REGULA1268')


class Refusals(unittest.TestCase):
    def test_shape(self):
        for v in (None, [], (), 1, 'x'):
            with self.subTest(v=v):
                refuses(self, v, 'input must be an object')

    def test_unknown_and_missing(self):
        refuses(self, dict(copy.deepcopy(BASE), note='x'), 'unknown top-level field present')
        d = copy.deepcopy(BASE); del d['rules']
        refuses(self, d, 'missing required top-level field')
        d = copy.deepcopy(BASE); d['rules'][0]['extra'] = 1
        refuses(self, d, 'unknown rule field present')
        d = copy.deepcopy(BASE); del d['rules'][0]['regulator']
        refuses(self, d, 'missing required rule field')
        d = copy.deepcopy(BASE); d['activities'][0]['extra'] = 1
        refuses(self, d, 'unknown activity field present')
        d = copy.deepcopy(BASE); d['controls'][0]['extra'] = 1
        refuses(self, d, 'unknown control field present')

    def test_non_string_keys(self):
        d = copy.deepcopy(BASE); del d['controls']; d[1] = 'x'   # 5 keys: within the key-count cap
        refuses(self, d, 'field names must be strings')
        d = copy.deepcopy(BASE); d['rules'][0][1] = 'x'   # 5 keys: within the rule key-count cap
        refuses(self, d, 'field names must be strings')

    def test_as_of(self):
        for v in (None, 20260601, '2026-6-1', '2026-13-01', '', '2026-06-01T00:00', ' 2026-06-01'):
            with self.subTest(v=v):
                refuses(self, dict(copy.deepcopy(BASE), as_of=v), 'as_of must be an ISO date YYYY-MM-DD')

    def test_dates_on_rules(self):
        d = copy.deepcopy(BASE); d['rules'][0]['effective_date'] = 'soon'
        refuses(self, d, 'rule dates must be ISO dates YYYY-MM-DD')
        d = copy.deepcopy(BASE); d['rules'][2]['end_date'] = '2019-01-01'
        refuses(self, d, 'rule end_date must be after effective_date')
        d = copy.deepcopy(BASE); d['rules'][2]['end_date'] = '2020-01-01'
        refuses(self, d, 'rule end_date must be after effective_date')

    def test_text_fields(self):
        for bad in (None, '', '   ', 5, 'a' * 501, 'a\x00b', 'a\nb', 'a\u202eb', 'a\u200bb', 'a\u2028b'):
            with self.subTest(bad=bad):
                d = copy.deepcopy(BASE); d['jurisdiction'] = bad
                refuses(self, d, 'text fields must be 1..500 characters without control, bidi or format characters')
                d = copy.deepcopy(BASE); d['rules'][0]['regulator'] = bad
                refuses(self, d, 'text fields must be 1..500 characters without control, bidi or format characters')

    def test_text_boundary_500_ok(self):
        d = copy.deepcopy(BASE); d['jurisdiction'] = 'a' * 500
        self.assertEqual(run(d)['jurisdiction'], 'a' * 500)

    def test_ids(self):
        for bad in (None, '', 5, 'has space', 'a' * 65, 'x\n', 'é'):
            with self.subTest(bad=bad):
                d = copy.deepcopy(BASE); d['rules'][3]['id'] = bad
                refuses(self, d, r'ids must match \[A-Za-z0-9_.-\]\{1,64\}')
        d = copy.deepcopy(BASE); d['rules'][3]['id'] = 'a' * 64
        self.assertIn('a' * 64, [r['id'] for r in run(d)['rules']])

    def test_duplicate_ids(self):
        d = copy.deepcopy(BASE); d['rules'][1]['id'] = 'R1'
        refuses(self, d, 'duplicate rule id')
        d = copy.deepcopy(BASE); d['activities'][1]['id'] = 'A1'
        refuses(self, d, 'duplicate activity id')
        d = copy.deepcopy(BASE); d['controls'][1]['id'] = 'C1'
        refuses(self, d, 'duplicate control id')

    def test_dangling_references(self):
        d = copy.deepcopy(BASE); d['activities'][0]['rule_ids'] = ['R1', 'NOPE']
        refuses(self, d, 'activity rule_ids reference an unknown rule')
        d = copy.deepcopy(BASE); d['controls'][0]['rule_id'] = 'NOPE'
        refuses(self, d, 'control rule_id references an unknown rule')

    def test_rule_ids_shape(self):
        for bad in (None, 'R1', ('R1',), [1], ['R1', 'R1']):
            with self.subTest(bad=bad):
                d = copy.deepcopy(BASE); d['activities'][0]['rule_ids'] = bad
                refuses(self, d, 'activity rule_ids must be a list of unique rule ids')

    def test_collection_types_and_caps(self):
        for key in ('activities', 'rules'):
            for bad in (None, (), {}, 'x', [], [1], [None]):
                with self.subTest(key=key, bad=bad):
                    d = copy.deepcopy(BASE); d[key] = bad
                    refuses(self, d, key + ' must be a list of 1..' + str(m.MAX_ITEMS) + ' objects')
        for bad in (None, (), {}, 'x', [1]):
            with self.subTest(controls=bad):
                d = copy.deepcopy(BASE); d['controls'] = bad
                refuses(self, d, 'controls must be a list of 0..' + str(m.MAX_ITEMS) + ' objects')

    def test_cap_checked_before_iteration(self):
        class Boom(dict):
            def items(self): raise AssertionError('iterated before cap')
        d = copy.deepcopy(BASE)
        d['rules'] = [{'id': 'R%d' % i, 'regulator': 'g', 'rule_text_ref': 'x', 'effective_date': '2020-01-01'} for i in range(m.MAX_ITEMS + 1)]
        refuses(self, d, 'rules must be a list of 1..' + str(m.MAX_ITEMS) + ' objects')
        d = copy.deepcopy(BASE)
        d['rules'] = [{'id': 'R%d' % i, 'regulator': 'g', 'rule_text_ref': 'x', 'effective_date': '2020-01-01'} for i in range(m.MAX_ITEMS)]
        d['activities'] = [{'id': 'A', 'text': 't', 'rule_ids': []}]
        d['controls'] = []
        self.assertEqual(len(run(d)['rules']), m.MAX_ITEMS)

    def test_rule_ids_cap(self):
        d = copy.deepcopy(BASE)
        d['rules'] = [{'id': 'R%d' % i, 'regulator': 'g', 'rule_text_ref': 'x', 'effective_date': '2020-01-01'} for i in range(m.MAX_ITEMS)]
        d['activities'] = [{'id': 'A', 'text': 't', 'rule_ids': ['R%d' % i for i in range(m.MAX_ITEMS)]}]
        d['controls'] = []
        self.assertEqual(len(run(d)['activities'][0]['rule_ids']), m.MAX_ITEMS)

    def test_rule_ids_over_cap_refused_with_exact_reason(self):
        d = copy.deepcopy(BASE)
        d['activities'][0]['rule_ids'] = ['X%d' % i for i in range(m.MAX_ITEMS + 1)]
        refuses(self, d, 'activity rule_ids must be a list of unique rule ids')

    def test_refusals_do_not_echo_caller_content(self):
        secret = 'SECRET-CALLER-TEXT'
        d = copy.deepcopy(BASE); d['rules'][0][secret] = 1
        with self.assertRaises(ValueError) as cm: m.map_regulatory_obligations(d)
        self.assertNotIn(secret, str(cm.exception))
        d = copy.deepcopy(BASE); d['activities'][0]['rule_ids'] = [secret]
        with self.assertRaises(ValueError) as cm: m.map_regulatory_obligations(d)
        self.assertNotIn(secret, str(cm.exception))

    def test_bool_and_subclass_rejected(self):
        class S(str): pass
        d = copy.deepcopy(BASE); d['jurisdiction'] = S('x')
        refuses(self, d, 'text fields must be 1..500 characters without control, bidi or format characters')
        class D(dict): pass
        refuses(self, D(copy.deepcopy(BASE)), 'input must be an object')


class UnicodePins(unittest.TestCase):
    MSG = 'text fields must be 1..500 characters without control, bidi or format characters'

    def test_soft_hyphen_u00ad_refused(self):
        for field_path in (('jurisdiction',), ('rules', 0, 'regulator'), ('controls', 0, 'evidence_ref')):
            d = copy.deepcopy(BASE); t = d
            for k in field_path[:-1]: t = t[k]
            t[field_path[-1]] = 'a\u00adb'
            refuses(self, d, self.MSG)

    def test_word_joiner_u2060_refused(self):
        d = copy.deepcopy(BASE); d['activities'][0]['text'] = 'a\u2060b'
        refuses(self, d, self.MSG)

    def test_every_cf_codepoint_refused_in_this_python(self):
        import sys, unicodedata
        cf = [cp for cp in range(sys.maxunicode + 1) if unicodedata.category(chr(cp)) == 'Cf']
        self.assertIn(0xAD, cf); self.assertIn(0x2060, cf); self.assertGreater(len(cf), 100)
        for cp in cf:
            d = copy.deepcopy(BASE); d['jurisdiction'] = 'a' + chr(cp) + 'b'
            with self.assertRaises(ValueError, msg=hex(cp)):
                m.map_regulatory_obligations(d)

    def test_zl_zp_and_all_cc_refused(self):
        import sys, unicodedata
        bad = [cp for cp in range(sys.maxunicode + 1) if unicodedata.category(chr(cp)) in ('Cc', 'Zl', 'Zp')]
        for cp in bad:
            d = copy.deepcopy(BASE); d['jurisdiction'] = 'a' + chr(cp) + 'b'
            with self.assertRaises(ValueError, msg=hex(cp)):
                m.map_regulatory_obligations(d)

    def test_zs_accepted_inside_text(self):
        import sys, unicodedata
        zs = [cp for cp in range(sys.maxunicode + 1) if unicodedata.category(chr(cp)) == 'Zs']
        self.assertGreater(len(zs), 3)
        for cp in zs:
            d = copy.deepcopy(BASE); d['jurisdiction'] = 'a' + chr(cp) + 'b'
            self.assertEqual(run(d)['jurisdiction'], 'a' + chr(cp) + 'b', hex(cp))

    def test_lone_surrogate_cs_residual_accepted_and_disclosed(self):
        d = copy.deepcopy(BASE); d['jurisdiction'] = 'a\ud800b'
        out = run(d)
        self.assertEqual(out['jurisdiction'], 'a\ud800b')
        self.assertRegex(out['provenance_sha256'], r'^[0-9a-f]{64}$')
        doc = (Path(__file__).resolve().parents[2] / 'docs/M20_REGULATORY_PRACTICE1268_CONTRACT.md').read_text()
        self.assertIn('Lone', doc); self.assertIn('surrogates (Cs) are accepted', doc.replace('\n', ' '))


class GatePins(unittest.TestCase):
    """Review pins: unknown root field under the key cap, end_date present vs absent, ensure_ascii hash."""

    def test_root_unknown_field_under_key_cap_refused_exactly(self):
        d = copy.deepcopy(BASE); del d['controls']; d['unreviewed'] = 1   # 5 keys: not over the cap
        self.assertEqual(len(d), 5)
        refuses(self, d, 'unknown top-level field present')

    def test_end_date_present_vs_absent_echo_hash_and_effectiveness(self):
        d = copy.deepcopy(BASE)
        by = {r['id']: r for r in run(d)['rules']}
        self.assertEqual(by['R3']['end_date'], '2026-01-01')
        self.assertIsNone(by['R1']['end_date'])
        self.assertEqual(by['R3']['effectiveness'], 'ended')
        h_with = run(d)['provenance_sha256']
        d2 = copy.deepcopy(BASE); del d2['rules'][2]['end_date']
        out2 = run(d2)
        self.assertIsNone({r['id']: r for r in out2['rules']}['R3']['end_date'])
        self.assertEqual({r['id']: r for r in out2['rules']}['R3']['effectiveness'], 'in_effect')
        self.assertNotEqual(out2['provenance_sha256'], h_with)

    def _expected_hash(self, jurisdiction, ensure_ascii):
        import hashlib, json
        canon = {'jurisdiction': jurisdiction, 'as_of': '2026-06-01',
                 'activities': [{'id': 'A', 'text': 't', 'rule_ids': ['R']}],
                 'rules': [{'id': 'R', 'regulator': 'g', 'rule_text_ref': 'x',
                            'effective_date': '2020-01-01', 'end_date': None}],
                 'controls': []}
        raw = json.dumps(canon, sort_keys=True, ensure_ascii=ensure_ascii, separators=(',', ':'))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _min(self, jurisdiction):
        return {'jurisdiction': jurisdiction, 'as_of': '2026-06-01',
                'activities': [{'id': 'A', 'text': 't', 'rule_ids': ['R']}],
                'rules': [{'id': 'R', 'regulator': 'g', 'rule_text_ref': 'x', 'effective_date': '2020-01-01'}]}

    def test_non_ascii_jurisdiction_accepted_and_hash_uses_ensure_ascii_true(self):
        j = 'caf\u00e9'
        out = m.map_regulatory_obligations(self._min(j))
        self.assertEqual(out['jurisdiction'], j)
        self.assertEqual(out['provenance_sha256'], self._expected_hash(j, True))
        self.assertNotEqual(out['provenance_sha256'], self._expected_hash(j, False))

    def test_cs_escape_hash_pinned_ensure_ascii_true(self):
        j = 'a\ud800b'   # lone surrogate (Cs): accepted residual, hashed as an escape
        out = m.map_regulatory_obligations(self._min(j))
        self.assertEqual(out['jurisdiction'], j)
        self.assertEqual(out['provenance_sha256'], self._expected_hash(j, True))


class OrderPins(unittest.TestCase):
    """Cap-first ordering: raw length/key-count checks precede strip, key-type scan and Unicode scan."""

    def _profile_calls(self, fn):
        import sys
        names = []
        def prof(frame, event, arg):
            if event == 'c_call':
                names.append(getattr(arg, '__name__', ''))
        sys.setprofile(prof)
        try:
            fn()
        except ValueError:
            pass
        finally:
            sys.setprofile(None)
        return names

    def test_over_cap_text_refused_before_strip_or_unicode_scan(self):
        for bad in ('a' * 501, ' ' * 501, 'a' * 500 + ' '):
            d = copy.deepcopy(BASE); d['jurisdiction'] = bad
            names = self._profile_calls(lambda: m.map_regulatory_obligations(d))
            self.assertNotIn('strip', names, 'strip ran before the raw cap')
            self.assertNotIn('category', names, 'Unicode scan ran before the raw cap')
            refuses(self, d, 'text fields must be 1..500 characters without control, bidi or format characters')

    def test_top_level_key_count_before_key_type_scan(self):
        d = copy.deepcopy(BASE); d[1] = 'x'   # 6 keys > 5 allowed
        refuses(self, d, 'unknown top-level field present')

    def test_container_key_count_before_key_type_scan(self):
        for coll, label, extra in (('rules', 'rule', {'end_date': '2030-01-01'}),
                                   ('activities', 'activity', {}), ('controls', 'control', {})):
            d = copy.deepcopy(BASE); d[coll][0][1] = 'x'; d[coll][0].update(extra)
            n_allowed = {'rules': 5, 'activities': 3, 'controls': 3}[coll]
            self.assertGreater(len(d[coll][0]), n_allowed)
            refuses(self, d, 'unknown ' + label + ' field present')

    def test_oversized_key_dict_not_scanned(self):
        d = copy.deepcopy(BASE)
        for i in range(2000): d['rules'][0][i] = 'x'
        names = self._profile_calls(lambda: m.map_regulatory_obligations(d))
        self.assertLess(len(names), 400)
        refuses(self, d, 'unknown rule field present')


if __name__ == '__main__':
    unittest.main()
