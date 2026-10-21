"""Tests for p235 concepts batch 1219: RFC 9110 s12.4.2/12.5.1/12.5.4 weight, Accept and Accept-Language syntax. Pure functions over caller data; claims asserted False."""
import ast
import builtins
import importlib.util
import inspect
import os
import re
import signal
import subprocess
import sys
import tracemalloc
import traceback
import types
import unicodedata

import pytest
import random
from importlib.util import find_spec

REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1219_httpaccept'
NAMES = ('qvalue_reason', 'qvalue_format', 'media_range_reason', 'language_range_reason',
         'accept_reason', 'accept_language_reason', 'split_accept', 'split_accept_language', 'accept_format',
         'accept_language_format')
PRIVATE = ('_str', '_int', '_fold', '_ows_end', '_token_run', '_qd_ok', '_qp_ok', '_quoted_end', '_param_at', '_param_parts',
           '_range_end', '_params_end', '_weight_at', '_element_end', '_list_reason', '_split_weight', '_format_param_value')
DOC_EXACT = 'p235 concepts batch 1219 (rev 1): RFC 9110 quality values (12.4.2), Accept (12.5.1) and Accept-Language (12.5.4) syntax. Pure functions over caller-supplied text. No retrieval, no network, no clock. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it does no content negotiation, consults no registry, and knows no media-type or language-tag semantics. ADJACENT names the neighbouring grammars this unit deliberately does not implement: the RFC 6838 media type registry grammar and registered semantics (b1172), RFC 2045 MIME media type and parameter semantics (b1204), and RFC 4647 matching schemes.\n\nLIVE-READ SOURCES (read live, quoted verbatim below and mechanically matched against the whitespace-collapsed RFC text with the page headers and footers removed):\n- RFC 9110, HTTP Semantics, Standards Track, June 2022. rfc9110.txt is 502941 bytes, sha256 21c1cdce6ab0e5509b04d84a28000836c7a087cf786efe6f04877ebfff47232a.\n- RFC 4647, Matching of Language Tags, September 2006, for the language-range grammar imported by 12.5.4. rfc4647.txt is 45595 bytes, sha256 999e4e23ca5b8925ac5f154855af0f2948a5d26d14853249c9fc857e469ecb49.\n- The rfc-editor info page for RFC 9110 lists Updates (1): RFC 3864, and Obsoletes (9): RFC 2818, RFC 7230, RFC 7231, RFC 7232, RFC 7233, RFC 7235, RFC 7538, RFC 7615, RFC 7694; the abstract on the page describes the 7230 entry as portions of RFC 7230. The page shows no Obsoleted by entry and no Updated by entry: RFC 9110 is the current HTTP Semantics document. CLAIMS current is still False.\n- errata.json (sha256 2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) records 14 errata for RFC 9110; 1 erratum touches the sections used here: 7138 (Verified, Technical, section 12.5.1) corrects a worked-example table value (text/html;level=3 maps to 0.3, not 0.7); it is about negotiation semantics and changes no grammar. The other 13 touch sections 5.2, 6.4.1, 6.5.1, 8.3.2, 8.6, 14.1.1, 15, 15.4, 15.4.9, 15.5.2, Appendix A and B.1/B.2, none of which carry grammar used here. Both counts are taken from that single JSON index and are not independently confirmed against the per-erratum pages. OURS: no erratum is applied. The RFC text and its collected ABNF decide. RFC 4647 carries 3 errata in the same index: 8287 (Reported, Technical, 3.1), 8253 (Held for Document Update, Editorial, 2 and 2.3) and 8838 (Verified, Editorial, 2.2); none touches section 2.1.\n\nSOURCED (the RFC text):\n- Weight and qvalue (9110 12.4.2): "weight = OWS ";" OWS "q=" qvalue" "qvalue = ( "0" [ "." 0*3DIGIT ] ) / ( "1" [ "." 0*3("0") ] )"\n- The q parameter and default (12.4.2): "The content negotiation fields defined by this specification use a common parameter, named "q" (case-insensitive), to assign a relative "weight" to the preference for that associated kind of content." "The weight is normalized to a real number in the range 0 through 1, where 0.001 is the least preferred and 1 is the most preferred; a value of 0 means "not acceptable". If no "q" parameter is present, the default weight is 1."\n- Sender digit limit (12.4.2): "A sender of qvalue MUST NOT generate more than three digits after the decimal point."\n- Accept (12.5.1): "Accept = #( media-range [ weight ] )" "media-range = ( "*/*" / ( type "/" "*" ) / ( type "/" subtype ) ) parameters"\n- Wildcards (12.5.1): "The asterisk "*" character is used to group media types into ranges, with "*/*" indicating all media types and "type/*" indicating all subtypes of that type."\n- accept-ext removed, q last (12.5.1): "Previous specifications allowed additional extension parameters to appear after the weight parameter. The accept extension grammar (accept-params, accept-ext) has been removed because it had a complicated definition, was not being used in practice, and is more easily deployed through new header fields." "Senders using weights SHOULD send "q" last (after all media-range parameters). Recipients SHOULD process any parameter named "q" as weight, regardless of parameter ordering."\n- Accept example (12.5.1): "Accept: audio/*; q=0.2, audio/basic"\n- Accept-Language (12.5.4): "Accept-Language = #( language-range [ weight ] )" "language-range = <language-range, see [RFC4647], Section 2.1>"\n- Accept-Language example (12.5.4): "Accept-Language: da, en-gb;q=0.8, en;q=0.7"\n- Parameters (9110 5.6.6): "parameters = *( OWS ";" OWS [ parameter ] )" "parameter = parameter-name "=" parameter-value" "parameter-name = token" "parameter-value = ( token / quoted-string )"\n- Parameter name case (5.6.6): "Parameter names are case-insensitive."\n- Media type (9110 8.3.1): "media-type = type "/" subtype parameters" "type = token" "subtype = token"\n- Type and subtype case (8.3.1): "The type and subtype tokens are case-insensitive."\n- Token (9110 5.6.2): "token = 1*tchar" "tchar = "!" / "#" / "$" / "%" / "&" / "\'" / "*" / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA"\n- Quoted string (9110 5.6.4): "quoted-string = DQUOTE *( qdtext / quoted-pair ) DQUOTE" "qdtext = HTAB / SP / %x21 / %x23-5B / %x5D-7E / obs-text" "quoted-pair = "\\" ( HTAB / SP / VCHAR / obs-text )"\n- Quoted-pair handling (5.6.4): "Recipients that process the value of a quoted-string MUST handle a quoted-pair as if it were replaced by the octet following the backslash."\n- OWS (9110 5.6.3, collected ABNF): "OWS = *( SP / HTAB )"\n- Recipient list rule (9110 5.6.1.2): "#element => [ element ] *( OWS "," OWS [ element ] )"\n- Empty list elements (5.6.1.2): "Empty elements do not contribute to the count of elements present. A recipient MUST parse and ignore a reasonable number of empty list elements: enough to handle common mistakes by senders that merge values, but not so much that they could be used as a denial-of- service mechanism."\n- Language range (RFC 4647 2.1): "language-range = (1*8ALPHA *("-" 1*8alphanum)) / "*"" "alphanum = ALPHA / DIGIT"\n- No registry validation (RFC 4647 2.1): "A basic language range differs from the language tags defined in [RFC4646] only in that there is no requirement that it be "well- formed" or be validated against the IANA Language Subtag Registry."\n\nOURS (conventions this module adds, each pinned by tests):\n1. ASCII only. obs-text (%x80-FF) is refused everywhere, including inside quoted-string and quoted-pair. Every other non-ASCII character is refused. Membership is tested with explicit ASCII strings, never with Unicode-aware str methods.\n2. Case folding. The q parameter name is matched case-insensitively (12.4.2: named "q" (case-insensitive)); the fold is an explicit ASCII A-Z to a-z map only. Returned structures preserve the original case of every token.\n3. Recipient list rule. Following 5.6.1.2, empty list elements are accepted and skipped, and so are leading commas, trailing commas and OWS-only segments; the empty string and OWS-only strings are accepted as zero-element lists by accept_reason and accept_language_reason, and split_accept and split_accept_language then return the empty list.\n4. Bare semicolons. parameters is *( OWS ";" OWS [ parameter ] ), so a semicolon need not be followed by a parameter: "a/b;", "a/b;;p=1" and "a/b; , text/plain" are all ok.\n5. No OWS around "=". parameter is parameter-name "=" parameter-value with no whitespace inside (5.6.6), and weight writes "q=" literally, so "a/b;q =0.5" is param.equals and "a/b;q= 0.5" is param.value.\n6. Weight detection in split_accept. Following "Recipients SHOULD process any parameter named "q" as weight, regardless of parameter ordering", the first parameter whose name folds to "q" and whose value, taken as a bare token or as the content of a quoted-string, is a valid qvalue is reported as the weight; every other parameter (a q whose value, quoted or not, is not a valid qvalue, and later q duplicates) stays in the params tuple in order. A parameter named q with an invalid qvalue value is still syntactically a parameter, so accept_reason("text/html;q=2") is ok. split_accept_language is strict the other way: it admits no parameters at all (OURS 9), and a quoted q value there is not dequoted, so en;q="0.5" is refused as weight.value.empty while split_accept reports its weight.\n7. Wildcards by ABNF. "*" is a tchar, so "*/html" parses as type "/" subtype like the grammar writes; only the prose restricts "*" to the two range forms, and this syntax-only unit does not (12.5.1 wildcard semantics are NOT_CLAIMED).\n8. language-range per RFC 4647 2.1: "*" alone, or a first subtag of 1-8 ASCII letters followed by subtags of 1-8 ASCII letters or digits. There is no registry validation, exactly as 4647 states. "a-*" is refused as form, because after the first subtag each subtag is 1-8 ASCII letters or digits and the asterisk is neither; "x-private" is ok under the 2.1 grammar alone.\n9. Accept-Language elements carry no parameters, only an optional weight (12.5.4): "en;foo=1" is weight.name, and anything after the qvalue other than OWS or "," is weight.value.char or comma.\n10. Canonical format. accept_format and accept_language_format join elements with ", ", put "; " before each parameter and before "; q=", emit parameter values as bare tokens when possible and as quoted-strings otherwise (escaping DQUOTE and backslash), and qvalue_format emits the shortest qvalue with up to three decimals ("0.5", not "0.500"). Trailing list OWS is never emitted.\n\nCAPS AND CLOSURE: TEXT_CAP is 4096 characters for every text input, and 4096 entries for every entries input. Lengths are checked before any content is read. The payloads of split_accept and split_accept_language are built from slices of the input and never longer than it.\n\nFUNCTIONS, in this order: qvalue_reason, qvalue_format, media_range_reason, language_range_reason, accept_reason, accept_language_reason, split_accept, split_accept_language, accept_format, accept_language_format. Errors are ValueError with the text P235:<function>:<code>. A code is bad_type:<name> (exact built-in type by identity, subclasses and bool-for-int refused), bad_value:<name>.length, or bad_value:<name>.<reason>.\n\nREASONS, in check order (the first failure decides, so a text with several faults reports the first):\n- qvalue_reason: empty, then a single left-to-right pass: char (a character that is neither DIGIT nor "."), then form (not "0" or "1" with an optional "." and up to three fraction digits, all "0" after "1."). ok otherwise.\n- qvalue_format: bad_type:milli (bool refused), then bad_value:milli.range outside 0..1000.\n- media_range_reason: empty, then type (no type token), slash (no "/" after the type), subtype (no subtype token), then the parameters left to right: semicolon (a character other than OWS, ";" or the end), param.name, param.equals, param.value, then tail (characters or trailing OWS after the last parameter). ok otherwise.\n- language_range_reason: empty, then form (a "*" inside a longer range, or a first character that is not an ASCII letter), then a single left-to-right pass over subtags: char (a character that is not ALPHA or DIGIT or "-"), form (an empty or over-8 subtag or a trailing "-"). ok otherwise.\n- accept_reason: per element in order: type, slash, subtype, then parameters: semicolon, param.name, param.equals, param.value; the list level accepts empty elements and trailing OWS. ok otherwise.\n- accept_language_reason: per element in order: the language_range_reason reasons, then comma (a character other than OWS, ";" or "," after the range), then the weight: weight.name, weight.equals, weight.value.empty, weight.value.form, weight.value.char. ok otherwise.\n- split_accept and split_accept_language: the accept_reason and accept_language_reason reasons as bad_value:text.<reason>.\n- accept_format: bad_type:entries, bad_value:entries.length, then per entry bad_type:entries.item, bad_type:range, bad_value:range.form, bad_type:entries.item for params, bad_type:name, bad_type:value, bad_value:name.form, bad_value:value.form, bad_type:q, bad_value:q.form. accept_language_format: the same without name and value.\n\nOUTPUT ORDER: split_accept returns a list of (range, params, q) in list order: range the type "/" subtype text as written, params a tuple of (name, value) pairs in order (a quoted value is unquoted; names keep their original case), q the detected weight qvalue string or None. split_accept_language returns a list of (range, q-or-None) in list order. accept_format takes split_accept-shaped entries; accept_language_format takes split_accept_language-shaped entries.\n'
QUOTES = ['weight = OWS ";" OWS "q=" qvalue', 'qvalue = ( "0" [ "." 0*3DIGIT ] ) / ( "1" [ "." 0*3("0") ] )', 'The content negotiation fields defined by this specification use a common parameter, named "q" (case-insensitive), to assign a relative "weight" to the preference for that associated kind of content.', 'The weight is normalized to a real number in the range 0 through 1, where 0.001 is the least preferred and 1 is the most preferred; a value of 0 means "not acceptable". If no "q" parameter is present, the default weight is 1.', 'A sender of qvalue MUST NOT generate more than three digits after the decimal point.', 'Accept = #( media-range [ weight ] )', 'media-range = ( "*/*" / ( type "/" "*" ) / ( type "/" subtype ) ) parameters', 'The asterisk "*" character is used to group media types into ranges, with "*/*" indicating all media types and "type/*" indicating all subtypes of that type.', 'Previous specifications allowed additional extension parameters to appear after the weight parameter. The accept extension grammar (accept-params, accept-ext) has been removed because it had a complicated definition, was not being used in practice, and is more easily deployed through new header fields.', 'Senders using weights SHOULD send "q" last (after all media-range parameters). Recipients SHOULD process any parameter named "q" as weight, regardless of parameter ordering.', 'Accept: audio/*; q=0.2, audio/basic', 'Accept-Language = #( language-range [ weight ] )', 'language-range = <language-range, see [RFC4647], Section 2.1>', 'Accept-Language: da, en-gb;q=0.8, en;q=0.7', 'parameters = *( OWS ";" OWS [ parameter ] )', 'parameter = parameter-name "=" parameter-value', 'parameter-name = token', 'parameter-value = ( token / quoted-string )', 'Parameter names are case-insensitive.', 'media-type = type "/" subtype parameters', 'type = token', 'subtype = token', 'The type and subtype tokens are case-insensitive.', 'token = 1*tchar', 'tchar = "!" / "#" / "$" / "%" / "&" / "\'" / "*" / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA', 'quoted-string = DQUOTE *( qdtext / quoted-pair ) DQUOTE', 'qdtext = HTAB / SP / %x21 / %x23-5B / %x5D-7E / obs-text', 'quoted-pair = "\\" ( HTAB / SP / VCHAR / obs-text )', 'Recipients that process the value of a quoted-string MUST handle a quoted-pair as if it were replaced by the octet following the backslash.', 'OWS = *( SP / HTAB )', '#element => [ element ] *( OWS "," OWS [ element ] )', 'Empty elements do not contribute to the count of elements present. A recipient MUST parse and ignore a reasonable number of empty list elements: enough to handle common mistakes by senders that merge values, but not so much that they could be used as a denial-of- service mechanism.', 'language-range = (1*8ALPHA *("-" 1*8alphanum)) / "*"', 'alphanum = ALPHA / DIGIT', 'A basic language range differs from the language tags defined in [RFC4646] only in that there is no requirement that it be "well- formed" or be validated against the IANA Language Subtag Registry.']
HERE = os.path.dirname(os.path.abspath(__file__))
import app.modules.instinct_doc.p235_concepts_batch1219_httpaccept as m  # noqa: E402
MODPATH = m.__file__


def _prefix():
    spec = importlib.util.spec_from_file_location('b1219_pfx', MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        return str(e)[:-len('x:c')]


PFX = _prefix()


class _Alarm(AssertionError):
    pass


@pytest.fixture(autouse=True)
def _alarm():
    def handler(signum, frame):
        raise _Alarm('ALARM2S test exceeded 2 seconds')
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 2.0)
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, old)


@pytest.fixture
def mp(monkeypatch):
    return monkeypatch


def fresh(name='b1219_fresh'):
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


def run(fn, *args, mod=None):
    try:
        return ('ok', getattr(mod or m, fn)(*args))
    except ValueError as e:
        return ('err', str(e))


# ---- independent oracle (regex from the ABNF, plus a split-based list parser, built separately from the module's loops) ----
_TOK = r"[A-Za-z0-9!#$%&'*+\-.^_`|~]"
_QS = r'"(?:[\t\x20\x21\x23-\x5B\x5D-\x7E]|\\[\t\x20-\x7E])*"'
_QV = re.compile(r"(?:0(?:\.[0-9]{0,3})?|1(?:\.0{0,3})?)", re.S)
_PARAM = _TOK + r"+=(?:" + _TOK + r"+|" + _QS + r")"
_PARAMS = r"(?:[ \t]*;[ \t]*(?:" + _PARAM + r")?)*"
_MRANGE = re.compile(_TOK + r"+/" + _TOK + r"+" + _PARAMS, re.S)
_LRANGE = re.compile(r"(?:[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*|\*)", re.S)
_LELEM = re.compile(r"(?:[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*|\*)(?:[ \t]*;[ \t]*[qQ]=(?:" + _QV.pattern + r"))?[ \t]*", re.S)
_TOKRE = re.compile(_TOK + r"+", re.S)
_PARAMRE = re.compile(_PARAM, re.S)


def o_qv(t):
    return _QV.fullmatch(t) is not None


def o_tok(t):
    return _TOKRE.fullmatch(t) is not None


def _seg_split(t):
    # split at commas outside quoted-strings; False when a quote never closes
    parts = []
    cur = ''
    i = 0
    while i < len(t):
        c = t[i]
        if c == ',':
            parts.append(cur)
            cur = ''
            i += 1
        elif c == '"':
            j = i + 1
            closed = False
            while j < len(t):
                if t[j] == '\\':
                    j += 2
                    continue
                if t[j] == '"':
                    closed = True
                    j += 1
                    break
                j += 1
            if not closed:
                return False
            cur += t[i:j]
            i = j
        else:
            cur += c
            i += 1
    parts.append(cur)
    return parts


def o_accept(t):
    segs = _seg_split(t)
    if segs is False:
        return False
    for raw in segs:
        s = raw.strip(' \t')
        if s == '':
            continue
        if _MRANGE.fullmatch(s) is None:
            return False
    return True


def o_accept_language(t):
    segs = _seg_split(t)
    if segs is False:
        return False
    for raw in segs:
        s = raw.strip(' \t')
        if s == '':
            continue
        if _LELEM.fullmatch(s) is None:
            return False
    return True


LOOKALIKES = ['\u0663', '\uff11', '\u00b2', '\u212a', '\u0131', '\u017f', '\u0660', '\u2467', '\u00a0', '\u2003', '\uff21', '\u0130', '\u037e', '\uff1b', '\uff1d',
              '\u201c', '\u2033', '\u2215', '\u2028', '\u0085', '\u1680', '\uff0c', '\uff01', '\uff1a', '\u212b', '\u2126', '\u1e9e', '\ufb01', '\uff0e', '\u2024',
              '\uff3f', '\u2010', '\u2212', '\uff5e', '\u2018', '\u2019', '\uff02', '\uff0f', '\uff1f', '\uff03', '\uff05', '\uff3b', '\uff3d', '\u2044', '\u00e9']
ARGSPEC = {'qvalue_reason': [('text', '0.5')], 'qvalue_format': [('milli', 500)],
           'media_range_reason': [('text', 'text/html;level=3')], 'language_range_reason': [('text', 'en-gb')],
           'accept_reason': [('text', 'text/*;q=0.3, */*')], 'accept_language_reason': [('text', 'da, en-gb;q=0.8')],
           'split_accept': [('text', 'text/*;q=0.3, */*')], 'split_accept_language': [('text', 'da, en-gb;q=0.8')],
           'accept_format': [('entries', [('text/*', (), '0.3')])], 'accept_language_format': [('entries', [('da', None)])]}

# ---- hostile values ----------------------------------------------------------------------------------------------
class S(str):
    pass


class T(tuple):
    pass


class Meta(type):
    def __eq__(cls, other):
        return True

    def __hash__(cls):
        return 1


class SM(str, metaclass=Meta):
    pass


class EqAll(str):
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __hash__(self):
        return 0


class BoolLike(int):
    pass


STR_HOSTILE = [S('g'), SM('g'), EqAll('g')]
JUNK = [None, 1, 0, True, False, 1.5, b'g', bytearray(b'g'), ['g'], {'g': 1}, {'g'}, object(), [], (lambda: 1), ('g',)]


# ---- constants, shape ----------------------------------------------------------------------------------------------
def test_constants_exact():
    assert m.SCOPE == 'RFC 9110 sections 12.4.2, 12.5.1 and 12.5.4 syntax over caller-supplied text: qvalue, weight, media-range, language-range, Accept and Accept-Language lists, well-formed parse and canonical format'
    assert m.NOT_CLAIMED == ('standard', 'authority', 'certification', 'currency', 'completeness', 'negotiation', 'registry', 'media-type-semantics', 'language-tag-semantics')
    assert m.CLAIMS == {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False,
                        'negotiation': False, 'registry': False, 'media_type_semantics': False, 'language_tag_semantics': False}
    assert all(v is False for v in m.CLAIMS.values()) and m.TEXT_CAP == 4096
    assert m.ADJACENT == ('RFC 6838 media type registry grammar and registered type/subtype/parameter semantics (b1172)',
                          'RFC 2045 MIME media type and parameter semantics (b1204)',
                          'RFC 4647 language matching schemes (only the 2.1 basic language-range syntax is in scope here)')
    assert m.DIGITS == '0123456789' and m.UPPER == 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' and m.LOWER == 'abcdefghijklmnopqrstuvwxyz' and m._REG == REG
    assert m.ALPHA == m.UPPER + m.LOWER and m.ALNUM == m.ALPHA + m.DIGITS
    assert m.TCHARS == m.DIGITS + m.UPPER + m.LOWER + "!#$%&'*+-.^_`|~"
    assert len(m.TCHARS) == 77 and len(set(m.TCHARS)) == 77
    assert m.FOLD == {m.UPPER[i]: m.LOWER[i] for i in range(26)} and len(m.FOLD) == 26
    assert m._MID == '#$%&\'()*+,-./' + m.DIGITS + ':;<=>?@' + m.UPPER + '[' and len(m._MID) == 57
    assert m._TAIL == ']^_`' + m.LOWER + '{|}~' and len(m._TAIL) == 34
    assert m.QDT == '\t !' + m._MID + m._TAIL and m.VCHAR == '!"' + m._MID + '\\' + m._TAIL and m.QPT == '\t ' + m.VCHAR
    assert (len(m.QDT), len(m.VCHAR), len(m.QPT)) == (94, 94, 96)
    assert len(set(m.QDT)) == 94 and len(set(m.VCHAR)) == 94 and len(set(m.QPT)) == 96
    assert set(m.QDT) < set(m.QPT) and set(m.VCHAR) < set(m.QPT)


@pytest.mark.parametrize('i', range(256))
def test_char_classes_and_reason_for_every_code(i):
    c = chr(i)
    assert (c in m.TCHARS) == (re.fullmatch(r"[A-Za-z0-9!#$%&'*+\-.^_`|~]", c) is not None), i
    assert (c in m.ALPHA) == (re.fullmatch(r'[A-Za-z]', c) is not None), i
    assert (c in m.ALNUM) == (re.fullmatch(r'[A-Za-z0-9]', c) is not None), i
    assert (c in m.FOLD) == (c in m.UPPER)
    assert (c in m.QDT) == (c in '\t ' or c == '!' or (0x23 <= i <= 0x5B) or (0x5D <= i <= 0x7E)), i
    assert (c in m.QPT) == (c == '\t' or 0x20 <= i <= 0x7E), i
    assert m.qvalue_reason(c) == ('ok' if c in '01' else ('char' if c not in m.DIGITS + '.' else 'form')), i
    assert m.language_range_reason(c) == ('ok' if c in m.ALPHA or c == '*' else 'form'), i
    assert m.media_range_reason('a/b' + c) == ('ok' if c in m.TCHARS + ';' else ('tail' if c in ', \t' else 'semicolon')), i
    assert m.accept_reason('a/b' + c) == ('ok' if c in m.TCHARS + ';, \t' else 'semicolon'), i
    if c in m.ALPHA or c in ', \t':
        want_l = 'ok'
    elif c in m.DIGITS + '-':
        want_l = 'form'
    elif c == ';':
        want_l = 'weight.name'
    elif c == '*':
        want_l = 'form'
    elif c in m.TCHARS:
        want_l = 'char'
    else:
        want_l = 'comma'
    assert m.accept_language_reason('en' + c) == want_l, i
    if c == '"':
        want_q = 'semicolon'
    elif c == '\\':
        want_q = 'param.value'
    elif c in m.QDT:
        want_q = 'ok'
    else:
        want_q = 'param.value'
    assert m.media_range_reason('a/b;p="' + c + '"') == want_q, i
    assert m.accept_reason('a/b;p=' + c) == ('ok' if c in m.TCHARS else 'param.value'), i


@pytest.mark.parametrize('ch', LOOKALIKES)
def test_lookalikes_are_refused_everywhere(ch):
    for st in (m.TCHARS, m.QDT, m.QPT, m.VCHAR, m.DIGITS, m.UPPER, m.LOWER, m.ALPHA, m.ALNUM):
        assert ch not in st
    assert ch not in m.FOLD
    assert m.qvalue_reason('0.' + ch) == 'char'
    assert m.media_range_reason('a' + ch + '/b') == 'slash' and m.media_range_reason('a/' + ch + 'b') == 'subtype'
    assert m.media_range_reason('a/b;p' + ch + '=1') == 'param.equals' and m.media_range_reason('a/b;p=1' + ch) == 'semicolon'
    assert m.language_range_reason('a' + ch) == 'char'
    assert m.accept_reason('a/b' + ch) == 'semicolon'
    assert m.accept_language_reason('en' + ch) == 'comma'
    assert run('split_accept', 'a/b' + ch) == E('split_accept', 'bad_value:text.semicolon')
    assert run('split_accept_language', 'en' + ch) == E('split_accept_language', 'bad_value:text.comma')


NDS = [chr(i) for i in range(sys.maxunicode + 1) if unicodedata.category(chr(i)) == 'Nd' and i > 127]


def test_every_unicode_decimal_digit_is_refused_in_every_slot():
    assert len(NDS) > 500
    for d in NDS:
        assert m.qvalue_reason('0.' + d) == 'char' and m.qvalue_reason(d) == 'char'
        assert m.media_range_reason('a' + d + '/b') == 'slash' and m.language_range_reason('a' + d) == 'char'
        assert m.accept_reason('a/b' + d) == 'semicolon' and m.accept_language_reason('en' + d) == 'comma'


def test_order_docstrings_and_private_names():
    fns = [n for n, v in vars(m).items() if inspect.isfunction(v) and v.__module__ == m.__name__ and not n.startswith('_') and n != 'make_fail']
    assert tuple(fns) == NAMES
    for n in NAMES + PRIVATE + ('make_fail',):
        assert getattr(m, n).__doc__ is None, n
    assert m.__doc__ == DOC_EXACT
    for n in PRIVATE:
        assert inspect.isfunction(getattr(m, n))
    priv = tuple(n for n, v in vars(m).items() if inspect.isfunction(v) and v.__module__ == m.__name__ and n.startswith('_'))
    assert priv == PRIVATE


def test_header_quotes_are_in_the_header_and_distinct():
    flat = re.sub(r'\s+', ' ', m.__doc__)
    assert len(QUOTES) == len(set(QUOTES))
    for q in QUOTES:
        assert re.sub(r'\s+', ' ', q) in flat, q


def test_header_names_every_erratum_source_and_function():
    d = m.__doc__
    for tok in ('7138', '14 errata', '1 erratum', 'RFC 9110', 'RFC 4647', 'RFC 6838', 'RFC 2045',
                '21c1cdce6ab0e5509b04d84a28000836c7a087cf786efe6f04877ebfff47232a', '999e4e23ca5b8925ac5f154855af0f2948a5d26d14853249c9fc857e469ecb49',
                '502941 bytes', 'Updated by', 'Obsoleted by'):
        assert tok in d, tok
    for n in NAMES:
        assert n in d, n
    for r in ('empty', 'char', 'form', 'type', 'slash', 'subtype', 'semicolon', 'tail', 'comma', 'param.name', 'param.equals', 'param.value',
              'weight.name', 'weight.equals', 'weight.value', 'range', 'milli'):
        assert r in d, r


# ---- source bans -------------------------------------------------------------------------------------------------
def _src():
    return open(MODPATH).read()


def test_module_imports_and_source_bans():
    tree = ast.parse(_src())
    mods = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            mods.append(n.module)
    assert sorted(mods) == sorted(['importlib.util', 'app.modules.instinct_doc.p235_concepts_registry'])
    names = set()
    attrs = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            attrs.add(n.attr)
    assert attrs == {'name'}
    for bad in ('re', 'unicodedata', 'urllib', 'ipaddress', 'socket', 'os', 'sys', 'time', 'random', 'datetime', 'open', 'eval', 'exec', '__import__', 'input', 'print',
                'ord', 'chr', 'isinstance', 'getattr', 'setattr', 'globals', 'locals', 'vars', 'hash', 'id', 'sorted', 'reversed', 'map', 'filter', 'any', 'all',
                'dict', 'set', 'frozenset', 'bytes', 'repr', 'format', 'sum', 'min', 'max', 'abs', 'divmod', 'zip', 'enumerate', 'iter', 'next'):
        assert bad not in names, bad
    for node in ast.walk(tree):
        assert not isinstance(node, (ast.Lambda, ast.Global, ast.Nonlocal, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.Starred, ast.JoinedStr, ast.Await, ast.Yield))
    src = _src()
    banned = [' or ' + 'True', 'if ' + 'False', 'else ' + 'True', ' and ' + 'False', ' or ' + 'False']
    for b in banned:
        assert b not in src, b
    assert 'import *' not in src


def test_source_and_tests_have_no_vacuous_assertions():
    me = open(os.path.join(HERE, 'test_instinct_p235_concepts_batch1219_httpaccept.py')).read()
    for b in (' or ' + 'True', 'if ' + 'False:', 'else ' + 'True', ' and ' + 'False', ' or ' + 'False', 'assert ' + 'True', 'assert ' + '1 ', 'assert ' + 'not ' + 'False'):
        assert b not in me, b


# ---- exact types ---------------------------------------------------------------------------------------------------
def arg_vectors(fn):
    for name, good in ARGSPEC[fn]:
        for bad in JUNK + STR_HOSTILE + [BoolLike(1)]:
            if type(bad) is type(good):
                continue
            yield name, [bad]


@pytest.mark.parametrize('fn', NAMES)
def test_every_argument_is_an_exact_type_by_identity(fn):
    n = 0
    for name, args in arg_vectors(fn):
        assert run(fn, *args) == E(fn, 'bad_type:' + name), (fn, name, args[0])
        n += 1
    assert n >= 14


# ---- caps: pinned at cap and cap + 1, length before content ----------------------------------------------------------
CAP_OK = {
    'qvalue_reason': '0.' + '1' * 4094,
    'media_range_reason': 'a/b;p=' + 'b' * 4090,
    'language_range_reason': 'aaaaaaaa-' * 455 + 'a',
    'accept_reason': 'a/b;p=' + 'b' * 4090,
    'accept_language_reason': 'en-gb;q=0.8' + ',' * 4085,
    'split_accept': 'a/b;p=' + 'b' * 4090,
    'split_accept_language': 'en-gb;q=0.8' + ',' * 4085,
}


@pytest.mark.parametrize('fname', [n for n in NAMES if n not in ('qvalue_format', 'accept_format', 'accept_language_format')])
def test_text_caps_pinned_at_cap_and_cap_plus_one(fname):
    fn = getattr(m, fname)
    good = CAP_OK[fname]
    assert len(good) == 4096
    if fname == 'qvalue_reason':
        assert fn(good) == 'form'
    elif fname == 'split_accept':
        assert fn(good) == [('a/b', (('p', 'b' * 4090),), None)]
    elif fname == 'split_accept_language':
        assert fn(good) == [('en-gb', '0.8')]
    else:
        assert fn(good) == 'ok', fname
    over = good + 'a'
    with pytest.raises(ValueError) as ei:
        fn(over)
    assert str(ei.value) == PFX + '%s:bad_value:text.length' % fname
    with pytest.raises(ValueError) as ei2:
        fn([4097] * 2)
    assert str(ei2.value) == PFX + '%s:bad_type:text' % fname
    if fname == 'qvalue_reason':
        with pytest.raises(ValueError) as ei3:
            fn(chr(0x100) * 4097)
        assert str(ei3.value) == PFX + 'qvalue_reason:bad_value:text.length'


def test_format_entry_caps_and_shape_errors():
    ents = [('a/b', (), None)] * 4096
    assert m.accept_format(ents) == ', '.join(['a/b'] * 4096)
    assert m.accept_language_format([('en', None)] * 4096) == ', '.join(['en'] * 4096)
    with pytest.raises(ValueError) as ei:
        m.accept_format([('a/b', (), None)] * 4097)
    assert str(ei.value) == PFX + 'accept_format:bad_value:entries.length'
    with pytest.raises(ValueError) as ei2:
        m.accept_language_format([('en', None)] * 4097)
    assert str(ei2.value) == PFX + 'accept_language_format:bad_value:entries.length'
    with pytest.raises(ValueError) as ei3:
        m.accept_format([['a/b', (), None]])
    assert str(ei3.value) == PFX + 'accept_format:bad_type:entries.item'
    with pytest.raises(ValueError) as ei4:
        m.accept_language_format([('en', None, None)])
    assert str(ei4.value) == PFX + 'accept_language_format:bad_type:entries.item'


def test_output_closure_splits_and_formats():
    s0 = 'text/html;level="x y z";q=0.5, text/*'
    out = m.split_accept(s0)
    assert out == [('text/html', (('level', 'x y z'),), '0.5'), ('text/*', (), None)]
    total = sum(len(a) + sum(len(n) + len(v) for n, v in ps) + (len(q) if q else 0) for a, ps, q in out)
    assert total < len(s0)
    assert m.accept_format(m.split_accept('text/html; q=0.5, text/*')) == 'text/html; q=0.5, text/*'
    assert m.accept_language_format(m.split_accept_language('da, en-gb;q=0.8')) == 'da, en-gb; q=0.8'
    f = m.accept_format([('a/b', (('p', 'v"'),), '0.1')])
    assert m.split_accept(f) == [('a/b', (('p', 'v"'),), '0.1')]


# ---- memory: caps are checked before work ---------------------------------------------------------------------------
def test_cap_is_checked_before_any_allocation_or_scan():
    tracemalloc.start()
    try:
        for fname, good in CAP_OK.items():
            big = good + 'a'
            tracemalloc.clear_traces()
            tracemalloc.reset_peak()
            base = tracemalloc.get_traced_memory()[0]
            r = run(fname, big)
            peak = tracemalloc.get_traced_memory()[1] - base
            assert r[0] == 'err' and peak < 4000, (fname, peak)
        big_ents = [('a/b', (), None)] * 4097
        tracemalloc.clear_traces()
        tracemalloc.reset_peak()
        base = tracemalloc.get_traced_memory()[0]
        r = run('accept_format', big_ents)
        peak = tracemalloc.get_traced_memory()[1] - base
        assert r[0] == 'err' and peak < 4000, ('accept_format', peak)
    finally:
        tracemalloc.stop()


# ---- no input mutation, no global state ---------------------------------------------------------------------------------
def test_results_are_fresh_exact_types_and_inputs_are_not_mutated():
    for fname in ('qvalue_reason', 'media_range_reason', 'language_range_reason', 'accept_reason', 'accept_language_reason'):
        assert type(getattr(m, fname)('a/b' if 'media' in fname or 'accept' in fname and 'language' not in fname else ('0.5' if 'qvalue' in fname else 'en'))) is str
    assert type(m.qvalue_format(500)) is str
    s1 = m.split_accept('a/b;p=1')
    s2 = m.split_accept('a/b;p=1')
    assert s1 is not s2 and s1 == s2 == [('a/b', (('p', '1'),), None)] and type(s1) is list
    assert type(s1[0]) is tuple and len(s1[0]) == 3 and type(s1[0][1]) is tuple
    l1 = m.split_accept_language('en;q=0.8')
    l2 = m.split_accept_language('en;q=0.8')
    assert l1 is not l2 and l1 == l2 == [('en', '0.8')] and type(l1[0]) is tuple and len(l1[0]) == 2

# ---- semantics: grammar tables, check order, both-bad pins, splits, formats, fuzz -----------------------------
QV_CASES = [
    ('', 'empty'), ('0', 'ok'), ('1', 'ok'), ('0.', 'ok'), ('1.', 'ok'),
    ('0.0', 'ok'), ('0.00', 'ok'), ('0.000', 'ok'), ('0.001', 'ok'), ('0.999', 'ok'),
    ('1.0', 'ok'), ('1.00', 'ok'), ('1.000', 'ok'),
    ('0.0000', 'form'), ('0.0001', 'form'), ('1.0000', 'form'),
    ('1.1', 'form'), ('1.01', 'form'), ('1.10', 'form'), ('1.001', 'form'), ('1.0001', 'form'),
    ('2', 'form'), ('9', 'form'), ('00', 'form'), ('01', 'form'), ('10', 'form'), ('11', 'form'),
    ('0..', 'form'), ('..', 'form'), ('.', 'form'), ('0..1', 'form'), ('1..0', 'form'), ('-.1', 'char'), ('+1', 'char'),
    ('a', 'char'), ('1.a', 'char'), ('0.5 ', 'char'), (' 0.5', 'char'), ('0,5', 'char'),
    ('1.a', 'char'), ('2.x', 'char'), ('0x', 'char'), ('\t0.5', 'char'),
]
@pytest.mark.parametrize('text,want', QV_CASES)
def test_qvalue_reason_table(text, want):
    assert m.qvalue_reason(text) == want


def test_qvalue_reason_char_beats_form_and_form_positions():
    assert m.qvalue_reason('2x') == 'char'
    assert m.qvalue_reason('2') == 'form'
    assert m.qvalue_reason('x2') == 'char'
    assert m.qvalue_reason('1.0000') == 'form'
    assert m.qvalue_reason('0.0001') == 'form'


QF_CASES = [(0, '0'), (1000, '1'), (1, '0.001'), (10, '0.01'), (100, '0.1'), (500, '0.5'), (50, '0.05'),
            (555, '0.555'), (550, '0.55'), (505, '0.505'), (999, '0.999'), (110, '0.11'), (101, '0.101')]
@pytest.mark.parametrize('milli,want', QF_CASES)
def test_qvalue_format_table(milli, want):
    got = m.qvalue_format(milli)
    assert got == want and m.qvalue_reason(got) == 'ok'


def test_qvalue_format_errors():
    assert run('qvalue_format', True) == E('qvalue_format', 'bad_type:milli')
    assert run('qvalue_format', False) == E('qvalue_format', 'bad_type:milli')
    assert run('qvalue_format', BoolLike(3)) == E('qvalue_format', 'bad_type:milli')
    assert run('qvalue_format', '500') == E('qvalue_format', 'bad_type:milli')
    assert run('qvalue_format', -1) == E('qvalue_format', 'bad_value:milli.range')
    assert run('qvalue_format', 1001) == E('qvalue_format', 'bad_value:milli.range')
    assert m.qvalue_format(0) == '0' and m.qvalue_format(1000) == '1'


MR_CASES = [
    ('', 'empty'), ('text/html', 'ok'), ('TEXT/HTML', 'ok'), ('*/*', 'ok'), ('text/*', 'ok'), ('*/html', 'ok'),
    ('a/b', 'ok'), ('a-b.c/d_e', 'ok'),
    ('text', 'slash'), ('a', 'slash'), ('a b/c', 'slash'), ('/b', 'type'), ('', 'empty'), ('/', 'type'),
    ('a/', 'subtype'), ('a/ ', 'subtype'), ('a//b', 'subtype'),
    ('a/b;p=1', 'ok'), ('a/b;p="1"', 'ok'), ('a/b;p="a b"', 'ok'), ('a/b;p=""', 'ok'),
    ('a/b;', 'ok'), ('a/b;;p=1', 'ok'), ('a/b ; p=1', 'ok'), ('a/b\t;\tp=1', 'ok'),
    ('a/b;P=1;q=0.5', 'ok'), ('a/b;q=0.5', 'ok'), ('a/b;q=2', 'ok'),
    ('a/b;p', 'param.equals'), ('a/b;p ', 'param.equals'), ('a/b;p =1', 'param.equals'), ('a/b;p= 1', 'param.value'),
    ('a/b;=1', 'param.name'), ('a/b; =1', 'param.name'), ('a/b;p=', 'param.value'), ('a/b;p="x', 'param.value'),
    ('a/b;p=x"', 'semicolon'), ('a/b p=1', 'semicolon'), ('a/b  p=1', 'semicolon'),
    ('a/b,', 'tail'), ('a/b ,', 'tail'), ('a/b ', 'tail'), ('a/b\t', 'tail'), ('a/b; ', 'tail'),
    ('a/b;p=1 ', 'tail'), ('a/b;p=1,', 'tail'),
]
@pytest.mark.parametrize('text,want', MR_CASES)
def test_media_range_reason_table(text, want):
    assert m.media_range_reason(text) == want


LR_CASES = [
    ('', 'empty'), ('en', 'ok'), ('EN', 'ok'), ('en-gb', 'ok'), ('en-GB-oed', 'ok'), ('a-b-c1', 'ok'),
    ('*', 'ok'), ('abcdefgh', 'ok'), ('a-12345678', 'ok'), ('i-klingon', 'ok'), ('x-private', 'ok'),
    ('1a', 'form'), ('a1', 'form'), ('Q0', 'form'), ('a1-b2', 'form'), ('ab-c1', 'ok'), ('en--gb', 'form'), ('en-', 'form'), ('-en', 'form'),
    ('abcdefghi', 'form'), ('a-123456789', 'form'), ('a-bcdefghi', 'ok'),
    ('*-a', 'form'), ('a-*', 'form'), ('**', 'form'), ('*1', 'form'),
    ('en_gb', 'char'), ('en.gb', 'char'), ('en gb', 'char'), ('e"n', 'char'), ("e'n", 'char'),
]
@pytest.mark.parametrize('text,want', LR_CASES)
def test_language_range_reason_table(text, want):
    assert m.language_range_reason(text) == want


A_CASES = [
    ('', 'ok'), (' ', 'ok'), (' , , ', 'ok'), (',', 'ok'), (',,', 'ok'),
    ('text/html', 'ok'), (' text/html', 'ok'), ('text/html ', 'ok'), ('\ttext/html\t', 'ok'),
    ('audio/*; q=0.2, audio/basic', 'ok'),
    ('text/plain; q=0.5, text/html, text/x-dvi; q=0.8, text/x-c', 'ok'),
    ('text/*, text/plain, text/plain;format=flowed, */*', 'ok'),
    ('text/*;q=0.3, text/plain;q=0.7, text/plain;format=flowed, text/plain;format=fixed;q=0.4, */*;q=0.5', 'ok'),
    ('text/html;level=3; q=0.7, text/plain', 'ok'), ('text/html;Q=0.5', 'ok'), ('text/html;;q=0.5', 'ok'),
    ('text/html;, text/plain', 'ok'), ('text/html; , text/plain', 'ok'),
    ('text/html;q=2', 'ok'), ('text/html;q=0.5;p=1', 'ok'),
    ('text/html q=0.5', 'semicolon'), ('x q=1, a/b', 'slash'),
    ('text/html;q =0.5', 'param.equals'), ('text/html;q= 0.5', 'param.value'),
    ('text/html,', 'ok'), (',text/html', 'ok'), ('text/html,,text/plain', 'ok'),
    ('text/html;level=3;q=0.7;', 'ok'), ('a', 'slash'), ('a/', 'subtype'), ('a/b;p', 'param.equals'),
    ('a/b;p="unclosed', 'param.value'), ('a/b;p="unclosed, c/d', 'param.value'),
]
@pytest.mark.parametrize('text,want', A_CASES)
def test_accept_reason_table(text, want):
    assert m.accept_reason(text) == want


L_CASES = [
    ('', 'ok'), (' ', 'ok'), (' , , ', 'ok'),
    ('da, en-gb;q=0.8, en;q=0.7', 'ok'), ('en', 'ok'), ('*', 'ok'), ('*, en', 'ok'),
    ('en-gb', 'ok'), ('en;q=1', 'ok'), ('en;Q=1', 'ok'), ('en ; q=0.5', 'ok'), ('en\t;\tq=0.5', 'ok'),
    ('en;q=0', 'ok'), ('en;q=1.000', 'ok'), ('en;q=0.', 'ok'),
    ('en;foo=1', 'weight.name'), ('en;q=1;p=2', 'weight.value.char'),
    ('en;q =1', 'weight.equals'), ('en;w=1', 'weight.name'), ('en;', 'weight.name'), ('en; ', 'weight.name'),
    ('en;q=', 'weight.value.empty'), ('en;q=2', 'weight.value.form'), ('en;q=1.1', 'weight.value.form'),
    ('en;q=0.5x', 'weight.value.char'), ('en;q=a', 'weight.value.empty'),
    ('en;q=0.5 ', 'ok'), ('en;q=0.5 , da', 'ok'), ('en;q=0.5 x', 'comma'),
    ('en da', 'comma'), ('en; q=0.5 da', 'comma'),
    ('1a', 'form'), ('en--gb', 'form'), ('en-', 'form'),
    ('en,', 'ok'), (',en', 'ok'), ('en,,da', 'ok'), ('en, , da', 'ok'),
]
@pytest.mark.parametrize('text,want', L_CASES)
def test_accept_language_reason_table(text, want):
    assert m.accept_language_reason(text) == want


def test_split_accept_tables():
    assert m.split_accept('') == []
    assert m.split_accept(' , , ') == []
    assert m.split_accept(',text/html,') == [('text/html', (), None)]
    assert m.split_accept('audio/*; q=0.2, audio/basic') == [('audio/*', (), '0.2'), ('audio/basic', (), None)]
    assert m.split_accept('text/*;q=0.3, text/plain;format=flowed, text/plain;format=fixed;q=0.4, */*;q=0.5') == [
        ('text/*', (), '0.3'), ('text/plain', (('format', 'flowed'),), None),
        ('text/plain', (('format', 'fixed'),), '0.4'), ('*/*', (), '0.5')]
    assert m.split_accept('text/html;LEVEL="a b";Q=0.5;q=x') == [('text/html', (('LEVEL', 'a b'), ('q', 'x')), '0.5')]
    assert m.split_accept('text/html;q=2') == [('text/html', (('q', '2'),), None)]
    assert m.split_accept('text/html;q=0.5;q=0.7') == [('text/html', (('q', '0.7'),), '0.5')]
    assert m.split_accept('text/html;p="a\\"b"') == [('text/html', (('p', 'a"b'),), None)]
    assert m.split_accept('text/html;p=""') == [('text/html', (('p', ''),), None)]
    assert m.split_accept('text/html;;p=1') == [('text/html', (('p', '1'),), None)]
    assert m.split_accept('TEXT/HTML') == [('TEXT/HTML', (), None)]
    assert m.split_accept('a/b;p=1 , c/d') == [('a/b', (('p', '1'),), None), ('c/d', (), None)]


def test_split_accept_language_tables():
    assert m.split_accept_language('') == []
    assert m.split_accept_language(' , ,') == []
    assert m.split_accept_language('da, en-gb;q=0.8, en;q=0.7') == [('da', None), ('en-gb', '0.8'), ('en', '0.7')]
    assert m.split_accept_language('*') == [('*', None)]
    assert m.split_accept_language('en ; q=0.5') == [('en', '0.5')]
    assert m.split_accept_language('en;q=0.5 , da') == [('en', '0.5'), ('da', None)]
    assert m.split_accept_language('EN-gb;Q=1') == [('EN-gb', '1')]


def test_split_errors_use_reason_prefixes():
    assert run('split_accept', '') == ('ok', [])
    assert run('split_accept', 'a') == E('split_accept', 'bad_value:text.slash')
    assert run('split_accept', 'a/b q=1') == E('split_accept', 'bad_value:text.semicolon')
    assert run('split_accept', 'a/b;p="x') == E('split_accept', 'bad_value:text.param.value')
    assert run('split_accept', 'a/b;p=1 c/d') == E('split_accept', 'bad_value:text.semicolon')
    assert run('split_accept_language', 'en;foo=1') == E('split_accept_language', 'bad_value:text.weight.name')
    assert run('split_accept_language', 'en;q=2') == E('split_accept_language', 'bad_value:text.weight.value.form')
    assert run('split_accept_language', 'en da') == E('split_accept_language', 'bad_value:text.comma')
    assert run('split_accept_language', 'en-gb-US') == ('ok', [('en-gb-US', None)])


def test_format_tables_and_round_trips():
    assert m.accept_format([]) == '' and m.accept_reason('') == 'ok'
    assert m.accept_language_format([]) == ''
    assert m.accept_format([('text/html', (), None)]) == 'text/html'
    assert m.accept_format([('text/html', (('level', '3'),), '0.7'), ('text/plain', (), None)]) == 'text/html; level=3; q=0.7, text/plain'
    assert m.accept_format([('a/b', (('p', 'a b'),), None)]) == 'a/b; p="a b"'
    assert m.accept_format([('a/b', (('p', 'a"b'),), None)]) == 'a/b; p="a\\"b"'
    assert m.accept_format([('a/b', (('p', ''),), None)]) == 'a/b; p=""'
    assert m.accept_language_format([('da', None), ('en-gb', '0.8')]) == 'da, en-gb; q=0.8'
    for t in ('text/*;q=0.3, text/plain;format=flowed, */*;q=0.5', 'audio/*; q=0.2, audio/basic', 'text/html;level=3; q=0.7'):
        assert m.accept_reason(m.accept_format(m.split_accept(t))) == 'ok'
        assert m.split_accept(m.accept_format(m.split_accept(t))) == m.split_accept(t)
    for t in ('da, en-gb;q=0.8, en;q=0.7', '*', 'en ; q=0.5'):
        assert m.split_accept_language(m.accept_language_format(m.split_accept_language(t))) == m.split_accept_language(t)


def test_format_validation_errors():
    assert run('accept_format', [('a', (), None)]) == E('accept_format', 'bad_value:range.form')
    assert run('accept_format', [('a/b ', (), None)]) == E('accept_format', 'bad_value:range.form')
    assert run('accept_format', [('a/b', (('p x', '1'),), None)]) == E('accept_format', 'bad_value:name.form')
    assert run('accept_format', [('a/b', (('p', '1'),), '2')]) == E('accept_format', 'bad_value:q.form')
    assert run('accept_format', [('a/b', [('p', '1')], None)]) == E('accept_format', 'bad_type:entries.item')
    assert run('accept_format', (('a/b', (), None),)) == E('accept_format', 'bad_type:entries')
    assert run('accept_language_format', [('1a', None)]) == E('accept_language_format', 'bad_value:range.form')
    assert run('accept_language_format', [('en', '2')]) == E('accept_language_format', 'bad_value:q.form')
    assert run('accept_language_format', [('en', None, None)]) == E('accept_language_format', 'bad_type:entries.item')
    assert run('accept_language_format', [('en',)]) == E('accept_language_format', 'bad_type:entries.item')


def test_qvalue_format_is_canonical_and_reason_is_its_inverse():
    for k in range(1001):
        s = m.qvalue_format(k)
        assert m.qvalue_reason(s) == 'ok', k
    assert m.qvalue_format(1) != '0.001' or m.qvalue_reason('0.001') == 'ok'


def _fz_string(rng):
    alpha = 'abAB09/",= \t\\";qQ.-*~!#\x7f\x80'
    return ''.join(rng.choice(alpha) for _ in range(rng.randrange(0, 22)))


def test_fuzz_reason_functions_against_oracles_1200_iterations():
    rng = random.Random(1219)
    for _ in range(1200):
        t = _fz_string(rng)
        assert (m.qvalue_reason(t) == 'ok') == o_qv(t), repr(t)


def test_fuzz_accept_against_list_oracles_1200_iterations():
    rng = random.Random(1220)
    for _ in range(1200):
        t = _fz_string(rng)
        assert (m.accept_reason(t) == 'ok') == o_accept(t), repr(t)
        assert (m.accept_language_reason(t) == 'ok') == o_accept_language(t), repr(t)


def test_fuzz_split_against_reason_1200_iterations():
    rng = random.Random(1221)
    for _ in range(1200):
        t = _fz_string(rng)
        if m.accept_reason(t) == 'ok':
            assert m.accept_reason(m.accept_format(m.split_accept(t))) == 'ok', repr(t)
        else:
            assert run('split_accept', t)[0] == 'err', repr(t)
        if m.accept_language_reason(t) == 'ok':
            assert m.accept_language_reason(m.accept_language_format(m.split_accept_language(t))) == 'ok', repr(t)
        else:
            assert run('split_accept_language', t)[0] == 'err', repr(t)


# ---- registry guard, import log, namespace ----------------------------------------------------------------------
def test_registry_absent_uses_local_fallback(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh()
    assert mod.make_fail.__module__ == mod.__name__
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert run('qvalue_reason', 1, mod=mod) == ('err', 'P235:qvalue_reason:bad_type:text')


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
    assert e.value is err and type(e.value) is ImportError


IMPORTS = [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]
NAMESPACE = (['find_spec'] + ['SCOPE', 'NOT_CLAIMED', 'CLAIMS', 'ADJACENT', 'TEXT_CAP', 'DIGITS', 'UPPER', 'LOWER', 'TCHARS', 'ALPHA', 'ALNUM',
                              'FOLD', 'QDT', 'VCHAR', 'QPT', '_MID', '_TAIL', '_REG', 'make_fail'] + list(PRIVATE) + list(NAMES))
CALLS = [(fn, tuple(g for _n, g in ARGSPEC[fn]), tuple([None] + [g for _n, g in ARGSPEC[fn]][1:])) for fn in NAMES]


@pytest.mark.parametrize('world', ['absent', 'foreign', 'registry_raise', 'present'])
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


# ---- the shared corpus: one success and every refusal code of every public function --------------------------
CORPUS = []
for _fn in NAMES:
    for _pos, (_name, _g) in enumerate(ARGSPEC[_fn]):
        _args = [g for _n, g in ARGSPEC[_fn]]
        _args[_pos] = 5 if type(_g) is str else 'x'
        CORPUS.append((_fn, tuple(_args), 'bad_type:' + _name))
for _fn in NAMES:
    if _fn in ('qvalue_format', 'accept_format', 'accept_language_format'):
        continue
    CORPUS.append((_fn, ('a' * 4097,), 'bad_value:text.length'))
CORPUS.append(('accept_format', ([('a/b', (), None)] * 4097,), 'bad_value:entries.length'))
CORPUS.append(('accept_language_format', ([('en', None)] * 4097,), 'bad_value:entries.length'))
CORPUS.append(('qvalue_format', (-1,), 'bad_value:milli.range'))
for _r, _t in (('slash', 'a'), ('semicolon', 'a/b x'), ('param.name', 'a/b;='), ('param.equals', 'a/b;p'),
               ('param.value', 'a/b;p='), ('type', '/b'), ('subtype', 'a/')):
    CORPUS.append(('split_accept', (_t,), 'bad_value:text.' + _r))
for _r, _t in (('form', '1a'), ('comma', 'en da'), ('weight.name', 'en;x=1'), ('weight.equals', 'en;q =1'),
               ('weight.value.form', 'en;q=2'), ('weight.value.empty', 'en;q='), ('weight.value.char', 'en;q=0.5x')):
    CORPUS.append(('split_accept_language', (_t,), 'bad_value:text.' + _r))
for _r, _t in (('range.form', [('a', (), None)]), ('name.form', [('a/b', (('p x', '1'),), None)]),
               ('q.form', [('a/b', (), '2')]), ('value.form', [('a/b', (('p', 'a\x01b'),), None)])):
    CORPUS.append(('accept_format', (_t,), 'bad_value:' + _r))
CORPUS.append(('accept_language_format', ([('1a', None)],), 'bad_value:range.form'))
CORPUS.append(('accept_language_format', ([('en', '2')],), 'bad_value:q.form'))
CORPUS.append(('accept_format', ([['a/b', (), None]],), 'bad_type:entries.item'))
CORPUS.append(('accept_format', ([('a/b', [('p', '1')], None)],), 'bad_type:entries.item'))
CORPUS.append(('accept_format', ([('a/b', (('p',),), None)],), 'bad_type:entries.item'))
CORPUS.append(('accept_language_format', ([['en', None]],), 'bad_type:entries.item'))
CORPUS.append(('split_accept', ('a/b;p="x\\',), 'bad_value:text.param.value'))
CORPUS.append(('split_accept', ('a/b, c',), 'bad_value:text.slash'))
CORPUS.append(('split_accept_language', ('en;X=1',), 'bad_value:text.weight.name'))
CORPUS.append(('split_accept_language', ('en;q',), 'bad_value:text.weight.equals'))
CORPUS.append(('accept_format', ([(5, (), None)],), 'bad_type:range'))
CORPUS.append(('accept_format', ([('a/b', ((5, '1'),), None)],), 'bad_type:name'))
CORPUS.append(('accept_format', ([('a/b', (('p', 5),), None)],), 'bad_type:value'))
CORPUS.append(('accept_format', ([('a/b', (), 5)],), 'bad_type:q'))
CORPUS.append(('accept_language_format', ([(5, None)],), 'bad_type:range'))
CORPUS.append(('accept_language_format', ([('en', 5)],), 'bad_type:q'))
CORPUS.append(('accept_format', ([('a' * 4097, (), None)],), 'bad_value:range.length'))
CORPUS.append(('accept_format', ([('a/b', (('p' * 4097, '1'),), None)],), 'bad_value:name.length'))
CORPUS.append(('accept_format', ([('a/b', (('p', '1' * 4097),), None)],), 'bad_value:value.length'))
CORPUS.append(('accept_format', ([('a/b', (), '1' * 4097)],), 'bad_value:q.length'))
CORPUS.append(('accept_language_format', ([('a' * 4097, None)],), 'bad_value:range.length'))
CORPUS.append(('accept_language_format', ([('en', '1' * 4097)],), 'bad_value:q.length'))
CORPUS.append(('accept_format', ([('a/b', (('', '1'),), None)],), 'bad_value:name.form'))
CORPUS.append(('accept_format', ([('a/b', ((' x', '1'),), None)],), 'bad_value:name.form'))
CORPUS.append(('accept_format', ([('a/b', (('p', '\x01ab'),), None)],), 'bad_value:value.form'))
CORPUS.append(('split_accept_language', ('en;q=2x',), 'bad_value:text.weight.value.form'))
CORPUS.append(('accept_format', ([('a/b',)],), 'bad_type:entries.item'))
CORPUS.append(('accept_format', ([('a/b', (), None, None)],), 'bad_type:entries.item'))
SUCCESS = [('qvalue_reason', ('0.5',), 'ok'), ('qvalue_reason', ('',), 'empty'), ('qvalue_reason', ('\x01',), 'char'),
           ('qvalue_reason', ('2',), 'form'), ('qvalue_reason', ('1.000',), 'ok'), ('qvalue_reason', ('1.001',), 'form'),
           ('qvalue_format', (0,), '0'), ('qvalue_format', (1000,), '1'), ('qvalue_format', (500,), '0.5'), ('qvalue_format', (1,), '0.001'),
           ('media_range_reason', ('text/html',), 'ok'), ('media_range_reason', ('*/*',), 'ok'), ('media_range_reason', ('',), 'empty'),
           ('media_range_reason', ('a',), 'slash'), ('media_range_reason', ('/b',), 'type'), ('media_range_reason', ('a/',), 'subtype'),
           ('media_range_reason', ('a/b p=1',), 'semicolon'), ('media_range_reason', ('a/b;p',), 'param.equals'),
           ('media_range_reason', ('a/b;=1',), 'param.name'), ('media_range_reason', ('a/b;p=',), 'param.value'),
           ('media_range_reason', ('a/b;',), 'ok'), ('media_range_reason', ('a/b;;p=1',), 'ok'), ('media_range_reason', ('a/b ',), 'tail'),
           ('language_range_reason', ('en-gb',), 'ok'), ('language_range_reason', ('*',), 'ok'), ('language_range_reason', ('',), 'empty'),
           ('language_range_reason', ('1a',), 'form'), ('language_range_reason', ('en_gb',), 'char'),
           ('language_range_reason', ('abcdefghi',), 'form'), ('language_range_reason', ('en--gb',), 'form'),
           ('accept_reason', ('',), 'ok'), ('accept_reason', (' , ',), 'ok'), ('accept_reason', ('text/html',), 'ok'),
           ('accept_reason', ('audio/*; q=0.2, audio/basic',), 'ok'), ('accept_reason', ('a',), 'slash'),
           ('accept_reason', ('a/b q=1',), 'semicolon'), ('accept_reason', ('a/b;p',), 'param.equals'),
           ('accept_language_reason', ('',), 'ok'), ('accept_language_reason', ('da, en-gb;q=0.8, en;q=0.7',), 'ok'),
           ('accept_language_reason', ('1a',), 'form'), ('accept_language_reason', ('en da',), 'comma'),
           ('accept_language_reason', ('en;x=1',), 'weight.name'), ('accept_language_reason', ('en;q =1',), 'weight.equals'),
           ('accept_language_reason', ('en;q=',), 'weight.value.empty'), ('accept_language_reason', ('en;q=2',), 'weight.value.form'),
           ('accept_language_reason', ('en;q=0.5x',), 'weight.value.char'),
           ('split_accept', ('',), []), ('split_accept', ('audio/*; q=0.2, audio/basic',), [('audio/*', (), '0.2'), ('audio/basic', (), None)]),
           ('split_accept', ('text/html;p="a b"',), [('text/html', (('p', 'a b'),), None)]),
           ('split_accept_language', ('',), []), ('split_accept_language', ('da, en-gb;q=0.8',), [('da', None), ('en-gb', '0.8')]),
           ('accept_format', ([],), ''), ('accept_format', ([('text/html', (('level', '3'),), '0.7')],), 'text/html; level=3; q=0.7'),
           ('accept_format', ([('a/b', (('p', 'a b'),), None)],), 'a/b; p="a b"'),
           ('accept_language_format', ([],), ''), ('accept_language_format', ([('da', None), ('en-gb', '0.8')],), 'da, en-gb; q=0.8'),
           ('accept_language_reason', ('en;q=0.5\t',), 'ok'),
           ('media_range_reason', ('a/b;p="x\\',), 'param.value'), ('media_range_reason', ('a/b;p="a\\\x01"',), 'param.value'),
           ('split_accept', ('a/b;, text/plain',), [('a/b', (), None), ('text/plain', (), None)]),
           ('accept_format', ([('a/b', (('p', ' x'),), None)],), 'a/b; p=" x"'),
           ('accept_format', ([('a/b', (('p', 'a\\b'),), None)],), 'a/b; p="a\\\\b"'),
           ('media_range_reason', ('a/b;p="a\\b"',), 'ok'), ('split_accept', ('a/b;p="a\\b"',), [('a/b', (('p', 'ab'),), None)]),
           ]


def drive(mod, pfx=None):
    p = PFX if pfx is None else pfx
    for fn, args, want in CORPUS:
        with pytest.raises(ValueError) as e:
            getattr(mod, fn)(*args)
        assert str(e.value) == p + fn + ':' + want
    for fn, args, want in SUCCESS:
        assert getattr(mod, fn)(*args) == want


def test_corpus_reaches_every_refusal_code_and_every_success_branch():
    drive(m)
    codes = {(fn, w) for fn, a, w in CORPUS}
    for fn in NAMES:
        for _name, _g in ARGSPEC[fn]:
            assert (fn, 'bad_type:' + _name) in codes
        if fn in ('qvalue_format', 'accept_format', 'accept_language_format'):
            continue
        assert (fn, 'bad_value:text.length') in codes
    assert ('accept_format', 'bad_value:entries.length') in codes and ('accept_language_format', 'bad_value:entries.length') in codes
    for r in ('slash', 'semicolon', 'param.name', 'param.equals', 'param.value', 'type', 'subtype'):
        assert ('split_accept', 'bad_value:text.' + r) in codes
    for r in ('form', 'comma', 'weight.name', 'weight.equals', 'weight.value.form', 'weight.value.empty', 'weight.value.char'):
        assert ('split_accept_language', 'bad_value:text.' + r) in codes
    for r in ('ok', 'empty', 'char', 'form'):
        assert any(f == 'qvalue_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'empty', 'slash', 'type', 'subtype', 'semicolon', 'param.name', 'param.equals', 'param.value', 'tail'):
        assert any(f == 'media_range_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'empty', 'form', 'char'):
        assert any(f == 'language_range_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'slash', 'semicolon', 'param.equals'):
        assert any(f == 'accept_reason' and w == r for f, a, w in SUCCESS)
    for r in ('ok', 'form', 'comma', 'weight.name', 'weight.equals', 'weight.value.empty', 'weight.value.form', 'weight.value.char'):
        assert any(f == 'accept_language_reason' and w == r for f, a, w in SUCCESS)


def test_fallback_failer_world_has_no_imports_one_success_and_every_refusal(mp):
    real = builtins.__import__
    seen = []
    name = 'b1219_fallback_world'

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
    mod = fresh('b1219_site_world')
    sites = set()
    for fn, args, want in CORPUS:
        with pytest.raises(Stop) as e:
            getattr(mod, fn)(*args)
        assert str(e.value) == fn + ':' + want
        frames = [f for f in traceback.extract_tb(e.value.__traceback__) if f.filename == mod.__file__]
        assert frames[-1].line.strip().startswith('fail(')
        sites.add(frames[-1].lineno)
    src = inspect.getsource(mod).split('\n')
    all_sites = {i + 1 for i, line in enumerate(src) if line.strip().startswith('fail(') and 'def ' not in line}
    assert sites == all_sites, sorted(all_sites - sites)


def test_fixture_autouse_hook_is_installed_and_sees_module_names():
    assert getattr(builtins.__import__, '__name__', '') == 'hook'


@pytest.fixture(autouse=True)
def _module_never_imports_at_call_time():
    """Every test drives the module through the hook: any import executed by the module's own code after load fails the test."""
    real = builtins.__import__
    seen = []

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == m.__name__:
            seen.append((n, tuple(fromlist or ()), level))
        return real(n, g, l, fromlist, level)
    builtins.__import__ = hook
    try:
        yield
    finally:
        if builtins.__import__ is hook:
            builtins.__import__ = real
    assert seen == []


def test_fallback_failer_functions_carry_no_docstring(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh('b1219_doc_world')
    assert mod.make_fail.__doc__ is None
    assert mod.make_fail('x').__doc__ is None
    assert mod.make_fail.__name__ == 'make_fail' and mod.make_fail('x').__name__ == 'fail'


def test_find_spec_is_consulted_exactly_once_in_the_absent_world_simulation(mp):
    spied = []
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda n: spied.append(n) or None)
    mod = fresh('b1219_spec_world')
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
            "import app.modules.instinct_doc.p235_concepts_batch1219_httpaccept as m\n"
            "print(m.accept_reason('text/*;q=0.3, */*'), m.split_accept_language('da, en;q=0.7'), "
            "m.qvalue_format(500), m.media_range_reason('text/html;level=3'))\n") % (
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(m.__file__)))),)
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok [('da', None), ('en', '0.7')] 0.5 ok"
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25, env={'PYTHONHASHSEED': '7'})
    assert out.stdout.strip() == "ok [('da', None), ('en', '0.7')] 0.5 ok"

def test_rev1_fold_pins():
    # A41 final item 1: the qvalue fraction loop examines every digit, not
    # just the first.
    assert m.qvalue_reason('0.0.0') == 'form'
    assert m.qvalue_reason('0.00.') == 'form'
    # A45 F2: more trailing-dot and double-dot qvalue forms.
    assert m.qvalue_reason('0.5.') == 'form'
    assert m.qvalue_reason('0.5.5') == 'form'
    assert m.qvalue_reason('0.12.') == 'form'
    # A41 final item 2: a trailing bare semicolon is a zero-parameter ending,
    # not an IndexError (OURS 4).
    assert m.split_accept('a/b;') == [('a/b', (), None)]
    assert m.split_accept('a/b;p=1;') == [('a/b', (('p', '1'),), None)]
    # A45 F3: in Accept-Language a non-q parameter name is weight.name.
    assert m.accept_language_reason('en;r=0.5') == 'weight.name'
    # A45 F4 + F5: accept_format checks param name type, then value type,
    # then name form, then value form.
    with pytest.raises(ValueError) as e1:
        m.accept_format([('a/b', ((1, 2),), None)])
    assert str(e1.value) == PFX + 'accept_format:bad_type:name'
    with pytest.raises(ValueError) as e2:
        m.accept_format([('a/b', (('p q', 1),), None)])
    assert str(e2.value) == PFX + 'accept_format:bad_type:value'
    with pytest.raises(ValueError) as e3:
        m.accept_format([('a/b', ((1, 'a b'),), None)])
    assert str(e3.value) == PFX + 'accept_format:bad_type:name'
    with pytest.raises(ValueError) as e4:
        m.accept_format([('a/b', (('p q', 'a b'),), None)])
    assert str(e4.value) == PFX + 'accept_format:bad_value:name.form'
    with pytest.raises(ValueError) as e5:
        m.accept_format([('a/b', (('p', 'a\nb'),), None)])
    assert str(e5.value) == PFX + 'accept_format:bad_value:value.form'
    # A45 F1: split_accept detects a quoted q whose content is a valid
    # qvalue and reports it as the weight; a quoted q with an invalid
    # qvalue stays in params. split_accept_language is strict the other
    # way and refuses a quoted q (OURS 6, OURS 9).
    assert m.split_accept('text/html;q="0.5"') == [('text/html', (), '0.5')]
    assert m.split_accept('text/html;q="1"') == [('text/html', (), '1')]
    assert m.split_accept('text/html;q="2"') == [('text/html', (('q', '2'),), None)]
    assert m.split_accept('text/html;q="0.5";p=1') == [('text/html', (('p', '1'),), '0.5')]
    assert m.split_accept_language('en;q=0.5') == [('en', '0.5')]
    with pytest.raises(ValueError) as e6:
        m.split_accept_language('en;q="0.5"')
    assert str(e6.value) == PFX + 'split_accept_language:bad_value:text.weight.value.empty'


def test_rev1_loopcall_class_pins():
    # _fold maps every character, not just the first: a longer parameter
    # name that starts with Q is not the q parameter.
    assert m.split_accept('a/b;Qx=0.5') == [('a/b', (('Qx', '0.5'),), None)]
    assert m.split_accept('a/b;QQ=0.5') == [('a/b', (('QQ', '0.5'),), None)]
    # accept_format emits and validates every parameter, not just the first.
    assert m.accept_format([('a/b', (('p', '1'), ('r', '2')), '0.5')]) == 'a/b; p=1; r=2; q=0.5'
    with pytest.raises(ValueError) as f1:
        m.accept_format([('a/b', (('p', '1'), (1, 'x')), None)])
    assert str(f1.value) == PFX + 'accept_format:bad_type:name'
