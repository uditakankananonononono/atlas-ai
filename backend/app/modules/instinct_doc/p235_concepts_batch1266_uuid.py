"""p235 concepts batch 1266 (rev 0): RFC 9562, Universally Unique IDentifiers (UUIDs), as a grammar over caller-supplied text: the section 4 hex-and-dash string format, the section 4.1 variant field, the section 4.2 version field, the section 5.9 Nil UUID, the section 5.10 Max UUID, the urn:uuid: form, and an octet extractor. Pure functions; no retrieval, no network, no clock, no registries, no randomness. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it generates no UUID, computes no timestamp or hash, and validates text form only.

LIVE SOURCES (fetched 2026-10-22; quotes below are verbatim from these files, mechanically matched with whitespace collapsed):
- RFC 9562 text, rfc-editor (114638 bytes, sha256 041870106b8701d9fa9261dcbc1679a6b7ab18cb179b37b69d7232431eac8042).
- rfc-editor info page for RFC 9562 (1020001 bytes, sha256 53035114a616a89ca8b5fd55efc5756398a817df71b88c41f6324998e66d8e8b): it lists "Obsoletes (1)" RFC 4122 (not re-derived here; RFC 4122 is obsolete and this module follows RFC 9562 only).
- The full rfc-editor errata index (11775016 bytes, sha256 23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c) contains exactly six RFC 9562 records (count from errata.json and not independently confirmed): EID 7929, status Verified, type Technical, section B.2 (a variant character in a worked example; this module has no example data); EID 7931, status Reported, type Editorial, section 1 (an introduction wording note); EID 7955, status Verified, type Technical, section 5.1 (a timestamp field layout in the version 1 description; timestamps are NOT_CLAIMED); EID 7958, status Verified, type Technical, section 4.1 (the variant table row for the high bit 0 lists "1-7" where the notes say the range is 0-7, because the Nil UUID has the digit 0 there); EID 8288, status Verified, type Technical, section 6.1 (a maximum-date calculation; timestamps are NOT_CLAIMED); EID 8695, status Verified, type Editorial, section 7.1 (the IANA text says Table 1 where Table 2 is meant; the IANA registry is NOT_CLAIMED).

SOURCED format (section 4): "UUIDs MAY be represented as binary data or integers." "any given UUID should be represented by the "hex-and-dash" string format consisting of multiple groups of uppercase or lowercase alphanumeric hexadecimal characters separated by single dashes/hyphens." "UUID = 4hexOctet "-" 2hexOctet "-" 2hexOctet "-" 2hexOctet "-" 6hexOctet" "hexOctet = HEXDIG HEXDIG" "HEXDIG = DIGIT / "A" / "B" / "C" / "D" / "E" / "F"" "Note that the alphabetic characters may be all uppercase, all lowercase, or mixed case, as per Section 2.3 of [RFC5234]." "urn:uuid:f81d4fae-7dec-11d0-a765-00a0c91e6bf6"
SOURCED variant (section 4.1): "The variant field consists of a variable number of the most significant bits of octet 8 of the UUID." "Specifically for UUIDs in this document, bits 64 and 65 of the UUID (bits 0 and 1 of octet 8) MUST be set to 1 and 0 as specified in row 2 of Table 1." Table 1 rows (section 4.1): "Reserved. Network Computing System (NCS) backward compatibility, and includes Nil UUID as per Section 5.9." "The variant specified in this document." "Reserved. Microsoft Corporation backward compatibility." "Reserved for future definition and includes Max UUID as per Section 5.10."
SOURCED version (section 4.2): "The version number is in the most significant 4 bits of octet 6 (bits 48 through 51 of the UUID)." Table 2 rows (section 4.2): "Unused." "The Gregorian time-based UUID specified in this document." "Reserved for DCE Security version, with embedded POSIX UUIDs." "The name-based version specified in this document that uses MD5 hashing." "The randomly or pseudorandomly generated version specified in this document." "The name-based version specified in this document that uses SHA-1 hashing." "Reordered Gregorian time- based UUID specified in this document." "Unix Epoch time-based UUID specified in this document." "Reserved for custom UUID formats specified in this document." "Reserved for future definition."
SOURCED special forms: "The Nil UUID is special form of UUID that is specified to have all 128 bits set to zero." "The Max UUID is a special form of UUID that is specified to have all 128 bits set to 1." "Note that the Nil UUID value falls within the range of the Apollo NCS variant as per the first row of Table 1 rather than the variant defined by this document." "Note that the Max UUID value falls within the range of the "yet-to-be defined" future UUID variant as per the last row of Table 1 rather than the variant defined by this document."

DECISIONS AND NOT_CLAIMED:
1. Input domain. Inputs are caller-supplied str values, already decoded. Binary and integer forms, the little-endian Microsoft COM byte order, databases (section 6.13), the curly-brace and OID forms, the version 1 to 8 field layouts and generation rules, the IANA registry, and the RFC 8141 URN rules are NOT_CLAIMED. The string form is read exactly as the ABNF: 36 characters, a dash at positions 8, 13, 18 and 23 (counting from 0), and a HEXDIG at the other 32 positions, in upper, lower or mixed case.
2. Variant classes (OURS reading of Table 1 with EID 7958). The high bits of the first hex digit of octet 8 give the class: digits 0 to 7 are ncs (the corrected row; the Nil UUID is there), 8 to B are rfc9562, C and D are microsoft, E and F are future (the Max UUID is there). EID 7958 is Verified Technical and its correction is followed here and not independently confirmed.
3. Version classes (OURS reading of Table 2). Only for variant rfc9562: digit 0 is unused, digit 2 is dce (reserved for DCE Security), digits 1, 3, 4, 5, 6, 7 and 8 are accepted, digits 9 to F are future. This module accepts version 8 as "specified in this document" and does not check that a field layout matches any version.
4. Nil and Max. nil_reason accepts only the text with all 32 hex digits 0; max_reason accepts only all 32 hex digits F or f. Both require a well-formed UUID string first.
5. URN form (OURS). urn_reason requires the exact lowercase prefix "urn:uuid:" followed by a well-formed UUID string. Case rules of RFC 8141 for the namespace identifier are NOT_CLAIMED; an uppercase prefix is reported as prefix.
6. Caps (OURS, all raising): _LEN_CAP 256 characters per input, checked after the type and before any content check; the cap is an input-size limit, not a statement about UUIDs.
7. uuid_octets and uuid_parts (OURS reports). uuid_octets returns the 16 octet values as a tuple of ints, first octet first, from the text order of the hex digits. uuid_parts returns (variant, version): variant is one of ncs, rfc9562, microsoft, future; version is the int value of the version digit when the variant is rfc9562, and -1 otherwise. Both raise bad_value:value.uuid for text that is not a well-formed UUID string.

FUNCTIONS, in this order: uuid_reason, groups_reason, hexdigits_reason, variant_reason, version_reason, nil_reason, max_reason, urn_reason, uuid_octets, uuid_parts. Reason functions return the string "ok" or a reason; uuid_octets returns a tuple of 16 ints; uuid_parts returns a 2-tuple.

REASONS, in check order (the first failure decides):
- uuid_reason: bad_type:value (raise), bad_value:value.length (raise); then length (not exactly 36 characters), then left to right by the first offending position: dash (a character other than "-" at position 8, 13, 18 or 23), hexdig (a character that is not a HEXDIG at any other position); ok.
- groups_reason: bad_type:value (raise), bad_value:value.length (raise); then length, dash (the dash positions only; the other positions are not read); ok.
- hexdigits_reason: bad_type:value (raise), bad_value:value.length (raise); then length, hexdig (a non-HEXDIG at one of the 32 non-dash positions; the dash positions are not read); ok.
- variant_reason: bad_type:value (raise), bad_value:value.length (raise); then uuid.<uuid_reason reason>; then variant.ncs, variant.microsoft, variant.future; ok (variant rfc9562).
- version_reason: bad_type:value (raise), bad_value:value.length (raise); then uuid.<uuid_reason reason>; then variant (the variant is not rfc9562, whichever other class it is); then version.unused, version.dce, version.future; ok.
- nil_reason: bad_type:value (raise), bad_value:value.length (raise); then uuid.<uuid_reason reason>; then not_nil; ok.
- max_reason: bad_type:value (raise), bad_value:value.length (raise); then uuid.<uuid_reason reason>; then not_max; ok.
- urn_reason: bad_type:value (raise), bad_value:value.length (raise); then prefix (fewer than 9 characters or the first 9 characters are not "urn:uuid:"), then uuid.<uuid_reason reason> of the rest; ok.
- uuid_octets: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.uuid (raise).
- uuid_parts: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.uuid (raise).

OUTPUT ORDER: reason strings are the exact codes listed above; uuid_parts emits variant first, then version.
"""
SCOPE = "RFC 9562 over caller-supplied text: the hex-and-dash UUID string of section 4, the variant and version fields of sections 4.1 and 4.2, the Nil and Max UUIDs of sections 5.9 and 5.10, the urn:uuid: form, and octet extraction. Pure functions; no retrieval, no network, no clock, no registries, no randomness."
NOT_CLAIMED = ('standard', 'authority', 'certification', 'currency', 'completeness',
               'binary and integer forms and byte order', 'field layouts and generation of versions 1 to 8',
               'timestamps, hashing and randomness', 'IANA registry', 'RFC 8141 URN case rules',
               'curly-brace and OID forms', 'database storage')
CLAIMS = {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False}
ADJACENT = ('RFC 4122 (obsoleted by RFC 9562, per the info page; not re-derived here)',
            'RFC 5234 (ABNF, the grammar notation the RFC cites; HEXDIG case rule of its section 2.3)',
            'RFC 8141 (URN syntax, cited by RFC 9562 for the urn:uuid: form; not re-derived here)')

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

_LEN_CAP = 256
_UUID_LEN = 36
_URN = 'urn:uuid:'
_DASHES = (8, 13, 18, 23)
_HEXVAL = {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
           'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14, 'F': 15,
           'a': 10, 'b': 11, 'c': 12, 'd': 13, 'e': 14, 'f': 15}


def _check(fail, v):
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')


def _shape(v, dashes, digits):
    if len(v) != _UUID_LEN:
        return 'length'
    i = 0
    while i < _UUID_LEN:
        if i in _DASHES:
            if dashes and v[i] != '-':
                return 'dash'
        elif digits and v[i] not in _HEXVAL:
            return 'hexdig'
        i += 1
    return 'ok'


def _variant(v):
    d = _HEXVAL[v[19]]
    if d < 8:
        return 'ncs'
    if d < 12:
        return 'rfc9562'
    if d < 14:
        return 'microsoft'
    return 'future'


def _uuid(fail, v):
    _check(fail, v)
    r = _shape(v, True, True)
    if r != 'ok':
        return 'uuid.' + r
    return 'ok'


def uuid_reason(v):
    fail = make_fail('uuid_reason')
    _check(fail, v)
    return _shape(v, True, True)


def groups_reason(v):
    fail = make_fail('groups_reason')
    _check(fail, v)
    return _shape(v, True, False)


def hexdigits_reason(v):
    fail = make_fail('hexdigits_reason')
    _check(fail, v)
    return _shape(v, False, True)


def variant_reason(v):
    fail = make_fail('variant_reason')
    r = _uuid(fail, v)
    if r != 'ok':
        return r
    c = _variant(v)
    if c != 'rfc9562':
        return 'variant.' + c
    return 'ok'


def version_reason(v):
    fail = make_fail('version_reason')
    r = _uuid(fail, v)
    if r != 'ok':
        return r
    if _variant(v) != 'rfc9562':
        return 'variant'
    d = _HEXVAL[v[14]]
    if d == 0:
        return 'version.unused'
    if d == 2:
        return 'version.dce'
    if d > 8:
        return 'version.future'
    return 'ok'


def nil_reason(v):
    fail = make_fail('nil_reason')
    r = _uuid(fail, v)
    if r != 'ok':
        return r
    i = 0
    while i < _UUID_LEN:
        if i not in _DASHES and v[i] != '0':
            return 'not_nil'
        i += 1
    return 'ok'


def max_reason(v):
    fail = make_fail('max_reason')
    r = _uuid(fail, v)
    if r != 'ok':
        return r
    i = 0
    while i < _UUID_LEN:
        if i not in _DASHES and _HEXVAL[v[i]] != 15:
            return 'not_max'
        i += 1
    return 'ok'


def urn_reason(v):
    fail = make_fail('urn_reason')
    _check(fail, v)
    if len(v) < len(_URN) or v[:len(_URN)] != _URN:
        return 'prefix'
    r = _shape(v[len(_URN):], True, True)
    if r != 'ok':
        return 'uuid.' + r
    return 'ok'


def uuid_octets(v):
    fail = make_fail('uuid_octets')
    _check(fail, v)
    if _shape(v, True, True) != 'ok':
        fail('bad_value:value.uuid')
    out = []
    i = 0
    while i < _UUID_LEN:
        if i in _DASHES:
            i += 1
        else:
            out.append(_HEXVAL[v[i]] * 16 + _HEXVAL[v[i + 1]])
            i += 2
    return tuple(out)


def uuid_parts(v):
    fail = make_fail('uuid_parts')
    _check(fail, v)
    if _shape(v, True, True) != 'ok':
        fail('bad_value:value.uuid')
    c = _variant(v)
    if c != 'rfc9562':
        return c, -1
    return c, _HEXVAL[v[14]]
