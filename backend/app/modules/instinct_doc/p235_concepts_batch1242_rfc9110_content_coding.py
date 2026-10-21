"""P235 batch1242: RFC 9110 content codings.

CLAIM: this module implements the content-coding grammar of RFC 9110
(HTTP Semantics, June 2022, Internet Standard, obsoletes RFC 2818,
RFC 7230, RFC 7231, RFC 7232, RFC 7233, RFC 7235, RFC 7538, RFC 7615
and RFC 7694, updates RFC 3864, not obsoleted, not updated) over caller
supplied str values, as pure functions, without decoding any content.
Section 8.4.1 defines content-coding = token, where token is the
Section 5.6.2 production (one or more tchar) and all content codings
are case-insensitive. Section 8.4 defines Content-Encoding =
#content-coding. Section 12.5.3 defines Accept-Encoding =
#( codings [ weight ] ) with codings = content-coding / "identity" /
"*", the Section 12.4.2 weight (OWS ";" OWS "q=" qvalue, the "q"
parameter name case-insensitive, qvalue = ( "0" [ "." 0*3DIGIT ] ) /
( "1" [ "." 0*3("0") ] ), a missing weight meaning 1 and a qvalue of 0
meaning "not acceptable"), and the asterisk matching any content
coding not explicitly listed. List parsing follows the recipient
requirements of Section 5.6.1.2: empty list elements are parsed and
ignored and do not contribute to the element count.

ADJACENCY: the weight and qvalue grammar and the #rule list parsing
are owned in general by batch1219 (RFC 9110 weight, Accept and
Accept-Language); this unit keeps a thin, self-contained local
implementation of exactly what the content-coding fields need, and
does not claim the general weight or list machinery.

OURS decisions: scheme-like details the RFC leaves open are fixed as
follows. A qvalue of exactly "0", "0.", "0.0", "0.00" or "0.000"
counts as zero ("not acceptable"); "0.001" is the least preferred
nonzero weight. Text after the maximal qvalue (such as the fourth
digit of "0.1234" or the second zero of "00") is trailing junk and is
refused as bad_value:list, while a missing or mistyped start of the
qvalue is bad_value:qvalue and a ";" not starting a weight is
bad_value:weight. When the same codings name appears more than once,
the last entry wins. A list with zero contributing elements (empty
field value, or only commas and whitespace) is valid, carries the
Section 12.5.3 empty-field meaning (no content coding wanted, identity
acceptable), and is pinned. coding_acceptable evaluates the three
rules of Section 12.5.3 exactly: an absent field (None) makes every
valid coding acceptable; an identity question is refused only by
identity;q=0 or by "*;q=0" without a more specific identity entry; a
listed coding is refused by its own q=0, an unlisted coding is
acceptable only through a "*" entry with nonzero q. coding_acceptable
refuses "*" as the asked-about coding (the asterisk only appears
inside the field). Content-Encoding accepts "identity" and "*" as
plain tokens (Section 8.4 only says identity SHOULD NOT be included).
The x-compress and x-gzip aliases of Section 8.4.1.1 and 8.4.1.3 are
recipient guidance and are NOT folded by this unit. The live IANA
HTTP Content Coding Registry is not tracked. Implementation guards:
at most 255 characters per token, 4096 characters per field value,
256 contributing elements; the value cap also bounds the empty
elements a recipient must ignore (Section 5.6.1.2).

Errata (live rfc-editor.org errata.json fetched 2026-10-21 at
authoring; every record of RFC 9110 named with EID, status, type and
section exactly as the listing shows; RFC 9110 has 14 records, none
of which touches Sections 5.6, 8.4, 12.4.2 or 12.5.3): RFC9110
Rejected Editorial: EID 7530 (15.5.2.). RFC9110 Rejected Technical:
EID 7107 (6.5.1), EID 7599 (6.4.1), EID 7870 (8.6), EID 8138 (15.4),
EID 8459 (15). RFC9110 Reported Technical: EID 9162 (5.2), EID 9164
(Appendix A). RFC9110 Verified Editorial: EID 7105 (B.1.), EID 7109
(15.4.9), EID 8268 (B.2). RFC9110 Verified Technical: EID 7138
(12.5.1), EID 7306 (14.1.1), EID 7419 (8.3.2).  SCOPE and NOT_CLAIMED
below are pinned by the tests.
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

__all__ = ['coding_token_validate', 'content_encoding_validate',
           'content_encoding_list', 'accept_encoding_validate',
           'accept_encoding_list', 'coding_acceptable']

TOKEN_CAP = 255
VALUE_CAP = 4096
COUNT_CAP = 256

_TCHAR = ((33, 33), (35, 39), (42, 43), (45, 46), (48, 57), (65, 90),
          (94, 96), (97, 122), (124, 124), (126, 126),)
_OWS = ((9, 9), (32, 32),)
_DIG = ((48, 57),)

SCOPE = ('FULL: the RFC 9110 content-coding grammar over caller '
         'supplied str values: the Section 8.4.1 content-coding token '
         '(Section 5.6.2 tchar), the Section 8.4 Content-Encoding '
         'list, and the Section 12.5.3 Accept-Encoding list with its '
         'Section 12.4.2 qvalue weight, asterisk and identity rules '
         'and the q=0 "not acceptable" semantics, with Section 5.6.1.2 '
         'recipient list parsing (empty elements ignored)')
NOT_CLAIMED = ('The general weight/qvalue and #rule machinery '
               '(batch1219 owns it); decoding any content; the live '
               'IANA HTTP Content Coding Registry; folding the '
               'x-compress and x-gzip aliases (recipient guidance '
               'only); Content-Language and language tags (batch1218 '
               'owns RFC 5646); media types, Accept and other '
               'negotiation fields')


def _in(code, ranges):
    for lo, hi in ranges:
        if lo <= code <= hi:
            return True
    return False


def _fold(ch):
    code = ord(ch)
    if 65 <= code <= 90:
        return chr(code + 32)
    return ch


def _folded(text):
    return ''.join(_fold(ch) for ch in text)


def _ows_end(text, pos):
    while pos < len(text) and _in(ord(text[pos]), _OWS):
        pos += 1
    return pos


def _token_end(f, text, pos):
    start = pos
    while pos < len(text) and _in(ord(text[pos]), _TCHAR):
        pos += 1
    if pos == start:
        f('bad_value:token')
    if pos - start > TOKEN_CAP:
        f('bad_value:field.length')
    return pos


def _qvalue_end(f, text, pos):
    if pos == len(text):
        f('bad_value:qvalue')
    ch = text[pos]
    if ch == '0':
        pos += 1
        if pos < len(text) and text[pos] == '.':
            pos += 1
            digs = 0
            while pos < len(text) and digs < 3 and _in(
                    ord(text[pos]), _DIG):
                pos += 1
                digs += 1
        return pos
    if ch == '1':
        pos += 1
        if pos < len(text) and text[pos] == '.':
            pos += 1
            digs = 0
            while pos < len(text) and digs < 3 and text[pos] == '0':
                pos += 1
                digs += 1
        return pos
    f('bad_value:qvalue')


def _weight_end(f, text, pos):
    # at a ';': OWS ';' OWS 'q=' qvalue
    pos += 1
    pos = _ows_end(text, pos)
    if pos + 1 > len(text) - 1:
        f('bad_value:weight')
    pair = text[pos:pos + 2]
    if pair != 'q=' and pair != 'Q=':
        f('bad_value:weight')
    return _qvalue_end(f, text, pos + 2)


def _element_end(f, text, pos, weighted):
    pos = _token_end(f, text, pos)
    if weighted:
        save = _ows_end(text, pos)
        if save < len(text) and text[save] == ';':
            pos = _weight_end(f, text, save)
    return pos


def _list(f, text, weighted, collect):
    pos = 0
    end = len(text)
    count = 0
    while True:
        pos = _ows_end(text, pos)
        if pos < end and text[pos] != ',':
            count += 1
            if count > COUNT_CAP:
                f('bad_value:field.count')
            start = pos
            pos = _element_end(f, text, pos, weighted)
            if collect is not None:
                collect.append((start, pos))
        pos = _ows_end(text, pos)
        if pos == end:
            return
        if text[pos] != ',':
            f('bad_value:list')
        pos += 1


def coding_token_validate(text):
    """Validate a content-coding token (RFC 9110 Section 8.4.1:
    content-coding = token, the Section 5.6.2 production of one or
    more tchar) as a caller supplied str. Return the text unchanged.
    Refusals: bad_type:text for a non-str; bad_value:field.length
    over TOKEN_CAP; bad_value:token when empty; bad_value:token.char
    for a character outside tchar."""
    f = make_fail('coding_token_validate')
    if type(text) is not str:
        f('bad_type:text')
    if len(text) > TOKEN_CAP:
        f('bad_value:field.length')
    pos = 0
    while pos < len(text):
        if not _in(ord(text[pos]), _TCHAR):
            f('bad_value:token.char')
        pos += 1
    if len(text) == 0:
        f('bad_value:token')
    return text


def content_encoding_validate(value):
    """Validate a Content-Encoding field value (RFC 9110 Section 8.4:
    #content-coding, recipient list rules of Section 5.6.1.2 so empty
    elements are ignored) as a caller supplied str; the empty value is
    valid. Return the value unchanged. Refusals: bad_type:text for a
    non-str; bad_value:field.length over VALUE_CAP;
    bad_value:field.count over COUNT_CAP contributing elements;
    bad_value:token.char for a non-tchar character;
    bad_value:list for junk between elements."""
    f = make_fail('content_encoding_validate')
    if type(value) is not str:
        f('bad_type:text')
    if len(value) > VALUE_CAP:
        f('bad_value:field.length')
    _list(f, value, False, None)
    return value


def content_encoding_list(value):
    """Extract the content codings of a Content-Encoding field value
    (RFC 9110 Section 8.4) from a caller supplied str, as a tuple of
    verbatim element strings in field order. Refusals: bad_type:text
    for a non-str; bad_value:field.length over VALUE_CAP;
    bad_value:field.count over COUNT_CAP contributing elements;
    bad_value:token.char for a non-tchar character;
    bad_value:list for junk between elements."""
    f = make_fail('content_encoding_list')
    if type(value) is not str:
        f('bad_type:text')
    if len(value) > VALUE_CAP:
        f('bad_value:field.length')
    spans = []
    _list(f, value, False, spans)
    return tuple(value[a:b] for a, b in spans)


def accept_encoding_validate(value):
    """Validate an Accept-Encoding field value (RFC 9110 Section
    12.5.3: #( codings [ weight ] ), recipient list rules of Section
    5.6.1.2) as a caller supplied str; the empty value is valid.
    Return the value unchanged. Refusals: bad_type:text for a
    non-str; bad_value:field.length over VALUE_CAP;
    bad_value:field.count over COUNT_CAP contributing elements;
    bad_value:token.char for a non-tchar character;
    bad_value:weight for a ";" not starting a Section 12.4.2 weight;
    bad_value:qvalue for a malformed qvalue; bad_value:list for junk
    between elements or after a weight."""
    f = make_fail('accept_encoding_validate')
    if type(value) is not str:
        f('bad_type:text')
    if len(value) > VALUE_CAP:
        f('bad_value:field.length')
    _list(f, value, True, None)
    return value


def accept_encoding_list(value):
    """Extract the entries of an Accept-Encoding field value (RFC
    9110 Section 12.5.3) from a caller supplied str, as a tuple of
    (codings, qvalue) pairs in field order; both parts are verbatim
    strings, the qvalue without its "q=" prefix, and the qvalue is
    None when no weight is present (default weight 1). Refusals:
    bad_type:text for a non-str; bad_value:field.length over
    VALUE_CAP; bad_value:field.count over COUNT_CAP contributing
    elements; bad_value:token.char for a non-tchar character;
    bad_value:weight for a ";" not starting a weight;
    bad_value:qvalue for a malformed qvalue; bad_value:list for
    junk between elements or after a weight."""
    f = make_fail('accept_encoding_list')
    if type(value) is not str:
        f('bad_type:text')
    if len(value) > VALUE_CAP:
        f('bad_value:field.length')
    spans = []
    _list(f, value, True, spans)
    out = []
    for start, stop in spans:
        semi = value.find(';', start, stop)
        if semi < 0:
            out.append((value[start:stop], None))
            continue
        name = value[start:semi].strip(' \t')
        qpos = _ows_end(value, semi + 1)
        out.append((name, value[qpos + 2:stop]))
    return tuple(out)


def _qzero(text):
    if text[0] == '0':
        for ch in text[1:]:
            if ch != '0' and ch != '.':
                return False
        return True
    return False


def coding_acceptable(coding, value):
    """Evaluate the Section 12.5.3 acceptability rules for one
    content coding against an Accept-Encoding field value: the asked
    coding is a caller supplied str token ('identity' asks the
    no-coding question; case-insensitive), and the value is a caller
    supplied str or None (None means the field is absent, so every
    valid coding is acceptable). Return True or False. OURS: '*'
    refused as the asked coding; a zero-entry value carries the
    empty-field meaning; duplicate names resolve to the last entry.
    Refusals: bad_type:coding or bad_type:value for a wrong type;
    bad_value:coding for '*' as the asked coding; plus the token,
    field.length, field.count, weight, qvalue and list codes."""
    f = make_fail('coding_acceptable')
    if type(coding) is not str:
        f('bad_type:coding')
    if len(coding) == 0 or len(coding) > TOKEN_CAP:
        f('bad_value:coding')
    pos = 0
    while pos < len(coding):
        if not _in(ord(coding[pos]), _TCHAR):
            f('bad_value:coding')
        pos += 1
    if coding == '*':
        f('bad_value:coding')
    if value is None:
        return True
    if type(value) is not str:
        f('bad_type:value')
    if len(value) > VALUE_CAP:
        f('bad_value:field.length')
    spans = []
    _list(f, value, True, spans)
    ask = _folded(coding)
    specific = {}
    star = None
    for start, stop in spans:
        semi = value.find(';', start, stop)
        if semi < 0:
            name = value[start:stop]
            qtext = None
        else:
            name = value[start:semi].strip(' \t')
            qpos = _ows_end(value, semi + 1)
            qtext = value[qpos + 2:stop]
        folded = _folded(name)
        zero = qtext is not None and _qzero(qtext)
        if folded == '*':
            star = not zero
        else:
            specific[folded] = not zero
    if ask in specific:
        return specific[ask]
    if star is not None:
        return star
    if ask == 'identity':
        return True
    return False
