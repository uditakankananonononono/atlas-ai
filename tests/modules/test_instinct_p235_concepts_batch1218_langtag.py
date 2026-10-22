import ast
import builtins
import contextlib
import importlib
import importlib.util
import itertools
import json
import os
import random
import re
import signal
import subprocess
import sys
import urllib.request

import pytest

from app.modules.instinct_doc import p235_concepts_batch1218_langtag as m
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


REG = 'app.modules.instinct_doc.p235_concepts_registry'
STUB_WORLD = importlib.util.find_spec(REG) is not None
PFX = 'STUB:' if STUB_WORLD else 'P235:'
SRC_PATH = m.__file__
FNS = ('language_tag_ok', 'parse_language_tag', 'format_language_tag')
KEYS = ('kind', 'language', 'extlangs', 'script', 'region', 'variants', 'extensions', 'privateuse', 'grandfathered')
ALPHA = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
DIGIT = '0123456789'
IRREGULAR = ('en-GB-oed', 'i-ami', 'i-bnn', 'i-default', 'i-enochian', 'i-hak', 'i-klingon', 'i-lux', 'i-mingo', 'i-navajo', 'i-pwn', 'i-tao', 'i-tay', 'i-tsu', 'sgn-BE-FR', 'sgn-BE-NL', 'sgn-CH-DE')
REGULAR = ('art-lojban', 'cel-gaulish', 'no-bok', 'no-nyn', 'zh-guoyu', 'zh-hakka', 'zh-min', 'zh-min-nan', 'zh-xiang')


class StrSub(str):
    pass


class EqStr(str):
    def __eq__(self, other):
        return True

    def __hash__(self):
        return 1


class Meta(type):
    def __eq__(cls, other):
        return True

    def __hash__(cls):
        return 7


class MetaStr(str, metaclass=Meta):
    pass


class TupSub(tuple):
    pass


class DictSub(dict):
    pass


class EqTup(tuple):
    def __eq__(self, other):
        return True

    def __hash__(self):
        return 2


HOSTILE_STR = (StrSub('en'), EqStr('en'), MetaStr('en'))


def err(fn, *args):
    try:
        fn(*args)
    except ValueError as e:
        return str(e)
    return None


def fe(fn, code):
    return '%s%s:%s' % (PFX, fn, code)


# Independent oracle: the section 2.1 ABNF written as one regular expression (ASCII, case-insensitive).
_AN = '[A-Za-z0-9]'
_LANG = '(?P<language>(?:[A-Za-z]{2,3}(?P<extlang>(?:-[A-Za-z]{3}){0,3})|[A-Za-z]{4}|[A-Za-z]{5,8}))'
_REGEX = (
    '(?:' + _LANG
    + '(?:-(?P<script>[A-Za-z]{4}))?'
    + '(?:-(?P<region>[A-Za-z]{2}|[0-9]{3}))?'
    + '(?P<variants>(?:-(?:' + _AN + '{5,8}|[0-9]' + _AN + '{3}))*)'
    + '(?P<extensions>(?:-[0-9A-WY-Za-wy-z](?:-' + _AN + '{2,8})+)*)'
    + '(?:-[xX](?P<privateuse>(?:-' + _AN + '{1,8})+))?'
    + '|[xX](?P<privateonly>(?:-' + _AN + '{1,8})+)'
    + '|(?P<grand>' + '|'.join(re.escape(g) for g in IRREGULAR + REGULAR) + '))'
)
ORACLE = re.compile(_REGEX, re.ASCII | re.IGNORECASE)


def oracle_ok(tag):
    return ORACLE.fullmatch(tag) is not None


def _split(s):
    return tuple(p for p in s.split('-') if p != '') if s else ()


def oracle_parse(tag):
    """Fields by the regex oracle, or None. Grandfathered tags take precedence (section 2.1.1 list)."""
    mt = ORACLE.fullmatch(tag)
    if mt is None:
        return None
    low = tag.lower()
    gf = [g for g in IRREGULAR + REGULAR if g.lower() == low]
    ext = ()
    exts = []
    if mt.group('extensions'):
        cur = None
        for part in mt.group('extensions').split('-')[1:]:
            if len(part) == 1:
                cur = [part, []]
                exts.append(cur)
            else:
                cur[1].append(part)
    ext = tuple((a, tuple(b)) for a, b in exts)
    if gf and gf[0] in IRREGULAR:
        return {'kind': 'irregular', 'language': None, 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': (), 'grandfathered': gf[0]}
    if mt.group('privateonly') is not None:
        return {'kind': 'privateuse', 'language': None, 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': _split(mt.group('privateonly')), 'grandfathered': None}
    lang = mt.group('language')
    el = mt.group('extlang') or ''
    return {'kind': 'regular' if gf else 'langtag', 'language': lang[:len(lang) - len(el)], 'extlangs': _split(el), 'script': mt.group('script'), 'region': mt.group('region'), 'variants': _split(mt.group('variants')), 'extensions': ext, 'privateuse': _split(mt.group('privateuse')), 'grandfathered': gf[0] if gf else None}


def conv_case(p):
    """Independent section 2.1.1 convention-case rendering of a parse-shaped dict."""
    if p['kind'] == 'irregular':
        return p['grandfathered']
    if p['kind'] == 'privateuse':
        return '-'.join(['x'] + [s.lower() for s in p['privateuse']])
    out = [p['language'].lower()] + [s.lower() for s in p['extlangs']]
    if p['script'] is not None:
        out.append(p['script'][0].upper() + p['script'][1:].lower())
    if p['region'] is not None:
        out.append(p['region'].upper())
    out += [s.lower() for s in p['variants']]
    for single, body in p['extensions']:
        out.append(single.lower())
        out += [s.lower() for s in body]
    if p['privateuse']:
        out.append('x')
        out += [s.lower() for s in p['privateuse']]
    return '-'.join(out)


def exact(a, b):
    assert type(a) is type(b), (a, b)
    if type(b) in (list, tuple):
        assert len(a) == len(b), (a, b)
        for x, y in zip(a, b):
            exact(x, y)
    elif type(b) is dict:
        assert list(a) == list(b), (a, b)
        for k in b:
            exact(a[k], b[k])
    else:
        assert a == b, (a, b)


def P(**kw):
    d = {'kind': 'langtag', 'language': 'en', 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': (), 'grandfathered': None}
    d.update(kw)
    return d


@pytest.fixture(autouse=True)
def _env_guard():
    """Fail a test that leaves the language-tag module state, sys.modules or the import hook changed."""
    before_mod = (m.CLAIMS, m.MAX_TAG, m._GRAND['i-ami'], len(m._GRAND))
    before_imp = builtins.__import__
    before_path = list(sys.path)
    yield
    assert builtins.__import__ == before_imp
    assert sys.path == before_path
    assert (m.CLAIMS, m.MAX_TAG, m._GRAND['i-ami'], len(m._GRAND)) == before_mod


@pytest.fixture(autouse=True)
def _per_test_time_limit(request):
    """A mutant that loops forever or crawls must fail the suite, not hang it: raise in the test after the wall-time budget."""
    limit = 25 if 'slow' in request.node.name else 5

    def _h(signum, frame):
        raise AssertionError('test exceeded %d s' % limit)
    old = signal.signal(signal.SIGALRM, _h)
    signal.setitimer(signal.ITIMER_REAL, limit)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


# ---------------------------------------------------------------- corpora
def _cands():
    return ['en', 'e', 'eng', 'engl', 'abcde', 'abcdefgh', 'abcdefghi', 'abc', 'abcd', 'Latn', '12', 'ab', 'AB', '123', '1234', '12345', 'a1b2', '1abc', 'a', 'x', 'X', '7', 'ab12', '', '1', 'ab-c']


def _corpus_tags(depth=4):
    c = _cands()
    seen = set()
    for n in range(1, depth + 1):
        for t in itertools.product(c, repeat=n):
            s = '-'.join(t)
            if s not in seen:
                seen.add(s)
                yield s


def _random_tags(n, seed):
    r = random.Random(seed)
    parts = ['en', 'zh', 'sgn', 'i', 'x', 'X', 'abc', 'Hant', 'hant', 'US', 'us', '419', '1996', '1901', 'rozaj', 'biske', 'a', 'b', 'y', 'z', '9', 'ab', 'ext1', 'abcdefgh', 'abcdefghi', 'oed', 'GB', 'min', 'nan', 'lojban', 'art', 'BE', 'FR', '', 'a1', '12345678', 'q']
    for _ in range(n):
        yield '-'.join(r.choice(parts) for _ in range(r.randint(1, 9)))


SPECIAL = ['', '-', '--', 'en-', '-en', 'en--US', 'en-US-', ' en', 'en ', 'en US', 'en\n', 'en-US\n', '\nen', 'en\x00', 'en_US', 'en.US', 'en-\u00fc', '\u212a-en', 'k\u212a', 'en-\u0661\u0662\u0663', 'en-\u0131', 'en-\u017f', '\uff45\uff4e', 'EN-us', 'eN-lAtN-uS', 'e\u0301n', 'en-US\u00a0', 'en-US\t', 'en-\ud800'.encode('utf-8', 'surrogatepass').decode('utf-8', 'surrogatepass')]


# ---------------------------------------------------------------- tests
def test_oracle_regex_is_the_abnf_and_matches_every_example_of_section_2_1():
    good = ['de', 'fr', 'ja', 'zh-Hant', 'zh-Hans', 'sr-Cyrl', 'sr-Latn', 'zh-cmn-Hans-CN', 'cmn-Hans-CN', 'zh-yue-HK', 'yue-HK', 'zh-Hans-CN', 'sr-Latn-RS', 'sl-rozaj', 'sl-rozaj-biske', 'sl-nedis', 'de-CH-1901', 'sl-IT-nedis', 'hy-Latn-IT-arevela', 'de-DE', 'en-US', 'es-419', 'de-CH-x-phonebk', 'az-Arab-x-AZE-derbend', 'x-whatever', 'qaa-Qaaa-QM-x-southern', 'de-Qaaa', 'sr-Latn-QM', 'sr-Qaaa-RS', 'en-US-u-islamcal', 'zh-CN-a-myext-x-private', 'en-a-myext-b-another', 'i-klingon', 'sgn-BE-FR', 'en-GB-oed', 'zh-min-nan']
    assert len(good) == 36
    for t in good:
        assert oracle_ok(t), t
        assert m.language_tag_ok(t) is True, t
    bad = ['de-419-DE', 'a-DE', 'ar-a-aaa-b-bbb-a-ccc']
    assert len(bad) == 3
    assert oracle_ok('ar-a-aaa-b-bbb-a-ccc') is True
    for t in ('de-419-DE', 'a-DE'):
        assert oracle_ok(t) is False and m.language_tag_ok(t) is False, t
    assert m.language_tag_ok('ar-a-aaa-b-bbb-a-ccc') is True


def test_language_tag_ok_matches_the_abnf_oracle_on_the_exhaustive_small_corpus_slow():
    n = 0
    for tag in _corpus_tags():
        n += 1
        assert m.language_tag_ok(tag) is oracle_ok(tag), tag
    assert n > 60000


def test_language_tag_ok_matches_the_oracle_on_random_and_special_tags_slow():
    n = 0
    for tag in list(_random_tags(40000, 3)) + SPECIAL:
        n += 1
        assert m.language_tag_ok(tag) is oracle_ok(tag), repr(tag)
    assert n > 40000


def test_parse_matches_the_oracle_fields_exactly_slow():
    n = ok = 0
    for tag in itertools.chain(_corpus_tags(3), _random_tags(20000, 5), SPECIAL):
        n += 1
        want = oracle_parse(tag)
        if want is None:
            assert err(m.parse_language_tag, tag) == fe('parse_language_tag', 'bad_value:tag.syntax'), repr(tag)
        else:
            ok += 1
            exact(m.parse_language_tag(tag), want)
    assert n > 20000 and ok > 2000


def test_format_equals_the_convention_case_oracle_and_round_trips_through_parse_slow():
    n = 0
    for tag in itertools.chain(_corpus_tags(3), _random_tags(8000, 7)):
        want = oracle_parse(tag)
        if want is None:
            continue
        n += 1
        p = m.parse_language_tag(tag)
        text = m.format_language_tag(p)
        assert type(text) is str and text == conv_case(want), tag
        assert text.lower() == tag.lower()
        q = m.parse_language_tag(text)
        exact(q, oracle_parse(text))
        assert m.format_language_tag(q) == text
    assert n > 5000


def test_the_26_grandfathered_tags_in_any_case_and_their_kinds():
    assert len(IRREGULAR) == 17 and len(REGULAR) == 9
    for g in IRREGULAR + REGULAR:
        for variant in (g, g.lower(), g.upper(), g.swapcase(), g.title()):
            p = m.parse_language_tag(variant)
            assert p['kind'] == ('irregular' if g in IRREGULAR else 'regular'), variant
            assert p['grandfathered'] == g
            assert m.format_language_tag(p) == g
            assert m.language_tag_ok(variant) is True
    p = m.parse_language_tag('ZH-Min-NAN')
    exact(p, {'kind': 'regular', 'language': 'ZH', 'extlangs': ('Min', 'NAN'), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': (), 'grandfathered': 'zh-min-nan'})
    p = m.parse_language_tag('I-KLINGON')
    exact(p, {'kind': 'irregular', 'language': None, 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': (), 'grandfathered': 'i-klingon'})
    assert m.language_tag_ok('i-klingon-x') is False and m.language_tag_ok('i-ami-x-a') is False and m.language_tag_ok('sgn-BE-FR-x') is False
    assert m.language_tag_ok('art-lojban-x-a') is True and m.parse_language_tag('art-lojban-x-a')['kind'] == 'langtag'


def test_parse_examples_exact_shapes():
    exact(m.parse_language_tag('en'), P())
    exact(m.parse_language_tag('zh-cmn-Hans-CN'), P(language='zh', extlangs=('cmn',), script='Hans', region='CN'))
    exact(m.parse_language_tag('de-CH-1901-x-phonebk'), P(language='de', region='CH', variants=('1901',), privateuse=('phonebk',)))
    exact(m.parse_language_tag('en-US-u-islamcal-a-bb'), P(region='US', extensions=(('u', ('islamcal',)), ('a', ('bb',)))))
    exact(m.parse_language_tag('X-Private-1'), {'kind': 'privateuse', 'language': None, 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': ('Private', '1'), 'grandfathered': None})
    exact(m.parse_language_tag('es-419'), P(language='es', region='419'))
    exact(m.parse_language_tag('sl-rozaj-biske-1994'), P(language='sl', variants=('rozaj', 'biske', '1994')))
    exact(m.parse_language_tag('abcdefgh'), P(language='abcdefgh'))
    exact(m.parse_language_tag('qaa-Qaaa-QM-x-southern'), P(language='qaa', script='Qaaa', region='QM', privateuse=('southern',)))


# ---------------------------------------------------------------- explicit per-position tables (hand written from section 2.1, not from the oracle)
ACCEPT = [
    'ab', 'abc', 'abcd', 'abcde', 'abcdefgh',
    'ab-abc', 'ab-abc-def', 'ab-abc-def-ghi', 'abc-abc', 'abc-abc-def-ghi',
    'ab-Latn', 'abc-Latn', 'abcd-Latn', 'abcdefgh-Latn',
    'ab-US', 'ab-us', 'ab-123', 'ab-Latn-US', 'ab-Latn-123', 'ab-abc-Latn-US',
    'ab-12345', 'ab-abcde', 'ab-abcdefgh', 'ab-1abc', 'ab-1234', 'ab-12345678', 'ab-US-12345', 'ab-US-1abc', 'ab-Latn-US-abcde-1abc',
    'ab-a-bb', 'ab-a-bbbbbbbb', 'ab-a-bb-cc', 'ab-0-bb', 'ab-9-bb', 'ab-w-bb', 'ab-y-bb', 'ab-z-bb', 'ab-W-bb', 'ab-Y-bb', 'ab-Z-bb', 'ab-a-bb-c-dd',
    'ab-US-a-bb', 'ab-a-bb-x-c',
    'ab-Lat', 'ab-Latni', 'ab-US-123a', 'ab-x-bb-a-cc', 'ab-a-bb-US', 'ab-a-bb-12345', 'ab-x-a-x-b', 'sgn-BE',
    'x-a', 'X-a', 'x-abcdefgh', 'x-a-b', 'x-1', 'ab-x-a', 'ab-x-abcdefgh', 'ab-x-a-b-c', 'ab-US-x-a',
]
REFUSE = [
    '', 'a', 'x', 'X', 'a-US', 'abcdefghi', 'ab-', '-ab', 'ab--US',
    '12', 'a1', '1a', 'ab-abcd-abcd', 'ab-abc-def-ghi-jkl',
    'abcd-abc', 'abcde-abc', 'abcdefgh-abc',
    'ab-Latn-Latn', 'ab-12', 'ab-1', 'ab-A', 'ab-US-Latn', 'ab-US-US', 'ab-US-123', 'ab-123-US', 'ab-123-123',
    'ab-abc-US-abc', 'ab-1234-US', 'ab-123456789', 'ab-abcdefghi',
    'ab-US-abcd', 'ab-ab12', 'ab-a123',
    'ab-a', 'ab-a-', 'ab-a-b', 'ab-a-bbbbbbbbb', 'ab-a-x', 'ab-a-bb-x', 'ab-a-bb-c', 
    'x-', 'x-abcdefghi', 'x-a-', 'x--a', 'xx-a', 'ab-x', 'ab-x-', 'ab-x-abcdefghi', 'ab-x-a-b-',
    'i', 'i-', 'i-ami-', 'i-unknown', 'en-GB-oe', 'en-GB-oed-x', 'sgn-BE-ES',
    'a-b', 'a-b-c', '-', '--', 'en-US-',
]
EXT_SINGLETONS_OK = ''.join(c for c in ALPHA + DIGIT if c not in 'xX')


def test_explicit_accept_and_refuse_tables():
    assert len(ACCEPT) == 60 and len(REFUSE) == len(set(REFUSE)) and len(set(ACCEPT)) == 60
    assert not set(ACCEPT) & set(REFUSE) and len(REFUSE) == 61
    for t in ACCEPT:
        assert m.language_tag_ok(t) is True, t
        assert m.language_tag_ok(t.upper()) is True and m.language_tag_ok(t.lower()) is True, t
        assert oracle_ok(t) is True, t
    for t in REFUSE:
        assert m.language_tag_ok(t) is False, t
        assert oracle_ok(t) is False, t


def test_every_alphanumeric_singleton_is_an_extension_start_except_x():
    assert len(EXT_SINGLETONS_OK) == 60
    for c in EXT_SINGLETONS_OK:
        assert m.language_tag_ok('en-%s-bb' % c) is True, c
        p = m.parse_language_tag('en-%s-bb' % c)
        assert p['extensions'] == ((c, ('bb',)),) and p['privateuse'] == (), c
    for c in 'xX':
        assert m.language_tag_ok('en-%s-bb' % c) is True
        p = m.parse_language_tag('en-%s-bb' % c)
        assert p['extensions'] == () and p['privateuse'] == ('bb',)
        assert m.language_tag_ok('en-%s' % c) is False
    for c in '-_.~!$&*+=:@/ \t\n\x00\x7f' + '\u00e9\u212a\u0661':
        assert m.language_tag_ok('en-%s-bb' % c) is False, repr(c)


def test_each_character_class_boundary_in_the_ascii_range_is_refused_outside_alnum_and_hyphen():
    ok = set(ALPHA + DIGIT + '-')
    n = 0
    for cp in range(0, 256):
        ch = chr(cp)
        for tag in ('e' + ch, 'en-' + ch + 'US', 'en-US-' + ch + 'a-bb', 'x-' + ch + 'a'):
            n += 1
            want = ch in ok and oracle_ok(tag)
            assert m.language_tag_ok(tag) is want, repr(tag)
    assert n == 1024
    for ch in ('\u212a', '\u017f', '\u0131', '\u0130', '\u0661', '\uff21', '\uff11', '\u00b2', '\u2460', '\u0660'):
        for tag in ('e' + ch, 'en-' + ch + 'US', 'x-a' + ch, 'en-a-b' + ch, 'en-1' + ch + 'bc'):
            assert m.language_tag_ok(tag) is False, repr(tag)
            assert err(m.parse_language_tag, tag) == fe('parse_language_tag', 'bad_value:tag.syntax')
    assert m.language_tag_ok('K\u212a') is False and m.language_tag_ok('\u212a') is False
    assert m.language_tag_ok('i-kl\u0131ngon') is False and m.language_tag_ok('I-K\u212aLINGON') is False


def test_no_trimming_or_case_folding_outside_ascii():
    for t in (' en', 'en ', '\ten', 'en\r', 'en\n', 'en\x0b', 'en\x0c', '\u00a0en', 'en\u2003', 'e n', 'en -US', 'en- US'):
        assert m.language_tag_ok(t) is False, repr(t)
        assert err(m.parse_language_tag, t) == fe('parse_language_tag', 'bad_value:tag.syntax')


# ---------------------------------------------------------------- types and caps at every entry
def test_non_str_tag_is_refused_at_both_tag_entries_with_exact_messages():
    for fn in ('language_tag_ok', 'parse_language_tag'):
        for bad in (None, 1, 1.5, True, b'en', bytearray(b'en'), ['en'], ('en',), {'a': 1}, {1}, object(), type, StrSub('en'), EqStr('en'), MetaStr('en'), StrSub(''), EqStr(''), MetaStr('')):
            assert err(getattr(m, fn), bad) == fe(fn, 'bad_type:tag'), (fn, bad)


def test_hostile_str_never_reaches_the_scan_and_both_bad_order_is_type_then_length_then_syntax():
    for fn in ('language_tag_ok', 'parse_language_tag'):
        big = 'x' * (m.MAX_TAG + 1)
        assert err(getattr(m, fn), StrSub(big)) == fe(fn, 'bad_type:tag')
        assert err(getattr(m, fn), big) == fe(fn, 'bad_value:tag.length')
        assert err(getattr(m, fn), '\u00e9' * (m.MAX_TAG + 1)) == fe(fn, 'bad_value:tag.length')
    assert err(m.parse_language_tag, '\u00e9' * m.MAX_TAG) == fe('parse_language_tag', 'bad_value:tag.syntax')
    assert m.language_tag_ok('\u00e9' * m.MAX_TAG) is False
    assert err(m.language_tag_ok, 'x' * 10 ** 6) == fe('language_tag_ok', 'bad_value:tag.length')


def _tag_of_length(n):
    assert 5 <= n <= 400
    if n % 2 == 1:
        k = (n - 1) // 2
        return 'x' + '-a' * k
    k = (n - 4) // 2
    return 'x' + '-a' * k + '-bb'


def test_tag_cap_255_is_exact_at_254_255_256_257_and_round_trips_through_format():
    assert m.MAX_TAG == 255 and type(m.MAX_TAG) is int
    for n in (253, 254, 255):
        t = _tag_of_length(n)
        assert len(t) == n
        assert m.language_tag_ok(t) is True
        p = m.parse_language_tag(t)
        assert m.format_language_tag(p) == t
        assert m.parse_language_tag(m.format_language_tag(p)) == p
    for n in (256, 257, 258):
        t = _tag_of_length(n)
        assert len(t) == n
        assert err(m.language_tag_ok, t) == fe('language_tag_ok', 'bad_value:tag.length')
        assert err(m.parse_language_tag, t) == fe('parse_language_tag', 'bad_value:tag.length')
    p255 = m.parse_language_tag(_tag_of_length(255))
    over = dict(p255, privateuse=p255['privateuse'] + ('a',))
    assert err(m.format_language_tag, over) == fe('format_language_tag', 'bad_value:tag.length')
    over = dict(p255, privateuse=p255['privateuse'][:-1] + ('bb',))
    assert err(m.format_language_tag, over) == fe('format_language_tag', 'bad_value:tag.length')
    exact(m.parse_language_tag(m.format_language_tag(dict(p255, privateuse=p255['privateuse'][:-2]))), dict(p255, privateuse=p255['privateuse'][:-2]))


def test_tuple_caps_are_checked_before_any_element_for_every_tuple_field():
    f = 'format_language_tag'
    big = ('',) * (m.MAX_TAG + 1)
    edge = ('',) * m.MAX_TAG
    assert err(m.format_language_tag, P(extlangs=big)) == fe(f, 'bad_value:parts.extlangs.length')
    assert err(m.format_language_tag, P(variants=big)) == fe(f, 'bad_value:parts.variants.length')
    assert err(m.format_language_tag, P(extensions=big)) == fe(f, 'bad_value:parts.extensions.length')
    assert err(m.format_language_tag, P(privateuse=big)) == fe(f, 'bad_value:parts.privateuse.length')
    assert err(m.format_language_tag, P(extensions=(('a', big),))) == fe(f, 'bad_value:parts.extensions.length')
    assert err(m.format_language_tag, P(variants=edge)) == fe(f, 'bad_value:parts.variants')
    assert err(m.format_language_tag, P(extensions=edge)) == fe(f, 'bad_type:parts.extensions')
    assert err(m.format_language_tag, P(privateuse=edge)) == fe(f, 'bad_value:parts.privateuse')
    assert err(m.format_language_tag, P(extensions=(('a', edge),))) == fe(f, 'bad_value:parts.extensions')
    assert err(m.format_language_tag, P(extlangs=('abc',) * 4)) == fe(f, 'bad_value:parts.extlangs')
    assert err(m.format_language_tag, P(variants=('abcde',) * 255)) == fe(f, 'bad_value:tag.length')
    assert err(m.format_language_tag, P(privateuse=('a',) * 255)) == fe(f, 'bad_value:tag.length')
    assert err(m.format_language_tag, P(privateuse=('a',) * 126)) == fe(f, 'bad_value:tag.length')
    assert m.format_language_tag(P(privateuse=('a',) * 125)) == 'en-x' + '-a' * 125


def test_format_refuses_non_dict_and_hostile_dicts_and_keys():
    f = 'format_language_tag'
    for bad in (None, 1, 'en', b'', [], (), set(), object(), DictSub(P()), DictSub(), [('kind', 'langtag')]):
        assert err(m.format_language_tag, bad) == fe(f, 'bad_type:parts'), bad
    assert err(m.format_language_tag, {}) == fe(f, 'bad_value:parts.keys')
    d = P()
    e = dict(d)
    del e['script']
    assert err(m.format_language_tag, e) == fe(f, 'bad_value:parts.keys')
    e = dict(d)
    e['extra'] = 1
    assert err(m.format_language_tag, e) == fe(f, 'bad_value:parts.keys')
    e = dict(d)
    del e['script']
    e['scripts'] = None
    assert err(m.format_language_tag, e) == fe(f, 'bad_value:parts.keys')
    for hostile in (StrSub('kind'), EqStr('kind'), MetaStr('kind')):
        e = dict(d)
        del e['kind']
        e[hostile] = 'langtag'
        assert err(m.format_language_tag, e) == fe(f, 'bad_type:parts.key'), hostile
    e = dict(d)
    del e['kind']
    e[1] = 'langtag'
    assert err(m.format_language_tag, e) == fe(f, 'bad_type:parts.key')
    e = dict(d)
    e2 = {k: e[k] for k in reversed(KEYS)}
    assert m.format_language_tag(e2) == 'en'
    assert err(m.format_language_tag, dict(d, extra=1, kind=1)) == fe(f, 'bad_value:parts.keys')


def test_kind_and_grandfathered_field_checks_in_order():
    f = 'format_language_tag'
    for bad in (None, 1, b'langtag', ['langtag'], StrSub('langtag'), EqStr('langtag'), MetaStr('langtag')):
        assert err(m.format_language_tag, P(kind=bad)) == fe(f, 'bad_type:parts.kind'), bad
    for bad in ('', 'Langtag', 'grandfathered', 'langtag ', 'x'):
        assert err(m.format_language_tag, P(kind=bad)) == fe(f, 'bad_value:parts.kind'), bad
    irr = {'kind': 'irregular', 'language': None, 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': (), 'grandfathered': 'i-ami'}
    assert m.format_language_tag(irr) == 'i-ami'
    for bad in (None, 1, b'i-ami', ('i-ami',), StrSub('i-ami'), EqStr('i-ami'), MetaStr('i-ami')):
        assert err(m.format_language_tag, dict(irr, grandfathered=bad)) == fe(f, 'bad_type:parts.grandfathered'), bad
    for bad in ('', 'i-AMI', 'I-ami', 'i-amy', 'zh-min', 'i-ami\n', 'i-\u00e1mi', 'x' * 300, 'i-ami ' + 'x' * 300):
        assert err(m.format_language_tag, dict(irr, grandfathered=bad)) == fe(f, 'bad_value:parts.grandfathered'), bad
    assert m.format_language_tag(dict(irr, grandfathered='en-GB-oed')) == 'en-GB-oed'
    assert err(m.format_language_tag, dict(irr, grandfathered='EN-GB-OED')) == fe(f, 'bad_value:parts.grandfathered')
    for key, bad in (('language', 'en'), ('script', 'Latn'), ('region', 'US')):
        assert err(m.format_language_tag, dict(irr, **{key: bad})) == fe(f, 'bad_value:parts.language'), key
    for key in ('extlangs', 'variants', 'extensions', 'privateuse'):
        assert err(m.format_language_tag, dict(irr, **{key: ['a']})) == fe(f, 'bad_type:parts.' + key), key
        assert err(m.format_language_tag, dict(irr, **{key: TupSub()})) == fe(f, 'bad_type:parts.' + key), key
        assert err(m.format_language_tag, dict(irr, **{key: ('a',)})) == fe(f, 'bad_value:parts.' + key), key
    assert err(m.format_language_tag, dict(irr, language='en', grandfathered='zh-min')) == fe(f, 'bad_value:parts.grandfathered')
    assert err(m.format_language_tag, dict(irr, kind='regular')) == fe(f, 'bad_value:parts.grandfathered')
    assert err(m.format_language_tag, P(grandfathered='zh-min')) == fe(f, 'bad_value:parts.grandfathered')
    assert err(m.format_language_tag, P(grandfathered='')) == fe(f, 'bad_value:parts.grandfathered')
    assert err(m.format_language_tag, P(kind='privateuse', language=None, privateuse=('a',), grandfathered='x')) == fe(f, 'bad_value:parts.grandfathered')


def test_privateuse_kind_fields():
    f = 'format_language_tag'
    pu = {'kind': 'privateuse', 'language': None, 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': ('A', 'bcdefghi'), 'grandfathered': None}
    assert m.format_language_tag(pu) == 'x-a-bcdefghi'
    for key, bad in (('language', 'en'), ('script', 'Latn'), ('region', 'US')):
        assert err(m.format_language_tag, dict(pu, **{key: bad})) == fe(f, 'bad_value:parts.language'), key
    for key in ('extlangs', 'variants', 'extensions'):
        assert err(m.format_language_tag, dict(pu, **{key: ['a']})) == fe(f, 'bad_type:parts.' + key), key
        assert err(m.format_language_tag, dict(pu, **{key: ('a',)})) == fe(f, 'bad_value:parts.' + key), key
    assert err(m.format_language_tag, dict(pu, privateuse=())) == fe(f, 'bad_value:parts.privateuse')
    assert err(m.format_language_tag, dict(pu, privateuse=['a'])) == fe(f, 'bad_type:parts.privateuse')
    assert err(m.format_language_tag, dict(pu, privateuse=TupSub(('a',)))) == fe(f, 'bad_type:parts.privateuse')
    assert err(m.format_language_tag, dict(pu, privateuse=('',))) == fe(f, 'bad_value:parts.privateuse')
    assert err(m.format_language_tag, dict(pu, privateuse=('a', 'abcdefghi'))) == fe(f, 'bad_value:parts.privateuse')
    assert err(m.format_language_tag, dict(pu, privateuse=('a', 1))) == fe(f, 'bad_type:parts.privateuse')
    assert err(m.format_language_tag, dict(pu, privateuse=('a', 'b-c'))) == fe(f, 'bad_value:parts.privateuse')
    for hostile in HOSTILE_STR:
        assert err(m.format_language_tag, dict(pu, privateuse=(hostile,))) == fe(f, 'bad_type:parts.privateuse')
        assert err(m.format_language_tag, dict(pu, privateuse=('a', hostile))) == fe(f, 'bad_type:parts.privateuse')




# ---------------------------------------------------------------- format side: every range, with format-then-parse round trips at lo-1, lo, hi, hi+1
def lowerp(p):
    """Lower-case every string of a parse-shaped dict (tags compare without case)."""
    def low(v):
        if type(v) is str:
            return v.lower()
        if type(v) is tuple:
            return tuple(low(x) for x in v)
        return v
    return {k: low(v) for k, v in p.items()}


def _rt(build, lo, hi, ch, field):
    """For length L in lo-1, lo, hi, hi+1 the format side accepts exactly lo..hi and parse reads the text back as the same fields; a refused length is not read back as those fields."""
    seen = []
    for length in (lo - 1, lo, hi, hi + 1):
        parts, text = build(ch * length)
        accepted = lo <= length <= hi
        e = err(m.format_language_tag, parts)
        if accepted:
            assert e is None, (length, e)
            out = m.format_language_tag(parts)
            assert out.lower() == text.lower(), (out, text)
            q = m.parse_language_tag(out)
            assert lowerp(q) == lowerp(parts)
            assert m.format_language_tag(q) == out
        else:
            assert e == fe('format_language_tag', 'bad_value:parts.' + field), (length, e)
            if m.language_tag_ok(text):
                assert lowerp(m.parse_language_tag(text)) != lowerp(parts), text
        seen.append(accepted)
    assert seen == [False, True, True, False]


def test_language_length_2_to_8_at_both_sides():
    _rt(lambda s: (P(language=s), s), 2, 8, 'a', 'language')


def test_language_must_be_alpha_only_on_the_format_side():
    for bad in ('e1', '1e', '12', 'e-', 'e\u00e9', 'e\u212a', 'en ', ' en', 'e\n', 'en\x00', '\u0661\u0662'):
        assert err(m.format_language_tag, P(language=bad)) == fe('format_language_tag', 'bad_value:parts.language'), repr(bad)
    for bad in (None, 1, b'en', ['en'], ('en',)):
        assert err(m.format_language_tag, P(language=bad)) == fe('format_language_tag', 'bad_type:parts.language'), bad
    for h in HOSTILE_STR:
        assert err(m.format_language_tag, P(language=h)) == fe('format_language_tag', 'bad_type:parts.language')
    assert m.format_language_tag(P(language='EN')) == 'en'
    assert m.format_language_tag(P(language='ENGLISH')) == 'english'


def test_extlang_count_and_length_and_the_short_language_rule():
    f = 'format_language_tag'
    for count in range(0, 4):
        parts = P(language='zh', extlangs=('abc', 'DEF', 'ghi')[:count])
        out = m.format_language_tag(parts)
        assert out == '-'.join(['zh', 'abc', 'def', 'ghi'][:count + 1])
        assert m.language_tag_ok(out) is True and m.parse_language_tag(out)['extlangs'] == ('abc', 'def', 'ghi')[:count]
    assert err(m.format_language_tag, P(language='zh', extlangs=('abc', 'def', 'ghi', 'jkl'))) == fe(f, 'bad_value:parts.extlangs')
    assert m.language_tag_ok('zh-abc-def-ghi-jkl') is False
    for lang, ok in (('ab', True), ('abc', True), ('abcd', False), ('abcde', False), ('abcdefgh', False)):
        e = err(m.format_language_tag, P(language=lang, extlangs=('abc',)))
        assert (e is None) is ok, lang
        if not ok:
            assert e == fe(f, 'bad_value:parts.extlangs')
            assert m.language_tag_ok(lang + '-abc') is False
        else:
            assert m.parse_language_tag(m.format_language_tag(P(language=lang, extlangs=('abc',))))['extlangs'] == ('abc',)
    _rt(lambda s: (P(language='zh', extlangs=(s,)), 'zh-' + s), 3, 3, 'a', 'extlangs')
    for bad in ('ab1', '1bc', '123', 'a-c', ' bc', 'b\u00e9c'):
        assert err(m.format_language_tag, P(language='zh', extlangs=(bad,))) == fe(f, 'bad_value:parts.extlangs'), repr(bad)
    assert err(m.format_language_tag, P(language='zh', extlangs=('abc', 1))) == fe(f, 'bad_type:parts.extlangs')
    assert err(m.format_language_tag, P(language='zh', extlangs=['abc'])) == fe(f, 'bad_type:parts.extlangs')
    assert err(m.format_language_tag, P(language='zh', extlangs=TupSub(('abc',)))) == fe(f, 'bad_type:parts.extlangs')
    for h in HOSTILE_STR:
        assert err(m.format_language_tag, P(language='zh', extlangs=(h,))) == fe(f, 'bad_type:parts.extlangs')
        assert err(m.format_language_tag, P(language='zh', extlangs=('abc', h))) == fe(f, 'bad_type:parts.extlangs')


def test_script_range_case_and_types():
    f = 'format_language_tag'
    _rt(lambda s: (P(script=s), 'en-' + s), 4, 4, 'a', 'script')
    assert m.format_language_tag(P(script='lATN')) == 'en-Latn'
    assert m.format_language_tag(P(script='LATN')) == 'en-Latn'
    for bad in ('123a', 'Lat1', '1234', 'La-n', 'L\u00e4tn', ''):
        assert err(m.format_language_tag, P(script=bad)) == fe(f, 'bad_value:parts.script'), repr(bad)
    for bad in (1, b'Latn', ['Latn'], ('Latn',)):
        assert err(m.format_language_tag, P(script=bad)) == fe(f, 'bad_type:parts.script'), bad
    for h in HOSTILE_STR:
        assert err(m.format_language_tag, P(script=h)) == fe(f, 'bad_type:parts.script')


def test_region_two_letters_or_three_digits_at_both_sides():
    f = 'format_language_tag'
    _rt(lambda s: (P(region=s), 'en-' + s), 2, 2, 'a', 'region')
    _rt(lambda s: (P(region=s), 'en-' + s), 3, 3, '1', 'region')
    for bad in ('aaa', '11', '1111', 'a1', '1a', '12a', 'a-', '', '\u00e9a', '\u0661\u0662\u0663', 'a\n'):
        assert err(m.format_language_tag, P(region=bad)) == fe(f, 'bad_value:parts.region'), repr(bad)
    for bad in (1, b'US', ['US']):
        assert err(m.format_language_tag, P(region=bad)) == fe(f, 'bad_type:parts.region'), bad
    for h in HOSTILE_STR:
        assert err(m.format_language_tag, P(region=h)) == fe(f, 'bad_type:parts.region')
    assert m.format_language_tag(P(region='us')) == 'en-US' and m.format_language_tag(P(region='419')) == 'en-419'
    assert m.language_tag_ok('en-1111') is True and m.parse_language_tag('en-1111')['region'] is None


def test_variant_shapes_at_both_sides():
    f = 'format_language_tag'
    for sub, ok in (('abcd', False), ('abcde', True), ('abcdefgh', True), ('abcdefghi', False), ('1abc', True), ('1ab', False), ('12345', True), ('12345678', True), ('123456789', False), ('a1bc', False), ('a1b2c', True), ('ab-cd', False), ('', False), ('ABCDE', True), ('1ABC', True), ('\u00e9bcde', False), ('abc\u0661e', False)):
        e = err(m.format_language_tag, P(variants=(sub,)))
        assert (e is None) is ok, sub
        if ok:
            out = m.format_language_tag(P(variants=(sub,)))
            assert out == 'en-' + sub.lower() and m.language_tag_ok(out) is True
            assert m.parse_language_tag(out)['variants'] == (sub.lower(),)
        else:
            assert e == fe(f, 'bad_value:parts.variants'), sub
            if m.language_tag_ok('en-' + sub):
                assert m.parse_language_tag('en-' + sub)['variants'] != (sub.lower(),), sub
    for bad in (1, b'abcde', ['abcde']):
        assert err(m.format_language_tag, P(variants=(bad,))) == fe(f, 'bad_type:parts.variants'), bad
    assert err(m.format_language_tag, P(variants=['abcde'])) == fe(f, 'bad_type:parts.variants')
    assert err(m.format_language_tag, P(variants=TupSub(('abcde',)))) == fe(f, 'bad_type:parts.variants')
    for h in HOSTILE_STR:
        assert err(m.format_language_tag, P(variants=(h,))) == fe(f, 'bad_type:parts.variants')
        assert err(m.format_language_tag, P(variants=('abcde', h))) == fe(f, 'bad_type:parts.variants')
    assert m.format_language_tag(P(variants=('abcde', '1ABC', 'Fghij'))) == 'en-abcde-1abc-fghij'
    assert m.format_language_tag(P(variants=('abcde', 'abcde'))) == 'en-abcde-abcde'


def test_extension_singleton_body_and_counts_at_both_sides():
    f = 'format_language_tag'
    _rt(lambda s: (P(extensions=(('a', (s,)),)), 'en-a-' + s), 2, 8, 'b', 'extensions')
    _rt(lambda s: (P(extensions=((s, ('bb',)),)), 'en-' + s + '-bb'), 1, 1, 'a', 'extensions')
    assert err(m.format_language_tag, P(extensions=(('a', ()),))) == fe(f, 'bad_value:parts.extensions')
    assert m.language_tag_ok('en-a') is False
    for c in EXT_SINGLETONS_OK:
        assert m.format_language_tag(P(extensions=((c, ('bb',)),))) == 'en-%s-bb' % c.lower()
    for c in 'xX':
        assert err(m.format_language_tag, P(extensions=((c, ('bb',)),))) == fe(f, 'bad_value:parts.extensions'), c
    for c in ('-', '_', ' ', '\u00e9', '\u212a'):
        assert err(m.format_language_tag, P(extensions=((c, ('bb',)),))) == fe(f, 'bad_value:parts.extensions'), repr(c)
    for sub in ('b-', 'b\u00e9', 'b c', '', 'b', 'bbbbbbbbb'):
        assert err(m.format_language_tag, P(extensions=(('a', (sub,)),))) == fe(f, 'bad_value:parts.extensions'), repr(sub)
    assert err(m.format_language_tag, P(extensions=(['a', ('bb',)],))) == fe(f, 'bad_type:parts.extensions')
    assert err(m.format_language_tag, P(extensions=(None,))) == fe(f, 'bad_type:parts.extensions')
    assert err(m.format_language_tag, P(extensions=(('a',),))) == fe(f, 'bad_value:parts.extensions')
    assert err(m.format_language_tag, P(extensions=(('a', ('bb',), 'c'),))) == fe(f, 'bad_value:parts.extensions')
    assert err(m.format_language_tag, P(extensions=('a-bb',))) == fe(f, 'bad_type:parts.extensions')
    assert err(m.format_language_tag, P(extensions=TupSub((('a', ('bb',)),)))) == fe(f, 'bad_type:parts.extensions')
    assert err(m.format_language_tag, P(extensions=(TupSub(('a', ('bb',))),))) == fe(f, 'bad_type:parts.extensions')
    assert err(m.format_language_tag, P(extensions=(('a', ['bb']),))) == fe(f, 'bad_type:parts.extensions')
    assert err(m.format_language_tag, P(extensions=(('a', TupSub(('bb',))),))) == fe(f, 'bad_type:parts.extensions')
    assert err(m.format_language_tag, P(extensions=(('a', 'bb'),))) == fe(f, 'bad_type:parts.extensions')
    assert err(m.format_language_tag, P(extensions=((1, ('bb',)),))) == fe(f, 'bad_type:parts.extensions')
    assert err(m.format_language_tag, P(extensions=(('a', (1,)),))) == fe(f, 'bad_type:parts.extensions')
    for h in HOSTILE_STR:
        assert err(m.format_language_tag, P(extensions=((h, ('bb',)),))) == fe(f, 'bad_type:parts.extensions')
        assert err(m.format_language_tag, P(extensions=(('a', (h,)),))) == fe(f, 'bad_type:parts.extensions')
        assert err(m.format_language_tag, P(extensions=(('a', ('bb', h)),))) == fe(f, 'bad_type:parts.extensions')
    assert m.format_language_tag(P(extensions=(('A', ('BB', 'Cc')), ('b', ('dd',))))) == 'en-a-bb-cc-b-dd'
    assert m.format_language_tag(P(extensions=(('a', ('bb',)), ('a', ('cc',))))) == 'en-a-bb-a-cc'


def test_privateuse_in_a_langtag_at_both_sides():
    f = 'format_language_tag'
    _rt(lambda s: (P(privateuse=(s,)), 'en-x-' + s), 1, 8, 'a', 'privateuse')
    assert m.format_language_tag(P(privateuse=())) == 'en'
    assert m.format_language_tag(P(privateuse=('A', '1', 'Bcdefghi'))) == 'en-x-a-1-bcdefghi'
    for h in HOSTILE_STR:
        assert err(m.format_language_tag, P(privateuse=(h,))) == fe(f, 'bad_type:parts.privateuse')
    assert err(m.format_language_tag, P(privateuse=['a'])) == fe(f, 'bad_type:parts.privateuse')
    assert err(m.format_language_tag, P(privateuse=('a b',))) == fe(f, 'bad_value:parts.privateuse')
    assert err(m.format_language_tag, P(privateuse=('\u00e9',))) == fe(f, 'bad_value:parts.privateuse')
    assert err(m.format_language_tag, P(privateuse=('',))) == fe(f, 'bad_value:parts.privateuse')


def test_langtag_that_renders_a_grandfathered_tag_must_be_regular_and_regular_must_match():
    f = 'format_language_tag'
    for g in REGULAR:
        p = m.parse_language_tag(g)
        assert p['kind'] == 'regular'
        assert m.format_language_tag(p) == g
        assert err(m.format_language_tag, dict(p, kind='langtag', grandfathered=None)) == fe(f, 'bad_value:parts.kind'), g
        other = [x for x in REGULAR if x != g][0]
        assert err(m.format_language_tag, dict(p, grandfathered=other)) == fe(f, 'bad_value:parts.grandfathered'), g
        assert err(m.format_language_tag, dict(p, grandfathered=g.upper())) == fe(f, 'bad_value:parts.grandfathered'), g
        assert err(m.format_language_tag, dict(p, grandfathered=None)) == fe(f, 'bad_type:parts.grandfathered')
    zh = m.parse_language_tag('zh-min')
    assert err(m.format_language_tag, dict(zh, extlangs=('yue',))) == fe(f, 'bad_value:parts.grandfathered')
    assert err(m.format_language_tag, dict(zh, kind='irregular')) == fe(f, 'bad_value:parts.grandfathered')
    assert m.format_language_tag(m.parse_language_tag('ZH-MIN-NAN')) == 'zh-min-nan'
    assert m.format_language_tag(P(language='zh', extlangs=('yue',))) == 'zh-yue'


def test_format_both_bad_refusal_order_is_field_order():
    f = 'format_language_tag'
    bad = {'language': '1', 'extlangs': ('1',), 'script': '1', 'region': '1', 'variants': ('1',), 'extensions': (('a', ()),), 'privateuse': ('',)}
    order = ['language', 'extlangs', 'script', 'region', 'variants', 'extensions', 'privateuse']
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            parts = P(**{order[i]: bad[order[i]], order[j]: bad[order[j]]})
            assert err(m.format_language_tag, parts) == fe(f, 'bad_value:parts.' + order[i]), (order[i], order[j])
    assert err(m.format_language_tag, P(language=None, extlangs=(1,))) == fe(f, 'bad_type:parts.language')
    assert err(m.format_language_tag, P(kind='x', language=1)) == fe(f, 'bad_value:parts.kind')
    assert err(m.format_language_tag, P(kind=1, grandfathered=1)) == fe(f, 'bad_type:parts.kind')
    assert err(m.format_language_tag, P(grandfathered='x', language=1)) == fe(f, 'bad_value:parts.grandfathered')
    assert err(m.format_language_tag, P(language='zh', extlangs=('abc', 'def', 'ghi', '1'))) == fe(f, 'bad_value:parts.extlangs')
    assert err(m.format_language_tag, P(language='zh', extlangs=('1', 'def', 'ghi', 'abc'))) == fe(f, 'bad_value:parts.extlangs')
    assert err(m.format_language_tag, P(extensions=(('x', ()),))) == fe(f, 'bad_value:parts.extensions')
    assert err(m.format_language_tag, P(extensions=(('a', ('b',)), ('x', ('bb',))))) == fe(f, 'bad_value:parts.extensions')
    assert err(m.format_language_tag, P(extensions=(('x', ('b',)),))) == fe(f, 'bad_value:parts.extensions')
    assert err(m.format_language_tag, P(extensions=((1, ()),))) == fe(f, 'bad_type:parts.extensions')
    assert err(m.format_language_tag, P(region='1', script='1')) == fe(f, 'bad_value:parts.script')
    assert err(m.format_language_tag, P(language='abcd', extlangs=('1',))) == fe(f, 'bad_value:parts.extlangs')
    assert err(m.format_language_tag, P(language='abcd', extlangs=('abc',), script='1')) == fe(f, 'bad_value:parts.extlangs')
    assert err(m.format_language_tag, P(privateuse=('a',) * 256, language='1')) == fe(f, 'bad_value:parts.language')
    assert err(m.format_language_tag, P(variants=('1',) * 256, extlangs=('1',))) == fe(f, 'bad_value:parts.extlangs')
    assert err(m.format_language_tag, P(variants=('1',) * 256, extensions=('1',) * 256)) == fe(f, 'bad_value:parts.variants.length')
    assert err(m.format_language_tag, P(extensions=('1',) * 256, privateuse=('a',) * 256)) == fe(f, 'bad_value:parts.extensions.length')
    assert err(m.format_language_tag, P(privateuse=('a',) * 256)) == fe(f, 'bad_value:parts.privateuse.length')


def test_extlangs_cap_order_count_then_length_then_elements():
    f = 'format_language_tag'
    assert err(m.format_language_tag, P(language='abcd', extlangs=('1',))) == fe(f, 'bad_value:parts.extlangs')
    assert err(m.format_language_tag, P(extlangs=('1',) * 255)) == fe(f, 'bad_value:parts.extlangs')
    assert err(m.format_language_tag, P(extlangs=('1',) * 256)) == fe(f, 'bad_value:parts.extlangs.length')
    assert m.format_language_tag(P(extlangs=('abc',))) == 'en-abc'


# ---------------------------------------------------------------- import and guard pins
UTIL_IMPORT = ('importlib.util', ('find_spec',), 0)
REG_IMPORT = (REG, ('make_fail',), 0)


def _guard_gen(world, src=None):
    """Execute the module source under a recording import hook for one guard world.
    Returns (import log, find_spec calls, namespace or None, raised exception or None)."""
    import types
    log = []
    calls = []
    real = builtins.__import__
    util = types.ModuleType('importlib.util')

    class Spec:
        pass

    def fake_find_spec(name, *a):
        calls.append(name)
        return Spec() if world == 'spec_present' else None
    util.find_spec = fake_find_spec
    reg = types.ModuleType(REG)
    reg.make_fail = lambda name: ('MARK', name)

    def hook(name, globals=None, locals=None, fromlist=(), level=0):
        log.append((name, tuple(fromlist) if fromlist else (), level))
        if name == 'importlib.util':
            return util
        if name == REG:
            if world == 'present':
                return reg
            if world == 'other':
                raise ModuleNotFoundError('No module named other', name='other.pkg')
            if world == 'noname':
                raise ModuleNotFoundError('No module named')
            if world == 'importerror':
                raise ImportError('boom', name=REG)
            raise ModuleNotFoundError('No module named ' + REG, name=REG)
        return real(name, globals, locals, fromlist, level)
    ns = {'__name__': 'x1218', '__builtins__': dict(vars(builtins), __import__=hook)}
    try:
        exec(compile(SRC_TEXT if src is None else src, '<m1218>', 'exec'), ns)
    except BaseException as e:
        return log, calls, None, e
    return log, calls, ns, None


SRC_TEXT = open(SRC_PATH).read()


def test_guard_present_registry_is_used_and_logs_exactly_two_imports():
    log, calls, ns, e = _guard_gen('present')
    assert e is None and log == [UTIL_IMPORT, REG_IMPORT] and calls == []
    assert ns['make_fail']('n') == ('MARK', 'n')
    assert ns['CLAIMS'] is False and ns['MAX_TAG'] == 255


def test_guard_absent_registry_falls_back_with_the_literal_p235_prefix_and_no_further_import():
    log, calls, ns, e = _guard_gen('absent')
    assert e is None and log == [UTIL_IMPORT, REG_IMPORT] and calls == [REG]
    fail = ns['make_fail']('nm')
    assert callable(fail) and ns['make_fail'].__name__ == 'make_fail' and fail.__name__ == 'fail'
    with pytest.raises(ValueError) as info:
        fail('some:code')
    assert str(info.value) == 'P235:nm:some:code' and type(info.value) is ValueError
    assert log == [UTIL_IMPORT, REG_IMPORT]


def test_guard_reraises_a_missing_module_that_is_not_the_registry_without_asking_find_spec():
    log, calls, ns, e = _guard_gen('other')
    assert ns is None and type(e) is ModuleNotFoundError and e.name == 'other.pkg'
    assert log == [UTIL_IMPORT, REG_IMPORT] and calls == []
    log, calls, ns, e = _guard_gen('noname')
    assert ns is None and type(e) is ModuleNotFoundError and e.name is None
    assert log == [UTIL_IMPORT, REG_IMPORT] and calls == []


def test_guard_reraises_when_the_registry_exists_but_its_import_failed():
    log, calls, ns, e = _guard_gen('spec_present')
    assert ns is None and type(e) is ModuleNotFoundError and e.name == REG
    assert log == [UTIL_IMPORT, REG_IMPORT] and calls == [REG]


def test_guard_catches_module_not_found_only_so_other_import_errors_propagate():
    log, calls, ns, e = _guard_gen('importerror')
    assert ns is None and type(e) is ImportError and e.name == REG
    assert log == [UTIL_IMPORT, REG_IMPORT] and calls == []


def test_guard_gen_self_test_detects_a_wrong_guard():
    bad_or = SRC_TEXT.replace(" or find_spec(", " and find_spec(")
    assert bad_or != SRC_TEXT
    _, _, ns, e = _guard_gen('other', bad_or)
    assert e is None and ns is not None
    bad_cls = SRC_TEXT.replace("except ModuleNotFoundError as exc", "except ImportError as exc")
    assert bad_cls != SRC_TEXT
    _, _, ns, e = _guard_gen('spec_present', bad_cls.replace("is not None:", "is None:"))
    assert e is None
    bad_name = SRC_TEXT.replace("exc.name != '", "exc.name == '")
    assert bad_name != SRC_TEXT
    _, _, ns, e = _guard_gen('absent', bad_name)
    assert e is not None and type(e) is ModuleNotFoundError
    assert _guard_gen('absent')[3] is None


def test_the_real_registry_world_prefix_is_probed_and_pinned():
    probe = err(m.make_fail('probe_fn'), 'probe_code')
    if STUB_WORLD:
        assert probe == 'STUB:probe_fn:probe_code'
        assert PFX == 'STUB:'
    else:
        assert probe == 'P235:probe_fn:probe_code'
        assert PFX == 'P235:'
    assert err(m.language_tag_ok, 1) == PFX + 'language_tag_ok:bad_type:tag'


@contextlib.contextmanager
def _record():
    """Record every import while the block runs; restore the original hook in a finally, whatever the block raises."""
    log = []
    real = builtins.__import__

    def hook(name, *a, **k):
        log.append(name)
        return real(name, *a, **k)
    _start_import(builtins, hook)
    try:
        yield log
    finally:
        _stop_import()


def test_the_recorder_restores_the_import_hook_even_when_the_block_raises():
    real = builtins.__import__
    with pytest.raises(RuntimeError):
        with _record() as log:
            exec('import hmac')
            assert log[0] == 'hmac'
            raise RuntimeError('boom')
    assert builtins.__import__ == real


def test_the_import_recorder_sees_a_function_level_import():
    log_holder = []
    real = builtins.__import__

    def hook(name, *a, **k):
        log_holder.append(name)
        return real(name, *a, **k)
    _start_import(builtins, hook)
    try:
        exec('import hmac')
    finally:
        _stop_import()
    assert log_holder[0] == 'hmac' and len(log_holder) >= 1


def test_success_shapes_do_no_import_through_all_three_entries():
    with _record() as log:
        n = 0
        for t in ACCEPT + list(IRREGULAR) + list(REGULAR) + ['x-a', 'en', 'zh-Hant-TW', 'i-ami']:
            assert m.language_tag_ok(t) is True
            p = m.parse_language_tag(t)
            assert type(m.format_language_tag(p)) is str
            n += 1
        assert n == 60 + 17 + 9 + 4
        assert log == []


def test_refusal_shapes_do_no_import_and_every_refusal_code_is_driven_under_the_hook():
    with _record() as log:
        seen = set()

        def drive(fn, *a):
            e = err(fn, *a)
            assert e is not None, (fn, a)
            seen.add(e[len(PFX):])
        for bad in (None, 1, StrSub('x'), b'x'):
            drive(m.language_tag_ok, bad)
            drive(m.parse_language_tag, bad)
        drive(m.language_tag_ok, 'x' * 256)
        drive(m.parse_language_tag, 'x' * 256)
        for t in REFUSE:
            drive(m.parse_language_tag, t)
        for fn, parts in _format_refusals():
            drive(m.format_language_tag, parts)
        assert log == []
        assert seen == set('%s:%s' % (fn, code) for fn, code in EXPECTED_CODES)
        ast_codes = _ast_fail_literals()
        assert ast_codes and ast_codes <= set(code for _, code in EXPECTED_CODES)


EXPECTED_CODES = [
    ('language_tag_ok', 'bad_type:tag'), ('language_tag_ok', 'bad_value:tag.length'),
    ('parse_language_tag', 'bad_type:tag'), ('parse_language_tag', 'bad_value:tag.length'), ('parse_language_tag', 'bad_value:tag.syntax'),
    ('format_language_tag', 'bad_type:parts'), ('format_language_tag', 'bad_value:parts.keys'), ('format_language_tag', 'bad_type:parts.key'),
    ('format_language_tag', 'bad_type:parts.kind'), ('format_language_tag', 'bad_value:parts.kind'),
    ('format_language_tag', 'bad_type:parts.grandfathered'), ('format_language_tag', 'bad_value:parts.grandfathered'),
    ('format_language_tag', 'bad_value:parts.language'), ('format_language_tag', 'bad_type:parts.language'),
    ('format_language_tag', 'bad_type:parts.extlangs'), ('format_language_tag', 'bad_value:parts.extlangs'), ('format_language_tag', 'bad_value:parts.extlangs.length'),
    ('format_language_tag', 'bad_type:parts.script'), ('format_language_tag', 'bad_value:parts.script'),
    ('format_language_tag', 'bad_type:parts.region'), ('format_language_tag', 'bad_value:parts.region'),
    ('format_language_tag', 'bad_type:parts.variants'), ('format_language_tag', 'bad_value:parts.variants'), ('format_language_tag', 'bad_value:parts.variants.length'),
    ('format_language_tag', 'bad_type:parts.extensions'), ('format_language_tag', 'bad_value:parts.extensions'), ('format_language_tag', 'bad_value:parts.extensions.length'),
    ('format_language_tag', 'bad_type:parts.privateuse'), ('format_language_tag', 'bad_value:parts.privateuse'), ('format_language_tag', 'bad_value:parts.privateuse.length'),
    ('format_language_tag', 'bad_value:tag.length'), ('format_language_tag', 'bad_value:parts.kind'),
]


def _format_refusals():
    irr = {'kind': 'irregular', 'language': None, 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': (), 'grandfathered': 'i-ami'}
    pu = {'kind': 'privateuse', 'language': None, 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': ('a',), 'grandfathered': None}
    yield 'f', None
    yield 'f', {}
    e0 = dict(P())
    e0[1] = 2
    yield 'f', e0
    e = dict(P())
    del e['kind']
    e[1] = 'x'
    yield 'f', e
    yield 'f', P(kind=1)
    yield 'f', P(kind='x')
    yield 'f', dict(irr, grandfathered=1)
    yield 'f', dict(irr, grandfathered='zz')
    yield 'f', dict(irr, language='en')
    yield 'f', dict(irr, extlangs=1)
    yield 'f', dict(irr, extlangs=('a',))
    yield 'f', dict(pu, region='US')
    yield 'f', dict(pu, privateuse=())
    yield 'f', P(language=1)
    yield 'f', P(language='1')
    yield 'f', P(extlangs=1)
    yield 'f', P(extlangs=('abc',) * 4)
    yield 'f', P(extlangs=('abc',) * 256)
    yield 'f', P(script=1)
    yield 'f', P(script='1')
    yield 'f', P(region=1)
    yield 'f', P(region='1')
    yield 'f', P(variants=1)
    yield 'f', P(variants=(1,))
    yield 'f', P(variants=('1',))
    yield 'f', P(variants=('abcde',) * 256)
    yield 'f', P(extensions=1)
    yield 'f', P(extensions=(1,))
    yield 'f', P(extensions=(('a', ()),))
    yield 'f', P(extensions=(('a', ('bb',)),) * 256)
    yield 'f', P(privateuse=1)
    yield 'f', P(privateuse=('',))
    yield 'f', P(privateuse=('a',) * 256)
    yield 'f', P(privateuse=('a',) * 126)
    yield 'f', P(grandfathered='zh-min')
    yield 'f', P(language='zh', extlangs=('min',))


def _ast_fail_literals():
    codes = set()
    for node in ast.walk(ast.parse(SRC_TEXT)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'fail' and node.args:
            a = node.args[0]
            if isinstance(a, ast.Constant) and type(a.value) is str:
                codes.add(a.value)
    return codes


# ---------------------------------------------------------------- scrub, lookalike and docstring pins
def _tree():
    return ast.parse(SRC_TEXT)


def test_module_source_is_ascii_and_has_no_banned_text_calls():
    SRC_TEXT.encode('ascii')
    banned_attr = ('isdigit', 'isalpha', 'isalnum', 'isspace', 'isupper', 'islower', 'isdecimal', 'isnumeric', 'isidentifier', 'isprintable', 'isascii', 'strip', 'lstrip', 'rstrip', 'casefold', 'title', 'capitalize', 'swapcase', 'encode', 'decode', 'format', 'translate', 'normalize')
    banned_name = ('isinstance', 'issubclass', 'int', 'float', 'ord', 'chr', 'eval', 'exec', 'getattr', 'hasattr', 'setattr', 'repr', 'str', 'bytes', 'list', 'dict', 'set', 'sorted', 'any', 'all', 'map', 'filter', 'compile', 'open', '__import__', 'import_module')
    calls = 0
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Call):
            calls += 1
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in banned_attr, node.func.attr
            if isinstance(node.func, ast.Name):
                assert node.func.id not in banned_name, node.func.id
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert (type(node).__name__, getattr(node, 'module', None), [a.name for a in node.names]) in (('ImportFrom', 'importlib.util', ['find_spec']), ('ImportFrom', REG, ['make_fail'])), ast.dump(node)
    assert calls > 40
    assert 're' not in [a.name for n in ast.walk(_tree()) if isinstance(n, ast.Import) for a in n.names]


def test_type_is_only_used_as_an_exact_type_identity_test_and_never_in_membership():
    uses = 0
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Compare):
            for side in [node.left] + list(node.comparators):
                if isinstance(side, ast.Call) and isinstance(side.func, ast.Name) and side.func.id == 'type':
                    uses += 1
                    assert len(node.ops) == 1 and type(node.ops[0]) in (ast.Is, ast.IsNot), ast.dump(node)
                    other = node.comparators[0]
                    assert isinstance(other, ast.Name) and other.id in ('str', 'tuple', 'dict', 'int'), ast.dump(node)
    total = sum(1 for n in ast.walk(_tree()) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'type')
    assert uses == total and uses == 12


def test_lower_and_upper_are_called_only_where_the_text_is_already_ascii_alnum():
    sites = {}
    for fn in [n for n in ast.walk(_tree()) if isinstance(n, ast.FunctionDef)]:
        for c in ast.walk(fn):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in ('lower', 'upper'):
                sites[(fn.name, c.func.attr)] = sites.get((fn.name, c.func.attr), 0) + 1
    assert sites == LOWER_UPPER_SITES
    assert m.language_tag_ok('\u212a') is False and m.language_tag_ok('i-\u212alingon') is False
    for bad in ('K\u212aa', '\u212a\u212a', '\u0130\u0130', 'ss\u00df', '\u00dfss', 'I-AM\u0130', 'zh-m\u0131n'):
        assert m.language_tag_ok(bad) is False
        assert err(m.parse_language_tag, bad) == fe('parse_language_tag', 'bad_value:tag.syntax')
    assert err(m.format_language_tag, dict(P(), kind='irregular', grandfathered='I-\u212a')) is not None


LOWER_UPPER_SITES = {('_parse', 'lower'): 1, ('format_language_tag', 'lower'): 9, ('format_language_tag', 'upper'): 2}


def test_whole_module_docstring_is_pinned_and_states_the_scope():
    assert m.__doc__ == DOC_EXACT
    assert ast.get_docstring(_tree(), clean=False) == DOC_EXACT
    assert m.CLAIMS is False
    for word in ('well-formed', 'section 2.1', 'section 2.1.1', 'EID 8711', 'EID 8712', 'EID 5457', '3 records', '12 errata records', 'none is applied', 'validity'):
        assert word in DOC_EXACT, word
    assert '\u2014' not in DOC_EXACT


def test_every_function_docstring_including_private_ones_is_pinned():
    found = {}
    for n in ast.walk(_tree()):
        if isinstance(n, ast.FunctionDef):
            found.setdefault(n.name, []).append(ast.get_docstring(n, clean=False))
    assert found == FUNC_DOCS
    assert len(found) >= 13
    assert all(v and all(type(d) is str and d != '' for d in v) for v in found.values())
    for name in FNS:
        assert getattr(m, name).__doc__ == FUNC_DOCS[name][0]


def test_module_constants_are_pinned_whole_by_type_and_repr():
    for name, tname, rep in CONSTS:
        value = getattr(m, name)
        assert type(value).__name__ == tname, name
        assert repr(value) == rep, name
    assert m.CLAIMS is False and type(m.NOT_CLAIMED) is tuple and type(m.ADJACENT) is tuple
    assert m.SCOPE.startswith('PARTIAL:')
    assert len(m._GRAND) == 26 and sorted(g[1] for g in m._GRAND.values()) == sorted(IRREGULAR + REGULAR)


def test_module_namespace_names_are_pinned_in_definition_order():
    names = [k for k in vars(m) if not (k.startswith('__') and k.endswith('__'))]
    assert names == NAMESPACE
    assert callable(m.make_fail)


def test_asserted_scope_claims_nothing_beyond_syntax():
    assert m.NOT_CLAIMED == ('registry validity', 'duplicate variant or singleton checks', 'canonicalization to preferred values', 'RFC 4647 matching or lookup', 'production readiness')
    assert m.ADJACENT == ('b1062 RFC 8187 ext-value language field, a looser own grammar', 'RFC 4647 language ranges', 'RFC 7231 Accept-Language')
    # Duplicate variants and duplicate singletons are valid syntax here (well-formed, not valid): OURS reading of section 2.2.9.
    assert m.language_tag_ok('en-abcde-abcde') is True
    assert m.language_tag_ok('en-a-bb-a-cc') is True
    assert m.language_tag_ok('qqq-Qqqq-QQ') is True


# ---------------------------------------------------------------- quotes (OURS: the quoted RFC text is checked against a fresh fetch) and errata
def _fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        return urllib.request.urlopen(req, timeout=60).read().decode('utf-8')
    except OSError as e:
        pytest.fail('cannot verify against %s: set the P235_* env file (%s)' % (url, e))


def _rfc_text():
    path = os.environ.get('P235_RFC5646_TXT')
    if path:
        assert os.path.exists(path) and os.path.getsize(path) > 150000, 'P235_RFC5646_TXT is empty or missing'
        return open(path, encoding='utf-8').read()
    text = _fetch('https://www.rfc-editor.org/rfc/rfc5646.txt')
    assert len(text) > 150000
    return text


def _ws(text):
    return ' '.join(text.split())


QUOTES = [
    'A tag is considered "well-formed" if it conforms to the ABNF (Section 2.1).',
    'Whitespace is not permitted in a language tag.',
    'All subtags have a maximum length of eight characters.',
    'language tags and their subtags, including private use and extensions, are to be treated as case insensitive',
    'a variant starting with a digit has a minimum length of four characters, while those starting with a letter have a minimum length of five characters.',
    'language = 2*3ALPHA ; shortest ISO 639 code ["-" extlang] ; sometimes followed by ; extended language subtags / 4ALPHA ; or reserved for future use / 5*8ALPHA ; or registered language subtag',
    'extlang = 3ALPHA ; selected ISO 639 codes *2("-" 3ALPHA) ; permanently reserved',
    'script = 4ALPHA ; ISO 15924 code',
    'region = 2ALPHA ; ISO 3166-1 code / 3DIGIT ; UN M.49 code',
    'variant = 5*8alphanum ; registered variants / (DIGIT 3alphanum)',
    'extension = singleton 1*("-" (2*8alphanum))',
    'singleton = DIGIT ; 0 - 9 / %x41-57 ; A - W / %x59-5A ; Y - Z / %x61-77 ; a - w / %x79-7A ; y - z',
    'privateuse = "x" 1*("-" (1*8alphanum))',
    'langtag = language ["-" script] ["-" region] *("-" variant) *("-" extension) ["-" privateuse]',
    'Language-Tag = langtag ; normal language tags / privateuse ; private use tag / grandfathered ; grandfathered tags',
    'alphanum = (ALPHA / DIGIT) ; letters and numbers',
    'the language tags described in this document are sequences of characters from the US-ASCII [ISO646] repertoire.',
]


def test_quotes_are_verbatim_in_a_fresh_copy_of_rfc_5646():
    text = _ws(_rfc_text())
    assert len(QUOTES) == 17 and len(set(QUOTES)) == 17
    for q in QUOTES:
        assert _ws(q) in text, q


def test_grandfathered_lists_equal_the_figure_1_abnf_derived_from_the_rfc_text():
    raw = _rfc_text()
    i = raw.index(' irregular     = "en-GB-oed"')
    j = raw.index(' regular       = "art-lojban"')
    k = raw.index(' alphanum      = (ALPHA / DIGIT)')
    irr = re.findall(r'"([^"]+)"', raw[i:j])
    reg = re.findall(r'"([^"]+)"', raw[j:k])
    assert tuple(irr) == IRREGULAR and tuple(reg) == REGULAR
    assert len(irr) == 17 and len(reg) == 9
    assert sorted(v[1] for v in m._GRAND.values()) == sorted(irr + reg)
    assert sorted(m._GRAND) == sorted(g.lower() for g in irr + reg)
    for g in irr + reg:
        assert m._GRAND[g.lower()] == (('irregular' if g in irr else 'regular'), g)


def _errata_records():
    path = os.environ.get('P235_ERRATA_JSON')
    if path:
        assert os.path.exists(path) and os.path.getsize(path) > 100000, 'P235_ERRATA_JSON is empty or missing'
        return json.load(open(path, encoding='utf-8'))
    return json.loads(_fetch('https://www.rfc-editor.org/errata.json'))


def test_errata_ledger_for_rfc_5646_and_rfc_5234_matches_errata_json():
    records = _errata_records()
    assert len(records) > 1000
    r5646 = {str(r['errata_id']): (r['errata_status_code'], r['errata_type_code'], r.get('section')) for r in records if r.get('doc-id') == 'RFC5646'}
    assert len(r5646) == 3
    assert r5646 == {'8711': ('Held for Document Update', 'Technical', '3.1.5'), '8712': ('Held for Document Update', 'Technical', '3.5'), '5457': ('Reported', 'Technical', '2.2.9')}
    r5234 = sorted(int(r['errata_id']) for r in records if r.get('doc-id') == 'RFC5234')
    assert r5234 == [1423, 2820, 2914, 2968, 3076, 3096, 4040, 4361, 4564, 5110, 6172, 6173]
    for eid in ('EID 8711 Held for Document Update Technical section 3.1.5', 'EID 8712 Held for Document Update Technical section 3.5', 'EID 5457 Reported Technical section 2.2.9', '3 records on errata.json'):
        assert eid in m.__doc__, eid
    assert 'RFC 5234 has 12 errata records (EID 1423 2820 2914 2968 3076 3096 4040 4361 4564 5110 6172 6173)' in m.__doc__


# ---------------------------------------------------------------- four-combo child pytest proof
def test_suite_passes_in_four_child_pytest_combos_slow(tmp_path):
    backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(SRC_PATH))))
    stub = tmp_path / 'stub'
    for rel in ('app', 'app/modules', 'app/modules/instinct_doc'):
        (stub / rel).mkdir(parents=True, exist_ok=True)
        (stub / rel / '__init__.py').write_text("__path__ = __import__('pkgutil').extend_path(__path__, __name__)\n")
    (stub / 'app/modules/instinct_doc/p235_concepts_registry.py').write_text("def make_fail(name):\n    def fail(code):\n        raise ValueError('STUB:%s:%s' % (name, code))\n    return fail\n")
    empty = tmp_path / 'none'
    empty.mkdir()
    combos = [(str(stub), '0'), (str(empty), '1'), ('', '2'), ('', 'random')]
    for world, seed in combos:
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=((world + os.pathsep) if world else '') + backend)
        r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', __file__, '-k', 'not slow'], env=env, capture_output=True, text=True, timeout=60, cwd=str(tmp_path))
        assert r.returncode == 0, (world, seed, r.stdout[-400:], r.stderr[-200:])
        assert ' passed' in r.stdout and 'failed' not in r.stdout


def test_format_both_bad_order_inside_each_kind_branch():
    f = 'format_language_tag'
    irr = {'kind': 'irregular', 'language': None, 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': (), 'grandfathered': 'i-klingon'}
    assert m.format_language_tag(irr) == 'i-klingon'
    assert err(m.format_language_tag, dict(irr, language='en', extlangs=['a'])) == fe(f, 'bad_value:parts.language')
    assert err(m.format_language_tag, dict(irr, language='en', extlangs=('a',))) == fe(f, 'bad_value:parts.language')
    pu = {'kind': 'privateuse', 'language': None, 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': ('a',), 'grandfathered': None}
    assert err(m.format_language_tag, dict(pu, language='en', extlangs=['a'])) == fe(f, 'bad_value:parts.language')
    assert err(m.format_language_tag, dict(pu, language='en', extlangs=('a',))) == fe(f, 'bad_value:parts.language')
    lt = {'kind': 'langtag', 'language': 'en', 'extlangs': (), 'script': None, 'region': None, 'variants': (), 'extensions': (), 'privateuse': (), 'grandfathered': None}
    assert err(m.format_language_tag, dict(lt, extlangs=('abc', 'abc', 'abc', 5))) == fe(f, 'bad_value:parts.extlangs')
    assert err(m.format_language_tag, dict(lt, language='abcd', extlangs=('abc', 5))) == fe(f, 'bad_value:parts.extlangs')
    assert err(m.format_language_tag, dict(lt, extlangs=('abc', 5))) == fe(f, 'bad_type:parts.extlangs')


# ---------------------------------------------------------------- generated pins (regenerate with gen_meta.py after any module edit)
DOC_EXACT = 'b1218 RFC 5646 (BCP 47) language-tag syntax: well-formed tags only (section 2.1 ABNF).\nlanguage_tag_ok(tag) -> bool: True when the tag is well-formed (a langtag, a private use tag or one of the 26 grandfathered tags of section 2.1). Tags are ASCII, compared without regard to case (section 2.1.1) and never trimmed. An exact str of 1..255 characters is checked; a non-str raises bad_type:tag and a longer str raises bad_value:tag.length before any scan. Other bad text returns False.\nparse_language_tag(tag) -> dict with the keys kind, language, extlangs, script, region, variants, extensions, privateuse, grandfathered, subtags kept in the case given. kind is langtag, privateuse, regular (one of the nine regular grandfathered tags, which also match the langtag production, so their subtags are kept and grandfathered holds the registered form) or irregular (one of the 17 irregular tags: only grandfathered is set). Bad text raises bad_value:tag.syntax.\nformat_language_tag(parts) -> str: the section 2.1.1 convention case (script Titlecase, two-letter region uppercase, all else lowercase) for a dict of the parse shape. Every field is checked by type and range, and the dict must be the one parse would give for that text.\nLimits: tags and formatted tags are at most 255 characters (OURS, section 4.4 asks for at least 35); a tuple field longer than 255 is refused before it is walked.\nErrata on RFC 5646 (3 records on errata.json): EID 8711 Held for Document Update Technical section 3.1.5, EID 8712 Held for Document Update Technical section 3.5 (both about the Latin script wording of Description fields, registry text this module does not use) and EID 5457 Reported Technical section 2.2.9 (validity text; this module checks well-formedness only). None is applied. RFC 5234 has 12 errata records (EID 1423 2820 2914 2968 3076 3096 4040 4361 4564 5110 6172 6173); none is applied.\nExtended language subtags follow the language only when it is 2 or 3 letters and number at most three (section 2.2.2); duplicate variants, duplicate singletons and registry membership are validity, not well-formedness, and are not checked.\n'
FUNC_DOCS = {'_all_in': ['True when every character of the exact str is in allowed (an empty str is True).'], '_is_variant': ['True for 5 to 8 alphanumerics, or a digit then 3 alphanumerics (section 2.1 variant).'], '_mk': ['Build the result dict in the fixed key order.'], '_langtag': ['Match the langtag or privateuse production on the split subtags; return the result dict or None.'], '_parse': ['Parse an exact str already length-checked; return the result dict or None.'], '_arg': ['Check the exact type and the length cap of a tag argument.'], 'language_tag_ok': ['True when the exact str is a well-formed RFC 5646 language tag.'], 'parse_language_tag': ['Return the parsed fields of a well-formed language tag; refuse any other text.'], '_sub': ['Check one subtag: exact str, lo..hi characters, all in allowed.'], '_tup': ['Check an exact tuple field and its length cap; return its length.'], 'format_language_tag': ['Render a parse-shaped dict in the section 2.1.1 convention case; refuse anything parse would not give.'], 'make_fail': ['Fallback used only when the shared registry module is absent: return a failer for the named function.'], 'fail': ['Raise ValueError with the P235 name and code.']}
NAMESPACE = ['find_spec', 'make_fail', 'CLAIMS', 'SCOPE', 'NOT_CLAIMED', 'ADJACENT', 'MAX_TAG', '_ALPHA', '_DIGIT', '_ALNUM', '_TAGCHARS', '_KEYS', '_GRAND', '_all_in', '_is_variant', '_mk', '_langtag', '_parse', '_arg', 'language_tag_ok', 'parse_language_tag', '_sub', '_tup', 'format_language_tag']
CONSTS = [('CLAIMS', 'bool', 'False'), ('SCOPE', 'str', "'PARTIAL: RFC 5646 section 2.1 well-formed language tags over caller text, no registry lookup and no validity checking'"), ('NOT_CLAIMED', 'tuple', "('registry validity', 'duplicate variant or singleton checks', 'canonicalization to preferred values', 'RFC 4647 matching or lookup', 'production readiness')"), ('ADJACENT', 'tuple', "('b1062 RFC 8187 ext-value language field, a looser own grammar', 'RFC 4647 language ranges', 'RFC 7231 Accept-Language')"), ('MAX_TAG', 'int', '255'), ('_ALPHA', 'str', "'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'"), ('_DIGIT', 'str', "'0123456789'"), ('_ALNUM', 'str', "'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'"), ('_TAGCHARS', 'str', "'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'"), ('_KEYS', 'tuple', "('kind', 'language', 'extlangs', 'script', 'region', 'variants', 'extensions', 'privateuse', 'grandfathered')"), ('_GRAND', 'dict', "{'en-gb-oed': ('irregular', 'en-GB-oed'), 'i-ami': ('irregular', 'i-ami'), 'i-bnn': ('irregular', 'i-bnn'), 'i-default': ('irregular', 'i-default'), 'i-enochian': ('irregular', 'i-enochian'), 'i-hak': ('irregular', 'i-hak'), 'i-klingon': ('irregular', 'i-klingon'), 'i-lux': ('irregular', 'i-lux'), 'i-mingo': ('irregular', 'i-mingo'), 'i-navajo': ('irregular', 'i-navajo'), 'i-pwn': ('irregular', 'i-pwn'), 'i-tao': ('irregular', 'i-tao'), 'i-tay': ('irregular', 'i-tay'), 'i-tsu': ('irregular', 'i-tsu'), 'sgn-be-fr': ('irregular', 'sgn-BE-FR'), 'sgn-be-nl': ('irregular', 'sgn-BE-NL'), 'sgn-ch-de': ('irregular', 'sgn-CH-DE'), 'art-lojban': ('regular', 'art-lojban'), 'cel-gaulish': ('regular', 'cel-gaulish'), 'no-bok': ('regular', 'no-bok'), 'no-nyn': ('regular', 'no-nyn'), 'zh-guoyu': ('regular', 'zh-guoyu'), 'zh-hakka': ('regular', 'zh-hakka'), 'zh-min': ('regular', 'zh-min'), 'zh-min-nan': ('regular', 'zh-min-nan'), 'zh-xiang': ('regular', 'zh-xiang')}")]
