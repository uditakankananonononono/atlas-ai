import ast
import builtins
import os
import importlib.util as iu
import pathlib
import random
import signal
import sys
import tempfile
import types
import pytest
from unittest import mock as _um


_IMPORT_PATCHES = []


def _start_import(mod, fn):
    p = _um.patch.object(mod, '__import__', fn)
    p.start()
    _IMPORT_PATCHES.append(p)


def _stop_import():
    if _IMPORT_PATCHES:
        _IMPORT_PATCHES.pop().stop()


@pytest.fixture(autouse=True)
def _release_import_patches():
    yield
    while _IMPORT_PATCHES:
        _IMPORT_PATCHES.pop().stop()


REG = 'app.modules.instinct_doc.p235_concepts_registry'


@pytest.fixture(scope='module', autouse=True)
def load_module():
    global m
    from app.modules.instinct_doc import (
        p235_concepts_batch1234_urn as mod)
    m = mod


@pytest.fixture(autouse=True)
def alarm():
    # No test may run away: a hanging mutant must die by assertion, and
    # fast enough that an accumulating loop cannot exhaust memory first.
    def stop(*a):
        raise AssertionError('test exceeded 30 seconds')
    old = signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, 30.0)
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, old)


_PFX = None


def _pfx():
    global _PFX
    if _PFX is None:
        try:
            m.make_fail('x')('c')
        except ValueError as e:
            msg = str(e)
            assert msg.endswith('x:c')
            _PFX = msg[:-len('x:c')]
        else:
            raise AssertionError('make_fail did not raise')
    return _PFX


def refuse(fn_name, code, *args):
    with pytest.raises(ValueError) as caught:
        getattr(m, fn_name)(*args)
    assert str(caught.value) == _pfx() + fn_name + ':' + code, (
        code, caught.value)


class _StrSub(str):
    pass


UP = 'urn_parse'
UV = 'urn_is_valid'

_SUCC_CACHE = None
_REFU_CACHE = None


def _success_corpus():
    global _SUCC_CACHE
    if _SUCC_CACHE is None:
        s = [(UP, ('urn:example:a123,z456',)),
             (UP, ('URN:example:a123,z456',)),
             (UP, ('urn:EXAMPLE:a123,z456',)),
             (UP, ('urn:example:a123,z456?+abc',)),
             (UP, ('urn:example:a123,z456?=xyz',)),
             (UP, ('urn:example:a123,z456#789',)),
             (UP, ('urn:example:a123,z456/foo',)),
             (UP, ('urn:example:a123%2Cz456',)),
             (UP, ('URN:EXAMPLE:a123%2cz456',)),
             (UP, ('urn:example:1/406/47452/2',)),
             (UP, ('urn:example:foo-bar-baz-qux?+CCResolve:cc=uk',)),
             (UP, ('urn:example:weather?=op=map&lat=39.56&lon=-104.85',)),
             (UP, ('urn:example:a123,z456#',)),
             (UP, ('urn:example:a123,z456?+?',)),
             (UP, ('urn:example:a123,z456?+a?b?=c?+d#e?f/g',)),
             (UP, ('urn:example:a#f?+x',)),
             (UP, ('urn:ab:x',)),
             (UP, ('urn:' + 'a' * 32 + ':x',)),
             (UP, ('urn:a-b:x!$&\'()*+,;=:@',)),
             (UP, ('urn:na:a%20%fF',)),
             (UP, ('urn:na:x?+r%41',)),
             (UP, ('urn:na:x?=q%41',)),
             (UP, ('urn:na:x#f%41',)),
             (UP, ('urn:na:x?+r%41?=q%42#f%43',)),
             (UV, ('urn:example:a123,z456',)),
             (UV, ('urn:example:a?+r?=q#f',)),
             (UV, ('URN:NID-2:NSS%2f',))]
        _SUCC_CACHE = s
    return _SUCC_CACHE


def _refusal_corpus():
    global _REFU_CACHE
    if _REFU_CACHE is None:
        r = [(UP, 'bad_type:value', (None,)),
             (UP, 'bad_type:value', (0,)),
             (UP, 'bad_type:value', (b'urn:na:x',)),
             (UP, 'bad_type:value', (_StrSub('urn:na:x'),)),
             (UP, 'bad_value:input.length', ('x' * 8193,)),
             (UP, 'bad_value:value.charset', ('urn:na:a b',)),
             (UP, 'bad_value:value.charset', ('urn:na:a\x7f',)),
             (UP, 'bad_value:scheme', ('xrn:n:x',)),
             (UP, 'bad_value:scheme', ('urn;n:x',)),
             (UP, 'bad_value:nss', ('urn:example',)),
             (UP, 'bad_value:nid', ('urn::x',)),
             (UP, 'bad_value:nid.length', ('urn:a:x',)),
             (UP, 'bad_value:nid.length', ('urn:' + 'a' * 33 + ':x',)),
             (UP, 'bad_value:nid.char', ('urn:a_b:x',)),
             (UP, 'bad_value:nid.edge', ('urn:-a:x',)),
             (UP, 'bad_value:nid.edge', ('urn:a-:x',)),
             (UP, 'bad_value:nss', ('urn:na:',)),
             (UP, 'bad_value:nss.char', ('urn:na:a[',)),
             (UP, 'bad_value:nss.pct', ('urn:na:a%4',)),
             (UP, 'bad_value:nss.pct', ('urn:na:a%4x',)),
             (UP, 'bad_value:rq', ('urn:na:a?x',)),
             (UP, 'bad_value:rq', ('urn:na:a?',)),
             (UP, 'bad_value:r', ('urn:na:a?+',)),
             (UP, 'bad_value:r', ('urn:na:a?+?=q',)),
             (UP, 'bad_value:r.char', ('urn:na:a?+b[',)),
             (UP, 'bad_value:r.pct', ('urn:na:a?+b%4',)),
             (UP, 'bad_value:q', ('urn:na:a?=',)),
             (UP, 'bad_value:q', ('urn:na:a?+r?=',)),
             (UP, 'bad_value:q.char', ('urn:na:a?=b[',)),
             (UP, 'bad_value:q.pct', ('urn:na:a?=b%4x',)),
             (UP, 'bad_value:f.char', ('urn:na:a#b[',)),
             (UP, 'bad_value:f.pct', ('urn:na:a#b%4',))]
        _REFU_CACHE = r
    return _REFU_CACHE


def test_loops_advance_under_time_bound():
    for fn_name, args in _success_corpus():
        getattr(m, fn_name)(*args)
    for fn_name, code, args in _refusal_corpus():
        try:
            getattr(m, fn_name)(*args)
            raise AssertionError('accepted ' + repr(args))
        except ValueError:
            pass


def test_module_docstring_is_pinned_whole():
    assert m.__doc__ == __DOC__


def test_rfc8141_examples():
    # s3.2, first group: scheme and NID are case insensitive
    base = m.urn_parse('urn:example:a123,z456')
    assert base['nid'] == 'example'
    assert base['nss'] == 'a123,z456'
    assert base['r_component'] is None
    assert base['q_component'] is None
    assert base['f_component'] is None
    assert base['normalized'] == 'urn:example:a123,z456'
    assert base['canonical_text'] == 'urn:example:a123,z456'
    assert base['canonical'] is True
    for variant in ('URN:example:a123,z456',
                    'urn:EXAMPLE:a123,z456'):
        r = m.urn_parse(variant)
        assert r['normalized'] == base['normalized']
        assert r['canonical'] is False
    # s3.2, second group: r/q/f-components are ignored for
    # URN-equivalence
    for variant in ('urn:example:a123,z456?+abc',
                    'urn:example:a123,z456?=xyz',
                    'urn:example:a123,z456#789'):
        r = m.urn_parse(variant)
        assert r['normalized'] == base['normalized']
        assert r['canonical'] is True
    # s3.2, third group: the NSS ("/" included) counts
    seen = set()
    for variant in ('urn:example:a123,z456/foo',
                    'urn:example:a123,z456/bar',
                    'urn:example:a123,z456/baz'):
        n = m.urn_parse(variant)['normalized']
        assert n != base['normalized']
        assert n not in seen
        seen.add(n)
    # s3.2, fourth group: pct triplets normalize A-F upward and are
    # NEVER decoded (%2C is not ",")
    n1 = m.urn_parse('urn:example:a123%2Cz456')['normalized']
    n2 = m.urn_parse('URN:EXAMPLE:a123%2cz456')['normalized']
    assert n1 == n2 == 'urn:example:a123%2Cz456'
    assert n1 != base['normalized']
    # s3.2, fifth group: NSS letters are case sensitive
    n3 = m.urn_parse('urn:example:A123,z456')['normalized']
    assert n3 == 'urn:example:A123,z456'
    assert n3 != base['normalized']
    # s2.3.1: the r-component example
    r = m.urn_parse('urn:example:foo-bar-baz-qux?+CCResolve:cc=uk')
    assert r['nss'] == 'foo-bar-baz-qux'
    assert r['r_component'] == 'CCResolve:cc=uk'
    assert r['q_component'] is None
    # s2.2: a hierarchical NSS with "/"
    r = m.urn_parse('urn:example:1/406/47452/2')
    assert r['nss'] == '1/406/47452/2'
    assert r['canonical'] is True


def test_component_boundaries():
    # "?+" introduces r, "?=" introduces q, "#" introduces f
    r = m.urn_parse('urn:na:x?+rc?=qc#fc')
    assert (r['r_component'], r['q_component'], r['f_component']) == (
        'rc', 'qc', 'fc')
    # '?' is ordinary data inside r, q and f
    r = m.urn_parse('urn:na:x?+a?b')
    assert r['r_component'] == 'a?b'
    r = m.urn_parse('urn:na:x?+a?b?c')
    assert r['r_component'] == 'a?b?c'
    r = m.urn_parse('urn:na:x?+a??=b')
    assert r['r_component'] == 'a?'
    assert r['q_component'] == 'b'
    r = m.urn_parse('urn:na:x?=a?b')
    assert r['q_component'] == 'a?b'
    # '?+' and '?=' are data inside q once q has started
    r = m.urn_parse('urn:na:x?+a?=b?+c')
    assert r['r_component'] == 'a'
    assert r['q_component'] == 'b?+c'
    r = m.urn_parse('urn:na:x?+a?=b?=c')
    assert r['q_component'] == 'b?=c'
    r = m.urn_parse('urn:na:x?=a?+b?=c')
    assert r['q_component'] == 'a?+b?=c'
    assert r['r_component'] is None
    # r alone: 'urn:na:x?+?' is a one-character r-component
    r = m.urn_parse('urn:na:x?+?')
    assert r['r_component'] == '?'
    # f runs to the end and swallows everything after '#'
    r = m.urn_parse('urn:na:a#f?+x')
    assert r['f_component'] == 'f?+x'
    assert r['r_component'] is None
    assert r['q_component'] is None
    r = m.urn_parse('urn:na:a#f?=x')
    assert r['f_component'] == 'f?=x'
    # an empty f-component is legal (fragment allows zero chars)
    r = m.urn_parse('urn:na:a#')
    assert r['f_component'] == ''
    assert r['canonical'] is True
    # r/q require at least one pchar
    refuse(UP, 'bad_value:r', 'urn:na:x?+')
    refuse(UP, 'bad_value:r', 'urn:na:x?+#f')
    refuse(UP, 'bad_value:q', 'urn:na:x?=')
    refuse(UP, 'bad_value:q', 'urn:na:x?=#f')
    refuse(UP, 'bad_value:q', 'urn:na:x?+r?=')
    # the s2 '?' rule: bare '?' outside the components refuses
    refuse(UP, 'bad_value:rq', 'urn:na:a?x')
    refuse(UP, 'bad_value:rq', 'urn:na:a??')
    refuse(UP, 'bad_value:rq', 'urn:na:a?')
    refuse(UP, 'bad_value:rq', 'urn:na:a?#f')
    refuse(UP, 'bad_value:rq', 'urn:na:a?x[')


def test_nid_rules():
    # length: 2..32, first and last alphanumeric, middle ldh
    assert m.urn_parse('urn:ab:x')['nid'] == 'ab'
    assert m.urn_parse('urn:' + 'a' * 32 + ':x')
    refuse(UP, 'bad_value:nid.length', 'urn:a:x')
    refuse(UP, 'bad_value:nid.length', 'urn:' + 'a' * 33 + ':x')
    refuse(UP, 'bad_value:nid', 'urn::x')
    # hyphens inside, never on the edges
    assert m.urn_parse('urn:a-b-c:x')['nid'] == 'a-b-c'
    assert m.urn_parse('urn:a' + '-' * 30 + 'b:x')
    refuse(UP, 'bad_value:nid.edge', 'urn:-a:x')
    refuse(UP, 'bad_value:nid.edge', 'urn:a-:x')
    refuse(UP, 'bad_value:nid.edge', 'urn:-a-:x')
    refuse(UP, 'bad_value:nid.edge', 'urn:-' + 'a' * 30 + '-:x')
    # every ldh character is accepted mid-NID
    for ch in ('-0123456789'
               'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
               'abcdefghijklmnopqrstuvwxyz'):
        assert m.urn_parse('urn:a' + ch + 'b:x')
    # every other printable character refuses mid-NID, except the
    # structural ':' (separator), '?' (boundary) and '#' (f split)
    ldh = set('-0123456789'
              'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
              'abcdefghijklmnopqrstuvwxyz')
    for i in range(0x21, 0x7F):
        ch = chr(i)
        if ch in ldh or ch in ':?#':
            continue
        refuse(UP, 'bad_value:nid.char', 'urn:a' + ch + 'b:x')
    # NIDs are case insensitive for equivalence
    assert (m.urn_parse('urn:ISBN:0451450523')['normalized']
            == m.urn_parse('urn:isbn:0451450523')['normalized']
            == 'urn:isbn:0451450523')


def test_nss_rules():
    # NSS = pchar *(pchar / "/"): every member accepted
    pchar = ("-._~!$&'()*+,;=:@"
             '0123456789'
             'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
             'abcdefghijklmnopqrstuvwxyz')
    for ch in pchar + '/':
        r = m.urn_parse('urn:na:a' + ch + 'b')
        assert r['nss'] == 'a' + ch + 'b'
    # every other printable character refuses, except the structural
    # '?' (boundary), '#' (f split) and '%' (triplet lead)
    ok = set(pchar + '/')
    for i in range(0x21, 0x7F):
        ch = chr(i)
        if ch in ok or ch in '?#%':
            continue
        refuse(UP, 'bad_value:nss.char', 'urn:na:a' + ch + 'b')
    # pct shape: both hex slots checked, triplet may end the NSS
    assert m.urn_parse('urn:na:a%41')['nss'] == 'a%41'
    assert m.urn_parse('urn:na:%2F%2f')['nss'] == '%2F%2f'
    refuse(UP, 'bad_value:nss.pct', 'urn:na:a%')
    refuse(UP, 'bad_value:nss.pct', 'urn:na:a%4')
    refuse(UP, 'bad_value:nss.pct', 'urn:na:a%x4')
    refuse(UP, 'bad_value:nss.pct', 'urn:na:a%4x')
    refuse(UP, 'bad_value:nss.pct', 'urn:na:%[a')
    # adjacent triplets: the second shape is checked too
    assert m.urn_parse('urn:na:a%20%20')['nss'] == 'a%20%20'
    refuse(UP, 'bad_value:nss.pct', 'urn:na:a%20%2')
    refuse(UP, 'bad_value:nss.pct', 'urn:na:a%20%2G')
    refuse(UP, 'bad_value:nss.pct', 'urn:na:a%20%x')
    # a pct triplet is opaque: '?' '#' ':' inside it are data
    r = m.urn_parse('urn:na:a%3Fb%23c%3Ad')
    assert r['nss'] == 'a%3Fb%23c%3Ad'
    assert r['r_component'] is None
    assert r['f_component'] is None
    # the NSS is case sensitive but its triplets normalize upward
    r = m.urn_parse('urn:na:A%2fb')
    assert r['nss'] == 'A%2fb'
    assert r['normalized'] == 'urn:na:A%2Fb'


def test_rqf_component_rules():
    # the r/q/f class is pchar / "/" / "?"; pct rules apply
    for seg, mk, code in (('r', lambda v: 'urn:na:x?+' + v,
                           'bad_value:r.char'),
                          ('q', lambda v: 'urn:na:x?=' + v,
                           'bad_value:q.char'),
                          ('f', lambda v: 'urn:na:x#' + v,
                           'bad_value:f.char')):
        r = m.urn_parse(mk('a/b?c'))
        assert r[seg + '_component'] == 'a/b?c'
        refuse(UP, code, mk('a[b'))
        refuse(UP, code, mk('a]b'))
        refuse(UP, code, mk('a"b'))
        refuse(UP, code, mk('a^b'))
        refuse(UP, code, mk('a`b'))
        refuse(UP, code, mk('a|b'))
        refuse(UP, code, mk('a\\b'))
        refuse(UP, code, mk('a<b'))
        refuse(UP, code, mk('a>b'))
        refuse(UP, code, mk('a{b'))
        refuse(UP, code, mk('a}b'))
    for mk, code in ((lambda v: 'urn:na:x?+' + v, 'bad_value:r.pct'),
                     (lambda v: 'urn:na:x?=' + v, 'bad_value:q.pct'),
                     (lambda v: 'urn:na:x#' + v, 'bad_value:f.pct')):
        assert m.urn_parse(mk('a%41'))
        assert m.urn_parse(mk('a%4f'))
        refuse(UP, code, mk('a%'))
        refuse(UP, code, mk('a%4'))
        refuse(UP, code, mk('a%4x'))
        refuse(UP, code, mk('a%x4'))
        # adjacent triplets: the second shape is checked too
        assert m.urn_parse(mk('a%20%20'))
        refuse(UP, code, mk('a%20%2'))
        refuse(UP, code, mk('a%20%2G'))
    # a pct triplet is opaque inside r: '=' after a triplet is data
    r = m.urn_parse('urn:na:x?+a%3Db')
    assert r['r_component'] == 'a%3Db'
    assert r['q_component'] is None
    r = m.urn_parse('urn:na:x?+a%3F%3D')
    assert r['r_component'] == 'a%3F%3D'
    assert r['q_component'] is None
    # a second '#' is never data
    refuse(UP, 'bad_value:f.char', 'urn:na:a#b#c')
    refuse(UP, 'bad_value:f.char', 'urn:na:a?+r?=q#b#c')
    # r before q before f, in grammar order
    r = m.urn_parse('urn:na:x?+r?=q#f')
    assert (r['r_component'], r['q_component'], r['f_component']) == (
        'r', 'q', 'f')


def test_equivalence_and_canonical():
    # 'normalized' ignores the r/q/f-components entirely
    r = m.urn_parse('URN:EXAMPLE:a123%2cz456?+R?=Q#F')
    assert r['normalized'] == 'urn:example:a123%2Cz456'
    assert r['canonical_text'] == 'urn:example:a123%2Cz456?+R?=Q#F'
    assert r['canonical'] is False
    # pct triplets are NEVER decoded (s3.1)
    assert (m.urn_parse('urn:na:%41')['normalized']
            != m.urn_parse('urn:na:A')['normalized'])
    # the canonical text always re-parses, canonically
    for t in ('URN:EXAMPLE:a123%2cz456?+R?=Q#F',
              'urn:example:a123,z456?+abc',
              'urn:na:a%2f'):
        r = m.urn_parse(t)
        r2 = m.urn_parse(r['canonical_text'])
        assert r2['canonical'] is True
        assert r2['canonical_text'] == r['canonical_text']
    # an already-canonical input reports canonical
    r = m.urn_parse('urn:example:a123%2Cz456?+R?=Q#F')
    assert r['canonical'] is True
    # output field types are exact
    r = m.urn_parse('urn:na:x')
    assert type(r['canonical']) is bool
    assert r['r_component'] is None
    assert r['q_component'] is None
    assert r['f_component'] is None
    assert r['urn'] == 'urn:na:x'


def test_result_shape_and_freshness():
    a = m.urn_parse('urn:example:a?+r?=q#f')
    assert set(a) == {'urn', 'nid', 'nss', 'r_component',
                      'q_component', 'f_component', 'normalized',
                      'canonical_text', 'canonical'}
    assert a['urn'] == 'urn:example:a?+r?=q#f'
    a['nid'] = 'MUTATED'
    b = m.urn_parse('urn:example:a?+r?=q#f')
    assert b['nid'] == 'example'
    assert a is not b


def test_header_refusals():
    for fn_name, code, args in _refusal_corpus():
        refuse(fn_name, code, *args)


def test_exact_types_refuse():
    for bad in (None, 0, True, 5.5, b'urn:na:x', ['urn:na:x'],
                (1,), _StrSub('urn:na:x')):
        refuse(UP, 'bad_type:value', bad)
        assert m.urn_is_valid(bad) is False


def test_input_length_cap():
    # the OURS 8192-character cap: exactly at it: accepted; one past:
    # refused
    ok = 'urn:na:' + 'e' * 8185
    assert len(ok) == 8192
    assert m.urn_parse(ok)['nss'] == 'e' * 8185
    assert len(ok + 'e') == 8193
    refuse(UP, 'bad_value:input.length', ok + 'e')
    refuse(UP, 'bad_value:input.length', 'x' * 9000)


def test_refusal_order():
    # type before length before the charset gate
    refuse(UP, 'bad_type:value', 0)
    refuse(UP, 'bad_value:input.length', 'x' * 8192 + ' ')
    refuse(UP, 'bad_value:value.charset', 'xrn n:x')
    # the charset gate before the scheme check
    refuse(UP, 'bad_value:value.charset', 'xrn;n x')
    # the scheme before the separator and NID checks
    refuse(UP, 'bad_value:scheme', 'xrn:a_b:x')
    # the ":" separator before any NID rule
    refuse(UP, 'bad_value:nss', 'urn:-a')
    # NID: empty before length before char before edge
    refuse(UP, 'bad_value:nid', 'urn::x')
    refuse(UP, 'bad_value:nid.length', 'urn:' + 'a~' * 17 + ':x')
    refuse(UP, 'bad_value:nid.char', 'urn:-~:x')
    refuse(UP, 'bad_value:nid.edge', 'urn:a-:[')
    # an empty NSS refuses before the NSS scan runs
    refuse(UP, 'bad_value:nss', 'urn:na:')
    refuse(UP, 'bad_value:nss', 'urn:na:?=q')
    # the NSS scan is left to right and precedes the boundary rule
    refuse(UP, 'bad_value:nss.char', 'urn:na:[?x')
    refuse(UP, 'bad_value:nss.pct', 'urn:na:%[a?x')
    refuse(UP, 'bad_value:rq', 'urn:na:a?x')
    # r before q before f
    refuse(UP, 'bad_value:r.char', 'urn:na:a?+[?=q#f')
    refuse(UP, 'bad_value:r', 'urn:na:a?+?=q#f')
    refuse(UP, 'bad_value:q.char', 'urn:na:a?+r?=[#f')
    refuse(UP, 'bad_value:q.char', 'urn:na:a?=[#f')
    refuse(UP, 'bad_value:f.char', 'urn:na:a?+r?=q#[')
    # within the f scan the pct shape precedes a later bad character
    refuse(UP, 'bad_value:f.pct', 'urn:na:a#%4[')


def test_is_valid_returns_exact_bool():
    v = m.urn_is_valid('urn:example:a123,z456')
    assert v is True and type(v) is bool
    assert m.urn_is_valid('urn:example:a?+r?=q#f') is True
    assert m.urn_is_valid('garbage') is False
    assert m.urn_is_valid('urn:na:x?+') is False
    assert m.urn_is_valid(None) is False
    assert m.urn_is_valid(0) is False


def test_constants_pinned_whole():
    assert m._MAX_INPUT_LENGTH == 8192
    assert m._ALPHANUM == frozenset(
        '0123456789'
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        'abcdefghijklmnopqrstuvwxyz')
    assert len(m._ALPHANUM) == 62
    assert m._LDH == m._ALPHANUM | frozenset('-')
    assert len(m._LDH) == 63
    assert m._UNRESERVED == m._ALPHANUM | frozenset('-._~')
    assert len(m._UNRESERVED) == 66
    assert m._SUB_DELIMS == frozenset("!$&'()*+,;=")
    assert len(m._SUB_DELIMS) == 11
    assert m._PCHAR == m._UNRESERVED | m._SUB_DELIMS | frozenset(':@')
    assert len(m._PCHAR) == 79
    assert m._HEXDIG == frozenset('0123456789ABCDEFabcdef')
    assert len(m._HEXDIG) == 22
    assert m._NSS_CHARS == m._PCHAR | frozenset('/')
    assert len(m._NSS_CHARS) == 80
    assert m._RQF_CHARS == m._PCHAR | frozenset('/?')
    assert len(m._RQF_CHARS) == 81


def test_function_docstrings_pinned_exact():
    assert m.urn_parse.__doc__ is None
    assert m.urn_is_valid.__doc__ == (
        'True iff urn_parse(text) would succeed.')


def test_module_namespace_is_pinned():
    names = set(vars(m))
    assert names == {
        '__name__', '__doc__', '__package__', '__loader__',
        '__spec__', '__file__', '__cached__', '__builtins__',
        'find_spec', 'make_fail',
        '_MAX_INPUT_LENGTH', '_ALPHANUM', '_LDH', '_UNRESERVED',
        '_SUB_DELIMS', '_PCHAR', '_HEXDIG', '_NSS_CHARS',
        '_RQF_CHARS', '_check_component', '_normalize_pct',
        'urn_parse', 'urn_is_valid'}


def test_parse_is_deterministic_and_consistent():
    rng = random.Random(1234)
    alphabet = 'aZ09%-._~!$&\'()*+,;=:@/?#[] \x00\x7f'
    for _ in range(400):
        blob = ''.join(rng.choice(alphabet)
                       for _ in range(rng.randrange(0, 40)))
        try:
            r1 = m.urn_parse(blob)
        except ValueError:
            assert m.urn_is_valid(blob) is False
        else:
            assert m.urn_is_valid(blob) is True
            assert m.urn_parse(blob) == r1
            # the canonical text always re-parses, canonically
            r2 = m.urn_parse(r1['canonical_text'])
            assert r2['canonical'] is True
            assert r2['canonical_text'] == r1['canonical_text']
            assert r2['normalized'] == r1['normalized']
            assert r2['nid'] == r1['nid'].lower()
            assert r2['r_component'] == r1['r_component']
            assert r2['q_component'] == r1['q_component']
            assert r2['f_component'] == r1['f_component']
def _f_lines():
    fname = pathlib.Path(m.__file__)
    tree = ast.parse(fname.read_text())
    lines = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == 'f'):
            lines.add(node.lineno)
    return lines, str(fname)


def test_corpus_drives_every_refusal_site_and_success_path():
    f_lines, fname = _f_lines()
    hits = set()

    def tracer(frame, event, arg):
        if event == 'line' and frame.f_code.co_filename == fname:
            hits.add(frame.f_lineno)
        return tracer

    sys.settrace(tracer)
    try:
        for fn_name, args in _success_corpus():
            getattr(m, fn_name)(*args)
        for fn_name, code, d in _refusal_corpus():
            raised = None
            try:
                getattr(m, fn_name)(*d)
            except ValueError as caught:
                raised = caught
            assert raised is not None, (fn_name, code)
    finally:
        sys.settrace(None)
    # no exemptions: every f() site in the module is corpus-reached
    assert f_lines <= hits, sorted(f_lines - hits)


# ---- no imports on any public call ----

def test_no_import_on_any_public_call():
    fname = str(pathlib.Path(m.__file__))
    f_lines, _ = _f_lines()
    hits = set()
    log = []

    def tracer(frame, event, arg):
        if event == 'line' and frame.f_code.co_filename == fname:
            hits.add(frame.f_lineno)
        return tracer

    real = builtins.__import__

    def hook(name, *a, **k):
        log.append(name)
        return real(name, *a, **k)

    sys.settrace(tracer)
    try:
        for fn_name, args in (
                _success_corpus()
                + [(fn, d) for fn, code, d in
                   _refusal_corpus()]):
            log = []
            _start_import(builtins, hook)
            try:
                try:
                    getattr(m, fn_name)(*args)
                except ValueError:
                    pass
                # the is_valid twin is a public call too (its
                # True AND False paths): an inserted import in
                # either body dies here
                is_valid = getattr(
                    m, fn_name.replace('_parse', '_is_valid'))
                is_valid(*args)
                is_valid(0)
            finally:
                _stop_import()
            assert log == [], (fn_name, args, log)
    finally:
        sys.settrace(None)
    assert f_lines <= hits, sorted(f_lines - hits)


# ---- registry guard ----

def test_registry_guard_shape():
    tree = ast.parse(pathlib.Path(m.__file__).read_text())
    tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
    guard = [t for t in tries
             if any(isinstance(s, ast.ImportFrom) and s.module == REG
                    for s in t.body)]
    assert len(guard) == 1
    assert len(guard) == 1
    # the try body is EXACTLY the registry import: an inserted
    # statement (import os between try: and the import) dies here
    assert len(guard[0].body) == 1
    assert isinstance(guard[0].body[0], ast.ImportFrom)
    h = guard[0].handlers[0]
    # the handler body is EXACTLY the re-raise If plus the fallback
    # def, and the If body is exactly the bare raise: an inserted
    # statement at either level dies here
    assert len(h.body) == 2
    assert isinstance(h.body[0], ast.If)
    assert len(h.body[0].body) == 1
    assert isinstance(h.body[0].body[0], ast.Raise)
    assert isinstance(h.body[1], ast.FunctionDef)
    assert type(h.type) is ast.Name and h.type.id == 'ModuleNotFoundError'
    assert "'P235:%s:%s'" in ast.dump(h)


def test_registry_guard_reraises_foreign_import_error():
    # or->and at the registry fallback guard must die: a
    # ModuleNotFoundError naming a DIFFERENT module while the
    # registry is genuinely absent must propagate, not silently
    # fall back
    import builtins as _b
    import importlib.util as _iu
    real_import = _b.__import__
    real_find_spec = _iu.find_spec

    def bogus_import(name, *a, **k):
        if name.endswith('p235_concepts_registry'):
            raise ModuleNotFoundError(
                "No module named 'x.other'", name='x.other')
        return real_import(name, *a, **k)

    def no_spec(name, *k, **kw):
        if name.endswith('p235_concepts_registry'):
            return None
        return real_find_spec(name, *k, **kw)

    src = pathlib.Path(m.__file__).read_text()
    _start_import(_b, bogus_import)
    _iu.find_spec = no_spec
    try:
        mod = types.ModuleType('fresh_b1234')
        with pytest.raises(ModuleNotFoundError):
            exec(compile(src, 'fresh_b1234', 'exec'), mod.__dict__)
    finally:
        _stop_import()
        _iu.find_spec = real_find_spec


def test_registry_import_failure_modes_propagate():
    # except-ModuleNotFoundError is pinned: a registry that exists but
    # lacks make_fail, one that fails importing an inner dependency,
    # or one that raises ModuleNotFoundError naming the registry
    # itself must propagate rather than silently fall back.
    import subprocess
    mod_path = pathlib.Path(m.__file__).name
    src_text = pathlib.Path(m.__file__).read_text()
    reg_raise = ("raise ModuleNotFoundError('gone', "
                 "name=%r)\n" % REG)
    for body, exc_kind in (
            ('X = 1\n', 'ImportError'),
            ('import no_such_dep_xyz_1234\n', 'ModuleNotFoundError'),
            (reg_raise, 'ModuleNotFoundError')):
        with tempfile.TemporaryDirectory() as td:
            pkg = pathlib.Path(td) / 'app' / 'modules' / 'instinct_doc'
            pkg.mkdir(parents=True)
            (pkg.parent.parent / '__init__.py').write_text('')
            (pkg.parent / '__init__.py').write_text('')
            (pkg / 'p235_concepts_registry.py').write_text(body)
            (pkg / mod_path).write_text(src_text)
            code = ('import sys; sys.path.insert(0, %r); '
                    'import app.modules.instinct_doc.%s'
                    % (td, mod_path[:-3]))
            r = subprocess.run(
                [sys.executable, '-I', '-S', '-c',
                 'try:\n ' + code + '\nexcept ' + exc_kind +
                 ':\n print("ok")'],
                capture_output=True, text=True,
                env={'PATH': os.environ.get('PATH', '/usr/bin:/bin')})
            assert r.stdout.strip() == 'ok', (exc_kind, r.stderr[-300:])


def test_find_spec_called_with_exact_registry_name_once():
    # the import guard must probe find_spec with EXACTLY the registry
    # module name, exactly once, on the fallback path (a mutated
    # argument like REG + 'Z' dies here)
    import importlib.util as _iu
    src = pathlib.Path(m.__file__).read_text()
    calls = []
    real_import = builtins.__import__
    real_find_spec = _iu.find_spec

    def bogus_import(name, *a, **k):
        if name.endswith('p235_concepts_registry'):
            raise ModuleNotFoundError(
                "No module named %r" % REG, name=REG)
        return real_import(name, *a, **k)

    def spy_find_spec(name, *a, **k):
        calls.append(name)
        return None

    _start_import(builtins, bogus_import)
    _iu.find_spec = spy_find_spec
    try:
        mod = types.ModuleType('fresh_b1234_spy')
        exec(compile(src, 'fresh_b1234_spy', 'exec'), mod.__dict__)
    finally:
        _stop_import()
        _iu.find_spec = real_find_spec
    assert calls == [REG], calls
    # the fallback engaged and works
    assert mod.urn_is_valid('urn:example:a123,z456') is True
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        assert str(e) == 'P235:x:c'
    else:
        raise AssertionError('fallback make_fail did not raise')




def test_battery_rev0_pins():
    # the OURS 8192 cap: exactly at it accepted, one past refused
    ok = 'urn:na:' + 'e' * 8185
    assert len(ok) == 8192
    assert m.urn_parse(ok)['nss'] == 'e' * 8185
    refuse(UP, 'bad_value:input.length', ok + 'e')
    # the charset gate flanks: 0x21 and 0x7E pass, 0x20/0x7F/0x00 die
    assert m.urn_parse('urn:na:!~')['nss'] == '!~'
    refuse(UP, 'bad_value:value.charset', 'urn:na: ')
    refuse(UP, 'bad_value:value.charset', 'urn:na:\x7f')
    refuse(UP, 'bad_value:value.charset', 'urn:na:\x00')
    # the scheme prefix accepts any casing (RFC 5234 s2.3)
    for pre in ('urn:', 'URN:', 'UrN:', 'uRn:'):
        assert m.urn_parse(pre + 'na:x')['nid'] == 'na'
    refuse(UP, 'bad_value:scheme', 'urn;n:x')
    refuse(UP, 'bad_value:scheme', 'urnn:x')
    refuse(UP, 'bad_value:scheme', 'urn')
    refuse(UP, 'bad_value:scheme', 'xurn:na:x')
    refuse(UP, 'bad_value:scheme', '')
    # NID flanks: 2 and 32 accepted, 1 and 33 refused
    assert m.urn_parse('urn:ab:x')
    refuse(UP, 'bad_value:nid.length', 'urn:a:x')
    assert m.urn_parse('urn:' + '9' * 32 + ':x')
    refuse(UP, 'bad_value:nid.length', 'urn:' + '9' * 33 + ':x')
    # an empty NSS refuses; a one-pchar NSS accepts
    refuse(UP, 'bad_value:nss', 'urn:na:')
    assert m.urn_parse('urn:na:!')['nss'] == '!'
    # r/q need at least one pchar; f may be empty
    refuse(UP, 'bad_value:r', 'urn:na:x?+')
    refuse(UP, 'bad_value:q', 'urn:na:x?=')
    assert m.urn_parse('urn:na:x#')['f_component'] == ''
    # '#' as the very first character after the scheme still
    # splits off an f-component, leaving no NID/NSS at all
    refuse(UP, 'bad_value:scheme', 'urn#n:x')
    refuse(UP, 'bad_value:nss', 'urn:#n:x')
    refuse(UP, 'bad_value:nss', 'urn:#')
    refuse(UP, 'bad_value:nss', 'urn:#x')
    # the boundary '?' must be followed by '+' or '=' (s2)
    refuse(UP, 'bad_value:rq', 'urn:na:a?')
    refuse(UP, 'bad_value:rq', 'urn:na:a?~')
    refuse(UP, 'bad_value:rq', 'urn:na:a??')
    # '?' is data inside r, q and f
    assert m.urn_parse('urn:na:x?+a?b')['r_component'] == 'a?b'
    assert m.urn_parse('urn:na:x?=a?b')['q_component'] == 'a?b'
    assert m.urn_parse('urn:na:x#a?b')['f_component'] == 'a?b'
    # '?' inside r terminates the component only as '?='
    r = m.urn_parse('urn:na:x?+a??=b')
    assert r['r_component'] == 'a?'
    assert r['q_component'] == 'b'
    # pct triplets: both slots checked, both cases, adjacent pairs
    assert m.urn_parse('urn:na:a%fF')
    refuse(UP, 'bad_value:nss.pct', 'urn:na:a%20%2')
    refuse(UP, 'bad_value:r.pct', 'urn:na:a?+b%20%2')
    refuse(UP, 'bad_value:q.pct', 'urn:na:a?=b%20%2')
    refuse(UP, 'bad_value:f.pct', 'urn:na:a#b%20%2')
    # the r-component ends at '?=' or '#', never at '?+'
    r = m.urn_parse('urn:ab:b?+r?+x')
    assert r['r_component'] == 'r?+x'
    assert r['q_component'] is None
    assert r['canonical'] is True
    # pct hex digits accept either case, first and second slot,
    # in every component
    assert m.urn_parse('urn:ab:b?=q%af')['q_component'] == 'q%af'
    assert m.urn_parse('urn:ab:b?=q%FA')['q_component'] == 'q%FA'
    assert m.urn_parse('urn:ab:b?+r%af')['r_component'] == 'r%af'
    assert m.urn_parse('urn:ab:b#f%af')['f_component'] == 'f%af'
    # the f-component is validated LAST: an earlier NID refusal
    # outranks a bad f-component character
    refuse(UP, 'bad_value:nid.length', 'urn:!:ok#bad^')
    # s3.1: equivalence normalization, triplets never decoded
    assert (m.urn_parse('URN:NID-2:NSS%2f?+r?=q#f')['normalized']
            == 'urn:nid-2:NSS%2F')
    assert (m.urn_parse('urn:na:%41')['normalized']
            != m.urn_parse('urn:na:A')['normalized'])
    # output field types are exact bools
    r = m.urn_parse('urn:na:x')
    assert type(r['canonical']) is bool
    assert r['canonical'] is True
    r = m.urn_parse('URN:na:x')
    assert r['canonical'] is False
    assert r['canonical_text'] == 'urn:na:x'

__DOC__ = 'RFC 8141 "Uniform Resource Names (URNs)": the s2\nnamestring grammar over one Python text string carrying\nONE URN, plus the s3.1 URN-equivalence normalization of\nthe assigned-name.  URN resolution, the semantics of the\nr/q/f-components, namespace-specific assignment or\nequivalence rules, and the NID registration constraints\nof s5.1/s5.2 (registry policy, not parser grammar) are\nout of scope.\n\nPublic API:\n\n  urn_parse(text) -> a dict:\n      \'urn\': the input text as received,\n      \'nid\': the Namespace Identifier as received,\n      \'nss\': the Namespace Specific String as received,\n      \'r_component\': the r-component as received, or\n          None when the "?+" delimiter is absent,\n      \'q_component\': the q-component as received, or\n          None when the "?=" delimiter is absent,\n      \'f_component\': the f-component as received, or\n          None when the "#" delimiter is absent,\n      \'normalized\': the assigned-name after the s3.1\n          case normalization (below); two URNs are\n          URN-equivalent iff their \'normalized\' values\n          are octet-by-octet equal,\n      \'canonical_text\': OURS (below),\n      \'canonical\': True iff the input IS the canonical\n          text, byte for byte.\n  urn_is_valid(text) -> True iff urn_parse would succeed.\n\nGrammar notes (verified against the RFC 8141 text).  s2:\n\'namestring = assigned-name [ rq-components ] [ "#"\nf-component ]\', \'assigned-name = "urn" ":" NID ":" NSS\',\n\'NID = (alphanum) 0*30(ldh) (alphanum)\', \'ldh = alphanum\n/ "-"\', \'NSS = pchar *(pchar / "/")\', \'rq-components =\n[ "?+" r-component ] [ "?=" q-component ]\', \'r-component\n= pchar *( pchar / "/" / "?" )\', \'q-component = pchar *(\npchar / "/" / "?" )\', \'f-component = fragment\', with\n\'alphanum\', \'fragment\' and \'pchar\' imported from RFC\n3986: \'pchar = unreserved / pct-encoded / sub-delims /\n":" / "@"\', \'unreserved = ALPHA / DIGIT / "-" / "." /\n"_" / "~"\', \'sub-delims = "!" / "$" / "&" / "\'" / "(" /\n")" / "*" / "+" / "," / ";" / "="\', \'pct-encoded = "%"\nHEXDIG HEXDIG\' (s2.1), \'fragment = *( pchar / "/" / "?"\n)\' (s3.5).  NID is two to thirty-two characters, first\nand last alphanumeric, the middle alphanumerics and\nhyphens.  ABNF string literals are case-insensitive\n(RFC 5234 s2.3), so the "urn" scheme prefix accepts any\ncasing, and s2.1 adds "NIDs are case insensitive".  The\ns2 \'?\' rule: \'Other than inside those components, a "?"\nthat is not immediately followed by "=" or "+" is not\ndefined for URNs and SHOULD be treated as a syntax error\nby URN-specific parsers and other processors.\' - folded\nhere as the bad_value:rq refusal.  The r-component ends at the first\n"?=" sequence or "#"; the q-component ends at "#"; the\nf-component runs to the end.  An r-component or\nq-component requires at least one pchar; an f-component\nmay be empty (\'fragment\' allows zero characters).\nPercent-encoding: in every component a "%" must be\nfollowed by exactly two HEXDIG; the digits accept either\ncase on input.\n\ns3.1 URN-equivalence: "Two URNs are URN-equivalent if\ntheir assigned-name portions are octet-by-octet equal\nafter applying case normalization ... to: 1. the URI\nscheme "urn", by conversion to lower case; 2. the NID, by\nconversion to lower case; 3. any percent-encoded\ncharacters in the NSS ..., by conversion to upper case\nfor the digits A-F."  "Percent-encoded characters MUST\nNOT be decoded"  "If an r-component, q-component, or\nf-component (or any combination thereof) is included in a\nURN, it MUST be ignored for purposes of determining\nURN-equivalence."  \'normalized\' is exactly that\nnormalized assigned-name; namespace-specific extra\nequivalence rules (s3.1 last paragraph) are not applied.\n\nProfile decisions (OURS, not from the RFC text):\n  - Only the exact str type is accepted; subclasses\n    refuse with the type code.\n  - The input is capped at 8192 characters; the RFC sets\n    no length limit.\n  - Canonical text: \'normalized\' + the r/q/f-components\n    re-attached byte-for-byte with their "?+", "?=" and\n    "#" delimiters, in grammar order.\n\nRefusal order: bad_type:value before everything; the\n8192-character cap (bad_value:input.length); the charset\ngate %x21-7E (bad_value:value.charset); the scheme\nprefix (bad_value:scheme); presence of the ":" separator\nafter the NID (bad_value:nss); the NID: presence and\nlength (bad_value:nid, bad_value:nid.length), the ldh\nclass (bad_value:nid.char), the alphanumeric first and\nlast characters (bad_value:nid.edge); a non-empty NSS\n(bad_value:nss), then the NSS scan - pct shape (bad_value:nss.pct) and the\npchar/"/" class (bad_value:nss.char) - up to the\ncomponent boundary; the \'?\' delimiter rule\n(bad_value:rq); the r-component: presence of at least\none pchar (bad_value:r), pct shape (bad_value:r.pct) and\nclass (bad_value:r.char); the q-component: presence\n(bad_value:q), pct shape (bad_value:q.pct) and class\n(bad_value:q.char); the f-component last: pct shape\n(bad_value:f.pct) and class (bad_value:f.char).  Within\neach component scan, characters are checked left to\nright, so a malformed "%" refuses before a later bad\ncharacter.\n\nErrata: RFC 8141 has zero records in the RFC Editor\nerrata feed (verified against the live feed).\n'
