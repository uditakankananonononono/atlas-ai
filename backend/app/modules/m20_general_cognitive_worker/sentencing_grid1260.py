"""Row 1260 (title only: "Sentencing Guidelines"): caller-declared grid lookup.

The caller declares a grid (levels, categories, cells with [min, max]) and named level
adjustments. ``lookup`` adds the chosen adjustment deltas to a base level and returns the
declared cell range. That is the whole mechanism: integer addition and a dictionary read.
No cell is inferred, interpolated, clamped or guessed, and nothing is checked against any
real guideline. Every refusal starts with ``SENT1260:``.
"""
from __future__ import annotations

import unicodedata
from typing import Any

MAX_ITEMS = 64
MAX_TEXT = 256
MAX_NAME = 64

DISCLAIMER = ("SENT1260: arithmetic lookup in a caller-declared table for counsel review; "
              "not legal advice, not a sentence, not a prediction, and not verified against any real guideline.")

_KEYS = {"name", "edition", "source", "unit", "levels", "categories", "cells",
         "offense_adjustments", "offender_adjustments"}
_REQUIRED = ("name", "edition", "source", "unit", "levels", "categories", "cells")


class SentencingGridError(ValueError):
    """Refused declaration or lookup. The message always starts with ``SENT1260:``."""


def _fail(text: str) -> None:
    raise SentencingGridError(f"SENT1260: {text}")


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _text(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _bad_chars(v: str) -> bool:
    return any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in v)


class SentencingGrid:
    def __init__(self, declaration: dict[str, Any]) -> None:
        if type(declaration) is not dict:
            _fail("declaration must be an object")
        d = declaration  # never copied; every validated value is stored in a fresh container
        extra = set(d) - _KEYS
        if extra:
            _fail(f"unknown declaration key(s) {sorted(extra)}")
        for key in _REQUIRED:
            if key not in d:
                _fail(f"declaration key '{key}' is required")
        for key in ("name", "edition", "source", "unit"):
            if not _text(d[key]):
                _fail(f"'{key}' must be a non-blank string")
            if len(d[key]) > MAX_TEXT:
                _fail(f"'{key}' must be at most {MAX_TEXT} characters")
            if _bad_chars(d[key]):
                _fail(f"'{key}' contains a disallowed character (Cc, Cf, Zl or Zp)")
        levels = d["levels"]
        if not isinstance(levels, list) or not levels:
            _fail("levels must be a non-empty strictly ascending list of integers")
        if len(levels) > MAX_ITEMS:
            _fail(f"levels must have at most {MAX_ITEMS} entries")
        if (not all(_is_int(x) for x in levels)
                or any(b <= a for a, b in zip(levels, levels[1:]))):
            _fail("levels must be a non-empty strictly ascending list of integers")
        if any(b != a + 1 for a, b in zip(levels, levels[1:])):
            _fail("levels must be contiguous (no gaps)")
        cats = d["categories"]
        if not isinstance(cats, list) or not cats:
            _fail("categories must be a non-empty list of unique non-blank strings")
        if len(cats) > MAX_ITEMS:
            _fail(f"categories must have at most {MAX_ITEMS} entries")
        if (not all(_text(c) for c in cats)
                or len(set(cats)) != len(cats)):
            _fail("categories must be a non-empty list of unique non-blank strings")
        for c in cats:
            if len(c) > MAX_NAME:
                _fail(f"category names must be at most {MAX_NAME} characters")
            if _bad_chars(c):
                _fail(f"category names contain a disallowed character (Cc, Cf, Zl or Zp)")
        cells = d["cells"]
        if type(cells) is not dict:
            _fail("cells must be an object")
        if len(cells) > MAX_ITEMS:
            _fail(f"cells must have at most {MAX_ITEMS} rows")
        table: dict[tuple[int, str], tuple[int, int]] = {}
        for lkey, row in cells.items():
            try:
                lvl = int(lkey)
            except (TypeError, ValueError):
                lvl = None
            if lvl is None or lvl not in levels or str(lvl) != str(lkey):
                _fail(f"cell level '{lkey}' is not a declared level")
            if type(row) is not dict:
                _fail(f"cell row for level '{lkey}' must be an object")
            if len(row) > MAX_ITEMS:
                _fail(f"cell row for level '{lkey}' must have at most {MAX_ITEMS} entries")
            for cat, pair in row.items():
                if cat not in cats:
                    _fail(f"cell category '{cat}' at level '{lkey}' is not a declared category")
                if (not isinstance(pair, list) or len(pair) != 2 or not all(_is_int(x) for x in pair)
                        or pair[0] < 0 or pair[0] > pair[1]):
                    _fail(f"cell level {lkey}, category '{cat}' must be [min, max] non-negative integers with min <= max")
                table[(lvl, cat)] = (pair[0], pair[1])
        self._adj = {}
        for kind in ("offense", "offender"):
            raw = d.get(f"{kind}_adjustments", {})
            if type(raw) is not dict:
                _fail(f"{kind}_adjustments must be an object")
            if len(raw) > MAX_ITEMS:
                _fail(f"{kind}_adjustments must have at most {MAX_ITEMS} entries")
            for name, delta in raw.items():
                if not _text(name):
                    _fail(f"{kind} adjustment names must be non-blank strings")
                if len(name) > MAX_NAME:
                    _fail(f"{kind} adjustment names must be at most {MAX_NAME} characters")
                if _bad_chars(name):
                    _fail(f"{kind} adjustment names contain a disallowed character (Cc, Cf, Zl or Zp)")
                if not _is_int(delta):
                    _fail(f"{kind} adjustment '{name}' must be an integer delta")
            self._adj[kind] = dict(raw)
        self._meta = {"name": d["name"], "edition": d["edition"], "source": d["source"]}
        self._unit = d["unit"]
        self._levels = list(levels)
        self._cats = list(cats)
        self._table = table

    def lookup(self, base_level: int, category: str, offense: list[str] | None = None,
               offender: list[str] | None = None) -> dict[str, Any]:
        if not _is_int(base_level):
            _fail("base_level must be an integer")
        if not isinstance(category, str):
            _fail("category must be a string")
        applied: list[dict[str, Any]] = []
        total = 0
        for kind, names in (("offense", offense), ("offender", offender)):
            names = [] if names is None else names
            if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                _fail(f"{kind} must be a list of names")
            seen: set[str] = set()
            for name in names:
                if name not in self._adj[kind]:
                    _fail(f"unknown {kind} adjustment '{name}'")
                if name in seen:
                    _fail(f"{kind} adjustment '{name}' listed more than once")
                seen.add(name)
                delta = self._adj[kind][name]
                total += delta
                applied.append({"kind": kind, "name": name, "delta": delta})
        if category not in self._cats:
            _fail(f"unknown category '{category}'; declared: {self._cats}")
        level = base_level + total
        if level < self._levels[0] or level > self._levels[-1]:
            _fail(f"adjusted level {level} is outside the declared grid levels {self._levels[0]}..{self._levels[-1]}")
        cell = self._table.get((level, category))
        if cell is None:
            _fail(f"no declared cell for level {level}, category '{category}'")
        return {
            "range": {"min": cell[0], "max": cell[1], "unit": self._unit},
            "base_level": base_level, "adjusted_level": level, "category": category,
            "applied_adjustments": applied, "grid": dict(self._meta), "disclaimer": DISCLAIMER,
        }
