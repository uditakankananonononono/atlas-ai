"""b1066 RFC 7578 multipart/form-data body framing (RFC 2046 boundary grammar, CRLF framing, form-data part headers), over caller bytes.

SCOPE: boundary_ok, pct_encode_param, pct_decode_param, parse_form_data and serialize_form_data over exact bytes and str values: the framing of one multipart/form-data body and the Content-Disposition and Content-Type header fields of its parts. No file IO, no retrieval, no network.
RFC 7578 and RFC 2046 quotes (verbatim):
Q1| Each part MUST contain a Content-Disposition header field [RFC2183] where the disposition type is "form-data".
Q2| The Content-Disposition header field MUST also contain an additional parameter of "name"
Q3| NOTE: The encoding method described in [RFC5987], which would add a "filename*" parameter to the Content-Disposition header field, MUST NOT be used.
Q4| Other header fields MUST NOT be included and MUST be ignored.
Q5| Form parts with identical field names MUST NOT be coalesced.
Q6| This use is deprecated for use in contexts that support binary data such as HTTP.
Q7| boundary := 0*69<bchars> bcharsnospace
Q8| bchars := bcharsnospace / " "
Q9| dash-boundary := "--" boundary
Q10| delimiter := CRLF dash-boundary
Q11| close-delimiter := delimiter "--"
Q12| encapsulation := delimiter transport-padding CRLF body-part
Q13| multipart-body := [preamble CRLF] dash-boundary transport-padding CRLF body-part *encapsulation close-delimiter transport-padding [CRLF epilogue]
OURS (not RFC text): caps checked before any scan or build: body 262144 bytes, 64 parts, boundary input 256 characters, text 255 characters, a parameter value 3072 characters, a header line 8192 bytes, 8 header fields per part, a content type 255 characters; refusals are ValueError P235:<fn>:<code>; a boundary is 1 to 70 characters of bchars and does not end in a space; the first dash-boundary is accepted at offset 0 or after a CRLF (preamble ignored, the tolerant reading of the held record on RFC 2046 section 5.1.1), a delimiter occurrence (CRLF, two hyphens, the boundary) that is not followed by transport padding and CRLF, or by two hyphens, is refused instead of being treated as part content, at least one part is required, and anything after the close delimiter and its padding must start with CRLF (the epilogue is ignored); a part is header lines, an empty line and content, or header lines alone, or an empty line and content (then no Content-Disposition, refused); header lines are US-ASCII with no folding, a token name and a colon; Content-Disposition must occur exactly once with type form-data (any case) and quoted-string parameters name (required) and filename (optional) without backslash escapes, each at most once, a filename* parameter and any other parameter are refused (name and filename match is case-insensitive); Content-Type may occur once and must be a token/token media type optionally followed by a semicolon and printable US-ASCII; every other header field, including Content-Transfer-Encoding, is ignored and never decoded; parse_form_data returns a tuple of (name, filename or None, content_type or None, data) with name and filename as written between the quotes, never percent-decoded; serialize_form_data writes each name and filename through pct_encode_param (UTF-8 bytes outside A-Z a-z 0-9 - . _ ~ as uppercase %HH), writes Content-Disposition then Content-Type, never a Content-Transfer-Encoding, starts with the first dash-boundary and ends with the close delimiter and CRLF, refuses data that holds the delimiter, and its output parses back to the same parts up to percent-encoding of name and filename (exact only for A-Z a-z 0-9 - . _ ~); pct_decode_param takes ASCII 0x20 to 0x7e where a percent sign must be followed by two hex digits and the bytes must be strict UTF-8.
parse_form_data(body, boundary) refuses with bad_type:body, bad_value:body.length, bad_type:boundary, bad_value:boundary.length, boundary.syntax, body.start, body.delimiter, body.close, body.unterminated, body.parts, body.empty, part.header.count, part.header.length, part.header.fold, part.header.chars, part.header.syntax, part.disposition.duplicate, part.disposition.syntax, part.disposition.type, part.disposition.filename_star, part.disposition.length, part.disposition.param, part.disposition.name, part.content_type.duplicate, part.content_type.syntax or part.disposition.missing.
serialize_form_data(parts, boundary) refuses with bad_type:parts, bad_value:parts.length, the boundary codes, bad_type:part, bad_type and bad_value .length of part.name, part.filename, part.content_type and part.data, bad_value:part.name.encode, part.filename.encode, part.content_type.syntax, body.delimiter or body.length.
NOT_CLAIMED: HTML form encoding, charset handling and _charset_, file name sanitising, nested multipart/mixed, the outer Content-Type header, quoted-printable or any Content-Transfer-Encoding decoding, RFC 2231 and RFC 5987 parameters (b1062 is the ext-value unit and is not used here), and every record on rfc-editor.org/errata/rfc7578 and rfc-editor.org/errata/rfc2046 beyond those named here.
ERRATA (fetched 13:26 on the day of the rev1 build from the RFC Editor errata.json): RFC 7578 EID 4676 Verified Technical section 4.6, EID 5616 Reported Technical section 4.5, EID 7385 Reported Technical section 4.5 and EID 9032 Reported Technical section 5.1.1; RFC 2046 EID 507 Verified Technical section 5.1.5, EID 508 Verified Technical section Appendix A, EID 509 Verified Editorial section 9, EID 510 Verified Editorial section 5.1.5, EID 511 Verified Editorial section 3, EID 588 Verified Technical section 5.2.2.2, EID 589 Verified Technical section 5.2.3.7, EID 4609 Held for Document Update Editorial section 3, EID 6582 Verified Editorial section 4.1.4, EID 6583 Rejected Editorial section 5.1.2, EID 6776 Held for Document Update Technical section 5.1.1, EID 6800 Verified Technical section 5.1.4, EID 7341 Verified Editorial section 5.2.3.7 and EID 8667 Reported Technical section 4.1.2. No erratum text is applied as RFC text here; the quotes above are from the published RFC text.
ADJACENT: b1062 (RFC 8187 ext-value, which RFC 7578 says must not be used for filename) and b1021 (Range multipart/byteranges) are neighbouring units.
CLAIMS is False.
"""
CLAIMS = False
SCOPE = 'RFC 7578 multipart/form-data framing and part headers'
NOT_CLAIMED = ('html-forms', 'charset', 'filename-sanitising', 'multipart-mixed', 'outer-content-type', 'transfer-encoding', 'rfc2231', 'errata')
ADJACENT = ('b1021', 'b1062')
MAX_BODY = 262144
MAX_PARTS = 64
MAX_BOUNDARY_INPUT = 256
MAX_TEXT = 255
MAX_PARAM = 3072
MAX_LINE = 8192
MAX_HEADERS = 8
MAX_CT = 255
_REG = 'app.modules.instinct_doc.p235_concepts_registry'
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != _REG:
        raise
    from importlib.util import find_spec as _find_spec
    if _find_spec(_REG) is not None:
        raise

    def make_fail(name):

        def fail(code):
            raise ValueError('P235:%s:%s' % (name, code))
        return fail
_STR = str
_BYTES = bytes
_LIST = list
_TUPLE = tuple
_ALNUM = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
_BCHARS = _ALNUM + "'()+_,-./:=? "
_UNRES = _ALNUM + '-._~'
_TOKEN = _ALNUM + "!#$%&'*+-.^_`|~"
_HEX = '0123456789abcdefABCDEF'
_UPPER_HEX = '0123456789ABCDEF'
_CRLF = b'\r\n'

class _Soft(Exception):
    pass

def _soft(code):
    raise _Soft(code)

def _arg(fail, label, value, cap):
    if type(value) is not _STR:
        fail('bad_type:' + label)
    if len(value) > cap:
        fail('bad_value:%s.length' % label)

def _barg(fail, label, value, cap):
    if type(value) is not _BYTES:
        fail('bad_type:' + label)
    if len(value) > cap:
        fail('bad_value:%s.length' % label)

def _all_in(s, allowed):
    for ch in s:
        if ch not in allowed:
            return False
    return True

def _boundary(fail, boundary):
    if len(boundary) == 0 or len(boundary) > 70 or (not _all_in(boundary, _BCHARS)) or (boundary[-1] == ' '):
        fail('bad_value:boundary.syntax')

def _enc(octets):
    out = []
    for b in octets:
        ch = chr(b)
        if ch in _UNRES:
            out.append(ch)
        else:
            out.append('%' + _UPPER_HEX[b >> 4] + _UPPER_HEX[b & 15])
    return ''.join(out)

def _ct_ok(value):
    if len(value) > MAX_CT:
        return False
    i = value.find('/')
    if i <= 0 or not _all_in(value[:i], _TOKEN):
        return False
    k = i + 1
    while k < len(value) and value[k] in _TOKEN:
        k += 1
    if k == i + 1:
        return False
    rest = value[k:]
    if rest == '':
        return True
    r = rest.lstrip(' \t')
    if r[:1] != ';' or rest[-1] in ' \t':
        return False
    for ch in r:
        if ord(ch) < 32 or ord(ch) > 126:
            return False
    return True

def _disp(fail, value):
    n = len(value)
    head = value.partition(';')[0]
    typ = head.rstrip(' \t')
    if typ == '' or not _all_in(typ, _TOKEN):
        fail('bad_value:part.disposition.syntax')
    if typ.lower() != 'form-data':
        fail('bad_value:part.disposition.type')
    name = None
    filename = None
    i = len(head)
    while i < n:
        i += 1
        while i < n and value[i] in ' \t':
            i += 1
        k = i
        while k < n and value[k] in _TOKEN:
            k += 1
        key = value[i:k]
        if key == '':
            fail('bad_value:part.disposition.syntax')
        while k < n and value[k] in ' \t':
            k += 1
        if k >= n or value[k] != '=':
            fail('bad_value:part.disposition.syntax')
        k += 1
        while k < n and value[k] in ' \t':
            k += 1
        if k >= n or value[k] != '"':
            fail('bad_value:part.disposition.syntax')
        k += 1
        start = k
        while k < n and value[k] != '"':
            if value[k] == '\t' or value[k] == '\\':
                fail('bad_value:part.disposition.syntax')
            k += 1
        if k >= n:
            fail('bad_value:part.disposition.syntax')
        val = value[start:k]
        i = k + 1
        while i < n and value[i] in ' \t':
            i += 1
        if i < n and value[i] != ';':
            fail('bad_value:part.disposition.syntax')
        low = key.lower()
        if low == 'filename*':
            fail('bad_value:part.disposition.filename_star')
        if len(val) > MAX_PARAM:
            fail('bad_value:part.disposition.length')
        if low == 'name' and name is None:
            name = val
        elif low == 'filename' and filename is None:
            filename = val
        else:
            fail('bad_value:part.disposition.param')
    if name is None:
        fail('bad_value:part.disposition.name')
    return (name, filename)

def _part(fail, seg):
    if seg[:2] == _CRLF:
        fail('bad_value:part.disposition.missing')
    head, _sep, data = seg.partition(b'\r\n\r\n')
    disp = None
    ctype = None
    if head != b'':
        if head.count(_CRLF) + 1 > MAX_HEADERS:
            fail('bad_value:part.header.count')
        for line in head.split(_CRLF):
            if len(line) > MAX_LINE:
                fail('bad_value:part.header.length')
            if line[:1] == b' ' or line[:1] == b'\t':
                fail('bad_value:part.header.fold')
            for b in line:
                if b > 126 or (b < 32 and b != 9):
                    fail('bad_value:part.header.chars')
            idx = line.find(b':')
            if idx <= 0:
                fail('bad_value:part.header.syntax')
            hname = line[:idx].decode('ascii')
            if not _all_in(hname, _TOKEN):
                fail('bad_value:part.header.syntax')
            hvalue = line[idx + 1:].decode('ascii').strip(' \t')
            low = hname.lower()
            if low == 'content-disposition':
                if disp is not None:
                    fail('bad_value:part.disposition.duplicate')
                disp = _disp(fail, hvalue)
            elif low == 'content-type':
                if ctype is not None:
                    fail('bad_value:part.content_type.duplicate')
                if not _ct_ok(hvalue):
                    fail('bad_value:part.content_type.syntax')
                ctype = hvalue
    if disp is None:
        fail('bad_value:part.disposition.missing')
    return (disp[0], disp[1], ctype, data)

def _frame(fail, body, bb):
    buf = _CRLF + body
    delim = b'\r\n--' + bb
    dl = len(delim)
    segs = []
    cur = buf.find(delim)
    if cur < 0:
        fail('bad_value:body.start')
    while True:
        after = cur + dl
        if buf[after:after + 2] == b'--':
            k = after + 2
            while k < len(buf) and (buf[k] == 32 or buf[k] == 9):
                k += 1
            if k < len(buf) and buf[k:k + 2] != _CRLF:
                fail('bad_value:body.close')
            if len(segs) == 0:
                fail('bad_value:body.empty')
            return segs
        k = after
        while k < len(buf) and (buf[k] == 32 or buf[k] == 9):
            k += 1
        if buf[k:k + 2] != _CRLF:
            fail('bad_value:body.delimiter')
        start = k + 2
        nxt = buf.find(delim, start)
        if nxt == -1:
            fail('bad_value:body.unterminated')
        if len(segs) >= MAX_PARTS:
            fail('bad_value:body.parts')
        segs.append(buf[start:nxt])
        cur = nxt

def boundary_ok(boundary):
    fail = make_fail('boundary_ok')
    _arg(fail, 'boundary', boundary, MAX_BOUNDARY_INPUT)
    try:
        _boundary(_soft, boundary)
    except _Soft:
        return False
    return True

def pct_encode_param(text):
    fail = make_fail('pct_encode_param')
    _arg(fail, 'text', text, MAX_TEXT)
    try:
        octets = text.encode('utf-8')
    except UnicodeEncodeError:
        fail('bad_value:text.encode')
    return _enc(octets)

def pct_decode_param(value):
    fail = make_fail('pct_decode_param')
    _arg(fail, 'value', value, MAX_PARAM)
    out = bytearray()
    i = 0
    n = len(value)
    while i < n:
        ch = value[i]
        if ch == '%':
            if i + 2 > n - 1 or value[i + 1] not in _HEX or value[i + 2] not in _HEX:
                fail('bad_value:value.pct')
            out.append(int(value[i + 1:i + 3], 16))
            i += 3
        elif ord(ch) < 32 or ord(ch) > 126:
            fail('bad_value:value.chars')
        else:
            out.append(ord(ch))
            i += 1
    try:
        return bytes(out).decode('utf-8')
    except UnicodeDecodeError:
        fail('bad_value:value.decode')

def parse_form_data(body, boundary):
    fail = make_fail('parse_form_data')
    _barg(fail, 'body', body, MAX_BODY)
    _arg(fail, 'boundary', boundary, MAX_BOUNDARY_INPUT)
    _boundary(fail, boundary)
    segs = _frame(fail, body, boundary.encode('ascii'))
    out = []
    for seg in segs:
        out.append(_part(fail, seg))
    return tuple(out)

def serialize_form_data(parts, boundary):
    fail = make_fail('serialize_form_data')
    if type(parts) is not _LIST and type(parts) is not _TUPLE:
        fail('bad_type:parts')
    if len(parts) == 0 or len(parts) > MAX_PARTS:
        fail('bad_value:parts.length')
    _arg(fail, 'boundary', boundary, MAX_BOUNDARY_INPUT)
    _boundary(fail, boundary)
    bb = boundary.encode('ascii')
    delim = b'\r\n--' + bb
    dash = b'--' + bb
    chunks = []
    total = len(dash) + 4
    for part in parts:
        if type(part) is not _TUPLE or len(part) != 4:
            fail('bad_type:part')
        name = part[0]
        filename = part[1]
        ctype = part[2]
        data = part[3]
        _arg(fail, 'part.name', name, MAX_TEXT)
        if filename is not None:
            _arg(fail, 'part.filename', filename, MAX_TEXT)
        if ctype is not None:
            _arg(fail, 'part.content_type', ctype, MAX_CT)
        _barg(fail, 'part.data', data, MAX_BODY)
        try:
            ename = _enc(name.encode('utf-8'))
        except UnicodeEncodeError:
            fail('bad_value:part.name.encode')
        head = 'Content-Disposition: form-data; name="' + ename + '"'
        if filename is not None:
            try:
                efile = _enc(filename.encode('utf-8'))
            except UnicodeEncodeError:
                fail('bad_value:part.filename.encode')
            head += '; filename="' + efile + '"'
        if ctype is not None:
            if not _ct_ok(ctype):
                fail('bad_value:part.content_type.syntax')
            head += '\r\nContent-Type: ' + ctype
        if (_CRLF + data).find(delim) >= 0:
            fail('bad_value:body.delimiter')
        hb = head.encode('ascii')
        total += len(dash) + 2 + len(hb) + 4 + len(data) + 2
        if total > MAX_BODY:
            fail('bad_value:body.length')
        chunks.append(dash + _CRLF + hb + b'\r\n\r\n' + data + _CRLF)
    chunks.append(dash + b'--' + _CRLF)
    return b''.join(chunks)