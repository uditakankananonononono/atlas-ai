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
        p235_concepts_batch1231_vcard_line as mod)
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


VP = 'vcard_line_parse'

_SUCC_CACHE = None
_REFU_CACHE = None


def _success_corpus():
    global _SUCC_CACHE
    if _SUCC_CACHE is None:
        s = [(VP, ('FN:Alice',)),
             (VP, ('fn:Alice',)),
             (VP, ('item1.FN:Alice',)),
             (VP, ('ITEM1.fn:Alice\r\n',)),
             (VP, ('FN:Alice Bob\n',)),
             (VP, ('N:Doe;J.;van;Helsing;Dr.',)),
             (VP, ('N:Doe\\;J.\\;van\\;Helsing\\;Dr.',)),
             (VP, ('TEL;TYPE=work,voice:tel:+1-418-656-9254',)),
             (VP, ('TEL;TYPE="work,voice";PREF=1:tel:+1-418-656-9254',)),
             (VP, ('N;SORT-AS="Harten,Rene":van der Harten;Rene;J.;Sir',)),
             (VP, ('X-ABLABEL;X-PARAM=a,,b:\u00e9v\u00e9nement',)),
             (VP, ('FN;X-P="":v',)),
             (VP, ('FN;X-P=:v',)),
             (VP, ('FN:',)),
             (VP, ('CATEGORIES:FRIENDS\\,COLLEAGUES',)),
             (VP, ('NOTE:Line1\\nLine2',)),
             (VP, ('NOTE:backslash\\\\end',)),
             (VP, ('FN:semi;colon:and"quote',)),
             (VP, ('X-1-2.x-z:value',)),
             (VP, ('FN;X-P="a;b:c":v',)),
             (VP, ('FN;X-P=a,b,c:v',)),
             (VP, ('FN;X-P=,:v',)),
             (VP, ('FN;X-P="","":v',)),
             (VP, ('FN;LANGUAGE=fr:Patron',)),
             (VP, ('FN:\u65e5\u672c\u8a9e\u30c6\u30b9\u30c8',)),
             (VP, ('FN:tab\there',))]
        _SUCC_CACHE = s
    return _SUCC_CACHE


def _refusal_corpus():
    global _REFU_CACHE
    if _REFU_CACHE is None:
        c = []
        for bad in (None, 0, 1, True, False, 5.5, b'FN:x', ['FN:x'],
                    {'x': 1}, (1,), _StrSub('FN:x')):
            c.append((VP, 'bad_type:value', (bad,)))
        c.append((VP, 'bad_value:input.length', ('x' * 8193,)))
        for bad in ('FN:a\x01b', 'FN:a\rb', 'FN:a\nb', 'FN:a\x7fb',
                    'FN:a\ud800b', 'FN:a\udfff', '\x00'):
            c.append((VP, 'bad_value:value.charset', (bad,)))
        for bad in ('', '\r\n', '\n'):
            c.append((VP, 'bad_value:line.empty', (bad,)))
        for bad in (':Alice', '.FN:Alice', 'item1.:Alice',
                    'FN extra:Alice', 'F_N:Alice', 'item1.F_N:Alice',
                    'a.b.c:x', 'FN.:x', '1.FN.:x'):
            c.append((VP, 'bad_value:name', (bad,)))
        for bad in ('FN;=x:Alice', 'FN;X:Alice', 'FN;X', 'FN;:',
                    'FN;;X=1:x'):
            c.append((VP, 'bad_value:param', (bad,)))
        for bad in ('FN;X="a:Alice', 'FN;X=a"b:Alice',
                    'FN;X="a"x:Alice', 'FN;X="a""b":Alice',
                    'FN;X="a', 'FN;X=ab"cd:Alice'):
            c.append((VP, 'bad_value:param.value', (bad,)))
        for bad in ('FN', 'FN;X=', 'FN;X=1', 'item1.FN', 'F', 'F;X=1,2',
                    'FN;X="q"'):
            c.append((VP, 'bad_value:colon', (bad,)))
        for bad in ('FN:Alice\\', 'FN:Alice\\tBob', 'FN:Alice\\x',
                    'FN:\\', 'FN:\\\\q\\', 'FN:a\\0'):
            c.append((VP, 'bad_value:value.escape', (bad,)))
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
        _bounded_call(VP, 'x' * 8193)
    except ValueError:
        pass
    else:
        raise AssertionError('cap-boundary input must not be reached '
                             'here or must refuse cleanly')


def test_module_docstring_is_pinned_whole():
    assert m.__doc__ == __DOC__


def test_rfc6350_examples():
    # s6.1.3 style: a straightforward FN line
    r = m.vcard_line_parse('FN:Simon Perreault')
    assert r['group'] is None and r['name'] == 'FN'
    assert r['params'] == [] and r['value'] == 'Simon Perreault'
    assert r['unescaped'] == 'Simon Perreault'
    assert r['canonical'] is True
    # s6.2.2 N example with SORT-AS (s5.9, Verified EID 3713 style)
    r = m.vcard_line_parse(
        'N;SORT-AS="Harten,Rene":van der Harten;Rene;J.;Sir')
    assert r['params'] == [{'name': 'SORT-AS',
                            'values': ['Harten,Rene']}]
    assert r['value'] == 'van der Harten;Rene;J.;Sir'
    assert r['canonical'] is True
    # s6.4.1 TEL with TYPE list (s5.6)
    r = m.vcard_line_parse('TEL;TYPE=work,voice:tel:+1-418-656-9254')
    assert r['params'][0]['values'] == ['work', 'voice']
    assert r['canonical'] is True
    # the s3.3 group construct
    r = m.vcard_line_parse('item1.FN:Alice')
    assert r['group'] == 'item1' and r['name'] == 'FN'
    assert r['canonical_text'] == 'ITEM1.FN:Alice'
    assert r['canonical'] is False


def test_escaping_rules():
    # s3.4: comma, semicolon, backslash escaped; newline as \n or \N
    r = m.vcard_line_parse('CATEGORIES:FRIENDS\\,COLLEAGUES')
    assert r['unescaped'] == 'FRIENDS,COLLEAGUES'
    r = m.vcard_line_parse('N:Doe\\;J.\\;van\\;Helsing\\;Dr.')
    assert r['unescaped'] == 'Doe;J.;van;Helsing;Dr.'
    r = m.vcard_line_parse('NOTE:Line1\\nLine2\\NLine3')
    assert r['unescaped'] == 'Line1\nLine2\nLine3'
    r = m.vcard_line_parse('NOTE:back\\\\slash')
    assert r['unescaped'] == 'back\\slash'
    # "In all other cases, escaping MUST NOT be used."
    for bad in ('FN:a\\t', 'FN:a\\x', 'FN:a\\', 'FN:\\0'):
        refuse(VP, 'bad_value:value.escape', bad)
    # raw separators in the value are fine without escapes too
    assert m.vcard_line_parse('FN:a;b,c')['unescaped'] == 'a;b,c'


def test_param_rules():
    # param-value list: commas split, quotes protect (s3.3 any-param)
    r = m.vcard_line_parse('FN;X-P=a,b,c:v')
    assert r['params'][0]['values'] == ['a', 'b', 'c']
    r = m.vcard_line_parse('FN;X-P="a,b",c:v')
    assert r['params'][0]['values'] == ['a,b', 'c']
    # quoted values may hold ':' and ';' (QSAFE-CHAR)
    r = m.vcard_line_parse('FN;X-P="a;b:c":v')
    assert r['params'][0]['values'] == ['a;b:c']
    # empty values are allowed both ways (*SAFE-CHAR / *QSAFE-CHAR)
    r = m.vcard_line_parse('FN;X-P=:v')
    assert r['params'][0]['values'] == ['']
    r = m.vcard_line_parse('FN;X-P="":v')
    assert r['params'][0]['values'] == ['']
    r = m.vcard_line_parse('FN;X-P=a,,b:v')
    assert r['params'][0]['values'] == ['a', '', 'b']
    # a DQUOTE can never appear in a parameter value at all
    refuse(VP, 'bad_value:param.value', 'FN;X=a"b:v')
    refuse(VP, 'bad_value:param.value', 'FN;X="a""b":v')
    # several params
    r = m.vcard_line_parse('TEL;TYPE=work;PREF=1;X-Z=9:v')
    assert [p['name'] for p in r['params']] == ['TYPE', 'PREF', 'X-Z']


def test_casing_and_canonical_rules():
    # names/groups/params are case-insensitive (s3.3)
    r = m.vcard_line_parse('fn:Alice')
    assert r['name'] == 'fn' and r['canonical'] is False
    assert r['canonical_text'] == 'FN:Alice'
    r = m.vcard_line_parse('ITEM1.fn;type=x:Alice')
    assert r['canonical_text'] == 'ITEM1.FN;TYPE=x:Alice'
    # the s5 quoting rule drives canonical re-quoting
    r = m.vcard_line_parse('FN;X-P="abc":v')
    assert r['canonical_text'] == 'FN;X-P=abc:v'
    assert r['canonical'] is False
    r = m.vcard_line_parse('FN;X-P="ab:c":d')
    assert r['canonical'] is True
    # values stay byte-for-byte
    r = m.vcard_line_parse('FN;X-P=CaseSensitive:v')
    assert r['canonical_text'] == 'FN;X-P=CaseSensitive:v'
    # one optional terminator is stripped (OURS)
    assert m.vcard_line_parse('FN:Alice\r\n')['value'] == 'Alice'
    assert m.vcard_line_parse('FN:Alice\n')['canonical'] is True
    assert m.vcard_line_parse('FN:Alice\r\n')['canonical'] is True
    refuse(VP, 'bad_value:value.charset', 'FN:a\rb')


def test_result_shape_and_freshness():
    r = m.vcard_line_parse('FN:Alice')
    assert list(r) == ['group', 'name', 'params', 'value', 'unescaped',
                       'canonical_text', 'canonical']
    assert type(r['params']) is list
    assert type(r['canonical']) is bool
    assert type(r['canonical_text']) is str
    assert r['group'] is None
    r = m.vcard_line_parse('g.FN;X=1:Alice')
    assert list(r['params'][0]) == ['name', 'values']
    assert type(r['group']) is str
    a = m.vcard_line_parse('g.FN;X=1:Alice')
    a['params'][0]['values'][0] = 'MUTATED'
    a['value'] = 'MUTATED'
    b = m.vcard_line_parse('g.FN;X=1:Alice')
    assert b['params'][0]['values'][0] == '1'
    assert b['value'] == 'Alice'
    assert a is not b
def test_header_refusals():
    for fn_name, code, args in _refusal_corpus():
        refuse(fn_name, code, *args)


def test_exact_types_refuse():
    for bad in (None, 0, True, 5.5, b'FN:x', ['FN:x'], (1,),
                _StrSub('FN:x')):
        refuse(VP, 'bad_type:value', bad)
        assert m.vcard_line_is_valid(bad) is False


def test_input_length_cap():
    # exactly at the OURS cap: accepted; one past: refused
    ok = 'FN:' + 'x' * (8192 - 3)
    assert len(ok) == 8192
    m.vcard_line_parse(ok)
    refuse(VP, 'bad_value:input.length', ok + 'x')
    refuse(VP, 'bad_value:input.length', 'FN:x' + 'x' * 8188 + '\r\n')


def test_refusal_order():
    # type before length cap before charset before line.empty
    refuse(VP, 'bad_type:value', 0)
    refuse(VP, 'bad_value:input.length', 'x' * 8193)
    refuse(VP, 'bad_value:value.charset', '\x01')
    refuse(VP, 'bad_value:line.empty', '')
    # name before param before colon before escape
    refuse(VP, 'bad_value:name', ';X=1:x\\')
    refuse(VP, 'bad_value:param', 'FN;=1:x\\')
    refuse(VP, 'bad_value:param.value', 'FN;X="a:x\\')
    refuse(VP, 'bad_value:colon', 'FN;X=1\\')
    refuse(VP, 'bad_value:value.escape', 'FN:x\\')
    # the first bad parameter refuses before a later one is read
    refuse(VP, 'bad_value:param', 'FN;;Y="u:x')
    refuse(VP, 'bad_value:param.value', 'FN;X="u;Y:1')


def test_is_valid_returns_exact_bool():
    v = m.vcard_line_is_valid('FN:Alice')
    assert v is True and type(v) is bool
    assert m.vcard_line_is_valid('TEL;TYPE=work,voice:tel:+1') is True
    assert m.vcard_line_is_valid('garbage') is False
    assert m.vcard_line_is_valid(None) is False
    assert m.vcard_line_is_valid(0) is False


def test_constants_pinned_whole():
    assert m._MAX_INPUT_LENGTH == 8192
    assert m._NAME_CHARS == frozenset(
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        '0123456789-')
    assert m._SAFE_CHARS == frozenset(
        '\t !#$%&\'()*+,-./0123456789<=>?@'
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`'
        'abcdefghijklmnopqrstuvwxyz{|}~')
    assert m._QSAFE_CHARS == frozenset(
        '\t !#$%&\'()*+,-./0123456789:;<=>?@'
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`'
        'abcdefghijklmnopqrstuvwxyz{|}~')
    assert m._ESCAPE_TARGETS == {'\\': '\\', ';': ';', ',': ',',
                                 'n': '\n', 'N': '\n'}


def test_function_docstrings_pinned_exact():
    assert m.vcard_line_parse.__doc__ == (
        'Validate one RFC 6350 s3.3 content line with s3.4 value '
        'escapes.')
    assert m.vcard_line_is_valid.__doc__ == (
        'True iff vcard_line_parse(text) would succeed.')


def test_module_namespace_is_pinned():
    names = set(vars(m))
    assert names == {
        '__name__', '__doc__', '__package__', '__loader__',
        '__spec__', '__file__', '__cached__', '__builtins__',
        'find_spec', 'make_fail',
        '_MAX_INPUT_LENGTH', '_NAME_CHARS', '_SAFE_CHARS',
        '_QSAFE_CHARS', '_ESCAPE_TARGETS',
        '_non_ascii_ok', '_canon_pvalue',
        'vcard_line_parse', 'vcard_line_is_valid'}


def test_parse_is_deterministic_and_consistent():
    rng = random.Random(1231)
    alphabet = 'aZ09-;:=,."\\nx FN\t\x00~/\u00e9'
    for _ in range(400):
        blob = ''.join(rng.choice(alphabet)
                       for _ in range(rng.randrange(0, 24)))
        try:
            r1 = m.vcard_line_parse(blob)
        except ValueError:
            assert m.vcard_line_is_valid(blob) is False
        else:
            assert m.vcard_line_is_valid(blob) is True
            assert m.vcard_line_parse(blob) == r1
            # the canonical text always re-parses, canonically
            r2 = m.vcard_line_parse(r1['canonical_text'])
            assert r2['canonical'] is True
            assert r2['canonical_text'] == r1['canonical_text']
            assert r2['value'] == r1['value']
            assert [p['values'] for p in r2['params']] == [
                p['values'] for p in r1['params']]


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
        mod = types.ModuleType('fresh_b1231')
        with pytest.raises(ModuleNotFoundError):
            exec(compile(src, 'fresh_b1231', 'exec'), mod.__dict__)
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
            ('import no_such_dep_xyz_1231\n', 'ModuleNotFoundError'),
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
        mod = types.ModuleType('fresh_b1231_spy')
        exec(compile(src, 'fresh_b1231_spy', 'exec'), mod.__dict__)
    finally:
        _stop_import()
        _iu.find_spec = real_find_spec
    assert calls == [REG], calls
    # the fallback engaged and works
    assert mod.vcard_line_is_valid('FN:x') is True
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        assert str(e) == 'P235:x:c'
    else:
        raise AssertionError('fallback make_fail did not raise')


def test_battery_rev0_pins():
    # exactly at the OURS cap: accepted; one past: refused
    ok = 'FN:' + 'x' * (8192 - 3)
    assert m.vcard_line_parse(ok)['canonical_text'] == ok
    refuse(VP, 'bad_value:input.length', 'x' * 8193)
    # group and name share one char class; the dot splits them
    r = m.vcard_line_parse('1-2.x-9:v')
    assert r['group'] == '1-2' and r['name'] == 'x-9'
    refuse(VP, 'bad_value:name', 'a.b.c:v')
    refuse(VP, 'bad_value:name', 'a.:v')
    # a param needs a name and an '='
    refuse(VP, 'bad_value:param', 'FN;=1:v')
    refuse(VP, 'bad_value:param', 'FN;X:v')
    # an escaped char is never a separator on input (s3.4)
    refuse(VP, 'bad_value:value.escape', 'FN:' + '\\' * 3)
    assert m.vcard_line_parse('FN:Alice\n')['value'] == 'Alice'
    r2 = m.vcard_line_parse('FN:a\\n')
    assert r2['value'] == 'a\\n' and r2['unescaped'] == 'a\n'
    for good in ('\u0080', '\ud7ff', '\ue000'):
        assert m.vcard_line_parse('FN:a' + good)['value'] == 'a' + good
    r = m.vcard_line_parse('FN;X=é:v')
    assert r['params'] == [{'name': 'X', 'values': ['é']}]
    r = m.vcard_line_parse('N:a\\;b')
    assert r['value'] == 'a\\;b'
    # the value may be empty (s3.3 value = *VALUE-CHAR)
    assert m.vcard_line_parse('FN:')['value'] == ''
    # HTAB is a WSP member of SAFE/QSAFE/VALUE chars (EID 3136)
    m.vcard_line_parse('FN;X-P=a\tb:v')
    m.vcard_line_parse('FN;X-P="a\tb":v')
    m.vcard_line_parse('FN:a\tb')
    # str subclasses refuse with the type code
    refuse(VP, 'bad_type:value', _StrSub('FN:x'))


def test_battery_rev1_pins():
    # A41 rev0 FINAL: loop1@255 - the canonical_text params loop
    # covers EVERY parameter, not only the first.
    r = m.vcard_line_parse('N;P=1;Q=2:V')
    assert r['canonical_text'] == 'N;P=1;Q=2:V'
    assert r['canonical'] is True
    # three params
    r = m.vcard_line_parse('N;P=1;Q=2;R=3:V')
    assert r['canonical_text'] == 'N;P=1;Q=2;R=3:V'
    assert r['canonical'] is True
    # a later param with a multi-value list
    r = m.vcard_line_parse('N;P=1;Q=x,y:V')
    assert r['canonical_text'] == 'N;P=1;Q=x,y:V'
    assert r['canonical'] is True
    assert r['params'][1]['values'] == ['x', 'y']
    # a later param drives a canonical difference (upper-casing)
    r = m.vcard_line_parse('N;p=1;q=2:V')
    assert r['canonical_text'] == 'N;P=1;Q=2:V'
    assert r['canonical'] is False
    # a quoted later-param value is re-quoted identically
    r = m.vcard_line_parse('N;P=1;Q="a:b":V')
    assert r['canonical_text'] == 'N;P=1;Q="a:b":V'
    assert r['canonical'] is True

__DOC__ = 'RFC 6350 "vCard Format Specification": the s3.3 content\nline grammar and the s3.4 property value escaping rules,\nover one Python text string carrying ONE logical content\nline (already unfolded: s3.2 line folding is out of scope,\nas are the vcard wrapper of s3.3, the s4 value data types\nand the per-property grammars of s5 and s6).\n\nPublic API:\n\n  vcard_line_parse(text) -> a dict:\n      \'group\': the group prefix as received, or None,\n      \'name\': the property name as received,\n      \'params\': list of {\'name\': the parameter name as\n          received, \'values\': list of parameter value\n          strings (DQUOTEs stripped from quoted forms)},\n      \'value\': the property value, escapes intact,\n      \'unescaped\': the value with s3.4 escapes decoded\n          (\\\\ -> \\, \\; -> ;, \\, -> comma, \\n/\\N -> LF),\n      \'canonical_text\': the canonical line (below),\n      \'canonical\': True iff the terminator-stripped input\n      IS the canonical text, byte for byte.\n  vcard_line_is_valid(text) -> True iff vcard_line_parse\n      would succeed.\n\nGrammar notes (verified against the RFC 6350 text).  s3.3:\n\'contentline = [group "."] name *(";" param) ":" value\nCRLF\', \'group = 1*(ALPHA / DIGIT / "-")\', \'name = "SOURCE"\n/ "KIND" / ... / iana-token / x-name\', \'iana-token =\n1*(ALPHA / DIGIT / "-")\', \'x-name = "x-" 1*(ALPHA / DIGIT /\n"-")\' ("Group and name are case-insensitive"), \'param-value\n= *SAFE-CHAR / DQUOTE *QSAFE-CHAR DQUOTE\' (with Verified\nerratum 2964\'s parenthesization), \'any-param = (iana-token\n/ x-name) "=" param-value *("," param-value)\', \'QSAFE-CHAR\n= WSP / "!" / %x23-7E / NON-ASCII\' ("Any character except\nCTLs, DQUOTE"), \'SAFE-CHAR = WSP / "!" / %x23-39 / %x3C-7E\n/ NON-ASCII\' ("Any character except CTLs, DQUOTE, ";",\n":""), \'VALUE-CHAR = WSP / VCHAR / NON-ASCII\'.  Verified\nerratum 3136 confirms WSP includes HTAB in all three.\ns3.3 text: "Property names and parameter names are\ncase-insensitive" and "it is RECOMMENDED that property and\nparameter names be upper-case on output".  s5: "Property\nparameter value elements that contain the COLON (U+003A),\nSEMICOLON (U+003B), or COMMA (U+002C) character separators\nMUST be specified as quoted-string text" (a sender rule;\nHeld erratum 3138 would move COMMA out of SAFE-CHAR and is\nNOT folded, so a bare comma still splits the param-value\nlist exactly as the printed any-param production says).\ns3.4: "a COMMA character in a value MUST be escaped with a\nBACKSLASH", "a SEMICOLON in a field of such a "compound"\nproperty MUST be escaped", "BACKSLASH characters in values\nMUST be escaped with a BACKSLASH character", "NEWLINE\n(U+000A) characters in values MUST be encoded by two\ncharacters: a BACKSLASH followed by either an \'n\' (U+006E)\nor an \'N\' (U+004E)", and "In all other cases, escaping MUST\nNOT be used" - so a backslash MUST be followed by one of\n\\ ; , n N and any other escape refuses.\n\nProfile decisions (OURS, not from the RFC text):\n  - Only the exact str type is accepted; subclasses refuse\n    with the type code.\n  - ONE optional trailing CRLF (or bare LF) terminator is\n    stripped before parsing; any other CR or LF refuses at\n    the charset gate.\n  - Charset gate: HTAB, 0x20-0x7E, and non-ASCII scalar\n    values (0x80 and up, UTF-16 surrogates refused); the\n    RFC\'s NON-ASCII is any UTF8-2/3/4 sequence.\n  - Size cap: _MAX_INPUT_LENGTH characters.\n  - The canonical text (the RFC defines none): group and\n    property/parameter names upper-cased (the s3.3\n    RECOMMENDATION), parameter values re-quoted EXACTLY\n    when they contain \':\', \';\' or \',\' (the s5 MUST rule),\n    list items joined with ",", the value byte-for-byte as\n    received, and no line terminator.  Param names and\n    values are stored as received (values with DQUOTEs\n    stripped).\n\nRefusal order (exactly as executed): bad_type:value (not\nexactly str); bad_value:input.length (over\n_MAX_INPUT_LENGTH = 8192, terminator included); then the\nsingle optional terminator is stripped and\nbad_value:value.charset fires for any remaining char\noutside HTAB / 0x20-0x7E / non-ASCII scalars;\nbad_value:line.empty; then bad_value:name (no name token,\nan empty name after a group dot, or junk between the name\nand the \';\' / \':\' that must follow); then per parameter\nbad_value:param (empty parameter name or missing \'=\') and\nbad_value:param.value (a CTL/DQUOTE in an unquoted value,\nan unterminated or badly-followed quoted value, a CTL\ninside one); then bad_value:colon (no \':\' before the\nvalue); then bad_value:value.escape (a lone backslash or\none followed by anything but \\ ; , n N).\n\nErrata: RFC 6350 has 33 records (14 Verified, 10 Held, 7\nReported, 2 Rejected).  Folded Verified: EID 2964 (s3.3)\nparenthesizes the param-value quoted alternative - this\nunit always parsed it that way; EID 3136 (s3.3) confirms\nHTAB is in QSAFE-CHAR/SAFE-CHAR/VALUE-CHAR - the charset\ngate allows it.  Verified but out of scope (s4-s7, s10):\nEIDs 3000, 3086, 3137, 3368, 3377, 3845, 3484, 3713,\n3748, 3846, 4246, 7316.  Held, not folded: EIDs 3138 and\n3139 (s3.3 param-value/list semantics - the printed\ngrammar stands), 7895, 3005, 3100, 3062, 3488, 4261,\n4213, 4245.  Reported, not folded: EIDs 7061, 4901,\n6746, 6812, 6864, 8092, 8109.  Rejected: EIDs 3199,\n7856.\n'
