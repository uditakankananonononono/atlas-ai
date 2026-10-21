"""b1192 RFC 1035 section 2.3.1 preferred domain name syntax and size limits.

Source: RFC 1035 (Mockapetris, November 1987), section 2.3.1 (Preferred name
syntax) with the size limits of sections 2.3.4 and 3.1. Only the TEXT form of
domain names is handled, never the wire form. The RFC says of labels: "They
must start with a letter, end with a letter or digit, and have as interior
characters only letters, digits, and hyphen." and "Labels must be 63
characters or less." On case: "That is, two names with the same spelling but
different case are to be treated as if identical." and "Name servers and
resolvers must compare labels in a case-insensitive manner (i.e., A=a),
assuming ASCII with zero parity." The size table gives "names 255 octets or
less"; section 3.1 makes that the wire length, label octets plus label length
octets plus the zero root octet, so a text name of n labels and n minus 1
dots is at most 253 characters.
Twenty-nine errata exist for RFC 1035 in the errata data used; one touches a
section implemented here: 7424 (Verified, Editorial, section 2.3.1, a blank
line inside a sentence): read, NOT applied, no rule changes. 6264 (Verified,
Editorial, section 2.2, a grammar typo) is the only other erratum in section
2: read, NOT applied.
No erratum changes the preferred name syntax, the size limits, or the case
rules implemented here.
OURS design choices (not sourced from the RFC): the empty string stands for
the root domain (the blank alternative of the domain rule); a trailing dot is
refused as an empty label; every function validates its arguments before
computing; is_label and is_name answer False for any syntactically bad string
and raise only on a non-string argument; the P235 error codes and their check
order; the 253 character text limit derived from the sourced 255 octet wire
limit. SOURCED: the letter start, the letter or digit end, the letter digit
hyphen interior, the 63 character label limit, the 255 octet name limit, and
ASCII case-insensitive comparison with all other codes matching exactly.
The digit-start relaxation of RFC 1123 and the any-8-bit labels of section
3.1 are ADJACENT and not implemented here.
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

SCOPE = 'RFC 1035 section 2.3.1 preferred domain name syntax and size limits'
NOT_CLAIMED = ('the wire format of section 3.1', 'labels outside the preferred syntax', 'the RFC 1123 digit start relaxation', 'name resolution', 'master file syntax')
ADJACENT = ('RFC 1034 domain concepts', 'RFC 1123 host name requirements', 'RFC 1035 section 3.1 wire form')
CLAIMS = False

LABEL_MAX = 63
WIRE_MAX = 255
TEXT_MAX = 253


def _letter(c):
    o = ord(c)
    return 97 <= o <= 122 or 65 <= o <= 90


def _letdig(c):
    o = ord(c)
    return 97 <= o <= 122 or 65 <= o <= 90 or 48 <= o <= 57


def _ldh(c):
    return _letdig(c) or c == '-'


def _label_ok(text):
    if text == '' or len(text) > LABEL_MAX:
        return False
    if not _letter(text[0]):
        return False
    if not _letdig(text[-1]):
        return False
    for c in text:
        if not _ldh(c):
            return False
    return True


def is_label(text):
    f = make_fail('is_label')
    if type(text) is not str:
        f('text-type')
    return _label_ok(text)


def _parse(text):
    if len(text) > TEXT_MAX:
        return 'name-length', None
    if text == '':
        return None, ()
    labels = text.split('.')
    for lab in labels:
        if lab == '':
            return 'label-empty', None
        if len(lab) > LABEL_MAX:
            return 'label-length', None
        if not _label_ok(lab):
            return 'label-invalid', None
    return None, tuple(labels)


def _text(f, text):
    if type(text) is not str:
        f('text-type')


def is_name(text):
    f = make_fail('is_name')
    _text(f, text)
    code, labels = _parse(text)
    return code is None


def split_name(text):
    f = make_fail('split_name')
    _text(f, text)
    code, labels = _parse(text)
    if code is not None:
        f(code)
    return labels


def canonical(text):
    f = make_fail('canonical')
    _text(f, text)
    code, labels = _parse(text)
    if code is not None:
        f(code)
    return '.'.join(labels).lower()


def name_equal(a, b):
    f = make_fail('name_equal')
    _text(f, a)
    code_a, la = _parse(a)
    if code_a is not None:
        f(code_a)
    _text(f, b)
    code_b, lb = _parse(b)
    if code_b is not None:
        f(code_b)
    return tuple(x.lower() for x in la) == tuple(x.lower() for x in lb)
