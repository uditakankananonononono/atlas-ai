'''RFC 6750 "The OAuth 2.0 Authorization Framework: Bearer Token
Usage": the s2.1 "Authorization" request header credentials
grammar ("Bearer" 1*SP b64token) and the s3
"WWW-Authenticate" Bearer challenge auth-parameter rules
(realm, scope, error, error_description, error_uri, plus the
extension policy) over a Python text string and a decoded
parameter map.  Form-encoded (s2.2) and URI-query (s2.3)
transmission, HTTP header parsing/quoting itself, token
issuance (s4) and the security considerations (s5) are out
of scope.

Public API:

  bearer_credentials_parse(text) -> a dict:
      'scheme': the string "Bearer",
      'token': the b64token text.
  bearer_credentials_is_valid(text) -> True iff
      bearer_credentials_parse would succeed.
  bearer_challenge_parse(params) -> a dict:
      'params': every auth-param as (name, value) pairs in
      document order,
      'realm', 'error', 'error_description', 'error_uri':
      the decoded value of that attribute, or None when
      absent,
      'scope': the decoded "scope" value split into its
      scope-token list, or None when absent.
      params is the DECODED auth-parameter map: either a
      dict mapping attribute name to value, or a list of
      (name, value) pairs in document order (a dict cannot
      express a repeated attribute, which s3 forbids for the
      five named attributes, so the pair-list form keeps
      that rule checkable).
  bearer_challenge_is_valid(params) -> True iff
      bearer_challenge_parse would succeed.

Grammar notes (verified against the RFC 6750 text): the
credentials grammar is printed in s2.1:

  b64token    = 1*( ALPHA / DIGIT /
                    "-" / "." / "_" / "~" / "+" / "/" ) *"="
  credentials = "Bearer" 1*SP b64token

with the s2.1 note that, "as with Basic, it does not conform
to the generic syntax defined in Section 1.2 of [RFC2617]".
The challenge rules (s3): all challenges "MUST use the
auth-scheme value "Bearer".  This scheme MUST be followed by
one or more auth-param values", so an empty parameter map
refuses.  "A "realm" attribute ... MUST NOT appear more than
once"; the "scope" attribute "is defined in Section 3.3 of
[RFC6749]" as "a space-delimited list of case-sensitive
scope values", is OPTIONAL, and "MUST NOT appear more than
once"; ""error", "error_description", and "error_uri"
attributes MUST NOT appear more than once".  "Other
auth-param attributes MAY be used as well", so unknown
attribute names pass with any string value.  The value
charsets quoted in s3: "scope" values "MUST NOT include
characters outside the set %x21 / %x23-5B / %x5D-7E for
representing scope values and %x20 for delimiters between
scope values"; "error" and "error_description" values "MUST
NOT include characters outside the set %x20-21 / %x23-5B /
%x5D-7E"; "error_uri" values "MUST conform to the
URI-reference syntax and thus MUST NOT include characters
outside the set %x21 / %x23-5B / %x5D-7E".  The underlying
[RFC6749] ABNF (Appendixes A.4, A.7, A.8) makes the
scope, error and error-description values non-empty:
scope = scope-token *( SP scope-token ) with scope-token =
1*NQCHAR, error = 1*NQSCHAR, error-description = 1*NQSCHAR.
A.9 gives error-uri = URI-reference, which CAN be empty
under RFC 3986 (relative-ref reduces to path-empty), so
the non-emptiness of error_uri is OURS, not from the ABNF.  s3.1 lists the defined "error" codes
invalid_request, invalid_token and insufficient_scope, but
[RFC6749] s11.4 (the OAuth Extensions Error
Registry) keeps the "error" space extensible, so
membership is not enforced; the charset is.  The "realm"
value carries no s3 charset rule (its wire quoting is the
HTTP layer's business), so any decoded string passes,
including the empty string.

Profile decisions (OURS, not from the RFC text):
  - The "Bearer" scheme token is matched exactly as printed;
    no case-folding (s2.1 prints the literal and notes the
    grammar deliberately deviates from the generic
    framework).
  - Challenge attribute names are matched case-sensitively;
    RFC 6750 gives no case-folding rule for the decoded
    names, and any HTTP-layer folding is the wire parser's
    concern.
  - Attribute names must have the RFC 2617 "token" shape
    (the framework s3 points at): one or more %x21-7E
    characters excluding the separators ( ) < > @ , ; : \\ "
    / [ ] ? = { } SP; anything else refuses
    bad_value:param.name.  This applies to unknown attribute
    names too; their VALUES are unconstrained.
  - "error_uri" is checked for the s3 character set and
    non-emptiness only; full RFC 3986 URI-reference
    validation is out of scope.
  - Only the exact str type is accepted for the credentials
    text and for names and values; subclasses refuse with
    the type code.  The same exact-type discipline covers
    the challenge container: only the exact dict or list
    types are accepted; dict or list subclasses refuse
    bad_type:challenge.type.
  - Size caps (OURS): _MAX_INPUT_LENGTH characters for the
    credentials text, _MAX_PARAMS parameters and
    _MAX_VALUE_LENGTH characters per value in a challenge.

Refusal order: bad_type before everything; for credentials,
the overall length cap, then the "Bearer" + 1*SP prefix
(bad_value:credentials.scheme), then the token
(bad_value:credentials.token.empty before
bad_value:credentials.token.char); for a challenge, the map
type, the pair shapes, the empty map, the parameter-count
cap, then per pair in document order: the attribute-name
rule, the value length cap, the duplicate rule for the five
named attributes (its code at the second occurrence), then
the attribute's own value rule.

Errata (4 records, all Reported, none folded): Reported EID
5335 (s2.1, Technical) proposes renaming "b64token" to
"token68" to match RFC 7235 and avoid base64 confusion: a
naming preference against the printed grammar, so the
grammar keeps the printed name.  Reported EID 6161 (s4,
Editorial), Reported EID 9053 (s5.1, Technical) and
Reported EID 9054 (s5.1, Technical) all drop the
"charset=UTF-8" parameter from the example token response's
application/json Content-Type: examples of token ISSUANCE,
not the validated request/challenge grammar.  ZERO Verified
errata exist for RFC 6750.
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


_MAX_INPUT_LENGTH = 65536
_MAX_PARAMS = 256
_MAX_VALUE_LENGTH = 65536

_B64TOKEN = frozenset(
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    '0123456789-._~+/')
_SCOPE_CHAR = frozenset(
    chr(c) for c in tuple(range(0x21, 0x22))
    + tuple(range(0x23, 0x5C)) + tuple(range(0x5D, 0x7F)))
_NQSCHAR = frozenset(
    chr(c) for c in tuple(range(0x20, 0x22))
    + tuple(range(0x23, 0x5C)) + tuple(range(0x5D, 0x7F)))
_URI_REF_CHAR = _SCOPE_CHAR
_SEPARATORS = frozenset('()<>@,;:\\"/[]?={} \t')


def _is_token_name(name):
    # RFC 2617 "token": 1*CHAR, no CTLs, no separators.
    if not name:
        return False
    for c in name:
        if ord(c) < 0x21 or ord(c) > 0x7E or c in _SEPARATORS:
            return False
    return True


def bearer_credentials_parse(text):
    'Validate s2.1 Bearer credentials; return scheme and token.'
    f = make_fail('bearer_credentials_parse')
    if type(text) is not str:
        f('bad_type:credentials.type')
    if len(text) > _MAX_INPUT_LENGTH:
        f('bad_value:credentials.length')
    if not text.startswith('Bearer'):
        f('bad_value:credentials.scheme')
    i = 6
    n = len(text)
    while i < n and text[i] == ' ':
        i += 1
    if i == 6:
        f('bad_value:credentials.scheme')
    token = text[i:]
    n = len(token)
    if n == 0:
        f('bad_value:credentials.token.empty')
    j = 0
    while j < n and token[j] in _B64TOKEN:
        j += 1
    if j == 0:
        f('bad_value:credentials.token.char')
    while j < n and token[j] == '=':
        j += 1
    if j != n:
        f('bad_value:credentials.token.char')
    return {'scheme': 'Bearer', 'token': token}


def bearer_credentials_is_valid(text):
    'True iff bearer_credentials_parse(text) would succeed.'
    try:
        bearer_credentials_parse(text)
        return True
    except ValueError:
        return False


def _check_scope(f, v):
    toks = v.split(' ')
    for tok in toks:
        if not tok:
            f('bad_value:scope.token')
        for c in tok:
            if c not in _SCOPE_CHAR:
                f('bad_value:scope.value')
    return toks


def _check_charset(f, code, charset, v):
    if not v:
        f(code)
    for c in v:
        if c not in charset:
            f(code)


def bearer_challenge_parse(params):
    'Validate s3 Bearer challenge auth-params; return the map.'
    f = make_fail('bearer_challenge_parse')
    if type(params) is dict:
        pairs = list(params.items())
    elif type(params) is list:
        pairs = params
    else:
        f('bad_type:challenge.type')
    for item in pairs:
        if (type(item) not in (list, tuple) or len(item) != 2
                or type(item[0]) is not str
                or type(item[1]) is not str):
            f('bad_type:challenge.pair')
    if not pairs:
        f('bad_value:challenge.empty')
    if len(pairs) > _MAX_PARAMS:
        f('bad_value:challenge.params.length')
    out = {'params': [(name, value) for name, value in pairs],
           'realm': None, 'scope': None, 'error': None,
           'error_description': None, 'error_uri': None}
    seen = set()
    for name, value in pairs:
        if not _is_token_name(name):
            f('bad_value:param.name')
        if len(value) > _MAX_VALUE_LENGTH:
            f('bad_value:param.value.length')
        if name in ('realm', 'scope', 'error',
                    'error_description', 'error_uri'):
            if name in seen:
                f('bad_value:%s.duplicate' % name)
            seen.add(name)
        if name == 'realm':
            out['realm'] = value
        elif name == 'scope':
            out['scope'] = _check_scope(f, value)
        elif name == 'error':
            _check_charset(f, 'bad_value:error.value',
                           _NQSCHAR, value)
            out['error'] = value
        elif name == 'error_description':
            _check_charset(f, 'bad_value:error_description.value',
                           _NQSCHAR, value)
            out['error_description'] = value
        elif name == 'error_uri':
            _check_charset(f, 'bad_value:error_uri.value',
                           _URI_REF_CHAR, value)
            out['error_uri'] = value
    return out


def bearer_challenge_is_valid(params):
    'True iff bearer_challenge_parse(params) would succeed.'
    try:
        bearer_challenge_parse(params)
        return True
    except ValueError:
        return False
