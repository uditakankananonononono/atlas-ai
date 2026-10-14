"""P235 concepts batch 27 (concepts 261-270, letter ciphers/encodings) - ten
new small deterministic letter concepts. 261-270 of the doc's 1000 (anchor
P235|L184). ASCII-strict; inputs bounded; oracles pinned in tests.
"""
from __future__ import annotations

from .p235_concepts_batch1 import MAX_ITEMS, check_str, make_fail

MAX_KEY_LEN = 1_000

_SCRABBLE = {
    "a": 1, "b": 3, "c": 3, "d": 2, "e": 1, "f": 4, "g": 2, "h": 4,
    "i": 1, "j": 8, "k": 5, "l": 1, "m": 3, "n": 1, "o": 1, "p": 3,
    "q": 10, "r": 1, "s": 1, "t": 1, "u": 1, "v": 4, "w": 4, "x": 8,
    "y": 4, "z": 10,
}
_NATO = ("alfa bravo charlie delta echo foxtrot golf hotel india juliett "
         "kilo lima mike november oscar papa quebec romeo sierra tango "
         "uniform victor whiskey xray yankee zulu").split(" ")
_T9 = ("", "", "abc", "def", "ghi", "jkl", "mno", "pqrs", "tuv", "wxyz")


def _checked(fail, text, name="text"):
    check_str(fail, text, name)
    if len(text) > MAX_ITEMS:
        fail("too_many:" + name)
    if not text.isascii():
        fail("bad_value:" + name)
    return text


def _letters_only(fail, text, name="text"):
    _checked(fail, text, name)
    if not text or not text.isalpha():
        fail("bad_value:" + name)
    return text.lower()


def atbash_cipher(text):
    """Atbash: a<->z per letter, case preserved, non-letters unchanged."""
    fail = make_fail("atbash_cipher")
    _checked(fail, text)
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append(chr(219 - ord(ch)))
        elif "A" <= ch <= "Z":
            out.append(chr(155 - ord(ch)))
        else:
            out.append(ch)
    return "".join(out)


def a1z26_encode(text):
    """Letters to dash-joined 1-26 positions."""
    fail = make_fail("a1z26_encode")
    low = _letters_only(fail, text)
    return "-".join(str(ord(ch) - 96) for ch in low)


def a1z26_decode(text):
    fail = make_fail("a1z26_decode")
    _checked(fail, text)
    if not text:
        fail("bad_value:text")
    parts = text.split("-")
    out = []
    for part in parts:
        if not part or len(part) > 2 or not part.isascii() or \
                not part.isdigit() or (len(part) > 1 and part[0] == "0"):
            fail("bad_value:text")
        value = int(part)
        if value < 1 or value > 26:
            fail("bad_value:text")
        out.append(chr(96 + value))
    return "".join(out)


def scrabble_score(text):
    """English Scrabble letter values summed; letters only."""
    fail = make_fail("scrabble_score")
    _checked(fail, text)
    if not text:
        return 0
    if not text.isalpha():
        fail("bad_value:text")
    return sum(_SCRABBLE[ch] for ch in text.lower())


def _vigenere(fail, text, key, direction):
    if type(key) is not str or not key.isalpha() or not key.isascii():
        fail("bad_value:key")
    if len(key) > MAX_KEY_LEN:
        fail("too_big:key")
    low_text = _letters_only(fail, text)
    low_key = key.lower()
    out = []
    for i, ch in enumerate(low_text):
        shift = ord(low_key[i % len(low_key)]) - 97
        out.append(chr(97 + (ord(ch) - 97 + direction * shift) % 26))
    return "".join(out).upper()


def vigenere_encode(text, key):
    fail = make_fail("vigenere_encode")
    return _vigenere(fail, text, key, 1)


def vigenere_decode(text, key):
    fail = make_fail("vigenere_decode")
    return _vigenere(fail, text, key, -1)


def nato_phonetic_render(text):
    fail = make_fail("nato_phonetic_render")
    low = _letters_only(fail, text)
    return " ".join(_NATO[ord(ch) - 97] for ch in low)


def t9_multitap_digits(text):
    """Multi-tap T9: each letter as its digit repeated by position,
    groups space-separated."""
    fail = make_fail("t9_multitap_digits")
    low = _letters_only(fail, text)
    groups = []
    for ch in low:
        for digit in range(2, 10):
            letters = _T9[digit]
            if ch in letters:
                groups.append(str(digit) * (letters.index(ch) + 1))
                break
    return " ".join(groups)


def alternating_case(text):
    """Lowercase at even character indices, uppercase at odd ones."""
    fail = make_fail("alternating_case")
    _checked(fail, text)
    out = []
    for i, ch in enumerate(text):
        out.append(ch.upper() if i % 2 else ch.lower())
    return "".join(out)


def disemvowel_text(text):
    """Remove ASCII vowels aeiou (either case); y stays."""
    fail = make_fail("disemvowel_text")
    _checked(fail, text)
    return "".join(ch for ch in text if ch.lower() not in "aeiou")
