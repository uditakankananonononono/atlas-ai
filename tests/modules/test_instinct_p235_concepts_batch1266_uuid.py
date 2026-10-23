"""Tests for p235 concepts batch 1266: RFC 9562 UUID text as a grammar over caller-supplied text. Pure functions over caller data; claims asserted False."""
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

import app.modules.instinct_doc.p235_concepts_batch1266_uuid as m  # noqa: E402
MODPATH = m.__file__


def _prefix():
    spec = importlib.util.spec_from_file_location('b1266_pfx', MODPATH)
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


def fresh(name='b1266_fresh'):
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


G = 'f81d4fae-7dec-11d0-a765-00a0c91e6bf6'
U4 = '123e4567-e89b-42d3-a456-426614174000'
UC = '123E4567-E89B-42D3-A456-426614174000'
NIL = '00000000-0000-0000-0000-000000000000'
MAX = 'FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF'
NAMES = ('uuid_reason', 'groups_reason', 'hexdigits_reason', 'variant_reason', 'version_reason',
         'nil_reason', 'max_reason', 'urn_reason', 'uuid_octets', 'uuid_parts')
PRIVATE = ('_LEN_CAP', '_UUID_LEN', '_URN', '_DASHES', '_HEXVAL', '_check', '_shape', '_variant', '_uuid')
QUOTES = ['UUIDs MAY be represented as binary data or integers.',
          'any given UUID should be represented by the "hex-and-dash" string format consisting of multiple groups of uppercase or lowercase alphanumeric hexadecimal characters separated by single dashes/hyphens.',
          'UUID = 4hexOctet "-" 2hexOctet "-" 2hexOctet "-" 2hexOctet "-" 6hexOctet',
          'hexOctet = HEXDIG HEXDIG',
          'HEXDIG = DIGIT / "A" / "B" / "C" / "D" / "E" / "F"',
          'Note that the alphabetic characters may be all uppercase, all lowercase, or mixed case, as per Section 2.3 of [RFC5234].',
          'urn:uuid:f81d4fae-7dec-11d0-a765-00a0c91e6bf6',
          'The variant field consists of a variable number of the most significant bits of octet 8 of the UUID.',
          'Specifically for UUIDs in this document, bits 64 and 65 of the UUID (bits 0 and 1 of octet 8) MUST be set to 1 and 0 as specified in row 2 of Table 1.',
          'Reserved. Network Computing System (NCS) backward compatibility, and includes Nil UUID as per Section 5.9.',
          'The variant specified in this document.',
          'Reserved. Microsoft Corporation backward compatibility.',
          'Reserved for future definition and includes Max UUID as per Section 5.10.',
          'The version number is in the most significant 4 bits of octet 6 (bits 48 through 51 of the UUID).',
          'Unused.',
          'The Gregorian time-based UUID specified in this document.',
          'Reserved for DCE Security version, with embedded POSIX UUIDs.',
          'The name-based version specified in this document that uses MD5 hashing.',
          'The randomly or pseudorandomly generated version specified in this document.',
          'The name-based version specified in this document that uses SHA-1 hashing.',
          'Reordered Gregorian time- based UUID specified in this document.',
          'Unix Epoch time-based UUID specified in this document.',
          'Reserved for custom UUID formats specified in this document.',
          'Reserved for future definition.',
          'The Nil UUID is special form of UUID that is specified to have all 128 bits set to zero.',
          'The Max UUID is a special form of UUID that is specified to have all 128 bits set to 1.',
          'Note that the Nil UUID value falls within the range of the Apollo NCS variant as per the first row of Table 1 rather than the variant defined by this document.',
          'Note that the Max UUID value falls within the range of the "yet-to-be defined" future UUID variant as per the last row of Table 1 rather than the variant defined by this document.']


def test_header_quotes_are_in_the_header_and_distinct():
    assert len(QUOTES) == len(set(QUOTES)) and len(QUOTES) >= 25
    doc = ' '.join(m.__doc__.split())
    for qt in QUOTES:
        assert qt in doc, qt


def test_header_quotes_are_verbatim_in_the_pinned_rfc_text_when_present():
    path = os.environ.get('RFC9562_TXT')
    if not path or not os.path.exists(path):
        pytest.skip('RFC text not supplied')
    with open(path, 'rb') as fh:
        raw = fh.read()
    assert hashlib.sha256(raw).hexdigest() == '041870106b8701d9fa9261dcbc1679a6b7ab18cb179b37b69d7232431eac8042'
    dec = raw.decode('utf-8')
    text = ' '.join(dec.split())
    tab = ' '.join(dec.replace('|', ' ').split())
    for qt in QUOTES:
        assert qt in text or qt in tab, qt


def test_header_names_errata_sources_and_functions():
    doc = m.__doc__
    for eid in ('7929', '7931', '7955', '7958', '8288', '8695'):
        assert 'EID ' + eid in doc
    for sha in ('041870106b8701d9fa9261dcbc1679a6b7ab18cb179b37b69d7232431eac8042',
                '53035114a616a89ca8b5fd55efc5756398a817df71b88c41f6324998e66d8e8b',
                '23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c'):
        assert sha in doc
    assert '"Obsoletes (1)" RFC 4122' in doc
    assert 'not independently confirmed' in doc and 'exactly six RFC 9562 records' in doc
    for fn in NAMES:
        assert fn in doc
    assert doc.startswith('p235 concepts batch 1266 (rev 0): RFC 9562')


def test_module_imports_and_source_bans():
    tree = ast.parse(_read(MODPATH))
    imps = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert len(imps) == 2
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in ('re', 'ord', 'chr', 'uuid', 'binascii', 'hashlib', 'random', 'secrets', 'time', 'datetime', 'int'):
            raise AssertionError('forbidden name referenced: %s' % node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('ord', 'chr', 'bin', 'hex', 'open', 'eval', 'exec', 'int'):
            raise AssertionError('forbidden call: %s' % node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'v':
                raise AssertionError('str method on input: %s' % node.func.attr)
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


class _Hostile(str):
    pass


def _mkhostile():
    class MM(type):
        def __eq__(self, other):
            return True

    class S(str, metaclass=MM):
        pass
    return S


@pytest.mark.parametrize('fn', NAMES)
def test_every_argument_is_an_exact_type_by_identity(fn):
    bad = [None, 1, True, False, 0, b'0', bytearray(b'0'), ['a'], ('a',), {'a'}, {'a': 1}, 3.5, _Hostile(G), _mkhostile()(G)]
    for b in bad:
        assert run(fn, b) == E(fn, 'bad_type:value'), (fn, b)


def test_len_cap_at_cap_and_cap_plus_one_on_every_function():
    for fn in NAMES:
        assert run(fn, 'a' * 257) == E(fn, 'bad_value:value.length'), fn
        assert run(fn, G + 'a' * 221) == E(fn, 'bad_value:value.length'), fn
        assert run(fn, 'a' * 2048) == E(fn, 'bad_value:value.length'), fn
    assert run('uuid_reason', 'a' * 256) == ('ok', 'length')
    assert run('uuid_reason', 'a' * 255) == ('ok', 'length')
    assert run('groups_reason', 'a' * 256) == ('ok', 'length')
    assert run('hexdigits_reason', 'a' * 256) == ('ok', 'length')
    assert run('variant_reason', 'a' * 256) == ('ok', 'uuid.length')
    assert run('version_reason', 'a' * 256) == ('ok', 'uuid.length')
    assert run('nil_reason', 'a' * 256) == ('ok', 'uuid.length')
    assert run('max_reason', 'a' * 256) == ('ok', 'uuid.length')
    assert run('urn_reason', 'a' * 256) == ('ok', 'prefix')
    assert run('urn_reason', 'urn:uuid:' + 'a' * 247) == ('ok', 'uuid.length')
    assert run('urn_reason', 'urn:uuid:' + 'a' * 248) == E('urn_reason', 'bad_value:value.length')
    assert run('uuid_octets', 'a' * 256) == E('uuid_octets', 'bad_value:value.uuid')
    assert run('uuid_parts', 'a' * 256) == E('uuid_parts', 'bad_value:value.uuid')


# ---- independent oracle: a regex fullmatch for the ABNF and bit arithmetic for the fields ----
_HEXRE = '[0-9A-Fa-f]'
_UUIDRE = re.compile(_HEXRE + '{8}-' + _HEXRE + '{4}-' + _HEXRE + '{4}-' + _HEXRE + '{4}-' + _HEXRE + '{12}')
_HEXSET = set('0123456789abcdefABCDEF')


def o_shape(s, dashes=True, digits=True):
    if len(s) != 36:
        return 'length'
    for k in range(36):
        c = s[k]
        if k in (8, 13, 18, 23):
            if dashes and c != '-':
                return 'dash'
        elif digits and c not in _HEXSET:
            return 'hexdig'
    return 'ok'


def o_nib(s, k):
    return int(s[k], 16)


def o_variant(s):
    n = o_nib(s, 19)
    b = format(n, '04b')
    if b[0] == '0':
        return 'ncs'
    if b[:2] == '10':
        return 'rfc9562'
    if b[:3] == '110':
        return 'microsoft'
    return 'future'


def o_all(fn, s):
    if fn == 'uuid_reason':
        return o_shape(s)
    if fn == 'groups_reason':
        return o_shape(s, True, False)
    if fn == 'hexdigits_reason':
        return o_shape(s, False, True)
    if fn == 'urn_reason':
        if s[:9] != 'urn:uuid:' or len(s) < 9:
            return 'prefix'
        r = o_shape(s[9:])
        return 'ok' if r == 'ok' else 'uuid.' + r
    r = o_shape(s)
    if fn in ('uuid_octets', 'uuid_parts'):
        if r != 'ok':
            return ('raise', 'bad_value:value.uuid')
        if fn == 'uuid_octets':
            return tuple(int(s.replace('-', '')[k:k + 2], 16) for k in range(0, 32, 2))
        var = o_variant(s)
        return (var, o_nib(s, 14) if var == 'rfc9562' else -1)
    if r != 'ok':
        return 'uuid.' + r
    var = o_variant(s)
    if fn == 'variant_reason':
        return 'ok' if var == 'rfc9562' else 'variant.' + var
    if fn == 'version_reason':
        if var != 'rfc9562':
            return 'variant'
        n = o_nib(s, 14)
        return {0: 'version.unused', 2: 'version.dce'}.get(n, 'version.future' if n > 8 else 'ok')
    digits = s.replace('-', '')
    if fn == 'nil_reason':
        return 'ok' if set(digits) == {'0'} else 'not_nil'
    if fn == 'max_reason':
        return 'ok' if set(digits.lower()) == {'f'} else 'not_max'


def _cmp(s):
    for fn in NAMES:
        want = o_all(fn, s)
        got = run(fn, s)
        if isinstance(want, tuple) and want and want[0] == 'raise':
            assert got == E(fn, want[1]), (fn, s)
        else:
            assert got == ('ok', want), (fn, s, got, want)


_JUNK = ['g', 'G', 'z', ' ', '-', '--', '\n', '\r', '\t', '\x00', '\x7f', '\u00e9', '\uff10', '\u0660', '\U0001f600', 'x', '_', '+', 'urn:uuid:']
_HEX = '0123456789abcdefABCDEF'


def _gen(rng):
    k = rng.randint(0, 9)
    if k == 0:
        return ''.join(rng.choice(_JUNK + list(_HEX)) for _ in range(rng.randint(0, 50)))
    base = [rng.choice(_HEX) for _ in range(36)]
    for p in (8, 13, 18, 23):
        base[p] = '-'
    s = ''.join(base)
    if k == 1:
        return s
    if k in (2, 3):
        for _ in range(rng.randint(1, 3)):
            p = rng.randrange(len(s))
            s = s[:p] + rng.choice(_JUNK) + s[p + 1:]
        return s
    if k == 4:
        p = rng.randrange(len(s) + 1)
        return s[:p] + rng.choice(_JUNK) + s[p:]
    if k == 5:
        p = rng.randrange(len(s))
        return s[:p] + s[p + 1:]
    if k == 6:
        return 'urn:uuid:' + _gen(rng)
    if k == 7:
        return rng.choice(['', 'urn:uuid:', 'URN:UUID:', 'urn:uuid', 'urn:uuid:urn:uuid:']) + s
    if k == 8:
        return s.upper() if rng.random() < 0.5 else s.lower()
    return s[:19] + rng.choice('01234567') + s[20:]


@pytest.mark.parametrize('seed', [1266, 2661, 6612])
def test_fuzz_against_regex_and_bit_oracles_1200(seed):
    rng = random.Random(seed)
    for _ in range(1200):
        s = _gen(rng)
        if len(s) <= 256:
            _cmp(s)
    for s in ('', '-', G, U4, UC, NIL, MAX):
        _cmp(s)
        assert (_UUIDRE.fullmatch(s) is not None) == (m.uuid_reason(s) == 'ok')


def test_every_variant_and_version_digit_on_all_positions_of_the_fields():
    for vd in _HEX:
        for nd in _HEX:
            s = '12345678-9abc-' + nd + 'def-' + vd + '123-456789abcdef'
            _cmp(s)
    assert m.uuid_parts('12345678-9abc-4def-8123-456789abcdef') == ('rfc9562', 4)
    assert m.uuid_parts('12345678-9abc-4def-7123-456789abcdef') == ('ncs', -1)
    assert m.uuid_parts('12345678-9abc-4def-C123-456789abcdef') == ('microsoft', -1)
    assert m.uuid_parts('12345678-9abc-4def-e123-456789abcdef') == ('future', -1)
    assert m.uuid_parts('12345678-9abc-Fdef-b123-456789abcdef') == ('rfc9562', 15)


def test_every_code_point_through_every_position_of_a_valid_uuid():
    cps = [chr(c) for c in range(0, 0x250)] + ['\u2028', '\uff10', '\u0660', '\U0001f600', '\uffff']
    for k in (0, 7, 8, 9, 13, 14, 18, 19, 23, 24, 35):
        for c in cps:
            s = G[:k] + c + G[k + 1:]
            want = o_shape(s)
            assert m.uuid_reason(s) == want, (k, hex(ord(c)))
            assert (m.groups_reason(s), m.hexdigits_reason(s)) == (o_shape(s, True, False), o_shape(s, False, True))
    for c in cps:
        _cmp(c)
        _cmp(c * 36)


def test_reason_battery_spec_examples_and_edges():
    assert m.uuid_reason(G) == 'ok' and m.uuid_reason(UC) == 'ok' and m.uuid_reason(G.upper()) == 'ok'
    assert m.uuid_reason('F81d4fae-7DEC-11d0-A765-00a0c91E6bf6') == 'ok'
    assert m.uuid_reason('') == 'length' and m.uuid_reason(G[:35]) == 'length' and m.uuid_reason(G + '0') == 'length'
    assert m.uuid_reason(G.replace('-', '', 1)) == 'length'
    assert m.uuid_reason('{' + G + '}') == 'length'
    assert m.uuid_reason(G.replace('-', '_', 1)) == 'dash'
    assert m.uuid_reason('f81d4fae7-dec-11d0-a765-00a0c91e6bf6') == 'dash'
    assert m.uuid_reason('g81d4fae-7dec-11d0-a765-00a0c91e6bf6') == 'hexdig'
    assert m.uuid_reason('f81d4fae-7dec-11d0-a765-00a0c91e6bfg') == 'hexdig'
    assert m.uuid_reason('f81d4fae-7dec-11d0-a765-00a0c91e6bf\u0660') == 'hexdig'
    assert m.uuid_reason(G.replace('a', '-', 1)) == 'hexdig'
    assert m.groups_reason('g81d4fae-7dec-11d0-a765-00a0c91e6bf6') == 'ok'
    assert m.groups_reason('g' * 8 + '-' + 'g' * 4 + '-' + 'g' * 4 + '-' + 'g' * 4 + '-' + 'g' * 12) == 'ok'
    assert m.groups_reason('x' * 36) == 'dash' and m.groups_reason('x' * 35) == 'length'
    assert m.hexdigits_reason('f81d4fae_7dec_11d0_a765_00a0c91e6bf6') == 'ok'
    assert m.hexdigits_reason('f81d4fae_7dec_11d0_a765_00a0c91e6bfg') == 'hexdig'
    assert m.hexdigits_reason('-' * 36) == 'hexdig' and m.hexdigits_reason('a' * 36) == 'ok'
    assert m.variant_reason(U4) == 'ok' and m.variant_reason(G) == 'ok'
    assert m.variant_reason(NIL) == 'variant.ncs' and m.variant_reason(MAX) == 'variant.future'
    assert m.variant_reason('12345678-9abc-4def-c123-456789abcdef') == 'variant.microsoft'
    assert m.variant_reason('12345678-9abc-4def-D123-456789abcdef') == 'variant.microsoft'
    assert m.variant_reason('12345678-9abc-4def-7123-456789abcdef') == 'variant.ncs'
    assert m.variant_reason('12345678-9abc-4def-8123-456789abcdef') == 'ok'
    assert m.variant_reason('12345678-9abc-4def-B123-456789abcdef') == 'ok'
    assert m.variant_reason(G[:35]) == 'uuid.length' and m.variant_reason('g' + G[1:]) == 'uuid.hexdig'
    assert m.variant_reason(G.replace('-', '_', 1)) == 'uuid.dash'
    exp = {'0': 'version.unused', '1': 'ok', '2': 'version.dce', '3': 'ok', '4': 'ok', '5': 'ok', '6': 'ok', '7': 'ok',
           '8': 'ok', '9': 'version.future', 'a': 'version.future', 'B': 'version.future', 'c': 'version.future',
           'D': 'version.future', 'e': 'version.future', 'F': 'version.future'}
    for d, want in exp.items():
        assert m.version_reason('12345678-9abc-' + d + 'def-8123-456789abcdef') == want, d
        assert m.version_reason('12345678-9abc-' + d + 'def-A123-456789abcdef') == want, d
    assert m.version_reason(NIL) == 'variant' and m.version_reason(MAX) == 'variant'
    assert m.version_reason('12345678-9abc-0def-c123-456789abcdef') == 'variant'
    assert m.version_reason('12345678-9abc-2def-7123-456789abcdef') == 'variant'
    assert m.version_reason(G[:35]) == 'uuid.length'
    assert m.nil_reason(NIL) == 'ok' and m.nil_reason(G) == 'not_nil'
    assert m.nil_reason('00000000-0000-0000-0000-000000000001') == 'not_nil'
    assert m.nil_reason('10000000-0000-0000-0000-000000000000') == 'not_nil'
    assert m.nil_reason('00000000-0000-0000-0000-00000000000g') == 'uuid.hexdig'
    assert m.nil_reason('0' * 36) == 'uuid.dash' and m.nil_reason('0' * 35) == 'uuid.length'
    assert m.max_reason(MAX) == 'ok' and m.max_reason(MAX.lower()) == 'ok' and m.max_reason('FfFfFfFf-FfFf-FfFf-FfFf-FfFfFfFfFfFf') == 'ok'
    assert m.max_reason(NIL) == 'not_max' and m.max_reason('FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFE') == 'not_max'
    assert m.max_reason('EFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF') == 'not_max'
    assert m.max_reason('F' * 36) == 'uuid.dash' and m.max_reason('FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFG') == 'uuid.hexdig'
    assert m.urn_reason('urn:uuid:' + G) == 'ok' and m.urn_reason('urn:uuid:' + UC) == 'ok'
    assert m.urn_reason(G) == 'prefix' and m.urn_reason('') == 'prefix' and m.urn_reason('urn:uuid') == 'prefix'
    assert m.urn_reason('URN:UUID:' + G) == 'prefix' and m.urn_reason('urn:uuid;' + G) == 'prefix'
    assert m.urn_reason('urn:uuid:') == 'uuid.length' and m.urn_reason('urn:uuid: ' + G) == 'uuid.length'
    assert m.urn_reason('urn:uuid:' + G + 'a') == 'uuid.length'
    assert m.urn_reason('urn:uuid:' + G.replace('-', '_', 1)) == 'uuid.dash'
    assert m.urn_reason('urn:uuid:g' + G[1:]) == 'uuid.hexdig'
    assert m.urn_reason('urn:uuid:urn:uuid:' + G) == 'uuid.length'
    assert m.uuid_octets(G) == (248, 29, 79, 174, 125, 236, 17, 208, 167, 101, 0, 160, 201, 30, 107, 246)
    assert m.uuid_octets(NIL) == (0,) * 16 and m.uuid_octets(MAX) == (255,) * 16
    assert m.uuid_octets(UC) == m.uuid_octets(UC.lower()) == (18, 62, 69, 103, 232, 155, 66, 211, 164, 86, 66, 102, 20, 23, 64, 0)
    for s in ('', G[:35], G + 'a', 'g' + G[1:], G.replace('-', '_', 1)):
        assert run('uuid_octets', s) == E('uuid_octets', 'bad_value:value.uuid'), s
        assert run('uuid_parts', s) == E('uuid_parts', 'bad_value:value.uuid'), s
    assert m.uuid_parts(G) == ('rfc9562', 1) and m.uuid_parts(U4) == ('rfc9562', 4)
    assert m.uuid_parts(NIL) == ('ncs', -1) and m.uuid_parts(MAX) == ('future', -1)
    assert type(m.uuid_octets(G)) is tuple and all(type(x) is int for x in m.uuid_octets(G))
    assert type(m.uuid_parts(G)) is tuple and type(m.uuid_parts(G)[1]) is int


def test_check_order_conflicting_reason_pairs_including_both_bad():
    bad_dash = G.replace('-', '_', 1)                       # dash at position 8
    bad_hex_first = 'g' + G[1:8] + '_' + G[9:]             # hexdig at 0, dash at 8
    bad_dash_first_hex_late = G[:8] + '_' + G[9:20] + 'g' + G[21:]   # dash at 8, hexdig at 20
    assert m.uuid_reason(bad_hex_first) == 'hexdig' and m.uuid_reason(bad_dash_first_hex_late) == 'dash'
    assert m.groups_reason(bad_hex_first) == 'dash' and m.hexdigits_reason(bad_hex_first) == 'hexdig'
    assert m.groups_reason(bad_dash_first_hex_late) == 'dash' and m.hexdigits_reason(bad_dash_first_hex_late) == 'hexdig'
    assert m.hexdigits_reason(bad_dash) == 'ok' and m.groups_reason(bad_dash) == 'dash'
    assert m.uuid_reason(bad_dash + 'a') == 'length' and m.groups_reason(bad_dash + 'a') == 'length'
    assert m.hexdigits_reason('g' + G[1:] + 'a') == 'length'
    assert m.variant_reason('g' + G[1:]) == 'uuid.hexdig'                               # shape beats variant
    assert m.variant_reason('12345678-9abc-4def-c12g-456789abcdef') == 'uuid.hexdig'
    assert m.version_reason('12345678-9abc-0def-c123-45678gabcdef') == 'uuid.hexdig'    # shape beats variant beats version
    assert m.version_reason('12345678-9abc-0def-c123-456789abcdef') == 'variant'
    assert m.version_reason('12345678-9abc-0def-8123-456789abcdef') == 'version.unused'
    assert m.nil_reason('0' * 8 + '-0000-0000-0000-00000000000g') == 'uuid.hexdig'       # shape beats not_nil
    assert m.max_reason('F' * 8 + '-FFFF-FFFF-FFFF-FFFFFFFFFFFg') == 'uuid.hexdig'
    assert m.urn_reason('URN:UUID:g') == 'prefix' and m.urn_reason('urn:uuid:g') == 'uuid.length'   # prefix beats shape
    assert m.urn_reason('urn:uui' + 'd' * 0) == 'prefix' and m.urn_reason('urn:uuid:' + 'g' * 36) == 'uuid.hexdig'
    assert m.urn_reason('urn:uuid:' + 'g' * 8 + '-' + 'g' * 4 + '-' + 'g' * 4 + '-' + 'g' * 4 + '-' + 'g' * 12) == 'uuid.hexdig'


def test_private_constants_exact():
    assert m._LEN_CAP == 256 and m._UUID_LEN == 36 and m._URN == 'urn:uuid:' and m._DASHES == (8, 13, 18, 23)
    assert type(m._LEN_CAP) is int and type(m._UUID_LEN) is int and type(m._DASHES) is tuple
    assert sorted(m._HEXVAL) == sorted(_HEX) and len(m._HEXVAL) == 22
    for c in _HEX:
        assert m._HEXVAL[c] == int(c, 16) and type(m._HEXVAL[c]) is int
    for d in _HEX:
        s = '0' * 19 + d + '0' * 16
        assert m._variant(s) == o_variant(s), d
    assert m._shape(G, True, True) == 'ok' and m._shape(G, True, False) == 'ok' and m._shape(G, False, True) == 'ok'
    assert m._shape('x' * 36, False, False) == 'ok' and m._shape('x' * 35, False, False) == 'length'
    assert m._shape('x' * 36, True, False) == 'dash' and m._shape('x' * 36, False, True) == 'hexdig'
    assert m._shape(G[:8] + 'x' + G[9:], False, True) == 'ok' and m._shape(G[:8] + 'x' + G[9:], True, False) == 'dash'
    assert m._shape('x' + G[1:], True, False) == 'ok' and m._shape('x' + G[1:], False, True) == 'hexdig'


def test_long_inputs_above_the_small_int_cache_and_loop_progress():
    s = G * 7
    assert len(s) == 252 and m.uuid_reason(s) == 'length' and m.groups_reason(s) == 'length' and m.hexdigits_reason(s) == 'length'
    assert m.urn_reason('urn:uuid:' + G * 6) == 'uuid.length'
    big = 'a' * 100 + G
    assert m.uuid_reason(big) == 'length' and m.variant_reason(big) == 'uuid.length'
    for k in range(250, 258):
        s = 'a' * k
        want = ('ok', 'length') if k <= 256 else E('uuid_reason', 'bad_value:value.length')
        assert run('uuid_reason', s) == want, k
    ok = G
    for _ in range(300):
        assert m.uuid_reason(ok) == 'ok' and m.nil_reason(NIL) == 'ok'


def test_first_char_and_template_sweep_against_oracles():
    tmpl = '12345678-9abc-4def-8123-456789abcdef'
    for k in range(36):
        for c in ('0', '9', 'a', 'F', 'g', '-', ' ', '\u0660'):
            _cmp(tmpl[:k] + c + tmpl[k + 1:])
        _cmp(tmpl[:k])
        _cmp(tmpl[:k] + tmpl[k + 1:])
        _cmp(tmpl[:k] + 'a' + tmpl[k:])
    for pre in ('urn:uuid:', 'URN:UUID:', 'urn:uuid', 'urn:', ' urn:uuid:'):
        _cmp(pre + tmpl)
        _cmp(pre)


# ---- registry guard worlds, corpus of refusals ----
def _deep_unused():
    return None


CORPUS = []
for _fn in NAMES:
    CORPUS.append((_fn, (None,), 'bad_type:value'))
    CORPUS.append((_fn, ('a' * 257,), 'bad_value:value.length'))
for _fn in ('uuid_octets', 'uuid_parts'):
    CORPUS.append((_fn, ('a',), 'bad_value:value.uuid'))
CORPUS = [tuple(c) for c in CORPUS]
IMPORTS = [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]
NAMESPACE = (['find_spec', '_REG', 'make_fail', 'SCOPE', 'NOT_CLAIMED', 'CLAIMS', 'ADJACENT'] +
             list(PRIVATE) + list(NAMES))
CALLS = [(fn, (G,), (None,)) for fn in NAMES]


def drive(mod, pfx):
    for fn, args, want in CORPUS:
        got = run(fn, *args, mod=mod)
        assert got == ('raise', pfx + fn + ':' + want), (fn, args, got)


def test_corpus_reaches_every_refusal_code():
    codes = set(c[2] for c in CORPUS)
    assert codes == {'bad_type:value', 'bad_value:value.length', 'bad_value:value.uuid'}
    drive(m, PFX)


def test_registry_absent_uses_local_fallback(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh()
    assert mod.make_fail.__module__ == mod.__name__
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert run('uuid_reason', 1, mod=mod) == ('raise', 'P235:uuid_reason:bad_type:value')


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
    name = 'b1266_fallback_world'

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
    mod = fresh('b1266_site_world')
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
    mod = fresh('b1266_doc_world')
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
    ('spec_eq_none', lambda: ModuleNotFoundError('inner', name=REG), type('EqNone', (), {'__eq__': lambda self, other: True, '__hash__': None})(), 'raise', 1),
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
import inspect
import sys
import traceback
sys.path.insert(0, ENVDIR)
import app.modules.instinct_doc.p235_concepts_batch1266_uuid as m
print(m.uuid_reason(GG), m.version_reason(GG), m.urn_reason('urn:uuid:' + GG), m.uuid_parts(GG), m.nil_reason(GG))
""".replace('ENVDIR', repr(_envdir())).replace('GG', repr(G))
    want = "ok ok ok ('rfc9562', 1) not_nil"
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
    for name in ('_shape', '_uuid'):
        real = getattr(m, name)

        def w(*a, _real=real):
            out = _real(*a)
            if out == 'ok':
                return _rt('ok')
            return out
        mp.setattr(m, name, w)


def test_internal_ok_propagation_compares_by_value_with_runtime_built_ok(mp):
    inputs = [G, G.upper(), '0' * 8 + '-0000-0000-0000-' + '0' * 12, 'f' * 8 + '-ffff-ffff-ffff-' + 'f' * 12,
              G[:-1], G + 'a', G.replace('-', 'x', 1), 'g' + G[1:], U4, UC, 'urn:uuid:' + G]
    fns = [f for f in NAMES if f not in ('uuid_octets', 'uuid_parts')]
    want = [[run(f, s) for f in NAMES] for s in inputs]
    _wrap_ok(mp)
    for s, w in zip(inputs, want):
        assert [run(f, s) for f in NAMES] == w, s
    assert fns and m.uuid_reason(G) == 'ok' and m.version_reason(G) == 'ok' and m.nil_reason(NIL) == 'ok'


def test_runtime_built_strings_in_a_dash_b_subprocess_with_purged_pycache():
    code = r"""
import inspect
import sys
import traceback
sys.path.insert(0, ENVDIR)
def rt(s):
    out = ''
    for ch in s:
        out = (out + ch)[0:len(out) + 1]
    return out
import app.modules.instinct_doc.p235_concepts_batch1266_uuid as m
d = rt('-'); h = rt('f'); u = rt('urn:uuid:')
g = rt(GG)
print(m.uuid_reason(g), m.uuid_reason(g.replace('-', d + d, 1)), m.hexdigits_reason(h * 32), m.groups_reason(h * 36),
      m.max_reason((h * 8) + d + (h * 4) + d + (h * 4) + d + (h * 4) + d + (h * 12)), m.urn_reason(u + g), m.nil_reason(g))
""".replace('ENVDIR', repr(_envdir())).replace('GG', repr(G))
    out = subprocess.run([sys.executable, '-B', '-I', '-c', code], capture_output=True, text=True, timeout=25)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == 'ok length length dash ok ok not_nil'





def test_identity_premises_of_the_is_and_in_survivors_hold_at_runtime():
    # small ints: every int the module compares by value is a cached CPython int, so `is` and `==` agree.
    for x in set(m._HEXVAL.values()) | {m._UUID_LEN, 36, 0, 2, 15}:
        assert x is (x + 1000 - 1000)
    for n in range(0, 257):
        assert len('a' * n) is (n + 1000 - 1000), n
    assert m._LEN_CAP == 256
    # one-character strings are singletons, so `is not '0'` equals `!= '0'` on single characters
    zero = ''.join(['0', '1'])[0:1]
    assert zero == '0' and zero is '0'.__class__('0') and zero is G[0:0] + '0'
    assert all((c in '0') == (c == '0') for c in _HEX + '-_ \u00e9')
    # reason strings: every non-ok reason sorts before 'ok' except the uuid.* prefix and is not a substring of 'ok'
    for r in ('length', 'dash', 'hexdig'):
        assert r < 'ok' and r not in 'ok'
    for r in ('uuid.length', 'uuid.dash', 'uuid.hexdig'):
        assert r > 'ok' and r not in 'ok'
    for c in ('ncs', 'microsoft', 'future'):
        assert c < 'rfc9562' and c not in 'rfc9562'
    for k in range(0, 16):
        assert (k == 0) == (k <= 0)

DOC_EXACT = 'p235 concepts batch 1266 (rev 0): RFC 9562, Universally Unique IDentifiers (UUIDs), as a grammar over caller-supplied text: the section 4 hex-and-dash string format, the section 4.1 variant field, the section 4.2 version field, the section 5.9 Nil UUID, the section 5.10 Max UUID, the urn:uuid: form, and an octet extractor. Pure functions; no retrieval, no network, no clock, no registries, no randomness. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it generates no UUID, computes no timestamp or hash, and validates text form only.\n\nLIVE SOURCES (fetched 2026-10-22; quotes below are verbatim from these files, mechanically matched with whitespace collapsed):\n- RFC 9562 text, rfc-editor (114638 bytes, sha256 041870106b8701d9fa9261dcbc1679a6b7ab18cb179b37b69d7232431eac8042).\n- rfc-editor info page for RFC 9562 (1020001 bytes, sha256 53035114a616a89ca8b5fd55efc5756398a817df71b88c41f6324998e66d8e8b): it lists "Obsoletes (1)" RFC 4122 (not re-derived here; RFC 4122 is obsolete and this module follows RFC 9562 only).\n- The full rfc-editor errata index (11775016 bytes, sha256 23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c) contains exactly six RFC 9562 records (count from errata.json and not independently confirmed): EID 7929, status Verified, type Technical, section B.2 (a variant character in a worked example; this module has no example data); EID 7931, status Reported, type Editorial, section 1 (an introduction wording note); EID 7955, status Verified, type Technical, section 5.1 (a timestamp field layout in the version 1 description; timestamps are NOT_CLAIMED); EID 7958, status Verified, type Technical, section 4.1 (the variant table row for the high bit 0 lists "1-7" where the notes say the range is 0-7, because the Nil UUID has the digit 0 there); EID 8288, status Verified, type Technical, section 6.1 (a maximum-date calculation; timestamps are NOT_CLAIMED); EID 8695, status Verified, type Editorial, section 7.1 (the IANA text says Table 1 where Table 2 is meant; the IANA registry is NOT_CLAIMED).\n\nSOURCED format (section 4): "UUIDs MAY be represented as binary data or integers." "any given UUID should be represented by the "hex-and-dash" string format consisting of multiple groups of uppercase or lowercase alphanumeric hexadecimal characters separated by single dashes/hyphens." "UUID = 4hexOctet "-" 2hexOctet "-" 2hexOctet "-" 2hexOctet "-" 6hexOctet" "hexOctet = HEXDIG HEXDIG" "HEXDIG = DIGIT / "A" / "B" / "C" / "D" / "E" / "F"" "Note that the alphabetic characters may be all uppercase, all lowercase, or mixed case, as per Section 2.3 of [RFC5234]." "urn:uuid:f81d4fae-7dec-11d0-a765-00a0c91e6bf6"\nSOURCED variant (section 4.1): "The variant field consists of a variable number of the most significant bits of octet 8 of the UUID." "Specifically for UUIDs in this document, bits 64 and 65 of the UUID (bits 0 and 1 of octet 8) MUST be set to 1 and 0 as specified in row 2 of Table 1." Table 1 rows (section 4.1): "Reserved. Network Computing System (NCS) backward compatibility, and includes Nil UUID as per Section 5.9." "The variant specified in this document." "Reserved. Microsoft Corporation backward compatibility." "Reserved for future definition and includes Max UUID as per Section 5.10."\nSOURCED version (section 4.2): "The version number is in the most significant 4 bits of octet 6 (bits 48 through 51 of the UUID)." Table 2 rows (section 4.2): "Unused." "The Gregorian time-based UUID specified in this document." "Reserved for DCE Security version, with embedded POSIX UUIDs." "The name-based version specified in this document that uses MD5 hashing." "The randomly or pseudorandomly generated version specified in this document." "The name-based version specified in this document that uses SHA-1 hashing." "Reordered Gregorian time- based UUID specified in this document." "Unix Epoch time-based UUID specified in this document." "Reserved for custom UUID formats specified in this document." "Reserved for future definition."\nSOURCED special forms: "The Nil UUID is special form of UUID that is specified to have all 128 bits set to zero." "The Max UUID is a special form of UUID that is specified to have all 128 bits set to 1." "Note that the Nil UUID value falls within the range of the Apollo NCS variant as per the first row of Table 1 rather than the variant defined by this document." "Note that the Max UUID value falls within the range of the "yet-to-be defined" future UUID variant as per the last row of Table 1 rather than the variant defined by this document."\n\nDECISIONS AND NOT_CLAIMED:\n1. Input domain. Inputs are caller-supplied str values, already decoded. Binary and integer forms, the little-endian Microsoft COM byte order, databases (section 6.13), the curly-brace and OID forms, the version 1 to 8 field layouts and generation rules, the IANA registry, and the RFC 8141 URN rules are NOT_CLAIMED. The string form is read exactly as the ABNF: 36 characters, a dash at positions 8, 13, 18 and 23 (counting from 0), and a HEXDIG at the other 32 positions, in upper, lower or mixed case.\n2. Variant classes (OURS reading of Table 1 with EID 7958). The high bits of the first hex digit of octet 8 give the class: digits 0 to 7 are ncs (the corrected row; the Nil UUID is there), 8 to B are rfc9562, C and D are microsoft, E and F are future (the Max UUID is there). EID 7958 is Verified Technical and its correction is followed here and not independently confirmed.\n3. Version classes (OURS reading of Table 2). Only for variant rfc9562: digit 0 is unused, digit 2 is dce (reserved for DCE Security), digits 1, 3, 4, 5, 6, 7 and 8 are accepted, digits 9 to F are future. This module accepts version 8 as "specified in this document" and does not check that a field layout matches any version.\n4. Nil and Max. nil_reason accepts only the text with all 32 hex digits 0; max_reason accepts only all 32 hex digits F or f. Both require a well-formed UUID string first.\n5. URN form (OURS). urn_reason requires the exact lowercase prefix "urn:uuid:" followed by a well-formed UUID string. Case rules of RFC 8141 for the namespace identifier are NOT_CLAIMED; an uppercase prefix is reported as prefix.\n6. Caps (OURS, all raising): _LEN_CAP 256 characters per input, checked after the type and before any content check; the cap is an input-size limit, not a statement about UUIDs.\n7. uuid_octets and uuid_parts (OURS reports). uuid_octets returns the 16 octet values as a tuple of ints, first octet first, from the text order of the hex digits. uuid_parts returns (variant, version): variant is one of ncs, rfc9562, microsoft, future; version is the int value of the version digit when the variant is rfc9562, and -1 otherwise. Both raise bad_value:value.uuid for text that is not a well-formed UUID string.\n\nFUNCTIONS, in this order: uuid_reason, groups_reason, hexdigits_reason, variant_reason, version_reason, nil_reason, max_reason, urn_reason, uuid_octets, uuid_parts. Reason functions return the string "ok" or a reason; uuid_octets returns a tuple of 16 ints; uuid_parts returns a 2-tuple.\n\nREASONS, in check order (the first failure decides):\n- uuid_reason: bad_type:value (raise), bad_value:value.length (raise); then length (not exactly 36 characters), then left to right by the first offending position: dash (a character other than "-" at position 8, 13, 18 or 23), hexdig (a character that is not a HEXDIG at any other position); ok.\n- groups_reason: bad_type:value (raise), bad_value:value.length (raise); then length, dash (the dash positions only; the other positions are not read); ok.\n- hexdigits_reason: bad_type:value (raise), bad_value:value.length (raise); then length, hexdig (a non-HEXDIG at one of the 32 non-dash positions; the dash positions are not read); ok.\n- variant_reason: bad_type:value (raise), bad_value:value.length (raise); then uuid.<uuid_reason reason>; then variant.ncs, variant.microsoft, variant.future; ok (variant rfc9562).\n- version_reason: bad_type:value (raise), bad_value:value.length (raise); then uuid.<uuid_reason reason>; then variant (the variant is not rfc9562, whichever other class it is); then version.unused, version.dce, version.future; ok.\n- nil_reason: bad_type:value (raise), bad_value:value.length (raise); then uuid.<uuid_reason reason>; then not_nil; ok.\n- max_reason: bad_type:value (raise), bad_value:value.length (raise); then uuid.<uuid_reason reason>; then not_max; ok.\n- urn_reason: bad_type:value (raise), bad_value:value.length (raise); then prefix (fewer than 9 characters or the first 9 characters are not "urn:uuid:"), then uuid.<uuid_reason reason> of the rest; ok.\n- uuid_octets: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.uuid (raise).\n- uuid_parts: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.uuid (raise).\n\nOUTPUT ORDER: reason strings are the exact codes listed above; uuid_parts emits variant first, then version.\n'
SCOPE_EXACT = 'RFC 9562 over caller-supplied text: the hex-and-dash UUID string of section 4, the variant and version fields of sections 4.1 and 4.2, the Nil and Max UUIDs of sections 5.9 and 5.10, the urn:uuid: form, and octet extraction. Pure functions; no retrieval, no network, no clock, no registries, no randomness.'
NOT_CLAIMED_EXACT = ('standard', 'authority', 'certification', 'currency', 'completeness', 'binary and integer forms and byte order', 'field layouts and generation of versions 1 to 8', 'timestamps, hashing and randomness', 'IANA registry', 'RFC 8141 URN case rules', 'curly-brace and OID forms', 'database storage')
ADJACENT_EXACT = ('RFC 4122 (obsoleted by RFC 9562, per the info page; not re-derived here)', 'RFC 5234 (ABNF, the grammar notation the RFC cites; HEXDIG case rule of its section 2.3)', 'RFC 8141 (URN syntax, cited by RFC 9562 for the urn:uuid: form; not re-derived here)')


def test_header_and_constants_exact_text():
    assert m.__doc__ == DOC_EXACT
    assert m.SCOPE == SCOPE_EXACT
    assert m.NOT_CLAIMED == NOT_CLAIMED_EXACT
    assert m.ADJACENT == ADJACENT_EXACT
    assert m.CLAIMS == {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False}
