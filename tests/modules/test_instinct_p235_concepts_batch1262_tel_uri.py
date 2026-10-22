"""Tests for p235 concepts batch 1262: RFC 3966 tel URI as a grammar over caller-supplied text, including the section 3 parameter uniqueness and ordering rules. Pure functions over caller data; claims asserted False."""
import ast
import builtins
import importlib.util
import inspect
import itertools
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

import app.modules.instinct_doc.p235_concepts_batch1262_tel_uri as m  # noqa: E402
MODPATH = m.__file__


def _prefix():
    spec = importlib.util.spec_from_file_location('b1262_pfx', MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        return str(e)[:-len('x:c')]


PFX = _prefix()
DOC_EXACT = 'p235 concepts batch 1262 (rev 0): RFC 3966, The tel URI for Telephone Numbers, as a grammar over caller-supplied text: the "tel:" scheme prefix, the telephone-subscriber (global-number and local-number with its mandatory phone-context), the parameter, extension and isdn-subaddress elements, the descriptor and domainname productions, and the section 3 parameter uniqueness and ordering rules. Pure functions; no retrieval, no network, no clock, no registries. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it dials nothing, validates no numbering plan, and defines no format.\n\nLIVE SOURCES (fetched 2026-10-22; quotes below are verbatim from these files, mechanically matched with whitespace collapsed):\n- RFC 3966 text, rfc-editor (40783 bytes, sha256 38d9aeec48d7f07120bd603f70b2da478218ffd3356eb362a651a31d0ff816bd).\n- RFC 2234 text, rfc-editor (24265 bytes, sha256 dcaf77997b83a9a0bda70bc00aa4670c084087e86b4aed57f5b705dfef6eb9ca), for the ABNF string-literal case rule that RFC 3966 imports ("The URI is defined using the ABNF (augmented Backus-Naur form) described in RFC 2234 [RFC2234] and uses elements from the core definitions (appendix A of RFC 2234).").\n- rfc-editor info page for RFC 3966 (260945 bytes, sha256 c7b28d8c136899bb0d8eaaedb83853bae9a5411454b0d1d25947327d595c77e3): it lists Obsoletes: RFC 2806 and Updated by: RFC 5341, and shows no Obsoleted by entry. CLAIMS current is still False.\n- The full rfc-editor errata index (11775016 bytes, sha256 23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c) contains exactly four RFC 3966 records (count from errata.json and not independently confirmed): EID 202, status Verified, type Editorial, section 5.1.5 (an example-context typo; no grammar content); EID 203, status Verified, type Editorial, section 3 (isdn-subaddress corrected from 1*uric to 1*paramchar; FOLLOWED here, see decision 2); EID 702, status Held for Document Update, type Editorial, section 12 (the fate of the fax and modem schemes; no grammar content); EID 4376, status Held for Document Update, type Editorial, section 3 (the bracketed optional visual-separator in phonedigit/phonedigit-hex; no language change, see decision 2).\n\nSOURCED grammar (RFC 3966 section 3): "telephone-subscriber = global-number / local-number" "global-number        = global-number-digits *par" "local-number         = local-number-digits *par context *par" "par                  = parameter / extension / isdn-subaddress" "descriptor           = domainname / global-number-digits" "global-number-digits = "+" *phonedigit DIGIT *phonedigit" "parameter            = ";" pname ["=" pvalue ]" "paramchar            = param-unreserved / unreserved / pct-encoded" "phonedigit           = DIGIT / [ visual-separator ]" "visual-separator     = "-" / "." / "(" / ")""\nSOURCED uniqueness, ordering and local context (sections 3 and 5.1.5): "Each parameter name ("pname"), the ISDN subaddress, the \'extension\', and the \'context\' MUST NOT appear more than once." "The \'isdn- subaddress\' or \'extension\' MUST appear first, if present, followed by the \'context\' parameter, if present, followed by any other parameters in lexicographical order." "Local numbers MUST have a \'phone-context\' parameter that identifies the scope of their validity."\nSOURCED comparison and case: "URI comparisons are case-insensitive." "All parameter names and values SHOULD use lower-case characters, as tel URIs may be used within contexts where comparisons are case sensitive."\nSOURCED separators and length: "Visual separators (\'visual-separator\') merely aid readability and are not used for URI comparison or placing a call." "However, even though ITU-T E.123 [E.123] recommends the use of space characters as visual separators in printed telephone numbers, "tel" URIs MUST NOT use spaces in visual separators to avoid excessive escaping." "Implementations MUST NOT assume that telephone numbers have a maximum, minimum, or fixed length, or that they always begin with or contain certain digits."\nSOURCED delimiters: "If the reserved characters "+", ";", "=", and "?" are used as delimiters between components of the "tel" URI, they MUST NOT be percent encoded. These characters MUST be percent encoded if they appear in tel URI parameter values."\nExamples exercised in the tests (section 6 and section 9): "tel:+1-201-555-0123: This URI points to a phone number in the United" "tel:7042;phone-context=example.com: The URI describes a local phone" "tel:863-1234;phone-context=+1-914-555: The URI describes a local" "tel:1234;phone-context=munich.example.com"\n\nDECISIONS AND NOT_CLAIMED:\n1. Case. RFC 3966 imports RFC 2234, whose literals are case-insensitive: "NOTE:     ABNF strings are case-insensitive and" Therefore the literal tokens "tel:", ";ext=", ";isub=" and ";phone-context=" match in any letter case, and HEXDIG (used in phonedigit-hex and pct-encoded) accepts a-f as well as A-F. This is grammar acceptance only; the canonical-comparison lowercase preference ("All parameter names and values SHOULD use lower-case characters, as tel URIs may be used within contexts where comparisons are case sensitive.") and the section 4 equivalence rules are NOT_CLAIMED.\n2. Errata. EID 203 (Verified Editorial) is FOLLOWED: an isub value is scanned as 1*paramchar, not 1*uric, so ";", "?", "@", "=" and "," are not accepted inside it. EID 4376 (Held) changes no accepted language: DIGIT / [ visual-separator ] and DIGIT / visual-separator match the same strings, so the phonedigit scan accepts DIGIT or one visual-separator character. EID 202 and EID 702 carry no grammar content.\n3. Ordering (OURS reading of the section 3 ordering sentence). The leading block holds the isub and ext elements, in either order when both are present (each at most once, per the uniqueness sentence); the phone-context follows; all other parameters follow in lexicographical pname order, compared on lowercase-folded names ("URI comparisons are case-insensitive."). A violation reports par.order; a repeated name of any kind reports par.dup. A generic parameter literally named "ext" without "=" is a parameter, not an extension, and collides with an extension under par.dup.\n4. Semantics. Number existence, reachability, E.164 assignment, dial plans, and the routing behaviors of sections 5 and 9 are NOT_CLAIMED. The section 4 URI-equivalence rules and any canonicalization are NOT_CLAIMED; the module reports grammar reasons only. tel_parts returns the raw digits text WITH visual separators and the raw par elements in order.\n5. Caps (OURS, all raising): _LEN_CAP 1024 characters per input. The grammar itself is unbounded ("Implementations MUST NOT assume that telephone numbers have a maximum, minimum, or fixed length, or that they always begin with or contain certain digits.").\n\nFUNCTIONS, in this order: tel_reason, subscriber_reason, global_number_reason, local_number_reason, global_digits_reason, local_digits_reason, par_reason, descriptor_reason, domainname_reason, tel_parts. The reason functions return the string "ok" or a reason string; tel_parts returns (kind, digits_text, pars) with kind "global" or "local" and pars a tuple of the raw "..." par elements in order. Errors are ValueError with the text P235:<function>:<code>, where <function> is the owning function and <code> is bad_type:value (non-str input), bad_value:value.length (over _LEN_CAP), or bad_value:value.tel (tel_parts on an invalid URI).\n\nREASONS, in check order (the first failure decides):\n- tel_reason: bad_type:value (raise), bad_value:value.length (raise); then scheme (not a case-insensitive "tel:" prefix), then subscriber.<subscriber_reason reason>; ok.\n- subscriber_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, plus (a "+" where a local number is required is only reported by local_number_reason; the plain subscriber picks the branch by the leading character), digits.<digits reason>, then per par left to right par.<par_reason reason>, par.dup, par.order, context.missing (local numbers only); ok.\n- global_number_reason / local_number_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, plus (missing for global, present for local), digits.<digits reason>, par.<par reason>, par.dup, par.order, context.missing (local only); ok.\n- global_digits_reason: bad_type:value (raise), bad_value:value.length (raise); then plus, char (outside DIGIT and visual-separator, left to right), digit.missing; ok.\n- local_digits_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, char (outside phonedigit-hex, left to right), hex.missing (no HEXDIG, "*" or "#"); ok.\n- par_reason: bad_type:value (raise), bad_value:value.length (raise); then semi, empty, then per kind: ext.empty, ext.char; isub.empty, isub.char, isub.pct; context.empty, context.<descriptor_reason reason>; pname.empty, pname.char, pvalue.empty, pvalue.char, pvalue.pct; ok.\n- descriptor_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, digits.<global digits reason> for a "+" start, domain.<domainname reason> otherwise; ok.\n- domainname_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, then per label left to right (one trailing "." allowed): label.empty, label.initial (non-alphanum initial on a non-final label), top.initial (non-ALPHA initial on the final label), label.final, label.char; ok.\n- tel_parts: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.tel (raise, when tel_reason would not return ok).\n\nOUTPUT ORDER: reason strings are the exact dotted codes listed above; tel_parts emits the digits text first, then the par elements in input order.'

QUOTES = ['The URI is defined using the ABNF (augmented Backus-Naur form) described in RFC 2234 [RFC2234] and uses elements from the core definitions (appendix A of RFC 2234).', 'If the reserved characters "+", ";", "=", and "?" are used as delimiters between components of the "tel" URI, they MUST NOT be percent encoded. These characters MUST be percent encoded if they appear in tel URI parameter values.', 'telephone-subscriber = global-number / local-number', 'global-number        = global-number-digits *par', 'local-number         = local-number-digits *par context *par', 'par                  = parameter / extension / isdn-subaddress', 'descriptor           = domainname / global-number-digits', 'global-number-digits = "+" *phonedigit DIGIT *phonedigit', 'parameter            = ";" pname ["=" pvalue ]', 'paramchar            = param-unreserved / unreserved / pct-encoded', 'phonedigit           = DIGIT / [ visual-separator ]', 'visual-separator     = "-" / "." / "(" / ")"', 'Each parameter name ("pname"), the ISDN subaddress, the \'extension\', and the \'context\' MUST NOT appear more than once.', "The 'isdn- subaddress' or 'extension' MUST appear first, if present, followed by the 'context' parameter, if present, followed by any other parameters in lexicographical order.", 'URI comparisons are case-insensitive.', 'All parameter names and values SHOULD use lower-case characters, as tel URIs may be used within contexts where comparisons are case sensitive.', "Visual separators ('visual-separator') merely aid readability and are not used for URI comparison or placing a call.", 'However, even though ITU-T E.123 [E.123] recommends the use of space characters as visual separators in printed telephone numbers, "tel" URIs MUST NOT use spaces in visual separators to avoid excessive escaping.', "Local numbers MUST have a 'phone-context' parameter that identifies the scope of their validity.", 'Implementations MUST NOT assume that telephone numbers have a maximum, minimum, or fixed length, or that they always begin with or contain certain digits.', 'tel:+1-201-555-0123: This URI points to a phone number in the United', 'tel:7042;phone-context=example.com: The URI describes a local phone', 'tel:863-1234;phone-context=+1-914-555: The URI describes a local', 'The URI is defined using the ABNF', 'NOTE:     ABNF strings are case-insensitive and', 'tel:1234;phone-context=munich.example.com']


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


def fresh(name='b1262_fresh'):
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


def _read(path):
    with open(path) as fh:
        return fh.read()


NAMES = ('tel_reason', 'subscriber_reason', 'global_number_reason', 'local_number_reason',
         'global_digits_reason', 'local_digits_reason', 'par_reason', 'descriptor_reason',
         'domainname_reason', 'tel_parts')
ARGSPEC = {fn: (('value', str),) for fn in NAMES}
PRIVATE = ('_LEN_CAP', '_DIGITS', '_ALO', '_AUP', '_ALPHA', '_ALNUM', '_HEXD', '_SEP', '_MARK',
           '_PARAM_UNRES', '_FOLD', '_fold', '_ci_eq', '_ci_prefix', '_scan_pct', '_digits_reason',
           '_global_digits_reason', '_local_digits_reason', '_domainname_reason', '_descriptor_reason',
           '_par_reason', '_par_name', '_split_pars', '_pars_reason', '_head_end', '_number_reason')

# ---- independent oracle: regexes written separately from the module's hand loops ----
_DIG = '0-9'
_HEXC = '0-9A-Fa-f'
_ALPHAC = 'A-Za-z'
_ALNUMC = 'A-Za-z0-9'
_SEPC = re.escape('-.()')
_MARKC = re.escape("-_.!~*'()")
_PUNC = re.escape('[]/:&+$')
_PCT = r'%[' + _HEXC + ']{2}'
_PARAMCHAR = r'(?:[' + _ALNUMC + _MARKC + _PUNC + ']|' + _PCT + ')'
_RE_GDIG = re.compile(r'^\+[' + _DIG + _SEPC + ']*$')
_RE_LDIG = re.compile(r'^[' + _HEXC + re.escape('*#') + _SEPC + ']*$')
_RE_LABEL = re.compile(r'^[' + _ALNUMC + '](?:[' + _ALNUMC + '-]*[' + _ALNUMC + '])?$')
_RE_TOPLABEL = re.compile(r'^[' + _ALPHAC + '](?:[' + _ALNUMC + '-]*[' + _ALNUMC + '])?$')
_RE_PNAME = re.compile(r'^[' + _ALNUMC + '-]+$')


def o_gdigits(v):
    if not v.startswith('+'):
        return 'plus'
    if not _RE_GDIG.match(v):
        return 'char'
    if not re.search('[' + _DIG + ']', v):
        return 'digit.missing'
    return 'ok'


def o_ldigits(v):
    if v == '':
        return 'empty'
    if not _RE_LDIG.match(v):
        return 'char'
    if not re.search('[' + _HEXC + re.escape('*#') + ']', v):
        return 'hex.missing'
    return 'ok'


def o_domainname(v):
    if v == '':
        return 'empty'
    if v.endswith('.'):
        v = v[:-1]
    labels = v.split('.')
    for i, lab in enumerate(labels[:-1]):
        if lab == '':
            return 'label.empty'
        if not _RE_LABEL.match(lab):
            if lab[0] not in (chr(c) for c in range(128) if chr(c).isalnum() and c < 128):
                pass
            if not re.match('^[' + _ALNUMC + ']', lab):
                return 'label.initial'
            if not re.search('[' + _ALNUMC + ']$', lab):
                return 'label.final'
            return 'label.char'
    last = labels[-1]
    if last == '':
        return 'label.empty'
    if not _RE_TOPLABEL.match(last):
        if not re.match('^[' + _ALPHAC + ']', last):
            return 'top.initial'
        if not re.search('[' + _ALNUMC + ']$', last):
            return 'label.final'
        return 'label.char'
    return 'ok'


def o_descriptor(v):
    if v == '':
        return 'empty'
    if v[0] == '+':
        r = o_gdigits(v)
        return 'ok' if r == 'ok' else 'digits.' + r
    r = o_domainname(v)
    return 'ok' if r == 'ok' else 'domain.' + r


def _o_scan(t, charcode, pctcode):
    i = 0
    n = len(t)
    while i < n:
        c = t[i]
        if c == '%':
            if i + 2 >= n or not re.match('[' + _HEXC + ']', t[i + 1]) or not re.match('[' + _HEXC + ']', t[i + 2]):
                return pctcode
            i += 3
        elif re.match('[' + _ALNUMC + _MARKC + _PUNC + ']', c):
            i += 1
        else:
            return charcode
    return 'ok'


def o_par(v):
    if not v.startswith(';'):
        return 'semi'
    rest = v[1:]
    if rest == '':
        return 'empty'
    low = rest.lower()
    if low.startswith('ext='):
        t = rest[4:]
        if t == '':
            return 'ext.empty'
        if not re.match('^[' + _DIG + _SEPC + ']*$', t):
            return 'ext.char'
        return 'ok'
    if low.startswith('isub='):
        t = rest[5:]
        if t == '':
            return 'isub.empty'
        return _o_scan(t, 'isub.char', 'isub.pct')
    if low.startswith('phone-context='):
        r = o_descriptor(rest[14:])
        return 'ok' if r == 'ok' else 'context.' + r
    eq = rest.find('=')
    name = rest if eq < 0 else rest[:eq]
    if name == '':
        return 'pname.empty'
    if not _RE_PNAME.match(name):
        return 'pname.char'
    if eq < 0:
        return 'ok'
    t = rest[eq + 1:]
    if t == '':
        return 'pvalue.empty'
    return _o_scan(t, 'pvalue.char', 'pvalue.pct')


def _name_of(p):
    low = p[1:].lower()
    for nm in ('ext=', 'isub=', 'phone-context='):
        if low.startswith(nm):
            return nm[:-1]
    eq = low.find('=')
    return low if eq < 0 else low[:eq]


def o_subscriber(v):
    if v == '':
        return 'empty'
    head, _, rest = v.partition(';')
    if v[0] == '+':
        r = o_gdigits(head)
    else:
        r = o_ldigits(head)
    if r != 'ok':
        return 'digits.' + r
    tail = v[len(head):]
    pars = [';' + p for p in tail[1:].split(';')] if tail else []
    for p in pars:
        r = o_par(p)
        if r != 'ok':
            return 'par.' + r
    names = [_name_of(p) for p in pars]
    if len(set(names)) != len(names):
        return 'par.dup'
    pos = 0
    while pos < len(names) and names[pos] in ('isub', 'ext'):
        pos += 1
    if pos < len(names) and names[pos] == 'phone-context':
        pos += 1
    prev = None
    for nm in names[pos:]:
        if nm in ('isub', 'ext', 'phone-context'):
            return 'par.order'
        if prev is not None and nm < prev:
            return 'par.order'
        prev = nm
    if v[0] != '+' and 'phone-context' not in names:
        return 'context.missing'
    return 'ok'


def o_tel(v):
    if len(v) < 4 or v[0:4].lower() != 'tel:':
        return 'scheme'
    r = o_subscriber(v[4:])
    return 'ok' if r == 'ok' else 'subscriber.' + r


# ---- RFC section 6 and 9 examples ----
def test_rfc_section6_and_9_examples_are_ok():
    assert m.tel_reason('tel:+1-201-555-0123') == 'ok'
    assert m.tel_reason('tel:7042;phone-context=example.com') == 'ok'
    assert m.tel_reason('tel:863-1234;phone-context=+1-914-555') == 'ok'
    assert m.tel_reason('tel:1234;phone-context=munich.example.com') == 'ok'
    assert m.tel_reason('tel:+1-212-555-0101') == 'ok'
    assert m.tel_reason('tel:+1-555-438-3732') == 'ok'
    assert m.tel_reason('tel:+1-900-555-0191') == 'ok'


def test_case_insensitive_literals_per_rfc2234():
    assert m.tel_reason('TEL:+1-201-555-0123') == 'ok'
    assert m.tel_reason('TeL:+1-201-555-0123') == 'ok'
    assert m.tel_reason('tel:+1;EXT=99') == 'ok'
    assert m.tel_reason('tel:+1;IsUb=a1') == 'ok'
    assert m.tel_reason('tel:7042;PHONE-CONTEXT=example.com') == 'ok'
    assert m.local_digits_reason('aBdF') == 'ok'
    assert m.local_digits_reason('AB12') == 'ok'
    assert m.par_reason(';foo=%aF') == 'ok'


def test_tel_parts_shape_and_examples():
    assert m.tel_parts('tel:+1-201-555-0123') == ('global', '+1-201-555-0123', ())
    assert m.tel_parts('tel:863-1234;phone-context=+1-914-555') == ('local', '863-1234', (';phone-context=+1-914-555',))
    assert m.tel_parts('tel:7042;ext=9;phone-context=example.com;b;foo=a') == ('local', '7042', (';ext=9', ';phone-context=example.com', ';b', ';foo=a'))
    assert run('tel_parts', 'tel:x') == E('tel_parts', 'bad_value:value.tel')
    assert run('tel_parts', 5) == E('tel_parts', 'bad_type:value')


def test_digits_grammars():
    assert m.global_digits_reason('+1-201-555-0123') == 'ok'
    assert m.global_digits_reason('+49-6151-16') == 'ok'
    assert m.global_digits_reason('+') == 'digit.missing'
    assert m.global_digits_reason('1') == 'plus'
    assert m.global_digits_reason('+-1') == 'ok'
    assert m.global_digits_reason('+1A') == 'char'
    assert m.global_digits_reason('+1*') == 'char'
    assert m.global_digits_reason('+1 2') == 'char'
    assert m.global_digits_reason('') == 'plus'
    assert m.local_digits_reason('863-1234') == 'ok'
    assert m.local_digits_reason('*70') == 'ok'
    assert m.local_digits_reason('#31#') == 'ok'
    assert m.local_digits_reason('aBdF') == 'ok'
    assert m.local_digits_reason('') == 'empty'
    assert m.local_digits_reason('-.()') == 'hex.missing'
    assert m.local_digits_reason('12g') == 'char'
    assert m.local_digits_reason('+1') == 'char'


def test_par_grammars():
    assert m.par_reason('x') == 'semi'
    assert m.par_reason(';') == 'empty'
    assert m.par_reason(';ext=123') == 'ok'
    assert m.par_reason(';ext=') == 'ext.empty'
    assert m.par_reason(';ext=12a') == 'ext.char'
    assert m.par_reason(';isub=abc') == 'ok'
    assert m.par_reason(';isub=') == 'isub.empty'
    assert m.par_reason(';isub=a;b') == 'isub.char'
    assert m.par_reason(';isub=a%20b') == 'ok'
    assert m.par_reason(';isub=a%2') == 'isub.pct'
    assert m.par_reason(';phone-context=example.com') == 'ok'
    assert m.par_reason(';phone-context=+1-914-555') == 'ok'
    assert m.par_reason(';phone-context=') == 'context.empty'
    assert m.par_reason(';phone-context=+') == 'context.digits.digit.missing'
    assert m.par_reason(';phone-context=1ex.com') == 'ok'
    assert m.par_reason(';phone-context=.com') == 'context.domain.label.empty'
    assert m.par_reason(';foo') == 'ok'
    assert m.par_reason(';foo=') == 'pvalue.empty'
    assert m.par_reason(';foo=bar') == 'ok'
    assert m.par_reason(';=') == 'pname.empty'
    assert m.par_reason(';f_o=1') == 'pname.char'
    assert m.par_reason(';foo=a;b') == 'pvalue.char'
    assert m.par_reason(';foo=%20') == 'ok'
    assert m.par_reason(';foo=%') == 'pvalue.pct'
    assert m.par_reason(';foo=a%2G') == 'pvalue.pct'
    assert m.par_reason('ext=1') == 'semi'
    assert m.par_reason(';') == 'empty'
    assert m.par_reason(';foo=a[]/:&+$') == 'ok'
    assert m.par_reason(';foo=a@b') == 'pvalue.char'
    assert m.par_reason(';foo=a=b') == 'pvalue.char'


def test_domainname_grammar():
    assert m.domainname_reason('example.com') == 'ok'
    assert m.domainname_reason('example.com.') == 'ok'
    assert m.domainname_reason('com') == 'ok'
    assert m.domainname_reason('houston.example.com') == 'ok'
    assert m.domainname_reason('') == 'empty'
    assert m.domainname_reason('.') == 'label.empty'
    assert m.domainname_reason('.com') == 'label.empty'
    assert m.domainname_reason('example..com') == 'label.empty'
    assert m.domainname_reason('ex-ample.com') == 'ok'
    assert m.domainname_reason('-example.com') == 'label.initial'
    assert m.domainname_reason('example-.com') == 'label.final'
    assert m.domainname_reason('ex_ample.com') == 'label.char'
    assert m.domainname_reason('example.c0m') == 'ok'
    assert m.domainname_reason('example.1com') == 'top.initial'
    assert m.domainname_reason('example.com-') == 'label.final'
    assert m.descriptor_reason('+1-914-555') == 'ok'
    assert m.descriptor_reason('+') == 'digits.digit.missing'
    assert m.descriptor_reason('+A') == 'digits.char'
    assert m.descriptor_reason('') == 'empty'


def test_subscriber_uniqueness_and_ordering():
    assert m.subscriber_reason('+1;ext=1;phone-context=x.com;foo=1') == 'ok'
    assert m.subscriber_reason('+1;isub=a;ext=1;phone-context=x.com') == 'ok'
    assert m.subscriber_reason('+1;ext=1;isub=a;phone-context=x.com') == 'ok'
    assert m.subscriber_reason('7042;phone-context=example.com') == 'ok'
    assert m.subscriber_reason('7042') == 'context.missing'
    assert m.subscriber_reason('') == 'empty'
    assert m.subscriber_reason('+1;foo=1;ext=2') == 'par.order'
    assert m.subscriber_reason('+1;foo=1;phone-context=x.com') == 'par.order'
    assert m.subscriber_reason('+1;b=1;a=2') == 'par.order'
    assert m.subscriber_reason('+1;a=1;b=2') == 'ok'
    assert m.subscriber_reason('+1;a=1;A=2') == 'par.dup'
    assert m.subscriber_reason('+1;ext=1;ext=2') == 'par.dup'
    assert m.subscriber_reason('+1;isub=a;isub=b') == 'par.dup'
    assert m.subscriber_reason('7042;phone-context=a.com;phone-context=b.com') == 'par.dup'
    assert m.subscriber_reason('+1;ext') == 'ok'
    assert m.subscriber_reason('+1;ext=1;ext') == 'par.dup'


def test_check_order_pins():
    assert m.tel_reason('sip:+1') == 'scheme'
    assert m.tel_reason('tel:+!;ext=') == 'subscriber.digits.char'
    assert m.tel_reason('tel:+1;ext=;ext=') == 'subscriber.par.ext.empty'
    assert m.tel_reason('tel:7042;ext=1;ext=1') == 'subscriber.par.dup'
    assert m.tel_reason('tel:7042;b=1;a=2;ext=1;ext=1') == 'subscriber.par.dup'
    assert m.tel_reason('tel:7042;zz=1;yy=2') == 'subscriber.par.order'
    assert m.tel_reason('tel:7042;zz=1') == 'subscriber.context.missing'
    assert m.global_number_reason('1') == 'plus'
    assert m.local_number_reason('+1;phone-context=x.com') == 'plus'
    assert m.domainname_reason('.-.com') == 'label.empty'
    assert m.domainname_reason('a!b.com') == 'label.char'
    assert m.domainname_reason('example.-om') == 'top.initial'
    over = 'tel:+1' + '2' * 2000
    assert run('tel_reason', over) == E('tel_reason', 'bad_value:value.length')
    assert run('par_reason', ';ext=' + '1' * 2000) == E('par_reason', 'bad_value:value.length')


def test_constants_exact():
    assert m._LEN_CAP == 1024 and type(m._LEN_CAP) is int
    assert m._DIGITS == '0123456789'
    assert m._SEP == '-.()'
    assert m._MARK == "-_.!~*'()"
    assert m._PARAM_UNRES == '[]/:&+$'
    assert m._HEXD == '0123456789ABCDEFabcdef'
    assert m.CLAIMS == {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False}
    assert type(m.CLAIMS) is dict and all(v is False for v in m.CLAIMS.values())
    assert m.SCOPE.startswith('RFC 3966 over caller-supplied text')
    assert 'dialing semantics' in m.NOT_CLAIMED
    assert 'RFC 2806' in m.ADJACENT[0]
    assert 'RFC 5341' in m.ADJACENT[1]


def test_constants_exact_contents():
    assert m.SCOPE == "RFC 3966 over caller-supplied text: the tel URI grammar - the telephone-subscriber (global-number and local-number with its mandatory phone-context), the parameter, extension and isdn-subaddress elements, the descriptor and domainname productions, and the section 3 uniqueness and ordering rules for parameters. Pure functions; no retrieval, no network, no clock, no registries."
    assert m.NOT_CLAIMED == ('standard', 'authority', 'certification', 'currency', 'completeness',
                             'dialing semantics', 'number existence or reachability', 'E.164 assignment validation', 'URI comparison canonicalization')
    assert m.ADJACENT == ('RFC 2806 (obsoleted by RFC 3966, per the info page)',
                          'RFC 5341 (updates RFC 3966 with a tel URI parameter registry, per the info page; the registry itself is NOT_CLAIMED)',
                          'RFC 2396 generic URI syntax and RFC 3261 SIP usage (named by the RFC 3966 text; neither grammar is re-derived here)')


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
    assert defs == ['tel_reason', 'subscriber_reason', 'global_number_reason', 'local_number_reason',
                    'global_digits_reason', 'local_digits_reason', 'par_reason', 'descriptor_reason',
                    'domainname_reason', 'tel_parts']


def test_header_quotes_are_in_the_header_and_distinct():
    assert len(QUOTES) == len(set(QUOTES)) and len(QUOTES) >= 20
    for qt in QUOTES:
        assert qt in DOC_EXACT


def test_header_names_erratum_sources_and_functions():
    assert m.__doc__ == DOC_EXACT
    for eid in ('202', '203', '702', '4376'):
        assert 'EID ' + eid in DOC_EXACT
    assert '38d9aeec48d7f07120bd603f70b2da478218ffd3356eb362a651a31d0ff816bd' in DOC_EXACT
    assert 'dcaf77997b83a9a0bda70bc00aa4670c084087e86b4aed57f5b705dfef6eb9ca' in DOC_EXACT
    assert 'c7b28d8c136899bb0d8eaaedb83853bae9a5411454b0d1d25947327d595c77e3' in DOC_EXACT
    assert '23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c' in DOC_EXACT
    assert 'Obsoletes: RFC 2806' in DOC_EXACT
    assert 'Updated by: RFC 5341' in DOC_EXACT
    assert 'not independently confirmed' in DOC_EXACT
    for fn in NAMES:
        assert fn in DOC_EXACT


def test_module_imports_and_source_bans():
    tree = ast.parse(_read(MODPATH))
    imps = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert len(imps) == 2
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in ('re', 'ord', 'chr', 'base64', 'binascii'):
            raise AssertionError('forbidden name referenced: %s' % node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('ord', 'chr', 'bin', 'hex'):
            raise AssertionError('forbidden call: %s' % node.func.id)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'v':
                raise AssertionError('str method on input: %s' % node.func.attr)
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While)) and isinstance(node.test, ast.Constant) and isinstance(node.test.value, bool):
            raise AssertionError('bool constant as branch condition')
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
    bad = [None, 1, True, False, 0, b'tel:+1', bytearray(b'tel:+1'), ['a'], ('a',), {'a'}, {'a': 1}, 3.5, _Hostile('tel:+1'), _mkhostile()('tel:+1')]
    for b in bad:
        assert run(fn, b) == E(fn, 'bad_type:value'), (fn, b)


def test_bool_is_refused_where_a_string_is_expected():
    for fn in NAMES:
        assert run(fn, True) == E(fn, 'bad_type:value')
        assert run(fn, False) == E(fn, 'bad_type:value')


def test_len_cap_at_cap_and_cap_plus_one_on_every_function():
    for fn in NAMES:
        assert run(fn, '1' * 1025) == E(fn, 'bad_value:value.length'), fn
    for fn in NAMES[:9]:
        assert run(fn, '1' * 1024)[0] == 'ok', fn
    assert run('tel_parts', '1' * 1024) == E('tel_parts', 'bad_value:value.tel')


def test_inputs_are_untouched_and_results_fresh():
    v = 'tel:+1-201-555-0123'
    assert m.tel_reason(v) == 'ok' and v == 'tel:+1-201-555-0123'
    a = m.tel_parts('tel:+1;foo=1')
    b = m.tel_parts('tel:+1;foo=1')
    assert a == b == ('global', '+1', (';foo=1',))
    assert type(a) is tuple and type(a[2]) is tuple


# ---- fuzz: mixed junk vs oracle, 1200 draws x 3 seeds ----
_JUNK_TEL = 'tel:+0129-.()ABCabcdef*#;%=&?/@[]:$!~\'_ x'
_JUNK_DOM = 'abcXYZ019-.!_'


def _fuzz(rng, alpha, n):
    return ''.join(rng.choice(alpha) for _ in range(rng.randrange(n)))


@pytest.mark.parametrize('seed', [1, 2, 3])
def test_fuzz_tel_subscriber_par_against_oracle_1200(seed):
    rng = random.Random('b1262:%d' % seed)
    for _ in range(1200):
        v = 'tel:' + _fuzz(rng, _JUNK_TEL, 30)
        assert m.tel_reason(v) == o_tel(v), v
        v = _fuzz(rng, _JUNK_TEL, 24)
        assert m.subscriber_reason(v) == o_subscriber(v), v
        v = ';' + _fuzz(rng, _JUNK_TEL, 14)
        assert m.par_reason(v) == o_par(v), v
        v = _fuzz(rng, _JUNK_DOM, 12)
        assert m.domainname_reason(v) == o_domainname(v), v
        v = '+' + _fuzz(rng, _JUNK_TEL, 12)
        assert m.global_digits_reason(v) == o_gdigits(v), v
        v = _fuzz(rng, _JUNK_TEL, 12)
        assert m.local_digits_reason(v) == o_ldigits(v), v


# ---- registry guard, import log, namespace ----------------------------------------------------------------------
def test_registry_absent_uses_local_fallback(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh()
    assert mod.make_fail.__module__ == mod.__name__
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert run('tel_reason', 1, mod=mod) == ('err', 'P235:tel_reason:bad_type:value')


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
CALLS = [(fn, ('tel:+1-201-555-0123',), (None,)) for fn in NAMES]


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
    CORPUS.append((_fn, (1,), 'bad_type:value'))
for _fn in NAMES:
    CORPUS.append((_fn, ('1' * 1025,), 'bad_value:value.length'))
CORPUS.append(('tel_parts', ('tel:x',), 'bad_value:value.tel'))
CORPUS.append(('tel_parts', ('tel:+1;b=1;a=2',), 'bad_value:value.tel'))
SUCCESS = [('tel_reason', ('tel:+1-201-555-0123',), 'ok'), ('tel_reason', ('TEL:+1',), 'ok'),
           ('tel_reason', ('tel:',), 'subscriber.empty'), ('tel_reason', ('telx',), 'scheme'),
           ('tel_reason', ('tel:+A',), 'subscriber.digits.char'),
           ('subscriber_reason', ('+1-201-555-0123',), 'ok'), ('subscriber_reason', ('',), 'empty'),
           ('subscriber_reason', ('+!A',), 'digits.char'), ('subscriber_reason', ('7042',), 'context.missing'),
           ('subscriber_reason', ('+1;ext=',), 'par.ext.empty'), ('subscriber_reason', ('+1;a=1;a=2',), 'par.dup'),
           ('subscriber_reason', ('+1;b=1;a=2',), 'par.order'),
           ('global_number_reason', ('+1',), 'ok'), ('global_number_reason', ('1',), 'plus'),
           ('global_number_reason', ('',), 'empty'), ('global_number_reason', ('+1;ext=',), 'par.ext.empty'),
           ('local_number_reason', ('7042;phone-context=x.com',), 'ok'),
           ('local_number_reason', ('+1;phone-context=x.com',), 'plus'),
           ('local_number_reason', ('7042',), 'context.missing'),
           ('local_number_reason', ('7042;phone-context=x.com;a=1;b=2',), 'ok'),
           ('global_digits_reason', ('+1-201',), 'ok'), ('global_digits_reason', ('1',), 'plus'),
           ('global_digits_reason', ('+-',), 'digit.missing'), ('global_digits_reason', ('+1a',), 'char'),
           ('global_digits_reason', ('+1*',), 'char'),
           ('local_digits_reason', ('863-1234',), 'ok'), ('local_digits_reason', ('*70#',), 'ok'),
           ('local_digits_reason', ('abCD',), 'ok'), ('local_digits_reason', ('',), 'empty'),
           ('local_digits_reason', ('-.()',), 'hex.missing'), ('local_digits_reason', ('1g',), 'char'),
           ('local_digits_reason', ('+1',), 'char'),
           ('par_reason', (';ext=1',), 'ok'), ('par_reason', ('ext=1',), 'semi'), ('par_reason', (';',), 'empty'),
           ('par_reason', (';ext=',), 'ext.empty'), ('par_reason', (';ext=1a',), 'ext.char'),
           ('par_reason', (';isub=a',), 'ok'), ('par_reason', (';isub=',), 'isub.empty'),
           ('par_reason', (';isub=a;b',), 'isub.char'), ('par_reason', (';isub=%2',), 'isub.pct'),
           ('par_reason', (';phone-context=x.com',), 'ok'), ('par_reason', (';phone-context=',), 'context.empty'),
           ('par_reason', (';phone-context=+',), 'context.digits.digit.missing'),
           ('par_reason', (';phone-context=..',), 'context.domain.label.empty'),
           ('par_reason', (';=',), 'pname.empty'), ('par_reason', (';f_o=1',), 'pname.char'),
           ('par_reason', (';f=',), 'pvalue.empty'), ('par_reason', (';f=a@b',), 'pvalue.char'),
           ('par_reason', (';f=a%',), 'pvalue.pct'), ('par_reason', (';f=a%20',), 'ok'),
           ('descriptor_reason', ('+1-914',), 'ok'), ('descriptor_reason', ('',), 'empty'),
           ('descriptor_reason', ('+',), 'digits.digit.missing'), ('descriptor_reason', ('+A',), 'digits.char'),
           ('descriptor_reason', ('x!y.com',), 'domain.label.char'),
           ('domainname_reason', ('example.com',), 'ok'), ('domainname_reason', ('example.com.',), 'ok'),
           ('domainname_reason', ('',), 'empty'), ('domainname_reason', ('.',), 'label.empty'),
           ('domainname_reason', ('a..b',), 'label.empty'), ('domainname_reason', ('a.b..',), 'label.empty'),
           ('domainname_reason', ('-a.com',), 'label.initial'), ('domainname_reason', ('a.1com',), 'top.initial'),
           ('domainname_reason', ('a-.com',), 'label.final'), ('domainname_reason', ('a_b.com',), 'label.char'),
           ('tel_parts', ('tel:+1',), ('global', '+1', ())),
           ('tel_parts', ('tel:7042;phone-context=x.com',), ('local', '7042', (';phone-context=x.com',)))]


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
        assert (fn, 'bad_type:value') in codes
        assert (fn, 'bad_value:value.length') in codes
    byfn = {}
    for f, a, w in SUCCESS:
        byfn.setdefault(f, set()).add(w if isinstance(w, str) else 'ok')
    assert byfn['tel_reason'] >= {'ok', 'scheme', 'subscriber.empty', 'subscriber.digits.char'}
    assert byfn['subscriber_reason'] >= {'ok', 'empty', 'digits.char', 'context.missing', 'par.ext.empty', 'par.dup', 'par.order'}
    assert byfn['global_number_reason'] >= {'ok', 'plus', 'empty', 'par.ext.empty'}
    assert byfn['local_number_reason'] >= {'ok', 'plus', 'context.missing'}
    assert byfn['global_digits_reason'] >= {'ok', 'plus', 'digit.missing', 'char'}
    assert byfn['local_digits_reason'] >= {'ok', 'empty', 'hex.missing', 'char'}
    assert byfn['par_reason'] >= {'ok', 'semi', 'empty', 'ext.empty', 'ext.char', 'isub.empty', 'isub.char', 'isub.pct',
                                  'context.empty', 'context.digits.digit.missing', 'context.domain.label.empty',
                                  'pname.empty', 'pname.char', 'pvalue.empty', 'pvalue.char', 'pvalue.pct'}
    assert byfn['descriptor_reason'] >= {'ok', 'empty', 'digits.digit.missing', 'digits.char', 'domain.label.char'}
    assert byfn['domainname_reason'] >= {'ok', 'empty', 'label.empty', 'label.initial', 'top.initial', 'label.final', 'label.char'}
    assert sum(1 for f, a, w in SUCCESS if f == 'tel_parts') == 2


def test_fallback_failer_world_has_no_imports_one_success_and_every_refusal(mp):
    real = builtins.__import__
    seen = []
    name = 'b1262_fallback_world'

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
    mod = fresh('b1262_site_world')
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
    mod = fresh('b1262_doc_world')
    assert mod.make_fail.__doc__ is None
    assert mod.make_fail('x').__doc__ is None
    assert mod.make_fail.__name__ == 'make_fail' and mod.make_fail('x').__name__ == 'fail'


def test_find_spec_is_consulted_exactly_once_in_the_absent_world_simulation(mp):
    spied = []
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda n: spied.append(n) or None)
    mod = fresh('b1262_spec_world')
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
            "import app.modules.instinct_doc.p235_concepts_batch1262_tel_uri as m\n"
            "print(m.tel_reason('tel:+1-201-555-0123'),"
            " m.tel_reason('TEL:+1'),"
            " m.tel_reason('tel:7042'),"
            " m.tel_reason('tel:+1;b=1;a=2'),"
            " m.par_reason(';isub=a;b'),"
            " m.domainname_reason('a.1com'),"
            " m.tel_parts('tel:7042;phone-context=x.com'))\n") % (
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(m.__file__)))),)
    want = ("ok ok subscriber.context.missing subscriber.par.order isub.char top.initial "
            "('local', '7042', (';phone-context=x.com',))")
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == want
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25, env={'PYTHONHASHSEED': '7'})
    assert out.stdout.strip() == want


# ---- Eq-to-Is pins: runtime-built non-interned strings at every multi-char equality site ----
def _rt(s):
    out = ''
    for ch in s:
        out = (out + ch)[0:len(out) + 1]
    # CPython caches latin-1 single characters; only longer strings can be witnessed non-identical.
    assert out == s and (len(s) == 1 or out is not s)
    return out


def test_ok_compares_use_value_equality_with_runtime_built_ok(mp):
    # tel_reason compares subscriber_reason's result against 'ok'; feed a runtime-built one.
    mp.setattr(m, 'subscriber_reason', lambda v: _rt('ok'))
    assert m.tel_reason('tel:anything') == 'ok'
    mp.setattr(m, 'subscriber_reason', lambda v: _rt('empty'))
    assert m.tel_reason('tel:anything') == 'subscriber.empty'
    # tel_parts compares tel_reason's result against 'ok' before raising.
    mp.setattr(m, 'tel_reason', lambda v: _rt('scheme'))
    assert run('tel_parts', 'tel:+1') == E('tel_parts', 'bad_value:value.tel')


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
        "import app.modules.instinct_doc.p235_concepts_batch1262_tel_uri as m\n"
        "semi = rt(';'); eq = rt('='); tel = rt('tel:'); ok = rt('ok')\n"
        "print(m.tel_reason(tel + '+1' + semi + 'ext' + eq + '9'),"
        " m.tel_reason(tel + '7042' + semi + 'phone-context' + eq + 'x.com'),"
        " m.par_reason(semi + 'foo' + eq + 'a' + rt('%') + '20'),"
        " m.par_reason(semi + 'foo' + eq + 'a' + rt('%') + '2'))\n")
    want = 'ok ok ok pvalue.pct'
    code = code.replace('%r', repr(envdir))
    out = subprocess.run([sys.executable, '-B', '-I', '-c', code], capture_output=True, text=True, timeout=25)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == want


def _rtok():
    return _rt('ok')


def test_internal_ok_propagation_compares_by_value_with_runtime_built_ok(mp):
    ok = lambda *a: _rtok()
    # _descriptor_reason: global branch, then domain branch
    mp.setattr(m, '_global_digits_reason', ok)
    assert m._descriptor_reason('+1') == 'ok'
    mp.setattr(m, '_domainname_reason', ok)
    assert m._descriptor_reason('x.com') == 'ok'
    # _par_reason phone-context branch
    mp.setattr(m, '_descriptor_reason', ok)
    assert m._par_reason(';phone-context=zzz') == 'ok'
    # _number_reason digits (global and local)
    mp.setattr(m, '_local_digits_reason', ok)
    assert m.global_number_reason('+1') == 'ok'
    assert m.local_number_reason('7042;phone-context=x.com') == 'ok'


def test_pars_loop_ok_compare_by_value_with_runtime_built_ok(mp):
    mp.setattr(m, '_par_reason', lambda p: _rtok())
    assert m.subscriber_reason('+1;ext=1') == 'ok'


def test_tel_parts_ok_compare_by_value_with_runtime_built_ok(mp):
    mp.setattr(m, 'tel_reason', lambda v: _rtok())
    assert m.tel_parts('tel:+1') == ('global', '+1', ())


def test_phone_context_name_compare_by_value_with_runtime_built_name(mp):
    mp.setattr(m, '_par_name', lambda p: _rt('phone-context') if p[1] == 'p' else _rt('zz'))
    assert m._pars_reason([';phone-context=x.com', ';zz=1'], True) == 'ok'


# ---- survivor-killing pins (sweep round 1) ----
def test_private_constants_exact():
    assert m._ALO == 'abcdefghijklmnopqrstuvwxyz'
    assert m._AUP == 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    assert m._ALPHA == m._ALO + m._AUP and m._ALNUM == m._ALPHA + '0123456789'
    assert len(m._FOLD) == 26 and m._FOLD['Z'] == 'z' and m._FOLD['A'] == 'a'
    assert m._fold('z') == 'z' and m._fold('Z') == 'z' and m._fold('-') == '-'


def test_ci_helpers_return_exact_bools():
    assert m._ci_eq('Zz', 'zZ') is True
    assert m._ci_eq('a', 'b') is False
    assert m._ci_eq('ab', 'aB') is True
    assert m._ci_eq('xb', 'ab') is False
    assert m._ci_prefix('EXT=1', 'ext=') is True
    assert m._ci_prefix('ab', 'x') is False
    assert m._ci_prefix('a', 'ab') is False


def test_scheme_each_position_and_fold_of_z_pname():
    for bad in ('xel:+1', 'tXl:+1', 'teX:+1', 'tel;+1', 'telX+1', 'xxxx+1', 'tel'):
        assert m.tel_reason(bad) == 'scheme', bad
    assert m.tel_reason('TeL:+1') == 'ok'
    assert m.subscriber_reason('+1;Z=1;z=2') == 'par.dup'
    assert m.subscriber_reason('+1;zZ=1;Zz=2') == 'par.dup'


def test_ext_digit_scan_checks_first_and_last_char():
    assert m.par_reason(';ext=a1') == 'ext.char'
    assert m.par_reason(';ext=1a') == 'ext.char'
    assert m.par_reason(';ext=1a1') == 'ext.char'
    assert m.par_reason('') == 'semi'


def test_pars_order_positions():
    assert m.subscriber_reason('+1;ext=1;a=1;phone-context=x.com') == 'par.order'
    assert m.subscriber_reason('+1;phone-context=x.com;zz=1;aa=2') == 'par.order'
    assert m.subscriber_reason('+1;phone-context=x.com;aa=2;zz=1') == 'ok'
    assert m.subscriber_reason('+1;ext=1;isub=a;phone-context=x.com;a=1;b=2') == 'ok'
    assert m.subscriber_reason('+1;a=1;isub=x') == 'par.order'
    assert m.subscriber_reason('+1;a=1;ext=1') == 'par.order'
    assert m.subscriber_reason('+1;a=1;phone-context=x.com') == 'par.order'
    assert m.subscriber_reason('+1;ext=1;a=1;b=1') == 'ok'


def test_scan_pct_boundaries_and_skips():
    assert m.par_reason(';isub=%4') == 'isub.pct'
    assert m.par_reason(';isub=%') == 'isub.pct'
    assert m.par_reason(';isub=%41') == 'ok'
    assert m.par_reason(';isub=%41@') == 'isub.char'
    assert m.par_reason(';isub=%41%4') == 'isub.pct'
    assert m.par_reason(';isub=@%') == 'isub.char'
    assert m.par_reason(';isub=%!!') == 'isub.pct'
    assert m.par_reason(';isub=a%4g') == 'isub.pct'
    assert m.par_reason(';isub=a%g4') == 'isub.pct'


def test_local_hex_letters_exact():
    assert m.local_digits_reason('X') == 'char'
    assert m.local_digits_reason('G') == 'char'
    assert m.local_digits_reason('fF') == 'ok'


def test_domain_first_last_and_middle_char_checks():
    assert m.domainname_reason('a-b.com') == 'ok'
    assert m.domainname_reason('a-.com') == 'label.final'
    assert m.domainname_reason('-a.com') == 'label.initial'
    assert m.domainname_reason('a_b.com') == 'label.char'
    assert m.domainname_reason('ab_.com') == 'label.final'
    assert m.domainname_reason('a--b.com') == 'ok'


def test_pct_second_digit_index_and_prefix_boundary():
    assert m.par_reason(';isub=ab%4g') == 'isub.pct'
    assert m.par_reason(';isub=ab%41') == 'ok'
    assert m.tel_reason('tel:') == 'subscriber.empty'
    assert m.tel_reason('tel') == 'scheme'
    assert m.tel_reason('TEL:') == 'subscriber.empty'


def test_auditor_atlas5_rev1_kill_pins():
    # Atlas 5 rev0 audit gaps a-h: each pin re-executed against its mutant (rc 1) on both interps.
    # a. L131 global_digits_reason: plus check is !=, not > ('*' sorts below '+').
    assert m.global_digits_reason('*' + '1') == 'plus'
    # b. L181 descriptor_reason: plus check is ==, not <= (a char below '+' is not a global descriptor).
    assert m.descriptor_reason('*') == 'domain.top.initial'
    # c. L187 descriptor_reason: domain check is !=, not < ('domain.top.initial' sorts below 'ok').
    assert m.descriptor_reason('a' + '.1om') == 'domain.top.initial'
    # d. L312 global_number_reason: plus check is !=, not >.
    assert m.global_number_reason('*' + '1') == 'plus'
    # e. L285 tel_reason: phone-context name check is ==, not in ('phone' is a substring of 'phone-context').
    assert m.tel_reason('tel:+1;' + 'phone' + '=1;p=2') == 'subscriber.par.order'
    # f. L156 domainname_reason: dot == end is ==, not is (positions past the 256-entry small-int cache).
    assert m.domainname_reason('b' * 300 + '.1om') == 'top.initial'
    # g. L173 domainname_reason: start == end is ==, not is (empty label past the cache).
    assert m.domainname_reason('x.' + 'a' * 300 + '..') == 'label.empty'
    # h. L231 par_reason: i == m is ==, not is (parameter scan past the cache).
    assert m.par_reason(';' + 'p' * 300) == 'ok'


def test_long_inputs_above_the_small_int_cache():
    # 7:53 hygiene: every while/for bound and length compare driven past the 256-entry
    # small-int cache, plus the 1024 at-cap and 2048 over-cap edges.
    assert m.global_number_reason('+' + '1' * 300) == 'ok'
    assert m.global_digits_reason('+' + '1' * 300) == 'ok'
    assert m.local_digits_reason('1' * 300) == 'ok'
    assert m.par_reason(';' + 'isub=' + 'a' * 300) == 'ok'
    assert m.par_reason(';' + 'p' * 300 + '=' + 'v' * 300) == 'ok'
    assert m.domainname_reason('a' * 300) == 'ok'
    pars = ''.join(';' + chr(97 + i // 10) + str(i % 10) for i in range(260))
    assert m.tel_reason('tel:+1' + pars) == 'ok'
    assert m.tel_reason('tel:+1;phone-context=1om.' + 'a' * 300 + ';p=2') == 'ok'
    assert m.tel_reason('tel:+' + '1' * (1024 - 5)) == 'ok'
    try:
        m.tel_reason('tel:+1' + '1' * 2048)
        assert False, 'over-cap accepted'
    except ValueError as e:
        assert str(e) == PFX + 'tel_reason:bad_value:value.length'


def test_rev1_second_round_kill_pins():
    # Found by my own clean cross-product re-run (pycache-free, per-mutant fresh copies):
    # i. L157 domainname_reason: dot == start is ==, not is (empty label past the 256-int cache).
    assert m.domainname_reason('a' * 300 + '..' + 'x') == 'label.empty'
    # j. L195 par_reason: semicolon check is !=, not > ('+' sorts below ';').
    assert m.par_reason('+') == 'semi'
    # k. L205 par_reason: separator membership is not-in, the != mutant is always-true ('-' is in _SEP).
    assert m.par_reason(';ext=1-2') == 'ok'
    # l. L423 tel_parts: global/local branch is ==, not <= ('(' sorts below '+' and starts a local number).
    assert m.tel_parts('tel:(1);phone-context=example.com')[0] == 'local'


def test_rev1_third_round_ext_separator_pin():
    # L205 par_reason: _SEP membership mutants '>' and '>=' pass chars sorting below '-'
    # ('+' is 0x2B, below '-' at 0x2D) that the not-in original rejects.
    assert m.par_reason(';ext=+') == 'ext.char'


# ---- rev 1d: direct pins on the decoder's loop-advance sites (_scan_pct) ----

_OFFSETS = (0, 1, 2, 3, 4, 5, 8, 100, 255, 256, 257, 300, 700)


@pytest.mark.parametrize('off', _OFFSETS)
def test_scan_pct_advances_exactly_three_after_an_escape_at_any_offset(off):
    # a mutant that reassigns the index instead of advancing it loops forever; the 60 s hang guard turns a hang into a failure
    lead = _rt('a' * off) if off > 1 else 'a' * off
    esc = _rt('%4E')
    s = lead + esc
    n = len(s)
    assert m._scan_pct(s, 0, n, 'C', 'P') == 'ok'
    assert m._scan_pct(s + _rt('"'), 0, n + 1, 'C', 'P') == 'C'
    assert m._scan_pct(s + _rt('"'), 0, n, 'C', 'P') == 'ok'
    assert m._scan_pct(s + _rt('%4'), 0, n + 2, 'C', 'P') == 'P'
    assert m._scan_pct(s + _rt('%G0'), 0, n + 3, 'C', 'P') == 'P'
    assert m._scan_pct(s + _rt('%4E') + _rt('x'), 0, n + 4, 'C', 'P') == 'ok'
    assert m._scan_pct(s + _rt('%4E"'), 0, n + 4, 'C', 'P') == 'C'
    assert m._scan_pct(esc + lead + esc, 0, 6 + off, 'C', 'P') == 'ok'
    assert m._scan_pct(lead + esc + lead, off, n + off, 'C', 'P') == 'ok'
    assert m._scan_pct(lead + _rt('"') + esc, off, n + 1, 'C', 'P') == 'C'
    assert m._scan_pct(lead + _rt('%') + esc, 0, n + 1, 'C', 'P') == 'P'


def test_scan_pct_single_character_advance_and_end_bound():
    for off in _OFFSETS:
        s = (_rt('a' * off) if off > 1 else 'a' * off) + '-'
        assert m._scan_pct(s, 0, len(s), 'C', 'P') == 'ok'
        assert m._scan_pct(s + _rt('"'), 0, len(s) + 1, 'C', 'P') == 'C'
        assert m._scan_pct(s + _rt('"'), 0, len(s), 'C', 'P') == 'ok'
        assert m._scan_pct(s, off, len(s), 'C', 'P') == 'ok'
        assert m._scan_pct(s, len(s), len(s), 'C', 'P') == 'ok'
        assert m._scan_pct(_rt('"') + s, 1, len(s) + 1, 'C', 'P') == 'ok'
    assert m._scan_pct('%4E', 0, 3, 'C', 'P') == 'ok' and m._scan_pct('%4E', 0, 2, 'C', 'P') == 'P'
    assert m._scan_pct('%4', 0, 2, 'C', 'P') == 'P' and m._scan_pct('%', 0, 1, 'C', 'P') == 'P'
    assert m._scan_pct('x%4E', 1, 4, 'C', 'P') == 'ok' and m._scan_pct('x%4E', 2, 4, 'C', 'P') == 'ok' and m._scan_pct('x"%4E', 1, 5, 'C', 'P') == 'C'


def test_decoder_witness_from_the_auditor_terminates_and_gives_the_same_reason():
    w = ';-fphone-context=example.com' + _rt('%4E') + 'xt='
    assert m.par_reason(w) == 'pvalue.char' and m.par_reason(_rt(w)) == 'pvalue.char'
    for pre in (0, 1, 2, 3, 4, 10, 255, 256, 300):
        b = _rt('b' * pre) if pre > 1 else 'b' * pre
        v = ';k=' + b + _rt('%4E') + _rt('xt')
        assert m.par_reason(v) == 'ok', pre
        assert m.par_reason(v + _rt('=')) == 'pvalue.char', pre
        assert m.par_reason(';k=' + b + _rt('%4')) == 'pvalue.pct', pre


def _scan_pct_step(v, i, n, step):
    while i < n:
        c = v[i]
        if c == '%':
            if i + 2 >= n or v[i + 1] not in m._HEXD or v[i + 2] not in m._HEXD:
                return 'P'
            i += step
        elif c in m._ALNUM or c in m._MARK or c in m._PARAM_UNRES:
            i += 1
        else:
            return 'C'
    return 'ok'


def test_scan_pct_escape_advance_of_one_or_two_is_equivalent_and_three_is_the_original():
    # Equivalence: after a valid escape both skipped characters are hex digits, and every hex digit is in _ALNUM,
    # so re-scanning them with the 1-step branch reaches the same index with the same result as skipping three.
    # Executed differential below; steps 1 and 2 are the only equivalent values (0, 4, reassignment are killed above).
    assert all(c in m._ALNUM for c in m._HEXD)
    alpha = '%4EG-"a'
    count = 0
    for k in range(0, 7):
        for t in itertools.product(alpha, repeat=k):
            s = ''.join(t)
            for n in range(len(s) + 1):
                r = _scan_pct_step(s, 0, n, 3)
                assert r == m._scan_pct(s, 0, n, 'C', 'P')
                assert r == _scan_pct_step(s, 0, n, 2) == _scan_pct_step(s, 0, n, 1)
                count += 1
    assert count > 100000
