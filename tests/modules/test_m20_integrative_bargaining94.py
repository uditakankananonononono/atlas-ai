"""Row 94 bounded exact integrative-bargaining priority audit (INTEGR94).

Hermetic, stdlib-only; loads the module by file path. ROW94_MODULE_PATH
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
    'ROW94_MODULE_PATH',
    ROOT / 'backend/app/modules/m20_general_cognitive_worker/integrative_bargaining94.py'))
spec = importlib.util.spec_from_file_location('row94_under_test', PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def req(**over):
    base = {'issues': ['price', 'delivery'],
            'party_a_weights': [1, 3],
            'party_b_weights': [2, 2]}
    base.update(over)
    return base


def refusal(data, code):
    try:
        m.run(data)
    except ValueError as e:
        assert str(e) == 'INTEGR94:' + code, str(e)
    else:
        raise AssertionError('no refusal for ' + code)


class TestRefusals(unittest.TestCase):
    def test_request_and_keys(self):
        refusal([], 'BAD_TYPE:request')
        refusal(req(extra=1), "UNKNOWN_KEY:'extra'")
        for key in ('deceive', 'mislead', 'hide', 'conceal', 'exploit', 'manipulate'):
            refusal(req(**{key: True}), 'DECEPTION_REQUEST:' + key)

    def test_issues(self):
        refusal(req(issues='price'), 'BAD_TYPE:issues')
        refusal(req(issues=[]), 'EMPTY:issues')
        refusal(req(issues=['ok', '']), 'BAD_TYPE:issue')
        refusal(req(issues=['a', 'a'], party_a_weights=[1, 1], party_b_weights=[1, 1]),
                'DUPLICATE:issue')
        m.run(req(issues=['i%02d' % i for i in range(64)],
                  party_a_weights=[1] * 64, party_b_weights=[1] * 64))
        refusal(req(issues=['i%02d' % i for i in range(65)],
                    party_a_weights=[1] * 65, party_b_weights=[1] * 65), 'OVERSIZE:issues')

    def test_weights(self):
        refusal(req(party_a_weights=[1]), 'LENGTH_MISMATCH')
        refusal(req(party_a_weights=[1, True]), 'BAD_TYPE:weight')
        refusal(req(party_a_weights=[1, -1]), 'NEGATIVE:weight')
        refusal(req(party_a_weights=[1, 'x']), 'BAD_TYPE:weight')
        refusal(req(party_a_weights=[0, 0]), 'ZERO_SUM:party_a')
        refusal(req(party_b_weights=[0, 0]), 'ZERO_SUM:party_b')
        refusal(req(party_a_weights=[1, '1/0']), 'BAD_TYPE:weight')
        refusal(req(party_a_weights=[1, 1.5]), 'BAD_TYPE:weight')

    def test_rational_strings_accepted(self):
        out = m.run(req(party_a_weights=[1, '1/2'], party_b_weights=['3/4', 2]))
        self.assertEqual(out['efficient_allocation'][0]['a_priority'], '2/3')


class TestMechanism(unittest.TestCase):
    def test_exact_allocation(self):
        out = m.run(req())
        alloc = out['efficient_allocation']
        self.assertEqual(alloc[0], {'issue': 'price', 'a_priority': '1/4', 'b_priority': '1/2',
                                    'efficient_holder': 'party_b', 'complementarity': '1/4'})
        self.assertEqual(alloc[1], {'issue': 'delivery', 'a_priority': '3/4', 'b_priority': '1/2',
                                    'efficient_holder': 'party_a', 'complementarity': '1/4'})

    def test_exact_gains(self):
        out = m.run(req())
        # joint = 1/2 + 3/4 = 5/4; naive = (1/4+1/2)/2 + (3/4+1/2)/2 = 3/8 + 5/8 = 1
        self.assertEqual(out['joint_gain_potential'], '1/2')
        self.assertEqual(out['logrolling_gain_vs_naive_split'], '1/4')
        self.assertEqual(out['purely_distributive'], False)
        self.assertEqual(out['tie_count'], 0)

    def test_tie_is_explicit_not_party_a(self):
        out = m.run(req(party_a_weights=[1, 1], party_b_weights=[1, 1]))
        self.assertEqual(out['efficient_allocation'][0]['efficient_holder'], 'tie')
        self.assertEqual(out['purely_distributive'], True)
        self.assertEqual(out['tie_count'], 2)
        self.assertEqual(out['logrolling_gain_vs_naive_split'], '0/1')

    def test_tradeoff_order_deterministic(self):
        out = m.run(req(issues=['z', 'a', 'b'], party_a_weights=[1, 2, 3],
                        party_b_weights=[3, 2, 1]))
        # complementarities: z: 1/3, a: 0, b: 1/3 -> name tiebreak gives b, z, a (not input order)
        self.assertEqual([r['issue'] for r in out['tradeoff_order']], ['b', 'z', 'a'])

    def test_no_scores_no_confidence_no_rounding(self):
        text = json.dumps(m.run(req()))
        for banned in ('confidence', 'score', 'interval', '0.65'):
            self.assertNotIn(banned, text)

    def test_record_shape(self):
        out = m.run(req())
        self.assertEqual(set(out), {'efficient_allocation', 'tradeoff_order',
                                    'joint_gain_potential', 'logrolling_gain_vs_naive_split',
                                    'purely_distributive', 'tie_count', 'limits'})

    def test_determinism_permutations(self):
        a = json.dumps(m.run(req()), sort_keys=True)
        b = json.dumps(m.run(req()), sort_keys=True)
        self.assertEqual(a, b)


class TestSurvivorPins(unittest.TestCase):
    def test_limits_strings_exact(self):
        self.assertEqual(m.run(req())['limits'], [
            'This module is a bounded exact integrative-bargaining audit aid, not shipped product code.',
            'Weights are stated priorities normalized exactly per party; ordinal misstatements change the allocation.',
            'A tie is reported as tie; the audit never picks a holder on equal priorities.',
            'Logrolling analysis compares declared numbers only; it never manufactures issues or concessions.',
        ])

    def test_tradeoff_order_key_and_shape(self):
        out = m.run(req())
        self.assertIn('tradeoff_order', out)
        self.assertEqual(out['tradeoff_order'],
                         [{'issue': 'delivery', 'complementarity': '1/4'},
                          {'issue': 'price', 'complementarity': '1/4'}])
        for entry in out['tradeoff_order']:
            self.assertEqual(set(entry), {'issue', 'complementarity'})

    def test_deception_refused_before_unknown_keys(self):
        refusal({'aaa_unknown': 1, 'deceive': True}, 'DECEPTION_REQUEST:deceive')
        refusal({'zzz_unknown': 1, 'deceive': True}, 'DECEPTION_REQUEST:deceive')
        refusal({'aaa_unknown': 1, 'manipulate': True, 'zzz_unknown': 2},
                'DECEPTION_REQUEST:manipulate')


class TestWeightGrammar(unittest.TestCase):
    def test_grammar_refusals(self):
        for bad in (' 1/2', '1/2 ', '1e3', '1_0', '+1', '-1', '1.5', '١٢',
                    '1e100000', '1/0', '1//2', '/2', '1/', '9' * 41, '',
                    '0x10', '1 /2', '1/ 2', '1/2/3', 'nan', 'inf'):
            refusal(req(party_a_weights=[1, bad]), 'BAD_TYPE:weight')

    def test_digit_bound_is_18(self):
        refusal(req(party_a_weights=[1, '9' * 19]), 'BAD_TYPE:weight')
        refusal(req(party_a_weights=[1, '9' * 19 + '/1']), 'BAD_TYPE:weight')
        refusal(req(party_a_weights=[1, '1/' + '9' * 19]), 'BAD_TYPE:weight')
        out = m.run(req(party_a_weights=[1, '9' * 18], party_b_weights=[1, 1]))
        self.assertIn('efficient_allocation', out)

    def test_raw_length_checked_first(self):
        refusal(req(party_a_weights=[1, '1' * 41]), 'BAD_TYPE:weight')
        out = m.run(req(party_a_weights=[1, '9' * 18 + '/' + '9' * 18],
                        party_b_weights=[1, 1]))
        self.assertIn('efficient_allocation', out)

    def test_grammar_acceptances(self):
        out = m.run(req(party_a_weights=[0, '1/2'], party_b_weights=[1, '999999999999999999/1']))
        self.assertEqual(out['efficient_allocation'][1]['a_priority'], '1/1')

    def test_leading_zeros_allowed(self):
        out = m.run(req(party_a_weights=['007', '1/02'], party_b_weights=[1, 1]))
        self.assertEqual(out['efficient_allocation'][0]['a_priority'], '14/15')
        self.assertEqual(out['efficient_allocation'][1]['a_priority'], '1/15')

    def test_int_bounds(self):
        refusal(req(party_a_weights=[1, -1]), 'NEGATIVE:weight')
        refusal(req(party_a_weights=[1, 10**18]), 'OVERSIZE:weight')
        out = m.run(req(party_a_weights=[1, 10**18 - 1], party_b_weights=[1, 1]))
        self.assertIn('efficient_allocation', out)

    def test_bool_and_float_objects_still_refused(self):
        refusal(req(party_a_weights=[1, True]), 'BAD_TYPE:weight')
        refusal(req(party_a_weights=[1, 1.5]), 'BAD_TYPE:weight')
        refusal(req(party_a_weights=[1, None]), 'BAD_TYPE:weight')


class TestBatchCaps(unittest.TestCase):
    def test_request_key_count_cap(self):
        data = req(**{'k%02d' % i: 0 for i in range(61)})  # 64 keys total
        refusal(data, "UNKNOWN_KEY:'k00'")
        data = req(**{'k%02d' % i: 0 for i in range(62)})  # 65 keys total
        refusal(data, 'OVERSIZE:keys')

    def test_key_cap_before_iteration(self):
        data = {'deceive': True}
        data.update({'k%02d' % i: 0 for i in range(64)})  # 65 keys incl deception
        refusal(data, 'OVERSIZE:keys')

    def test_issues_cap_before_iteration(self):
        data = req(issues=[''] + ['i%02d' % i for i in range(64)],
                   party_a_weights=[1] * 65, party_b_weights=[1] * 65)
        refusal(data, 'OVERSIZE:issues')

    def test_key_type_and_length(self):
        data = req()
        data[1] = 0
        refusal(data, 'BAD_TYPE:key')
        refusal(req(**{'k' * 129: 0}), 'BAD_TYPE:key')
        refusal(req(**{'k' * 128: 0}), "UNKNOWN_KEY:'" + 'k' * 128 + "'")

    def test_key_unicode_screening(self):
        for ch in ('\x00', '\u200b', '\u2028', '\u2029', '\u0085'):
            refusal(req(**{'k' + ch: 0}), 'BAD_TYPE:key')
        for ch in ('\u00a0', '\u2003', '\u3000'):
            refusal(req(**{'k' + ch: 0}), "UNKNOWN_KEY:%r" % ('k' + ch,))

    def test_exact_type_spy(self):
        class ListSub(list):
            pass
        class DictSub(dict):
            pass
        refusal(DictSub(req()), 'BAD_TYPE:request')
        refusal(req(issues=ListSub(['a', 'b'])), 'BAD_TYPE:issues')
        refusal(req(party_a_weights=ListSub([1, 3])), 'LENGTH_MISMATCH')


if __name__ == '__main__':
    unittest.main()

