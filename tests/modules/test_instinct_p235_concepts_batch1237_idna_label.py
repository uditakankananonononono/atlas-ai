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
        p235_concepts_batch1237_idna_label as mod)
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


IP = 'idna_label_parse'
IV = 'idna_label_is_valid'

_SUCC_CACHE = None
_REFU_CACHE = None


def _success_corpus():
    global _SUCC_CACHE
    if _SUCC_CACHE is None:
        s = [(IP, ('example',)),
             (IP, ('EXAMPLE',)),
             (IP, ('a',)),
             (IP, ('a-b',)),
             (IP, ('a--b',)),
             (IP, ('abc--d',)),
             (IP, ('xn--bcher-kva',)),
             (IP, ('XN--BCHER-KVA',)),
             (IP, ('xn--a',)),
             (IP, ('xn---a',)),
             (IP, ('xn--0',)),
             (IP, ('0foo',)),
             (IP, ('a' * 63,)),
             (IP, ('xn--' + 'a' * 59,)),
             (IV, ('example',)),
             (IV, ('xn--bcher-kva',)),
             (IV, ('XN--X',))]
        _SUCC_CACHE = s
    return _SUCC_CACHE


def _refusal_corpus():
    global _REFU_CACHE
    if _REFU_CACHE is None:
        r = [(IP, 'bad_type:value', (None,)),
             (IP, 'bad_type:value', (0,)),
             (IP, 'bad_type:value', (b'example',)),
             (IP, 'bad_type:value', (_StrSub('example'),)),
             (IP, 'bad_value:label.length', ('a' * 64,)),
             (IP, 'bad_value:label.length', ('xn--' + 'a' * 60,)),
             (IP, 'bad_value:label', ('',)),
             (IP, 'bad_value:value.charset', ('a b',)),
             (IP, 'bad_value:value.charset', ('a\x7fb',)),
             (IP, 'bad_value:label.char', ('a_b',)),
             (IP, 'bad_value:label.char', ('a.b',)),
             (IP, 'bad_value:label.char', ('a"b',)),
             (IP, 'bad_value:label.fake', ('xn--',)),
             (IP, 'bad_value:label.fake', ('XN--',)),
             (IP, 'bad_value:label.edge', ('-a',)),
             (IP, 'bad_value:label.edge', ('a-',)),
             (IP, 'bad_value:label.edge', ('xn---',)),
             (IP, 'bad_value:label.edge', ('ab--',)),
             (IP, 'bad_value:label.r_ldh', ('ab--cd',)),
             (IP, 'bad_value:label.r_ldh', ('FA--B',))]
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


def test_rfc5890_classification():
    # s2.3.2.2: an NR-LDH label, reported with its parts
    r = m.idna_label_parse('example')
    assert r['label'] == 'example'
    assert r['label_class'] == 'nr_ldh'
    assert r['punycode_part'] is None
    assert r['canonical_text'] == 'example'
    assert r['canonical'] is True
    # s2.3.2.1/s2.3.2.5: an XN-label in A-label shape; the prefix is
    # case independent
    r = m.idna_label_parse('xn--bcher-kva')
    assert r['label_class'] == 'a_label'
    assert r['punycode_part'] == 'bcher-kva'
    assert r['canonical'] is True
    for pre in ('XN--', 'xN--', 'Xn--'):
        r = m.idna_label_parse(pre + 'BCHER-KVA')
        assert r['label_class'] == 'a_label'
        assert r['punycode_part'] == 'BCHER-KVA'
        assert r['canonical_text'] == 'xn--bcher-kva'
        assert r['canonical'] is False
    # s2.3.2: "--" at the third and fourth characters without the
    # "xn--" prefix is R-LDH - not a valid IDNA label
    refuse(IP, 'bad_value:label.r_ldh', 'ab--cd')
    refuse(IP, 'bad_value:label.r_ldh', 'zz--zz')
    # "--" anywhere else is an ordinary NR-LDH label
    assert m.idna_label_parse('a--b')['label_class'] == 'nr_ldh'
    assert m.idna_label_parse('abc--d')['label_class'] == 'nr_ldh'
    assert m.idna_label_parse('abcde--f')['label_class'] == 'nr_ldh'
    # fake A-label: "xn--" with an empty punycode part
    refuse(IP, 'bad_value:label.fake', 'xn--')
    refuse(IP, 'bad_value:label.fake', 'XN--')


def test_ldh_base_rules():
    # s2.3.1: letters, digits, hyphen; whole-set membership both sides
    ldh = set('-0123456789'
              'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
              'abcdefghijklmnopqrstuvwxyz')
    for ch in ldh:
        assert m.idna_label_parse('a' + ch + 'b')
    for i in range(0x21, 0x7F):
        ch = chr(i)
        if ch not in ldh:
            refuse(IP, 'bad_value:label.char', 'a' + ch + 'b')
    # no leading or trailing hyphen
    assert m.idna_label_parse('a-b-c')
    refuse(IP, 'bad_value:label.edge', '-a')
    refuse(IP, 'bad_value:label.edge', 'a-')
    refuse(IP, 'bad_value:label.edge', '-')
    refuse(IP, 'bad_value:label.edge', '--')
    refuse(IP, 'bad_value:label.edge', '--a')
    refuse(IP, 'bad_value:label.edge', 'a--')
    # length flanks: 1 and 63 accepted, 64 refused
    assert m.idna_label_parse('a')
    assert m.idna_label_parse('a' * 63)
    refuse(IP, 'bad_value:label.length', 'a' * 64)
    refuse(IP, 'bad_value:label.length', 'a' * 100)
    # digits are fine anywhere inside
    assert m.idna_label_parse('0foo')
    assert m.idna_label_parse('0')


def test_a_label_shape():
    # the punycode part is 1..59 characters via the 63-octet cap
    assert m.idna_label_parse('xn--a')['punycode_part'] == 'a'
    assert m.idna_label_parse('xn--' + 'a' * 59)
    refuse(IP, 'bad_value:label.length', 'xn--' + 'a' * 60)
    # the whole XN-label must conform to LDH, prefix included
    refuse(IP, 'bad_value:label.char', 'xn--a_b')
    refuse(IP, 'bad_value:label.char', 'xn--a.b')
    refuse(IP, 'bad_value:label.edge', 'xn--a-')
    refuse(IP, 'bad_value:label.edge', 'xn---')
    # a punycode part may itself hold hyphens and digits
    r = m.idna_label_parse('xn---a')
    assert r['label_class'] == 'a_label'
    assert r['punycode_part'] == '-a'
    assert m.idna_label_parse('xn--0')['punycode_part'] == '0'
    assert m.idna_label_parse('xn--a-b-9')['punycode_part'] == 'a-b-9'
    # "xn" without the full prefix is no XN-label
    assert m.idna_label_parse('xn')['label_class'] == 'nr_ldh'
    assert m.idna_label_parse('xn-a')['label_class'] == 'nr_ldh'
    assert m.idna_label_parse('xna--b')['label_class'] == 'nr_ldh'


def test_canonical_rules():
    r = m.idna_label_parse('EXAMPLE')
    assert r['canonical_text'] == 'example'
    assert r['canonical'] is False
    r = m.idna_label_parse('XN--BCHER-KVA')
    assert r['canonical_text'] == 'xn--bcher-kva'
    assert r['canonical'] is False
    for t in ('example', 'xn--bcher-kva', 'a--b', '0'):
        assert m.idna_label_parse(t)['canonical'] is True
    # the canonical text always re-parses, canonically, same class
    for t in ('EXAMPLE', 'XN--BCHER-KVA', 'A-B', 'Xn--A'):
        r1 = m.idna_label_parse(t)
        r2 = m.idna_label_parse(r1['canonical_text'])
        assert r2['canonical'] is True
        assert r2['label_class'] == r1['label_class']
        assert r2['canonical_text'] == r1['canonical_text']
        if r1['punycode_part'] is not None:
            assert r2['punycode_part'] == r1['punycode_part'].lower()
    # output field types are exact
    r = m.idna_label_parse('example')
    assert type(r['canonical']) is bool
    assert type(r['label_class']) is str


def test_result_shape_and_freshness():
    a = m.idna_label_parse('xn--bcher-kva')
    assert set(a) == {'label', 'label_class', 'punycode_part',
                      'canonical_text', 'canonical'}
    a['label_class'] = 'MUTATED'
    b = m.idna_label_parse('xn--bcher-kva')
    assert b['label_class'] == 'a_label'
    assert a is not b


def test_header_refusals():
    for fn_name, code, args in _refusal_corpus():
        refuse(fn_name, code, *args)


def test_exact_types_refuse():
    for bad in (None, 0, True, 5.5, b'example', ['example'],
                (1,), _StrSub('example')):
        refuse(IP, 'bad_type:value', bad)
        assert m.idna_label_is_valid(bad) is False


def test_label_length_cap():
    # the RFC 63-octet cap: exactly at it accepted, one past refused,
    # for both classes
    ok = 'a' * 63
    assert len(ok) == 63
    m.idna_label_parse(ok)
    assert len(ok + 'a') == 64
    refuse(IP, 'bad_value:label.length', ok + 'a')
    refuse(IP, 'bad_value:label.length', 'xn--' + 'a' * 60)


def test_refusal_order():
    # type before length before the empty label
    refuse(IP, 'bad_type:value', 0)
    refuse(IP, 'bad_value:label.length', 'a' * 63 + ' ')
    refuse(IP, 'bad_value:label', '')
    # the charset gate before the LDH class
    refuse(IP, 'bad_value:value.charset', 'a b')
    refuse(IP, 'bad_value:value.charset', 'a\x7f')
    refuse(IP, 'bad_value:label.char', 'a_b')
    # the LDH class before the hyphen edges
    refuse(IP, 'bad_value:label.char', '-~')
    # the fake A-label ahead of the hyphen-edge rule it also trips
    refuse(IP, 'bad_value:label.fake', 'xn--')
    # the hyphen-edge rule before the R-LDH reservation
    refuse(IP, 'bad_value:label.edge', 'ab--')
    # the R-LDH reservation last
    refuse(IP, 'bad_value:label.r_ldh', 'ab--cd')


def test_is_valid_returns_exact_bool():
    v = m.idna_label_is_valid('example')
    assert v is True and type(v) is bool
    assert m.idna_label_is_valid('xn--bcher-kva') is True
    assert m.idna_label_is_valid('ab--cd') is False
    assert m.idna_label_is_valid('xn--') is False
    assert m.idna_label_is_valid(None) is False
    assert m.idna_label_is_valid(0) is False


def test_constants_pinned_whole():
    assert m._MAX_LABEL_LENGTH == 63
    assert m._ACE_PREFIX == 'xn--'
    assert m._ALPHANUM == frozenset(
        '0123456789'
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        'abcdefghijklmnopqrstuvwxyz')
    assert len(m._ALPHANUM) == 62
    assert m._LDH_CHARS == m._ALPHANUM | frozenset('-')
    assert len(m._LDH_CHARS) == 63


def test_function_docstrings_pinned_exact():
    assert m.idna_label_parse.__doc__ is None
    assert m.idna_label_is_valid.__doc__ == (
        'True iff idna_label_parse(text) would succeed.')


def test_module_namespace_is_pinned():
    names = set(vars(m))
    assert names == {
        '__name__', '__doc__', '__package__', '__loader__',
        '__spec__', '__file__', '__cached__', '__builtins__',
        'find_spec', 'make_fail',
        '_MAX_LABEL_LENGTH', '_ACE_PREFIX', '_ALPHANUM',
        '_LDH_CHARS', 'idna_label_parse', 'idna_label_is_valid'}


def test_parse_is_deterministic_and_consistent():
    rng = random.Random(1237)
    alphabet = 'aZ09-._~xnX \x00\x7f'
    for _ in range(400):
        blob = ''.join(rng.choice(alphabet)
                       for _ in range(rng.randrange(0, 20)))
        try:
            r1 = m.idna_label_parse(blob)
        except ValueError:
            assert m.idna_label_is_valid(blob) is False
        else:
            assert m.idna_label_is_valid(blob) is True
            assert m.idna_label_parse(blob) == r1
            # the canonical text always re-parses, canonically
            r2 = m.idna_label_parse(r1['canonical_text'])
            assert r2['canonical'] is True
            assert r2['canonical_text'] == r1['canonical_text']
            assert r2['label_class'] == r1['label_class']
            if r1['punycode_part'] is None:
                assert r2['punycode_part'] is None
            else:
                assert (r2['punycode_part']
                        == r1['punycode_part'].lower())
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
        mod = types.ModuleType('fresh_b1237')
        with pytest.raises(ModuleNotFoundError):
            exec(compile(src, 'fresh_b1237', 'exec'), mod.__dict__)
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
            ('import no_such_dep_xyz_1237\n', 'ModuleNotFoundError'),
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
        mod = types.ModuleType('fresh_b1237_spy')
        exec(compile(src, 'fresh_b1237_spy', 'exec'), mod.__dict__)
    finally:
        _stop_import()
        _iu.find_spec = real_find_spec
    assert calls == [REG], calls
    # the fallback engaged and works
    assert mod.idna_label_is_valid('xn--bcher-kva') is True
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        assert str(e) == 'P235:x:c'
    else:
        raise AssertionError('fallback make_fail did not raise')




def test_battery_rev0_pins():
    # the RFC 63-octet cap flanks, both classes
    assert m.idna_label_parse('a' * 63)
    refuse(IP, 'bad_value:label.length', 'a' * 64)
    assert m.idna_label_parse('xn--' + '9' * 59)
    refuse(IP, 'bad_value:label.length', 'xn--' + '9' * 60)
    # the charset gate flanks: 0x21 and 0x7E reach the LDH class,
    # 0x20/0x7F/0x00 die at the gate
    refuse(IP, 'bad_value:label.char', 'a!b')
    refuse(IP, 'bad_value:label.char', 'a~b')
    refuse(IP, 'bad_value:value.charset', 'a b')
    refuse(IP, 'bad_value:value.charset', 'a\x7fb')
    refuse(IP, 'bad_value:value.charset', 'a\x00b')
    # the empty label
    refuse(IP, 'bad_value:label', '')
    # every LDH character accepted mid-label
    for ch in ('-0123456789'
               'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
               'abcdefghijklmnopqrstuvwxyz'):
        assert m.idna_label_parse('a' + ch + 'b')
    # hyphen edges, including a lone hyphen and all-hyphen labels
    refuse(IP, 'bad_value:label.edge', '-')
    refuse(IP, 'bad_value:label.edge', '--')
    refuse(IP, 'bad_value:label.edge', '-ab')
    refuse(IP, 'bad_value:label.edge', 'ab-')
    # "--" at the third and fourth characters, case both ways
    refuse(IP, 'bad_value:label.r_ldh', 'ab--cd')
    refuse(IP, 'bad_value:label.r_ldh', 'AB--CD')
    # ...unless the prefix is exactly "xn--", case independent
    assert m.idna_label_parse('xn--cd')['label_class'] == 'a_label'
    assert m.idna_label_parse('XN--CD')['label_class'] == 'a_label'
    # "--" anywhere else is NR-LDH
    assert m.idna_label_parse('a--cd')['label_class'] == 'nr_ldh'
    # fake A-label: "xn--" alone, any casing
    refuse(IP, 'bad_value:label.fake', 'xn--')
    refuse(IP, 'bad_value:label.fake', 'xN--')
    # but "xn---" is long enough to hold a punycode part: edge
    refuse(IP, 'bad_value:label.edge', 'xn---')
    # result['label'] echoes the input as received (A43)
    assert m.idna_label_parse('Example')['label'] == 'Example'
    r = m.idna_label_parse('XN--ABC')
    assert r['label'] == 'XN--ABC'
    assert r['canonical_text'] == 'xn--abc'
    assert r['canonical'] is False
    # the charset gate covers the FIRST character too (A43):
    # leading non-ASCII / control / space die at the gate
    refuse(IP, 'bad_value:value.charset', 'éabc')
    refuse(IP, 'bad_value:value.charset', ' abc')
    refuse(IP, 'bad_value:value.charset', 'abc')
    refuse(IP, 'bad_value:value.charset', 'é')
    # canonical-casing pins
    r = m.idna_label_parse('Xn--A-b')
    assert r['canonical_text'] == 'xn--a-b'
    assert r['canonical'] is False
    assert r['punycode_part'] == 'A-b'
    # output field types are exact bools
    r = m.idna_label_parse('a')
    assert type(r['canonical']) is bool
    assert r['canonical'] is True
    r = m.idna_label_parse('A')
    assert r['canonical'] is False
    assert r['canonical_text'] == 'a'


__DOC__ = 'RFC 5890 "Internationalized Domain Names for\nApplications (IDNA): Definitions and Document Framework":\nthe ASCII-side label rules for ONE label string - the\ns2.3.1 LDH label base (kept thin; b1220 owns the RFC 1123\nhost-name rules), the s2.3.2 R-LDH / XN-label / NR-LDH\ndistinction, the A-label DATA SHAPE (s2.3.2.1, s2.3.2.5),\nand fake-A-label detection on ASCII grounds.  U-labels\n(NFC, non-ASCII characters, the RFC 5892 PVALID/CONTEXT\ntables, bidi and symmetry constraints), Punycode validity\nitself (the RFC 3492 codec - b1198\'s unit; an \'a_label\'\nresult here certifies every ASCII-side requirement, NOT\nthat the punycode part decodes), multi-label domain\nnames, and DNS wire format are out of scope.\n\nPublic API:\n\n  idna_label_parse(text) -> a dict:\n      \'label\': the input text as received,\n      \'label_class\': \'nr_ldh\' (a Non-Reserved LDH label)\n          or \'a_label\' (an XN-label meeting every\n          ASCII-side A-label requirement),\n      \'punycode_part\': the characters after the "xn--"\n          prefix for an \'a_label\' result, else None,\n      \'canonical_text\': OURS (below),\n      \'canonical\': True iff the input IS the canonical\n          text, byte for byte.\n  idna_label_is_valid(text) -> True iff idna_label_parse\n      would succeed.\n\nGrammar notes (verified against the RFC 5890 text).\ns2.3.1: an LDH label is a "string consisting of ASCII\nletters, digits, and the hyphen with the further\nrestriction that the hyphen cannot appear at the\nbeginning or end of the string.  Like all DNS labels, its\ntotal length must not exceed 63 octets."  s2.3.2:\n"Reserved LDH labels ... have the property that they\ncontain "--" in the third and fourth characters but which\notherwise conform to LDH label rules"; the IDNA-usable\nsubset of R-LDH labels "consists of the class of labels\nthat begin with the prefix "xn--" (case independent), but\notherwise conform to the rules for LDH labels" -\nthose are the XN-labels.  "Non-Reserved LDH labels are\nthe set of valid LDH labels that do not have "--" in the\nthird and fourth positions."  s2.3.2.1: "every A-label\nwill begin with the IDNA ACE prefix, "xn--" ..., followed\nby a string that is a valid output of the Punycode\nalgorithm [RFC3492] and hence a maximum of 59 ASCII\ncharacters in length.  The prefix and string together\nmust conform to all requirements for a label that can be\nstored in the DNS including conformance to the rules for\nLDH labels (Section 2.3.1)."\nThe 59-character punycode-part cap is the 63-octet label\ncap minus the 4-character prefix, so the label-length\ncheck already enforces it.  Fake A-labels: "Some strings\nthat are prefixed with "xn--" ... may not be the output\nof the Punycode algorithm ... They are called "Fake\nA-labels""; on ASCII grounds the detectable case is an\nEMPTY punycode part ("xn--" alone), since no U-label\nencodes to nothing.  R-LDH labels without the "xn--"\nprefix "are also not valid IDNA labels ... those labels\nMUST NOT be processed as ordinary LDH labels by\nIDNA-conforming programs" - refused here with\nbad_value:label.r_ldh.  "A-labels should be produced only\nin lowercase, despite matching other (mixed-case or\nuppercase) potential labels in the DNS": a SHOULD about\nproducing, so mixed case is accepted and the canonical\ntext is the lowercase form.\n\nProfile decisions (OURS, not from the RFC text):\n  - Only the exact str type is accepted; subclasses\n    refuse with the type code.\n  - Canonical text: the whole label in lowercase (DNS\n    label matching is case insensitive; the RFC 5890\n    lowercase-production SHOULD covers A-labels and the\n    unit applies one rule to both classes).\n\nRefusal order: bad_type:value before everything; the\n63-octet cap (bad_value:label.length); the empty label\n(bad_value:label); the printable-ASCII gate %x21-7E\n(bad_value:value.charset); the LDH character class\n(bad_value:label.char); the fake A-label "xn--" alone,\nwith an empty punycode part (bad_value:label.fake -\nahead of the hyphen-edge rule it would otherwise trip);\nthe leading/trailing hyphen rule (bad_value:label.edge);\nthe R-LDH reservation (bad_value:label.r_ldh).\n\nErrata: RFC 5890 has 7 records (3 Verified, 3 Held, 1\nReported, 0 Rejected).  Verified, not folded: EID 4695\n(s2.3.2.1, A-label expansion length - a U-label-side\nnote), EID 4696 (s4.2, DNS label compression), EID 7291\n(GLOBAL, header metadata: "Updates: 4343").  Held, not\nfolded: EIDs 4824 (s4.2), 4823 (s2.3.2.1) and 5484\n(s2.3.2.1).  Reported, not folded: EID 9026 (s2.3.2.1).\nRFC 5891 has 1 record (Held, EID 3969); its protocol\noperations are out of scope here.\n'
