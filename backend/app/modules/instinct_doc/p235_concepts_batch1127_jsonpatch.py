"""P235 b1127 bounded exact RFC 6901 JSON Pointer and RFC 6902 JSON Patch on parsed values.

Pure functions on parsed JSON values (exact dict, list, str, int, float, bool
and None), no JSON text, no clock, no network: pointer_parse, pointer_valid,
pointer_format, array_index and pointer_get for RFC 6901, and json_equal,
patch_valid and patch_apply for RFC 6902 with the six operations add, remove,
replace, move, copy and test.

Primary sources (fetched fresh and read live 2026-10-21): RFC 6901 JavaScript
Object Notation (JSON) Pointer, https://www.rfc-editor.org/rfc/rfc6901.txt,
Sections 3, 4, 5 and 7, and its info page https://www.rfc-editor.org/info/rfc6901
(Proposed Standard, April 2013); RFC 6902 JavaScript Object Notation (JSON)
Patch, https://www.rfc-editor.org/rfc/rfc6902.txt, Sections 3, 4, 5 and
Appendix A, and its info page https://www.rfc-editor.org/info/rfc6902
(Proposed Standard, April 2013).
Quotes: 'json-pointer = *( "/" reference-token )' 'reference-token = *( unescaped / escaped )' 'unescaped = %x00-2E / %x30-7D / %x7F-10FFFF' 'escaped = "~" ( "0" / "1" )' 'array-index = %x30 / ( %x31-39 *(%x30-39) )' 'It is an error condition if a JSON Pointer value does not conform to this syntax (see Section 7).' 'By performing the substitutions in this order, an implementation avoids the error of turning' 'No Unicode character normalization is performed.' 'note that leading zeros are not allowed' 'Note that the use of the "-" character to index an array will always result in such an error condition because by definition it refers to a nonexistent array element.' 'Operations are applied sequentially in the order they appear in the array.' 'Operation objects MUST have exactly one "op" member, whose value indicates the operation to perform.' 'Its value MUST be one of "add", "remove", "replace", "move", "copy", or "test"; other values are errors.' 'Additionally, operation objects MUST have exactly one "path" member.' 'Members that are not explicitly defined for the operation in question MUST be ignored' 'The operation object MUST contain a "value" member whose content specifies the value to be added.' 'The specified index MUST NOT be greater than the number of elements in the array.' 'If the "-" character is used to index the end of the array (see [RFC6901]), this has the effect of appending the value to the array.' 'The target location MUST exist for the operation to be successful.' 'The "from" location MUST exist for the operation to be successful.' 'The "from" location MUST NOT be a proper prefix of the "path" location; i.e., a location cannot be moved into one of its children.' 'The target location MUST be equal to the "value" value for the operation to be considered successful.' 'numbers: are considered equal if their values are numerically equal.' 'literals (false, true, and null): are considered equal if they are the same.' 'application of the entire patch document SHALL NOT be deemed successful.'
Errata (read live 2026-10-21, from the full index
https://www.rfc-editor.org/errata.json, because per-RFC pages can omit
records): RFC 6901, https://www.rfc-editor.org/errata/rfc6901, three records,
EID 3981 (Rejected, Technical, Section 3: double the slash instead of the ~1
escape, a change request), EID 5745 (Reported, Editorial, Section 5: the
"/i\\j" and "/k\"l" example strings) and EID 8314 (Reported, Technical, Section
5: the same example strings under RFC 8259 string escaping); none applied, and
this unit takes a pointer as an already unescaped str, as Section 5 says, so it
does no JSON string unescaping. RFC 6902, https://www.rfc-editor.org/errata/rfc6902,
six records, EID 4419 (Rejected, Editorial, A.14), EID 4460 (Rejected,
Editorial, 4.1), EID 4596 (Rejected, Technical, Global: an append operation, not
applied, so append is an unknown operation here), EID 4787 (Held for Document
Update, Technical, 4.2: the remove of the root is never specified, and it
proposes to forbid it; not applied as an RFC rule, but see the OURS refusal
below), EID 5239 (Rejected, Technical, A.16: the example is correct, an array
value is added as one element) and EID 6351 (Rejected, Technical, Global: a
previous member for reverse patches, not applied).

CONVENTIONS (OURS, UNSOURCED, stated). Values: only exact dict, list, str, int,
float, bool and None; bool is not a number, subclasses of every type are
refused, every dict key is an exact str. Caps: a str or key has at most 256
characters (MAX_TEXT), an int has absolute value below 10 ** 10 (MAX_DIGITS is
10), a float is finite, containers nest at most 16 deep (MAX_DEPTH, the root
container is depth 0, an empty container at depth 16 is refused), and a value
has at most 1024 values in all (MAX_NODES, every container and every member
counts, the keys do not), so a cycle or a shared-reference blow-up is refused,
never followed. All Unicode is accepted in a str, including NUL and lone
surrogates, because RFC 6901 Section 3 allows %x7F-10FFFF and Section 8 notes
the NUL; only the array-index digit class is ASCII 0 to 9, and this module
source is ASCII. A pointer text has at most 256 characters (MAX_TEXT) and at
most 32 reference tokens (MAX_TOKENS). pointer_parse returns the tuple of
decoded tokens, '' gives (), a text that does not start with '/' is refused,
and each '~' must be followed by 0 or 1. Decoding turns ~1 into '/' first and
then ~0 into '~'. pointer_format takes a tuple of at most 32 exact str tokens
of at most 256 characters each, turns '~' into ~0 first and then '/' into ~1,
and refuses output over 256 characters, so every output parses back to the
same tokens and every parseable text formats back to itself. array_index takes
the ABNF array-index of at most 10 ASCII digits and returns an int built by
digit arithmetic, never int() on text; '-' is refused there. pointer_get
returns a deep copy of the referenced value; an object token is an exact
member name, an array token must be an array-index below the length, '-' never
resolves and a str, number, bool or None never has members. json_equal follows
RFC 6902 Section 4.6: strings by code points, numbers by numeric value (1 equals
1.0), arrays by position, objects by member name and value regardless of order,
and a bool equals only the same bool, so true is not 1. patch_valid checks
structure only, and patch_apply never mutates its inputs and returns a new
value that shares no list or dict with the document or the patch. A patch is a
list of at most 64 operations, each an exact dict whose keys are all exact
str. Members the operation does not define, including from on add, replace,
remove and test and value on remove, move and copy, are ignored without being
looked at, as RFC 6902 Section 4 requires. The whole patch is checked for
structure before any operation runs, so a bad later operation is refused even
when an earlier one would fail first; RFC 6902 Section 5 only says evaluation
SHOULD terminate on error. Operations apply in order on a private copy and a
refusal returns nothing, so the document is unchanged. add: a root path
replaces the document, an object parent sets the member, an array parent takes
an index from 0 to the length or '-' to append, the parent must exist.
remove and replace need the target to exist. OURS REFUSAL, stated plainly: RFC
6902 never says what the remove of the root yields (EID 4787, held), so remove
of path '' and move from '' are refused as apply.root; replace and test and
copy from the root are accepted. move refuses a from that is a proper prefix
of path, compared token by token, as apply.child, before it checks that from
exists, and a move with from equal to path is a no-op on an existing value;
move is a remove followed by an add, so the array index of the add counts the
array after the removal (the Appendix A.7 example). copy deep-copies. test
refuses unequal values as apply.test. After every operation the result must
still fit the caps, else bad_value:result.depth or bad_value:result.nodes.
The failing operation index is not reported. Errors are ValueError with
message P235:<function>:<code>. pointer_parse: bad_type:text, then
bad_value:text.length, text.syntax and text.tokens. pointer_valid: bad_type:text
only, every other refusal of pointer_parse gives False. pointer_format:
bad_type:tokens, bad_value:tokens.length, then per item in order bad_type:token
and bad_value:token.length, then bad_value:text.length. array_index:
bad_type:token, bad_value:token.length, bad_value:token.syntax. pointer_get:
the document first, bad_type:doc or bad_value:doc.depth, doc.nodes, doc.str,
doc.int, doc.float or doc.key for the first failure in depth-first order, then
bad_type:text, bad_value:text.length, text.syntax, text.tokens, then
bad_value:pointer.missing. json_equal: the same document codes for a, then for
b, with a and b in place of doc. patch_valid: bad_type:patch only, and every
other refusal of the structure check gives False. patch_apply: the document codes
with doc, then the structure codes in operation order, bad_type:patch,
bad_value:patch.length, bad_type:op, bad_type:op.key, bad_value:op.op.missing,
bad_type:op.op, bad_value:op.op.unknown, bad_value:op.path.missing,
bad_type:op.path, bad_value:op.path.length, op.path.syntax, op.path.tokens,
then for move and copy bad_value:op.from.missing, bad_type:op.from and
bad_value:op.from.length, op.from.syntax, op.from.tokens, then for add,
replace and test bad_value:op.value.missing, bad_type:op.value and
bad_value:op.value.depth, nodes, str, int, float, key, then at run time
bad_value:apply.index, apply.parent, apply.root, apply.missing, apply.from,
apply.child, apply.test and bad_value:result.depth, result.nodes.

ADJACENCY, by name only: RFC 8259 JSON text, RFC 7396 JSON Merge Patch, RFC
5789 HTTP PATCH, the RFC 6901 Section 6 URI fragment form and the RFC 6902
Section 6 media type belong to other units and were not read beyond the
sections named above. SCOPE and NOT_CLAIMED are the module constants below.
"""

SCOPE = ('PARTIAL: RFC 6901 JSON Pointer syntax and evaluation and RFC 6902 JSON '
         'Patch application on parsed JSON values, with the OURS caps and '
         'refusals stated in the docstring, pure functions')

NOT_CLAIMED = (
    'JSON text parsing or serialising, only parsed values are handled',
    'the URI fragment form of a pointer, RFC 6901 Section 6',
    'RFC 7396 JSON Merge Patch or any media type handling',
    'duplicate object member names, a parsed dict cannot carry them',
    'the remove or move of the document root, which RFC 6902 leaves unspecified',
    'global novelty',
    'production readiness')

CLAIMS = False

ADJACENT = (
    'RFC 8259 JSON text, RFC 7396 JSON Merge Patch, RFC 5789 HTTP PATCH and '
    'the RFC 6901 URI fragment form are covered by other units and were not '
    'read',)


MAX_TEXT = 256
MAX_TOKENS = 32
MAX_DEPTH = 16
MAX_NODES = 1024
MAX_OPS = 64
MAX_DIGITS = 10

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



_DIG = '0123456789'
_OPS = ('add', 'remove', 'replace', 'move', 'copy', 'test')
_FROM_OPS = ('move', 'copy')
_VALUE_OPS = ('add', 'replace', 'test')
_LIM = 10 ** MAX_DIGITS
_TEXT = ('bad_value:text.length', 'bad_value:text.syntax', 'bad_value:text.tokens')
_PATH = ('bad_value:op.path.length', 'bad_value:op.path.syntax', 'bad_value:op.path.tokens')
_FROM = ('bad_value:op.from.length', 'bad_value:op.from.syntax', 'bad_value:op.from.tokens')
_NOPE = object()


class _No(Exception):
    pass


def _no(code):
    raise _No(code)


def _why(v):
    st = [0]
    return _walk(v, 0, st)


def _walk(v, depth, st):
    st[0] += 1
    if st[0] > MAX_NODES:
        return 'nodes'
    t = type(v)
    if v is None or t is bool:
        return ''
    if t is str:
        return '' if len(v) <= MAX_TEXT else 'str'
    if t is int:
        return '' if -_LIM < v < _LIM else 'int'
    if t is float:
        return '' if v - v == 0 else 'float'
    if t is list:
        if depth >= MAX_DEPTH:
            return 'depth'
        for x in v:
            r = _walk(x, depth + 1, st)
            if r:
                return r
        return ''
    if t is dict:
        if depth >= MAX_DEPTH:
            return 'depth'
        for k in v:
            if type(k) is not str or len(k) > MAX_TEXT:
                return 'key'
            r = _walk(v[k], depth + 1, st)
            if r:
                return r
        return ''
    return 'type'


def _vcheck(f, v, label):
    w = _why(v)
    if w == 'type':
        f('bad_type:' + label)
    if w:
        f('bad_value:' + label + '.' + w)


def _copy(v):
    t = type(v)
    if t is list:
        return [_copy(x) for x in v]
    if t is dict:
        return {k: _copy(v[k]) for k in v}
    return v


def _eq(a, b):
    ta = type(a)
    tb = type(b)
    if ta is list:
        if tb is not list or len(a) != len(b):
            return False
        for x, y in zip(a, b):
            if not _eq(x, y):
                return False
        return True
    if ta is dict:
        if tb is not dict or len(a) != len(b):
            return False
        for k in a:
            if k not in b or not _eq(a[k], b[k]):
                return False
        return True
    if ta is bool or tb is bool:
        return ta is tb and a == b
    return a == b


def _index(tok):
    if tok == '' or len(tok) > MAX_DIGITS:
        return -1
    if tok[0] == '0' and len(tok) > 1:
        return -1
    n = 0
    for c in tok:
        d = _DIG.find(c)
        if d < 0:
            return -1
        n = n * 10 + d
    return n


def _tokens(f, text, codes):
    if len(text) > MAX_TEXT:
        f(codes[0])
    if text == '':
        return ()
    if text[0] != '/':
        f(codes[1])
    parts = text.split('/')[1:]
    for p in parts:
        for e in p.split('~')[1:]:
            if e[:1] != '0' and e[:1] != '1':
                f(codes[1])
    if len(parts) > MAX_TOKENS:
        f(codes[2])
    return tuple([p.replace('~1', '/').replace('~0', '~') for p in parts])


def _slot(cur, tok):
    if type(cur) is dict:
        return tok if tok in cur else None
    if type(cur) is list:
        i = _index(tok)
        if i < 0 or i >= len(cur):
            return None
        return i
    return None


def _resolve(cur, toks):
    for tok in toks:
        s = _slot(cur, tok)
        if s is None:
            return _NOPE
        cur = cur[s]
    return cur


def _locate(f, d, pt, code):
    parent = _resolve(d, pt[:-1])
    s = None if parent is _NOPE else _slot(parent, pt[-1])
    if s is None:
        f(code)
    return parent, s


def _add(f, d, pt, val):
    if len(pt) == 0:
        return val
    parent = _resolve(d, pt[:-1])
    last = pt[-1]
    t = type(parent)
    if t is dict:
        parent[last] = val
        return d
    if t is list:
        if last == '-':
            parent.append(val)
            return d
        i = _index(last)
        if i < 0 or i > len(parent):
            f('bad_value:apply.index')
        parent.insert(i, val)
        return d
    f('bad_value:apply.parent')


def _take(f, d, pt, code):
    parent, s = _locate(f, d, pt, code)
    v = parent[s]
    del parent[s]
    return v


def _do(f, d, name, pt, ft, val):
    if name == 'add':
        return _add(f, d, pt, _copy(val))
    if name == 'remove':
        if len(pt) == 0:
            f('bad_value:apply.root')
        _take(f, d, pt, 'bad_value:apply.missing')
        return d
    if name == 'replace':
        if len(pt) == 0:
            return _copy(val)
        parent, s = _locate(f, d, pt, 'bad_value:apply.missing')
        parent[s] = _copy(val)
        return d
    if name == 'move':
        if len(ft) < len(pt) and pt[:len(ft)] == ft:
            f('bad_value:apply.child')
        if len(ft) == 0:
            f('bad_value:apply.root')
        v = _take(f, d, ft, 'bad_value:apply.from')
        return _add(f, d, pt, v)
    if name == 'copy':
        v = _resolve(d, ft)
        if v is _NOPE:
            f('bad_value:apply.from')
        return _add(f, d, pt, _copy(v))
    v = _resolve(d, pt)
    if v is _NOPE:
        f('bad_value:apply.missing')
    if not _eq(v, val):
        f('bad_value:apply.test')
    return d


def _ops(f, patch):
    if type(patch) is not list:
        f('bad_type:patch')
    if len(patch) > MAX_OPS:
        f('bad_value:patch.length')
    out = []
    for op in patch:
        if type(op) is not dict:
            f('bad_type:op')
        for k in op:
            if type(k) is not str:
                f('bad_type:op.key')
        if 'op' not in op:
            f('bad_value:op.op.missing')
        name = op['op']
        if type(name) is not str:
            f('bad_type:op.op')
        if name not in _OPS:
            f('bad_value:op.op.unknown')
        if 'path' not in op:
            f('bad_value:op.path.missing')
        p = op['path']
        if type(p) is not str:
            f('bad_type:op.path')
        pt = _tokens(f, p, _PATH)
        ft = ()
        if name in _FROM_OPS:
            if 'from' not in op:
                f('bad_value:op.from.missing')
            p = op['from']
            if type(p) is not str:
                f('bad_type:op.from')
            ft = _tokens(f, p, _FROM)
        val = None
        if name in _VALUE_OPS:
            if 'value' not in op:
                f('bad_value:op.value.missing')
            val = op['value']
            _vcheck(f, val, 'op.value')
        out.append((name, pt, ft, val))
    return out


def pointer_parse(text):
    f = make_fail('pointer_parse')
    if type(text) is not str:
        f('bad_type:text')
    return _tokens(f, text, _TEXT)


def pointer_valid(text):
    f = make_fail('pointer_valid')
    if type(text) is not str:
        f('bad_type:text')
    try:
        _tokens(_no, text, _TEXT)
    except _No:
        return False
    return True


def pointer_format(tokens):
    f = make_fail('pointer_format')
    if type(tokens) is not tuple:
        f('bad_type:tokens')
    if len(tokens) > MAX_TOKENS:
        f('bad_value:tokens.length')
    out = ''
    for t in tokens:
        if type(t) is not str:
            f('bad_type:token')
        if len(t) > MAX_TEXT:
            f('bad_value:token.length')
        out += '/' + t.replace('~', '~0').replace('/', '~1')
    if len(out) > MAX_TEXT:
        f('bad_value:text.length')
    return out


def array_index(token):
    f = make_fail('array_index')
    if type(token) is not str:
        f('bad_type:token')
    if len(token) > MAX_DIGITS:
        f('bad_value:token.length')
    n = _index(token)
    if n < 0:
        f('bad_value:token.syntax')
    return n


def pointer_get(doc, text):
    f = make_fail('pointer_get')
    _vcheck(f, doc, 'doc')
    if type(text) is not str:
        f('bad_type:text')
    toks = _tokens(f, text, _TEXT)
    v = _resolve(doc, toks)
    if v is _NOPE:
        f('bad_value:pointer.missing')
    return _copy(v)


def json_equal(a, b):
    f = make_fail('json_equal')
    _vcheck(f, a, 'a')
    _vcheck(f, b, 'b')
    return _eq(a, b)


def patch_valid(patch):
    f = make_fail('patch_valid')
    if type(patch) is not list:
        f('bad_type:patch')
    try:
        _ops(_no, patch)
    except _No:
        return False
    return True


def patch_apply(doc, patch):
    f = make_fail('patch_apply')
    _vcheck(f, doc, 'doc')
    ops = _ops(f, patch)
    d = _copy(doc)
    for name, pt, ft, val in ops:
        d = _do(f, d, name, pt, ft, val)
        w = _why(d)
        if w:
            f('bad_value:result.' + w)
    return d
