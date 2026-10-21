"""b1204 RFC 2045 section 5.1 Content-Type and section 6.1 Content-Transfer-Encoding field values.

Source: RFC 2045 (Freed and Borenstein, November 1996), section 5.1 (Syntax of
the Content-Type Header Field) and section 6.1 (Content-Transfer-Encoding
Syntax). Only the field VALUE is handled, never the field name. The RFC says:
"Note also that a subtype specification is MANDATORY -- it may not be omitted
from a Content-Type header field." and "The type, subtype, and parameter names
are not case sensitive." and, for the encoding, "These values are not case
sensitive -- Base64 and BASE64 and bAsE64 are all equivalent."
Grammar implemented (ABNF fragments in single quotes): value is type '/'
subtype *( ';' attribute '=' value ); a token is one or more US-ASCII
characters except space, control characters and the tspecials; a value is a
token or a quoted-string; a mechanism is one of the five named values or an
extension token.
Erratum 512 (Verified, Editorial, section 5.1) is APPLIED: the tspecials
listing lacks the alternative separator after the quote character, so all 15
listed characters are members and TSPECIALS has 15 members. Other errata on
RFC 2045 are read and NOT applied: 2586 (Verified, Technical, section 1, about
which fields may carry comments; this module refuses comments as an OURS
choice, so it is not applied), 3950 (Rejected, Technical, section 4), 3442
(Held for Document Update, Editorial, section 8), and 7120 (Verified,
Editorial, section 2.4); none changes the section 5.1 or 6.1 rules.
Five errata exist for RFC 2045 in the errata data used.
OURS design choices (not sourced from the RFC): white space (space or tab) is
accepted only around the whole value and around each semicolon; comments and
line folding are refused; non-ASCII text and control characters other than tab
are refused; a backslash inside a quoted-string quotes the next character; the
caps TOKEN_MAX 255, TEXT_MAX 131072, VALUE_MAX 1024 and PARAMS_MAX 32; the
check order and the error codes. SOURCED: the token and tspecials rules, the
case-insensitive type, subtype, attribute and mechanism, the five mechanism
names, the x-token form, and the mandatory subtype.
OURS scope note: RFC 6838 (media type names and registration), RFC 2046 and
RFC 7578 are ADJACENT; this module imports none of them, owns pure code, and
makes no registration claim.
Errors raise ValueError P235:<name>:<code>.
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

SCOPE = 'RFC 2045 section 5.1 Content-Type and section 6.1 Content-Transfer-Encoding field values'
NOT_CLAIMED = ('comments and line folding', 'registration of media types', 'semantics of any parameter', 'the defaults of section 5.2', 'RFC 2231 parameter continuations', 'quoted-printable and base64 coding')
ADJACENT = ('RFC 6838 media type names and registration', 'RFC 2046 media types', 'RFC 7578 form-data')
CLAIMS = False

TSPECIALS = '()<>@,;:\\"/[]?='
TOKEN_MAX = 255
TEXT_MAX = 131072
VALUE_MAX = 1024
PARAMS_MAX = 32
MECHANISMS = ('7bit', '8bit', 'binary', 'quoted-printable', 'base64')
DISCRETE = ('text', 'image', 'audio', 'video', 'application')
COMPOSITE = ('message', 'multipart')


def _tok(c):
    return 33 <= ord(c) <= 126 and c not in TSPECIALS


def _is_token(s):
    if s == '':
        return False
    for c in s:
        if not _tok(c):
            return False
    return True


def is_token(text):
    f = make_fail('is_token')
    if type(text) is not str:
        f('text-type')
    if len(text) > TOKEN_MAX:
        f('text-length')
    return _is_token(text)


def _kind(low):
    if low in DISCRETE:
        return 'discrete'
    if low in COMPOSITE:
        return 'composite'
    if low.startswith('x-') and len(low) > 2:
        return 'x-token'
    return 'extension'


def classify_type(text):
    f = make_fail('classify_type')
    if type(text) is not str:
        f('text-type')
    if len(text) > TOKEN_MAX:
        f('text-length')
    if not _is_token(text):
        f('not-token')
    return _kind(text.lower())


def _skip(s, i):
    while i < len(s) and s[i] in ' \t':
        i += 1
    return i


def _run(s, i):
    while i < len(s) and _tok(s[i]):
        i += 1
    return i


def _parse(s):
    for c in s:
        if ord(c) > 126 or (ord(c) < 32 and c != '\t'):
            return 'char-invalid', None
    s = s.strip(' \t')
    i = _run(s, 0)
    if i == 0:
        return 'type-invalid', None
    if i == len(s):
        return 'subtype-missing', None
    if s[i] != '/':
        return 'slash-expected', None
    typ = s[:i]
    j = _run(s, i + 1)
    if j == i + 1:
        return 'subtype-invalid', None
    sub = s[i + 1:j]
    params = []
    i = _skip(s, j)
    while i < len(s):
        if s[i] != ';':
            return 'separator-expected', None
        i = _skip(s, i + 1)
        if i == len(s):
            return 'param-empty', None
        if len(params) == PARAMS_MAX:
            return 'params-length', None
        j = _run(s, i)
        if j == i:
            return 'attribute-invalid', None
        attr = s[i:j]
        if j == len(s) or s[j] != '=':
            return 'equals-expected', None
        i = j + 1
        if i < len(s) and s[i] == '"':
            out = []
            i += 1
            esc = False
            for _ in range(len(s) - i):
                c = s[i]
                i += 1
                if esc:
                    out.append(c)
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    break
                else:
                    out.append(c)
            else:
                return 'quote-unterminated', None
            value = ''.join(out)
        else:
            j = _run(s, i)
            if j == i:
                return 'value-invalid', None
            value = s[i:j]
            i = j
        params.append((attr.lower(), value))
        i = _skip(s, i)
    return None, (typ.lower(), sub.lower(), tuple(params))


def parse_content_type(text):
    f = make_fail('parse_content_type')
    if type(text) is not str:
        f('text-type')
    if len(text) > TEXT_MAX:
        f('text-length')
    code, result = _parse(text)
    if code is not None:
        f(code)
    return result


def parse_encoding(text):
    f = make_fail('parse_encoding')
    if type(text) is not str:
        f('text-type')
    if len(text) > TOKEN_MAX:
        f('text-length')
    s = text.strip(' \t')
    if not _is_token(s):
        f('mechanism-invalid')
    low = s.lower()
    if low in MECHANISMS:
        return low, low
    if low.startswith('x-') and len(low) > 2:
        return low, 'x-token'
    return low, 'extension'


def _quote(value):
    if _is_token(value):
        return value
    out = ['"']
    for c in value:
        if c == '"' or c == '\\':
            out.append('\\')
        out.append(c)
    out.append('"')
    return ''.join(out)


def format_content_type(type_, subtype, params):
    f = make_fail('format_content_type')
    if type(type_) is not str:
        f('type-type')
    if len(type_) > TOKEN_MAX:
        f('type-length')
    if not _is_token(type_):
        f('type-invalid')
    if type(subtype) is not str:
        f('subtype-type')
    if len(subtype) > TOKEN_MAX:
        f('subtype-length')
    if not _is_token(subtype):
        f('subtype-invalid')
    if type(params) is not tuple and type(params) is not list:
        f('params-type')
    if len(params) > PARAMS_MAX:
        f('params-length')
    out = [type_, '/', subtype]
    for item in params:
        if type(item) is not tuple:
            f('item-type')
        if len(item) != 2:
            f('item-length')
        attr, value = item
        if type(attr) is not str:
            f('attribute-type')
        if len(attr) > TOKEN_MAX:
            f('attribute-length')
        if not _is_token(attr):
            f('attribute-invalid')
        if type(value) is not str:
            f('value-type')
        if len(value) > VALUE_MAX:
            f('value-length')
        for c in value:
            if ord(c) > 126 or (ord(c) < 32 and c != '\t'):
                f('value-invalid')
        out.append('; ' + attr + '=' + _quote(value))
    return ''.join(out)
