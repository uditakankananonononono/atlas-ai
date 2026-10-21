r"""p235 concepts batch 1219 (rev 1): RFC 9110 quality values (12.4.2), Accept (12.5.1) and Accept-Language (12.5.4) syntax. Pure functions over caller-supplied text. No retrieval, no network, no clock. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it does no content negotiation, consults no registry, and knows no media-type or language-tag semantics. ADJACENT names the neighbouring grammars this unit deliberately does not implement: the RFC 6838 media type registry grammar and registered semantics (b1172), RFC 2045 MIME media type and parameter semantics (b1204), and RFC 4647 matching schemes.

LIVE-READ SOURCES (read live, quoted verbatim below and mechanically matched against the whitespace-collapsed RFC text with the page headers and footers removed):
- RFC 9110, HTTP Semantics, Standards Track, June 2022. rfc9110.txt is 502941 bytes, sha256 21c1cdce6ab0e5509b04d84a28000836c7a087cf786efe6f04877ebfff47232a.
- RFC 4647, Matching of Language Tags, September 2006, for the language-range grammar imported by 12.5.4. rfc4647.txt is 45595 bytes, sha256 999e4e23ca5b8925ac5f154855af0f2948a5d26d14853249c9fc857e469ecb49.
- The rfc-editor info page for RFC 9110 lists Updates (1): RFC 3864, and Obsoletes (9): RFC 2818, RFC 7230, RFC 7231, RFC 7232, RFC 7233, RFC 7235, RFC 7538, RFC 7615, RFC 7694; the abstract on the page describes the 7230 entry as portions of RFC 7230. The page shows no Obsoleted by entry and no Updated by entry: RFC 9110 is the current HTTP Semantics document. CLAIMS current is still False.
- errata.json (sha256 2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) records 14 errata for RFC 9110; 1 erratum touches the sections used here: 7138 (Verified, Technical, section 12.5.1) corrects a worked-example table value (text/html;level=3 maps to 0.3, not 0.7); it is about negotiation semantics and changes no grammar. The other 13 touch sections 5.2, 6.4.1, 6.5.1, 8.3.2, 8.6, 14.1.1, 15, 15.4, 15.4.9, 15.5.2, Appendix A and B.1/B.2, none of which carry grammar used here. Both counts are taken from that single JSON index and are not independently confirmed against the per-erratum pages. OURS: no erratum is applied. The RFC text and its collected ABNF decide. RFC 4647 carries 3 errata in the same index: 8287 (Reported, Technical, 3.1), 8253 (Held for Document Update, Editorial, 2 and 2.3) and 8838 (Verified, Editorial, 2.2); none touches section 2.1.

SOURCED (the RFC text):
- Weight and qvalue (9110 12.4.2): "weight = OWS ";" OWS "q=" qvalue" "qvalue = ( "0" [ "." 0*3DIGIT ] ) / ( "1" [ "." 0*3("0") ] )"
- The q parameter and default (12.4.2): "The content negotiation fields defined by this specification use a common parameter, named "q" (case-insensitive), to assign a relative "weight" to the preference for that associated kind of content." "The weight is normalized to a real number in the range 0 through 1, where 0.001 is the least preferred and 1 is the most preferred; a value of 0 means "not acceptable". If no "q" parameter is present, the default weight is 1."
- Sender digit limit (12.4.2): "A sender of qvalue MUST NOT generate more than three digits after the decimal point."
- Accept (12.5.1): "Accept = #( media-range [ weight ] )" "media-range = ( "*/*" / ( type "/" "*" ) / ( type "/" subtype ) ) parameters"
- Wildcards (12.5.1): "The asterisk "*" character is used to group media types into ranges, with "*/*" indicating all media types and "type/*" indicating all subtypes of that type."
- accept-ext removed, q last (12.5.1): "Previous specifications allowed additional extension parameters to appear after the weight parameter. The accept extension grammar (accept-params, accept-ext) has been removed because it had a complicated definition, was not being used in practice, and is more easily deployed through new header fields." "Senders using weights SHOULD send "q" last (after all media-range parameters). Recipients SHOULD process any parameter named "q" as weight, regardless of parameter ordering."
- Accept example (12.5.1): "Accept: audio/*; q=0.2, audio/basic"
- Accept-Language (12.5.4): "Accept-Language = #( language-range [ weight ] )" "language-range = <language-range, see [RFC4647], Section 2.1>"
- Accept-Language example (12.5.4): "Accept-Language: da, en-gb;q=0.8, en;q=0.7"
- Parameters (9110 5.6.6): "parameters = *( OWS ";" OWS [ parameter ] )" "parameter = parameter-name "=" parameter-value" "parameter-name = token" "parameter-value = ( token / quoted-string )"
- Parameter name case (5.6.6): "Parameter names are case-insensitive."
- Media type (9110 8.3.1): "media-type = type "/" subtype parameters" "type = token" "subtype = token"
- Type and subtype case (8.3.1): "The type and subtype tokens are case-insensitive."
- Token (9110 5.6.2): "token = 1*tchar" "tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*" / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA"
- Quoted string (9110 5.6.4): "quoted-string = DQUOTE *( qdtext / quoted-pair ) DQUOTE" "qdtext = HTAB / SP / %x21 / %x23-5B / %x5D-7E / obs-text" "quoted-pair = "\" ( HTAB / SP / VCHAR / obs-text )"
- Quoted-pair handling (5.6.4): "Recipients that process the value of a quoted-string MUST handle a quoted-pair as if it were replaced by the octet following the backslash."
- OWS (9110 5.6.3, collected ABNF): "OWS = *( SP / HTAB )"
- Recipient list rule (9110 5.6.1.2): "#element => [ element ] *( OWS "," OWS [ element ] )"
- Empty list elements (5.6.1.2): "Empty elements do not contribute to the count of elements present. A recipient MUST parse and ignore a reasonable number of empty list elements: enough to handle common mistakes by senders that merge values, but not so much that they could be used as a denial-of- service mechanism."
- Language range (RFC 4647 2.1): "language-range = (1*8ALPHA *("-" 1*8alphanum)) / "*"" "alphanum = ALPHA / DIGIT"
- No registry validation (RFC 4647 2.1): "A basic language range differs from the language tags defined in [RFC4646] only in that there is no requirement that it be "well- formed" or be validated against the IANA Language Subtag Registry."

OURS (conventions this module adds, each pinned by tests):
1. ASCII only. obs-text (%x80-FF) is refused everywhere, including inside quoted-string and quoted-pair. Every other non-ASCII character is refused. Membership is tested with explicit ASCII strings, never with Unicode-aware str methods.
2. Case folding. The q parameter name is matched case-insensitively (12.4.2: named "q" (case-insensitive)); the fold is an explicit ASCII A-Z to a-z map only. Returned structures preserve the original case of every token.
3. Recipient list rule. Following 5.6.1.2, empty list elements are accepted and skipped, and so are leading commas, trailing commas and OWS-only segments; the empty string and OWS-only strings are accepted as zero-element lists by accept_reason and accept_language_reason, and split_accept and split_accept_language then return the empty list.
4. Bare semicolons. parameters is *( OWS ";" OWS [ parameter ] ), so a semicolon need not be followed by a parameter: "a/b;", "a/b;;p=1" and "a/b; , text/plain" are all ok.
5. No OWS around "=". parameter is parameter-name "=" parameter-value with no whitespace inside (5.6.6), and weight writes "q=" literally, so "a/b;q =0.5" is param.equals and "a/b;q= 0.5" is param.value.
6. Weight detection in split_accept. Following "Recipients SHOULD process any parameter named "q" as weight, regardless of parameter ordering", the first parameter whose name folds to "q" and whose value, taken as a bare token or as the content of a quoted-string, is a valid qvalue is reported as the weight; every other parameter (a q whose value, quoted or not, is not a valid qvalue, and later q duplicates) stays in the params tuple in order. A parameter named q with an invalid qvalue value is still syntactically a parameter, so accept_reason("text/html;q=2") is ok. split_accept_language is strict the other way: it admits no parameters at all (OURS 9), and a quoted q value there is not dequoted, so en;q="0.5" is refused as weight.value.empty while split_accept reports its weight.
7. Wildcards by ABNF. "*" is a tchar, so "*/html" parses as type "/" subtype like the grammar writes; only the prose restricts "*" to the two range forms, and this syntax-only unit does not (12.5.1 wildcard semantics are NOT_CLAIMED).
8. language-range per RFC 4647 2.1: "*" alone, or a first subtag of 1-8 ASCII letters followed by subtags of 1-8 ASCII letters or digits. There is no registry validation, exactly as 4647 states. "a-*" is refused as form, because after the first subtag each subtag is 1-8 ASCII letters or digits and the asterisk is neither; "x-private" is ok under the 2.1 grammar alone.
9. Accept-Language elements carry no parameters, only an optional weight (12.5.4): "en;foo=1" is weight.name, and anything after the qvalue other than OWS or "," is weight.value.char or comma.
10. Canonical format. accept_format and accept_language_format join elements with ", ", put "; " before each parameter and before "; q=", emit parameter values as bare tokens when possible and as quoted-strings otherwise (escaping DQUOTE and backslash), and qvalue_format emits the shortest qvalue with up to three decimals ("0.5", not "0.500"). Trailing list OWS is never emitted.

CAPS AND CLOSURE: TEXT_CAP is 4096 characters for every text input, and 4096 entries for every entries input. Lengths are checked before any content is read. The payloads of split_accept and split_accept_language are built from slices of the input and never longer than it.

FUNCTIONS, in this order: qvalue_reason, qvalue_format, media_range_reason, language_range_reason, accept_reason, accept_language_reason, split_accept, split_accept_language, accept_format, accept_language_format. Errors are ValueError with the text P235:<function>:<code>. A code is bad_type:<name> (exact built-in type by identity, subclasses and bool-for-int refused), bad_value:<name>.length, or bad_value:<name>.<reason>.

REASONS, in check order (the first failure decides, so a text with several faults reports the first):
- qvalue_reason: empty, then a single left-to-right pass: char (a character that is neither DIGIT nor "."), then form (not "0" or "1" with an optional "." and up to three fraction digits, all "0" after "1."). ok otherwise.
- qvalue_format: bad_type:milli (bool refused), then bad_value:milli.range outside 0..1000.
- media_range_reason: empty, then type (no type token), slash (no "/" after the type), subtype (no subtype token), then the parameters left to right: semicolon (a character other than OWS, ";" or the end), param.name, param.equals, param.value, then tail (characters or trailing OWS after the last parameter). ok otherwise.
- language_range_reason: empty, then form (a "*" inside a longer range, or a first character that is not an ASCII letter), then a single left-to-right pass over subtags: char (a character that is not ALPHA or DIGIT or "-"), form (an empty or over-8 subtag or a trailing "-"). ok otherwise.
- accept_reason: per element in order: type, slash, subtype, then parameters: semicolon, param.name, param.equals, param.value; the list level accepts empty elements and trailing OWS. ok otherwise.
- accept_language_reason: per element in order: the language_range_reason reasons, then comma (a character other than OWS, ";" or "," after the range), then the weight: weight.name, weight.equals, weight.value.empty, weight.value.form, weight.value.char. ok otherwise.
- split_accept and split_accept_language: the accept_reason and accept_language_reason reasons as bad_value:text.<reason>.
- accept_format: bad_type:entries, bad_value:entries.length, then per entry bad_type:entries.item, bad_type:range, bad_value:range.form, bad_type:entries.item for params, bad_type:name, bad_type:value, bad_value:name.form, bad_value:value.form, bad_type:q, bad_value:q.form. accept_language_format: the same without name and value.

OUTPUT ORDER: split_accept returns a list of (range, params, q) in list order: range the type "/" subtype text as written, params a tuple of (name, value) pairs in order (a quoted value is unquoted; names keep their original case), q the detected weight qvalue string or None. split_accept_language returns a list of (range, q-or-None) in list order. accept_format takes split_accept-shaped entries; accept_language_format takes split_accept_language-shaped entries.
"""
SCOPE = 'RFC 9110 sections 12.4.2, 12.5.1 and 12.5.4 syntax over caller-supplied text: qvalue, weight, media-range, language-range, Accept and Accept-Language lists, well-formed parse and canonical format'
NOT_CLAIMED = ('standard', 'authority', 'certification', 'currency', 'completeness', 'negotiation', 'registry', 'media-type-semantics', 'language-tag-semantics')
CLAIMS = {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False,
          'negotiation': False, 'registry': False, 'media_type_semantics': False, 'language_tag_semantics': False}
ADJACENT = ('RFC 6838 media type registry grammar and registered type/subtype/parameter semantics (b1172)', 'RFC 2045 MIME media type and parameter semantics (b1204)', 'RFC 4647 language matching schemes (only the 2.1 basic language-range syntax is in scope here)')
TEXT_CAP = 4096
DIGITS = '0123456789'
UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
LOWER = 'abcdefghijklmnopqrstuvwxyz'
ALPHA = UPPER + LOWER
ALNUM = ALPHA + DIGITS
TCHARS = DIGITS + UPPER + LOWER + "!#$%&'*+-.^_`|~"
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
            raise ValueError('P235:%s:%s' % (name, code))
        return fail


def _str(fail, x, name, cap):
    if type(x) is not str:
        fail('bad_type:' + name)
    if len(x) > cap:
        fail('bad_value:%s.length' % name)


def _int(fail, x, name):
    if type(x) is not int:
        fail('bad_type:' + name)


def _fold(s):
    out = ''
    for c in s:
        if c in FOLD:
            out += FOLD[c]
        else:
            out += c
    return out


def _ows_end(text, i):
    for _steps in range(len(text) + 1):
        if i == len(text) or (text[i] != ' ' and text[i] != '\t'):
            return i
        i += 1
    return i


def _token_run(text, i):
    j = i
    for _steps in range(len(text) + 1):
        if j == len(text) or text[j] not in TCHARS:
            return j
        j += 1
    return j


def _qd_ok(ch):
    return ch in QDT


def _qp_ok(ch):
    return ch in QPT


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


def _param_at(text, i):
    # parameter = parameter-name "=" parameter-value (no OWS inside, 5.6.6).
    # Returns ('ok', end) or (reason, -1).
    t = _token_run(text, i)
    if t == i:
        return ('param.name', -1)
    if t == len(text) or text[t] != '=':
        return ('param.equals', -1)
    v = t + 1
    if v == len(text):
        return ('param.value', -1)
    if text[v] == '"':
        k = _quoted_end(text, v)
        if k < 0:
            return ('param.value', -1)
        return ('ok', k)
    k = _token_run(text, v)
    if k == v:
        return ('param.value', -1)
    return ('ok', k)


def _param_parts(text, i):
    # Splits the parameter starting at i (already validated by _param_at).
    t = _token_run(text, i)
    name = text[i:t]
    v = t + 1
    if text[v] == '"':
        out = ''
        k = v + 1
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
    k = _token_run(text, v)
    return (name, text[v:k])


def _range_end(text, i):
    # type "/" subtype at i; returns (reason, end). end stops before any
    # parameter semicolon or list comma.
    t = _token_run(text, i)
    if t == i:
        return ('type', -1)
    if t == len(text) or text[t] != '/':
        return ('slash', -1)
    s = _token_run(text, t + 1)
    if s == t + 1:
        return ('subtype', -1)
    return ('ok', s)


def _params_end(text, pos):
    # parameters = *( OWS ";" OWS [ parameter ] ); returns (reason, end).
    for _steps in range(len(text) + 1):
        pos = _ows_end(text, pos)
        if pos == len(text) or text[pos] == ',':
            return ('ok', pos)
        if text[pos] != ';':
            return ('semicolon', -1)
        pos = _ows_end(text, pos + 1)
        if pos == len(text) or text[pos] == ',' or text[pos] == ';':
            continue
        reason, pos = _param_at(text, pos)
        if reason != 'ok':
            return (reason, -1)
    return ('ok', pos)


def _weight_at(text, i):
    # weight = OWS ";" OWS "q=" qvalue at i; q case-insensitive. Returns
    # (reason, end) with end just past the qvalue.
    p = _ows_end(text, i)
    if p == len(text) or text[p] != ';':
        return ('semicolon', -1)
    p = _ows_end(text, p + 1)
    if p == len(text) or text[p] not in 'qQ':
        return ('name', -1)
    if p + 1 == len(text) or text[p + 1] != '=':
        return ('equals', -1)
    j = p + 2
    r = j
    for _steps in range(len(text) + 1):
        if r == len(text) or (text[r] not in DIGITS and text[r] != '.'):
            break
        r += 1
    if r == j:
        return ('value.empty', -1)
    qr = qvalue_reason(text[j:r])
    if qr != 'ok':
        return ('value.' + qr, -1)
    if r < len(text) and text[r] != ' ' and text[r] != '\t' and text[r] != ',':
        return ('value.char', -1)
    return ('ok', r)


def qvalue_reason(text):
    fail = make_fail('qvalue_reason')
    _str(fail, text, 'text', TEXT_CAP)
    if text == '':
        return 'empty'
    for ch in text:
        if ch not in DIGITS and ch != '.':
            return 'char'
    if text[0] != '0' and text[0] != '1':
        return 'form'
    if len(text) == 1:
        return 'ok'
    if text[1] != '.':
        return 'form'
    frac = text[2:]
    if len(frac) > 3:
        return 'form'
    for ch in frac:
        if ch not in DIGITS:
            return 'form'
    if text[0] == '1':
        for ch in frac:
            if ch != '0':
                return 'form'
    return 'ok'


def qvalue_format(milli):
    fail = make_fail('qvalue_format')
    _int(fail, milli, 'milli')
    if milli < 0 or milli > 1000:
        fail('bad_value:milli.range')
    if milli == 1000:
        return '1'
    if milli == 0:
        return '0'
    s = '%03d' % milli
    for _steps in range(4):
        if s[-1] != '0':
            break
        s = s[:-1]
    return '0.' + s


def media_range_reason(text):
    fail = make_fail('media_range_reason')
    _str(fail, text, 'text', TEXT_CAP)
    if text == '':
        return 'empty'
    reason, pos = _range_end(text, 0)
    if reason != 'ok':
        return reason
    reason, e = _params_end(text, pos)
    if reason != 'ok':
        return reason
    if e != len(text) or text[-1] == ' ' or text[-1] == '\t':
        return 'tail'
    return 'ok'


def language_range_reason(text):
    fail = make_fail('language_range_reason')
    _str(fail, text, 'text', TEXT_CAP)
    if text == '':
        return 'empty'
    if text == '*':
        return 'ok'
    if '*' in text:
        return 'form'
    if text[0] not in ALPHA:
        return 'form'
    sub = ''
    first = True
    for ch in text:
        if ch == '-':
            if sub == '':
                return 'form'
            first = False
            sub = ''
        elif ch not in ALNUM or (first and ch not in ALPHA):
            return 'char' if ch not in ALNUM else 'form'
        else:
            sub += ch
            if len(sub) > 8:
                return 'form'
    if sub == '':
        return 'form'
    return 'ok'


def _element_end(text, pos, lang):
    # Parses one list element (media-range parameters / language-range
    # [ weight ]) at pos; returns (reason, end).
    if lang:
        t = _token_run(text, pos)
        if not (t == pos + 1 and text[pos] == '*'):
            r = language_range_reason(text[pos:t])
            if r != 'ok':
                return (r, -1)
        p = _ows_end(text, t)
        if p == len(text) or text[p] == ',':
            return ('ok', p)
        if text[p] != ';':
            return ('comma', -1)
        reason, e = _weight_at(text, p)
        if reason != 'ok':
            return ('weight.' + reason, -1)
        return ('ok', e)
    reason, e = _range_end(text, pos)
    if reason != 'ok':
        return (reason, -1)
    return _params_end(text, e)


def _list_reason(text, lang):
    # #rule recipient requirements (5.6.1.2): empty elements are skipped.
    pos = 0
    for _steps in range(len(text) + 1):
        pos = _ows_end(text, pos)
        if pos == len(text):
            return 'ok'
        if text[pos] == ',':
            pos += 1
            continue
        reason, pos = _element_end(text, pos, lang)
        if reason != 'ok':
            return reason
        pos = _ows_end(text, pos)
        if pos == len(text):
            return 'ok'
        if text[pos] != ',':
            return 'comma'
        pos += 1
    return 'ok'


def accept_reason(text):
    fail = make_fail('accept_reason')
    _str(fail, text, 'text', TEXT_CAP)
    return _list_reason(text, False)


def accept_language_reason(text):
    fail = make_fail('accept_language_reason')
    _str(fail, text, 'text', TEXT_CAP)
    return _list_reason(text, True)


def _split_weight(params):
    # Returns (q-or-None, kept-params). The first parameter named q
    # (case-insensitive) whose bare-token value is a valid qvalue is the
    # weight; every other parameter is kept in order.
    q = None
    kept = []
    for name, value in params:
        if q is None and _fold(name) == 'q' and qvalue_reason(value) == 'ok':
            q = value
        else:
            kept += [(name, value)]
    return (q, kept)


def split_accept(text):
    fail = make_fail('split_accept')
    _str(fail, text, 'text', TEXT_CAP)
    r = _list_reason(text, False)
    if r != 'ok':
        fail('bad_value:text.' + r)
    out = []
    pos = 0
    for _steps in range(len(text) + 1):
        pos = _ows_end(text, pos)
        if pos == len(text):
            return out
        if text[pos] == ',':
            pos += 1
            continue
        reason, e = _range_end(text, pos)
        rng = text[pos:e]
        params = []
        p = e
        for _s2 in range(len(text) + 1):
            p = _ows_end(text, p)
            if p == len(text) or text[p] == ',':
                break
            p = _ows_end(text, p + 1)
            if p != len(text) and text[p] != ',' and text[p] != ';':
                nm, val = _param_parts(text, p)
                params += [(nm, val)]
                _r2, p = _param_at(text, p)
        q, kept = _split_weight(params)
        out += [(rng, tuple(kept), q)]
        pos = p
    return out


def split_accept_language(text):
    fail = make_fail('split_accept_language')
    _str(fail, text, 'text', TEXT_CAP)
    r = _list_reason(text, True)
    if r != 'ok':
        fail('bad_value:text.' + r)
    out = []
    pos = 0
    for _steps in range(len(text) + 1):
        pos = _ows_end(text, pos)
        if pos == len(text):
            return out
        if text[pos] == ',':
            pos += 1
            continue
        t = _token_run(text, pos)
        rng = text[pos:t]
        p = _ows_end(text, t)
        q = None
        if p < len(text) and text[p] == ';':
            w = _ows_end(text, p + 1)
            _wr, e = _weight_at(text, p)
            q = text[w + 2:e]
        else:
            e = p
        out += [(rng, q)]
        pos = e
    return out


def _format_param_value(value):
    if value != '' and _token_run(value, 0) == len(value):
        return value
    out = '"'
    for ch in value:
        if ch == '"' or ch == '\\':
            out += '\\'
        out += ch
    return out + '"'


def accept_format(entries):
    fail = make_fail('accept_format')
    if type(entries) is not list:
        fail('bad_type:entries')
    if len(entries) > TEXT_CAP:
        fail('bad_value:entries.length')
    parts = []
    for ent in entries:
        if type(ent) is not tuple or len(ent) != 3:
            fail('bad_type:entries.item')
        rng, params, q = ent
        _str(fail, rng, 'range', TEXT_CAP)
        if media_range_reason(rng) != 'ok':
            fail('bad_value:range.form')
        if type(params) is not tuple:
            fail('bad_type:entries.item')
        seg = rng
        for prm in params:
            if type(prm) is not tuple or len(prm) != 2:
                fail('bad_type:entries.item')
            nm, val = prm
            _str(fail, nm, 'name', TEXT_CAP)
            _str(fail, val, 'value', TEXT_CAP)
            if nm == '' or _token_run(nm, 0) != len(nm):
                fail('bad_value:name.form')
            if val != '' and _token_run(val, 0) != len(val):
                for vc in val:
                    if not _qp_ok(vc):
                        fail('bad_value:value.form')
            seg += '; ' + nm + '=' + _format_param_value(val)
        if q is not None:
            _str(fail, q, 'q', TEXT_CAP)
            if qvalue_reason(q) != 'ok':
                fail('bad_value:q.form')
            seg += '; q=' + q
        parts += [seg]
    out = ''
    for p in parts:
        if out != '':
            out += ', '
        out += p
    return out


def accept_language_format(entries):
    fail = make_fail('accept_language_format')
    if type(entries) is not list:
        fail('bad_type:entries')
    if len(entries) > TEXT_CAP:
        fail('bad_value:entries.length')
    parts = []
    for ent in entries:
        if type(ent) is not tuple or len(ent) != 2:
            fail('bad_type:entries.item')
        rng, q = ent
        _str(fail, rng, 'range', TEXT_CAP)
        if language_range_reason(rng) != 'ok':
            fail('bad_value:range.form')
        seg = rng
        if q is not None:
            _str(fail, q, 'q', TEXT_CAP)
            if qvalue_reason(q) != 'ok':
                fail('bad_value:q.form')
            seg += '; q=' + q
        parts += [seg]
    out = ''
    for p in parts:
        if out != '':
            out += ', '
        out += p
    return out
