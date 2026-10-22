"""Tests for p235 concepts batch 1272: RFC 3629 UTF-8 octet grammar over caller-supplied bytes and ints. Pure functions over caller data; claims asserted False."""
import ast
import builtins
import hashlib
import importlib.util
import os
import random
import re
import signal
import subprocess
import inspect
import sys
import traceback
import types

import pytest
from importlib.util import find_spec

REG = 'app.modules.instinct_doc.p235_concepts_registry'

import app.modules.instinct_doc.p235_concepts_batch1272_utf8 as m  # noqa: E402
MODPATH = m.__file__


def _prefix():
    spec = importlib.util.spec_from_file_location('b1272_pfx', MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        return str(e)[:-len('x:c')]


PFX = _prefix()


class _Alarm(AssertionError):
    pass


@pytest.fixture(autouse=True)
def _alarm():
    def handler(signum, frame):
        raise _Alarm('ALARM test exceeded 60 seconds (hang guard only)')
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 60.0)
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, old)


@pytest.fixture
def mp(monkeypatch):
    return monkeypatch


def fresh(name='b1272_fresh'):
    spec = importlib.util.spec_from_file_location(name, MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def E(fn, code):
    return ('raise', PFX + fn + ':' + code)


def run(fn, *args, mod=None):
    mod = mod or m
    try:
        return ('ok', getattr(mod, fn)(*args))
    except ValueError as e:
        return ('raise', str(e))


def _read(path):
    with open(path, 'r') as fh:
        return fh.read()


NAMES = ('utf8_reason', 'ascii_reason', 'char_reason', 'lead_reason', 'tail_reason', 'codepoint_reason',
         'encoded_length', 'encode_codepoint', 'decode_utf8', 'char_lengths')
BYTES_FNS = ('utf8_reason', 'ascii_reason', 'char_reason', 'lead_reason', 'tail_reason', 'decode_utf8', 'char_lengths')
INT_FNS = ('codepoint_reason', 'encoded_length', 'encode_codepoint')
SAMPLE = {fn: (b'A' if fn in BYTES_FNS else 65) for fn in NAMES}
PRIVATE = ('_LEN_CAP', '_check', '_lead', '_scan', '_cp_reason')
QUOTES = ['In UTF-8, characters from the U+0000..U+10FFFF range (the UTF-16 accessible range) are encoded using sequences of 1 to 4 octets.',
          'The only octet of a "sequence" of one has the higher-order bit set to 0, the remaining 7 bits being used to encode the character number.',
          'In a sequence of n octets, n>1, the initial octet has the n higher-order bits set to 1, followed by a bit set to 0.',
          'The following octet(s) all have the higher-order bit set to 1 and the following bit set to 0, leaving 6 bits in each to contain bits from the character to be encoded.',
          '0000 0000-0000 007F | 0xxxxxxx', '0000 0080-0000 07FF | 110xxxxx 10xxxxxx',
          '0000 0800-0000 FFFF | 1110xxxx 10xxxxxx 10xxxxxx', '0001 0000-0010 FFFF | 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx',
          'It is important to note that the rows of the table are mutually exclusive, i.e., there is only one valid way to encode a given character.',
          'The definition of UTF-8 prohibits encoding character numbers between U+D800 and U+DFFF, which are reserved for use with the UTF-16 encoding form (as surrogate pairs) and do not directly represent characters.',
          'Implementations of the decoding algorithm above MUST protect against decoding invalid sequences.',
          'a naive implementation may decode the overlong UTF-8 sequence C0 80 into the character U+0000, or the surrogate pair ED A1 8C ED BE B4 into U+233B4.',
          'the CESU-8 encoding of those characters is NOT valid UTF-8.',
          'UTF8-octets = *( UTF8-char )', 'UTF8-char = UTF8-1 / UTF8-2 / UTF8-3 / UTF8-4', 'UTF8-1 = %x00-7F',
          'UTF8-2 = %xC2-DF UTF8-tail',
          'UTF8-3 = %xE0 %xA0-BF UTF8-tail / %xE1-EC 2( UTF8-tail ) / %xED %x80-9F UTF8-tail / %xEE-EF 2( UTF8-tail )',
          'UTF8-4 = %xF0 %x90-BF 2( UTF8-tail ) / %xF1-F3 3( UTF8-tail ) / %xF4 %x80-8F 2( UTF8-tail )',
          'UTF8-tail = %x80-BF',
          'NOTE -- The authoritative definition of UTF-8 is in [UNICODE]. This grammar is believed to describe the same thing Unicode describes, but does not claim to be authoritative.']


def test_header_quotes_are_in_the_header_and_distinct():
    assert len(QUOTES) == len(set(QUOTES)) and len(QUOTES) >= 20
    doc = ' '.join(m.__doc__.split())
    for qt in QUOTES:
        assert qt in doc, qt


def test_header_quotes_are_verbatim_in_the_pinned_rfc_text_when_present():
    path = os.environ.get('RFC3629_TXT')
    if not path or not os.path.exists(path):
        pytest.skip('RFC text not supplied')
    with open(path, 'rb') as fh:
        raw = fh.read()
    assert hashlib.sha256(raw).hexdigest() == 'a2a3a39457d30420c812f87a38cc2b9194832f6982ef17e619de7d816879d6a6'
    text = ' '.join(raw.decode('ascii').split())
    for qt in QUOTES:
        assert qt in text, qt


def test_header_names_errata_sources_and_functions():
    doc = m.__doc__
    for sha in ('a2a3a39457d30420c812f87a38cc2b9194832f6982ef17e619de7d816879d6a6',
                '126c267614990bbdb4daa2a2f39894f97970624bf8909599016f466710dabbbb',
                '23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c'):
        assert sha in doc
    assert '"Obsoletes: 2279"' in doc and 'STD 63' in doc
    assert 'exactly zero RFC 3629 records' in doc and 'not independently confirmed' in doc
    for fn in NAMES:
        assert fn in doc
    assert doc.startswith('p235 concepts batch 1272 (rev 0): RFC 3629')


def test_module_imports_and_source_bans():
    tree = ast.parse(_read(MODPATH))
    imps = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert len(imps) == 2
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in ('re', 'ord', 'chr', 'codecs', 'unicodedata', 'binascii', 'hashlib', 'random', 'secrets', 'time', 'datetime', 'str', 'socket', 'struct'):
            raise AssertionError('forbidden name referenced: %s' % node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('ord', 'chr', 'bin', 'hex', 'open', 'eval', 'exec', 'int', 'str', 'bytearray', 'memoryview'):
            raise AssertionError('forbidden call: %s' % node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'v':
                raise AssertionError('method call on input: %s' % node.func.attr)
        if isinstance(node, (ast.If, ast.While)) and isinstance(node.test, ast.Constant) and isinstance(node.test.value, bool):
            raise AssertionError('bool constant as branch condition')
        if isinstance(node, ast.BoolOp):
            for c in node.values:
                if isinstance(c, ast.Constant) and isinstance(c.value, bool):
                    raise AssertionError('bool constant in BoolOp')


def test_public_function_definition_order_and_namespace_pinned():
    tree = ast.parse(_read(MODPATH))
    defs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')]
    assert defs == list(NAMES)
    names = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.extend(a.asname or a.name for a in node.names)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.append(t.id)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
    want = ['find_spec', '_REG', 'SCOPE', 'NOT_CLAIMED', 'CLAIMS', 'ADJACENT'] + list(PRIVATE) + list(NAMES)
    assert sorted(set(names)) == sorted(set(want))


def test_docstrings_and_private_names():
    for fn in NAMES:
        f = getattr(m, fn)
        assert callable(f) and f.__doc__ is None
    for p in PRIVATE:
        obj = getattr(m, p)
        if callable(obj):
            assert obj.__doc__ is None, p


def test_source_and_tests_have_no_vacuous_assertions():
    banned = ['or' + ' True', 'if' + ' False', 'else' + ' True', 'and' + ' False', 'or' + ' False', 'assert' + ' True']
    for path in (MODPATH, __file__):
        for b in banned:
            assert b not in _read(path), (path, b)


class _HostileBytes(bytes):
    pass


class _HostileInt(int):
    pass


def _mkhostile(base, val):
    class MM(type):
        def __eq__(self, other):
            return True

    class S(base, metaclass=MM):
        pass
    return S(val)


@pytest.mark.parametrize('fn', NAMES)
def test_every_argument_is_an_exact_type_by_identity(fn):
    common = [None, 3.5, ['a'], ('a',), {'a'}, {'a': 1}, 'A', 'abc']
    if fn in BYTES_FNS:
        bad = common + [1, True, False, 0, bytearray(b'A'), memoryview(b'A'), _HostileBytes(b'A'), _mkhostile(bytes, b'A')]
    else:
        bad = common + [b'A', bytearray(b'A'), True, False, _HostileInt(65), _mkhostile(int, 65)]
    for b in bad:
        assert run(fn, b) == E(fn, 'bad_type:value'), (fn, b)


# ---- independent oracles: the stdlib codec (validity), the section 4 ABNF as a bytes regex, and a table walker for reasons ----
_ABNF = re.compile(
    rb'(?:[\x00-\x7f]|[\xc2-\xdf][\x80-\xbf]'
    rb'|\xe0[\xa0-\xbf][\x80-\xbf]|[\xe1-\xec][\x80-\xbf]{2}|\xed[\x80-\x9f][\x80-\xbf]|[\xee-\xef][\x80-\xbf]{2}'
    rb'|\xf0[\x90-\xbf][\x80-\xbf]{2}|[\xf1-\xf3][\x80-\xbf]{3}|\xf4[\x80-\x8f][\x80-\xbf]{2})*')

# lead octet -> (sequence length, allowed second octets); every other tail is 80..BF
_SEQ = ([(range(0xC2, 0xE0), 2, 0x80, 0xBF), (range(0xE0, 0xE1), 3, 0xA0, 0xBF), (range(0xE1, 0xED), 3, 0x80, 0xBF),
         (range(0xED, 0xEE), 3, 0x80, 0x9F), (range(0xEE, 0xF0), 3, 0x80, 0xBF), (range(0xF0, 0xF1), 4, 0x90, 0xBF),
         (range(0xF1, 0xF4), 4, 0x80, 0xBF), (range(0xF4, 0xF5), 4, 0x80, 0x8F)])


def ref_lead(b):
    if b < 0x80:
        return 'ok'
    if 0x80 <= b <= 0xBF or b >= 0xF8:
        return 'lead'
    if b in (0xC0, 0xC1):
        return 'overlong'
    if 0xF5 <= b <= 0xF7:
        return 'range'
    return 'ok'


def ref_first(v):
    # reason for the first character of v, and its length (0 when it failed); v is not empty
    b = v[0]
    r = ref_lead(b)
    if r != 'ok':
        return r, 0
    if b < 0x80:
        return 'ok', 1
    for rg, n, lo, hi in _SEQ:
        if b in rg:
            for k in range(1, n):
                if k >= len(v):
                    return 'truncated', 0
                t = v[k]
                if not 0x80 <= t <= 0xBF:
                    return 'tail', 0
                if k == 1 and t < lo:
                    return 'overlong', 0
                if k == 1 and t > hi:
                    return ('surrogate' if b == 0xED else 'range'), 0
            return 'ok', n
    raise AssertionError('unreachable')


def ref_reason(v):
    i = 0
    while i < len(v):
        r, n = ref_first(v[i:])
        if r != 'ok':
            return r
        i += n
    return 'ok'


def ref_char(v):
    if not v:
        return 'empty'
    r, n = ref_first(v)
    if r != 'ok':
        return r
    return 'extra' if len(v) > n else 'ok'


def _stdlib_ok(v):
    try:
        v.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


def _check_bytes(v):
    ok = ref_reason(v) == 'ok'
    assert ok == _stdlib_ok(v) == (_ABNF.fullmatch(v) is not None), v
    assert m.utf8_reason(v) == ref_reason(v), v
    assert m.char_reason(v) == ref_char(v), v
    assert (m.ascii_reason(v) == 'ok') == all(b < 128 for b in v), v
    if ok:
        want = tuple(len(chr(c).encode()) for c in map(ord, v.decode()))
        assert m.char_lengths(v) == want and sum(want) == len(v), v
        assert m.decode_utf8(v) == tuple(map(ord, v.decode())), v
    else:
        assert run('decode_utf8', v) == E('decode_utf8', 'bad_value:value.utf8'), v
        assert run('char_lengths', v) == E('char_lengths', 'bad_value:value.utf8'), v


def test_len_cap_at_cap_and_cap_plus_one_on_every_function():
    assert m._LEN_CAP == 1024
    for fn in BYTES_FNS:
        assert run(fn, b'a' * 1025) == E(fn, 'bad_value:value.length'), fn
        assert run(fn, b'\x80' * 2048) == E(fn, 'bad_value:value.length'), fn
    at = b'a' * 1024
    assert run('utf8_reason', at) == ('ok', 'ok') and run('ascii_reason', at) == ('ok', 'ok')
    assert run('char_reason', at) == ('ok', 'extra')
    assert run('lead_reason', at) == ('ok', 'length') and run('tail_reason', at) == ('ok', 'length')
    assert run('decode_utf8', at) == ('ok', (97,) * 1024)
    assert run('char_lengths', at) == ('ok', (1,) * 1024)
    two = '\u00e9'.encode() * 512
    assert len(two) == 1024
    assert run('decode_utf8', two) == ('ok', (233,) * 512) and run('char_lengths', two) == ('ok', (2,) * 512)
    assert run('utf8_reason', b'a' * 1023 + b'\xc3') == ('ok', 'truncated')
    assert run('utf8_reason', b'a' * 1024 + b'\xc3') == E('utf8_reason', 'bad_value:value.length')
    assert run('utf8_reason', b'\xc3') == ('ok', 'truncated')
    assert run('utf8_reason', b'a' * 1022 + b'\xc3\xa9') == ('ok', 'ok')


def test_every_single_octet_through_every_bytes_function():
    for b in range(256):
        v = bytes([b])
        assert m.lead_reason(v) == ref_lead(b), b
        assert m.tail_reason(v) == ('ok' if 0x80 <= b <= 0xBF else 'tail'), b
        assert m.ascii_reason(v) == ('ok' if b < 128 else 'nonascii'), b
        _check_bytes(v)
    assert m.lead_reason(b'') == 'length' and m.lead_reason(b'ab') == 'length'
    assert m.tail_reason(b'') == 'length' and m.tail_reason(b'\x80\x80') == 'length'
    assert m.utf8_reason(b'') == 'ok' and m.decode_utf8(b'') == () and m.char_lengths(b'') == ()
    assert m.char_reason(b'') == 'empty' and m.ascii_reason(b'') == 'ok'


def test_all_two_octet_strings():
    for a in range(256):
        for b in range(256):
            _check_bytes(bytes([a, b]))


def test_three_octet_strings_over_every_boundary_lead():
    leads = (0x41, 0xC1, 0xC2, 0xDF, 0xE0, 0xE1, 0xEC, 0xED, 0xEE, 0xEF, 0xF0, 0xF1, 0xF4, 0xF5)
    seconds = (0x00, 0x41, 0x7F, 0x80, 0x8F, 0x90, 0x9F, 0xA0, 0xBF, 0xC0, 0xFF)
    for a in leads:
        for b in seconds:
            for c in range(0x7E, 0xC1):
                _check_bytes(bytes([a, b, c]))
    for a in range(0xE0, 0xF0):
        for b in range(256):
            assert m.utf8_reason(bytes([a, b, 0x80])) == ref_reason(bytes([a, b, 0x80]))


def test_four_octet_strings_over_every_boundary():
    leads = (0xEF, 0xF0, 0xF1, 0xF3, 0xF4, 0xF5, 0xF7, 0xF8, 0xFF)
    for a in leads:
        for b in (0x7F, 0x80, 0x8F, 0x90, 0xBF, 0xC0):
            for c in (0x7F, 0x80, 0xBF, 0xC0):
                for d in (0x7F, 0x80, 0xBF, 0xC0):
                    _check_bytes(bytes([a, b, c, d]))


def _junk(rnd):
    pool = [0, 0x41, 0x7F, 0x80, 0x8F, 0x90, 0x9F, 0xA0, 0xBF, 0xC0, 0xC1, 0xC2, 0xDF, 0xE0, 0xE1, 0xEC, 0xED, 0xEE, 0xEF,
            0xF0, 0xF1, 0xF3, 0xF4, 0xF5, 0xF8, 0xFF]
    out = bytearray()
    for _ in range(rnd.randint(0, 12)):
        pick = rnd.randint(0, 3)
        if pick == 0:
            out.extend(chr(rnd.choice([0x41, 0xE9, 0x20AC, 0x1F600, 0x7FF, 0x800, 0xFFFF, 0x10000, 0x10FFFF, 0xD7FF, 0xE000])).encode())
        else:
            out.append(rnd.choice(pool))
    return bytes(out)


@pytest.mark.parametrize('seed', [1, 2, 3])
def test_fuzz_against_codec_regex_and_table_oracles_1200(seed):
    rnd = random.Random(seed)
    for _ in range(1200):
        _check_bytes(_junk(rnd))


def test_reason_battery_spec_examples_and_edges():
    cases = [(b'', 'ok'), (b'A', 'ok'), (b'\xc2\x80', 'ok'), (b'\xdf\xbf', 'ok'), (b'\xe0\xa0\x80', 'ok'),
             (b'\xed\x9f\xbf', 'ok'), (b'\xee\x80\x80', 'ok'), (b'\xef\xbb\xbf', 'ok'), (b'\xf0\x90\x80\x80', 'ok'),
             (b'\xf4\x8f\xbf\xbf', 'ok'), (b'\xc0\x80', 'overlong'), (b'\xc1\xbf', 'overlong'), (b'\xe0\x9f\xbf', 'overlong'),
             (b'\xe0\x80\x80', 'overlong'), (b'\xf0\x8f\xbf\xbf', 'overlong'), (b'\xf0\x80\x80\x80', 'overlong'),
             (b'\xed\xa0\x80', 'surrogate'), (b'\xed\xa1\x8c\xed\xbe\xb4', 'surrogate'), (b'\xed\xbf\xbf', 'surrogate'),
             (b'\xf4\x90\x80\x80', 'range'), (b'\xf5\x80\x80\x80', 'range'), (b'\xf7\xbf\xbf\xbf', 'range'),
             (b'\x80', 'lead'), (b'\xbf', 'lead'), (b'\xf8\x88\x80\x80\x80', 'lead'), (b'\xff', 'lead'), (b'\xfe', 'lead'),
             (b'\xc3', 'truncated'), (b'\xe2\x82', 'truncated'), (b'\xf0\x9f\x98', 'truncated'), (b'\xe0\xa0', 'truncated'),
             (b'\xc3\x28', 'tail'), (b'\xe2\x28\xa1', 'tail'), (b'\xe2\x82\x28', 'tail'), (b'\xf0\x28\x8c\xbc', 'tail'),
             (b'\xf0\x9f\x28\x80', 'tail'), (b'\xf0\x9f\x98\x28', 'tail'), (b'A\x80', 'lead'), (b'\xc3\xa9\xc3', 'truncated')]
    for v, want in cases:
        assert m.utf8_reason(v) == want, v
        assert ref_reason(v) == want, v
    assert m.char_reason(b'') == 'empty' and m.char_reason(b'A') == 'ok' and m.char_reason(b'AB') == 'extra'
    assert m.char_reason(b'\xf0\x9f\x98\x80') == 'ok' and m.char_reason(b'\xf0\x9f\x98\x80\x80') == 'extra'
    assert m.char_reason(b'\xc0\x80') == 'overlong' and m.char_reason(b'\xc3') == 'truncated'
    assert m.char_reason(b'A\xff') == 'extra' and m.char_reason(b'\xc3\xa9\xff') == 'extra'
    assert m.char_lengths(b'a\xc3\xa9\xe2\x82\xac\xf0\x9f\x98\x80') == (1, 2, 3, 4)
    assert m.decode_utf8(b'a\xc3\xa9\xe2\x82\xac\xf0\x9f\x98\x80') == (97, 233, 8364, 128512)
    assert m.decode_utf8(b'\xef\xbb\xbf') == (65279,) and m.decode_utf8(b'\xf4\x8f\xbf\xbf') == (1114111,)
    assert m.decode_utf8(b'\xed\x9f\xbf\xee\x80\x80') == (55295, 57344)


def test_check_order_conflicting_reason_pairs_including_both_bad():
    # lead beats everything later; the first failure from left to right decides
    assert m.utf8_reason(b'\x80\xc0\xff') == 'lead' and m.utf8_reason(b'\xc0\x28') == 'overlong'
    assert m.utf8_reason(b'\xf8\xc3') == 'lead' and m.utf8_reason(b'\xf5\x28') == 'range'
    # inside one sequence: second octet tail check before overlong/surrogate/range; truncated only after the seen octets fit
    assert m.utf8_reason(b'\xe0\x28') == 'tail' and m.utf8_reason(b'\xe0\x80') == 'overlong'
    assert m.utf8_reason(b'\xed\x28') == 'tail' and m.utf8_reason(b'\xed\xa0') == 'surrogate'
    assert m.utf8_reason(b'\xf4\x28') == 'tail' and m.utf8_reason(b'\xf4\x90') == 'range'
    assert m.utf8_reason(b'\xf0\x28') == 'tail' and m.utf8_reason(b'\xf0\x80') == 'overlong'
    assert m.utf8_reason(b'\xe0\x80\x28') == 'overlong' and m.utf8_reason(b'\xed\xa0\x28') == 'surrogate'
    assert m.utf8_reason(b'\xf4\x90\x28\x28') == 'range' and m.utf8_reason(b'\xf0\x80\x28\x28') == 'overlong'
    assert m.utf8_reason(b'\xe1\x80\x28') == 'tail' and m.utf8_reason(b'\xf1\x80\x80\x28') == 'tail'
    assert m.utf8_reason(b'\xf1\x80\x28\x80') == 'tail' and m.utf8_reason(b'\xf1\x80\x80') == 'truncated'
    assert m.utf8_reason(b'\xc2') == 'truncated' and m.utf8_reason(b'\xc2\x28') == 'tail'
    # an earlier valid character never hides a later failure; an earlier failure hides a later one
    assert m.utf8_reason(b'\xc3\xa9\xed\xa0\x80') == 'surrogate' and m.utf8_reason(b'\xed\xa0\x80\xff') == 'surrogate'
    assert m.utf8_reason(b'\xe2\x82\xff\xc3') == 'tail' and m.utf8_reason(b'\xc0\xff') == 'overlong'
    # char_reason: empty, then the first character's reason, then extra
    assert m.char_reason(b'\xc0\x80\x80') == 'overlong' and m.char_reason(b'\xc3\xa9\x80') == 'extra'
    assert m.char_reason(b'\x80\x80') == 'lead' and m.char_reason(b'\xc3\x28\x28') == 'tail'
    # lead_reason / tail_reason: length first, then the octet class
    assert m.lead_reason(b'\xff\xff') == 'length' and m.lead_reason(b'') == 'length'
    assert m.tail_reason(b'\x41\x41') == 'length' and m.tail_reason(b'') == 'length'
    assert m.lead_reason(b'\xf5') == 'range' and m.lead_reason(b'\xc0') == 'overlong' and m.lead_reason(b'\xf8') == 'lead'
    assert m.lead_reason(b'\xbf') == 'lead' and m.lead_reason(b'\xc2') == 'ok' and m.lead_reason(b'\xf4') == 'ok'
    assert m.lead_reason(b'\xf7') == 'range' and m.lead_reason(b'\xf8') == 'lead' and m.lead_reason(b'\xc1') == 'overlong'
    # codepoint: the three failures are disjoint
    assert m.codepoint_reason(-1) == 'negative' and m.codepoint_reason(0x110000) == 'range'
    assert m.codepoint_reason(0xD800) == 'surrogate' and m.codepoint_reason(0xDFFF) == 'surrogate'
    assert m.codepoint_reason(0xD7FF) == 'ok' and m.codepoint_reason(0xE000) == 'ok' and m.codepoint_reason(0x10FFFF) == 'ok'


def test_codepoint_functions_every_boundary_and_a_stride_sweep():
    edges = (0, 1, 0x7E, 0x7F, 0x80, 0x81, 0x7FE, 0x7FF, 0x800, 0x801, 0xFFE, 0xFFF, 0x1000, 0xD7FE, 0xD7FF, 0xD800, 0xD801,
             0xDFFE, 0xDFFF, 0xE000, 0xE001, 0xFFFE, 0xFFFF, 0x10000, 0x10001, 0x10FFFE, 0x10FFFF, 0x110000, 0x110001, 1 << 64, 1 << 200)
    cps = sorted(set(list(edges) + [-1, -2, -(1 << 70)] + list(range(0, 0x900)) + list(range(0, 0x110000, 61))))
    for c in cps:
        valid = 0 <= c <= 0x10FFFF and not 0xD800 <= c <= 0xDFFF
        assert m.codepoint_reason(c) == ('ok' if valid else ('negative' if c < 0 else ('range' if c > 0x10FFFF else 'surrogate'))), c
        if valid:
            want = chr(c).encode()
            assert m.encode_codepoint(c) == want and m.encoded_length(c) == len(want), c
            assert m.decode_utf8(want) == (c,) and m.char_lengths(want) == (len(want),), c
            assert m.utf8_reason(want) == 'ok' and m.char_reason(want) == 'ok', c
        else:
            assert run('encode_codepoint', c) == E('encode_codepoint', 'bad_value:value.codepoint'), c
            assert run('encoded_length', c) == E('encoded_length', 'bad_value:value.codepoint'), c
    for c in (0xD800, 0xDBFF, 0xDC00, 0xDFFF):
        bytes3 = bytes([0xE0 + c // 4096, 0x80 + c // 64 % 64, 0x80 + c % 64])
        assert m.utf8_reason(bytes3) == 'surrogate' and not _stdlib_ok(bytes3)
    assert m.encode_codepoint(0x7F) == b'\x7f' and m.encode_codepoint(0x80) == b'\xc2\x80'
    assert m.encode_codepoint(0x7FF) == b'\xdf\xbf' and m.encode_codepoint(0x800) == b'\xe0\xa0\x80'
    assert m.encode_codepoint(0xFFFF) == b'\xef\xbf\xbf' and m.encode_codepoint(0x10000) == b'\xf0\x90\x80\x80'
    assert m.encode_codepoint(0x10FFFF) == b'\xf4\x8f\xbf\xbf' and m.encode_codepoint(0xD7FF) == b'\xed\x9f\xbf'
    assert m.encoded_length(0x7F) == 1 and m.encoded_length(0x80) == 2 and m.encoded_length(0x7FF) == 2
    assert m.encoded_length(0x800) == 3 and m.encoded_length(0xFFFF) == 3 and m.encoded_length(0x10000) == 4
    assert type(m.encode_codepoint(65)) is bytes and type(m.decode_utf8(b'A')) is tuple and type(m.char_lengths(b'A')) is tuple


def test_private_constants_and_lead_table_exact():
    assert m._LEN_CAP == 1024
    for b in range(256):
        r, n, lo, hi, mask = m._lead(b)
        assert r == ref_lead(b), b
        if r != 'ok':
            assert (n, lo, hi, mask) == (0, 0, 0, 0), b
        elif b < 0x80:
            assert (n, lo, hi, mask) == (1, 0, 0, 127), b
        else:
            for rg, ln, l2, h2 in _SEQ:
                if b in rg:
                    assert (n, lo, hi, mask) == (ln, l2, h2, {2: 31, 3: 15, 4: 7}[ln]), b
    assert m._cp_reason(-1) == 'negative' and m._cp_reason(0) == 'ok' and m._cp_reason(1114111) == 'ok'
    assert m._cp_reason(1114112) == 'range' and m._cp_reason(55295) == 'ok' and m._cp_reason(55296) == 'surrogate'
    assert m._cp_reason(57343) == 'surrogate' and m._cp_reason(57344) == 'ok'
    assert m._scan(b'', False) == ('ok', [], []) and m._scan(b'', True) == ('ok', [], [])
    assert m._scan(b'a\xc3\xa9', False) == ('ok', [1, 2], [97, 233])
    assert m._scan(b'a\xc3\xa9', True) == ('ok', [1], [97])
    assert m._scan(b'\xc3\xa9a', True) == ('ok', [2], [233])
    assert m._scan(b'a\xff', True) == ('ok', [1], [97]) and m._scan(b'a\xff', False) == ('lead', [1], [97])
    assert m._scan(b'\xe2\x82\xac\xed\xa0', False) == ('surrogate', [3], [8364])
    assert m._scan(b'\xf0\x9f\x98\x80\xc3', False) == ('truncated', [4], [128512])


def test_long_inputs_above_the_small_int_cache_and_loop_progress():
    # positions and counts above 256 (the small-int cache) and up to the 1024 cap and the 2048 over-cap
    for n in (255, 256, 257, 258, 300, 511, 512, 513, 1000, 1023, 1024):
        s = b'a' * n
        assert m.utf8_reason(s) == 'ok' and m.decode_utf8(s) == (97,) * n and m.char_lengths(s) == (1,) * n
        t = '\u20ac'.encode() * (n // 3)
        assert m.decode_utf8(t) == (8364,) * (n // 3) and m.char_lengths(t) == (3,) * (n // 3)
        for tail, want in ((b'\xc3', 'truncated'), (b'\xff', 'lead'), (b'\xed\xa0\x80', 'surrogate'), (b'\xc3\x28', 'tail'),
                           (b'\xf4\x90\x80\x80', 'range'), (b'\xc0\x80', 'overlong')):
            if n + len(tail) <= 1024:
                assert m.utf8_reason(s + tail) == want and ref_reason(s + tail) == want, (n, tail)
                assert m.utf8_reason(t + tail) == want, (n, tail)
        q = s + b'\xf0\x9f\x98\x80' if n <= 1020 else s
        assert m.char_lengths(q) == (1,) * n + ((4,) if n <= 1020 else ())
        assert m.char_reason(s) == 'extra' if n > 1 else m.char_reason(s) == 'ok'
        assert m.ascii_reason(s) == 'ok' and m.ascii_reason(s[:-1] + b'\x80') == 'nonascii'
    assert run('utf8_reason', b'a' * 2048) == E('utf8_reason', 'bad_value:value.length')
    big = bytes(range(0x80, 0xC0)) * 17
    assert len(big) == 1088 and run('utf8_reason', big) == E('utf8_reason', 'bad_value:value.length')
CORPUS = []
for _fn in NAMES:
    CORPUS.append((_fn, (None,), 'bad_type:value'))
for _fn in BYTES_FNS:
    CORPUS.append((_fn, (b'a' * 1025,), 'bad_value:value.length'))
for _fn in ('decode_utf8', 'char_lengths'):
    CORPUS.append((_fn, (b'\xff',), 'bad_value:value.utf8'))
for _fn in ('encoded_length', 'encode_codepoint'):
    CORPUS.append((_fn, (-1,), 'bad_value:value.codepoint'))
CORPUS = [tuple(c) for c in CORPUS]
IMPORTS = [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]
NAMESPACE = (['find_spec', '_REG', 'make_fail', 'SCOPE', 'NOT_CLAIMED', 'CLAIMS', 'ADJACENT'] +
             list(PRIVATE) + list(NAMES))
CALLS = [(fn, (SAMPLE[fn],), (None,)) for fn in NAMES]


def drive(mod, pfx):
    for fn, args, want in CORPUS:
        got = run(fn, *args, mod=mod)
        assert got == ('raise', pfx + fn + ':' + want), (fn, args, got)


def test_corpus_reaches_every_refusal_code():
    codes = set(c[2] for c in CORPUS)
    assert codes == {'bad_type:value', 'bad_value:value.length', 'bad_value:value.utf8', 'bad_value:value.codepoint'}
    drive(m, PFX)


def test_registry_absent_uses_local_fallback(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh()
    assert mod.make_fail.__module__ == mod.__name__
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert run('utf8_reason', 1, mod=mod) == ('raise', 'P235:utf8_reason:bad_type:value')


def test_registry_present_is_used_by_every_function(mp):
    fake = types.ModuleType(REG)
    fake.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE:%s:%s' % (name, code))))
    mp.setitem(sys.modules, REG, fake)
    mod = fresh()
    assert mod.make_fail is fake.make_fail
    for fn in NAMES:
        assert run(fn, None, mod=mod) == ('raise', 'FAKE:%s:bad_type:value' % fn)


def test_registry_guard_foreign_name_never_consults_find_spec(mp):
    real = builtins.__import__
    spied = []
    err = ModuleNotFoundError('foreign', name='some.other.module')

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda name: spied.append(name) or object())
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ModuleNotFoundError) as e:
        fresh()
    assert e.value is err and spied == []


def test_registry_guard_registry_name_with_spec_found_is_reraised(mp):
    real = builtins.__import__
    spied = []
    err = ModuleNotFoundError('inner', name=REG)

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda name: spied.append(name) or object())
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ModuleNotFoundError) as e:
        fresh()
    assert e.value is err and spied == [REG]


@pytest.mark.parametrize('nm', [REG, 'some.other.module'])
def test_import_error_is_not_a_module_not_found_error(mp, nm):
    real = builtins.__import__
    err = ImportError('x', name=nm)

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda n: None)
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ImportError) as e:
        fresh()
    assert e.value is err


@pytest.mark.parametrize('world', ['absent', 'present', 'foreign', 'registry_raise'])
def test_import_log_and_namespace_on_every_path(mp, world):
    real = builtins.__import__
    seen = []
    spied = []
    err = ModuleNotFoundError('x', name=('some.other.module' if world == 'foreign' else REG))
    fake = types.ModuleType(REG)
    fake.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE')))

    def spy(name):
        spied.append(name)
        return None if world == 'absent' else object()

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == fresh.__defaults__[0]:
            seen.append((n, tuple(fromlist or ()), level))
        if n == REG and world in ('foreign', 'registry_raise'):
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, fake if world == 'present' else None)
    mp.setattr(importlib.util, 'find_spec', spy)
    mp.setattr(builtins, '__import__', hook)
    if world in ('foreign', 'registry_raise'):
        with pytest.raises(ModuleNotFoundError) as e:
            fresh()
        assert e.value is err
        assert seen == IMPORTS
        assert spied == ([] if world == 'foreign' else [REG])
        return
    mod = fresh()
    assert seen == IMPORTS
    assert spied == ([REG] if world == 'absent' else [])
    names = sorted(k for k in vars(mod) if not (k.startswith('__') and k.endswith('__')))
    assert names == sorted(NAMESPACE)
    del seen[:]
    for fn, good, bad in CALLS:
        for args in (good, bad):
            try:
                getattr(mod, fn)(*args)
            except ValueError:
                pass
    assert seen == []



def test_failure_prefix_is_p235_when_the_fallback_is_bound():
    if m.make_fail.__module__ == m.__name__:
        assert PFX == 'P235:'
    assert PFX.endswith(':') and 'x:c' not in PFX



def test_fallback_failer_world_has_no_imports_one_success_and_every_refusal(mp):
    real = builtins.__import__
    seen = []
    name = 'b1267_fallback_world'

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == name:
            seen.append((n, tuple(fromlist or ()), level))
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(builtins, '__import__', hook)
    mod = fresh(name)
    assert mod.make_fail.__module__ == name
    assert seen == IMPORTS
    del seen[:]
    drive(mod, 'P235:')
    assert seen == []
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert seen == []


def test_every_refusal_goes_through_the_failer_call_site(mp):
    class Stop(ValueError):
        pass

    def make(name):
        def fail(code):
            raise Stop(name + ':' + code)
        return fail
    fake = types.ModuleType(REG)
    fake.make_fail = make
    mp.setitem(sys.modules, REG, fake)
    mod = fresh('b1267_site_world')
    sites = set()
    for fn, args, want in CORPUS:
        with pytest.raises(Stop) as e:
            getattr(mod, fn)(*args)
        assert str(e.value) == fn + ':' + want, (fn, args)
        frames = [f for f in traceback.extract_tb(e.value.__traceback__) if f.filename == mod.__file__]
        assert frames[-1].line.strip().startswith('fail(')
        sites.add(frames[-1].lineno)
    src = inspect.getsource(mod).split('\n')
    all_sites = {i + 1 for i, line in enumerate(src) if line.strip().startswith('fail(') and 'def ' not in line}
    assert sites == all_sites, sorted(all_sites - sites)


@pytest.fixture(autouse=True)
def _module_never_imports_at_call_time(monkeypatch):
    real = builtins.__import__
    seen = []

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == m.__name__:
            seen.append((n, tuple(fromlist or ()), level))
        return real(n, g, l, fromlist, level)
    monkeypatch.setattr(builtins, '__import__', hook)
    yield
    assert seen == []


def test_fallback_failer_functions_carry_no_docstring(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh('b1267_doc_world')
    assert mod.make_fail.__doc__ is None
    assert mod.make_fail('x').__doc__ is None
    assert mod.make_fail.__name__ == 'make_fail' and mod.make_fail('x').__name__ == 'fail'


def _world(mp, exc_factory, spec_result, register=None):
    real = builtins.__import__
    spied = []
    err = exc_factory() if exc_factory else None

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG and err is not None:
            raise err
        return real(n, g, l, fromlist, level)

    def spy(name):
        spied.append(name)
        return spec_result
    mp.setitem(sys.modules, REG, register if register is not None else None)
    mp.setattr(importlib.util, 'find_spec', spy)
    mp.setattr(builtins, '__import__', hook)
    try:
        mod = fresh()
    except BaseException as e:
        return ('raised', e, err), spied
    return ('loaded', mod, err), spied


_FAKE = types.ModuleType(REG)
_FAKE.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE:%s:%s' % (name, code))))
GUARD_WORLDS = [
    ('absent', lambda: ModuleNotFoundError('absent', name=REG), None, 'fallback', 1),
    ('foreign_found', lambda: ModuleNotFoundError('inner', name=REG), object(), 'raise', 1),
    ('spec_false', lambda: ModuleNotFoundError('inner', name=REG), False, 'raise', 1),
    ('spec_empty_tuple', lambda: ModuleNotFoundError('inner', name=REG), (), 'raise', 1),
    ('foreign_mnf_name', lambda: ModuleNotFoundError('foreign', name='some.other.module'), None, 'raise', 0),
    ('name_x', lambda: ModuleNotFoundError('x', name='x'), None, 'raise', 0),
    ('name_none', lambda: ModuleNotFoundError('none'), None, 'raise', 0),
    ('name_prefix', lambda: ModuleNotFoundError('prefix', name='app.modules.instinct_doc'), None, 'raise', 0),
    ('name_longer', lambda: ModuleNotFoundError('longer', name=REG + '.sub'), None, 'raise', 0),
    ('name_upper', lambda: ModuleNotFoundError('upper', name=REG.upper()), None, 'raise', 0),
    ('import_error', lambda: ImportError('ie', name=REG), None, 'raise', 0),
    ('named_import_error', lambda: ImportError('ie', name='some.other.module'), None, 'raise', 0),
    ('present', None, None, 'present', 0),
]


@pytest.mark.parametrize('label,factory,spec,outcome,calls', GUARD_WORLDS, ids=[w[0] for w in GUARD_WORLDS])
def test_find_spec_call_count_and_outcome_per_world_is_an_exact_table(mp, label, factory, spec, outcome, calls):
    got, spied = _world(mp, factory, spec, _FAKE if outcome == 'present' else None)
    assert len(spied) == calls and spied == [REG] * calls, label
    if outcome == 'raise':
        assert got[0] == 'raised' and got[1] is got[2], label
    elif outcome == 'fallback':
        assert got[0] == 'loaded' and got[1].make_fail.__module__ == got[1].__name__, label
    else:
        assert got[0] == 'loaded' and got[1].make_fail is _FAKE.make_fail, label




def _envdir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(m.__file__))))


def test_child_process_in_isolated_mode_gives_the_same_answers():
    code = r"""
import sys
sys.path.insert(0, ENVDIR)
import app.modules.instinct_doc.p235_concepts_batch1272_utf8 as m
print(m.utf8_reason(b'a\xc3\xa9'), m.char_reason(b'\xf0\x9f\x98\x80'), m.lead_reason(b'\xc0'), m.codepoint_reason(0xD800),
      m.encode_codepoint(0x20AC), m.decode_utf8(b'\xe2\x82\xac'), m.char_lengths(b'a\xc3\xa9'), m.encoded_length(0x10000))
""".replace('ENVDIR', repr(_envdir()))
    want = "ok ok overlong surrogate b'\\xe2\\x82\\xac' (8364,) (1, 2) 4"
    for env in (None, {'PYTHONHASHSEED': '7'}):
        kw = {} if env is None else {'env': env}
        out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25, **kw)
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip() == want


def _rt(s):
    out = ''
    for ch in s:
        out = (out + ch)[0:len(out) + 1]
    assert out == s and (len(s) == 1 or out is not s)
    return out


def _rtb(b):
    out = b''
    for i in range(len(b)):
        out = (out + b[i:i + 1])[0:len(out) + 1]
    assert out == b and (len(b) == 1 or out is not b)
    return out


def test_guard_name_compare_uses_value_equality_with_runtime_built_registry_name(mp):
    real = builtins.__import__
    spied = []
    regname = _rt(REG)
    assert regname == REG and regname is not REG
    err = ModuleNotFoundError('inner', name=regname)

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda name: spied.append(name) or object())
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ModuleNotFoundError) as e:
        fresh()
    assert e.value is err and spied == [REG]


def _wrap_ok(mp):
    for name in ('_scan', '_lead', '_cp_reason'):
        real = getattr(m, name)

        def w(*a, _real=real):
            out = _real(*a)
            if type(out) is tuple and out[0] == 'ok':
                return (_rt('ok'),) + tuple(out[1:])
            if out == 'ok':
                return _rt('ok')
            return out
        mp.setattr(m, name, w)


def test_internal_ok_propagation_compares_by_value_with_runtime_built_ok(mp):
    inputs = [b'', b'A', b'\xc3\xa9', b'\xe2\x82\xac', b'\xf0\x9f\x98\x80', b'\xc0\x80', b'\xff', b'\xc3', b'\xed\xa0\x80', b'A\x80']
    ints = [0, 65, 0x7FF, 0xD800, 0x10FFFF, 0x110000, -1]
    want = [[run(f, s) for f in BYTES_FNS] for s in inputs] + [[run(f, c) for f in INT_FNS] for c in ints]
    _wrap_ok(mp)
    got = [[run(f, s) for f in BYTES_FNS] for s in inputs] + [[run(f, c) for f in INT_FNS] for c in ints]
    assert got == want
    assert m.utf8_reason(b'\xc3\xa9') == 'ok' and m.codepoint_reason(65) == 'ok' and m.lead_reason(b'A') == 'ok'


def test_runtime_built_bytes_in_a_dash_b_subprocess_with_purged_pycache():
    code = r"""
import sys
sys.path.insert(0, ENVDIR)
def rt(b):
    out = b''
    for i in range(len(b)):
        out = (out + b[i:i + 1])[0:len(out) + 1]
    return out
import app.modules.instinct_doc.p235_concepts_batch1272_utf8 as m
a = rt(b'\xc3\xa9'); e = rt(b'\xe2\x82\xac'); f = rt(b'\xf0\x9f\x98\x80')
print(m.utf8_reason(a + e + f), m.utf8_reason(a + rt(b'\xc3')), m.char_reason(a + a), m.char_reason(f), m.decode_utf8(a + e + f),
      m.char_lengths(a + e + f), m.lead_reason(rt(b'\xf4')), m.tail_reason(rt(b'\xbf')))
""".replace('ENVDIR', repr(_envdir()))
    out = subprocess.run([sys.executable, '-B', '-I', '-c', code], capture_output=True, text=True, timeout=25)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == 'ok truncated extra ok (233, 8364, 128512) (2, 3, 4) ok ok'


def test_identity_premises_of_the_is_and_in_survivors_hold_at_runtime():
    # every int the module compares is a length, an octet or an index at most 1024 or a code point;
    # octets and small counts live in the small-int cache, larger values are compared with the ordering operators only
    for b in range(256):
        assert bytes([b])[0] is b
    assert m.utf8_reason(_rtb(b'\xed\xa0\x80')) == 'surrogate' and m.utf8_reason(_rtb(b'\xf4\x90\x80\x80')) == 'range'
    reasons = set()
    rnd = random.Random(5)
    for _ in range(4000):
        v = _junk(rnd)
        reasons.add(m.utf8_reason(v))
        reasons.add(m.char_reason(v))
        reasons.add(m.lead_reason(v))
    reasons.update({m.codepoint_reason(c) for c in (-1, 0, 0xD800, 0x110000)})
    assert {'ok', 'lead', 'overlong', 'surrogate', 'range', 'tail', 'truncated', 'extra', 'empty', 'length', 'negative'} >= reasons
    assert all((r in 'ok') == (r == 'ok') for r in reasons)

DOC_EXACT = 'p235 concepts batch 1272 (rev 0): RFC 3629, UTF-8, a transformation format of ISO 10646, as a grammar over caller-supplied octets: the section 3 sequence lengths and the table of character ranges, the section 3 prohibition of surrogates and of overlong forms, the U+10FFFF maximum, the section 4 ABNF, and an encoder, a decoder and a length reader built on them. Pure functions; no retrieval, no network, no clock, no registries, no codecs. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it follows the RFC 3629 text only and the Unicode Standard is authoritative.\n\nLIVE SOURCES (fetched 2026-10-22; quotes below are verbatim from these files, mechanically matched with whitespace collapsed):\n- RFC 3629 text, rfc-editor (33856 bytes, sha256 a2a3a39457d30420c812f87a38cc2b9194832f6982ef17e619de7d816879d6a6).\n- rfc-editor info page for RFC 3629 (206798 bytes, sha256 126c267614990bbdb4daa2a2f39894f97970624bf8909599016f466710dabbbb): it shows "Obsoletes: 2279", the STD 63 label, and no "Updated by" or "Obsoleted by" entry. RFC 2279 is obsolete and is not followed; CLAIMS current is still False.\n- The full rfc-editor errata index (11775016 bytes, sha256 23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c) contains exactly zero RFC 3629 records (count from errata.json and not independently confirmed), so no erratum is applied or declined.\n\nSOURCED definition (section 3): "In UTF-8, characters from the U+0000..U+10FFFF range (the UTF-16 accessible range) are encoded using sequences of 1 to 4 octets." "The only octet of a "sequence" of one has the higher-order bit set to 0, the remaining 7 bits being used to encode the character number." "In a sequence of n octets, n>1, the initial octet has the n higher-order bits set to 1, followed by a bit set to 0." "The following octet(s) all have the higher-order bit set to 1 and the following bit set to 0, leaving 6 bits in each to contain bits from the character to be encoded."\nSOURCED table (section 3): "0000 0000-0000 007F | 0xxxxxxx" "0000 0080-0000 07FF | 110xxxxx 10xxxxxx" "0000 0800-0000 FFFF | 1110xxxx 10xxxxxx 10xxxxxx" "0001 0000-0010 FFFF | 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx" "It is important to note that the rows of the table are mutually exclusive, i.e., there is only one valid way to encode a given character."\nSOURCED surrogates and invalid sequences (section 3): "The definition of UTF-8 prohibits encoding character numbers between U+D800 and U+DFFF, which are reserved for use with the UTF-16 encoding form (as surrogate pairs) and do not directly represent characters." "Implementations of the decoding algorithm above MUST protect against decoding invalid sequences." "a naive implementation may decode the overlong UTF-8 sequence C0 80 into the character U+0000, or the surrogate pair ED A1 8C ED BE B4 into U+233B4." "the CESU-8 encoding of those characters is NOT valid UTF-8."\nSOURCED ABNF (section 4): "UTF8-octets = *( UTF8-char )" "UTF8-char = UTF8-1 / UTF8-2 / UTF8-3 / UTF8-4" "UTF8-1 = %x00-7F" "UTF8-2 = %xC2-DF UTF8-tail" "UTF8-3 = %xE0 %xA0-BF UTF8-tail / %xE1-EC 2( UTF8-tail ) / %xED %x80-9F UTF8-tail / %xEE-EF 2( UTF8-tail )" "UTF8-4 = %xF0 %x90-BF 2( UTF8-tail ) / %xF1-F3 3( UTF8-tail ) / %xF4 %x80-8F 2( UTF8-tail )" "UTF8-tail = %x80-BF" "NOTE -- The authoritative definition of UTF-8 is in [UNICODE]. This grammar is believed to describe the same thing Unicode describes, but does not claim to be authoritative."\n\nDECISIONS AND NOT_CLAIMED:\n1. Input domain. Octet inputs are caller-supplied bytes values; code point inputs are caller-supplied ints. A str, a bytearray, a memoryview, a list or a bool is a type error. Byte order marks, the Unicode Standard, normalization, UTF-16 and UTF-32, CESU-8, modified UTF-8, ISO 10646 versions, MIME charset labels, RFC 2279 and every section other than 3 and 4 are NOT_CLAIMED. A byte order mark is just the octets EF BB BF here.\n2. Grammar. An octet string is valid when it matches UTF8-octets of section 4; the empty string is valid (the star allows zero characters). The module reads the ABNF exactly: UTF8-2 leads are C2 to DF; UTF8-3 leads are E0 to EF with the second octet limited for E0 (A0 to BF) and ED (80 to 9F); UTF8-4 leads are F0 to F4 with the second octet limited for F0 (90 to BF) and F4 (80 to 8F); every other octet of a sequence is a UTF8-tail 80 to BF.\n3. Reason codes (OURS naming of the section 3 and 4 failures). lead: an octet that cannot start a sequence (80 to BF, a stray tail, or F8 to FF). overlong: a lead C0 or C1, or a second octet below the E0 and F0 limits (the C0 80 example of section 3, and the longer forms of the same kind). surrogate: ED followed by A0 to BF (U+D800 to U+DFFF). range: a lead F5 to F7, or F4 followed by 90 to BF (above U+10FFFF). tail: an octet that is not 80 to BF where a tail is required. truncated: the input ends inside a sequence with every octet seen so far fitting the grammar. The first failure from left to right decides. Within one sequence the lead is checked first, then the second octet, then each later tail in order.\n4. Code points. codepoint_reason accepts 0 to 0x10FFFF without 0xD800 to 0xDFFF. A negative value reports negative, a value above 0x10FFFF reports range, a value from 0xD800 to 0xDFFF reports surrogate. The three tests are disjoint.\n5. Caps (OURS, all raising): _LEN_CAP 1024 octets per bytes input, checked after the type and before any content check; the cap is an input-size limit, not a statement about UTF-8. Code point inputs have no cap.\n6. Outputs (OURS reports). decode_utf8 returns a tuple of ints, one per character, from the section 3 decoding bit layout. char_lengths returns a tuple of the sequence lengths in octets, one per character. encoded_length returns 1, 2, 3 or 4 from the table. encode_codepoint returns the bytes of the one valid encoding. All four raise bad_value on invalid input (value.utf8 for the octet inputs, value.codepoint for the int inputs).\n\nFUNCTIONS, in this order: utf8_reason, ascii_reason, char_reason, lead_reason, tail_reason, codepoint_reason, encoded_length, encode_codepoint, decode_utf8, char_lengths. Reason functions return the string "ok" or a reason; the others return the values named in decision 6.\n\nREASONS, in check order (the first failure decides):\n- utf8_reason: bad_type:value (raise), bad_value:value.length (raise); then left to right per character: lead, overlong, surrogate, range, tail, truncated; ok.\n- ascii_reason: bad_type:value (raise), bad_value:value.length (raise); then nonascii (an octet above 7F); ok.\n- char_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, then the reasons of utf8_reason for the first character only, then extra (octets after the first character); ok.\n- lead_reason: bad_type:value (raise), bad_value:value.length (raise); then length (not exactly one octet), then lead (80 to BF or F8 to FF), overlong (C0 or C1), range (F5 to F7); ok (00 to 7F or C2 to F4).\n- tail_reason: bad_type:value (raise), bad_value:value.length (raise); then length (not exactly one octet), then tail (not 80 to BF); ok.\n- codepoint_reason: bad_type:value (raise); then negative, range, surrogate; ok.\n- encoded_length: bad_type:value (raise), bad_value:value.codepoint (raise).\n- encode_codepoint: bad_type:value (raise), bad_value:value.codepoint (raise).\n- decode_utf8: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.utf8 (raise).\n- char_lengths: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.utf8 (raise).\n\nOUTPUT ORDER: reason strings are the exact codes listed above; decode_utf8 and char_lengths list the characters in input order.\n'
SCOPE_EXACT = 'RFC 3629 over caller-supplied octets: the section 3 sequence lengths and character ranges, the surrogate and overlong prohibitions, the U+10FFFF maximum, the section 4 ABNF, and an encoder, a decoder and a length reader. Pure functions; no retrieval, no network, no clock, no registries, no codecs.'
NOT_CLAIMED_EXACT = ('standard', 'authority', 'certification', 'currency', 'completeness', 'the Unicode Standard', 'byte order marks and normalization', 'UTF-16, UTF-32, CESU-8 and modified UTF-8', 'ISO 10646 versions', 'MIME charset labels', 'RFC 2279')
ADJACENT_EXACT = ('RFC 2279 (obsoleted by RFC 3629, per the info page; not followed here)', 'RFC 2234 (ABNF, the grammar notation the RFC cites; not re-derived here)', 'The Unicode Standard (named authoritative by RFC 3629 sections 3 and 4; not read here)')


def test_header_and_constants_exact_text():
    assert m.__doc__ == DOC_EXACT
    assert m.SCOPE == SCOPE_EXACT
    assert m.NOT_CLAIMED == NOT_CLAIMED_EXACT
    assert m.ADJACENT == ADJACENT_EXACT
    assert m.CLAIMS == {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False}
    assert all(type(v) is bool for v in m.CLAIMS.values())
    assert m._REG == 'app.modules.instinct_doc.p235_concepts_registry'



def test_every_digit_split_boundary_of_the_encoder_matches_the_codec():
    # the encoder splits by 64, 4096 and 262144: check every multiple of each divisor and its neighbours
    seen = set()
    for d in (64, 4096, 262144):
        for k in range(0, 0x110000 // d + 1):
            for delta in (-2, -1, 0, 1, 2):
                c = k * d + delta
                if 0 <= c <= 0x10FFFF and not 0xD800 <= c <= 0xDFFF:
                    seen.add(c)
    assert len(seen) > 50000 and 0x40000 in seen and 0xFFFFF in seen and 0x100000 in seen and 0x3FFFF in seen
    for c in sorted(seen):
        want = chr(c).encode()
        assert m.encode_codepoint(c) == want and m.encoded_length(c) == len(want), c
        assert m.decode_utf8(want) == (c,), c


def test_small_int_identity_premise_holds_for_runtime_built_values():
    # The module compares octets, lengths and loop counters with ==, <, >.
    # Some mutants swap == for `is`; those are equivalent only because CPython
    # keeps one object for every int in -5..256. Build each literal at runtime
    # (no constant folding, no shared literal) and pin that premise.
    for lit in (0, 1, 224, 237, 240, 244, 191, 128):
        built = int(str(lit)[::-1][::-1]) + int('0') * 7
        built2 = sum([lit // 2, lit - lit // 2])
        built3 = len(bytes(lit))
        assert built is built2 and built2 is built3 and built3 == lit
        assert eval(str(lit)) is built


def test_runtime_built_octets_and_lengths_behave_like_the_literals():
    for lead in (224, 237, 240, 244):
        v = bytes([int(str(lead)) + 0, 128 + int('0')])
        w = bytes([sum([lead - 1, 1])])
        assert v[0] is w[0]
        assert m.lead_reason(w) == 'ok'
        assert m.char_reason(v) == m.char_reason(bytes(list(v)))
    one = bytes(len(b'x') + 0 * 5)
    assert len(one) == 1 and m.lead_reason(one) == 'ok'
    assert len(bytes(0)) == 0 and m.char_reason(bytes(0)) == 'empty'
    assert m.char_reason(b'a' * 1024 + b'') == 'extra'
    assert m.tail_reason(bytes(len(b'ab'))) == 'length'


def test_char_reason_extra_branch_cannot_see_a_shorter_input_than_its_char():
    # In char_reason the `len(v) > n` test runs only after a successful scan,
    # which has already checked i + k < len(v) for every tail octet, so
    # n <= len(v) always. Hence `len(v) > n` and `len(v) != n` agree.
    # Executed pin: for every valid char and every cut, a short prefix is
    # never 'ok' or 'extra' and a whole char is 'ok'; trailing junk is 'extra'.
    for cp in (0x41, 0x7F, 0x80, 0x7FF, 0x800, 0xD7FF, 0xE000, 0xFFFF, 0x10000, 0x10FFFF):
        e = chr(cp).encode()
        assert m.char_reason(e) == 'ok'
        for cut in range(1, len(e)):
            assert m.char_reason(e[:cut]) == 'truncated'
        for extra in (b'a', b'\x80', b'\xff', e):
            assert m.char_reason(e + extra) == 'extra'
