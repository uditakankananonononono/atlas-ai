'''RFC 5890 "Internationalized Domain Names for
Applications (IDNA): Definitions and Document Framework":
the ASCII-side label rules for ONE label string - the
s2.3.1 LDH label base (kept thin; b1220 owns the RFC 1123
host-name rules), the s2.3.2 R-LDH / XN-label / NR-LDH
distinction, the A-label DATA SHAPE (s2.3.2.1, s2.3.2.5),
and fake-A-label detection on ASCII grounds.  U-labels
(NFC, non-ASCII characters, the RFC 5892 PVALID/CONTEXT
tables, bidi and symmetry constraints), Punycode validity
itself (the RFC 3492 codec - b1198's unit; an 'a_label'
result here certifies every ASCII-side requirement, NOT
that the punycode part decodes), multi-label domain
names, and DNS wire format are out of scope.

Public API:

  idna_label_parse(text) -> a dict:
      'label': the input text as received,
      'label_class': 'nr_ldh' (a Non-Reserved LDH label)
          or 'a_label' (an XN-label meeting every
          ASCII-side A-label requirement),
      'punycode_part': the characters after the "xn--"
          prefix for an 'a_label' result, else None,
      'canonical_text': OURS (below),
      'canonical': True iff the input IS the canonical
          text, byte for byte.
  idna_label_is_valid(text) -> True iff idna_label_parse
      would succeed.

Grammar notes (verified against the RFC 5890 text).
s2.3.1: an LDH label is a "string consisting of ASCII
letters, digits, and the hyphen with the further
restriction that the hyphen cannot appear at the
beginning or end of the string.  Like all DNS labels, its
total length must not exceed 63 octets."  s2.3.2:
"Reserved LDH labels ... have the property that they
contain "--" in the third and fourth characters but which
otherwise conform to LDH label rules"; the IDNA-usable
subset of R-LDH labels "consists of the class of labels
that begin with the prefix "xn--" (case independent), but
otherwise conform to the rules for LDH labels" -
those are the XN-labels.  "Non-Reserved LDH labels are
the set of valid LDH labels that do not have "--" in the
third and fourth positions."  s2.3.2.1: "every A-label
will begin with the IDNA ACE prefix, "xn--" ..., followed
by a string that is a valid output of the Punycode
algorithm [RFC3492] and hence a maximum of 59 ASCII
characters in length.  The prefix and string together
must conform to all requirements for a label that can be
stored in the DNS including conformance to the rules for
LDH labels (Section 2.3.1)."
The 59-character punycode-part cap is the 63-octet label
cap minus the 4-character prefix, so the label-length
check already enforces it.  Fake A-labels: "Some strings
that are prefixed with "xn--" ... may not be the output
of the Punycode algorithm ... They are called "Fake
A-labels""; on ASCII grounds the detectable case is an
EMPTY punycode part ("xn--" alone), since no U-label
encodes to nothing.  R-LDH labels without the "xn--"
prefix "are also not valid IDNA labels ... those labels
MUST NOT be processed as ordinary LDH labels by
IDNA-conforming programs" - refused here with
bad_value:label.r_ldh.  "A-labels should be produced only
in lowercase, despite matching other (mixed-case or
uppercase) potential labels in the DNS": a SHOULD about
producing, so mixed case is accepted and the canonical
text is the lowercase form.

Profile decisions (OURS, not from the RFC text):
  - Only the exact str type is accepted; subclasses
    refuse with the type code.
  - Canonical text: the whole label in lowercase (DNS
    label matching is case insensitive; the RFC 5890
    lowercase-production SHOULD covers A-labels and the
    unit applies one rule to both classes).

Refusal order: bad_type:value before everything; the
63-octet cap (bad_value:label.length); the empty label
(bad_value:label); the printable-ASCII gate %x21-7E
(bad_value:value.charset); the LDH character class
(bad_value:label.char); the fake A-label "xn--" alone,
with an empty punycode part (bad_value:label.fake -
ahead of the hyphen-edge rule it would otherwise trip);
the leading/trailing hyphen rule (bad_value:label.edge);
the R-LDH reservation (bad_value:label.r_ldh).

Errata: RFC 5890 has 7 records (3 Verified, 3 Held, 1
Reported, 0 Rejected).  Verified, not folded: EID 4695
(s2.3.2.1, A-label expansion length - a U-label-side
note), EID 4696 (s4.2, DNS label compression), EID 7291
(GLOBAL, header metadata: "Updates: 4343").  Held, not
folded: EIDs 4824 (s4.2), 4823 (s2.3.2.1) and 5484
(s2.3.2.1).  Reported, not folded: EID 9026 (s2.3.2.1).
RFC 5891 has 1 record (Held, EID 3969); its protocol
operations are out of scope here.
'''

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


# s2.3.1: "Like all DNS labels, its total length must not
# exceed 63 octets."
_MAX_LABEL_LENGTH = 63

# s2.3.2 / s2.3.2.5: the IDNA ACE prefix, case independent.
_ACE_PREFIX = 'xn--'

_ALPHANUM = frozenset(
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    '0123456789')

# s2.3.1 LDH: ASCII letters, digits, and the hyphen.
_LDH_CHARS = _ALPHANUM | frozenset('-')


def idna_label_parse(text):
    f = make_fail('idna_label_parse')
    if type(text) is not str:
        f('bad_type:value')
    if len(text) > _MAX_LABEL_LENGTH:
        f('bad_value:label.length')
    if not text:
        f('bad_value:label')
    for c in text:
        if not '!' <= c <= '~':
            f('bad_value:value.charset')
    for c in text:
        if c not in _LDH_CHARS:
            f('bad_value:label.char')
    prefixed = text[:4].lower() == _ACE_PREFIX
    if prefixed and len(text) == len(_ACE_PREFIX):
        # the fake A-label shape: ahead of the hyphen-edge
        # rule it would otherwise trip
        f('bad_value:label.fake')
    if text[0] == '-' or text[-1] == '-':
        f('bad_value:label.edge')
    if text[2:4] == '--' and not prefixed:
        f('bad_value:label.r_ldh')
    label_class = 'a_label' if prefixed else 'nr_ldh'
    punycode_part = text[len(_ACE_PREFIX):] if prefixed else None
    canonical_text = text.lower()
    return {'label': text,
            'label_class': label_class,
            'punycode_part': punycode_part,
            'canonical_text': canonical_text,
            'canonical': text == canonical_text}


def idna_label_is_valid(text):
    'True iff idna_label_parse(text) would succeed.'
    try:
        idna_label_parse(text)
        return True
    except ValueError:
        return False
