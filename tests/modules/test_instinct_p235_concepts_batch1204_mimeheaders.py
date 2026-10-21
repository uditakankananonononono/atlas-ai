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
from app.modules.instinct_doc import p235_concepts_batch1204_mimeheaders as m
from email.message import Message

MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1204_mimeheaders'
REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODPATH = m.__file__


def _probe():
    try:
        m.is_token(None)
    except ValueError as e:
        s = str(e)
        assert s.endswith('is_token:text-type'), s
        return s[:-len('is_token:text-type')]
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


class SubTuple(tuple):
    pass


def run(fn, *args):
    try:
        return getattr(m, fn)(*args)
    except ValueError as e:
        assert str(e).startswith(PFX + fn + ':'), str(e)
        return 'ERR:' + str(e)[len(PFX + fn + ':'):]


TSP = set('()<>@,;:\\"/[]?=')
TOKCH = [chr(c) for c in range(33, 127) if chr(c) not in TSP]
TOKRE = "[A-Za-z0-9!#$%&'*+\\-.^_`{|}~]"
PARAM = TOKRE + '+=(?:' + TOKRE + '+|"(?:[^"\\\\]|\\\\.)*")'
FULL = re.compile('[ \\t]*(' + TOKRE + '+)/(' + TOKRE + '+)((?:[ \\t]*;[ \\t]*' + PARAM + ')*)[ \\t]*\\Z', re.S)
PRE = re.compile('[ \\t]*;[ \\t]*(' + TOKRE + '+)=(' + TOKRE + '+|"(?:[^"\\\\]|\\\\.)*")')


def o_parse(text):
    if any(ord(c) > 126 or (ord(c) < 32 and c != '\t') for c in text):
        return None
    mt = FULL.match(text)
    if mt is None:
        return None
    params = []
    for pm in PRE.finditer(mt.group(3)):
        v = pm.group(2)
        if v[0] == '"':
            v = re.sub('\\\\(.)', '\\1', v[1:-1], flags=re.S)
        params.append((pm.group(1).lower(), v))
    return mt.group(1).lower(), mt.group(2).lower(), tuple(params)


def o_format(typ, sub, params):
    out = typ + '/' + sub
    for a, v in params:
        if v != '' and all(c in TOKCH for c in v):
            q = v
        else:
            q = '"' + ''.join('\\' + c if c in '"\\' else c for c in v) + '"'
        out += '; ' + a + '=' + q
    return out


def test_constants_tables_and_namespace():
    assert m.TSPECIALS == '()<>@,;:\\"/[]?=' and len(m.TSPECIALS) == 15 and len(set(m.TSPECIALS)) == 15
    assert set(m.TSPECIALS) == TSP
    assert (m.TOKEN_MAX, m.TEXT_MAX, m.VALUE_MAX, m.PARAMS_MAX) == (255, 131072, 1024, 32)
    assert m.MECHANISMS == ('7bit', '8bit', 'binary', 'quoted-printable', 'base64')
    assert m.DISCRETE == ('text', 'image', 'audio', 'video', 'application') and m.COMPOSITE == ('message', 'multipart')
    assert m.SCOPE == 'RFC 2045 section 5.1 Content-Type and section 6.1 Content-Transfer-Encoding field values' and m.CLAIMS is False
    assert m.NOT_CLAIMED == ('comments and line folding', 'registration of media types', 'semantics of any parameter', 'the defaults of section 5.2', 'RFC 2231 parameter continuations', 'quoted-printable and base64 coding')
    assert m.ADJACENT == ('RFC 6838 media type names and registration', 'RFC 2046 media types', 'RFC 7578 form-data')
    names = {k for k in vars(m) if not k.startswith('__')}
    assert names == {'find_spec', 'make_fail', 'SCOPE', 'NOT_CLAIMED', 'ADJACENT', 'CLAIMS', 'TSPECIALS', 'TOKEN_MAX', 'TEXT_MAX', 'VALUE_MAX', 'PARAMS_MAX', 'MECHANISMS', 'DISCRETE', 'COMPOSITE', '_tok', '_is_token', 'is_token', 'classify_type', '_kind', '_skip', '_run', '_parse', 'parse_content_type', 'parse_encoding', '_quote', 'format_content_type'}
    for c in range(0, 256):
        ch = chr(c)
        want = 33 <= c <= 126 and ch not in TSP
        assert m._tok(ch) is want, c
        assert m._is_token(ch) is want, c
        assert m.is_token(ch) is want, c
        for t in ('a' + ch, ch + 'a', 'ab' + ch + 'cd'):
            assert m.is_token(t) is (want and all(33 <= ord(x) <= 126 and x not in TSP for x in t)), repr(t)
    assert m._skip('  \tx', 0) == 3 and m._skip('x', 0) == 0 and m._skip('  ', 0) == 2 and m._skip('a b', 1) == 2
    assert m._run('abc;d', 0) == 3 and m._run('abc;d', 4) == 5 and m._run(';', 0) == 0 and m._run('', 0) == 0
    assert m._quote('abc') == 'abc' and m._quote('') == '""' and m._quote('a b') == '"a b"' and m._quote('a"b\\c') == '"a\\"b\\\\c"'
    assert m._kind('text') == 'discrete' and m._kind('x-y') == 'x-token' and m._kind('x-') == 'extension' and m._kind('message') == 'composite'


def test_is_token_and_classify_type():
    assert m.is_token('') is False and m.is_token('a') is True and m.is_token('x-y') is True and m.is_token('a b') is False
    assert m.is_token('\u0131') is False and m.is_token('\u212a') is False and m.is_token('\uff11') is False and m.is_token('\u0663') is False
    assert m.is_token('a' * 255) is True
    err('is_token', 'text-length', 'a' * 256)
    err('is_token', 'text-length', ' ' * 256)
    for bad in (None, b'a', 5, ['a'], SubStr('a')):
        err('is_token', 'text-type', bad)
        err('classify_type', 'text-type', bad)
        err('parse_encoding', 'text-type', bad)
        err('parse_content_type', 'text-type', bad)
    for t in m.DISCRETE:
        for v in (t, t.upper(), t.title(), t.swapcase()):
            assert m.classify_type(v) == 'discrete', v
    for t in m.COMPOSITE:
        for v in (t, t.upper(), t.title(), t.swapcase()):
            assert m.classify_type(v) == 'composite', v
    for v in ('x-foo', 'X-foo', 'X-FOO', 'x-1', 'x--'):
        assert m.classify_type(v) == 'x-token', v
    for v in ('x-', 'X-', 'x', 'xx-y', 'texts', 'tex', 'applicatio', 'foo', 'Message2', 'a-x-b', '-x-y'):
        assert m.classify_type(v) == 'extension', v
    assert m.classify_type('a' * 255) == 'extension'
    err('classify_type', 'text-length', 'a' * 256)
    err('classify_type', 'text-length', ' ' * 256)
    for bad in ('', ' ', 'a b', 'text/plain', 'a;', '"a"', '\u00e9', 'text\n', ' text'):
        err('classify_type', 'not-token', bad)


def test_parse_encoding():
    for name in m.MECHANISMS:
        for v in (name, name.upper(), name.title(), name.swapcase(), ' ' + name, name + ' ', '\t' + name + '\t '):
            assert m.parse_encoding(v) == (name, name), v
    assert m.parse_encoding('bAsE64') == ('base64', 'base64') and m.parse_encoding('Quoted-Printable') == ('quoted-printable', 'quoted-printable')
    assert m.parse_encoding('X-Uuencode') == ('x-uuencode', 'x-token') and m.parse_encoding('x-a') == ('x-a', 'x-token')
    assert m.parse_encoding('x-') == ('x-', 'extension') and m.parse_encoding('ietf-new') == ('ietf-new', 'extension')
    assert m.parse_encoding('7bits') == ('7bits', 'extension') and m.parse_encoding('base-64') == ('base-64', 'extension')
    assert m.parse_encoding('text') == ('text', 'extension') and m.parse_encoding('message') == ('message', 'extension')
    assert m.parse_encoding('8BIT') == ('8bit', '8bit') and m.parse_encoding('BINARY') == ('binary', 'binary')
    assert m.parse_encoding('a' * 255) == ('a' * 255, 'extension')
    err('parse_encoding', 'text-length', 'a' * 256)
    err('parse_encoding', 'text-length', ' ' * 256)
    for bad in ('', ' ', '\t', 'a b', '"base64"', 'base64;', '(c) base64', 'base64 (c)', 'ba\u0131se64', '\u212ase', 'base64\n', 'a/b', 'a=b', '\u00e9', ' a b '):
        err('parse_encoding', 'mechanism-invalid', bad)
    err('parse_encoding', 'text-length', 'a b' * 100)


def test_parse_content_type_vectors():
    P = m.parse_content_type
    a = P('text/plain; charset=us-ascii')
    assert a == ('text', 'plain', (('charset', 'us-ascii'),))
    assert P('text/plain; charset="us-ascii"') == a
    assert P('Text/Plain;CHARSET=us-ASCII') == ('text', 'plain', (('charset', 'us-ASCII'),))
    assert P('TeXt/PlAiN') == ('text', 'plain', ()) and P('TEXT/plain') == ('text', 'plain', ())
    assert type(a) is tuple and type(a[2]) is tuple and type(a[2][0]) is tuple
    assert P('  text/plain  ') == ('text', 'plain', ()) and P('\ttext/plain\t;\tcharset=x\t') == ('text', 'plain', (('charset', 'x'),))
    assert P('text/plain;charset=x;format=flowed') == ('text', 'plain', (('charset', 'x'), ('format', 'flowed')))
    assert P('text/plain ; a=b ;  c=d') == ('text', 'plain', (('a', 'b'), ('c', 'd')))
    assert P('multipart/mixed; boundary="gc0p4Jq0M2Yt08jU534c0p"') == ('multipart', 'mixed', (('boundary', 'gc0p4Jq0M2Yt08jU534c0p'),))
    assert P('application/x-foo; a="b c"; d=""') == ('application', 'x-foo', (('a', 'b c'), ('d', '')))
    assert P('a/b; q="x\\"y"; r="x\\\\y"; s="\\a"') == ('a', 'b', (('q', 'x"y'), ('r', 'x\\y'), ('s', 'a')))
    assert P('a/b; q=" ; = / (c) "') == ('a', 'b', (('q', ' ; = / (c) '),))
    assert P('a/b; q="x\ty"') == ('a', 'b', (('q', 'x\ty'),))
    assert P('a/b;a=b;a=c') == ('a', 'b', (('a', 'b'), ('a', 'c')))
    assert P('x-a.b+c/y-z_1; A.b=C') == ('x-a.b+c', 'y-z_1', (('a.b', 'C'),))
    assert P('a/b; q="x" ; r=y') == ('a', 'b', (('q', 'x'), ('r', 'y')))
    assert P('a/b' + ';a=b' * 32)[2] == (('a', 'b'),) * 32
    err('parse_content_type', 'params-length', 'a/b' + ';a=b' * 33)
    err('parse_content_type', 'params-length', 'a/b' + ';a=b' * 32 + ';c=d')
    err('parse_content_type', 'param-empty', 'a/b' + ';a=b' * 32 + ';')
    err('parse_content_type', 'params-length', 'a/b' + ';a=b' * 33 + ' ;  ')
    err('parse_content_type', 'text-length', 'a' * 131073)
    assert P('a/b; q="' + 'x' * (131072 - 9) + '"')[2][0][1] == 'x' * (131072 - 9)
    assert len('a/b; q="' + 'x' * (131072 - 9) + '"') == 131072
    err('parse_content_type', 'text-length', 'a/b; q="' + 'x' * (131072 - 8) + '"')
    err('parse_content_type', 'subtype-missing', 'a' * 131072)
    assert P('a/b; q="' + 'x' * 100000 + '"')[2][0][1] == 'x' * 100000
    err('parse_content_type', 'text-length', '\u00e9' * 131073)
    for bad in ('', ' ', ';', '/', '/plain', ' /plain', '@/plain', '(c)text/plain', '"text"/plain', '=/b', ',/b'):
        err('parse_content_type', 'type-invalid', bad)
    for bad in ('text', 'text ', ' text', 'x-foo', 'a' * 300):
        err('parse_content_type', 'subtype-missing', bad)
    for bad in ('text plain', 'text;plain', 'text@x/y', 'a b/c', 'a=b', 'a;b/c', 'a"/b', 'a(c)/b', 'a ;/b', 'a\t/b'):
        err('parse_content_type', 'slash-expected', bad)
    for bad in ('text/', 'text/;', 'text/ plain', 'text/@', 'text/(c)plain', 'text/"x"', 'text/=', 'text/ ', 'text//plain'):
        err('parse_content_type', 'subtype-invalid', bad)
    for bad in ('text/plain charset=x', 'text/pl@in', 'text/plain@', 'text/plain (comment)', 'text/plain,x', 'text/plain/x', 'text/pl ain', 'a/b; c=d e=f', 'a/b; c=d (x)', 'a/b; c="d"e', 'a/b; c="d" e', 'a/b; c=d,e=f', 'a/b; c=d/e', 'a/b; c=d=e', 'a/b; c=d@', 'a/b; x=y; z=w q'):
        err('parse_content_type', 'separator-expected', bad)
    for bad in ('text/plain;', 'text/plain; ', 'text/plain;\t', 'a/b; c=d;', 'a/b; c=d; ', 'a/b;c=d;e=f; '):
        err('parse_content_type', 'param-empty', bad)
    for bad in ('a/b;;', 'a/b; ;', 'a/b; =x', 'a/b; (c)=x', 'a/b; "q"=x', 'a/b; c=d; =e', 'a/b; c=d;;e=f', 'a/b; c=d; /', 'a/b; c=d; e=f; @=g'):
        err('parse_content_type', 'attribute-invalid', bad)
    for bad in ('a/b; c', 'a/b; c ', 'a/b; c d', 'a/b; c =d', 'a/b; c;d=e', 'a/b; c=d; e', 'a/b; c=d; e f=g', 'a/b; c@=d', 'a/b; c"=d'):
        err('parse_content_type', 'equals-expected', bad)
    for bad in ('a/b; c=', 'a/b; c=;', 'a/b; c= d', 'a/b; c=(x)', 'a/b; c=;d=e', 'a/b; c=d; e=', 'a/b; c=d; e=@', 'a/b; c=d; e=\t', 'a/b; c=d; e= f', 'a/b; c=d; e=/', 'a/b; c=\\'):
        err('parse_content_type', 'value-invalid', bad)
    for bad in ('a/b; c="', 'a/b; c="d', 'a/b; c="d\\"', 'a/b; c="\\', 'a/b; c=d; e="x', 'a/b; c=d; e="x\\"', 'a/b; c="d" ; e="', 'a/b; c=""; e="\\'):
        err('parse_content_type', 'quote-unterminated', bad)
    for bad in ('a/b\n', 'a/b\r\n', 'a/b\x00', 'a/b\x7f', 'a/b\x1f', 'a/b; c="d\n"', 'a/b; c="\x01"', 'a/\u00e9', 'a/b; c=\u00e9', 'a/b; c="\u00e9"', '\u00e9', 'a/b\u2028', 'a/b; c=\u0131', 'a/b; \u212a=x', 'a/b; c="\\\u00e9"', 'a/b;\nc=d'):
        err('parse_content_type', 'char-invalid', bad)
    err('parse_content_type', 'char-invalid', '\u00e9/')
    err('parse_content_type', 'char-invalid', '/\n')
    err('parse_content_type', 'char-invalid', 'a/b; c=\u00e9;;')
    err('parse_content_type', 'char-invalid', ';;\x01')
    err('parse_content_type', 'type-invalid', ';;;')
    err('parse_content_type', 'text-length', 'a/b;' * 40000)
    err('parse_content_type', 'params-length', 'a/b' + ';a=b' * 33 + ';;')


def test_parse_content_type_oracle_exhaustive_and_random():
    alphabet = ['a', '/', ';', '=', '"', '\\', ' ', '\t', '(']
    n_ok = 0
    n = 0
    for length in range(0, 5):
        for t in itertools.product(alphabet, repeat=length):
            s = ''.join(t)
            want = o_parse(s)
            got = run('parse_content_type', s)
            if want is None:
                assert isinstance(got, str) and got.startswith('ERR:'), s
            else:
                assert got == want, (s, got, want)
                n_ok += 1
            n += 1
    assert n == sum(9 ** k for k in range(5)) and n_ok >= 5
    rnd = random.Random(1204)
    pool = ['a', 'B', 'x-', '/', ';', '=', '"', '\\', ' ', '\t', '1', '.', '@', '"b c"', 'text', 'plain', 'charset', '; a=b', '\\"']
    ok = 0
    for _ in range(6000):
        s = ''.join(rnd.choice(pool) for _ in range(rnd.randint(1, 12)))
        want = o_parse(s)
        got = run('parse_content_type', s)
        if want is None:
            assert isinstance(got, str) and got.startswith('ERR:'), s
        else:
            assert got == want, (s, got, want)
            ok += 1
    assert ok >= 20
    base = ['text/plain; charset=us-ascii', 'a/b; c="d e"; f=g', ' a/b ;c="x\\"y" ', 'x-a/b;c=d;e=""']
    ok2 = 0
    for _ in range(4000):
        s = list(rnd.choice(base))
        for _ in range(rnd.randint(0, 2)):
            k = rnd.randrange(len(s) + 1)
            if rnd.randint(0, 2) == 0 and s:
                s.pop(min(k, len(s) - 1))
            else:
                s.insert(k, rnd.choice(pool[:12]))
        s = ''.join(s)
        want = o_parse(s)
        got = run('parse_content_type', s)
        if want is None:
            assert isinstance(got, str) and got.startswith('ERR:'), s
        else:
            assert got == want, (s, got, want)
            ok2 += 1
    assert ok2 > 300


def test_parse_agrees_with_stdlib_email_for_safe_inputs():
    rnd = random.Random(2045)
    safe = [c for c in TOKCH if c not in "*'%"]
    n = 0
    for _ in range(300):
        typ = ''.join(rnd.choice(safe) for _ in range(rnd.randint(1, 8)))
        sub = ''.join(rnd.choice(safe) for _ in range(rnd.randint(1, 8)))
        params = []
        for _ in range(rnd.randint(0, 4)):
            attr = ''.join(rnd.choice(safe) for _ in range(rnd.randint(1, 6)))
            if rnd.random() < 0.5:
                val = ''.join(rnd.choice(safe) for _ in range(rnd.randint(1, 8)))
                txt = val
            else:
                val = ''.join(rnd.choice('abc;=/@,.') for _ in range(rnd.randint(1, 8)))
                txt = '"' + val + '"'
            params.append((attr, val, txt))
        field = typ + '/' + sub + ''.join('; ' + a + '=' + t for a, v, t in params)
        got = m.parse_content_type(field)
        msg = Message()
        msg['Content-Type'] = field
        sp = msg.get_params()
        assert sp[0][0].lower() == typ.lower() + '/' + sub.lower(), field
        assert [(k.lower(), v) for k, v in sp[1:]] == [(a.lower(), v) for a, v, t in params], field
        assert got == (typ.lower(), sub.lower(), tuple((a.lower(), v) for a, v, t in params)), field
        n += 1
    assert n == 300


def test_format_content_type_vectors_errors_and_roundtrip():
    F = m.format_content_type
    assert F('text', 'plain', ()) == 'text/plain' and F('text', 'plain', []) == 'text/plain'
    assert F('text', 'plain', (('charset', 'us-ascii'),)) == 'text/plain; charset=us-ascii'
    assert F('Text', 'Plain', [('A', 'b c'), ('d', ''), ('e', 'x"y\\z'), ('f', 'a;b'), ('g', 'a\tb')]) == 'Text/Plain; A="b c"; d=""; e="x\\"y\\\\z"; f="a;b"; g="a\tb"'
    assert F('a', 'b', (('c', '"'),)) == 'a/b; c="\\""' and F('a', 'b', (('c', '\\'),)) == 'a/b; c="\\\\"'
    assert F('a' * 255, 'b' * 255, ()) == 'a' * 255 + '/' + 'b' * 255
    assert F('a', 'b', (('c' * 255, 'd' * 1024),)) == 'a/b; ' + 'c' * 255 + '=' + 'd' * 1024
    assert F('a', 'b', (('c', 'd'),) * 32) == 'a/b' + '; c=d' * 32
    err('format_content_type', 'params-length', 'a', 'b', (('c', 'd'),) * 33)
    err('format_content_type', 'type-length', 'a' * 256, 'b', ())
    err('format_content_type', 'subtype-length', 'a', 'b' * 256, ())
    err('format_content_type', 'attribute-length', 'a', 'b', (('c' * 256, 'd'),))
    err('format_content_type', 'value-length', 'a', 'b', (('c', 'd' * 1025),))
    for bad in (None, b'a', 5, SubStr('a'), ['a']):
        err('format_content_type', 'type-type', bad, 'b', ())
        err('format_content_type', 'subtype-type', 'a', bad, ())
    for bad in ('', 'a b', 'a/b', 'a;', '\u00e9', 'a=', '"a"', '(a)'):
        err('format_content_type', 'type-invalid', bad, 'b', ())
        err('format_content_type', 'subtype-invalid', 'a', bad, ())
        err('format_content_type', 'attribute-invalid', 'a', 'b', (('c', 'd'), ('e', 'f'), ('g', 'h'), (bad, 'x')))
    for bad in (None, 'a', {('c', 'd')}, 5, SubTuple((('c', 'd'),))):
        err('format_content_type', 'params-type', 'a', 'b', bad)
    err('format_content_type', 'type-type', None, None, None)
    err('format_content_type', 'type-length', 'a' * 256, None, None)
    err('format_content_type', 'type-invalid', '', None, None)
    err('format_content_type', 'subtype-type', 'a', None, None)
    err('format_content_type', 'subtype-length', 'a', 'b' * 256, None)
    err('format_content_type', 'subtype-invalid', 'a', '', None)
    err('format_content_type', 'params-type', 'a', 'b', None)
    err('format_content_type', 'params-length', 'a', 'b', [None] * 33)
    for pos in range(0, 4):
        pre = [('c', 'd')] * pos
        err('format_content_type', 'item-type', 'a', 'b', pre + [['c', 'd']])
        err('format_content_type', 'item-type', 'a', 'b', pre + [None])
        err('format_content_type', 'item-type', 'a', 'b', pre + [SubTuple(('c', 'd'))])
        err('format_content_type', 'item-length', 'a', 'b', pre + [('c',)])
        err('format_content_type', 'item-length', 'a', 'b', pre + [('c', 'd', 'e')])
        err('format_content_type', 'attribute-type', 'a', 'b', pre + [(None, 'd')])
        err('format_content_type', 'attribute-type', 'a', 'b', pre + [(SubStr('c'), 'd')])
        err('format_content_type', 'attribute-length', 'a', 'b', pre + [('c' * 256, 'd')])
        err('format_content_type', 'attribute-invalid', 'a', 'b', pre + [('', 'd')])
        err('format_content_type', 'value-type', 'a', 'b', pre + [('c', None)])
        err('format_content_type', 'value-type', 'a', 'b', pre + [('c', SubStr('d'))])
        err('format_content_type', 'value-length', 'a', 'b', pre + [('c', 'd' * 1025)])
        for bad in ('\n', '\r', '\x00', '\x7f', '\x1f', '\u00e9', 'a\u0131', 'a\nb'):
            err('format_content_type', 'value-invalid', 'a', 'b', pre + [('c', bad)])
        err('format_content_type', 'item-type', 'a', 'b', pre + [None, (None, 'd')])
        err('format_content_type', 'item-length', 'a', 'b', pre + [('c',), (None, 'd')])
        err('format_content_type', 'attribute-type', 'a', 'b', pre + [(None, None)])
        err('format_content_type', 'attribute-length', 'a', 'b', pre + [('c' * 256, None)])
        err('format_content_type', 'attribute-invalid', 'a', 'b', pre + [('', None)])
        err('format_content_type', 'value-type', 'a', 'b', pre + [('c', None), ('c', '\n')])
        err('format_content_type', 'value-length', 'a', 'b', pre + [('c', 'd' * 1025 + '\n')])
    for c in range(0, 256):
        ch = chr(c)
        good = 32 <= c <= 126 or c == 9
        r = run('format_content_type', 'a', 'b', (('c', 'x' + ch + 'y'),))
        if good:
            assert r.startswith('a/b; c='), c
            assert m.parse_content_type(r)[2] == (('c', 'x' + ch + 'y'),), c
        else:
            assert r == 'ERR:value-invalid', c
    rnd = random.Random(31204)
    valch = [chr(c) for c in range(32, 127)] + ['\t']
    for _ in range(500):
        typ = ''.join(rnd.choice(TOKCH) for _ in range(rnd.randint(1, 10)))
        sub = ''.join(rnd.choice(TOKCH) for _ in range(rnd.randint(1, 10)))
        params = tuple((''.join(rnd.choice(TOKCH) for _ in range(rnd.randint(1, 6))), ''.join(rnd.choice(valch) for _ in range(rnd.randint(0, 12)))) for _ in range(rnd.randint(0, 5)))
        out = F(typ, sub, params)
        assert out == o_format(typ, sub, params), (typ, sub, params)
        assert m.parse_content_type(out) == (typ.lower(), sub.lower(), tuple((a.lower(), v) for a, v in params)), out
    worst = F('a' * 255, 'b' * 255, (('c' * 255, '"' * 1024),) * 32)
    assert len(worst) < 131072 and m.parse_content_type(worst)[2] == (('c' * 255, '"' * 1024),) * 32


def _cmp_parse(s):
    want = o_parse(s)
    got = run('parse_content_type', s)
    if want is None:
        assert isinstance(got, str) and got.startswith('ERR:'), repr(s)
    else:
        assert got == want, (repr(s), got, want)


def test_strip_and_skip_charsets_every_char():
    assert m.parse_encoding('Z8bitZ') == ('z8bitz', 'extension')
    assert m.parse_encoding('Z7bitZ\t') == ('z7bitz', 'extension')
    for c in range(0, 256):
        ch = chr(c)
        ws = ch in ' \t'
        tok = 33 <= c <= 126 and ch not in TSP
        for text in (ch + 'base64' + ch, ch + 'base64', 'base64' + ch, ' ' + ch + 'base64' + ch + ' '):
            r = run('parse_encoding', text)
            core = text.strip(' \t')
            if all(33 <= ord(x) <= 126 and x not in TSP for x in core) and core:
                low = core.lower()
                kind = low if low in m.MECHANISMS else ('x-token' if low.startswith('x-') and len(low) > 2 else 'extension')
                assert r == (low, kind), (repr(text), r)
            else:
                assert r == 'ERR:mechanism-invalid', (repr(text), r)
        for text in (ch + 'a/b' + ch, ch + 'a/b', 'a/b' + ch, 'a/b;' + ch + 'a=b', 'a/b' + ch + ';a=b', 'a/b;a=b' + ch, 'a/b;a=' + ch + 'b', 'a/b;' + ch + ch + 'a=b', 'a/b; a=b ;' + ch + 'c=d' + ch):
            _cmp_parse(text)
        if tok:
            assert m.parse_content_type(ch + 'a/b' + ch)[:2] == ((ch + 'a').lower(), ('b' + ch).lower())
        if ws:
            assert m.parse_content_type(ch + 'a/b' + ch) == ('a', 'b', ())


def test_check_order_pairs_and_param_positions():
    P = 'parse_content_type'
    err(P, 'text-type', SubStr('a' * 300000))
    err(P, 'text-length', 'a' * 131073)
    err(P, 'text-length', '\x01' * 131073)
    err(P, 'char-invalid', ';\x01')
    err(P, 'char-invalid', '\x01/')
    err(P, 'char-invalid', 'a/b;;\x7f')
    err(P, 'type-invalid', ';')
    err(P, 'subtype-missing', 'ab')
    err(P, 'slash-expected', 'ab;/')
    err(P, 'subtype-invalid', 'ab/;x')
    for pos in range(0, 4):
        pre = 'a/b' + ';c=d' * pos
        err(P, 'separator-expected', pre + ' x')
        err(P, 'param-empty', pre + ';')
        err(P, 'attribute-invalid', pre + ';=')
        err(P, 'equals-expected', pre + ';c')
        err(P, 'value-invalid', pre + ';c=')
        err(P, 'quote-unterminated', pre + ';c="')
        err(P, 'attribute-invalid', pre + ';=;')
        err(P, 'equals-expected', pre + ';c;=')
        err(P, 'value-invalid', pre + ';c=;"')
        assert m.parse_content_type(pre + ';e=f')[2] == (('c', 'd'),) * pos + (('e', 'f'),)
    err(P, 'params-length', 'a/b' + ';a=b' * 32 + ';;')
    err(P, 'params-length', 'a/b' + ';a=b' * 32 + ';"')
    err(P, 'param-empty', 'a/b' + ';a=b' * 32 + '; ')
    assert len(m.parse_content_type('a/b' + ';a=b' * 32)[2]) == 32


def _no_import_hook(*a, **k):
    raise AssertionError('import during call: %r' % (a[:1],))


CASES = []


def _run_everything():
    texts = ['', 'a', 'a b', 'text/plain', 'x-y', 'X-', 'TEXT', 'Message', 'a' * 256, None, SubStr('a'), ' base64 ', '7BIT', 'x-uu', 'ietf', '"a"', 'a;', '\u00e9', 'a/b; c=d', 'a/b; c="d\\"e"', 'a/b; c="d', 'a/b; c=d;', 'a/b; c', 'a/b; c=', 'a/b; ;', 'a/b' + ';a=b' * 40, 'a/b; c="\\', 'a' * 131073, 'a/b c', 'a b/c', 'text', '/b', 'a/', 'a/b@', 'a/b\n', 'a/b; c=d e', ' a/b ; c = d ', 'a/b; c="\\q"', 'a/b; c="x" ; d=y', 'a/b' + ';a=b' * 32]
    for text in texts:
        for fn in (m.is_token, m.classify_type, m.parse_content_type, m.parse_encoding):
            try:
                fn(text)
            except ValueError:
                pass
    plist = [(), [], (('c', 'd'),), [('c', 'd e'), ('f', ''), ('g', 'x"y\\z')], (('c', 'd'),) * 33, None, 'x', [None], [('c',)], [('c', 'd', 'e')], [(None, 'd')], [('c' * 256, 'd')], [('', 'd')], [('c', None)], [('c', 'd' * 1025)], [('c', '\n')], [['c', 'd']]]
    for typ in ('a', 'text', '', None, 'a b', 'a' * 256, SubStr('a')):
        for sub in ('b', '', None, 'b c', 'b' * 256):
            for params in plist:
                try:
                    m.format_content_type(typ, sub, params)
                except ValueError:
                    pass


def _load(name='fresh_1204'):
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
        if globals is not None and globals.get('__name__') == 'fresh_1204':
            log.append((name, tuple(fromlist or ()), level))
        return real(name, globals, locals, fromlist, level)

    calls = []
    real_fs = importlib.util.find_spec
    importlib.util.find_spec = fs if fs is not None else (lambda n, *a, **k: calls.append(n) or real_fs(n, *a, **k))
    builtins.__import__ = spy
    try:
        mod = _load()
    finally:
        builtins.__import__ = real
        importlib.util.find_spec = real_fs
    return mod, log, calls


def test_exact_import_log_and_find_spec_count_in_this_world():
    present = sys.modules.get(REG) is not None
    saved = sys.modules.pop(REG, None)
    try:
        mod, log, calls = _logged_load()
        assert log == [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]
        assert calls == [REG] and mod.make_fail is not None
        assert mod.make_fail('f').__name__ == 'fail'
        with pytest.raises(ValueError) as e:
            mod.make_fail('f')('c')
        assert str(e.value) == 'P235:f:c'
    finally:
        if saved is not None:
            sys.modules[REG] = saved
    if present:
        mod, log, calls = _logged_load()
        assert log == [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]
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
            mod.is_token(None)
        assert str(e.value) == 'P235:is_token:text-type'
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
            mod.is_token(1)
        assert str(e.value) == 'X:is_token:text-type'
    finally:
        if saved == 'absent':
            sys.modules.pop(REG, None)
        else:
            sys.modules[REG] = saved


def test_no_import_on_any_call_path():
    real = builtins.__import__
    builtins.__import__ = _no_import_hook
    try:
        _run_everything()
        assert m.parse_content_type('a/b; c="d"') == ('a', 'b', (('c', 'd'),))
        assert m.format_content_type('a', 'b', [('c', 'd e')]) == 'a/b; c="d e"'
    finally:
        builtins.__import__ = real


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
            lines.discard(fn.body[0].lineno) if isinstance(fn.body[0], ast.Expr) and isinstance(getattr(fn.body[0], 'value', None), ast.Constant) else None
            want[fn.name] = lines
    hit = set()
    real = builtins.__import__

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != MODPATH:
            return None
        if event == 'line':
            hit.add((frame.f_code.co_name, frame.f_lineno))
            if frame.f_code.co_name in want and frame.f_code.co_name != '<module>' and False:
                pass
        return tracer

    builtins.__import__ = _no_import_hook
    sys.settrace(tracer)
    try:
        _run_everything()
        m.parse_content_type('a/b; c="d\\"e"; f=g')
        m.format_content_type('a', 'b', [('c', 'd e')])
    finally:
        sys.settrace(None)
        builtins.__import__ = real
    missing = []
    for name, lines in want.items():
        for ln in sorted(lines):
            if (name, ln) not in hit:
                missing.append((name, ln))
    assert missing == []
    assert set(want) == {'_tok', '_is_token', 'is_token', '_kind', 'classify_type', '_skip', '_run', '_parse', 'parse_content_type', 'parse_encoding', '_quote', 'format_content_type'}


STATIC_CODES = {'is_token': ['text-type', 'text-length'], 'classify_type': ['text-type', 'text-length', 'not-token'], 'parse_content_type': ['text-type', 'text-length', '<code>'], 'parse_encoding': ['text-type', 'text-length', 'mechanism-invalid'], 'format_content_type': ['type-type', 'type-length', 'type-invalid', 'subtype-type', 'subtype-length', 'subtype-invalid', 'params-type', 'params-length', 'item-type', 'item-length', 'attribute-type', 'attribute-length', 'attribute-invalid', 'value-type', 'value-length', 'value-invalid']}
PARSE_RETURNS = ['char-invalid', 'type-invalid', 'subtype-missing', 'slash-expected', 'subtype-invalid', 'separator-expected', 'param-empty', 'params-length', 'attribute-invalid', 'equals-expected', 'quote-unterminated', 'value-invalid']


def test_ast_every_f_site_and_parse_return_codes():
    import ast
    with open(MODPATH) as fh:
        tree = ast.parse(fh.read())
    got = {}
    rets = []
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef):
            sites = []
            for n in ast.walk(fn):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'f':
                    a = n.args[0]
                    sites.append(a.value if isinstance(a, ast.Constant) else '<' + ast.unparse(a) + '>')
            if sites:
                got[fn.name] = sites
            if fn.name == '_parse':
                for n in ast.walk(fn):
                    if isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple) and isinstance(n.value.elts[0], ast.Constant) and n.value.elts[0].value is not None:
                        rets.append((n.lineno, n.value.elts[0].value))
    assert got == STATIC_CODES
    assert [c for _, c in sorted(rets)] == PARSE_RETURNS
    fs = [n for fn in tree.body if isinstance(fn, ast.FunctionDef) for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'f']
    assert len(fs) == sum(len(v) for v in STATIC_CODES.values()) == 27


def test_cap_before_work_tracemalloc_pins():
    import tracemalloc
    n = 2000000
    big = 'a' * n
    cases = (('is_token', (big,), 'text-length'), ('classify_type', (big,), 'text-length'), ('parse_encoding', (big,), 'text-length'), ('parse_content_type', (big,), 'text-length'), ('parse_content_type', ('\u00e9' * n,), 'text-length'), ('format_content_type', (big, 'b', ()), 'type-length'), ('format_content_type', ('a', big, ()), 'subtype-length'), ('format_content_type', ('a', 'b', [('c', 'd')] * n), 'params-length'), ('format_content_type', ('a', 'b', [(big, 'd')]), 'attribute-length'), ('format_content_type', ('a', 'b', [('c', big)]), 'value-length'))
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


DOC = 'b1204 RFC 2045 section 5.1 Content-Type and section 6.1 Content-Transfer-Encoding field values.\n\nSource: RFC 2045 (Freed and Borenstein, November 1996), section 5.1 (Syntax of\nthe Content-Type Header Field) and section 6.1 (Content-Transfer-Encoding\nSyntax). Only the field VALUE is handled, never the field name. The RFC says:\n"Note also that a subtype specification is MANDATORY -- it may not be omitted\nfrom a Content-Type header field." and "The type, subtype, and parameter names\nare not case sensitive." and, for the encoding, "These values are not case\nsensitive -- Base64 and BASE64 and bAsE64 are all equivalent."\nGrammar implemented (ABNF fragments in single quotes): value is type \'/\'\nsubtype *( \';\' attribute \'=\' value ); a token is one or more US-ASCII\ncharacters except space, control characters and the tspecials; a value is a\ntoken or a quoted-string; a mechanism is one of the five named values or an\nextension token.\nErratum 512 (Verified, Editorial, section 5.1) is APPLIED: the tspecials\nlisting lacks the alternative separator after the quote character, so all 15\nlisted characters are members and TSPECIALS has 15 members. Other errata on\nRFC 2045 are read and NOT applied: 2586 (Verified, Technical, section 1, about\nwhich fields may carry comments; this module refuses comments as an OURS\nchoice, so it is not applied), 3950 (Rejected, Technical, section 4), 3442\n(Held for Document Update, Editorial, section 8), and 7120 (Verified,\nEditorial, section 2.4); none changes the section 5.1 or 6.1 rules.\nFive errata exist for RFC 2045 in the errata data used.\nOURS design choices (not sourced from the RFC): white space (space or tab) is\naccepted only around the whole value and around each semicolon; comments and\nline folding are refused; non-ASCII text and control characters other than tab\nare refused; a backslash inside a quoted-string quotes the next character; the\ncaps TOKEN_MAX 255, TEXT_MAX 131072, VALUE_MAX 1024 and PARAMS_MAX 32; the\ncheck order and the error codes. SOURCED: the token and tspecials rules, the\ncase-insensitive type, subtype, attribute and mechanism, the five mechanism\nnames, the x-token form, and the mandatory subtype.\nOURS scope note: RFC 6838 (media type names and registration), RFC 2046 and\nRFC 7578 are ADJACENT; this module imports none of them, owns pure code, and\nmakes no registration claim.\nErrors raise ValueError P235:<name>:<code>.\n'


def test_whole_module_docstring_literal_and_ascii():
    assert m.__doc__ == DOC
    for p in (MODPATH, __file__):
        with open(p, 'rb') as fh:
            assert fh.read().isascii()
    assert '\\' not in m.__doc__
    assert 'Erratum 512 (Verified, Editorial, section 5.1) is APPLIED' in m.__doc__
    assert 'OURS' in m.__doc__ and 'SOURCED' in m.__doc__
