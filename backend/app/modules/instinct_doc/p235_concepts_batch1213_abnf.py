r"""P235 b1213 bounded exact RFC 5234 ABNF rulelist syntax (Sections 3 and 4) with RFC 7405 %s/%i string
prefixes: parse and validate only.

Pure functions on bytes, no clock, no network, no regex: rulelist_parse and rulelist_is_valid.

Primary sources (fetched fresh and read live 2026-10-21): RFC 5234 Augmented BNF for Syntax Specifications: ABNF,
https://www.rfc-editor.org/rfc/rfc5234.txt, Section 3 (operators) and Section 4 (ABNF definition of ABNF), and
RFC 7405 Case-Sensitive String Support in ABNF, https://www.rfc-editor.org/rfc/rfc7405.txt, Section 2.
Quotes: 'rulelist       =  1*( rule / (*c-wsp c-nl) )' 'rule           =  rulename defined-as elements c-nl'
'rulename       =  ALPHA *(ALPHA / DIGIT / "-")' 'defined-as     =  *c-wsp ("=" / "=/") *c-wsp'
'elements       =  alternation *c-wsp' 'c-wsp          =  WSP / (c-nl WSP)' 'c-nl           =  comment / CRLF'
'comment        =  ";" *(WSP / VCHAR) CRLF' '*(*c-wsp "/" *c-wsp concatenation)'
'concatenation  =  repetition *(1*c-wsp repetition)' 'repetition     =  [repeat] element'
'repeat         =  1*DIGIT / (*DIGIT "*" *DIGIT)' 'element        =  rulename / group / option /'
'char-val / num-val / prose-val' 'group          =  "(" *c-wsp alternation *c-wsp ")"'
'option         =  "[" *c-wsp alternation *c-wsp "]"' 'char-val       =  DQUOTE *(%x20-21 / %x23-7E) DQUOTE'
'num-val        =  "%" (bin-val / dec-val / hex-val)' 'bin-val        =  "b" 1*BIT'
'prose-val      =  "<" *(%x20-3D / %x3F-7E) ">"' 'case-sensitive-string' '[ "%i" ] quoted-string'
'"%s" quoted-string' 'quoted-string  =  DQUOTE *(%x20-21 / %x23-7E) DQUOTE'.
Errata (read live 2026-10-21, from the full index https://www.rfc-editor.org/errata.json): RFC 5234 has twelve
records and RFC 7405 has one. EID 2968 (Verified, Technical, 4) changes elements to 'alternation *WSP' and is
APPLIED: trailing whitespace after the last element is plain WSP, so the grammar is not ambiguous. EID 3076
(Verified, Technical, 4) changes rulelist to '1*( rule / (*WSP c-nl) )' and is APPLIED: a blank or comment line
between rules is WSP then comment-or-newline. EID 2820 (Held for Document Update, Editorial, 4) only rewords the
prose-val comment from 'without angles' to 'without ">"'; the printed range is unchanged and is what is
implemented here, so '<' (%x3C) is allowed inside a prose-val and only '>' is excluded. EID 2914 (Held for
Document Update, Editorial, GLOBAL) notes that the Section 4 grammar is recursive; informational only. EID 6172
(Held for Document Update, Editorial, Appendix B) and EID 6173 (Held for Document Update, Editorial, 3.6) fix
wording; informational only. EID 1423 (Rejected, Technical, 4), EID 3096 (Rejected, Technical, B.1), EID 4040
(Rejected, Technical, B.1), EID 5110 (Rejected, Technical, B.1.), EID 4361 (Rejected, Editorial, 2.1), EID 4564 (Rejected, Technical, 3.8) and, for
RFC 7405, EID 5334 (Rejected, Technical, 2.2) are not applied.

CONVENTIONS (OURS, UNSOURCED where stated). Input is exact bytes, never str, bytearray or a bytes subclass, at
most 4096 bytes (MAX_DATA); a longer input is refused before any scan. Only HTAB, CR, LF and printable ASCII
%x20-7E may appear; any other byte raises bad_value:char. Line endings must be strict CRLF pairs; a lone CR or LF
raises bad_value:nl. Every rule must end with a comment or CRLF, so the last line of input must be CRLF
terminated; where a rule ending is missing or junk stands where the ending belongs, bad_value:crlf is raised.
Empty input raises bad_value:rulelist; an input of only blank lines and comment lines is valid (the grammar
allows it) and parses to the empty tuple. A rule must begin with a letter in column 0; a line that begins with
WSP and is then not a blank or comment line raises bad_value:rulename. Group and option nesting deeper than 64
(MAX_DEPTH) raises bad_value:depth. The base letters of num-val and the RFC 7405 prefixes are string literals of
the grammar and string literals are case-insensitive, so %X41, %B101, %D13, %S"a" and %I"a" are accepted. A
range whose low value is above its high value (for example %x30-20) is valid syntax and is accepted as written;
this is a grammar unit and does not judge values. No str, decode, encode, int, isdigit, strip or regex is used on
input; number values are accumulated digit by digit. rulelist_parse(data) returns a tuple with one
(rulename, incremental, tree) per rule, in order; blank and comment lines are consumed but not returned. In a
tree, a rulename is ('name', bytes) exactly as written, a string is ('str', kind, bytes) with kind 'i' or 's' and
the quotes removed and no case folding, a numeric value is ('num', base, value) with base 'b', 'd' or 'x' and
value ('seq', (v, ...)) or ('range', lo, hi) as integers, a prose value is ('prose', bytes) without the angle
brackets, a group is ('grp', inner), an option is ('opt', inner), a repetition is ('rep', lo, hi, element) with
hi None for no upper bound and a bare count n as ('rep', n, n, element), an alternation of two or more parts is
('alt', parts) and a concatenation of two or more parts is ('cat', parts); a singleton alternation or
concatenation collapses to its single part. rulelist_is_valid(data) returns exactly True or False and refuses
only a wrong type. Check order: bad_type:data, bad_value:data.length, then a whole-input scan in position order
raising bad_value:nl or bad_value:char, then a left-to-right structural scan raising bad_value:rulelist,
bad_value:rulename, bad_value:defined_as, bad_value:element, bad_value:numval, bad_value:charval,
bad_value:proseval, bad_value:group, bad_value:option, bad_value:depth or bad_value:crlf. Errors are ValueError
with message P235:<function>:<code>. Matching input against a described grammar, the Appendix B core rules as
data, terminal value semantics and prose-val semantics are not implemented.

ADJACENCY, by name only: the Appendix B core rules of RFC 5234 are referenced as names only, RFC 7405 Section
2.1 matching semantics, and every unit that quotes ABNF to define its own syntax belong to other units and were
not read beyond the sections named above. SCOPE and NOT_CLAIMED are the module constants below.
"""

SCOPE = ('PARTIAL: RFC 5234 Section 3 and 4 ABNF rulelist grammar with the RFC 7405 Section 2.2 %s and %i '
         'string prefixes on whole bytes values, parse and is_valid, pure functions, with the OURS choices '
         'stated in the docstring')

NOT_CLAIMED = (
    'matching any input against a grammar described by a rulelist',
    'the Appendix B core rules as data or their semantics',
    'terminal value, prose-val or case-matching semantics',
    'global novelty',
    'production readiness')

CLAIMS = False

ADJACENT = (
    'the Appendix B core rules of RFC 5234, RFC 7405 Section 2.1 matching semantics and every unit that '
    'quotes ABNF for its own syntax are covered elsewhere and were not read beyond the sections named in '
    'the docstring',)

MAX_DATA = 4096
MAX_DEPTH = 64

try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry':
        raise
    import importlib.util as _iu
    if _iu.find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:
        raise
    def make_fail(name):
        def fail(code):
            raise ValueError('P235:%s:%s' % (name, code))
        return fail


_ALPHA = b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
_DIGIT = b'0123456789'
_BIT = b'01'
_HEXD = b'0123456789abcdefABCDEF'


class _No(Exception):
    pass


def _no(code):
    raise _No(code)


def _is_wsp(d, i, n):
    return i < n and (d[i] == 32 or d[i] == 9)


def _cnl_end(d, i, n):
    # if a c-nl (comment or CRLF) starts at i, return the index just after it, else -1
    if i < n and d[i] == 59:
        k = d.find(b'\r\n', i)
        if k < 0:
            return -1
        return k + 2
    if d[i:i + 2] == b'\r\n':
        return i + 2
    return -1


def _ws(d, i, n):
    # skip *c-wsp starting at i
    while True:
        if _is_wsp(d, i, n):
            i += 1
            continue
        j = _cnl_end(d, i, n)
        if j >= 0 and _is_wsp(d, j, n):
            i = j + 1
            continue
        return i


def _estart(d, i, n):
    if i >= n:
        return False
    c = d[i]
    if c == 40 or c == 91 or c == 34 or c == 37 or c == 60 or c == 42:
        return True
    if _ALPHA.find(d[i:i + 1]) >= 0:
        return True
    return _DIGIT.find(d[i:i + 1]) >= 0


def _rulename(f, d, i, n):
    # callers guarantee d[i] is ALPHA
    j = i + 1
    while j < n and (_ALPHA.find(d[j:j + 1]) >= 0 or _DIGIT.find(d[j:j + 1]) >= 0 or d[j] == 45):
        j += 1
    return d[i:j], j


def _num(base, text):
    v = 0
    for ch in text:
        if ch <= 57:
            dgt = ch - 48
        elif ch <= 70:
            dgt = ch - 55
        else:
            dgt = ch - 87
        v = v * base + dgt
    return v


def _quoted(f, d, i, n, kind):
    # d[i] is the opening DQUOTE; chars are %x20-21 / %x23-7E
    j = i + 1
    while j < n and d[j] != 34:
        b = d[j]
        if b < 32 or b > 126:
            f('bad_value:charval')
        j += 1
    if j >= n:
        f('bad_value:charval')
    return ('str', kind, d[i + 1:j]), j + 1


def _numval(f, d, i, n):
    # d[i] is '%'; returns (tree, next index)
    nxt = d[i + 1:i + 2]
    if nxt == b's' or nxt == b'S':
        if d[i + 2:i + 3] != b'"':
            f('bad_value:charval')
        return _quoted(f, d, i + 2, n, 's')
    if nxt == b'i' or nxt == b'I':
        if d[i + 2:i + 3] != b'"':
            f('bad_value:charval')
        return _quoted(f, d, i + 2, n, 'i')
    if nxt == b'b' or nxt == b'B':
        base, dset, letter = 2, _BIT, 'b'
    elif nxt == b'd' or nxt == b'D':
        base, dset, letter = 10, _DIGIT, 'd'
    elif nxt == b'x' or nxt == b'X':
        base, dset, letter = 16, _HEXD, 'x'
    else:
        f('bad_value:numval')
    p = i + 2
    q = p
    while q < n and dset.find(d[q:q + 1]) >= 0:
        q += 1
    if q == p:
        f('bad_value:numval')
    segs = [d[p:q]]
    kind = None
    if q < n and d[q] == 46:
        kind = 'seq'
        while q < n and d[q] == 46:
            q += 1
            p = q
            while q < n and dset.find(d[q:q + 1]) >= 0:
                q += 1
            if q == p:
                f('bad_value:numval')
            segs.append(d[p:q])
    elif q < n and d[q] == 45:
        kind = 'range'
        q += 1
        p = q
        while q < n and dset.find(d[q:q + 1]) >= 0:
            q += 1
        if q == p:
            f('bad_value:numval')
        segs.append(d[p:q])
    vals = tuple(_num(base, s) for s in segs)
    if kind == 'range':
        return ('num', letter, ('range', vals[0], vals[1])), q
    return ('num', letter, ('seq', vals)), q


def _element(f, d, i, n, depth):
    if i >= n:
        f('bad_value:element')
    c = d[i]
    if c == 40:
        if depth >= MAX_DEPTH:
            f('bad_value:depth')
        j = _ws(d, i + 1, n)
        t, j = _alternation(f, d, j, n, depth + 1)
        j = _ws(d, j, n)
        if j >= n or d[j] != 41:
            f('bad_value:group')
        return ('grp', t), j + 1
    if c == 91:
        if depth >= MAX_DEPTH:
            f('bad_value:depth')
        j = _ws(d, i + 1, n)
        t, j = _alternation(f, d, j, n, depth + 1)
        j = _ws(d, j, n)
        if j >= n or d[j] != 93:
            f('bad_value:option')
        return ('opt', t), j + 1
    if c == 34:
        return _quoted(f, d, i, n, 'i')
    if c == 37:
        return _numval(f, d, i, n)
    if c == 60:
        j = i + 1
        while j < n and d[j] != 62:
            b = d[j]
            if b < 32 or b > 126:
                f('bad_value:proseval')
            j += 1
        if j >= n:
            f('bad_value:proseval')
        return ('prose', d[i + 1:j]), j + 1
    if _ALPHA.find(d[i:i + 1]) >= 0:
        name, j = _rulename(f, d, i, n)
        return ('name', name), j
    f('bad_value:element')


def _repetition(f, d, i, n, depth):
    lo = hi = None
    has = False
    if i < n and _DIGIT.find(d[i:i + 1]) >= 0:
        j = i
        while j < n and _DIGIT.find(d[j:j + 1]) >= 0:
            j += 1
        if j < n and d[j] == 42:
            lo = _num(10, d[i:j])
            k = j + 1
            while k < n and _DIGIT.find(d[k:k + 1]) >= 0:
                k += 1
            hi = _num(10, d[j + 1:k]) if k > j + 1 else None
            i = k
        else:
            lo = hi = _num(10, d[i:j])
            i = j
        has = True
    elif i < n and d[i] == 42:
        lo = 0
        k = i + 1
        while k < n and _DIGIT.find(d[k:k + 1]) >= 0:
            k += 1
        hi = _num(10, d[i + 1:k]) if k > i + 1 else None
        i = k
        has = True
    t, i = _element(f, d, i, n, depth)
    if has:
        return ('rep', lo, hi, t), i
    return t, i


def _concatenation(f, d, i, n, depth):
    t, i = _repetition(f, d, i, n, depth)
    reps = [t]
    while True:
        save = i
        j = _ws(d, i, n)
        if j == i:
            break
        if not _estart(d, j, n):
            i = save
            break
        t, i = _repetition(f, d, j, n, depth)
        reps.append(t)
    if len(reps) == 1:
        return reps[0], i
    return ('cat', tuple(reps)), i


def _alternation(f, d, i, n, depth):
    t, i = _concatenation(f, d, i, n, depth)
    alts = [t]
    while True:
        save = i
        j = _ws(d, i, n)
        if j < n and d[j] == 47:
            j = _ws(d, j + 1, n)
            t, i = _concatenation(f, d, j, n, depth)
            alts.append(t)
        else:
            i = save
            break
    if len(alts) == 1:
        return alts[0], i
    return ('alt', tuple(alts)), i


def _rule(f, d, i, n):
    name, i = _rulename(f, d, i, n)
    i = _ws(d, i, n)
    if i < n and d[i] == 61:
        if d[i + 1:i + 2] == b'/':
            incr = True
            i += 2
        else:
            incr = False
            i += 1
    else:
        f('bad_value:defined_as')
    i = _ws(d, i, n)
    t, i = _alternation(f, d, i, n, 0)
    while _is_wsp(d, i, n):
        i += 1
    j = _cnl_end(d, i, n)
    if j < 0:
        f('bad_value:crlf')
    return (name, incr, t), j


def _parse(f, d):
    n = len(d)
    i = 0
    while i < n:
        b = d[i]
        if b == 13:
            if i + 1 >= n or d[i + 1] != 10:
                f('bad_value:nl')
            i += 2
            continue
        if b == 10:
            f('bad_value:nl')
        if b != 9 and (b < 32 or b > 126):
            f('bad_value:char')
        i += 1
    items = []
    seen = 0
    i = 0
    while i < n:
        if _ALPHA.find(d[i:i + 1]) >= 0:
            t, i = _rule(f, d, i, n)
            items.append(t)
            seen += 1
        else:
            while i < n and (d[i] == 32 or d[i] == 9):
                i += 1
            j = _cnl_end(d, i, n)
            if j < 0:
                f('bad_value:rulename')
            i = j
            seen += 1
    if seen == 0:
        f('bad_value:rulelist')
    return tuple(items)


def _check(f, data):
    if type(data) is not bytes:
        f('bad_type:data')
    if len(data) > MAX_DATA:
        f('bad_value:data.length')
    return _parse(f, data)


def rulelist_parse(data):
    return _check(make_fail('rulelist_parse'), data)


def rulelist_is_valid(data):
    f = make_fail('rulelist_is_valid')
    if type(data) is not bytes:
        f('bad_type:data')
    try:
        _check(_no, data)
    except _No:
        return False
    return True
