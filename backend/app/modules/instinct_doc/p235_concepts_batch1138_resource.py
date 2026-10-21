"""Batch 1138 - RFC 8707 resource indicators: the resource parameter (PARTIAL).

Checks one "resource" parameter value for the RFC 8707 section 2 shape,
extracts the "resource" values from an application/x-www-form-urlencoded
string, formats such a string from resource values, and classifies an OAuth
error code string. The RFC 3986 URI grammar and the RFC 6749 error syntax are
named boundaries: only the character level shape that the quoted rules need is
checked here. No network, no token, and no authorization decision is involved.

CLAIMS: a resource value is an absolute URI shape (scheme, ":", the rest)
with no fragment; a query is reported; form extraction of repeated "resource"
parameters; strict form and percent-encoding syntax; the invalid_target error
name; exact error codes.

SCOPE: PARTIAL: RFC 8707 resource parameter syntax over caller-supplied str values, URI shape only, no authority or path grammar, no policy

NOT_CLAIMED (the module constant NOT_CLAIMED, one line per item):
the RFC 3986 authority, host, port, path and query grammar beyond the character sets used here
whether a resource is known, acceptable, audience restricted or reachable
JWT aud claims, token introspection, and any authorization server policy
the RFC 6749 error response structure beyond the error code character set
global novelty
production readiness

QUOTES (RFC 8707, February 2020, https://www.rfc-editor.org/rfc/rfc8707.txt,
RFC 3986, https://www.rfc-editor.org/rfc/rfc3986.txt, and RFC 6749,
https://www.rfc-editor.org/rfc/rfc6749.txt, fetched 2026-10-21;
NORMALIZED: leading indentation stripped, wrapped lines joined (a line that
breaks after a hyphen is joined without a space), page headers and footers
removed, runs of whitespace collapsed):
  [1] "Its value MUST be an absolute URI, as specified by Section 4.3 of [RFC3986]." - RFC 8707 section 2.
  [2] "The URI MUST NOT include a fragment component." - RFC 8707 section 2.
  [3] "It SHOULD NOT include a query component, but it is recognized that there are cases that make a query component a useful and necessary part of the resource parameter, such as when one or more query parameters are used to scope requests to an application." - RFC 8707 section 2.
  [4] "Multiple \"resource\" parameters MAY be used to indicate that the requested token is intended to be used at multiple resources." - RFC 8707 section 2.
  [5] "invalid_target The requested resource is invalid, missing, unknown, or malformed." - RFC 8707 section 2.
  [6] "Although multiple occurrences of the \"resource\" parameter may be included in a token request, using only a single \"resource\" parameter is encouraged." - RFC 8707 section 3.
  [7] "absolute-URI = scheme \":\" hier-part [ \"?\" query ]" - RFC 3986 section 4.3.
  [8] "scheme = ALPHA *( ALPHA / DIGIT / \"+\" / \"-\" / \".\" )" - RFC 3986 section 3.1.
  [9] "unreserved = ALPHA / DIGIT / \"-\" / \".\" / \"_\" / \"~\"" - RFC 3986 section 2.3.
  [10] "pct-encoded = \"%\" HEXDIG HEXDIG" - RFC 3986 section 2.1.
  [11] "gen-delims = \":\" / \"/\" / \"?\" / \"#\" / \"[\" / \"]\" / \"@\"" - RFC 3986 section 2.2.
  [12] "sub-delims = \"!\" / \"$\" / \"&\" / \"'\" / \"(\" / \")\" / \"*\" / \"+\" / \",\" / \";\" / \"=\"" - RFC 3986 section 2.2.
  [13] "error = 1*NQSCHAR" - RFC 6749 appendix A.7.
  [14] "NQSCHAR = %x20-21 / %x23-5B / %x5D-7E" - RFC 6749 appendix A.

CONVENTIONS (OURS, UNSOURCED - the RFCs define no parser strictness profile):
  * Every argument is an exact builtin str, tuple or list as named (no
    subclass, no bool, no bytes).
  * A resource value is accepted when it is not empty, at most 2048
    characters, starts with a scheme (ALPHA then ALPHA, DIGIT, "+", "-", "."
    up to a ":"), and the text after the ":" has only unreserved, sub-delims,
    ":", "/", "?", "@", "[" and "]" characters and well formed pct-encoded
    triplets (HEXDIG is 0-9 A-F a-f). The text after the ":" may be empty,
    as the hier-part may be path-empty. This is a character level shape
    check, not the RFC 3986 grammar: "[" and "]" are not placed.
  * ALPHA and DIGIT are explicit ASCII sets, never str methods, so non-ASCII
    letters and digits are refused. The scheme is returned as written, and its
    case is kept (RFC 3986 says schemes are case-insensitive).
  * A "#" anywhere after the scheme is a fragment and is refused with its own
    code, so "#" must be percent-encoded to appear at all.
  * resource_check returns (scheme, has_query): has_query is True when a "?"
    follows the scheme colon. A query is allowed (the RFC says SHOULD NOT) and
    only reported.
  * The form string is limited to unreserved, "!$'()*,;:@/?" and "%+=&"
    characters; pairs are split on "&" and each pair at its first "=" (a pair
    with no "=" has an empty value). Names and the value of a "resource"
    pair are decoded: "+" is a space and a pct-encoded triplet is its octet; an
    octet of 0x80 or more is refused. Decoding happens once: a value
    "%2541" becomes "%41", which resource_check then reads as a pct-encoded
    triplet. An empty pair (as in "a=1&&b=2" or a leading or trailing "&") is
    refused. A name is the resource parameter only when its decoded form is
    exactly "resource" in lower case. Repeated "resource" pairs are all kept,
    in order, duplicates included.
  * resource_form_format writes each value as resource=<value> with every
    character that is not unreserved written as %XX (upper case hex), pairs
    joined by "&", so resource_form_parse(resource_form_format(v)) == tuple(v).
  * Caps: resource 2048 characters, form 8192, 64 pairs, 16 resource values,
    error code 64.
  * error_code_class checks the RFC 6749 error character set (NQSCHAR, which
    is printable ASCII except the double quote and the backslash) and returns
    'invalid_target' for exactly that string (case-sensitive), else 'other'.

ERRATA (RFC Editor, https://www.rfc-editor.org/errata/rfc8707 and
https://www.rfc-editor.org/errata.json, fetched 2026-10-21; the page and the
index both list 1 erratum):
  Verified 6810 (Editorial, 2022-01-05, section 4): "sever" should read
  "server" and a comma follows "In typical OAuth deployments". It touches
  only privacy text and changes nothing in this module.

CHECK ORDER (each public call obtains make_fail with its own function name):
resource_check: str type, length, empty, scheme, then the characters after
the scheme colon left to right ("#" is a fragment error, "%" must be
followed by two HEXDIG else a pct error, any other character outside the set
is a char error). resource_form_parse: str type, length, pair count (from its
"&"), an empty form gives (); then each pair in order: empty pair, its raw
characters (a "%" needs two HEXDIG, else a form pct error; other characters
must be in the form set), its name decoded (octet check), and when the name is
"resource" its value decoded (octet check) and checked as in resource_check
and appended; then the resource count. resource_form_format: list or tuple,
count, then each item in order (str type, then the resource_check rules); then
the built string length. error_code_class: str type, length, empty,
characters. resource_is_valid returns True exactly when resource_check does
not refuse, and never raises. All errors are ValueError('P235:fn:code').
"""
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

SCOPE = 'PARTIAL: RFC 8707 resource parameter syntax over caller-supplied str values, URI shape only, no authority or path grammar, no policy'
NOT_CLAIMED = ('the RFC 3986 authority, host, port, path and query grammar beyond the character sets used here',
               'whether a resource is known, acceptable, audience restricted or reachable',
               'JWT aud claims, token introspection, and any authorization server policy',
               'the RFC 6749 error response structure beyond the error code character set',
               'global novelty', 'production readiness')

RESOURCE_CAP = 2048
FORM_CAP = 8192
PAIR_CAP = 64
RESOURCE_COUNT_CAP = 16
ERROR_CAP = 64
_ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
_DIGIT = '0123456789'
_UNRESERVED = _ALPHA + _DIGIT + '-._~'
_SCHEME_START = frozenset(_ALPHA)
_SCHEME_REST = frozenset(_ALPHA + _DIGIT + '+-.')
_URI_CHARS = frozenset(_UNRESERVED + "!$&'()*+,;=:/?@[]")
_FORM_CHARS = frozenset(_UNRESERVED + "!$'()*,;:@/?" + '%+=&')
_HEXVAL = {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
           'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14, 'F': 15, 'a': 10, 'b': 11, 'c': 12, 'd': 13, 'e': 14, 'f': 15}
_HEXOUT = '0123456789ABCDEF'
_UNRESERVED_SET = frozenset(_UNRESERVED)


def _scheme(f, text):
    if text[0] not in _SCHEME_START:
        f('bad_value:resource.scheme')
    k = 1
    n = len(text)
    while k < n:
        ch = text[k]
        if ch == ':':
            return k
        if ch not in _SCHEME_REST:
            f('bad_value:resource.scheme')
        k += 1
    f('bad_value:resource.scheme')


def _rest(f, text, start):
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '#':
            f('bad_value:resource.fragment')
        if ch == '%':
            if i + 2 >= n or text[i + 1] not in _HEXVAL or text[i + 2] not in _HEXVAL:
                f('bad_value:resource.pct')
            i += 3
        else:
            if ch not in _URI_CHARS:
                f('bad_value:resource.char')
            i += 1


def _resource(f, value):
    if len(value) > RESOURCE_CAP:
        f('bad_value:resource.length')
    if value == '':
        f('bad_value:resource.empty')
    colon = _scheme(f, value)
    _rest(f, value, colon + 1)
    return (value[:colon], value.find('?', colon + 1) >= 0)


def _scan(f, piece):
    i = 0
    n = len(piece)
    while i < n:
        ch = piece[i]
        if ch == '%':
            if i + 2 >= n or piece[i + 1] not in _HEXVAL or piece[i + 2] not in _HEXVAL:
                f('bad_value:form.pct')
            i += 3
        else:
            if ch not in _FORM_CHARS:
                f('bad_value:form.char')
            i += 1


def _decode(f, text):
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '%':
            octet = _HEXVAL[text[i + 1]] * 16 + _HEXVAL[text[i + 2]]
            if octet > 127:
                f('bad_value:form.octet')
            out.append(chr(octet))
            i += 3
        elif ch == '+':
            out.append(' ')
            i += 1
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


def resource_check(value):
    """Check one resource parameter value and return (scheme, has_query)."""
    f = make_fail('resource_check')
    if type(value) is not str:
        f('bad_type:resource')
    return _resource(f, value)


def resource_is_valid(value):
    """True exactly when resource_check(value) does not refuse; never raises."""
    try:
        resource_check(value)
    except ValueError:
        return False
    return True


def resource_form_parse(form):
    """Return the tuple of decoded resource values in a form string."""
    f = make_fail('resource_form_parse')
    if type(form) is not str:
        f('bad_type:form')
    if len(form) > FORM_CAP:
        f('bad_value:form.length')
    if form == '':
        return ()
    if form.count('&') + 1 > PAIR_CAP:
        f('bad_value:form.count')
    found = []
    for piece in form.split('&'):
        if piece == '':
            f('bad_value:form.pair')
        _scan(f, piece)
        cut = piece.find('=')
        name = piece if cut < 0 else piece[:cut]
        value = '' if cut < 0 else piece[cut + 1:]
        if _decode(f, name) == 'resource':
            text = _decode(f, value)
            _resource(f, text)
            found.append(text)
    if len(found) > RESOURCE_COUNT_CAP:
        f('bad_value:form.resources')
    return tuple(found)


def resource_form_format(resources):
    """Return a form string with one resource=<value> pair per value."""
    f = make_fail('resource_form_format')
    if type(resources) is not tuple and type(resources) is not list:
        f('bad_type:resources')
    if len(resources) > RESOURCE_COUNT_CAP:
        f('bad_value:resources.count')
    pairs = []
    for item in resources:
        if type(item) is not str:
            f('bad_type:resources.item')
        _resource(f, item)
        out = []
        for ch in item:
            if ch in _UNRESERVED_SET:
                out.append(ch)
            else:
                code = ord(ch)
                out.append('%' + _HEXOUT[code // 16] + _HEXOUT[code % 16])
        pairs.append('resource=' + ''.join(out))
    form = '&'.join(pairs)
    if len(form) > FORM_CAP:
        f('bad_value:form.length')
    return form


def error_code_class(code):
    """Return 'invalid_target' for that exact error code, else 'other'."""
    f = make_fail('error_code_class')
    if type(code) is not str:
        f('bad_type:error')
    if len(code) > ERROR_CAP:
        f('bad_value:error.length')
    if code == '':
        f('bad_value:error.empty')
    for ch in code:
        if not (' ' <= ch <= '!' or '#' <= ch <= '[' or ']' <= ch <= '~'):
            f('bad_value:error.char')
    if code == 'invalid_target':
        return 'invalid_target'
    return 'other'
