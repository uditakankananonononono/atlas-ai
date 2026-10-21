"""b1220 RFC 1123 section 2.1 host name syntax on the RFC 952 hostname grammar.

Source: RFC 1123 (Braden, October 1989), section 2.1 (Host Names and
Numbers), layered on the RFC 952 (October 1985) hostname grammar
(hname = name *(dot name); name = letter, then letters digits and hyphens,
ending letter or digit). RFC 1123 changes one rule: "the restriction on the
first character is relaxed to allow either a letter or a digit." On lengths:
"Host software MUST handle host names of up to 63 characters and SHOULD
handle host names of up to 255 characters." RFC 952 adds: "No distinction is
made between upper and lower case." The label character rules and the 63
character label limit are the RFC 1035 label grammar; see the sibling module
for RFC 1035, referenced here without any import.
The last-label rule: RFC 1123 says a valid host name can never have the
dotted-decimal form, "since at least the highest-level component label will
be alphabetic." Erratum 1081 (Rejected, Technical, section 2.1) proposed
weakening that to not all-numeric and was rejected; the implemented rule is
that the last label must not be all numeric, the task-scoped choice,
consistent with the informational statement in RFC 3696 section 2 and weaker
than the RFC text. Errata: fourteen exist for RFC 1123 in the errata data
used; the four touching section 2.1 are named here: 1081 and 1353 (both
Rejected, Technical, section 2.1), 1354 (Verified, Editorial, section 2.1, an
added citation to RFC 1034 section 3.5) and 8148 (Verified, Editorial,
section 2.1, a corrected cross reference); the two Verified errata change no
rule and are NOT applied. One erratum exists for RFC 952: 3584 (Verified,
Editorial, header text): read, NOT applied.
OURS design choices (not sourced from the RFCs): the empty string and a
trailing dot are refused; is_hlabel, is_hname and all_numeric answer False
for a bad string and raise only on a non-string argument; the RFC 952
policies (24 character table limit, the single character ban, the gateway and
TAC suffix conventions) are NOT implemented, being host table policy
superseded by the RFC 1123 lengths; the P235 error codes, their check order
(structural checks label by label, the last-label rule last), and the 63
character label limit taken from the referenced RFC 1035 grammar. SOURCED:
the digit-or-letter start (RFC 1123), the letter-or-digit end and the
letter-digit-hyphen interior (RFC 952), case-insensitive comparison (RFC
952), the 255 character host name length (RFC 1123), and the last label not
all numeric rule as scoped above.
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

SCOPE = 'RFC 1123 section 2.1 host name syntax on the RFC 952 hostname grammar'
NOT_CLAIMED = ('dotted-decimal IP address forms', 'RFC 952 host table policies', 'the single character name ban', 'name lookup or resolution', 'internationalized names')
ADJACENT = ('RFC 952 host table specification', 'RFC 1035 domain name syntax (sibling module)', 'RFC 1034 section 3.5 preferred name syntax', 'RFC 3696 application checks of domain names')
CLAIMS = False

HLABEL_MAX = 63
HNAME_MAX = 255


def _letter(c):
    o = ord(c)
    return 97 <= o <= 122 or 65 <= o <= 90


def _digit(c):
    o = ord(c)
    return 48 <= o <= 57


def _letdig(c):
    return _letter(c) or _digit(c)


def _ldh(c):
    return _letdig(c) or c == '-'


def _hlabel_ok(text):
    if text == '' or len(text) > HLABEL_MAX:
        return False
    if not _letdig(text[0]):
        return False
    if not _letdig(text[-1]):
        return False
    for c in text:
        if not _ldh(c):
            return False
    return True


def is_hlabel(text):
    f = make_fail('is_hlabel')
    if type(text) is not str:
        f('text-type')
    return _hlabel_ok(text)


def all_numeric(text):
    f = make_fail('all_numeric')
    if type(text) is not str:
        f('text-type')
    if text == '':
        return False
    for c in text:
        if not _digit(c):
            return False
    return True


def _parse(text):
    if len(text) > HNAME_MAX:
        return 'name-length', None
    labels = text.split('.')
    for lab in labels:
        if lab == '':
            return 'label-empty', None
        if len(lab) > HLABEL_MAX:
            return 'label-length', None
        if not _hlabel_ok(lab):
            return 'label-invalid', None
    last = labels[-1]
    numeric = True
    for c in last:
        if not _digit(c):
            numeric = False
    if numeric:
        return 'last-numeric', None
    return None, tuple(labels)


def _text(f, text):
    if type(text) is not str:
        f('text-type')


def is_hname(text):
    f = make_fail('is_hname')
    _text(f, text)
    code, labels = _parse(text)
    return code is None


def split_hname(text):
    f = make_fail('split_hname')
    _text(f, text)
    code, labels = _parse(text)
    if code is not None:
        f(code)
    return labels


def canonical_hname(text):
    f = make_fail('canonical_hname')
    _text(f, text)
    code, labels = _parse(text)
    if code is not None:
        f(code)
    return '.'.join(labels).lower()


def hname_equal(a, b):
    f = make_fail('hname_equal')
    _text(f, a)
    code_a, la = _parse(a)
    if code_a is not None:
        f(code_a)
    _text(f, b)
    code_b, lb = _parse(b)
    if code_b is not None:
        f(code_b)
    return tuple(x.lower() for x in la) == tuple(x.lower() for x in lb)
