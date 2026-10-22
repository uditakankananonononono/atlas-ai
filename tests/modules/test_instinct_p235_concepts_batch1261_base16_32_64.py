"""Tests for p235 concepts batch 1261: RFC 4648 Base16/32/64 (plus base64url/base32hex) as a grammar over caller-supplied text, the section 3.5 canonical pad-bit checks, and a base16 octet extractor. Pure functions over caller data; claims asserted False."""
import ast
import builtins
import importlib.util
import inspect
import os
import re
import signal
import subprocess
import sys
import traceback
import types

import pytest
import random
from importlib.util import find_spec

REG = 'app.modules.instinct_doc.p235_concepts_registry'
import app.modules.instinct_doc.p235_concepts_batch1261_base16_32_64 as m  # noqa: E402
MODPATH = m.__file__


def _prefix():
    spec = importlib.util.spec_from_file_location('b1261_pfx', MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        return str(e)[:-len('x:c')]


PFX = _prefix()

DOC_EXACT = 'p235 concepts batch 1261 (rev 0): RFC 4648, The Base16, Base32, and Base64 Data Encodings, as a grammar over caller-supplied text: alphabet membership, block length, pad placement and pad count for the base64 (section 4), base64url (section 5), base32 (section 6) and base32hex (section 7) encodings, the case-insensitive base16 form (section 8), the section 3.5 canonical-form pad-bit checks, and a base16 octet extractor. Pure functions; no retrieval, no network, no clock, no registries. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it performs no encoding or decoding of caller data beyond the base16 octet extraction named below, and it defines no format.\n\nLIVE SOURCES (fetched 2026-10-22; quotes below are verbatim from these files, mechanically matched with whitespace collapsed):\n- RFC 4648 text, rfc-editor (35491 bytes, sha256 84e14418f795d503be5f34bf23ce4ebaa119e9ec7c9f667d8caeb111385b178f).\n- rfc-editor info page for RFC 4648 (231933 bytes, sha256 ae5d74008d0608c800cd959cd93c59834d29c04193781f2121206d269e836972): it lists Obsoletes: RFC 3548, and shows no Obsoleted by entry and no Updated by entry. CLAIMS current is still False.\n- The full rfc-editor errata index (11775016 bytes, sha256 23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c) contains exactly six RFC 4648 records (count from errata.json and not independently confirmed): EID 2837, status Verified, type Editorial, section 16.2 (a reference URL); EID 4889, status Reported, type Technical, section 6 (wording of the base32 zero-bit padding description); EID 5855, status Verified, type Editorial, section 10 (a test-vector presentation note); EID 7514, status Verified, type Editorial, section 3.5 (the "do not hold" verb typo; the quote below preserves the live text); EID 8669, status Reported, type Technical, section 4 (wording of the base64 24-bit group description); EID 9030, status Verified, type Editorial, section 5 (a pad-character percent-encoding note). The two Reported-Technical errata concern the encoding-PROCESS descriptions; this module validates text form only, anchored on section 3.5 and the case lists, so its rules are unchanged; no departure is taken from the live text.\n\nSOURCED rules:\n- Non-alphabet characters: "Implementations MUST reject the encoded data if it contains characters outside the base alphabet" (section 3.3, MUST-strength here: no referring specification relaxes it for these functions). Line feeds are never added or accepted: "Implementations MUST NOT add line feeds to base-encoded data unless the specification referring to this document explicitly directs base encoders to add line feeds after a specific number of characters."\n- Padding: "Implementations MUST include appropriate pad characters at the end of encoded data unless the specification referring to this document explicitly states otherwise." These functions implement the general case, so padding is required where the encoding defines it: "The base64 and base32 alphabets use padding, as described below in sections 4 and 6, but the base16 alphabet does not need it; see section 8."\n- Base 64 pad cases: "(2) The final quantum of encoding input is exactly 8 bits; here, the final unit of encoded output will be two characters followed by two "=" padding characters." "(3) The final quantum of encoding input is exactly 16 bits; here, the final unit of encoded output will be three characters followed by one "=" padding character."\n- Base 32 pad cases: "(2) The final quantum of encoding input is exactly 8 bits; here, the final unit of encoded output will be two characters followed by six "=" padding characters." ... "(5) The final quantum of encoding input is exactly 32 bits; here, the final unit of encoded output will be seven characters followed by one "=" padding character." (the 16-bit and 24-bit cases give four/four and five/three characters/pads respectively).\n- base64url: "This encoding is technically identical to the previous one, except for the 62:nd and 63:rd alphabet character, as indicated in Table 2." "This encoding should not be regarded as the same as the "base64" encoding and should not be referred to as only "base64"."\n- base32hex: "This encoding is identical to the previous one, except for the alphabet. The new alphabet is found in Table 4." "This encoding should not be regarded as the same as the "base32" encoding and should not be referred to as only "base32"."\n- Base 16: "Essentially, Base 16 encoding is the standard case- insensitive hex encoding and may be referred to as "base16" or "hex"." "Unlike base 32 and base 64, no special padding is necessary since a full code word is always available."\n- Canonical form: "These pad bits MUST be set to zero by conforming encoders" "If this property do not hold, there is no canonical representation of base-encoded data, and multiple base- encoded strings can be decoded to the same binary data." "If this property (and others discussed in this document) holds, a canonical encoding is guaranteed."\n- Test vectors (section 10, exercised in the tests): "BASE64("foobar") = "Zm9vYmFy"" "BASE32("foobar") = "MZXW6YTBOI======"" "BASE32-HEX("foobar") = "CPNMUOJ1E8======"" "BASE16("foobar") = "666F6F626172""\n- Base 32 bit order: "When a bit stream is encoded via the base 32 encoding, the bit stream must be presumed to be ordered with the most-significant- bit first."\n\nDECISIONS AND NOT_CLAIMED:\n1. Case. base16 accepts both upper- and lowercase (section 8 calls it the "standard case-insensitive hex encoding"; SOURCED). base32 and base32hex are uppercase-only as their tables define them; the case-insensitivity in section 6 is a design goal for the transport ("needs to be case insensitive"), not a licence for decoders, and liberal lowercase acceptance is NOT_CLAIMED: a lowercase base32 character reports char. base64 and base64url are case-sensitive by construction.\n2. Padding. Only the strict padded form is validated (the section 3.2 general case). Unpadded forms permitted "if the data length is known implicitly" (section 5) are a referencing-specification choice and are NOT_CLAIMED: a short final quantum reports length, and missing pads report length, never ok.\n3. Decoding. No binary decoding is provided except base16_octets, which extracts the octet values of a valid base16 string; full decoding semantics (including the bit ordering in "When a bit stream is encoded via the base 32 encoding, the bit stream must be presumed to be ordered with the most-significant- bit first.") are NOT_CLAIMED. The canonical checks look only at the pad bits named in section 3.5, via alphabet positions, without decoding.\n4. Caps (OURS, all raising): _LEN_CAP 1024 characters per input. The grammar itself is unbounded.\n\nFUNCTIONS, in this order: base64_reason, base64url_reason, base32_reason, base32hex_reason, base16_reason, base64_canon_reason, base64url_canon_reason, base32_canon_reason, base32hex_canon_reason, base16_octets. The reason functions return the string "ok" or a reason string; base16_octets returns a tuple of octet values (0-255) in order. Errors are ValueError with the text P235:<function>:<code>, where <function> is the owning function and <code> is bad_type:value (non-str input), bad_value:value.length (over _LEN_CAP), or bad_value:value.base16 (base16_octets on an invalid string).\n\nREASONS, in check order (the first failure decides):\n- base64_reason / base64url_reason / base32_reason / base32hex_reason: bad_type:value (raise), bad_value:value.length (raise); then length (total length not a multiple of the block, 4 for the 64-family and 8 for the 32-family), char (a character outside the alphabet before the first "="), pad.placement (a non-"=" character after the first "="), pad.count (a pad count the encoding cannot produce: the 64-family allows 1 or 2, the 32-family allows 1, 3, 4 or 6); ok. The empty string is ok.\n- base16_reason: bad_type:value (raise), bad_value:value.length (raise); then length (odd length), char (outside 0-9 A-F a-f); ok. The empty string is ok.\n- base64_canon_reason / base64url_canon_reason / base32_canon_reason / base32hex_canon_reason: bad_type:value (raise), bad_value:value.length (raise); then the matching base reason if not ok, then pad.bits (the final data character carries nonzero pad bits: with pad 2 in the 64-family the low 4 bits, with pad 1 the low 2 bits; with pad 6/4/3/1 in the 32-family the low 2/4/1/3 bits); ok.\n- base16_octets: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.base16 (raise, when base16_reason would not return ok).\n\nOUTPUT ORDER: reason strings are the exact dotted codes listed above; base16_octets emits octets left to right, high nibble first, per the section 8 "high-order bit" reading of each 8-bit group.'

QUOTES = ['Implementations MUST reject the encoded data if it contains characters outside the base alphabet', 'These pad bits MUST be set to zero by conforming encoders', 'Implementations MUST NOT add line feeds to base-encoded data unless the specification referring to this document explicitly directs base encoders to add line feeds after a specific number of characters.', 'Implementations MUST include appropriate pad characters at the end of encoded data unless the specification referring to this document explicitly states otherwise.', 'The base64 and base32 alphabets use padding, as described below in sections 4 and 6, but the base16 alphabet does not need it; see section 8.', '(2) The final quantum of encoding input is exactly 8 bits; here, the final unit of encoded output will be two characters followed by two "=" padding characters.', '(3) The final quantum of encoding input is exactly 16 bits; here, the final unit of encoded output will be three characters followed by one "=" padding character.', '(2) The final quantum of encoding input is exactly 8 bits; here, the final unit of encoded output will be two characters followed by six "=" padding characters.', '(5) The final quantum of encoding input is exactly 32 bits; here, the final unit of encoded output will be seven characters followed by one "=" padding character.', 'This encoding is technically identical to the previous one, except for the 62:nd and 63:rd alphabet character, as indicated in Table 2.', 'This encoding should not be regarded as the same as the "base64" encoding and should not be referred to as only "base64".', 'This encoding is identical to the previous one, except for the alphabet. The new alphabet is found in Table 4.', 'This encoding should not be regarded as the same as the "base32" encoding and should not be referred to as only "base32".', 'Essentially, Base 16 encoding is the standard case- insensitive hex encoding and may be referred to as "base16" or "hex".', 'Unlike base 32 and base 64, no special padding is necessary since a full code word is always available.', 'When a bit stream is encoded via the base 32 encoding, the bit stream must be presumed to be ordered with the most-significant- bit first.', 'If this property do not hold, there is no canonical representation of base-encoded data, and multiple base- encoded strings can be decoded to the same binary data.', 'If this property (and others discussed in this document) holds, a canonical encoding is guaranteed.', 'BASE64("foobar") = "Zm9vYmFy"', 'BASE32("foobar") = "MZXW6YTBOI======"', 'BASE32-HEX("foobar") = "CPNMUOJ1E8======"', 'BASE16("foobar") = "666F6F626172"']


class _Alarm(AssertionError):
    pass


@pytest.fixture(autouse=True)
def _alarm():
    def handler(signum, frame):
        raise _Alarm('ALARM test exceeded 60 seconds (hang guard only)')
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 60.0)
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, old)


@pytest.fixture
def mp(monkeypatch):
    return monkeypatch


def fresh(name='b1261_fresh'):
    spec = importlib.util.spec_from_file_location(name, MODPATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod


def E(fn, code):
    return ('err', PFX + fn + ':' + code)


def _read(path):
    with open(path) as fh:
        return fh.read()


def _readlines(path):
    with open(path) as fh:
        return fh.readlines()

def run(fn, *args, mod=None):
    try:
        return ('ok', getattr(mod or m, fn)(*args))
    except ValueError as e:
        return ('err', str(e))


NAMES = ('base64_reason', 'base64url_reason', 'base32_reason', 'base32hex_reason', 'base16_reason',
         'base64_canon_reason', 'base64url_canon_reason', 'base32_canon_reason', 'base32hex_canon_reason',
         'base16_octets')
ARGSPEC = {fn: (('value', str),) for fn in NAMES}
PRIVATE = ('_LEN_CAP', '_B64', '_B64U', '_B32', '_B32H', '_B16', '_B16L',
           '_B64_IDX', '_B64U_IDX', '_B32_IDX', '_B32H_IDX', '_B16_IDX',
           '_B64_PADS', '_B32_PADS', '_B64_ZERO', '_B32_ZERO',
           '_padded_reason', '_pad_count', '_canon_reason')

# ---- independent oracle: regexes plus re-encode checks via the stdlib, written separately from the module's hand loops ----
_A64 = 'A-Za-z0-9+/'
_A64U = 'A-Za-z0-9\\-_'
_A32 = 'A-Z2-7'
_A32H = '0-9A-V'
_A16 = '0-9A-Fa-f'
_RE64 = re.compile(r'^(?:[%s]{4})*(?:[%s]{2}==|[%s]{3}=)?$' % (_A64, _A64, _A64))
_RE64U = re.compile(r'^(?:[%s]{4})*(?:[%s]{2}==|[%s]{3}=)?$' % (_A64U, _A64U, _A64U))
_R32TAIL = r'(?:[%s]{2}={6}|[%s]{4}={4}|[%s]{5}={3}|[%s]{7}=)?$'
_RE32 = re.compile((r'^(?:[%s]{8})*' % _A32) + (_R32TAIL % ((_A32,) * 4)))
_RE32H = re.compile((r'^(?:[%s]{8})*' % _A32H) + (_R32TAIL % ((_A32H,) * 4)))
_RE16 = re.compile(r'^(?:[%s]{2})*$' % _A16)

def _o_padded(v, alpha, block, pads, full_re):
    if len(v) % block != 0:
        return 'length'
    i = v.find('=')
    body = v if i < 0 else v[:i]
    if re.search('[^' + alpha + ']', body):
        return 'char'
    tail = '' if i < 0 else v[i:]
    if re.search('[^=]', tail):
        return 'pad.placement'
    if len(tail) not in pads + (0,):
        return 'pad.count'
    if not full_re.match(v):
        return '??oracle-mismatch'
    return 'ok'


def o_b64(v):
    return _o_padded(v, _A64, 4, (1, 2), _RE64)


def o_b64u(v):
    return _o_padded(v, _A64U, 4, (1, 2), _RE64U)


def o_b32(v):
    return _o_padded(v, _A32, 8, (1, 3, 4, 6), _RE32)


def o_b32h(v):
    return _o_padded(v, _A32H, 8, (1, 3, 4, 6), _RE32H)


def o_b16(v):
    if len(v) % 2 != 0:
        return 'length'
    if re.search('[^' + _A16 + ']', v):
        return 'char'
    return 'ok'


import base64 as _b64mod
import binascii as _binascii

_B32_TO_32H = str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567', '0123456789ABCDEFGHIJKLMNOPQRSTUV')
_32H_TO_B32 = str.maketrans('0123456789ABCDEFGHIJKLMNOPQRSTUV', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567')


def _o_canon(reenc):
    try:
        return 'ok' if reenc() else 'pad.bits'
    except Exception:
        return '??oracle-error'


def o_b64_canon(v):
    if o_b64(v) != 'ok':
        return o_b64(v)
    return _o_canon(lambda: _b64mod.b64encode(_b64mod.b64decode(v, validate=True)).decode() == v)


def o_b64u_canon(v):
    if o_b64u(v) != 'ok':
        return o_b64u(v)
    return _o_canon(lambda: _b64mod.urlsafe_b64encode(_b64mod.urlsafe_b64decode(v)).decode() == v)


def o_b32_canon(v):
    if o_b32(v) != 'ok':
        return o_b32(v)
    return _o_canon(lambda: _b64mod.b32encode(_b64mod.b32decode(v, casefold=False)).decode() == v)


def o_b32h_canon(v):
    if o_b32h(v) != 'ok':
        return o_b32h(v)
    def f():
        t = v.translate(_32H_TO_B32)
        return _b64mod.b32encode(_b64mod.b32decode(t, casefold=False)).decode().translate(_B32_TO_32H) == v
    return _o_canon(f)


def o_b16_octets(v):
    return tuple(_binascii.unhexlify(v))


# ---- RFC 4648 section 10 test vectors as oracle pins ----
V64 = {'': '', 'f': 'Zg==', 'fo': 'Zm8=', 'foo': 'Zm9v', 'foob': 'Zm9vYg==', 'fooba': 'Zm9vYmE=', 'foobar': 'Zm9vYmFy'}
V32 = {'': '', 'f': 'MY======', 'fo': 'MZXQ====', 'foo': 'MZXW6===', 'foob': 'MZXW6YQ=', 'fooba': 'MZXW6YTB', 'foobar': 'MZXW6YTBOI======'}
V32H = {'': '', 'f': 'CO======', 'fo': 'CPNG====', 'foo': 'CPNMU===', 'foob': 'CPNMUOG=', 'fooba': 'CPNMUOJ1', 'foobar': 'CPNMUOJ1E8======'}
V16 = {'': '', 'f': '66', 'fo': '666F', 'foo': '666F6F', 'foob': '666F6F62', 'fooba': '666F6F6261', 'foobar': '666F6F626172'}


def test_rfc_section10_vectors_valid_and_canonical():
    for raw, enc in V64.items():
        assert m.base64_reason(enc) == 'ok'
        assert m.base64_canon_reason(enc) == 'ok'
        assert _b64mod.b64encode(raw.encode()).decode() == enc
    for raw, enc in V32.items():
        assert m.base32_reason(enc) == 'ok'
        assert m.base32_canon_reason(enc) == 'ok'
        assert _b64mod.b32encode(raw.encode()).decode() == enc
    for raw, enc in V32H.items():
        assert m.base32hex_reason(enc) == 'ok'
        assert m.base32hex_canon_reason(enc) == 'ok'
    for raw, enc in V16.items():
        assert m.base16_reason(enc) == 'ok'
        assert m.base16_reason(enc.lower()) == 'ok'
        assert _b64mod.b16encode(raw.encode()).decode() == enc


def test_base16_octets_over_vectors_and_roundtrip():
    for raw, enc in V16.items():
        assert m.base16_octets(enc) == tuple(raw.encode())
        assert m.base16_octets(enc.lower()) == tuple(raw.encode())
    assert m.base16_octets('') == ()
    assert m.base16_octets('00ff10') == (0, 255, 16)


def test_base64url_vectors_and_alphabet_split():
    enc = _b64mod.urlsafe_b64encode(b'\xfb\xff\xfe').decode()
    assert enc == '-__-' and m.base64url_reason(enc) == 'ok'
    assert m.base64_reason(enc) == 'char'
    std = _b64mod.b64encode(b'\xfb\xff\xfe').decode()
    assert std == '+//+' and m.base64_reason(std) == 'ok'
    assert m.base64url_reason(std) == 'char'
    assert m.base64url_canon_reason(enc) == 'ok'
    assert m.base32hex_reason('MZXW6YTB') == 'char'
    assert m.base32_reason('CPNMUOJ1') == 'char'


def test_noncanonical_pad_bits_detected_per_pad_count():
    # 64-family: '==' leaves the low 4 bits, '=' the low 2 bits of the final char.
    assert m.base64_canon_reason('Zh==') == 'pad.bits'
    assert m.base64_canon_reason('Zl==') == 'pad.bits'
    assert m.base64_canon_reason('Zg==') == 'ok'
    assert m.base64_canon_reason('Zm9=') == 'pad.bits'
    assert m.base64_canon_reason('Zm8=') == 'ok'
    assert m.base64url_canon_reason('Zh==') == 'pad.bits'
    # 32-family: pads 6/4/3/1 leave the low 2/4/1/3 bits.
    assert m.base32_canon_reason('MZ======') == 'pad.bits'
    assert m.base32_canon_reason('MZXR====') == 'pad.bits'
    assert m.base32_canon_reason('MZXW7===') == 'pad.bits'
    assert m.base32_canon_reason('MZXW6YR=') == 'pad.bits'
    assert m.base32_canon_reason('MY======') == 'ok'
    assert m.base32_canon_reason('MZXW6YQ=') == 'ok'
    assert m.base32hex_canon_reason('CP======') == 'pad.bits'
    assert m.base32hex_canon_reason('CPNMUOH=') == 'pad.bits'
    assert m.base32hex_canon_reason('CPNMUOG=') == 'ok'
    # canon functions report the base reason first.
    assert m.base64_canon_reason('Zg=') == 'length'
    assert m.base32_canon_reason('MY=====!') == 'pad.placement'
    assert m.base32_canon_reason('MY=========') == 'length'


def test_pad_shape_rejections():
    assert m.base64_reason('Zg=') == 'length'
    assert m.base64_reason('Zg===') == 'length'
    assert m.base64_reason('Z===') == 'pad.count'
    assert m.base64_reason('====') == 'pad.count'
    assert m.base64_reason('=AAA') == 'pad.placement'
    assert m.base64_reason('AA=A') == 'pad.placement'
    assert m.base64_reason('AAA=') == 'ok'
    assert m.base64_reason('AA==') == 'ok'
    assert m.base64_reason('Zm9v') == 'ok'
    assert m.base64_reason('') == 'ok'
    assert m.base64_reason('Zm9!') == 'char'
    assert m.base64_reason('Zm 9') == 'char'
    assert m.base64_reason('Zm9\n') == 'char'
    assert m.base32_reason('M=======') == 'pad.count'
    assert m.base32_reason('MM======') == 'ok'
    assert m.base32_reason('MMM=====') == 'pad.count'
    assert m.base32_reason('MMMM====') == 'ok'
    assert m.base32_reason('MMMMM===') == 'ok'
    assert m.base32_reason('MMMMMM==') == 'pad.count'
    assert m.base32_reason('MMMMMMM=') == 'ok'
    assert m.base32_reason('MMMMMMMM') == 'ok'
    assert m.base32_reason('mmmm====') == 'char'
    assert m.base32hex_reason('mmmm====') == 'char'
    assert m.base16_reason('ABC') == 'length'
    assert m.base16_reason('AG') == 'char'
    assert m.base16_reason('==') == 'char'
    assert m.base16_reason('') == 'ok'


def test_both_bad_check_order_pins():
    # length beats char; char beats pad.placement; placement beats pad.count.
    assert m.base64_reason('!') == 'length'
    assert m.base64_reason('!') != 'char'
    assert m.base64_reason('!===') == 'char'
    assert m.base64_reason('!==A') == 'char'
    assert m.base64_reason('==A=') == 'pad.placement'
    assert m.base64_reason('A===') == 'pad.count'
    assert m.base32_reason('!===') == 'length'
    assert m.base32_reason('!=======') == 'char'
    assert m.base32_reason('==M=====') == 'pad.placement'
    assert m.base16_reason('!') == 'length'
    assert m.base16_reason('!A') == 'char'
    # cap raise beats every content reason.
    over = '!' * 2000
    assert run('base64_reason', over) == E('base64_reason', 'bad_value:value.length')
    assert run('base16_reason', over + '!') == E('base16_reason', 'bad_value:value.length')
    assert run('base64_canon_reason', 'Zg=='.ljust(2000, 'A')) == E('base64_canon_reason', 'bad_value:value.length')


def test_constants_exact():
    assert m._LEN_CAP == 1024
    assert m._B64 == 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    assert m._B64U == 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
    assert m._B32 == 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
    assert m._B32H == '0123456789ABCDEFGHIJKLMNOPQRSTUV'
    assert m._B16 == '0123456789ABCDEF'
    assert m._B16L == '0123456789abcdef'
    assert m._B64_PADS == (1, 2)
    assert m._B32_PADS == (1, 3, 4, 6)
    assert m._B64_ZERO == {1: 4, 2: 16}
    assert m._B32_ZERO == {1: 8, 3: 2, 4: 16, 6: 4}
    assert m.CLAIMS == {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False}
    assert type(m.CLAIMS) is dict and all(v is False for v in m.CLAIMS.values())
    assert m.SCOPE.startswith('RFC 4648 over caller-supplied text')
    assert 'unpadded forms' in m.NOT_CLAIMED
    assert 'RFC 3548' in m.ADJACENT[2]


def test_constants_exact_contents():
    assert m.SCOPE == "RFC 4648 over caller-supplied text: the Base16, Base32, Base64 (and the base64url and base32hex alphabet variants) data encoding grammars - alphabet membership, block length, pad placement and pad count, the section 3.5 canonical pad-bit checks, and a base16 octet extractor. Pure functions; no retrieval, no network, no clock, no registries."
    assert m.NOT_CLAIMED == ('standard', 'authority', 'certification', 'currency', 'completeness',
                             'encoding process', 'binary decoding (beyond base16_octets)', 'unpadded forms', 'liberal lowercase base32')
    assert m.ADJACENT == ('RFC 2045 MIME base64 Content-Transfer-Encoding (b1204 covers the field value; the 76-character line limit is not this grammar)',
                          'RFC 3986 token68 usages of base64 text (b1123, b1199 treat it as opaque)',
                          'RFC 3548 (obsoleted by RFC 4648, per the info page)')


def test_index_maps_are_complete_and_exact():
    for alpha, idx in ((m._B64, m._B64_IDX), (m._B64U, m._B64U_IDX), (m._B32, m._B32_IDX), (m._B32H, m._B32H_IDX)):
        assert len(idx) == len(alpha)
        for k in range(len(alpha)):
            assert idx[alpha[k]] == k
    assert len(m._B16_IDX) == 22
    for k in range(16):
        assert m._B16_IDX[m._B16[k]] == k and m._B16_IDX[m._B16L[k]] == k


def test_order_docstrings_and_private_names():
    for fn in NAMES:
        f = getattr(m, fn)
        assert callable(f) and f.__doc__ is None
    assert m.make_fail.__doc__ is None
    for p in PRIVATE:
        obj = getattr(m, p)
        if callable(obj):
            assert obj.__doc__ is None, p


def test_public_function_definition_order_pinned():
    tree = ast.parse(_read(MODPATH))
    defs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')]
    assert defs == ['base64_reason', 'base64url_reason', 'base32_reason', 'base32hex_reason', 'base16_reason',
                    'base64_canon_reason', 'base64url_canon_reason', 'base32_canon_reason', 'base32hex_canon_reason',
                    'base16_octets']


def test_header_quotes_are_in_the_header_and_distinct():
    assert len(QUOTES) == len(set(QUOTES)) and len(QUOTES) >= 20
    for qt in QUOTES:
        assert qt in DOC_EXACT


def test_header_names_erratum_sources_and_functions():
    assert m.__doc__ == DOC_EXACT
    for eid in ('2837', '4889', '5855', '7514', '8669', '9030'):
        assert 'EID ' + eid in DOC_EXACT
    assert '84e14418f795d503be5f34bf23ce4ebaa119e9ec7c9f667d8caeb111385b178f' in DOC_EXACT
    assert 'ae5d7400' in DOC_EXACT
    assert '23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c' in DOC_EXACT
    assert 'Obsoletes: RFC 3548' in DOC_EXACT
    assert 'not independently confirmed' in DOC_EXACT
    for fn in NAMES:
        assert fn in DOC_EXACT


def test_module_imports_and_source_bans():
    tree = ast.parse(_read(MODPATH))
    imps = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert len(imps) == 2
    src = _read(MODPATH)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in ('base64', 'binascii', 're', 'ord', 'chr'):
            raise AssertionError('forbidden name referenced: %s' % node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('ord', 'chr', 'bin', 'hex'):
            raise AssertionError('forbidden call: %s' % node.func.id)
    # no str methods on input: no attribute calls on parameters named v
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'v':
                raise AssertionError('str method on input: %s' % node.func.attr)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value is True:
            raise AssertionError('literal True constant')
        if isinstance(node, ast.BoolOp):
            for c in node.values:
                if isinstance(c, ast.Constant) and isinstance(c.value, bool):
                    raise AssertionError('bool constant in BoolOp')


def test_source_and_tests_have_no_vacuous_assertions():
    banned = ['or' + ' True', 'if' + ' False', 'else' + ' True', 'and' + ' False', 'or' + ' False', 'assert' + ' True']
    src = _read(MODPATH)
    tsrc = _read(__file__)
    for b in banned:
        assert b not in src, (MODPATH, b)
        assert b not in tsrc, (__file__, b)


class _Hostile(str):
    pass


def _mkhostile():
    class MM(type):
        def __eq__(self, other):
            return True
    class S(str, metaclass=MM):
        pass
    return S


@pytest.mark.parametrize('fn', NAMES)
def test_every_argument_is_an_exact_type_by_identity(fn):
    bad = [None, 1, True, False, 0, b'Zm9v', bytearray(b'Zg=='), ['A'], ('A',), {'A'}, {'a': 1}, 3.5, _Hostile('Zm9v'), _mkhostile()('Zm9v')]
    for b in bad:
        assert run(fn, b) == E(fn, 'bad_type:value'), (fn, b)


def test_bool_is_refused_where_a_string_is_expected():
    for fn in NAMES:
        assert run(fn, True) == E(fn, 'bad_type:value')
        assert run(fn, False) == E(fn, 'bad_type:value')


def test_len_cap_at_cap_and_cap_plus_one_on_every_function():
    for fn in NAMES:
        at = 'A' * 1024
        assert run(fn, at)[0] == 'ok'
        over = 'A' * 1025
        assert run(fn, over) == E(fn, 'bad_value:value.length'), fn


def test_cap_checks_fire_before_content():
    for fn in NAMES:
        assert run(fn, '!' * 1025) == E(fn, 'bad_value:value.length')
    # at the cap, content reasons still surface (no raise) for the nine reason functions
    for fn in NAMES[:9]:
        assert run(fn, '!' * 1024) == ('ok', 'char'), fn
    assert run('base16_reason', '!' * 1024) == ('ok', 'char')
    assert run('base16_octets', '!' * 1024) == E('base16_octets', 'bad_value:value.base16')
    assert run('base16_octets', 'A' * 1024) == ('ok', (170,) * 512)


def test_inputs_are_untouched_and_results_fresh():
    v = 'Zm9vYg=='
    assert m.base64_reason(v) == 'ok' and v == 'Zm9vYg=='
    a = m.base16_octets('666F')
    b = m.base16_octets('666F')
    assert a == b == (102, 111) and a is not b
    assert type(a) is tuple and type(a[0]) is int and type(a[1]) is int


def test_base16_octets_raises_on_invalid():
    assert run('base16_octets', '6G') == E('base16_octets', 'bad_value:value.base16')
    assert run('base16_octets', '666') == E('base16_octets', 'bad_value:value.base16')
    assert run('base16_octets', 'A' * 1025) == E('base16_octets', 'bad_value:value.length')
    assert run('base16_octets', None) == E('base16_octets', 'bad_type:value')


# ---- fuzz: mixed junk vs oracle, 1200 draws x 3 seeds ----
_JUNK64 = 'ABCZabz09+/=! \n-_'
_JUNK64U = 'ABCZabz09-_=! \n+/'
_JUNK32 = 'ABMZT27=! \na0189'
_JUNK32H = '09AMV=! \naWXYZ'
_JUNK16 = '09AFaf=! \nGgZz'


def _fuzz(rng, alpha, n):
    return ''.join(rng.choice(alpha) for _ in range(rng.randrange(n)))


@pytest.mark.parametrize('seed', [1, 2, 3])
def test_fuzz_reason_functions_against_oracle_1200(seed):
    rng = random.Random('b1261:%d' % seed)
    for _ in range(1200):
        v = _fuzz(rng, _JUNK64, 20)
        assert m.base64_reason(v) == o_b64(v), v
        v = _fuzz(rng, _JUNK64U, 20)
        assert m.base64url_reason(v) == o_b64u(v), v
        v = _fuzz(rng, _JUNK32, 24)
        assert m.base32_reason(v) == o_b32(v), v
        v = _fuzz(rng, _JUNK32H, 24)
        assert m.base32hex_reason(v) == o_b32h(v), v
        v = _fuzz(rng, _JUNK16, 12)
        assert m.base16_reason(v) == o_b16(v), v


@pytest.mark.parametrize('seed', [1, 2, 3])
def test_fuzz_canon_and_octets_against_oracle_1200(seed):
    rng = random.Random('b1261c:%d' % seed)
    for _ in range(1200):
        raw = bytes(rng.randrange(256) for _ in range(rng.randrange(12)))
        v = _b64mod.b64encode(raw).decode()
        assert m.base64_reason(v) == 'ok' and m.base64_canon_reason(v) == o_b64_canon(v)
        # flip bits in the last data char before pads to exercise pad.bits
        if v.endswith('=='):
            i = _B64 = None
            body = v[:-2]
            alt = 'A' if body[-1] != 'A' else 'B'
            w = body[:-1] + alt + '=='
            assert m.base64_canon_reason(w) == o_b64_canon(w), w
        elif v.endswith('='):
            body = v[:-1]
            alt = 'A' if body[-1] != 'A' else 'B'
            w = body[:-1] + alt + '='
            assert m.base64_canon_reason(w) == o_b64_canon(w), w
        v = _b64mod.urlsafe_b64encode(raw).decode()
        assert m.base64url_reason(v) == 'ok' and m.base64url_canon_reason(v) == 'ok'
        v = _b64mod.b32encode(raw).decode()
        assert m.base32_reason(v) == 'ok' and m.base32_canon_reason(v) == o_b32_canon(v)
        v = v.translate(_B32_TO_32H)
        assert m.base32hex_reason(v) == 'ok' and m.base32hex_canon_reason(v) == o_b32h_canon(v)
        v = _b64mod.b16encode(raw).decode()
        assert m.base16_reason(v) == 'ok' and m.base16_octets(v) == o_b16_octets(v)


# ---- registry guard, import log, namespace ----------------------------------------------------------------------
def test_registry_absent_uses_local_fallback(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh()
    assert mod.make_fail.__module__ == mod.__name__
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert run('base64_reason', 1, mod=mod) == ('err', 'P235:base64_reason:bad_type:value')


def test_registry_present_is_used_by_every_function(mp):
    fake = types.ModuleType(REG)
    fake.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE:%s:%s' % (name, code))))
    mp.setitem(sys.modules, REG, fake)
    mod = fresh()
    assert mod.make_fail is fake.make_fail
    for fn in NAMES:
        spec = ARGSPEC[fn]
        args = [g for _n, g in spec]
        args[0] = None
        assert run(fn, *args, mod=mod) == ('err', 'FAKE:%s:bad_type:%s' % (fn, spec[0][0]))


def test_registry_guard_foreign_name_never_consults_find_spec(mp):
    real = builtins.__import__
    spied = []
    err = ModuleNotFoundError('foreign', name='some.other.module')

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda name: spied.append(name) or object())
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ModuleNotFoundError) as e:
        fresh()
    assert e.value is err and spied == []


def test_registry_guard_registry_name_with_spec_found_is_reraised(mp):
    real = builtins.__import__
    spied = []
    err = ModuleNotFoundError('inner', name=REG)

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda name: spied.append(name) or object())
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ModuleNotFoundError) as e:
        fresh()
    assert e.value is err and spied == [REG]


@pytest.mark.parametrize('nm', [REG, 'some.other.module'])
def test_import_error_is_not_a_module_not_found_error(mp, nm):
    real = builtins.__import__
    err = ImportError('x', name=nm)

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda n: None)
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ImportError) as e:
        fresh()
    assert e.value is err


IMPORTS = [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]
NAMESPACE = (['find_spec', '_REG', 'make_fail', 'SCOPE', 'NOT_CLAIMED', 'CLAIMS', 'ADJACENT'] +
             list(PRIVATE) + list(NAMES))
CALLS = [(fn, ('Zm9v',), (None,)) for fn in NAMES]


@pytest.mark.parametrize('world', ['absent', 'present', 'foreign', 'registry_raise'])
def test_import_log_and_namespace_on_every_path(mp, world):
    real = builtins.__import__
    seen = []
    spied = []
    err = ModuleNotFoundError('x', name=('some.other.module' if world == 'foreign' else REG))
    fake = types.ModuleType(REG)
    fake.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE')))

    def spy(name):
        spied.append(name)
        return None if world == 'absent' else object()

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == fresh.__defaults__[0]:
            seen.append((n, tuple(fromlist or ()), level))
        if n == REG and world in ('foreign', 'registry_raise'):
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, fake if world == 'present' else None)
    mp.setattr(importlib.util, 'find_spec', spy)
    mp.setattr(builtins, '__import__', hook)
    if world in ('foreign', 'registry_raise'):
        with pytest.raises(ModuleNotFoundError) as e:
            fresh()
        assert e.value is err
        assert seen == IMPORTS
        assert spied == ([] if world == 'foreign' else [REG])
        return
    mod = fresh()
    assert seen == IMPORTS
    assert spied == ([REG] if world == 'absent' else [])
    names = sorted(k for k in vars(mod) if not (k.startswith('__') and k.endswith('__')))
    assert names == sorted(NAMESPACE)
    del seen[:]
    for fn, good, bad in CALLS:
        for args in (good, bad):
            try:
                getattr(mod, fn)(*args)
            except ValueError:
                pass
    assert seen == []


def test_failure_prefix_is_p235_when_the_fallback_is_bound():
    if m.make_fail.__module__ == m.__name__:
        assert PFX == 'P235:'
    assert PFX.endswith(':') and 'x:c' not in PFX


# ---- the shared corpus: every refusal site of every public function, plus reason successes --------------------------
CORPUS = []
for _fn in NAMES:
    for _pos, (_name, _g) in enumerate(ARGSPEC[_fn]):
        _args = [g for _n, g in ARGSPEC[_fn]]
        _args[_pos] = 1
        CORPUS.append((_fn, tuple(_args), 'bad_type:' + _name))
for _fn in NAMES:
    CORPUS.append((_fn, ('x' * 1025,), 'bad_value:value.length'))
CORPUS.append(('base16_octets', ('6G',), 'bad_value:value.base16'))
CORPUS.append(('base16_octets', ('666',), 'bad_value:value.base16'))
CORPUS.append(('base16_octets', ('==',), 'bad_value:value.base16'))
CORPUS2 = [('base64_canon_reason', ('Zg=',), 'length'),
           ('base64_canon_reason', ('Zg',), 'length'),
           ('base64_canon_reason', ('Z===',), 'pad.count'),
           ('base64_canon_reason', ('=Zg=',), 'pad.placement'),
           ('base64url_canon_reason', ('Zg',), 'length'),
           ('base64url_canon_reason', ('Z+==',), 'char'),
           ('base32_canon_reason', ('MY=====',), 'length'),
           ('base32_canon_reason', ('M=======',), 'pad.count'),
           ('base32_canon_reason', ('=Y======',), 'pad.placement'),
           ('base32hex_canon_reason', ('CO=====',), 'length'),
           ('base32hex_canon_reason', ('=O======',), 'pad.placement')]
SUCCESS = [('base64_reason', ('',), 'ok'), ('base64_reason', ('Zg==',), 'ok'),
           ('base64_reason', ('Zg=',), 'length'), ('base64_reason', ('Z!==',), 'char'),
           ('base64_reason', ('=g==',), 'pad.placement'), ('base64_reason', ('Z===',), 'pad.count'),
           ('base64url_reason', ('-__-',), 'ok'), ('base64url_reason', ('Zg=',), 'length'),
           ('base64url_reason', ('Z+==',), 'char'), ('base64url_reason', ('=g==',), 'pad.placement'),
           ('base64url_reason', ('Z===',), 'pad.count'),
           ('base32_reason', ('MY======',), 'ok'), ('base32_reason', ('MY=====',), 'length'),
           ('base32_reason', ('M1======',), 'char'), ('base32_reason', ('=Y======',), 'pad.placement'),
           ('base32_reason', ('MY=======',), 'length'), ('base32_reason', ('M=======',), 'pad.count'),
           ('base32hex_reason', ('CO======',), 'ok'), ('base32hex_reason', ('CW======',), 'char'),
           ('base32hex_reason', ('CO=======',), 'length'), ('base32hex_reason', ('=O======',), 'pad.placement'),
           ('base32hex_reason', ('C=======',), 'pad.count'),
           ('base16_reason', ('666F',), 'ok'), ('base16_reason', ('666f',), 'ok'),
           ('base16_reason', ('666',), 'length'), ('base16_reason', ('6 6F',), 'char'),
           ('base16_reason', ('66G6',), 'char'),
           ('base64_canon_reason', ('Zg==',), 'ok'), ('base64_canon_reason', ('Zh==',), 'pad.bits'),
           ('base64url_canon_reason', ('Zm8=',), 'ok'), ('base64url_canon_reason', ('Zm9=',), 'pad.bits'),
           ('base32_canon_reason', ('MZXW6YQ=',), 'ok'), ('base32_canon_reason', ('MZXW6YR=',), 'pad.bits'),
           ('base32hex_canon_reason', ('CPNMUOG=',), 'ok'), ('base32hex_canon_reason', ('CPNMUOH=',), 'pad.bits'),
           ('base16_octets', ('',), ()), ('base16_octets', ('666f',), (102, 111))]


def drive(mod, pfx=None):
    p = PFX if pfx is None else pfx
    for fn, args, want in CORPUS:
        with pytest.raises(ValueError) as e:
            getattr(mod, fn)(*args)
        assert str(e.value) == p + fn + ':' + want
    for fn, args, want in CORPUS2:
        assert getattr(mod, fn)(*args) == want
    for fn, args, want in SUCCESS:
        assert getattr(mod, fn)(*args) == want


def test_corpus_reaches_every_refusal_code_and_every_success_branch():
    drive(m)
    codes = {(fn, w) for fn, a, w in CORPUS}
    for fn in NAMES:
        assert (fn, 'bad_type:value') in codes
        assert (fn, 'bad_value:value.length') in codes
    byfn = {}
    for f, a, w in SUCCESS:
        byfn.setdefault(f, set()).add(w if isinstance(w, str) else 'ok')
    for fn in ('base64_reason', 'base64url_reason', 'base32_reason', 'base32hex_reason'):
        assert byfn[fn] >= {'ok', 'length', 'char', 'pad.placement', 'pad.count'}, fn
    assert byfn['base16_reason'] >= {'ok', 'length', 'char'}
    for fn in ('base64_canon_reason', 'base64url_canon_reason', 'base32_canon_reason', 'base32hex_canon_reason'):
        assert byfn[fn] >= {'ok', 'pad.bits'}, fn
    assert sum(1 for f, a, w in SUCCESS if f == 'base16_octets') == 2
    sub = {(f, w) for f, a, w in CORPUS2}
    assert ('base64_canon_reason', 'pad.count') in sub
    assert ('base32_canon_reason', 'length') in sub


def test_fallback_failer_world_has_no_imports_one_success_and_every_refusal(mp):
    real = builtins.__import__
    seen = []
    name = 'b1261_fallback_world'

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == name:
            seen.append((n, tuple(fromlist or ()), level))
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(builtins, '__import__', hook)
    mod = fresh(name)
    assert mod.make_fail.__module__ == name
    assert seen == IMPORTS
    del seen[:]
    drive(mod, 'P235:')
    assert seen == []
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert seen == []


def test_every_refusal_goes_through_the_failer_call_site(mp):
    """Stub world: the bound failer raises a sentinel; the last frame inside the module for each refusal is a line starting with fail(."""
    class Stop(Exception):
        pass

    def make(name):
        def fail(code):
            raise Stop(name + ':' + code)
        return fail
    fake = types.ModuleType(REG)
    fake.make_fail = make
    mp.setitem(sys.modules, REG, fake)
    mod = fresh('b1261_site_world')
    sites = set()
    for fn, args, want in [(f, a, f + ':' + w) for f, a, w in CORPUS]:
        with pytest.raises(Stop) as e:
            getattr(mod, fn)(*args)
        assert str(e.value) == want
        frames = [f for f in traceback.extract_tb(e.value.__traceback__) if f.filename == mod.__file__]
        assert frames[-1].line.strip().startswith('fail(')
        sites.add(frames[-1].lineno)
    src = inspect.getsource(mod).split('\n')
    all_sites = {i + 1 for i, line in enumerate(src) if line.strip().startswith('fail(') and 'def ' not in line}
    assert sites == all_sites, sorted(all_sites - sites)


def test_fixture_autouse_hook_is_installed_and_sees_module_names():
    assert getattr(builtins.__import__, '__name__', '') == 'hook'


@pytest.fixture(autouse=True)
def _module_never_imports_at_call_time(monkeypatch):
    """Every test drives the module through the hook: any import executed by the module's own code after load fails the test."""
    real = builtins.__import__
    seen = []

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == m.__name__:
            seen.append((n, tuple(fromlist or ()), level))
        return real(n, g, l, fromlist, level)
    monkeypatch.setattr(builtins, '__import__', hook)
    yield
    assert seen == []


def test_fallback_failer_functions_carry_no_docstring(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh('b1261_doc_world')
    assert mod.make_fail.__doc__ is None
    assert mod.make_fail('x').__doc__ is None
    assert mod.make_fail.__name__ == 'make_fail' and mod.make_fail('x').__name__ == 'fail'


def test_find_spec_is_consulted_exactly_once_in_the_absent_world_simulation(mp):
    spied = []
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda n: spied.append(n) or None)
    mod = fresh('b1261_spec_world')
    assert spied == [REG] and mod.make_fail.__module__ == mod.__name__


def _world(mp, exc_factory, spec_result, register=None):
    """Run fresh() with __import__ of REG raising exc_factory() (or present as a fake module); return (outcome, spied calls)."""
    real = builtins.__import__
    spied = []
    err = exc_factory() if exc_factory else None

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG and err is not None:
            raise err
        return real(n, g, l, fromlist, level)

    def spy(name):
        spied.append(name)
        return spec_result
    mp.setitem(sys.modules, REG, register if register is not None else None)
    mp.setattr(importlib.util, 'find_spec', spy)
    mp.setattr(builtins, '__import__', hook)
    try:
        mod = fresh()
    except BaseException as e:
        return ('raised', e, err), spied
    return ('loaded', mod, err), spied


_FAKE = types.ModuleType(REG)
_FAKE.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE:%s:%s' % (name, code))))
GUARD_WORLDS = [
    ('absent', lambda: ModuleNotFoundError('absent', name=REG), None, 'fallback', 1),
    ('foreign_found', lambda: ModuleNotFoundError('inner', name=REG), object(), 'raise', 1),
    ('spec_false', lambda: ModuleNotFoundError('inner', name=REG), False, 'raise', 1),
    ('spec_empty_tuple', lambda: ModuleNotFoundError('inner', name=REG), (), 'raise', 1),
    ('foreign_mnf_name', lambda: ModuleNotFoundError('foreign', name='some.other.module'), None, 'raise', 0),
    ('name_x', lambda: ModuleNotFoundError('x', name='x'), None, 'raise', 0),
    ('name_none', lambda: ModuleNotFoundError('none'), None, 'raise', 0),
    ('name_prefix', lambda: ModuleNotFoundError('prefix', name='app.modules.instinct_doc'), None, 'raise', 0),
    ('name_longer', lambda: ModuleNotFoundError('longer', name=REG + '.sub'), None, 'raise', 0),
    ('name_upper', lambda: ModuleNotFoundError('upper', name=REG.upper()), None, 'raise', 0),
    ('import_error', lambda: ImportError('ie', name=REG), None, 'raise', 0),
    ('named_import_error', lambda: ImportError('ie', name='some.other.module'), None, 'raise', 0),
    ('present', None, None, 'present', 0),
]


@pytest.mark.parametrize('label,factory,spec,outcome,calls', GUARD_WORLDS, ids=[w[0] for w in GUARD_WORLDS])
def test_find_spec_call_count_and_outcome_per_world_is_an_exact_table(mp, label, factory, spec, outcome, calls):
    got, spied = _world(mp, factory, spec, _FAKE if outcome == 'present' else None)
    assert len(spied) == calls and spied == [REG] * calls, label
    if outcome == 'raise':
        assert got[0] == 'raised' and got[1] is got[2], label
    elif outcome == 'fallback':
        assert got[0] == 'loaded' and got[1].make_fail.__module__ == got[1].__name__, label
    else:
        assert got[0] == 'loaded' and got[1].make_fail is _FAKE.make_fail, label


def test_child_process_in_isolated_mode_gives_the_same_answers():
    code = ("import sys; sys.path.insert(0, %r)\n"
            "import app.modules.instinct_doc.p235_concepts_batch1261_base16_32_64 as m\n"
            "print(m.base64_reason('Zm9vYmFy'),"
            " m.base64_reason('Zg='),"
            " m.base64_canon_reason('Zh=='),"
            " m.base32_reason('M1======'),"
            " m.base32hex_canon_reason('CPNMUOH='),"
            " m.base16_reason('AG'),"
            " m.base16_octets('00ff10'),"
            " m.base64_reason('Zm9!'))\n") % (
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(m.__file__)))),)
    want = "ok length pad.bits char pad.bits char (0, 255, 16) char"
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == want
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25, env={'PYTHONHASHSEED': '7'})
    assert out.stdout.strip() == want


# ---- Eq-to-Is pins: every string-equality site driven with runtime-built non-interned strings ----
def _rt(s):
    """Build s at runtime so it is never the interned/source-serialized constant."""
    out = ''
    for ch in s:
        out = (out + ch)[0:len(out) + 1]
    # CPython caches every latin-1 single-character string, so a runtime-built
    # 1-char string IS the same object as the literal; only longer strings can
    # be witnessed non-identical.
    assert out == s and (len(s) == 1 or out is not s)
    return out


def test_pad_char_compares_use_value_equality_with_runtime_built_equals(mp):
    eq = _rt('=')
    v = 'Zg' + eq + eq
    assert v == 'Zg=='
    assert m.base64_reason(v) == 'ok'
    bad = 'Zg' + eq + 'A'
    assert m.base64_reason(bad) == 'pad.placement'
    v32 = 'MZXW6YQ' + eq
    assert m.base32_reason(v32) == 'ok'
    bad32 = 'MZ' + eq + 'XW6YQ'
    assert m.base32_reason(bad32) == 'pad.placement'
    three = 'Z' + eq + eq + eq
    assert m.base64_reason(three) == 'pad.count'


def test_ok_compares_use_value_equality_with_runtime_built_ok(mp):
    # _canon_reason compares the base reason against 'ok'; feed it a runtime-built one.
    mp.setattr(m, '_padded_reason', lambda *a: _rt('ok'))
    assert m.base64_canon_reason('Zg==') == 'ok'
    # non-canonical pad bits must still be checked after a runtime-built 'ok':
    # an is-compare would take the early return and skip this.
    assert m.base64_canon_reason('Zh==') == 'pad.bits'
    mp.setattr(m, '_padded_reason', lambda *a: _rt('length'))
    assert m.base64_canon_reason('Zg==') == 'length'
    mp.setattr(m, '_padded_reason', lambda *a: _rt('pad.count'))
    assert m.base64_canon_reason('Zg==') == 'pad.count'
    # base16_octets compares base16_reason's result against 'ok'.
    mp.setattr(m, 'base16_reason', lambda v: _rt('ok'))
    assert m.base16_octets('666F') == (102, 111)
    mp.setattr(m, 'base16_reason', lambda v: _rt('char'))
    assert run('base16_octets', '666F') == E('base16_octets', 'bad_value:value.base16')


def test_guard_name_compare_uses_value_equality_with_runtime_built_registry_name(mp):
    real = builtins.__import__
    spied = []
    regname = _rt(REG)
    assert regname == REG and regname is not REG
    err = ModuleNotFoundError('inner', name=regname)

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda name: spied.append(name) or object())
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ModuleNotFoundError) as e:
        fresh()
    assert e.value is err and spied == [REG]


def test_runtime_built_strings_in_a_dash_b_subprocess_with_purged_pycache():
    envdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(m.__file__))))
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "def rt(s):\n"
        "    out = ''\n"
        "    for ch in s:\n"
        "        out = (out + ch)[0:len(out) + 1]\n"
        "    return out\n"
        "import app.modules.instinct_doc.p235_concepts_batch1261_base16_32_64 as m\n"
        "eq = rt('='); ok = rt('ok')\n"
        "assert eq == '=' and ok == 'ok'\n"
        "print(m.base64_reason('Zg' + eq + eq),"
        " m.base64_reason('Zg' + eq + 'A'),"
        " m.base32_reason('MZ' + eq + 'XW6YQ'),"
        " m.base64_reason('Z' + eq + eq + eq),"
        " m.base64_reason('Zm9v' + rt('YmFy')))\n") % (envdir,)
    want = 'ok pad.placement pad.placement pad.count ok'
    out = subprocess.run([sys.executable, '-B', '-I', '-c', code], capture_output=True, text=True, timeout=25)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == want


# ---- direct pins for the private helpers (rev 0e) ----

@pytest.mark.parametrize('v, want', [
    ('', 0), ('=', 1), ('==', 2), ('===', 3), ('====', 4), ('A', 0), ('A=', 1), ('A==', 2),
    ('=A', 0), ('=A=', 1), ('A=A=', 1), ('A=A==', 2), ('AA=====', 5), ('=' * 8, 8), ('A' * 3 + '=' * 6, 6),
])
def test_pad_count_direct_table(v, want):
    assert m._pad_count(v) == want


def test_pad_count_agrees_with_an_independent_oracle_on_every_short_string():
    import itertools
    for k in range(0, 8):
        for p in itertools.product('A=', repeat=k):
            s = ''.join(p)
            want = 0
            for ch in reversed(s):
                if ch != '=':
                    break
                want += 1
            assert m._pad_count(s) == want, s


@pytest.mark.parametrize('v, alpha, block, pads, want', [
    ('', m._B64, 4, m._B64_PADS, 'ok'),
    ('AAAA', m._B64, 4, m._B64_PADS, 'ok'),
    ('AAA', m._B64, 4, m._B64_PADS, 'length'),
    ('AAA=', m._B64, 4, m._B64_PADS, 'ok'),
    ('AA==', m._B64, 4, m._B64_PADS, 'ok'),
    ('A===', m._B64, 4, m._B64_PADS, 'pad.count'),
    ('====', m._B64, 4, m._B64_PADS, 'pad.count'),
    ('A=A=', m._B64, 4, m._B64_PADS, 'pad.placement'),
    ('A-A=', m._B64, 4, m._B64_PADS, 'char'),
    ('=AAA', m._B64, 4, m._B64_PADS, 'pad.placement'),
    ('AAAAAA==', m._B32, 8, m._B32_PADS, 'pad.count'),
    ('AAAAA===', m._B32, 8, m._B32_PADS, 'ok'),
    ('AAAA====', m._B32, 8, m._B32_PADS, 'ok'),
    ('AAAAAAA=', m._B32, 8, m._B32_PADS, 'ok'),
    ('AAAAAA=A', m._B32, 8, m._B32_PADS, 'pad.placement'),
    ('AAA=====', m._B32, 8, m._B32_PADS, 'pad.count'),
    ('AA======', m._B32, 8, m._B32_PADS, 'ok'),
    ('A=======', m._B32, 8, m._B32_PADS, 'pad.count'),
    ('========', m._B32, 8, m._B32_PADS, 'pad.count'),
])
def test_padded_reason_direct_table(v, alpha, block, pads, want):
    assert m._padded_reason(v, alpha, block, pads) == want


@pytest.mark.parametrize('v, idx, zero, r, want', [
    ('AAAA', m._B64_IDX, m._B64_ZERO, 'length', 'length'),
    ('AAAA', m._B64_IDX, m._B64_ZERO, 'ok', 'ok'),
    ('AAA=', m._B64_IDX, m._B64_ZERO, 'ok', 'ok'),
    ('AAB=', m._B64_IDX, m._B64_ZERO, 'ok', 'pad.bits'),
    ('AAE=', m._B64_IDX, m._B64_ZERO, 'ok', 'ok'),
    ('AAC=', m._B64_IDX, m._B64_ZERO, 'ok', 'pad.bits'),
    ('AAQ=', m._B64_IDX, m._B64_ZERO, 'ok', 'ok'),
    ('AB==', m._B64_IDX, m._B64_ZERO, 'ok', 'pad.bits'),
    ('AQ==', m._B64_IDX, m._B64_ZERO, 'ok', 'ok'),
    ('AA==', m._B64_IDX, m._B64_ZERO, 'ok', 'ok'),
    ('AAAAAAAB', m._B32_IDX, m._B32_ZERO, 'ok', 'ok'),
    ('AAAAAAB=', m._B32_IDX, m._B32_ZERO, 'ok', 'pad.bits'),
    ('AAAAAAI=', m._B32_IDX, m._B32_ZERO, 'ok', 'ok'),
    ('AAAAB===', m._B32_IDX, m._B32_ZERO, 'ok', 'pad.bits'),
    ('AAAAC===', m._B32_IDX, m._B32_ZERO, 'ok', 'ok'),
    ('AAAB====', m._B32_IDX, m._B32_ZERO, 'ok', 'pad.bits'),
    ('AAAQ====', m._B32_IDX, m._B32_ZERO, 'ok', 'ok'),
    ('AB======', m._B32_IDX, m._B32_ZERO, 'ok', 'pad.bits'),
    ('AE======', m._B32_IDX, m._B32_ZERO, 'ok', 'ok'),
])
def test_canon_reason_direct_table(v, idx, zero, r, want):
    assert m._canon_reason(v, idx, zero, r) == want


class _StepBudget(AssertionError):
    pass


def _bounded(fn, arg, budget):
    """Run fn(arg) under a line-event budget counted in the module under test; fail by assertion, never by hang."""
    count = [0]
    target = MODPATH

    def local(frame, event, a):
        if event == 'line':
            count[0] += 1
            if count[0] > budget:
                raise _StepBudget('step budget %d exceeded' % budget)
        return local

    def glob(frame, event, a):
        if frame.f_code.co_filename == target:
            return local
        return None
    old = sys.gettrace()
    sys.settrace(glob)
    try:
        return fn(arg), count[0]
    finally:
        sys.settrace(old)


_ALL_FNS = ['base64_reason', 'base64url_reason', 'base32_reason', 'base32hex_reason', 'base16_reason',
            'base64_canon_reason', 'base64url_canon_reason', 'base32_canon_reason', 'base32hex_canon_reason',
            'base16_octets']
_STEP_INPUTS = ['', 'AAAA', 'AA==', 'AAA=', 'AAAA====', '====', '=', 'A', 'AAAAAAAA', 'AAAAAA==', 'AAAAA===',
                'AAAAAAA=', 'AAAAAAAA======', 'A=A=', '66', '666F6F626172', '6', 'AA==AA==', 'AAAA=AAA',
                'A' * 1024, 'A' * 1022 + '==', '=' * 1024, 'A' * 1018 + '======']


def test_step_budget_helper_fails_by_assertion_on_a_non_terminating_loop():
    ns = {}
    exec(compile('def spin(_):\n    i = 0\n    while i < 1:\n        i += 0\n', MODPATH, 'exec'), ns)
    with pytest.raises(_StepBudget):
        _bounded(ns['spin'], None, 50)


def test_step_budget_helper_ignores_frames_outside_the_module_and_restores_the_tracer():
    before = sys.gettrace()
    got, steps = _bounded(lambda s: len(s), 'abc', 5)
    assert got == 3 and steps == 0 and sys.gettrace() is before


@pytest.mark.parametrize('name', _ALL_FNS)
def test_every_function_terminates_within_a_linear_line_budget_on_every_shape(name):
    fn = getattr(m, name)
    for s in _STEP_INPUTS:
        try:
            _bounded(fn, s, 12 * len(s) + 60)
        except ValueError as e:
            assert str(e).startswith(PFX + name + ':bad_value:value.base16')


@pytest.mark.parametrize('s,steps_max', [('AAAA', 30), ('AA==', 30), ('AAA=', 30), ('', 18), ('====', 30)])
def test_padding_scanners_have_small_step_counts_per_shape(s, steps_max):
    r1, n1 = _bounded(m.base64_reason, s, steps_max)
    r2, n2 = _bounded(m.base64_canon_reason, s, steps_max + 20)
    assert ('ok', r1) == run('base64_reason', s) and ('ok', r2) == run('base64_canon_reason', s)
    assert n1 <= steps_max and n2 <= steps_max + 20


@pytest.mark.parametrize('n', [4, 8, 64, 256, 260, 1024])
def test_loop_step_growth_is_linear_in_the_input_length(n):
    a, na = _bounded(m.base64_reason, 'A' * n, 3 * n + 21)
    b, nb = _bounded(m.base64_reason, 'A' * (n - 4) + '====', 3 * n + 21)
    assert a == 'ok' and 3 * n + 9 <= na <= 3 * n + 21
    assert b == 'pad.count' and 3 * n + 9 <= nb <= 3 * n + 21


def test_registry_guard_uses_identity_not_equality_against_none_for_find_spec(mp):
    real = builtins.__import__
    err = ModuleNotFoundError('inner', name=REG)

    class Liar:
        def __ne__(self, other):
            return False

        def __eq__(self, other):
            return True

        __hash__ = None

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda name: Liar())
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ModuleNotFoundError) as e:
        fresh()
    assert e.value is err
