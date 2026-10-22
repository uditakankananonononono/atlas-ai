import builtins
import importlib
import importlib.util
import itertools
import os
import random
import re
import signal
import resource
import sys
import types

import pytest

sys.path.insert(0, 'backend')
from app.modules.instinct_doc import p235_concepts_batch1230_zoneids as m
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


MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1230_zoneids'
REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODPATH = m.__file__


def _probe():
    try:
        m.is_zone_id(None)
    except ValueError as e:
        s = str(e)
        assert s.endswith('is_zone_id:text-type'), s
        return s[:-len('is_zone_id:text-type')]
    raise AssertionError('probe')


PFX = _probe()


@pytest.fixture(autouse=True)
def _guard():
    old = signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError('guard')))
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    signal.setitimer(signal.ITIMER_REAL, 30)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
        resource.setrlimit(resource.RLIMIT_AS, (soft, hard))


def err(fn, code, *args):
    with pytest.raises(ValueError) as e:
        getattr(m, fn)(*args)
    assert str(e.value) == PFX + fn + ':' + code, (str(e.value), fn, code)


class SubStr(str):
    pass


def test_constants_and_unreserved_pin():
    assert m.ZONE_MIN == 1 and m.ZONE_MAX == 255
    assert m.ADDR_MIN == 1 and m.ADDR_MAX == 45
    assert m.TEXT_MAX == 1024
    assert m.UNRESERVED == 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'
    assert len(m.UNRESERVED) == 66
    assert m._hexval('0') == 0 and m._hexval('9') == 9
    assert m._hexval('A') == 10 and m._hexval('F') == 15
    assert m._hexval('a') == 10 and m._hexval('f') == 15
    assert m._hexval('/') is None and m._hexval(':') is None
    assert m._hexval('@') is None and m._hexval('G') is None
    assert m._hexval('`') is None and m._hexval('g') is None
    assert m._zone_code('') == 'zone-empty'
    assert m._addr_code('') == 'addr-empty'
    assert m._addrz_code('',)[0] == 'empty'
    assert m._literal_code('')[0] == 'empty'
    assert m.SCOPE == 'RFC 6874 section 2 IPv6 zone identifier syntax in address literals' and m.CLAIMS is False
    assert m.NOT_CLAIMED == ('IPv6 address text validation (sibling modules)', 'IPvFuture literals', 'URI parsing outside the bracketed literal', 'zone identifier semantics or interface lookup', 'web browser handling (section 3)')
    assert m.ADJACENT == ('RFC 3986 URI syntax (unreserved and pct-encoded)', 'RFC 4007 IPv6 scoped address architecture', 'RFC 5952 IPv6 text representation (sibling module)', 'RFC 4291 IPv6 addressing', 'RFC 9844 successor work named by erratum 8552')
    names = {k for k in vars(m) if not k.startswith('__')}
    assert names == {'find_spec', 'make_fail', 'SCOPE', 'NOT_CLAIMED', 'ADJACENT', 'CLAIMS', 'ZONE_MIN', 'ZONE_MAX', 'ADDR_MIN', 'ADDR_MAX', 'TEXT_MAX', 'UNRESERVED', '_text', '_unres', '_hexval', '_zone_code', '_addr_code', '_addrz_code', '_literal_code', 'is_zone_id', 'encode_zone_id', 'decode_zone_id', 'split_addrz', 'is_addrz', 'format_addrz', 'split_literal', 'is_literal'}


def _o_zone(t):
    if not (1 <= len(t) <= 255):
        return False
    return re.fullmatch(r'(?:[A-Za-z0-9._~-]|%[0-9A-Fa-f]{2})+', t) is not None


def _o_addrz(t):
    if t == '' or len(t) > 1024:
        return False
    p = t.find('%')
    if p < 0 or t[p:p + 3] != '%25':
        return False
    a = t[:p]
    if not (1 <= len(a) <= 45):
        return False
    for c in a:
        if ord(c) > 127 or c == '[' or c == ']':
            return False
    return _o_zone(t[p + 3:])


def test_zone_oracle_differential():
    rng = random.Random(6874)
    alpha = ['a', 'Z', '0', '-', '.', '_', '~', '%', '4', 'F', 'f', 'G', ']', '[', ':', ' ', '\u00e9', '\x7f', '\x80']
    cases = ['', '%', '%%', '%4', '%41', '%4f', '%4F', '%4G', '%G4', 'a%', 'ab%', 'a%4', 'a%41', 'a%41b', '%41%42', 'a%4~', 'a%41~', 'A', '~', 'a' * 255, 'a' * 256, 'a' * 254 + '%41']
    for _ in range(4000):
        cases.append(''.join(rng.choice(alpha) for _ in range(rng.randrange(0, 9))))
    for t in cases:
        assert m.is_zone_id(t) is _o_zone(t), t
        if m.is_zone_id(t):
            assert m.decode_zone_id(t) is not None


def test_addrz_oracle_differential():
    rng = random.Random(6875)
    alpha = ['a', ':', '1', '%', '2', '5', 'Z', ']', '[', ' ', '\u00e9', '~', 'G', '.']
    cases = ['', 'a', 'a%25b', 'fe80::a%25en1', 'a%b', 'a%2', 'a%2x', '%25a', '%xy', 'a%25', 'a%25b%25c', 'a' * 45 + '%25b', 'a' * 46 + '%25b', 'x' * 1024, 'x' * 1025, '[' + 'a%25b', 'a%25b' + ']']
    for _ in range(4000):
        cases.append(''.join(rng.choice(alpha) for _ in range(rng.randrange(0, 14))))
    for t in cases:
        assert m.is_addrz(t) is _o_addrz(t), t


def test_zone_id_codes_and_boundaries():
    err('is_zone_id', 'text-type', None)
    err('is_zone_id', 'text-type', True)
    err('is_zone_id', 'text-type', SubStr('ab'))
    err('is_zone_id', 'text-type', 5)
    assert m.is_zone_id('') is False
    assert m.is_zone_id('a') is True
    assert m.is_zone_id('a' * 255) is True
    assert m.is_zone_id('a' * 256) is False
    err('decode_zone_id', 'zone-length', 'a' * 256)
    assert m.is_zone_id('%41') is True and m.is_zone_id('%4f') is True
    assert m.is_zone_id('%') is False and m.is_zone_id('%4') is False
    assert m.is_zone_id('%4G') is False and m.is_zone_id('%G4') is False
    assert m.is_zone_id('ab%4G') is False
    assert m.is_zone_id('ab]') is False
    assert m.is_zone_id('%0a') is True
    assert m.is_zone_id('%a0') is True and m.is_zone_id('%A0') is True
    assert m.is_zone_id('a%4~') is False
    assert m.is_zone_id('a%41~') is True
    assert m.is_zone_id('\x7f') is False and m.is_zone_id('\x80') is False
    assert m.is_zone_id('A') is True and m.is_zone_id('~') is True
    assert m.is_zone_id('@') is False and m.is_zone_id('`') is False
    assert m.is_zone_id('/') is False and m.is_zone_id(':') is False
    assert m.is_zone_id('%25') is True and m.is_zone_id('%00') is True
    err('decode_zone_id', 'zone-pc', 'ab%4G')
    err('decode_zone_id', 'zone-pc', 'a%')
    err('decode_zone_id', 'zone-char', 'ab]')
    err('decode_zone_id', 'zone-empty', '')
    err('decode_zone_id', 'zone-type', None)


def test_encode_decode_round_trips():
    err('encode_zone_id', 'raw-type', None)
    err('encode_zone_id', 'raw-type', 25)
    err('encode_zone_id', 'raw-empty', '')
    err('encode_zone_id', 'raw-length', 'a' * 256)
    assert m.encode_zone_id('a' * 255) == 'a' * 255
    assert m.encode_zone_id('eth0') == 'eth0'
    assert m.encode_zone_id('en0-._~') == 'en0-._~'
    assert m.encode_zone_id('a b') == 'a%20b'
    assert m.encode_zone_id('a%b') == 'a%25b'
    assert m.encode_zone_id(']') == '%5D' and m.encode_zone_id('[') == '%5B'
    assert m.encode_zone_id('/') == '%2F'
    assert m.encode_zone_id('\x7f') == '%7F'
    assert m.encode_zone_id('\x00') == '%00'
    assert m.encode_zone_id('\u00e9') == '%C3%A9'
    assert m.encode_zone_id('\u20ac') == '%E2%82%AC'
    assert m.encode_zone_id('\u00e9' * 42) == '%C3%A9' * 42
    err('encode_zone_id', 'zone-length', '\u00e9' * 43)
    err('encode_zone_id', 'zone-length', ' ' * 86)
    assert m.encode_zone_id(' ' * 85) == '%20' * 85
    assert m.decode_zone_id('eth0') == 'eth0'
    assert m.decode_zone_id('a%20b') == 'a b'
    assert m.decode_zone_id('a%25b') == 'a%b'
    assert m.decode_zone_id('%41%42') == 'AB'
    assert m.decode_zone_id('%4a%4A') == 'JJ'
    assert m.decode_zone_id('%00') == '\x00'
    assert m.decode_zone_id('%7f') == '\x7f'
    assert m.decode_zone_id('%C3%A9') == '\xc3\xa9'
    for raw in ('eth0', 'a b', 'a%b', '~A0-._', '\x00\x7f', 'x]y[z', '::1', 'if/0'):
        assert m.decode_zone_id(m.encode_zone_id(raw)) == raw
    assert m.encode_zone_id(m.decode_zone_id('%2f%5d')) == '%2F%5D'
    assert m.encode_zone_id(m.decode_zone_id('%2f%41')) == '%2FA'
    assert m.encode_zone_id(m.decode_zone_id('a%20b')) == 'a%20b'


def test_split_addrz_codes_order_and_boundaries():
    err('split_addrz', 'text-type', None)
    err('is_addrz', 'text-type', None)
    err('split_addrz', 'text-type', SubStr('a%25b'))
    err('split_addrz', 'empty', '')
    err('split_addrz', 'text-length', 'x' * 1025)
    err('split_addrz', 'text-length', '%'.join(['a' * 1024, 'b']))
    err('split_addrz', 'no-separator', 'fe80::1')
    err('split_addrz', 'no-separator', 'x' * 1024)
    err('split_addrz', 'bad-separator', 'a%b')
    err('split_addrz', 'bad-separator', 'a%2')
    err('split_addrz', 'bad-separator', 'a%2x')
    err('split_addrz', 'bad-separator', '%xy')
    assert m.split_addrz('a%253') == ('a', '3')
    err('split_addrz', 'bad-separator', 'a%2G')
    err('split_addrz', 'addr-empty', '%25eth0')
    err('split_addrz', 'addr-length', 'a' * 46 + '%25b')
    assert m.is_addrz('a' * 45 + '%25b') is True
    err('split_addrz', 'addr-ascii', 'ab\u00e9%25c')
    err('split_addrz', 'addr-ascii', '\u00e9%25c')
    err('split_addrz', 'addr-bracket', 'ab]%25c')
    err('split_addrz', 'addr-bracket', '[%25 ')
    err('split_addrz', 'zone-empty', 'a%25')
    err('split_addrz', 'zone-length', 'a%25' + 'b' * 256)
    err('split_addrz', 'zone-char', 'a%25b]')
    err('split_addrz', 'zone-pc', 'a%25b%4')
    assert m.split_addrz('fe80::a%25en1') == ('fe80::a', 'en1')
    assert m.split_addrz('a%25b%25c') == ('a', 'b%25c')
    assert m.split_addrz('::1%250') == ('::1', '0')
    assert m.is_addrz('a%25b') is True
    assert m.is_addrz('') is False
    assert m.is_addrz('a%25b%') is False
    assert m.is_addrz('a\x7f%25b') is True
    assert m.is_addrz('a\x80%25b') is False
    assert m.split_addrz('a%25~') == ('a', '~')


def test_format_addrz_codes_and_round_trip():
    err('format_addrz', 'address-type', None, 'eth0')
    err('format_addrz', 'address-type', 1, 'eth0')
    err('format_addrz', 'addr-empty', '', 'eth0')
    err('format_addrz', 'addr-length', 'a' * 46, 'eth0')
    err('format_addrz', 'addr-ascii', 'a\u00e9', 'eth0')
    err('format_addrz', 'addr-bracket', 'a]', 'eth0')
    err('format_addrz', 'addr-percent', 'a%b', 'eth0')
    err('format_addrz', 'addr-bracket', '[%', 'b')
    err('format_addrz', 'addr-percent', '%[', 'b')
    err('format_addrz', 'zone-type', 'fe80::a', None)
    err('format_addrz', 'zone-empty', 'fe80::a', '')
    err('format_addrz', 'zone-length', 'fe80::a', 'b' * 256)
    err('format_addrz', 'zone-char', 'fe80::a', 'b]')
    err('format_addrz', 'zone-pc', 'fe80::a', 'b%4')
    err('format_addrz', 'addr-bracket', '[', '%')
    err('format_addrz', 'address-type', None, None)
    assert m.format_addrz('fe80::a', 'en1') == 'fe80::a%25en1'
    assert m.format_addrz('::1', '0') == '::1%250'
    assert m.format_addrz('a' * 45, 'b' * 255) == 'a' * 45 + '%25' + 'b' * 255
    for a, z in (('fe80::a', 'en1'), ('::1', '0'), ('a', 'b%25c'), ('x' * 45, '~')):
        assert m.split_addrz(m.format_addrz(a, z)) == (a, z)
        assert m.is_addrz(m.format_addrz(a, z)) is True
        assert m.split_literal(m.format_addrz(a, z).join('[]')) == (a, z)


def test_literal_codes_order_and_round_trip():
    err('split_literal', 'text-type', None)
    err('is_literal', 'text-type', None)
    err('split_literal', 'text-type', SubStr('[a%25b]'))
    err('split_literal', 'empty', '')
    err('split_literal', 'text-length', '[' + 'x' * 1024 + ']')
    err('split_literal', 'text-length', '[' + 'x' * 1023 + ']')
    err('split_literal', 'no-separator', '[' + 'x' * 1022 + ']')
    err('split_literal', 'text-length', 'x' * 1025)
    err('split_literal', 'open-bracket', 'a%25b]')
    err('split_literal', 'open-bracket', ']')
    err('split_literal', 'open-bracket', 'x')
    err('split_literal', 'open-bracket', 'abc')
    err('split_literal', 'open-bracket', 'x[fe80::a%25en1')
    assert m.is_literal('abc') is False
    assert m.is_literal('x[fe80::a%25en1') is False
    err('split_literal', 'close-bracket', '[')
    err('split_literal', 'close-bracket', '[a%25b')
    err('split_literal', 'close-bracket', '[a%25b}x')
    err('split_literal', 'empty', '[]')
    err('split_literal', 'no-separator', '[fe80::1]')
    err('split_literal', 'bad-separator', '[fe80::1%eth0]')
    err('split_literal', 'addr-bracket', '[[a%25b]')
    err('split_literal', 'zone-char', '[a%25b]]')
    err('split_literal', 'zone-char', '[a%25b]x]')
    err('split_literal', 'addr-empty', '[%25eth0]')
    err('split_literal', 'zone-empty', '[a%25]')
    assert m.split_literal('[fe80::a%25en1]') == ('fe80::a', 'en1')
    assert m.split_literal('[a%25b]') == ('a', 'b')
    assert m.is_literal('[a%25b]') is True
    assert m.is_literal('[]') is False
    assert m.is_literal('x') is False
    assert m.is_literal('[a]') is False


def _run_everything():
    zones = ['', 'a', 'eth0', '%41', '%4f', '%', '%4', '%4G', '%G4', 'ab]', 'ab%4G', 'a%', '~', 'A', 'a' * 255, 'a' * 256, ' ' * 86, '\u00e9' * 43, '%25', '%00', 'a%4~', 'a%41~', '\u00e9', '\x7f', '\x80', None, SubStr('ab'), True]
    for t2 in zones:
        for fn in (m.is_zone_id, m.decode_zone_id, m.encode_zone_id):
            try:
                fn(t2)
            except ValueError:
                pass
    addrzs = ['', 'a', 'fe80::1', 'a%25b', 'fe80::a%25en1', 'a%b', 'a%2', 'a%2x', '%xy', '%25eth0', 'a%25', 'a%25b%25c', 'a' * 45 + '%25b', 'a' * 46 + '%25b', 'ab\u00e9%25c', 'ab]%25c', 'a%25b]', 'a%25b%4', 'x' * 1025, 'a\x7f%25b', 'a\x80%25b', None, SubStr('a%25b'), True]
    for t2 in addrzs:
        for fn in (m.is_addrz, m.split_addrz):
            try:
                fn(t2)
            except ValueError:
                pass
    lits = ['', '[]', '[a%25b]', '[fe80::a%25en1]', 'a%25b]', ']', '[', '[a%25b', '[fe80::1]', '[fe80::1%eth0]', '[[a%25b]', '[a%25b]]', '[a%25b]x]', '[%25eth0]', '[a%25]', '[' + 'x' * 1024 + ']', None, SubStr('[a%25b]'), True]
    for t2 in lits:
        for fn in (m.is_literal, m.split_literal):
            try:
                fn(t2)
            except ValueError:
                pass
    pairs = [('fe80::a', 'en1'), ('::1', '0'), ('a', 'b%25c'), (None, 'a'), ('a', None), ('', 'a'), ('a', ''), ('a]', 'b'), ('a%b', 'c'), ('a', 'b]'), ('a' * 46, 'b'), ('a', 'b' * 256), ('a\u00e9', 'b'), ('a', 'b%4')]
    for a2, z2 in pairs:
        try:
            m.format_addrz(a2, z2)
        except ValueError:
            pass
    assert m.split_addrz('fe80::a%25en1') == ('fe80::a', 'en1')
    assert m.split_literal('[fe80::a%25en1]') == ('fe80::a', 'en1')
    assert m.encode_zone_id('a b') == 'a%20b' and m.decode_zone_id('a%20b') == 'a b'
    assert m.format_addrz('::1', '0') == '::1%250'
    assert m._hexval('A') == 10 and m._hexval('g') is None
    assert m._zone_code('') == 'zone-empty' and m._addr_code('') == 'addr-empty'
    assert m._addrz_code('a%25b') == (None, ('a', 'b')) and m._literal_code('[a%25b]') == (None, ('a', 'b'))


def _no_import_hook(*a, **k):
    raise AssertionError('import during call: %r' % (a[:1],))


def _load(name='fresh_1230'):
    spec = importlib.util.spec_from_file_location(name, MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LAST = []
EXPECT_LOG = [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]


def _logged_load(fs=None):
    log = LAST
    del log[:]
    real = builtins.__import__

    def spy(name, globals=None, locals=None, fromlist=(), level=0):
        if globals is not None and globals.get('__name__') == 'fresh_1230':
            log.append((name, tuple(fromlist or ()), level))
        return real(name, globals, locals, fromlist, level)

    calls = []
    real_fs = importlib.util.find_spec
    importlib.util.find_spec = fs if fs is not None else (lambda n, *a, **k: calls.append(n) or real_fs(n, *a, **k))
    _start_import(builtins, spy)
    try:
        mod = _load()
    finally:
        _stop_import()
        importlib.util.find_spec = real_fs
    return mod, log, calls


def test_exact_import_log_and_find_spec_count_in_this_world():
    present = sys.modules.get(REG) is not None
    saved = sys.modules.pop(REG, None)
    try:
        mod, log, calls = _logged_load()
        assert log == EXPECT_LOG
        assert calls == [REG] and mod.make_fail is not None
        with pytest.raises(ValueError) as e:
            mod.make_fail('f')('c')
        assert str(e.value) == 'P235:f:c'
    finally:
        if saved is not None:
            sys.modules[REG] = saved
    if present:
        mod, log, calls = _logged_load()
        assert log == EXPECT_LOG
        assert calls == [] and mod.make_fail is saved.make_fail


def test_absent_registry_fallback_literal_and_reraise_paths():
    saved = sys.modules.get(REG, 'absent')
    try:
        sys.modules[REG] = None
        mod, log, calls = _logged_load(lambda n, *a, **k: None)
        with pytest.raises(ValueError) as e:
            mod.make_fail('f')('c')
        assert str(e.value) == 'P235:f:c'
        with pytest.raises(ValueError) as e:
            mod.is_zone_id(None)
        assert str(e.value) == 'P235:is_zone_id:text-type'
        with pytest.raises(ModuleNotFoundError):
            _logged_load(lambda n, *a, **k: object())
        assert LAST == EXPECT_LOG
        stub = types.ModuleType(REG)
        sys.modules[REG] = stub
        with pytest.raises(ImportError) as e:
            _logged_load()
        assert not isinstance(e.value, ModuleNotFoundError)

        for other in ('app', 'aaa_other', 'app.modules.instinct_doc', 'zzz_other'):
            class Loader:
                def create_module(self, spec):
                    return None

                def exec_module(self, module):
                    raise ModuleNotFoundError('inner', name=other)

            class Finder:
                def find_spec(self, name, path=None, target=None):
                    if name == REG:
                        return importlib.util.spec_from_loader(name, Loader())

            sys.modules.pop(REG, None)
            sys.meta_path.insert(0, Finder())
            try:
                with pytest.raises(ModuleNotFoundError) as e:
                    _logged_load(lambda n, *a, **k: None)
                assert e.value.name == other
                assert LAST == EXPECT_LOG
            finally:
                sys.meta_path.pop(0)
        good = types.ModuleType(REG)
        good.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('X:%s:%s' % (name, code))))
        sys.modules[REG] = good
        mod, log, calls = _logged_load()
        assert calls == [] and mod.make_fail is good.make_fail
        with pytest.raises(ValueError) as e:
            mod.is_zone_id(1)
        assert str(e.value) == 'X:is_zone_id:text-type'
    finally:
        if saved == 'absent':
            sys.modules.pop(REG, None)
        else:
            sys.modules[REG] = saved


def test_no_import_on_any_call_path():
    real = builtins.__import__
    _start_import(builtins, _no_import_hook)
    try:
        _run_everything()
        assert m.split_addrz('a%25b') == ('a', 'b')
        assert m.is_literal('[fe80::a%25en1]') is True
    finally:
        _stop_import()


def test_no_import_at_any_line_and_every_line_reached():
    import ast
    with open(MODPATH) as fh:
        src = fh.read()
    tree = ast.parse(src)
    want = {}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef):
            lines = set()
            for n in ast.walk(fn):
                if isinstance(n, ast.stmt) and n is not fn:
                    lines.add(n.lineno)
            want[fn.name] = lines
    hit = set()
    real = builtins.__import__

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != MODPATH:
            return None
        if event == 'line':
            hit.add((frame.f_code.co_name, frame.f_lineno))
        return tracer

    _start_import(builtins, _no_import_hook)
    sys.settrace(tracer)
    try:
        _run_everything()
        assert m.split_addrz('fe80::a%25en1') == ('fe80::a', 'en1')
        assert m.is_literal('[a%25b]') is True
        assert m.is_zone_id('%41') is True and m.is_zone_id('%4G') is False
        assert m.encode_zone_id('a b') == 'a%20b' and m.decode_zone_id('a%20b') == 'a b'
    finally:
        sys.settrace(None)
        _stop_import()
    missing = []
    for name, lines in want.items():
        for ln in sorted(lines):
            if (name, ln) not in hit:
                missing.append((name, ln))
    assert missing == []
    assert set(want) == {'_text', '_unres', '_hexval', '_zone_code', '_addr_code', '_addrz_code', '_literal_code', 'is_zone_id', 'encode_zone_id', 'decode_zone_id', 'split_addrz', 'is_addrz', 'format_addrz', 'split_literal', 'is_literal'}


STATIC_CODES = {'_text': ['text-type'], 'encode_zone_id': ['raw-type', 'raw-empty', 'raw-length', 'zone-length'], 'decode_zone_id': ['zone-type', '<zcode>'], 'split_addrz': ['<code>'], 'format_addrz': ['address-type', '<acode>', 'zone-type', '<zcode>'], 'split_literal': ['<code>']}


def test_ast_every_f_site_codes():
    import ast
    with open(MODPATH) as fh:
        tree = ast.parse(fh.read())
    got = {}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef):
            sites = []
            for n in ast.walk(fn):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'f':
                    a = n.args[0]
                    sites.append(a.value if isinstance(a, ast.Constant) else '<' + ast.unparse(a) + '>')
            if sites:
                got[fn.name] = sites
    assert got == STATIC_CODES
    assert sum(len(v) for v in got.values()) == 13


def test_cap_before_work_tracemalloc_pins():
    import tracemalloc
    n = 2000000
    big = 'a' * n
    big_e = '\u00e9' * n
    cases = (('split_addrz', (big,), 'text-length'), ('split_addrz', (big_e,), 'text-length'), ('split_literal', (big,), 'text-length'), ('split_literal', ('[' + big,), 'text-length'), ('encode_zone_id', (big,), 'raw-length'), ('decode_zone_id', (big,), 'zone-length'), ('format_addrz', (big, 'a'), 'addr-length'), ('format_addrz', ('a', big), 'zone-length'))
    for fn, args, code in cases:
        tracemalloc.start()
        try:
            with pytest.raises(ValueError) as e:
                getattr(m, fn)(*args)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert str(e.value) == PFX + fn + ':' + code
        assert peak < 20000, (fn, peak)
    tracemalloc.start()
    try:
        assert m.is_zone_id(big) is False and m.is_addrz(big) is False and m.is_literal(big) is False and m.is_addrz(big_e) is False
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 20000, peak


DOC = 'b1230 RFC 6874 section 2: IPv6 zone identifiers in address literals.\n\nSource: RFC 6874 (Carpenter, Cheshire, Hinden, February 2013), section 2\n(Specification). In a URI an IPv6 address literal sits between square\nbrackets, and "This document specifies how a <zone_id> can be appended to\nthe address." Because a bare percent sign must be escaped in a URI, the\nzone separator is the three character sequence %25, so the scoped address\nfe80::a%en1 appears as [fe80::a%25en1]. The grammar keeps the address\nrule unchanged: "the existing syntax of IPv6address is retained, and a\nzone identifier may be added optionally to any literal address." The two\nrules added are \'ZoneID = 1*( unreserved / pct-encoded )\' and\n\'IPv6addrz = IPv6address "%25" ZoneID\', with unreserved and pct-encoded\nimported from the URI syntax: unreserved is the 66 ASCII letters, digits\nand the four characters - . _ ~, and a pct-encoded triplet is a percent\nsign followed by two hexadecimal digits, accepted in either case and\nemitted uppercase. On scope: "URIs including a ZoneID are to be\ninterpreted only in the context of the host at which they originate,\nsince the ZoneID is of local significance only."\nErrata: five exist for RFC 6874 in the errata data used; all are named\nhere. 3630 and 3632 (Rejected, Technical, section 3) and 3631 and 3633\n(Rejected, Technical, section 4) concern browser handling and\nintermediary removal of zone identifiers; sections 3 and 4 are not\nimplemented, so these are outside the implemented section and none is\napplied. 8552 (Verified, Technical, GLOBAL) records that the Updates\nrelationship to the URI syntax was found unimplementable and points to\nRFC 9844; it corrects no section 2 grammar text, so the implemented\nsyntax stands as published and the erratum is documented but not applied\nto the grammar.\nOURS design choices (not sourced from the RFC): the IPv6 address part is\nan opaque token here (nonempty, ASCII, no percent sign and no square\nbrackets, at most ADDR_MAX characters); its validation is owned by the\nIPv6 text form sibling modules and is NOT implemented. ZONE_MAX 255 and\nTEXT_MAX 1024 are implementation bounds; the RFC sets no length limit on\na ZoneID. encode_zone_id percent-encodes non-ASCII raw characters as\nUTF-8 byte triplets and decode_zone_id is a byte level decode, so exact\nround trips are pinned for ASCII raw text only. The P235 error codes and\ntheir check order are ours. SOURCED: the %25 separator, the ZoneID\ngrammar with at least one element, the unreserved set of 66 characters,\nthe pct-encoded triplet of a percent sign and two hexadecimal digits, the\nsquare bracket delimiters of the literal form, and ADDR_MAX 45, the\nlength of the longest textual address form.\nErrors raise ValueError P235:<name>:<code>.\n'


def test_whole_module_docstring_literal_and_ascii():
    assert m.__doc__ == DOC
    for p in (MODPATH, __file__):
        with open(p, 'rb') as fh:
            assert fh.read().isascii()
    assert '\\' not in m.__doc__
    assert 'five exist for RFC 6874' in m.__doc__
    assert '8552' in m.__doc__ and '9844' in m.__doc__ and '3630' in m.__doc__ and '3633' in m.__doc__
    assert 'ZONE_MAX' in m.__doc__ and 'not applied' in m.__doc__
    assert 'OURS' in m.__doc__ and 'SOURCED' in m.__doc__
