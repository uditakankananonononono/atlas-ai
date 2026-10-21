"""b1230 RFC 6874 section 2: IPv6 zone identifiers in address literals.

Source: RFC 6874 (Carpenter, Cheshire, Hinden, February 2013), section 2
(Specification). In a URI an IPv6 address literal sits between square
brackets, and "This document specifies how a <zone_id> can be appended to
the address." Because a bare percent sign must be escaped in a URI, the
zone separator is the three character sequence %25, so the scoped address
fe80::a%en1 appears as [fe80::a%25en1]. The grammar keeps the address
rule unchanged: "the existing syntax of IPv6address is retained, and a
zone identifier may be added optionally to any literal address." The two
rules added are 'ZoneID = 1*( unreserved / pct-encoded )' and
'IPv6addrz = IPv6address "%25" ZoneID', with unreserved and pct-encoded
imported from the URI syntax: unreserved is the 66 ASCII letters, digits
and the four characters - . _ ~, and a pct-encoded triplet is a percent
sign followed by two hexadecimal digits, accepted in either case and
emitted uppercase. On scope: "URIs including a ZoneID are to be
interpreted only in the context of the host at which they originate,
since the ZoneID is of local significance only."
Errata: five exist for RFC 6874 in the errata data used; all are named
here. 3630 and 3632 (Rejected, Technical, section 3) and 3631 and 3633
(Rejected, Technical, section 4) concern browser handling and
intermediary removal of zone identifiers; sections 3 and 4 are not
implemented, so these are outside the implemented section and none is
applied. 8552 (Verified, Technical, GLOBAL) records that the Updates
relationship to the URI syntax was found unimplementable and points to
RFC 9844; it corrects no section 2 grammar text, so the implemented
syntax stands as published and the erratum is documented but not applied
to the grammar.
OURS design choices (not sourced from the RFC): the IPv6 address part is
an opaque token here (nonempty, ASCII, no percent sign and no square
brackets, at most ADDR_MAX characters); its validation is owned by the
IPv6 text form sibling modules and is NOT implemented. ZONE_MAX 255 and
TEXT_MAX 1024 are implementation bounds; the RFC sets no length limit on
a ZoneID. encode_zone_id percent-encodes non-ASCII raw characters as
UTF-8 byte triplets and decode_zone_id is a byte level decode, so exact
round trips are pinned for ASCII raw text only. The P235 error codes and
their check order are ours. SOURCED: the %25 separator, the ZoneID
grammar with at least one element, the unreserved set of 66 characters,
the pct-encoded triplet of a percent sign and two hexadecimal digits, the
square bracket delimiters of the literal form, and ADDR_MAX 45, the
length of the longest textual address form.
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

SCOPE = 'RFC 6874 section 2 IPv6 zone identifier syntax in address literals'
NOT_CLAIMED = ('IPv6 address text validation (sibling modules)', 'IPvFuture literals', 'URI parsing outside the bracketed literal', 'zone identifier semantics or interface lookup', 'web browser handling (section 3)')
ADJACENT = ('RFC 3986 URI syntax (unreserved and pct-encoded)', 'RFC 4007 IPv6 scoped address architecture', 'RFC 5952 IPv6 text representation (sibling module)', 'RFC 4291 IPv6 addressing', 'RFC 9844 successor work named by erratum 8552')
CLAIMS = False

ZONE_MIN = 1
ZONE_MAX = 255
ADDR_MIN = 1
ADDR_MAX = 45
TEXT_MAX = 1024
UNRESERVED = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'


def _text(f, text):
    if type(text) is not str:
        f('text-type')


def _unres(c):
    return c in UNRESERVED


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


def _zone_code(t):
    if len(t) < ZONE_MIN:
        return 'zone-empty'
    if len(t) > ZONE_MAX:
        return 'zone-length'
    skip = 0
    for c in t:
        if skip:
            if _hexval(c) is None:
                return 'zone-pc'
            skip -= 1
            continue
        if c == '%':
            skip = 2
            continue
        if not _unres(c):
            return 'zone-char'
    return 'zone-pc' if skip else None


def _addr_code(t):
    if len(t) < ADDR_MIN:
        return 'addr-empty'
    if len(t) > ADDR_MAX:
        return 'addr-length'
    for c in t:
        if ord(c) > 127:
            return 'addr-ascii'
    found = None
    for c in t:
        if c == '[' or c == ']':
            found = 'addr-bracket'
            break
        if c == '%':
            found = 'addr-percent'
            break
    return found


def _addrz_code(text):
    if text == '':
        return 'empty', None
    if len(text) > TEXT_MAX:
        return 'text-length', None
    p = text.find('%')
    if p < 0:
        return 'no-separator', None
    if text[p:p + 3] != '%25':
        return 'bad-separator', None
    addr = text[:p]
    zone = text[p + 3:]
    acode = _addr_code(addr)
    if acode is not None:
        return acode, None
    zcode = _zone_code(zone)
    if zcode is not None:
        return zcode, None
    return None, (addr, zone)


def _literal_code(text):
    if text == '':
        return 'empty', None
    if len(text) > TEXT_MAX:
        return 'text-length', None
    if text[0] != '[':
        return 'open-bracket', None
    if text[-1] != ']':
        return 'close-bracket', None
    return _addrz_code(text[1:-1])


def is_zone_id(text):
    f = make_fail('is_zone_id')
    _text(f, text)
    return _zone_code(text) is None


def encode_zone_id(raw):
    f = make_fail('encode_zone_id')
    if type(raw) is not str:
        f('raw-type')
    if len(raw) < ZONE_MIN:
        f('raw-empty')
    if len(raw) > ZONE_MAX:
        f('raw-length')
    out = []
    for c in raw:
        if _unres(c):
            out.append(c)
            continue
        for b in c.encode('utf-8'):
            out.append('%%%02X' % b)
    zone = ''.join(out)
    if len(zone) > ZONE_MAX:
        f('zone-length')
    return zone


def decode_zone_id(zone):
    f = make_fail('decode_zone_id')
    if type(zone) is not str:
        f('zone-type')
    zcode = _zone_code(zone)
    if zcode is not None:
        f(zcode)
    out = []
    i = 0
    n = len(zone)
    while i < n:
        c = zone[i]
        if c == '%':
            out.append(chr(_hexval(zone[i + 1]) * 16 + _hexval(zone[i + 2])))
            i += 3
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def split_addrz(text):
    f = make_fail('split_addrz')
    _text(f, text)
    code, parts = _addrz_code(text)
    if code is not None:
        f(code)
    return parts


def is_addrz(text):
    f = make_fail('is_addrz')
    _text(f, text)
    code, parts = _addrz_code(text)
    return code is None


def format_addrz(address, zone_id):
    f = make_fail('format_addrz')
    if type(address) is not str:
        f('address-type')
    acode = _addr_code(address)
    if acode is not None:
        f(acode)
    if type(zone_id) is not str:
        f('zone-type')
    zcode = _zone_code(zone_id)
    if zcode is not None:
        f(zcode)
    return address + '%25' + zone_id


def split_literal(text):
    f = make_fail('split_literal')
    _text(f, text)
    code, parts = _literal_code(text)
    if code is not None:
        f(code)
    return parts


def is_literal(text):
    f = make_fail('is_literal')
    _text(f, text)
    code, parts = _literal_code(text)
    return code is None
