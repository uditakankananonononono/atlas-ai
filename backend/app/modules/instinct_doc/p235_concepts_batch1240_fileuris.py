"""b1240 RFC 8089 section 2: file URI scheme syntax, with drive letters.

Source: RFC 8089 (Kerwin, February 2017), section 2 (Syntax), importing
the host and path-absolute rules from the URI syntax, plus the drive
letter material from appendix E. The grammar is 'file-URI = file-scheme
":" file-hier-part' with file-scheme the case-insensitive literal file,
'file-hier-part = ( "//" auth-path ) / local-path', 'auth-path =
[ file-auth ] path-absolute', 'local-path = path-absolute' and
'file-auth = "localhost" / host'. The authority special case: the string
localhost is interpreted "exactly as if no authority were present." On
case: "Any transport-related handling of the file URI scheme MUST retain
the case as given." The path rule is "the absolute path to the file in
the file system." Appendix E variations "are not supported by the
normative syntax of Section 2"; the implemented nonstandard forms are the
E.2 rule 'local-path = [ drive-letter ] path-absolute' and the E.2.2
rules 'file-absolute = "/" drive-letter path-absolute' and 'drive-letter
= ALPHA ":" / ALPHA "|"', and "Note that comparison of drive letters in
DOS or Windows file paths is case insensitive." The pipe form is updated
to the colon form per E.2.2.
Errata: one exists for RFC 8089 in the errata data used: 6501 (Reported,
Editorial, section 6) concerns the IANA registration template, which is
outside the implemented section 2; not applied.
OURS design choices (not sourced from the RFC): TEXT_MAX, AUTH_MAX and
HOST_MAX are implementation bounds; the RFC sets no length limits. A
bracketed authority literal is an opaque token here (nonempty, ASCII, no
nested brackets); its content is validated by the IPv6 sibling modules
and is NOT implemented. host_kind classifies first-match-wins into
literal, ipv4 or reg-name. When a first path segment is exactly a drive
letter, split_drive_uri prefers the drive reading over the plain path
reading. The E.1 userinfo authority and the E.3 UNC forms are NOT
implemented. The P235 error codes and their check order are ours.
SOURCED: the file scheme and hierarchy grammar, the localhost special
case, the case retention rule, the path-absolute structure, the pchar
character set (the 66 unreserved characters, the 11 sub-delims, the colon
and the at-sign), pct-encoded triplets, the host alternatives with
dec-octet IPv4 validation (no leading zeros, each octet at most 255), the
empty reg-name, and the appendix E drive letter rules named above.
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

SCOPE = 'RFC 8089 section 2 file URI syntax with appendix E drive letter forms'
NOT_CLAIMED = ('IPv6 address and IPvFuture validation inside bracketed literals (sibling modules)', 'zone identifiers (sibling module)', 'E.1 userinfo authorities', 'E.3 UNC string forms', 'file system access or path resolution', 'relative reference resolution')
ADJACENT = ('RFC 3986 URI syntax (host, path-absolute, pchar, pct-encoded)', 'RFC 5234 ABNF', 'RFC 6874 zone identifiers (sibling module)', 'RFC 4291 and RFC 5952 IPv6 forms (sibling modules)')
CLAIMS = False

TEXT_MAX = 1024
AUTH_MAX = 255
HOST_MAX = 255
UNRESERVED = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'
SUB_DELIMS = "!$&'()*+,;="


def _text(f, text):
    if type(text) is not str:
        f('text-type')


def _letter(c):
    o = ord(c)
    return 97 <= o <= 122 or 65 <= o <= 90


def _digit(c):
    o = ord(c)
    return 48 <= o <= 57


def _unres(c):
    return c in UNRESERVED


def _iei(c, u):
    o = ord(c)
    return o == u or o == u - 32


def _ici(t, w):
    if len(t) != len(w):
        return False
    for i in range(len(w)):
        if not _iei(t[i], ord(w[i])):
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


def _pchar(c):
    return _unres(c) or c in SUB_DELIMS or c == ':' or c == '@'


def _path_code(p):
    if len(p) < 1:
        return 'path-empty'
    if p[0] != '/':
        return 'path-slash'
    if len(p) > 1 and p[1] == '/':
        return 'path-double-slash'
    skip = 0
    for c in p:
        if skip:
            if _hexval(c) is None:
                return 'path-pc'
            skip -= 1
            continue
        if c == '%':
            skip = 2
            continue
        if c == '/':
            continue
        if not _pchar(c):
            return 'path-char'
    return 'path-pc' if skip else None


def _host_code(h):
    if len(h) > HOST_MAX:
        return 'host-length'
    if h == '':
        return None
    if h[0] == '[':
        if h[-1] != ']':
            return 'host-bracket'
        inner = h[1:-1]
        if len(inner) < 1:
            return 'host-bracket-empty'
        for c in inner:
            if ord(c) > 127 or c in '[]':
                return 'host-bracket-char'
        return None
    skip = 0
    for c in h:
        if skip:
            if _hexval(c) is None:
                return 'host-pc'
            skip -= 1
            continue
        if c == '%':
            skip = 2
            continue
        if not (_unres(c) or c in SUB_DELIMS):
            return 'host-char'
    return 'host-pc' if skip else None


def _ipv4_ok(h):
    parts = h.split('.')
    if len(parts) != 4:
        return False
    for p in parts:
        if len(p) < 1 or len(p) > 3:
            return False
        for c in p:
            if not _digit(c):
                return False
        if len(p) > 1 and p[0] == '0':
            return False
        if int(p) > 255:
            return False
    return True


def _uri_code(text):
    if text == '':
        return 'empty', None
    if len(text) > TEXT_MAX:
        return 'text-length', None
    if len(text) < 5:
        return 'short', None
    if not _ici(text[:4], 'file'):
        return 'scheme', None
    if text[4] != ':':
        return 'scheme-colon', None
    rest = text[5:]
    if rest[:2] == '//':
        tail = rest[2:]
        i = tail.find('/')
        if i < 0:
            return 'path-empty', None
        auth = tail[:i]
        path = tail[i:]
        if len(auth) > AUTH_MAX:
            return 'auth-length', None
        hcode = _host_code(auth)
        if hcode is not None:
            return hcode, None
    else:
        auth = None
        path = rest
    pcode = _path_code(path)
    if pcode is not None:
        return pcode, None
    return None, (auth, path)


def _drive_split(p):
    if len(p) >= 3 and p[0] == '/' and _letter(p[1]) and (p[2] == ':' or p[2] == '|'):
        if len(p) >= 4 and p[3] != '/':
            return None, None, p
        return p[1], p[2], p[3:]
    if len(p) >= 2 and _letter(p[0]) and (p[1] == ':' or p[1] == '|'):
        if len(p) >= 3 and p[2] != '/':
            return p[0], p[1], None
        if len(p) == 2:
            return p[0], p[1], None
        return p[0], p[1], p[2:]
    return None, None, p


def _drive_uri_code(text):
    if text == '':
        return 'empty', None
    if len(text) > TEXT_MAX:
        return 'text-length', None
    if len(text) < 5:
        return 'short', None
    if not _ici(text[:4], 'file'):
        return 'scheme', None
    if text[4] != ':':
        return 'scheme-colon', None
    rest = text[5:]
    if rest[:2] == '//':
        tail = rest[2:]
        i = tail.find('/')
        if i < 0:
            return 'path-empty', None
        auth = tail[:i]
        p = tail[i:]
        if len(auth) > AUTH_MAX:
            return 'auth-length', None
        hcode = _host_code(auth)
        if hcode is not None:
            return hcode, None
    else:
        auth = None
        p = rest
    drive, sep, path = _drive_split(p)
    if drive is not None:
        if path is None or path == '':
            return 'drive-rest', None
    pcode = _path_code(path)
    if pcode is not None:
        return pcode, None
    return None, (auth, drive, sep, path)


def is_file_uri(text):
    f = make_fail('is_file_uri')
    _text(f, text)
    code, parts = _uri_code(text)
    return code is None


def split_file_uri(text):
    f = make_fail('split_file_uri')
    _text(f, text)
    code, parts = _uri_code(text)
    if code is not None:
        f(code)
    return parts


def is_local_uri(text):
    f = make_fail('is_local_uri')
    _text(f, text)
    code, parts = _uri_code(text)
    if code is not None:
        f(code)
    auth, path = parts
    if auth is None or auth == '':
        return True
    return _ici(auth, 'localhost')


def host_kind(text):
    f = make_fail('host_kind')
    _text(f, text)
    hcode = _host_code(text)
    if hcode is not None:
        f(hcode)
    if text == '':
        return 'reg-name'
    if text[0] == '[':
        return 'literal'
    if _ipv4_ok(text):
        return 'ipv4'
    return 'reg-name'


def split_drive(path):
    f = make_fail('split_drive')
    _text(f, path)
    if len(path) < 3:
        f('path-short')
    if path[0] != '/':
        f('path-slash')
    if not _letter(path[1]):
        f('drive-letter')
    if path[2] != ':' and path[2] != '|':
        f('drive-colon')
    rest = path[3:]
    if rest == '' or rest[0] != '/':
        f('drive-rest')
    return (path[1], path[2], rest)


def split_drive_uri(text):
    f = make_fail('split_drive_uri')
    _text(f, text)
    code, parts = _drive_uri_code(text)
    if code is not None:
        f(code)
    return parts


def is_drive_uri(text):
    f = make_fail('is_drive_uri')
    _text(f, text)
    code, parts = _drive_uri_code(text)
    return code is None


def normalize_pipe(text):
    f = make_fail('normalize_pipe')
    _text(f, text)
    code, parts = _drive_uri_code(text)
    if code is not None:
        f(code)
    auth, drive, sep, path = parts
    if sep != '|':
        return text
    lead = text[5:]
    if auth is not None:
        out = text[:5] + '//' + auth + '/' + drive + ':' + path
    elif lead[:1] == '/':
        out = text[:5] + '/' + drive + ':' + path
    else:
        out = text[:5] + drive + ':' + path
    return out
