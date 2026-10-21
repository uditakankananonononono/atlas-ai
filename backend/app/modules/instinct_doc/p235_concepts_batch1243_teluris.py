"""b1243 RFC 3966 section 3: tel URI syntax for telephone numbers.

Source: RFC 3966 (Schulzrinne, December 2004), section 3 (URI Syntax),
with the section 5.1.5 requirement that local numbers carry a
phone-context. The grammar is 'telephone-uri = "tel:"
telephone-subscriber' with 'telephone-subscriber = global-number /
local-number', 'global-number = global-number-digits *par' and
'local-number = local-number-digits *par context *par'. The digits rules
are 'global-number-digits = "+" *phonedigit DIGIT *phonedigit' and
'local-number-digits = *phonedigit-hex (HEXDIG / "*" / "#")
*phonedigit-hex' with 'phonedigit = DIGIT / [ visual-separator ]',
'phonedigit-hex = HEXDIG / "*" / "#" / [ visual-separator ]' and
'visual-separator = "-" / "." / "(" / ")"'. Parameters follow 'par =
parameter / extension / isdn-subaddress' with 'parameter = ";" pname
["=" pvalue ]', 'extension = ";ext=" 1*phonedigit' and 'context =
";phone-context=" descriptor' with 'descriptor = domainname /
global-number-digits'. On alphabetic numbers: "The URI format does not
support this notation". On hex in local numbers: "However, in accordance
with E.164, these may not be included in global numbers." On case: "URI
comparisons are case-insensitive." On local numbers: "Local numbers MUST
have a 'phone-context' parameter that identifies the scope of their
validity." Global numbers: "Globally unique numbers are unambiguous
everywhere in the world and SHOULD be used."
Errata: four exist for RFC 3966 in the errata data used, cross-checked
against the live index: 202 (Verified, Editorial, section 5.1.5) fixes an
example string and changes no grammar; not applied. 203 (Verified,
Editorial, section 3) corrects 'isdn-subaddress = ";isub=" 1*uric' to
1*paramchar; APPLIED (isub values are validated as paramchar strings).
702 (Held for Document Update, Editorial, section 12) and 4376 (Held for
Document Update, Editorial, section 3) are not applied. RFC 3966 obsoletes
RFC 2806 and is updated by RFC 5341, which changes only the IANA tel URI
parameter registration procedures; the section 3 grammar stands.
OURS design choices (not sourced from the RFC): TEXT_MAX and DESC_MAX are
implementation bounds; the RFC sets no length limits. phone-context is
accepted at most once per URI and is required for local numbers; in a
global number it is validated like any descriptor (the ABNF admits it as
a generic parameter). Local-number hex letters are accepted in upper
case only, per the HEXDIG core rule; percent-encoding hex accepts both
cases. split_tel_uri returns params in order as (pname, pvalue) pairs
with pvalue None when no '=' is present, including ext and isub but not
phone-context, which has its own slot. The E.164 digit-count rules and
any check-digit semantics are NOT implemented. The P235 error codes and
their check order are ours.
SOURCED: the tel scheme and subscriber grammar, the global and local
digits rules with their visual separators, the parameter, extension,
isdn-subaddress and phone-context forms, the descriptor alternatives
with the domainname, domainlabel and toplabel rules, the pname and
pvalue character sets (mark, param-unreserved, pct-encoded), and the
case-insensitivity of comparisons.
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

SCOPE = 'RFC 3966 section 3 tel URI syntax with section 5.1.5 local number context'
NOT_CLAIMED = ('E.164 digit-count rules', 'check-digit or CRC semantics of any kind', 'E.161/T1.703 alphabetic-to-digit mapping', 'actual dialing or call setup', 'SIP/SIPS URI parameters (RFC 3261)', 'tel URI parameter registry contents (RFC 5341)')
ADJACENT = ('RFC 5234 ABNF core rules (DIGIT, HEXDIG, ALPHA)', 'RFC 2396 uric and URI syntax heritage', 'RFC 1035 and RFC 1123 domain name labels (sibling modules)', 'RFC 5341 tel URI parameter registry (updates RFC 3966)', 'RFC 2806 (obsoleted predecessor)')
CLAIMS = False

TEXT_MAX = 1024
DESC_MAX = 255
VISUAL_SEPARATORS = '-.()'
MARK = "-_.!~*'()"
PARAM_UNRESERVED = '[]/:&+$'


def _text(f, text):
    if type(text) is not str:
        f('text-type')


def _letter(c):
    o = ord(c)
    return 97 <= o <= 122 or 65 <= o <= 90


def _digit(c):
    o = ord(c)
    return 48 <= o <= 57


def _alphanum(c):
    return _letter(c) or _digit(c)


def _iei(a, b):
    ua = ord(a)
    ub = ord(b)
    if 97 <= ua <= 122:
        ua = ua - 32
    if 97 <= ub <= 122:
        ub = ub - 32
    return ua == ub


def _ici(a, b):
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not _iei(a[i], b[i]):
            return False
    return True


def _hexval(c):
    o = ord(c)
    if 48 <= o <= 57:
        v = o - 48
    elif 65 <= o <= 70:
        v = o - 55
    elif 97 <= o <= 102:
        v = o - 87
    else:
        v = None
    return v


def _paramchar(c):
    return _alphanum(c) or c in MARK or c in PARAM_UNRESERVED


def _digits_code(digits, kind):
    seen = False
    bad = ''
    for c in digits[1:] if kind == 'global' else digits:
        if _digit(c):
            seen = True
        elif kind == 'local' and (65 <= ord(c) <= 70 or c == '*' or c == '#'):
            seen = True
        elif c not in VISUAL_SEPARATORS:
            bad = c
            break
    if bad:
        return 'digit-char'
    return None if seen else 'digit-none'


def _pct_code(s, ccode, pcode):
    skip = 0
    bad = ''
    for c in s:
        if skip:
            if _hexval(c) is None:
                bad = 'pc'
                break
            skip -= 1
        elif c == '%':
            skip = 2
        elif not _paramchar(c):
            bad = 'c'
            break
    if bad == 'pc':
        return pcode
    if bad == 'c':
        return ccode
    return pcode if skip else None


def _desc_domain_code(d):
    code = None
    if len(d) > DESC_MAX:
        code = 'context-length'
    else:
        core = d[:-1] if d[-1:] == '.' else d
        labels = core.split('.')
        for lab in labels:
            bad = ''
            for c in lab:
                if not _alphanum(c) and c != '-':
                    bad = c
                    break
            if lab == '':
                code = 'context-dot'
                break
            if bad:
                code = 'context-char'
                break
            if lab[0] == '-' or lab[-1] == '-':
                code = 'context-label'
                break
        if code is None and not _letter(labels[-1][0]):
            code = 'context-toplabel'
    return code


def _desc_code(d):
    if d[:1] == '+':
        code = None
        seen = False
        for c in d[1:]:
            if _digit(c):
                seen = True
            elif c not in VISUAL_SEPARATORS:
                code = 'context-char'
                break
        if code is None and not seen:
            code = 'context-none'
    else:
        code = _desc_domain_code(d)
    return code


def _pars_code(parstr):
    context = None
    params = []
    if parstr:
        for seg in parstr.split(';')[1:]:
            if seg == '':
                return 'par-empty', None
            j = seg.find('=')
            if j < 0:
                name = seg
                value = None
            else:
                name = seg[:j]
                value = seg[j + 1:]
            if name == '':
                return 'pname-empty', None
            bad = ''
            for c in name:
                if not _alphanum(c) and c != '-':
                    bad = c
                    break
            if bad:
                return 'pname-char', None
            if _ici(name, 'ext'):
                if value is None:
                    return 'ext-value', None
                if value == '':
                    return 'ext-empty', None
                bad = ''
                for c in value:
                    if not _digit(c) and c not in VISUAL_SEPARATORS:
                        bad = c
                        break
                if bad:
                    return 'ext-char', None
            elif _ici(name, 'isub'):
                if value is None:
                    return 'isub-value', None
                if value == '':
                    return 'isub-empty', None
                code = _pct_code(value, 'isub-char', 'isub-pc')
                if code is not None:
                    return code, None
            elif _ici(name, 'phone-context'):
                if value is None:
                    return 'context-value', None
                if value == '':
                    return 'context-empty', None
                code = _desc_code(value)
                if code is not None:
                    return code, None
                if context is not None:
                    return 'context-dup', None
                context = value
                continue
            else:
                if value is not None:
                    if value == '':
                        return 'pvalue-empty', None
                    code = _pct_code(value, 'pvalue-char', 'pvalue-pc')
                    if code is not None:
                        return code, None
            params.append((name, value))
    return None, (context, params)


def _uri_code(text):
    if text == '':
        return 'empty', None
    if len(text) > TEXT_MAX:
        return 'text-length', None
    if len(text) < 4:
        return 'short', None
    if not _ici(text[:3], 'tel'):
        return 'scheme', None
    if text[3] != ':':
        return 'scheme-colon', None
    body = text[4:]
    if body == '':
        return 'subscriber-empty', None
    i = body.find(';')
    if i < 0:
        digits = body
        parstr = ''
    else:
        digits = body[:i]
        parstr = body[i:]
    if digits[:1] == '+':
        kind = 'global'
    else:
        kind = 'local'
    dcode = _digits_code(digits, kind)
    if dcode is not None:
        return dcode, None
    code, parts = _pars_code(parstr)
    if code is not None:
        return code, None
    context, params = parts
    if kind == 'local' and context is None:
        return 'context-missing', None
    return None, (kind, digits, context, params)


def is_tel_uri(text):
    f = make_fail('is_tel_uri')
    _text(f, text)
    code, parts = _uri_code(text)
    return code is None


def split_tel_uri(text):
    f = make_fail('split_tel_uri')
    _text(f, text)
    code, parts = _uri_code(text)
    if code is not None:
        f(code)
    return parts


def number_kind(text):
    f = make_fail('number_kind')
    _text(f, text)
    code, parts = _uri_code(text)
    if code is not None:
        f(code)
    return parts[0]


def strip_separators(text):
    f = make_fail('strip_separators')
    _text(f, text)
    code, parts = _uri_code(text)
    if code is not None:
        f(code)
    out = []
    for c in parts[1]:
        if c not in VISUAL_SEPARATORS:
            out.append(c)
    return ''.join(out)
