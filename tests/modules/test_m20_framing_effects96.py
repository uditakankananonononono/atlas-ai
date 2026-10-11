"""Row 96 bounded exact framing-equivalence audit (FRAMIN96).

Hermetic, stdlib-only; loads the module by file path. ROW96_MODULE_PATH
overrides the path for mutation runs.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
PATH = pathlib.Path(os.environ.get(
    'ROW96_MODULE_PATH',
    ROOT / 'backend/app/modules/m20_general_cognitive_worker/framing_effects_utilization96.py'))
spec = importlib.util.spec_from_file_location('row96_under_test', PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def req(**over):
    base = {'gain_frame': 'Keep 80 of 100 jobs',
            'loss_frame': 'Lose 20 of 100 jobs',
            'facts': {'delta': 20, 'unit': 'jobs'}}
    base.update(over)
    return base


def refusal(data, code):
    try:
        m.run(data)
    except ValueError as e:
        assert str(e) == 'FRAMIN96:' + code, str(e)
    else:
        raise AssertionError('no refusal for ' + code)


class TestRefusals(unittest.TestCase):
    def test_request_and_keys(self):
        refusal([], 'BAD_TYPE:request')
        refusal(req(extra=1), "UNKNOWN_KEY:'extra'")
        for key in ('exploit', 'manipulate', 'deceive', 'mislead', 'coerce', 'hide'):
            refusal(req(**{key: True}), 'MANIPULATION_REQUEST:' + key)

    def test_frames(self):
        refusal(req(gain_frame=7), 'BAD_TYPE:frame')
        refusal(req(gain_frame='  '), 'EMPTY:frame')
        refusal(req(loss_frame=''), 'EMPTY:frame')
        refusal({'loss_frame': 'Lose 20', 'facts': {'delta': 20}}, 'MISSING:gain_frame')

    def test_facts(self):
        refusal(req(facts='jobs'), 'BAD_TYPE:facts')
        refusal(req(facts={}), 'EMPTY:facts')
        refusal({'gain_frame': 'Keep 80', 'loss_frame': 'Lose 20'}, 'MISSING:facts')
        refusal(req(facts={'delta': 2.5}), 'BAD_TYPE:delta')
        refusal(req(facts={'delta': True}), 'BAD_TYPE:delta')
        refusal(req(facts={'delta': 'x'}), 'BAD_TYPE:delta')


class TestMechanism(unittest.TestCase):
    def test_exact_extraction(self):
        out = m.run(req())
        self.assertEqual(out['extracted_frame_numbers'],
                         {'gain': ['80/1', '100/1'], 'loss': ['20/1', '100/1']})
        self.assertEqual(out['numeric_equivalence'], False)

    def test_numeric_equivalence_exact(self):
        out = m.run(req(gain_frame='Save 80 of 100', loss_frame='80 of 100 remain at risk'))
        self.assertEqual(out['numeric_equivalence'], True)
        out = m.run(req(gain_frame='Save 0.5 of the budget', loss_frame='Lose 1/2 of it'))
        self.assertEqual(out['extracted_frame_numbers']['gain'], ['1/2'])

    def test_equivalence_order_insensitive(self):
        out = m.run(req(gain_frame='Keep 80 of 100 jobs', loss_frame='Of 100 jobs, 80 lost'))
        self.assertEqual(out['numeric_equivalence'], True)

    def test_negative_delta_matches_absolute(self):
        self.assertEqual(m.run(req(facts={'delta': -20}))['consistent_with_facts'], True)

    def test_consistency_exact_not_epsilon(self):
        self.assertEqual(m.run(req(facts={'delta': 20}))['consistent_with_facts'], True)
        self.assertEqual(m.run(req(facts={'delta': '19'}))['consistent_with_facts'], False)
        self.assertEqual(m.run(req(facts={'delta': 21}))['consistent_with_facts'], False)
        out = m.run(req(gain_frame='Keep most jobs', loss_frame='Lose some jobs'))
        self.assertIs(out['consistent_with_facts'], None)
        self.assertIs(out['facts_checked'], False)
        self.assertEqual(out['numeric_equivalence'], False)

    def test_balanced_presentation(self):
        out = m.run(req())
        self.assertIs(out['balanced_presentation_required'], True)
        self.assertEqual(out['selected_frame'], 'both')
        self.assertEqual(out['facts'], {'delta': 20, 'unit': 'jobs'})

    def test_no_confidence_no_deployment_no_floats(self):
        text = json.dumps(m.run(req()))
        for banned in ('confidence', 'deployment', '0.8', '0.4'):
            self.assertNotIn(banned, text)

    def test_record_shape(self):
        out = m.run(req())
        self.assertEqual(set(out), {'gain_frame', 'loss_frame', 'facts',
                                    'extracted_frame_numbers', 'numeric_equivalence',
                                    'consistent_with_facts', 'facts_checked',
                                    'balanced_presentation_required',
                                    'selected_frame', 'limits'})

    def test_determinism(self):
        self.assertEqual(json.dumps(m.run(req()), sort_keys=True),
                         json.dumps(m.run(req()), sort_keys=True))


class TestNumeralGrammar(unittest.TestCase):
    def nums(self, frame):
        out = m.run(req(gain_frame=frame, loss_frame='nothing', facts={'unit': 'x'}))
        return out['extracted_frame_numbers']['gain']

    def test_ascii_numerals(self):
        self.assertEqual(self.nums('save 80 jobs'), ['80/1'])
        self.assertEqual(self.nums('save 0.5'), ['1/2'])
        self.assertEqual(self.nums('cost ١٢٣'), [])

    def test_sign_only_at_start_after_space_or_paren(self):
        self.assertEqual(self.nums('-5 jobs'), ['-5/1'])
        self.assertEqual(self.nums('(-5) jobs'), ['-5/1'])
        self.assertEqual(self.nums('a -5 drop'), ['-5/1'])
        self.assertEqual(self.nums('10-15 jobs'), ['10/1', '15/1'])
        self.assertEqual(self.nums('x-5 jobs'), ['5/1'])

    def test_thousands_strict(self):
        self.assertEqual(self.nums('1,000 jobs'), ['1000/1'])
        self.assertEqual(self.nums('1,234.5 risked'), ['2469/2'])
        self.assertEqual(self.nums('1,234 jobs'), ['1234/1'])

    def test_other_commas_are_separators(self):
        self.assertEqual(self.nums('1,2,3 jobs'), ['1/1', '2/1', '3/1'])
        self.assertEqual(self.nums('1,00 jobs'), ['1/1', '0/1'])
        self.assertEqual(self.nums('12,3456 jobs'), ['12/1', '3456/1'])

    def test_frame_resource_guards(self):
        refusal(req(gain_frame='x' * 2001), 'OVERSIZE:gain_frame')
        m.run(req(gain_frame='x' * 2000))
        refusal(req(gain_frame='1234567890123456789 jobs'), 'OVERSIZE:gain_frame')
        refusal(req(gain_frame='0.1234567890123456789 jobs'), 'OVERSIZE:gain_frame')
        m.run(req(gain_frame='123456789012345678.123456789012345678 jobs'))
        refusal(req(gain_frame=' '.join(str(i) for i in range(65))), 'OVERSIZE:gain_frame')
        m.run(req(gain_frame=' '.join(str(i) for i in range(64))))

    def test_no_conversion_on_oversize_numeral(self):
        calls = []
        real = m.Fraction
        def spy(*a, **k):
            calls.append(a)
            return real(*a, **k)
        m.Fraction = spy
        try:
            refusal(req(gain_frame='9' * 19 + ' jobs'), 'OVERSIZE:gain_frame')
        finally:
            m.Fraction = real
        self.assertEqual(calls, [])


class TestFactsValidation(unittest.TestCase):
    def test_exact_type_and_key_cap(self):
        refusal(req(facts={'k%02d' % i: 0 for i in range(65)}), 'OVERSIZE:facts')
        m.run(req(facts={'k%02d' % i: 0 for i in range(64)}))

    def test_key_rules(self):
        refusal(req(facts={'k' * 129: 0}), 'OVERSIZE:facts')
        m.run(req(facts={'k' * 128: 0}))
        for ch in ('\x00', '\u200b', '\u2028', '\u2029'):
            refusal(req(facts={'k' + ch: 0}), 'BAD_TYPE:facts_key')
        m.run(req(facts={'k\u00a0': 0, 'k\u2003': 1}))

    def test_scalar_values_only(self):
        refusal(req(facts={'nested': {'a': 1}}), 'BAD_TYPE:facts_value')
        refusal(req(facts={'nested': [1]}), 'BAD_TYPE:facts_value')
        m.run(req(facts={'s': 'ok', 'i': 1, 'f': 2.5, 'b': True, 'n': None}))
        refusal(req(facts={'s': 'v' * 129}), 'OVERSIZE:facts')
        m.run(req(facts={'s': 'v' * 128}))
        refusal(req(facts={'s': 'bad\u200bvalue'}), 'BAD_TYPE:facts_value')
        m.run(req(facts={'s': 'nbsp\u00a0ok'}))

    def test_non_string_fact_key(self):
        data = req()
        data['facts'] = {1: 'x'}
        refusal(data, 'BAD_TYPE:facts_key')


class TestTriStateConsistency(unittest.TestCase):
    def test_absent_delta(self):
        out = m.run(req(facts={'unit': 'jobs'}))
        self.assertIs(out['consistent_with_facts'], None)
        self.assertIs(out['facts_checked'], False)

    def test_no_numerals(self):
        out = m.run(req(gain_frame='Keep most', loss_frame='Lose some', facts={'delta': 5}))
        self.assertIs(out['consistent_with_facts'], None)
        self.assertIs(out['facts_checked'], False)

    def test_one_sided_numerals_not_checked(self):
        out = m.run(req(gain_frame='Keep 80 jobs', loss_frame='Lose some', facts={'delta': 80}))
        self.assertIs(out['consistent_with_facts'], None)
        self.assertIs(out['facts_checked'], False)
        out = m.run(req(gain_frame='Keep most', loss_frame='Lose 80 jobs', facts={'delta': 80}))
        self.assertIs(out['consistent_with_facts'], None)
        self.assertIs(out['facts_checked'], False)

    def test_match(self):
        out = m.run(req(facts={'delta': 20}))
        self.assertIs(out['consistent_with_facts'], True)
        self.assertIs(out['facts_checked'], True)

    def test_mismatch(self):
        out = m.run(req(facts={'delta': 21}))
        self.assertIs(out['consistent_with_facts'], False)
        self.assertIs(out['facts_checked'], True)


class TestDeltaGrammar(unittest.TestCase):
    def test_delta_rejects(self):
        for bad in ('1e3', '1_0', '+5', ' 5', '5 ', '١٢', '1/0', '1/2', '-1/2', '19/1',
                    '-', '', 'nan', '5..5', '.5', '5.', '1,000'):
            refusal(req(facts={'delta': bad}), 'BAD_TYPE:delta')
        for big in ('9' * 65, '9' * 19, '1.' + '9' * 19):
            refusal(req(facts={'delta': big}), 'OVERSIZE:delta')

    def test_delta_passes_and_bounds(self):
        m.run(req(facts={'delta': '19'}))
        m.run(req(facts={'delta': '-19'}))
        m.run(req(facts={'delta': '12.5'}))
        m.run(req(facts={'delta': '-3.25'}))
        m.run(req(facts={'delta': '999999999999999999.999999999999999999'}))
        refusal(req(facts={'delta': 10**18}), 'OVERSIZE:delta')
        refusal(req(facts={'delta': -(10**18)}), 'OVERSIZE:delta')
        m.run(req(facts={'delta': 10**18 - 1}))


class TestKeyEchoPins(unittest.TestCase):
    def test_non_string_request_key(self):
        data = req()
        data[1] = 0
        refusal(data, 'BAD_TYPE:key')

    def test_unknown_key_echo_truncated(self):
        refusal(req(**{'k' * 200: 0}), 'OVERSIZE:request')
        try:
            m.run(req(**{'k' * 128: 0}))
        except ValueError as e:
            self.assertIn('k' * 128, str(e))
            self.assertNotIn('k' * 129, str(e))
        else:
            raise AssertionError('no refusal')


class TestOutputTextPins(unittest.TestCase):
    def test_limits_strings_exact(self):
        self.assertEqual(m.run(req())['limits'], [
            'This module is a bounded exact framing-equivalence audit aid, not shipped product code.',
            'Equivalence is checked on extracted numerals only; wording emphasis is not measured.',
            'One-sided framing and exploitation of loss aversion are refused.',
        ])

    def test_missing_loss_frame(self):
        refusal({'gain_frame': 'Keep 80', 'facts': {'delta': 20}}, 'MISSING:loss_frame')


class TestFreeTextTokenPins(unittest.TestCase):
    def nums(self, frame):
        out = m.run(req(gain_frame=frame, loss_frame='nothing', facts={'unit': 'x'}))
        return out['extracted_frame_numbers']['gain']

    def test_dot_edge_tokens_read_as_integers(self):
        self.assertEqual(self.nums('.5 jobs'), ['5/1'])
        self.assertEqual(self.nums('5. jobs'), ['5/1'])

    def test_free_text_slash_is_separator_not_rational(self):
        self.assertEqual(self.nums('1/2 jobs'), ['1/1', '2/1'])

    def test_direct_delta_decimal_parses_pq_refuses(self):
        out = m.run(req(gain_frame='Keep 12.5', loss_frame='Lose 12.5', facts={'delta': '12.5'}))
        self.assertIs(out['consistent_with_facts'], True)
        refusal(req(facts={'delta': '1/2'}), 'BAD_TYPE:delta')

    def test_extracted_token_over_digits_refuses_resource_code(self):
        refusal(req(gain_frame='9' * 19 + ' jobs'), 'OVERSIZE:gain_frame')
        refusal(req(gain_frame='0.' + '9' * 19 + ' jobs'), 'OVERSIZE:gain_frame')


class TestMagnitudeAndFiniteFacts(unittest.TestCase):
    def test_magnitude_only_comparison(self):
        out = m.run(req(gain_frame='Save 5 jobs', loss_frame='Lose 5 jobs', facts={'delta': -5}))
        self.assertIs(out['consistent_with_facts'], True)
        self.assertIs(out['facts_checked'], True)
        out = m.run(req(gain_frame='Save 5 jobs', loss_frame='Lose 5 jobs', facts={'delta': 5}))
        self.assertIs(out['consistent_with_facts'], True)
        out = m.run(req(gain_frame='Save 4 jobs', loss_frame='Lose 6 jobs', facts={'delta': -5}))
        self.assertIs(out['consistent_with_facts'], False)

    def test_nonfinite_facts_refused_no_echo(self):
        for bad in (float('nan'), float('inf'), float('-inf')):
            refusal(req(facts={'x': bad}), 'BAD_TYPE:facts_value')
        m.run(req(facts={'a': 0.0, 'b': -0.0, 'c': 1e300, 'd': 12.5, 'e': True}))

    def test_output_json_finite(self):
        out = m.run(req(facts={'delta': 20, 'v': 1e300}))
        json.dumps(out, allow_nan=False)

    def test_oversize_codes_carry_field_names(self):
        refusal(req(loss_frame='x' * 2001), 'OVERSIZE:loss_frame')
        refusal(req(loss_frame='9' * 19 + ' jobs'), 'OVERSIZE:loss_frame')
        refusal(req(loss_frame=' '.join(str(i) for i in range(65))), 'OVERSIZE:loss_frame')


class TestAuthorFinalBoundaryPins(unittest.TestCase):
    def test_request_key_raw_length_boundary(self):
        refusal(req(**{'k' * 129: 0}), 'OVERSIZE:request')
        refusal(req(**{'k' * 128: 0}), "UNKNOWN_KEY:%r" % ('k' * 128,))

    def test_trailing_hyphen_is_not_a_sign(self):
        for text in ('5 -', '5-', '5 - '):
            out = m.run(req(gain_frame=text + ' jobs', loss_frame='nothing',
                            facts={'unit': 'x'}))
            self.assertEqual(out['extracted_frame_numbers']['gain'], ['5/1'])
        out = m.run(req(gain_frame='-5 jobs', loss_frame='nothing', facts={'unit': 'x'}))
        self.assertEqual(out['extracted_frame_numbers']['gain'], ['-5/1'])
        out = m.run(req(gain_frame='a-5 jobs', loss_frame='nothing', facts={'unit': 'x'}))
        self.assertEqual(out['extracted_frame_numbers']['gain'], ['5/1'])


class TestPeerPassPins(unittest.TestCase):
    def test_delta_length_before_grammar(self):
        refusal(req(facts={'delta': 'x' * 64}), 'BAD_TYPE:delta')
        refusal(req(facts={'delta': 'x' * 65}), 'OVERSIZE:delta')

    def test_leading_token_never_reads_trailing_minus(self):
        out = m.run(req(gain_frame='5 -', loss_frame='Lose 10', facts={'delta': '5'}))
        self.assertIs(out['consistent_with_facts'], True)
        self.assertIs(out['facts_checked'], True)


if __name__ == '__main__':
    unittest.main()
