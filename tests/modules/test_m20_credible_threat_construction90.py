"""Row 90 bounded credible-consequence gate audit (CREDIB90).

Hermetic, stdlib-only; loads the module by file path. ROW90_MODULE_PATH
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
    'ROW90_MODULE_PATH',
    ROOT / 'backend/app/modules/m20_general_cognitive_worker/credible_threat_construction90.py'))
spec = importlib.util.spec_from_file_location('row90_under_test', PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def req(**over):
    base = {'consequence': 'we will decline to renew the contract',
            'lawful': True, 'proportionate': True, 'authorized': True,
            'basis': ['contract clause 4.2', 'board minute 2026-09-30']}
    base.update(over)
    return base


def refusal(data, code):
    try:
        m.run(data)
    except ValueError as e:
        assert str(e) == 'CREDIB90:' + code, str(e)
    else:
        raise AssertionError('no refusal for ' + code)


class TestRefusals(unittest.TestCase):
    def test_request_and_keys(self):
        refusal([], 'BAD_TYPE:request')
        refusal(req(extra=1), "UNKNOWN_KEY:'extra'")
        for key in ('harm', 'injure', 'coerce', 'punish', 'retaliate', 'violence'):
            refusal(req(**{key: True}), 'HARM_REQUEST:' + key)

    def test_consequence(self):
        refusal(req(consequence=None), 'BAD_TYPE:consequence')
        d = req(); del d['consequence']
        refusal(d, 'MISSING:consequence')
        refusal(req(consequence='  '), 'EMPTY:consequence')
        m.run(req(consequence='x' * 500))
        refusal(req(consequence='x' * 501), 'OVERSIZE:consequence')

    def test_condition_types(self):
        for field in ('lawful', 'proportionate', 'authorized'):
            refusal(req(**{field: 'yes'}), 'BAD_TYPE:' + field)
            refusal(req(**{field: 1}), 'BAD_TYPE:' + field)

    def test_echo_hygiene_seven_chars_per_field(self):
        # Fifteen characters pinned per str-typed field (this method's seven: three Cc (newline, tab,
        # NUL), DEL, Zl, Zp, and one Cf (zero-width space). Refusal codes carry
        # the field only, never the character or value.
        banned = ['\n', '\t', '\x00', '\x7f', '\u2028', '\u2029', '\u200b']
        for ch in banned:
            refusal(req(consequence='we will' + ch + 'decline'), 'UNCLEAN:consequence')
            refusal(req(basis=['clause' + ch + '4.2']), 'UNCLEAN:basis_entry')

    def test_echo_hygiene_extended_cf_pins(self):
        # Author-accepted broader guard (all Cc, Cf, Zl, Zp): four additional
        # Cf characters pinned per field. Categories tool-verified as Cf on
        # BOTH interpreters (U+061C ARABIC LETTER MARK; U+180E MONGOLIAN VOWEL
        # SEPARATOR - Cf under unidata 13.0.0 and 16.0.0 alike).
        for ch in ('­', '⁠', '؜', '᠎'):
            refusal(req(consequence='we will' + ch + 'decline'), 'UNCLEAN:consequence')
            refusal(req(basis=['clause' + ch + '4.2']), 'UNCLEAN:basis_entry')

    def test_echo_hygiene_final_four_refused(self):
        for ch in ('', '‪', '‮', '﻿'):
            refusal(req(consequence='we will' + ch + 'decline'), 'UNCLEAN:consequence')
            refusal(req(basis=['clause' + ch + '4.2']), 'UNCLEAN:basis_entry')

    def test_zs_accepted_and_echoed_verbatim(self):
        for ch in (' ', ' ', '　'):
            text = 'we will' + ch + 'decline to renew'
            out = m.run(req(consequence=text))
            self.assertEqual(out['declared_consequence'], text)
            out = m.run(req(basis=['clause' + ch + '4.2']))
            self.assertEqual(out['basis_count'], 1)

    def test_u2003_accepted_and_echoed_verbatim(self):
        text = 'we will decline to renew'
        out = m.run(req(consequence=text))
        self.assertEqual(out['declared_consequence'], text)
        out = m.run(req(basis=['clause 4.2']))
        self.assertEqual(out['basis_count'], 1)

    def test_raw_length_cap_first(self):
        # Length is capped on the raw string before any other content check:
        # a 501-char string carrying a banned char is OVERSIZE, not UNCLEAN.
        refusal(req(consequence='x' * 500 + '\n'), 'OVERSIZE:consequence')
        refusal(req(basis=['x' * 500 + '\n']), 'OVERSIZE:basis_entry')
        refusal(req(consequence=' ' * 501), 'OVERSIZE:consequence')
        m.run(req(consequence='x' * 500))
        m.run(req(basis=['x' * 500]))

    def test_no_strip_no_normalize_echo(self):
        out = m.run(req(consequence='  we will decline to renew  '))
        self.assertEqual(out['declared_consequence'], '  we will decline to renew  ')
        out = m.run(req(basis=['  clause 4.2  ']))
        self.assertEqual(out['basis_count'], 1)
        refusal(req(consequence='   '), 'EMPTY:consequence')
        refusal(req(consequence='\n'), 'EMPTY:consequence')
        refusal(req(basis=[' ']), 'BAD_TYPE:basis_entry')

    def test_basis(self):
        refusal(req(basis='x'), 'BAD_TYPE:basis')
        refusal(req(basis=['ok', 3]), 'BAD_TYPE:basis_entry')
        refusal(req(basis=['ok', 'ok']), 'DUPLICATE:basis')
        m.run(req(basis=['b%02d' % i for i in range(32)]))
        refusal(req(basis=['b%02d' % i for i in range(33)]), 'OVERSIZE:basis')


class TestMechanism(unittest.TestCase):
    def test_all_true_passes(self):
        out = m.run(req())
        self.assertEqual(out['gate'], 'pass')
        self.assertEqual(out['blocked_reasons'], [])
        self.assertEqual(out['conditions'], {'lawful': True, 'proportionate': True,
                                             'authorized': True})
        self.assertEqual(out['basis_count'], 2)
        self.assertEqual(out['declared_consequence'],
                         'we will decline to renew the contract')

    def test_each_false_blocks(self):
        for field in ('lawful', 'proportionate', 'authorized'):
            out = m.run(req(**{field: False}))
            self.assertEqual(out['gate'], 'blocked')
            self.assertEqual(out['blocked_reasons'], ['not_' + field])
        out = m.run(req(lawful=False, authorized=False))
        self.assertEqual(out['blocked_reasons'], ['not_authorized', 'not_lawful'])

    def test_no_scores_no_confidence(self):
        text = json.dumps(m.run(req()))
        for banned in ('score', 'confidence', 'estimate', 'probability'):
            self.assertNotIn(banned, text)

    def test_no_threat_text_generated(self):
        out = m.run(req())
        self.assertEqual(out['wording'], 'human_authored_required')
        self.assertEqual(set(out), {'declared_consequence', 'conditions', 'gate',
                                    'blocked_reasons', 'basis_count', 'wording', 'limits'})

    def test_determinism(self):
        self.assertEqual(json.dumps(m.run(req()), sort_keys=True),
                         json.dumps(m.run(req()), sort_keys=True))


if __name__ == '__main__':
    unittest.main()
