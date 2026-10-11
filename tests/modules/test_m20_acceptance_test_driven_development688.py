"""Row 688 bounded declared ATDD agreement bookkeeping (ACCEPT688).

Hermetic, stdlib-only; loads the module by file path. ROW688_MODULE_PATH
overrides the path for mutation runs.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import unittest

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
PATH = pathlib.Path(os.environ.get(
    'ROW688_MODULE_PATH',
    ROOT / 'backend/app/modules/m20_general_cognitive_worker/acceptance_test_driven_development688.py'))
spec = importlib.util.spec_from_file_location('row688_under_test', PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def req(**over):
    base = {'feature': 'Export report',
            'acceptance_criteria': [{'id': 'AC1', 'text': 'CSV download starts'},
                                    {'id': 'AC2', 'text': 'Empty state shown'}],
            'examples': [{'criterion_id': 'AC1', 'text': 'User picks CSV'},
                         {'criterion_id': 'AC2', 'text': 'No rows present'}],
            'stakeholders': ['po', 'qa', 'dev'],
            'agreed_by': ['po', 'qa']}
    base.update(over)
    return base


def refusal(data, code):
    try:
        m.run(data)
    except ValueError as e:
        assert str(e) == 'ACCEPT688:' + code, str(e)
    else:
        raise AssertionError('no refusal for ' + code)


class TestRefusals(unittest.TestCase):
    def test_request_and_keys(self):
        refusal([], 'BAD_TYPE:request')
        refusal(req(extra=1), 'UNKNOWN_KEY')
        data = req()
        data[1] = 0
        refusal(data, 'BAD_TYPE:key')
        refusal(req(**{'k' * 129: 0}), 'OVERSIZE:request')
        refusal(req(**{'k' * 128: 0}), 'UNKNOWN_KEY')
        for key in ('execute', 'run_tests', 'deploy', 'release', 'certify'):
            refusal(req(**{key: True}), 'EXECUTION_REQUEST:' + key)

    def test_feature(self):
        refusal(req(feature=None), 'MISSING:feature')
        refusal(req(feature=7), 'BAD_TYPE:feature')
        refusal(req(feature='   '), 'EMPTY:feature')
        refusal(req(feature='x' * 513), 'OVERSIZE:feature')

    def test_criteria_shape(self):
        refusal(req(acceptance_criteria=None), 'MISSING:acceptance_criteria')
        refusal(req(acceptance_criteria='AC1'), 'BAD_TYPE:acceptance_criteria')
        refusal(req(acceptance_criteria=[]), 'EMPTY:acceptance_criteria')
        refusal(req(acceptance_criteria=[{'text': 'x'}]), 'MISSING:criterion_id')
        refusal(req(acceptance_criteria=[{'id': 1, 'text': 'x'}]), 'BAD_TYPE:criterion_id')
        refusal(req(acceptance_criteria=[{'id': 'AC1'}]), 'MISSING:criterion_text')
        refusal(req(acceptance_criteria=[{'id': 'AC1', 'text': '  '}]), 'EMPTY:criterion_text')

    def test_criteria_uniqueness_and_caps(self):
        refusal(req(acceptance_criteria=[{'id': 'AC1', 'text': 'a'},
                                         {'id': 'AC1', 'text': 'b'}]), 'DUPLICATE:criterion_id')
        refusal(req(acceptance_criteria=[{'id': 'AC%03d' % i, 'text': 'x'}
                                         for i in range(129)]), 'OVERSIZE:acceptance_criteria')
        m.run(req(acceptance_criteria=[{'id': 'AC%03d' % i, 'text': 'x'}
                                       for i in range(128)]))

    def test_examples_shape(self):
        refusal(req(examples=None), 'MISSING:examples')
        refusal(req(examples='x'), 'BAD_TYPE:examples')
        refusal(req(examples=[{'text': 'x'}]), 'MISSING:example_criterion_id')
        refusal(req(examples=[{'criterion_id': 9, 'text': 'x'}]), 'BAD_TYPE:example_criterion_id')
        refusal(req(examples=[{'criterion_id': 'AC1', 'text': ''}]), 'EMPTY:example_text')
        refusal(req(examples=[{'criterion_id': 'AC1', 'text': 'x'}] * 257), 'OVERSIZE:examples')
        m.run(req(examples=[{'criterion_id': 'AC1', 'text': 'x'}] * 256))

    def test_stakeholders_shape(self):
        refusal(req(stakeholders=None), 'MISSING:stakeholders')
        refusal(req(stakeholders='po'), 'BAD_TYPE:stakeholders')
        refusal(req(stakeholders=[]), 'EMPTY:stakeholders')
        refusal(req(stakeholders=['po', '']), 'EMPTY:stakeholder')
        refusal(req(stakeholders=['po', 3]), 'BAD_TYPE:stakeholder')
        refusal(req(stakeholders=['po', 'po']), 'DUPLICATE:stakeholder')
        refusal(req(stakeholders=['s%03d' % i for i in range(65)]), 'OVERSIZE:stakeholders')
        m.run(req(stakeholders=['s%03d' % i for i in range(64)]))

    def test_agreed_by_shape(self):
        refusal(req(agreed_by='po'), 'BAD_TYPE:agreed_by')
        refusal(req(agreed_by=['po', 3]), 'BAD_TYPE:agreement')
        refusal(req(agreed_by=['po', 'po']), 'DUPLICATE:agreement')
        refusal(req(agreed_by=[''] * 1), 'EMPTY:agreement')
        refusal(req(agreed_by=['a%03d' % i for i in range(65)]), 'OVERSIZE:agreed_by')

    def test_key_unicode_screening(self):
        refusal(req(**{'k\x00': 0}), 'BAD_TYPE:key')
        refusal(req(**{'k' * 128 + '​': 0}), 'OVERSIZE:request')
        refusal(req(**{'k ': 0}), 'UNKNOWN_KEY')


class TestBookkeeping(unittest.TestCase):
    def test_agreement_incomplete(self):
        out = m.run(req())
        self.assertIs(out['agreement_complete'], False)
        self.assertEqual(out['pending_agreement'], ['dev'])

    def test_agreement_complete(self):
        out = m.run(req(agreed_by=['po', 'qa', 'dev']))
        self.assertIs(out['agreement_complete'], True)
        self.assertEqual(out['pending_agreement'], [])
        out = m.run(req(agreed_by=['dev', 'qa', 'po', 'extra-reviewer']))
        self.assertIs(out['agreement_complete'], True)
        self.assertEqual(out['unlisted_agreements'], ['extra-reviewer'])

    def test_agreement_default_empty(self):
        base = req()
        del base['agreed_by']
        out = m.run(base)
        self.assertIs(out['agreement_complete'], False)
        self.assertEqual(out['pending_agreement'], ['dev', 'po', 'qa'])
        self.assertEqual(out['unlisted_agreements'], [])

    def test_coverage_bookkeeping(self):
        out = m.run(req(examples=[{'criterion_id': 'AC1', 'text': 'x'}]))
        self.assertEqual(out['uncovered_criterion_ids'], ['AC2'])
        self.assertEqual(out['orphan_example_criterion_ids'], [])
        out = m.run(req(examples=[{'criterion_id': 'AC1', 'text': 'x'},
                                  {'criterion_id': 'AC9', 'text': 'y'}]))
        self.assertEqual(out['uncovered_criterion_ids'], ['AC2'])
        self.assertEqual(out['orphan_example_criterion_ids'], ['AC9'])

    def test_no_execution_no_quality_claims(self):
        out = m.run(req())
        self.assertIs(out['executable_before_implementation'], True)
        self.assertIs(out['tests_executed'], False)
        self.assertIs(out['caller_declared_agreement'], True)
        text = json.dumps(out)
        for banned in ('quality_score', 'release_ready', 'confidence', 'coverage_pct'):
            self.assertNotIn(banned, text)
        # 'coverage' as a word appears only inside the limits negation line
        for line in out['limits']:
            if 'coverage' in line:
                self.assertIn('no coverage', line)

    def test_record_shape(self):
        out = m.run(req())
        self.assertEqual(set(out), {'feature', 'criteria_count', 'example_count',
                                    'stakeholders', 'agreed_by', 'pending_agreement',
                                    'unlisted_agreements', 'agreement_complete',
                                    'uncovered_criterion_ids', 'orphan_example_criterion_ids',
                                    'executable_before_implementation', 'tests_executed',
                                    'caller_declared_agreement', 'limits'})

    def test_determinism(self):
        self.assertEqual(json.dumps(m.run(req()), sort_keys=True),
                         json.dumps(m.run(req()), sort_keys=True))

    def test_echo_is_exact(self):
        out = m.run(req(feature='  Export report  '))
        self.assertEqual(out['feature'], 'Export report')
        self.assertEqual(out['stakeholders'], ['po', 'qa', 'dev'])
        self.assertEqual(out['agreed_by'], ['po', 'qa'])
        self.assertEqual(out['criteria_count'], 2)
        self.assertEqual(out['example_count'], 2)

    def test_sorted_bookkeeping(self):
        out = m.run(req(acceptance_criteria=[{'id': 'AC9', 'text': 'a'},
                                             {'id': 'AC2', 'text': 'b'}],
                        examples=[{'criterion_id': 'ZZZ', 'text': 'x'}],
                        agreed_by=['zz', 'qa']))
        self.assertEqual(out['uncovered_criterion_ids'], ['AC2', 'AC9'])
        self.assertEqual(out['orphan_example_criterion_ids'], ['ZZZ'])
        self.assertEqual(out['pending_agreement'], ['dev', 'po'])
        self.assertEqual(out['unlisted_agreements'], ['zz'])


class TestLimitsText(unittest.TestCase):
    def test_limits_present(self):
        limits = m.run(req())['limits']
        self.assertTrue(any('not shipped product code' in x for x in limits))
        self.assertTrue(any('never executes' in x for x in limits))
        self.assertTrue(any('caller-supplied' in x for x in limits))


class TestSettledPolicyPins(unittest.TestCase):
    def test_request_key_count_first(self):
        data = req()  # 5 base keys + 60 = 65, over the 64 cap
        for i in range(60):
            data['x%02d' % i] = 0
        refusal(data, 'OVERSIZE:request')
        data2 = req()  # 5 base keys + 59 = 64, exactly at the cap
        for i in range(59):
            data2['x%02d' % i] = 0
        refusal(data2, 'UNKNOWN_KEY')

    def test_soft_hyphen_refused(self):
        refusal(req(feature='Export\u00adreport'), 'BAD_TYPE:feature')
        refusal(req(acceptance_criteria=[{'id': 'AC1', 'text': 'a\u00adb'}]),
                'BAD_TYPE:criterion_text')

    def test_word_joiner_refused(self):
        refusal(req(feature='Export\u2060report'), 'BAD_TYPE:feature')
        refusal(req(acceptance_criteria=[{'id': 'AC1', 'text': 'a\u2060b'}]),
                'BAD_TYPE:criterion_text')


class TestEntryExactSchema(unittest.TestCase):
    def test_criterion_extra_key_fixed_reason(self):
        refusal(req(acceptance_criteria=[{'id': 'AC1', 'text': 'a', 'weight': 3}]),
                'OVERSIZE:criterion')
        refusal(req(acceptance_criteria=[{'id': 'AC1', 'extra': 1}]),
                'UNKNOWN_FIELD:criterion')
        refusal(req(acceptance_criteria=[{'id': 'AC1', 'text': 'a', 1: 2}]),
                'OVERSIZE:criterion')
        refusal(req(acceptance_criteria=[{'text': 'a', 1: 2}]),
                'UNKNOWN_FIELD:criterion')

    def test_example_extra_key_fixed_reason(self):
        refusal(req(examples=[{'criterion_id': 'AC1', 'text': 'a', 'weight': 3}]),
                'OVERSIZE:example')
        refusal(req(examples=[{'criterion_id': 'AC1', 'extra': 1}]),
                'UNKNOWN_FIELD:example')
        refusal(req(examples=[{'text': 'a', 1: 2}]),
                'UNKNOWN_FIELD:example')

    def test_unknown_field_reason_carries_no_echo(self):
        try:
            m.run(req(acceptance_criteria=[{'id': 'AC1', 'secretfield': 1}]))
        except ValueError as e:
            self.assertEqual(str(e), 'ACCEPT688:UNKNOWN_FIELD:criterion')
            self.assertNotIn('secretfield', str(e))
        else:
            raise AssertionError('no refusal')

    def test_two_key_entries_accepted(self):
        out = m.run(req())
        self.assertEqual(out['criteria_count'], 2)
        self.assertEqual(out['example_count'], 2)


class TestRootUnknownKeyNoEcho(unittest.TestCase):
    def test_root_unknown_key_fixed_reason(self):
        try:
            m.run(req(verylongcallerkeyname_xyz=1))
        except ValueError as e:
            self.assertEqual(str(e), 'ACCEPT688:UNKNOWN_KEY')
            self.assertNotIn('verylongcallerkeyname_xyz', str(e))
        else:
            raise AssertionError('no refusal')


if __name__ == '__main__':
    unittest.main()


# Closing pins for cap boundaries, strict built-ins and independent outputs.
def closing_field(field, value):
    data = req()
    slots = {'criterion_id': ('acceptance_criteria', 'id'),
             'criterion_text': ('acceptance_criteria', 'text'),
             'example_criterion_id': ('examples', 'criterion_id'),
             'example_text': ('examples', 'text')}
    if field in slots:
        container, key = slots[field]
        data[container][0][key] = value
    elif field in ('stakeholder', 'agreement'):
        data['stakeholders' if field == 'stakeholder' else 'agreed_by'][0] = value
    else:
        data[field] = value
    return data


FIELDS = [('feature', 512), ('criterion_id', 128), ('example_criterion_id', 128),
          ('criterion_text', 512), ('example_text', 512), ('stakeholder', 128),
          ('agreement', 128)]


@pytest.mark.parametrize('field,cap', FIELDS)
def test_closing_raw_cap_pair(field, cap):
    out = m.run(closing_field(field, 'x' * cap))
    if field == 'feature':
        assert out['feature'] == 'x' * cap
    elif field == 'stakeholder':
        assert out['stakeholders'][0] == 'x' * cap
    elif field == 'agreement':
        assert out['agreed_by'][0] == 'x' * cap
    refusal(closing_field(field, 'x' * (cap + 1)), 'OVERSIZE:' + field)


def test_closing_agreed_by_exact_64():
    names = ['reviewer%02d' % i for i in range(64)]
    out = m.run(req(agreed_by=names))
    assert out['agreed_by'] == names
    assert out['unlisted_agreements'] == names
    assert out['agreement_complete'] is False


@pytest.mark.parametrize('separator', ['\u2028', '\u2029'])
@pytest.mark.parametrize('field,cap', FIELDS)
def test_closing_unicode_separators(field, cap, separator):
    refusal(closing_field(field, 'a' + separator + 'b'), 'BAD_TYPE:' + field)


class ClosingStr(str):
    pass


class ClosingList(list):
    pass


class ClosingDict(dict):
    pass


@pytest.mark.parametrize('field,cap', FIELDS)
def test_closing_str_subclass(field, cap):
    refusal(closing_field(field, ClosingStr('valid')), 'BAD_TYPE:' + field)


@pytest.mark.parametrize('field', ['acceptance_criteria', 'examples',
                                  'stakeholders', 'agreed_by'])
def test_closing_list_subclass(field):
    data = req()
    data[field] = ClosingList(data[field])
    refusal(data, 'BAD_TYPE:' + field)


@pytest.mark.parametrize('field,code', [('acceptance_criteria', 'criterion'),
                                       ('examples', 'example')])
def test_closing_dict_entry_subclass(field, code):
    data = req()
    data[field][0] = ClosingDict(data[field][0])
    refusal(data, 'BAD_TYPE:' + code)


def test_closing_request_subclass():
    refusal(ClosingDict(req()), 'BAD_TYPE:request')


def test_closing_three_way_sorted_output():
    out = m.run(req(stakeholders=['zebra', 'alpha', 'middle'],
                   agreed_by=['outside_z', 'outside_a', 'outside_m'],
                   examples=[{'criterion_id': x, 'text': 'example'}
                             for x in ['orphan_z', 'orphan_a', 'orphan_m']]))
    assert out['pending_agreement'] == ['alpha', 'middle', 'zebra']
    assert out['unlisted_agreements'] == ['outside_a', 'outside_m', 'outside_z']
    assert out['orphan_example_criterion_ids'] == ['orphan_a', 'orphan_m', 'orphan_z']


def test_closing_stakeholders_stripped():
    out = m.run(req(stakeholders=[' alice ', ' bob '], agreed_by=[' alice ']))
    assert out['stakeholders'] == ['alice', 'bob']
    assert out['agreed_by'] == ['alice']
    assert out['pending_agreement'] == ['bob']
    assert out['agreement_complete'] is False


def test_closing_limits_not_aliased():
    first = m.run(req())
    expected = first['limits'][:]
    first['limits'][0] = 'caller overwrite'
    first['limits'].append('caller append')
    later = m.run(req())
    assert later['limits'] == expected
    assert later['limits'] is not first['limits']


@pytest.mark.parametrize('seed', ['0', '1'])
@pytest.mark.parametrize('target', ['uncovered_criterion_ids', 'orphan_example_criterion_ids'])
def test_closing_sorted_ids_fixed_seeds(target, seed):
    import subprocess

    ids = ['id_g', 'id_f', 'id_e', 'id_d', 'id_c', 'id_b', 'id_a']
    data = req(acceptance_criteria=[{'id': x, 'text': 'criterion'} for x in ids],
               examples=[])
    if target == 'orphan_example_criterion_ids':
        data = req(examples=[{'criterion_id': x, 'text': 'example'} for x in ids])
    # Check the current process and two fresh, reproducible hash seeds.
    assert m.run(data)[target] == sorted(ids)
    program = '''import importlib.util,json,sys
spec=importlib.util.spec_from_file_location('row688_seeded',sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(json.dumps(module.run(json.loads(sys.argv[2]))[sys.argv[3]]))
'''
    result = subprocess.run([sys.executable, '-c', program, str(PATH), json.dumps(data), target],
                            env={**os.environ, 'PYTHONHASHSEED': seed},
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == ['id_a', 'id_b', 'id_c', 'id_d', 'id_e', 'id_f', 'id_g']
