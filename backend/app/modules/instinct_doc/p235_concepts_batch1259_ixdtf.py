r"""p235 concepts batch 1259 (rev 0): RFC 9557, Date and Time on the Internet: Timestamps with Additional Information - the Internet Extended Date/Time Format (IXDTF) as a grammar over caller-supplied text: the RFC 3339 date-time core it imports (re-derived here from the live RFC 3339 sections 5.6 and 5.7), the section 4.1 suffix grammar (time-zone tag, suffix tags, critical flag), and the section 3 key and case rules. Pure functions; no retrieval, no network, no clock, no calendar arithmetic, no registry lookups. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it carries no timestamp semantics, consults no tz database, no leap-second table and no calendar registry, and defines no format.

LIVE SOURCES (fetched 2026-10-22; quotes below are verbatim from these files, mechanically matched with whitespace collapsed):
- RFC 9557 text, rfc-editor (39113 bytes, sha256 87fa632cd75d13aa441859da635ed6618f66d203fe71a30fa85afedbeb149e85).
- RFC 3339 text, rfc-editor (35064 bytes, sha256 9ab2b8864a85dca73a88f49b0927bc7bc85f596926e4fd1890905777924e700a), for the imported date-time core and the section 5.7 restriction texts.
- rfc-editor info page for RFC 9557 (468497 bytes, sha256 c585df7162898aa21dde9a7856da61aef1e25c7ff153f6f42b8293d7d9558fe9): it lists Updates: RFC 3339, and shows no Obsoletes entry, no Obsoleted by entry and no Updated by entry. CLAIMS current is still False.
- The full rfc-editor errata index (11775016 bytes, sha256 23fe2627c26acf3fe70087763fefce39ec9cb5cdfaaaf51977742e844929762c) contains exactly one RFC 9557 record (count from errata.json and not independently confirmed): EID 8192, status Rejected, type Editorial, section 3.4 (a rejected hyphenation note about "critical flag"; no technical content).

SOURCED grammar (RFC 9557 section 4.1): "date-time-ext     = date-time suffix" "suffix            = [time-zone] *suffix-tag"
"time-zone         = "[" critical-flag time-zone-name / time-numoffset "]"" "suffix-tag        = "[" critical-flag suffix-key "=" suffix-values "]"" "critical-flag     = [ "!" ]"
"time-zone-name    = time-zone-part *("/" time-zone-part)" "time-zone-part    = time-zone-initial *time-zone-char ; but not "." or ".."" "time-zone-initial = ALPHA / "." / "_"" "time-zone-char    = time-zone-initial / DIGIT / "-" / "+"" "key-initial       = lcalpha / "_"" "suffix-key        = key-initial *key-char" "suffix-value      = 1*alphanum" "suffix-values     = suffix-value *("-" suffix-value)" "lcalpha           = %x61-7A" "alphanum          = ALPHA / DIGIT"

SOURCED core (RFC 3339 section 5.6, imported by RFC 9557): "date-fullyear   = 4DIGIT" "date-month      = 2DIGIT  ; 01-12" "date-mday       = 2DIGIT  ; 01-28, 01-29, 01-30, 01-31 based on ; month/year" "time-hour       = 2DIGIT  ; 00-23" "time-minute     = 2DIGIT  ; 00-59" "time-second     = 2DIGIT  ; 00-58, 00-59, 00-60 based on leap second ; rules" "time-secfrac    = "." 1*DIGIT" "time-numoffset  = ("+" / "-") time-hour ":" time-minute" "time-offset     = "Z" / time-numoffset" "partial-time    = time-hour ":" time-minute ":" time-second [time-secfrac]" "full-date       = date-fullyear "-" date-month "-" date-mday" "full-time       = partial-time time-offset" "date-time       = full-date "T" full-time"

DECISIONS AND NOT_CLAIMED:
1. Case. "Per [ABNF] and ISO8601, the "T" and "Z" characters in this syntax may alternatively be lower case "t" or "z" respectively." Both "T"/"t" and "Z"/"z" are accepted. Keys are lowercase by grammar: "Keys are lowercase only.  Values are case-sensitive unless otherwise specified." Values are compared as grammar characters only; no case folding anywhere.
2. Separator. Only "T"/"t" is accepted between date and time. The space alternative is an application-level choice - "Applications using this syntax may choose, for the sake of readability, to specify a full-date and full-time separated by (say) a space character." - and is NOT_CLAIMED here: a space separator reports sep.t.
3. Leap seconds. time-second accepts 00-60 grammatically; whether a given instant actually had a leap second ("The grammar element time-second may have the value "60" at the end of months in which a leap second occurs") is a table lookup and is NOT_CLAIMED. Hour 24 is rejected: "this profile of ISO 8601 only allows values between "00" and "23" for the hour in order to reduce confusion."
4. Leap years. date-mday maxima follow section 5.7 ("02            February, leap year  29" and the rest of the table): February has 29 days in years divisible by 4 but not by 100 unless also divisible by 400.
5. Time zone names. tzname checks the grammar only ("time-zone-part    = time-zone-initial *time-zone-char ; but not "." or "..""), including the exclusion in "The ABNF definition of time-zone-part matches "." and "..", which are both explicitly excluded (see the note below on time-zone-part)." The 14-character platform limit is deliberately not enforced: "over the length, the time-zone-part production in Figure 3 is | deliberately permissive." Whether the name exists in any tz database is NOT_CLAIMED.
6. Suffix handling. Tags are elective by default and critical when flagged: "The recipient is free to ignore any suffix tag included in an IXDTF string." "A critical suffix tag is indicated by following its opening bracket with an exclamation mark (see critical-flag in Section 4.1)." Rejection of critical tags, inconsistency handling between time-offset and time zone (section 3.4), and the duplicate-key first-wins rule ("does not want to perform additional processing on this inconsistency MUST choose the first suffix that has that key") are recipient behaviors and are NOT_CLAIMED: ixdtf_tags returns the tags in order, flagged, and applies no dedup. Experimental underscore keys ("such keys MUST NOT be used for interchange and MUST be rejected by implementations not specifically configured to take part in such an experiment.") are accepted as grammar; rejecting them is NOT_CLAIMED.
7. Z semantics. The section 2.2 update ("If the time in UTC is known, but the offset to local time is | unknown, this can be represented with an offset of "Z".") and the -00:00 deprecation note are semantics; both Z and -00:00 are accepted syntactically, and their semantic difference is NOT_CLAIMED.
8. Offsets inside a time-zone bracket are checked with the same ranges as a time-offset (hour 00-23, minute 00-59); RFC 9557 imports time-numoffset for both positions.
9. Caps (OURS, all raising): _LEN_CAP 1024 characters per input; _TAGS_CAP 128 suffix tags (a tag is at least five characters, so 129 tags fit under _LEN_CAP); _VALUES_CAP 64 hyphen-separated items per suffix-values; _PARTS_CAP 64 slash-separated parts per time-zone-name; _FRAC_CAP 64 digits per time-secfrac. The grammar itself is unbounded in these five places.

FUNCTIONS, in this order: date_reason, time_reason, offset_reason, datetime_reason, tzname_reason, tzsuffix_reason, suffixtag_reason, suffix_reason, ixdtf_reason, ixdtf_tags. The reason functions return the string "ok" or a reason string; ixdtf_tags returns (head, tz, tags) where head is the date-time portion, tz is None or (critical, body), and tags is a tuple of (critical, key, values) with values a tuple of the hyphen-separated items, in order. Errors are ValueError with the text P235:<function>:<code>, where <function> is the owning function and <code> is bad_type:value (non-str input), bad_value:value.length (over _LEN_CAP), bad_value:frac.length, bad_value:parts.length, bad_value:values.length, bad_value:tags.length, or bad_value:value.ixdtf (ixdtf_tags on an invalid string).

REASONS, in check order (the first failure decides):
- date_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (not exactly 10 characters or hyphens misplaced), year (non-digit), month (non-digit), month.range (not 01-12), mday (non-digit), mday.range (outside the month/year maximum); ok.
- time_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (fewer than 8 characters or colons misplaced), hour (non-digit), hour.range (over 23), minute (non-digit), minute.range (over 59), second (non-digit), second.range (over 60), frac.dot (extra text not starting with "."), frac.empty, bad_value:frac.length (raise), frac.char (non-digit); ok.
- offset_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (empty, or "Z"/"z" with trailing text, or not exactly 6 characters, or colon misplaced), sign (not "+" or "-"), hour (non-digit), hour.range (over 23), minute (non-digit), minute.range (over 59); ok. A lone "Z" or "z" is ok.
- datetime_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (fewer than 20 characters), date.<date_reason reason>, sep.t, time.<time_reason reason>, offset.<offset_reason reason>; ok. A nested cap raise propagates under the owning function's name. The time portion runs to the first "Z", "z", "+" or "-" after the separator; a missing offset reports shape when the string is under 20 characters, else offset.shape.
- tzname_reason: bad_type:value (raise), bad_value:value.length (raise); then empty, bad_value:parts.length (raise), then per part left to right: part.empty, part.dot (exactly "." or ".."), part.initial, part.char; ok.
- tzsuffix_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (fewer than 3 characters), open, close, empty (only a critical flag inside), then for a body starting "+" or "-": offset.<shape, sign, hour, hour.range, minute, minute.range>, else name.<tzname_reason reason>; ok. A nested cap raise propagates under the owning function's name.
- suffixtag_reason: bad_type:value (raise), bad_value:value.length (raise); then shape (fewer than 5 characters), open, close, eq.missing, key.empty, key.initial, key.char, value.empty, bad_value:values.length (raise), value.empty (empty item between hyphens), value.char; ok.
- suffix_reason: bad_type:value (raise), bad_value:value.length (raise); ok on the empty string; then tz.close or tz.<tzsuffix_reason reason> for the optional leading time-zone, then per tag left to right: bad_value:tags.length (raise), suffix.char (text outside brackets), tag.close, tag.<suffixtag_reason reason>; ok.
- ixdtf_reason: bad_type:value (raise), bad_value:value.length (raise); then datetime.<datetime_reason reason> for the portion before the first "[", then the suffix_reason reasons for the rest; ok. A bare RFC 3339 date-time is valid IXDTF ("date-time-ext     = date-time suffix" with "suffix            = [time-zone] *suffix-tag" both optional).
- ixdtf_tags: bad_type:value (raise), bad_value:value.length (raise), bad_value:value.ixdtf (raise, when ixdtf_reason would not return ok, including any cap raise propagating first under its owning name).

OUTPUT ORDER: reason strings are the exact dotted codes listed above; ixdtf_tags emits the time-zone first, then the suffix tags in input order, each critical flag preceding its key."""
from importlib.util import find_spec

SCOPE = "RFC 9557 over caller-supplied text: the Internet Extended Date/Time Format (IXDTF) grammar - the RFC 3339 date-time core it imports (full-date, partial-time, time-offset, date-time, re-derived here from the RFC 3339 sections 5.6 and 5.7 texts) plus the section 4.1 suffix grammar (time-zone tag, suffix tags, critical flag), the section 3 key/case rules, and validation of the same. Pure functions; no retrieval, no network, no clock, no calendars, no registries."
NOT_CLAIMED = ('standard', 'authority', 'certification', 'currency', 'completeness',
               'semantics', 'registry', 'leap-second table', 'tz database', 'calendar projection')
CLAIMS = {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False}
ADJACENT = ('RFC 3339 grammar itself (b970, b1028 cover it standalone; here it is re-derived from the live RFC 3339 text as the imported core of IXDTF, not reused)',
            'RFC 5322 date-time (a different grammar, named only by the section 2.2 note)',
            'the IANA Time Zone Database and the u-ca Unicode calendar registry (names and keys are checked as grammar only)')

_LEN_CAP = 1024
_TAGS_CAP = 128
_VALUES_CAP = 64
_PARTS_CAP = 64
_FRAC_CAP = 64

_DIGITS = '0123456789'
_UCALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
_LCALPHA = 'abcdefghijklmnopqrstuvwxyz'
_ALPHA = _UCALPHA + _LCALPHA
_ALNUM = _ALPHA + _DIGITS
_TZ_INITIAL = _ALPHA + '._'
_TZ_CHAR = _TZ_INITIAL + _DIGITS + '-+'
_KEY_INITIAL = _LCALPHA + '_'
_KEY_CHAR = _KEY_INITIAL + _DIGITS + '-'

_MDAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

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


def _is_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _digits(s, i, n):
    j = i
    while j < i + n:
        if s[j] not in _DIGITS:
            return -1
        j += 1
    return int(s[i:i + n])


def date_reason(v):
    fail = make_fail('date_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    if len(v) != 10:
        return 'shape'
    if v[4] != '-' or v[7] != '-':
        return 'shape'
    y = _digits(v, 0, 4)
    if y < 0:
        return 'year'
    mo = _digits(v, 5, 2)
    if mo < 0:
        return 'month'
    if mo < 1 or mo > 12:
        return 'month.range'
    d = _digits(v, 8, 2)
    if d < 0:
        return 'mday'
    top = _MDAYS[mo - 1]
    if mo == 2 and _is_leap(y):
        top = 29
    if d < 1 or d > top:
        return 'mday.range'
    return 'ok'


def time_reason(v):
    fail = make_fail('time_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    if len(v) < 8:
        return 'shape'
    if v[2] != ':' or v[5] != ':':
        return 'shape'
    hh = _digits(v, 0, 2)
    if hh < 0:
        return 'hour'
    if hh > 23:
        return 'hour.range'
    mi = _digits(v, 3, 2)
    if mi < 0:
        return 'minute'
    if mi > 59:
        return 'minute.range'
    ss = _digits(v, 6, 2)
    if ss < 0:
        return 'second'
    if ss > 60:
        return 'second.range'
    if len(v) == 8:
        return 'ok'
    if v[8] != '.':
        return 'frac.dot'
    f = v[9:]
    if len(f) < 1:
        return 'frac.empty'
    if len(f) > _FRAC_CAP:
        fail('bad_value:frac.length')
    for c in f:
        if c not in _DIGITS:
            return 'frac.char'
    return 'ok'


def offset_reason(v):
    fail = make_fail('offset_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    if len(v) < 1:
        return 'shape'
    if v[0] == 'Z' or v[0] == 'z':
        if len(v) != 1:
            return 'shape'
        return 'ok'
    if len(v) != 6:
        return 'shape'
    if v[0] != '+' and v[0] != '-':
        return 'sign'
    if v[3] != ':':
        return 'shape'
    hh = _digits(v, 1, 2)
    if hh < 0:
        return 'hour'
    if hh > 23:
        return 'hour.range'
    mi = _digits(v, 4, 2)
    if mi < 0:
        return 'minute'
    if mi > 59:
        return 'minute.range'
    return 'ok'


def datetime_reason(v):
    fail = make_fail('datetime_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    if len(v) < 20:
        return 'shape'
    rd = date_reason(v[:10])
    if rd != 'ok':
        return 'date.' + rd
    if v[10] != 'T' and v[10] != 't':
        return 'sep.t'
    i = 11
    n = len(v)
    j = i
    while j < n and v[j] != 'Z' and v[j] != 'z' and v[j] != '+' and v[j] != '-':
        j += 1
    rt = time_reason(v[i:j])
    if rt != 'ok':
        return 'time.' + rt
    ro = offset_reason(v[j:])
    if ro != 'ok':
        return 'offset.' + ro
    return 'ok'


def _tzpart_reason(p):
    if len(p) < 1:
        return 'part.empty'
    if p == '.' or p == '..':
        return 'part.dot'
    if p[0] not in _TZ_INITIAL:
        return 'part.initial'
    for c in p[1:]:
        if c not in _TZ_CHAR:
            return 'part.char'
    return 'ok'


def tzname_reason(v):
    fail = make_fail('tzname_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    if len(v) < 1:
        return 'empty'
    start = 0
    nparts = 0
    for k in range(len(v) + 1):
        if k == len(v) or v[k] == '/':
            nparts += 1
            if nparts > _PARTS_CAP:
                fail('bad_value:parts.length')
            r = _tzpart_reason(v[start:k])
            if r != 'ok':
                return r
            start = k + 1
    return 'ok'


def _numoffset_shape(s):
    if len(s) != 6:
        return 'shape'
    if s[0] != '+' and s[0] != '-':
        return 'sign'
    if s[3] != ':':
        return 'shape'
    hh = _digits(s, 1, 2)
    if hh < 0:
        return 'hour'
    if hh > 23:
        return 'hour.range'
    mi = _digits(s, 4, 2)
    if mi < 0:
        return 'minute'
    if mi > 59:
        return 'minute.range'
    return 'ok'


def tzsuffix_reason(v):
    fail = make_fail('tzsuffix_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    if len(v) < 3:
        return 'shape'
    if v[0] != '[':
        return 'open'
    if v[-1] != ']':
        return 'close'
    body = v[1:-1]
    if body[:1] == '!':
        body = body[1:]
    if len(body) < 1:
        return 'empty'
    if body[0] == '+' or body[0] == '-':
        r = _numoffset_shape(body)
        if r != 'ok':
            return 'offset.' + r
        return 'ok'
    r = tzname_reason(body)
    if r != 'ok':
        return 'name.' + r
    return 'ok'


def suffixtag_reason(v):
    fail = make_fail('suffixtag_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    if len(v) < 5:
        return 'shape'
    if v[0] != '[':
        return 'open'
    if v[-1] != ']':
        return 'close'
    body = v[1:-1]
    if body[:1] == '!':
        body = body[1:]
    eq = -1
    for k in range(len(body)):
        if body[k] == '=':
            eq = k
            break
    if eq < 0:
        return 'eq.missing'
    key = body[:eq]
    if len(key) < 1:
        return 'key.empty'
    if key[0] not in _KEY_INITIAL:
        return 'key.initial'
    for c in key[1:]:
        if c not in _KEY_CHAR:
            return 'key.char'
    vals = body[eq + 1:]
    if len(vals) < 1:
        return 'value.empty'
    start = 0
    nitems = 0
    for k in range(len(vals) + 1):
        if k == len(vals) or vals[k] == '-':
            nitems += 1
            if nitems > _VALUES_CAP:
                fail('bad_value:values.length')
            if k == start:
                return 'value.empty'
            for c in vals[start:k]:
                if c not in _ALNUM:
                    return 'value.char'
            start = k + 1
    return 'ok'


def _find_close(v, i):
    k = i + 1
    while k < len(v):
        if v[k] == ']':
            return k
        k += 1
    return -1


def _scan_suffix(v, i, fail):
    tags = []
    tz = None
    n = len(v)
    if i < n and v[i] == '[':
        k = _find_close(v, i)
        if k < 0:
            return ('tz.close', None, None)
        seg = v[i:k + 1]
        body = seg[1:-1]
        b2 = body[1:] if body[:1] == '!' else body
        has_eq = False
        for c2 in b2:
            if c2 == '=':
                has_eq = True
        if not has_eq:
            r = tzsuffix_reason(seg)
            if r != 'ok':
                return ('tz.' + r, None, None)
            tz = seg
            i = k + 1
    while i < n:
        if len(tags) >= _TAGS_CAP:
            fail('bad_value:tags.length')
        if v[i] != '[':
            return ('suffix.char', None, None)
        k = _find_close(v, i)
        if k < 0:
            return ('tag.close', None, None)
        seg = v[i:k + 1]
        r = suffixtag_reason(seg)
        if r != 'ok':
            return ('tag.' + r, None, None)
        tags += [seg]
        i = k + 1
    return ('ok', tz, tags)


def suffix_reason(v):
    fail = make_fail('suffix_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    if len(v) < 1:
        return 'ok'
    r, _tz, _tags = _scan_suffix(v, 0, fail)
    return r


def _split_ixdtf(v):
    n = len(v)
    i = 0
    while i < n and v[i] != '[':
        i += 1
    return v[:i], v[i:]


def ixdtf_reason(v):
    fail = make_fail('ixdtf_reason')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    head, tail = _split_ixdtf(v)
    rd = datetime_reason(head)
    if rd != 'ok':
        return 'datetime.' + rd
    r, _tz, _tags = _scan_suffix(tail, 0, fail)
    return r


def ixdtf_tags(v):
    fail = make_fail('ixdtf_tags')
    if type(v) is not str:
        fail('bad_type:value')
    if len(v) > _LEN_CAP:
        fail('bad_value:value.length')
    r = ixdtf_reason(v)
    if r != 'ok':
        fail('bad_value:value.ixdtf')
    head, tail = _split_ixdtf(v)
    _r, tz, tags = _scan_suffix(tail, 0, fail)
    out = []
    for seg in tags or []:
        body = seg[1:-1]
        crit = body[:1] == '!'
        if crit:
            body = body[1:]
        eq = 0
        while body[eq] != '=':
            eq += 1
        vals = body[eq + 1:]
        items = []
        start = 0
        for k in range(len(vals) + 1):
            if k == len(vals) or vals[k] == '-':
                items += [vals[start:k]]
                start = k + 1
        out += [(crit, body[:eq], tuple(items))]
    tzout = None
    if tz is not None:
        body = tz[1:-1]
        crit = body[:1] == '!'
        if crit:
            body = body[1:]
        tzout = (crit, body)
    return (head, tzout, tuple(out))
