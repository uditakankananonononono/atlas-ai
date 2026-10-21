r"""P235 batch 1211: RFC 9111 (HTTP Caching) Section 5.2 (the Cache-Control header field
and its request and response directives), Section 5.2.3 (extension directives) and
Section 1.2.2 (delta-seconds), as a parser of a Cache-Control field value for a given
role and a formatter back.

STATUS OF THE RFC: RFC 9111 (June 2022, Standards Track) obsoletes RFC 7234. RFC 7234
and every other RFC are not relied on.
OVERLAP (OURS SCOPE): the unit is the grammar of the field value for the two roles; the
Age (5.1), Expires (5.3) and Vary header fields and the freshness, age and validation
rules belong to other units or to none and are not modelled.

QUOTED FROM THE RAW RFC TEXT, read 2026-10-21 from the official plain text file
https://www.rfc-editor.org/rfc/rfc9111.txt as 84477 bytes, sha256
aeb52adb3279d5f23dae34f68af11bd5cef0a0aff7ffcd014c9ca93c5302cf3e, 0 page breaks (form feeds), 0 page footer lines ("[Page"), and a
byte order mark at its start (not in any passage). Each of the 20 passages below is one
contiguous run of whole lines of that raw file, copied without elision or change; the raw
line numbers are in each passage title. The rest of the RFC is not quoted and not modelled.

PASSAGE 1 (RFC 9111 Section 5.2, the field and the directive grammar, raw lines 1083-1109)

   The "Cache-Control" header field is used to list directives for
   caches along the request/response chain.  Cache directives are
   unidirectional, in that the presence of a directive in a request does
   not imply that the same directive is present or copied in the
   response.

   See Section 5.2.3 for information about how Cache-Control directives
   defined elsewhere are handled.

   A proxy, whether or not it implements a cache, MUST pass cache
   directives through in forwarded messages, regardless of their
   significance to that application, since the directives might apply to
   all recipients along the request/response chain.  It is not possible
   to target a directive to a specific cache.

   Cache directives are identified by a token, to be compared case-
   insensitively, and have an optional argument that can use both token
   and quoted-string syntax.  For the directives defined below that
   define arguments, recipients ought to accept both forms, even if a
   specific form is required for generation.

     Cache-Control   = #cache-directive

     cache-directive = token [ "=" ( token / quoted-string ) ]

   For the cache directives defined below, no argument is defined (nor
   allowed) unless stated otherwise.

PASSAGE 2 (RFC 9111 Section 5.2.1.1, max-age (request), raw lines 1116-1129)

5.2.1.1.  max-age

   Argument syntax:

      delta-seconds (see Section 1.2.2)

   The max-age request directive indicates that the client prefers a
   response whose age is less than or equal to the specified number of
   seconds.  Unless the max-stale request directive is also present, the
   client does not wish to receive a stale response.

   This directive uses the token form of the argument syntax: e.g.,
   'max-age=5' not 'max-age="5"'.  A sender MUST NOT generate the
   quoted-string form.

PASSAGE 3 (RFC 9111 Section 5.2.1.2, max-stale, raw lines 1131-1146)

5.2.1.2.  max-stale

   Argument syntax:

      delta-seconds (see Section 1.2.2)

   The max-stale request directive indicates that the client will accept
   a response that has exceeded its freshness lifetime.  If a value is
   present, then the client is willing to accept a response that has
   exceeded its freshness lifetime by no more than the specified number
   of seconds.  If no value is assigned to max-stale, then the client
   will accept a stale response of any age.

   This directive uses the token form of the argument syntax: e.g.,
   'max-stale=10' not 'max-stale="10"'.  A sender MUST NOT generate the
   quoted-string form.

PASSAGE 4 (RFC 9111 Section 5.2.1.3, min-fresh, raw lines 1148-1162)

5.2.1.3.  min-fresh

   Argument syntax:

      delta-seconds (see Section 1.2.2)

   The min-fresh request directive indicates that the client prefers a
   response whose freshness lifetime is no less than its current age
   plus the specified time in seconds.  That is, the client wants a
   response that will still be fresh for at least the specified number
   of seconds.

   This directive uses the token form of the argument syntax: e.g.,
   'min-fresh=20' not 'min-fresh="20"'.  A sender MUST NOT generate the
   quoted-string form.

PASSAGE 5 (RFC 9111 Section 5.2.1.4, no-cache (request), raw lines 1164-1168)

5.2.1.4.  no-cache

   The no-cache request directive indicates that the client prefers a
   stored response not be used to satisfy the request without successful
   validation on the origin server.

PASSAGE 6 (RFC 9111 Section 5.2.1.5, no-store (request), raw lines 1170-1187)

5.2.1.5.  no-store

   The no-store request directive indicates that a cache MUST NOT store
   any part of either this request or any response to it.  This
   directive applies to both private and shared caches.  "MUST NOT
   store" in this context means that the cache MUST NOT intentionally
   store the information in non-volatile storage and MUST make a best-
   effort attempt to remove the information from volatile storage as
   promptly as possible after forwarding it.

   This directive is not a reliable or sufficient mechanism for ensuring
   privacy.  In particular, malicious or compromised caches might not
   recognize or obey this directive, and communications networks might
   be vulnerable to eavesdropping.

   Note that if a request containing this directive is satisfied from a
   cache, the no-store request directive does not apply to the already
   stored response.

PASSAGE 7 (RFC 9111 Section 5.2.1.6, no-transform (request), raw lines 1189-1193)

5.2.1.6.  no-transform

   The no-transform request directive indicates that the client is
   asking for intermediaries to avoid transforming the content, as
   defined in Section 7.7 of [HTTP].

PASSAGE 8 (RFC 9111 Section 5.2.1.7, only-if-cached, raw lines 1195-1201)

5.2.1.7.  only-if-cached

   The only-if-cached request directive indicates that the client only
   wishes to obtain a stored response.  Caches that honor this request
   directive SHOULD, upon receiving it, respond with either a stored
   response consistent with the other constraints of the request or a
   504 (Gateway Timeout) status code.

PASSAGE 9 (RFC 9111 Section 5.2.2 intro and Section 5.2.2.1, max-age (response), raw lines 1203-1220)

5.2.2.  Response Directives

   This section defines cache response directives.  A cache MUST obey
   the Cache-Control directives defined in this section.

5.2.2.1.  max-age

   Argument syntax:

      delta-seconds (see Section 1.2.2)

   The max-age response directive indicates that the response is to be
   considered stale after its age is greater than the specified number
   of seconds.

   This directive uses the token form of the argument syntax: e.g.,
   'max-age=5' not 'max-age="5"'.  A sender MUST NOT generate the
   quoted-string form.

PASSAGE 10 (RFC 9111 Section 5.2.2.2, must-revalidate, raw lines 1222-1244)

5.2.2.2.  must-revalidate

   The must-revalidate response directive indicates that once the
   response has become stale, a cache MUST NOT reuse that response to
   satisfy another request until it has been successfully validated by
   the origin, as defined by Section 4.3.

   The must-revalidate directive is necessary to support reliable
   operation for certain protocol features.  In all circumstances, a
   cache MUST NOT ignore the must-revalidate directive; in particular,
   if a cache is disconnected, the cache MUST generate an error response
   rather than reuse the stale response.  The generated status code
   SHOULD be 504 (Gateway Timeout) unless another error status code is
   more applicable.

   The must-revalidate directive ought to be used by servers if and only
   if failure to validate a request could cause incorrect operation,
   such as a silently unexecuted financial transaction.

   The must-revalidate directive also permits a shared cache to reuse a
   response to a request containing an Authorization header field
   (Section 11.6.2 of [HTTP]), subject to the above requirement on
   revalidation (Section 3.5).

PASSAGE 11 (RFC 9111 Section 5.2.2.3, must-understand, raw lines 1246-1256)

5.2.2.3.  must-understand

   The must-understand response directive limits caching of the response
   to a cache that understands and conforms to the requirements for that
   response's status code.

   A response that contains the must-understand directive SHOULD also
   contain the no-store directive.  When a cache that implements the
   must-understand directive receives a response that includes it, the
   cache SHOULD ignore the no-store directive if it understands and
   implements the status code's caching requirements.

PASSAGE 12 (RFC 9111 Section 5.2.2.4, no-cache (response), raw lines 1258-1293)

5.2.2.4.  no-cache

   Argument syntax:

      #field-name

   The no-cache response directive, in its unqualified form (without an
   argument), indicates that the response MUST NOT be used to satisfy
   any other request without forwarding it for validation and receiving
   a successful response; see Section 4.3.

   This allows an origin server to prevent a cache from using the
   response to satisfy a request without contacting it, even by caches
   that have been configured to send stale responses.

   The qualified form of the no-cache response directive, with an
   argument that lists one or more field names, indicates that a cache
   MAY use the response to satisfy a subsequent request, subject to any
   other restrictions on caching, if the listed header fields are
   excluded from the subsequent response or the subsequent response has
   been successfully revalidated with the origin server (updating or
   removing those fields).  This allows an origin server to prevent the
   reuse of certain header fields in a response, while still allowing
   caching of the rest of the response.

   The field names given are not limited to the set of header fields
   defined by this specification.  Field names are case-insensitive.

   This directive uses the quoted-string form of the argument syntax.  A
   sender SHOULD NOT generate the token form (even if quoting appears
   not to be needed for single-entry lists).

      |  *Note:* The qualified form of the directive is often handled by
      |  caches as if an unqualified no-cache directive was received;
      |  that is, the special handling for the qualified form is not
      |  widely implemented.

PASSAGE 13 (RFC 9111 Section 5.2.2.5, no-store (response), raw lines 1295-1313)

5.2.2.5.  no-store

   The no-store response directive indicates that a cache MUST NOT store
   any part of either the immediate request or the response and MUST NOT
   use the response to satisfy any other request.

   This directive applies to both private and shared caches.  "MUST NOT
   store" in this context means that the cache MUST NOT intentionally
   store the information in non-volatile storage and MUST make a best-
   effort attempt to remove the information from volatile storage as
   promptly as possible after forwarding it.

   This directive is not a reliable or sufficient mechanism for ensuring
   privacy.  In particular, malicious or compromised caches might not
   recognize or obey this directive, and communications networks might
   be vulnerable to eavesdropping.

   Note that the must-understand cache directive overrides no-store in
   certain circumstances; see Section 5.2.2.3.

PASSAGE 14 (RFC 9111 Section 5.2.2.6, no-transform (response), raw lines 1315-1319)

5.2.2.6.  no-transform

   The no-transform response directive indicates that an intermediary
   (regardless of whether it implements a cache) MUST NOT transform the
   content, as defined in Section 7.7 of [HTTP].

PASSAGE 15 (RFC 9111 Section 5.2.2.7, private, raw lines 1321-1353)

5.2.2.7.  private

   Argument syntax:

      #field-name

   The unqualified private response directive indicates that a shared
   cache MUST NOT store the response (i.e., the response is intended for
   a single user).  It also indicates that a private cache MAY store the
   response, subject to the constraints defined in Section 3, even if
   the response would not otherwise be heuristically cacheable by a
   private cache.

   If a qualified private response directive is present, with an
   argument that lists one or more field names, then only the listed
   header fields are limited to a single user: a shared cache MUST NOT
   store the listed header fields if they are present in the original
   response but MAY store the remainder of the response message without
   those header fields, subject the constraints defined in Section 3.

   The field names given are not limited to the set of header fields
   defined by this specification.  Field names are case-insensitive.

   This directive uses the quoted-string form of the argument syntax.  A
   sender SHOULD NOT generate the token form (even if quoting appears
   not to be needed for single-entry lists).

      |  *Note:* This usage of the word "private" only controls where
      |  the response can be stored; it cannot ensure the privacy of the
      |  message content.  Also, the qualified form of the directive is
      |  often handled by caches as if an unqualified private directive
      |  was received; that is, the special handling for the qualified
      |  form is not widely implemented.

PASSAGE 16 (RFC 9111 Section 5.2.2.8, proxy-revalidate, raw lines 1355-1367)

5.2.2.8.  proxy-revalidate

   The proxy-revalidate response directive indicates that once the
   response has become stale, a shared cache MUST NOT reuse that
   response to satisfy another request until it has been successfully
   validated by the origin, as defined by Section 4.3.  This is
   analogous to must-revalidate (Section 5.2.2.2), except that proxy-
   revalidate does not apply to private caches.

   Note that proxy-revalidate on its own does not imply that a response
   is cacheable.  For example, it might be combined with the public
   directive (Section 5.2.2.9), allowing the response to be cached while
   requiring only a shared cache to revalidate when stale.

PASSAGE 17 (RFC 9111 Section 5.2.2.9, public, raw lines 1369-1382)

5.2.2.9.  public

   The public response directive indicates that a cache MAY store the
   response even if it would otherwise be prohibited, subject to the
   constraints defined in Section 3.  In other words, public explicitly
   marks the response as cacheable.  For example, public permits a
   shared cache to reuse a response to a request containing an
   Authorization header field (Section 3.5).

   Note that it is unnecessary to add the public directive to a response
   that is already cacheable according to Section 3.

   If a response with the public directive has no explicit freshness
   information, it is heuristically cacheable (Section 4.2.2).

PASSAGE 18 (RFC 9111 Section 5.2.2.10, s-maxage, raw lines 1384-1406)

5.2.2.10.  s-maxage

   Argument syntax:

      delta-seconds (see Section 1.2.2)

   The s-maxage response directive indicates that, for a shared cache,
   the maximum age specified by this directive overrides the maximum age
   specified by either the max-age directive or the Expires header
   field.

   The s-maxage directive incorporates the semantics of the
   proxy-revalidate response directive (Section 5.2.2.8) for a shared
   cache.  A shared cache MUST NOT reuse a stale response with s-maxage
   to satisfy another request until it has been successfully validated
   by the origin, as defined by Section 4.3.  This directive also
   permits a shared cache to reuse a response to a request containing an
   Authorization header field, subject to the above requirements on
   maximum age and revalidation (Section 3.5).

   This directive uses the token form of the argument syntax: e.g.,
   's-maxage=10' not 's-maxage="10"'.  A sender MUST NOT generate the
   quoted-string form.

PASSAGE 19 (RFC 9111 Section 5.2.3, extension directives, raw lines 1408-1416)

5.2.3.  Extension Directives

   The Cache-Control header field can be extended through the use of one
   or more extension cache directives.  A cache MUST ignore unrecognized
   cache directives.

   Informational extensions (those that do not require a change in cache
   behavior) can be added without changing the semantics of other
   directives.

PASSAGE 20 (RFC 9111 Section 1.2.2, delta-seconds, raw lines 214-234)

   The delta-seconds rule specifies a non-negative integer, representing
   time in seconds.

     delta-seconds  = 1*DIGIT

   A recipient parsing a delta-seconds value and converting it to binary
   form ought to use an arithmetic type of at least 31 bits of non-
   negative integer range.  If a cache receives a delta-seconds value
   greater than the greatest integer it can represent, or if any of its
   subsequent calculations overflows, the cache MUST consider the value
   to be 2147483648 (2^31) or the greatest positive integer it can
   conveniently represent.

      |  *Note:* The value 2147483648 is here for historical reasons,
      |  represents infinity (over 68 years), and does not need to be
      |  stored in binary form; an implementation could produce it as a
      |  string if any overflow occurs, even if the calculations are
      |  performed with an arithmetic type incapable of directly
      |  representing that number.  What matters here is that an
      |  overflow be detected and not treated as a negative value in
      |  later calculations.

ERRATA: the RFC Editor errata index (https://www.rfc-editor.org/errata.json, which now
redirects to the RFC Editor API; read 2026-10-21 through the redirect as 11766165 bytes, sha256
2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) holds
these records.
RFC 9111, 4 records:
- ID 7695 (Rejected, Technical, Section 4.3.2)
- ID 9004 (Reported, Technical, Section 3.5)
- ID 9166 (Held for Document Update, Technical, Section 5.2.3)
- ID 9185 (Reported, Technical, Section 4.3.4)
RFC 7234, 5 records (obsoleted by RFC 9111, not relied on):
- ID 4479 (Rejected, Editorial, Section 5.3)
- ID 4616 (Rejected, Editorial, GLOBAL)
- ID 4674 (Verified, Editorial, Section 5.4)
- ID 5564 (Rejected, Technical, Section 4.2.4)
- ID 6279 (Held for Document Update, Technical, Section 4.2.4)
RFC 9111 ID 9166 (Held for Document Update, Technical, Section 5.2.3) is on the quoted
extension paragraph: the correction adds a sentence saying other HTTP extensions (such as
header fields) can also modify the operation of a cache. It does not change the rule this
unit relies on (a cache MUST ignore unrecognized cache directives), so the parser keeps
extension directives as the printed text states (RELIANCE PINNED). ID 7695 (Rejected,
Technical, Section 4.3.2), ID 9004 (Reported, Technical, Section 3.5) and ID 9185
(Reported, Technical, Section 4.3.4) are filed on sections outside this unit's scope and
are ledgered only. RFC 7234 records are on an obsoleted text and are ledgered only.

SIDE OF THE LINE: this unit takes one Cache-Control field value as text and a role
("request" or "response") and returns a tagged tuple, or takes the tuple and writes the
field value back. What a cache does with a directive (store, reuse, validate, the
qualified handling of no-cache and private, the 2^31 overflow convention of 1.2.2) is not
decided here; a delta value is returned exactly as written.

SOURCED FROM THE PASSAGES ABOVE: the field value is a #-list of cache-directive, each
"token [ "=" ( token / quoted-string ) ]"; directive names are compared
case-insensitively; an argument can use both token and quoted-string syntax and recipients
ought to accept both forms even when a specific form is required for generation; for the
directives defined there no argument is defined (nor allowed) unless stated otherwise; a
proxy passes cache directives through and a cache MUST ignore unrecognized cache
directives; the request directives are max-age, max-stale, min-fresh, no-cache, no-store,
no-transform and only-if-cached; the response directives are max-age, must-revalidate,
must-understand, no-cache, no-store, no-transform, private, proxy-revalidate, public and
s-maxage; max-age (both roles), min-fresh and s-maxage take delta-seconds and use the
token form for generation (a sender MUST NOT generate the quoted-string form); max-stale
takes an optional delta-seconds (no value means a stale response of any age) and uses the
token form for generation; no-cache and private in a response take an optional #field-name
argument and use the quoted-string form (a sender SHOULD NOT generate the token form);
delta-seconds is 1*DIGIT.

DECISIONS OURS, where the RFC allows a choice or is silent (each pinned by a test):
- A tree is ("cache_control", role, directives) with role "request" or "response" and
  directives a tuple of (name, argument) in order. The name is lowercase. The argument is
  None; ("delta", n) with n the exact integer; ("names", (field_name, ...)) with the field
  names lowercase for the qualified no-cache and private; ("token", text) or ("quoted",
  text) for an extension directive, recording the form the argument arrived in.
- A directive known only in the other role is parsed as an extension directive and kept,
  because a proxy passes directives through and a cache ignores what it does not recognize
  (5.2.3); its argument keeps its form. Duplicate directives are kept in order: the RFC
  does not state a rule for them.
- A defined argument accepts both forms on parse (5.2): a delta-seconds reads the content
  of either form (digits only), and a field-name list reads a quoted string of
  comma-separated names or one token (the single-entry token form). The formatter always
  writes the required form: token for delta-seconds (leading zeros are dropped, since
  1*DIGIT allows them on receipt) and a quoted string for a field-name list.
- A refusal is a ValueError whose code is "bad_type:<where>" or "bad_value:<where>".
  parse_cache_control checks, in order: the type of value; its size (at most 8192 octets);
  the type of role; the role itself; the characters of value (printable ASCII and HTAB
  only); then each directive in order: the name (a non-empty token), the argument form
  (a token or a quoted-string; its characters are already bounded by the field-value
  check above, so only its terminators and a trailing escape are read here), then the
  rule of the directive: an
  argument where none is defined is bad_value:directive.argument; a missing, empty or
  non-digit delta-seconds, or one above 10*2^31 (OURS cap: 1.2.2 caps the useful value
  at 2^31 and this unit bounds the integer it builds), is bad_value:directive.delta; a
  bad field-name list is bad_value:directive.names; a bad quoted-string is
  bad_value:directive.quoted; an empty element (including a leading comma) is
  bad_value:directive.name, and a bad separator after a directive (a trailing comma or
  other non-comma text) is bad_value:value.list. The grammar allows no whitespace around "=" (token [ "=" ...
  ]), so "max-age =5" reads as a bare max-age (its delta-seconds is missing) and
  "no-store =5" as a directive followed by a bad separator; OWS around the commas of
  the #-list is allowed.
- format_cache_control checks the tree with exact types (an int is not a bool; order:
  the type of the tree, its shape, the tag, the role, the directives tuple, then each
  directive: pair shape, name, argument), builds the field value with one space after
  each comma, refuses a result above 8192 octets (bad_value:tree.size), and re-parses
  its own text: a refusal from that parse is passed on (with the name of the function
  that was called), and a tree that does not come back equal is bad_value:tree.mismatch
  (this catches an argument on a directive that allows none, a "token" argument that is
  not a token, and the like).
- constants() returns {"field_cap": 8192, "delta_max": 2147483648}.

NOT MODELLED: see NOT_CLAIMED in the module: Age, Expires, Vary, freshness, validation
and every other section of RFC 9111.
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



FIELD_CAP = 8192
TAG = 'cache_control'
ROLES = ('request', 'response')
TCHARS = "!#$%&'*+-.^_`|~" + '0123456789' + 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' + 'abcdefghijklmnopqrstuvwxyz'
DIGITS = '0123456789'
VCHARS = ''.join(chr(c) for c in range(0x21, 0x7f))
DELTA_MAX = 2147483648
ARGS = {
    'request': {'max-age': 'delta', 'max-stale': 'delta?', 'min-fresh': 'delta', 'no-cache': 'none', 'no-store': 'none', 'no-transform': 'none', 'only-if-cached': 'none'},
    'response': {'max-age': 'delta', 'must-revalidate': 'none', 'must-understand': 'none', 'no-cache': 'names?', 'no-store': 'none', 'no-transform': 'none',
                 'private': 'names?', 'proxy-revalidate': 'none', 'public': 'none', 's-maxage': 'delta'},
}
FULL = False


def constants():
    return {'field_cap': FIELD_CAP, 'delta_max': DELTA_MAX}


def _tok(s):
    if len(s) == 0:
        return False
    for c in s:
        if c not in TCHARS:
            return False
    return True


def _ows(s, i, n):
    while i < n and (s[i] == ' ' or s[i] == '\t'):
        i += 1
    return i


def _quoted(s, i, n, f):
    i += 1
    out = []
    while True:
        if i >= n:
            f('bad_value:directive.quoted')
        c = s[i]
        if c == '"':
            return ''.join(out), i + 1
        if c == '\\':
            if i + 1 >= n:
                f('bad_value:directive.quoted')
            out.append(s[i + 1])
            i += 2
        else:
            out.append(c)
            i += 1


def _delta(text, f):
    if len(text) == 0:
        f('bad_value:directive.delta')
    for c in text:
        if c not in DIGITS:
            f('bad_value:directive.delta')
    v = 0
    for c in text:
        v = v * 10 + (ord(c) - 48)
        if v > 10 * DELTA_MAX:
            f('bad_value:directive.delta')
    return ('delta', v)


def _names(text, f):
    out = []
    i = 0
    n = len(text)
    while True:
        i = _ows(text, i, n)
        start = i
        while i < n and text[i] in TCHARS:
            i += 1
        if i == start:
            f('bad_value:directive.names')
        out.append(text[start:i].lower())
        i = _ows(text, i, n)
        if i >= n:
            return ('names', tuple(out))
        if text[i] != ',':
            f('bad_value:directive.names')
        i += 1


def _argument(raw, quoted, rule, f):
    if rule == 'none':
        if raw is not None:
            f('bad_value:directive.argument')
        return None
    if rule == 'delta':
        if raw is None:
            f('bad_value:directive.delta')
        return _delta(raw, f)
    if rule == 'delta?':
        if raw is None:
            return None
        return _delta(raw, f)
    if rule == 'names?':
        if raw is None:
            return None
        return _names(raw, f)
    if raw is None:
        return None
    return ('quoted' if quoted else 'token', raw)


def parse_cache_control(value, role):
    f = make_fail('parse_cache_control')
    if type(value) is not str:
        f('bad_type:value')
    if len(value) > FIELD_CAP:
        f('bad_value:value.size')
    if type(role) is not str:
        f('bad_type:role')
    if role not in ROLES:
        f('bad_value:role')
    for c in value:
        o = ord(c)
        if o < 32 or o > 126:
            if c != '\t':
                f('bad_value:value.char')
    out = []
    i = 0
    n = len(value)
    while True:
        i = _ows(value, i, n)
        start = i
        while i < n and value[i] in TCHARS:
            i += 1
        name = value[start:i].lower()
        if i == start:
            f('bad_value:directive.name')
        arg = None
        quoted = False
        if i < n and value[i] == '=':
            i += 1
            if i < n and value[i] == '"':
                arg, i = _quoted(value, i, n, f)
                quoted = True
            else:
                start = i
                while i < n and value[i] in TCHARS:
                    i += 1
                if i == start:
                    f('bad_value:directive.argument')
                arg = value[start:i]
        i = _ows(value, i, n)
        out.append((name, _argument(arg, quoted, ARGS[role].get(name), f)))
        if i >= n:
            return (TAG, role, tuple(out))
        if value[i] != ',':
            f('bad_value:value.list')
        i += 1
        if i >= n:
            f('bad_value:value.list')


def _quote(s):
    out = []
    for c in s:
        if c == '"' or c == '\\':
            out.append('\\')
        out.append(c)
    return '"' + ''.join(out) + '"'


def _arg_text(arg, f):
    kind = arg[0]
    if kind == 'delta':
        v = arg[1]
        if type(v) is not int:
            f('bad_value:tree.delta')
        if v < 0 or v > 10 * DELTA_MAX:
            f('bad_value:tree.delta')
        return str(v), False
    if kind == 'names':
        names = arg[1]
        if type(names) is not tuple:
            f('bad_value:tree.names')
        if len(names) == 0:
            f('bad_value:tree.names')
        for nm in names:
            if type(nm) is not str:
                f('bad_value:tree.names')
            if not _tok(nm):
                f('bad_value:tree.names')
        return _quote(', '.join(names)), True
    if kind == 'token':
        return arg[1], False
    if kind == 'quoted':
        return _quote(arg[1]), True
    f('bad_value:tree.argument')


def _build(directives, f):
    parts = []
    for d in directives:
        if type(d) is not tuple:
            f('bad_type:tree.directive')
        if len(d) != 2:
            f('bad_value:tree.directive')
        name, arg = d
        if type(name) is not str:
            f('bad_type:tree.name')
        if not _tok(name):
            f('bad_value:tree.name')
        if arg is None:
            parts.append(name)
        else:
            if type(arg) is not tuple:
                f('bad_type:tree.argument')
            if len(arg) != 2:
                f('bad_value:tree.argument')
            if arg[0] == 'token':
                if type(arg[1]) is not str:
                    f('bad_value:tree.argument')
                if not _tok(arg[1]):
                    f('bad_value:tree.argument')
            if arg[0] == 'quoted':
                if type(arg[1]) is not str:
                    f('bad_value:tree.argument')
            parts.append(name + '=' + _arg_text(arg, f)[0])
    return ', '.join(parts)


def format_cache_control(tree):
    f = make_fail('format_cache_control')
    if type(tree) is not tuple:
        f('bad_type:tree')
    if len(tree) != 3:
        f('bad_value:tree.shape')
    tag, role, directives = tree
    if type(tag) is not str:
        f('bad_type:tree.tag')
    if tag != TAG:
        f('bad_value:tree.tag')
    if type(role) is not str:
        f('bad_type:tree.role')
    if role not in ROLES:
        f('bad_value:tree.role')
    if type(directives) is not tuple:
        f('bad_type:tree.directives')
    line = _build(directives, f)
    if len(line) > FIELD_CAP:
        f('bad_value:tree.size')
    if line != '':
        try:
            back = parse_cache_control(line, role)
        except ValueError as e:
            f(str(e).split(':', 2)[2])
        if back != tree:
            f('bad_value:tree.mismatch')
    return line


SCOPE = ('PARTIAL: RFC 9111 (HTTP Caching) Section 5.2: the Cache-Control directive grammar (5.2), the request directives of 5.2.1, the response directives of 5.2.2, '
         'the extension rule of 5.2.3, and delta-seconds from 1.2.2, as a parser and a formatter of the field value for a given role; '
         'no Age, no Expires, no Vary, no freshness or age calculation, no cache behavior')
NOT_CLAIMED = (
    'Age (5.1), Expires (5.3), Pragma (5.4) and Warning (5.5), and every other field of RFC 9111',
    'freshness, age and their calculations (4.2), including the 2^31 overflow convention of 1.2.2: a delta value is returned exactly as written',
    'what a cache does with a directive: validation, storing, staleness, the qualified no-cache and private handling, and the Notes on deployment',
    'the RFC 9110 #rule recipient tolerance for empty list elements: this unit refuses an empty element',
    'RFC 9110 token, quoted-string, #list and field-value rules beyond what the quoted passages state, and every other RFC')
ADJACENT = (
    'a directive known only in the other role is parsed as an extension directive and kept, because a proxy passes directives through and a cache ignores what it does not recognize (5.2.3)',
    'duplicate directives are kept in order: the RFC does not state a rule for them',
    'recipients accept both the token and the quoted-string form of a defined argument (5.2); the formatter generates the required form (token for delta-seconds, quoted for field-name lists)',
    'leading zeros in delta-seconds are accepted (1*DIGIT) and the formatter writes the minimal decimal form')
