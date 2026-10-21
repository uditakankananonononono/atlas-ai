"""b1229 RFC 4514 (LDAP string representation of Distinguished Names): the section 3 grammar, the section 2.3 and 2.4 conversion rules, over caller text and caller tuples only.
dn_ok(text) -> bool: True when the exact str is a distinguishedName of section 3 (zero or more RDNs, so the empty str is a DN). attribute_type_ok(text) -> bool: descr or numericoid (RFC 4512 section 1.4, copied here). A non-str raises bad_type:text and a str longer than 1024 characters raises bad_value:text.length before any scan. Other bad text returns False. Text is never trimmed and never case folded.
parse_dn(text) -> tuple of RDNs in the order written (section 2.1 writes the RDNSequence backwards; this module does not reverse), each RDN a tuple of AVAs, each AVA a tuple (type, kind, value): type is the text as given, kind is 'string' or 'hex', value is bytes: the UTF-8 octets after each pair is replaced (section 3) for 'string', the BER octets of the hexpairs for 'hex'. Bad text raises bad_value:text.syntax.
format_dn(rdns) -> str: the section 2 conversion of a parse-shaped tuple. A 'string' value must be strict UTF-8; ' ' or '#' at the start, ' ' at the end, '"' '+' ',' ';' '<' '>' '\' anywhere are written backslash then the character, U+0000 is written \00, everything else is written as is (OURS: the one-character backslash alternative of section 2.4). A 'hex' value is written '#' and its octets as uppercase hexpairs and may not be empty. Section 2.4 requires the '#' form for a numericoid type, so format_dn refuses a 'string' value on a numericoid type (bad_value:rdns.kind) although parse_dn accepts it (section 3 allows it). Empty RDNs are refused.
Limits (OURS): text and formatted text are at most 1024 characters; rdns and each RDN hold at most 1024 items, each type at most 1024 characters and each value at most 4096 octets (4 octets for each of 1024 characters), all checked before the items are walked, so every parse_dn result is within the caps format_dn checks.
Errors: format_dn checks rdns type and count, then each RDN (type, count, not empty), then each AVA (type, size 3), then type, kind, value in that order, and last the formatted length.
Errata on RFC 4514 (2 records on errata.json): EID 73 Held for Document Update Editorial section 4 and EID 7229 Verified Editorial section 2.4 (both wording only, no effect). RFC 4512, whose descr, numericoid and UTF-8 productions this module copies, has 9 errata records (EID 74 2281 5261 7224 7225 7226 7227 7228 7896; 7896 is Reported Technical on DITStructureRule syntax, which this module does not use). RFC 4234, the ABNF of both, has 7 errata records (EID 159 160 777 778 783 866 2625). RFC 2253 (obsolete, 1 record: EID 2664) is not used. None is applied.
"""
from importlib.util import find_spec
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:
        raise

    def make_fail(name):
        """Fallback used only when the shared registry module is absent: return a failer for the named function."""
        def fail(code):
            """Raise ValueError with the P235 name and code."""
            raise ValueError('P235:%s:%s' % (name, code))
        return fail
CLAIMS = False
SCOPE = 'PARTIAL: RFC 4514 section 3 grammar and section 2 conversion of Distinguished Names over caller text and tuples, no attribute registry and no value syntax checks'
NOT_CLAIMED = ('attribute type registry or short name table', 'BER validity of hex values', 'distinguishedNameMatch comparison', 'RFC 2253 legacy forms', 'production readiness')
ADJACENT = ('RFC 3629 UTF-8 units', 'RFC 4515 filter escaping', 'RFC 4516 LDAP URL')
MAX_DN = 1024
MAX_VALUE = 4096
_ALPHA = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
_DIGIT = '0123456789'
_KEYCHARS = _ALPHA + _DIGIT + '-'
_HEXVAL = {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14, 'F': 15, 'a': 10, 'b': 11, 'c': 12, 'd': 13, 'e': 14, 'f': 15}
_HEXUP = '0123456789ABCDEF'
_PAIRSPECIAL = '\\"+,;<> #='
_ESCAPED = '"+,;<>\\'
_LUTF1 = "\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f!$%&'()*-./0123456789:=?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_`abcdefghijklmnopqrstuvwxyz{|}~\x7f"
_TUTF1 = "\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f!#$%&'()*-./0123456789:=?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_`abcdefghijklmnopqrstuvwxyz{|}~\x7f"
_SUTF1 = "\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f !#$%&'()*-./0123456789:=?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_`abcdefghijklmnopqrstuvwxyz{|}~\x7f"


def _all_in(text, allowed):
    """True when every character of the exact str is in allowed (an empty str is True)."""
    for ch in text:
        if ch not in allowed:
            return False
    return True


def _is_utfmb(ch):
    """True for one non-ASCII character that UTF-8 can carry (section 3 UTFMB): not a surrogate."""
    return ch >= '\x80' and not '\ud800' <= ch < '\ue000'


def _is_descr(text):
    """RFC 4512 descr: a letter then letters, digits and hyphens."""
    return text != '' and text[0] in _ALPHA and _all_in(text, _KEYCHARS)


def _is_numericoid(text):
    """RFC 4512 numericoid: two or more numbers (0 or no leading zero) separated by dots."""
    parts = text.split('.')
    if len(parts) < 2:
        return False
    for part in parts:
        if part == '' or not _all_in(part, _DIGIT):
            return False
        if len(part) > 1 and part[0] == '0':
            return False
    return True


def _type_ok(text):
    """The attributeType production: descr or numericoid."""
    return _is_descr(text) or _is_numericoid(text)


def _hexbytes(chars):
    """Octets of an even-length str of hex digits (already checked)."""
    out = b''
    for i in range(0, len(chars), 2):
        out += bytes((_HEXVAL[chars[i]] * 16 + _HEXVAL[chars[i + 1]],))
    return out


def _string(text):
    """The string production on text with pairs: return the octets, or None when it does not match."""
    units = []
    skip = 0
    n = len(text)
    for i in range(n):
        if skip > 0:
            skip -= 1
            continue
        ch = text[i]
        if ch != '\\':
            units.append((ch, None))
            continue
        if i + 1 >= n:
            return None
        nxt = text[i + 1]
        if nxt in _PAIRSPECIAL:
            units.append((None, nxt.encode('utf-8')))
            skip = 1
        elif nxt in _HEXVAL:
            if i + 2 >= n or text[i + 2] not in _HEXVAL:
                return None
            units.append((None, _hexbytes(text[i + 1:i + 3])))
            skip = 2
        else:
            return None
    out = b''
    last = len(units) - 1
    for k in range(len(units)):
        ch, octets = units[k]
        if ch is None:
            out += octets
            continue
        if k == 0:
            ok = ch in _LUTF1
        elif k == last:
            ok = ch in _TUTF1
        else:
            ok = ch in _SUTF1
        if not ok and not _is_utfmb(ch):
            return None
        out += ch.encode('utf-8')
    return out


def _value(text):
    """The attributeValue production: return (kind, octets) or None."""
    if text[:1] == '#':
        body = text[1:]
        if body == '' or len(body) % 2 != 0 or not _all_in(body, _HEXVAL):
            return None
        return ('hex', _hexbytes(body))
    octets = _string(text)
    if octets is None:
        return None
    return ('string', octets)


def _ava(text):
    """The attributeTypeAndValue production: return (type, kind, octets) or None."""
    parts = text.split('=', 1)
    if len(parts) != 2 or not _type_ok(parts[0]):
        return None
    value = _value(parts[1])
    if value is None:
        return None
    return (parts[0], value[0], value[1])


def _parse(text):
    """The distinguishedName production on an exact str already length checked: return the RDN tuple or None."""
    if text == '':
        return ()
    cuts = []
    skip = False
    for i in range(len(text)):
        if skip:
            skip = False
            continue
        ch = text[i]
        if ch == '\\':
            skip = True
        elif ch == ',' or ch == '+':
            cuts.append(i)
    rdns = []
    rdn = []
    start = 0
    for i in cuts + [len(text)]:
        ava = _ava(text[start:i])
        if ava is None:
            return None
        rdn.append(ava)
        if i == len(text) or text[i] == ',':
            rdns.append(tuple(rdn))
            rdn = []
        start = i + 1
    return tuple(rdns)


def _arg(fail, text):
    """Check the exact type and the length cap of a text argument."""
    if type(text) is not str:
        fail('bad_type:text')
    if len(text) > MAX_DN:
        fail('bad_value:text.length')


def dn_ok(text):
    """True when the exact str is a distinguishedName (RFC 4514 section 3); the empty str is one."""
    fail = make_fail('dn_ok')
    _arg(fail, text)
    return _parse(text) is not None


def attribute_type_ok(text):
    """True when the exact str is an attributeType: a descr or a numericoid."""
    fail = make_fail('attribute_type_ok')
    _arg(fail, text)
    return _type_ok(text)


def parse_dn(text):
    """Return the RDN tuples of a distinguishedName in the order written; refuse any other text."""
    fail = make_fail('parse_dn')
    _arg(fail, text)
    rdns = _parse(text)
    if rdns is None:
        fail('bad_value:text.syntax')
    return rdns


def _escape(text):
    """Section 2.4 escaping of a decoded value, using the backslash alternative."""
    out = []
    last = len(text) - 1
    for k in range(len(text)):
        ch = text[k]
        if ch == '\x00':
            out.append('\\00')
        elif ch in _ESCAPED:
            out.append('\\' + ch)
        elif k == 0 and (ch == ' ' or ch == '#'):
            out.append('\\' + ch)
        elif k == last and ch == ' ':
            out.append('\\ ')
        else:
            out.append(ch)
    return ''.join(out)


def _hexup(octets):
    """Uppercase hexpairs of the octets."""
    out = []
    for n in octets:
        out.append(_HEXUP[n >> 4] + _HEXUP[n & 15])
    return ''.join(out)


def _format_ava(fail, ava):
    """Check one AVA tuple and return its string encoding."""
    if type(ava) is not tuple:
        fail('bad_type:rdns.ava')
    if len(ava) != 3:
        fail('bad_value:rdns.ava')
    typ, kind, value = ava
    if type(typ) is not str:
        fail('bad_type:rdns.type')
    if len(typ) > MAX_DN:
        fail('bad_value:rdns.type.length')
    if not _type_ok(typ):
        fail('bad_value:rdns.type')
    if type(kind) is not str:
        fail('bad_type:rdns.kind')
    if kind != 'string' and kind != 'hex':
        fail('bad_value:rdns.kind')
    if kind == 'string' and _is_numericoid(typ):
        fail('bad_value:rdns.kind')
    if type(value) is not bytes:
        fail('bad_type:rdns.value')
    if len(value) > MAX_VALUE:
        fail('bad_value:rdns.value.length')
    if kind == 'hex':
        if len(value) == 0:
            fail('bad_value:rdns.value')
        return typ + '=#' + _hexup(value)
    try:
        decoded = value.decode('utf-8')
    except UnicodeDecodeError:
        fail('bad_value:rdns.value')
    return typ + '=' + _escape(decoded)


def format_dn(rdns):
    """Render a parse-shaped tuple of RDNs as a distinguishedName string (RFC 4514 section 2)."""
    fail = make_fail('format_dn')
    if type(rdns) is not tuple:
        fail('bad_type:rdns')
    if len(rdns) > MAX_DN:
        fail('bad_value:rdns.length')
    parts = []
    for rdn in rdns:
        if type(rdn) is not tuple:
            fail('bad_type:rdns.item')
        if len(rdn) > MAX_DN:
            fail('bad_value:rdns.item.length')
        if len(rdn) == 0:
            fail('bad_value:rdns.item')
        avas = []
        for ava in rdn:
            avas.append(_format_ava(fail, ava))
        parts.append('+'.join(avas))
    out = ','.join(parts)
    if len(out) > MAX_DN:
        fail('bad_value:dn.length')
    return out
