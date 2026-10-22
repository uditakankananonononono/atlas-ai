import builtins
import importlib
import importlib.util
import itertools
import os
import random
import re
import signal
import resource
import sys
import types

import pytest

sys.path.insert(0, 'backend')
from app.modules.instinct_doc import p235_concepts_batch1188_fieldcounts as m
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


MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1188_fieldcounts'
REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODPATH = m.__file__


def _probe():
    try:
        m.kind(None)
    except ValueError as e:
        s = str(e)
        assert s.endswith('kind:name-type'), s
        return s[:-len('kind:name-type')]
    raise AssertionError('probe')


PFX = _probe()


@pytest.fixture(autouse=True)
def _guard():
    old = signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError('guard')))
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    signal.setitimer(signal.ITIMER_REAL, 30)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
        resource.setrlimit(resource.RLIMIT_AS, (soft, hard))


def err(fn, code, *args):
    with pytest.raises(ValueError) as e:
        getattr(m, fn)(*args)
    assert str(e.value) == PFX + fn + ':' + code, (str(e.value), fn, code)


class SubStr(str):
    pass

class SubInt(int):
    pass

class SubList(list):
    pass

class SubTuple(tuple):
    pass


def run(fn, *args):
    try:
        return getattr(m, fn)(*args)
    except ValueError as e:
        assert str(e).startswith(PFX + fn + ':'), str(e)
        return 'ERR:' + str(e)[len(PFX + fn + ':'):]


WIRE = {'date': 'orig-date', 'from': 'from', 'sender': 'sender', 'reply-to': 'reply-to', 'to': 'to', 'cc': 'cc', 'bcc': 'bcc', 'message-id': 'message-id', 'in-reply-to': 'in-reply-to', 'references': 'references', 'subject': 'subject', 'comments': 'comments', 'keywords': 'keywords', 'resent-date': 'resent-date', 'resent-from': 'resent-from', 'resent-sender': 'resent-sender', 'resent-to': 'resent-to', 'resent-cc': 'resent-cc', 'resent-bcc': 'resent-bcc', 'resent-msg-id': 'resent-msg-id', 'received': 'trace', 'return-path': 'trace'}
ROWS = [('orig-date', 1, 1), ('from', 1, 1), ('sender', 0, 1), ('reply-to', 0, 1), ('to', 0, 1), ('cc', 0, 1), ('bcc', 0, 1), ('message-id', 0, 1), ('in-reply-to', 0, 1), ('references', 0, 1), ('subject', 0, 1)]
ROWSET = {r for r, lo, hi in ROWS}
RROWS = ['resent-date', 'resent-from', 'resent-sender', 'resent-to', 'resent-cc', 'resent-bcc', 'resent-msg-id']


def o_kind(name):
    return WIRE.get(name.lower(), 'optional-field')


def o_main(kinds):
    out = []
    for row, lo, hi in ROWS:
        n = sum(1 for k in kinds if k == row)
        if lo == 1 and n == 0:
            out.append(row + '-missing')
        if n > hi:
            out.append(row + '-many')
    return out


def o_block(kinds):
    out = []
    total = 0
    for row in RROWS:
        n = sum(1 for k in kinds if k == row)
        total += n
        if n > 1:
            out.append(row + '-many')
    if total and kinds.count('resent-date') == 0:
        out.insert(0, 'resent-date-missing')
    return out


def o_message(kinds):
    out = list(o_main([k for k in kinds if k in ROWSET]))
    run = []
    for k in kinds:
        if k in RROWS:
            run.append(k)
        else:
            out += o_block(run)
            run = []
    out += o_block(run)
    return tuple(out)


def test_constants_tables_and_namespace():
    assert m.NAMES == WIRE and len(m.NAMES) == 22
    assert m.RESENT == ('resent-date', 'resent-from', 'resent-sender', 'resent-to', 'resent-cc', 'resent-bcc', 'resent-msg-id')
    assert m.MAIN == ('orig-date', 'from', 'sender', 'reply-to', 'to', 'cc', 'bcc', 'message-id', 'in-reply-to', 'references', 'subject')
    assert m.REQUIRED == ('orig-date', 'from')
    assert (m.NAME_MAX, m.FIELDS_MAX, m.COUNT_MAX) == (64, 4096, 255)
    assert m.SCOPE == 'RFC 5322 section 3.6 header field occurrence counts' and m.CLAIMS is False
    assert m.NOT_CLAIMED == ('field body syntax or semantics', 'mailbox counts inside any field', 'ordering rules beyond maximal resent runs', 'obsolete field syntax', 'message transmission')
    assert m.ADJACENT == ('RFC 5322 sections 3.6.1 to 3.6.7 field semantics', 'RFC 5321 trace field handling', 'RFC 2045 MIME header fields')
    names = {k for k in vars(m) if not k.startswith('__')}
    assert names == {'find_spec', 'make_fail', 'SCOPE', 'NOT_CLAIMED', 'ADJACENT', 'CLAIMS', 'NAME_MAX', 'FIELDS_MAX', 'COUNT_MAX', 'NAMES', 'RESENT', 'MAIN', 'REQUIRED', '_canon', '_name', 'kind', '_count', 'needs_sender', 'needs_resent_sender', '_struct', '_main', '_block', 'check_counts', 'check_block', 'check_message'}
    for w, k in WIRE.items():
        for v in (w, w.upper(), w.title(), w.swapcase()):
            assert m.kind(v) == k and m._canon(v) == k, v
    assert m._canon('X-Foo') == 'optional-field' and m._canon('ZZZ') == 'optional-field'


def test_kind_all_chars_and_bounds():
    assert m.kind('a' * 64) == 'optional-field' and m.kind('a' * 63 + '9') == 'optional-field'
    err('kind', 'name-length', 'a' * 65)
    err('kind', 'name-length', 'a' * 100)
    for c in range(0, 256):
        ch = chr(c)
        ok = 33 <= c <= 126 and c != 58
        if ok:
            assert m.kind(ch) == o_kind(ch), c
            assert m.kind('a' + ch) == o_kind('a' + ch) and m.kind(ch + 'a') == o_kind(ch + 'a') and m.kind('ab' + ch + 'cd') == o_kind('ab' + ch + 'cd')
        else:
            err('kind', 'name-invalid', ch)
            err('kind', 'name-invalid', 'a' + ch)
            err('kind', 'name-invalid', ch + 'a')
            err('kind', 'name-invalid', 'ab' + ch + 'cd')
    err('kind', 'name-invalid', '')
    err('kind', 'name-length', '\x00' * 65)
    err('kind', 'name-length', ' ' * 65)
    for bad in (None, b'a', 5, ['a'], SubStr('date'), True):
        err('kind', 'name-type', bad)
    err('kind', 'name-type', SubStr('a' * 65))


def test_needs_sender_pair():
    for fn in ('needs_sender', 'needs_resent_sender'):
        assert getattr(m, fn)(0) is False and getattr(m, fn)(1) is False
        assert getattr(m, fn)(2) is True and getattr(m, fn)(3) is True
        assert getattr(m, fn)(254) is True and getattr(m, fn)(255) is True
        err(fn, 'count-range', 256)
        err(fn, 'count-range', 1000)
        err(fn, 'count-range', -1)
        err(fn, 'count-range', -255)
        for bad in (None, 'x', 1.5, True, False, SubInt(2), [1]):
            err(fn, 'count-type', bad)
        err(fn, 'count-range', SubInt(0) if False else -0 + 256)


def test_check_counts_vectors_and_order():
    C = m.check_counts
    assert C(()) == ('orig-date-missing', 'from-missing') and C([]) == ('orig-date-missing', 'from-missing')
    assert C(['date', 'from']) == () and C(['from', 'date']) == ()
    assert C(['date']) == ('from-missing',) and C(['from']) == ('orig-date-missing',)
    assert C(['date', 'date', 'from']) == ('orig-date-many',) and C(['date', 'from', 'from']) == ('from-many',)
    assert C(['date', 'date', 'date', 'from']) == ('orig-date-many',)
    assert C(['from', 'from', 'from']) == ('orig-date-missing', 'from-many')
    for row, lo, hi in ROWS:
        if row in ('orig-date', 'from'):
            continue
        base = ['date', 'from']
        assert C(base + [row]) == (), row
        assert C(base + [row, row]) == (row + '-many',), row
        assert C(base + [row] * 5) == (row + '-many',), row
    assert C(['date', 'from'] + ['comments', 'comments', 'comments', 'keywords'] * 20) == ()
    assert C(['date', 'from'] + ['x-a', 'received', 'return-path'] * 100) == ()
    assert C(['date', 'from', 'resent-from', 'resent-date']) == ()
    assert C(['to', 'to', 'cc', 'cc', 'date', 'from', 'from']) == ('from-many', 'to-many', 'cc-many')
    assert C(['subject', 'subject', 'to', 'to']) == ('orig-date-missing', 'from-missing', 'to-many', 'subject-many')
    assert C(['date', 'from', 'DATE', 'FROM']) == ('orig-date-many', 'from-many')
    assert len(C(['date', 'from'] + ['x-a'] * 4094)) == 0
    err('check_counts', 'fields-length', ['date'] * 4097)
    assert C(['date', 'from'] + ['comments'] * 4094) == ()
    for pos in range(0, 4):
        pre = ['date', 'from', 'to'][:pos] + ['date', 'from'][0:0]
        base = ['date', 'from', 'cc'][:pos]
        full = ['date', 'from'] + ['cc'] * pos
        err('check_counts', 'name-type', full + [None])
        err('check_counts', 'name-type', full + [SubStr('to')])
        err('check_counts', 'name-length', full + ['a' * 65])
        err('check_counts', 'name-invalid', full + ['a b'])
    for bad in (None, 'date', 5, SubList(['date']), SubTuple(('date',)), {'date': 1}):
        err('check_counts', 'fields-type', bad)
    assert C(('date', 'from')) == () and C(['date', 'from']) == ()


def test_check_block_vectors_and_order():
    B = m.check_block
    assert B(()) == () and B([]) == ()
    assert B(['resent-date']) == ()
    for row in RROWS:
        if row == 'resent-date':
            continue
        assert B([row]) == ('resent-date-missing',), row
        assert B(['resent-date', row]) == (), row
        assert B([row, row]) == ('resent-date-missing', row + '-many'), row
        assert B(['resent-date', row, row]) == (row + '-many',), row
    assert B(['resent-date', 'resent-date']) == ('resent-date-many',)
    assert B(['resent-date', 'resent-date', 'resent-from']) == ('resent-date-many',)
    assert B(['resent-from', 'resent-to', 'resent-cc', 'resent-bcc', 'resent-msg-id', 'resent-sender', 'resent-date']) == ()
    assert B(['resent-from', 'resent-from', 'resent-to', 'resent-to']) == ('resent-date-missing', 'resent-from-many', 'resent-to-many')
    assert B(['resent-date', 'resent-from', 'resent-from', 'resent-to', 'resent-to']) == ('resent-from-many', 'resent-to-many')
    assert B(['from', 'to', 'received', 'x-a', 'comments']) == ()
    assert B(['date', 'from', 'resent-from']) == ('resent-date-missing',)
    assert B(['RESENT-FROM', 'Resent-To']) == ('resent-date-missing',)
    assert B(['resent-date'] + ['resent-from'] * 2 + ['x-a'] * 5) == ('resent-from-many',)
    err('check_block', 'fields-length', ['resent-date'] * 4097)
    assert B(['resent-date'] + ['x-a'] * 4095) == ()
    for bad in (None, 'resent-date', SubList(['resent-date'])):
        err('check_block', 'fields-type', bad)
    for pos in range(0, 3):
        pre = ['resent-date'] + ['resent-from'] * pos
        err('check_block', 'name-type', pre + [None])
        err('check_block', 'name-length', pre + ['a' * 65])
        err('check_block', 'name-invalid', pre + ['a:b'])


def test_check_message_runs_and_oracle():
    M = m.check_message
    assert M(['date', 'from', 'to', 'subject']) == ()
    assert M(['received', 'received', 'return-path', 'date', 'from', 'sender', 'reply-to', 'to', 'cc', 'bcc', 'message-id', 'in-reply-to', 'references', 'subject', 'comments', 'keywords', 'x-1', 'x-2']) == ()
    assert M(['resent-date', 'resent-from', 'date', 'from']) == ()
    assert M(['resent-from', 'to', 'resent-cc']) == ('orig-date-missing', 'from-missing', 'resent-date-missing', 'resent-date-missing')
    assert M(['resent-from', 'resent-cc', 'to']) == ('orig-date-missing', 'from-missing', 'resent-date-missing')
    assert M(['resent-from', 'received', 'resent-date']) == ('orig-date-missing', 'from-missing', 'resent-date-missing')
    assert M(['resent-from', 'x-a', 'resent-date']) == ('orig-date-missing', 'from-missing', 'resent-date-missing')
    assert M(['resent-to', 'date', 'date']) == ('orig-date-many', 'from-missing', 'resent-date-missing')
    assert M(['date', 'date', 'resent-from', 'resent-from']) == ('orig-date-many', 'from-missing', 'resent-date-missing', 'resent-from-many')
    assert M(['resent-from', 'resent-from', 'date', 'from', 'resent-to']) == ('resent-date-missing', 'resent-from-many', 'resent-date-missing')
    assert M(['to', 'to', 'resent-from', 'resent-date', 'resent-from']) == ('orig-date-missing', 'from-missing', 'to-many', 'resent-from-many')
    err('check_message', 'fields-type', None)
    err('check_message', 'fields-type', SubList(['date']))
    err('check_message', 'fields-length', ['date'] * 4097)
    err('check_message', 'name-type', ['date', 'from', None])
    err('check_message', 'name-type', ['date', 'from', 'to', None])
    alphabet = ['date', 'from', 'to', 'comments', 'resent-date', 'resent-from', 'received', 'x-a']
    n = 0
    for length in range(0, 4):
        for t in itertools.product(alphabet, repeat=length):
            ks = [o_kind(x) for x in t]
            assert M(list(t)) == o_message(ks), t
            n += 1
    assert n == sum(8 ** k for k in range(4))
    rnd = random.Random(1188)
    pool = list(WIRE) + ['x-a', 'x-b', 'foo']
    for _ in range(4000):
        t = [rnd.choice(pool) for _ in range(rnd.randint(0, 14))]
        ks = [o_kind(x) for x in t]
        assert M(t) == o_message(ks), t
        assert m.check_counts(t) == tuple(o_main([k for k in ks if k in ROWSET])), t
        assert m.check_block(t) == tuple(o_block([k for k in ks if k in RROWS])), t


def _run_everything():
    texts = ['date', 'FROM', 'x-a', '', 'a b', 'a:b', 'a' * 65, None, SubStr('to'), '\x7f', 'received', 'resent-bcc']
    for t in texts:
        try:
            m.kind(t)
        except ValueError:
            pass
    for n in (0, 1, 2, 255, 256, -1, None, True, SubInt(2)):
        for fn in (m.needs_sender, m.needs_resent_sender):
            try:
                fn(n)
            except ValueError:
                pass
    samples = [(), [], ['date', 'from'], ['date'], ['from'], ['date', 'date', 'from', 'from'], ['to', 'to', 'subject', 'subject'], ['comments'] * 50, ['resent-from'], ['resent-date'], ['resent-date', 'resent-from', 'resent-from'], ['resent-from', 'to', 'resent-cc'], ['resent-from', 'received', 'resent-date'], ['date', 'from', 'x-a', 'received'], ['date', 'from', None], ['date', 'from', 'a' * 65], ['date', 'from', 'a b'], ['date'] * 4097, None, 'date', SubList(['date']), ('date', 'from'), ['resent-to', 'date', 'date', 'from', 'resent-bcc']]
    for s in samples:
        for fn in (m.check_counts, m.check_block, m.check_message):
            try:
                fn(s)
            except ValueError:
                pass


def _no_import_hook(*a, **k):
    raise AssertionError('import during call: %r' % (a[:1],))


def _load(name='fresh_1188'):
    spec = importlib.util.spec_from_file_location(name, MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LAST = []
EXPECT_LOG = [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]


def _logged_load(fs=None):
    log = LAST
    del log[:]
    real = builtins.__import__

    def spy(name, globals=None, locals=None, fromlist=(), level=0):
        if globals is not None and globals.get('__name__') == 'fresh_1188':
            log.append((name, tuple(fromlist or ()), level))
        return real(name, globals, locals, fromlist, level)

    calls = []
    real_fs = importlib.util.find_spec
    importlib.util.find_spec = fs if fs is not None else (lambda n, *a, **k: calls.append(n) or real_fs(n, *a, **k))
    _start_import(builtins, spy)
    try:
        mod = _load()
    finally:
        _stop_import()
        importlib.util.find_spec = real_fs
    return mod, log, calls


def test_exact_import_log_and_find_spec_count_in_this_world():
    present = sys.modules.get(REG) is not None
    saved = sys.modules.pop(REG, None)
    try:
        mod, log, calls = _logged_load()
        assert log == EXPECT_LOG
        assert calls == [REG] and mod.make_fail is not None
        with pytest.raises(ValueError) as e:
            mod.make_fail('f')('c')
        assert str(e.value) == 'P235:f:c'
    finally:
        if saved is not None:
            sys.modules[REG] = saved
    if present:
        mod, log, calls = _logged_load()
        assert log == EXPECT_LOG
        assert calls == [] and mod.make_fail is saved.make_fail


def test_absent_registry_fallback_literal_and_reraise_paths():
    saved = sys.modules.get(REG, 'absent')
    try:
        sys.modules[REG] = None
        mod, log, calls = _logged_load(lambda n, *a, **k: None)
        with pytest.raises(ValueError) as e:
            mod.make_fail('f')('c')
        assert str(e.value) == 'P235:f:c'
        with pytest.raises(ValueError) as e:
            mod.kind(None)
        assert str(e.value) == 'P235:kind:name-type'
        with pytest.raises(ModuleNotFoundError):
            _logged_load(lambda n, *a, **k: object())
        assert LAST == EXPECT_LOG
        stub = types.ModuleType(REG)
        sys.modules[REG] = stub
        with pytest.raises(ImportError) as e:
            _logged_load()
        assert not isinstance(e.value, ModuleNotFoundError)

        for other in ('app', 'aaa_other', 'app.modules.instinct_doc', 'zzz_other'):
            class Loader:
                def create_module(self, spec):
                    return None

                def exec_module(self, module):
                    raise ModuleNotFoundError('inner', name=other)

            class Finder:
                def find_spec(self, name, path=None, target=None):
                    if name == REG:
                        return importlib.util.spec_from_loader(name, Loader())

            sys.modules.pop(REG, None)
            sys.meta_path.insert(0, Finder())
            try:
                with pytest.raises(ModuleNotFoundError) as e:
                    _logged_load(lambda n, *a, **k: None)
                assert e.value.name == other
                assert LAST == EXPECT_LOG
            finally:
                sys.meta_path.pop(0)
        good = types.ModuleType(REG)
        good.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('X:%s:%s' % (name, code))))
        sys.modules[REG] = good
        mod, log, calls = _logged_load()
        assert calls == [] and mod.make_fail is good.make_fail
        with pytest.raises(ValueError) as e:
            mod.kind(1)
        assert str(e.value) == 'X:kind:name-type'
    finally:
        if saved == 'absent':
            sys.modules.pop(REG, None)
        else:
            sys.modules[REG] = saved


def test_no_import_on_any_call_path():
    real = builtins.__import__
    _start_import(builtins, _no_import_hook)
    try:
        _run_everything()
        assert m.check_message(['date', 'from', 'resent-date', 'resent-from']) == ()
        assert m.kind('To') == 'to'
    finally:
        _stop_import()


def test_no_import_at_any_line_and_every_line_reached():
    import ast
    with open(MODPATH) as fh:
        src = fh.read()
    tree = ast.parse(src)
    want = {}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef):
            lines = set()
            for n in ast.walk(fn):
                if isinstance(n, ast.stmt) and n is not fn:
                    lines.add(n.lineno)
            want[fn.name] = lines
    hit = set()
    real = builtins.__import__

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != MODPATH:
            return None
        if event == 'line':
            hit.add((frame.f_code.co_name, frame.f_lineno))
        return tracer

    _start_import(builtins, _no_import_hook)
    sys.settrace(tracer)
    try:
        _run_everything()
        assert m.check_message(['resent-from', 'to', 'resent-date']) == ('orig-date-missing', 'from-missing', 'resent-date-missing')
        assert m.check_block(['resent-from', 'resent-from']) == ('resent-date-missing', 'resent-from-many')
        assert m.check_counts(['date', 'date', 'from', 'from', 'to', 'to']) == ('orig-date-many', 'from-many', 'to-many')
    finally:
        sys.settrace(None)
        _stop_import()
    missing = []
    for name, lines in want.items():
        for ln in sorted(lines):
            if (name, ln) not in hit:
                missing.append((name, ln))
    assert missing == []
    assert set(want) == {'_canon', '_name', 'kind', '_count', 'needs_sender', 'needs_resent_sender', '_struct', '_main', '_block', 'check_counts', 'check_block', 'check_message'}


STATIC_CODES = {'_name': ['name-type', 'name-length', 'name-invalid', 'name-invalid'], '_count': ['count-type', 'count-range'], '_struct': ['fields-type', 'fields-length']}


def test_ast_every_f_site_codes():
    import ast
    with open(MODPATH) as fh:
        tree = ast.parse(fh.read())
    got = {}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef):
            sites = []
            for n in ast.walk(fn):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'f':
                    a = n.args[0]
                    sites.append(a.value if isinstance(a, ast.Constant) else '<' + ast.unparse(a) + '>')
            if sites:
                got[fn.name] = sites
    assert got == STATIC_CODES
    assert sum(len(v) for v in got.values()) == 8


def test_cap_before_work_tracemalloc_pins():
    import tracemalloc
    n = 2000000
    big = 'a' * n
    many = ['date'] * n
    cases = (('kind', (big,), 'name-length'), ('kind', ('\x00' * n,), 'name-length'), ('check_counts', (many,), 'fields-length'), ('check_block', (many,), 'fields-length'), ('check_message', (many,), 'fields-length'))
    for fn, args, code in cases:
        tracemalloc.start()
        try:
            with pytest.raises(ValueError) as e:
                getattr(m, fn)(*args)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert str(e.value) == PFX + fn + ':' + code
        assert peak < 20000, (fn, peak)


DOC = 'b1188 RFC 5322 section 3.6 header field occurrence counts.\n\nSource: RFC 5322 (Resnick, October 2008), section 3.6 (Field Definitions),\nthe min/max occurrence table and its Notes column. Only the NUMBER of times\neach field occurs is checked, never the field bodies. The RFC says: "The only\nrequired header fields are the origination date field and the originator\naddress field(s)." Five resent rows carry the note\n"One per block - see 3.6.6"; the resent-date row adds that the field is\nrequired when other resent fields are present, and the resent-sender row adds\nthat the field must occur with a multi-address resent-from. For a\nmulti-address originator field the rule is "Otherwise, both fields SHOULD\nappear." The section 3.6.6 prose says Resent-From and Resent-Date MUST both\nbe sent when resent fields are used, which is stronger than the table, where\nonly resent-date carries the conditional requirement; this module implements\nthe table.\nThirty-one errata exist for RFC 5322 in the errata data used; four touch section\n3.6 and are named here. 2816 (Rejected, Technical, section 3.6.2, reply-to\nsyntax): read, NOT applied. 2950 (Held for Document Update, Technical,\nsection 3.6, the fields ABNF): read, NOT applied; it rewrites the ABNF\nrepetition, not the count table. 3048 (Held for Document Update, Editorial,\nsection 3.6.6, wording): read, NOT applied. 3979 (Verified, Technical,\nsections 3.6.7 and 4.5.7, the received-token syntax): read, NOT applied; it\nchanges the Received field body syntax, not any occurrence count, so no\nVerified erratum changes the rules implemented here.\nOURS design choices (not sourced from the RFC): the wire-name to table-kind\nmapping including \'date\' for orig-date and \'received\' and \'return-path\' for\ntrace; every unknown well-formed name is kind optional-field; the caps\nNAME_MAX 64, FIELDS_MAX 4096 and COUNT_MAX 255; the violation codes and their\ntable-row order; a resent block is a maximal contiguous run of resent fields;\nnon-resent and non-trace entries passed to check_block are ignored; trace,\ncomments, keywords and optional-field entries are ignored by the count checks\nbecause the table sets no limit for them; the conditional MUST rules are pure\npredicates (needs_sender, needs_resent_sender) because mailbox counts live in\nfield bodies, which are out of scope. SOURCED: the 22 table rows with their\nmin and max numbers, the one-per-block resent rule with resent-date required\nwhen any resent field is present, and the multi-address sender rules.\nErrors raise ValueError P235:<name>:<code>. Well-formed but over- or\nunder-counted input returns a tuple of violation codes, never an exception.\n'


def test_whole_module_docstring_literal_and_ascii():
    assert m.__doc__ == DOC
    for p in (MODPATH, __file__):
        with open(p, 'rb') as fh:
            assert fh.read().isascii()
    assert '\\' not in m.__doc__
    assert '2950 (Held for Document Update, Technical,' in m.__doc__
    assert '3979 (Verified, Technical,' in m.__doc__ and 'NOT applied' in m.__doc__
    assert 'OURS' in m.__doc__ and 'SOURCED' in m.__doc__
