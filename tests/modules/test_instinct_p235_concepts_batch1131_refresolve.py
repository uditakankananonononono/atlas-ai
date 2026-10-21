"""Tests for p235 concepts batch 1131: RFC 3986 section 5 reference resolution. Pure functions over caller data; claims asserted False."""
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
import types
import unicodedata

import pytest
from importlib.util import find_spec

REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1131_refresolve'
NAMES = ('path_reason', 'reference_reason', 'absolute_reason', 'remove_dot_segments', 'merge_paths', 'split_reference', 'recompose',
         'resolve_components', 'resolve_reference', 'resolve_reason')
PRIVATE = ('_str', '_pct_run', '_scheme_ok', '_has_any', '_parse', '_base_check', '_merge', '_drop_last', '_dots', '_target', '_join', '_recompose',
           '_check_parts', '_resolve_text')
DOC_EXACT = 'p235 concepts batch 1131 (rev 0): RFC 3986 section 5 reference resolution. Pure functions over caller-supplied text. No retrieval, no network, no clock. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete, does not validate hosts, does not normalize and does not check any network state. ADJACENT is the empty tuple.\n\nLIVE-READ SOURCES (read live, quoted verbatim below and mechanically matched against the whitespace-collapsed RFC text with the page headers and footers removed):\n- RFC 3986, Uniform Resource Identifier (URI): Generic Syntax, STD 66, January 2005. rfc3986.txt is 141811 bytes, sha256 3102dae4b68cebe40337730312fcb612297b8928547267e8b3d1ee6002b2d683.\n- The rfc-editor info page for RFC 3986 lists: Updates RFC 1738; Updated by RFC 8820 and RFC 7320 (both titled URI Design and Ownership); Obsoletes RFC 1808, RFC 2732 and RFC 2396. It shows no Obsoleted by. This module therefore targets a current Internet Standard that later documents updated, and it does not apply those updates.\n- errata.json (sha256 2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) lists 18 errata for RFC 3986. The ones that touch the sections used here: 4547 (Held for Document Update, Technical, section 5.4.2: proposes "http://a/../g" and "http://a/../../g" for the two examples with too many ".." segments); 4789 (Held for Document Update, Technical, section 5.2.3: proposes a merge change when the base path ends with "/.."); 2933 (Held for Document Update, Editorial, section 5.2.2: argues merge should take the base and not only its path); 7590 (Verified, Editorial, section 5.2.4: a stray hyperlink in the second example); 5428 (Held for Document Update, Technical, section 4.2: relative-part and the reference "/"); 8442 (Rejected, Technical, section 4.1); 9147 (Reported, Technical, section 2.3). OURS: no erratum is applied. The RFC text and its printed examples decide. Erratum 5428 does not arise because the reference "/" is parsed as an empty authority-less path-absolute and accepted.\n\nSOURCED (the RFC text):\n- Pre-parse (5.2.1): "A component is undefined if its associated delimiter does not appear in the URI reference; the path component is never undefined, though it may be empty."\n- Base URI (5.1): "A base URI must conform to the <absolute-URI> syntax rule (Section 4.3). If the base URI is obtained from a URI reference, then that reference must be converted to absolute form and stripped of any fragment component prior to its use as a base URI."\n- Transform (5.2.2): "(R.scheme, R.authority, R.path, R.query, R.fragment) = parse(R);" "-- A non-strict parser may ignore a scheme in the reference -- if it is identical to the base URI\'s scheme." "if ((not strict) and (R.scheme == Base.scheme)) then undefine(R.scheme); endif;" "T.path = remove_dot_segments(R.path);" "T.path = merge(Base.path, R.path);" "T.fragment = R.fragment;"\n- Merge (5.2.3): "If the base URI has a defined authority component and an empty path, then return a string consisting of "/" concatenated with the reference\'s path; otherwise," "return a string consisting of the reference\'s path component appended to all but the last segment of the base URI\'s path (i.e., excluding any characters after the right-most "/" in the base URI path, or excluding the entire base URI path if it does not contain any "/" characters)."\n- Remove dot segments (5.2.4): "A. If the input buffer begins with a prefix of "../" or "./", then remove that prefix from the input buffer; otherwise," "B. if the input buffer begins with a prefix of "/./" or "/.", where "." is a complete path segment, then replace that prefix with "/" in the input buffer; otherwise," "C. if the input buffer begins with a prefix of "/../" or "/..", where ".." is a complete path segment, then replace that prefix with "/" in the input buffer and remove the last segment and its preceding "/" (if any) from the output buffer; otherwise," "D. if the input buffer consists only of "." or "..", then remove that from the input buffer; otherwise," "E. move the first path segment in the input buffer to the end of the output buffer, including the initial "/" character (if any) and any subsequent characters up to, but not including, the next "/" character or the end of the input buffer."\n- Recomposition (5.3): "Note that we are careful to preserve the distinction between a component that is undefined, meaning that its separator was not present in the reference, and a component that is empty, meaning that the separator was present and was immediately followed by the next component separator or the end of the reference."\n- Examples (5.4) use the base "http://a/b/c/d;p?q" and, for the abnormal case: "Parsers must be careful in handling cases where there are more ".." segments in a relative-path reference than there are hierarchical levels in the base URI\'s path. Note that the ".." syntax cannot be used to change the authority component of a URI." ""../../../g" = "http://a/g""\n- Grammar (Appendix A): "absolute-URI = scheme ":" hier-part [ "?" query ]" "relative-part = "//" authority path-abempty / path-absolute / path-noscheme / path-empty" "scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )" "pchar = unreserved / pct-encoded / sub-delims / ":" / "@"" "query = *( pchar / "/" / "?" )" "pct-encoded = "%" HEXDIG HEXDIG" "segment-nz-nc = 1*( unreserved / pct-encoded / sub-delims / "@" ) ; non-zero-length segment without any colon ":""\n- Appendix B splits a reference with "^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\\?([^#]*))?(#(.*))?"\n\nOURS (conventions this module adds, each pinned by tests):\n1. Authority is opaque. It is the text after "//" up to the next "/" ("?" and "#" are already split off). Userinfo, host, port and IP literals are not validated: any URI character is accepted there, including "[", "]", ":" and "@". CLAIMS host_validated is False.\n2. No case folding, percent decoding or normalization of any component. The scheme comparison in non-strict mode is literal equality, as the pseudocode writes it.\n3. Characters. The URI character set is the ASCII letters, digits, the unreserved marks "-._~", the sub-delims "!$&\'()*+,;=" and ":@/?#[]", plus "%" only as the start of a percent triplet with two ASCII hex digits (either case). Anything else, including every non-ASCII character, is refused. Membership is tested with explicit ASCII strings, never with Unicode-aware str methods.\n4. "[" and "]" are valid only in the authority. Path, query and fragment refuse them (they are gen-delims, not pchar). The fragment also refuses a second "#".\n5. A reference with a ":" before the first "/", "?" or "#" has a scheme. If that text is not a scheme (ALPHA then ALPHA, DIGIT, "+", "-", "."), the reference is refused with scheme. This is the path-noscheme rule: the first segment of a relative path has no colon. The empty string is a valid reference (relative-part is path-empty).\n6. An absolute base needs a scheme and no fragment (5.1). absolute_reason gives no_scheme, then fragment, after the reference checks pass.\n7. remove_dot_segments and merge_paths take path text only (path characters: pchar and "/"). They do not check path forms: a leading "//" or a colon in the first segment is accepted there.\n8. The target must survive recomposition. The target components are joined with 5.3, the result is parsed again, and the parse must equal the components. Otherwise target.ambiguous is reported. Example: base "a:/b/." and reference "..//c" merge to the path "//c" with no authority, which would print as "a://c". recompose uses the same rule under the name components.\n9. Output length is capped at TEXT_CAP like input length.\n\nCAPS AND CLOSURE: TEXT_CAP is 4096 characters for every text and every component, and for every output. Lengths are checked before any content is read. The output of remove_dot_segments is never longer than its input. recompose(split_reference(t)) == t for every t that split_reference accepts, and split_reference(recompose(c)) == c for every c that recompose accepts.\n\nFUNCTIONS, in this order: path_reason, reference_reason, absolute_reason, remove_dot_segments, merge_paths, split_reference, recompose, resolve_components, resolve_reference, resolve_reason. Errors are ValueError with the text P235:<function>:<code>. A code is bad_type:<name> (exact built-in type by identity, subclasses and bool-for-int refused), bad_value:<name>.length, or bad_value:<name>.<reason>.\n\nREASONS, in check order (the first failure decides, so a text with several faults reports the first):\n- path_reason: a single left-to-right pass over the text. At each position a "%" must be followed by two ASCII hex digits, otherwise pct; any other character outside the path set is char. So the first offending position decides between char and pct. ok otherwise.\n- reference_reason (and split_reference as bad_value:text.<reason>): the same single pass over the URI character set (char or pct), then scheme, then path_char, then query_char, then fragment_char. The components are cut in this order: the first "#" starts the fragment, the first "?" before it starts the query, a ":" before any "/" ends the scheme, "//" starts the authority. ok otherwise.\n- absolute_reason: the reference_reason result, then no_scheme, then fragment.\n- remove_dot_segments: type, length, then bad_value:path.<char or pct>. merge_paths: base_has_authority must be a bool (bad_type:base_has_authority), then base_path type and length, then ref_path type and length, then base_path.<char or pct>, then ref_path.<char or pct>, then bad_value:output_length.\n- recompose and the two component arguments of resolve_components: a tuple (bad_type), exactly five items (bad_value:<name>.length), then each item left to right as scheme, authority, path, query, fragment: type (None is allowed for all but the path) then length. Content is checked after the types: the joined text must fit (output_length), parse (the reference reasons) and parse back to the same components (ambiguous).\n- resolve_components: base, reference, strict (bad_type:strict), then base content, then base.no_scheme, then base.fragment, then reference content, then the target (target.output_length, target.ambiguous). Content codes are prefixed with the argument name.\n- resolve_reference and resolve_reason: base, reference, strict (types and lengths in that order), then the base reasons (base.<reference reason>, base.no_scheme, base.fragment), then reference.<reason>, then target.<reason>. resolve_reference raises bad_value:<reason>; resolve_reason returns the reason, or ok.\n\nOUTPUT ORDER: split_reference and resolve_components return a 5-tuple (scheme, authority, path, query, fragment). A component is None when undefined and a string, possibly empty, when defined. The path is always a string. resolve_reference returns the recomposed target text.\n'
QUOTES = ['(R.scheme, R.authority, R.path, R.query, R.fragment) = parse(R);', "-- A non-strict parser may ignore a scheme in the reference -- if it is identical to the base URI's scheme.", 'if ((not strict) and (R.scheme == Base.scheme)) then undefine(R.scheme); endif;', 'T.path = remove_dot_segments(R.path);', 'T.path = merge(Base.path, R.path);', 'T.fragment = R.fragment;', 'If the base URI has a defined authority component and an empty path, then return a string consisting of "/" concatenated with the reference\'s path; otherwise,', 'return a string consisting of the reference\'s path component appended to all but the last segment of the base URI\'s path (i.e., excluding any characters after the right-most "/" in the base URI path, or excluding the entire base URI path if it does not contain any "/" characters).', 'A. If the input buffer begins with a prefix of "../" or "./", then remove that prefix from the input buffer; otherwise,', 'B. if the input buffer begins with a prefix of "/./" or "/.", where "." is a complete path segment, then replace that prefix with "/" in the input buffer; otherwise,', 'C. if the input buffer begins with a prefix of "/../" or "/..", where ".." is a complete path segment, then replace that prefix with "/" in the input buffer and remove the last segment and its preceding "/" (if any) from the output buffer; otherwise,', 'D. if the input buffer consists only of "." or "..", then remove that from the input buffer; otherwise,', 'E. move the first path segment in the input buffer to the end of the output buffer, including the initial "/" character (if any) and any subsequent characters up to, but not including, the next "/" character or the end of the input buffer.', 'Note that we are careful to preserve the distinction between a component that is undefined, meaning that its separator was not present in the reference, and a component that is empty, meaning that the separator was present and was immediately followed by the next component separator or the end of the reference.', 'A component is undefined if its associated delimiter does not appear in the URI reference; the path component is never undefined, though it may be empty.', 'A base URI must conform to the <absolute-URI> syntax rule (Section 4.3). If the base URI is obtained from a URI reference, then that reference must be converted to absolute form and stripped of any fragment component prior to its use as a base URI.', 'http://a/b/c/d;p?q', 'Parsers must be careful in handling cases where there are more ".." segments in a relative-path reference than there are hierarchical levels in the base URI\'s path. Note that the ".." syntax cannot be used to change the authority component of a URI.', '"../../../g" = "http://a/g"', 'absolute-URI = scheme ":" hier-part [ "?" query ]', 'relative-part = "//" authority path-abempty / path-absolute / path-noscheme / path-empty', 'scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )', 'pchar = unreserved / pct-encoded / sub-delims / ":" / "@"', 'query = *( pchar / "/" / "?" )', 'pct-encoded = "%" HEXDIG HEXDIG', 'segment-nz-nc = 1*( unreserved / pct-encoded / sub-delims / "@" ) ; non-zero-length segment without any colon ":"', '^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\\?([^#]*))?(#(.*))?']
HERE = os.path.dirname(os.path.abspath(__file__))
import app.modules.instinct_doc.p235_concepts_batch1131_refresolve as m  # noqa: E402
MODPATH = m.__file__


def _prefix():
    spec = importlib.util.spec_from_file_location('b1131_pfx', MODPATH)
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


def fresh(name='b1131_fresh'):
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


# ---- independent oracle (regex from the RFC grammar, Appendix B regex, a different remove_dot_segments) ---------
_PC = r"(?:[A-Za-z0-9\-._~!$&'()*+,;=:@]|%[0-9A-Fa-f]{2})"
_PCNC = r"(?:[A-Za-z0-9\-._~!$&'()*+,;=@]|%[0-9A-Fa-f]{2})"
_AU = r"(?:[A-Za-z0-9\-._~!$&'()*+,;=:@\[\]]|%[0-9A-Fa-f]{2})*"
_PABE = r"(?:/" + _PC + r"*)*"
_PABS = r"/(?:" + _PC + r"+(?:/" + _PC + r"*)*)?"
_PROOT = _PC + r"+(?:/" + _PC + r"*)*"
_PNOS = _PCNC + r"+(?:/" + _PC + r"*)*"
_Q = r"(?:" + _PC + r"|[/?])*"
_SCH = r"[A-Za-z][A-Za-z0-9+.\-]*"
_URI = re.compile(_SCH + r":(?://" + _AU + _PABE + r"|" + _PABS + r"|" + _PROOT + r"|)(?:\?" + _Q + r")?(?:#" + _Q + r")?", re.S)
_ABS = re.compile(_SCH + r":(?://" + _AU + _PABE + r"|" + _PABS + r"|" + _PROOT + r"|)(?:\?" + _Q + r")?", re.S)
_REL = re.compile(r"(?://" + _AU + _PABE + r"|" + _PABS + r"|" + _PNOS + r"|)(?:\?" + _Q + r")?(?:#" + _Q + r")?", re.S)
_APPB = re.compile(r"(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?", re.S)
_PATHRE = re.compile(r"(?:[A-Za-z0-9\-._~!$&'()*+,;=:@/]|%[0-9A-Fa-f]{2})*", re.S)
_URICSET = set(chr(i) for i in range(128) if re.fullmatch(r"[A-Za-z0-9\-._~!$&'()*+,;=:@/?#\[\]]", chr(i)))
_PATHSET = set(chr(i) for i in range(128) if re.fullmatch(r"[A-Za-z0-9\-._~!$&'()*+,;=:@/]", chr(i)))


def o_valid(t):
    return (_URI.fullmatch(t) or _REL.fullmatch(t)) is not None


def o_pass(t, allowed):
    i = 0
    while i < len(t):
        c = t[i]
        if c == '%':
            if re.fullmatch(r'%[0-9A-Fa-f]{2}', t[i:i + 3]) is None:
                return 'pct'
            i += 3
            continue
        if c not in allowed:
            return 'char'
        i += 1
    return 'ok'


def o_parse(t):
    r = o_pass(t, _URICSET)
    if r != 'ok':
        return (r, None)
    g = _APPB.fullmatch(t)
    scheme, authority, path, query, fragment = g.group(2), g.group(4), g.group(5), g.group(7), g.group(9)
    if g.group(1) is None and ':' in re.split(r'[/?#]', t)[0]:
        return ('scheme', None)
    if scheme is not None and re.fullmatch(_SCH, scheme) is None:
        return ('scheme', None)
    if '[' in path or ']' in path:
        return ('path_char', None)
    if query is not None and ('[' in query or ']' in query):
        return ('query_char', None)
    if fragment is not None and ('[' in fragment or ']' in fragment or '#' in fragment):
        return ('fragment_char', None)
    return ('ok', (scheme, authority, path, query, fragment))


def o_rds(path):
    inp, out = path, ''
    while inp:
        if re.match(r'\.\./|\./', inp):
            inp = inp[3:] if inp.startswith('../') else inp[2:]
        elif re.match(r'/\./', inp) or inp == '/.':
            inp = '/' + inp[3:]
        elif re.match(r'/\.\./', inp) or inp == '/..':
            inp = '/' + inp[4:]
            out = out[:out.rindex('/')] if '/' in out else ''
        elif inp in ('.', '..'):
            inp = ''
        else:
            g = re.match(r'/?[^/]*', inp)
            out += g.group(0)
            inp = inp[g.end():]
    return out


def o_rds_stack(path):
    if not path.startswith('/'):
        return None
    segs = path[1:].split('/')
    res = []
    for i, s in enumerate(segs):
        last = i == len(segs) - 1
        if s == '.':
            if last:
                res.append('')
        elif s == '..':
            if res:
                res.pop()
            if last:
                res.append('')
        else:
            res.append(s)
    return '/' + '/'.join(res)


def o_merge(has_auth, bp, rp):
    if has_auth and bp == '':
        return '/' + rp
    return bp[:bp.rindex('/') + 1] + rp if '/' in bp else rp


def o_join(c):
    s = ''
    if c[0] is not None:
        s += c[0] + ':'
    if c[1] is not None:
        s += '//' + c[1]
    s += c[2]
    if c[3] is not None:
        s += '?' + c[3]
    if c[4] is not None:
        s += '#' + c[4]
    return s


def o_recompose(c):
    s = o_join(c)
    if len(s) > 4096:
        return ('output_length', None)
    r = o_parse(s)
    if r[0] != 'ok':
        return (r[0], None)
    return ('ok', s) if r[1] == c else ('ambiguous', None)


def o_target(b, r, strict):
    rs = r[0]
    if not strict and rs == b[0]:
        rs = None
    if rs is not None:
        return (rs, r[1], o_rds(r[2]), r[3], r[4])
    if r[1] is not None:
        return (b[0], r[1], o_rds(r[2]), r[3], r[4])
    if r[2] == '':
        return (b[0], b[1], b[2], r[3] if r[3] is not None else b[3], r[4])
    if r[2].startswith('/'):
        return (b[0], b[1], o_rds(r[2]), r[3], r[4])
    return (b[0], b[1], o_rds(o_merge(b[1] is not None, b[2], r[2])), r[3], r[4])


def o_resolve(bt, rt, strict):
    b = o_parse(bt)
    if b[0] != 'ok':
        return 'base.' + b[0], None
    if b[1][0] is None:
        return 'base.no_scheme', None
    if b[1][4] is not None:
        return 'base.fragment', None
    r = o_parse(rt)
    if r[0] != 'ok':
        return 'reference.' + r[0], None
    rr = o_recompose(o_target(b[1], r[1], strict))
    if rr[0] != 'ok':
        return 'target.' + rr[0], None
    return 'ok', rr[1]


BASE = 'http://a/b/c/d;p?q'
BASEC = ('http', 'a', '/b/c/d;p', 'q', None)
REFC = (None, None, 'g', 'y', 's')
COMPS = ('http', 'a', '/b/c/g', 'y', 's')
LOOKALIKES = ['\u0663', '\uff11', '\u00b2', '\u212a', '\u0131', '\u017f', '\u0660', '\u2467', '\u00a0', '\u2003', '\uff21', '\u0130', '\u037e', '\uff1b', '\uff1d',
              '\u201c', '\u2033', '\u2215', '\u2028', '\u0085', '\u1680', '\uff0c', '\uff01', '\uff1a', '\u212b', '\u2126', '\u1e9e', '\ufb01', '\uff0e', '\u2024',
              '\uff3f', '\u2010', '\u2212', '\uff5e', '\u2018', '\u2019', '\uff02', '\uff0f', '\uff1f', '\uff03', '\uff05', '\uff3b', '\uff3d', '\u2044', '\u00e9']
ARGSPEC = {'path_reason': [('text', 'a/b')], 'reference_reason': [('text', 'g')], 'absolute_reason': [('text', 'http://a/b')],
           'remove_dot_segments': [('path', '/a/./b')],
           'merge_paths': [('base_has_authority', True), ('base_path', '/b/c'), ('ref_path', 'g')],
           'split_reference': [('text', 'g?y#s')], 'recompose': [('components', COMPS)],
           'resolve_components': [('base', BASEC), ('reference', REFC), ('strict', True)],
           'resolve_reference': [('base', BASE), ('reference', 'g'), ('strict', True)],
           'resolve_reason': [('base', BASE), ('reference', 'g'), ('strict', True)]}


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
TUP_JUNK = [None, 1, 0, True, False, 'a', '', b'a', [], list(COMPS), {'a': 1}, object(), T(), T(COMPS)]
BOOL_JUNK = [None, 1, 0, 2, 'True', '', b'', [], (), 1.0, object(), BoolLike(1), BoolLike(0)]


# ---- constants, shape ----------------------------------------------------------------------------------------------
def test_constants_exact():
    assert m.SCOPE == 'RFC 3986 section 5 reference resolution over caller-supplied text: split, merge, remove_dot_segments, recompose and resolve'
    assert m.NOT_CLAIMED == ('standard', 'authority', 'certification', 'currency', 'completeness', 'host-validation', 'normalization', 'network-use')
    assert m.CLAIMS == {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False,
                        'host_validated': False, 'normalized': False, 'network_checked': False}
    assert all(v is False for v in m.CLAIMS.values()) and m.ADJACENT == () and type(m.ADJACENT) is tuple and m.TEXT_CAP == 4096
    assert m.DIGITS == '0123456789' and m.UPPER == 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' and m.LOWER == 'abcdefghijklmnopqrstuvwxyz' and m._REG == REG
    assert m.HEXDIG == '0123456789ABCDEFabcdef' and m.UNRESERVED == m.UPPER + m.LOWER + m.DIGITS + '-._~'
    assert m.SUBDELIM == "!$&'()*+,;=" and m.PATHC == m.UNRESERVED + m.SUBDELIM + ':@/' and m.URIC == m.PATHC + '?#[]' and m.SCHEMEC == m.UPPER + m.LOWER + m.DIGITS + '+-.'
    for s in (m.HEXDIG, m.UNRESERVED, m.SUBDELIM, m.PATHC, m.URIC, m.SCHEMEC):
        assert len(set(s)) == len(s)
    assert (len(m.HEXDIG), len(m.UNRESERVED), len(m.SUBDELIM), len(m.PATHC), len(m.URIC), len(m.SCHEMEC)) == (22, 66, 11, 80, 84, 65)


@pytest.mark.parametrize('i', range(256))
def test_char_classes_for_every_code(i):
    c = chr(i)
    assert (c in m.HEXDIG) == (re.fullmatch(r'[0-9A-Fa-f]', c) is not None)
    assert (c in m.UNRESERVED) == (re.fullmatch(r'[A-Za-z0-9\-._~]', c) is not None)
    assert (c in m.SUBDELIM) == (c in "!$&'()*+,;=" and c != '')
    assert (c in m.PATHC) == (c in _PATHSET) and (c in m.URIC) == (c in _URICSET)
    assert (c in m.SCHEMEC) == (re.fullmatch(r'[A-Za-z0-9+.\-]', c) is not None)
    ok_path = 'ok' if c in _PATHSET else 'char'
    assert m.path_reason('a' + c) == (o_pass('a' + c, _PATHSET) if c != '%' else 'pct') and m.path_reason(c + 'a') == (o_pass(c + 'a', _PATHSET) if c != '%' else 'pct')
    if c != '%':
        assert m.path_reason(c) == ok_path and m.path_reason('a' + c + 'b') == ok_path
    ok_uri = 'ok' if (c in _URICSET and c not in '[]#?:/') else None
    for t in ('//' + c, '//a' + c, '/' + c, 'a/' + c, '?' + c, '?a' + c, '#' + c, '#a' + c, 'a' + c + ':', c + 'a:', 'a:' + c, '//a/' + c):
        assert m.reference_reason(t) == o_parse(t)[0], (i, t)
        assert run('split_reference', t) == (('ok', o_parse(t)[1]) if o_parse(t)[0] == 'ok' else E('split_reference', 'bad_value:text.' + o_parse(t)[0])), (i, t)
        assert m.absolute_reason(t) == (o_parse(t)[0] if o_parse(t)[0] != 'ok' else ('no_scheme' if o_parse(t)[1][0] is None else ('fragment' if o_parse(t)[1][4] is not None else 'ok'))), (i, t)
    for t in ('%' + c + '0', '%0' + c, '%' + c + c, 'a%' + c + '0'):
        assert m.reference_reason(t) == o_parse(t)[0] and m.path_reason(t) == o_pass(t, _PATHSET), (i, t)
    for t in ('/a/' + c, '/' + c + '/..', c, 'a' + c):
        assert run('remove_dot_segments', t)[0] == ('ok' if o_pass(t, _PATHSET) == 'ok' else 'err'), (i, t)
    if ok_uri is None and c in ('\u0000',):
        assert m.reference_reason(c) == 'char'


@pytest.mark.parametrize('ch', LOOKALIKES)
def test_lookalikes_are_refused_everywhere(ch):
    for s in (m.HEXDIG, m.UNRESERVED, m.SUBDELIM, m.PATHC, m.URIC, m.SCHEMEC, m.DIGITS, m.UPPER, m.LOWER):
        assert ch not in s
    for t in ('a' + ch, ch + 'a', '//' + ch, '//a' + ch, '/' + ch, '?' + ch, '#' + ch, 'a' + ch + ':', ch + ':', 'a:' + ch, 'a:b?' + ch + '#c', '%' + ch + '0', '%0' + ch):
        want = 'pct' if '%' in t else ('char' if (ch + ':' != t and ch + 'a' + ':' != t) else 'char')
        assert m.reference_reason(t) == want, t
        assert m.path_reason(t) == want and m.absolute_reason(t) == want, t
        assert run('split_reference', t) == E('split_reference', 'bad_value:text.' + want), t
        assert run('resolve_reference', BASE, t, True) == E('resolve_reference', 'bad_value:reference.' + want), t
        assert run('resolve_reference', t, 'g', True) == E('resolve_reference', 'bad_value:base.' + want), t
        assert run('remove_dot_segments', t) == E('remove_dot_segments', 'bad_value:path.' + want), t
        assert run('merge_paths', True, t, 'g') == E('merge_paths', 'bad_value:base_path.' + want), t
        assert run('merge_paths', True, '/a', t) == E('merge_paths', 'bad_value:ref_path.' + want), t
    assert run('recompose', (ch, 'a', '', None, None)) == E('recompose', 'bad_value:components.char')
    assert run('recompose', (None, None, 'a' + ch, None, None)) == E('recompose', 'bad_value:components.char')


NDS = [chr(i) for i in range(sys.maxunicode + 1) if unicodedata.category(chr(i)) == 'Nd' and i > 127]


def test_every_unicode_decimal_digit_is_refused_in_every_slot():
    assert len(NDS) > 500
    for d in NDS:
        assert m.path_reason('a' + d) == 'char' and m.reference_reason('a' + d) == 'char' and m.reference_reason('http://a/' + d) == 'char'
        assert m.reference_reason('1' + d + ':') == 'char' and m.reference_reason('%' + d + '0') == 'pct' and m.reference_reason('%0' + d) == 'pct'
        assert m.reference_reason('a:b?' + d) == 'char' and m.reference_reason('a:b#' + d) == 'char' and m.reference_reason('a' + d + ':b') == 'char'


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
    assert len(QUOTES) == 27 and len(set(QUOTES)) == 27
    for q in QUOTES:
        assert re.sub(r'\s+', ' ', q) in flat, q


def test_header_names_every_erratum_source_and_function():
    d = m.__doc__
    for tok in ('4547', '4789', '2933', '7590', '5428', '8442', '9147', '18 errata', 'RFC 8820', 'RFC 7320', 'RFC 1808', 'RFC 2732', 'RFC 2396', 'RFC 1738',
                '3102dae4b68cebe40337730312fcb612297b8928547267e8b3d1ee6002b2d683', '2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66', '141811 bytes',
                'Obsoleted by'):
        assert tok in d, tok
    for n in NAMES:
        assert n in d, n
    for r in ('pct', 'char', 'scheme', 'path_char', 'query_char', 'fragment_char', 'no_scheme', 'fragment', 'output_length', 'ambiguous', 'target.', 'base.', 'reference.'):
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
    assert sorted(names) == ['ADJACENT', 'CLAIMS', 'DIGITS', 'HEXDIG', 'LOWER', 'ModuleNotFoundError', 'NOT_CLAIMED', 'PATHC', 'SCHEMEC', 'SCOPE', 'SUBDELIM', 'TEXT_CAP', 'UNRESERVED', 'UPPER', 'URIC', 'ValueError', '_REG', '_base_check', '_check_parts', '_dots', '_drop_last', '_has_any', '_join', '_merge', '_parse', '_pct_run', '_recompose', '_resolve_text', '_scheme_ok', '_steps', '_str', '_target', 'authority', 'base', 'base_has_authority', 'base_path', 'base_text', 'bool', 'cap', 'ch', 'chars', 'checked', 'code', 'components', 'end', 'exc', 'fail', 'find_spec', 'fragment', 'has_authority', 'hier', 'i', 'inp', 'j', 'k', 'labels', 'len', 'make_fail', 'name', 'ok', 'out', 'parsed', 'parts', 'path', 'query', 'range', 'reason', 'ref', 'ref_path', 'ref_text', 'reference', 'reference_text', 'rest', 'result', 'scheme', 'skip', 'str', 'strict', 'target', 'text', 'tuple', 'type', 'value']
    for node in ast.walk(tree):
        assert not isinstance(node, (ast.Lambda, ast.Global, ast.Nonlocal, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.Starred, ast.JoinedStr, ast.Await, ast.Yield))
    src = _src()
    banned = [' or ' + 'True', 'if ' + 'False', 'else ' + 'True', ' and ' + 'False', ' or ' + 'False']
    for b in banned:
        assert b not in src, b
    assert 'import *' not in src


def test_source_and_tests_have_no_vacuous_assertions():
    me = open(os.path.join(HERE, 'test_instinct_p235_concepts_batch1131_refresolve.py')).read()
    for b in (' or ' + 'True', 'if ' + 'False:', 'else ' + 'True', ' and ' + 'False', ' or ' + 'False', 'assert ' + 'True', 'assert ' + '1 ', 'assert ' + 'not ' + 'False'):
        assert b not in me, b


# ---- exact types ---------------------------------------------------------------------------------------------------
def arg_vectors(fn):
    spec = ARGSPEC[fn]
    base = [g for _n, g in spec]
    for pos, (name, good) in enumerate(spec):
        if type(good) is bool:
            bads = BOOL_JUNK
        elif type(good) is tuple:
            bads = TUP_JUNK
        else:
            bads = JUNK + STR_HOSTILE + [BoolLike(1)]
        for bad in bads:
            args = list(base)
            args[pos] = bad
            yield pos, name, args


@pytest.mark.parametrize('fn', NAMES)
def test_every_argument_is_an_exact_type_by_identity(fn):
    n = 0
    for pos, name, args in arg_vectors(fn):
        assert run(fn, *args) == E(fn, 'bad_type:' + name), (fn, pos, args[pos])
        n += 1
    assert n >= 14


def test_bool_arguments_accept_only_the_two_bool_singletons():
    for st in (True, False):
        assert run('resolve_reference', BASE, 'g', st)[0] == 'ok' and run('resolve_reason', BASE, 'g', st) == ('ok', 'ok')
        assert run('resolve_components', BASEC, REFC, st)[0] == 'ok'
    for ha in (True, False):
        assert run('merge_paths', ha, '/b/c', 'g') == ('ok', '/b/g')


def test_component_slots_are_exact_types_at_every_site():
    ok = ('http', 'a', '/p', 'q', 'f')
    for fn, pre, post in (('recompose', (), ()), ('resolve_components', (), (REFC, True)), ('resolve_components', (BASEC,), (True,))):
        pos = 0 if fn == 'recompose' or not pre else 1
        for k, nm in enumerate(('scheme', 'authority', 'path', 'query', 'fragment')):
            for bad in (1, True, b'a', ['a'], S('a'), SM('a'), EqAll('a'), object(), 1.5):
                c = list(ok)
                c[k] = bad
                args = list(pre) + [tuple(c)] + list(post)
                label = 'components' if fn == 'recompose' else ('base' if not pre else 'reference')
                assert run(fn, *args) == E(fn, 'bad_type:' + label + '.' + nm), (fn, nm, bad)
    for bad in (None, 1, [], S('x'), SM('x'), EqAll('x'), object(), b''):
        assert run('recompose', ('http', 'a', bad, 'q', 'f')) == E('recompose', 'bad_type:components.path')
    for k in (0, 1, 3, 4):
        c = list(ok)
        c[k] = None
        assert run('recompose', tuple(c))[0] == 'ok'
    assert run('recompose', (None, None, '', None, None)) == ('ok', '')


def test_tuple_length_five_exactly_and_before_items():
    for n in (0, 1, 4, 6, 7):
        assert run('recompose', ('a',) * n) == E('recompose', 'bad_value:components.length')
    assert run('recompose', (5, 5, 5, 5)) == E('recompose', 'bad_value:components.length')
    assert run('recompose', (5, 5, 5, 5, 5, 5)) == E('recompose', 'bad_value:components.length')
    assert run('resolve_components', ('a',) * 4, REFC, True) == E('resolve_components', 'bad_value:base.length')
    assert run('resolve_components', BASEC, ('a',) * 6, True) == E('resolve_components', 'bad_value:reference.length')
    assert run('resolve_components', ('a',) * 4, ('a',) * 6, 5) == E('resolve_components', 'bad_value:base.length')
    assert run('resolve_components', BASEC, ('a',) * 6, 5) == E('resolve_components', 'bad_value:reference.length')
    assert run('resolve_components', BASEC, REFC, 5) == E('resolve_components', 'bad_type:strict')
    assert run('resolve_components', ('a',) * 4, 5, 5) == E('resolve_components', 'bad_value:base.length')
    assert run('resolve_components', 5, 5, 5) == E('resolve_components', 'bad_type:base')


# ---- caps: pinned at cap and cap + 1, length before content ----------------------------------------------------------
def test_text_caps_pinned_at_cap_and_cap_plus_one():
    for fn in ('path_reason', 'reference_reason', 'absolute_reason'):
        assert run(fn, 'a' * 4096)[0] == 'ok'
        assert run(fn, 'a' * 4097) == E(fn, 'bad_value:text.length')
        assert run(fn, '\x01' * 4097) == E(fn, 'bad_value:text.length')
        assert run(fn, '\x01' * 4096)[0] == 'ok' and run(fn, '\x01' * 4096)[1] in ('char', 'pct')
    assert run('split_reference', 'a' * 4096)[0] == 'ok' and run('split_reference', 'a' * 4097) == E('split_reference', 'bad_value:text.length')
    assert run('split_reference', '\x01' * 4097) == E('split_reference', 'bad_value:text.length')
    assert run('remove_dot_segments', 'a' * 4096) == ('ok', 'a' * 4096) and run('remove_dot_segments', 'a' * 4097) == E('remove_dot_segments', 'bad_value:path.length')
    assert run('remove_dot_segments', '\x01' * 4097) == E('remove_dot_segments', 'bad_value:path.length')
    assert run('merge_paths', True, 'a' * 4096, '')[0] == 'ok' and run('merge_paths', True, 'a' * 4097, '') == E('merge_paths', 'bad_value:base_path.length')
    assert run('merge_paths', True, '', 'a' * 4095)[0] == 'ok' and run('merge_paths', True, '', 'a' * 4096) == E('merge_paths', 'bad_value:output_length')
    assert run('merge_paths', False, '', 'a' * 4096)[0] == 'ok' and run('merge_paths', True, '', 'a' * 4097) == E('merge_paths', 'bad_value:ref_path.length')
    assert run('merge_paths', True, 'a' * 4097, 'a' * 4097) == E('merge_paths', 'bad_value:base_path.length')
    assert run('merge_paths', True, '\x01' * 4097, '\x01') == E('merge_paths', 'bad_value:base_path.length')
    assert run('merge_paths', True, '\x01', '\x01' * 4097) == E('merge_paths', 'bad_value:ref_path.length')
    for fn in ('resolve_reference', 'resolve_reason'):
        assert run(fn, 'a:' + 'b' * 4094, '', True)[0] == 'ok'
        assert run(fn, 'a:' + 'b' * 4095, '', True) == E(fn, 'bad_value:base.length')
        assert run(fn, BASE, 'h:' + 'a' * 4094, True)[0] == 'ok'
        assert run(fn, BASE, 'a' * 4096, True) == E(fn, 'bad_value:target.output_length') if fn == 'resolve_reference' else run(fn, BASE, 'a' * 4096, True) == ('ok', 'target.output_length')
        assert run(fn, BASE, 'a' * 4097, True) == E(fn, 'bad_value:reference.length')
        assert run(fn, 'a' * 4097, 'a' * 4097, True) == E(fn, 'bad_value:base.length')
        assert run(fn, '\x01', 'a' * 4097, True) == E(fn, 'bad_value:reference.length')
        assert run(fn, 'a' * 4097, 5, True) == E(fn, 'bad_value:base.length')
        assert run(fn, 'a' * 4097, 'g', 5) == E(fn, 'bad_value:base.length')
        assert run(fn, BASE, 'a' * 4097, 5) == E(fn, 'bad_value:reference.length')
        assert run(fn, BASE, 5, 5) == E(fn, 'bad_type:reference')
        assert run(fn, 5, 5, 5) == E(fn, 'bad_type:base')
        assert run(fn, BASE, 'g', 5) == E(fn, 'bad_type:strict')
        assert run(fn, 5, 'g', 5) == E(fn, 'bad_type:base')


def test_component_caps_pinned_at_cap_and_cap_plus_one():
    for k, nm in ((0, 'scheme'), (1, 'authority'), (2, 'path'), (3, 'query'), (4, 'fragment')):
        for fn, build, label in (('recompose', lambda c: (c,), 'components'),):
            c = ['http', 'a', '/p', 'q', 'f']
            c[k] = 'a' * 4097
            assert run(fn, *build(tuple(c))) == E(fn, 'bad_value:' + label + '.' + nm + '.length'), nm
            c[k] = '\x01' * 4097
            assert run(fn, *build(tuple(c))) == E(fn, 'bad_value:' + label + '.' + nm + '.length'), nm
            c[k] = 'a' * 4096
            assert run(fn, *build(tuple(c))) == E(fn, 'bad_value:components.output_length'), nm
        c = ['http', 'a', '/p', 'q', 'f']
        c[k] = 'a' * 4097
        assert run('resolve_components', tuple(c), REFC, True) == E('resolve_components', 'bad_value:base.' + nm + '.length')
        assert run('resolve_components', BASEC, tuple(c), True) == E('resolve_components', 'bad_value:reference.' + nm + '.length')
    assert run('recompose', (None, None, 'a' * 4096, None, None)) == ('ok', 'a' * 4096)
    assert run('recompose', (None, None, 'a' * 4095, '', None))[0] == 'ok' and run('recompose', (None, None, 'a' * 4096, '', None)) == E('recompose', 'bad_value:components.output_length')
    assert run('recompose', (None, None, 'a' * 4094, 'b', None)) == ('ok', 'a' * 4094 + '?b') and len(m.recompose((None, None, 'a' * 4094, 'b', None))) == 4096
    assert run('recompose', (None, None, 'a' * 4095, 'b', None)) == E('recompose', 'bad_value:components.output_length')
    assert run('recompose', ('s', None, 'a' * 4094, None, None))[0] == 'ok' and run('recompose', ('s', None, 'a' * 4095, None, None)) == E('recompose', 'bad_value:components.output_length')
    assert run('recompose', (None, 'x', '/' + 'a' * 4092, None, None))[0] == 'ok' and run('recompose', (None, 'x', '/' + 'a' * 4093, None, None)) == E('recompose', 'bad_value:components.output_length')
    assert run('recompose', (None, None, 'a' * 4094, None, 'f'))[0] == 'ok' and run('recompose', (None, None, 'a' * 4095, None, 'f')) == E('recompose', 'bad_value:components.output_length')
    assert run('recompose', (None, 'x' * 4094, '', None, None))[0] == 'ok' and run('recompose', (None, 'x' * 4095, '', None, None)) == E('recompose', 'bad_value:components.output_length')


def test_output_caps_of_merge_and_resolve_pinned_at_cap_and_cap_plus_one():
    assert run('merge_paths', True, '/' + 'a' * 2000 + '/', 'b' * 2094)[0] == 'ok' and len(m.merge_paths(True, '/' + 'a' * 2000 + '/', 'b' * 2094)) == 4096
    assert run('merge_paths', True, '/' + 'a' * 2000 + '/', 'b' * 2095) == E('merge_paths', 'bad_value:output_length')
    assert run('merge_paths', True, '', 'b' * 4095) == ('ok', '/' + 'b' * 4095)
    assert run('merge_paths', True, '', 'b' * 4096) == E('merge_paths', 'bad_value:output_length')
    assert run('merge_paths', False, '', 'b' * 4096) == ('ok', 'b' * 4096)
    bt = 'http://a/' + 'p' * 2000 + '/d'
    ok_len = 4096 - len('http://a/' + 'p' * 2000 + '/')
    assert run('resolve_reference', bt, 'r' * ok_len, True)[0] == 'ok' and len(m.resolve_reference(bt, 'r' * ok_len, True)) == 4096
    assert run('resolve_reference', bt, 'r' * (ok_len + 1), True) == E('resolve_reference', 'bad_value:target.output_length')
    assert run('resolve_reason', bt, 'r' * (ok_len + 1), True) == ('ok', 'target.output_length')
    bc = ('http', 'a', '/' + 'p' * 2000 + '/d', None, None)
    assert run('resolve_components', bc, (None, None, 'r' * (ok_len + 1), None, None), True) == E('resolve_components', 'bad_value:target.output_length')
    assert run('resolve_components', bc, (None, None, 'r' * ok_len, None, None), True) == ('ok', ('http', 'a', '/' + 'p' * 2000 + '/' + 'r' * ok_len, None, None))


# ---- memory: caps are checked before work ---------------------------------------------------------------------------
def test_cap_is_checked_before_any_allocation_or_scan():
    big = 'a' * 4097
    tracemalloc.start()
    try:
        for fn, args in (('path_reason', (big,)), ('reference_reason', (big,)), ('absolute_reason', (big,)), ('remove_dot_segments', (big,)), ('split_reference', (big,)),
                         ('merge_paths', (True, big, big)), ('resolve_reference', (big, big, True)), ('resolve_reason', (big, big, True))):
            tracemalloc.clear_traces()
            tracemalloc.reset_peak()
            base = tracemalloc.get_traced_memory()[0]
            r = run(fn, *args)
            peak = tracemalloc.get_traced_memory()[1] - base
            assert r[0] == 'err' and peak < 4000, (fn, peak)
    finally:
        tracemalloc.stop()


# ---- no input mutation, no global state ---------------------------------------------------------------------------------
def test_results_are_fresh_exact_types_and_inputs_are_not_mutated():
    c = ('http', 'a', '/b/c/d;p', 'q', None)
    before = tuple(c)
    r = m.resolve_components(c, (None, None, '../g', None, 'z'), True)
    assert c == before and type(r) is tuple and len(r) == 5 and r == ('http', 'a', '/b/g', None, 'z')
    for v in r:
        assert v is None or type(v) is str
    s = m.split_reference('http://a/b?q#f')
    assert type(s) is tuple and s == ('http', 'a', '/b', 'q', 'f') and all(type(v) is str for v in s)
    assert type(m.resolve_reference(BASE, 'g', True)) is str and type(m.recompose(COMPS)) is str and type(m.remove_dot_segments('/a')) is str and type(m.merge_paths(True, '', 'a')) is str
    for fn, args in (('path_reason', ('a',)), ('reference_reason', ('a',)), ('absolute_reason', ('a:b',)), ('resolve_reason', (BASE, 'g', True))):
        assert type(getattr(m, fn)(*args)) is str
    assert m.split_reference('a') is not m.split_reference('a')


import random
import traceback


# ---- RFC 5.4.1 normal examples and 5.4.2 abnormal examples, base http://a/b/c/d;p?q ------------------------------------
NORMAL = [('g:h', 'g:h'), ('g', 'http://a/b/c/g'), ('./g', 'http://a/b/c/g'), ('g/', 'http://a/b/c/g/'), ('/g', 'http://a/g'),
          ('//g', 'http://g'), ('?y', 'http://a/b/c/d;p?y'), ('g?y', 'http://a/b/c/g?y'), ('#s', 'http://a/b/c/d;p?q#s'),
          ('g#s', 'http://a/b/c/g#s'), ('g?y#s', 'http://a/b/c/g?y#s'), (';x', 'http://a/b/c/;x'), ('g;x', 'http://a/b/c/g;x'),
          ('g;x?y#s', 'http://a/b/c/g;x?y#s'), ('', 'http://a/b/c/d;p?q'), ('.', 'http://a/b/c/'), ('./', 'http://a/b/c/'),
          ('..', 'http://a/b/'), ('../', 'http://a/b/'), ('../g', 'http://a/b/g'), ('../..', 'http://a/'),
          ('../../', 'http://a/'), ('../../g', 'http://a/g')]
ABNORMAL = [('../../../g', 'http://a/g'), ('../../../../g', 'http://a/g'), ('/./g', 'http://a/g'), ('/../g', 'http://a/g'),
            ('g.', 'http://a/b/c/g.'), ('.g', 'http://a/b/c/.g'), ('g..', 'http://a/b/c/g..'), ('..g', 'http://a/b/c/..g'),
            ('./../g', 'http://a/b/g'), ('./g/.', 'http://a/b/c/g/'), ('g/./h', 'http://a/b/c/g/h'), ('g/../h', 'http://a/b/c/h'),
            ('g;x=1/./y', 'http://a/b/c/g;x=1/y'), ('g;x=1/../y', 'http://a/b/c/y'), ('g?y/./x', 'http://a/b/c/g?y/./x'),
            ('g?y/../x', 'http://a/b/c/g?y/../x'), ('g#s/./x', 'http://a/b/c/g#s/./x'), ('g#s/../x', 'http://a/b/c/g#s/../x')]


@pytest.mark.parametrize('ref,want', NORMAL + ABNORMAL)
def test_rfc_5_4_resolution_examples_strict_and_non_strict(ref, want):
    for strict in (True, False):
        assert m.resolve_reference(BASE, ref, strict) == want
        assert m.resolve_reason(BASE, ref, strict) == 'ok'
        assert o_resolve(BASE, ref, strict) == ('ok', want)
        got = m.resolve_components(BASEC, o_parse(ref)[1], strict)
        assert o_join(got) == want


def test_strict_and_non_strict_same_scheme_reference():
    assert m.resolve_reference(BASE, 'http:g', True) == 'http:g'
    assert m.resolve_reference(BASE, 'http:g', False) == 'http://a/b/c/g'
    assert m.resolve_reason(BASE, 'http:g', False) == 'ok' and o_resolve(BASE, 'http:g', False) == ('ok', 'http://a/b/c/g')
    assert m.resolve_components(BASEC, ('http', None, 'g', None, None), False) == ('http', 'a', '/b/c/g', None, None)
    assert m.resolve_components(BASEC, ('http', None, 'g', None, None), True) == ('http', None, 'g', None, None)
    # OURS: scheme comparison is literal, so a differently-cased scheme is not the same scheme
    assert m.resolve_reference(BASE, 'HTTP:g', False) == 'HTTP:g'
    assert m.resolve_reason(BASE, 'http:g ', False) == 'reference.char'


def test_appendix_b_parse_example_and_falsy_witnesses():
    assert m.split_reference('http://www.ics.uci.edu/pub/ietf/uri/#Related') == ('http', 'www.ics.uci.edu', '/pub/ietf/uri/', None, 'Related')
    assert m.split_reference('//') == (None, '', '', None, None)
    assert m.split_reference('a://') == ('a', '', '', None, None)
    assert m.split_reference('?') == (None, None, '', '', None)
    assert m.split_reference('#') == (None, None, '', None, '')
    assert m.split_reference('') == (None, None, '', None, None)
    assert m.recompose((None, None, '', None, None)) == ''
    assert m.recompose(('a', '', '', None, None)) == 'a://'
    assert m.recompose((None, None, '', '', None)) == '?'
    assert m.recompose((None, None, '', None, '')) == '#'
    assert m.resolve_reference(BASE, '?', True) == 'http://a/b/c/d;p?'
    assert m.resolve_reference(BASE, '#', True) == 'http://a/b/c/d;p?q#'
    assert m.recompose(COMPS) == 'http://a/b/c/g?y#s'
    assert m.recompose((None, None, 'g', None, None)) == 'g'
    assert m.split_reference('a://[::1]/b') == ('a', '[::1]', '/b', None, None)
    assert m.resolve_reference(BASE, '//g#s', True) == 'http://g#s'
    assert m.resolve_reference(BASE, '//g?y', True) == 'http://g?y'
    assert m.resolve_reference(BASE, '//g?y#s', True) == 'http://g?y#s'
    assert m.resolve_reference('http://a', 'g', True) == 'http://a/g'
    assert m.resolve_reference('http://a', '', True) == 'http://a'
    assert m.resolve_components(('http', 'a', '', None, None), (None, None, 'g', None, None), True) == ('http', 'a', '/g', None, None)
    assert m.resolve_reference('http://a', 'g/', True) == 'http://a/g/'
    assert m.resolve_reference('a:', 'g', True) == 'a:g'
    assert m.resolve_reference('a:', 'g', False) == 'a:g'
    assert m.resolve_components(('a', None, '', None, None), (None, None, 'g', None, None), True) == ('a', None, 'g', None, None)
    assert m.resolve_reference('a:/b', 'g', True) == 'a:/g'
    try:
        m.merge_paths(1, 5, 'g')
        raise SystemExit('merge both-bad not refused')
    except ValueError as e:
        assert str(e) == PFX + 'merge_paths:bad_type:base_has_authority', str(e)
    try:
        m.merge_paths(1, True, 5)
        raise SystemExit('merge both-bad 2 not refused')
    except ValueError as e:
        assert str(e) == PFX + 'merge_paths:bad_type:base_has_authority', str(e)
    assert m.reference_reason('a:/%41?%41#%41') == 'ok'
    assert m.reference_reason('g:h') == 'ok' and m.absolute_reason('g:h') == 'ok'
    assert m.absolute_reason('//g') == 'no_scheme' and m.absolute_reason('g:h#f') == 'fragment'
    assert m.absolute_reason('a://b/c?') == 'ok' and m.absolute_reason('a:b?') == 'ok'


# ---- remove_dot_segments buffer-trace vectors and exhaustive segment fuzz ---------------------------------------------
RDS = [('', ''), ('.', ''), ('..', ''), ('./', ''), ('../', ''), ('a', 'a'), ('a/b', 'a/b'), ('/a', '/a'),
       ('/a/b/c/./../../g', '/a/g'), ('mid/content=5/../6', 'mid/6'), ('/a/./b', '/a/b'), ('/a/../b', '/b'),
       ('/./', '/'), ('/../', '/'), ('/..', '/'), ('/.', '/'), ('/../..', '/'), ('/../../x', '/x'),
       ('../../x', 'x'), ('a/.', 'a/'), ('a/..', '/'), ('a/../..', '/'), ('/./x', '/x'), ('/x/..', '/'),
       ('x/..', '/'), ('x/y/../..', '/'), ('/x/y/../..', '/'), ('//a', '//a'), ('/a//b', '/a//b'), ('a//../b', 'a/b'),
       ('/a/b/../../..', '/'), ('a/./b/./c', 'a/b/c'), ('a/../b/../c', '/c'), ('/a/b/c/../../../../d', '/d'),
       ('g.', 'g.'), ('.g', '.g'), ('g..', 'g..'), ('..g', '..g'), ('g/.', 'g/'), ('g/..', '/'), ('%41/./%42', '%41/%42'),
       ('/././x', '/x'), ('/.././x', '/x'), ('/a/../../b', '/b'), ('a/../../b', '/b')]


@pytest.mark.parametrize('path,want', RDS)
def test_remove_dot_segments_buffer_traces(path, want):
    assert m.remove_dot_segments(path) == want
    assert o_rds(path) == want
    if path.startswith('/') and '[' not in path:
        assert o_rds_stack(path) == want


def test_remove_dot_segments_exhaustive_short_paths_match_two_independent_oracles():
    import itertools
    segs = ['.', '..', 'a', 'b', '']
    paths = []
    for depth in range(5):
        for combo in itertools.product(segs, repeat=depth):
            paths.append('/' + '/'.join(combo))
    assert len(paths) == 781
    for p in paths:
        assert m.remove_dot_segments(p) == o_rds(p), p
        assert o_rds_stack(p) == o_rds(p), p
    for p in ('a', '..', '.', 'a/b', 'a/./b', '../a', './a', 'a/..', 'a/.', 'a/b/../..', '..g', '.g', 'g..', 'g.', 'a/../../b', 'a//../b'):
        assert m.remove_dot_segments(p) == o_rds(p), p


# ---- merge_paths and the merge/drop loops, while-to-if pins -----------------------------------------------------------
MERGE_CASES = [(True, '', 'g', '/g'), (True, '', '', '/'), (False, '', 'g', 'g'), (True, '/b/c/d', 'g', '/b/c/g'),
               (True, '/b/c/d', '', '/b/c/'), (False, '/b/c/d', '../g', '/b/c/../g'), (True, '/b/', 'g', '/b/g'),
               (False, 'abc', 'g', 'g'), (False, 'abc', '', ''), (True, '/', 'g', '/g'), (True, '/a', '/x', '//x'),
               (False, 'a/b/c', 'd/e', 'a/b/d/e'), (True, '/a/b', '/..', '/a//..')]


@pytest.mark.parametrize('ha,bp,rp,want', MERGE_CASES)
def test_merge_paths_table(ha, bp, rp, want):
    assert m.merge_paths(ha, bp, rp) == want
    assert o_merge(ha, bp, rp) == want


def test_merge_output_cap_at_cap_and_cap_plus_one():
    assert m.merge_paths(True, '', 'r' * 4095) == '/' + 'r' * 4095
    assert run('merge_paths', True, '', 'r' * 4096) == E('merge_paths', 'bad_value:output_length')
    assert m.merge_paths(False, 'p' * 2000 + '/', 'r' * 2095) == 'p' * 2000 + '/' + 'r' * 2095
    assert run('merge_paths', False, 'p' * 2000 + '/', 'r' * 2096) == E('merge_paths', 'bad_value:output_length')


# ---- parse check order: leftmost defect wins; scheme before brackets; path before query before fragment ------------------
ORDER_CASES = [('\x01%zz', 'char'), ('%zz\x01', 'pct'), ('\x01%', 'char'), ('%\x01', 'pct'), ('ab%', 'pct'), ('a%z', 'pct'),
               ('%41\x01', 'char'), ('%41%zz', 'pct'),
               ('%41', 'ok'), ('%zz', 'pct'), ('1a:/[', 'scheme'), ('a:/[', 'path_char'), ('1:/[?]', 'scheme'),
               ('/[?[', 'path_char'), ('/?[', 'query_char'), ('?[#[', 'query_char'), ('/?x#[', 'fragment_char'),
               ('/#x[y', 'fragment_char'), ('/x#y#z', 'fragment_char'), (':x', 'scheme'), ('1:x', 'scheme'),
               ('a b:/x', 'char'), ('a:/x y', 'char'), ('+a:/x', 'scheme'), ('.a:/x', 'scheme'), ('-a:/x', 'scheme'),
               ('A+/-.9:/x', 'ok'), ('a:/x/[', 'path_char'), ('a:/x?[', 'query_char'), ('a:/x#[', 'fragment_char'),
               ('a://[/x', 'ok'), ('a://x/y[', 'path_char'), ('a://x?y]', 'query_char'), ('a://x#y]', 'fragment_char')]


@pytest.mark.parametrize('text,want', ORDER_CASES)
def test_parse_check_order_and_reason_names(text, want):
    assert m.reference_reason(text) == want
    assert o_parse(text)[0] == want
    if want == 'ok':
        assert m.split_reference(text) == o_parse(text)[1]
    else:
        assert run('split_reference', text) == E('split_reference', 'bad_value:text.' + want)


# ---- resolve check order: base before reference before target; no_scheme before fragment --------------------------------
def test_resolve_check_order_base_reference_target_and_both_bad():
    rr = m.resolve_reason
    assert rr('\x01', '\x01', True) == 'base.char'
    assert rr('%zz', '\x01', True) == 'base.pct'
    assert rr('a:/x', '\x01', True) == 'reference.char'
    assert rr('a:/x', '%zz', True) == 'reference.pct'
    assert rr('x', '\x01', True) == 'base.no_scheme'
    assert rr('x#f', '\x01', True) == 'base.no_scheme'
    assert rr('a:/x#f', '\x01', True) == 'base.fragment'
    assert rr('a:#f', 'g', True) == 'base.fragment'
    assert rr('a:/x', '1:/[', True) == 'reference.scheme'
    assert rr('1:/x', 'g', True) == 'base.scheme'
    assert rr('a:/x', '/[', True) == 'reference.path_char'
    assert rr('a:/x', '/?[', True) == 'reference.query_char'
    assert rr('a:/x', '/#[', True) == 'reference.fragment_char'
    assert rr('a:/b', '/.//x', True) == 'target.ambiguous'
    assert rr('a:/b', '/.//x', False) == 'target.ambiguous'
    big = '/' + 'p' * 4000 + '/'
    assert rr('a://b' + big, 'r' * 100, True) == 'target.output_length'
    assert run('resolve_reference', '\x01', 'g', True) == E('resolve_reference', 'bad_value:base.char')
    assert run('resolve_reference', 'a:/x', '\x01', True) == E('resolve_reference', 'bad_value:reference.char')
    assert run('resolve_reference', 'a:/b', '/.//x', True) == E('resolve_reference', 'bad_value:target.ambiguous')
    for br in ('base.char', 'base.no_scheme', 'base.fragment', 'reference.char', 'target.ambiguous'):
        assert rr(*( {'base.char': ('\x01', 'g', True), 'base.no_scheme': ('x', 'g', True), 'base.fragment': ('a:/x#f', 'g', True),
                       'reference.char': ('a:/x', '\x01', True), 'target.ambiguous': ('a:/b', '/.//x', True)}[br] )) == br


def test_resolve_components_check_order_and_target_prefixes():
    rc = m.resolve_components
    assert run('resolve_components', ('1', None, 'x', None, None), REFC, True) == E('resolve_components', 'bad_value:base.scheme')
    assert run('resolve_components', (None, None, 'x', None, None), REFC, True) == E('resolve_components', 'bad_value:base.no_scheme')
    assert run('resolve_components', ('a', None, 'x', None, 'f'), REFC, True) == E('resolve_components', 'bad_value:base.fragment')
    assert run('resolve_components', BASEC, ('1', None, 'x', None, None), True) == E('resolve_components', 'bad_value:reference.scheme')
    assert run('resolve_components', ('a', None, '/b', None, None), (None, None, '/.//x', None, None), True) == E('resolve_components', 'bad_value:target.ambiguous')
    assert run('resolve_components', ('a', 'b', '/' + 'p' * 4000 + '/', None, None), (None, None, 'r' * 100, None, None), True) == E('resolve_components', 'bad_value:target.output_length')
    # argument order pin: base shape is checked before strict
    assert run('resolve_components', ('a',), ('a',), 1) == E('resolve_components', 'bad_value:base.length')
    assert run('resolve_components', BASEC, ('a',), 1) == E('resolve_components', 'bad_value:reference.length')
    assert run('resolve_components', BASEC, REFC, 1) == E('resolve_components', 'bad_type:strict')
    assert rc(BASEC, (None, None, '../g', None, None), True) == ('http', 'a', '/b/g', None, None)
    assert rc(BASEC, (None, None, '../g', None, 'z'), True) == ('http', 'a', '/b/g', None, 'z')


# ---- recompose round-trip pins at output boundary and ambiguity ------------------------------------------------------------
def test_recompose_output_length_at_minus1_cap_and_cap_plus_one():
    for n, ok in ((4091, True), (4092, True), (4093, False)):
        r = run('recompose', ('a', 'x' * n, '', None, None))
        if ok:
            assert r == ('ok', 'a://' + 'x' * n) and len(r[1]) == 4 + n
        else:
            assert r == E('recompose', 'bad_value:components.output_length')
    assert m.recompose((None, None, 'p' * 4096, None, None)) == 'p' * 4096
    assert m.recompose(('a', None, 'p' * 4090, 'q', 'f')) == 'a:' + 'p' * 4090 + '?q#f'


def test_recompose_ambiguous_and_reparse_reasons():
    assert run('recompose', ('a', None, '//x', None, None)) == E('recompose', 'bad_value:components.ambiguous')
    assert run('recompose', (None, None, '//x', None, None)) == E('recompose', 'bad_value:components.ambiguous')
    assert run('recompose', ('1', None, 'x', None, None)) == E('recompose', 'bad_value:components.scheme')
    assert run('recompose', (None, None, '/[', None, None)) == E('recompose', 'bad_value:components.path_char')
    assert run('recompose', (None, None, '', '?[', None)) == E('recompose', 'bad_value:components.query_char')
    assert run('recompose', (None, None, '', None, '#[')) == E('recompose', 'bad_value:components.fragment_char')
    assert run('recompose', (None, None, '', None, 'a#b')) == E('recompose', 'bad_value:components.fragment_char')
    assert run('recompose', (None, None, '%zz', None, None)) == E('recompose', 'bad_value:components.pct')
    assert run('recompose', (None, None, 'x y', None, None)) == E('recompose', 'bad_value:components.char')
    assert m.recompose(('g', None, 'h', None, None)) == 'g:h'
    # authority with brackets round-trips; a path that would reparse as authority does not
    assert m.recompose(('a', '[::1]', '/b', None, None)) == 'a://[::1]/b'


# ---- mixed-junk fuzz against the independent oracle ----------------------------------------------------------------------
FZ_SEED_CHARS = list('abAB09:/?#[]%.-~!$&\'()*+,;=@gG') + ['%41', '%4', '%zz', '\x01', ' ', '3', 'K', 'Á', 'https://x/y?z#f', '..', './', '/../', '//', ':']


def _fz_string(rng):
    n = rng.randint(0, 24)
    s = ''
    for _ in range(n):
        s += rng.choice(FZ_SEED_CHARS)
    return s[:rng.randint(0, max(1, len(s)))] if rng.random() < 0.3 else s


def test_fuzz_reference_reason_absolute_reason_split_against_oracle_1200_iterations():
    rng = random.Random(1131)
    seen = set()
    for _ in range(1200):
        t = _fz_string(rng)
        if len(t) > m.TEXT_CAP:
            continue
        want = o_parse(t)
        assert m.reference_reason(t) == want[0], repr(t)
        seen.add(want[0])
        if want[0] == 'ok':
            assert m.split_reference(t) == want[1]
            parts = want[1]
            abs_want = 'no_scheme' if parts[0] is None else ('fragment' if parts[4] is not None else 'ok')
            assert m.absolute_reason(t) == abs_want, repr(t)
            assert m.recompose(parts) == t, repr(t)
        else:
            assert run('split_reference', t) == E('split_reference', 'bad_value:text.' + want[0])
            assert m.absolute_reason(t) == want[0], repr(t)
    assert {'ok', 'char', 'pct', 'scheme'} <= seen


FZ_BASES = [BASE, 'a:/x', 'a://b/c', 'x', 'a:#f', '\x01', '1:/x', 'a:/b/..', 'g:h', 'a://b/', 'a:/', 'a:b?y']


def test_fuzz_resolve_reference_and_reason_against_oracle_1200_iterations():
    rng = random.Random(3986)
    seen = set()
    for _ in range(1200):
        b = rng.choice(FZ_BASES)
        r = _fz_string(rng)
        strict = rng.random() < 0.5
        if len(r) > m.TEXT_CAP:
            continue
        want = o_resolve(b, r, strict)
        assert m.resolve_reason(b, r, strict) == want[0], (repr(b), repr(r), strict)
        seen.add(want[0].split('.')[0])
        if want[0] == 'ok':
            assert m.resolve_reference(b, r, strict) == want[1]
        else:
            assert run('resolve_reference', b, r, strict) == E('resolve_reference', 'bad_value:' + want[0])
    assert {'base', 'reference', 'ok'} <= seen


def test_fuzz_remove_dot_segments_against_oracle_1200_iterations():
    rng = random.Random(52)
    for _ in range(1200):
        n = rng.randint(0, 20)
        p = ''.join(rng.choice(list('/.ab%41z') + ['..', './', '/../', '/./']) for _ in range(n))
        if len(p) > m.TEXT_CAP:
            continue
        if o_pass(p, _PATHSET) != 'ok':
            continue
        assert m.remove_dot_segments(p) == o_rds(p), repr(p)


def test_private_helpers_return_exact_bool_singletons():
    assert m._scheme_ok('a') is True and m._scheme_ok('A9+-.z') is True and m._scheme_ok('http') is True
    assert m._scheme_ok('') is False and m._scheme_ok('1a') is False and m._scheme_ok('+a') is False
    assert m._scheme_ok('a b') is False and m._scheme_ok('a_b') is False and m._scheme_ok('a/b') is False and m._scheme_ok('a%41') is False
    assert m._has_any('ab[', '[]') is True and m._has_any(']ab', '[]') is True and m._has_any('ab', '[]') is False and m._has_any('', '[]') is False
    assert m._pct_run('ab', m.PATHC) == 'ok' and m._pct_run('%41', m.PATHC) == 'ok'
    assert m._drop_last('') == '' and m._drop_last('/') == '' and m._drop_last('/a') == '' and m._drop_last('/a/') == '/a' and m._drop_last('a/b') == 'a'
    assert m._merge(False, 'abc', 'g') == 'g' and m._merge(True, '', 'g') == '/g' and m._merge(True, '/a/b', 'g') == '/a/g'
    assert m._dots('') == '' and m._dots('/a/./b') == '/a/b'
    assert m._join((None, None, 'g', None, None)) == 'g' and m._join(COMPS) == 'http://a/b/c/g?y#s'


# ---- registry guard, import log, namespace ----------------------------------------------------------------------
def test_registry_absent_uses_local_fallback(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh()
    assert mod.make_fail.__module__ == mod.__name__
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert run('path_reason', 1, mod=mod) == ('err', 'P235:path_reason:bad_type:text')


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
NAMESPACE = (['find_spec'] + ['SCOPE', 'NOT_CLAIMED', 'CLAIMS', 'ADJACENT', 'TEXT_CAP', 'DIGITS', 'UPPER', 'LOWER', 'HEXDIG', 'UNRESERVED',
                              'SUBDELIM', 'PATHC', 'URIC', 'SCHEMEC', '_REG', 'make_fail'] + list(PRIVATE) + list(NAMES))
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
for _fn, _arg in (('path_reason', 'text'), ('reference_reason', 'text'), ('absolute_reason', 'text'),
                  ('split_reference', 'text')):
    CORPUS.append((_fn, ('a' * 4097,), 'bad_value:' + _arg + '.length'))
CORPUS += [('remove_dot_segments', ('a' * 4097,), 'bad_value:path.length'),
           ('remove_dot_segments', ('\x01',), 'bad_value:path.char'), ('remove_dot_segments', ('%zz',), 'bad_value:path.pct'),
           ('merge_paths', (True, 'a' * 4097, 'g'), 'bad_value:base_path.length'),
           ('merge_paths', (True, 'g', 'a' * 4097), 'bad_value:ref_path.length'),
           ('merge_paths', (True, '\x01', 'g'), 'bad_value:base_path.char'), ('merge_paths', (True, '%zz', 'g'), 'bad_value:base_path.pct'),
           ('merge_paths', (True, 'g', '\x01'), 'bad_value:ref_path.char'), ('merge_paths', (True, 'g', '%zz'), 'bad_value:ref_path.pct'),
           ('merge_paths', (True, '', 'r' * 4096), 'bad_value:output_length')]
for _r, _t in (('char', '\x01'), ('pct', '%zz'), ('scheme', '1:x'), ('path_char', '/['), ('query_char', '?['), ('fragment_char', '#[')):
    CORPUS.append(('split_reference', (_t,), 'bad_value:text.' + _r))
SLOT_BAD = [(5, None, '', None, None), (None, 5, '', None, None), (None, None, 5, None, None), (None, None, '', 5, None), (None, None, '', None, 5)]
SLOT_LONG = [('a' * 4097, None, '', None, None), (None, 'a' * 4097, '', None, None), (None, None, 'p' * 4097, None, None),
             (None, None, '', 'q' * 4097, None), (None, None, '', None, 'f' * 4097)]
SLOT_NAMES = ('scheme', 'authority', 'path', 'query', 'fragment')
for _i, _c in enumerate(SLOT_BAD):
    CORPUS.append(('recompose', (_c,), 'bad_type:components.' + SLOT_NAMES[_i]))
for _i, _c in enumerate(SLOT_LONG):
    CORPUS.append(('recompose', (_c,), 'bad_value:components.' + SLOT_NAMES[_i] + '.length'))
CORPUS += [('recompose', (('a', 'b'),), 'bad_value:components.length'), ('recompose', (('a',) * 6,), 'bad_value:components.length')]
for _r, _c in (('scheme', ('1', None, 'x', None, None)), ('path_char', (None, None, '/[', None, None)),
               ('query_char', (None, None, '', '?[', None)), ('fragment_char', (None, None, '', None, '#[')),
               ('pct', (None, None, '%zz', None, None)), ('char', (None, None, 'x y', None, None))):
    CORPUS.append(('recompose', (_c,), 'bad_value:components.' + _r))
CORPUS += [('recompose', (('a', 'x' * 4093, '', None, None),), 'bad_value:components.output_length'),
           ('recompose', (('a', None, '//x', None, None),), 'bad_value:components.ambiguous'),
           ('resolve_components', (('a', 'b'), REFC, True), 'bad_value:base.length'),
           ('resolve_components', (BASEC, ('a', 'b'), True), 'bad_value:reference.length'),
           ('resolve_components', (('1', None, 'x', None, None), REFC, True), 'bad_value:base.scheme'),
           ('resolve_components', ((None, None, 'x', None, None), REFC, True), 'bad_value:base.no_scheme'),
           ('resolve_components', (('a', None, 'x', None, 'f'), REFC, True), 'bad_value:base.fragment'),
           ('resolve_components', (('a', 'x' * 4093, '', None, None), REFC, True), 'bad_value:base.output_length'),
           ('resolve_components', (BASEC, ('1', None, 'x', None, None), True), 'bad_value:reference.scheme'),
           ('resolve_components', (BASEC, (None, None, 'p' * 4090, 'q' * 3, 'f' * 3), True), 'bad_value:reference.output_length'),
           ('resolve_components', (('a', None, '/b', None, None), (None, None, '/.//x', None, None), True), 'bad_value:target.ambiguous'),
           ('resolve_components', (('a', 'b', '/' + 'p' * 4000 + '/', None, None), (None, None, 'r' * 100, None, None), True),
            'bad_value:target.output_length')]
REF_REASONS = (('char', '\x01'), ('pct', '%zz'), ('scheme', '1:x'), ('path_char', '/['), ('query_char', '?['), ('fragment_char', '#['))
for _fn in ('resolve_reference', 'resolve_reason'):
    CORPUS.append((_fn, ('a' * 4097, 'g', True), 'bad_value:base.length'))
    CORPUS.append((_fn, ('a:/x', 'g' * 4097, True), 'bad_value:reference.length'))
for _r, _b in (('char', '\x01'), ('pct', '%zz'), ('scheme', '1:x'), ('no_scheme', 'x'), ('fragment', 'a:/x#f')):
    CORPUS.append(('resolve_reference', (_b, 'g', True), 'bad_value:base.' + _r))
for _r, _t in REF_REASONS:
    CORPUS.append(('resolve_reference', ('a:/x', _t, True), 'bad_value:reference.' + _r))
CORPUS.append(('resolve_reference', ('a:/b', '/.//x', True), 'bad_value:target.ambiguous'))
CORPUS.append(('resolve_reference', ('a://b' + '/' + 'p' * 4000 + '/', 'r' * 100, True), 'bad_value:target.output_length'))
SUCCESS = [('path_reason', ('a/b',), 'ok'), ('path_reason', ('\x01',), 'char'), ('path_reason', ('%zz',), 'pct'), ('path_reason', ('a?b',), 'char'),
           ('reference_reason', ('g?y#s',), 'ok')] + [('reference_reason', (_t,), _r) for _r, _t in
                                                      (('char', '\x01'), ('pct', '%zz'), ('scheme', '1:x'), ('path_char', '/['),
                                                       ('query_char', '?['), ('fragment_char', '#['))] + [
           ('absolute_reason', ('a:b',), 'ok'), ('absolute_reason', ('x',), 'no_scheme'), ('absolute_reason', ('a:b#f',), 'fragment'),
           ('absolute_reason', ('\x01',), 'char'),
           ('remove_dot_segments', ('/a/b/c/./../../g',), '/a/g'), ('remove_dot_segments', ('',), ''),
           ('merge_paths', (True, '', 'g'), '/g'), ('merge_paths', (False, 'abc', 'g'), 'g'),
           ('split_reference', ('g?y#s',), (None, None, 'g', 'y', 's')),
           ('recompose', (COMPS,), 'http://a/b/c/g?y#s'), ('recompose', ((None, None, 'g', None, None),), 'g'),
           ('resolve_components', (BASEC, REFC, True), COMPS),
           ('resolve_reference', (BASE, 'g', True), 'http://a/b/c/g'),
           ('resolve_reason', (BASE, 'g', True), 'ok'), ('resolve_reason', ('\x01', 'g', True), 'base.char'),
           ('resolve_reason', ('x', 'g', True), 'base.no_scheme'), ('resolve_reason', ('a:/x#f', 'g', True), 'base.fragment'),
           ('resolve_reason', ('a:/x', '\x01', True), 'reference.char'), ('resolve_reason', ('a:/b', '/.//x', True), 'target.ambiguous')]


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
    for r in ('char', 'pct', 'scheme', 'path_char', 'query_char', 'fragment_char'):
        assert ('split_reference', 'bad_value:text.' + r) in codes
        assert any(f == 'reference_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'char', 'pct'):
        assert any(f == 'path_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'no_scheme', 'fragment', 'char'):
        assert any(f == 'absolute_reason' and w == r for f, a, w in SUCCESS)
    for pre in ('base', 'reference', 'target'):
        assert any(f == 'resolve_reason' and w.startswith(pre + '.') for f, a, w in SUCCESS)


def test_fallback_failer_world_has_no_imports_one_success_and_every_refusal(mp):
    real = builtins.__import__
    seen = []
    name = 'b1131_fallback_world'

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
    mod = fresh('b1131_site_world')
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
    mod = fresh('b1131_doc_world')
    assert mod.make_fail.__doc__ is None
    assert mod.make_fail('x').__doc__ is None
    assert mod.make_fail.__name__ == 'make_fail' and mod.make_fail('x').__name__ == 'fail'


def test_find_spec_is_consulted_exactly_once_in_the_absent_world_simulation(mp):
    spied = []
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda n: spied.append(n) or None)
    mod = fresh('b1131_spec_world')
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
            "import app.modules.instinct_doc.p235_concepts_batch1131_refresolve as m\n"
            "print(m.resolve_reference(%r, 'g', True), m.reference_reason('1:x'), m.remove_dot_segments('/a/./b'), "
            "m.merge_paths(True, '', 'g'), m.split_reference('g?y#s'))\n") % (
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(m.__file__)))), BASE)
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "http://a/b/c/g scheme /a/b /g (None, None, 'g', 'y', 's')"
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25, env={'PYTHONHASHSEED': '7'})
    assert out.stdout.strip() == "http://a/b/c/g scheme /a/b /g (None, None, 'g', 'y', 's')"
