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
        p235_concepts_batch1228_webdav_headers as mod)
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


DP = 'dav_depth_parse'
OP = 'dav_overwrite_parse'
TP = 'dav_timeout_parse'
LP = 'dav_lock_token_parse'
XP = 'dav_destination_parse'
FP = 'dav_if_parse'
PARSE_FNS = (DP, OP, TP, LP, XP, FP)

_SUCC_CACHE = None
_REFU_CACHE = None


def _success_corpus():
    global _SUCC_CACHE
    if _SUCC_CACHE is None:
        s = [(DP, ('0',)), (DP, ('1',)), (DP, ('infinity',)),
             (DP, ('INFINITY',)), (DP, (' Infinity ',)),
             (OP, ('T',)), (OP, ('f',)),
             (TP, ('Second-30',)), (TP, ('Infinite',)),
             (TP, ('Second-10, Infinite',)),
             (TP, ('second-007 , INFINITE',)),
             (TP, ('Second-4294967295',)),
             (TP, ('Second-1,,Second-2',)),
             (LP, ('<urn:uuid:181d4fae-7d8c-11d0-a765-00a0c91e6bf2>',)),
             (LP, ('<http://example.com/lock/1?x=%2F>',)),
             (LP, (' <urn:uuid:sp>',)),
             (XP, ('http://example.com/dir/file',)),
             (XP, ('/dir/file',)),
             (XP, ('/a/b?x=1&y=2',)),
             (XP, ('http://u%20ser:pw@ex.com:8080/p',)),
             (XP, ('http://ex.com:/p',)),
             (XP, ('http://192.168.0.1/p',)),
             (XP, ('http://[::1]:80/p',)),
             (XP, ('http://[::1]:8/p',)),
             (XP, ('http://[v1.fe80::a]/p',)),
             (XP, ('file:///x',)),
             (XP, ('urn:isbn:0451450523',)),
             (XP, ('a:',)),
             (XP, ('a:?q',)),
             (XP, ('/',)),
             (XP, ('/?',)),
             (XP, ('/a//b',)),
             (XP, ('http://ex.com/a%2Fb?x=%2f',)),
             (XP, ('mailto:foo@bar',)),
             (XP, ('http://[zz]/',)),
             (FP, ('(<urn:uuid:181d4fae-7d8c-11d0-a765-00a0c91e6bf2>)',)),
             (FP, ('(Not <urn:uuid:a> <urn:uuid:b>)',)),
             (FP, ('(["etagv"]) (Not [W/"weak1"])',)),
             (FP, ('<http://example.com/a> (<urn:uuid:x> ["e1"]) '
                   '(<urn:uuid:y>)',)),
             (FP, ('</b> (<urn:uuid:z>) </c?q=1> (Not [W/"e2"])',)),
             (FP, ('(Not<urn:uuid:nospace>)',)),
             (FP, ('(["quo\\"ted"])',)),
             (FP, ('(  <urn:uuid:lws>\t["e"]  )',)),
             (FP, ('(<urn:uuid:a>)  (<urn:uuid:b>)',)),
             (FP, ('<urn:uuid:t>\t (<urn:uuid:a>)',)),
             (FP, ('(Not  <urn:uuid:a>)',))]
        _SUCC_CACHE = s
    return _SUCC_CACHE


def _refusal_corpus():
    global _REFU_CACHE
    if _REFU_CACHE is None:
        c = []
        for fn in PARSE_FNS:
            for bad in (None, 0, 1, True, False, 5.5, b'0', ['0'],
                        {'x': 1}, (1,), _StrSub('0')):
                c.append((fn, 'bad_type:value', (bad,)))
            c.append((fn, 'bad_value:input.length', ('x' * 8193,)))
            c.append((fn, 'bad_value:value.charset', ('a\rb',)))
        for bad in ('', '2', 'infinite', '1 2', 'infinity0', '01'):
            c.append((DP, 'bad_value:depth', (bad,)))
        for bad in ('', 'TF', 'true', ' x'):
            c.append((OP, 'bad_value:overwrite', (bad,)))
        for bad in ('', ' , , ', ','):
            c.append((TP, 'bad_value:timeout.list', (bad,)))
        for bad in ('Second-', 'Second- 10', 'Second -10', 'Infinit',
                    'Infinite5', 'Second-x', 'Second-1x', 'In finite',
                    'Second-10 5', 'Infinite-Infinite', 'Second--1'):
            c.append((TP, 'bad_value:timeout.item', (bad,)))
        for bad in ('Second-4294967296', 'Second-000000000004294967296',
                    'Second-99999999999'):
            c.append((TP, 'bad_value:timeout.second_range', (bad,)))
        for bad in ('urn:uuid:x', '<urn:uuid:x', 'urn:uuid:x>',
                    '<urn:uuid:a<b>', '<urn:uuid:a>x', '<<urn:uuid:a>>',
                    '<urn:uuid:a>>', '<<urn:uuid:a>', '<>x>'):
            c.append((LP, 'bad_value:lock_token.brackets', (bad,)))
        for bad in ('<>', '< urn:uuid:x>', '</rel/path>', '<urn>',
                    '<http://ex.com/%zz>', '<1http://x/>'):
            c.append((LP, 'bad_value:lock_token.uri', (bad,)))
        for bad in ('', 'rel/path', '//host/path', '/a b', '/a?x=|',
                    'http://ex.com/a#frag', 'http://ex.com/%4',
                    '1http://x/', 'http://exa mple.com/',
                    'http://1.2.3/', 'http://1.2..4/',
                    'http://1.2.3.1234/', 'http://01.2.3.4/',
                    'http://256.1.1.1/', 'http://u ser@h/',
                    'http://[::1', 'http://[]/', 'http://[a b]/',
                    'http://[::1]x/p', 'http://ex.com:8x/p',
                    'ht tp://x/', '/%zz', '/a#b', 'http://x/p#f',
                    'http://ex.com/a b', 'http://ex.com/a?x=|',
                    'a:b c', 'a:?q=|', '/%4x', 'http://e.com/%4x', '/%x4',
                    'http://e.com/%x4'):
            c.append((XP, 'bad_value:destination', (bad,)))
        c.append((FP, 'bad_value:if.empty', (' ',)))
        c.append((FP, 'bad_value:if.mixed',
                  ('(<urn:uuid:a>) <urn:uuid:t>',)))
        for bad in ('(<urn:uuid:a', '(<>)', '(<a<b>)', '(<a b>)'):
            c.append((FP, 'bad_value:if.token', (bad,)))
        for bad in ('([etag])', '(["unterminated)', '(["a" ])',
                    '([W])', '([W/])', '(["a"x])',
                    '([etag"x"])', '([W/x"])'):
            c.append((FP, 'bad_value:if.etag', (bad,)))
        for bad in ('()', '( )', '(junk)', '(<urn:uuid:a> junk)',
                    '(Not)', '(notx)', '(["a"]x)', '(Not?)'):
            c.append((FP, 'bad_value:if.condition', (bad,)))
        for bad in ('(', '(<urn:uuid:a>', 'x(<urn:uuid:a>)',
                    '(<urn:uuid:a>)x', '(<urn:uuid:a>) x',
                    '<urn:uuid:a>x (<urn:uuid:b>)'):
            c.append((FP, 'bad_value:if.list', (bad,)))
        for bad in ('<urn:uuid:t', '< urn:uuid:t> (<urn:uuid:a>)',
                    '<> (<urn:uuid:a>)', '<a<b> (<urn:uuid:a>)',
                    '<rel> (<urn:uuid:a>)', '<//h> (<urn:uuid:a>)',
                    '<urn:uuid:t1> <urn:uuid:t2> (<urn:uuid:a>)'):
            c.append((FP, 'bad_value:if.tag', (bad,)))
        c.append((FP, 'bad_value:if.tag',
                  ('<urn:uuid:t1> (<urn:uuid:a>) <urn:uuid:t2>',)))
        _REFU_CACHE = c
    return _REFU_CACHE


def _bounded_call(fn_name, arg, bound=1.0):
    'Run a parse under a hard real-time bound; AssertionError on overrun.'
    fn = getattr(m, fn_name)
    if not hasattr(signal, 'setitimer') or not hasattr(signal, 'SIGALRM'):
        return fn(arg)
    def stop(*a):
        raise AssertionError(
            'parse exceeded 1.0s bound: a scan loop did not advance')
    old = signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, bound)
    try:
        return fn(arg)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def test_loops_advance_under_time_bound():
    for fn_name, args in _success_corpus():
        _bounded_call(fn_name, args[0])
    try:
        _bounded_call(FP, 'x' * 8193)
    except ValueError:
        pass
    else:
        raise AssertionError('cap-boundary input must not be reached '
                             'here or must refuse cleanly')


def test_module_docstring_is_pinned_whole():
    assert m.__doc__ == __DOC__


def test_rfc4918_s10_4_examples():
    # s10.4.6 No-tag production (unfolded)
    r = m.dav_if_parse(
        '(<urn:uuid:181d4fae-7d8c-11d0-a765-00a0c91e6bf2> '
        '["I am an ETag"]) (["I am another ETag"])')
    assert r['tagged'] is False
    assert len(r['groups']) == 1
    assert r['groups'][0]['tag'] is None
    l1, l2 = r['groups'][0]['lists']
    assert l1[0] == {'negated': False, 'kind': 'state-token',
                     'value': 'urn:uuid:181d4fae-7d8c-11d0-a765-'
                              '00a0c91e6bf2', 'weak': False}
    assert l1[1] == {'negated': False, 'kind': 'entity-tag',
                     'value': 'I am an ETag', 'weak': False}
    assert l2 == [{'negated': False, 'kind': 'entity-tag',
                   'value': 'I am another ETag', 'weak': False}]
    # s10.4.7 "Not" with no-tag production (Verified EID 1068 fixes
    # only its indentation; the tokens are these)
    r = m.dav_if_parse(
        '(Not <urn:uuid:181d4fae-7d8c-11d0-a765-00a0c91e6bf2> '
        '<urn:uuid:58f202ac-22cf-11d1-b12d-002035b29092>)')
    assert [c['negated'] for c in r['groups'][0]['lists'][0]] == [
        True, False]
    # s10.4.8: DAV:no-lock is a valid absolute-URI state token
    r = m.dav_if_parse(
        '(<urn:uuid:181d4fae-7d8c-11d0-a765-00a0c91e6bf2>) '
        '(Not <DAV:no-lock>)')
    assert r['groups'][0]['lists'][1][0]['value'] == 'DAV:no-lock'
    assert r['canonical'] is True


def test_rfc4918_simple_header_examples():
    # s10.2
    assert m.dav_depth_parse('0')['value'] == '0'
    assert m.dav_depth_parse('1')['value'] == '1'
    assert m.dav_depth_parse('infinity')['value'] == 'infinity'
    # s10.6
    assert m.dav_overwrite_parse('T')['overwrite'] is True
    assert m.dav_overwrite_parse('F')['overwrite'] is False
    # s10.7: 'Timeout: Second-604800, Infinite'
    r = m.dav_timeout_parse('Second-604800, Infinite')
    assert r['types'] == [{'kind': 'second', 'seconds': 604800},
                          {'kind': 'infinite'}]
    # s10.5
    r = m.dav_lock_token_parse(
        '<urn:uuid:181d4fae-7d8c-11d0-a765-00a0c91e6bf2>')
    assert r['token'] == 'urn:uuid:181d4fae-7d8c-11d0-a765-00a0c91e6bf2'
    # s10.3: absolute-URI and path-absolute forms
    r = m.dav_destination_parse('http://example.com/dir/file')
    assert r['absolute'] is True
    assert r['destination'] == 'http://example.com/dir/file'
    r = m.dav_destination_parse('/dir/file')
    assert r['absolute'] is False


def test_casing_and_canonical_rules():
    # ABNF literals are case-insensitive (RFC 2234 s2.3); the OURS
    # canonical text uses the RFC example casing
    r = m.dav_depth_parse('INFINITY')
    assert r['value'] == 'infinity' and r['canonical'] is False
    r = m.dav_depth_parse('Infinity')
    assert r['canonical_text'] == 'infinity'
    r = m.dav_overwrite_parse('f')
    assert r['canonical_text'] == 'F' and r['overwrite'] is False
    r = m.dav_timeout_parse('SECOND-007')
    assert r['canonical_text'] == 'Second-7' and r['canonical'] is False
    assert r['types'] == [{'kind': 'second', 'seconds': 7}]
    r = m.dav_timeout_parse('infinite')
    assert r['canonical_text'] == 'Infinite' and r['canonical'] is False
    r = m.dav_if_parse('(not <urn:uuid:a> NOT [w/"e"])')
    assert r['canonical_text'] == '(Not <urn:uuid:a> Not [W/"e"])'
    assert r['canonical'] is False
    assert [c['negated'] for c in r['groups'][0]['lists'][0]] == [
        True, True]
    assert r['groups'][0]['lists'][0][1]['weak'] is True
    # outer OWS is stripped before parsing (RFC 2616 s4.2)
    assert m.dav_depth_parse('\t0\t')['value'] == '0'
    assert m.dav_if_parse(' (<urn:uuid:a>) ')['canonical'] is True
    assert m.dav_if_parse(' (<urn:uuid:a>) ')['canonical_text'] == (
        '(<urn:uuid:a>)')
    # Lock-Token and Destination define no normalization: canonical
    # is always True on the stripped value
    assert m.dav_lock_token_parse(' <urn:uuid:x> ')['canonical'] is True
    assert m.dav_lock_token_parse(' <urn:uuid:x> ')[
        'canonical_text'] == '<urn:uuid:x>'
    assert m.dav_destination_parse(' /a ')['canonical'] is True
    assert m.dav_destination_parse(' /a ')['canonical_text'] == '/a'
    # LWS inside a TimeType refuses (s10.7 grammar comment)
    refuse(TP, 'bad_value:timeout.item', 'Second- 10')
    refuse(TP, 'bad_value:timeout.item', 'In finite')


def test_if_structure_rules():
    # tagged and no-tag lists cannot mix (s10.4.2)
    refuse(FP, 'bad_value:if.mixed', '(<urn:uuid:a>) <urn:uuid:t>')
    # a Resource-Tag applies to all following Lists up to the next tag
    r = m.dav_if_parse('<http://e.com/a> (<urn:uuid:x>) (<urn:uuid:y>) '
                       '</b> (<urn:uuid:z>)')
    assert [g['tag'] for g in r['groups']] == [
        'http://e.com/a', '/b']
    assert [len(g['lists']) for g in r['groups']] == [2, 1]
    # a Resource-Tag must be followed by at least one List
    refuse(FP, 'bad_value:if.tag', '<urn:uuid:t1> <urn:uuid:t2> '
                                   '(<urn:uuid:a>)')
    refuse(FP, 'bad_value:if.tag', '<urn:uuid:t1> (<urn:uuid:a>) '
                                   '<urn:uuid:t2>')
    refuse(FP, 'bad_value:if.tag', '<urn:uuid:t>')
    # No LWS in a Resource-Tag or Coded-URL (s10.4.2 comments)
    refuse(FP, 'bad_value:if.tag', '< urn:uuid:t> (<urn:uuid:a>)')
    refuse(FP, 'bad_value:if.token', '(< urn:uuid:a>)')
    # No LWS between "[", entity-tag and "]" (s10.4.2 comment)
    refuse(FP, 'bad_value:if.etag', '(["a" ])')
    # "Not" is only a negation when a token follows
    refuse(FP, 'bad_value:if.condition', '(Not)')
    refuse(FP, 'bad_value:if.condition', '(notx)')
    r = m.dav_if_parse('(Not<urn:uuid:a>)')
    assert r['groups'][0]['lists'][0][0]['negated'] is True
    assert r['canonical'] is False  # canonical inserts the space


def test_timeout_rules():
    # 1#TimeType: null elements are allowed and ignored (RFC 2616 s2.1)
    r = m.dav_timeout_parse('Second-1, ,Second-2,')
    assert [t['seconds'] for t in r['types']] == [1, 2]
    # the "Second" value MUST NOT exceed 2^32-1 (s10.7)
    m.dav_timeout_parse('Second-4294967295')
    refuse(TP, 'bad_value:timeout.second_range', 'Second-4294967296')
    # at least one TimeType is required
    refuse(TP, 'bad_value:timeout.list', ' , ,')
    refuse(TP, 'bad_value:timeout.list', '')


def test_result_shape_and_freshness():
    r = m.dav_depth_parse('0')
    assert list(r) == ['value', 'canonical_text', 'canonical']
    r = m.dav_overwrite_parse('T')
    assert list(r) == ['overwrite', 'canonical_text', 'canonical']
    assert type(r['overwrite']) is bool
    r = m.dav_timeout_parse('Second-30')
    assert list(r) == ['types', 'canonical_text', 'canonical']
    assert list(r['types'][0]) == ['kind', 'seconds']
    r = m.dav_lock_token_parse('<urn:uuid:x>')
    assert list(r) == ['token', 'canonical_text', 'canonical']
    r = m.dav_destination_parse('/a')
    assert list(r) == ['destination', 'absolute', 'canonical_text',
                       'canonical']
    assert type(r['absolute']) is bool
    r = m.dav_if_parse('(<urn:uuid:x>)')
    assert list(r) == ['tagged', 'groups', 'canonical_text',
                       'canonical']
    assert type(r['tagged']) is bool and type(r['canonical']) is bool
    assert list(r['groups'][0]) == ['tag', 'lists']
    assert list(r['groups'][0]['lists'][0][0]) == [
        'negated', 'kind', 'value', 'weak']
    a = m.dav_if_parse('(<urn:uuid:x>)')
    a['groups'][0]['lists'][0][0]['value'] = 'MUTATED'
    a['canonical_text'] = 'MUTATED'
    b = m.dav_if_parse('(<urn:uuid:x>)')
    assert b['groups'][0]['lists'][0][0]['value'] == 'urn:uuid:x'
    assert b['canonical_text'] == '(<urn:uuid:x>)'
    assert a is not b
def test_header_refusals():
    for fn_name, code, args in _refusal_corpus():
        refuse(fn_name, code, *args)


def test_exact_types_refuse():
    for fn in PARSE_FNS:
        for bad in (None, 0, True, 5.5, b'0', ['0'], (1,),
                    _StrSub('0')):
            refuse(fn, 'bad_type:value', bad)
            assert getattr(m, fn.replace('_parse', '_is_valid'))(
                bad) is False


def test_input_length_cap():
    # exactly at the OURS cap: accepted; one past: refused
    pad = 8192 - len('(<urn:uuid:' + '>)')
    ok = '(<urn:uuid:' + 'x' * pad + '>)'
    assert len(ok) == 8192
    m.dav_if_parse(ok)
    refuse(FP, 'bad_value:input.length', ok + 'x')
    for fn in PARSE_FNS:
        refuse(fn, 'bad_value:input.length', 'x' * 8193)


def test_refusal_order():
    # type before length cap before charset before header syntax
    refuse(DP, 'bad_type:value', 0)
    refuse(DP, 'bad_value:input.length', 'x' * 8193)
    refuse(DP, 'bad_value:value.charset', 'a\rb')
    refuse(DP, 'bad_value:value.charset', '2\r')
    refuse(DP, 'bad_value:depth', '2')
    refuse(FP, 'bad_value:input.length', 'x' * 8193)
    refuse(FP, 'bad_value:value.charset', '(<urn:uuid:\x80a>)')
    refuse(FP, 'bad_value:if.empty', ' ')
    refuse(FP, 'bad_value:if.mixed', '(<urn:uuid:a>) <urn:uuid:t>')
    # lock_token: brackets before uri
    refuse(LP, 'bad_value:lock_token.brackets', 'x')
    refuse(LP, 'bad_value:lock_token.brackets', '<a<b>>')
    refuse(LP, 'bad_value:lock_token.uri', '<>')
    # timeout: item before range within one bad item
    refuse(TP, 'bad_value:timeout.item', 'Second-')
    refuse(TP, 'bad_value:timeout.second_range', 'Second-4294967296')
    # timeout: an earlier item refuses before a later item is read
    refuse(TP, 'bad_value:timeout.item', 'junk, Second-4294967296')
    refuse(TP, 'bad_value:timeout.second_range',
           'Second-4294967296, junk')


def test_is_valid_returns_exact_bool():
    for fn in PARSE_FNS:
        is_valid = getattr(m, fn.replace('_parse', '_is_valid'))
        v = is_valid('0' if fn == DP else {'dav_overwrite_parse': 'T',
                                           'dav_timeout_parse':
                                           'Second-1',
                                           'dav_lock_token_parse':
                                           '<urn:uuid:x>',
                                           'dav_destination_parse':
                                           '/a',
                                           'dav_if_parse':
                                           '(<urn:uuid:x>)'}[fn])
        assert v is True and type(v) is bool
        assert is_valid('garbage !@#') is False
        assert is_valid(None) is False
        assert is_valid(0) is False


def test_constants_pinned_whole():
    assert m._MAX_INPUT_LENGTH == 8192
    assert m._MAX_SECOND == 4294967295
    assert m._HEXDIGITS == frozenset('0123456789abcdefABCDEF')
    assert m._UNRESERVED == frozenset(
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        '0123456789' '-._~')
    assert m._SUB_DELIMS == frozenset('!$&\'()*+,;=')
    assert m._PCHAR == m._UNRESERVED | m._SUB_DELIMS | frozenset(':@%')
    assert m._PATH_CHARS == m._PCHAR | frozenset('/')
    assert m._QUERY_CHARS == m._PCHAR | frozenset('/?')
    assert m._USERINFO_CHARS == (m._UNRESERVED | m._SUB_DELIMS
                                 | frozenset(':%'))
    assert m._REGNAME_CHARS == (m._UNRESERVED | m._SUB_DELIMS
                                | frozenset('%'))
    assert m._LIT_CHARS == m._REGNAME_CHARS | frozenset(':.')


def test_function_docstrings_pinned_exact():
    assert m.dav_depth_parse.__doc__ == (
        'Validate an RFC 4918 s10.2 Depth header value.')
    assert m.dav_depth_is_valid.__doc__ == (
        'True iff dav_depth_parse(text) would succeed.')
    assert m.dav_overwrite_parse.__doc__ == (
        'Validate an RFC 4918 s10.6 Overwrite header value.')
    assert m.dav_overwrite_is_valid.__doc__ == (
        'True iff dav_overwrite_parse(text) would succeed.')
    assert m.dav_timeout_parse.__doc__ == (
        'Validate an RFC 4918 s10.7 Timeout request header value.')
    assert m.dav_timeout_is_valid.__doc__ == (
        'True iff dav_timeout_parse(text) would succeed.')
    assert m.dav_lock_token_parse.__doc__ == (
        'Validate an RFC 4918 s10.5 Lock-Token header value.')
    assert m.dav_lock_token_is_valid.__doc__ == (
        'True iff dav_lock_token_parse(text) would succeed.')
    assert m.dav_destination_parse.__doc__ == (
        'Validate an RFC 4918 s10.3 Destination header value.')
    assert m.dav_destination_is_valid.__doc__ == (
        'True iff dav_destination_parse(text) would succeed.')
    assert m.dav_if_parse.__doc__ == (
        'Validate an RFC 4918 s10.4 If header value.')
    assert m.dav_if_is_valid.__doc__ == (
        'True iff dav_if_parse(text) would succeed.')


def test_module_namespace_is_pinned():
    names = set(vars(m))
    assert names == {
        '__name__', '__doc__', '__package__', '__loader__',
        '__spec__', '__file__', '__cached__', '__builtins__',
        'find_spec', 'make_fail',
        '_MAX_INPUT_LENGTH', '_MAX_SECOND', '_HEXDIGITS',
        '_UNRESERVED', '_SUB_DELIMS', '_PCHAR', '_PATH_CHARS',
        '_QUERY_CHARS', '_USERINFO_CHARS', '_REGNAME_CHARS',
        '_LIT_CHARS',
        '_check_text', '_check_pct', '_all_in', '_valid_host',
        '_valid_authority', '_valid_path_query',
        '_valid_absolute_uri', '_valid_simple_ref',
        '_scan_entity_tag', '_scan_coded_url',
        'dav_depth_parse', 'dav_depth_is_valid',
        'dav_overwrite_parse', 'dav_overwrite_is_valid',
        'dav_timeout_parse', 'dav_timeout_is_valid',
        'dav_lock_token_parse', 'dav_lock_token_is_valid',
        'dav_destination_parse', 'dav_destination_is_valid',
        'dav_if_parse', 'dav_if_is_valid'}


def test_parse_is_deterministic_and_consistent():
    rng = random.Random(1228)
    alphabet = '019tTfFiNseco<>"[]()/,.?:%wW -dAxz\t\\'
    for fn in PARSE_FNS:
        for _ in range(150):
            blob = ''.join(rng.choice(alphabet)
                           for _ in range(rng.randrange(0, 24)))
            parse = getattr(m, fn)
            is_valid = getattr(m, fn.replace('_parse', '_is_valid'))
            try:
                r1 = parse(blob)
            except ValueError:
                assert is_valid(blob) is False
            else:
                assert is_valid(blob) is True
                assert parse(blob) == r1
                # the canonical text always re-parses, canonically
                r2 = parse(r1['canonical_text'])
                assert r2['canonical'] is True
                assert r2['canonical_text'] == r1['canonical_text']


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
        mod = types.ModuleType('fresh_b1228')
        with pytest.raises(ModuleNotFoundError):
            exec(compile(src, 'fresh_b1228', 'exec'), mod.__dict__)
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
            ('import no_such_dep_xyz_1228\n', 'ModuleNotFoundError'),
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
        mod = types.ModuleType('fresh_b1228_spy')
        exec(compile(src, 'fresh_b1228_spy', 'exec'), mod.__dict__)
    finally:
        _stop_import()
        _iu.find_spec = real_find_spec
    assert calls == [REG], calls
    # the fallback engaged and works
    assert mod.dav_depth_is_valid('0') is True
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        assert str(e) == 'P235:x:c'
    else:
        raise AssertionError('fallback make_fail did not raise')


def test_battery_rev0_pins():
    # exactly at the OURS cap: accepted; one past: refused
    pad = 8192 - len('(<urn:uuid:' + '>)')
    ok = '(<urn:uuid:' + 'x' * pad + '>)'
    assert m.dav_if_parse(ok)['canonical_text'] == ok
    refuse(FP, 'bad_value:input.length', 'x' * 8193)
    # the Second- ceiling is 2^32-1 exactly (s10.7)
    m.dav_timeout_parse('Second-4294967295')
    refuse(TP, 'bad_value:timeout.second_range', 'Second-4294967296')
    # "Infinite" alone is legal; an empty value is not
    m.dav_timeout_parse('Infinite')
    refuse(TP, 'bad_value:timeout.list', '')
    # the tagged / no-tag boundary is the FIRST element
    m.dav_if_parse('</rel> (<urn:uuid:a>)')
    # a tagged canonical text carries its Resource-Tag
    r = m.dav_if_parse('<http://e.com/a> (<urn:uuid:x>)')
    assert r['canonical_text'] == '<http://e.com/a> (<urn:uuid:x>)'
    assert r['canonical'] is True
    refuse(FP, 'bad_value:if.mixed', '(<urn:uuid:a>) </rel>')
    # a state token is an absolute-URI only; an etag needs quotes
    refuse(FP, 'bad_value:if.token', '(<rel>)')
    refuse(FP, 'bad_value:if.etag', '([bare])')
    # weak-prefix boundary: w/ both cases, W alone is not an etag
    m.dav_if_parse('([w/"e"])')
    refuse(FP, 'bad_value:if.etag', '([W"e"])')
    # Destination refuses a fragment; Lock-Token refuses a relative ref
    refuse(XP, 'bad_value:destination', '/a#frag')
    refuse(LP, 'bad_value:lock_token.uri', '</rel>')
    # str subclasses refuse with the type code
    for fn in PARSE_FNS:
        refuse(fn, 'bad_type:value', _StrSub('0'))



def test_battery_rev1_pins():
    # A45 F1 is the s10.4.2 Resource-Tag docstring quote (whole-
    # docstring pin covers it).  A45 F2-F5 + A46 1-9 below.

    # A45 F2: '~' (unreserved) accepted in the path
    r = m.dav_destination_parse('http://a/~x')
    assert r['absolute'] is True

    # A45 F3: 255 octets accepted (the >= 255 boundary)
    assert m.dav_destination_parse('http://10.0.0.255/')['absolute'] is True
    r = m.dav_lock_token_parse('<http://255.255.255.255/x>')
    assert r['token'] == 'http://255.255.255.255/x'
    refuse('dav_lock_token_parse', 'bad_value:lock_token.uri',
           '<http://255.255.255.256/x>')
    refuse('dav_destination_parse', 'bad_value:destination',
           'http://10.0.0.256/')

    # A45 F4: '-' in the scheme
    assert m.dav_destination_parse('foo-bar://h/x')['absolute'] is True
    r = m.dav_if_parse('(<a-b:c>)')
    assert r['groups'][0]['lists'][0][0]['value'] == 'a-b:c'

    # A45 F5: 'Second10' (no dash) refuses timeout.item
    refuse('dav_timeout_parse', 'bad_value:timeout.item', 'Second10')

    # A46 1: scheme chars '+.-' in every URI-bearing header
    for fn, wrapped in (('dav_destination_parse', 'ht.tp://h/%41ok'),
                        ('dav_lock_token_parse', '<ht.tp://h/%41ok>')):
        assert getattr(m, fn)(wrapped)
    for fn, wrapped in (('dav_destination_parse', 'Z+a9:Xc1Y'),
                        ('dav_lock_token_parse', '<Z+a9:Xc1Y>')):
        assert getattr(m, fn)(wrapped)
    r = m.dav_if_parse('(<Z+a9:Xc1Y>)')
    assert r['groups'][0]['lists'][0][0]['value'] == 'Z+a9:Xc1Y'

    # A46 2: 'Not' LWS-skip and entity-tag scan guards raise
    # ValueError, never IndexError
    refuse('dav_if_parse', 'bad_value:if.condition', '( Not')
    refuse('dav_if_parse', 'bad_value:if.condition', '( Not ')
    refuse('dav_if_parse', 'bad_value:if.etag', '( [')
    refuse('dav_if_parse', 'bad_value:if.etag', '( [W/"x"')

    # A46 3: the scheme scan requires ':' before any space
    refuse('dav_lock_token_parse', 'bad_value:lock_token.uri',
           '<ht tp://h/>')

    # A46 4: Overwrite 'T' is already canonical
    r = m.dav_overwrite_parse('T')
    assert r['canonical'] is True and r['canonical_text'] == 'T'
    assert r['overwrite'] is True
    r = m.dav_overwrite_parse('t')
    assert r['canonical'] is False and r['canonical_text'] == 'T'

    # A46 5: a multi-group Tagged-list keeps both groups, in order
    r = m.dav_if_parse('<http://t1/> (<urn:a>) <http://t2/> (<urn:b>)')
    assert r['tagged'] is True
    assert [g['tag'] for g in r['groups']] == ['http://t1/', 'http://t2/']
    assert r['groups'][0]['lists'][0][0]['value'] == 'urn:a'
    assert r['groups'][1]['lists'][0][0]['value'] == 'urn:b'

    # A46 6: the pct scan advances past a good triplet and still
    # refuses a later bad one
    refuse('dav_lock_token_parse', 'bad_value:lock_token.uri',
           '<http://h/%20%zz>')
    refuse('dav_destination_parse', 'bad_value:destination',
           'http://h/%20%zz')

    # A46 7: 'Z+a9:Xc1Y' accepted (above) while '#' stays refused
    refuse('dav_destination_parse', 'bad_value:destination',
           'Z+a9:X#c1Y')
    refuse('dav_lock_token_parse', 'bad_value:lock_token.uri',
           '<http://h/x#y>')

    # A46 8: strip charsets - tab OWS around timeout items accepted;
    # a leading junk char in the If value refuses if.list
    r = m.dav_timeout_parse('Infinite\t,\tSecond-10')
    assert r['types'] == [{'kind': 'infinite'},
                          {'kind': 'second', 'seconds': 10}]
    refuse('dav_if_parse', 'bad_value:if.list', 'Z(\\)9a0en')
    refuse('dav_if_parse', 'bad_value:if.list', 'x')
    refuse('dav_if_parse', 'bad_value:if.list', ']')

    # A46 9: canonical_text separators are exact single-','/' '
    # joins
    r = m.dav_timeout_parse(' Second-5 , Infinite ')
    assert r['canonical_text'] == 'Second-5, Infinite'
    assert r['canonical'] is False
    r = m.dav_if_parse(
        '<http://t1/>  (<urn:a>)   <http://t2/>   (<urn:b>)')
    assert (r['canonical_text']
            == '<http://t1/> (<urn:a>) <http://t2/> (<urn:b>)')
    assert r['canonical'] is False

    # A46 hang-kills: bounded parse on junk inside a list (the
    # 30s alarm kills an index-unadvanced mutant)
    refuse('dav_if_parse', 'bad_value:if.condition', '( ~')
    refuse('dav_if_parse', 'bad_value:if.condition', '( ~)')
    refuse('dav_if_parse', 'bad_value:if.condition', '( & <urn:a>)')
    refuse('dav_if_parse', 'bad_value:if.condition', '( <urn:a> ~)')
    refuse('dav_if_parse', 'bad_value:if.condition', '( Not ~)')

    # 'Not' pins while here: case-insensitive, LWS optional, and
    # canonical form is 'Not <token>'
    for neg in ('(Not<urn:a>)', '(NOT <urn:a>)', '( Not<urn:a>)'):
        r = m.dav_if_parse(neg)
        assert r['groups'][0]['lists'][0][0]['negated'] is True
        assert r['canonical_text'] == '(Not <urn:a>)'
        assert r['canonical'] is False
    refuse('dav_if_parse', 'bad_value:if.etag', '( Not [<"x">])')


def test_battery_rev2_pins():
    # A40 rev1 FINAL: 6 survivor classes, module AST unchanged.

    # L209: a second '@' in the authority refuses with the P235
    # code (a bare unpack ValueError would escape as-is)
    refuse(XP, 'bad_value:destination', 'http://a@b@c/x')
    # L216: IP-literal inner first char outside the literal class
    refuse(LP, 'bad_value:lock_token.uri', '<http://[^::1]/x>')
    # L221: non-numeric port after a bracketed literal host
    refuse(LP, 'bad_value:lock_token.uri', '<http://[::1]:abc/>')
    # L225: a multi-colon host:port refuses with the P235 code
    refuse(XP, 'bad_value:destination', 'http://h:80:90/x')
    # L257: the authority terminator scan stops at '?' as well as
    # '/', so an empty path plus query after authority accepts
    r = m.dav_lock_token_parse('<http://ex.com?x>')
    assert r['token'] == 'http://ex.com?x'
    # L302: an escaped quote right before the closing quote is
    # data, not the terminator
    r = m.dav_if_parse('(["\\""])')
    cond = r['groups'][0]['lists'][0][0]
    assert cond['kind'] == 'entity-tag'
    assert cond['value'] == '\\"'


__DOC__ = 'RFC 4918 "HTTP Extensions for Web Distributed Authoring and\nVersioning (WebDAV)": the request-header grammars of s10.2\n(Depth), s10.3 (Destination), s10.4 (If), s10.5 (Lock-Token),\ns10.6 (Overwrite) and s10.7 (Timeout), over Python text\nstrings carrying the header VALUE (the part after ":").\nMethod semantics, lock semantics, the DAV response header\n(s10.1) and all body formats are out of scope.\n\nPublic API (each parse raises ValueError on refusal; each\nis_valid returns True iff its parse would succeed):\n\n  dav_depth_parse(text) -> {\'value\': \'0\' | \'1\' | \'infinity\',\n      \'canonical_text\': str, \'canonical\': bool}\n  dav_overwrite_parse(text) -> {\'overwrite\': bool,\n      \'canonical_text\': \'T\' | \'F\', \'canonical\': bool}\n  dav_timeout_parse(text) -> {\'types\': list of\n      {\'kind\': \'second\', \'seconds\': int} or\n      {\'kind\': \'infinite\'}, \'canonical_text\', \'canonical\'}\n  dav_lock_token_parse(text) -> {\'token\': the inner\n      absolute-URI, \'canonical_text\', \'canonical\'}\n  dav_destination_parse(text) -> {\'destination\': str,\n      \'absolute\': True for the absolute-URI form, False for\n      the path-absolute form, \'canonical_text\', \'canonical\'}\n  dav_if_parse(text) -> {\'tagged\': bool, \'groups\': list of\n      {\'tag\': None or the Resource-Tag Simple-ref string,\n       \'lists\': list of lists of condition dicts\n       {\'negated\': bool, \'kind\': \'state-token\' or\n        \'entity-tag\', \'value\': str (the State-token URI or\n        the entity-tag\'s quoted content, escapes intact),\n        \'weak\': bool}}, \'canonical_text\', \'canonical\'}\n\nGrammar notes (verified against the RFC 4918 text).  s10.2:\n\'Depth = "Depth" ":" ("0" | "1" | "infinity")\'.  s10.3:\n\'Destination = "Destination" ":" Simple-ref\'.  s10.5:\n\'Lock-Token = "Lock-Token" ":" Coded-URL\'.  s10.6:\n\'Overwrite = "Overwrite" ":" ("T" | "F")\'.  s10.7: \'TimeOut\n= "Timeout" ":" 1#TimeType\', \'TimeType = ("Second-"\nDAVTimeOutVal | "Infinite") ; No LWS allowed within\nTimeType\', \'DAVTimeOutVal = 1*DIGIT\', and \'The timeout value\nfor TimeType "Second" MUST NOT be greater than 2^32-1\'.\ns10.4.2: \'If = "If" ":" ( 1*No-tag-list | 1*Tagged-list )\',\n\'No-tag-list = List\', \'Tagged-list = Resource-Tag 1*List\',\n\'List = "(" 1*Condition ")"\', \'Condition = ["Not"]\n(State-token | "[" entity-tag "]")\' with \'; entity-tag: see\nSection 3.11 of [RFC2616]\' and \'; No LWS allowed between\n"[", entity-tag and "]"\', \'State-token = Coded-URL\',\n\'Resource-Tag = "<" Simple-ref ">" ; Simple-ref: see\nSection 8.3 ; No LWS allowed in Resource-Tag\'.  s10.1: \'Coded-URL = "<" absolute-URI ">"\'.\ns8.3: \'Simple-ref = absolute-URI | ( path-absolute [ "?"\nquery ] )\' with absolute-URI, path-absolute and query from\nRFC 3986 s3, s3.3 and s3.4.  RFC 2616 s3.11: entity-tag =\n[ weak ] opaque-tag, weak = "W/", opaque-tag =\nquoted-string (RFC 2616 s2.2: quoted-string = ( \'"\' *(qdtext\n| quoted-pair) \'"\' ), quoted-pair = "\\" CHAR).\n\nCasing: RFC 4918 and RFC 2616 use the ABNF of RFC 2234,\nwhose s2.3 makes quoted literals case-insensitive, so the\ntokens "0", "1", "infinity", "T", "F", "Second-",\n"Infinite", "Not" and "W/" match case-insensitively on\ninput.  The RFCs define no canonical text form for these\nheaders; the canonical_text emitted here (OURS) uses the\ncasing of the RFC examples: \'infinity\', \'T\', \'F\',\n\'Second-N\' with no leading zeros, \'Infinite\', \'Not\', \'W/\',\nsingle spaces as separators, no LWS after \'(\' or before\n\')\', ", " between Timeout items, and the URI / quoted\ncontent byte-for-byte as received.  \'canonical\' is True iff\nthe OWS-stripped input IS that canonical text; Lock-Token\nand Destination define no normalization, so for them\ncanonical_text is the stripped input and \'canonical\' is\nalways True.\n\nLWS handling: per RFC 2616 s2.1, LWS (SP/HT) may appear\nbetween adjacent words, and per s2.1\'s #rule null elements\nbetween commas are allowed and ignored, so Timeout accepts\nand drops them; per the grammar comments, NO LWS is allowed\ninside Resource-Tag, Coded-URL, the "[" entity-tag "]"\nform, or within a TimeType.  Leading/trailing OWS around\nthe whole value is stripped before parsing (RFC 2616 s4.2:\nfield-content excludes leading and trailing LWS).\n\'Not\' is recognized only when followed by optional LWS and\nthen \'<\' or \'[\'; anything else that starts with those\nletters is parsed as a token start and refuses there.\n\nURI validation is SYNTAX ONLY (OURS): scheme per RFC 3986\ns3.1, authority with optional userinfo and port, strict\ndec-octet IPv4 hosts, bracketed IP-literals checked by\ncharacter class only (no IPv6/IPvFuture grammar\nvalidation), reg-name by character class, pct-encoding\nenforced (\'%\' must be followed by two HEXDIG) in every\ncomponent, pchar/sub-delims/unreserved character classes\nfor path and query, and no \'#\' fragment anywhere (neither\nSimple-ref production admits one).  Sender conformance\nrules of s8.3 (no dot-segments; Request-URI prefix match)\nare NOT enforced - Verified erratum 1519 confirms those are\nsender-side rules, not syntax.\n\nRefusal order (exactly as executed, per function):\nbad_type:value (not exactly str); bad_value:input.length\n(longer than _MAX_INPUT_LENGTH = 8192); bad_value:\nvalue.charset (any char outside HT and 0x20-0x7E); then,\nafter OWS stripping: depth -> bad_value:depth; overwrite ->\nbad_value:overwrite; timeout -> bad_value:timeout.list (no\nTimeType at all), then per item bad_value:timeout.item\n(malformed TimeType, including LWS inside one or a "Second-"\nwith no digits) or bad_value:timeout.second_range (digits\nwhose value exceeds 4294967295); lock_token ->\nbad_value:lock_token.brackets (not exactly "<...>"), then\nbad_value:lock_token.uri; destination ->\nbad_value:destination; if -> bad_value:if.empty, then while\nscanning bad_value:if.list (junk at element start, an\nunbalanced or tag-less List in tagged mode),\nbad_value:if.mixed (a Resource-Tag after a No-tag-list),\nbad_value:if.tag (Resource-Tag malformed, LWS inside, bad\nSimple-ref, or a Resource-Tag not followed by a List),\nbad_value:if.condition (empty List or junk where a\nCondition belongs), bad_value:if.token (State-token\nmalformed, LWS inside, or bad absolute-URI),\nbad_value:if.etag (entity-tag malformed).\n\nErrata: RFC 4918 has 9 records (3 Verified, 3 Held, 3\nReported; none folded).  Verified EID 1519 (s8.3) narrows\nthe Request-URI prefix rule to Multi-Status responses and\nkeeps the dot-segment ban sender-side - see the URI note\nabove.  Verified EID 1068 (s10.4.7) fixes example\nindentation only.  Verified EID 1430 (s9.3) restores MKCOL\nprose - no header grammar.  Held EIDs 1207 (s9.10.1), 1371\n(s9.2) and 1635 (s7.4) touch LOCK bodies and depth\nsemantics, not these header grammars.  Reported EIDs 4431\n(GLOBAL), 4435 and 4440 (s9.8.x) are unverified.\n'
