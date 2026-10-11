"""Row 95 bounded exact anchoring-reference audit (ANCHOR95).

Hermetic, stdlib-only; loads the module by file path. ROW95_MODULE_PATH
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
    'ROW95_MODULE_PATH',
    ROOT / 'backend/app/modules/m20_general_cognitive_worker/anchoring_strategy95.py'))
spec = importlib.util.spec_from_file_location('row95_under_test', PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def req(**over):
    base = {'objective_value': 70, 'evidence_low': 50, 'evidence_high': 100}
    base.update(over)
    return base


def refusal(data, code):
    try:
        m.run(data)
    except ValueError as e:
        assert str(e) == 'ANCHOR95:' + code, str(e)
    else:
        raise AssertionError('no refusal for ' + code)


class TestRefusals(unittest.TestCase):
    def test_request_and_keys(self):
        refusal([], 'BAD_TYPE:request')
        refusal(req(extra=1), "UNKNOWN_KEY:'extra'")
        for key in ('deceive', 'mislead', 'bluff', 'fabricate', 'inflate', 'misrepresent'):
            refusal(req(**{key: True}), 'DECEPTIVE_ANCHOR:' + key)

    def test_values(self):
        refusal(req(objective_value=1.5), 'BAD_TYPE:value')
        refusal(req(objective_value=True), 'BAD_TYPE:value')
        refusal(req(evidence_low='abc'), 'BAD_TYPE:value')
        refusal(req(evidence_high='1/0'), 'BAD_TYPE:value')
        refusal(req(evidence_low=100, evidence_high=50), 'INVERTED_RANGE')
        refusal({'objective_value': 70, 'evidence_low': 50}, 'MISSING:evidence_high')


class TestMechanism(unittest.TestCase):
    def test_exact_anchor(self):
        out = m.run(req())
        self.assertEqual(out['evidence_based_anchor'], '70/1')
        self.assertEqual(out['anchor_in_evidence_range'], True)
        self.assertEqual(out['range'], ['50/1', '100/1'])
        self.assertEqual(out['range_midpoint'], '75/1')
        self.assertEqual(out['heuristic_adjustment_band'], '25/2')
        self.assertEqual(out['expected_settlement_zone'], ['70/1', '75/1'])
        self.assertNotIn('rejection', out)

    def test_range_boundaries_inclusive(self):
        self.assertEqual(m.run(req(objective_value=50))['evidence_based_anchor'], '50/1')
        self.assertEqual(m.run(req(objective_value=100))['evidence_based_anchor'], '100/1')
        self.assertEqual(m.run(req(objective_value=49))['anchor_in_evidence_range'], False)
        self.assertEqual(m.run(req(objective_value=101))['anchor_in_evidence_range'], False)

    def test_rational_values(self):
        out = m.run(req(objective_value='201/3', evidence_low='50/1', evidence_high='100/1'))
        self.assertEqual(out['evidence_based_anchor'], '67/1')
        self.assertEqual(out['range_midpoint'], '75/1')

    def test_out_of_range(self):
        out = m.run(req(evidence_low=50, evidence_high=60))
        self.assertEqual(out['anchor_in_evidence_range'], False)
        self.assertEqual(out['evidence_based_anchor'], None)
        self.assertEqual(out['expected_settlement_zone'], None)
        self.assertIn('rejection', out)

    def test_no_confidence_no_floats(self):
        text = json.dumps(m.run(req()))
        for banned in ('confidence', '0.6', '0.9', 'estimated', 'deployment'):
            self.assertNotIn(banned, text)

    def test_record_shape(self):
        out = m.run(req())
        self.assertEqual(set(out), {'evidence_based_anchor', 'anchor_in_evidence_range',
                                    'range', 'range_midpoint', 'heuristic_adjustment_band',
                                    'expected_settlement_zone', 'rationale_required', 'limits'})

    def test_zero_width_range_allowed(self):
        out = m.run(req(objective_value=75, evidence_low=75, evidence_high=75))
        self.assertEqual(out['evidence_based_anchor'], '75/1')
        self.assertEqual(out['heuristic_adjustment_band'], '0/1')
        refusal(req(objective_value=74, evidence_low=75, evidence_high=75), None) if False else None
        self.assertEqual(m.run(req(objective_value=74, evidence_low=75,
                                   evidence_high=75))['anchor_in_evidence_range'], False)

    def test_rationale_required_true(self):
        self.assertIs(m.run(req())['rationale_required'], True)

    def test_determinism(self):
        self.assertEqual(json.dumps(m.run(req()), sort_keys=True),
                         json.dumps(m.run(req()), sort_keys=True))


class TestValueGrammar(unittest.TestCase):
    def test_missing_codes(self):
        refusal({'evidence_low': 50, 'evidence_high': 100}, 'MISSING:objective_value')
        refusal({'objective_value': 70, 'evidence_high': 100}, 'MISSING:evidence_low')
        refusal({'objective_value': 70, 'evidence_low': 50}, 'MISSING:evidence_high')

    def test_grammar_rejects(self):
        for bad in (' 5', '5 ', '1_0', '1e2', '١٢', '5.5', '1/ 2', '1 /2',
                    '+3', '1/0', '1//2', '/2', '1/', '', 'nan', '0x5', '-',
                    '-/2', '9' * 65, '9' * 19, '1/' + '9' * 19):
            refusal(req(objective_value=bad), 'BAD_TYPE:value')

    def test_grammar_passes(self):
        self.assertEqual(m.run(req(objective_value='1/2', evidence_low=0,
                                   evidence_high=1))['evidence_based_anchor'], '1/2')
        self.assertEqual(m.run(req(objective_value='-1/2', evidence_low='-1',
                                   evidence_high=1))['evidence_based_anchor'], '-1/2')
        self.assertEqual(m.run(req(objective_value='5', evidence_low=0, evidence_high=10))['evidence_based_anchor'], '5/1')
        self.assertEqual(m.run(req(objective_value=-5, evidence_low=-10,
                                   evidence_high=0))['evidence_based_anchor'], '-5/1')

    def test_int_magnitude_bound(self):
        refusal(req(objective_value=10**18), 'BAD_TYPE:value')
        refusal(req(objective_value=-(10**18)), 'BAD_TYPE:value')
        self.assertEqual(m.run(req(objective_value=10**18 - 1, evidence_low=0,
                                   evidence_high=10**18 - 1))['anchor_in_evidence_range'], True)

    def test_no_conversion_on_fast_reject(self):
        calls = []
        real = m.Fraction
        def spy(*a, **k):
            calls.append(a)
            return real(*a, **k)
        m.Fraction = spy
        try:
            refusal(req(objective_value='1e5000000'), 'BAD_TYPE:value')
            refusal(req(objective_value=10**5000), 'BAD_TYPE:value')
            refusal(req(objective_value='9' * 100), 'BAD_TYPE:value')
        finally:
            m.Fraction = real
        self.assertEqual(calls, [])

    def test_no_echo_in_refusals(self):
        try:
            m.run(req(objective_value='secret-marker-string'))
        except ValueError as e:
            self.assertNotIn('secret-marker-string', str(e))
        else:
            raise AssertionError('no refusal')


class TestKeyHandling(unittest.TestCase):
    def test_non_string_keys_refused_before_echo(self):
        for k in (1, None, (1, 2), b'x'):
            data = req()
            data[k] = 0
            refusal(data, 'BAD_TYPE:key')

    def test_unknown_key_echo_truncated_before_repr(self):
        long_key = 'k' * 200
        try:
            m.run(req(**{long_key: 0}))
        except ValueError as e:
            msg = str(e)
            self.assertTrue(msg.startswith('ANCHOR95:UNKNOWN_KEY:'))
            self.assertNotIn('k' * 129, msg)
            self.assertIn('k' * 128, msg)
        else:
            raise AssertionError('no refusal')


class TestOutputTextPins(unittest.TestCase):
    def test_limits_strings_exact(self):
        self.assertEqual(m.run(req())['limits'], [
            'This module is a bounded exact anchoring-reference audit aid, not shipped product code.',
            'The adjustment band is (range / 4), a stated heuristic, not a measurement.',
            'Anchor pull varies widely by counterparty; no settlement outcome is predicted.',
            'A reference point outside the stated evidence range is rejected, not clamped.',
        ])

    def test_rejection_text_exact(self):
        out = m.run(req(evidence_low=50, evidence_high=60))
        self.assertEqual(out['rejection'],
                         'Objective outside the evidence range cannot anchor honestly.')


if __name__ == '__main__':
    unittest.main()
