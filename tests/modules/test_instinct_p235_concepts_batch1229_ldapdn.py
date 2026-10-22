import ast
import builtins
import contextlib
import importlib
import importlib.util
import itertools
import json
import os
import random
import re
import signal
import subprocess
import sys
import urllib.request

import pytest

from app.modules.instinct_doc import p235_concepts_batch1229_ldapdn as m
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
STUB_WORLD = importlib.util.find_spec(REG) is not None
PFX = 'STUB:' if STUB_WORLD else 'P235:'
SRC_PATH = m.__file__
FNS = ('dn_ok', 'attribute_type_ok', 'parse_dn', 'format_dn')
ALPHA = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
DIGIT = '0123456789'


class StrSub(str):
    pass


class EqStr(str):
    def __eq__(self, other):
        return True

    def __hash__(self):
        return 1


class Meta(type):
    def __eq__(cls, other):
        return True

    def __hash__(cls):
        return 7


class MetaStr(str, metaclass=Meta):
    pass


class TupSub(tuple):
    pass


class DictSub(dict):
    pass


class EqTup(tuple):
    def __eq__(self, other):
        return True

    def __hash__(self):
        return 2


class BytesSub(bytes):
    pass


class EqBytes(bytes):
    def __eq__(self, other):
        return True

    def __hash__(self):
        return 3


class MetaBytes(bytes, metaclass=Meta):
    pass


HOSTILE_STR = (StrSub('en'), EqStr('en'), MetaStr('en'))
HOSTILE_BYTES = (BytesSub(b'ab'), EqBytes(b'ab'), MetaBytes(b'ab'))




def err(fn, *args):
    try:
        fn(*args)
    except ValueError as e:
        return str(e)
    return None


def fe(fn, code):
    return '%s%s:%s' % (PFX, fn, code)


@pytest.fixture(autouse=True)
def _env_guard():
    """Fail a test that leaves the module state, sys.modules or the import hook changed."""
    before_mod = (m.CLAIMS, m.MAX_DN, m.MAX_VALUE, m._HEXVAL['a'], len(m._HEXVAL))
    before_imp = builtins.__import__
    before_path = list(sys.path)
    yield
    assert builtins.__import__ == before_imp
    assert sys.path == before_path
    assert (m.CLAIMS, m.MAX_DN, m.MAX_VALUE, m._HEXVAL['a'], len(m._HEXVAL)) == before_mod




@pytest.fixture(autouse=True)
def _per_test_time_limit(request):
    """A mutant that loops forever or crawls must fail the suite, not hang it: raise in the test after the wall-time budget."""
    limit = 25 if 'slow' in request.node.name else 5

    def _h(signum, frame):
        raise AssertionError('test exceeded %d s' % limit)
    old = signal.signal(signal.SIGALRM, _h)
    signal.setitimer(signal.ITIMER_REAL, limit)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


# ---------------------------------------------------------------- independent oracle: the section 3 ABNF as one regular expression over code points
_UTFMB = '\u0080-\ud7ff\ue000-\U0010ffff'
_LEAD = '[\\x01-\\x1f\\x21\\x24-\\x2a\\x2d-\\x3a\\x3d\\x3f-\\x5b\\x5d-\\x7f' + _UTFMB + ']'
_TRAIL = '[\\x01-\\x1f\\x21\\x23-\\x2a\\x2d-\\x3a\\x3d\\x3f-\\x5b\\x5d-\\x7f' + _UTFMB + ']'
_STR1 = '[\\x01-\\x21\\x23-\\x2a\\x2d-\\x3a\\x3d\\x3f-\\x5b\\x5d-\\x7f' + _UTFMB + ']'
_PAIR = '\\\\(?:[\\\\"+,;<> #=]|[0-9A-Fa-f]{2})'
_STRING = '(?:(?:' + _LEAD + '|' + _PAIR + ')(?:(?:' + _STR1 + '|' + _PAIR + ')*(?:' + _TRAIL + '|' + _PAIR + '))?)?'
_HEXSTRING = '#(?:[0-9A-Fa-f]{2})+'
_DESCR = '[A-Za-z][A-Za-z0-9-]*'
_NUM = '(?:0|[1-9][0-9]*)'
_NUMOID = _NUM + '(?:\\.' + _NUM + ')+'
_TYPE = '(?:' + _DESCR + '|' + _NUMOID + ')'
_AVA = _TYPE + '=(?:' + _HEXSTRING + '|' + _STRING + ')'
_RDN = _AVA + '(?:\\+' + _AVA + ')*'
DN_RE = re.compile('(?:' + _RDN + '(?:,' + _RDN + ')*)?', re.ASCII | re.DOTALL)
TYPE_RE = re.compile(_TYPE, re.ASCII)
SEG_RE = re.compile('((?:\\\\.|[^\\\\,+])*)([,+]|$)', re.DOTALL)
AVA_RE = re.compile('(' + _TYPE + ')=(' + _HEXSTRING + '|' + _STRING + ')', re.ASCII | re.DOTALL)
TOK_RE = re.compile('\\\\([\\\\"+,;<> #=]|[0-9A-Fa-f]{2})|(.)', re.DOTALL)


def o_dn(t):
    return len(t) <= 1024 and DN_RE.fullmatch(t) is not None


def o_type(t):
    return len(t) <= 1024 and TYPE_RE.fullmatch(t) is not None


def o_value(vt):
    if vt.startswith('#'):
        return ('hex', bytes.fromhex(vt[1:]))
    out = b''
    for mt in TOK_RE.finditer(vt):
        if mt.group(1) is not None:
            g = mt.group(1)
            out += bytes.fromhex(g) if len(g) == 2 and g not in ('\\\\',) and all(c in '0123456789abcdefABCDEF' for c in g) else g.encode('utf-8')
        else:
            out += mt.group(2).encode('utf-8')
    return ('string', out)


def o_parse(t):
    """Segment by regex, then the AVA regex; None when the text is not a DN."""
    if not o_dn(t):
        return None
    if t == '':
        return ()
    rdns = []
    cur = []
    pos = 0
    while True:
        seg = SEG_RE.match(t, pos)
        mt = AVA_RE.fullmatch(seg.group(1))
        typ, val = mt.group(1), mt.group(2)
        kind, octets = o_value(val)
        cur.append((typ, kind, octets))
        pos = seg.end()
        if seg.group(2) != '+':
            rdns.append(tuple(cur))
            cur = []
        if seg.group(2) == '':
            return tuple(rdns)


_ESC = {'"': '\\"', '+': '\\+', ',': '\\,', ';': '\\;', '<': '\\<', '>': '\\>', '\\': '\\\\', '\x00': '\\00'}


def o_escape(s):
    chars = [_ESC.get(c, c) for c in s]
    if s and s[0] in ' #':
        chars[0] = '\\' + s[0]
    if s and s[-1] == ' ':
        chars[-1] = '\\ '
    return ''.join(chars)


def o_format(rdns):
    return ','.join('+'.join(t + '=' + ('#' + v.hex().upper() if k == 'hex' else o_escape(v.decode('utf-8'))) for t, k, v in rdn) for rdn in rdns)


def exact(a, b):
    assert type(a) is type(b), (a, b)
    if type(b) is tuple:
        assert len(a) == len(b), (a, b)
        for x, y in zip(a, b):
            exact(x, y)
    else:
        assert a == b, (a, b)


def _words(alphabet, depth):
    for n in range(1, depth + 1):
        for t in itertools.product(alphabet, repeat=n):
            yield ''.join(t)


# ---------------------------------------------------------------- RFC examples and explicit tables
RFC_EXAMPLES = [
    ('UID=jsmith,DC=example,DC=net', (( ('UID', 'string', b'jsmith'),), (('DC', 'string', b'example'),), (('DC', 'string', b'net'),))),
    ('OU=Sales+CN=J.  Smith,DC=example,DC=net', ((('OU', 'string', b'Sales'), ('CN', 'string', b'J.  Smith')), (('DC', 'string', b'example'),), (('DC', 'string', b'net'),))),
    ('CN=James \\"Jim\\" Smith\\, III,DC=example,DC=net', ((('CN', 'string', b'James "Jim" Smith, III'),), (('DC', 'string', b'example'),), (('DC', 'string', b'net'),))),
    ('CN=Before\\0dAfter,DC=example,DC=net', ((('CN', 'string', b'Before\rAfter'),), (('DC', 'string', b'example'),), (('DC', 'string', b'net'),))),
    ('1.3.6.1.4.1.1466.0=#04024869', ((('1.3.6.1.4.1.1466.0', 'hex', b'\x04\x02Hi'),),)),
    ('CN=Lu\\C4\\8Di\\C4\\87', ((('CN', 'string', 'Lu\u010di\u0107'.encode('utf-8')),),)),
]

DN_ACCEPT = ['', 'a=', 'a=b', 'a=b,c=d', 'a=b+c=d', 'a=b+c=d,e=f', 'a=#00', 'a=#0aFf', 'a=\\ ', 'a=\\#', 'a=\\ b\\ ', 'a=b c', 'a=b#c', 'a=b\\ ', 'a=x=y', 'a=\\=', 'a=\\\\', 'a=\\"', 'a=\\+', 'a=\\,', 'a=\\;', 'a=\\<', 'a=\\>', 'a=\\00', 'a=\\Ff', 'a=\u00e9', 'a=\U0010ffff', 'a=\ue000', 'a=\ud7ff', 'A-1=x', 'a1-b=x', '1.2=#00', '0.0=#00', '1.2.3=x', '1.20.3=x', 'a=\x01', 'a=\x1f', 'a=\x7f', 'a=!', 'a=a#', 'a=a b', 'a=\\20', 'a=\\23', 'a=\\#00', 'a=b,a=b,a=b', 'a=\\5c', 'a=\u0080']
DN_REFUSE = [' ', ',', '+', '=', 'a', 'a=b,', ',a=b', 'a=b+', '+a=b', 'a=b,,c=d', 'a=b++c=d', 'a=b+,c=d', 'a=b,+c=d', ' a=b', 'a =b', 'a= b', 'a=b ', 'a=b  ', 'a=b ,c=d', 'a= ', 'a=#', 'a=#0', 'a=#000', 'a=#0g', 'a=#g0', 'a=# 00', 'a=#00 ', 'a=##00', 'a=\\', 'a=b\\', 'a=\\0', 'a=\\g', 'a=\\0g', 'a=\\g0', 'a=\\:', 'a=\\a', 'a="b"', 'a=b"', 'a="', 'a=b"c', 'a=b+c', 'a=<', 'a=>', 'a=;', 'a=b;c', 'a=b<c', 'a=b>c', 'a=\x00', 'a=b\x00c', 'a=\ud800', 'a=b\udfffc', '=b', 'a=b,=c', 'a=b+=', '#=b', '1=x', '1.=x', '.1=x', '1..2=x', '01.2=x', '1.02=x', '1.2.=x', 'a_b=x', 'a b=x', '-a=x', '1a=x', 'a.b=x', 'a:b=x', 'a=#00,', '\\=b', 'a\\=b', 'a=b\x00', '\na=b', 'a=\\\n', 'a=b,\na=c', '\u00e9=b', 'a\u0131=b', '\uff21=b', 'a=\\\uff21\uff21', '\u212a=x', 'a=\\\u00e9', 'a=\\ \\', 'a=\\#\\']


def test_rfc_4514_section_4_examples_parse_and_the_section_2_conversion_reproduces_them():
    assert len(RFC_EXAMPLES) == 6
    for text, want in RFC_EXAMPLES:
        assert m.dn_ok(text) is True, text
        exact(m.parse_dn(text), want)
        assert o_parse(text) == want
    assert m.format_dn(RFC_EXAMPLES[0][1]) == RFC_EXAMPLES[0][0]
    assert m.format_dn(RFC_EXAMPLES[1][1]) == RFC_EXAMPLES[1][0]
    assert m.format_dn(RFC_EXAMPLES[4][1]) == RFC_EXAMPLES[4][0]
    assert m.format_dn(RFC_EXAMPLES[3][1]) == 'CN=Before\rAfter,DC=example,DC=net'
    assert m.format_dn(RFC_EXAMPLES[2][1]) == 'CN=James \\"Jim\\" Smith\\, III,DC=example,DC=net'
    assert m.format_dn(RFC_EXAMPLES[5][1]) == 'CN=Lu\u010di\u0107'


def test_explicit_accept_and_refuse_tables_for_dn_ok():
    assert len(DN_ACCEPT) == 47 and len(DN_REFUSE) == 83 and len(set(DN_ACCEPT)) == 47 and len(set(DN_REFUSE)) == 83
    for t in DN_ACCEPT:
        assert m.dn_ok(t) is True, repr(t)
        assert o_dn(t) is True, repr(t)
    for t in DN_REFUSE:
        assert m.dn_ok(t) is False, repr(t)
        assert o_dn(t) is False, repr(t)
        assert err(m.parse_dn, t) == fe('parse_dn', 'bad_value:text.syntax'), repr(t)


def test_every_ascii_character_as_lead_middle_trail_and_only_character_of_a_value_matches_the_oracle():
    n = 0
    samples = [chr(c) for c in range(128)] + ['\u0080', '\u07ff', '\u0800', '\ud7ff', '\ud800', '\udbff', '\udc00', '\udfff', '\ue000', '\uffff', '\U00010000', '\U0010ffff']
    for ch in samples:
        for text in ('a=' + ch, 'a=x' + ch, 'a=' + ch + 'x', 'a=x' + ch + 'y', 'a=x' + ch + 'y' + ch + 'z', 'a=' + ch + ch, 'a=' + ch + 'x ', 'a=\\ ' + ch):
            assert m.dn_ok(text) is o_dn(text), repr(text)
            n += 1
    assert n == len(samples) * 8 and len(samples) == 140
    expect_lead = {'\x00': False, ' ': False, '"': False, '#': False, '+': False, ',': False, ';': False, '<': False, '>': False, '\\': False}
    for ch, ok in expect_lead.items():
        assert m.dn_ok('a=' + ch) is ok, repr(ch)
    assert m.dn_ok('a=x ') is False and m.dn_ok('a=x#') is True and m.dn_ok('a=x y') is True and m.dn_ok('a=x#y') is True
    assert m.dn_ok('a= x') is False and m.dn_ok('a=#x') is False and m.dn_ok('a=#') is False
    assert m.dn_ok('a=\\ ') is True and m.dn_ok('a=\\ x') is True and m.dn_ok('a=x\\ ') is True


def test_first_and_last_character_of_every_range_in_the_grammar_classes():
    for lo, hi in ((0x01, 0x1f), (0x24, 0x2a), (0x2d, 0x3a), (0x3f, 0x5b), (0x5d, 0x7f)):
        for c in (lo, hi):
            ch = chr(c)
            assert m.dn_ok('a=' + ch) is True and m.dn_ok('a=x' + ch) is True and m.dn_ok('a=x' + ch + 'y') is True, hex(c)
        assert m.dn_ok('a=' + chr(lo - 1)) is o_dn('a=' + chr(lo - 1))
        assert m.dn_ok('a=' + chr(hi + 1)) is o_dn('a=' + chr(hi + 1))
    for c in (0x21, 0x3d):
        assert m.dn_ok('a=' + chr(c)) is True
    for c in (0x20, 0x22, 0x23, 0x2b, 0x2c, 0x3b, 0x3c, 0x3e, 0x5c, 0x00):
        assert m.dn_ok('a=' + chr(c)) is False, hex(c)
    for c in (0x23, 0x20):
        assert m.dn_ok('a=x' + chr(c) + 'y') is True and m.dn_ok('a=x' + chr(c)) is (c == 0x23)
    assert m.dn_ok('a=\u0080') is True and m.dn_ok('a=\U0010ffff') is True and m.dn_ok('a=\ud7ff') is True and m.dn_ok('a=\ue000') is True
    assert m.dn_ok('a=\ud800') is False and m.dn_ok('a=\udfff') is False


# ---------------------------------------------------------------- exhaustive differential: dn_ok and parse_dn against the oracle
def test_exhaustive_words_dn_ok_parse_dn_and_format_round_trip_match_the_oracle_slow():
    alphabet = ['a', '=', ',', '+', '\\', ' ', '#', '0', 'F', 'g', '"', '\u00e9']
    n_ok = 0
    n_all = 0
    for w in itertools.chain([''], _words(alphabet, 4)):
        n_all += 1
        want = o_parse(w)
        assert m.dn_ok(w) is (want is not None), repr(w)
        if want is None:
            assert err(m.parse_dn, w) == fe('parse_dn', 'bad_value:text.syntax'), repr(w)
        else:
            n_ok += 1
            got = m.parse_dn(w)
            exact(got, want)
            back = m.format_dn(got)
            assert type(back) is str
            assert o_parse(back) == want, repr(w)
            assert back == o_format(want), repr(w)
            assert m.parse_dn(back) == want
    assert n_all == 1 + 12 + 144 + 1728 + 20736
    assert n_ok == 301, n_ok


def test_exhaustive_attribute_type_words_match_the_oracle():
    alphabet = ['a', 'Z', '0', '1', '9', '-', '.', '_', ' ', '\u00e9']
    n_ok = 0
    n_all = 0
    for w in itertools.chain([''], _words(alphabet, 5)):
        n_all += 1
        want = o_type(w)
        assert m.attribute_type_ok(w) is want, repr(w)
        n_ok += 1 if want else 0
    assert n_all == 1 + 10 + 100 + 1000 + 10000 + 100000
    assert n_ok == 3326, n_ok
    for t, ok in (('cn', True), ('A', True), ('a-', True), ('a-b-9', True), ('0.0', True), ('1.2', True), ('10.20.30', True), ('0', False), ('1', False), ('1.', False), ('.1', False), ('1..2', False), ('00.1', False), ('1.01', False), ('', False), ('-a', False), ('9a', False), ('a b', False), ('a_b', False), ('a.b', False), ('\u00e9', False), ('a\u00e9', False), ('1.2.3.4.5.6.7.8.9.0', True), ('0.0.0', True), ('0.1.2', True), ('a\n', False)):
        assert m.attribute_type_ok(t) is ok, t


def test_random_structured_dns_round_trip_and_match_the_oracle():
    rng = random.Random(4514)
    pool = ['a', 'b', ' ', '#', '"', '+', ',', ';', '<', '>', '\\', '=', '\x00', '\x01', '\n', '\r', '\u00e9', '\u0800', '\U00010000', '\U0010ffff', '\ue000', 'x', '1']
    types = ['cn', 'DC', 'ou', 'A-1', 'x9']
    n = 0
    for _ in range(400):
        rdns = []
        for _r in range(rng.randrange(0, 4)):
            avas = []
            for _a in range(rng.randrange(1, 3)):
                if rng.randrange(4) == 0:
                    avas.append(('1.2.%d' % rng.randrange(0, 50), 'hex', bytes(rng.randrange(256) for _b in range(rng.randrange(1, 5)))))
                else:
                    avas.append((rng.choice(types), 'string', ''.join(rng.choice(pool) for _c in range(rng.randrange(0, 6))).encode('utf-8')))
            rdns.append(tuple(avas))
        rdns = tuple(rdns)
        text = m.format_dn(rdns)
        assert text == o_format(rdns)
        assert o_dn(text) is True and m.dn_ok(text) is True
        exact(m.parse_dn(text), rdns)
        exact(o_parse(text), rdns)
        n += 1
    assert n == 400


# ---------------------------------------------------------------- escaping rules (RFC 4514 section 2.4)
ESC_TABLE = [
    ('', 'a='), (' ', 'a=\\ '), ('  ', 'a=\\ \\ '), ('#', 'a=\\#'), ('##', 'a=\\##'), ('x#', 'a=x#'), ('x ', 'a=x\\ '), (' x', 'a=\\ x'), ('#x', 'a=\\#x'), (' x ', 'a=\\ x\\ '),
    ('x y', 'a=x y'), ('"', 'a=\\"'), ('+', 'a=\\+'), (',', 'a=\\,'), (';', 'a=\\;'), ('<', 'a=\\<'), ('>', 'a=\\>'), ('\\', 'a=\\\\'),
    ('\x00', 'a=\\00'), ('x\x00y', 'a=x\\00y'), ('=', 'a=='), ('a=b', 'a=a=b'), ('\n', 'a=\n'), ('\x01', 'a=\x01'), ('\x7f', 'a=\x7f'),
    ('\u00e9', 'a=\u00e9'), ('\U0010ffff', 'a=\U0010ffff'), (' #', 'a=\\ #'), ('# ', 'a=\\#\\ '), ('a\\,b', 'a=a\\\\\\,b'), ('x  ', 'a=x \\ '),
]


def test_format_escaping_table_and_every_ascii_character_alone_leading_and_trailing():
    assert len(ESC_TABLE) == 31
    for raw, want in ESC_TABLE:
        got = m.format_dn((( ('a', 'string', raw.encode('utf-8')),),))
        assert got == want, (raw, got)
        assert o_format(((('a', 'string', raw.encode('utf-8')),),)) == want
        exact(m.parse_dn(want), ((('a', 'string', raw.encode('utf-8')),),))
    n = 0
    for c in range(128):
        ch = chr(c)
        for raw in (ch, ch + 'x', 'x' + ch, 'x' + ch + 'y', ch + ch):
            rdns = ((('a', 'string', raw.encode('utf-8')),),)
            text = m.format_dn(rdns)
            assert text == o_format(rdns), repr(raw)
            exact(m.parse_dn(text), rdns)
            n += 1
    assert n == 640


def test_pair_forms_hex_pairs_both_cases_and_the_special_pairs_decode_to_the_right_octets():
    cases = [('\\5C', b'\\'), ('\\5c', b'\\'), ('\\20', b' '), ('\\23', b'#'), ('\\00', b'\x00'), ('\\FF', b'\xff'), ('\\fF', b'\xff'), ('\\Ff', b'\xff'), ('\\c4\\8D', b'\xc4\x8d'), ('\\\\', b'\\'), ('\\ ', b' '), ('\\#', b'#'), ('\\=', b'='), ('\\"', b'"'), ('\\+', b'+'), ('\\,', b','), ('\\;', b';'), ('\\<', b'<'), ('\\>', b'>'), ('\\41', b'A'), ('\\3d', b'=')]
    assert len(cases) == 21
    for pair, octets in cases:
        for text, want in (('a=' + pair, octets), ('a=x' + pair + 'y', b'x' + octets + b'y'), ('a=' + pair + 'y', octets + b'y'), ('a=x' + pair, b'x' + octets)):
            got = m.parse_dn(text)
            exact(got, ((('a', 'string', want),),))
            assert o_parse(text) == got
    # a hex pair needs no UTF-8 validity at parse time (section 3 pairs are octets), so lone continuation octets are accepted
    assert m.parse_dn('a=\\80')[0][0][2] == b'\x80'
    assert m.parse_dn('a=\\ff\\fe')[0][0][2] == b'\xff\xfe'
    assert m.parse_dn('a=\\C4\\8D\\C4\\87')[0][0][2].decode('utf-8') == '\u010d\u0107'
    # a hex pair for an octet that would be a trailing space is still a value, the parse keeps it
    assert m.parse_dn('a=x\\20')[0][0][2] == b'x '
    assert err(m.parse_dn, 'a=x ') == fe('parse_dn', 'bad_value:text.syntax')


def test_hexstring_forms():
    assert m.parse_dn('a=#00') == ((('a', 'hex', b'\x00'),),)
    assert m.parse_dn('a=#0aFf') == ((('a', 'hex', b'\x0a\xff'),),)
    assert m.parse_dn('a=#' + '01' * 5) == ((('a', 'hex', b'\x01' * 5),),)
    assert m.parse_dn('1.2=#04024869')[0][0][2] == b'\x04\x02Hi'
    assert m.format_dn(((('a', 'hex', b'\x0a\xff'),),)) == 'a=#0AFF'
    assert m.format_dn(((('a', 'hex', b'\x00'),),)) == 'a=#00'
    assert m.format_dn(((('1.2', 'hex', b'\x00'),),)) == '1.2=#00'
    for bad in ('a=#', 'a=#0', 'a=#000', 'a=#0G', 'a=# 0', 'a=#00 ', 'a=#\\00', 'a=##00', 'a=#00#'):
        assert err(m.parse_dn, bad) == fe('parse_dn', 'bad_value:text.syntax'), bad


class MetaTup(tuple, metaclass=Meta):
    pass


HOSTILE_TUP = (TupSub(), EqTup(), MetaTup())
NOT_STR = (None, 1, 0, True, False, 1.5, b'a=b', bytearray(b'a=b'), ['a=b'], ('a=b',), {'a': 'b'}, {'a=b'}, object(), len)
NOT_TUPLE = (None, 1, True, 'a=b', b'', bytearray(), [], {}, set(), 1.5, object())
NOT_BYTES = (None, 1, True, 'a', bytearray(b'a'), [b'a'], (b'a',), 1.5, object(), memoryview(b'a'))


def test_text_argument_type_cap_and_both_bad_order_for_the_three_text_functions():
    for name in ('dn_ok', 'attribute_type_ok', 'parse_dn'):
        fn = getattr(m, name)
        for bad in NOT_STR + HOSTILE_STR:
            assert err(fn, bad) == fe(name, 'bad_type:text'), (name, bad)
        assert err(fn, 'a' * 1025) == fe(name, 'bad_value:text.length')
        assert err(fn, '\u00e9' * 1025) == fe(name, 'bad_value:text.length')
        assert err(fn, '=' * 1025) == fe(name, 'bad_value:text.length')
        assert err(fn, 'a' * 1024) != fe(name, 'bad_value:text.length')
    assert m.attribute_type_ok('a' * 1024) is True and m.attribute_type_ok('a' * 1023) is True
    assert m.dn_ok('a=' + 'b' * 1022) is True and m.dn_ok('a=' + 'b' * 1021) is True
    assert err(m.dn_ok, 'a=' + 'b' * 1023) == fe('dn_ok', 'bad_value:text.length')
    assert err(m.parse_dn, 'a=' + 'b' * 1023) == fe('parse_dn', 'bad_value:text.length')
    assert len(m.parse_dn('a=' + 'b' * 1022)[0][0][2]) == 1022
    assert m.parse_dn('') == ()
    assert type(m.parse_dn('')) is tuple


def test_hostile_text_never_runs_its_overrides_and_returns_no_value():
    for name in ('dn_ok', 'attribute_type_ok', 'parse_dn'):
        for bad in HOSTILE_STR:
            assert err(getattr(m, name), bad) == fe(name, 'bad_type:text')
    for bad in HOSTILE_STR:
        assert err(m.format_dn, bad) == fe('format_dn', 'bad_type:rdns')


def good_ava():
    return ('a', 'string', b'b')


def test_format_dn_error_codes_in_check_order_one_bad_input_each():
    fd = m.format_dn
    for bad in NOT_TUPLE + HOSTILE_STR:
        assert err(fd, bad) == fe('format_dn', 'bad_type:rdns'), repr(bad)
    for bad in NOT_TUPLE:
        assert err(fd, (bad,)) == fe('format_dn', 'bad_type:rdns.item'), repr(bad)
    for bad in HOSTILE_TUP:
        assert err(fd, bad) == fe('format_dn', 'bad_type:rdns'), repr(bad)
        assert err(fd, (bad,)) == fe('format_dn', 'bad_type:rdns.item'), repr(bad)
        assert err(fd, ((bad,),)) == fe('format_dn', 'bad_type:rdns.ava'), repr(bad)
    assert err(fd, ((),)) == fe('format_dn', 'bad_value:rdns.item')
    for bad in NOT_TUPLE:
        assert err(fd, ((bad,),)) == fe('format_dn', 'bad_type:rdns.ava'), repr(bad)
    for bad in ((), ('a',), ('a', 'string'), ('a', 'string', b'', b''), ('a', 'string', b'', 1, 2)):
        assert err(fd, ((bad,),)) == fe('format_dn', 'bad_value:rdns.ava'), repr(bad)
    for bad in NOT_STR + HOSTILE_STR:
        assert err(fd, (((bad, 'string', b'x'),),)) == fe('format_dn', 'bad_type:rdns.type'), repr(bad)
    for bad in ('', 'a b', '-a', '9a', '1', '1.', '1..2', '01.2', 'a_b', '\u00e9', ' a', 'a ', 'a\n', 'a=b', 'a,b', '#', '1.2.', '.1'):
        assert err(fd, (((bad, 'string', b'x'),),)) == fe('format_dn', 'bad_value:rdns.type'), repr(bad)
    assert err(fd, ((('a' * 1025, 'string', b'x'),),)) == fe('format_dn', 'bad_value:rdns.type.length')
    assert err(fd, ((('\u00e9' * 1025, 'string', b'x'),),)) == fe('format_dn', 'bad_value:rdns.type.length')
    for bad in NOT_STR + HOSTILE_STR:
        assert err(fd, ((('a', bad, b'x'),),)) == fe('format_dn', 'bad_type:rdns.kind'), repr(bad)
    for bad in ('', 'String', 'HEX', 'str', 'bytes', 'string ', ' hex', 'strin', 'hexx', 'h', 's'):
        assert err(fd, ((('a', bad, b'x'),),)) == fe('format_dn', 'bad_value:rdns.kind'), repr(bad)
    for bad in NOT_BYTES + HOSTILE_BYTES:
        for kind in ('string', 'hex'):
            assert err(fd, ((('a', kind, bad),),)) == fe('format_dn', 'bad_type:rdns.value'), (kind, bad)
    assert err(fd, ((('a', 'string', b'\xff'),),)) == fe('format_dn', 'bad_value:rdns.value')
    assert err(fd, ((('a', 'string', b'\xc4'),),)) == fe('format_dn', 'bad_value:rdns.value')
    assert err(fd, ((('a', 'string', b'\xed\xa0\x80'),),)) == fe('format_dn', 'bad_value:rdns.value')
    assert err(fd, ((('a', 'string', b'\xc0\x80'),),)) == fe('format_dn', 'bad_value:rdns.value')
    assert err(fd, ((('a', 'string', b'\xf4\x90\x80\x80'),),)) == fe('format_dn', 'bad_value:rdns.value')
    assert err(fd, ((('a', 'hex', b''),),)) == fe('format_dn', 'bad_value:rdns.value')
    assert fd(((('a', 'string', b''),),)) == 'a='
    assert err(fd, ((('1.2', 'string', b'x'),),)) == fe('format_dn', 'bad_value:rdns.kind')
    assert err(fd, ((('0.0', 'string', b''),),)) == fe('format_dn', 'bad_value:rdns.kind')
    assert fd(((('1.2', 'hex', b'x'),),)) == '1.2=#78'
    assert fd(((('a-1', 'hex', b'x'),),)) == 'a-1=#78'


def test_format_dn_both_bad_refusal_order_across_slots_and_walk_order():
    fd = m.format_dn
    c = lambda code: fe('format_dn', code)
    big = ('x',) * 1025
    assert err(fd, big) == c('bad_value:rdns.length')
    assert err(fd, (None,) * 1025) == c('bad_value:rdns.length')
    assert err(fd, ((good_ava(),) * 1025, None)) == c('bad_value:rdns.item.length')
    assert err(fd, ((None,) * 1025,)) == c('bad_value:rdns.item.length')
    assert err(fd, (((),) * 3)) == c('bad_value:rdns.item')
    assert err(fd, ((), None)) == c('bad_value:rdns.item')
    assert err(fd, (None, ())) == c('bad_type:rdns.item')
    assert err(fd, ((good_ava(),), None)) == c('bad_type:rdns.item')
    assert err(fd, ((good_ava(), None),)) == c('bad_type:rdns.ava')
    assert err(fd, ((good_ava(), ('a',)), None)) == c('bad_value:rdns.ava')
    assert err(fd, (((1, 'x'),),)) == c('bad_value:rdns.ava')
    assert err(fd, (((1, 'x', 2),),)) == c('bad_type:rdns.type')
    assert err(fd, ((('a' * 1025 + ' ', 'x', 2),),)) == c('bad_value:rdns.type.length')
    assert err(fd, ((('a b', 'x', 2),),)) == c('bad_value:rdns.type')
    assert err(fd, ((('a', 1, 2),),)) == c('bad_type:rdns.kind')
    assert err(fd, ((('a', 'x', 2),),)) == c('bad_value:rdns.kind')
    assert err(fd, ((('1.2', 'x', 2),),)) == c('bad_value:rdns.kind')
    assert err(fd, ((('1.2', 'string', 2),),)) == c('bad_value:rdns.kind')
    assert err(fd, ((('1.2', 'hex', 2),),)) == c('bad_type:rdns.value')
    assert err(fd, ((('a', 'hex', 'x' * 5000),),)) == c('bad_type:rdns.value')
    assert err(fd, ((('a', 'hex', b'x' * 4097),),)) == c('bad_value:rdns.value.length')
    assert err(fd, ((('a', 'string', b'\xff' * 4097),),)) == c('bad_value:rdns.value.length')
    assert err(fd, ((('a', 'hex', b'x' * 4096),),)) == c('bad_value:dn.length')
    assert err(fd, ((('a', 'string', b'\xff' * 4096),),)) == c('bad_value:rdns.value')
    assert err(fd, ((('a', 'string', b'\xff'), ('b', 'hex', 5)),)) == c('bad_value:rdns.value')
    assert err(fd, ((('a', 'string', b'x'),) * 2000,) * 1 + ((),)) == c('bad_value:rdns.item.length')
    assert err(fd, (((('a', 'string', b'x'),) * 1025),)) == c('bad_value:rdns.item.length')
    assert err(fd, (((('a', 'string', b'x'),) * 1024),)) == c('bad_value:dn.length')


def test_format_dn_caps_with_format_then_parse_round_trips_at_lo_minus_1_lo_hi_hi_plus_1():
    fd = m.format_dn
    c = lambda code: fe('format_dn', code)
    for t in (1021, 1022, 1023):
        text = fd(((('a' * t, 'string', b''),),))
        assert len(text) == t + 1 and text == 'a' * t + '='
        assert m.parse_dn(text) == ((('a' * t, 'string', b''),),)
    assert err(fd, ((('a' * 1024, 'string', b''),),)) == c('bad_value:dn.length')
    assert err(fd, ((('a' * 1025, 'string', b''),),)) == c('bad_value:rdns.type.length')
    assert err(m.parse_dn, 'a' * 1024 + '=') == fe('parse_dn', 'bad_value:text.length')
    for n in (1021, 1022, 1023, 1024):
        rdns = ((('a', 'string', b'\xf4\x8f\xbf\xbf' * n),),)
        if n <= 1022:
            text = fd(rdns)
            assert len(text) == n + 2 and text == 'a=' + '\U0010ffff' * n
            exact(m.parse_dn(text), rdns)
        else:
            assert err(fd, rdns) == c('bad_value:dn.length')
    assert len(m.parse_dn('a=' + '\U0010ffff' * 1022)[0][0][2]) == 4088
    for n in (340, 341, 342):
        rdns = ((('a', 'string', b''),),) * n
        if n <= 341:
            text = fd(rdns)
            assert len(text) == 3 * n - 1
            assert m.parse_dn(text) == rdns
        else:
            assert err(fd, rdns) == c('bad_value:dn.length')
    for n in (340, 341, 342):
        rdns = ((('a', 'string', b''),) * n,)
        if n <= 341:
            text = fd(rdns)
            assert len(text) == 3 * n - 1
            assert m.parse_dn(text) == rdns
        else:
            assert err(fd, rdns) == c('bad_value:dn.length')
    assert err(fd, ((('a', 'string', b''),),) * 1024) == c('bad_value:dn.length')
    assert err(fd, ((('a', 'string', b''),),) * 1025) == c('bad_value:rdns.length')
    assert err(fd, (((('a', 'string', b''),) * 1024),)) == c('bad_value:dn.length')
    # the largest value the parse side can produce still formats (or fails only on the output cap)
    big = m.parse_dn('a=' + '\\ff' * 340)
    assert len(big[0][0][2]) == 340
    assert err(m.parse_dn, 'a=' + '\\ff' * 341) == fe('parse_dn', 'bad_value:text.length')
    assert len(m.parse_dn('a=' + '\\00' * 340)[0][0][2]) == 340
    assert m.parse_dn('a=#' + '00' * 510)[0][0][2] == b'\x00' * 510
    assert len(m.format_dn(m.parse_dn('a=#' + '00' * 510))) == 1023
    assert len(m.format_dn(m.parse_dn('ab=#' + '00' * 510))) == 1024
    assert err(m.parse_dn, 'abc=#' + '00' * 510) == fe('parse_dn', 'bad_value:text.length')
    assert err(fd, ((('abc', 'hex', b'\x00' * 510),),)) == c('bad_value:dn.length')
    assert err(m.parse_dn, 'a=#' + '00' * 511) == fe('parse_dn', 'bad_value:text.length')
    assert err(fd, ((('a', 'hex', b'\x00' * 511),),)) == c('bad_value:dn.length')


def test_results_are_exact_builtin_types_and_never_aliases_of_the_input():
    r = m.parse_dn('a=b+c=d,e=f')
    assert type(r) is tuple and all(type(x) is tuple for x in r)
    assert all(type(a) is tuple and len(a) == 3 and type(a[0]) is str and type(a[1]) is str and type(a[2]) is bytes for x in r for a in x)
    assert m.dn_ok('a=b') is True and m.dn_ok('a') is False
    assert m.attribute_type_ok('a') is True and m.attribute_type_ok('') is False
    assert type(m.format_dn(r)) is str and m.format_dn(r) == 'a=b+c=d,e=f'
    assert m.format_dn(()) == ''
    inp = ((('a', 'string', b'b'),),)
    assert m.format_dn(inp) == 'a=b' and inp == ((('a', 'string', b'b'),),)
    assert m.parse_dn('A=b')[0][0][0] == 'A' and m.parse_dn('a=B')[0][0][2] == b'B'


def test_constants_functions_and_claims():
    assert m.CLAIMS is False
    assert m.MAX_DN == 1024 and type(m.MAX_DN) is int
    assert m.MAX_VALUE == 4096 and type(m.MAX_VALUE) is int
    assert type(m.SCOPE) is str and type(m.NOT_CLAIMED) is tuple and type(m.ADJACENT) is tuple
    for name in FNS:
        assert callable(getattr(m, name))


AVA_SLOTS = [('T0', 'bad_type:rdns.type'), ('T1', 'bad_value:rdns.type.length'), ('T2', 'bad_value:rdns.type'), ('K0', 'bad_type:rdns.kind'), ('K1', 'bad_value:rdns.kind'), ('V0', 'bad_type:rdns.value'), ('V1', 'bad_value:rdns.value.length'), ('V2', 'bad_value:rdns.value')]


def _ava_for(flags):
    if 'T0' in flags:
        typ = 1
    elif 'T1' in flags and 'T2' in flags:
        typ = 'a' * 1024 + ' '
    elif 'T1' in flags:
        typ = 'a' * 1025
    elif 'T2' in flags:
        typ = 'a b'
    else:
        typ = 'a'
    kind = 1 if 'K0' in flags else ('x' if 'K1' in flags else 'string')
    if 'V0' in flags:
        value = 'x'
    elif 'V1' in flags and 'V2' in flags:
        value = b'\xff' * 4097
    elif 'V1' in flags:
        value = b'x' * 4097
    elif 'V2' in flags:
        value = b'\xff'
    else:
        value = b'x'
    return (typ, kind, value)


def test_every_subset_of_bad_ava_slots_reports_the_earliest_bad_slot_in_check_order():
    n = 0
    for mask in range(1, 256):
        flags = [AVA_SLOTS[k][0] for k in range(8) if mask >> k & 1]
        want = [code for name, code in AVA_SLOTS if name in flags][0]
        assert err(m.format_dn, ((_ava_for(flags),),)) == fe('format_dn', want), flags
        assert err(m.format_dn, ((good_ava(), _ava_for(flags)),)) == fe('format_dn', want), flags
        n += 1
    assert n == 255
    # a hex kind never takes the UTF-8 content check, an empty hex value is the only content refusal for it
    assert m.format_dn(((('a', 'hex', b'\xff'),),)) == 'a=#FF'
    assert err(m.format_dn, ((('a', 'hex', b'\xff' * 4097),),)) == fe('format_dn', 'bad_value:rdns.value.length')


def test_numericoid_with_string_kind_is_checked_after_kind_and_before_every_value_check():
    c = fe('format_dn', 'bad_value:rdns.kind')
    for val in (b'x', 'x', b'\xff', b'x' * 4097, b'\xff' * 4097, None, 5):
        assert err(m.format_dn, ((('1.2', 'string', val),),)) == c, val
    for bad_kind in (1, None, 'x', ''):
        want = 'bad_type:rdns.kind' if type(bad_kind) is not str else 'bad_value:rdns.kind'
        assert err(m.format_dn, ((('1.2', bad_kind, b'x'),),)) == fe('format_dn', want), bad_kind
    assert err(m.format_dn, ((('1.2', 'hex', 'x'),),)) == fe('format_dn', 'bad_type:rdns.value')
    assert err(m.format_dn, ((('1.2', 'hex', b'x' * 4097),),)) == fe('format_dn', 'bad_value:rdns.value.length')
    assert err(m.format_dn, ((('1.2', 'hex', b''),),)) == fe('format_dn', 'bad_value:rdns.value')
    assert err(m.format_dn, ((('a1', 'string', b'x'), ('1.2', 'string', b'x')),)) == c


# ---------------------------------------------------------------- registry guard
UTIL_IMPORT = ('importlib.util', ('find_spec',), 0)
REG_IMPORT = (REG, ('make_fail',), 0)


def _guard_gen(world, src=None):
    """Execute the module source under a recording import hook for one guard world.
    Returns (import log, find_spec calls, namespace or None, raised exception or None)."""
    import types
    log = []
    calls = []
    real = builtins.__import__
    util = types.ModuleType('importlib.util')

    class Spec:
        pass

    def fake_find_spec(name, *a):
        calls.append(name)
        return Spec() if world == 'spec_present' else None
    util.find_spec = fake_find_spec
    reg = types.ModuleType(REG)
    reg.make_fail = lambda name: ('MARK', name)

    def hook(name, globals=None, locals=None, fromlist=(), level=0):
        log.append((name, tuple(fromlist) if fromlist else (), level))
        if name == 'importlib.util':
            return util
        if name == REG:
            if world == 'present':
                return reg
            if world == 'other':
                raise ModuleNotFoundError('No module named other', name='other.pkg')
            if world == 'noname':
                raise ModuleNotFoundError('No module named')
            if world == 'importerror':
                raise ImportError('boom', name=REG)
            raise ModuleNotFoundError('No module named ' + REG, name=REG)
        return real(name, globals, locals, fromlist, level)
    ns = {'__name__': 'x1229', '__builtins__': dict(vars(builtins), __import__=hook)}
    try:
        exec(compile(SRC_TEXT if src is None else src, '<m1229>', 'exec'), ns)
    except BaseException as e:
        return log, calls, None, e
    return log, calls, ns, None


SRC_TEXT = open(SRC_PATH).read()


def test_guard_present_registry_is_used_and_logs_exactly_two_imports():
    log, calls, ns, e = _guard_gen('present')
    assert e is None and log == [UTIL_IMPORT, REG_IMPORT] and calls == []
    assert ns['make_fail']('n') == ('MARK', 'n')
    assert ns['CLAIMS'] is False and ns['MAX_DN'] == 1024


def test_guard_absent_registry_falls_back_with_the_literal_p235_prefix_and_no_further_import():
    log, calls, ns, e = _guard_gen('absent')
    assert e is None and log == [UTIL_IMPORT, REG_IMPORT] and calls == [REG]
    fail = ns['make_fail']('nm')
    assert callable(fail) and ns['make_fail'].__name__ == 'make_fail' and fail.__name__ == 'fail'
    with pytest.raises(ValueError) as info:
        fail('some:code')
    assert str(info.value) == 'P235:nm:some:code' and type(info.value) is ValueError
    assert log == [UTIL_IMPORT, REG_IMPORT]


def test_guard_reraises_a_missing_module_that_is_not_the_registry_without_asking_find_spec():
    log, calls, ns, e = _guard_gen('other')
    assert ns is None and type(e) is ModuleNotFoundError and e.name == 'other.pkg'
    assert log == [UTIL_IMPORT, REG_IMPORT] and calls == []
    log, calls, ns, e = _guard_gen('noname')
    assert ns is None and type(e) is ModuleNotFoundError and e.name is None
    assert log == [UTIL_IMPORT, REG_IMPORT] and calls == []


def test_guard_reraises_when_the_registry_exists_but_its_import_failed():
    log, calls, ns, e = _guard_gen('spec_present')
    assert ns is None and type(e) is ModuleNotFoundError and e.name == REG
    assert log == [UTIL_IMPORT, REG_IMPORT] and calls == [REG]


def test_guard_catches_module_not_found_only_so_other_import_errors_propagate():
    log, calls, ns, e = _guard_gen('importerror')
    assert ns is None and type(e) is ImportError and e.name == REG
    assert log == [UTIL_IMPORT, REG_IMPORT] and calls == []


def test_guard_gen_self_test_detects_a_wrong_guard():
    bad_or = SRC_TEXT.replace(" or find_spec(", " and find_spec(")
    assert bad_or != SRC_TEXT
    _, _, ns, e = _guard_gen('other', bad_or)
    assert e is None and ns is not None
    bad_cls = SRC_TEXT.replace("except ModuleNotFoundError as exc", "except ImportError as exc")
    assert bad_cls != SRC_TEXT
    _, _, ns, e = _guard_gen('spec_present', bad_cls.replace("is not None:", "is None:"))
    assert e is None
    bad_name = SRC_TEXT.replace("exc.name != '", "exc.name == '")
    assert bad_name != SRC_TEXT
    _, _, ns, e = _guard_gen('absent', bad_name)
    assert e is not None and type(e) is ModuleNotFoundError
    assert _guard_gen('absent')[3] is None



def test_the_real_registry_world_prefix_is_probed_and_pinned():
    probe = err(m.make_fail('probe_fn'), 'probe_code')
    if STUB_WORLD:
        assert probe == 'STUB:probe_fn:probe_code'
        assert PFX == 'STUB:'
    else:
        assert probe == 'P235:probe_fn:probe_code'
        assert PFX == 'P235:'
    assert err(m.dn_ok, 1) == PFX + 'dn_ok:bad_type:text'


@contextlib.contextmanager
def _record():
    """Record every import while the block runs; restore the original hook in a finally, whatever the block raises."""
    log = []
    real = builtins.__import__

    def hook(name, *a, **k):
        log.append(name)
        return real(name, *a, **k)
    _start_import(builtins, hook)
    try:
        yield log
    finally:
        _stop_import()


def test_the_recorder_restores_the_import_hook_even_when_the_block_raises():
    real = builtins.__import__
    with pytest.raises(RuntimeError):
        with _record() as log:
            exec('import hmac')
            assert log[0] == 'hmac'
            raise RuntimeError('boom')
    assert builtins.__import__ == real


def test_the_import_recorder_sees_a_function_level_import():
    log_holder = []
    real = builtins.__import__

    def hook(name, *a, **k):
        log_holder.append(name)
        return real(name, *a, **k)
    _start_import(builtins, hook)
    try:
        exec('import hmac')
    finally:
        _stop_import()
    assert log_holder[0] == 'hmac' and len(log_holder) >= 1


def _drive_all_success():
    n = 0
    for t in DN_ACCEPT:
        assert m.dn_ok(t) is True
        assert m.parse_dn(t) == o_parse(t)
        n += 1
    for t in RFC_EXAMPLES:
        assert m.format_dn(m.parse_dn(t[0])) == o_format(t[1])
        n += 1
    assert m.attribute_type_ok('cn') is True and m.attribute_type_ok('1.2') is True and m.attribute_type_ok('') is False
    assert m.dn_ok('a=\\') is False and m.dn_ok('') is True
    return n + 5


def test_success_shapes_do_no_import_through_every_entry():
    with _record() as log:
        assert _drive_all_success() == 47 + 6 + 5
        assert log == []


EXPECTED_CODES = [
    ('dn_ok', 'bad_type:text'), ('dn_ok', 'bad_value:text.length'),
    ('attribute_type_ok', 'bad_type:text'), ('attribute_type_ok', 'bad_value:text.length'),
    ('parse_dn', 'bad_type:text'), ('parse_dn', 'bad_value:text.length'), ('parse_dn', 'bad_value:text.syntax'),
    ('format_dn', 'bad_type:rdns'), ('format_dn', 'bad_value:rdns.length'),
    ('format_dn', 'bad_type:rdns.item'), ('format_dn', 'bad_value:rdns.item.length'), ('format_dn', 'bad_value:rdns.item'),
    ('format_dn', 'bad_type:rdns.ava'), ('format_dn', 'bad_value:rdns.ava'),
    ('format_dn', 'bad_type:rdns.type'), ('format_dn', 'bad_value:rdns.type.length'), ('format_dn', 'bad_value:rdns.type'),
    ('format_dn', 'bad_type:rdns.kind'), ('format_dn', 'bad_value:rdns.kind'),
    ('format_dn', 'bad_type:rdns.value'), ('format_dn', 'bad_value:rdns.value.length'), ('format_dn', 'bad_value:rdns.value'),
    ('format_dn', 'bad_value:dn.length'),
]


def _ast_fail_literals():
    codes = set()
    for node in ast.walk(ast.parse(SRC_TEXT)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'fail' and node.args:
            a = node.args[0]
            if isinstance(a, ast.Constant) and type(a.value) is str:
                codes.add(a.value)
    return codes


def test_every_refusal_code_is_driven_under_the_import_hook_and_none_imports():
    with _record() as log:
        seen = set()

        def drive(fn, *a):
            e = err(fn, *a)
            assert e is not None, (fn, a)
            seen.add(e[len(PFX):])
        for fn in (m.dn_ok, m.attribute_type_ok, m.parse_dn):
            drive(fn, None)
            drive(fn, 'a' * 1025)
        drive(m.parse_dn, 'a')
        a = ('a', 'string', b'x')
        drive(m.format_dn, 1)
        drive(m.format_dn, (a,) * 1025)
        drive(m.format_dn, (1,))
        drive(m.format_dn, ((a,) * 1025,))
        drive(m.format_dn, ((),))
        drive(m.format_dn, ((1,),))
        drive(m.format_dn, ((('a',),),))
        drive(m.format_dn, (((1, 'string', b''),),))
        drive(m.format_dn, ((('a' * 1025, 'string', b''),),))
        drive(m.format_dn, ((('a b', 'string', b''),),))
        drive(m.format_dn, ((('a', 1, b''),),))
        drive(m.format_dn, ((('a', 'x', b''),),))
        drive(m.format_dn, ((('a', 'string', 1),),))
        drive(m.format_dn, ((('a', 'string', b'x' * 4097),),))
        drive(m.format_dn, ((('a', 'string', b'\xff'),),))
        drive(m.format_dn, ((('a', 'hex', b'x' * 4096),),))
        drive(m.format_dn, ((('a', 'string', b''),) * 1025,))
        drive(m.format_dn, ((a,),) * 1025)
        assert log == []
        assert seen == set('%s:%s' % (fn, code) for fn, code in EXPECTED_CODES)
        assert len(EXPECTED_CODES) == 23 and len(set(EXPECTED_CODES)) == 23
        assert _ast_fail_literals() == LITERAL_CODES
        assert _ast_fail_expressions() == EXPR_CODES


LITERAL_CODES = set(['bad_type:rdns', 'bad_type:rdns.ava', 'bad_type:rdns.item', 'bad_type:rdns.kind', 'bad_type:rdns.type', 'bad_type:rdns.value', 'bad_type:text', 'bad_value:dn.length', 'bad_value:rdns.ava', 'bad_value:rdns.item', 'bad_value:rdns.item.length', 'bad_value:rdns.kind', 'bad_value:rdns.length', 'bad_value:rdns.type', 'bad_value:rdns.type.length', 'bad_value:rdns.value', 'bad_value:rdns.value.length', 'bad_value:text.length', 'bad_value:text.syntax'])
EXPR_CODES = []


def _ast_fail_expressions():
    out = []
    for node in ast.walk(ast.parse(SRC_TEXT)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'fail' and node.args and not isinstance(node.args[0], ast.Constant):
            out.append(ast.unparse(node.args[0]))
    return sorted(out)


# ---------------------------------------------------------------- scrub, lookalike and docstring pins
def _tree():
    return ast.parse(SRC_TEXT)


def test_module_source_is_ascii_and_has_no_banned_text_calls():
    SRC_TEXT.encode('ascii')
    banned_attr = ('isdigit', 'isalpha', 'isalnum', 'isspace', 'isupper', 'islower', 'isdecimal', 'isnumeric', 'isidentifier', 'isprintable', 'isascii', 'strip', 'lstrip', 'rstrip', 'casefold', 'title', 'capitalize', 'swapcase', 'upper', 'lower', 'format', 'translate', 'normalize', 'index', 'find', 'count', 'replace', 'partition', 'fromhex', 'hex')
    banned_name = ('isinstance', 'issubclass', 'int', 'float', 'ord', 'chr', 'eval', 'exec', 'getattr', 'hasattr', 'setattr', 'repr', 'str', 'list', 'dict', 'set', 'sorted', 'any', 'all', 'map', 'filter', 'compile', 'open', '__import__', 'import_module', 'iter', 'next', 'enumerate', 'zip', 'min', 'max', 'sum')
    calls = 0
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Call):
            calls += 1
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in banned_attr, node.func.attr
            if isinstance(node.func, ast.Name):
                assert node.func.id not in banned_name, node.func.id
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert (type(node).__name__, getattr(node, 'module', None), [a.name for a in node.names]) in (('ImportFrom', 'importlib.util', ['find_spec']), ('ImportFrom', REG, ['make_fail'])), ast.dump(node)
        assert not isinstance(node, (ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp, ast.Lambda))
    assert calls > 40


def test_loops_are_bounded_for_loops_and_the_only_while_loops_are_pinned():
    fors = 0
    whiles = 0
    for node in ast.walk(_tree()):
        if isinstance(node, ast.For):
            fors += 1
            it = node.iter
            ok = isinstance(it, ast.Name) or (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range') or isinstance(it, ast.Subscript) or isinstance(it, ast.BinOp)
            assert ok, ast.dump(it)
        if isinstance(node, ast.While):
            whiles += 1
    assert (fors, whiles) == LOOP_COUNTS


def test_type_is_only_used_as_an_exact_type_identity_test_and_never_in_membership():
    uses = 0
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Compare):
            for side in [node.left] + list(node.comparators):
                if isinstance(side, ast.Call) and isinstance(side.func, ast.Name) and side.func.id == 'type':
                    uses += 1
                    assert len(node.ops) == 1 and type(node.ops[0]) is ast.IsNot, ast.dump(node)
                    other = node.comparators[0]
                    assert isinstance(other, ast.Name) and other.id in ('str', 'tuple', 'bytes'), ast.dump(node)
    total = sum(1 for n in ast.walk(_tree()) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'type')
    assert uses == total and uses == TYPE_USES


def test_text_calls_are_limited_to_the_pinned_encode_decode_and_join_sites():
    sites = {}
    for fn in [n for n in ast.walk(_tree()) if isinstance(n, ast.FunctionDef)]:
        for c in ast.walk(fn):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute):
                key = (fn.name, c.func.attr)
                sites[key] = sites.get(key, 0) + 1
    assert sites == ATTR_SITES


def test_lookalike_text_is_refused_everywhere_and_nothing_folds():
    for ch in ('\u212a', '\u0130', '\u0131', '\u00df', '\uff21', '\uff10', '\u0660', '\u00b2', '\u2160', '\u00a0', '\u2028', '\u0085', '\u200b', '\ufeff', '\u037e', '\u2024', '\uff0c', '\uff1d', '\uff0b', '\uff3c', '\u201c'):
        assert m.dn_ok(ch + '=x') is False and m.dn_ok('a' + ch + '=x') is False, repr(ch)
        assert m.attribute_type_ok(ch) is False and m.attribute_type_ok('a' + ch) is False and m.attribute_type_ok('1.' + ch) is False
        assert m.attribute_type_ok(ch + 'a') is False
    for ch in ('\uff0c', '\uff1d', '\uff0b', '\uff3c', '\u201c', '\u2028', '\u00a0', '\u037e', '\ufeff'):
        text = 'a=' + ch + 'b'
        assert m.dn_ok(text) is True, repr(ch)
        assert m.parse_dn(text)[0][0][2] == (ch + 'b').encode('utf-8')
    assert m.dn_ok('a=\\\uff10\uff10') is False and m.dn_ok('a=\\\u0660\u0660') is False
    assert m.dn_ok('a=\\1\uff10') is False and m.dn_ok('a=\\\u00b21') is False
    assert m.dn_ok('1\u0660.2=#00') is False and m.dn_ok('1.\u06602=#00') is False
    assert m.dn_ok('a=#\uff10\uff10') is False and m.dn_ok('a=#\u0660\u0660') is False
    assert m.dn_ok('a=#0\u00b2') is False
    assert m.dn_ok('a=b,\u212a=c') is False
    assert m.parse_dn('a=\\41')[0][0][2] == b'A' and m.parse_dn('a=\\4a')[0][0][2] == b'J' and m.parse_dn('a=\\4A')[0][0][2] == b'J'


def test_whole_module_docstring_is_pinned_and_states_the_scope():
    assert m.__doc__ == DOC_EXACT
    assert ast.get_docstring(_tree(), clean=False) == DOC_EXACT
    assert m.CLAIMS is False
    for word in ('RFC 4514', 'EID 73', 'EID 7229', '2 records', '9 errata records', '7896 is Reported Technical', '7 errata records', 'RFC 2253', 'EID 2664', 'OURS', 'section 2.4', 'section 3'):
        assert word in DOC_EXACT, word
    assert '\u2014' not in DOC_EXACT


def test_every_function_docstring_including_private_ones_is_pinned():
    found = {}
    for n in ast.walk(_tree()):
        if isinstance(n, ast.FunctionDef):
            found.setdefault(n.name, []).append(ast.get_docstring(n, clean=False))
    assert found == FUNC_DOCS
    assert len(found) >= 17
    assert all(v and all(type(d) is str and d != '' for d in v) for v in found.values())
    for name in FNS:
        assert getattr(m, name).__doc__ == FUNC_DOCS[name][0]


def test_module_constants_are_pinned_whole_by_type_and_repr():
    for name, tname, rep in CONSTS:
        value = getattr(m, name)
        assert type(value).__name__ == tname, name
        assert repr(value) == rep, name
    assert len(CONSTS) == 16
    assert m.CLAIMS is False and type(m.NOT_CLAIMED) is tuple and type(m.ADJACENT) is tuple
    assert m.SCOPE.startswith('PARTIAL:')


def test_module_namespace_names_are_pinned_in_definition_order():
    names = [k for k in vars(m) if not (k.startswith('__') and k.endswith('__'))]
    assert names == NAMESPACE
    assert callable(m.make_fail)


def test_asserted_scope_claims_nothing_beyond_syntax_and_conversion():
    assert m.NOT_CLAIMED == ('attribute type registry or short name table', 'BER validity of hex values', 'distinguishedNameMatch comparison', 'RFC 2253 legacy forms', 'production readiness')
    assert m.ADJACENT == ('RFC 3629 UTF-8 units', 'RFC 4515 filter escaping', 'RFC 4516 LDAP URL')
    # a hexstring is any run of hexpairs: the BER inside is not parsed (OURS)
    assert m.dn_ok('a=#ff') is True and m.dn_ok('a=#0000') is True
    # legacy RFC 2253 forms are refused: hex-less quoted values and the semicolon separator
    assert m.dn_ok('a="b"') is False and m.dn_ok('a=b;c=d') is False


# ---------------------------------------------------------------- quotes (OURS: the quoted RFC text is checked against a fresh fetch) and errata
def _fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        return urllib.request.urlopen(req, timeout=60).read().decode('utf-8')
    except OSError as e:
        pytest.fail('cannot verify against %s: set the P235_* env file (%s)' % (url, e))


def _rfc_text(env, num, size):
    path = os.environ.get(env)
    if path:
        assert os.path.exists(path) and os.path.getsize(path) > size, env + ' is empty or missing'
        return open(path, encoding='utf-8').read()
    text = _fetch('https://www.rfc-editor.org/rfc/rfc%d.txt' % num)
    assert len(text) > size
    return text


def _ws(text):
    return ' '.join(text.split())


QUOTES_4514 = [
    'distinguishedName = [ relativeDistinguishedName *( COMMA relativeDistinguishedName ) ]',
    'relativeDistinguishedName = attributeTypeAndValue *( PLUS attributeTypeAndValue )',
    'attributeTypeAndValue = attributeType EQUALS attributeValue',
    'attributeType = descr / numericoid',
    'attributeValue = string / hexstring',
    'string = [ ( leadchar / pair ) [ *( stringchar / pair ) ( trailchar / pair ) ] ]',
    'leadchar = LUTF1 / UTFMB',
    'LUTF1 = %x01-1F / %x21 / %x24-2A / %x2D-3A / %x3D / %x3F-5B / %x5D-7F',
    'trailchar = TUTF1 / UTFMB',
    'TUTF1 = %x01-1F / %x21 / %x23-2A / %x2D-3A /',
    'stringchar = SUTF1 / UTFMB',
    'SUTF1 = %x01-21 / %x23-2A / %x2D-3A / %x3D / %x3F-5B / %x5D-7F',
    'pair = ESC ( ESC / special / hexpair )',
    'special = escaped / SPACE / SHARP / EQUALS',
    'escaped = DQUOTE / PLUS / COMMA / SEMI / LANGLE / RANGLE',
    'hexstring = SHARP 1*hexpair',
    'hexpair = HEX HEX',
    'If the RDNSequence is an empty sequence, the result is the empty or zero-length string.',
    "a space (' ' U+0020) character occurring at the end of the string;",
    'the null (U+0000) character.',
    'Each octet of the character to be escaped is replaced by a backslash and two hex digits, which form a single octet in the code of the character.',
    'There is one or more attribute value assertions, separated by <PLUS>, for a relative distinguished name.',
    'There is zero or more relative distinguished names, separated by <COMMA>, for a distinguished name.',
    'This document does not define a canonical string representation for DNs.',
]
QUOTES_4512 = [
    'keystring = leadkeychar *keychar',
    'leadkeychar = ALPHA',
    'keychar = ALPHA / DIGIT / HYPHEN',
    'number = DIGIT / ( LDIGIT 1*DIGIT )',
    'numericoid = number 1*( DOT number )',
    'descr = keystring',
    'UTF2 = %xC2-DF UTF0',
    'UTF0 = %x80-BF',
]


def test_quotes_are_verbatim_in_a_fresh_copy_of_rfc_4514_and_4512():
    t14 = _ws(_rfc_text('P235_RFC4514_TXT', 4514, 30000))
    t12 = _ws(_rfc_text('P235_RFC4512_TXT', 4512, 100000))
    assert len(QUOTES_4514) == 24 and len(set(QUOTES_4514)) == 24
    assert len(QUOTES_4512) == 8 and len(set(QUOTES_4512)) == 8
    for q in QUOTES_4514:
        assert _ws(q) in t14, q
    for q in QUOTES_4512:
        assert _ws(q) in t12, q
    # TUTF1 differs from LUTF1 only by allowing SHARP (%x23) (OURS reading of the s3 text)


def _errata_records():
    path = os.environ.get('P235_ERRATA_JSON')
    if path:
        assert os.path.exists(path) and os.path.getsize(path) > 100000, 'P235_ERRATA_JSON is empty or missing'
        return json.load(open(path, encoding='utf-8'))
    return json.loads(_fetch('https://www.rfc-editor.org/errata.json'))


def test_errata_ledger_for_rfc_4514_4512_4234_and_2253_matches_errata_json():
    records = _errata_records()
    assert len(records) > 1000

    def ledger(doc):
        return {str(r['errata_id']): (r['errata_status_code'], r['errata_type_code'], r.get('section')) for r in records if r.get('doc-id') == doc}
    r4514 = ledger('RFC4514')
    assert len(r4514) == 2
    assert r4514 == {'73': ('Held for Document Update', 'Editorial', '4'), '7229': ('Verified', 'Editorial', '2.4')}
    r4512 = ledger('RFC4512')
    assert len(r4512) == 9
    assert sorted(int(k) for k in r4512) == [74, 2281, 5261, 7224, 7225, 7226, 7227, 7228, 7896]
    assert r4512['7896'][:2] == ('Reported', 'Technical')
    assert sorted(int(k) for k in ledger('RFC4234')) == [159, 160, 777, 778, 783, 866, 2625]
    assert sorted(int(k) for k in ledger('RFC2253')) == [2664]
    for eid in ('EID 73 Held for Document Update Editorial section 4', 'EID 7229 Verified Editorial section 2.4', '2 records', 'EID 74 2281 5261 7224 7225 7226 7227 7228 7896', '7896 is Reported Technical', '7 errata records', 'EID 159 160 777 778 783 866 2625', 'EID 2664'):
        assert eid in m.__doc__, eid


# ---------------------------------------------------------------- four-combo child pytest proof
def test_suite_passes_in_four_child_pytest_combos_slow(tmp_path):
    backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(SRC_PATH))))
    stub = tmp_path / 'stub'
    for rel in ('app', 'app/modules', 'app/modules/instinct_doc'):
        (stub / rel).mkdir(parents=True, exist_ok=True)
        (stub / rel / '__init__.py').write_text("__path__ = __import__('pkgutil').extend_path(__path__, __name__)\n")
    (stub / 'app/modules/instinct_doc/p235_concepts_registry.py').write_text("def make_fail(name):\n    def fail(code):\n        raise ValueError('STUB:%s:%s' % (name, code))\n    return fail\n")
    empty = tmp_path / 'none'
    empty.mkdir()
    combos = [(str(stub), '0'), (str(empty), '1'), ('', '2'), ('', 'random')]
    for world, seed in combos:
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=((world + os.pathsep) if world else '') + backend)
        r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', __file__, '-k', 'not slow'], env=env, capture_output=True, text=True, timeout=60, cwd=str(tmp_path))
        assert r.returncode == 0, (world, seed, r.stdout[-400:], r.stderr[-200:])
        assert ' passed' in r.stdout and 'failed' not in r.stdout


# ---------------------------------------------------------------- generated pins (regenerate with gen_meta.py after any module edit)
DOC_EXACT = 'b1229 RFC 4514 (LDAP string representation of Distinguished Names): the section 3 grammar, the section 2.3 and 2.4 conversion rules, over caller text and caller tuples only.\ndn_ok(text) -> bool: True when the exact str is a distinguishedName of section 3 (zero or more RDNs, so the empty str is a DN). attribute_type_ok(text) -> bool: descr or numericoid (RFC 4512 section 1.4, copied here). A non-str raises bad_type:text and a str longer than 1024 characters raises bad_value:text.length before any scan. Other bad text returns False. Text is never trimmed and never case folded.\nparse_dn(text) -> tuple of RDNs in the order written (section 2.1 writes the RDNSequence backwards; this module does not reverse), each RDN a tuple of AVAs, each AVA a tuple (type, kind, value): type is the text as given, kind is \'string\' or \'hex\', value is bytes: the UTF-8 octets after each pair is replaced (section 3) for \'string\', the BER octets of the hexpairs for \'hex\'. Bad text raises bad_value:text.syntax.\nformat_dn(rdns) -> str: the section 2 conversion of a parse-shaped tuple. A \'string\' value must be strict UTF-8; \' \' or \'#\' at the start, \' \' at the end, \'"\' \'+\' \',\' \';\' \'<\' \'>\' \'\' anywhere are written backslash then the character, U+0000 is written \x00, everything else is written as is (OURS: the one-character backslash alternative of section 2.4). A \'hex\' value is written \'#\' and its octets as uppercase hexpairs and may not be empty. Section 2.4 requires the \'#\' form for a numericoid type, so format_dn refuses a \'string\' value on a numericoid type (bad_value:rdns.kind) although parse_dn accepts it (section 3 allows it). Empty RDNs are refused.\nLimits (OURS): text and formatted text are at most 1024 characters; rdns and each RDN hold at most 1024 items, each type at most 1024 characters and each value at most 4096 octets (4 octets for each of 1024 characters), all checked before the items are walked, so every parse_dn result is within the caps format_dn checks.\nErrors: format_dn checks rdns type and count, then each RDN (type, count, not empty), then each AVA (type, size 3), then type, kind, value in that order, and last the formatted length.\nErrata on RFC 4514 (2 records on errata.json): EID 73 Held for Document Update Editorial section 4 and EID 7229 Verified Editorial section 2.4 (both wording only, no effect). RFC 4512, whose descr, numericoid and UTF-8 productions this module copies, has 9 errata records (EID 74 2281 5261 7224 7225 7226 7227 7228 7896; 7896 is Reported Technical on DITStructureRule syntax, which this module does not use). RFC 4234, the ABNF of both, has 7 errata records (EID 159 160 777 778 783 866 2625). RFC 2253 (obsolete, 1 record: EID 2664) is not used. None is applied.\n'
FUNC_DOCS = {'_all_in': ['True when every character of the exact str is in allowed (an empty str is True).'], '_is_utfmb': ['True for one non-ASCII character that UTF-8 can carry (section 3 UTFMB): not a surrogate.'], '_is_descr': ['RFC 4512 descr: a letter then letters, digits and hyphens.'], '_is_numericoid': ['RFC 4512 numericoid: two or more numbers (0 or no leading zero) separated by dots.'], '_type_ok': ['The attributeType production: descr or numericoid.'], '_hexbytes': ['Octets of an even-length str of hex digits (already checked).'], '_string': ['The string production on text with pairs: return the octets, or None when it does not match.'], '_value': ['The attributeValue production: return (kind, octets) or None.'], '_ava': ['The attributeTypeAndValue production: return (type, kind, octets) or None.'], '_parse': ['The distinguishedName production on an exact str already length checked: return the RDN tuple or None.'], '_arg': ['Check the exact type and the length cap of a text argument.'], 'dn_ok': ['True when the exact str is a distinguishedName (RFC 4514 section 3); the empty str is one.'], 'attribute_type_ok': ['True when the exact str is an attributeType: a descr or a numericoid.'], 'parse_dn': ['Return the RDN tuples of a distinguishedName in the order written; refuse any other text.'], '_escape': ['Section 2.4 escaping of a decoded value, using the backslash alternative.'], '_hexup': ['Uppercase hexpairs of the octets.'], '_format_ava': ['Check one AVA tuple and return its string encoding.'], 'format_dn': ['Render a parse-shaped tuple of RDNs as a distinguishedName string (RFC 4514 section 2).'], 'make_fail': ['Fallback used only when the shared registry module is absent: return a failer for the named function.'], 'fail': ['Raise ValueError with the P235 name and code.']}
NAMESPACE = ['find_spec', 'make_fail', 'CLAIMS', 'SCOPE', 'NOT_CLAIMED', 'ADJACENT', 'MAX_DN', 'MAX_VALUE', '_ALPHA', '_DIGIT', '_KEYCHARS', '_HEXVAL', '_HEXUP', '_PAIRSPECIAL', '_ESCAPED', '_LUTF1', '_TUTF1', '_SUTF1', '_all_in', '_is_utfmb', '_is_descr', '_is_numericoid', '_type_ok', '_hexbytes', '_string', '_value', '_ava', '_parse', '_arg', 'dn_ok', 'attribute_type_ok', 'parse_dn', '_escape', '_hexup', '_format_ava', 'format_dn']
CONSTS = [('CLAIMS', 'bool', 'False'), ('SCOPE', 'str', "'PARTIAL: RFC 4514 section 3 grammar and section 2 conversion of Distinguished Names over caller text and tuples, no attribute registry and no value syntax checks'"), ('NOT_CLAIMED', 'tuple', "('attribute type registry or short name table', 'BER validity of hex values', 'distinguishedNameMatch comparison', 'RFC 2253 legacy forms', 'production readiness')"), ('ADJACENT', 'tuple', "('RFC 3629 UTF-8 units', 'RFC 4515 filter escaping', 'RFC 4516 LDAP URL')"), ('MAX_DN', 'int', '1024'), ('MAX_VALUE', 'int', '4096'), ('_ALPHA', 'str', "'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'"), ('_DIGIT', 'str', "'0123456789'"), ('_KEYCHARS', 'str', "'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'"), ('_HEXVAL', 'dict', "{'0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14, 'F': 15, 'a': 10, 'b': 11, 'c': 12, 'd': 13, 'e': 14, 'f': 15}"), ('_HEXUP', 'str', "'0123456789ABCDEF'"), ('_PAIRSPECIAL', 'str', '\'\\\\"+,;<> #=\''), ('_ESCAPED', 'str', '\'"+,;<>\\\\\''), ('_LUTF1', 'str', '"\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08\\t\\n\\x0b\\x0c\\r\\x0e\\x0f\\x10\\x11\\x12\\x13\\x14\\x15\\x16\\x17\\x18\\x19\\x1a\\x1b\\x1c\\x1d\\x1e\\x1f!$%&\'()*-./0123456789:=?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_`abcdefghijklmnopqrstuvwxyz{|}~\\x7f"'), ('_TUTF1', 'str', '"\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08\\t\\n\\x0b\\x0c\\r\\x0e\\x0f\\x10\\x11\\x12\\x13\\x14\\x15\\x16\\x17\\x18\\x19\\x1a\\x1b\\x1c\\x1d\\x1e\\x1f!#$%&\'()*-./0123456789:=?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_`abcdefghijklmnopqrstuvwxyz{|}~\\x7f"'), ('_SUTF1', 'str', '"\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08\\t\\n\\x0b\\x0c\\r\\x0e\\x0f\\x10\\x11\\x12\\x13\\x14\\x15\\x16\\x17\\x18\\x19\\x1a\\x1b\\x1c\\x1d\\x1e\\x1f !#$%&\'()*-./0123456789:=?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_`abcdefghijklmnopqrstuvwxyz{|}~\\x7f"')]
LOOP_COUNTS = (11, 0)
TYPE_USES = 7
ATTR_SITES = {('_is_numericoid', 'split'): 1, ('_string', 'encode'): 2, ('_string', 'append'): 3, ('_ava', 'split'): 1, ('_parse', 'append'): 3, ('_escape', 'join'): 1, ('_escape', 'append'): 5, ('_hexup', 'join'): 1, ('_hexup', 'append'): 1, ('_format_ava', 'decode'): 1, ('format_dn', 'join'): 2, ('format_dn', 'append'): 2}

