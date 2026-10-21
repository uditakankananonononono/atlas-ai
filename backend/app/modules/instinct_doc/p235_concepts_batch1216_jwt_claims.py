'''RFC 7519 "JSON Web Token (JWT)": the JWT Claims Set (s4)
over a Python text string holding the JSON Claims Set: parse
and validation of the registered claim rules (s4.1), claim
name uniqueness (s4), and the StringOrURI and NumericDate
types (s2).  The JWS/JWE envelope (s7.2) is out of scope.

Public API:

  jwt_claims_parse(text) -> a dict:
      'iss', 'sub', 'jti': the claim string value, or None
      when the claim is absent,
      'aud': the claim string, or the list of strings, or
      None when absent (the one-string special case is kept
      as a bare string),
      'exp', 'nbf', 'iat': the claim number (int or
      float), or None when absent,
      'claims': every claim as (name, value) pairs in
      document order, registered ones included.
  jwt_claims_is_valid(text) -> True iff jwt_claims_parse
      would succeed.

Grammar notes (verified against the RFC 7519 text): the
Claims Set is a JSON object (s4); Claim Names within it
MUST be unique (s4).  StringOrURI (s2): a JSON string;
arbitrary strings MAY be used, but any value containing a
":" character MUST be a URI (RFC 3986); compared
case-sensitively.  NumericDate (s2): a JSON numeric value,
seconds since 1970-01-01T00:00:00Z UTC ignoring leap
seconds; non-integer values can be represented.  s4.1:
"iss" and "sub" are StringOrURI; "aud" is an array of
StringOrURI in the general case and MAY be a single string
when there is one audience; "exp", "nbf" and "iat" MUST be
numbers containing NumericDate values; "jti" is a
case-sensitive string.  All seven are OPTIONAL; claims not
understood MUST be ignored (s4), so unregistered names
(case-sensitive, so "ISS" is not "iss") pass as private
claims with any JSON value.

Errata (8 records): Verified EID 8060 (s7.2 JOSE header
validation step) and Verified EID 8388 (s13.2 POSIX.1
reference URL, editorial) do not touch the validated
claims grammar: noted, not folded.  Reported EID 5906
(s7.2 algorithm rejection), Reported EID 7720 (s4.1.6
future "iat" handling), Reported EID 8225 (s7.2 base64url
decoding), Rejected EID 5648 (s1 pronunciation),
Rejected EID 6622 (s11 link) and Rejected EID 9212 (s4
ECMAScript section pointer) are noted, not folded.  In
particular, temporal acceptance (exp/nbf/iat versus the
current time) is application processing outside this
unit: only the claim TYPES are validated.

JSON parsing is strict RFC 7159: whitespace is SP, TAB,
CR or LF only; strings allow the seven two-character
escapes and \\uXXXX, with a high surrogate only as the
first half of a pair; numbers forbid leading zeros and
require digits around the fraction and exponent points;
true/false/null are lowercase; a document is exactly one
value.

Profile decisions (OURS, not from the RFC text):
  - Duplicate Claim Names are rejected (s4 permits either
    rejection or a lexically-last parser).
  - An empty "aud" array is accepted: the text does not
    forbid it.
  - The StringOrURI URI requirement is checked as: the
    part before the first ":" must be a valid RFC 3986
    scheme (ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )),
    and the value must not contain SP, C0/C1 controls or
    DEL; full RFC 3986 validation is out of scope.
  - A NumericDate may be negative, zero or fractional
    (the text does not bound it); it must be a finite
    number, so a JSON number whose magnitude overflows a
    float refuses (bad_value:json.number).
  - Size caps (OURS): _MAX_INPUT_LENGTH characters
    overall, _MAX_DEPTH nesting, _MAX_MEMBERS members per
    object, _MAX_ELEMENTS items per array,
    _MAX_STRING_LENGTH per string.

Refusal order: bad_type before everything; the overall
length cap; the claims-set shape (the first non-whitespace
character must be '{'); then the JSON document as scanned
(structural, string, number and literal codes by
position; the depth, string length, members and elements
caps as encountered); trailing content after the single
top-level value; duplicate Claim Names (after the whole
document parses, so a syntax error anywhere refuses with
its syntax code first); then per claim in document order:
the registered claim's type rule, then its URI rule.
'''

from importlib.util import find_spec
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:
        raise
    def make_fail(name):
        def fail(code):
            raise ValueError('P235:%s:%s' % (name, code))
        return fail

_MAX_INPUT_LENGTH = 262144
_MAX_DEPTH = 16
_MAX_MEMBERS = 256
_MAX_ELEMENTS = 4096
_MAX_STRING_LENGTH = 8192

_WS = frozenset(' \t\r\n')
_HEXDIG = frozenset('0123456789abcdefABCDEF')
_DIGIT = frozenset('0123456789')
_ALPHA = frozenset(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
_SCHEME_CHAR = _ALPHA | _DIGIT | frozenset('+-.')
_ESCAPES = {'"': '"', '\\': '\\', '/': '/', 'b': '\b',
            'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}


def _skip_ws(s, i, n):
    while i < n and s[i] in _WS:
        i += 1
    return i


def _parse_string(f, s, i, n):
    # s[i] == '"'; return (text, next index).
    i += 1
    out = []
    while True:
        if i >= n:
            f('bad_value:json.string')
        c = s[i]
        if c == '"':
            i += 1
            return ''.join(out), i
        if c == '\\':
            if i + 1 >= n:
                f('bad_value:json.string')
            e = s[i + 1]
            if e in _ESCAPES:
                out.append(_ESCAPES[e])
                i += 2
                continue
            if e == 'u':
                h = s[i + 2:i + 6]
                if len(h) != 4 or any(c2 not in _HEXDIG
                                      for c2 in h):
                    f('bad_value:json.string')
                cp = int(h, 16)
                if 0xD800 <= cp <= 0xDBFF:
                    if (i + 11 >= n or s[i + 6] != '\\'
                            or s[i + 7] != 'u'):
                        f('bad_value:json.surrogate')
                    h2 = s[i + 8:i + 12]
                    if len(h2) != 4 or any(c2 not in _HEXDIG
                                           for c2 in h2):
                        f('bad_value:json.string')
                    cp2 = int(h2, 16)
                    if not 0xDC00 <= cp2 <= 0xDFFF:
                        f('bad_value:json.surrogate')
                    out.append(chr(0x10000 + ((cp - 0xD800) << 10)
                                   + (cp2 - 0xDC00)))
                    i += 12
                    continue
                if 0xDC00 <= cp <= 0xDFFF:
                    f('bad_value:json.surrogate')
                out.append(chr(cp))
                i += 6
                continue
            f('bad_value:json.string')
        if ord(c) < 0x20:
            f('bad_value:json.string')
        out.append(c)
        i += 1
        if len(out) > _MAX_STRING_LENGTH:
            f('bad_value:json.string.length')


def _parse_number(f, s, i, n):
    # Return (int or float, next index); JSON number shape.
    start = i
    if i < n and s[i] == '-':
        i += 1
    if i >= n or s[i] not in _DIGIT:
        f('bad_value:json.number')
    if s[i] == '0':
        i += 1
        if i < n and s[i] in _DIGIT:
            f('bad_value:json.number')
    else:
        while i < n and s[i] in _DIGIT:
            i += 1
    is_float = False
    if i < n and s[i] == '.':
        is_float = True
        i += 1
        if i >= n or s[i] not in _DIGIT:
            f('bad_value:json.number')
        while i < n and s[i] in _DIGIT:
            i += 1
    if i < n and s[i] in 'eE':
        is_float = True
        i += 1
        if i < n and s[i] in '+-':
            i += 1
        if i >= n or s[i] not in _DIGIT:
            f('bad_value:json.number')
        while i < n and s[i] in _DIGIT:
            i += 1
    text = s[start:i]
    if is_float:
        v = float(text)
        if v == float('inf') or v == float('-inf'):
            f('bad_value:json.number')
        return v, i
    return int(text), i


def _parse_value(f, s, i, n, depth):
    # Return (value, next index).
    if depth > _MAX_DEPTH:
        f('bad_value:json.depth')
    if i >= n:
        f('bad_value:json.structure')
    c = s[i]
    if c == '{':
        return _parse_object(f, s, i, n, depth)
    if c == '[':
        return _parse_array(f, s, i, n, depth)
    if c == '"':
        return _parse_string(f, s, i, n)
    if c == '-' or c in _DIGIT:
        return _parse_number(f, s, i, n)
    for word, val in (('true', True), ('false', False),
                      ('null', None)):
        if s.startswith(word, i):
            return val, i + len(word)
    if c in 'tfn':
        f('bad_value:json.literal')
    f('bad_value:json.structure')


class _Obj(list):
    # Object pairs before conversion to a plain dict; only the
    # top-level Claims Set keeps this form.
    pass


def _parse_object(f, s, i, n, depth):
    # s[i] == '{'; return (pairs, next index).
    i += 1
    pairs = _Obj()
    i = _skip_ws(s, i, n)
    if i < n and s[i] == '}':
        return pairs, i + 1
    while True:
        i = _skip_ws(s, i, n)
        if i >= n or s[i] != '"':
            f('bad_value:json.structure')
        key, i = _parse_string(f, s, i, n)
        i = _skip_ws(s, i, n)
        if i >= n or s[i] != ':':
            f('bad_value:json.structure')
        i = _skip_ws(s, i + 1, n)
        value, i = _parse_value(f, s, i, n, depth + 1)
        if isinstance(value, _Obj):
            value = dict(value)
        pairs.append((key, value))
        if len(pairs) > _MAX_MEMBERS:
            f('bad_value:json.members')
        i = _skip_ws(s, i, n)
        if i >= n:
            f('bad_value:json.structure')
        if s[i] == ',':
            i += 1
            continue
        if s[i] == '}':
            return pairs, i + 1
        f('bad_value:json.structure')


def _parse_array(f, s, i, n, depth):
    # s[i] == '['; return (items, next index).
    i += 1
    items = []
    i = _skip_ws(s, i, n)
    if i < n and s[i] == ']':
        return items, i + 1
    while True:
        i = _skip_ws(s, i, n)
        value, i = _parse_value(f, s, i, n, depth + 1)
        if isinstance(value, _Obj):
            value = dict(value)
        items.append(value)
        if len(items) > _MAX_ELEMENTS:
            f('bad_value:json.elements')
        i = _skip_ws(s, i, n)
        if i >= n:
            f('bad_value:json.structure')
        if s[i] == ',':
            i += 1
            continue
        if s[i] == ']':
            return items, i + 1
        f('bad_value:json.structure')


def _check_uri(f, code, v):
    # StringOrURI containing ':': scheme shape plus no SP or
    # control characters (profile OURS, s2 + RFC 3986 s3.1).
    k = v.find(':')
    scheme = v[:k]
    if not scheme or scheme[0] not in _ALPHA:
        f(code)
    for c in scheme[1:]:
        if c not in _SCHEME_CHAR:
            f(code)
    for c in v:
        if ord(c) < 0x21 or 0x7F <= ord(c) <= 0x9F:
            f(code)


def _check_stringoruri(f, type_code, uri_code, v):
    if type(v) is not str:
        f(type_code)
    if ':' in v:
        _check_uri(f, uri_code, v)


def jwt_claims_parse(s):
    'Validate an RFC 7519 JWT Claims Set; return its claims.'
    f = make_fail('jwt_claims_parse')
    if type(s) is not str:
        f('bad_type:value')
    if len(s) > _MAX_INPUT_LENGTH:
        f('bad_value:input.length')
    n = len(s)
    i = _skip_ws(s, 0, n)
    if i >= n or s[i] != '{':
        f('bad_value:claims.shape')
    value, i = _parse_value(f, s, i, n, 1)
    i = _skip_ws(s, i, n)
    if i != n:
        f('bad_value:json.trailing')
    seen = set()
    for name, v in value:
        if name in seen:
            f('bad_value:claim.dup')
        seen.add(name)
    iss = sub = aud = jti = None
    exp = nbf = iat = None
    for name, v in value:
        if name == 'iss':
            _check_stringoruri(f, 'bad_value:iss.type',
                               'bad_value:iss.uri', v)
            iss = v
        elif name == 'sub':
            _check_stringoruri(f, 'bad_value:sub.type',
                               'bad_value:sub.uri', v)
            sub = v
        elif name == 'aud':
            if type(v) is str:
                if ':' in v:
                    _check_uri(f, 'bad_value:aud.uri', v)
                aud = v
            elif type(v) is list:
                for item in v:
                    _check_stringoruri(f, 'bad_value:aud.type',
                                       'bad_value:aud.uri', item)
                aud = v
            else:
                f('bad_value:aud.type')
        elif name == 'exp' or name == 'nbf' or name == 'iat':
            if (type(v) is not int and type(v) is not float):
                f('bad_value:' + name + '.type')
            if name == 'exp':
                exp = v
            elif name == 'nbf':
                nbf = v
            else:
                iat = v
        elif name == 'jti':
            if type(v) is not str:
                f('bad_value:jti.type')
            jti = v
    return {'iss': iss, 'sub': sub, 'aud': aud, 'exp': exp,
            'nbf': nbf, 'iat': iat, 'jti': jti,
            'claims': value}


def jwt_claims_is_valid(s):
    'True iff jwt_claims_parse(s) would succeed.'
    try:
        jwt_claims_parse(s)
    except ValueError:
        return False
    return True
