r"""p235 concepts batch 1131 (rev 0): RFC 3986 section 5 reference resolution. Pure functions over caller-supplied text. No retrieval, no network, no clock. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete, does not validate hosts, does not normalize and does not check any network state. ADJACENT is the empty tuple.

LIVE-READ SOURCES (read live, quoted verbatim below and mechanically matched against the whitespace-collapsed RFC text with the page headers and footers removed):
- RFC 3986, Uniform Resource Identifier (URI): Generic Syntax, STD 66, January 2005. rfc3986.txt is 141811 bytes, sha256 3102dae4b68cebe40337730312fcb612297b8928547267e8b3d1ee6002b2d683.
- The rfc-editor info page for RFC 3986 lists: Updates RFC 1738; Updated by RFC 8820 and RFC 7320 (both titled URI Design and Ownership); Obsoletes RFC 1808, RFC 2732 and RFC 2396. It shows no Obsoleted by. This module therefore targets a current Internet Standard that later documents updated, and it does not apply those updates.
- errata.json (sha256 2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) lists 18 errata for RFC 3986. The ones that touch the sections used here: 4547 (Held for Document Update, Technical, section 5.4.2: proposes "http://a/../g" and "http://a/../../g" for the two examples with too many ".." segments); 4789 (Held for Document Update, Technical, section 5.2.3: proposes a merge change when the base path ends with "/.."); 2933 (Held for Document Update, Editorial, section 5.2.2: argues merge should take the base and not only its path); 7590 (Verified, Editorial, section 5.2.4: a stray hyperlink in the second example); 5428 (Held for Document Update, Technical, section 4.2: relative-part and the reference "/"); 8442 (Rejected, Technical, section 4.1); 9147 (Reported, Technical, section 2.3). OURS: no erratum is applied. The RFC text and its printed examples decide. Erratum 5428 does not arise because the reference "/" is parsed as an empty authority-less path-absolute and accepted.

SOURCED (the RFC text):
- Pre-parse (5.2.1): "A component is undefined if its associated delimiter does not appear in the URI reference; the path component is never undefined, though it may be empty."
- Base URI (5.1): "A base URI must conform to the <absolute-URI> syntax rule (Section 4.3). If the base URI is obtained from a URI reference, then that reference must be converted to absolute form and stripped of any fragment component prior to its use as a base URI."
- Transform (5.2.2): "(R.scheme, R.authority, R.path, R.query, R.fragment) = parse(R);" "-- A non-strict parser may ignore a scheme in the reference -- if it is identical to the base URI's scheme." "if ((not strict) and (R.scheme == Base.scheme)) then undefine(R.scheme); endif;" "T.path = remove_dot_segments(R.path);" "T.path = merge(Base.path, R.path);" "T.fragment = R.fragment;"
- Merge (5.2.3): "If the base URI has a defined authority component and an empty path, then return a string consisting of "/" concatenated with the reference's path; otherwise," "return a string consisting of the reference's path component appended to all but the last segment of the base URI's path (i.e., excluding any characters after the right-most "/" in the base URI path, or excluding the entire base URI path if it does not contain any "/" characters)."
- Remove dot segments (5.2.4): "A. If the input buffer begins with a prefix of "../" or "./", then remove that prefix from the input buffer; otherwise," "B. if the input buffer begins with a prefix of "/./" or "/.", where "." is a complete path segment, then replace that prefix with "/" in the input buffer; otherwise," "C. if the input buffer begins with a prefix of "/../" or "/..", where ".." is a complete path segment, then replace that prefix with "/" in the input buffer and remove the last segment and its preceding "/" (if any) from the output buffer; otherwise," "D. if the input buffer consists only of "." or "..", then remove that from the input buffer; otherwise," "E. move the first path segment in the input buffer to the end of the output buffer, including the initial "/" character (if any) and any subsequent characters up to, but not including, the next "/" character or the end of the input buffer."
- Recomposition (5.3): "Note that we are careful to preserve the distinction between a component that is undefined, meaning that its separator was not present in the reference, and a component that is empty, meaning that the separator was present and was immediately followed by the next component separator or the end of the reference."
- Examples (5.4) use the base "http://a/b/c/d;p?q" and, for the abnormal case: "Parsers must be careful in handling cases where there are more ".." segments in a relative-path reference than there are hierarchical levels in the base URI's path. Note that the ".." syntax cannot be used to change the authority component of a URI." ""../../../g" = "http://a/g""
- Grammar (Appendix A): "absolute-URI = scheme ":" hier-part [ "?" query ]" "relative-part = "//" authority path-abempty / path-absolute / path-noscheme / path-empty" "scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )" "pchar = unreserved / pct-encoded / sub-delims / ":" / "@"" "query = *( pchar / "/" / "?" )" "pct-encoded = "%" HEXDIG HEXDIG" "segment-nz-nc = 1*( unreserved / pct-encoded / sub-delims / "@" ) ; non-zero-length segment without any colon ":""
- Appendix B splits a reference with "^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?"

OURS (conventions this module adds, each pinned by tests):
1. Authority is opaque. It is the text after "//" up to the next "/" ("?" and "#" are already split off). Userinfo, host, port and IP literals are not validated: any URI character is accepted there, including "[", "]", ":" and "@". CLAIMS host_validated is False.
2. No case folding, percent decoding or normalization of any component. The scheme comparison in non-strict mode is literal equality, as the pseudocode writes it.
3. Characters. The URI character set is the ASCII letters, digits, the unreserved marks "-._~", the sub-delims "!$&'()*+,;=" and ":@/?#[]", plus "%" only as the start of a percent triplet with two ASCII hex digits (either case). Anything else, including every non-ASCII character, is refused. Membership is tested with explicit ASCII strings, never with Unicode-aware str methods.
4. "[" and "]" are valid only in the authority. Path, query and fragment refuse them (they are gen-delims, not pchar). The fragment also refuses a second "#".
5. A reference with a ":" before the first "/", "?" or "#" has a scheme. If that text is not a scheme (ALPHA then ALPHA, DIGIT, "+", "-", "."), the reference is refused with scheme. This is the path-noscheme rule: the first segment of a relative path has no colon. The empty string is a valid reference (relative-part is path-empty).
6. An absolute base needs a scheme and no fragment (5.1). absolute_reason gives no_scheme, then fragment, after the reference checks pass.
7. remove_dot_segments and merge_paths take path text only (path characters: pchar and "/"). They do not check path forms: a leading "//" or a colon in the first segment is accepted there.
8. The target must survive recomposition. The target components are joined with 5.3, the result is parsed again, and the parse must equal the components. Otherwise target.ambiguous is reported. Example: base "a:/b/." and reference "..//c" merge to the path "//c" with no authority, which would print as "a://c". recompose uses the same rule under the name components.
9. Output length is capped at TEXT_CAP like input length.

CAPS AND CLOSURE: TEXT_CAP is 4096 characters for every text and every component, and for every output. Lengths are checked before any content is read. The output of remove_dot_segments is never longer than its input. recompose(split_reference(t)) == t for every t that split_reference accepts, and split_reference(recompose(c)) == c for every c that recompose accepts.

FUNCTIONS, in this order: path_reason, reference_reason, absolute_reason, remove_dot_segments, merge_paths, split_reference, recompose, resolve_components, resolve_reference, resolve_reason. Errors are ValueError with the text P235:<function>:<code>. A code is bad_type:<name> (exact built-in type by identity, subclasses and bool-for-int refused), bad_value:<name>.length, or bad_value:<name>.<reason>.

REASONS, in check order (the first failure decides, so a text with several faults reports the first):
- path_reason: a single left-to-right pass over the text. At each position a "%" must be followed by two ASCII hex digits, otherwise pct; any other character outside the path set is char. So the first offending position decides between char and pct. ok otherwise.
- reference_reason (and split_reference as bad_value:text.<reason>): the same single pass over the URI character set (char or pct), then scheme, then path_char, then query_char, then fragment_char. The components are cut in this order: the first "#" starts the fragment, the first "?" before it starts the query, a ":" before any "/" ends the scheme, "//" starts the authority. ok otherwise.
- absolute_reason: the reference_reason result, then no_scheme, then fragment.
- remove_dot_segments: type, length, then bad_value:path.<char or pct>. merge_paths: base_has_authority must be a bool (bad_type:base_has_authority), then base_path type and length, then ref_path type and length, then base_path.<char or pct>, then ref_path.<char or pct>, then bad_value:output_length.
- recompose and the two component arguments of resolve_components: a tuple (bad_type), exactly five items (bad_value:<name>.length), then each item left to right as scheme, authority, path, query, fragment: type (None is allowed for all but the path) then length. Content is checked after the types: the joined text must fit (output_length), parse (the reference reasons) and parse back to the same components (ambiguous).
- resolve_components: base, reference, strict (bad_type:strict), then base content, then base.no_scheme, then base.fragment, then reference content, then the target (target.output_length, target.ambiguous). Content codes are prefixed with the argument name.
- resolve_reference and resolve_reason: base, reference, strict (types and lengths in that order), then the base reasons (base.<reference reason>, base.no_scheme, base.fragment), then reference.<reason>, then target.<reason>. resolve_reference raises bad_value:<reason>; resolve_reason returns the reason, or ok.

OUTPUT ORDER: split_reference and resolve_components return a 5-tuple (scheme, authority, path, query, fragment). A component is None when undefined and a string, possibly empty, when defined. The path is always a string. resolve_reference returns the recomposed target text.
"""
from importlib.util import find_spec

SCOPE = 'RFC 3986 section 5 reference resolution over caller-supplied text: split, merge, remove_dot_segments, recompose and resolve'
NOT_CLAIMED = ('standard', 'authority', 'certification', 'currency', 'completeness', 'host-validation', 'normalization', 'network-use')
CLAIMS = {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False,
          'host_validated': False, 'normalized': False, 'network_checked': False}
ADJACENT = ()
TEXT_CAP = 4096
DIGITS = '0123456789'
UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
LOWER = 'abcdefghijklmnopqrstuvwxyz'
HEXDIG = DIGITS + 'ABCDEF' + 'abcdef'
UNRESERVED = UPPER + LOWER + DIGITS + '-._~'
SUBDELIM = "!$&'()*+,;="
PATHC = UNRESERVED + SUBDELIM + ':@/'
URIC = PATHC + '?#[]'
SCHEMEC = UPPER + LOWER + DIGITS + '+-.'

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


def _pct_run(text, ok):
    skip = 0
    for i in range(len(text)):
        if skip > 0:
            skip -= 1
            continue
        ch = text[i]
        if ch == '%':
            if i + 2 >= len(text):
                return 'pct'
            if text[i + 1] not in HEXDIG or text[i + 2] not in HEXDIG:
                return 'pct'
            skip = 2
        elif ch not in ok:
            return 'char'
    return 'ok'


def _scheme_ok(text):
    if text == '' or text[0] not in UPPER + LOWER:
        return False
    for ch in text:
        if ch not in SCHEMEC:
            return False
    return True


def _has_any(text, chars):
    for ch in text:
        if ch in chars:
            return True
    return False


def _parse(text):
    reason = _pct_run(text, URIC)
    if reason != 'ok':
        return (reason, None)
    rest = text
    fragment = None
    for i in range(len(rest)):
        if rest[i] == '#':
            fragment = rest[i + 1:]
            rest = rest[:i]
            break
    query = None
    for i in range(len(rest)):
        if rest[i] == '?':
            query = rest[i + 1:]
            rest = rest[:i]
            break
    scheme = None
    hier = rest
    for i in range(len(rest)):
        if rest[i] == '/':
            break
        if rest[i] == ':':
            scheme = rest[:i]
            hier = rest[i + 1:]
            break
    if scheme is not None and not _scheme_ok(scheme):
        return ('scheme', None)
    authority = None
    path = hier
    if hier[:2] == '//':
        end = len(hier)
        for i in range(2, len(hier)):
            if hier[i] == '/':
                end = i
                break
        authority = hier[2:end]
        path = hier[end:]
    if _has_any(path, '[]'):
        return ('path_char', None)
    if query is not None and _has_any(query, '[]'):
        return ('query_char', None)
    if fragment is not None and _has_any(fragment, '[]#'):
        return ('fragment_char', None)
    return ('ok', (scheme, authority, path, query, fragment))


def _base_check(parts):
    if parts[0] is None:
        return 'no_scheme'
    if parts[4] is not None:
        return 'fragment'
    return 'ok'


def _merge(has_authority, base_path, ref_path):
    if has_authority and base_path == '':
        return '/' + ref_path
    i = len(base_path)
    for _steps in range(len(base_path) + 1):
        if i == 0 or base_path[i - 1] == '/':
            break
        i -= 1
    return base_path[:i] + ref_path


def _drop_last(out):
    j = len(out)
    for _steps in range(len(out) + 1):
        if j == 0 or out[j - 1] == '/':
            break
        j -= 1
    if j > 0:
        j -= 1
    return out[:j]


def _dots(path):
    inp = path
    out = ''
    for _steps in range(len(path) + 1):
        if inp == '':
            return out
        if inp[:3] == '../':
            inp = inp[3:]
        elif inp[:2] == './':
            inp = inp[2:]
        elif inp[:3] == '/./':
            inp = '/' + inp[3:]
        elif inp == '/.':
            inp = '/'
        elif inp[:4] == '/../':
            inp = '/' + inp[4:]
            out = _drop_last(out)
        elif inp == '/..':
            inp = '/'
            out = _drop_last(out)
        elif inp == '.' or inp == '..':
            inp = ''
        else:
            k = 1 if inp[0] == '/' else 0
            for _steps in range(len(inp) + 1):
                if k == len(inp) or inp[k] == '/':
                    break
                k += 1
            out += inp[:k]
            inp = inp[k:]
    return out


def _target(base, ref, strict):
    scheme = ref[0]
    if not strict and scheme is not None and scheme == base[0]:
        scheme = None
    if scheme is not None:
        return (scheme, ref[1], _dots(ref[2]), ref[3], ref[4])
    if ref[1] is not None:
        return (base[0], ref[1], _dots(ref[2]), ref[3], ref[4])
    if ref[2] == '':
        query = ref[3]
        if query is None:
            query = base[3]
        return (base[0], base[1], base[2], query, ref[4])
    if ref[2][0] == '/':
        path = _dots(ref[2])
    else:
        path = _dots(_merge(base[1] is not None, base[2], ref[2]))
    return (base[0], base[1], path, ref[3], ref[4])


def _join(parts):
    out = ''
    if parts[0] is not None:
        out += parts[0] + ':'
    if parts[1] is not None:
        out += '//' + parts[1]
    out += parts[2]
    if parts[3] is not None:
        out += '?' + parts[3]
    if parts[4] is not None:
        out += '#' + parts[4]
    return out


def _recompose(parts):
    out = _join(parts)
    if len(out) > TEXT_CAP:
        return ('output_length', None)
    parsed = _parse(out)
    if parsed[0] != 'ok':
        return (parsed[0], None)
    if parsed[1] != parts:
        return ('ambiguous', None)
    return ('ok', out)


def _check_parts(fail, parts, name):
    if type(parts) is not tuple:
        fail('bad_type:' + name)
    if len(parts) != 5:
        fail('bad_value:' + name + '.length')
    labels = ('scheme', 'authority', 'path', 'query', 'fragment')
    for k in range(5):
        if parts[k] is not None or k == 2:
            _str(fail, parts[k], name + '.' + labels[k], TEXT_CAP)


def _resolve_text(base_text, ref_text, strict):
    base = _parse(base_text)
    if base[0] != 'ok':
        return ('base.' + base[0], None)
    checked = _base_check(base[1])
    if checked != 'ok':
        return ('base.' + checked, None)
    ref = _parse(ref_text)
    if ref[0] != 'ok':
        return ('reference.' + ref[0], None)
    result = _recompose(_target(base[1], ref[1], strict))
    if result[0] != 'ok':
        return ('target.' + result[0], None)
    return result


def path_reason(text):
    _str(make_fail('path_reason'), text, 'text', TEXT_CAP)
    return _pct_run(text, PATHC)


def reference_reason(text):
    _str(make_fail('reference_reason'), text, 'text', TEXT_CAP)
    return _parse(text)[0]


def absolute_reason(text):
    _str(make_fail('absolute_reason'), text, 'text', TEXT_CAP)
    parsed = _parse(text)
    if parsed[0] != 'ok':
        return parsed[0]
    return _base_check(parsed[1])


def remove_dot_segments(path):
    fail = make_fail('remove_dot_segments')
    _str(fail, path, 'path', TEXT_CAP)
    reason = _pct_run(path, PATHC)
    if reason != 'ok':
        fail('bad_value:path.' + reason)
    return _dots(path)


def merge_paths(base_has_authority, base_path, ref_path):
    fail = make_fail('merge_paths')
    if type(base_has_authority) is not bool:
        fail('bad_type:base_has_authority')
    _str(fail, base_path, 'base_path', TEXT_CAP)
    _str(fail, ref_path, 'ref_path', TEXT_CAP)
    reason = _pct_run(base_path, PATHC)
    if reason != 'ok':
        fail('bad_value:base_path.' + reason)
    reason = _pct_run(ref_path, PATHC)
    if reason != 'ok':
        fail('bad_value:ref_path.' + reason)
    out = _merge(base_has_authority, base_path, ref_path)
    if len(out) > TEXT_CAP:
        fail('bad_value:output_length')
    return out


def split_reference(text):
    fail = make_fail('split_reference')
    _str(fail, text, 'text', TEXT_CAP)
    parsed = _parse(text)
    if parsed[0] != 'ok':
        fail('bad_value:text.' + parsed[0])
    return parsed[1]


def recompose(components):
    fail = make_fail('recompose')
    _check_parts(fail, components, 'components')
    result = _recompose(components)
    if result[0] != 'ok':
        fail('bad_value:components.' + result[0])
    return result[1]


def resolve_components(base, reference, strict):
    fail = make_fail('resolve_components')
    _check_parts(fail, base, 'base')
    _check_parts(fail, reference, 'reference')
    if type(strict) is not bool:
        fail('bad_type:strict')
    result = _recompose(base)
    if result[0] != 'ok':
        fail('bad_value:base.' + result[0])
    checked = _base_check(base)
    if checked != 'ok':
        fail('bad_value:base.' + checked)
    result = _recompose(reference)
    if result[0] != 'ok':
        fail('bad_value:reference.' + result[0])
    target = _target(base, reference, strict)
    result = _recompose(target)
    if result[0] != 'ok':
        fail('bad_value:target.' + result[0])
    return target


def resolve_reference(base_text, reference_text, strict):
    fail = make_fail('resolve_reference')
    _str(fail, base_text, 'base', TEXT_CAP)
    _str(fail, reference_text, 'reference', TEXT_CAP)
    if type(strict) is not bool:
        fail('bad_type:strict')
    result = _resolve_text(base_text, reference_text, strict)
    if result[0] != 'ok':
        fail('bad_value:' + result[0])
    return result[1]


def resolve_reason(base_text, reference_text, strict):
    fail = make_fail('resolve_reason')
    _str(fail, base_text, 'base', TEXT_CAP)
    _str(fail, reference_text, 'reference', TEXT_CAP)
    if type(strict) is not bool:
        fail('bad_type:strict')
    return _resolve_text(base_text, reference_text, strict)[0]
