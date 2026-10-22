import ast
import builtins
import importlib.util as iu
import pathlib
import re
import signal
import sys
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
        p235_concepts_batch1242_rfc9110_content_coding as mod)
    m = mod


@pytest.fixture(autouse=True)
def alarm():
    def stop(*a):
        raise RuntimeError('test exceeded 30 seconds')
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


def refuse(fn, code, *args, **kw):
    with pytest.raises(ValueError) as caught:
        getattr(m, fn)(*args, **kw)
    assert type(caught.value) is ValueError
    assert str(caught.value) == _pfx() + fn + ':' + code
# ---- core acceptance: atoms / dot-atoms ----
# ---- structure pins: registry worlds, literals, docstring, imports ----

@pytest.fixture
def undo_log():
    log = []
    yield log
    for mapping, key, present, old in reversed(log):
        if present:
            mapping[key] = old
        else:
            mapping.pop(key, None)


def _setitem(log, mapping, key, value):
    log.append((mapping, key, key in mapping, mapping.get(key)))
    mapping[key] = value


def _pop(log, mapping, key):
    log.append((mapping, key, key in mapping, mapping.get(key)))
    mapping.pop(key, None)


def _exec_with(log, import_exc=None, find_spec_exc=None, present=False,
               spy=None):
    src = pathlib.Path(m.__file__).read_text()
    real_import = builtins.__import__
    real_fs = iu.find_spec
    _pop(log, sys.modules, REG)

    def blocked(name, *a, **k):
        if name == REG and import_exc is not None:
            raise import_exc
        return real_import(name, *a, **k)

    def fs(*a, **k):
        if a and a[0] == REG:
            if spy is not None:
                spy.append((a, k))
            if find_spec_exc is not None:
                raise find_spec_exc
            return object() if present else None
        return real_fs(*a, **k)

    _start_import(builtins, blocked)
    iu.find_spec = fs
    try:
        ns = {'__name__': 'b1242_exec'}
        exec(compile(src, 'm', 'exec'), ns)
        return ns
    finally:
        _stop_import()
        iu.find_spec = real_fs


def _exec_guarded(log, spec_result=None, spy=None):
    return _exec_with(log,
                      import_exc=ModuleNotFoundError('b1242 guard probe',
                                                     name=REG),
                      present=spec_result is not None, spy=spy)


def test_guard_propagates_other_module_not_found_exactly(undo_log):
    exc = ModuleNotFoundError('no sibling',
                              name='app.modules.instinct_doc.nope')
    with pytest.raises(ModuleNotFoundError) as caught:
        _exec_with(undo_log, import_exc=exc)
    assert caught.value is exc


def test_guard_propagates_plain_import_error(undo_log):
    exc = ImportError('boom')
    with pytest.raises(ImportError) as caught:
        _exec_with(undo_log, import_exc=exc)
    assert caught.value is exc


def test_guard_propagates_import_error_named_registry(undo_log):
    exc = ImportError('registry broken', name=REG)
    assert type(exc) is ImportError
    with pytest.raises(ImportError) as caught:
        _exec_with(undo_log, import_exc=exc, present=False)
    assert caught.value is exc
    assert type(caught.value) is ImportError


def test_guard_resurrected_registry_reraises(undo_log):
    # registry import failed but find_spec finds it: do not fall back
    with pytest.raises(ModuleNotFoundError):
        _exec_guarded(undo_log, spec_result=object())


def test_guard_find_spec_not_called_on_wrong_name(undo_log):
    spy = []
    exc = ModuleNotFoundError('probe', name='totally.other')
    with pytest.raises(ModuleNotFoundError):
        _exec_with(undo_log, import_exc=exc, spy=spy)
    assert spy == [], spy


def test_guard_find_spec_called_once_on_registry_name(undo_log):
    spy = []
    ns = _exec_guarded(undo_log, spy=spy)
    assert callable(ns['make_fail'])
    assert len(spy) == 1 and spy[0][0][0] == REG, spy


def test_import_log_is_exactly_pinned_in_all_four_registry_worlds(
        undo_log):
    # module load imports exactly: importlib.util, then the registry
    def run(kind):
        src = pathlib.Path(m.__file__).read_text()
        real_import = builtins.__import__
        real_fs = iu.find_spec
        _pop(undo_log, sys.modules, REG)
        if kind == 'present':
            fake = types.ModuleType(REG)
            fake.make_fail = lambda name: (lambda code: None)
            _setitem(undo_log, sys.modules, REG, fake)
        ilog = []

        def hooked(name, globals=None, locals=None, fromlist=(), level=0):
            ilog.append((name, tuple(fromlist) if fromlist else ()))
            if kind == 'present' and name == REG:
                return real_import(name, globals, locals, fromlist, level)
            if kind in ('fallback', 'resurrect') and name == REG:
                raise ModuleNotFoundError('probe', name=REG)
            if kind == 'other' and name == REG:
                raise ModuleNotFoundError('probe', name='x.y')
            return real_import(name, globals, locals, fromlist, level)

        def fs(name, *a, **k):
            if name == REG:
                return object() if kind == 'resurrect' else None
            return real_fs(name, *a, **k)

        _start_import(builtins, hooked)
        iu.find_spec = fs
        try:
            ns = {'__name__': 'b1242_world'}
            try:
                exec(compile(src, 'm', 'exec'), ns)
            except ModuleNotFoundError:
                return None, ilog
            return ns, ilog
        finally:
            _stop_import()
            iu.find_spec = real_fs

    expected = [('importlib.util', ('find_spec',)), (REG, ('make_fail',))]
    ns, ilog = run('present')
    assert ns is not None and ilog == expected, ilog
    ns, ilog = run('fallback')
    assert ns is not None and callable(ns['make_fail'])
    assert ilog == expected, ilog
    ns, ilog = run('other')
    assert ns is None and ilog == expected, ilog
    ns, ilog = run('resurrect')
    assert ns is None and ilog == expected, ilog
# ---- codes, successes, refusals ----

def _src():
    return pathlib.Path(m.__file__).read_text()

def _run_all(ns, log=None):
    results = []
    for fn, args in _SUCCESSES + _REFUSALS:
        try:
            results.append(('ok', ns[fn](*args)))
        except ValueError as exc:
            results.append(('err', str(exc)))
    return results


def _hooked_ns(src, kind='absent'):
    real = builtins.__import__
    log = []

    def hook(name, g=None, l=None, fromlist=(), level=0):
        log.append(name)
        if name == REG:
            raise ModuleNotFoundError('probe', name=REG)
        return real(name, g, l, fromlist, level)

    real_fs = iu.find_spec
    _start_import(builtins, hook)
    iu.find_spec = lambda name, *a, **k: (
        None if name == REG else real_fs(name, *a, **k))
    try:
        ns = {'__name__': 'b1242_hooked'}
        exec(compile(src, 'm', 'exec'), ns)
    finally:
        _stop_import()
        iu.find_spec = real_fs
    del log[:]
    return ns, log


def _drive(ns, log):
    real = builtins.__import__

    def hook(name, *a, **k):
        log.append(name)
        return real(name, *a, **k)

    _start_import(builtins, hook)
    try:
        return _run_all(ns)
    finally:
        _stop_import()


def test_every_refusal_code_of_every_function_is_driven():
    seen = {}
    for fn, args in _REFUSALS:
        try:
            getattr(m, fn)(*args)
        except ValueError as exc:
            seen.setdefault(fn, set()).add(
                str(exc)[len(_pfx() + fn + ':'):])
    for fn, codes in _CODES.items():
        assert seen[fn] == set(codes), (fn, seen[fn] ^ set(codes))
    # the AST finds exactly these f() call sites in the module
    tree = ast.parse(_src())
    sites = {}
    for func in tree.body:
        if isinstance(func, ast.FunctionDef):
            for node in ast.walk(func):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == 'f'):
                    arg = node.args[0]
                    if isinstance(arg, ast.Name):
                        continue
                    sites.setdefault(arg.value, []).append(func.name)
    union = set()
    for codes in _CODES.values():
        union |= set(codes)
    assert set(sites) == union, set(sites) ^ union


def test_success_and_refusal_paths_import_nothing_and_insertions_die():
    src = _src()
    ns, log = _hooked_ns(src)
    first = _drive(ns, log)
    assert log == [], log
    assert first == _drive(ns, log)
    tree = ast.parse(src)
    lines = src.split('\n')
    stmts = []
    for func in tree.body:
        if isinstance(func, ast.FunctionDef):
            for node in ast.walk(func):
                if isinstance(node, ast.stmt) and node is not func and not (
                        isinstance(node, ast.Expr) and isinstance(
                            node.value, ast.Constant)):
                    stmts.append(node)
    stmts.sort(key=lambda n: n.lineno)
    stmts = [n for n in stmts
             if not lines[n.lineno - 1].lstrip().startswith('elif ')]
    assert len(stmts) > 30
    for node in stmts:
        patched = list(lines)
        patched.insert(node.lineno - 1, ' ' * node.col_offset + 'import os')
        ns2, log2 = _hooked_ns('\n'.join(patched))
        _drive(ns2, log2)
        assert 'os' in log2, (type(node).__name__, node.lineno)


def test_cap_before_work_tracemalloc():
    import tracemalloc
    cases = [
        ('coding_token_validate', ('x' * 10000000,),
         'bad_value:field.length'),
        ('content_encoding_validate', ('x' * 10000000,),
         'bad_value:field.length'),
        ('content_encoding_list', ('x' * 10000000,),
         'bad_value:field.length'),
        ('accept_encoding_validate', ('x' * 10000000,),
         'bad_value:field.length'),
        ('accept_encoding_list', ('x' * 10000000,),
         'bad_value:field.length'),
        ('coding_acceptable', ('gzip', 'x' * 10000000),
         'bad_value:field.length'),
        ('coding_acceptable', ('x' * 10000000, None),
         'bad_value:coding'),
    ]
    for fn, args, code in cases:
        tracemalloc.start()
        try:
            refuse(fn, code, *args)
        finally:
            peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
        assert peak < 4 * 1024 * 1024, (fn, peak)


def test_every_success_case_succeeds_and_every_refusal_refuses():
    for fn, args in _SUCCESSES:
        getattr(m, fn)(*args)
    for fn, args in _REFUSALS:
        with pytest.raises(ValueError):
            getattr(m, fn)(*args)


# ---- codes, successes, refusals ----

_T = 'coding_token_validate'
_C = 'content_encoding_validate'
_L = 'content_encoding_list'
_A = 'accept_encoding_validate'
_AL = 'accept_encoding_list'
_E = 'coding_acceptable'

_CODES = {
    _T: (
        'bad_type:text',
        'bad_value:field.length',
        'bad_value:token',
        'bad_value:token.char',
    ),
    _C: (
        'bad_type:text',
        'bad_value:field.length',
        'bad_value:field.count',
        'bad_value:token',
        'bad_value:list',
    ),
    _L: (
        'bad_type:text',
        'bad_value:field.length',
        'bad_value:field.count',
        'bad_value:token',
        'bad_value:list',
    ),
    _A: (
        'bad_type:text',
        'bad_value:field.length',
        'bad_value:field.count',
        'bad_value:token',
        'bad_value:weight',
        'bad_value:qvalue',
        'bad_value:list',
    ),
    _AL: (
        'bad_type:text',
        'bad_value:field.length',
        'bad_value:field.count',
        'bad_value:token',
        'bad_value:weight',
        'bad_value:qvalue',
        'bad_value:list',
    ),
    _E: (
        'bad_type:coding',
        'bad_type:value',
        'bad_value:coding',
        'bad_value:field.length',
        'bad_value:field.count',
        'bad_value:token',
        'bad_value:weight',
        'bad_value:qvalue',
        'bad_value:list',
    ),
}

_SUCCESSES = [
    (_T, ('gzip',)),
    (_T, ('a',)),
    (_T, ('*',)),
    (_T, ("!#$%&'*+-.^_`|~",)),
    (_T, ('x' * 255,)),
    (_C, ('gzip',)),
    (_C, ('gzip, br',)),
    (_C, ('gzip,br,, ,deflate',)),
    (_C, ('',)),
    (_C, (',',)),
    (_C, (' , , ',)),
    (_C, ('identity',)),
    (_C, ('*',)),
    (_L, ('gzip, br',)),
    (_L, ('',)),
    (_A, ('gzip',)),
    (_A, ('compress, gzip',)),
    (_A, ('*',)),
    (_A, ('',)),
    (_A, ('gzip;q=0.5',)),
    (_A, ('gzip;q=1.0, identity; q=0.5, *;q=0',)),
    (_A, ('gzip;Q=1',)),
    (_A, ('gzip ; q=0.000',)),
    (_A, ('gzip;q=1.',)),
    (_A, ('gzip;q=0.',)),
    (_A, ('gzip;q=0.123',)),
    (_A, ('gzip;q=1.000',)),
    (_A, (',gzip,,br,',)),
    (_AL, ('gzip, br',)),
    (_AL, ('gzip;q=0.5',)),
    (_AL, ('*;q=0',)),
    (_E, ('gzip', None)),
    (_E, ('identity', None)),
    (_E, ('gzip', '')),
    (_E, ('gzip', 'gzip')),
    (_E, ('gzip', '*')),
    (_E, ('GZIP', 'Gzip;Q=1')),
    (_E, ('gzip', 'gzip;q=0.5')),
    (_E, ('gzip', 'gzip;q=0.0')),
    (_E, ('identity', 'gzip')),
]

_REFUSALS = [
    (_T, (None,)),
    (_T, ('x' * 256,)),
    (_T, ('',)),
    (_T, ('gz ip',)),
    (_C, (None,)),
    (_C, ('x' * 4097,)),
    (_C, (','.join(['a'] * 257),)),
    (_C, ('a' * 256,)),
    (_C, ('@gzip',)),
    (_C, ('gzip br',)),
    (_L, (None,)),
    (_L, ('y' * 4097,)),
    (_L, (','.join(['a'] * 257),)),
    (_L, ('@gzip',)),
    (_L, ('gzip;q=1',)),
    (_A, (None,)),
    (_A, ('x' * 4097,)),
    (_A, (','.join(['a'] * 257),)),
    (_A, ('@gzip',)),
    (_A, ('gzip;',)),
    (_A, ('gzip; x=1',)),
    (_A, ('gzip;q=',)),
    (_A, ('gzip;q=2',)),
    (_A, ('gzip;q=1.5',)),
    (_AL, (None,)),
    (_AL, ('z' * 4097,)),
    (_AL, (','.join(['a'] * 257),)),
    (_AL, ('@gzip',)),
    (_AL, ('gzip;',)),
    (_AL, ('gzip;qq=1',)),
    (_AL, ('gzip;q=.5',)),
    (_AL, ('gzip;q=0.1234',)),
    (_E, (5, None)),
    (_E, ('', None)),
    (_E, ('x' * 256, None)),
    (_E, ('gz ip', None)),
    (_E, ('*', None)),
    (_E, ('gzip', 5)),
    (_E, ('gzip', 'x' * 4097)),
    (_E, ('gzip', ','.join(['a'] * 257))),
    (_E, ('gzip', '@x')),
    (_E, ('gzip', 'br;')),
    (_E, ('gzip', 'br;q=')),
    (_E, ('gzip', 'br x')),
]
def test_fallback_failer_prefix_is_literal_p235(undo_log):
    ns = _exec_guarded(undo_log)
    with pytest.raises(ValueError) as e:
        ns['coding_token_validate'](None)
    assert type(e.value) is ValueError
    assert str(e.value) == 'P235:coding_token_validate:bad_type:text'
    with pytest.raises(ValueError) as e:
        ns['make_fail']('x')('y:z')
    assert str(e.value) == 'P235:x:y:z'


def test_fallback_failer_is_import_free_and_fully_driven(undo_log):
    ns = _exec_guarded(undo_log)
    log = []
    got = _drive(ns, log)
    assert log == [], log
    assert [r[0] for r in got].count('ok') == len(_SUCCESSES)
    for (fn, args), (kind, val) in zip(_SUCCESSES + _REFUSALS, got):
        if kind == 'err':
            assert val.startswith('P235:' + fn + ':'), val
    # the registry failer insertions: import os before each failer statement
    src = _src()
    lines = src.split('\n')
    start = next(i for i, l in enumerate(lines)
                 if l.startswith('    def make_fail'))
    for offset in range(1, 4):
        patched = list(lines)
        target = lines[start + offset]
        patched.insert(start + offset,
                       target[:len(target) - len(target.lstrip())]
                       + 'import os')
        ns2, log2 = _hooked_ns('\n'.join(patched))
        _drive(ns2, log2)
        assert 'os' in log2, offset
# ---- constants, namespace, docstring and errata pins ----

_NAMES = ['COUNT_CAP', 'NOT_CLAIMED', 'SCOPE', 'TOKEN_CAP', 'VALUE_CAP', '_DIG', '_OWS', '_TCHAR', '_element_end', '_fold', '_folded', '_in', '_list', '_ows_end', '_qvalue_end', '_qzero', '_token_end', '_weight_end', 'find_spec', 'make_fail']


def test_constants_and_exact_namespace(undo_log):
    assert m.__all__ == ['coding_token_validate', 'content_encoding_validate', 'content_encoding_list', 'accept_encoding_validate', 'accept_encoding_list', 'coding_acceptable']
    assert (m.TOKEN_CAP, m.VALUE_CAP, m.COUNT_CAP) == (255, 4096, 256)
    assert m.SCOPE == 'FULL: the RFC 9110 content-coding grammar over caller supplied str values: the Section 8.4.1 content-coding token (Section 5.6.2 tchar), the Section 8.4 Content-Encoding list, and the Section 12.5.3 Accept-Encoding list with its Section 12.4.2 qvalue weight, asterisk and identity rules and the q=0 "not acceptable" semantics, with Section 5.6.1.2 recipient list parsing (empty elements ignored)'
    assert m.NOT_CLAIMED == 'The general weight/qvalue and #rule machinery (batch1219 owns it); decoding any content; the live IANA HTTP Content Coding Registry; folding the x-compress and x-gzip aliases (recipient guidance only); Content-Language and language tags (batch1218 owns RFC 5646); media types, Accept and other negotiation fields'
    expected = set(_NAMES) | set(m.__all__)
    names = {n for n in vars(m) if not n.startswith("__")}
    assert names == expected, sorted(names ^ expected)
    ns = _exec_guarded(undo_log)
    assert {n for n in ns if not n.startswith("__")} == expected
    fake = types.ModuleType(REG)
    fake.make_fail = lambda name: (lambda code: None)
    _setitem(undo_log, sys.modules, REG, fake)
    ns2 = {'__name__': 'b1242_present'}
    exec(compile(_src(), 'm', 'exec'), ns2)
    assert {n for n in ns2 if not n.startswith("__")} == expected
    assert ns2['make_fail'] is fake.make_fail


def test_module_docstring_and_function_docstrings_pinned():
    assert m.__doc__ == _src().split('\"\"\"')[1]
    assert '\\' not in m.__doc__
    assert m.coding_token_validate.__doc__ == 'Validate a content-coding token (RFC 9110 Section 8.4.1:\n    content-coding = token, the Section 5.6.2 production of one or\n    more tchar) as a caller supplied str. Return the text unchanged.\n    Refusals: bad_type:text for a non-str; bad_value:field.length\n    over TOKEN_CAP; bad_value:token when empty; bad_value:token.char\n    for a character outside tchar.'
    assert m.content_encoding_validate.__doc__ == 'Validate a Content-Encoding field value (RFC 9110 Section 8.4:\n    #content-coding, recipient list rules of Section 5.6.1.2 so empty\n    elements are ignored) as a caller supplied str; the empty value is\n    valid. Return the value unchanged. Refusals: bad_type:text for a\n    non-str; bad_value:field.length over VALUE_CAP;\n    bad_value:field.count over COUNT_CAP contributing elements;\n    bad_value:token.char for a non-tchar character;\n    bad_value:list for junk between elements.'
    assert m.content_encoding_list.__doc__ == 'Extract the content codings of a Content-Encoding field value\n    (RFC 9110 Section 8.4) from a caller supplied str, as a tuple of\n    verbatim element strings in field order. Refusals: bad_type:text\n    for a non-str; bad_value:field.length over VALUE_CAP;\n    bad_value:field.count over COUNT_CAP contributing elements;\n    bad_value:token.char for a non-tchar character;\n    bad_value:list for junk between elements.'
    assert m.accept_encoding_validate.__doc__ == 'Validate an Accept-Encoding field value (RFC 9110 Section\n    12.5.3: #( codings [ weight ] ), recipient list rules of Section\n    5.6.1.2) as a caller supplied str; the empty value is valid.\n    Return the value unchanged. Refusals: bad_type:text for a\n    non-str; bad_value:field.length over VALUE_CAP;\n    bad_value:field.count over COUNT_CAP contributing elements;\n    bad_value:token.char for a non-tchar character;\n    bad_value:weight for a ";" not starting a Section 12.4.2 weight;\n    bad_value:qvalue for a malformed qvalue; bad_value:list for junk\n    between elements or after a weight.'
    assert m.accept_encoding_list.__doc__ == 'Extract the entries of an Accept-Encoding field value (RFC\n    9110 Section 12.5.3) from a caller supplied str, as a tuple of\n    (codings, qvalue) pairs in field order; both parts are verbatim\n    strings, the qvalue without its "q=" prefix, and the qvalue is\n    None when no weight is present (default weight 1). Refusals:\n    bad_type:text for a non-str; bad_value:field.length over\n    VALUE_CAP; bad_value:field.count over COUNT_CAP contributing\n    elements; bad_value:token.char for a non-tchar character;\n    bad_value:weight for a ";" not starting a weight;\n    bad_value:qvalue for a malformed qvalue; bad_value:list for\n    junk between elements or after a weight.'
    assert m.coding_acceptable.__doc__ == "Evaluate the Section 12.5.3 acceptability rules for one\n    content coding against an Accept-Encoding field value: the asked\n    coding is a caller supplied str token ('identity' asks the\n    no-coding question; case-insensitive), and the value is a caller\n    supplied str or None (None means the field is absent, so every\n    valid coding is acceptable). Return True or False. OURS: '*'\n    refused as the asked coding; a zero-entry value carries the\n    empty-field meaning; duplicate names resolve to the last entry.\n    Refusals: bad_type:coding or bad_type:value for a wrong type;\n    bad_value:coding for '*' as the asked coding; plus the token,\n    field.length, field.count, weight, qvalue and list codes."


_ERRATA = (
    'RFC9110 Rejected Editorial: EID 7530 (15.5.2.).',
    'RFC9110 Rejected Technical: EID 7107 (6.5.1), EID 7599 (6.4.1), EID 7870 (8.6), EID 8138 (15.4), EID 8459 (15).',
    'RFC9110 Reported Technical: EID 9162 (5.2), EID 9164 (Appendix A).',
    'RFC9110 Verified Editorial: EID 7105 (B.1.), EID 7109 (15.4.9), EID 8268 (B.2).',
    'RFC9110 Verified Technical: EID 7138 (12.5.1), EID 7306 (14.1.1), EID 7419 (8.3.2).',
)


def test_docstring_errata_list_whole():
    flat = ' '.join(m.__doc__.split())
    errata = flat[flat.index('Errata (live'):flat.index('SCOPE and')]
    for piece in _ERRATA:
        assert ' '.join(piece.split()) in errata, piece
    listing = errata[errata.index('12.5.3): ') + 9:]
    assert len(re.findall(r'EID \d+', listing)) == 14
    assert len(set(re.findall(r'EID (\d+)', listing))) == 14
    assert listing == ' '.join(' '.join(_ERRATA).split()) + ' '
    assert 'RFC 9110 has 14 records' in errata
# ---- explicit pins ----

class _Str(str):
    pass


def _c2(fn, value):
    with pytest.raises(ValueError) as e:
        getattr(m, fn)(value)
    return str(e.value)[len(_pfx() + fn + ':'):]


def test_rfc_section_examples_witnessed():
    # Section 8.4 example
    assert m.content_encoding_validate('gzip') == 'gzip'
    # Section 12.5.3 examples
    assert m.accept_encoding_validate('compress, gzip') == (
        'compress, gzip')
    assert m.accept_encoding_validate('') == ''
    assert m.accept_encoding_validate('*') == '*'
    assert m.accept_encoding_validate('compress;q=0.5, gzip;q=1.0')
    assert m.accept_encoding_validate(
        'gzip;q=1.0, identity; q=0.5, *;q=0')
    assert m.accept_encoding_list('compress;q=0.5, gzip;q=1.0') == (
        ('compress', '0.5'), ('gzip', '1.0'))
    assert m.accept_encoding_list('gzip;q=1.0, identity; q=0.5, *;q=0') == (
        ('gzip', '1.0'), ('identity', '0.5'), ('*', '0'))
    # Section 5.6.1.2 recipient list examples (as Content-Encoding)
    assert m.content_encoding_list('foo,bar') == ('foo', 'bar')
    assert m.content_encoding_list('foo ,bar,') == ('foo', 'bar')
    assert m.content_encoding_list('foo , ,bar,charlie') == (
        'foo', 'bar', 'charlie')


def test_str_subclass_refused_on_every_public_function():
    assert _c2(_T, _Str('gzip')) == 'bad_type:text'
    assert _c2(_C, _Str('gzip')) == 'bad_type:text'
    assert _c2(_L, _Str('gzip')) == 'bad_type:text'
    assert _c2(_A, _Str('gzip')) == 'bad_type:text'
    assert _c2(_AL, _Str('gzip')) == 'bad_type:text'
    with pytest.raises(ValueError) as e:
        m.coding_acceptable(_Str('gzip'), None)
    assert str(e.value) == _pfx() + 'coding_acceptable:bad_type:coding'
    with pytest.raises(ValueError) as e:
        m.coding_acceptable('gzip', _Str('gzip'))
    assert str(e.value) == _pfx() + 'coding_acceptable:bad_type:value'
    for fn in (_T, _C, _L, _A, _AL):
        assert _c2(fn, None) == 'bad_type:text'
        assert _c2(fn, 1) == 'bad_type:text'
        assert _c2(fn, b'x') == 'bad_type:text'


def test_tchar_slots_accept_and_refuse():
    for ch in ('!', '#', '$', '%', '&', "'", '*', '+', '-', '.',
               '^', '_', '`', '|', '~', '0', '9', 'A', 'Z', 'a', 'z'):
        assert m.coding_token_validate('x' + ch + 'y') == (
            'x' + ch + 'y'), ch
    for ch in ('"', '(', ')', ',', '/', ':', ';', '<', '=', '>',
               '?', '@', '[', '\\', ']', '{', '}', ' ', '\t', '\x00',
               '\x7f', '\xe9', '\u2028'):
        assert _c2(_T, 'x' + ch + 'y') == 'bad_value:token.char', ch
    # boundary pairs around the range-table slots
    assert m.coding_token_validate('!') == '!'
    assert _c2(_T, '"') == 'bad_value:token.char'
    assert m.coding_token_validate("#$%&'") == "#$%&'"
    assert _c2(_T, '(') == 'bad_value:token.char'
    assert _c2(_T, ')') == 'bad_value:token.char'
    assert m.coding_token_validate('*+') == '*+'
    assert _c2(_T, ',') == 'bad_value:token.char'
    assert m.coding_token_validate('-.') == '-.'
    assert _c2(_T, '/') == 'bad_value:token.char'
    assert m.coding_token_validate('09') == '09'
    assert _c2(_T, ':') == 'bad_value:token.char'
    assert m.coding_token_validate('AZ') == 'AZ'
    assert _c2(_T, '[') == 'bad_value:token.char'
    assert _c2(_T, '\\') == 'bad_value:token.char'
    assert _c2(_T, ']') == 'bad_value:token.char'
    assert m.coding_token_validate('^_`') == '^_`'
    assert m.coding_token_validate('az') == 'az'
    assert _c2(_T, '{') == 'bad_value:token.char'
    assert m.coding_token_validate('|') == '|'
    assert _c2(_T, '}') == 'bad_value:token.char'
    assert m.coding_token_validate('~') == '~'
    assert _c2(_T, '\x7f') == 'bad_value:token.char'


def test_cap_boundary_pairs():
    assert m.coding_token_validate('x' * 255) == 'x' * 255
    assert _c2(_T, 'x' * 256) == 'bad_value:field.length'
    big = ' ' + ','.join(['a' * 255] * 16)
    assert len(big) == 4096
    assert m.content_encoding_validate(big) == big
    assert m.accept_encoding_validate(big) == big
    assert _c2(_C, big + ' ') == 'bad_value:field.length'
    assert _c2(_A, big + ' ') == 'bad_value:field.length'
    assert m.content_encoding_validate(','.join(['a'] * 256))
    assert _c2(_C, ','.join(['a'] * 257)) == 'bad_value:field.count'
    assert m.accept_encoding_validate(','.join(['a'] * 256))
    assert _c2(_A, ','.join(['a'] * 257)) == 'bad_value:field.count'


def test_qvalue_shape_pins():
    for q in ('0', '0.', '0.0', '0.00', '0.000', '0.001', '0.5',
              '0.999', '1', '1.', '1.0', '1.00', '1.000'):
        assert m.accept_encoding_validate('g;q=' + q) == 'g;q=' + q, q
    # zero vs nonzero semantics: only all-zero forms mean not acceptable
    for q in ('0', '0.', '0.0', '0.00', '0.000'):
        assert m.coding_acceptable('gzip', 'gzip;q=' + q) is False, q
    for q in ('0.001', '0.01', '0.1', '1', '1.', '1.0', '1.000'):
        assert m.coding_acceptable('gzip', 'gzip;q=' + q) is True, q
    # OURS: junk after the maximal qvalue is bad_value:list, not qvalue
    assert _c2(_A, 'g;q=0.1234') == 'bad_value:list'
    assert _c2(_A, 'g;q=00') == 'bad_value:list'
    assert _c2(_A, 'g;q=1.5') == 'bad_value:list'
    assert _c2(_A, 'g;q=1.0000') == 'bad_value:list'
    assert _c2(_A, 'g;q=0.5x') == 'bad_value:list'
    assert _c2(_A, 'g;q=1.05') == 'bad_value:list'
    # malformed qvalue starts are bad_value:qvalue
    assert _c2(_A, 'g;q=') == 'bad_value:qvalue'
    assert _c2(_A, 'g;q=.5') == 'bad_value:qvalue'
    assert _c2(_A, 'g;q=2') == 'bad_value:qvalue'
    assert _c2(_A, 'g;q=x') == 'bad_value:qvalue'
    # the q parameter name is case-insensitive (Section 12.4.2)
    assert m.accept_encoding_validate('g;Q=0.5') == 'g;Q=0.5'
    assert m.accept_encoding_list('g;Q=0.5') == (('g', '0.5'),)
    assert _c2(_A, 'g;') == 'bad_value:weight'
    assert _c2(_A, 'g; ') == 'bad_value:weight'
    assert _c2(_A, 'g;q') == 'bad_value:weight'
    assert _c2(_A, 'g;x=0.5') == 'bad_value:weight'
    # no second weight and no junk after a weight
    assert _c2(_A, 'g;q=1;q=0') == 'bad_value:list'
    assert _c2(_A, 'g;q=1;') == 'bad_value:list'
    assert m.accept_encoding_validate('g;q=1 \t') == 'g;q=1 \t'


def test_identity_and_star_semantics():
    # Section 8.4: identity SHOULD NOT appear in Content-Encoding but
    # the grammar accepts it; the asterisk is a plain token there
    assert m.content_encoding_validate('identity') == 'identity'
    assert m.content_encoding_validate('*') == '*'
    # codings are case-insensitive (Section 8.4.1)
    assert m.coding_acceptable('GZIP', 'gzip') is True
    assert m.coding_acceptable('gzip', 'GZIP;Q=0') is False
    assert m.coding_acceptable('Identity', 'identity;q=0') is False
    # rule 1: absent field accepts everything valid
    assert m.coding_acceptable('gzip', None) is True
    assert m.coding_acceptable('identity', None) is True
    assert m.coding_acceptable('x-private-thing', None) is True
    # empty field value: no content coding wanted, identity acceptable
    assert m.coding_acceptable('gzip', '') is False
    assert m.coding_acceptable('identity', '') is True
    # OURS: zero contributing elements carry the empty-field meaning
    assert m.coding_acceptable('gzip', ',') is False
    assert m.coding_acceptable('gzip', ' , , ') is False
    assert m.coding_acceptable('identity', ',') is True
    # rule 2: identity exclusions
    assert m.coding_acceptable('identity', 'identity;q=0') is False
    assert m.coding_acceptable('identity', 'identity;q=0.0') is False
    assert m.coding_acceptable('identity', '*;q=0') is False
    assert m.coding_acceptable('identity', '*;q=0, identity') is True
    assert m.coding_acceptable('identity', '*;q=0, identity;q=0.001') is True
    assert m.coding_acceptable('identity', 'gzip') is True
    # rule 3: listed codings, q=0 refusal, star fallback
    assert m.coding_acceptable('gzip', 'gzip;q=0') is False
    assert m.coding_acceptable('gzip', 'gzip;q=0, gzip;q=0.5') is True
    assert m.coding_acceptable('gzip', 'gzip;q=0.5, gzip;q=0') is False
    assert m.coding_acceptable('br', 'gzip') is False
    assert m.coding_acceptable('br', 'gzip, *') is True
    assert m.coding_acceptable('br', 'gzip, *;q=0.5') is True
    assert m.coding_acceptable('br', 'gzip, *;q=0') is False
    assert m.coding_acceptable('br', 'br;q=0, *;q=0.5') is False
    assert m.coding_acceptable('br', 'br, *;q=0') is True
    # OURS: the asterisk is refused as the asked-about coding
    with pytest.raises(ValueError) as e:
        m.coding_acceptable('*', '*')
    assert str(e.value) == _pfx() + 'coding_acceptable:bad_value:coding'
    # OURS: the x- aliases are recipient guidance, not folded
    assert m.coding_acceptable('x-gzip', 'gzip') is False
    assert m.coding_acceptable('gzip', 'x-gzip') is False
    assert m.coding_acceptable('x-compress', 'compress') is False


def test_list_parsing_pins():
    # OWS around commas, empty elements ignored and not counted
    assert m.content_encoding_list(' \t gzip \t , \t br \t ') == (
        'gzip', 'br')
    assert m.content_encoding_list(',gzip,,br,') == ('gzip', 'br')
    assert m.content_encoding_validate(',') == ','
    assert m.content_encoding_validate(' , , ') == ' , , '
    assert m.content_encoding_list(' , , ') == ()
    # junk between elements
    assert _c2(_C, 'gzip br') == 'bad_value:list'
    assert _c2(_C, 'gzip;') == 'bad_value:list'
    assert _c2(_C, 'gzip:br') == 'bad_value:list'
    assert _c2(_A, 'gzip;q=1 br') == 'bad_value:list'
    # an element may not start with a non-tchar
    assert _c2(_C, '@gzip') == 'bad_value:token'
    assert _c2(_A, ';q=1') == 'bad_value:token'
    # adjacent pair: comma-separated vs whitespace-separated
    assert m.content_encoding_validate('gzip,br') == 'gzip,br'
    assert _c2(_C, 'gzip br') == 'bad_value:list'


def _c3(fn, a, b):
    with pytest.raises(ValueError) as e:
        getattr(m, fn)(a, b)
    return str(e.value)[len(_pfx() + fn + ':'):]


def test_sweep_kill_pins_rev0():
    big = ' ' + ','.join(['a' * 255] * 16)
    toks = tuple(['a' * 255] * 16)
    assert m.content_encoding_list(big) == toks
    assert m.accept_encoding_list(big) == tuple((t, None) for t in toks)
    assert _c2('content_encoding_list', big + ' ') == (
        'bad_value:field.length')
    assert _c2('accept_encoding_list', big + ' ') == (
        'bad_value:field.length')
    # 'gzip' unlisted and no '*' entry: not acceptable (12.5.3 rule 3)
    assert m.coding_acceptable('gzip', big) is False
    assert _c3('coding_acceptable', 'gzip', big + ' ') == (
        'bad_value:field.length')
    assert m.coding_acceptable('a' * 255, None) is True
    assert _c3('coding_acceptable', 'a' * 256, None) == 'bad_value:coding'
    assert _c3('coding_acceptable', '@gzip', None) == 'bad_value:coding'
    assert _c3('coding_acceptable', 'g@zip', None) == 'bad_value:coding'
    assert m.accept_encoding_list('gzip ;q=0') == (('gzip', '0'),)
    assert m.accept_encoding_list('gzip, br') == (
        ('gzip', None), ('br', None))
    assert m.coding_acceptable('gzip', 'gzip ;q=0') is False
    # A43 rev0 finding: content_encoding_list preserves element case (verbatim per docstring)
    assert m.content_encoding_list('GZip, BR') == ('GZip', 'BR')
    # A40 rev0 finding: duplicate '*' entries are last-wins too
    assert m.coding_acceptable('br', '*;q=0, *;q=0.5') is True
    assert m.coding_acceptable('br', '*;q=0.5, *;q=0') is False
    assert m.coding_acceptable('br',
                               'gzip;q=1, *;q=0, *;q=0.5') is True
    assert m.coding_acceptable('br',
                               'gzip;q=1, *;q=0.5, *;q=0') is False
    assert m.accept_encoding_list('gzipX ;q=0') == (('gzipX', '0'),)
    assert m.coding_acceptable('gzipX', 'gzipX ;q=1') is True
# ---- flattened module docstring pin ----


def test_module_docstring_whole():
    flat = ' '.join(m.__doc__.split())
    assert len(flat) == 3903
    import hashlib
    assert hashlib.sha256(flat.encode()).hexdigest() == '375251a0c22bbd0c31906dfe19745841fdc7ad3d17655d1753e3e8ce0a60fc56'


def test_module_docstring_flattened_sentences():
    flat = ' '.join(m.__doc__.split())
    for sentence in (
            'P235 batch1242: RFC 9110 content codings.',
            'ADJACENCY: the weight and qvalue grammar and the #rule list parsing are owned in general by batch1219',
            'an absent field (None) makes every valid coding acceptable',
            'Implementation guards: at most 255 characters per token, 4096 characters per field value, 256 contributing elements',
            'RFC 9110 has 14 records, none of which touches Sections 5.6, 8.4, 12.4.2 or 12.5.3',
            ):
        assert ' '.join(sentence.split()) in flat, sentence
def test_find_spec_call_count_table_per_world(undo_log):
    # every world's call list is asserted AFTER the run, raising worlds too
    src = pathlib.Path(m.__file__).read_text()
    real_import = builtins.__import__
    real_fs = iu.find_spec
    worlds = (
        ('present', 0, 'ok'),
        ('absent', 1, 'fallback'),
        ('foreign_found', 1, 'mnfe'),
        ('foreign_name', 0, 'mnfe'),
        ('name_x', 0, 'mnfe'),
        ('import_error', 0, 'ie'),
        ('named_import_error', 0, 'ie'),
    )
    for world, expected, outcome in worlds:
        _pop(undo_log, sys.modules, REG)
        calls = []
        if world == 'present':
            fake = types.ModuleType(REG)
            fake.make_fail = lambda name: (lambda code: None)
            _setitem(undo_log, sys.modules, REG, fake)

        def blocked(name, *a, **k):
            if name == REG:
                if world in ('absent', 'foreign_found'):
                    raise ModuleNotFoundError('probe', name=REG)
                if world == 'foreign_name':
                    raise ModuleNotFoundError('probe', name='x.y')
                if world == 'name_x':
                    raise ModuleNotFoundError('probe', name=REG + 'x')
                if world == 'import_error':
                    raise ImportError('probe')
                if world == 'named_import_error':
                    raise ImportError('probe', name=REG)
            return real_import(name, *a, **k)

        def fs(name, *a, **k):
            if name == REG:
                calls.append(name)
                return object() if world == 'foreign_found' else None
            return real_fs(name, *a, **k)

        _start_import(builtins, blocked)
        iu.find_spec = fs
        try:
            if outcome == 'ok':
                ns = {'__name__': 'countprobe'}
                exec(compile(src, m.__file__, 'exec'), ns)
                assert ns['coding_token_validate']('gzip') == 'gzip'
            elif outcome == 'fallback':
                ns = {'__name__': 'countprobe'}
                exec(compile(src, m.__file__, 'exec'), ns)
                with pytest.raises(ValueError):
                    ns['coding_token_validate'](None)
            elif outcome == 'mnfe':
                with pytest.raises(ModuleNotFoundError):
                    exec(compile(src, m.__file__, 'exec'),
                         {'__name__': 'countprobe'})
            else:
                with pytest.raises(ImportError) as caught:
                    exec(compile(src, m.__file__, 'exec'),
                         {'__name__': 'countprobe'})
                if world == 'import_error':
                    assert type(caught.value) is ImportError
        finally:
            _stop_import()
            iu.find_spec = real_fs
        assert calls == [REG] * expected, (world, calls)


# ---- helper and range pins ----


def test_range_tables_exact():
    assert m._TCHAR == ((33, 33), (35, 39), (42, 43), (45, 46),
                        (48, 57), (65, 90), (94, 96), (97, 122),
                        (124, 124), (126, 126))
    assert m._OWS == ((9, 9), (32, 32))
    assert m._DIG == ((48, 57),)
    for code in (33, 35, 36, 37, 38, 39, 42, 43, 45, 46, 48, 57, 65,
                 90, 94, 95, 96, 97, 122, 124, 126):
        assert m._in(code, m._TCHAR), code
    for code in (32, 34, 40, 41, 44, 47, 58, 59, 60, 61, 62, 63, 64,
                 91, 92, 93, 123, 125, 127, 9, 0):
        assert not m._in(code, m._TCHAR), code
    assert m._in(9, m._OWS) and m._in(32, m._OWS)
    assert not m._in(8, m._OWS) and not m._in(10, m._OWS)
    assert not m._in(33, m._OWS) and not m._in(13, m._OWS)


def test_fold_and_folded_exact():
    assert m._fold('a') == 'a' and m._fold('A') == 'a'
    assert m._fold('Z') == 'z' and m._fold('z') == 'z'
    assert m._fold('*') == '*' and m._fold('@') == '@'
    assert m._fold('[') == '[' and m._fold('`') == '`'
    assert m._folded('GzIp-9') == 'gzip-9'
    assert m._folded('') == ''


def test_ows_and_token_offsets():
    assert m._ows_end(' \t x', 0) == 3
    assert m._ows_end('', 0) == 0
    assert m._ows_end('x', 0) == 0
    assert m._ows_end(' \r x', 0) == 1
    f = m.make_fail('probe')
    assert m._token_end(f, 'gzip,br', 0) == 4
    assert m._token_end(f, 'gzip,br', 5) == 7
    with pytest.raises(ValueError) as e:
        m._token_end(f, ',g', 0)
    assert str(e.value).endswith('probe:bad_value:token')
    with pytest.raises(ValueError) as e:
        m._token_end(f, 'x' * 300, 0)
    assert str(e.value).endswith('probe:bad_value:field.length')


def test_qvalue_and_weight_offsets():
    f = m.make_fail('probe')
    assert m._qvalue_end(f, '0.5', 0) == 3
    assert m._qvalue_end(f, '0', 0) == 1
    assert m._qvalue_end(f, '1.000', 0) == 5
    assert m._qvalue_end(f, '1.0000', 0) == 5
    assert m._qvalue_end(f, '0.1234', 0) == 5
    assert m._qvalue_end(f, '1.', 0) == 2
    assert m._qvalue_end(f, '0.', 0) == 2
    assert m._qvalue_end(f, '1.5', 0) == 2
    with pytest.raises(ValueError) as e:
        m._qvalue_end(f, '2', 0)
    assert str(e.value).endswith('probe:bad_value:qvalue')
    with pytest.raises(ValueError) as e:
        m._qvalue_end(f, '', 0)
    assert str(e.value).endswith('probe:bad_value:qvalue')
    assert m._weight_end(f, ';q=0.5', 0) == 6
    assert m._weight_end(f, '; Q=1', 0) == 5
    with pytest.raises(ValueError) as e:
        m._weight_end(f, ';x=1', 0)
    assert str(e.value).endswith('probe:bad_value:weight')
    with pytest.raises(ValueError) as e:
        m._weight_end(f, ';q', 0)
    assert str(e.value).endswith('probe:bad_value:weight')


def test_qzero_exact():
    for q in ('0', '0.', '0.0', '0.00', '0.000'):
        assert m._qzero(q) is True, q
    for q in ('1', '1.', '1.0', '0.1', '0.001', '0.010', '0.5'):
        assert m._qzero(q) is False, q


def test_list_offsets_and_count():
    f = m.make_fail('probe')
    spans = []
    m._list(f, 'a, b,,c', False, spans)
    assert spans == [(0, 1), (3, 4), (6, 7)]
    spans = []
    m._list(f, '', False, spans)
    assert spans == []
    spans = []
    m._list(f, ' , ', False, spans)
    assert spans == []
    with pytest.raises(ValueError) as e:
        m._list(f, ','.join(['a'] * 257), False, [])
    assert str(e.value).endswith('probe:bad_value:field.count')
    with pytest.raises(ValueError) as e:
        m._list(f, 'a b', False, [])
    assert str(e.value).endswith('probe:bad_value:list')
