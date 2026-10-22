"""Tests for p235 concepts batch 1259: RFC 9557 IXDTF grammar over caller-supplied text (the imported RFC 3339 date-time core plus the section 4.1 suffix grammar and the section 3 key/case rules) plus a structured suffix extractor. Pure functions over caller data; claims asserted False."""
import ast
import builtins
import calendar
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
MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1259_ixdtf'
NAMES = ('date_reason', 'time_reason', 'offset_reason', 'datetime_reason', 'tzname_reason',
         'tzsuffix_reason', 'suffixtag_reason', 'suffix_reason', 'ixdtf_reason', 'ixdtf_tags')
PRIVATE = ('_LEN_CAP', '_TAGS_CAP', '_VALUES_CAP', '_PARTS_CAP', '_FRAC_CAP',
           '_DIGITS', '_UCALPHA', '_LCALPHA', '_ALPHA', '_ALNUM', '_TZ_INITIAL', '_TZ_CHAR',
           '_KEY_INITIAL', '_KEY_CHAR', '_MDAYS', '_is_leap', '_digits', '_tzpart_reason',
           '_numoffset_shape', '_find_close', '_scan_suffix', '_split_ixdtf')
DOC_EXACT = 'p235 concepts batch 1259 (rev 0): RFC 9557, Date and Time on the Internet: Timestamps with Additional Information - the Internet Extended Date/Time Format (IXDTF) as a grammar over caller-supplied text: the RFC 3339 date-time core it imports (re-derived here from the live RFC 3339 sections 5.6 and 5.7), the section 4.1 suffix grammar (time-zone tag, suffix tags, critical flag), and the section 3 key and case rules. Pure functions; no retrieval, no network, no clock, no calendar arithmetic, no registry lookups. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it carries no timestamp semantics, consults no tz database, no leap-second table and no calendar registry, and defines no format.\n\nLIVE SOURCES (fetched 2026-10-22; quotes below are verbatim from these files, mechanically matched with whitespace collapsed):\n- RFC 9557 text, rfc-editor (39113 bytes, sha256 87fa632cd75d13aa441859da635ed6618f66d203fe71a30fa85afedbeb149e85).\n- RFC 3339 text, rfc-editor (35064 bytes, sha256 9ab2b8864a85dca73a88f49b0927bc7bc85f596926e4fd1890905777924e700a), for the imported date-time core and the section 5.7 restriction texts.\n- rfc-editor info page for RFC 9557 (468497 bytes, sha256 c585df7162898aa21dde9a7856da61aef1e25c7ff153f6f42b8293d7d9558fe9): it lists Updates: RFC 3339, and shows no Obsoletes entry, no Obsoleted by entry and no Updated by entry. CLAIMS current is still False.\n- The full rfc-editor errata index (11775016 bytes, sha256 23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c) contains exactly one RFC 9557 record (count from errata.json and not independently confirmed): EID 8192, status Rejected, type Editorial, section 3.4 (a rejected hyphenation note about "critical flag"; no technical content).\n\nSOURCED grammar (RFC 9557 section 4.1): "date-time-ext     = date-time suffix" "suffix            = [time-zone] *suffix-tag"\n"time-zone         = "[" critical-flag time-zone-name / time-numoffset "]"" "suffix-tag        = "[" critical-flag suffix-key "=" suffix-values "]"" "critical-flag     = [ "!" ]"\n"time-zone-name    = time-zone-part *("/" time-zone-part)" "time-zone-part    = time-zone-initial *time-zone-char ; but not "." or ".."" "time-zone-initial = ALPHA / "." / "_"" "time-zone-char    = time-zone-initial / DIGIT / "-" / "+"" "key-initial       = lcalpha / "_"" "suffix-key        = key-initial *key-char" "suffix-value      = 1*alphanum" "suffix-values     = suffix-value *("-" suffix-value)" "lcalpha           = %x61-7A" "alphanum          = ALPHA / DIGIT"\n\nSOURCED core (RFC 3339 section 5.6, imported by RFC 9557): "date-fullyear   = 4DIGIT" "date-month      = 2DIGIT  ; 01-12" "date-mday       = 2DIGIT  ; 01-28, 01-29, 01-30, 01-31 based on ; month/year" "time-hour       = 2DIGIT  ; 00-23" "time-minute     = 2DIGIT  ; 00-59" "time-second     = 2DIGIT  ; 00-58, 00-59, 00-60 based on leap second ; rules" "time-secfrac    = "." 1*DIGIT" "time-numoffset  = ("+" / "-") time-hour ":" time-minute" "time-offset     = "Z" / time-numoffset" "partial-time    = time-hour ":" time-minute ":" time-second [time-secfrac]" "full-date       = date-fullyear "-" date-month "-" date-mday" "full-time       = partial-time time-offset" "date-time       = full-date "T" full-time"\n\nDECISIONS AND NOT_CLAIMED:\n1. Case. "Per [ABNF] and ISO8601, the "T" and "Z" characters in this syntax may alternatively be lower case "t" or "z" respectively." Both "T"/"t" and "Z"/"z" are accepted. Keys are lowercase by grammar: "Keys are lowercase only.  Values are case-sensitive unless otherwise specified." Values are compared as grammar characters only; no case folding anywhere.\n2. Separator. Only "T"/"t" is accepted between date and time. The space alternative is an application-level choice - "Applications using this syntax may choose, for the sake of readability, to specify a full-date and full-time separated by (say) a space character." - and is NOT_CLAIMED here: a space separator reports sep.t.\n3. Leap seconds. time-second accepts 00-60 grammatically; whether a given instant actually had a leap second ("The grammar element time-second may have the value "60" at the end of months in which a leap second occurs") is a table lookup and is NOT_CLAIMED. Hour 24 is rejected: "this profile of ISO 8601 only allows values between "00" and "23" for the hour in order to reduce confusion."\n4. Leap years. date-mday maxima follow section 5.7 ("02            February, leap year  29" and the rest of the table): February has 29 days in years divisible by 4 but not by 100 unless also divisible by 400.\n5. Time zone names. tzname checks the grammar only ("time-zone-part    = time-zone-initial *time-zone-char ; but not "." or "..""), including the exclusion in "The ABNF definition of time-zone-part matches "." and "..", which are both explicitly excluded (see the note below on time-zone-part)." The 14-character platform limit is deliberately not enforced: "over the length, the time-zone-part production in Figure 3 is | deliberately permissive." Whether the name exists in any tz database is NOT_CLAIMED.\n6. Suffix handling. Tags are elective by default and critical when flagged: "The recipient is free to ignore any suffix tag included in an IXDTF string." "A critical suffix tag is indicated by following its opening bracket with an exclamation mark (see critical-flag in Section 4.1)." Rejection of critical tags, inconsistency handling between time-offset and time zone (section 3.4), and the duplicate-key first-wins rule ("does not want to perform additional processing on this inconsistency MUST choose the first suffix that has that key") are recipient behaviors and are NOT_CLAIMED: ixdtf_tags returns the tags in order, flagged, and applies no dedup. Experimental underscore keys ("such keys MUST NOT be used for interchange and MUST be rejected by implementations not specifically configured to take part in such an experiment.") are accepted as grammar; rejecting them is NOT_CLAIMED.\n7. Z semantics. The section 2.2 update ("If the time in UTC is known, but the offset to local time is | unknown, this can be represented with an offset of "Z".") and the -00:00 deprecation note are semantics; both Z and -00:00 are accepted syntactically, and their semantic difference is NOT_CLAIMED.\n8. Offsets inside a time-zone bracket are checked with the same ranges as a time-offset (hour 00-23, minute 00-59); RFC 9557 imports time-numoffset for both positions.\n9. Caps (OURS, all raising): _LEN_CAP 1024 characters per input; _TAGS_CAP 128 suffix tags (a tag is at least five characters, so 129 tags fit under _LEN_CAP); _VALUES_CAP 64 hyphen-separated items per suffix-values; _PARTS_CAP 64 slash-separated parts per time-zone-name; _FRAC_CAP 64 digits per time-secfrac. The grammar itself is unbounded in these five places.\n\nFUNCTIONS, in this order: date_reason, time_reason, offset_reason, datetime_reason, tzname_reason, tzsuffix_reason, suffixtag_reason, suffix_reason, ixdtf_reason, ixdtf_tags. The reason functions return the string "ok" or a reason string; ixdtf_tags returns (head, tz, tags) where head is the date-time portion, tz is None or (critical, body), and tags is a tuple of (critical, key, values) with values a tuple of the hyphen-separated items, in order. Errors are ValueError with the text P235:<function>:<code>, where <function> is the owning function and <code> is bad_type:value (non-str input), bad_value:value.length (over _LEN_CAP), bad_value:frac.length, bad_value:parts.length, bad_value:values.length, bad_value:tags.length, or bad_value:value.ixdtf (ixdtf_tags on an invalid string).\n\nREASONS, in check order (the first failure decides):\n- date_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (not exactly 10 characters or hyphens misplaced), year (non-digit), month (non-digit), month.range (not 01-12), mday (non-digit), mday.range (outside the month/year maximum); ok.\n- time_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (fewer than 8 characters or colons misplaced), hour (non-digit), hour.range (over 23), minute (non-digit), minute.range (over 59), second (non-digit), second.range (over 60), frac.dot (extra text not starting with "."), frac.empty, bad_value:frac.length (raise), frac.char (non-digit); ok.\n- offset_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (empty, or "Z"/"z" with trailing text, or not exactly 6 characters, or colon misplaced), sign (not "+" or "-"), hour (non-digit), hour.range (over 23), minute (non-digit), minute.range (over 59); ok. A lone "Z" or "z" is ok.\n- datetime_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (fewer than 20 characters), date.<date_reason reason>, sep.t, time.<time_reason reason>, offset.<offset_reason reason>; ok. A nested cap raise propagates under the owning function\'s name. The time portion runs to the first "Z", "z", "+" or "-" after the separator; a missing offset reports shape when the string is under 20 characters, else offset.shape.\n- tzname_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, bad_value:parts.length (raise), then per part left to right: part.empty, part.dot (exactly "." or ".."), part.initial, part.char; ok.\n- tzsuffix_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (fewer than 3 characters), open, close, empty (only a critical flag inside), then for a body starting "+" or "-": offset.<shape, sign, hour, hour.range, minute, minute.range>, else name.<tzname_reason reason>; ok. A nested cap raise propagates under the owning function\'s name.\n- suffixtag_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (fewer than 5 characters), open, close, eq.missing, key.empty, key.initial, key.char, value.empty, bad_value:values.length (raise), value.empty (empty item between hyphens), value.char; ok.\n- suffix_reason: bad_type:value (raise), bad_value:value.length (raise); ok on the empty string; then tz.close or tz.<tzsuffix_reason reason> for the optional leading time-zone, then per tag left to right: bad_value:tags.length (raise), suffix.char (text outside brackets), tag.close, tag.<suffixtag_reason reason>; ok.\n- ixdtf_reason: bad_type:value (raise), bad_value:value.length (raise); then datetime.<datetime_reason reason> for the portion before the first "[", then the suffix_reason reasons for the rest; ok. A bare RFC 3339 date-time is valid IXDTF ("date-time-ext     = date-time suffix" with "suffix            = [time-zone] *suffix-tag" both optional).\n- ixdtf_tags: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.ixdtf (raise, when ixdtf_reason would not return ok, including any cap raise propagating first under its owning name).\n\nOUTPUT ORDER: reason strings are the exact dotted codes listed above; ixdtf_tags emits the time-zone first, then the suffix tags in input order, each critical flag preceding its key.'
QUOTES = ['date-time-ext     = date-time suffix', 'suffix            = [time-zone] *suffix-tag', 'time-zone         = "[" critical-flag time-zone-name / time-numoffset "]"', 'suffix-tag        = "[" critical-flag suffix-key "=" suffix-values "]"', 'critical-flag     = [ "!" ]', 'time-zone-part    = time-zone-initial *time-zone-char ; but not "." or ".."', 'The ABNF definition of time-zone-part matches "." and "..", which are both explicitly excluded (see the note below on time-zone-part).', 'over the length, the time-zone-part production in Figure 3 is | deliberately permissive.', 'Keys are lowercase only.  Values are case-sensitive unless otherwise specified.', 'A critical suffix tag is indicated by following its opening bracket with an exclamation mark (see critical-flag in Section 4.1).', 'The recipient is free to ignore any suffix tag included in an IXDTF string.', 'does not want to perform additional processing on this inconsistency MUST choose the first suffix that has that key', 'such keys MUST NOT be used for interchange and MUST be rejected by implementations not specifically configured to take part in such an experiment.', 'If the time in UTC is known, but the offset to local time is | unknown, this can be represented with an offset of "Z".', 'date-fullyear   = 4DIGIT', 'date-month      = 2DIGIT  ; 01-12', 'date-mday       = 2DIGIT  ; 01-28, 01-29, 01-30, 01-31 based on ; month/year', 'time-hour       = 2DIGIT  ; 00-23', 'time-minute     = 2DIGIT  ; 00-59', 'time-second     = 2DIGIT  ; 00-58, 00-59, 00-60 based on leap second ; rules', 'time-secfrac    = "." 1*DIGIT', 'time-numoffset  = ("+" / "-") time-hour ":" time-minute', 'time-offset     = "Z" / time-numoffset', 'partial-time    = time-hour ":" time-minute ":" time-second [time-secfrac]', 'full-date       = date-fullyear "-" date-month "-" date-mday', 'full-time       = partial-time time-offset', 'date-time       = full-date "T" full-time', 'Per [ABNF] and ISO8601, the "T" and "Z" characters in this syntax may alternatively be lower case "t" or "z" respectively.', 'Applications using this syntax may choose, for the sake of readability, to specify a full-date and full-time separated by (say) a space character.', 'The grammar element time-second may have the value "60" at the end of months in which a leap second occurs', 'this profile of ISO 8601 only allows values between "00" and "23" for the hour in order to reduce confusion.', '02            February, leap year  29', 'time-zone-name    = time-zone-part *("/" time-zone-part)', 'key-initial       = lcalpha / "_"', 'suffix-key        = key-initial *key-char', 'suffix-value      = 1*alphanum', 'suffix-values     = suffix-value *("-" suffix-value)', 'time-zone-char    = time-zone-initial / DIGIT / "-" / "+"', 'time-zone-initial = ALPHA / "." / "_"', 'lcalpha           = %x61-7A', 'alphanum          = ALPHA / DIGIT']
HERE = os.path.dirname(os.path.abspath(__file__))
import app.modules.instinct_doc.p235_concepts_batch1259_ixdtf as m  # noqa: E402
MODPATH = m.__file__


def _prefix():
    spec = importlib.util.spec_from_file_location('b1259_pfx', MODPATH)
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
        raise _Alarm('ALARM test exceeded 60 seconds (hang guard only)')
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 60.0)
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, old)


@pytest.fixture
def mp(monkeypatch):
    return monkeypatch


def fresh(name='b1259_fresh'):
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


# ---- independent oracle (regexes and calendar.isleap, written separately from the module's hand loops) ----
_RX_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}\Z')
_RX_TIME = re.compile(r'[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?\Z')
_RX_OFFSET = re.compile(r'([Zz]|[+-][0-9]{2}:[0-9]{2})\Z')
_RX_TZPART = re.compile(r'[A-Za-z._][A-Za-z0-9._+-]*\Z')
_RX_KEY = re.compile(r'[a-z_][a-z0-9_-]*\Z')
_RX_VALUES = re.compile(r'[A-Za-z0-9]+(-[A-Za-z0-9]+)*\Z')
_MD = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def o_date(v):
    if type(v) is not str or not _RX_DATE.match(v):
        return False
    y, mo, d = int(v[0:4]), int(v[5:7]), int(v[8:10])
    if not 1 <= mo <= 12:
        return False
    top = 29 if mo == 2 and calendar.isleap(y) else _MD[mo - 1]
    return 1 <= d <= top


def o_time(v):
    if type(v) is not str or not _RX_TIME.match(v):
        return False
    return int(v[0:2]) <= 23 and int(v[3:5]) <= 59 and int(v[6:8]) <= 60


def o_offset(v):
    if type(v) is not str or not _RX_OFFSET.match(v):
        return False
    return len(v) == 1 or (int(v[1:3]) <= 23 and int(v[4:6]) <= 59)


def o_datetime(v):
    if type(v) is not str or len(v) < 20:
        return False
    if not o_date(v[:10]) or v[10] not in 'Tt':
        return False
    i, j = 11, 11
    while j < len(v) and v[j] not in 'Zz+-':
        j += 1
    return o_time(v[i:j]) and o_offset(v[j:])


def o_tzname(v):
    if type(v) is not str or len(v) < 1:
        return False
    for p in v.split('/'):
        if len(p) < 1 or p in ('.', '..') or not _RX_TZPART.match(p):
            return False
    return True


def o_numoffset(s):
    return bool(_RX_OFFSET.match(s)) and len(s) == 6 and int(s[1:3]) <= 23 and int(s[4:6]) <= 59


def o_tzsuffix(v):
    if type(v) is not str or len(v) < 3 or v[0] != '[' or v[-1] != ']':
        return False
    body = v[1:-1]
    if body[:1] == '!':
        body = body[1:]
    if len(body) < 1:
        return False
    if body[0] in '+-':
        return o_numoffset(body)
    return o_tzname(body)


def o_suffixtag(v):
    if type(v) is not str or len(v) < 5 or v[0] != '[' or v[-1] != ']':
        return False
    body = v[1:-1]
    if body[:1] == '!':
        body = body[1:]
    if '=' not in body:
        return False
    key, vals = body.split('=', 1)
    return bool(_RX_KEY.match(key)) and bool(_RX_VALUES.match(vals))


def o_suffix(v):
    if type(v) is not str:
        return False
    i, n = 0, len(v)
    if i < n and v[i] == '[':
        k = v.find(']', i + 1)
        if k < 0:
            return False
        seg = v[i:k + 1]
        body = seg[1:-1]
        b2 = body[1:] if body[:1] == '!' else body
        if '=' not in b2:
            if not o_tzsuffix(seg):
                return False
            i = k + 1
    while i < n:
        if v[i] != '[':
            return False
        k = v.find(']', i + 1)
        if k < 0:
            return False
        if not o_suffixtag(v[i:k + 1]):
            return False
        i = k + 1
    return True


def o_ixdtf(v):
    if type(v) is not str:
        return False
    i = v.find('[')
    if i < 0:
        i = len(v)
    return o_datetime(v[:i]) and o_suffix(v[i:])


def o_tags(v):
    # Independent recomputation of ixdtf_tags; None when the string is invalid.
    if not o_ixdtf(v):
        return None
    cut = v.find('[')
    if cut < 0:
        cut = len(v)
    head, tail = v[:cut], v[cut:]
    tz, tags = None, []
    i, n = 0, len(tail)
    if n and tail[0] == '[':
        k = tail.find(']', 1)
        body = tail[1:k]
        b2 = body[1:] if body[:1] == '!' else body
        if '=' not in b2:
            crit = body[:1] == '!'
            if crit:
                body = body[1:]
            tz = (crit, body)
            i = k + 1
    while i < n:
        k = tail.find(']', i + 1)
        body = tail[i + 1:k]
        crit = body[:1] == '!'
        if crit:
            body = body[1:]
        key, vals = body.split('=', 1)
        tags.append((crit, key, tuple(vals.split('-'))))
        i = k + 1
    return (head, tz, tuple(tags))


JUNK = [None, True, False, 0, 1, -1, 2, 60, 64, 128, 256, 1024, 3.5, -0.0, float('inf'), float('nan'),
        '', 'Z', 'z', 'T', '1996-12-19T16:39:57Z', 'America/Los_Angeles', '[u-ca=hebrew]', 'ok', 'é', '\U0001f600',
        [], [[]], {}, {'x': 1}, (), (1, 2), b'\x00', bytearray(2), {1, 2}, frozenset(), object(), range(3), 0j]
ARGSPEC = {'date_reason': [('value', '1996-12-19')],
           'time_reason': [('value', '16:39:57')],
           'offset_reason': [('value', '+05:30')],
           'datetime_reason': [('value', '1996-12-19T16:39:57Z')],
           'tzname_reason': [('value', 'America/Los_Angeles')],
           'tzsuffix_reason': [('value', '[America/Los_Angeles]')],
           'suffixtag_reason': [('value', '[u-ca=hebrew]')],
           'suffix_reason': [('value', '[America/Los_Angeles][u-ca=hebrew]')],
           'ixdtf_reason': [('value', '1996-12-19T16:39:57-08:00[America/Los_Angeles]')],
           'ixdtf_tags': [('value', '1996-12-19T16:39:57-08:00[America/Los_Angeles]')]}
TOKENS = ('0', '1', '9', 'a', 'k', 'Z', 'z', 'T', 't', ':', '-', '+', '.', '/', '[', ']', '=', '!', '_',
          'A', 'u-ca', 'x', ' ', '\n', 'é', '\U0001f600', '%', '@', ',', '-08:00', '[u-ca=hebrew]',
          '1996-12-19T16:39:57', '16:39:57', '.52', 'America', '/Los_Angeles', '1996-12-19', '+05:30', '[!k=a]')

# ---- RFC 9557 section 4.2 and section 3 examples plus RFC 3339 section 5.8 examples as oracle pins ----
S42 = ['1996-12-19T16:39:57-08:00',
       '1996-12-19T16:39:57-08:00[America/Los_Angeles]',
       '1996-12-19T16:39:57-08:00[America/Los_Angeles][u-ca=hebrew]',
       '1996-12-19T16:39:57-08:00[_foo=bar][_baz=bat]']
S3X = ['2022-07-08T00:14:07+01:00[Europe/Paris]', '2022-07-08T00:14:07+01:00',
       '2022-07-08T00:14:07Z[Europe/Paris]', '2022-07-08T02:14:07+02:00[Europe/Paris]',
       '2022-07-08T00:14:07+01:00[knort=blargel]', '2022-07-08T00:14:07+01:00[!Europe/Paris]',
       '2022-07-08T00:14:07Z[!u-ca=chinese][u-ca=japanese]', '2022-07-08T00:14:07Z[u-ca=chinese][!u-ca=japanese]',
       '2022-07-08T00:14:07Z[!knort=blargel]', '2022-07-08T00:14:07Z[u-ca=chinese][u-ca=japanese]',
       '2022-07-08T00:14:07Z[u-ca=chinese]', '2022-07-08T00:14:07+00:00[!Europe/London]',
       '2022-07-08T00:14:07+00:00[Europe/London]', '2022-07-08T00:14:07Z[!Europe/London]',
       '2022-07-08T00:14:07Z[Europe/London]', '2022-07-08T00:14:07+08:45[+08:45]']
S58 = ['1985-04-12T23:20:50.52Z', '1996-12-19T16:39:57-08:00', '1990-12-31T23:59:60Z',
       '1990-12-31T15:59:60-08:00', '1937-01-01T12:00:27.87+00:20']
ALL_EXAMPLES = S42 + S3X + S58


def test_every_rfc_example_is_valid_ixdtf():
    assert len(ALL_EXAMPLES) == 25
    for v in ALL_EXAMPLES:
        assert m.ixdtf_reason(v) == 'ok', v
        assert o_ixdtf(v), v


def test_rfc3339_examples_are_valid_date_times():
    for v in S58:
        assert m.datetime_reason(v) == 'ok', v
    assert m.time_reason('23:59:60') == 'ok'  # leap second is grammar-valid (NOT_CLAIMED: leap-second table)
    assert m.time_reason('15:59:60') == 'ok'
    assert m.datetime_reason('1990-12-31T23:59:60Z') == 'ok'


def test_ixdtf_tags_over_rfc_examples():
    assert m.ixdtf_tags('1996-12-19T16:39:57-08:00') == ('1996-12-19T16:39:57-08:00', None, ())
    assert m.ixdtf_tags('1996-12-19T16:39:57-08:00[America/Los_Angeles]') == (
        '1996-12-19T16:39:57-08:00', (False, 'America/Los_Angeles'), ())
    assert m.ixdtf_tags('1996-12-19T16:39:57-08:00[America/Los_Angeles][u-ca=hebrew]') == (
        '1996-12-19T16:39:57-08:00', (False, 'America/Los_Angeles'), ((False, 'u-ca', ('hebrew',)),))
    assert m.ixdtf_tags('1996-12-19T16:39:57-08:00[_foo=bar][_baz=bat]') == (
        '1996-12-19T16:39:57-08:00', None, ((False, '_foo', ('bar',)), (False, '_baz', ('bat',))))
    assert m.ixdtf_tags('2022-07-08T00:14:07Z[!u-ca=chinese][u-ca=japanese]') == (
        '2022-07-08T00:14:07Z', None, ((True, 'u-ca', ('chinese',)), (False, 'u-ca', ('japanese',))))
    assert m.ixdtf_tags('2022-07-08T00:14:07+08:45[+08:45]') == ('2022-07-08T00:14:07+08:45', (False, '+08:45'), ())
    assert m.ixdtf_tags('2022-07-08T00:14:07+01:00[!Europe/Paris]') == ('2022-07-08T00:14:07+01:00', (True, 'Europe/Paris'), ())


def test_ixdtf_tags_keeps_duplicate_keys_in_order_no_dedup():
    v = '2022-07-08T00:14:07Z[u-ca=chinese][u-ca=japanese]'
    assert m.ixdtf_tags(v) == ('2022-07-08T00:14:07Z', None, ((False, 'u-ca', ('chinese',)), (False, 'u-ca', ('japanese',))))
    v2 = '1996-12-19T16:39:57Z[k=a-b-c][k=d][!k=e]'
    assert m.ixdtf_tags(v2) == ('1996-12-19T16:39:57Z', None,
                                ((False, 'k', ('a', 'b', 'c')), (False, 'k', ('d',)), (True, 'k', ('e',))))


def test_ixdtf_tags_raises_on_invalid_and_returns_fresh_tuples():
    assert run('ixdtf_tags', 'junk') == E('ixdtf_tags', 'bad_value:value.ixdtf')
    assert run('ixdtf_tags', '1996-12-19T16:39:57') == E('ixdtf_tags', 'bad_value:value.ixdtf')
    assert run('ixdtf_tags', '1996-12-19T16:39:57Z[') == E('ixdtf_tags', 'bad_value:value.ixdtf')
    a = m.ixdtf_tags('1996-12-19T16:39:57Z[u-ca=hebrew]')
    b = m.ixdtf_tags('1996-12-19T16:39:57Z[u-ca=hebrew]')
    assert a == b and a is not b and a[2] is not b[2]


def test_leap_year_rule_4_100_400():
    for y, ok in ((1900, False), (2000, True), (1996, True), (1999, False), (2100, False), (2400, True),
                  (0, True), (4, True), (100, False), (400, True), (1996, True), (1896, True)):
        v = '%04d-02-29' % y
        assert (m.date_reason(v) == 'ok') == ok, v
        assert o_date(v) == ok, v
    assert m.date_reason('1996-02-30') == 'mday.range'
    assert m.date_reason('2000-02-30') == 'mday.range'
    assert m.date_reason('1996-04-31') == 'mday.range'
    assert m.date_reason('1996-06-31') == 'mday.range'


def test_case_variants_t_and_z_accepted_space_rejected():
    assert m.datetime_reason('1996-12-19t16:39:57Z') == 'ok'
    assert m.datetime_reason('1996-12-19T16:39:57z') == 'ok'
    assert m.datetime_reason('1996-12-19t16:39:57z') == 'ok'
    assert m.ixdtf_reason('1996-12-19t16:39:57z[Europe/Paris]') == 'ok'
    assert m.datetime_reason('1996-12-19 16:39:57Z') == 'sep.t'
    assert m.ixdtf_reason('1996-12-19 16:39:57Z[u-ca=hebrew]') == 'datetime.sep.t'


def test_tzname_grammar_not_registry_and_dot_exclusions():
    assert m.tzname_reason('America/Los_Angeles') == 'ok'
    assert m.tzname_reason('Etc/GMT+3') == 'ok'
    assert m.tzname_reason('Not/A/Real_Zone-1+x') == 'ok'  # grammar only; tz database NOT_CLAIMED
    assert m.tzname_reason('.') == 'part.dot'
    assert m.tzname_reason('..') == 'part.dot'
    assert m.tzname_reason('...') == 'ok'
    assert m.tzname_reason('.x') == 'ok'
    assert m.tzname_reason('_x') == 'ok'
    assert m.tzname_reason('/America') == 'part.empty'
    assert m.tzname_reason('America/') == 'part.empty'
    assert m.tzname_reason('') == 'empty'
    assert m.tzsuffix_reason('[This/Is_Not/A/Real/Zone]') == 'ok'  # the 14-character platform limit is not enforced
    assert m.tzsuffix_reason('[.]') == 'name.part.dot'
    assert m.tzsuffix_reason('[..]') == 'name.part.dot'

def test_constants_exact():
    assert m._LEN_CAP == 1024 and type(m._LEN_CAP) is int
    assert m._TAGS_CAP == 128 and type(m._TAGS_CAP) is int
    assert m._VALUES_CAP == 64 and type(m._VALUES_CAP) is int
    assert m._PARTS_CAP == 64 and type(m._PARTS_CAP) is int
    assert m._FRAC_CAP == 64 and type(m._FRAC_CAP) is int
    assert m._MDAYS == (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    assert m.CLAIMS == {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False}
    assert all(v is False for v in m.CLAIMS.values())
    assert 'RFC 9557' in m.SCOPE and 'RFC 9557' in m.__doc__
    assert isinstance(m.NOT_CLAIMED, tuple) and isinstance(m.ADJACENT, tuple)


def test_constants_exact_contents():
    assert m.SCOPE == "RFC 9557 over caller-supplied text: the Internet Extended Date/Time Format (IXDTF) grammar - the RFC 3339 date-time core it imports (full-date, partial-time, time-offset, date-time, re-derived here from the RFC 3339 sections 5.6 and 5.7 texts) plus the section 4.1 suffix grammar (time-zone tag, suffix tags, critical flag), the section 3 key/case rules, and validation of the same. Pure functions; no retrieval, no network, no clock, no calendars, no registries."
    assert m.NOT_CLAIMED == ('standard', 'authority', 'certification', 'currency', 'completeness',
                             'semantics', 'registry', 'leap-second table', 'tz database', 'calendar projection')
    assert m.ADJACENT == ('RFC 3339 grammar itself (b970, b1028 cover it standalone; here it is re-derived from the live RFC 3339 text as the imported core of IXDTF, not reused)',
                          'RFC 5322 date-time (a different grammar, named only by the section 2.2 note)',
                          'the IANA Time Zone Database and the u-ca Unicode calendar registry (names and keys are checked as grammar only)')


def test_order_docstrings_and_private_names():
    fns = [n for n, o in vars(m).items() if type(o) is types.FunctionType and not n.startswith('_')]
    assert [n for n in fns if n not in ('make_fail', 'find_spec')] == list(NAMES)
    for n in NAMES:
        assert callable(getattr(m, n))
        assert len(list(inspect.signature(getattr(m, n)).parameters)) == 1
    for n in PRIVATE:
        assert n in vars(m), n


def test_public_function_definition_order_pinned():
    assert [n for n in vars(m) if n in NAMES] == list(NAMES)


def test_header_quotes_are_in_the_header_and_distinct():
    assert len(QUOTES) == len(set(QUOTES)) and len(QUOTES) >= 30
    for qt in QUOTES:
        assert qt in DOC_EXACT


def test_header_names_erratum_sources_and_functions():
    assert 'EID 8192' in DOC_EXACT
    assert 'Rejected' in DOC_EXACT and 'Editorial' in DOC_EXACT
    assert 'not independently confirmed' in DOC_EXACT
    assert '87fa632cd75d13aa441859da635ed6618f66d203fe71a30fa85afedbeb149e85' in DOC_EXACT
    assert '9ab2b8864a85dca73a88f49b0927bc7bc85f596926e4fd1890905777924e700a' in DOC_EXACT
    assert 'c585df7162898aa21dde9a7856da61aef1e25c7ff153f6f42b8293d7d9558fe9' in DOC_EXACT
    assert '23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c' in DOC_EXACT
    assert 'Updates: RFC 3339' in DOC_EXACT and 'no Obsoletes entry' in DOC_EXACT
    for n in NAMES:
        assert n in DOC_EXACT
    assert DOC_EXACT == m.__doc__


def test_module_imports_and_source_bans():
    with open(MODPATH) as _f:
        _modsrc = _f.read()
    tree = ast.parse(_modsrc)
    imps = set()
    for node in ast.walk(tree):
        if type(node) is ast.Import:
            for a in node.names:
                imps.add(a.name)
        elif type(node) is ast.ImportFrom:
            imps.add(node.module)
    assert imps == {'importlib.util', REG}
    for node in ast.walk(tree):
        assert type(node) is not ast.JoinedStr, 'no f-strings anywhere'
        assert type(node) is not ast.Global and type(node) is not ast.Nonlocal
    src = _modsrc
    for bad in ('ord(', 'chr(', 'socket', 'urllib', 'requests', 'http', 'open(', 'input(', 'eval(', 'exec(',
                'getattr(', 'globals(', 'locals(', 'vars(', 'isinstance(', 'issubclass(', 'hasattr(', 'setattr(',
                'delattr(', 'callable(', ' or True', ' and False', 'if False', 'else True', ' or False',
                '.upper()', '.lower()', '.strip()', '.split(', '.replace(', '.encode(', '.decode(',
                '.isdigit()', '.isalpha()', '.isalnum()', '.find(', '.index(', '.startswith(', '.endswith(',
                '.join(', '.count(', '.title(', '.casefold(', '.swapcase(', '.partition(', '.zfill(',
                'format(', 'import datetime', 'import time', 'import re', 'zoneinfo', 'random'):
        assert bad not in src, bad


def test_source_and_tests_have_no_vacuous_assertions():
    with open(MODPATH) as _f:
        src = _f.read()
    assert ' or True' not in src and 'if False' not in src and 'else True' not in src
    assert ' and False' not in src and ' or False' not in src
    me = os.path.abspath(__file__)
    with open(me) as _f:
        tsrc = _f.read()
    assert ('assert ' + 'True') not in tsrc and ('assert ' + '1') not in tsrc.replace('assert 1 ==', '')


@pytest.mark.parametrize('fn', NAMES)
def test_every_argument_is_an_exact_type_by_identity(fn):
    for bad in (None, 1, 1.5, True, b'x', (), (1,), [1], {1}, {'x': 1}, bytearray(1), 0j):
        r = run(fn, bad)
        assert r == E(fn, 'bad_type:value'), (fn, bad, r)


def test_str_subclasses_and_hostile_metaclass_refused():
    class S(str):
        pass
    class M(type):
        def __eq__(cls, other):
            return True
    class HostileStr(str, metaclass=M):
        pass
    for fn in NAMES:
        good = ARGSPEC[fn][0][1]
        assert run(fn, S(good)) == E(fn, 'bad_type:value'), fn
        assert run(fn, HostileStr(good)) == E(fn, 'bad_type:value'), fn


def test_bool_is_refused_where_a_string_is_expected():
    for fn in NAMES:
        assert run(fn, True) == E(fn, 'bad_type:value')
        assert run(fn, False) == E(fn, 'bad_type:value')


def test_len_cap_at_cap_and_cap_plus_one_on_every_function():
    at = 'x' * 1024
    over = 'x' * 1025
    at_tags = '1996-12-19T16:39:57Z[aa]' + '[k=a]' * 127 + '[k=' + 'a' * 361 + ']'
    assert len(at_tags) == 1024
    for fn in NAMES:
        r = run(fn, at_tags if fn == 'ixdtf_tags' else at)
        assert r[0] == 'ok', (fn, r)
        assert run(fn, over) == E(fn, 'bad_value:value.length'), fn
    got = m.ixdtf_tags(at_tags)
    assert len(got[2]) == 128 and got[2][-1] == (False, 'k', ('a' * 361,))


def test_frac_cap_at_cap_and_cap_plus_one():
    assert m.time_reason('16:39:57.' + '1' * 64) == 'ok'
    assert run('time_reason', '16:39:57.' + '1' * 65) == E('time_reason', 'bad_value:frac.length')
    assert m.datetime_reason('1996-12-19T16:39:57.' + '1' * 64 + 'Z') == 'ok'
    assert run('datetime_reason', '1996-12-19T16:39:57.' + '1' * 65 + 'Z') == E('time_reason', 'bad_value:frac.length')
    assert run('ixdtf_reason', '1996-12-19T16:39:57.' + '1' * 65 + 'Z[u-ca=x]') == E('time_reason', 'bad_value:frac.length')


def test_parts_cap_at_cap_and_cap_plus_one():
    ok64 = '/'.join(['a'] * 64)
    over65 = '/'.join(['a'] * 65)
    assert len(ok64.split('/')) == 64
    assert m.tzname_reason(ok64) == 'ok'
    assert run('tzname_reason', over65) == E('tzname_reason', 'bad_value:parts.length')
    assert m.tzsuffix_reason('[' + ok64 + ']') == 'ok'
    assert run('tzsuffix_reason', '[' + over65 + ']') == E('tzname_reason', 'bad_value:parts.length')
    assert m.suffix_reason('[' + ok64 + ']') == 'ok'
    assert run('suffix_reason', '[' + over65 + ']') == E('tzname_reason', 'bad_value:parts.length')
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[' + ok64 + ']') == 'ok'
    assert run('ixdtf_reason', '1996-12-19T16:39:57Z[' + over65 + ']') == E('tzname_reason', 'bad_value:parts.length')


def test_values_cap_at_cap_and_cap_plus_one():
    ok64 = '[k=' + '-'.join(['a'] * 64) + ']'
    over65 = '[k=' + '-'.join(['a'] * 65) + ']'
    assert m.suffixtag_reason(ok64) == 'ok'
    assert run('suffixtag_reason', over65) == E('suffixtag_reason', 'bad_value:values.length')
    assert m.suffix_reason(ok64) == 'ok'
    assert run('suffix_reason', over65) == E('suffixtag_reason', 'bad_value:values.length')
    assert m.ixdtf_reason('1996-12-19T16:39:57Z' + ok64) == 'ok'
    assert run('ixdtf_reason', '1996-12-19T16:39:57Z' + over65) == E('suffixtag_reason', 'bad_value:values.length')
    assert m.ixdtf_tags('1996-12-19T16:39:57Z' + ok64)[2][0][2] == tuple(['a'] * 64)


def test_tags_cap_at_cap_and_cap_plus_one():
    ok128 = '[k=a]' * 128
    over129 = '[k=a]' * 129
    assert len(ok128) == 640 and len('1996-12-19T16:39:57Z' + over129) == 665 < 1024
    assert m.suffix_reason(ok128) == 'ok'
    assert run('suffix_reason', over129) == E('suffix_reason', 'bad_value:tags.length')
    assert m.ixdtf_reason('1996-12-19T16:39:57Z' + ok128) == 'ok'
    assert run('ixdtf_reason', '1996-12-19T16:39:57Z' + over129) == E('ixdtf_reason', 'bad_value:tags.length')
    assert run('ixdtf_tags', '1996-12-19T16:39:57Z' + over129) == E('ixdtf_reason', 'bad_value:tags.length')
    assert len(m.ixdtf_tags('1996-12-19T16:39:57Z' + ok128)[2]) == 128



def test_swap_survivor_pins_guard_order():
    # Order-swap survivor pins (rev2): each input is runtime-built and sits on
    # the boundary where TWO consecutive guards hold, so swapping the guards
    # changes the reported reason. Each asserts the ORIGINAL check order.
    assert m.offset_reason(' ' + '0:00') == 'shape'      # len != 6 before sign
    assert m.offset_reason(' ' + '00x00') == 'sign'      # sign before colon
    assert m.tzname_reason('0' + ' ' + 'x') == 'part.initial'  # initial before char
    assert m._numoffset_shape(' ' + '0:00') == 'shape'   # len != 6 before sign
    assert m._numoffset_shape(' ' + '00x00') == 'sign'   # sign before colon
    tag_run = '[a=b]' * 128 + 'x'
    assert run('suffix_reason', tag_run) == E('suffix_reason', 'bad_value:tags.length')
    val_run = '[k=' + '-'.join(['a'] * 64) + '-' + ']'
    assert run('suffixtag_reason', val_run) == E('suffixtag_reason', 'bad_value:values.length')
    ix_run = '2020-13-01T00:00:00Z' + '[k=a]' * 129
    assert m.ixdtf_reason(ix_run) == 'datetime.date.month.range'  # date before suffix caps


def test_long_inputs_above_the_small_int_cache():
    # Main 7:53 hygiene: `!=` -> `is not` and `==` -> `is` on loop bounds and
    # length compares are only distinguishable above the 256 small-int cache.
    # Every loop bound and length compare below sees a >256-character input and
    # a 2048 edge (over _LEN_CAP, exercising len(v) > 1024 with uncached ints).
    long_name = 'a' * 300
    assert m.tzname_reason(long_name) == 'ok'                      # parts-loop bound
    assert m.tzsuffix_reason('[' + long_name + ']') == 'ok'        # tz branch
    long_frac = '00:00:00.' + '1' * 60
    assert m.time_reason(long_frac) == 'ok'                        # frac under _FRAC_CAP 64
    long_date = '2020-02-29T23:59:59.' + '1' * 300 + 'Z'
    assert run('datetime_reason', long_date) == E('time_reason', 'bad_value:frac.length')
    no_off = '2020-02-29T23:59:59' + '1' * 300
    assert m.datetime_reason(no_off) == 'time.frac.dot'            # L211 loop runs j to n > 256
    long_tag = '[k=' + 'a' * 300 + ']'
    assert m.suffixtag_reason(long_tag) == 'ok'                    # key/val scans
    assert m.suffix_reason('[Europe/Berlin]' + '[k=' + 'a' * 300 + ']') == 'ok'
    assert m.ixdtf_reason('2020-02-29T23:59:59Z' + '[k=' + 'a' * 300 + ']') == 'ok'
    for fn in (m.date_reason, m.time_reason, m.offset_reason, m.datetime_reason,
               m.tzname_reason, m.tzsuffix_reason, m.suffixtag_reason, m.suffix_reason,
               m.ixdtf_reason):
        assert run(fn.__name__, '0' * 2048)[0] == 'err'            # 2048 > _LEN_CAP raises
    assert run('ixdtf_tags', '0' * 2048)[0] == 'err'

def test_cap_checks_fire_before_content():
    assert run('date_reason', 'x' * 1025) == E('date_reason', 'bad_value:value.length')
    assert run('ixdtf_reason', '1996-13-99T99:99:99' + '[+99:99]' + 'x' * 1010) == E('ixdtf_reason', 'bad_value:value.length')
    assert run('time_reason', '23:59:59.' + 'x' * 65) == E('time_reason', 'bad_value:frac.length')
    assert run('suffix_reason', '[k=a]' * 128 + '[j=k]') == E('suffix_reason', 'bad_value:tags.length')


def test_date_check_order_pins():
    assert run('date_reason', None) == E('date_reason', 'bad_type:value')
    assert m.date_reason('1996-12-1') == 'shape'
    assert m.date_reason('1996-12-199') == 'shape'
    assert m.date_reason('1996/12/19') == 'shape'
    assert m.date_reason('1996-1219') == 'shape'
    assert m.date_reason('x996-13-99') == 'year'
    assert m.date_reason('1996-aa-99') == 'month'
    assert m.date_reason('1996-13-99') == 'month.range'
    assert m.date_reason('1996-00-99') == 'month.range'
    assert m.date_reason('1996-12-bb') == 'mday'
    assert m.date_reason('1996-12-00') == 'mday.range'
    assert m.date_reason('1996-12-32') == 'mday.range'


def test_time_check_order_pins():
    assert m.time_reason('') == 'shape'
    assert m.time_reason('16:39:5') == 'shape'
    assert m.time_reason('16;39:57') == 'shape'
    assert m.time_reason('16:39;57') == 'shape'
    assert m.time_reason('x6:60:61') == 'hour'
    assert m.time_reason('24:60:61') == 'hour.range'
    assert m.time_reason('23:x0:61') == 'minute'
    assert m.time_reason('23:60:61') == 'minute.range'
    assert m.time_reason('23:59:6x') == 'second'
    assert m.time_reason('23:59:61') == 'second.range'
    assert m.time_reason('23:59:60') == 'ok'
    assert m.time_reason('23:59:59x') == 'frac.dot'
    assert m.time_reason('23:59:59,5') == 'frac.dot'
    assert m.time_reason('23:59:59.') == 'frac.empty'
    assert m.time_reason('23:59:59.1x') == 'frac.char'
    assert m.time_reason('23:59:59.0000000001') == 'ok'


def test_offset_check_order_pins():
    assert m.offset_reason('') == 'shape'
    assert m.offset_reason('ZZ') == 'shape'
    assert m.offset_reason('Z0') == 'shape'
    assert m.offset_reason('z') == 'ok'
    assert m.offset_reason('+') == 'shape'
    assert m.offset_reason('+0:00') == 'shape'
    assert m.offset_reason('+000:00') == 'shape'
    assert m.offset_reason('+00x00') == 'shape'
    assert m.offset_reason('x00:00') == 'sign'
    assert m.offset_reason('+x0:60') == 'hour'
    assert m.offset_reason('+24:60') == 'hour.range'
    assert m.offset_reason('+00:x0') == 'minute'
    assert m.offset_reason('+00:60') == 'minute.range'
    assert m.offset_reason('-00:00') == 'ok'  # deprecated semantically; grammar-valid (NOT_CLAIMED)


def test_datetime_check_order_pins():
    assert m.datetime_reason('') == 'shape'
    assert m.datetime_reason('1996-12-19T16:39:57') == 'shape'
    assert m.datetime_reason('1996-13-19 16:39:57Z') == 'date.month.range'
    assert m.datetime_reason('1996-12-19 16:39:57Z') == 'sep.t'
    assert m.datetime_reason('1996-12-19x16:39:57Z') == 'sep.t'
    assert m.datetime_reason('1996-12-19T24:39:57Z') == 'time.hour.range'
    assert m.datetime_reason('1996-12-19T16:39:57.1') == 'offset.shape'
    assert m.datetime_reason('1996-12-19T16:39:57+') == 'offset.shape'
    assert m.datetime_reason('1996-12-19T16:39:57+24:00') == 'offset.hour.range'
    assert m.datetime_reason('1996-12-19T16:39:57.12xZ') == 'time.frac.char'
    assert m.datetime_reason('1996-12-19T16:39:57.1+05:30') == 'ok'


def test_tzname_check_order_pins():
    assert m.tzname_reason('') == 'empty'
    assert m.tzname_reason('/') == 'part.empty'
    assert m.tzname_reason('/a') == 'part.empty'
    assert m.tzname_reason('a//b') == 'part.empty'
    assert m.tzname_reason('./x') == 'part.dot'
    assert m.tzname_reason('9a') == 'part.initial'
    assert m.tzname_reason('-a') == 'part.initial'
    assert m.tzname_reason('+a') == 'part.initial'
    assert m.tzname_reason('a b') == 'part.char'
    assert m.tzname_reason('a=b') == 'part.char'
    assert m.tzname_reason('a:b') == 'part.char'
    assert m.tzname_reason('a/9b') == 'part.initial'
    assert m.tzname_reason('a/.') == 'part.dot'


def test_tzsuffix_check_order_pins():
    assert m.tzsuffix_reason('') == 'shape'
    assert m.tzsuffix_reason('[]') == 'shape'
    assert m.tzsuffix_reason('ab') == 'shape'
    assert m.tzsuffix_reason('abc') == 'open'
    assert m.tzsuffix_reason('[ab') == 'close'
    assert m.tzsuffix_reason('[!]') == 'empty'
    assert m.tzsuffix_reason('[!+05:30]') == 'ok'
    assert m.tzsuffix_reason('[+]') == 'offset.shape'
    assert m.tzsuffix_reason('[+1:00]') == 'offset.shape'
    assert m.tzsuffix_reason('[+x5:00]') == 'offset.hour'
    assert m.tzsuffix_reason('[+25:00]') == 'offset.hour.range'
    assert m.tzsuffix_reason('[+05:x0]') == 'offset.minute'
    assert m.tzsuffix_reason('[+05:60]') == 'offset.minute.range'
    assert m.tzsuffix_reason('[-00:00]') == 'ok'
    assert m.tzsuffix_reason('[a/]') == 'name.part.empty'
    assert m.tzsuffix_reason('[9a]') == 'name.part.initial'
    assert m.tzsuffix_reason('[a b]') == 'name.part.char'


def test_suffixtag_check_order_pins():
    assert m.suffixtag_reason('') == 'shape'
    assert m.suffixtag_reason('[k=]') == 'shape'
    assert m.suffixtag_reason('abcd') == 'shape'
    assert m.suffixtag_reason('abcde') == 'open'
    assert m.suffixtag_reason('[abcd') == 'close'
    assert m.suffixtag_reason('[abcd]') == 'eq.missing'
    assert m.suffixtag_reason('[ABCD]') == 'eq.missing'
    assert m.suffixtag_reason('[=xy]') == 'key.empty'
    assert m.suffixtag_reason('[1=x]') == 'key.initial'
    assert m.suffixtag_reason('[A=x]') == 'key.initial'
    assert m.suffixtag_reason('[a!=x]') == 'key.char'
    assert m.suffixtag_reason('[k=a-]') == 'value.empty'
    assert m.suffixtag_reason('[k=-a]') == 'value.empty'
    assert m.suffixtag_reason('[k=--]') == 'value.empty'
    assert m.suffixtag_reason('[k=a!]') == 'value.char'
    assert m.suffixtag_reason('[k=a b]') == 'value.char'
    assert m.suffixtag_reason('[k=a-b-c-9]') == 'ok'
    assert m.suffixtag_reason('[!k=a]') == 'ok'
    assert m.suffixtag_reason('[!_x=1]') == 'ok'
    assert m.suffixtag_reason('[_x=1]') == 'ok'
    assert m.suffixtag_reason('[U-CA=x]') == 'key.initial'


def test_suffix_check_order_pins():
    assert m.suffix_reason('') == 'ok'
    assert m.suffix_reason('x') == 'suffix.char'
    assert m.suffix_reason(' [u-ca=x]') == 'suffix.char'
    assert m.suffix_reason('[') == 'tz.close'
    assert m.suffix_reason('[x=y') == 'tz.close'
    assert m.suffix_reason('[+25:00][k=a]') == 'tz.offset.hour.range'
    assert m.suffix_reason('[!][k=a]') == 'tz.empty'
    assert m.suffix_reason('[]') == 'tz.shape'
    assert m.suffix_reason('[x=]') == 'tag.shape'
    assert m.suffix_reason('[u-ca=x][') == 'tag.close'
    assert m.suffix_reason('[u-ca=x]y') == 'suffix.char'
    assert m.suffix_reason('[u-ca=x][+05:30]') == 'tag.eq.missing'
    assert m.suffix_reason('[America/Los_Angeles][Europe/Paris]') == 'tag.eq.missing'
    assert m.suffix_reason('[u-ca=x][1=x]') == 'tag.key.initial'
    assert m.suffix_reason('[+05:30][u-ca=x][!knort=blargel]') == 'ok'
    assert m.suffix_reason('[!u-ca=hebrew]') == 'ok'


def test_ixdtf_check_order_pins():
    assert m.ixdtf_reason('Z[u-ca=x]') == 'datetime.shape'
    assert m.ixdtf_reason('not-a-date[x=') == 'datetime.shape'
    assert m.ixdtf_reason('1996-13-19T16:39:57Z[') == 'datetime.date.month.range'
    assert m.ixdtf_reason('1996-12-19 16:39:57Z[u-ca=x]') == 'datetime.sep.t'
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[') == 'tz.close'
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[]') == 'tz.shape'
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[!]') == 'tz.empty'
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[+25:00]') == 'tz.offset.hour.range'
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[u-ca=x][') == 'tag.close'
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[u-ca=x]y') == 'suffix.char'
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[u-ca=x][U-CA=y]') == 'tag.key.initial'
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[.][u-ca=x]') == 'tz.name.part.dot'
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[America/Los_Angeles][u-ca=hebrew][_foo=bar-baz]') == 'ok'


def test_first_bracket_with_equals_is_a_tag_not_a_zone():
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[u-ca=hebrew]') == 'ok'
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[u-ca=hebrew][America/Los_Angeles]') == 'tag.eq.missing'
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[!u-ca=hebrew]') == 'ok'
    assert m.ixdtf_tags('1996-12-19T16:39:57Z[u-ca=hebrew]') == (
        '1996-12-19T16:39:57Z', None, ((False, 'u-ca', ('hebrew',)),))
    assert m.ixdtf_reason('1996-12-19T16:39:57Z[=xy]') == 'tag.key.empty'


def test_ixdtf_tags_structure_and_types():
    r = m.ixdtf_tags('1996-12-19T16:39:57-08:00[!America/Los_Angeles][u-ca=hebrew][_foo=bar-baz]')
    assert r == ('1996-12-19T16:39:57-08:00', (True, 'America/Los_Angeles'),
                 ((False, 'u-ca', ('hebrew',)), (False, '_foo', ('bar', 'baz'))))
    assert type(r) is tuple and type(r[2]) is tuple and type(r[2][1][2]) is tuple
    assert type(r[1][0]) is bool and r[1][0] is True
    r2 = m.ixdtf_tags('1996-12-19T16:39:57Z[+05:30]')
    assert r2 == ('1996-12-19T16:39:57Z', (False, '+05:30'), ())
    r3 = m.ixdtf_tags('1996-12-19T16:39:57Z[!-08:00]')
    assert r3 == ('1996-12-19T16:39:57Z', (True, '-08:00'), ())


def test_nested_cap_raises_propagate_under_owning_name():
    assert run('datetime_reason', '1996-12-19T16:39:57.' + '1' * 65 + 'Z') == E('time_reason', 'bad_value:frac.length')
    assert run('tzsuffix_reason', '[' + '/'.join(['a'] * 65) + ']') == E('tzname_reason', 'bad_value:parts.length')
    assert run('suffix_reason', '[' + '/'.join(['a'] * 65) + ']') == E('tzname_reason', 'bad_value:parts.length')
    assert run('ixdtf_reason', '1996-12-19T16:39:57Z[' + '/'.join(['a'] * 65) + ']') == E('tzname_reason', 'bad_value:parts.length')
    assert run('ixdtf_reason', '1996-12-19T16:39:57Z[k=' + '-'.join(['a'] * 65) + ']') == E('suffixtag_reason', 'bad_value:values.length')
    assert run('ixdtf_tags', '1996-12-19T16:39:57.' + '1' * 65 + 'Z') == E('time_reason', 'bad_value:frac.length')


def test_inputs_are_untouched_and_results_fresh():
    v = '1996-12-19T16:39:57-08:00[America/Los_Angeles][u-ca=hebrew]'
    assert m.ixdtf_reason(v) == 'ok'
    assert v == '1996-12-19T16:39:57-08:00[America/Los_Angeles][u-ca=hebrew]'
    t1 = m.ixdtf_tags(v)
    assert m.ixdtf_reason(v) == 'ok' and m.ixdtf_tags(v) == t1


def _fuzz_strings(rng, count):
    out = []
    for _ in range(count):
        n = rng.randrange(0, 14)
        s = ''.join(rng.choice(TOKENS) for _ in range(n))
        out.append(s)
        if rng.randrange(3) == 0:
            base = rng.choice(ALL_EXAMPLES)
            if base:
                i = rng.randrange(len(base))
                out.append(base[:i] + rng.choice(TOKENS) + base[i + 1:])
    return out


@pytest.mark.parametrize('seed', (1259, 95572024, 31415))
def test_fuzz_reason_functions_against_oracle_1200(seed):
    rng = random.Random(seed)
    for v in _fuzz_strings(rng, 1200):
        assert len(v) < 1024
        for fn, oracle in (('date_reason', o_date), ('time_reason', o_time), ('offset_reason', o_offset),
                           ('datetime_reason', o_datetime), ('tzname_reason', o_tzname),
                           ('tzsuffix_reason', o_tzsuffix), ('suffixtag_reason', o_suffixtag),
                           ('suffix_reason', o_suffix), ('ixdtf_reason', o_ixdtf)):
            r = run(fn, v)
            assert r[0] == 'ok', (fn, v, r)
            assert (r[1] == 'ok') == oracle(v), (fn, v, r)


@pytest.mark.parametrize('seed', (1259, 95572024, 31415))
def test_fuzz_ixdtf_tags_against_oracle_1200(seed):
    rng = random.Random(seed)
    for v in _fuzz_strings(rng, 1200):
        r = run('ixdtf_tags', v)
        want = o_tags(v)
        if want is None:
            assert r == E('ixdtf_tags', 'bad_value:value.ixdtf'), (v, r)
        else:
            assert r == ('ok', want), (v, r, want)

# ---- registry guard, import log, namespace ----------------------------------------------------------------------
def test_registry_absent_uses_local_fallback(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh()
    assert mod.make_fail.__module__ == mod.__name__
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert run('date_reason', 1, mod=mod) == ('err', 'P235:date_reason:bad_type:value')


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
CALLS = [(fn, tuple(g for _n, g in ARGSPEC[fn]), tuple([None] + [g for _n, g in ARGSPEC[fn]][1:])) for fn in NAMES]


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
CORPUS.append(('time_reason', ('16:39:57.' + '1' * 65,), 'bad_value:frac.length'))
CORPUS.append(('tzname_reason', ('/'.join(['a'] * 65),), 'bad_value:parts.length'))
CORPUS.append(('suffixtag_reason', ('[k=' + '-'.join(['a'] * 65) + ']',), 'bad_value:values.length'))
CORPUS.append(('suffix_reason', ('[k=a]' * 129,), 'bad_value:tags.length'))
CORPUS.append(('ixdtf_reason', ('1996-12-19T16:39:57Z' + '[k=a]' * 129,), 'bad_value:tags.length'))
CORPUS.append(('ixdtf_tags', ('junk',), 'bad_value:value.ixdtf'))
CORPUS2 = [('datetime_reason', ('1996-12-19T16:39:57.' + '1' * 65 + 'Z',), 'time_reason:bad_value:frac.length'),
           ('ixdtf_reason', ('1996-12-19T16:39:57.' + '1' * 65 + 'Z',), 'time_reason:bad_value:frac.length'),
           ('ixdtf_tags', ('1996-12-19T16:39:57.' + '1' * 65 + 'Z',), 'time_reason:bad_value:frac.length'),
           ('tzsuffix_reason', ('[' + '/'.join(['a'] * 65) + ']',), 'tzname_reason:bad_value:parts.length'),
           ('suffix_reason', ('[' + '/'.join(['a'] * 65) + ']',), 'tzname_reason:bad_value:parts.length'),
           ('ixdtf_reason', ('1996-12-19T16:39:57Z[' + '/'.join(['a'] * 65) + ']',), 'tzname_reason:bad_value:parts.length'),
           ('suffix_reason', ('[k=' + '-'.join(['a'] * 65) + ']',), 'suffixtag_reason:bad_value:values.length'),
           ('ixdtf_reason', ('1996-12-19T16:39:57Z[k=' + '-'.join(['a'] * 65) + ']',), 'suffixtag_reason:bad_value:values.length'),
           ('ixdtf_tags', ('1996-12-19T16:39:57Z' + '[k=a]' * 129,), 'ixdtf_reason:bad_value:tags.length')]
SUCCESS = [('date_reason', ('1996-12-19',), 'ok'), ('date_reason', ('1996-02-29',), 'ok'),
           ('date_reason', ('2000-02-29',), 'ok'), ('date_reason', ('1900-02-29',), 'mday.range'),
           ('date_reason', ('1996-12-1',), 'shape'), ('date_reason', ('x996-12-19',), 'year'),
           ('date_reason', ('1996-aa-19',), 'month'), ('date_reason', ('1996-13-19',), 'month.range'),
           ('date_reason', ('1996-12-bb',), 'mday'), ('date_reason', ('1996-12-32',), 'mday.range'),
           ('time_reason', ('16:39:57',), 'ok'), ('time_reason', ('23:59:60',), 'ok'),
           ('time_reason', ('16:39:57.52',), 'ok'), ('time_reason', ('16:39:5',), 'shape'),
           ('time_reason', ('x6:39:57',), 'hour'), ('time_reason', ('24:39:57',), 'hour.range'),
           ('time_reason', ('16:x9:57',), 'minute'), ('time_reason', ('16:60:57',), 'minute.range'),
           ('time_reason', ('16:39:x7',), 'second'), ('time_reason', ('16:39:61',), 'second.range'),
           ('time_reason', ('16:39:57x',), 'frac.dot'), ('time_reason', ('16:39:57.',), 'frac.empty'),
           ('time_reason', ('16:39:57.5x',), 'frac.char'),
           ('offset_reason', ('Z',), 'ok'), ('offset_reason', ('z',), 'ok'),
           ('offset_reason', ('+05:30',), 'ok'), ('offset_reason', ('-00:00',), 'ok'),
           ('offset_reason', ('',), 'shape'), ('offset_reason', ('ZZ',), 'shape'),
           ('offset_reason', ('x00:00',), 'sign'), ('offset_reason', ('+x0:00',), 'hour'),
           ('offset_reason', ('+24:00',), 'hour.range'), ('offset_reason', ('+00:x0',), 'minute'),
           ('offset_reason', ('+00:60',), 'minute.range'),
           ('datetime_reason', ('1996-12-19T16:39:57Z',), 'ok'), ('datetime_reason', ('1996-12-19t16:39:57z',), 'ok'),
           ('datetime_reason', ('1985-04-12T23:20:50.52Z',), 'ok'), ('datetime_reason', ('1990-12-31T23:59:60Z',), 'ok'),
           ('datetime_reason', ('1996-12-19T16:39:57',), 'shape'),
           ('datetime_reason', ('1996-13-19T16:39:57Z',), 'date.month.range'),
           ('datetime_reason', ('1996-12-19 16:39:57Z',), 'sep.t'),
           ('datetime_reason', ('1996-12-19T24:39:57Z',), 'time.hour.range'),
           ('datetime_reason', ('1996-12-19T16:39:57+',), 'offset.shape'),
           ('datetime_reason', ('1996-12-19T16:39:57+24:00',), 'offset.hour.range'),
           ('tzname_reason', ('America/Los_Angeles',), 'ok'), ('tzname_reason', ('',), 'empty'),
           ('tzname_reason', ('/a',), 'part.empty'), ('tzname_reason', ('.',), 'part.dot'),
           ('tzname_reason', ('..',), 'part.dot'), ('tzname_reason', ('...',), 'ok'),
           ('tzname_reason', ('9a',), 'part.initial'), ('tzname_reason', ('a b',), 'part.char'),
           ('tzsuffix_reason', ('[America/Los_Angeles]',), 'ok'), ('tzsuffix_reason', ('[!Europe/Paris]',), 'ok'),
           ('tzsuffix_reason', ('[+05:30]',), 'ok'), ('tzsuffix_reason', ('[]',), 'shape'),
           ('tzsuffix_reason', ('abc',), 'open'), ('tzsuffix_reason', ('[ab',), 'close'),
           ('tzsuffix_reason', ('[!]',), 'empty'), ('tzsuffix_reason', ('[+]',), 'offset.shape'),
           ('tzsuffix_reason', ('[+25:00]',), 'offset.hour.range'), ('tzsuffix_reason', ('[.]',), 'name.part.dot'),
           ('tzsuffix_reason', ('[9a]',), 'name.part.initial'),
           ('suffixtag_reason', ('[u-ca=hebrew]',), 'ok'), ('suffixtag_reason', ('[!knort=blargel]',), 'ok'),
           ('suffixtag_reason', ('[_foo=bar]',), 'ok'), ('suffixtag_reason', ('[k=a-b-c]',), 'ok'),
           ('suffixtag_reason', ('[k=]',), 'shape'), ('suffixtag_reason', ('abcde',), 'open'),
           ('suffixtag_reason', ('[abcd',), 'close'), ('suffixtag_reason', ('[abcd]',), 'eq.missing'),
           ('suffixtag_reason', ('[=xy]',), 'key.empty'), ('suffixtag_reason', ('[1=x]',), 'key.initial'),
           ('suffixtag_reason', ('[a!=x]',), 'key.char'), ('suffixtag_reason', ('[k=a-]',), 'value.empty'),
           ('suffixtag_reason', ('[k=a!]',), 'value.char'),
           ('suffix_reason', ('',), 'ok'), ('suffix_reason', ('[America/Los_Angeles]',), 'ok'),
           ('suffix_reason', ('[+05:30]',), 'ok'), ('suffix_reason', ('[u-ca=hebrew]',), 'ok'),
           ('suffix_reason', ('[America/Los_Angeles][u-ca=hebrew][_foo=bar]',), 'ok'),
           ('suffix_reason', ('x',), 'suffix.char'), ('suffix_reason', ('[',), 'tz.close'),
           ('suffix_reason', ('[]',), 'tz.shape'), ('suffix_reason', ('[!]',), 'tz.empty'),
           ('suffix_reason', ('[+25:00]',), 'tz.offset.hour.range'),
           ('suffix_reason', ('[u-ca=x][',), 'tag.close'), ('suffix_reason', ('[u-ca=x]y',), 'suffix.char'),
           ('suffix_reason', ('[u-ca=x][+05:30]',), 'tag.eq.missing'),
           ('ixdtf_reason', ('1996-12-19T16:39:57-08:00',), 'ok'),
           ('ixdtf_reason', ('1996-12-19T16:39:57-08:00[America/Los_Angeles][u-ca=hebrew]',), 'ok'),
           ('ixdtf_reason', ('Z[u-ca=x]',), 'datetime.shape'),
           ('ixdtf_reason', ('1996-12-19 16:39:57Z[u-ca=x]',), 'datetime.sep.t'),
           ('ixdtf_reason', ('1996-12-19T16:39:57Z[',), 'tz.close'),
           ('ixdtf_reason', ('1996-12-19T16:39:57Z[u-ca=x]y',), 'suffix.char'),
           ('ixdtf_reason', ('1996-12-19T16:39:57Z[u-ca=x][U-CA=y]',), 'tag.key.initial'),
           ('ixdtf_tags', ('1996-12-19T16:39:57-08:00',), ('1996-12-19T16:39:57-08:00', None, ())),
           ('ixdtf_tags', ('2022-07-08T00:14:07Z[!u-ca=chinese][u-ca=japanese]',),
            ('2022-07-08T00:14:07Z', None, ((True, 'u-ca', ('chinese',)), (False, 'u-ca', ('japanese',))))),
           ('ixdtf_tags', ('2022-07-08T00:14:07+08:45[+08:45]',), ('2022-07-08T00:14:07+08:45', (False, '+08:45'), ())),
           ]


def drive(mod, pfx=None):
    p = PFX if pfx is None else pfx
    for fn, args, want in CORPUS:
        with pytest.raises(ValueError) as e:
            getattr(mod, fn)(*args)
        assert str(e.value) == p + fn + ':' + want
    for fn, args, want in CORPUS2:
        with pytest.raises(ValueError) as e:
            getattr(mod, fn)(*args)
        assert str(e.value) == p + want
    for fn, args, want in SUCCESS:
        assert getattr(mod, fn)(*args) == want


def test_corpus_reaches_every_refusal_code_and_every_success_branch():
    drive(m)
    codes = {(fn, w) for fn, a, w in CORPUS}
    for fn in NAMES:
        for _name, _g in ARGSPEC[fn]:
            assert (fn, 'bad_type:' + _name) in codes
        assert (fn, 'bad_value:value.length') in codes
    byfn = {}
    for f, a, w in SUCCESS:
        byfn.setdefault(f, set()).add(w)
    assert byfn['date_reason'] >= {'ok', 'shape', 'year', 'month', 'month.range', 'mday', 'mday.range'}
    assert byfn['time_reason'] >= {'ok', 'shape', 'hour', 'hour.range', 'minute', 'minute.range',
                                   'second', 'second.range', 'frac.dot', 'frac.empty', 'frac.char'}
    assert byfn['offset_reason'] >= {'ok', 'shape', 'sign', 'hour', 'hour.range', 'minute', 'minute.range'}
    assert byfn['datetime_reason'] >= {'ok', 'shape', 'sep.t', 'date.month.range', 'time.hour.range',
                                       'offset.shape', 'offset.hour.range'}
    assert byfn['tzname_reason'] >= {'ok', 'empty', 'part.empty', 'part.dot', 'part.initial', 'part.char'}
    assert byfn['tzsuffix_reason'] >= {'ok', 'shape', 'open', 'close', 'empty', 'offset.shape',
                                       'offset.hour.range', 'name.part.dot', 'name.part.initial'}
    assert byfn['suffixtag_reason'] >= {'ok', 'shape', 'open', 'close', 'eq.missing', 'key.empty',
                                        'key.initial', 'key.char', 'value.empty', 'value.char'}
    assert byfn['suffix_reason'] >= {'ok', 'suffix.char', 'tz.close', 'tz.shape', 'tz.empty',
                                     'tz.offset.hour.range', 'tag.close', 'tag.eq.missing'}
    assert byfn['ixdtf_reason'] >= {'ok', 'datetime.shape', 'datetime.sep.t', 'tz.close', 'suffix.char',
                                    'tag.key.initial'}
    assert sum(1 for f, a, w in SUCCESS if f == 'ixdtf_tags') == 3


def test_fallback_failer_world_has_no_imports_one_success_and_every_refusal(mp):
    real = builtins.__import__
    seen = []
    name = 'b1259_fallback_world'

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
    mod = fresh('b1259_site_world')
    sites = set()
    for fn, args, want in [(f, a, f + ':' + w) for f, a, w in CORPUS] + CORPUS2:
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
    mod = fresh('b1259_doc_world')
    assert mod.make_fail.__doc__ is None
    assert mod.make_fail('x').__doc__ is None
    assert mod.make_fail.__name__ == 'make_fail' and mod.make_fail('x').__name__ == 'fail'


def test_find_spec_is_consulted_exactly_once_in_the_absent_world_simulation(mp):
    spied = []
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda n: spied.append(n) or None)
    mod = fresh('b1259_spec_world')
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
            "import app.modules.instinct_doc.p235_concepts_batch1259_ixdtf as m\n"
            "print(m.ixdtf_reason('1996-12-19T16:39:57-08:00[America/Los_Angeles]'),"
            " m.date_reason('1900-02-29'),"
            " m.tzsuffix_reason('[+25:00]'),"
            " m.ixdtf_reason('1996-12-19 16:39:57Z[u-ca=x]'),"
            " m.ixdtf_tags('2022-07-08T00:14:07Z[!u-ca=chinese]'))\n") % (
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(m.__file__)))),)
    want = ("ok mday.range offset.hour.range datetime.sep.t "
            "('2022-07-08T00:14:07Z', None, ((True, 'u-ca', ('chinese',)),))")
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == want
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25, env={'PYTHONHASHSEED': '7'})
    assert out.stdout.strip() == want


def test_digit_slots_reject_letters_including_x():
    # X must not be a digit (mutant _DIGITS + 'X'), and a non-digit year must
    # report year, not silently parse as 0 (mutant _digits -1 -> 0).
    assert m.date_reason('202X-01-01') == 'year'
    assert m.date_reason('AAAA-01-01') == 'year'


def test_tag_key_charset_boundaries():
    # Uppercase X is neither a key-initial nor a key-char (mutants adding 'X').
    assert m.suffixtag_reason('[Xk=v]') == 'key.initial'
    assert m.suffixtag_reason('[kX=v]') == 'key.char'


def test_time_and_offset_range_boundaries():
    assert m.time_reason('23:59:59') == 'ok'
    assert m.time_reason('24:00:00') == 'hour.range'
    assert m.time_reason('00:60:00') == 'minute.range'
    assert m.offset_reason('+23:59') == 'ok'
    assert m.offset_reason('-23:59') == 'ok'
    assert m.offset_reason('+24:00') == 'hour.range'
    assert m.offset_reason('+00:60') == 'minute.range'


def test_offset_z_check_uses_first_character():
    # A trailing Z/z inside a numeric offset is a minute digit error, not shape.
    assert m.offset_reason('+05:0Z') == 'minute'
    assert m.offset_reason('+05:0z') == 'minute'


def test_numoffset_colon_shape_via_tzsuffix():
    assert m.tzsuffix_reason('[+0500x]') == 'offset.shape'


def test_tag_eq_missing_and_multi_eq_paths():
    assert m.suffixtag_reason('[abc]') == 'eq.missing'
    assert m.suffixtag_reason('[a=b=c]') == 'value.char'


def test_unclosed_brackets_report_close_reasons():
    assert m.suffix_reason('[abc') == 'tz.close'
    assert m.suffix_reason('[u=UTC][ab') == 'tag.close'


def test_critical_tag_in_first_suffix_position():
    assert m.ixdtf_reason('2026-01-01T00:00:00Z[!a=b]') == 'ok'
    assert m.suffix_reason('[!=b]') == 'tag.key.empty'


def test_leading_bracket_is_not_a_datetime():
    assert m.ixdtf_reason('[2026-01-01T00:00:00Z') == 'datetime.shape'



def test_audit_rev0_survivor_pins_runtime_built():
    # Witnesses for the 10 killable rev0 sweep survivors from the independent
    # audit (9 sites). Every input is built at runtime from fragments so no
    # source literal is interned; each pins the ORIGINAL behavior and fails
    # under the named mutant.
    jan = '2020-' + '01' + '-' + '31'
    mar = '2020-' + '03' + '-' + '31'
    apr = '2020-' + '04' + '-' + '30'
    assert m.date_reason(jan) == 'ok'   # L117 mo == 2 -> <= would read Jan as 29-day Feb
    assert m.date_reason(mar) == 'ok'   # L117 mo == 2 -> >=
    assert m.date_reason(apr) == 'ok'   # L117 mo == 2 -> >=
    sp = ' ' + '00:00'
    assert m.offset_reason(sp) == 'sign'  # L178 != -> > at cols 12 and 28
    brace = '2020-02-29T23:59:59' + '{' + '+05:00'
    assert m.datetime_reason(brace) == 'time.frac.dot'  # L211 != -> < at col 41
    spc = '2020-02-29T23:59:59' + ' ' + '+05:00'
    assert m.datetime_reason(spc) == 'time.frac.dot'    # L211 != -> < at col 57
    das = '2020-02-29T23:59:59' + ' ' + '-' + '05:00'
    assert m.datetime_reason(das) == 'time.frac.dot'    # L211 != -> < at col 73
    spx = '[' + ' ' + 'x' + ']'
    assert m.tzsuffix_reason(spx) == 'name.part.initial'  # L294 == -> <= at cols 15 and 33
    longtag = '[' + 'k' + '=' + 'a' * 300 + '-' + '-' + 'b' + ']'
    assert m.suffixtag_reason(longtag) == 'value.empty'   # L345 k == start -> is, k > 256

def test_tzsuffix_numoffset_range_boundaries():
    # The time-zone bracket offset uses the same 00-23 / 00-59 ranges.
    assert m.tzsuffix_reason('[+23:59]') == 'ok'
    assert m.tzsuffix_reason('[-23:59]') == 'ok'
    assert m.tzsuffix_reason('[+24:00]') == 'offset.hour.range'
    assert m.tzsuffix_reason('[+00:60]') == 'offset.minute.range'


def test_xcmp_cross_product_kill_pins():
    # Cross-product comparison sweep: pins for the eight killable survivor sites.
    # L313: suffixtag open-bracket check is !=, not > (a char below '[' must still fail).
    assert m.suffixtag_reason('+' + 'k=v]') == 'open'
    # L315: suffixtag close-bracket check is !=, not > (a char below ']' must still fail).
    assert m.suffixtag_reason('[k=v' + '+') == 'close'
    # L258: numoffset length check is !=, not < (an over-long body must fail).
    assert m._numoffset_shape('+' + '00:000') == 'shape'
    # L260: both sign checks are !=, not < ('0' sorts above '+' and '-').
    assert m._numoffset_shape('0' + '00:00') == 'sign'
    # L262: colon check is !=, not < ('a' sorts above ':').
    assert m._numoffset_shape('+00' + 'a' + '00') == 'shape'
    # L356: _find_close loop bound is <, not is not, past the 256-entry small-int cache.
    assert m.suffix_reason('[k=a]' * 60 + '[' + 'a' * 300) == 'tag.close'
    # L367: tz-branch entry check is ==, not <= (a char below '[' is plain suffix text).
    assert m.suffix_reason('+' + 'a') == 'suffix.char'


def test_empty_suffix_value_reason_is_pinned_through_every_layer():
    # a suffix tag whose value part is entirely empty reports value.empty (key checks come first)
    for tag in ('[ab=]', '[!ab=]', '[u-ca=]', '[ab=-]', '[ab=a-]', '[ab=-a]'):
        assert m.suffixtag_reason(tag) == 'value.empty', tag
        assert m.suffix_reason(tag) == 'tag.value.empty', tag
    assert m.suffixtag_reason('[1b=]') == 'key.initial'
    assert m.suffixtag_reason('[a!=]') == 'key.char'
    assert m.suffixtag_reason('[ab=a]') == 'ok'
    assert m.suffixtag_reason('[a=]') == 'shape'
    assert m.suffix_reason('[Europe/Paris][u-ca=]') == 'tag.value.empty'
    assert m.suffix_reason('[u-ca=a][u-ca=]') == 'tag.value.empty'


def test_leap_second_boundary_with_lowercase_z_and_an_empty_value_suffix():
    for z in ('z', 'Z'):
        for t in ('T', 't'):
            base = '2026-10-22' + t + '23:59:'
            assert m.ixdtf_reason(base + '60' + z + '[u-ca=]') == 'tag.value.empty'
            assert m.ixdtf_reason(base + '60' + z + '[!u-ca=]') == 'tag.value.empty'
            assert m.ixdtf_reason(base + '59' + z + '[u-ca=]') == 'tag.value.empty'
            assert m.ixdtf_reason(base + '60' + z + '[u-ca=a]') == 'ok'
            assert m.ixdtf_reason(base + '61' + z + '[u-ca=]') == 'datetime.time.second.range'
            assert m.ixdtf_reason(base + '61' + z + '[u-ca=a]') == 'datetime.time.second.range'
    assert m.ixdtf_reason('2026-10-22T24:59:60z[u-ca=]') == 'datetime.time.hour.range'
    assert m.ixdtf_reason('2026-10-22T23:59:60z[Europe/Paris][u-ca=]') == 'tag.value.empty'
    assert m.ixdtf_reason('2026-10-22T23:59:60z[u-ca=a][u-ca=]') == 'tag.value.empty'
    for w in ('2026-10-22T23:59:60z[u-ca=]', '2026-10-22T23:59:60Z[!u-ca=]'):
        assert run('ixdtf_tags', w) == E('ixdtf_tags', 'bad_value:value.ixdtf')
    assert m.ixdtf_tags('2026-10-22T23:59:60z[u-ca=a]') == ('2026-10-22T23:59:60z', None, ((False, 'u-ca', ('a',)),))
