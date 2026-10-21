'''RFC 7518 "JSON Web Algorithms (JWA)": the "alg" (algorithm)
name registries and the "enc" (encryption algorithm) name
registry as pure tables: the s3.1 "alg" values for JWS, the
s4.1 "alg" values for JWE, and the s5.1 "enc" values for JWE,
with the "none" handling of s3.6 and the RFC 8725 s3.2
caution.  Computing or verifying any of the named algorithms
is cryptographic processing and out of scope.

Public API:

  jws_alg_parse(text) -> the s3.1 table row for a JWS "alg"
      value as a dict: 'name' (the value), 'algorithm'
      (the Digital Signature or MAC column text),
      'implementation' (the Implementation Requirements
      column text, verbatim, including any '+'/'-' suffix).
  jws_alg_is_valid(text) -> True iff jws_alg_parse would
      succeed.
  jwe_alg_parse(text) -> the s4.1 table row for a JWE "alg"
      value as a dict: 'name', 'algorithm' (the Key
      Management Algorithm column text),
      'more_header_params' (the More Header Params column as
      a list of names, empty for "(none)"), 'implementation'.
  jwe_alg_is_valid(text) -> True iff jwe_alg_parse would
      succeed.
  jwe_enc_parse(text) -> the s5.1 table row for a JWE "enc"
      value as a dict: 'name', 'algorithm' (the Content
      Encryption Algorithm column text), 'implementation'.
  jwe_enc_is_valid(text) -> True iff jwe_enc_parse would
      succeed.

Grammar notes (verified against the RFC 7518 text): an "alg"
value is "a case-sensitive ASCII string containing a
StringOrURI value" (JWS s4.1.1, the same text at JWE
s4.1.1), so the tables are matched case-sensitively and any
non-ASCII character refuses.  The s3.1 table lists "HS256",
"HS384", "HS512", "RS256", "RS384", "RS512", "ES256",
"ES384", "ES512", "PS256", "PS384", "PS512" and "none".  The
s4.1 table lists "RSA1_5", "RSA-OAEP", "RSA-OAEP-256",
"A128KW", "A192KW", "A256KW", "dir", "ECDH-ES",
"ECDH-ES+A128KW", "ECDH-ES+A192KW", "ECDH-ES+A256KW",
"A128GCMKW", "A192GCMKW", "A256GCMKW", "PBES2-HS256+A128KW",
"PBES2-HS384+A192KW" and "PBES2-HS512+A256KW".  The s5.1
table lists "A128CBC-HS256", "A192CBC-HS384",
"A256CBC-HS512", "A128GCM", "A192GCM" and "A256GCM".  "The
use of "+" in the Implementation Requirements column
indicates that the requirement strength is likely to be
increased in a future version of the specification." (s3.1);
s4.1 adds: "The use of "-" indicates that the requirement
strength is likely to be decreased in a future version of
the specification."  The s4.1 More Header
Params column names "epk", "apu" and "apv" for the ECDH-ES
family, "iv" and "tag" for the AES GCM key wrapping family
and "p2s" and "p2c" for the PBES2 family, and s4.1 notes:
"All but "dir" and "ECDH-ES" also produce a JWE Encrypted
Key value."  No name appears in more than one of the three
tables, so each function's membership test is against its
own table only.

The "none" handling (s3.6, RFC 8725 s3.2): "none" is a
registered s3.1 value ("No digital signature or MAC
performed"), so jws_alg_parse("none") succeeds with its row;
it is not an s4.1 or s5.1 value, so the JWE functions refuse
it.  Accepting it is an application decision, not a registry
fact: s3.6 says "Implementations that support Unsecured JWSs
MUST NOT accept such objects as valid unless the application
specifies that it is acceptable for a specific object to not
be integrity protected.  Implementations MUST NOT accept
Unsecured JWSs by default." and, against downgrade attacks,
"applications MUST NOT signal acceptance of Unsecured JWSs
at a global level, and SHOULD signal acceptance on a
per-object basis".  RFC 8725 s3.2 adds that applications
"MUST only allow the use of cryptographically current
algorithms", that the "none" algorithm "should only be used
when the JWT is cryptographically protected by other means",
and that "JWT libraries SHOULD NOT generate JWTs using
"none" unless explicitly requested to do so by the caller"
and "SHOULD NOT consume JWTs using "none" unless explicitly
requested by the caller".  This unit validates registry
membership only; those acceptance rules are the caller's to
enforce.

Profile decisions (OURS, not from the RFC text):
  - Values are required to be pure ASCII (both "alg" texts
    say ASCII); the check is per character, before the
    membership test.
  - The empty string is ASCII and in no table, so it refuses
    as an unknown name rather than with its own code.
  - A registered-name row reports the printed table columns
    only; prose facts around the tables (such as which JWE
    "alg" values produce a JWE Encrypted Key) are documented
    above, not folded into the rows.
  - Only the exact str type is accepted: subclasses refuse
    with the type code.

Refusal order: bad_type before everything (the exact type
check); then bad_value: the ASCII rule before the membership
rule ("unknown" covers every well-formed value the table
does not list, including wrong case, surrounding whitespace
and names from the other tables).

Errata (4 records, all Verified, none touching the name
tables, none folded): Verified EID 6612 (s3.4, Editorial)
fixes "being be" to "being" in the ECDSA R/S octet-step
text: signature computation, not the name grammar.
Verified EID 8526 (s3.4.5, Technical) carries text about
RTCP header compression that has no counterpart in RFC 7518
(a misfiled record): nothing to fold.  Verified EID 8568
(s3.2, Editorial) corrects a "NIST SP 800-117" reference to
"NIST SP 800-107" in the HMAC key-length rationale: a
citation fix, not the name grammar.  Verified EID 8747
(s7.1.1, Editorial) fixes "Algorithm Analysis
Documents(s):" to "Algorithm Analysis Document(s):" in the
IANA registration template: registry paperwork, not the
name tables.
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


_JWS_ALG = {
    'HS256': ('HMAC using SHA-256', 'Required'),
    'HS384': ('HMAC using SHA-384', 'Optional'),
    'HS512': ('HMAC using SHA-512', 'Optional'),
    'RS256': ('RSASSA-PKCS1-v1_5 using SHA-256', 'Recommended'),
    'RS384': ('RSASSA-PKCS1-v1_5 using SHA-384', 'Optional'),
    'RS512': ('RSASSA-PKCS1-v1_5 using SHA-512', 'Optional'),
    'ES256': ('ECDSA using P-256 and SHA-256', 'Recommended+'),
    'ES384': ('ECDSA using P-384 and SHA-384', 'Optional'),
    'ES512': ('ECDSA using P-521 and SHA-512', 'Optional'),
    'PS256': ('RSASSA-PSS using SHA-256 and MGF1 with SHA-256',
              'Optional'),
    'PS384': ('RSASSA-PSS using SHA-384 and MGF1 with SHA-384',
              'Optional'),
    'PS512': ('RSASSA-PSS using SHA-512 and MGF1 with SHA-512',
              'Optional'),
    'none': ('No digital signature or MAC performed', 'Optional'),
}

_JWE_ALG = {
    'RSA1_5': ('RSAES-PKCS1-v1_5', (), 'Recommended-'),
    'RSA-OAEP': ('RSAES OAEP using default parameters', (),
                 'Recommended+'),
    'RSA-OAEP-256': ('RSAES OAEP using SHA-256 and MGF1 with'
                     ' SHA-256', (), 'Optional'),
    'A128KW': ('AES Key Wrap with default initial value using'
               ' 128-bit key', (), 'Recommended'),
    'A192KW': ('AES Key Wrap with default initial value using'
               ' 192-bit key', (), 'Optional'),
    'A256KW': ('AES Key Wrap with default initial value using'
               ' 256-bit key', (), 'Recommended'),
    'dir': ('Direct use of a shared symmetric key as the CEK', (),
            'Recommended'),
    'ECDH-ES': ('Elliptic Curve Diffie-Hellman Ephemeral Static'
                ' key agreement using Concat KDF',
                ('epk', 'apu', 'apv'), 'Recommended+'),
    'ECDH-ES+A128KW': ('ECDH-ES using Concat KDF and CEK wrapped'
                       ' with "A128KW"', ('epk', 'apu', 'apv'),
                       'Recommended'),
    'ECDH-ES+A192KW': ('ECDH-ES using Concat KDF and CEK wrapped'
                       ' with "A192KW"', ('epk', 'apu', 'apv'),
                       'Optional'),
    'ECDH-ES+A256KW': ('ECDH-ES using Concat KDF and CEK wrapped'
                       ' with "A256KW"', ('epk', 'apu', 'apv'),
                       'Recommended'),
    'A128GCMKW': ('Key wrapping with AES GCM using 128-bit key',
                  ('iv', 'tag'), 'Optional'),
    'A192GCMKW': ('Key wrapping with AES GCM using 192-bit key',
                  ('iv', 'tag'), 'Optional'),
    'A256GCMKW': ('Key wrapping with AES GCM using 256-bit key',
                  ('iv', 'tag'), 'Optional'),
    'PBES2-HS256+A128KW': ('PBES2 with HMAC SHA-256 and'
                           ' "A128KW" wrapping', ('p2s', 'p2c'),
                           'Optional'),
    'PBES2-HS384+A192KW': ('PBES2 with HMAC SHA-384 and'
                           ' "A192KW" wrapping', ('p2s', 'p2c'),
                           'Optional'),
    'PBES2-HS512+A256KW': ('PBES2 with HMAC SHA-512 and'
                           ' "A256KW" wrapping', ('p2s', 'p2c'),
                           'Optional'),
}

_JWE_ENC = {
    'A128CBC-HS256': ('AES_128_CBC_HMAC_SHA_256 authenticated'
                      ' encryption algorithm, as defined in'
                      ' Section 5.2.3', 'Required'),
    'A192CBC-HS384': ('AES_192_CBC_HMAC_SHA_384 authenticated'
                      ' encryption algorithm, as defined in'
                      ' Section 5.2.4', 'Optional'),
    'A256CBC-HS512': ('AES_256_CBC_HMAC_SHA_512 authenticated'
                      ' encryption algorithm, as defined in'
                      ' Section 5.2.5', 'Required'),
    'A128GCM': ('AES GCM using 128-bit key', 'Recommended'),
    'A192GCM': ('AES GCM using 192-bit key', 'Optional'),
    'A256GCM': ('AES GCM using 256-bit key', 'Recommended'),
}


def _name_row(f, table, text, kind):
    if type(text) is not str:
        f('bad_type:%s.type' % kind)
    for c in text:
        if ord(c) > 0x7F:
            f('bad_value:%s.ascii' % kind)
    row = table.get(text)
    if row is None:
        f('bad_value:%s.unknown' % kind)
    return row


def jws_alg_parse(text):
    'Validate an s3.1 JWS "alg" value; return its table row.'
    f = make_fail('jws_alg_parse')
    row = _name_row(f, _JWS_ALG, text, 'alg')
    return {'name': text, 'algorithm': row[0],
            'implementation': row[1]}


def jws_alg_is_valid(text):
    'True iff jws_alg_parse(text) would succeed.'
    try:
        jws_alg_parse(text)
        return True
    except ValueError:
        return False


def jwe_alg_parse(text):
    'Validate an s4.1 JWE "alg" value; return its table row.'
    f = make_fail('jwe_alg_parse')
    row = _name_row(f, _JWE_ALG, text, 'alg')
    return {'name': text, 'algorithm': row[0],
            'more_header_params': list(row[1]),
            'implementation': row[2]}


def jwe_alg_is_valid(text):
    'True iff jwe_alg_parse(text) would succeed.'
    try:
        jwe_alg_parse(text)
        return True
    except ValueError:
        return False


def jwe_enc_parse(text):
    'Validate an s5.1 JWE "enc" value; return its table row.'
    f = make_fail('jwe_enc_parse')
    row = _name_row(f, _JWE_ENC, text, 'enc')
    return {'name': text, 'algorithm': row[0],
            'implementation': row[1]}


def jwe_enc_is_valid(text):
    'True iff jwe_enc_parse(text) would succeed.'
    try:
        jwe_enc_parse(text)
        return True
    except ValueError:
        return False
