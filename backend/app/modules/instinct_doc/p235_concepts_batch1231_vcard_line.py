'''RFC 6350 "vCard Format Specification": the s3.3 content
line grammar and the s3.4 property value escaping rules,
over one Python text string carrying ONE logical content
line (already unfolded: s3.2 line folding is out of scope,
as are the vcard wrapper of s3.3, the s4 value data types
and the per-property grammars of s5 and s6).

Public API:

  vcard_line_parse(text) -> a dict:
      'group': the group prefix as received, or None,
      'name': the property name as received,
      'params': list of {'name': the parameter name as
          received, 'values': list of parameter value
          strings (DQUOTEs stripped from quoted forms)},
      'value': the property value, escapes intact,
      'unescaped': the value with s3.4 escapes decoded
          (\\\\ -> \\, \\; -> ;, \\, -> comma, \\n/\\N -> LF),
      'canonical_text': the canonical line (below),
      'canonical': True iff the terminator-stripped input
      IS the canonical text, byte for byte.
  vcard_line_is_valid(text) -> True iff vcard_line_parse
      would succeed.

Grammar notes (verified against the RFC 6350 text).  s3.3:
'contentline = [group "."] name *(";" param) ":" value
CRLF', 'group = 1*(ALPHA / DIGIT / "-")', 'name = "SOURCE"
/ "KIND" / ... / iana-token / x-name', 'iana-token =
1*(ALPHA / DIGIT / "-")', 'x-name = "x-" 1*(ALPHA / DIGIT /
"-")' ("Group and name are case-insensitive"), 'param-value
= *SAFE-CHAR / DQUOTE *QSAFE-CHAR DQUOTE' (with Verified
erratum 2964's parenthesization), 'any-param = (iana-token
/ x-name) "=" param-value *("," param-value)', 'QSAFE-CHAR
= WSP / "!" / %x23-7E / NON-ASCII' ("Any character except
CTLs, DQUOTE"), 'SAFE-CHAR = WSP / "!" / %x23-39 / %x3C-7E
/ NON-ASCII' ("Any character except CTLs, DQUOTE, ";",
":""), 'VALUE-CHAR = WSP / VCHAR / NON-ASCII'.  Verified
erratum 3136 confirms WSP includes HTAB in all three.
s3.3 text: "Property names and parameter names are
case-insensitive" and "it is RECOMMENDED that property and
parameter names be upper-case on output".  s5: "Property
parameter value elements that contain the COLON (U+003A),
SEMICOLON (U+003B), or COMMA (U+002C) character separators
MUST be specified as quoted-string text" (a sender rule;
Held erratum 3138 would move COMMA out of SAFE-CHAR and is
NOT folded, so a bare comma still splits the param-value
list exactly as the printed any-param production says).
s3.4: "a COMMA character in a value MUST be escaped with a
BACKSLASH", "a SEMICOLON in a field of such a "compound"
property MUST be escaped", "BACKSLASH characters in values
MUST be escaped with a BACKSLASH character", "NEWLINE
(U+000A) characters in values MUST be encoded by two
characters: a BACKSLASH followed by either an 'n' (U+006E)
or an 'N' (U+004E)", and "In all other cases, escaping MUST
NOT be used" - so a backslash MUST be followed by one of
\\ ; , n N and any other escape refuses.

Profile decisions (OURS, not from the RFC text):
  - Only the exact str type is accepted; subclasses refuse
    with the type code.
  - ONE optional trailing CRLF (or bare LF) terminator is
    stripped before parsing; any other CR or LF refuses at
    the charset gate.
  - Charset gate: HTAB, 0x20-0x7E, and non-ASCII scalar
    values (0x80 and up, UTF-16 surrogates refused); the
    RFC's NON-ASCII is any UTF8-2/3/4 sequence.
  - Size cap: _MAX_INPUT_LENGTH characters.
  - The canonical text (the RFC defines none): group and
    property/parameter names upper-cased (the s3.3
    RECOMMENDATION), parameter values re-quoted EXACTLY
    when they contain ':', ';' or ',' (the s5 MUST rule),
    list items joined with ",", the value byte-for-byte as
    received, and no line terminator.  Param names and
    values are stored as received (values with DQUOTEs
    stripped).

Refusal order (exactly as executed): bad_type:value (not
exactly str); bad_value:input.length (over
_MAX_INPUT_LENGTH = 8192, terminator included); then the
single optional terminator is stripped and
bad_value:value.charset fires for any remaining char
outside HTAB / 0x20-0x7E / non-ASCII scalars;
bad_value:line.empty; then bad_value:name (no name token,
an empty name after a group dot, or junk between the name
and the ';' / ':' that must follow); then per parameter
bad_value:param (empty parameter name or missing '=') and
bad_value:param.value (a CTL/DQUOTE in an unquoted value,
an unterminated or badly-followed quoted value, a CTL
inside one); then bad_value:colon (no ':' before the
value); then bad_value:value.escape (a lone backslash or
one followed by anything but \\ ; , n N).

Errata: RFC 6350 has 33 records (14 Verified, 10 Held, 7
Reported, 2 Rejected).  Folded Verified: EID 2964 (s3.3)
parenthesizes the param-value quoted alternative - this
unit always parsed it that way; EID 3136 (s3.3) confirms
HTAB is in QSAFE-CHAR/SAFE-CHAR/VALUE-CHAR - the charset
gate allows it.  Verified but out of scope (s4-s7, s10):
EIDs 3000, 3086, 3137, 3368, 3377, 3845, 3484, 3713,
3748, 3846, 4246, 7316.  Held, not folded: EIDs 3138 and
3139 (s3.3 param-value/list semantics - the printed
grammar stands), 7895, 3005, 3100, 3062, 3488, 4261,
4213, 4245.  Reported, not folded: EIDs 7061, 4901,
6746, 6812, 6864, 8092, 8109.  Rejected: EIDs 3199,
7856.
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

_NAME_CHARS = frozenset(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '0123456789-')
_SAFE_CHARS = frozenset(
    '\t !#$%&\'()*+,-./0123456789<=>?@'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`'
    'abcdefghijklmnopqrstuvwxyz{|}~')
_QSAFE_CHARS = frozenset(
    '\t !#$%&\'()*+,-./0123456789:;<=>?@'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`'
    'abcdefghijklmnopqrstuvwxyz{|}~')
_ESCAPE_TARGETS = {'\\': '\\', ';': ';', ',': ',',
                   'n': '\n', 'N': '\n'}


def _non_ascii_ok(c):
    o = ord(c)
    return o >= 0x80 and not 0xD800 <= o <= 0xDFFF


def _canon_pvalue(v):
    if any(c in v for c in ':;,'):
        return '"' + v + '"'
    return v


def vcard_line_parse(text):
    'Validate one RFC 6350 s3.3 content line with s3.4 value escapes.'
    f = make_fail('vcard_line_parse')
    if type(text) is not str:
        f('bad_type:value')
    if len(text) > _MAX_INPUT_LENGTH:
        f('bad_value:input.length')
    s = text
    if s.endswith('\r\n'):
        s = s[:-2]
    elif s.endswith('\n'):
        s = s[:-1]
    for c in s:
        if (c != '\t' and not ' ' <= c <= '~'
                and not _non_ascii_ok(c)):
            f('bad_value:value.charset')
    if not s:
        f('bad_value:line.empty')
    n = len(s)
    j = 0
    while j < n and s[j] in _NAME_CHARS:
        j += 1
    if j == 0:
        f('bad_value:name')
    group = None
    i = 0
    if j < n and s[j] == '.':
        group = s[:j]
        i = j + 1
        j = i
        while j < n and s[j] in _NAME_CHARS:
            j += 1
        if j == i:
            f('bad_value:name')
    name = s[i:j]
    i = j
    if i < n and s[i] not in ';:':
        f('bad_value:name')
    params = []
    while i < n and s[i] == ';':
        i += 1
        j = i
        while j < n and s[j] in _NAME_CHARS:
            j += 1
        if j == i:
            f('bad_value:param')
        pname = s[i:j]
        i = j
        if i >= n or s[i] != '=':
            f('bad_value:param')
        i += 1
        values = []
        while True:
            if i < n and s[i] == '"':
                k = i + 1
                while True:
                    if k >= n:
                        f('bad_value:param.value')
                    if s[k] == '"':
                        break
                    # QSAFE-CHAR excludes only DQUOTE and CTLs: the
                    # former breaks the scan, the latter the charset
                    # gate already refused
                    k += 1
                values.append(s[i + 1:k])
                i = k + 1
                if i < n and s[i] not in ',;:':
                    f('bad_value:param.value')
            else:
                k = i
                while k < n and s[k] not in ',;:':
                    if (s[k] not in _SAFE_CHARS
                            and not _non_ascii_ok(s[k])):
                        f('bad_value:param.value')
                    k += 1
                values.append(s[i:k])
                i = k
            if i < n and s[i] == ',':
                i += 1
                continue
            break
        params.append({'name': pname, 'values': values})
    if i >= n or s[i] != ':':
        f('bad_value:colon')
    value = s[i + 1:]
    k = 0
    while k < len(value):
        if value[k] == '\\':
            if (k + 1 >= len(value)
                    or value[k + 1] not in _ESCAPE_TARGETS):
                f('bad_value:value.escape')
            k += 2
        else:
            k += 1
    out = []
    k = 0
    while k < len(value):
        if value[k] == '\\':
            out.append(_ESCAPE_TARGETS[value[k + 1]])
            k += 2
        else:
            out.append(value[k])
            k += 1
    canon = ''
    if group is not None:
        canon += group.upper() + '.'
    canon += name.upper()
    for p in params:
        canon += ';' + p['name'].upper() + '='
        canon += ','.join(_canon_pvalue(v) for v in p['values'])
    canon += ':' + value
    return {'group': group,
            'name': name,
            'params': params,
            'value': value,
            'unescaped': ''.join(out),
            'canonical_text': canon,
            'canonical': s == canon}


def vcard_line_is_valid(text):
    'True iff vcard_line_parse(text) would succeed.'
    try:
        vcard_line_parse(text)
    except ValueError:
        return False
    return True
