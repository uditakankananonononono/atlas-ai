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
        from app.modules.instinct_doc import p235_concepts_batch1184_imapstr as mod
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
    assert builtins.__import__ == snap_import, 'builtins.__import__ leaked by this module'
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
        m.imap_parse(None, b"")
    tail = 'imap_parse:bad_type:rule'
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





# ================= behaviour =================
import itertools
import random
import re
from unittest import mock as _um


_IMPORT_PATCHES = []


def _start_import(mod, fn):
    p = _um.patch.object(mod, '__import__', fn)
    p.start()
    _IMPORT_PATCHES.append(p)


def _stop_import():
    if _IMPORT_PATCHES:
        _IMPORT_PATCHES.pop().stop()


@pytest.fixture(autouse=True)
def _release_import_patches():
    yield
    while _IMPORT_PATCHES:
        _IMPORT_PATCHES.pop().stop()


PA = 'imap_parse'
FM = 'imap_format'
IV = 'imap_is_valid'
_RULES = ('atom', 'number', 'nz-number', 'quoted', 'literal', 'string', 'astring', 'nstring', 'tag')

# RFC 3501 Section 9, written out independently of the module
_ATOM_SPECIALS = set(b'(){ %*"\\]') | set(range(0, 32)) | {127}
_ATOM_CHARS = set(range(1, 128)) - _ATOM_SPECIALS
_ASTRING_CHARS = _ATOM_CHARS | {ord(']')}
_TAG_CHARS = _ASTRING_CHARS - {ord('+')}


def test_character_classes_match_an_independent_reading_of_the_abnf():
    assert _ATOM_CHARS == set(range(0x21, 0x7F)) - set(b'(){%*"\\]')
    assert len(_ATOM_CHARS) == 94 - 8
    for b in range(256):
        one = bytes([b])
        assert m.imap_is_valid('atom', one) is (b in _ATOM_CHARS), b
        assert m.imap_is_valid('astring', one) is (b in _ASTRING_CHARS), b
        assert m.imap_is_valid('tag', one) is (b in _TAG_CHARS), b
        assert m.imap_is_valid('number', one) is (48 <= b <= 57), b
        assert m.imap_is_valid('nz-number', one) is (49 <= b <= 57), b
        q = b'"' + one + b'"'
        qok = 1 <= b <= 127 and b not in (10, 13, 34, 92)
        assert m.imap_is_valid('quoted', q) is qok, b
        assert m.imap_is_valid('string', q) is qok, b
        assert m.imap_is_valid('astring', q) is qok, b
        assert m.imap_is_valid('nstring', q) is qok, b
        e = b'"\\' + one + b'"'
        assert m.imap_is_valid('quoted', e) is (b in (34, 92)), b
        lit = b'{1}\r\n' + one
        assert m.imap_is_valid('literal', lit) is (b != 0), b
        assert m.imap_is_valid('string', lit) is (b != 0), b
        assert m.imap_is_valid('astring', lit) is (b != 0), b
        assert m.imap_is_valid('nstring', lit) is (b != 0), b
        # the same byte inside a longer atom, at either end
        assert m.imap_is_valid('atom', b'a' + one + b'a') is (b in _ATOM_CHARS), b
        assert m.imap_is_valid('atom', one + b'a') is (b in _ATOM_CHARS), b
        assert m.imap_is_valid('atom', b'a' + one) is (b in _ATOM_CHARS), b


def test_astring_char_set_is_the_atom_set_plus_the_closing_bracket_only():
    for b in range(256):
        assert m.imap_is_valid('astring', bytes([b])) is (b in _ATOM_CHARS or b == 93), b
    assert m.imap_parse('astring', b']') == ('atom', b']')
    assert m.imap_parse('astring', b'a]b]') == ('atom', b'a]b]')
    refuse(PA, 'bad_value:atom', 'atom', b']')
    refuse(PA, 'bad_value:atom', 'atom', b'a]')
    assert m.imap_parse('tag', b'a]') == ('tag', b'a]')
    assert m.imap_parse('atom', b'a+') == ('atom', b'a+')
    assert m.imap_parse('astring', b'+') == ('atom', b'+')
    refuse(PA, 'bad_value:atom', 'tag', b'+')
    refuse(PA, 'bad_value:atom', 'tag', b'a+b')
    refuse(PA, 'bad_value:atom', 'tag', b'a+')


_EX = (
    ('atom', b'abc', ('atom', b'abc')), ('atom', b'INBOX', ('atom', b'INBOX')), ('atom', b'NIL', ('atom', b'NIL')),
    ('atom', b"!#$&'+,-./09:;<=>?@AZ[^_`az|}~", ('atom', b"!#$&'+,-./09:;<=>?@AZ[^_`az|}~")),
    ('tag', b'A001', ('tag', b'A001')), ('tag', b'a]b', ('tag', b'a]b')),
    ('number', b'0', ('number', 0)), ('number', b'1', ('number', 1)), ('number', b'4294967295', ('number', 4294967295)),
    ('number', b'0000', ('number', 0)), ('number', b'007', ('number', 7)), ('number', b'00004294967295', ('number', 4294967295)),
    ('nz-number', b'1', ('number', 1)), ('nz-number', b'4294967295', ('number', 4294967295)),
    ('nz-number', b'10', ('number', 10)),
    ('quoted', b'""', ('quoted', b'')), ('quoted', b'"abc"', ('quoted', b'abc')), ('quoted', b'"a b"', ('quoted', b'a b')),
    ('quoted', b'"a\\"b"', ('quoted', b'a"b')), ('quoted', b'"a\\\\b"', ('quoted', b'a\\b')),
    ('quoted', b'"\\\\"', ('quoted', b'\\')), ('quoted', b'"\\""', ('quoted', b'"')), ('quoted', b'"\\\\\\""', ('quoted', b'\\"')),
    ('quoted', b'"(){%*]"', ('quoted', b'(){%*]')), ('quoted', b'"\x01\x7f"', ('quoted', b'\x01\x7f')),
    ('quoted', b'"\t"', ('quoted', b'\t')),
    ('literal', b'{0}\r\n', ('literal', b'')), ('literal', b'{3}\r\nabc', ('literal', b'abc')),
    ('literal', b'{5}\r\na\r\nb\n', ('literal', b'a\r\nb\n')), ('literal', b'{2}\r\n\x01\xff', ('literal', b'\x01\xff')),
    ('literal', b'{03}\r\nabc', ('literal', b'abc')), ('literal', b'{1}\r\n"', ('literal', b'"')),
    ('literal', b'{4}\r\n{1}\r', ('literal', b'{1}\r')),
    ('literal', b'{10}\r\n' + bytes(range(1, 11)), ('literal', bytes(range(1, 11)))),
    ('string', b'""', ('quoted', b'')), ('string', b'"x"', ('quoted', b'x')), ('string', b'{0}\r\n', ('literal', b'')),
    ('string', b'{1}\r\nx', ('literal', b'x')),
    ('astring', b'abc', ('atom', b'abc')), ('astring', b'a]', ('atom', b'a]')), ('astring', b'"a b"', ('quoted', b'a b')),
    ('astring', b'{1}\r\nx', ('literal', b'x')), ('astring', b'NIL', ('atom', b'NIL')), ('astring', b'nil', ('atom', b'nil')),
    ('astring', b'""', ('quoted', b'')),
    ('nstring', b'NIL', ('nil', None)), ('nstring', b'nil', ('nil', None)), ('nstring', b'Nil', ('nil', None)),
    ('nstring', b'nIL', ('nil', None)), ('nstring', b'""', ('quoted', b'')), ('nstring', b'"a"', ('quoted', b'a')),
    ('nstring', b'{0}\r\n', ('literal', b'')), ('nstring', b'{2}\r\nNI', ('literal', b'NI')),
)


@pytest.mark.parametrize('rule,data,expect', _EX)
def test_parse_examples_exact(rule, data, expect):
    got = m.imap_parse(rule, data)
    assert got == expect and type(got) is tuple and len(got) == 2 and type(got[0]) is str
    assert m.imap_is_valid(rule, data) is True
    kind, value = got
    if kind == 'number':
        assert type(value) is int
    elif kind == 'nil':
        assert value is None
    else:
        assert type(value) is bytes


_BAD = (
    # rule, data, code
    ('atom', b'', 'bad_value:atom'), ('atom', b' ', 'bad_value:atom'), ('atom', b'a b', 'bad_value:atom'),
    ('atom', b'a(', 'bad_value:atom'), ('atom', b'a)', 'bad_value:atom'), ('atom', b'{', 'bad_value:atom'),
    ('atom', b'a%', 'bad_value:atom'), ('atom', b'a*', 'bad_value:atom'), ('atom', b'a"', 'bad_value:atom'),
    ('atom', b'a\\', 'bad_value:atom'), ('atom', b'a\r', 'bad_value:atom'), ('atom', b'a\n', 'bad_value:atom'),
    ('atom', b'a\x00', 'bad_value:atom'), ('atom', b'a\x7f', 'bad_value:atom'), ('atom', b'a\x80', 'bad_value:atom'),
    ('atom', b'a\xff', 'bad_value:atom'), ('atom', b'a\t', 'bad_value:atom'), ('atom', b'a\x1f', 'bad_value:atom'),
    ('astring', b'', 'bad_value:atom'), ('astring', b'a b', 'bad_value:atom'), ('astring', b'a\x00', 'bad_value:atom'),
    ('astring', b'a"', 'bad_value:atom'), ('astring', b'a{', 'bad_value:atom'), ('astring', b'a\\', 'bad_value:atom'),
    ('tag', b'', 'bad_value:atom'), ('tag', b'a b', 'bad_value:atom'), ('tag', b'a*', 'bad_value:atom'),
    ('number', b'', 'bad_value:number'), ('number', b'-1', 'bad_value:number'), ('number', b'+1', 'bad_value:number'),
    ('number', b'1 ', 'bad_value:number'), ('number', b' 1', 'bad_value:number'), ('number', b'1.0', 'bad_value:number'),
    ('number', b'0x1', 'bad_value:number'), ('number', b'1e3', 'bad_value:number'), ('number', b'\xd9\xa1', 'bad_value:number'),
    ('number', b'4294967296', 'bad_value:number'), ('number', b'99999999999', 'bad_value:number'),
    ('number', b'1' * 4000, 'bad_value:number'), ('number', b'4294967296x', 'bad_value:number'),
    ('number', b'1' * 4000 + b'x', 'bad_value:number'), ('number', b'\x001', 'bad_value:number'),
    ('nz-number', b'0', 'bad_value:number'), ('nz-number', b'0000', 'bad_value:number'), ('nz-number', b'', 'bad_value:number'),
    ('nz-number', b'01', 'bad_value:number'), ('nz-number', b'0001', 'bad_value:number'), ('nz-number', b'010', 'bad_value:number'),
    ('nz-number', b'00', 'bad_value:number'), ('nz-number', b'007', 'bad_value:number'),
    ('nz-number', b'4294967296', 'bad_value:number'), ('nz-number', b'-0', 'bad_value:number'),
    ('quoted', b'', 'bad_value:quoted.syntax'), ('quoted', b'"', 'bad_value:quoted.syntax'),
    ('quoted', b'abc', 'bad_value:quoted.syntax'), ('quoted', b'"abc', 'bad_value:quoted.syntax'),
    ('quoted', b'abc"', 'bad_value:quoted.syntax'), ('quoted', b'"abc" ', 'bad_value:quoted.syntax'),
    ('quoted', b' "abc"', 'bad_value:quoted.syntax'), ('quoted', b'"a"b"', 'bad_value:quoted.syntax'),
    ('quoted', b'"abc\\"', 'bad_value:quoted.syntax'), ('quoted', b'"\\"', 'bad_value:quoted.syntax'),
    ('quoted', b'"""', 'bad_value:quoted.syntax'), ('quoted', b'"a"""', 'bad_value:quoted.syntax'),
    ('quoted', b'"abc"\r\n', 'bad_value:quoted.syntax'), ('quoted', b'"abc"x"', 'bad_value:quoted.syntax'),
    ('quoted', b"'abc'", 'bad_value:quoted.syntax'), ('quoted', b'{3}\r\nabc', 'bad_value:quoted.syntax'),
    ('quoted', b'"a\\n"', 'bad_value:quoted.char'), ('quoted', b'"a\\a"', 'bad_value:quoted.char'),
    ('quoted', b'"\\\r"', 'bad_value:quoted.char'), ('quoted', b'"\r"', 'bad_value:quoted.char'),
    ('quoted', b'"\n"', 'bad_value:quoted.char'), ('quoted', b'"a\r\nb"', 'bad_value:quoted.char'),
    ('quoted', b'"\x00"', 'bad_value:quoted.char'), ('quoted', b'"\x80"', 'bad_value:quoted.char'),
    ('quoted', b'"\xff"', 'bad_value:quoted.char'), ('quoted', b'"\\\x00"', 'bad_value:quoted.char'),
    ('quoted', b'"\\\x80"', 'bad_value:quoted.char'), ('quoted', b'"\\ "', 'bad_value:quoted.char'),
    ('literal', b'', 'bad_value:literal.syntax'), ('literal', b'abc', 'bad_value:literal.syntax'),
    ('literal', b'{', 'bad_value:literal.syntax'), ('literal', b'{3', 'bad_value:literal.syntax'),
    ('literal', b'{3}', 'bad_value:literal.syntax'), ('literal', b'{3}\r', 'bad_value:literal.syntax'),
    ('literal', b'{3}\n', 'bad_value:literal.syntax'), ('literal', b'{3}\nabc', 'bad_value:literal.syntax'),
    ('literal', b'{3}\rabc', 'bad_value:literal.syntax'), ('literal', b'{3}abc', 'bad_value:literal.syntax'),
    ('literal', b'{3}\n\rabc', 'bad_value:literal.syntax'), ('literal', b'3}\r\nabc', 'bad_value:literal.syntax'),
    ('literal', b' {3}\r\nabc', 'bad_value:literal.syntax'), ('literal', b'[3]\r\nabc', 'bad_value:literal.syntax'),
    ('literal', b'{3} \r\nabc', 'bad_value:literal.syntax'),
    ('literal', b'{}\r\n', 'bad_value:literal.count'), ('literal', b'{x}\r\n', 'bad_value:literal.count'),
    ('literal', b'{-1}\r\nabc', 'bad_value:literal.count'), ('literal', b'{+3}\r\nabc', 'bad_value:literal.count'),
    ('literal', b'{3+}\r\nabc', 'bad_value:literal.count'), ('literal', b'{ 3}\r\nabc', 'bad_value:literal.count'),
    ('literal', b'{3 }\r\nabc', 'bad_value:literal.count'), ('literal', b'{1.0}\r\nx', 'bad_value:literal.count'),
    ('literal', b'{4294967296}\r\n', 'bad_value:literal.count'), ('literal', b'{99999999999}\r\n', 'bad_value:literal.count'),
    ('literal', b'{' + b'9' * 3000 + b'}\r\n', 'bad_value:literal.count'),
    ('literal', b'{3}\r\nab', 'bad_value:literal.length'), ('literal', b'{3}\r\nabcd', 'bad_value:literal.length'),
    ('literal', b'{0}\r\nx', 'bad_value:literal.length'), ('literal', b'{1}\r\n', 'bad_value:literal.length'),
    ('literal', b'{3}\r\nabc\r\n', 'bad_value:literal.length'), ('literal', b'{4294967295}\r\nabc', 'bad_value:literal.length'),
    ('literal', b'{3}\r\n\x00bc', 'bad_value:literal.char'), ('literal', b'{3}\r\nab\x00', 'bad_value:literal.char'),
    ('literal', b'{1}\r\n\x00', 'bad_value:literal.char'),
    ('string', b'', 'bad_value:string.syntax'), ('string', b'abc', 'bad_value:string.syntax'),
    ('string', b'NIL', 'bad_value:string.syntax'), ('string', b' ""', 'bad_value:string.syntax'),
    ('string', b'(', 'bad_value:string.syntax'),
    ('string', b'"abc', 'bad_value:quoted.syntax'), ('string', b'{3}\r\nab', 'bad_value:literal.length'),
    ('astring', b'"abc', 'bad_value:quoted.syntax'), ('astring', b'{3}\r\nab', 'bad_value:literal.length'),
    ('nstring', b'"abc', 'bad_value:quoted.syntax'), ('nstring', b'{3}\r\nab', 'bad_value:literal.length'),
    ('nstring', b'', 'bad_value:nstring.syntax'), ('nstring', b'abc', 'bad_value:nstring.syntax'),
    ('nstring', b'nill', 'bad_value:nstring.syntax'), ('nstring', b'ni', 'bad_value:nstring.syntax'),
    ('nstring', b' nil', 'bad_value:nstring.syntax'), ('nstring', b'nil ', 'bad_value:nstring.syntax'),
    ('nstring', b'NIL\r\n', 'bad_value:nstring.syntax'), ('nstring', b'n1l', 'bad_value:nstring.syntax'),
    ('nstring', b'NI\xcc', 'bad_value:nstring.syntax'),
)


@pytest.mark.parametrize('rule,data,code', _BAD)
def test_parse_refusals_one_by_one_and_is_valid_false(rule, data, code):
    refuse(PA, code, rule, data)
    assert m.imap_is_valid(rule, data) is False


def test_numbers_by_digit_arithmetic_agree_with_python_on_every_boundary_and_fuzz():
    rnd = random.Random(3501)
    for n in (0, 1, 9, 10, 99, 100, 255, 256, 65535, 65536, 2 ** 31 - 1, 2 ** 31, 2 ** 32 - 2, 2 ** 32 - 1):
        for z in (0, 1, 5):
            t = b'0' * z + str(n).encode()
            assert m.imap_parse('number', t) == ('number', n)
    for n in (2 ** 32, 2 ** 32 + 1, 2 ** 33, 10 ** 10, 10 ** 12, 2 ** 40, 10 ** 30):
        refuse(PA, 'bad_value:number', 'number', str(n).encode())
        refuse(PA, 'bad_value:number', 'nz-number', str(n).encode())
        refuse(PA, 'bad_value:literal.count', 'literal', b'{' + str(n).encode() + b'}\r\n')
    for _ in range(3000):
        n = rnd.randrange(0, 2 ** 33)
        t = str(n).encode()
        if n < 2 ** 32:
            assert m.imap_parse('number', t) == ('number', n)
            assert m.imap_format('number', n) == t
            if n:
                assert m.imap_format('nz-number', n) == t
        else:
            assert m.imap_is_valid('number', t) is False
    for n in range(0, 300):
        assert m.imap_format('number', n) == str(n).encode()
    refuse(FM, 'bad_value:number', 'nz-number', 0)
    refuse(FM, 'bad_value:number', 'number', -1)
    refuse(FM, 'bad_value:number', 'number', 2 ** 32)
    refuse(FM, 'bad_value:number', 'nz-number', 2 ** 32)
    refuse(FM, 'bad_value:number', 'number', 10 ** 5000)
    assert m.imap_format('number', 2 ** 32 - 1) == b'4294967295'
    assert m.imap_format('nz-number', 1) == b'1' and m.imap_format('number', 0) == b'0'
    assert m.imap_format('number', 10) == b'10' and m.imap_format('number', 100) == b'100'


def test_literal_count_must_match_the_octets_exactly_for_every_small_count():
    for n in range(0, 40):
        body = bytes((i % 255) + 1 for i in range(n))
        head = b'{' + str(n).encode() + b'}\r\n'
        assert m.imap_parse('literal', head + body) == ('literal', body)
        if n:
            refuse(PA, 'bad_value:literal.length', 'literal', head + body[:-1])
        refuse(PA, 'bad_value:literal.length', 'literal', head + body + b'x')
        refuse(PA, 'bad_value:literal.length', 'literal', b'{' + str(n + 1).encode() + b'}\r\n' + body)


_FMT = (
    ('atom', b'abc', b'abc'), ('atom', b'INBOX', b'INBOX'), ('tag', b'A1', b'A1'),
    ('quoted', b'', b'""'), ('quoted', b'abc', b'"abc"'), ('quoted', b'a b', b'"a b"'), ('quoted', b'a"b', b'"a\\"b"'),
    ('quoted', b'a\\b', b'"a\\\\b"'), ('quoted', b'"', b'"\\""'), ('quoted', b'\\"', b'"\\\\\\""'), ('quoted', b'\x7f\x01', b'"\x7f\x01"'),
    ('literal', b'', b'{0}\r\n'), ('literal', b'abc', b'{3}\r\nabc'), ('literal', b'a\r\nb', b'{4}\r\na\r\nb'),
    ('literal', b'\xff\x01', b'{2}\r\n\xff\x01'), ('literal', b'x' * 10, b'{10}\r\n' + b'x' * 10),
    ('literal', b'x' * 100, b'{100}\r\n' + b'x' * 100), ('literal', b'x' * 2000, b'{2000}\r\n' + b'x' * 2000),
    ('string', b'', b'""'), ('string', b'abc', b'"abc"'), ('string', b'a"b', b'"a\\"b"'), ('string', b'a\nb', b'{3}\r\na\nb'),
    ('string', b'a\rb', b'{3}\r\na\rb'), ('string', b'\x80', b'{1}\r\n\x80'), ('string', b'a\xffb', b'{3}\r\na\xffb'),
    ('astring', b'abc', b'abc'), ('astring', b'a]c', b'a]c'), ('astring', b'', b'""'), ('astring', b'a b', b'"a b"'),
    ('astring', b'a(b', b'"a(b"'), ('astring', b'a%', b'"a%"'), ('astring', b'a\nb', b'{3}\r\na\nb'),
    ('astring', b'NIL', b'NIL'), ('astring', b'\xff', b'{1}\r\n\xff'), ('astring', b'a"', b'"a\\""'),
    ('nstring', None, b'NIL'), ('nstring', b'', b'""'), ('nstring', b'NIL', b'"NIL"'), ('nstring', b'abc', b'"abc"'),
    ('nstring', b'a\nb', b'{3}\r\na\nb'),
)


@pytest.mark.parametrize('rule,value,out', _FMT)
def test_format_examples_exact_and_parse_gives_the_value_back(rule, value, out):
    got = m.imap_format(rule, value)
    assert got == out and type(got) is bytes
    kind, back = m.imap_parse(rule, got)
    if value is None:
        assert kind == 'nil' and back is None
    else:
        assert back == value


def test_format_policy_astring_atom_then_quoted_then_literal_over_every_byte():
    for b in range(1, 256):
        one = bytes([b])
        out = m.imap_format('astring', one)
        if b in _ASTRING_CHARS:
            assert out == one, b
        elif b <= 127 and b not in (10, 13):
            assert out == b'"' + (b'\\' if b in (34, 92) else b'') + one + b'"', b
        else:
            assert out == b'{1}\r\n' + one, b
        assert m.imap_parse('astring', out)[1] == one
        outs = m.imap_format('string', one)
        if b <= 127 and b not in (10, 13):
            assert outs == b'"' + (b'\\' if b in (34, 92) else b'') + one + b'"', b
        else:
            assert outs == b'{1}\r\n' + one, b
        assert m.imap_parse('string', outs)[1] == one
    refuse(FM, 'bad_value:literal.char', 'astring', b'\x00')
    refuse(FM, 'bad_value:literal.char', 'string', b'\x00')
    refuse(FM, 'bad_value:literal.char', 'nstring', b'a\x00')
    refuse(FM, 'bad_value:literal.char', 'literal', b'\x00')
    refuse(FM, 'bad_value:quoted.char', 'quoted', b'\x00')
    refuse(FM, 'bad_value:quoted.char', 'quoted', b'a\n')
    refuse(FM, 'bad_value:quoted.char', 'quoted', b'a\r')
    refuse(FM, 'bad_value:quoted.char', 'quoted', b'a\x80')
    refuse(FM, 'bad_value:atom', 'atom', b'')
    refuse(FM, 'bad_value:atom', 'atom', b'a b')
    refuse(FM, 'bad_value:atom', 'atom', b']')
    refuse(FM, 'bad_value:atom', 'tag', b'+')
    refuse(FM, 'bad_value:atom', 'tag', b'')
    assert m.imap_format('tag', b']') == b']' and m.imap_format('atom', b'+') == b'+'


def test_format_then_parse_is_identity_on_fuzz_for_every_rule():
    rnd = random.Random(99)
    ok = bad = 0
    for _ in range(6000):
        rule = rnd.choice(_RULES)
        if rule in ('number', 'nz-number'):
            v = rnd.choice((0, 1, 5, 2 ** 32 - 1, 2 ** 32, -1, rnd.randrange(0, 2 ** 33)))
        elif rule == 'nstring' and rnd.random() < 0.2:
            v = None
        else:
            pool = b'abAB09 "\\()]{}%*+\r\n\x00\x7f\x80\xff'
            v = bytes(rnd.choice(pool) for _ in range(rnd.randrange(0, 8)))
        try:
            out = m.imap_format(rule, v)
        except ValueError:
            bad += 1
            continue
        ok += 1
        assert type(out) is bytes and len(out) <= m.MAX_DATA
        kind, back = m.imap_parse(rule, out)
        assert back == v and m.imap_is_valid(rule, out) is True
    assert ok > 2000 and bad > 300


def _ref(rule, d):
    # independent reference built from regular expressions over bytes
    atom = b'[' + re.escape(bytes(sorted(_ATOM_CHARS))) + b']'
    astr = b'[' + re.escape(bytes(sorted(_ASTRING_CHARS))) + b']'
    tagc = b'[' + re.escape(bytes(sorted(_TAG_CHARS))) + b']'
    num = rb'[0-9]+'
    qchar = rb'(?:[\x01-\x09\x0b\x0c\x0e-\x21\x23-\x5b\x5d-\x7f]|\\["\\])'
    quoted = rb'"' + qchar + rb'*"'
    def isnum(t, nz=False):
        if not re.fullmatch(num, t):
            return False
        if nz and t[:1] == b'0':
            return False
        v = 0
        for c in t:
            v = v * 10 + c - 48
        return v <= 4294967295 and not (nz and v == 0)
    def lit(t):
        mm = re.fullmatch(rb'\{([^}]*)\}\r\n(.*)', t, re.S)
        return bool(mm) and isnum(mm.group(1)) and len(mm.group(2)) == int(mm.group(1)) and b'\x00' not in mm.group(2)
    if rule == 'atom':
        return re.fullmatch(atom + b'+', d) is not None
    if rule == 'tag':
        return re.fullmatch(tagc + b'+', d) is not None
    if rule == 'number':
        return isnum(d)
    if rule == 'nz-number':
        return isnum(d, True)
    q = re.fullmatch(quoted, d) is not None
    l = lit(d)
    if rule == 'quoted':
        return q
    if rule == 'literal':
        return l
    if rule == 'string':
        return q or l
    if rule == 'astring':
        return q or l or re.fullmatch(astr + b'+', d) is not None
    return q or l or d.lower() == b'nil'


def test_is_valid_agrees_with_an_independent_regex_reference_on_fuzz():
    rnd = random.Random(8)
    pool = [b'a', b'Z', b'0', b'9', b'"', b'\\', b'{', b'}', b'3', b'\r\n', b'\r', b'\n', b' ', b']', b'+', b'(', b'%', b'nil', b'NIL',
            b'\x00', b'\x80', b'abc', b'{1}\r\n', b'{0}\r\n', b'1', b'']
    t = f = 0
    for _ in range(12000):
        rule = rnd.choice(_RULES)
        d = b''.join(rnd.choice(pool) for _ in range(rnd.randrange(0, 7)))
        ref = _ref(rule, d)
        assert m.imap_is_valid(rule, d) is ref, (rule, d)
        t += ref
        f += not ref
    assert t > 300 and f > 1500


def test_nz_number_refuses_every_leading_zero_form_at_parse_and_valid():
    # nz-number = digit-nz *DIGIT: the first digit is %x31-39, so any leading zero is refused
    for z in (1, 2, 3, 10, 100, 1000, 4095):
        for tail in (b'', b'0', b'7', b'123'):
            d = b'0' * z + tail
            if len(d) > m.MAX_DATA:
                continue
            refuse(PA, 'bad_value:number', 'nz-number', d)
            assert m.imap_is_valid('nz-number', d) is False, d
    for d in (b'1', b'9', b'10', b'90', b'100', b'4294967295', b'1000000000'):
        assert m.imap_parse('nz-number', d) == ('number', int(d.decode())), d
        assert m.imap_is_valid('nz-number', d) is True, d
    # the number rule keeps allowing leading zeros
    assert m.imap_parse('number', b'0001') == ('number', 1)
    assert m.imap_is_valid('number', b'007') is True


def test_data_cap_exact_at_4096_and_4097_for_every_rule():
    assert m.MAX_DATA == 4096 and type(m.MAX_DATA) is int
    assert m.MAX_VALUE == 2000 and type(m.MAX_VALUE) is int
    assert m.MAX_NUMBER == 4294967295 and type(m.MAX_NUMBER) is int
    for rule in _RULES:
        refuse(PA, 'bad_value:data.length', rule, b'a' * 4097)
        refuse(PA, 'bad_value:data.length', rule, b'\x00' * 4097)
        assert m.imap_is_valid(rule, b'a' * 4097) is False
    assert m.imap_parse('atom', b'a' * 4096) == ('atom', b'a' * 4096)
    assert m.imap_parse('tag', b'a' * 4096)[1] == b'a' * 4096
    assert m.imap_parse('number', b'0' * 4096) == ('number', 0)
    refuse(PA, 'bad_value:number', 'nz-number', b'0' * 4095 + b'7')
    assert m.imap_is_valid('nz-number', b'0' * 4095 + b'7') is False
    refuse(PA, 'bad_value:number', 'nz-number', b'0' * 4096)
    q = b'"' + b'a' * 4094 + b'"'
    assert len(q) == 4096 and m.imap_parse('quoted', q)[1] == b'a' * 4094
    refuse(PA, 'bad_value:data.length', 'quoted', b'"' + b'a' * 4095 + b'"')
    body = b'x' * 4088
    assert len(b'{4088}\r\n' + body) == 4096
    assert m.imap_parse('literal', b'{4088}\r\n' + body)[1] == body
    refuse(PA, 'bad_value:data.length', 'literal', b'{4089}\r\n' + body + b'x')
    # the cap is judged before the syntax
    refuse(PA, 'bad_value:data.length', 'quoted', b'a' * 4097)
    refuse(PA, 'bad_value:data.length', 'literal', b'a' * 4097)
    refuse(PA, 'bad_value:data.length', 'number', b'x' * 4097)


def test_format_value_cap_exact_at_2000_and_2001_and_every_output_parses_back_within_the_cap():
    for rule in ('atom', 'tag', 'quoted', 'literal', 'string', 'astring', 'nstring'):
        refuse(FM, 'bad_value:value.length', rule, b'a' * 2001)
        refuse(FM, 'bad_value:value.length', rule, b'\x00' * 2001)
        out = m.imap_format(rule, b'a' * 2000)
        assert m.imap_parse(rule, out)[1] == b'a' * 2000
    worst = b'"' * 2000
    out = m.imap_format('quoted', worst)
    assert len(out) == 4002 and m.imap_parse('quoted', out)[1] == worst
    out = m.imap_format('astring', b'\\' * 2000)
    assert len(out) == 4002 and m.imap_parse('astring', out)[1] == b'\\' * 2000
    out = m.imap_format('literal', b'\xff' * 2000)
    assert len(out) == 2008 and m.imap_parse('literal', out)[1] == b'\xff' * 2000
    refuse(FM, 'bad_value:value.length', 'atom', b' ' * 2001)
    refuse(FM, 'bad_value:value.length', 'quoted', b'\x00' * 2001)


def test_no_int_call_on_input_works_under_a_tiny_int_str_limit():
    import sys as _s
    old = _s.get_int_max_str_digits()
    _s.set_int_max_str_digits(640)
    try:
        assert m.imap_parse('number', b'0' * 4000 + b'12') == ('number', 12)
        refuse(PA, 'bad_value:number', 'number', b'9' * 4000)
        refuse(PA, 'bad_value:literal.count', 'literal', b'{' + b'9' * 4000 + b'}\r\n')
        assert m.imap_parse('literal', b'{' + b'0' * 4000 + b'2}\r\nab')[1] == b'ab'
        assert m.imap_format('number', 4294967295) == b'4294967295'
        refuse(FM, 'bad_value:number', 'number', 10 ** 639)
    finally:
        _s.set_int_max_str_digits(old)


def test_literal_check_order_and_quoted_left_to_right_with_both_fields_wrong_witnesses():
    # literal: leading brace, closing brace, CRLF, count, length, NUL
    refuse(PA, 'bad_value:literal.syntax', 'literal', b'x}')
    refuse(PA, 'bad_value:literal.syntax', 'literal', b'{x')
    refuse(PA, 'bad_value:literal.syntax', 'literal', b'{x}\n')
    refuse(PA, 'bad_value:literal.syntax', 'literal', b'{99999999999}\n')
    refuse(PA, 'bad_value:literal.count', 'literal', b'{x}\r\n\x00\x00')
    refuse(PA, 'bad_value:literal.count', 'literal', b'{99999999999}\r\n\x00')
    refuse(PA, 'bad_value:literal.length', 'literal', b'{5}\r\n\x00')
    refuse(PA, 'bad_value:literal.length', 'literal', b'{1}\r\n\x00\x00')
    refuse(PA, 'bad_value:literal.char', 'literal', b'{2}\r\n\x00x')
    # quoted: the first problem from the left wins
    refuse(PA, 'bad_value:quoted.char', 'quoted', b'"\x00"x"')
    refuse(PA, 'bad_value:quoted.syntax', 'quoted', b'"a"\x00"')
    refuse(PA, 'bad_value:quoted.char', 'quoted', b'"\\a"x"')
    refuse(PA, 'bad_value:quoted.syntax', 'quoted', b'"a"\\a"')
    refuse(PA, 'bad_value:quoted.char', 'quoted', b'"\x80\\"')
    refuse(PA, 'bad_value:quoted.char', 'quoted', b'"\\\x80\\"')
    refuse(PA, 'bad_value:quoted.syntax', 'quoted', b'x"\x00"')
    refuse(PA, 'bad_value:quoted.syntax', 'quoted', b'"\x00"x')
    # string family: the first byte selects the branch, then that branch's errors
    refuse(PA, 'bad_value:string.syntax', 'string', b'\x00')
    refuse(PA, 'bad_value:quoted.syntax', 'string', b'"\x00')
    refuse(PA, 'bad_value:literal.syntax', 'astring', b'{ ')
    refuse(PA, 'bad_value:literal.syntax', 'nstring', b'{ ')
    refuse(PA, 'bad_value:atom', 'astring', b'a"')
    refuse(PA, 'bad_value:nstring.syntax', 'nstring', b'a"')
    # the lower-case nil test is on the whole input
    assert m.imap_parse('nstring', b'NIL')[0] == 'nil'
    for bad in (b'NIL ', b'NILL', b'NI', b'N', b'', b'nil\x00', b'\x00nil'):
        refuse(PA, 'bad_value:nstring.syntax', 'nstring', bad)


def test_literal_must_start_with_an_open_brace_for_every_first_byte():
    for b in range(256):
        data = bytes([b]) + b'3}\r\nabc'
        assert m.imap_is_valid('literal', data) is (b == 123), b
        if b != 123:
            refuse(PA, 'bad_value:literal.syntax', 'literal', data)
    assert m.imap_parse('literal', b'{3}\r\nabc') == ('literal', b'abc')


def test_format_refuses_negative_numbers_exactly_for_every_negative_boundary():
    for rule in ('number', 'nz-number'):
        for v in (-1, -2, -9, -10, -4294967295, -4294967296, -(10 ** 30)):
            refuse(FM, 'bad_value:number', rule, v)
    assert m.imap_format('number', 0) == b'0'
    assert m.imap_format('nz-number', 1) == b'1'


# ================= hostile types, exact-type pins at every site =================
class _BytesSub(bytes):
    def __len__(self):
        _Spy.calls.append('bytes_len')
        return 1

    def __iter__(self):
        _Spy.calls.append('bytes_iter')
        return iter(())

    def find(self, *a):
        _Spy.calls.append('bytes_find')
        return -1

    def lower(self):
        _Spy.calls.append('bytes_lower')
        return b'nil'


class _BoolLike:
    def __bool__(self):
        _Spy.calls.append('bool')
        return True


def _bad_data():
    return [None, 1, 1.5, True, 'atom', bytearray(b'abc'), [b'abc'], (b'abc',), {b'abc': 1}, object(), _Liar(), _StrSub('abc'),
            _IntSub(1), memoryview(b'abc'), _BytesSub(b'abc'), 1j, bytes, type]


def _bad_rule():
    return [None, 1, 1.5, True, b'atom', bytearray(b'atom'), ['atom'], ('atom',), object(), _Liar(), _StrSub('atom'), _IntSub(1), str]


def test_every_parse_and_valid_site_refuses_every_non_exact_input_type_and_makes_no_dunder_call():
    for fn in (PA, IV):
        for bad in _bad_data():
            for rule in _RULES:
                _Spy.calls.clear()
                refuse(fn, 'bad_type:data', rule, bad)
                assert _Spy.calls == [], (fn, rule, bad)
        for bad in _bad_rule():
            _Spy.calls.clear()
            refuse(fn, 'bad_type:rule', bad, b'abc')
            refuse(fn, 'bad_type:rule', bad, 5)
            assert _Spy.calls == [], (fn, bad)


def test_unknown_rule_names_are_refused_exactly_and_case_and_space_matter():
    for rule in ('', 'ATOM', 'Atom', 'atom ', ' atom', 'nz_number', 'nznumber', 'numbers', 'list-mailbox', 'mailbox', 'text', 'astrings',
                 'at', 'atom\x00', 'atom\n', 'str', 'nil', 'literal8', 'string8', 'quoted-string', '\u0430tom', 'n\u1d1cmber', 'tag ', 'TAG'):
        refuse(PA, 'bad_value:rule', rule, b'abc')
        refuse(IV, 'bad_value:rule', rule, b'abc')
        refuse(FM, 'bad_value:rule', rule, b'abc')
    for rule in _RULES:
        assert m.imap_is_valid(rule, b'a') is (rule in ('atom', 'astring', 'tag'))


def test_format_refuses_every_non_exact_value_type_per_rule_and_makes_no_dunder_call():
    bad_bytes = [None, 1, 1.5, True, 'abc', bytearray(b'abc'), [b'abc'], (b'abc',), object(), _Liar(), _StrSub('abc'), _IntSub(1),
                 memoryview(b'abc'), _BytesSub(b'abc'), {b'a': 1}]
    for rule in ('atom', 'tag', 'quoted', 'literal', 'string', 'astring'):
        for bad in bad_bytes:
            _Spy.calls.clear()
            refuse(FM, 'bad_type:value', rule, bad)
            assert _Spy.calls == [], (rule, bad)
    for bad in bad_bytes[1:]:
        _Spy.calls.clear()
        refuse(FM, 'bad_type:value', 'nstring', bad)
        assert _Spy.calls == [], bad
    for rule in ('number', 'nz-number'):
        for bad in (None, 1.0, 1.5, True, False, '1', b'1', [1], (1,), _IntSub(1), _Liar(), object(), 1j, bytearray(b'1')):
            _Spy.calls.clear()
            refuse(FM, 'bad_type:value', rule, bad)
            assert _Spy.calls == [], (rule, bad)
    for bad in _bad_rule():
        _Spy.calls.clear()
        refuse(FM, 'bad_type:rule', bad, b'abc')
        refuse(FM, 'bad_type:rule', bad, 5)
        assert _Spy.calls == []
    assert m.imap_format('nstring', None) == b'NIL'


def test_check_order_for_parse_and_valid_with_both_fields_wrong_witnesses():
    for fn in (PA, IV):
        refuse(fn, 'bad_type:rule', 5, 5)
        refuse(fn, 'bad_type:rule', None, b'a' * 5000)
        refuse(fn, 'bad_type:data', 'atom', 5)
        refuse(fn, 'bad_type:data', 'nope', 5)
        refuse(fn, 'bad_value:rule', 'nope', b'a')
        refuse(fn, 'bad_value:rule', 'nope', b'a' * 5000)
        refuse(fn, 'bad_value:rule', '', b'\x00' * 5000)
    refuse(PA, 'bad_value:data.length', 'atom', b'\x00' * 4097)
    refuse(PA, 'bad_value:data.length', 'quoted', b'\x00' * 4097)


def test_check_order_for_format_with_both_fields_wrong_witnesses():
    refuse(FM, 'bad_type:rule', 5, 5)
    refuse(FM, 'bad_type:rule', None, None)
    refuse(FM, 'bad_value:rule', 'nope', 5)
    refuse(FM, 'bad_value:rule', 'nope', None)
    refuse(FM, 'bad_value:rule', '', b'a' * 5000)
    refuse(FM, 'bad_type:value', 'atom', 5)
    refuse(FM, 'bad_type:value', 'number', b'a' * 5000)
    refuse(FM, 'bad_type:value', 'number', True)
    refuse(FM, 'bad_type:value', 'nz-number', 0.0)
    refuse(FM, 'bad_type:value', 'atom', None)
    refuse(FM, 'bad_type:value', 'nstring', 'x' * 5000)
    # the value length comes before every content check
    refuse(FM, 'bad_value:value.length', 'atom', b' ' * 2001)
    refuse(FM, 'bad_value:value.length', 'tag', b'+' * 2001)
    refuse(FM, 'bad_value:value.length', 'literal', b'\x00' * 2001)
    refuse(FM, 'bad_value:value.length', 'string', b'\x00' * 2001)
    refuse(FM, 'bad_value:value.length', 'astring', b'\x00' * 2001)
    refuse(FM, 'bad_value:value.length', 'nstring', b'\x00' * 2001)
    # numbers: the type before the range
    refuse(FM, 'bad_value:number', 'number', -1)
    refuse(FM, 'bad_value:number', 'nz-number', -1)
    refuse(FM, 'bad_value:number', 'nz-number', 0)


def test_returned_values_are_fresh_exact_types():
    a = m.imap_parse('literal', b'{3}\r\nabc')
    b = m.imap_parse('literal', b'{3}\r\nabc')
    assert a == b and type(a[1]) is bytes and type(a[0]) is str
    src = bytearray(b'abc')
    assert type(m.imap_parse('atom', bytes(src))[1]) is bytes
    for r, d in (('atom', b'a'), ('tag', b'a'), ('quoted', b'""'), ('literal', b'{0}\r\n'), ('string', b'""'), ('astring', b'a'),
                 ('nstring', b'NIL'), ('number', b'1'), ('nz-number', b'1')):
        assert type(m.imap_parse(r, d)) is tuple
        assert m.imap_is_valid(r, d) is True
    assert m.imap_is_valid('atom', b'a b') is False
    for r, v in (('atom', b'a'), ('number', 5), ('nstring', None), ('literal', b'')):
        assert type(m.imap_format(r, v)) is bytes


# ================= cap-before-work =================
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


def test_no_allocation_or_work_before_the_cap_check_on_oversized_inputs():
    bound = 100000
    for big in (b'a' * 3000000, b'"' * 3000000, b'{' + b'9' * 3000000, b'0' * 3000000, b'\x00' * 3000000, b'\xff' * 3000000):
        for rule in _RULES:
            assert _peak_refusal(PA, 'bad_value:data.length', rule, big) < bound
            def call(rule=rule, big=big):
                with pytest.raises(ValueError):
                    m.imap_parse(rule, big)
            assert _trace(call) < 20
            def call2(rule=rule, big=big):
                assert m.imap_is_valid(rule, big) is False
            assert _trace(call2) < 20
    for fn in (PA, IV):
        assert _peak_refusal(fn, 'bad_type:data', 'atom', 'a' * 3000000) < bound
        assert _peak_refusal(fn, 'bad_value:rule', 'x' * 3000000, b'a') < bound
    for rule in ('atom', 'tag', 'quoted', 'literal', 'string', 'astring', 'nstring'):
        for big in (b'a' * 3000000, b'"' * 3000000, b'\x00' * 3000000):
            assert _peak_refusal(FM, 'bad_value:value.length', rule, big) < bound
            def callf(rule=rule, big=big):
                with pytest.raises(ValueError):
                    m.imap_format(rule, big)
            assert _trace(callf) < 20
    assert _peak_refusal(FM, 'bad_value:number', 'number', 10 ** 200000) < bound * 4
    assert _peak_refusal(FM, 'bad_value:rule', 'x' * 3000000, b'a') < bound
    # a refusal inside the cap does bounded work
    def inside():
        with pytest.raises(ValueError):
            m.imap_parse('number', b'9' * 4096)
    assert _trace(inside) < 30000
    def inside2():
        with pytest.raises(ValueError):
            m.imap_parse('quoted', b'"' + b'a' * 4093 + b'\x00"')
    assert _trace(inside2) < 30000
    def inside3():
        with pytest.raises(ValueError):
            m.imap_parse('literal', b'{4088}\r\n' + b'a' * 4087 + b'\x00')
    assert _trace(inside3) < 30000


# ================= module namespace and literal pins =================
_NS_BASE = ['ADJACENT', 'CLAIMS', 'MAX_DATA', 'MAX_NUMBER', 'MAX_VALUE', 'NOT_CLAIMED', 'SCOPE', '_ATOM', '_DIGITS', '_No', '__builtins__',
            '__doc__', '__name__', '_RULES', '_atomlike', '_check', '_dec', '_fliteral', '_format', '_fquoted', '_fstring', '_literal',
            '_no', '_num', '_parse', '_quotable', '_quoted', 'imap_format', 'imap_is_valid', 'imap_parse', 'make_fail']


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
    assert m.MAX_DATA == 4096 and m.MAX_VALUE == 2000 and m.MAX_NUMBER == 2 ** 32 - 1
    for n in ('MAX_DATA', 'MAX_VALUE', 'MAX_NUMBER'):
        assert type(getattr(m, n)) is int
    assert m._DIGITS == b'0123456789' and type(m._DIGITS) is bytes
    assert m._ATOM == bytes(sorted(_ATOM_CHARS)) and type(m._ATOM) is bytes and len(m._ATOM) == 86
    assert m._ATOM == b"!#$&'+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[^_`abcdefghijklmnopqrstuvwxyz|}~"
    assert m._RULES == ('atom', 'number', 'nz-number', 'quoted', 'literal', 'string', 'astring', 'nstring', 'tag')
    assert type(m._RULES) is tuple
    assert m.CLAIMS is False
    assert issubclass(m._No, Exception) and m._No.__mro__[1] is Exception
    with pytest.raises(m._No) as e:
        m._no('x')
    assert e.value.args == ('x',)


def test_module_source_is_ascii_and_uses_no_int_call_no_regex_no_clock_no_import_beyond_the_guard():
    import ast
    raw = pathlib.Path(m.__file__).read_bytes()
    raw.decode('ascii')
    assert b'\r' not in raw and raw.endswith(b'\n')
    tree = ast.parse(raw.decode('ascii'))
    names = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert 'int' not in names and 'str' not in names and 'float' not in names and 'isinstance' not in names and 'ord' not in names
    assert not attrs & {'isdigit', 'isalpha', 'isalnum', 'isdecimal', 'isnumeric', 'isascii', 'strip', 'lstrip', 'rstrip', 'upper',
                        'casefold', 'decode', 'encode', 'from_bytes', 'to_bytes', 'index', 'hex', 'fromhex', 'match', 'search',
                        'fullmatch', 'sub', 'compile', 'startswith', 'endswith', 'format', 'translate', 'time', 'now', 'today',
                        'deepcopy', 'copy', 'loads', 'dumps', 'items', 'keys', 'values', 'get', 'pop', 'sort', 'split', 'partition'}
    assert attrs == {'append', 'count', 'find', 'find_spec', 'lower', 'name', 'reverse'}
    assert names == {'ValueError', '_No', '_atomlike', '_check', '_dec', '_fliteral', '_format', '_fquoted', '_fstring', '_literal',
                     '_num', '_parse', '_quotable', '_quoted', 'bytes', 'f', 'len', 'make_fail', 'type'}
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert len(imports) == 2
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.Global, ast.Nonlocal, ast.Lambda))]
    assert len([n for n in ast.walk(tree) if isinstance(n, ast.Try)]) == 3


# ================= every refusal site, no import on any of them =================
def _site_cases():
    pa, iv, fm = PA, IV, FM
    return [
        # _check
        (pa, 'bad_type:rule', (1, b'a')), (pa, 'bad_type:data', ('atom', 1)), (pa, 'bad_value:rule', ('x', b'a')),
        (iv, 'bad_type:rule', (1, b'a')), (iv, 'bad_type:data', ('atom', 1)), (iv, 'bad_value:rule', ('x', b'a')),
        # _parse
        (pa, 'bad_value:data.length', ('atom', b'a' * 4097)), (pa, 'bad_value:number', ('nz-number', b'0')),
        (pa, 'bad_value:string.syntax', ('string', b'a')), (pa, 'bad_value:nstring.syntax', ('nstring', b'a')),
        # _num
        (pa, 'bad_value:number', ('number', b'')), (pa, 'bad_value:number', ('number', b'x')),
        (pa, 'bad_value:number', ('number', b'4294967296')), (pa, 'bad_value:literal.count', ('literal', b'{}\r\n')),
        (pa, 'bad_value:literal.count', ('literal', b'{x}\r\n')), (pa, 'bad_value:literal.count', ('literal', b'{4294967296}\r\n')),
        # _atomlike
        (pa, 'bad_value:atom', ('atom', b'')), (pa, 'bad_value:atom', ('atom', b']')), (pa, 'bad_value:atom', ('tag', b'+')),
        (pa, 'bad_value:atom', ('atom', b' ')),
        # _quoted
        (pa, 'bad_value:quoted.syntax', ('quoted', b'"')), (pa, 'bad_value:quoted.syntax', ('quoted', b'"\\"')),
        (pa, 'bad_value:quoted.char', ('quoted', b'"\\a"')), (pa, 'bad_value:quoted.syntax', ('quoted', b'"a"b"')),
        (pa, 'bad_value:quoted.char', ('quoted', b'"\x00"')),
        # _literal
        (pa, 'bad_value:literal.syntax', ('literal', b'x')), (pa, 'bad_value:literal.syntax', ('literal', b'{3')),
        (pa, 'bad_value:literal.syntax', ('literal', b'{3}x')), (pa, 'bad_value:literal.length', ('literal', b'{3}\r\nab')),
        (pa, 'bad_value:literal.char', ('literal', b'{1}\r\n\x00')),
        # imap_format
        (fm, 'bad_type:rule', (1, b'a')), (fm, 'bad_value:rule', ('x', b'a')), (fm, 'bad_type:value', ('number', b'1')),
        (fm, 'bad_type:value', ('nstring', 'x')), (fm, 'bad_type:value', ('atom', 'x')), (fm, 'bad_value:number', ('number', -1)),
        (fm, 'bad_value:number', ('nz-number', 0)), (fm, 'bad_value:value.length', ('atom', b'a' * 2001)),
        (fm, 'bad_value:atom', ('atom', b' ')), (fm, 'bad_value:quoted.char', ('quoted', b'\x00')),
        (fm, 'bad_value:literal.char', ('literal', b'\x00')), (fm, 'bad_value:literal.char', ('string', b'\x00')),
    ]


_ALL_CODES = (
    'bad_type:rule', 'bad_type:data', 'bad_type:value', 'bad_value:rule', 'bad_value:data.length', 'bad_value:atom',
    'bad_value:number', 'bad_value:quoted.syntax', 'bad_value:quoted.char', 'bad_value:literal.syntax', 'bad_value:literal.count',
    'bad_value:literal.length', 'bad_value:literal.char', 'bad_value:string.syntax', 'bad_value:nstring.syntax',
    'bad_value:value.length')


def _ok_calls():
    assert m.imap_parse('atom', b'a') == ('atom', b'a')
    assert m.imap_parse('tag', b'a]') == ('tag', b'a]')
    assert m.imap_parse('number', b'12') == ('number', 12)
    assert m.imap_parse('nz-number', b'12') == ('number', 12)
    assert m.imap_parse('quoted', b'"a\\"\\\\b"') == ('quoted', b'a"\\b')
    assert m.imap_parse('literal', b'{2}\r\nab') == ('literal', b'ab')
    assert m.imap_parse('string', b'""') == ('quoted', b'')
    assert m.imap_parse('string', b'{0}\r\n') == ('literal', b'')
    assert m.imap_parse('astring', b'a]') == ('atom', b'a]')
    assert m.imap_parse('astring', b'"a"') == ('quoted', b'a')
    assert m.imap_parse('nstring', b'NiL') == ('nil', None)
    assert m.imap_parse('nstring', b'{1}\r\nx') == ('literal', b'x')
    assert m.imap_is_valid('atom', b'a') is True and m.imap_is_valid('atom', b'') is False
    assert m.imap_format('number', 0) == b'0' and m.imap_format('number', 1234567890) == b'1234567890'
    assert m.imap_format('nz-number', 7) == b'7'
    assert m.imap_format('atom', b'a') == b'a' and m.imap_format('tag', b'a') == b'a'
    assert m.imap_format('quoted', b'a"\\') == b'"a\\"\\\\"'
    assert m.imap_format('literal', b'ab') == b'{2}\r\nab'
    assert m.imap_format('string', b'a') == b'"a"' and m.imap_format('string', b'a\n') == b'{2}\r\na\n'
    assert m.imap_format('astring', b'a') == b'a' and m.imap_format('astring', b'a b') == b'"a b"'
    assert m.imap_format('astring', b'a\nb') == b'{3}\r\na\nb'
    assert m.imap_format('nstring', None) == b'NIL' and m.imap_format('nstring', b'a') == b'"a"'


def test_site_cases_cover_exactly_the_documented_codes_and_each_raises_it():
    cases = _site_cases()
    assert set(c for _f, c, _a in cases) == set(_ALL_CODES)
    assert len(_ALL_CODES) == len(set(_ALL_CODES)) == 16
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
    assert len(want) == 33 and len(returns) == 35
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
    for fn, code, args in _site_cases():
        _start_import(builtins, hook)
        sys.settrace(tracer)
        try:
            with pytest.raises(Exception) as e:
                getattr(m, fn)(*args)
        finally:
            sys.settrace(prev)
            _stop_import()
        assert str(e.value) == _pfx() + '%s:%s' % (fn, code)
    assert calls == []
    _start_import(builtins, hook)
    sys.settrace(tracer)
    try:
        _ok_calls()
        m.imap_is_valid('number', b'x')
    finally:
        sys.settrace(prev)
        _stop_import()
    assert calls == []
    assert want <= reached, sorted(want - reached)
    assert returns <= reached, sorted(returns - reached)


def test_import_log_pin_no_import_during_any_function_call():
    real = builtins.__import__
    calls = []

    def hook(*a, **k):
        calls.append(a[:1])
        return real(*a, **k)

    _start_import(builtins, hook)
    try:
        _ok_calls()
        for fn, code, args in _site_cases():
            with pytest.raises(ValueError):
                getattr(m, fn)(*args)
    finally:
        _stop_import()
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
    assert ns['imap_parse']('atom', b'abc') == ('atom', b'abc')
    assert ns['imap_format']('number', 5) == b'5'


def test_fallback_handler_binds_iu_not_importlib():
    ns, _seen, _fc = _exec_guarded(import_exc=_mnfe(REG), spec_result=None)
    assert '_iu' in ns and 'importlib' not in ns
    assert ns['_iu'] is iu
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
    _start_import(builtins, fake_import)
    iu.find_spec = fake_find
    try:
        exec(compile(src, str(path), 'exec'), ns)
    finally:
        assert builtins.__import__ == fake_import, '__import__ clobbered mid-probe'
        assert iu.find_spec is fake_find, 'find_spec clobbered mid-probe'
        _stop_import()
        iu.find_spec = real_find
        sys.modules.pop(REG, None)
        if saved is not _MISSING:
            sys.modules[REG] = saved
    assert builtins.__import__ == real_import and iu.find_spec is real_find
    return ns, seen, full_calls


def _mnfe(name, msg='no such module'):
    e = ModuleNotFoundError(msg)
    e.name = name
    return e


def test_guard_absent_registry_falls_back_via_find_spec():
    ns, seen, fc = _exec_guarded(import_exc=_mnfe(REG), spec_result=None)
    assert seen == [REG] and fc == [((REG,), {})]
    with pytest.raises(ValueError) as e:
        ns['imap_parse'](None, b'')
    assert str(e.value) == 'P235:imap_parse:bad_type:rule'


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
        ns['imap_parse'](None, b'')
    assert str(e.value) == 'custom:imap_parse:bad_type:rule' and calls == ['imap_parse']


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
    _start_import(builtins, hook)
    try:
        try:
            exec(compile(src, str(path), 'exec'), ns)
            err = None
        except ModuleNotFoundError as e:
            err = e
    finally:
        assert builtins.__import__ == hook, '__import__ clobbered mid-probe'
        _stop_import()
        sys.modules.pop(REG, None)
        if saved is not absent:
            sys.modules[REG] = saved
    assert builtins.__import__ == real_import
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
        assert mod.imap_parse('atom', b'a') == ('atom', b'a')
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
    assert builtins.__import__ == real and iu.find_spec is find
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
    _start_import(builtins, fake_import)
    iu.find_spec = spy
    try:
        try:
            exec(compile(path.read_text(), str(path), 'exec'), ns)
        except BaseException as e:
            raised = e
    finally:
        _stop_import()
        iu.find_spec = real_find
        sys.modules.pop(REG, None)
        if saved is not _MISSING:
            sys.modules[REG] = saved
    assert builtins.__import__ == real_import and iu.find_spec is real_find
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




# ---------- docstring pins ----------

_DOC_QUOTES = (
    'atom = 1*ATOM-CHAR',
    'ATOM-CHAR = <any CHAR except atom-specials>',
    'atom-specials = "(" / ")" / "{" / SP / CTL / list-wildcards / quoted-specials / resp-specials',
    'list-wildcards = "%" / "*"',
    'resp-specials = "]"',
    'astring = 1*ASTRING-CHAR / string',
    'ASTRING-CHAR = ATOM-CHAR / resp-specials',
    'tag = 1*<any ASTRING-CHAR except "+">',
    'literal = "{" number "}" CRLF *CHAR8',
    'CHAR8 = %x01-ff',
    'quoted = DQUOTE *QUOTED-CHAR DQUOTE',
    'QUOTED-CHAR = <any TEXT-CHAR except quoted-specials> / "\\" quoted-specials',
    'quoted-specials = DQUOTE / "\\"',
    'TEXT-CHAR = <any CHAR except CR and LF>',
    'string = quoted / literal',
    'nstring = string / nil',
    'nil = "NIL"',
    'number = 1*DIGIT',
    '(0 <= n < 4,294,967,296)',
    'nz-number = digit-nz *DIGIT',
    'digit-nz = %x31-39',
    'The ASCII NUL character, %x00, MUST NOT be used at any time.',
    'Implementations MUST accept these strings in a case-insensitive fashion.',
    'The empty string is represented as either "" (a quoted string with zero characters between double quotes) or as {0} followed by CRLF (a literal with an octet count of 0)',
)


@pytest.mark.parametrize('q', _DOC_QUOTES)
def test_docstring_quote_present(q):
    assert q in ' '.join(m.__doc__.split())


_DOC_FULL = (
    'P235 b1184 bounded exact IMAP4rev1 string syntax: atom, number, quoted, literal and the '
    'rules built on them. Pure functions on bytes, no clock, no network, no IMAP library: ima'
    'p_parse, imap_is_valid and imap_format. Primary source (fetched fresh and read live 2026'
    '-10-21): RFC 3501 INTERNET MESSAGE ACCESS PROTOCOL - VERSION 4rev1, https://www.rfc-edit'
    'or.org/rfc/rfc3501.txt, Section 4 (Data Formats, 4.1 to 4.3) and Section 9 (Formal Synta'
    "x). Quotes: 'atom = 1*ATOM-CHAR' 'ATOM-CHAR = <any CHAR except atom-specials>' 'atom-spe"
    'cials = "(" / ")" / "{" / SP / CTL / list-wildcards / quoted-specials / resp-specials\' \''
    'list-wildcards = "%" / "*"\' \'resp-specials = "]"\' \'astring = 1*ASTRING-CHAR / string\' \'A'
    'STRING-CHAR = ATOM-CHAR / resp-specials\' \'tag = 1*<any ASTRING-CHAR except "+">\' \'litera'
    'l = "{" number "}" CRLF *CHAR8\' \'CHAR8 = %x01-ff\' \'quoted = DQUOTE *QUOTED-CHAR DQUOTE\' '
    '\'QUOTED-CHAR = <any TEXT-CHAR except quoted-specials> / "\\" quoted-specials\' \'quoted-spe'
    'cials = DQUOTE / "\\"\' \'TEXT-CHAR = <any CHAR except CR and LF>\' \'string = quoted / liter'
    'al\' \'nstring = string / nil\' \'nil = "NIL"\' \'number = 1*DIGIT\' \'(0 <= n < 4,294,967,296)\''
    " 'nz-number = digit-nz *DIGIT' 'digit-nz = %x31-39' 'The ASCII NUL character, %x00, MUST"
    " NOT be used at any time.' 'Implementations MUST accept these strings in a case-insensit"
    'ive fashion.\' \'The empty string is represented as either "" (a quoted string with zero c'
    'haracters between double quotes) or as {0} followed by CRLF (a literal with an octet cou'
    "nt of 0).' Errata (read live 2026-10-21, from the full index https://www.rfc-editor.org/"
    'errata.json): RFC 3501, https://www.rfc-editor.org/errata/rfc3501, seven records, none a'
    'pplied and none touches the syntax of this unit. EID 261 (Verified, no section) is about'
    ' the UID wording of Section 2.3.1.1. EID 3032 (Verified, Technical, 6.3.1) and EID 3445 '
    '(Rejected, Technical, 6.3.1) are about the UNSEEN and UIDNEXT responses to SELECT. EID 3'
    '093 (Held for Document Update, Editorial, 6.3.11) is about must and may wording. EID 616'
    '0 (Held for Document Update, Editorial, Page 89) is a wording fix in the search rule. EI'
    'D 6636 (Rejected, Technical, GLOBAL) is the RFC 2822 versus RFC 5322 reference. EID 6637'
    ' (Held for Document Update, Technical, 9) says the envelope rule lacks env-references; t'
    'his unit does not parse an envelope. CONVENTIONS (OURS, UNSOURCED where stated). Input a'
    'nd output are exact bytes, never str, bytearray or a bytes subclass. CHAR is read as %x0'
    '1-7F, CTL as %x01-1F and %x7F, SP as %x20, DQUOTE as %x22 and CR, LF as %x0D, %x0A (the '
    'RFC 2234 definitions were not read, so this is OURS); the NUL byte %x00 is never accepte'
    'd, as Section 9 says. An atom character is therefore one of %x21-7E except ( ) { % * " \\'
    ' and ]; an astring character is an atom character or ]; a tag is astring characters othe'
    'r than +. Parsing takes one whole value and nothing else: leading or trailing bytes, inc'
    'luding a space or CRLF after a quoted string, are refused. A quoted string is DQUOTE, th'
    'en characters of %x01-7F except CR, LF, DQUOTE and backslash, or a backslash followed by'
    ' DQUOTE or backslash, then DQUOTE, and imap_parse returns the unescaped bytes. A literal'
    ' is { digits } CRLF and exactly that many octets of %x01-FF; the octet data must be whol'
    'ly present, a non-synchronizing {n+} form is refused (it is not in RFC 3501), and a lite'
    'ral count follows the number rule. A number is one or more ASCII digits, leading zeros a'
    'llowed as the ABNF says, at most 4294967295, and nz-number refuses 0 and any leading zer'
    'o (digit-nz first); the value is built by digit arithmetic, never by the int builtin on '
    'input. nil is NIL in any letter case and is accepted only by nstring, where it returns t'
    'he kind nil and the value None; as an astring the text NIL is an atom. The rules are ato'
    'm, number, nz-number, quoted, literal, string, astring, nstring and tag. imap_parse(rule'
    ', data) returns a pair (kind, value): kind atom, quoted, literal, number, nil or tag, an'
    'd the value is bytes, an int or None. For string, astring and nstring a first byte of DQ'
    'UOTE selects quoted and { selects literal; astring otherwise reads an atom, nstring othe'
    'rwise reads NIL. The input is at most 4096 bytes (MAX_DATA); a number, atom or tag is re'
    'ad as-is. imap_is_valid(rule, data) returns exactly True or False and refuses only a wro'
    'ng type or an unknown rule. imap_format(rule, value) takes bytes of at most 2000 (MAX_VA'
    'LUE), an exact int for number and nz-number (bool refused) and bytes or None for nstring'
    '. atom and tag refuse a value that is not one; quoted refuses NUL, CR, LF and bytes abov'
    'e 127; literal refuses NUL; string writes quoted when every byte fits and a literal othe'
    'rwise; astring writes the bare atom when it is a valid astring, else as string; nstring '
    'writes NIL for None. Numbers are written in decimal with no leading zeros. Every output '
    'parses back to the same value under the same rule, so format output is always within the'
    ' parse cap. Errors are ValueError with message P235:<function>:<code>. imap_parse: bad_t'
    'ype:rule, bad_type:data, bad_value:rule, bad_value:data.length, then by rule bad_value:a'
    'tom, bad_value:number, bad_value:quoted.syntax, quoted.char, bad_value:literal.syntax, l'
    'iteral.count, literal.length, literal.char, bad_value:string.syntax and bad_value:nstrin'
    'g.syntax. imap_is_valid: bad_type:rule, bad_type:data and bad_value:rule only. imap_form'
    'at: bad_type:rule, bad_value:rule, bad_type:value, bad_value:number, bad_value:value.len'
    'gth, then bad_value:atom, quoted.char or literal.char. ADJACENCY, by name only: RFC 2234'
    ' and RFC 5234 ABNF, RFC 7888 LITERAL+, RFC 3501 commands and responses outside Section 4'
    ' and 9 strings, RFC 2152 and the modified UTF-7 mailbox names of Section 5.1.3 belong to'
    ' other units and were not read beyond the sections named above. SCOPE and NOT_CLAIMED ar'
    'e the module constants below.'
)


def test_docstring_whole_exact():
    assert ' '.join(m.__doc__.split()) == _DOC_FULL
    assert m.__doc__.startswith('P235 b1184')


def test_scope_and_constants_exact():
    assert m.SCOPE == 'PARTIAL: RFC 3501 Section 4 and 9 atom, number, quoted, literal, string, astring, nstring and tag syntax on whole bytes values, parse and format, pure functions, with the OURS choices stated in the docstring'
    assert m.NOT_CLAIMED == ('commands, responses, flags, sequence sets or any other Section 9 rule', 'mailbox name encoding, modified UTF-7 or INBOX handling', 'the non-synchronizing literal form, literal continuation or streaming', 'the RFC 2234 definitions of CHAR and CTL, which were not read', 'global novelty', 'production readiness')
    assert m.ADJACENT == ('RFC 5234 ABNF, RFC 7888 LITERAL+, the rest of RFC 3501 Section 9 and Section 5.1.3 mailbox names are covered by other units and were not read beyond the sections named in the docstring',)
    assert m.CLAIMS is False
    assert m.MAX_DATA == 4096
    assert m.MAX_VALUE == 2000
    assert m.MAX_NUMBER == 4294967295
    assert type(m.NOT_CLAIMED) is tuple and type(m.ADJACENT) is tuple and type(m.SCOPE) is str
