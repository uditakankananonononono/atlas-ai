"""p235 concepts batch 1262 (rev 0): RFC 3966, The tel URI for Telephone Numbers, as a grammar over caller-supplied text: the "tel:" scheme prefix, the telephone-subscriber (global-number and local-number with its mandatory phone-context), the parameter, extension and isdn-subaddress elements, the descriptor and domainname productions, and the section 3 parameter uniqueness and ordering rules. Pure functions; no retrieval, no network, no clock, no registries. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it dials nothing, validates no numbering plan, and defines no format.

LIVE SOURCES (fetched 2026-10-22; quotes below are verbatim from these files, mechanically matched with whitespace collapsed):
- RFC 3966 text, rfc-editor (40783 bytes, sha256 38d9aeec48d7f07120bd603f70b2da478218ffd3356eb362a651a31d0ff816bd).
- RFC 2234 text, rfc-editor (24265 bytes, sha256 dcaf77997b83a9a0bda70bc00aa4670c084087e86b4aed57f5b705dfef6eb9ca), for the ABNF string-literal case rule that RFC 3966 imports ("The URI is defined using the ABNF (augmented Backus-Naur form) described in RFC 2234 [RFC2234] and uses elements from the core definitions (appendix A of RFC 2234).").
- rfc-editor info page for RFC 3966 (260945 bytes, sha256 c7b28d8c136899bb0d8eaaedb83853bae9a5411454b0d1d25947327d595c77e3): it lists Obsoletes: RFC 2806 and Updated by: RFC 5341, and shows no Obsoleted by entry. CLAIMS current is still False.
- The full rfc-editor errata index (11775016 bytes, sha256 23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c) contains exactly four RFC 3966 records (count from errata.json and not independently confirmed): EID 202, status Verified, type Editorial, section 5.1.5 (an example-context typo; no grammar content); EID 203, status Verified, type Editorial, section 3 (isdn-subaddress corrected from 1*uric to 1*paramchar; FOLLOWED here, see decision 2); EID 702, status Held for Document Update, type Editorial, section 12 (the fate of the fax and modem schemes; no grammar content); EID 4376, status Held for Document Update, type Editorial, section 3 (the bracketed optional visual-separator in phonedigit/phonedigit-hex; no language change, see decision 2).

SOURCED grammar (RFC 3966 section 3): "telephone-subscriber = global-number / local-number" "global-number        = global-number-digits *par" "local-number         = local-number-digits *par context *par" "par                  = parameter / extension / isdn-subaddress" "descriptor           = domainname / global-number-digits" "global-number-digits = "+" *phonedigit DIGIT *phonedigit" "parameter            = ";" pname ["=" pvalue ]" "paramchar            = param-unreserved / unreserved / pct-encoded" "phonedigit           = DIGIT / [ visual-separator ]" "visual-separator     = "-" / "." / "(" / ")""
SOURCED uniqueness, ordering and local context (sections 3 and 5.1.5): "Each parameter name ("pname"), the ISDN subaddress, the 'extension', and the 'context' MUST NOT appear more than once." "The 'isdn- subaddress' or 'extension' MUST appear first, if present, followed by the 'context' parameter, if present, followed by any other parameters in lexicographical order." "Local numbers MUST have a 'phone-context' parameter that identifies the scope of their validity."
SOURCED comparison and case: "URI comparisons are case-insensitive." "All parameter names and values SHOULD use lower-case characters, as tel URIs may be used within contexts where comparisons are case sensitive."
SOURCED separators and length: "Visual separators ('visual-separator') merely aid readability and are not used for URI comparison or placing a call." "However, even though ITU-T E.123 [E.123] recommends the use of space characters as visual separators in printed telephone numbers, "tel" URIs MUST NOT use spaces in visual separators to avoid excessive escaping." "Implementations MUST NOT assume that telephone numbers have a maximum, minimum, or fixed length, or that they always begin with or contain certain digits."
SOURCED delimiters: "If the reserved characters "+", ";", "=", and "?" are used as delimiters between components of the "tel" URI, they MUST NOT be percent encoded. These characters MUST be percent encoded if they appear in tel URI parameter values."
Examples exercised in the tests (section 6 and section 9): "tel:+1-201-555-0123: This URI points to a phone number in the United" "tel:7042;phone-context=example.com: The URI describes a local phone" "tel:863-1234;phone-context=+1-914-555: The URI describes a local" "tel:1234;phone-context=munich.example.com"

DECISIONS AND NOT_CLAIMED:
1. Case. RFC 3966 imports RFC 2234, whose literals are case-insensitive: "NOTE:     ABNF strings are case-insensitive and" Therefore the literal tokens "tel:", ";ext=", ";isub=" and ";phone-context=" match in any letter case, and HEXDIG (used in phonedigit-hex and pct-encoded) accepts a-f as well as A-F. This is grammar acceptance only; the canonical-comparison lowercase preference ("All parameter names and values SHOULD use lower-case characters, as tel URIs may be used within contexts where comparisons are case sensitive.") and the section 4 equivalence rules are NOT_CLAIMED.
2. Errata. EID 203 (Verified Editorial) is FOLLOWED: an isub value is scanned as 1*paramchar, not 1*uric, so ";", "?", "@", "=" and "," are not accepted inside it. EID 4376 (Held) changes no accepted language: DIGIT / [ visual-separator ] and DIGIT / visual-separator match the same strings, so the phonedigit scan accepts DIGIT or one visual-separator character. EID 202 and EID 702 carry no grammar content.
3. Ordering (OURS reading of the section 3 ordering sentence). The leading block holds the isub and ext elements, in either order when both are present (each at most once, per the uniqueness sentence); the phone-context follows; all other parameters follow in lexicographical pname order, compared on lowercase-folded names ("URI comparisons are case-insensitive."). A violation reports par.order; a repeated name of any kind reports par.dup. A generic parameter literally named "ext" without "=" is a parameter, not an extension, and collides with an extension under par.dup.
4. Semantics. Number existence, reachability, E.164 assignment, dial plans, and the routing behaviors of sections 5 and 9 are NOT_CLAIMED. The section 4 URI-equivalence rules and any canonicalization are NOT_CLAIMED; the module reports grammar reasons only. tel_parts returns the raw digits text WITH visual separators and the raw par elements in order.
5. Caps (OURS, all raising): _LEN_CAP 1024 characters per input. The grammar itself is unbounded ("Implementations MUST NOT assume that telephone numbers have a maximum, minimum, or fixed length, or that they always begin with or contain certain digits.").

FUNCTIONS, in this order: tel_reason, subscriber_reason, global_number_reason, local_number_reason, global_digits_reason, local_digits_reason, par_reason, descriptor_reason, domainname_reason, tel_parts. The reason functions return the string "ok" or a reason string; tel_parts returns (kind, digits_text, pars) with kind "global" or "local" and pars a tuple of the raw "..." par elements in order. Errors are ValueError with the text P235:<function>:<code>, where <function> is the owning function and <code> is bad_type:value (non-str input), bad_value:value.length (over _LEN_CAP), or bad_value:value.tel (tel_parts on an invalid URI).

REASONS, in check order (the first failure decides):
- tel_reason: bad_type:value (raise), bad_value:value.length (raise); then scheme (not a case-insensitive "tel:" prefix), then subscriber.<subscriber_reason reason>; ok.
- subscriber_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, plus (a "+" where a local number is required is only reported by local_number_reason; the plain subscriber picks the branch by the leading character), digits.<digits reason>, then per par left to right par.<par_reason reason>, par.dup, par.order, context.missing (local numbers only); ok.
- global_number_reason / local_number_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, plus (missing for global, present for local), digits.<digits reason>, par.<par reason>, par.dup, par.order, context.missing (local only); ok.
- global_digits_reason: bad_type:value (raise), bad_value:value.length (raise); then plus, char (outside DIGIT and visual-separator, left to right), digit.missing; ok.
- local_digits_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, char (outside phonedigit-hex, left to right), hex.missing (no HEXDIG, "*" or "#"); ok.
- par_reason: bad_type:value (raise), bad_value:value.length (raise); then semi, empty, then per kind: ext.empty, ext.char; isub.empty, isub.char, isub.pct; context.empty, context.<descriptor_reason reason>; pname.empty, pname.char, pvalue.empty, pvalue.char, pvalue.pct; ok.
- descriptor_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, digits.<global digits reason> for a "+" start, domain.<domainname reason> otherwise; ok.
- domainname_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, then per label left to right (one trailing "." allowed): label.empty, label.initial (non-alphanum initial on a non-final label), top.initial (non-ALPHA initial on the final label), label.final, label.char; ok.
- tel_parts: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.tel (raise, when tel_reason would not return ok).

OUTPUT ORDER: reason strings are the exact dotted codes listed above; tel_parts emits the digits text first, then the par elements in input order."""
SCOPE = "RFC 3966 over caller-supplied text: the tel URI grammar - the telephone-subscriber (global-number and local-number with its mandatory phone-context), the parameter, extension and isdn-subaddress elements, the descriptor and domainname productions, and the section 3 uniqueness and ordering rules for parameters. Pure functions; no retrieval, no network, no clock, no registries."
NOT_CLAIMED = ('standard', 'authority', 'certification', 'currency', 'completeness',
               'dialing semantics', 'number existence or reachability', 'E.164 assignment validation', 'URI comparison canonicalization')
CLAIMS = {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False}
ADJACENT = ('RFC 2806 (obsoleted by RFC 3966, per the info page)',
            'RFC 5341 (updates RFC 3966 with a tel URI parameter registry, per the info page; the registry itself is NOT_CLAIMED)',
            'RFC 2396 generic URI syntax and RFC 3261 SIP usage (named by the RFC 3966 text; neither grammar is re-derived here)')

from importlib.util import find_spec

_REG = 'app.modules.instinct_doc.p235_concepts_registry'
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != _REG or find_spec(_REG) is not None:
        raise

    def make_fail(name):
        def fail(code):
            raise ValueError('P235:%s:%s' % (name, code))
        return fail

_LEN_CAP = 1024

_DIGITS = '0123456789'
_ALO = 'abcdefghijklmnopqrstuvwxyz'
_AUP = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
_ALPHA = _ALO + _AUP
_ALNUM = _ALPHA + _DIGITS
_HEXD = '0123456789ABCDEFabcdef'
_SEP = '-.()'
_MARK = "-_.!~*'()"
_PARAM_UNRES = '[]/:&+$'
_FOLD = {_AUP[_k]: _ALO[_k] for _k in range(26)}


def _fold(c):
    return _FOLD[c] if c in _FOLD else c


def _ci_eq(a, b):
    # callers always pass strings of equal length
    for i in range(len(a)):
        if _fold(a[i]) != _fold(b[i]):
            return False
    return True


def _ci_prefix(v, lit):
    return len(v) >= len(lit) and _ci_eq(v[:len(lit)], lit)


def _scan_pct(v, i, n, charcode, pctcode):
    # scan v[i:n] as 1*paramchar; returns a reason or 'ok'
    while i < n:
        c = v[i]
        if c == '%':
            if i + 2 >= n or v[i + 1] not in _HEXD or v[i + 2] not in _HEXD:
                return pctcode
            i += 3
        elif c in _ALNUM or c in _MARK or c in _PARAM_UNRES:
            i += 1
        else:
            return charcode
    return 'ok'


def _digits_reason(v, hexf):
    # shared scan for global-number-digits (hexf False) and local-number-digits
    n = len(v)
    i = 0
    saw_digit = False
    saw_hex = False
    while i < n:
        c = v[i]
        if c in _DIGITS:
            saw_digit = True
            saw_hex = True
        elif hexf and (c in 'ABCDEFabcdef' or c == '*' or c == '#'):
            saw_hex = True
        elif c in _SEP:
            pass
        else:
            return 'char'
        i += 1
    if hexf:
        if not saw_hex:
            return 'hex.missing'
    elif not saw_digit:
        return 'digit.missing'
    return 'ok'


def _global_digits_reason(v):
    if len(v) < 1 or v[0] != '+':
        return 'plus'
    return _digits_reason(v[1:], False)


def _local_digits_reason(v):
    if len(v) == 0:
        return 'empty'
    return _digits_reason(v, True)


def _domainname_reason(v):
    n = len(v)
    if n == 0:
        return 'empty'
    end = n
    if v[n - 1] == '.':
        end = n - 1
        if end == 0:
            return 'label.empty'
    start = 0
    while start < end:
        dot = start
        while dot < end and v[dot] != '.':
            dot += 1
        label_last = dot == end
        if dot == start:
            return 'label.empty'
        c0 = v[start]
        if label_last:
            if c0 not in _ALPHA:
                return 'top.initial'
        elif c0 not in _ALNUM:
            return 'label.initial'
        if v[dot - 1] not in _ALNUM:
            return 'label.final'
        k = start
        while k < dot:
            if v[k] not in _ALNUM and v[k] != '-':
                return 'label.char'
            k += 1
        start = dot + 1
        if start == end:
            return 'label.empty'
    return 'ok'


def _descriptor_reason(v):
    if len(v) == 0:
        return 'empty'
    if v[0] == '+':
        r = _global_digits_reason(v)
        if r != 'ok':
            return 'digits.' + r
        return 'ok'
    r = _domainname_reason(v)
    if r != 'ok':
        return 'domain.' + r
    return 'ok'


def _par_reason(v):
    # one par element, leading ';' included
    n = len(v)
    if n == 0 or v[0] != ';':
        return 'semi'
    if n == 1:
        return 'empty'
    rest = v[1:]
    if _ci_prefix(rest, 'ext='):
        tail = rest[4:]
        if len(tail) == 0:
            return 'ext.empty'
        for i in range(len(tail)):
            if tail[i] not in _DIGITS and tail[i] not in _SEP:
                return 'ext.char'
        return 'ok'
    if _ci_prefix(rest, 'isub='):
        tail = rest[5:]
        if len(tail) == 0:
            return 'isub.empty'
        return _scan_pct(tail, 0, len(tail), 'isub.char', 'isub.pct')
    if _ci_prefix(rest, 'phone-context='):
        tail = rest[14:]
        r = _descriptor_reason(tail)
        if r != 'ok':
            return 'context.' + r
        return 'ok'
    # generic parameter: ";" pname ["=" pvalue]
    i = 0
    m = len(rest)
    while i < m and rest[i] != '=':
        i += 1
    if i == 0:
        return 'pname.empty'
    k = 0
    while k < i:
        if rest[k] not in _ALNUM and rest[k] != '-':
            return 'pname.char'
        k += 1
    if i == m:
        return 'ok'
    tail = rest[i + 1:]
    if len(tail) == 0:
        return 'pvalue.empty'
    return _scan_pct(tail, 0, len(tail), 'pvalue.char', 'pvalue.pct')


def _par_name(v):
    # lowercase identity string of a par's name, for dup and order checks
    rest = v[1:]
    out = ''
    for k in range(len(rest)):
        if rest[k] == '=':
            break
        out += _fold(rest[k])
    return out


def _split_pars(v, head_end):
    # v[head_end:] is a sequence of ';...' elements with no ';' inside any element
    pars = []
    n = len(v)
    i = head_end
    while i < n:
        j = i + 1
        while j < n and v[j] != ';':
            j += 1
        pars += [v[i:j]]
        i = j
    return pars


def _pars_reason(pars, need_context):
    i = 0
    np = len(pars)
    while i < np:
        r = _par_reason(pars[i])
        if r != 'ok':
            return 'par.' + r
        i += 1
    names = []
    i = 0
    while i < np:
        nm = _par_name(pars[i])
        if nm in names:
            return 'par.dup'
        names += [nm]
        i += 1
    # order: isub/ext first (any order between themselves), then phone-context,
    # then other parameters in lexicographical pname order (case-insensitive)
    pos = 0
    while pos < np and names[pos] in ('isub', 'ext'):
        pos += 1
    if pos < np and names[pos] == 'phone-context':
        pos += 1
    prev = None
    while pos < np:
        if names[pos] in ('isub', 'ext', 'phone-context'):
            return 'par.order'
        if prev is not None and names[pos] < prev:
            return 'par.order'
        prev = names[pos]
        pos += 1
    if need_context and 'phone-context' not in names:
        return 'context.missing'
    return 'ok'


def _head_end(v):
    n = len(v)
    i = 0
    while i < n and v[i] != ';':
        i += 1
    return i


def _number_reason(v, want_global):
    if len(v) == 0:
        return 'empty'
    if want_global:
        if v[0] != '+':
            return 'plus'
    elif v[0] == '+':
        return 'plus'
    he = _head_end(v)
    head = v[:he]
    if want_global:
        r = _global_digits_reason(head)
    else:
        r = _local_digits_reason(head)
    if r != 'ok':
        return 'digits.' + r
    return _pars_reason(_split_pars(v, he), not want_global)


def tel_reason(v):
    fail = make_fail('tel_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    if not _ci_prefix(v, 'tel:'):
        return 'scheme'
    r = subscriber_reason(v[4:])
    if r != 'ok':
        return 'subscriber.' + r
    return 'ok'


def subscriber_reason(v):
    fail = make_fail('subscriber_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _number_reason(v, len(v) > 0 and v[0] == '+')


def global_number_reason(v):
    fail = make_fail('global_number_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _number_reason(v, True)


def local_number_reason(v):
    fail = make_fail('local_number_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _number_reason(v, False)


def global_digits_reason(v):
    fail = make_fail('global_digits_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _global_digits_reason(v)


def local_digits_reason(v):
    fail = make_fail('local_digits_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _local_digits_reason(v)


def par_reason(v):
    fail = make_fail('par_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _par_reason(v)


def descriptor_reason(v):
    fail = make_fail('descriptor_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _descriptor_reason(v)


def domainname_reason(v):
    fail = make_fail('domainname_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _domainname_reason(v)


def tel_parts(v):
    fail = make_fail('tel_parts')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    if tel_reason(v) != 'ok':
        fail('bad_value:value.tel')
    rest = v[4:]
    he = _head_end(rest)
    kind = 'global' if rest[0] == '+' else 'local'
    return (kind, rest[:he], tuple(_split_pars(rest, he)))
