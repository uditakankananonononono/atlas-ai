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
from app.modules.instinct_doc import p235_concepts_batch1243_teluris as m
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


MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1243_teluris'
REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODPATH = m.__file__


def _probe():
    try:
        m.is_tel_uri(None)
    except ValueError as e:
        s = str(e)
        assert s.endswith('is_tel_uri:text-type'), s
        return s[:-len('is_tel_uri:text-type')]
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
    def __str__(self):
        raise AssertionError('str() called')



def _o_digits(d, kind):
    if not isinstance(d, str) or d == '':
        return 'bad'
    if kind == 'global':
        if d[0] != '+':
            return 'bad'
        d = d[1:]
    seen = False
    for c in d:
        if c in '0123456789':
            seen = True
        elif kind == 'local' and c in 'ABCDEF*#':
            seen = True
        elif c in '-.()':
            pass
        else:
            return 'bad'
    return 'ok' if seen else 'bad'


def _o_desc(d):
    if not isinstance(d, str) or d == '':
        return 'bad'
    if d[0] == '+':
        return _o_digits(d, 'global')
    core = d[:-1] if d.endswith('.') else d
    labs = core.split('.')
    for lab in labs:
        if lab == '':
            return 'bad'
        if any(not (c.isascii() and (c.isalnum() or c == '-')) for c in lab):
            return 'bad'
        if lab[0] == '-' or lab[-1] == '-':
            return 'bad'
    if not labs[-1][0].isalpha() or not labs[-1][0].isascii():
        return 'bad'
    return 'ok'


def _o_uri(t):
    if not isinstance(t, str):
        return 'bad'
    if len(t) < 4 or t[:3].lower() != 'tel' or t[3] != ':':
        return 'bad'
    body = t[4:]
    if body == '':
        return 'bad'
    i = body.find(';')
    digits = body if i < 0 else body[:i]
    parstr = '' if i < 0 else body[i:]
    kind = 'global' if digits[:1] == '+' else 'local'
    if _o_digits(digits, kind) != 'ok':
        return 'bad'
    nctx = 0
    if parstr:
        for seg in parstr.split(';')[1:]:
            if seg == '':
                return 'bad'
            j = seg.find('=')
            name = seg if j < 0 else seg[:j]
            value = None if j < 0 else seg[j + 1:]
            if name == '' or any(not (c.isascii() and (c.isalnum() or c == '-')) for c in name):
                return 'bad'
            low = name.lower()
            if low == 'ext':
                if value is None or value == '':
                    return 'bad'
                if any(not (c in '0123456789' or c in '-.()') for c in value):
                    return 'bad'
            elif low == 'isub':
                if value is None or value == '':
                    return 'bad'
                if not _o_paramchar(value):
                    return 'bad'
            elif low == 'phone-context':
                if value is None:
                    return 'bad'
                if _o_desc(value) != 'ok':
                    return 'bad'
                nctx += 1
            else:
                if value is not None and (value == '' or not _o_paramchar(value)):
                    return 'bad'
    if kind == 'local' and nctx == 0:
        return 'bad'
    if nctx > 1:
        return 'bad'
    return 'ok'


def _o_paramchar(v):
    i = 0
    while i < len(v):
        c = v[i]
        if c == '%':
            if i + 2 >= len(v) + 1 and i + 2 > len(v) - 1:
                if i + 2 > len(v):
                    return False
            if i + 2 > len(v) - 1:
                return False
            if any(ch not in '0123456789ABCDEFabcdef' for ch in v[i + 1:i + 3]):
                return False
            i += 3
            continue
        if not (c.isascii() and (c.isalnum() or c in "-_.!~*'()[]/:&+$")):
            return False
        i += 1
    return True


def test_oracle_fuzz():
    import random
    rng = random.Random(3966)
    pool = 'tel:+1234567890ABCDEF*#-.();=abzAZ_!~%[]/:&$ \x7f\x80'
    for _ in range(60000):
        n = rng.randrange(0, 26)
        t = ''.join(rng.choice(pool) for _ in range(n))
        exp = _o_uri(t)
        got = 'ok' if m.is_tel_uri(t) else 'bad'
        assert got == exp, (t, got, exp)
    for _ in range(20000):
        n = rng.randrange(1, 18)
        t = 'tel:' + ''.join(rng.choice(pool[4:]) for _ in range(n))
        exp = _o_uri(t)
        got = 'ok' if m.is_tel_uri(t) else 'bad'
        assert got == exp, (t, got, exp)


def test_constants_tables_and_namespace():
    assert m.TEXT_MAX == 1024 and m.DESC_MAX == 255
    assert m.VISUAL_SEPARATORS == '-.()'
    assert m.MARK == "-_.!~*'()"
    assert m.PARAM_UNRESERVED == '[]/:&+$'
    assert m.CLAIMS is False
    assert m.SCOPE == 'RFC 3966 section 3 tel URI syntax with section 5.1.5 local number context'
    assert m.NOT_CLAIMED == ('E.164 digit-count rules', 'check-digit or CRC semantics of any kind', 'E.161/T1.703 alphabetic-to-digit mapping', 'actual dialing or call setup', 'SIP/SIPS URI parameters (RFC 3261)', 'tel URI parameter registry contents (RFC 5341)')
    assert m.ADJACENT == ('RFC 5234 ABNF core rules (DIGIT, HEXDIG, ALPHA)', 'RFC 2396 uric and URI syntax heritage', 'RFC 1035 and RFC 1123 domain name labels (sibling modules)', 'RFC 5341 tel URI parameter registry (updates RFC 3966)', 'RFC 2806 (obsoleted predecessor)')
    names = {n for n in vars(m) if not n.startswith('__')}
    assert names == {'find_spec', 'make_fail', 'SCOPE', 'NOT_CLAIMED', 'ADJACENT', 'CLAIMS', 'TEXT_MAX', 'DESC_MAX', 'VISUAL_SEPARATORS', 'MARK', 'PARAM_UNRESERVED', '_text', '_letter', '_digit', '_alphanum', '_iei', '_ici', '_hexval', '_paramchar', '_digits_code', '_pct_code', '_desc_domain_code', '_desc_code', '_pars_code', '_uri_code', 'is_tel_uri', 'split_tel_uri', 'number_kind', 'strip_separators'}
    assert m._digits_code('', 'local') == 'digit-none'
    assert m._digits_code('+', 'global') == 'digit-none'
    assert m._digits_code('+-', 'global') == 'digit-none'
    assert m._digits_code('-', 'local') == 'digit-none'
    assert m._desc_code('') == 'context-dot'
    assert m._hexval('0') == 0 and m._hexval('9') == 9
    assert m._hexval('a') == 10 and m._hexval('f') == 15
    assert m._hexval('A') == 10 and m._hexval('F') == 15
    assert m._hexval('g') is None and m._hexval('G') is None
    assert m._hexval('@') is None and m._hexval('`') is None and m._hexval('/') is None and m._hexval(':') is None


def test_scheme_and_caps():
    err('is_tel_uri', 'text-type', None)
    err('is_tel_uri', 'text-type', True)
    err('is_tel_uri', 'text-type', SubStr('tel:+1'))
    err('split_tel_uri', 'text-type', None)
    err('split_tel_uri', 'text-type', SubStr('tel:+1'))
    err('number_kind', 'text-type', None)
    err('strip_separators', 'text-type', None)
    err('split_tel_uri', 'empty', '')
    err('split_tel_uri', 'text-length', 'tel:+1' + '1' * 1019)
    assert m.is_tel_uri('tel:+1' + '1' * 1018) is True
    err('split_tel_uri', 'short', 'tel')
    err('split_tel_uri', 'short', 'te')
    err('split_tel_uri', 'scheme', 'sip:1')
    err('split_tel_uri', 'scheme-colon', 'telx:1')
    err('split_tel_uri', 'scheme-colon', 'tel/1')
    err('split_tel_uri', 'subscriber-empty', 'tel:')
    assert m.is_tel_uri('TEL:+1-2') is True
    assert m.is_tel_uri('TeL:+1') is True
    err('number_kind', 'scheme', 'http:+1')
    assert m.split_tel_uri('tel:+1-201-555-0123') == ('global', '+1-201-555-0123', None, [])
    assert m.split_tel_uri('tel:+1') == ('global', '+1', None, [])


def test_digits_rules():
    err('split_tel_uri', 'digit-none', 'tel:+')
    err('split_tel_uri', 'digit-none', 'tel:+-')
    err('split_tel_uri', 'digit-none', 'tel:+(-)')
    err('split_tel_uri', 'digit-none', 'tel:-.()')
    err('split_tel_uri', 'digit-none', 'tel:;phone-context=x.com')
    err('split_tel_uri', 'digit-char', 'tel:+a')
    err('split_tel_uri', 'digit-char', 'tel:+1A')
    err('split_tel_uri', 'digit-char', 'tel:+1*')
    err('split_tel_uri', 'digit-char', 'tel:+1#')
    err('split_tel_uri', 'digit-char', 'tel:+1\x7f')
    err('split_tel_uri', 'digit-char', 'tel:+\u00e9')
    err('split_tel_uri', 'context-char', 'tel:+1;phone-context=+a')
    assert m.is_tel_uri('tel:+1--2') is True
    assert m.is_tel_uri('tel:+-1') is True
    assert m.is_tel_uri('tel:+1-') is True
    assert m.is_tel_uri('tel:+(1).2-3') is True
    assert m.is_tel_uri('tel:1A#*;phone-context=x.com') is True
    assert m.is_tel_uri('tel:#;phone-context=x.com') is True
    err('split_tel_uri', 'digit-char', 'tel:1a;phone-context=x.com')
    assert m.is_tel_uri('tel:1F;phone-context=x.com') is True
    assert m.is_tel_uri('tel:F;phone-context=x.com') is True
    assert m.number_kind('tel:+1-2') == 'global'
    assert m.number_kind('tel:123;phone-context=+33') == 'local'
    assert m.number_kind('tel:AB;phone-context=x.com') == 'local'


def test_params_rules():
    err('split_tel_uri', 'par-empty', 'tel:+1;')
    err('split_tel_uri', 'par-empty', 'tel:+1;;a=1')
    err('split_tel_uri', 'par-empty', 'tel:+1;a=1;')
    err('split_tel_uri', 'pname-empty', 'tel:+1;=v')
    err('split_tel_uri', 'pname-empty', 'tel:+1;=')
    err('split_tel_uri', 'pname-char', 'tel:+1;a b=1')
    err('split_tel_uri', 'pname-char', 'tel:+1;a_b=1')
    err('split_tel_uri', 'pname-char', 'tel:+1;\u00e9=1')
    err('split_tel_uri', 'pname-char', 'tel:+1;.x=1')
    assert m.split_tel_uri('tel:+1;foo') == ('global', '+1', None, [('foo', None)])
    assert m.split_tel_uri('tel:+1;a-b;C-d=e') == ('global', '+1', None, [('a-b', None), ('C-d', 'e')])
    err('split_tel_uri', 'pvalue-empty', 'tel:+1;foo=')
    err('split_tel_uri', 'pvalue-char', 'tel:+1;foo=a b')
    err('split_tel_uri', 'pvalue-char', 'tel:+1;foo=a\x7f')
    err('split_tel_uri', 'pvalue-pc', 'tel:+1;foo=a%2')
    err('split_tel_uri', 'pvalue-pc', 'tel:+1;foo=a%2G')
    err('split_tel_uri', 'pvalue-pc', 'tel:+1;foo=a%')
    assert m.split_tel_uri('tel:+1;foo=a%39') == ('global', '+1', None, [('foo', 'a%39')])
    assert m.split_tel_uri('tel:+1;foo=a%4A') == ('global', '+1', None, [('foo', 'a%4A')])
    assert m.split_tel_uri('tel:+1;foo=a%4a') == ('global', '+1', None, [('foo', 'a%4a')])
    assert m.split_tel_uri("tel:+1;foo=[]/:&+$-_.!~*'()%20AZaz09") == ('global', '+1', None, [('foo', "[]/:&+$-_.!~*'()%20AZaz09")])


def test_ext_isub_rules():
    err('split_tel_uri', 'ext-value', 'tel:+1;ext')
    err('split_tel_uri', 'ext-empty', 'tel:+1;ext=')
    err('split_tel_uri', 'ext-char', 'tel:+1;ext=12a')
    err('split_tel_uri', 'ext-char', 'tel:+1;ext=12A')
    err('split_tel_uri', 'ext-char', 'tel:+1;ext=*')
    err('split_tel_uri', 'ext-char', 'tel:+1;ext=%20')
    assert m.split_tel_uri('tel:+1;ext=1-.()2') == ('global', '+1', None, [('ext', '1-.()2')])
    assert m.split_tel_uri('tel:+1;EXT=9') == ('global', '+1', None, [('EXT', '9')])
    err('split_tel_uri', 'isub-value', 'tel:+1;isub')
    err('split_tel_uri', 'isub-empty', 'tel:+1;isub=')
    err('split_tel_uri', 'isub-char', 'tel:+1;isub=a b')
    err('split_tel_uri', 'isub-pc', 'tel:+1;isub=a%2G')
    assert m.split_tel_uri('tel:+1;isub=a%41') == ('global', '+1', None, [('isub', 'a%41')])
    assert m.split_tel_uri("tel:+1;isub=[]/:&+$-_.!~*'()AZaz09") == ('global', '+1', None, [('isub', "[]/:&+$-_.!~*'()AZaz09")])
    assert m.split_tel_uri('tel:+1;ISUB=1') == ('global', '+1', None, [('ISUB', '1')])


def test_context_rules():
    err('split_tel_uri', 'context-missing', 'tel:123')
    err('split_tel_uri', 'context-missing', 'tel:123;ext=5')
    err('split_tel_uri', 'context-value', 'tel:123;phone-context')
    err('split_tel_uri', 'context-empty', 'tel:123;phone-context=')
    err('split_tel_uri', 'context-dup', 'tel:123;phone-context=a.com;phone-context=b.com')
    err('split_tel_uri', 'context-char', 'tel:123;phone-context=a;phone-context=%20')
    err('split_tel_uri', 'context-char', 'tel:123;phone-context=a b.com')
    err('split_tel_uri', 'context-char', 'tel:123;phone-context=a_b.com')
    err('split_tel_uri', 'context-char', 'tel:123;phone-context=+a')
    err('split_tel_uri', 'context-char', 'tel:123;phone-context=+1*')
    err('split_tel_uri', 'context-none', 'tel:123;phone-context=+')
    err('split_tel_uri', 'context-none', 'tel:123;phone-context=+(-)')
    err('split_tel_uri', 'context-dot', 'tel:123;phone-context=a..b')
    err('split_tel_uri', 'context-dot', 'tel:123;phone-context=.a')
    err('split_tel_uri', 'context-dot', 'tel:123;phone-context=.')
    err('split_tel_uri', 'context-label', 'tel:123;phone-context=-a.com')
    err('split_tel_uri', 'context-label', 'tel:123;phone-context=a-.com')
    err('split_tel_uri', 'context-label', 'tel:123;phone-context=-.a')
    err('split_tel_uri', 'context-toplabel', 'tel:123;phone-context=a.2')
    err('split_tel_uri', 'context-toplabel', 'tel:123;phone-context=9com')
    err('split_tel_uri', 'context-toplabel', 'tel:123;phone-context=a.9')
    err('split_tel_uri', 'context-length', 'tel:123;phone-context=' + 'a' * 256)
    assert m.split_tel_uri('tel:123;phone-context=' + 'a' * 255)[2] == 'a' * 255
    assert m.split_tel_uri('tel:123;phone-context=houston.example.com') == ('local', '123', 'houston.example.com', [])
    assert m.split_tel_uri('tel:123;phone-context=+33') == ('local', '123', '+33', [])
    assert m.split_tel_uri('tel:123;phone-context=+3-3') == ('local', '123', '+3-3', [])
    assert m.split_tel_uri('tel:123;phone-context=a.com.') == ('local', '123', 'a.com.', [])
    assert m.split_tel_uri('tel:123;PHONE-CONTEXT=a.com') == ('local', '123', 'a.com', [])
    assert m.split_tel_uri('tel:+1;phone-context=+33') == ('global', '+1', '+33', [])
    assert m.split_tel_uri('tel:123;ext=5;phone-context=a.com;isub=2') == ('local', '123', 'a.com', [('ext', '5'), ('isub', '2')])
    assert m.split_tel_uri('tel:123;x=1;phone-context=a.com;y=2') == ('local', '123', 'a.com', [('x', '1'), ('y', '2')])


def test_strip_separators():
    assert m.strip_separators('tel:+1-201-555-0123') == '+12015550123'
    assert m.strip_separators('tel:+1') == '+1'
    assert m.strip_separators('tel:+1-') == '+1'
    assert m.strip_separators('tel:+(1).2-3') == '+123'
    assert m.strip_separators('tel:1-2;phone-context=+3-3') == '12'
    assert m.strip_separators('tel:A-B;phone-context=x.com') == 'AB'
    assert m.strip_separators('tel:#*1;phone-context=x.com') == '#*1'
    assert m.strip_separators('tel:+1;ext=1-2') == '+1'
    err('strip_separators', 'context-missing', 'tel:1-2')
    err('strip_separators', 'digit-char', 'tel:+a')
    err('number_kind', 'digit-none', 'tel:+')
    assert m.is_tel_uri('tel:+1-201-555-0123;phone-context=+1-201') is True


def test_survivor_kill_pins():
    # _letter range boundaries (kills int-1 mutants on 97/65 in _letter)
    assert m._letter('A') is True and m._letter('Z') is True
    assert m._letter('a') is True and m._letter('z') is True
    assert m._letter('@') is False and m._letter('[') is False
    assert m._letter('`') is False and m._letter('{') is False
    assert m._alphanum('@') is False and m._alphanum('`') is False
    err('split_tel_uri', 'context-char', 'tel:123;phone-context=`x')
    err('split_tel_uri', 'context-char', 'tel:123;phone-context=@x')
    # local hex range stops at F (kills int+1 on 70 in _digits_code)
    assert m._digits_code('G', 'local') == 'digit-char'
    assert m._digits_code('g', 'local') == 'digit-char'
    # local hex range starts at A (kills int-1 on 65 in _digits_code)
    assert m._digits_code('@', 'local') == 'digit-char'
    err('split_tel_uri', 'digit-char', 'tel:1@;phone-context=x.com')
    err('split_tel_uri', 'digit-char', 'tel:1G;phone-context=x.com')
    err('split_tel_uri', 'digit-char', 'tel:1g;phone-context=x.com')
    # _ici compares every char (kills loop-break after first iteration)
    assert m._ici('tax', 'tel') is False
    assert m._ici('exu', 'ext') is False
    assert m._ici('isux', 'isub') is False
    # multi-fault phase pins (A44 rev1): first fault's code must win
    err('split_tel_uri', 'pvalue-pc', 'tel:+1;foo=%zz ')
    err('split_tel_uri', 'isub-pc', 'tel:+1;isub=%zz ')
    err('split_tel_uri', 'pvalue-char', 'tel:+1;foo=a b%zz')
    err('split_tel_uri', 'isub-char', 'tel:+1;isub=a b%zz')
    err('split_tel_uri', 'context-char', 'tel:123;phone-context=a!..x')
    err('split_tel_uri', 'context-label', 'tel:123;phone-context=-a..x')
    assert m.is_tel_uri('tel:+1;foo=%zz ') is False
    assert m.is_tel_uri('tel:+1;foo=a b%zz') is False
    assert m.is_tel_uri('tel:123;phone-context=a!..x') is False
    assert m.is_tel_uri('tel:123;phone-context=-a..x') is False
    assert m._ici('phone-contexu', 'phone-context') is False
    assert m.split_tel_uri('tel:+1;exu=1') == ('global', '+1', None, [('exu', '1')])
    assert m.split_tel_uri('tel:+1;isux=12a') == ('global', '+1', None, [('isux', '12a')])
    assert m.split_tel_uri('tel:+1;phone-contexu=a.com') == ('global', '+1', None, [('phone-contexu', 'a.com')])
    err('split_tel_uri', 'context-missing', 'tel:123;phone-contexu=a.com')
    # _ici length mismatch (kills del of return False)
    assert m._ici('exty', 'ext') is False
    assert m._ici('ext', 'exty') is False
    assert m._ici('phone-contexts', 'phone-context') is False
    assert m.split_tel_uri('tel:+1;exty=1') == ('global', '+1', None, [('exty', '1')])
    assert m.split_tel_uri('tel:+1;EXTY=1') == ('global', '+1', None, [('EXTY', '1')])
    # trailing-dot strip removes exactly one char (kills int+1 on d[:-1])
    assert m._desc_domain_code('x.') is None
    assert m._desc_domain_code('ab.') is None
    assert m.is_tel_uri('tel:123;phone-context=x.') is True
def _run_everything():
    uris = ['', 't', 'te', 'tel', 'tel:', 'tel:+', 'tel:+1', 'tel:+1-2', 'tel:+-1', 'tel:+1--2', 'tel:+1-', 'tel:+a', 'tel:+1A', 'tel:+1*', 'tel:+1#', 'tel:+1\x7f', 'tel:+\u00e9', 'tel:1', 'tel:123', 'tel:1A', 'tel:1a', 'tel:1F', 'tel:F', 'tel:#*1', 'tel:-.()', 'TEL:+1-2', 'TeL:+1', 'telx:1', 'tel/1', 'sip:1', 'tel:;phone-context=x.com', 'tel:+1;', 'tel:+1;;a=1', 'tel:+1;a=1;', 'tel:+1;=v', 'tel:+1;=', 'tel:+1;a b=1', 'tel:+1;a_b=1', 'tel:+1;foo', 'tel:+1;foo=', 'tel:+1;foo=a b', 'tel:+1;foo=a%2', 'tel:+1;foo=a%2G', 'tel:+1;foo=a%', 'tel:+1;foo=a%39', 'tel:+1;foo=a%4A', 'tel:+1;foo=a%4a', 'tel:+1;ext', 'tel:+1;ext=', 'tel:+1;ext=12a', 'tel:+1;ext=1-2', 'tel:+1;EXT=9', 'tel:+1;isub', 'tel:+1;isub=', 'tel:+1;isub=a b', 'tel:+1;isub=a%2G', 'tel:+1;isub=a%41', 'tel:123;phone-context=houston.example.com', 'tel:123;phone-context=+33', 'tel:123;phone-context=+3-3', 'tel:123;phone-context=a.com.', 'tel:123;phone-context=a..b', 'tel:123;phone-context=.a', 'tel:123;phone-context=.', 'tel:123;phone-context=-a.com', 'tel:123;phone-context=a-.com', 'tel:123;phone-context=a.2', 'tel:123;phone-context=9com', 'tel:123;phone-context=a b.com', 'tel:123;phone-context=a_b.com', 'tel:123;phone-context=+a', 'tel:123;phone-context=+', 'tel:123;phone-context=%2B33', 'tel:123;phone-context=a.com;phone-context=b.com', 'tel:123;phone-context', 'tel:123;phone-context=', 'tel:123;phone-context=a;phone-context=%20', 'tel:+1;phone-context=+33', 'tel:123;ext=5;phone-context=a.com;isub=2', 'tel:123;x=1;phone-context=a.com;y=2', 'tel:123;phone-context=' + 'a' * 255, 'tel:123;phone-context=' + 'a' * 256, 'tel:+1' + '1' * 1023, 'tel:+1' + '1' * 1024, 'tel:+\u00e9', None, SubStr('tel:+1'), True, 'x' * 1025]
    for t2 in uris:
        for fn in (m.is_tel_uri, m.split_tel_uri, m.number_kind, m.strip_separators):
            try:
                fn(t2)
            except ValueError:
                pass
    assert m.split_tel_uri('tel:+1-201-555-0123') == ('global', '+1-201-555-0123', None, [])
    assert m.number_kind('tel:123;phone-context=+33') == 'local'
    assert m.strip_separators('tel:+1-2') == '+12'
    assert m._ici('TEL', 'tel') is True
    assert m._digits_code('1A', 'local') is None and m._digits_code('+1', 'global') is None
    assert m._desc_code('+33') is None and m._desc_code('a.com') is None
    assert m._pct_code('a%41', 'c', 'p') is None and m._pars_code(';ext=1')[0] is None


def _no_import_hook(*a, **k):
    raise AssertionError('import during call: %r' % (a[:1],))


def _load(name='fresh_1243'):
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
        if globals is not None and globals.get('__name__') == 'fresh_1243':
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
            mod.is_tel_uri(None)
        assert str(e.value) == 'P235:is_tel_uri:text-type'
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
            mod.is_tel_uri(1)
        assert str(e.value) == 'X:is_tel_uri:text-type'
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
        assert m.split_tel_uri('tel:+1-201-555-0123') == ('global', '+1-201-555-0123', None, [])
        assert m.is_tel_uri('TEL:+1') is True
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
        assert m.split_tel_uri('tel:+1-201-555-0123') == ('global', '+1-201-555-0123', None, [])
        assert m.number_kind('tel:123;phone-context=+33') == 'local'
        assert m.strip_separators('tel:+1-2') == '+12' and m.is_tel_uri('TEL:+1') is True
    finally:
        sys.settrace(None)
        _stop_import()
    missing = []
    for name, lines in want.items():
        for ln in sorted(lines):
            if (name, ln) not in hit:
                missing.append((name, ln))
    assert missing == []
    assert set(want) == {'_text', '_letter', '_digit', '_alphanum', '_iei', '_ici', '_hexval', '_paramchar', '_digits_code', '_pct_code', '_desc_domain_code', '_desc_code', '_pars_code', '_uri_code', 'is_tel_uri', 'split_tel_uri', 'number_kind', 'strip_separators'}


STATIC_CODES = {'_text': ['text-type'], 'split_tel_uri': ['<code>'], 'number_kind': ['<code>'], 'strip_separators': ['<code>']}


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
    assert sum(len(v) for v in got.values()) == 4


def test_cap_before_work_tracemalloc_pins():
    import tracemalloc
    n = 2000000
    big = 'a' * n
    big_e = '\u00e9' * n
    cases = (('split_tel_uri', (big,), 'text-length'), ('split_tel_uri', (big_e,), 'text-length'), ('number_kind', (big,), 'text-length'), ('strip_separators', (big,), 'text-length'), ('split_tel_uri', ('tel:+1;' + 'a' * n,), 'text-length'), ('split_tel_uri', ('tel:1;phone-context=' + 'a' * 256,), 'context-length'))
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
        assert m.is_tel_uri(big) is False and m.is_tel_uri(big_e) is False
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 20000, peak


DOC = 'b1243 RFC 3966 section 3: tel URI syntax for telephone numbers.\n\nSource: RFC 3966 (Schulzrinne, December 2004), section 3 (URI Syntax),\nwith the section 5.1.5 requirement that local numbers carry a\nphone-context. The grammar is \'telephone-uri = "tel:"\ntelephone-subscriber\' with \'telephone-subscriber = global-number /\nlocal-number\', \'global-number = global-number-digits *par\' and\n\'local-number = local-number-digits *par context *par\'. The digits rules\nare \'global-number-digits = "+" *phonedigit DIGIT *phonedigit\' and\n\'local-number-digits = *phonedigit-hex (HEXDIG / "*" / "#")\n*phonedigit-hex\' with \'phonedigit = DIGIT / [ visual-separator ]\',\n\'phonedigit-hex = HEXDIG / "*" / "#" / [ visual-separator ]\' and\n\'visual-separator = "-" / "." / "(" / ")"\'. Parameters follow \'par =\nparameter / extension / isdn-subaddress\' with \'parameter = ";" pname\n["=" pvalue ]\', \'extension = ";ext=" 1*phonedigit\' and \'context =\n";phone-context=" descriptor\' with \'descriptor = domainname /\nglobal-number-digits\'. On alphabetic numbers: "The URI format does not\nsupport this notation". On hex in local numbers: "However, in accordance\nwith E.164, these may not be included in global numbers." On case: "URI\ncomparisons are case-insensitive." On local numbers: "Local numbers MUST\nhave a \'phone-context\' parameter that identifies the scope of their\nvalidity." Global numbers: "Globally unique numbers are unambiguous\neverywhere in the world and SHOULD be used."\nErrata: four exist for RFC 3966 in the errata data used, cross-checked\nagainst the live index: 202 (Verified, Editorial, section 5.1.5) fixes an\nexample string and changes no grammar; not applied. 203 (Verified,\nEditorial, section 3) corrects \'isdn-subaddress = ";isub=" 1*uric\' to\n1*paramchar; APPLIED (isub values are validated as paramchar strings).\n702 (Held for Document Update, Editorial, section 12) and 4376 (Held for\nDocument Update, Editorial, section 3) are not applied. RFC 3966 obsoletes\nRFC 2806 and is updated by RFC 5341, which changes only the IANA tel URI\nparameter registration procedures; the section 3 grammar stands.\nOURS design choices (not sourced from the RFC): TEXT_MAX and DESC_MAX are\nimplementation bounds; the RFC sets no length limits. phone-context is\naccepted at most once per URI and is required for local numbers; in a\nglobal number it is validated like any descriptor (the ABNF admits it as\na generic parameter). Local-number hex letters are accepted in upper\ncase only, per the HEXDIG core rule; percent-encoding hex accepts both\ncases. split_tel_uri returns params in order as (pname, pvalue) pairs\nwith pvalue None when no \'=\' is present, including ext and isub but not\nphone-context, which has its own slot. The E.164 digit-count rules and\nany check-digit semantics are NOT implemented. The P235 error codes and\ntheir check order are ours.\nSOURCED: the tel scheme and subscriber grammar, the global and local\ndigits rules with their visual separators, the parameter, extension,\nisdn-subaddress and phone-context forms, the descriptor alternatives\nwith the domainname, domainlabel and toplabel rules, the pname and\npvalue character sets (mark, param-unreserved, pct-encoded), and the\ncase-insensitivity of comparisons.\nErrors raise ValueError P235:<name>:<code>.\n'


def test_whole_module_docstring_literal_and_ascii():
    assert m.__doc__ == DOC
    for p in (MODPATH, __file__):
        with open(p, 'rb') as fh:
            assert fh.read().isascii()
    assert '\\' not in m.__doc__
    assert 'four exist for RFC 3966' in m.__doc__
    assert '202' in m.__doc__ and '203' in m.__doc__ and '702' in m.__doc__ and '4376' in m.__doc__
    assert 'APPLIED' in m.__doc__ and 'Held for Document Update' in m.__doc__
    assert 'TEXT_MAX' in m.__doc__ and 'RFC 5341' in m.__doc__ and 'not applied' in m.__doc__
    assert 'OURS' in m.__doc__ and 'SOURCED' in m.__doc__
