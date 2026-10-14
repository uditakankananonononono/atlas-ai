"""P235 concepts batch 21 (concepts 201-210, text metrics/transforms) - ten new
small deterministic text concepts. 201-210 of the doc's 1000 (anchor P235|L184).
Inputs bounded (MAX_ITEMS 10_000 chars); simple splits; oracles pinned in tests.
"""
from __future__ import annotations

from fractions import Fraction

from .p235_concepts_batch1 import MAX_ITEMS, check_str, make_fail

MAX_TAB_WIDTH = 64
MAX_TAB_OUTPUT = 100_000


def _check_text(fail, text, name):
    check_str(fail, text, name)
    if len(text) > MAX_ITEMS:
        fail("too_many:text")


VOWELS = set("aeiouAEIOU")
PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


def syllable_estimate(text):
    fail = make_fail("syllable_estimate")
    _check_text(fail, text, "syllable_estimate")
    groups = 0
    prev_vowel = False
    for ch in text:
        is_vowel = ch in VOWELS
        if is_vowel and not prev_vowel:
            groups += 1
        prev_vowel = is_vowel
    return groups


def unique_bigram_count(text):
    fail = make_fail("unique_bigram_count")
    _check_text(fail, text, "unique_bigram_count")
    return len({text[i:i + 2] for i in range(len(text) - 1)})


def vowel_consonant_ratio_exact(text):
    fail = make_fail("vowel_consonant_ratio_exact")
    _check_text(fail, text, "vowel_consonant_ratio_exact")
    vowels = 0
    consonants = 0
    for ch in text:
        if ch in VOWELS:
            vowels += 1
        elif ch.isalpha():
            consonants += 1
    if consonants == 0:
        fail("no_consonants")
    return Fraction(vowels, consonants)


def repeated_word_count(text):
    fail = make_fail("repeated_word_count")
    _check_text(fail, text, "repeated_word_count")
    seen = set()
    repeated = set()
    for word in text.split():
        key = word.lower()
        if key in seen:
            repeated.add(key)
        seen.add(key)
    return len(repeated)


def punctuation_count(text):
    fail = make_fail("punctuation_count")
    _check_text(fail, text, "punctuation_count")
    return sum(1 for ch in text if ch in PUNCT)


def line_length_max(text):
    fail = make_fail("line_length_max")
    _check_text(fail, text, "line_length_max")
    if not text:
        return 0
    return max(len(line) for line in text.split("\n"))


def paragraph_count(text):
    fail = make_fail("paragraph_count")
    _check_text(fail, text, "paragraph_count")
    blocks = [b for b in text.split("\n\n") if b.strip()]
    return len(blocks)


def tab_to_spaces(text, width):
    fail = make_fail("tab_to_spaces")
    _check_text(fail, text, "tab_to_spaces")
    if type(width) is not int or width < 1:
        fail("bad_value:width")
    if width > MAX_TAB_WIDTH:
        fail("too_big:width")
    out = []
    col = 0
    total = 0
    for ch in text:
        if ch == "\t":
            pad = width - (col % width)
            out.append(" " * pad)
            col += pad
            total += pad
        else:
            out.append(ch)
            col = 0 if ch == "\n" else col + 1
            total += 1
        if total > MAX_TAB_OUTPUT:
            fail("too_many:output")
    return "".join(out)


def pig_latin_word(word):
    """Initial consonant cluster moves to the end + "ay"; leading vowel gets
    "yay". y is treated as a consonant everywhere."""
    fail = make_fail("pig_latin_word")
    _check_text(fail, word, "pig_latin_word")
    if not word or not word.isalpha():
        fail("bad_value:word")
    low = word.lower()
    if low[0] in VOWELS:
        return low + "yay"
    i = 0
    while i < len(low) and low[i] not in VOWELS:
        i += 1
    return low[i:] + low[:i] + "ay"


_SOUNDEX = {
    "b": "1", "f": "1", "p": "1", "v": "1",
    "c": "2", "g": "2", "j": "2", "k": "2", "q": "2", "s": "2", "x": "2",
    "z": "2",
    "d": "3", "t": "3",
    "l": "4",
    "m": "5", "n": "5",
    "r": "6",
}


def soundex_code(word):
    fail = make_fail("soundex_code")
    _check_text(fail, word, "soundex_code")
    if not word or not word.isalpha():
        fail("bad_value:word")
    low = word.lower()
    first_code = _SOUNDEX.get(low[0])
    digits = []
    prev_code = first_code
    prev_sep_vowel = False
    for ch in low[1:]:
        code = _SOUNDEX.get(ch)
        if code is None:
            if ch in "hw":
                pass
            else:
                prev_sep_vowel = True
            continue
        if code != prev_code or prev_sep_vowel:
            digits.append(code)
        prev_code = code
        prev_sep_vowel = False
    code = low[0].upper() + "".join(digits)
    return (code + "000")[:4]
