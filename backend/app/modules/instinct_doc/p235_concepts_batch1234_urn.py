'''RFC 8141 "Uniform Resource Names (URNs)": the s2
namestring grammar over one Python text string carrying
ONE URN, plus the s3.1 URN-equivalence normalization of
the assigned-name.  URN resolution, the semantics of the
r/q/f-components, namespace-specific assignment or
equivalence rules, and the NID registration constraints
of s5.1/s5.2 (registry policy, not parser grammar) are
out of scope.

Public API:

  urn_parse(text) -> a dict:
      'urn': the input text as received,
      'nid': the Namespace Identifier as received,
      'nss': the Namespace Specific String as received,
      'r_component': the r-component as received, or
          None when the "?+" delimiter is absent,
      'q_component': the q-component as received, or
          None when the "?=" delimiter is absent,
      'f_component': the f-component as received, or
          None when the "#" delimiter is absent,
      'normalized': the assigned-name after the s3.1
          case normalization (below); two URNs are
          URN-equivalent iff their 'normalized' values
          are octet-by-octet equal,
      'canonical_text': OURS (below),
      'canonical': True iff the input IS the canonical
          text, byte for byte.
  urn_is_valid(text) -> True iff urn_parse would succeed.

Grammar notes (verified against the RFC 8141 text).  s2:
'namestring = assigned-name [ rq-components ] [ "#"
f-component ]', 'assigned-name = "urn" ":" NID ":" NSS',
'NID = (alphanum) 0*30(ldh) (alphanum)', 'ldh = alphanum
/ "-"', 'NSS = pchar *(pchar / "/")', 'rq-components =
[ "?+" r-component ] [ "?=" q-component ]', 'r-component
= pchar *( pchar / "/" / "?" )', 'q-component = pchar *(
pchar / "/" / "?" )', 'f-component = fragment', with
'alphanum', 'fragment' and 'pchar' imported from RFC
3986: 'pchar = unreserved / pct-encoded / sub-delims /
":" / "@"', 'unreserved = ALPHA / DIGIT / "-" / "." /
"_" / "~"', 'sub-delims = "!" / "$" / "&" / "\'" / "(" /
")" / "*" / "+" / "," / ";" / "="', 'pct-encoded = "%"
HEXDIG HEXDIG' (s2.1), 'fragment = *( pchar / "/" / "?"
)' (s3.5).  NID is two to thirty-two characters, first
and last alphanumeric, the middle alphanumerics and
hyphens.  ABNF string literals are case-insensitive
(RFC 5234 s2.3), so the "urn" scheme prefix accepts any
casing, and s2.1 adds "NIDs are case insensitive".  The
s2 '?' rule: 'Other than inside those components, a "?"
that is not immediately followed by "=" or "+" is not
defined for URNs and SHOULD be treated as a syntax error
by URN-specific parsers and other processors.' - folded
here as the bad_value:rq refusal.  The r-component ends at the first
"?=" sequence or "#"; the q-component ends at "#"; the
f-component runs to the end.  An r-component or
q-component requires at least one pchar; an f-component
may be empty ('fragment' allows zero characters).
Percent-encoding: in every component a "%" must be
followed by exactly two HEXDIG; the digits accept either
case on input.

s3.1 URN-equivalence: "Two URNs are URN-equivalent if
their assigned-name portions are octet-by-octet equal
after applying case normalization ... to: 1. the URI
scheme "urn", by conversion to lower case; 2. the NID, by
conversion to lower case; 3. any percent-encoded
characters in the NSS ..., by conversion to upper case
for the digits A-F."  "Percent-encoded characters MUST
NOT be decoded"  "If an r-component, q-component, or
f-component (or any combination thereof) is included in a
URN, it MUST be ignored for purposes of determining
URN-equivalence."  'normalized' is exactly that
normalized assigned-name; namespace-specific extra
equivalence rules (s3.1 last paragraph) are not applied.

Profile decisions (OURS, not from the RFC text):
  - Only the exact str type is accepted; subclasses
    refuse with the type code.
  - The input is capped at 8192 characters; the RFC sets
    no length limit.
  - Canonical text: 'normalized' + the r/q/f-components
    re-attached byte-for-byte with their "?+", "?=" and
    "#" delimiters, in grammar order.

Refusal order: bad_type:value before everything; the
8192-character cap (bad_value:input.length); the charset
gate %x21-7E (bad_value:value.charset); the scheme
prefix (bad_value:scheme); presence of the ":" separator
after the NID (bad_value:nss); the NID: presence and
length (bad_value:nid, bad_value:nid.length), the ldh
class (bad_value:nid.char), the alphanumeric first and
last characters (bad_value:nid.edge); a non-empty NSS
(bad_value:nss), then the NSS scan - pct shape (bad_value:nss.pct) and the
pchar/"/" class (bad_value:nss.char) - up to the
component boundary; the '?' delimiter rule
(bad_value:rq); the r-component: presence of at least
one pchar (bad_value:r), pct shape (bad_value:r.pct) and
class (bad_value:r.char); the q-component: presence
(bad_value:q), pct shape (bad_value:q.pct) and class
(bad_value:q.char); the f-component last: pct shape
(bad_value:f.pct) and class (bad_value:f.char).  Within
each component scan, characters are checked left to
right, so a malformed "%" refuses before a later bad
character.

Errata: RFC 8141 has zero records in the RFC Editor
errata feed (verified against the live feed).
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


# OURS: the RFC sets no length limit.
_MAX_INPUT_LENGTH = 8192

_ALPHANUM = frozenset(
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    '0123456789')

# ldh = alphanum / "-"
_LDH = _ALPHANUM | frozenset('-')

# RFC 3986 s2.3, s2.2, s3.3 (imported by reference in s2).
_UNRESERVED = _ALPHANUM | frozenset('-._~')
_SUB_DELIMS = frozenset("!$&'()*+,;=")
_PCHAR = _UNRESERVED | _SUB_DELIMS | frozenset(':@')
_HEXDIG = frozenset('0123456789ABCDEFabcdef')

# NSS = pchar *(pchar / "/")
_NSS_CHARS = _PCHAR | frozenset('/')

# r-component / q-component / fragment: pchar / "/" / "?"
_RQF_CHARS = _PCHAR | frozenset('/?')


def _check_component(f, seg, code_char, code_pct):
    k = 0
    while k < len(seg):
        c = seg[k]
        if c == '%':
            if (k + 2 >= len(seg)
                    or seg[k + 1] not in _HEXDIG
                    or seg[k + 2] not in _HEXDIG):
                f(code_pct)
            k += 3
            continue
        if c not in _RQF_CHARS:
            f(code_char)
        k += 1


def _normalize_pct(seg):
    # s3.1 item 3: pct-encoding triplets to upper case;
    # the segment is already validated, so every "%"
    # starts a full triplet.
    out = []
    k = 0
    while k < len(seg):
        if seg[k] == '%':
            out.append(seg[k:k + 3].upper())
            k += 3
        else:
            out.append(seg[k])
            k += 1
    return ''.join(out)


def urn_parse(text):
    f = make_fail('urn_parse')
    if type(text) is not str:
        f('bad_type:value')
    if len(text) > _MAX_INPUT_LENGTH:
        f('bad_value:input.length')
    for c in text:
        if not '!' <= c <= '~':
            f('bad_value:value.charset')
    if text[:4].lower() != 'urn:':
        f('bad_value:scheme')
    body = text[4:]
    # The f-component runs to the end of the URN, and "#"
    # is in no other component's class, so the first "#"
    # splits it off; its content is validated last.
    fcomp = None
    fi = body.find('#')
    if fi >= 0:
        fcomp = body[fi + 1:]
        body = body[:fi]
    colon = body.find(':')
    if colon < 0:
        f('bad_value:nss')
    nid = body[:colon]
    if not nid:
        f('bad_value:nid')
    if len(nid) < 2 or len(nid) > 32:
        f('bad_value:nid.length')
    for c in nid:
        if c not in _LDH:
            f('bad_value:nid.char')
    if nid[0] not in _ALPHANUM or nid[-1] not in _ALPHANUM:
        f('bad_value:nid.edge')
    rest = body[colon + 1:]
    # NSS scan: validates left to right and stops at the
    # component boundary, the first '?' (never a pchar).
    k = 0
    nss_end = len(rest)
    boundary = None
    while k < len(rest):
        c = rest[k]
        if c == '?':
            nss_end = k
            if k + 1 >= len(rest) or rest[k + 1] not in '+=':
                f('bad_value:rq')
            boundary = rest[k + 1]
            break
        if c == '%':
            if (k + 2 >= len(rest)
                    or rest[k + 1] not in _HEXDIG
                    or rest[k + 2] not in _HEXDIG):
                f('bad_value:nss.pct')
            k += 3
            continue
        if c not in _NSS_CHARS:
            f('bad_value:nss.char')
        k += 1
    nss = rest[:nss_end]
    if not nss:
        f('bad_value:nss')
    rcomp = None
    qcomp = None
    if boundary == '+':
        seg = rest[nss_end + 2:]
        # The r-component ends at the first "?=" sequence
        # or at the end of the URN; a bare '?' is data.
        k = 0
        r_end = len(seg)
        q_start = None
        while k < len(seg):
            c = seg[k]
            if c == '?':
                if k + 1 < len(seg) and seg[k + 1] == '=':
                    r_end = k
                    q_start = k + 2
                    break
                k += 1
                continue
            if c == '%':
                if (k + 2 >= len(seg)
                        or seg[k + 1] not in _HEXDIG
                        or seg[k + 2] not in _HEXDIG):
                    f('bad_value:r.pct')
                k += 3
                continue
            if c not in _RQF_CHARS:
                f('bad_value:r.char')
            k += 1
        rcomp = seg[:r_end]
        if not rcomp:
            f('bad_value:r')
        if q_start is not None:
            qcomp = seg[q_start:]
            if not qcomp:
                f('bad_value:q')
            _check_component(f, qcomp,
                             'bad_value:q.char', 'bad_value:q.pct')
    elif boundary == '=':
        qcomp = rest[nss_end + 2:]
        if not qcomp:
            f('bad_value:q')
        _check_component(f, qcomp,
                         'bad_value:q.char', 'bad_value:q.pct')
    if fcomp is not None:
        _check_component(f, fcomp,
                         'bad_value:f.char', 'bad_value:f.pct')
    normalized = 'urn:' + nid.lower() + ':' + _normalize_pct(nss)
    canonical_text = normalized
    if rcomp is not None:
        canonical_text += '?+' + rcomp
    if qcomp is not None:
        canonical_text += '?=' + qcomp
    if fcomp is not None:
        canonical_text += '#' + fcomp
    return {'urn': text,
            'nid': nid,
            'nss': nss,
            'r_component': rcomp,
            'q_component': qcomp,
            'f_component': fcomp,
            'normalized': normalized,
            'canonical_text': canonical_text,
            'canonical': text == canonical_text}


def urn_is_valid(text):
    'True iff urn_parse(text) would succeed.'
    try:
        urn_parse(text)
        return True
    except ValueError:
        return False
