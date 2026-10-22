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
from app.modules.instinct_doc import p235_concepts_batch1220_hostnames as m
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


MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1220_hostnames'
REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODPATH = m.__file__


def _probe():
    try:
        m.is_hlabel(None)
    except ValueError as e:
        s = str(e)
        assert s.endswith('is_hlabel:text-type'), s
        return s[:-len('is_hlabel:text-type')]
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


def run(fn, *args):
    try:
        return getattr(m, fn)(*args)
    except ValueError as e:
        assert str(e).startswith(PFX + fn + ':'), str(e)
        return 'ERR:' + str(e)[len(PFX + fn + ':'):]


HLABELRE = re.compile('[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\\Z')


def o_hlabel(t):
    return HLABELRE.match(t) is not None


def o_numeric(t):
    return t != '' and all('0' <= c <= '9' for c in t)


def o_parse(t):
    if len(t) > 255:
        return None
    if t == '':
        return None
    labs = t.split('.')
    if any(not o_hlabel(x) for x in labs):
        return None
    if o_numeric(labs[-1]):
        return None
    return tuple(labs)


def test_constants_tables_and_namespace():
    assert (m.HLABEL_MAX, m.HNAME_MAX) == (63, 255)
    assert m.SCOPE == 'RFC 1123 section 2.1 host name syntax on the RFC 952 hostname grammar' and m.CLAIMS is False
    assert m.NOT_CLAIMED == ('dotted-decimal IP address forms', 'RFC 952 host table policies', 'the single character name ban', 'name lookup or resolution', 'internationalized names')
    assert m.ADJACENT == ('RFC 952 host table specification', 'RFC 1035 domain name syntax (sibling module)', 'RFC 1034 section 3.5 preferred name syntax', 'RFC 3696 application checks of domain names')
    names = {k for k in vars(m) if not k.startswith('__')}
    assert names == {'find_spec', 'make_fail', 'SCOPE', 'NOT_CLAIMED', 'ADJACENT', 'CLAIMS', 'HLABEL_MAX', 'HNAME_MAX', '_letter', '_digit', '_letdig', '_ldh', '_hlabel_ok', 'is_hlabel', 'all_numeric', '_parse', '_text', 'is_hname', 'split_hname', 'canonical_hname', 'hname_equal'}
    for c in range(0, 256):
        ch = chr(c)
        wl = ('a' <= ch <= 'z') or ('A' <= ch <= 'Z')
        wd = ('0' <= ch <= '9')
        wld = wl or wd
        wh = wld or ch == '-'
        assert m._letter(ch) is wl and m._digit(ch) is wd and m._letdig(ch) is wld and m._ldh(ch) is wh, c
    assert m._hlabel_ok('a') is True and m._hlabel_ok('') is False and m._hlabel_ok('a' * 63) is True and m._hlabel_ok('a' * 64) is False


def test_is_hlabel_all_chars_positions_and_bounds():
    assert m.is_hlabel('a') is True and m.is_hlabel('Z') is True
    assert m.is_hlabel('9') is True and m.is_hlabel('0') is True
    assert m.is_hlabel('-') is False and m.is_hlabel('') is False
    assert m.is_hlabel('9a') is True and m.is_hlabel('a9') is True and m.is_hlabel('99') is True
    assert m.is_hlabel('3com') is True and m.is_hlabel('9-9') is True
    assert m.is_hlabel('a-') is False and m.is_hlabel('-a') is False and m.is_hlabel('9-') is False and m.is_hlabel('-9') is False and m.is_hlabel('a_') is False
    assert m.is_hlabel('a--b') is True and m.is_hlabel('a-9') is True and m.is_hlabel('9-b') is True
    assert m.is_hlabel('a' * 62 + '9') is True and m.is_hlabel('a' * 63) is True
    assert m.is_hlabel('9' * 63) is True
    assert m.is_hlabel('a' * 64) is False and m.is_hlabel('9' * 64) is False and m.is_hlabel('a' * 100) is False
    assert m.is_hlabel('a' * 62 + '-') is False
    for c in range(0, 256):
        ch = chr(c)
        wl = ('a' <= ch <= 'z') or ('A' <= ch <= 'Z')
        wd = ('0' <= ch <= '9')
        wld = wl or wd
        wh = wld or ch == '-'
        assert m.is_hlabel(ch) is wld, c
        assert m.is_hlabel('b' + ch) is wld, c
        assert m.is_hlabel('8' + ch) is wld, c
        assert m.is_hlabel(ch + 'b') is wld, c
        assert m.is_hlabel(ch + '8') is wld, c
        assert m.is_hlabel('a' + ch + 'c') is wh, c
        assert m.is_hlabel('ab' + ch + 'cd') is wh, c
    for bad in (None, b'a', 5, ['a'], SubStr('a'), True):
        err('is_hlabel', 'text-type', bad)
        err('all_numeric', 'text-type', bad)
        err('is_hname', 'text-type', bad)
        err('split_hname', 'text-type', bad)
        err('canonical_hname', 'text-type', bad)
        err('hname_equal', 'text-type', bad, 'a')
        err('hname_equal', 'text-type', 'a', bad)


def test_all_numeric_class():
    assert m.all_numeric('') is False
    assert m.all_numeric('0') is True and m.all_numeric('9') is True and m.all_numeric('9' * 63) is True
    assert m.all_numeric('9a') is False and m.all_numeric('a9') is False and m.all_numeric('9-9') is False
    assert m.all_numeric(' 9') is False and m.all_numeric('9 ') is False
    assert m.all_numeric('\u0661') is False and m.all_numeric('\u00b2') is False and m.all_numeric('\u2468') is False
    for c in range(0, 256):
        ch = chr(c)
        wd = ('0' <= ch <= '9')
        assert m.all_numeric(ch) is wd, c
        assert m.all_numeric('1' + ch) is wd, c
        assert m.all_numeric(ch + '1') is wd, c
        assert m.all_numeric('1' + ch + '2') is wd, c


def test_is_hname_vectors_and_bounds():
    assert m.is_hname('') is False
    assert m.is_hname('A.ISI.EDU') is True and m.is_hname('SRI-NIC.ARPA') is True
    assert m.is_hname('a') is True and m.is_hname('a.b') is True and m.is_hname('a.b.c.d.e') is True
    assert m.is_hname('3com') is True and m.is_hname('9abc') is True and m.is_hname('9.9abc') is True
    assert m.is_hname('123') is False and m.is_hname('9') is False and m.is_hname('0') is False
    assert m.is_hname('1.2.3.4') is False and m.is_hname('0.0.0.0') is False and m.is_hname('255.255.255.255') is False
    assert m.is_hname('1.2.3.4a') is True and m.is_hname('1.2.3.a4') is True and m.is_hname('1.2.3.a') is True
    assert m.is_hname('123.a') is True and m.is_hname('a.123') is False and m.is_hname('ok.99') is False
    assert m.is_hname('a.9-9') is True and m.is_hname('a.99-') is False
    assert m.is_hname('.') is False and m.is_hname('a.') is False and m.is_hname('.a') is False and m.is_hname('a..b') is False
    assert m.is_hname('a..') is False and m.is_hname('..') is False and m.is_hname('...a') is False
    assert m.is_hname('-a.b') is False and m.is_hname('a.-b') is False and m.is_hname('a.b-') is False
    assert m.is_hname('a' * 63) is True and m.is_hname('a' * 64) is False
    n255 = '.'.join(['a' * 63] * 4)
    assert len(n255) == 255 and m.is_hname(n255) is True
    n254 = n255[:-1]
    assert len(n254) == 254 and m.is_hname(n254) is True
    n256 = n255 + 'c'
    assert len(n256) == 256 and m.is_hname(n256) is False
    assert m.is_hname('a' * 255) is False and m.is_hname('a' * 256) is False and m.is_hname('a' * 300) is False
    assert m.is_hname('a' * 63 + '.' + 'b' * 63) is True
    assert m.is_hname('a' * 64 + '.b') is False and m.is_hname('a.' + 'b' * 64) is False
    assert m.is_hname('\u00e9.b') is False and m.is_hname('a.b\u00e9') is False
    assert m.is_hname('a.b9') is True and m.is_hname('a.9b') is True


def test_split_hname_codes_order_and_positions():
    S = m.split_hname
    assert S('a') == ('a',) and S('A.ISI.EDU') == ('A', 'ISI', 'EDU')
    assert S('a.b.c') == ('a', 'b', 'c') and type(S('a.b')) is tuple
    assert S('3com') == ('3com',) and S('1.2.3.a4') == ('1', '2', '3', 'a4')
    err('split_hname', 'name-length', 'a' * 256)
    err('split_hname', 'name-length', 'a' * 300)
    err('split_hname', 'name-length', '.'.join(['a' * 63] * 4) + '.b')
    err('split_hname', 'name-length', '9' * 256)
    err('split_hname', 'label-empty', '')
    err('split_hname', 'label-empty', '.')
    err('split_hname', 'label-empty', 'a..b')
    err('split_hname', 'label-empty', 'a.')
    err('split_hname', 'label-empty', '.a')
    err('split_hname', 'label-empty', 'a.b.')
    err('split_hname', 'label-empty', 'ok.99.')
    err('split_hname', 'label-length', 'a' * 64)
    err('split_hname', 'label-length', 'a' * 100)
    err('split_hname', 'label-length', 'ok.' + 'a' * 64)
    err('split_hname', 'label-length', 'a' * 64 + '.ok')
    err('split_hname', 'label-length', 'ok.ok.' + 'a' * 64)
    err('split_hname', 'label-length', 'ok.' + '9' * 64)
    err('split_hname', 'label-invalid', '-a')
    err('split_hname', 'label-invalid', 'a-')
    err('split_hname', 'label-invalid', 'a_b')
    err('split_hname', 'label-invalid', 'ok.-x')
    err('split_hname', 'label-invalid', 'ok.99-')
    err('split_hname', 'label-invalid', 'ok.ok.-x')
    err('split_hname', 'label-invalid', '\u00e9')
    err('split_hname', 'label-invalid', 'ok.\u00e9')
    err('split_hname', 'last-numeric', '9')
    err('split_hname', 'last-numeric', '123')
    err('split_hname', 'last-numeric', '1.2.3.4')
    err('split_hname', 'last-numeric', 'ok.99')
    err('split_hname', 'last-numeric', '9' * 63)
    err('split_hname', 'last-numeric', 'a.2.3.4')
    for pos in range(0, 4):
        pre = '.'.join(['ok'] * pos)
        pre = (pre + '.') if pre else ''
        err('split_hname', 'label-empty', pre + 'a..b')
        err('split_hname', 'label-length', pre + 'zz.' + 'a' * 64)
        err('split_hname', 'label-invalid', pre + 'zz.-x')
        err('split_hname', 'last-numeric', pre + 'zz.77')
    err('split_hname', 'name-length', 'a' * 256 + '.')
    err('split_hname', 'label-empty', ('a' * 63) + '..')
    err('split_hname', 'name-length', '\u00e9' * 256)


def test_canonical_hname_and_hname_equal():
    assert m.canonical_hname('A.ISI.EDU') == 'a.isi.edu'
    assert m.canonical_hname('SRI-NIC.ARPA') == 'sri-nic.arpa' and m.canonical_hname('a') == 'a'
    assert m.canonical_hname('9ABC-dE.F6') == '9abc-de.f6' and m.canonical_hname('3COM') == '3com'
    err('canonical_hname', 'name-length', 'a' * 256)
    err('canonical_hname', 'label-empty', 'a..b')
    err('canonical_hname', 'label-length', 'a' * 64)
    err('canonical_hname', 'label-invalid', '-a')
    err('canonical_hname', 'last-numeric', 'a.9')
    E = m.hname_equal
    assert E('a', 'a') is True and E('9a', '9A') is True
    assert E('A.ISI.EDU', 'a.isi.edu') is True and E('SRI-NIC.ARPA', 'sri-nic.arpa') is True
    assert E('a', 'A') is True and E('Ab9-Cd', 'aB9-cD') is True and E('3COM', '3com') is True
    assert E('a', 'b') is False and E('a.b', 'a.c') is False and E('a.b', 'a.b.c') is False
    assert E('a-a', 'a-A') is True and E('a0', 'A0') is True
    assert E('a', 'a9') is False
    err('hname_equal', 'label-empty', 'a', 'a.')
    err('hname_equal', 'label-invalid', '-a', 'zz')
    err('hname_equal', 'label-empty', 'a.', 'zz')
    err('hname_equal', 'name-length', 'a' * 256, 'zz')
    err('hname_equal', 'last-numeric', 'a.9', 'zz')
    err('hname_equal', 'label-invalid', 'ok', '-a')
    err('hname_equal', 'label-empty', 'ok', 'a.')
    err('hname_equal', 'name-length', 'ok', 'a' * 256)
    err('hname_equal', 'last-numeric', 'ok', 'a.9')
    err('hname_equal', 'label-invalid', '-a', '-b')
    err('hname_equal', 'label-empty', 'a.', 'b.')
    err('hname_equal', 'last-numeric', 'a.9', 'b.8')
    err('hname_equal', 'label-invalid', '-', '.')
    err('hname_equal', 'label-empty', '', '.')
    err('hname_equal', 'label-empty', '', '')
    assert E('a', 'A') is True


def test_oracle_exhaustive_and_random():
    alphabet = ['a', 'Z', '9', '-', '.', ' ', '_', '\u00e9']
    n = 0
    ok = 0
    for length in range(0, 5):
        for t in itertools.product(alphabet, repeat=length):
            s = ''.join(t)
            want = o_parse(s)
            assert m.is_hname(s) is (want is not None), s
            got = run('split_hname', s)
            if want is None:
                assert isinstance(got, str) and got.startswith('ERR:'), s
            else:
                assert got == want, (s, got, want)
                assert m.canonical_hname(s) == '.'.join(want).lower()
                ok += 1
            n += 1
    assert n == sum(8 ** k for k in range(5)) and ok > 50
    rnd = random.Random(1123)
    pool = ['a', 'B', 'z', '0', '9', '-', '.', '..', 'a-b', '9a', 'x' * 63, 'y' * 64, ' ', '_', '\u00e9', 'ok.', '.ok', 'A.ISI.EDU', '99', '']
    ok2 = 0
    for _ in range(6000):
        s = ''.join(rnd.choice(pool) for _ in range(rnd.randint(1, 6)))
        want = o_parse(s)
        assert m.is_hname(s) is (want is not None), s
        got = run('split_hname', s)
        if want is None:
            assert isinstance(got, str) and got.startswith('ERR:'), s
        else:
            assert got == want, (s, got, want)
            assert m.hname_equal(s, s.lower()) is True
            assert m.hname_equal(s, s.upper()) is True
            ok2 += 1
    assert ok2 > 200
    for _ in range(2000):
        a = ''.join(rnd.choice(pool) for _ in range(rnd.randint(1, 4)))
        b = ''.join(rnd.choice(pool) for _ in range(rnd.randint(1, 4)))
        wa, wb = o_parse(a), o_parse(b)
        r = run('hname_equal', a, b)
        if wa is None or wb is None:
            assert isinstance(r, str) and r.startswith('ERR:'), (a, b, r)
        else:
            assert r is (tuple(x.lower() for x in wa) == tuple(x.lower() for x in wb)), (a, b, r)

def _run_everything():
    texts = ['', 'a', 'A.ISI.EDU', '9', '9a', '-a', 'a-', 'a_b', 'a..b', 'a.', '.a', 'a' * 63, 'a' * 64, 'a' * 255, 'a' * 256, 'ok.' + 'a' * 64, 'ok.9b', 'ok.99', 'ok.99-', '1.2.3.4', '1.2.3.a', '3com', '\u00e9', 'a.\u00e9', None, SubStr('a'), True, 'a--b', '.'.join(['a' * 63] * 4), 'x' * 300]
    for t2 in texts:
        for fn in (m.is_hlabel, m.all_numeric, m.is_hname, m.split_hname, m.canonical_hname):
            try:
                fn(t2)
            except ValueError:
                pass
        for t3 in ('a', 'B.C', '9', '', None, 'a..b', 'a.9', 'a' * 256, SubStr('a')):
            try:
                m.hname_equal(t2, t3)
                m.hname_equal(t3, t2)
            except ValueError:
                pass
    m.split_hname('a.b.c')
    m.canonical_hname('A.B')
    m.hname_equal('A.ISI.EDU', 'a.isi.edu')


def _no_import_hook(*a, **k):
    raise AssertionError('import during call: %r' % (a[:1],))


def _load(name='fresh_1220'):
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
        if globals is not None and globals.get('__name__') == 'fresh_1220':
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
            mod.is_hlabel(None)
        assert str(e.value) == 'P235:is_hlabel:text-type'
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
            mod.is_hlabel(1)
        assert str(e.value) == 'X:is_hlabel:text-type'
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
        assert m.split_hname('a.b') == ('a', 'b')
        assert m.hname_equal('A.B', 'a.b') is True
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
        assert m.split_hname('A.ISI.EDU') == ('A', 'ISI', 'EDU')
        assert m.hname_equal('A.ISI.EDU', 'a.isi.edu') is True
        assert m.is_hname('a..b') is False and m.canonical_hname('SRI-NIC.ARPA') == 'sri-nic.arpa'
        assert m.is_hname('1.2.3.4') is False and m.is_hname('3com') is True
    finally:
        sys.settrace(None)
        _stop_import()
    missing = []
    for name, lines in want.items():
        for ln in sorted(lines):
            if (name, ln) not in hit:
                missing.append((name, ln))
    assert missing == []
    assert set(want) == {'_letter', '_digit', '_letdig', '_ldh', '_hlabel_ok', 'is_hlabel', 'all_numeric', '_parse', '_text', 'is_hname', 'split_hname', 'canonical_hname', 'hname_equal'}


STATIC_CODES = {'is_hlabel': ['text-type'], 'all_numeric': ['text-type'], '_text': ['text-type'], 'split_hname': ['<code>'], 'canonical_hname': ['<code>'], 'hname_equal': ['<code_a>', '<code_b>']}


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
    assert sum(len(v) for v in got.values()) == 7


def test_cap_before_work_tracemalloc_pins():
    import tracemalloc
    n = 2000000
    big = 'a' * n
    cases = (('split_hname', (big,), 'name-length'), ('canonical_hname', (big,), 'name-length'), ('canonical_hname', ('\u00e9' * n,), 'name-length'), ('hname_equal', (big, 'a'), 'name-length'), ('hname_equal', ('a', big), 'name-length'), ('split_hname', ('\u00e9' * n,), 'name-length'))
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
    big_e = '\u00e9' * n
    tracemalloc.start()
    try:
        assert m.is_hname(big) is False and m.is_hlabel(big) is False and m.is_hname(big_e) is False
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 20000, peak


DOC = 'b1220 RFC 1123 section 2.1 host name syntax on the RFC 952 hostname grammar.\n\nSource: RFC 1123 (Braden, October 1989), section 2.1 (Host Names and\nNumbers), layered on the RFC 952 (October 1985) hostname grammar\n(hname = name *(dot name); name = letter, then letters digits and hyphens,\nending letter or digit). RFC 1123 changes one rule: "the restriction on the\nfirst character is relaxed to allow either a letter or a digit." On lengths:\n"Host software MUST handle host names of up to 63 characters and SHOULD\nhandle host names of up to 255 characters." RFC 952 adds: "No distinction is\nmade between upper and lower case." The label character rules and the 63\ncharacter label limit are the RFC 1035 label grammar; see the sibling module\nfor RFC 1035, referenced here without any import.\nThe last-label rule: RFC 1123 says a valid host name can never have the\ndotted-decimal form, "since at least the highest-level component label will\nbe alphabetic." Erratum 1081 (Rejected, Technical, section 2.1) proposed\nweakening that to not all-numeric and was rejected; the implemented rule is\nthat the last label must not be all numeric, the task-scoped choice,\nconsistent with the informational statement in RFC 3696 section 2 and weaker\nthan the RFC text. Errata: fourteen exist for RFC 1123 in the errata data\nused; the four touching section 2.1 are named here: 1081 and 1353 (both\nRejected, Technical, section 2.1), 1354 (Verified, Editorial, section 2.1, an\nadded citation to RFC 1034 section 3.5) and 8148 (Verified, Editorial,\nsection 2.1, a corrected cross reference); the two Verified errata change no\nrule and are NOT applied. One erratum exists for RFC 952: 3584 (Verified,\nEditorial, header text): read, NOT applied.\nOURS design choices (not sourced from the RFCs): the empty string and a\ntrailing dot are refused; is_hlabel, is_hname and all_numeric answer False\nfor a bad string and raise only on a non-string argument; the RFC 952\npolicies (24 character table limit, the single character ban, the gateway and\nTAC suffix conventions) are NOT implemented, being host table policy\nsuperseded by the RFC 1123 lengths; the P235 error codes, their check order\n(structural checks label by label, the last-label rule last), and the 63\ncharacter label limit taken from the referenced RFC 1035 grammar. SOURCED:\nthe digit-or-letter start (RFC 1123), the letter-or-digit end and the\nletter-digit-hyphen interior (RFC 952), case-insensitive comparison (RFC\n952), the 255 character host name length (RFC 1123), and the last label not\nall numeric rule as scoped above.\nErrors raise ValueError P235:<name>:<code>.\n'


def test_whole_module_docstring_literal_and_ascii():
    assert m.__doc__ == DOC
    for p in (MODPATH, __file__):
        with open(p, 'rb') as fh:
            assert fh.read().isascii()
    assert '\\' not in m.__doc__
    assert 'fourteen exist for RFC 1123' in m.__doc__
    assert 'One erratum exists for RFC 952: 3584' in m.__doc__
    assert '1081' in m.__doc__ and '1354' in m.__doc__ and '8148' in m.__doc__ and 'NOT applied' in m.__doc__
    assert 'OURS' in m.__doc__ and 'SOURCED' in m.__doc__
