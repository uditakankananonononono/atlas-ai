"""Row1267 new cap-order pins, hermetic runtime observations."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch

PATH = pathlib.Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/administrative_law1267.py'
spec = importlib.util.spec_from_file_location('row1267_caps', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class CapOrder1267Tests(unittest.TestCase):
    def test_raw_oversized_blank_cap_checked_before_strip(self):
        raw = ' ' * (module.MAX_TEXT + 1)
        seen = []
        def measured(value):
            seen.append(value)
            return len(value)
        with patch.object(module, 'len', measured, create=True):
            with self.assertRaisesRegex(ValueError, '^ADMINI1267:TEXT$'):
                module._text(raw)
        self.assertEqual(seen, [raw])

    def test_object_key_count_checked_before_set(self):
        raw = {'key-' + str(index): 'value' for index in range(201)}
        with patch.object(module, 'set', side_effect=AssertionError('set reached before cap'), create=True):
            with self.assertRaisesRegex(ValueError, '^ADMINI1267:SCHEMA$'):
                module._object(raw, ('required',))

    def test_object_specific_shape_cap_before_set(self):
        raw = {'required': 'value', 'unknown': 'value'}
        with patch.object(module, 'set', side_effect=AssertionError('set reached before shape cap'), create=True):
            with self.assertRaisesRegex(ValueError, '^ADMINI1267:SCHEMA$'):
                module._object(raw, ('required',))

    def test_refs_list_cap_before_scan_or_set(self):
        with patch.object(module, '_text', side_effect=AssertionError('scan before cap')):
            with self.assertRaisesRegex(ValueError, '^ADMINI1267:COLLECTION$'):
                module._refs(['value'] * 201)

    def test_text_raw_limit_is_inclusive(self):
        self.assertEqual(module._text('x' * 4000), 'x' * 4000)
        with self.assertRaisesRegex(ValueError, '^ADMINI1267:TEXT$'):
            module._text(' ' + 'x' * 4000)

    def test_nested_schema_uses_same_pre_set_guard(self):
        for required in (('source_label', 'observed_on'), ('id', 'text'),
                         ('id', 'domain', 'question', 'authority_refs', 'fact_refs', 'assertion_refs', 'analysis_refs')):
            raw = {key: 'value' for key in required}
            raw['extra'] = 'value'
            with patch.object(module, 'set', side_effect=AssertionError('nested set before cap'), create=True):
                with self.assertRaisesRegex(ValueError, '^ADMINI1267:SCHEMA$'):
                    module._object(raw, required)

class Unicode1267Tests(unittest.TestCase):
    def test_raw_unicode_categories_rejected_before_trim(self):
        for char in ('\x7f', '\x00', '\n', '\u00ad', '\u2060', '\u2028', '\u2029'):
            for raw in (char + 'plain', 'plain' + char, 'p' + char + 'lain'):
                with self.subTest(codepoint=ord(char), raw=repr(raw)):
                    with self.assertRaisesRegex(ValueError, '^ADMINI1267:TEXT$'):
                        module._text(raw)

    def test_entire_cf_category_not_selected_ranges(self):
        import unicodedata
        cf = [chr(code) for code in range(0x110000) if unicodedata.category(chr(code)) == 'Cf']
        self.assertIn('\u00ad', cf)
        self.assertIn('\u2060', cf)
        for char in cf:
            with self.subTest(codepoint=ord(char)):
                with self.assertRaisesRegex(ValueError, '^ADMINI1267:TEXT$'):
                    module._text('plain' + char)

    def test_zs_accepted_and_existing_trim_preserved(self):
        self.assertEqual(module._text('\u00a0plain\u2003'), 'plain')
        self.assertEqual(module._text('two\u2003words'), 'two\u2003words')

    def test_date_exact_raw_ten_before_any_generic_text_scan(self):
        for raw in ('x' * 4000, 'x' * 4001, '2026-1-01', '', '2026-10-11\u2060'):
            with patch.object(module, '_text', side_effect=AssertionError('generic scan reached')):
                with self.assertRaisesRegex(ValueError, '^ADMINI1267:DATE$'):
                    module._date(raw)

    def test_date_type_before_length_and_scan(self):
        for raw in (None, 42, True, [], {}):
            with patch.object(module, 'len', side_effect=AssertionError('length reached before type'), create=True):
                with self.assertRaisesRegex(ValueError, '^ADMINI1267:DATE$'):
                    module._date(raw)

    def test_date_all_malformed_exact_ten_map_to_date(self):
        for raw in ('2026-02-30', '2026/10/11', '2026-10-1\x7f', '2026-10-1\u2060', '2026-10-1\ud800'):
            with self.assertRaisesRegex(ValueError, '^ADMINI1267:DATE$'):
                module._date(raw)
        self.assertEqual(module._date('2026-10-11').isoformat(), '2026-10-11')

    def test_cs_residual_not_new_refusal(self):
        self.assertEqual(module._text('plain\ud800'), 'plain\ud800')

    def test_url_uses_uniform_text_screen(self):
        for char in ('\x7f', '\u00ad', '\u2060', '\u2028', '\u2029'):
            with self.assertRaisesRegex(ValueError, '^ADMINI1267:TEXT$'):
                module._url('https://example.invalid/' + char)

    def test_schema_keys_screened_after_count(self):
        with self.assertRaisesRegex(ValueError, '^ADMINI1267:TEXT$'):
            module._object({'bad\u2060key': 'value'}, ('required',))


def review_packet():
    return {
        'jurisdiction': 'Declared jurisdiction', 'as_of': '2026-10-11',
        'provenance': {'source_label': 'Declared packet', 'observed_on': '2026-10-11'},
        'authorities': [{'id': 'source-a', 'title': 'Declared authority', 'citation': 'Declared section',
                         'source_url': 'https://example.invalid/authority', 'jurisdiction': 'Declared jurisdiction',
                         'effective_on': '2026-01-01', 'checked_on': '2026-10-11', 'valid_through': '2026-12-31'}],
        'sourced_facts': [{'id': 'fact-a', 'text': 'Declared fact', 'authority_refs': ['source-a']}],
        'assertions': [{'id': 'assertion-a', 'text': 'Declared assertion'}],
        'analysis': [{'id': 'analysis-a', 'text': 'Declared analysis', 'authority_refs': ['source-a'],
                      'fact_refs': ['fact-a'], 'assertion_refs': ['assertion-a']}],
        'issues': [{'id': 'issue-' + d, 'domain': d, 'question': 'Declared question',
                    'authority_refs': ['source-a'], 'fact_refs': ['fact-a'],
                    'assertion_refs': ['assertion-a'], 'analysis_refs': ['analysis-a']}
                   for d in ('delegation', 'procedure', 'record', 'deference', 'remedy')],
    }

class ExactOutput1267Tests(unittest.TestCase):
    def refuses(self, packet, code):
        with self.assertRaisesRegex(ValueError, '^ADMINI1267:' + code + '$'):
            module.build_review(packet)

    def test_disclaimer_literal_exact(self):
        literal = 'Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.'
        self.assertEqual(module.DISCLAIMER, literal)
        self.assertEqual(module.build_review(review_packet())['disclaimer'], literal)

    def test_full_output_exact(self):
        import copy
        packet = review_packet()
        authority = copy.deepcopy(packet['authorities'][0]); authority['independently_verified'] = False
        fact = copy.deepcopy(packet['sourced_facts'][0]); fact['status'] = 'supplied_reference_linked_unverified'
        assertion = copy.deepcopy(packet['assertions'][0]); assertion['status'] = 'caller_assertion_unverified'
        analysis = copy.deepcopy(packet['analysis'][0]); analysis['status'] = 'caller_analysis_unverified'
        domain_map = {}
        for issue in packet['issues']:
            item = copy.deepcopy(issue); item['status'] = 'declared_question_for_counsel_review'
            domain_map[item['domain']] = [item]
        expected = {
            'feature_id': 1267, 'status': 'declared_administrative_bookkeeping_only',
            'jurisdiction': 'Declared jurisdiction', 'as_of': '2026-10-11',
            'provenance': {'source_label': 'Declared packet', 'observed_on': '2026-10-11'},
            'supplied_material': {'authorities': [authority], 'sourced_facts': [fact],
                                  'assertions': [assertion], 'analysis': [analysis]},
            'domain_map': domain_map, 'gaps': [],
            'counts': {'authorities': 1, 'sourced_facts': 1, 'assertions': 1, 'analysis': 1, 'issues': 5},
            'review_state': 'counsel_review_required', 'evidence_verified': False,
            'named_legal_capability_executed': False, 'legal_conclusion': None,
            'external_effect': False, 'requires_licensed_counsel': True,
            'disclaimer': 'Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.',
        }
        self.assertEqual(module.build_review(packet), expected)

    def test_exact_top_and_provenance_and_supplied_material_keys(self):
        result = module.build_review(review_packet())
        self.assertEqual(set(result), {'feature_id','status','jurisdiction','as_of','provenance','supplied_material','domain_map','gaps','counts','review_state','evidence_verified','named_legal_capability_executed','legal_conclusion','external_effect','requires_licensed_counsel','disclaimer'})
        self.assertEqual(result['provenance'], {'source_label': 'Declared packet', 'observed_on': '2026-10-11'})
        self.assertEqual(set(result['supplied_material']), {'authorities','sourced_facts','assertions','analysis'})
        self.assertEqual(result['jurisdiction'], 'Declared jurisdiction')
        self.assertEqual(result['as_of'], '2026-10-11')

    def test_ordered_dict_top_and_nested_rejected(self):
        from collections import OrderedDict
        self.refuses(OrderedDict(review_packet()), 'SCHEMA')
        for location in ('provenance', 'authority', 'issue'):
            packet = review_packet()
            if location == 'provenance': packet['provenance'] = OrderedDict(packet['provenance'])
            elif location == 'authority': packet['authorities'][0] = OrderedDict(packet['authorities'][0])
            else: packet['issues'][0] = OrderedDict(packet['issues'][0])
            self.refuses(packet, 'SCHEMA')

    def test_list_instead_of_object_required_keys_rejected(self):
        packet = review_packet(); self.refuses(list(packet), 'SCHEMA')
        for location in ('provenance', 'authority', 'issue'):
            packet = review_packet()
            if location == 'provenance': packet['provenance'] = list(packet['provenance'])
            elif location == 'authority': packet['authorities'][0] = list(packet['authorities'][0])
            else: packet['issues'][0] = list(packet['issues'][0])
            self.refuses(packet, 'SCHEMA')

    def test_all_collection_exact_200_boundary(self):
        import copy
        self.assertEqual(module.MAX_ITEMS, 200)
        for name in ('authorities','sourced_facts','assertions','analysis','issues'):
            packet = review_packet(); prototype = copy.deepcopy(packet[name][0])
            entries = []
            for index in range(200):
                item = copy.deepcopy(prototype)
                item['id'] = prototype['id'] if index == 0 else 'entry-' + str(index)
                entries.append(item)
            packet[name] = entries
            result = module.build_review(packet)
            self.assertEqual(result['counts'][name], 200)
            packet[name].append(copy.deepcopy(prototype)); self.refuses(packet, 'COLLECTION')

    def test_url_interior_spaces_and_thin_space(self):
        for char in (' ', '\u2009'):
            packet = review_packet(); packet['authorities'][0]['source_url'] = 'https://example.invalid/a' + char + 'b'
            self.refuses(packet, 'SOURCE_URL')

    def test_url_port_echo_exact(self):
        for url in ('https://example.invalid:443/authority', 'https://example.invalid/authority'):
            packet = review_packet(); packet['authorities'][0]['source_url'] = url
            self.assertEqual(module.build_review(packet)['supplied_material']['authorities'][0]['source_url'], url)
        packet = review_packet(); packet['authorities'][0]['source_url'] = 'https://example.invalid:444/authority'
        self.refuses(packet, 'SOURCE_URL')

    def test_unknown_root_key_within_optional_key_budget_refused(self):
        packet = review_packet()
        del packet['analysis']
        packet['unknown'] = []
        self.refuses(packet, 'SCHEMA')

    def test_fact_assertion_analysis_exact_schema(self):
        for name in ('sourced_facts','assertions','analysis'):
            packet = review_packet(); packet[name][0]['extra'] = 'not permitted'; self.refuses(packet, 'SCHEMA')
            packet = review_packet(); del packet[name][0]['text']; self.refuses(packet, 'SCHEMA')

    def test_authority_exact_echo_fields_and_false_verification(self):
        packet = review_packet(); expected = dict(packet['authorities'][0]); expected['independently_verified'] = False
        self.assertEqual(module.build_review(packet)['supplied_material']['authorities'][0], expected)

    def test_exact_material_statuses_and_issue_question(self):
        result = module.build_review(review_packet())
        for name,status in (('sourced_facts','supplied_reference_linked_unverified'),('assertions','caller_assertion_unverified'),('analysis','caller_analysis_unverified')):
            self.assertEqual(result['supplied_material'][name][0]['status'],status)
        item = result['domain_map']['delegation'][0]
        self.assertEqual(item['question'], 'Declared question')
        self.assertEqual(item['status'], 'declared_question_for_counsel_review')

if __name__ == '__main__':
    unittest.main()
