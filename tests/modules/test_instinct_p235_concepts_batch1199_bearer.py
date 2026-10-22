import ast
import builtins
import os
import importlib.util as iu
import pathlib
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
        p235_concepts_batch1199_bearer as mod)
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


class _DictSub(dict):
    pass


class _ListSub(list):
    pass


CR = 'bearer_credentials_parse'
CH = 'bearer_challenge_parse'

_B64_CHARS = ('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstu'
              'vwxyz0123456789-._~+/')

_SUCC_CACHE = None
_REFU_CACHE = None


def _success_corpus():
    global _SUCC_CACHE
    if _SUCC_CACHE is None:
        s = [(CR, ('Bearer mF_9.B5f-4.1JqM',)),
             (CR, ('Bearer A',)),
             (CR, ('Bearer ' + _B64_CHARS + '==',)),
             (CR, ('Bearer   spaced',)),
             (CH, ([('realm', 'example')],)),
             (CH, ({'realm': 'example'},)),
             (CH, ([('realm', 'example'),
                    ('error', 'invalid_token'),
                    ('error_description', 'The access token expired')],)),
             (CH, ([('scope', 'openid profile email')],)),
             (CH, ([('scope', 'urn:example:channel=HBO&'
                     'urn:example:rating=G,PG-13')],)),
             (CH, ([('error_uri', 'https://as.example/errors/1')],)),
             (CH, ([('x-ext', 'anything \x7f goes')],)),
             (CH, ([('x-a', '1'), ('x-a', '2')],)),
             (CH, ([('realm', '')],))]
        _SUCC_CACHE = s
    return _SUCC_CACHE


def _refusal_corpus():
    global _REFU_CACHE
    if _REFU_CACHE is None:
        c = []
        for bad in (None, 0, 1, True, False, 5.5, b'Bearer A',
                    ['Bearer A'], {'x': 1}, (1,),
                    _StrSub('Bearer A')):
            c.append((CR, 'bad_type:credentials.type', bad))
        c.append((CR, 'bad_value:credentials.length',
                  'Bearer ' + 'A' * 65536))
        for bad in ('bearer A', 'BEARER A', 'Bearer', 'BearerX',
                    'Bearer\tA', ' Bearer A', 'Bear A', 'BearerA'):
            c.append((CR, 'bad_value:credentials.scheme', bad))
        for bad in ('Bearer ', 'Bearer   '):
            c.append((CR, 'bad_value:credentials.token.empty', bad))
        for bad in ('Bearer =', 'Bearer ==', 'Bearer ab=c',
                    'Bearer a$', 'Bearer a%', 'Bearer a*',
                    'Bearer a\xe9', 'Bearer a b', 'Bearer a\tb',
                    'Bearer "x"', 'Bearer a\\b', 'Bearer a=b',
                    'Bearer =ab'):
            c.append((CR, 'bad_value:credentials.token.char', bad))
        for bad in (None, 0, 'realm="example"',
                    [('realm', 'example', 'x')], [('realm',)],
                    [(1, 'example')], [('realm', 1)], ['realm'],
                    [None]):
            c.append((CH, 'bad_type:challenge.type', bad)
                     if not isinstance(bad, list)
                     else (CH, 'bad_type:challenge.pair', bad))
        c.append((CH, 'bad_type:challenge.type',
                  _DictSub({'realm': 'example'})))
        c.append((CH, 'bad_type:challenge.type',
                  _ListSub([('realm', 'example')])))
        c.append((CH, 'bad_value:challenge.empty', []))
        c.append((CH, 'bad_value:challenge.empty', {}))
        c.append((CH, 'bad_value:challenge.params.length',
                  [('x%d' % i, 'v') for i in range(257)]))
        for bad in ('', 'a b', 'a"b', 'a\\b', '\xe9', '(x)', 'x\ty',
                    'a=b', 'a,b', 'a;b', 'a\x7f'):
            c.append((CH, 'bad_value:param.name', [(bad, 'v')]))
        c.append((CH, 'bad_value:param.value.length',
                  [('x', 'A' * 65537)]))
        for name in ('realm', 'scope', 'error', 'error_description',
                     'error_uri'):
            c.append((CH, 'bad_value:%s.duplicate' % name,
                      [(name, 'a'), (name, 'b')]))
        for bad in ('', ' a', 'a ', 'a  b', ' '):
            c.append((CH, 'bad_value:scope.token',
                      [('scope', bad)]))
        for bad in ('a"b', 'a\\b', 'a\x7fb', 'a\x1fb', 'a\xe9b'):
            c.append((CH, 'bad_value:scope.value', [('scope', bad)]))
        for name in ('error', 'error_description'):
            for bad in ('', 'a"b', 'a\\b', 'a\x7fb', 'a\xe9b',
                        'a\x1fb'):
                c.append((CH, 'bad_value:%s.value' % name,
                          [(name, bad)]))
        for bad in ('', 'a b', 'a"b', 'a\\b', 'a\x7fb', 'a\xe9b'):
            c.append((CH, 'bad_value:error_uri.value',
                      [('error_uri', bad)]))
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
        _bounded_call(CR, 'Bearer ' + 'A' * 65535)
    except ValueError:
        pass
    else:
        raise AssertionError('cap-length input must not be reached '
                             'here or must refuse only by the cap')


def test_module_docstring_is_pinned_whole():
    assert m.__doc__ == __DOC__


def test_rfc_s2_1_example():
    assert m.bearer_credentials_parse('Bearer mF_9.B5f-4.1JqM') == {
        'scheme': 'Bearer', 'token': 'mF_9.B5f-4.1JqM'}


def test_rfc_s3_examples():
    # s3: the no-authentication challenge
    r = m.bearer_challenge_parse([('realm', 'example')])
    assert r['params'] == [('realm', 'example')]
    assert r['realm'] == 'example'
    assert r['scope'] is None and r['error'] is None
    # the full result key set and absent-None for all five
    # named attributes (A33)
    assert set(r) == {'params', 'realm', 'scope', 'error',
                      'error_description', 'error_uri'}
    assert r['error_description'] is None
    assert r['error_uri'] is None
    # s3: the expired-token challenge
    r = m.bearer_challenge_parse(
        [('realm', 'example'), ('error', 'invalid_token'),
         ('error_description', 'The access token expired')])
    assert r['realm'] == 'example'
    assert r['error'] == 'invalid_token'
    assert r['error_description'] == 'The access token expired'
    # s3: both printed scope examples
    # the accepted present error_uri value lands in the
    # output map (A33), with the other named attrs absent-None
    r = m.bearer_challenge_parse(
        [('realm', 'example'), ('error', 'invalid_token'),
         ('error_uri', 'https://as.example/errors/1')])
    assert r['error_uri'] == 'https://as.example/errors/1'
    assert set(r) == {'params', 'realm', 'scope', 'error',
                      'error_description', 'error_uri'}
    assert r['scope'] is None
    assert r['error_description'] is None
    # s3: both printed scope examples
    assert m.bearer_challenge_parse(
        [('scope', 'openid profile email')])['scope'] == [
        'openid', 'profile', 'email']
    assert m.bearer_challenge_parse(
        [('scope', 'urn:example:channel=HBO&'
          'urn:example:rating=G,PG-13')])['scope'] == [
        'urn:example:channel=HBO&urn:example:rating=G,PG-13']


def test_credentials_grammar():
    # 1*SP: more than one SP is fine
    assert m.bearer_credentials_parse('Bearer   x')['token'] == 'x'
    # the full b64token alphabet plus a trailing "=" run
    tok = _B64_CHARS + '==='
    assert m.bearer_credentials_parse(
        'Bearer ' + tok)['token'] == tok
    # one character is enough; zero "=" is fine, many are fine
    assert m.bearer_credentials_parse('Bearer A')['token'] == 'A'
    assert m.bearer_credentials_parse(
        'Bearer A========')['token'] == 'A========'
    # exactly at the input cap the parse still succeeds
    ok = 'Bearer ' + 'A' * (65536 - 7)
    assert m.bearer_credentials_parse(ok)['token'] == 'A' * (65536 - 7)
    refuse(CR, 'bad_value:credentials.length', ok + 'A')


def test_credentials_refusals():
    for fn_name, code, bad in _refusal_corpus():
        if fn_name == CR:
            refuse(fn_name, code, bad)


def test_challenge_extension_policy():
    # unknown attributes pass with any string value, repeat freely
    r = m.bearer_challenge_parse(
        [('x-ext', 'a'), ('x-ext', 'b'), ('OTHER', 'c d e')])
    assert r['params'] == [('x-ext', 'a'), ('x-ext', 'b'),
                           ('OTHER', 'c d e')]
    assert r['realm'] is None


def test_challenge_dict_input_matches_pair_list():
    d = {'realm': 'example', 'error': 'invalid_token'}
    assert m.bearer_challenge_parse(d) == m.bearer_challenge_parse(
        list(d.items()))


def test_challenge_duplicates():
    for name in ('realm', 'scope', 'error', 'error_description',
                 'error_uri'):
        refuse(CH, 'bad_value:%s.duplicate' % name,
               [(name, 'a'), (name, 'b')])
    # unknown names may repeat
    m.bearer_challenge_parse([('x', 'a'), ('x', 'b')])


def test_challenge_value_rules():
    # scope structure: single SP delimiters, non-empty tokens
    assert m.bearer_challenge_parse([('scope', 'a b c')])[
        'scope'] == ['a', 'b', 'c']
    # boundary characters accepted where the charset allows
    m.bearer_challenge_parse([('error', 'a b!c#d[e]f~g')])
    m.bearer_challenge_parse([('error_description', '! # [ ] ~')])
    m.bearer_challenge_parse([('error_uri', '!#[]~')])
    m.bearer_challenge_parse([('scope', '!#[]~')])
    m.bearer_challenge_parse([('scope', 'a!b#c[d]e~f')])
    for fn_name, code, bad in _refusal_corpus():
        if fn_name == CH:
            refuse(fn_name, code, bad)


def test_challenge_caps():
    # exactly at the caps: accepted; one past: refused
    m.bearer_challenge_parse([('x%d' % i, 'v') for i in range(256)])
    refuse(CH, 'bad_value:challenge.params.length',
           [('x%d' % i, 'v') for i in range(257)])
    m.bearer_challenge_parse([('realm', 'A' * 65536)])
    refuse(CH, 'bad_value:param.value.length',
           [('realm', 'A' * 65537)])


def test_return_values_are_fresh():
    a = m.bearer_challenge_parse([('scope', 'a b')])
    a['scope'].append('MUTATED')
    a['params'].append(('x', 'y'))
    b = m.bearer_challenge_parse([('scope', 'a b')])
    assert b['scope'] == ['a', 'b']
    assert b['params'] == [('scope', 'a b')]
    assert a is not b


def test_exact_refusal_codes():
    refuse(CR, 'bad_value:credentials.scheme', 'Basic abc')
    refuse(CH, 'bad_value:challenge.empty', [])


def test_refusal_order():
    # credentials: type before length before scheme before token
    refuse(CR, 'bad_type:credentials.type', 0)
    refuse(CR, 'bad_value:credentials.length',
           'X' * 65537)
    refuse(CR, 'bad_value:credentials.scheme', 'Bearer\tA')
    refuse(CR, 'bad_value:credentials.token.empty', 'Bearer ')
    refuse(CR, 'bad_value:credentials.token.char', 'Bearer =')
    # challenge: type before pair shape before empty before count
    refuse(CH, 'bad_type:challenge.type', 0)
    refuse(CH, 'bad_type:challenge.pair', [('a', 'b', 'c')])
    refuse(CH, 'bad_value:challenge.empty', [])
    refuse(CH, 'bad_value:challenge.params.length',
           [('bad name', 'v')] * 257)
    # per pair: name before value-cap before duplicate before value
    refuse(CH, 'bad_value:param.name', [('bad name', '\xe9')])
    refuse(CH, 'bad_value:param.name',
           [('a b', 'x' * 65537)])
    refuse(CH, 'bad_value:param.value.length',
           [('error', 'A' * 65537)])
    refuse(CH, 'bad_value:error.duplicate',
           [('error', 'ok'), ('error', '\xe9')])
    refuse(CH, 'bad_value:error.value', [('error', '\xe9')])


def test_is_valid_returns_exact_bool():
    v = m.bearer_credentials_is_valid('Bearer A')
    assert v is True and type(v) is bool
    assert m.bearer_credentials_is_valid('nope') is False
    assert m.bearer_credentials_is_valid(None) is False
    assert m.bearer_challenge_is_valid([('realm', 'x')]) is True
    assert m.bearer_challenge_is_valid([]) is False
    assert m.bearer_challenge_is_valid(0) is False


def test_constants_pinned_whole():
    assert m._MAX_INPUT_LENGTH == 65536
    assert m._MAX_PARAMS == 256
    assert m._MAX_VALUE_LENGTH == 65536
    assert m._B64TOKEN == frozenset(_B64_CHARS)
    assert m._SCOPE_CHAR == frozenset(
        chr(c) for c in tuple(range(0x21, 0x22))
        + tuple(range(0x23, 0x5C)) + tuple(range(0x5D, 0x7F)))
    assert m._NQSCHAR == frozenset(
        chr(c) for c in tuple(range(0x20, 0x22))
        + tuple(range(0x23, 0x5C)) + tuple(range(0x5D, 0x7F)))
    assert m._URI_REF_CHAR == m._SCOPE_CHAR
    assert m._SEPARATORS == frozenset('()<>@,;:\\"/[]?={} \t')


def test_function_docstrings_pinned_exact():
    assert m.bearer_credentials_parse.__doc__ == (
        'Validate s2.1 Bearer credentials; return scheme and token.')
    assert m.bearer_credentials_is_valid.__doc__ == (
        'True iff bearer_credentials_parse(text) would succeed.')
    assert m.bearer_challenge_parse.__doc__ == (
        'Validate s3 Bearer challenge auth-params; return the map.')
    assert m.bearer_challenge_is_valid.__doc__ == (
        'True iff bearer_challenge_parse(params) would succeed.')


def test_module_namespace_is_pinned():
    names = set(vars(m))
    assert names == {
        '__name__', '__doc__', '__package__', '__loader__',
        '__spec__', '__file__', '__cached__', '__builtins__',
        'find_spec', 'make_fail',
        '_MAX_INPUT_LENGTH', '_MAX_PARAMS', '_MAX_VALUE_LENGTH',
        '_B64TOKEN', '_SCOPE_CHAR', '_NQSCHAR', '_URI_REF_CHAR',
        '_SEPARATORS', '_is_token_name', '_check_scope',
        '_check_charset',
        'bearer_credentials_parse', 'bearer_credentials_is_valid',
        'bearer_challenge_parse', 'bearer_challenge_is_valid'}


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
                getattr(m, fn_name)(d)
            except ValueError as caught:
                raised = caught
            assert raised is not None, (fn_name, code)
    finally:
        sys.settrace(None)
    # no exemptions: every f() site in the module is corpus-reached
    assert f_lines <= hits, sorted(f_lines - hits)


def test_short_inputs():
    for bad in ('', 'B', 'Bearer', 'Bearer ', 'Bearer  ',
                'Bearer=', 'Bear', 'bearer a'):
        try:
            getattr(m, CR)(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('short input accepted: %r' % bad)


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
                + [(fn, (d,)) for fn, code, d in
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

def test_battery_rev0_pins():
    # the s2.1 grammar is 1*SP: exactly one SP is the minimum
    refuse(CR, 'bad_value:credentials.scheme', 'Bearer')
    # "=" may only trail: any content after "=" refuses
    refuse(CR, 'bad_value:credentials.token.char', 'Bearer ab=c')
    refuse(CR, 'bad_value:credentials.token.char', 'Bearer =')
    # b64token per-character pins at both flanks of the alphabet
    refuse(CR, 'bad_value:credentials.token.char', 'Bearer a\x60')
    refuse(CR, 'bad_value:credentials.token.char', 'Bearer a\x7b')
    refuse(CR, 'bad_value:credentials.token.char', 'Bearer a\x40')
    m.bearer_credentials_parse('Bearer ~-._+/')
    # case-sensitive scheme and attribute names (OURS)
    refuse(CR, 'bad_value:credentials.scheme', 'bearer A')
    refuse(CH, 'bad_value:param.name', [('REA LM', 'x')])
    # token-name boundary acceptance: 0x21 '!' and 0x7E '~' are
    # CHAR, not CTLs and not separators, so names containing
    # them are well-formed (RFC 2617 token)
    r = m.bearer_challenge_parse([('a!b', 'v'), ('a~b', 'w')])
    assert r['params'] == [('a!b', 'v'), ('a~b', 'w')]
    m.bearer_challenge_parse([('!', 'v'), ('~', 'v')])
    r = m.bearer_challenge_parse([('REALM', 'x')])
    assert r['realm'] is None  # unknown attribute, not folded
    # str subclasses refuse with the type code
    refuse(CR, 'bad_type:credentials.type', _StrSub('Bearer A'))
    refuse(CH, 'bad_type:challenge.pair',
           [(_StrSub('realm'), 'x')])
    refuse(CH, 'bad_type:challenge.pair',
           [('realm', _StrSub('x'))])


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
        mod = types.ModuleType('fresh_b1199')
        with pytest.raises(ModuleNotFoundError):
            exec(compile(src, 'fresh_b1199', 'exec'), mod.__dict__)
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
            ('import no_such_dep_xyz_1199\n', 'ModuleNotFoundError'),
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
        mod = types.ModuleType('fresh_b1199_spy')
        exec(compile(src, 'fresh_b1199_spy', 'exec'), mod.__dict__)
    finally:
        _stop_import()
        _iu.find_spec = real_find_spec
    assert calls == [REG], calls
    # the fallback engaged and works
    assert mod.bearer_credentials_is_valid('Bearer A') is True
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        assert str(e) == 'P235:x:c'
    else:
        raise AssertionError('fallback make_fail did not raise')


__DOC__ = 'RFC 6750 "The OAuth 2.0 Authorization Framework: Bearer Token\nUsage": the s2.1 "Authorization" request header credentials\ngrammar ("Bearer" 1*SP b64token) and the s3\n"WWW-Authenticate" Bearer challenge auth-parameter rules\n(realm, scope, error, error_description, error_uri, plus the\nextension policy) over a Python text string and a decoded\nparameter map.  Form-encoded (s2.2) and URI-query (s2.3)\ntransmission, HTTP header parsing/quoting itself, token\nissuance (s4) and the security considerations (s5) are out\nof scope.\n\nPublic API:\n\n  bearer_credentials_parse(text) -> a dict:\n      \'scheme\': the string "Bearer",\n      \'token\': the b64token text.\n  bearer_credentials_is_valid(text) -> True iff\n      bearer_credentials_parse would succeed.\n  bearer_challenge_parse(params) -> a dict:\n      \'params\': every auth-param as (name, value) pairs in\n      document order,\n      \'realm\', \'error\', \'error_description\', \'error_uri\':\n      the decoded value of that attribute, or None when\n      absent,\n      \'scope\': the decoded "scope" value split into its\n      scope-token list, or None when absent.\n      params is the DECODED auth-parameter map: either a\n      dict mapping attribute name to value, or a list of\n      (name, value) pairs in document order (a dict cannot\n      express a repeated attribute, which s3 forbids for the\n      five named attributes, so the pair-list form keeps\n      that rule checkable).\n  bearer_challenge_is_valid(params) -> True iff\n      bearer_challenge_parse would succeed.\n\nGrammar notes (verified against the RFC 6750 text): the\ncredentials grammar is printed in s2.1:\n\n  b64token    = 1*( ALPHA / DIGIT /\n                    "-" / "." / "_" / "~" / "+" / "/" ) *"="\n  credentials = "Bearer" 1*SP b64token\n\nwith the s2.1 note that, "as with Basic, it does not conform\nto the generic syntax defined in Section 1.2 of [RFC2617]".\nThe challenge rules (s3): all challenges "MUST use the\nauth-scheme value "Bearer".  This scheme MUST be followed by\none or more auth-param values", so an empty parameter map\nrefuses.  "A "realm" attribute ... MUST NOT appear more than\nonce"; the "scope" attribute "is defined in Section 3.3 of\n[RFC6749]" as "a space-delimited list of case-sensitive\nscope values", is OPTIONAL, and "MUST NOT appear more than\nonce"; ""error", "error_description", and "error_uri"\nattributes MUST NOT appear more than once".  "Other\nauth-param attributes MAY be used as well", so unknown\nattribute names pass with any string value.  The value\ncharsets quoted in s3: "scope" values "MUST NOT include\ncharacters outside the set %x21 / %x23-5B / %x5D-7E for\nrepresenting scope values and %x20 for delimiters between\nscope values"; "error" and "error_description" values "MUST\nNOT include characters outside the set %x20-21 / %x23-5B /\n%x5D-7E"; "error_uri" values "MUST conform to the\nURI-reference syntax and thus MUST NOT include characters\noutside the set %x21 / %x23-5B / %x5D-7E".  The underlying\n[RFC6749] ABNF (Appendixes A.4, A.7, A.8) makes the\nscope, error and error-description values non-empty:\nscope = scope-token *( SP scope-token ) with scope-token =\n1*NQCHAR, error = 1*NQSCHAR, error-description = 1*NQSCHAR.\nA.9 gives error-uri = URI-reference, which CAN be empty\nunder RFC 3986 (relative-ref reduces to path-empty), so\nthe non-emptiness of error_uri is OURS, not from the ABNF.  s3.1 lists the defined "error" codes\ninvalid_request, invalid_token and insufficient_scope, but\n[RFC6749] s11.4 (the OAuth Extensions Error\nRegistry) keeps the "error" space extensible, so\nmembership is not enforced; the charset is.  The "realm"\nvalue carries no s3 charset rule (its wire quoting is the\nHTTP layer\'s business), so any decoded string passes,\nincluding the empty string.\n\nProfile decisions (OURS, not from the RFC text):\n  - The "Bearer" scheme token is matched exactly as printed;\n    no case-folding (s2.1 prints the literal and notes the\n    grammar deliberately deviates from the generic\n    framework).\n  - Challenge attribute names are matched case-sensitively;\n    RFC 6750 gives no case-folding rule for the decoded\n    names, and any HTTP-layer folding is the wire parser\'s\n    concern.\n  - Attribute names must have the RFC 2617 "token" shape\n    (the framework s3 points at): one or more %x21-7E\n    characters excluding the separators ( ) < > @ , ; : \\ "\n    / [ ] ? = { } SP; anything else refuses\n    bad_value:param.name.  This applies to unknown attribute\n    names too; their VALUES are unconstrained.\n  - "error_uri" is checked for the s3 character set and\n    non-emptiness only; full RFC 3986 URI-reference\n    validation is out of scope.\n  - Only the exact str type is accepted for the credentials\n    text and for names and values; subclasses refuse with\n    the type code.  The same exact-type discipline covers\n    the challenge container: only the exact dict or list\n    types are accepted; dict or list subclasses refuse\n    bad_type:challenge.type.\n  - Size caps (OURS): _MAX_INPUT_LENGTH characters for the\n    credentials text, _MAX_PARAMS parameters and\n    _MAX_VALUE_LENGTH characters per value in a challenge.\n\nRefusal order: bad_type before everything; for credentials,\nthe overall length cap, then the "Bearer" + 1*SP prefix\n(bad_value:credentials.scheme), then the token\n(bad_value:credentials.token.empty before\nbad_value:credentials.token.char); for a challenge, the map\ntype, the pair shapes, the empty map, the parameter-count\ncap, then per pair in document order: the attribute-name\nrule, the value length cap, the duplicate rule for the five\nnamed attributes (its code at the second occurrence), then\nthe attribute\'s own value rule.\n\nErrata (4 records, all Reported, none folded): Reported EID\n5335 (s2.1, Technical) proposes renaming "b64token" to\n"token68" to match RFC 7235 and avoid base64 confusion: a\nnaming preference against the printed grammar, so the\ngrammar keeps the printed name.  Reported EID 6161 (s4,\nEditorial), Reported EID 9053 (s5.1, Technical) and\nReported EID 9054 (s5.1, Technical) all drop the\n"charset=UTF-8" parameter from the example token response\'s\napplication/json Content-Type: examples of token ISSUANCE,\nnot the validated request/challenge grammar.  ZERO Verified\nerrata exist for RFC 6750.\n'
