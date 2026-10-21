"""Tests for p235 concepts batch 1123: RFC 7235 HTTP authentication framework syntax. Pure functions over caller data; claims asserted False."""
import ast
import builtins
import importlib.util
import inspect
import os
import re
import signal
import subprocess
import sys
import tracemalloc
import traceback
import types
import unicodedata

import pytest
import random
from importlib.util import find_spec

REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1123_httpauth'
NAMES = ('token_reason', 'token68_reason', 'quoted_reason', 'unquote', 'param_reason', 'challenge_reason', 'credentials_reason',
         'challenges_reason', 'split_challenge', 'split_credentials')
PRIVATE = ('_str', '_fold', '_ows_end', '_token_run', '_qd_ok', '_qp_ok', '_t68_ok', '_quoted_end', '_quoted', '_param_at', '_param_parts',
           '_auth_parse')
DOC_EXACT = 'p235 concepts batch 1123 (rev 0): RFC 7235 HTTP authentication framework syntax. Pure functions over caller-supplied text. No retrieval, no network, no clock. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete, has no scheme semantics, does not consult the registry and does not validate credentials. ADJACENT is the empty tuple.\n\nLIVE-READ SOURCES (read live, quoted verbatim below and mechanically matched against the whitespace-collapsed RFC text with the page headers and footers removed):\n- RFC 7235, Hypertext Transfer Protocol (HTTP/1.1): Authentication, Standards Track, June 2014. rfc7235.txt is 38142 bytes, sha256 abfb45a43fdebffc640b51fae46f480e65fc01238f244f94b1bcf2c20da0b862.\n- RFC 7230, Hypertext Transfer Protocol (HTTP/1.1): Message Syntax and Routing, June 2014, for the imported ABNF (BWS, OWS, token, quoted-string, the #rule). rfc7230.txt is 205947 bytes, sha256 c7fdc8bebdf1f8195f731592c47f5ea822b489436fd905b01b55ef531fca4120.\n- The rfc-editor info page for RFC 7235 says "This RFC is now obsolete, see RFC 9110" and lists Obsoleted by (1): RFC 9110 (HTTP Semantics). It lists Obsoletes (2): RFC 2616 and RFC 2617. The RFC header itself says "Obsoletes: 2616" and "Updates: 2617". The page shows no Updated by entry. This module therefore targets a superseded document: it implements RFC 7235 as assigned, applies none of RFC 9110\'s changes, and CLAIMS current is False.\n- errata.json (sha256 2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) records 1 erratum for RFC 7235: 6307 (Rejected, Technical, section 2.1, about the case-insensitive token). It records 24 errata for RFC 7230; the ones touching the sections used here: 4050 (Verified, Editorial, 3.2.4: "response code" versus "status code"); 5163 (Held for Document Update, Technical, 3.2.4: linear whitespace and obs-fold); 4189 (Held for Document Update, Technical, 3.2: the general field-value rule); 4891 (Held for Document Update, Editorial, 3.2.6: a missing space in the qdtext rule); 6333 (Rejected, Technical, 3.2.6 PDF: curly quotes in the PDF only, the text version is correct); 4169 (Verified, Technical, 7: a legacy-list derivation corner with trailing whitespace); 5257 (Held for Document Update, Technical, 7: #element versus 1#element for a leading comma). Both counts are taken from that single JSON index and are not independently confirmed against the per-erratum pages. OURS: no erratum is applied. The RFC text and its collected ABNF decide.\n\nSOURCED (the RFC text):\n- Scheme, parameters and token68 (2.1): "auth-scheme = token" "auth-param = token BWS "=" BWS ( token / quoted-string )" "token68 = 1*( ALPHA / DIGIT / "-" / "." / "_" / "~" / "+" / "/" ) *"=""\n- Challenge and credentials (2.1): "challenge = auth-scheme [ 1*SP ( token68 / #auth-param ) ]" "credentials = auth-scheme [ 1*SP ( token68 / #auth-param ) ]"\n- Parameter names (2.1): "Authentication parameters are name=value pairs, where the name token is matched case-insensitively, and each parameter name MUST only occur once per challenge."\n- Field values (4.1-4.4): "WWW-Authenticate = 1#challenge" "Authorization = credentials" "Proxy-Authenticate = 1#challenge" "Proxy-Authorization = credentials"\n- List parsing caution (4.1): "User agents are advised to take special care in parsing the field value, as it might contain more than one challenge, and each challenge can contain a comma-separated list of authentication parameters."\n- The empty-entry ambiguity (4.1 note): "Therefore, a sequence of comma, whitespace, and comma can be considered either as applying to the preceding challenge, or to be an empty entry in the list of challenges. In practice, this ambiguity does not affect the semantics of the header field value and thus is harmless."\n- The 4.1 example: "WWW-Authenticate: Newauth realm="apps", type=1," "title="Login to \\"apps\\"", Basic realm="simple""\n- token68 rationale (2.1): "The token68 syntax allows the 66 unreserved URI characters ([RFC3986]), plus a few others, so that it can hold a base64, base64url (URL and filename safe alphabet), base32, or base16 (hex) encoding, with or without padding, but excluding whitespace ([RFC4648])."\n- Header purposes: "The "WWW-Authenticate" header field indicates the authentication scheme(s) and parameters applicable to the target resource." "The "Authorization" header field allows a user agent to authenticate itself with an origin server"\n- Imported ABNF (RFC 7230 3.2.3, 3.2.6): "OWS = *( SP / HTAB )" "BWS = OWS" "token = 1*tchar" "tchar = "!" / "#" / "$" / "%" / "&" / "\'" / "*" / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA" "quoted-string = DQUOTE *( qdtext / quoted-pair ) DQUOTE" "qdtext = HTAB / SP /%x21 / %x23-5B / %x5D-7E / obs-text" "quoted-pair = "\\" ( HTAB / SP / VCHAR / obs-text )"\n- Collected ABNF (RFC 7235 Appendix C): "Proxy-Authenticate = *( "," OWS ) challenge *( OWS "," [ OWS challenge ] )" "WWW-Authenticate = *( "," OWS ) challenge *( OWS "," [ OWS challenge ] )" "challenge = auth-scheme [ 1*SP ( token68 / [ ( "," / auth-param ) *( OWS "," [ OWS auth-param ] ) ] ) ]"\n- Status use (2.1): "A 401 (Unauthorized) response message is used by an origin server to challenge the authorization of a user agent"\n- Client parsing note (2.1): "Note: Many clients fail to parse a challenge that contains an unknown scheme."\n\nOURS (conventions this module adds, each pinned by tests):\n1. ASCII only. obs-text (%x80-FF) is refused everywhere, including inside quoted-string and quoted-pair. Every other non-ASCII character is refused. Membership is tested with explicit ASCII strings, never with Unicode-aware str methods.\n2. Case folding. Parameter names are compared case-insensitively (2.1) for the duplicate check; the fold is an explicit ASCII A-Z to a-z map only. Returned structures preserve the original case.\n3. Duplicate parameter names are refused (duplicate), applying the 2.1 "MUST only occur once" on the receiving side.\n4. A comma directly after the scheme, with no SP, is refused (scheme): the optional part of a challenge or credentials requires 1*SP first. So "Basic,realm=a" is refused; at list level the comma starts a new challenge whose token is followed by "=", which is refused the same way.\n5. After the 1*SP, the token68 alternative is tried first (the SOURCED order "token68 / #auth-param"). A parameter part follows the collected ABNF exactly: it may begin with a comma, but every parameter still needs its own comma, so "x ,y=1" is refused (comma) while "x ,,y=1" is accepted. Empty entries are accepted: "x ,", "x ,," and "x y=1,z=2,," are all ok.\n6. HTAB is OWS (around commas, and BWS around "=") but never SP: a HTAB directly after the scheme is refused (scheme), because the grammar writes 1*SP.\n7. List level (challenges_reason, the WWW-Authenticate and Proxy-Authenticate shape): empty list elements are accepted, trailing OWS after the last challenge is accepted, and a token68 may be followed by OWS before the list comma. Where a comma could either extend the parameter list or start a new challenge (the harmless ambiguity of the 4.1 note), the next token decides: followed by BWS "=" it is a parameter of the current challenge, otherwise it starts a new challenge.\n8. No scheme semantics. Basic, Digest, Bearer and every other scheme are unknown tokens; the registry is not consulted; credentials are not validated; realm carries no special handling; the 401/407 status codes are out of scope.\n9. List level leading OWS: challenges_reason skips OWS before the first challenge, exactly as before every later one, so "  Basic x" and "\tBasic x, Digest y" are ok. challenge_reason and credentials_reason refuse any leading OWS (scheme), because their grammar starts with auth-scheme.\n\nCAPS AND CLOSURE: TEXT_CAP is 4096 characters for every input. Lengths are checked before any content is read. The output of unquote is never longer than its input. The payload of split_challenge and split_credentials is built from slices of the input and never longer than it.\n\nFUNCTIONS, in this order: token_reason, token68_reason, quoted_reason, unquote, param_reason, challenge_reason, credentials_reason, challenges_reason, split_challenge, split_credentials. Errors are ValueError with the text P235:<function>:<code>. A code is bad_type:<name> (exact built-in type by identity, subclasses and bool-for-int refused), bad_value:<name>.length, or bad_value:<name>.<reason>.\n\nREASONS, in check order (the first failure decides, so a text with several faults reports the first):\n- token_reason: empty, then a single left-to-right pass: char. ok otherwise.\n- token68_reason: empty, then char (a character outside the 68 and "="), then padding (no base character before the first "=", or a non-"=" after the first "="). ok otherwise.\n- quoted_reason: quote (the opening DQUOTE is missing, an unescaped DQUOTE appears inside, or the closing DQUOTE is missing), with a single left-to-right pass in which escape (a bad quoted-pair target) or char (a bad qdtext character) is reported at its position. ok otherwise.\n- unquote: the quoted_reason reasons as bad_value:text.<reason>.\n- param_reason: param.name (no name token), param.equals (no "=" after the name and BWS), param.value (no value, or a malformed token or quoted-string value), then trailing (characters after the value). ok otherwise.\n- challenge_reason and credentials_reason (same grammar): scheme (no scheme token, or a character other than SP directly after it), tail (SP then nothing), then the params part after token68 fails: param.name, param.equals, param.value, comma (a comma or the end was expected), duplicate (the first repeated folded name). ok otherwise.\n- challenges_reason: empty (only commas and OWS, no challenge), then per challenge: scheme, then the params-part reasons of challenge_reason with the list-level conventions of OURS 7, comma (a comma or the end of the list was expected), duplicate. ok otherwise.\n- split_challenge and split_credentials: the challenge_reason reasons as bad_value:text.<reason>.\n\nOUTPUT ORDER: split_challenge and split_credentials return a 3-tuple (scheme, kind, payload). kind is "none" (scheme only, payload None), "token68" (payload the token68 string) or "params" (payload a tuple of (name, value) pairs in order; a quoted value is unquoted, a bare token value is kept as written; names keep their original case).\n'
QUOTES = ['auth-scheme = token', 'auth-param = token BWS "=" BWS ( token / quoted-string )', 'token68 = 1*( ALPHA / DIGIT / "-" / "." / "_" / "~" / "+" / "/" ) *"="', 'WWW-Authenticate = 1#challenge', 'Authorization = credentials', 'Proxy-Authenticate = 1#challenge', 'Proxy-Authorization = credentials', 'challenge = auth-scheme [ 1*SP ( token68 / #auth-param ) ]', 'credentials = auth-scheme [ 1*SP ( token68 / #auth-param ) ]', 'Authentication parameters are name=value pairs, where the name token is matched case-insensitively, and each parameter name MUST only occur once per challenge.', 'Therefore, a sequence of comma, whitespace, and comma can be considered either as applying to the preceding challenge, or to be an empty entry in the list of challenges. In practice, this ambiguity does not affect the semantics of the header field value and thus is harmless.', 'User agents are advised to take special care in parsing the field value, as it might contain more than one challenge, and each challenge can contain a comma-separated list of authentication parameters.', 'WWW-Authenticate: Newauth realm="apps", type=1,', 'title="Login to \\"apps\\"", Basic realm="simple"', 'The token68 syntax allows the 66 unreserved URI characters ([RFC3986]), plus a few others, so that it can hold a base64, base64url (URL and filename safe alphabet), base32, or base16 (hex) encoding, with or without padding, but excluding whitespace ([RFC4648]).', 'The "WWW-Authenticate" header field indicates the authentication scheme(s) and parameters applicable to the target resource.', 'The "Authorization" header field allows a user agent to authenticate itself with an origin server', 'Proxy-Authenticate = *( "," OWS ) challenge *( OWS "," [ OWS challenge ] )', 'challenge = auth-scheme [ 1*SP ( token68 / [ ( "," / auth-param ) *( OWS "," [ OWS auth-param ] ) ] ) ]', 'A 401 (Unauthorized) response message is used by an origin server to challenge the authorization of a user agent', 'Note: Many clients fail to parse a challenge that contains an unknown scheme.', 'OWS = *( SP / HTAB )', 'BWS = OWS', 'token = 1*tchar', 'tchar = "!" / "#" / "$" / "%" / "&" / "\'" / "*" / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA', 'quoted-string = DQUOTE *( qdtext / quoted-pair ) DQUOTE', 'qdtext = HTAB / SP /%x21 / %x23-5B / %x5D-7E / obs-text', 'quoted-pair = "\\" ( HTAB / SP / VCHAR / obs-text )', 'WWW-Authenticate = *( "," OWS ) challenge *( OWS "," [ OWS challenge ] )']
HERE = os.path.dirname(os.path.abspath(__file__))
import app.modules.instinct_doc.p235_concepts_batch1123_httpauth as m  # noqa: E402
MODPATH = m.__file__


def _prefix():
    spec = importlib.util.spec_from_file_location('b1123_pfx', MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        return str(e)[:-len('x:c')]


PFX = _prefix()


class _Alarm(AssertionError):
    pass


@pytest.fixture(autouse=True)
def _alarm():
    def handler(signum, frame):
        raise _Alarm('ALARM2S test exceeded 2 seconds')
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 2.0)
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, old)


@pytest.fixture
def mp(monkeypatch):
    return monkeypatch


def fresh(name='b1123_fresh'):
    spec = importlib.util.spec_from_file_location(name, MODPATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod




def E(fn, code):
    return ('err', PFX + fn + ':' + code)


def run(fn, *args, mod=None):
    try:
        return ('ok', getattr(mod or m, fn)(*args))
    except ValueError as e:
        return ('err', str(e))


# ---- independent oracle (regex from the ABNF, plus a split-based list parser, built separately from the module's loops) ----
_TOK = r"[A-Za-z0-9!#$%&'*+\-.^_`|~]"
_T68 = r"[A-Za-z0-9\-._~+/]"
_QS = r'"(?:[\t\x20\x21\x23-\x5B\x5D-\x7E]|\\[\t\x20-\x7E])*"'
_BWS = r"[ \t]*"
_PARAM = _TOK + r"+" + _BWS + r"=" + _BWS + r"(?:" + _TOK + r"+|" + _QS + r")"
_PARAMS = r"(?:,|" + _PARAM + r")(?:[ \t]*,(?:[ \t]*" + _PARAM + r")?)*"
_AUTH = re.compile(_TOK + r"+(?: +(?:" + _T68 + r"+=*|" + _PARAMS + r"))?", re.S)
_TOKRE = re.compile(_TOK + r"+", re.S)
_T68RE = re.compile(_T68 + r"+=*", re.S)
_QSRE = re.compile(_QS, re.S)
_PARAMRE = re.compile(_PARAM, re.S)


def o_token(t):
    return _TOKRE.fullmatch(t) is not None


def o_t68(t):
    return _T68RE.fullmatch(t) is not None


def o_qs(t):
    return _QSRE.fullmatch(t) is not None


def o_param(t):
    return _PARAMRE.fullmatch(t) is not None


def _o_params_rest(r):
    i = 0
    if r.startswith(','):
        i = 1
    else:
        m0 = _PARAMRE.match(r, 0)
        if m0 is None:
            return False
        i = m0.end()
    while True:
        while i < len(r) and r[i] in ' \t':
            i += 1
        if i == len(r):
            return True
        if r[i] != ',':
            return False
        i += 1
        while i < len(r) and r[i] in ' \t':
            i += 1
        if i == len(r):
            return True
        if r[i] == ',':
            continue
        m0 = _PARAMRE.match(r, i)
        if m0 is None:
            return False
        i = m0.end()


def o_auth(t):
    m0 = _TOKRE.match(t, 0)
    if m0 is None:
        return False
    j = m0.end()
    if j == len(t):
        return True
    if t[j] != ' ':
        return False
    while j < len(t) and t[j] == ' ':
        j += 1
    if j == len(t):
        return False
    rest = t[j:]
    if _T68RE.fullmatch(rest) is not None:
        return True
    return _o_params_rest(rest)


def _seg_split(t):
    # split at commas outside quoted-strings; False when a quote never closes
    parts = []
    cur = ''
    i = 0
    while i < len(t):
        c = t[i]
        if c == ',':
            parts.append(cur)
            cur = ''
            i += 1
        elif c == '"':
            j = i + 1
            closed = False
            while j < len(t):
                if t[j] == '\\':
                    j += 2
                    continue
                if t[j] == '"':
                    closed = True
                    j += 1
                    break
                j += 1
            if not closed:
                return False
            cur += t[i:j]
            i = j
        else:
            cur += c
            i += 1
    parts.append(cur)
    return parts


def _strip_ows(s):
    a = 0
    while a < len(s) and (s[a] == ' ' or s[a] == '\t'):
        a += 1
    b = len(s)
    while b > a and (s[b - 1] == ' ' or s[b - 1] == '\t'):
        b -= 1
    return s[a:b]


def o_list(t):
    segs = _seg_split(t)
    if segs is False:
        return False
    seen = False
    cur_params = False
    for raw in segs:
        s = _strip_ows(raw)
        if s == '':
            continue
        mt = _TOKRE.match(s)
        if mt is None:
            return False
        b = mt.end()
        while b < len(s) and (s[b] == ' ' or s[b] == '\t'):
            b += 1
        if b < len(s) and s[b] == '=':
            if not (seen and cur_params):
                return False
            if not o_param(s):
                return False
            continue
        if not o_auth(s):
            return False
        seen = True
        j = mt.end()
        if j < len(s) and s[j] == ' ':
            k = j
            while k < len(s) and s[k] == ' ':
                k += 1
            cur_params = _T68RE.fullmatch(s[k:]) is None
        else:
            cur_params = False
    return seen


def o_split(t):
    # structural oracle for split_challenge/split_credentials
    if not o_auth(t):
        return None
    mt = _TOKRE.match(t)
    scheme = t[:mt.end()]
    if mt.end() == len(t):
        return (scheme, 'none', None)
    k = mt.end() + 1
    while k < len(t) and t[k] == ' ':
        k += 1
    rest = t[k:]
    if _T68RE.fullmatch(rest):
        return (scheme, 'token68', rest)
    parts = []
    for raw in _seg_split(rest):
        seg = _strip_ows(raw)
        if seg == '':
            continue
        pm = _PARAMRE.match(seg)
        name = pm.group(0)[:_TOKRE.match(seg).end()]
        v = seg[pm.group(0).index('=', len(name)) + 1:]
        a = 0
        while a < len(v) and (v[a] == ' ' or v[a] == '\t'):
            a += 1
        v = v[a:]
        if v[0] == '"':
            out = ''
            q = 1
            while v[q] != '"':
                if v[q] == '\\':
                    out += v[q + 1]
                    q += 2
                else:
                    out += v[q]
                    q += 1
            parts.append((name, out))
        else:
            parts.append((name, v))
    return (scheme, 'params', tuple(parts))


LOOKALIKES = ['\u0663', '\uff11', '\u00b2', '\u212a', '\u0131', '\u017f', '\u0660', '\u2467', '\u00a0', '\u2003', '\uff21', '\u0130', '\u037e', '\uff1b', '\uff1d',
              '\u201c', '\u2033', '\u2215', '\u2028', '\u0085', '\u1680', '\uff0c', '\uff01', '\uff1a', '\u212b', '\u2126', '\u1e9e', '\ufb01', '\uff0e', '\u2024',
              '\uff3f', '\u2010', '\u2212', '\uff5e', '\u2018', '\u2019', '\uff02', '\uff0f', '\uff1f', '\uff03', '\uff05', '\uff3b', '\uff3d', '\u2044', '\u00e9']
ARGSPEC = {'token_reason': [('text', 'Basic')], 'token68_reason': [('text', 'x==')], 'quoted_reason': [('text', '"a"')],
           'unquote': [('text', '"a"')], 'param_reason': [('text', 'a=1')],
           'challenge_reason': [('text', 'Basic realm="a"')], 'credentials_reason': [('text', 'Digest x==')],
           'challenges_reason': [('text', 'Basic x, Digest y')],
           'split_challenge': [('text', 'Basic realm="a"')], 'split_credentials': [('text', 'Digest x==')]}


# ---- hostile values ----------------------------------------------------------------------------------------------
class S(str):
    pass


class T(tuple):
    pass


class Meta(type):
    def __eq__(cls, other):
        return True

    def __hash__(cls):
        return 1


class SM(str, metaclass=Meta):
    pass


class EqAll(str):
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __hash__(self):
        return 0


class BoolLike(int):
    pass


STR_HOSTILE = [S('g'), SM('g'), EqAll('g')]
JUNK = [None, 1, 0, True, False, 1.5, b'g', bytearray(b'g'), ['g'], {'g': 1}, {'g'}, object(), [], (lambda: 1), ('g',)]


# ---- constants, shape ----------------------------------------------------------------------------------------------
def test_constants_exact():
    assert m.SCOPE == 'RFC 7235 HTTP authentication framework syntax over caller-supplied text: token, token68, quoted-string, auth-param, challenge, credentials and WWW-Authenticate lists'
    assert m.NOT_CLAIMED == ('standard', 'authority', 'certification', 'currency', 'completeness', 'scheme-semantics', 'registry', 'credential-validation')
    assert m.CLAIMS == {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False,
                        'scheme_semantics': False, 'registry': False, 'credential_validated': False}
    assert all(v is False for v in m.CLAIMS.values()) and m.ADJACENT == () and type(m.ADJACENT) is tuple and m.TEXT_CAP == 4096
    assert m.DIGITS == '0123456789' and m.UPPER == 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' and m.LOWER == 'abcdefghijklmnopqrstuvwxyz' and m._REG == REG
    assert m.TCHARS == m.DIGITS + m.UPPER + m.LOWER + "!#$%&'*+-.^_`|~" and m.T68 == m.DIGITS + m.UPPER + m.LOWER + '-._~+/'
    assert len(m.TCHARS) == 77 and len(m.T68) == 68 and len(set(m.TCHARS)) == 77 and len(set(m.T68)) == 68
    assert m.FOLD == {m.UPPER[i]: m.LOWER[i] for i in range(26)} and len(m.FOLD) == 26
    assert m._MID == '#$%&\'()*+,-./' + m.DIGITS + ':;<=>?@' + m.UPPER + '[' and len(m._MID) == 57
    assert m._TAIL == ']^_`' + m.LOWER + '{|}~' and len(m._TAIL) == 34
    assert m.QDT == '\t !' + m._MID + m._TAIL and m.VCHAR == '!"' + m._MID + '\\' + m._TAIL and m.QPT == '\t ' + m.VCHAR
    assert (len(m.QDT), len(m.VCHAR), len(m.QPT)) == (94, 94, 96)
    assert len(set(m.QDT)) == 94 and len(set(m.VCHAR)) == 94 and len(set(m.QPT)) == 96
    assert set(m.QDT) < set(m.QPT) and set(m.VCHAR) < set(m.QPT)


@pytest.mark.parametrize('i', range(256))
def test_char_classes_and_reason_for_every_code(i):
    c = chr(i)
    assert (c in m.TCHARS) == (re.fullmatch(r"[A-Za-z0-9!#$%&'*+\-.^_`|~]", c) is not None), i
    assert (c in m.T68) == (re.fullmatch(r'[A-Za-z0-9\-._~+/]', c) is not None), i
    assert (c in m.FOLD) == (c in m.UPPER)
    assert (c in m.QDT) == (c in '\t ' or c == '!' or (0x23 <= i <= 0x5B) or (0x5D <= i <= 0x7E)), i
    assert (c in m.QPT) == (c == '\t' or 0x20 <= i <= 0x7E), i
    assert m.token_reason(c) == ('ok' if c in m.TCHARS else 'char'), i
    assert m.token68_reason(c) == ('ok' if c in m.T68 else ('padding' if c == '=' else 'char')), i
    if c in ('"', '\\'):
        want_q = 'quote'
    elif c in m.QDT:
        want_q = 'ok'
    else:
        want_q = 'char'
    assert m.quoted_reason('"' + c + '"') == want_q, i
    assert m.param_reason('a' + c + 'b=1') == ('ok' if c in m.TCHARS else ('trailing' if c == '=' else 'param.equals')), i
    assert m.param_reason('a=b' + c) == ('ok' if c in m.TCHARS else 'trailing'), i
    assert m.challenge_reason('Basic' + c) == ('ok' if c in m.TCHARS else ('tail' if c == ' ' else 'scheme')), i
    if c == ' ':
        want_sp = 'tail'
    elif c in m.T68 or c == ',':
        want_sp = 'ok'
    elif c in m.TCHARS:
        want_sp = 'param.equals'
    else:
        want_sp = 'param.name'
    assert m.challenge_reason('Basic ' + c) == want_sp, i
    assert m.credentials_reason('Basic ' + c) == want_sp, i
    assert m.challenges_reason('Basic' + c) == ('ok' if c in (m.TCHARS + ', \t') else 'scheme'), i
    assert m.challenges_reason('x a=1' + c) == ('ok' if c in (m.TCHARS + ', \t') else 'comma'), i


@pytest.mark.parametrize('ch', LOOKALIKES)
def test_lookalikes_are_refused_everywhere(ch):
    for st in (m.TCHARS, m.T68, m.QDT, m.QPT, m.VCHAR, m.DIGITS, m.UPPER, m.LOWER):
        assert ch not in st
    assert ch not in m.FOLD
    assert m.token_reason('a' + ch) == 'char' and m.token68_reason('a' + ch) == 'char'
    assert m.quoted_reason('"' + ch + '"') == 'char'
    assert m.param_reason('a' + ch + '=1') == 'param.equals' and m.param_reason('a=b' + ch) == 'trailing'
    assert m.challenge_reason('Basic' + ch) == 'scheme' and m.credentials_reason('Basic' + ch) == 'scheme'
    assert m.challenges_reason('Basic' + ch) == 'scheme'
    assert m.challenge_reason('Basic ' + ch) == 'param.name'
    assert run('unquote', '"a' + ch + '"') == E('unquote', 'bad_value:text.char')
    assert run('split_challenge', 'Basic ' + ch) == E('split_challenge', 'bad_value:text.param.name')
    assert run('split_credentials', 'Basic' + ch) == E('split_credentials', 'bad_value:text.scheme')


NDS = [chr(i) for i in range(sys.maxunicode + 1) if unicodedata.category(chr(i)) == 'Nd' and i > 127]


def test_every_unicode_decimal_digit_is_refused_in_every_slot():
    assert len(NDS) > 500
    for d in NDS:
        assert m.token_reason('a' + d) == 'char' and m.token68_reason('a' + d) == 'char'
        assert m.quoted_reason('"' + d + '"') == 'char'
        assert m.param_reason('a=b' + d) == 'trailing' and m.param_reason('a' + d + '=1') == 'param.equals'
        assert m.challenge_reason('Basic' + d) == 'scheme' and m.challenges_reason('Basic' + d) == 'scheme'


def test_order_docstrings_and_private_names():
    fns = [n for n, v in vars(m).items() if inspect.isfunction(v) and v.__module__ == m.__name__ and not n.startswith('_') and n != 'make_fail']
    assert tuple(fns) == NAMES
    for n in NAMES + PRIVATE + ('make_fail',):
        assert getattr(m, n).__doc__ is None, n
    assert m.__doc__ == DOC_EXACT
    for n in PRIVATE:
        assert inspect.isfunction(getattr(m, n))
    priv = tuple(n for n, v in vars(m).items() if inspect.isfunction(v) and v.__module__ == m.__name__ and n.startswith('_'))
    assert priv == PRIVATE


def test_header_quotes_are_in_the_header_and_distinct():
    flat = re.sub(r'\s+', ' ', m.__doc__)
    assert len(QUOTES) == 29 and len(set(QUOTES)) == 29
    for q in QUOTES:
        assert re.sub(r'\s+', ' ', q) in flat, q


def test_header_names_every_erratum_source_and_function():
    d = m.__doc__
    for tok in ('6307', '4050', '4169', '5257', '4891', '6333', '5163', '4189', '1 erratum', '24 errata', 'RFC 9110', 'RFC 2616', 'RFC 2617',
                'abfb45a43fdebffc640b51fae46f480e65fc01238f244f94b1bcf2c20da0b862', 'c7fdc8bebdf1f8195f731592c47f5ea822b489436fd905b01b55ef531fca4120',
                '2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66', '38142 bytes', '205947 bytes',
                'Obsoleted by'):
        assert tok in d, tok
    for n in NAMES:
        assert n in d, n
    for r in ('empty', 'char', 'padding', 'quote', 'escape', 'scheme', 'tail', 'comma', 'duplicate', 'trailing', 'param.name', 'param.equals', 'param.value', 'none', 'token68', 'params'):
        assert r in d, r


# ---- source bans -------------------------------------------------------------------------------------------------
def _src():
    return open(MODPATH).read()


def test_module_imports_and_source_bans():
    tree = ast.parse(_src())
    mods = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            mods.append(n.module)
    assert sorted(mods) == sorted(['importlib.util', 'app.modules.instinct_doc.p235_concepts_registry'])
    names = set()
    attrs = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            attrs.add(n.attr)
        elif isinstance(n, (ast.Lambda, ast.Global, ast.Nonlocal, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.While) and ast.AST):
            pass
    assert attrs == {'name'}
    for bad in ('re', 'unicodedata', 'urllib', 'ipaddress', 'socket', 'os', 'sys', 'time', 'random', 'datetime', 'open', 'eval', 'exec', '__import__', 'input', 'print',
                'ord', 'chr', 'int', 'isinstance', 'getattr', 'setattr', 'globals', 'locals', 'vars', 'hash', 'id', 'sorted', 'reversed', 'map', 'filter', 'any', 'all',
                'list', 'dict', 'set', 'frozenset', 'bytes', 'repr', 'format', 'sum', 'min', 'max', 'abs', 'divmod', 'zip', 'enumerate', 'iter', 'next'):
        assert bad not in names, bad
    assert sorted(names) == ['ADJACENT', 'CLAIMS', 'DIGITS', 'FOLD', 'LOWER', 'ModuleNotFoundError', 'NOT_CLAIMED', 'QDT', 'QPT', 'SCOPE', 'T68', 'TCHARS', 'TEXT_CAP', 'UPPER', 'VCHAR', 'ValueError', '_MID', '_REG', '_TAIL', '_auth_parse', '_fold', '_i', '_kind', '_ows_end', '_param_at', '_param_parts', '_payload', '_qd_ok', '_qp_ok', '_quoted', '_quoted_end', '_scheme', '_steps', '_str', '_t68_ok', '_token_run', '_val', 'a', 'b', 'cap', 'ch', 'code', 'e', 'exc', 'fail', 'find_spec', 'first', 'fn', 'i', 'j', 'k', 'kind', 'len', 'm', 'make_fail', 'name', 'names', 'nm', 'out', 'p', 'parts', 'payload', 'pos', 'q', 'range', 'reason', 'rest', 'scheme', 'seen', 'seg', 'str', 't', 't2', 'text', 'tuple', 'type', 'val', 'value']
    for node in ast.walk(tree):
        assert not isinstance(node, (ast.Lambda, ast.Global, ast.Nonlocal, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.Starred, ast.JoinedStr, ast.Await, ast.Yield))
    src = _src()
    banned = [' or ' + 'True', 'if ' + 'False', 'else ' + 'True', ' and ' + 'False', ' or ' + 'False']
    for b in banned:
        assert b not in src, b
    assert 'import *' not in src


def test_source_and_tests_have_no_vacuous_assertions():
    me = open(os.path.join(HERE, 'test_instinct_p235_concepts_batch1123_httpauth.py')).read()
    for b in (' or ' + 'True', 'if ' + 'False:', 'else ' + 'True', ' and ' + 'False', ' or ' + 'False', 'assert ' + 'True', 'assert ' + '1 ', 'assert ' + 'not ' + 'False'):
        assert b not in me, b


# ---- exact types ---------------------------------------------------------------------------------------------------
def arg_vectors(fn):
    for bad in JUNK + STR_HOSTILE + [BoolLike(1)]:
        yield 0, 'text', [bad]


@pytest.mark.parametrize('fn', NAMES)
def test_every_argument_is_an_exact_type_by_identity(fn):
    n = 0
    for pos, name, args in arg_vectors(fn):
        assert run(fn, *args) == E(fn, 'bad_type:' + name), (fn, pos, args[pos])
        n += 1
    assert n >= 14


# ---- caps: pinned at cap and cap + 1, length before content ----------------------------------------------------------
CAP_OK = {
    'token_reason': 'a' * 4096,
    'token68_reason': 'a' * 4094 + '==',
    'quoted_reason': '"' + 'a' * 4094 + '"',
    'unquote': '"' + 'a' * 4094 + '"',
    'param_reason': 'a="' + 'b' * 4092 + '"',
    'challenge_reason': 'Basic ' + 'a' * 4090,
    'credentials_reason': 'Basic ' + 'a' * 4090,
    'challenges_reason': 'Basic ' + 'a' * 4090,
    'split_challenge': 'Basic ' + 'a' * 4090,
    'split_credentials': 'Basic ' + 'a' * 4090,
}


@pytest.mark.parametrize('fname', NAMES)
def test_text_caps_pinned_at_cap_and_cap_plus_one(fname):
    fn = getattr(m, fname)
    good = CAP_OK[fname]
    assert len(good) == 4096
    if fname == 'unquote':
        assert fn(good) == 'a' * 4094
    elif fname in ('split_challenge', 'split_credentials'):
        assert fn(good) == ('Basic', 'token68', 'a' * 4090)
    else:
        assert fn(good) == 'ok', fname
    over = good + 'a'
    with pytest.raises(ValueError) as ei:
        fn(over)
    assert str(ei.value) == PFX + '%s:bad_value:text.length' % fname
    with pytest.raises(ValueError) as ei2:
        fn([4097] * 2)
    assert str(ei2.value) == PFX + '%s:bad_type:text' % fname
    if fname == 'token_reason':
        with pytest.raises(ValueError) as ei3:
            fn(chr(0x100) * 4097)
        assert str(ei3.value) == PFX + 'token_reason:bad_value:text.length'


def test_output_closure_unquote_and_splits():
    t = '"a\\nb\\t\\\\' + 'x' * 100 + '"'
    assert len(m.unquote(t)) < len(t)
    s0 = 'Basic realm="x", nonce="y"'
    assert m.split_challenge(s0) == ('Basic', 'params', (('realm', 'x'), ('nonce', 'y')))
    sch, kind, payload = m.split_challenge('Basic ' + 'a' * 60 + '==')
    assert (sch, kind) == ('Basic', 'token68') and len(payload) <= 62
    sch2, kind2, payload2 = m.split_credentials('B a=1,b=2')
    assert (sch2, kind2, payload2) == ('B', 'params', (('a', '1'), ('b', '2')))


# ---- memory: caps are checked before work ---------------------------------------------------------------------------
def test_cap_is_checked_before_any_allocation_or_scan():
    big = 'a' * 4097
    tracemalloc.start()
    try:
        for fname in NAMES:
            tracemalloc.clear_traces()
            tracemalloc.reset_peak()
            base = tracemalloc.get_traced_memory()[0]
            r = run(fname, big)
            peak = tracemalloc.get_traced_memory()[1] - base
            assert r[0] == 'err' and peak < 4000, (fname, peak)
    finally:
        tracemalloc.stop()


# ---- no input mutation, no global state ---------------------------------------------------------------------------------
def test_results_are_fresh_exact_types_and_inputs_are_not_mutated():
    for fname in ('token_reason', 'token68_reason', 'quoted_reason', 'param_reason', 'challenge_reason', 'credentials_reason', 'challenges_reason'):
        assert type(getattr(m, fname)('Basic a=1' if 'challenge' in fname or 'credentials' in fname or 'challenges' in fname else 'a')) is str
    assert type(m.unquote('"a"')) is str
    s1 = m.split_challenge('Basic a=1')
    s2 = m.split_challenge('Basic a=1')
    assert s1 is not s2 and s1 == s2 == ('Basic', 'params', (('a', '1'),)) and type(s1) is tuple and len(s1) == 3
    assert type(s1[0]) is str and type(s1[1]) is str and type(s1[2]) is tuple
    assert all(type(p) is tuple and len(p) == 2 and type(p[0]) is str and type(p[1]) is str for p in s1[2])
    assert m.split_credentials('Basic a=1') == m.split_challenge('Basic a=1')
    assert m.split_challenge('Basic') == ('Basic', 'none', None)
    assert m.split_challenge('Basic abc==') == ('Basic', 'token68', 'abc==')

# ---- semantics: grammar tables, check order, both-bad pins, splits, duplicates, fuzz -----------------------------

RFC_EXAMPLE = 'Newauth realm="apps", type=1, title="Login to \\"apps\\"", Basic realm="simple"'


def test_rfc_4_1_example_and_4_x_field_shapes():
    assert m.challenges_reason(RFC_EXAMPLE) == 'ok'
    assert m.challenge_reason('Newauth realm="apps", type=1, title="Login to \\"apps\\""') == 'ok'
    assert m.challenge_reason('Basic realm="simple"') == 'ok'
    assert m.credentials_reason('Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==') == 'ok'


TOKEN_CASES = [
    ('', 'empty'), ('Basic', 'ok'), ('a', 'ok'), ('A0!#$%&\'*+-.^_`|~', 'ok'), ('Basic realm', 'char'),
    ('Basic"', 'char'), ('Basic,', 'char'), ('Basic=', 'char'), ('Basic/', 'char'), ('Basic\\', 'char'),
    ('Basic\x7f', 'char'), ('Basic\x80', 'char'), ('Basic\x00', 'char'), ('Basic ', 'char'), ('\tBasic', 'char'),
    ('"Basic', 'char'), ('Bàsic', 'char'),
]
@pytest.mark.parametrize('text,want', TOKEN_CASES)
def test_token_reason_table(text, want):
    assert m.token_reason(text) == want


def test_token_reason_every_tchar_accepted():
    for ch in m.TCHARS:
        assert m.token_reason('a' + ch + 'b') == 'ok', repr(ch)


def test_token_reason_every_ascii_non_tchar_refused():
    for o in range(128):
        ch = chr(o)
        if ch not in m.TCHARS:
            assert m.token_reason(ch) == 'char', o


T68_CASES = [
    ('', 'empty'), ('x', 'ok'), ('QWxhZGRpbjpvcGVuIHNlc2FtZQ==', 'ok'), ('x=', 'ok'), ('x==', 'ok'),
    ('=', 'padding'), ('==', 'padding'), ('=x', 'padding'), ('x=x', 'padding'), ('x==x', 'padding'),
    ('x!==', 'char'), ('x x', 'char'), ('x\tx', 'char'), ('x"x', 'char'), ('x,x', 'char'), ('x\\x', 'char'),
    ('x\x7f', 'char'), ('x\x80', 'char'), ('-._~+/', 'ok'), ('09aZ', 'ok'),
]
@pytest.mark.parametrize('text,want', T68_CASES)
def test_token68_reason_table(text, want):
    assert m.token68_reason(text) == want


def test_token68_char_beats_padding_at_first_bad_position():
    assert m.token68_reason('!x==') == 'char'
    assert m.token68_reason('x=x!') == 'char'
    assert m.token68_reason('x=x') == 'padding'
    assert m.token68_reason('=x') == 'padding'
    assert m.token68_reason('x=\x01=x') == 'char'
    assert m.token68_reason('=x\x01') == 'char'


def test_token68_every_set_char_accepted():
    for ch in m.T68:
        assert m.token68_reason(ch) == 'ok', repr(ch)
        assert m.token68_reason('a' + ch + '==') == 'ok', repr(ch)


QUOTED_CASES = [
    ('', 'quote'), ('"', 'quote'), ('x"', 'quote'), ('"a', 'quote'), ('"a\\', 'quote'), ('""', 'ok'),
    ('"a"', 'ok'), ('"a b"', 'ok'), ('"a!b"', 'ok'), ('"a#b"', 'ok'), ('"a[b"', 'ok'), ('"a]b"', 'ok'),
    ('"a~b"', 'ok'), ('"a\\"b"', 'ok'), ('"a\\\\b"', 'ok'), ('"a\\\tb"', 'ok'), ('"a\\ b"', 'ok'),
    ('"a\\~b"', 'ok'), ('"a"x', 'quote'), ('"a""', 'quote'), ('"a\x01"', 'char'), ('"a\x7f"', 'char'),
    ('"a\x80"', 'char'), ('"a\\\x01"', 'escape'), ('"a\\\x7f"', 'escape'), ('"a\\\x80"', 'escape'),
    ('"a\tb"', 'ok'), ('"a\rb"', 'char'), ('"a\nb"', 'char'),
]
@pytest.mark.parametrize('text,want', QUOTED_CASES)
def test_quoted_reason_table(text, want):
    assert m.quoted_reason(text) == want


def test_quoted_reason_position_decides_escape_versus_char():
    assert m.quoted_reason('"\\\x01\x02"') == 'escape'
    assert m.quoted_reason('"\x02\\\x01"') == 'char'


def test_unquote_round_trips_and_pairs():
    assert m.unquote('""') == ''
    assert m.unquote('"abc"') == 'abc'
    assert m.unquote('"a\\"b"') == 'a"b'
    assert m.unquote('"a\\\\b"') == 'a\\b'
    assert m.unquote('"\\\t\\\x21\\~"') == '\t' + '!' + '~'
    assert len(m.unquote('"a\\"b"')) <= len('"a\\"b"')
    for bad in ('x', '"', '"a', '"a\\', '"a"x', '"a\x01"', '"a\\\x01"'):
        assert run('unquote', bad) == E('unquote', 'bad_value:text.' + m.quoted_reason(bad))


PARAM_CASES = [
    ('', 'param.name'), ('=1', 'param.name'), (' a=1', 'param.name'), ('\ta=1', 'param.name'),
    ('a', 'param.equals'), ('a ', 'param.equals'), ('a\t', 'param.equals'), ('a 1', 'param.equals'),
    ('a=', 'param.value'), ('a= ', 'param.value'), ('a="', 'param.value'), ('a="x', 'param.value'),
    ('a="x"y', 'trailing'), ('a=1 ', 'trailing'), ('a=1\t', 'trailing'), ('a=1,', 'trailing'),
    ('a=1', 'ok'), ('a =1', 'ok'), ('a= 1', 'ok'), ('a \t=\t 1', 'ok'), ('a="x y"', 'ok'), ('a=""', 'ok'),
    ('realm="apps"', 'ok'), ('type=1', 'ok'), ("a=!#$%&'*+-.^_`|~", 'ok'), ('a=\x80', 'param.value'),
    ('a=,', 'param.value'), ('a=="', 'param.value'),
]
@pytest.mark.parametrize('text,want', PARAM_CASES)
def test_param_reason_table(text, want):
    assert m.param_reason(text) == want


AUTH_CASES = [
    ('', 'scheme'), (',Basic', 'scheme'), ('=x', 'scheme'), (' Basic', 'scheme'), ('"Basic', 'scheme'),
    ('Basic', 'ok'), ('Basic\tx', 'scheme'), ('Basic,x', 'scheme'), ('Basic"x', 'scheme'),
    ('Basic ', 'tail'), ('Basic  ', 'tail'), ('Basic \t', 'param.name'),
    ('Basic  x==', 'ok'), ('Basic  a=1', 'ok'), ('Basic   ', 'tail'), ('Basic b =', 'param.value'), ('Basic  =x', 'param.name'),
    ('Basic x', 'ok'), ('Basic x==', 'ok'), ('Basic -._~+/', 'ok'),
    ('Basic x ', 'param.equals'), ('Basic x\ty', 'param.equals'), ('Basic !', 'param.equals'),
    ('Basic x==x', 'param.value'), ('Basic =', 'param.name'),
    ('Basic ,', 'ok'), ('Basic ,,', 'ok'), ('Basic , ,', 'ok'), ('Basic ,realm="a"', 'comma'),
    ('Basic ,,realm="a"', 'ok'), ('Basic , realm="a"', 'comma'), ('Basic , ,realm="a"', 'ok'),
    ('Basic realm="a"', 'ok'), ('Basic realm="a", type=1', 'ok'), ('Basic realm="a",type=1,', 'ok'),
    ('Basic realm="a", type=1, ', 'ok'), ('Basic realm="a" , type=1', 'ok'),
    ('Basic realm="a" type=1', 'comma'), ('Basic realm="a"\ttype=1', 'comma'),
    ('Basic realm', 'ok'), ('Basic realm=', 'ok'), ('Basic realm="a', 'param.value'),
    ('Basic a=1,A=2', 'duplicate'), ('Basic a=1,b=2,A=3', 'duplicate'), ('Basic a=1,a=2', 'duplicate'),
    ('Basic A=1,a=2', 'duplicate'), ('Basic a=1,A=2,b', 'duplicate'),
    ('Basic a=1,b,A=2', 'param.equals'), ('Basic a=1,b=2,A=3', 'duplicate'), ('Digest x==', 'ok'),
    ('x a=1,b=2,b=3', 'duplicate'), ('x a=1,b=2,B=3', 'duplicate'), ('Basic realm=a, type=1, type=2', 'duplicate'),
    ('x a=1,b=2,c=3,c=4', 'duplicate'), ('x a=1,b=2,c=3,B=4', 'duplicate'), ('x a=1,b=2,b=3,b=4', 'duplicate'),
]
@pytest.mark.parametrize('text,want', AUTH_CASES)
def test_challenge_reason_table(text, want):
    assert m.challenge_reason(text) == want
    assert m.credentials_reason(text) == want


def test_quoted_control_char_right_after_backslash_is_escape():
    assert m.quoted_reason('"\\\x01') == 'escape' and m.quoted_reason('"\\\x7f"') == 'escape'
    assert m.quoted_reason('"\\\t') == 'quote' and m.quoted_reason('"a\\\x01"') == 'escape'


def test_quoted_backslash_at_end_and_escaped_quote_in_value():
    assert m.quoted_reason('"a\\') == 'quote' and m.quoted_reason('"\\') == 'quote'
    assert m.quoted_reason('"a\\"') == 'quote' and m.quoted_reason('"a\\\\"') == 'ok'
    assert m.param_reason('a="b\\') == 'param.value' and m.param_reason('a="b\\\\"') == 'ok' and m.param_reason('a="b\\""') == 'ok'
    assert m.challenge_reason('Basic a="b\\') == 'param.value' and m.challenge_reason('Basic a="b\\\\"') == 'ok'
    assert run('unquote', '"a\\') == E('unquote', 'bad_value:text.quote')
    assert m.split_challenge('Basic a="b\\""') == ('Basic', 'params', (('a', 'b"'),))
    assert m.unquote('"a\\\\"') == 'a\\'
    assert m.param_reason('a="b\\\x01"') == 'param.value' and m.param_reason('a="b\x01"') == 'param.value'
    assert m.challenge_reason('Basic a="b\\\x01"') == 'param.value' and m.challenge_reason('Basic a="b\x01"') == 'param.value'
    assert run('split_challenge', 'Basic a="b\\\x01"') == E('split_challenge', 'bad_value:text.param.value')
    assert run('split_credentials', 'Basic a="b\x01"') == E('split_credentials', 'bad_value:text.param.value')


def test_duplicate_fold_is_ascii_only():
    assert m.challenge_reason('Basic \u0130=1,x=2') == 'param.name'
    assert m.challenge_reason('Basic \u212a=1,K=2') == 'param.name'
    assert m.challenge_reason('Basic k=1,K=2') == 'duplicate'


LIST_CASES = [
    ('', 'empty'), (',', 'empty'), (',,', 'empty'), (', ,', 'empty'), (' \t', 'empty'),
    ('Basic', 'ok'), ('Basic ', 'ok'), ('Basic  ', 'ok'), ('Basic ,', 'ok'), ('Basic , ', 'ok'),
    (',Basic', 'ok'), (', Basic', 'ok'), (',,Basic', 'ok'), ('Basic,,', 'ok'),
    ('Basic,realm=a', 'scheme'), ('B,a=1', 'scheme'), (',x,1=x', 'scheme'), ('Basic, realm=a', 'scheme'),
    ('Basic x, Digest y', 'ok'), ('Basic x==, Digest y=1', 'ok'), ('Basic x== , Digest y=1', 'ok'),
    ('Basic x==\t, Digest y=1', 'ok'), ('Basic , Digest x', 'ok'), ('Basic  , Digest x', 'ok'),
    ('Basic\tx, Digest y', 'scheme'), ('Basic x, Digest', 'ok'), ('Basic x,', 'ok'), ('Basic x, ', 'ok'),
    (RFC_EXAMPLE, 'ok'),
    ('Newauth realm="apps", type=1, title="Login to \\"apps\\"", Basic realm="simple",', 'ok'),
    ('Newauth realm="apps", type=1, title="x",Basic realm="simple"', 'ok'),
    ('x a=1,,b=2', 'ok'), ('x a=1,,b=2, Digest y', 'ok'), ('x a=1,b=2,, Digest y', 'ok'),
    ('x a=1,A=2', 'duplicate'), ('x a=1,,A=2', 'duplicate'), ('x a=1, Digest A=2', 'ok'),
    ('x a=1,b=2,c', 'ok'), ('x a=1,"b"', 'scheme'), ('x a=1,=b', 'scheme'),
    ('x a=1 b=2', 'comma'), ('x a="unclosed', 'param.value'), ('x a="unclosed, Basic y', 'param.value'),
    ('x a=1,', 'ok'), ('x a=1, ', 'ok'), ('x a=1, , Basic y', 'ok'),
    ('Digest  x== , Basic y', 'ok'), ('Basic  x, Digest y', 'ok'), ('x a=1, b =', 'param.value'), ('x a=1, b =, Basic y', 'param.value'), ('x a=1,  b=2', 'ok'),
    ('Digest x==, Basic realm="a"', 'ok'), ('Digest x== , Basic realm="a"', 'ok'),
    ('x a=1,b=2,b=3', 'duplicate'), ('x a=1,b=2,B=3', 'duplicate'), ('x a=1,b=2,c=3,c=4', 'duplicate'),
    ('  Basic x', 'ok'), ('\tBasic x, Digest y', 'ok'), (' \t, Basic x', 'ok'), ('  ', 'empty'), (' \t', 'empty'),
    ('x   a=b', 'ok'), ('x    a=b', 'ok'), ('x abc  , y', 'ok'), ('x abc   , y', 'ok'), ('x \t,y', 'param.name'), ('x \t, y', 'param.name'),
]
@pytest.mark.parametrize('text,want', LIST_CASES)
def test_challenges_reason_table(text, want):
    assert m.challenges_reason(text) == want


def test_split_tables():
    assert m.split_challenge('Basic') == ('Basic', 'none', None)
    assert m.split_credentials('Basic') == ('Basic', 'none', None)
    assert m.split_challenge('Basic x==') == ('Basic', 'token68', 'x==')
    assert m.split_credentials('Digest QWxhZGRpbjpvcGVuIHNlc2FtZQ==') == ('Digest', 'token68', 'QWxhZGRpbjpvcGVuIHNlc2FtZQ==')
    assert m.split_challenge('Basic realm="apps", type=1') == ('Basic', 'params', (('realm', 'apps'), ('type', '1')))
    assert m.split_challenge('Basic ,,realm="apps",,type=1,') == ('Basic', 'params', (('realm', 'apps'), ('type', '1')))
    assert m.split_challenge('Basic realm="a\\"b"') == ('Basic', 'params', (('realm', 'a"b'),))
    assert m.split_challenge('Basic realm=""') == ('Basic', 'params', (('realm', ''),))
    assert m.split_challenge('Basic ReAlM="a"') == ('Basic', 'params', (('ReAlM', 'a'),))
    assert m.split_challenge('Basic a = 1 , b\t=\t"x"') == ('Basic', 'params', (('a', '1'), ('b', 'x')))
    assert run('split_credentials', 'Basic x, y=2') == E('split_credentials', 'bad_value:text.param.equals')


def test_split_errors_use_reason_prefixes():
    assert run('split_challenge', '') == E('split_challenge', 'bad_value:text.scheme')
    assert run('split_challenge', 'Basic ') == E('split_challenge', 'bad_value:text.tail')
    assert run('split_challenge', 'Basic a=1,A=2') == E('split_challenge', 'bad_value:text.duplicate')
    assert run('split_challenge', 'x a=1,b=2,b=3') == E('split_challenge', 'bad_value:text.duplicate')
    assert run('split_challenge', 'x a=1,b=2,B=3') == E('split_challenge', 'bad_value:text.duplicate')
    assert run('split_credentials', 'x a=1,b=2,b=3') == E('split_credentials', 'bad_value:text.duplicate')
    assert run('split_credentials', 'Basic realm=a, type=1, type=2') == E('split_credentials', 'bad_value:text.duplicate')
    assert run('split_credentials', 'Basic a=1 b=2') == E('split_credentials', 'bad_value:text.comma')
    assert m.split_credentials('Basic realm') == ('Basic', 'token68', 'realm')


def test_token68_wins_over_params():
    assert m.challenge_reason('Basic abc') == 'ok'
    assert m.split_challenge('Basic abc') == ('Basic', 'token68', 'abc')
    assert m.challenge_reason('Basic abc=') == 'ok'
    assert m.split_challenge('Basic abc=') == ('Basic', 'token68', 'abc=')
    assert m.challenge_reason('Basic a=b') == 'ok'
    assert m.split_challenge('Basic a=b') == ('Basic', 'params', (('a', 'b'),))


def _fz_string(rng):
    alpha = 'abAB09",= \t\\"\',;~!#\x7f\x80'
    return ''.join(rng.choice(alpha) for _ in range(rng.randrange(0, 22)))


def test_fuzz_reason_functions_against_oracles_1200_iterations():
    rng = random.Random(1123)
    for _ in range(1200):
        t = _fz_string(rng)
        assert (m.token_reason(t) == 'ok') == o_token(t), repr(t)
        assert (m.token68_reason(t) == 'ok') == o_t68(t), repr(t)
        assert (m.quoted_reason(t) == 'ok') == o_qs(t), repr(t)
        assert (m.param_reason(t) == 'ok') == o_param(t), repr(t)
        assert (m.challenge_reason(t) == 'ok') == o_auth(t), repr(t)
        assert (m.credentials_reason(t) == 'ok') == o_auth(t), repr(t)


def test_fuzz_challenges_reason_against_list_oracle_1200_iterations():
    rng = random.Random(1124)
    for _ in range(1200):
        t = _fz_string(rng)
        assert (m.challenges_reason(t) == 'ok') == o_list(t), repr(t)


def test_fuzz_split_against_structural_oracle_1200_iterations():
    rng = random.Random(1125)
    for _ in range(1200):
        t = _fz_string(rng)
        want = o_split(t)
        if want is None:
            assert m.challenge_reason(t) != 'ok', repr(t)
        else:
            assert m.split_challenge(t) == want, repr(t)
            assert m.split_credentials(t) == want, repr(t)


# ---- registry guard, import log, namespace ----------------------------------------------------------------------
def test_registry_absent_uses_local_fallback(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh()
    assert mod.make_fail.__module__ == mod.__name__
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert run('token_reason', 1, mod=mod) == ('err', 'P235:token_reason:bad_type:text')


def test_registry_present_is_used_by_every_function(mp):
    fake = types.ModuleType(REG)
    fake.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE:%s:%s' % (name, code))))
    mp.setitem(sys.modules, REG, fake)
    mod = fresh()
    assert mod.make_fail is fake.make_fail
    for fn in NAMES:
        spec = ARGSPEC[fn]
        args = [g for _n, g in spec]
        args[0] = None
        assert run(fn, *args, mod=mod) == ('err', 'FAKE:%s:bad_type:%s' % (fn, spec[0][0]))


def test_registry_guard_foreign_name_never_consults_find_spec(mp):
    real = builtins.__import__
    spied = []
    err = ModuleNotFoundError('foreign', name='some.other.module')

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda name: spied.append(name) or object())
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ModuleNotFoundError) as e:
        fresh()
    assert e.value is err and spied == []


def test_registry_guard_registry_name_with_spec_found_is_reraised(mp):
    real = builtins.__import__
    spied = []
    err = ModuleNotFoundError('inner', name=REG)

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda name: spied.append(name) or object())
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ModuleNotFoundError) as e:
        fresh()
    assert e.value is err and spied == [REG]


@pytest.mark.parametrize('nm', [REG, 'some.other.module'])
def test_import_error_is_not_a_module_not_found_error(mp, nm):
    real = builtins.__import__
    err = ImportError('x', name=nm)

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda n: None)
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ImportError) as e:
        fresh()
    assert e.value is err and type(e.value) is ImportError


IMPORTS = [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]
NAMESPACE = (['find_spec'] + ['SCOPE', 'NOT_CLAIMED', 'CLAIMS', 'ADJACENT', 'TEXT_CAP', 'DIGITS', 'UPPER', 'LOWER', 'TCHARS', 'T68',
                              'FOLD', 'QDT', 'VCHAR', 'QPT', '_MID', '_TAIL', '_REG', 'make_fail'] + list(PRIVATE) + list(NAMES))
CALLS = [(fn, tuple(g for _n, g in ARGSPEC[fn]), tuple([None] + [g for _n, g in ARGSPEC[fn]][1:])) for fn in NAMES]


@pytest.mark.parametrize('world', ['absent', 'foreign', 'registry_raise', 'present'])
def test_import_log_and_namespace_on_every_path(mp, world):
    real = builtins.__import__
    seen = []
    spied = []
    err = ModuleNotFoundError('x', name=('some.other.module' if world == 'foreign' else REG))
    fake = types.ModuleType(REG)
    fake.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE')))

    def spy(name):
        spied.append(name)
        return None if world == 'absent' else object()

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == fresh.__defaults__[0]:
            seen.append((n, tuple(fromlist or ()), level))
        if n == REG and world in ('foreign', 'registry_raise'):
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, fake if world == 'present' else None)
    mp.setattr(importlib.util, 'find_spec', spy)
    mp.setattr(builtins, '__import__', hook)
    if world in ('foreign', 'registry_raise'):
        with pytest.raises(ModuleNotFoundError) as e:
            fresh()
        assert e.value is err
        assert seen == IMPORTS
        assert spied == ([] if world == 'foreign' else [REG])
        return
    mod = fresh()
    assert seen == IMPORTS
    assert spied == ([REG] if world == 'absent' else [])
    names = sorted(k for k in vars(mod) if not (k.startswith('__') and k.endswith('__')))
    assert names == sorted(NAMESPACE)
    del seen[:]
    for fn, good, bad in CALLS:
        for args in (good, bad):
            try:
                getattr(mod, fn)(*args)
            except ValueError:
                pass
    assert seen == []


def test_failure_prefix_is_p235_when_the_fallback_is_bound():
    if m.make_fail.__module__ == m.__name__:
        assert PFX == 'P235:'
    assert PFX.endswith(':') and 'x:c' not in PFX


# ---- the shared corpus: one success and every refusal code of every public function --------------------------
CORPUS = []
for _fn in NAMES:
    for _pos, (_name, _g) in enumerate(ARGSPEC[_fn]):
        _args = [g for _n, g in ARGSPEC[_fn]]
        _args[_pos] = 5
        CORPUS.append((_fn, tuple(_args), 'bad_type:' + _name))
for _fn in NAMES:
    CORPUS.append((_fn, ('a' * 4097,), 'bad_value:text.length'))
for _r, _t in (('quote', '"a'), ('escape', '"a\\\x01"'), ('char', '"\x01"')):
    CORPUS.append(('unquote', (_t,), 'bad_value:text.' + _r))
for _r, _t in (('scheme', '\x01 x'), ('tail', 'Basic '), ('param.name', 'Basic \x01'), ('param.equals', 'Basic a b'),
               ('param.value', 'Basic a=\x01'), ('duplicate', 'Basic a=1,A=2')):
    CORPUS.append(('split_challenge', (_t,), 'bad_value:text.' + _r))
CORPUS.append(('split_credentials', ('\x01 x',), 'bad_value:text.scheme'))
CORPUS.append(('split_credentials', ('Basic a=1,A=2',), 'bad_value:text.duplicate'))
SUCCESS = [('token_reason', ('a',), 'ok'), ('token_reason', ('\x01',), 'char'), ('token_reason', ('',), 'empty'),
           ('token68_reason', ('a=',), 'ok'), ('token68_reason', ('==',), 'padding'), ('token68_reason', ('\x01',), 'char'),
           ('token68_reason', ('',), 'empty'),
           ('quoted_reason', ('"a"',), 'ok'), ('quoted_reason', ('"a',), 'quote'), ('quoted_reason', ('"a\\\x01"',), 'escape'),
           ('quoted_reason', ('"\x01"',), 'char'),
           ('unquote', ('"a\\nb"',), 'anb'), ('unquote', ('""',), ''),
           ('param_reason', ('a=1',), 'ok'), ('param_reason', ('a="x y"',), 'ok'), ('param_reason', ('a',), 'param.equals'),
           ('param_reason', ('a=\x01',), 'param.value'), ('param_reason', ('a=1\x01',), 'trailing'),
           ('param_reason', ('\x01=1',), 'param.name'),
           ('challenge_reason', ('Basic',), 'ok'), ('challenge_reason', ('Basic abc==',), 'ok'),
           ('challenge_reason', ('Basic a=1',), 'ok'), ('challenge_reason', ('\x01',), 'scheme'),
           ('challenge_reason', ('Basic ',), 'tail'), ('challenge_reason', ('Basic \x01',), 'param.name'),
           ('challenge_reason', ('Basic a b',), 'param.equals'), ('challenge_reason', ('Basic a=1,A=2',), 'duplicate'),
           ('credentials_reason', ('Basic abc==',), 'ok'), ('credentials_reason', ('Basic a=1',), 'ok'),
           ('credentials_reason', ('x,',), 'scheme'),  ('credentials_reason', ('Basic a=1,A=2',), 'duplicate'),
           ('challenges_reason', ('Basic, Digest a=1',), 'ok'), ('challenges_reason', ('',), 'empty'),
           ('challenges_reason', (',',), 'empty'), ('challenges_reason', ('Basic x,,',), 'ok'),
           ('challenges_reason', ('Basic,realm=a',), 'scheme'), ('challenges_reason', ('x ,y=1',), 'scheme'),
           ('challenges_reason', ('x a=1,A=2',), 'duplicate'),
           ('challenges_reason', ('x a=1 b=2',), 'comma'),
           ('split_challenge', ('Basic a=1',), ('Basic', 'params', (('a', '1'),))),
           ('split_challenge', ('Basic',), ('Basic', 'none', None)),
           ('split_challenge', ('Basic abc==',), ('Basic', 'token68', 'abc==')),
           ('split_credentials', ('Basic abc',), ('Basic', 'token68', 'abc')),
           ('split_credentials', ('Basic',), ('Basic', 'none', None)),
           ('split_credentials', ('B a=1, b=2',), ('B', 'params', (('a', '1'), ('b', '2')))),
           ]


def drive(mod, pfx=None):
    p = PFX if pfx is None else pfx
    for fn, args, want in CORPUS:
        with pytest.raises(ValueError) as e:
            getattr(mod, fn)(*args)
        assert str(e.value) == p + fn + ':' + want
    for fn, args, want in SUCCESS:
        assert getattr(mod, fn)(*args) == want


def test_corpus_reaches_every_refusal_code_and_every_success_branch():
    drive(m)
    codes = {(fn, w) for fn, a, w in CORPUS}
    for fn in NAMES:
        for _name, _g in ARGSPEC[fn]:
            assert (fn, 'bad_type:' + _name) in codes
        assert (fn, 'bad_value:text.length') in codes
    for r in ('quote', 'escape', 'char'):
        assert ('unquote', 'bad_value:text.' + r) in codes
    for r in ('scheme', 'tail', 'param.name', 'param.equals', 'param.value', 'duplicate'):
        assert ('split_challenge', 'bad_value:text.' + r) in codes
    for r in ('ok', 'empty', 'char'):
        assert any(f == 'token_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'padding'):
        assert any(f == 'token68_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'quote', 'escape', 'char'):
        assert any(f == 'quoted_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'param.name', 'param.equals', 'param.value', 'trailing'):
        assert any(f == 'param_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'scheme', 'tail', 'duplicate'):
        assert any(f == 'challenge_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'scheme', 'duplicate'):
        assert any(f == 'credentials_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'empty', 'scheme', 'comma', 'duplicate'):
        assert any(f == 'challenges_reason' and w == r for f, a, w in SUCCESS)


def test_fallback_failer_world_has_no_imports_one_success_and_every_refusal(mp):
    real = builtins.__import__
    seen = []
    name = 'b1123_fallback_world'

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == name:
            seen.append((n, tuple(fromlist or ()), level))
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(builtins, '__import__', hook)
    mod = fresh(name)
    assert mod.make_fail.__module__ == name
    assert seen == IMPORTS
    del seen[:]
    drive(mod, 'P235:')
    assert seen == []
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert seen == []


def test_every_refusal_goes_through_the_failer_call_site(mp):
    """Stub world: the bound failer raises a sentinel; the last frame inside the module for each refusal is a line starting with fail(."""
    class Stop(Exception):
        pass

    def make(name):
        def fail(code):
            raise Stop(name + ':' + code)
        return fail
    fake = types.ModuleType(REG)
    fake.make_fail = make
    mp.setitem(sys.modules, REG, fake)
    mod = fresh('b1123_site_world')
    sites = set()
    for fn, args, want in CORPUS:
        with pytest.raises(Stop) as e:
            getattr(mod, fn)(*args)
        assert str(e.value) == fn + ':' + want
        frames = [f for f in traceback.extract_tb(e.value.__traceback__) if f.filename == mod.__file__]
        assert frames[-1].line.strip().startswith('fail(')
        sites.add(frames[-1].lineno)
    src = inspect.getsource(mod).split('\n')
    all_sites = {i + 1 for i, line in enumerate(src) if line.strip().startswith('fail(') and 'def ' not in line}
    assert sites == all_sites, sorted(all_sites - sites)


def test_fixture_autouse_hook_is_installed_and_sees_module_names():
    assert getattr(builtins.__import__, '__name__', '') == 'hook'


@pytest.fixture(autouse=True)
def _module_never_imports_at_call_time():
    """Every test drives the module through the hook: any import executed by the module's own code after load fails the test."""
    real = builtins.__import__
    seen = []

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == m.__name__:
            seen.append((n, tuple(fromlist or ()), level))
        return real(n, g, l, fromlist, level)
    builtins.__import__ = hook
    try:
        yield
    finally:
        if builtins.__import__ is hook:
            builtins.__import__ = real
    assert seen == []


def test_fallback_failer_functions_carry_no_docstring(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh('b1123_doc_world')
    assert mod.make_fail.__doc__ is None
    assert mod.make_fail('x').__doc__ is None
    assert mod.make_fail.__name__ == 'make_fail' and mod.make_fail('x').__name__ == 'fail'


def test_find_spec_is_consulted_exactly_once_in_the_absent_world_simulation(mp):
    spied = []
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda n: spied.append(n) or None)
    mod = fresh('b1123_spec_world')
    assert spied == [REG] and mod.make_fail.__module__ == mod.__name__


def _world(mp, exc_factory, spec_result, register=None):
    """Run fresh() with __import__ of REG raising exc_factory() (or present as a fake module); return (outcome, spied calls)."""
    real = builtins.__import__
    spied = []
    err = exc_factory() if exc_factory else None

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG and err is not None:
            raise err
        return real(n, g, l, fromlist, level)

    def spy(name):
        spied.append(name)
        return spec_result
    mp.setitem(sys.modules, REG, register if register is not None else None)
    mp.setattr(importlib.util, 'find_spec', spy)
    mp.setattr(builtins, '__import__', hook)
    try:
        mod = fresh()
    except BaseException as e:
        return ('raised', e, err), spied
    return ('loaded', mod, err), spied


_FAKE = types.ModuleType(REG)
_FAKE.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE:%s:%s' % (name, code))))
GUARD_WORLDS = [
    ('absent', lambda: ModuleNotFoundError('absent', name=REG), None, 'fallback', 1),
    ('foreign_found', lambda: ModuleNotFoundError('inner', name=REG), object(), 'raise', 1),
    ('spec_false', lambda: ModuleNotFoundError('inner', name=REG), False, 'raise', 1),
    ('spec_empty_tuple', lambda: ModuleNotFoundError('inner', name=REG), (), 'raise', 1),
    ('foreign_mnf_name', lambda: ModuleNotFoundError('foreign', name='some.other.module'), None, 'raise', 0),
    ('name_x', lambda: ModuleNotFoundError('x', name='x'), None, 'raise', 0),
    ('name_none', lambda: ModuleNotFoundError('none'), None, 'raise', 0),
    ('name_prefix', lambda: ModuleNotFoundError('prefix', name='app.modules.instinct_doc'), None, 'raise', 0),
    ('name_longer', lambda: ModuleNotFoundError('longer', name=REG + '.sub'), None, 'raise', 0),
    ('name_upper', lambda: ModuleNotFoundError('upper', name=REG.upper()), None, 'raise', 0),
    ('import_error', lambda: ImportError('ie', name=REG), None, 'raise', 0),
    ('named_import_error', lambda: ImportError('ie', name='some.other.module'), None, 'raise', 0),
    ('present', None, None, 'present', 0),
]


@pytest.mark.parametrize('label,factory,spec,outcome,calls', GUARD_WORLDS, ids=[w[0] for w in GUARD_WORLDS])
def test_find_spec_call_count_and_outcome_per_world_is_an_exact_table(mp, label, factory, spec, outcome, calls):
    got, spied = _world(mp, factory, spec, _FAKE if outcome == 'present' else None)
    assert len(spied) == calls and spied == [REG] * calls, label
    if outcome == 'raise':
        assert got[0] == 'raised' and got[1] is got[2], label
    elif outcome == 'fallback':
        assert got[0] == 'loaded' and got[1].make_fail.__module__ == got[1].__name__, label
    else:
        assert got[0] == 'loaded' and got[1].make_fail is _FAKE.make_fail, label


def test_child_process_in_isolated_mode_gives_the_same_answers():
    code = ("import sys; sys.path.insert(0, %r)\n"
            "import app.modules.instinct_doc.p235_concepts_batch1123_httpauth as m\n"
            "print(m.challenges_reason('Basic, Digest a=1'), m.split_challenge('Basic abc=='), "
            "m.param_reason('a=1'), m.token68_reason('abc=='))\n") % (
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(m.__file__)))),)
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok ('Basic', 'token68', 'abc==') ok ok"
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25, env={'PYTHONHASHSEED': '7'})
    assert out.stdout.strip() == "ok ('Basic', 'token68', 'abc==') ok ok"
