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

REG = 'app.modules.instinct_doc.p235_concepts_registry'


@pytest.fixture(scope='module', autouse=True)
def load_module():
    global m
    from app.modules.instinct_doc import (
        p235_concepts_batch1224_jwa_names as mod)
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


JA = 'jws_alg_parse'
KA = 'jwe_alg_parse'
JE = 'jwe_enc_parse'

# Independent transcriptions of the RFC 7518 tables: (algorithm,
# implementation) for JWS "alg" (s3.1) and JWE "enc" (s5.1),
# (algorithm, more-header-params, implementation) for JWE "alg"
# (s4.1).
JWS_TABLE = {
    'HS256': ('HMAC using SHA-256', 'Required'),
    'HS384': ('HMAC using SHA-384', 'Optional'),
    'HS512': ('HMAC using SHA-512', 'Optional'),
    'RS256': ('RSASSA-PKCS1-v1_5 using SHA-256', 'Recommended'),
    'RS384': ('RSASSA-PKCS1-v1_5 using SHA-384', 'Optional'),
    'RS512': ('RSASSA-PKCS1-v1_5 using SHA-512', 'Optional'),
    'ES256': ('ECDSA using P-256 and SHA-256', 'Recommended+'),
    'ES384': ('ECDSA using P-384 and SHA-384', 'Optional'),
    'ES512': ('ECDSA using P-521 and SHA-512', 'Optional'),
    'PS256': ('RSASSA-PSS using SHA-256 and MGF1 with SHA-256',
              'Optional'),
    'PS384': ('RSASSA-PSS using SHA-384 and MGF1 with SHA-384',
              'Optional'),
    'PS512': ('RSASSA-PSS using SHA-512 and MGF1 with SHA-512',
              'Optional'),
    'none': ('No digital signature or MAC performed', 'Optional'),
}

JWE_TABLE = {
    'RSA1_5': ('RSAES-PKCS1-v1_5', (), 'Recommended-'),
    'RSA-OAEP': ('RSAES OAEP using default parameters', (),
                 'Recommended+'),
    'RSA-OAEP-256': ('RSAES OAEP using SHA-256 and MGF1 with'
                     ' SHA-256', (), 'Optional'),
    'A128KW': ('AES Key Wrap with default initial value using'
               ' 128-bit key', (), 'Recommended'),
    'A192KW': ('AES Key Wrap with default initial value using'
               ' 192-bit key', (), 'Optional'),
    'A256KW': ('AES Key Wrap with default initial value using'
               ' 256-bit key', (), 'Recommended'),
    'dir': ('Direct use of a shared symmetric key as the CEK', (),
            'Recommended'),
    'ECDH-ES': ('Elliptic Curve Diffie-Hellman Ephemeral Static'
                ' key agreement using Concat KDF',
                ('epk', 'apu', 'apv'), 'Recommended+'),
    'ECDH-ES+A128KW': ('ECDH-ES using Concat KDF and CEK wrapped'
                       ' with "A128KW"', ('epk', 'apu', 'apv'),
                       'Recommended'),
    'ECDH-ES+A192KW': ('ECDH-ES using Concat KDF and CEK wrapped'
                       ' with "A192KW"', ('epk', 'apu', 'apv'),
                       'Optional'),
    'ECDH-ES+A256KW': ('ECDH-ES using Concat KDF and CEK wrapped'
                       ' with "A256KW"', ('epk', 'apu', 'apv'),
                       'Recommended'),
    'A128GCMKW': ('Key wrapping with AES GCM using 128-bit key',
                  ('iv', 'tag'), 'Optional'),
    'A192GCMKW': ('Key wrapping with AES GCM using 192-bit key',
                  ('iv', 'tag'), 'Optional'),
    'A256GCMKW': ('Key wrapping with AES GCM using 256-bit key',
                  ('iv', 'tag'), 'Optional'),
    'PBES2-HS256+A128KW': ('PBES2 with HMAC SHA-256 and'
                           ' "A128KW" wrapping', ('p2s', 'p2c'),
                           'Optional'),
    'PBES2-HS384+A192KW': ('PBES2 with HMAC SHA-384 and'
                           ' "A192KW" wrapping', ('p2s', 'p2c'),
                           'Optional'),
    'PBES2-HS512+A256KW': ('PBES2 with HMAC SHA-512 and'
                           ' "A256KW" wrapping', ('p2s', 'p2c'),
                           'Optional'),
}

ENC_TABLE = {
    'A128CBC-HS256': ('AES_128_CBC_HMAC_SHA_256 authenticated'
                      ' encryption algorithm, as defined in'
                      ' Section 5.2.3', 'Required'),
    'A192CBC-HS384': ('AES_192_CBC_HMAC_SHA_384 authenticated'
                      ' encryption algorithm, as defined in'
                      ' Section 5.2.4', 'Optional'),
    'A256CBC-HS512': ('AES_256_CBC_HMAC_SHA_512 authenticated'
                      ' encryption algorithm, as defined in'
                      ' Section 5.2.5', 'Required'),
    'A128GCM': ('AES GCM using 128-bit key', 'Recommended'),
    'A192GCM': ('AES GCM using 192-bit key', 'Optional'),
    'A256GCM': ('AES GCM using 256-bit key', 'Recommended'),
}

_SUCC_CACHE = None
_REFU_CACHE = None


def _success_corpus():
    global _SUCC_CACHE
    if _SUCC_CACHE is None:
        s = []
        for name in JWS_TABLE:
            s.append((JA, (name,)))
        for name in JWE_TABLE:
            s.append((KA, (name,)))
        for name in ENC_TABLE:
            s.append((JE, (name,)))
        _SUCC_CACHE = s
    return _SUCC_CACHE


def _kind(fn_name):
    return 'enc' if fn_name == JE else 'alg'


def _refusal_corpus():
    global _REFU_CACHE
    if _REFU_CACHE is None:
        c = []
        for fn in (JA, KA, JE):
            k = _kind(fn)
            for bad in (None, 0, 1, True, False, 5.5, b'HS256',
                        ['HS256'], {'x': 1}, (1,), _StrSub('HS256')):
                c.append((fn, 'bad_type:%s.type' % k, bad))
            for bad in ('\xe9', 'HS25\xe9', 'A128GCM\u0100',
                        'HS25\x80', '\U0001F600'):
                c.append((fn, 'bad_value:%s.ascii' % k, bad))
            for bad in ('', 'HS255', 'hs256', 'HS256 ', ' HS256',
                        'HS25\x7f', 'NONE', 'None', 'none ',
                        'A128GCMKW2', 'ECDH-ES+ A128KW',
                        'ECDH-ES +A128KW', 'RSA-OAEP-257', 'dir2'):
                c.append((fn, 'bad_value:%s.unknown' % k, bad))
        # cross-table refusals: registered in one table, unknown in
        # the others
        for name in JWS_TABLE:
            c.append((KA, 'bad_value:alg.unknown', name))
            c.append((JE, 'bad_value:enc.unknown', name))
        for name in JWE_TABLE:
            c.append((JA, 'bad_value:alg.unknown', name))
            c.append((JE, 'bad_value:enc.unknown', name))
        for name in ENC_TABLE:
            c.append((JA, 'bad_value:alg.unknown', name))
            c.append((KA, 'bad_value:alg.unknown', name))
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
    # the per-character ASCII scan must terminate on long junk too
    try:
        _bounded_call(JA, 'Z' * 100000)
    except ValueError:
        pass
    else:
        raise AssertionError('long junk name must refuse')


def test_module_docstring_is_pinned_whole():
    assert m.__doc__ == __DOC__


def test_jws_alg_table_whole():
    assert len(JWS_TABLE) == 13
    for name, (algorithm, implementation) in JWS_TABLE.items():
        assert m.jws_alg_parse(name) == {
            'name': name, 'algorithm': algorithm,
            'implementation': implementation}


def test_jwe_alg_table_whole():
    assert len(JWE_TABLE) == 17
    for name, (algorithm, params, implementation) in (
            JWE_TABLE.items()):
        assert m.jwe_alg_parse(name) == {
            'name': name, 'algorithm': algorithm,
            'more_header_params': list(params),
            'implementation': implementation}


def test_jwe_enc_table_whole():
    assert len(ENC_TABLE) == 6
    for name, (algorithm, implementation) in ENC_TABLE.items():
        assert m.jwe_enc_parse(name) == {
            'name': name, 'algorithm': algorithm,
            'implementation': implementation}


def test_none_handling_s3_6_and_rfc8725_s3_2():
    # "none" is a registered s3.1 JWS value: it parses with its row
    assert m.jws_alg_parse('none') == {
        'name': 'none',
        'algorithm': 'No digital signature or MAC performed',
        'implementation': 'Optional'}
    assert m.jws_alg_is_valid('none') is True
    # it is not an s4.1 or s5.1 value: the JWE functions refuse it
    refuse(KA, 'bad_value:alg.unknown', 'none')
    refuse(JE, 'bad_value:enc.unknown', 'none')
    assert m.jwe_alg_is_valid('none') is False
    assert m.jwe_enc_is_valid('none') is False


def test_return_values_are_fresh_dicts():
    r1 = m.jwe_alg_parse('ECDH-ES')
    r1['name'] = 'MUTATED'
    r1['more_header_params'].append('MUTATED')
    r2 = m.jwe_alg_parse('ECDH-ES')
    assert r2 == {'name': 'ECDH-ES',
                  'algorithm': 'Elliptic Curve Diffie-Hellman'
                               ' Ephemeral Static key agreement'
                               ' using Concat KDF',
                  'more_header_params': ['epk', 'apu', 'apv'],
                  'implementation': 'Recommended+'}
    assert r1 is not r2
    a = m.jws_alg_parse('HS256')
    b = m.jws_alg_parse('HS256')
    assert a == b and a is not b


def test_exact_refusal_codes():
    refuse(JA, 'bad_value:alg.unknown', 'HS255')
    try:
        m.jws_alg_parse(0)
    except ValueError as e:
        assert str(e) == _pfx() + 'jws_alg_parse:bad_type:alg.type'
    else:
        raise AssertionError('int must refuse')


def test_type_refusals():
    for fn_name, code, bad in _refusal_corpus():
        if code.startswith('bad_type:'):
            refuse(fn_name, code, bad)


def test_ascii_before_unknown_and_boundary():
    # 0x7f (DEL) is ASCII: a name carrying it refuses as unknown,
    # not as non-ASCII
    for fn in (JA, KA, JE):
        refuse(fn, 'bad_value:%s.unknown' % _kind(fn), 'HS25\x7f')
        # 0x80 is the first non-ASCII code point: the ascii rule
        # fires before membership even though the name is also
        # unknown
        refuse(fn, 'bad_value:%s.ascii' % _kind(fn), 'HS25\x80')
        refuse(fn, 'bad_value:%s.ascii' % _kind(fn), 'ZZZZ\xe9')


def test_every_name_position_pinned():
    # every character of every registered name is load-bearing:
    # replace it, drop it, or add a neighbour and the value is out
    for fn, table in ((JA, JWS_TABLE), (KA, JWE_TABLE),
                      (JE, ENC_TABLE)):
        code = 'bad_value:%s.unknown' % _kind(fn)
        for name in table:
            for i, c in enumerate(name):
                alt = 'Z' if c != 'Z' else 'Y'
                bad = name[:i] + alt + name[i + 1:]
                assert bad not in table
                refuse(fn, code, bad)
            refuse(fn, code, name[:-1])
            refuse(fn, code, name + 'Z')
            refuse(fn, code, 'Z' + name)


def test_short_inputs():
    for bad in ('', 'H', 'HS', 'HS2', 'A', 'A1', 'A12', 'A128',
                'A128G', 'd', 'di', 'n', 'no', 'non', 'P',
                'PBES2-HS512+A256K'):
        for fn in (JA, KA, JE):
            refuse(fn, 'bad_value:%s.unknown' % _kind(fn), bad)


def test_refusal_order():
    # bad_type before everything: a non-str refuses with the type
    # code even though its repr contains no ASCII at all
    for fn in (JA, KA, JE):
        refuse(fn, 'bad_type:%s.type' % _kind(fn), object())
    # bad_value: ascii before unknown
    refuse(JA, 'bad_value:alg.ascii', '\xe9not-a-name-at-all')


def test_is_valid_returns_exact_bool():
    for parse_name, valid, invalid in (
            (JA, 'HS256', 'hs256'), (KA, 'RSA1_5', 'RSA1_4'),
            (JE, 'A128GCM', 'A129GCM')):
        is_valid = getattr(m, parse_name.replace(
            '_parse', '_is_valid'))
        assert is_valid(valid) is True
        assert is_valid(invalid) is False
        assert is_valid(None) is False
        assert type(is_valid(valid)) is bool
        assert type(is_valid(invalid)) is bool


def test_constants_pinned_whole():
    assert m._JWS_ALG == JWS_TABLE
    assert m._JWE_ALG == JWE_TABLE
    assert m._JWE_ENC == ENC_TABLE
    assert type(m._JWS_ALG) is dict
    assert type(m._JWE_ALG) is dict
    assert type(m._JWE_ENC) is dict


def test_function_docstrings_pinned_exact():
    assert m.jws_alg_parse.__doc__ == (
        'Validate an s3.1 JWS "alg" value; return its table row.')
    assert m.jws_alg_is_valid.__doc__ == (
        'True iff jws_alg_parse(text) would succeed.')
    assert m.jwe_alg_parse.__doc__ == (
        'Validate an s4.1 JWE "alg" value; return its table row.')
    assert m.jwe_alg_is_valid.__doc__ == (
        'True iff jwe_alg_parse(text) would succeed.')
    assert m.jwe_enc_parse.__doc__ == (
        'Validate an s5.1 JWE "enc" value; return its table row.')
    assert m.jwe_enc_is_valid.__doc__ == (
        'True iff jwe_enc_parse(text) would succeed.')


def test_module_namespace_is_pinned():
    names = set(vars(m))
    assert names == {
        '__name__', '__doc__', '__package__', '__loader__',
        '__spec__', '__file__', '__cached__', '__builtins__',
        'find_spec', 'make_fail',
        '_JWS_ALG', '_JWE_ALG', '_JWE_ENC', '_name_row',
        'jws_alg_parse', 'jws_alg_is_valid',
        'jwe_alg_parse', 'jwe_alg_is_valid',
        'jwe_enc_parse', 'jwe_enc_is_valid'}


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
            builtins.__import__ = hook
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
                is_valid('not a name at all: ' + chr(0))
            finally:
                builtins.__import__ = real
            assert log == [], (fn_name, args, log)
    finally:
        sys.settrace(None)
    assert f_lines <= hits, sorted(f_lines - hits)


# ---- registry guard ----

def test_battery_rev0_pins():
    # case-sensitivity pins: the tables are matched exactly (JWS
    # s4.1.1: "a case-sensitive ASCII string")
    refuse(JA, 'bad_value:alg.unknown', 'hs256')
    refuse(JA, 'bad_value:alg.unknown', 'Hs256')
    refuse(JA, 'bad_value:alg.unknown', 'HS256 ')
    refuse(JA, 'bad_value:alg.unknown', ' HS256')
    refuse(KA, 'bad_value:alg.unknown', 'rsa1_5')
    refuse(KA, 'bad_value:alg.unknown', 'RSA1_5 ')
    refuse(JE, 'bad_value:enc.unknown', 'a128gcm')
    # the '+' in ECDH-ES+A128KW and PBES2 names is literal
    refuse(KA, 'bad_value:alg.unknown', 'ECDH-ES A128KW')
    refuse(KA, 'bad_value:alg.unknown', 'ECDH-ES%2BA128KW')
    refuse(KA, 'bad_value:alg.unknown', 'PBES2-HS256 A128KW')
    # str subclass refuses with the type code (exact type check)
    for fn in (JA, KA, JE):
        refuse(fn, 'bad_type:%s.type' % _kind(fn),
               _StrSub('HS256'))
        refuse(fn, 'bad_type:%s.type' % _kind(fn), True)
    # s3.6: "none" belongs to the JWS table only
    assert m.jws_alg_is_valid('none') is True
    refuse(KA, 'bad_value:alg.unknown', 'none')
    refuse(JE, 'bad_value:enc.unknown', 'none')


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
    _b.__import__ = bogus_import
    _iu.find_spec = no_spec
    try:
        mod = types.ModuleType('fresh_b1224')
        with pytest.raises(ModuleNotFoundError):
            exec(compile(src, 'fresh_b1224', 'exec'), mod.__dict__)
    finally:
        _b.__import__ = real_import
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
            ('import no_such_dep_xyz_1224\n', 'ModuleNotFoundError'),
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

    builtins.__import__ = bogus_import
    _iu.find_spec = spy_find_spec
    try:
        mod = types.ModuleType('fresh_b1224_spy')
        exec(compile(src, 'fresh_b1224_spy', 'exec'), mod.__dict__)
    finally:
        builtins.__import__ = real_import
        _iu.find_spec = real_find_spec
    assert calls == [REG], calls
    # the fallback engaged and works
    assert mod.jws_alg_is_valid('HS256') is True
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        assert str(e) == 'P235:x:c'
    else:
        raise AssertionError('fallback make_fail did not raise')


__DOC__ = 'RFC 7518 "JSON Web Algorithms (JWA)": the "alg" (algorithm)\nname registries and the "enc" (encryption algorithm) name\nregistry as pure tables: the s3.1 "alg" values for JWS, the\ns4.1 "alg" values for JWE, and the s5.1 "enc" values for JWE,\nwith the "none" handling of s3.6 and the RFC 8725 s3.2\ncaution.  Computing or verifying any of the named algorithms\nis cryptographic processing and out of scope.\n\nPublic API:\n\n  jws_alg_parse(text) -> the s3.1 table row for a JWS "alg"\n      value as a dict: \'name\' (the value), \'algorithm\'\n      (the Digital Signature or MAC column text),\n      \'implementation\' (the Implementation Requirements\n      column text, verbatim, including any \'+\'/\'-\' suffix).\n  jws_alg_is_valid(text) -> True iff jws_alg_parse would\n      succeed.\n  jwe_alg_parse(text) -> the s4.1 table row for a JWE "alg"\n      value as a dict: \'name\', \'algorithm\' (the Key\n      Management Algorithm column text),\n      \'more_header_params\' (the More Header Params column as\n      a list of names, empty for "(none)"), \'implementation\'.\n  jwe_alg_is_valid(text) -> True iff jwe_alg_parse would\n      succeed.\n  jwe_enc_parse(text) -> the s5.1 table row for a JWE "enc"\n      value as a dict: \'name\', \'algorithm\' (the Content\n      Encryption Algorithm column text), \'implementation\'.\n  jwe_enc_is_valid(text) -> True iff jwe_enc_parse would\n      succeed.\n\nGrammar notes (verified against the RFC 7518 text): an "alg"\nvalue is "a case-sensitive ASCII string containing a\nStringOrURI value" (JWS s4.1.1, the same text at JWE\ns4.1.1), so the tables are matched case-sensitively and any\nnon-ASCII character refuses.  The s3.1 table lists "HS256",\n"HS384", "HS512", "RS256", "RS384", "RS512", "ES256",\n"ES384", "ES512", "PS256", "PS384", "PS512" and "none".  The\ns4.1 table lists "RSA1_5", "RSA-OAEP", "RSA-OAEP-256",\n"A128KW", "A192KW", "A256KW", "dir", "ECDH-ES",\n"ECDH-ES+A128KW", "ECDH-ES+A192KW", "ECDH-ES+A256KW",\n"A128GCMKW", "A192GCMKW", "A256GCMKW", "PBES2-HS256+A128KW",\n"PBES2-HS384+A192KW" and "PBES2-HS512+A256KW".  The s5.1\ntable lists "A128CBC-HS256", "A192CBC-HS384",\n"A256CBC-HS512", "A128GCM", "A192GCM" and "A256GCM".  "The\nuse of "+" in the Implementation Requirements column\nindicates that the requirement strength is likely to be\nincreased in a future version of the specification." (s3.1);\ns4.1 adds: "The use of "-" indicates that the requirement\nstrength is likely to be decreased in a future version of\nthe specification."  The s4.1 More Header\nParams column names "epk", "apu" and "apv" for the ECDH-ES\nfamily, "iv" and "tag" for the AES GCM key wrapping family\nand "p2s" and "p2c" for the PBES2 family, and s4.1 notes:\n"All but "dir" and "ECDH-ES" also produce a JWE Encrypted\nKey value."  No name appears in more than one of the three\ntables, so each function\'s membership test is against its\nown table only.\n\nThe "none" handling (s3.6, RFC 8725 s3.2): "none" is a\nregistered s3.1 value ("No digital signature or MAC\nperformed"), so jws_alg_parse("none") succeeds with its row;\nit is not an s4.1 or s5.1 value, so the JWE functions refuse\nit.  Accepting it is an application decision, not a registry\nfact: s3.6 says "Implementations that support Unsecured JWSs\nMUST NOT accept such objects as valid unless the application\nspecifies that it is acceptable for a specific object to not\nbe integrity protected.  Implementations MUST NOT accept\nUnsecured JWSs by default." and, against downgrade attacks,\n"applications MUST NOT signal acceptance of Unsecured JWSs\nat a global level, and SHOULD signal acceptance on a\nper-object basis".  RFC 8725 s3.2 adds that applications\n"MUST only allow the use of cryptographically current\nalgorithms", that the "none" algorithm "should only be used\nwhen the JWT is cryptographically protected by other means",\nand that "JWT libraries SHOULD NOT generate JWTs using\n"none" unless explicitly requested to do so by the caller"\nand "SHOULD NOT consume JWTs using "none" unless explicitly\nrequested by the caller".  This unit validates registry\nmembership only; those acceptance rules are the caller\'s to\nenforce.\n\nProfile decisions (OURS, not from the RFC text):\n  - Values are required to be pure ASCII (both "alg" texts\n    say ASCII); the check is per character, before the\n    membership test.\n  - The empty string is ASCII and in no table, so it refuses\n    as an unknown name rather than with its own code.\n  - A registered-name row reports the printed table columns\n    only; prose facts around the tables (such as which JWE\n    "alg" values produce a JWE Encrypted Key) are documented\n    above, not folded into the rows.\n  - Only the exact str type is accepted: subclasses refuse\n    with the type code.\n\nRefusal order: bad_type before everything (the exact type\ncheck); then bad_value: the ASCII rule before the membership\nrule ("unknown" covers every well-formed value the table\ndoes not list, including wrong case, surrounding whitespace\nand names from the other tables).\n\nErrata (4 records, all Verified, none touching the name\ntables, none folded): Verified EID 6612 (s3.4, Editorial)\nfixes "being be" to "being" in the ECDSA R/S octet-step\ntext: signature computation, not the name grammar.\nVerified EID 8526 (s3.4.5, Technical) carries text about\nRTCP header compression that has no counterpart in RFC 7518\n(a misfiled record): nothing to fold.  Verified EID 8568\n(s3.2, Editorial) corrects a "NIST SP 800-117" reference to\n"NIST SP 800-107" in the HMAC key-length rationale: a\ncitation fix, not the name grammar.  Verified EID 8747\n(s7.1.1, Editorial) fixes "Algorithm Analysis\nDocuments(s):" to "Algorithm Analysis Document(s):" in the\nIANA registration template: registry paperwork, not the\nname tables.\n'
