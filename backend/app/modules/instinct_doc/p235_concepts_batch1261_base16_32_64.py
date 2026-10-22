"""p235 concepts batch 1261 (rev 0): RFC 4648, The Base16, Base32, and Base64 Data Encodings, as a grammar over caller-supplied text: alphabet membership, block length, pad placement and pad count for the base64 (section 4), base64url (section 5), base32 (section 6) and base32hex (section 7) encodings, the case-insensitive base16 form (section 8), the section 3.5 canonical-form pad-bit checks, and a base16 octet extractor. Pure functions; no retrieval, no network, no clock, no registries. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it performs no encoding or decoding of caller data beyond the base16 octet extraction named below, and it defines no format.

LIVE SOURCES (fetched 2026-10-22; quotes below are verbatim from these files, mechanically matched with whitespace collapsed):
- RFC 4648 text, rfc-editor (35491 bytes, sha256 84e14418f795d503be5f34bf23ce4ebaa119e9ec7c9f667d8caeb111385b178f).
- rfc-editor info page for RFC 4648 (231933 bytes, sha256 ae5d74008d0608c800cd959cd93c59834d29c04193781f2121206d269e836972): it lists Obsoletes: RFC 3548, and shows no Obsoleted by entry and no Updated by entry. CLAIMS current is still False.
- The full rfc-editor errata index (11775016 bytes, sha256 23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c) contains exactly six RFC 4648 records (count from errata.json and not independently confirmed): EID 2837, status Verified, type Editorial, section 16.2 (a reference URL); EID 4889, status Reported, type Technical, section 6 (wording of the base32 zero-bit padding description); EID 5855, status Verified, type Editorial, section 10 (a test-vector presentation note); EID 7514, status Verified, type Editorial, section 3.5 (the "do not hold" verb typo; the quote below preserves the live text); EID 8669, status Reported, type Technical, section 4 (wording of the base64 24-bit group description); EID 9030, status Verified, type Editorial, section 5 (a pad-character percent-encoding note). The two Reported-Technical errata concern the encoding-PROCESS descriptions; this module validates text form only, anchored on section 3.5 and the case lists, so its rules are unchanged; no departure is taken from the live text.

SOURCED rules:
- Non-alphabet characters: "Implementations MUST reject the encoded data if it contains characters outside the base alphabet" (section 3.3, MUST-strength here: no referring specification relaxes it for these functions). Line feeds are never added or accepted: "Implementations MUST NOT add line feeds to base-encoded data unless the specification referring to this document explicitly directs base encoders to add line feeds after a specific number of characters."
- Padding: "Implementations MUST include appropriate pad characters at the end of encoded data unless the specification referring to this document explicitly states otherwise." These functions implement the general case, so padding is required where the encoding defines it: "The base64 and base32 alphabets use padding, as described below in sections 4 and 6, but the base16 alphabet does not need it; see section 8."
- Base 64 pad cases: "(2) The final quantum of encoding input is exactly 8 bits; here, the final unit of encoded output will be two characters followed by two "=" padding characters." "(3) The final quantum of encoding input is exactly 16 bits; here, the final unit of encoded output will be three characters followed by one "=" padding character."
- Base 32 pad cases: "(2) The final quantum of encoding input is exactly 8 bits; here, the final unit of encoded output will be two characters followed by six "=" padding characters." ... "(5) The final quantum of encoding input is exactly 32 bits; here, the final unit of encoded output will be seven characters followed by one "=" padding character." (the 16-bit and 24-bit cases give four/four and five/three characters/pads respectively).
- base64url: "This encoding is technically identical to the previous one, except for the 62:nd and 63:rd alphabet character, as indicated in Table 2." "This encoding should not be regarded as the same as the "base64" encoding and should not be referred to as only "base64"."
- base32hex: "This encoding is identical to the previous one, except for the alphabet. The new alphabet is found in Table 4." "This encoding should not be regarded as the same as the "base32" encoding and should not be referred to as only "base32"."
- Base 16: "Essentially, Base 16 encoding is the standard case- insensitive hex encoding and may be referred to as "base16" or "hex"." "Unlike base 32 and base 64, no special padding is necessary since a full code word is always available."
- Canonical form: "These pad bits MUST be set to zero by conforming encoders" "If this property do not hold, there is no canonical representation of base-encoded data, and multiple base- encoded strings can be decoded to the same binary data." "If this property (and others discussed in this document) holds, a canonical encoding is guaranteed."
- Test vectors (section 10, exercised in the tests): "BASE64("foobar") = "Zm9vYmFy"" "BASE32("foobar") = "MZXW6YTBOI======"" "BASE32-HEX("foobar") = "CPNMUOJ1E8======"" "BASE16("foobar") = "666F6F626172""
- Base 32 bit order: "When a bit stream is encoded via the base 32 encoding, the bit stream must be presumed to be ordered with the most-significant- bit first."

DECISIONS AND NOT_CLAIMED:
1. Case. base16 accepts both upper- and lowercase (section 8 calls it the "standard case-insensitive hex encoding"; SOURCED). base32 and base32hex are uppercase-only as their tables define them; the case-insensitivity in section 6 is a design goal for the transport ("needs to be case insensitive"), not a licence for decoders, and liberal lowercase acceptance is NOT_CLAIMED: a lowercase base32 character reports char. base64 and base64url are case-sensitive by construction.
2. Padding. Only the strict padded form is validated (the section 3.2 general case). Unpadded forms permitted "if the data length is known implicitly" (section 5) are a referencing-specification choice and are NOT_CLAIMED: a short final quantum reports length, and missing pads report length, never ok.
3. Decoding. No binary decoding is provided except base16_octets, which extracts the octet values of a valid base16 string; full decoding semantics (including the bit ordering in "When a bit stream is encoded via the base 32 encoding, the bit stream must be presumed to be ordered with the most-significant- bit first.") are NOT_CLAIMED. The canonical checks look only at the pad bits named in section 3.5, via alphabet positions, without decoding.
4. Caps (OURS, all raising): _LEN_CAP 1024 characters per input. The grammar itself is unbounded.

FUNCTIONS, in this order: base64_reason, base64url_reason, base32_reason, base32hex_reason, base16_reason, base64_canon_reason, base64url_canon_reason, base32_canon_reason, base32hex_canon_reason, base16_octets. The reason functions return the string "ok" or a reason string; base16_octets returns a tuple of octet values (0-255) in order. Errors are ValueError with the text P235:<function>:<code>, where <function> is the owning function and <code> is bad_type:value (non-str input), bad_value:value.length (over _LEN_CAP), or bad_value:value.base16 (base16_octets on an invalid string).

REASONS, in check order (the first failure decides):
- base64_reason / base64url_reason / base32_reason / base32hex_reason: bad_type:value (raise), bad_value:value.length (raise); then length (total length not a multiple of the block, 4 for the 64-family and 8 for the 32-family), char (a character outside the alphabet before the first "="), pad.placement (a non-"=" character after the first "="), pad.count (a pad count the encoding cannot produce: the 64-family allows 1 or 2, the 32-family allows 1, 3, 4 or 6); ok. The empty string is ok.
- base16_reason: bad_type:value (raise), bad_value:value.length (raise); then length (odd length), char (outside 0-9 A-F a-f); ok. The empty string is ok.
- base64_canon_reason / base64url_canon_reason / base32_canon_reason / base32hex_canon_reason: bad_type:value (raise), bad_value:value.length (raise); then the matching base reason if not ok, then pad.bits (the final data character carries nonzero pad bits: with pad 2 in the 64-family the low 4 bits, with pad 1 the low 2 bits; with pad 6/4/3/1 in the 32-family the low 2/4/1/3 bits); ok.
- base16_octets: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.base16 (raise, when base16_reason would not return ok).

OUTPUT ORDER: reason strings are the exact dotted codes listed above; base16_octets emits octets left to right, high nibble first, per the section 8 "high-order bit" reading of each 8-bit group."""
SCOPE = "RFC 4648 over caller-supplied text: the Base16, Base32, Base64 (and the base64url and base32hex alphabet variants) data encoding grammars - alphabet membership, block length, pad placement and pad count, the section 3.5 canonical pad-bit checks, and a base16 octet extractor. Pure functions; no retrieval, no network, no clock, no registries."
NOT_CLAIMED = ('standard', 'authority', 'certification', 'currency', 'completeness',
               'encoding process', 'binary decoding (beyond base16_octets)', 'unpadded forms', 'liberal lowercase base32')
CLAIMS = {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False}
ADJACENT = ('RFC 2045 MIME base64 Content-Transfer-Encoding (b1204 covers the field value; the 76-character line limit is not this grammar)',
            'RFC 3986 token68 usages of base64 text (b1123, b1199 treat it as opaque)',
            'RFC 3548 (obsoleted by RFC 4648, per the info page)')

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

_LEN_CAP = 1024

_B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
_B64U = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
_B32 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
_B32H = '0123456789ABCDEFGHIJKLMNOPQRSTUV'
_B16 = '0123456789ABCDEF'
_B16L = '0123456789abcdef'

_B64_IDX = {_B64[_k]: _k for _k in range(len(_B64))}
_B64U_IDX = {_B64U[_k]: _k for _k in range(len(_B64U))}
_B32_IDX = {_B32[_k]: _k for _k in range(len(_B32))}
_B32H_IDX = {_B32H[_k]: _k for _k in range(len(_B32H))}
_B16_IDX = {_c: _k for _k in range(len(_B16)) for _c in (_B16[_k], _B16L[_k])}

_B64_PADS = (1, 2)
_B32_PADS = (1, 3, 4, 6)
_B64_ZERO = {1: 4, 2: 16}
_B32_ZERO = {1: 8, 3: 2, 4: 16, 6: 4}


def _padded_reason(v, alpha, block, pads):
    n = len(v)
    if n % block != 0:
        return 'length'
    i = 0
    while i < n and v[i] != '=':
        if v[i] not in alpha:
            return 'char'
        i += 1
    j = i
    while j < n:
        if v[j] != '=':
            return 'pad.placement'
        j += 1
    padc = n - i
    if padc > 0 and padc not in pads:
        return 'pad.count'
    return 'ok'


def _pad_count(v):
    n = len(v)
    i = n
    while i > 0 and v[i - 1] == '=':
        i -= 1
    return n - i


def _canon_reason(v, idx, zero, r):
    if r != 'ok':
        return r
    padc = _pad_count(v)
    if padc == 0:
        return 'ok'
    last = idx[v[len(v) - padc - 1]]
    if last % zero[padc] != 0:
        return 'pad.bits'
    return 'ok'


def base64_reason(v):
    fail = make_fail('base64_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _padded_reason(v, _B64, 4, _B64_PADS)


def base64url_reason(v):
    fail = make_fail('base64url_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _padded_reason(v, _B64U, 4, _B64_PADS)


def base32_reason(v):
    fail = make_fail('base32_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _padded_reason(v, _B32, 8, _B32_PADS)


def base32hex_reason(v):
    fail = make_fail('base32hex_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _padded_reason(v, _B32H, 8, _B32_PADS)


def base16_reason(v):
    fail = make_fail('base16_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    n = len(v)
    if n % 2 != 0:
        return 'length'
    for k in range(n):
        c = v[k]
        if c not in _B16 and c not in _B16L:
            return 'char'
    return 'ok'


def base64_canon_reason(v):
    fail = make_fail('base64_canon_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _canon_reason(v, _B64_IDX, _B64_ZERO, _padded_reason(v, _B64, 4, _B64_PADS))


def base64url_canon_reason(v):
    fail = make_fail('base64url_canon_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _canon_reason(v, _B64U_IDX, _B64_ZERO, _padded_reason(v, _B64U, 4, _B64_PADS))


def base32_canon_reason(v):
    fail = make_fail('base32_canon_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _canon_reason(v, _B32_IDX, _B32_ZERO, _padded_reason(v, _B32, 8, _B32_PADS))


def base32hex_canon_reason(v):
    fail = make_fail('base32hex_canon_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    return _canon_reason(v, _B32H_IDX, _B32_ZERO, _padded_reason(v, _B32H, 8, _B32_PADS))


def base16_octets(v):
    fail = make_fail('base16_octets')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    if base16_reason(v) != 'ok':
        fail('bad_value:value.base16')
    out = []
    for k in range(0, len(v), 2):
        out += [_B16_IDX[v[k]] * 16 + _B16_IDX[v[k + 1]]]
    return tuple(out)
