"""Row 92 BATNA standalone delta (BATNA92). See docs/M20_BATNA92_CONTRACT.md.

Pure, offline, stdlib only. Ranks caller-declared utilities exactly.
Does not replace or edit negotiation_behavior_0085_0109._batna.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

BATNA92_VERSION = "1"

LIMITS = (
    "Utilities are caller-declared; nothing here verifies they are true or comparable in reality.",
    "A single option set is ranked; no sensitivity, probability or risk analysis.",
    "One option is not a negotiation BATNA proof: it is merely the only supplied option.",
    "Names are compared exactly, with no case or whitespace normalization.",
    "Not a replacement for the landed batna_identification mechanism.",
)


class Batna92Error(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _fmt(f: Fraction) -> str:
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


@dataclass(frozen=True)
class RankEntry:
    name: str
    utility: Fraction
    rank: int


@dataclass(frozen=True)
class BatnaRecord:
    version: str
    options_count: int
    best_names: tuple
    best_utility: Fraction
    is_tie: bool
    ranking: tuple
    margin_to_next: object
    limits: tuple

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "options_count": self.options_count,
            "best_names": list(self.best_names),
            "best_utility": _fmt(self.best_utility),
            "is_tie": self.is_tie,
            "ranking": [{"name": r.name, "utility": _fmt(r.utility), "rank": r.rank} for r in self.ranking],
            "margin_to_next": None if self.margin_to_next is None else _fmt(self.margin_to_next),
            "limits": list(self.limits),
        }


def _utility(name: str, u) -> Fraction:
    if isinstance(u, bool) or not isinstance(u, (int, float, Fraction, Decimal)):
        raise Batna92Error("BATNA92:UNCOMPARABLE", f"utility of {name!r} is not a finite real number")
    if isinstance(u, float) and not math.isfinite(u):
        raise Batna92Error("BATNA92:UNCOMPARABLE", f"utility of {name!r} is not finite")
    if isinstance(u, Decimal) and not u.is_finite():
        raise Batna92Error("BATNA92:UNCOMPARABLE", f"utility of {name!r} is not finite")
    return Fraction(u)


def identify_batna(options) -> BatnaRecord:
    if not isinstance(options, (list, tuple)):
        raise Batna92Error("BATNA92:BAD_SHAPE", "options must be a list or tuple")
    if len(options) == 0:
        raise Batna92Error("BATNA92:NO_OPTIONS", "at least one option is required")
    parsed = []
    for i, opt in enumerate(options):
        if not isinstance(opt, Mapping):
            raise Batna92Error("BATNA92:BAD_OPTION", f"option {i} is not a mapping")
        if set(opt.keys()) - {"name", "utility"}:
            raise Batna92Error("BATNA92:BAD_OPTION", f"option {i} has unknown keys")
        name = opt.get("name")
        if not isinstance(name, str) or name == "":
            raise Batna92Error("BATNA92:BAD_OPTION", f"option {i} needs a non-empty str name")
        if opt.get("utility") is None:
            raise Batna92Error("BATNA92:MISSING_UTILITY", f"option {name!r} has no utility")
        parsed.append((name, _utility(name, opt["utility"])))
    seen = set()
    for name, _ in parsed:
        if name in seen:
            raise Batna92Error("BATNA92:DUPLICATE_NAME", f"duplicate option name {name!r}")
        seen.add(name)
    ordered = sorted(parsed, key=lambda p: p[1], reverse=True)  # stable: ties keep input order
    ranking = []
    for idx, (name, u) in enumerate(ordered):
        rank = ranking[-1].rank if idx and u == ordered[idx - 1][1] else idx + 1
        ranking.append(RankEntry(name, u, rank))
    best_u = ordered[0][1]
    best_names = tuple(r.name for r in ranking if r.utility == best_u)
    lower = [r.utility for r in ranking if r.utility < best_u]
    margin = (best_u - lower[0]) if lower else None
    return BatnaRecord(BATNA92_VERSION, len(parsed), best_names, best_u, len(best_names) > 1,
                       tuple(ranking), margin, LIMITS)
