"""Row 89 bounded commitment-device structure audit (COMMIT89).

Hermetic, stdlib-only; loads the module by file path. ROW89_MODULE_PATH
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
    'ROW89_MODULE_PATH',
    ROOT / 'backend/app/modules/m20_general_cognitive_worker/commitment_device_creation89.py'))
spec = importlib.util.spec_from_file_location('row89_under_test', PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def req(**over):
    base = {'goal': 'finish the draft',
            'deadline': '2026-12-31',
            'checkins': ['2026-11-01', '2026-11-15', '2026-12-01'],
            'reversible': True}
    base.update(over)
    return base


def refusal(data, code):
    try:
        m.run(data)
    except ValueError as e:
        assert str(e) == 'COMMIT89:' + code, str(e)
    else:
        raise AssertionError('no refusal for ' + code)


class TestRefusals(unittest.TestCase):
    def test_request_and_keys(self):
        refusal([], 'BAD_TYPE:request')
        refusal(req(extra=1), "UNKNOWN_KEY:'extra'")
        for key in ('enforce', 'coerce', 'irrevocable', 'lock', 'punish'):
            refusal(req(**{key: True}), 'COERCE_REQUEST:' + key)

    def test_goal(self):
        refusal(req(goal=''), 'EMPTY:goal')
        refusal(req(goal=5), 'BAD_TYPE:goal')
        m.run(req(goal='x' * 200))
        refusal(req(goal='x' * 201), 'OVERSIZE:goal')

    def test_deadline(self):
        refusal(req(deadline='31-12-2026'), 'BAD_DATE:deadline')
        refusal(req(deadline='2026-02-30'), 'BAD_DATE:deadline')
        refusal(req(deadline=20261231), 'BAD_TYPE:deadline')

    def test_date_guard_uniform_refusals(self):
        # The strict gate (length cap, ASCII fullmatch, calendar validity) must
        # refuse identically on every interpreter; baseline fromisoformat parsed
        # basic and week dates on the newer interpreter and refused them on 3.10.
        for field in ('deadline', 'checkin'):
            label = field
            for bad in ('20261231', '2026-W52-5', '2026-W01-1', '2026-12-31\n',
                        '٢٠٢٦-١٢-٣١', '2026-02-30', '2026-13-01'):
                if field == 'deadline':
                    refusal(req(deadline=bad), 'BAD_DATE:' + label)
                else:
                    refusal(req(checkins=[bad]), 'BAD_DATE:' + label)
            for bad in (20261231, None, b'2026-12-31'):
                if field == 'deadline':
                    refusal(req(deadline=bad), 'BAD_TYPE:' + label)
                else:
                    refusal(req(checkins=[bad]), 'BAD_TYPE:' + label)
            if field == 'deadline':
                refusal(req(deadline='2' * 65), 'OVERSIZE:' + label)
                refusal(req(deadline='x' * 65), 'OVERSIZE:' + label)
            else:
                refusal(req(checkins=['2' * 65]), 'OVERSIZE:' + label)
                refusal(req(checkins=['x' * 65]), 'OVERSIZE:' + label)
        # At-cap 64-char non-date strings are BAD_DATE (format), not OVERSIZE:
        # the raw length cap only refuses above 64.
        refusal(req(deadline='2' * 64), 'BAD_DATE:deadline')
        refusal(req(checkins=['2' * 64]), 'BAD_DATE:checkin')
        out = m.run(req(deadline='2026-12-31', checkins=['2026-12-01']))
        self.assertEqual(out['deadline'], '2026-12-31')
        self.assertEqual(out['checkins'], ['2026-12-01'])

    def test_checkins(self):
        refusal(req(checkins='2026-11-01'), 'BAD_TYPE:checkins')
        refusal(req(checkins=['2026-13-01']), 'BAD_DATE:checkin')
        refusal(req(checkins=['2026-11-01', '2026-11-01']), 'DUPLICATE:checkin')
        m.run(req(checkins=['2026-11-%02d' % i for i in range(1, 29)] + ['2026-12-%02d' % i for i in range(1, 29)] + ['2026-10-%02d' % i for i in range(1, 9)]))
        refusal(req(checkins=['2026-11-%02d' % i for i in range(1, 29)] + ['2026-12-%02d' % i for i in range(1, 29)] + ['2026-10-%02d' % i for i in range(1, 10)]), 'OVERSIZE:checkins')

    def test_irrevocable_refused(self):
        refusal(req(reversible=False), 'IRREVOCABLE')
        refusal(req(reversible='yes'), 'BAD_TYPE:reversible')

    def test_penalty_echo_only(self):
        out = m.run(req(self_selected_penalty='donate 5 to charity'))
        self.assertEqual(out['checklist']['penalty_declared'], True)
        refusal(req(self_selected_penalty=5), 'BAD_TYPE:penalty')


class TestMechanism(unittest.TestCase):
    def test_structure_audit_exact(self):
        out = m.run(req())
        self.assertEqual(out['checkin_count'], 3)
        self.assertEqual(out['checkins_before_deadline'], 3)
        self.assertEqual(out['checkins_after_deadline'], 0)
        self.assertEqual(out['coverage_ratio'], '1/1')
        self.assertEqual(out['first_to_last_spacing_days'], 30)
        self.assertEqual(out['verdict'], 'structurally_complete')
        self.assertEqual(out['checklist'], {
            'has_goal': True, 'has_deadline': True, 'has_checkins': True,
            'all_checkins_before_deadline': True, 'owner_revocable': True,
            'penalty_declared': False})

    def test_after_deadline_and_verdict(self):
        out = m.run(req(checkins=['2027-01-05']))
        self.assertEqual(out['checkins_before_deadline'], 0)
        self.assertEqual(out['checkins_after_deadline'], 1)
        self.assertEqual(out['coverage_ratio'], '0/1')
        self.assertEqual(out['checklist']['all_checkins_before_deadline'], False)
        self.assertEqual(out['verdict'], 'missing_properties')
        self.assertIn('all_checkins_before_deadline', out['missing'])

    def test_no_checkins(self):
        out = m.run(req(checkins=[]))
        self.assertEqual(out['coverage_ratio'], '0/1')
        self.assertEqual(out['checklist']['has_checkins'], False)
        self.assertEqual(out['missing'], ['has_checkins'])
        self.assertEqual(out['first_to_last_spacing_days'], 0)

    def test_absent_reversible_defaults_owner_revocable(self):
        data = req()
        del data['reversible']
        out = m.run(data)
        self.assertIs(out['checklist']['owner_revocable'], True)

    def test_penalty_flag_only_limits_disclosure(self):
        out = m.run(req(self_selected_penalty='donate 5 to charity'))
        self.assertIn('The penalty value is not echoed; the output reports only whether a penalty was declared (penalty_declared, a boolean). It is never created, enforced or escalated.',
                      out['limits'])
        self.assertNotIn('donate 5 to charity', json.dumps(out))
        self.assertIs(out['checklist']['penalty_declared'], True)
        self.assertIsInstance(out['checklist']['penalty_declared'], bool)

    def test_no_scores_no_estimates(self):
        out = m.run(req())
        text = json.dumps(out)
        for banned in ('strength', 'estimate', 'interval', 'confidence', 'score'):
            self.assertNotIn(banned, text)

    def test_record_shape(self):
        out = m.run(req())
        self.assertEqual(set(out), {'goal', 'deadline', 'checkins', 'checkin_count',
                                    'checkins_before_deadline', 'checkins_after_deadline',
                                    'coverage_ratio', 'first_to_last_spacing_days',
                                    'checklist', 'missing', 'verdict', 'limits'})
        self.assertEqual(out['checkins'], ['2026-11-01', '2026-11-15', '2026-12-01'])

    def test_checkin_on_deadline_counts_as_before(self):
        out = m.run(req(checkins=['2026-12-31']))
        self.assertEqual(out['checkins_before_deadline'], 1)
        self.assertEqual(out['checkins_after_deadline'], 0)
        self.assertEqual(out['coverage_ratio'], '1/1')

    def test_unsorted_input_is_sorted(self):
        out = m.run(req(checkins=['2026-12-01', '2026-11-01', '2026-11-15']))
        self.assertEqual(out['checkins'], ['2026-11-01', '2026-11-15', '2026-12-01'])
        self.assertEqual(out['first_to_last_spacing_days'], 30)

    def test_determinism(self):
        self.assertEqual(json.dumps(m.run(req()), sort_keys=True),
                         json.dumps(m.run(req()), sort_keys=True))


if __name__ == '__main__':
    unittest.main()
