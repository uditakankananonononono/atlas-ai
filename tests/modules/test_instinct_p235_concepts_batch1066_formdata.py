"""Tests for b1066 RFC 7578 multipart/form-data framing. PARTIAL claims only."""
import ast
import builtins
import importlib
import hashlib
import importlib.util as iu
import json
import os
import pathlib
import random
import re
import signal
import sys
import tracemalloc
import types
import urllib.parse

import pytest

REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1066_formdata'
PUBLIC = ['boundary_ok', 'pct_encode_param', 'pct_decode_param', 'parse_form_data', 'serialize_form_data']

m = None


@pytest.fixture(scope='module', autouse=True)
def load_module():
    global m
    from app.modules.instinct_doc import p235_concepts_batch1066_formdata as mod
    m = mod


@pytest.fixture(autouse=True)
def alarm():
    def stop(*a):
        raise RuntimeError('test exceeded 120 seconds')
    old = signal.signal(signal.SIGALRM, stop)
    signal.alarm(120)
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
    assert ok


def pfx():
    try:
        m.make_fail('x')('c')
    except ValueError as e:
        s = str(e)
        assert s.endswith('x:c')
        return s[:-3]
    raise AssertionError('make_fail must raise')


def err(fn, *a):
    try:
        r = fn(*a)
    except ValueError as e:
        return str(e)
    raise AssertionError('expected refusal, got %r' % (r,))


def refuse(fn, want, *a):
    got = err(fn, *a)
    assert got == pfx() + fn.__name__ + ':' + want, (got, want)


class SStr(str):
    pass


class SBytes(bytes):
    pass


class SList(list):
    pass


class STuple(tuple):
    pass


# ---------------------------------------------------------------- constants, namespace, doc

def test_module_constants_pinned_whole():
    assert m.CLAIMS is False
    assert m.SCOPE == 'RFC 7578 multipart/form-data framing and part headers'
    assert m.NOT_CLAIMED == ('html-forms', 'charset', 'filename-sanitising', 'multipart-mixed',
                             'outer-content-type', 'transfer-encoding', 'rfc2231', 'errata')
    assert m.ADJACENT == ('b1021', 'b1062')
    assert (m.MAX_BODY, m.MAX_PARTS, m.MAX_BOUNDARY_INPUT, m.MAX_TEXT, m.MAX_PARAM,
            m.MAX_LINE, m.MAX_HEADERS, m.MAX_CT) == (262144, 64, 256, 255, 3072, 8192, 8, 255)
    ALNUM = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    assert m._ALNUM == ALNUM
    assert m._BCHARS == ALNUM + "'()+_,-./:=? "
    assert m._UNRES == ALNUM + '-._~'
    assert m._TOKEN == ALNUM + "!#$%&'*+-.^_`|~"
    assert m._HEX == '0123456789abcdefABCDEF'
    assert m._UPPER_HEX == '0123456789ABCDEF'
    assert m._CRLF == b'\r\n'
    assert type(m.MAX_BODY) is int and type(m.CLAIMS) is bool


def test_module_namespace_is_exact():
    want = {'ADJACENT', 'CLAIMS', 'MAX_BODY', 'MAX_PARTS', 'MAX_BOUNDARY_INPUT', 'MAX_TEXT', 'MAX_PARAM',
            'MAX_LINE', 'MAX_HEADERS', 'MAX_CT', 'NOT_CLAIMED', 'SCOPE', '_REG', '_STR', '_BYTES', '_LIST',
            '_TUPLE', '_ALNUM', '_BCHARS', '_UNRES', '_TOKEN', '_HEX', '_UPPER_HEX', '_CRLF', '_Soft',
            '_soft', '_arg', '_barg', '_all_in', '_boundary', '_enc', '_ct_ok', '_disp', '_part', '_frame',
            'make_fail', '__doc__', '__name__', '__package__', '__loader__', '__spec__', '__file__',
            '__cached__', '__builtins__'} | set(PUBLIC)
    ns = set(vars(m))
    if '_find_spec' in ns:  # fallback branch (no registry on the path)
        assert ns == want | {'_find_spec'}
    else:  # registry-present world
        assert ns == want


def test_module_has_exactly_two_top_level_imports():
    src = pathlib.Path(m.__file__).read_text()
    tree = ast.parse(src)
    imps = [n for n in tree.body if type(n) is ast.Import or type(n) is ast.ImportFrom]
    assert imps == []
    trys = [n for n in tree.body if type(n) is ast.Try]
    assert len(trys) == 1
    t = trys[0]
    assert [type(n) for n in t.body] == [ast.ImportFrom]
    assert t.body[0].module == REG and t.body[0].names[0].name == 'make_fail'
    assert len(t.handlers) == 1 and t.handlers[0].type.id == 'ModuleNotFoundError'
    inner = [n for n in t.handlers[0].body if type(n) is ast.Import or type(n) is ast.ImportFrom]
    assert len(inner) == 1 and inner[0].module == 'importlib.util'
    assert src.count('import ') == 2


def test_module_docstring_pinned_whole():
    assert hashlib.sha256(m.__doc__.encode('utf-8')).hexdigest() == DOC_SHA


def test_public_functions_have_no_docstrings_and_exact_names():
    for name in PUBLIC:
        f = getattr(m, name)
        assert type(f).__name__ == 'function'
        assert f.__doc__ is None
        assert f.__module__ == MODNAME
    src = pathlib.Path(m.__file__).read_text()
    defs = [n.name for n in ast.walk(ast.parse(src)) if type(n) is ast.FunctionDef]
    assert sorted(defs) == sorted(['_soft', '_arg', '_barg', '_all_in', '_boundary', '_enc', '_ct_ok',
                                   '_disp', '_part', '_frame', 'make_fail', 'fail'] + PUBLIC)


DOC_SHA = 'a48175738af3ae80b3309327b418ea0bde4b8f1d6ae60922b3021d9271454319'


# ---------------------------------------------------------------- boundary_ok

BCHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'()+_,-./:=? "
UNRES = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'
TOKEN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$%&'*+-.^_`|~"
B_RE = re.compile(r"[A-Za-z0-9'()+_,\-./:=? ]{0,69}[A-Za-z0-9'()+_,\-./:=?]\Z")


def o_boundary(b):
    if type(b) is not str or len(b) > 256:
        return None
    return B_RE.fullmatch(b) is not None


def test_boundary_ok_type_and_length_codes():
    for v in (5, None, b'a', 5.5, SStr('a')):
        refuse(m.boundary_ok, 'bad_type:boundary', v)
    refuse(m.boundary_ok, 'bad_value:boundary.length', 'a' * 257)
    assert m.boundary_ok('a' * 256) is False  # over the RFC 70-char grammar, under the input cap


def test_boundary_ok_is_exact_bool_and_grammar():
    assert m.boundary_ok('a') is True
    assert m.boundary_ok('A' * 70) is True
    assert m.boundary_ok('A' * 71) is False
    assert m.boundary_ok('') is False
    assert m.boundary_ok('a ') is False
    assert m.boundary_ok(' a') is True
    assert m.boundary_ok('a b') is True
    for ch in BCHARS:
        assert m.boundary_ok('x' + ch) is (ch != ' '), repr(ch)
        assert m.boundary_ok(ch + 'x') is True, repr(ch)
    for ch in '*;\\"\t\r\n\x00\x7f':
        assert m.boundary_ok('x' + ch) is False, repr(ch)


def test_boundary_ok_every_codepoint_and_lookalikes():
    for c in range(0x300):
        ch = chr(c)
        want = o_boundary('x' + ch)
        got = m.boundary_ok('x' + ch)
        assert got is want, (c, got, want)
    for ch in ('\u0660', '\u06f0', '\uff10', '\u1d7ce', '\u2102', '\u0131', '\u212a', '\u00e9'):
        assert m.boundary_ok('x' + ch) is False, repr(ch)
        assert m.boundary_ok(ch) is False, repr(ch)


def test_boundary_ok_agrees_with_oracle_randomized():
    rng = random.Random(66)
    al = BCHARS + '*;\\"\t\r\n\x00\x7f\u00e9\u0660Z0 ?'
    for _ in range(40000):
        n = rng.randint(0, 75)
        b = ''.join(rng.choice(al) for _ in range(n))
        got = m.boundary_ok(b)
        want = o_boundary(b)
        assert got is want, (b, got, want)


# ---------------------------------------------------------------- pct_encode_param / pct_decode_param

def o_enc(text):
    return urllib.parse.quote(text, safe="-._~", encoding='utf-8', errors='strict')


def test_pct_encode_type_length_and_surrogate():
    for v in (5, None, b'a', SStr('a')):
        refuse(m.pct_encode_param, 'bad_type:text', v)
    refuse(m.pct_encode_param, 'bad_value:text.length', 'a' * 256)
    assert m.pct_encode_param('a' * 255) == 'a' * 255
    refuse(m.pct_encode_param, 'bad_value:text.encode', '\ud800')
    refuse(m.pct_encode_param, 'bad_value:text.encode', 'a\udfff')
    assert m.pct_encode_param('') == ''


def test_pct_encode_matches_quote_everywhere():
    for c in range(0x300):
        ch = chr(c)
        assert m.pct_encode_param('x' + ch + 'y') == o_enc('x' + ch + 'y'), c
    rng = random.Random(67)
    al = UNRES + " !*'();:@&=+$,/?%#[]\u00e9\u4e2d\U0001f600"
    for _ in range(20000):
        s = ''.join(rng.choice(al) for _ in range(rng.randint(0, 12)))
        assert m.pct_encode_param(s) == o_enc(s), s
    for ch in UNRES:
        assert m.pct_encode_param(ch) == ch
    assert m.pct_encode_param('\x00') == '%00'
    assert m.pct_encode_param('\x7f') == '%7F'
    assert m.pct_encode_param(' ') == '%20'


def o_dec(value):
    if type(value) is not str or len(value) > 3072:
        return None
    out = bytearray()
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == '%':
            if i + 2 >= len(value) or value[i + 1] not in '0123456789abcdefABCDEF' \
                    or value[i + 2] not in '0123456789abcdefABCDEF':
                return 'pct'
            out.append(int(value[i + 1:i + 3], 16))
            i += 3
        elif ord(ch) < 32 or ord(ch) > 126:
            return 'chars'
        else:
            out.append(ord(ch))
            i += 1
    try:
        return bytes(out).decode('utf-8')
    except UnicodeDecodeError:
        return 'decode'


def test_pct_decode_type_length_and_codes():
    for v in (5, None, b'a', SStr('a')):
        refuse(m.pct_decode_param, 'bad_type:value', v)
    refuse(m.pct_decode_param, 'bad_value:value.length', 'a' * 3073)
    assert m.pct_decode_param('a' * 3072) == 'a' * 3072
    refuse(m.pct_decode_param, 'bad_value:value.pct', '%')
    refuse(m.pct_decode_param, 'bad_value:value.pct', '%4')
    refuse(m.pct_decode_param, 'bad_value:value.pct', '%4g')
    refuse(m.pct_decode_param, 'bad_value:value.pct', 'a%zz')
    refuse(m.pct_decode_param, 'bad_value:value.chars', 'a b\t')
    refuse(m.pct_decode_param, 'bad_value:value.chars', '\u00e9')
    refuse(m.pct_decode_param, 'bad_value:value.decode', '%80')
    refuse(m.pct_decode_param, 'bad_value:value.decode', '%C3')
    refuse(m.pct_decode_param, 'bad_value:value.decode', '%ff%FF')
    assert m.pct_decode_param('%C3%A9') == '\u00e9'
    assert m.pct_decode_param('%41%42') == 'AB'
    assert m.pct_decode_param('') == ''
    assert m.pct_decode_param('%25') == '%'


def test_pct_decode_agrees_with_oracle_randomized():
    rng = random.Random(68)
    al = list("ab%41%4%xyz091AZ \t\u00e9\x7f\x1f~%C3%A9%80%ff%GG")
    for _ in range(40000):
        s = ''.join(rng.choice(al) for _ in range(rng.randint(0, 14)))
        w = o_dec(s)
        if w in ('pct', 'chars', 'decode'):
            refuse(m.pct_decode_param, 'bad_value:value.' + w, s)
        else:
            assert m.pct_decode_param(s) == w, s


def test_pct_roundtrip_encode_then_decode_is_exact():
    rng = random.Random(69)
    al = UNRES + " !*'();:@&=+$,/?%#[]\u00e9\u4e2d\U0001f600"
    for _ in range(20000):
        s = ''.join(rng.choice(al) for _ in range(rng.randint(0, 12)))
        assert m.pct_decode_param(m.pct_encode_param(s)) == s, s


# ---------------------------------------------------------------- parse_form_data: framing

def mk(parts, bnd='AaB03x', pad=b'', epilogue=b'', preamble=b''):
    out = [preamble + b'--' + bnd.encode()]
    for head, data in parts:
        out.append(pad + b'\r\n' + head + b'\r\n\r\n' + data + b'\r\n--' + bnd.encode())
    out.append(b'--' + pad + epilogue)
    return b''.join(out)


CD = b'Content-Disposition: form-data; name="a"'


def test_parse_type_and_length_order():
    refuse(m.parse_form_data, 'bad_type:body', 'x', 'b')
    refuse(m.parse_form_data, 'bad_type:body', None, 'b')
    refuse(m.parse_form_data, 'bad_type:body', SBytes(b'x'), 'b')
    refuse(m.parse_form_data, 'bad_value:body.length', b'x' * 262145, 'b')
    refuse(m.parse_form_data, 'bad_type:boundary', b'x', 5)
    refuse(m.parse_form_data, 'bad_type:boundary', b'x', SStr('b'))
    refuse(m.parse_form_data, 'bad_value:boundary.length', b'x', 'a' * 257)
    refuse(m.parse_form_data, 'bad_value:boundary.syntax', b'x', '')
    refuse(m.parse_form_data, 'bad_value:boundary.syntax', b'x', 'a' * 71)
    refuse(m.parse_form_data, 'bad_value:boundary.syntax', b'x', 'a ')
    refuse(m.parse_form_data, 'bad_value:boundary.syntax', b'x', 'a;b')


def test_parse_framing_codes():
    refuse(m.parse_form_data, 'bad_value:body.start', b'', 'b')
    refuse(m.parse_form_data, 'bad_value:body.start', b'--c\r\n--c--\r\n', 'b')
    refuse(m.parse_form_data, 'bad_value:body.unterminated', b'--b\r\n' + CD + b'\r\n\r\nx', 'b')
    refuse(m.parse_form_data, 'bad_value:body.empty', b'--b--\r\n', 'b')
    refuse(m.parse_form_data, 'bad_value:body.delimiter', b'--b\rX' + CD, 'b')
    refuse(m.parse_form_data, 'bad_value:body.delimiter', b'--bZ\r\n' + CD + b'\r\n\r\nx\r\n--b--\r\n', 'b')
    refuse(m.parse_form_data, 'bad_value:body.close', b'--b\r\n' + CD + b'\r\n\r\nx\r\n--b--Z', 'b')
    refuse(m.parse_form_data, 'bad_value:body.close', b'--b\r\n' + CD + b'\r\n\r\nx\r\n--b--x\r\n', 'b')


def test_parse_minimal_and_padding_and_epilogue():
    body = b'--b\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n'
    assert m.parse_form_data(body, 'b') == (('a', None, None, b'hi'),)
    body2 = b'--b \t\r\n' + CD + b'\r\n\r\nhi\r\n--b-- \t \r\nTRAILER IGNORED'
    assert m.parse_form_data(body2, 'b') == (('a', None, None, b'hi'),)
    body3 = b'PREAMBLE\r\n--b\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n'
    assert m.parse_form_data(body3, 'b') == (('a', None, None, b'hi'),)
    body4 = b'--b\r\n' + CD + b'\r\n\r\nhi\r\n--b--'
    assert m.parse_form_data(body4, 'b') == (('a', None, None, b'hi'),)
    refuse(m.parse_form_data, 'bad_value:body.empty',
           b'junk--b\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n', 'b')  # junk prefix: no delimiter before close
    assert m.parse_form_data(b'junk\r\n--b\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n', 'b') == (('a', None, None, b'hi'),)


def test_parse_data_passes_through_bytes_and_fake_delims():
    data = bytes(range(256)) * 3
    body = b'--b\r\n' + CD + b'\r\n\r\n' + data + b'\r\n--b--\r\n'
    assert m.parse_form_data(body, 'b') == (('a', None, None, data),)
    body = b'--b\r\n' + CD + b'\r\n\r\nx--b\r\ny--b--\r\nz\r\n--b--\r\n'
    got = m.parse_form_data(body, 'b')
    assert got == (('a', None, None, b'x--b\r\ny--b--\r\nz'),), got
    body = b'--b\r\n' + CD + b'\r\n\r\n\r\n\r\n--b--\r\n'
    assert m.parse_form_data(body, 'b') == (('a', None, None, b'\r\n'),)
    body = b'--b\r\n' + CD + b'\r\n\r\n\r\n--b--\r\n'
    assert m.parse_form_data(body, 'b') == (('a', None, None, b''),)


def test_parse_multiple_parts_and_cap():
    parts = [(b'Content-Disposition: form-data; name="p%d"' % i, b'd%d' % i) for i in range(3)]
    got = m.parse_form_data(mk(parts), 'AaB03x')
    assert got == tuple(('p%d' % i, None, None, b'd%d' % i) for i in range(3))
    parts = [(b'Content-Disposition: form-data; name="p%d"' % i, b'') for i in range(64)]
    assert len(m.parse_form_data(mk(parts), 'AaB03x')) == 64
    parts = [(b'Content-Disposition: form-data; name="p%d"' % i, b'') for i in range(65)]
    refuse(m.parse_form_data, 'bad_value:body.parts', mk(parts), 'AaB03x')


# ---------------------------------------------------------------- parse_form_data: part headers

def one(head, data=b'x', bnd='b'):
    return b'--' + bnd.encode() + b'\r\n' + head + b'\r\n\r\n' + data + b'\r\n--' + bnd.encode() + b'--\r\n'


def test_parse_header_count_length_fold_chars_syntax():
    heads = b'\r\n'.join(b'X-H%d: v' % i for i in range(7)) + b'\r\n' + CD
    assert m.parse_form_data(one(heads), 'b')[0][0] == 'a'
    heads = b'\r\n'.join(b'X-H%d: v' % i for i in range(8)) + b'\r\n' + CD
    refuse(m.parse_form_data, 'bad_value:part.header.count', one(heads), 'b')
    refuse(m.parse_form_data, 'bad_value:part.header.length', one(b'X: ' + b'v' * 8190 + b'\r\n' + CD), 'b')
    assert m.parse_form_data(one(b'X: ' + b'v' * 8189 + b'\r\n' + CD), 'b')[0][0] == 'a'
    assert m.parse_form_data(b'--b\r\n' + CD + b'\r\n--b--\r\n', 'b') == (('a', None, None, b''),)
    refuse(m.parse_form_data, 'bad_value:part.header.fold', one(b' Content-Disposition: form-data; name="a"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.header.fold', one(b'X: a\r\n\tb\r\n' + CD), 'b')
    refuse(m.parse_form_data, 'bad_value:part.header.chars', one(b'X: \x7f\r\n' + CD), 'b')
    refuse(m.parse_form_data, 'bad_value:part.header.chars', one(b'X: \x80\r\n' + CD), 'b')
    refuse(m.parse_form_data, 'bad_value:part.header.chars', one(b'X: a\x01\r\n' + CD), 'b')
    assert m.parse_form_data(one(b'X: a\tb\r\n' + CD), 'b')[0][0] == 'a'
    refuse(m.parse_form_data, 'bad_value:part.header.syntax', one(b'noColon\r\n' + CD), 'b')
    refuse(m.parse_form_data, 'bad_value:part.header.syntax', one(b': v\r\n' + CD), 'b')
    refuse(m.parse_form_data, 'bad_value:part.header.syntax', one(b'X Y: v\r\n' + CD), 'b')
    refuse(m.parse_form_data, 'bad_value:part.header.syntax', one(b'X@Y: v\r\n' + CD), 'b')
    assert m.parse_form_data(one(b'X-any_Header: v\r\n' + CD), 'b')[0][0] == 'a'


def test_parse_header_bytes_sweep():
    for b in range(256):
        line = b'X: a' + bytes([b]) + b'\r\n' + CD
        if b in (9,) or 32 <= b <= 126:
            assert m.parse_form_data(one(line), 'b')[0][0] == 'a', b
        else:
            refuse(m.parse_form_data, 'bad_value:part.header.chars', one(line), 'b')


def test_parse_unknown_headers_ignored_incl_cte():
    head = b'Content-Transfer-Encoding: base64\r\nX-Other: z\r\n' + CD
    assert m.parse_form_data(one(head), 'b') == (('a', None, None, b'x'),)
    head = b'content-DISPOSITION: form-data; name="a"'
    assert m.parse_form_data(one(head), 'b') == (('a', None, None, b'x'),)


def test_parse_disposition_codes():
    refuse(m.parse_form_data, 'bad_value:part.disposition.missing', one(b'X: v'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.missing', b'--b\r\n\r\n\r\nx\r\n--b--\r\n', 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.missing', b'--b\r\n\r\nx\r\n--b--\r\n', 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.duplicate', one(CD + b'\r\n' + CD), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: '), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: for m-data; name="a"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: form-data; name=a'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: form-data; name="a'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: form-data; name'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: form-data; ="a"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: form-data; name="a" x'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: form-data; name="a"; '), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: form-data; name="a"b'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: form-data; name="a\tb"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: form-data; name="a\\nb"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.type', one(b'Content-Disposition: attachment; name="a"'), 'b')
    assert m.parse_form_data(one(b'Content-Disposition: FORM-data; name="a"'), 'b')[0][0] == 'a'
    assert m.parse_form_data(one(b'Content-Disposition: form-data  ; name="a"'), 'b')[0][0] == 'a'
    refuse(m.parse_form_data, 'bad_value:part.disposition.filename_star', one(b'Content-Disposition: form-data; name="a"; filename*=\"x\"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.filename_star', one(b'Content-Disposition: form-data; FILENAME*="x"; name="a"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.param', one(b'Content-Disposition: form-data; name="a"; x="1"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.param', one(b'Content-Disposition: form-data; name="a"; name="b"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.param', one(b'Content-Disposition: form-data; filename="a"; filename="b"; name="c"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.name', one(b'Content-Disposition: form-data; filename="a"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.name', one(b'Content-Disposition: form-data'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.length', one(b'Content-Disposition: form-data; name="' + b'v' * 3073 + b'"'), 'b')
    assert m.parse_form_data(one(b'Content-Disposition: form-data; name="' + b'v' * 3072 + b'"'), 'b')[0][0] == 'v' * 3072


def test_parse_disposition_whitespace_and_values():
    got = m.parse_form_data(one(b'Content-Disposition: form-data; name = "a" ; filename = "f.txt"'), 'b')
    assert got == (('a', 'f.txt', None, b'x'),), got
    got = m.parse_form_data(one(b'Content-Disposition: form-data; name="a b"; filename="x%20y.txt"'), 'b')
    assert got == (('a b', 'x%20y.txt', None, b'x'),), got
    got = m.parse_form_data(one(b'Content-Disposition: form-data; NAME="a"'), 'b')
    assert got == (('a', None, None, b'x'),), got
    got = m.parse_form_data(one(b'Content-Disposition: form-data; name=""'), 'b')
    assert got == (('', None, None, b'x'),), got


def test_parse_content_type_codes():
    got = m.parse_form_data(one(CD + b'\r\nContent-Type: text/plain'), 'b')
    assert got == (('a', None, 'text/plain', b'x'),), got
    got = m.parse_form_data(one(CD + b'\r\ncontent-type: application/json; charset=utf-8'), 'b')
    assert got == (('a', None, 'application/json; charset=utf-8', b'x'),), got
    refuse(m.parse_form_data, 'bad_value:part.content_type.duplicate', one(CD + b'\r\nContent-Type: a/b\r\nContent-Type: a/b'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.content_type.syntax', one(CD + b'\r\nContent-Type: '), 'b')
    refuse(m.parse_form_data, 'bad_value:part.content_type.syntax', one(CD + b'\r\nContent-Type: text'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.content_type.syntax', one(CD + b'\r\nContent-Type: /plain'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.content_type.syntax', one(CD + b'\r\nContent-Type: text/'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.content_type.syntax', one(CD + b'\r\nContent-Type: te xt/plain'), 'b')
    # trailing ws is stripped at the header level, so this one is accepted
    assert m.parse_form_data(one(CD + b'\r\nContent-Type: text/plain; charset=utf-8 '), 'b')[0][2] == 'text/plain; charset=utf-8'
    refuse(m.parse_form_data, 'bad_value:part.content_type.syntax', one(CD + b'\r\nContent-Type: text/plain x'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.content_type.syntax', one(CD + b'\r\nContent-Type: ' + b'a/b' + b'v' * 260), 'b')
    assert m.parse_form_data(one(CD + b'\r\nContent-Type: text/plain; charset="utf 8"'), 'b')[0][2] == 'text/plain; charset="utf 8"'
    assert m.parse_form_data(one(CD + b'\r\nContent-Type: text/plain ; charset=utf-8'), 'b')[0][2] == 'text/plain ; charset=utf-8'


# ---------------------------------------------------------------- serialize_form_data

def test_serialize_type_and_part_shape_codes():
    for v in (5, None, 'x', b'x', SList([]), {'a': 1}):
        refuse(m.serialize_form_data, 'bad_type:parts', v, 'b')
    refuse(m.serialize_form_data, 'bad_value:parts.length', [], 'b')
    refuse(m.serialize_form_data, 'bad_value:parts.length', (), 'b')
    refuse(m.serialize_form_data, 'bad_value:parts.length', [('a', None, None, b'x')] * 65, 'b')
    refuse(m.serialize_form_data, 'bad_type:part', ['a'], 'b')
    refuse(m.serialize_form_data, 'bad_type:part', [('a', None, None)], 'b')
    refuse(m.serialize_form_data, 'bad_type:part', [('a', None, None, b'x', 1)], 'b')
    refuse(m.serialize_form_data, 'bad_type:part', [STuple(('a', None, None, b'x'))], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.name', [(5, None, None, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.name', [(SStr('a'), None, None, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.name.length', [('a' * 256, None, None, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.filename', [('a', 5, None, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.filename.length', [('a', 'f' * 256, None, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.content_type', [('a', None, 5, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.content_type.length', [('a', None, 'a/b' + 'c' * 300, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.data', [('a', None, None, 'x')], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.data', [('a', None, None, SBytes(b'x'))], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.data.length', [('a', None, None, b'x' * 262145)], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.name.encode', [('\ud800', None, None, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.filename.encode', [('a', '\udfff', None, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, 'text', b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, 'text/plain ', b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_type:boundary', [('a', None, None, b'x')], 5)
    refuse(m.serialize_form_data, 'bad_value:boundary.syntax', [('a', None, None, b'x')], 'a;')
    refuse(m.serialize_form_data, 'bad_value:body.delimiter', [('a', None, None, b'x\r\n--b')], 'b')
    refuse(m.serialize_form_data, 'bad_value:body.delimiter', [('a', None, None, b'\r\n--bZ')], 'b')
    assert m.serialize_form_data([('a', None, None, b'x--b\r\ny')], 'b')


def test_serialize_body_length_running_total():
    base = len(b'--b\r\nContent-Disposition: form-data; name="a"\r\n\r\n') + len(b'\r\n--b--\r\n')
    room = 262144 - base
    assert len(m.serialize_form_data([('a', None, None, b'x' * room)], 'b')) == 262144
    refuse(m.serialize_form_data, 'bad_value:body.length', [('a', None, None, b'x' * (room + 1))], 'b')
    half = (262144 - base - (len(b'--b\r\nContent-Disposition: form-data; name="c"\r\n\r\n') + 2)) // 1
    d1 = b'x' * 100000
    d2 = b'x' * 100000
    d3 = b'x' * 100000
    refuse(m.serialize_form_data, 'bad_value:body.length', [('a', None, None, d1), ('c', None, None, d2), ('e', None, None, d3)], 'b')


def test_serialize_output_shape_and_encoding():
    out = m.serialize_form_data([('a', None, None, b'hi'), ('f\u00e9', 'x y.txt', 'text/plain', b'')], 'AaB03x')
    want = (b'--AaB03x\r\nContent-Disposition: form-data; name="a"\r\n\r\nhi\r\n'
            b'--AaB03x\r\nContent-Disposition: form-data; name="f%C3%A9"; filename="x%20y.txt"\r\n'
            b'Content-Type: text/plain\r\n\r\n\r\n--AaB03x--\r\n')
    assert out == want
    assert out.startswith(b'--AaB03x\r\n') and out.endswith(b'--AaB03x--\r\n')
    out = m.serialize_form_data((('n', None, None, b''),), 'b')
    assert out == b'--b\r\nContent-Disposition: form-data; name="n"\r\n\r\n\r\n--b--\r\n'
    out = m.serialize_form_data([('a"b', None, None, b'x')], 'b')
    assert b'name="a%22b"' in out
    out = m.serialize_form_data([('a', 'f', 'application/octet-stream', bytes(range(256)))], 'b')
    assert out.endswith(bytes(range(256)) + b'\r\n--b--\r\n')


def test_serialize_then_parse_roundtrip_unreserved_exact():
    rng = random.Random(70)
    for _ in range(4000):
        n = rng.randint(1, 4)
        parts = []
        for _ in range(n):
            name = ''.join(rng.choice(UNRES) for _ in range(rng.randint(0, 12)))
            fn = None if rng.random() < 0.5 else ''.join(rng.choice(UNRES) for _ in range(rng.randint(0, 8)))
            ct = None if rng.random() < 0.5 else rng.choice(['text/plain', 'application/json', 'a/b; x=y'])
            data = bytes(rng.randint(0, 255) for _ in range(rng.randint(0, 40)))
            if (b'\r\n' + data).find(b'\r\n--BB') >= 0:
                continue
            parts.append((name, fn, ct, data))
        if not parts:
            continue
        out = m.serialize_form_data(parts, 'BB')
        assert m.parse_form_data(out, 'BB') == tuple(parts)


def test_serialize_then_parse_roundtrip_encoded_names():
    parts = [('a b', 'f \u00e9.txt', 'text/plain', b'x'), ('\u4e2d\u6587', None, None, b'y')]
    out = m.serialize_form_data(parts, 'BB')
    got = m.parse_form_data(out, 'BB')
    want = (('a%20b', 'f%20%C3%A9.txt', 'text/plain', b'x'), ('%E4%B8%AD%E6%96%87', None, None, b'y'))
    assert got == want, got
    for name, fn, ct, data in got:
        assert m.pct_decode_param(name) is not None
    assert [m.pct_decode_param(g[0]) for g in got] == ['a b', '\u4e2d\u6587']
    assert m.pct_decode_param(got[0][1]) == 'f \u00e9.txt'


# ---------------------------------------------------------------- refusal ORDER pins (both-bad witnesses)

def test_parse_order_pins_both_bad():
    refuse(m.parse_form_data, 'bad_type:body', 'x', '')                    # body.type before boundary
    refuse(m.parse_form_data, 'bad_value:body.length', b'x' * 262145, '')  # body.length before boundary
    refuse(m.parse_form_data, 'bad_type:boundary', b'', 5)                 # boundary.type before its length/syntax
    refuse(m.parse_form_data, 'bad_value:boundary.length', b'', 'a' * 257) # length before syntax
    refuse(m.parse_form_data, 'bad_value:boundary.syntax', b'', '')        # syntax before framing
    refuse(m.parse_form_data, 'bad_value:body.start', b'ZZ', 'b')
    body = b'--b\r\nX: v\r\n\r\nx'  # unterminated AND header too short to matter: framing first
    refuse(m.parse_form_data, 'bad_value:body.unterminated', body, 'b')
    body = b'--b\r\nContent-Disposition: attachment; name="a"\r\nX: v\r\n\r\nx\r\n--b--Z'
    refuse(m.parse_form_data, 'bad_value:body.close', body, 'b')           # close checked in framing pass


def test_part_order_pins_both_bad():
    # header.chars is checked before header.syntax on the same line
    refuse(m.parse_form_data, 'bad_value:part.header.chars', one(b'X Y: \x80\r\n' + CD), 'b')
    # header.length before header.chars
    refuse(m.parse_form_data, 'bad_value:part.header.length', one(b'X: \x80' + b'v' * 8190 + b'\r\n' + CD), 'b')
    # header.count before any per-line check
    heads = b'\r\n'.join(b'X-H%d: \x80' % i for i in range(8)) + b'\r\n' + CD
    refuse(m.parse_form_data, 'bad_value:part.header.count', one(heads), 'b')
    # header.fold before header.chars
    refuse(m.parse_form_data, 'bad_value:part.header.fold', one(b' \x80\r\n' + CD), 'b')
    # disposition.duplicate (second CD header) beats content of the second CD
    refuse(m.parse_form_data, 'bad_value:part.disposition.duplicate',
           one(CD + b'\r\nContent-Disposition: attachment; name="b"'), 'b')
    # disposition.syntax before disposition.type
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(b'Content-Disposition: att achment; name="a"'), 'b')
    # filename_star before disposition.length and disposition.param
    big = b'v' * 3073
    refuse(m.parse_form_data, 'bad_value:part.disposition.filename_star',
           one(b'Content-Disposition: form-data; name="a"; filename*="' + big + b'"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.filename_star',
           one(b'Content-Disposition: form-data; name="a"; filename*="x"; x="1"'), 'b')
    # disposition.length before disposition.param (unknown key with oversized value)
    refuse(m.parse_form_data, 'bad_value:part.disposition.length',
           one(b'Content-Disposition: form-data; name="a"; x="' + big + b'"'), 'b')
    # content_type.duplicate before content_type.syntax of the second
    refuse(m.parse_form_data, 'bad_value:part.content_type.duplicate',
           one(CD + b'\r\nContent-Type: a/b\r\nContent-Type: bad'), 'b')
    # disposition.missing after all header-level checks
    refuse(m.parse_form_data, 'bad_value:part.header.syntax', one(b'noColon'), 'b')


def test_serialize_order_pins_both_bad():
    refuse(m.serialize_form_data, 'bad_type:parts', 'x', '')               # parts.type first
    refuse(m.serialize_form_data, 'bad_value:parts.length', [], '')        # parts.length before boundary
    refuse(m.serialize_form_data, 'bad_type:boundary', [('a', None, None, 5)], 5)
    refuse(m.serialize_form_data, 'bad_value:boundary.syntax', [5], 'a;')  # boundary before part checks
    refuse(m.serialize_form_data, 'bad_type:part', [5], 'b')
    refuse(m.serialize_form_data, 'bad_type:part', [('a', None, None)], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.name', [(5, 5, 5, 5)], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.filename', [('a', 5, 5, 5)], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.content_type', [('a', None, 5, 5)], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.data', [('a', None, None, 5)], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.name.length', [('a' * 256, 'f' * 256, None, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.name.encode', [('\ud800', '\ud800', None, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.filename.encode', [('a', '\ud800', 'text', b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, 'bad', b'\r\n--b')], 'b')
    refuse(m.serialize_form_data, 'bad_value:body.delimiter', [('a', None, None, b'\r\n--b'), ('c', None, None, b'x' * 262144)], 'b')


# ---------------------------------------------------------------- no-import pins on success and refusal paths

def test_no_imports_during_operation():
    calls = []
    real = builtins.__import__

    def spy(name, *a, **k):
        calls.append(name)
        return real(name, *a, **k)

    body = b'--b\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n'
    try:
        builtins.__import__ = spy
        assert m.boundary_ok('Bb') is True
        assert m.pct_encode_param('a b') == 'a%20b'
        assert m.pct_decode_param('a%20b') == 'a b'
        assert m.parse_form_data(body, 'b') == (('a', None, None, b'hi'),)
        assert m.serialize_form_data([('a', None, None, b'hi')], 'b')
        for fn, args in ((m.parse_form_data, ('x', 'b')), (m.boundary_ok, (5,)),
                         (m.serialize_form_data, ([], 'b')), (m.pct_decode_param, ('%',))):
            try:
                fn(*args)
            except ValueError:
                pass
    finally:
        builtins.__import__ = real
    assert calls == []


# ---------------------------------------------------------------- registry worlds

def purge():
    sys.modules.pop(MODNAME, None)


def test_world_registry_present():
    purge()
    mod = importlib.import_module(MODNAME)
    try:
        assert mod.parse_form_data(b'--b\r\n' + CD + b'\r\n\r\nx\r\n--b--\r\n', 'b') == (('a', None, None, b'x'),)
        try:
            mod.boundary_ok(5)
        except ValueError as e:
            assert str(e) == 'P235:boundary_ok:bad_type:boundary'
    finally:
        purge()


def mk_tree(tmp_path, registry_src=None):
    doc = tmp_path / 'app' / 'modules' / 'instinct_doc'
    doc.mkdir(parents=True)
    for d in (tmp_path / 'app', tmp_path / 'app' / 'modules', doc):
        (d / '__init__.py').write_text('')
    (doc / 'p235_concepts_batch1066_formdata.py').write_text(pathlib.Path(m.__file__).read_text())
    if registry_src is not None:
        (doc / 'p235_concepts_registry.py').write_text(registry_src)
    return tmp_path


def drop_app_modules():
    dropped = {k: v for k, v in sys.modules.items()
               if type(k) is str and (k == 'app' or k.startswith('app.'))}
    for k in dropped:
        sys.modules.pop(k, None)
    return dropped


def test_world_registry_absent_uses_fallback(tmp_path):
    root = mk_tree(tmp_path, registry_src=None)
    sys.path.insert(0, str(root))
    try:
        dropped = drop_app_modules()
        mod = importlib.import_module(MODNAME)
        try:
            try:
                mod.make_fail('x')('c')
            except ValueError as e:
                assert str(e) == 'P235:x:c'
            assert mod.boundary_ok('Bb') is True
            try:
                mod.boundary_ok(5)
            except ValueError as e:
                assert str(e) == 'P235:boundary_ok:bad_type:boundary'
            body = b'--b\r\n' + CD + b'\r\n\r\nx\r\n--b--\r\n'
            assert mod.parse_form_data(body, 'b') == (('a', None, None, b'x'),)
        finally:
            purge()
    finally:
        sys.path.remove(str(root))
        drop_app_modules()
        sys.modules.update(dropped)


def test_world_registry_foreign_missing_dep_reraises(tmp_path):
    root = mk_tree(tmp_path, registry_src='import nonexistent_dep_xyz_1066\nmake_fail = None\n')
    sys.path.insert(0, str(root))
    try:
        dropped = drop_app_modules()
        try:
            importlib.import_module(MODNAME)
            raise AssertionError('expected ModuleNotFoundError')
        except ModuleNotFoundError as e:
            assert e.name == 'nonexistent_dep_xyz_1066'
    finally:
        sys.path.remove(str(root))
        drop_app_modules()
        sys.modules.update(dropped)


def test_world_registry_broken_self_ref_reraises(tmp_path):
    root = mk_tree(tmp_path, registry_src='raise ModuleNotFoundError(name=%r)\n' % REG)
    sys.path.insert(0, str(root))
    try:
        dropped = drop_app_modules()
        try:
            importlib.import_module(MODNAME)
            raise AssertionError('expected ModuleNotFoundError')
        except ModuleNotFoundError as e:
            assert e.name == REG
    finally:
        sys.path.remove(str(root))
        drop_app_modules()
        sys.modules.update(dropped)


def test_world_registry_present_imports_exactly_once(tmp_path):
    log = []
    real = builtins.__import__

    def spy(name, *a, **k):
        if 'registry' in name or name == 'importlib.util':
            log.append(name)
        return real(name, *a, **k)

    root = mk_tree(tmp_path, registry_src='def make_fail(name):\n    def fail(code):\n        raise ValueError("Zq9:%s:%s" % (name, code))\n    return fail\n')
    sys.path.insert(0, str(root))
    try:
        dropped = drop_app_modules()
        try:
            builtins.__import__ = spy
            mod = importlib.import_module(MODNAME)
        finally:
            builtins.__import__ = real
        assert log.count(REG) == 1
        assert 'importlib.util' not in log
        try:
            mod.boundary_ok(5)
        except ValueError as e:
            assert str(e) == 'Zq9:boundary_ok:bad_type:boundary'
    finally:
        sys.path.remove(str(root))
        drop_app_modules()
        sys.modules.update(dropped)


# ---------------------------------------------------------------- tracemalloc cap-before-work pins

def test_caps_refuse_before_proportional_work():
    big = 'q' * 200000 + ';'
    bigb = b'x' * 262145
    bigp = [('a', None, None, b'x')] * 65
    tracemalloc.start()
    try:
        refuse(m.boundary_ok, 'bad_value:boundary.length', big)
        cur, peak = tracemalloc.get_traced_memory()
        assert peak < 100000, peak
        tracemalloc.reset_peak()
        refuse(m.parse_form_data, 'bad_value:body.length', bigb, 'b')
        cur, peak = tracemalloc.get_traced_memory()
        assert peak < 100000, peak
        tracemalloc.reset_peak()
        refuse(m.serialize_form_data, 'bad_value:parts.length', bigp, 'b')
        cur, peak = tracemalloc.get_traced_memory()
        assert peak < 100000, peak
    finally:
        tracemalloc.stop()


# ---------------------------------------------------------------- quoted RFC text vs live documents

RFC_ENV = 'P235_RFC1066_TXT'
ERR_ENV = 'P235_ERRATA_JSON'


def test_rfc_quotes_match_live_documents():
    path = os.environ.get(RFC_ENV)
    if not path:
        pytest.skip(RFC_ENV + ' not set')
    raw = open(path, encoding='utf-8').read()
    lines = [l for l in raw.split('\n') if not re.match(r'^\s*(RFC \d+|\f|.*\[(Page|page) \d+\])\s*$', l)]
    t = re.sub(r'-\n(\w)', r'\1', '\n'.join(lines))
    t = re.sub(r'\s+', ' ', t)
    qs = re.findall(r'^Q(\d+)\| (.*)$', m.__doc__, re.M)
    assert [n for n, _ in qs] == [str(i) for i in range(1, 14)]
    for n, q in qs:
        assert q in t, n


def test_errata_block_names_every_live_record():
    path = os.environ.get(ERR_ENV)
    if not path:
        pytest.skip(ERR_ENV + ' not set')
    data = json.load(open(path))
    want = [e for e in data if e.get('doc-id') in ('RFC7578', 'RFC2046')]
    assert len(want) == 18
    doc = m.__doc__
    assert doc.count('EID ') == 18
    for e in want:
        st = e['errata_status_code'] + ' ' + e['errata_type_code']
        sec = e.get('section', '').rstrip().rstrip(':').rstrip('.')
        if sec.endswith(' states'):
            sec = sec[:-7]
        assert 'EID %s %s section %s' % (e['errata_id'], st, sec) in doc, e['errata_id']
    assert 'RFC 7578' in doc and 'RFC 2046' in doc
    for eid in (4676, 5616, 7385, 9032, 507, 508, 509, 510, 511, 588, 589, 6582, 6800, 7341, 8667, 4609, 6583, 6776):
        assert 'EID %d ' % eid in doc


# ---------------------------------------------------------------- vac guard

def test_all_refusal_assertions_were_checked_above():
    assert callable(m.parse_form_data) and callable(m.serialize_form_data)
    src = pathlib.Path(__file__).read_text()
    assert src.count('refuse(m.parse_form_data') > 40
    assert src.count('refuse(m.serialize_form_data') > 20
    assert src.count('or Tr' + 'ue') == 0


def test_serialize_delimiter_at_data_start_refused():
    # differential finding: data beginning with the boundary bytes right after the
    # header CRLF creates an ambiguous delimiter position (find() == 0)
    refuse(m.serialize_form_data, 'bad_value:body.delimiter', [('a', None, None, b'--b')], 'b')
    refuse(m.serialize_form_data, 'bad_value:body.delimiter', [('a', None, None, b'--bxyz')], 'b')
    refuse(m.serialize_form_data, 'bad_value:body.delimiter', [('a', None, None, b'--b--')], 'b')
    refuse(m.serialize_form_data, 'bad_value:body.delimiter', [('a', None, None, b'--b\r\nz')], 'b')
    assert m.serialize_form_data([('a', None, None, b'a--b')], 'b')  # interior, not after CRLF: fine


def test_parse_tab_whitespace_in_disposition_and_headers():
    got = m.parse_form_data(one(b'Content-Disposition: form-data;\tname\t=\t"a"\t; filename="f"'), 'b')
    assert got == (('a', 'f', None, b'x'),), got
    got = m.parse_form_data(one(b'Content-Disposition: form-data; name="a"\t'), 'b')
    assert got == (('a', None, None, b'x'),), got
    got = m.parse_form_data(one(CD + b'\r\nContent-Type:\ttext/plain\t'), 'b')
    assert got == (('a', None, 'text/plain', b'x'),), got
    got = m.parse_form_data(one(b'X:\tv\t\r\n' + CD), 'b')
    assert got == (('a', None, None, b'x'),), got
    refuse(m.parse_form_data, 'bad_value:part.content_type.syntax',
           one(CD + b'\r\nContent-Type: text/plain;\tcharset=utf-8'), 'b')  # tab inside params: only 32..126


def test_serialize_and_decode_control_chars_refused():
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, 'a/b; x=\x1fy', b'v')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, 'a/b; x=\x7fy', b'v')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, 'a/b;\tx=y', b'v')], 'b')
    refuse(m.parse_form_data, 'bad_value:part.header.chars', one(CD + b'\r\nContent-Type: a/b; x=\x1fy'), 'b')  # line-level check first
    refuse(m.pct_decode_param, 'bad_value:value.chars', '\x1f')
    refuse(m.pct_decode_param, 'bad_value:value.chars', '\x7f')
    assert m.pct_decode_param('~ ok') == '~ ok'


def test_parse_disposition_junk_before_quote_refused():
    # 1559-survivor witness: ws-skip after '=' must not absorb token chars
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax',
           one(b'Content-Disposition: form-data; name= x"a"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax',
           one(b'Content-Disposition: form-data; name=x"a"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax',
           one(b'Content-Disposition: form-data; name=xx"a"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax',
           one(b'Content-Disposition: form-data; name= \t x"a"'), 'b')


def test_serialize_ct_params_trailing_space_refused():
    # 1917-survivor witness: the trailing-ws check is on the LAST char of rest
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, 'a/b; x=y ', b'v')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, 'text/plain; charset=utf-8 ', b'v')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, 'a/b; x=y\t', b'v')], 'b')
    assert m.serialize_form_data([('a', None, 'a/b; x=y', b'v')], 'b')


def test_serialize_body_total_exact_arithmetic():
    # 2190-survivor witnesses: len(dash)+2 (=6) and len(hb) (=42) share bits;
    # | or ^ give 46 where + gives 48, shifting the 262144 boundary by 2
    hb_len = len('Content-Disposition: form-data; name="abc"')
    assert hb_len == 42
    base = 4 + 4 + 4 + 2 + 42 + 4 + 2  # close frame + one part frame
    room = 262144 - base
    assert len(m.serialize_form_data([('abc', None, None, b'x' * room)], 'bb')) == 262144
    refuse(m.serialize_form_data, 'bad_value:body.length', [('abc', None, None, b'x' * (room + 1))], 'bb')
    refuse(m.serialize_form_data, 'bad_value:body.length', [('abc', None, None, b'x' * (room + 2))], 'bb')


def test_parse_header_value_without_space_after_colon():
    # 2541-survivor witness: hvalue slice starts right after the colon
    got = m.parse_form_data(one(b'Content-Disposition:form-data; name="a"'), 'b')
    assert got == (('a', None, None, b'x'),), got
    got = m.parse_form_data(one(b'X:v\r\n' + CD), 'b')
    assert got == (('a', None, None, b'x'),), got
    got = m.parse_form_data(one(CD + b'\r\nContent-Type:text/plain'), 'b')
    assert got == (('a', None, 'text/plain', b'x'),), got


def test_parse_empty_segment_and_disp_junk_positions():
    refuse(m.parse_form_data, 'bad_value:part.disposition.missing', b'--b\r\n\r\n--b--\r\n', 'b')
    for h in (b'Content-Disposition: form-data; name x="a"',
              b'Content-Disposition: form-data; name x"a"',
              b'Content-Disposition: form-data; name "a"',
              b'Content-Disposition: form-data; name= x',
              b'Content-Disposition: form-data; name="a" junk',
              b'Content-Disposition: form-data; name'):
        refuse(m.parse_form_data, 'bad_value:part.disposition.syntax', one(h), 'b')


def test_ct_exactly_at_cap_and_control_chars():
    good = 'a/' + 'b' * 253  # exactly 255 chars, valid token/token
    assert len(good) == 255
    out = m.serialize_form_data([('a', None, good, b'v')], 'b')
    assert m.parse_form_data(one(CD + b'\r\nContent-Type: ' + good.encode()), 'b')[0][2] == good
    refuse(m.serialize_form_data, 'bad_value:part.content_type.length', [('a', None, good + 'c', b'v')], 'b')
    assert len(good + 'c') == 256


def test_parse_body_exactly_at_cap_and_serialize_data_at_cap():
    data = b'y' * (262144 - len(b'--b\r\n' + CD + b'\r\n\r\n\r\n--b--\r\n'))
    body = b'--b\r\n' + CD + b'\r\n\r\n' + data + b'\r\n--b--\r\n'
    assert len(body) == 262144
    assert m.parse_form_data(body, 'b') == (('a', None, None, data),)
    refuse(m.parse_form_data, 'bad_value:body.length', body + b'Z', 'b')
    # data at exactly the per-part data cap: accepted by the type/length checks,
    # then refused by the running body-total check
    refuse(m.serialize_form_data, 'bad_value:body.length', [('a', None, None, b'x' * 262144)], 'b')


def test_parse_disposition_quote_and_semicolon_checks():
    # 341-survivor witness: opening-quote check must reject junk before the quote
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax',
           one(b'Content-Disposition: form-data; name=x"; filename="f"'), 'b')
    # 349-survivor witness: params must be semicolon-separated
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax',
           one(b'Content-Disposition: form-data; name="a" filename="f"'), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax',
           one(b'Content-Disposition: form-data; name="a" x="1"'), 'b')


def test_ct_empty_subtype_and_rest_lstrip_edges():
    # 560-survivor witness: empty subtype refused regardless of '/' position
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, 'x/', b'v')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, '/', b'v')], 'b')
    # 572-survivor witnesses: rest after subtype starts at the first non-token char
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, 'text/plain x;y', b'v')], 'b')
    assert m.serialize_form_data([('a', None, 'text/plain\t;x', b'v')], 'b')
    assert m.serialize_form_data([('a', None, 'text/plain ;x', b'v')], 'b')


def test_parse_disposition_type_rstrip_and_param_spacing():
    # 590-survivor witnesses: type rstrip covers space+tab only, junk stays
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax',
           one(b'Content-Disposition: form-data x; name="a"'), 'b')
    got = m.parse_form_data(one(b'Content-Disposition: form-data\t; name="a"'), 'b')
    assert got == (('a', None, None, b'x'),), got
    # 609-survivor witness: semicolon without space is valid separation
    got = m.parse_form_data(one(b'Content-Disposition: form-data; name="a";filename="f"'), 'b')
    assert got == (('a', 'f', None, b'x'),), got
    # 627/629-survivor witnesses: dangling '=' at end is a clean syntax refusal
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax',
           one(b'Content-Disposition: form-data; name='), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax',
           one(b'Content-Disposition: form-data; name= '), 'b')
    refuse(m.parse_form_data, 'bad_value:part.disposition.syntax',
           one(b'Content-Disposition: form-data; name=\t'), 'b')


def test_parse_close_padding_at_eof_and_serialize_part_cap():
    # 733-survivor witness: close padding runs to EOF without CRLF
    body = b'--b\r\n' + CD + b'\r\n\r\nhi\r\n--b-- \t'
    assert m.parse_form_data(body, 'b') == (('a', None, None, b'hi'),)
    body = b'--b\r\n' + CD + b'\r\n\r\nhi\r\n--b-- '
    assert m.parse_form_data(body, 'b') == (('a', None, None, b'hi'),)
    # 837-survivor witness: exactly MAX_PARTS parts serialize fine
    parts = [('p%d' % i, None, None, b'') for i in range(64)]
    assert m.parse_form_data(m.serialize_form_data(parts, 'b'), 'b') == tuple(parts)


def test_ct_ending_in_x_accepted():
    # 998-superset-survivor witness: 'x' is an ordinary final char
    assert m.serialize_form_data([('a', None, 'a/b; y=x', b'v')], 'b')
    assert m.serialize_form_data([('a', None, 'text/x', b'v')], 'b')


def test_parse_delimiter_padding_at_eof_is_clean_refusal():
    # 733-survivor witness: padding that runs to EOF refuses, never raises bare
    refuse(m.parse_form_data, 'bad_value:body.delimiter', b'--b \t', 'b')
    refuse(m.parse_form_data, 'bad_value:body.delimiter', b'--b ', 'b')
    refuse(m.parse_form_data, 'bad_value:body.delimiter', b'--b\r\n' + CD + b'\r\n\r\nx\r\n--b \t', 'b')


def test_parse_header_count_exact_arithmetic():
    # 1135-survivor witnesses: count+1 arithmetic pinned at 9 and 10 lines
    heads9 = b'\r\n'.join(b'X-H%d: v' % i for i in range(9)) + b'\r\n' + CD
    refuse(m.parse_form_data, 'bad_value:part.header.count', one(heads9), 'b')
    heads10 = b'\r\n'.join(b'X-H%d: v' % i for i in range(10)) + b'\r\n' + CD
    refuse(m.parse_form_data, 'bad_value:part.header.count', one(heads10), 'b')
    heads7 = b'\r\n'.join(b'X-H%d: v' % i for i in range(7)) + b'\r\n' + CD
    assert m.parse_form_data(one(heads7), 'b')[0][0] == 'a'


def test_ct_tilde_in_params_and_single_char_padding():
    # 1001-survivor witness: '~' (126) is a legal param char
    assert m.serialize_form_data([('a', None, 'a/b; x=~', b'v')], 'b')
    got = m.parse_form_data(one(CD + b'\r\nContent-Type: a/b; x=~'), 'b')
    assert got[0][2] == 'a/b; x=~'
    # 1210-survivor witness: padding of exactly one char is legal framing
    body = b'--b \r\n' + CD + b'\r\n\r\nhi\r\n--b-- \r\n'
    assert m.parse_form_data(body, 'b') == (('a', None, None, b'hi'),)
    body = b'--b\t\r\n' + CD + b'\r\n\r\nhi\r\n--b--\t\r\n'
    assert m.parse_form_data(body, 'b') == (('a', None, None, b'hi'),)


# ---------------------------------------------------------------- rev1b pins

def test_tab_folded_first_header_line_refused_as_fold():
    # L185 pin: first segment byte TAB (9) sorts below CR; must be a fold, not 'missing'
    for lead in (b'\t', b' ', b'\t\t', b' \t'):
        body = b'--b\r\n' + lead + b'foo: x\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n'
        refuse(m.parse_form_data, 'bad_value:part.header.fold', body, 'b')
    # first line starting with a byte below and above CR[0] but not CRLF
    for lead in (b'\x00', b'\x01', b'\x0e', b'\x7f'):
        body = b'--b\r\n' + lead + b'oo: x\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n'
        refuse(m.parse_form_data, 'bad_value:part.header.chars', body, 'b')
    for lead in (b'A', b'~'):
        body = b'--b\r\n' + lead + b'oo: x\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n'
        assert m.parse_form_data(body, 'b') == (('a', None, None, b'hi'),)
    # a lone CR then non-LF
    refuse(m.parse_form_data, 'bad_value:part.header.chars', b'--b\r\n\rx: y\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n', 'b')
    # exactly CRLF at segment start: missing disposition
    refuse(m.parse_form_data, 'bad_value:part.disposition.missing', b'--b\r\n\r\n\r\nhi\r\n--b--\r\n', 'b')
    # one-byte and two-byte segments below CR
    refuse(m.parse_form_data, 'bad_value:part.header.fold', b'--b\r\n\t\r\n--b--\r\n', 'b')


def test_bare_delimiter_and_truncated_close_refused_as_delimiter():
    # L233 pin: slice after delimiter equal to '' , '-' or '--' prefixes must not count as a close
    refuse(m.parse_form_data, 'bad_value:body.delimiter', b'--abc', 'abc')
    refuse(m.parse_form_data, 'bad_value:body.delimiter', b'--abc-', 'abc')
    refuse(m.parse_form_data, 'bad_value:body.delimiter', b'--abc-x', 'abc')
    refuse(m.parse_form_data, 'bad_value:body.delimiter', b'--abcx', 'abc')
    refuse(m.parse_form_data, 'bad_value:body.close', b'--abc--x', 'abc')
    refuse(m.parse_form_data, 'bad_value:body.empty', b'--abc--', 'abc')
    refuse(m.parse_form_data, 'bad_value:body.empty', b'--abc--\r\n', 'abc')
    nb = b'--b\r\n' + CD + b'\r\n\r\nhi\r\n--b'
    refuse(m.parse_form_data, 'bad_value:body.delimiter', nb, 'b')
    refuse(m.parse_form_data, 'bad_value:body.delimiter', nb + b'-', 'b')
    refuse(m.parse_form_data, 'bad_value:body.close', nb + b'--x', 'b')
    assert m.parse_form_data(nb + b'--', 'b') == (('a', None, None, b'hi'),)


def test_rev1b_long_inputs_every_bound_over_256_and_2048():
    ok = lambda s: m.boundary_ok(s)
    for n in (69, 70, 71, 255, 256, 257, 300, 2048, 2049):
        s = 'a' * n
        if n <= 256:
            assert ok(s) is (n <= 70), n
        else:
            refuse(m.boundary_ok, 'bad_value:boundary.length', s)
    # pct decode at 255/256/257/2048/3072/3073
    for n in (255, 256, 257, 2047, 2048, 2049, 3071, 3072):
        assert m.pct_decode_param('a' * n) == 'a' * n
    refuse(m.pct_decode_param, 'bad_value:value.length', 'a' * 3073)
    for n in (254, 255):
        assert m.pct_encode_param('a' * n) == 'a' * n
    refuse(m.pct_encode_param, 'bad_value:text.length', 'a' * 256)
    # header lines at 300 / 2048 / 8192 / 8193 chars
    for n in (300, 2048, 8191, 8192):
        line = b'X-L: ' + b'v' * (n - 5)
        assert len(line) == n
        assert m.parse_form_data(b'--b\r\n' + line + b'\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n', 'b')[0][0] == 'a'
    line = b'X-L: ' + b'v' * (8193 - 5)
    refuse(m.parse_form_data, 'bad_value:part.header.length', b'--b\r\n' + line + b'\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n', 'b')
    # long preamble / long padding / long data containing partial delimiters
    pre = b'x' * 300 + b'\r\n'
    assert m.parse_form_data(pre + b'--b\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n', 'b')[0][3] == b'hi'
    pre = b'x' * 2048 + b'\r\n'
    assert m.parse_form_data(pre + b'--b\r\n' + CD + b'\r\n\r\nhi\r\n--b--\r\n', 'b')[0][3] == b'hi'
    pad = b' \t' * 300
    assert m.parse_form_data(b'--b' + pad + b'\r\n' + CD + b'\r\n\r\nhi\r\n--b--' + pad + b'\r\n', 'b')[0][3] == b'hi'
    data = (b'\r\n-' * 300) + b'x'
    assert m.parse_form_data(b'--b\r\n' + CD + b'\r\n\r\n' + data + b'\r\n--b--\r\n', 'b')[0][3] == data
    # 256 parts-ish: part cap at 64/65 with many bytes
    parts = [('f%d' % i, None, None, b'd' * 300) for i in range(64)]
    s = m.serialize_form_data(parts, 'b')
    assert len(m.parse_form_data(s, 'b')) == 64
    refuse(m.serialize_form_data, 'bad_value:parts.length', parts + [('z', None, None, b'')], 'b')
    # long names and filenames through roundtrip
    nm = 'n' * 250
    s = m.serialize_form_data([(nm, 'f' * 250, None, b'')], 'b')
    assert m.parse_form_data(s, 'b') == ((nm, 'f' * 250, None, b''),)


# ---------------------------------------------------------------- rev1b edge and size grid

SIZES = (0, 1, 2, 255, 256, 257, 300, 1000)


def dparse(v):
    return m.parse_form_data(one(b'Content-Disposition: ' + v), 'b')


def drefuse(want, v):
    refuse(m.parse_form_data, 'bad_value:part.disposition.' + want, one(b'Content-Disposition: ' + v), 'b')


def test_disposition_value_ends_at_every_scanner_state():
    for z in SIZES:
        ws = b' \t' * (z // 2) + b' ' * (z % 2)
        pad = lambda: ws
        drefuse('syntax', b'form-data;')
        drefuse('syntax', b'form-data;' + pad() + b'x')
        drefuse('syntax', b'form-data; name')
        drefuse('syntax', b'form-data; name' + pad() + b'x')
        drefuse('syntax', b'form-data; name=')
        drefuse('syntax', b'form-data; name' + pad() + b'=')
        drefuse('syntax', b'form-data; name=' + pad() + b'x')
        drefuse('syntax', b'form-data; name="')
        drefuse('syntax', b'form-data; name="' + b'a' * z)
        drefuse('syntax', b'form-data; name="' + b'a' * z + b'\\')
        drefuse('syntax', b'form-data; name="' + b'a' * z + b'\tq"')
        drefuse('syntax', b'form-data; name="a"x')
        drefuse('syntax', b'form-data; name="a"' + pad() + b'x')
        drefuse('syntax', b'form-data; =' + b'"a"')
        drefuse('syntax', b'form-data;' + pad() + b'="a"')
        drefuse('type' if z == 0 else 'syntax', b'form-data' + pad() + b'x; name="a"')
        drefuse('syntax', b';name="a"')
        drefuse('syntax', b'; name="a"')
        drefuse('type', b'x' * (z + 1) + b'; name="a"')
        drefuse('type', b'x' * (z + 1))
        drefuse('name', b'form-data; filename="f"')
        drefuse('param', b'form-data; name="a"; ' + b'k' * (z + 1) + b'="v"')
        drefuse('duplicate_dummy' if False else 'param', b'form-data; name="a"; name="b"')
        drefuse('syntax', b'form-data; name="a"; ' + b'k' * (z + 1))
        drefuse('syntax', b'form-data; name="a"; ' + b'k' * (z + 1) + b' x')
        drefuse('syntax', b'form-data; name="a"; ' + b'k' * (z + 1) + b'=')


def test_disposition_whitespace_runs_accepted_at_every_size():
    for z in SIZES[:-1]:
        for unit in (b' ', b'\t', b' \t'):
            ws = unit * z
            v = (b'form-data' + ws + b';' + ws + b'name' + ws + b'=' + ws + b'"a"' + ws + b';' + ws
                 + b'filename' + ws + b'=' + ws + b'"f"')
            assert dparse(v) == (('a', 'f', None, b'x'),), (z, unit)
            drefuse('syntax', b'form-data' + ws + b';' + ws + b'name="a"' + ws + b';')
            drefuse('syntax', b'form-data; name="a";' + ws + b'filename="f";')
            assert dparse(b'form-data; name="a";' + ws + b'filename="f"') == (('a', 'f', None, b'x'),)


def test_disposition_values_at_length_edges():
    for z in (0, 1, 255, 256, 257, 300, 2047, 2048, 2049, 3071, 3072):
        v = b'form-data; name="' + b'v' * z + b'"; filename="' + b'w' * z + b'"'
        assert dparse(v) == (('v' * z, 'w' * z, None, b'x'),)
    drefuse('length', b'form-data; name="' + b'v' * 3073 + b'"')
    drefuse('length', b'form-data; name="a"; filename="' + b'v' * 3073 + b'"')
    drefuse('length', b'form-data; filename="' + b'v' * 3073 + b'"; name="a"')
    drefuse('filename_star', b'form-data; name="a"; filename*="' + b'v' * 300 + b'"')
    drefuse('filename_star', b'form-data; filename*="v"; name="a"')


def test_content_type_scanner_at_length_edges():
    for z in (1, 2, 100, 200, 240):
        t = ('t' * z + '/' + 's' * 1).encode()
        got = m.parse_form_data(one(CD + b'\r\nContent-Type: ' + t), 'b')
        assert got[0][2] == t.decode()
        t = ('t/' + 's' * z).encode()
        assert m.parse_form_data(one(CD + b'\r\nContent-Type: ' + t), 'b')[0][2] == t.decode()
        t = ('t/s' + ' ' * z + '; a=b').encode()
        got = m.parse_form_data(one(CD + b'\r\nContent-Type: ' + t), 'b')
        assert got[0][2] == t.decode()
        t = ('t/s;' + ' ' * z + 'a=b').encode()
        assert m.parse_form_data(one(CD + b'\r\nContent-Type: ' + t), 'b')[0][2] == t.decode()
    for z in (255, 256, 257, 300, 2048):
        bad = b'Content-Type: t/' + b's' * z
        got = err(m.parse_form_data, one(CD + b'\r\n' + bad), 'b')
        assert got.endswith('part.content_type.syntax') == (z + 2 > 255)
    for t in (b't/', b't/ ', b't/;', b't/s x', b't/s;\x01', b't', b'/s', b't/s/u',
              b't/s;x=\x7f'):
        got = err(m.parse_form_data, one(CD + b'\r\nContent-Type: ' + t), 'b')
        assert got.endswith('part.content_type.syntax') or got.endswith('part.header.chars'), t
    assert m.parse_form_data(one(CD + b'\r\nContent-Type: t/s;'), 'b')[0][2] == 't/s;'


def test_frame_padding_data_and_epilogue_at_every_size():
    for z in SIZES + (2048, 2049):
        for unit in (b' ', b'\t'):
            pad = unit * z
            data = b'd' * z
            body = b'--b' + pad + b'\r\n' + CD + b'\r\n\r\n' + data + b'\r\n--b' + pad + b'\r\n' + CD.replace(b'"a"', b'"z"') + b'\r\n\r\n\r\n--b--' + pad + b'\r\n' + b'e' * z
            assert m.parse_form_data(body, 'b') == (('a', None, None, data), ('z', None, None, b''))
            body = b'p' * z + b'\r\n--b' + pad + b'\r\n' + CD + b'\r\n\r\nq\r\n--b--' + pad
            assert m.parse_form_data(body, 'b') == (('a', None, None, b'q'),)
            refuse(m.parse_form_data, 'bad_value:body.delimiter', b'--b' + pad + b'x\r\n' + CD + b'\r\n\r\nq\r\n--b--', 'b')
            refuse(m.parse_form_data, 'bad_value:body.close', b'--b\r\n' + CD + b'\r\n\r\nq\r\n--b--' + pad + b'x', 'b')
            refuse(m.parse_form_data, 'bad_value:body.unterminated', b'--b' + pad + b'\r\n' + CD + b'\r\n\r\n' + data, 'b')
            refuse(m.parse_form_data, 'bad_value:body.empty', b'p' * z + b'\r\n--b--' + pad + b'\r\n', 'b')
            refuse(m.parse_form_data, 'bad_value:body.start', b'p' * (z + 1) + b'--b\r\n', 'b')
    for n in (63, 64, 65, 66):
        parts = [b'--b\r\n' + CD + b'\r\n\r\nv%d\r\n' % i for i in range(n)]
        body = b''.join(parts) + b'--b--\r\n'
        if n <= 64:
            assert len(m.parse_form_data(body, 'b')) == n
        else:
            refuse(m.parse_form_data, 'bad_value:body.parts', body, 'b')


def test_pct_decode_percent_positions_and_sizes():
    for z in (0, 1, 2, 255, 256, 257, 300, 2047, 2048, 3068, 3069):
        a = 'a' * z
        assert m.pct_decode_param(a + '%41') == a + 'A'
        assert m.pct_decode_param('%41' + a) == 'A' + a
        refuse(m.pct_decode_param, 'bad_value:value.pct', a + '%4')
        refuse(m.pct_decode_param, 'bad_value:value.pct', a + '%')
        refuse(m.pct_decode_param, 'bad_value:value.pct', a + '%4g')
        refuse(m.pct_decode_param, 'bad_value:value.pct', a + '%g4')
    for n in (85, 86, 341, 1023, 1024):
        assert m.pct_decode_param('%41' * n) == 'A' * n


def test_header_block_edges_at_sizes():
    assert m.parse_form_data(b'--b\r\n' + CD + b'\r\n\r\n\r\n--b--', 'b') == (('a', None, None, b''),)
    refuse(m.parse_form_data, 'bad_value:part.disposition.missing', b'--b\r\nX-A: v\r\n\r\nq\r\n--b--', 'b')
    refuse(m.parse_form_data, 'bad_value:part.header.syntax', b'--b\r\n:v\r\n' + CD + b'\r\n\r\nq\r\n--b--', 'b')
    refuse(m.parse_form_data, 'bad_value:part.header.syntax', b'--b\r\nnocolon\r\n' + CD + b'\r\n\r\nq\r\n--b--', 'b')
    for z in (255, 256, 257, 300, 2048):
        refuse(m.parse_form_data, 'bad_value:part.header.syntax', b'--b\r\n' + b'h' * z + b'\r\n' + CD + b'\r\n\r\nq\r\n--b--', 'b')
        refuse(m.parse_form_data, 'bad_value:part.header.syntax', b'--b\r\n' + b'h' * z + b' : v\r\n' + CD + b'\r\n\r\nq\r\n--b--', 'b')
        assert m.parse_form_data(b'--b\r\n' + b'h' * z + b': v\r\n' + CD + b'\r\n\r\nq\r\n--b--', 'b')[0][0] == 'a'
        assert m.parse_form_data(b'--b\r\nX: ' + b'v' * z + b'\r\n' + CD + b'\r\n\r\nq\r\n--b--', 'b')[0][0] == 'a'
    refuse(m.parse_form_data, 'bad_value:part.disposition.duplicate', b'--b\r\n' + CD + b'\r\n' + CD + b'\r\n\r\nq\r\n--b--', 'b')
    refuse(m.parse_form_data, 'bad_value:part.content_type.duplicate',
           b'--b\r\n' + CD + b'\r\nContent-Type: a/b\r\nContent-Type: a/b\r\n\r\nq\r\n--b--', 'b')
    assert m.parse_form_data(b'--b\r\ncontent-DISPOSITION: FORM-data; NAME="a"\r\nCONTENT-type: a/b\r\n\r\nq\r\n--b--', 'b') == (('a', None, 'a/b', b'q'),)
    refuse(m.parse_form_data, 'bad_value:part.header.syntax', b'--b\r\n' + CD + b'\r\nbad name: v\r\n\r\nq\r\n--b--', 'b')


# ---------------------------------------------------------------- rev1b golden corpus (regression pin)

def golden_corpus(seed=1):
    R=random.Random(seed); C=[]
    S=(0,1,2,3,5,255,256,257,300,2048)
    toks=['name','filename','filename*','x','form-data','Form-Data','a','b']
    def ws(): return R.choice(['',' ','\t',' \t',' '*R.choice(S),'\t'*R.choice(S)])
    def q(): return R.choice(['"a"','"'+'v'*R.choice(S)+'"','"','"a','a"','"a\\"','"\ta"','""',"'a'"])
    def vdisp():
        w=ws
        v='form-data'+w()+';'+w()+'name'+w()+'='+w()+'"'+R.choice(['a','n'*R.choice(S),'v w'])+'"'
        if R.random()<.5: v+=w()+';'+w()+R.choice(['filename','FileName'])+w()+'='+w()+'"'+R.choice(['f','f'*R.choice(S),''])+'"'
        return v
    def disp():
        if R.random()<.8: return vdisp()
        v=R.choice(['form-data','x','',' ','Form-Data']) if R.random()<.8 else 'f'*R.choice(S)
        v+=ws()
        for _ in range(R.choice([0,1,1,2,3])):
            v+=R.choice([';','; ',';;','',' ;'])+ws()+R.choice(toks+['k'*R.choice(S),''])+ws()+R.choice(['=','=','','==',' = '])+ws()+q()+ws()
        if R.random()<.15: v=v.strip(' \t')+R.choice([';',';x','"',''])
        return v
    def ct():
        if R.random()<.7: return R.choice(['t/s','t/s; a=b','text/plain; charset=utf-8','t/s ;a=b','t/s;'+ws()[:3]+'a=b','t'*R.choice([1,100,200])+'/s','t/'+'s'*R.choice([1,100,200]),'t/s;'])
        return R.choice(['t/s','t/','/s','t','t/s;','t/s; a=b','t/s ; a=b','t/'+'s'*R.choice(S),'t'*R.choice(S)+'/s','t/s;'+ws()+'a=b'+ws(),'t/s'+ws()+';x','t/s\x01','t/s;x=\x7f',''])
    def part():
        h=[]
        for _ in range(R.choice([0,1,1,1,1,1,2,2,3,7,8,9])):
            k=R.random()
            if k<.6: h.append('Content-Disposition: '+disp())
            elif k<.8: h.append('Content-Type: '+ct())
            elif R.random()<.7: h.append(R.choice(['X-A: v','Content-Transfer-Encoding: binary','X: '+'v'*R.choice([0,1,300,2000,8000])]))
            else: h.append(R.choice(['X-A: v','x:v',':v','nocolon','\tfold: x',' fold: y','bad name: v','h'*R.choice(S)+': v','X: '+'v'*R.choice([0,300,8190,8200]),'X-\x01: v','X: \x80']))
        if R.random()<.93 and not any(x.startswith('Content-Disp') for x in h): h.insert(R.randrange(len(h)+1),'Content-Disposition: form-data; name="a"')
        hb='\r\n'.join(h).encode('latin-1')
        d=R.choice([b'',b'x',b'x',b'x',b'x',b'd'*R.choice(S),b'\r\n',b'\r\n-'*R.choice([1,300]),b'x\r\n--bx']+[b'x']*6+[b'\r\n--',b'\r\n--b',b'--b'][:R.choice([0,0,0,0,0,3])])
        sep=R.choice([b'\r\n\r\n']*40+[b'\r\n',b'',b'\n\n'])
        return hb+sep+d
    for _ in range(14000):
        b=R.choice(['b','b','b','abc','b'*70,'b'*R.choice([0,71,256,257,300])])
        bb=b.encode()
        parts=[part() for _ in range(R.choice([1]*10+[2]*6+[3]*3+[5,0,64,65]))] if R.random()<.97 else []
        pad=lambda: R.choice([b'']*4+[b' ',b'\t',b' \t'*R.choice(S)])
        body=R.choice([b'',b'p'*R.choice(S),b'p\r\n',b'p'*R.choice(S)+b'\r\n'])
        for p in parts: body+=b'--'+bb+pad()+R.choice([b'\r\n']*400+[b'',b'\n',b'x',b'-',b'--'])+p+b'\r\n'
        close=R.choice([b'--'+bb+b'--'+pad()+R.choice([b'\r\n',b'',b'\r\nE'*3,b'\r\n'+b'e'*R.choice(S),b'x'])]*14+[b'--'+bb,b'--'+bb+b'-',b'--'+bb+b'--x',b'--'+bb+b'-'+pad(), b''])
        body+=close
        if R.random()<.04: body=body[:R.randrange(len(body)+1)]
        C.append(('parse_form_data',(body,b)))
    for _ in range(2500):
        n=R.choice([1,1,2,3,4,63,64,64,65])
        ps=[]
        for _ in range(n):
            nm=R.choice(['a','b','n'*R.choice([1,2,254,255,256,257,300]) ,'a b','a','a','\xe9','\xe9'*85,'\xe9'*86,'~-._!*()','\xe9','a\r\n','a"b','\x00','x'*3072,'%','\ud800'])
            fn=R.choice([None,None,'f','f'*R.choice(S),'','\xe9'])
            ctt=R.choice([None,None,'t/s','t/'+'s'*R.choice(S),'t/s; a=b','','t'])
            dt=R.choice([b'',b'd'*R.choice(S),b'\r\n--b',b'\r\n--bb',b'x'*R.choice([0,262143,262144,262145]) if R.random()<.1 else b'q'])
            ps.append(R.choice([(nm,fn,ctt,dt)]*40+[(nm,fn,ctt),(nm,),'x',(1,2,3,4),(nm,fn,ctt,'s'),[nm,fn,ctt,dt]]))
        ps=R.choice([ps,tuple(ps)])
        C.append(('serialize_form_data',(ps,R.choice(['b']*12+['abc','b'*70,'b'*71,'','a b','b '])) ))
    for _ in range(1500):
        C.append(('boundary_ok',(R.choice(['b','a'*R.choice([0,1,69,70,71,255,256,257,300]),'a b','a ','\xe9','\x00',"'()+_,-./:=?","!#"]),)))
    for _ in range(2500):
        a='%41'*R.choice([0,1,2,85,86,1024,1025])+R.choice(['','%','%4','%4g','%g4','%41','a'*R.choice(S),'\xe9','%c3%a9','%00','%ff'])
        C.append(('pct_decode_param',(a,)))
        C.append(('pct_encode_param',(R.choice(['','a','\xe9','\ud800','a'*R.choice([254,255,256]),'x y','~-._'])+R.choice(['','\xe9'*R.choice([0,1,127,128])]),)))
    for fn in ('parse_form_data','serialize_form_data','boundary_ok','pct_decode_param','pct_encode_param'):
        for a in (None,1,b'x','x',[],(),b'x'): C.append((fn,(a,)) if fn!='parse_form_data' and fn!='serialize_form_data' else (fn,(a,'b')))
    return C


def golden_run(mod, corp):
    out = []
    for fname, args in corp:
        try:
            r = getattr(mod, fname)(*args)
        except ValueError as e:
            r = ('VE', str(e))
        except BaseException as e:
            r = ('EX', type(e).__name__)
        out.append(r)
    return out


GOLDEN_SHA = 'c8db87b304bbb679ba9a29b2a23cd92638a308333c6bd9536280358435407912'


def test_golden_corpus_outputs_pinned_whole():
    corp = golden_corpus(1)
    assert len(corp) == 23035
    res = golden_run(m, corp)
    kinds = {}
    for r in res:
        k = r[0] if type(r) is tuple and len(r) == 2 and r[0] in ('VE', 'EX') else type(r).__name__
        kinds[k] = kinds.get(k, 0) + 1
    assert kinds['tuple'] > 1000 and kinds['bytes'] > 100 and kinds['bool'] > 1000
    assert 'EX' not in kinds
    assert hashlib.sha256('\n'.join(repr(r) for r in res).encode('utf-8', 'surrogatepass')).hexdigest() == GOLDEN_SHA


# ---------------------------------------------------------------- rev1b whitespace-set sweeps (every ASCII byte)

def _accepts(v):
    try:
        got = m.parse_form_data(one(b'Content-Disposition: ' + v), 'b')
    except ValueError:
        return False
    return got[0][0] == 'a'


def test_disposition_skips_only_space_and_tab_at_every_position():
    for c in range(128):
        cb = bytes([c])
        ws = c == 9 or c == 32
        cases = (
            b'form-data;' + cb + b'name="a"',
            b'form-data; name' + cb + b'="a"',
            b'form-data; name=' + cb + b'"a"',
            b'form-data; name="a"' + cb + b';filename="f"',
            b'form-data; name="a"' + cb + b'; filename="f"',
            b'form-data' + cb + b'; name="a"',
            cb + b'form-data; name="a"',
            b'form-data; name="a"' + cb,
            b'form-data; name="a"; filename="f"' + cb,
        )
        want = (ws, ws, ws, ws, ws, ws, ws, ws, ws)
        for case, w in zip(cases, want):
            assert _accepts(case) is (w and True), (c, case)
    # Content-Type: leading skip, trailing-edge and token edge
    for c in range(128):
        cb = bytes([c])
        ws = c == 9 or c == 32
        t = b't/s ' + cb + b';a=b'
        got = _ct_parse(t)
        assert got is (c == 9 or c == 32 or c == 59), (c, got)
        t = b't/s;a=' + cb
        got = _ct_parse(t)
        assert got is (c == 9 or c == 32 or 33 <= c <= 126), (c, got)
        t = b't/s' + cb + b'x'
        got = _ct_parse(t)
        want = (c in range(48, 58) or c in range(65, 91) or c in range(97, 123) or cb in b"!#$%&'*+-.^_`|~;")
        assert got is want, (c, got)


def _ct_parse(t):
    try:
        got = m.parse_form_data(one(CD + b'\r\nContent-Type: ' + t), 'b')
    except ValueError:
        return False
    return got[0][2] is not None


def test_eq_is_witnesses_runtime_built_values():
    # non-interned strings and ints > 256 reached through arithmetic, public API only
    nm = ''.join(['n', 'a', 'm', 'e'])
    fn = ''.join(['f', 'i', 'l', 'e'])
    fnn = fn + 'name'
    v = 'form-data; ' + nm + '="' + ''.join(['a']) + '"; ' + fnn + '="' + ''.join(['f']) + '"'
    assert dparse(v.encode()) == (('a', 'f', None, b'x'),)
    v = ('x' * 5).replace('x', 'q') + '='
    big = 256 + 1 + len('ab') * 100
    for extra in (big, big + 1, 1500 + len('abc')):
        pad = ' ' * extra
        assert dparse(('form-data' + pad + ';' + pad + nm + pad + '=' + pad + '"a"').encode()) == (('a', None, None, b'x'),)
        drefuse('syntax', ('form-data; ' + nm + pad + '=').encode())
        drefuse('syntax', ('form-data; ' + nm + '="' + 'a' * extra).encode())
        drefuse('syntax', ('form-data; ' + nm + '=' + pad + 'x').encode())
    # empty-string results built at runtime
    drefuse('syntax', b'form-data; =""')
    drefuse('syntax', b'form-data;')
    drefuse('syntax', ('form-data; ' + '=').encode())
    # subclass inputs refused by exact-type check
    refuse(m.parse_form_data, 'bad_type:body', SBytes(b'--b\r\n' + CD + b'\r\n\r\nq\r\n--b--'), 'b')
    refuse(m.parse_form_data, 'bad_type:boundary', b'--b\r\n' + CD + b'\r\n\r\nq\r\n--b--', SStr('b'))


# ---------------------------------------------------------------- rev1b survivor pins (registry worlds, header names, padding bytes, metaclass)

MODPATH = None


class _Raiser:
    def __init__(self, name):
        self.name = name

    def find_spec(self, fullname, path=None, target=None):
        if fullname == REG:
            raise ModuleNotFoundError('missing', name=self.name)
        return None


def _world(monkeypatch, name, spec_ret):
    calls = []

    def spy(n, *a, **k):
        calls.append(n)
        return spec_ret

    monkeypatch.setattr(iu, 'find_spec', spy)
    sys.modules.pop(REG, None)
    fin = _Raiser(name)
    sys.meta_path.insert(0, fin)
    try:
        spec = iu.spec_from_file_location('p235_world_probe', m.__file__)
        mod = iu.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except ModuleNotFoundError as e:
            return calls, None, e
        return calls, mod, None
    finally:
        sys.meta_path.remove(fin)
        sys.modules.pop(REG, None)


def test_world_foreign_missing_names_short_circuit_before_find_spec(monkeypatch):
    for name in ('zzz.dep', 'aaa', REG + 'x', REG[:-1], REG[5:], 'app', '', None):
        calls, mod, e = _world(monkeypatch, name, None)
        assert mod is None and e is not None and e.name == name, name
        assert calls == [], (name, calls)


def test_world_exact_registry_name_runtime_built_falls_back(monkeypatch):
    name = ''.join(list(REG))
    assert name == REG
    calls, mod, e = _world(monkeypatch, name, None)
    assert e is None and calls == [REG]
    try:
        mod.make_fail('x')('c')
    except ValueError as ve:
        assert str(ve) == 'P235:x:c'
    else:
        raise AssertionError('make_fail must raise')
    assert mod.boundary_ok('b') is True
    # registry file present per find_spec: the original error is re-raised
    calls, mod, e = _world(monkeypatch, name, object())
    assert mod is None and e is not None and e.name == REG and calls == [REG]

    class Odd:
        def __ne__(self, other):
            return False

        def __eq__(self, other):
            return True

        __hash__ = None

    calls, mod, e = _world(monkeypatch, name, Odd())
    assert mod is None and e is not None and calls == [REG]


def test_world_falsy_non_none_spec_still_reraises(monkeypatch):
    name = ''.join(list(REG))
    for spec in (0, '', (), b'', False, [], {}, 0.0):
        calls, mod, e = _world(monkeypatch, name, spec)
        assert mod is None and e is not None and e.name == REG, repr(spec)
        assert calls == [REG], repr(spec)

    class Falsy:
        def __bool__(self):
            return False

        def __len__(self):
            return 0

    calls, mod, e = _world(monkeypatch, name, Falsy())
    assert mod is None and e is not None and e.name == REG and calls == [REG]


def test_serialize_falsy_non_none_filename_and_content_type():
    for v in (0, 0.0, False, b'', (), [], {}):
        refuse(m.serialize_form_data, 'bad_type:part.filename', [('a', v, None, b'x')], 'b')
        refuse(m.serialize_form_data, 'bad_type:part.content_type', [('a', None, v, b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', None, '', b'x')], 'b')
    refuse(m.serialize_form_data, 'bad_value:part.content_type.syntax', [('a', '', '', b'')], 'b')
    got = m.serialize_form_data([('a', '', None, b'x')], 'b')
    assert got == b'--b\r\nContent-Disposition: form-data; name="a"; filename=""\r\n\r\nx\r\n--b--\r\n'


def test_lone_cr_or_lf_first_segment_is_header_chars():
    for seg in (b'\r', b'\n', b'\r\r', b'\n\r', b'\n\n'):
        refuse(m.parse_form_data, 'bad_value:part.header.chars', b'--b\r\n' + seg + b'\r\n--b--', 'b')


def test_header_names_that_are_substrings_are_ignored_not_matched():
    for name in (b'Content', b'Disposition', b'Content-Disp', b'Content-Disposition-X', b'Content-Disposi',
                 b'position', b'c', b'on', b'-', b'e', b'X-Content-Disposition'):
        got = m.parse_form_data(one(CD + b'\r\n' + name + b': form-data; name="b"'), 'b')
        assert got == (('a', None, None, b'x'),), name
    for name in (b'Content-Typ', b'ype', b'Type', b'content', b'-type', b'Content-Type-X', b't', b'e',
                 b'content-', b'-', b'X-Content-Type'):
        got = m.parse_form_data(one(CD + b'\r\nContent-Type: a/b\r\n' + name + b': a/b'), 'b')
        assert got == (('a', None, 'a/b', b'x'),), name


def test_delimiter_padding_accepts_only_space_and_tab_every_byte():
    for c in range(256):
        cb = bytes([c])
        ws = c == 9 or c == 32
        body = b'--b' + cb + b'\r\n' + CD + b'\r\n\r\nq\r\n--b--\r\n'
        try:
            got = m.parse_form_data(body, 'b')
            ok = got == (('a', None, None, b'q'),)
        except ValueError as e:
            ok = False
            assert str(e).endswith('body.delimiter') or str(e).endswith('part.header.chars') or str(e).endswith('body.start') or str(e).endswith('part.header.syntax') or str(e).endswith('part.disposition.missing') or str(e).endswith('body.unterminated'), (c, str(e))
        assert ok is ws, c
        body = b'--b\r\n' + CD + b'\r\n\r\nq\r\n--b' + cb + b'\r\n--b--'
        try:
            got = m.parse_form_data(body, 'b')
            ok = len(got) == 2
        except ValueError:
            ok = False
        assert ok is False or ws, c
        body = b'--b\r\n' + CD + b'\r\n\r\nq\r\n--b--' + cb + b'\r\n'
        try:
            ok = m.parse_form_data(body, 'b') == (('a', None, None, b'q'),)
        except ValueError as e:
            ok = False
            assert str(e).endswith('body.close'), (c, str(e))
        assert ok is ws, c


def test_disposition_delimiter_char_replacement_sweeps():
    for c in range(128):
        cb = bytes([c])
        assert _accepts(b'form-data; name' + cb + b'"a"') is (c == 61), c
        assert _accepts(b'form-data; name=' + cb + b'a"') is (c == 34), c
        assert _accepts(b'form-data; name="a"' + cb + b'filename="f"') is (c == 59), c
        try:
            got = dparse(b'form-data; name="a' + cb + b'"')[0][0]
        except ValueError:
            got = None
        assert got == ('a' + chr(c) if (32 <= c <= 126 and c != 34 and c != 92) else None), c


class _M(type):
    def __ne__(cls, other):
        return False

    def __eq__(cls, other):
        return True

    __hash__ = type.__hash__


class MStr(str, metaclass=_M):
    pass


class MBytes(bytes, metaclass=_M):
    pass


class MList(list, metaclass=_M):
    pass


class MTuple(tuple, metaclass=_M):
    pass


def test_exact_type_checks_reject_lookalike_metaclass_subclasses():
    good = b'--b\r\n' + CD + b'\r\n\r\nq\r\n--b--'
    refuse(m.boundary_ok, 'bad_type:boundary', MStr('b'))
    refuse(m.pct_encode_param, 'bad_type:text', MStr('b'))
    refuse(m.pct_decode_param, 'bad_type:value', MStr('b'))
    refuse(m.parse_form_data, 'bad_type:body', MBytes(good), 'b')
    refuse(m.parse_form_data, 'bad_type:boundary', good, MStr('b'))
    refuse(m.serialize_form_data, 'bad_type:boundary', [('a', None, None, b'')], MStr('b'))
    refuse(m.serialize_form_data, 'bad_type:parts', MList([('a', None, None, b'')]), 'b')
    refuse(m.serialize_form_data, 'bad_type:parts', MTuple([('a', None, None, b'')]), 'b')
    refuse(m.serialize_form_data, 'bad_type:part', [MTuple(('a', None, None, b''))], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.name', [(MStr('a'), None, None, b'')], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.filename', [('a', MStr('f'), None, b'')], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.content_type', [('a', None, MStr('a/b'), b'')], 'b')
    refuse(m.serialize_form_data, 'bad_type:part.data', [('a', None, None, MBytes(b''))], 'b')


# ------------------------------------------------ direct private-helper pins

class _HF(Exception):
    pass


def _hfail(code):
    raise _HF(code)


def _dcall(value):
    try:
        return ('ok', m._disp(_hfail, value))
    except _HF as e:
        return ('fail', e.args[0])


def _rt(*chars):
    return ''.join(chr(c) for c in chars)


def test_private_all_in_returns_exact_bools():
    assert m._all_in(_rt(97, 98), 'ab') is True
    assert m._all_in('', 'ab') is True
    assert m._all_in(_rt(97, 99), 'ab') is False
    assert m._all_in(_rt(99), 'ab') is False


def test_private_ct_ok_returns_exact_bools():
    assert m._ct_ok('a/' + 'b' * (m.MAX_CT - 2)) is True
    assert m._ct_ok('a/' + 'b' * (m.MAX_CT - 1)) is False
    assert m._ct_ok(_rt(97, 98, 99)) is False
    assert m._ct_ok('/b') is False
    assert m._ct_ok('a b/c') is False
    assert m._ct_ok('a/') is False
    assert m._ct_ok('a/b') is True
    assert m._ct_ok('a/b; c=d') is True
    assert m._ct_ok('a/b x') is False
    assert m._ct_ok('a/b;' + _rt(1)) is False
    assert m._ct_ok('a/b;' + _rt(127)) is False
    assert m._ct_ok('a/b; ') is False
    assert m._ct_ok('a/b;' + _rt(233)) is False
    assert m._ct_ok('a/b;' + _rt(126)) is True
    assert m._ct_ok('a/b;' + _rt(32)) is False


def test_private_disp_skip_ws_only_space_and_tab():
    base = 'form-data;'
    for c in range(0, 256):
        ch = _rt(c)
        before = _dcall(base + ch + 'name="a"')
        after_key = _dcall(base + 'name' + ch + '="a"')
        after_eq = _dcall(base + 'name=' + ch + '"a"')
        after_val = _dcall(base + 'name="a"' + ch + ';filename="b"')
        if c == 32 or c == 9:
            assert before == ('ok', ('a', None)), c
            assert after_key == ('ok', ('a', None)), c
            assert after_eq == ('ok', ('a', None)), c
            assert after_val == ('ok', ('a', 'b')), c
        else:
            tokc = ch in "!#$%&'*+-.^_`|~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
            exp = 'bad_value:part.disposition.param' if tokc else 'bad_value:part.disposition.syntax'
            assert before == ('fail', exp), c
            assert after_key == ('fail', exp), c
            assert after_eq == ('fail', 'bad_value:part.disposition.syntax'), c
            assert after_val == ('fail', 'bad_value:part.disposition.syntax'), c


def test_private_disp_quoted_value_rejects_only_tab_and_backslash():
    for c in range(0, 256):
        ch = _rt(c)
        r = _dcall('form-data; name="a' + ch + 'b"')
        if c == 9 or c == 92:
            assert r == ('fail', 'bad_value:part.disposition.syntax'), c
        elif c == 34:
            assert r == ('fail', 'bad_value:part.disposition.syntax'), c
        else:
            assert r == ('ok', ('a' + ch + 'b', None)), c
