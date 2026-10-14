"""P235 concepts batch 68: string dynamic programming.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
"""

from app.modules.instinct_doc.p235_concepts_registry import (
    check_int, check_items, check_str, make_fail)

MAX_LEN = 1_000
MAX_WORDS = 1_000
MAX_WORD = 100


def _text(fail, s, name="s", allow_empty=True, alpha=None):
    check_str(fail, s, name)
    if len(s) > MAX_LEN:
        fail("too_long:%s" % name)
    if not s and not allow_empty:
        fail("empty:%s" % name)
    if not s.isascii():
        fail("bad_char:%s" % name)
    if alpha == "lower" and any(not ("a" <= c <= "z") for c in s):
        fail("bad_char:%s" % name)
    if alpha == "parens" and any(c not in "()" for c in s):
        fail("bad_char:%s" % name)


def palindrome_partition_min_cuts(s):
    """Fewest cuts so every piece of s is a palindrome."""
    fail = make_fail("palindrome_partition_min_cuts")
    _text(fail, s, "s", allow_empty=False)
    n = len(s)
    pal = [[False] * n for _ in range(n)]
    for i in range(n):
        pal[i][i] = True
    for length in range(2, n + 1):
        for i in range(n - length + 1):
            j = i + length - 1
            pal[i][j] = s[i] == s[j] and (length == 2
                                          or pal[i + 1][j - 1])
    dp = [0] * (n + 1)
    for i in range(1, n + 1):
        dp[i] = min(dp[j] + 1 for j in range(i) if pal[j][i - 1])
    return dp[n] - 1


def distinct_subsequences_count(s, t):
    """Number of ways t occurs as a subsequence of s."""
    fail = make_fail("distinct_subsequences_count")
    _text(fail, s, "s")
    _text(fail, t, "t")
    dp = [0] * (len(t) + 1)
    dp[0] = 1
    for ch in s:
        for j in range(len(t), 0, -1):
            if t[j - 1] == ch:
                dp[j] += dp[j - 1]
    return dp[len(t)]


def longest_repeating_substring_length(s):
    """Longest substring of s occurring at least twice.

    The two occurrences may overlap.
    """
    fail = make_fail("longest_repeating_substring_length")
    _text(fail, s, "s")
    n = len(s)
    best = 0
    for length in range(1, n):
        seen = set()
        for i in range(n - length + 1):
            sub = s[i:i + length]
            if sub in seen:
                best = length
                break
            seen.add(sub)
    return best


def word_break_check(s, words):
    """True when s segments fully into dictionary words.

    Only lowercase ASCII a-z is accepted, for s and words.
    """
    fail = make_fail("word_break_check")
    _text(fail, s, "s", allow_empty=False, alpha="lower")
    check_items(fail, words, "words")
    if not words:
        fail("empty:words")
    if len(words) > MAX_WORDS:
        fail("too_many:words")
    for i, w in enumerate(words):
        check_str(fail, w, "words[%d]" % i)
        if not w:
            fail("empty:words[%d]" % i)
        if len(w) > MAX_WORD:
            fail("too_long:words[%d]" % i)
        if any(not ("a" <= c <= "z") for c in w):
            fail("bad_char:words[%d]" % i)
    ws = set(words)
    n = len(s)
    dp = [False] * (n + 1)
    dp[0] = True
    for i in range(1, n + 1):
        dp[i] = any(dp[j] and s[j:i] in ws for j in range(i))
    return dp[n]


def glob_match_check(s, p):
    """Full-string match where ? is any char and * any run.

    The * wildcard spans zero or more of ANY characters; unlike a
    regex, a glob star repeats no single element. Only ASCII is
    accepted, and pattern characters other than ? and * match
    literally.
    """
    fail = make_fail("glob_match_check")
    _text(fail, s, "s")
    _text(fail, p, "p")
    n, m = len(s), len(p)
    dp = [[False] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = True
    for j in range(1, m + 1):
        if p[j - 1] == "*":
            dp[0][j] = dp[0][j - 1]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if p[j - 1] == "*":
                dp[i][j] = dp[i - 1][j] or dp[i][j - 1]
            elif p[j - 1] == "?" or p[j - 1] == s[i - 1]:
                dp[i][j] = dp[i - 1][j - 1]
    return dp[n][m]


def longest_valid_parens_length(s):
    """Longest well-formed parentheses substring of s.

    Only ( and ) are accepted.
    """
    fail = make_fail("longest_valid_parens_length")
    _text(fail, s, "s", alpha="parens")
    stack = [-1]
    best = 0
    for i, ch in enumerate(s):
        if ch == "(":
            stack.append(i)
        else:
            stack.pop()
            if not stack:
                stack.append(i)
            elif i - stack[-1] > best:
                best = i - stack[-1]
    return best


def count_palindromic_substrings(s):
    """Count of palindromic substrings of s."""
    fail = make_fail("count_palindromic_substrings")
    _text(fail, s, "s")
    n = len(s)
    total = 0
    for center in range(2 * n - 1):
        lo = center // 2
        hi = lo + center % 2
        while lo >= 0 and hi < n and s[lo] == s[hi]:
            total += 1
            lo -= 1
            hi += 1
    return total


def min_ascii_delete_sum(a, b):
    """Lowest ASCII sum of deletions making the two strings equal."""
    fail = make_fail("min_ascii_delete_sum")
    _text(fail, a, "a")
    _text(fail, b, "b")
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + ord(a[i - 1])
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + ord(b[j - 1])
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = min(dp[i - 1][j] + ord(a[i - 1]),
                               dp[i][j - 1] + ord(b[j - 1]))
    return dp[n][m]


def longest_palindromic_subsequence_length(s):
    """Longest palindromic subsequence of s (gaps allowed)."""
    fail = make_fail("longest_palindromic_subsequence_length")
    _text(fail, s, "s", allow_empty=False)
    n = len(s)
    dp = [[0] * n for _ in range(n)]
    for i in range(n):
        dp[i][i] = 1
    for length in range(2, n + 1):
        for i in range(n - length + 1):
            j = i + length - 1
            if s[i] == s[j]:
                dp[i][j] = 2 + dp[i + 1][j - 1]
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j - 1])
    return dp[0][n - 1]


def regex_match_dot_star(s, p):
    """Full-string match with . and Kleene star over one element.

    . matches any single character; x* matches zero or more
    repetitions of the preceding element x (a character or .).
    The pattern must be lowercase ASCII letters, ., and *, and *
    must follow a repeatable element - a leading * or a **
    sequence is refused. Unlike a glob, the star repeats the one
    preceding element, not an arbitrary span.
    """
    fail = make_fail("regex_match_dot_star")
    _text(fail, s, "s", alpha="lower")
    _text(fail, p, "p")
    for j, ch in enumerate(p):
        if not ("a" <= ch <= "z" or ch in ".*"):
            fail("bad_char:p")
        if ch == "*" and (j == 0 or p[j - 1] == "*"):
            fail("bad_value:p")
    n, m = len(s), len(p)
    dp = [[False] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = True
    for j in range(2, m + 1):
        if p[j - 1] == "*":
            dp[0][j] = dp[0][j - 2]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if p[j - 1] == "*":
                dp[i][j] = dp[i][j - 2] or (
                    (p[j - 2] == "." or p[j - 2] == s[i - 1])
                    and dp[i - 1][j])
            elif p[j - 1] == "." or p[j - 1] == s[i - 1]:
                dp[i][j] = dp[i - 1][j - 1]
    return dp[n][m]
