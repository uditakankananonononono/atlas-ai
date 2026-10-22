import ast
import builtins
import hashlib
import importlib.util as iu
import pathlib
import random
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
SCOPE = 'PARTIAL: RFC 8707 resource parameter syntax over caller-supplied str values, URI shape only, no authority or path grammar, no policy'
PUBLIC = ['resource_check', 'resource_is_valid', 'resource_form_parse', 'resource_form_format', 'error_code_class']


@pytest.fixture(scope='module', autouse=True)
def load_module():
    global m
    from app.modules.instinct_doc import p235_concepts_batch1138_resource as mod
    m = mod


@pytest.fixture(autouse=True)
def alarm():
    def stop(*a):
        raise RuntimeError('test exceeded 15 seconds')
    old = signal.signal(signal.SIGALRM, stop)
    signal.alarm(15)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old)


@pytest.fixture(autouse=True)
def reg_guard(monkeypatch):
    present = REG in sys.modules
    old = sys.modules.get(REG)
    real_import = builtins.__import__
    real_fs = iu.find_spec
    yield
    monkeypatch.undo()
    ok = ((REG in sys.modules) == present and sys.modules.get(REG) is old
          and builtins.__import__ is real_import and iu.find_spec is real_fs)
    _stop_import()
    iu.find_spec = real_fs
    if present:
        sys.modules[REG] = old
    else:
        sys.modules.pop(REG, None)
    assert ok, 'a test leaked registry or import state'


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


def _pfx():
    # derived from the bound make_fail; the literal 'P235:x:c' is pinned separately against the exec'd fallback
    try:
        m.make_fail('x')('c')
    except ValueError as e:
        msg = str(e)
        assert msg.endswith('x:c')
        return msg[:-len('x:c')]
    raise AssertionError('make_fail did not raise')


def refuse(fn, code, *args):
    with pytest.raises(ValueError) as caught:
        getattr(m, fn)(*args)
    assert type(caught.value) is ValueError
    assert str(caught.value) == _pfx() + fn + ':' + code


def refusal(fn, *args):
    try:
        getattr(m, fn)(*args)
    except ValueError as e:
        assert type(e) is ValueError
        msg = str(e)
        assert msg.startswith(_pfx() + fn + ':')
        return msg[len(_pfx() + fn + ':'):]
    return None


# ---------------------------------------------------------------- hostile types
class SStr(str):
    pass


class SList(list):
    pass


class STuple(tuple):
    pass


class SDict(dict):
    pass


class Meta(type):
    def __eq__(cls, other):
        return True

    def __hash__(cls):
        return 1


class MetaStr(str, metaclass=Meta):
    pass


class MetaList(list, metaclass=Meta):
    pass


class Boom:
    def __eq__(self, other):
        raise RuntimeError('eq')

    def __hash__(self):
        raise RuntimeError('hash')

    def __len__(self):
        raise RuntimeError('len')

    def __iter__(self):
        raise RuntimeError('iter')

    def __bool__(self):
        raise RuntimeError('bool')


HOSTILE = [None, True, False, 0, 1, 1.5, b'a', bytearray(b'a'), {'a': 1}, {'a'}, object(), SStr('a:b'), SStr(''), MetaStr('a:b'), SList(), STuple(),
           SDict(), MetaList(), Boom(), complex(1, 1), str, len]
UNRES = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


# ---------------------------------------------------------------- oracle (independent of the module: regexes and plain loops)
O_SCHEME = re.compile(r'[A-Za-z][A-Za-z0-9+\-.]*:')
O_REST = re.compile(r"[A-Za-z0-9\-._~!$&'()*+,;=:/?@\[\]]|%[0-9A-Fa-f]{2}|(#)|(%)|(.)", re.S)
O_FORM = re.compile(r"[A-Za-z0-9\-._~!$'()*,;:@/?+=&]|%[0-9A-Fa-f]{2}|(%)|(.)", re.S)
O_ERR = re.compile(r'[ !#-\[\]-~]+')


def o_resource(v):
    if len(v) > 2048:
        return None, 'bad_value:resource.length'
    if v == '':
        return None, 'bad_value:resource.empty'
    mt = O_SCHEME.match(v)
    if not mt:
        return None, 'bad_value:resource.scheme'
    for tok in O_REST.finditer(v, mt.end()):
        if tok.group(1):
            return None, 'bad_value:resource.fragment'
        if tok.group(2):
            return None, 'bad_value:resource.pct'
        if tok.group(3) is not None:
            return None, 'bad_value:resource.char'
    return (v[:mt.end() - 1], '?' in v[mt.end():]), None


def agree_resource(v):
    if type(v) is not str:
        exp, err = None, 'bad_type:resource'
    else:
        exp, err = o_resource(v)
    if err is None:
        assert m.resource_check(v) == exp
        assert m.resource_is_valid(v) is True
    else:
        assert refusal('resource_check', v) == err
        assert m.resource_is_valid(v) is False
    return err


def o_decode(text):
    out = []
    for tok in re.finditer(r'%(..)|\+|.', text, re.S):
        if tok.group(1):
            n = int(tok.group(1), 16)
            if n > 127:
                return None
            out.append(chr(n))
        elif tok.group() == '+':
            out.append(' ')
        else:
            out.append(tok.group())
    return ''.join(out)


def o_form_parse(form):
    if type(form) is not str:
        return None, 'bad_type:form'
    if len(form) > 8192:
        return None, 'bad_value:form.length'
    if form == '':
        return (), None
    if len(form.split('&')) > 64:
        return None, 'bad_value:form.count'
    found = []
    for piece in form.split('&'):
        if piece == '':
            return None, 'bad_value:form.pair'
        for tok in O_FORM.finditer(piece):
            if tok.group(1):
                return None, 'bad_value:form.pct'
            if tok.group(2) is not None:
                return None, 'bad_value:form.char'
        name, _, value = piece.partition('=')
        dn = o_decode(name)
        if dn is None:
            return None, 'bad_value:form.octet'
        if dn == 'resource':
            dv = o_decode(value)
            if dv is None:
                return None, 'bad_value:form.octet'
            r, e = o_resource(dv)
            if e:
                return None, e
            found.append(dv)
    if len(found) > 16:
        return None, 'bad_value:form.resources'
    return tuple(found), None


def agree_form(form):
    exp, err = o_form_parse(form)
    if err is None:
        assert m.resource_form_parse(form) == exp
    else:
        assert refusal('resource_form_parse', form) == err
    return err


def o_format(resources):
    import urllib.parse
    if type(resources) is not tuple and type(resources) is not list:
        return None, 'bad_type:resources'
    if len(resources) > 16:
        return None, 'bad_value:resources.count'
    pairs = []
    for it in resources:
        if type(it) is not str:
            return None, 'bad_type:resources.item'
        r, e = o_resource(it)
        if e:
            return None, e
        pairs.append('resource=' + urllib.parse.quote(it, safe=''))
    out = '&'.join(pairs)
    if len(out) > 8192:
        return None, 'bad_value:form.length'
    return out, None


def agree_format(resources):
    exp, err = o_format(resources)
    if err is None:
        got = m.resource_form_format(resources)
        assert got == exp
        assert m.resource_form_parse(got) == tuple(resources)
    else:
        assert refusal('resource_form_format', resources) == err
    return err


def o_error(code):
    if type(code) is not str:
        return None, 'bad_type:error'
    if len(code) > 64:
        return None, 'bad_value:error.length'
    if code == '':
        return None, 'bad_value:error.empty'
    if not O_ERR.fullmatch(code):
        return None, 'bad_value:error.char'
    return ('invalid_target' if code == 'invalid_target' else 'other'), None


def agree_error(code):
    exp, err = o_error(code)
    if err is None:
        assert m.error_code_class(code) == exp
    else:
        assert refusal('error_code_class', code) == err
    return err


# ---------------------------------------------------------------- constants and exact text
def test_constants_and_char_set_literals_pinned_whole():
    assert m.SCOPE == SCOPE and type(m.SCOPE) is str
    assert m.NOT_CLAIMED == (
        'the RFC 3986 authority, host, port, path and query grammar beyond the character sets used here',
        'whether a resource is known, acceptable, audience restricted or reachable',
        'JWT aud claims, token introspection, and any authorization server policy',
        'the RFC 6749 error response structure beyond the error code character set',
        'global novelty', 'production readiness')
    assert type(m.NOT_CLAIMED) is tuple
    caps = (m.RESOURCE_CAP, m.FORM_CAP, m.PAIR_CAP, m.RESOURCE_COUNT_CAP, m.ERROR_CAP)
    assert caps == (2048, 8192, 64, 16, 64) and all(type(x) is int for x in caps)
    assert m._ALPHA == 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz' and type(m._ALPHA) is str
    assert m._DIGIT == '0123456789' and type(m._DIGIT) is str
    assert m._UNRESERVED == UNRES and len(m._UNRESERVED) == 66
    assert m._SCHEME_START == frozenset(m._ALPHA) and type(m._SCHEME_START) is frozenset and len(m._SCHEME_START) == 52
    assert m._SCHEME_REST == frozenset(m._ALPHA + m._DIGIT + '+-.') and type(m._SCHEME_REST) is frozenset and len(m._SCHEME_REST) == 65
    assert m._URI_CHARS == frozenset(UNRES + "!$&'()*+,;=:/?@[]") and type(m._URI_CHARS) is frozenset and len(m._URI_CHARS) == 83
    assert '#' not in m._URI_CHARS and '%' not in m._URI_CHARS
    assert m._FORM_CHARS == frozenset(UNRES + "!$'()*,;:@/?" + '%+=&') and type(m._FORM_CHARS) is frozenset and len(m._FORM_CHARS) == 82
    assert m._HEXVAL == dict(zip('0123456789ABCDEFabcdef', list(range(16)) + list(range(10, 16)))) and type(m._HEXVAL) is dict
    assert m._HEXOUT == '0123456789ABCDEF' and type(m._HEXOUT) is str
    assert m._UNRESERVED_SET == frozenset(UNRES) and type(m._UNRESERVED_SET) is frozenset
    for n in PUBLIC:
        assert callable(getattr(m, n))


DOC_SHA = '6cd509ce02a4824e4188583bf0d808f55291b733e8c8940b11d7b527288f6478'
FUNC_DOC = {
    'resource_check': 'Check one resource parameter value and return (scheme, has_query).',
    'resource_is_valid': 'True exactly when resource_check(value) does not refuse; never raises.',
    'resource_form_parse': 'Return the tuple of decoded resource values in a form string.',
    'resource_form_format': 'Return a form string with one resource=<value> pair per value.',
    'error_code_class': "Return 'invalid_target' for that exact error code, else 'other'.",
}


@pytest.mark.parametrize('name', sorted(FUNC_DOC))
def test_every_public_doc_is_exact(name):
    assert getattr(m, name).__doc__ == FUNC_DOC[name]


def test_module_docstring_pinned():
    doc = m.__doc__
    assert doc.startswith('Batch 1138 - RFC 8707 resource indicators: the resource parameter (PARTIAL).\n')
    flat = ' '.join(doc.split())
    for needle in ('Caps: resource 2048 characters, form 8192, 64 pairs, 16 resource values, error code 64.',
                   'the page and the index both list 1 erratum',
                   'Verified 6810 (Editorial, 2022-01-05, section 4)',
                   '"sever" should read "server"',
                   'A "#" anywhere after the scheme is a fragment',
                   'Decoding happens once: a value "%2541" becomes "%41"'):
        assert needle in flat, needle
    assert re.findall(r'^  \[(\d+)\] ', doc, re.M) == [str(i) for i in range(1, 15)]
    assert hashlib.sha256(doc.encode('utf-8')).hexdigest() == DOC_SHA


# ---------------------------------------------------------------- RFC 8707 examples
FIG2 = ('response_type=code&client_id=s6BhdRkqt3&state=tNwzQ87pC6llebpmac_IDeeq-mCR2wLDYljHUZUAWuI&redirect_uri=https%3A%2F%2Fclient.example.org%2Fcb'
        '&scope=calendar%20contacts&resource=https%3A%2F%2Fcal.example.com%2F&resource=https%3A%2F%2Fcontacts.example.com%2F')


def test_rfc_examples():
    assert m.resource_form_parse('response_type=token&client_id=example-client&state=XzZaJlcwYew1u0QBrRv_Gw&redirect_uri=https%3A%2F%2Fclient.example.org%2Fcb'
                                 '&resource=https%3A%2F%2Fapi.example.com%2Fapp%2F') == ('https://api.example.com/app/',)
    assert m.resource_form_parse(FIG2) == ('https://cal.example.com/', 'https://contacts.example.com/')
    assert m.resource_form_parse('grant_type=authorization_code&redirect_uri=https%3A%2F%2Fclient.example.org%2Fcb&code=10esc29BWC2qZB0acc9v8zAv9ltc2pko105tQauZ'
                                 '&resource=https%3A%2F%2Fcal.example.com%2F') == ('https://cal.example.com/',)
    assert m.resource_form_parse('grant_type=refresh_token&refresh_token=4LTC8lb0acc6Oy4esc1Nk9BWC0imAwH7kic16BDC2&resource=https%3A%2F%2Fcontacts.example.com%2F') == (
        'https://contacts.example.com/',)
    assert m.resource_form_format(['https://cal.example.com/', 'https://contacts.example.com/']) == (
        'resource=https%3A%2F%2Fcal.example.com%2F&resource=https%3A%2F%2Fcontacts.example.com%2F')
    for v, exp in (('https://api.example.com/', ('https', False)), ('https://apps.example.com/scim/', ('https', False)), ('https://apps.example.com/scim/Users', ('https', False)),
                   ('https://example.com/app?tenant=a', ('https', True)), ('urn:example:resource', ('urn', False)), ('a:', ('a', False)), ('A+b-c.9:?', ('A+b-c.9', True))):
        assert m.resource_check(v) == exp
        assert type(m.resource_check(v)) is tuple
    assert m.error_code_class('invalid_target') == 'invalid_target'
    assert m.error_code_class('invalid_request') == 'other'
    assert m.error_code_class('Invalid_Target') == 'other'
    assert m.error_code_class('invalid_target ') == 'other'


# ---------------------------------------------------------------- resource_check: codes, order, boundaries
def test_resource_codes_and_order():
    P = 'bad_value:'
    refuse('resource_check', 'bad_type:resource', None)
    refuse('resource_check', P + 'resource.length', 'a' * 2049)
    refuse('resource_check', P + 'resource.length', '#' * 2049)
    refuse('resource_check', P + 'resource.empty', '')
    refuse('resource_check', P + 'resource.scheme', '1a:b')
    refuse('resource_check', P + 'resource.scheme', ':b')
    refuse('resource_check', P + 'resource.scheme', 'ab')
    refuse('resource_check', P + 'resource.scheme', 'a')
    refuse('resource_check', P + 'resource.scheme', 'a b:c')
    refuse('resource_check', P + 'resource.scheme', 'a_b:c')
    refuse('resource_check', P + 'resource.scheme', 'a#b:c')
    refuse('resource_check', P + 'resource.scheme', '//x/y')
    refuse('resource_check', P + 'resource.scheme', '/x:y')
    refuse('resource_check', P + 'resource.scheme', 'a%41:b')
    refuse('resource_check', P + 'resource.fragment', 'a:b#')
    refuse('resource_check', P + 'resource.fragment', 'https://x/y#frag')
    refuse('resource_check', P + 'resource.fragment', 'a:#')
    refuse('resource_check', P + 'resource.pct', 'a:b%zz#')
    refuse('resource_check', P + 'resource.fragment', 'a:#%zz')
    refuse('resource_check', P + 'resource.pct', 'a:%')
    refuse('resource_check', P + 'resource.pct', 'a:%4')
    refuse('resource_check', P + 'resource.pct', 'a:%4g')
    refuse('resource_check', P + 'resource.pct', 'a:%g4')
    refuse('resource_check', P + 'resource.pct', 'a:x% ')
    refuse('resource_check', P + 'resource.char', 'a: ')
    refuse('resource_check', P + 'resource.char', 'a:b c')
    refuse('resource_check', P + 'resource.char', 'a:b"c')
    refuse('resource_check', P + 'resource.char', 'a:b c%zz')
    refuse('resource_check', P + 'resource.pct', 'a:b%zz c')
    refuse('resource_check', P + 'resource.char', 'a:b\x00')
    refuse('resource_check', P + 'resource.char', 'a:\u00e9')
    assert m.resource_check('a:b' + '%41' * 3) == ('a', False)
    assert m.resource_check('a:%41') == ('a', False)
    assert m.resource_check('a:%aF') == ('a', False)
    assert m.resource_check('a:' + 'x' * 2) == ('a', False)
    assert m.resource_check('a:[::1]/x') == ('a', False)
    assert m.resource_check('a:?') == ('a', True)
    assert m.resource_check('a:b?c?d') == ('a', True)
    assert m.resource_check('a:b/c?') == ('a', True)
    refuse('resource_check', P + 'resource.scheme', 'a?b:c')


def test_length_boundary():
    ok = 'a:' + 'b' * 2046
    assert len(ok) == 2048 and m.resource_check(ok) == ('a', False) and m.resource_is_valid(ok) is True
    refuse('resource_check', 'bad_value:resource.length', ok + 'b')
    assert m.resource_is_valid(ok + 'b') is False
    ok2 = 'a:' + '%41' * 682
    assert len(ok2) == 2048 and m.resource_is_valid(ok2) is True
    refuse('resource_check', 'bad_value:resource.length', ok2 + 'b')
    ok3 = 'a:?' + 'q' * 2045
    assert len(ok3) == 2048 and m.resource_check(ok3) == ('a', True)
    refuse('resource_check', 'bad_value:resource.length', ok3 + 'q')


def test_query_flag_is_after_the_scheme_colon_only():
    for v, q in (('a:b', False), ('a:b?', True), ('a:?', True), ('a:b/c?d=e', True), ('a:b%3Fc', False), ('a:/?', True), ('a:b=c', False), ('a:??', True), ('a:x/y/z', False)):
        assert m.resource_check(v)[1] is q, v
        assert type(m.resource_check(v)[1]) is bool


# ---------------------------------------------------------------- per-character sweeps
def test_char_sweep_every_slot():
    for code in range(0, 0x200):
        ch = chr(code)
        for u in (ch, 'a:' + ch, 'a:b' + ch, 'a:' + ch + 'b', 'a:b' + ch + 'c', 'a' + ch + ':b', ch + 'a:b', 'a:b?' + ch, 'a:%41' + ch, 'a:' + ch + '%41'):
            agree_resource(u)
        for u in ('a:%' + ch + '1', 'a:%1' + ch, 'a:%' + ch + ch):
            agree_resource(u)


def test_uri_char_set_exact():
    allowed = set(UNRES + "!$&'()*+,;=:/?@[]")
    got = {chr(c) for c in range(0x200) if m.resource_is_valid('a:' + chr(c)) and chr(c) != '%'}
    assert got == allowed
    assert m.resource_is_valid('a:%41') and not m.resource_is_valid('a:%')
    sch = {chr(c) for c in range(0x200) if m.resource_is_valid('a' + chr(c) + ':')}
    assert sch == set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-.:')  # ':' ends the scheme early
    first = {chr(c) for c in range(0x200) if m.resource_is_valid(chr(c) + ':')}
    assert first == set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
    for k in range(1, 5):
        for c in range(0x100):
            agree_resource('a' * k + chr(c) + 'b:x')
            agree_resource('a' * k + chr(c) + ':x')


def _nonascii_class_points():
    import unicodedata
    pts = []
    for c in range(0x80, 0x110000):
        ch = chr(c)
        if ch.isdigit() or ch.isnumeric() or ch.isalpha() or ch.isalnum() or ch.isdecimal() or unicodedata.category(ch) == 'Nd' or ch.upper() != ch or ch.lower() != ch:
            pts.append(c)
    return pts


POINTS = _nonascii_class_points()


def test_nd_digit_numeric_alpha_case_points_refused_in_every_slot():
    assert len(POINTS) > 100000
    bad = []
    for c in POINTS:
        ch = chr(c)
        for u in (ch + ':b', 'a' + ch + ':b', 'a:' + ch, 'a:b' + ch, 'a:b?' + ch, 'a:%' + ch + '0', 'a:%0' + ch):
            if m.resource_is_valid(u):
                bad.append((c, u))
        for form in ('resource=a%3A' + ch, ch + '=a', 'resource' + ch + '=a%3Ab', 'a=' + ch, 'a=%' + ch + '0', 'resource=a%3A%' + ch + '0', 'resource=a%3A%0' + ch):
            if refusal('resource_form_parse', form) is None:
                bad.append((c, form))
        if refusal('error_code_class', 'a' + ch) is None:
            bad.append((c, 'err'))
    assert bad == []
    for u in ('a:%\uff11\uff11', 'a:%\u0661\u0661', 'a:%\u00b2\u00b2', 'a:%\uff21\uff21', 'a:%\u2169\u2169'):
        refuse('resource_check', 'bad_value:resource.pct', u)
    for u in ('\u212a:b', '\u0131:b', 'a\u017f:b', 'a\u0661:b', '\uff21:b', 'a\u212a:b'):
        refuse('resource_check', 'bad_value:resource.scheme', u)


# ---------------------------------------------------------------- loop-advance pins
TERMS = ['%', '%A', '%AB', '?', '&', '=', '#', ' ', '\x00', '\u0100', '/', '[', ']', ':', '+', '\r\n', '\u212a', '\uff11']


@pytest.mark.parametrize('term', TERMS)
def test_resource_scan_stops_at_first_bad_char_with_more_text_after(term):
    base = 'ab%41-._~!$'
    for k in range(0, len(base) + 1):
        pre = base[:k]
        for tail in ('', 'x', 'xy', '%41', term + 'q', '#', '%zz', ' '):
            for text in (pre + term + tail, pre + term + tail + term, term + pre + tail):
                agree_resource('a:' + text)
                agree_resource('a:b?' + text)
                agree_resource(text + ':x')
                agree_resource('a' + text + ':x')


@pytest.mark.parametrize('term', TERMS)
def test_form_scan_stops_at_first_bad_char_with_more_text_after(term):
    base = 'ab%41-._~!$'
    for k in range(0, len(base) + 1):
        pre = base[:k]
        for tail in ('', 'x', '%41', term + 'q', '&', '=', '#', '%zz'):
            for text in (pre + term + tail, pre + term + tail + term, term + pre + tail):
                agree_form('resource=a%3A' + text)
                agree_form(text + '=1&resource=a%3Ab')
                agree_form('resource=a%3Ab&' + text)
                agree_form(text)


def test_pct_run_lengths_and_positions():
    for n in range(0, 6):
        for tail in ('', '%', '%4', '%41', 'x', '%zz'):
            agree_resource('a:' + '%41' * n + tail)
            agree_resource('a:x' * 1 + '%41' * n + tail + 'y')
            agree_form('resource=a%3A' + '%2541' * n + tail)
            agree_form('x=' + '%41' * n + tail + '&resource=a%3Ab')
    # a triplet is consumed whole: the two hex digits are not scanned as characters
    assert m.resource_is_valid('a:%41%41') and m.resource_is_valid('a:%FF') and m.resource_is_valid('a:%ff')
    assert m.resource_is_valid('a:%00')  # the pct triplet is syntactically fine even for a control octet
# ---------------------------------------------------------------- form parse
def test_form_codes_and_order():
    P = 'bad_value:'
    F = 'resource_form_parse'
    refuse(F, 'bad_type:form', None)
    refuse(F, P + 'form.length', 'a' * 8193)
    refuse(F, P + 'form.length', '&' * 8193)
    assert m.resource_form_parse('') == () and type(m.resource_form_parse('')) is tuple
    refuse(F, P + 'form.count', '&' * 64 + 'a=%')
    refuse(F, P + 'form.count', '&'.join(['a'] * 65))
    assert m.resource_form_parse('&'.join(['a'] * 64)) == ()
    refuse(F, P + 'form.pair', '&')
    refuse(F, P + 'form.pair', 'a=1&')
    refuse(F, P + 'form.pair', '&a=1')
    refuse(F, P + 'form.pair', 'a=1&&b=2')
    refuse(F, P + 'form.pair', 'a=1&&%')
    refuse(F, P + 'form.pct', 'a=%')
    refuse(F, P + 'form.pct', 'a=%4')
    refuse(F, P + 'form.pct', 'a=%4g')
    refuse(F, P + 'form.pct', '%g4=1')
    refuse(F, P + 'form.char', 'a b=1')
    refuse(F, P + 'form.char', 'a=1 ')
    refuse(F, P + 'form.char', 'a=#')
    refuse(F, P + 'form.char', 'a=\u00e9')
    refuse(F, P + 'form.char', 'a="')
    refuse(F, P + 'form.char', 'a=[')
    refuse(F, P + 'form.pct', 'a=% #')
    refuse(F, P + 'form.char', 'a=# %')
    refuse(F, P + 'form.octet', '%80=1')
    refuse(F, P + 'form.octet', 'a%FF=1')
    refuse(F, P + 'form.octet', 'resource=%80')
    refuse(F, P + 'form.octet', 'resource=a%3A%C3%A9')
    refuse(F, P + 'form.octet', 'resource=a+%80')
    refuse(F, P + 'form.octet', 'resource=a+%FF')
    refuse(F, P + 'form.octet', 'r%65source=9$+%80+)&=&resource=B')
    assert m.resource_form_parse('%7F=1') == ()
    assert m.resource_form_parse('=%80') == ()
    assert m.resource_form_parse('=%C3%A9') == ()
    assert m.resource_form_parse('=%FF') == ()
    assert m.resource_form_parse('=%80&resource=a%3Ab') == ('a:b',)
    refuse(F, P + 'resource.empty', 'resource=')
    refuse(F, P + 'resource.empty', 'resource')
    refuse(F, P + 'resource.scheme', 'resource=abc')
    refuse(F, P + 'resource.scheme', 'resource=a+b%3Ac')
    refuse(F, P + 'resource.char', 'resource=a%3Ab+c')
    refuse(F, P + 'resource.char', 'resource=a%3A%00')
    refuse(F, P + 'resource.fragment', 'resource=a%3Ab%23c')
    refuse(F, P + 'resource.pct', 'resource=a%3A%2541%25')
    refuse(F, P + 'resource.pct', 'resource=a%3A%25')
    refuse(F, P + 'resource.length', 'resource=a%3A' + 'b' * 2047)
    assert m.resource_form_parse('resource=a%3A%2541') == ('a:%41',)
    assert m.resource_form_parse('resource=a%3Ab%3Fc') == ('a:b?c',)
    assert m.resource_form_parse('resource=a:b') == ('a:b',)
    assert m.resource_form_parse('resource=a%3Ab=c') == ('a:b=c',)
    assert m.resource_form_parse('%72esource=a%3Ab') == ('a:b',)
    assert m.resource_form_parse('r%65source=a%3Ab&resou%72ce=c%3Ad') == ('a:b', 'c:d')
    assert m.resource_form_parse('resource=a%3Ab&resource=a%3Ab') == ('a:b', 'a:b')
    for name in ('Resource', 'RESOURCE', 'resources', 'resourc', 'resource ', ' resource', 'resource%00', 'xresource'):
        got = refusal('resource_form_parse', name + '=a%3Ab')
        assert got is None or got.startswith('bad_value:form.')
        if got is None:
            assert m.resource_form_parse(name + '=a%3Ab') == ()
    assert m.resource_form_parse('Resource=a%3Ab&RESOURCE=c') == ()
    assert m.resource_form_parse('resource%2B=a%3Ab') == ()
    assert m.resource_form_parse('resource%20=a%3Ab') == ()
    assert m.resource_form_parse('res+ource=a') == ()
    # the first failing pair wins, whatever later pairs hold
    refuse(F, P + 'form.pct', 'a=%&resource=')
    refuse(F, P + 'resource.empty', 'resource=&a=%')
    refuse(F, P + 'form.pair', 'a=1&&resource=')
    refuse(F, P + 'resource.scheme', 'resource=ab&&')
    refuse(F, P + 'resource.scheme', 'resource=ab&x=%')
    refuse(F, P + 'form.pct', 'x=%&resource=ab')


def test_form_value_decodes_once_and_plus_is_space():
    assert m.resource_form_parse('resource=a%3Ab%2541') == ('a:b%41',)
    refuse('resource_form_parse', 'bad_value:resource.pct', 'resource=a%3Ab%2541%2541%25')
    refuse('resource_form_parse', 'bad_value:resource.char', 'resource=a%3Ab+')
    refuse('resource_form_parse', 'bad_value:resource.char', 'resource=a%3A+')
    assert m.resource_form_parse('resource=a%3Ab%2Bc') == ('a:b+c',)
    assert m.resource_form_parse('resource=a%3Ab%3Dc%26d') == ('a:b=c&d',)
    assert m.resource_form_parse('x=%26&resource=a%3Ab') == ('a:b',)


def test_form_resource_count_cap_and_order():
    ok = '&'.join(['resource=a%3Ab'] * 16)
    assert m.resource_form_parse(ok) == ('a:b',) * 16
    for n in (17, 18, 20, 32, 33, 48, 63, 64):
        refuse('resource_form_parse', 'bad_value:form.resources', '&'.join(['resource=a%3Ab'] * n))
    refuse('resource_form_parse', 'bad_value:form.count', '&'.join(['resource=a%3Ab'] * 65))
    refuse('resource_form_parse', 'bad_value:form.count', '&'.join(['resource=a%3Ab'] * 66))
    refuse('resource_form_parse', 'bad_value:form.count', '&'.join(['resource=a%3Ab'] * 67))
    refuse('resource_form_parse', 'bad_value:form.count', '&'.join(['resource=a%3Ab'] * 128))
    assert m.resource_form_parse('&'.join(['x=1'] * 48 + ['resource=a%3Ab'] * 16)) == ('a:b',) * 16
    # a bad pair beats the count of resources found before it
    refuse('resource_form_parse', 'bad_value:resource.scheme', '&'.join(['resource=a%3Ab'] * 17 + ['resource=x']))
    refuse('resource_form_parse', 'bad_value:form.pct', '&'.join(['resource=a%3Ab'] * 17 + ['x=%']))
    refuse('resource_form_parse', 'bad_value:form.resources', '&'.join(['resource=a%3Ab'] * 17 + ['x=1']))
    for n in (60, 61, 62, 63, 64):
        agree_form('&'.join(['x'] * n))
        agree_form('&'.join(['resource=a%3Ab'] * min(n, 16) + ['x'] * (n - 16)) if n > 16 else 'resource=a%3Ab')


def test_form_length_boundary():
    ok = 'x=' + 'a' * 8190
    assert len(ok) == 8192 and m.resource_form_parse(ok) == ()
    refuse('resource_form_parse', 'bad_value:form.length', ok + 'a')
    ok2 = 'resource=a%3A' + 'b' * 2000 + '&x=' + 'y' * 6100
    assert len(ok2) <= 8192 and m.resource_form_parse(ok2) == ('a:' + 'b' * 2000,)
    refuse('resource_form_parse', 'bad_value:form.length', '&' * 8193)


# ---------------------------------------------------------------- form format
def test_format_codes_and_order():
    F = 'resource_form_format'
    refuse(F, 'bad_type:resources', None)
    refuse(F, 'bad_type:resources', 'a:b')
    refuse(F, 'bad_type:resources', {'a:b'})
    refuse(F, 'bad_value:resources.count', ['a:b'] * 17)
    refuse(F, 'bad_value:resources.count', ['a:b'] * 18)
    refuse(F, 'bad_value:resources.count', [5] * 17)
    refuse(F, 'bad_value:resources.count', ('a:b',) * 32)
    refuse(F, 'bad_type:resources.item', [5])
    refuse(F, 'bad_type:resources.item', ['a:b', None])
    refuse(F, 'bad_type:resources.item', [b'a:b'])
    refuse(F, 'bad_value:resource.empty', [''])
    refuse(F, 'bad_value:resource.scheme', ['ab'])
    refuse(F, 'bad_value:resource.fragment', ['a:b#c'])
    refuse(F, 'bad_value:resource.pct', ['a:b%'])
    refuse(F, 'bad_value:resource.char', ['a:b c'])
    refuse(F, 'bad_value:resource.length', ['a:' + 'b' * 2047])
    refuse(F, 'bad_value:resource.scheme', ['a:b', 'ab'])
    refuse(F, 'bad_type:resources.item', ['a:b', 5])
    refuse(F, 'bad_value:resource.scheme', ['ab', 'a b'])
    assert m.resource_form_format([]) == '' and m.resource_form_format(()) == ''
    assert m.resource_form_format(['a:b']) == 'resource=a%3Ab'
    assert m.resource_form_format(('a:b', 'c:d')) == 'resource=a%3Ab&resource=c%3Ad'
    assert m.resource_form_format(['a:%41']) == 'resource=a%3A%2541'
    assert m.resource_form_format(['a:/?@[]!$&\'()*+,;=:']) == 'resource=a%3A%2F%3F%40%5B%5D%21%24%26%27%28%29%2A%2B%2C%3B%3D%3A'
    assert m.resource_form_format(['a:' + UNRES]) == 'resource=a%3A' + UNRES
    assert m.resource_form_format(['a:b'] * 16) == '&'.join(['resource=a%3Ab'] * 16)
    big = ['a:' + 'b' * 2000] * 4
    assert len(m.resource_form_format(big)) == 4 * (9 + 4 + 2000) + 3
    refuse(F, 'bad_value:form.length', ['a:' + '/' * 600] * 5)


def test_format_length_cap_boundary_exact():
    # every '/' becomes %2F (3 chars); 'resource=' + 'a%3A' is 13 chars before the value
    assert len(m.resource_form_format(['a:' + '/' * 1000])) == 13 + 3000
    two = ['a:' + '/' * 1360, 'a:' + '/' * 1361]
    assert len(m.resource_form_format(two)) == 2 * 13 + 3 * (1360 + 1361) + 1 == 8190
    at = ['a:' + '/' * 1360, 'a:' + '/' * 1361 + 'xx']
    assert len(m.resource_form_format(at)) == 8192 and m.resource_form_parse(m.resource_form_format(at)) == tuple(at)
    one_less = ['a:' + '/' * 1360, 'a:' + '/' * 1361 + 'x']
    assert len(m.resource_form_format(one_less)) == 8191
    refuse('resource_form_format', 'bad_value:form.length', ['a:' + '/' * 1360, 'a:' + '/' * 1361 + 'xxx'])
    refuse('resource_form_format', 'bad_value:form.length', ['a:' + '/' * 1360, 'a:' + '/' * 1362])
    refuse('resource_form_format', 'bad_value:form.length', ['a:' + '/' * 1360, 'a:' + '/' * 1361 + 'xxxx'])


def test_format_parse_round_trip_for_every_ascii_char():
    for c in range(0x20, 0x7f):
        ch = chr(c)
        v = 'a:' + ch
        if m.resource_is_valid(v):
            f = m.resource_form_format([v])
            assert m.resource_form_parse(f) == (v,)
            assert f == 'resource=' + o_format([v])[0][9:]
            assert f.count('%') == (0 if ch in UNRES else 1) + 1
    assert m.resource_form_format(['a:b']) == m.resource_form_format(('a:b',))
    assert type(m.resource_form_format(['a:b'])) is str


# ---------------------------------------------------------------- error codes
def test_error_code_class():
    E = 'error_code_class'
    for ok in ('invalid_target', 'invalid_request', 'a', ' ', '!', '#', '[', ']', '~', 'x' * 64, 'invalid target', 'a!b#c[d]e~f'):
        assert m.error_code_class(ok) == ('invalid_target' if ok == 'invalid_target' else 'other')
    for c in range(0x200):
        ch = chr(c)
        ok = (0x20 <= c <= 0x21) or (0x23 <= c <= 0x5B) or (0x5D <= c <= 0x7E)
        assert refusal(E, ch) == (None if ok else 'bad_value:error.char'), c
        assert refusal(E, 'a' + ch + 'b') == (None if ok else 'bad_value:error.char'), c
        assert refusal(E, 'invalid_target' + ch) == (None if ok else 'bad_value:error.char'), c
    refuse(E, 'bad_type:error', None)
    refuse(E, 'bad_value:error.length', 'a' * 65)
    refuse(E, 'bad_value:error.length', '"' * 65)
    refuse(E, 'bad_value:error.empty', '')
    refuse(E, 'bad_value:error.char', '"')
    refuse(E, 'bad_value:error.char', 'invalid_target\\')
    refuse(E, 'bad_value:error.char', 'invalid_target\n')
    assert m.error_code_class('x' * 64) == 'other'
    for near in ('Invalid_Target', 'INVALID_TARGET', 'invalid_target ', ' invalid_target', 'invalid-target', 'invalid_targe', 'invalid_targets'):
        assert refusal(E, near) is None
    refuse(E, 'bad_value:error.char', 'invalid_targe\u0442')
    refuse(E, 'bad_value:error.char', 'invalid_target\u212a')
    assert m.error_code_class('invalid_targe') == 'other'
    assert m.error_code_class('nvalid_target') == 'other'
    assert m.error_code_class('i') == 'other'
    assert m.error_code_class('invalid_target') == 'invalid_target' and type(m.error_code_class('invalid_target')) is str


# ---------------------------------------------------------------- hostile types at every site
@pytest.mark.parametrize('bad', HOSTILE)
def test_hostile_single_arg_sites(bad):
    refuse('resource_check', 'bad_type:resource', bad)
    assert m.resource_is_valid(bad) is False
    refuse('resource_form_parse', 'bad_type:form', bad)
    refuse('error_code_class', 'bad_type:error', bad)


@pytest.mark.parametrize('bad', HOSTILE)
def test_hostile_format_sites(bad):
    if type(bad) is not list and type(bad) is not tuple:
        refuse('resource_form_format', 'bad_type:resources', bad)
    refuse('resource_form_format', 'bad_type:resources.item', [bad]) if type(bad) is not list and type(bad) is not tuple else None
    refuse('resource_form_format', 'bad_type:resources.item', ('a:b', bad))


@pytest.mark.parametrize('bad', [SStr('a:b'), MetaStr('a:b')])
def test_str_subclass_refused_at_each_str_site(bad):
    refuse('resource_form_format', 'bad_type:resources.item', [bad])
    refuse('resource_check', 'bad_type:resource', bad)
    refuse('resource_form_parse', 'bad_type:form', bad)
    refuse('error_code_class', 'bad_type:error', bad)


@pytest.mark.parametrize('cont', [SList, STuple, MetaList])
def test_container_subclass_refused(cont):
    refuse('resource_form_format', 'bad_type:resources', cont())
    refuse('resource_form_format', 'bad_type:resources', cont(['a:b']))


def test_other_containers_refused():
    for bad in ({}, {'a:b'}, frozenset(['a:b']), range(2), (x for x in ['a:b']), iter(['a:b']), SDict()):
        refuse('resource_form_format', 'bad_type:resources', bad)


# ---------------------------------------------------------------- cap before work, fuzz
def _peak(fn, *args):
    import tracemalloc
    tracemalloc.start()
    try:
        try:
            fn(*args)
        except ValueError:
            pass
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


BIG = 2000000
DENSE = [('a', 'letters'), (':', 'colons'), ('&', 'amps'), ('=', 'equals'), ('%', 'pct'), ('%41', 'pct-ok'), ('?', 'qmarks'), ('#', 'hashes'), ('+', 'plus'),
         ('resource=a%3Ab&', 'resource-dense'), ('\u0100', 'wide'), ('\x00', 'nul'), (' ', 'spaces'), ('"', 'quotes')]


@pytest.mark.parametrize('unit,label', DENSE)
def test_cap_is_checked_before_any_work_on_huge_input(unit, label):
    text = unit * (BIG // len(unit))
    assert len(text) >= BIG - 20
    for fn in ('resource_check', 'resource_is_valid', 'resource_form_parse', 'error_code_class'):
        assert _peak(getattr(m, fn), text) < 16384, (fn, label)
    assert _peak(m.resource_check, 'a:' + text) < 16384, label
    assert _peak(m.resource_form_parse, 'resource=' + text) < 16384, label
    assert _peak(m.resource_form_format, [text]) < 16384, label
    assert _peak(m.resource_form_format, ['a:' + text]) < 16384, label


def test_huge_inputs_get_cap_codes():
    for unit in ('a', ':', '&', '%', '#', '\u0100', ' '):
        refuse('resource_check', 'bad_value:resource.length', unit * BIG)
        refuse('resource_form_parse', 'bad_value:form.length', unit * BIG)
        refuse('error_code_class', 'bad_value:error.length', unit * BIG)
        refuse('resource_form_format', 'bad_value:resource.length', ['a:' + unit * BIG])
    refuse('resource_form_format', 'bad_value:resources.count', ['a:b'] * 1000000)
    refuse('resource_form_format', 'bad_value:resources.count', ('a:b',) * 1000000)
    refuse('resource_form_format', 'bad_value:resources.count', [None] * 1000000)
    assert _peak(m.resource_form_format, ['a:b'] * 1000000) < 16384
    assert _peak(m.resource_form_format, [5] * 1000000) < 16384
    assert _peak(m.resource_form_parse, '&' * 100000) < 16384
    assert _peak(m.resource_form_parse, 'a&' * 4096) < 16384


def test_just_over_each_cap_allocates_nothing_proportional():
    for unit in ('a', '%', '&', ':'):
        assert _peak(m.resource_check, unit * 2049) < 8192
        assert _peak(m.resource_form_parse, unit * 8193) < 8192
        assert _peak(m.error_code_class, unit * 65) < 8192
        assert _peak(m.resource_form_parse, '&'.join(['a'] * 65)) < 8192


def test_caps_every_neighbour():
    for n in (2046, 2047, 2048, 2049, 2050):
        agree_resource('a:' + 'b' * (n - 2))
        agree_resource('a:' + '%41' * ((n - 2) // 3))
    for n in (8190, 8191, 8192, 8193, 8194):
        agree_form('x=' + 'a' * (n - 2))
        agree_form('x' * n)
    for n in (62, 63, 64, 65, 66, 67):
        agree_form('&'.join(['a'] * n))
        agree_form('&'.join(['a=1'] * n))
    for n in (62, 63, 64, 65, 66, 67):
        agree_error('x' * n)
        agree_error('"' * n)
    for n in (15, 16, 17, 18, 31, 32, 33):
        agree_format(['a:b'] * n)
        agree_format(('a:b',) * n)
    for n in (0, 1, 2):
        agree_format(['a:b'] * n)
    assert m.error_code_class('x' * 63) == 'other' and m.error_code_class('x' * 64) == 'other'


ALPHA = list('ab:/?#%&=+4CF.-') + [' ', '\x00', '~', '\u0100', '\u212a', '\uff11', '[', ']', '"', '\\']


def _rand_text(rng):
    r = rng.random()
    if r < 0.03:
        return rng.choice(HOSTILE)
    body = ''.join(rng.choice(ALPHA) for _ in range(rng.choice([0, 1, 3, 6, 10, 20])))
    if rng.random() < 0.5:
        body = rng.choice(['a:', 'https://', 'urn:x:', 'resource=', 'x=1&resource=', 'A9+-.:']) + body
    if r < 0.05:
        body = body * rng.choice([30, 300])
    return body


def test_seeded_fuzz_against_the_oracle():
    rng = random.Random(8707)
    errs = set()
    for _ in range(15000):
        t = _rand_text(rng)
        errs.add(agree_resource(t))
        errs.add(agree_form(t) if type(t) is str else 'x')
        errs.add(agree_error(t) if type(t) is str else 'x')
    assert {None, 'bad_value:resource.scheme', 'bad_value:resource.char', 'bad_value:resource.pct', 'bad_value:resource.fragment', 'bad_value:resource.empty',
            'bad_value:form.char', 'bad_value:form.pct', 'bad_value:form.pair', 'bad_value:form.octet', 'bad_value:error.char'} <= errs


def test_seeded_format_fuzz_and_round_trip():
    rng = random.Random(6750)
    chars = list(UNRES) + list("!$&'()*+,;=:/?@[]%") + [' ', '#', '\u0100']
    errs = set()
    for _ in range(4000):
        vals = []
        for _ in range(rng.randint(0, 3)):
            v = 'a:' + ''.join(rng.choice(chars) for _ in range(rng.randint(0, 8)))
            if rng.random() < 0.1:
                v = rng.choice(['', 5, None, 'ab', 'a:b#', 'a:%'])
            vals.append(v)
        if rng.random() < 0.5:
            vals = tuple(vals)
        errs.add(agree_format(vals))
    assert None in errs and len(errs) >= 5
# ---------------------------------------------------------------- failure prefix, imports, namespace
def test_fallback_failer_prefix_is_the_literal_p235_x_c(undo_log):
    # pinned against a literal, never derived from the fallback's own output
    ns, seen, marker = _exec_logged(undo_log, 'absent')
    with pytest.raises(ValueError) as caught:
        ns['make_fail']('x')('c')
    assert str(caught.value) == 'P235:x:c'
    assert type(caught.value) is ValueError
    with pytest.raises(ValueError) as caught:
        ns['resource_check'](5)
    assert str(caught.value) == 'P235:resource_check:bad_type:resource'


def _exec_logged(log, registry):
    src = pathlib.Path(m.__file__).read_text()
    real_import = builtins.__import__
    _pop(log, sys.modules, REG)
    seen = []
    stub = types.ModuleType(REG)
    marker = []

    def stub_make_fail(name):
        def fail(code):
            marker.append((name, code))
            raise ValueError('Q7:%s:%s' % (name, code))
        return fail

    stub.make_fail = stub_make_fail

    def hooked(name, globals=None, locals=None, fromlist=(), level=0):
        if globals is not None and globals.get('__name__') == 'b1138_logged':
            seen.append((name, tuple(fromlist) if fromlist else None, level))
        if name == REG:
            if registry == 'absent':
                raise ModuleNotFoundError('No module named ' + repr(REG), name=REG)
            return stub
        return real_import(name, globals, locals, fromlist, level)

    real_fs = iu.find_spec

    def fs(*a, **k):
        # the simulated absent world: the registry is not resolvable even when a real one is on the path
        if a and a[0] == REG and registry == 'absent':
            return None
        return real_fs(*a, **k)

    _start_import(builtins, hooked)
    iu.find_spec = fs
    ns = {'__name__': 'b1138_logged'}
    try:
        exec(compile(src, 'm', 'exec'), ns)
    finally:
        _stop_import()
        iu.find_spec = real_fs
    return ns, seen, marker


LOG = [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]
NAMES = sorted(['RESOURCE_CAP', 'FORM_CAP', 'PAIR_CAP', 'RESOURCE_COUNT_CAP', 'ERROR_CAP', 'NOT_CLAIMED', 'SCOPE', '_ALPHA', '_DIGIT', '_UNRESERVED', '_SCHEME_START', '_SCHEME_REST', '_URI_CHARS', '_FORM_CHARS', '_HEXVAL', '_HEXOUT', '_UNRESERVED_SET', '_scheme', '_rest', '_resource', '_scan', '_decode', '__doc__', '__name__', 'find_spec', 'make_fail'] + PUBLIC)


def test_namespace_key_set_is_exact_in_every_world(undo_log):
    for world in ('absent', 'stub'):
        ns, seen, marker = _exec_logged(undo_log, world)
        assert sorted(k for k in ns if k != '__builtins__') == NAMES


def test_import_log_registry_absent(undo_log):
    ns, seen, marker = _exec_logged(undo_log, 'absent')
    assert seen == LOG
    with pytest.raises(ValueError) as e:
        ns['resource_check'](3)
    assert str(e.value) == 'P235:resource_check:bad_type:resource'
    assert marker == []


def test_import_log_stub_registry_and_alt_prefix(undo_log):
    ns, seen, marker = _exec_logged(undo_log, 'stub')
    assert seen == LOG
    for fn, args, code in (('resource_check', (5,), 'bad_type:resource'), ('resource_form_parse', (5,), 'bad_type:form'),
                           ('resource_form_format', (5,), 'bad_type:resources'), ('error_code_class', (5,), 'bad_type:error')):
        with pytest.raises(ValueError) as e:
            ns[fn](*args)
        assert str(e.value) == 'Q7:%s:%s' % (fn, code)
    assert marker == [('resource_check', 'bad_type:resource'), ('resource_form_parse', 'bad_type:form'),
                      ('resource_form_format', 'bad_type:resources'), ('error_code_class', 'bad_type:error')]
    assert ns['resource_is_valid'](5) is False


def _exec_raising(log, name_, exc, fs=None):
    src = pathlib.Path(m.__file__).read_text()
    real_import = builtins.__import__
    real_fs = iu.find_spec
    _pop(log, sys.modules, REG)
    seen = []

    def hooked(name, globals=None, locals=None, fromlist=(), level=0):
        if globals is not None and globals.get('__name__') == name_:
            seen.append((name, tuple(fromlist) if fromlist else None, level))
        if name == REG:
            raise exc
        return real_import(name, globals, locals, fromlist, level)

    _start_import(builtins, hooked)
    if fs is not None:
        iu.find_spec = fs
    try:
        exec(compile(src, 'm', 'exec'), {'__name__': name_})
    finally:
        _stop_import()
        iu.find_spec = real_fs
    return seen


def test_foreign_module_not_found_reraises_with_exact_log_and_no_find_spec(undo_log):
    exc = ModuleNotFoundError('foreign', name='app.other')
    spy = []

    def fs(*a, **k):
        spy.append(a)
        raise AssertionError('find_spec must not run for a foreign name')
    with pytest.raises(ModuleNotFoundError) as caught:
        _exec_raising(undo_log, 'b1138_foreign', exc, fs)
    assert caught.value is exc
    assert spy == []
    seen = []
    # the log in the same world
    real_import = builtins.__import__
    log2 = []

    def hooked(name, globals=None, locals=None, fromlist=(), level=0):
        if globals is not None and globals.get('__name__') == 'b1138_foreign2':
            log2.append((name, tuple(fromlist) if fromlist else None, level))
        if name == REG:
            raise exc
        return real_import(name, globals, locals, fromlist, level)
    _pop(undo_log, sys.modules, REG)
    _start_import(builtins, hooked)
    try:
        with pytest.raises(ModuleNotFoundError):
            exec(compile(pathlib.Path(m.__file__).read_text(), 'm', 'exec'), {'__name__': 'b1138_foreign2'})
    finally:
        _stop_import()
    assert log2 == LOG


def test_absent_with_find_spec_present_reraises_and_calls_find_spec_once(undo_log):
    exc = ModuleNotFoundError('absent but present', name=REG)
    spy = []
    real_fs = iu.find_spec

    def fs(*a, **k):
        if a and a[0] == REG:
            spy.append((a, k))
            return object()
        return real_fs(*a, **k)
    with pytest.raises(ModuleNotFoundError) as caught:
        _exec_raising(undo_log, 'b1138_present', exc, fs)
    assert caught.value is exc
    assert spy == [((REG,), {})]


@pytest.mark.parametrize('exc', [ImportError('x', name=REG), ImportError('x'), ImportError('x', name='app.other')])
def test_plain_import_error_never_falls_back(undo_log, exc):
    with pytest.raises(ImportError) as caught:
        _exec_raising(undo_log, 'b1138_ie', exc)
    assert caught.value is exc
    assert type(caught.value) is ImportError


@pytest.mark.parametrize('near', [REG + 'x', REG[:-1], REG.upper(), None, ''])
def test_near_miss_names_do_not_fall_back(undo_log, near):
    with pytest.raises(ModuleNotFoundError):
        _exec_raising(undo_log, 'b1138_near', ModuleNotFoundError('near', name=near))


def test_find_spec_none_means_fallback_and_object_means_reraise_identity(undo_log):
    src = pathlib.Path(m.__file__).read_text()
    real_import = builtins.__import__
    real_fs = iu.find_spec
    _pop(undo_log, sys.modules, REG)

    def hooked(name, *a, **k):
        if name == REG:
            raise ModuleNotFoundError('x', name=REG)
        return real_import(name, *a, **k)

    def fs(*a, **k):
        if a and a[0] == REG:
            return None
        return real_fs(*a, **k)
    _start_import(builtins, hooked)
    iu.find_spec = fs
    try:
        ns = {'__name__': 'b1138_fb'}
        exec(compile(src, 'm', 'exec'), ns)
    finally:
        _stop_import()
        iu.find_spec = real_fs
    assert ns['make_fail'].__qualname__ == 'make_fail'


def _call_everything(ns):
    texts = ['', 'a', 'a:', 'a:b', 'a:b?c', 'a:b#c', 'a:%41', 'a:%', 'a:%4', 'a:%zz', '1:b', ':b', 'a b:c', 'a:b c', 'a:\u0100', 'a:' + 'b' * 2047, 'a:' + 'b' * 2046,
             'resource=a%3Ab', 'resource=a%3Ab&resource=c%3Ad', 'x=1&resource=a%3Ab&y', 'resource', 'resource=', '&', 'a=1&&b=2', 'resource=%80', 'resource=%',
             'resource=a%3Ab#', 'resource=a+b', 'resource=a%3A%2541', '%72esource=a%3Ab', 'resource=' + 'a%3A' + 'b' * 5000, 'a' * 8193, '&'.join(['x'] * 65),
             'invalid_target', 'invalid_request', 'a"b', 'a\\b', ' ', '~', '\x7f', 'invalid_targe', 'invalid_targets', 'x' * 65]
    for t in texts:
        for fn in ('resource_check', 'resource_is_valid', 'resource_form_parse', 'error_code_class'):
            try:
                ns[fn](t)
            except ValueError:
                pass
    for bad in (5, None, b'a', SStr('a'), MetaStr('a'), object(), [], {}):
        for fn in ('resource_check', 'resource_is_valid', 'resource_form_parse', 'error_code_class', 'resource_form_format'):
            try:
                ns[fn](bad)
            except ValueError:
                pass
    for rs in ([], ['a:b'], ('a:b', 'c:d'), ['a:b?c#'], ['a:b c'], [5], [None], ['a:b'] * 17, ['a:' + 'b' * 2046] * 5, ['a:%41%'], ['', 'a:b'], ['a:\u0100'], ['a:b%'] * 2,
               ['a:/?@[]!$&\'()*+,;=:'], ['a:' + 'b' * 2046] * 4):
        try:
            ns['resource_form_format'](rs)
        except ValueError:
            pass


def test_import_freedom_across_all_public_functions_and_branches(undo_log):
    for world in ('absent', 'stub', 'live'):
        if world == 'live':
            ns = vars(m)
        else:
            ns, seen, marker = _exec_logged(undo_log, world)
            assert seen == LOG
        before = sorted(k for k in ns if k != '__builtins__')
        real_import = builtins.__import__
        calls = []

        def spy(name, globals=None, locals=None, fromlist=(), level=0):
            calls.append((name, tuple(fromlist) if fromlist else None, level))
            return real_import(name, globals, locals, fromlist, level)

        _start_import(builtins, spy)
        try:
            _call_everything(ns)
            assert ns['resource_check']('https://a/b?c') == ('https', True)
            assert ns['resource_check']('a:') == ('a', False)
            assert ns['resource_is_valid']('a:b') is True
            assert ns['resource_is_valid']('a:b#') is False
            assert ns['resource_form_parse']('resource=a%3Ab&x=1&resource=c%3Ad') == ('a:b', 'c:d')
            assert ns['resource_form_parse']('') == ()
            assert ns['resource_form_parse']('x=1') == ()
            assert ns['resource_form_format'](['a:b/c']) == 'resource=a%3Ab%2Fc'
            assert ns['resource_form_format']([]) == ''
            assert ns['error_code_class']('invalid_target') == 'invalid_target'
            assert ns['error_code_class']('other_code') == 'other'
        finally:
            _stop_import()
        assert calls == [], (world, calls)
        assert sorted(k for k in ns if k != '__builtins__') == before
        if world != 'live':
            assert before == NAMES


def test_source_has_exactly_the_two_import_statements():
    src = pathlib.Path(m.__file__).read_text()
    code = src.split('"""', 2)[2]
    lines = [ln.strip() for ln in code.split('\n') if re.match(r'\s*(import|from)\s', ln)]
    assert lines == ['from importlib.util import find_spec',
                     'from app.modules.instinct_doc.p235_concepts_registry import make_fail']
    assert len(re.findall(r'__import__|importlib\.import_module|\bexec\b|\beval\b', code)) == 0
    tree = ast.parse(src)
    assert len([n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]) == 2
    assert [type(n) for n in tree.body[1:3]] == [ast.ImportFrom, ast.Try]
    assert tree.body[1].module == 'importlib.util' and tree.body[1].level == 0
    # no str class methods on characters: explicit ASCII membership and ranges only
    assert re.findall(r'\.(isdigit|isalpha|isalnum|isspace|isupper|islower|isnumeric|isdecimal|isascii|upper|lower|casefold|strip|lstrip|rstrip)\(|\bint\(', code) == []


def _f_call_lines(path):
    tree = ast.parse(pathlib.Path(path).read_text())
    return {n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'f'}


NSITES = 25


def _sites_cases(ns):
    C = ns['resource_check']
    for v in (5, 'a' * 2049, '', '1:a', 'ab', 'a b:c', 'a:b#', 'a:%', 'a:%4g', 'a: '):
        with pytest.raises(ValueError):
            C(v)
    P = ns['resource_form_parse']
    for v in (5, 'a' * 8193, '&'.join(['x'] * 65), 'a&&b', 'a=%', 'a=%4g', 'a=\u0100', '%80=1', 'resource=%80', 'resource=a%3Ab%23', 'resource=',
              'resource=a%3Ab&' * 17 + 'x', 'resource=%2541', 'resource=a+b'):
        with pytest.raises(ValueError):
            P(v)
    F = ns['resource_form_format']
    for v in (5, ['a:b'] * 17, [5], ['a:b#'], [''], [('a:' + 'b' * 2046)] * 5):
        with pytest.raises(ValueError):
            F(v)
    E = ns['error_code_class']
    for v in (5, 'a' * 65, '', 'a"b'):
        with pytest.raises(ValueError):
            E(v)


def test_stub_world_every_f_site_is_exercised_by_line(undo_log):
    src = pathlib.Path(m.__file__).read_text()
    stub = types.ModuleType(REG)
    hit = set()

    def make_fail(name):
        def fail(code):
            hit.add(sys._getframe(1).f_lineno)
            raise ValueError('Q7:%s:%s' % (name, code))
        return fail
    stub.make_fail = make_fail
    _setitem(undo_log, sys.modules, REG, stub)
    ns = {'__name__': 'b1138_sites'}
    exec(compile(src, str(m.__file__), 'exec'), ns)
    want = _f_call_lines(m.__file__)
    assert len(want) == NSITES
    _sites_cases(ns)
    assert hit == want, sorted(want ^ hit)
