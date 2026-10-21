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
from app.modules.instinct_doc import p235_concepts_batch1240_fileuris as m

MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1240_fileuris'
REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODPATH = m.__file__


def _probe():
    try:
        m.is_file_uri(None)
    except ValueError as e:
        s = str(e)
        assert s.endswith('is_file_uri:text-type'), s
        return s[:-len('is_file_uri:text-type')]
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


def test_constants_tables_and_namespace():
    assert m.TEXT_MAX == 1024 and m.AUTH_MAX == 255 and m.HOST_MAX == 255
    assert m.UNRESERVED == 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~' and len(m.UNRESERVED) == 66
    assert m.SUB_DELIMS == "!$&'()*+,;=" and len(m.SUB_DELIMS) == 11
    assert m.SUB_DELIMS[0] == '!' and m.SUB_DELIMS[-1] == '='
    assert m.SCOPE == 'RFC 8089 section 2 file URI syntax with appendix E drive letter forms' and m.CLAIMS is False
    assert m.NOT_CLAIMED == ('IPv6 address and IPvFuture validation inside bracketed literals (sibling modules)', 'zone identifiers (sibling module)', 'E.1 userinfo authorities', 'E.3 UNC string forms', 'file system access or path resolution', 'relative reference resolution')
    assert m.ADJACENT == ('RFC 3986 URI syntax (host, path-absolute, pchar, pct-encoded)', 'RFC 5234 ABNF', 'RFC 6874 zone identifiers (sibling module)', 'RFC 4291 and RFC 5952 IPv6 forms (sibling modules)')
    names = {k for k in vars(m) if not k.startswith('__')}
    assert names == {'find_spec', 'make_fail', 'SCOPE', 'NOT_CLAIMED', 'ADJACENT', 'CLAIMS', 'TEXT_MAX', 'AUTH_MAX', 'HOST_MAX', 'UNRESERVED', 'SUB_DELIMS', '_text', '_letter', '_digit', '_unres', '_iei', '_ici', '_hexval', '_pchar', '_path_code', '_host_code', '_ipv4_ok', '_uri_code', '_drive_split', '_drive_uri_code', 'is_file_uri', 'split_file_uri', 'is_local_uri', 'host_kind', 'split_drive', 'split_drive_uri', 'is_drive_uri', 'normalize_pipe'}
    assert m._ici('file', 'file') is True and m._ici('FILE', 'file') is True and m._ici('FiLe', 'file') is True
    assert m._ici('files', 'file') is False and m._ici('fil', 'file') is False and m._ici('fila', 'file') is False
    assert m._ici('fxle', 'file') is False and m._ici('', '') is True
    assert m._ipv4_ok('0.0.0.0') is True and m._ipv4_ok('255.255.255.255') is True
    assert m._ipv4_ok('256.1.1.1') is False and m._ipv4_ok('01.1.1.1') is False
    assert m._ipv4_ok('1.1.1') is False and m._ipv4_ok('1.1.1.1.1') is False
    assert m._path_code('') == 'path-empty' and m._path_code('x') == 'path-slash'
    assert m._host_code('') is None and m._host_code('a' * 256) == 'host-length'
    assert m._drive_split('/c:/x') == ('c', ':', '/x') and m._drive_split('/x/y') == (None, None, '/x/y')


def _o_path(p):
    if len(p) < 1 or p[0] != '/':
        return False
    if len(p) > 1 and p[1] == '/':
        return False
    return re.fullmatch(r'(?:[A-Za-z0-9._~!$&\'()*+,;=:@/-]|%[0-9A-Fa-f]{2})+', p) is not None


def _o_host(h):
    if len(h) > 255:
        return False
    if h == '':
        return True
    if h[0] == '[':
        return len(h) > 2 and h[-1] == ']' and all(ord(c) < 128 and c not in '[]' for c in h[1:-1])
    return re.fullmatch(r'(?:[A-Za-z0-9._~!$&\'()*+,;=-]|%[0-9A-Fa-f]{2})*', h) is not None


def _o_uri(t):
    if t == '' or len(t) > 1024 or len(t) < 5:
        return False
    if t[:4].lower() != 'file' or t[4] != ':':
        return False
    rest = t[5:]
    if rest[:2] == '//':
        tail = rest[2:]
        i = tail.find('/')
        if i < 0:
            return False
        auth, path = tail[:i], tail[i:]
        if len(auth) > 255 or not _o_host(auth):
            return False
    else:
        path = rest
    return _o_path(path)


def test_uri_oracle_differential():
    rng = random.Random(8089)
    alpha = ['f', 'i', 'l', 'e', 'F', 'E', ':', '/', 'a', '1', '%', '4', 'G', '.', '-', '~', '!', '@', ']', '[', ' ', '\u00e9', '|', '$', "'"]
    cases = ['', 'f', 'file', 'file:', 'file:/', 'file://', 'file:///', 'file://a/', 'file:///a', 'FILE:/a', 'filex/a', 'file:a', 'file:/a', 'file://a', 'file://a/b', 'file://localhost/', 'file:////h/x', 'file:/a//b', 'file:/a b', 'file:/a%20b', 'file:/a%2', 'file:/a|b', 'file://h]st/x', 'file://h st/x', 'file://[v1.x]/a', 'file://[]/a', 'file://[/a', 'file://' + 'a' * 256 + '/x', 'file:/' + 'a' * 1018, 'file:/' + 'a' * 1019]
    for _ in range(5000):
        cases.append(''.join(rng.choice(alpha) for _ in range(rng.randrange(0, 16))))
    for t in cases:
        assert m.is_file_uri(t) is _o_uri(t), t


def test_split_file_uri_codes_order_and_boundaries():
    err('split_file_uri', 'text-type', None)
    err('split_file_uri', 'text-type', SubStr('file:/a'))
    err('is_file_uri', 'text-type', None)
    err('is_file_uri', 'text-type', True)
    err('is_file_uri', 'text-type', SubStr('file:/a'))
    err('split_file_uri', 'empty', '')
    err('split_file_uri', 'text-length', 'file:/' + 'a' * 1019)
    assert m.is_file_uri('file:/' + 'a' * 1018) is True
    err('split_file_uri', 'short', 'file')
    err('split_file_uri', 'short', 'fil')
    err('split_file_uri', 'scheme', 'http:/a')
    err('split_file_uri', 'scheme-colon', 'filex:/a')
    err('split_file_uri', 'scheme-colon', 'file/a')
    err('split_file_uri', 'path-empty', 'file:')
    err('split_file_uri', 'path-empty', 'file://host')
    err('split_file_uri', 'path-empty', 'file://')
    err('split_file_uri', 'path-empty', 'file://h]st')
    err('split_file_uri', 'path-slash', 'file:a')
    err('split_file_uri', 'path-slash', 'file:c:/p')
    err('split_file_uri', 'path-slash', 'file:c|/p')
    err('split_file_uri', 'path-double-slash', 'file:////h/x')
    err('split_file_uri', 'path-double-slash', 'file://a//b')
    err('split_file_uri', 'path-char', 'file:/a b')
    err('split_file_uri', 'path-char', 'file:/a|b')
    err('split_file_uri', 'path-char', 'file:/ab\x7fc')
    err('split_file_uri', 'path-pc', 'file:/a%2')
    err('split_file_uri', 'path-pc', 'file:/a%2G')
    err('split_file_uri', 'path-pc', 'file:/ab%4G')
    err('split_file_uri', 'path-pc', 'file:/a%2/x')
    err('split_file_uri', 'path-double-slash', 'file:////')
    assert m.split_file_uri('file:/a%39') == (None, '/a%39')
    assert m._hexval('0') == 0 and m._hexval('9') == 9
    assert m._hexval('a') == 10 and m._hexval('f') == 15
    assert m._hexval('A') == 10 and m._hexval('F') == 15
    assert m._hexval('g') is None and m._hexval('G') is None
    assert m._hexval('@') is None and m._hexval('`') is None and m._hexval('/') is None and m._hexval(':') is None
    err('split_file_uri', 'auth-length', 'file://' + 'a' * 256 + '/x')
    assert m.is_file_uri('file://' + 'a' * 255 + '/x') is True
    err('split_file_uri', 'host-char', 'file://h st/x')
    err('split_file_uri', 'host-char', 'file://hhh]st/x')
    err('split_file_uri', 'host-pc', 'file://h%/x')
    err('split_file_uri', 'host-bracket', 'file://[v1.x/a')
    err('split_file_uri', 'host-bracket-empty', 'file://[]/a')
    err('split_file_uri', 'host-bracket-char', 'file://[a[b]/x')
    assert m.split_file_uri('file:///etc/passwd') == ('', '/etc/passwd')
    assert m.split_file_uri('file:/a/b') == (None, '/a/b')
    assert m.split_file_uri('file://EXAMPLE.com/x') == ('EXAMPLE.com', '/x')
    assert m.split_file_uri('FILE:/a') == (None, '/a')
    assert m.split_file_uri('file://h/%7E') == ('h', '/%7E')
    assert m.split_file_uri('file:/a@b:c') == (None, '/a@b:c')
    assert m.split_file_uri("file:/a!$&'()*+,;=b") == (None, "/a!$&'()*+,;=b")
    assert m.is_file_uri("file://a!$&'()*+,;=b/x") is True
    assert m.split_file_uri("file://a!$&'()*+,;=b/x") == ("a!$&'()*+,;=b", "/x")
    assert m.split_file_uri('file:///c:/p') == ('', '/c:/p')
    assert m.split_file_uri('file:/') == (None, '/')
    assert m.split_file_uri('file:///') == ('', '/')


def test_is_local_uri_rules():
    err('is_local_uri', 'text-type', None)
    err('is_local_uri', 'scheme', 'http:/a')
    assert m.is_local_uri('file:///x') is True
    assert m.is_local_uri('file:/x') is True
    assert m.is_local_uri('file://localhost/x') is True
    assert m.is_local_uri('file://LOCALHOST/x') is True
    assert m.is_local_uri('file://LocalHost/x') is True
    assert m.is_local_uri('file://localhosts/x') is False
    assert m.is_local_uri('file://localhost./x') is False
    assert m.is_local_uri('file://example.com/x') is False
    assert m.is_local_uri('file://192.168.0.1/x') is False
    assert m.is_local_uri('file://[v1]/x') is False


def test_host_kind_rules():
    err('host_kind', 'text-type', None)
    err('host_kind', 'host-length', 'a' * 256)
    assert m.host_kind('1.2.3.a') == 'reg-name'
    assert m.host_kind('1.2.3.4a') == 'reg-name'
    err('host_kind', 'host-char', '1.2.3.:')
    assert m.host_kind('h%39') == 'reg-name'
    assert m.host_kind('[X]') == 'literal'
    assert m.host_kind('[\x7f]') == 'literal'
    err('host_kind', 'host-bracket-char', '[\x80]')
    assert m.host_kind('a' * 255) == 'reg-name'
    assert m.host_kind('') == 'reg-name'
    assert m.host_kind('example.com') == 'reg-name'
    assert m.host_kind('EX-AMPLE.com') == 'reg-name'
    assert m.host_kind('192.168.0.1') == 'ipv4'
    assert m.host_kind('0.0.0.0') == 'ipv4'
    assert m.host_kind('255.255.255.255') == 'ipv4'
    assert m.host_kind('256.1.1.1') == 'reg-name'
    assert m.host_kind('1.2.3.256') == 'reg-name'
    assert m.host_kind('01.2.3.4') == 'reg-name'
    assert m.host_kind('1.2.3') == 'reg-name'
    assert m.host_kind('1.2.3.4.5') == 'reg-name'
    assert m.host_kind('1.2.3.') == 'reg-name'
    assert m.host_kind('%41') == 'reg-name'
    assert m.host_kind('[fe80::1]') == 'literal'
    assert m.host_kind('[v6future]') == 'literal'
    err('host_kind', 'host-bracket', '[abc')
    err('host_kind', 'host-bracket-empty', '[]')
    err('host_kind', 'host-bracket-char', '[a]b]')
    err('host_kind', 'host-bracket-char', '[\u00e9]')
    err('host_kind', 'host-char', 'h h')
    err('host_kind', 'host-char', 'user@host')
    err('host_kind', 'host-pc', 'h%4')
    err('host_kind', 'host-pc', 'h%4G')
    assert m.host_kind('h%41') == 'reg-name'
    err('host_kind', 'host-char', 'a\x7f')
    err('host_kind', 'host-char', 'a\x80')


def test_split_drive_and_drive_uri():
    assert m._letter('a') and m._letter('z') and m._letter('A') and m._letter('Z')
    assert not m._letter('`') and not m._letter('@') and not m._letter('{') and not m._letter('[')
    assert m._digit('0') and m._digit('9') and not m._digit(':') and not m._digit('/')
    err('split_drive', 'text-type', None)
    err('split_drive', 'path-short', '')
    err('split_drive', 'path-short', '/c')
    err('split_drive', 'path-slash', 'c:/x')
    err('split_drive', 'drive-letter', '/1:/x')
    err('split_drive', 'drive-letter', '/::/x')
    err('split_drive', 'drive-letter', '/`:/x')
    err('split_drive', 'drive-letter', '/@:/x')
    assert m.split_drive('/A:/x') == ('A', ':', '/x')
    assert m.split_drive('/Z:/x') == ('Z', ':', '/x')
    assert m._drive_split('c:') == ('c', ':', None)
    assert m._drive_split('c|x') == ('c', '|', None)
    assert m._drive_split('/c:x') == (None, None, '/c:x')
    assert m._drive_split('/a|b/c') == (None, None, '/a|b/c')
    err('split_drive', 'drive-colon', '/ca/x')
    err('split_drive', 'drive-colon', '/c%/x')
    err('split_drive', 'drive-rest', '/c:')
    err('split_drive', 'drive-rest', '/c:x')
    err('split_drive', 'drive-rest', '/c|')
    assert m.split_drive('/c:/x') == ('c', ':', '/x')
    assert m.split_drive('/c:/') == ('c', ':', '/')
    assert m.split_drive('/C|/x') == ('C', '|', '/x')
    assert m.split_drive('/z:/') == ('z', ':', '/')
    err('split_drive_uri', 'text-type', None)
    err('split_drive_uri', 'empty', '')
    err('split_drive_uri', 'short', 'fil')
    err('normalize_pipe', 'short', 'fil')
    assert m.is_drive_uri('file:/' + 'a' * 1018) is True
    assert m.split_drive_uri('file://' + 'a' * 255 + '/c:/p') == ('a' * 255, 'c', ':', '/p')
    err('split_drive_uri', 'scheme', 'http:c:/p')
    err('split_drive_uri', 'scheme-colon', 'filex/a')
    err('normalize_pipe', 'scheme-colon', 'filex/a')
    assert m.is_drive_uri('filex/a') is False
    err('split_drive_uri', 'path-empty', 'file:')
    err('normalize_pipe', 'path-empty', 'file:')
    assert m.is_drive_uri('file:') is False
    err('split_drive_uri', 'path-empty', 'file://a')
    err('normalize_pipe', 'path-empty', 'file://a')
    err('split_drive_uri', 'auth-length', 'file://' + 'a' * 256 + '/c:/p')
    err('split_drive_uri', 'host-char', 'file://h st/c:/p')
    err('normalize_pipe', 'host-char', 'file://h st/c:/p')
    err('split_drive_uri', 'drive-rest', 'file:/c:')
    err('split_drive_uri', 'path-char', 'file:/a|b')
    err('normalize_pipe', 'path-char', 'file:/a|b')
    assert m.split_drive_uri('file:/c:x') == (None, None, None, '/c:x')
    assert m.is_drive_uri('file:/c:x') is True
    assert m.split_drive_uri('file:c:/p') == (None, 'c', ':', '/p')
    assert m.split_drive_uri('file:c|/p') == (None, 'c', '|', '/p')
    assert m.split_drive_uri('file:/c|/p') == (None, 'c', '|', '/p')
    assert m.split_drive_uri('file:///c|/p') == ('', 'c', '|', '/p')
    assert m.split_drive_uri('file://h/c|/p') == ('h', 'c', '|', '/p')
    assert m.split_drive_uri('file:/c:/p') == (None, 'c', ':', '/p')
    assert m.split_drive_uri('file:/x/y') == (None, None, None, '/x/y')
    assert m.split_drive_uri('file:///x') == ('', None, None, '/x')
    assert m.split_drive_uri('file:c:/') == (None, 'c', ':', '/')
    assert m.split_drive_uri('file://LOCALHOST/c:/x') == ('LOCALHOST', 'c', ':', '/x')
    err('split_drive_uri', 'drive-rest', 'file:c:')
    err('split_drive_uri', 'drive-rest', 'file:c:x')
    err('split_drive_uri', 'path-slash', 'file:x')
    err('split_drive_uri', 'path-char', 'file:/a|b/c')
    assert m.is_drive_uri('file:c:/p') is True
    assert m.is_drive_uri('file:/a') is True
    assert m.is_drive_uri('file:/a|b') is False
    err('is_drive_uri', 'text-type', SubStr('file:c:/p'))
    err('is_drive_uri', 'text-type', None)


def test_normalize_pipe():
    err('normalize_pipe', 'text-type', None)
    err('normalize_pipe', 'scheme', 'http:/a')
    err('normalize_pipe', 'path-char', 'file:/a|b/c')
    assert m.normalize_pipe('file:///c|/p') == 'file:///c:/p'
    assert m.normalize_pipe('file:/c|/p') == 'file:/c:/p'
    assert m.normalize_pipe('file:c|/p') == 'file:c:/p'
    assert m.normalize_pipe('file://h/c|/p') == 'file://h/c:/p'
    assert m.normalize_pipe('file://LOCALHOST/c|/x') == 'file://LOCALHOST/c:/x'
    assert m.normalize_pipe('file:c:/p') == 'file:c:/p'
    assert m.normalize_pipe('file:/a/b') == 'file:/a/b'
    assert m.normalize_pipe('FILE:C|/P') == 'FILE:C:/P'
    assert m.normalize_pipe('FILE:///c|/x') == 'FILE:///c:/x'
    assert m.normalize_pipe('File://H/c|/x') == 'File://H/c:/x'
    assert m.normalize_pipe('fILE:/C|/P') == 'fILE:/C:/P'
    for t in ('file:///c|/p', 'file:/c|/p', 'file://h/c|/p'):
        once = m.normalize_pipe(t)
        assert m.is_file_uri(once) is True
        assert m.normalize_pipe(once) == once
        assert m.split_drive(m.split_file_uri(once)[1]) == ('c', ':', '/p')
    once = m.normalize_pipe('file:c|/p')
    assert m.is_drive_uri(once) is True
    assert m.normalize_pipe(once) == once
    assert m.split_drive_uri(once)[1:] == ('c', ':', '/p')
def _run_everything():
    uris = ['', 'f', 'file', 'file:', 'file:/', 'file://', 'file:///', 'file:///a', 'file:/a', 'FILE:/a', 'filex/a', 'file:a', 'file://a', 'file://a/b', 'file://localhost/', 'file://LOCALHOST/x', 'file:////h/x', 'file:/a//b', 'file:/a b', 'file:/a%20b', 'file:/a%2', 'file:/a%2G', 'file:/a|b', 'file://h]st/x', 'file://[v1.x]/a', 'file://[]/a', 'file://[/a', 'file://h%/x', 'file://h%41/x', 'file://h%4A/x', 'file://h%4a/x', 'http:/a', 'file://' + 'a' * 256 + '/x', 'file:/c:/p', 'file:///c:/p', 'file:/\u00e9', None, SubStr('file:/a'), True, 'x' * 1025]
    for t2 in uris:
        for fn in (m.is_file_uri, m.split_file_uri, m.is_local_uri):
            try:
                fn(t2)
            except ValueError:
                pass
    hosts = ['', 'a', 'example.com', '192.168.0.1', '0.0.0.0', '255.255.255.255', '256.1.1.1', '01.2.3.4', '1.2.3', '1.2.3.4.5', '1..2.3', '1234.1.1.1', '1.2.3.a', '[fe80::1]', '[v]', '[]', '[a', '[a]b]', 'h h', 'user@host', 'h%41', 'h%4', 'h%4G', 'a' * 255, 'a' * 256, '\u00e9', None, SubStr('a'), True]
    for t2 in hosts:
        try:
            m.host_kind(t2)
        except ValueError:
            pass
    paths = ['', '/c', 'c:/x', '/1:/x', '/::/x', '/ca/x', '/c%/x', '/c:', '/c:x', '/c|', '/c:/x', '/c:/', '/C|/x', '/z:/', None, SubStr('/c:/x'), True]
    for t2 in paths:
        try:
            m.split_drive(t2)
        except ValueError:
            pass
    dus = ['', 'file', 'filex/a', 'file://host', 'file://h st/c:/p', 'file://' + 'a' * 256 + '/c:/p', 'x' * 1025, 'file:c:/p', 'file:c|/p', 'file:/c|/p', 'file:///c|/p', 'file://h/c|/p', 'file:/c:/p', 'file:/x/y', 'file:c:', 'file:c:x', 'file:x', 'file:/a|b/c', 'file://LOCALHOST/c:/x', 'http:c:/p', None, SubStr('file:c:/p'), True]
    for t2 in dus:
        for fn in (m.split_drive_uri, m.is_drive_uri, m.normalize_pipe):
            try:
                fn(t2)
            except ValueError:
                pass
    assert m.split_file_uri('file:///etc/passwd') == ('', '/etc/passwd')
    assert m.is_local_uri('file://localhost/x') is True
    assert m.host_kind('192.168.0.1') == 'ipv4' and m.host_kind('[v]') == 'literal'
    assert m.split_drive('/c:/x') == ('c', ':', '/x')
    assert m.split_drive_uri('file:c|/p') == (None, 'c', '|', '/p')
    assert m.normalize_pipe('file:c|/p') == 'file:c:/p'
    assert m._ici('FILE', 'file') is True and m._ipv4_ok('1.2.3.4') is True
    assert m._path_code('') == 'path-empty' and m._host_code('') is None
    assert m._drive_split('/c:/x') == ('c', ':', '/x') and m._drive_uri_code('file:/a')[0] is None


def _no_import_hook(*a, **k):
    raise AssertionError('import during call: %r' % (a[:1],))


def _load(name='fresh_1240'):
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
        if globals is not None and globals.get('__name__') == 'fresh_1240':
            log.append((name, tuple(fromlist or ()), level))
        return real(name, globals, locals, fromlist, level)

    calls = []
    real_fs = importlib.util.find_spec
    importlib.util.find_spec = fs if fs is not None else (lambda n, *a, **k: calls.append(n) or real_fs(n, *a, **k))
    builtins.__import__ = spy
    try:
        mod = _load()
    finally:
        builtins.__import__ = real
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
            mod.is_file_uri(None)
        assert str(e.value) == 'P235:is_file_uri:text-type'
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
            mod.is_file_uri(1)
        assert str(e.value) == 'X:is_file_uri:text-type'
    finally:
        if saved == 'absent':
            sys.modules.pop(REG, None)
        else:
            sys.modules[REG] = saved


def test_no_import_on_any_call_path():
    real = builtins.__import__
    builtins.__import__ = _no_import_hook
    try:
        _run_everything()
        assert m.split_file_uri('file:///etc/passwd') == ('', '/etc/passwd')
        assert m.is_local_uri('file://localhost/x') is True
    finally:
        builtins.__import__ = real


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

    builtins.__import__ = _no_import_hook
    sys.settrace(tracer)
    try:
        _run_everything()
        assert m.split_file_uri('file:///etc/passwd') == ('', '/etc/passwd')
        assert m.is_local_uri('file://localhost/x') is True
        assert m.host_kind('192.168.0.1') == 'ipv4' and m.host_kind('a') == 'reg-name'
        assert m.split_drive('/c:/x') == ('c', ':', '/x') and m.normalize_pipe('file:c|/p') == 'file:c:/p'
    finally:
        sys.settrace(None)
        builtins.__import__ = real
    missing = []
    for name, lines in want.items():
        for ln in sorted(lines):
            if (name, ln) not in hit:
                missing.append((name, ln))
    assert missing == []
    assert set(want) == {'_text', '_letter', '_digit', '_unres', '_iei', '_ici', '_hexval', '_pchar', '_path_code', '_host_code', '_ipv4_ok', '_uri_code', '_drive_split', '_drive_uri_code', 'is_file_uri', 'split_file_uri', 'is_local_uri', 'host_kind', 'split_drive', 'split_drive_uri', 'is_drive_uri', 'normalize_pipe'}


STATIC_CODES = {'_text': ['text-type'], 'split_file_uri': ['<code>'], 'is_local_uri': ['<code>'], 'host_kind': ['<hcode>'], 'split_drive': ['path-short', 'path-slash', 'drive-letter', 'drive-colon', 'drive-rest'], 'split_drive_uri': ['<code>'], 'normalize_pipe': ['<code>']}


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
    assert sum(len(v) for v in got.values()) == 11


def test_cap_before_work_tracemalloc_pins():
    import tracemalloc
    n = 2000000
    big = 'a' * n
    big_e = '\u00e9' * n
    cases = (('split_file_uri', (big,), 'text-length'), ('split_file_uri', (big_e,), 'text-length'), ('is_local_uri', (big,), 'text-length'), ('host_kind', (big,), 'host-length'), ('split_drive_uri', (big,), 'text-length'), ('normalize_pipe', (big,), 'text-length'), ('split_drive', ('/',), 'path-short'))
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
    tracemalloc.start()
    try:
        assert m.is_file_uri(big) is False and m.is_drive_uri(big) is False and m.is_file_uri(big_e) is False
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 20000, peak


DOC = 'b1240 RFC 8089 section 2: file URI scheme syntax, with drive letters.\n\nSource: RFC 8089 (Kerwin, February 2017), section 2 (Syntax), importing\nthe host and path-absolute rules from the URI syntax, plus the drive\nletter material from appendix E. The grammar is \'file-URI = file-scheme\n":" file-hier-part\' with file-scheme the case-insensitive literal file,\n\'file-hier-part = ( "//" auth-path ) / local-path\', \'auth-path =\n[ file-auth ] path-absolute\', \'local-path = path-absolute\' and\n\'file-auth = "localhost" / host\'. The authority special case: the string\nlocalhost is interpreted "exactly as if no authority were present." On\ncase: "Any transport-related handling of the file URI scheme MUST retain\nthe case as given." The path rule is "the absolute path to the file in\nthe file system." Appendix E variations "are not supported by the\nnormative syntax of Section 2"; the implemented nonstandard forms are the\nE.2 rule \'local-path = [ drive-letter ] path-absolute\' and the E.2.2\nrules \'file-absolute = "/" drive-letter path-absolute\' and \'drive-letter\n= ALPHA ":" / ALPHA "|"\', and "Note that comparison of drive letters in\nDOS or Windows file paths is case insensitive." The pipe form is updated\nto the colon form per E.2.2.\nErrata: one exists for RFC 8089 in the errata data used: 6501 (Reported,\nEditorial, section 6) concerns the IANA registration template, which is\noutside the implemented section 2; not applied.\nOURS design choices (not sourced from the RFC): TEXT_MAX, AUTH_MAX and\nHOST_MAX are implementation bounds; the RFC sets no length limits. A\nbracketed authority literal is an opaque token here (nonempty, ASCII, no\nnested brackets); its content is validated by the IPv6 sibling modules\nand is NOT implemented. host_kind classifies first-match-wins into\nliteral, ipv4 or reg-name. When a first path segment is exactly a drive\nletter, split_drive_uri prefers the drive reading over the plain path\nreading. The E.1 userinfo authority and the E.3 UNC forms are NOT\nimplemented. The P235 error codes and their check order are ours.\nSOURCED: the file scheme and hierarchy grammar, the localhost special\ncase, the case retention rule, the path-absolute structure, the pchar\ncharacter set (the 66 unreserved characters, the 11 sub-delims, the colon\nand the at-sign), pct-encoded triplets, the host alternatives with\ndec-octet IPv4 validation (no leading zeros, each octet at most 255), the\nempty reg-name, and the appendix E drive letter rules named above.\nErrors raise ValueError P235:<name>:<code>.\n'


def test_whole_module_docstring_literal_and_ascii():
    assert m.__doc__ == DOC
    for p in (MODPATH, __file__):
        with open(p, 'rb') as fh:
            assert fh.read().isascii()
    assert '\\' not in m.__doc__
    assert 'one exists for RFC 8089' in m.__doc__
    assert '6501' in m.__doc__ and 'E.2.2' in m.__doc__ and 'drive-letter' in m.__doc__
    assert 'TEXT_MAX' in m.__doc__ and 'not applied' in m.__doc__
    assert 'OURS' in m.__doc__ and 'SOURCED' in m.__doc__
