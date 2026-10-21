r"""p235 concepts batch 1123 (rev 0): RFC 7235 HTTP authentication framework syntax. Pure functions over caller-supplied text. No retrieval, no network, no clock. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete, has no scheme semantics, does not consult the registry and does not validate credentials. ADJACENT is the empty tuple.

LIVE-READ SOURCES (read live, quoted verbatim below and mechanically matched against the whitespace-collapsed RFC text with the page headers and footers removed):
- RFC 7235, Hypertext Transfer Protocol (HTTP/1.1): Authentication, Standards Track, June 2014. rfc7235.txt is 38142 bytes, sha256 abfb45a43fdebffc640b51fae46f480e65fc01238f244f94b1bcf2c20da0b862.
- RFC 7230, Hypertext Transfer Protocol (HTTP/1.1): Message Syntax and Routing, June 2014, for the imported ABNF (BWS, OWS, token, quoted-string, the #rule). rfc7230.txt is 205947 bytes, sha256 c7fdc8bebdf1f8195f731592c47f5ea822b489436fd905b01b55ef531fca4120.
- The rfc-editor info page for RFC 7235 says "This RFC is now obsolete, see RFC 9110" and lists Obsoleted by (1): RFC 9110 (HTTP Semantics). It lists Obsoletes (2): RFC 2616 and RFC 2617. The RFC header itself says "Obsoletes: 2616" and "Updates: 2617". The page shows no Updated by entry. This module therefore targets a superseded document: it implements RFC 7235 as assigned, applies none of RFC 9110's changes, and CLAIMS current is False.
- errata.json (sha256 2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) records 1 erratum for RFC 7235: 6307 (Rejected, Technical, section 2.1, about the case-insensitive token). It records 24 errata for RFC 7230; the ones touching the sections used here: 4050 (Verified, Editorial, 3.2.4: "response code" versus "status code"); 5163 (Held for Document Update, Technical, 3.2.4: linear whitespace and obs-fold); 4189 (Held for Document Update, Technical, 3.2: the general field-value rule); 4891 (Held for Document Update, Editorial, 3.2.6: a missing space in the qdtext rule); 6333 (Rejected, Technical, 3.2.6 PDF: curly quotes in the PDF only, the text version is correct); 4169 (Verified, Technical, 7: a legacy-list derivation corner with trailing whitespace); 5257 (Held for Document Update, Technical, 7: #element versus 1#element for a leading comma). Both counts are taken from that single JSON index and are not independently confirmed against the per-erratum pages. OURS: no erratum is applied. The RFC text and its collected ABNF decide.

SOURCED (the RFC text):
- Scheme, parameters and token68 (2.1): "auth-scheme = token" "auth-param = token BWS "=" BWS ( token / quoted-string )" "token68 = 1*( ALPHA / DIGIT / "-" / "." / "_" / "~" / "+" / "/" ) *"=""
- Challenge and credentials (2.1): "challenge = auth-scheme [ 1*SP ( token68 / #auth-param ) ]" "credentials = auth-scheme [ 1*SP ( token68 / #auth-param ) ]"
- Parameter names (2.1): "Authentication parameters are name=value pairs, where the name token is matched case-insensitively, and each parameter name MUST only occur once per challenge."
- Field values (4.1-4.4): "WWW-Authenticate = 1#challenge" "Authorization = credentials" "Proxy-Authenticate = 1#challenge" "Proxy-Authorization = credentials"
- List parsing caution (4.1): "User agents are advised to take special care in parsing the field value, as it might contain more than one challenge, and each challenge can contain a comma-separated list of authentication parameters."
- The empty-entry ambiguity (4.1 note): "Therefore, a sequence of comma, whitespace, and comma can be considered either as applying to the preceding challenge, or to be an empty entry in the list of challenges. In practice, this ambiguity does not affect the semantics of the header field value and thus is harmless."
- The 4.1 example: "WWW-Authenticate: Newauth realm="apps", type=1," "title="Login to \"apps\"", Basic realm="simple""
- token68 rationale (2.1): "The token68 syntax allows the 66 unreserved URI characters ([RFC3986]), plus a few others, so that it can hold a base64, base64url (URL and filename safe alphabet), base32, or base16 (hex) encoding, with or without padding, but excluding whitespace ([RFC4648])."
- Header purposes: "The "WWW-Authenticate" header field indicates the authentication scheme(s) and parameters applicable to the target resource." "The "Authorization" header field allows a user agent to authenticate itself with an origin server"
- Imported ABNF (RFC 7230 3.2.3, 3.2.6): "OWS = *( SP / HTAB )" "BWS = OWS" "token = 1*tchar" "tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*" / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA" "quoted-string = DQUOTE *( qdtext / quoted-pair ) DQUOTE" "qdtext = HTAB / SP /%x21 / %x23-5B / %x5D-7E / obs-text" "quoted-pair = "\" ( HTAB / SP / VCHAR / obs-text )"
- Collected ABNF (RFC 7235 Appendix C): "Proxy-Authenticate = *( "," OWS ) challenge *( OWS "," [ OWS challenge ] )" "WWW-Authenticate = *( "," OWS ) challenge *( OWS "," [ OWS challenge ] )" "challenge = auth-scheme [ 1*SP ( token68 / [ ( "," / auth-param ) *( OWS "," [ OWS auth-param ] ) ] ) ]"
- Status use (2.1): "A 401 (Unauthorized) response message is used by an origin server to challenge the authorization of a user agent"
- Client parsing note (2.1): "Note: Many clients fail to parse a challenge that contains an unknown scheme."

OURS (conventions this module adds, each pinned by tests):
1. ASCII only. obs-text (%x80-FF) is refused everywhere, including inside quoted-string and quoted-pair. Every other non-ASCII character is refused. Membership is tested with explicit ASCII strings, never with Unicode-aware str methods.
2. Case folding. Parameter names are compared case-insensitively (2.1) for the duplicate check; the fold is an explicit ASCII A-Z to a-z map only. Returned structures preserve the original case.
3. Duplicate parameter names are refused (duplicate), applying the 2.1 "MUST only occur once" on the receiving side.
4. A comma directly after the scheme, with no SP, is refused (scheme): the optional part of a challenge or credentials requires 1*SP first. So "Basic,realm=a" is refused; at list level the comma starts a new challenge whose token is followed by "=", which is refused the same way.
5. After the 1*SP, the token68 alternative is tried first (the SOURCED order "token68 / #auth-param"). A parameter part follows the collected ABNF exactly: it may begin with a comma, but every parameter still needs its own comma, so "x ,y=1" is refused (comma) while "x ,,y=1" is accepted. Empty entries are accepted: "x ,", "x ,," and "x y=1,z=2,," are all ok.
6. HTAB is OWS (around commas, and BWS around "=") but never SP: a HTAB directly after the scheme is refused (scheme), because the grammar writes 1*SP.
7. List level (challenges_reason, the WWW-Authenticate and Proxy-Authenticate shape): empty list elements are accepted, trailing OWS after the last challenge is accepted, and a token68 may be followed by OWS before the list comma. Where a comma could either extend the parameter list or start a new challenge (the harmless ambiguity of the 4.1 note), the next token decides: followed by BWS "=" it is a parameter of the current challenge, otherwise it starts a new challenge.
8. No scheme semantics. Basic, Digest, Bearer and every other scheme are unknown tokens; the registry is not consulted; credentials are not validated; realm carries no special handling; the 401/407 status codes are out of scope.
9. List level leading OWS: challenges_reason skips OWS before the first challenge, exactly as before every later one, so "  Basic x" and "	Basic x, Digest y" are ok. challenge_reason and credentials_reason refuse any leading OWS (scheme), because their grammar starts with auth-scheme.

CAPS AND CLOSURE: TEXT_CAP is 4096 characters for every input. Lengths are checked before any content is read. The output of unquote is never longer than its input. The payload of split_challenge and split_credentials is built from slices of the input and never longer than it.

FUNCTIONS, in this order: token_reason, token68_reason, quoted_reason, unquote, param_reason, challenge_reason, credentials_reason, challenges_reason, split_challenge, split_credentials. Errors are ValueError with the text P235:<function>:<code>. A code is bad_type:<name> (exact built-in type by identity, subclasses and bool-for-int refused), bad_value:<name>.length, or bad_value:<name>.<reason>.

REASONS, in check order (the first failure decides, so a text with several faults reports the first):
- token_reason: empty, then a single left-to-right pass: char. ok otherwise.
- token68_reason: empty, then char (a character outside the 68 and "="), then padding (no base character before the first "=", or a non-"=" after the first "="). ok otherwise.
- quoted_reason: quote (the opening DQUOTE is missing, an unescaped DQUOTE appears inside, or the closing DQUOTE is missing), with a single left-to-right pass in which escape (a bad quoted-pair target) or char (a bad qdtext character) is reported at its position. ok otherwise.
- unquote: the quoted_reason reasons as bad_value:text.<reason>.
- param_reason: param.name (no name token), param.equals (no "=" after the name and BWS), param.value (no value, or a malformed token or quoted-string value), then trailing (characters after the value). ok otherwise.
- challenge_reason and credentials_reason (same grammar): scheme (no scheme token, or a character other than SP directly after it), tail (SP then nothing), then the params part after token68 fails: param.name, param.equals, param.value, comma (a comma or the end was expected), duplicate (the first repeated folded name). ok otherwise.
- challenges_reason: empty (only commas and OWS, no challenge), then per challenge: scheme, then the params-part reasons of challenge_reason with the list-level conventions of OURS 7, comma (a comma or the end of the list was expected), duplicate. ok otherwise.
- split_challenge and split_credentials: the challenge_reason reasons as bad_value:text.<reason>.

OUTPUT ORDER: split_challenge and split_credentials return a 3-tuple (scheme, kind, payload). kind is "none" (scheme only, payload None), "token68" (payload the token68 string) or "params" (payload a tuple of (name, value) pairs in order; a quoted value is unquoted, a bare token value is kept as written; names keep their original case).
"""
SCOPE = 'RFC 7235 HTTP authentication framework syntax over caller-supplied text: token, token68, quoted-string, auth-param, challenge, credentials and WWW-Authenticate lists'
NOT_CLAIMED = ('standard', 'authority', 'certification', 'currency', 'completeness', 'scheme-semantics', 'registry', 'credential-validation')
CLAIMS = {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False,
          'scheme_semantics': False, 'registry': False, 'credential_validated': False}
ADJACENT = ()
TEXT_CAP = 4096
DIGITS = '0123456789'
UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
LOWER = 'abcdefghijklmnopqrstuvwxyz'
TCHARS = DIGITS + UPPER + LOWER + "!#$%&'*+-.^_`|~"
T68 = DIGITS + UPPER + LOWER + '-._~+/'
FOLD = {}
for _i in range(26):
    FOLD[UPPER[_i]] = LOWER[_i]
del _i
_MID = '#$%&\'()*+,-./' + DIGITS + ':;<=>?@' + UPPER + '['
_TAIL = ']^_`' + LOWER + '{|}~'
QDT = '\t !' + _MID + _TAIL
VCHAR = '!"' + _MID + '\\' + _TAIL
QPT = '\t ' + VCHAR
from importlib.util import find_spec
_REG = 'app.modules.instinct_doc.p235_concepts_registry'
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != _REG or find_spec(_REG) is not None:
        raise
    def make_fail(name):
        def fail(code):
            raise ValueError('P235:' + name + ':' + code)
        return fail


def _str(fail, value, name, cap):
    if type(value) is not str:
        fail('bad_type:' + name)
    if len(value) > cap:
        fail('bad_value:' + name + '.length')


def _fold(text):
    out = ''
    for ch in text:
        if ch in FOLD:
            out += FOLD[ch]
        else:
            out += ch
    return out


def _ows_end(text, i):
    for _steps in range(len(text) + 1):
        if i == len(text) or (text[i] != ' ' and text[i] != '\t'):
            break
        i += 1
    return i


def _token_run(text, i):
    j = i
    for _steps in range(len(text) + 1):
        if j == len(text) or text[j] not in TCHARS:
            break
        j += 1
    return j


def _qd_ok(ch):
    return ch in QDT


def _qp_ok(ch):
    return ch in QPT


def _t68_ok(seg):
    if seg == '' or seg[0] not in T68:
        return False
    seen = False
    for ch in seg:
        if ch == '=':
            seen = True
        elif ch in T68:
            if seen:
                return False
        else:
            return False
    return True


def _quoted_end(text, i):
    # text[i] is the opening DQUOTE; returns the index just past the closing
    # DQUOTE, or -1 when the quoted-string is malformed.
    j = i + 1
    for _steps in range(len(text) + 1):
        if j == len(text):
            return -1
        ch = text[j]
        if ch == '"':
            return j + 1
        if ch == '\\':
            if j + 1 >= len(text) or not _qp_ok(text[j + 1]):
                return -1
            j += 2
        elif _qd_ok(ch):
            j += 1
        else:
            return -1
    return -1


def _quoted(text):
    if len(text) < 2 or text[0] != '"':
        return 'quote'
    i = 1
    for _steps in range(len(text) + 1):
        if i == len(text):
            return 'quote'
        ch = text[i]
        if ch == '"':
            if i == len(text) - 1:
                return 'ok'
            return 'quote'
        if ch == '\\':
            if i + 1 >= len(text):
                return 'quote'
            if not _qp_ok(text[i + 1]):
                return 'escape'
            i += 2
        elif _qd_ok(ch):
            i += 1
        else:
            return 'char'
    return 'quote'


def _param_at(text, i):
    # Parses one auth-param at i. Returns (reason, next) with next just past
    # the value on success, or (reason, -1) on failure.
    j = _token_run(text, i)
    if j == i:
        return ('param.name', -1)
    j = _ows_end(text, j)
    if j >= len(text) or text[j] != '=':
        return ('param.equals', -1)
    j = _ows_end(text, j + 1)
    if j >= len(text):
        return ('param.value', -1)
    if text[j] == '"':
        k = _quoted_end(text, j)
        if k < 0:
            return ('param.value', -1)
        return ('ok', k)
    k = _token_run(text, j)
    if k == j:
        return ('param.value', -1)
    return ('ok', k)


def _param_parts(text, i):
    # Same scan as _param_at, returning (name, value); valid only after
    # _param_at returned ok.
    j = _token_run(text, i)
    name = text[i:j]
    j = _ows_end(text, j)
    j = _ows_end(text, j + 1)
    if text[j] == '"':
        out = ''
        k = j + 1
        for _steps in range(len(text) + 1):
            if text[k] == '"':
                return (name, out)
            if text[k] == '\\':
                out += text[k + 1]
                k += 2
            else:
                out += text[k]
                k += 1
        return (name, out)
    k = _token_run(text, j)
    return (name, text[j:k])


def _auth_parse(text):
    # Parses one challenge or credentials value (same grammar). Returns
    # ('ok', scheme, kind, payload) with kind 'none', 'token68' or 'params',
    # or (reason, None, None, None).
    j = _token_run(text, 0)
    if j == 0:
        return ('scheme', None, None, None)
    scheme = text[:j]
    if j == len(text):
        return ('ok', scheme, 'none', None)
    if text[j] != ' ':
        return ('scheme', None, None, None)
    j += 1
    for _steps in range(len(text) + 1):
        if j == len(text) or text[j] != ' ':
            break
        j += 1
    if j == len(text):
        return ('tail', None, None, None)
    rest = text[j:]
    if _t68_ok(rest):
        return ('ok', scheme, 'token68', rest)
    names = []
    parts = []
    pos = 0
    if rest[0] == ',':
        pos = 1
    else:
        reason, k = _param_at(rest, 0)
        if reason != 'ok':
            return (reason, None, None, None)
        nm, val = _param_parts(rest, 0)
        names += [_fold(nm)]
        parts += [(nm, val)]
        pos = k
    for _steps in range(len(rest) + 1):
        pos = _ows_end(rest, pos)
        if pos == len(rest):
            break
        if rest[pos] != ',':
            return ('comma', None, None, None)
        pos = _ows_end(rest, pos + 1)
        if pos == len(rest):
            break
        if rest[pos] == ',':
            continue
        reason, k = _param_at(rest, pos)
        if reason != 'ok':
            return (reason, None, None, None)
        nm, val = _param_parts(rest, pos)
        fn = _fold(nm)
        if fn in names:
            return ('duplicate', None, None, None)
        names += [fn]
        parts += [(nm, val)]
        pos = k
    return ('ok', scheme, 'params', tuple(parts))


def token_reason(text):
    fail = make_fail('token_reason')
    _str(fail, text, 'text', TEXT_CAP)
    if text == '':
        return 'empty'
    for ch in text:
        if ch not in TCHARS:
            return 'char'
    return 'ok'


def token68_reason(text):
    fail = make_fail('token68_reason')
    _str(fail, text, 'text', TEXT_CAP)
    if text == '':
        return 'empty'
    for ch in text:
        if ch != '=' and ch not in T68:
            return 'char'
    i = 0
    for _steps in range(len(text) + 1):
        if i == len(text) or text[i] not in T68:
            break
        i += 1
    if i == 0:
        return 'padding'
    for _steps in range(len(text) + 1):
        if i == len(text):
            return 'ok'
        if text[i] != '=':
            return 'padding'
        i += 1
    return 'padding'


def quoted_reason(text):
    fail = make_fail('quoted_reason')
    _str(fail, text, 'text', TEXT_CAP)
    return _quoted(text)


def unquote(text):
    fail = make_fail('unquote')
    _str(fail, text, 'text', TEXT_CAP)
    reason = _quoted(text)
    if reason != 'ok':
        fail('bad_value:text.' + reason)
    out = ''
    i = 1
    for _steps in range(len(text) + 1):
        if i == len(text) - 1:
            break
        if text[i] == '\\':
            out += text[i + 1]
            i += 2
        else:
            out += text[i]
            i += 1
    return out


def param_reason(text):
    fail = make_fail('param_reason')
    _str(fail, text, 'text', TEXT_CAP)
    reason, k = _param_at(text, 0)
    if reason != 'ok':
        return reason
    if k != len(text):
        return 'trailing'
    return 'ok'


def challenge_reason(text):
    fail = make_fail('challenge_reason')
    _str(fail, text, 'text', TEXT_CAP)
    reason, _scheme, _kind, _payload = _auth_parse(text)
    return reason


def credentials_reason(text):
    fail = make_fail('credentials_reason')
    _str(fail, text, 'text', TEXT_CAP)
    reason, _scheme, _kind, _payload = _auth_parse(text)
    return reason


def challenges_reason(text):
    fail = make_fail('challenges_reason')
    _str(fail, text, 'text', TEXT_CAP)
    pos = 0
    for _steps in range(len(text) + 1):
        pos = _ows_end(text, pos)
        if pos == len(text):
            return 'empty'
        if text[pos] != ',':
            break
        pos += 1
    first = True
    for _steps in range(len(text) + 1):
        if pos == len(text):
            return 'ok'
        if not first:
            pos = _ows_end(text, pos)
            if pos == len(text):
                return 'ok'
            if text[pos] != ',':
                return 'comma'
            pos = _ows_end(text, pos + 1)
            if pos == len(text):
                return 'ok'
            if text[pos] == ',':
                continue
        first = False
        j = _token_run(text, pos)
        if j == pos:
            return 'scheme'
        if j == len(text):
            return 'ok'
        ch = text[j]
        if ch == ',':
            pos = j
            continue
        if ch == '\t':
            t2 = _ows_end(text, j)
            if t2 == len(text):
                return 'ok'
            if text[t2] == ',':
                pos = j
                continue
            return 'scheme'
        if ch != ' ':
            return 'scheme'
        k = j + 1
        for _steps in range(len(text) + 1):
            if k == len(text) or text[k] != ' ':
                break
            k += 1
        if k == len(text) or text[k] == ',':
            pos = j
            continue
        m = k
        for _steps in range(len(text) + 1):
            if m == len(text) or text[m] == ',':
                break
            m += 1
        e = m
        for _steps in range(len(text) + 1):
            if e == k or (text[e - 1] != ' ' and text[e - 1] != '\t'):
                break
            e -= 1
        if _t68_ok(text[k:e]):
            pos = m
            continue
        names = []
        reason, q = _param_at(text, k)
        if reason != 'ok':
            return reason
        nm, _val = _param_parts(text, k)
        fn = _fold(nm)
        if fn in names:
            return 'duplicate'
        names += [fn]
        p = q
        for _steps in range(len(text) + 1):
            p = _ows_end(text, p)
            if p == len(text):
                return 'ok'
            if text[p] != ',':
                return 'comma'
            t = _ows_end(text, p + 1)
            if t == len(text):
                return 'ok'
            if text[t] == ',':
                p = t
                continue
            a = _token_run(text, t)
            if a == t:
                pos = p
                break
            b = _ows_end(text, a)
            if b < len(text) and text[b] == '=':
                reason, q = _param_at(text, t)
                if reason != 'ok':
                    return reason
                nm, _val = _param_parts(text, t)
                fn = _fold(nm)
                if fn in names:
                    return 'duplicate'
                names += [fn]
                p = q
                continue
            pos = p
            break
    return 'comma'


def split_challenge(text):
    fail = make_fail('split_challenge')
    _str(fail, text, 'text', TEXT_CAP)
    reason, scheme, kind, payload = _auth_parse(text)
    if reason != 'ok':
        fail('bad_value:text.' + reason)
    return (scheme, kind, payload)


def split_credentials(text):
    fail = make_fail('split_credentials')
    _str(fail, text, 'text', TEXT_CAP)
    reason, scheme, kind, payload = _auth_parse(text)
    if reason != 'ok':
        fail('bad_value:text.' + reason)
    return (scheme, kind, payload)
