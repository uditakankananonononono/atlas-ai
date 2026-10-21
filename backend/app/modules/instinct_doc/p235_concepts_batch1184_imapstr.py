r"""P235 b1184 bounded exact IMAP4rev1 string syntax: atom, number, quoted, literal and the rules built on them.

Pure functions on bytes, no clock, no network, no IMAP library: imap_parse,
imap_is_valid and imap_format.

Primary source (fetched fresh and read live 2026-10-21): RFC 3501 INTERNET MESSAGE ACCESS PROTOCOL - VERSION 4rev1,
https://www.rfc-editor.org/rfc/rfc3501.txt, Section 4 (Data Formats, 4.1 to 4.3) and Section 9 (Formal Syntax).
Quotes: 'atom = 1*ATOM-CHAR' 'ATOM-CHAR = <any CHAR except atom-specials>' 'atom-specials = "(" / ")" / "{" / SP / CTL / list-wildcards / quoted-specials / resp-specials' 'list-wildcards = "%" / "*"' 'resp-specials = "]"' 'astring = 1*ASTRING-CHAR / string' 'ASTRING-CHAR = ATOM-CHAR / resp-specials' 'tag = 1*<any ASTRING-CHAR except "+">' 'literal = "{" number "}" CRLF *CHAR8' 'CHAR8 = %x01-ff' 'quoted = DQUOTE *QUOTED-CHAR DQUOTE' 'QUOTED-CHAR = <any TEXT-CHAR except quoted-specials> / "\" quoted-specials' 'quoted-specials = DQUOTE / "\"' 'TEXT-CHAR = <any CHAR except CR and LF>' 'string = quoted / literal' 'nstring = string / nil' 'nil = "NIL"' 'number = 1*DIGIT' '(0 <= n < 4,294,967,296)' 'nz-number = digit-nz *DIGIT' 'digit-nz = %x31-39' 'The ASCII NUL character, %x00, MUST NOT be used at any time.' 'Implementations MUST accept these strings in a case-insensitive fashion.' 'The empty string is represented as either "" (a quoted string with zero characters between double quotes) or as {0} followed by CRLF (a literal with an octet count of 0).'
Errata (read live 2026-10-21, from the full index
https://www.rfc-editor.org/errata.json): RFC 3501, https://www.rfc-editor.org/errata/rfc3501,
seven records, none applied and none touches the syntax of this unit. EID 261 (Verified, no section) is
about the UID wording of Section 2.3.1.1. EID 3032 (Verified, Technical, 6.3.1) and EID 3445 (Rejected,
Technical, 6.3.1) are about the UNSEEN and UIDNEXT responses to SELECT. EID 3093 (Held for Document
Update, Editorial, 6.3.11) is about must and may wording. EID 6160 (Held for Document Update, Editorial,
Page 89) is a wording fix in the search rule. EID 6636 (Rejected, Technical, GLOBAL) is the RFC 2822
versus RFC 5322 reference. EID 6637 (Held for Document Update, Technical, 9) says the envelope rule lacks
env-references; this unit does not parse an envelope.

CONVENTIONS (OURS, UNSOURCED where stated). Input and output are exact bytes, never str, bytearray or a bytes
subclass. CHAR is read as %x01-7F, CTL as %x01-1F and %x7F, SP as %x20, DQUOTE as %x22 and CR, LF as %x0D, %x0A
(the RFC 2234 definitions were not read, so this is OURS); the NUL byte %x00 is never accepted, as Section 9
says. An atom character is therefore one of %x21-7E except ( ) { % * " \ and ]; an astring character is an
atom character or ]; a tag is astring characters other than +. Parsing takes one whole value and nothing
else: leading or trailing bytes, including a space or CRLF after a quoted string, are refused. A quoted string
is DQUOTE, then characters of %x01-7F except CR, LF, DQUOTE and backslash, or a backslash followed by DQUOTE
or backslash, then DQUOTE, and imap_parse returns the unescaped bytes. A literal is { digits } CRLF and exactly
that many octets of %x01-FF; the octet data must be wholly present, a non-synchronizing {n+} form is refused
(it is not in RFC 3501), and a literal count follows the number rule. A number is one or more ASCII digits,
leading zeros allowed as the ABNF says, at most 4294967295, and nz-number refuses 0 and any leading zero
(digit-nz first); the value is built by digit arithmetic, never by the int builtin on input. nil is NIL in any letter case and is accepted only by
nstring, where it returns the kind nil and the value None; as an astring the text NIL is an atom. The rules are
atom, number, nz-number, quoted, literal, string, astring, nstring and tag. imap_parse(rule, data) returns a
pair (kind, value): kind atom, quoted, literal, number, nil or tag, and the value is bytes, an int or None. For
string, astring and nstring a first byte of DQUOTE selects quoted and { selects literal; astring otherwise reads
an atom, nstring otherwise reads NIL. The input is at most 4096 bytes (MAX_DATA); a number, atom or tag is read
as-is. imap_is_valid(rule, data) returns exactly True or False and refuses only a wrong type or an unknown
rule. imap_format(rule, value) takes bytes of at most 2000 (MAX_VALUE), an exact int for number and nz-number
(bool refused) and bytes or None for nstring. atom and tag refuse a value that is not one; quoted refuses NUL,
CR, LF and bytes above 127; literal refuses NUL; string writes quoted when every byte fits and a literal
otherwise; astring writes the bare atom when it is a valid astring, else as string; nstring writes NIL for None.
Numbers are written in decimal with no leading zeros. Every output parses back to the same value under the same
rule, so format output is always within the parse cap. Errors are ValueError with message
P235:<function>:<code>. imap_parse: bad_type:rule, bad_type:data, bad_value:rule, bad_value:data.length, then by
rule bad_value:atom, bad_value:number, bad_value:quoted.syntax, quoted.char, bad_value:literal.syntax,
literal.count, literal.length, literal.char, bad_value:string.syntax and bad_value:nstring.syntax.
imap_is_valid: bad_type:rule, bad_type:data and bad_value:rule only. imap_format: bad_type:rule, bad_value:rule,
bad_type:value, bad_value:number, bad_value:value.length, then bad_value:atom, quoted.char or literal.char.

ADJACENCY, by name only: RFC 2234 and RFC 5234 ABNF, RFC 7888 LITERAL+, RFC 3501 commands and responses outside
Section 4 and 9 strings, RFC 2152 and the modified UTF-7 mailbox names of Section 5.1.3 belong to other units
and were not read beyond the sections named above. SCOPE and NOT_CLAIMED are the module constants below.
"""

SCOPE = ('PARTIAL: RFC 3501 Section 4 and 9 atom, number, quoted, literal, '
         'string, astring, nstring and tag syntax on whole bytes values, parse '
         'and format, pure functions, with the OURS choices stated in the '
         'docstring')

NOT_CLAIMED = (
    'commands, responses, flags, sequence sets or any other Section 9 rule',
    'mailbox name encoding, modified UTF-7 or INBOX handling',
    'the non-synchronizing literal form, literal continuation or streaming',
    'the RFC 2234 definitions of CHAR and CTL, which were not read',
    'global novelty',
    'production readiness')

CLAIMS = False

ADJACENT = (
    'RFC 5234 ABNF, RFC 7888 LITERAL+, the rest of RFC 3501 Section 9 and '
    'Section 5.1.3 mailbox names are covered by other units and were not '
    'read beyond the sections named in the docstring',)


MAX_DATA = 4096
MAX_VALUE = 2000
MAX_NUMBER = 4294967295

try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry':
        raise
    import importlib.util as _iu
    if _iu.find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:
        raise
    def make_fail(name):
        def fail(code):
            raise ValueError('P235:%s:%s' % (name, code))
        return fail


_ATOM = b"!#$&'+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[^_`abcdefghijklmnopqrstuvwxyz|}~"
_DIGITS = b'0123456789'
_RULES = ('atom', 'number', 'nz-number', 'quoted', 'literal', 'string', 'astring', 'nstring', 'tag')


class _No(Exception):
    pass


def _no(code):
    raise _No(code)


def _num(f, s, code):
    if len(s) == 0:
        f(code)
    acc = 0
    for b in s:
        d = _DIGITS.find(b)
        if d < 0:
            f(code)
        acc = acc * 10 + d
    if acc > MAX_NUMBER:
        f(code)
    return acc


def _atomlike(f, d, bracket, plus):
    if len(d) == 0:
        f('bad_value:atom')
    for b in d:
        if b == 93:
            if not bracket:
                f('bad_value:atom')
        elif b == 43:
            if not plus:
                f('bad_value:atom')
        elif _ATOM.find(b) < 0:
            f('bad_value:atom')
    return bytes(d)


def _quoted(f, d):
    n = len(d)
    if n < 2 or d[0] != 34 or d[n - 1] != 34:
        f('bad_value:quoted.syntax')
    out = []
    esc = False
    for b in d[1:n - 1]:
        if esc:
            if b != 34 and b != 92:
                f('bad_value:quoted.char')
            out.append(b)
            esc = False
        elif b == 92:
            esc = True
        elif b == 34:
            f('bad_value:quoted.syntax')
        elif b < 1 or b > 127 or b == 10 or b == 13:
            f('bad_value:quoted.char')
        else:
            out.append(b)
    if esc:
        f('bad_value:quoted.syntax')
    return bytes(out)


def _literal(f, d):
    if len(d) == 0 or d[0] != 123:
        f('bad_value:literal.syntax')
    close = d.find(b'}')
    if close < 0:
        f('bad_value:literal.syntax')
    if d[close + 1:close + 3] != b'\r\n':
        f('bad_value:literal.syntax')
    n = _num(f, d[1:close], 'bad_value:literal.count')
    body = d[close + 3:]
    if len(body) != n:
        f('bad_value:literal.length')
    if body.find(0) >= 0:
        f('bad_value:literal.char')
    return bytes(body)


def _parse(f, rule, d):
    if len(d) > MAX_DATA:
        f('bad_value:data.length')
    if rule == 'atom':
        return 'atom', _atomlike(f, d, False, True)
    if rule == 'tag':
        return 'tag', _atomlike(f, d, True, False)
    if rule == 'number':
        return 'number', _num(f, d, 'bad_value:number')
    if rule == 'nz-number':
        n = _num(f, d, 'bad_value:number')
        if d[:1] == b'0':
            f('bad_value:number')
        return 'number', n
    if rule == 'quoted':
        return 'quoted', _quoted(f, d)
    if rule == 'literal':
        return 'literal', _literal(f, d)
    head = d[:1]
    if head == b'"':
        return 'quoted', _quoted(f, d)
    if head == b'{':
        return 'literal', _literal(f, d)
    if rule == 'string':
        f('bad_value:string.syntax')
    if rule == 'astring':
        return 'atom', _atomlike(f, d, True, True)
    if d.lower() == b'nil':
        return 'nil', None
    f('bad_value:nstring.syntax')


def _dec(n):
    if n == 0:
        return b'0'
    out = []
    while n:
        out.append(48 + n % 10)
        n //= 10
    out.reverse()
    return bytes(out)


def _quotable(v):
    for b in v:
        if b < 1 or b > 127 or b == 10 or b == 13:
            return False
    return True


def _fquoted(f, v):
    out = [34]
    for b in v:
        if b < 1 or b > 127 or b == 10 or b == 13:
            f('bad_value:quoted.char')
        if b == 34 or b == 92:
            out.append(92)
        out.append(b)
    out.append(34)
    return bytes(out)


def _fliteral(f, v):
    if v.find(0) >= 0:
        f('bad_value:literal.char')
    return b'{' + _dec(len(v)) + b'}\r\n' + v


def _fstring(f, v):
    if _quotable(v):
        return _fquoted(f, v)
    return _fliteral(f, v)


def _format(f, rule, value):
    if type(rule) is not str:
        f('bad_type:rule')
    if _RULES.count(rule) == 0:
        f('bad_value:rule')
    if rule == 'number' or rule == 'nz-number':
        if type(value) is not int:
            f('bad_type:value')
    elif rule == 'nstring':
        if value is not None and type(value) is not bytes:
            f('bad_type:value')
    elif type(value) is not bytes:
        f('bad_type:value')
    if rule == 'number' or rule == 'nz-number':
        if value < 0 or value > MAX_NUMBER or (rule == 'nz-number' and value == 0):
            f('bad_value:number')
        return _dec(value)
    if value is None:
        return b'NIL'
    if len(value) > MAX_VALUE:
        f('bad_value:value.length')
    if rule == 'atom':
        return _atomlike(f, value, False, True)
    if rule == 'tag':
        return _atomlike(f, value, True, False)
    if rule == 'quoted':
        return _fquoted(f, value)
    if rule == 'literal':
        return _fliteral(f, value)
    if rule == 'astring':
        try:
            return _atomlike(_no, value, True, True)
        except _No:
            return _fstring(f, value)
    return _fstring(f, value)


def _check(f, rule, data):
    if type(rule) is not str:
        f('bad_type:rule')
    if type(data) is not bytes:
        f('bad_type:data')
    if _RULES.count(rule) == 0:
        f('bad_value:rule')


def imap_parse(rule, data):
    f = make_fail('imap_parse')
    _check(f, rule, data)
    return _parse(f, rule, data)


def imap_is_valid(rule, data):
    f = make_fail('imap_is_valid')
    _check(f, rule, data)
    try:
        _parse(_no, rule, data)
    except _No:
        return False
    return True


def imap_format(rule, value):
    return _format(make_fail('imap_format'), rule, value)
