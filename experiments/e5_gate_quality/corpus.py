"""Synthetic patch corpus for experiment E5 (gate quality).

Each template has correct code, a buggy variant, thorough tests and weak tests.
Optional "omission" entries hold a bug of omission plus tests that exercise every
line that exists (so line-level mutants die) but never the missing behavior.
All of this is authored by the experimenter: results are UNVERIFIED for any
real patch stream. See RESULTS.md.
"""

T = {}

T["clamp"] = dict(
 good='''def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x
''',
 bug='''def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi - 1
    return x
''',
 thorough='''from m_clamp import clamp
def test_mid():
    assert clamp(5, 0, 10) == 5
def test_low():
    assert clamp(-3, 0, 10) == 0
def test_high():
    assert clamp(30, 0, 10) == 10
def test_edges():
    assert clamp(0, 0, 10) == 0
    assert clamp(10, 0, 10) == 10
''',
 weak='''from m_clamp import clamp
def test_mid():
    assert clamp(5, 0, 10) == 5
def test_low():
    assert clamp(-3, 0, 10) == 0
''')

T["window_sum"] = dict(
 good='''def window_sum(xs, n):
    if n <= 0:
        return 0
    return sum(xs[-n:])
''',
 bug='''def window_sum(xs, n):
    return sum(xs[-n:])
''',
 thorough='''from m_window_sum import window_sum
def test_basic():
    assert window_sum([1, 2, 3, 4], 2) == 7
def test_zero():
    assert window_sum([1, 2, 3], 0) == 0
def test_negative():
    assert window_sum([1, 2, 3], -1) == 0
def test_long():
    assert window_sum([1, 2], 5) == 3
''',
 weak='''from m_window_sum import window_sum
def test_basic():
    assert window_sum([1, 2, 3, 4], 2) == 7
''')

T["dedupe"] = dict(
 good='''def dedupe(xs):
    seen = set()
    out = []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
''',
 bug='''def dedupe(xs):
    seen = set()
    out = []
    for x in reversed(xs):
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out[::-1]
''',
 thorough='''from m_dedupe import dedupe
def test_none():
    assert dedupe([1, 2, 3]) == [1, 2, 3]
def test_dups_keep_first():
    assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]
def test_empty():
    assert dedupe([]) == []
''',
 weak='''from m_dedupe import dedupe
def test_none():
    assert dedupe([1, 2, 3]) == [1, 2, 3]
def test_empty():
    assert dedupe([]) == []
''')

T["parse_amount"] = dict(
 good='''from decimal import Decimal
def parse_amount(s):
    s = s.replace("$", "").replace(",", "").strip()
    return int(Decimal(s) * 100)
''',
 bug='''def parse_amount(s):
    s = s.replace("$", "").replace(",", "").strip()
    return int(float(s) * 100)
''',
 thorough='''from m_parse_amount import parse_amount
def test_plain():
    assert parse_amount("5.00") == 500
def test_dollar_comma():
    assert parse_amount("$1,234.50") == 123450
def test_float_trap():
    assert parse_amount("19.99") == 1999
def test_space():
    assert parse_amount(" 7 ") == 700
''',
 weak='''from m_parse_amount import parse_amount
def test_plain():
    assert parse_amount("5.00") == 500
def test_dollar_comma():
    assert parse_amount("$1,234.50") == 123450
''')

T["rate_ok"] = dict(
 good='''def rate_ok(count, limit):
    return count < limit
''',
 bug='''def rate_ok(count, limit):
    return count <= limit
''',
 thorough='''from m_rate_ok import rate_ok
def test_under():
    assert rate_ok(1, 5)
def test_at_limit():
    assert not rate_ok(5, 5)
def test_over():
    assert not rate_ok(9, 5)
def test_just_under():
    assert rate_ok(4, 5)
''',
 weak='''from m_rate_ok import rate_ok
def test_under():
    assert rate_ok(1, 5)
def test_over():
    assert not rate_ok(9, 5)
''')

T["median"] = dict(
 good='''def median(xs):
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2
''',
 bug='''def median(xs):
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return s[mid]
''',
 thorough='''from m_median import median
def test_odd():
    assert median([3, 1, 2]) == 2
def test_even():
    assert median([4, 1, 3, 2]) == 2.5
def test_single():
    assert median([7]) == 7
def test_two():
    assert median([1, 3]) == 2
''',
 weak='''from m_median import median
def test_odd():
    assert median([3, 1, 2]) == 2
def test_single():
    assert median([7]) == 7
''')

T["chunk"] = dict(
 good='''def chunk(xs, n):
    out = []
    i = 0
    while i < len(xs):
        out.append(xs[i:i + n])
        i += n
    return out
''',
 bug='''def chunk(xs, n):
    out = []
    i = 0
    while i + n <= len(xs):
        out.append(xs[i:i + n])
        i += n
    return out
''',
 thorough='''from m_chunk import chunk
def test_even():
    assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]
def test_remainder():
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
def test_empty():
    assert chunk([], 3) == []
def test_big_n():
    assert chunk([1, 2], 5) == [[1, 2]]
''',
 weak='''from m_chunk import chunk
def test_even():
    assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]
def test_empty():
    assert chunk([], 3) == []
''')

T["safe_div"] = dict(
 good='''def safe_div(a, b, default=0):
    if b == 0:
        return default
    return a / b
''',
 bug='''def safe_div(a, b, default=0):
    if b == 0 or a == 0:
        return default
    return a / b
''',
 thorough='''from m_safe_div import safe_div
def test_div():
    assert safe_div(6, 3) == 2
def test_zero_den():
    assert safe_div(1, 0, -1) == -1
def test_zero_num():
    assert safe_div(0, 3, -1) == 0
def test_default_zero():
    assert safe_div(5, 0) == 0
''',
 weak='''from m_safe_div import safe_div
def test_div():
    assert safe_div(6, 3) == 2
def test_zero_den():
    assert safe_div(1, 0, -1) == -1
''')

T["is_leap"] = dict(
 good='''def is_leap(y):
    if y % 400 == 0:
        return True
    if y % 100 == 0:
        return False
    return y % 4 == 0
''',
 bug='''def is_leap(y):
    if y % 100 == 0:
        return False
    return y % 4 == 0
''',
 thorough='''from m_is_leap import is_leap
def test_common():
    assert is_leap(2024)
    assert not is_leap(2023)
def test_century():
    assert not is_leap(1900)
def test_400():
    assert is_leap(2000)
def test_four_hundred_off_by_one():
    assert not is_leap(2001)
''',
 weak='''from m_is_leap import is_leap
def test_common():
    assert is_leap(2024)
    assert not is_leap(2023)
''',
 # omission: 400 rule missing, tests exercise every existing line, never y % 400 == 0
 omit_tests='''from m_is_leap import is_leap
def test_common():
    assert is_leap(2024)
    assert not is_leap(2023)
def test_century():
    assert not is_leap(1900)
def test_four():
    assert is_leap(2008)
    assert not is_leap(2009)
''')

T["slugify"] = dict(
 good='''import re
def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower())
    return s.strip("-")
''',
 bug='''import re
def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower())
    return s
''',
 thorough='''from m_slugify import slugify
def test_basic():
    assert slugify("Hello World") == "hello-world"
def test_edges():
    assert slugify("  Hi!  ") == "hi"
def test_collapse():
    assert slugify("a   b__c") == "a-b-c"
def test_digits():
    assert slugify("Route 66") == "route-66"
''',
 weak='''from m_slugify import slugify
def test_basic():
    assert slugify("Hello World") == "hello-world"
def test_collapse():
    assert slugify("a   b__c") == "a-b-c"
''')

T["top_k"] = dict(
 good='''def top_k(d, k):
    items = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))
    return [key for key, _ in items[:k]]
''',
 bug='''def top_k(d, k):
    items = sorted(d.items(), key=lambda kv: -kv[1])
    return [key for key, _ in items[:k]]
''',
 thorough='''from m_top_k import top_k
def test_basic():
    assert top_k({"a": 1, "b": 3, "c": 2}, 2) == ["b", "c"]
def test_ties_by_key():
    assert top_k({"z": 2, "a": 2, "m": 1}, 2) == ["a", "z"]
def test_k_zero():
    assert top_k({"a": 1}, 0) == []
def test_k_big():
    assert top_k({"a": 1, "b": 2}, 9) == ["b", "a"]
''',
 weak='''from m_top_k import top_k
def test_basic():
    assert top_k({"a": 1, "b": 3, "c": 2}, 2) == ["b", "c"]
def test_k_zero():
    assert top_k({"a": 1}, 0) == []
''')

T["merge_ranges"] = dict(
 good='''def merge_ranges(rs):
    out = []
    for lo, hi in sorted(rs):
        if out and lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [tuple(r) for r in out]
''',
 bug='''def merge_ranges(rs):
    out = []
    for lo, hi in sorted(rs):
        if out and lo < out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [tuple(r) for r in out]
''',
 thorough='''from m_merge_ranges import merge_ranges
def test_disjoint():
    assert merge_ranges([(5, 6), (1, 2)]) == [(1, 2), (5, 6)]
def test_overlap():
    assert merge_ranges([(1, 4), (2, 6)]) == [(1, 6)]
def test_touching():
    assert merge_ranges([(1, 2), (2, 3)]) == [(1, 3)]
def test_contained():
    assert merge_ranges([(1, 10), (2, 3)]) == [(1, 10)]
def test_empty():
    assert merge_ranges([]) == []
''',
 weak='''from m_merge_ranges import merge_ranges
def test_disjoint():
    assert merge_ranges([(5, 6), (1, 2)]) == [(1, 2), (5, 6)]
def test_overlap():
    assert merge_ranges([(1, 4), (2, 6)]) == [(1, 6)]
''')
