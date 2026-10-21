'''RFC 4918 "HTTP Extensions for Web Distributed Authoring and
Versioning (WebDAV)": the request-header grammars of s10.2
(Depth), s10.3 (Destination), s10.4 (If), s10.5 (Lock-Token),
s10.6 (Overwrite) and s10.7 (Timeout), over Python text
strings carrying the header VALUE (the part after ":").
Method semantics, lock semantics, the DAV response header
(s10.1) and all body formats are out of scope.

Public API (each parse raises ValueError on refusal; each
is_valid returns True iff its parse would succeed):

  dav_depth_parse(text) -> {'value': '0' | '1' | 'infinity',
      'canonical_text': str, 'canonical': bool}
  dav_overwrite_parse(text) -> {'overwrite': bool,
      'canonical_text': 'T' | 'F', 'canonical': bool}
  dav_timeout_parse(text) -> {'types': list of
      {'kind': 'second', 'seconds': int} or
      {'kind': 'infinite'}, 'canonical_text', 'canonical'}
  dav_lock_token_parse(text) -> {'token': the inner
      absolute-URI, 'canonical_text', 'canonical'}
  dav_destination_parse(text) -> {'destination': str,
      'absolute': True for the absolute-URI form, False for
      the path-absolute form, 'canonical_text', 'canonical'}
  dav_if_parse(text) -> {'tagged': bool, 'groups': list of
      {'tag': None or the Resource-Tag Simple-ref string,
       'lists': list of lists of condition dicts
       {'negated': bool, 'kind': 'state-token' or
        'entity-tag', 'value': str (the State-token URI or
        the entity-tag's quoted content, escapes intact),
        'weak': bool}}, 'canonical_text', 'canonical'}

Grammar notes (verified against the RFC 4918 text).  s10.2:
'Depth = "Depth" ":" ("0" | "1" | "infinity")'.  s10.3:
'Destination = "Destination" ":" Simple-ref'.  s10.5:
'Lock-Token = "Lock-Token" ":" Coded-URL'.  s10.6:
'Overwrite = "Overwrite" ":" ("T" | "F")'.  s10.7: 'TimeOut
= "Timeout" ":" 1#TimeType', 'TimeType = ("Second-"
DAVTimeOutVal | "Infinite") ; No LWS allowed within
TimeType', 'DAVTimeOutVal = 1*DIGIT', and 'The timeout value
for TimeType "Second" MUST NOT be greater than 2^32-1'.
s10.4.2: 'If = "If" ":" ( 1*No-tag-list | 1*Tagged-list )',
'No-tag-list = List', 'Tagged-list = Resource-Tag 1*List',
'List = "(" 1*Condition ")"', 'Condition = ["Not"]
(State-token | "[" entity-tag "]")' with '; entity-tag: see
Section 3.11 of [RFC2616]' and '; No LWS allowed between
"[", entity-tag and "]"', 'State-token = Coded-URL',
'Resource-Tag = "<" Simple-ref ">" ; Simple-ref: see
Section 8.3 ; No LWS allowed in Resource-Tag'.  s10.1: 'Coded-URL = "<" absolute-URI ">"'.
s8.3: 'Simple-ref = absolute-URI | ( path-absolute [ "?"
query ] )' with absolute-URI, path-absolute and query from
RFC 3986 s3, s3.3 and s3.4.  RFC 2616 s3.11: entity-tag =
[ weak ] opaque-tag, weak = "W/", opaque-tag =
quoted-string (RFC 2616 s2.2: quoted-string = ( '"' *(qdtext
| quoted-pair) '"' ), quoted-pair = "\\" CHAR).

Casing: RFC 4918 and RFC 2616 use the ABNF of RFC 2234,
whose s2.3 makes quoted literals case-insensitive, so the
tokens "0", "1", "infinity", "T", "F", "Second-",
"Infinite", "Not" and "W/" match case-insensitively on
input.  The RFCs define no canonical text form for these
headers; the canonical_text emitted here (OURS) uses the
casing of the RFC examples: 'infinity', 'T', 'F',
'Second-N' with no leading zeros, 'Infinite', 'Not', 'W/',
single spaces as separators, no LWS after '(' or before
')', ", " between Timeout items, and the URI / quoted
content byte-for-byte as received.  'canonical' is True iff
the OWS-stripped input IS that canonical text; Lock-Token
and Destination define no normalization, so for them
canonical_text is the stripped input and 'canonical' is
always True.

LWS handling: per RFC 2616 s2.1, LWS (SP/HT) may appear
between adjacent words, and per s2.1's #rule null elements
between commas are allowed and ignored, so Timeout accepts
and drops them; per the grammar comments, NO LWS is allowed
inside Resource-Tag, Coded-URL, the "[" entity-tag "]"
form, or within a TimeType.  Leading/trailing OWS around
the whole value is stripped before parsing (RFC 2616 s4.2:
field-content excludes leading and trailing LWS).
'Not' is recognized only when followed by optional LWS and
then '<' or '['; anything else that starts with those
letters is parsed as a token start and refuses there.

URI validation is SYNTAX ONLY (OURS): scheme per RFC 3986
s3.1, authority with optional userinfo and port, strict
dec-octet IPv4 hosts, bracketed IP-literals checked by
character class only (no IPv6/IPvFuture grammar
validation), reg-name by character class, pct-encoding
enforced ('%' must be followed by two HEXDIG) in every
component, pchar/sub-delims/unreserved character classes
for path and query, and no '#' fragment anywhere (neither
Simple-ref production admits one).  Sender conformance
rules of s8.3 (no dot-segments; Request-URI prefix match)
are NOT enforced - Verified erratum 1519 confirms those are
sender-side rules, not syntax.

Refusal order (exactly as executed, per function):
bad_type:value (not exactly str); bad_value:input.length
(longer than _MAX_INPUT_LENGTH = 8192); bad_value:
value.charset (any char outside HT and 0x20-0x7E); then,
after OWS stripping: depth -> bad_value:depth; overwrite ->
bad_value:overwrite; timeout -> bad_value:timeout.list (no
TimeType at all), then per item bad_value:timeout.item
(malformed TimeType, including LWS inside one or a "Second-"
with no digits) or bad_value:timeout.second_range (digits
whose value exceeds 4294967295); lock_token ->
bad_value:lock_token.brackets (not exactly "<...>"), then
bad_value:lock_token.uri; destination ->
bad_value:destination; if -> bad_value:if.empty, then while
scanning bad_value:if.list (junk at element start, an
unbalanced or tag-less List in tagged mode),
bad_value:if.mixed (a Resource-Tag after a No-tag-list),
bad_value:if.tag (Resource-Tag malformed, LWS inside, bad
Simple-ref, or a Resource-Tag not followed by a List),
bad_value:if.condition (empty List or junk where a
Condition belongs), bad_value:if.token (State-token
malformed, LWS inside, or bad absolute-URI),
bad_value:if.etag (entity-tag malformed).

Errata: RFC 4918 has 9 records (3 Verified, 3 Held, 3
Reported; none folded).  Verified EID 1519 (s8.3) narrows
the Request-URI prefix rule to Multi-Status responses and
keeps the dot-segment ban sender-side - see the URI note
above.  Verified EID 1068 (s10.4.7) fixes example
indentation only.  Verified EID 1430 (s9.3) restores MKCOL
prose - no header grammar.  Held EIDs 1207 (s9.10.1), 1371
(s9.2) and 1635 (s7.4) touch LOCK bodies and depth
semantics, not these header grammars.  Reported EIDs 4431
(GLOBAL), 4435 and 4440 (s9.8.x) are unverified.
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


_MAX_INPUT_LENGTH = 8192

_HEXDIGITS = frozenset('0123456789abcdefABCDEF')
_UNRESERVED = frozenset(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '0123456789' '-._~')
_SUB_DELIMS = frozenset('!$&\'()*+,;=')
_PCHAR = _UNRESERVED | _SUB_DELIMS | frozenset(':@%')
_PATH_CHARS = _PCHAR | frozenset('/')
_QUERY_CHARS = _PCHAR | frozenset('/?')
_USERINFO_CHARS = _UNRESERVED | _SUB_DELIMS | frozenset(':%')
_REGNAME_CHARS = _UNRESERVED | _SUB_DELIMS | frozenset('%')
_LIT_CHARS = _REGNAME_CHARS | frozenset(':.')
_MAX_SECOND = 4294967295


def _check_text(f, text):
    'Type, length and charset gates; return the OWS-stripped value.'
    if type(text) is not str:
        f('bad_type:value')
    if len(text) > _MAX_INPUT_LENGTH:
        f('bad_value:input.length')
    for c in text:
        if c != '\t' and not ' ' <= c <= '~':
            f('bad_value:value.charset')
    return text.strip(' \t')


def _check_pct(text):
    'True iff every % starts a pct-encoded triple.'
    i = 0
    while True:
        i = text.find('%', i)
        if i < 0:
            return True
        if (i + 2 >= len(text)
                or text[i + 1] not in _HEXDIGITS
                or text[i + 2] not in _HEXDIGITS):
            return False
        i += 3


def _all_in(text, allowed):
    return all(c in allowed for c in text)


def _valid_host(f, code, host):
    if host and all(c in '0123456789.' for c in host):
        parts = host.split('.')
        if len(parts) != 4:
            f(code)
        for part in parts:
            if not part or len(part) > 3:
                f(code)
            if len(part) > 1 and part[0] == '0':
                f(code)
            if int(part) > 255:
                f(code)
        return
    if not _all_in(host, _REGNAME_CHARS):
        f(code)


def _valid_authority(f, code, authority):
    if '@' in authority:
        userinfo, authority = authority.rsplit('@', 1)
        if not _all_in(userinfo, _USERINFO_CHARS):
            f(code)
    if authority.startswith('['):
        end = authority.find(']')
        if end < 0:
            f(code)
        inner = authority[1:end]
        if not inner or not _all_in(inner, _LIT_CHARS):
            f(code)
        port = authority[end + 1:]
        if port:
            if not port.startswith(':') or not port[1:].isdigit():
                f(code)
        return
    if ':' in authority:
        host, port = authority.rsplit(':', 1)
        if port and not port.isdigit():
            f(code)
    else:
        host = authority
    _valid_host(f, code, host)


def _valid_path_query(f, code, rest):
    path, mark, query = rest.partition('?')
    if not _all_in(path, _PATH_CHARS):
        f(code)
    if mark and not _all_in(query, _QUERY_CHARS):
        f(code)


def _valid_absolute_uri(f, code, text):
    'RFC 3986 absolute-URI: scheme ":" hier-part [ "?" query ].'
    if not text or '#' in text or not _check_pct(text):
        f(code)
    i = 0
    if not text[0].isalpha():
        f(code)
    while i < len(text) and (text[i].isalnum()
                             or text[i] in '+.-'):
        i += 1
    if i >= len(text) or text[i] != ':':
        f(code)
    rest = text[i + 1:]
    if rest.startswith('//'):
        body = rest[2:]
        cut = len(body)
        for mark in '/?':
            at = body.find(mark)
            if 0 <= at < cut:
                cut = at
        _valid_authority(f, code, body[:cut])
        _valid_path_query(f, code, body[cut:])
    else:
        _valid_path_query(f, code, rest)


def _valid_simple_ref(f, code, text):
    'Simple-ref = absolute-URI | ( path-absolute [ "?" query ] ).'
    if not text or '#' in text or not _check_pct(text):
        f(code)
    if text[0].isalpha():
        j = 0
        while j < len(text) and (text[j].isalnum()
                                 or text[j] in '+.-'):
            j += 1
        if j < len(text) and text[j] == ':':
            _valid_absolute_uri(f, code, text)
            return True
    if not text.startswith('/') or text.startswith('//'):
        f(code)
    _valid_path_query(f, code, text)
    return False


def _scan_entity_tag(f, code, text, i):
    'Parse entity-tag starting at i; return (weak, content, next index).'
    weak = False
    if text[i:i + 2].lower() == 'w/':
        weak = True
        i += 2
    if i >= len(text) or text[i] != '"':
        f(code)
    i += 1
    start = i
    while True:
        if i >= len(text):
            f(code)
        c = text[i]
        if c == '\\':
            # the escaped char's range is already guaranteed by
            # the value.charset gate in _check_text
            i += 2
            continue
        if c == '"':
            break
        i += 1
    return weak, text[start:i], i + 1


def dav_depth_parse(text):
    'Validate an RFC 4918 s10.2 Depth header value.'
    f = make_fail('dav_depth_parse')
    s = _check_text(f, text)
    low = s.lower()
    if low not in ('0', '1', 'infinity'):
        f('bad_value:depth')
    return {'value': low,
            'canonical_text': low,
            'canonical': s == low}


def dav_depth_is_valid(text):
    'True iff dav_depth_parse(text) would succeed.'
    try:
        dav_depth_parse(text)
    except ValueError:
        return False
    return True


def dav_overwrite_parse(text):
    'Validate an RFC 4918 s10.6 Overwrite header value.'
    f = make_fail('dav_overwrite_parse')
    s = _check_text(f, text)
    low = s.lower()
    if low not in ('t', 'f'):
        f('bad_value:overwrite')
    canon = low.upper()
    return {'overwrite': low == 't',
            'canonical_text': canon,
            'canonical': s == canon}


def dav_overwrite_is_valid(text):
    'True iff dav_overwrite_parse(text) would succeed.'
    try:
        dav_overwrite_parse(text)
    except ValueError:
        return False
    return True


def dav_timeout_parse(text):
    'Validate an RFC 4918 s10.7 Timeout request header value.'
    f = make_fail('dav_timeout_parse')
    s = _check_text(f, text)
    types = []
    for item in s.split(','):
        item = item.strip(' \t')
        if not item:
            continue
        low = item.lower()
        if low == 'infinite':
            types.append({'kind': 'infinite'})
            continue
        if low.startswith('second-'):
            digits = item[7:]
            if digits.isdigit():
                seconds = int(digits)
                if seconds > _MAX_SECOND:
                    f('bad_value:timeout.second_range')
                types.append({'kind': 'second', 'seconds': seconds})
                continue
        f('bad_value:timeout.item')
    if not types:
        f('bad_value:timeout.list')
    canon = ', '.join(
        'Second-%d' % t['seconds'] if t['kind'] == 'second'
        else 'Infinite' for t in types)
    return {'types': types,
            'canonical_text': canon,
            'canonical': s == canon}


def dav_timeout_is_valid(text):
    'True iff dav_timeout_parse(text) would succeed.'
    try:
        dav_timeout_parse(text)
    except ValueError:
        return False
    return True


def dav_lock_token_parse(text):
    'Validate an RFC 4918 s10.5 Lock-Token header value.'
    f = make_fail('dav_lock_token_parse')
    s = _check_text(f, text)
    if (len(s) < 2 or not s.startswith('<') or not s.endswith('>')
            or '<' in s[1:-1] or '>' in s[1:-1]):
        f('bad_value:lock_token.brackets')
    token = s[1:-1]
    _valid_absolute_uri(f, 'bad_value:lock_token.uri', token)
    canon = '<' + token + '>'
    return {'token': token,
            'canonical_text': canon,
            'canonical': s == canon}


def dav_lock_token_is_valid(text):
    'True iff dav_lock_token_parse(text) would succeed.'
    try:
        dav_lock_token_parse(text)
    except ValueError:
        return False
    return True


def dav_destination_parse(text):
    'Validate an RFC 4918 s10.3 Destination header value.'
    f = make_fail('dav_destination_parse')
    s = _check_text(f, text)
    absolute = _valid_simple_ref(f, 'bad_value:destination', s)
    return {'destination': s,
            'absolute': absolute,
            'canonical_text': s,
            'canonical': True}


def dav_destination_is_valid(text):
    'True iff dav_destination_parse(text) would succeed.'
    try:
        dav_destination_parse(text)
    except ValueError:
        return False
    return True


def _scan_coded_url(f, code, s, i):
    'Parse "<" absolute-URI ">" starting at i; return (uri, next).'
    j = s.find('>', i + 1)
    if j < 0:
        f(code)
    inner = s[i + 1:j]
    if not inner or ' ' in inner or '\t' in inner or '<' in inner:
        f(code)
    _valid_absolute_uri(f, code, inner)
    return inner, j + 1


def dav_if_parse(text):
    'Validate an RFC 4918 s10.4 If header value.'
    f = make_fail('dav_if_parse')
    s = _check_text(f, text)
    if not s:
        f('bad_value:if.empty')
    groups = []
    tagged = None
    current = None
    i = 0
    n = len(s)
    while True:
        while i < n and s[i] in ' \t':
            i += 1
        if i >= n:
            break
        if s[i] == '<':
            if tagged is False:
                f('bad_value:if.mixed')
            tagged = True
            if current is not None and not current['lists']:
                f('bad_value:if.tag')
            j = s.find('>', i + 1)
            if j < 0:
                f('bad_value:if.tag')
            tag = s[i + 1:j]
            if not tag or ' ' in tag or '\t' in tag or '<' in tag:
                f('bad_value:if.tag')
            _valid_simple_ref(f, 'bad_value:if.tag', tag)
            current = {'tag': tag, 'lists': []}
            groups.append(current)
            i = j + 1
            continue
        if s[i] == '(':
            if tagged is None:
                tagged = False
            i += 1
            conds = []
            while True:
                while i < n and s[i] in ' \t':
                    i += 1
                if i >= n:
                    f('bad_value:if.list')
                if s[i] == ')':
                    i += 1
                    break
                negated = False
                if s[i:i + 3].lower() == 'not':
                    j = i + 3
                    while j < n and s[j] in ' \t':
                        j += 1
                    if j < n and s[j] in '<[':
                        negated = True
                        i = j
                if s[i] == '<':
                    uri, i = _scan_coded_url(f, 'bad_value:if.token', s, i)
                    conds.append({'negated': negated,
                                  'kind': 'state-token',
                                  'value': uri,
                                  'weak': False})
                    continue
                if s[i] == '[':
                    weak, content, i = _scan_entity_tag(
                        f, 'bad_value:if.etag', s, i + 1)
                    if i >= n or s[i] != ']':
                        f('bad_value:if.etag')
                    i += 1
                    conds.append({'negated': negated,
                                  'kind': 'entity-tag',
                                  'value': content,
                                  'weak': weak})
                    continue
                f('bad_value:if.condition')
            if not conds:
                f('bad_value:if.condition')
            if tagged:
                current['lists'].append(conds)
            else:
                if not groups:
                    groups.append({'tag': None, 'lists': []})
                groups[0]['lists'].append(conds)
            continue
        f('bad_value:if.list')
    if tagged and not current['lists']:
        f('bad_value:if.tag')
    parts = []
    for group in groups:
        seg = []
        if group['tag'] is not None:
            seg.append('<' + group['tag'] + '>')
        for conds in group['lists']:
            body = []
            for cond in conds:
                if cond['kind'] == 'state-token':
                    token = '<' + cond['value'] + '>'
                else:
                    token = ('[' + ('W/' if cond['weak'] else '')
                             + '"' + cond['value'] + '"]')
                body.append('Not ' + token if cond['negated'] else token)
            seg.append('(' + ' '.join(body) + ')')
        parts.append(' '.join(seg))
    canon = ' '.join(parts)
    return {'tagged': tagged,
            'groups': groups,
            'canonical_text': canon,
            'canonical': s == canon}


def dav_if_is_valid(text):
    'True iff dav_if_parse(text) would succeed.'
    try:
        dav_if_parse(text)
    except ValueError:
        return False
    return True
