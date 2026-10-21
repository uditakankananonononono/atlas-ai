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
        p235_concepts_batch1216_jwt_claims as mod)
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


PJ = 'jwt_claims_parse'


def _success_corpus():
    S = []
    # the empty claims set
    S.append((PJ, ('{}',)))
    S.append((PJ, (' { } \t',)))
    # the s3.1 example claims set
    S.append((PJ, ('{"iss":"joe","exp":1300819380,'
                   '"http://example.com/is_root":true}',)))
    # all seven registered claims together
    S.append((PJ, ('{"iss":"me","sub":"you","aud":["a","b:c"],'
                   '"exp":100,"nbf":1.5,"iat":0,"jti":"id-1"}',)))
    # aud as a single string, and an empty aud array
    S.append((PJ, ('{"aud":"one"}',)))
    S.append((PJ, ('{"aud":[]}',)))
    # NumericDate: fractional, zero, negative
    S.append((PJ, ('{"exp":1.5}',)))
    S.append((PJ, ('{"nbf":0}',)))
    S.append((PJ, ('{"iat":-100}',)))
    # private claims: any JSON values; "ISS" is not "iss"
    S.append((PJ, ('{"ISS":5,"x":{"y":[1,2.5,null,true,false]},'
                   '"z":"text"}',)))
    # an object nested inside an array
    S.append((PJ, ('{"a":[{"b":1,"c":2},3]}',)))
    # signed exponents, both signs and none
    S.append((PJ, ('{"a":1e+5,"b":1E-3,"c":2e0}',)))
    # BMP characters just outside the surrogate range
    S.append((PJ, ('{"a":"\\uD7FF\\uE000"}',)))
    # surrogate-pair boundary pairs
    S.append((PJ, ('{"a":"\\uD800\\uDC00","b":"\\uDBFF\\uDFFF"}',)))
    # nesting exactly at the depth cap accepts
    S.append((PJ, ('{"a":' + '[' * 14 + '1' + ']' * 14 + '}',)))
    # URI boundary characters: ~ and ! are valid
    S.append((PJ, ('{"iss":"x:~!"}',)))
    # U+00A0 sits just above the refused C1 range
    S.append((PJ, ('{"iss":"x:' + chr(0xA0) + '"}',)))
    # duplicate names are allowed inside nested objects
    S.append((PJ, ('{"a":{"b":1,"b":2}}',)))
    # every two-character escape, \u escapes, a surrogate pair
    S.append((PJ, ('{"s":"a\\"b\\\\c\\/d\\be\\ff\\ng\\rh\\ti"}',)))
    S.append((PJ, ('{"s":"\\u0041\\u00e9"}',)))
    S.append((PJ, ('{"s":"\\uD834\\uDD1E"}',)))
    # JSON whitespace between every token
    S.append((PJ, ('\t {\r\n "a" \t:\r [ 1 , null ]\n } ',)))
    # numbers: exponent forms, big integers, negative zero
    S.append((PJ, ('{"n":-0.5e2,"m":1E+10,"k":-0,"b":'
                   '123456789012345678901234567890}',)))
    # caps: string, members, elements, depth exactly at the caps
    S.append((PJ, ('{"s":"' + 'x' * 8192 + '"}',)))
    S.append((PJ, ('{' + ','.join('"k%03d":%d' % (k, k)
                                  for k in range(256)) + '}',)))
    S.append((PJ, ('{"a":[' + ','.join('1' * 1
                                        for _ in range(4096)) + ']}',)))
    deep = '{"a":' * 15 + '1' + '}' * 15
    S.append((PJ, (deep,)))
    # a URI-form StringOrURI with every scheme character
    S.append((PJ, ('{"iss":"aA0+-.://host/path?q=1#f"}',)))
    return S


def _refusal_corpus():
    C = []
    # exact type first (subclasses and bool included)
    for v in (5, None, True, [], {}, b'{}', 0.0,
              _StrSub('{}')):
        C.append((PJ, 'bad_type:value', v))
    # the overall length cap
    C.append((PJ, 'bad_value:input.length',
              '{' + ' ' * 262144 + '}'))
    # the top-level value must be an object
    for v in ('', ' ', '[1]', '[]', '"x"', '5', 'true', 'null',
              ' [ 1 ] '):
        C.append((PJ, 'bad_value:claims.shape', v))
    # structural errors
    for v in ('{', '{"a"', '{"a":', '{"a":1', '{"a":1,}', '{,}',
              '{"a" 1}', '{"a":1 "b":2}', '{]', '{1:2}', '{"a":}',
              '{"a":1;', '{"a":q}', '{"a":y}', '{"a":1,',
              '{"a":[1;', '{"a":[1,', '{"a":1x}'):
        C.append((PJ, 'bad_value:json.structure', v))
    # literals are exact and lowercase
    for v in ('{"a":tru}', '{"a":nul}', '{"a":tru e}',
              '{"a":fals}'):
        C.append((PJ, 'bad_value:json.literal', v))
    # a wrong-case literal start is not even a literal
    C.append((PJ, 'bad_value:json.structure', '{"a":True}'))
    C.append((PJ, 'bad_value:json.structure', '{"a":FALSE}'))
    # an array item followed by anything but "," or "]" refuses,
    # even a character that would start a value
    for v in ('{"a":[1 2]}', '{"a":[1 {}]}', '{"a":[1 true]}',
              '{"a":[1 "x"]}', '{"a":[1 []}'):
        C.append((PJ, 'bad_value:json.structure', v))
    # a comma where the colon belongs cannot slip through: the
    # colon check must fire before the value scan
    for v in ('{"a" ,5}', '{"a" , "x"}', '{"a" true}'):
        C.append((PJ, 'bad_value:json.structure', v))
    # a number whose digits run to the end of the input still
    # refuses structurally, never with an index crash
    for v in ('{"a":0', '{"a":12', '{"a":1.5', '{"a":1e2'):
        C.append((PJ, 'bad_value:json.structure', v))
    # an exponent truncated right after the letter refuses as a
    # number error, never with an index crash on the sign check
    for v in ('{"a":1e', '{"a":1E', '{"a":1e+'):
        C.append((PJ, 'bad_value:json.number', v))
    # a high surrogate whose second escape is truncated refuses
    # as a surrogate error, not a generic string error
    # the last high surrogate still requires its pair
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uDBFFx'))
    # a high surrogate followed by enough non-escape characters
    # still refuses as a surrogate error
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uD800xxxx"}'))
    # the low end of the low-surrogate range
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uD800\\uDBFF"'))
    # a second escape one hex digit short refuses as a surrogate
    # error even though a string error sits just behind it
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uD800\\uDC0'))
    # each operand of the pair lookahead in isolation: a
    # non-backslash after the high surrogate (A40 survivor: the
    # or->and flip accepts this), a backslash followed by a
    # non-"u", and the too-short tail
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uD800auDC00"'))
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uD800buDC00"'))
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uD800\\xDC00"'))
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uD800\\tDC00"'))
    # a low surrogate first never starts a pair
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uDC00\\uDC00"}'))
    # nesting past the depth cap refuses
    C.append((PJ, 'bad_value:json.depth',
              '{"a":' + '[' * 15 + '1' + ']' * 15 + '}'))
    # C1 controls and DEL in a StringOrURI URI refuse
    for ch in (chr(0x7F), chr(0x9E), chr(0x9F)):
        C.append((PJ, 'bad_value:iss.uri', '{"iss":"x:' + ch + '"}'))
    # a lone low surrogate refuses
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uDC00"}'))
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uDFFF"}'))
    # a pair whose second half is above the low-surrogate range
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uD800\\uE000"'))
    # a complete pair with the string left open refuses as a
    # string error, not a surrogate error
    C.append((PJ, 'bad_value:json.string', '{"a":"\\uD800\\uDC00'))
    # an array opened and left empty at the end of the input
    # refuses structurally, never with an index crash
    C.append((PJ, 'bad_value:json.structure', '{"a":['))
    C.append((PJ, 'bad_value:json.structure', '{"a":[ '))
    # a number truncated after the sign or the point refuses as
    # a number error, never with an index crash
    C.append((PJ, 'bad_value:json.number', '{"a":-'))
    C.append((PJ, 'bad_value:json.number', '{"a":1.'))
    # a raw control character at the 0x20 boundary refuses
    C.append((PJ, 'bad_value:json.string', '{"a":"x' + chr(31) + '"}'))
    C.append((PJ, 'bad_value:json.string', '{"a":"' + chr(0) + '"}'))
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uD800\\u0'))
    C.append((PJ, 'bad_value:json.surrogate', '{"a":"\\uD800\\'))
    # a literal followed by more characters refuses structurally
    C.append((PJ, 'bad_value:json.structure', '{"a":nullx}'))
    C.append((PJ, 'bad_value:json.structure', '{"a":truex}'))
    # strings: unterminated, raw control chars, bad escapes
    for v in ('{"a', '{"s":"x', '{"s":"a\nb"}', '{"s":"a\tb"}',
              '{"s":"\\q"}', '{"s":"\\', '{"s":"abc\\"',
              '{"s":"\\u12"}', '{"s":"\\u12xz"}', '{"s":"\\uXYZW"}'):
        C.append((PJ, 'bad_value:json.string', v))
    # surrogates: lone high, lone low, high then non-escape, high
    # then bad hex, high then another high
    for v in ('{"s":"\\uD800"}', '{"s":"\\uDC00"}',
              '{"s":"\\uD800x"}', '{"s":"\\uD800\\n"}',
              '{"s":"\\uD800\\u12xz"}',
              '{"s":"\\uD800\\uD800"}', '{"s":"\\uD834\\u0041"}'):
        code = ('bad_value:json.string'
                if v == '{"s":"\\uD800\\u12xz"}'
                else 'bad_value:json.surrogate')
        C.append((PJ, code, v))
    # numbers: leading zeros, missing digits, overflow
    for v in ('{"a":01}', '{"a":-}', '{"a":-x}', '{"a":1.}',
              '{"a":1e}', '{"a":1e+}', '{"a":1e999}',
              '{"a":-1e999}', '{"a":[00]}'):
        C.append((PJ, 'bad_value:json.number', v))
    # a leading "." does not even start a JSON number
    C.append((PJ, 'bad_value:json.structure', '{"a":.5}'))
    # the \u escape truncated at the end of the input, and an
    # array cut off right after a value
    C.append((PJ, 'bad_value:json.string', '{"s":"\\u12'))
    C.append((PJ, 'bad_value:json.structure', '{"a":[1'))
    # trailing content
    for v in ('{}x', '{} {}', '{"a":1},', '{"a":1}]'):
        C.append((PJ, 'bad_value:json.trailing', v))
    # caps: depth, string length, members, elements
    C.append((PJ, 'bad_value:json.depth',
              '{"a":' * 16 + '1' + '}' * 16))
    C.append((PJ, 'bad_value:json.depth',
              '{"a":' + '[' * 17 + ']' * 17 + '}'))
    C.append((PJ, 'bad_value:json.string.length',
              '{"s":"' + 'x' * 8193 + '"}'))
    C.append((PJ, 'bad_value:json.members',
              '{' + ','.join('"k%03d":%d' % (k, k)
                             for k in range(257)) + '}'))
    C.append((PJ, 'bad_value:json.elements',
              '{"a":[' + ','.join('1' for _ in range(4097)) + ']}'))
    # duplicate Claim Names (lexically-last is not used: OURS)
    C.append((PJ, 'bad_value:claim.dup', '{"a":1,"a":2}'))
    C.append((PJ, 'bad_value:claim.dup', '{"a":1,"b":1,"a":2}'))
    # iss / sub: StringOrURI
    for v in ('{"iss":5}', '{"iss":true}', '{"iss":[]}',
              '{"iss":{}}', '{"iss":null}'):
        C.append((PJ, 'bad_value:iss.type', v))
    C.append((PJ, 'bad_value:sub.type', '{"sub":5}'))
    for v in ('{"iss":"1abc:x"}', '{"iss":":x"}',
              '{"iss":"a b:x"}', '{"iss":"aé:x"}',
              '{"iss":"ab:x y"}', '{"iss":"ab:x\\u0001y"}',
              '{"iss":"ab:x' + chr(0x7F) + 'y"}'):
        C.append((PJ, 'bad_value:iss.uri', v))
    C.append((PJ, 'bad_value:sub.uri', '{"sub":"1abc:x"}'))
    # aud: string or array of strings
    for v in ('{"aud":5}', '{"aud":{}}', '{"aud":true}',
              '{"aud":[1]}', '{"aud":["a",2]}', '{"aud":[null]}'):
        C.append((PJ, 'bad_value:aud.type', v))
    C.append((PJ, 'bad_value:aud.uri', '{"aud":"1abc:x"}'))
    C.append((PJ, 'bad_value:aud.uri', '{"aud":["ok","1abc:x"]}'))
    # exp / nbf / iat: NumericDate (a number; bool is not a number)
    for name in ('exp', 'nbf', 'iat'):
        for v in ('"%s"' % name,):
            C.append((PJ, 'bad_value:%s.type' % name,
                      '{"%s":"100"}' % name))
            C.append((PJ, 'bad_value:%s.type' % name,
                      '{"%s":true}' % name))
            C.append((PJ, 'bad_value:%s.type' % name,
                      '{"%s":[]}' % name))
            C.append((PJ, 'bad_value:%s.type' % name,
                      '{"%s":null}' % name))
    # jti: a case-sensitive string
    for v in ('{"jti":5}', '{"jti":true}', '{"jti":[]}',
              '{"jti":null}'):
        C.append((PJ, 'bad_value:jti.type', v))
    return C


def _bounded_parse(s, bound=1.0):
    'Run jwt_claims_parse under a hard real-time bound; AssertionError on overrun.'
    if not hasattr(signal, 'setitimer') or not hasattr(signal, 'SIGALRM'):
        return m.jwt_claims_parse(s)
    def stop(*a):
        raise AssertionError(
            'parse exceeded 1.0s bound: a scan loop did not advance')
    old = signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, bound)
    try:
        return m.jwt_claims_parse(s)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def test_loops_advance_under_time_bound():
    # Allocation/spin hang guard: a mutant that stops advancing in
    # any scan loop (ws, string, number, object, array, URI) must
    # die by assertion, never by timeout or MemoryError.
    doc = '{' + ','.join('"k%03d":%d' % (k, k) for k in range(256)) + '}'
    r = _bounded_parse(doc)
    assert len(r['claims']) == 256
    r = _bounded_parse('{"s":"' + 'x' * 8192 + '"}')
    assert r['claims'][0][1] == 'x' * 8192
    r = _bounded_parse('{"a":[' + ','.join('1' for _ in range(4096))
                       + ']}')
    assert len(r['claims'][0][1]) == 4096
    r = _bounded_parse('{"iss":"aA0+-.://' + 'h' * 2000 + '"}')
    assert r['iss'].startswith('aA0+-.://')
    r = _bounded_parse(' \t\r\n' * 500 + '{}')
    assert r['claims'] == []


__DOC__ = 'RFC 7519 "JSON Web Token (JWT)": the JWT Claims Set (s4)\nover a Python text string holding the JSON Claims Set: parse\nand validation of the registered claim rules (s4.1), claim\nname uniqueness (s4), and the StringOrURI and NumericDate\ntypes (s2).  The JWS/JWE envelope (s7.2) is out of scope.\n\nPublic API:\n\n  jwt_claims_parse(text) -> a dict:\n      \'iss\', \'sub\', \'jti\': the claim string value, or None\n      when the claim is absent,\n      \'aud\': the claim string, or the list of strings, or\n      None when absent (the one-string special case is kept\n      as a bare string),\n      \'exp\', \'nbf\', \'iat\': the claim number (int or\n      float), or None when absent,\n      \'claims\': every claim as (name, value) pairs in\n      document order, registered ones included.\n  jwt_claims_is_valid(text) -> True iff jwt_claims_parse\n      would succeed.\n\nGrammar notes (verified against the RFC 7519 text): the\nClaims Set is a JSON object (s4); Claim Names within it\nMUST be unique (s4).  StringOrURI (s2): a JSON string;\narbitrary strings MAY be used, but any value containing a\n":" character MUST be a URI (RFC 3986); compared\ncase-sensitively.  NumericDate (s2): a JSON numeric value,\nseconds since 1970-01-01T00:00:00Z UTC ignoring leap\nseconds; non-integer values can be represented.  s4.1:\n"iss" and "sub" are StringOrURI; "aud" is an array of\nStringOrURI in the general case and MAY be a single string\nwhen there is one audience; "exp", "nbf" and "iat" MUST be\nnumbers containing NumericDate values; "jti" is a\ncase-sensitive string.  All seven are OPTIONAL; claims not\nunderstood MUST be ignored (s4), so unregistered names\n(case-sensitive, so "ISS" is not "iss") pass as private\nclaims with any JSON value.\n\nErrata (8 records): Verified EID 8060 (s7.2 JOSE header\nvalidation step) and Verified EID 8388 (s13.2 POSIX.1\nreference URL, editorial) do not touch the validated\nclaims grammar: noted, not folded.  Reported EID 5906\n(s7.2 algorithm rejection), Reported EID 7720 (s4.1.6\nfuture "iat" handling), Reported EID 8225 (s7.2 base64url\ndecoding), Rejected EID 5648 (s1 pronunciation),\nRejected EID 6622 (s11 link) and Rejected EID 9212 (s4\nECMAScript section pointer) are noted, not folded.  In\nparticular, temporal acceptance (exp/nbf/iat versus the\ncurrent time) is application processing outside this\nunit: only the claim TYPES are validated.\n\nJSON parsing is strict RFC 7159: whitespace is SP, TAB,\nCR or LF only; strings allow the seven two-character\nescapes and \\uXXXX, with a high surrogate only as the\nfirst half of a pair; numbers forbid leading zeros and\nrequire digits around the fraction and exponent points;\ntrue/false/null are lowercase; a document is exactly one\nvalue.\n\nProfile decisions (OURS, not from the RFC text):\n  - Duplicate Claim Names are rejected (s4 permits either\n    rejection or a lexically-last parser).\n  - An empty "aud" array is accepted: the text does not\n    forbid it.\n  - The StringOrURI URI requirement is checked as: the\n    part before the first ":" must be a valid RFC 3986\n    scheme (ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )),\n    and the value must not contain SP, C0/C1 controls or\n    DEL; full RFC 3986 validation is out of scope.\n  - A NumericDate may be negative, zero or fractional\n    (the text does not bound it); it must be a finite\n    number, so a JSON number whose magnitude overflows a\n    float refuses (bad_value:json.number).\n  - Size caps (OURS): _MAX_INPUT_LENGTH characters\n    overall, _MAX_DEPTH nesting, _MAX_MEMBERS members per\n    object, _MAX_ELEMENTS items per array,\n    _MAX_STRING_LENGTH per string.\n\nRefusal order: bad_type before everything; the overall\nlength cap; the claims-set shape (the first non-whitespace\ncharacter must be \'{\'); then the JSON document as scanned\n(structural, string, number and literal codes by\nposition; the depth, string length, members and elements\ncaps as encountered); trailing content after the single\ntop-level value; duplicate Claim Names (after the whole\ndocument parses, so a syntax error anywhere refuses with\nits syntax code first); then per claim in document order:\nthe registered claim\'s type rule, then its URI rule.\n'


def test_module_docstring_is_pinned_whole():
    assert m.__doc__ == __DOC__


def test_rfc_section_3_example():
    # s3.1: the example claims set of the RFC
    r = m.jwt_claims_parse('{"iss":"joe","exp":1300819380,'
                           '"http://example.com/is_root":true}')
    assert r['iss'] == 'joe' and r['exp'] == 1300819380
    assert r['claims'] == [('iss', 'joe'), ('exp', 1300819380),
                           ('http://example.com/is_root', True)]


def test_return_values():
    r = m.jwt_claims_parse('{}')
    assert r == {'iss': None, 'sub': None, 'aud': None, 'exp': None,
                 'nbf': None, 'iat': None, 'jti': None, 'claims': []}
    r = m.jwt_claims_parse('{"aud":["a","b:c"],"nbf":1.5,"jti":"x"}')
    assert r['aud'] == ['a', 'b:c'] and r['nbf'] == 1.5
    assert r['jti'] == 'x' and r['iat'] is None
    # the one-string aud special case stays a bare string
    r = m.jwt_claims_parse('{"aud":"one"}')
    assert r['aud'] == 'one'
    # claims are in document order, registered ones included
    r = m.jwt_claims_parse('{"z":1,"exp":2,"a":3}')
    assert [k for k, v in r['claims']] == ['z', 'exp', 'a']


def test_json_grammar():
    # values of every JSON type in private claims
    r = m.jwt_claims_parse('{"i":-5,"f":2.5e3,"t":true,"u":false,'
                           '"n":null,"s":"x","a":[[1]],"o":{"p":0}}')
    d = dict(r['claims'])
    assert d['i'] == -5 and d['f'] == 2500.0 and d['t'] is True
    assert d['u'] is False and d['n'] is None and d['a'] == [[1]]
    assert d['o'] == {'p': 0}
    # -0 and 0 are equal ints; a huge integer keeps full precision
    r = m.jwt_claims_parse('{"a":-0,"b":123456789012345678901234567890}')
    assert dict(r['claims'])['b'] == 123456789012345678901234567890
    # a non-integer NumericDate
    r = m.jwt_claims_parse('{"exp":1300819380.25}')
    assert r['exp'] == 1300819380.25
    # unicode escapes decode; surrogate pairs combine
    r = m.jwt_claims_parse('{"s":"\\u0041\\uD834\\uDD1E"}')
    assert dict(r['claims'])['s'] == 'A\U0001D11E'
    # all four whitespace characters are accepted between tokens
    assert m.jwt_claims_is_valid('\r\n\t { "a" : 1 } ') is True
    # other "whitespace" is not JSON whitespace
    refuse(PJ, 'bad_value:claims.shape', '\x0b{}')
    refuse(PJ, 'bad_value:claims.shape', '\x0c{}')
    refuse(PJ, 'bad_value:claims.shape', '\xa0{}')
    refuse(PJ, 'bad_value:json.trailing', '{} \x0b')
    # A44 rev2 pins: whitespace before ']' and after ','
    assert m.jwt_claims_parse('{"a":[ ]}')['claims'] == [('a', [])]
    assert m.jwt_claims_parse('{"a":1, "b":2}')['claims'] == [('a', 1),
                                                              ('b', 2)]


def test_registered_claim_rules():
    # claim names are case-sensitive: ISS is a private claim
    r = m.jwt_claims_parse('{"ISS":5,"iss":"ok"}')
    assert r['iss'] == 'ok'
    # StringOrURI: a colon-free value is any string
    for v in ('{"iss":""}', '{"iss":"a b c"}', '{"sub":"x@y.z"}',
              '{"iss":"#frag"}', '{"iss":"?query"}'):
        assert m.jwt_claims_is_valid(v) is True, v
    # StringOrURI: a colon demands a URI (scheme shape OURS)
    for v in ('{"iss":"urn:x:y"}', '{"iss":"a+b-c.d://h"}',
              '{"iss":"a1://h"}'):
        assert m.jwt_claims_is_valid(v) is True, v
    # aud elements each follow StringOrURI
    assert m.jwt_claims_is_valid('{"aud":["urn:a","plain"]}') is True
    # exp/nbf/iat accept int and float, not bool
    assert m.jwt_claims_parse('{"exp":1}')['exp'] == 1
    assert m.jwt_claims_parse('{"exp":1.0}')['exp'] == 1.0
    refuse(PJ, 'bad_value:exp.type', '{"exp":true}')
    # jti keeps case
    assert m.jwt_claims_parse('{"jti":"AbC"}')['jti'] == 'AbC'
    # A44 rev2 pins: sub and iat assignment sites
    assert m.jwt_claims_parse('{"sub":"you"}')['sub'] == 'you'
    assert m.jwt_claims_parse('{"iat":0}')['iat'] == 0
    # A44 rev2 pin: the aud StringOrURI scheme guard
    refuse(PJ, 'bad_value:aud.uri', '{"aud":"1abc:z"}')
    # unknown claims with any value are ignored by the rules
    assert m.jwt_claims_is_valid('{"anything":[{},false]}') is True


def test_exact_refusal_codes():
    for fn, code, d in _refusal_corpus():
        refuse(fn, code, d)


def test_success_corpus():
    for fn, args in _success_corpus():
        getattr(m, fn)(*args)
        is_valid = getattr(m, fn.replace('_parse', '_is_valid'))
        r = is_valid(*args)
        assert r is True, args

    # an object nested inside an array becomes a dict value
    r = m.jwt_claims_parse('{"a":[{"b":1,"c":2},3]}')
    assert r['claims'] == [('a', [{'b': 1, 'c': 2}, 3])]

    # escape sequences land as their characters in the value
    r = m.jwt_claims_parse('{"a":"x\\ny","b":"\\u0041Z","c":"q\\"w"}')
    assert r['claims'] == [('a', 'x\ny'), ('b', 'AZ'), ('c', 'q"w')]
    r = m.jwt_claims_parse('{"a":"\\uD7FF\\uE000"}')
    assert r['claims'] == [('a', chr(0xD7FF) + chr(0xE000))]
    r = m.jwt_claims_parse(
        '{"a":"\\uD800\\uDC00","b":"\\uDBFF\\uDFFF"}')
    assert r['claims'] == [('a', chr(0x10000)), ('b', chr(0x10FFFF))]


def test_refusal_order():
    # type before everything
    refuse(PJ, 'bad_type:value', _StrSub('[1]'))
    refuse(PJ, 'bad_type:value', 5)
    # length before shape
    refuse(PJ, 'bad_value:input.length', '{' + ' ' * 262144 + '}')
    # the claims-set shape before any JSON scanning of the value
    refuse(PJ, 'bad_value:claims.shape', '[1')
    refuse(PJ, 'bad_value:claims.shape', ' "')
    # syntax before duplicates, duplicates before claim rules
    refuse(PJ, 'bad_value:json.structure', '{"a":1,"a":2,"b":}')
    refuse(PJ, 'bad_value:json.trailing', '{"a":1,"a":2}x')
    refuse(PJ, 'bad_value:claim.dup', '{"exp":"x","exp":"y"}')
    # claim rules in document order
    refuse(PJ, 'bad_value:jti.type', '{"jti":5,"iss":6}')
    refuse(PJ, 'bad_value:iss.type', '{"iss":6,"jti":5}')
    # the type rule before the URI rule
    refuse(PJ, 'bad_value:iss.type', '{"iss":["1abc:x"]}')
    refuse(PJ, 'bad_value:aud.type', '{"aud":[2,"1abc:x"]}')
    # the caps as encountered: depth fires before the structure
    # error of an empty nested value
    refuse(PJ, 'bad_value:json.depth', '{"a":' * 17)
    refuse(PJ, 'bad_value:json.members',
           '{' + ','.join('"k%03d":%d' % (k, k)
                          for k in range(257)) + '}')
    # A44 rev2 pins: non-literal start char and bad exponent digit run
    refuse(PJ, 'bad_value:json.structure', '{"a":r}')
    refuse(PJ, 'bad_value:json.number', '{"a":1ee5}')


def test_caps_boundary_acceptance():
    # exactly at the string cap accepted
    r = m.jwt_claims_parse('{"s":"' + 'x' * 8192 + '"}')
    assert dict(r['claims'])['s'] == 'x' * 8192
    refuse(PJ, 'bad_value:json.string.length',
           '{"s":"' + 'x' * 8193 + '"}')
    # exactly at the members cap accepted
    doc = '{' + ','.join('"k%03d":%d' % (k, k) for k in range(256)) + '}'
    assert len(m.jwt_claims_parse(doc)['claims']) == 256
    refuse(PJ, 'bad_value:json.members',
           '{' + ','.join('"k%03d":%d' % (k, k)
                          for k in range(257)) + '}')
    # exactly at the elements cap accepted
    doc = '{"a":[' + ','.join('1' for _ in range(4096)) + ']}'
    assert len(dict(m.jwt_claims_parse(doc)['claims'])['a']) == 4096
    # exactly at the depth cap accepted
    deep = '{"a":' * 15 + '1' + '}' * 15
    assert m.jwt_claims_is_valid(deep) is True
    refuse(PJ, 'bad_value:json.depth', '{"a":' * 16 + '1' + '}' * 16)
    # exactly at the input cap accepted (whitespace fills it: a
    # single string could not, the string cap is lower)
    doc = '{' + ' ' * (262144 - 2) + '}'
    assert len(doc) == 262144
    assert m.jwt_claims_is_valid(doc) is True
    refuse(PJ, 'bad_value:input.length', doc + ' ')


def test_is_valid_returns_exact_bool():
    r = m.jwt_claims_is_valid('{}')
    assert r is True and type(r) is bool
    for v in ('', '[1]', '{"a":1,"a":2}', '{"exp":true}',
              '{"iss":"1abc:x"}', '{"s":"\\uD800"}', 5, None, b'{}',
              '{"a":01}', '{}x', _StrSub('[1]')):
        r = m.jwt_claims_is_valid(v)
        assert r is False and type(r) is bool, (v,)


def test_constants_pinned_whole():
    assert m._MAX_INPUT_LENGTH == 262144
    assert m._MAX_DEPTH == 16
    assert m._MAX_MEMBERS == 256
    assert m._MAX_ELEMENTS == 4096
    assert m._MAX_STRING_LENGTH == 8192
    assert m._WS == frozenset(' \t\r\n')
    assert m._HEXDIG == frozenset('0123456789abcdefABCDEF')
    assert m._DIGIT == frozenset('0123456789')
    assert m._ALPHA == frozenset(
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
    assert m._SCHEME_CHAR == m._ALPHA | m._DIGIT | frozenset('+-.')
    assert m._ESCAPES == {'"': '"', '\\': '\\', '/': '/', 'b': '\b',
                          'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}


def test_function_docstrings_pinned_exact():
    assert m.jwt_claims_parse.__doc__ == (
        'Validate an RFC 7519 JWT Claims Set; return its claims.')
    assert m.jwt_claims_is_valid.__doc__ == (
        'True iff jwt_claims_parse(s) would succeed.')


def test_module_namespace_is_pinned():
    names = set(vars(m))
    assert names == {
        '__name__', '__doc__', '__package__', '__loader__',
        '__spec__', '__file__', '__cached__', '__builtins__',
        'find_spec', 'make_fail',
        '_MAX_INPUT_LENGTH', '_MAX_DEPTH', '_MAX_MEMBERS',
        '_MAX_ELEMENTS', '_MAX_STRING_LENGTH',
        '_WS', '_HEXDIG', '_DIGIT', '_ALPHA', '_SCHEME_CHAR',
        '_ESCAPES', '_skip_ws', '_parse_string', '_parse_number',
        '_parse_value', '_parse_object', '_parse_array',
        '_check_uri', '_check_stringoruri', '_Obj',
        'jwt_claims_parse', 'jwt_claims_is_valid'}


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
    f_lines, fname = _f_lines()
    hits = set()

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
                is_valid('not valid at all: ' + chr(0))
            finally:
                builtins.__import__ = real
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
    _b.__import__ = bogus_import
    _iu.find_spec = no_spec
    try:
        mod = types.ModuleType('fresh_b1216')
        with pytest.raises(ModuleNotFoundError):
            exec(compile(src, 'fresh_b1216', 'exec'), mod.__dict__)
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
            ('import no_such_dep_xyz_1216\n', 'ModuleNotFoundError'),
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
        mod = types.ModuleType('fresh_b1216_spy')
        exec(compile(src, 'fresh_b1216_spy', 'exec'), mod.__dict__)
    finally:
        builtins.__import__ = real_import
        _iu.find_spec = real_find_spec
    assert calls == [REG], calls
    # the fallback engaged and works
    assert mod.jwt_claims_is_valid('{}') is True
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        assert str(e) == 'P235:x:c'
    else:
        raise AssertionError('fallback make_fail did not raise')
