"""Hermetic stdlib tests for the bounded row705 record builder."""
import copy
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/architecture_decision_records705.py'
spec = importlib.util.spec_from_file_location('adr705_under_test', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
build = module.architecture_decision_records705


def sample():
    return {'title': 'Queue choice', 'context': 'Buffer declared work',
            'decision': 'Use a bounded queue', 'consequences': ['Overflow is explicit']}


class ADR705Tests(unittest.TestCase):
    def refusal(self, data, reason):
        with self.assertRaises(ValueError) as caught:
            build(data)
        self.assertEqual(str(caught.exception), 'ARCHIT705: ' + reason)

    def test_exact_default_record_and_counts(self):
        result = build(sample())
        self.assertEqual(result['record'], dict(sample(), status='proposed', alternatives=[], supersedes=None))
        self.assertEqual(result['counts'], {'alternatives': 0, 'consequences': 1})
        self.assertEqual(result['scope'], 'caller_supplied_adr_bookkeeping_only')

    def test_statuses_and_optional_values_preserved(self):
        for status in ('proposed', 'accepted', 'rejected', 'deprecated', 'superseded'):
            with self.subTest(status=status):
                data = dict(sample(), status=status, alternatives=['Unbounded queue'], supersedes='Previous queue record')
                result = build(data)
                self.assertEqual(result['record'], data)
                self.assertEqual(result['counts'], {'alternatives': 1, 'consequences': 1})

    def test_boundaries_are_always_non_authorizing(self):
        for status in ('proposed', 'accepted', 'superseded'):
            result = build(dict(sample(), status=status))
            self.assertTrue(result['immutable_history_required'])
            self.assertTrue(result['human_review_required'])
            for key in ('history_immutability_enforced', 'architecture_validated', 'repository_behavior_verified', 'release_authorized', 'evidence_verified'):
                self.assertIs(result[key], False, key)

    def test_input_and_output_have_no_list_aliases(self):
        data = dict(sample(), alternatives=['A', 'B'])
        before = copy.deepcopy(data)
        result = build(data)
        self.assertEqual(data, before)
        result['record']['alternatives'].append('C')
        result['record']['consequences'][0] = 'changed'
        self.assertEqual(data, before)
        data['alternatives'][0] = 'later'
        self.assertEqual(result['record']['alternatives'][0], 'A')

    def test_exact_mapping_type(self):
        class Mapping(dict):
            pass
        for value in (None, [], 'data', Mapping(sample())):
            self.refusal(value, 'input must be a dict')

    def test_missing_required_fields(self):
        for field in ('title', 'context', 'decision', 'consequences'):
            data = sample(); del data[field]
            self.refusal(data, 'missing ' + field)

    def test_unknown_fields(self):
        for key in ('approval', 'release_authorized', 1):
            self.refusal(dict(sample(), **{key: True}) if isinstance(key, str) else {**sample(), key: True}, 'unknown fields')

    def test_text_types_empty_and_controls(self):
        class Text(str):
            pass
        for field in ('title', 'context', 'decision', 'supersedes'):
            for value in (0, True, [], Text('text'), '', '   ', 'a\nb', 'a\x7fb', 'a\x85b', 'a\u202eb', 'a\u2028b', 'a\u2029b'):
                with self.subTest(field=field, value=repr(value)):
                    self.refusal(dict(sample(), **{field: value}), field + ' must be nonblank safe text')

    def test_raw_text_caps_and_preservation(self):
        for field, cap in (('title', 200), ('context', 4000), ('decision', 4000), ('supersedes', 200)):
            value = 'x' * cap
            self.assertEqual(build(dict(sample(), **{field: value}))['record'][field], value)
            self.refusal(dict(sample(), **{field: value + 'x'}), field + ' raw length exceeds ' + str(cap))
            self.refusal(dict(sample(), **{field: ' ' * (cap + 1)}), field + ' raw length exceeds ' + str(cap))
        self.assertEqual(build(dict(sample(), title='  Queue  '))['record']['title'], '  Queue  ')

    def test_non_ascii_visible_text_is_preserved(self):
        self.assertEqual(build(dict(sample(), title='Caf\u00e9\u00a0queue'))['record']['title'], 'Caf\u00e9\u00a0queue')

    def test_status_exact_enum(self):
        for status in (None, [], True, 'Accepted', ' accepted ', 'unknown'):
            self.refusal(dict(sample(), status=status), 'status must be a declared ADR status')

    def test_status_raw_cap_before_enum(self):
        self.refusal(dict(sample(), status='x' * 11), 'status raw length exceeds 10')
        self.refusal(dict(sample(), status=' ' * 11), 'status raw length exceeds 10')

    def test_full_cf_soft_hyphen_word_joiner_pins(self):
        for char in ('\u00ad', '\u2060'):
            for field in ('title', 'context', 'decision', 'supersedes'):
                self.refusal(dict(sample(), **{field: 'a' + char + 'b'}), field + ' must be nonblank safe text')
            for field in ('alternatives', 'consequences'):
                self.refusal(dict(sample(), **{field: ['a' + char + 'b']}), field + '[0] must be nonblank safe text')
            self.refusal(dict(sample(), status='a' + char + 'b'), 'status must be a declared ADR status')

    def test_cs_remains_accepted_residual_and_zs_preserved(self):
        for char in ('\ud800', '\u00a0'):
            for field in ('title', 'context', 'decision', 'supersedes'):
                value = 'a' + char + 'b'
                self.assertEqual(build(dict(sample(), **{field: value}))['record'][field], value)
            for field in ('alternatives', 'consequences'):
                value = ['a' + char + 'b']
                self.assertEqual(build(dict(sample(), **{field: value}))['record'][field], value)

    def test_status_str_subclass_refusal(self):
        class Status(str):
            pass
        self.refusal(dict(sample(), status=Status('accepted')), 'status must be a declared ADR status')

    def test_str_subclass_key_refusal(self):
        class Key(str):
            pass
        data = sample()
        del data['title']
        data[Key('title')] = 'Queue choice'
        self.refusal(data, 'unknown fields')

    def test_adjacent_refusal_order(self):
        cases = (
            ({'title': '', 'context': ''}, 'title must be nonblank safe text'),
            ({'context': '', 'decision': ''}, 'context must be nonblank safe text'),
            ({'decision': '', 'status': 'bad'}, 'decision must be nonblank safe text'),
            ({'status': 'bad', 'alternatives': None}, 'status must be a declared ADR status'),
            ({'alternatives': None, 'consequences': None}, 'alternatives must be a list'),
            ({'consequences': None, 'supersedes': ''}, 'consequences must be a list'),
        )
        for changes, reason in cases:
            with self.subTest(changes=changes):
                self.refusal(dict(sample(), **changes), reason)

    def test_missing_required_before_invalid_title(self):
        for field in ('context', 'decision', 'consequences'):
            data = dict(sample(), title='')
            del data[field]
            with self.subTest(field=field):
                self.refusal(data, 'missing ' + field)

    def test_optional_null_supersedes(self):
        self.assertIsNone(build(dict(sample(), supersedes=None))['record']['supersedes'])

    def test_list_type_and_cardinality(self):
        class Items(list):
            pass
        for field in ('alternatives', 'consequences'):
            for value in (None, 'x', (), {}, Items(['x'])):
                self.refusal(dict(sample(), **{field: value}), field + ' must be a list')
            self.refusal(dict(sample(), **{field: ['x'] * 33}), field + ' count exceeds 32')
        self.assertEqual(build(dict(sample(), consequences=['x'] * 32))['counts']['consequences'], 32)
        self.assertEqual(build(dict(sample(), alternatives=['x'] * 32))['counts']['alternatives'], 32)
        self.refusal(dict(sample(), consequences=[]), 'consequences must not be empty')
        self.assertEqual(build(dict(sample(), alternatives=[]))['counts']['alternatives'], 0)

    def test_list_item_types_controls_and_caps(self):
        for field in ('alternatives', 'consequences'):
            for item in ('', ' ', None, 1, [], 'a\u200bb'):
                self.refusal(dict(sample(), **{field: [item]}), field + '[0] must be nonblank safe text')
            self.assertEqual(build(dict(sample(), **{field: ['x' * 1000]}))['record'][field], ['x' * 1000])
            self.refusal(dict(sample(), **{field: ['x' * 1001]}), field + '[0] raw length exceeds 1000')

    def test_order_and_duplicates_not_reinterpreted(self):
        data = dict(sample(), alternatives=['B', 'A', 'B'], consequences=['Y', 'X'])
        self.assertEqual(build(data)['record']['alternatives'], ['B', 'A', 'B'])
        self.assertEqual(build(data)['record']['consequences'], ['Y', 'X'])
        self.assertEqual(build(data), build(copy.deepcopy(data)))


if __name__ == '__main__':
    unittest.main()
