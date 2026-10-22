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
        from app.modules.instinct_doc import p235_concepts_batch1213_abnf as mod
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
        m.rulelist_parse(None)
    tail = 'rulelist_parse:bad_type:data'
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





TP = 'rulelist_parse'
TV = 'rulelist_is_valid'

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



# ================= behavioral pins: exact trees, codes, order =================
TP = 'rulelist_parse'
TV = 'rulelist_is_valid'

GOOD = (
    b'x = y\r\n', b'a=/b\r\n', b'x = 1*2(a / b) [c %x30-39]\r\n; comment\r\n', b'\r\n \t\r\n', b';hi\r\n',
    b'x = y\r\n z / 2*w\r\n', b'x = y ;c\r\n more\r\n', b'x\r\n = y\r\n', b'x\t=\ty\r\n',
    b'x = %s"Ab" / %i"cD" / "eF" / %S"g" / %I"h"\r\n',
    b'x = %b101 / %d65.66 / %x30-39 / %X41 / %B1 / %D2 / %d99999999999999999999\r\n',
    b'x = <a <b> / <>\r\n', b'x = 3y / 2*z / *5w / *v / 12*34q\r\n', b'x = (a (b (c))) / [[d]]\r\n',
    b'a-b1 = %x41\r\n', b'x = ""\r\n', b'x = y ;trail\r\n', b'x = a/b\r\n', b'x = y\r\n\r\nz = w\r\n',
    b'x = a 2b\r\n', b'x = a *2b\r\n', b'x = y \r\n', b'x = (a\r\n / b)\r\n', b'x = %b1.0.1\r\n',
    b'x = "a" "b"\r\n', b'x = y <note>\r\n', b'x = %xAB\r\n', b'x = %d1/y\r\n', b'x = %d1.2/y\r\n',
    b'x = (a )\r\n', b'x = [a ]\r\n',
    b'a = b A\r\n', b'a = b z\r\n', b'a = b 0c\r\n', b'a = b 9c\r\n', b'xA = b\r\n', b'a0 = b\r\n',
    b'xz = b\r\n', b'x9 = b\r\n', b'A = b\r\n', b'z = b\r\n', b'x = A\r\n', b'x = z\r\n', b'x = 0y\r\n',
    b'x = 9y\r\n', b'x = 10y\r\n', b'x = 19y\r\n', b'x = 1*0y\r\n', b'x = *0y\r\n', b'x = *9y\r\n',
    b'x = %b0\r\n', b'x = <~>\r\n', b'x = *19y\r\n',
    b'x = y\r\n ; Z\r\n', b'x- = y\r\n', b'x = y \t;c\r\n', b'x = (a / b) (c)\r\n', b'x = "a" / "b"\r\n',
)

BAD = (
    b'', b'1x = y\r\n', b'-x\r\n', b' x = y\r\n', b' ;c\r\n x = y\r\n', b'x y\r\n', b'x\r\n', b'x',
    b'x =\r\n', b'x = ()\r\n', b'x = a/\r\n', b'x = 3 \r\n', b'x = 3;y\r\n', b'x = a / / b\r\n',
    b'x = %\r\n', b'x = %b\r\n', b'x = %b2\r\n', b'x = %d1.\r\n', b'x = %d1..\r\n', b'x = %x1-\r\n',
    b'x = %q1\r\n', b'x = %s1\r\n', b'x = %s\r\n', b'x = %i x\r\n', b'x = "abc\r\n', b'x = "a\tb"\r\n',
    b'x = %i"\r\n', b'x = <abc\r\n', b'x = <a\tb>\r\n', b'x = (a\r\n', b'x = [a\r\n', b'x = (a]\r\n',
    b'x = [a)\r\n', b'x = y', b'x = y ;c', b'x = y}', b'x = y >', b'x\ry\r\n', b'x\ny', b'x = y\r',
    b'\x7f\r\n', b'x = \x80\r\n', b'x==y\r\n', b'x = <a>b>\r\n', b'x = 2  y\r\n',
)


def test_good_bad_lists_agree_with_is_valid():
    for t in GOOD:
        assert m.rulelist_is_valid(t) is True
    for t in BAD:
        assert m.rulelist_is_valid(t) is False


def test_exact_trees_simple_forms():
    assert m.rulelist_parse(b'x = y\r\n') == ((b'x', False, ('name', b'y')),)
    assert m.rulelist_parse(b'a=/b\r\n') == ((b'a', True, ('name', b'b')),)
    assert m.rulelist_parse(b'x = a/b\r\n') == ((b'x', False, ('alt', (('name', b'a'), ('name', b'b')))),)
    assert m.rulelist_parse(b'x = y z\r\n') == ((b'x', False, ('cat', (('name', b'y'), ('name', b'z')))),)
    assert m.rulelist_parse(b'x = (y)\r\n') == ((b'x', False, ('grp', ('name', b'y'))),)
    assert m.rulelist_parse(b'x = [y]\r\n') == ((b'x', False, ('opt', ('name', b'y'))),)
    assert m.rulelist_parse(b'Foo-Bar1 = "aBc"\r\n') == ((b'Foo-Bar1', False, ('str', 'i', b'aBc')),)
    assert m.rulelist_parse(b'x- = y\r\n') == ((b'x-', False, ('name', b'y')),)


def test_exact_trees_compound():
    assert m.rulelist_parse(b'x = 1*2(a / b) [c %x30-39]\r\n; comment\r\n') == (
        (b'x', False, ('cat', (('rep', 1, 2, ('grp', ('alt', (('name', b'a'), ('name', b'b'))))),
                              ('opt', ('cat', (('name', b'c'), ('num', 'x', ('range', 48, 57)))))))),)
    assert m.rulelist_parse(b'x = y\r\n z / 2*w\r\n') == (
        (b'x', False, ('alt', (('cat', (('name', b'y'), ('name', b'z'))), ('rep', 2, None, ('name', b'w'))))),)
    assert m.rulelist_parse(b'x = y ;c\r\n more\r\n') == (
        (b'x', False, ('cat', (('name', b'y'), ('name', b'more')))),)
    assert m.rulelist_parse(b'x = (a\r\n / b)\r\n') == (
        (b'x', False, ('grp', ('alt', (('name', b'a'), ('name', b'b'))))),)
    assert m.rulelist_parse(b'x\r\n = y\r\n') == ((b'x', False, ('name', b'y')),)
    assert m.rulelist_parse(b'x = (a / b) (c)\r\n') == (
        (b'x', False, ('cat', (('grp', ('alt', (('name', b'a'), ('name', b'b')))), ('grp', ('name', b'c'))))),)


def test_exact_trees_repetition_forms():
    assert m.rulelist_parse(b'r = 3y\r\n') == ((b'r', False, ('rep', 3, 3, ('name', b'y'))),)
    assert m.rulelist_parse(b'r = 2*z\r\n') == ((b'r', False, ('rep', 2, None, ('name', b'z'))),)
    assert m.rulelist_parse(b'r = *5w\r\n') == ((b'r', False, ('rep', 0, 5, ('name', b'w'))),)
    assert m.rulelist_parse(b'r = *v\r\n') == ((b'r', False, ('rep', 0, None, ('name', b'v'))),)
    assert m.rulelist_parse(b'r = 12*34q\r\n') == ((b'r', False, ('rep', 12, 34, ('name', b'q'))),)
    assert m.rulelist_parse(b'r = 12345q\r\n') == ((b'r', False, ('rep', 12345, 12345, ('name', b'q'))),)


def test_exact_trees_strings_and_case_preserved():
    assert m.rulelist_parse(b'x = %s"AbC" / %i"d" / "e"\r\n') == (
        (b'x', False, ('alt', (('str', 's', b'AbC'), ('str', 'i', b'd'), ('str', 'i', b'e')))),)
    assert m.rulelist_parse(b'x = %S"q" / %I"r"\r\n') == (
        (b'x', False, ('alt', (('str', 's', b'q'), ('str', 'i', b'r')))),)
    assert m.rulelist_parse(b'x = ""\r\n') == ((b'x', False, ('str', 'i', b'')),)
    body = b' !#$%&\'()*+,-./0123456789:;<=>?@AZ[\\]^_`az{|}~'
    assert m.rulelist_parse(b'x = "' + body + b'"\r\n') == ((b'x', False, ('str', 'i', body)),)


def test_exact_trees_numval():
    assert m.rulelist_parse(b'x = %d13.10.65\r\n') == ((b'x', False, ('num', 'd', ('seq', (13, 10, 65)))),)
    assert m.rulelist_parse(b'x = %b1.0.1\r\n') == ((b'x', False, ('num', 'b', ('seq', (1, 0, 1)))),)
    assert m.rulelist_parse(b'x = %x41\r\n') == ((b'x', False, ('num', 'x', ('seq', (65,)))),)
    assert m.rulelist_parse(b'x = %X41\r\n') == ((b'x', False, ('num', 'x', ('seq', (65,)))),)
    assert m.rulelist_parse(b'x = %B101\r\n') == ((b'x', False, ('num', 'b', ('seq', (5,)))),)
    assert m.rulelist_parse(b'x = %D65\r\n') == ((b'x', False, ('num', 'd', ('seq', (65,)))),)
    assert m.rulelist_parse(b'x = %x30-39\r\n') == ((b'x', False, ('num', 'x', ('range', 48, 57))),)
    assert m.rulelist_parse(b'x = %x30-20\r\n') == ((b'x', False, ('num', 'x', ('range', 48, 32))),)
    assert m.rulelist_parse(b'x = %d0\r\n') == ((b'x', False, ('num', 'd', ('seq', (0,)))),)
    assert m.rulelist_parse(b'x = %x0-0\r\n') == ((b'x', False, ('num', 'x', ('range', 0, 0))),)
    assert m.rulelist_parse(b'x = %d99999999999999999999\r\n') == (
        (b'x', False, ('num', 'd', ('seq', (99999999999999999999,)))),)
    assert m.rulelist_parse(b'x = %xffFF\r\n') == ((b'x', False, ('num', 'x', ('seq', (65535,)))),)


def test_exact_trees_prose():
    assert m.rulelist_parse(b'x=<a <b>\r\n') == ((b'x', False, ('prose', b'a <b')),)
    assert m.rulelist_parse(b'x = <>\r\n') == ((b'x', False, ('prose', b'')),)
    assert m.rulelist_parse(b'x = <why not>\r\n') == ((b'x', False, ('prose', b'why not')),)


def test_exact_trees_sweep_pins():
    # pins added after the mutation sweeps: each kills a logged survivor (see delivery notes)
    assert m.rulelist_parse(b'x = "a" "b"\r\n') == ((b'x', False, ('cat', (('str', 'i', b'a'), ('str', 'i', b'b')))),)
    assert m.rulelist_parse(b'x = y <note>\r\n') == ((b'x', False, ('cat', (('name', b'y'), ('prose', b'note')))),)
    assert m.rulelist_parse(b'x = %xAB\r\n') == ((b'x', False, ('num', 'x', ('seq', (171,)))),)
    assert m.rulelist_parse(b'x = %d1/y\r\n') == ((b'x', False, ('alt', (('num', 'd', ('seq', (1,))), ('name', b'y')))),)
    assert m.rulelist_parse(b'x = %d1.2/y\r\n') == ((b'x', False, ('alt', (('num', 'd', ('seq', (1, 2))), ('name', b'y')))),)
    assert m.rulelist_parse(b'x = (a )\r\n') == ((b'x', False, ('grp', ('name', b'a'))),)
    assert m.rulelist_parse(b'x = [a ]\r\n') == ((b'x', False, ('opt', ('name', b'a'))),)


def test_exact_trees_first_and_last_class_members():
    # A40 interim: find() >= 0 vs >= 1 is observable at index 0 (first class member); pin first AND last
    # member of every find()-based class at every class site: _estart, _rulename tail, _element, _parse,
    # repetition counts, numval digit sets.
    assert m.rulelist_parse(b'a = b A\r\n') == ((b'a', False, ('cat', (('name', b'b'), ('name', b'A')))),)
    assert m.rulelist_parse(b'a = b z\r\n') == ((b'a', False, ('cat', (('name', b'b'), ('name', b'z')))),)
    assert m.rulelist_parse(b'a = b 0c\r\n') == ((b'a', False, ('cat', (('name', b'b'), ('rep', 0, 0, ('name', b'c'))))),)
    assert m.rulelist_parse(b'a = b 9c\r\n') == ((b'a', False, ('cat', (('name', b'b'), ('rep', 9, 9, ('name', b'c'))))),)
    assert m.rulelist_parse(b'xA = b\r\n') == ((b'xA', False, ('name', b'b')),)
    assert m.rulelist_parse(b'a0 = b\r\n') == ((b'a0', False, ('name', b'b')),)
    assert m.rulelist_parse(b'xz = b\r\n') == ((b'xz', False, ('name', b'b')),)
    assert m.rulelist_parse(b'x9 = b\r\n') == ((b'x9', False, ('name', b'b')),)
    assert m.rulelist_parse(b'A = b\r\n') == ((b'A', False, ('name', b'b')),)
    assert m.rulelist_parse(b'z = b\r\n') == ((b'z', False, ('name', b'b')),)
    assert m.rulelist_parse(b'x = A\r\n') == ((b'x', False, ('name', b'A')),)
    assert m.rulelist_parse(b'x = z\r\n') == ((b'x', False, ('name', b'z')),)
    assert m.rulelist_parse(b'x = 0y\r\n') == ((b'x', False, ('rep', 0, 0, ('name', b'y'))),)
    assert m.rulelist_parse(b'x = 9y\r\n') == ((b'x', False, ('rep', 9, 9, ('name', b'y'))),)
    assert m.rulelist_parse(b'x = 10y\r\n') == ((b'x', False, ('rep', 10, 10, ('name', b'y'))),)
    assert m.rulelist_parse(b'x = 19y\r\n') == ((b'x', False, ('rep', 19, 19, ('name', b'y'))),)
    assert m.rulelist_parse(b'x = 1*0y\r\n') == ((b'x', False, ('rep', 1, 0, ('name', b'y'))),)
    assert m.rulelist_parse(b'x = *0y\r\n') == ((b'x', False, ('rep', 0, 0, ('name', b'y'))),)
    assert m.rulelist_parse(b'x = *9y\r\n') == ((b'x', False, ('rep', 0, 9, ('name', b'y'))),)
    assert m.rulelist_parse(b'x = %b0\r\n') == ((b'x', False, ('num', 'b', ('seq', (0,)))),)
    assert m.rulelist_parse(b'x = <~>\r\n') == ((b'x', False, ('prose', b'~')),)
    assert m.rulelist_parse(b'x = *19y\r\n') == ((b'x', False, ('rep', 0, 19, ('name', b'y'))),)


def test_exact_trees_a40_final_pins():
    # A40 final audit: multi-digit hi run (while->if single iteration), base-10 multi-digit hi
    # (10->9 / 10->11), and 3-element concatenation (while True->for-once). Verified against the module.
    assert m.rulelist_parse(b'x = *33y\r\n') == ((b'x', False, ('rep', 0, 33, ('name', b'y'))),)
    assert m.rulelist_parse(b'x = *10y\r\n') == ((b'x', False, ('rep', 0, 10, ('name', b'y'))),)
    assert m.rulelist_parse(b'a = b c d\r\n') == ((b'a', False, ('cat', (('name', b'b'), ('name', b'c'), ('name', b'd')))),)


def test_a43_final_pins():
    # A43 final audit: num-val seq-then-'-' elif->if must not truncate a seq into a range;
    # concatenation not-estart break must restore i=save (not j) so the refusal code is exact.
    refuse(TP, 'bad_value:crlf', b'a = %x30.31-32\r\n')
    refuse(TP, 'bad_value:crlf', b'a = %b1.0-1\r\n')
    refuse(TP, 'bad_value:rulename', b'a\r\n =\r\n\t%s""\r\n -\r\n')


def test_a45_final_pins():
    # A45 final audit: leading *c-wsp after "(" and "[" must be skipped (WSP, tab,
    # comment-with-CRLF continuation, and nested depth). Trees verified against the module.
    assert m.rulelist_parse(b'x = ( a)\r\n') == ((b'x', False, ('grp', ('name', b'a'))),)
    assert m.rulelist_parse(b'x = [ a]\r\n') == ((b'x', False, ('opt', ('name', b'a'))),)
    assert m.rulelist_parse(b'x = ( ;c\r\n a)\r\n') == ((b'x', False, ('grp', ('name', b'a'))),)
    assert m.rulelist_parse(b'x = (\ta)\r\n') == ((b'x', False, ('grp', ('name', b'a'))),)
    assert m.rulelist_parse(b'x = (( a))\r\n') == ((b'x', False, ('grp', ('grp', ('name', b'a')))),)


def test_errata_pins():
    # EID 2968: trailing WSP after elements is plain WSP; the comment line after is a rulelist item
    assert m.rulelist_parse(b'X = Y\r\n ; Z\r\n') == ((b'X', False, ('name', b'Y')),)
    assert m.rulelist_parse(b'x = y \t;c\r\n') == ((b'x', False, ('name', b'y')),)
    # EID 3076: blank or comment lines between rules are WSP then c-nl; comment-only input is a valid rulelist
    assert m.rulelist_parse(b';a\r\n;b\r\n') == ()
    assert m.rulelist_parse(b' ; Z\r\n') == ()
    assert m.rulelist_parse(b'\r\n \t\r\n') == ()
    # EID 2820: the printed prose-val range stands; '<' (%x3C) is allowed inside, only '>' is excluded
    assert m.rulelist_parse(b'x = <a <b>\r\n') == ((b'x', False, ('prose', b'a <b')),)
    refuse(TP, 'bad_value:crlf', b'x = <a>b>\r\n')


def test_refusal_codes_exact():
    refuse(TP, 'bad_value:rulelist', b'')
    refuse(TP, 'bad_value:rulename', b'1x = y\r\n')
    refuse(TP, 'bad_value:rulename', b'-x\r\n')
    refuse(TP, 'bad_value:rulename', b' x = y\r\n')
    refuse(TP, 'bad_value:rulename', b' ;c\r\n x = y\r\n')
    refuse(TP, 'bad_value:rulename', b')x = y\r\n')
    refuse(TP, 'bad_value:defined_as', b'x y\r\n')
    refuse(TP, 'bad_value:defined_as', b'x\r\n')
    refuse(TP, 'bad_value:defined_as', b'x')
    refuse(TP, 'bad_value:defined_as', b'x +\r\n')
    refuse(TP, 'bad_value:element', b'x =\r\n')
    refuse(TP, 'bad_value:element', b'x = ()\r\n')
    refuse(TP, 'bad_value:element', b'x = a/\r\n')
    refuse(TP, 'bad_value:element', b'x = 3 \r\n')
    refuse(TP, 'bad_value:element', b'x = 3;y\r\n')
    refuse(TP, 'bad_value:element', b'x = a / / b\r\n')
    refuse(TP, 'bad_value:element', b'x==y\r\n')
    refuse(TP, 'bad_value:element', b'x = 2  y\r\n')
    refuse(TP, 'bad_value:numval', b'x = %\r\n')
    refuse(TP, 'bad_value:numval', b'x = %b\r\n')
    refuse(TP, 'bad_value:numval', b'x = %b2\r\n')
    refuse(TP, 'bad_value:numval', b'x = %d1.\r\n')
    refuse(TP, 'bad_value:numval', b'x = %d1..\r\n')
    refuse(TP, 'bad_value:numval', b'x = %x1-\r\n')
    refuse(TP, 'bad_value:numval', b'x = %q1\r\n')
    refuse(TP, 'bad_value:charval', b'x = %s1\r\n')
    refuse(TP, 'bad_value:charval', b'x = %s\r\n')
    refuse(TP, 'bad_value:charval', b'x = %i x\r\n')
    refuse(TP, 'bad_value:charval', b'x = "abc\r\n')
    refuse(TP, 'bad_value:charval', b'x = "a\tb"\r\n')
    refuse(TP, 'bad_value:charval', b'x = %i"\r\n')
    refuse(TP, 'bad_value:proseval', b'x = <abc\r\n')
    refuse(TP, 'bad_value:proseval', b'x = <a\tb>\r\n')
    refuse(TP, 'bad_value:group', b'x = (a\r\n')
    refuse(TP, 'bad_value:group', b'x = (a]\r\n')
    refuse(TP, 'bad_value:option', b'x = [a\r\n')
    refuse(TP, 'bad_value:option', b'x = [a)\r\n')
    refuse(TP, 'bad_value:crlf', b'x = y')
    refuse(TP, 'bad_value:crlf', b'x = y ;c')
    refuse(TP, 'bad_value:crlf', b'x = y}')
    refuse(TP, 'bad_value:crlf', b'x = y >')
    refuse(TP, 'bad_value:nl', b'x\ry\r\n')
    refuse(TP, 'bad_value:nl', b'x\ny')
    refuse(TP, 'bad_value:nl', b'x = y\r')
    refuse(TP, 'bad_value:char', b'\x7f\r\n')
    refuse(TP, 'bad_value:char', b'x = \x80\r\n')
    refuse(TP, 'bad_value:char', b'\x1f\r\n')
    refuse(TP, 'bad_value:numval', b'x = %a1\r\n')
    refuse(TP, 'bad_value:numval', b'x = %A1\r\n')
    refuse(TP, 'bad_value:numval', b'x = %C1\r\n')
    refuse(TP, 'bad_value:numval', b'x = %W1\r\n')
    refuse(TP, 'bad_value:numval', b'x = %c1\r\n')
    refuse(TP, 'bad_value:numval', b'x = %w1\r\n')
    refuse(TP, 'bad_value:numval', b'x = %y1\r\n')
    refuse(TP, 'bad_value:charval', b'x = %s1"\r\n')
    refuse(TP, 'bad_value:charval', b'x = %i1"\r\n')
    refuse(TP, 'bad_value:option', b'x = [a~\r\n')
    refuse(TP, 'bad_value:crlf', b'x = a"b"\r\n')
    refuse(TP, 'bad_value:crlf', b'x = %d1')
    refuse(TP, 'bad_value:crlf', b'x = %d1.2')
    refuse(TP, 'bad_value:crlf', b'x = %d1-2')


def test_check_order_whole_scan_then_structure():
    # the whole-input byte and newline scan runs before any structural check
    refuse(TP, 'bad_value:char', b'= x\r\n\x80')
    refuse(TP, 'bad_value:char', b'\x7f\r')
    refuse(TP, 'bad_value:nl', b'\r\x7f')
    refuse(TP, 'bad_value:nl', b'1\r')
    refuse(TP, 'bad_value:data.length', b'\xff' * 5000)


def test_caps_exact_boundaries_both_sides():
    t = b'x = y\r\n' + b' ' * (4096 - len(b'x = y\r\n') - 2) + b'\r\n'
    assert len(t) == 4096
    assert m.rulelist_is_valid(t) is True
    refuse(TP, 'bad_value:data.length', t + b' ')
    deep_ok = b'x = ' + b'(' * 64 + b'a' + b')' * 64 + b'\r\n'
    assert m.rulelist_is_valid(deep_ok) is True
    deep_no = b'x = ' + b'(' * 65 + b'a' + b')' * 65 + b'\r\n'
    refuse(TP, 'bad_value:depth', deep_no)
    assert m.rulelist_is_valid(deep_no) is False
    deep_opt_ok = b'x = ' + b'[' * 64 + b'a' + b']' * 64 + b'\r\n'
    assert m.rulelist_is_valid(deep_opt_ok) is True
    deep_opt_no = b'x = ' + b'[' * 65 + b'a' + b']' * 65 + b'\r\n'
    refuse(TP, 'bad_value:depth', deep_opt_no)
    assert m.rulelist_is_valid(deep_opt_no) is False


def test_is_valid_exact_types_and_no_raise_but_type():
    assert m.rulelist_is_valid(b'x = y\r\n') is True
    assert m.rulelist_is_valid(b'x y\r\n') is False
    assert type(m.rulelist_is_valid(b'')) is bool
    refuse(TV, 'bad_type:data', None)
    refuse(TV, 'bad_type:data', bytearray(b'x = y\r\n'))
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

    def __eq__(self, o):
        _Spy.calls.append('bytes_eq')
        return True

    __hash__ = bytes.__hash__


def _bad_data():
    return [None, 1, 1.5, True, '{x}', bytearray(b'{x}'), [b'{x}'], (b'{x}',), {b'{x}': 1}, object(), _Liar(),
            _StrSub('x'), _IntSub(1), memoryview(b'{x}'), _BytesSub(b'{x}'), 1j, bytes, type]


def test_every_site_refuses_every_non_exact_input_type_and_makes_no_dunder_call():
    for fn in (TP, TV):
        for bad in _bad_data():
            _Spy.calls.clear()
            refuse(fn, 'bad_type:data', bad)
            assert _Spy.calls == [], (fn, bad)


def test_check_order_type_then_length():
    for fn in (TP, TV):
        refuse(fn, 'bad_type:data', 5)
        refuse(fn, 'bad_type:data', 'a' * 5000)
    refuse(TP, 'bad_value:data.length', b'\xff' * 5000)
    refuse(TP, 'bad_value:data.length', b'a' * 4097)
    assert m.rulelist_is_valid(b'x' * 4097) is False


def test_data_is_never_decoded_or_converted():
    for bad in (bytearray(b'{x}'), memoryview(b'{x}'), '{x}', _BytesSub(b'{x}')):
        with pytest.raises(ValueError):
            m.rulelist_parse(bad)
        with pytest.raises(ValueError):
            m.rulelist_is_valid(bad)


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
    for big in (b'a' * 3000000, b'{' * 3000000, b'%' * 3000000, b'\xff' * 3000000, b'\xc3' * 3000000):
        assert _peak_refusal(TP, 'bad_value:data.length', big) < bound
        def call(big=big):
            with pytest.raises(ValueError):
                m.rulelist_parse(big)
        assert _trace(call) < 20
        def call2(big=big):
            assert m.rulelist_is_valid(big) is False
        assert _trace(call2) < 20
    assert _peak_refusal(TP, 'bad_type:data', 'a' * 3000000) < bound
    assert _peak_refusal(TV, 'bad_type:data', 'a' * 3000000) < bound
    # a refusal inside the cap does bounded work
    def inside():
        with pytest.raises(ValueError):
            m.rulelist_parse(b'a' * 1000 + b' ')
    assert _trace(inside) < 20000
    def inside2():
        assert m.rulelist_is_valid(b'x = ' + b'(' * 2000 + b'a' + b')' * 2000 + b'\r\n') is False
    assert _trace(inside2) < 60000
    def inside3():
        assert m.rulelist_is_valid(b'x = ' + b'a / ' * 1000 + b'a\r\n') is True
    assert _trace(inside3) < 200000


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
        ns['rulelist_parse'](None)
    assert str(e.value) == 'P235:rulelist_parse:bad_type:data'


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
        ns['rulelist_parse'](None)
    assert str(e.value) == 'custom:rulelist_parse:bad_type:data' and calls == ['rulelist_parse']


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
        assert mod.rulelist_parse(b'a=b\r\n') == ((b'a', False, ('name', b'b')),)
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





# ================= module namespace and literal pins =================
_NS_BASE = ['ADJACENT', 'CLAIMS', 'MAX_DATA', 'MAX_DEPTH', 'NOT_CLAIMED', 'SCOPE', '_ALPHA', '_BIT', '_DIGIT', '_HEXD', '_No',
            '__builtins__', '__doc__', '__name__', '_alternation', '_check', '_cnl_end', '_concatenation', '_element', '_estart', '_is_wsp', '_no',
            '_num', '_numval', '_parse', '_quoted', '_repetition', '_rule', '_rulename', '_ws', 'make_fail',
            'rulelist_is_valid', 'rulelist_parse']


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
    assert m.MAX_DATA == 4096 and type(m.MAX_DATA) is int
    assert m.MAX_DEPTH == 64 and type(m.MAX_DEPTH) is int
    assert m._ALPHA == b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    assert m._DIGIT == b'0123456789' and m._BIT == b'01'
    assert m._HEXD == b'0123456789abcdefABCDEF'
    for n in ('_ALPHA', '_DIGIT', '_BIT', '_HEXD'):
        v = getattr(m, n)
        assert type(v) is bytes and len(v) == len(set(v)), n


def test_module_source_is_ascii_and_uses_no_int_call_no_regex_no_clock_no_import_beyond_the_guard():
    import ast
    src = pathlib.Path(m.__file__).read_text()
    src.encode('ascii')
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            assert n.func.id not in ('int', 'str', 'float', 'eval', 'exec', 'compile', 'open', 'input',
                                     'isinstance', 'issubclass', 'getattr', 'setattr', 'round')
        if isinstance(n, ast.Attribute):
            assert n.attr not in ('decode', 'encode', 'isdigit', 'isnumeric', 'isdecimal', 'isalpha', 'isalnum',
                                  'strip', 'lstrip', 'rstrip', 'split', 'splitlines', 'replace', 'lower',
                                  'upper', 'casefold', 'translate', 'removeprefix', 'removesuffix')
    names = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        local = {a.arg for a in fn.args.args}
        for x in ast.walk(fn):
            if isinstance(x, ast.Name) and isinstance(x.ctx, (ast.Store, ast.Del)):
                local.add(x.id)
        for x in ast.walk(fn):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load) and x.id not in local:
                names.add(x.id)
    assert names == {'MAX_DATA', 'MAX_DEPTH', 'ValueError', '_ALPHA', '_BIT', '_DIGIT', '_HEXD', '_No',
                     '_alternation', '_check', '_cnl_end', '_concatenation', '_element', '_estart', '_is_wsp',
                     '_no', '_num', '_numval', '_parse', '_quoted', '_repetition', '_rule', '_rulename', '_ws',
                     'bytes', 'code', 'fail', 'len', 'make_fail', 'name', 'tuple', 'type'}
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert len(imports) == 2
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.Global, ast.Nonlocal, ast.Lambda))]
    assert len([n for n in ast.walk(tree) if isinstance(n, ast.Try)]) == 2


# ================= every refusal site, no import on any of them =================
def _site_cases():
    return [
        (TP, 'bad_type:data', (1,)), (TP, 'bad_value:data.length', (b'a' * 4097,)),
        (TV, 'bad_type:data', (1,)),
        (TP, 'bad_value:nl', (b'\r',)), (TP, 'bad_value:nl', (b'\n',)), (TP, 'bad_value:char', (b'\x80',)),
        (TP, 'bad_value:rulelist', (b'',)),
        (TP, 'bad_value:rulename', (b'1x\r\n',)), (TP, 'bad_value:rulename', (b' x\r\n',)),
        (TP, 'bad_value:defined_as', (b'x y\r\n',)),
        (TP, 'bad_value:element', (b'x =\r\n',)), (TP, 'bad_value:element', (b'x = ',)),
        (TP, 'bad_value:element', (b'x = 3 \r\n',)),
        (TP, 'bad_value:numval', (b'x = %b2\r\n',)), (TP, 'bad_value:numval', (b'x = %q1\r\n',)),
        (TP, 'bad_value:charval', (b'x = "abc',)), (TP, 'bad_value:charval', (b'x = "a\tb"\r\n',)),
        (TP, 'bad_value:charval', (b'x = %s1\r\n',)),
        (TP, 'bad_value:proseval', (b'x = <abc',)), (TP, 'bad_value:proseval', (b'x = <a\tb>\r\n',)),
        (TP, 'bad_value:group', (b'x = (a\r\n',)), (TP, 'bad_value:option', (b'x = [a\r\n',)),
        (TP, 'bad_value:depth', (b'x = ' + b'(' * 65 + b'a' + b')' * 65 + b'\r\n',)),
        (TP, 'bad_value:depth', (b'x = ' + b'[' * 65 + b'a' + b']' * 65 + b'\r\n',)),
        (TP, 'bad_value:crlf', (b'x = y',)), (TP, 'bad_value:crlf', (b'x = y ',)),
    ]


_ALL_CODES = (
    'bad_type:data', 'bad_value:data.length', 'bad_value:nl', 'bad_value:char', 'bad_value:rulelist',
    'bad_value:rulename', 'bad_value:defined_as', 'bad_value:element', 'bad_value:numval', 'bad_value:charval',
    'bad_value:proseval', 'bad_value:group', 'bad_value:option', 'bad_value:depth', 'bad_value:crlf')


def _ok_calls():
    assert m.rulelist_parse(b'x = y\r\n') == ((b'x', False, ('name', b'y')),)
    for t in GOOD:
        assert m.rulelist_is_valid(t) is True
        m.rulelist_parse(t)
    for t in BAD:
        assert m.rulelist_is_valid(t) is False
    m.rulelist_is_valid(b'x = y\r\n')


def test_site_cases_cover_exactly_the_documented_codes_and_each_raises_it():
    cases = _site_cases()
    assert set(c for _f, c, _a in cases) == set(_ALL_CODES)
    assert len(_ALL_CODES) == len(set(_ALL_CODES)) == 15
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
    assert len(want) == 26 and len(returns) == 35
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
    assert ns['rulelist_parse'](b'a=b\r\n') == ((b'a', False, ('name', b'b')),)
    assert ns['rulelist_is_valid'](b'a=b\r\n') is True


def test_fallback_handler_binds_iu_not_importlib():
    ns, _seen, _fc = _exec_guarded(import_exc=_mnfe(REG), spec_result=None)
    assert '_iu' in ns and 'importlib' not in ns
    assert ns['_iu'] is iu
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
    'rulelist = 1*( rule / (*c-wsp c-nl) )',
    'rule = rulename defined-as elements c-nl',
    'rulename = ALPHA *(ALPHA / DIGIT / "-")',
    'defined-as = *c-wsp ("=" / "=/") *c-wsp',
    'elements = alternation *c-wsp',
    'c-wsp = WSP / (c-nl WSP)',
    'c-nl = comment / CRLF',
    'comment = ";" *(WSP / VCHAR) CRLF',
    '*(*c-wsp "/" *c-wsp concatenation)',
    'concatenation = repetition *(1*c-wsp repetition)',
    'repetition = [repeat] element',
    'repeat = 1*DIGIT / (*DIGIT "*" *DIGIT)',
    'element = rulename / group / option /',
    'char-val / num-val / prose-val',
    'group = "(" *c-wsp alternation *c-wsp ")"',
    'option = "[" *c-wsp alternation *c-wsp "]"',
    'char-val = DQUOTE *(%x20-21 / %x23-7E) DQUOTE',
    'num-val = "%" (bin-val / dec-val / hex-val)',
    'bin-val = "b" 1*BIT',
    'prose-val = "<" *(%x20-3D / %x3F-7E) ">"',
    'case-sensitive-string',
    '[ "%i" ] quoted-string',
    '"%s" quoted-string',
    'quoted-string = DQUOTE *(%x20-21 / %x23-7E) DQUOTE',
)


@pytest.mark.parametrize('q', _DOC_QUOTES)
def test_docstring_quote_present(q):
    assert q in ' '.join(m.__doc__.split())


_DOC_FULL = (
    'P235 b1213 bounded exact RFC 5234 ABNF rulelist syntax (Sections 3 and 4) with RFC 7405 %s/%i string'
    ' prefixes: parse and validate only. Pure functions on bytes, no clock, no network, no regex: rulelis'
    't_parse and rulelist_is_valid. Primary sources (fetched fresh and read live 2026-10-21): RFC 5234 Au'
    'gmented BNF for Syntax Specifications: ABNF, https://www.rfc-editor.org/rfc/rfc5234.txt, Section 3 ('
    'operators) and Section 4 (ABNF definition of ABNF), and RFC 7405 Case-Sensitive String Support in AB'
    "NF, https://www.rfc-editor.org/rfc/rfc7405.txt, Section 2. Quotes: 'rulelist = 1*( rule / (*c-wsp c-"
    'nl) )\' \'rule = rulename defined-as elements c-nl\' \'rulename = ALPHA *(ALPHA / DIGIT / "-")\' \'defined'
    '-as = *c-wsp ("=" / "=/") *c-wsp\' \'elements = alternation *c-wsp\' \'c-wsp = WSP / (c-nl WSP)\' \'c-nl ='
    ' comment / CRLF\' \'comment = ";" *(WSP / VCHAR) CRLF\' \'*(*c-wsp "/" *c-wsp concatenation)\' \'concatena'
    "tion = repetition *(1*c-wsp repetition)' 'repetition = [repeat] element' 'repeat = 1*DIGIT / (*DIGIT"
    ' "*" *DIGIT)\' \'element = rulename / group / option /\' \'char-val / num-val / prose-val\' \'group = "(" '
    '*c-wsp alternation *c-wsp ")"\' \'option = "[" *c-wsp alternation *c-wsp "]"\' \'char-val = DQUOTE *(%x2'
    '0-21 / %x23-7E) DQUOTE\' \'num-val = "%" (bin-val / dec-val / hex-val)\' \'bin-val = "b" 1*BIT\' \'prose-v'
    'al = "<" *(%x20-3D / %x3F-7E) ">"\' \'case-sensitive-string\' \'[ "%i" ] quoted-string\' \'"%s" quoted-str'
    "ing' 'quoted-string = DQUOTE *(%x20-21 / %x23-7E) DQUOTE'. Errata (read live 2026-10-21, from the fu"
    'll index https://www.rfc-editor.org/errata.json): RFC 5234 has twelve records and RFC 7405 has one. '
    "EID 2968 (Verified, Technical, 4) changes elements to 'alternation *WSP' and is APPLIED: trailing wh"
    'itespace after the last element is plain WSP, so the grammar is not ambiguous. EID 3076 (Verified, T'
    "echnical, 4) changes rulelist to '1*( rule / (*WSP c-nl) )' and is APPLIED: a blank or comment line "
    'between rules is WSP then comment-or-newline. EID 2820 (Held for Document Update, Editorial, 4) only'
    ' rewords the prose-val comment from \'without angles\' to \'without ">"\'; the printed range is unchange'
    "d and is what is implemented here, so '<' (%x3C) is allowed inside a prose-val and only '>' is exclu"
    'ded. EID 2914 (Held for Document Update, Editorial, GLOBAL) notes that the Section 4 grammar is recu'
    'rsive; informational only. EID 6172 (Held for Document Update, Editorial, Appendix B) and EID 6173 ('
    'Held for Document Update, Editorial, 3.6) fix wording; informational only. EID 1423 (Rejected, Techn'
    'ical, 4), EID 3096 (Rejected, Technical, B.1), EID 4040 (Rejected, Technical, B.1), EID 5110 (Reject'
    'ed, Technical, B.1.), EID 4361 (Rejected, Editorial, 2.1), EID 4564 (Rejected, Technical, 3.8) and, '
    'for RFC 7405, EID 5334 (Rejected, Technical, 2.2) are not applied. CONVENTIONS (OURS, UNSOURCED wher'
    'e stated). Input is exact bytes, never str, bytearray or a bytes subclass, at most 4096 bytes (MAX_D'
    'ATA); a longer input is refused before any scan. Only HTAB, CR, LF and printable ASCII %x20-7E may a'
    'ppear; any other byte raises bad_value:char. Line endings must be strict CRLF pairs; a lone CR or LF'
    ' raises bad_value:nl. Every rule must end with a comment or CRLF, so the last line of input must be '
    'CRLF terminated; where a rule ending is missing or junk stands where the ending belongs, bad_value:c'
    'rlf is raised. Empty input raises bad_value:rulelist; an input of only blank lines and comment lines'
    ' is valid (the grammar allows it) and parses to the empty tuple. A rule must begin with a letter in '
    'column 0; a line that begins with WSP and is then not a blank or comment line raises bad_value:rulen'
    'ame. Group and option nesting deeper than 64 (MAX_DEPTH) raises bad_value:depth. The base letters of'
    ' num-val and the RFC 7405 prefixes are string literals of the grammar and string literals are case-i'
    'nsensitive, so %X41, %B101, %D13, %S"a" and %I"a" are accepted. A range whose low value is above its'
    ' high value (for example %x30-20) is valid syntax and is accepted as written; this is a grammar unit'
    ' and does not judge values. No str, decode, encode, int, isdigit, strip or regex is used on input; n'
    'umber values are accumulated digit by digit. rulelist_parse(data) returns a tuple with one (rulename'
    ', incremental, tree) per rule, in order; blank and comment lines are consumed but not returned. In a'
    " tree, a rulename is ('name', bytes) exactly as written, a string is ('str', kind, bytes) with kind "
    "'i' or 's' and the quotes removed and no case folding, a numeric value is ('num', base, value) with "
    "base 'b', 'd' or 'x' and value ('seq', (v, ...)) or ('range', lo, hi) as integers, a prose value is "
    "('prose', bytes) without the angle brackets, a group is ('grp', inner), an option is ('opt', inner),"
    " a repetition is ('rep', lo, hi, element) with hi None for no upper bound and a bare count n as ('re"
    "p', n, n, element), an alternation of two or more parts is ('alt', parts) and a concatenation of two"
    " or more parts is ('cat', parts); a singleton alternation or concatenation collapses to its single p"
    'art. rulelist_is_valid(data) returns exactly True or False and refuses only a wrong type. Check orde'
    'r: bad_type:data, bad_value:data.length, then a whole-input scan in position order raising bad_value'
    ':nl or bad_value:char, then a left-to-right structural scan raising bad_value:rulelist, bad_value:ru'
    'lename, bad_value:defined_as, bad_value:element, bad_value:numval, bad_value:charval, bad_value:pros'
    'eval, bad_value:group, bad_value:option, bad_value:depth or bad_value:crlf. Errors are ValueError wi'
    'th message P235:<function>:<code>. Matching input against a described grammar, the Appendix B core r'
    'ules as data, terminal value semantics and prose-val semantics are not implemented. ADJACENCY, by na'
    'me only: the Appendix B core rules of RFC 5234 are referenced as names only, RFC 7405 Section 2.1 ma'
    'tching semantics, and every unit that quotes ABNF to define its own syntax belong to other units and'
    ' were not read beyond the sections named above. SCOPE and NOT_CLAIMED are the module constants below'
    '.'
)


def test_docstring_whole_exact():
    assert ' '.join(m.__doc__.split()) == _DOC_FULL
    assert m.__doc__.startswith('P235 b1213 bounded exact RFC 5234')


def test_scope_and_constants_exact():
    assert m.SCOPE == 'PARTIAL: RFC 5234 Section 3 and 4 ABNF rulelist grammar with the RFC 7405 Section 2.2 %s and %i string prefixes on whole bytes values, parse and is_valid, pure functions, with the OURS choices stated in the docstring'
    assert m.NOT_CLAIMED == ('matching any input against a grammar described by a rulelist', 'the Appendix B core rules as data or their semantics', 'terminal value, prose-val or case-matching semantics', 'global novelty', 'production readiness')
    assert m.ADJACENT == ('the Appendix B core rules of RFC 5234, RFC 7405 Section 2.1 matching semantics and every unit that quotes ABNF for its own syntax are covered elsewhere and were not read beyond the sections named in the docstring',)
    assert m.CLAIMS is False
    assert m.MAX_DATA == 4096
    assert m.MAX_DEPTH == 64
    assert type(m.NOT_CLAIMED) is tuple and type(m.ADJACENT) is tuple and type(m.SCOPE) is str
