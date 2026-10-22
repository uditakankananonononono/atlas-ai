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
from app.modules.instinct_doc import p235_concepts_batch1192_domainnames as m
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


MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1192_domainnames'
REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODPATH = m.__file__


def _probe():
    try:
        m.is_label(None)
    except ValueError as e:
        s = str(e)
        assert s.endswith('is_label:text-type'), s
        return s[:-len('is_label:text-type')]
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


LABELRE = re.compile('[A-Za-z](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\\Z')


def o_label(t):
    return LABELRE.match(t) is not None


def o_parse(t):
    if len(t) > 253:
        return None
    if t == '':
        return ()
    labs = t.split('.')
    if any(not o_label(x) for x in labs):
        return None
    return tuple(labs)


def test_constants_tables_and_namespace():
    assert (m.LABEL_MAX, m.WIRE_MAX, m.TEXT_MAX) == (63, 255, 253)
    assert m.SCOPE == 'RFC 1035 section 2.3.1 preferred domain name syntax and size limits' and m.CLAIMS is False
    assert m.NOT_CLAIMED == ('the wire format of section 3.1', 'labels outside the preferred syntax', 'the RFC 1123 digit start relaxation', 'name resolution', 'master file syntax')
    assert m.ADJACENT == ('RFC 1034 domain concepts', 'RFC 1123 host name requirements', 'RFC 1035 section 3.1 wire form')
    names = {k for k in vars(m) if not k.startswith('__')}
    assert names == {'find_spec', 'make_fail', 'SCOPE', 'NOT_CLAIMED', 'ADJACENT', 'CLAIMS', 'LABEL_MAX', 'WIRE_MAX', 'TEXT_MAX', '_letter', '_letdig', '_ldh', '_label_ok', 'is_label', '_parse', '_text', 'is_name', 'split_name', 'canonical', 'name_equal'}
    for c in range(0, 256):
        ch = chr(c)
        wl = ('a' <= ch <= 'z') or ('A' <= ch <= 'Z')
        wd = wl or ('0' <= ch <= '9')
        wh = wd or ch == '-'
        assert m._letter(ch) is wl and m._letdig(ch) is wd and m._ldh(ch) is wh, c
    assert m._label_ok('a') is True and m._label_ok('') is False and m._label_ok('a' * 63) is True and m._label_ok('a' * 64) is False


def test_is_label_all_chars_positions_and_bounds():
    assert m.is_label('a') is True and m.is_label('Z') is True
    assert m.is_label('9') is False and m.is_label('-') is False and m.is_label('') is False
    assert m.is_label('a9') is True and m.is_label('aZ') is True and m.is_label('ab') is True
    assert m.is_label('a-') is False and m.is_label('-a') is False and m.is_label('9a') is False and m.is_label('a_') is False
    assert m.is_label('a--b') is True and m.is_label('a-9') is True and m.is_label('a9-b') is True
    assert m.is_label('a' * 62 + '9') is True and m.is_label('a' * 63) is True
    assert m.is_label('a' * 64) is False and m.is_label('a' * 100) is False
    assert m.is_label('a' * 62 + '-') is False
    for c in range(0, 256):
        ch = chr(c)
        wl = ('a' <= ch <= 'z') or ('A' <= ch <= 'Z')
        wd = wl or ('0' <= ch <= '9')
        wh = wd or ch == '-'
        assert m.is_label(ch) is wl, c
        assert m.is_label('b' + ch) is wd, c
        assert m.is_label(ch + 'b') is (wl and wd), c
        assert m.is_label('a' + ch + 'c') is wh, c
        assert m.is_label('ab' + ch + 'cd') is wh, c
    for bad in (None, b'a', 5, ['a'], SubStr('a'), True):
        err('is_label', 'text-type', bad)
        err('is_name', 'text-type', bad)
        err('split_name', 'text-type', bad)
        err('canonical', 'text-type', bad)
        err('name_equal', 'text-type', bad, 'a')
        err('name_equal', 'text-type', 'a', bad)


def test_is_name_vectors_and_bounds():
    assert m.is_name('') is True
    assert m.is_name('A.ISI.EDU') is True and m.is_name('XX.LCS.MIT.EDU') is True and m.is_name('SRI-NIC.ARPA') is True
    assert m.is_name('a') is True and m.is_name('a.b') is True and m.is_name('a.b.c.d.e') is True
    assert m.is_name('.') is False and m.is_name('a.') is False and m.is_name('.a') is False and m.is_name('a..b') is False
    assert m.is_name('a..') is False and m.is_name('..') is False and m.is_name('...a') is False
    assert m.is_name('9.b') is False and m.is_name('a.9b') is False and m.is_name('a.b9') is True
    assert m.is_name('a' * 63) is True and m.is_name('a' * 64) is False
    n253 = '.'.join(['a' * 63, 'a' * 63, 'a' * 63, 'b' * 61])
    assert len(n253) == 253 and m.is_name(n253) is True
    n252 = n253[:-1]
    assert len(n252) == 252 and m.is_name(n252) is True
    n254 = n253 + 'c'
    assert len(n254) == 254 and m.is_name(n254) is False
    assert m.is_name('a' * 254) is False and m.is_name('a' * 300) is False
    assert m.is_name('a' * 63 + '.' + 'b' * 63) is True
    assert m.is_name('a' * 64 + '.b') is False and m.is_name('a.' + 'b' * 64) is False
    assert m.is_name('\u00e9.b') is False and m.is_name('a.b\u00e9') is False


def test_split_name_codes_order_and_positions():
    S = m.split_name
    assert S('') == () and S('a') == ('a',) and S('A.ISI.EDU') == ('A', 'ISI', 'EDU')
    assert S('a.b.c') == ('a', 'b', 'c') and type(S('a.b')) is tuple
    err('split_name', 'name-length', 'a' * 254)
    err('split_name', 'name-length', 'a' * 300)
    err('split_name', 'name-length', '.'.join(['a' * 63] * 4) + '.b')
    err('split_name', 'label-empty', '.')
    err('split_name', 'label-empty', 'a..b')
    err('split_name', 'label-empty', 'a.')
    err('split_name', 'label-empty', '.a')
    err('split_name', 'label-empty', 'a.b.')
    err('split_name', 'label-empty', '..a')
    err('split_name', 'label-length', 'a' * 64)
    err('split_name', 'label-length', 'a' * 100)
    err('split_name', 'label-length', 'ok.' + 'a' * 64)
    err('split_name', 'label-length', 'a' * 64 + '.ok')
    err('split_name', 'label-length', 'ok.ok.' + 'a' * 64)
    err('split_name', 'label-invalid', '9')
    err('split_name', 'label-invalid', '-a')
    err('split_name', 'label-invalid', 'a-')
    err('split_name', 'label-invalid', 'a_b')
    err('split_name', 'label-invalid', 'ok.9b')
    err('split_name', 'label-invalid', 'ok.ok.-x')
    err('split_name', 'label-invalid', '\u00e9')
    err('split_name', 'label-invalid', 'ok.\u00e9')
    for pos in range(0, 4):
        pre = '.'.join(['ok'] * pos)
        pre = (pre + '.') if pre else ''
        err('split_name', 'label-empty', pre + 'a..b')
        err('split_name', 'label-length', pre + 'zz.' + 'a' * 64)
        err('split_name', 'label-invalid', pre + 'zz.9x')
    err('split_name', 'name-length', 'a' * 254 + '.')
    err('split_name', 'label-empty', ('a' * 63) + '..')
    err('split_name', 'name-length', '\u00e9' * 254)


def test_canonical_and_name_equal():
    assert m.canonical('A.ISI.EDU') == 'a.isi.edu' and m.canonical('') == ''
    assert m.canonical('SRI-NIC.ARPA') == 'sri-nic.arpa' and m.canonical('a') == 'a'
    assert m.canonical('aB9-cD.eF') == 'ab9-cd.ef'
    err('canonical', 'name-length', 'a' * 254)
    err('canonical', 'label-empty', 'a..b')
    err('canonical', 'label-length', 'a' * 64)
    err('canonical', 'label-invalid', '9a')
    E = m.name_equal
    assert E('', '') is True and E('a', 'a') is True
    assert E('A.ISI.EDU', 'a.isi.edu') is True and E('XX.LCS.MIT.EDU', 'xx.lcs.mit.edu') is True
    assert E('a', 'A') is True and E('Ab9-Cd', 'aB9-cD') is True
    assert E('a', 'b') is False and E('a.b', 'a.c') is False and E('a.b', 'a.b.c') is False
    err('name_equal', 'label-empty', 'a', 'a.')
    assert E('a-a', 'a-A') is True and E('a0', 'A0') is True
    assert E('', 'a') is False
    err('name_equal', 'label-invalid', '9a', 'zz')
    err('name_equal', 'label-empty', 'a.', 'zz')
    err('name_equal', 'name-length', 'a' * 254, 'zz')
    err('name_equal', 'label-invalid', 'ok', '9a')
    err('name_equal', 'label-empty', 'ok', 'a.')
    err('name_equal', 'name-length', 'ok', 'a' * 254)
    err('name_equal', 'label-invalid', '9a', '9b')
    err('name_equal', 'label-empty', 'a.', 'b.')
    err('name_equal', 'label-invalid', '-', '.')
    err('name_equal', 'label-empty', '', '.')
    assert E('a', 'A') is True


def test_oracle_exhaustive_and_random():
    alphabet = ['a', 'Z', '9', '-', '.', ' ', '_', '\u00e9']
    n = 0
    ok = 0
    for length in range(0, 5):
        for t in itertools.product(alphabet, repeat=length):
            s = ''.join(t)
            want = o_parse(s)
            assert m.is_name(s) is (want is not None), s
            got = run('split_name', s)
            if want is None:
                assert isinstance(got, str) and got.startswith('ERR:'), s
            else:
                assert got == want, (s, got, want)
                assert m.canonical(s) == '.'.join(want).lower()
                ok += 1
            n += 1
    assert n == sum(8 ** k for k in range(5)) and ok > 50
    rnd = random.Random(1035)
    pool = ['a', 'B', 'z', '0', '9', '-', '.', '..', 'a-b', 'x' * 63, 'y' * 64, ' ', '_', '\u00e9', 'ok.', '.ok', 'A.ISI.EDU', '']
    ok2 = 0
    for _ in range(6000):
        s = ''.join(rnd.choice(pool) for _ in range(rnd.randint(1, 6)))
        want = o_parse(s)
        assert m.is_name(s) is (want is not None), s
        got = run('split_name', s)
        if want is None:
            assert isinstance(got, str) and got.startswith('ERR:'), s
        else:
            assert got == want, (s, got, want)
            assert m.name_equal(s, s.lower()) is True
            assert m.name_equal(s, s.upper()) is True
            ok2 += 1
    assert ok2 > 200
    for _ in range(2000):
        a = ''.join(rnd.choice(pool) for _ in range(rnd.randint(1, 4)))
        b = ''.join(rnd.choice(pool) for _ in range(rnd.randint(1, 4)))
        wa, wb = o_parse(a), o_parse(b)
        r = run('name_equal', a, b)
        if wa is None or wb is None:
            assert isinstance(r, str) and r.startswith('ERR:'), (a, b, r)
        else:
            assert r is (tuple(x.lower() for x in wa) == tuple(x.lower() for x in wb)), (a, b, r)


def _run_everything():
    texts = ['', 'a', 'A.ISI.EDU', '9', '-a', 'a-', 'a_b', 'a..b', 'a.', '.a', 'a' * 63, 'a' * 64, 'a' * 254, 'ok.' + 'a' * 64, 'ok.9b', '\u00e9', 'a.\u00e9', None, SubStr('a'), True, 'a--b', 'a' * 253, '.'.join(['a' * 63] * 4), 'x' * 300]
    for t2 in texts:
        for fn in (m.is_label, m.is_name, m.split_name, m.canonical):
            try:
                fn(t2)
            except ValueError:
                pass
        for t3 in ('a', 'B.C', '', None, 'a..b', 'a' * 254, SubStr('a')):
            try:
                m.name_equal(t2, t3)
                m.name_equal(t3, t2)
            except ValueError:
                pass
    m.split_name('a.b.c')
    m.canonical('A.B')
    m.name_equal('A.ISI.EDU', 'a.isi.edu')


def _no_import_hook(*a, **k):
    raise AssertionError('import during call: %r' % (a[:1],))


def _load(name='fresh_1192'):
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
        if globals is not None and globals.get('__name__') == 'fresh_1192':
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
            mod.is_label(None)
        assert str(e.value) == 'P235:is_label:text-type'
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
            mod.is_label(1)
        assert str(e.value) == 'X:is_label:text-type'
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
        assert m.split_name('a.b') == ('a', 'b')
        assert m.name_equal('A.B', 'a.b') is True
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
        assert m.split_name('A.ISI.EDU') == ('A', 'ISI', 'EDU')
        assert m.name_equal('A.ISI.EDU', 'a.isi.edu') is True
        assert m.is_name('a..b') is False and m.canonical('SRI-NIC.ARPA') == 'sri-nic.arpa'
    finally:
        sys.settrace(None)
        _stop_import()
    missing = []
    for name, lines in want.items():
        for ln in sorted(lines):
            if (name, ln) not in hit:
                missing.append((name, ln))
    assert missing == []
    assert set(want) == {'_letter', '_letdig', '_ldh', '_label_ok', 'is_label', '_parse', '_text', 'is_name', 'split_name', 'canonical', 'name_equal'}


STATIC_CODES = {'is_label': ['text-type'], '_text': ['text-type'], 'split_name': ['<code>'], 'canonical': ['<code>'], 'name_equal': ['<code_a>', '<code_b>']}


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
    assert sum(len(v) for v in got.values()) == 6


def test_cap_before_work_tracemalloc_pins():
    import tracemalloc
    n = 2000000
    big = 'a' * n
    cases = (('split_name', (big,), 'name-length'), ('canonical', (big,), 'name-length'), ('canonical', ('\u00e9' * n,), 'name-length'), ('name_equal', (big, 'a'), 'name-length'), ('name_equal', ('a', big), 'name-length'), ('split_name', ('\u00e9' * n,), 'name-length'))
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
        assert m.is_name(big) is False and m.is_label(big) is False and m.is_name(big_e) is False
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 20000, peak


DOC = 'b1192 RFC 1035 section 2.3.1 preferred domain name syntax and size limits.\n\nSource: RFC 1035 (Mockapetris, November 1987), section 2.3.1 (Preferred name\nsyntax) with the size limits of sections 2.3.4 and 3.1. Only the TEXT form of\ndomain names is handled, never the wire form. The RFC says of labels: "They\nmust start with a letter, end with a letter or digit, and have as interior\ncharacters only letters, digits, and hyphen." and "Labels must be 63\ncharacters or less." On case: "That is, two names with the same spelling but\ndifferent case are to be treated as if identical." and "Name servers and\nresolvers must compare labels in a case-insensitive manner (i.e., A=a),\nassuming ASCII with zero parity." The size table gives "names 255 octets or\nless"; section 3.1 makes that the wire length, label octets plus label length\noctets plus the zero root octet, so a text name of n labels and n minus 1\ndots is at most 253 characters.\nTwenty-nine errata exist for RFC 1035 in the errata data used; one touches a\nsection implemented here: 7424 (Verified, Editorial, section 2.3.1, a blank\nline inside a sentence): read, NOT applied, no rule changes. 6264 (Verified,\nEditorial, section 2.2, a grammar typo) is the only other erratum in section\n2: read, NOT applied.\nNo erratum changes the preferred name syntax, the size limits, or the case\nrules implemented here.\nOURS design choices (not sourced from the RFC): the empty string stands for\nthe root domain (the blank alternative of the domain rule); a trailing dot is\nrefused as an empty label; every function validates its arguments before\ncomputing; is_label and is_name answer False for any syntactically bad string\nand raise only on a non-string argument; the P235 error codes and their check\norder; the 253 character text limit derived from the sourced 255 octet wire\nlimit. SOURCED: the letter start, the letter or digit end, the letter digit\nhyphen interior, the 63 character label limit, the 255 octet name limit, and\nASCII case-insensitive comparison with all other codes matching exactly.\nThe digit-start relaxation of RFC 1123 and the any-8-bit labels of section\n3.1 are ADJACENT and not implemented here.\nErrors raise ValueError P235:<name>:<code>.\n'


def test_whole_module_docstring_literal_and_ascii():
    assert m.__doc__ == DOC
    for p in (MODPATH, __file__):
        with open(p, 'rb') as fh:
            assert fh.read().isascii()
    assert '\\' not in m.__doc__
    assert 'Twenty-nine errata exist for RFC 1035' in m.__doc__
    assert '7424 (Verified, Editorial, section' in m.__doc__ and 'NOT applied' in m.__doc__
    assert 'OURS' in m.__doc__ and 'SOURCED' in m.__doc__
