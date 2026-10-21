import builtins
import importlib
import importlib.util as iu
import pathlib
import re
import signal
import sys
import types
import pytest

REG = 'app.modules.instinct_doc.p235_concepts_registry'
LEAF = 'p235_concepts_registry'
_MISSING = object()


def _import_module_fresh():
    # a preset sys.modules[REG] = None makes the registry import raise
    # ModuleNotFoundError(name=REG), which the module's own guard handles;
    # clear the preset for this import, then restore the exact world we found
    saved = sys.modules.get(REG, _MISSING)
    if saved is None:
        del sys.modules[REG]
    try:
        from app.modules.instinct_doc import p235_concepts_batch1127_jsonpatch as mod
        return mod
    finally:
        if saved is None:
            sys.modules[REG] = None
        elif saved is not _MISSING:
            sys.modules[REG] = saved


@pytest.fixture(scope='module', autouse=True)
def load_module():
    global m
    snap_import = builtins.__import__
    snap_find = iu.find_spec
    m = _import_module_fresh()
    yield
    assert builtins.__import__ is snap_import, 'builtins.__import__ leaked by this module'
    assert iu.find_spec is snap_find, 'find_spec leaked by this module'


@pytest.fixture(autouse=True)
def _alarm():
    # 60 s guards against a hang only; the slowest test takes about 5 s alone, and a loaded host must not turn
    # a slow pass into a false failure
    def h(*a):
        raise RuntimeError('test exceeded 60 s')
    old = signal.signal(signal.SIGALRM, h)
    signal.alarm(60)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def _pfx():
    # prefix of the error text in whichever registry world is active, derived
    # from one known refusal, never hardcoded
    with pytest.raises(ValueError) as e:
        m.pointer_valid(None)
    tail = 'pointer_valid:bad_type:text'
    text = str(e.value)
    assert text.endswith(tail)
    return text[:-len(tail)]


def refuse(fn, code, *a):
    with pytest.raises(ValueError) as e:
        getattr(m, fn)(*a)
    assert str(e.value) == _pfx() + '%s:%s' % (fn, code)


class _Spy:
    calls = []


class _Meta(type):
    def __eq__(cls, o):
        _Spy.calls.append('meta_eq')
        return True

    def __hash__(cls):
        return 1

    def __instancecheck__(cls, o):
        _Spy.calls.append('meta_ic')
        return True


class _Liar(metaclass=_Meta):
    def __eq__(self, o):
        _Spy.calls.append('eq')
        return True

    def __ne__(self, o):
        _Spy.calls.append('ne')
        return False

    def __lt__(self, o):
        _Spy.calls.append('lt')
        return False

    def __gt__(self, o):
        _Spy.calls.append('gt')
        return False

    def __index__(self):
        _Spy.calls.append('index')
        return 5

    def __int__(self):
        _Spy.calls.append('int')
        return 5

    def __len__(self):
        _Spy.calls.append('len')
        return 1

    def __hash__(self):
        return 2


class _IntSub(int):
    def __eq__(self, o):
        _Spy.calls.append('sub_eq')
        return True

    def __lt__(self, o):
        _Spy.calls.append('sub_lt')
        return False

    def __gt__(self, o):
        _Spy.calls.append('sub_gt')
        return False

    __hash__ = int.__hash__


class _StrSub(str):
    def split(self, *a):
        _Spy.calls.append('split')
        return ['5']

    def strip(self, *a):
        _Spy.calls.append('strip')
        return '5'

    def __len__(self):
        _Spy.calls.append('strlen')
        return 1

    def __iter__(self):
        _Spy.calls.append('iter')
        return iter('5')





# ================= reference model, written independently of the module =================
import copy
import random

_R_PTR = re.compile(r'(?:/(?:[^/~]|~[01])*)*')
_R_IDX = re.compile(r'0|[1-9][0-9]{0,9}', re.A)
_R_CODES = {'type': 'bad_type:%s', }


def r_why(v):
    nodes = [0]

    def go(x, depth):
        nodes[0] += 1
        if nodes[0] > 1024:
            return 'nodes'
        if x is None or type(x) is bool:
            return ''
        if type(x) is str:
            return 'str' if len(x) > 256 else ''
        if type(x) is int:
            return 'int' if abs(x) >= 10 ** 10 else ''
        if type(x) is float:
            return '' if x == x and abs(x) != float('inf') else 'float'
        if type(x) is list:
            if depth > 15:
                return 'depth'
            for y in x:
                r = go(y, depth + 1)
                if r:
                    return r
            return ''
        if type(x) is dict:
            if depth > 15:
                return 'depth'
            for k, y in x.items():
                if type(k) is not str or len(k) > 256:
                    return 'key'
                r = go(y, depth + 1)
                if r:
                    return r
            return ''
        return 'type'
    return go(v, 0)


def r_parse(t, pre='text'):
    if len(t) > 256:
        return 'bad_value:%s.length' % pre
    if not _R_PTR.fullmatch(t):
        return 'bad_value:%s.syntax' % pre
    toks = t.split('/')[1:] if t else []
    if len(toks) > 32:
        return 'bad_value:%s.tokens' % pre
    return tuple(x.replace('~1', '/').replace('~0', '~') for x in toks)


def r_idx(tok):
    return int(tok) if _R_IDX.fullmatch(tok) else None


def r_find(doc, toks):
    cur = doc
    for t in toks:
        if type(cur) is dict and t in cur:
            cur = cur[t]
        elif type(cur) is list and r_idx(t) is not None and r_idx(t) < len(cur):
            cur = cur[r_idx(t)]
        else:
            return None
    return (cur,)


def r_eq(a, b):
    if type(a) is bool or type(b) is bool:
        return type(a) is type(b) and a == b
    if a is None or b is None:
        return a is None and b is None
    if type(a) is str or type(b) is str:
        return type(a) is type(b) and a == b
    if type(a) in (int, float) and type(b) in (int, float):
        return a == b
    if type(a) is list and type(b) is list:
        return len(a) == len(b) and all(r_eq(x, y) for x, y in zip(a, b))
    if type(a) is dict and type(b) is dict:
        return sorted(a) == sorted(b) and all(r_eq(a[k], b[k]) for k in a)
    return False


def r_put(doc, toks, val):
    # add; returns (new doc,) or a code
    if not toks:
        return (val,)
    hit = r_find(doc, toks[:-1])
    if hit is None:
        return 'bad_value:apply.parent'
    par, last = hit[0], toks[-1]
    if type(par) is dict:
        par[last] = val
    elif type(par) is list:
        if last == '-':
            par.append(val)
        else:
            i = r_idx(last)
            if i is None or i > len(par):
                return 'bad_value:apply.index'
            par.insert(i, val)
    else:
        return 'bad_value:apply.parent'
    return (doc,)


def r_cut(doc, toks):
    hit = r_find(doc, toks)
    if hit is None:
        return None
    par = r_find(doc, toks[:-1])[0]
    if type(par) is dict:
        del par[toks[-1]]
    else:
        del par[r_idx(toks[-1])]
    return hit


def r_step(doc, op):
    # one structurally valid op; returns (doc,) or a code
    name = op['op']
    pt = r_parse(op['path'])
    ft = r_parse(op['from']) if name in ('move', 'copy') else ()
    if name == 'add':
        return r_put(doc, pt, copy.deepcopy(op['value']))
    if name == 'remove':
        if not pt:
            return 'bad_value:apply.root'
        return (doc,) if r_cut(doc, pt) else 'bad_value:apply.missing'
    if name == 'replace':
        if not pt:
            return (copy.deepcopy(op['value']),)
        if r_find(doc, pt) is None:
            return 'bad_value:apply.missing'
        r_cut(doc, pt)
        res = r_put(doc, pt, copy.deepcopy(op['value']))
        return res
    if name == 'move':
        if pt[:len(ft)] == ft and len(ft) < len(pt):
            return 'bad_value:apply.child'
        if not ft:
            return 'bad_value:apply.root'
        got = r_cut(doc, ft)
        if got is None:
            return 'bad_value:apply.from'
        return r_put(doc, pt, got[0])
    if name == 'copy':
        hit = r_find(doc, ft)
        if hit is None:
            return 'bad_value:apply.from'
        return r_put(doc, pt, copy.deepcopy(hit[0]))
    hit = r_find(doc, pt)
    if hit is None:
        return 'bad_value:apply.missing'
    return (doc,) if r_eq(hit[0], op['value']) else 'bad_value:apply.test'


def r_apply(doc, patch):
    d = copy.deepcopy(doc)
    for op in patch:
        res = r_step(d, op)
        if type(res) is str:
            return res
        d = res[0]
        w = r_why(d)
        if w:
            return 'bad_value:result.' + w
    return (d,)


def _same(a, b):
    # strict structural identity of values: types and contents
    if type(a) is not type(b):
        return False
    if type(a) is list:
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if type(a) is dict:
        return list(a) == list(b) and all(_same(a[k], b[k]) for k in a)
    return a == b and repr(a) == repr(b)


def _nodes(v, out=None):
    out = [] if out is None else out
    if type(v) in (list, dict):
        out.append(v)
        for x in (v if type(v) is list else v.values()):
            _nodes(x, out)
    return out


def deep(n, leaf=0):
    v = leaf
    for _ in range(n):
        v = [v]
    return v


def ddeep(n, leaf=0):
    v = leaf
    for _ in range(n):
        v = {'k': v}
    return v


def mdeep(n, leaf=0):
    # alternating dict and list wrappers, outermost dict
    v = leaf
    for i in range(n):
        v = [v] if i % 2 == 0 else {'k': v}
    return v


RFC_DOC = {"foo": ["bar", "baz"], "": 0, "a/b": 1, "c%d": 2, "e^f": 3, "g|h": 4, "i\\j": 5, "k\"l": 6, " ": 7, "m~n": 8}
RFC_TABLE = [('', None), ('/foo', ['bar', 'baz']), ('/foo/0', 'bar'), ('/', 0), ('/a~1b', 1), ('/c%d', 2),
             ('/e^f', 3), ('/g|h', 4), ('/i\\j', 5), ('/k"l', 6), ('/ ', 7), ('/m~0n', 8)]


def test_rfc6901_section5_table_exact():
    for ptr, want in RFC_TABLE:
        got = m.pointer_get(RFC_DOC, ptr)
        if ptr == '':
            assert _same(got, RFC_DOC) and got is not RFC_DOC
        else:
            assert _same(got, want), ptr
        assert m.pointer_valid(ptr) is True
        assert m.pointer_format(m.pointer_parse(ptr)) == ptr


def test_pointer_parse_exact_values():
    assert m.pointer_parse('') == ()
    assert m.pointer_parse('/') == ('',)
    assert m.pointer_parse('//') == ('', '')
    assert m.pointer_parse('/a/b') == ('a', 'b')
    assert m.pointer_parse('/a~1b') == ('a/b',)
    assert m.pointer_parse('/m~0n') == ('m~n',)
    assert m.pointer_parse('/~01') == ('~1',)
    assert m.pointer_parse('/~10') == ('/0',)
    assert m.pointer_parse('/~0~1') == ('~/',)
    assert m.pointer_parse('/~00') == ('~0',)
    assert m.pointer_parse('/~1~1') == ('//',)
    assert m.pointer_parse('/ ') == (' ',)
    assert m.pointer_parse('/\x00') == ('\x00',)
    assert m.pointer_parse('/\ud800') == ('\ud800',)
    assert m.pointer_parse('/\u00e9/\U0001f600') == ('\u00e9', '\U0001f600')
    assert m.pointer_parse('/\n/\t') == ('\n', '\t')
    assert m.pointer_parse('/%25/#') == ('%25', '#')
    for t in ('', '/', '/a', '/~0', '/~1', '/\u00e9'):
        assert type(m.pointer_parse(t)) is tuple
        assert all(type(x) is str for x in m.pointer_parse(t))


@pytest.mark.parametrize('t', ['a', ' /a', 'a/b', '~0', '~', '/~', '/a~', '/~2', '/~a', '/~ ', '/~~0', '/a~/b', '/~\u00e9', '/a/~',
                               '/~\x00', '~/', '\u00e9', '#/a', '//~3'])
def test_pointer_parse_syntax_refusals(t):
    refuse('pointer_parse', 'bad_value:text.syntax', t)
    assert m.pointer_valid(t) is False
    assert r_parse(t) == 'bad_value:text.syntax'


def test_pointer_caps_exact_both_sides_and_order():
    ok = '/' + 'a' * 255
    assert len(ok) == 256 and m.pointer_parse(ok) == ('a' * 255,) and m.pointer_valid(ok) is True
    refuse('pointer_parse', 'bad_value:text.length', ok + 'a')
    assert m.pointer_valid(ok + 'a') is False
    ok = '/' * 32
    assert m.pointer_parse(ok) == ('',) * 32 and m.pointer_valid(ok) is True
    refuse('pointer_parse', 'bad_value:text.tokens', '/' * 33)
    assert m.pointer_valid('/' * 33) is False
    # check order: length, syntax, tokens, with both fields wrong at each adjacent pair
    refuse('pointer_parse', 'bad_value:text.length', 'x' * 257)
    refuse('pointer_parse', 'bad_value:text.length', '/~' + '/' * 300)
    refuse('pointer_parse', 'bad_value:text.syntax', '/~' + '/' * 33)
    refuse('pointer_parse', 'bad_value:text.syntax', '/' * 33 + '~')
    refuse('pointer_parse', 'bad_value:text.syntax', '/' * 33 + '~2')
    refuse('pointer_parse', 'bad_value:text.tokens', '/~0' * 33)
    assert m.pointer_parse('/~0' * 32) == ('~',) * 32
    assert len('/~0' * 32) == 96


def test_pointer_valid_returns_exact_bool_and_refuses_only_type():
    for t in ('', '/', '/a', '/~0', '/' * 32, '/' + 'a' * 255):
        assert m.pointer_valid(t) is True
    for t in ('a', '/~', '/' * 33, 'a' * 257, '/~' + '/' * 300):
        assert m.pointer_valid(t) is False
    for v in (None, 1, b'/a', ('/a',), ['/a']):
        refuse('pointer_valid', 'bad_type:text', v)


def test_pointer_format_exact_values_and_escape_order():
    assert m.pointer_format(()) == ''
    assert m.pointer_format(('',)) == '/'
    assert m.pointer_format(('a', 'b')) == '/a/b'
    assert m.pointer_format(('a/b',)) == '/a~1b'
    assert m.pointer_format(('m~n',)) == '/m~0n'
    assert m.pointer_format(('~1',)) == '/~01'
    assert m.pointer_format(('/0',)) == '/~10'
    assert m.pointer_format(('~/',)) == '/~0~1'
    assert m.pointer_format(('~0',)) == '/~00'
    assert m.pointer_format(('//',)) == '/~1~1'
    assert m.pointer_format(('\u00e9', '\ud800', '\x00')) == '/\u00e9/\ud800/\x00'
    assert type(m.pointer_format(('a',))) is str


def test_pointer_format_caps_both_sides_and_roundtrip():
    toks = ('a' * 255,)
    assert len(m.pointer_format(toks)) == 256 and m.pointer_parse(m.pointer_format(toks)) == toks
    refuse('pointer_format', 'bad_value:text.length', ('a' * 256,))
    refuse('pointer_format', 'bad_value:token.length', ('a' * 257,))
    toks = ('~' * 127 + 'a',)
    assert len(m.pointer_format(toks)) == 256 and m.pointer_parse(m.pointer_format(toks)) == toks
    refuse('pointer_format', 'bad_value:text.length', ('~' * 128,))
    refuse('pointer_format', 'bad_value:text.length', ('/' * 128,))
    toks = ('',) * 32
    assert m.pointer_format(toks) == '/' * 32 and m.pointer_parse('/' * 32) == toks
    refuse('pointer_format', 'bad_value:tokens.length', ('',) * 33)
    # order: tokens type, tokens length, item type, item length, total length
    refuse('pointer_format', 'bad_type:tokens', ['a'] * 33)
    refuse('pointer_format', 'bad_value:tokens.length', (1,) * 33)
    refuse('pointer_format', 'bad_value:token.length', ('a' * 257, 1))
    refuse('pointer_format', 'bad_value:token.length', ('a' * 257,))
    refuse('pointer_format', 'bad_type:token', (1, 'a' * 257))
    refuse('pointer_format', 'bad_value:token.length', ('a' * 257, 'a' * 257))
    refuse('pointer_format', 'bad_value:text.length', ('a' * 200, 'a' * 200))
    rnd = random.Random(1127)
    alpha = ['a', 'b', '/', '~', '0', '1', '~0', '~1', '\u00e9', '', ' ', '\ud800']
    for _ in range(3000):
        toks = tuple(''.join(rnd.choice(alpha) for _ in range(rnd.randrange(0, 6))) for _ in range(rnd.randrange(0, 8)))
        text = m.pointer_format(toks)
        assert m.pointer_parse(text) == toks and r_parse(text) == toks
        assert m.pointer_valid(text) is True
        assert m.pointer_format(m.pointer_parse(text)) == text
    for _ in range(3000):
        text = ''.join(rnd.choice(['/', '~', '0', '1', 'a', '2', '~0', '~1']) for _ in range(rnd.randrange(0, 14)))
        want = r_parse(text)
        if type(want) is str:
            refuse('pointer_parse', want, text)
            assert m.pointer_valid(text) is False
        else:
            assert m.pointer_parse(text) == want
            assert m.pointer_format(want) == text and m.pointer_valid(text) is True


def test_array_index_exact_and_digit_class():
    for t, n in (('0', 0), ('1', 1), ('9', 9), ('10', 10), ('19', 19), ('99', 99), ('100', 100), ('1234567890', 1234567890),
                 ('9999999999', 9999999999)):
        got = m.array_index(t)
        assert got == n and type(got) is int
    for t in ('', '00', '01', '001', '-', '-1', '+1', ' 1', '1 ', '1.0', '1e1', '0x1', '1_0', '\u0663', '\u00b2', '\uff11', '\u0966',
              'a', '\x00', '1\n', '1\x00', '\u0661', '\u06f1', '1\u0663', '\u0663' * 3):
        refuse('array_index', 'bad_value:token.syntax', t)
    refuse('array_index', 'bad_value:token.length', '1' * 11)
    refuse('array_index', 'bad_value:token.length', '0' * 11)
    refuse('array_index', 'bad_value:token.length', 'x' * 11)
    refuse('array_index', 'bad_value:token.length', '9' * 5000)
    refuse('array_index', 'bad_value:token.length', '9' * 4301)
    refuse('array_index', 'bad_value:token.length', '9' * 400000)
    refuse('array_index', 'bad_value:token.syntax', '0' * 10)
    assert m.array_index('1' * 10) == 1111111111


def test_pointer_get_missing_and_index_rules():
    doc = {'a': [10, 20, 30], '0': 'zero', '': 'empty', 'n': None, 'o': {'x': {'y': 1}}, 's': 'str', 't': True, 'f': 1.5}
    assert m.pointer_get(doc, '/a/0') == 10 and m.pointer_get(doc, '/a/2') == 30
    assert m.pointer_get(doc, '/0') == 'zero' and m.pointer_get(doc, '/') == 'empty'
    assert m.pointer_get(doc, '/n') is None and m.pointer_get(doc, '/t') is True and m.pointer_get(doc, '/f') == 1.5
    assert m.pointer_get(doc, '/o/x/y') == 1
    for bad in ('/a/3', '/a/-', '/a/01', '/a/00', '/a/x', '/a/ 1', '/a/1 ', '/a/-1', '/a/+1', '/a/1.0', '/a/\u0661', '/a/',
                '/a/9999999999', '/a/99999999999', '/missing', '/o/x/z', '/o/y/y', '/s/0', '/t/x', '/n/x', '/f/0', '/s/', '/a/0/0',
                '/o/x/y/z', '/a/1/', '//'):
        refuse('pointer_get', 'bad_value:pointer.missing', doc, bad)
    assert m.pointer_get([1, 2], '/1') == 2
    refuse('pointer_get', 'bad_value:pointer.missing', [1, 2], '/-')
    refuse('pointer_get', 'bad_value:pointer.missing', [1, 2], '/2')
    refuse('pointer_get', 'bad_value:pointer.missing', [], '/0')
    refuse('pointer_get', 'bad_value:pointer.missing', {'0': 1}.get('0'), '/0')
    assert m.pointer_get({'a': {'0': 5}}, '/a/0') == 5
    assert m.pointer_get(7, '') == 7
    refuse('pointer_get', 'bad_value:pointer.missing', 7, '/a')
    # a member name is matched as exact characters, no normalisation, no case folding
    assert m.pointer_get({'\u00e9': 1}, '/\u00e9') == 1
    refuse('pointer_get', 'bad_value:pointer.missing', {'\u00e9': 1}, '/e\u0301')
    refuse('pointer_get', 'bad_value:pointer.missing', {'A': 1}, '/a')
    assert m.pointer_get({'a/b': {'c~d': 4}}, '/a~1b/c~0d') == 4
    assert m.pointer_get({'~1': 10, '/': 9}, '/~01') == 10 and m.pointer_get({'~1': 10, '/': 9}, '/~1') == 9


def test_pointer_get_returns_independent_copy():
    doc = {'a': [1, {'b': [2]}]}
    got = m.pointer_get(doc, '/a')
    assert got == [1, {'b': [2]}] and got is not doc['a']
    got[1]['b'].append(3)
    assert doc == {'a': [1, {'b': [2]}]}
    root = m.pointer_get(doc, '')
    assert root == doc and root is not doc and root['a'] is not doc['a']
    for n in _nodes(root):
        assert all(n is not o for o in _nodes(doc))


def test_pointer_get_check_order():
    refuse('pointer_get', 'bad_type:doc', object(), 5)
    refuse('pointer_get', 'bad_value:doc.depth', deep(17), 5)
    refuse('pointer_get', 'bad_type:text', {}, 5)
    refuse('pointer_get', 'bad_value:text.length', {}, 'a' * 257)
    refuse('pointer_get', 'bad_value:text.length', {}, '/~' + '/' * 300)
    refuse('pointer_get', 'bad_value:text.syntax', {}, '/~' + '/' * 33)
    refuse('pointer_get', 'bad_value:text.tokens', {}, '/' * 33)
    refuse('pointer_get', 'bad_value:pointer.missing', {}, '/a')
    refuse('pointer_get', 'bad_value:text.syntax', {'a': 1}, 'a')


def test_json_equal_rfc_rules():
    assert m.json_equal('foo', 'foo') is True and m.json_equal('foo', 'bar') is False
    assert m.json_equal(10, '10') is False and m.json_equal('10', 10) is False
    assert m.json_equal(1, 1.0) is True and m.json_equal(1.0, 1) is True and m.json_equal(0, -0.0) is True
    assert m.json_equal(1, 2) is False and m.json_equal(1.5, 1.5) is True and m.json_equal(1.5, 1) is False
    assert m.json_equal(10 ** 10 - 1, float(10 ** 10 - 1)) is True
    assert m.json_equal(True, True) is True and m.json_equal(False, False) is True and m.json_equal(True, False) is False
    assert m.json_equal(True, 1) is False and m.json_equal(1, True) is False and m.json_equal(False, 0) is False
    assert m.json_equal(0, False) is False and m.json_equal(1.0, True) is False and m.json_equal(False, 0.0) is False
    assert m.json_equal(None, None) is True and m.json_equal(None, 0) is False and m.json_equal(0, None) is False
    assert m.json_equal(None, False) is False and m.json_equal(False, None) is False and m.json_equal('', None) is False
    assert m.json_equal(None, '') is False and m.json_equal(None, []) is False and m.json_equal({}, None) is False
    assert m.json_equal('', '') is True and m.json_equal('a', 'A') is False
    assert m.json_equal('\u00e9', 'e\u0301') is False and m.json_equal('\u00e9', '\u00e9') is True
    assert m.json_equal([], []) is True and m.json_equal({}, {}) is True
    assert m.json_equal([], {}) is False and m.json_equal({}, []) is False and m.json_equal([], '') is False
    assert m.json_equal('', []) is False and m.json_equal(0, []) is False and m.json_equal([], 0) is False
    assert m.json_equal({}, 0) is False and m.json_equal(0, {}) is False and m.json_equal({}, '') is False
    assert m.json_equal([1, 2], [1, 2]) is True and m.json_equal([1, 2], [2, 1]) is False
    assert m.json_equal([1, 2], [1, 2, 3]) is False and m.json_equal([1, 2, 3], [1, 2]) is False
    assert m.json_equal([1, [2, [3]]], [1.0, [2.0, [3.0]]]) is True and m.json_equal([1, [2, [3]]], [1, [2, [4]]]) is False
    assert m.json_equal({'a': 1, 'b': 2}, {'b': 2, 'a': 1}) is True and m.json_equal({'a': 1}, {'a': 2}) is False
    assert m.json_equal({'a': 1}, {'b': 1}) is False and m.json_equal({'a': 1}, {'a': 1, 'b': 2}) is False
    assert m.json_equal({'a': 1, 'b': 2}, {'a': 1}) is False and m.json_equal({'a': 1, 'b': 2}, {'a': 1, 'c': 2}) is False
    assert m.json_equal({'a': [1, {'b': None}]}, {'a': [1.0, {'b': None}]}) is True
    assert m.json_equal({'a': [1, {'b': None}]}, {'a': [1.0, {'b': False}]}) is False
    assert m.json_equal({'a': True}, {'a': 1}) is False and m.json_equal([True], [1]) is False
    assert m.json_equal([None], [0]) is False and m.json_equal([[]], [{}]) is False
    x = {'k': [1, 2]}
    assert m.json_equal(x, x) is True


def test_json_equal_matches_reference_on_random_values():
    rnd = random.Random(61)

    def gen(d):
        k = rnd.randrange(0, 9 if d < 3 else 6)
        if k == 0:
            return None
        if k == 1:
            return rnd.choice([True, False])
        if k == 2:
            return rnd.choice([0, 1, 2, -1, 10])
        if k == 3:
            return rnd.choice([0.0, 1.0, 2.0, -1.0, 1.5, 10.0])
        if k == 4:
            return rnd.choice(['', 'a', 'b', '1', '0', 'A'])
        if k == 5:
            return rnd.choice(['x', 'y'])
        if k == 6 or k == 7:
            return [gen(d + 1) for _ in range(rnd.randrange(0, 4))]
        return {rnd.choice('abc'): gen(d + 1) for _ in range(rnd.randrange(0, 4))}
    seen = [0, 0]
    for _ in range(6000):
        a = gen(0)
        b = copy.deepcopy(a) if rnd.randrange(3) == 0 else gen(0)
        got = m.json_equal(a, b)
        assert got is r_eq(a, b)
        seen[got] += 1
    assert seen[0] > 1000 and seen[1] > 1000


# ================= document caps and value validation =================
def _doc_codes(fn_check):
    # fn_check(doc) must raise the expected code for each of these in every function that takes a document
    pass


_DOC_BAD = [
    ('type', object()), ('type', b'x'), ('type', (1,)), ('type', {1}), ('type', _StrSub('a')), ('type', _IntSub(1)),
    ('type', _Liar()), ('type', bytearray(b'x')), ('type', [object()]), ('type', {'a': (1,)}), ('type', {'a': [b'']}),
    ('type', type('L', (list,), {})()), ('type', type('D', (dict,), {})()), ('type', type('F', (float,), {})(1.5)),
    ('type', [[[_StrSub('x')]]]), ('type', 1j), ('type', [1, 2, [3, {'a': {4}}]]),
    ('depth', deep(17)), ('depth', deep(17, [])), ('depth', deep(17, {})), ('depth', deep(40)),
    ('depth', ddeep(17)), ('depth', ddeep(16, {})), ('depth', ddeep(17, [])), ('depth', mdeep(17)), ('depth', mdeep(16, {})), ('depth', mdeep(16, [])),
    ('nodes', [0] * 1024), ('nodes', [0] * 5000), ('nodes', {str(i): 0 for i in range(1024)}), ('nodes', [[0] * 511, [0] * 511]),
    ('nodes', [0] * 1023 + [object()]),
    ('str', 'a' * 257), ('str', ['a' * 257]), ('str', {'k': 'a' * 257}), ('str', 'a' * 3000000),
    ('int', 10 ** 10), ('int', -10 ** 10), ('int', 2 ** 40000), ('int', -2 ** 40000), ('int', [10 ** 10]), ('int', {'a': -10 ** 10}),
    ('float', float('inf')), ('float', float('-inf')), ('float', float('nan')), ('float', [float('nan')]), ('float', {'a': float('inf')}),
    ('key', {1: 1}), ('key', {'a' * 257: 1}), ('key', {_StrSub('a'): 1}), ('key', {b'a': 1}), ('key', {None: 1}), ('key', {(1,): 1}),
    ('key', {'a': {2: 3}}), ('key', {'a' * 257: object()}), ('key', {1.5: 1}), ('key', {True: 1}),
]


def _cyc_list():
    a = []
    a.append(a)
    return a


def _cyc_dict():
    d = {}
    d['k'] = d
    return d


def _dag(n):
    x = [0]
    for _ in range(n):
        x = [x, x]
    return x


_DOC_BAD += [('depth', _cyc_list()), ('depth', _cyc_dict()), ('nodes', _dag(12)), ('nodes', _dag(15)), ('depth', _dag(17))]


def _doc_code(kind):
    return 'bad_type:%s' if kind == 'type' else 'bad_value:%s.' + kind


@pytest.mark.parametrize('idx', range(len(_DOC_BAD)))
def test_every_function_refuses_each_bad_document_with_the_same_code(idx):
    kind, bad = _DOC_BAD[idx]
    code = _doc_code(kind)
    assert r_why(bad) == ('type' if kind == 'type' else kind)
    refuse('pointer_get', code % 'doc', bad, '')
    refuse('patch_apply', code % 'doc', bad, [])
    refuse('json_equal', code % 'a', bad, 1)
    refuse('json_equal', code % 'a', bad, object())
    refuse('json_equal', code % 'b', 1, bad)
    refuse('patch_apply', code % 'op.value', {}, [{'op': 'add', 'path': '', 'value': bad}])
    refuse('patch_apply', code % 'op.value', {}, [{'op': 'replace', 'path': '', 'value': bad}])
    refuse('patch_apply', code % 'op.value', {}, [{'op': 'test', 'path': '', 'value': bad}])
    assert m.patch_valid([{'op': 'add', 'path': '', 'value': bad}]) is False
    assert m.patch_valid([{'op': 'remove', 'path': '/a', 'value': bad}]) is True


def test_document_caps_exact_both_sides():
    ok = [
        [0] * 1023, {str(i): 0 for i in range(1023)}, [[0] * 510, [0] * 511], deep(16), deep(15, []), deep(15, {}), ddeep(16), ddeep(15, {}), ddeep(15, []), mdeep(16), mdeep(15, {}), mdeep(15, []),
        'a' * 256, ['a' * 256], {'a' * 256: 1}, 10 ** 10 - 1, -10 ** 10 + 1, 0, -0.0, 1e308, -1e308, 5e-324, 1.5, True, False, None, '',
        [], {}, {'a': [None, True, 1, 1.5, 'x', [], {}]}, '\x00\ud800\u00e9',
        [[0] * 255] * 3, [[0] * 255, [0] * 254, [0] * 254, [0] * 1], [[0]] * 511,
    ]
    for v in ok:
        assert r_why(v) == ''
        assert m.json_equal(v, v) is True
        got = m.patch_apply(v, [])
        assert _same(got, v)
        assert m.pointer_get(v, '') == v or v != v
    assert m.pointer_get(float('1e308'), '') == 1e308


def test_node_count_includes_containers_and_counts_in_depth_first_order():
    assert r_why([0] * 1022 + [object()]) == 'type'
    assert r_why([0] * 1023 + [object()]) == 'nodes'
    refuse('patch_apply', 'bad_type:doc', [0] * 1022 + [object()], [])
    refuse('patch_apply', 'bad_value:doc.nodes', [0] * 1023 + [object()], [])
    refuse('patch_apply', 'bad_value:doc.depth', [deep(17), object()], [])
    refuse('patch_apply', 'bad_type:doc', [object(), deep(17)], [])
    refuse('patch_apply', 'bad_value:doc.key', {1: object()}, [])
    refuse('patch_apply', 'bad_value:doc.key', {'a' * 257: object()}, [])
    refuse('patch_apply', 'bad_value:doc.str', {'a': 'b' * 257, 'c': object()}, [])
    refuse('patch_apply', 'bad_type:doc', {'c': object(), 'a': 'b' * 257}, [])
    refuse('patch_apply', 'bad_value:doc.float', [float('nan'), 10 ** 10], [])
    refuse('patch_apply', 'bad_value:doc.int', [10 ** 10, float('nan')], [])
    refuse('patch_apply', 'bad_value:doc.nodes', [[0] * 1023, object()], [])
    assert r_why([[0] * 510, [0] * 511]) == ''


def test_float_and_int_and_str_edges():
    for good in (0.0, -0.0, 1e-320, 1.7976931348623157e308, -1.7976931348623157e308):
        assert m.pointer_get(good, '') == good
    for bad in (float('inf'), -float('inf'), float('nan')):
        refuse('pointer_get', 'bad_value:doc.float', bad, '')
    for good in (0, 9999999999, -9999999999, 1, -1):
        assert m.pointer_get(good, '') == good and type(m.pointer_get(good, '')) is int
    for bad in (10 ** 10, -10 ** 10, 10 ** 10 + 1, 2 ** 64):
        refuse('pointer_get', 'bad_value:doc.int', bad, '')
    assert m.pointer_get(True, '') is True and m.pointer_get(False, '') is False
    assert m.pointer_get(None, '') is None
    assert m.pointer_get('a' * 256, '') == 'a' * 256
    refuse('pointer_get', 'bad_value:doc.str', 'a' * 257, '')
    assert m.pointer_get({'k' * 255: 1}, '/' + 'k' * 255) == 1


# ================= patch: structure =================
def _ap(doc, patch):
    return m.patch_apply(doc, patch)


def test_rfc6902_appendix_a_examples_exact():
    A = [
        ({'foo': 'bar'}, [{'op': 'add', 'path': '/baz', 'value': 'qux'}], {'baz': 'qux', 'foo': 'bar'}),
        ({'foo': ['bar', 'baz']}, [{'op': 'add', 'path': '/foo/1', 'value': 'qux'}], {'foo': ['bar', 'qux', 'baz']}),
        ({'baz': 'qux', 'foo': 'bar'}, [{'op': 'remove', 'path': '/baz'}], {'foo': 'bar'}),
        ({'foo': ['bar', 'qux', 'baz']}, [{'op': 'remove', 'path': '/foo/1'}], {'foo': ['bar', 'baz']}),
        ({'baz': 'qux', 'foo': 'bar'}, [{'op': 'replace', 'path': '/baz', 'value': 'boo'}], {'baz': 'boo', 'foo': 'bar'}),
        ({'foo': {'bar': 'baz', 'waldo': 'fred'}, 'qux': {'corge': 'grault'}},
         [{'op': 'move', 'from': '/foo/waldo', 'path': '/qux/thud'}],
         {'foo': {'bar': 'baz'}, 'qux': {'corge': 'grault', 'thud': 'fred'}}),
        ({'foo': ['all', 'grass', 'cows', 'eat']}, [{'op': 'move', 'from': '/foo/1', 'path': '/foo/3'}],
         {'foo': ['all', 'cows', 'eat', 'grass']}),
        ({'baz': 'qux', 'foo': ['a', 2, 'c']},
         [{'op': 'test', 'path': '/baz', 'value': 'qux'}, {'op': 'test', 'path': '/foo/1', 'value': 2}],
         {'baz': 'qux', 'foo': ['a', 2, 'c']}),
        ({'foo': 'bar'}, [{'op': 'add', 'path': '/child', 'value': {'grandchild': {}}}],
         {'foo': 'bar', 'child': {'grandchild': {}}}),
        ({'foo': 'bar'}, [{'op': 'add', 'path': '/baz', 'value': 'qux', 'xyz': 123}], {'foo': 'bar', 'baz': 'qux'}),
        ({'/': 9, '~1': 10}, [{'op': 'test', 'path': '/~01', 'value': 10}], {'/': 9, '~1': 10}),
        ({'foo': ['bar']}, [{'op': 'add', 'path': '/foo/-', 'value': ['abc', 'def']}], {'foo': ['bar', ['abc', 'def']]}),
    ]
    for doc, patch, want in A:
        before = copy.deepcopy(doc)
        got = _ap(doc, patch)
        assert _same(got, want) or (got == want and list(got) != [] ), (patch, got)
        assert doc == before
        assert m.patch_valid(patch) is True
        assert r_apply(doc, patch) == (want,)
    # key order is as the RFC example result: members keep insertion order, added last
    assert list(_ap({'foo': 'bar'}, [{'op': 'add', 'path': '/baz', 'value': 'qux'}])) == ['foo', 'baz']
    # A.9 error, A.12 error, A.15 error
    refuse('patch_apply', 'bad_value:apply.test', {'baz': 'qux'}, [{'op': 'test', 'path': '/baz', 'value': 'bar'}])
    refuse('patch_apply', 'bad_value:apply.parent', {'foo': 'bar'}, [{'op': 'add', 'path': '/baz/bat', 'value': 'qux'}])
    refuse('patch_apply', 'bad_value:apply.test', {'/': 9, '~1': 10}, [{'op': 'test', 'path': '/~01', 'value': '10'}])
    # Section 5 atomic example: a replace then a failing test changes nothing
    d = {'a': {'b': {'c': 'x'}}}
    refuse('patch_apply', 'bad_value:apply.test', d, [{'op': 'replace', 'path': '/a/b/c', 'value': 42},
                                                      {'op': 'test', 'path': '/a/b/c', 'value': 'C'}])
    assert d == {'a': {'b': {'c': 'x'}}}
    # Section 4.1 examples
    assert _ap({'a': {'foo': 1}}, [{'op': 'add', 'path': '/a/b', 'value': 9}]) == {'a': {'foo': 1, 'b': 9}}
    refuse('patch_apply', 'bad_value:apply.parent', {'q': {'bar': 2}}, [{'op': 'add', 'path': '/a/b', 'value': 9}])
    # Section 3 example sequence on a document where every step succeeds
    doc = {'a': {'b': {'c': 'foo', 'd': 'x'}}}
    patch = [{'op': 'test', 'path': '/a/b/c', 'value': 'foo'}, {'op': 'remove', 'path': '/a/b/c'},
             {'op': 'add', 'path': '/a/b/c', 'value': ['foo', 'bar']}, {'op': 'replace', 'path': '/a/b/c', 'value': 42},
             {'op': 'move', 'from': '/a/b/c', 'path': '/a/b/d'}, {'op': 'copy', 'from': '/a/b/d', 'path': '/a/b/e'}]
    assert _ap(doc, patch) == {'a': {'b': {'d': 42, 'e': 42}}}


def test_add_semantics_exact():
    assert _ap({}, [{'op': 'add', 'path': '', 'value': [1]}]) == [1]
    assert _ap(5, [{'op': 'add', 'path': '', 'value': None}]) is None
    assert _ap({'a': 1}, [{'op': 'add', 'path': '/a', 'value': 2}]) == {'a': 2}
    assert _ap({'a': 1}, [{'op': 'add', 'path': '/', 'value': 2}]) == {'a': 1, '': 2}
    assert _ap([1, 2], [{'op': 'add', 'path': '/0', 'value': 0}]) == [0, 1, 2]
    assert _ap([1, 2], [{'op': 'add', 'path': '/2', 'value': 3}]) == [1, 2, 3]
    assert _ap([1, 2], [{'op': 'add', 'path': '/-', 'value': 3}]) == [1, 2, 3]
    assert _ap([], [{'op': 'add', 'path': '/0', 'value': 3}]) == [3]
    assert _ap([], [{'op': 'add', 'path': '/-', 'value': 3}]) == [3]
    assert _ap({'a': []}, [{'op': 'add', 'path': '/a/-', 'value': 1}, {'op': 'add', 'path': '/a/-', 'value': 2}]) == {'a': [1, 2]}
    assert _ap({'-': 1}, [{'op': 'add', 'path': '/-', 'value': 2}]) == {'-': 2}
    assert _ap({'a': {}}, [{'op': 'add', 'path': '/a/0', 'value': 2}]) == {'a': {'0': 2}}
    for bad, code in (('/3', 'bad_value:apply.index'), ('/01', 'bad_value:apply.index'), ('/x', 'bad_value:apply.index'),
                      ('/-1', 'bad_value:apply.index'), ('/ 1', 'bad_value:apply.index'), ('/\u0661', 'bad_value:apply.index'),
                      ('/', 'bad_value:apply.index'), ('/9999999999', 'bad_value:apply.index'),
                      ('/99999999999', 'bad_value:apply.index'), ('/0/0', 'bad_value:apply.parent'),
                      ('/a/b', 'bad_value:apply.parent')):
        refuse('patch_apply', code, [1, 2], [{'op': 'add', 'path': bad, 'value': 0}])
    refuse('patch_apply', 'bad_value:apply.parent', 5, [{'op': 'add', 'path': '/a', 'value': 0}])
    refuse('patch_apply', 'bad_value:apply.parent', {'a': 'str'}, [{'op': 'add', 'path': '/a/b', 'value': 0}])
    refuse('patch_apply', 'bad_value:apply.parent', {'a': None}, [{'op': 'add', 'path': '/a/b', 'value': 0}])
    refuse('patch_apply', 'bad_value:apply.parent', {'a': True}, [{'op': 'add', 'path': '/a/-', 'value': 0}])
    refuse('patch_apply', 'bad_value:apply.parent', {}, [{'op': 'add', 'path': '/a/b/c', 'value': 0}])


def test_remove_replace_test_semantics_exact():
    assert _ap({'a': 1, 'b': 2}, [{'op': 'remove', 'path': '/a'}]) == {'b': 2}
    assert _ap([1, 2, 3], [{'op': 'remove', 'path': '/0'}]) == [2, 3]
    assert _ap([1, 2, 3], [{'op': 'remove', 'path': '/2'}]) == [1, 2]
    assert _ap({'a': [1]}, [{'op': 'remove', 'path': '/a/0'}]) == {'a': []}
    assert _ap({'': 1}, [{'op': 'remove', 'path': '/'}]) == {}
    for bad in ('/3', '/-', '/01', '/x', '/ 1', '/1/0', '/-1'):
        refuse('patch_apply', 'bad_value:apply.missing', [1, 2, 3][:3] if bad != '/3' else [1, 2, 3], [{'op': 'remove', 'path': bad}])
    refuse('patch_apply', 'bad_value:apply.missing', {}, [{'op': 'remove', 'path': '/a'}])
    refuse('patch_apply', 'bad_value:apply.missing', {'a': {}}, [{'op': 'remove', 'path': '/a/b'}])
    refuse('patch_apply', 'bad_value:apply.missing', {}, [{'op': 'remove', 'path': '/a/b'}])
    refuse('patch_apply', 'bad_value:apply.root', {}, [{'op': 'remove', 'path': ''}])
    refuse('patch_apply', 'bad_value:apply.root', 5, [{'op': 'remove', 'path': ''}])
    assert _ap({'a': 1}, [{'op': 'replace', 'path': '/a', 'value': [2]}]) == {'a': [2]}
    assert _ap([1, 2], [{'op': 'replace', 'path': '/1', 'value': 9}]) == [1, 9]
    assert _ap([1, 2], [{'op': 'replace', 'path': '/0', 'value': None}]) == [None, 2]
    assert _ap({'a': 1}, [{'op': 'replace', 'path': '', 'value': {'z': 0}}]) == {'z': 0}
    assert _ap(1, [{'op': 'replace', 'path': '', 'value': 2}]) == 2
    for bad in ('/2', '/-', '/01', '/x'):
        refuse('patch_apply', 'bad_value:apply.missing', [1, 2], [{'op': 'replace', 'path': bad, 'value': 0}])
    refuse('patch_apply', 'bad_value:apply.missing', {}, [{'op': 'replace', 'path': '/a', 'value': 0}])
    refuse('patch_apply', 'bad_value:apply.missing', {}, [{'op': 'replace', 'path': '/a/b', 'value': 0}])
    # replace keeps the member position, which a remove plus add would not
    assert list(_ap({'a': 1, 'b': 2, 'c': 3}, [{'op': 'replace', 'path': '/a', 'value': 0}])) == ['a', 'b', 'c']
    assert _ap({'a': 1}, [{'op': 'test', 'path': '/a', 'value': 1.0}]) == {'a': 1}
    assert _ap({'a': 1}, [{'op': 'test', 'path': '', 'value': {'a': 1}}]) == {'a': 1}
    assert _ap({'a': [None]}, [{'op': 'test', 'path': '/a/0', 'value': None}]) == {'a': [None]}
    refuse('patch_apply', 'bad_value:apply.test', {'a': 1}, [{'op': 'test', 'path': '/a', 'value': True}])
    refuse('patch_apply', 'bad_value:apply.test', {'a': 0}, [{'op': 'test', 'path': '/a', 'value': False}])
    refuse('patch_apply', 'bad_value:apply.test', {'a': None}, [{'op': 'test', 'path': '/a', 'value': 0}])
    refuse('patch_apply', 'bad_value:apply.test', {'a': [1]}, [{'op': 'test', 'path': '/a', 'value': [1, 2]}])
    refuse('patch_apply', 'bad_value:apply.test', {'a': 1}, [{'op': 'test', 'path': '', 'value': {'a': 2}}])
    refuse('patch_apply', 'bad_value:apply.missing', {'a': 1}, [{'op': 'test', 'path': '/b', 'value': None}])
    refuse('patch_apply', 'bad_value:apply.missing', [1], [{'op': 'test', 'path': '/-', 'value': None}])
    refuse('patch_apply', 'bad_value:apply.missing', [1], [{'op': 'test', 'path': '/1', 'value': None}])


def test_move_and_copy_semantics_exact():
    assert _ap({'a': 1}, [{'op': 'move', 'from': '/a', 'path': '/b'}]) == {'b': 1}
    assert _ap({'a': 1}, [{'op': 'move', 'from': '/a', 'path': '/a'}]) == {'a': 1}
    assert _ap([1, 2, 3], [{'op': 'move', 'from': '/1', 'path': '/1'}]) == [1, 2, 3]
    assert _ap([1, 2, 3], [{'op': 'move', 'from': '/0', 'path': '/-'}]) == [2, 3, 1]
    assert _ap([1, 2, 3], [{'op': 'move', 'from': '/0', 'path': '/2'}]) == [2, 3, 1]
    assert _ap([1, 2, 3], [{'op': 'move', 'from': '/2', 'path': '/0'}]) == [3, 1, 2]
    assert _ap([1, 2, 3], [{'op': 'move', 'from': '/0', 'path': '/1'}]) == [2, 1, 3]
    refuse('patch_apply', 'bad_value:apply.index', [1, 2, 3], [{'op': 'move', 'from': '/0', 'path': '/3'}])
    assert _ap({'a': [1, 2], 'b': []}, [{'op': 'move', 'from': '/a/0', 'path': '/b/0'}]) == {'a': [2], 'b': [1]}
    assert _ap({'a': {'b': 1}}, [{'op': 'move', 'from': '/a/b', 'path': '/c'}]) == {'a': {}, 'c': 1}
    assert _ap({'a': {'b': 1}}, [{'op': 'move', 'from': '/a', 'path': '/c'}]) == {'c': {'b': 1}}
    # a sibling with the from name as a prefix is not a child
    refuse('patch_apply', 'bad_value:apply.parent', {'a': 1, 'ab': 2}, [{'op': 'move', 'from': '/a', 'path': '/ab/x'}])
    assert _ap({'a': 1, 'ab': {}}, [{'op': 'move', 'from': '/a', 'path': '/ab/x'}]) == {'ab': {'x': 1}}
    assert _ap({'a': 1, 'b': {}}, [{'op': 'move', 'from': '/a', 'path': '/b/a'}]) == {'b': {'a': 1}}
    refuse('patch_apply', 'bad_value:apply.child', {'a': {'b': 1}}, [{'op': 'move', 'from': '/a', 'path': '/a/b'}])
    refuse('patch_apply', 'bad_value:apply.child', {'a': {'b': 1}}, [{'op': 'move', 'from': '/a', 'path': '/a/c'}])
    refuse('patch_apply', 'bad_value:apply.child', {'a': {'b': 1}}, [{'op': 'move', 'from': '/a', 'path': '/a/b/c'}])
    refuse('patch_apply', 'bad_value:apply.child', {}, [{'op': 'move', 'from': '/x', 'path': '/x/y'}])
    refuse('patch_apply', 'bad_value:apply.child', {'a': 1}, [{'op': 'move', 'from': '', 'path': '/a'}])
    refuse('patch_apply', 'bad_value:apply.root', {'a': 1}, [{'op': 'move', 'from': '', 'path': ''}])
    refuse('patch_apply', 'bad_value:apply.from', {}, [{'op': 'move', 'from': '/x', 'path': '/y'}])
    refuse('patch_apply', 'bad_value:apply.from', {}, [{'op': 'move', 'from': '/x', 'path': '/q/r'}])
    refuse('patch_apply', 'bad_value:apply.from', [1], [{'op': 'move', 'from': '/-', 'path': '/0'}])
    refuse('patch_apply', 'bad_value:apply.from', [1], [{'op': 'move', 'from': '/1', 'path': '/0'}])
    refuse('patch_apply', 'bad_value:apply.parent', {'a': 1}, [{'op': 'move', 'from': '/a', 'path': '/q/r'}])
    refuse('patch_apply', 'bad_value:apply.parent', {'a': 1}, [{'op': 'move', 'from': '/a', 'path': '/b/r'}])
    # copy
    assert _ap({'a': [1, {'b': 2}]}, [{'op': 'copy', 'from': '/a', 'path': '/c'}]) == {'a': [1, {'b': 2}], 'c': [1, {'b': 2}]}
    assert _ap([1, 2], [{'op': 'copy', 'from': '/0', 'path': '/-'}]) == [1, 2, 1]
    assert _ap([1, 2], [{'op': 'copy', 'from': '/1', 'path': '/0'}]) == [2, 1, 2]
    assert _ap({'a': 1}, [{'op': 'copy', 'from': '/a', 'path': '/a'}]) == {'a': 1}
    assert _ap({'a': 1}, [{'op': 'copy', 'from': '', 'path': '/b'}]) == {'a': 1, 'b': {'a': 1}}
    assert _ap({'a': 1}, [{'op': 'copy', 'from': '', 'path': ''}]) == {'a': 1}
    assert _ap({'a': {'b': 1}}, [{'op': 'copy', 'from': '/a', 'path': '/a/c'}]) == {'a': {'b': 1, 'c': {'b': 1}}}
    refuse('patch_apply', 'bad_value:apply.from', {}, [{'op': 'copy', 'from': '/x', 'path': '/y'}])
    refuse('patch_apply', 'bad_value:apply.from', {}, [{'op': 'copy', 'from': '/x', 'path': '/q/r'}])
    refuse('patch_apply', 'bad_value:apply.from', [1], [{'op': 'copy', 'from': '/-', 'path': '/0'}])
    refuse('patch_apply', 'bad_value:apply.parent', {'a': 1}, [{'op': 'copy', 'from': '/a', 'path': '/q/r'}])
    refuse('patch_apply', 'bad_value:apply.index', [1], [{'op': 'copy', 'from': '/0', 'path': '/5'}])


def test_inputs_never_mutated_and_result_shares_nothing():
    doc = {'a': [1, {'b': [2, 3]}], 'c': {'d': [4]}}
    patch = [{'op': 'add', 'path': '/e', 'value': {'f': [5]}}, {'op': 'copy', 'from': '/a', 'path': '/g'},
             {'op': 'move', 'from': '/c', 'path': '/h'}, {'op': 'replace', 'path': '/a/1/b/0', 'value': [6]},
             {'op': 'remove', 'path': '/a/0'}, {'op': 'add', 'path': '/i', 'value': {'f': [5]}}]
    d0, p0 = copy.deepcopy(doc), copy.deepcopy(patch)
    got = _ap(doc, patch)
    assert doc == d0 and patch == p0 and _same(doc, d0) and _same(patch, p0)
    ids = {id(n) for n in _nodes(doc) + _nodes(patch)}
    for n in _nodes(got):
        assert id(n) not in ids
    allg = _nodes(got)
    assert len({id(n) for n in allg}) == len(allg)
    got['g'][1]['b'].append(99)
    assert got['a'] == [{'b': [[6], 3]}] and doc == d0
    # refusal returns nothing and leaves both unchanged
    bad = patch + [{'op': 'test', 'path': '/zzz', 'value': 1}]
    refuse('patch_apply', 'bad_value:apply.missing', doc, bad)
    assert doc == d0 and patch == p0
    # the same value object used in two operations gives two independent copies
    shared = {'k': [1]}
    out = _ap({}, [{'op': 'add', 'path': '/a', 'value': shared}, {'op': 'add', 'path': '/b', 'value': shared}])
    assert out['a'] == out['b'] == shared and out['a'] is not out['b'] and out['a'] is not shared
    assert out['a']['k'] is not out['b']['k'] and out['a']['k'] is not shared['k']
    out = _ap(shared, [])
    assert out == shared and out is not shared and out['k'] is not shared['k']
    # scalars may be shared, they are immutable
    assert _ap('s', []) == 's'


def test_result_caps_after_every_operation():
    d = {'a': deep(15)}
    got = _ap(d, [{'op': 'add', 'path': '/b', 'value': deep(15)}])
    assert r_why(got) == ''
    refuse('patch_apply', 'bad_value:result.depth', d, [{'op': 'add', 'path': '/b', 'value': deep(16)}])
    inner = '/0' * 15
    got = _ap(deep(15), [{'op': 'add', 'path': inner, 'value': [0]}])
    assert r_why(got) == ''
    refuse('patch_apply', 'bad_value:result.depth', deep(15), [{'op': 'add', 'path': inner, 'value': [[0]]}])
    refuse('patch_apply', 'bad_value:result.depth', deep(15), [{'op': 'add', 'path': inner, 'value': {'k': [0]}}])
    dinner = '/k' * 15
    got = _ap(ddeep(15), [{'op': 'add', 'path': dinner, 'value': {}}])
    assert r_why(got) == ''
    refuse('patch_apply', 'bad_value:result.depth', ddeep(15), [{'op': 'add', 'path': dinner, 'value': {'k': {}}}])
    refuse('patch_apply', 'bad_value:result.depth', ddeep(16), [{'op': 'copy', 'from': '', 'path': '/j'}])
    base = {'a': [0] * 600}
    got = _ap(base, [{'op': 'add', 'path': '/b', 'value': [0] * 421}])
    assert r_why(got) == '' and len(got['b']) == 421
    refuse('patch_apply', 'bad_value:result.nodes', base, [{'op': 'add', 'path': '/b', 'value': [0] * 422}])
    refuse('patch_apply', 'bad_value:result.nodes', {'a': [0] * 400},
           [{'op': 'copy', 'from': '/a', 'path': '/b'}, {'op': 'copy', 'from': '/a', 'path': '/c'}])
    assert r_why(_ap({'a': [0] * 510}, [{'op': 'copy', 'from': '/a', 'path': '/b'}])) == ''
    refuse('patch_apply', 'bad_value:result.nodes', {'a': [0] * 511}, [{'op': 'copy', 'from': '/a', 'path': '/b'}])
    refuse('patch_apply', 'bad_value:result.nodes', [0] * 1023, [{'op': 'add', 'path': '/-', 'value': 0}])
    assert len(_ap([0] * 1022, [{'op': 'add', 'path': '/-', 'value': 0}])) == 1023
    # an intermediate over-cap result is refused even when a later operation would shrink it back
    refuse('patch_apply', 'bad_value:result.nodes', {'a': [0] * 1000},
           [{'op': 'add', 'path': '/b', 'value': [0] * 100}, {'op': 'remove', 'path': '/b'}])
    # a copy of the root into itself nests one level
    assert _ap({'a': [1]}, [{'op': 'copy', 'from': '', 'path': '/b'}]) == {'a': [1], 'b': {'a': [1]}}
    refuse('patch_apply', 'bad_value:result.depth', deep(16), [{'op': 'copy', 'from': '', 'path': '/0'}])


# ================= patch structure =================
def _struct(patch, code, doc=None):
    refuse('patch_apply', code, {} if doc is None else doc, patch)
    assert m.patch_valid(patch) is False


_OKOP = {'op': 'add', 'path': '/a', 'value': 1}


def test_patch_structure_refusals_exact():
    for bad in ('x', (), {}, None, 1, b'[]', ({'op': 'test', 'path': '', 'value': 1},), type('L', (list,), {})()):
        refuse('patch_apply', 'bad_type:patch', {}, bad)
        refuse('patch_valid', 'bad_type:patch', bad)
    _struct([_OKOP] * 65, 'bad_value:patch.length')
    assert m.patch_valid([{'op': 'test', 'path': '', 'value': 1}] * 64) is True
    assert m.patch_valid([]) is True
    assert _ap({}, [{'op': 'test', 'path': '', 'value': {}}] * 64) == {}
    for bad in (None, 1, 'op', [], (), type('D', (dict,), {})(), _Liar(), b'x'):
        _struct([bad], 'bad_type:op')
    for k in (1, None, b'op', (1,), 1.5, True, _StrSub('zz')):
        _struct([{k: 1, 'op': 'add', 'path': '/a', 'value': 1}], 'bad_type:op.key')
        _struct([{'op': 'add', 'path': '/a', 'value': 1, k: 1}], 'bad_type:op.key')
    _struct([{}], 'bad_value:op.op.missing')
    _struct([{'path': '/a', 'value': 1}], 'bad_value:op.op.missing')
    _struct([{'OP': 'add', 'path': '/a', 'value': 1}], 'bad_value:op.op.missing')
    for bad in (1, None, ['add'], b'add', _StrSub('add'), True, {'a': 1}):
        _struct([{'op': bad, 'path': '/a', 'value': 1}], 'bad_type:op.op')
    for bad in ('', 'Add', 'ADD', 'add ', ' add', 'append', 'patch', 'rem', 'addx', 'move\x00', 'test\n', 'copy ', 'x'):
        _struct([{'op': bad, 'path': '/a', 'value': 1}], 'bad_value:op.op.unknown')
    for name in ('add', 'remove', 'replace', 'move', 'copy', 'test'):
        _struct([{'op': name}], 'bad_value:op.path.missing')
        _struct([{'op': name, 'Path': '/a'}], 'bad_value:op.path.missing')
        for bad in (None, 1, ['/a'], b'/a', _StrSub('/a'), True):
            _struct([{'op': name, 'path': bad, 'from': '/b', 'value': 1}], 'bad_type:op.path')
        _struct([{'op': name, 'path': 'a' * 257, 'from': '/b', 'value': 1}], 'bad_value:op.path.length')
        _struct([{'op': name, 'path': 'a', 'from': '/b', 'value': 1}], 'bad_value:op.path.syntax')
        _struct([{'op': name, 'path': '/~', 'from': '/b', 'value': 1}], 'bad_value:op.path.syntax')
        _struct([{'op': name, 'path': '/' * 33, 'from': '/b', 'value': 1}], 'bad_value:op.path.tokens')
    for name in ('move', 'copy'):
        _struct([{'op': name, 'path': '/a'}], 'bad_value:op.from.missing')
        _struct([{'op': name, 'path': '/a', 'From': '/a'}], 'bad_value:op.from.missing')
        for bad in (None, 1, ['/a'], b'/a', _StrSub('/a'), True):
            _struct([{'op': name, 'path': '/a', 'from': bad}], 'bad_type:op.from')
        _struct([{'op': name, 'path': '/a', 'from': 'a' * 257}], 'bad_value:op.from.length')
        _struct([{'op': name, 'path': '/a', 'from': 'a'}], 'bad_value:op.from.syntax')
        _struct([{'op': name, 'path': '/a', 'from': '/~3'}], 'bad_value:op.from.syntax')
        _struct([{'op': name, 'path': '/a', 'from': '/' * 33}], 'bad_value:op.from.tokens')
    for name in ('add', 'replace', 'test'):
        _struct([{'op': name, 'path': '/a'}], 'bad_value:op.value.missing')
        _struct([{'op': name, 'path': '/a', 'Value': 1}], 'bad_value:op.value.missing')
        _struct([{'op': name, 'path': '/a', 'from': '/a'}], 'bad_value:op.value.missing')
    # a null value is a present value
    assert _ap({}, [{'op': 'add', 'path': '/a', 'value': None}]) == {'a': None}
    assert _ap({'a': 1}, [{'op': 'replace', 'path': '/a', 'value': None}]) == {'a': None}


def test_undefined_members_ignored_without_being_inspected():
    junk = [object(), _Liar(), deep(40), float('nan'), 10 ** 400, b'x', _StrSub('x'), [object()], {1: 2}, None, ('a',)]
    for j in junk:
        assert _ap({'a': 1}, [{'op': 'add', 'path': '/b', 'value': 2, 'xyz': j}]) == {'a': 1, 'b': 2}
        assert _ap({'a': 1}, [{'op': 'add', 'path': '/b', 'value': 2, 'from': j}]) == {'a': 1, 'b': 2}
        assert _ap({'a': 1}, [{'op': 'replace', 'path': '/a', 'value': 2, 'from': j}]) == {'a': 2}
        assert _ap({'a': 1}, [{'op': 'test', 'path': '/a', 'value': 1, 'from': j}]) == {'a': 1}
        assert _ap({'a': 1, 'b': 2}, [{'op': 'remove', 'path': '/a', 'from': j, 'value': j}]) == {'b': 2}
        assert _ap({'a': 1}, [{'op': 'move', 'from': '/a', 'path': '/b', 'value': j}]) == {'b': 1}
        assert _ap({'a': 1}, [{'op': 'copy', 'from': '/a', 'path': '/b', 'value': j}]) == {'a': 1, 'b': 1}
        assert m.patch_valid([{'op': 'remove', 'path': '/a', 'value': j, 'from': j, 'zz': j}]) is True
    # member order does not matter
    for op in ({'value': 1, 'path': '/a', 'op': 'add'}, {'path': '/a', 'value': 1, 'op': 'add'}):
        assert _ap({}, [op]) == {'a': 1}


def test_structure_checked_for_the_whole_patch_before_any_operation_and_in_order():
    doc = {'a': 1}
    # an apply failure in op 0 loses to a structure failure in op 1
    patch = [{'op': 'test', 'path': '/a', 'value': 2}, {'op': 'bogus', 'path': '/a'}]
    refuse('patch_apply', 'bad_value:op.op.unknown', doc, patch)
    patch = [{'op': 'remove', 'path': '/zzz'}, {'op': 'add', 'path': 'x', 'value': 1}]
    refuse('patch_apply', 'bad_value:op.path.syntax', doc, patch)
    # earlier structure failure wins over later ones
    refuse('patch_apply', 'bad_type:op', doc, [1, {'op': 'bogus'}])
    refuse('patch_apply', 'bad_value:op.op.missing', doc, [{}, 1])
    refuse('patch_apply', 'bad_value:op.path.syntax', doc, [{'op': 'add', 'path': 'x', 'value': 1}, {}])
    # inside one operation: op, path, from, value
    refuse('patch_apply', 'bad_type:op.key', doc, [{1: 1}])
    refuse('patch_apply', 'bad_type:op.key', doc, [{1: 1, 'op': 'bogus'}])
    refuse('patch_apply', 'bad_type:op.op', doc, [{'op': 1}])
    refuse('patch_apply', 'bad_value:op.op.unknown', doc, [{'op': 'x'}])
    refuse('patch_apply', 'bad_value:op.path.missing', doc, [{'op': 'move'}])
    refuse('patch_apply', 'bad_type:op.path', doc, [{'op': 'move', 'path': 1}])
    refuse('patch_apply', 'bad_value:op.path.length', doc, [{'op': 'move', 'path': '~' * 300}])
    refuse('patch_apply', 'bad_value:op.path.length', doc, [{'op': 'move', 'path': '/~' + '/' * 300}])
    refuse('patch_apply', 'bad_value:op.path.syntax', doc, [{'op': 'move', 'path': '/~' + '/' * 33}])
    refuse('patch_apply', 'bad_value:op.path.tokens', doc, [{'op': 'move', 'path': '/' * 33}])
    refuse('patch_apply', 'bad_value:op.from.missing', doc, [{'op': 'move', 'path': '/'}])
    refuse('patch_apply', 'bad_type:op.from', doc, [{'op': 'move', 'path': '/', 'from': 1}])
    refuse('patch_apply', 'bad_value:op.from.length', doc, [{'op': 'move', 'path': '/', 'from': '~' * 300}])
    refuse('patch_apply', 'bad_value:op.from.syntax', doc, [{'op': 'move', 'path': '/', 'from': '/~' + '/' * 33}])
    refuse('patch_apply', 'bad_value:op.from.tokens', doc, [{'op': 'move', 'path': '/', 'from': '/' * 33}])
    refuse('patch_apply', 'bad_value:op.path.syntax', doc, [{'op': 'move', 'path': 'x', 'from': 1}])
    refuse('patch_apply', 'bad_value:op.value.missing', doc, [{'op': 'add', 'path': '/'}])
    refuse('patch_apply', 'bad_type:op.value', doc, [{'op': 'add', 'path': '/', 'value': object()}])
    refuse('patch_apply', 'bad_value:op.path.syntax', doc, [{'op': 'add', 'path': 'x', 'value': object()}])
    # the document is checked before the patch
    refuse('patch_apply', 'bad_type:doc', object(), 'not a list')
    refuse('patch_apply', 'bad_value:doc.nodes', [0] * 1024, 'not a list')
    refuse('patch_apply', 'bad_type:patch', {}, 'not a list')
    # the op value is checked as a value, node cap included
    assert m.patch_valid([{'op': 'add', 'path': '', 'value': [0] * 1023}]) is True
    assert m.patch_valid([{'op': 'add', 'path': '', 'value': [0] * 1024}]) is False
    assert m.patch_valid([{'op': 'add', 'path': '', 'value': deep(16)}]) is True
    assert m.patch_valid([{'op': 'add', 'path': '', 'value': deep(17)}]) is False


def test_patch_valid_returns_exact_bool():
    for good in ([], [_OKOP], [{'op': 'remove', 'path': ''}], [{'op': 'move', 'from': '/a', 'path': '/b'}],
                 [{'op': 'copy', 'from': '', 'path': ''}], [{'op': 'test', 'path': '/a/-', 'value': 0}],
                 [{'op': 'move', 'from': '/a', 'path': '/a/b'}]):
        assert m.patch_valid(good) is True
    for bad in ([1], [{}], [{'op': 'x', 'path': ''}], [{'op': 'add', 'path': 'a', 'value': 1}], [{'op': 'add', 'path': ''}]):
        assert m.patch_valid(bad) is False


# ================= exact-type guards at every site =================
class _DictSub(dict):
    def __iter__(self):
        _Spy.calls.append('d_iter')
        return dict.__iter__(self)

    def __getitem__(self, k):
        _Spy.calls.append('d_get')
        return dict.__getitem__(self, k)

    def __contains__(self, k):
        _Spy.calls.append('d_in')
        return True

    def __len__(self):
        _Spy.calls.append('d_len')
        return 1


class _ListSub(list):
    def __iter__(self):
        _Spy.calls.append('l_iter')
        return list.__iter__(self)

    def __getitem__(self, k):
        _Spy.calls.append('l_get')
        return list.__getitem__(self, k)

    def __len__(self):
        _Spy.calls.append('l_len')
        return 1


class _TupSub(tuple):
    def __iter__(self):
        _Spy.calls.append('t_iter')
        return tuple.__iter__(self)

    def __len__(self):
        _Spy.calls.append('t_len')
        return 1


class _KeyLiar(str):
    def __eq__(self, o):
        _Spy.calls.append('k_eq')
        return True

    def __hash__(self):
        _Spy.calls.append('k_hash')
        return 1


class _FloatSub(float):
    def __eq__(self, o):
        _Spy.calls.append('f_eq')
        return True

    __hash__ = float.__hash__


def test_exact_types_everywhere_and_no_dunder_ever_invoked():
    del _Spy.calls[:]
    hostile = [_StrSub('x'), _IntSub(1), _IntSub(0), _FloatSub(1.5), _DictSub(), _ListSub(), _TupSub(), _Liar(), _KeyLiar('k'),
               object(), b'x', bytearray(b'x'), (1,), {1}, 1j]
    for h in hostile:
        refuse('pointer_get', 'bad_type:doc', h, '')
        refuse('pointer_get', 'bad_type:doc', [h], '')
        refuse('pointer_get', 'bad_type:doc', {'a': h}, '')
        refuse('pointer_get', 'bad_type:doc', [[{'a': [h]}]], '')
        refuse('patch_apply', 'bad_type:doc', h, [])
        refuse('patch_apply', 'bad_type:doc', {'a': [h]}, [])
        refuse('json_equal', 'bad_type:a', h, 1)
        refuse('json_equal', 'bad_type:b', 1, h)
        refuse('json_equal', 'bad_type:a', [h], [h])
        refuse('patch_apply', 'bad_type:op.value', {}, [{'op': 'add', 'path': '/a', 'value': h}])
        refuse('patch_apply', 'bad_type:op.value', {}, [{'op': 'replace', 'path': '', 'value': [h]}])
        refuse('patch_apply', 'bad_type:op.value', {}, [{'op': 'test', 'path': '', 'value': {'k': h}}])
        refuse('patch_apply', 'bad_type:patch', {}, h)
        refuse('patch_valid', 'bad_type:patch', h)
        refuse('patch_apply', 'bad_type:op', {}, [h])
        refuse('pointer_parse', 'bad_type:text', h)
        refuse('pointer_valid', 'bad_type:text', h)
        refuse('pointer_get', 'bad_type:text', {}, h)
        refuse('array_index', 'bad_type:token', h)
        if type(h) is not tuple:
            refuse('pointer_format', 'bad_type:tokens', h)
        if type(h) is not str:
            refuse('pointer_format', 'bad_type:token', (h,))
        refuse('pointer_format', 'bad_type:token', ('a', h))
        if type(h) is not str:
            refuse('patch_apply', 'bad_type:op.op', {}, [{'op': h, 'path': ''}])
        refuse('patch_apply', 'bad_type:op.path', {}, [{'op': 'add', 'path': h, 'value': 1}])
        refuse('patch_apply', 'bad_type:op.from', {}, [{'op': 'move', 'path': '', 'from': h}])
        refuse('patch_apply', 'bad_type:op.from', {}, [{'op': 'copy', 'path': '', 'from': h}])
    for h in hostile:
        if type(h) is str or not _hashable(h):
            continue
        op = {h: 1, 'op': 'add', 'path': '', 'value': 1}
        doc = {h: 1}
        del _Spy.calls[:]
        refuse('patch_apply', 'bad_type:op.key', {}, [op])
        refuse('patch_apply', 'bad_value:doc.key', doc, [])
        refuse('json_equal', 'bad_value:a.key', doc, 1)
        assert _Spy.calls == []
    # bool is never a number, a number is never a bool
    refuse('pointer_get', 'bad_type:text', {}, True)
    refuse('array_index', 'bad_type:token', 1)
    refuse('pointer_valid', 'bad_type:text', 0)
    refuse('pointer_format', 'bad_type:token', (1,))
    refuse('pointer_format', 'bad_type:tokens', ['a'])
    assert _Spy.calls == []
    # the good path is clean too
    assert m.patch_apply({'a': [1]}, [{'op': 'add', 'path': '/a/-', 'value': 2.5}]) == {'a': [1, 2.5]}
    assert _Spy.calls == []


def _hashable(h):
    try:
        hash(h)
    except TypeError:
        return False
    return True


# ================= differential run against the reference =================
def _rand_doc(rnd, d=0):
    k = rnd.randrange(0, 10 if d < 3 else 6)
    if k == 0:
        return None
    if k == 1:
        return rnd.choice([True, False])
    if k == 2:
        return rnd.choice([0, 1, 2, 5])
    if k == 3:
        return rnd.choice(['', 'a', 'b', '0', '1', '-', '~', '/'])
    if k == 4 or k == 5:
        return rnd.choice([1.5, 2.0, 'x'])
    if k in (6, 7, 8):
        return [_rand_doc(rnd, d + 1) for _ in range(rnd.randrange(0, 4))]
    return {rnd.choice(['a', 'b', '0', '1', '', '-', 'c/d', 'e~f']): _rand_doc(rnd, d + 1) for _ in range(rnd.randrange(0, 4))}


def _paths(doc, pre=()):
    out = [pre]
    if type(doc) is dict:
        for k in doc:
            out += _paths(doc[k], pre + (k,))
    elif type(doc) is list:
        for i in range(len(doc)):
            out += _paths(doc[i], pre + (str(i),))
    return out


def _enc(toks):
    return ''.join('/' + t.replace('~', '~0').replace('/', '~1') for t in toks)


def _rand_ptr(rnd, doc):
    ps = _paths(doc)
    base = list(rnd.choice(ps))
    r = rnd.randrange(8)
    if r == 0 and base:
        base[-1] = rnd.choice(['0', '1', '2', '-', '01', 'a', 'zz', ''])
    elif r == 1:
        base.append(rnd.choice(['0', '-', 'a', '']))
    elif r == 2 and base:
        base.pop()
    elif r == 3:
        return rnd.choice(['', '/', '/a', '/-', '/0', '/1', '/a/b', '/a/-', '/0/0'])
    return _enc(base)


def _rand_patch(rnd, doc):
    ops = []
    for _ in range(rnd.randrange(0, 5)):
        name = rnd.choice(['add', 'add', 'remove', 'replace', 'move', 'copy', 'test'])
        op = {'op': name, 'path': _rand_ptr(rnd, doc)}
        if name in ('move', 'copy'):
            op['from'] = _rand_ptr(rnd, doc)
        if name in ('add', 'replace', 'test'):
            op['value'] = rnd.choice([_rand_doc(rnd, 2), _rand_doc(rnd, 2), rnd.choice([doc, 1, None, 'a', [], {}])])
        ops.append(op)
    return ops


def test_patch_apply_matches_reference_on_random_documents_and_patches():
    rnd = random.Random(6902)
    ok = bad = 0
    codes = set()
    for _ in range(6000):
        doc = _rand_doc(rnd)
        if r_why(doc):
            continue
        patch = _rand_patch(rnd, doc)
        if rnd.randrange(3) == 0 and patch:
            # make later ops depend on earlier ones: apply the first op reference-side and draw paths from the result
            first = r_apply(doc, patch[:1])
            if type(first) is tuple:
                patch += _rand_patch(rnd, first[0])
        d0, p0 = copy.deepcopy(doc), copy.deepcopy(patch)
        want = r_apply(doc, patch)
        if type(want) is str:
            refuse('patch_apply', want, doc, patch)
            bad += 1
            codes.add(want)
        else:
            got = m.patch_apply(doc, patch)
            assert _same(got, want[0]) or (got == want[0] and r_eq(got, want[0])), (doc, patch, got, want)
            ok += 1
        assert m.patch_valid(patch) is True
        assert _same(doc, d0) and _same(patch, p0)
    assert ok > 1200 and bad > 1200
    assert codes >= {'bad_value:apply.parent', 'bad_value:apply.index', 'bad_value:apply.missing', 'bad_value:apply.from',
                     'bad_value:apply.test', 'bad_value:apply.root', 'bad_value:apply.child'}


def test_pointer_get_matches_reference_on_random_documents():
    rnd = random.Random(6901)
    hit = miss = 0
    for _ in range(6000):
        doc = _rand_doc(rnd)
        ptr = _rand_ptr(rnd, doc)
        toks = r_parse(ptr)
        want = r_find(doc, toks)
        if want is None:
            refuse('pointer_get', 'bad_value:pointer.missing', doc, ptr)
            miss += 1
        else:
            got = m.pointer_get(doc, ptr)
            assert _same(got, want[0])
            hit += 1
    assert hit > 1000 and miss > 1000


def _rand_op_junk(rnd):
    return rnd.choice([None, 1, 'x', [], {}, 'add', True, 1.5, ['a'], {'op': 'add'}, b'x'])


def test_patch_valid_agrees_with_patch_apply_structure_checks():
    rnd = random.Random(77)
    structure = ('bad_type:patch', 'bad_value:patch.length', 'bad_type:op', 'bad_type:op.key', 'bad_value:op.op.', 'bad_type:op.op',
                 'bad_value:op.path.', 'bad_type:op.path', 'bad_value:op.from.', 'bad_type:op.from', 'bad_value:op.value.',
                 'bad_type:op.value')
    seen = [0, 0]
    for _ in range(5000):
        patch = []
        for _ in range(rnd.randrange(0, 4)):
            op = {}
            for k in ('op', 'path', 'from', 'value'):
                if rnd.randrange(5):
                    if k == 'op':
                        op[k] = rnd.choice(['add', 'remove', 'replace', 'move', 'copy', 'test', 'x', _rand_op_junk(rnd)])
                    elif k == 'value':
                        op[k] = rnd.choice([None, 1, 'v', [1], {'k': 1}, _rand_op_junk(rnd)])
                    else:
                        op[k] = rnd.choice(['', '/a', '/a/0', '/~0', 'a', '/~', _rand_op_junk(rnd)])
            patch.append(op)
        bad_value = any(r_why(op.get('value')) for op in patch if op.get('op') in ('add', 'replace', 'test') and 'value' in op)
        try:
            m.patch_apply({'a': [1]}, patch)
            struct_fail = False
        except ValueError as e:
            msg = str(e)
            tail = msg.split('patch_apply:', 1)[1]
            struct_fail = tail.startswith(structure)
        valid = m.patch_valid(patch)
        assert valid is (not struct_fail), patch
        seen[valid] += 1
        if bad_value:
            assert valid is False
    assert seen[0] > 500 and seen[1] > 500
# ---------- registry guard battery ----------

def _exec_guarded(import_exc=None, import_result=_MISSING, spec_result=None, spec_exc=None):
    path = pathlib.Path(m.__file__)
    src = path.read_text()
    real_import = builtins.__import__
    real_find = iu.find_spec
    seen = []
    full_calls = []
    saved = sys.modules.pop(REG, _MISSING)

    def fake_import(name, *a, **k):
        if name == REG:
            if import_exc is not None:
                raise import_exc
            if import_result is not _MISSING:
                return import_result
        return real_import(name, *a, **k)

    def fake_find(name, *a, **k):
        seen.append(name)
        full_calls.append(((name,) + a, k))
        if spec_exc is not None:
            raise spec_exc
        return spec_result

    ns = {'__name__': 'guarded_probe'}
    builtins.__import__ = fake_import
    iu.find_spec = fake_find
    try:
        exec(compile(src, str(path), 'exec'), ns)
    finally:
        assert builtins.__import__ is fake_import, '__import__ clobbered mid-probe'
        assert iu.find_spec is fake_find, 'find_spec clobbered mid-probe'
        builtins.__import__ = real_import
        iu.find_spec = real_find
        sys.modules.pop(REG, None)
        if saved is not _MISSING:
            sys.modules[REG] = saved
    assert builtins.__import__ is real_import and iu.find_spec is real_find
    return ns, seen, full_calls


def _mnfe(name, msg='no such module'):
    e = ModuleNotFoundError(msg)
    e.name = name
    return e


def test_guard_absent_registry_falls_back_via_find_spec():
    ns, seen, fc = _exec_guarded(import_exc=_mnfe(REG), spec_result=None)
    assert seen == [REG] and fc == [((REG,), {})]
    with pytest.raises(ValueError) as e:
        ns['pointer_valid'](None)
    assert str(e.value) == 'P235:pointer_valid:bad_type:text'


def test_guard_other_module_missing_propagates_exact_object():
    exc = _mnfe('some_other_dep_pin')
    with pytest.raises(ModuleNotFoundError) as e:
        _exec_guarded(import_exc=exc)
    assert e.value is exc


@pytest.mark.parametrize('name', [None, 'x.' + REG, REG + '.sub', 'x.' + REG + '.y', REG.upper(), REG.replace('p235', 'P235'),
                                  'app.modules.instinct_doc', 'app', LEAF, '', REG[:-1], REG + 'x'])
def test_guard_near_miss_and_case_variant_names_reraise_exact_object(name):
    exc = _mnfe(name)
    with pytest.raises(ModuleNotFoundError) as e:
        _exec_guarded(import_exc=exc)
    assert e.value is exc


def test_guard_registry_name_but_spec_exists_reraises():
    exc = _mnfe(REG)
    with pytest.raises(ModuleNotFoundError) as e:
        _exec_guarded(import_exc=exc, spec_result=object())
    assert e.value is exc


def test_guard_plain_importerror_with_registry_name_propagates():
    exc = ImportError('x', name=REG)
    with pytest.raises(ImportError) as e:
        _exec_guarded(import_exc=exc)
    assert e.value is exc and type(e.value) is ImportError


def test_guard_runtimeerror_from_import_and_find_spec_propagate():
    exc = RuntimeError('boom')
    with pytest.raises(RuntimeError) as e:
        _exec_guarded(import_exc=exc)
    assert e.value is exc
    exc2 = RuntimeError('boom2')
    with pytest.raises(RuntimeError) as e:
        _exec_guarded(import_exc=_mnfe(REG), spec_exc=exc2)
    assert e.value is exc2


def test_guard_present_registry_used_find_spec_not_called():
    calls = []

    def mk(n):
        calls.append(n)
        return lambda code: (_ for _ in ()).throw(ValueError('custom:%s:%s' % (n, code)))

    ns, seen, fc = _exec_guarded(import_result=types.SimpleNamespace(make_fail=mk))
    assert seen == [] and fc == []
    with pytest.raises(ValueError) as e:
        ns['pointer_valid'](None)
    assert str(e.value) == 'custom:pointer_valid:bad_type:text' and calls == ['pointer_valid']


def test_guard_leaves_no_sys_modules_trace():
    before = set(sys.modules)
    _exec_guarded(import_exc=_mnfe(REG), spec_result=None)
    assert set(sys.modules) - before <= set()
    assert 'guarded_probe' not in sys.modules


class _FalsySpec:
    def __bool__(self):
        return False


class _LyingSpec:
    def __eq__(self, o):
        return True

    def __bool__(self):
        return True


@pytest.mark.parametrize('spec', [0, '', False, [], (), {}, 0.0, _FalsySpec(), _LyingSpec()])
def test_guard_falsy_or_lying_find_spec_results_reraise(spec):
    exc = _mnfe(REG)
    if spec is None:
        return
    # only None means absent; anything else, falsy or not, means a spec exists
    with pytest.raises(ModuleNotFoundError) as e:
        _exec_guarded(import_exc=exc, spec_result=spec)
    assert e.value is exc


def test_guard_foreign_error_find_spec_not_called_with_raising_spy():
    exc = _mnfe('foreign_pin')
    with pytest.raises(ModuleNotFoundError) as e:
        _exec_guarded(import_exc=exc, spec_exc=AssertionError('find_spec must not run'))
    assert e.value is exc


_FULL_LOG = []


def _import_names_while_exec(import_exc=None):
    path = pathlib.Path(m.__file__)
    src = path.read_text()
    real_import = builtins.__import__
    seen = []

    full = _FULL_LOG
    del full[:]

    def hook(name, *a, **k):
        seen.append(name)
        full.append((name, tuple(a[2]) if len(a) > 2 and a[2] else (), a[3] if len(a) > 3 else 0))
        if name == REG and import_exc is not None:
            raise import_exc
        if name == REG:
            return types.SimpleNamespace(make_fail=lambda n: None)
        return real_import(name, *a, **k)

    ns = {'__name__': 'pin_import_order'}
    absent = object()
    saved = sys.modules.pop(REG, absent)  # a preseeded stub (spec None) must not reach find_spec
    builtins.__import__ = hook
    try:
        try:
            exec(compile(src, str(path), 'exec'), ns)
            err = None
        except ModuleNotFoundError as e:
            err = e
    finally:
        assert builtins.__import__ is hook, '__import__ clobbered mid-probe'
        builtins.__import__ = real_import
        sys.modules.pop(REG, None)
        if saved is not absent:
            sys.modules[REG] = saved
    assert builtins.__import__ is real_import
    return seen, err, ns


def test_guard_foreign_missing_name_reraised_before_importlib_util_is_imported():
    exc = _mnfe('some_foreign_dependency_pin')
    seen, err, _ns = _import_names_while_exec(exc)
    assert err is exc
    assert REG in seen
    assert 'importlib.util' not in seen and 'importlib' not in seen


def test_guard_registry_name_missing_imports_importlib_util_after_registry_attempt():
    seen, err, ns = _import_names_while_exec(_mnfe(REG))
    assert seen.count('importlib.util') == 1
    assert seen.index(REG) < seen.index('importlib.util')
    if err is None:
        assert callable(ns['make_fail'])


def test_guard_present_registry_never_imports_importlib_util():
    seen, err, ns = _import_names_while_exec(None)
    assert err is None and REG in seen
    assert 'importlib.util' not in seen


def test_own_restore_import_helper_none_preset_world():
    prior = sys.modules.get(REG, _MISSING)
    sys.modules[REG] = None
    try:
        mod = _import_module_fresh()
        assert mod.pointer_valid('') is True
        assert REG in sys.modules and sys.modules[REG] is None
    finally:
        if prior is _MISSING:
            sys.modules.pop(REG, None)
        else:
            sys.modules[REG] = prior


def test_env_guard_import_machinery_untouched():
    real = builtins.__import__
    find = iu.find_spec
    _exec_guarded(import_exc=_mnfe(REG), spec_result=None)
    assert builtins.__import__ is real and iu.find_spec is find
    __import__('json')


def test_real_stub_root_present_combo(tmp_path):
    # a stub root first on PYTHONPATH whose packages merge via pkgutil.extend_path
    # supplies a real registry file; a child pytest run of THIS suite must pass
    signal.alarm(240)  # the child runs the whole suite; the autouse fixture resets the alarm
    import os
    import shutil
    import subprocess
    backend = pathlib.Path(m.__file__).resolve().parents[3]
    stubroot = tmp_path / 'stubroot'
    spkg = stubroot / 'app' / 'modules' / 'instinct_doc'
    spkg.mkdir(parents=True)
    ext = '__path__ = __import__("pkgutil").extend_path(__path__, __name__)\n'
    (stubroot / 'app' / '__init__.py').write_text(ext)
    (stubroot / 'app' / 'modules' / '__init__.py').write_text(ext)
    (spkg / '__init__.py').write_text(ext)
    (spkg / 'p235_concepts_registry.py').write_text(
        'def make_fail(name):\n'
        '    def fail(code):\n'
        "        raise ValueError('P235:%s:%s' % (name, code))\n"
        '    return fail\n')
    child_test = tmp_path / 'test_child.py'
    shutil.copy(pathlib.Path(__file__), child_test)
    env = dict(os.environ)
    env['PYTHONPATH'] = str(stubroot) + os.pathsep + str(backend)
    r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                        '--deselect', 'test_child.py::test_real_stub_root_present_combo',
                        str(child_test)], cwd=str(tmp_path), env=env,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


def test_foreign_import_pin_module_imports_only_registry_and_importlib():
    import ast
    tree = ast.parse(pathlib.Path(m.__file__).read_text())
    names = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            names.append(n.module)
    assert sorted(names) == ['app.modules.instinct_doc.p235_concepts_registry', 'importlib.util']


def test_guard_hook_full_args_registry_missing_logs_plain_importlib_util_import():
    _seen, _err, _ns = _import_names_while_exec(_mnfe(REG))
    assert _FULL_LOG[:2] == [(REG, ('make_fail',), 0), ('importlib.util', (), 0)]
    assert all(n == 'app.modules.instinct_doc' for n, _f, _l in _FULL_LOG[2:])


def test_guard_hook_full_args_foreign_name_logs_only_registry_entry():
    _import_names_while_exec(_mnfe('some_foreign_dependency_pin'))
    assert _FULL_LOG == [(REG, ('make_fail',), 0)]


def test_guard_hook_full_args_registry_present_logs_only_registry_entry():
    _import_names_while_exec(None)
    assert _FULL_LOG == [(REG, ('make_fail',), 0)]




# ---------- guard-world find_spec call lists, asserted after the raise ----------
def _spy_world(import_exc=None, import_result=_MISSING, spec_result=None):
    # runs the module source with a recording find_spec; returns (raised, namespace, calls)
    path = pathlib.Path(m.__file__)
    real_import = builtins.__import__
    real_find = iu.find_spec
    calls = []

    def fake_import(name, *a, **k):
        if name == REG:
            if import_exc is not None:
                raise import_exc
            if import_result is not _MISSING:
                return import_result
        return real_import(name, *a, **k)

    def spy(name, *a, **k):
        calls.append((name, a, k))
        return spec_result

    saved = sys.modules.pop(REG, _MISSING)
    ns = {'__name__': 'guarded_probe'}
    raised = None
    builtins.__import__ = fake_import
    iu.find_spec = spy
    try:
        try:
            exec(compile(path.read_text(), str(path), 'exec'), ns)
        except BaseException as e:
            raised = e
    finally:
        builtins.__import__ = real_import
        iu.find_spec = real_find
        sys.modules.pop(REG, None)
        if saved is not _MISSING:
            sys.modules[REG] = saved
    assert builtins.__import__ is real_import and iu.find_spec is real_find
    return raised, ns, calls


def test_find_spec_call_list_asserted_after_the_raise_in_every_guard_world():
    # absent registry (find_spec says no spec): one call for the registry name, no error, fallback defined
    raised, ns, calls = _spy_world(import_exc=_mnfe(REG), spec_result=None)
    assert raised is None and calls == [(REG, (), {})] and ns['_iu'] is iu
    # registry name missing but a spec exists: one call, then the exact original error escapes
    for spec in (object(), True, 1, 'x'):
        exc = _mnfe(REG)
        raised, ns, calls = _spy_world(import_exc=exc, spec_result=spec)
        assert raised is exc and calls == [(REG, (), {})] and 'make_fail' not in ns
    # registry present: no call at all
    raised, ns, calls = _spy_world(import_result=types.SimpleNamespace(make_fail=lambda n: None))
    assert raised is None and calls == [] and '_iu' not in ns
    # foreign or near-miss module names, plain and named ImportError, other errors: no call, exact object escapes
    excs = [_mnfe(n) for n in ('some_other_dep_pin', 'x.' + REG, REG + '.sub', 'x.' + REG + '.y', REG.upper(), None, '', 'app')]
    excs += [ImportError('x'), ImportError('x', name=REG), RuntimeError('x'), ModuleNotFoundError('x')]
    for exc in excs:
        raised, ns, calls = _spy_world(import_exc=exc, spec_result=object())
        assert raised is exc and calls == [], repr(exc)


def test_no_import_during_exec_of_module_body_beyond_the_guard_in_every_world():
    _import_names_while_exec(_mnfe(REG))
    assert _FULL_LOG[:2] == [(REG, ('make_fail',), 0), ('importlib.util', (), 0)]
    assert all(n == 'app.modules.instinct_doc' for n, _f, _l in _FULL_LOG[2:])
    _import_names_while_exec(None)
    assert _FULL_LOG == [(REG, ('make_fail',), 0)]
    _import_names_while_exec(_mnfe('some_foreign_dependency_pin'))
    assert _FULL_LOG == [(REG, ('make_fail',), 0)]


# ================= cap-before-work, work and allocation bounds =================
def _peak_refusal(fn, code, *a):
    import tracemalloc
    tracemalloc.start()
    try:
        with pytest.raises(ValueError) as e:
            getattr(m, fn)(*a)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert str(e.value) == _pfx() + '%s:%s' % (fn, code)
    return peak


def _trace(call):
    fname = m.__file__
    n = [0]

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != fname:
            return None
        if event == 'line':
            n[0] += 1
        return tracer

    prev = sys.gettrace()
    sys.settrace(tracer)
    try:
        call()
    finally:
        sys.settrace(prev)
    return n[0]


def _work_lines(fn, *a):
    def call():
        with pytest.raises(ValueError):
            getattr(m, fn)(*a)
    return _trace(call)


def test_no_allocation_or_work_before_the_cap_check_on_oversized_inputs():
    bound = 100000
    for big in ('a' * 3000000, '/' * 3000000, '/~' * 1500000, '\u00e9' * 3000000, '1' * 3000000, '\ud800' * 3000000):
        for fn in ('pointer_parse',):
            assert _peak_refusal(fn, 'bad_value:text.length', big) < bound
            assert _work_lines(fn, big) < 20
        def call(big=big):
            assert m.pointer_valid(big) is False
        assert _trace(call) < 20
        assert _peak_refusal('array_index', 'bad_value:token.length', big) < bound
        assert _work_lines('array_index', big) < 20
        assert _peak_refusal('pointer_get', 'bad_value:text.length', {}, big) < bound
        assert _work_lines('pointer_get', {}, big) < 60
        assert _peak_refusal('patch_apply', 'bad_value:op.path.length', {}, [{'op': 'test', 'path': big, 'value': 1}]) < bound
        assert _peak_refusal('patch_apply', 'bad_value:op.from.length', {}, [{'op': 'move', 'path': '', 'from': big}]) < bound
        assert _peak_refusal('pointer_format', 'bad_value:token.length', (big,)) < bound
    for fn, tail in (('pointer_parse', 'text'), ('pointer_valid', 'text'), ('array_index', 'token')):
        assert _peak_refusal(fn, 'bad_type:' + tail, b'a' * 3000000) < bound
    big = ('a',) * 3000000
    assert _peak_refusal('pointer_format', 'bad_value:tokens.length', big) < bound
    assert _work_lines('pointer_format', big) < 20
    big = [0] * 3000000
    assert _peak_refusal('patch_apply', 'bad_value:doc.nodes', big, []) < bound
    assert _work_lines('patch_apply', big, []) < 15000
    assert _peak_refusal('patch_apply', 'bad_value:op.value.nodes', {}, [{'op': 'add', 'path': '', 'value': big}]) < bound
    assert _peak_refusal('json_equal', 'bad_value:a.nodes', big, big) < bound
    assert _peak_refusal('patch_apply', 'bad_value:patch.length', {}, [{'op': 'remove', 'path': '/a'}] * 3000000) < bound
    assert _work_lines('patch_apply', {}, [{'op': 'remove', 'path': '/a'}] * 3000000) < 40
    assert _peak_refusal('patch_apply', 'bad_value:doc.str', 'a' * 3000000, []) < bound
    assert _peak_refusal('patch_apply', 'bad_value:doc.int', 2 ** 400000, []) < bound
    assert _work_lines('patch_apply', 2 ** 400000, []) < 40
    # a shared-reference blow-up and a cycle are cut by the node and depth caps
    assert _work_lines('patch_apply', _dag(15), []) < 16000
    assert _work_lines('patch_apply', _cyc_list(), []) < 400
    # a refusal inside the caps does bounded work
    assert _work_lines('pointer_parse', '/~' + '/' * 255) < 400
    assert _work_lines('patch_apply', {}, [{'op': 'test', 'path': '/a', 'value': 1}] * 64) < 4000


# ================= module namespace and literal pins =================
_NS_BASE = ['ADJACENT', 'CLAIMS', 'MAX_DEPTH', 'MAX_DIGITS', 'MAX_NODES', 'MAX_OPS', 'MAX_TEXT', 'MAX_TOKENS', 'NOT_CLAIMED', 'SCOPE',
            '_DIG', '_FROM', '_FROM_OPS', '_LIM', '_NOPE', '_No', '_OPS', '_PATH', '_TEXT', '_VALUE_OPS', '__builtins__', '__doc__',
            '__name__', '_add', '_copy', '_do', '_eq', '_index', '_locate', '_no', '_ops', '_resolve', '_slot', '_take', '_tokens',
            '_vcheck', '_walk', '_why', 'array_index', 'json_equal', 'make_fail', 'patch_apply', 'patch_valid', 'pointer_format',
            'pointer_get', 'pointer_parse', 'pointer_valid']


def test_module_namespace_exact_in_every_world():
    names = set(vars(m))
    reg = sys.modules.get(REG)
    fallback_here = reg is None or m.make_fail is not getattr(reg, 'make_fail', None)
    expect = set(_NS_BASE) | {'__cached__', '__file__', '__loader__', '__package__', '__spec__'}
    if fallback_here:
        expect |= {'_iu'}
    assert names == expect
    ns, _seen, _fc = _exec_guarded(import_result=types.SimpleNamespace(make_fail=lambda n: None))
    assert sorted(ns) == sorted(_NS_BASE)
    ns, _seen, _fc = _exec_guarded(import_exc=_mnfe(REG), spec_result=None)
    assert sorted(ns) == sorted(set(_NS_BASE) | {'_iu'})
    assert ns['_iu'] is iu


def test_every_module_level_literal_pinned_whole():
    assert (m.MAX_TEXT, m.MAX_TOKENS, m.MAX_DEPTH, m.MAX_NODES, m.MAX_OPS, m.MAX_DIGITS) == (256, 32, 16, 1024, 64, 10)
    assert m._LIM == 10 ** 10 and type(m._LIM) is int
    assert m._DIG == '0123456789' and type(m._DIG) is str
    assert m._OPS == ('add', 'remove', 'replace', 'move', 'copy', 'test')
    assert m._FROM_OPS == ('move', 'copy') and m._VALUE_OPS == ('add', 'replace', 'test')
    assert m._TEXT == ('bad_value:text.length', 'bad_value:text.syntax', 'bad_value:text.tokens')
    assert m._PATH == ('bad_value:op.path.length', 'bad_value:op.path.syntax', 'bad_value:op.path.tokens')
    assert m._FROM == ('bad_value:op.from.length', 'bad_value:op.from.syntax', 'bad_value:op.from.tokens')
    assert m.CLAIMS is False
    for n in ('MAX_TEXT', 'MAX_TOKENS', 'MAX_DEPTH', 'MAX_NODES', 'MAX_OPS', 'MAX_DIGITS'):
        assert type(getattr(m, n)) is int
    for n in ('_OPS', '_FROM_OPS', '_VALUE_OPS', '_TEXT', '_PATH', '_FROM'):
        assert type(getattr(m, n)) is tuple
    assert type(m._NOPE) is object and m._NOPE is not None


def test_module_source_is_ascii_and_uses_no_int_call_no_regex_no_clock_no_import_beyond_the_guard():
    import ast
    raw = pathlib.Path(m.__file__).read_bytes()
    raw.decode('ascii')
    assert b'\r' not in raw and raw.endswith(b'\n')
    tree = ast.parse(raw.decode('ascii'))
    names = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert 'int' not in names and 'str' not in names and 'float' not in names and 'ord' not in names
    assert not attrs & {'isdigit', 'isalpha', 'isalnum', 'isdecimal', 'isnumeric', 'isascii', 'strip', 'lstrip', 'rstrip', 'upper',
                        'lower', 'casefold', 'decode', 'encode', 'from_bytes', 'to_bytes', 'index', 'hex', 'fromhex', 'match',
                        'search', 'fullmatch', 'sub', 'compile', 'startswith', 'endswith', 'format', 'translate', 'join', 'time',
                        'now', 'today', 'deepcopy', 'copy', 'loads', 'dumps', 'items', 'keys', 'values', 'get', 'pop', 'sort'}
    assert attrs == {'append', 'find', 'find_spec', 'insert', 'name', 'replace', 'split'}
    assert names == {'ValueError', '_No', '_add', '_copy', '_do', '_eq', '_index', '_locate', '_ops', '_resolve', '_slot', '_take',
                     '_tokens', '_vcheck', '_walk', '_why', 'f', 'len', 'make_fail', 'object', 'tuple', 'type', 'zip'}
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert len(imports) == 2
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.Global, ast.Nonlocal, ast.Lambda, ast.Try)) and
                not isinstance(n, ast.Try)]
    assert len([n for n in ast.walk(tree) if isinstance(n, ast.Try)]) == 3


# ================= every refusal site, no import on any of them =================
_GOOD = {'a': [1]}


def _site_cases():
    pp, pv, pf, ai, pg, je, pl, pa = ('pointer_parse', 'pointer_valid', 'pointer_format', 'array_index', 'pointer_get',
                                       'json_equal', 'patch_valid', 'patch_apply')
    cases = [
        (pp, 'bad_type:text', (1,)), (pp, 'bad_value:text.length', ('a' * 257,)), (pp, 'bad_value:text.syntax', ('a',)),
        (pp, 'bad_value:text.syntax', ('/~',)), (pp, 'bad_value:text.tokens', ('/' * 33,)),
        (pv, 'bad_type:text', (1,)),
        (pf, 'bad_type:tokens', ([],)), (pf, 'bad_value:tokens.length', (('a',) * 33,)), (pf, 'bad_type:token', ((1,),)),
        (pf, 'bad_value:token.length', (('a' * 257,),)), (pf, 'bad_value:text.length', (('a' * 256,),)),
        (ai, 'bad_type:token', (1,)), (ai, 'bad_value:token.length', ('1' * 11,)), (ai, 'bad_value:token.syntax', ('01',)),
        (pg, 'bad_value:pointer.missing', (_GOOD, '/b')), (pg, 'bad_type:text', (_GOOD, 1)),
        (pg, 'bad_value:text.length', (_GOOD, 'a' * 257)), (pg, 'bad_value:text.syntax', (_GOOD, 'a')),
        (pg, 'bad_value:text.tokens', (_GOOD, '/' * 33)),
        (pl, 'bad_type:patch', (1,)),
    ]
    for kind, bad in (('type', object()), ('depth', deep(17)), ('nodes', [0] * 1024), ('str', 'a' * 257), ('int', 10 ** 10),
                      ('float', float('nan')), ('key', {1: 1})):
        c = 'bad_type:%s' if kind == 'type' else 'bad_value:%s.' + kind
        cases.append((pg, c % 'doc', (bad, '')))
        cases.append((pa, c % 'doc', (bad, [])))
        cases.append((je, c % 'a', (bad, 1)))
        cases.append((je, c % 'b', (1, bad)))
        cases.append((pa, c % 'op.value', ({}, [{'op': 'add', 'path': '', 'value': bad}])))
    S = [
        ('bad_type:patch', 1), ('bad_value:patch.length', [{'op': 'remove', 'path': '/a'}] * 65), ('bad_type:op', [1]),
        ('bad_type:op.key', [{1: 1}]), ('bad_value:op.op.missing', [{}]), ('bad_type:op.op', [{'op': 1}]),
        ('bad_value:op.op.unknown', [{'op': 'x'}]), ('bad_value:op.path.missing', [{'op': 'add'}]),
        ('bad_type:op.path', [{'op': 'add', 'path': 1}]), ('bad_value:op.path.length', [{'op': 'add', 'path': 'a' * 257}]),
        ('bad_value:op.path.syntax', [{'op': 'add', 'path': 'a'}]), ('bad_value:op.path.syntax', [{'op': 'add', 'path': '/~'}]),
        ('bad_value:op.path.tokens', [{'op': 'add', 'path': '/' * 33}]),
        ('bad_value:op.from.missing', [{'op': 'move', 'path': ''}]), ('bad_type:op.from', [{'op': 'move', 'path': '', 'from': 1}]),
        ('bad_value:op.from.length', [{'op': 'move', 'path': '', 'from': 'a' * 257}]),
        ('bad_value:op.from.syntax', [{'op': 'move', 'path': '', 'from': 'a'}]),
        ('bad_value:op.from.syntax', [{'op': 'move', 'path': '', 'from': '/~'}]),
        ('bad_value:op.from.tokens', [{'op': 'move', 'path': '', 'from': '/' * 33}]),
        ('bad_value:op.value.missing', [{'op': 'add', 'path': ''}]),
    ]
    for code, patch in S:
        cases.append((pa, code, ({}, patch)))
    A = [
        ('bad_value:apply.index', [{'op': 'add', 'path': '/a/5', 'value': 0}]),
        ('bad_value:apply.parent', [{'op': 'add', 'path': '/q/r', 'value': 0}]),
        ('bad_value:apply.parent', [{'op': 'add', 'path': '/a/0/x', 'value': 0}]),
        ('bad_value:apply.root', [{'op': 'remove', 'path': ''}]),
        ('bad_value:apply.root', [{'op': 'move', 'from': '', 'path': ''}]),
        ('bad_value:apply.missing', [{'op': 'remove', 'path': '/q'}]),
        ('bad_value:apply.missing', [{'op': 'replace', 'path': '/q', 'value': 0}]),
        ('bad_value:apply.missing', [{'op': 'test', 'path': '/q', 'value': 0}]),
        ('bad_value:apply.from', [{'op': 'move', 'from': '/q', 'path': '/z'}]),
        ('bad_value:apply.from', [{'op': 'copy', 'from': '/q', 'path': '/z'}]),
        ('bad_value:apply.child', [{'op': 'move', 'from': '/a', 'path': '/a/0'}]),
        ('bad_value:apply.test', [{'op': 'test', 'path': '/a', 'value': 0}]),
        ('bad_value:result.depth', [{'op': 'add', 'path': '/b', 'value': deep(16)}]),
        ('bad_value:result.nodes', [{'op': 'add', 'path': '/b', 'value': [0] * 1022}]),
    ]
    for code, patch in A:
        cases.append((pa, code, (_GOOD, patch)))
    return cases


_ALL_CODES = (
    'bad_type:text', 'bad_value:text.length', 'bad_value:text.syntax', 'bad_value:text.tokens', 'bad_type:tokens',
    'bad_value:tokens.length', 'bad_type:token', 'bad_value:token.length', 'bad_value:token.syntax', 'bad_value:pointer.missing',
    'bad_type:patch', 'bad_value:patch.length', 'bad_type:op', 'bad_type:op.key', 'bad_value:op.op.missing', 'bad_type:op.op',
    'bad_value:op.op.unknown', 'bad_value:op.path.missing', 'bad_type:op.path', 'bad_value:op.path.length',
    'bad_value:op.path.syntax', 'bad_value:op.path.tokens', 'bad_value:op.from.missing', 'bad_type:op.from',
    'bad_value:op.from.length', 'bad_value:op.from.syntax', 'bad_value:op.from.tokens', 'bad_value:op.value.missing',
    'bad_value:apply.index', 'bad_value:apply.parent', 'bad_value:apply.root', 'bad_value:apply.missing',
    'bad_value:apply.from', 'bad_value:apply.child', 'bad_value:apply.test', 'bad_value:result.depth', 'bad_value:result.nodes',
    'bad_type:doc', 'bad_value:doc.depth', 'bad_value:doc.nodes', 'bad_value:doc.str', 'bad_value:doc.int', 'bad_value:doc.float',
    'bad_value:doc.key', 'bad_type:a', 'bad_value:a.depth', 'bad_value:a.nodes', 'bad_value:a.str', 'bad_value:a.int',
    'bad_value:a.float', 'bad_value:a.key', 'bad_type:b', 'bad_value:b.depth', 'bad_value:b.nodes', 'bad_value:b.str',
    'bad_value:b.int', 'bad_value:b.float', 'bad_value:b.key', 'bad_type:op.value', 'bad_value:op.value.depth',
    'bad_value:op.value.nodes', 'bad_value:op.value.str', 'bad_value:op.value.int', 'bad_value:op.value.float',
    'bad_value:op.value.key')


def _ok_calls():
    assert m.pointer_parse('/a~1b') == ('a/b',)
    assert m.pointer_valid('/a') is True and m.pointer_valid('a') is False
    assert m.pointer_format(('a/b',)) == '/a~1b'
    assert m.array_index('7') == 7
    assert m.pointer_get({'a': [1]}, '/a/0') == 1
    assert m.json_equal({'a': 1}, {'a': 1.0}) is True and m.json_equal(1, True) is False
    assert m.patch_valid([{'op': 'add', 'path': '/a', 'value': 1}]) is True
    assert m.patch_valid([{'op': 'add', 'path': 'a', 'value': 1}]) is False
    assert m.patch_apply({'a': [1]}, [{'op': 'add', 'path': '/a/-', 'value': 2}]) == {'a': [1, 2]}
    assert m.patch_apply({'a': [1]}, [{'op': 'add', 'path': '/a/0', 'value': 2}]) == {'a': [2, 1]}
    assert m.patch_apply({'a': 1}, [{'op': 'remove', 'path': '/a'}]) == {}
    assert m.patch_apply({'a': 1}, [{'op': 'replace', 'path': '/a', 'value': 2}]) == {'a': 2}
    assert m.patch_apply({'a': 1}, [{'op': 'replace', 'path': '', 'value': 2}]) == 2
    assert m.patch_apply({'a': 1}, [{'op': 'move', 'from': '/a', 'path': '/b'}]) == {'b': 1}
    assert m.patch_apply({'a': 1}, [{'op': 'copy', 'from': '/a', 'path': '/b'}]) == {'a': 1, 'b': 1}
    assert m.patch_apply({'a': 1}, [{'op': 'test', 'path': '/a', 'value': 1}]) == {'a': 1}
    assert m.patch_apply({'a': 1}, [{'op': 'add', 'path': '', 'value': 3}]) == 3


def test_site_cases_cover_exactly_the_documented_codes_and_each_raises_it():
    cases = _site_cases()
    assert set(c for _f, c, _a in cases) == set(_ALL_CODES)
    assert len(_ALL_CODES) == len(set(_ALL_CODES)) == 65
    for fn, code, args in cases:
        refuse(fn, code, *args)


def test_no_import_on_every_refusal_site_and_every_return_site():
    import ast
    src = pathlib.Path(m.__file__).read_text()
    want = set()
    returns = set()
    for fn in ast.parse(src).body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'f':
                want.add((fn.name, n.lineno))
            if isinstance(n, ast.Return):
                returns.add((fn.name, n.lineno))
    assert len(want) == 41 and len(returns) == 61
    fname = m.__file__
    reached = set()
    calls = []
    real = builtins.__import__

    def hook(*a, **k):
        calls.append(a[:1])
        return real(*a, **k)

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != fname:
            return None
        if event == 'call':
            return tracer
        if event == 'line':
            reached.add((frame.f_code.co_name, frame.f_lineno))
        return tracer

    prev = sys.gettrace()
    cases = _site_cases()
    for fn, code, args in cases:
        builtins.__import__ = hook
        sys.settrace(tracer)
        try:
            with pytest.raises(Exception) as e:
                getattr(m, fn)(*args)
        finally:
            sys.settrace(prev)
            builtins.__import__ = real
        assert str(e.value) == _pfx() + '%s:%s' % (fn, code)
    assert calls == []
    builtins.__import__ = hook
    sys.settrace(tracer)
    try:
        _ok_calls()
        m.pointer_get(7, '')
        m.json_equal([1], [1, 2])
        m.json_equal([1], 'x')
        m.json_equal({'a': 1}, {'b': 1})
        m.json_equal({'a': 1, 'b': 2}, {'a': 1})
        m.json_equal({'a': 1}, {'a': 2})
        m.json_equal(None, 1)
        m.json_equal('x', 'x')
        m.json_equal(1.5, 1.5)
        m.json_equal(True, True)
        m.patch_apply({'a': [1]}, [{'op': 'add', 'path': '/a/-', 'value': 2}])
        m.patch_valid([1])
        m.pointer_valid('/~')
        m.patch_apply({'a': 1}, [{'op': 'test', 'path': '/a', 'value': 1}])
        m.patch_apply([1], [{'op': 'remove', 'path': '/0'}])
        m.patch_apply([1], [{'op': 'replace', 'path': '/0', 'value': 2}])
        m.patch_apply({'a': 1}, [{'op': 'copy', 'from': '', 'path': '/b'}])
        m.patch_apply({'a': {'b': 1}}, [{'op': 'move', 'from': '/a/b', 'path': '/c'}])
        m.patch_apply({'a': 1}, [{'op': 'move', 'from': '/a', 'path': '/a'}])
    finally:
        sys.settrace(prev)
        builtins.__import__ = real
    assert calls == []
    assert want <= reached, sorted(want - reached)


def test_import_log_pin_no_import_during_any_function_call():
    real = builtins.__import__
    calls = []

    def hook(*a, **k):
        calls.append(a[:1])
        return real(*a, **k)

    builtins.__import__ = hook
    try:
        _ok_calls()
        for fn, code, args in _site_cases():
            with pytest.raises(ValueError):
                getattr(m, fn)(*args)
    finally:
        builtins.__import__ = real
    assert calls == []


def test_fallback_world_literal_p235_prefix_for_every_function_and_any_code():
    ns, _seen, _fc = _exec_guarded(import_exc=_mnfe(REG), spec_result=None)
    for fn, code, args in _site_cases():
        with pytest.raises(ValueError) as e:
            ns[fn](*args)
        assert str(e.value) == 'P235:%s:%s' % (fn, code)
    with pytest.raises(ValueError) as e:
        ns['make_fail']('nm')('zz')
    assert str(e.value) == 'P235:nm:zz'
    assert ns['pointer_parse']('/a') == ('a',)
    assert ns['patch_apply']({'a': 1}, [{'op': 'remove', 'path': '/a'}]) == {}


def test_fallback_handler_binds_iu_not_importlib():
    ns, _seen, _fc = _exec_guarded(import_exc=_mnfe(REG), spec_result=None)
    assert '_iu' in ns and 'importlib' not in ns
    assert ns['_iu'] is iu


# ---------- docstring pins ----------

_DOC_QUOTES = (
    'json-pointer = *( "/" reference-token )',
    'reference-token = *( unescaped / escaped )',
    'unescaped = %x00-2E / %x30-7D / %x7F-10FFFF',
    'escaped = "~" ( "0" / "1" )',
    'array-index = %x30 / ( %x31-39 *(%x30-39) )',
    'It is an error condition if a JSON Pointer value does not conform to this syntax (see Section 7).',
    'By performing the substitutions in this order, an implementation avoids the error of turning',
    'No Unicode character normalization is performed.',
    'note that leading zeros are not allowed',
    'Note that the use of the "-" character to index an array will always result in such an error condition because by definition it refers to a nonexistent array element.',
    'Operations are applied sequentially in the order they appear in the array.',
    'Operation objects MUST have exactly one "op" member, whose value indicates the operation to perform.',
    'Its value MUST be one of "add", "remove", "replace", "move", "copy", or "test"; other values are errors.',
    'Additionally, operation objects MUST have exactly one "path" member.',
    'Members that are not explicitly defined for the operation in question MUST be ignored',
    'The operation object MUST contain a "value" member whose content specifies the value to be added.',
    'The specified index MUST NOT be greater than the number of elements in the array.',
    'If the "-" character is used to index the end of the array (see [RFC6901]), this has the effect of appending the value to the array.',
    'The target location MUST exist for the operation to be successful.',
    'The "from" location MUST exist for the operation to be successful.',
    'The "from" location MUST NOT be a proper prefix of the "path" location; i.e., a location cannot be moved into one of its children.',
    'The target location MUST be equal to the "value" value for the operation to be considered successful.',
    'numbers: are considered equal if their values are numerically equal.',
    'literals (false, true, and null): are considered equal if they are the same.',
    'application of the entire patch document SHALL NOT be deemed successful',
    'EID 3981 (Rejected, Technical, Section 3',
    'EID 5745 (Reported, Editorial, Section 5',
    'EID 8314 (Reported, Technical, Section 5',
    'three records',
    'EID 4419 (Rejected, Editorial, A.14)',
    'EID 4460 (Rejected, Editorial, 4.1)',
    'EID 4596 (Rejected, Technical, Global',
    'EID 4787 (Held for Document Update, Technical, 4.2',
    'EID 5239 (Rejected, Technical, A.16',
    'EID 6351 (Rejected, Technical, Global',
    'six records',
    'https://www.rfc-editor.org/errata.json',
    'OURS REFUSAL, stated plainly',
    "remove of path '' and move from '' are refused as apply.root",
)


@pytest.mark.parametrize('q', _DOC_QUOTES)
def test_docstring_quote_present(q):
    assert q in ' '.join(m.__doc__.split())


_DOC_FULL = (
    'P235 b1127 bounded exact RFC 6901 JSON Pointer and RFC 6902 JSON Patch on parsed values. Pure functi'
    'ons on parsed JSON values (exact dict, list, str, int, float, bool and None), no JSON text, no clock'
    ', no network: pointer_parse, pointer_valid, pointer_format, array_index and pointer_get for RFC 6901'
    ', and json_equal, patch_valid and patch_apply for RFC 6902 with the six operations add, remove, repl'
    'ace, move, copy and test. Primary sources (fetched fresh and read live 2026-10-21): RFC 6901 JavaScr'
    'ipt Object Notation (JSON) Pointer, https://www.rfc-editor.org/rfc/rfc6901.txt, Sections 3, 4, 5 and'
    ' 7, and its info page https://www.rfc-editor.org/info/rfc6901 (Proposed Standard, April 2013); RFC 6'
    '902 JavaScript Object Notation (JSON) Patch, https://www.rfc-editor.org/rfc/rfc6902.txt, Sections 3,'
    ' 4, 5 and Appendix A, and its info page https://www.rfc-editor.org/info/rfc6902 (Proposed Standard, '
    'April 2013). Quotes: \'json-pointer = *( "/" reference-token )\' \'reference-token = *( unescaped / esc'
    'aped )\' \'unescaped = %x00-2E / %x30-7D / %x7F-10FFFF\' \'escaped = "~" ( "0" / "1" )\' \'array-index = %'
    "x30 / ( %x31-39 *(%x30-39) )' 'It is an error condition if a JSON Pointer value does not conform to "
    "this syntax (see Section 7).' 'By performing the substitutions in this order, an implementation avoi"
    "ds the error of turning' 'No Unicode character normalization is performed.' 'note that leading zeros"
    ' are not allowed\' \'Note that the use of the "-" character to index an array will always result in su'
    "ch an error condition because by definition it refers to a nonexistent array element.' 'Operations a"
    "re applied sequentially in the order they appear in the array.' 'Operation objects MUST have exactly"
    ' one "op" member, whose value indicates the operation to perform.\' \'Its value MUST be one of "add", '
    '"remove", "replace", "move", "copy", or "test"; other values are errors.\' \'Additionally, operation o'
    'bjects MUST have exactly one "path" member.\' \'Members that are not explicitly defined for the operat'
    'ion in question MUST be ignored\' \'The operation object MUST contain a "value" member whose content s'
    "pecifies the value to be added.' 'The specified index MUST NOT be greater than the number of element"
    's in the array.\' \'If the "-" character is used to index the end of the array (see [RFC6901]), this h'
    "as the effect of appending the value to the array.' 'The target location MUST exist for the operatio"
    'n to be successful.\' \'The "from" location MUST exist for the operation to be successful.\' \'The "from'
    '" location MUST NOT be a proper prefix of the "path" location; i.e., a location cannot be moved into'
    ' one of its children.\' \'The target location MUST be equal to the "value" value for the operation to '
    "be considered successful.' 'numbers: are considered equal if their values are numerically equal.' 'l"
    "iterals (false, true, and null): are considered equal if they are the same.' 'application of the ent"
    "ire patch document SHALL NOT be deemed successful.' Errata (read live 2026-10-21, from the full inde"
    'x https://www.rfc-editor.org/errata.json, because per-RFC pages can omit records): RFC 6901, https:/'
    '/www.rfc-editor.org/errata/rfc6901, three records, EID 3981 (Rejected, Technical, Section 3: double '
    'the slash instead of the ~1 escape, a change request), EID 5745 (Reported, Editorial, Section 5: the'
    ' "/i\\j" and "/k"l" example strings) and EID 8314 (Reported, Technical, Section 5: the same example s'
    'trings under RFC 8259 string escaping); none applied, and this unit takes a pointer as an already un'
    'escaped str, as Section 5 says, so it does no JSON string unescaping. RFC 6902, https://www.rfc-edit'
    'or.org/errata/rfc6902, six records, EID 4419 (Rejected, Editorial, A.14), EID 4460 (Rejected, Editor'
    'ial, 4.1), EID 4596 (Rejected, Technical, Global: an append operation, not applied, so append is an '
    'unknown operation here), EID 4787 (Held for Document Update, Technical, 4.2: the remove of the root '
    'is never specified, and it proposes to forbid it; not applied as an RFC rule, but see the OURS refus'
    'al below), EID 5239 (Rejected, Technical, A.16: the example is correct, an array value is added as o'
    'ne element) and EID 6351 (Rejected, Technical, Global: a previous member for reverse patches, not ap'
    'plied). CONVENTIONS (OURS, UNSOURCED, stated). Values: only exact dict, list, str, int, float, bool '
    'and None; bool is not a number, subclasses of every type are refused, every dict key is an exact str'
    '. Caps: a str or key has at most 256 characters (MAX_TEXT), an int has absolute value below 10 ** 10'
    ' (MAX_DIGITS is 10), a float is finite, containers nest at most 16 deep (MAX_DEPTH, the root contain'
    'er is depth 0, an empty container at depth 16 is refused), and a value has at most 1024 values in al'
    'l (MAX_NODES, every container and every member counts, the keys do not), so a cycle or a shared-refe'
    'rence blow-up is refused, never followed. All Unicode is accepted in a str, including NUL and lone s'
    'urrogates, because RFC 6901 Section 3 allows %x7F-10FFFF and Section 8 notes the NUL; only the array'
    '-index digit class is ASCII 0 to 9, and this module source is ASCII. A pointer text has at most 256 '
    'characters (MAX_TEXT) and at most 32 reference tokens (MAX_TOKENS). pointer_parse returns the tuple '
    "of decoded tokens, '' gives (), a text that does not start with '/' is refused, and each '~' must be"
    " followed by 0 or 1. Decoding turns ~1 into '/' first and then ~0 into '~'. pointer_format takes a t"
    "uple of at most 32 exact str tokens of at most 256 characters each, turns '~' into ~0 first and then"
    " '/' into ~1, and refuses output over 256 characters, so every output parses back to the same tokens"
    ' and every parseable text formats back to itself. array_index takes the ABNF array-index of at most '
    "10 ASCII digits and returns an int built by digit arithmetic, never int() on text; '-' is refused th"
    'ere. pointer_get returns a deep copy of the referenced value; an object token is an exact member nam'
    "e, an array token must be an array-index below the length, '-' never resolves and a str, number, boo"
    'l or None never has members. json_equal follows RFC 6902 Section 4.6: strings by code points, number'
    's by numeric value (1 equals 1.0), arrays by position, objects by member name and value regardless o'
    'f order, and a bool equals only the same bool, so true is not 1. patch_valid checks structure only, '
    'and patch_apply never mutates its inputs and returns a new value that shares no list or dict with th'
    'e document or the patch. A patch is a list of at most 64 operations, each an exact dict whose keys a'
    're all exact str. Members the operation does not define, including from on add, replace, remove and '
    'test and value on remove, move and copy, are ignored without being looked at, as RFC 6902 Section 4 '
    'requires. The whole patch is checked for structure before any operation runs, so a bad later operati'
    'on is refused even when an earlier one would fail first; RFC 6902 Section 5 only says evaluation SHO'
    'ULD terminate on error. Operations apply in order on a private copy and a refusal returns nothing, s'
    'o the document is unchanged. add: a root path replaces the document, an object parent sets the membe'
    "r, an array parent takes an index from 0 to the length or '-' to append, the parent must exist. remo"
    've and replace need the target to exist. OURS REFUSAL, stated plainly: RFC 6902 never says what the '
    "remove of the root yields (EID 4787, held), so remove of path '' and move from '' are refused as app"
    'ly.root; replace and test and copy from the root are accepted. move refuses a from that is a proper '
    'prefix of path, compared token by token, as apply.child, before it checks that from exists, and a mo'
    've with from equal to path is a no-op on an existing value; move is a remove followed by an add, so '
    'the array index of the add counts the array after the removal (the Appendix A.7 example). copy deep-'
    'copies. test refuses unequal values as apply.test. After every operation the result must still fit t'
    'he caps, else bad_value:result.depth or bad_value:result.nodes. The failing operation index is not r'
    'eported. Errors are ValueError with message P235:<function>:<code>. pointer_parse: bad_type:text, th'
    'en bad_value:text.length, text.syntax and text.tokens. pointer_valid: bad_type:text only, every othe'
    'r refusal of pointer_parse gives False. pointer_format: bad_type:tokens, bad_value:tokens.length, th'
    'en per item in order bad_type:token and bad_value:token.length, then bad_value:text.length. array_in'
    'dex: bad_type:token, bad_value:token.length, bad_value:token.syntax. pointer_get: the document first'
    ', bad_type:doc or bad_value:doc.depth, doc.nodes, doc.str, doc.int, doc.float or doc.key for the fir'
    'st failure in depth-first order, then bad_type:text, bad_value:text.length, text.syntax, text.tokens'
    ', then bad_value:pointer.missing. json_equal: the same document codes for a, then for b, with a and '
    'b in place of doc. patch_valid: bad_type:patch only, and every other refusal of the structure check '
    'gives False. patch_apply: the document codes with doc, then the structure codes in operation order, '
    'bad_type:patch, bad_value:patch.length, bad_type:op, bad_type:op.key, bad_value:op.op.missing, bad_t'
    'ype:op.op, bad_value:op.op.unknown, bad_value:op.path.missing, bad_type:op.path, bad_value:op.path.l'
    'ength, op.path.syntax, op.path.tokens, then for move and copy bad_value:op.from.missing, bad_type:op'
    '.from and bad_value:op.from.length, op.from.syntax, op.from.tokens, then for add, replace and test b'
    'ad_value:op.value.missing, bad_type:op.value and bad_value:op.value.depth, nodes, str, int, float, k'
    'ey, then at run time bad_value:apply.index, apply.parent, apply.root, apply.missing, apply.from, app'
    'ly.child, apply.test and bad_value:result.depth, result.nodes. ADJACENCY, by name only: RFC 8259 JSO'
    'N text, RFC 7396 JSON Merge Patch, RFC 5789 HTTP PATCH, the RFC 6901 Section 6 URI fragment form and'
    ' the RFC 6902 Section 6 media type belong to other units and were not read beyond the sections named'
    ' above. SCOPE and NOT_CLAIMED are the module constants below.'
)


def test_docstring_whole_exact():
    assert ' '.join(m.__doc__.split()) == _DOC_FULL
    assert m.__doc__.startswith('P235 b1127 bounded exact RFC 6901')


def test_scope_and_constants_exact():
    assert m.SCOPE == 'PARTIAL: RFC 6901 JSON Pointer syntax and evaluation and RFC 6902 JSON Patch application on parsed JSON values, with the OURS caps and refusals stated in the docstring, pure functions'
    assert m.NOT_CLAIMED == ('JSON text parsing or serialising, only parsed values are handled', 'the URI fragment form of a pointer, RFC 6901 Section 6', 'RFC 7396 JSON Merge Patch or any media type handling', 'duplicate object member names, a parsed dict cannot carry them', 'the remove or move of the document root, which RFC 6902 leaves unspecified', 'global novelty', 'production readiness')
    assert m.ADJACENT == ('RFC 8259 JSON text, RFC 7396 JSON Merge Patch, RFC 5789 HTTP PATCH and the RFC 6901 URI fragment form are covered by other units and were not read',)
    assert m.CLAIMS is False
    assert m.MAX_TEXT == 256
    assert m.MAX_TOKENS == 32
    assert m.MAX_DEPTH == 16
    assert m.MAX_NODES == 1024
    assert m.MAX_OPS == 64
    assert m.MAX_DIGITS == 10
    assert type(m.NOT_CLAIMED) is tuple and type(m.ADJACENT) is tuple and type(m.SCOPE) is str
