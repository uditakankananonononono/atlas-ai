"""p235 concepts batch 1272 (rev 0): RFC 3629, UTF-8, a transformation format of ISO 10646, as a grammar over caller-supplied octets: the section 3 sequence lengths and the table of character ranges, the section 3 prohibition of surrogates and of overlong forms, the U+10FFFF maximum, the section 4 ABNF, and an encoder, a decoder and a length reader built on them. Pure functions; no retrieval, no network, no clock, no registries, no codecs. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it follows the RFC 3629 text only and the Unicode Standard is authoritative.

LIVE SOURCES (fetched 2026-10-22; quotes below are verbatim from these files, mechanically matched with whitespace collapsed):
- RFC 3629 text, rfc-editor (33856 bytes, sha256 a2a3a39457d30420c812f87a38cc2b9194832f6982ef17e619de7d816879d6a6).
- rfc-editor info page for RFC 3629 (206798 bytes, sha256 126c267614990bbdb4daa2a2f39894f97970624bf8909599016f466710dabbbb): it shows "Obsoletes: 2279", the STD 63 label, and no "Updated by" or "Obsoleted by" entry. RFC 2279 is obsolete and is not followed; CLAIMS current is still False.
- The full rfc-editor errata index (11775016 bytes, sha256 23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c) contains exactly zero RFC 3629 records (count from errata.json and not independently confirmed), so no erratum is applied or declined.

SOURCED definition (section 3): "In UTF-8, characters from the U+0000..U+10FFFF range (the UTF-16 accessible range) are encoded using sequences of 1 to 4 octets." "The only octet of a "sequence" of one has the higher-order bit set to 0, the remaining 7 bits being used to encode the character number." "In a sequence of n octets, n>1, the initial octet has the n higher-order bits set to 1, followed by a bit set to 0." "The following octet(s) all have the higher-order bit set to 1 and the following bit set to 0, leaving 6 bits in each to contain bits from the character to be encoded."
SOURCED table (section 3): "0000 0000-0000 007F | 0xxxxxxx" "0000 0080-0000 07FF | 110xxxxx 10xxxxxx" "0000 0800-0000 FFFF | 1110xxxx 10xxxxxx 10xxxxxx" "0001 0000-0010 FFFF | 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx" "It is important to note that the rows of the table are mutually exclusive, i.e., there is only one valid way to encode a given character."
SOURCED surrogates and invalid sequences (section 3): "The definition of UTF-8 prohibits encoding character numbers between U+D800 and U+DFFF, which are reserved for use with the UTF-16 encoding form (as surrogate pairs) and do not directly represent characters." "Implementations of the decoding algorithm above MUST protect against decoding invalid sequences." "a naive implementation may decode the overlong UTF-8 sequence C0 80 into the character U+0000, or the surrogate pair ED A1 8C ED BE B4 into U+233B4." "the CESU-8 encoding of those characters is NOT valid UTF-8."
SOURCED ABNF (section 4): "UTF8-octets = *( UTF8-char )" "UTF8-char = UTF8-1 / UTF8-2 / UTF8-3 / UTF8-4" "UTF8-1 = %x00-7F" "UTF8-2 = %xC2-DF UTF8-tail" "UTF8-3 = %xE0 %xA0-BF UTF8-tail / %xE1-EC 2( UTF8-tail ) / %xED %x80-9F UTF8-tail / %xEE-EF 2( UTF8-tail )" "UTF8-4 = %xF0 %x90-BF 2( UTF8-tail ) / %xF1-F3 3( UTF8-tail ) / %xF4 %x80-8F 2( UTF8-tail )" "UTF8-tail = %x80-BF" "NOTE -- The authoritative definition of UTF-8 is in [UNICODE]. This grammar is believed to describe the same thing Unicode describes, but does not claim to be authoritative."

DECISIONS AND NOT_CLAIMED:
1. Input domain. Octet inputs are caller-supplied bytes values; code point inputs are caller-supplied ints. A str, a bytearray, a memoryview, a list or a bool is a type error. Byte order marks, the Unicode Standard, normalization, UTF-16 and UTF-32, CESU-8, modified UTF-8, ISO 10646 versions, MIME charset labels, RFC 2279 and every section other than 3 and 4 are NOT_CLAIMED. A byte order mark is just the octets EF BB BF here.
2. Grammar. An octet string is valid when it matches UTF8-octets of section 4; the empty string is valid (the star allows zero characters). The module reads the ABNF exactly: UTF8-2 leads are C2 to DF; UTF8-3 leads are E0 to EF with the second octet limited for E0 (A0 to BF) and ED (80 to 9F); UTF8-4 leads are F0 to F4 with the second octet limited for F0 (90 to BF) and F4 (80 to 8F); every other octet of a sequence is a UTF8-tail 80 to BF.
3. Reason codes (OURS naming of the section 3 and 4 failures). lead: an octet that cannot start a sequence (80 to BF, a stray tail, or F8 to FF). overlong: a lead C0 or C1, or a second octet below the E0 and F0 limits (the C0 80 example of section 3, and the longer forms of the same kind). surrogate: ED followed by A0 to BF (U+D800 to U+DFFF). range: a lead F5 to F7, or F4 followed by 90 to BF (above U+10FFFF). tail: an octet that is not 80 to BF where a tail is required. truncated: the input ends inside a sequence with every octet seen so far fitting the grammar. The first failure from left to right decides. Within one sequence the lead is checked first, then the second octet, then each later tail in order.
4. Code points. codepoint_reason accepts 0 to 0x10FFFF without 0xD800 to 0xDFFF. A negative value reports negative, a value above 0x10FFFF reports range, a value from 0xD800 to 0xDFFF reports surrogate. The three tests are disjoint.
5. Caps (OURS, all raising): _LEN_CAP 1024 octets per bytes input, checked after the type and before any content check; the cap is an input-size limit, not a statement about UTF-8. Code point inputs have no cap.
6. Outputs (OURS reports). decode_utf8 returns a tuple of ints, one per character, from the section 3 decoding bit layout. char_lengths returns a tuple of the sequence lengths in octets, one per character. encoded_length returns 1, 2, 3 or 4 from the table. encode_codepoint returns the bytes of the one valid encoding. All four raise bad_value on invalid input (value.utf8 for the octet inputs, value.codepoint for the int inputs).

FUNCTIONS, in this order: utf8_reason, ascii_reason, char_reason, lead_reason, tail_reason, codepoint_reason, encoded_length, encode_codepoint, decode_utf8, char_lengths. Reason functions return the string "ok" or a reason; the others return the values named in decision 6.

REASONS, in check order (the first failure decides):
- utf8_reason: bad_type:value (raise), bad_value:value.length (raise); then left to right per character: lead, overlong, surrogate, range, tail, truncated; ok.
- ascii_reason: bad_type:value (raise), bad_value:value.length (raise); then nonascii (an octet above 7F); ok.
- char_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, then the reasons of utf8_reason for the first character only, then extra (octets after the first character); ok.
- lead_reason: bad_type:value (raise), bad_value:value.length (raise); then length (not exactly one octet), then lead (80 to BF or F8 to FF), overlong (C0 or C1), range (F5 to F7); ok (00 to 7F or C2 to F4).
- tail_reason: bad_type:value (raise), bad_value:value.length (raise); then length (not exactly one octet), then tail (not 80 to BF); ok.
- codepoint_reason: bad_type:value (raise); then negative, range, surrogate; ok.
- encoded_length: bad_type:value (raise), bad_value:value.codepoint (raise).
- encode_codepoint: bad_type:value (raise), bad_value:value.codepoint (raise).
- decode_utf8: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.utf8 (raise).
- char_lengths: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.utf8 (raise).

OUTPUT ORDER: reason strings are the exact codes listed above; decode_utf8 and char_lengths list the characters in input order.
"""

SCOPE = 'RFC 3629 over caller-supplied octets: the section 3 sequence lengths and character ranges, the surrogate and overlong prohibitions, the U+10FFFF maximum, the section 4 ABNF, and an encoder, a decoder and a length reader. Pure functions; no retrieval, no network, no clock, no registries, no codecs.'
NOT_CLAIMED = ('standard', 'authority', 'certification', 'currency', 'completeness',
               'the Unicode Standard', 'byte order marks and normalization', 'UTF-16, UTF-32, CESU-8 and modified UTF-8',
               'ISO 10646 versions', 'MIME charset labels', 'RFC 2279')
CLAIMS = {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False}
ADJACENT = ('RFC 2279 (obsoleted by RFC 3629, per the info page; not followed here)',
            'RFC 2234 (ABNF, the grammar notation the RFC cites; not re-derived here)',
            'The Unicode Standard (named authoritative by RFC 3629 sections 3 and 4; not read here)')

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


def _check(fail, v):
    if type(v) is not bytes:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')


def _lead(b):
    # classify one lead octet: (reason, sequence length, low bound, high bound, mask)
    if b < 128:
        return ('ok', 1, 0, 0, 127)
    if b < 192:
        return ('lead', 0, 0, 0, 0)
    if b < 194:
        return ('overlong', 0, 0, 0, 0)
    if b < 224:
        return ('ok', 2, 128, 191, 31)
    if b < 240:
        if b == 224:
            return ('ok', 3, 160, 191, 15)
        if b == 237:
            return ('ok', 3, 128, 159, 15)
        return ('ok', 3, 128, 191, 15)
    if b < 245:
        if b == 240:
            return ('ok', 4, 144, 191, 7)
        if b == 244:
            return ('ok', 4, 128, 143, 7)
        return ('ok', 4, 128, 191, 7)
    if b < 248:
        return ('range', 0, 0, 0, 0)
    return ('lead', 0, 0, 0, 0)


def _scan(v, one):
    # walk v as UTF8-octets; with one set, stop after the first character
    n = len(v)
    i = 0
    lens = []
    cps = []
    while i < n:
        (r, need, lo, hi, mask) = _lead(v[i])
        if r != 'ok':
            return (r, lens, cps)
        cp = v[i] & mask
        k = 1
        while k < need:
            if i + k >= n:
                return ('truncated', lens, cps)
            t = v[i + k]
            if t < 128 or t > 191:
                return ('tail', lens, cps)
            if k == 1 and t < lo:
                return ('overlong', lens, cps)
            if k == 1 and t > hi:
                if v[i] == 237:
                    return ('surrogate', lens, cps)
                return ('range', lens, cps)
            cp = cp * 64 + (t & 63)
            k += 1
        lens.append(need)
        cps.append(cp)
        i += need
        if one:
            break
    return ('ok', lens, cps)


def utf8_reason(v):
    fail = make_fail('utf8_reason')
    _check(fail, v)
    return _scan(v, False)[0]


def ascii_reason(v):
    fail = make_fail('ascii_reason')
    _check(fail, v)
    for b in v:
        if b > 127:
            return 'nonascii'
    return 'ok'


def char_reason(v):
    fail = make_fail('char_reason')
    _check(fail, v)
    if len(v) == 0:
        return 'empty'
    (r, lens, cps) = _scan(v, True)
    if r != 'ok':
        return r
    (n,) = lens
    if len(v) > n:
        return 'extra'
    return 'ok'


def lead_reason(v):
    fail = make_fail('lead_reason')
    _check(fail, v)
    if len(v) != 1:
        return 'length'
    (b,) = v
    return _lead(b)[0]


def tail_reason(v):
    fail = make_fail('tail_reason')
    _check(fail, v)
    if len(v) != 1:
        return 'length'
    (b,) = v
    if b < 128 or b > 191:
        return 'tail'
    return 'ok'


def _cp_reason(cp):
    if cp < 0:
        return 'negative'
    if cp > 1114111:
        return 'range'
    if cp >= 55296 and cp <= 57343:
        return 'surrogate'
    return 'ok'


def codepoint_reason(cp):
    fail = make_fail('codepoint_reason')
    if type(cp) is not int:
        fail('bad_type:value')
    return _cp_reason(cp)


def encoded_length(cp):
    fail = make_fail('encoded_length')
    if type(cp) is not int:
        fail('bad_type:value')
    if _cp_reason(cp) != 'ok':
        fail('bad_value:value.codepoint')
    if cp < 128:
        return 1
    if cp < 2048:
        return 2
    if cp < 65536:
        return 3
    return 4


def encode_codepoint(cp):
    fail = make_fail('encode_codepoint')
    if type(cp) is not int:
        fail('bad_type:value')
    if _cp_reason(cp) != 'ok':
        fail('bad_value:value.codepoint')
    if cp < 128:
        return bytes([cp])
    if cp < 2048:
        return bytes([192 + cp // 64, 128 + cp % 64])
    if cp < 65536:
        return bytes([224 + cp // 4096, 128 + cp // 64 % 64, 128 + cp % 64])
    return bytes([240 + cp // 262144, 128 + cp // 4096 % 64, 128 + cp // 64 % 64, 128 + cp % 64])


def decode_utf8(v):
    fail = make_fail('decode_utf8')
    _check(fail, v)
    (r, lens, cps) = _scan(v, False)
    if r != 'ok':
        fail('bad_value:value.utf8')
    return tuple(cps)


def char_lengths(v):
    fail = make_fail('char_lengths')
    _check(fail, v)
    (r, lens, cps) = _scan(v, False)
    if r != 'ok':
        fail('bad_value:value.utf8')
    return tuple(lens)
