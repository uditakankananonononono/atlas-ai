"""Row 708 bounded code-formatting declaration bookkeeping (CODEFO708).

Hermetic, stdlib-only; loads the module by file path. ROW708_MODULE_PATH
overrides the path for mutation runs. Sample data is synthetic.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
PATH = pathlib.Path(os.environ.get(
    'ROW708_MODULE_PATH',
    ROOT / 'backend/app/modules/m20_general_cognitive_worker/code_formatting708.py'))
spec = importlib.util.spec_from_file_location('row708_under_test', PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def style(**over):
    base = {'name': 'team-style-a', 'indent': 'spaces', 'indent_width': 4, 'max_line_length': 40,
            'line_ending': 'lf', 'final_newline': True}
    base.update(over)
    return base


def req(**over):
    base = {'style': style(),
            'files': [{'path': 'src/a.py', 'before': 'x=1\n', 'after': 'x = 1\n'}]}
    base.update(over)
    return base


def refuse(test, request, suffix):
    with test.assertRaises(ValueError) as ctx:
        m.run(request)
    test.assertEqual(str(ctx.exception), 'CODEFO708:' + suffix)


class Basics(unittest.TestCase):
    def test_changed_whitespace_only_file_exact(self):
        out = m.run(req())
        f = out['files'][0]
        self.assertEqual(f['path'], 'src/a.py')
        self.assertIs(f['changed'], True)
        self.assertIs(f['whitespace_only_change'], True)
        self.assertEqual(f['before_sha256'], sha('x=1\n'))
        self.assertEqual(f['after_sha256'], sha('x = 1\n'))
        self.assertEqual(f['before_chars'], 4)
        self.assertEqual(f['after_chars'], 6)
        self.assertEqual(out['changed_paths'], ['src/a.py'])
        self.assertEqual(out['counts'], {'files': 1, 'changed': 1, 'unchanged': 0,
                                          'whitespace_only': 1, 'with_style_findings': 0})

    def test_unchanged_file(self):
        out = m.run(req(files=[{'path': 'b.py', 'before': 'y = 2\n', 'after': 'y = 2\n'}]))
        f = out['files'][0]
        self.assertIs(f['changed'], False)
        self.assertIs(f['whitespace_only_change'], False)
        self.assertEqual(out['changed_paths'], [])
        self.assertEqual(out['counts']['unchanged'], 1)

    def test_non_whitespace_change_is_not_whitespace_only(self):
        out = m.run(req(files=[{'path': 'c.py', 'before': 'x = 1\n', 'after': 'x = 2\n'}]))
        self.assertIs(out['files'][0]['whitespace_only_change'], False)
        self.assertEqual(out['counts']['whitespace_only'], 0)

    def test_whitespace_only_means_equal_after_removing_all_whitespace(self):
        out = m.run(req(files=[{'path': 'c.py', 'before': 'a b\n', 'after': 'ab\n'}]))
        self.assertIs(out['files'][0]['whitespace_only_change'], True)

    def test_empty_files_list_ok(self):
        out = m.run(req(files=[]))
        self.assertEqual(out['files'], [])
        self.assertEqual(out['counts'], {'files': 0, 'changed': 0, 'unchanged': 0,
                                          'whitespace_only': 0, 'with_style_findings': 0})

    def test_order_preserved_and_changed_paths_in_order(self):
        files = [{'path': 'z.py', 'before': 'a', 'after': 'b'}, {'path': 'a.py', 'before': 'q', 'after': 'q'},
                 {'path': 'm.py', 'before': 'c', 'after': 'd'}]
        out = m.run(req(files=files, style=style(final_newline=False)))
        self.assertEqual([f['path'] for f in out['files']], ['z.py', 'a.py', 'm.py'])
        self.assertEqual(out['changed_paths'], ['z.py', 'm.py'])

    def test_input_not_mutated_and_deterministic(self):
        r = req()
        before = json.dumps(r, sort_keys=True)
        a = m.run(r)
        b = m.run(r)
        self.assertEqual(json.dumps(r, sort_keys=True), before)
        self.assertEqual(a, b)

    def test_pinned_non_claims(self):
        out = m.run(req())
        self.assertIs(out['formatter_executed'], False)
        self.assertIs(out['semantics_verified'], False)
        self.assertIs(out['style_authority'], False)
        self.assertIs(out['idempotence_proven'], False)
        self.assertIn('limits', out)
        self.assertGreaterEqual(len(out['limits']), 4)
        self.assertEqual(out['style'], style())


class StyleObservations(unittest.TestCase):
    def one(self, after, **sty):
        return m.run(req(style=style(**sty), files=[{'path': 'f.txt', 'before': '', 'after': after}]))['files'][0]

    def test_long_lines_boundary(self):
        ok = self.one('x' * 40 + '\n')
        self.assertEqual(ok['style_findings']['long_lines'], [])
        bad = self.one('ok\n' + 'x' * 41 + '\n')
        self.assertEqual(bad['style_findings']['long_lines'], [2])
        self.assertEqual(bad['style_findings']['long_line_count'], 1)

    def test_trailing_whitespace_lines(self):
        f = self.one('a \nb\nc\t\n')
        self.assertEqual(f['style_findings']['trailing_whitespace_lines'], [1, 3])
        self.assertEqual(f['style_findings']['trailing_whitespace_count'], 2)

    def test_indent_mismatch_spaces_style(self):
        f = self.one('\tindented\n    ok\n')
        self.assertEqual(f['style_findings']['indent_mismatch_lines'], [1])

    def test_indent_mismatch_tabs_style(self):
        f = self.one('    spaced\n\tok\n', indent='tabs')
        self.assertEqual(f['style_findings']['indent_mismatch_lines'], [1])

    def test_indent_width_multiple(self):
        f = self.one('  two\n    four\n      six\n')
        self.assertEqual(f['style_findings']['indent_width_lines'], [1, 3])

    def test_line_ending_lf_and_crlf(self):
        lf = self.one('a\r\nb\n')
        self.assertEqual(lf['style_findings']['wrong_line_ending_lines'], [1])
        crlf = self.one('a\r\nb\n', line_ending='crlf')
        self.assertEqual(crlf['style_findings']['wrong_line_ending_lines'], [2])

    def test_final_newline(self):
        self.assertIs(self.one('a')['style_findings']['final_newline_ok'], False)
        self.assertIs(self.one('a\n')['style_findings']['final_newline_ok'], True)
        self.assertIs(self.one('a', final_newline=False)['style_findings']['final_newline_ok'], True)
        self.assertIs(self.one('a\n', final_newline=False)['style_findings']['final_newline_ok'], False)
        self.assertIs(self.one('')['style_findings']['final_newline_ok'], True)

    def test_findings_flag_and_count(self):
        out = m.run(req(files=[{'path': 'a', 'before': '', 'after': 'x\n'},
                               {'path': 'b', 'before': '', 'after': 'x '}]))
        self.assertIs(out['files'][0]['has_style_findings'], False)
        self.assertIs(out['files'][1]['has_style_findings'], True)
        self.assertEqual(out['counts']['with_style_findings'], 1)

    def test_findings_are_capped_but_counts_are_exact(self):
        text = ''.join('x \n' for _ in range(30))
        f = self.one(text)
        self.assertEqual(len(f['style_findings']['trailing_whitespace_lines']), 20)
        self.assertEqual(f['style_findings']['trailing_whitespace_lines'][-1], 20)
        self.assertEqual(f['style_findings']['trailing_whitespace_count'], 30)

    def test_before_is_not_style_checked(self):
        out = m.run(req(files=[{'path': 'a', 'before': 'x ' * 100, 'after': 'x\n'}]))
        self.assertIs(out['files'][0]['has_style_findings'], False)


class Idempotence(unittest.TestCase):
    def test_second_pass_equal_declared_idempotent(self):
        f = m.run(req(files=[{'path': 'a', 'before': 'x=1\n', 'after': 'x = 1\n', 'second_pass': 'x = 1\n'}]))['files'][0]
        self.assertEqual(f['idempotence'], 'second_pass_equal')

    def test_second_pass_different(self):
        f = m.run(req(files=[{'path': 'a', 'before': 'x=1\n', 'after': 'x = 1\n', 'second_pass': 'x  =  1\n'}]))['files'][0]
        self.assertEqual(f['idempotence'], 'second_pass_differs')

    def test_second_pass_absent(self):
        self.assertEqual(m.run(req())['files'][0]['idempotence'], 'second_pass_not_supplied')

    def test_counts_second_pass(self):
        out = m.run(req(files=[
            {'path': 'a', 'before': 'x', 'after': 'y', 'second_pass': 'y'},
            {'path': 'b', 'before': 'x', 'after': 'y', 'second_pass': 'z'},
            {'path': 'c', 'before': 'x', 'after': 'y'}]))
        self.assertEqual(out['idempotence_counts'], {'second_pass_equal': 1, 'second_pass_differs': 1,
                                                    'second_pass_not_supplied': 1})
        self.assertIs(out['idempotence_proven'], False)


class Refusals(unittest.TestCase):
    def test_request_type(self):
        for bad in (None, [], 'x', 3):
            refuse(self, bad, 'BAD_TYPE:request')

    def test_unknown_and_required_keys(self):
        r = req(); r['extra'] = 1
        refuse(self, r, 'UNKNOWN_KEY:request')
        refuse(self, {'files': []}, 'MISSING:style')
        refuse(self, {'style': style()}, 'MISSING:files')

    def test_execution_and_authority_keys_refused(self):
        for key in ('run', 'command', 'execute', 'formatter_command', 'apply', 'write', 'commit', 'push'):
            r = req(); r[key] = 'x'
            refuse(self, r, 'EXEC_REQUEST:' + key)
        for key in ('certify', 'approve', 'style_authority', 'release'):
            r = req(); r[key] = True
            refuse(self, r, 'CLAIM_REQUEST:' + key)

    def test_style_type_and_unknown_keys(self):
        refuse(self, req(style=[]), 'BAD_TYPE:style')
        s = style(); s['zzz'] = 1
        refuse(self, req(style=s), 'UNKNOWN_KEY:style')
        s = style(); del s['name']
        refuse(self, req(style=s), 'MISSING:style.name')

    def test_style_values(self):
        refuse(self, req(style=style(name='')), 'BAD_TYPE:style.name')
        refuse(self, req(style=style(name='   ')), 'BAD_TYPE:style.name')
        refuse(self, req(style=style(name='n' * 65)), 'OVERSIZE:style.name')
        m.run(req(style=style(name='n' * 64)))
        refuse(self, req(style=style(indent='mixed')), 'BAD_STYLE:indent')
        refuse(self, req(style=style(line_ending='cr')), 'BAD_STYLE:line_ending')
        refuse(self, req(style=style(final_newline='yes')), 'BAD_TYPE:style.final_newline')

    def test_integer_bounds(self):
        for key, lo, hi in (('indent_width', 1, 16), ('max_line_length', 20, 400)):
            m.run(req(style=style(**{key: lo})))
            m.run(req(style=style(**{key: hi})))
            refuse(self, req(style=style(**{key: lo - 1})), 'BAD_RANGE:style.' + key)
            refuse(self, req(style=style(**{key: hi + 1})), 'BAD_RANGE:style.' + key)
            refuse(self, req(style=style(**{key: True})), 'BAD_TYPE:style.' + key)
            refuse(self, req(style=style(**{key: 4.0})), 'BAD_TYPE:style.' + key)
            refuse(self, req(style=style(**{key: '4'})), 'BAD_TYPE:style.' + key)

    def test_files_type_and_entries(self):
        refuse(self, req(files='x'), 'BAD_TYPE:files')
        refuse(self, req(files=[1]), 'BAD_TYPE:file')
        refuse(self, req(files=[{'path': 'a', 'before': 'x'}]), 'MISSING:file.after')
        refuse(self, req(files=[{'before': 'x', 'after': 'x'}]), 'MISSING:file.path')
        refuse(self, req(files=[{'path': 'a', 'before': 'x', 'after': 'x', 'k': 1}]), 'UNKNOWN_KEY:file')
        refuse(self, req(files=[{'path': 'a', 'before': 1, 'after': 'x'}]), 'BAD_TYPE:file.before')
        refuse(self, req(files=[{'path': 'a', 'before': 'x', 'after': None}]), 'BAD_TYPE:file.after')
        refuse(self, req(files=[{'path': 'a', 'before': 'x', 'after': 'x', 'second_pass': 3}]), 'BAD_TYPE:file.second_pass')

    def test_paths(self):
        for bad in ('/abs.py', '../up.py', 'a/../b.py', 'a\\b.py', 'a\x00b', '', '  ', 'a\nb', 'C:evil'):
            refuse(self, req(files=[{'path': bad, 'before': '', 'after': ''}]), 'BAD_PATH')
        refuse(self, req(files=[{'path': 5, 'before': '', 'after': ''}]), 'BAD_TYPE:file.path')
        refuse(self, req(files=[{'path': 'p' * 257, 'before': '', 'after': ''}]), 'OVERSIZE:path')
        m.run(req(files=[{'path': 'p' * 256, 'before': '', 'after': ''}]))
        m.run(req(files=[{'path': 'a..b/c.py', 'before': '', 'after': ''}]))

    def test_duplicate_paths(self):
        files = [{'path': 'a', 'before': '', 'after': ''}, {'path': 'a', 'before': '', 'after': ''}]
        refuse(self, req(files=files), 'DUPLICATE:path')

    def test_bounds(self):
        ok = [{'path': 'f%d' % i, 'before': '', 'after': ''} for i in range(64)]
        self.assertEqual(m.run(req(files=ok))['counts']['files'], 64)
        refuse(self, req(files=ok + [{'path': 'f64', 'before': '', 'after': ''}]), 'OVERSIZE:files')
        big = 'x' * 100000
        m.run(req(style=style(max_line_length=400), files=[{'path': 'a', 'before': big, 'after': big[:-1]}]))
        refuse(self, req(files=[{'path': 'a', 'before': big + 'x', 'after': ''}]), 'OVERSIZE:content')
        refuse(self, req(files=[{'path': 'a', 'before': '', 'after': big + 'x'}]), 'OVERSIZE:content')
        refuse(self, req(files=[{'path': 'a', 'before': '', 'after': '', 'second_pass': big + 'x'}]), 'OVERSIZE:content')
        many = [{'path': 'f%d' % i, 'before': 'x' * 100000, 'after': 'x' * 100000} for i in range(6)]
        refuse(self, req(files=many), 'OVERSIZE:total')
        five = many[:5]
        self.assertEqual(m.run(req(style=style(max_line_length=400), files=five))['counts']['files'], 5)


class Pins(unittest.TestCase):
    def test_total_boundary_exact_plus_one(self):
        five = [{'path': 'f%d' % i, 'before': 'x' * 100000, 'after': 'x' * 100000} for i in range(5)]
        sty = style(max_line_length=400)
        self.assertEqual(m.run(req(style=sty, files=five))['counts']['files'], 5)
        refuse(self, req(style=sty, files=five + [{'path': 'g', 'before': 'x', 'after': ''}]), 'OVERSIZE:total')
        refuse(self, req(style=sty, files=five[:4] + [{'path': 'g', 'before': 'x' * 100000, 'after': 'x' * 100000,
                                                       'second_pass': 'x'}]), 'OVERSIZE:total')

    def test_final_newline_alone_and_trailing_alone_set_flag(self):
        out = m.run(req(files=[{'path': 'a', 'before': '', 'after': 'a'}, {'path': 'b', 'before': '', 'after': 'x \n'}]))
        self.assertIs(out['files'][0]['has_style_findings'], True)
        self.assertEqual(out['files'][0]['style_findings']['trailing_whitespace_count'], 0)
        self.assertIs(out['files'][1]['has_style_findings'], True)
        self.assertIs(out['files'][1]['style_findings']['final_newline_ok'], True)

    def test_last_line_without_newline_has_no_ending_check(self):
        def endings(after, **sty):
            f = m.run(req(style=style(**sty), files=[{'path': 'a', 'before': '', 'after': after}]))['files'][0]
            return f['style_findings']['wrong_line_ending_lines']
        self.assertEqual(endings('a\r\nb', line_ending='crlf', final_newline=False), [])
        self.assertEqual(endings('a\r\nb', final_newline=False), [1])
        self.assertEqual(endings('a\nb', line_ending='crlf', final_newline=False), [1])
        self.assertEqual(endings('a\n', line_ending='crlf'), [1])

    def test_name_non_string_refused(self):
        refuse(self, req(style=style(name=5)), 'BAD_TYPE:style.name')
        refuse(self, req(style=style(name=None)), 'BAD_TYPE:style.name')

    def test_encoding_refused_per_field(self):
        bad = '\ud800'
        refuse(self, req(files=[{'path': 'a', 'before': bad, 'after': ''}]), 'ENCODING:before')
        refuse(self, req(files=[{'path': 'a', 'before': '', 'after': bad}]), 'ENCODING:after')
        refuse(self, req(files=[{'path': 'a', 'before': '', 'after': '', 'second_pass': bad}]), 'ENCODING:second_pass')

    def test_path_character_boundaries(self):
        for ok in ('a b.py', 'a~b', 'a\u00a0b', 'a\u3000b/c d.py'):
            m.run(req(files=[{'path': ok, 'before': '', 'after': ''}]))
        for bad in ('a\x1fb', 'a\x7fb', 'a\x80b', 'a\x9fb', 'a\tb', 'a\rb'):
            refuse(self, req(files=[{'path': bad, 'before': '', 'after': ''}]), 'BAD_PATH')

    def test_crlf_long_line_boundary(self):
        def longs(body):
            return m.run(req(style=style(line_ending='crlf'),
                             files=[{'path': 'a', 'before': '', 'after': body}]))['files'][0]['style_findings']['long_lines']
        self.assertEqual(longs('x' * 40 + '\r\n'), [])
        self.assertEqual(longs('x' * 41 + '\r\n'), [1])
        self.assertEqual(longs('y\r\n' + 'x' * 41 + '\r\n'), [2])


import sys as _sys
import unicodedata as _ud

_CF = [chr(c) for c in range(_sys.maxunicode + 1) if _ud.category(chr(c)) == 'Cf']


class TextPolicy(unittest.TestCase):
    """Count-first, raw-length-before-strip, and Cc/Cf/Zl/Zp refusal for echoed or hashed text."""

    def test_cf_category_is_fully_covered_and_includes_named_pins(self):
        self.assertGreater(len(_CF), 100)
        self.assertIn('\u00ad', _CF)
        self.assertIn('\u2060', _CF)

    def test_every_cf_char_refused_in_name_path_and_content(self):
        for ch in _CF:
            refuse(self, req(style=style(name='n' + ch)), 'CONTROL_CHARS:style.name')
            refuse(self, req(files=[{'path': 'a' + ch, 'before': '', 'after': ''}]), 'BAD_PATH')
            for field in ('before', 'after', 'second_pass'):
                item = {'path': 'a', 'before': '', 'after': ''}
                item[field] = 'x' + ch
                refuse(self, req(files=[item]), 'CONTROL_CHARS:' + field)

    def test_soft_hyphen_and_word_joiner_explicit(self):
        for ch in ('\u00ad', '\u2060'):
            refuse(self, req(style=style(name='a' + ch + 'b')), 'CONTROL_CHARS:style.name')
            refuse(self, req(files=[{'path': 'a' + ch + 'b.py', 'before': '', 'after': ''}]), 'BAD_PATH')
            refuse(self, req(files=[{'path': 'a', 'before': 'a' + ch + 'b', 'after': ''}]), 'CONTROL_CHARS:before')

    def test_zl_zp_and_cc_refused_zs_accepted(self):
        for ch in ('\u2028', '\u2029', '\x00', '\x85', '\x1b', '\x7f'):
            refuse(self, req(style=style(name='a' + ch)), 'CONTROL_CHARS:style.name')
            refuse(self, req(files=[{'path': 'a', 'before': 'x' + ch, 'after': ''}]), 'CONTROL_CHARS:before')
            refuse(self, req(files=[{'path': 'a', 'before': '', 'after': 'x' + ch}]), 'CONTROL_CHARS:after')
        for ch in ('\u00a0', '\u3000', '\u2003', ' '):
            out = m.run(req(style=style(name='a' + ch + 'b'),
                            files=[{'path': 'a', 'before': 'x' + ch, 'after': 'x' + ch + '\n'}]))
            self.assertEqual(out['style']['name'], 'a' + ch + 'b')

    def test_content_keeps_lf_cr_tab(self):
        out = m.run(req(files=[{'path': 'a', 'before': 'a\tb\r\nc\n', 'after': 'a\tb\r\nc\n'}]))
        self.assertIs(out['files'][0]['changed'], False)

    def test_raw_length_cap_before_strip_and_unicode_check(self):
        # 65 chars where the only non-name char is a Cf: the length refusal must win over the char refusal
        refuse(self, req(style=style(name='\u00ad' * 65)), 'OVERSIZE:style.name')
        refuse(self, req(style=style(name=' ' * 65)), 'OVERSIZE:style.name')
        refuse(self, req(files=[{'path': '\u00ad' * 257, 'before': '', 'after': ''}]), 'OVERSIZE:path')
        refuse(self, req(files=[{'path': 'a', 'before': '\u00ad' * 100001, 'after': ''}]), 'OVERSIZE:content')
        refuse(self, req(files=[{'path': 'a', 'before': '', 'after': '\u2028' * 100001}]), 'OVERSIZE:content')

    def test_count_first_on_every_container(self):
        class Boom(dict):
            def __iter__(self):
                raise AssertionError('iterated before count check')
            def keys(self):
                raise AssertionError('keys before count check')
            def items(self):
                raise AssertionError('items before count check')
        # subclasses are refused by strict type before any iteration or count
        refuse(self, Boom({'k%d' % i: 1 for i in range(17)}), 'BAD_TYPE:request')
        refuse(self, req(style=Boom({'k%d' % i: 1 for i in range(17)})), 'BAD_TYPE:style')
        refuse(self, req(files=[Boom({'k%d' % i: 1 for i in range(9)})]), 'BAD_TYPE:file')

        class BoomList(list):
            def __iter__(self):
                raise AssertionError('iterated before count check')
        refuse(self, req(files=BoomList([{}] * 65)), 'BAD_TYPE:files')
        # plain containers: count is refused before any key is inspected
        big = {'k%d' % i: 1 for i in range(16)}
        big['run'] = 1
        refuse(self, big, 'OVERSIZE:keys')
        refuse(self, req(files=[{}] * 65), 'OVERSIZE:files')

    def test_key_count_boundaries(self):
        r = {'style': style(), 'files': []}
        for i in range(14):
            r['k%d' % i] = 1
        self.assertEqual(len(r), 16)
        refuse(self, r, 'UNKNOWN_KEY:request')          # 16 keys reaches the key check
        r['k14'] = 1
        refuse(self, r, 'OVERSIZE:keys')              # 17 keys refused by count first
        s = style()
        for i in range(10):
            s['k%d' % i] = 1
        self.assertEqual(len(s), 16)
        refuse(self, req(style=s), 'UNKNOWN_KEY:style')
        s['k10'] = 1
        refuse(self, req(style=s), 'OVERSIZE:style.keys')
        f = {'path': 'a', 'before': '', 'after': ''}
        for i in range(5):
            f['k%d' % i] = 1
        self.assertEqual(len(f), 8)
        refuse(self, req(files=[f]), 'UNKNOWN_KEY:file')
        f['k5'] = 1
        refuse(self, req(files=[f]), 'OVERSIZE:file.keys')

    def test_surrogate_residual_unchanged(self):
        # existing behaviour, not a new refusal: a lone surrogate cannot be hashed, so content is refused by the existing encode guard
        refuse(self, req(files=[{'path': 'a', 'before': '\ud800', 'after': ''}]), 'ENCODING:before')


class StrictTypesAndFixedReasons(unittest.TestCase):
    """v3: fixed unknown-key reasons, strict builtin types, enum raw cap first."""

    def test_unknown_key_reasons_never_echo_the_key(self):
        secret = 'SECRETKEY'
        for r, want in ((req(**{secret: 1}), 'UNKNOWN_KEY:request'),
                        (req(style=dict(style(), **{secret: 1})), 'UNKNOWN_KEY:style'),
                        (req(files=[{'path': 'a', 'before': '', 'after': '', secret: 1}]), 'UNKNOWN_KEY:file')):
            with self.assertRaises(ValueError) as ctx:
                m.run(r)
            self.assertEqual(str(ctx.exception), 'CODEFO708:' + want)
            self.assertNotIn(secret, str(ctx.exception))

    def test_non_str_keys_fixed_reason(self):
        refuse(self, {1: 2, 'style': style(), 'files': []}, 'UNKNOWN_KEY:request')
        refuse(self, req(style=dict(style(), **{}) | {(1, 2): 3}), 'UNKNOWN_KEY:style')
        refuse(self, req(files=[{'path': 'a', 'before': '', 'after': '', None: 1}]), 'UNKNOWN_KEY:file')

    def test_str_subclass_key_for_exec_name_not_echoed(self):
        class K(str):
            def __str__(self):
                return 'LEAK'
        r = {K('run'): 1, 'style': style(), 'files': []}
        with self.assertRaises(ValueError) as ctx:
            m.run(r)
        self.assertEqual(str(ctx.exception), 'CODEFO708:UNKNOWN_KEY:request')

    def test_container_subclasses_refused(self):
        class D(dict):
            pass

        class L(list):
            pass
        refuse(self, D(req()), 'BAD_TYPE:request')
        refuse(self, req(style=D(style())), 'BAD_TYPE:style')
        refuse(self, req(files=L()), 'BAD_TYPE:files')
        refuse(self, req(files=[D(path='a', before='', after='')]), 'BAD_TYPE:file')

    def test_str_subclasses_refused(self):
        class S(str):
            pass
        refuse(self, req(style=style(name=S('n'))), 'BAD_TYPE:style.name')
        refuse(self, req(style=style(indent=S('spaces'))), 'BAD_TYPE:style.indent')
        refuse(self, req(style=style(line_ending=S('lf'))), 'BAD_TYPE:style.line_ending')
        refuse(self, req(files=[{'path': S('a'), 'before': '', 'after': ''}]), 'BAD_TYPE:file.path')
        refuse(self, req(files=[{'path': 'a', 'before': S(''), 'after': ''}]), 'BAD_TYPE:file.before')
        refuse(self, req(files=[{'path': 'a', 'before': '', 'after': '', 'second_pass': S('')}]), 'BAD_TYPE:file.second_pass')

    def test_number_and_bool_strictness(self):
        class I(int):
            pass
        refuse(self, req(style=style(indent_width=True)), 'BAD_TYPE:style.indent_width')
        refuse(self, req(style=style(max_line_length=True)), 'BAD_TYPE:style.max_line_length')
        refuse(self, req(style=style(indent_width=I(4))), 'BAD_TYPE:style.indent_width')
        refuse(self, req(style=style(indent_width=4.0)), 'BAD_TYPE:style.indent_width')
        class B:
            pass
        refuse(self, req(style=style(final_newline=1)), 'BAD_TYPE:style.final_newline')
        self.assertEqual(m.run(req(style=style(indent_width=4)))['style']['indent_width'], 4)

    def test_enum_type_then_raw_cap_before_membership(self):
        refuse(self, req(style=style(indent=1)), 'BAD_TYPE:style.indent')
        refuse(self, req(style=style(line_ending=None)), 'BAD_TYPE:style.line_ending')
        refuse(self, req(style=style(indent='x' * 9)), 'OVERSIZE:style.indent')
        refuse(self, req(style=style(line_ending='y' * 9)), 'OVERSIZE:style.line_ending')
        refuse(self, req(style=style(indent='x' * 8)), 'BAD_STYLE:indent')
        refuse(self, req(style=style(line_ending='cr')), 'BAD_STYLE:line_ending')


if __name__ == '__main__':
    unittest.main()


class GatePins(unittest.TestCase):
    """Auditor-5 closing pins (tests-only; runtime ec61bba0 unchanged)."""

    def test_vertical_tab_refused_in_content(self):
        # _CONTENT_WS exempts only \n \r \t; a VT (Cc) must still be refused
        refuse(self, req(files=[{'path': 'a.py', 'before': 'x=1\n', 'after': 'x =\x0b1\n'}]),
               'CONTROL_CHARS:after')
        refuse(self, req(files=[{'path': 'a.py', 'before': 'x=\x0b1\n', 'after': 'x = 1\n'}]),
               'CONTROL_CHARS:before')

    def test_missing_before_key_refused(self):
        refuse(self, req(files=[{'path': 'a.py', 'after': 'x = 1\n'}]), 'MISSING:file.before')

    def test_crlf_trailing_space_is_trailing_finding(self):
        # check runs on the content with \r stripped, not on the raw line
        out = m.run(req(style=style(line_ending='crlf'),
                        files=[{'path': 'a.py', 'before': 'x\r\n', 'after': 'x \r\n'}]))
        f = out['files'][0]['style_findings']
        self.assertEqual(f['trailing_whitespace_lines'], [1])
        self.assertEqual(f['trailing_whitespace_count'], 1)
        self.assertEqual(f['wrong_line_ending_lines'], [])

    def test_whitespace_only_line_skips_indent_and_width_checks(self):
        out = m.run(req(files=[{'path': 'a.py', 'before': 'x = 1\n', 'after': '   \n'}]))
        f = out['files'][0]['style_findings']
        self.assertEqual(f['indent_width_lines'], [])
        self.assertEqual(f['indent_width_count'], 0)
        self.assertEqual(f['indent_mismatch_lines'], [])

    def test_indent_remainder_exactly_one_is_width_finding(self):
        out = m.run(req(files=[{'path': 'a.py', 'before': 'x = 1\n', 'after': '     x = 1\n'}]))
        f = out['files'][0]['style_findings']
        self.assertEqual(f['indent_width_lines'], [1])
        self.assertEqual(f['indent_width_count'], 1)

    def test_change_of_only_leading_and_trailing_whitespace_is_changed(self):
        out = m.run(req(files=[{'path': 'a.py', 'before': 'x = 1', 'after': '  x = 1  '}]))
        self.assertIs(out['files'][0]['changed'], True)
        self.assertEqual(out['changed_paths'], ['a.py'])

    def test_tab_to_spaces_change_is_whitespace_only(self):
        out = m.run(req(files=[{'path': 'a.py', 'before': 'a =\t1\n', 'after': 'a =  1\n'}]))
        self.assertIs(out['files'][0]['whitespace_only_change'], True)
        self.assertEqual(out['counts']['whitespace_only'], 1)
